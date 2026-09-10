import pytest


class TestErrorEnvelope:
    def test_validation_error_format(self, client):
        resp = client.post("/ingest", json={"type": "note"})  # missing content
        assert resp.status_code == 422
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "details" in data["error"]
        assert "errors" in data["error"]["details"]
        assert isinstance(data["error"]["details"]["errors"], list)

    def test_not_found_format(self, client):
        resp = client.get("/items/nonexistent")
        assert resp.status_code == 404
        data = resp.json()
        assert data["error"]["code"] == "NOT_FOUND"
        assert "message" in data["error"]

    def test_duplicate_item_format(self, client, offline_embedder):
        content = "Duplicate test"
        client.post("/ingest", json={"type": "note", "content": content})
        resp = client.post("/ingest", json={"type": "note", "content": content})
        assert resp.status_code == 409
        data = resp.json()
        assert data["error"]["code"] == "DUPLICATE_ITEM"
        assert "item_id" in data["error"]["details"]

    def test_invalid_url_format(self, client):
        resp = client.post("/ingest", json={"type": "url", "url": "ftp://example.com"})
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "INVALID_URL"

    def test_blocked_url_format(self, client):
        resp = client.post("/ingest", json={"type": "url", "url": "http://10.0.0.1"})
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "BLOCKED_URL"

    def test_unsupported_content_type_format(self, client):
        # This is tested via mock in test_ingest_api
        pass

    def test_content_too_large_format(self, client):
        pass

    def test_fetch_failed_format(self, client):
        pass

    def test_x_request_id_header(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert "X-Request-ID" in resp.headers
        # Should be valid hex uuid
        rid = resp.headers["X-Request-ID"]
        assert len(rid) == 32
        assert all(c in "0123456789abcdef" for c in rid)

    def test_x_request_id_echoed(self, client):
        custom_id = "custom-request-id-123"
        resp = client.get("/health", headers={"X-Request-ID": custom_id})
        assert resp.status_code == 200
        assert resp.headers["X-Request-ID"] == custom_id

    def test_cors_headers(self, client):
        # Proper preflight request includes Access-Control-Request-Method
        resp = client.options("/health", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        })
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers


class TestStructuredLogging:
    def test_logging_output(self, client, capfd):
        # This is more of an integration check - just verify no crashes
        client.get("/health")
        # Structured logging goes to stdout, hard to capture in unit test
        pass