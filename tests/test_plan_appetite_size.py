"""Plan graders: `Appetite:` per phase/ticket (spec D11) and the `Size: small` spec rule (D10).

Ticket T05a of plan 2026-10-02-plan-1-fabrik-task-feature-lane. Two layers:
the pure rules in `scripts/enforcement/plan_appetite.py`, and the two graders that
call them — `check_plan_tickets.check_plan_dir` (plan sets) and
`check_plan_quality.check_file` (monoliths, spines and tickets) — driven over
throwaway plan trees, never a stubbed module.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
import scripts.enforcement.check_plan_quality as cpq_mod
import scripts.enforcement.check_plan_tickets as cpt_mod
import scripts.enforcement.check_plans as cp_mod
from scripts.enforcement import plan_appetite as pa

PLANS = "docs/development/plans"
SPEC_REL = "docs/superpowers/specs/2026-10-03-widget-design.md"

TICKET = """# T01 — widget schema

Depends: none
Parallel: ⚡
Complexity: native
{appetite}Docs: none
Gate: python -m pytest tests/test_widget.py

## Scope

Build the widget schema.

## Touches

- src/widget/schema.py

## Behavior Contract

- **Given** a widget, **When** saved, **Then** it persists (src/widget/schema.py:1).

## Context Files

- .windsurf/rules/core/10-python.md
"""

SPINE = """# Plan: widget

Status: {status}
{profile}Spec: {spec}

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
"""

MONOLITH = """# Plan: widget

Status: {status}
{profile}Spec: {spec}

## Context Ledger

| a | b | c |

## File Scope (owned paths)

- src/x.py

## Phase A — the schema

{appetite_a}Step 1: write it.

## Phase B — the API

{appetite_b}Step 1: expose it.

## Evidence

src/x.py:1
"""

SPEC = """# Widget — design

Status: {status}
{size}Owner: infra

## Goal

A widget.
"""


def _write(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p.resolve()


def _monolith(appetite_a: str = "Appetite: 60\n", appetite_b: str = "Appetite: 90\n", **kw) -> str:
    return MONOLITH.format(
        status=kw.get("status", "CONVERGED"),
        profile=kw.get("profile", ""),
        spec=kw.get("spec", SPEC_REL),
        appetite_a=appetite_a,
        appetite_b=appetite_b,
    )


def _spec(status: str, size: str = "") -> str:
    return SPEC.format(status=status, size=size)


# --- the pure rules ---------------------------------------------------------------------------


def test_rollout_date_is_pinned() -> None:
    assert pa.LANE_ROLLOUT_DATE == "2026-10-03"


@pytest.mark.parametrize(
    "line",
    ["", "Appetite: 0\n", "Appetite: soon\n", "Appetite: -5\n", "Appetite:\n"],
    ids=["missing", "zero", "word", "negative", "empty"],
)
def test_ticket_without_a_positive_appetite_is_refused_naming_it(line: str) -> None:
    found = pa.appetite_findings(TICKET.format(appetite=line), "2026-10-03", label="T01")
    assert len(found) == 1
    assert "T01" in found[0]
    assert "Appetite" in found[0]


def test_ticket_with_a_positive_appetite_passes() -> None:
    for line in ("Appetite: 60\n", "**Appetite:** 45\n", "- Appetite: 30 min\n"):
        assert pa.appetite_findings(TICKET.format(appetite=line), "2026-10-03", label="T01") == []


def test_plan_dated_before_the_rollout_is_not_regraded() -> None:
    text = TICKET.format(appetite="")
    assert pa.appetite_findings(text, "2026-10-02", label="T01") == []
    assert pa.appetite_findings(_monolith("", "Appetite: soon\n"), "2026-10-02") == []


def test_monolith_phase_without_appetite_is_refused_naming_the_phase() -> None:
    found = pa.appetite_findings(_monolith("Appetite: 60\n", ""), "2026-10-03")
    assert len(found) == 1
    assert "Phase B" in found[0]
    assert pa.appetite_findings(_monolith(), "2026-10-03") == []


def test_fenced_appetite_does_not_satisfy_a_phase() -> None:
    fenced = "```\nAppetite: 60\n```\n"
    found = pa.appetite_findings(_monolith(fenced, "Appetite: 60\n"), "2026-10-04")
    assert len(found) == 1
    assert "Phase A" in found[0]


def test_spine_itself_needs_no_appetite() -> None:
    spine = SPINE.format(status="DRAFT", profile="", spec=SPEC_REL)
    assert pa.appetite_findings(spine, "2026-10-03") == []


def test_plan_date_of_reads_the_file_or_the_directory() -> None:
    assert pa.plan_date_of(Path(f"{PLANS}/2026-10-03-plan-1-w.md")) == "2026-10-03"
    assert pa.plan_date_of(Path(f"{PLANS}/2026-10-03-plan-1-w/T01-x.md")) == "2026-10-03"
    assert pa.plan_date_of(Path(f"{PLANS}/README.md")) is None


def test_small_profile_with_a_draft_spec_lacking_size_is_refused() -> None:
    plan = _monolith(profile="Profile: small\n")
    found = pa.small_profile_findings(plan, _spec("DRAFT"))
    assert len(found) == 1
    assert "Size: small" in found[0]


def test_small_profile_with_a_sized_draft_spec_passes() -> None:
    plan = _monolith(profile="Profile: small\n")
    sized = _spec("DRAFT", "Size: small (≈300 lines, 4 files)\n")
    assert pa.small_profile_findings(plan, sized) == []


def test_small_profile_with_a_converged_spec_passes_either_way() -> None:
    plan = _monolith(profile="Profile: small\n")
    assert pa.small_profile_findings(plan, _spec("CONVERGED")) == []
    assert pa.small_profile_findings(plan, _spec("CONVERGED", "Size: small\n")) == []


def test_full_profile_plan_is_not_held_to_the_size_rule() -> None:
    assert pa.small_profile_findings(_monolith(), _spec("DRAFT")) == []


def test_profile_regex_is_the_one_check_plan_tickets_uses() -> None:
    assert cpt_mod.PROFILE_RE is pa.PROFILE_RE


# --- the graders ------------------------------------------------------------------------------


def _set(root: Path, date: str, appetite: str, *, profile: str = "", status: str = "CONVERGED"):
    d = f"{PLANS}/{date}-plan-1-widget"
    _write(
        root,
        f"{d}/{date}-plan-1-widget.md",
        SPINE.format(status=status, profile=profile, spec=SPEC_REL),
    )
    _write(root, f"{d}/T01-widget-schema.md", TICKET.format(appetite=appetite))
    return (root / d).resolve()


def _messages(results) -> list[str]:
    return [r.message for r in results if r.severity.value in ("error", "warn")]


@pytest.fixture
def plans_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    try:
        monkeypatch.chdir(tmp_path)
        importlib.reload(cp_mod)
        importlib.reload(cpq_mod)
        yield tmp_path
    finally:
        monkeypatch.undo()
        importlib.reload(cp_mod)
        importlib.reload(cpq_mod)


@pytest.mark.parametrize("line", ["", "Appetite: 0\n", "Appetite: soon\n"])
def test_check_plan_tickets_refuses_a_ticket_without_appetite(tmp_path: Path, line: str) -> None:
    plan_dir = _set(tmp_path, "2026-10-03", line)
    found = [r for r in cpt_mod.check_plan_dir(plan_dir, context="cli") if "Appetite" in r.message]
    assert len(found) == 1
    assert "T01" in found[0].message
    assert found[0].severity.value == "error"


def test_check_plan_tickets_does_not_regrade_an_older_set(tmp_path: Path) -> None:
    plan_dir = _set(tmp_path, "2026-10-02", "")
    assert not [
        m for m in _messages(cpt_mod.check_plan_dir(plan_dir, context="cli")) if "Appetite" in m
    ]
    ok = _set(tmp_path, "2026-10-04", "Appetite: 60\n")
    assert not [m for m in _messages(cpt_mod.check_plan_dir(ok, context="cli")) if "Appetite" in m]


def test_check_plan_tickets_refuses_small_profile_on_an_unsized_draft_spec(tmp_path: Path) -> None:
    plan_dir = _set(tmp_path, "2026-10-03", "Appetite: 60\n", profile="Profile: small\n")
    _write(tmp_path, SPEC_REL, _spec("DRAFT"))
    found = [
        r for r in cpt_mod.check_plan_dir(plan_dir, context="cli") if "Size: small" in r.message
    ]
    assert len(found) == 1
    assert found[0].severity.value == "error"
    _write(tmp_path, SPEC_REL, _spec("DRAFT", "Size: small (≈200 lines, 2 files)\n"))
    assert not [
        m for m in _messages(cpt_mod.check_plan_dir(plan_dir, context="cli")) if "Size: small" in m
    ]
    _write(tmp_path, SPEC_REL, _spec("CONVERGED"))
    assert not [
        m for m in _messages(cpt_mod.check_plan_dir(plan_dir, context="cli")) if "Size: small" in m
    ]


def test_check_plan_quality_refuses_a_monolith_phase_without_appetite(plans_env: Path) -> None:
    p = _write(
        plans_env,
        f"{PLANS}/2026-10-03-plan-1-mono.md",
        _monolith("Appetite: 60\n", "Appetite: soon\n"),
    )
    found = [r for r in cpq_mod.check_file(p) if "Appetite" in r.message]
    assert len(found) == 1
    assert "Phase B" in found[0].message
    assert found[0].severity.value == "error"
    old = _write(plans_env, f"{PLANS}/2026-10-02-plan-1-mono.md", _monolith("", ""))
    assert not [r for r in cpq_mod.check_file(old) if "Appetite" in r.message]


def test_check_plan_quality_refuses_a_ticket_without_appetite(plans_env: Path) -> None:
    _set(plans_env, "2026-10-03", "Appetite: soon\n")
    ticket = (plans_env / f"{PLANS}/2026-10-03-plan-1-widget/T01-widget-schema.md").resolve()
    found = [r for r in cpq_mod.check_file(ticket) if "Appetite" in r.message]
    assert len(found) == 1
    assert "T01" in found[0].message


def test_check_plan_quality_refuses_small_profile_on_an_unsized_draft_spec(plans_env: Path) -> None:
    p = _write(
        plans_env,
        f"{PLANS}/2026-10-03-plan-2-mono.md",
        _monolith(profile="Profile: small\n"),
    )
    _write(plans_env, SPEC_REL, _spec("DRAFT"))
    found = [r for r in cpq_mod.check_file(p) if "Size: small" in r.message]
    assert len(found) == 1
    assert found[0].severity.value == "error"
    _write(plans_env, SPEC_REL, _spec("DRAFT", "Size: small\n"))
    assert not [r for r in cpq_mod.check_file(p) if "Size: small" in r.message]
    _write(plans_env, SPEC_REL, _spec("CONVERGED"))
    assert not [r for r in cpq_mod.check_file(p) if "Size: small" in r.message]
    # an older plan is not re-graded, whatever its spec says
    _write(plans_env, SPEC_REL, _spec("DRAFT"))
    old = _write(
        plans_env, f"{PLANS}/2026-10-02-plan-2-mono.md", _monolith(profile="Profile: small\n")
    )
    assert not [r for r in cpq_mod.check_file(old) if "Size: small" in r.message]
