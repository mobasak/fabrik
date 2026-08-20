"""T07 outcome tier — behavior tests (ticket: T07-outcome-tier.md).

Every test isolates KAIZEN_EVENTS_DIR / KAIZEN_STATE_DIR (autouse fixture) so nothing
here ever touches the operator's real ~/.claude/state. Git fixtures pin their commit
dates so the rework window arithmetic is deterministic.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "sysadmin"))

import kaizen_outcomes as ko  # noqa: E402

DASH = "—"


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing in this suite may write the operator's real ~/.claude/state."""
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(tmp_path / "events-env"))
    monkeypatch.setenv("KAIZEN_STATE_DIR", str(tmp_path / "state-env"))


# ── git fixture helpers ───────────────────────────────────────────────────────────────


def _git(repo: Path, *args: str, date: str | None = None) -> None:
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env
    )


def _repo(root: Path, name: str) -> Path:
    repo = root / name
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "fixture@test")
    _git(repo, "config", "user.name", "fixture")
    _git(repo, "config", "commit.gpgsign", "false")
    return repo


def _commit(
    repo: Path,
    fname: str,
    subject: str,
    days_ago: float = 0,
    trailer: bool = True,
    content: str | None = None,
) -> None:
    f = repo / fname
    f.write_text(content if content is not None else f"# {subject}\nx = 1\n", encoding="utf-8")
    _git(repo, "add", fname)
    when = (dt.datetime.now(dt.UTC) - dt.timedelta(days=days_ago)).isoformat()
    msgs = ["-m", subject]
    if trailer:
        msgs += ["-m", "Agent-Role: subagent\nAgent-Context: fixture commit"]
    _git(repo, "commit", "-q", "--no-verify", *msgs, date=when)


def _mtimes(root: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    for p in root.rglob("*"):
        try:
            out[str(p.relative_to(root))] = p.stat().st_mtime_ns
        except OSError:
            pass
    return out


def _events_lines(tmp_path: Path) -> list[dict]:
    rows: list[dict] = []
    ev_dir = tmp_path / "events-env"
    if not ev_dir.is_dir():
        return rows
    for f in ev_dir.glob("*.jsonl"):
        for raw in f.read_text(encoding="utf-8").splitlines():
            if raw.strip():
                rows.append(json.loads(raw))
    return rows


# ── rework_rate ───────────────────────────────────────────────────────────────────────


def test_rework_counts_fix_retouch_within_window(tmp_path: Path) -> None:
    root = tmp_path / "opt"
    repo = _repo(root, "alpha")
    _commit(repo, "a.py", "feat: add a", days_ago=10)
    _commit(repo, "a.py", "fix(a): repair a", days_ago=9)
    overall, per = ko.rework_rate(root=root, days=7)
    assert overall.measurable
    assert overall.numerator == 1
    assert overall.denominator == 2  # denominator always printed
    assert "(1/2" in overall.cell
    assert per[0].numerator == 1 and per[0].denominator == 2


def test_rework_ignores_non_fix_retouch(tmp_path: Path) -> None:
    root = tmp_path / "opt"
    repo = _repo(root, "alpha")
    _commit(repo, "a.py", "feat: add a", days_ago=10)
    _commit(repo, "a.py", "feat: extend a", days_ago=9)
    overall, _ = ko.rework_rate(root=root, days=7)
    assert overall.numerator == 0
    assert overall.denominator == 2


def test_rework_ignores_fix_retouch_outside_window(tmp_path: Path) -> None:
    root = tmp_path / "opt"
    repo = _repo(root, "alpha")
    _commit(repo, "a.py", "feat: add a", days_ago=20)
    _commit(repo, "a.py", "fix(a): late repair", days_ago=10)  # 10 days later > 7-day window
    overall, _ = ko.rework_rate(root=root, days=7)
    assert overall.numerator == 0
    assert overall.denominator == 2


def test_rework_ignores_prose_hotfix_mention(tmp_path: Path) -> None:
    """F2: 'hotfix' must anchor the subject — a docs commit MENTIONING it is not a fix."""
    root = tmp_path / "opt"
    repo = _repo(root, "alpha")
    _commit(repo, "a.py", "feat: add a", days_ago=10)
    _commit(repo, "a.py", "docs: describe the hotfix procedure", days_ago=9)
    overall, _ = ko.rework_rate(root=root, days=7)
    assert overall.numerator == 0
    assert overall.denominator == 2


def test_rework_counts_anchored_hotfix_subject(tmp_path: Path) -> None:
    root = tmp_path / "opt"
    repo = _repo(root, "alpha")
    _commit(repo, "a.py", "feat: add a", days_ago=10)
    _commit(repo, "a.py", "hotfix: emergency patch", days_ago=9)
    overall, _ = ko.rework_rate(root=root, days=7)
    assert overall.numerator == 1
    assert overall.denominator == 2


def test_rework_ignores_hotfix_prefix_words(tmp_path: Path) -> None:
    """F2(r2): 'hotfix' is word-bounded — 'hotfixture:' (and 'hotfixed') are not fixes."""
    root = tmp_path / "opt"
    repo = _repo(root, "alpha")
    _commit(repo, "a.py", "feat: add a", days_ago=10)
    _commit(repo, "a.py", "hotfixture: rename module", days_ago=9)
    overall, _ = ko.rework_rate(root=root, days=7)
    assert overall.numerator == 0
    assert overall.denominator == 2


def test_rework_pure_rename_by_fix_not_counted(tmp_path: Path) -> None:
    """F5: a fix-shaped commit that only RENAMES a file did not rework its content."""
    root = tmp_path / "opt"
    repo = _repo(root, "alpha")
    _commit(repo, "a.py", "feat: add a", days_ago=10)
    _git(repo, "mv", "a.py", "b.py")
    when = (dt.datetime.now(dt.UTC) - dt.timedelta(days=9)).isoformat()
    _git(
        repo,
        "commit",
        "-q",
        "--no-verify",
        "-m",
        "fix(a): relocate module",
        "-m",
        "Agent-Role: subagent\nAgent-Context: fixture commit",
        date=when,
    )
    overall, _ = ko.rework_rate(root=root, days=7)
    assert overall.numerator == 0
    assert overall.denominator == 2


def test_rework_repo_without_trailers_dashes_with_reason(tmp_path: Path) -> None:
    root = tmp_path / "opt"
    repo = _repo(root, "bare")
    _commit(repo, "a.py", "feat: add a", days_ago=10, trailer=False)
    _commit(repo, "a.py", "fix(a): repair", days_ago=9, trailer=False)
    overall, per = ko.rework_rate(root=root, days=7)
    assert per[0].cell == DASH
    assert "trailer" in per[0].reason.lower()
    # F6: absence-of-parse, not absence-of-trailers — a malformed block must not read
    # as "the repo has no trailers" without saying parsing is the boundary.
    assert "parsed" in per[0].reason.lower()
    assert not overall.measurable  # only repo is unmeasured -> honest dash, never a 0


def test_rework_fails_open_on_unreadable_repo(tmp_path: Path) -> None:
    root = tmp_path / "opt"
    broken = root / "broken"
    (broken / ".git").mkdir(parents=True)  # a .git dir with no repo inside
    overall, per = ko.rework_rate(root=root, days=7)
    assert per[0].cell == DASH and per[0].reason
    assert not overall.measurable
    missing, per2 = ko.rework_rate(root=tmp_path / "nope", days=7)
    assert not missing.measurable and per2 == []


# ── fleet_health sweep ────────────────────────────────────────────────────────────────


def test_sweep_runs_in_temp_worktree_and_live_mtimes_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "opt"
    proj = _repo(root, "pilot")
    _commit(proj, "mod.py", "feat: module", content="x = 1\n")
    _repo(root, "other")  # present on disk but NOT configured -> never swept (no heuristics)
    monkeypatch.setenv("KAIZEN_SWEEP_PROJECTS", "pilot")
    before = _mtimes(proj)
    report = ko.run_sweep(root=root)
    assert _mtimes(proj) == before  # the live tree's mtime set is untouched
    assert [r.project for r in report.results] == ["pilot"]
    assert report.results[0].swept and report.results[0].cell == "ok"
    assert report.coverage.numerator == 1 and report.coverage.denominator == 1
    assert any("swept 1/1" in ln for ln in report.lines)
    events = [e for e in _events_lines(tmp_path) if e.get("event") == "fleet_health"]
    assert len(events) == 1 and events[0]["project"] == "pilot"


def test_sweep_uses_head_not_dirty_live_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "opt"
    proj = _repo(root, "pilot")
    _commit(proj, "mod.py", "feat: module", content="x = 1\n")
    (proj / "mod.py").write_text("def broken(:\n", encoding="utf-8")  # dirty + unparseable
    monkeypatch.setenv("KAIZEN_SWEEP_PROJECTS", "pilot")
    report = ko.run_sweep(root=root)
    assert report.results[0].swept and report.results[0].cell == "ok"  # HEAD compiles


def test_sweep_timeout_reports_honest_dash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "opt"
    proj = _repo(root, "slow")
    _commit(proj, "mod.py", "feat: module", content="x = 1\n")
    _commit(proj, "pyproject.toml", "chore: pytest cfg", content="[tool.pytest.ini_options]\n")
    venv_bin = proj / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    fake = venv_bin / "python"
    fake.write_text("#!/bin/sh\nsleep 30\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("KAIZEN_SWEEP_PROJECTS", "slow")
    monkeypatch.setenv("KAIZEN_SWEEP_TIMEOUT_S", "3")
    t0 = time.monotonic()
    report = ko.run_sweep(root=root)
    assert time.monotonic() - t0 < 25  # the budget bound the sweep, not the sleeper
    res = report.results[0]
    assert res.cell == DASH and "timeout" in res.reason.lower()
    assert not res.swept
    assert report.coverage.numerator == 0 and report.coverage.denominator == 1
    assert any(f"the rest {DASH}" in ln for ln in report.lines)
    events = [e for e in _events_lines(tmp_path) if e.get("event") == "fleet_health"]
    assert len(events) == 1  # honest events still land


def test_sweep_timeout_kills_whole_process_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F3: a timed-out check's GRANDCHILDREN must die with it, not outlive the budget."""
    root = tmp_path / "opt"
    proj = _repo(root, "forker")
    _commit(proj, "mod.py", "feat: module", content="x = 1\n")
    _commit(proj, "pyproject.toml", "chore: pytest cfg", content="[tool.pytest.ini_options]\n")
    pidfile = tmp_path / "grandchild.pid"
    selfpidfile = tmp_path / "child.pid"
    venv_bin = proj / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    fake = venv_bin / "python"
    fake.write_text(
        f'#!/bin/sh\nsleep 600 > /dev/null 2>&1 &\necho $! > "{pidfile}"\n'
        f'echo $$ > "{selfpidfile}"\nexec sleep 600\n',
        encoding="utf-8",
    )
    fake.chmod(0o755)
    monkeypatch.setenv("KAIZEN_SWEEP_PROJECTS", "forker")
    monkeypatch.setenv("KAIZEN_SWEEP_TIMEOUT_S", "3")
    report = ko.run_sweep(root=root)
    assert not report.results[0].swept and "timeout" in report.results[0].reason.lower()
    pid = int(pidfile.read_text().strip())
    try:
        dead = False
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                dead = True
                break
            time.sleep(0.1)
        assert dead, "grandchild survived the sweep timeout — process tree not killed"
    finally:
        # F4(r2): a red run must never leak a 600s sleeper — reap BOTH the grandchild
        # and the primary child ($$ survives the exec, so child.pid is the direct child).
        for leftover in (pidfile, selfpidfile):
            with contextlib.suppress(OSError, ValueError):
                os.kill(int(leftover.read_text().strip()), 9)


def test_run_check_bounded_reap_gives_up_on_unreapable_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F1(r2): a D-state child that survives SIGKILL must not hang the sweep — the
    post-kill reap is BOUNDED; on a second timeout the check gives up, fail-open."""

    class FakeProc:
        pid = 4242

        def wait(self, timeout: float | None = None) -> int:
            raise subprocess.TimeoutExpired(cmd="fake-check", timeout=timeout or 0)

    killed: list[int] = []
    monkeypatch.setattr(ko.subprocess, "Popen", lambda *a, **k: FakeProc())
    monkeypatch.setattr(ko.os, "killpg", lambda pid, sig: killed.append(pid))
    t0 = time.monotonic()
    rc = ko._run_check(["fake-check"], timeout=0.2)
    assert time.monotonic() - t0 < 30  # bounded — never a budget-defeating hang
    assert rc == ko.CHECK_UNREAPABLE
    assert killed == [4242]  # the kill was still attempted before giving up


def test_sweep_reports_real_failure_rc_not_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F5(r2): a genuine non-zero rc through the Popen path surfaces as fail (rc=N),
    never conflated with a timeout dash."""
    root = tmp_path / "opt"
    proj = _repo(root, "redproj")
    _commit(proj, "mod.py", "feat: module", content="x = 1\n")
    _commit(proj, "pyproject.toml", "chore: pytest cfg", content="[tool.pytest.ini_options]\n")
    venv_bin = proj / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    fake = venv_bin / "python"
    fake.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("KAIZEN_SWEEP_PROJECTS", "redproj")
    report = ko.run_sweep(root=root)
    res = report.results[0]
    assert res.swept and res.cell == "red (pytest)"
    assert res.checks["pytest"] == "fail (rc=7)"


def test_sweep_only_empty_list_sweeps_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F7: an explicit empty ``only`` list means sweep NOTHING, not fall back to env."""
    monkeypatch.setenv("KAIZEN_SWEEP_PROJECTS", "pilot")
    assert ko.sweep_project_names(only=[]) == []
    report = ko.run_sweep(root=tmp_path / "opt", only=[])
    assert report.results == []
    assert not report.coverage.measurable


def test_sweep_node_project_skipped_with_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "opt"
    proj = _repo(root, "webby")
    _commit(
        proj,
        "package.json",
        "feat: node scaffold",
        content='{"name": "webby", "scripts": {"test": "jest"}}\n',
    )
    monkeypatch.setenv("KAIZEN_SWEEP_PROJECTS", "webby")
    report = ko.run_sweep(root=root)
    res = report.results[0]
    assert res.cell == DASH and "node" in res.reason.lower()
    assert not res.swept


def test_sweep_missing_project_dashes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAIZEN_SWEEP_PROJECTS", "ghost")
    report = ko.run_sweep(root=tmp_path / "opt")
    res = report.results[0]
    assert res.cell == DASH and res.reason
    assert report.coverage.numerator == 0 and report.coverage.denominator == 1


# ── premature_stop + pairs ────────────────────────────────────────────────────────────


def _seed_facts(tmp_path: Path, rows: list[dict]) -> None:
    st = tmp_path / "state-env"
    st.mkdir(parents=True, exist_ok=True)
    with open(st / "derived-facts.jsonl", "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _fact(sid: str, **over: object) -> dict:
    row: dict = {
        "facts_version": 1,
        "sid": sid,
        "day": "2026-08-19",
        # Recent by construction: the store-reading metrics are WINDOWED on last_ts
        # (L7) and a fixed fixture date would silently age out of the window.
        "last_ts": dt.datetime.now(dt.UTC).isoformat(timespec="milliseconds"),
        "events": {},
        "runs": {},
        "stop_causes": {},
    }
    row.update(over)
    return row


def test_premature_stop_reads_stop_block_events_per_session(tmp_path: Path) -> None:
    """F4: session-level — sessions with a premature-cause block over stop-carrying sessions."""
    _seed_facts(
        tmp_path,
        [
            _fact(
                "s1",
                events={"stop_pass": 3, "stop_block": 1},
                stop_causes={"run-record": 1},
            ),
            _fact("s2", events={"stop_pass": 0, "stop_block": 0}),  # no verdicts — excluded
            _fact("s3", events={"stop_pass": 2}),  # verdicts, no premature block
        ],
    )
    prem, causes = ko.premature_stop()
    assert prem.measurable
    assert prem.numerator == 1 and prem.denominator == 2  # sessions, not events
    assert "(1/2" in prem.cell
    assert causes.value == {"run-record": 1}


def test_gate_red_stop_block_is_not_premature(tmp_path: Path) -> None:
    """F4: a stop_block whose cause is NOT premature (e.g. an uncommitted-work hold)
    must not count — only T06's PREMATURE_CAUSES do."""
    _seed_facts(
        tmp_path,
        [_fact("s1", events={"stop_block": 1}, stop_causes={"uncommitted": 1})],
    )
    prem, causes = ko.premature_stop()
    assert prem.measurable
    assert prem.numerator == 0 and prem.denominator == 1
    assert causes.value == {"uncommitted": 1}  # the histogram keeps the FULL cause mix


def test_premature_stop_missing_store_dashes(tmp_path: Path) -> None:
    prem, causes = ko.premature_stop()
    assert not prem.measurable and prem.cell == DASH
    assert not causes.measurable


def test_stop_block_causes_dashes_with_premature_when_no_stop_verdicts(tmp_path: Path) -> None:
    """F1: a paired counter must dash WITH its metric — never fabricate "clean" while
    premature_stop is unmeasurable."""
    _seed_facts(tmp_path, [_fact("s1", events={"gate_run": 2}), _fact("s2")])
    prem, causes = ko.premature_stop()
    assert not prem.measurable and prem.cell == DASH
    assert not causes.measurable and causes.cell == DASH
    assert causes.detail == prem.detail  # one shared reason — the pair dashes together


def test_premature_vocab_unavailable_dashes_stops_pair_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F3(r2): a missing PREMATURE_CAUSES vocabulary (older collector on a box
    mid-sync) dashes ONLY the stops pair — the other tiers still run (fail-open,
    never fail-total)."""
    monkeypatch.setattr(ko, "PREMATURE_CAUSES", None)
    _seed_facts(
        tmp_path,
        [_fact("s1", events={"stop_block": 1}, stop_causes={"run-record": 1})],
    )
    prem, causes = ko.premature_stop()
    assert not prem.measurable and "vocabulary" in prem.detail
    assert not causes.measurable and causes.detail == prem.detail
    root = tmp_path / "opt"
    repo = _repo(root, "alpha")
    _commit(repo, "a.py", "feat: add a", days_ago=10)
    _commit(repo, "a.py", "fix(a): repair a", days_ago=9)
    overall, _ = ko.rework_rate(root=root, days=7)
    assert overall.measurable  # rework is untouched by the vocabulary hole


def test_stop_block_causes_units_are_events(tmp_path: Path) -> None:
    """F6(r2): the histogram's numerator, denominator AND cell all count EVENTS —
    the cell must never re-label the denominator in session units."""
    _seed_facts(
        tmp_path,
        [_fact("s1", events={"stop_pass": 3}), _fact("s2", events={"stop_pass": 1})],
    )
    prem, causes = ko.premature_stop()
    assert causes.measurable
    assert causes.numerator == 0 and causes.denominator == 4  # 4 stop-verdict EVENTS
    assert "4 stop verdicts" in causes.cell  # the cell states the same unit


def _transcript_fact(sid: str = "tr-legacy") -> dict:
    """A T08 backfill row, verbatim shape: event-only fields are DASH strings."""
    return {
        "facts_version": 1,
        "era": "transcript",
        "sid": sid,
        "day": "2026-08-19",
        "events": DASH,
        "gate": DASH,
        "runs": DASH,
        "stop_causes": DASH,
        "death_classes": DASH,
        "lines_total": 10,
        "lines_unclassified": 2,
        "unclassified_reasons": {"unparseable-json": 2},
    }


def test_premature_stop_survives_transcript_era_rows(tmp_path: Path) -> None:
    """T09 wave 2 (confirmed live 2026-08-20): the real store holds era:"transcript"
    rows whose events/stop_causes are DASH strings — _stop_verdicts crashed on them.
    They must be excluded from the read, and the event-era rows still measure."""
    _seed_facts(
        tmp_path,
        [
            _transcript_fact(),
            _fact("s1", events={"stop_pass": 1, "stop_block": 1}, stop_causes={"run-record": 1}),
        ],
    )
    prem, causes = ko.premature_stop()
    assert prem.measurable
    assert prem.numerator == 1 and prem.denominator == 1
    assert causes.value == {"run-record": 1}


def test_review_rounds_survives_transcript_era_rows(tmp_path: Path) -> None:
    """Same class: runs is a DASH string on transcript rows — review_rounds crashed."""
    _seed_facts(tmp_path, [_transcript_fact(), _fact("s1", runs={"rounds_max": 3})])
    rounds = ko.review_rounds()
    assert rounds.measurable
    assert "3.0" in rounds.cell and "n=1" in rounds.cell


def test_review_rounds_pair_from_rows(tmp_path: Path) -> None:
    _seed_facts(
        tmp_path,
        [
            _fact("s1", runs={"rounds_max": 3}),
            _fact("s2", runs={"rounds_max": 0}),
        ],
    )
    rounds = ko.review_rounds()
    assert rounds.measurable
    assert "3.0" in rounds.cell and "n=1" in rounds.cell


# ── registry + authored cron entry ────────────────────────────────────────────────────


def test_registry_registers_three_reciprocal_pairs_alongside_t06(tmp_path: Path) -> None:
    reg = ko.registry()
    for a, b in (
        ("rework_rate", "review_rounds"),
        ("fleet_health", "sweep_coverage"),
        ("premature_stop", "stop_block_causes"),
    ):
        assert reg[a]["counter_metric"] == b
        assert reg[b]["counter_metric"] == a
        assert reg[a]["hash"] and reg[b]["hash"]
    assert "rules_compliance" in reg  # T06's set still loads alongside — one registry


def test_premature_def_cross_references_t06_metric(tmp_path: Path) -> None:
    """F4: the two premature definitions in one registry must name each other."""
    reg = ko.registry()
    assert "premature_stop_rate" in reg["premature_stop"]["formula"]


def test_nightly_cron_entry_authored_not_installed(tmp_path: Path) -> None:
    doc = ko.__doc__ or ""
    assert "T09" in doc  # the installer is named — this module never installs
    assert "stamp" in doc  # wake-proof stamp-check pattern, not a bare nightly slot
    assert re.search(r"^\s*\d+ \* \* \* \*", doc, re.M)  # an hourly catch-up crontab line


# ── review fix-wave: adjudicated findings, red-first ─────────────────────────────────


def test_store_metrics_are_windowed_not_all_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L7: premature_stop / stop_block_causes / review_rounds read only the last
    KAIZEN_OUTCOMES_WINDOW_DAYS days (default 7) — never all-time cumulative."""
    _seed_facts(
        tmp_path,
        [
            _fact(
                "old",
                events={"stop_pass": 1, "stop_block": 1},
                stop_causes={"run-record": 1},
                runs={"rounds_max": 4},
                last_ts="2026-01-01T00:00:00.000+00:00",
            )
        ],
    )
    prem, causes = ko.premature_stop()
    assert not prem.measurable, "a months-old row must fall outside the default window"
    assert not causes.measurable
    assert not ko.review_rounds().measurable
    monkeypatch.setenv("KAIZEN_OUTCOMES_WINDOW_DAYS", "36500")
    prem2, causes2 = ko.premature_stop()
    assert prem2.measurable and causes2.measurable
    assert ko.review_rounds().measurable


def test_windowed_formulas_are_version_bumped() -> None:
    """L7: the window is stated in the formulas — a formula edit is a def-hash
    version bump (the versioned-definitions law)."""
    reg = ko.registry()
    for mid in ("premature_stop", "stop_block_causes", "review_rounds"):
        assert reg[mid]["version"] == 2, mid
        assert "KAIZEN_OUTCOMES_WINDOW_DAYS" in reg[mid]["formula"], mid


def test_rework_survives_delimiter_injection_in_subject(tmp_path: Path) -> None:
    """M4: \\x1e/\\x1f in a commit subject must not corrupt record parsing and
    deflate the metric — mining is NUL-delimited (NUL cannot appear in a subject)."""
    root = tmp_path / "opt"
    repo = _repo(root, "proj")
    _commit(repo, "a.py", "feat: add parser \x1e evil \x1f fields", days_ago=10)
    _commit(repo, "a.py", "fix(parser): repair", days_ago=4, content="x = 2\n")
    r = ko.mine_repo(repo, 7, now=time.time())
    assert r.measurable, r.reason
    assert (r.numerator, r.denominator) == (1, 1), (
        "the injected commit must keep its files and be seen reworked"
    )


def test_sweep_one_survives_tempdir_cleanup_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L2: a CHECK_UNREAPABLE child can hold the temp worktree busy — a cleanup
    error is swallowed (warned), never raised out of sweep_one."""
    import shutil  # noqa: PLC0415
    import tempfile as _tempfile  # noqa: PLC0415

    root = tmp_path / "opt"
    proj = _repo(root, "pilot")
    _commit(proj, "mod.py", "feat: module", content="x = 1\n")
    real_mkdtemp = _tempfile.mkdtemp

    class _FakeTmp:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self._kwargs = kwargs
            self._dir = real_mkdtemp(prefix=str(kwargs.get("prefix", "t")))

        def __enter__(self) -> str:
            return self._dir

        def __exit__(self, *exc: object) -> bool:
            if not self._kwargs.get("ignore_cleanup_errors"):
                raise OSError(16, "device or resource busy")
            shutil.rmtree(self._dir, ignore_errors=True)
            return False

    monkeypatch.setattr(ko.tempfile, "TemporaryDirectory", _FakeTmp)
    res = ko.sweep_one("pilot", root, 120)
    assert res.project == "pilot", "sweep_one must survive a busy temp worktree"
