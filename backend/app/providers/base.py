from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    citation_index: int
    content: str
    title: str | None
    source: str | None
    item_type: str
    score: float


class EmbeddingProvider(Protocol):
    name: str
    model: str
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class ChatProvider(Protocol):
    name: str
    model: str

    def answer(self, question: str, sources: list[RetrievedChunk]) -> str: ...