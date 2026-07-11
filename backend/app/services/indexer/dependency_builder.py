import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File
from app.models.graph import Import, ImportType
from app.services.analyzer.ast_visitor import ImportInfo

logger = logging.getLogger(__name__)


class DependencyBuilder:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def build(self, project_id: uuid.UUID, imports_by_file: dict[str, list[ImportInfo]]) -> int:
        # Build file path -> file_id map
        stmt = select(File).where(File.project_id == project_id)
        result = await self.db.execute(stmt)
        file_map = {f.file_path: f.id for f in result.scalars().all()}

        count = 0
        for file_path, imports in imports_by_file.items():
            source_file_id = file_map.get(file_path)
            if not source_file_id:
                continue
            for imp in imports:
                import_type = ImportType.STATIC_IMPORT if imp.import_type == "static_import" else ImportType.IMPORT
                record = Import(
                    source_file_id=source_file_id,
                    target_module=imp.module_path,
                    import_type=import_type,
                )
                self.db.add(record)
                count += 1

        await self.db.commit()
        logger.info(f"Built {count} import dependencies for project {project_id}")
        return count
