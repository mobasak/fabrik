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


# --- review round 1 (T05a-O1..O10) ------------------------------------------------------------

_SMALL_PLAN = "# P\n\nStatus: DRAFT\nProfile: small\nSpec: docs/superpowers/specs/s.md\n\n## Phase A\n\nAppetite: 30\n"


def test_o1_check_plan_tickets_does_not_regrade_small_profile_on_an_older_set(
    tmp_path: Path,
) -> None:
    plan_dir = _set(tmp_path, "2026-10-02", "Appetite: 60\n", profile="Profile: small\n")
    _write(tmp_path, SPEC_REL, _spec("DRAFT"))
    msgs = _messages(cpt_mod.check_plan_dir(plan_dir, context="cli"))
    assert not [m for m in msgs if "Size: small" in m or "Appetite" in m]


def test_o2_plan_date_of_reads_any_leading_date() -> None:
    assert pa.plan_date_of(Path(f"{PLANS}/2026-10-05-widget.md")) == "2026-10-05"


def test_o2_check_plan_quality_grades_a_legacy_named_monolith(plans_env: Path) -> None:
    p = _write(plans_env, f"{PLANS}/2026-10-05-widget.md", _monolith("", "Appetite: 60\n"))
    assert [r for r in cpq_mod.check_file(p) if "Appetite" in r.message]


@pytest.mark.parametrize(
    "header",
    [
        "Status: PROPOSED\n",
        "",
        "Status: LOCKED\n",
        "Status: PLANNED\n",
        "> **Status:** DRAFT\n",
        "| Field | Value |\n|---|---|\n| Status | DRAFT |\n",
    ],
    ids=["proposed", "no-status", "locked", "planned", "blockquoted-draft", "table-draft"],
)
def test_o3_o7_unconverged_or_unreadable_spec_status_is_refused(header: str) -> None:
    spec = f"# s\n\n{header}\n## Goal\n"
    assert len(pa.small_profile_findings(_SMALL_PLAN, spec)) == 1


@pytest.mark.parametrize(
    "header",
    [
        "Status: CONVERGED\n",
        "**Status:** CONVERGED (D-1)\n",
        "> **Status:** CONVERGED\n",
        "| Field | Value |\n|---|---|\n| Status | CONVERGED |\n",
    ],
    ids=["plain", "bold", "blockquoted", "table"],
)
def test_o7_converged_spec_in_every_form_passes(header: str) -> None:
    assert pa.small_profile_findings(_SMALL_PLAN, f"# s\n\n{header}\n## Goal\n") == []


def test_o4_check_plan_quality_grades_a_pillarless_post_rollout_monolith(plans_env: Path) -> None:
    text = (
        "# P\n\nStatus: DRAFT\nProfile: small\nSpec: docs/superpowers/specs/2026-10-03-widget-design.md\n\n"
        "## Phase A\n\nStep 1.\n"
    )
    _write(plans_env, SPEC_REL, _spec("DRAFT"))
    p = _write(plans_env, f"{PLANS}/2026-10-05-plan-2-x.md", text)
    msgs = [r.message for r in cpq_mod.check_file(p)]
    assert any("Appetite" in m for m in msgs)
    assert any("Size: small" in m for m in msgs)


def test_o5_ticket_is_graded_by_its_field_line_not_its_phase_subheadings() -> None:
    t = "# T01 - x\n\nDepends: none\nAppetite: 60\n\n## Scope\n\n### Phase 1 — red\nw\n### Phase 2 — green\nc\n"
    assert pa.appetite_findings(t, "2026-10-03", label="T01", ticket=True) == []
    assert (
        len(
            pa.appetite_findings(
                t.replace("Appetite: 60\n", ""), "2026-10-03", label="T01", ticket=True
            )
        )
        == 1
    )


def test_o5_check_plan_tickets_ticket_with_phase_subheadings_passes(tmp_path: Path) -> None:
    plan_dir = _set(tmp_path, "2026-10-03", "Appetite: 60\n")
    t = plan_dir / "T01-widget-schema.md"
    t.write_text(t.read_text() + "\n### Phase 1 — red\nwrite tests\n", encoding="utf-8")
    assert not [
        m for m in _messages(cpt_mod.check_plan_dir(plan_dir, context="cli")) if "Appetite" in m
    ]


def test_o5_phase_out_heading_is_not_a_phase() -> None:
    h = "# Plan\n\n## Phase-out of the old API (background)\n\ncontext\n\n## Phase 1\n\nAppetite: 30\n"
    assert pa.appetite_findings(h, "2026-10-03") == []


@pytest.mark.parametrize(
    "field",
    [
        "> **Spec:** docs/superpowers/specs/s.md",
        "Spec (source of truth): `docs/superpowers/specs/s.md` (CONVERGED)",
        "**Spec:** docs/superpowers/specs/s.md",
        "**Spec:** [design](../../superpowers/specs/s.md)",
    ],
    ids=["blockquoted", "parenthesised", "bold", "relative-link"],
)
def test_o6_spec_field_forms_resolve(tmp_path: Path, field: str) -> None:
    _write(tmp_path, "docs/superpowers/specs/s.md", "# s\n\nStatus: DRAFT\n")
    plan = f"# Plan\n\nStatus: DRAFT\nProfile: small\n{field}\n\n## Phase A\n"
    plan_dir = tmp_path / "docs/development/plans"
    assert pa.spec_text_for(plan, tmp_path, plan_dir) == "# s\n\nStatus: DRAFT\n"


def test_o8_size_small_in_spec_body_does_not_count() -> None:
    spec = "# s\n\nStatus: DRAFT\n\n## Goal\n\nSize: small\n"
    assert len(pa.small_profile_findings(_SMALL_PLAN, spec)) == 1


def test_o8_spec_field_outside_the_header_is_not_read(tmp_path: Path) -> None:
    _write(tmp_path, "docs/superpowers/specs/s.md", "# s\n\nStatus: DRAFT\n")
    plan = "# Plan\n\nStatus: DRAFT\n\n## Notes\n\nSpec: docs/superpowers/specs/s.md\n"
    assert pa.spec_text_for(plan, tmp_path) is None


def test_o8_profile_small_outside_the_header_does_not_arm_the_rule() -> None:
    plan = "# P\n\nStatus: DRAFT\n\n## Global Constraints\n\nProfile: small\n"
    assert pa.small_profile_findings(plan, _spec("DRAFT")) == []


def test_o8_appetite_inside_an_unclosed_fence_does_not_count() -> None:
    t = "# T01\n\nDepends: none\n```\nAppetite: 60\n"
    assert len(pa.appetite_findings(t, "2026-10-03", label="T01", ticket=True)) == 1


def test_o8_appetite_with_trailing_junk_is_refused() -> None:
    t = "# T01\n\nAppetite: 60abc\n"
    assert len(pa.appetite_findings(t, "2026-10-03", label="T01", ticket=True)) == 1


@pytest.mark.parametrize("value", ["small-to-medium", "small? no — large", "smallish"])
def test_o9_size_must_be_small_as_the_whole_value(value: str) -> None:
    spec = f"# s\n\nStatus: DRAFT\nSize: {value}\n\n## Goal\n"
    assert len(pa.small_profile_findings(_SMALL_PLAN, spec)) == 1


@pytest.mark.parametrize("value", ["small", "small   ", "small (≈300 lines, 4 files)", "**small**"])
def test_o9_size_small_value_forms_pass(value: str) -> None:
    spec = f"# s\n\nStatus: DRAFT\nSize: {value}\n\n## Goal\n"
    assert pa.small_profile_findings(_SMALL_PLAN, spec) == []


def test_o10_blockquoted_profile_does_not_arm_the_rule() -> None:
    plan = _SMALL_PLAN.replace("Profile: small", "> Profile: small")
    assert pa.small_profile_findings(plan, _spec("DRAFT")) == []


def test_o10_both_graders_agree_on_a_blockquoted_profile(plans_env: Path) -> None:
    plan_dir = _set(plans_env, "2026-10-03", "Appetite: 60\n", profile="> Profile: small\n")
    _write(plans_env, SPEC_REL, _spec("DRAFT"))
    spine = plan_dir / f"{plan_dir.name}.md"
    cpt = [
        m for m in _messages(cpt_mod.check_plan_dir(plan_dir, context="cli")) if "Size: small" in m
    ]
    cpq = [r for r in cpq_mod.check_file(spine) if "Size: small" in r.message]
    assert cpt == [] and cpq == []


def test_o5_ticket_with_level_two_phase_headings_is_graded_once() -> None:
    t = "# T01 - x\n\nAppetite: 60\n\n## Phase 1 — red\n\nw\n\n## Phase 2 — green\n\nc\n"
    assert pa.appetite_findings(t, "2026-10-03", label="T01", ticket=True) == []
    assert pa.lane_findings(t, Path(f"{PLANS}/2026-10-03-plan-1-w/T01-x.md"), None) == []


# --- review round 1b (coordinator rulings on the open concerns) ------------------------------


def test_r1b_small_profile_without_a_spec_citation_is_refused(tmp_path: Path) -> None:
    plan = "# P\n\nStatus: DRAFT\nProfile: small\n\n## Phase A\n\nAppetite: 30\n"
    found = pa.lane_findings(plan, Path(f"{PLANS}/2026-10-03-plan-1-p.md"), tmp_path)
    assert len(found) == 1
    assert "no spec citation" in found[0]


def test_r1b_small_profile_citing_a_missing_spec_is_refused(tmp_path: Path) -> None:
    found = pa.lane_findings(_SMALL_PLAN, Path(f"{PLANS}/2026-10-03-plan-1-p.md"), tmp_path)
    assert len(found) == 1
    assert "docs/superpowers/specs/s.md" in found[0]
    assert "does not exist" in found[0]


def test_r1b_full_profile_plan_without_a_spec_is_not_refused(tmp_path: Path) -> None:
    plan = "# P\n\nStatus: DRAFT\n\n## Phase A\n\nAppetite: 30\n"
    assert pa.lane_findings(plan, Path(f"{PLANS}/2026-10-03-plan-1-p.md"), tmp_path) == []


def test_r1b_check_plan_quality_refuses_small_profile_citing_a_missing_spec(
    plans_env: Path,
) -> None:
    p = _write(
        plans_env, f"{PLANS}/2026-10-03-plan-3-mono.md", _monolith(profile="Profile: small\n")
    )
    found = [r for r in cpq_mod.check_file(p) if "does not exist" in r.message]
    assert len(found) == 1
    assert found[0].severity.value == "error"


def test_r1b_mid_line_spec_citation_resolves(tmp_path: Path) -> None:
    _write(tmp_path, "docs/superpowers/specs/s.md", "# s\n\nStatus: DRAFT\n")
    plan = "# Plan\n\nStatus: DRAFT\nProfile: small\nDate: 2026-10-05 · Spec: docs/superpowers/specs/s.md\n\n## Phase A\n"
    assert pa.spec_text_for(plan, tmp_path) == "# s\n\nStatus: DRAFT\n"


# --- review round 2 (T05a-O11..O13) ----------------------------------------------------------


def test_o11_word_named_phases_are_each_graded() -> None:
    plan = (
        "# P\n\nStatus: DRAFT\n\n## Phase One\n\nAppetite: 30\n\n"
        "## Phase Three — build\n\nstep\n\n## Phase Seven\n\nstep\n"
    )
    found = pa.appetite_findings(plan, "2026-10-05")
    assert len(found) == 2
    assert any("Phase Three" in f for f in found)
    assert any("Phase Seven" in f for f in found)


def test_o11_long_word_phases_do_not_fall_back_to_one_plan_line() -> None:
    plan = "# P\n\nAppetite: 30\n\n## Phase Alpha\n\nstep\n\n## Phase Gamma\n\nstep\n"
    found = pa.appetite_findings(plan, "2026-10-05")
    assert len(found) == 2


def test_o11_phases_heading_is_not_a_phase() -> None:
    plan = "# P\n\n## Phases\n\noverview\n\n## Phase 1\n\nAppetite: 30\n"
    assert pa.appetite_findings(plan, "2026-10-05") == []


def test_o11_level_three_phase_subheading_is_not_a_separate_phase() -> None:
    plan = (
        "# P\n\n## Phase A\n\nAppetite: 30\n\n### Phase 1 — red\n\nw\n\n### Phase 2 — green\n\nc\n"
    )
    assert pa.appetite_findings(plan, "2026-10-05") == []


def test_o12_prose_spec_phrase_does_not_beat_the_real_field(tmp_path: Path) -> None:
    _write(tmp_path, "docs/superpowers/specs/old.md", "# o\n\nStatus: DRAFT\n")
    _write(tmp_path, "docs/superpowers/specs/new.md", "# n\n\nStatus: CONVERGED\n")
    plan = (
        "# P\n\nStatus: DRAFT\nProfile: small\n"
        "Supersedes the older spec: docs/superpowers/specs/old.md\n"
        "Spec: docs/superpowers/specs/new.md\n\n## Phase A\n\nAppetite: 30\n"
    )
    assert pa.spec_text_for(plan, tmp_path) == "# n\n\nStatus: CONVERGED\n"
    assert pa.lane_findings(plan, Path(f"{PLANS}/2026-10-05-plan-1-p.md"), tmp_path) == []


def test_o12_mid_line_field_needs_a_separator_and_a_path(tmp_path: Path) -> None:
    _write(tmp_path, "docs/superpowers/specs/s.md", "# s\n\nStatus: DRAFT\n")
    prose = (
        "# P\n\nProfile: small\nThis follows the spec: docs/superpowers/specs/s.md\n\n## Phase A\n"
    )
    assert pa.spec_text_for(prose, tmp_path) is None
    no_path = "# P\n\nProfile: small\nDate: 2026-10-05 · Spec: see below\n\n## Phase A\n"
    assert pa.spec_text_for(no_path, tmp_path) is None
    for sep in (" · ", " | ", ", ", "; "):
        plan = f"# P\n\nProfile: small\nDate: 2026-10-05{sep}Spec: docs/superpowers/specs/s.md\n\n## Phase A\n"
        assert pa.spec_text_for(plan, tmp_path) == "# s\n\nStatus: DRAFT\n", sep


@pytest.mark.parametrize("name", ["README.md", "notes.md", "2026-10-05-scratch.md"])
def test_o13_non_spine_non_ticket_file_in_a_set_dir_is_skipped(name: str) -> None:
    path = Path(f"{PLANS}/2026-10-05-plan-1-x/{name}")
    assert pa.lane_findings("# Notes\n\nsome notes\n", path, None) == []


def test_o13_spine_and_ticket_in_a_set_dir_are_still_graded() -> None:
    d = f"{PLANS}/2026-10-05-plan-1-x"
    assert pa.lane_findings("# T01\n\nDepends: none\n", Path(f"{d}/T01-a.md"), None)
    spine = "# P\n\nStatus: DRAFT\nProfile: small\n\n## Ticket Board\n"
    assert pa.lane_findings(spine, Path(f"{d}/2026-10-05-plan-1-x.md"), Path("/nonexistent"))


def test_o13_check_plan_quality_skips_notes_in_a_set_dir(plans_env: Path) -> None:
    _set(plans_env, "2026-10-05", "Appetite: 60\n")
    p = _write(plans_env, f"{PLANS}/2026-10-05-plan-1-widget/notes.md", "# Notes\n\nsome notes\n")
    assert not [r for r in cpq_mod.check_file(p) if "Appetite" in r.message]


def test_o12_a_pathless_mid_line_field_does_not_hide_a_later_one(tmp_path: Path) -> None:
    _write(tmp_path, "docs/superpowers/specs/s.md", "# s\n\nStatus: DRAFT\n")
    plan = (
        "# P\n\nProfile: small\nDate: 2026-10-05 · Spec: see below\n"
        "Owner: infra · Spec: docs/superpowers/specs/s.md\n\n## Phase A\n"
    )
    assert pa.spec_text_for(plan, tmp_path) == "# s\n\nStatus: DRAFT\n"


# --- T08-D7: the whole-plan review's plan-grader findings ------------------------------------


def test_c_s1_an_explicit_external_root_wins_over_the_layout_root(tmp_path: Path) -> None:
    layout, external = tmp_path / "layout", tmp_path / "external"
    plan_dir = _set(layout, "2026-10-03", "Appetite: 60\n", profile="Profile: small\n")
    _write(layout, SPEC_REL, _spec("DRAFT"))
    _write(external, SPEC_REL, _spec("CONVERGED"))
    results = cpt_mod.check_plan_dir(plan_dir, context="cli", external_root=external)
    assert not [m for m in _messages(results) if "Size: small" in m]
    # the mirror: without external_root the layout's own (DRAFT) spec is graded
    results = cpt_mod.check_plan_dir(plan_dir, context="cli")
    assert [m for m in _messages(results) if "Size: small" in m]


def test_c_s2_check_plan_quality_resolves_the_spec_from_the_plan_files_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    _write(repo, SPEC_REL, _spec("DRAFT"))
    p = _write(repo, f"{PLANS}/2026-10-05-plan-2-x.md", _monolith(profile="Profile: small\n"))
    # PLAN_DIR is the cwd captured at import; here it encloses the repo instead of naming it
    monkeypatch.setattr(cpq_mod, "PLAN_DIR", tmp_path.resolve())
    msgs = [r.message for r in cpq_mod.check_file(p)]
    assert not any("does not exist" in m for m in msgs), msgs
    assert any("not CONVERGED" in m for m in msgs), msgs


def test_c_s2_repo_root_of_reads_the_layout_of_monoliths_sets_and_archives(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    for rel in (
        f"{PLANS}/2026-10-05-plan-2-x.md",
        f"{PLANS}/2026-10-05-plan-1-x/T01-a.md",
        f"{PLANS}/archived/2026-10-05-plan-1-x/2026-10-05-plan-1-x.md",
    ):
        assert pa.repo_root_of(root / rel) == root, rel
    assert pa.repo_root_of(root / "notes" / "x.md") is None


def test_c_s3_a_markdown_link_spec_is_cited_once() -> None:
    plan = "# P\n\nSpec: [design](docs/superpowers/specs/s.md)\n\n## Phase A\n"
    assert pa.spec_citations(plan) == ["docs/superpowers/specs/s.md"]
    two = "# P\n\nSpec: [a](docs/a.md), `docs/b.md`, docs/a.md\n\n## Phase A\n"
    assert pa.spec_citations(two) == ["docs/a.md", "docs/b.md"]


@pytest.mark.parametrize("form", ["{p}", "`{p}`", "[design]({p})"])
def test_c_o3_an_absolute_spec_path_inside_the_repo_resolves(tmp_path: Path, form: str) -> None:
    _write(tmp_path, "docs/superpowers/specs/s.md", "# s\n\nStatus: DRAFT\n")
    cite = form.format(p=f"{tmp_path.resolve()}/docs/superpowers/specs/s.md")
    plan = f"# P\n\nProfile: small\nSpec: {cite}\n\n## Phase A\n"
    assert pa.resolve_spec(plan, tmp_path) == ("# s\n\nStatus: DRAFT\n", None)


@pytest.mark.parametrize("form", ["{p}", "[design]({p})"])
def test_c_o3_an_absolute_spec_path_outside_the_repo_is_not_found(
    tmp_path: Path, form: str
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = _write(tmp_path, "elsewhere/docs/s.md", "# s\n\nStatus: CONVERGED\n")
    plan = f"# P\n\nProfile: small\nSpec: {form.format(p=outside)}\n\n## Phase A\n"
    text, why = pa.resolve_spec(plan, repo, repo / PLANS)
    assert text is None
    assert why and "does not exist" in why and str(outside) in why


def test_c_o4_a_ticket_is_graded_by_its_header_field_lines_only() -> None:
    body_only = "# T01 - x\n\nDepends: none\n\n## Scope\n\nAppetite: 60\n"
    found = pa.appetite_findings(body_only, "2026-10-03", label="T01", ticket=True)
    assert len(found) == 1 and "T01" in found[0], found
    prose = "# T01 - x\n\nAppetite: 60\n\n## Scope\n\nAppetite: soon, once T00 lands\n"
    assert pa.appetite_findings(prose, "2026-10-03", label="T01", ticket=True) == []
    quoted = "# T01 - x\n\n> Appetite: 60\n\n## Scope\n"
    assert len(pa.appetite_findings(quoted, "2026-10-03", label="T01", ticket=True)) == 1


@pytest.mark.parametrize("fence", ["~~~", "```"])
def test_c_o6_both_graders_agree_on_a_fenced_heading_in_the_header(
    tmp_path: Path, fence: str
) -> None:
    plan_dir = _set(tmp_path, "2026-10-03", "Appetite: 60\n")
    spine = plan_dir / f"{plan_dir.name}.md"
    text = spine.read_text(encoding="utf-8").replace(
        "\n\n## Ticket Board", f"\n{fence}\n## fake\n{fence}\nProfile: small\n\n## Ticket Board", 1
    )
    spine.write_text(text, encoding="utf-8")
    _write(tmp_path, SPEC_REL, _spec("DRAFT"))
    results = cpt_mod.check_plan_dir(plan_dir, context="cli")
    waived = any("WAIVED" in r.message for r in results)
    d10 = any("Size: small" in r.message for r in results)
    assert waived == d10, (fence, waived, d10)
    assert pa.is_small_profile(text) == waived
    # the zone is CUT at the fenced heading first, so the Profile line past it is not header
    assert waived is False
