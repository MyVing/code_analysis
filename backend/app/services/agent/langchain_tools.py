from __future__ import annotations

import json
import uuid

from langchain_core.tools import tool as lc_tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.graph_tools import find_symbol as _find_symbol, find_callers as _find_callers, find_callees as _find_callees, get_class_methods as _get_class_methods
from app.tools.code_tools import read_file as _read_file, search_content as _search_content


def _json_result(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def create_langchain_tools(db: AsyncSession, project_id: uuid.UUID) -> list:
    """为每次请求创建注入了 db + project_id 的 LangChain 工具列表。"""

    @lc_tool("find_symbol")
    async def find_symbol(name: str, kind: str | None = None) -> str:
        """按名称和类型查询项目中的符号（类、方法、接口等），返回匹配的符号列表及其位置信息"""
        return _json_result(await _find_symbol(db, project_id, name=name, kind=kind))

    @lc_tool("find_callers")
    async def find_callers(symbol_name: str) -> str:
        """查找项目中调用了指定符号的所有调用者，返回调用者列表及调用位置"""
        return _json_result(await _find_callers(db, project_id, symbol_name=symbol_name))

    @lc_tool("find_callees")
    async def find_callees(symbol_name: str) -> str:
        """查找项目中指定符号调用了哪些其他符号，返回被调用者列表及调用位置"""
        return _json_result(await _find_callees(db, project_id, symbol_name=symbol_name))

    @lc_tool("get_class_methods")
    async def get_class_methods(class_name: str) -> str:
        """获取指定类的所有方法，返回方法列表（含签名、修饰符、行号）"""
        return _json_result(await _get_class_methods(db, project_id, class_name=class_name))

    @lc_tool("read_file")
    async def read_file(file_path: str, start_line: int | None = None, end_line: int | None = None) -> str:
        """读取项目中指定源代码文件的内容，可指定行号范围"""
        kwargs: dict = {"file_path": file_path}
        if start_line is not None:
            kwargs["start_line"] = start_line
        if end_line is not None:
            kwargs["end_line"] = end_line
        return _json_result(await _read_file(db, project_id, **kwargs))

    @lc_tool("search_content")
    async def search_content(query: str, max_results: int = 20) -> str:
        """在项目源代码中搜索包含指定关键词的文件和行，返回匹配结果"""
        return _json_result(await _search_content(db, project_id, query=query, max_results=max_results))

    return [find_symbol, find_callers, find_callees, get_class_methods, read_file, search_content]
