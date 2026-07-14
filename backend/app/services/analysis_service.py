import asyncio
import logging
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AnalysisError
from app.db.session import async_session
from app.models.graph import CallGraph, FieldAccess, ImplementsRelation, Import
from app.models.project import Project, ProjectStatus
from app.models.symbol import Symbol
from app.models.file import File
from app.services.analyzer.git_manager import GitManager
from app.services.indexer.call_graph_builder import CallGraphBuilder
from app.services.indexer.dependency_builder import DependencyBuilder
from app.services.indexer.field_access_builder import FieldAccessBuilder
from app.services.indexer.symbol_builder import IndexResult, SymbolTableBuilder

logger = logging.getLogger(__name__)

MAX_CONCURRENT_ANALYSES = 2
MAX_RETRIES = 3


class AnalysisService:
    def __init__(self):
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_ANALYSES)
        self._tasks: dict[uuid.UUID, asyncio.Task] = {}

    async def _cleanup_analysis_data(self, db: AsyncSession, project_id: uuid.UUID) -> None:
        await db.execute(delete(CallGraph).where(CallGraph.project_id == project_id))
        await db.execute(delete(FieldAccess).where(FieldAccess.project_id == project_id))
        await db.execute(delete(ImplementsRelation).where(ImplementsRelation.project_id == project_id))
        await db.execute(
            delete(Import).where(
                Import.source_file_id.in_(select(File.id).where(File.project_id == project_id))
            )
        )
        await db.execute(
            delete(Symbol).where(
                Symbol.file_id.in_(select(File.id).where(File.project_id == project_id))
            )
        )
        await db.commit()

    async def run_analysis(self, project_id: uuid.UUID) -> None:
        async with async_session() as db:
            try:
                project = await db.get(Project, project_id)
                if not project:
                    logger.error(f"Project {project_id} not found")
                    return

                logger.info(f"Starting analysis for project {project.name}")

                # 清除旧分析数据，避免重跑时数据重复
                await self._cleanup_analysis_data(db, project_id)

                # Step 1: Git clone/pull
                project.status = ProjectStatus.CLONING
                await db.commit()
                git_mgr = GitManager(db)
                await git_mgr.clone(project)

                # Step 2: Parse & build symbol index
                project.status = ProjectStatus.PARSING
                await db.commit()
                symbol_builder = SymbolTableBuilder(db)
                index_result: IndexResult = await symbol_builder.build(project)

                # Step 3: Build call graph
                project.status = ProjectStatus.INDEXING
                await db.commit()
                call_builder = CallGraphBuilder(db, symbol_builder._symbol_id_map, index_result.implements_map)
                call_count = await call_builder.build(
                    project_id, index_result.calls, index_result.file_id_map
                )

                # Step 3.1: Build implements relations
                impl_count = await call_builder.build_implements(
                    project_id, index_result.file_id_map
                )

                # Step 3.5: Build field access graph
                fa_builder = FieldAccessBuilder(db, symbol_builder._symbol_id_map)
                fa_count = await fa_builder.build(
                    project_id, index_result.field_accesses, index_result.file_id_map
                )

                # Step 4: Build dependency graph
                dep_builder = DependencyBuilder(db)
                dep_count = await dep_builder.build(project_id, index_result.imports)

                # Step 5: Mark ready
                project.status = ProjectStatus.READY
                await db.commit()

                logger.info(
                    f"Analysis complete for {project.name}: "
                    f"{call_count} call edges, {fa_count} field accesses, {dep_count} imports, {impl_count} implements"
                )

            except Exception as e:
                logger.exception(f"Analysis failed for project {project_id}")
                try:
                    project = await db.get(Project, project_id)
                    if project and project.status != ProjectStatus.ERROR:
                        project.status = ProjectStatus.ERROR
                        await db.commit()
                except Exception:
                    pass
                raise

    def start_analysis(self, project_id: uuid.UUID) -> None:
        if project_id in self._tasks and not self._tasks[project_id].done():
            logger.warning(f"Analysis already running for {project_id}, skipping")
            return
        task = asyncio.create_task(self._run(project_id))
        self._tasks[project_id] = task
        task.add_done_callback(lambda t: self._tasks.pop(project_id, None))

    async def _run(self, project_id: uuid.UUID) -> None:
        async with self._semaphore:
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    await self.run_analysis(project_id)
                    return
                except Exception:
                    if attempt < MAX_RETRIES:
                        wait = 5 * attempt
                        logger.warning(f"Retry {attempt}/{MAX_RETRIES} for {project_id}, waiting {wait}s")
                        await asyncio.sleep(wait)
                    else:
                        logger.error(f"All {MAX_RETRIES} attempts failed for {project_id}")

    async def recover_stuck_projects(self) -> None:
        """Startup: reset projects stuck in intermediate states and re-trigger analysis."""
        async with async_session() as db:
            stuck_statuses = [ProjectStatus.CLONING, ProjectStatus.PARSING, ProjectStatus.INDEXING]
            result = await db.execute(
                select(Project).where(Project.status.in_(stuck_statuses))
            )
            projects = result.scalars().all()
            if not projects:
                return
            for project in projects:
                logger.info(f"Recovering stuck project {project.name} ({project.id}), resetting to PENDING")
                project.status = ProjectStatus.PENDING
            await db.commit()
            for project in projects:
                self.start_analysis(project.id)


analysis_service = AnalysisService()
