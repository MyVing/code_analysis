import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PromptParamDef(BaseModel):
    key: str
    label: str
    type: str = "text"  # text | select
    required: bool = True
    placeholder: str | None = None
    options: list[str] | None = None


class PromptTemplateRead(BaseModel):
    id: uuid.UUID
    name: str
    icon: str
    description: str
    category: str
    prompt_template: str
    parameters: list[PromptParamDef]
    output_schema: dict | None = None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_params(cls, obj):
        import json
        data = {
            "id": obj.id,
            "name": obj.name,
            "icon": obj.icon,
            "description": obj.description,
            "category": obj.category,
            "prompt_template": obj.prompt_template,
            "parameters": json.loads(obj.parameters) if isinstance(obj.parameters, str) else obj.parameters,
            "output_schema": json.loads(obj.output_schema) if isinstance(obj.output_schema, str) else obj.output_schema,
            "sort_order": obj.sort_order,
            "is_active": obj.is_active,
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
        }
        return cls(**data)


class PromptTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    icon: str = Field(default="📝", max_length=10)
    description: str = Field(default="", max_length=255)
    category: str = Field(default="general", max_length=50)
    prompt_template: str = Field(..., min_length=1)
    parameters: list[PromptParamDef] = Field(default_factory=list)
    output_schema: dict | None = None
    sort_order: int = Field(default=0)
    is_active: bool = Field(default=True)


class PromptTemplateUpdate(BaseModel):
    name: str | None = None
    icon: str | None = None
    description: str | None = None
    category: str | None = None
    prompt_template: str | None = None
    parameters: list[PromptParamDef] | None = None
    output_schema: dict | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class PromptExecuteRequest(BaseModel):
    params: dict[str, str] = Field(default_factory=dict)


class PromptExecuteResponse(BaseModel):
    prompt: str
