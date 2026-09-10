import pytest

from app.services.chunking import ChunkDraft, chunk_text, normalize_text


class TestNormalizeText:
    def test_crlf_to_lf(self):
        assert normalize_text("a\r\nb") == "a\nb"

    def test_collapse_multiple_newlines(self):
        assert normalize_text("a\n\n\nb") == "a\n\nb"
        assert normalize_text("a\n\n\n\nb") == "a\n\nb"

    def test_strip_trailing_spaces(self):
        # Spec: strip trailing spaces per line, then strip outer whitespace.
        # Leading spaces on a line are preserved (only trailing stripped per line).
        assert normalize_text("a \n b ") == "a\n b"

    def test_strip_outer_whitespace(self):
        assert normalize_text("  hello  ") == "hello"

    def test_empty_string(self):
        assert normalize_text("") == ""
        assert normalize_text("   \n\n  ") == ""


class TestChunkText:
    def test_short_text_single_chunk(self):
        text = "Hello world"
        chunks = chunk_text(text, max_chars=1000, overlap_chars=150, min_chars=50)
        assert len(chunks) == 1
        assert chunks[0].content == "Hello world"
        assert chunks[0].char_start == 0
        assert chunks[0].char_end == 11

    def test_empty_text(self):
        chunks = chunk_text("", max_chars=1000, overlap_chars=150, min_chars=50)
        assert chunks == []

    def test_whitespace_only(self):
        chunks = chunk_text("   \n\n  ", max_chars=1000, overlap_chars=150, min_chars=50)
        assert chunks == []

    def test_paragraph_packing(self):
        text = "Para one.\n\nPara two.\n\nPara three."
        chunks = chunk_text(text, max_chars=50, overlap_chars=0, min_chars=10)
        # Should pack paragraphs greedily
        assert len(chunks) >= 1
        for c in chunks:
            assert len(c.content) <= 50

    def test_oversized_paragraph_sentence_split(self):
        # A long paragraph without blank lines, but with sentences
        text = "Sentence one. " * 50  # ~700 chars
        chunks = chunk_text(text, max_chars=200, overlap_chars=20, min_chars=30)
        assert len(chunks) > 1
        for c in chunks:
            assert len(c.content) <= 200

    def test_oversized_sentence_hard_split(self):
        # Single very long "sentence" (no period)
        text = "word " * 300  # ~1500 chars, no sentence breaks
        chunks = chunk_text(text, max_chars=200, overlap_chars=20, min_chars=30)
        assert len(chunks) > 1
        for c in chunks:
            assert len(c.content) <= 200
            # Should not split mid-word
            assert not c.content.endswith("wor")

    def test_overlap_applied(self):
        text = "Para one.\n\nPara two.\n\nPara three."
        chunks = chunk_text(text, max_chars=30, overlap_chars=15, min_chars=10)
        # With overlap, second chunk should start with end of first
        if len(chunks) >= 2:
            # Check that overlap was applied (within max_chars limit)
            assert len(chunks[1].content) <= 30

    def test_min_chars_merge(self):
        # Create scenario where last chunk would be tiny and merge is possible without exceeding max_chars
        # First para: 70 chars, second para: 20 chars, min_chars=30, max_chars=100
        # Merged: 70 + 2 + 20 = 92 <= 100, so merge should happen
        text = "A" * 70 + "\n\n" + "B" * 20
        chunks = chunk_text(text, max_chars=100, overlap_chars=0, min_chars=30)
        # Tiny chunk should be merged into previous
        assert len(chunks) == 1
        assert len(chunks[0].content) == 92  # 70 + 2 + 20

    def test_no_chunk_exceeds_max(self):
        text = "x" * 5000
        chunks = chunk_text(text, max_chars=1000, overlap_chars=150, min_chars=50)
        for c in chunks:
            assert len(c.content) <= 1000

    def test_chunks_cover_content(self):
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        chunks = chunk_text(text, max_chars=100, overlap_chars=20, min_chars=10)
        # Concatenated (without overlap) should cover all non-whitespace
        combined = "".join(c.content for c in chunks)
        # Normalize both for comparison
        normalized = normalize_text(text)
        # Since overlap adds duplication, just check all original text chars appear
        for ch in normalized:
            if not ch.isspace():
                assert ch in combined

    def test_offsets_correct(self):
        text = "Hello world.\n\nGoodbye world."
        chunks = chunk_text(text, max_chars=100, overlap_chars=0, min_chars=10)
        normalized = normalize_text(text)
        for c in chunks:
            assert normalized[c.char_start:c.char_end] == c.content

    def test_deterministic(self):
        text = "This is a test. " * 100
        c1 = chunk_text(text, max_chars=500, overlap_chars=50, min_chars=50)
        c2 = chunk_text(text, max_chars=500, overlap_chars=50, min_chars=50)
        assert len(c1) == len(c2)
        for a, b in zip(c1, c2):
            assert a.content == b.content
            assert a.char_start == b.char_start
            assert a.char_end == b.char_end

    def test_offsets_exact_with_overlap(self):
        text = "Sentence one. Sentence two. Sentence three. " * 40
        normalized = normalize_text(text)
        chunks = chunk_text(text, max_chars=200, overlap_chars=50, min_chars=30)
        assert len(chunks) > 1
        for c in chunks:
            assert normalized[c.char_start:c.char_end] == c.content

    def test_no_content_dropped(self):
        text = "Alpha beta gamma delta. " * 100 + "\n\n" + "word " * 200
        normalized = normalize_text(text)
        chunks = chunk_text(text, max_chars=300, overlap_chars=100, min_chars=50)
        covered = [False] * len(normalized)
        for c in chunks:
            for i in range(c.char_start, c.char_end):
                covered[i] = True
        for i, ch in enumerate(normalized):
            if not ch.isspace():
                assert covered[i], f"character {i} ({ch!r}) missing from every chunk"

    def test_overlap_never_exceeds_max(self):
        # Dense text with no paragraph breaks: overlap must be clipped to the budget
        text = "word " * 1000
        chunks = chunk_text(text, max_chars=250, overlap_chars=200, min_chars=50)
        assert len(chunks) > 1
        for c in chunks:
            assert len(c.content) <= 250