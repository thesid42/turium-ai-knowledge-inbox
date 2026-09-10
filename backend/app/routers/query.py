from fastapi import APIRouter, Depends, Request

from app.config import Settings, get_settings
from app.db import connection
from app.schemas import QueryRequest, QueryResponse
from app.services.rag import answer_question

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
def query(
    request: Request,
    payload: QueryRequest,
    settings: Settings = Depends(get_settings),
) -> QueryResponse:
    embedder = request.app.state.embedding_provider
    chat = request.app.state.chat_provider

    # Apply defaults and validation
    top_k = payload.top_k if payload.top_k is not None else settings.default_top_k
    top_k = min(top_k, settings.max_top_k)

    with connection(settings) as conn:
        result = answer_question(conn, payload.question, top_k, embedder, chat, settings)

    return QueryResponse(
        answer=result.answer,
        citations=result.citations,
        provider=result.provider,
        model=result.model,
        retrieved=result.retrieved,
        latency_ms=result.latency_ms,
        warnings=result.warnings,
    )