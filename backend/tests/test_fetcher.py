import pytest

from app.services.fetcher import google_export_url, is_supported_content_type


class TestGoogleExportUrl:
    def test_docs_edit_link(self):
        assert (
            google_export_url("https://docs.google.com/document/d/ABC123/edit?usp=sharing")
            == "https://docs.google.com/document/d/ABC123/export?format=txt"
        )

    def test_docs_account_prefix(self):
        assert (
            google_export_url("https://docs.google.com/document/u/0/d/XYZ/edit")
            == "https://docs.google.com/document/d/XYZ/export?format=txt"
        )

    def test_sheets_link(self):
        assert (
            google_export_url("https://docs.google.com/spreadsheets/d/SHEET1/edit#gid=0")
            == "https://docs.google.com/spreadsheets/d/SHEET1/export?format=csv"
        )

    def test_slides_link(self):
        assert (
            google_export_url("https://docs.google.com/presentation/d/SLIDES1/edit")
            == "https://docs.google.com/presentation/d/SLIDES1/export?format=txt"
        )

    def test_export_link_is_stable(self):
        url = "https://docs.google.com/document/d/ABC/export?format=txt"
        assert google_export_url(url) == url

    def test_non_google_urls(self):
        assert google_export_url("https://example.com/document/d/ABC/edit") is None
        assert google_export_url("https://drive.google.com/file/d/ABC/view") is None
        assert google_export_url("https://docs.google.com/spreadsheets/other") is None


class TestContentTypes:
    @pytest.mark.parametrize(
        "content_type",
        ["text/html", "text/html; charset=utf-8", "text/plain", "text/plain; charset=utf-8", "text/csv"],
    )
    def test_supported(self, content_type):
        assert is_supported_content_type(content_type)

    @pytest.mark.parametrize("content_type", ["application/pdf", "application/json", "image/png", ""])
    def test_unsupported(self, content_type):
        assert not is_supported_content_type(content_type)
