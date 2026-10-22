"""HTML → markdown: strip site chrome, keep heading hierarchy + code/lists/links.

bs4 + lxml. A recursive renderer emits each block once (no get_text duplication
from nested blocks).
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString

__all__ = ["html_to_markdown", "strip_chrome"]

# Inline tags whose text belongs to the surrounding sentence (merged into one
# paragraph), not emitted as its own block.
_INLINE_TAGS = {
    "a",
    "span",
    "strong",
    "em",
    "b",
    "i",
    "code",
    "small",
    "sup",
    "sub",
    "abbr",
    "time",
    "mark",
    "kbd",
    "u",
    "s",
    "cite",
    "q",
    "var",
    "samp",
    "label",
}

_REMOVE_TAGS = [
    "nav",
    "header",
    "footer",
    "aside",
    "script",
    "style",
    "noscript",
    "svg",
    "img",
    "form",
    "button",
    "iframe",
    "template",
    "input",
    "select",
]
_CHROME_RE = re.compile(
    r"(?:^|[-_ ])(nav|menu|sidebar|footer|header|cookie|banner|breadcrumb|toc|promo|advert|ad)(?:[-_ ]|$)",
    re.I,
)
_HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
_BLOCK_DESCENDANTS = [
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "ul",
    "ol",
    "pre",
    "blockquote",
    "table",
]


def strip_chrome(soup: BeautifulSoup) -> Tag:
    """Remove nav/header/footer/script/etc. + chrome-class/id elements; return the
    content root (<body> if present).
    """
    for tag in soup.find_all(_REMOVE_TAGS):
        tag.decompose()
    for tag in soup.find_all(class_=_CHROME_RE):  # class_/id kwargs accept a regex
        if isinstance(tag, Tag):
            tag.decompose()
    for tag in soup.find_all(id=_CHROME_RE):
        if isinstance(tag, Tag):
            tag.decompose()
    body = soup.body
    return body if isinstance(body, Tag) else soup


def _render(node: Tag, out: list[str]) -> None:
    # Bare text and inline tags (text, links, <code>…) are accumulated into one
    # paragraph and flushed when a block-level element interrupts them, so prose
    # that introduces a list/code block ("To install, run:") is not lost.
    inline: list[str] = []

    def flush() -> None:
        if inline:
            text = " ".join(inline).strip()
            if text:
                out.append(text)
            inline.clear()

    for child in node.children:
        if isinstance(child, NavigableString):
            text = str(child).strip()
            if text:
                inline.append(text)
            continue
        if not isinstance(child, Tag):
            continue
        name = child.name
        if name in _HEADINGS:
            flush()
            text = child.get_text(" ", strip=True)
            if text:
                out.append("#" * _HEADINGS[name] + " " + text)
        elif name == "p":
            flush()
            text = child.get_text(" ", strip=True)
            if text:
                out.append(text)
        elif name in ("ul", "ol"):
            flush()
            for li in child.find_all("li", recursive=False):
                text = li.get_text(" ", strip=True)
                if text:
                    out.append("- " + text)
        elif name == "pre":
            flush()
            text = child.get_text("\n", strip=True)
            if text:
                out.append("```\n" + text + "\n```")
        elif name == "blockquote":
            flush()
            text = child.get_text(" ", strip=True)
            if text:
                out.append("> " + text)
        elif name == "table":
            flush()
            for tr in child.find_all("tr"):
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                if any(cells):
                    out.append(" | ".join(cells))
        elif name in _INLINE_TAGS:
            text = child.get_text(" ", strip=True)  # part of the surrounding sentence
            if text:
                inline.append(text)
        elif child.find(_BLOCK_DESCENDANTS) is not None:
            flush()
            _render(child, out)  # container with block children -> recurse
        else:
            flush()
            text = child.get_text(" ", strip=True)  # leaf container with bare text
            if text:
                out.append(text)
    flush()


def html_to_markdown(html: str) -> str:
    """Render `html` to markdown after stripping site chrome. Empty string if no body."""
    soup = BeautifulSoup(html, "lxml")
    root = strip_chrome(soup)
    out: list[str] = []
    _render(root, out)
    md = "\n\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", md).strip()
