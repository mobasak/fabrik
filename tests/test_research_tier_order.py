"""Every command source wires web research in the operator's two-tier order (D-337, decided for the commands by
D-845): tier 1 (`WebSearch` / `WebFetch` / brave) first, the metered `exa` and `firecrawl` searches only on a
tier-1 miss.

The property runs over the whole corpus, so a new command that opens its chain with exa fails here, not in review.
Cobra note: the cheapest way to satisfy a loose check is to write "on a miss" beside an exa-first chain, or to name
an unrelated `WebSearch` nearby, or to wrap prose in backticks; so the check reads ONE chain — from a tier-1
engine to the miss marker only further TIER-1 engines (a closed set) and their `→` / `/` / `,` separators, an
"official-docs" label allowed — requires the marker directly before exa, and refuses a firecrawl search chained
after exa by its own arrow (it is tier 2 too, gated by the same miss).
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = sorted((ROOT / "commands" / "_sources").glob("*.md")) + sorted(
    (ROOT / "commands" / "_fragments").glob("*.md")
)
EXA = "`mcp__exa__web_search_exa`"
FIRECRAWL = "`mcp__firecrawl__firecrawl_search`"
_TIER1 = r"(?:`WebSearch`|`WebFetch`|`mcp__brave-search__brave_web_search`)"
# a tier-1 search engine, then only further tier-1 engines in the same chain, then the miss marker right before exa
_LADDER = re.compile(
    r"(?:`WebSearch`|`mcp__brave-search__brave_web_search`)"
    r"(?: ?[→/,] ?(?:official-docs )?" + _TIER1 + r")*"
    r" ?[→/,] on a miss $"
)


def _flat(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


def _violations(corpus: list[Path]) -> list[str]:
    bad = []
    sites = 0
    for path in corpus:
        text = _flat(path)
        for m in re.finditer(re.escape(EXA), text):
            sites += 1
            if not _LADDER.search(text[max(0, m.start() - 240) : m.start()]):
                bad.append(f"{path.name}: exa not reached from tier 1 on a miss in one clause")
            if re.match(r"\s*→\s*" + re.escape(FIRECRAWL), text[m.end() : m.end() + 60]):
                bad.append(f"{path.name}: firecrawl search chained after exa by its own arrow")
    assert sites, "no exa search site found — the corpus moved; re-point this grader"
    return bad


def test_every_exa_search_in_the_corpus_comes_after_tier_one_on_a_miss() -> None:
    assert _violations(CORPUS) == []


def test_the_check_refuses_the_shapes_a_loose_check_would_pass(tmp_path: Path) -> None:
    shapes = {
        "first.md": f"live research: {EXA} → `WebSearch` → `mcp__brave-search__brave_web_search`.",
        "decoy.md": f"Use `WebSearch` for unrelated lookups. Then treat a stale cache as on a miss {EXA} → x.",
        "comma.md": f"Earlier `WebSearch` was tried elsewhere, unrelated to this chain, on a miss {EXA} → x.",
        "codespan.md": f"`WebSearch` → `prose in a code span, not a tool` → on a miss {EXA} → x.",
        "chained.md": f"`WebSearch` → `mcp__brave-search__brave_web_search` → on a miss {EXA} → {FIRECRAWL}.",
    }
    paths = []
    for name, body in shapes.items():
        (tmp_path / name).write_text(body, encoding="utf-8")
        paths.append(tmp_path / name)
    found = _violations(paths)
    assert len([v for v in found if v.startswith("first.md")]) == 1
    assert len([v for v in found if v.startswith("decoy.md")]) == 1
    assert len([v for v in found if v.startswith("comma.md")]) == 1
    assert len([v for v in found if v.startswith("codespan.md")]) == 1
    assert [v for v in found if v.startswith("chained.md")] == [
        "chained.md: firecrawl search chained after exa by its own arrow"
    ]
