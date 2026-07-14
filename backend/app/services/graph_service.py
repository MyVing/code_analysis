import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import FileNotFoundError, ProjectNotFoundError, SymbolNotFoundError
from app.models.file import File
from app.models.graph import CallGraph, FieldAccess, ImplementsRelation
from app.models.project import Project
from app.models.symbol import Symbol, SymbolKind
from app.schemas.graph import GraphEdge, GraphNode


def symbol_to_node(symbol: Symbol, file_path: str) -> GraphNode:
    return GraphNode(
        id=symbol.id,
        name=symbol.name,
        kind=symbol.kind.value,
        file_path=file_path,
        start_line=symbol.start_line,
        end_line=symbol.end_line,
        parent_id=symbol.parent_id,
        file_id=symbol.file_id,
        signature=symbol.signature,
        modifiers=symbol.modifiers,
    )


async def get_file_path(db: AsyncSession, file_id: uuid.UUID) -> str:
    stmt = select(File.file_path).where(File.id == file_id)
    return (await db.execute(stmt)).scalar_one_or_none() or ""


async def fetch_symbols_with_paths(db: AsyncSession, symbol_ids: set[uuid.UUID]) -> list[GraphNode]:
    if not symbol_ids:
        return []
    stmt = (
        select(Symbol, File.file_path)
        .join(File, Symbol.file_id == File.id)
        .where(Symbol.id.in_(symbol_ids))
    )
    result = await db.execute(stmt)
    return [symbol_to_node(s, fp) for s, fp in result.all()]


async def fetch_field_access_edges(
    db: AsyncSession, project_id: uuid.UUID, symbol_ids: set[uuid.UUID]
) -> list[GraphEdge]:
    if not symbol_ids:
        return []
    stmt = select(FieldAccess).where(
        FieldAccess.project_id == project_id,
        FieldAccess.accessor_id.in_(symbol_ids),
    )
    result = await db.execute(stmt)
    return [
        GraphEdge(
            id=fa.id,
            source=fa.accessor_id,
            target=fa.accessed_field_id,
            edge_type="field_access",
            line_number=fa.line_number,
        )
        for fa in result.scalars().all()
    ]


async def fetch_children_of_classes(
    db: AsyncSession, class_ids: set[uuid.UUID]
) -> tuple[list[GraphNode], list[GraphEdge]]:
    if not class_ids:
        return [], []
    stmt = (
        select(Symbol, File.file_path)
        .join(File, Symbol.file_id == File.id)
        .where(Symbol.parent_id.in_(class_ids))
        .order_by(Symbol.start_line)
    )
    result = await db.execute(stmt)
    nodes, edges = [], []
    for s, fp in result.all():
        nodes.append(symbol_to_node(s, fp))
        edges.append(GraphEdge(
            id=uuid.uuid4(),
            source=s.parent_id,
            target=s.id,
            edge_type="contains",
        ))
    return nodes, edges


async def fetch_implements_edges(
    db: AsyncSession, project_id: uuid.UUID, symbol_ids: set[uuid.UUID]
) -> tuple[list[GraphEdge], set[uuid.UUID]]:
    if not symbol_ids:
        return [], set()
    stmt = select(ImplementsRelation).where(
        ImplementsRelation.project_id == project_id,
        ImplementsRelation.interface_id.in_(symbol_ids),
    )
    result = await db.execute(stmt)
    edges, impl_ids = [], set()
    for ir in result.scalars().all():
        edges.append(GraphEdge(
            id=ir.id,
            source=ir.interface_id,
            target=ir.impl_id,
            edge_type="implements",
        ))
        impl_ids.add(ir.impl_id)
    return edges, impl_ids


async def fetch_call_edges(
    db: AsyncSession, project_id: uuid.UUID, caller_ids: set[uuid.UUID]
) -> list[GraphEdge]:
    if not caller_ids:
        return []
    stmt = select(CallGraph).where(
        CallGraph.project_id == project_id,
        CallGraph.caller_id.in_(caller_ids),
    )
    result = await db.execute(stmt)
    return [
        GraphEdge(
            id=cg.id,
            source=cg.caller_id,
            target=cg.callee_id,
            edge_type="call",
            line_number=cg.line_number,
        )
        for cg in result.scalars().all()
    ]


async def fetch_callee_edges(
    db: AsyncSession, project_id: uuid.UUID, callee_ids: set[uuid.UUID]
) -> list[GraphEdge]:
    if not callee_ids:
        return []
    stmt = select(CallGraph).where(
        CallGraph.project_id == project_id,
        CallGraph.callee_id.in_(callee_ids),
    )
    result = await db.execute(stmt)
    return [
        GraphEdge(
            id=cg.id,
            source=cg.caller_id,
            target=cg.callee_id,
            edge_type="call",
            line_number=cg.line_number,
        )
        for cg in result.scalars().all()
    ]


async def fetch_all_call_edges(
    db: AsyncSession, project_id: uuid.UUID
) -> list[GraphEdge]:
    stmt = select(CallGraph).where(CallGraph.project_id == project_id)
    result = await db.execute(stmt)
    return [
        GraphEdge(
            id=cg.id,
            source=cg.caller_id,
            target=cg.callee_id,
            edge_type="call",
            line_number=cg.line_number,
        )
        for cg in result.scalars().all()
    ]


async def fetch_all_implements_edges(
    db: AsyncSession, project_id: uuid.UUID
) -> list[GraphEdge]:
    stmt = select(ImplementsRelation).where(ImplementsRelation.project_id == project_id)
    result = await db.execute(stmt)
    return [
        GraphEdge(
            id=ir.id,
            source=ir.interface_id,
            target=ir.impl_id,
            edge_type="implements",
        )
        for ir in result.scalars().all()
    ]


async def fetch_file_symbols_with_contains(
    db: AsyncSession, project_id: uuid.UUID, file_id: uuid.UUID
) -> tuple[list[GraphNode], list[GraphEdge]]:
    stmt = (
        select(Symbol, File.file_path)
        .join(File, Symbol.file_id == File.id)
        .where(Symbol.file_id == file_id)
        .order_by(Symbol.start_line)
    )
    result = await db.execute(stmt)
    rows = result.all()

    nodes = [symbol_to_node(s, fp) for s, fp in rows]
    symbol_ids = {s.id for s, _ in rows}

    edges: list[GraphEdge] = []
    for s, _ in rows:
        if s.parent_id and s.parent_id in symbol_ids:
            edges.append(GraphEdge(
                id=uuid.uuid4(),
                source=s.parent_id,
                target=s.id,
                edge_type="contains",
            ))

    method_ids = {s.id for s, _ in rows if s.kind in (SymbolKind.METHOD, SymbolKind.FUNCTION)}
    if method_ids:
        call_edges = await fetch_call_edges(db, project_id, method_ids)
        edges.extend(call_edges)
        fa_edges = await fetch_field_access_edges(db, project_id, method_ids)
        edges.extend(fa_edges)

    return nodes, edges


async def fetch_project_symbols(db: AsyncSession, project_id: uuid.UUID) -> list[GraphNode]:
    stmt = (
        select(Symbol, File.file_path)
        .join(File, Symbol.file_id == File.id)
        .where(File.project_id == project_id)
    )
    result = await db.execute(stmt)
    return [symbol_to_node(s, fp) for s, fp in result.all()]


async def fetch_symbol_children(
    db: AsyncSession, symbol_id: uuid.UUID
) -> tuple[list[GraphNode], list[uuid.UUID]]:
    stmt = (
        select(Symbol, File.file_path)
        .join(File, Symbol.file_id == File.id)
        .where(Symbol.parent_id == symbol_id)
        .order_by(Symbol.start_line)
    )
    result = await db.execute(stmt)
    rows = result.all()
    nodes = [symbol_to_node(s, fp) for s, fp in rows]
    child_ids = [s.id for s, _ in rows]
    return nodes, child_ids


async def fetch_class_method_ids(db: AsyncSession, class_id: uuid.UUID) -> list[uuid.UUID]:
    stmt = select(Symbol).where(Symbol.parent_id == class_id)
    result = await db.execute(stmt)
    return [m.id for m in result.scalars().all()]


async def validate_project(db: AsyncSession, project_id: uuid.UUID) -> None:
    project = await db.get(Project, project_id)
    if not project:
        raise ProjectNotFoundError()


async def validate_symbol(db: AsyncSession, symbol_id: uuid.UUID) -> Symbol:
    symbol = await db.get(Symbol, symbol_id)
    if not symbol:
        raise SymbolNotFoundError()
    return symbol


async def validate_file(db: AsyncSession, project_id: uuid.UUID, file_id: uuid.UUID) -> File:
    file = await db.get(File, file_id)
    if not file or file.project_id != project_id:
        raise FileNotFoundError()
    return file
