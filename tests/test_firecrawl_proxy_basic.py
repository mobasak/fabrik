"""Every Firecrawl scrape or crawl instruction in the command corpus pins `proxy: "basic"` (W-10146d20, D-1100/D-1101).

Firecrawl's default proxy mode is `auto`, which retries a blocked page through its stealth proxies at a higher credit
price; the spec's § Fallback contract allows only the basic proxy until a tested slice-1d check of the proxy it used.

The rule is strict and literal, fail-closed by design:
- A MENTION is any match of `MENTION`; its CLAUSE runs from the mention to the next `END` match outside a code span,
  with line wraps collapsed first by `WRAP` (double-backtick spans masked before single ones). A newline `WRAP` keeps
  — a blank line, or one that opens a list item, table row, heading, quote or fence — ends the clause.
- A clause PASSES only when it holds a `PIN` match and no `NEG` match, and no `OTHER` match sits anywhere in the
  mention's block — the text between blank lines around it, so a stealth retry before it, after a `;` or ` — `, or in
  a sub-item of the same list is the same instruction. The constants ARE the lists; this text names them rather than
  repeating them, so it cannot drift from the code.
The cost is a false red on a correct clause that negates something unrelated ("(not exa)"), names a word `OTHER`
holds, or holds a `.` that `END` reads as a clause end (a URL, an abbreviation other than e.g., i.e., cf., vs. and
etc.); its remedy is rewording that one clause, which the failure message says. A false red costs a rewrite; a false
green ships an unpinned call.

Cobra note: this guards PRESENCE against regression. Natural-language negation is unbounded, so the cheapest way to
satisfy the test without the outcome is a negation spelled outside `NEG` ("is optional"). The counter-measure is a
named check, not a longer list: every review of a change to a pinned clause in the scanned corpus (`CORPUS`) reads
that clause and states that it instructs the basic proxy. The failure message (`REMEDY`) and this docstring
both say so.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORPUS = [
    p
    for d in ("_sources", "_agents", "_fragments")
    for p in sorted((ROOT / "commands" / d).glob("*.md"))
]

# a fetch verb in any inflection, never a lookalike ("ready", "scrapbook"); `read` only next to Firecrawl (W-ddb716ca:
# forty characters away it is a reader's "read" — "Firecrawl docs are easy to read")
_FETCH = (
    r"scrap(?:e|es|ed|ing|ers?)|(?:re-?)?crawl(?:s|ed|ing|ers?)?|retriev(?:e|es|ed|ing)"
    r"|fetch(?:es|ed|ing)?|re-fetch"
)
_VERB = r"(?:" + _FETCH + r"|read(?:s|ing)?)\b"
_FAR_VERB = r"(?:" + _FETCH + r")\b"
MENTION = re.compile(
    r"firecrawl_(?:\w*scrape|crawl)\b|mcp__firecrawl__\*"
    r"|\bfirecrawl(?:['’]s)?[\s-]+(?:\w+\s+){0,2}?(?:" + _VERB + r")"
    r"|\b(?:" + _VERB + r")\s+(?:\S+\s+){0,5}?(?:with|via|through|using|by|from|at)\s+firecrawl\b"
    r"|\bfirecrawl\w*(?:\(\))?\.\s*(?:scrap|crawl)\w*"
    r"|\bfirecrawl\b(?=[^.;→\n]{0,60}`maxAge)"
    r"|\bfirecrawl\b(?=[^.;→\n]{0,40}\b(?:" + _FAR_VERB + r"))",
    re.I,
)
PIN = re.compile(r"""["']?proxy["']?\s*[:=]\s*["']basic["']""")
OTHER = re.compile(
    r"\b(?:stealth|auto|automatic|enhanced)\b|\bdefault\s+proxy\b|\bproxy\s+default\b", re.I
)
NEG = re.compile(
    r"\b(?:never|not|no|nor|neither|without|instead|drop\w*|omit\w*|unless|avoid\w*|skip\w*|except|cannot)\b"
    r"|n['’]t\b",
    re.I,
)
END = re.compile(
    r"(?<!\be\.g)(?<!\bi\.e)(?<!\bcf)(?<!\bvs)(?<!\betc)(?<!\d)\.(?![a-z]\.)|(?<=\d)\.(?!\d)|[;→\n]|\s—\s"
)
BLANK = re.compile(r"\n[ \t]*\n")
# A newline is a wrap (joined into one line) unless the next line is blank or opens a block of its own.
WRAP = re.compile(r"(?<!```)(?<!\n)[ \t]*\n(?![ \t]*(?:\n|[-*+]\s|\||#|>|\d+[.)]\s|```))[ \t]*")

REMEDY = (
    'Each listed clause needs the literal `proxy: "basic"`, no word from NEG and none from OTHER - reword the clause, '
    "never the list. A review of any change to a pinned clause reads it and states that it instructs the basic proxy."
)

FIXTURES = {
    # pass
    '`firecrawl_scrape` with `maxAge: 0` and `proxy: "basic"`.': 0,
    '`firecrawl_crawl` with `"proxy": "basic"` in scrapeOptions.': 0,
    "`firecrawl_scrape` with `proxy: 'basic'`.": 0,
    '`firecrawl_scrape` (e.g. a docs page) with `proxy: "basic"`.': 0,
    '`firecrawl_scrape` on v2.1 pages with `proxy: "basic"`.': 0,
    "`mcp__firecrawl__firecrawl_search` for a query.": 0,
    're-fetch the page with Firecrawl scrape and `proxy: "basic"`.': 0,
    # fail: pin missing, elsewhere, negated or replaced
    '`firecrawl_scrape` with `maxAge: 0`. Later: `proxy: "basic"`.': 1,
    '`firecrawl_scrape` but never `proxy: "basic"`.': 1,
    '`firecrawl_scrape` with `maxAge: 0` and without `proxy: "basic"`.': 1,
    '`firecrawl_scrape` with no `proxy: "basic"`.': 1,
    '`firecrawl_scrape` with `proxy: "stealth"` instead of `proxy: "basic"`.': 1,
    'use ``a`b`` here. `firecrawl_scrape` with `maxAge: 0`. Later `proxy: "basic"`.': 1,
    '`firecrawl_scrape` must never, under any circumstance at all, carry `proxy: "basic"`.': 1,
    '`firecrawl_scrape` with `proxy: "basic"` is not needed.': 1,
    '`firecrawl_scrape` with `proxy: "basic"` never set.': 1,
    '`firecrawl_scrape` on plan A. Later `proxy: "basic"`.': 1,
    '`firecrawl_scrape` on attempt 2. Later `proxy: "basic"`.': 1,
    # fail by design: a negation in the clause, even an unrelated one (reword the clause)
    '`firecrawl_scrape` (not exa) with `proxy: "basic"`.': 1,
    '`firecrawl_scrape` with no cache and `proxy: "basic"`.': 1,
    '`firecrawl_scrape` with `proxy: "basic"` (never `proxy: "auto"`).': 1,
    # mentions in every spelling, unpinned
    "settled by firecrawl `maxAge: 0`, else the verdict": 1,
    "settled by firecrawl\n  `maxAge: 0`, else the verdict": 1,
    "firecrawl (with `maxAge: 0`) is that read": 1,
    "a Firecrawl scrape with `maxAge: 0`": 1,
    "`firecrawl_batch_scrape` over the list": 1,
    "re-fetch the page with Firecrawl scrape (a live fetch).": 1,
    # negations and modes in other words
    '`firecrawl_scrape` cannot take `proxy: "basic"`.': 1,
    '`firecrawl_scrape` doesn\'t need `proxy: "basic"`.': 1,
    '`firecrawl_scrape` doesn’t need `proxy: "basic"`.': 1,
    '`firecrawl_scrape` with `maxAge: 0`, skipping `proxy: "basic"`.': 1,
    '`firecrawl_scrape` must avoid `proxy: "basic"`.': 1,
    '`firecrawl_scrape` with `proxy: "basic"` except on a retry.': 1,
    '`firecrawl_scrape` with neither `maxAge: 0` nor `proxy: "basic"`.': 1,
    '`firecrawl_scrape` with `proxy: "basic"`, or the stealth proxy on a retry.': 1,
    '`firecrawl_scrape` with `proxy: "basic"` and then auto mode if it fails.': 1,
    '`firecrawl_scrape` with `proxy: "basic"` omitted.': 1,
    '`firecrawl_scrape` with `proxy: "basic"` dropped.': 1,
    '`firecrawl_scrape` avoiding `proxy: "basic"`.': 1,
    # a block boundary ends the clause: a pin in the next list item, table row, paragraph or after a fence is no pin
    '- `firecrawl_scrape` with `maxAge: 0`\n- exa with `proxy: "basic"`.': 1,
    '| `firecrawl_scrape` | `maxAge: 0` |\n| exa | `proxy: "basic"` |': 1,
    '## Use `firecrawl_scrape`\n\nThen set `proxy: "basic"` on exa.': 1,
    '```\nfirecrawl_scrape(url, maxAge=0)\n```\nLater use `proxy: "basic"`.': 1,
    '`firecrawl_scrape` with `maxAge: 0`\n  and `proxy: "basic"`.': 0,
    # prose spellings of a scrape or crawl, any case
    "Firecrawl scrapes the page.": 1,
    "Firecrawl crawls the site.": 1,
    "Firecrawl's scrape endpoint returns markdown.": 1,
    "scrape the page with Firecrawl.": 1,
    "FIRECRAWL scrape it.": 1,
    "a Firecrawl-scrape call.": 1,
    "Firecrawl (the tier-2 arm beside exa, re-wired 2026-09-23) with `maxAge: 0`": 1,
    'Firecrawl scrapes the page with `proxy: "basic"`.': 0,
    'scrape the page with Firecrawl and `proxy: "basic"`.': 0,
    # abbreviations and the keyword form a pinned clause may carry
    '`firecrawl_scrape` on docs, vs. exa, with `proxy: "basic"`.': 0,
    '`firecrawl_scrape` on pages, PDFs etc. with `proxy: "basic"`.': 0,
    '`firecrawl_scrape(url, proxy="basic")`.': 0,
    # out of scope: other Firecrawl tools, search, and crawl/scrape words about other systems
    "`firecrawl_extract` the fields.": 0,
    "Firecrawl search for the page.": 0,
    "exa serves a crawl cache, and a page firecrawl serves live is not dead.": 0,
    "Prometheus scrapes the metrics.": 0,
    # a forbidden mode later in the same paragraph is the same instruction
    '`firecrawl_scrape` with `proxy: "basic"`; on a block, retry with `proxy: "stealth"`.': 1,
    '`firecrawl_scrape` with `proxy: "basic"` — on a block, retry through the stealth proxy.': 1,
    '`firecrawl_scrape` with `proxy: "basic"`, falling back to the default proxy on a block.': 1,
    '`firecrawl_scrape` with `proxy: "basic"`.\n\nThe stealth proxy is for other tools.': 0,
    # a fetch verb after Firecrawl is a mention
    "Use Firecrawl to read the page with the stealth proxy.": 1,
    'Use Firecrawl to read the page with `proxy: "basic"`.': 0,
    # the mode check covers the whole block: before the mention, and a sub-item of the same list
    'If the page blocks, switch to the stealth proxy after `firecrawl_scrape` with `proxy: "basic"`.': 1,
    'On a block use `proxy: "stealth"`; first `firecrawl_scrape` with `proxy: "basic"`.': 1,
    '- `firecrawl_scrape` with `proxy: "basic"`.\n  - on a block, retry with the stealth proxy.': 1,
    '1) `firecrawl_scrape` with `proxy: "basic"` on the first try,\n2) then the stealth proxy on a block.': 1,
    '`firecrawl_scrape` with `proxy: "basic"`; on a block, retry in automatic mode.': 1,
    # more spellings of a Firecrawl fetch
    "scrape it using Firecrawl.": 1,
    "Scrape the page by Firecrawl.": 1,
    "call `FirecrawlApp().scrape_url(url)` here.": 1,
    "call `firecrawl.scrape(url)` here.": 1,
    # lookalike words are no fetch verb
    "Firecrawl is ready for the call.": 0,
    "the Firecrawl scrapbook of notes.": 0,
    "Run Firecrawl crawlers over the site.": 1,
    "Point Firecrawl scrapers at the docs.": 1,
    # W-ddb716ca: three more spellings of a Firecrawl fetch, and a reader's "read" that is none
    "Firecrawl recrawls the docs nightly.": 1,
    "Firecrawl retrieves the page for the seat.": 1,
    "Point the scrapers at Firecrawl via its API.": 1,
    "Firecrawl docs are easy to read.": 0,
}


def _collapse(s: str) -> str:
    return WRAP.sub(" ", s)


def _mask(s: str) -> str:
    """Blank code spans (a fence is caught by the double-backtick form); a newline inside stays a newline."""
    return re.sub(r"``.*?``|`[^`\n]*`", lambda m: re.sub(r"[^\n]", "x", m.group(0)), s, flags=re.S)


def _clause(text: str, start: int) -> str:
    m = END.search(_mask(text), start)
    return text[start : m.start() if m else len(text)]


def _block(text: str, at: int) -> str:
    """The text between the blank lines around offset `at` (a blank line survives `_collapse`)."""
    starts = [m.end() for m in BLANK.finditer(text, 0, at)]
    end = BLANK.search(text, at)
    return text[starts[-1] if starts else 0 : end.start() if end else len(text)]


def _failing_offsets(raw: str) -> list[int]:
    """Offsets, in the collapsed text, of mentions whose clause fails the literal rule."""
    text = _collapse(raw)
    bad = []
    for m in MENTION.finditer(text):
        cl = _clause(text, m.start())
        if not PIN.search(cl) or NEG.search(cl) or OTHER.search(_block(text, m.start())):
            bad.append(m.start())
    return bad


def _line_of(raw: str, offset: int) -> int:
    """Map an offset in the collapsed text back to its 1-based source line.

    `_collapse` replaces each `WRAP` match with one space and copies everything between matches unchanged, so the
    text between matches maps one to one; walk the matches to the segment that holds `offset`.
    """
    coll, pos = 0, 0
    for m in WRAP.finditer(raw):
        seg = m.start() - pos
        if offset < coll + seg:
            break
        if offset == coll + seg:  # the joining space itself sits where the wrap began
            return raw.count("\n", 0, m.start()) + 1
        coll += seg + 1
        pos = m.end()
    return raw.count("\n", 0, pos + (offset - coll)) + 1


def _violations(corpus: list[Path]) -> list[str]:
    return [
        f"{path.relative_to(ROOT) if path.is_relative_to(ROOT) else path.name}:{_line_of(raw, off)}"
        for path in corpus
        for raw in [path.read_text(encoding="utf-8")]
        for off in _failing_offsets(raw)
    ]


def _message(rows: list[str]) -> str:
    return REMEDY + "\n" + "\n".join(rows)


@pytest.mark.parametrize(("text", "want"), list(FIXTURES.items()))
def test_the_rule_judges_each_fixture_as_listed(text: str, want: int) -> None:
    assert len(_failing_offsets(text)) == want


def test_every_firecrawl_scrape_or_crawl_instruction_pins_the_basic_proxy() -> None:
    assert any(MENTION.search(_collapse(p.read_text(encoding="utf-8"))) for p in CORPUS), (
        "no Firecrawl scrape or crawl mention found — the corpus moved; re-point this grader"
    )
    rows = _violations(CORPUS)
    assert rows == [], _message(rows)


def test_a_red_result_carries_the_remedy_and_names_the_line(tmp_path: Path) -> None:
    bad = tmp_path / "bad.md"
    bad.write_text("intro\nUse `firecrawl_scrape` with `maxAge: 0`.\n", encoding="utf-8")
    rows = _violations([bad])
    assert rows == ["bad.md:2"]
    message = _message(rows)
    assert REMEDY in message and "bad.md:2" in message
