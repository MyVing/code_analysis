from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.session import engine


async def init_db(engine: AsyncEngine | None = None) -> None:
    _engine = engine or __import__("app.db.session", fromlist=["engine"]).engine
    from app.models.base import Base

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
