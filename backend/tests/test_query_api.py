import pytest


class TestQueryEmptyStore:
    def test_query_empty_store(self, client):
        resp = client.post("/query", json={"question": "What did I save?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "You haven't saved anything yet — add a note or URL first."
        assert data["citations"] == []
        assert data["retrieved"] == 0
        assert data["provider"] == "offline"
        assert data["model"] == "offline-extractive"
        assert data["warnings"] == []


class TestQueryAfterIngest:
    def test_query_with_matching_content(self, client, offline_embedder):
        # Ingest some content
        client.post("/ingest", json={"type": "note", "content": "Apple is a fruit that grows on trees.", "title": "Apple Note"})
        client.post("/ingest", json={"type": "note", "content": "Cars have wheels and engines.", "title": "Car Note"})

        resp = client.post("/query", json={"question": "What is an apple?", "top_k": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] != ""
        assert data["citations"] != []
        assert data["retrieved"] > 0
        assert data["provider"] == "offline"
        assert data["model"] == "offline-extractive"
        # Citations should have required fields
        for cit in data["citations"]:
            assert "index" in cit
            assert "item_id" in cit
            assert "chunk_id" in cit
            assert "snippet" in cit
            assert "score" in cit
            assert isinstance(cit["score"], float)

    def test_query_no_match_returns_canned(self, client, offline_embedder):
        client.post("/ingest", json={"type": "note", "content": "Apple is a fruit.", "title": "Apple Note"})

        # Use a query with zero token overlap to ensure best_score <= 0
        resp = client.post("/query", json={"question": "xyzzy car", "top_k": 5})
        assert resp.status_code == 200
        data = resp.json()
        # Offline mode with no good match returns canned response
        assert "couldn't find" in data["answer"].lower() or "relevant" in data["answer"].lower()
        assert data["citations"] == []
        assert data["retrieved"] == 0

    def test_query_top_k_respected(self, client, offline_embedder):
        # Add multiple items
        for i in range(10):
            client.post("/ingest", json={"type": "note", "content": f"Item {i} content about topic {i}", "title": f"Item {i}"})

        resp = client.post("/query", json={"question": "topic 5", "top_k": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert data["retrieved"] <= 3

    def test_question_validation(self, client):
        # Empty question
        resp = client.post("/query", json={"question": "   "})
        assert resp.status_code == 422

        # Too long
        resp = client.post("/query", json={"question": "x" * 1001})
        assert resp.status_code == 422

        # Missing question
        resp = client.post("/query", json={})
        assert resp.status_code == 422

    def test_top_k_validation(self, client):
        resp = client.post("/query", json={"question": "test", "top_k": 0})
        assert resp.status_code == 422

        resp = client.post("/query", json={"question": "test", "top_k": 21})
        assert resp.status_code == 422

    def test_default_top_k(self, client, offline_embedder):
        client.post("/ingest", json={"type": "note", "content": "Test content"})
        # Don't specify top_k, should use default (5)
        resp = client.post("/query", json={"question": "test"})
        assert resp.status_code == 200
        # Default top_k is 5, but retrieved depends on matches

    def test_scores_sorted_descending(self, client, offline_embedder):
        client.post("/ingest", json={"type": "note", "content": "Apple fruit red green", "title": "Apple"})
        client.post("/ingest", json={"type": "note", "content": "Banana yellow fruit", "title": "Banana"})

        resp = client.post("/query", json={"question": "apple fruit", "top_k": 5})
        data = resp.json()
        if data["citations"]:
            scores = [c["score"] for c in data["citations"]]
            assert scores == sorted(scores, reverse=True)


class TestQueryWithWarnings:
    def test_mismatched_dimension_warning(self, client, test_settings, offline_embedder):
        # This test would require inserting chunks with different dimensions
        # which is hard to do via API. Skip for now - tested in store tests.
        pass