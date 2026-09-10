import hashlib
import math
import re

import numpy as np

from app.providers.base import ChatProvider, EmbeddingProvider, RetrievedChunk


class OfflineEmbeddingProvider:
    """Lexical embedding via stable sparse signed token hashing (NOT semantic).

    Each token maps to a single dimension (``hash % dim``) with a pseudo-random
    sign. This is the classic hashing trick: texts with disjoint vocabularies
    have a cosine of exactly 0 (modulo rare hash collisions), unlike dense
    random projections which give every pair a small accidental similarity.
    """

    def __init__(self, dimension: int = 512) -> None:
        self.name = "offline"
        self.model = f"offline-hashing-{dimension}"
        self.dimension = dimension

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[a-z0-9']+", text.lower())

    def _token_hash(self, token: str) -> int:
        # Stable 64-bit hash via blake2b
        return int.from_bytes(
            hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(), "little"
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            tokens = self._tokenize(text)
            if not tokens:
                vectors.append([0.0] * self.dimension)
                continue

            # Count term frequencies
            tf: dict[str, int] = {}
            for tok in tokens:
                tf[tok] = tf.get(tok, 0) + 1

            # Sparse signed hashing: one dimension per token, stable sign bit
            vec = np.zeros(self.dimension, dtype=np.float32)
            for tok, count in tf.items():
                weight = 1.0 + math.log(count)  # 1 + ln(tf)
                h = self._token_hash(tok)
                idx = h % self.dimension
                sign = -1.0 if (h >> 63) & 1 else 1.0
                vec[idx] += sign * weight

            # L2 normalize
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm

            vectors.append(vec.tolist())

        return vectors


class OfflineChatProvider:
    """Extractive answer: pick top sentences by cosine similarity to question."""

    def __init__(self, embedding_provider: OfflineEmbeddingProvider) -> None:
        self.embedding_provider = embedding_provider
        self.name = "offline"
        self.model = "offline-extractive"

    def _split_sentences(self, text: str) -> list[str]:
        parts = re.split(r"(?<=[.!?])\s+", text)
        return [p.strip() for p in parts if p.strip()]

    def _cosine(self, a: list[float], b: list[float]) -> float:
        va = np.array(a, dtype=np.float32)
        vb = np.array(b, dtype=np.float32)
        na = np.linalg.norm(va)
        nb = np.linalg.norm(vb)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(va / na, vb / nb))

    def answer(self, question: str, sources: list[RetrievedChunk]) -> str:
        if not sources:
            return (
                "I couldn't find anything relevant in your saved items. "
                "(Offline mode uses keyword matching — set OPENAI_API_KEY for semantic answers.)"
            )

        question_vec = self.embedding_provider.embed([question])[0]
        if all(v == 0.0 for v in question_vec):
            return (
                "I couldn't find anything relevant in your saved items. "
                "(Offline mode uses keyword matching — set OPENAI_API_KEY for semantic answers.)"
            )

        # Collect all sentences with their source info
        all_sentences: list[tuple[str, int, float]] = []  # (sentence, source_idx, score)
        for idx, src in enumerate(sources):
            sentences = self._split_sentences(src.content)
            if not sentences:
                continue
            sent_vecs = self.embedding_provider.embed(sentences)
            for sent, vec in zip(sentences, sent_vecs):
                score = self._cosine(question_vec, vec)
                all_sentences.append((sent, idx, score))

        if not all_sentences:
            return (
                "I couldn't find anything relevant in your saved items. "
                "(Offline mode uses keyword matching — set OPENAI_API_KEY for semantic answers.)"
            )

        # Sort by score descending
        all_sentences.sort(key=lambda x: x[2], reverse=True)

        best_score = all_sentences[0][2]
        if best_score <= 0:
            return (
                "I couldn't find anything relevant in your saved items. "
                "(Offline mode uses keyword matching — set OPENAI_API_KEY for semantic answers.)"
            )

        threshold = max(0.05, 0.5 * best_score)
        selected: list[tuple[str, int]] = []
        seen: set[str] = set()

        for sent, src_idx, score in all_sentences:
            if score < threshold:
                break
            if len(selected) >= 4:
                break
            # Dedupe identical sentences
            if sent in seen:
                continue
            seen.add(sent)
            selected.append((sent, src_idx))

        if not selected:
            return (
                "I couldn't find anything relevant in your saved items. "
                "(Offline mode uses keyword matching — set OPENAI_API_KEY for semantic answers.)"
            )

        # Format answer with citation markers
        parts = []
        for i, (sent, src_idx) in enumerate(selected):
            parts.append(f"{sent} [{src_idx + 1}]")

        return " ".join(parts)