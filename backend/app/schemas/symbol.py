import uuid

from pydantic import BaseModel

from app.models.symbol import SymbolKind


class SymbolRead(BaseModel):
    id: uuid.UUID
    file_id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    kind: SymbolKind
    signature: str | None
    start_line: int
    end_line: int
    modifiers: str | None

    model_config = {"from_attributes": True}


class SymbolQuery(BaseModel):
    name: str | None = None
    kind: SymbolKind | None = None
    file_id: uuid.UUID | None = None
