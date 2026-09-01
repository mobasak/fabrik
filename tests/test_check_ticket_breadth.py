"""Ticket-breadth advisory — behaviour tests.

Each test names one user-observable behaviour from the check's contract
(``scripts/enforcement/check_ticket_breadth.py``): a narrow ticket is SILENT, a
broad one WARNS with its components named, ``--strict`` flips only the exit
code, a repo with no plan sets exits clean and silent, a malformed ticket fails
SOFT, and the two retroactively-measured anchors (T01 8 rounds / T02b 1 round)
land on the right side of the threshold.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.enforcement import check_ticket_breadth as ctb  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "enforcement" / "check_ticket_breadth.py"


# ── fixtures ────────────────────────────────────────────────────────────────


def _plan_set(root: Path, name: str = "2026-08-16-plan-1-fixture") -> Path:
    d = root / "docs" / "development" / "plans" / name
    d.mkdir(parents=True)
    (d / f"{name}.md").write_text("# spine\n\n## Ticket Board\n", encoding="utf-8")
    return d


NARROW = """# T02b — one gitignore line

## Scope
Add one line.

Depends: —
Complexity: native
Gate: pytest -q

## Touches
- scripts/fabrik_synced_manifest.py — PRIMARY PATH

## Behavior Contract
- **Given** the manifest's gitignore groups, **When** the block renders, **Then** it contains the line (scripts/fabrik_synced_manifest.py:208)
"""

# Mirrors 2026-08-15 T01's real shape: 2 areas (scripts, tests), 4 Given rows.
BROAD = """# T01 — Disarm the old world

## Scope
Gate the credential swapper.

Depends: —
Complexity: native
Gate: pytest -q

## Touches
- scripts/sysadmin/claude_rotate.py — PRIMARY PATH
- scripts/aro-wake/claude_rotate.py — byte-identical twin
- tests/test_claude_rotate_v2.py — red-first pair

## Behavior Contract
- **Given** the marker exists, **When** rotation triggers, **Then** it installs nothing (scripts/sysadmin/claude_rotate.py:403)
- **Given** the marker is absent, **When** the same trigger fires, **Then** rotation behaves as before (scripts/sysadmin/claude_rotate.py:649)
- **Given** the marker exists, **When** the operator runs --next, **Then** it refuses (scripts/sysadmin/claude_rotate.py:766)
- **Given** the marker exists, **When** a 401 leaves rotation withheld, **Then** no Telegram fires (scripts/sysadmin/claude_rotate.py:670)

## Context Files
- tests/test_claude_rotate_v2.py
"""


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=60
    )


# ── behaviour: a narrow ticket passes SILENTLY ──────────────────────────────


def test_narrow_ticket_is_silent_and_green(tmp_path: Path) -> None:
    d = _plan_set(tmp_path)
    (d / "T02b-narrow.md").write_text(NARROW, encoding="utf-8")
    proc = _run("--plan-dir", str(d), "--project-root", str(tmp_path))
    assert proc.returncode == 0
    assert proc.stdout.strip() == "", f"narrow ticket must be silent, got: {proc.stdout!r}"


# ── behaviour: a broad ticket WARNS with its components named ───────────────


def test_broad_ticket_warns_with_components_named(tmp_path: Path) -> None:
    d = _plan_set(tmp_path)
    (d / "T01-broad.md").write_text(BROAD, encoding="utf-8")
    proc = _run("--plan-dir", str(d), "--project-root", str(tmp_path))
    assert proc.returncode == 0, "advisory by default — a warning never reds the gate"
    out = proc.stdout
    assert "TICKET BREADTH" in out
    assert "T01" in out
    # Components, not a bare number.
    assert "areas=1" in out and "scripts" in out
    assert "test surface(s), not counted" in out
    assert "behaviors=4" in out
    assert "code+governance mix=no" in out
    # Predicted cost, with the measured basis cited.
    assert "predicted review cost" in out
    assert "rounds/plan" in out and "n=14/22" in out
    # A concrete split suggestion.
    assert "split:" in out
    # The footer must state the check's OWN accuracy at the point of use.
    assert "Calibration honesty" in out
    assert "2 of 4 flags" in out
    assert "prompt to LOOK, not a verdict" in out


def test_broad_ticket_score_matches_measured_anchor(tmp_path: Path) -> None:
    """T01's real shape scores 5 (1 non-test area + 4 behaviours); it cost 8
    rounds. Its `tests/` entry is a companion surface and must NOT add an area —
    after that fix T01 sits EXACTLY on the threshold, which is why 5 is the
    largest defensible value."""
    d = _plan_set(tmp_path)
    p = d / "T01-broad.md"
    p.write_text(BROAD, encoding="utf-8")
    b = ctb.measure_ticket(p)
    assert (len(b.areas), b.behaviors, b.mix) == (1, 4, False)
    assert b.areas == ["scripts"], "tests/ is not an independent risk area"
    assert b.test_areas == 1, "the test surface is seen, just not counted"
    assert b.score == 5
    assert b.flagged


def test_narrow_ticket_score_matches_measured_anchor(tmp_path: Path) -> None:
    """T02b's real shape scores 2 (1 area + 1 behaviour); it cost 1 round."""
    d = _plan_set(tmp_path)
    p = d / "T02b-narrow.md"
    p.write_text(NARROW, encoding="utf-8")
    b = ctb.measure_ticket(p)
    assert (len(b.areas), b.behaviors, b.mix) == (1, 1, False)
    assert b.score == 2
    assert not b.flagged


# ── behaviour: --strict flips the exit code, default stays 0 ────────────────


def test_strict_flips_exit_code_default_stays_zero(tmp_path: Path) -> None:
    d = _plan_set(tmp_path)
    (d / "T01-broad.md").write_text(BROAD, encoding="utf-8")
    default = _run("--plan-dir", str(d), "--project-root", str(tmp_path))
    strict = _run("--plan-dir", str(d), "--project-root", str(tmp_path), "--strict")
    assert default.returncode == 0
    assert strict.returncode == 1
    # Same warning text either way — only the exit code differs.
    assert "TICKET BREADTH" in default.stdout and "TICKET BREADTH" in strict.stdout


def test_strict_stays_zero_when_nothing_is_flagged(tmp_path: Path) -> None:
    d = _plan_set(tmp_path)
    (d / "T02b-narrow.md").write_text(NARROW, encoding="utf-8")
    assert _run("--plan-dir", str(d), "--project-root", str(tmp_path), "--strict").returncode == 0


# ── behaviour: a repo with NO plan sets exits clean and silent ──────────────


def test_repo_with_no_plan_sets_is_clean_and_silent(tmp_path: Path) -> None:
    """The fleet-wide inert case — most of the ~46 synced repos have no plans."""
    (tmp_path / "src").mkdir()
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, timeout=30)
    proc = _run("--project-root", str(tmp_path))
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
    strict = _run("--project-root", str(tmp_path), "--strict")
    assert strict.returncode == 0
    assert strict.stdout.strip() == ""


def test_all_sweep_on_repo_with_no_plans_is_clean(tmp_path: Path) -> None:
    proc = _run("--all", "--project-root", str(tmp_path))
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_nonexistent_plan_dir_never_reds(tmp_path: Path) -> None:
    proc = _run("--plan-dir", str(tmp_path / "nope"), "--project-root", str(tmp_path), "--strict")
    assert proc.returncode == 0


# ── behaviour: a malformed ticket fails SOFT ────────────────────────────────


def test_unparseable_ticket_fails_soft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A parse error must never block a gate — NOTE and carry on, exit 0."""
    d = _plan_set(tmp_path)
    p = d / "T01-boom.md"
    p.write_text(BROAD, encoding="utf-8")

    def _boom(*_a: object, **_k: object) -> str:
        raise OSError("simulated read failure")

    monkeypatch.setattr(Path, "read_text", _boom)
    b = ctb.measure_ticket(p)
    assert b.parse_note, "a failed parse must be recorded, not swallowed"
    assert b.score == 0
    assert not b.flagged
    lines = ctb.render([b])
    assert any("NOTE" in ln for ln in lines)


def test_garbage_ticket_body_does_not_raise_or_flag(tmp_path: Path) -> None:
    d = _plan_set(tmp_path)
    (d / "T01-garbage.md").write_text("\x00\x01 not markdown ## ## ##", encoding="utf-8")
    proc = _run("--plan-dir", str(d), "--project-root", str(tmp_path), "--strict")
    assert proc.returncode == 0


# ── behaviour: the code+governance mix is its own risk class ────────────────


def test_governance_dotfile_surface_is_detected(tmp_path: Path) -> None:
    """`.claude/hooks/…` is a fleet-synced surface — a leading-dot path must not
    slip past the governance test (it did, via lstrip('./'))."""
    d = _plan_set(tmp_path)
    p = d / "T05-router.md"
    p.write_text(
        "# T05\n\n## Touches\n"
        "- .claude/hooks/skill_router.py\n"
        "- src/app/router.py\n"
        "- tests/test_skill_router_hook.py\n\n"
        "## Behavior Contract\n- **Given** a prompt, **When** it routes, **Then** it fires (a.py:1)\n",
        encoding="utf-8",
    )
    b = ctb.measure_ticket(p)
    assert ".claude/hooks/skill_router.py" in b.gov_paths
    assert b.mix, "code + fleet-synced surface in one ticket is the mix class"
    assert ".claude" in b.areas


def test_governance_only_ticket_is_not_a_mix(tmp_path: Path) -> None:
    """T02b touches ONLY a synced file — a blast radius alone is not the mix
    class, and must not push a one-line ticket over the threshold."""
    d = _plan_set(tmp_path)
    p = d / "T02b-narrow.md"
    p.write_text(NARROW, encoding="utf-8")
    b = ctb.measure_ticket(p)
    assert b.gov_paths == ["scripts/fabrik_synced_manifest.py"]
    assert not b.mix


# ── behaviour: test surfaces are never a risk class nor a split target ──────


@pytest.mark.parametrize(
    "p",
    [
        "tests/test_x.py",
        "test/x.py",
        "src/app/__tests__/x.tsx",
        "spec/models/user_spec.rb",
        "src/app/button.test.ts",
        "src/app/button.spec.tsx",
        "scripts/test_helper.py",
        "conftest.py",
        "tests/",
    ],
)
def test_test_paths_are_recognised(p: str) -> None:
    assert ctb._is_test_path(p), f"{p} must be treated as a companion test surface"


@pytest.mark.parametrize(
    "p", ["scripts/sysadmin/rotate.py", "src/contest.py", "docs/testing.md", "libs/latest/x.py"]
)
def test_production_paths_are_not_test_paths(p: str) -> None:
    assert not ctb._is_test_path(p), f"{p} is production code, not a test surface"


def test_split_hint_never_suggests_separating_tests(tmp_path: Path) -> None:
    """The anti-pattern guard: tests ship WITH the behaviour they prove. A ticket
    whose tests live elsewhere cannot be red-on-revert proven and its Gate would
    pass while proving nothing — so no suggestion may ever peel them off."""
    d = _plan_set(tmp_path)
    p = d / "T01-broad.md"
    p.write_text(BROAD, encoding="utf-8")
    hint = ctb.measure_ticket(p).split_hint()
    assert "peel off tests" not in hint
    assert "tests/" not in hint.split("never split")[0]


def test_multi_area_hint_keeps_tests_with_their_code(tmp_path: Path) -> None:
    d = _plan_set(tmp_path)
    p = d / "T01-multi.md"
    p.write_text(
        "# T01\n\n## Touches\n"
        "- src/api/routes.py\n"
        "- docs/QUICKSTART.md\n"
        "- tests/test_routes.py\n\n"
        "## Behavior Contract\n"
        "- **Given** a route, **When** called, **Then** it answers (src/api/routes.py:1)\n",
        encoding="utf-8",
    )
    b = ctb.measure_ticket(p)
    # 01M1DMBS overturned the old "docs is a real area" contract: a QUICKSTART
    # row travels with the API change that invalidates it (Doc Sync Matrix) —
    # peeling it was advice a HARD governance rule forbids. Use a second CODE
    # area to keep exercising the multi-area hint.
    assert b.areas == ["src"], "docs is a doc-sync companion now; tests never counted"
    assert b.docsync_areas == 1
    p2 = d / "T02-multi.md"
    p2.write_text(
        "# T02\n\n## Touches\n- src/api/routes.py\n- libs/client/sdk.py\n"
        "- tests/test_routes.py\n\n## Behavior Contract\n"
        "- **Given** a route, **When** called, **Then** it answers (src/api/routes.py:1)\n",
        encoding="utf-8",
    )
    hint = ctb.measure_ticket(p2).split_hint()
    assert "peel off libs/" in hint
    assert "their tests move WITH them" in hint
    assert "peel off tests" not in hint


def test_test_only_ticket_scores_as_one_area(tmp_path: Path) -> None:
    """A test-only ticket touches something — one area, never zero, never many."""
    d = _plan_set(tmp_path)
    p = d / "T09-tests-only.md"
    p.write_text(
        "# T09\n\n## Touches\n- tests/test_a.py\n- tests/integration/test_b.py\n\n"
        "## Behavior Contract\n"
        "- **Given** the suite, **When** it runs, **Then** it is green (tests/test_a.py:1)\n",
        encoding="utf-8",
    )
    b = ctb.measure_ticket(p)
    assert b.areas == ["<tests-only>"]
    assert b.score == 2
    assert not b.flagged


def test_governance_plus_only_tests_is_not_a_mix(tmp_path: Path) -> None:
    """A synced surface plus its own tests is one axis, not a code/governance mix
    — the test file must not supply the 'code' half."""
    d = _plan_set(tmp_path)
    p = d / "T05-gov.md"
    p.write_text(
        "# T05\n\n## Touches\n"
        "- .claude/hooks/skill_router.py\n"
        "- tests/test_skill_router_hook.py\n\n"
        "## Behavior Contract\n- **Given** a prompt, **When** it routes, **Then** it fires (a.py:1)\n",
        encoding="utf-8",
    )
    b = ctb.measure_ticket(p)
    assert ".claude/hooks/skill_router.py" in b.gov_paths
    assert not b.mix, "tests are not the local-code half of the blast-radius mix"


# ── behaviour: fenced examples never inflate the score ──────────────────────


def test_fenced_example_rows_do_not_count(tmp_path: Path) -> None:
    d = _plan_set(tmp_path)
    p = d / "T04-fenced.md"
    p.write_text(
        "# T04\n\n## Touches\n- docs/reference/x.md\n\n"
        "## Behavior Contract\n"
        "- **Given** a doc, **When** it renders, **Then** it is true (docs/reference/x.md:1)\n\n"
        "```\n"
        "- **Given** a template row, **When** quoted, **Then** it must not count\n"
        "- **Given** another, **When** quoted, **Then** still no\n"
        "- **Given** a third, **When** quoted, **Then** still no\n"
        "- **Given** a fourth, **When** quoted, **Then** still no\n"
        "```\n",
        encoding="utf-8",
    )
    b = ctb.measure_ticket(p)
    assert b.behaviors == 1, "fenced example rows are quoted content, never behaviours"
    assert not b.flagged


def test_01m1dmbs_docsync_companions_never_count_as_areas(tmp_path):
    """01M1DMBS (wef, measured): counting docs/ + Doc-Sync root files as risk areas
    produced the remedy 'peel docs/ into a separate ticket' — which CLAUDE.md's Doc
    Sync Matrix forbids, and following it RAISED the flag count 3->4. Doc-sync
    companions now get the test-surface treatment: not an area, never a peel target."""
    t = tmp_path / "T01-widget.md"
    t.write_text(
        "# T01 — widget\n\n"
        "## Touches\n"
        "- src/widget/core.py\n"
        "- docs/CONFIGURATION.md\n"
        "- CHANGELOG.md\n"
        "- .env.example\n"
        "- tests/test_widget.py\n\n"
        "## Behavior Contract\n"
        "| GIVEN a | WHEN b | THEN c |\n"
    )
    from scripts.enforcement.check_ticket_breadth import measure_ticket

    b = measure_ticket(t)
    assert b.areas == ["src"], b.areas  # docs/, CHANGELOG, .env.example all companions
    assert b.docsync_areas >= 2
    assert "travel with the code" in b.components()


def test_docs_only_ticket_still_scores_its_own_axis(tmp_path):
    # A docs-ONLY ticket must not vanish to zero signal — mirror of tests-only.
    t = tmp_path / "T02-docs.md"
    t.write_text(
        "# T02 — docs\n\n## Touches\n- docs/FEATURES.md\n- docs/QUICKSTART.md\n\n"
        "## Behavior Contract\n| GIVEN a | WHEN b | THEN c |\n"
    )
    from scripts.enforcement.check_ticket_breadth import measure_ticket

    b = measure_ticket(t)
    assert b.score >= 1  # behaviors still count; the ticket is visible
