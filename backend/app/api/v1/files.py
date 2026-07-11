import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.models.file import File
from app.models.project import Project
from app.schemas.project import FileContentRead
from app.services.analyzer.git_manager import GitManager

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{file_id}/content", response_model=FileContentRead)
async def get_file_content(file_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    file = await db.get(File, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    project = await db.get(Project, file.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    git_mgr = GitManager(db)
    try:
        content = await git_mgr.read_file(project.name, file.file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return FileContentRead(
        id=file.id,
        file_path=file.file_path,
        language=file.language,
        content=content,
    )
