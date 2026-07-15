from dataclasses import dataclass
from typing import Any, Callable, Awaitable


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]


# Type: (db: AsyncSession, project_id: UUID, **kwargs) -> dict
ToolFunc = Callable[..., Awaitable[dict[str, Any]]]

_TOOL_REGISTRY: dict[str, tuple[ToolDefinition, ToolFunc]] = {}


def tool(name: str, description: str, input_schema: dict[str, Any]):
    def decorator(func: ToolFunc) -> ToolFunc:
        _TOOL_REGISTRY[name] = (ToolDefinition(name, description, input_schema), func)
        return func
    return decorator


def get_tool_definitions() -> list[dict[str, Any]]:
    """Return tool definitions in OpenAI API format."""
    return [
        {
            "type": "function",
            "function": {
                "name": td.name,
                "description": td.description,
                "parameters": td.input_schema,
            },
        }
        for td, _ in _TOOL_REGISTRY.values()
    ]


def get_tool_function(name: str) -> ToolFunc | None:
    entry = _TOOL_REGISTRY.get(name)
    return entry[1] if entry else None


def get_registry() -> dict[str, tuple[ToolDefinition, ToolFunc]]:
    return _TOOL_REGISTRY.copy()
