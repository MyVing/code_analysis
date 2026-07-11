import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File
from app.models.graph import CallGraph, ImplementsRelation
from app.models.symbol import Symbol
from app.services.analyzer.ast_visitor import CallInfo

logger = logging.getLogger(__name__)


class CallGraphBuilder:
    def __init__(self, db: AsyncSession, symbol_id_map: dict[str, uuid.UUID], implements_map: dict[str, list[str]] | None = None):
        self.db = db
        self._symbol_id_map = symbol_id_map
        self._implements_map = implements_map or {}
        # Build method_name -> list of qualified names index for fuzzy matching
        self._method_index: dict[str, list[str]] = {}
        for qualified in symbol_id_map:
            parts = qualified.rsplit(".", 1)
            if len(parts) == 2:
                method_name = parts[1]
                self._method_index.setdefault(method_name, []).append(qualified)
        # Build field_name -> parent_class_qualified_names index
        # e.g. "UserService.userMapper" -> field, parent class is "UserService"
        # We need: simple field name "userMapper" -> ["UserMapper"] (type inferred from naming)
        # and: qualified field name "UserService.userMapper" -> ["UserMapper"]
        self._field_to_type: dict[str, list[str]] = {}
        for qualified in symbol_id_map:
            parts = qualified.rsplit(".", 1)
            if len(parts) == 2:
                parent_name, field_name = parts
                # Check if this symbol is a field (variable kind) by looking at naming patterns
                # In Java, field names are camelCase while class names are PascalCase
                if field_name[0].islower():
                    # This is likely a field. Infer type from naming convention:
                    # userMapper -> UserMapper, userDto -> UserDto
                    inferred_type = field_name[0].upper() + field_name[1:]
                    # Also handle common patterns: userService -> UserService
                    self._field_to_type.setdefault(field_name, []).append(inferred_type)
                    # Also store the qualified version
                    qualified_key = f"{parent_name}.{field_name}"
                    self._field_to_type.setdefault(qualified_key, []).append(inferred_type)

    async def build(self, project_id: uuid.UUID, calls: list[CallInfo], file_id_map: dict[str, uuid.UUID]) -> int:
        count = 0
        for call in calls:
            caller_id = self._resolve_caller(call.caller_name)
            callee_id = self._resolve_callee(call.callee_name)
            if not caller_id or not callee_id:
                continue
            if caller_id == callee_id:
                continue
            edge = CallGraph(
                project_id=project_id,
                caller_id=caller_id,
                callee_id=callee_id,
                file_id=file_id_map.get(call.file_path, caller_id) if call.file_path else caller_id,
                line_number=call.line_number,
            )
            self.db.add(edge)
            count += 1
        await self.db.commit()
        logger.info(f"Built {count} call graph edges for project {project_id}")
        return count

    def _resolve_caller(self, caller_name: str) -> uuid.UUID | None:
        return self._symbol_id_map.get(caller_name)

    def _resolve_callee(self, callee_name: str) -> uuid.UUID | None:
        # Exact match first
        if callee_name in self._symbol_id_map:
            return self._symbol_id_map[callee_name]
        # Try "ObjectType.methodName" -> search for any Class.methodName
        parts = callee_name.rsplit(".", 1)
        if len(parts) == 2:
            obj_name, method_name = parts
            # Strip "this." prefix: "this.userMapper.findById" -> "userMapper.findById"
            if obj_name.startswith("this."):
                obj_name = obj_name[5:]
            # Try resolving via field-to-type mapping
            # e.g. "userMapper.findById" -> look up "userMapper" -> "UserMapper" -> "UserMapper.findById"
            type_candidates = self._field_to_type.get(obj_name, [])
            for type_name in type_candidates:
                qualified = f"{type_name}.{method_name}"
                if qualified in self._symbol_id_map:
                    return self._symbol_id_map[qualified]
            # Fallback: search method index
            candidates = self._method_index.get(method_name, [])
            if len(candidates) == 1:
                return self._symbol_id_map[candidates[0]]
        # Try matching by method name alone (no qualifier)
        candidates = self._method_index.get(callee_name, [])
        if len(candidates) == 1:
            return self._symbol_id_map[candidates[0]]
        return None

    async def build_implements(self, project_id: uuid.UUID, file_id_map: dict[str, uuid.UUID]) -> int:
        """Build implements relations: interface class/method -> impl class/method."""
        count = 0
        for interface_name, impl_class_names in self._implements_map.items():
            interface_id = self._symbol_id_map.get(interface_name)
            if not interface_id:
                continue
            for impl_class_name in impl_class_names:
                impl_class_id = self._symbol_id_map.get(impl_class_name)
                if not impl_class_id:
                    continue
                # Class-level implements relation
                file_id = file_id_map.get("") or interface_id  # fallback
                # Find the file_id for the impl class
                impl_file_id = self._find_file_id_for_symbol(impl_class_name, file_id_map)
                edge = ImplementsRelation(
                    project_id=project_id,
                    interface_id=interface_id,
                    impl_id=impl_class_id,
                    file_id=impl_file_id,
                )
                self.db.add(edge)
                count += 1

                # Method-level implements relations
                # Find all methods of the interface and match them to impl class methods
                for qualified, sym_id in self._symbol_id_map.items():
                    parts = qualified.rsplit(".", 1)
                    if len(parts) != 2:
                        continue
                    parent, method_name = parts
                    if parent != interface_name:
                        continue
                    # Look for the same method in the impl class
                    impl_qualified = f"{impl_class_name}.{method_name}"
                    impl_method_id = self._symbol_id_map.get(impl_qualified)
                    if impl_method_id:
                        edge = ImplementsRelation(
                            project_id=project_id,
                            interface_id=sym_id,
                            impl_id=impl_method_id,
                            file_id=impl_file_id,
                        )
                        self.db.add(edge)
                        count += 1

        await self.db.commit()
        logger.info(f"Built {count} implements relations for project {project_id}")
        return count

    def _find_file_id_for_symbol(self, symbol_name: str, file_id_map: dict[str, uuid.UUID]) -> uuid.UUID:
        """Find the file_id for a class by searching the file_id_map for a path containing the class name."""
        for rel_path, fid in file_id_map.items():
            if symbol_name in rel_path:
                return fid
        # Fallback: return any file_id
        return next(iter(file_id_map.values())) if file_id_map else uuid.UUID(int=0)
