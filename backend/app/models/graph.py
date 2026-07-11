import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class ImportType(str, enum.Enum):
    IMPORT = "import"
    FROM_IMPORT = "from_import"
    STATIC_IMPORT = "static_import"


class CallGraph(UUIDMixin, Base):
    __tablename__ = "call_graph"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    caller_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("symbols.id", ondelete="CASCADE"))
    callee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("symbols.id", ondelete="CASCADE"))
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"))
    line_number: Mapped[int] = mapped_column(Integer)


class FieldAccess(UUIDMixin, Base):
    __tablename__ = "field_accesses"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    accessor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("symbols.id", ondelete="CASCADE"))
    accessed_field_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("symbols.id", ondelete="CASCADE"))
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"))
    line_number: Mapped[int] = mapped_column(Integer)


class Import(UUIDMixin, Base):
    __tablename__ = "imports"

    source_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"))
    target_module: Mapped[str] = mapped_column(String(1024))
    import_type: Mapped[ImportType] = mapped_column(Enum(ImportType))


class ImplementsRelation(UUIDMixin, Base):
    __tablename__ = "implements_relations"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    interface_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("symbols.id", ondelete="CASCADE"))
    impl_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("symbols.id", ondelete="CASCADE"))
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"))
