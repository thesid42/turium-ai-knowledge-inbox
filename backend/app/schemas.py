from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints


class NoteIngest(BaseModel):
    type: Literal["note"]
    content: Annotated[str, StringConstraints(min_length=1, max_length=100000, strip_whitespace=True)]
    title: Annotated[str | None, StringConstraints(max_length=200)] = None

    model_config = {"extra": "forbid"}


class URLIngest(BaseModel):
    type: Literal["url"]
    url: Annotated[str, StringConstraints(min_length=1, max_length=2048, strip_whitespace=True)]
    title: Annotated[str | None, StringConstraints(max_length=200)] = None

    model_config = {"extra": "forbid"}


IngestRequest = Annotated[NoteIngest | URLIngest, Field(discriminator="type")]


class IngestResponseItem(BaseModel):
    id: str
    type: Literal["note", "url"]
    title: str | None
    source: str | None
    created_at: datetime
    char_count: int
    chunk_count: int


class IngestResponse(BaseModel):
    item: IngestResponseItem
    chunks_created: int


class ItemSummary(BaseModel):
    id: str
    type: Literal["note", "url"]
    title: str | None
    source: str | None
    created_at: datetime
    char_count: int
    chunk_count: int


class ItemsListResponse(BaseModel):
    items: list[ItemSummary]
    total: int
    limit: int
    offset: int


class ChunkDetail(BaseModel):
    id: str
    chunk_index: int
    content: str
    char_start: int
    char_end: int
    embedding_model: str


class ItemDetailResponse(BaseModel):
    item: ItemSummary
    chunks: list[ChunkDetail]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    provider: str
    chat_model: str
    embedding_model: str
    items: int
    chunks: int


class Citation(BaseModel):
    index: int
    item_id: str
    chunk_id: str
    title: str | None
    source: str | None
    type: Literal["note", "url"]
    snippet: str
    score: float


class QueryRequest(BaseModel):
    question: Annotated[str, StringConstraints(min_length=1, max_length=1000, strip_whitespace=True)]
    top_k: Annotated[int, Field(ge=1, le=20)] = 5


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    provider: str
    model: str
    retrieved: int
    latency_ms: int
    warnings: list[str]


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail