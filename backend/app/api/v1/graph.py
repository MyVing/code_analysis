import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.file import File
from app.models.graph import CallGraph, Import
from app.models.project import Project
from app.models.symbol import Symbol, SymbolKind
from app.schemas.graph import CallGraphRead, ExpandedGraphData, GraphData, GraphEdge, GraphNode, ImportRead
from app.services.chain_traversal import traverse_full_chain
from app.services.graph_service import (
    fetch_all_call_edges,
    fetch_all_implements_edges,
    fetch_call_edges,
    fetch_callee_edges,
    fetch_children_of_classes,
    fetch_class_method_ids,
    fetch_field_access_edges,
    fetch_file_symbols_with_contains,
    fetch_implements_edges,
    fetch_project_symbols,
    fetch_symbol_children,
    fetch_symbols_with_paths,
    get_file_path,
    symbol_to_node,
    validate_file,
    validate_project,
    validate_symbol,
)

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/call-graph/{project_id}", response_model=list[CallGraphRead])
async def get_call_graph(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await validate_project(db, project_id)
    stmt = select(CallGraph).where(CallGraph.project_id == project_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/imports/{project_id}", response_model=list[ImportRead])
async def get_imports(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await validate_project(db, project_id)
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
    await validate_project(db, project_id)
    nodes = await fetch_project_symbols(db, project_id)
    edges = await fetch_all_call_edges(db, project_id)
    edges.extend(await fetch_all_implements_edges(db, project_id))
    return GraphData(nodes=nodes, edges=edges)


@router.get("/call-graph/{project_id}/expand/{symbol_id}", response_model=ExpandedGraphData)
async def expand_symbol_graph(
    project_id: uuid.UUID,
    symbol_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await validate_project(db, project_id)
    symbol = await validate_symbol(db, symbol_id)

    child_nodes, child_ids = await fetch_symbol_children(db, symbol_id)

    edges: list[GraphEdge] = []
    if child_ids:
        child_id_set = set(child_ids)
        edges.extend(await fetch_call_edges(db, project_id, child_id_set))

        callee_edges = await fetch_callee_edges(db, project_id, child_id_set)
        existing_edge_ids = {e.id for e in edges}
        for e in callee_edges:
            if e.id not in existing_edge_ids:
                edges.append(e)

        edges.extend(await fetch_field_access_edges(db, project_id, child_id_set))

        interface_ids = {n.id for n in child_nodes if n.kind == SymbolKind.INTERFACE.value}
        if interface_ids:
            impl_edges, impl_ids = await fetch_implements_edges(db, project_id, interface_ids)
            edges.extend(impl_edges)
            if impl_ids:
                impl_nodes = await fetch_symbols_with_paths(db, impl_ids)
                child_nodes.extend(impl_nodes)

    parent_fp = await get_file_path(db, symbol.file_id)
    return ExpandedGraphData(
        parent_node=symbol_to_node(symbol, parent_fp),
        child_nodes=child_nodes,
        edges=edges,
    )


@router.get("/file-symbols/{project_id}/{file_id}", response_model=GraphData)
async def get_file_symbols(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await validate_project(db, project_id)
    await validate_file(db, project_id, file_id)
    nodes, edges = await fetch_file_symbols_with_contains(db, project_id, file_id)
    return GraphData(nodes=nodes, edges=edges)


@router.get("/expand-call/{project_id}/{symbol_id}", response_model=ExpandedGraphData)
async def expand_call(
    project_id: uuid.UUID,
    symbol_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await validate_project(db, project_id)
    symbol = await validate_symbol(db, symbol_id)

    call_edges_raw = await fetch_call_edges(db, project_id, {symbol_id})
    callee_ids = list({e.target for e in call_edges_raw})

    child_nodes: list[GraphNode] = []
    contains_edges_cache: list[GraphEdge] = []

    if callee_ids:
        callee_nodes = await fetch_symbols_with_paths(db, set(callee_ids))
        child_nodes.extend(callee_nodes)

        child_class_ids = {n.id for n in callee_nodes if n.kind in ("class", "interface", "enum")}
        if child_class_ids:
            class_children, contains_edges = await fetch_children_of_classes(db, child_class_ids)
            child_nodes.extend(class_children)
            contains_edges_cache = contains_edges
            child_method_ids = {n.id for n in class_children if n.kind in ("method", "function")}
            if child_method_ids:
                inner_edges = await fetch_call_edges(db, project_id, child_method_ids)
                call_edges_raw.extend(inner_edges)

    all_callee_ids = {e.target for e in call_edges_raw}
    existing_child_ids = {n.id for n in child_nodes}
    missing_callee_ids = all_callee_ids - existing_child_ids
    if missing_callee_ids:
        missing_nodes = await fetch_symbols_with_paths(db, missing_callee_ids)
        child_nodes.extend(missing_nodes)

    edges = list(call_edges_raw)
    for ce in contains_edges_cache:
        if ce.id not in {e.id for e in edges}:
            edges.append(ce)

    accessor_ids = {symbol_id}
    accessor_ids.update({n.id for n in child_nodes if n.kind in ("method", "function")})
    edges.extend(await fetch_field_access_edges(db, project_id, accessor_ids))

    all_symbol_ids_for_impl = {n.id for n in child_nodes if n.kind == "interface"}
    if all_symbol_ids_for_impl:
        impl_edges, impl_ids = await fetch_implements_edges(db, project_id, all_symbol_ids_for_impl)
        edges.extend(impl_edges)
        if impl_ids:
            impl_nodes = await fetch_symbols_with_paths(db, impl_ids)
            child_nodes.extend(impl_nodes)
            impl_class_ids = {n.id for n in impl_nodes if n.kind in ("class", "interface")}
            if impl_class_ids:
                impl_children, impl_contains = await fetch_children_of_classes(db, impl_class_ids)
                child_nodes.extend(impl_children)
                edges.extend(impl_contains)

    parent_fp = await get_file_path(db, symbol.file_id)
    return ExpandedGraphData(
        parent_node=symbol_to_node(symbol, parent_fp),
        child_nodes=child_nodes,
        edges=edges,
    )


@router.get("/expand-class-calls/{project_id}/{symbol_id}", response_model=ExpandedGraphData)
async def expand_class_calls(
    project_id: uuid.UUID,
    symbol_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await validate_project(db, project_id)
    symbol = await validate_symbol(db, symbol_id)

    if symbol.kind in (SymbolKind.METHOD, SymbolKind.FUNCTION):
        method_ids = [symbol_id]
    else:
        method_ids = await fetch_class_method_ids(db, symbol_id)

    child_nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    seen_callee_ids: set[uuid.UUID] = set()

    if method_ids:
        method_id_set = set(method_ids)
        call_edges = await fetch_call_edges(db, project_id, method_id_set)

        callee_ids = list({e.target for e in call_edges if e.target not in seen_callee_ids})
        seen_callee_ids.update(callee_ids)

        if callee_ids:
            callee_nodes = await fetch_symbols_with_paths(db, set(callee_ids))
            child_nodes.extend(callee_nodes)

            callee_class_ids = {n.id for n in callee_nodes if n.kind in ("class", "interface", "enum")}
            if callee_class_ids:
                class_children, contains_edges = await fetch_children_of_classes(db, callee_class_ids)
                child_nodes.extend(class_children)
                edges.extend(contains_edges)

                child_method_ids = {n.id for n in class_children if n.kind in ("method", "function")}
                if child_method_ids:
                    inner_edges = await fetch_call_edges(db, project_id, child_method_ids)
                    call_edges.extend(inner_edges)

        edges.extend(call_edges)

        all_callee_ids = {e.target for e in call_edges}
        existing_child_ids = {n.id for n in child_nodes}
        missing_callee_ids = all_callee_ids - existing_child_ids
        if missing_callee_ids:
            missing_nodes = await fetch_symbols_with_paths(db, missing_callee_ids)
            child_nodes.extend(missing_nodes)

        edges.extend(await fetch_field_access_edges(db, project_id, method_id_set))

        all_callee_ids_for_impl = {n.id for n in child_nodes if n.kind == "interface"}
        if all_callee_ids_for_impl:
            impl_edges, impl_ids = await fetch_implements_edges(db, project_id, all_callee_ids_for_impl)
            edges.extend(impl_edges)
            if impl_ids:
                impl_nodes = await fetch_symbols_with_paths(db, impl_ids)
                child_nodes.extend(impl_nodes)
                impl_class_ids = {n.id for n in impl_nodes if n.kind in ("class", "interface")}
                if impl_class_ids:
                    impl_children, impl_contains = await fetch_children_of_classes(db, impl_class_ids)
                    child_nodes.extend(impl_children)
                    edges.extend(impl_contains)

    parent_fp = await get_file_path(db, symbol.file_id)
    return ExpandedGraphData(
        parent_node=symbol_to_node(symbol, parent_fp),
        child_nodes=child_nodes,
        edges=edges,
    )


@router.get("/full-chain/{project_id}/{symbol_id}", response_model=GraphData)
async def get_full_chain(
    project_id: uuid.UUID,
    symbol_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await validate_project(db, project_id)
    symbol = await validate_symbol(db, symbol_id)
    nodes, edges = await traverse_full_chain(db, project_id, symbol)
    return GraphData(nodes=nodes, edges=edges)
