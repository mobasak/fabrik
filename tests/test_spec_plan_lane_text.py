"""T05b — `/fabrik-spec` and `/fabrik-plan-after-chat` command TEXT for the lane's D9/D10/D11 half.

These are prose graders, not code graders: `/fabrik-task` lane admission and the DOWNGRADE/Size/Appetite
MECHANISMS live in `command_run.py` and the plan graders (other tickets of this plan). This ticket's job is
the two command SOURCES a cold agent reads to drive those mechanisms correctly — each grader proves the
instruction a reader needs is actually THERE, scoped to the right phase/section so a stray mention
elsewhere in either 400+-line file does not pass a test that should be reading the wrong paragraph.

Behavior Contract (ticket T05b):
  1. `/fabrik-spec` Phase 0 orders the DOWNGRADE handoff with `--resume`, the refusal id in the reason, and
     the `/fabrik-task --from-downgrade <id>` restart in the seed (spec sec:The-delta D9).
  2. `/fabrik-spec` Phase 5 writes `Size: small` for a spec whose deltas estimate <= ~400 code lines and
     <= 5 code files, and hands it straight to `/fabrik-plan-after-chat` (spec sec:The-delta D10).
  3. `/fabrik-plan-after-chat`'s approval-row step mints no approval row for a `Size: small` spec, and its
     emit rule requires `Appetite: <minutes>` on every phase/ticket (spec sec:The-delta D10, D11).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPEC_MD = REPO / "commands" / "_sources" / "fabrik-spec.md"
PLAN_MD = REPO / "commands" / "_sources" / "fabrik-plan-after-chat.md"


def _section(text: str, start_pat: str, end_pat: str) -> str:
    """The text strictly between the first line matching `start_pat` and the first later line
    matching `end_pat` (or EOF). Keeps a grader honest about WHICH phase it read."""
    lines = text.splitlines()
    start = end = None
    for i, line in enumerate(lines):
        if start is None and re.search(start_pat, line):
            start = i
            continue
        if start is not None and re.search(end_pat, line):
            end = i
            break
    assert start is not None, f"no line matches start pattern {start_pat!r}"
    if end is None:
        end = len(lines)
    return "\n".join(lines[start:end])


def _spec_phase0() -> str:
    text = SPEC_MD.read_text(encoding="utf-8")
    return _section(text, r"^## Phase 0 —", r"^## Phase 1 —")


def _spec_phase5() -> str:
    text = SPEC_MD.read_text(encoding="utf-8")
    return _section(text, r"^## Phase 5 —", r"^## Phase 6 —")


def _spec_phase6() -> str:
    text = SPEC_MD.read_text(encoding="utf-8")
    return _section(text, r"^## Phase 6 —", r"^## Guardrails")


def _plan_phase0() -> str:
    text = PLAN_MD.read_text(encoding="utf-8")
    return _section(text, r"^## Phase 0 —", r"^## Phase 0\.5 —")


def _plan_phase2() -> str:
    text = PLAN_MD.read_text(encoding="utf-8")
    return _section(text, r"^## Phase 2 —", r"^## Phase 3 —")


# ---------------------------------------------------------------------------
# Behavior 1 — /fabrik-spec Phase 0: the DOWNGRADE handoff ordering (D9)
# ---------------------------------------------------------------------------


def test_fabrik_spec_phase0_orders_downgrade_check_before_other_work():
    """The DOWNGRADE check must be read before the rest of Phase 0 — it decides whether a spec
    gets written at all. Scoped to the Phase 0 section so a D9 mention elsewhere (e.g. the
    Interfaces digest copied into a ticket) can never satisfy this."""
    phase0 = _spec_phase0()
    assert "DOWNGRADE check (BLOCKING" in phase0, phase0


def test_fabrik_spec_phase0_downgrade_handoff_uses_resume_flag():
    """D9: `command_run.py:2706-2713` makes `--resume` REQUIRED on `handoff` — the text must drive
    the real flag, not an invented shortcut."""
    phase0 = _spec_phase0()
    assert "--resume" in phase0
    assert "handoff" in phase0
    assert "--command fabrik-spec" in phase0


def test_fabrik_spec_phase0_downgrade_reason_carries_the_refusal_id():
    """D9: the handoff's `--reason` must read `DOWNGRADE: <refusal id> — ...` so
    `command_feedback_report.py` can join downgraded runs back to their refusal."""
    phase0 = _spec_phase0()
    assert re.search(r'--reason\s+"DOWNGRADE:\s*<[^>]*refusal id[^>]*>', phase0), phase0


def test_fabrik_spec_phase0_seed_names_fabrik_task_from_downgrade_restart():
    """D9: the seed's own `## RESUME` block must name the exact restart —
    `/fabrik-task --from-downgrade <refusal id>` — so the operator lands on the right command."""
    phase0 = _spec_phase0()
    assert re.search(r"/fabrik-task\s+--from-downgrade\s+<[^>]*refusal id[^>]*>", phase0), phase0
    assert "## RESUME" in phase0


def test_fabrik_spec_phase0_downgrade_requires_one_reversible_decision_no_tradeoff():
    """D9: the downgrade fires only when the brief settles one reversible decision with no open
    trade-off — a text that omits this condition would downgrade EVERYTHING."""
    phase0 = _spec_phase0()
    assert "one reversible decision" in phase0
    assert "trade-off" in phase0 or "tradeoff" in phase0


# ---------------------------------------------------------------------------
# Behavior 2 — /fabrik-spec Phase 5: `Size: small` + straight handoff (D10)
# ---------------------------------------------------------------------------


def test_fabrik_spec_phase5_writes_size_small_line_under_status():
    phase5 = _spec_phase5()
    assert "`Size: small" in phase5 or "Size: small" in phase5
    assert "under `Status:`" in phase5 or "under Status" in phase5


def test_fabrik_spec_phase5_size_small_trigger_matches_d169_rule():
    """D10 reuses D-169's exact bound — 400 code lines, 5 code files — the same test
    `/fabrik-plan-after-chat` applies to a plan, so the two never silently drift apart."""
    phase5 = _spec_phase5()
    assert "400 code lines" in phase5
    assert "5 code files" in phase5


def test_fabrik_spec_phase5_size_small_skips_spec_review_and_hands_off_to_plan_after_chat():
    phase5 = _spec_phase5()
    assert "skips `/fabrik-spec-review`" in phase5
    assert "/fabrik-plan-after-chat" in phase5


def test_fabrik_spec_phase5_status_draft_sentence_carries_the_small_spec_exception():
    """The `:324-325`-era sentence ('/fabrik-spec-review flips it to CONVERGED') must gain the
    exception stating WHO flips a `Size: small` spec instead, so the two paragraphs cannot
    contradict each other."""
    phase5 = _spec_phase5()
    status_sentence = _section(phase5, r"Open the spec with", r"\*\*`Profile: delta`")
    assert "except a `Size: small` spec" in status_sentence
    assert "/fabrik-plan-review" in status_sentence


def test_fabrik_spec_phase6_size_small_skips_the_mandatory_spec_review_call():
    """Phase 6 unconditionally invoked `/fabrik-spec-review` before this ticket; a `Size: small`
    spec must now skip that call rather than running it twice (once implicitly via Phase 5's
    text, once explicitly here)."""
    phase6 = _spec_phase6()
    assert "Size: small" in phase6
    normalized = re.sub(r"\s+", " ", phase6)
    assert "do NOT invoke `/fabrik-spec-review`" in normalized
    assert "/fabrik-plan-after-chat" in phase6


# ---------------------------------------------------------------------------
# Behavior 3 — /fabrik-plan-after-chat: no approval row + required Appetite (D10, D11)
# ---------------------------------------------------------------------------


def test_fabrik_plan_after_chat_size_small_mints_no_approval_row():
    """D10: for a `Size: small` spec, `/fabrik-spec-review` never minted the approval row (it
    never ran), and `/fabrik-plan-after-chat` must NOT mint it here either — `/fabrik-plan-review`
    mints it later, at its own approval gate."""
    phase0 = _plan_phase0()
    assert "Size: small" in phase0
    assert re.search(r"does NOT apply|mint NO approval row", phase0)
    assert "/fabrik-plan-review" in phase0


def test_fabrik_plan_after_chat_approval_exception_is_scoped_to_the_mint_paragraph():
    """The exception must sit next to the mint rule it overrides, not float free elsewhere in
    Phase 0 — otherwise a reader can miss which rule it modifies."""
    phase0 = _plan_phase0()
    mint_idx = phase0.index("mint it HERE before planning")
    exception_idx = phase0.index("Exception — a `Size: small` spec")
    assert 0 < exception_idx - mint_idx < 400, (mint_idx, exception_idx)


def test_fabrik_plan_after_chat_emit_rule_requires_appetite_per_phase_or_ticket():
    """D11: every phase (monolith) or ticket (spine+ticket set) must carry `Appetite: <minutes>` —
    scoped to Phase 2 (the emit rule) so a stray `Appetite` mention elsewhere cannot pass this."""
    phase2 = _plan_phase2()
    assert "Appetite: <minutes>" in phase2
    assert "every phase" in phase2.lower() or "every phase or ticket" in phase2.lower()


def test_fabrik_plan_after_chat_appetite_applies_to_both_shapes_every_profile():
    """D11 binds every plan, not just `Profile: small` — the Appetite rule must sit OUTSIDE the
    small-profile paragraph it follows, not nested inside it."""
    phase2 = _plan_phase2()
    appetite_para = _section(
        phase2, r"Appetite: <minutes>.*spec § The delta D11", r"SHAPE DECISION FIRST"
    )
    assert "check_plan_tickets.py" in appetite_para
    assert "check_plan_quality.py" in appetite_para
    assert "over_appetite_phases" in appetite_para
