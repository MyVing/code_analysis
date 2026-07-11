from fastapi import APIRouter

from app.api.v1.chat import router as chat_router
from app.api.v1.files import router as files_router
from app.api.v1.graph import router as graph_router
from app.api.v1.projects import router as projects_router
from app.api.v1.symbols import router as symbols_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(projects_router)
v1_router.include_router(symbols_router)
v1_router.include_router(graph_router)
v1_router.include_router(chat_router)
v1_router.include_router(files_router)
