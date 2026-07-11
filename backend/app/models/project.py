import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ProjectStatus(str, enum.Enum):
    PENDING = "pending"
    CLONING = "cloning"
    PARSING = "parsing"
    INDEXING = "indexing"
    READY = "ready"
    ERROR = "error"


class Project(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255))
    git_url: Mapped[str] = mapped_column(String(1024))
    language: Mapped[str] = mapped_column(String(50), default="java")
    framework: Mapped[str | None] = mapped_column(String(100))
    branch: Mapped[str] = mapped_column(String(255), default="main")
    commit: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), default=ProjectStatus.PENDING
    )

    files: Mapped[list["File"]] = relationship(back_populates="project", cascade="all, delete-orphan")
