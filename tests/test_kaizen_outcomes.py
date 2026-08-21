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
        # Recent by construction: since W5-1 there is ONE window — the last
        # KAIZEN_OUTCOMES_WINDOW_DAYS calendar DAYS including today (LOCAL days
        # since W6-5, matching the store's dt.date.today() stamps) — and both the
        # value population and the attribution guard read it; fixed fixture dates
        # would silently age out of it. first_ts today = born in-window (W6-2):
        # a first-ever row without it is bootstrap-excluded.
        "day": dt.date.today().isoformat(),
        "first_ts": dt.datetime.now(dt.UTC).isoformat(timespec="milliseconds"),
        "last_ts": dt.datetime.now(dt.UTC).isoformat(timespec="milliseconds"),
        "events": {},
        "events_unattributed": {},
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
    _seed_facts(
        tmp_path,
        [_transcript_fact(), _fact("s1", events={"round": 3}, runs={"rounds_max": 3})],
    )
    rounds = ko.review_rounds()
    assert rounds.measurable
    assert "3.0" in rounds.cell and "n=1" in rounds.cell


def test_review_rounds_pair_from_rows(tmp_path: Path) -> None:
    _seed_facts(
        tmp_path,
        [
            _fact("s1", events={"round": 3}, runs={"rounds_max": 3}),
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
    """L7 (window redefined by W5-1): premature_stop / stop_block_causes /
    review_rounds read only the last KAIZEN_OUTCOMES_WINDOW_DAYS calendar DAYS
    including today (one definition, day-scoped) — never all-time cumulative."""
    _seed_facts(
        tmp_path,
        [
            _fact(
                "old",
                day="2026-01-01",
                events={"stop_pass": 1, "stop_block": 1, "round": 4},
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
    # review_rounds: v2 added the window (L7), v3 the attribution floor (W2-F2),
    # v4 the window-scoped knowability guard (S3), v5 the windowed-delta guard on
    # the 20% floor (W4-1), v6 the one-window day-scoped delta population (W5-1),
    # v7 the LOCAL day window + attributed bootstrap symmetry (W6-2/W6-5), v8 the
    # DAY-scoped published day point + the visible baseline smear (W7-1/W7-5).
    # The stops pair took S3 at v3, W4-1 at v4, W5-1 at v5, W6 at v6, W7 at v7.
    for mid, ver in (("premature_stop", 7), ("stop_block_causes", 7), ("review_rounds", 8)):
        assert reg[mid]["version"] == ver, mid
        assert "KAIZEN_OUTCOMES_WINDOW_DAYS" in reg[mid]["formula"], mid
        assert "LOCAL calendar days" in reg[mid]["formula"], mid
        assert "DAY-scoped" in reg[mid]["formula"], mid
        assert "smear" in reg[mid]["formula"], mid


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


# ── fix-wave 2 (whole-M1 closing sweep, red-first) ───────────────────────────────────


def test_review_rounds_dashes_when_round_family_unattributable(tmp_path: Path) -> None:
    """W2-F2 (guard windowed by W4-1): a mean over n=1 attributed round-carrying
    sessions while the WINDOW's round mass sits in the unknown stream is fabricated
    precision — 1 vs 47 is below the 20% floor, dash with the attribution reason.
    (The unknown accumulator has a pre-window baseline row so its in-window delta
    is knowable — a first-ever in-window row is the W5-3 bootstrap case.)"""
    baseline_day = (dt.datetime.now(dt.UTC).date() - dt.timedelta(days=30)).isoformat()
    _seed_facts(
        tmp_path,
        [
            _fact("s1", runs={"rounds_max": 3}, events={"round": 1}),
            _fact("unknown", day=baseline_day, last_ts=None, events={}, events_unattributed={}),
            _fact(
                "unknown",
                last_ts=None,
                events={},
                events_unattributed={"round": 47},
            ),
        ],
    )
    rounds = ko.review_rounds()
    assert not rounds.measurable, "n=1 attributed vs 47 unknown rounds is below the floor"
    assert rounds.cell == DASH
    assert "unattributable" in rounds.detail


def test_review_rounds_still_measures_when_attribution_is_healthy(tmp_path: Path) -> None:
    """W2-F2 counter-case: no unknown-stream round mass — the mean still publishes."""
    _seed_facts(tmp_path, [_fact("s1", runs={"rounds_max": 3}, events={"round": 3})])
    rounds = ko.review_rounds()
    assert rounds.measurable
    assert "3.0" in rounds.cell and "n=1" in rounds.cell


# ── fix-wave 3 (S3 window-scoped guards + S5 registry pin, red-first) ────────────────
# S3's knowability rule is superseded by W4-1's windowed-delta guard (fix-wave 4):
# the unknown accumulator's rows are day-keyed, so the windowed count is computable.


def test_review_rounds_publishes_when_window_share_meets_floor(tmp_path: Path) -> None:
    """W4-1 (supersedes S3's knowability ratchet): the window's unattributed count
    IS computable from the unknown accumulator's day-keyed per-day deltas — 100
    attributed vs 10 unknown in-window (91%) meets the 20% floor and publishes
    with the share stated, instead of dashing on mere unknown-mass existence."""
    baseline_day = (dt.datetime.now(dt.UTC).date() - dt.timedelta(days=30)).isoformat()
    _seed_facts(
        tmp_path,
        [
            _fact("s1", runs={"rounds_max": 3}, events={"round": 100}),
            _fact("unknown", day=baseline_day, last_ts=None, events={}, events_unattributed={}),
            _fact("unknown", last_ts=None, events={}, events_unattributed={"round": 10}),
        ],
    )
    rounds = ko.review_rounds()
    assert rounds.measurable, "a healthy windowed share must publish — no lifetime ratchet"
    assert "91% attributed" in rounds.detail


def test_review_rounds_heals_when_unknown_mass_is_pre_window(tmp_path: Path) -> None:
    """W4-1 heal direction: last month's unknown round mass is not THIS window's
    mass — the guard heals when attribution improves instead of ratcheting
    permanently dead on the monotone accumulator's lifetime."""
    old_day = (dt.datetime.now(dt.UTC).date() - dt.timedelta(days=30)).isoformat()
    _seed_facts(
        tmp_path,
        [
            _fact("s1", runs={"rounds_max": 3}, events={"round": 1}),
            _fact(
                "unknown",
                day=old_day,
                last_ts=None,
                events={},
                events_unattributed={"round": 470},
            ),
        ],
    )
    rounds = ko.review_rounds()
    assert rounds.measurable, "pre-window unknown mass must not dash the current window"
    assert "100% attributed" in rounds.detail


def test_stops_pair_dashes_when_unknown_holds_stop_mass(tmp_path: Path) -> None:
    """W4-1: premature_stop / stop_block_causes dash together when the WINDOW's
    unknown-stream stop mass swamps the attributed share (below the 20% floor) —
    4 attributed vs 100 unknown is a sliver, not the population."""
    baseline_day = (dt.datetime.now(dt.UTC).date() - dt.timedelta(days=30)).isoformat()
    _seed_facts(
        tmp_path,
        [
            _fact(
                "s1",
                events={"stop_pass": 3, "stop_block": 1},
                stop_causes={"run-record": 1},
            ),
            _fact("unknown", day=baseline_day, last_ts=None, events={}, events_unattributed={}),
            _fact("unknown", last_ts=None, events={}, events_unattributed={"stop_block": 100}),
        ],
    )
    prem, causes = ko.premature_stop()
    assert not prem.measurable and not causes.measurable
    assert "unattributable in the window" in prem.detail
    assert "attribution floor" in prem.detail
    assert causes.detail == prem.detail, "the pair dashes together"


def test_stops_pair_dash_on_pre_v3_unknown_row_in_window(tmp_path: Path) -> None:
    """W4-1 root law: a live-shape v1 unknown row (events_unattributed ABSENT) in
    the window is not a measured 0 — the old guard printed '100% attributed' over a
    store that never measured attribution. The pair dashes with the pre-v3 reason."""
    unk = _fact("unknown", last_ts=None, events={})
    unk.pop("events_unattributed", None)
    _seed_facts(
        tmp_path,
        [
            _fact(
                "s1",
                events={"stop_pass": 3, "stop_block": 1},
                stop_causes={"run-record": 1},
            ),
            unk,
        ],
    )
    prem, causes = ko.premature_stop()
    assert not prem.measurable and not causes.measurable
    assert "pre-v3 rows in window" in prem.detail
    assert causes.detail == prem.detail


def test_registry_pin_no_formula_change_ships_without_a_version_bump() -> None:
    """S5 tripwire: the FULL registry pinned as {id: (version, def_hash)}. ANY
    formula/population edit changes the def hash and fails this test loudly — the
    editor must then BUMP the metric's version and re-pin BOTH values here (the
    versioned-definitions law made mechanical). A version bump without a formula
    edit, or vice versa, is equally caught."""
    pinned = {
        "rules_compliance": (4, "be837b4449c15df7ff7916588350ac20856e9b1af75f2f9ea80e3c16bcd94135"),
        "terminator_spam": (3, "0838226b9136f445aeccb48455a970554f82b3ad6d5a7970e6e8cf65e31a1b59"),
        "premature_stop_rate": (
            3,
            "82f20ffd81e26326bc5c3b33051aa295a8c9db5bf2c6168d479579081eeaa1de",
        ),
        "first_attempt_gate_pass": (
            3,
            "30b2fe4c2c4756f5ed2aec49f44c91e65f8b1835ad53250b15d10216316d3e25",
        ),
        "gate_failure_taxonomy": (
            3,
            "23f016ae60247ce930fc538a7514d71202a8eec7bdfd83329bddeaaca11a8678",
        ),
        "rule_activation": (3, "1c3ea2cbe3ed7475763a0f03c1b1a5022fc7485acca48d7563eac2f04a3d84c9"),
        "unclassified_rate": (
            3,
            "fdb59d0957a0ee826018bb69ef4faffda3f213f1324f05d645eec396f468d2c4",
        ),
        "hole_count": (3, "3e8a9a9f518e04e865431476fcebad9d4e104fa5b3d8f59fbb9e411d08d41439"),
        "death_occurrences": (
            1,
            "b728c7b15f7caeb5ae55bbdc5e2207ae3000b2290ecb37c3a46dcd72228c048b",
        ),
        "death_classes": (1, "4344dc33b44011e212fdac04c9e3d75572acfdb6f3e5c9766ad1d774117541c3"),
        "rework_rate": (1, "3fd774a5a3e73e32f0fb7ecec4c1419721f5c5f2148fda9b78a65ca89f8767f5"),
        "review_rounds": (8, "ff47289ff93d8f45504df4bc15b13484f492140a8f6e3e444810581cab526068"),
        "fleet_health": (1, "f6c8ff227fe9be5504d83287da354cd991b3ca5ed447a3c50ef3f8c35095951a"),
        "sweep_coverage": (1, "624645a089b459e6e6955fdd7773472eff3377e5038d0c15eb3d53dd6329e7d0"),
        "premature_stop": (7, "b9f5df0cd455b441882ce704a35328dfe2c2cc0c2b7066135b013f48bb5c6a9f"),
        "stop_block_causes": (
            7,
            "8bd63f606989310eb85269cb80df174fdd1728597b0fef6edc3bd9150470c9fd",
        ),
    }
    live = {mid: (d["version"], d["hash"]) for mid, d in ko.registry().items()}
    assert live == pinned, (
        "registry drift: a metric's formula/population changed — bump its version "
        "and re-pin (id, version, hash) here in the SAME change"
    )


# ── fix-wave 5 (W5: like-with-like windowed operands, red-first) ─────────────────────


def _days_ago(n: int) -> str:
    # LOCAL days (W6-5) — the store's day stamps are dt.date.today() locals.
    return (dt.date.today() - dt.timedelta(days=n)).isoformat()


def test_stops_pair_guard_operands_are_windowed_deltas_like_for_like(tmp_path: Path) -> None:
    """W5-1 (the round-5 probe): a 60-day session's LIFETIME cumulative events must
    not vouch for the window — the attributed operand is its in-window GROWTH (0
    here), summed from the same day-scoped delta rows the value uses. With 0 truly
    windowed attributed verdicts against 5 in-window unknown-stream verdicts the
    pair dashes below the floor — never a published share built from lifetime
    mass."""
    _seed_facts(
        tmp_path,
        [
            _fact("long", day=_days_ago(60), events={"stop_pass": 60}),
            _fact("long", events={"stop_pass": 60}),  # today: NO in-window growth
            _fact("unknown", day=_days_ago(60), last_ts=None, events={}, events_unattributed={}),
            _fact("unknown", last_ts=None, events={}, events_unattributed={"stop_block": 5}),
        ],
    )
    prem, causes = ko.premature_stop()
    assert not prem.measurable and not causes.measurable, (
        "0 windowed attributed verdicts vs 5 unknown-stream verdicts must dash — "
        "a lifetime cumulative count is not the window's attributed operand"
    )
    assert "unattributable in the window" in prem.detail
    assert "0 attributed" in prem.detail
    assert causes.detail == prem.detail


def test_review_rounds_population_is_in_window_growth(tmp_path: Path) -> None:
    """W5-1: the VALUE population moves to the same windowed delta rows — a 60-day
    session with no in-window round growth is not this window's round-carrying
    session (its 60 lifetime rounds must not enter the mean); the fresh session
    alone defines the value."""
    _seed_facts(
        tmp_path,
        [
            _fact("long", day=_days_ago(60), events={"round": 60}, runs={"rounds_max": 60}),
            _fact("long", events={"round": 60}, runs={"rounds_max": 60}),  # no growth
            _fact("fresh", events={"round": 2}, runs={"rounds_max": 2}),
        ],
    )
    rounds = ko.review_rounds()
    assert rounds.measurable
    assert "2.0" in rounds.cell and "n=1" in rounds.cell, (
        "only the session whose round family GREW in the window is population"
    )


def test_outcome_metrics_dash_on_derivation_gap_never_knowable_zero(tmp_path: Path) -> None:
    """W5-1 (#5): a window containing NO derived delta rows at all is a DERIVATION
    gap (the daily cron slept) — unmeasurable with the stated reason, never a
    knowable-0 publish."""
    old_ts = "2026-01-01T00:00:00.000+00:00"
    _seed_facts(
        tmp_path,
        [
            _fact(
                "s1",
                day="2026-01-01",
                last_ts=old_ts,
                events={"stop_pass": 2, "round": 2},
                runs={"rounds_max": 2},
            )
        ],
    )
    prem, causes = ko.premature_stop()
    assert not prem.measurable and not causes.measurable
    assert "no derivation in window" in prem.detail
    assert causes.detail == prem.detail
    rounds = ko.review_rounds()
    assert not rounds.measurable
    assert "no derivation in window" in rounds.detail


def test_stops_pair_dash_names_shrink_not_pre_v3(tmp_path: Path) -> None:
    """W5-2 (#2): a shrunk unknown accumulator (an in-window row went backwards
    against its baseline) must dash with the SHRINK cause — the wave-4 guard
    printed the blanket 'pre-v3 rows in window' claim for every unknowable case."""
    _seed_facts(
        tmp_path,
        [
            _fact("s1", events={"stop_pass": 3, "stop_block": 1}, stop_causes={"run-record": 1}),
            _fact(
                "unknown",
                day=_days_ago(30),
                last_ts=None,
                events={},
                events_unattributed={"stop_block": 50},
            ),
            _fact("unknown", last_ts=None, events={}, events_unattributed={"stop_block": 40}),
        ],
    )
    prem, causes = ko.premature_stop()
    assert not prem.measurable and not causes.measurable
    assert "shrank" in prem.detail, "the TRUE cause — the accumulator went backwards"
    assert "pre-v3" not in prem.detail
    assert causes.detail == prem.detail


def test_stops_pair_bootstrap_window_dashes_with_honest_reason(tmp_path: Path) -> None:
    """W5-3 (#4): the store's FIRST unknown derivation landing in-window dumps
    lifetime backlog on one day — the split is unknowable, so the pair dashes
    (fail-closed) with the HONEST bootstrap reason, not a floor/pre-v3 claim."""
    _seed_facts(
        tmp_path,
        [
            _fact("s1", events={"stop_pass": 3, "stop_block": 1}, stop_causes={"run-record": 1}),
            _fact("unknown", last_ts=None, events={}, events_unattributed={"stop_block": 2}),
        ],
    )
    prem, causes = ko.premature_stop()
    assert not prem.measurable and not causes.measurable, (
        "a bootstrap window is expected unmeasurable — even a floor-passing share "
        "could be all pre-window backlog"
    )
    assert (
        "bootstrap window: the unknown accumulator's first derivation carries pre-window backlog"
    ) in prem.detail
    assert causes.detail == prem.detail


def test_stops_pair_states_the_share_when_knowable(tmp_path: Path) -> None:
    """S3 counter-direction: zero unknown-stream stop events — the window's
    attribution share IS knowable (100% attributed) and the pair publishes with the
    share stated."""
    _seed_facts(
        tmp_path,
        [
            _fact(
                "s1",
                events={"stop_pass": 3, "stop_block": 1},
                stop_causes={"run-record": 1},
            )
        ],
    )
    prem, causes = ko.premature_stop()
    assert prem.measurable and causes.measurable
    assert "100% attributed" in prem.detail
    assert "100% attributed" in causes.detail


# ── fix-wave 6 (W6: bootstrap symmetry, causes scope, measured reasons, local days) ──


def test_outcome_metrics_exclude_pre_window_bootstrap_rows(tmp_path: Path) -> None:
    """W6-2 (the round-6 probe): a 60-day session whose FIRST-EVER derivation
    lands in-window (delta_of None, family mass > 0, first_ts predating the
    window) dumped lifetime backlog as its 'delta' — bootstrap-unmeasurable: the
    stops pair and review_rounds dash with the bootstrap reason, never
    40.0 (n=1) / 100%."""
    born = (dt.datetime.now(dt.UTC) - dt.timedelta(days=60)).isoformat(timespec="milliseconds")
    _seed_facts(
        tmp_path,
        [
            _fact(
                "sixty",
                first_ts=born,
                events={"stop_pass": 90, "stop_block": 10, "round": 40},
                stop_causes={"run-record": 10},
                runs={"rounds_max": 40},
            )
        ],
    )
    prem, causes = ko.premature_stop()
    assert not prem.measurable and not causes.measurable, (
        "a lifetime dump must never publish as the window's 100%"
    )
    assert "bootstrap" in prem.detail
    assert causes.detail == prem.detail
    rounds = ko.review_rounds()
    assert not rounds.measurable, "40 lifetime rounds must never publish as 40.0 (n=1)"
    assert "bootstrap" in rounds.detail


def test_in_window_born_first_row_is_not_bootstrap(tmp_path: Path) -> None:
    """W6-2 counter-direction: a first-ever row whose first_ts proves the session
    was BORN in-window carries no pre-window backlog — its lifetime IS in-window
    growth, so the steady-state single-derivation session still measures."""
    _seed_facts(
        tmp_path,
        [_fact("fresh", events={"stop_pass": 1, "round": 2}, runs={"rounds_max": 2})],
    )
    prem, _causes = ko.premature_stop()
    assert prem.measurable, "an in-window-born session is real in-window growth"
    rounds = ko.review_rounds()
    assert rounds.measurable and "2.0" in rounds.cell


def test_bootstrap_exclusion_is_counted_when_population_survives(tmp_path: Path) -> None:
    """W6-2: beside a measurable fresh session the metric publishes over the
    survivors and COUNTS the bootstrap exclusion in its detail."""
    born = (dt.datetime.now(dt.UTC) - dt.timedelta(days=60)).isoformat(timespec="milliseconds")
    _seed_facts(
        tmp_path,
        [
            _fact("sixty", first_ts=born, events={"round": 40}, runs={"rounds_max": 40}),
            _fact("fresh", events={"round": 2}, runs={"rounds_max": 2}),
        ],
    )
    rounds = ko.review_rounds()
    assert rounds.measurable
    assert "2.0" in rounds.cell and "n=1" in rounds.cell, (
        "the bootstrap row's 40 lifetime rounds must stay out of the mean"
    )
    assert "bootstrap" in rounds.detail, "the exclusion is counted, never silent"


def test_unprovable_first_ts_with_mass_is_bootstrap_excluded(tmp_path: Path) -> None:
    """W6-2: a first-ever row carrying family mass whose first_ts cannot prove an
    in-window birth (absent/unparseable) is excluded — unprovable is not
    measurable."""
    row = _fact("noft", events={"stop_pass": 5})
    row["first_ts"] = None
    _seed_facts(tmp_path, [row])
    prem, causes = ko.premature_stop()
    assert not prem.measurable and not causes.measurable
    assert "bootstrap" in prem.detail


def test_stop_block_causes_sum_over_verdict_bearing_rows_only(tmp_path: Path) -> None:
    """W6-3: a causes-without-verdicts row must not leak into the histogram —
    causes are summed over verdict-bearing rows only, restoring the numerator ⊆
    denominator invariant structurally."""
    _seed_facts(
        tmp_path,
        [
            _fact("s1", events={"stop_pass": 1, "stop_block": 1}, stop_causes={"run-record": 1}),
            _fact("weird", events={}, stop_causes={"gate-red": 3}),
        ],
    )
    prem, causes = ko.premature_stop()
    assert prem.measurable and causes.measurable
    assert causes.value == {"run-record": 1}, "the verdict-less row's causes never count"
    assert causes.numerator is not None and causes.denominator is not None
    assert causes.numerator <= causes.denominator, "numerator ⊆ denominator structurally"


def test_empty_window_reason_names_the_measured_cause(tmp_path: Path) -> None:
    """W6-4: the empty-window dash states WHICH measured cause applies — empty
    store · transcript-era-only store · rows exist but none dated in-window —
    never the guessed 'the daily derivation did not run'."""
    prem_a, _ = ko.premature_stop(state=tmp_path / "empty")
    assert "no derivation in window" in prem_a.detail
    assert "store is empty" in prem_a.detail
    assert "did not run" not in prem_a.detail
    tr_state = tmp_path / "tr"
    ko.kc.append_facts(
        [
            {
                "facts_version": 1,
                "sid": "t",
                "day": dt.date.today().isoformat(),
                "era": "transcript",
            }
        ],
        tr_state,
    )
    prem_b, _ = ko.premature_stop(state=tr_state)
    assert "transcript-era" in prem_b.detail
    assert "did not run" not in prem_b.detail
    old_state = tmp_path / "old"
    ko.kc.append_facts(
        [{"facts_version": 1, "sid": "s", "day": "2026-01-01", "events": {"stop_pass": 1}}],
        old_state,
    )
    prem_c, _ = ko.premature_stop(state=old_state)
    assert "none dated in-window" in prem_c.detail
    assert "2026-01-01" in prem_c.detail, "the newest derived day is named"
    assert "did not run" not in prem_c.detail
    rounds_c = ko.review_rounds(state=old_state)
    assert "none dated in-window" in rounds_c.detail


def test_window_day_stamps_are_local_calendar_days() -> None:
    """W6-5: the store's day stamps are LOCAL dates (dt.date.today() at
    derivation) — the window arithmetic must be local too, never a UTC/local mix
    that silently drops the boundary day."""
    import time as _time  # noqa: PLC0415

    utc_now = dt.datetime.now(dt.UTC)
    zone = "Etc/GMT-14" if utc_now.hour >= 12 else "Etc/GMT+12"
    old_tz = os.environ.get("TZ")
    try:
        os.environ["TZ"] = zone
        _time.tzset()
        assert dt.date.today() != dt.datetime.now(dt.UTC).date(), (
            "fixture zone must split local from UTC"
        )
        stamps = ko._window_day_stamps()
        assert stamps[0] == dt.date.today().isoformat(), "the window is LOCAL days"
        assert len(stamps) == ko._window_days()
    finally:
        if old_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old_tz
        _time.tzset()


# ── fix-wave 7 (W7: day-scoped published points, measured reasons, visible smear) ────


def test_outcome_metrics_accept_day_scoped_days(tmp_path: Path) -> None:
    """W7-1: the ``days`` parameter pins the population to exactly those day
    stamps — the publish seam passes the single published day, so each day point
    is that day's delta rows only; the trailing window stays the CLI default."""
    y = _days_ago(1)
    t = dt.date.today().isoformat()
    _seed_facts(
        tmp_path,
        [
            _fact("s1", day=y, events={"round": 3}, runs={"rounds_max": 3}),
            _fact("s2", day=t, events={"round": 9}, runs={"rounds_max": 9}),
        ],
    )
    r_y = ko.review_rounds(days=[y])
    assert r_y.measurable and (r_y.numerator, r_y.denominator) == (3, 1), (
        "the [yesterday] point sees yesterday's growth only"
    )
    r_t = ko.review_rounds(days=[t])
    assert r_t.measurable and (r_t.numerator, r_t.denominator) == (9, 1)
    r_all = ko.review_rounds()
    assert r_all.denominator == 2, "the CLI default remains the trailing window"


def test_empty_window_reason_names_shrink_suppression(tmp_path: Path) -> None:
    """W7-4 (the 3-row shrink probe): in-window rows EXIST but every delta was
    shrink-suppressed (delta_row returned None) — the reason states the measured
    shrink branch, never the misattributed 'none dated in-window'."""
    _seed_facts(
        tmp_path,
        [
            _fact(
                "s1",
                day=_days_ago(10),
                events={"stop_pass": 5, "round": 5},
                runs={"rounds_max": 5},
            ),
            _fact(
                "s1",
                day=_days_ago(1),
                events={"stop_pass": 3, "round": 3},
                runs={"rounds_max": 3},
            ),
            _fact("s1", events={"stop_pass": 2, "round": 2}, runs={"rounds_max": 2}),
        ],
    )
    prem, causes = ko.premature_stop()
    assert not prem.measurable and not causes.measurable
    assert "every delta was suppressed" in prem.detail
    assert "shrink" in prem.detail
    assert "none dated in-window" not in prem.detail
    assert causes.detail == prem.detail
    rounds = ko.review_rounds()
    assert not rounds.measurable
    assert "every delta was suppressed" in rounds.detail


def test_metric_detail_annotates_pre_window_baseline_smear(tmp_path: Path) -> None:
    """W7-5 (adjudicated design-consistent, made VISIBLE): a kept attributed row
    whose baseline (delta_of) predates the window start smears derivation-gap
    growth into it — the metric publishes and the detail counts the smear rows."""
    _seed_facts(
        tmp_path,
        [
            _fact(
                "s1",
                day=_days_ago(10),
                events={"stop_pass": 1, "round": 1},
                runs={"rounds_max": 1},
            ),
            _fact(
                "s1",
                events={"stop_pass": 3, "stop_block": 1, "round": 3},
                stop_causes={"run-record": 1},
                runs={"rounds_max": 3},
            ),
        ],
    )
    rounds = ko.review_rounds()
    assert rounds.measurable
    assert "1 row(s) whose baseline predates the window" in rounds.detail
    assert "derivation-gap smear" in rounds.detail
    prem, causes = ko.premature_stop()
    assert prem.measurable and causes.measurable
    assert "1 row(s) whose baseline predates the window" in prem.detail
    assert "derivation-gap smear" in causes.detail


def test_no_smear_note_when_baselines_are_in_window(tmp_path: Path) -> None:
    """W7-5 counter-direction: an in-window baseline is no smear — no annotation."""
    _seed_facts(
        tmp_path,
        [
            _fact("s1", day=_days_ago(1), events={"round": 1}, runs={"rounds_max": 1}),
            _fact("s1", events={"round": 3}, runs={"rounds_max": 3}),
        ],
    )
    rounds = ko.review_rounds()
    assert rounds.measurable
    assert "smear" not in rounds.detail
