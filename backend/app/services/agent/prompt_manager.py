import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File
from app.models.project import Project
from app.models.symbol import Symbol

SYSTEM_PROMPT_TEMPLATE = """你是一个高级代码架构师，专门帮助用户理解和分析代码项目。

当前分析的项目信息：
- 项目名称：{project_name}
- 主语言：{language}
- 框架：{framework}
- 分支：{branch}
- 文件数量：{file_count}
- 符号数量：{symbol_count}

你可以使用提供的工具来查询符号表、调用链和读取源码。

重要规则：
1. 不要猜测代码内容，必须通过工具获取准确的代码信息
2. 回答时要引用具体的文件路径和行号
3. 分析调用链时，先找到目标符号，再查找其调用者或被调用者
4. 如果搜索结果不明确，尝试用更精确的关键词再次搜索
5. 用中文回答用户的问题"""


class PromptManager:
    async def build_system_prompt(self, db: AsyncSession, project_id: uuid.UUID) -> str:
        project = await db.get(Project, project_id)
        if not project:
            return "你是一个代码分析助手。"

        file_count = await db.scalar(
            select(func.count()).where(File.project_id == project_id)
        )
        symbol_count = await db.scalar(
            select(func.count())
            .where(Symbol.file_id.in_(select(File.id).where(File.project_id == project_id)))
        )

        return SYSTEM_PROMPT_TEMPLATE.format(
            project_name=project.name,
            language=project.language,
            framework=project.framework or "未知",
            branch=project.branch,
            file_count=file_count or 0,
            symbol_count=symbol_count or 0,
        )
