import pytest


class TestItemsList:
    def test_empty_list(self, client):
        resp = client.get("/items")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["limit"] == 50
        assert data["offset"] == 0

    def test_list_with_items(self, client, offline_embedder):
        # Add a few items
        for i in range(3):
            client.post("/ingest", json={"type": "note", "content": f"Content {i}", "title": f"Note {i}"})

        resp = client.get("/items")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        # Newest first
        assert data["items"][0]["title"] == "Note 2"
        assert data["items"][1]["title"] == "Note 1"
        assert data["items"][2]["title"] == "Note 0"

    def test_pagination(self, client, offline_embedder):
        for i in range(5):
            client.post("/ingest", json={"type": "note", "content": f"Content {i}"})

        resp = client.get("/items?limit=2&offset=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 2
        assert data["offset"] == 1
        assert len(data["items"]) == 2

    def test_limit_validation(self, client):
        resp = client.get("/items?limit=0")
        assert resp.status_code == 422
        resp = client.get("/items?limit=101")
        assert resp.status_code == 422

    def test_offset_validation(self, client):
        resp = client.get("/items?offset=-1")
        assert resp.status_code == 422


class TestItemDetail:
    def test_get_existing_item(self, client, offline_embedder):
        resp = client.post("/ingest", json={"type": "note", "content": "Detail test", "title": "Detail Note"})
        item_id = resp.json()["item"]["id"]

        resp = client.get(f"/items/{item_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["item"]["id"] == item_id
        assert data["item"]["title"] == "Detail Note"
        assert len(data["chunks"]) == 1
        assert data["chunks"][0]["content"] == "Detail test"

    def test_get_nonexistent_item(self, client):
        resp = client.get("/items/nonexistent")
        assert resp.status_code == 404
        data = resp.json()
        assert data["error"]["code"] == "NOT_FOUND"


class TestItemDelete:
    def test_delete_existing_item(self, client, offline_embedder):
        resp = client.post("/ingest", json={"type": "note", "content": "To delete", "title": "Delete Me"})
        item_id = resp.json()["item"]["id"]

        resp = client.delete(f"/items/{item_id}")
        assert resp.status_code == 204

        # Verify deleted
        resp = client.get(f"/items/{item_id}")
        assert resp.status_code == 404

        # Verify list updated
        resp = client.get("/items")
        assert resp.json()["total"] == 0

    def test_delete_nonexistent_item(self, client):
        resp = client.delete("/items/nonexistent")
        assert resp.status_code == 404
        data = resp.json()
        assert data["error"]["code"] == "NOT_FOUND"

    def test_delete_cascades_chunks(self, client, offline_embedder):
        resp = client.post("/ingest", json={"type": "note", "content": "A" * 2000, "title": "Long"})
        item_id = resp.json()["item"]["id"]

        # Should have multiple chunks
        detail = client.get(f"/items/{item_id}")
        assert len(detail.json()["chunks"]) > 1

        resp = client.delete(f"/items/{item_id}")
        assert resp.status_code == 204

        # Verify no orphan chunks
        resp = client.get("/items")
        assert resp.json()["total"] == 0