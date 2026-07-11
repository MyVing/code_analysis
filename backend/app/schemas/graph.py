import uuid

from pydantic import BaseModel

from app.models.graph import ImportType


class CallGraphRead(BaseModel):
    id: uuid.UUID
    caller_id: uuid.UUID
    callee_id: uuid.UUID
    file_id: uuid.UUID
    line_number: int

    model_config = {"from_attributes": True}


class ImportRead(BaseModel):
    id: uuid.UUID
    source_file_id: uuid.UUID
    target_module: str
    import_type: ImportType

    model_config = {"from_attributes": True}


class GraphNode(BaseModel):
    id: uuid.UUID
    name: str
    kind: str
    file_path: str
    start_line: int
    end_line: int
    parent_id: uuid.UUID | None = None
    file_id: uuid.UUID | None = None
    signature: str | None = None
    modifiers: str | None = None


class GraphEdge(BaseModel):
    id: uuid.UUID
    source: uuid.UUID
    target: uuid.UUID
    edge_type: str
    line_number: int | None = None


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class ExpandedGraphData(BaseModel):
    parent_node: GraphNode
    child_nodes: list[GraphNode]
    edges: list[GraphEdge]


class FieldAccessRead(BaseModel):
    id: uuid.UUID
    accessor_id: uuid.UUID
    accessed_field_id: uuid.UUID
    file_id: uuid.UUID
    line_number: int

    model_config = {"from_attributes": True}
