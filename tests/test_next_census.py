"""Behavior contract for ``scripts/sysadmin/next_census.py`` (plan
2026-09-25-plan-1-work-store-single-tracker, ticket T06).

The census reads Claude Code transcripts (``*.jsonl``, one per session, one level under
``--root``), extracts every line of an assistant text block that starts ``NEXT:``, classifies it
with ``work.classify_next`` (never a re-implementation), and reports the fleet's own § Why this
exists measurement plus the store's Validation V5 reading. Every test builds its own throwaway
``--root`` tree and, for V5, a throwaway git repo under ``tmp_path`` — never the real
``~/.claude/projects``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "sysadmin" / "next_census.py"
WORK_SCRIPT = REPO / "scripts" / "work.py"


def _env(tmp_path: Path) -> dict[str, str]:
    for sub in ("home", "tmp"):
        (tmp_path / sub).mkdir(exist_ok=True)
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path / "home"),
        "TMPDIR": str(tmp_path / "tmp"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }


def _run(
    args: list[str], env: dict[str, str], timeout: float = 30
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def _assistant_entry(text: str, *, sidechain: bool = False) -> dict:
    return {
        "type": "assistant",
        "isSidechain": sidechain,
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }


def _user_entry(text: str) -> dict:
    return {
        "type": "user",
        "isSidechain": False,
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
    }


def _write_transcript(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")


def _project_dir_name(path: Path) -> str:
    """Mirrors ``next_census._dir_name_for_path`` — a path separator becomes ``-``. Kept as a
    one-line fixture helper (naming glue), never a re-implementation of the logic under test."""
    return str(path.resolve()).replace(os.sep, "-")


def _lines(stdout: str) -> list[str]:
    return [line for line in stdout.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Behavior Contract row 1 — the classes line, all five, over the session denominator
# ---------------------------------------------------------------------------


def test_classes_line_all_five_over_session_denominator(tmp_path: Path) -> None:
    root = tmp_path / "root"
    repo_dir = root / "-opt-alpha"
    _write_transcript(
        repo_dir / "session1.jsonl",
        [
            _assistant_entry("NEXT: W-12345678 keep going with the audit"),
            _assistant_entry("NEXT: none — terminal"),
        ],
    )
    _write_transcript(
        repo_dir / "session2.jsonl",
        [
            _assistant_entry("NEXT: operator decision: start W-00000000 now"),
            _assistant_entry("NEXT: BLOCKED: waiting on infra"),
            _assistant_entry("NEXT: write the changelog entry"),
        ],
    )
    env = _env(tmp_path)
    result = _run(["--root", str(root), "--since", "7"], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    assert lines[0] == (
        "next: 5 lines over 2 sessions — names-item 1 · none 1 · operator-decision 1 · "
        "blocked 1 · free-text 1"
    )


# ---------------------------------------------------------------------------
# Behavior Contract row 2 — sessions per repo, gated on thread_anchor._is_anchor
# ---------------------------------------------------------------------------


def test_sessions_per_repo_only_counts_accepted_anchors(tmp_path: Path) -> None:
    root = tmp_path / "root"
    anchored_repo = root / "-opt-projA"
    plain_repo = root / "-opt-projB"
    _write_transcript(
        anchored_repo / "s1.jsonl",
        [
            _assistant_entry(
                "some earlier turn, nothing to do with NEXT\n"
                "NEXT: phase B of the plan — docs/development/plans/2026-09-25-x/T06.md"
            )
        ],
    )
    _write_transcript(
        plain_repo / "s2.jsonl",
        [_assistant_entry("NEXT: tidy the notes")],
    )
    env = _env(tmp_path)
    result = _run(["--root", str(root), "--since", "7"], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    sessions_line = next(ln for ln in lines if ln.startswith("sessions with an accepted"))
    assert sessions_line == "sessions with an accepted free-text NEXT: 1 (projA 1)"


def test_a_next_inside_a_user_message_is_not_counted(tmp_path: Path) -> None:
    root = tmp_path / "root"
    repo_dir = root / "-opt-alpha"
    _write_transcript(
        repo_dir / "session.jsonl",
        [
            _user_entry("NEXT: this is the operator's own line, never the agent's"),
            _assistant_entry("NEXT: write the report"),
        ],
    )
    env = _env(tmp_path)
    result = _run(["--root", str(root), "--since", "7"], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    # only the assistant's own NEXT: counts — 1 line, not 2
    assert lines[0] == (
        "next: 1 lines over 1 sessions — names-item 0 · none 0 · operator-decision 0 · "
        "blocked 0 · free-text 1"
    )


def test_distinct_free_text_counts_unique_values(tmp_path: Path) -> None:
    root = tmp_path / "root"
    repo_dir = root / "-opt-alpha"
    _write_transcript(
        repo_dir / "session.jsonl",
        [
            _assistant_entry("NEXT: write the report"),
            _assistant_entry("NEXT: write the report"),  # repeated value
            _assistant_entry("NEXT: file the finding"),
        ],
    )
    env = _env(tmp_path)
    result = _run(["--root", str(root), "--since", "7"], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    distinct_line = next(ln for ln in lines if ln.startswith("distinct free-text"))
    assert distinct_line == "distinct free-text: 2"


# ---------------------------------------------------------------------------
# Behavior Contract row 3 — an old file excluded, a bad line skipped, the run never stops
# ---------------------------------------------------------------------------


def test_old_file_excluded_bad_line_skipped_run_continues(tmp_path: Path) -> None:
    root = tmp_path / "root"
    old_repo = root / "-opt-old"
    cur_repo = root / "-opt-current"

    old_path = old_repo / "old.jsonl"
    _write_transcript(old_path, [_assistant_entry("NEXT: this must never be counted")])
    old_ts = time.time() - 30 * 86400
    os.utime(old_path, (old_ts, old_ts))

    cur_path = cur_repo / "cur.jsonl"
    cur_repo.mkdir(parents=True, exist_ok=True)
    with cur_path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(_assistant_entry("NEXT: file the finding")) + "\n")
        fh.write('{"type": "assistant", truncated garbage not json\n')  # the bad line

    env = _env(tmp_path)
    result = _run(["--root", str(root), "--since", "7"], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    # only the current session counts towards the denominator — the old one is excluded
    assert lines[0] == (
        "next: 1 lines over 1 sessions — names-item 0 · none 0 · operator-decision 0 · "
        "blocked 0 · free-text 1"
    )
    skipped_line = next(ln for ln in lines if ln.startswith("skipped:"))
    assert skipped_line == "skipped: 1 file(s)"


def test_missing_root_prints_zero_counts_and_exits_zero(tmp_path: Path) -> None:
    env = _env(tmp_path)
    result = _run(["--root", str(tmp_path / "does-not-exist"), "--since", "7"], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    assert lines[0] == (
        "next: 0 lines over 0 sessions — names-item 0 · none 0 · operator-decision 0 · "
        "blocked 0 · free-text 0"
    )
    assert lines[1] == "distinct free-text: 0"
    assert lines[2] == "sessions with an accepted free-text NEXT: 0"
    assert lines[-1] == "skipped: 0 file(s)"


def test_bad_argument_exits_two(tmp_path: Path) -> None:
    env = _env(tmp_path)
    result = _run(["--since", "not-a-number"], env)
    assert result.returncode == 2


# ---------------------------------------------------------------------------
# Behavior Contract row 4 — Validation V5
# ---------------------------------------------------------------------------


def _git(cwd: Path, env: dict[str, str], *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True, timeout=30
    ).stdout


def _make_repo(tmp_path: Path, env: dict[str, str]) -> Path:
    work = tmp_path / "repo"
    _git(tmp_path, env, "init", "-q", "-b", "main", str(work))
    (work / "README").write_text("seed\n", encoding="utf-8")
    _git(work, env, "add", "README")
    _git(work, env, "commit", "-q", "-m", "seed")
    return work.resolve()


def _init_store(repo: Path, env: dict[str, str]) -> None:
    result = subprocess.run(
        [sys.executable, str(WORK_SCRIPT), "init", "--distributor", "infra"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)


def _write_next_item(repo: Path, item_id: str, *, next_at_days_ago: float = 0.0) -> None:
    store = repo / ".fabrik" / "work"
    store.mkdir(parents=True, exist_ok=True)
    now = time.time() - next_at_days_ago * 86400
    next_at = time.strftime("%Y-%m-%dT%H:%M:%S.000000Z", time.gmtime(now))
    item = {
        "id": item_id,
        "kind": "next",
        "status": "open",
        "title": "a session's current line",
        "next": "a session's current line",
        "next_at": next_at,
        "created": next_at,
        "creator": "s1",
        "owner": "",
        "priority": 3,
        "links": {"session": "s1"},
        "blocked_by": [],
        "evidence": "",
        "note": "",
        "legacy": False,
    }
    (store / f"{item_id}.json").write_text(json.dumps(item), encoding="utf-8")


def _write_live_claim(repo: Path, item_id: str) -> None:
    claims = repo / ".git" / "fabrik-work" / "claims"
    claims.mkdir(parents=True, exist_ok=True)
    claim = {"session": "s1", "agent": "infra", "token": "tok1", "at": time.time(), "lease_s": 3600}
    (claims / f"{item_id}.json").write_text(json.dumps(claim), encoding="utf-8")


def _seed_v5_repo(tmp_path: Path, env: dict[str, str]) -> tuple[Path, Path]:
    """A repo with two open ``kind: next`` items (within 7 days) and two qualifying sessions
    (the transcripts root's project directory, named the way Claude Code names it). Returns
    ``(repo, transcripts_root)``."""
    repo = _make_repo(tmp_path, env)
    _init_store(repo, env)
    _write_next_item(repo, "W-0000aaa1")
    _write_next_item(repo, "W-0000aaa2")

    transcripts_root = tmp_path / "transcripts"
    project_dir = transcripts_root / _project_dir_name(repo)
    anchor_next = "NEXT: phase B of the plan — docs/development/plans/2026-09-25-x/T06.md"
    _write_transcript(project_dir / "s1.jsonl", [_assistant_entry(anchor_next)])
    _write_transcript(project_dir / "s2.jsonl", [_assistant_entry(anchor_next)])
    return repo, transcripts_root


def test_v5_pass_with_live_claim_and_matching_sessions(tmp_path: Path) -> None:
    env = _env(tmp_path)
    repo, transcripts_root = _seed_v5_repo(tmp_path, env)
    _write_live_claim(repo, "W-0000ccc1")

    result = _run(["--root", str(transcripts_root), "--since", "7", "--repo", str(repo)], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    v5_line = next(ln for ln in lines if ln.startswith("V5:"))
    assert v5_line == "V5: PASS"


def test_v5_fail_names_the_claims_bound_with_no_live_claim(tmp_path: Path) -> None:
    env = _env(tmp_path)
    repo, transcripts_root = _seed_v5_repo(tmp_path, env)
    # no claim written this time

    result = _run(["--root", str(transcripts_root), "--since", "7", "--repo", str(repo)], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    v5_line = next(ln for ln in lines if ln.startswith("V5:"))
    assert v5_line == "V5: FAIL — 0 live claims"


def test_v5_no_store_in_a_plain_repo(tmp_path: Path) -> None:
    env = _env(tmp_path)
    repo = _make_repo(tmp_path, env)  # git repo, never `work.py init`
    transcripts_root = tmp_path / "transcripts"
    transcripts_root.mkdir()

    result = _run(["--root", str(transcripts_root), "--since", "7", "--repo", str(repo)], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    v5_line = next(ln for ln in lines if ln.startswith("V5:"))
    assert v5_line == f"V5: no store in {repo}"
