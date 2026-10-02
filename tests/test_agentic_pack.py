"""Pins `ai/50-agentic.md` to the agent loop the fleet actually runs, its bounds and its auth boundary.

The pack is glob-activated on agentic, reasoning, orchestration and multi-agent paths. Seven things it states can go
false with no other gate red:

1. The two machinery-owned blocks (GATEWAY_COUNTS, OPENROUTER_ROUTES) survive, and `Last content verification:` parses
   for `scripts/check_ai_pack_freshness.py`.
2. A workflow on a fixed code path comes before an agent, and agent loops run on Claude through `claude -p` and
   fabrik-lib's `llm-dispatch`, with no framework by default; the pack once offered OpenAI's o-series and AutoGPT.
3. Every loop is bounded: `max_turns`, a fixed tool set with MCP tools denied separately, `dontAsk`, strict MCP config,
   persisted sessions whose cost is cumulative.
4. Reasoning depth is effort, never a thinking budget, set on the CLI lane through `CLAUDE_CLI_EFFORT`.
5. The auth boundary: subscription OAuth, never `ANTHROPIC_API_KEY`, never bare mode; Anthropic's terms for products
   serving other users are stated and handed to the operator's open item.
6. The operational diagnose loop takes no per-call dollar cap; AutoGPT's platform licence is named as a trap; frameworks
   are gated on a recorded need, with AutoGen's maintenance mode stated.
7. No retired route or model (Kilo, Traycer, OpenAI's o-series and GPT-4 line) and no version number in any shape — the
   detector is the one `tests/test_vision_pack.py` defines — and every cited pack, item and fabrik-lib module exists.

Guards read structure (one bullet at a time, emphasis stripped, whole words) so a restyled line keeps its meaning — a
re-wrap, a dropped bold, a label arrow or colon — and each guard pins the clause that carries the rule's force, not only
its subject, so a reversed verb fails. The
cheapest way past (2) is a framework offered in prose outside the bullets the parser reads; the review reads the rest.
The cheapest way past (7) is a version in words; the detector catches the shapes agents copy.
"""

from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
PACK = RULES / "ai" / "50-agentic.md"
INDEX = RULES / "ai" / "00-ai-model-selection.md"
FRESH = ROOT / "scripts" / "check_ai_pack_freshness.py"
LIB = Path(os.environ.get("FABRIK_LIB_DIR", "/opt/fabrik-lib"))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pack() -> str:
    return PACK.read_text(encoding="utf-8")


def _plain(text: str) -> str:
    """Whitespace collapsed and emphasis stripped; an underscore inside a word stays."""
    return re.sub(r"\s+", " ", re.sub(r"[`*]|(?<!\w)_|_(?!\w)", "", text))


def _section(heading: str) -> str:
    text = _pack()
    start = text.index(f"\n## {heading}\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def _bullets(heading: str) -> list[str]:
    body = re.split(r"\n\*\*(?:Anti-pattern|Licence trap)", _section(heading), maxsplit=1)[0]
    return [_plain(b) for b in body.split("\n- ")[1:]]


def _bullet(heading: str, label: str) -> str:
    """The first bullet whose opening words contain the label (a restyled label still matches)."""
    return next((b for b in _bullets(heading) if label.lower() in b[:60].lower()), "")


def _paragraph(lead: str) -> str:
    """The bold-led paragraph after the defaults' bullets (Anti-pattern, Licence trap), emphasis stripped."""
    defaults = _section("Fabrik defaults")
    i = defaults.find(f"**{lead}")
    return _plain(defaults[i:].split("\n\n", 1)[0]) if i != -1 else ""


def _prose() -> str:
    body = _pack().split("\n---\n", 1)[1]
    for marker in ("<!-- GATEWAY_COUNTS:START", "<!-- OPENROUTER_ROUTES:START"):
        head, _, rest = body.partition(marker)
        body = head + rest.split(":END -->", 1)[1]
    return body


@pytest.mark.parametrize("block", ["GATEWAY_COUNTS", "OPENROUTER_ROUTES"])
def test_machinery_blocks_survive(block: str) -> None:
    pack = _pack()
    start, end = pack.find(f"<!-- {block}:START"), pack.find(f"<!-- {block}:END -->")
    assert start != -1 and end > start, (
        f"the {block} markers are gone: its generator can no longer write the block"
    )


def test_freshness_check_reads_the_stamp() -> None:
    mod = _load("freshchk_agentic", FRESH)
    # warn-only past its window: the pin is that the stamp PARSES on the script's own UTC clock, never that it is fresh
    status, _age, msg = mod.check_pack(PACK, mod._today())
    assert status != "unstamped", f"check_ai_pack_freshness.py cannot read the stamp: {msg}"


def test_workflow_first_and_the_claude_loop() -> None:
    workflow = _bullet("Fabrik defaults", "Workflow")
    assert re.match(r"Workflow before agent", workflow) and "fixed code path" in workflow, (
        "the defaults no longer put a workflow on a fixed code path before an agent"
    )
    loops = _bullet("Fabrik defaults", "Agent loops")
    # the default is what the bullet OPENS with, not a later mention
    assert re.match(r"Agent loops\s*(?::\s*→?|→)\s*Claude through claude -p", loops), (
        f"the agent-loop default changed: {loops[:70]!r}"
    )
    for needle in ("llm-dispatch", "run_agentic", "start_session", "json_schema", "§ Claude"):
        assert needle in loops, f"the agent-loop default no longer names {needle!r}"
    # ai/00 puts agentic work on opus and scopes its haiku-first ladder to single calls
    assert re.search(r"Agent loops run on opus", loops) and re.search(r"haiku-first ladder is for single calls", loops), (
        "the agent-loop rung no longer follows ai/00 (opus for loops, haiku for single calls)"
    )
    assert re.search(r"No agent framework by default", loops), "the loop default no longer refuses a framework"


def test_every_loop_is_bounded() -> None:
    bound = _bullet("Fabrik defaults", "Bound every loop")
    for needle in ("max_turns", "without a limit", "disallowed_tools", "dontAsk", "strict_mcp_config"):
        assert needle in bound, f"the loop bounds no longer name {needle!r}"
    # the emphasis stripper eats an underscore of `mcp__*`, so that token is read from the raw section
    assert "`mcp__*`" in _section("Fabrik defaults"), "the bounds no longer say how to remove every MCP tool"
    assert re.search(r"tools, which leaves MCP tools untouched", bound), (
        "the bounds no longer say `tools` leaves MCP tools in place"
    )
    assert re.search(r"resumes only a persisted session", bound) and re.search(r"rather than summing results", bound), (
        "the bounds lost the session rules (persisted to resume, read the session total)"
    )
    for needle in ("timeout_s", 'setting_sources=""', "DispatchError"):
        assert needle in bound, f"the loop bounds no longer name {needle!r}"


def test_reasoning_is_effort() -> None:
    effort = _bullet("Fabrik defaults", "Reasoning depth")
    assert re.match(r"Reasoning depth is effort, not a thinking budget", effort), (
        f"the reasoning default changed: {effort[:70]!r}"
    )
    assert "CLAUDE_CLI_EFFORT" in effort and re.search(r"thinking token budget is rejected", effort), (
        "the reasoning rule lost its CLI knob or the thinking-budget rejection"
    )
    # the haiku rung is the reverse of the others: extended thinking only, and no effort
    assert re.search(r"haiku rung(?: is)?\s*[:—-]?\s*the reverse", effort) and re.search(r"effort does not apply", effort), (
        "the reasoning rule no longer says the haiku rung thinks differently"
    )
    assert "effort=" in effort and "prompt cache" in effort, "the reasoning rule lost its per-call knob or the cache warning"


def test_auth_boundary() -> None:
    auth = _bullet("Fabrik defaults", "Auth boundary")
    assert re.search(r"never ANTHROPIC_API_KEY", auth), "the auth boundary no longer refuses ANTHROPIC_API_KEY"
    assert re.search(r"Never pass bare=True", auth) and "Not logged in" in auth, (
        "the auth boundary no longer warns that bare mode breaks the subscription lane"
    )
    assert "uses_claude_cli" in auth and "rotated" in auth, "the deployed-service rule is gone"
    # Anthropic's terms for products serving other users are stated, and the fleet-wide call is the operator's
    assert re.search(r"ordinary, individual use", auth) and "API key" in auth, (
        "the auth boundary no longer states Anthropic's terms for products serving other users"
    )
    assert re.search(r"on behalf of their users", auth) and re.search(r"decision before it is built", auth), (
        "the auth boundary lost the terms' prohibition or its interim rule"
    )
    assert re.search(r"\b(?:never|not) (?:as )?a default\b", auth), "the interim rule no longer says it is never a default"
    items = re.findall(r"\bW-[0-9a-f]{8}\b", auth)
    assert items, "the auth boundary no longer cites the open operator item"
    for item in items:
        assert (ROOT / ".fabrik" / "work" / f"{item}.json").is_file(), f"the auth boundary cites a missing item: {item}"
    assert re.search(r"paused on 2026-06-15", auth), "the paused credit change is no longer dated"


def test_dollar_caps_trap_and_framework_gate() -> None:
    anti = _paragraph("Anti-pattern")
    assert re.search(
        r"Anti-pattern:\s*(?:putting|adding|setting|placing) (?:a )?per-call dollar caps? on the operational diagnose loop", anti
    ), "the anti-pattern is gone or no longer forbids the caps"
    assert re.search(r"\bIt must run\b", anti) and not re.search(r"must not run", anti), (
        "the anti-pattern no longer says the diagnose loop must run"
    )
    assert "max_turns" in anti and "core/cost-budget.md" in anti, "the anti-pattern lost its bound or its cite"
    trap = _paragraph("Licence trap")
    assert "AutoGPT" in trap and "Polyform Shield" in trap, "the licence trap no longer names AutoGPT's platform licence"
    assert re.search(r"\bnot (?:an? )?open[- ]source\b|rather than open[- ]source", trap), (
        "the licence trap no longer says the platform licence is not open source"
    )
    for bullet in _bullets("Fabrik defaults"):
        assert not re.search(r"\bAutoGPT\b", bullet), f"AutoGPT is offered: {bullet[:70]!r}"
    frameworks = _bullet("Subcategories", "Agent frameworks")
    assert re.search(r"only on a recorded need", frameworks), "frameworks are no longer gated on a recorded need"
    assert re.search(r"AutoGen, which is in maintenance mode", frameworks), "AutoGen's maintenance mode is gone"
    research = _bullet("Subcategories", "Research")
    assert "deep-research" in research and re.search(r"ai-consult[^.]*off", research), (
        "the research lane lost deep-research or ai-consult's pause"
    )
    assert re.search(r"not an agent loop", research), "deep-research is no longer named as a workflow"
    compare = _bullet("Subcategories", "Compare")
    assert re.search(r"not been updated since 2026-04-12", compare), "the stale function-calling board is not flagged"


def test_gateway_note() -> None:
    gateway = _plain(_section("Gateway coverage").split("<!-- GATEWAY_COUNTS:START", 1)[0])
    assert "supported_parameters=tools" in gateway, "the gateway note lost the tool-calling filter"
    assert re.search(r"Reasoning tokens bill as output", gateway), "the gateway note lost the reasoning billing rule"


def test_no_retired_routes() -> None:
    body = _plain(_prose())
    lowered = body.replace("docs/reference/kilo/", "docs/reference/").lower()
    for gone in ("traycer", "kilo", "o3", "o4-mini", "o1"):
        assert not re.search(rf"\b{re.escape(gone)}\b", lowered), f"{gone} is retired and still named"
    assert not re.search(r"\bGPT-?4", body), "OpenAI's GPT-4 line is shut down or scheduled; the pack still names it"


def test_no_version_literals() -> None:
    version_re = _load("vision_pack_test", ROOT / "tests" / "test_vision_pack.py").VERSION_RE
    found = version_re.findall(_prose())
    assert not found, f"version literals in the pack: {found}"


def test_choice_recorded_and_cites_resolve() -> None:
    header = _plain(_pack().split("# 5. Agentic", 1)[0])
    assert "project.yaml (ai_category, ai_subcategory, ai_tools)" in header, (
        "the header no longer records the choice in project.yaml"
    )
    index = INDEX.read_text(encoding="utf-8")
    for key in ("ai_category", "ai_subcategory", "ai_tools"):
        assert key in index, f"ai/00 no longer names {key}: re-align this pack"
    heads = [ln.lstrip("#").strip() for ln in index.splitlines() if ln.startswith("#")]
    assert any(h.startswith("Claude subscription first") for h in heads), "ai/00 lost § Claude subscription first"
    for sibling in ("core/62-using-subagents.md", "core/cost-budget.md"):
        assert sibling in _pack() and (RULES / sibling).is_file(), f"{sibling} is cited but missing"


@pytest.mark.skipif(not (LIB / "README.md").is_file(), reason="needs /opt/fabrik-lib")
def test_fabrik_lib_modules_exist() -> None:
    for module in ("llm-dispatch", "deep-research", "ai-consult"):
        assert f"`{module}`" in _pack(), f"the pack no longer names fabrik-lib's {module}"
        assert (LIB / module / "README.md").is_file(), f"fabrik-lib no longer has {module}/"
    dispatch = (LIB / "llm-dispatch" / "README.md").read_text(encoding="utf-8")
    for needle in ("run_agentic", "start_session", "strict_mcp_config", 'permission_mode="dontAsk"'):
        assert needle in dispatch, f"llm-dispatch no longer documents {needle!r}: re-align the pack"
    assert re.search(r"bare.{0,40}defaults to .?False", dispatch), "llm-dispatch no longer defaults bare to False"
