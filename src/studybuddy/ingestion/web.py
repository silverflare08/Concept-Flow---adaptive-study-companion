"""Safe remote fetching and source-cited web-page ingestion."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .models import CitationAnchor, EvidenceKind, SourceSegment, SourceType

MAX_REMOTE_BYTES = 50 * 1024 * 1024


def validate_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Enter a complete public http:// or https:// URL.")
    try:
        default_port = 443 if parsed.scheme == "https" else 80
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or default_port)}
    except socket.gaierror as error:
        raise ValueError("The website address could not be found.") from error
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
        if not ip.is_global:
            raise ValueError("Private, local and reserved network addresses are not allowed.")
    return url


class _PublicRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        validate_public_url(urljoin(req.full_url, newurl))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@dataclass(frozen=True)
class RemoteResource:
    content: bytes
    content_type: str
    final_url: str
    filename: str


def fetch_public_resource(url: str, *, max_bytes: int = MAX_REMOTE_BYTES) -> RemoteResource:
    validate_public_url(url)
    request = Request(url, headers={"User-Agent": "ConceptFlow/0.1 educational material importer"})
    with build_opener(_PublicRedirectHandler()).open(request, timeout=30) as response:  # nosec B310 - validated public URL
        final_url = validate_public_url(response.geturl())
        length = response.headers.get("Content-Length")
        if length and int(length) > max_bytes:
            raise ValueError("That remote file is larger than the 50 MB URL-import limit.")
        content = response.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise ValueError("That remote file is larger than the 50 MB URL-import limit.")
        content_type = response.headers.get_content_type().lower()
    filename = Path(urlparse(final_url).path).name or "web-page.html"
    return RemoteResource(content=content, content_type=content_type, final_url=final_url, filename=filename)


class _StudyHTMLParser(HTMLParser):
    block_tags = {"p", "li", "pre", "blockquote", "td", "th"}
    heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__()
        self.skip_depth = 0
        self.active_tag: str | None = None
        self.buffer: list[str] = []
        self.section = "web page"
        self.blocks: list[tuple[str, str]] = []
        self.title = ""

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1
        elif not self.skip_depth and tag in self.block_tags | self.heading_tags | {"title"}:
            self.active_tag, self.buffer = tag, []

    def handle_data(self, data: str) -> None:
        if not self.skip_depth and self.active_tag:
            self.buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth or tag != self.active_tag:
            return
        text = " ".join(" ".join(self.buffer).split())
        if text:
            if tag == "title":
                self.title = text
            elif tag in self.heading_tags:
                self.section = text
            else:
                self.blocks.append((self.section, text))
        self.active_tag, self.buffer = None, []


def ingest_web_page(
    html: bytes, *, source_id: str, source_name: str, source_uri: str,
) -> tuple[str, list[SourceSegment]]:
    parser = _StudyHTMLParser()
    parser.feed(html.decode("utf-8", errors="replace"))
    display_name = parser.title or source_name
    segments = [SourceSegment(
        text=text,
        citation=CitationAnchor(
            source_id=source_id, source_name=display_name, source_type=SourceType.WEB,
            source_uri=source_uri, section=section,
        ),
        evidence_kind=EvidenceKind.TEXT,
    ) for section, text in parser.blocks if len(text.split()) >= 3]
    if not segments:
        raise ValueError("No readable study text was found on that web page.")
    return display_name, segments


def is_youtube_url(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return hostname in {"youtube.com", "m.youtube.com", "youtu.be", "music.youtube.com"}
