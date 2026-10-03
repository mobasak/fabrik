"""Pins `ai/90-long-context.md` to the rules its 2026-10-03 currency pass set.

The pack is glob-activated on long-context, codebase-analysis and document-QA paths (no fleet directory matches today;
it is read by citation from ai/00's category table). Eight things it states can go false with no other gate red:

1. Its frontmatter carries `currency_pass:` and `Last content verification:` parses, and the machine-written
   OPENROUTER_ROUTES block survives with both markers.
2. Model choice is ai/00's: Claude by alias, no model generation named, and a window size is never the reason to pick a
   model.
3. The advertised window is not the usable window, and the task is measured at the length it will run.
4. Long inputs are curated and ordered: documents first, question last, quotes before the answer.
5. Retrieval is the default when a corpus outgrows one document, and the choice is scored on the project's questions.
6. Long runs compact early, keep durable rules in files, and the cache cost of clearing tool results is stated.
7. A codebase is analysed by agentic search; a semantic index only on a measured lift.
8. Repeated long prefixes are cached, price steps are named, input is sized in tokens; no retired route (Kilo, Traycer)
   and no version number in any shape in the prose (the detector `tests/test_vision_pack.py` defines).

Guards read emphasis-stripped, whitespace-collapsed text and pin the clause that carries the force, so a reversed verb
fails. The cheapest way past (2) is naming a model generation in words the detector does not see ("the latest Opus");
the alias rule names `opus` and `fable` and ai/00 owns the table, so a generation name has nowhere to hide its value.
"""

from __future__ import annotations

import importlib.util
import re
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
PACK = RULES / "ai" / "90-long-context.md"
FRESH = ROOT / "scripts" / "check_ai_pack_freshness.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[`*]|(?<!\w)_|_(?!\w)", "", text))


def _pack() -> str:
    return PACK.read_text(encoding="utf-8")


def _prose() -> str:
    body = _pack().split("\n---\n", 1)[1]
    head, _, rest = body.partition("<!-- OPENROUTER_ROUTES:START")
    return head + rest.split(":END -->", 1)[1]


def _bullet(label: str) -> str:
    body = _pack().split("\n## Fabrik defaults\n", 1)[1].split("\n**Anti-pattern:**", 1)[0]
    return next(
        (_plain(b) for b in body.split("\n- ")[1:] if label.lower() in _plain(b)[:80].lower()), ""
    )


def test_stamps() -> None:
    head = _pack().split("---", 2)[1]
    assert re.search(r"^currency_pass: \d{4}-\d{2}-\d{2}$", head, re.M), (
        "the pack lost its currency_pass stamp"
    )
    status, age, msg = _load("fresh90", FRESH).check_pack(PACK, date(2026, 10, 3))
    assert status == "fresh" and age == 0, (
        f"the freshness checker no longer parses the pack's stamp: {msg}"
    )


def test_routes_block_survives() -> None:
    pack = _pack()
    start, end = (
        pack.find("<!-- OPENROUTER_ROUTES:START"),
        pack.find("<!-- OPENROUTER_ROUTES:END -->"),
    )
    assert start != -1 and end > start, (
        "the OPENROUTER_ROUTES markers are gone: its generator can no longer write it"
    )


def test_model_choice_is_ai00s() -> None:
    b = _bullet("Model choice is ai/00's")
    assert b, "the model-choice rule is gone"
    for phrase in (
        "this pack names no model generation",
        "Select Claude by alias: opus for long-context work, fable only when opus measurably falls short",
        "ai/00-ai-model-selection.md",
        "haiku's is smaller",
        "A window size is never the reason to pick a model",
    ):
        assert phrase in b, f"the model-choice rule lost: {phrase!r}"


def test_usable_window() -> None:
    b = _bullet("The advertised window is not the usable window")
    assert b, "the usable-window rule is gone"
    for phrase in (
        "Accuracy falls as input grows, well inside the advertised length",
        "11 of 13 models that claim 128K tokens fell below half their short-input score at 32K",
        "every token is a cost to accuracy",
        "cost about 14% to 85% of accuracy even when the evidence was retrieved perfectly",
        "measure the task at the input length you will actually send, and send less when the score drops",
    ):
        assert phrase in b, f"the usable-window rule lost: {phrase!r}"


def test_curate_and_order() -> None:
    b = _bullet("Curate before you stuff")
    assert b, "the curate-and-order rule is gone"
    for phrase in (
        "the smallest set of high-signal tokens that does the job",
        "put the documents at the top and the question last",
        "wrap each document in its own tags with its source",
        "ask the model to quote the relevant passages before it answers",
        "put the instructions both before and after the context",
    ):
        assert phrase in b, f"the curate-and-order rule lost: {phrase!r}"


def test_retrieval_default() -> None:
    b = _bullet("Retrieval beats a full context on cost")
    assert b, "the retrieval rule is gone"
    for phrase in (
        "Default to retrieval (core/65-rag-search.md",
        "when the corpus is more than one document or the same corpus answers many questions",
        "Decide on the project's own questions, scored both ways",
    ):
        assert phrase in b, f"the retrieval rule lost: {phrase!r}"


def test_long_runs_compact_early() -> None:
    b = _bullet("Long conversations and agent runs")
    assert b, "the long-run rule is gone"
    for phrase in (
        "compact before the window fills",
        "keep rules that must survive compaction in files",
        "A fresh session with a better prompt beats a long one carrying corrections",
        "compacts only at about 967K tokens by default; set autoCompactWindow",
        "Clearing tool results invalidates the cached prompt prefix",
        "or CLAUDE_CODE_AUTO_COMPACT_WINDOW for headless claude -p runs",
        "cached tokens still fill the window",
    ):
        assert phrase in b, f"the long-run rule lost: {phrase!r}"


def test_codebase_by_agentic_search() -> None:
    b = _bullet("Analyse a codebase by agentic search")
    assert b, "the codebase rule is gone"
    assert "Analyse a codebase by agentic search, not by loading it whole" in b
    assert "semantic search beside grep raised Cursor's average accuracy (+12.5%)" in b, (
        "the measured lift behind the index rule is gone"
    )
    assert "add one only when a test on the project shows the lift" in b, (
        "the semantic index is no longer gated"
    )


def test_cost_rules() -> None:
    b = _bullet("Pay once for a long prefix")
    assert b, "the cost rule is gone"
    for phrase in (
        "caching pays after one read on the five-minute cache and after two on the one-hour cache",
        "which shows as zero cache-write and zero cache-read tokens on the call",
        "a prompt below the model's minimum length is silently not cached",
        "Claude bills its whole 1M window at the standard per-token rate",
        "charge a higher rate for every token once a prompt passes a size step (200K and 272K tokens respectively)",
        "Offline jobs go through the batch APIs at half price",
        "Size input in tokens with the provider's own counter, never in words",
    ):
        assert phrase in b, f"the cost rule lost: {phrase!r}"


def test_open_weight_licence_traps() -> None:
    sub = _plain(_pack().split("\n## Subcategories\n", 1)[1].split("\n**Use cases:**", 1)[0])
    assert "MiniMax's (non-commercial without MiniMax's written authorisation)" in sub, (
        "ai/90 no longer says MiniMax's weights are non-commercial"
    )
    assert "Kimi's (a modified MIT licence; 1M window)" in sub
    assert "Read the exact licence before use" in sub


@pytest.mark.parametrize("word", ["Kilo", "Traycer"])
def test_no_retired_routes(word: str) -> None:
    assert word not in _prose(), f"ai/90 names the retired route {word}"


def test_no_version_literals() -> None:
    found = _load("vision90", ROOT / "tests" / "test_vision_pack.py").VERSION_RE.findall(
        _plain(_prose())
    )
    assert not found, f"version literals in ai/90's prose: {found}"


def test_cited_packs_exist() -> None:
    for ref in set(re.findall(r"`((?:ai|core)/[\w-]+\.md)`", _pack())):
        assert (RULES / ref).is_file(), f"ai/90 cites {ref}, which does not exist"
