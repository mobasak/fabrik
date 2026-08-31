"""Tests for scripts/enforcement/check_plan_tickets.py (Behavior Contract 7-12, 16-17, 19-24, 26-30, 32-34).

Builds throwaway plan sets under tmp_path (<root>/docs/development/plans/<dated-dir>/)
and drives check_plan_dir / the check_file adapter / the CLI directly.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.enforcement import check_plan_tickets as cpt

DIRNAME = "2026-01-02-plan-1-widget"

T01 = """# T01 — schema

Depends: none
Parallel: ⚡
Complexity: simple
Docs: none
Gate: pytest -q tests/test_schema.py

## Scope

Schema. DO-NOT touch the api.

## Touches

- src/app/schema.py

## Behavior Contract

- **Given** a widget, **When** saved, **Then** it persists (src/app/schema.py:1).

## Context Files

- docs/small-context.md
"""

T02 = """# T02 — api

Depends: T01
Parallel: ⛓️
Complexity: simple
Docs: none
Gate: pytest -q tests/test_api.py

## Scope

API layer. DO-NOT touch schema internals.

## Touches

- src/app/api.py

## Behavior Contract

- **Given** a request, **When** posted, **Then** 201 (src/app/api.py:1).

## Context Files

- docs/small-context.md
"""

T99 = """# T99 — integration

Depends: T02
Parallel: ⛓️
Complexity: native
Docs: whole-plan receipt
Gate: python scripts/enforcement/check_doc_sync.py
Integration: true

## Scope

Integration receipts. DO-NOT write code.

## Touches

- docs/receipt-notes.md

## Behavior Contract

- **Given** the merged plan, **When** receipts run, **Then** green (docs/receipt-notes.md:1).

## Context Files

- docs/small-context.md
"""

SPINE = """# Plan: widget

Status: DRAFT

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | schema | — | ⚡ | ⬜ | |
| T02 | api | T01 | ⛓️ | ⬜ | |
| T99 | integration | T02 | ⛓️ | ⬜ | |

## Merge Order

1. T01
2. T02
3. T99

## Interfaces

None.

## Behavior Contract

- **Given** a widget, **When** saved, **Then** it persists (src/app/schema.py:1).
- **Given** a request, **When** posted, **Then** 201 (src/app/api.py:1).
- **Given** the merged plan, **When** receipts run, **Then** green (docs/receipt-notes.md:1).

## Global Constraints

- None.

## Context Ledger

| a | b | c |

## File Scope (owned paths)

- src/app/schema.py
- src/app/api.py
- docs/receipt-notes.md

## Evidence

src/app/schema.py:1

```
$ true
ok
```
"""


def _build(
    root: Path,
    spine: str = SPINE,
    tickets: dict[str, str] | None = None,
    dirname: str = DIRNAME,
) -> Path:
    plan_dir = root / "docs" / "development" / "plans" / dirname
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / f"{dirname}.md").write_text(spine, encoding="utf-8")
    for name, content in (
        tickets or {"T01-schema.md": T01, "T02-api.md": T02, "T99-integration.md": T99}
    ).items():
        (plan_dir / name).write_text(content, encoding="utf-8")
    (root / "docs" / "small-context.md").parent.mkdir(parents=True, exist_ok=True)
    (root / "docs" / "small-context.md").write_text("tiny\n", encoding="utf-8")
    return plan_dir


def _errors(results) -> list[str]:
    return [r.message for r in results if r.severity.value == "error"]


def _warns(results) -> list[str]:
    return [r.message for r in results if r.severity.value == "warn"]


def test_valid_plan_set_is_clean(tmp_path: Path) -> None:
    plan_dir = _build(tmp_path)
    assert _errors(cpt.check_plan_dir(plan_dir)) == []


# --- BC 7: shared paths -----------------------------------------------------------


def test_bc7_parallel_shared_path_without_serialized_errors(tmp_path: Path) -> None:
    t2 = T02.replace("Depends: T01", "Depends: none").replace("Parallel: ⛓️", "Parallel: ⚡")
    t2 = t2.replace("- src/app/api.py", "- src/app/schema.py")
    spine = SPINE.replace("- src/app/api.py\n", "")
    plan_dir = _build(
        tmp_path,
        spine=spine,
        tickets={"T01-schema.md": T01, "T02-api.md": t2, "T99-integration.md": T99},
    )
    assert any("Touches overlap" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


def test_bc7_depends_connected_shared_path_passes(tmp_path: Path) -> None:
    t2 = T02.replace("- src/app/api.py", "- src/app/schema.py")  # keeps Depends: T01
    spine = SPINE.replace("- src/app/api.py\n", "")
    plan_dir = _build(
        tmp_path,
        spine=spine,
        tickets={"T01-schema.md": T01, "T02-api.md": t2, "T99-integration.md": T99},
    )
    assert not any("Touches overlap" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


def test_bc7_serialized_row_licences_parallel_share(tmp_path: Path) -> None:
    t2 = T02.replace("Depends: T01", "Depends: none").replace("Parallel: ⛓️", "Parallel: ⚡")
    t2 = t2.replace("- src/app/api.py", "- src/app/schema.py")
    spine = SPINE.replace("- src/app/api.py\n", "").replace(
        "3. T99\n", "3. T99\n\nSerialized: src/app/schema.py — T01, T02\n"
    )
    plan_dir = _build(
        tmp_path,
        spine=spine,
        tickets={"T01-schema.md": T01, "T02-api.md": t2, "T99-integration.md": T99},
    )
    assert not any("Touches overlap" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


# --- BC 8: cycles -----------------------------------------------------------------


def test_bc8_cyclic_depends_errors(tmp_path: Path) -> None:
    t1 = T01.replace("Depends: none", "Depends: T02")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    assert any("cycle" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


# --- BC 9: READ budget severity by context ------------------------------------------


def test_bc9_budget_overrun_errors_in_cli_and_warns_in_gate_path(tmp_path: Path) -> None:
    plan_dir = _build(tmp_path)
    big = tmp_path / "src" / "app" / "schema.py"
    big.parent.mkdir(parents=True, exist_ok=True)
    big.write_text("x" * (cpt.READ_BUDGET_BYTES + 1), encoding="utf-8")
    cli = cpt.check_plan_dir(plan_dir, context="cli")
    assert any("READ budget" in m for m in _errors(cli))
    gate = cpt.check_plan_dir(plan_dir, context="gate")  # spine is DRAFT
    assert not any("READ budget" in m for m in _errors(gate))
    assert any("READ budget" in m for m in _warns(gate))


def test_bc9_budget_overrun_names_the_entry_that_blew_it(tmp_path: Path) -> None:
    """The total says a ticket is too big; only the breakdown says WHICH entry did it.

    The usual culprit is a directory entry silently owning a large subtree — a total
    alone costs a debugging loop to localise (transdoc, 2026-08-22: 102KB from
    `public/i18n/`).
    """
    t1 = T01.replace("- src/app/schema.py", "- src/app/schema.py\n- src/bulk/")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    (tmp_path / "src" / "app").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "app" / "schema.py").write_text("x" * 10, encoding="utf-8")
    bulk = tmp_path / "src" / "bulk"
    bulk.mkdir(parents=True, exist_ok=True)
    (bulk / "big.py").write_text("y" * (cpt.READ_BUDGET_BYTES + 1), encoding="utf-8")
    msg = next(m for m in _errors(cpt.check_plan_dir(plan_dir, context="cli")) if "READ budget" in m)
    assert "src/bulk/=" in msg, msg  # the subtree entry is named, not just the total
    assert str(cpt.READ_BUDGET_BYTES + 1) in msg


# --- BC 11: grounding floor ----------------------------------------------------------


def test_bc11_ticket_without_citation_errors(tmp_path: Path) -> None:
    t1 = T01.replace("(src/app/schema.py:1)", "(no citation here)")
    spine = SPINE.replace("it persists (src/app/schema.py:1)", "it persists (no citation here)")
    plan_dir = _build(
        tmp_path,
        spine=spine,
        tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99},
    )
    assert any("grounding floor" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


# --- BC 12: adapter dedupe -----------------------------------------------------------


def test_bc12_adapter_emits_once_per_dir_first_file_attached(tmp_path: Path) -> None:
    plan_dir = _build(tmp_path)
    cpt._SEEN_DIRS.clear()
    first = cpt.check_file(plan_dir / "T01-schema.md")
    second = cpt.check_file(plan_dir / f"{DIRNAME}.md")
    assert first == []  # clean set → no findings (the dedupe proof lives in
    # test_bc12_dedupe_is_real_not_vacuous, which uses a set WITH a finding)
    assert second == []
    assert plan_dir.resolve() in cpt._SEEN_DIRS
    cpt._SEEN_DIRS.clear()


# --- BC 16: governance files ----------------------------------------------------------


def test_bc16_governance_file_in_touches_errors(tmp_path: Path) -> None:
    t1 = T01.replace("- src/app/schema.py", "- src/app/schema.py\n- CHANGELOG.md")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    assert any("governance file" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


def test_bc16_decisions_ledger_in_touches_errors(tmp_path: Path) -> None:
    """docs/DECISIONS.md is the sixth governance surface: per-run shared-append (close-out
    decision line) AND pen-holder-restricted (CLAUDE.md § the decision ledger — subagents
    never hold the pen). A ticket touching it hands a coder subagent exactly that pen."""
    t1 = T01.replace("- src/app/schema.py", "- src/app/schema.py\n- docs/DECISIONS.md")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    assert any("governance file" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


def test_bc16_strategic_backlog_in_touches_errors(tmp_path: Path) -> None:
    """docs/STRATEGIC_BACKLOG.md is the seventh governance surface (Doc Sync Matrix deferred-work
    append; repo-review/upstream mandate per-run appends — the CHANGELOG collision class)."""
    t1 = T01.replace("- src/app/schema.py", "- src/app/schema.py\n- docs/STRATEGIC_BACKLOG.md")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    assert any("governance file" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


def test_bc16_governance_file_in_context_files_is_fine(tmp_path: Path) -> None:
    t1 = T01.replace("- docs/small-context.md", "- docs/small-context.md\n- CHANGELOG.md")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    assert not any("governance file" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


# --- BC 17: never-route cross-check ----------------------------------------------------


def test_bc17_pool_tier_ticket_touching_never_route_errors(tmp_path: Path) -> None:
    t1 = T01.replace("- src/app/schema.py", "- scripts/enforcement/check_foo.py")
    spine = SPINE.replace("- src/app/schema.py", "- scripts/enforcement/check_foo.py")
    plan_dir = _build(
        tmp_path,
        spine=spine,
        tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99},
    )
    assert any("never-route" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


# --- BC 19/20: archived exemption + same-stem spine -------------------------------------


def test_bc19_archived_plan_dir_is_skipped(tmp_path: Path) -> None:
    plan_dir = tmp_path / "docs" / "development" / "plans" / "archived" / DIRNAME
    plan_dir.mkdir(parents=True)
    (plan_dir / "T01-x.md").write_text("junk", encoding="utf-8")
    assert cpt.check_plan_dir(plan_dir) == []


def test_bc20_missing_same_stem_spine_errors(tmp_path: Path) -> None:
    plan_dir = tmp_path / "docs" / "development" / "plans" / DIRNAME
    plan_dir.mkdir(parents=True)
    (plan_dir / "T01-x.md").write_text(T01, encoding="utf-8")
    assert any("same-stem spine" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


# --- BC 22/23: Integration rules ----------------------------------------------------------


def test_bc22_two_integration_tickets_errors(tmp_path: Path) -> None:
    t2 = T02.replace("Gate: pytest -q tests/test_api.py", "Gate: x\nIntegration: true")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": T01, "T02-api.md": t2, "T99-integration.md": T99}
    )
    assert any("exactly one" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


def test_bc22_integration_not_last_errors(tmp_path: Path) -> None:
    spine = SPINE.replace("1. T01\n2. T02\n3. T99", "1. T01\n2. T99\n3. T02")
    plan_dir = _build(tmp_path, spine=spine)
    assert any("must be LAST" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


def test_bc23_integration_ticket_budget_exempt(tmp_path: Path) -> None:
    plan_dir = _build(tmp_path)
    big = tmp_path / "docs" / "receipt-notes.md"
    big.write_text("x" * (cpt.READ_BUDGET_BYTES + 1), encoding="utf-8")
    results = cpt.check_plan_dir(plan_dir, context="cli")
    assert not any("READ budget" in m for m in _errors(results) + _warns(results))


# --- BC 24: roll-up equality -----------------------------------------------------------


def test_bc24_rollup_missing_ticket_row_errors(tmp_path: Path) -> None:
    spine = SPINE.replace(
        "- **Given** a request, **When** posted, **Then** 201 (src/app/api.py:1).\n", ""
    )
    plan_dir = _build(tmp_path, spine=spine)
    assert any("roll-up missing" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


# The (path:line) citation is GROUNDING, not identity. The skeleton at
# fabrik-plan-after-chat.md teaches "**Then** <observable> (src/app/x.py:12)", so an
# author who follows it cites the ticket's own line in the ticket and the primary path
# in the spine — two different strings for ONE behavior, which the roll-up scored as
# missing-row PLUS matches-no-ticket. Two ERRORs per faithfully-cited row (transdoc,
# 2026-08-22: ~30 on a 16-ticket set; their workaround was to strip every citation,
# i.e. the gate punished the exact grounding habit it teaches).


def test_bc24_rollup_ignores_differing_citation_lines(tmp_path: Path) -> None:
    spine = SPINE.replace("**Then** 201 (src/app/api.py:1)", "**Then** 201 (src/app/api.py:47)")
    assert _errors(cpt.check_plan_dir(_build(tmp_path, spine=spine))) == []


def test_bc24_rollup_ignores_citation_present_on_one_side_only(tmp_path: Path) -> None:
    spine = SPINE.replace("**Then** 201 (src/app/api.py:1).", "**Then** 201.")
    assert _errors(cpt.check_plan_dir(_build(tmp_path, spine=spine))) == []


def test_bc24_rollup_ignores_multi_path_citations(tmp_path: Path) -> None:
    spine = SPINE.replace(
        "**Then** 201 (src/app/api.py:1)", "**Then** 201 (src/app/api.py:12, src/app/schema.py:8)"
    )
    assert _errors(cpt.check_plan_dir(_build(tmp_path, spine=spine))) == []


def test_bc24_rollup_still_catches_a_genuinely_different_behavior(tmp_path: Path) -> None:
    """Forgiving the citation must not forgive the SENTENCE — else the check stops asking."""
    spine = SPINE.replace(
        "**When** posted, **Then** 201 (src/app/api.py:1)",
        "**When** posted, **Then** 500 (src/app/api.py:1)",
    )
    errs = _errors(cpt.check_plan_dir(_build(tmp_path, spine=spine)))
    assert any("roll-up missing" in m for m in errs)
    assert any("matches no ticket" in m for m in errs)


def test_bc24_rollup_does_not_strip_a_non_citation_parenthetical(tmp_path: Path) -> None:
    """`(observable)` is prose, not grounding — stripping it would erase real signal."""
    spine = SPINE.replace("**Then** 201 (src/app/api.py:1)", "**Then** 201 (idempotently)")
    assert any("matches no ticket" in m for m in _errors(cpt.check_plan_dir(_build(tmp_path, spine=spine))))


# --- BC 10 + 21: board staleness (execution window) ---------------------------------------


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, timeout=20, capture_output=True)


def _repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    return tmp_path


def test_bc10_21_staleness_window(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    plan_dir = _build(root)
    (root / "src" / "app").mkdir(parents=True, exist_ok=True)
    (root / "src" / "app" / "schema.py").write_text("# v1\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "baseline")
    baseline = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()

    # No lock → skipped entirely (BC 10 second half).
    (root / "src" / "app" / "schema.py").write_text("# v2\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "touch schema without trailer")
    res = cpt.check_plan_dir(plan_dir)
    assert not any("Agent-Task" in m for m in _errors(res) + _warns(res))

    # Lock with baseline → trailer-less Touches commit WARNs (BC 21 — WARN, not
    # ERROR: on shared master the commit may be a sibling's or the daily
    # pipeline's; an unfixable hard-block would red the gate for the plan's life).
    locks = root / ".fabrik" / "plan-locks"
    locks.mkdir(parents=True)
    (locks / f"{DIRNAME}.json").write_text(
        json.dumps({"plan": "x", "status": "active", "baseline_commit": baseline}),
        encoding="utf-8",
    )
    res = cpt.check_plan_dir(plan_dir)
    assert any("without an 'Agent-Task: T01'" in m for m in _warns(res))
    assert not any("without an 'Agent-Task: T01'" in m for m in _errors(res))

    # Trailer commit while the Board row is still ⬜ → ERROR (BC 10 first half).
    # Plan identity: the commit must touch the plan DIR (the same-commit
    # Board-flip discipline stages the spine) — a trailer commit elsewhere
    # belongs to some other plan and is ignored.
    (root / "src" / "app" / "schema.py").write_text("# v3\n", encoding="utf-8")
    spine_file = plan_dir / f"{DIRNAME}.md"
    spine_file.write_text(
        spine_file.read_text(encoding="utf-8") + "\n<!-- t -->\n", encoding="utf-8"
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "feat: T01 work\n\nAgent-Task: T01")
    msgs = _errors(cpt.check_plan_dir(plan_dir))
    assert any("still ⬜" in m for m in msgs)

    # Cross-plan negative: a trailer commit that does NOT touch this plan's dir
    # (another plan's T01) must neither credit nor blame this board.
    (root / "unrelated.txt").write_text("x\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "feat: other plan work\n\nAgent-Task: T02")
    msgs = _errors(cpt.check_plan_dir(plan_dir))
    assert not any("'Agent-Task: T02' but the Board row" in m for m in msgs)

    # Row flipped past ⬜ → the never-flipped ERROR clears for that commit.
    spine_p = plan_dir / f"{DIRNAME}.md"
    spine_p.write_text(
        spine_p.read_text(encoding="utf-8").replace(
            "| T01 | schema | — | ⚡ | ⬜ | |", "| T01 | schema | — | ⚡ | ✅ | abc123 |"
        ),
        encoding="utf-8",
    )
    msgs = _errors(cpt.check_plan_dir(plan_dir))
    assert not any("still ⬜" in m for m in msgs)


# --- BC 26: no-arg CLI selects active-lock plan dirs ---------------------------------------


def test_bc26_noarg_cli_selects_active_lock_dir(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    plan_dir = _build(root)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed")
    locks = root / ".fabrik" / "plan-locks"
    locks.mkdir(parents=True)
    (locks / f"{DIRNAME}.json").write_text(
        json.dumps({"plan": "x", "status": "active", "owned_paths": ["src/app/schema.py"]}),
        encoding="utf-8",
    )
    # Only an implementation file changes — TRACKED (untracked files are a
    # sibling's in-flight draft and are deliberately excluded from discovery).
    (root / "src" / "app").mkdir(parents=True, exist_ok=True)
    (root / "src" / "app" / "schema.py").write_text("seed\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "track schema")
    (root / "src" / "app" / "schema.py").write_text("changed\n", encoding="utf-8")
    dirs, lock_only = cpt._discover_dirs(root)
    assert plan_dir.resolve() in [d.resolve() for d in dirs]
    # Selected ONLY via the lock (my change didn't touch the plan dir) → marked
    # lock_only, so the CLI downgrades its findings to sibling-advisory WARNs.
    assert plan_dir.resolve() in {d.resolve() for d in lock_only}
    # Committed-but-unpushed must ALSO be discovered (execute-plan commits per
    # phase and THEN runs the gate) — needs an upstream to diff against.
    _git(root, "checkout", "-q", "-b", "work")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "wip")
    _git(root, "branch", "-q", "base")
    _git(root, "branch", "-q", "--set-upstream-to=base", "work")
    (root / "src" / "app" / "schema.py").write_text("committed change\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "implementation commit, no board flip")
    dirs2, _ = cpt._discover_dirs(root)
    assert plan_dir.resolve() in [d.resolve() for d in dirs2]


# --- Review-fix regressions (Phase A adjudicated findings) --------------------------


def test_dir_vs_file_touches_overlap_errors(tmp_path: Path) -> None:
    # O3: a directory entry covering another ticket's file is an overlap.
    t1 = T01.replace("- src/app/schema.py", "- src/app/")
    t2 = T02.replace("Depends: T01", "Depends: none")
    spine = SPINE.replace("- src/app/schema.py", "- src/app/")
    plan_dir = _build(
        tmp_path,
        spine=spine,
        tickets={"T01-schema.md": t1, "T02-api.md": t2, "T99-integration.md": T99},
    )
    assert any("Touches overlap" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


def test_unknown_depends_target_errors(tmp_path: Path) -> None:
    # O13: a Depends typo must be loud, not silently dropped.
    t2 = T02.replace("Depends: T01", "Depends: T05")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": T01, "T02-api.md": t2, "T99-integration.md": T99}
    )
    assert any("unknown ticket T05" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


def test_env_example_is_not_never_route(tmp_path: Path) -> None:
    # O11: .env.example is a routine Doc-Sync file; .env.production is a secret.
    assert not cpt._never_route(".env.example")
    assert cpt._never_route(".env")
    assert cpt._never_route(".env.production")


def test_bold_board_cell_is_parsed(tmp_path: Path) -> None:
    # S4: | **T01** | must not vanish from the row set.
    spine = SPINE.replace("| T01 | schema", "| **T01** | schema")
    plan_dir = _build(tmp_path, spine=spine)
    assert not any("has no Ticket Board row" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


def test_serialized_accepts_plain_hyphen(tmp_path: Path) -> None:
    # S2: `Serialized: <path> - T01, T02` (plain hyphen) must license the pair.
    t2 = T02.replace("Depends: T01", "Depends: none").replace("Parallel: ⛓️", "Parallel: ⚡")
    t2 = t2.replace("- src/app/api.py", "- src/app/schema.py")
    spine = SPINE.replace("- src/app/api.py\n", "").replace(
        "3. T99\n", "3. T99\n\nSerialized: src/app/schema.py - T01, T02\n"
    )
    plan_dir = _build(
        tmp_path,
        spine=spine,
        tickets={"T01-schema.md": T01, "T02-api.md": t2, "T99-integration.md": T99},
    )
    assert not any("Touches overlap" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


def test_bc12_dedupe_is_real_not_vacuous(tmp_path: Path) -> None:
    # O24: prove the dedupe on a plan set that HAS a finding (orphan Board row).
    spine = SPINE.replace(
        "| T02 | api | T01 | ⛓️ | ⬜ | |",
        "| T02 | api | T01 | ⛓️ | ⬜ | |\n| T77 | ghost | — | ⚡ | ⬜ | — |",
    )
    plan_dir = _build(tmp_path, spine=spine)
    cpt._SEEN_DIRS.clear()
    first = cpt.check_file(plan_dir / "T01-schema.md")
    second = cpt.check_file(plan_dir / f"{DIRNAME}.md")
    assert any("orphan row" in r.message for r in first)
    assert second == []
    cpt._SEEN_DIRS.clear()


def test_archived_under_plans_only_is_exempt_not_any_abs_path(tmp_path: Path) -> None:
    # O12: a repo living under a dir literally named 'archived' must still be checked.
    root = tmp_path / "archived" / "someproj"
    plan_dir = root / "docs" / "development" / "plans" / DIRNAME
    plan_dir.mkdir(parents=True)
    (plan_dir / "T01-x.md").write_text(T01, encoding="utf-8")
    # no spine → the same-stem ERROR must fire (gate NOT disabled by the abs path)
    assert any("same-stem spine" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


# --- Fence policy + wave-5 severity matrix (review rounds 4-5) ----------------------


def test_fenced_board_example_is_not_an_orphan_row(tmp_path: Path) -> None:
    spine = SPINE.replace(
        "## Interfaces",
        "## Interfaces\n\nRow format example:\n\n```\n| T77 | ghost | — | ⚡ | ⬜ | — |\n```\n",
    )
    plan_dir = _build(tmp_path, spine=spine)
    assert not any("T77" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


def test_fenced_integration_example_does_not_steal_the_role(tmp_path: Path) -> None:
    t1 = T01.replace(
        "## Scope",
        "## Scope\n\nHeader example:\n\n```\nIntegration: true\nDepends: T55\n```\n",
    )
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    errs = _errors(cpt.check_plan_dir(plan_dir))
    assert not any("exactly one" in m for m in errs)  # T99 keeps the role
    assert not any("T55" in m for m in errs)  # fenced Depends not parsed


def test_fenced_citation_still_satisfies_grounding_floor(tmp_path: Path) -> None:
    # PROOF stays RAW by design — evidence legitimately lives in fenced output.
    t1 = T01.replace(
        "- **Given** a widget, **When** saved, **Then** it persists (src/app/schema.py:1).",
        "- **Given** a widget, **When** saved, **Then** it persists.\n\n```\ngrounded at src/app/schema.py:1\n```",
    )
    spine = SPINE.replace(
        "- **Given** a widget, **When** saved, **Then** it persists (src/app/schema.py:1).",
        "- **Given** a widget, **When** saved, **Then** it persists.",
    )
    plan_dir = _build(
        tmp_path,
        spine=spine,
        tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99},
    )
    assert not any("grounding floor" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


def test_unrecognized_spine_status_fails_closed(tmp_path: Path) -> None:
    spine = SPINE.replace("Status: DRAFT", "Status: COMPLETE").replace(
        "| T02 | api | T01 | ⛓️ | ⬜ | |",
        "| T02 | api | T01 | ⛓️ | ⬜ | |\n| T88 | ghost | — | ⚡ | ⬜ | — |",
    )
    plan_dir = _build(tmp_path, spine=spine)
    res = cpt.check_plan_dir(plan_dir, context="gate")
    # NOT downgraded (unknown ≠ draft-like): orphan stays ERROR + the status itself flagged
    assert any("orphan row" in m for m in _errors(res))
    assert any("not a pipeline value" in m for m in _errors(res))


def test_blockquoted_status_example_never_downgrades_the_gate(tmp_path: Path) -> None:
    # Pass-47 regression: a `> Status: DRAFT` example above the real line must
    # not win first-match as the spine's own status (that would silently make
    # the whole contract advisory at the gate). The real EXECUTED wins.
    spine = SPINE.replace("Status: DRAFT", "> Status: DRAFT\n\nStatus: EXECUTED").replace(
        "| T02 | api | T01 | ⛓️ | ⬜ | |",
        "| T02 | api | T01 | ⛓️ | ⬜ | |\n| T88 | ghost | — | ⚡ | ⬜ | — |",
    )
    plan_dir = _build(tmp_path, spine=spine)
    assert any("orphan row" in m for m in _errors(cpt.check_plan_dir(plan_dir, context="gate")))


def test_blockquoted_only_status_is_absent_not_parsed(tmp_path: Path) -> None:
    # Quoted content — fenced OR blockquoted — is invisible to spine-status
    # determination: a spine whose ONLY Status line is quoted behaves as
    # absent (draft-like sibling protection), never as the quoted value.
    spine = SPINE.replace("Status: DRAFT", "> Status: EXECUTED").replace(
        "| T02 | api | T01 | ⛓️ | ⬜ | |",
        "| T02 | api | T01 | ⛓️ | ⬜ | |\n| T88 | ghost | — | ⚡ | ⬜ | — |",
    )
    plan_dir = _build(tmp_path, spine=spine)
    res = cpt.check_plan_dir(plan_dir, context="gate")
    assert not any("orphan row" in m for m in _errors(res))
    assert any("orphan row" in m for m in _warns(res))


def test_blockquoted_example_does_not_mask_unrecognized_status(tmp_path: Path) -> None:
    # A quoted DRAFT example must not make a typo'd REAL status (COMPLETE)
    # look recognized — the unrecognized branch still fails closed.
    spine = SPINE.replace("Status: DRAFT", "> Status: DRAFT\n\nStatus: COMPLETE")
    plan_dir = _build(tmp_path, spine=spine)
    assert any(
        "not a pipeline value" in m for m in _errors(cpt.check_plan_dir(plan_dir, context="gate"))
    )


def test_blockquoted_never_route_adds_coverage(tmp_path: Path) -> None:
    # Pass-47 mutation kill: the `>` on the Never-Route label is load-bearing —
    # a quoted Never-Route line ADDS coverage (fail-closed direction).
    spine = SPINE.replace(
        "## Global Constraints\n\n- None.",
        "## Global Constraints\n\n> Never-Route: src/app/",
    )
    plan_dir = _build(tmp_path, spine=spine)
    assert any("route it native" in m for m in _errors(cpt.check_plan_dir(plan_dir, context="cli")))


def test_adapter_path_is_always_advisory(tmp_path: Path) -> None:
    # A CONVERGED sibling set with structural breaks must not hard-red the
    # per-file validate_conventions path (it cannot know whose plan this is).
    spine = SPINE.replace("Status: DRAFT", "Status: CONVERGED").replace(
        "| T02 | api | T01 | ⛓️ | ⬜ | |",
        "| T02 | api | T01 | ⛓️ | ⬜ | |\n| T88 | ghost | — | ⚡ | ⬜ | — |",
    )
    plan_dir = _build(tmp_path, spine=spine)
    cpt._SEEN_DIRS.clear()
    res = cpt.check_file(plan_dir / f"{DIRNAME}.md")
    assert res and not _errors(res) and _warns(res)
    cpt._SEEN_DIRS.clear()


def test_missing_spine_is_warn_in_gate_context(tmp_path: Path) -> None:
    plan_dir = tmp_path / "docs" / "development" / "plans" / DIRNAME
    plan_dir.mkdir(parents=True)
    (plan_dir / "T01-x.md").write_text(T01, encoding="utf-8")
    gate = cpt.check_plan_dir(plan_dir, context="gate")
    assert not _errors(gate) and any("same-stem spine" in m for m in _warns(gate))
    cli = cpt.check_plan_dir(plan_dir, context="cli")
    assert any("same-stem spine" in m for m in _errors(cli))


def test_unparseable_file_scope_warns_loudly(tmp_path: Path) -> None:
    spine = SPINE.replace(
        "- src/app/schema.py\n- src/app/api.py\n- docs/receipt-notes.md",
        "| Path | Owner |\n|---|---|\n| src/app/schema.py | T01 |",
    )
    plan_dir = _build(tmp_path, spine=spine)
    assert any("not parseable as a path list" in m for m in _warns(cpt.check_plan_dir(plan_dir)))


# --- Wave-7 regressions (review round 7) ---------------------------------------------


def test_duplicate_ticket_ids_error(tmp_path: Path) -> None:
    plan_dir = _build(tmp_path)
    (plan_dir / "T01-schema-v2.md").write_text(T01, encoding="utf-8")
    assert any("duplicate ticket ID T01" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


def test_unrecognized_complexity_errors(tmp_path: Path) -> None:
    t1 = T01.replace("Complexity: simple", "Complexity: medium")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    assert any("unrecognized Complexity" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


def test_zero_integration_tickets_error(tmp_path: Path) -> None:
    t99 = T99.replace("Integration: true\n", "")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": T01, "T02-api.md": T02, "T99-integration.md": t99}
    )
    assert any("exactly one" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


def test_directory_touches_count_subtree_bytes(tmp_path: Path) -> None:
    t1 = T01.replace("- src/app/schema.py", "- src/app/")
    spine = SPINE.replace("- src/app/schema.py", "- src/app/")
    plan_dir = _build(
        tmp_path,
        spine=spine,
        tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99},
    )
    big = tmp_path / "src" / "app" / "big.py"
    big.parent.mkdir(parents=True, exist_ok=True)
    big.write_text("x" * (cpt.READ_BUDGET_BYTES + 1), encoding="utf-8")
    assert any("READ budget" in m for m in _errors(cpt.check_plan_dir(plan_dir, context="cli")))


def test_unpaired_backtick_does_not_swallow_sections(tmp_path: Path) -> None:
    # The live fleet regression: an inline/unpaired ``` in prose must not pair
    # with the next block's fence and delete real sections between them.
    t1 = T01.replace(
        "Schema. DO-NOT touch the api.",
        "Schema with ```json fences in prose. DO-NOT touch the api.",
    )
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    errs = _errors(cpt.check_plan_dir(plan_dir))
    # Assert on FENCE-STRIPPED consumers (grounding uses RAW text and could not
    # fail here): the ticket's Touches/Behavior-Contract sections must survive
    # the unpaired backtick, so no scope-containment or roll-up error appears.
    assert not any("outside the spine File Scope" in m for m in errs)
    assert not any("roll-up" in m for m in errs)


def test_spine_never_route_extension(tmp_path: Path) -> None:
    spine = SPINE.replace(
        "## Global Constraints\n\n- None.",
        "## Global Constraints\n\n- Never-Route: src/app/schema.py",
    )
    plan_dir = _build(tmp_path, spine=spine)
    assert any("route it native" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


def test_board_state_header_scan_ignores_data_rows() -> None:
    # A decorated header IS header-aware post-normalization (State resolves to
    # index 5 here); the DATA row titled "State" is excluded by the break live
    # (and by the T##-veto under a break-less mutant — the break's isolation
    # lives in test_board_state_break_isolates_aux_table_after_data_rows).
    spine = SPINE.replace(
        "| Ticket | Title | Depends | Parallel | State | Commit |",
        "| **Ticket** | **Title** | **Depends** | **Parallel** | **State** | **Commit** |",
    ).replace("| T01 | schema |", "| T01 | State |")
    states = cpt._board_states(spine)
    assert states == {"T01": "⬜", "T02": "⬜", "T99": "⬜"}


def test_board_state_header_awareness_reads_reordered_column() -> None:
    # Characterization: a bare header with an extra column BEFORE State must
    # be read via the header index (6), never the fallback (5). Guards against
    # deleting header-awareness wholesale (green before and after pass-10).
    spine = (
        SPINE.replace(
            "| Ticket | Title | Depends | Parallel | State | Commit |",
            "| Ticket | Title | Owner | Depends | Parallel | State | Commit |",
        )
        .replace("| T01 | schema | — |", "| T01 | schema | me | — |")
        .replace("| T02 | api | T01 |", "| T02 | api | me | T01 |")
        .replace("| T99 | integration | T02 |", "| T99 | integration | me | T02 |")
    )
    assert cpt._board_states(spine) == {"T01": "⬜", "T02": "⬜", "T99": "⬜"}


def test_board_state_header_scan_skips_legend_table() -> None:
    # A legend table ABOVE the board must not be mistaken for the header —
    # last-candidate-wins makes the real header authoritative. (The width guard
    # itself is isolated by test_board_state_narrow_legend_below_separator.)
    spine = SPINE.replace(
        "| Ticket | Title | Depends | Parallel | State | Commit |",
        "| State | Meaning |\n|---|---|\n| ⬜ | todo |\n\n"
        "| Ticket | Title | Depends | Parallel | State | Commit |",
    )
    assert cpt._board_states(spine) == {"T01": "⬜", "T02": "⬜", "T99": "⬜"}


def test_board_state_decorated_header_keeps_header_awareness() -> None:
    # Cell normalization: a fully-decorated header with an extra column before
    # State must still be header-aware (State read at index 6, not fallback 5).
    spine = (
        SPINE.replace(
            "| Ticket | Title | Depends | Parallel | State | Commit |",
            "| **Ticket** | **Title** | **Owner** | **Depends** | **Parallel** | **State** | **Commit** |",
        )
        .replace("| T01 | schema | — |", "| T01 | schema | me | — |")
        .replace("| T02 | api | T01 |", "| T02 | api | me | T01 |")
        .replace("| T99 | integration | T02 |", "| T99 | integration | me | T02 |")
    )
    assert cpt._board_states(spine) == {"T01": "⬜", "T02": "⬜", "T99": "⬜"}


def test_board_state_roster_table_does_not_hijack_header_scan() -> None:
    # A `| Ticket | Owner |` roster above the real board has a Ticket cell but
    # no State cell — it must be skipped, not break the scan. (T##-bearing rows
    # inside the Board section are BANNED by the doc: they parse as Board rows.)
    spine = (
        SPINE.replace(
            "| Ticket | Title | Depends | Parallel | State | Commit |",
            "| Ticket | Owner |\n|---|---|\n| all | me |\n\n"
            "| Ticket | Title | Owner | Depends | Parallel | State | Commit |",
        )
        .replace("| T01 | schema | — |", "| T01 | schema | me | — |")
        .replace("| T02 | api | T01 |", "| T02 | api | me | T01 |")
        .replace("| T99 | integration | T02 |", "| T99 | integration | me | T02 |")
    )
    assert cpt._board_states(spine) == {"T01": "⬜", "T02": "⬜", "T99": "⬜"}


def test_board_state_data_row_state_cell_is_normalized() -> None:
    # A bold-wrapped state cell must not disable the ⬜-never-flipped check.
    spine = SPINE.replace("| T01 | schema | — | ⚡ | ⬜ |", "| T01 | schema | — | ⚡ | **⬜** |")
    assert cpt._board_states(spine)["T01"] == "⬜"


def test_governance_files_in_file_scope_error(tmp_path: Path) -> None:
    # Governance files belong in NEITHER Touches nor File Scope (outside the
    # lock by design) — File Scope BUILDS the lock, so a listed surface is an
    # ERROR (never the misleading orphan message).
    spine = SPINE.replace(
        "## File Scope (owned paths)\n",
        "## File Scope (owned paths)\n\n- CHANGELOG.md\n- INDEX.md\n- docs/README.md\n- docs/FEATURES.md\n",
    )
    plan_dir = _build(tmp_path, spine=spine)
    results = cpt.check_plan_dir(plan_dir, context="cli")
    assert not any("owned by no ticket" in m for m in _warns(results))
    # Not silence either: each listed surface draws the DEDICATED error.
    assert sum("governance surface" in m for m in _errors(results)) == 4


def test_integration_ticket_pool_tier_errors(tmp_path: Path) -> None:
    # The Integration ticket owns whole-plan gates/reviews — a pool tier ERRORs.
    t99 = T99.replace("Complexity: native", "Complexity: simple")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": T01, "T02-api.md": T02, "T99-integration.md": t99}
    )
    assert any("receipts run native" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


def test_board_state_renamed_header_keeps_header_awareness() -> None:
    # A renamed first cell (`ID`) must not lose header-awareness: the header is
    # recognized by State + width + no-T##-cell, not by the literal `Ticket`.
    spine = (
        SPINE.replace(
            "| Ticket | Title | Depends | Parallel | State | Commit |",
            "| ID | Title | Owner | Depends | Parallel | State | Commit |",
        )
        .replace("| T01 | schema | — |", "| T01 | schema | me | — |")
        .replace("| T02 | api | T01 |", "| T02 | api | me | T01 |")
        .replace("| T99 | integration | T02 |", "| T99 | integration | me | T02 |")
    )
    assert cpt._board_states(spine) == {"T01": "⬜", "T02": "⬜", "T99": "⬜"}


def test_board_state_data_row_titled_state_never_sets_index() -> None:
    # With an unrecognizable header (bold-outside-backtick double-wrap), a data
    # row whose Title cell is "State" is excluded by the break live (T##-veto
    # would catch it under a break-less mutant) — fallback 5 reads the true
    # state column.
    spine = SPINE.replace(
        "| Ticket | Title | Depends | Parallel | State | Commit |",
        "| **`Ticket`** | **`Title`** | **`Depends`** | **`Parallel`** | **`State`** | **`Commit`** |",
    ).replace("| T01 | schema |", "| T01 | State |")
    assert cpt._board_states(spine) == {"T01": "⬜", "T02": "⬜", "T99": "⬜"}


def test_path_qualified_changelog_is_ownable(tmp_path: Path) -> None:
    # A path-qualified CHANGELOG.md is an ownable file — the governance
    # predicate must NOT hit it (it still draws the normal orphan WARN).
    spine = SPINE.replace(
        "## File Scope (owned paths)\n",
        "## File Scope (owned paths)\n\n- projects/foo/CHANGELOG.md\n",
    )
    plan_dir = _build(tmp_path, spine=spine)
    warns = _warns(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("projects/foo/CHANGELOG.md' is owned by no ticket" in m for m in warns)


def test_board_state_wide_legend_loses_to_real_header() -> None:
    # A WIDE legend (>=4 cells, has State, no T## IDs) above the board must not
    # hijack the index: the LAST candidate header before the first data row wins.
    spine = SPINE.replace(
        "| Ticket | Title | Depends | Parallel | State | Commit |",
        "| State | Glyph | Meaning | Set by |\n|---|---|---|---|\n\n"
        "| Ticket | Title | Depends | Parallel | State | Commit |",
    )
    assert cpt._board_states(spine) == {"T01": "⬜", "T02": "⬜", "T99": "⬜"}


def test_integration_ticket_never_route_tier_does_not_fire_pool_error(tmp_path: Path) -> None:
    # never-route must not fire "receipts run native"; a BOLDED pool-tier label
    # now PARSES (tolerant regex) and correctly fires it — the old
    # bolded-label-means-no-Complexity fail-open is closed.
    t99a = T99.replace("Complexity: native", "Complexity: never-route")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": T01, "T02-api.md": T02, "T99-integration.md": t99a}
    )
    assert not any("receipts run native" in m for m in _errors(cpt.check_plan_dir(plan_dir)))
    t99b = T99.replace("Complexity: native", "**Complexity:** simple")
    plan_dir2 = _build(
        tmp_path, tickets={"T01-schema.md": T01, "T02-api.md": T02, "T99-integration.md": t99b}
    )
    assert any("receipts run native" in m for m in _errors(cpt.check_plan_dir(plan_dir2)))


def test_duplicate_board_row_errors(tmp_path: Path) -> None:
    # A copy-pasted Board row silently masks the real state (last row wins) —
    # the gate must flag it loudly.
    spine = SPINE.replace(
        "| T99 | integration | T02 | ⛓️ | ⬜ | |",
        "| T99 | integration | T02 | ⛓️ | ⬜ | |\n| T01 | schema (dup) | — | ⚡ | ✅ | abc |",
    )
    plan_dir = _build(tmp_path, spine=spine)
    assert any("duplicate Ticket Board row" in m for m in _errors(cpt.check_plan_dir(plan_dir)))


def test_board_state_header_scan_vetoes_id_bearing_wide_line() -> None:
    # The T##-veto in ISOLATION: a wide aux |-line with a State cell and T##
    # tokens placed BELOW the separator (after the real header, before the data
    # rows) is the LAST candidate — only the veto stops it hijacking the index.
    # Red-on-revert against a veto-less scan.
    spine = SPINE.replace(
        "|---|---|---|---|---|---|",
        "|---|---|---|---|---|---|\n| State | T01, T02 | example | note |",
    )
    assert cpt._board_states(spine) == {"T01": "⬜", "T02": "⬜", "T99": "⬜"}


def test_board_state_break_isolates_aux_table_after_data_rows() -> None:
    # The break in isolation: a recognizable wide aux table (State cell, >=4
    # cells, NO T## token) placed AFTER the data rows would be the last
    # candidate without the first-data-row break. Red-on-revert against a
    # break-less scan.
    spine = SPINE.replace(
        "| T99 | integration | T02 | ⛓️ | ⬜ | |",
        "| T99 | integration | T02 | ⛓️ | ⬜ | |\n\n| State | Glyph | Meaning | Note |\n|---|---|---|---|",
    )
    assert cpt._board_states(spine) == {"T01": "⬜", "T02": "⬜", "T99": "⬜"}


def test_board_state_three_column_board_stays_parseable() -> None:
    # Removed-behavior guard: a minimal 3-column board parsed at HEAD and must
    # keep parsing (width guard is >=3, not >=4) — else the staleness check
    # silently dies on narrow boards.
    spine = SPINE.replace(
        "| Ticket | Title | Depends | Parallel | State | Commit |",
        "| Ticket | State | Commit |",
    ).replace("|---|---|---|---|---|---|", "|---|---|---|")
    spine = (
        spine.replace("| T01 | schema | — | ⚡ | ⬜ | |", "| T01 | ⬜ | |")
        .replace("| T02 | api | T01 | ⛓️ | ⬜ | |", "| T02 | ⬜ | |")
        .replace("| T99 | integration | T02 | ⛓️ | ⬜ | |", "| T99 | ⬜ | |")
    )
    assert cpt._board_states(spine) == {"T01": "⬜", "T02": "⬜", "T99": "⬜"}


def test_board_state_narrow_legend_below_separator_rejected() -> None:
    # The width guard in ISOLATION: a 2-cell `| State | Meaning |` legend below
    # the separator is the LAST candidate — only the width guard stops it
    # setting state_idx=1. Red-on-revert against a width-guard-less scan.
    spine = SPINE.replace(
        "|---|---|---|---|---|---|",
        "|---|---|---|---|---|---|\n| State | Meaning |",
    )
    assert cpt._board_states(spine) == {"T01": "⬜", "T02": "⬜", "T99": "⬜"}


def test_board_state_lowercase_state_header_is_recognized() -> None:
    # The State cell match is case-insensitive: a `state` header cell with an
    # extra column before it must still be header-aware (index 6).
    spine = (
        SPINE.replace(
            "| Ticket | Title | Depends | Parallel | State | Commit |",
            "| Ticket | Title | Owner | Depends | Parallel | state | Commit |",
        )
        .replace("| T01 | schema | — |", "| T01 | schema | me | — |")
        .replace("| T02 | api | T01 |", "| T02 | api | me | T01 |")
        .replace("| T99 | integration | T02 |", "| T99 | integration | me | T02 |")
    )
    assert cpt._board_states(spine) == {"T01": "⬜", "T02": "⬜", "T99": "⬜"}


def test_cli_plan_dir_validation_messages(tmp_path: Path) -> None:
    # The four --plan-dir rejection branches each name their real cause.
    root = Path(__file__).resolve().parents[2]
    import sys as _sys

    cmd = [_sys.executable, "-m", "scripts.enforcement.check_plan_tickets", "--plan-dir"]
    r1 = subprocess.run(
        cmd + ["docs/development/plans/2026-01-01-plan-9-nope"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert r1.returncode == 1 and "does not exist" in r1.stdout
    bad = tmp_path / "docs" / "development" / "plans" / "not-a-plan-name"
    bad.mkdir(parents=True)
    r2 = subprocess.run(cmd + [str(bad)], cwd=root, capture_output=True, text=True)
    assert r2.returncode == 1 and "not a dated plan directory" in r2.stdout
    outside = tmp_path / "elsewhere" / "2026-01-01-plan-9-x"
    outside.mkdir(parents=True)
    r3 = subprocess.run(cmd + [str(outside)], cwd=root, capture_output=True, text=True)
    assert r3.returncode == 1 and "not under docs/development/plans/" in r3.stdout
    monolith = tmp_path / "2026-01-01-plan-9-mono.md"
    monolith.write_text("# plan\n", encoding="utf-8")
    r4 = subprocess.run(cmd + [str(monolith)], cwd=root, capture_output=True, text=True)
    assert r4.returncode == 1 and "is a FILE" in r4.stdout


def test_board_state_three_cell_aux_below_separator_hijacks() -> None:
    # CHARACTERIZATION of the accepted cost of the >=3 width guard (which keeps
    # 3-column boards parseable): a 3-content-cell T##-free aux line with a
    # State cell, below the separator, IS a recognizable last candidate and
    # hijacks the index. The doc bans aux tables in the Board section for
    # exactly this reason. If this test ever fails, the width boundary moved —
    # update the doc's ">=3 content cells" claim in the same change.
    spine = SPINE.replace(
        "|---|---|---|---|---|---|",
        "|---|---|---|---|---|---|\n| State | Glyph | Meaning |",
    )
    states = cpt._board_states(spine)
    assert states["T01"] != "⬜"  # hijacked — reads the ID column


def test_board_state_two_column_board_is_not_recognized() -> None:
    # CHARACTERIZATION of the accepted cost of the >=3 width guard: a 2-column
    # board is below the recognition floor AND below fallback reach — states
    # read empty, the staleness check is off. Documented ("keep the canonical
    # six"); if this test fails, the width boundary moved — update the doc.
    spine = SPINE.replace(
        "| Ticket | Title | Depends | Parallel | State | Commit |",
        "| Ticket | State |",
    ).replace("|---|---|---|---|---|---|", "|---|---|")
    spine = (
        spine.replace("| T01 | schema | — | ⚡ | ⬜ | |", "| T01 | ⬜ |")
        .replace("| T02 | api | T01 | ⛓️ | ⬜ | |", "| T02 | ⬜ |")
        .replace("| T99 | integration | T02 | ⛓️ | ⬜ | |", "| T99 | ⬜ |")
    )
    assert cpt._board_states(spine) == {"T01": "", "T02": "", "T99": ""}


def test_board_state_five_cell_aux_below_separator_hijacks_plausibly() -> None:
    # CHARACTERIZATION (companion to the 3-cell case): a WIDE T##-free aux line
    # below the separator hijacks via pure last-candidate-wins — and the nastier
    # symptom is a plausible-looking non-⬜ value (the Depends column), not an
    # obvious ticket ID. Doc-banned; if this fails, the recognition rule moved.
    spine = SPINE.replace(
        "|---|---|---|---|---|---|",
        "|---|---|---|---|---|---|\n| State | Glyph | Meaning | Set by | Note |",
    )
    states = cpt._board_states(spine)
    assert states["T01"] != "⬜"  # hijacked


def test_lessons_learnt_is_governance_class(tmp_path: Path) -> None:
    # docs/LESSONS_LEARNT.md is the fifth shared-append surface: banned from
    # Touches like the other governance files; a File Scope listing draws the
    # dedicated ERROR, never the orphan message.
    t1 = T01.replace("- src/app/schema.py", "- src/app/schema.py\n- docs/LESSONS_LEARNT.md")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    assert any(
        "governance file" in m and "LESSONS_LEARNT" in m
        for m in _errors(cpt.check_plan_dir(plan_dir))
    )
    spine = SPINE.replace(
        "## File Scope (owned paths)\n",
        "## File Scope (owned paths)\n\n- docs/LESSONS_LEARNT.md\n",
    )
    plan_dir2 = _build(tmp_path / "b", spine=spine)
    results2 = cpt.check_plan_dir(plan_dir2, context="cli")
    assert not any("owned by no ticket" in m for m in _warns(results2))
    assert any("governance surface" in m and "LESSONS_LEARNT" in m for m in _errors(results2))


def test_legacy_lessons_alias_is_governance_class(tmp_path: Path) -> None:
    # The legacy-tolerated lowercase name is the SAME surface — the ban must
    # not be bypassable by the alias.
    t1 = T01.replace("- src/app/schema.py", "- src/app/schema.py\n- docs/lessons-learnt.md")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    assert any(
        "governance file 'docs/lessons-learnt.md'" in m
        for m in _errors(cpt.check_plan_dir(plan_dir))
    )


def test_docs_dir_in_file_scope_draws_governance_error(tmp_path: Path) -> None:
    # Dir-aware: a `docs/` File Scope entry covers three governance surfaces —
    # the dedicated ERROR must fire (the lock would own them all).
    spine = SPINE.replace(
        "## File Scope (owned paths)\n",
        "## File Scope (owned paths)\n\n- docs/\n",
    )
    plan_dir = _build(tmp_path, spine=spine)
    errors = _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("governance surface" in m and "'docs/'" in m for m in errors)


def test_governance_touches_reports_exactly_one_finding(tmp_path: Path) -> None:
    # The containment ERROR is suppressed for governance-banned paths — one
    # cause, one finding (the ban), even when File Scope doesn't cover it.
    t1 = T01.replace("- src/app/schema.py", "- src/app/schema.py\n- docs/LESSONS_LEARNT.md")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    findings = [m for m in _errors(cpt.check_plan_dir(plan_dir)) if "LESSONS_LEARNT" in m]
    assert len(findings) == 1 and "governance file" in findings[0]


def test_glob_in_touches_and_file_scope_errors(tmp_path: Path) -> None:
    # Opaque tokens disable ownership/never-route/governance predicates — both
    # surfaces ERROR (a WARN would let a secrets path ride to the pool).
    # Edge stars survive too (_norm_path strips symmetric emphasis wraps only).
    t1 = T01.replace("- src/app/schema.py", "- src/app/schema.py\n- src/legacy/*.py")
    spine = SPINE.replace(
        "## File Scope (owned paths)\n",
        "## File Scope (owned paths)\n\n- tools/gen-?.py\n",
    )
    plan_dir = _build(
        tmp_path,
        spine=spine,
        tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99},
    )
    errors = _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("glob 'src/legacy/*.py' in Touches" in m for m in errors)
    assert any("glob 'tools/gen-?.py' in File Scope" in m for m in errors)


def test_edge_glob_survives_normalization_and_errors(tmp_path: Path) -> None:
    # `CHANGELOG.*` must not degenerate to the prefix `CHANGELOG.` (which would
    # evade the governance ban AND let the lock prefix-match the real file) —
    # it survives normalization and draws the glob ERROR.
    t1 = T01.replace("- src/app/schema.py", "- src/app/schema.py\n- CHANGELOG.*")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    errors = _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("glob 'CHANGELOG.*' in Touches" in m for m in errors)


def test_dynamic_route_brackets_are_not_globs(tmp_path: Path) -> None:
    # Next.js/Expo dynamic-route dirs are LITERAL names — no glob WARN.
    t1 = T01.replace("- src/app/schema.py", "- app/(app)/items/[id]/page.tsx")
    spine = SPINE.replace("- src/app/schema.py", "- app/(app)/items/[id]/page.tsx")
    plan_dir = _build(
        tmp_path,
        spine=spine,
        tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99},
    )
    results = cpt.check_plan_dir(plan_dir, context="cli")
    assert not any("glob" in m for m in _warns(results) + _errors(results))


def test_asymmetric_bold_secrets_path_fails_closed(tmp_path: Path) -> None:
    # THE pass-25 fail-open: an unclosed `**secrets/x` token must ERROR (glob
    # check on the surviving `*`s), never ride to the pool on a WARN.
    t1 = T01.replace("- src/app/schema.py", "- **secrets/keys.json")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    errors = _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("glob '**secrets/keys.json' in Touches" in m for m in errors)


def test_never_route_glob_entries(tmp_path: Path) -> None:
    # An EDGE-star glob degenerates to the dir prefix (fail-closed: coverage
    # extends); an INTERIOR glob stays inert and must draw the WARN.
    spine = SPINE.replace(
        "## Global Constraints\n\n- None.",
        "## Global Constraints\n\n- Never-Route: src/app/*",
    )
    plan_dir = _build(tmp_path, spine=spine)
    results = cpt.check_plan_dir(plan_dir, context="cli")
    assert any("route it native" in m for m in _errors(results))  # src/app/ coverage
    spine2 = SPINE.replace(
        "## Global Constraints\n\n- None.",
        "## Global Constraints\n\n- Never-Route: vendor/*.py",
    )
    plan_dir2 = _build(tmp_path / "b", spine=spine2)
    warns = _warns(cpt.check_plan_dir(plan_dir2, context="cli"))
    assert any("Never-Route entry 'vendor/*.py' contains an interior glob" in m for m in warns)


def test_context_files_glob_warns_budget_opacity(tmp_path: Path) -> None:
    # A glob in Context Files counts 0 bytes — the budget under-counts silently
    # without this WARN.
    t1 = T01.replace("## Context Files", "## Context Files\n\n- src/**/*.py")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    warns = _warns(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("glob 'src/**/*.py' in Context Files" in m for m in warns)


def test_recursive_glob_normalizes_to_absolute_and_errors(tmp_path: Path) -> None:
    # `**/secrets/**` is SYMMETRIC to the emphasis-strip and collapses to the
    # absolute `/secrets/` — the absolute-path ERROR must catch it (fail-closed;
    # it would otherwise evade both the glob check and never-route, and the
    # sizing walker would escape the repo root).
    t1 = T01.replace("- src/app/schema.py", "- **/secrets/**")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    errors = _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("out-of-repo path '/secrets/' in Touches" in m for m in errors)


def test_absolute_path_in_file_scope_errors(tmp_path: Path) -> None:
    # BC 32's File Scope half: an absolute scope entry is an ERROR.
    spine = SPINE.replace(
        "## File Scope (owned paths)\n",
        "## File Scope (owned paths)\n\n- /opt/fabrik/scripts/x.py\n",
    )
    plan_dir = _build(tmp_path, spine=spine)
    errors = _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("out-of-repo path '/opt/fabrik/scripts/x.py' in File Scope" in m for m in errors)


def test_dotdot_touches_errors(tmp_path: Path) -> None:
    # `..` traversal is the same out-of-repo class — ERROR (and the sizing
    # walker skips it, never climbing out of the repo root).
    t1 = T01.replace("- src/app/schema.py", "- ../../../etc/")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    errors = _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("out-of-repo path '../../../etc/' in Touches" in m for m in errors)


def test_sibling_plan_lock_dir_in_touches_errors(tmp_path: Path) -> None:
    # Metadata prefixes are per-plan territory: a ticket owning the whole lock
    # dir (every sibling's lock) draws the dedicated foreign-stem ERROR — and
    # exactly one finding (containment is suppressed for the same cause).
    t1 = T01.replace("- src/app/schema.py", "- src/app/schema.py\n- .fabrik/plan-locks/")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    findings = [
        m for m in _errors(cpt.check_plan_dir(plan_dir, context="cli")) if "plan-locks" in m
    ]
    assert len(findings) == 1 and "outside this plan's stem" in findings[0]


def test_foreign_stem_metadata_touches_errors(tmp_path: Path) -> None:
    # Metadata prefixes are per-plan territory: another plan's review or the
    # bare lock dir in Touches is an ERROR even when File Scope lists it.
    t1 = T01.replace(
        "- src/app/schema.py",
        "- src/app/schema.py\n- docs/development/reviews/2026-01-01-plan-9-other-review.md",
    )
    spine = SPINE.replace(
        "## File Scope (owned paths)\n",
        "## File Scope (owned paths)\n\n- docs/development/reviews/\n",
    )
    plan_dir = _build(
        tmp_path,
        spine=spine,
        tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99},
    )
    errors = _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("outside this plan's stem" in m for m in errors)


def test_own_stem_receipt_touches_pass(tmp_path: Path) -> None:
    # The plan's OWN receipt (stem-bounded via DIRNAME) needs no File Scope
    # coverage and draws no finding.
    t1 = T01.replace(
        "- src/app/schema.py",
        "- src/app/schema.py\n- docs/development/reviews/" + DIRNAME + "-review.md",
    )
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    results = cpt.check_plan_dir(plan_dir, context="cli")
    assert not any("review.md" in m for m in _errors(results) + _warns(results))


def test_sibling_stem_extension_lock_in_touches_errors(tmp_path: Path) -> None:
    # A sibling lock whose name EXTENDS this stem (`<stem>-v2.json`) must not
    # ride the stem exemption — only `<stem>.json` and `<stem>…-review….md`
    # shapes are the plan's own artifacts.
    t1 = T01.replace(
        "- src/app/schema.py",
        "- src/app/schema.py\n- .fabrik/plan-locks/" + DIRNAME + "-v2.json",
    )
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    errors = _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("outside this plan's stem" in m for m in errors)


def test_integration_real_receipt_touches_pass_end_to_end(tmp_path: Path) -> None:
    # The canonical Integration receipt (this plan's review doc, stem-named)
    # passes every ownership check with zero findings about it.
    t99 = T99.replace(
        "- docs/receipt-notes.md",
        "- docs/development/reviews/" + DIRNAME + "-review.md",
    )
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": T01, "T02-api.md": T02, "T99-integration.md": t99}
    )
    results = cpt.check_plan_dir(plan_dir, context="cli")
    assert not any("review.md" in m for m in _errors(results) + _warns(results))


def test_repo_root_token_errors_both_surfaces(tmp_path: Path) -> None:
    # `- .` claims the whole repo while covering NOTHING in the ownership
    # predicates (a pool ticket could ride it past never-route) — ERROR on
    # both surfaces.
    t1 = T01.replace("- src/app/schema.py", "- src/app/schema.py\n- .")
    spine = SPINE.replace("## File Scope (owned paths)\n", "## File Scope (owned paths)\n\n- .\n")
    plan_dir = _build(
        tmp_path,
        spine=spine,
        tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99},
    )
    errors = _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("repo-root token '.' in Touches" in m for m in errors)
    assert any("repo-root token" in m and "File Scope" in m for m in errors)


def test_slashless_and_ancestor_metadata_touches_error(tmp_path: Path) -> None:
    # The metadata ownership ERROR is bidirectional: a slash-less
    # `.fabrik/plan-locks` and an ancestor `docs/development/` must both hit.
    t1 = T01.replace("- src/app/schema.py", "- src/app/schema.py\n- .fabrik/plan-locks")
    t2 = T02.replace("- src/app/api.py", "- src/app/api.py\n- docs/development/")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": t2, "T99-integration.md": T99}
    )
    errors = _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("metadata path '.fabrik/plan-locks' outside this plan's stem" in m for m in errors)
    # The ancestor covers the plan-set territory too — the dedicated
    # plan-set ERROR fires (it precedes the generic metadata check).
    assert any("plan-set territory 'docs/development/'" in m for m in errors)


def test_own_lock_in_file_scope_is_orphan_exempt(tmp_path: Path) -> None:
    # The plan's OWN lock (`<stem>.json`, _stem_scoped arm 2) listed in File
    # Scope draws no orphan WARN and no other finding — the exemption is live.
    spine = SPINE.replace(
        "## File Scope (owned paths)\n",
        "## File Scope (owned paths)\n\n- .fabrik/plan-locks/" + DIRNAME + ".json\n",
    )
    plan_dir = _build(tmp_path, spine=spine)
    results = cpt.check_plan_dir(plan_dir, context="cli")
    assert not any("plan-locks" in m for m in _errors(results) + _warns(results))


def test_reviews_subdir_receipt_passes(tmp_path: Path) -> None:
    # _stem_scoped arm 1: a receipt under `reviews/<stem>/` (the stem as a DIR
    # segment) is the plan's own artifact — no findings.
    t99 = T99.replace(
        "- docs/receipt-notes.md",
        "- docs/development/reviews/" + DIRNAME + "/T01-review.md",
    )
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": T01, "T02-api.md": T02, "T99-integration.md": t99}
    )
    results = cpt.check_plan_dir(plan_dir, context="cli")
    assert not any("T01-review" in m for m in _errors(results) + _warns(results))


def test_bolded_complexity_label_routing_stays_live(tmp_path: Path) -> None:
    # THE pass-31 fail-open: `**Complexity:** simple` + secrets Touches must
    # still fire the never-route routing ERROR (tolerant label regex).
    t1 = T01.replace("Complexity: simple", "**Complexity:** simple").replace(
        "- src/app/schema.py", "- secrets/keys.json"
    )
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    errors = _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("route it native" in m for m in errors)


def test_missing_complexity_line_errors_at_emit_gate(tmp_path: Path) -> None:
    # No parseable Complexity at all -> the routing check is OFF; the gate must
    # say so instead of staying silent.
    t1 = T01.replace("Complexity: simple\n", "")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    # ERROR at the emit gate (fail-closed floor for the routing layer);
    # advisory on the shared gate path.
    assert any(
        "no parseable Complexity" in m for m in _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    )
    assert any(
        "no parseable Complexity" in m for m in _warns(cpt.check_plan_dir(plan_dir, context="gate"))
    )


def test_docs_dev_plans_dir_is_metadata_territory(tmp_path: Path) -> None:
    # docs/development/plans/ holds every sibling plan set — owning it (either
    # surface) is an ERROR.
    t1 = T01.replace("- src/app/schema.py", "- src/app/schema.py\n- docs/development/plans/")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    errors = _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("plan-set territory 'docs/development/plans/'" in m for m in errors)


def test_metadata_territory_in_file_scope_errors(tmp_path: Path) -> None:
    # The FS surface gets the same ownership hardening: docs/development/ in
    # File Scope would put every sibling plan into the lock.
    spine = SPINE.replace(
        "## File Scope (owned paths)\n",
        "## File Scope (owned paths)\n\n- docs/development/\n",
    )
    plan_dir = _build(tmp_path, spine=spine)
    errors = _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("metadata territory 'docs/development/' in File Scope" in m for m in errors)


def test_own_lock_in_touches_errors(tmp_path: Path) -> None:
    # Even the plan's OWN lock is orchestrator territory — never a write set.
    t1 = T01.replace(
        "- src/app/schema.py",
        "- src/app/schema.py\n- .fabrik/plan-locks/" + DIRNAME + ".json",
    )
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    errors = _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("orchestrator-owned, never a ticket's write set" in m for m in errors)


def test_integration_missing_complexity_also_flagged(tmp_path: Path) -> None:
    # BC 33 has no Integration carve-out: the receipts ticket's tier is
    # enforced like every other ticket's.
    t99 = T99.replace("Complexity: native\n", "")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": T01, "T02-api.md": T02, "T99-integration.md": t99}
    )
    errors = _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("T99: no parseable Complexity" in m for m in errors)


def test_bolded_never_route_line_still_extends(tmp_path: Path) -> None:
    # A `**Never-Route:**` label must not silently disable the spine's
    # never-route extension (same fail-open class as the Complexity label).
    spine = SPINE.replace(
        "## Global Constraints\n\n- None.",
        "## Global Constraints\n\n- **Never-Route:** src/app/schema.py",
    )
    plan_dir = _build(tmp_path, spine=spine)
    assert any("route it native" in m for m in _errors(cpt.check_plan_dir(plan_dir)))
    # The VALUE half of the same class: a bolded path must normalize clean,
    # not survive as a phantom glob (the pass-34 regression).
    spine2 = SPINE.replace(
        "## Global Constraints\n\n- None.",
        "## Global Constraints\n\n- Never-Route: **src/app/schema.py**",
    )
    plan_dir2 = _build(tmp_path / "b", spine=spine2)
    assert any("route it native" in m for m in _errors(cpt.check_plan_dir(plan_dir2)))


def test_never_route_multi_token_lines_drop_with_warn(tmp_path: Path) -> None:
    # A comma list and a prose sentence are both multi-token lines: the ENTIRE
    # line is dropped with the truthful WARN — including the FIRST token (use
    # non-built-in prefixes so the routing outcome discriminates).
    spine = SPINE.replace(
        "## Global Constraints\n\n- None.",
        "## Global Constraints\n\n- Never-Route: vendor/, third_party/\n"
        "- **Never-Route:** lines are optional here",
    )
    t1 = T01.replace("- src/app/schema.py", "- vendor/lib.py")
    plan_dir = _build(
        tmp_path,
        spine=spine.replace("- src/app/schema.py", "- vendor/lib.py"),
        tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99},
    )
    results = cpt.check_plan_dir(plan_dir, context="cli")
    warns = _warns(results)
    assert sum("is not a single token" in m for m in warns) == 2
    # The message is truthful: vendor/ is NOT enforced (whole line dropped).
    assert not any("route it native" in m for m in _errors(results))
    # Out-of-repo + empty tokens draw their own WARNs.
    spine3 = SPINE.replace(
        "## Global Constraints\n\n- None.",
        "## Global Constraints\n\n- Never-Route: **/secrets2/**\n- Never-Route: **",
    )
    plan_dir3 = _build(tmp_path / "c", spine=spine3)
    warns3 = _warns(cpt.check_plan_dir(plan_dir3, context="cli"))
    assert any("out-of-repo Never-Route token '/secrets2/'" in m for m in warns3)
    assert any("no path after the label" in m for m in warns3)


def test_never_route_punctuation_and_bare_label(tmp_path: Path) -> None:
    # Sentence punctuation is stripped (the prefix still works); a bare label
    # and a repo-root token each draw the void WARN — never silence.
    spine = SPINE.replace(
        "## Global Constraints\n\n- None.",
        "## Global Constraints\n\n- Never-Route: vendor/.\n- Never-Route:\n- Never-Route: .",
    )
    t1 = T01.replace("- src/app/schema.py", "- vendor/lib.py")
    plan_dir = _build(
        tmp_path,
        spine=spine.replace("- src/app/schema.py", "- vendor/lib.py"),
        tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99},
    )
    results = cpt.check_plan_dir(plan_dir, context="cli")
    assert any("route it native" in m for m in _errors(results))  # vendor/ enforced
    voids = [m for m in _warns(results) if "void" in m]
    assert len(voids) == 2  # bare label + repo-root token


def test_norm_path_fixpoint_closes_pass37_matrix(tmp_path: Path) -> None:
    # The four pass-37 fail-opens, end-to-end: code-span+period NR still
    # enforces; wrapped out-of-repo tokens WARN; route-group literals survive;
    # a trailing sentence period cannot evade the governance ERROR.
    spine = SPINE.replace(
        "## Global Constraints\n\n- None.",
        '## Global Constraints\n\n- Never-Route: `vendor/`.\n- Never-Route: "../vendor"',
    )
    t1 = T01.replace("- src/app/schema.py", "- vendor/lib.py")
    plan_dir = _build(
        tmp_path,
        spine=spine.replace("- src/app/schema.py", "- vendor/lib.py"),
        tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99},
    )
    results = cpt.check_plan_dir(plan_dir, context="cli")
    assert any("route it native" in m for m in _errors(results))  # `vendor/`. enforced
    assert any("out-of-repo Never-Route token '../vendor'" in m for m in _warns(results))
    # Route-group literal survives normalization (unbalanced edge paren).
    assert cpt._norm_path("app/(marketing)") == "app/(marketing)"
    # Governance ERROR is period-proof.
    t1b = T01.replace("- src/app/schema.py", "- src/app/schema.py\n- CHANGELOG.md.")
    plan_dir2 = _build(
        tmp_path / "b", tickets={"T01-schema.md": t1b, "T02-api.md": T02, "T99-integration.md": T99}
    )
    assert any(
        "governance file 'CHANGELOG.md'" in m
        for m in _errors(cpt.check_plan_dir(plan_dir2, context="cli"))
    )


def test_residue_tokens_fail_closed_everywhere(tmp_path: Path) -> None:
    # Comma lists, ellipses and quote residue must be LOUD, never silent:
    # (1) a comma-list Touches bullet ERRORs (nothing silently dropped);
    # (2) an ellipsis cannot evade the governance ban;
    # (3) a mismatched quote is residue, not a strip candidate;
    # (4) a bare route-group token stays literal.
    t1 = T01.replace("- src/app/schema.py", "- src/app/schema.py, secrets/keys.json")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    errors = _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("unparseable token 'src/app/schema.py," in m for m in errors)
    t1b = T01.replace("- src/app/schema.py", "- src/app/schema.py\n- CHANGELOG.md...")
    plan_dir2 = _build(
        tmp_path / "b", tickets={"T01-schema.md": t1b, "T02-api.md": T02, "T99-integration.md": T99}
    )
    errors2 = _errors(cpt.check_plan_dir(plan_dir2, context="cli"))
    assert any("governance file 'CHANGELOG.md'" in m for m in errors2)
    assert cpt._norm_path("\"x'") == "\"x'"  # mismatched quotes never strip
    assert cpt._norm_path("(marketing)") == "(marketing)"  # route group literal
    assert cpt._norm_path("vendor/.") == "vendor/"  # POSIX self-reference


def test_residue_arms_on_file_scope_and_never_route(tmp_path: Path) -> None:
    # The other two residue arms: File Scope residue ERRORs; a backtick-residue
    # Never-Route token WARNs; and a path:NN citation collapses to the path so
    # never-route/governance stay closed.
    spine = SPINE.replace(
        "## File Scope (owned paths)\n",
        "## File Scope (owned paths)\n\n- src/extra.py, src/other.py\n",
    ).replace(
        "## Global Constraints\n\n- None.",
        "## Global Constraints\n\n- Never-Route: `a`b",
    )
    plan_dir = _build(tmp_path, spine=spine)
    results = cpt.check_plan_dir(plan_dir, context="cli")
    assert any(
        "unparseable token 'src/extra.py," in m and "File Scope" in m for m in _errors(results)
    )
    assert any("unparseable Never-Route token" in m for m in _warns(results))
    # path:NN collapses — the never-route ERROR fires on the underlying file.
    t1 = T01.replace("- src/app/schema.py", "- scripts/final_gate.py:20")
    plan_dir2 = _build(
        tmp_path / "b", tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    errors2 = _errors(cpt.check_plan_dir(plan_dir2, context="cli"))
    assert any("never-route path 'scripts/final_gate.py'" in m for m in errors2)


def test_merge_order_duplicate_entry_errors(tmp_path: Path) -> None:
    # A duplicated Merge Order entry must ERROR — last-wins positions would
    # silently defeat the topological and Integration-last checks (BC 28 class).
    spine = SPINE.replace("1. T01\n2. T02\n3. T99", "1. T02\n2. T01\n3. T02\n4. T99")
    plan_dir = _build(tmp_path, spine=spine)
    errors = _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("duplicate Merge Order entry" in m and "T02" in m for m in errors)


def test_context_files_residue_warns_budget_opacity(tmp_path: Path) -> None:
    # A comma-listed Context Files bullet counts 0 bytes — the third
    # zero-byte class gets the same WARN as globs and out-of-repo tokens.
    t1 = T01.replace("## Context Files", "## Context Files\n\n- docs/big-a.md, docs/big-b.md")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    warns = _warns(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("unparseable token 'docs/big-a.md," in m and "Context Files" in m for m in warns)


def test_serialized_residue_row_warns_void(tmp_path: Path) -> None:
    # A residue-bearing Serialized path voids the row: the WARN names the
    # cause AND the real overlap ERROR still stands (no licence granted).
    t1 = T01.replace("- src/app/schema.py", "- src/shared.py")
    t2 = T02.replace("- src/app/api.py", "- src/shared.py").replace("Depends: T01", "Depends: none")
    spine = SPINE.replace(
        "## Merge Order", "## Merge Order\n\nSerialized: src/shared.py, — T01 T02"
    ).replace("- src/app/schema.py", "- src/shared.py")
    plan_dir = _build(
        tmp_path,
        spine=spine,
        tickets={"T01-schema.md": t1, "T02-api.md": t2, "T99-integration.md": T99},
    )
    results = cpt.check_plan_dir(plan_dir, context="cli")
    assert any("Serialized row path 'src/shared.py,'" in m and "VOID" in m for m in _warns(results))
    assert any("Touches overlap between T01 and T02" in m for m in _errors(results))


def test_serialized_licence_is_pair_scoped_and_covering(tmp_path: Path) -> None:
    # (1) Two rows with DISJOINT pairs never license a cross pair; (2) a
    # dir-level row covers file-level overlaps; (3) slash-insensitive.
    base_t1 = T01.replace("- src/app/schema.py", "- src/shared/a.py")
    base_t2 = T02.replace("- src/app/api.py", "- src/shared/a.py").replace(
        "Depends: T01", "Depends: none"
    )
    # Disjoint rows: T01+T99 and T02+T99 — the T01/T02 pair stays unlicensed.
    spine = SPINE.replace(
        "## Merge Order",
        "## Merge Order\n\nSerialized: src/shared/a.py — T01 T99\n"
        "Serialized: src/shared/a.py — T02 T99",
    ).replace("- src/app/schema.py", "- src/shared/a.py")
    plan_dir = _build(
        tmp_path,
        spine=spine,
        tickets={"T01-schema.md": base_t1, "T02-api.md": base_t2, "T99-integration.md": T99},
    )
    errors = _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("Touches overlap between T01 and T02" in m for m in errors)
    # One row naming the pair, at DIR level with a trailing slash, licenses it.
    spine2 = SPINE.replace(
        "## Merge Order",
        "## Merge Order\n\nSerialized: src/shared/ — T01, T02",
    ).replace("- src/app/schema.py", "- src/shared/a.py")
    plan_dir2 = _build(
        tmp_path / "b",
        spine=spine2,
        tickets={"T01-schema.md": base_t1, "T02-api.md": base_t2, "T99-integration.md": T99},
    )
    errors2 = _errors(cpt.check_plan_dir(plan_dir2, context="cli"))
    assert not any("Touches overlap between T01 and T02" in m for m in errors2)


def test_context_files_out_of_repo_warns(tmp_path: Path) -> None:
    # The middle arm of the Context-Files chain: an absolute read counts 0
    # bytes and must say so.
    t1 = T01.replace("## Context Files", "## Context Files\n\n- /opt/fabrik/agents-fabrik.md")
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": T02, "T99-integration.md": T99}
    )
    warns = _warns(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any(
        "out-of-repo path '/opt/fabrik/agents-fabrik.md' in Context Files" in m for m in warns
    )


def test_bolded_depends_label_keeps_graph_edge(tmp_path: Path) -> None:
    # `**Depends:** T01` must parse — proven on a SHARED path where the edge is
    # the only thing suppressing the overlap ERROR, plus a positive parse assert.
    t2 = T02.replace("Depends: T01", "**Depends:** T01").replace(
        "- src/app/api.py", "- src/app/schema.py"
    )
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": T01, "T02-api.md": t2, "T99-integration.md": T99}
    )
    results = cpt.check_plan_dir(plan_dir, context="cli")
    assert not any("Touches overlap" in m for m in _errors(results))
    parsed = cpt._parse_ticket(plan_dir / "T02-api.md")
    assert parsed.depends == ["T01"]


def test_bolded_serialized_label_still_licenses(tmp_path: Path) -> None:
    # `**Serialized:**` must parse like the rest of the field family — a
    # silently-voided licence row demands the row the author already wrote.
    t1 = T01.replace("- src/app/schema.py", "- src/shared.py")
    t2 = T02.replace("- src/app/api.py", "- src/shared.py").replace("Depends: T01", "Depends: none")
    spine = SPINE.replace(
        "## Merge Order", "## Merge Order\n\n**Serialized:** src/shared.py — T01, T02"
    ).replace("- src/app/schema.py", "- src/shared.py")
    plan_dir = _build(
        tmp_path,
        spine=spine,
        tickets={"T01-schema.md": t1, "T02-api.md": t2, "T99-integration.md": T99},
    )
    assert not any(
        "Touches overlap between T01 and T02" in m
        for m in _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    )


def test_serialized_file_row_does_not_license_dir_overlap(tmp_path: Path) -> None:
    # DIRECTIONAL licence: a row keyed on ONE file must not disable the
    # collision guard for a whole-dir Touches overlap on OTHER files.
    t1 = T01.replace("- src/app/schema.py", "- src/app/")
    t2 = T02.replace("- src/app/api.py", "- src/app/api.py").replace(
        "Depends: T01", "Depends: none"
    )
    spine = SPINE.replace(
        "## Merge Order", "## Merge Order\n\nSerialized: src/app/schema.py — T01, T02"
    ).replace("- src/app/schema.py", "- src/app/")
    plan_dir = _build(
        tmp_path,
        spine=spine,
        tickets={"T01-schema.md": t1, "T02-api.md": t2, "T99-integration.md": T99},
    )
    assert any(
        "Touches overlap between T01 and T02" in m
        for m in _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    )


def test_bulleted_serialized_row_still_licenses(tmp_path: Path) -> None:
    # A `- Serialized: …` bullet parses like the rest of the field family —
    # the old silent void demanded the row the author already wrote.
    t1 = T01.replace("- src/app/schema.py", "- src/shared.py")
    t2 = T02.replace("- src/app/api.py", "- src/shared.py").replace("Depends: T01", "Depends: none")
    spine = SPINE.replace(
        "## Merge Order", "## Merge Order\n\n- Serialized: src/shared.py — T01, T02"
    ).replace("- src/app/schema.py", "- src/shared.py")
    plan_dir = _build(
        tmp_path,
        spine=spine,
        tickets={"T01-schema.md": t1, "T02-api.md": t2, "T99-integration.md": T99},
    )
    assert not any(
        "Touches overlap between T01 and T02" in m
        for m in _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    )


def test_numbered_serialized_row_licenses_blockquote_stays_void(tmp_path: Path) -> None:
    # A numbered `3. Serialized: ...` row parses (the natural Merge Order form);
    # a blockquoted example row deliberately does NOT (its parse would disable
    # the collision guard).
    t1 = T01.replace("- src/app/schema.py", "- src/shared.py")
    t2 = T02.replace("- src/app/api.py", "- src/shared.py").replace("Depends: T01", "Depends: none")
    spine = SPINE.replace(
        "## Merge Order", "## Merge Order\n\n4. Serialized: src/shared.py — T01, T02"
    ).replace("- src/app/schema.py", "- src/shared.py")
    plan_dir = _build(
        tmp_path,
        spine=spine,
        tickets={"T01-schema.md": t1, "T02-api.md": t2, "T99-integration.md": T99},
    )
    assert not any(
        "Touches overlap between T01 and T02" in m
        for m in _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    )
    spine2 = SPINE.replace(
        "## Merge Order", "## Merge Order\n\n> Serialized: src/shared.py — T01, T02"
    ).replace("- src/app/schema.py", "- src/shared.py")
    plan_dir2 = _build(
        tmp_path / "b",
        spine=spine2,
        tickets={"T01-schema.md": t1, "T02-api.md": t2, "T99-integration.md": T99},
    )
    assert any(
        "Touches overlap between T01 and T02" in m
        for m in _errors(cpt.check_plan_dir(plan_dir2, context="cli"))
    )


def test_blockquoted_field_examples_never_parse(tmp_path: Path) -> None:
    # Blockquotes are quoted content: a quoted `> Depends: T01` must not
    # license an overlap, and a quoted `> Integration: true` must not mint a
    # phantom Integration ticket.
    t1 = T01.replace("- src/app/schema.py", "- src/shared.py")
    t2 = (
        T02.replace("- src/app/api.py", "- src/shared.py")
        .replace("Depends: T01", "Depends: none")
        .replace("## Scope", "> Depends: T01\n\n## Scope")
    )
    plan_dir = _build(
        tmp_path, tickets={"T01-schema.md": t1, "T02-api.md": t2, "T99-integration.md": T99}
    )
    errors = _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    assert any("Touches overlap between T01 and T02" in m for m in errors)
    # Quoted Integration is not counted: removing the real line leaves zero.
    t99 = T99.replace("Integration: true", "> Integration: true")
    plan_dir2 = _build(
        tmp_path / "b", tickets={"T01-schema.md": T01, "T02-api.md": T02, "T99-integration.md": t99}
    )
    errors2 = _errors(cpt.check_plan_dir(plan_dir2, context="cli"))
    assert any("exactly one 'Integration: true' ticket required (found 0)" in m for m in errors2)


def test_lowercase_serialized_label_parses(tmp_path: Path) -> None:
    # re.I parity with the rest of the family.
    t1 = T01.replace("- src/app/schema.py", "- src/shared.py")
    t2 = T02.replace("- src/app/api.py", "- src/shared.py").replace("Depends: T01", "Depends: none")
    spine = SPINE.replace(
        "## Merge Order", "## Merge Order\n\nserialized: src/shared.py — T01, T02"
    ).replace("- src/app/schema.py", "- src/shared.py")
    plan_dir = _build(
        tmp_path,
        spine=spine,
        tickets={"T01-schema.md": t1, "T02-api.md": t2, "T99-integration.md": T99},
    )
    assert not any(
        "Touches overlap between T01 and T02" in m
        for m in _errors(cpt.check_plan_dir(plan_dir, context="cli"))
    )


# ── a Gate that pipes into a display filter throws away the exit status it exists to check ──────
# transdoc, 2026-08-28, with hard evidence: five tickets declared
#   `pytest server/tests -q -p no:randomly 2>&1 | tail -5`
# against a repo with no `server/tests`. Measured: pipeline $?=0 while PIPESTATUS(pytest)=4,
# "no tests ran in 0.00s" — while the real root runs 472 passed. check_plan_tickets exited 0 with
# zero output both before AND after they fixed it, which is what makes it BLIND rather than lenient.
# Same shape as the "44 skipped, exit 0" hole the ${TEST_DATABASE_URL:?} guard closes: the guard
# shut the unset-variable door and the pipe opened a wider one beside it.


def test_a_gate_piping_into_tail_is_flagged():
    bad = cpt._gate_masks_exit_status("Gate: pytest server/tests -q -p no:randomly 2>&1 | tail -5")
    assert bad, "the exact filed shape must be caught"


def test_display_filters_are_all_covered():
    for filt in ("tail -5", "head -20", "cat", "less", "more"):
        assert cpt._gate_masks_exit_status(f"Gate: pytest tests -q | {filt}"), filt


def test_an_asserting_final_stage_is_not_flagged():
    """The false-positive side, and the reason the rule is display-only. `grep -q`, `grep -c` and
    `jq` as a final stage ARE the assertion — flagging them would be wrong. Measured fleet-wide:
    16 of 805 gates end in some filter, only 2 in a display filter."""
    for cmd in (
        "Gate: bash -c 'python x.py | grep -q OK'",
        "Gate: python -m pytest --collect-only -q | grep -c test_x",
        "Gate: curl -s url | jq -r .note",
    ):
        assert not cpt._gate_masks_exit_status(cmd), cmd


def test_a_gate_with_no_pipe_is_never_flagged():
    assert not cpt._gate_masks_exit_status("Gate: pytest tests -q -p no:randomly")


def test_a_quoted_gate_inside_a_fence_is_not_counted():
    """Fenced blocks are QUOTED content — the module's standing rule for every other Gate check."""
    assert not cpt._gate_masks_exit_status("```\nGate: pytest tests -q | tail -5\n```\n")


def test_the_masking_check_is_wired_into_the_audit_not_just_defined():
    """THE WIRING — the gap that slipped three times today: a helper covered while its call site
    was not. Asserted by reading the audit body, because building a full plan-set fixture here
    would test the fixture more than the rule."""
    src = Path(cpt.__file__).read_text(encoding="utf-8")
    assert "_gate_masks_exit_status(t.text)" in src, "the helper is defined but never called"
    call = src.index("_gate_masks_exit_status(t.text)")
    assert "results.append" in src[call - 200 : call + 400], "its finding never reaches results"


# ── the FROZEN 2-contract artifacts are not a ticket's scope ────────────────────────────────────
# transdoc, 2026-08-28: a 14-ticket GUI plan — all merged, reviewed, green — could not be marked
# EXECUTED, because the READ budget escalates WARN→ERROR on the CONVERGED/EXECUTED flip and the
# three FROZEN contracts exceed the ENTIRE budget by themselves (163292 + 65312 + 81827 = 310431 =
# 118%). A GUI ticket citing its own spec was over budget before naming a single source file.
# The commands require citing those contracts AND push them toward completeness, so the budget was
# punishing tickets for the quality of the artifacts they are told to read.


def test_the_frozen_contracts_are_exempt_from_the_read_budget():
    for f in ("docs/ui-design.md", "docs/flows.md", "docs/data-contract.md", "docs/design-system.md"):
        assert f in cpt.BUDGET_EXEMPT_READS, f


def test_the_exemption_is_narrow():
    """Only the mandatory shared contracts. Source files, tests and everything else a ticket names
    still count — the budget's real job is catching an over-scoped TICKET."""
    for f in ("src/app.py", "tests/test_x.py", "docs/FEATURES.md", "docs/QUICKSTART.md"):
        assert f not in cpt.BUDGET_EXEMPT_READS, f


def test_exempting_can_only_lower_a_total_never_raise_it():
    """Why this is safe to land on a BLOCKING escalation: the change removes bytes from a sum, so
    no plan that passes today can start failing."""
    src = Path(cpt.__file__).read_text(encoding="utf-8")
    i = src.index("BUDGET_EXEMPT_READS:")
    assert "continue" in src[i : i + 200], "the exemption must SKIP, never add"


# --- BC 25: generated build artifacts are WRITES, not reads ---------------------------
# transdoc 01M14A49ZN: openapi.json was 62% of one ticket's measured READ budget
# (161,606 of 464,566 B) and no agent holds it in context — it is regenerated by a
# command and committed. The budget asks "bytes a coder must hold in context"; a
# generated artifact answers a different question.
#
# ⚠️ transdoc ALSO offered a generic detector — "a Touches entry not cited in Context
# Files" — and asked to be told if it was another wallpaper case. MEASURED across 266
# real tickets in 15 repos: it would exempt 1045 of 1315 Touches entries (79.5%), and
# 100% in one repo, because Touches and Context Files are near-disjoint BY CONSTRUCTION.
# That does not narrow the budget, it deletes it. Rejected in favour of the signature
# below, which the same sweep measured at 6 entries — while `uv.lock` (288,726 B) alone
# exceeds the entire 262,144 budget.


def _with_touch(extra: str) -> dict[str, str]:
    """T01 with one extra Touches entry — the helper's own idiom, not a post-hoc rewrite."""
    return {
        "T01-schema.md": T01.replace("- src/app/schema.py", f"- src/app/schema.py\n- {extra}"),
        "T02-api.md": T02,
        "T99-integration.md": T99,
    }


def test_bc25_generated_openapi_json_is_budget_exempt(tmp_path: Path) -> None:
    (tmp_path / "openapi.json").write_text("x" * (cpt.READ_BUDGET_BYTES + 1), encoding="utf-8")
    plan_dir = _build(tmp_path, tickets=_with_touch("openapi.json"))
    results = cpt.check_plan_dir(plan_dir, context="cli")
    assert not any("READ budget" in m for m in _errors(results) + _warns(results))


def test_bc25_generated_lockfile_is_budget_exempt(tmp_path: Path) -> None:
    """A resolver output nobody reads. uv.lock at 288,726 B alone exceeds the budget."""
    (tmp_path / "uv.lock").write_text("x" * (cpt.READ_BUDGET_BYTES + 1), encoding="utf-8")
    plan_dir = _build(tmp_path, tickets=_with_touch("uv.lock"))
    results = cpt.check_plan_dir(plan_dir, context="cli")
    assert not any("READ budget" in m for m in _errors(results) + _warns(results))


def test_bc25_a_hand_authored_json_is_still_counted(tmp_path: Path) -> None:
    """The counter-direction, and the reason this is a SIGNATURE and not 'any .json':
    an authored config IS read by whoever edits it and must still blow the budget."""
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "settings.json").write_text(
        "x" * (cpt.READ_BUDGET_BYTES + 1), encoding="utf-8"
    )
    plan_dir = _build(tmp_path, tickets=_with_touch("config/settings.json"))
    results = cpt.check_plan_dir(plan_dir, context="cli")
    assert any("READ budget" in m for m in _errors(results) + _warns(results))
