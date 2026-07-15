import shutil
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.core.exceptions import ProjectNotFoundError, AnalysisInProgressError
from app.models.file import File
from app.models.project import Project, ProjectStatus
from app.schemas.project import FileRead, ProjectCreate, ProjectRead, ProjectStatusUpdate
from app.services.analysis_service import analysis_service
from pathlib import Path

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/", response_model=list[ProjectRead])
async def list_projects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    return result.scalars().all()


@router.post("/", response_model=ProjectRead, status_code=201)
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_db)):
    project = Project(**body.model_dump(exclude={"auto_analyze"}))
    db.add(project)
    await db.commit()
    await db.refresh(project)
    if body.auto_analyze:
        analysis_service.start_analysis(project.id)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise ProjectNotFoundError()
    return project


@router.post("/{project_id}/analyze", response_model=ProjectRead)
async def trigger_analysis(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise ProjectNotFoundError()
    if project.status in (ProjectStatus.CLONING, ProjectStatus.PARSING, ProjectStatus.INDEXING):
        raise AnalysisInProgressError()
    analysis_service.start_analysis(project.id)
    return project


@router.get("/{project_id}/files", response_model=list[FileRead])
async def list_project_files(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise ProjectNotFoundError()
    stmt = select(File).where(File.project_id == project_id).order_by(File.file_path)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.patch("/{project_id}/status", response_model=ProjectRead)
async def update_project_status(
    project_id: uuid.UUID,
    body: ProjectStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project:
        raise ProjectNotFoundError()
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise ProjectNotFoundError()
    workspace_path = Path(settings.WORKSPACE_DIR) / project.name
    if workspace_path.exists():
        shutil.rmtree(str(workspace_path), ignore_errors=True)
    await db.delete(project)
    await db.commit()
