import re
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    content: str
    char_start: int
    char_end: int


def normalize_text(text: str) -> str:
    # 1. Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 2. Collapse 3+ newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 3. Strip trailing spaces per line
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)
    # 4. Strip leading/trailing whitespace
    return text.strip()


def _split_paragraphs(text: str) -> list[str]:
    """Split on blank lines (double newline)."""
    if not text:
        return []
    parts = text.split("\n\n")
    return [p for p in parts if p.strip()]


def _split_sentences(paragraph: str) -> list[str]:
    """Split on sentence boundaries: punctuation followed by whitespace."""
    # Split on . ! ? followed by whitespace
    parts = re.split(r"(?<=[.!?])\s+", paragraph)
    return [p for p in parts if p.strip()]


def _hard_split(text: str, max_chars: int) -> list[str]:
    """Split oversized text at word boundaries, never mid-word."""
    if len(text) <= max_chars:
        return [text]

    result = []
    remaining = text
    while len(remaining) > max_chars:
        # Find last space within max_chars
        split_pos = remaining.rfind(" ", 0, max_chars)
        if split_pos == -1:
            # No space found, force split at max_chars (should not happen for normal text)
            split_pos = max_chars
        chunk = remaining[:split_pos].rstrip()
        result.append(chunk)
        remaining = remaining[split_pos:].lstrip()
    if remaining:
        result.append(remaining)
    return result


def _pack_parts(parts: list[str], max_chars: int) -> list[str]:
    """Greedily pack parts into chunks respecting max_chars with double newline separator."""
    if not parts:
        return []

    chunks = []
    current = parts[0]
    for part in parts[1:]:
        # Need 2 chars for "\n\n" separator
        if len(current) + 2 + len(part) <= max_chars:
            current += "\n\n" + part
        else:
            chunks.append(current)
            current = part
    chunks.append(current)
    return chunks


def _apply_overlap(chunks: list[str], overlap_chars: int) -> list[str]:
    """Prepend overlap from previous chunk, trimmed to word boundary."""
    if not chunks or overlap_chars <= 0:
        return chunks

    result = [chunks[0]]
    for i in range(1, len(chunks)):
        prev = chunks[i - 1]
        curr = chunks[i]

        if len(prev) <= overlap_chars:
            overlap_text = prev
        else:
            overlap_text = prev[-overlap_chars:]
            # Trim to word boundary (find first space from left)
            space_pos = overlap_text.find(" ")
            if space_pos != -1:
                overlap_text = overlap_text[space_pos + 1 :]
            else:
                overlap_text = ""

        if overlap_text and len(overlap_text) + 2 + len(curr) <= len(curr) + overlap_chars + 2:
            # Check if prepending overlap would exceed max_chars (we need to know max_chars here)
            # We'll handle the max_chars check in the caller
            new_chunk = overlap_text + "\n\n" + curr
            result.append(new_chunk)
        else:
            result.append(curr)
    return result


def _merge_small_chunks(chunks: list[str], min_chars: int, max_chars: int) -> list[str]:
    """Merge trailing chunks smaller than min_chars into previous chunk."""
    if not chunks:
        return chunks

    result = [chunks[0]]
    for chunk in chunks[1:]:
        if len(chunk) < min_chars and result:
            # Try to merge with previous
            merged = result[-1] + "\n\n" + chunk
            if len(merged) <= max_chars:
                result[-1] = merged
            else:
                result.append(chunk)
        else:
            result.append(chunk)
    return result


def chunk_text(
    text: str,
    max_chars: int = 1000,
    overlap_chars: int = 150,
    min_chars: int = 50,
) -> list[ChunkDraft]:
    """
    Chunk text according to the specification.
    Returns list of ChunkDraft with offsets relative to normalized text.
    """
    normalized = normalize_text(text)
    if not normalized:
        return []

    if len(normalized) <= max_chars:
        return [ChunkDraft(content=normalized, char_start=0, char_end=len(normalized))]

    # Split into paragraphs
    paragraphs = _split_paragraphs(normalized)

    # Pack paragraphs into initial chunks
    chunks_content: list[str] = []
    for para in paragraphs:
        if len(para) <= max_chars:
            # Try to pack with previous chunks
            if chunks_content and len(chunks_content[-1]) + 2 + len(para) <= max_chars:
                chunks_content[-1] += "\n\n" + para
            else:
                chunks_content.append(para)
        else:
            # Oversized paragraph: split into sentences
            sentences = _split_sentences(para)
            sentence_chunks = _pack_parts(sentences, max_chars)
            for sc in sentence_chunks:
                if len(sc) <= max_chars:
                    if chunks_content and len(chunks_content[-1]) + 2 + len(sc) <= max_chars:
                        chunks_content[-1] += "\n\n" + sc
                    else:
                        chunks_content.append(sc)
                else:
                    # Oversized sentence: hard split at word boundaries
                    hard_chunks = _hard_split(sc, max_chars)
                    for hc in hard_chunks:
                        if chunks_content and len(chunks_content[-1]) + 2 + len(hc) <= max_chars:
                            chunks_content[-1] += "\n\n" + hc
                        else:
                            chunks_content.append(hc)

    # Apply overlap
    chunks_with_overlap = _apply_overlap(chunks_content, overlap_chars)

    # Ensure no chunk exceeds max_chars after overlap (trim if needed)
    final_chunks: list[str] = []
    for chunk in chunks_with_overlap:
        if len(chunk) <= max_chars:
            final_chunks.append(chunk)
        else:
            # This shouldn't happen with proper overlap logic, but safety trim
            final_chunks.append(chunk[:max_chars].rstrip())

    # Merge small trailing chunks
    final_chunks = _merge_small_chunks(final_chunks, min_chars, max_chars)

    # Calculate offsets
    result: list[ChunkDraft] = []
    pos = 0
    for chunk in final_chunks:
        # Find this chunk in normalized text starting from pos
        idx = normalized.find(chunk, pos)
        if idx == -1:
            # Fallback: use current pos
            idx = pos
        char_start = idx
        char_end = idx + len(chunk)
        result.append(ChunkDraft(content=chunk, char_start=char_start, char_end=char_end))
        pos = char_end

    return result