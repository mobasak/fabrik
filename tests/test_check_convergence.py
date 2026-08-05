"""Tests for scripts/enforcement/check_convergence.py — the convergence-evidence gate.

A markdown artifact that CLAIMS convergence must embed its proof, or the gate
fails. These tests drive the real script over a throwaway git repo (it discovers
artifacts via ``git status``), so they exercise the actual code path.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

CHECK = Path(__file__).resolve().parents[1] / "scripts" / "enforcement" / "check_convergence.py"

COMPLIANT_PLAN = """# Plan for X

**Status:** CONVERGED

## Evidence

## Phase 1 — wiring
Grounded in src/app/handler.py:42 (the request handler) and db/schema.sql:10.

```
$ python scripts/final_gate.py --lean
{"status": "success", "passed": 15, "failed": 0}
```

## Self-audit
Every claim above traces to a path:line citation and the gate output. No
runtime-only assumptions remain.
"""

PLAN_NO_EVIDENCE = """# Plan for X

**Status:** CONVERGED

## Phase 1
We will change the handler. It is converged, trust me.
"""

PLAN_NO_CLAIM = """# Plan for X

**Status:** DRAFT

## Phase 1
Exploratory notes; no convergence claimed yet. src/app/handler.py:42
"""

COMPLIANT_REVIEW = """# Review of plan X

## Phase 1 verdict
Mirrors the plan; no deviation.

reviewed — sign-off.

```
$ python scripts/final_gate.py --json
{"status": "success", "tier": 1, "passed": 15, "failed": 0}
```
"""

REVIEW_NO_GATE = """# Review of plan X

This was reviewed and looks converged to me.
No gate output, no phase verdicts.
"""

# --- EXECUTED-plan → whole-plan-review gate fixtures --------------------------

EXECUTED_PLAN_NO_REVIEW = """# Plan X

**Status:** EXECUTED 2026-08-03 (abc1234)

## Phase A
Shipped the handler. src/app/handler.py:42
"""

EXECUTED_PLAN_CITES_MISSING = """# Plan X

**Status:** EXECUTED 2026-08-03 (abc1234)
Whole-plan review: docs/development/reviews/2026-08-03-plan-x-review.md

## Phase A
Shipped. src/app/handler.py:42
"""

EXECUTED_PLAN_CITES = """# Plan X

**Status:** EXECUTED 2026-08-03 (abc1234)
Whole-plan review: docs/development/reviews/2026-08-03-plan-x-review.md

## Phase A
Shipped. src/app/handler.py:42
"""

# A real whole-plan review: passes _check_review (gate + phase + "reviewed") AND
# my adjudication signal (Coverage Checklist present, last `found:` is 0).
ADJUDICATED_REVIEW = """# Whole-plan review of Plan X

Surface: HEADabc + 0decafbad

## Coverage Checklist
| class | verdict |
|---|---|
| fail-open vs fail-closed | CLEAN |
| cost/quota edges | FIXED(1) |

## Phase A verdict
Mirrors the plan; one finding fixed.

reviewed — sign-off.

## Pass Ledger
Pass 1 — found: 2, fixed: 1
Pass 2 — found: 0, fixed: 0

```
$ python scripts/final_gate.py --json
{"status": "success", "tier": 2, "passed": 20, "failed": 0}
```
"""

# Passes _check_review (gate + phase + "reviewed") but is NOT coverage-adjudicated:
# no quiet `found: 0, fixed: 0` pass, so the loop never reached a clean exit.
STUB_REVIEW = """# Whole-plan review of Plan X

## Coverage Checklist
| class | verdict |
|---|---|
| fail-open vs fail-closed | UNCHECKED |

## Phase A verdict
pending.

reviewed.

## Pass Ledger
Pass 1 — found: 3, fixed: 1

```
{"status": "success", "passed": 1, "failed": 0}
```
"""

# A review that DOCUMENTS its own non-convergence: "found:0" appears only in prose,
# never as a quiet `found: 0, fixed: 0` pass. Must be REJECTED (the false-accept
# a whole-file last-`found:` heuristic let through).
PROSE_NONCONVERGENCE_REVIEW = """# Whole-plan review of Plan X

## Coverage Checklist
| class | verdict |
|---|---|
| cost/quota edges | FIXED(6) |

## Phase A verdict
One finding BLOCKED after 3 attempts.

## Pass Ledger
Pass 1 — found: 15, fixed: 9
Pass 2 — found: 6, fixed: 5

The loop did NOT reach a clean found:0 round — one finding is BLOCKED-escalated.

reviewed.

```
{"status": "success", "passed": 1, "failed": 0}
```
"""

# A genuine quiet pass, with a trailing `found: N` in later prose (declared
# residuals / net-new-coverage note). Must be ACCEPTED (the false-reject).
TRAILING_FOUND_REVIEW = """# Whole-plan review of Plan X

## Coverage Checklist
| class | verdict |
|---|---|
| fail-open vs fail-closed | CLEAN |

## Phase A verdict
Clean.

reviewed — sign-off.

## Pass Ledger
Pass 1 — found: 2, fixed: 2
Pass 2 — found: 0, fixed: 0

Declared residuals (advisory, out of scope): found: 2 follow-ups for a later plan.

```
{"status": "success", "passed": 20, "failed": 0}
```
"""

# Status is DRAFT/IN-PROGRESS with "executed" only in prose — NOT an EXECUTED claim.
PLAN_NOT_EXECUTED = """# Plan X

**Status:** DRAFT — to be executed after review; the migration was executed manually once.

## Phase A
Notes. src/app/handler.py:42
"""


# Status is CLOSED / Done, but the word "executed" appears in the status PROSE —
# must NOT be treated as an EXECUTED claim (real /opt/fabrik plans do this).
PLAN_EXECUTED_IN_PROSE_ONLY = """# Plan X

**Status:** ✅ **CLOSED 2026-06-02 — superseded** (a Draft that was never executed directly)

## Phase A
Notes. src/app/handler.py:42
"""

PLAN_DONE_WITH_EXECUTED_PROSE = """# Plan X

**Status:** Done, end-to-end verified. Initial install was executed unauthorized by an external AI.

## Phase A
Notes. src/app/handler.py:42
"""


def _run(repo: Path, relpath: str, content: str) -> int:
    return _run_files(repo, {relpath: content})


def _run_files(repo: Path, files: dict[str, str]) -> int:
    for relpath, content in files.items():
        (repo / relpath).parent.mkdir(parents=True, exist_ok=True)
        (repo / relpath).write_text(content)
    # The gate runs on STAGED content (it skips untracked '??' in-flight drafts —
    # "checked at staging"), so stage the fixtures to exercise the real path.
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, timeout=15)
    proc = subprocess.run(
        [sys.executable, str(CHECK), "--project-root", str(repo)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.returncode


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, timeout=15)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True, timeout=15)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True, timeout=15)
    return tmp_path


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, timeout=15, capture_output=True)


def _check(repo: Path) -> int:
    return subprocess.run(
        [sys.executable, str(CHECK), "--project-root", str(repo)],
        capture_output=True,
        text=True,
        timeout=30,
    ).returncode


def _check_out(repo: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(CHECK), "--project-root", str(repo)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.returncode, proc.stdout


def test_compliant_plan_passes(repo: Path) -> None:
    assert _run(repo, "docs/development/plans/2026-06-18-plan-x.md", COMPLIANT_PLAN) == 0


def test_converged_plan_without_evidence_fails(repo: Path) -> None:
    assert _run(repo, "docs/development/plans/2026-06-18-plan-x.md", PLAN_NO_EVIDENCE) == 1


def test_plan_not_claiming_convergence_is_ignored(repo: Path) -> None:
    assert _run(repo, "docs/development/plans/2026-06-18-plan-x.md", PLAN_NO_CLAIM) == 0


def test_compliant_review_passes(repo: Path) -> None:
    assert _run(repo, "docs/development/reviews/2026-06-18-plan-x-review.md", COMPLIANT_REVIEW) == 0


def test_review_without_embedded_success_fails(repo: Path) -> None:
    assert _run(repo, "docs/development/reviews/2026-06-18-plan-x-review.md", REVIEW_NO_GATE) == 1


def test_no_artifacts_passes(repo: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(CHECK), "--project-root", str(repo)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0


# --- EXECUTED-plan → whole-plan-review gate -----------------------------------


def test_executed_plan_without_review_fails(repo: Path) -> None:
    # The SEO fingerprint: Status flipped EXECUTED with no persisted review.
    assert _run(repo, "docs/development/plans/2026-08-03-plan-x.md", EXECUTED_PLAN_NO_REVIEW) == 1


def test_executed_plan_citing_missing_review_fails(repo: Path) -> None:
    # Cites a review path that does not exist on disk.
    assert (
        _run(repo, "docs/development/plans/2026-08-03-plan-x.md", EXECUTED_PLAN_CITES_MISSING) == 1
    )


def test_executed_plan_citing_unadjudicated_review_fails(repo: Path) -> None:
    assert (
        _run_files(
            repo,
            {
                "docs/development/plans/2026-08-03-plan-x.md": EXECUTED_PLAN_CITES,
                "docs/development/reviews/2026-08-03-plan-x-review.md": STUB_REVIEW,
            },
        )
        == 1
    )


def test_executed_plan_with_adjudicated_review_passes(repo: Path) -> None:
    assert (
        _run_files(
            repo,
            {
                "docs/development/plans/2026-08-03-plan-x.md": EXECUTED_PLAN_CITES,
                "docs/development/reviews/2026-08-03-plan-x-review.md": ADJUDICATED_REVIEW,
            },
        )
        == 0
    )


def test_rename_into_archived_is_enforced(repo: Path) -> None:
    # The flip-EXECUTED-and-archive-in-one-commit move (a git rename into archived/)
    # must NOT be an escape hatch — it is still held to the review-citation rule.
    src = repo / "docs/development/plans/2026-08-03-plan-x.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    # Seed identical to EXECUTED_PLAN_NO_REVIEW except the Status line, so the later
    # move is detected by git as a RENAME (high similarity), not delete+add.
    src.write_text(EXECUTED_PLAN_NO_REVIEW.replace("EXECUTED 2026-08-03 (abc1234)", "CONVERGED"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "seed plan")
    # Now flip EXECUTED (no citation) and move it into archived/ — as one staged change.
    dst = repo / "docs/development/plans/archived/2026-08-03-plan-x.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "mv", str(src), str(dst))
    dst.write_text(EXECUTED_PLAN_NO_REVIEW)
    _git(repo, "add", "-A")
    assert _check(repo) == 1


def test_flip_and_archive_as_delete_add_is_enforced(repo: Path) -> None:
    # The move can be recorded as delete+add (big body rewrite) instead of a rename —
    # HEAD-comparison catches it anyway (archived path is new-with-EXECUTED at HEAD).
    src = repo / "docs/development/plans/2026-08-03-plan-x.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("# Plan X\n\n**Status:** CONVERGED\n\n## Phase A\nshort seed body\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "seed")
    _git(repo, "config", "status.renames", "false")  # force delete+add representation
    src.unlink()
    dst = repo / "docs/development/plans/archived/2026-08-03-plan-x.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(EXECUTED_PLAN_NO_REVIEW + "\n(completely rewritten summary body)\n")
    _git(repo, "add", "-A")
    assert _check(repo) == 1


def test_modified_already_archived_plan_is_skipped(repo: Path) -> None:
    # An already-settled archived plan that is merely re-touched (bulk reformat)
    # must NOT be re-failed for lacking the (new) citation — the 'cries wolf' guard.
    p = repo / "docs/development/plans/archived/2026-07-01-plan-old.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(EXECUTED_PLAN_NO_REVIEW)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "seed archived plan")
    p.write_text(EXECUTED_PLAN_NO_REVIEW + "\n<!-- reformatted -->\n")  # incidental touch
    _git(repo, "add", "-A")
    assert _check(repo) == 0


def test_executed_word_in_status_prose_is_not_an_executed_claim(repo: Path) -> None:
    # CLOSED / Done / DRAFT status with "executed" in the prose must NOT trip the gate.
    assert (
        _run(repo, "docs/development/plans/2026-06-02-plan-x.md", PLAN_EXECUTED_IN_PROSE_ONLY) == 0
    )
    assert (
        _run(repo, "docs/development/plans/2026-06-01-plan-y.md", PLAN_DONE_WITH_EXECUTED_PROSE)
        == 0
    )
    assert _run(repo, "docs/development/plans/2026-06-03-plan-z.md", PLAN_NOT_EXECUTED) == 0


def test_review_documenting_nonconvergence_is_rejected(repo: Path) -> None:
    # "found:0" in prose (a BLOCKED-escalated, non-quiet exit) is NOT a clean exit.
    assert (
        _run_files(
            repo,
            {
                "docs/development/plans/2026-08-03-plan-x.md": EXECUTED_PLAN_CITES,
                "docs/development/reviews/2026-08-03-plan-x-review.md": PROSE_NONCONVERGENCE_REVIEW,
            },
        )
        == 1
    )


def test_quiet_pass_with_trailing_found_is_accepted(repo: Path) -> None:
    # A real `found: 0, fixed: 0` pass is adjudicated even if later prose adds a trailing `found: N`.
    assert (
        _run_files(
            repo,
            {
                "docs/development/plans/2026-08-03-plan-x.md": EXECUTED_PLAN_CITES,
                "docs/development/reviews/2026-08-03-plan-x-review.md": TRAILING_FOUND_REVIEW,
            },
        )
        == 0
    )


def test_review_with_a_trailing_summary_pair_is_still_accepted(repo: Path) -> None:
    # Candidate-2 guard (NO CRIES-WOLF): a genuinely-converged review whose ledger
    # reaches `found: 0, fixed: 0` but then ends with a per-phase summary line that
    # itself carries counts ("Phase A found: 3, fixed: 3") must STILL be accepted.
    # (A whole-tree "last found/fixed pair" heuristic wrongly rejected this common shape.)
    review = (
        "# Whole-plan review\n\n## Pass Ledger\nPass 1 — found: 2, fixed: 2\n"
        "Pass 2 — found: 0, fixed: 0\n\n## Per-phase summary\n"
        "Phase A found: 3, fixed: 3\nPhase B found: 1, fixed: 1\n\n"
        '## Phase A verdict\nclean.\n\nreviewed — sign-off.\n\n```\n{"status": "success", "passed": 9}\n```\n'
    )
    assert (
        _run_files(
            repo,
            {
                "docs/development/plans/2026-08-03-plan-x.md": EXECUTED_PLAN_CITES,
                "docs/development/reviews/2026-08-03-plan-x-review.md": review,
            },
        )
        == 0
    )


def test_reorg_move_of_settled_archived_plan_is_skipped(repo: Path) -> None:
    # Candidate-1 guard (NO CRIES-WOLF): a dir reorg that MOVES a settled, pre-citation
    # EXECUTED archived plan must not re-fail it — it was already EXECUTED at its source.
    old = repo / "docs/development/plans/archived/2026-07-01-plan-old.md"
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_text(EXECUTED_PLAN_NO_REVIEW)  # settled, no citation (grandfathered)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "seed settled archived plan")
    new = repo / "docs/development/plans/archived/2026-07/plan-old.md"
    new.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "mv", str(old), str(new))  # relocate during a reorg
    _git(repo, "add", "-A")
    assert _check(repo) == 0


# --- Spine+ticket shape: tolerant CONVERGED + new-transition-only (BC 6) --------

SPINE_DIR = "docs/development/plans/2026-08-05-plan-1-widget"

CONVERGED_SPINE_ORPHAN_ROW = """# Plan: widget

Status: CONVERGED

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | schema | — | ⚡ | ⬜ | — |
| T02 | api | T01 | ⛓️ | ⬜ | — |

## Merge Order

1. T01
2. T02

## Evidence

Grounded in src/app/handler.py:42.

```
$ python scripts/final_gate.py --lean
{"status": "success", "passed": 15, "failed": 0}
```

## Self-audit
Traced.
"""

TICKET_T01 = """# T01 — schema

Depends: none
Parallel: ⚡
Complexity: simple
Docs: none
Gate: pytest -q

## Scope
Schema. DO-NOT touch api.

## Touches
- src/app/schema.py

## Behavior Contract
- **Given** x, **When** y, **Then** z (src/app/schema.py:1).

## Context Files
- .windsurf/rules/core/10-python.md
"""


def test_bc6_new_plain_converged_spine_with_orphan_row_fails(repo: Path) -> None:
    # T02 row has no ticket file on disk → orphan → fail (also proves the
    # tolerant CONVERGED regex: the Status line is PLAIN, not **Status:**).
    rc = _run_files(
        repo,
        {
            f"{SPINE_DIR}/2026-08-05-plan-1-widget.md": CONVERGED_SPINE_ORPHAN_ROW,
            f"{SPINE_DIR}/T01-schema.md": TICKET_T01,
        },
    )
    rc2, out = _check_out(repo)
    # Message-level: the ORPHAN-ROW mechanism specifically (the fixture also has
    # other contract gaps; rc alone would pass with the orphan loop deleted).
    assert rc == 1 and rc2 == 1
    assert "orphan row" in out


def test_flip_runs_full_ticket_contract_in_process(repo: Path) -> None:
    # BC 33's flip half: the in-process check_plan_dir(context="flip") call must
    # surface plan-set contract ERRORs (here: missing Complexity) at the
    # CONVERGED flip — if the import or the call regresses, the whole contract
    # would silently degrade to orphan-rows + the Status ban.
    complete = CONVERGED_SPINE_ORPHAN_ROW.replace("| T02 | api | T01 | ⛓️ | ⬜ | — |\n", "").replace(
        "2. T02\n", ""
    )
    no_cx = TICKET_T01.replace("Complexity: simple\n", "")
    rc = _run_files(
        repo,
        {
            f"{SPINE_DIR}/2026-08-05-plan-1-widget.md": complete,
            f"{SPINE_DIR}/T01-schema.md": no_cx,
        },
    )
    rc2, out = _check_out(repo)
    assert rc == 1 and rc2 == 1
    assert "plan-set contract" in out and "no parseable Complexity" in out


def test_spine_executed_per_ticket_review_never_proves_the_whole_plan(tmp_path: Path) -> None:
    # D7 discrimination (exec-D hardening): a spine flipping EXECUTED must cite
    # the WHOLE-PLAN validation review; an adjudicated D4 per-ticket review
    # (-T##-review.md) cannot satisfy the citation — else a set flips EXECUTED
    # without the D7 validation ever running.
    import scripts.enforcement.check_convergence as cc

    d = tmp_path / "docs" / "development" / "plans" / "2026-08-05-plan-1-widget"
    d.mkdir(parents=True)
    spine = d / "2026-08-05-plan-1-widget.md"
    rev_dir = tmp_path / "docs" / "development" / "reviews"
    rev_dir.mkdir(parents=True)
    (rev_dir / "2026-08-05-plan-1-widget-T01-review.md").write_text(
        ADJUDICATED_REVIEW, encoding="utf-8"
    )
    spine.write_text(
        "# Plan\n\nStatus: EXECUTED 2026-08-05\n\nWhole-plan review: "
        "docs/development/reviews/2026-08-05-plan-1-widget-T01-review.md\n",
        encoding="utf-8",
    )
    fails = cc._check_executed_plan(tmp_path, spine)
    assert any("per-ticket -T##-review.md files never satisfy it" in f for f in fails)

    # The SAME adjudicated content, cited as the whole-plan review, satisfies it.
    (rev_dir / "2026-08-05-plan-1-widget-review.md").write_text(
        ADJUDICATED_REVIEW, encoding="utf-8"
    )
    spine.write_text(
        spine.read_text(encoding="utf-8").replace("-T01-review.md", "-review.md"),
        encoding="utf-8",
    )
    fails2 = cc._check_executed_plan(tmp_path, spine)
    assert not any("cited whole-plan review" in f for f in fails2)


def test_bc6_ticket_with_status_line_fails_spine_convergence(repo: Path) -> None:
    complete = CONVERGED_SPINE_ORPHAN_ROW.replace("| T02 | api | T01 | ⛓️ | ⬜ | — |\n", "").replace(
        "2. T02\n", ""
    )
    rc = _run_files(
        repo,
        {
            f"{SPINE_DIR}/2026-08-05-plan-1-widget.md": complete,
            f"{SPINE_DIR}/T01-schema.md": TICKET_T01 + "\nStatus: DRAFT\n",
        },
    )
    rc2, out = _check_out(repo)
    assert rc == 1 and rc2 == 1
    assert "carries a Status: line" in out  # the BAN mechanism, not a side effect


def test_bc6_already_converged_at_head_is_settled(repo: Path) -> None:
    # A plain-CONVERGED monolith WITHOUT evidence, committed at HEAD, then
    # re-touched: the tolerant regex now matches it, but new-transition-only
    # enforcement must skip it (fleet backcompat — /opt/seo live instance).
    p = repo / "docs/development/plans/2026-08-02-plan-1-legacy.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# Old plan\n\n**Status: CONVERGED** (4 passes)\n\nNo evidence sections at all.\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "seed settled converged plan")
    p.write_text(p.read_text() + "\nA later touch.\n")
    _git(repo, "add", "-A")
    assert _check(repo) == 0


def test_bc6_new_plain_converged_monolith_without_evidence_fails(repo: Path) -> None:
    # The tolerant regex must catch a NEW plain-Status monolith (was invisible
    # to the bold-only token regex).
    assert (
        _run(
            repo,
            "docs/development/plans/2026-08-05-plan-2-mono.md",
            "# Plan\n\nStatus: CONVERGED\n\n## Phase 1\nNo evidence.\n",
        )
        == 1
    )


def test_fenced_converged_quote_is_not_a_claim(repo: Path) -> None:
    # A DRAFT plan QUOTING the flip in an example block must not be enforced.
    body = (
        "# Plan\n\nStatus: DRAFT\n\nExample of the final flip:\n\n"
        "```markdown\nStatus: CONVERGED\n```\n\nNo evidence sections at all.\n"
    )
    assert _run(repo, "docs/development/plans/2026-08-06-plan-1-fq.md", body) == 0


def test_fenced_executed_at_head_does_not_settle_a_real_flip(repo: Path) -> None:
    # HEAD has a DRAFT plan quoting `Status: EXECUTED` in a fence; a later REAL
    # EXECUTED flip must still be enforced (the citation gate must fire).
    p = repo / "docs/development/plans/2026-08-06-plan-2-fx.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "# Plan\n\nStatus: DRAFT\n\n```markdown\nStatus: EXECUTED\n```\n", encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "seed draft with fenced example")
    p.write_text("# Plan\n\nStatus: EXECUTED\n\nDone.\n", encoding="utf-8")
    _git(repo, "add", "-A")
    assert _check(repo) == 1  # claims EXECUTED, cites no review → enforced


def test_dual_claim_executed_at_head_plus_new_converged_still_enforced(repo: Path) -> None:
    # Round-9 #1: an already-EXECUTED-at-HEAD spine gaining a NEW CONVERGED claim
    # must still run the plan-set contract (the skip-if-EXECUTED dedupe opened
    # this hole; dedupe now happens on finding lines, not by skipping a path).
    d = repo / "docs/development/plans/2026-08-06-plan-3-dual"
    d.mkdir(parents=True)
    spine = d / "2026-08-06-plan-3-dual.md"
    spine.write_text(
        "# Plan\n\nStatus: EXECUTED\n\n## Ticket Board\n\n"
        "| Ticket | Title | Depends | Parallel | State | Commit |\n|---|---|---|---|---|---|\n"
        "| T99 | ghost | — | ⚡ | ⬜ | — |\n\nWhole-plan review: docs/development/reviews/x-review.md\n",
        encoding="utf-8",
    )
    (repo / "docs/development/reviews").mkdir(parents=True, exist_ok=True)
    (repo / "docs/development/reviews/x-review.md").write_text(
        '# R\n\nreviewed\n\n```\n"status": "success" and more content here\n```\n\n'
        "## Phase 1 verdict\nok\n\nfound: 0, fixed: 0\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "seed executed spine (settled)")
    spine.write_text(
        spine.read_text(encoding="utf-8").replace(
            "Status: EXECUTED", "Status: EXECUTED — CLEAN-CONVERGED"
        ),
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    rc, out = _check_out(repo)
    assert rc == 1 and "orphan row" in out
