import json
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.exceptions import TemplateNotFoundError
from app.models.prompt_template import PromptTemplate
from app.schemas.prompt_template import (
    PromptExecuteRequest,
    PromptExecuteResponse,
    PromptTemplateCreate,
    PromptTemplateRead,
    PromptTemplateUpdate,
)

router = APIRouter(prefix="/prompt-templates", tags=["prompt-templates"])


@router.get("/", response_model=list[PromptTemplateRead])
async def list_templates(db: AsyncSession = Depends(get_db)):
    stmt = select(PromptTemplate).where(PromptTemplate.is_active == True).order_by(PromptTemplate.sort_order)
    result = await db.execute(stmt)
    templates = result.scalars().all()
    return [PromptTemplateRead.from_orm_with_params(t) for t in templates]


@router.get("/all", response_model=list[PromptTemplateRead])
async def list_all_templates(db: AsyncSession = Depends(get_db)):
    stmt = select(PromptTemplate).order_by(PromptTemplate.sort_order)
    result = await db.execute(stmt)
    templates = result.scalars().all()
    return [PromptTemplateRead.from_orm_with_params(t) for t in templates]


@router.post("/", response_model=PromptTemplateRead, status_code=201)
async def create_template(body: PromptTemplateCreate, db: AsyncSession = Depends(get_db)):
    template = PromptTemplate(
        name=body.name,
        icon=body.icon,
        description=body.description,
        category=body.category,
        prompt_template=body.prompt_template,
        parameters=json.dumps([p.model_dump() for p in body.parameters]),
        output_schema=json.dumps(body.output_schema) if body.output_schema else None,
        sort_order=body.sort_order,
        is_active=body.is_active,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return PromptTemplateRead.from_orm_with_params(template)


@router.put("/{template_id}", response_model=PromptTemplateRead)
async def update_template(
    template_id: uuid.UUID,
    body: PromptTemplateUpdate,
    db: AsyncSession = Depends(get_db),
):
    template = await db.get(PromptTemplate, template_id)
    if not template:
        raise TemplateNotFoundError()

    update_data = body.model_dump(exclude_unset=True)
    if "parameters" in update_data and update_data["parameters"] is not None:
        update_data["parameters"] = json.dumps([p.model_dump() for p in update_data["parameters"]])
    if "output_schema" in update_data and update_data["output_schema"] is not None:
        update_data["output_schema"] = json.dumps(update_data["output_schema"])

    for key, value in update_data.items():
        setattr(template, key, value)

    await db.commit()
    await db.refresh(template)
    return PromptTemplateRead.from_orm_with_params(template)


@router.delete("/{template_id}", status_code=204)
async def delete_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    template = await db.get(PromptTemplate, template_id)
    if not template:
        raise TemplateNotFoundError()
    await db.delete(template)
    await db.commit()


@router.post("/{template_id}/execute", response_model=PromptExecuteResponse)
async def execute_template(
    template_id: uuid.UUID,
    body: PromptExecuteRequest,
    db: AsyncSession = Depends(get_db),
):
    template = await db.get(PromptTemplate, template_id)
    if not template:
        raise TemplateNotFoundError()

    prompt = template.prompt_template
    for key, value in body.params.items():
        prompt = prompt.replace(f"{{{key}}}", value)

    return PromptExecuteResponse(prompt=prompt)
