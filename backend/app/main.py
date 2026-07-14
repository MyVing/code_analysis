import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import v1_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.db.init_db import init_db
from app.services.analysis_service import analysis_service

# Import tools to register them
import app.tools.graph_tools  # noqa: F401
import app.tools.code_tools  # noqa: F401

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — initializing database")
    await init_db()
    await analysis_service.recover_stuck_projects()
    yield
    logger.info("Shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(v1_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.SERVER_PORT, reload=False)
