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
    assert ("from a RAW fetch (`firecrawl_scrape` as markdown with `maxAge: 0`, the raw `gh api` call above, the raw file — a "
            "`WebFetch` reply summarises, below)") in text


def test_fabrik_spec_review_fetches_live_and_keeps_mechanism_in_the_plan() -> None:
    """/fabrik-spec-review queue (kaizen D-711): the re-verify ladder sent official-docs reads to a
    summarising WebFetch; a quote was called NOT FOUND on a cached copy (firecrawl and exa both reuse
    cached content -- firecrawl's own schema: `maxAge: 0` forces a live fetch; 2 rows); and delta rounds
    re-fixed mechanism prose a spec should not carry (6 rows). The author command, the review and the
    grounder agent say the same thing."""
    import re

    def norm(t: str) -> str:
        return " ".join(t.split())

    src = (REPO / "commands" / "_sources" / "fabrik-spec-review.md").read_text(encoding="utf-8")
    text = norm(src)
    assert "→ `WebFetch` on the official library docs →" not in text
    assert ("`mcp__firecrawl__firecrawl_search`/`firecrawl_scrape` (on the official library docs; `WebFetch` only to "
            "locate a page) → the `gh` CLI") in text
    assert ("`firecrawl_scrape` with `maxAge: 0` — firecrawl reuses recently indexed content unless `maxAge: 0` forces a "
            "live fetch (its tool schema) and `mcp__exa__web_fetch_exa` serves a crawl cache (below), so a quote — yours or "
            "a grounder's — is called NOT FOUND only after that live re-fetch)") in text
    a = norm(_section(src, r"^\*\*A\) External facts", r"^\*\*B\) fabrik-lib"))
    assert "A cached/mirroring fetch tool is NOT a liveness oracle" in a and "`mcp__exa__web_fetch_exa` serves crawl cache" in a
    sanctioned = ("`mcp__exa__web_fetch_exa` serves a crawl cache (below), so a quote — yours or a grounder's — is "
                  "called NOT FOUND only after that live re-fetch")
    rest = a.replace(sanctioned, "")
    exa = r"(web_fetch_exa|\bexa\b)"
    assert re.search(rf"NOT FOUND.{{0,160}}{exa}|{exa}.{{0,160}}NOT FOUND", rest, re.I) is None, "NOT FOUND on the exa cache"
    quote_rule = text[text.index("to quote, pull the RAW document"):text.index("and match the string")]
    assert "WebFetch" not in quote_rule, "a WebFetch reply is not a raw source"
    d = norm(_section(src, r"^\*\*D\) Completeness", r"^\*\*E\) Fabrik"))
    assert ("A section describing a code FLOW states its invariants and touchpoints (what must hold, which paths it "
            "touches); the executable sequence belongs to the plan, so when the edit loop's TWO CONSECUTIVE RESIDUE "
            "PASSES rule forces a rewrite inside such a section, the rewrite re-shapes it to invariants + touchpoints "
            "rather than re-wording the sequence.") in d
    te = (REPO / "commands" / "_fragments" / "term-edit.md").read_text(encoding="utf-8")
    assert "(3) **TWO CONSECUTIVE RESIDUE PASSES FORCE A REWRITE**" in te, "the rule the review names moved"
    spec = norm((REPO / "commands" / "_sources" / "fabrik-spec.md").read_text(encoding="utf-8"))
    assert "`firecrawl_scrape` with `maxAge: 0`, a live fetch) and match" in spec
    assert "data flow (as invariants + touchpoints — the step sequence is the plan's)" in spec
    agent = norm((REPO / "commands" / "_agents" / "fabrik-researcher.md").read_text(encoding="utf-8"))
    assert ("have failed a correct quote as MISQUOTED). Exa serves a crawl cache, so before you report a quote NOT "
            "FOUND re-fetch the page with `mcp__firecrawl__firecrawl_scrape` and `maxAge: 0` (a live fetch).") in agent
    assert "from a RAW fetch (`firecrawl_scrape` as markdown with `maxAge: 0`," in spec


def test_fabrik_plan_after_chat_tells_the_gates_truth() -> None:
    """/fabrik-plan-after-chat queue (kaizen D-711 audit, 12 rows): the ticket skeleton put no Appetite above the
    first `##` (the only zone plan_appetite.header_zone reads); the Coverage Checklist asked for an rubric
    INVOCATION where RUBRIC_RUN matches only the pasted output header, and never said table + verdict; the
    byte recipe double-counts a repeated path; a wrapped G/W/T row loses its Then; Phase 5's stop had no close
    and missed the unconverged-spec refusal."""
    import importlib.util
    import re

    def load(name, rel):
        spec = importlib.util.spec_from_file_location(name, REPO / rel)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        return mod

    src = (REPO / "commands" / "_sources" / "fabrik-plan-after-chat.md").read_text(encoding="utf-8")
    text = " ".join(src.split())
    skeleton = src[src.index("```markdown\n# T01 — <title>") :]
    skeleton = skeleton[len("```markdown\n") : skeleton.index("\n```", 12)]
    pa = load("plan_appetite_probe", "scripts/enforcement/plan_appetite.py")
    assert re.search(r"(?m)^Appetite:", pa.header_zone(skeleton)), "the skeleton's Appetite must sit in the header zone"
    assert ("for every ticket (spine+ticket set), before its first `##`–`######` heading (the only zone the gate "
            "reads in a ticket), or for every phase (monolith), inside its own `## Phase <id>` section") in text
    mono = "# Plan\nAppetite: 30\n\n## Phase 1 — a\nx\n\n## Phase 2 — b\ny\n"
    inside = "# Plan\n\n## Phase 1 — a\nAppetite: 30\nx\n\n## Phase 2 — b\nAppetite: 20\ny\n"
    assert pa.appetite_findings(mono, "2026-10-09") and not pa.appetite_findings(inside, "2026-10-09"), (
        "a monolith's Appetite lives in each phase section, not the header zone")
    crc = load("crc_probe", "scripts/enforcement/check_review_coverage.py")
    assert not crc.RUBRIC_RUN.search("```bash\npython3 scripts/review_rubric.py --changed a.py\n```")
    assert crc.RUBRIC_RUN.search("# REVIEW RUBRIC — generated by review_rubric.py")
    assert "**with an embedded `review_rubric.py` invocation**" not in text
    assert "header — the bare invocation does not match)" in text
    assert ("(a TABLE of rubric-derived rows plus the four standing recurrence classes, each row CLEAN/FIXED/REFUTED by "
            "the flip) **with the pasted OUTPUT of `review_rubric.py`**") in text
    assert ("one exact number for paths each listed ONCE (the gate drops exact repeats, rules packs, the exempt "
            "shared reads and generated artifacts, but a file beside its own directory, or `dir` beside `dir/`, "
            "counts twice there too)") in text
    assert "each row on ONE physical line, since the gate reads only the first line of a wrapped row" in text
    assert "surface those and stop" not in text
    assert "(`/fabrik-plan-review`'s Small-spec exception, which flips the spec first or in the same commit)" in text
    assert ("or a cited spec that is not CONVERGED and carries no `Size: small` (`check_stage_artifacts.py` refuses "
            "a plan flip over ANY") in text
    assert ("any other goes to `/fabrik-spec-review` first) — surface those and close with `python3 "
            "scripts/command_run.py handoff --command fabrik-plan-after-chat --resume") in text
    assert ("refuses a plan flip over ANY non-CONVERGED spec; a `Size: small` one converges spec-first in "
            "`/fabrik-plan-review`'s joint loop") in text
    assert ("--reason \"<the open item>\" --feedback …`, the file's `## RESUME` block naming it and the restart, never "
            "by stopping on a `running` record") in text
    assert ("Read its `Status:` too: a spec neither CONVERGED nor `Size: small` stops the run here, by Phase 5's "
            "`handoff` close, for `/fabrik-spec-review`.") in text
    assert ("For each function the plan moves or re-signs, grep `tests/` for the tests that call, stub or patch "
            "it; each lands in that ticket's File Scope") in text
    assert ("A behavioural claim the plan rests on (a render, a state transition, a suite count after the core "
            "edit) is EXECUTED once against a copy, never inferred from anchors.") in text
    assert "captured in Phase 1, pasted from that run's captured output, never typed" in text


def test_fabrik_spec_carries_its_recurring_feedback_rules(tmp_path, monkeypatch) -> None:
    """/fabrik-spec queue, recurring HELD subjects (D-711: a recurrence is edited): execute local claims (10 rows),
    vendor-doc coverage (3), the judge-panel brief and dissent (8), the repo duplicate check (2), self-check of
    path:line anchors (2), delta as invariants + touchpoints (2), and the handoff's kept seed (2 rows, D-716)."""
    import json
    import subprocess
    import sys

    def norm(t: str) -> str:
        return " ".join(t.split())

    text = norm((REPO / "commands" / "_sources" / "fabrik-spec.md").read_text(encoding="utf-8"))
    panel = norm((REPO / "commands" / "_fragments" / "judge-panel.md").read_text(encoding="utf-8"))
    assert ("every premise the brief states about the codebase, every mechanism the design relies on (\"X fires\", "
            "\"Y catches this\"), every design rule (an algebra, a classifier) and every runtime-state claim is EXECUTED "
            "this session, its command and output cited in the spec, and Phase 3 waits on it as on the BLOCKING bullet "
            "below. An executed in-repo measurement outranks a web answer about the repo's own code; a vendored or "
            "installed third-party package's behaviour stays an external claim under this gate.") in text
    assert ("the machine-readable schema when one exists (an OpenAPI endpoint names the parameters), the error-code page "
            "beside the endpoint page when the design retries or re-sends, and a design that survives both readings when "
            "two vendor pages contradict each other.") in text
    assert ("The brief carries only the approaches that survive 1b-bis's hard constraints and the Phase 3 cuts (fewer "
            "than two: say so and return to 1c for another), any precedent quoted in its exact lines beside every "
            "approach it bears on, every count from an executed probe; each seat prices each approach's mechanism "
            "against Fabrik's hard constraints and the stack it runs on.") in panel
    assert ("verify every factual claim a dissent rests on first, fold a confirmed dissent's gap into the design (a fold "
            "that changes the ranked approach's mechanism re-dispatches the panel)") in panel
    assert "what stays split is carried to the operator's approval as an open question" in panel
    assert "the brief never names it" in panel, "the cobra counter stays"
    assert ("grep `docs/superpowers/specs` and `docs/development/plans` for the module and the brief's work-item ids") in text
    assert "does every backticked `path:line` resolve (grep it)?" in text
    assert ("· The delta (invariants + touchpoints, one `path:line` per existing touchpoint and a new file by path "
            "alone — never \"as today\") ·") in text
    assert ("handoff keeps a byte copy under `<state dir>/seeds/` and prints its path, also `resume_copy` on the "
            "run_close event, D-716 — carry that path into the restart, since the next `start` overwrites the record") in text
    # the behaviour the D-716 sentence relies on: handoff keeps the seed's bytes under resume_copy
    monkeypatch.setenv("COMMAND_RUN_DIR", str(tmp_path / "cr"))
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(tmp_path / "ev"))
    cr = [sys.executable, str(REPO / "scripts" / "command_run.py")]
    subprocess.run([*cr, "start", "--command", "fabrik-spec", "--phases", "6", "--terminal", "t"], check=True,
                   capture_output=True)
    seed = tmp_path / "seed.md"
    seed.write_text("## RESUME\nrestart: /fabrik-task --from-downgrade R1\n", encoding="utf-8")
    fb = "confusion: none · waste: none · change: none · filed: none — surfaces exercised: probe"
    p = subprocess.run([*cr, "handoff", "--command", "fabrik-spec", "--resume", str(seed), "--reason",
                        "DOWNGRADE: R1 — x", "--feedback", fb], check=True, capture_output=True, text=True)
    seed.unlink()
    assert "handoff: the resume artifact is kept at " in p.stdout, p.stdout
    recs = [json.loads(q.read_text()) for q in (tmp_path / "cr").glob("*.json")]
    kept = [r.get("resume_copy") for r in recs if r.get("resume_copy")]
    assert kept and Path(kept[0]).read_text(encoding="utf-8").startswith("## RESUME"), recs
    closes = [json.loads(ln) for f in (tmp_path / "ev").glob("*.jsonl") for ln in f.read_text().splitlines()
              if '"run_close"' in ln]
    assert any(json.dumps(c).count(kept[0]) for c in closes), closes
