import pytest
from unittest.mock import patch, MagicMock

from app.schemas import IngestRequest
from app.services.fetcher import FetchedPage


class TestIngestNote:
    def test_note_happy_path(self, client, offline_embedder):
        resp = client.post("/ingest", json={"type": "note", "content": "Hello world", "title": "Test"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["item"]["type"] == "note"
        assert data["item"]["title"] == "Test"
        assert data["item"]["char_count"] == 11
        assert data["chunks_created"] == 1
        assert "id" in data["item"]

    def test_note_empty_content_rejected(self, client):
        resp = client.post("/ingest", json={"type": "note", "content": "   ", "title": "Test"})
        assert resp.status_code == 422
        data = resp.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_note_content_too_long(self, client):
        long_content = "x" * 100001
        resp = client.post("/ingest", json={"type": "note", "content": long_content})
        assert resp.status_code == 422
        data = resp.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_note_duplicate_rejected(self, client, offline_embedder):
        content = "Duplicate note content"
        resp1 = client.post("/ingest", json={"type": "note", "content": content})
        assert resp1.status_code == 201

        resp2 = client.post("/ingest", json={"type": "note", "content": content})
        assert resp2.status_code == 409
        data = resp2.json()
        assert data["error"]["code"] == "DUPLICATE_ITEM"
        assert "item_id" in data["error"]["details"]

    def test_note_extra_fields_rejected(self, client):
        resp = client.post("/ingest", json={"type": "note", "content": "test", "extra": "field"})
        assert resp.status_code == 422
        data = resp.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"


class TestIngestURL:
    @patch("app.routers.ingest.fetch_url")
    def test_url_happy_path(self, mock_fetch, client, offline_embedder):
        mock_fetch.return_value = FetchedPage(
            title="Example Page",
            text="This is the fetched content from the URL.",
            final_url="https://example.com/page",
        )
        resp = client.post("/ingest", json={"type": "url", "url": "https://example.com"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["item"]["type"] == "url"
        assert data["item"]["title"] == "Example Page"
        assert data["item"]["source"] == "https://example.com/page"
        assert data["chunks_created"] >= 1

    @patch("app.routers.ingest.fetch_url")
    def test_url_custom_title_override(self, mock_fetch, client, offline_embedder):
        mock_fetch.return_value = FetchedPage(
            title="Original Title",
            text="Content here",
            final_url="https://example.com",
        )
        resp = client.post("/ingest", json={"type": "url", "url": "https://example.com", "title": "My Title"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["item"]["title"] == "My Title"

    @patch("app.routers.ingest.fetch_url")
    def test_url_empty_content_rejected(self, mock_fetch, client):
        mock_fetch.return_value = FetchedPage(
            title="Empty",
            text="",
            final_url="https://example.com",
        )
        resp = client.post("/ingest", json={"type": "url", "url": "https://example.com"})
        assert resp.status_code == 422
        data = resp.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_url_invalid_scheme(self, client):
        resp = client.post("/ingest", json={"type": "url", "url": "ftp://example.com"})
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "INVALID_URL"

    def test_url_blocked_private(self, client):
        # This should be blocked by SSRF guard
        resp = client.post("/ingest", json={"type": "url", "url": "http://192.168.1.1"})
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "BLOCKED_URL"

    def test_url_localhost_blocked(self, client):
        resp = client.post("/ingest", json={"type": "url", "url": "http://localhost:8000"})
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "BLOCKED_URL"

    def test_url_extra_fields_rejected(self, client):
        resp = client.post("/ingest", json={"type": "url", "url": "https://example.com", "extra": "field"})
        assert resp.status_code == 422
        data = resp.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"


class TestFetchErrorMapping:
    @patch("app.routers.ingest.fetch_url")
    def test_fetch_failed_502(self, mock_fetch, client):
        from app.errors import create_error
        mock_fetch.side_effect = create_error("FETCH_FAILED", "Upstream error", details={"status": 500})
        resp = client.post("/ingest", json={"type": "url", "url": "https://example.com"})
        assert resp.status_code == 502
        data = resp.json()
        assert data["error"]["code"] == "FETCH_FAILED"

    @patch("app.routers.ingest.fetch_url")
    def test_unsupported_content_type_415(self, mock_fetch, client):
        from app.errors import create_error
        mock_fetch.side_effect = create_error("UNSUPPORTED_CONTENT_TYPE", "Bad type", details={"content_type": "application/pdf"})
        resp = client.post("/ingest", json={"type": "url", "url": "https://example.com"})
        assert resp.status_code == 415
        data = resp.json()
        assert data["error"]["code"] == "UNSUPPORTED_CONTENT_TYPE"

    @patch("app.routers.ingest.fetch_url")
    def test_content_too_large_413(self, mock_fetch, client):
        from app.errors import create_error
        mock_fetch.side_effect = create_error("CONTENT_TOO_LARGE", "Too big", details={"max_bytes": 5000000})
        resp = client.post("/ingest", json={"type": "url", "url": "https://example.com"})
        assert resp.status_code == 413
        data = resp.json()
        assert data["error"]["code"] == "CONTENT_TOO_LARGE"

    @patch("app.routers.ingest.fetch_url")
    def test_blocked_url_400(self, mock_fetch, client):
        from app.errors import create_error
        mock_fetch.side_effect = create_error("BLOCKED_URL", "Private IP blocked")
        resp = client.post("/ingest", json={"type": "url", "url": "https://example.com"})
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "BLOCKED_URL"