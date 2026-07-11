import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.graph import FieldAccess
from app.services.analyzer.ast_visitor import FieldAccessInfo

logger = logging.getLogger(__name__)


class FieldAccessBuilder:
    def __init__(self, db: AsyncSession, symbol_id_map: dict[str, uuid.UUID]):
        self.db = db
        self._symbol_id_map = symbol_id_map
        # Build field_name -> list of qualified names index
        self._field_index: dict[str, list[str]] = {}
        for qualified in symbol_id_map:
            parts = qualified.rsplit(".", 1)
            if len(parts) == 2:
                field_name = parts[1]
                self._field_index.setdefault(field_name, []).append(qualified)

    async def build(
        self, project_id: uuid.UUID, field_accesses: list[FieldAccessInfo], file_id_map: dict[str, uuid.UUID]
    ) -> int:
        count = 0
        for fa in field_accesses:
            accessor_id = self._resolve_accessor(fa.accessor_name)
            accessed_field_id = self._resolve_field(fa.field_name)
            if not accessor_id or not accessed_field_id:
                continue
            if accessor_id == accessed_field_id:
                continue
            record = FieldAccess(
                project_id=project_id,
                accessor_id=accessor_id,
                accessed_field_id=accessed_field_id,
                file_id=file_id_map.get(fa.file_path, accessor_id) if fa.file_path else accessor_id,
                line_number=fa.line_number,
            )
            self.db.add(record)
            count += 1
        await self.db.commit()
        logger.info(f"Built {count} field access edges for project {project_id}")
        return count

    def _resolve_accessor(self, accessor_name: str) -> uuid.UUID | None:
        return self._symbol_id_map.get(accessor_name)

    def _resolve_field(self, field_name: str) -> uuid.UUID | None:
        # Exact match first
        if field_name in self._symbol_id_map:
            return self._symbol_id_map[field_name]
        # Try "ClassName.fieldName" -> search for any Class.fieldName
        parts = field_name.rsplit(".", 1)
        if len(parts) == 2:
            _, name = parts
            candidates = self._field_index.get(name, [])
            if len(candidates) == 1:
                return self._symbol_id_map[candidates[0]]
        # Try matching by field name alone
        candidates = self._field_index.get(field_name, [])
        if len(candidates) == 1:
            return self._symbol_id_map[candidates[0]]
        return None
