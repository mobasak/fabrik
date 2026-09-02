# AFTER-EDIT: ../autocommit_pipeline_outputs.sh | ../guard_selection_freshness.py
"""The SHELL wiring of the freshness guard — untested before (review 2026-09-02, finding 9).

The filter's own tests exercise the python; they say nothing about how bash consumes it, and the
bash side is where the dangerous failure lived: `mapfile -t PATHS < <(cmd || fallback)` hides the
helper's exit code, so a helper exiting 0 with no output wiped PATHS to zero — the stage loop ran
zero times and the `${#STAGED[@]} -ne ${#PATHS[@]}` check compared 0 against 0 and stayed silent.
`test_golden_parity.py:1338` is already named for that failure class and could not catch this
because it only greps for literal strings, so these drive the REAL contract instead.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
GUARD = SCRIPTS / "guard_selection_freshness.py"


def _run(script: str, repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, cwd=str(repo),
    )


def _repo(tmp_path: Path, committed_date: str, worktree_date: str) -> tuple[Path, str]:
    r = tmp_path / "r"
    rel = "docs/reference/kilo/TASK_SUBAGENT_SELECTION.md"
    (r / "docs/reference/kilo").mkdir(parents=True)
    for cmd in (["init", "-q", "."], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        subprocess.run(["git", "-C", str(r), *cmd], check=True)
    (r / rel).write_text(f"Last refresh: {committed_date}\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(r), "add", rel], check=True)
    subprocess.run(["git", "-C", str(r), "commit", "-qm", "base"], check=True)
    (r / rel).write_text(f"Last refresh: {worktree_date}\n", encoding="utf-8")
    return r, rel


# the exact wiring from autocommit_pipeline_outputs.sh, with the alert stubbed
WIRING = f"""
set -u
FABRIK_ROOT="$PWD"
SELF_DIR="{SCRIPTS}"
PATHS=(%s)
_GUARD_OUT="$(mktemp)"
_GUARD_N=${{#PATHS[@]}}
if GUARD_REPO="$FABRIK_ROOT" python3 "$SELF_DIR/guard_selection_freshness.py" "${{PATHS[@]}}" > "$_GUARD_OUT"; then
  mapfile -t _GUARD_KEPT < "$_GUARD_OUT"
  _GUARD_DROPPED=$(( _GUARD_N - ${{#_GUARD_KEPT[@]}} ))
  if [ "$_GUARD_DROPPED" -gt 0 ]; then
    echo "DROPPED=${{_GUARD_DROPPED}}/${{_GUARD_N}}"
  fi
  PATHS=("${{_GUARD_KEPT[@]}}")
else
  echo "GUARD_FAILED_KEEPING_ALL"
fi
rm -f "$_GUARD_OUT"
echo "FINAL_COUNT=${{#PATHS[@]}}"
"""


def test_a_dropped_path_is_reported_not_silent(tmp_path):
    """The whole point: a drop must be VISIBLE. Silence here is the round-16 class."""
    r, rel = _repo(tmp_path, committed_date="2026-08-29", worktree_date="2026-08-19")
    other = "docs/reference/kilo/OTHER.md"
    (r / other).write_text("no date\n", encoding="utf-8")
    p = _run(WIRING % f'"{rel}" "{other}"', r)
    assert "DROPPED=1/2" in p.stdout, p.stdout + p.stderr
    assert "FINAL_COUNT=1" in p.stdout, "the undated path must still be staged"


def test_all_dropped_does_not_masquerade_as_an_empty_stage_list(tmp_path):
    """THE bug: helper exits 0 having dropped everything. The old `||` fallback never fired and
    PATHS silently became empty, so the script blamed the stage list for a guard decision."""
    r, rel = _repo(tmp_path, committed_date="2026-08-29", worktree_date="2026-08-19")
    p = _run(WIRING % f'"{rel}"', r)
    assert "DROPPED=1/1" in p.stdout, "an all-dropped run must SAY the guard dropped them"
    assert "FINAL_COUNT=0" in p.stdout
    assert "GUARD_FAILED_KEEPING_ALL" not in p.stdout, "exit 0 is not a helper failure"


def test_a_helper_crash_keeps_the_unfiltered_list(tmp_path):
    """Fail-open: a broken guard must never stop the pipeline publishing."""
    r, rel = _repo(tmp_path, committed_date="2026-08-29", worktree_date="2026-08-19")
    broken = WIRING.replace(
        'python3 "$SELF_DIR/guard_selection_freshness.py"', "python3 -c 'import sys;sys.exit(3)'"
    )
    p = _run(broken % f'"{rel}"', r)
    assert "GUARD_FAILED_KEEPING_ALL" in p.stdout
    assert "FINAL_COUNT=1" in p.stdout, "the crash path must KEEP every candidate"


def test_paths_with_spaces_survive_the_round_trip(tmp_path):
    r, rel = _repo(tmp_path, committed_date="2026-08-29", worktree_date="2026-09-02")
    spaced = "docs/reference/kilo/has space.md"
    (r / spaced).write_text("no date\n", encoding="utf-8")
    p = _run(WIRING % f'"{rel}" "{spaced}"', r)
    assert "FINAL_COUNT=2" in p.stdout, p.stdout + p.stderr


def test_guard_reads_the_repo_it_is_told_to_not_a_hardcoded_root(tmp_path):
    """Finding 1: a hardcoded /opt/fabrik made the guard inspect the WRONG repo and fail open —
    the original incident reproduced WITH the fix installed."""
    r, rel = _repo(tmp_path, committed_date="2026-08-29", worktree_date="2026-08-19")
    p = subprocess.run(
        [sys.executable, str(GUARD), rel],
        capture_output=True, text=True, cwd=str(r), env={"PATH": "/usr/bin:/bin"},
    )
    assert rel not in p.stdout.split(), "with CWD as the root the regression must be caught"
    assert "DROP" in p.stderr
