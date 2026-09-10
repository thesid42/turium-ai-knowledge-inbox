from fastapi import APIRouter, Depends, Request

from app.config import Settings, get_settings
from app.db import connection
from app.schemas import HealthResponse
from app.store import count_chunks, count_items

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request, settings: Settings = Depends(get_settings)) -> HealthResponse:
    # Get providers from app.state
    embedder = request.app.state.embedding_provider
    chat = request.app.state.chat_provider

    with connection(settings) as conn:
        items = count_items(conn)
        chunks = count_chunks(conn)

    return HealthResponse(
        status="ok",
        provider=embedder.name,
        chat_model=chat.model,
        embedding_model=embedder.model,
        items=items,
        chunks=chunks,
    )