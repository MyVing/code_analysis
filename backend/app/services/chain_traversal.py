import uuid
from collections import deque

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.graph import CallGraph, FieldAccess
from app.models.symbol import Symbol, SymbolKind
from app.schemas.graph import GraphEdge, GraphNode
from app.services.graph_service import (
    fetch_children_of_classes,
    fetch_implements_edges,
    get_file_path,
    symbol_to_node,
)


async def traverse_full_chain(
    db: AsyncSession,
    project_id: uuid.UUID,
    symbol: Symbol,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    start_ids: set[uuid.UUID] = {symbol.id}
    if symbol.kind in (SymbolKind.CLASS, SymbolKind.INTERFACE, SymbolKind.ENUM):
        method_stmt = select(Symbol).where(Symbol.parent_id == symbol.id)
        method_result = await db.execute(method_stmt)
        for m in method_result.scalars().all():
            start_ids.add(m.id)

    visited: set[uuid.UUID] = set()
    queue: deque[uuid.UUID] = deque(start_ids)
    all_symbol_ids: set[uuid.UUID] = set(start_ids)
    all_edges: list[GraphEdge] = []

    while queue:
        batch = []
        while queue and len(batch) < 50:
            sid = queue.popleft()
            if sid in visited:
                continue
            visited.add(sid)
            batch.append(sid)

        if not batch:
            continue

        batch_set = set(batch)

        # Calls FROM these symbols
        caller_stmt = select(CallGraph).where(
            CallGraph.project_id == project_id,
            CallGraph.caller_id.in_(batch),
        )
        caller_result = await db.execute(caller_stmt)
        for cg in caller_result.scalars().all():
            all_edges.append(GraphEdge(
                id=cg.id,
                source=cg.caller_id,
                target=cg.callee_id,
                edge_type="call",
                line_number=cg.line_number,
            ))
            if cg.callee_id not in visited:
                all_symbol_ids.add(cg.callee_id)
                queue.append(cg.callee_id)

        # Field accesses FROM these symbols
        fa_stmt = select(FieldAccess).where(
            FieldAccess.project_id == project_id,
            FieldAccess.accessor_id.in_(batch),
        )
        fa_result = await db.execute(fa_stmt)
        for fa in fa_result.scalars().all():
            all_edges.append(GraphEdge(
                id=fa.id,
                source=fa.accessor_id,
                target=fa.accessed_field_id,
                edge_type="field_access",
                line_number=fa.line_number,
            ))
            if fa.accessed_field_id not in visited:
                all_symbol_ids.add(fa.accessed_field_id)
                queue.append(fa.accessed_field_id)
                field_sym = await db.get(Symbol, fa.accessed_field_id)
                if field_sym and field_sym.parent_id and field_sym.parent_id not in visited:
                    all_symbol_ids.add(field_sym.parent_id)
                    queue.append(field_sym.parent_id)

        # Implements relations FROM these symbols
        impl_edges, impl_ids = await fetch_implements_edges(db, project_id, batch_set)
        all_edges.extend(impl_edges)
        for impl_id in impl_ids:
            if impl_id not in visited:
                all_symbol_ids.add(impl_id)
                queue.append(impl_id)
                impl_sym = await db.get(Symbol, impl_id)
                if impl_sym and impl_sym.kind in (SymbolKind.CLASS, SymbolKind.INTERFACE):
                    impl_method_stmt = select(Symbol).where(Symbol.parent_id == impl_id)
                    impl_method_result = await db.execute(impl_method_stmt)
                    for m in impl_method_result.scalars().all():
                        if m.id not in visited:
                            all_symbol_ids.add(m.id)
                            queue.append(m.id)

    # Fetch all discovered symbols
    from app.models.file import File
    sym_stmt = (
        select(Symbol, File.file_path)
        .join(File, Symbol.file_id == File.id)
        .where(Symbol.id.in_(all_symbol_ids))
    )
    sym_result = await db.execute(sym_stmt)
    sym_rows = sym_result.all()

    # Discover class symbols and fetch their children
    class_ids_in_chain: set[uuid.UUID] = set()
    for s, _ in sym_rows:
        if s.kind in (SymbolKind.CLASS, SymbolKind.INTERFACE, SymbolKind.ENUM):
            class_ids_in_chain.add(s.id)

    child_nodes: list[GraphNode] = []
    if class_ids_in_chain:
        class_children, contains_edges = await fetch_children_of_classes(db, class_ids_in_chain)
        child_nodes.extend(class_children)
        all_edges.extend(contains_edges)

        child_method_ids = {n.id for n in class_children if n.kind in (SymbolKind.METHOD, SymbolKind.FUNCTION)}
        if child_method_ids:
            child_fa_stmt = select(FieldAccess).where(
                FieldAccess.project_id == project_id,
                FieldAccess.accessor_id.in_(child_method_ids),
            )
            child_fa_result = await db.execute(child_fa_stmt)
            for fa in child_fa_result.scalars().all():
                all_edges.append(GraphEdge(
                    id=fa.id,
                    source=fa.accessor_id,
                    target=fa.accessed_field_id,
                    edge_type="field_access",
                    line_number=fa.line_number,
                ))
                if fa.accessed_field_id not in all_symbol_ids:
                    all_symbol_ids.add(fa.accessed_field_id)
                    field_sym = await db.get(Symbol, fa.accessed_field_id)
                    if field_sym:
                        fp = await get_file_path(db, field_sym.file_id)
                        child_nodes.append(symbol_to_node(field_sym, fp))

    nodes = [symbol_to_node(s, fp) for s, fp in sym_rows]
    nodes.extend(child_nodes)

    # Add parent-child containment edges
    node_ids = {n.id for n in nodes}
    for n in nodes:
        if n.parent_id and n.parent_id in node_ids:
            contains_already = any(
                e.edge_type == "contains" and e.source == n.parent_id and e.target == n.id
                for e in all_edges
            )
            if not contains_already:
                all_edges.append(GraphEdge(
                    id=uuid.uuid4(),
                    source=n.parent_id,
                    target=n.id,
                    edge_type="contains",
                ))

    return nodes, all_edges
