import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File
from app.models.project import Project, ProjectStatus
from app.models.symbol import Symbol, SymbolKind
from app.services.analyzer.ast_visitor import CallInfo, FieldAccessInfo, ImportInfo, ImplementsInfo, SymbolInfo
from app.services.analyzer.git_manager import GitManager
from app.services.analyzer.tree_sitter_parser import TreeSitterParser
from app.services.analyzer.ast_visitor import JavaASTVisitor

logger = logging.getLogger(__name__)


@dataclass
class IndexResult:
    file_id_map: dict[str, uuid.UUID] = field(default_factory=dict)
    calls: list[CallInfo] = field(default_factory=list)
    field_accesses: list[FieldAccessInfo] = field(default_factory=list)
    imports: dict[str, list[ImportInfo]] = field(default_factory=dict)
    implements_map: dict[str, list[str]] = field(default_factory=dict)

    def add_visitor_result(self, rel_path: str, visitor: JavaASTVisitor) -> None:
        for call in visitor.calls:
            call.file_path = rel_path
            self.calls.append(call)
        for fa in visitor.field_accesses:
            fa.file_path = rel_path
            self.field_accesses.append(fa)
        if visitor.imports:
            self.imports[rel_path] = visitor.imports
        for impl_info in visitor.implements_list:
            for iface_name in impl_info.interface_names:
                self.implements_map.setdefault(iface_name, []).append(impl_info.class_name)


class SymbolTableBuilder:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.parser = TreeSitterParser()
        self._symbol_id_map: dict[str, uuid.UUID] = {}

    async def build(self, project: Project) -> IndexResult:
        result = IndexResult()

        project.status = ProjectStatus.PARSING
        await self.db.commit()

        git_mgr = GitManager(self.db)
        file_list = await git_mgr.get_file_list(project.name)
        workspace = git_mgr._workspace_path(project.name)

        project.status = ProjectStatus.INDEXING
        await self.db.commit()

        for rel_path in file_list:
            full_path = workspace / rel_path
            file_record = await self._upsert_file(project.id, rel_path, full_path)
            visitor = self._parse_file(full_path)
            if not visitor:
                continue
            result.file_id_map[rel_path] = file_record.id
            result.add_visitor_result(rel_path, visitor)
            for sym_info in visitor.symbols:
                await self._insert_symbol(sym_info, file_record.id, None)

        await self.db.commit()
        logger.info(f"Indexed {len(file_list)} files for project {project.name}")
        return result

    def _parse_file(self, full_path: Path) -> JavaASTVisitor | None:
        try:
            root_node = self.parser.parse_file(full_path)
            if not root_node:
                return None
            visitor = JavaASTVisitor()
            visitor.visit(root_node)
            return visitor
        except Exception as e:
            logger.warning(f"Failed to parse {full_path}: {e}")
            return None

    async def _upsert_file(self, project_id: uuid.UUID, rel_path: str, full_path: Path) -> File:
        content = full_path.read_bytes()
        content_hash = hashlib.md5(content).hexdigest()
        stmt = select(File).where(File.project_id == project_id, File.file_path == rel_path)
        result = await self.db.execute(stmt)
        file_record = result.scalar_one_or_none()
        if file_record:
            file_record.content_hash = content_hash
        else:
            file_record = File(
                project_id=project_id,
                file_path=rel_path,
                language="java",
                content_hash=content_hash,
            )
            self.db.add(file_record)
        await self.db.flush()
        return file_record

    async def _insert_symbol(
        self, sym_info: SymbolInfo, file_id: uuid.UUID, parent_id: uuid.UUID | None
    ) -> Symbol:
        qualified_name = f"{sym_info.parent_name}.{sym_info.name}" if sym_info.parent_name else sym_info.name
        symbol = Symbol(
            file_id=file_id,
            parent_id=parent_id,
            name=sym_info.name,
            kind=sym_info.kind,
            signature=sym_info.signature,
            start_line=sym_info.start_line,
            end_line=sym_info.end_line,
            modifiers=sym_info.modifiers,
        )
        self.db.add(symbol)
        await self.db.flush()
        self._symbol_id_map[qualified_name] = symbol.id

        for child in sym_info.children:
            child.parent_name = sym_info.name
            await self._insert_symbol(child, file_id, symbol.id)

        return symbol

    def get_symbol_id(self, qualified_name: str) -> uuid.UUID | None:
        return self._symbol_id_map.get(qualified_name)
