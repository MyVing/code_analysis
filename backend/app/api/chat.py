import json
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.exceptions import ProjectNotFoundError, ProjectNotReadyError
from app.models.project import Project, ProjectStatus
from app.schemas.chat import ChatRequest
from app.services.agent.claude_client import run_agent_loop

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/{project_id}")
async def chat(
    project_id: uuid.UUID,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project:
        raise ProjectNotFoundError()
    if project.status != ProjectStatus.READY:
        raise ProjectNotReadyError(f"Project status is {project.status.value}, must be ready")

    async def event_generator():
        async for event in run_agent_loop(project_id, body.message, body.session_id):
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
