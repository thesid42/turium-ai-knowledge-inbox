from app.providers.openai_provider import normalize_citations


class TestNormalizeCitations:
    def test_glyph_citations(self):
        assert normalize_citations("Chunks are ~1000 chars 【1†L1-L4】.") == "Chunks are ~1000 chars [1]."

    def test_multiple_glyph_citations(self):
        assert normalize_citations("Warm-up steps 【1†L1-L4】 【4†L1-L4】") == "Warm-up steps [1] [4]"

    def test_adjacent_glyphs(self):
        assert normalize_citations("answer 【2†L4-L7】【3†L8-L9】") == "answer [2][3]"

    def test_bracket_dagger_citations(self):
        assert normalize_citations("feature [5†L10-L12] here") == "feature [5] here"

    def test_plain_citations_unchanged(self):
        assert normalize_citations("Already fine [1] and [2].") == "Already fine [1] and [2]."

    def test_no_citations_unchanged(self):
        assert normalize_citations("No citations here.") == "No citations here."
