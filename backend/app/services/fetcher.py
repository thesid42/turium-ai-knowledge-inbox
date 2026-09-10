import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import Settings
from app.errors import AppError, create_error


@dataclass(frozen=True, slots=True)
class FetchedPage:
    title: str
    text: str
    final_url: str


def _collapse_soft_breaks(text: str) -> str:
    """Join single newlines (inline-tag noise) into spaces, keep blank-line paragraphs."""
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    return text.strip()


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

    headers = {"User-Agent": settings.fetch_user_agent}
    timeout = httpx.Timeout(settings.fetch_timeout_seconds)
    max_bytes = settings.fetch_max_bytes

    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
            with client.stream("GET", url) as resp:
                if not (200 <= resp.status_code < 300):
                    raise create_error(
                        "FETCH_FAILED",
                        f"Upstream returned {resp.status_code}",
                        details={"status": resp.status_code},
                    )

                content_type = resp.headers.get("Content-Type", "").lower()
                if not (content_type.startswith("text/html") or content_type.startswith("text/plain")):
                    raise create_error(
                        "UNSUPPORTED_CONTENT_TYPE",
                        f"Content-Type {content_type} not supported",
                        details={"content_type": content_type},
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
                final_url = str(resp.url)

    except httpx.TimeoutException:
        raise create_error("FETCH_FAILED", "Request timed out", details={"timeout": settings.fetch_timeout_seconds})
    except httpx.RequestError as e:
        raise create_error("FETCH_FAILED", f"Request failed: {type(e).__name__}", details={"error": str(e)})

    # Decode content
    try:
        text_content = content.decode("utf-8", errors="replace")
    except UnicodeDecodeError:
        text_content = content.decode("latin-1", errors="replace")

    # Parse based on content type
    if content_type.startswith("text/plain"):
        title = urlparse(final_url).hostname or "Untitled"
        return FetchedPage(title=title, text=text_content.strip(), final_url=final_url)

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