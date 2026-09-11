import re

import numpy as np
from openai import OpenAI, OpenAIError

from app.errors import AppError, create_error
from app.providers.base import ChatProvider, EmbeddingProvider, RetrievedChunk

# Some models emit provider-specific citation glyphs (e.g. 【1†L1-L4】) despite the
# prompt asking for [1]; normalize them so the UI and answer text stay consistent.
_CITATION_GLYPH_RE = re.compile(r"【\s*(\d+)\s*[^】]*】")
_CITATION_DAGGER_RE = re.compile(r"\[\s*(\d+)\s*†[^\]]*\]")


def normalize_citations(text: str) -> str:
    """Rewrite model-specific citation markers to bracketed numeric ones: 【1†L1-L4】 -> [1]."""
    text = _CITATION_GLYPH_RE.sub(r"[\1]", text)
    text = _CITATION_DAGGER_RE.sub(r"[\1]", text)
    return text


class OpenAIEmbeddingProvider:
    def __init__(self, api_key: str, base_url: str | None, model: str) -> None:
        self.name = "openai"
        self.model = model
        self.dimension = 1536  # text-embedding-3-small
        self._client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

    def embed(self, texts: list[str]) -> list[list[float]]:
        # Batch in groups of 100 (OpenAI limit)
        batch_size = 100
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                resp = self._client.embeddings.create(model=self.model, input=batch)
                # Preserve order
                embeddings = [d.embedding for d in resp.data]
                all_embeddings.extend(embeddings)
            except OpenAIError as e:
                raise create_error(
                    "UPSTREAM_AI_ERROR",
                    "Embedding request failed",
                    details={"error": str(e), "model": self.model},
                ) from e

        return all_embeddings


class OpenAIChatProvider:
    def __init__(self, api_key: str, base_url: str | None, model: str) -> None:
        self.name = "openai"
        self.model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

    def answer(self, question: str, sources: list[RetrievedChunk]) -> str:
        if not sources:
            return "I couldn't find anything relevant in your saved items."

        # Build context blocks
        context_blocks = []
        for src in sources:
            title_part = src.title or "Untitled"
            source_part = src.source or "note"
            header = f"[{src.citation_index}] ({title_part}, {source_part})"
            context_blocks.append(f"{header}\n{src.content}")

        context = "\n\n".join(context_blocks)

        system = (
            "You are a knowledge assistant. Answer ONLY from the user's saved content below. "
            "Cite every claim with bracketed source numbers, e.g. [1]. "
            "If the answer is not in the content, say you couldn't find it in the saved items. "
            "Be concise."
        )
        user = f"{context}\n\nQuestion: {question}"

        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.2,
            )
            return normalize_citations(resp.choices[0].message.content or "")
        except OpenAIError as e:
            raise create_error(
                "UPSTREAM_AI_ERROR",
                "Chat completion failed",
                details={"error": str(e), "model": self.model},
            ) from e