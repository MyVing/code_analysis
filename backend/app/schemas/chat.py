import uuid

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    template_id: str | None = None
    template_params: dict | None = None
    output_schema: dict | None = None


class ChatEvent(BaseModel):
    event: str
    data: dict
