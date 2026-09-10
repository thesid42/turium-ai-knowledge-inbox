import tempfile
from pathlib import Path

import pytest

from app.config import Settings, create_settings
from app.main import create_app
from app.providers.offline import OfflineChatProvider, OfflineEmbeddingProvider


@pytest.fixture
def temp_db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test.db")


@pytest.fixture
def test_settings(temp_db_path: str) -> Settings:
    return create_settings(
        db_path=temp_db_path,
        ai_provider="offline",
        chunk_max_chars=1000,
        chunk_overlap_chars=150,
        chunk_min_chars=50,
        fetch_timeout_seconds=10,
        fetch_max_bytes=5000000,
        allow_private_urls=False,
        default_top_k=5,
        max_top_k=20,
        offline_embedding_dim=512,
        log_level="DEBUG",
    )


@pytest.fixture
def offline_embedder() -> OfflineEmbeddingProvider:
    return OfflineEmbeddingProvider(dimension=512)


@pytest.fixture
def offline_chat(offline_embedder: OfflineEmbeddingProvider) -> OfflineChatProvider:
    return OfflineChatProvider(offline_embedder)


@pytest.fixture
def test_app(test_settings: Settings, offline_embedder: OfflineEmbeddingProvider, offline_chat: OfflineChatProvider):
    return create_app(settings=test_settings, embedding_provider=offline_embedder, chat_provider=offline_chat)


@pytest.fixture
def client(test_app):
    from fastapi.testclient import TestClient
    with TestClient(test_app) as client:
        yield client