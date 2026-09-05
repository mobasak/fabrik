"""Behavior Contract — Phase 0 of the session-history retention plan
(`docs/development/plans/2026-09-06-plan-1-session-history-retention.md`).

The sampler feeds the ONLY input from which the retention cap is derived, so a defect here
is not a wrong log line — it is a wrong cap, and the cap decides what gets deleted. Three
behaviors, each one a way the derived number could be silently wrong:

  1. it records the real totals for MAIN transcripts;
  2. it EXCLUDES subagent transcripts — they are a separate 7-day tier, and counting them
     into the MAIN series inflates every bound derived from it;
  3. it is idempotent per day — a cron retry, a manual run or an @reboot catch-up must not
     double-count a day into the series.

It also records the LARGEST single file, because the aggregate bound is structurally blind
to a runaway session (50% of all bytes live in the top 14 files).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SAMPLER = REPO / "scripts" / "sysadmin" / "sample_transcript_growth.sh"


def _run(projects: Path, log: Path) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603
        ["bash", str(SAMPLER)],
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(log.parent.parent),
            "CLAUDE_PROJECTS_DIR": str(projects),
            "TRANSCRIPT_GROWTH_LOG": str(log),
        },
        capture_output=True,
        text=True,
        timeout=120,
    )


def _rows(log: Path) -> list[list[str]]:
    lines = log.read_text().strip().splitlines()
    return [ln.split("\t") for ln in lines[1:]]  # drop the header


@pytest.fixture
def tree(tmp_path: Path) -> tuple[Path, Path]:
    """A projects dir shaped like the real one: MAIN transcripts as siblings of a session
    dir that holds the subagent sidechain."""
    projects = tmp_path / "projects"
    (projects / "-opt-alpha").mkdir(parents=True)
    (projects / "-opt-alpha" / "sess-1.jsonl").write_bytes(b"x" * 1000)
    (projects / "-opt-alpha" / "sess-2.jsonl").write_bytes(b"x" * 2500)
    subs = projects / "-opt-alpha" / "sess-1" / "subagents"
    subs.mkdir(parents=True)
    (subs / "agent-aaa.jsonl").write_bytes(b"y" * 9_000_000)  # must NOT be counted
    log = tmp_path / "state" / "growth.tsv"
    log.parent.mkdir(parents=True)
    return projects, log


def test_records_main_totals_and_the_largest_file(tree):
    projects, log = tree
    r = _run(projects, log)
    assert r.returncode == 0, r.stderr
    rows = _rows(log)
    assert len(rows) == 1, rows
    _date, main_bytes, main_files, largest_bytes, largest_path = rows[0]
    assert int(main_bytes) == 3500, "MAIN total must be exactly the two main transcripts"
    assert int(main_files) == 2
    assert int(largest_bytes) == 2500, "largest MAIN file, not the largest file on disk"
    assert largest_path.endswith("sess-2.jsonl")


def test_subagent_transcripts_are_excluded_from_the_main_series(tree):
    """The 9 MB subagent sidechain dwarfs both MAIN files. If the predicate ever loses
    `! -path '*/subagents/*'`, every bound derived from this series inflates ~2500x and
    nothing else would notice — the log would still look plausible."""
    projects, log = tree
    _run(projects, log)
    _date, main_bytes, main_files, largest_bytes, _ = _rows(log)[0]
    assert int(main_bytes) == 3500, "subagent bytes leaked into the MAIN total"
    assert int(main_files) == 2, "subagent files leaked into the MAIN count"
    assert int(largest_bytes) == 2500, "the largest-file column picked up a subagent file"


def test_second_run_same_day_is_a_no_op(tree):
    """Idempotence by DATE. A cron retry or an @reboot catch-up must not append a second
    row for today — the cap is derived from this series, so a duplicated day biases it."""
    projects, log = tree
    _run(projects, log)
    (projects / "-opt-alpha" / "sess-3.jsonl").write_bytes(b"z" * 5000)  # tree changed
    second = _run(projects, log)
    assert second.returncode == 0, second.stderr
    assert "already recorded" in second.stdout
    rows = _rows(log)
    assert len(rows) == 1, f"a second row was appended for the same day: {rows}"
    assert int(rows[0][1]) == 3500, "the existing row must not be rewritten either"


def test_missing_projects_dir_fails_loudly(tree, tmp_path):
    """A typo'd or absent projects dir must NOT record a zero row — a 0-byte day would be
    indistinguishable from a real quiet day and would drag the derived cap down.

    ⚠️ The absent path is under a WRITABLE parent, deliberately. An earlier version passed
    `/nonexistent-projects-dir`, where any mutant that tried to create the directory failed
    on PERMISSIONS instead — so the test went green against a sampler mutated to record a
    false zero, and proved nothing. Mutation caught it; the path had to become one a mutant
    could actually create."""
    _projects, log = tree
    absent = tmp_path / "not-created-yet"
    assert not absent.exists()
    r = _run(absent, log)
    assert r.returncode != 0, "must exit non-zero rather than record a false zero"
    assert not log.exists() or _rows(log) == [], "no row may be written"
