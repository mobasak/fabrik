"""The anti-mix-up guard must actually BLOCK — found at corpus audit cmd 14/31 (2026-08-29).

Three texts claimed the namespace findings are BLOCKING (`fabrik-user-test.md`, the check's own
docstring, `final_gate.py`'s registration comment: "BLOCKING by their own flag") while the check
`return 0`-ed on every path under `warn_only=True` — so a cert board that `/fabrik-execute-plan`
would dispatch to CODING agents produced a warning nobody reads and a green gate. A safety guard
that was prose all the way down: the exact fail-silent-green class this corpus keeps finding.

The contract now: coverage-quality findings stay advisory (exit 0); a MIX-UP finding exits 1, which
the gate turns into a red. These tests pin both directions plus the anti-pattern-91 guards.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHECK = REPO / "scripts" / "enforcement" / "check_certification_coverage.py"


def run(root: Path, *extra: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(CHECK), "--project-root", str(root), *extra],
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _board(root: Path, spine: str) -> Path:
    d = root / "docs" / "development" / "certifications" / "2026-01-01-cert-probe"
    d.mkdir(parents=True)
    (d / "2026-01-01-cert-probe.md").write_text(spine, encoding="utf-8")
    return d


def test_a_mixup_board_exits_nonzero_so_the_gate_can_actually_block(tmp_path):
    """The founding defect: `## Ticket Board` on a cert spine dispatches CODING agents."""
    _board(tmp_path, "# cert\n\n## Ticket Board\n\n| id |\n")
    rc, out = run(tmp_path)
    assert rc != 0, f"a mix-up board exited 0 — the BLOCKING claim is typography again: {out}"
    assert "MIX-UP" in out, out


def test_a_cert_lock_in_the_plan_lock_dir_also_blocks(tmp_path):
    locks = tmp_path / ".fabrik" / "plan-locks"
    locks.mkdir(parents=True)
    # A REAL cert lock: detection is precise by design — `plan` must point INTO the
    # certifications tree (a bare "cert" substring once flagged an implementation plan ABOUT
    # certification). An empty dict is the naive fixture the guard deliberately ignores.
    (locks / "2026-01-01-cert-probe.json").write_text(
        '{"plan": "docs/development/certifications/2026-01-01-cert-probe/2026-01-01-cert-probe.md"}',
        encoding="utf-8",
    )
    _board(tmp_path, "# cert\n\n## Test Board\n\n| id |\n")
    rc, out = run(tmp_path)
    assert rc != 0, f"a cert lock among plan locks exited 0: {out}"


def test_coverage_quality_findings_stay_advisory_exit_zero(tmp_path):
    """The other half of the ruling must survive: UNVISITED etc. warn, never block."""
    _board(
        tmp_path,
        "# cert\n\n## Test Board\n\n| TC01 | UNVISITED |\n",
    )
    rc, out = run(tmp_path)
    assert rc == 0, f"a coverage-quality finding blocked — the advisory ruling was lost: {out}"


def test_a_repo_with_no_cert_board_is_silent_and_green(tmp_path):
    rc, out = run(tmp_path)
    assert rc == 0
    assert out.strip() == "", f"advisory noise on a repo with no boards: {out!r}"


def test_a_bogus_flag_still_exits_zero(tmp_path):
    """Anti-pattern 91: argparse exits 2 on unknown flags unless guarded; under warn_only that
    was a fleet-wide blocking red. The mix-up exit must not have reopened this."""
    rc, _ = run(tmp_path, "--bogus-flag")
    assert rc == 0


def test_the_crash_path_still_exits_zero(tmp_path):
    """A hostile root must degrade to the could-not-evaluate line, never a traceback exit."""
    rc, _ = run(tmp_path / "does-not-exist")
    assert rc == 0
