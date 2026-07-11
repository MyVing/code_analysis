import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File
from app.models.graph import CallGraph
from app.models.symbol import Symbol, SymbolKind
from app.tools.base import tool

SYMBOL_QUERY_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "符号名称（支持模糊匹配），如 'AuthService' 或 'login'",
        },
        "kind": {
            "type": "string",
            "enum": ["class", "method", "function", "variable", "interface", "annotation", "enum"],
            "description": "符号类型过滤",
        },
    },
    "required": ["name"],
}

CALLERS_SCHEMA = {
    "type": "object",
    "properties": {
        "symbol_name": {
            "type": "string",
            "description": "要查找调用者的符号名称，如 'AuthService' 或 'findById'",
        },
    },
    "required": ["symbol_name"],
}

CALLEES_SCHEMA = {
    "type": "object",
    "properties": {
        "symbol_name": {
            "type": "string",
            "description": "要查找被调用者的符号名称，如 'AuthController'",
        },
    },
    "required": ["symbol_name"],
}

CLASS_METHODS_SCHEMA = {
    "type": "object",
    "properties": {
        "class_name": {
            "type": "string",
            "description": "类名称，如 'AuthService'",
        },
    },
    "required": ["class_name"],
}


@tool("find_symbol", "按名称和类型查询项目中的符号（类、方法、接口等），返回匹配的符号列表及其位置信息", SYMBOL_QUERY_SCHEMA)
async def find_symbol(db: AsyncSession, project_id: uuid.UUID, **kwargs) -> dict:
    name = kwargs.get("name", "")
    kind = kwargs.get("kind")

    stmt = (
        select(Symbol, File.file_path)
        .join(File, Symbol.file_id == File.id)
        .where(File.project_id == project_id)
    )
    if name:
        stmt = stmt.where(Symbol.name.ilike(f"%{name}%"))
    if kind:
        stmt = stmt.where(Symbol.kind == kind)
    stmt = stmt.order_by(Symbol.start_line).limit(50)

    result = await db.execute(stmt)
    rows = result.all()

    symbols = []
    for sym, file_path in rows:
        symbols.append({
            "id": str(sym.id),
            "name": sym.name,
            "kind": sym.kind.value,
            "signature": sym.signature,
            "file_path": file_path,
            "start_line": sym.start_line,
            "end_line": sym.end_line,
            "modifiers": sym.modifiers,
        })
    return {"count": len(symbols), "symbols": symbols}


@tool("find_callers", "查找项目中调用了指定符号的所有调用者，返回调用者列表及调用位置", CALLERS_SCHEMA)
async def find_callers(db: AsyncSession, project_id: uuid.UUID, **kwargs) -> dict:
    symbol_name = kwargs.get("symbol_name", "")

    # Find matching symbols
    sym_stmt = (
        select(Symbol.id).join(File, Symbol.file_id == File.id)
        .where(File.project_id == project_id, Symbol.name.ilike(f"%{symbol_name}%"))
    )
    sym_result = await db.execute(sym_stmt)
    symbol_ids = [row[0] for row in sym_result.all()]
    if not symbol_ids:
        return {"count": 0, "callers": [], "message": f"No symbol found matching '{symbol_name}'"}

    # Find callers from call_graph where callee_id matches
    cg_stmt = (
        select(CallGraph.caller_id, CallGraph.line_number, CallGraph.file_id)
        .where(CallGraph.project_id == project_id, CallGraph.callee_id.in_(symbol_ids))
    )
    cg_result = await db.execute(cg_stmt)
    caller_rows = cg_result.all()

    # Resolve caller info
    caller_ids = list({r[0] for r in caller_rows})
    if not caller_ids:
        return {"count": 0, "callers": []}

    caller_stmt = (
        select(Symbol, File.file_path)
        .join(File, Symbol.file_id == File.id)
        .where(Symbol.id.in_(caller_ids))
    )
    caller_result = await db.execute(caller_stmt)
    caller_map = {}
    for sym, fp in caller_result.all():
        caller_map[sym.id] = {"name": sym.name, "kind": sym.kind.value, "file_path": fp, "start_line": sym.start_line}

    callers = []
    for caller_id, line_number, file_id in caller_rows:
        info = caller_map.get(caller_id, {})
        callers.append({**info, "call_line": line_number})

    return {"count": len(callers), "callers": callers}


@tool("find_callees", "查找项目中指定符号调用了哪些其他符号，返回被调用者列表及调用位置", CALLEES_SCHEMA)
async def find_callees(db: AsyncSession, project_id: uuid.UUID, **kwargs) -> dict:
    symbol_name = kwargs.get("symbol_name", "")

    # Find matching symbols
    sym_stmt = (
        select(Symbol.id).join(File, Symbol.file_id == File.id)
        .where(File.project_id == project_id, Symbol.name.ilike(f"%{symbol_name}%"))
    )
    sym_result = await db.execute(sym_stmt)
    symbol_ids = [row[0] for row in sym_result.all()]
    if not symbol_ids:
        return {"count": 0, "callees": [], "message": f"No symbol found matching '{symbol_name}'"}

    # Find callees from call_graph where caller_id matches
    cg_stmt = (
        select(CallGraph.callee_id, CallGraph.line_number)
        .where(CallGraph.project_id == project_id, CallGraph.caller_id.in_(symbol_ids))
    )
    cg_result = await db.execute(cg_stmt)
    callee_rows = cg_result.all()

    # Resolve callee info
    callee_ids = list({r[0] for r in callee_rows})
    if not callee_ids:
        return {"count": 0, "callees": []}

    callee_stmt = (
        select(Symbol, File.file_path)
        .join(File, Symbol.file_id == File.id)
        .where(Symbol.id.in_(callee_ids))
    )
    callee_result = await db.execute(callee_stmt)
    callee_map = {}
    for sym, fp in callee_result.all():
        callee_map[sym.id] = {"name": sym.name, "kind": sym.kind.value, "file_path": fp, "start_line": sym.start_line}

    callees = []
    for callee_id, line_number in callee_rows:
        info = callee_map.get(callee_id, {})
        callees.append({**info, "call_line": line_number})

    return {"count": len(callees), "callees": callees}


@tool("get_class_methods", "获取指定类的所有方法，返回方法列表（含签名、修饰符、行号）", CLASS_METHODS_SCHEMA)
async def get_class_methods(db: AsyncSession, project_id: uuid.UUID, **kwargs) -> dict:
    class_name = kwargs.get("class_name", "")

    # Find the class symbol
    cls_stmt = (
        select(Symbol, File.file_path)
        .join(File, Symbol.file_id == File.id)
        .where(
            File.project_id == project_id,
            Symbol.name.ilike(f"%{class_name}%"),
            Symbol.kind == SymbolKind.CLASS,
        )
    )
    cls_result = await db.execute(cls_stmt)
    cls_rows = cls_result.all()
    if not cls_rows:
        return {"count": 0, "methods": [], "message": f"No class found matching '{class_name}'"}

    results = []
    for cls_sym, file_path in cls_rows:
        # Find methods belonging to this class
        method_stmt = (
            select(Symbol)
            .where(Symbol.parent_id == cls_sym.id, Symbol.kind == SymbolKind.METHOD)
            .order_by(Symbol.start_line)
        )
        method_result = await db.execute(method_stmt)
        methods = method_result.scalars().all()

        method_list = []
        for m in methods:
            method_list.append({
                "name": m.name,
                "signature": m.signature,
                "modifiers": m.modifiers,
                "start_line": m.start_line,
                "end_line": m.end_line,
            })
        results.append({
            "class_name": cls_sym.name,
            "file_path": file_path,
            "methods": method_list,
        })

    return {"count": len(results), "classes": results}
