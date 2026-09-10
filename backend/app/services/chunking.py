"""Deterministic, structure-aware chunking.

The chunker works on *character spans* of the normalized text. Every chunk is
exactly ``normalized_text[char_start:char_end]``, which makes offsets exact and
makes it impossible to silently drop content: the text is first partitioned
into non-overlapping units (paragraph -> sentence -> word), then units are
packed into chunks, overlap is added only when it fits the size budget, and a
tiny trailing chunk is merged into its predecessor.

Sizes are character-based (see docs/DESIGN.md for the rationale).
"""

import re
from dataclasses import dataclass

Span = tuple[int, int]

_SENTENCE_RE = re.compile(r"[^.!?]*[.!?]+(?:\s+|$)|[^.!?]+$")
_WORD_RE = re.compile(r"\S+")


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    content: str
    char_start: int
    char_end: int


def normalize_text(text: str) -> str:
    """Normalize line endings, collapse blank-line runs, strip per-line trailing spaces."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return text.strip()


def _trim_span(text: str, span: Span) -> Span:
    """Shrink a span so it contains no leading/trailing whitespace."""
    start, end = span
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return (start, end)


def _paragraph_spans(text: str) -> list[Span]:
    """Exact spans of paragraphs (text between blank lines)."""
    spans: list[Span] = []
    pos = 0
    for part in text.split("\n\n"):
        if part:
            spans.append((pos, pos + len(part)))
        pos += len(part) + 2  # advance past the "\n\n" separator
    return spans


def _sentence_spans(text: str, start: int, end: int) -> list[Span]:
    """Exact spans of sentences inside ``text[start:end]`` (trailing spaces trimmed)."""
    segment = text[start:end]
    return [_trim_span(text, (start + m.start(), start + m.end())) for m in _SENTENCE_RE.finditer(segment)]


def _word_spans(text: str, start: int, end: int) -> list[Span]:
    """Exact spans of whitespace-delimited words inside ``text[start:end]``."""
    segment = text[start:end]
    return [(start + m.start(), start + m.end()) for m in _WORD_RE.finditer(segment)]


def _cap_span(span: Span, max_chars: int) -> list[Span]:
    """Last-resort split for a single token longer than max_chars (no word boundary exists)."""
    start, end = span
    if end - start <= max_chars:
        return [span]
    return [(pos, min(pos + max_chars, end)) for pos in range(start, end, max_chars)]


def _build_units(text: str, max_chars: int) -> list[Span]:
    """Partition the whole text into non-overlapping units, each <= max_chars."""
    units: list[Span] = []
    for para_start, para_end in _paragraph_spans(text):
        if para_end - para_start <= max_chars:
            units.append((para_start, para_end))
            continue
        for sent_start, sent_end in _sentence_spans(text, para_start, para_end):
            if sent_end - sent_start <= max_chars:
                units.append((sent_start, sent_end))
                continue
            for word_span in _word_spans(text, sent_start, sent_end):
                units.extend(_cap_span(word_span, max_chars))
    return units


def _pack_units(units: list[Span], max_chars: int) -> list[Span]:
    """Greedily pack contiguous units into chunks of at most max_chars."""
    if not units:
        return []

    chunks: list[Span] = []
    current_start, current_end = units[0]
    for unit_start, unit_end in units[1:]:
        if unit_end - current_start <= max_chars:
            current_end = unit_end
        else:
            chunks.append((current_start, current_end))
            current_start, current_end = unit_start, unit_end
    chunks.append((current_start, current_end))
    return chunks


def _apply_overlap(text: str, chunks: list[Span], overlap_chars: int, max_chars: int) -> list[Span]:
    """Extend each chunk backwards into the previous one, only within its size budget."""
    if not chunks or overlap_chars <= 0:
        return chunks

    result: list[Span] = [chunks[0]]
    for i in range(1, len(chunks)):
        start, end = chunks[i]
        budget = max_chars - (end - start)
        if budget <= 0:
            result.append((start, end))
            continue

        previous_start, _ = chunks[i - 1]
        overlap_start = max(previous_start, start - overlap_chars)
        # Snap the overlap start forward to the next word boundary.
        gap = text[overlap_start:start].find(" ")
        overlap_start = start if gap == -1 else overlap_start + gap + 1
        # If the overlap is still too large for the budget, shrink it further.
        if start - overlap_start > budget:
            overlap_start = start - budget
            gap = text[overlap_start:start].find(" ")
            overlap_start = start if gap == -1 else overlap_start + gap + 1

        result.append((overlap_start, end) if overlap_start < start else (start, end))
    return result


def _merge_small_chunks(text: str, chunks: list[Span], min_chars: int, max_chars: int) -> list[Span]:
    """Merge a chunk smaller than min_chars into the previous one when it still fits."""
    if not chunks:
        return chunks

    result: list[Span] = [chunks[0]]
    for start, end in chunks[1:]:
        if end - start < min_chars:
            merged_start, merged_end = result[-1][0], end
            if merged_end - merged_start <= max_chars:
                result[-1] = (merged_start, merged_end)
                continue
        result.append((start, end))
    return result


def chunk_text(
    text: str,
    max_chars: int = 1000,
    overlap_chars: int = 150,
    min_chars: int = 50,
) -> list[ChunkDraft]:
    """Split text into chunks of at most ``max_chars`` characters.

    Guarantees:
    - every chunk is exactly ``normalized[char_start:char_end]`` (no content mutation),
    - no chunk exceeds ``max_chars``,
    - every non-whitespace character of the input appears in at least one chunk.
    """
    normalized = normalize_text(text)
    if not normalized:
        return []

    if len(normalized) <= max_chars:
        return [ChunkDraft(content=normalized, char_start=0, char_end=len(normalized))]

    units = _build_units(normalized, max_chars)
    chunks = _pack_units(units, max_chars)
    chunks = _apply_overlap(normalized, chunks, overlap_chars, max_chars)
    chunks = _merge_small_chunks(normalized, chunks, min_chars, max_chars)

    return [
        ChunkDraft(
            content=normalized[start:end],
            char_start=start,
            char_end=end,
        )
        for start, end in chunks
        if end > start
    ]
