import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class File(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "files"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    file_path: Mapped[str] = mapped_column(String(1024))
    language: Mapped[str] = mapped_column(String(50))
    content_hash: Mapped[str | None] = mapped_column(String(32))

    project: Mapped["Project"] = relationship(back_populates="files")
    symbols: Mapped[list["Symbol"]] = relationship(back_populates="file", cascade="all, delete-orphan")
