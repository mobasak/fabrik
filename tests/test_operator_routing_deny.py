"""Behavior contract for the hub's operator routing denies.

The denies are applied in `scripts/kilo-benchmarks/rank_task_subagents.py`, which GENERATES
`docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` — the doc `libs/subagents.select.pick_models`
prefers over its vendored table. A model omitted from the emitted routing section is not routed to.

⚠️ WHY NOT IN `libs/subagents/select.py`, where the mechanism would be simpler. That module is
VENDORED from fabrik-lib (`fabrik_synced_manifest.VENDORED_DIRS`; the hub copy is contractually kept
byte-identical to `/opt/fabrik-lib/subagents` by re-vendoring). Editing it is an unauthorised fork of
another repo's code AND gets reverted by the next re-vendor. This was learned the expensive way on
2026-09-05: a deny was implemented there, force-synced to 46 project copies, and reverted three times
by the re-vendor — which I then misread as a defect rather than as the boundary working. The generator
is hub-owned; that is the whole point of this file's existence.

The root causes that argue for an upstream fix were mailed to fabrik-lib (01M1S7QACGEP66JM891E9B4CCQ).
If they adopt the denies in canonical, these entries become redundant — the intended end state.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_KB = _ROOT / "scripts" / "kilo-benchmarks"
_DOC = _ROOT / "docs" / "reference" / "kilo" / "TASK_SUBAGENT_SELECTION.md"

sys.path.insert(0, str(_KB))
sys.path.insert(0, str(_ROOT))
_spec = importlib.util.spec_from_file_location("rank_deny", _KB / "rank_task_subagents.py")
rank = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rank)

from libs.subagents.select import pick_models  # noqa: E402

REVIEW_DENIED = ("qwen/qwen3-max", "google/gemini-3-flash-preview")
ALWAYS_DENIED = "deepseek/deepseek-v4-pro"


def test_the_denies_are_declared_in_hub_owned_code_not_the_vendored_module():
    """The placement IS the contract. If someone moves these back into `libs/subagents`, the deny
    becomes an unauthorised fork that the next re-vendor silently reverts."""
    assert set(rank.OPERATOR_DENY["review"]) == set(REVIEW_DENIED)
    assert ALWAYS_DENIED in rank.OPERATOR_DENY_ALWAYS
    vendored = (_ROOT / "libs" / "subagents" / "select.py").read_text(encoding="utf-8")
    assert "ROUTING_DENYLIST" not in vendored, (
        "a routing deny is back inside the VENDORED fabrik-lib module — that is not the hub's code "
        "to edit, and the next re-vendor reverts it. Put policy in rank_task_subagents.py."
    )


@pytest.mark.parametrize("model", REVIEW_DENIED)
def test_a_denied_reviewer_is_absent_from_the_emitted_review_section(model):
    """The doc is what routing reads, so absence FROM THE DOC is the deny.

    ⚠️ This used to bound the section with `.split("###")[0]`, which does NOT stop at the `## Full …
    results` display tables that list every benchmarked model including the denied ones. It passed
    only because another `### <kind>` section happened to follow `### review` and cut the chunk short
    — an accident of section ORDER, not a property of the doc. Removing the section that followed it
    (proven live while revert-testing D-159's backstop) turned it red instantly. Parse with the
    module's own `_synced_ranking()` instead: it returns exactly what routing consumes."""
    from libs.subagents import select

    routable = select._synced_ranking().get("review", [])
    assert model not in routable, f"{model} is still routable for review: {routable}"


def test_the_broken_worker_is_absent_from_every_routing_section():
    """`deepseek/deepseek-v4-pro`: 83 dispatches across 9 repos since 2026-08-20, 67 errors (81%),
    65 recording no cost, 4.09 MB of prompt shipped. It ranked FIRST for `docs`."""
    # ⚠️ Bound each section to its OWN table rows. Splitting on "\n### " alone lets a routing
    # section run past the next "## " heading and swallow the display-only benchmark leaderboards
    # further down the doc — which DO list denied models legitimately ("display only; not parsed for
    # routing"). The first version of this test did exactly that and reported a routing defect that
    # did not exist.
    kind = None
    offenders = []
    for line in _DOC.read_text(encoding="utf-8").splitlines():
        if line.startswith("### ") and "(n_total=" in line:
            kind = line[4:].split(" ")[0]
            continue
        if line.startswith("#"):
            kind = None  # any other heading ends the routing section
            continue
        if kind and line.startswith("|") and f"`{ALWAYS_DENIED}`" in line:
            offenders.append((kind, line.strip()))
    assert not offenders, f"{ALWAYS_DENIED} is still routable: {offenders}"


@pytest.mark.parametrize("kind", ["review", "docs"])
def test_pick_models_end_to_end_honours_the_deny(kind):
    """The invariant that actually matters: what a dispatching agent gets back. Runs the REAL
    `pick_models` against the REAL doc — no fixture, because the doc is the coupling under test."""
    got = pick_models(kind, n=25)
    assert got, f"{kind} routing returned nothing — a deny must not empty a roster"
    assert ALWAYS_DENIED not in got
    if kind == "review":
        for m in REVIEW_DENIED:
            assert m not in got, f"{m} came back from pick_models({kind!r}): {got}"


def test_the_benchmark_supplement_cannot_reintroduce_a_denied_model():
    """The deny has to be applied at BOTH injection points. Filtering only the fleet-rows loop left
    qwen3-max and gemini-3-flash at ranks 3-4 of the review section as n=0 benchmark rows — where no
    amount of live evidence would ever have removed them, because they had no live rows to judge."""
    src = (_KB / "rank_task_subagents.py").read_text(encoding="utf-8")
    supplement = src.split("review_benchmark: list[str] = [")[1].split("]")[0]
    assert "OPERATOR_DENY" in supplement, (
        "the benchmark supplement no longer applies the operator deny — denied models will reappear "
        "as n=0 rows in the emitted review section"
    )


# ─── D-159: the operator ALLOWLIST (layered over the denies above) ────────────────────────────────
# The allowlist is the narrower policy: the denies name models that may never route, the allowlist
# names the only ones that may. Its dangerous edge is NOT letting a bad model through — it is
# emptying a section, because `pick_models` then falls back to the vendored `_TABLE`, which is
# unrestricted. Every test below exists because that fallback is silent.

ALLOWED = ("deepseek/deepseek-v4-flash", "deepseek/deepseek-v3.2-exp")


def test_the_allowlist_is_declared_in_hub_owned_code_with_a_deterministic_order():
    assert set(rank.OPERATOR_ALLOW) == set(ALLOWED)
    assert rank.OPERATOR_ALLOW_ORDER == ALLOWED, (
        "order is the emitted rank order and must be a TUPLE — emitting from the frozenset would "
        "reorder the doc between runs, because Python randomises str hashing per process"
    )


def test_allowlist_covers_every_task_kind_pick_models_can_ask_for():
    """A kind missing from the backstop is a kind that silently reverts to the vendored table."""
    from libs.subagents import TASK_KINDS

    assert set(rank.TASK_KINDS_EMITTED) == set(TASK_KINDS), (
        "TASK_KINDS_EMITTED has drifted from the module's TASK_KINDS; an uncovered kind falls "
        "through to the unrestricted _TABLE"
    )


def test_every_routing_section_in_the_live_doc_contains_only_allowed_models():
    """The doc IS the routing policy — so assert on the module's OWN parse of it, not a hand-rolled
    one. The first version of this test split the doc on `### <kind> (` and ended each section at the
    next `### `, which silently swallowed the `## Full … results` display tables that follow the LAST
    routing section, and then read their `grade` column as model names. Parsing with
    `select._synced_ranking()` removes that whole class: it is the exact function `pick_models`
    calls, so what it returns is what routing sees, by construction rather than by resemblance."""
    from libs.subagents import select

    ranking = select._synced_ranking()
    assert ranking, "the module parsed NO routing sections out of the live doc"
    offenders = [
        f"{kind}: {model}"
        for kind, models in ranking.items()
        for model in models
        if not rank._allowed(model)
    ]
    assert not offenders, "non-allowed models are routable in the live doc: " + ", ".join(offenders)


def test_no_task_kind_falls_through_to_the_vendored_table():
    """THE regression this change exists to prevent. Filtering a section to zero rows does not
    narrow routing — it hands that whole kind to the unrestricted `_TABLE`. Before D-159, `plan`
    held exactly one row (deepseek-v4-pro, itself denied) and `spec` one (z-ai/glm-5), so a naive
    allowlist would have deleted both sections and reverted both kinds to the vendored default."""
    doc = _DOC.read_text(encoding="utf-8")
    missing = [k for k in rank.TASK_KINDS_EMITTED if f"### {k} (" not in doc]
    assert not missing, (
        f"no routing section for {missing} — pick_models falls back to the vendored _TABLE for "
        "those kinds, which the operator's allowlist does not govern"
    )


@pytest.mark.parametrize("kind", ["code", "docs", "plan", "research", "review", "spec"])
def test_pick_models_end_to_end_returns_only_allowed_models(kind):
    """The executable check: not what the doc says, but what routing actually hands a dispatch."""
    picked = pick_models(kind, n=12)
    assert picked, f"pick_models({kind!r}) returned nothing — a dispatch would have no worker"
    bad = [m for m in picked if not rank._allowed(m)]
    assert not bad, f"pick_models({kind!r}) still routes non-allowed models: {bad}"


# ─── Guards for the pass-1 review fixes (D-159) ───────────────────────────────────────────────────


def test_claude_code_ids_are_not_routable():
    """`_allowed()` is what the tests above use as the definition of "routable", so it must not
    bless an id the pool cannot dispatch. `claude-code/*` are spawn-native — `_transport` would 404
    — and an earlier draft returned True for them, which made every guard here assert less than it
    looked like it did."""
    for model in ("claude-code/opus", "claude-code/haiku", "claude-code/fable"):
        assert not rank._allowed(model), f"{model} is spawn-native and must never be routable"


def test_the_allowlist_rows_parse_back_through_the_real_parser():
    """The 9-column shape is a CONTRACT (`select.py:296,303` — model at cells[1], n at cells[-1]).
    Assert it by round-tripping through the actual parser rather than by eyeballing the format, and
    cover the emitter BOTH the backstop and the no-data stub now share."""
    from libs.subagents.select import load_task_ranking

    body = "\n".join(rank._allowlist_rows({}, {}))
    doc = f"# t\n\nLast refresh: 2099-01-01\n\n### plan (n_total=0, operator allowlist)\n{body}\n"
    tmp = Path(__file__).parent.parent / ".tmp" / "allowlist_roundtrip.md"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(doc, encoding="utf-8")
    try:
        parsed = load_task_ranking(str(tmp))
    finally:
        tmp.unlink(missing_ok=True)
    assert parsed.get("plan") == list(rank.OPERATOR_ALLOW_ORDER), (
        f"the real parser did not read the allowlist rows back: {parsed!r}"
    )


def test_the_no_data_stub_does_not_hand_every_kind_to_the_vendored_table():
    """FAIL-OPEN guard. `render([])` takes the early "No aggregated runs yet" return, which predates
    the allowlist; its own comment called falling back to `_TABLE` correct, and under D-159 that is
    the unrestricted list the operator excluded. An empty flywheel must still emit the policy."""
    out = rank.render([], state="ok", include_full_results=False)
    for kind in rank.TASK_KINDS_EMITTED:
        assert f"### {kind} (" in out, (
            f"the no-data stub emitted no `### {kind}` section — pick_models falls back to the "
            f"unrestricted vendored _TABLE for it:\n{out[:600]}"
        )
    assert "`_TABLE` default" not in out, "the stub still advertises the vendored-table fallback"


def test_the_backstop_covers_a_task_kind_the_frozen_literal_has_not_caught_up_with():
    """`TASK_KINDS_EMITTED` is frozen hub-side so a re-vendor cannot redefine hub policy — which is
    also exactly how a NEW TaskKind goes uncovered. The backstop unions it with live `by_task`, so a
    kind the fleet is actually dispatching gets a section even before the literal is updated."""
    assert "ops" not in rank.TASK_KINDS_EMITTED, "pick a kind the literal really does not carry"
    rows = [("ops", "qwen/qwen3-max", 40, 0.01, 3.0, 0.9)]
    out = rank.render(rows, state="ok", include_full_results=False)
    assert "### ops (" in out, (
        "a fleet-used kind absent from the frozen literal got NO section, so it falls through to "
        "the unrestricted vendored _TABLE"
    )
    ops_section = out.split("### ops (")[1].split("\n#")[0]
    assert "qwen/qwen3-max" not in ops_section, "a non-allowed model survived into the new section"


# ─── Guards for the CLOSING-pass fixes (R1/R2/R5) ─────────────────────────────────────────────────


@pytest.mark.parametrize("kind", ["code", "docs", "plan", "research", "review", "spec"])
def test_excluding_the_top_model_still_leaves_a_worker(kind):
    """THE reliability lever, and the fix that had no grader. `select.py:559` documents `exclude` as
    what a caller reaches for when a model failed THIS session; `agent.py` raises
    `ValueError: fanout: pick_models(...) returned no models` on an empty draw. So a kind that offers
    only ONE model turns a routine provider hiccup into a raised batch."""
    picked = pick_models(kind, n=5)
    assert len(picked) >= 2, f"{kind} offers {picked} — excluding one leaves nothing to route to"
    survivors = pick_models(kind, n=5, exclude=(picked[0],))
    assert survivors, f"{kind}: excluding the top model returned nothing — fanout would raise"


def test_a_one_model_fallback_section_is_topped_up_not_shipped_short(monkeypatch):
    """R1: the mode-(b) CODE fallback marks `code` emitted, so the backstop skips the kind — meaning
    the top-up must run in that emitter too, or a fallback section built from one allowlisted model
    ships a one-model kind and `pick_models("code", exclude=rank1)` returns [].

    ⚠️ This must reach the FALLBACK path, not the fleet loop. An earlier draft passed a `docs` row,
    which goes through the fleet loop — it would have passed against the unfixed fallback and graded
    nothing. Monkeypatching `_load_coding_fallback` is what makes it a real guard: `by_task` carries
    no `code` rows, so the mode-(b) block is the only thing that can emit that section."""
    from libs.subagents.select import load_task_ranking

    monkeypatch.setattr(rank, "_load_coding_fallback", lambda: ["deepseek/deepseek-v4-flash"])
    rows = [("docs", "deepseek/deepseek-v4-flash", 40, 0.01, 3.0, 0.9)]
    out = rank.render(rows, state="ok", include_full_results=False)
    assert "fallback from CODING_SUBAGENT_SELECTION.md" in out, (
        "the mode-(b) code fallback did not fire — this test is not exercising the path it names"
    )
    tmp = Path(__file__).parent.parent / ".tmp" / "topup_fallback.md"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(out, encoding="utf-8")
    try:
        parsed = load_task_ranking(str(tmp))
    finally:
        tmp.unlink(missing_ok=True)
    assert set(parsed.get("code", [])) == set(rank.OPERATOR_ALLOW_ORDER), (
        f"the one-model FALLBACK section was not topped up: {parsed.get('code')}"
    )
    assert parsed.get("docs"), "the fleet-loop kind regressed while fixing the fallback one"


def test_no_section_carries_a_duplicate_model_or_a_duplicate_rank():
    """R2: the first top-up derived its `already` set and its starting rank from the FLEET rows
    alone, so a model the benchmark supplement had already appended was emitted a SECOND time, at a
    duplicate rank. Routing survived (the parser dedups), so only a doc-integrity assertion catches
    it — in a fleet-synced table whose rank order IS the contract."""
    doc = _DOC.read_text(encoding="utf-8")
    for kind in rank.TASK_KINDS_EMITTED:
        for chunk in doc.split(f"### {kind} (")[1:]:
            section = chunk.split("\n#")[0]
            models, ranks = [], []
            for line in section.splitlines():
                if not line.startswith("| ") or "`" not in line:
                    continue
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if not cells or not cells[0].isdecimal():
                    continue
                ranks.append(cells[0])
                models.append(cells[1].strip("`"))
            assert len(models) == len(set(models)), f"{kind}: duplicate model in one section: {models}"
            assert len(ranks) == len(set(ranks)), f"{kind}: duplicate rank in one section: {ranks}"


@pytest.mark.parametrize("kind", ["review", "code", "docs"])
def test_a_supplemented_section_does_not_re_emit_what_the_supplement_already_wrote(kind):
    """The live-doc check above passes even when this is broken, because the live sections happen not
    to trigger it — so this CONSTRUCTS the case. The code/review benchmark supplements append rows
    but for a long time recorded neither the models nor the ranks they used (`emitted_*_models` and
    `*_last_rank` were updated only by the fleet loop). Nothing ran after them, so it was harmless —
    until the D-159 top-up did, and re-emitted a model the supplement had already written, at a rank
    it had already used (measured: `1, 2, 2` with v4-flash twice)."""
    rows = [(kind, "deepseek/deepseek-v3.2-exp", 40, 0.01, 3.0, 0.9)]
    out = rank.render(rows, state="ok", include_full_results=False)
    section = out.split(f"### {kind} (")[1].split("\n#")[0]
    models, ranks = [], []
    for line in section.splitlines():
        if not line.startswith("| ") or "`" not in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or not cells[0].isdecimal():
            continue
        ranks.append(cells[0])
        models.append(cells[1].strip("`"))
    assert models, f"{kind}: constructed section emitted no data rows"
    assert len(models) == len(set(models)), f"{kind}: model emitted twice: {models}"
    assert len(ranks) == len(set(ranks)), (
        f"{kind}: rank reused: {list(zip(ranks, models, strict=True))}"
    )


def test_a_deny_beats_the_allowlist_everywhere_it_could_contradict(monkeypatch):
    """The two operator policies can contradict, and the allowlist emitters used to win.

    Every other emission path checks `OPERATOR_DENY` / `OPERATOR_DENY_ALWAYS`, but the top-up and the
    backstop wrote straight from `OPERATOR_ALLOW_ORDER` — so a model on BOTH lists (an operator
    restricting a roster and then banning one of its members: an ordinary thing to want) would have
    been emitted as routable by them while every other path refused it. No overlap exists today,
    which is exactly why this needs a test rather than an observation."""
    from libs.subagents.select import load_task_ranking

    banned = rank.OPERATOR_ALLOW_ORDER[0]
    monkeypatch.setattr(rank, "OPERATOR_DENY_ALWAYS", frozenset({banned}))
    out = rank.render([], state="ok", include_full_results=False)  # the no-data stub path
    tmp = Path(__file__).parent.parent / ".tmp" / "deny_beats_allow.md"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(out, encoding="utf-8")
    try:
        parsed = load_task_ranking(str(tmp))
    finally:
        tmp.unlink(missing_ok=True)
    for kind, models in parsed.items():
        assert banned not in models, (
            f"{kind}: `{banned}` is denied but the allowlist emitted it as routable: {models}"
        )
    assert any(parsed.values()), "the deny emptied every kind — the guard must not fail-open either"
