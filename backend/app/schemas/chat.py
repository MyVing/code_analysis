import uuid

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatEvent(BaseModel):
    event: str
    data: dict
