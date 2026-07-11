import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.project import ProjectStatus


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    git_url: str = Field(..., min_length=1)
    language: str = "java"
    branch: str = "main"
    auto_analyze: bool = True


class ProjectRead(BaseModel):
    id: uuid.UUID
    name: str
    git_url: str
    language: str
    framework: str | None
    branch: str
    commit: str | None
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectStatusUpdate(BaseModel):
    status: ProjectStatus
    commit: str | None = None
    framework: str | None = None


class FileRead(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    file_path: str
    language: str
    content_hash: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FileContentRead(BaseModel):
    id: uuid.UUID
    file_path: str
    language: str
    content: str


class AnalysisTrigger(BaseModel):
    pass
