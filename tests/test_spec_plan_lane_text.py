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

Round 1 review fix (findings T05b-S1, T05b-S2 — both CONFIRMED, orchestrator rulings applied):
  S1. Phase 5's self-review closing bullet ('... /fabrik-spec-review convergence runs BEFORE the user
      approves') was an UNCONDITIONAL claim, directly contradicted by Phase 6's own `Size: small` exception
      two lines later (which skips that call entirely). Fixed: the bullet is now conditional on
      full-profile, and names the `Size: small` exception explicitly.
  S2. The DOWNGRADE bullet named `--resume <seed>` without ever instructing the agent to WRITE that seed
      file to disk first — `command_run.py`'s real `handoff` implementation REFUSES (rc 1) a `--resume`
      path that is not already a regular file carrying a `## RESUME` heading (`:4746-4756`). Fixed: the
      bullet now orders writing the seed file FIRST (path, `## RESUME` heading, refusal id, brief) and
      only then running `handoff --resume` against it.
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


# ---------------------------------------------------------------------------
# Round-1 review fix — T05b-S1: Phase 5's closing bullet must be CONDITIONAL on size
# ---------------------------------------------------------------------------


def test_fabrik_spec_phase5_closing_handoff_sentence_is_conditional_on_size():
    """T05b-S1 (CONFIRMED): the un-edited bullet claimed UNCONDITIONALLY that
    `/fabrik-spec-review` convergence runs before user approval, directly contradicted by Phase 6's
    own `Size: small` exception two lines later. The fixed sentence must scope the claim to a
    full-profile spec and name the `Size: small` exception in the same breath, so a cold reader
    cannot invoke `/fabrik-spec-review` and then invoke `/fabrik-plan-after-chat` too."""
    phase5 = _spec_phase5()
    closing = _section(phase5, r"After the self-review, go straight to Phase 6", r"^## Phase 6")
    assert "for a full-profile spec" in closing
    assert "Exception — a `Size: small` spec" in closing
    assert "/fabrik-plan-after-chat" in closing


def test_fabrik_spec_phase5_closing_sentence_never_claims_review_runs_unconditionally():
    """A regression guard for the exact contradiction the refuter found: the OLD text had no
    qualifier at all before 'the independent `/fabrik-spec-review` convergence runs BEFORE the
    user' — that bare unconditional phrase must not reappear."""
    phase5 = _spec_phase5()
    normalized = re.sub(r"\s+", " ", phase5)
    assert "go straight to Phase 6 — the independent `/fabrik-spec-review`" not in normalized


# ---------------------------------------------------------------------------
# Round-1 review fix — T05b-S2: the DOWNGRADE bullet must order WRITING the seed file first
# ---------------------------------------------------------------------------


def test_fabrik_spec_phase0_downgrade_instructs_writing_seed_file_before_handoff():
    """T05b-S2 (CONFIRMED): `command_run.py`'s real `handoff` implementation REFUSES (rc 1) a
    `--resume` path that does not already exist as a regular file carrying a `## RESUME` heading
    (`command_run.py`'s handoff branch) — the bullet must instruct WRITING that file (path, `## RESUME`
    heading, refusal id, the brief) before the handoff command, not just name the command."""
    phase0 = _spec_phase0()
    assert "WRITE the seed file to disk FIRST" in phase0
    assert "(`command_run.py`'s `handoff` branch — grep `## RESUME`)" in " ".join(phase0.split())
    assert "command_run.py:4746-4756" not in phase0, "a line range into command_run.py drifts"
    write_idx = phase0.index("WRITE the seed file to disk FIRST")
    handoff_idx = phase0.index("python3 scripts/command_run.py handoff")
    assert write_idx < handoff_idx, "the write instruction must precede the handoff command"


def test_fabrik_spec_phase0_downgrade_write_instruction_names_resume_heading_and_refusal_id():
    """The written seed must carry the exact `## RESUME` heading + restart + refusal id — not a
    vague 'write something' — or a cold agent still cannot build a file `handoff` accepts."""
    phase0 = _spec_phase0()
    write_sentence = _section(
        phase0, r"WRITE the seed file to disk FIRST", r"Only THEN close this run"
    )
    assert "## RESUME" in write_sentence
    assert "/fabrik-task --from-downgrade <refusal id>" in write_sentence
    assert "refusal id" in write_sentence


def test_fabrik_spec_names_both_endings_and_a_sanctioned_close(tmp_path, monkeypatch) -> None:
    """/fabrik-spec queue (kaizen D-711 audit, 9 rows): `--terminal` is fixed at start, the
    `Size: small` verdict that decides where the run ends lands in Phase 5, and command_run.py
    refuses `--terminal-amend` outside /fabrik-task -- so the text names both endings, right after
    the run-record `start` block. Also: Phase 4 no longer stops per section, Phase 6's "stop" has a
    sanctioned close, the NEXT map names the Size: small branch, and a hard seat cap is honoured."""
    import importlib.util
    import subprocess
    import sys

    def norm(t: str) -> str:
        return " ".join(t.split())

    both = ("**`--terminal` names both endings:** the `Size:` verdict lands in Phase 5 and `--terminal-amend` "
            "belongs to `/fabrik-task` alone, so start with `--terminal \"the spec CONVERGED by /fabrik-spec-review "
            "and its approval gate answered, or — when Phase 5 writes Size: small — the DRAFT handed to "
            "/fabrik-plan-after-chat\"`.")
    spec = importlib.util.spec_from_file_location("asm_spec_probe", REPO / "commands" / "assemble_commands.py")
    asm = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(asm)
    asm.render(tmp_path / "r", tmp_path / "r" / "_skills", agents_dest=tmp_path / "r" / "_agents")
    rendered = norm((tmp_path / "r" / "fabrik-spec.md").read_text(encoding="utf-8"))
    start = rendered.index("python3 scripts/command_run.py start --command fabrik-spec")
    at = rendered.index(both)
    assert at < start, "the both-endings rule must come before the start block it governs"
    assert ("Close it EXACTLY ONE of these ways — never by simply stopping (a third, ``handoff --resume <a file "
            "with a `## RESUME` block>``, only where this command's own text names that close):") in rendered
    assert asm.NEXT["fabrik-spec"].endswith("a `Size: small` spec goes to /fabrik-plan-after-chat <spec path> instead.")

    monkeypatch.setenv("COMMAND_RUN_DIR", str(tmp_path / "command-runs"))
    cr = [sys.executable, str(REPO / "scripts" / "command_run.py")]
    subprocess.run([*cr, "start", "--command", "fabrik-spec", "--phases", "6", "--terminal", "t"],
                   check=True, capture_output=True)
    amend = subprocess.run([*cr, "step", "--phase", "2", "--title", "t", "--terminal-amend", "u"],
                           capture_output=True, text=True)
    assert "--terminal-amend belongs to --command fabrik-task" in amend.stdout + amend.stderr

    src = (REPO / "commands" / "_sources" / "fabrik-spec.md").read_text(encoding="utf-8")
    p4 = norm(_section(src, r"^## Phase 4 —", r"^## Phase 5 —"))
    assert ("Present in sections scaled to complexity; an operator present may redirect any section, but the run "
            "does not stop for a per-section yes — the approval gate is the one Phase 6 names.") in p4
    import re

    for sec in (p4, norm(_section(src, r"^## Phase 3 —", r"^## Phase 4 —"))):
        assert re.search(r"(?i)\b(yes|approv\w*)\b[^.]*\bafter each\b", sec) is None, "a per-section stop is back"
    assert ("**HARD GATE:** no implementation or scaffold until the design is approved at that gate (a `Size: small` "
            "spec's plan is drafted before it and approved with it).") in p4
    assert "no code or scaffold — and no plan except a `Size: small` spec's" in norm(src)
    assert "- Write code or a scaffold, or a plan outside the `Size: small` path, before the design is approved" in norm(src)
    p6 = norm(_spec_phase6())
    text = norm(src)
    assert ("surface those and close with `python3 scripts/command_run.py handoff --command fabrik-spec --resume "
            "<scratch file> --reason \"<the open question>\" --feedback …`, the file's `## RESUME` block naming the "
            "question and the restart `/fabrik-spec <spec path>` — never by stopping on a `running` record.") in p6
    assert "surface those and stop" not in text
    assert ("A hard cap outranks the floor (D-189): when `dispatch_headroom.py` prints fewer `SEATS:`, dispatch that "
            "many, name the dependencies no seat grounded, and dispatch them when headroom returns.") in text
    assert ("`firecrawl_scrape` on the library's OFFICIAL docs site for framework/API detail (`WebFetch` only to "
            "locate the page) → the **`gh` CLI** (`gh search code` / `gh api -H 'Accept: application/vnd.github.raw' "
            "repos/<o>/<r>/contents/<path>`") in text
    assert ("from a RAW fetch (`firecrawl_scrape` as markdown, the raw `gh api` call above, the raw file — a "
            "`WebFetch` reply summarises, below)") in text
