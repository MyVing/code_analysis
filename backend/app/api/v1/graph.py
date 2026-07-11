import uuid
from collections import deque

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.exceptions import ProjectNotFoundError, SymbolNotFoundError, FileNotFoundError
from app.models.file import File
from app.models.graph import CallGraph, FieldAccess, Import, ImplementsRelation
from app.models.project import Project
from app.models.symbol import Symbol, SymbolKind
from app.schemas.graph import CallGraphRead, ExpandedGraphData, GraphData, GraphEdge, GraphNode, ImportRead

router = APIRouter(prefix="/graph", tags=["graph"])


def _symbol_to_node(symbol: Symbol, file_path: str) -> GraphNode:
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


async def _get_file_path(db: AsyncSession, file_id: uuid.UUID) -> str:
    stmt = select(File.file_path).where(File.id == file_id)
    return (await db.execute(stmt)).scalar_one_or_none() or ""


async def _fetch_symbols_with_paths(db: AsyncSession, symbol_ids: set[uuid.UUID]) -> list[GraphNode]:
    if not symbol_ids:
        return []
    stmt = (
        select(Symbol, File.file_path)
        .join(File, Symbol.file_id == File.id)
        .where(Symbol.id.in_(symbol_ids))
    )
    result = await db.execute(stmt)
    return [_symbol_to_node(s, fp) for s, fp in result.all()]


async def _fetch_field_access_edges(db: AsyncSession, project_id: uuid.UUID, symbol_ids: set[uuid.UUID]) -> list[GraphEdge]:
    """Fetch field_access edges where accessor is in symbol_ids."""
    if not symbol_ids:
        return []
    stmt = select(FieldAccess).where(
        FieldAccess.project_id == project_id,
        FieldAccess.accessor_id.in_(symbol_ids),
    )
    result = await db.execute(stmt)
    edges = []
    for fa in result.scalars().all():
        edges.append(GraphEdge(
            id=fa.id,
            source=fa.accessor_id,
            target=fa.accessed_field_id,
            edge_type="field_access",
            line_number=fa.line_number,
        ))
    return edges


async def _fetch_children_of_classes(db: AsyncSession, class_ids: set[uuid.UUID]) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Fetch all child methods/fields of given class symbol IDs."""
    if not class_ids:
        return [], []
    stmt = (
        select(Symbol, File.file_path)
        .join(File, Symbol.file_id == File.id)
        .where(Symbol.parent_id.in_(class_ids))
        .order_by(Symbol.start_line)
    )
    result = await db.execute(stmt)
    nodes = []
    edges = []
    for s, fp in result.all():
        nodes.append(_symbol_to_node(s, fp))
        edges.append(GraphEdge(
            id=uuid.uuid4(),
            source=s.parent_id,
            target=s.id,
            edge_type="contains",
        ))
    return nodes, edges


async def _fetch_implements_edges(db: AsyncSession, project_id: uuid.UUID, symbol_ids: set[uuid.UUID]) -> tuple[list[GraphEdge], set[uuid.UUID]]:
    """Fetch implements edges where interface_id is in symbol_ids.
    Returns (edges, impl_symbol_ids) — the discovered implementation symbol IDs."""
    if not symbol_ids:
        return [], set()
    stmt = select(ImplementsRelation).where(
        ImplementsRelation.project_id == project_id,
        ImplementsRelation.interface_id.in_(symbol_ids),
    )
    result = await db.execute(stmt)
    edges = []
    impl_ids: set[uuid.UUID] = set()
    for ir in result.scalars().all():
        edges.append(GraphEdge(
            id=ir.id,
            source=ir.interface_id,
            target=ir.impl_id,
            edge_type="implements",
        ))
        impl_ids.add(ir.impl_id)
    return edges, impl_ids
async def get_call_graph(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise ProjectNotFoundError()
    stmt = select(CallGraph).where(CallGraph.project_id == project_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/imports/{project_id}", response_model=list[ImportRead])
async def get_imports(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise ProjectNotFoundError()
    stmt = select(File).where(File.project_id == project_id)
    result = await db.execute(stmt)
    file_ids = [f.id for f in result.scalars().all()]
    if not file_ids:
        return []
    stmt = select(Import).where(Import.source_file_id.in_(file_ids))
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/visualization/{project_id}", response_model=GraphData)
async def get_graph_visualization(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise ProjectNotFoundError()

    stmt = (
        select(Symbol, File.file_path)
        .join(File, Symbol.file_id == File.id)
        .where(File.project_id == project_id)
    )
    result = await db.execute(stmt)
    rows = result.all()
    nodes = [_symbol_to_node(s, fp) for s, fp in rows]

    stmt = select(CallGraph).where(CallGraph.project_id == project_id)
    result = await db.execute(stmt)
    edges = [
        GraphEdge(
            id=cg.id,
            source=cg.caller_id,
            target=cg.callee_id,
            edge_type="call",
            line_number=cg.line_number,
        )
        for cg in result.scalars().all()
    ]

    # Also include implements relations
    impl_stmt = select(ImplementsRelation).where(ImplementsRelation.project_id == project_id)
    impl_result = await db.execute(impl_stmt)
    for ir in impl_result.scalars().all():
        edges.append(GraphEdge(
            id=ir.id,
            source=ir.interface_id,
            target=ir.impl_id,
            edge_type="implements",
        ))

    return GraphData(nodes=nodes, edges=edges)


@router.get("/call-graph/{project_id}/expand/{symbol_id}", response_model=ExpandedGraphData)
async def expand_symbol_graph(
    project_id: uuid.UUID,
    symbol_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project:
        raise ProjectNotFoundError()

    symbol = await db.get(Symbol, symbol_id)
    if not symbol:
        raise SymbolNotFoundError()

    child_stmt = (
        select(Symbol, File.file_path)
        .join(File, Symbol.file_id == File.id)
        .where(Symbol.parent_id == symbol_id)
        .order_by(Symbol.start_line)
    )
    child_result = await db.execute(child_stmt)
    child_rows = child_result.all()

    child_ids = [s.id for s, _ in child_rows]
    child_nodes = [_symbol_to_node(s, fp) for s, fp in child_rows]

    edges: list[GraphEdge] = []
    if child_ids:
        caller_stmt = select(CallGraph).where(
            CallGraph.project_id == project_id,
            CallGraph.caller_id.in_(child_ids),
        )
        caller_result = await db.execute(caller_stmt)
        for cg in caller_result.scalars().all():
            edges.append(GraphEdge(
                id=cg.id,
                source=cg.caller_id,
                target=cg.callee_id,
                edge_type="call",
                line_number=cg.line_number,
            ))

        callee_stmt = select(CallGraph).where(
            CallGraph.project_id == project_id,
            CallGraph.callee_id.in_(child_ids),
        )
        callee_result = await db.execute(callee_stmt)
        existing_edge_ids = {e.id for e in edges}
        for cg in callee_result.scalars().all():
            if cg.id not in existing_edge_ids:
                edges.append(GraphEdge(
                    id=cg.id,
                    source=cg.caller_id,
                    target=cg.callee_id,
                    edge_type="call",
                    line_number=cg.line_number,
                ))

        # Field access edges from child methods
        fa_edges = await _fetch_field_access_edges(db, project_id, set(child_ids))
        edges.extend(fa_edges)

        # Implements edges: if any child is an interface, follow to its implementation
        interface_ids = {s.id for s, _ in child_rows if s.kind == SymbolKind.INTERFACE}
        if interface_ids:
            impl_edges, impl_ids = await _fetch_implements_edges(db, project_id, interface_ids)
            edges.extend(impl_edges)
            if impl_ids:
                impl_nodes = await _fetch_symbols_with_paths(db, impl_ids)
                child_nodes.extend(impl_nodes)

    parent_fp = await _get_file_path(db, symbol.file_id)
    return ExpandedGraphData(
        parent_node=_symbol_to_node(symbol, parent_fp),
        child_nodes=child_nodes,
        edges=edges,
    )


@router.get("/file-symbols/{project_id}/{file_id}", response_model=GraphData)
async def get_file_symbols(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all symbols in a file — initial view when clicking a file in the tree."""
    project = await db.get(Project, project_id)
    if not project:
        raise ProjectNotFoundError()

    file = await db.get(File, file_id)
    if not file or file.project_id != project_id:
        raise FileNotFoundError()

    stmt = (
        select(Symbol, File.file_path)
        .join(File, Symbol.file_id == File.id)
        .where(Symbol.file_id == file_id)
        .order_by(Symbol.start_line)
    )
    result = await db.execute(stmt)
    rows = result.all()

    nodes = [_symbol_to_node(s, fp) for s, fp in rows]

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

    # Also include call edges within this file
    method_ids = {s.id for s, _ in rows if s.kind in (SymbolKind.METHOD, SymbolKind.FUNCTION)}
    if method_ids:
        caller_stmt = select(CallGraph).where(
            CallGraph.project_id == project_id,
            CallGraph.caller_id.in_(method_ids),
        )
        caller_result = await db.execute(caller_stmt)
        for cg in caller_result.scalars().all():
            edges.append(GraphEdge(
                id=cg.id,
                source=cg.caller_id,
                target=cg.callee_id,
                edge_type="call",
                line_number=cg.line_number,
            ))

        # Field access edges
        fa_edges = await _fetch_field_access_edges(db, project_id, method_ids)
        edges.extend(fa_edges)

    return GraphData(nodes=nodes, edges=edges)


@router.get("/expand-call/{project_id}/{symbol_id}", response_model=ExpandedGraphData)
async def expand_call(
    project_id: uuid.UUID,
    symbol_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Expand one method's outgoing calls — show what this method calls."""
    project = await db.get(Project, project_id)
    if not project:
        raise ProjectNotFoundError()

    symbol = await db.get(Symbol, symbol_id)
    if not symbol:
        raise SymbolNotFoundError()

    # Find call edges where this symbol is the caller
    stmt = select(CallGraph).where(
        CallGraph.project_id == project_id,
        CallGraph.caller_id == symbol_id,
    )
    result = await db.execute(stmt)
    call_edges = result.scalars().all()

    callee_ids = list({cg.callee_id for cg in call_edges})

    # For each callee that is a class, also fetch its child methods
    child_nodes: list[GraphNode] = []
    child_class_ids: set[uuid.UUID] = set()
    contains_edges_cache: list[GraphEdge] = []

    if callee_ids:
        callee_nodes = await _fetch_symbols_with_paths(db, set(callee_ids))
        child_nodes.extend(callee_nodes)

        # Identify which callees are classes — fetch their children
        for node in callee_nodes:
            if node.kind in ("class", "interface", "enum"):
                child_class_ids.add(node.id)

        if child_class_ids:
            class_children, contains_edges = await _fetch_children_of_classes(db, child_class_ids)
            child_nodes.extend(class_children)
            contains_edges_cache = contains_edges
            # Also add call edges from these children
            child_method_ids = {n.id for n in class_children if n.kind in ("method", "function")}
            if child_method_ids:
                inner_caller_stmt = select(CallGraph).where(
                    CallGraph.project_id == project_id,
                    CallGraph.caller_id.in_(child_method_ids),
                )
                inner_result = await db.execute(inner_caller_stmt)
                for cg in inner_result.scalars().all():
                    call_edges.append(cg)

    # Collect all callee IDs from call_edges (including inner calls from class children)
    all_callee_ids: set[uuid.UUID] = {cg.callee_id for cg in call_edges}
    # Fetch any callee nodes not already in child_nodes
    existing_child_ids = {n.id for n in child_nodes}
    missing_callee_ids = all_callee_ids - existing_child_ids
    if missing_callee_ids:
        missing_nodes = await _fetch_symbols_with_paths(db, missing_callee_ids)
        child_nodes.extend(missing_nodes)

    edges = [
        GraphEdge(
            id=cg.id,
            source=cg.caller_id,
            target=cg.callee_id,
            edge_type="call",
            line_number=cg.line_number,
        )
        for cg in call_edges
    ]

    # Add contains edges for class children
    for ce in contains_edges_cache:
        if ce.id not in {e.id for e in edges}:
            edges.append(ce)

    # Field access edges
    accessor_ids = {symbol_id}
    accessor_ids.update({n.id for n in child_nodes if n.kind in ("method", "function")})
    fa_edges = await _fetch_field_access_edges(db, project_id, accessor_ids)
    edges.extend(fa_edges)

    # Implements edges: if any callee is an interface, follow to its implementation
    all_symbol_ids_for_impl = {n.id for n in child_nodes if n.kind == "interface"}
    if all_symbol_ids_for_impl:
        impl_edges, impl_ids = await _fetch_implements_edges(db, project_id, all_symbol_ids_for_impl)
        edges.extend(impl_edges)
        if impl_ids:
            impl_nodes = await _fetch_symbols_with_paths(db, impl_ids)
            child_nodes.extend(impl_nodes)
            # Also fetch children of impl classes
            impl_class_ids = {n.id for n in impl_nodes if n.kind in ("class", "interface")}
            if impl_class_ids:
                impl_children, impl_contains = await _fetch_children_of_classes(db, impl_class_ids)
                child_nodes.extend(impl_children)
                edges.extend(impl_contains)

    parent_fp = await _get_file_path(db, symbol.file_id)
    return ExpandedGraphData(
        parent_node=_symbol_to_node(symbol, parent_fp),
        child_nodes=child_nodes,
        edges=edges,
    )


@router.get("/expand-class-calls/{project_id}/{symbol_id}", response_model=ExpandedGraphData)
async def expand_class_calls(
    project_id: uuid.UUID,
    symbol_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Expand all methods of a class one layer — show all Service methods called by this class's methods."""
    project = await db.get(Project, project_id)
    if not project:
        raise ProjectNotFoundError()

    symbol = await db.get(Symbol, symbol_id)
    if not symbol:
        raise SymbolNotFoundError()

    method_stmt = select(Symbol).where(Symbol.parent_id == symbol_id)
    method_result = await db.execute(method_stmt)
    methods = method_result.scalars().all()

    method_ids = [m.id for m in methods]

    if symbol.kind == SymbolKind.METHOD or symbol.kind == SymbolKind.FUNCTION:
        method_ids = [symbol_id]

    child_nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    seen_callee_ids: set[uuid.UUID] = set()

    if method_ids:
        caller_stmt = select(CallGraph).where(
            CallGraph.project_id == project_id,
            CallGraph.caller_id.in_(method_ids),
        )
        caller_result = await db.execute(caller_stmt)
        call_edges = list(caller_result.scalars().all())

        callee_ids = list({cg.callee_id for cg in call_edges if cg.callee_id not in seen_callee_ids})
        seen_callee_ids.update(callee_ids)

        if callee_ids:
            callee_nodes = await _fetch_symbols_with_paths(db, set(callee_ids))
            child_nodes.extend(callee_nodes)

            # For callee classes, also fetch their children
            callee_class_ids = {n.id for n in callee_nodes if n.kind in ("class", "interface", "enum")}
            if callee_class_ids:
                class_children, contains_edges = await _fetch_children_of_classes(db, callee_class_ids)
                child_nodes.extend(class_children)
                edges.extend(contains_edges)

                # Also fetch call edges from class children methods
                child_method_ids = {n.id for n in class_children if n.kind in ("method", "function")}
                if child_method_ids:
                    inner_caller_stmt = select(CallGraph).where(
                        CallGraph.project_id == project_id,
                        CallGraph.caller_id.in_(child_method_ids),
                    )
                    inner_result = await db.execute(inner_caller_stmt)
                    call_edges.extend(inner_result.scalars().all())

        edges.extend([
            GraphEdge(
                id=cg.id,
                source=cg.caller_id,
                target=cg.callee_id,
                edge_type="call",
                line_number=cg.line_number,
            )
            for cg in call_edges
        ])

        # Fetch any callee nodes referenced by edges but not yet in child_nodes
        all_callee_ids: set[uuid.UUID] = {cg.callee_id for cg in call_edges}
        existing_child_ids = {n.id for n in child_nodes}
        missing_callee_ids = all_callee_ids - existing_child_ids
        if missing_callee_ids:
            missing_nodes = await _fetch_symbols_with_paths(db, missing_callee_ids)
            child_nodes.extend(missing_nodes)

        # Field access edges
        fa_edges = await _fetch_field_access_edges(db, project_id, set(method_ids))
        edges.extend(fa_edges)

        # Implements edges: if any callee is an interface, follow to its implementation
        all_callee_ids_for_impl = {n.id for n in child_nodes if n.kind == "interface"}
        if all_callee_ids_for_impl:
            impl_edges, impl_ids = await _fetch_implements_edges(db, project_id, all_callee_ids_for_impl)
            edges.extend(impl_edges)
            if impl_ids:
                impl_nodes = await _fetch_symbols_with_paths(db, impl_ids)
                child_nodes.extend(impl_nodes)
                impl_class_ids = {n.id for n in impl_nodes if n.kind in ("class", "interface")}
                if impl_class_ids:
                    impl_children, impl_contains = await _fetch_children_of_classes(db, impl_class_ids)
                    child_nodes.extend(impl_children)
                    edges.extend(impl_contains)

    parent_fp = await _get_file_path(db, symbol.file_id)
    return ExpandedGraphData(
        parent_node=_symbol_to_node(symbol, parent_fp),
        child_nodes=child_nodes,
        edges=edges,
    )


@router.get("/full-chain/{project_id}/{symbol_id}", response_model=GraphData)
async def get_full_chain(
    project_id: uuid.UUID,
    symbol_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Recursively trace the full call chain from a class — double-click to expand all."""
    project = await db.get(Project, project_id)
    if not project:
        raise ProjectNotFoundError()

    symbol = await db.get(Symbol, symbol_id)
    if not symbol:
        raise SymbolNotFoundError()

    # Start with the class and its methods
    start_ids: set[uuid.UUID] = {symbol_id}
    if symbol.kind in (SymbolKind.CLASS, SymbolKind.INTERFACE, SymbolKind.ENUM):
        method_stmt = select(Symbol).where(Symbol.parent_id == symbol_id)
        method_result = await db.execute(method_stmt)
        for m in method_result.scalars().all():
            start_ids.add(m.id)
    elif symbol.kind in (SymbolKind.METHOD, SymbolKind.FUNCTION):
        pass
    else:
        start_ids = {symbol_id}

    # BFS to trace call chain
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

        # Find calls FROM these symbols
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

        # Find field accesses FROM these symbols
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
                # Also enqueue the field's parent class so we can traverse its methods
                field_sym = await db.get(Symbol, fa.accessed_field_id)
                if field_sym and field_sym.parent_id and field_sym.parent_id not in visited:
                    all_symbol_ids.add(field_sym.parent_id)
                    queue.append(field_sym.parent_id)

        # Find implements relations FROM these symbols (interface → impl)
        impl_edges, impl_ids = await _fetch_implements_edges(db, project_id, set(batch))
        all_edges.extend(impl_edges)
        for impl_id in impl_ids:
            if impl_id not in visited:
                all_symbol_ids.add(impl_id)
                queue.append(impl_id)
                # Also enqueue the impl class's child methods so their calls get traversed
                impl_sym = await db.get(Symbol, impl_id)
                if impl_sym and impl_sym.kind in (SymbolKind.CLASS, SymbolKind.INTERFACE):
                    impl_method_stmt = select(Symbol).where(Symbol.parent_id == impl_id)
                    impl_method_result = await db.execute(impl_method_stmt)
                    for m in impl_method_result.scalars().all():
                        if m.id not in visited:
                            all_symbol_ids.add(m.id)
                            queue.append(m.id)

    # For any discovered class symbols, also include their child methods/fields
    class_ids_in_chain: set[uuid.UUID] = set()
    sym_stmt = (
        select(Symbol, File.file_path)
        .join(File, Symbol.file_id == File.id)
        .where(Symbol.id.in_(all_symbol_ids))
    )
    sym_result = await db.execute(sym_stmt)
    sym_rows = sym_result.all()

    for s, _ in sym_rows:
        if s.kind in (SymbolKind.CLASS, SymbolKind.INTERFACE, SymbolKind.ENUM):
            class_ids_in_chain.add(s.id)

    # Fetch children of discovered classes
    child_nodes: list[GraphNode] = []
    if class_ids_in_chain:
        class_children, contains_edges = await _fetch_children_of_classes(db, class_ids_in_chain)
        child_nodes.extend(class_children)
        all_edges.extend(contains_edges)

        # Also include field accesses from newly discovered child methods
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
                    # Fetch the field symbol too
                    field_sym = await db.get(Symbol, fa.accessed_field_id)
                    if field_sym:
                        fp = await _get_file_path(db, field_sym.file_id)
                        child_nodes.append(_symbol_to_node(field_sym, fp))

    nodes = [_symbol_to_node(s, fp) for s, fp in sym_rows]
    nodes.extend(child_nodes)

    # Also add parent-child containment edges for the initial set
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

    return GraphData(nodes=nodes, edges=all_edges)
