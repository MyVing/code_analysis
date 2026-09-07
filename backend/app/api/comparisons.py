import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.analyzer.git_diff_service import GitDiffService

router = APIRouter(prefix="/projects", tags=["comparisons"])


@router.get("/{project_id}/commits")
async def list_commits(project_id: uuid.UUID, limit: int = Query(50, ge=1, le=100), ref: str | None = None, db: AsyncSession = Depends(get_db)):
    return await GitDiffService(db).list_commits(project_id, limit, ref)


@router.get("/{project_id}/commit-diffs")
async def compare_commits(project_id: uuid.UUID, base_commit: str, head_commit: str, file_pattern: str | None = None, db: AsyncSession = Depends(get_db)):
    return await GitDiffService(db).compare_commits(project_id, base_commit, head_commit, file_pattern)


@router.get("/{project_id}/commit-diffs/file")
async def get_file_diff(project_id: uuid.UUID, base_commit: str, head_commit: str, path: str, db: AsyncSession = Depends(get_db)):
    return await GitDiffService(db).get_file_diff(project_id, base_commit, head_commit, path)
