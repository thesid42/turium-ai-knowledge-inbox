import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.db import connection
from app.errors import AppError, create_error
from app.schemas import IngestRequest, IngestResponse, IngestResponseItem
from app.services import ChunkDraft, chunk_text, fetch_url
from app.store import insert_item_with_chunks

router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
def ingest(
    request: Request,
    payload: IngestRequest,
    settings: Settings = Depends(get_settings),
) -> IngestResponse | JSONResponse:
    embedder = request.app.state.embedding_provider

    with connection(settings) as conn:
        try:
            if payload.type == "note":
                content = payload.content.strip()
                if not content:
                    raise create_error("VALIDATION_ERROR", "Content cannot be empty")

                title = payload.title.strip() if payload.title else None
                source = None
                raw_content = content

            else:  # url
                fetched = fetch_url(payload.url, settings)
                raw_content = fetched.text
                if not raw_content.strip():
                    raise create_error("VALIDATION_ERROR", "Fetched page has no text content")

                title = payload.title.strip() if payload.title else fetched.title
                source = fetched.final_url

            # Chunk the content
            chunks_draft = chunk_text(
                raw_content,
                max_chars=settings.chunk_max_chars,
                overlap_chars=settings.chunk_overlap_chars,
                min_chars=settings.chunk_min_chars,
            )

            if not chunks_draft:
                raise create_error("VALIDATION_ERROR", "No chunks generated from content")

            # Embed chunks
            chunk_contents = [c.content for c in chunks_draft]
            embeddings = embedder.embed(chunk_contents)

            # Prepare chunk data for insertion
            chunk_data = []
            for draft, emb in zip(chunks_draft, embeddings):
                chunk_data.append((
                    draft.content,
                    draft.char_start,
                    draft.char_end,
                    emb,
                    embedder.model,
                    embedder.name,
                ))

            item_id, chunk_count = insert_item_with_chunks(
                conn,
                item_type=payload.type,
                title=title,
                source=source,
                raw_content=raw_content,
                chunks=chunk_data,
                settings=settings,
            )

            conn.commit()

        except AppError:
            raise
        except ValueError as e:
            if str(e).startswith("duplicate:"):
                existing_id = str(e).split(":", 1)[1]
                raise create_error("DUPLICATE_ITEM", "Item with same content already exists", details={"item_id": existing_id})
            raise create_error("INTERNAL_ERROR", str(e))
        except Exception as e:
            raise create_error("INTERNAL_ERROR", f"Failed to ingest: {type(e).__name__}")

    item = IngestResponseItem(
        id=item_id,
        type=payload.type,
        title=title,
        source=source,
        created_at=datetime.now(timezone.utc),
        char_count=len(raw_content),
        chunk_count=chunk_count,
    )

    return IngestResponse(item=item, chunks_created=chunk_count)