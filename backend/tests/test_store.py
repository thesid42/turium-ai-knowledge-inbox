import pytest

from app.config import create_settings
from app.db import connection, init_schema
from app.store import (
    ScoredChunk,
    count_chunks,
    count_items,
    count_mismatched_chunks,
    delete_item,
    get_item,
    get_item_chunks,
    insert_item_with_chunks,
    list_items,
    search,
)


@pytest.fixture
def store_conn(test_settings):
    with connection(test_settings) as conn:
        init_schema(conn)
        yield conn


def test_init_schema_idempotent(test_settings):
    with connection(test_settings) as conn:
        init_schema(conn)
        init_schema(conn)  # Should not raise
        # Tables exist
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        names = {t["name"] for t in tables}
        assert "items" in names
        assert "chunks" in names


def test_insert_item_with_chunks(store_conn, test_settings, offline_embedder):
    content = "Test content for embedding"
    chunks = [("Test content for embedding", 0, 28)]
    embeddings = offline_embedder.embed([c[0] for c in chunks])
    chunk_data = [
        (c[0], c[1], c[2], emb, offline_embedder.model, offline_embedder.name)
        for c, emb in zip(chunks, embeddings)
    ]

    item_id, count = insert_item_with_chunks(
        store_conn,
        item_type="note",
        title="Test Note",
        source=None,
        raw_content=content,
        chunks=chunk_data,
        settings=test_settings,
    )
    store_conn.commit()

    assert count == 1
    assert len(item_id) == 12

    # Verify item
    item = get_item(store_conn, item_id)
    assert item is not None
    assert item["type"] == "note"
    assert item["title"] == "Test Note"
    assert item["char_count"] == len(content)

    # Verify chunks
    item_chunks = get_item_chunks(store_conn, item_id)
    assert len(item_chunks) == 1
    assert item_chunks[0]["content"] == content


def test_duplicate_content_hash_rejected(store_conn, test_settings, offline_embedder):
    content = "Duplicate content"
    chunks = [(content, 0, len(content))]
    embeddings = offline_embedder.embed([content])
    chunk_data = [(content, 0, len(content), embeddings[0], offline_embedder.model, offline_embedder.name)]

    # First insert
    item_id1, _ = insert_item_with_chunks(
        store_conn, item_type="note", title="First", source=None,
        raw_content=content, chunks=chunk_data, settings=test_settings
    )
    store_conn.commit()

    # Second insert should raise
    with pytest.raises(ValueError, match="duplicate:"):
        insert_item_with_chunks(
            store_conn, item_type="note", title="Second", source=None,
            raw_content=content, chunks=chunk_data, settings=test_settings
        )


def test_list_items_pagination(store_conn, test_settings, offline_embedder):
    # Insert multiple items
    for i in range(5):
        content = f"Content {i}"
        chunks = [(content, 0, len(content))]
        embeddings = offline_embedder.embed([content])
        chunk_data = [(content, 0, len(content), embeddings[0], offline_embedder.model, offline_embedder.name)]
        insert_item_with_chunks(
            store_conn, item_type="note", title=f"Note {i}", source=None,
            raw_content=content, chunks=chunk_data, settings=test_settings
        )
    store_conn.commit()

    rows, total = list_items(store_conn, limit=2, offset=0)
    assert total == 5
    assert len(rows) == 2
    # Newest first
    assert rows[0]["title"] == "Note 4"
    assert rows[1]["title"] == "Note 3"

    rows2, _ = list_items(store_conn, limit=2, offset=2)
    assert len(rows2) == 2
    assert rows2[0]["title"] == "Note 2"


def test_get_item_not_found(store_conn, test_settings):
    item = get_item(store_conn, "nonexistent")
    assert item is None


def test_get_item_chunks(store_conn, test_settings, offline_embedder):
    content = "Chunk test content"
    chunks = [(content, 0, len(content))]
    embeddings = offline_embedder.embed([content])
    chunk_data = [(content, 0, len(content), embeddings[0], offline_embedder.model, offline_embedder.name)]

    item_id, _ = insert_item_with_chunks(
        store_conn, item_type="note", title="Test", source=None,
        raw_content=content, chunks=chunk_data, settings=test_settings
    )
    store_conn.commit()

    item_chunks = get_item_chunks(store_conn, item_id)
    assert len(item_chunks) == 1
    assert item_chunks[0]["content"] == content
    assert item_chunks[0]["chunk_index"] == 0


def test_delete_item_cascades(store_conn, test_settings, offline_embedder):
    content = "Delete me"
    chunks = [(content, 0, len(content))]
    embeddings = offline_embedder.embed([content])
    chunk_data = [(content, 0, len(content), embeddings[0], offline_embedder.model, offline_embedder.name)]

    item_id, _ = insert_item_with_chunks(
        store_conn, item_type="note", title="Test", source=None,
        raw_content=content, chunks=chunk_data, settings=test_settings
    )
    store_conn.commit()

    deleted = delete_item(store_conn, item_id)
    assert deleted is True
    store_conn.commit()

    assert get_item(store_conn, item_id) is None
    assert count_chunks(store_conn) == 0


def test_delete_item_not_found(store_conn, test_settings):
    deleted = delete_item(store_conn, "nonexistent")
    assert deleted is False


def test_search_returns_top_k(store_conn, test_settings, offline_embedder):
    # Insert items with different content
    texts = [
        "Apple banana fruit",
        "Car truck vehicle",
        "Apple computer technology",
    ]
    for i, text in enumerate(texts):
        chunks = [(text, 0, len(text))]
        embeddings = offline_embedder.embed([text])
        chunk_data = [(text, 0, len(text), embeddings[0], offline_embedder.model, offline_embedder.name)]
        insert_item_with_chunks(
            store_conn, item_type="note", title=f"Item {i}", source=None,
            raw_content=text, chunks=chunk_data, settings=test_settings
        )
    store_conn.commit()

    # Query for "apple"
    query_vec = offline_embedder.embed(["apple"])[0]
    results = search(store_conn, query_vec, top_k=2)

    assert len(results) == 2
    assert all(isinstance(r, ScoredChunk) for r in results)
    # Should be sorted by score descending
    assert results[0].score >= results[1].score
    # Both apple-related should rank higher
    assert "Apple" in results[0].content or "Apple" in results[1].content


def test_search_zero_vector_returns_empty(store_conn, test_settings):
    results = search(store_conn, [0.0] * 512, top_k=5)
    assert results == []


def test_search_empty_query_returns_empty(store_conn, test_settings):
    results = search(store_conn, [], top_k=5)
    assert results == []


def test_search_filters_by_dimension(store_conn, test_settings, offline_embedder):
    # Insert with 512-dim
    content = "Test content"
    chunks = [(content, 0, len(content))]
    embeddings = offline_embedder.embed([content])
    chunk_data = [(content, 0, len(content), embeddings[0], offline_embedder.model, offline_embedder.name)]
    insert_item_with_chunks(
        store_conn, item_type="note", title="Test", source=None,
        raw_content=content, chunks=chunk_data, settings=test_settings
    )
    store_conn.commit()

    # Search with wrong dimension (100)
    query_vec = [0.1] * 100
    results = search(store_conn, query_vec, top_k=5)
    assert results == []


def test_count_mismatched_chunks(store_conn, test_settings, offline_embedder):
    # Insert with 512-dim
    content = "Test"
    chunks = [(content, 0, len(content))]
    embeddings = offline_embedder.embed([content])
    chunk_data = [(content, 0, len(content), embeddings[0], offline_embedder.model, offline_embedder.name)]
    insert_item_with_chunks(
        store_conn, item_type="note", title="Test", source=None,
        raw_content=content, chunks=chunk_data, settings=test_settings
    )
    store_conn.commit()

    # Count mismatched for different dimension
    mismatched = count_mismatched_chunks(store_conn, dim=256)
    assert mismatched == 1

    # Count mismatched for same dimension
    mismatched = count_mismatched_chunks(store_conn, dim=512)
    assert mismatched == 0