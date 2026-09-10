import logging

from app.config import Settings
from app.providers.base import ChatProvider, EmbeddingProvider
from app.providers.offline import OfflineChatProvider, OfflineEmbeddingProvider
from app.providers.openai_provider import OpenAIChatProvider, OpenAIEmbeddingProvider

logger = logging.getLogger(__name__)


def build_providers(settings: Settings) -> tuple[EmbeddingProvider, ChatProvider]:
    provider_name = settings.ai_provider.lower()

    if provider_name == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when AI_PROVIDER=openai")
        emb = OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.embedding_model,
        )
        chat = OpenAIChatProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.chat_model,
        )
        logger.info("Using OpenAI provider (explicit)")
        return emb, chat

    if provider_name == "offline":
        emb = OfflineEmbeddingProvider(dimension=settings.offline_embedding_dim)
        chat = OfflineChatProvider(emb)
        logger.info("Using offline provider (explicit)")
        return emb, chat

    # auto
    if settings.openai_api_key:
        emb = OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.embedding_model,
        )
        chat = OpenAIChatProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.chat_model,
        )
        logger.info("Using OpenAI provider (auto-detected via OPENAI_API_KEY)")
        return emb, chat

    emb = OfflineEmbeddingProvider(dimension=settings.offline_embedding_dim)
    chat = OfflineChatProvider(emb)
    logger.info("Using offline provider (auto, no OPENAI_API_KEY)")
    return emb, chat