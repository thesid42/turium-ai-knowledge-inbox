import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import sqlite3

from app.config import Settings


@dataclass(frozen=True, slots=True)
class ScoredChunk:
    chunk_id: str
    item_id: str
    chunk_index: int
    content: str
    char_start: int
    char_end: int
    title: str | None
    source: str | None
    item_type: str
    score: float


def _compute_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _serialize_embedding(vec: list[float]) -> bytes:
    arr = np.array(vec, dtype=np.float32)
    return arr.tobytes()


def _deserialize_embedding(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL CHECK (type IN ('note','url')),
            title TEXT,
            source TEXT,
            raw_content TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            char_count INTEGER NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_items_content_hash ON items(content_hash);

        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            char_start INTEGER NOT NULL,
            char_end INTEGER NOT NULL,
            embedding BLOB NOT NULL,
            embedding_dim INTEGER NOT NULL,
            embedding_model TEXT NOT NULL,
            embedding_provider TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_chunks_item_id ON chunks(item_id);
        """
    )


def insert_item_with_chunks(
    conn: sqlite3.Connection,
    *,
    item_type: str,
    title: str | None,
    source: str | None,
    raw_content: str,
    chunks: list[tuple[str, int, int, list[float], str, str]],
    settings: Settings,
) -> tuple[str, int]:
    """
    Insert item and its chunks in a single transaction.
    chunks: list of (content, char_start, char_end, embedding, embedding_model, embedding_provider)
    Returns (item_id, chunk_count)
    """
    content_hash = _compute_content_hash(raw_content)
    now = datetime.now(timezone.utc).isoformat()
    char_count = len(raw_content)
    item_id = uuid.uuid4().hex[:12]

    # Check for duplicate
    existing = conn.execute("SELECT id FROM items WHERE content_hash = ?", (content_hash,)).fetchone()
    if existing:
        raise ValueError(f"duplicate:{existing['id']}")

    conn.execute(
        """
        INSERT INTO items (id, type, title, source, raw_content, content_hash, created_at, char_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (item_id, item_type, title, source, raw_content, content_hash, now, char_count),
    )

    chunk_rows = []
    for idx, (content, char_start, char_end, embedding, emb_model, emb_provider) in enumerate(chunks):
        chunk_id = uuid.uuid4().hex[:12]
        emb_blob = _serialize_embedding(embedding)
        chunk_rows.append(
            (
                chunk_id,
                item_id,
                idx,
                content,
                char_start,
                char_end,
                emb_blob,
                len(embedding),
                emb_model,
                emb_provider,
                now,
            )
        )

    conn.executemany(
        """
        INSERT INTO chunks (id, item_id, chunk_index, content, char_start, char_end,
                           embedding, embedding_dim, embedding_model, embedding_provider, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        chunk_rows,
    )

    return item_id, len(chunks)


def list_items(conn: sqlite3.Connection, limit: int, offset: int) -> tuple[list[sqlite3.Row], int]:
    total_row = conn.execute("SELECT COUNT(*) as cnt FROM items").fetchone()
    total = total_row["cnt"] if total_row else 0

    rows = conn.execute(
        """
        SELECT i.id, i.type, i.title, i.source, i.created_at, i.char_count,
               COUNT(c.id) as chunk_count
        FROM items i
        LEFT JOIN chunks c ON c.item_id = i.id
        GROUP BY i.id
        ORDER BY i.created_at DESC, i.rowid DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()

    return rows, total


def get_item(conn: sqlite3.Connection, item_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT i.id, i.type, i.title, i.source, i.raw_content, i.content_hash,
               i.created_at, i.char_count,
               COUNT(c.id) as chunk_count
        FROM items i
        LEFT JOIN chunks c ON c.item_id = i.id
        WHERE i.id = ?
        GROUP BY i.id
        """,
        (item_id,),
    ).fetchone()


def get_item_chunks(conn: sqlite3.Connection, item_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, chunk_index, content, char_start, char_end,
               embedding_model, embedding_provider, embedding_dim
        FROM chunks
        WHERE item_id = ?
        ORDER BY chunk_index
        """,
        (item_id,),
    ).fetchall()


def delete_item(conn: sqlite3.Connection, item_id: str) -> bool:
    cur = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    return cur.rowcount > 0


def count_items(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) as cnt FROM items").fetchone()
    return row["cnt"] if row else 0


def count_chunks(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) as cnt FROM chunks").fetchone()
    return row["cnt"] if row else 0


def search(
    conn: sqlite3.Connection,
    query_embedding: list[float],
    top_k: int,
) -> list[ScoredChunk]:
    if not query_embedding or all(v == 0.0 for v in query_embedding):
        return []

    q_vec = np.array(query_embedding, dtype=np.float32)
    dim = len(query_embedding)

    rows = conn.execute(
        """
        SELECT c.id, c.item_id, c.chunk_index, c.content, c.char_start, c.char_end,
               c.embedding, c.embedding_dim,
               i.title, i.source, i.type
        FROM chunks c
        JOIN items i ON i.id = c.item_id
        WHERE c.embedding_dim = ?
        """,
        (dim,),
    ).fetchall()

    if not rows:
        return []

    q_norm = np.linalg.norm(q_vec)
    if q_norm == 0:
        return []
    q_unit = q_vec / q_norm

    scored: list[ScoredChunk] = []
    for row in rows:
        emb = _deserialize_embedding(row["embedding"])
        if emb.shape[0] != dim:
            continue
        score = float(np.dot(q_unit, emb))
        # Non-positive cosine means no lexical/semantic overlap: not a retrieval.
        if score <= 0.0:
            continue
        scored.append(
            ScoredChunk(
                chunk_id=row["id"],
                item_id=row["item_id"],
                chunk_index=row["chunk_index"],
                content=row["content"],
                char_start=row["char_start"],
                char_end=row["char_end"],
                title=row["title"],
                source=row["source"],
                item_type=row["type"],
                score=score,
            )
        )

    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:top_k]


def count_mismatched_chunks(conn: sqlite3.Connection, dim: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM chunks WHERE embedding_dim != ?", (dim,)
    ).fetchone()
    return row["cnt"] if row else 0