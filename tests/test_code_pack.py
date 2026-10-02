"""Pins `ai/60-code.md` to the dev stack the operator named, the code-agent loop, its isolation and its trust rules.

The pack is read by citation from ai/00 (one scratch folder under /opt matches its globs). Seven things it states can go
false with no other gate red:

1. The two machinery-owned blocks (GATEWAY_COUNTS, OPENROUTER_ROUTES) survive, and `Last content verification:` parses
   for `scripts/check_ai_pack_freshness.py`.
2. Fabrik's own development runs on Claude Code in VS Code (operator ruling, D-514); Windsurf and the Kilo CLI are no
   longer used; OpenRouter agents wait on the paused pool. The pack once listed Windsurf Cascade and Kilo as live.
3. Code-writing features run on Claude through `claude -p` on ai/50's agent loop, with the fleet's own example cited.
4. Generated code never runs on the host: the Bash sandbox alone does not contain an unattended agent, so a container
   or VM with egress closed, and `sandbox.failIfUnavailable` where the Bash sandbox is used.
5. Repository content is untrusted input: credentials out of reach, least privilege, a human approves side effects,
   and the loop's settings default holds.
6. The licence trap names Codestral's non-production licence and the revenue-capped open coding licences; review
   cites core/50; the comparison list flags the stale boards.
7. No retired name offered as live (Windsurf Cascade, Kilo, Traycer, OpenAI's GPT-4 line), no version number in any
   shape — the detector is the one `tests/test_vision_pack.py` defines — and every cited pack, script and module exists.

Guards read structure (one bullet at a time, emphasis stripped, whole words) so a restyled line keeps its meaning — a
re-wrap, a dropped bold, a label arrow or colon — and each guard pins the clause that carries the rule's force (never,
untrusted, no longer, does not contain), not only its subject, so a reversed verb fails. The cheapest way past (3) is a
second route offered in prose outside the bullets; the review reads the rest. The cheapest way past (7) is a version in
words; the detector catches the shapes agents copy.
"""

from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
PACK = RULES / "ai" / "60-code.md"
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
    body = re.split(r"\n\*\*(?:Licence trap)", _section(heading), maxsplit=1)[0]
    return [_plain(b) for b in body.split("\n- ")[1:]]


def _bullet(heading: str, label: str) -> str:
    """The first bullet whose opening words contain the label (a restyled label still matches)."""
    return next((b for b in _bullets(heading) if label.lower() in b[:60].lower()), "")


def _trap() -> str:
    defaults = _section("Fabrik defaults")
    i = defaults.find("**Licence trap")
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
    mod = _load("freshchk_code", FRESH)
    # warn-only past its window: the pin is that the stamp PARSES on the script's own UTC clock, never that it is fresh
    status, _age, msg = mod.check_pack(PACK, mod._today())
    assert status != "unstamped", f"check_ai_pack_freshness.py cannot read the stamp: {msg}"


def test_dev_stack_is_the_operators() -> None:
    stack = _bullet("Fabrik defaults", "Fabrik's own development")
    assert re.search(r"runs on Claude Code", stack) and "VS Code" in stack and "D-514" in stack, (
        "the dev-stack bullet no longer says Fabrik runs on Claude Code in VS Code (D-514)"
    )
    assert re.search(r"Windsurf is no longer used \(D-514\)", stack) and re.search(r"Kilo CLI \(D-364\)", stack), (
        "the dev-stack bullet no longer retires Windsurf (D-514) and the Kilo CLI (D-364)"
    )
    assert re.search(r"OpenRouter agents", stack) and re.search(r"paused", stack) and "D-181" in stack, (
        "OpenRouter agents are no longer tied to the paused pool"
    )


def test_code_features_run_on_the_ai50_loop() -> None:
    loop = _bullet("Fabrik defaults", "Code-writing")
    # the default is what the bullet OPENS with, not a later mention
    assert re.match(r"Code-writing features\s*(?::\s*→?|→)\s*Claude through claude -p", loop), (
        f"the code-writing default changed: {loop[:70]!r}"
    )
    for needle in ("ai/50-agentic.md", "llm-dispatch", "run_agentic", "opus", "scripts/ci_fix_dispatcher.py"):
        assert needle in loop, f"the code-writing default no longer names {needle!r}"
    assert re.search(r"grant editing and commands with allowed_tools", loop), (
        "the code-writing default no longer says how dontAsk grants Edit and Bash"
    )
    assert re.search(r"not the pattern\s+for a product feature", loop), (
        "the CI dispatcher is offered as the product pattern again"
    )
    assert (ROOT / "scripts" / "ci_fix_dispatcher.py").is_file(), "the cited in-house example is missing"


def test_generated_code_never_runs_on_the_host() -> None:
    iso = _bullet("Fabrik defaults", "run generated code")
    assert re.match(r"(?:Never|Do not|Don't) run generated code on the host", iso), (
        f"the isolation rule no longer forbids host execution: {iso[:70]!r}"
    )
    assert re.search(r"file tools, MCP servers and hooks still run on the host", iso), (
        "the isolation rule no longer says what the Bash sandbox leaves on the host"
    )
    assert re.search(r"(?:does not|doesn't|cannot) contain an unattended agent", iso), (
        "the isolation rule no longer says the Bash sandbox alone does not contain an agent"
    )
    assert re.search(r"container, a VM, or Anthropic's sandbox runtime", iso) and re.search(r"egress closed", iso), (
        "the isolation rule lost the container-VM-runtime route or the egress rule"
    )
    assert re.search(r"untrusted repository[^.]*dedicated VM", iso), "untrusted repositories no longer go to a VM"
    assert "sandbox.failIfUnavailable" in iso, "the fail-closed sandbox setting is gone"


def test_repository_is_untrusted_input() -> None:
    trust = _bullet("Fabrik defaults", "repository is")
    assert re.match(r"The repository is (?:untrusted|not trusted) input", trust), (
        f"the trust rule changed: {trust[:70]!r}"
    )
    assert re.search(r"credentials out of the agent's reach", trust), "the credential rule is gone"
    assert re.search(r"human approve", trust) and re.search(r"before anything with side effects", trust), (
        "the human-approval rule for side effects is gone"
    )
    assert 'setting_sources=""' in trust and "strict_mcp_config=True" in trust, (
        "the loop's settings default or the strict-MCP flag is gone"
    )
    assert re.search(r"Rule of Two", trust) and re.search(r"needs a human to approve each action", trust), (
        "the trust rule no longer names the Rule of Two floor"
    )


def test_trap_review_and_comparison() -> None:
    trap = _trap()
    assert "Codestral" in trap and re.search(r"no commercial or hosted use", trap), (
        "the licence trap no longer says Codestral's open weights allow no commercial use"
    )
    assert re.search(r"revenue cap", trap) and re.search(r"AI work assistant", trap), (
        "the licence trap lost the revenue-capped and assistant-gated licences"
    )
    review = _bullet("Fabrik defaults", "Code review")
    assert "core/50-code-review.md" in review and re.search(r"read-only", review), (
        "the review rule lost its core/50 cite or its read-only tool set"
    )
    tools = _bullet("Subcategories", "Developer tools")
    for needle in ("Devin Desktop", "Kiro", "Antigravity CLI", "not Fabrik's stack"):
        assert needle in tools, f"the developer-tools list no longer names {needle!r}"
    reviews = _bullet("Subcategories", "Review products")
    assert re.search(r"code-review reviews a diff locally on the Max plan", reviews), (
        "the review list no longer says /code-review is the Max plan's route"
    )
    assert re.search(r"Team and Enterprise only", reviews), "the hosted review service's plan limit is gone"
    assert re.search(r"outside the fleet's auth boundary", reviews), "the GitHub action is offered without its auth caveat"
    compare = _bullet("Subcategories", "Compare")
    assert re.search(r"Terminal-Bench, which is current", compare), "Terminal-Bench is no longer named as current"
    assert re.search(r"SWE-bench Verified is saturated", compare), "SWE-bench Verified is no longer flagged"
    gateway = _plain(_section("Gateway coverage").split("<!-- GATEWAY_COUNTS:START", 1)[0])
    assert re.search(r"usage, not quality", gateway), "the gateway note no longer says the ranking is usage"


def test_no_retired_routes_offered() -> None:
    body = _plain(_prose())
    assert not re.search(r"\btraycer\b", body, re.I), "Traycer is retired and still named"
    assert not re.search(r"Windsurf Cascade", body), "Windsurf Cascade is retired and still named"
    assert not re.search(r"\bGPT-?4", body), "OpenAI's GPT-4 line is shut down; the pack still names it"
    # Kilo may appear only in the sentence that retires it
    for sentence in re.split(r"(?<=[.;])\s+", body.replace("docs/reference/kilo/", "docs/reference/")):
        if re.search(r"\bkilo\b", sentence, re.I):
            assert re.search(r"no longer used", sentence), f"Kilo is named as live: {sentence!r}"


def test_no_version_literals() -> None:
    version_re = _load("vision_pack_test", ROOT / "tests" / "test_vision_pack.py").VERSION_RE
    found = version_re.findall(_prose())
    assert not found, f"version literals in the pack: {found}"


def test_choice_recorded_and_cites_resolve() -> None:
    header = _plain(_pack().split("# 6. Code", 1)[0])
    assert "project.yaml (ai_category, ai_subcategory, ai_tools)" in header, (
        "the header no longer records the choice in project.yaml"
    )
    index = INDEX.read_text(encoding="utf-8")
    for key in ("ai_category", "ai_subcategory", "ai_tools"):
        assert key in index, f"ai/00 no longer names {key}: re-align this pack"
    for sibling in ("ai/50-agentic.md", "core/50-code-review.md", "core/76-gpu-workers.md"):
        assert sibling in _pack() and (RULES / sibling).is_file(), f"{sibling} is cited but missing"


@pytest.mark.skipif(not (LIB / "README.md").is_file(), reason="needs /opt/fabrik-lib")
def test_fabrik_lib_module_exists() -> None:
    assert "`llm-dispatch`" in _pack() and (LIB / "llm-dispatch" / "README.md").is_file(), (
        "the pack no longer names fabrik-lib's llm-dispatch, or the module is gone"
    )
