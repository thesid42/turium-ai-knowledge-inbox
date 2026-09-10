import time
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.providers.base import ChatProvider, EmbeddingProvider, RetrievedChunk
from app.store import ScoredChunk, count_items, count_mismatched_chunks, search


@dataclass(frozen=True, slots=True)
class QueryResult:
    answer: str
    citations: list[dict[str, Any]]
    provider: str
    model: str
    retrieved: int
    latency_ms: int
    warnings: list[str]


def answer_question(
    conn,
    question: str,
    top_k: int,
    embedder: EmbeddingProvider,
    chat: ChatProvider,
    settings: Settings,
) -> QueryResult:
    start = time.perf_counter()

    # 1. Embed question
    question_vec = embedder.embed([question])[0]

    # 2. Search
    scored = search(conn, question_vec, top_k)

    # 3. No chunks at all
    if count_items(conn) == 0:
        return QueryResult(
            answer="You haven't saved anything yet — add a note or URL first.",
            citations=[],
            provider=chat.name,
            model=chat.model,
            retrieved=0,
            latency_ms=int((time.perf_counter() - start) * 1000),
            warnings=[],
        )

    # 4. Retrieval empty (zero vector / no match)
    if not scored:
        return QueryResult(
            answer="I couldn't find anything relevant in your saved items.",
            citations=[],
            provider=chat.name,
            model=chat.model,
            retrieved=0,
            latency_ms=int((time.perf_counter() - start) * 1000),
            warnings=[],
        )

    # 5. Build citations and call chat provider
    retrieved_chunks: list[RetrievedChunk] = []
    citations: list[dict[str, Any]] = []

    for i, sc in enumerate(scored, start=1):
        retrieved_chunks.append(
            RetrievedChunk(
                citation_index=i,
                content=sc.content,
                title=sc.title,
                source=sc.source,
                item_type=sc.item_type,
                score=sc.score,
            )
        )
        # Snippet: first 240 chars
        snippet = sc.content[:240]
        citations.append(
            {
                "index": i,
                "item_id": sc.item_id,
                "chunk_id": sc.chunk_id,
                "title": sc.title,
                "source": sc.source,
                "type": sc.item_type,
                "snippet": snippet,
                "score": round(sc.score, 4),
            }
        )

    answer = chat.answer(question, retrieved_chunks)

    # 6. Warnings
    warnings = []
    mismatched = count_mismatched_chunks(conn, embedder.dimension)
    if mismatched > 0:
        warnings.append(
            f"{mismatched} chunks were embedded with a different model and were skipped; "
            "re-ingest content after changing the AI provider."
        )

    latency_ms = int((time.perf_counter() - start) * 1000)

    return QueryResult(
        answer=answer,
        citations=citations,
        provider=chat.name,
        model=chat.model,
        retrieved=len(scored),
        latency_ms=latency_ms,
        warnings=warnings,
    )