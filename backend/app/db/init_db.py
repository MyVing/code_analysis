from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.session import engine


async def init_db(engine: AsyncEngine | None = None) -> None:
    _engine = engine or __import__("app.db.session", fromlist=["engine"]).engine
    from app.models.base import Base

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add output_schema column if missing (SQLite migration)
        await conn.run_sync(_migrate_add_output_schema)

    await _seed_prompt_templates()


def _migrate_add_output_schema(connection):
    from sqlalchemy import inspect
    inspector = inspect(connection)
    columns = [col["name"] for col in inspector.get_columns("prompt_templates")]
    if "output_schema" not in columns:
        connection.execute(
            __import__("sqlalchemy").text(
                "ALTER TABLE prompt_templates ADD COLUMN output_schema TEXT"
            )
        )


async def _seed_prompt_templates() -> None:
    import json
    from sqlalchemy import select, func
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.db.session import async_session
    from app.models.prompt_template import PromptTemplate

    async with async_session() as db:
        count = await db.scalar(select(func.count()).select_from(PromptTemplate))
        if not count or count == 0:
            # First run: seed all default templates
            defaults = _get_default_templates()
            for d in defaults:
                params = d.pop("parameters")
                output_schema = d.pop("output_schema", None)
                template = PromptTemplate(
                    **d,
                    parameters=json.dumps(params),
                    output_schema=json.dumps(output_schema) if output_schema else None,
                    is_active=True,
                )
                db.add(template)
            await db.commit()
        else:
            # Subsequent runs: check if structured template exists, add if not
            existing = await db.scalar(
                select(func.count()).select_from(PromptTemplate).where(
                    PromptTemplate.output_schema != None
                )
            )
            if not existing or existing == 0:
                structured = _get_structured_templates()
                for d in structured:
                    params = d.pop("parameters")
                    output_schema = d.pop("output_schema")
                    template = PromptTemplate(
                        **d,
                        parameters=json.dumps(params),
                        output_schema=json.dumps(output_schema),
                        is_active=True,
                    )
                    db.add(template)
                await db.commit()


def _get_default_templates() -> list[dict]:
    return [
        {
            "name": "链路分析",
            "icon": "🔗",
            "description": "追踪方法的完整调用链路",
            "category": "call_chain",
            "prompt_template": "分析 {class_name} 的完整调用链路",
            "parameters": [{"key": "class_name", "label": "类名", "type": "text", "required": True, "placeholder": "如 UserController"}],
            "sort_order": 1,
        },
        {
            "name": "调用者查找",
            "icon": "🔍",
            "description": "查找谁调用了指定方法",
            "category": "call_chain",
            "prompt_template": "谁调用了 {method_name}？",
            "parameters": [{"key": "method_name", "label": "方法名", "type": "text", "required": True, "placeholder": "如 getUser"}],
            "sort_order": 2,
        },
        {
            "name": "被调用者查找",
            "icon": "📞",
            "description": "查找指定类调用了哪些方法",
            "category": "call_chain",
            "prompt_template": "{class_name} 调用了哪些方法？",
            "parameters": [{"key": "class_name", "label": "类名", "type": "text", "required": True, "placeholder": "如 UserController"}],
            "sort_order": 3,
        },
        {
            "name": "类结构分析",
            "icon": "🏗️",
            "description": "列出类的所有方法和签名",
            "category": "structure",
            "prompt_template": "分析 {class_name} 的结构，列出所有方法",
            "parameters": [{"key": "class_name", "label": "类名", "type": "text", "required": True, "placeholder": "如 UserController"}],
            "sort_order": 4,
        },
        {
            "name": "代码搜索",
            "icon": "🔎",
            "description": "搜索代码中包含关键词的位置",
            "category": "search",
            "prompt_template": "搜索代码中包含 {keyword} 的位置",
            "parameters": [{"key": "keyword", "label": "关键词", "type": "text", "required": True, "placeholder": "如 @GetMapping"}],
            "sort_order": 5,
        },
        {
            "name": "代码阅读",
            "icon": "📄",
            "description": "读取指定文件的源码",
            "category": "search",
            "prompt_template": "读取 {file_path} 的源码",
            "parameters": [{"key": "file_path", "label": "文件路径", "type": "text", "required": True, "placeholder": "如 src/main/java/com/example/UserController.java"}],
            "sort_order": 6,
        },
    ]


def _get_structured_templates() -> list[dict]:
    return [
        {
            "name": "链路分析（结构化）",
            "icon": "📊",
            "description": "按结构化模板分析方法的完整调用链路，返回 JSON 格式结果",
            "category": "call_chain",
            "prompt_template": "分析 {entry_path} 的完整调用链路，分析深度为 {depth}。请严格按照指定的 JSON Schema 返回结构化结果。",
            "parameters": [
                {"key": "entry_path", "label": "请求路径", "type": "text", "required": True, "placeholder": "如 /api/auth/login"},
                {"key": "depth", "label": "分析深度", "type": "select", "required": True, "options": ["直接调用", "完整链路"]},
            ],
            "output_schema": {
                "type": "object",
                "properties": {
                    "发布单元": {
                        "type": "object",
                        "properties": {
                            "分支": {"type": "string", "description": "代码分支名"},
                            "仓库": {
                                "type": "object",
                                "properties": {
                                    "label": {"type": "string", "description": "仓库名称"},
                                    "包": {
                                        "type": "object",
                                        "properties": {
                                            "类": {
                                                "type": "object",
                                                "properties": {
                                                    "id": {"type": "string", "description": "类的唯一标识"},
                                                    "类名": {"type": "string"},
                                                    "Java方法": {
                                                        "type": "array",
                                                        "items": {
                                                            "type": "object",
                                                            "properties": {
                                                                "id": {"type": "string", "description": "方法的唯一标识"},
                                                                "方法名": {"type": "string"},
                                                                "上游": {
                                                                    "type": "array",
                                                                    "items": {"type": "string"},
                                                                    "description": "调用此方法的上游方法列表",
                                                                },
                                                                "下游": {
                                                                    "type": "array",
                                                                    "items": {"type": "string"},
                                                                    "description": "此方法调用的下游方法列表",
                                                                },
                                                                "入参": {
                                                                    "type": "array",
                                                                    "items": {
                                                                        "type": "object",
                                                                        "properties": {
                                                                            "名称": {"type": "string"},
                                                                            "类型": {"type": "string"},
                                                                            "可空": {"type": "boolean"},
                                                                            "描述": {"type": "string"},
                                                                            "默认值": {"type": "string"},
                                                                        },
                                                                    },
                                                                    "description": "方法入参列表",
                                                                },
                                                                "出参": {
                                                                    "type": "object",
                                                                    "properties": {
                                                                        "返回类型": {"type": "string"},
                                                                        "可空": {"type": "boolean"},
                                                                    },
                                                                    "description": "方法出参",
                                                                },
                                                                "方法描述": {"type": "string"},
                                                                "方法内容分析": {
                                                                    "type": "object",
                                                                    "properties": {
                                                                        "业务价值": {"type": "string"},
                                                                        "入口参数": {"type": "string"},
                                                                        "基础校验": {"type": "string"},
                                                                        "业务规则": {
                                                                            "type": "array",
                                                                            "items": {"type": "string"},
                                                                        },
                                                                        "数据处理": {"type": "string"},
                                                                        "实现逻辑": {"type": "string"},
                                                                        "数据库操作": {
                                                                            "type": "array",
                                                                            "items": {
                                                                                "type": "object",
                                                                                "properties": {
                                                                                    "sql": {"type": "string"},
                                                                                    "描述": {"type": "string"},
                                                                                },
                                                                            },
                                                                        },
                                                                        "异常处理": {
                                                                            "type": "array",
                                                                            "items": {"type": "string"},
                                                                        },
                                                                        "中间件": {
                                                                            "type": "array",
                                                                            "items": {
                                                                                "type": "object",
                                                                                "properties": {
                                                                                    "类型": {"type": "string"},
                                                                                    "报文": {"type": "string"},
                                                                                },
                                                                            },
                                                                        },
                                                                        "日志信息": {
                                                                            "type": "array",
                                                                            "items": {"type": "string"},
                                                                        },
                                                                    },
                                                                    "description": "方法内容的深度分析",
                                                                },
                                                            },
                                                        },
                                                        "description": "类中的方法列表",
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
            "sort_order": 7,
        },
    ]
