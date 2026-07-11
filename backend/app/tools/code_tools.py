import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File
from app.models.project import Project
from app.services.analyzer.git_manager import GitManager
from app.tools.base import tool

READ_FILE_SCHEMA = {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "文件相对路径，如 'src/main/java/com/ving/controller/AuthController.java'",
        },
        "start_line": {
            "type": "integer",
            "description": "起始行号（从1开始），可选，不传则返回全文",
        },
        "end_line": {
            "type": "integer",
            "description": "结束行号，可选，不传则返回到文件末尾",
        },
    },
    "required": ["file_path"],
}

SEARCH_CONTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "搜索关键词",
        },
        "max_results": {
            "type": "integer",
            "description": "最大返回结果数，默认20",
        },
    },
    "required": ["query"],
}


@tool("read_file", "读取项目中指定源代码文件的内容，可指定行号范围", READ_FILE_SCHEMA)
async def read_file(db: AsyncSession, project_id: uuid.UUID, **kwargs) -> dict:
    file_path = kwargs.get("file_path", "")
    start_line = kwargs.get("start_line")
    end_line = kwargs.get("end_line")

    # Get project name
    project = await db.get(Project, project_id)
    if not project:
        return {"error": "Project not found"}

    git_mgr = GitManager(db)
    try:
        content = await git_mgr.read_file(project.name, file_path)
    except Exception as e:
        return {"error": str(e)}

    lines = content.splitlines()
    total_lines = len(lines)

    s = max(1, start_line) if start_line else 1
    e = min(total_lines, end_line) if end_line else total_lines

    selected = lines[s - 1 : e]
    # Add line numbers
    numbered = [f"{i}: {line}" for i, line in zip(range(s, e + 1), selected)]

    return {
        "file_path": file_path,
        "total_lines": total_lines,
        "start_line": s,
        "end_line": e,
        "content": "\n".join(numbered),
    }


@tool("search_content", "在项目源代码中搜索包含指定关键词的文件和行，返回匹配结果", SEARCH_CONTENT_SCHEMA)
async def search_content(db: AsyncSession, project_id: uuid.UUID, **kwargs) -> dict:
    query = kwargs.get("query", "")
    max_results = kwargs.get("max_results", 20)

    if not query:
        return {"count": 0, "matches": []}

    project = await db.get(Project, project_id)
    if not project:
        return {"error": "Project not found"}

    # Get all file paths
    stmt = select(File.file_path).where(File.project_id == project_id)
    result = await db.execute(stmt)
    file_paths = [row[0] for row in result.all()]

    git_mgr = GitManager(db)
    matches = []

    for fp in file_paths:
        if len(matches) >= max_results:
            break
        try:
            content = await git_mgr.read_file(project.name, fp)
            for i, line in enumerate(content.splitlines(), 1):
                if query in line:
                    matches.append({
                        "file_path": fp,
                        "line_number": i,
                        "line": line.strip()[:200],
                    })
                    if len(matches) >= max_results:
                        break
        except Exception:
            continue

    return {"count": len(matches), "matches": matches}
