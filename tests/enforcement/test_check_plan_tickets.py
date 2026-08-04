"""Tests for scripts/enforcement/check_plan_tickets.py (Behavior Contract 7-12, 16-17, 19-24, 26).

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
Complexity: simple
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
| T01 | schema | — | ⚡ | ⬜ | — |
| T02 | api | T01 | ⛓️ | ⬜ | — |
| T99 | integration | T02 | ⛓️ | ⬜ | — |

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
            "| T01 | schema | — | ⚡ | ⬜ | — |", "| T01 | schema | — | ⚡ | ✅ | abc123 |"
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
        "| T02 | api | T01 | ⛓️ | ⬜ | — |",
        "| T02 | api | T01 | ⛓️ | ⬜ | — |\n| T77 | ghost | — | ⚡ | ⬜ | — |",
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
        "| T02 | api | T01 | ⛓️ | ⬜ | — |",
        "| T02 | api | T01 | ⛓️ | ⬜ | — |\n| T88 | ghost | — | ⚡ | ⬜ | — |",
    )
    plan_dir = _build(tmp_path, spine=spine)
    res = cpt.check_plan_dir(plan_dir, context="gate")
    # NOT downgraded (unknown ≠ draft-like): orphan stays ERROR + the status itself flagged
    assert any("orphan row" in m for m in _errors(res))
    assert any("not a pipeline value" in m for m in _errors(res))


def test_adapter_path_is_always_advisory(tmp_path: Path) -> None:
    # A CONVERGED sibling set with structural breaks must not hard-red the
    # per-file validate_conventions path (it cannot know whose plan this is).
    spine = SPINE.replace("Status: DRAFT", "Status: CONVERGED").replace(
        "| T02 | api | T01 | ⛓️ | ⬜ | — |",
        "| T02 | api | T01 | ⛓️ | ⬜ | — |\n| T88 | ghost | — | ⚡ | ⬜ | — |",
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
