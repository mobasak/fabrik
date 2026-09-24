"""The Stop hook's DEFERRAL shape (D1-D4) and the DECISION block that is its one exemption.

Spec: docs/superpowers/specs/2026-09-23-stop-and-compaction-enforcement-design.md § C1 (the four
shapes, their scope and inputs) and § C2 (the block's parse and checks); ticket
docs/development/plans/2026-09-23-plan-1-stop-and-compaction/T03-stop-hook-deferral.md.

The red fixtures are drawn from the judged sample the spec measured
(docs/reference/research/2026-09-23-stop-compaction/verdict-*.json, loaded at runtime), the green
ones from the same files' FALSE-MATCH records and from d4_probe.py's ordinary-prose list.
"""

from __future__ import annotations

import ast
import importlib.util
import io
import json
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_HOOK = REPO / ".claude" / "hooks" / "final_gate_stop.py"
_spec = importlib.util.spec_from_file_location("final_gate_stop_deferral_probe", _HOOK)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

RESEARCH = REPO / "docs" / "reference" / "research" / "2026-09-23-stop-compaction"


@pytest.fixture(autouse=True)
def _interactive(monkeypatch, tmp_path) -> None:
    """Every fixture here is an INTERACTIVE session unless it says otherwise, and no hook side
    effect reaches the operator's real state (thread anchors, command runs, kaizen events)."""
    monkeypatch.delenv("CLAUDE_MESH_HEADLESS", raising=False)
    monkeypatch.setenv("THREAD_ANCHOR_DIR", str(tmp_path / "threads"))
    monkeypatch.setenv("COMMAND_RUN_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(tmp_path / "events"))
    monkeypatch.setenv(
        "HOME", str(tmp_path / "home")
    )  # main()'s harvest never reaches the real HOME


# --- transcript helpers (the shapes of tests/test_final_gate_stop_hook.py:816-835) ----------


def _turn(transcript: Path, *entries: str) -> None:
    transcript.write_text("\n".join(entries) + "\n", encoding="utf-8")


def _user(text: str = "do the thing", **extra: object) -> str:
    return json.dumps(
        {"type": "user", "message": {"content": [{"type": "text", "text": text}]}, **extra}
    )


def _asst_text(text: str) -> str:
    return json.dumps(
        {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}
    )


def _asst_tool(name: str, **inp: object) -> str:
    return json.dumps(
        {
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]},
        }
    )


def _stall(tmp_path: Path, final: str, *, user: str = "do the thing", **kw: object):
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(user), _asst_text(final))
    return hook._detect_stall(str(tr), tmp_path, set(), **kw)


def _load(name: str) -> list[dict]:
    return json.loads((RESEARCH / name).read_text(encoding="utf-8"))


def _prose() -> list[str]:
    """d4_probe.py's PROSE list, read from the file rather than copied (one source)."""
    tree = ast.parse((RESEARCH / "d4_probe.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "PROSE" for t in node.targets
        ):
            return list(ast.literal_eval(node.value))
    raise AssertionError("d4_probe.py lost its PROSE list")


# --- red: the judged premature stops (verdict-opdec.json) -----------------------------------

_OPDEC = [r for r in _load("verdict-opdec.json") if r.get("shape") in ("say-the-word", "menu")]
# The records are EXCERPTS of at most 100 chars. These ids' excerpts carry the deferral itself;
# the rest (O02 O05 O13 O14 O28 O29 O46 O70 O78) hold only the surrounding sentence, and the ≥ 17
# of 19 bar is V1's, measured on the FULL message (ticket step 12), never on an excerpt.
_OPDEC_SELF_CONTAINED = {"O01", "O09", "O17", "O18", "O25", "O40", "O61", "O69", "O74", "O79"}


def test_the_self_contained_set_is_a_subset_of_the_judged_records() -> None:
    assert {r["id"] for r in _OPDEC} >= _OPDEC_SELF_CONTAINED
    assert len(_OPDEC) == 19, "the judged say-the-word + menu population changed"


@pytest.mark.parametrize(
    "rec", [r for r in _OPDEC if r["id"] in _OPDEC_SELF_CONTAINED], ids=lambda r: r["id"]
)
def test_a_judged_premature_deferral_blocks(tmp_path: Path, rec: dict) -> None:
    """Each excerpt as it sat in the message: on the NEXT: line (the footer is where 281 of 905
    deferrals were measured) — the shape it trips is whichever the vocabulary names."""
    got = _stall(tmp_path, f"Work committed.\n\nNEXT: {rec['quote']}")
    assert got and got[0].startswith("deferral:"), (rec["id"], rec["quote"], got)


# --- red: the judged context excuses (verdict-context.json) ---------------------------------

_CONTEXT = _load("verdict-context.json")


def test_d4_fires_on_six_of_the_eight_judged_excuses() -> None:
    rows = [r for r in _CONTEXT if r["verdict"] == "STOP-EXCUSE"]
    fired = [r["id"] for r in rows if hook.deferral_shape(r["quote"]) == "D4"]
    assert len(rows) == 8
    assert len(fired) >= 6, fired


@pytest.mark.parametrize(
    "rec", [r for r in _CONTEXT if r["verdict"] == "STOP-EXCUSE"], ids=lambda r: r["id"]
)
def test_a_context_excuse_blocks_through_the_hook(tmp_path: Path, rec: dict) -> None:
    got = _stall(tmp_path, f"Phase 2 committed. {rec['quote']}")
    if hook.deferral_shape(rec["quote"]) is None:
        pytest.skip(f"{rec['id']}: below D4's recall floor by design (2 of 8 allowed)")
    assert got and got[0] == "deferral:D4", (rec["id"], got)


# --- red: one per shape, synthetic ---------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "shape"),
    [
        ("Committed.\n\nNEXT: operator decision — resume or reshape the plan", "D1"),
        ("Committed.\n\nNEXT: your call on the second half", "D1"),
        ("Committed.\n\n**NEXT:** awaiting your go on the sweep", "D1"),
        ("Committed.\n\nNEXT: Gate 2 — human gate on the deploy", "D1"),
        (
            "Two ways forward: (a) rerun the sweep on the new diff, or (b) fold it into T04. "
            "Which do you want?",
            "D2",
        ),
        (
            "Option A keeps the flag; option B deletes it. Your call.",
            "D2",
        ),
        ("All done and committed. Want me to also fold these in?", "D3"),
        ("Shall I run the next pass now?", "D3"),
        ("Just say the word and I will draft the migration.", "D3"),
        ("Let me know which of the two you prefer.", "D3"),
        ("It needs a clean session to finish; context is getting long.", "D4"),
    ],
)
def test_each_shape_blocks_outside_a_run(tmp_path: Path, text: str, shape: str) -> None:
    got = _stall(tmp_path, text)
    assert got and got[0] == f"deferral:{shape}", got
    assert hook.deferral_shape(text) == shape


def test_the_permission_shape_now_blocks_without_a_midrun_marker(tmp_path: Path) -> None:
    """The one behaviour that moves (spec § C1): D3 replaces `_PERMISSION_RE`'s mid-run-only
    loop, so no plan lock or UNCHECKED review is needed."""
    got = _stall(tmp_path, "Findings fixed. Should I push it?")
    assert got == ("deferral:D3", got[1]) and "Should I push it?" in got[1]


def test_a_named_gate_on_the_same_line_does_not_exempt_a_deferral(tmp_path: Path) -> None:
    """K2's per-line exemption is superseded for DEFERRAL only (spec § C1)."""
    got = _stall(tmp_path, "Done.\n\nNEXT: operator decision [cross-repo] — deploy approval")
    assert got and got[0] == "deferral:D1"


def test_a_dispatch_in_the_turn_does_not_keep_a_deferral(tmp_path: Path) -> None:
    tr = tmp_path / "t.jsonl"
    _turn(
        tr,
        _user(),
        _asst_tool("Agent", prompt="round 2 finders"),
        _asst_text("Round 2 dispatched. Which do you prefer for round 3 — slices or units?"),
    )
    got = hook._detect_stall(str(tr), tmp_path, set())
    assert got and got[0] == "deferral:D3"


def test_blocked_exempts_a_deferral_globally(tmp_path: Path) -> None:
    waived: list[tuple[str, str]] = []
    text = (
        "BLOCKED: vendor API — searched: docs/, web — missing: the auth scheme.\n"
        + "detail\n" * 80
        + "NEXT: operator decision — supply the scheme"
    )
    assert _stall(tmp_path, text, waived=waived) is None
    assert ("blocked-escalation", "BLOCKED:") in waived
    assert hook.deferral_shape(text) is None


# --- the DECISION block --------------------------------------------------------------------

_GATE_BLOCK = (
    "Certified build is ready.\n\n"
    "DECISION NEEDED (ground: gate)\n"
    "- Question: Deploy the certified build to production now?\n"
    "- Why it is yours: gate — Gate 2, a destructive/irreversible action needing authorisation.\n"
    "- Options: A — deploy now, live in ~5 min · B — hold for one more smoke pass (+15 min)\n"
    "- Recommendation: A — the certification gauntlet already passed; holding adds no new "
    "evidence.\n\n"
    "NEXT: operator decision — see DECISION NEEDED above"
)

_OPERATOR_Q = "should the retention window be 30 days or 90?"


def _block(ground: str, why: str, *, question: str = "Pick the retention window?") -> str:
    return (
        "Analysis done.\n\n"
        f"DECISION NEEDED (ground: {ground})\n"
        f"- Question: {question}\n"
        f"- Why it is yours: {why}\n"
        "- Options: A — 30 days, smaller disk · B — 90 days, longer audit trail\n"
        "- Recommendation: A — nothing in the spec needs 90.\n\n"
        "NEXT: operator decision — see DECISION NEEDED above"
    )


_WELL_FORMED = {
    "gate": _GATE_BLOCK,
    "underivable": _block(
        "underivable",
        "underivable — 30 vs 90 days changes the disk budget and the purge job; searched: "
        "docs/DECISIONS.md, `grep -rn retention docs/`, D-212 — all silent",
    ),
    "owned-asked": _block("owned", f'owned — asked: "{_OPERATOR_Q}"'),
    "owned-scope": _block("owned", 'owned — scope: "only touch the parser, nothing else"'),
}


@pytest.mark.parametrize("key", list(_WELL_FORMED))
def test_a_well_formed_block_exempts_the_deferral(tmp_path: Path, key: str) -> None:
    user = (
        f"Please look at the retention bug. {_OPERATOR_Q} Also only touch the parser, nothing else."
    )
    text = _WELL_FORMED[key]
    assert hook.deferral_shape(text) == "D1", "the fixture must carry a real deferral to exempt"
    assert _stall(tmp_path, text, user=user) is None
    ok, ground = hook.parse_decision_block(
        text, run_live=False, transcript_path=str(tmp_path / "t.jsonl")
    )
    assert ok and ground == key.split("-")[0]


def test_the_contract_example_parses_and_the_refused_example_is_refused(tmp_path: Path) -> None:
    """CLAUDE.md's own Legitimate/Refused pair (§ FINAL OUTPUT), read from the file."""
    claude = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
    legit = claude.split("Legitimate:\n```\n", 1)[1].split("```", 1)[0]
    refused = claude.split("Refused (a manufactured fork, not a decision):\n```\n", 1)[1].split(
        "```", 1
    )[0]
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user("(a) mine the unread session, then (b) deploy"))
    assert hook.parse_decision_block(legit, run_live=False, transcript_path=str(tr)) == (
        True,
        "gate",
    )
    ok, why = hook.parse_decision_block(refused, run_live=False, transcript_path=str(tr))
    assert not ok and "asked" in why


_GATE_SOURCES = [
    "fabrik-spec-review.md",
    "fabrik-flows-review.md",
    "fabrik-ui-design-review.md",
    "fabrik-deploy-plan-review.md",
    "fabrik-release.md",
    "fabrik-deploy.md",
]


@pytest.mark.parametrize("name", _GATE_SOURCES)
def test_every_gate_ending_command_block_parses(tmp_path: Path, name: str) -> None:
    """The six gate-ending commands (T01a) tell the agent to write their block unfenced; the
    block AS THEY STATE IT must pass `ground: gate` — their Why lines name design approval,
    Gate 2, deploy and publish."""
    import textwrap

    src = (REPO / "commands" / "_sources" / name).read_text(encoding="utf-8")
    blocks = []
    for chunk in src.split("DECISION NEEDED (ground: gate)")[1:]:
        body = chunk.split("```", 1)[0]
        blocks.append(
            "DECISION NEEDED (ground: gate)" + textwrap.dedent("\n" + body.split("\n", 1)[1])
        )
    assert blocks, f"{name} states no gate block"
    for block in blocks:
        text = textwrap.dedent(block)
        assert hook.parse_decision_block(text, run_live=True, transcript_path="") == (
            True,
            "gate",
        ), text


def test_a_fenced_block_never_exempts(tmp_path: Path) -> None:
    fenced = _GATE_BLOCK.replace("DECISION NEEDED", "```\nDECISION NEEDED", 1).replace(
        "\n\nNEXT:", "\n```\n\nNEXT:", 1
    )
    assert hook.extract_decision_block(fenced) is None
    got = _stall(tmp_path, fenced)
    assert got and got[0] == "deferral:D1"


def test_extract_takes_the_last_block(tmp_path: Path) -> None:
    two = _block("owned", "owned — nothing") + "\n\n" + _GATE_BLOCK
    block = hook.extract_decision_block(two)
    assert block and block.startswith("DECISION NEEDED (ground: gate)")
    assert block.count("\n") == 4


@pytest.mark.parametrize(
    ("text", "names"),
    [
        (
            _GATE_BLOCK.replace(
                "- Options: A — deploy now, live in ~5 min · B — hold for one more smoke pass (+15 min)\n",
                "",
            ),
            "Options",
        ),
        (_block("hunch", "hunch — it feels risky"), "unknown ground"),
        (_block("gate", "gate — the operator likes to see these"), "gate class"),
        (
            _block("underivable", "underivable — the purge job changes; nothing searched"),
            "searched:",
        ),
        (
            _block("underivable", "underivable — the purge job changes; searched: my memory"),
            "searched:",
        ),
        (
            _block(
                "underivable",
                "underivable — the purge job changes; searched: the spec and/or ledger",
            ),
            "searched:",
        ),
        (_block("owned", "owned — the operator owns retention"), "asked: or scope:"),
        (_block("owned", 'owned — asked: "why?"'), "12"),
        (_block("owned", 'owned — asked: "the retention window is theirs"'), "?"),
        (_block("owned", 'owned — asked: "is the retention window 7 days or 1?"'), "operator"),
        (_block("owned", 'owned — scope: "rewrite the whole storage layer"'), "operator"),
    ],
    ids=[
        "missing-field",
        "unknown-ground",
        "gate-without-class",
        "underivable-without-searched",
        "underivable-searched-names-nothing",
        "underivable-searched-prose-slash",
        "owned-without-quote",
        "asked-under-12",
        "asked-not-a-question",
        "asked-not-in-operator-entries",
        "scope-not-in-operator-entries",
    ],
)
def test_a_malformed_block_is_itself_a_deferral(tmp_path: Path, text: str, names: str) -> None:
    user = f"Please look at the retention bug. {_OPERATOR_Q}"
    got = _stall(tmp_path, text, user=user)
    assert got and got[0] == "deferral:block", got
    assert names in got[1], got[1]


def test_an_asked_quote_only_in_a_meta_row_is_refused(tmp_path: Path) -> None:
    """A command's expansion body (`isMeta: true`, the rows render_chat_history.py skips) is the
    command's words, not the operator's."""
    tr = tmp_path / "t.jsonl"
    text = _block("owned", f'owned — asked: "{_OPERATOR_Q}"')
    _turn(tr, _user("/fabrik-x"), _user(_OPERATOR_Q, isMeta=True), _asst_text(text))
    got = hook._detect_stall(str(tr), tmp_path, set())
    assert got and got[0] == "deferral:block" and "operator" in got[1]


def test_an_asked_quote_in_a_tool_result_or_summary_is_refused(tmp_path: Path) -> None:
    tr = tmp_path / "t.jsonl"
    text = _block("owned", f'owned — asked: "{_OPERATOR_Q}"')
    tool_row = json.dumps(
        {
            "type": "user",
            "message": {"content": [{"type": "tool_result", "content": _OPERATOR_Q}]},
            "toolUseResult": {"stdout": _OPERATOR_Q},
        }
    )
    _turn(tr, _user("go"), tool_row, _user(_OPERATOR_Q, isCompactSummary=True), _asst_text(text))
    got = hook._detect_stall(str(tr), tmp_path, set())
    assert got and got[0] == "deferral:block"


def _write_run(tmp_path: Path, sid: str, state: str) -> None:
    runs = tmp_path / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / f"{sid}.json").write_text(
        json.dumps({"command": "fabrik-review", "state": state, "updated_ts": time.time()}),
        encoding="utf-8",
    )


def _run_main(monkeypatch, tmp_path: Path, payload: dict) -> str:
    proj = tmp_path / "proj"
    (proj / "scripts").mkdir(parents=True, exist_ok=True)
    (proj / "scripts" / "final_gate.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"cwd": str(proj), **payload})))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(hook.tempfile, "gettempdir", lambda: str(tmp_path))
    assert hook.main([]) == 0
    return out.getvalue().strip()


def _scope_turn(tmp_path: Path) -> Path:
    tr = tmp_path / "t.jsonl"
    text = _block("owned", 'owned — scope: "only touch the parser, nothing else"')
    _turn(tr, _user("fix it. only touch the parser, nothing else."), _asst_text(text))
    return tr


def test_owned_scope_is_refused_inside_a_live_run(monkeypatch, tmp_path: Path) -> None:
    """The invoked command already grants its own scope (spec § C2); read the way `_run_record`
    reads it — `state: running` with a numeric fresh `updated_ts`."""
    tr = _scope_turn(tmp_path)
    _write_run(tmp_path, "sidrun", "running")
    out = _run_main(monkeypatch, tmp_path, {"session_id": "sidrun", "transcript_path": str(tr)})
    body = json.loads(out)
    assert body["decision"] == "block" and "DEFERRAL" in body["reason"]
    assert "scope:" in body["reason"]


def test_owned_scope_passes_outside_a_run(monkeypatch, tmp_path: Path) -> None:
    tr = _scope_turn(tmp_path)
    _write_run(tmp_path, "siddone", "done")
    out = _run_main(monkeypatch, tmp_path, {"session_id": "siddone", "transcript_path": str(tr)})
    assert out == ""
    events = [
        json.loads(line)
        for f in (tmp_path / "events").rglob("*.jsonl")
        for line in f.read_text(encoding="utf-8").splitlines()
    ]
    grounds = [e.get("ground") for e in events if e.get("event") == "decision_block"]
    assert grounds == ["owned"], events


def test_a_deferral_block_event_names_its_cause_and_shape(monkeypatch, tmp_path: Path) -> None:
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text("Done.\n\nNEXT: your call on the second half"))
    out = _run_main(monkeypatch, tmp_path, {"session_id": "sidev", "transcript_path": str(tr)})
    body = json.loads(out)
    assert body["decision"] == "block"
    assert "DECISION block (CLAUDE.md § FINAL OUTPUT)" in body["reason"]
    assert "do it now" in body["reason"]
    events = [
        json.loads(line)
        for f in (tmp_path / "events").rglob("*.jsonl")
        for line in f.read_text(encoding="utf-8").splitlines()
    ]
    blocks = [e for e in events if e.get("event") == "stop_block"]
    assert blocks and blocks[0].get("cause") == "deferral" and blocks[0].get("shape") == "D1"


def test_a_deferral_warns_through_after_three_blocks(monkeypatch, tmp_path: Path) -> None:
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text("Done.\n\nNEXT: your call on the second half"))
    payload = {"session_id": "sidcap", "transcript_path": str(tr)}
    for _ in range(3):
        assert json.loads(_run_main(monkeypatch, tmp_path, payload))["decision"] == "block"
    assert _run_main(monkeypatch, tmp_path, payload) == ""


# --- scope: headless sessions and the payload's own final message -------------------------


def test_headless_env_skips_the_deferral(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CLAUDE_MESH_HEADLESS", "1")
    assert _stall(tmp_path, "Done.\n\nNEXT: operator decision — resume or reshape") is None


def test_an_sdk_cli_session_skips_the_deferral(tmp_path: Path) -> None:
    tr = tmp_path / "t.jsonl"
    _turn(
        tr,
        _user("run the daily pass", entrypoint="sdk-cli"),
        _asst_text("Done.\n\nNEXT: operator decision — resume or reshape"),
    )
    assert hook._detect_stall(str(tr), tmp_path, set()) is None


def test_last_assistant_message_takes_precedence(monkeypatch, tmp_path: Path) -> None:
    """The transcript's last text entry is OLDER than the turn's real final message (the race
    `_final_message_text` works around); the payload's `last_assistant_message` wins."""
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text("Working on it."))
    final = "Done.\n\nNEXT: operator decision — resume or reshape"
    got = hook._detect_stall(str(tr), tmp_path, set(), text=final)
    assert got and got[0] == "deferral:D1"
    out = _run_main(
        monkeypatch,
        tmp_path,
        {"session_id": "sidlam", "transcript_path": str(tr), "last_assistant_message": final},
    )
    assert json.loads(out)["decision"] == "block"


def test_last_assistant_message_alone_is_enough(tmp_path: Path) -> None:
    got = hook._detect_stall("", tmp_path, set(), text="Want me to push it?")
    assert got and got[0] == "deferral:D3"


# --- green: must NOT fire -------------------------------------------------------------------

_GREEN = [
    "Committed.\n\nSTATE: phase 2 of 4 green\nNEXT: awaiting your reply",
    "Committed.\n\nNEXT: none — terminal",
    "Committed.\n\nNEXT: /fabrik-docs-review — the chain is terminal after it",
    "Committed.\n\nNEXT: /fabrik-spec-review docs/superpowers/specs/2026-09-23-x-design.md",
    "Fixed three findings: (a) the parser dropped rows, (b) the regex over-matched, "
    "(c) the test was vacuous. All committed.",
    "Steps done:\n1. rebuilt the index\n2. re-ran the gate\n3. pushed.",
    'You asked "should I keep the old flag?" — yes, it stays; committed.',
    "The guard now refuses `want me to run it?` as a D3 offer.",
    "Should I have caught this earlier? Yes — the grader was vacuous; fixed now.",
    "Do you want the old flag kept? No — it is dead code, so it is removed and committed.",
    "> Shall I run the next pass now?\n\nThat was the old stall shape; it now blocks.",
]


@pytest.mark.parametrize("text", _GREEN)
def test_a_green_message_never_fires(tmp_path: Path, text: str) -> None:
    assert hook.deferral_shape(text) is None, text
    assert _stall(tmp_path, text) is None


@pytest.mark.parametrize(
    "rec", [r for r in _CONTEXT if r["verdict"] == "FALSE-MATCH"], ids=lambda r: r["id"]
)
def test_a_judged_false_match_never_fires(rec: dict) -> None:
    assert hook.deferral_shape(rec["quote"]) is None, rec


@pytest.mark.parametrize("sentence", _prose())
def test_ordinary_prose_about_sessions_never_fires(sentence: str) -> None:
    assert hook.deferral_shape(sentence) is None


@pytest.mark.parametrize(
    "sentence",
    [
        "The fix takes effect in a new session; nothing to do.",
        "Hooks load when you start a new session.",
        "Verified in a fresh session: the hook fires.",
        "The new session will inherit the synced hooks.",
        "A new session runs SessionStart first.",
    ],
)
def test_a_factual_new_session_sentence_never_fires(sentence: str) -> None:
    """A-O40: D4 fires only when the agent hands its OWN work to a later session."""
    assert hook.deferral_shape(sentence) is None


@pytest.mark.parametrize(
    "sentence",
    [
        "The MCP servers load at startup, so open a fresh window to pick up the new roster.",
        "This one needs a new session after the 5h reset lands at 14:40.",
    ],
)
def test_a_window_needed_for_a_reload_or_a_quota_reset_never_fires(sentence: str) -> None:
    """Spec § C1 D4: a fresh window for MCP/roster/reload/quota/5h/weekly/reset is a tool fact."""
    assert hook.deferral_shape(sentence) is None


# --- V1 fixups (the backtest over 16,278 real turn ends; shapes paraphrased, never quoted) --------

_LONG_FOOTER = (
    "```\n"
    "GATE: python scripts/final_gate.py --json → success\n"
    "DOCS UPDATED: docs/FEATURES.md, docs/SERVICES.md, docs/CONFIGURATION.md, INDEX.md, CHANGELOG.md\n"
    "CHANGELOG: Added — the widget export and its retry ledger (2026-09-01)\n"
    "LESSONS LEARNT: none\n"
    "DONE: three commits pushed; 41 tests green; the export runs nightly from the scheduler, "
    "its retry ledger is capped at 500 rows and the dashboard tile shows the last run's status\n"
    "NEXT: none — terminal\n"
    "FEEDBACK: /fabrik-execute-plan · 2h · rounds 3 (4→1→0) · confusion: none · waste: none · "
    "change: none · filed: none — surfaces exercised: the export, the scheduler and the ledger\n"
    "```"
)


@pytest.mark.parametrize(
    ("text", "shape"),
    [
        # the agent's OWN closing footer written inside a trailing fence is not a quotation
        (
            "Plan 4 executed.\n\n```\nGATE: success\nDONE: pushed\n"
            "NEXT: /fabrik-plan-review docs/p5.md — awaiting your go\n```",
            "D1",
        ),
        # a BLOCKED: MENTION mid-line is not the agent's escalation header
        (
            "The earlier review closed `BLOCKED: NON-CONVERGENCE` on its own receipt.\n\n"
            "NEXT: operator decision — resume that review or re-scope it",
            "D1",
        ),
        # the successor named on the NEXT: line is the operator
        ("Nothing to distribute.\n\nNEXT: operator — hand item 6 to the other repo's agent", "D1"),
        # an offer that waits on the operator's word outside a NEXT: line
        ("The revision and its ledger row land on your word.", "D3"),
        # the excuse sits before a closing block that alone runs past the 600-char tail
        ("Phase 1 committed. The rest wants a clean session with a lock.\n\n" + _LONG_FOOTER, "D4"),
        # a context excuse is the diagnosis even when the same message also defers on NEXT:
        ("Findings written.\nNEXT: on your word, I write the memo, then open a new window.", "D4"),
    ],
    ids=[
        "trailing-fenced-footer",
        "blocked-mention-mid-line",
        "next-names-the-operator",
        "on-your-word-in-prose",
        "excuse-before-a-long-footer",
        "d4-wins-over-d1",
    ],
)
def test_a_v1_miss_now_fires(tmp_path: Path, text: str, shape: str) -> None:
    assert hook.deferral_shape(text) == shape, hook._deferral_match(text)
    got = _stall(tmp_path, text)
    assert got and got[0] == f"deferral:{shape}", got


@pytest.mark.parametrize(
    "text",
    [
        "```\nNEXT: operator decision — pick one\n```\n\nThat footer shape is now refused.",
        "BLOCKED: the vendor API — searched: docs/ — missing: auth scheme\n\nNEXT: operator decision — x",
        "Roster changed.\n\nNEXT: operator — reload the window so the MCP roster refreshes",
        "Open a fresh session in /opt/other-repo and run its deploy there.",
        "The MCP roster changed, so anything MCP-dependent needs a new window.",
        "The config fix is committed; it needs a new window to take effect.",
        "Option two, which I'd slightly prefer, is already committed.",
        "Shipped.\n\nNEXT: none — terminal. A cleanup pass is possible if you want it later.",
        "Shipped.\n\nNEXT: none owed — all green. Still open if you want them: (1) docs, (2) a bench.",
        "Shipped.\n\nNEXT: none — terminal. The unrelated migration still awaits your go.",
        "Shipped.\n\nNEXT: operator — optionally rename the dashboard tile; otherwise nothing pending.",
        "Shipped.\n\nNEXT: operator — rename the dashboard tile; otherwise nothing pending.",
    ],
    ids=[
        "quoted-fence-mid-message",
        "blocked-header",
        "operator-line-for-a-reload",
        "fresh-session-in-another-tree",
        "tool-fact-before-the-window",
        "window-to-take-effect",
        "own-preference-is-not-an-offer",
        "next-none-terminal-if-you-want",
        "next-none-owed-still-open",
        "next-none-awaits-your-go",
        "next-operator-optionally",
        "next-operator-otherwise-nothing",
    ],
)
def test_a_v1_green_stays_silent(tmp_path: Path, text: str) -> None:
    assert hook.deferral_shape(text) is None, hook._deferral_match(text)


# --- the T04/T05 interfaces ----------------------------------------------------------------


def test_the_vocabulary_is_one_importable_constant() -> None:
    assert hook._DEFER_RE.search("awaiting the operator's decision")
    assert not hook._DEFER_RE.search("awaiting your reply")
    assert hook._DECISION_GATE_RE.search("UI design approval — the frozen screens")
    assert not hook._DECISION_GATE_RE.search("unpublished draft, a policy about cost and quota")


def _git(cwd: Path, *args: str) -> str:
    import subprocess

    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


def test_session_unpushed_lists_only_this_sessions_commits(tmp_path: Path) -> None:
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "master", str(origin))
    repo = tmp_path / "repo"
    _git(tmp_path, "clone", "-q", str(origin), str(repo))
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "base.txt").write_text("b", encoding="utf-8")
    _git(repo, "add", "base.txt")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "push", "-q", "-u", "origin", "master")
    for name, subject in (("mine.py", "feat: mine"), ("theirs.py", "feat: a sibling's")):
        (repo / name).write_text(name, encoding="utf-8")
        _git(repo, "add", name)
        _git(repo, "commit", "-qm", subject)
    lines = hook.session_unpushed(repo, {"mine.py"})
    assert len(lines) == 1 and lines[0].endswith(" feat: mine"), lines
    assert hook.session_unpushed(repo, set()) == []
    assert hook.session_unpushed(tmp_path, {"mine.py"}) == []  # no repo → indeterminate → []


# --- /fabrik-review round 1 (T03): each confirmed defect, red first --------------------------


def _tool_result_row() -> str:
    return json.dumps(
        {
            "type": "user",
            "message": {"content": [{"type": "tool_result", "content": "ok"}]},
            "toolUseResult": {"stdout": "ok"},
        }
    )


@pytest.mark.parametrize("entrypoint", ["sdk-cli", "sdk-ts", "sdk-py"])
def test_headless_is_read_from_the_last_real_user_row(tmp_path: Path, entrypoint: str) -> None:
    """A-S1/A-O6: the last `"user"` line is often a tool result carrying no entrypoint; the
    session's entrypoint is read from the last REAL user row, and every `sdk-*` is headless."""
    tr = tmp_path / "t.jsonl"
    _turn(
        tr,
        _user("run the nightly pass", entrypoint=entrypoint),
        _asst_tool("Bash", command="ls"),
        _tool_result_row(),
        _asst_text("Done.\n\nNEXT: operator decision — resume or reshape"),
    )
    assert hook._detect_stall(str(tr), tmp_path, set()) is None


def test_hook_injected_rows_are_never_the_operator(tmp_path: Path) -> None:
    """A-O1: a machine-append row (Stop-hook feedback, a mesh notification) is not the operator's."""
    q = "should the retention window be 30 days or 90?"
    tr = tmp_path / "t.jsonl"
    text = _block("owned", f'owned — asked: "{q}"')
    _turn(tr, _user("go"), _user(f"Stop hook feedback: {q}"), _asst_text(text))
    got = hook._detect_stall(str(tr), tmp_path, set())
    assert got and got[0] == "deferral:block" and "operator" in got[1]


def test_the_machine_append_marks_mirror_the_coroner() -> None:
    """A-O1: the hook cannot import `kaizen_coroner` (a hook import that can fail degrades every
    cause), so it MIRRORS its list; this pins the mirror to the source."""
    spec = importlib.util.spec_from_file_location(
        "kaizen_coroner_probe", REPO / "scripts" / "sysadmin" / "kaizen_coroner.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # its dataclasses resolve their module by name
    spec.loader.exec_module(mod)
    assert set(mod.MACHINE_APPEND_MARKS) <= set(hook._NOT_OPERATOR_PREFIXES)


def test_a_malformed_row_is_skipped_not_fatal(tmp_path: Path) -> None:
    """A-O13: a row whose `message` is not a dict used to raise out of the whole DEFERRAL check."""
    tr = tmp_path / "t.jsonl"
    text = _block("owned", 'owned — asked: "is the retention window seven days or one?"')
    _turn(
        tr,
        json.dumps({"type": "user", "message": "a bare string"}),
        _user("fix the retention bug"),
        _asst_text(text),
    )
    got = hook._detect_stall(str(tr), tmp_path, set())
    assert got and got[0] == "deferral:block", got


@pytest.mark.parametrize(
    "text",
    [
        "Done.\n\n> NEXT: operator decision — resume or reshape",
        "Done.\n\nNEXT: 'your call' — merge or hold the branch",
    ],
    ids=["blockquoted-next", "quote-before-the-term"],
)
def test_a_next_line_is_always_the_agents_own(text: str) -> None:
    """A-O2/A-O10: a NEXT: line is the agent's footer; only a non-trailing fence quotes it."""
    assert hook.deferral_shape(text) == "D1", hook._deferral_match(text)


def test_a_footer_fence_followed_by_one_prose_line_is_still_the_footer() -> None:
    """A-O9: the LAST fence holding a NEXT: line, with no fence after it, is the agent's footer."""
    text = (
        "Plan 4 executed.\n\n```\nGATE: success\nNEXT: operator decision — resume or reshape\n```\n"
        "One more note about the logs."
    )
    assert hook.deferral_shape(text) == "D1", hook._deferral_match(text)


def test_a_word_starting_with_no_is_not_an_answer() -> None:
    """A-O3: 'Note', 'Now', 'Yesterday' after a question are not its answer."""
    text = "Shall I run the next pass now? Note: the queue is empty."
    assert hook.deferral_shape(text) == "D3", hook._deferral_match(text)


@pytest.mark.parametrize(
    "text",
    [
        "```\nBLOCKED: an example header in a how-to\n```\n\nNEXT: operator decision — pick",
        "UN-BLOCKED: the lane is free again.\n\nNEXT: operator decision — pick",
        "NOT-BLOCKED: nothing waits.\n\nNEXT: operator decision — pick",
    ],
    ids=["fenced-header", "un-blocked", "not-blocked"],
)
def test_only_a_real_blocked_header_exempts(text: str) -> None:
    """A-O4: the header must sit outside a quoting fence, and only `BLOCKED:` (optionally behind a
    ticket id, `T03 BLOCKED:` / `T1a-BLOCKED:`, or markdown) is one."""
    assert hook.deferral_shape(text) == "D1", hook._deferral_match(text)


@pytest.mark.parametrize(
    "text",
    [
        "T03 BLOCKED: no DSN\n\nNEXT: operator decision — x",
        "T1a-BLOCKED: no DSN\n\nNEXT: operator decision — x",
        "## BLOCKED: no DSN\n\nNEXT: x — your call",
    ],
    ids=["ticket-space", "ticket-hyphen", "heading"],
)
def test_a_ticket_or_heading_blocked_header_still_exempts(text: str) -> None:
    assert hook.deferral_shape(text) is None


@pytest.mark.parametrize(
    ("why", "user"),
    [
        (
            "owned — asked: 'what's the retention window we keep?'",
            "what's the retention window we keep?",
        ),
        (
            "owned — asked: what's the retention window we keep? (still open)",
            "what's the retention window we keep?",
        ),
    ],
    ids=["single-quoted-with-apostrophe", "unquoted-up-to-the-question-mark"],
)
def test_an_asked_quote_survives_an_apostrophe_and_trailing_prose(
    tmp_path: Path, why: str, user: str
) -> None:
    """A-O7: a mid-word apostrophe is not a closing quote; an unquoted asked: ends at its `?`."""
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(f"Look at the purge job. {user}"), _asst_text("x"))
    assert hook.parse_decision_block(
        _block("owned", why), run_live=False, transcript_path=str(tr)
    ) == (True, "owned")


@pytest.mark.parametrize(
    "text",
    [
        "Done.\n\nNEXT: operator — merge the branch; optionally tidy the docs",
        "Done.\n\nNEXT: operator — rerun the ingest; no reload needed",
    ],
    ids=["optional-later-on-the-line", "negated-tool-word"],
)
def test_the_operator_waiver_is_narrow(text: str) -> None:
    """A-O8: only an operator clause that BEGINS optional, ends 'otherwise nothing pending', or
    asks for a reload/restart is waived."""
    assert hook.deferral_shape(text) == "D1", hook._deferral_match(text)


def test_the_operator_tool_ask_is_case_insensitive() -> None:
    text = "Done.\n\nNEXT: operator — Reload the window so the new mcp server loads"
    assert hook.deferral_shape(text) is None


@pytest.mark.parametrize(
    "heading",
    [
        "**DECISION NEEDED (ground: gate)**",
        "⚠️ DECISION NEEDED (ground: gate)",
        "DECISION NEEDED (ground: gate):",
        "DECISION NEEDED (ground: `gate`)",
    ],
    ids=["bold", "emoji", "trailing-colon", "backticked-ground"],
)
def test_the_heading_tolerates_near_misses(heading: str) -> None:
    """A-O11: the near-misses agents write still parse; a fenced heading still never counts."""
    text = _GATE_BLOCK.replace("DECISION NEEDED (ground: gate)", heading, 1)
    assert hook.parse_decision_block(text, run_live=False, transcript_path="") == (True, "gate")


def test_a_blockquoted_block_never_exempts(tmp_path: Path) -> None:
    """A-O14: a `>`-quoted DECISION block is discussed text, like a fenced one."""
    quoted = "\n".join(
        ("> " + ln) if ln.startswith(("DECISION", "- ")) else ln for ln in _GATE_BLOCK.split("\n")
    )
    assert hook.extract_decision_block(quoted) is None
    got = _stall(tmp_path, quoted)
    assert got and got[0] == "deferral:D1"


def test_the_promise_reason_does_not_offer_the_decision_block(monkeypatch, tmp_path: Path) -> None:
    """A-O12: the promise/obligation loops never consult a DECISION block, so their reason names
    only 'do it now, or BLOCKED:'."""
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(), _asst_text("I'll run the confirming pass now."))
    out = _run_main(monkeypatch, tmp_path, {"session_id": "sidpr", "transcript_path": str(tr)})
    body = json.loads(out)
    assert "STALL" in body["reason"] and "BLOCKED:" in body["reason"]
    assert "DECISION" not in body["reason"], body["reason"]


def _words(s: str) -> list[str]:
    import re

    return re.findall(r"[a-z0-9']+", s.lower().replace("’", "'"))


def test_no_fixture_copies_a_committed_quote() -> None:
    """B-S1/B-S2/B-H1: the judged quotes are excerpts of real operator transcripts; a fixture is
    a paraphrase of their SHAPE, never a copy. No string in this file shares a 6-word run with any
    committed `quote` (the files are read at runtime, never pasted)."""
    grams: set[tuple[str, ...]] = set()
    for f in sorted(RESEARCH.glob("verdict-*.json")):
        for r in json.loads(f.read_text(encoding="utf-8")):
            w = _words(str(r.get("quote") or ""))
            grams |= {tuple(w[i : i + 6]) for i in range(len(w) - 5)}
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            w = _words(node.value)
            shared = {tuple(w[i : i + 6]) for i in range(len(w) - 5)} & grams
            if shared:
                hits.append((node.lineno, " ".join(sorted(shared)[0])))
    assert not hits, hits


# --- /fabrik-review round 2 (T03): the four residues of round 1, red first ------------------


@pytest.mark.parametrize(
    "text",
    [
        "Done.\n\nNEXT: operator — restart the payment worker on vps2 after you approve the migration",
        "Done.\n\nNEXT: operator — reload the ingest service config, then re-run the import",
        "Done.\n\nNEXT: operator — open the deploy for vps3 and watch the rollout",
    ],
    ids=["restart-a-worker", "reload-a-service", "open-a-deploy"],
)
def test_the_waiver_is_only_the_tool_reload_class(text: str) -> None:
    """A-O15: a reload/restart/open verb is waived only when its object is a window, session, VS
    Code, the editor, MCP or the roster — never a service, worker, deploy or VPS."""
    assert hook.deferral_shape(text) == "D1", hook._deferral_match(text)


@pytest.mark.parametrize(
    ("label", "value", "said"),
    [
        (
            "asked",
            "'do the users' retention windows need 90 days?'",
            "do the users' retention windows need 90 days?",
        ),
        ("scope", "'the admins' pages only'; nothing else", "the admins' pages only"),
    ],
    ids=["asked-plural-possessive", "scope-plural-possessive"],
)
def test_a_plural_possessive_is_not_the_closing_quote(
    tmp_path: Path, label: str, value: str, said: str
) -> None:
    """A-O18: `users' ` is a possessive, not the close of a single-quoted value."""
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user(f"Check the purge job. {said}"), _asst_text("x"))
    block = _block("owned", f"owned — {label}: {value}")
    assert hook.parse_decision_block(block, run_live=False, transcript_path=str(tr)) == (
        True,
        "owned",
    )


@pytest.mark.parametrize(
    "text",
    [
        "P21-A-BLOCKED: no DSN in the env\n\nNEXT: operator decision — x",
        "A-L3-BLOCKED: no DSN in the env\n\nNEXT: operator decision — x",
    ],
    ids=["plan-ticket-id", "lane-id"],
)
def test_an_id_with_a_digit_before_blocked_exempts(text: str) -> None:
    """A-O17: any id token containing a digit before `-BLOCKED:` is a header; a word is not."""
    assert hook.deferral_shape(text) is None


@pytest.mark.parametrize(
    "text",
    [
        'Done.\n\nNEXT: /fabrik-review — then fix the "your call" phrasing in the docs',
        "Done.\n\nNEXT: /fabrik-docs-review — reword the `awaiting your go` example",
    ],
    ids=["double-quoted-data", "backticked-data"],
)
def test_a_quoted_phrase_on_a_next_line_is_data(text: str) -> None:
    """A-O16: a deferral phrase ENCLOSED in a paired quote or code span on a NEXT: line is quoted
    data; a lone quote character or an apostrophe still does not skip (A-O10)."""
    assert hook.deferral_shape(text) is None, hook._deferral_match(text)


# --- /fabrik-review round 3 (T03): the rewritten helpers, one scenario per seat finding ------


@pytest.mark.parametrize(
    "clause",
    [
        "restart the worker session after the queue drains",
        "restart the ingest session broker on vps1",
        "restart the vps2 editor-proxy service",
        "restart the session broker on vps1",
    ],
    ids=["worker-session", "session-broker", "editor-proxy-service", "direct-object-not-whole"],
)
def test_a_service_hand_off_is_never_waived(clause: str) -> None:
    """A-O19/A-O20: the waiver's object is the verb's DIRECT object; anything else is a hand-off."""
    text = f"Done.\n\nNEXT: operator — {clause}"
    assert hook.deferral_shape(text) == "D1", hook._deferral_match(text)


@pytest.mark.parametrize(
    "clause",
    [
        "refresh the window",
        "reload the window so the roster refreshes",
        "reload MCP, then retry the search",
        "open a fresh VS Code window for the new roster",
    ],
    ids=["refresh-window", "reload-window", "reload-mcp", "open-fresh-window"],
)
def test_a_tool_reload_phrase_is_waived(clause: str) -> None:
    text = f"Done.\n\nNEXT: operator — {clause}"
    assert hook.deferral_shape(text) is None, hook._deferral_match(text)


@pytest.mark.parametrize(
    ("label", "why", "want"),
    [
        (
            "scope",
            "owned — scope: 'the admins' pages — list only'",
            "the admins' pages — list only",
        ),
        ("asked", "owned — asked: 'ship it?' then I said 'ok?'", "ship it?"),
        ("scope", "owned — scope: 'the users' data'", "the users' data"),
        (
            "asked",
            "owned — asked: 'do the users' logs need 90 days?'",
            "do the users' logs need 90 days?",
        ),
        (
            "scope",
            "owned — scope: 'the admins' pages only'; nothing else",
            "the admins' pages only",
        ),
        ("asked", "owned — asked: what's the plan here? (still open)", "what's the plan here?"),
        ("scope", "owned — scope: only the parser — nothing else", "only the parser"),
    ],
    ids=[
        "possessive-then-dash",
        "first-quoted-span-wins",
        "possessive-in-the-middle",
        "asked-possessive",
        "scope-possessive-then-semicolon",
        "unquoted-asked",
        "unquoted-scope",
    ],
)
def test_the_quote_is_tokenised(label: str, why: str, want: str) -> None:
    """A-O21/A-O22/A-O23: the value is the leading quoted span (a possessive `s'` never closes it,
    the first closing quote wins), else the unquoted clause; never a delimiter."""
    assert hook._decision_quote(why, label) == want


def test_an_inch_mark_never_encloses() -> None:
    """A-O24: a `"` glued to a digit is an inch mark, not an opener; the deferral outside the one
    real `"…"` span still fires."""
    text = 'Done.\n\nNEXT: /fabrik-x — the 12" panel; your call, then "y"'
    assert hook.deferral_shape(text) == "D1", hook._deferral_match(text)


def test_a_count_before_blocked_is_not_a_header() -> None:
    """A-O25: the id before BLOCKED: starts with a letter; `- 2 BLOCKED: …` is a count."""
    text = "- 2 BLOCKED: T04, T05\n\nNEXT: operator decision — which first"
    assert hook.deferral_shape(text) == "D1", hook._deferral_match(text)


@pytest.mark.parametrize(
    ("label", "why", "want"),
    [
        ("scope", "owned — scope: 'list the users' then I said 'all'", "list the users"),
        ("asked", "owned — asked: 'ship the fixes' then 'ok'", "ship the fixes"),
        ("scope", "owned — scope: 'the admin pages' — then I said 'all'", "the admin pages"),
    ],
    ids=["s-quote-before-a-later-quote", "asked-s-quote", "s-quote-then-dash"],
)
def test_a_value_ending_in_s_closes_before_a_later_quote(label: str, why: str, want: str) -> None:
    """A-O22 remainder: the closer is the LAST valid closing quote BEFORE the first later opening
    quote, so a value ending in `s` closes and the later quoted text is never absorbed."""
    assert hook._decision_quote(why, label) == want


# --- whole-plan review (T06): the DECISION block is stored and judged only where it belongs -----

_PUBLISH_BLOCK = (
    "The docs rebuild is staged.\n\n"
    "DECISION NEEDED (ground: gate)\n"
    "- Question: Publish the rebuilt handbook site today?\n"
    "- Why it is yours: gate — publish, the public handbook changes for every reader.\n"
    "- Options: A — publish at once · B — wait for the typo sweep first\n"
    "- Recommendation: A — the sweep found nothing blocking.\n\n"
    "NEXT: operator decision — see DECISION NEEDED above"
)


def _asst_edit(path: Path) -> str:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    return json.dumps(
        {
            "type": "assistant",
            "timestamp": stamp,
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Write", "input": {"file_path": str(path)}}
                ]
            },
        }
    )


def _proj_with_upstream(tmp_path: Path, *, pushed: bool) -> Path:
    """A fabrik-style repo with an upstream and one committed note this session wrote; `pushed`
    decides whether that commit is still ahead of origin (the UNPUSHED cause blocks) or not."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "master", str(origin))
    proj = tmp_path / "proj"
    _git(tmp_path, "clone", "-q", str(origin), str(proj))
    _git(proj, "config", "user.email", "t@example.com")
    _git(proj, "config", "user.name", "t")
    (proj / "scripts").mkdir()
    (proj / "scripts" / "final_gate.py").write_text("", encoding="utf-8")
    _git(proj, "add", "scripts/final_gate.py")
    _git(proj, "commit", "-qm", "base")
    _git(proj, "push", "-q", "-u", "origin", "master")
    (proj / "notes.txt").write_text("a note", encoding="utf-8")
    _git(proj, "add", "notes.txt")
    _git(proj, "commit", "-qm", "docs: a note")
    if pushed:
        _git(proj, "push", "-q")
    return proj


def _drive(monkeypatch, tmp_path: Path, proj: Path, sid: str, tr: Path) -> str:
    payload = {"cwd": str(proj), "session_id": sid, "transcript_path": str(tr)}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(hook.tempfile, "gettempdir", lambda: str(tmp_path))
    assert hook.main([]) == 0
    return out.getvalue().strip()


def _stored_decision(tmp_path: Path, sid: str) -> object:
    f = tmp_path / "threads" / f"{sid}.json"
    return json.loads(f.read_text(encoding="utf-8")).get("decision") if f.exists() else None


def _events(tmp_path: Path, name: str) -> list[dict]:
    return [
        e
        for f in (tmp_path / "events").rglob("*.jsonl")
        for e in (json.loads(ln) for ln in f.read_text(encoding="utf-8").splitlines())
        if e.get("event") == name
    ]


@pytest.mark.parametrize("pushed", [False, True], ids=["blocked-unpushed", "allowed-clean"])
def test_a_decision_block_is_stored_only_when_the_stop_is_allowed(
    monkeypatch, tmp_path: Path, pushed: bool
) -> None:
    """A-O1: a Stop that BLOCKS keeps the agent working with no UserPromptSubmit to clear the
    block, so storing it there leaves a stale OPEN DECISION for WHERE YOU ARE after a compaction."""
    proj = _proj_with_upstream(tmp_path, pushed=pushed)
    tr = tmp_path / "t.jsonl"
    _turn(
        tr,
        _user("stage the handbook rebuild"),
        _asst_edit(proj / "notes.txt"),
        _asst_text(_PUBLISH_BLOCK),
    )
    out = _drive(monkeypatch, tmp_path, proj, "sidstore", tr)
    if pushed:
        assert out == ""
        dec = _stored_decision(tmp_path, "sidstore")
        assert isinstance(dec, dict) and "Publish the rebuilt handbook" in dec["text"]
    else:
        assert "UNPUSHED WORK" in json.loads(out)["reason"]
        assert _stored_decision(tmp_path, "sidstore") is None


def test_a_decision_block_is_not_stored_while_a_run_record_blocks(
    monkeypatch, tmp_path: Path
) -> None:
    """A-O1, the run-record cause: a `gate` block passes inside a live run, and the run blocks."""
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user("stage the handbook rebuild"), _asst_text(_PUBLISH_BLOCK))
    _write_run(tmp_path, "sidlive", "running")
    out = _run_main(monkeypatch, tmp_path, {"session_id": "sidlive", "transcript_path": str(tr)})
    assert json.loads(out)["decision"] == "block"
    assert _stored_decision(tmp_path, "sidlive") is None


def test_a_previous_turns_block_is_never_judged_for_this_turn(monkeypatch, tmp_path: Path) -> None:
    """A-O2: no `last_assistant_message` and this turn ends on a textless tool call — the block in
    the PREVIOUS turn (before the operator's prompt) is neither an event nor stored."""
    tr = tmp_path / "t.jsonl"
    _turn(
        tr,
        _user("stage the handbook rebuild"),
        _asst_text(_PUBLISH_BLOCK),
        _user("go ahead and publish it"),
        _asst_tool("Bash", command="true"),
    )
    out = _run_main(monkeypatch, tmp_path, {"session_id": "sidprev", "transcript_path": str(tr)})
    assert out == ""
    assert _events(tmp_path, "decision_block") == []
    assert _stored_decision(tmp_path, "sidprev") is None


def test_a_block_before_a_textless_final_entry_is_still_judged(monkeypatch, tmp_path: Path) -> None:
    """A-O2's own-fix residue: the block sits in an EARLIER text entry of THIS turn and the turn
    ends on a textless tool call — it is this turn's last text, so it is judged and stored."""
    tr = tmp_path / "t.jsonl"
    _turn(
        tr,
        _user("stage the handbook rebuild"),
        _asst_text(_PUBLISH_BLOCK),
        _asst_tool("Bash", command="true"),
    )
    out = _run_main(monkeypatch, tmp_path, {"session_id": "sidlate", "transcript_path": str(tr)})
    assert out == ""
    assert [e.get("ground") for e in _events(tmp_path, "decision_block")] == ["gate"]
    assert isinstance(_stored_decision(tmp_path, "sidlate"), dict)


def test_this_turns_block_is_still_judged_from_the_transcript(monkeypatch, tmp_path: Path) -> None:
    """A-O2's mirror: with no payload message, THIS turn's own final text still carries its block."""
    tr = tmp_path / "t.jsonl"
    _turn(tr, _user("stage the handbook rebuild"), _asst_text(_PUBLISH_BLOCK))
    out = _run_main(monkeypatch, tmp_path, {"session_id": "sidthis", "transcript_path": str(tr)})
    assert out == ""
    assert [e.get("ground") for e in _events(tmp_path, "decision_block")] == ["gate"]
    assert isinstance(_stored_decision(tmp_path, "sidthis"), dict)
