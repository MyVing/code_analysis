import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class SymbolKind(str, enum.Enum):
    CLASS = "class"
    METHOD = "method"
    FUNCTION = "function"
    VARIABLE = "variable"
    INTERFACE = "interface"
    ANNOTATION = "annotation"
    ENUM = "enum"


class Symbol(UUIDMixin, Base):
    __tablename__ = "symbols"

    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("symbols.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[SymbolKind] = mapped_column(Enum(SymbolKind))
    signature: Mapped[str | None] = mapped_column(Text)
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    modifiers: Mapped[str | None] = mapped_column(String(255))

    file: Mapped["File"] = relationship(back_populates="symbols")
    parent: Mapped["Symbol | None"] = relationship(remote_side="Symbol.id", backref="children")
