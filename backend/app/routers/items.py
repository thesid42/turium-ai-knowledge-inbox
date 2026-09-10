from fastapi import APIRouter, Depends, Query, Request, status

from app.config import Settings, get_settings
from app.db import connection
from app.errors import create_error
from app.schemas import ItemDetailResponse, ItemSummary, ItemsListResponse, ChunkDetail
from app.store import count_items, delete_item, get_item, get_item_chunks, list_items

router = APIRouter(tags=["items"])


@router.get("/items", response_model=ItemsListResponse)
def list_items_endpoint(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    settings: Settings = Depends(get_settings),
) -> ItemsListResponse:
    with connection(settings) as conn:
        rows, total = list_items(conn, limit, offset)

    items = [
        ItemSummary(
            id=row["id"],
            type=row["type"],
            title=row["title"],
            source=row["source"],
            created_at=row["created_at"],
            char_count=row["char_count"],
            chunk_count=row["chunk_count"],
        )
        for row in rows
    ]

    return ItemsListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/items/{item_id}", response_model=ItemDetailResponse)
def get_item_endpoint(
    request: Request,
    item_id: str,
    settings: Settings = Depends(get_settings),
) -> ItemDetailResponse:
    with connection(settings) as conn:
        item_row = get_item(conn, item_id)
        if not item_row:
            raise create_error("NOT_FOUND", "Item not found")

        chunk_rows = get_item_chunks(conn, item_id)

    item = ItemSummary(
        id=item_row["id"],
        type=item_row["type"],
        title=item_row["title"],
        source=item_row["source"],
        created_at=item_row["created_at"],
        char_count=item_row["char_count"],
        chunk_count=item_row["chunk_count"],
    )

    chunks = [
        ChunkDetail(
            id=row["id"],
            chunk_index=row["chunk_index"],
            content=row["content"],
            char_start=row["char_start"],
            char_end=row["char_end"],
            embedding_model=row["embedding_model"],
        )
        for row in chunk_rows
    ]

    return ItemDetailResponse(item=item, chunks=chunks)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item_endpoint(
    request: Request,
    item_id: str,
    settings: Settings = Depends(get_settings),
) -> None:
    with connection(settings) as conn:
        deleted = delete_item(conn, item_id)
        if not deleted:
            raise create_error("NOT_FOUND", "Item not found")
        conn.commit()