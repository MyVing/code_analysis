import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class PromptTemplate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "prompt_templates"

    name: Mapped[str] = mapped_column(String(100))
    icon: Mapped[str] = mapped_column(String(10))
    description: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(50), default="general")
    prompt_template: Mapped[str] = mapped_column(Text)
    parameters: Mapped[str] = mapped_column(Text, default="[]")
    output_schema: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
