import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AnalysisError
from app.db.session import async_session
from app.models.project import Project, ProjectStatus
from app.services.analyzer.git_manager import GitManager
from app.services.indexer.call_graph_builder import CallGraphBuilder
from app.services.indexer.dependency_builder import DependencyBuilder
from app.services.indexer.field_access_builder import FieldAccessBuilder
from app.services.indexer.symbol_builder import IndexResult, SymbolTableBuilder

logger = logging.getLogger(__name__)


class AnalysisService:
    async def run_analysis(self, project_id: uuid.UUID) -> None:
        async with async_session() as db:
            try:
                project = await db.get(Project, project_id)
                if not project:
                    logger.error(f"Project {project_id} not found")
                    return

                logger.info(f"Starting analysis for project {project.name}")

                # Step 1: Git clone/pull
                project.status = ProjectStatus.CLONING
                await db.commit()
                git_mgr = GitManager(db)
                await git_mgr.clone(project)

                # Step 2: Parse & build symbol index
                symbol_builder = SymbolTableBuilder(db)
                index_result: IndexResult = await symbol_builder.build(project)

                # Step 3: Build call graph
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
        asyncio.create_task(self._run(project_id))

    async def _run(self, project_id: uuid.UUID) -> None:
        try:
            await self.run_analysis(project_id)
        except Exception:
            pass  # already logged in run_analysis


analysis_service = AnalysisService()
