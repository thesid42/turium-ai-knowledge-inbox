import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import Settings
from app.errors import create_error

SUPPORTED_CONTENT_TYPES = ("text/html", "text/plain", "text/csv")

_SHELL_MARKER = "this browser version is no longer supported"

_GOOGLE_DOC_RE = re.compile(r"^/document(?:/u/\d+)?/d/(?P<id>[A-Za-z0-9_-]+)")
_GOOGLE_SHEET_RE = re.compile(r"^/spreadsheets(?:/u/\d+)?/d/(?P<id>[A-Za-z0-9_-]+)")
_GOOGLE_SLIDES_RE = re.compile(r"^/presentation(?:/u/\d+)?/d/(?P<id>[A-Za-z0-9_-]+)")


@dataclass(frozen=True, slots=True)
class FetchedPage:
    title: str
    text: str
    final_url: str


def google_export_url(url: str) -> str | None:
    """Rewrite Google Docs/Sheets/Slides links to their plain export endpoints.

    The ``/edit`` pages are JavaScript apps: a server-side fetch only sees a
    browser-support shell, not the document. The export endpoints return the
    actual content as text/plain (Docs, Slides) or text/csv (Sheets).
    Returns ``None`` for any other URL.
    """
    parsed = urlparse(url)
    if parsed.hostname != "docs.google.com":
        return None

    if match := _GOOGLE_DOC_RE.match(parsed.path):
        return f"https://docs.google.com/document/d/{match.group('id')}/export?format=txt"
    if match := _GOOGLE_SHEET_RE.match(parsed.path):
        return f"https://docs.google.com/spreadsheets/d/{match.group('id')}/export?format=csv"
    if match := _GOOGLE_SLIDES_RE.match(parsed.path):
        return f"https://docs.google.com/presentation/d/{match.group('id')}/export?format=txt"
    return None


def is_supported_content_type(content_type: str) -> bool:
    return any(content_type.startswith(allowed) for allowed in SUPPORTED_CONTENT_TYPES)


def _collapse_soft_breaks(text: str) -> str:
    """Join single newlines (inline-tag noise) into spaces, keep blank-line paragraphs."""
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    return text.strip()


def _first_line_title(text: str, max_len: int = 200) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and len(stripped) <= max_len:
            return stripped
    return None


def _is_private_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return (
            addr.is_loopback
            or addr.is_private
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_unspecified
        )
    except ValueError:
        return False


def _check_ssrf(url: str, allow_private: bool) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise create_error("INVALID_URL", "URL must use http or https scheme")

    hostname = parsed.hostname
    if not hostname:
        raise create_error("INVALID_URL", "URL must have a hostname")

    # Block localhost explicitly
    if hostname.lower() == "localhost":
        raise create_error("BLOCKED_URL", "localhost is not allowed")

    try:
        addrs = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise create_error("INVALID_URL", "Could not resolve hostname")

    for addr in addrs:
        ip = addr[4][0]
        if _is_private_ip(ip) and not allow_private:
            raise create_error("BLOCKED_URL", f"Access to private IP {ip} is blocked")


def fetch_url(url: str, settings: Settings) -> FetchedPage:
    _check_ssrf(url, settings.allow_private_urls)

    # Google Docs/Sheets/Slides: fetch the export endpoint instead of the JS app,
    # but keep the original link as the human-facing source.
    export_url = google_export_url(url)
    request_url = export_url or url

    headers = {"User-Agent": settings.fetch_user_agent}
    timeout = httpx.Timeout(settings.fetch_timeout_seconds)
    max_bytes = settings.fetch_max_bytes

    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
            with client.stream("GET", request_url) as resp:
                if not (200 <= resp.status_code < 300):
                    raise create_error(
                        "FETCH_FAILED",
                        f"Upstream returned {resp.status_code}",
                        details={"status": resp.status_code},
                    )

                content_type = resp.headers.get("Content-Type", "").lower()
                if not is_supported_content_type(content_type):
                    raise create_error(
                        "UNSUPPORTED_CONTENT_TYPE",
                        f"Content-Type {content_type} not supported",
                        details={"content_type": content_type},
                    )

                if export_url and content_type.startswith("text/html"):
                    raise create_error(
                        "FETCH_FAILED",
                        "Could not export the Google document. Make sure its sharing is set to "
                        "'Anyone with the link', or paste the text as a note instead.",
                    )

                # Stream body with byte limit
                chunks = []
                total = 0
                for chunk in resp.iter_bytes(chunk_size=8192):
                    total += len(chunk)
                    if total > max_bytes:
                        raise create_error(
                            "CONTENT_TOO_LARGE",
                            f"Response exceeds {max_bytes} bytes",
                            details={"max_bytes": max_bytes},
                        )
                    chunks.append(chunk)

                content = b"".join(chunks)
                final_url = url if export_url else str(resp.url)

    except httpx.TimeoutException:
        raise create_error("FETCH_FAILED", "Request timed out", details={"timeout": settings.fetch_timeout_seconds})
    except httpx.RequestError as e:
        raise create_error("FETCH_FAILED", f"Request failed: {type(e).__name__}", details={"error": str(e)})

    # Decode content (utf-8-sig also strips a leading BOM, e.g. Google Docs exports)
    try:
        text_content = content.decode("utf-8-sig", errors="replace")
    except UnicodeDecodeError:
        text_content = content.decode("latin-1", errors="replace")

    # Plain text / CSV: no HTML parsing needed.
    if content_type.startswith("text/plain") or content_type.startswith("text/csv"):
        text = text_content.strip()
        title = _first_line_title(text) if export_url else None
        if not title:
            title = urlparse(final_url).hostname or "Untitled"
        return FetchedPage(title=title, text=text, final_url=final_url)

    # HTML parsing
    soup = BeautifulSoup(text_content, "html.parser")

    # Remove unwanted elements
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "form", "svg", "iframe"]):
        tag.decompose()

    # Find main content area
    main_content = None
    for selector in ["article", "main", '[role="main"]', "body"]:
        main_content = soup.select_one(selector)
        if main_content:
            break

    if main_content:
        text = _collapse_soft_breaks(main_content.get_text("\n", strip=True))
    else:
        text = _collapse_soft_breaks(soup.get_text("\n", strip=True))

    # Client-rendered apps (e.g. a private Google Doc fallback) return only a shell:
    # fail loudly instead of indexing garbage.
    if len(text) < 500 and _SHELL_MARKER in text.lower():
        raise create_error(
            "FETCH_FAILED",
            "The page content is rendered by JavaScript, so it cannot be fetched directly. "
            "Paste the text as a note, or make the document public ('Anyone with the link').",
        )

    # Extract title
    title = None
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)
    if not title:
        title = urlparse(final_url).hostname or "Untitled"

    return FetchedPage(title=title, text=text, final_url=final_url)
