import json
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.exceptions import ProjectNotFoundError, ProjectNotReadyError
from app.models.project import Project, ProjectStatus
from app.schemas.chat import ChatRequest
from app.services.agent.langgraph_client import run_agent_loop

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

    # Load output_schema: request body > template
    output_schema = body.output_schema
    if not output_schema and body.template_id:
        from app.models.prompt_template import PromptTemplate
        template = await db.get(PromptTemplate, uuid.UUID(body.template_id))
        if template and template.output_schema:
            output_schema = json.loads(template.output_schema)

    async def event_generator():
        async for event in run_agent_loop(
            project_id,
            body.message,
            body.session_id,
            output_schema=output_schema,
        ):
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
