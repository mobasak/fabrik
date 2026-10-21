"""LLM-free page classification: is this a doc/content page, and what kind?

4 layers (URL hard-kills → meta noindex → structural scoring → threshold), plus
a coarse PageType from URL/title. Generalized from apidoccreator's page_classifier.
"""

from __future__ import annotations

from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from .types import ClassifyResult, PageType

__all__ = ["classify_page", "DOC_THRESHOLD"]

DOC_THRESHOLD = 0.35

# Path SEGMENTS that are never doc content. Matched exactly against split("/")
# segments (not substrings) so e.g. "/docs/legal-entities" is NOT killed by "legal".
_HARD_KILL = frozenset(
    {
        "login",
        "signin",
        "sign-in",
        "signup",
        "sign-up",
        "register",
        "logout",
        "cart",
        "checkout",
        "account",
        "privacy",
        "terms",
        "cookie",
        "cookies",
        "legal",
        "unsubscribe",
    }
)
_DOC_HINTS = ("/docs", "/doc/", "/guide", "/reference", "/api", "/tutorial", "/manual")


def _page_type(path: str, title: str) -> PageType:
    blob = f"{path} {title}".lower()
    if "changelog" in blob or "release-note" in blob or "release note" in blob:
        return PageType.CHANGELOG
    if "pricing" in blob or "/plans" in blob:
        return PageType.PRICING
    if any(
        k in blob for k in ("login", "auth", "token", "api-key", "api key", "oauth")
    ):
        return PageType.AUTH
    if "/api" in path or "/reference" in path or "endpoint" in blob:
        return PageType.API_ENDPOINT
    if any(k in path for k in ("/guide", "/tutorial", "/how-to", "/getting-started")):
        return PageType.GUIDE
    if (
        path in ("", "/", "/docs", "/docs/")
        or "overview" in blob
        or "introduction" in blob
    ):
        return PageType.OVERVIEW
    return PageType.OTHER


def classify_page(url: str, html: str) -> ClassifyResult:
    """Return (is_doc, score in [0,1], PageType). Pure — no I/O."""
    path = urlparse(url).path.lower()
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.get_text(strip=True) if soup.title else "") or ""

    # Layer 1: URL hard-kills (exact path-segment match, not substring).
    if _HARD_KILL & set(path.split("/")):
        return ClassifyResult(False, 0.0, _page_type(path, title))

    # Layer 2: meta robots noindex.
    robots = soup.find("meta", attrs={"name": "robots"})
    if isinstance(robots, Tag):
        content = robots.get("content")
        if isinstance(content, str) and "noindex" in content.lower():
            return ClassifyResult(False, 0.0, _page_type(path, title))

    # Layers 3-4: structural scoring.
    root = soup.body if isinstance(soup.body, Tag) else soup
    score = 0.0
    if root.find_all("h1"):
        score += 0.10
    if root.find_all(["h2", "h3", "h4"]):
        score += 0.05
    if len(root.find_all("p")) >= 3:
        score += 0.10

    words = len(root.get_text(" ", strip=True).split())
    if words >= 100:
        score += 0.10
    if words >= 300:
        score += 0.10
    if words >= 600:
        score += 0.05
    if root.find_all(["pre", "code"]):
        score += 0.10

    link_count = len(root.find_all("a"))
    density = link_count / max(words, 1)
    if density <= 0.25:
        score += 0.05
    if density <= 0.10:
        score += 0.05
    if any(hint in path for hint in _DOC_HINTS):
        score += 0.05

    score = round(min(score, 1.0), 3)
    return ClassifyResult(score >= DOC_THRESHOLD, score, _page_type(path, title))
