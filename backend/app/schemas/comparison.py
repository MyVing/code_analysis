from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ChangeType = Literal["added", "deleted", "modified", "renamed", "copied"]


class CommitInfo(BaseModel):
    sha: str
    short_sha: str
    message: str
    author: str
    authored_at: datetime


class DiffSummary(BaseModel):
    files_changed: int = 0
    added_files: int = 0
    deleted_files: int = 0
    modified_files: int = 0
    renamed_files: int = 0
    copied_files: int = 0
    additions: int = 0
    deletions: int = 0


class ChangedFile(BaseModel):
    old_path: str | None = None
    new_path: str | None = None
    change_type: ChangeType
    additions: int = 0
    deletions: int = 0
    is_binary: bool = False
    is_truncated: bool = False


class Hunk(BaseModel):
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str] = Field(default_factory=list)


class CommitDiffResult(BaseModel):
    base_commit: CommitInfo
    head_commit: CommitInfo
    summary: DiffSummary
    files: list[ChangedFile] = Field(default_factory=list)


class FileDiffResult(ChangedFile):
    old_content: str | None = None
    new_content: str | None = None
    patch: str | None = None
    hunks: list[Hunk] = Field(default_factory=list)
