from fastapi import APIRouter

from app.api.chat import router as chat_router
from app.api.comparisons import router as comparisons_router
from app.api.files import router as files_router
from app.api.graph import router as graph_router
from app.api.projects import router as projects_router
from app.api.prompt_templates import router as prompt_templates_router
from app.api.symbols import router as symbols_router
from app.core.config import settings

api_router = APIRouter(prefix="/api")


@api_router.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}


api_router.include_router(projects_router)
api_router.include_router(symbols_router)
api_router.include_router(graph_router)
api_router.include_router(chat_router)
api_router.include_router(comparisons_router)
api_router.include_router(files_router)
api_router.include_router(prompt_templates_router)
