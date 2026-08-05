"""Tests for the spine+ticket plan-shape gates (Behavior Contract 1-5, 13-15, 18, 25, 31).

Drives the patched per-file checks (check_plans, check_plan_quality) directly over
throwaway plan trees. The modules compute PLAN_DIR from Path.cwd() at import time,
so each fixture chdirs into tmp_path and reloads them (and restores on teardown).
Severity is compared by .value — reloads mint fresh enum instances (the identity
trap validate_conventions.py documents).
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest
import scripts.enforcement.check_plan_quality as cpq_mod
import scripts.enforcement.check_plans as cp_mod

DIR = "docs/development/plans/2026-01-01-plan-1-widget"
SPINE = f"{DIR}/2026-01-01-plan-1-widget.md"

TICKET_OK = """# T01 — widget schema

Depends: none
Parallel: ⚡
Complexity: simple
Docs: CHANGELOG entry via Deltas
Gate: python -m pytest tests/test_widget.py

## Scope

Build the widget schema. DO-NOT touch the API layer.

## Touches

- src/widget/schema.py

## Behavior Contract

- **Given** a widget, **When** saved, **Then** it persists (src/widget/schema.py:1).

## Context Files

- .windsurf/rules/core/10-python.md
"""

SPINE_OK = """# Plan: widget

Status: DRAFT

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | widget schema | — | ⚡ | ⬜ | — |

## Merge Order

1. T01

## Interfaces

None.

## Behavior Contract

- **Given** a widget, **When** saved, **Then** it persists (src/widget/schema.py:1).

## Global Constraints

- None.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| x | y | src/widget/schema.py:1 |

## File Scope (owned paths)

- src/widget/schema.py

## Evidence

src/widget/schema.py:1

```
$ true
ok
```
"""

MODERN_MONOLITH = """# Plan: legacy-shape modern plan

Status: DRAFT

## Context Ledger

| a | b | c |

## File Scope (owned paths)

- src/x.py

## Evidence

src/x.py:1
"""

LEGACY_PLAN = """# Old plan

Some pre-pipeline plan with no Status line at all.

## Steps

1. do things
"""


@pytest.fixture
def plans_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    try:
        monkeypatch.chdir(tmp_path)
        importlib.reload(cp_mod)
        importlib.reload(cpq_mod)
        yield tmp_path
    finally:
        # Always restore cwd + module-level PLAN_DIR, even if setup raised —
        # a leaked reload would corrupt these modules for the whole session.
        monkeypatch.undo()
        importlib.reload(cp_mod)
        importlib.reload(cpq_mod)


def _write(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p.resolve()


def _sev(results) -> set[str]:
    return {r.severity.value for r in results}


# --- Behavior Contract 1-2: check_plans naming ---------------------------------


def test_bc1_ticket_in_dated_dir_passes_check_plans(plans_env: Path) -> None:
    p = _write(plans_env, f"{DIR}/T01-widget-schema.md", TICKET_OK)
    assert cp_mod.check_file(p) == []


def test_bc1_split_suffix_ticket_passes_check_plans(plans_env: Path) -> None:
    p = _write(plans_env, f"{DIR}/T01a-widget-schema.md", TICKET_OK)
    assert cp_mod.check_file(p) == []


def test_bc2_loose_ticket_still_errors(plans_env: Path) -> None:
    p = _write(plans_env, "docs/development/plans/T01-loose.md", TICKET_OK)
    assert "error" in _sev(cp_mod.check_file(p))


def test_bc2_ticket_in_undated_dir_errors(plans_env: Path) -> None:
    p = _write(plans_env, "docs/development/plans/widget/T01-x.md", TICKET_OK)
    assert "error" in _sev(cp_mod.check_file(p))


def test_archived_ticket_in_dated_dir_passes_check_plans(plans_env: Path) -> None:
    # The whole-directory archive move must not red the naming gate.
    p = _write(plans_env, "docs/development/plans/archived/2026-01-01-plan-1-w/T01-x.md", TICKET_OK)
    assert cp_mod.check_file(p) == []


# --- Behavior Contract 3: modern monolith + legacy grandfather ------------------


def test_bc3_modern_monolith_passes_quality(plans_env: Path) -> None:
    p = _write(plans_env, "docs/development/plans/2026-01-01-plan-1-mono.md", MODERN_MONOLITH)
    assert "error" not in _sev(cpq_mod.check_file(p))
    # NON-VACUOUS guard: the same plan at CONVERGED missing Evidence must ERROR —
    # proving the modern branch classified it (grandfather would WARN either way;
    # a DRAFT plan deliberately WARNs — sibling-session protection).
    broken = MODERN_MONOLITH.replace("Status: DRAFT", "Status: CONVERGED").replace(
        "## Evidence", "## Nothing"
    )
    p2 = _write(plans_env, "docs/development/plans/2026-01-01-plan-2-mono.md", broken)
    assert "error" in _sev(cpq_mod.check_file(p2))
    draft_broken = MODERN_MONOLITH.replace("## Evidence", "## Nothing")
    p3 = _write(plans_env, "docs/development/plans/2026-01-01-plan-3-mono.md", draft_broken)
    r3 = cpq_mod.check_file(p3)
    # Message-level: the MODERN branch's missing-section WARN, not the
    # grandfather's generic legacy WARN (both would satisfy a bare {"warn"}).
    assert any("Missing required section: Evidence" in r.message for r in r3)
    assert _sev(r3) == {"warn"}


def test_bc3_legacy_plan_warns_only(plans_env: Path) -> None:
    p = _write(plans_env, "docs/development/plans/2026-01-01-plan-1-old.md", LEGACY_PLAN)
    results = cpq_mod.check_file(p)
    assert _sev(results) == {"warn"}


def test_spine_with_all_sections_passes_quality(plans_env: Path) -> None:
    p = _write(plans_env, SPINE, SPINE_OK)
    assert "error" not in _sev(cpq_mod.check_file(p))


def test_spine_missing_merge_order_errors(plans_env: Path) -> None:
    broken = SPINE_OK.replace("Status: DRAFT", "Status: CONVERGED").replace(
        "## Merge Order", "## Something Else"
    )
    p = _write(plans_env, SPINE, broken)
    assert "error" in _sev(cpq_mod.check_file(p))
    # The same gap on a DRAFT spine is a WARN (mid-authoring protection).
    draft = SPINE_OK.replace("## Merge Order", "## Something Else")
    p2 = _write(plans_env, SPINE, draft)
    assert "error" not in _sev(cpq_mod.check_file(p2))


# --- Behavior Contract 4-5: ticket field contract + Status ban ------------------


def test_bc4_ticket_missing_fields_errors_when_spine_not_draft(plans_env: Path) -> None:
    _write(plans_env, SPINE, SPINE_OK.replace("Status: DRAFT", "Status: CONVERGED"))
    broken = (
        TICKET_OK.replace("Complexity: simple\n", "")
        .replace("Docs: CHANGELOG entry via Deltas\n", "")
        .replace("Parallel: ⚡\n", "")
    )
    p = _write(plans_env, f"{DIR}/T01-widget-schema.md", broken)
    results = cpq_mod.check_file(p)
    assert "error" in _sev(results)
    missing = {r.message for r in results if r.severity.value == "error"}
    assert any("Complexity" in m for m in missing)
    assert any("Docs" in m for m in missing)
    assert any("Parallel" in m for m in missing)


def test_bc5_ticket_with_status_line_errors(plans_env: Path) -> None:
    _write(plans_env, SPINE, SPINE_OK.replace("Status: DRAFT", "Status: CONVERGED"))
    p = _write(plans_env, f"{DIR}/T01-widget-schema.md", TICKET_OK + "\nStatus: DRAFT\n")
    results = cpq_mod.check_file(p)
    assert any(r.severity.value == "error" and "Status" in r.message for r in results)


def test_bc5_blockquoted_ticket_status_still_draws_the_ban(plans_env: Path) -> None:
    # Pass-47 mutation kill: the `>` in ANY_STATUS_RE is load-bearing — a
    # quoted ticket Status is still ticket state (fail-closed direction).
    _write(plans_env, SPINE, SPINE_OK.replace("Status: DRAFT", "Status: CONVERGED"))
    p = _write(plans_env, f"{DIR}/T01-widget-schema.md", TICKET_OK + "\n> Status: DRAFT\n")
    results = cpq_mod.check_file(p)
    assert any(r.severity.value == "error" and "Status" in r.message for r in results)


def test_blockquoted_spine_status_never_downgrades_ticket_findings(plans_env: Path) -> None:
    # Pass-47 regression: a `> Status: DRAFT` example in a CONVERGED spine must
    # not re-enable the draft downgrade for sibling-ticket findings.
    _write(
        plans_env,
        SPINE,
        SPINE_OK.replace("Status: DRAFT", "> Status: DRAFT\n\nStatus: CONVERGED"),
    )
    broken = TICKET_OK.replace("Complexity: simple\n", "")
    p = _write(plans_env, f"{DIR}/T01-widget-schema.md", broken)
    results = cpq_mod.check_file(p)
    assert any(r.severity.value == "error" and "Complexity" in r.message for r in results)


def test_status_regex_byte_parity_across_modules() -> None:
    # The parity doctrine, enforced mechanically: the modern Status regex is
    # byte-identical across the two plan gates, the any-Status ban regex is
    # byte-identical with check_convergence, and every sibling shares the same
    # label prefix — a one-sided "harmonization" (e.g. dropping `>`) fails here.
    from scripts.enforcement import check_convergence as cc
    from scripts.enforcement import check_plan_tickets as cpt

    assert cpt.STATUS_RE.pattern == cpq_mod.MODERN_STATUS_RE.pattern
    assert cpq_mod.ANY_STATUS_RE.pattern == cc.ANY_STATUS_LINE.pattern
    label_prefix = r"^\s*(?:[-*>]\s+)?\*{0,2}Status\*{0,2}[^\S\n]*:[^\S\n]*"
    for pat in (cpt.STATUS_RE, cpq_mod.ANY_STATUS_RE, cc.CONVERGED_LINE, cc.EXECUTED):
        assert pat.pattern.startswith(label_prefix)


def test_loose_ticket_is_not_reclassified_by_quality(plans_env: Path) -> None:
    # check_plans ERRORs it; check_plan_quality must skip (naming error stands alone).
    p = _write(plans_env, "docs/development/plans/T01-loose.md", "anything")
    assert cpq_mod.check_file(p) == []


# --- Behavior Contract 18: DRAFT-spine downgrade --------------------------------


def test_bc18_ticket_findings_warn_only_while_spine_draft(plans_env: Path) -> None:
    _write(plans_env, SPINE, SPINE_OK)  # Status: DRAFT
    broken = TICKET_OK.replace("Complexity: simple\n", "")
    p = _write(plans_env, f"{DIR}/T01-widget-schema.md", broken)
    results = cpq_mod.check_file(p)
    assert results, "missing-field finding expected"
    assert _sev(results) == {"warn"}


def test_archived_ticket_exempt_from_quality(plans_env: Path) -> None:
    p = _write(plans_env, "docs/development/plans/archived/2026-01-01-plan-1-w/T01-x.md", "junk")
    assert cpq_mod.check_file(p) == []


# --- Behavior Contract 13: check_test_proposal detects plan DIRECTORIES ---------

CHECK_PROPOSAL = (
    Path(__file__).resolve().parents[2] / "scripts" / "enforcement" / "check_test_proposal.py"
)


def _proposal_repo(tmp_path: Path) -> Path:
    for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, timeout=15, capture_output=True)
    (tmp_path / "docs/development/plans").mkdir(parents=True)
    (tmp_path / "seed.txt").write_text("seed")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, timeout=15, capture_output=True)
    subprocess.run(
        ["git", "commit", "-qm", "seed"], cwd=tmp_path, check=True, timeout=15, capture_output=True
    )
    return tmp_path


def test_bc13_staged_plan_directory_is_detected(tmp_path: Path) -> None:
    repo = _proposal_repo(tmp_path)
    d = repo / "docs/development/plans/2026-01-03-plan-1-w"
    d.mkdir()
    (d / "2026-01-03-plan-1-w.md").write_text(
        "# Plan\n\nStatus: DRAFT\n\n## Behavior Contract\n"
        "- **Given** x, **When** y, **Then** z.\n- **Mocked:** nothing\n"
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, timeout=15, capture_output=True)
    proc = subprocess.run(
        [sys.executable, str(CHECK_PROPOSAL)], cwd=repo, capture_output=True, text=True, timeout=30
    )
    assert "No new plan proposed" not in proc.stdout
    assert proc.returncode == 0  # spine carries a valid G/W/T roll-up


def test_bc13_spine_without_gwt_fails_proposal(tmp_path: Path) -> None:
    repo = _proposal_repo(tmp_path)
    d = repo / "docs/development/plans/2026-01-03-plan-1-w"
    d.mkdir()
    (d / "2026-01-03-plan-1-w.md").write_text("# Plan\n\nStatus: DRAFT\n\nNo contract.\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, timeout=15, capture_output=True)
    proc = subprocess.run(
        [sys.executable, str(CHECK_PROPOSAL)], cwd=repo, capture_output=True, text=True, timeout=30
    )
    assert proc.returncode == 1


# --- Behavior Contract 14 + 25: docs_updater dir-awareness + BLOCKED vocab -------


def test_bc14_plans_table_lists_spine_and_skips_archived(
    plans_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.docs_updater as du

    _write(plans_env, SPINE, SPINE_OK)
    # REAL archived plan set on disk (an empty archived dir would make the
    # exclusion assertion vacuous — the regex filter must be what excludes it).
    _write(
        plans_env,
        "docs/development/plans/archived/2026-01-01-plan-9-done/2026-01-01-plan-9-done.md",
        "# done\n",
    )
    # NON-VACUOUS guards: a NON-dated dir with a same-stem spine inside proves the
    # regex filter (not just an empty-dir accident) keeps it out of the table.
    _write(plans_env, "docs/development/plans/notes/notes.md", "# scratch\n")
    monkeypatch.setattr(du, "PLANS_DIR", plans_env / "docs/development/plans")
    table = du.generate_plans_table()
    assert "plans/2026-01-01-plan-1-widget/2026-01-01-plan-1-widget.md" in table
    assert "T01" not in table
    assert "plan-9-done" not in table
    assert "notes.md" not in table


def test_bc25_blocked_status_is_parsed(plans_env: Path) -> None:
    import scripts.docs_updater as du

    p = _write(plans_env, "blocked-plan.md", "# P\n\nStatus: BLOCKED — quota (Phase B)\n")
    status, _, _ = du.parse_plan_status(p)
    assert status == "BLOCKED"


def test_bc25_plain_converged_status_is_parsed(plans_env: Path) -> None:
    import scripts.docs_updater as du

    p = _write(plans_env, "conv-plan.md", "# P\n\nStatus: CONVERGED\n")
    status, _, _ = du.parse_plan_status(p)
    assert status == "CONVERGED"


# --- Review-fix regressions (Phase A adjudicated findings) --------------------------


def test_colon_outside_bold_status_is_modern(plans_env: Path) -> None:
    # O4: `**Status**: DRAFT` (colon outside the bold) must classify modern.
    body = MODERN_MONOLITH.replace("Status: DRAFT", "**Status**: DRAFT")
    p = _write(plans_env, "docs/development/plans/2026-01-01-plan-1-cb.md", body)
    assert "error" not in _sev(cpq_mod.check_file(p))
    # and at CONVERGED with a pillar missing it must ERROR (not grandfathered)
    broken = body.replace("**Status**: DRAFT", "**Status**: CONVERGED").replace(
        "## Evidence", "## Nothing"
    )
    p2 = _write(plans_env, "docs/development/plans/2026-01-01-plan-2-cb.md", broken)
    assert "error" in _sev(cpq_mod.check_file(p2))


def test_old_vocab_plan_without_pillars_is_grandfathered(plans_env: Path) -> None:
    # O8: a pre-pipeline plan saying `Status: EXECUTED` with no pillars → WARN only.
    p = _write(
        plans_env,
        "docs/development/plans/2026-01-01-plan-1-oldexec.md",
        "# Old\n\n**Status:** EXECUTED\n\n## Steps\n\n1. done\n",
    )
    assert _sev(cpq_mod.check_file(p)) == {"warn"}


def test_prose_status_line_does_not_trip_ticket_ban(plans_env: Path) -> None:
    # O10: prose ABOUT statuses (no colon) is not a Status: line.
    _write(plans_env, SPINE, SPINE_OK.replace("Status: DRAFT", "Status: CONVERGED"))
    t = TICKET_OK + "\n- Status flips are the orchestrator's job, not this ticket's.\n"
    p = _write(plans_env, f"{DIR}/T01-widget-schema.md", t)
    results = cpq_mod.check_file(p)
    assert not any("Status" in r.message and r.severity.value == "error" for r in results)


def test_relative_path_is_resolved(plans_env: Path) -> None:
    # O2: validate_conventions feeds relative paths — the gates must resolve them.
    rel = Path("docs/development/plans/T01-loose.md")
    _write(plans_env, str(rel), "junk")
    assert "error" in _sev(cp_mod.check_file(rel))


def test_bc14_table_lists_spine_not_tickets_for_real(
    plans_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # O24: non-vacuous — a ticket file EXISTS and still must not be listed.
    import scripts.docs_updater as du

    _write(plans_env, SPINE, SPINE_OK)
    _write(plans_env, f"{DIR}/T01-widget-schema.md", TICKET_OK)
    monkeypatch.setattr(du, "PLANS_DIR", plans_env / "docs/development/plans")
    table = du.generate_plans_table()
    assert "plans/2026-01-01-plan-1-widget/2026-01-01-plan-1-widget.md" in table
    assert "T01-widget-schema.md" not in table


def test_validate_plan_consistency_reads_spine_status(
    plans_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # O24: the LIVE consumer — a COMPLETE spine with unchecked boxes must be flagged.
    import scripts.docs_updater as du

    spine = SPINE_OK.replace("Status: DRAFT", "**Status:** COMPLETE") + "\n- [ ] undone item\n"
    _write(plans_env, SPINE, spine)
    monkeypatch.setattr(du, "PLANS_DIR", plans_env / "docs/development/plans")
    errors = du.validate_plan_consistency()
    assert any("unchecked" in e for e in errors)


# --- Fence policy (review rounds 4-5) --------------------------------------------


def test_fenced_ticket_board_does_not_make_a_monolith_a_spine(plans_env: Path) -> None:
    body = MODERN_MONOLITH.replace(
        "## Context Ledger",
        "Quoted example:\n\n```markdown\n## Ticket Board\n```\n\n## Context Ledger",
    )
    p = _write(plans_env, "docs/development/plans/2026-01-01-plan-4-mono.md", body)
    results = cpq_mod.check_file(p)
    assert not any("Merge Order" in r.message for r in results)


def test_fenced_pillar_does_not_satisfy_the_requirement(plans_env: Path) -> None:
    body = (
        MODERN_MONOLITH.replace("Status: DRAFT", "Status: CONVERGED").replace(
            "## Evidence", "## Nothing"
        )
        + "\n```markdown\n## Evidence\n```\n"
    )
    p = _write(plans_env, "docs/development/plans/2026-01-01-plan-5-mono.md", body)
    assert any(
        r.severity.value == "error" and "Evidence" in r.message for r in cpq_mod.check_file(p)
    )


def test_fenced_status_is_ignored_by_docs_updater(plans_env: Path) -> None:
    import scripts.docs_updater as du

    p = _write(
        plans_env,
        "status-fence.md",
        "# P\n\n```\nStatus: draft-example\n```\n\n**Status:** COMPLETE\n",
    )
    status, _, _ = du.parse_plan_status(p)
    assert status == "COMPLETE"


# --- Wave-7 regressions (review round 7) ---------------------------------------------


def test_tracked_bad_name_warns_not_errors(plans_env: Path) -> None:
    # Pre-existing (tracked-at-HEAD) invalid names are settled fleet history.
    subprocess.run(
        ["git", "init", "-q"], cwd=plans_env, check=True, timeout=15, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "t@t"],
        cwd=plans_env,
        check=True,
        timeout=15,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "t"],
        cwd=plans_env,
        check=True,
        timeout=15,
        capture_output=True,
    )
    p = _write(plans_env, "docs/development/plans/my-old-notes.md", "junk")
    subprocess.run(["git", "add", "-A"], cwd=plans_env, check=True, timeout=15, capture_output=True)
    subprocess.run(
        ["git", "commit", "-qm", "seed"], cwd=plans_env, check=True, timeout=15, capture_output=True
    )
    results = cp_mod.check_file(p)
    assert any(r.severity.value == "warn" and "Invalid plan filename" in r.message for r in results)
    # …while a NEW bad name (staged or not) stays ERROR:
    p2 = _write(plans_env, "docs/development/plans/new-bad-notes.md", "junk")
    subprocess.run(["git", "add", "-A"], cwd=plans_env, check=True, timeout=15, capture_output=True)
    results2 = cp_mod.check_file(p2)
    assert any(r.severity.value == "error" for r in results2)


def test_strict_exempts_plan_check_warns(plans_env: Path) -> None:
    # The designed advisories must not re-promote under --strict.
    import subprocess as sp
    import sys as _sys

    p = _write(plans_env, "docs/development/plans/2026-01-01-plan-1-leg.md", LEGACY_PLAN)
    env = dict(__import__("os").environ, PYTHONPATH="/opt/fabrik")
    proc = sp.run(
        [_sys.executable, "-m", "scripts.enforcement.validate_conventions", "--strict", str(p)],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=plans_env,  # PLAN_DIR is cwd-derived — /opt/fabrik cwd would skip the file entirely
        env=env,
    )
    # The check must actually FIRE (a warn emitted) AND --strict must not promote it.
    assert "Legacy plan" in proc.stdout, proc.stdout + proc.stderr
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_docs_updater_counts_fenced_checkboxes_raw(plans_env: Path) -> None:
    import scripts.docs_updater as du

    p = _write(
        plans_env,
        "raw-boxes.md",
        "# P\n\n**Status:** COMPLETE\n\n## DONE WHEN\n\n```\n- [ ] fenced undone box\n```\n- [x] real done box\n",
    )
    status, checked, total = du.parse_plan_status(p)
    assert status == "COMPLETE"
    assert (checked, total) == (1, 2)  # fenced box still counted — counters stay RAW


def test_count_behaviors_ignores_fenced_examples() -> None:
    # A fenced example row inside ## Behavior Contract must not count — the
    # Tier-2 gate would otherwise pass an under-enumerated plan (fail-open).
    import scripts.enforcement.check_test_proposal as ctp

    content = (
        "# Plan\n\n## Behavior Contract\n\n"
        "- **Given** real, **When** run, **Then** works.\n\n"
        "```markdown\n"
        "- **Given** example one, **When** copied, **Then** must not count.\n"
        "- **Given** example two, **When** copied, **Then** must not count.\n"
        "```\n"
    )
    assert ctp._count_behaviors(content) == 1


def test_count_criteria_ignores_fenced_examples() -> None:
    # Symmetric strip: fenced example criteria must not inflate the denominator
    # (one-sided stripping failed healthy plans at Tier-2).
    import scripts.enforcement.check_test_proposal as ctp

    content = (
        "# Plan\n\n## Success criteria\n\n- real one\n\n"
        "```markdown\n- fenced example criterion\n- another\n```\n"
    )
    assert ctp._count_criteria(content) == 1


def test_fenced_heading_does_not_hijack_section() -> None:
    # A fenced `## Behavior Contract` template (the emitted worked skeleton)
    # must not hijack _section's first-heading match — strip precedes extract.
    import scripts.enforcement.check_test_proposal as ctp

    content = (
        "# Plan\n\n```markdown\n## Behavior Contract\n- **Given** template row.\n```\n\n"
        "## Behavior Contract\n\n"
        "- **Given** a, **When** b, **Then** c.\n"
        "- **Given** d, **When** e, **Then** f.\n"
    )
    assert ctp._count_behaviors(content) == 2


def test_fenced_hash_comment_does_not_truncate_section() -> None:
    # A fenced `# comment` line must not act as a section terminator — the
    # strip-first order removes it before _section scans for headings.
    import scripts.enforcement.check_test_proposal as ctp

    content = (
        "# Plan\n\n## Behavior Contract\n\n"
        "- **Given** a, **When** b, **Then** c.\n\n"
        "```bash\n# a shell comment\necho hi\n```\n\n"
        "- **Given** d, **When** e, **Then** f.\n"
        "- **Given** g, **When** h, **Then** i.\n"
    )
    assert ctp._count_behaviors(content) == 3


def test_all_fenced_criteria_section_is_structure_only() -> None:
    # Quoted content is never a denominator: an all-fenced criteria section
    # counts 0 (the comparison is skipped) — a raw fallback would re-open the
    # inflation and fenced-template-hijack holes.
    import scripts.enforcement.check_test_proposal as ctp

    content = (
        "# Plan\n\n## Success criteria\n\n```markdown\n- fenced only one\n- fenced only two\n```\n"
    )
    assert ctp._count_criteria(content) == 0


def test_quality_field_presence_accepts_bolded_complexity() -> None:
    # The two gates must agree on `**Complexity:**` — quality's presence regex
    # is bold-tolerant like check_plan_tickets' parser.
    import scripts.enforcement.check_plan_quality as cpq

    fields = dict(cpq.TICKET_FIELDS)
    for name in ("Complexity", "Depends", "Parallel", "Docs", "Gate"):
        assert fields[name].search(f"**{name}:** value"), name
        assert fields[name].search(f"{name}: value"), name
        # Blockquoted examples must NOT count as field presence (quoted content).
        assert not fields[name].search(f"> {name}: value"), name
