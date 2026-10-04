"""The sixth Stop cause reviews every authored file, and reads the session's own commits.

W-ea06749b (trade-intelligence 01M3QCYB7JKX): the cause counted only a code-suffix allowlist and
learnt authorship only from Edit-family tool calls, so `docs/OPERATIONS.md`, `.env.example` and
`.gitignore` were pushed with no review and nothing objected. The operator ruled it "not
acceptable … it must be prevented".
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "final_gate_stop.py"
_spec = importlib.util.spec_from_file_location("final_gate_stop_every_file", _HOOK)
fgs = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(fgs)

T = 1_800_000_000


def _iso(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.UTC).isoformat()


def _git(repo: Path, *args: str, env: dict | None = None) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    ).stdout


def _repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    (r / "seed").write_text("seed")
    _git(r, "add", "seed")
    _git(r, "commit", "-qm", "seed")
    return r


def _commit_at(repo: Path, rel: str, when: int) -> str:
    """Commit `rel` with committer time `when`; return what `git commit` printed."""
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"written by a heredoc at {when}")
    _git(repo, "add", rel)
    env = {**os.environ, "GIT_COMMITTER_DATE": f"@{when}", "GIT_AUTHOR_DATE": f"@{when}"}
    return _git(repo, "commit", "-m", f"add {rel}", env=env)


def _bash(call_id: str, command: str, ts: float) -> dict:
    return {
        "type": "assistant",
        "timestamp": _iso(ts),
        "message": {
            "content": [
                {"type": "tool_use", "id": call_id, "name": "Bash", "input": {"command": command}}
            ]
        },
    }


def _result(call_id: str, text: str, ts: float, *, as_list: bool = False) -> dict:
    body: object = [{"type": "text", "text": text}] if as_list else text
    return {
        "type": "user",
        "timestamp": _iso(ts),
        "message": {"content": [{"type": "tool_result", "tool_use_id": call_id, "content": body}]},
    }


def _transcript(tmp_path: Path, entries: list[dict]) -> str:
    t = tmp_path / "t.jsonl"
    t.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return str(t)


# --- 1. every file counts ------------------------------------------------------------------------


def test_non_code_files_now_count():
    authored = {
        "docs/OPERATIONS.md": T,
        ".env.example": T,
        ".gitignore": T,
        "Dockerfile": T,
        "site/index.html": T,
        "src/a.py": T,
    }
    assert fgs._unreviewed_code_file_names(authored, None) == sorted(authored)


def test_ledgers_and_fabrik_state_are_exempt():
    authored = dict.fromkeys(fgs._ROUTINE_GOVERNANCE, T)
    authored |= {
        ".fabrik/work/W-0a1b2c3d.json": T,
        ".fabrik/plan-locks/x.json": T,
        ".claude/worktrees/agent-2/CHANGELOG.md": T,
        ".claude/worktrees/agent-2/.fabrik/work/W-1.json": T,
        "docs/notes.md": T,
    }
    assert fgs._unreviewed_code_file_names(authored, None) == ["docs/notes.md"]
    # a ledger's NAME elsewhere in the tree is not the ledger
    assert not fgs._review_exempt("docs/sub/CHANGELOG.md")
    assert not fgs._review_exempt("fabrik/x.md")


# --- 2. the session's own commits ---------------------------------------------------------------


def test_session_commits_reads_every_bash_result_and_no_other_tool(tmp_path: Path):
    """Every `[branch sha]` line a BASH call printed is a candidate, with that call's start and end;
    the command text is never parsed (three review rounds each found a shell shape a regex
    misread). Whether a candidate is the session's own commit is `_commit_files`'s question."""
    read_use = {
        "type": "assistant",
        "timestamp": _iso(T + 70),
        "message": {
            "content": [
                {"type": "tool_use", "id": "r1", "name": "Read", "input": {"file_path": "/x/l"}}
            ]
        },
    }
    path = _transcript(
        tmp_path,
        [
            _bash("c1", "cd /x && git commit -m 'add notes' -- docs/n.md", T),
            _result("c1", "[master abc1234] add notes\n 1 file changed\n", T + 2),
            _bash("c3", 'OUT="$(git -C "/x y" commit -F msg)"', T + 20),
            _result("c3", "[detached HEAD 9a8b7c6] list form\n", T + 21, as_list=True),
            _bash("c4", "git \\\n  commit --allow-empty -m root", T + 30),
            _result("c4", "[main (root-commit) 1111111] root\n", T + 31),
            read_use,  # a Read result is not a Bash call's output
            _result("r1", "[master 3333333] text in a file that was read\n", T + 71),
        ],
    )
    files, commits = fgs._session_authorship(path, tmp_path)
    assert files == {}
    assert commits == [
        ("abc1234", T, T + 2),
        ("9a8b7c6", T + 20, T + 21),
        ("1111111", T + 30, T + 31),
    ]


def test_a_displayed_commit_made_before_the_call_is_not_mine(tmp_path: Path):
    """The attribution is git's own clock, not the command text: a sibling's commit a command of
    ours merely PRINTS was created before that command started."""
    repo = _repo(tmp_path)
    now = int(time.time())
    sibling = _commit_at(repo, "sibling.md", now - 600).split("]")[0].split()[-1]
    mine = _commit_at(repo, "mine.md", now - 95).split("]")[0].split()[-1]
    commits = [(sibling, now - 100, now - 90), (mine, now - 100, now - 90)]
    assert fgs._unreviewed_spontaneous_files(None, {}, now - 3600, None, repo, commits) == [
        "mine.md"
    ]


def _windows_rec(lo: float, hi: float) -> dict:
    return {
        "command": "fabrik-review-scoped",
        "state": "done",
        "started_epoch": lo,
        "updated_ts": hi,
        "covered": [[lo, hi]],
    }


def test_bash_written_commit_with_no_window_is_unreviewed(tmp_path: Path):
    repo = _repo(tmp_path)
    now = int(time.time())
    printed = _commit_at(repo, ".env.example", now - 30)
    sha = printed.split("]")[0].split()[-1]
    names = fgs._unreviewed_spontaneous_files(
        None, {}, now - 3600, None, repo, [(sha, now - 31, now - 29)]
    )
    assert names == [".env.example"]


def test_commit_within_the_grace_of_a_close_is_presumed_reviewed(tmp_path: Path):
    """edit → review → close → commit: the commit lands after the close, inside the grace."""
    repo = _repo(tmp_path)
    now = int(time.time())
    printed = _commit_at(repo, "docs/OPERATIONS.md", now - 30)
    sha = printed.split("]")[0].split()[-1]
    rec = _windows_rec(now - 1200, now - 600)  # closed 10 minutes before the commit
    names = fgs._unreviewed_spontaneous_files(
        rec, {}, now - 7200, None, repo, [(sha, now - 31, now - 29)]
    )
    assert names == []


def test_commit_long_after_the_last_close_is_unreviewed(tmp_path: Path):
    """The reported session: commands earlier in the day, the commit 46 minutes after the last
    close. The first cut ("any window before the commit") passed it whole."""
    repo = _repo(tmp_path)
    now = int(time.time())
    printed = _commit_at(repo, ".env.example", now - 30)
    sha = printed.split("]")[0].split()[-1]
    rec = _windows_rec(now - 4000, now - 30 - 46 * 60)
    names = fgs._unreviewed_spontaneous_files(
        rec, {}, now - 7200, None, repo, [(sha, now - 31, now - 29)]
    )
    assert names == [".env.example"]


def test_a_running_reviews_surface_exempts_a_committed_file(tmp_path: Path, monkeypatch):
    """T5.2 for the second source: a review started AFTER the commit names it in its surface."""
    repo = _repo(tmp_path)
    now = int(time.time())
    printed = _commit_at(repo, ".env.example", now - 600)
    sha = printed.split("]")[0].split()[-1]
    monkeypatch.setattr(fgs, "_stale_bound_s", lambda: None)
    rec = {
        "command": "fabrik-review-scoped",
        "state": "running",
        "started_epoch": now - 60,
        "updated_ts": now,
        "surface": "the commit of .env.example",
    }
    commits = [(sha, now - 601, now - 599)]
    assert fgs._unreviewed_spontaneous_files(rec, {}, now - 7200, "s", repo, commits) == []
    rec["surface"] = "something else"
    assert fgs._unreviewed_spontaneous_files(rec, {}, now - 7200, "s", repo, commits) == [
        ".env.example"
    ]


def test_an_ignored_file_is_not_shipped_work(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / ".gitignore").write_text(".env\nscratch/\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-qm", "ignore")
    now = int(time.time())
    for rel in (".env", "scratch/notes.md", "docs/real.md"):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text("x")
    authored = {".env": now, "scratch/notes.md": now, "docs/real.md": now}
    assert fgs._unreviewed_spontaneous_files(None, authored, now - 3600, None, repo) == [
        "docs/real.md"
    ]


def test_commit_outside_its_time_bounds_is_not_mine(tmp_path: Path):
    repo = _repo(tmp_path)
    now = int(time.time())
    old = _commit_at(repo, "old.md", now - 7200).split("]")[0].split()[-1]
    late = _commit_at(repo, "late.md", now - 60).split("]")[0].split()[-1]
    ledger = _commit_at(repo, "CHANGELOG.md", now - 50).split("]")[0].split()[-1]
    mine = _commit_at(repo, "mine.md", now - 40).split("]")[0].split()[-1]
    commits = [
        (old, now - 7201, now - 7199),  # committed before the floor
        (late, now - 3010, now - 3000),  # the call ENDED 49 min before this commit was made
        (ledger, now - 51, now - 49),  # a ledger: exempt
        ("ffffffffffff", now - 41, now - 40),  # a sha this repo lacks (another repo's commit)
        (mine, now - 41, now - 39),  # the one real commit — the foreign sha must not void it
    ]
    assert fgs._unreviewed_spontaneous_files(None, {}, now - 3600, None, repo, commits) == [
        "mine.md"
    ]


def test_the_time_bounds_are_inclusive_at_their_edges(tmp_path: Path):
    """Round 1, B-sonnet: edges no test sat on — the floor, the grace's end, and the call's own
    window, whose start and end are each widened by the clock-skew tolerance, inclusive."""
    repo = _repo(tmp_path)
    now = int(time.time())
    floor = now - 7200
    at_floor = _commit_at(repo, "at_floor.md", floor).split("]")[0].split()[-1]
    echoed = _commit_at(repo, "echoed.md", now - 5000).split("]")[0].split()[-1]
    # the floor itself is inside `[floor, …]`
    assert fgs._unreviewed_spontaneous_files(
        None, {}, floor, None, repo, [(at_floor, floor - 5, floor + 5)]
    ) == ["at_floor.md"]
    # a commit made 83 minutes before the call that printed it started is displayed, not made
    assert (
        fgs._unreviewed_spontaneous_files(
            None, {}, floor, None, repo, [(echoed, now - 20, now - 10)]
        )
        == []
    )
    # a commit exactly at the grace's end is still covered; one second later it is not
    rec = _windows_rec(now - 9000, now - 6000)  # `_review_windows` reads the close as hi + 1
    edge = int(now - 6000 + 1 + fgs._COMMIT_GRACE_S)
    on = _commit_at(repo, "on_edge.md", edge).split("]")[0].split()[-1]
    past = _commit_at(repo, "past_edge.md", edge + 1).split("]")[0].split()[-1]
    commits = [(on, edge - 1, edge + 1), (past, edge, edge + 2)]
    assert fgs._unreviewed_spontaneous_files(rec, {}, floor, None, repo, commits) == [
        "past_edge.md"
    ]


def test_the_calls_window_is_inclusive_at_both_ends(tmp_path: Path):
    repo = _repo(tmp_path)
    now = int(time.time())
    skew = int(fgs._CLOCK_SKEW_TOLERANCE_S)
    started, ended = now - 1000, now - 900
    shas = {
        name: _commit_at(repo, f"{name}.md", when).split("]")[0].split()[-1]
        for name, when in (
            ("at_start", started - skew),
            ("before_start", started - skew - 1),
            ("at_end", ended + skew),
            ("after_end", ended + skew + 1),
        )
    }
    commits = [(sha, started, ended) for sha in shas.values()]
    assert fgs._unreviewed_spontaneous_files(None, {}, now - 3600, None, repo, commits) == [
        "at_end.md",
        "at_start.md",
    ]


def test_a_commit_redisplayed_by_a_later_call_is_still_mine(tmp_path: Path):
    """Round 5: the same sha printed by two calls — the one that made it and a later re-display.
    Either order of the two entries must attribute it."""
    repo = _repo(tmp_path)
    now = int(time.time())
    sha = _commit_at(repo, "real.md", now - 100).split("]")[0].split()[-1]
    made, shown = (sha, now - 105, now - 95), (sha, now - 20, now - 10)
    for commits in ([made, shown], [shown, made]):
        assert fgs._unreviewed_spontaneous_files(None, {}, now - 3600, None, repo, commits) == [
            "real.md"
        ]


def test_a_call_ending_exactly_at_the_floor_less_skew_still_counts(tmp_path: Path):
    """Round 5: the pre-filter's own edge — `ended + skew == floor` is inside, like the floor."""
    repo = _repo(tmp_path)
    now = int(time.time())
    floor = now - 3600
    skew = int(fgs._CLOCK_SKEW_TOLERANCE_S)
    sha = _commit_at(repo, "edge.md", floor).split("]")[0].split()[-1]
    commits = [(sha, floor - 10, floor - skew)]
    assert fgs._unreviewed_spontaneous_files(None, {}, floor, None, repo, commits) == ["edge.md"]


def test_a_call_straddling_the_floor_keeps_a_commit_made_after_it(tmp_path: Path):
    """Round 6: the pre-filter reads the call's END — a long call that began before the floor
    and committed after it is still in scope."""
    repo = _repo(tmp_path)
    now = int(time.time())
    floor = now - 3600
    sha = _commit_at(repo, "straddle.md", floor + 10).split("]")[0].split()[-1]
    commits = [(sha, floor - 100, floor + 50)]
    assert fgs._unreviewed_spontaneous_files(None, {}, floor, None, repo, commits) == [
        "straddle.md"
    ]


def test_a_file_committed_twice_is_judged_by_its_latest_commit(tmp_path: Path):
    """Round 6: two commits of one file, the first reviewed and the second not. The LATEST commit
    decides, whichever order git lists the two shas in — so both orders are tried."""
    repo = _repo(tmp_path)
    now = int(time.time())
    early = _commit_at(repo, "shared.md", now - 4500).split("]")[0].split()[-1]
    # `_commit_files` lists the shas sorted, so make the LATE sha sort first: git then visits the
    # early commit last, and only a max() — not a last-write — keeps the late time
    for k in range(64):
        (repo / "shared.md").write_text(f"late variant {k}")
        _git(repo, "add", "shared.md")
        env = {
            **os.environ,
            "GIT_COMMITTER_DATE": f"@{now - 30}",
            "GIT_AUTHOR_DATE": f"@{now - 30}",
        }
        late = _git(repo, "commit", "-m", f"late {k}", env=env).split("]")[0].split()[-1]
        if late < early:
            break
        _git(repo, "reset", "-q", "--hard", "HEAD~1")
    assert late < early
    rec = _windows_rec(
        now - 5000, now - 4000
    )  # covers the early commit; its grace ends long before the late one
    for commits in (
        [(early, now - 4505, now - 4495), (late, now - 35, now - 25)],
        [(late, now - 35, now - 25), (early, now - 4505, now - 4495)],
    ):
        assert fgs._unreviewed_spontaneous_files(rec, {}, now - 6000, None, repo, commits) == [
            "shared.md"
        ]


def test_a_call_with_an_unreadable_time_attributes_nothing(tmp_path: Path):
    """Round 4: with the start unreadable, `git log` printing a commit three hours old claimed it.
    A wrong claim BLOCKS a session for work it never did, so unknown here means "not mine"."""
    repo = _repo(tmp_path)
    now = int(time.time())
    old = _commit_at(repo, "old.md", now - 3 * 3600).split("]")[0].split()[-1]
    new = _commit_at(repo, "new.md", now - 40).split("]")[0].split()[-1]
    commits = [(old, 0, now - 5), (new, now - 50, 0), (new, 0, 0)]
    assert fgs._unreviewed_spontaneous_files(None, {}, now - 6 * 3600, None, repo, commits) == []


# --- 3. end to end ------------------------------------------------------------------------------


def test_main_blocks_a_bash_only_session(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "final_gate.py").write_text(
        "import json\nprint(json.dumps({'status': 'success', 'failing_checks': []}))\n"
    )
    _git(repo, "add", "scripts/final_gate.py")
    _git(repo, "commit", "-qm", "gate")
    sid = f"s_every_file_{os.getpid()}"
    bl = Path(tempfile.gettempdir()) / f"fabrik-gate-baseline-{sid}.json"
    ctr = Path(tempfile.gettempdir()) / f"fabrik-gate-stop-{sid}.attempts"
    ctr.unlink(missing_ok=True)
    bl.write_text("[]")
    now = int(time.time())
    printed = _commit_at(repo, "src/a.py", now + 1)
    transcript = _transcript(
        tmp_path,
        [
            _bash("w1", "cat > src/a.py <<'EOF'\nprint(1)\nEOF", now),
            _bash("w2", "git add src/a.py && git commit -m 'add src/a.py'", now + 1),
            _result("w2", printed, now + 2),
        ],
    )
    run_dir = tmp_path / "runs"
    run_dir.mkdir()
    try:
        proc = subprocess.run(
            [sys.executable, str(_HOOK)],
            input=json.dumps(
                {
                    "session_id": sid,
                    "cwd": str(repo),
                    "transcript_path": transcript,
                    "hook_event_name": "Stop",
                }
            ),
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "COMMAND_RUN_DIR": str(run_dir)},
        )
    finally:
        bl.unlink(missing_ok=True)
        ctr.unlink(missing_ok=True)
    out = proc.stdout
    assert "UNREVIEWED SPONTANEOUS WORK" in out, (out, proc.stderr[-2000:])
    assert "src/a.py" in out, out
