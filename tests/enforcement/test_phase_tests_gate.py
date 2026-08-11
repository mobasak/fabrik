"""Behavior Contract tests for check_phase_tests.py (plan-2 Phase C).

Fixture = a real throwaway git repo per test: a plan with bulleted Given rows, an active lock
with baseline_commit, and commits shaping the window. The script is run as a subprocess from the
fixture root (it reads Path.cwd()), so these are end-to-end behavior tests, not unit shims.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "enforcement" / "check_phase_tests.py"
ENFORCE_DIR = SCRIPT.parent


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    assert r.returncode == 0, f"git {args}: {r.stderr}"
    return r.stdout.strip()


def _run(repo: Path) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, cwd=repo,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(ENFORCE_DIR)},
    )
    return r.returncode, r.stdout + r.stderr


def _repo(tmp_path: Path, given_rows: int = 2) -> tuple[Path, str]:
    repo = tmp_path / "proj"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    plan_dir = repo / "docs/development/plans"
    plan_dir.mkdir(parents=True)
    rows = "\n".join(
        f"- **Given** state {i}, **When** action, **Then** outcome {i}" for i in range(given_rows)
    )
    (plan_dir / "p.md").write_text(f"# Plan\n\nStatus: IN-PROGRESS\n\n## Behavior Contract\n{rows}\n")
    (repo / "src").mkdir()
    (repo / "src/app.py").write_text("A = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "baseline")
    baseline = _git(repo, "rev-parse", "HEAD")
    locks = repo / ".fabrik/plan-locks"
    locks.mkdir(parents=True)
    (locks / "p.json").write_text(json.dumps({
        "plan": "docs/development/plans/p.md", "status": "active",
        "baseline_commit": baseline, "owned_paths": ["src/", "tests/"],
    }))
    return repo, baseline


def test_declared_rows_source_changes_zero_tests_warns(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    (repo / "src/app.py").write_text("A = 2\nB = 3\n")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-qm", "behavior shipped, no tests")
    rc, out = _run(repo)
    assert rc == 0, out  # ADVISORY: exit 0 even when warning
    assert "WARNING" in out and "ZERO test changes" in out, out
    assert "declared:" in out, out  # the rows are listed for the reviewer


def test_tests_accompanying_the_window_silences(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    (repo / "src/app.py").write_text("A = 2\n")
    t = repo / "tests"
    t.mkdir()
    (t / "test_app.py").write_text("def test_a():\n    assert True\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "behavior + tests")
    rc, out = _run(repo)
    assert rc == 0 and "WARNING" not in out, out


def test_docs_only_window_is_silent(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    (repo / "README.md").write_text("docs only\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "docs only")
    rc, out = _run(repo)
    assert rc == 0 and "WARNING" not in out, out


def test_no_declared_rows_is_silent_by_construction(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path, given_rows=0)
    (repo / "src/app.py").write_text("A = 2\n")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-qm", "no declared behaviors")
    rc, out = _run(repo)
    assert rc == 0 and "WARNING" not in out, out


def test_no_lock_exits_zero_silent(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    (repo / ".fabrik/plan-locks/p.json").unlink()
    (repo / "src/app.py").write_text("A = 2\n")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-qm", "ad-hoc work")
    rc, out = _run(repo)
    assert rc == 0 and "WARNING" not in out, out


def test_released_lock_is_ignored(tmp_path: Path) -> None:
    repo, base = _repo(tmp_path)
    lock = repo / ".fabrik/plan-locks/p.json"
    d = json.loads(lock.read_text())
    d["status"] = "released"
    lock.write_text(json.dumps(d))
    (repo / "src/app.py").write_text("A = 2\n")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-qm", "post-release work")
    rc, out = _run(repo)
    assert rc == 0 and "WARNING" not in out, out


def test_broken_lock_json_fails_soft(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    (repo / ".fabrik/plan-locks/p.json").write_text("{not json")
    (repo / "src/app.py").write_text("A = 2\n")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-qm", "broken lock")
    rc, out = _run(repo)
    assert rc == 0, out  # an advisory never breaks a commit


def test_deleted_test_does_not_satisfy_accompaniment(tmp_path: Path) -> None:
    # Review finding (live-reproduced): a window that DELETES a test while shipping source must
    # WARN — a deleted tests/ path in the unfiltered diff must never count as accompaniment.
    repo = tmp_path / "proj"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    plan_dir = repo / "docs/development/plans"
    plan_dir.mkdir(parents=True)
    (plan_dir / "p.md").write_text(
        "# Plan\n\n## Behavior Contract\n- **Given** s, **When** a, **Then** o\n")
    (repo / "src").mkdir()
    (repo / "src/app.py").write_text("A = 1\n")
    t = repo / "tests"
    t.mkdir()
    (t / "test_app.py").write_text("def test_a():\n    assert True\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "baseline with a test")
    baseline = _git(repo, "rev-parse", "HEAD")
    locks = repo / ".fabrik/plan-locks"
    locks.mkdir(parents=True)
    (locks / "p.json").write_text(json.dumps({
        "plan": "docs/development/plans/p.md", "status": "active",
        "baseline_commit": baseline, "owned_paths": ["src/", "tests/"]}))
    (repo / "src/app.py").write_text("A = 2\n")
    (t / "test_app.py").unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "ship behavior, DELETE the test")
    rc, out = _run(repo)
    assert rc == 0, out
    assert "WARNING" in out and "ZERO test changes" in out, out


def test_absolute_plan_path_in_lock_is_confined(tmp_path: Path) -> None:
    # Review finding: PROJECT_ROOT / "/abs/path" discards the root — a lock pointing outside the
    # repo must be ignored, never read.
    repo, _ = _repo(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("- **Given** leaked, **When** read, **Then** bad\n")
    lock = repo / ".fabrik/plan-locks/p.json"
    d = json.loads(lock.read_text())
    d["plan"] = str(outside)  # absolute, escapes the repo
    lock.write_text(json.dumps(d))
    (repo / "src/app.py").write_text("A = 2\n")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-qm", "source change")
    rc, out = _run(repo)
    assert rc == 0, out
    assert "leaked" not in out and "WARNING" not in out, out


def test_string_owned_paths_scopes_not_chars(tmp_path: Path) -> None:
    # Review finding (live-reproduced): a hand-edited scalar `"owned_paths": "src/"` iterated
    # CHARACTERS, matched nothing, and silently swallowed the WARN — fail-open on the gate's
    # own core promise. A string must scope like a one-element list.
    repo, _ = _repo(tmp_path)
    lock = repo / ".fabrik/plan-locks/p.json"
    d = json.loads(lock.read_text())
    d["owned_paths"] = "src/"  # scalar, not a list
    lock.write_text(json.dumps(d))
    (repo / "src/app.py").write_text("A = 2\n")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-qm", "behavior shipped, no tests, scalar owned_paths")
    rc, out = _run(repo)
    assert rc == 0, out
    assert "WARNING" in out and "ZERO test changes" in out, out


def test_non_dict_lock_json_does_not_abort_other_locks(tmp_path: Path) -> None:
    # Review finding (live-reproduced): one valid-JSON-but-not-a-dict lock file raised out of
    # _active_locks and silently disabled checking for EVERY other active lock. The bad file
    # must be skipped in isolation; the good lock's WARN must still fire.
    repo, _ = _repo(tmp_path)
    (repo / ".fabrik/plan-locks/aaa-bad.json").write_text("[]")  # sorts BEFORE p.json
    (repo / "src/app.py").write_text("A = 2\n")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-qm", "behavior shipped, no tests, bad sibling lock")
    rc, out = _run(repo)
    assert rc == 0, out
    assert "WARNING" in out and "ZERO test changes" in out, out
    assert "fail-soft" not in out, out


def test_illustrative_given_outside_contract_not_counted(tmp_path: Path) -> None:
    # Review finding: GIVEN_ROW_RE must be scoped to Behavior-Contract regions like its SSOT
    # consumer (check_plan_tickets scopes to _section) — an illustrative Given bullet in prose
    # must not mint a phantom declared row.
    repo, _ = _repo(tmp_path, given_rows=0)
    plan = repo / "docs/development/plans/p.md"
    plan.write_text(
        "# Plan\n\nStatus: IN-PROGRESS\n\n## Notes on the row format\n"
        "- **Given** an EXAMPLE row, **When** quoted in prose, **Then** it must not count\n"
    )
    _git(repo, "add", str(plan.relative_to(repo)))
    (repo / "src/app.py").write_text("A = 2\n")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-qm", "source change; plan has only an illustrative row")
    rc, out = _run(repo)
    assert rc == 0 and "WARNING" not in out, out


def test_bold_label_contract_form_counts(tmp_path: Path) -> None:
    # Monolithic plans carry `**Behavior Contract (Phase X):**` bold labels, not ## headings
    # (grounded against the real archived plan-2) — the label + its bullet block must count.
    repo, _ = _repo(tmp_path, given_rows=0)
    plan = repo / "docs/development/plans/p.md"
    plan.write_text(
        "# Plan\n\nStatus: IN-PROGRESS\n\n**Behavior Contract (Phase A):**\n"
        "- **Given** s, **When** a, **Then** o\n\nClosing sequence: prose after the block.\n"
    )
    _git(repo, "add", str(plan.relative_to(repo)))
    (repo / "src/app.py").write_text("A = 2\n")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-qm", "behavior shipped under a bold-label contract, no tests")
    rc, out = _run(repo)
    assert rc == 0, out
    assert "WARNING" in out and "ZERO test changes" in out, out


def test_utility_script_named_test_is_not_accompaniment(tmp_path: Path) -> None:
    # Review finding: `scripts/test_connectivity.py` (a diagnostic utility) must not silently
    # satisfy the WARN — only tests/-dir files and root-level test_*.py count.
    repo, _ = _repo(tmp_path)
    lock = repo / ".fabrik/plan-locks/p.json"
    d = json.loads(lock.read_text())
    d["owned_paths"] = ["src/", "tests/", "scripts/"]
    lock.write_text(json.dumps(d))
    (repo / "src/app.py").write_text("A = 2\n")
    (repo / "scripts").mkdir()
    (repo / "scripts/test_connectivity.py").write_text("print('probe')\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "behavior + a utility script named test_*")
    rc, out = _run(repo)
    assert rc == 0, out
    assert "WARNING" in out and "ZERO test changes" in out, out


def test_nested_bold_label_not_double_counted(tmp_path: Path) -> None:
    # Review finding (live-reproduced): a bold `**Behavior Contract:**` label nested inside a
    # `## Behavior Contract` heading region was scanned twice — 2 distinct rows printed as 3.
    repo, _ = _repo(tmp_path, given_rows=0)
    plan = repo / "docs/development/plans/p.md"
    plan.write_text(
        "# Plan\n\nStatus: IN-PROGRESS\n\n## Behavior Contract\n\n"
        "**Behavior Contract (Phase A):**\n"
        "- **Given** s1, **When** a1, **Then** o1\n"
        "- **Given** s2, **When** a2, **Then** o2\n\n## Next section\n"
    )
    _git(repo, "add", str(plan.relative_to(repo)))
    (repo / "src/app.py").write_text("A = 2\n")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-qm", "behavior under nested contract forms, no tests")
    rc, out = _run(repo)
    assert rc == 0, out
    assert "declares 2 Behavior-Contract row(s)" in out, out


def test_test_adjacent_files_do_not_silence_the_warn(tmp_path: Path) -> None:
    # Review finding (live-reproduced): `tests/data.json` (a fixture) silenced the WARN for a
    # zero-test behavior window. Test-ADJACENT files are not test accompaniment.
    repo, _ = _repo(tmp_path)
    (repo / "src/app.py").write_text("A = 2\n")
    t = repo / "tests"
    t.mkdir()
    (t / "data.json").write_text('{"fixture": true}\n')
    (t / "conftest.py").write_text("import pytest\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "behavior + fixture data + conftest, ZERO real tests")
    rc, out = _run(repo)
    assert rc == 0, out
    assert "WARNING" in out and "ZERO test changes" in out, out


def test_conftest_only_window_is_silent(tmp_path: Path) -> None:
    # The flip side of the three-way split: test-adjacent files are not shipped behavior
    # either — a conftest-only window must not draw a false WARN.
    repo, _ = _repo(tmp_path)
    t = repo / "tests"
    t.mkdir()
    (t / "conftest.py").write_text("import pytest\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "test-infrastructure only")
    rc, out = _run(repo)
    assert rc == 0 and "WARNING" not in out, out


def test_hostile_lock_field_types_isolated_per_lock(tmp_path: Path) -> None:
    # Review finding (live-reproduced): a lock with `"owned_paths": 5` raised inside the loop
    # and the outer except silently suppressed a SIBLING lock's real WARN. Hostile field types
    # must be isolated per lock.
    repo, _ = _repo(tmp_path)
    locks = repo / ".fabrik/plan-locks"
    # sorts BEFORE p.json; baseline is a dict → str() → git error → per-lock skip, not abort
    (locks / "aaa-hostile.json").write_text(json.dumps({
        "plan": "docs/development/plans/p.md", "status": "active",
        "baseline_commit": {"x": 1}, "owned_paths": ["src/"]}))
    (repo / "src/app.py").write_text("A = 2\n")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-qm", "behavior shipped, no tests, hostile sibling lock")
    rc, out = _run(repo)
    assert rc == 0, out
    assert "WARNING" in out and "ZERO test changes" in out, out
    assert "skipping malformed lock" in out, out


def test_non_list_owned_paths_falls_back_to_whole_window(tmp_path: Path) -> None:
    # An int owned_paths must degrade toward WARNING (whole-window fallback), never toward
    # silence or a run-wide abort.
    repo, _ = _repo(tmp_path)
    lock = repo / ".fabrik/plan-locks/p.json"
    d = json.loads(lock.read_text())
    d["owned_paths"] = 5
    lock.write_text(json.dumps(d))
    (repo / "src/app.py").write_text("A = 2\n")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-qm", "behavior shipped, no tests, int owned_paths")
    rc, out = _run(repo)
    assert rc == 0, out
    assert "WARNING" in out and "ZERO test changes" in out, out


def test_sibling_commits_outside_owned_paths_are_scoped_out(tmp_path: Path) -> None:
    # Review finding (whole-plan round): shared-master sibling commits inside the window must not
    # count in EITHER direction — a sibling's untested .py must not WARN this plan, and a
    # sibling's tests/ addition must not mask this plan's own zero-test gap.
    repo, _ = _repo(tmp_path)  # owns src/ and tests/
    # This plan ships behavior in its owned src/ with NO owned tests…
    (repo / "src/app.py").write_text("A = 2\n")
    # …while a SIBLING (outside owned_paths) ships an untested .py AND a test file.
    sib = repo / "sibling"
    sib.mkdir()
    (sib / "worker.py").write_text("W = 1\n")
    (sib / "test_worker.py").write_text("def test_w():\n    assert True\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "mixed window: own behavior + sibling files")
    rc, out = _run(repo)
    assert rc == 0, out
    # The sibling's test file must NOT satisfy accompaniment for THIS plan's source change:
    assert "WARNING" in out and "ZERO test changes" in out, out
