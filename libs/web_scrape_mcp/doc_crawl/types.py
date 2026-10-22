"""Shared dataclasses + enums for doc-crawl (vendor this folder, don't import)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PageType(str, Enum):
    """Coarse page classification (LLM-free)."""

    GUIDE = "guide"
    API_ENDPOINT = "api_endpoint"
    OVERVIEW = "overview"
    CHANGELOG = "changelog"
    PRICING = "pricing"
    AUTH = "auth"
    ERROR = "error"
    OTHER = "other"


@dataclass(frozen=True)
class CrawlProfile:
    """How to crawl one doc site. Generic — no per-vendor logic."""

    start_urls: list[str]
    # empty -> derived from start_urls' hosts.
    allowed_domains: list[str] = field(default_factory=list)
    # CSS selectors whose links are visited first (crawl-order priority only).
    nav_selectors: list[str] = field(
        default_factory=lambda: [
            "nav",
            "aside",
            ".sidebar",
            "[role=navigation]",
            ".toc",
        ]
    )
    skip_extensions: tuple[str, ...] = (
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".webp",
        ".ico",
        ".css",
        ".js",
        ".mjs",
        ".woff",
        ".woff2",
        ".ttf",
        ".zip",
        ".gz",
        ".tar",
        ".mp4",
        ".mp3",
        ".wasm",
    )
    max_depth: int = 5
    max_pages: int = 500
    strip_query: bool = True


@dataclass
class ClassifyResult:
    is_doc: bool
    score: float
    page_type: PageType


@dataclass
class DocPage:
    """One crawled, classified, markdown-rendered page."""

    url: str
    depth: int
    html: str
    markdown: str
    content_hash: str
    classify: ClassifyResult
    links: list[str]
