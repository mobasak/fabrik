"""Behavior contract for ``scripts/sysadmin/next_census.py`` (plan
2026-09-25-plan-1-work-store-single-tracker, ticket T06 + its round-1 review fixes).

The census reads Claude Code transcripts (``*.jsonl``, one per session, one level under
``--root``), reads every NEXT value of an assistant text block with the harvest's own
``thread_anchor._next_values``, classifies it with ``work.classify_next`` (never a
re-implementation), and reports the fleet's own § Why this
exists measurement plus the store's Validation V5 reading. Every test builds its own throwaway
``--root`` tree and, for V5, a throwaway git repo under ``tmp_path`` — never the real
``~/.claude/projects``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType

import pytest

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


def _census_module() -> ModuleType:
    """``next_census.py`` imported normally (never by path) — used only to unit-test its pure
    naming helpers directly; every behavioral assertion below still goes through the CLI."""
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import next_census
    finally:
        sys.path.remove(str(SCRIPT.parent))
    return next_census


def _assistant_entry(
    text: str,
    *,
    sidechain: bool = False,
    message_id: str | None = None,
    row_uuid: str | None = None,
) -> dict:
    message: dict = {"role": "assistant", "content": [{"type": "text", "text": text}]}
    if message_id is not None:
        message["id"] = message_id
    entry: dict = {"type": "assistant", "isSidechain": sidechain, "message": message}
    if row_uuid is not None:
        entry["uuid"] = row_uuid
    return entry


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
    """Mirrors ``next_census._dir_name_for_path`` — every non-alphanumeric character becomes
    ``-``. Kept as a one-line fixture helper (naming glue), never a re-implementation of the
    logic under test."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path.resolve()))


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


def test_none_and_blocked_counts_distinguishable_with_unequal_values(tmp_path: Path) -> None:
    """Item 11: a none/blocked label swap must be visible — equal counts (1 and 1) hide it."""
    root = tmp_path / "root"
    repo_dir = root / "-opt-alpha"
    _write_transcript(
        repo_dir / "session.jsonl",
        [
            _assistant_entry("NEXT: none — terminal"),
            _assistant_entry("NEXT: none — nothing else to do"),
            _assistant_entry("NEXT: none — all clear"),
            _assistant_entry("NEXT: BLOCKED: waiting on infra"),
        ],
    )
    env = _env(tmp_path)
    result = _run(["--root", str(root), "--since", "7"], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    assert lines[0] == (
        "next: 4 lines over 1 sessions — names-item 0 · none 3 · operator-decision 0 · "
        "blocked 1 · free-text 0"
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


def test_the_anchor_is_judged_on_the_registers_first_300_characters(tmp_path: Path) -> None:
    # the harvest judges `matches[-1][:300]` (thread_anchor.py cmd_harvest); a NEXT whose anchor
    # shape sits past character 300 is no accepted anchor there, so the census must not count it
    root = tmp_path / "root"
    late = "x" * 310 + " phase B of the plan — docs/development/plans/2026-09-25-x/T06.md"
    _write_transcript(root / "-opt-projA" / "s1.jsonl", [_assistant_entry("NEXT: " + late)])
    early = "phase B of the plan — docs/development/plans/2026-09-25-x/T06.md " + "y" * 310
    _write_transcript(root / "-opt-projB" / "s2.jsonl", [_assistant_entry("NEXT: " + early)])
    result = _run(["--root", str(root), "--since", "7"], _env(tmp_path))
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    sessions_line = next(ln for ln in lines if ln.startswith("sessions with an accepted"))
    assert sessions_line == "sessions with an accepted free-text NEXT: 1 (projB 1)"


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
            _assistant_entry("NEXT: write the report"),  # repeated value, distinct occurrence
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
# Item 1 — the LAST NEXT: a trailing textless turn must not erase an earlier NEXT
# ---------------------------------------------------------------------------


def test_trailing_textless_turn_does_not_erase_the_last_real_next(tmp_path: Path) -> None:
    root = tmp_path / "root"
    repo_dir = root / "-opt-projA"
    _write_transcript(
        repo_dir / "s1.jsonl",
        [
            _assistant_entry(
                "NEXT: phase B of the plan — docs/development/plans/2026-09-25-x/T06.md"
            ),
            {
                "type": "assistant",
                "isSidechain": False,
                "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "t1"}]},
            },
        ],
    )
    env = _env(tmp_path)
    result = _run(["--root", str(root), "--since", "7"], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    sessions_line = next(ln for ln in lines if ln.startswith("sessions with an accepted"))
    # counted exactly once — neither lost to the trailing textless turn nor double-counted
    assert sessions_line == "sessions with an accepted free-text NEXT: 1 (projA 1)"


# ---------------------------------------------------------------------------
# Item 3 — dedup by the row's own uuid (falling back to message.id + text), GLOBAL across files
# ---------------------------------------------------------------------------


def test_dedup_key_is_row_uuid_second_block_of_same_message_still_counts(tmp_path: Path) -> None:
    """Round-2 review (C2-S1/C2-O1): Claude Code writes one JSONL row per content BLOCK, and
    every block of one API message shares that message's ``message.id`` — keying dedup on
    ``message.id`` alone silently dropped a NEXT: line living in a message's SECOND block. Two
    rows, same ``message.id``, DIFFERENT row ``uuid``: both must count (this goes red under a
    message.id-only key — the second row would be treated as a duplicate of the first)."""
    root = tmp_path / "root"
    repo_dir = root / "-opt-alpha"
    _write_transcript(
        repo_dir / "s.jsonl",
        [
            _assistant_entry(
                "NEXT: block one has its own line", message_id="msg-X", row_uuid="uuid-1"
            ),
            _assistant_entry(
                "NEXT: block two carries a different line", message_id="msg-X", row_uuid="uuid-2"
            ),
        ],
    )
    env = _env(tmp_path)
    result = _run(["--root", str(root), "--since", "7"], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    # same message.id, different uuid — both rows are distinct blocks and both count
    assert lines[0] == (
        "next: 2 lines over 1 sessions — names-item 0 · none 0 · operator-decision 0 · "
        "blocked 0 · free-text 2"
    )


def test_dedup_same_message_id_counted_once_distinct_ids_both_counted(tmp_path: Path) -> None:
    root = tmp_path / "root"
    repo_dir = root / "-opt-alpha"
    _write_transcript(
        repo_dir / "s.jsonl",
        [
            _assistant_entry("NEXT: write the report", message_id="msg-A"),
            _assistant_entry("NEXT: write the report", message_id="msg-A"),  # literal duplicate
            _assistant_entry("NEXT: write the report", message_id="msg-B"),  # distinct id
        ],
    )
    env = _env(tmp_path)
    result = _run(["--root", str(root), "--since", "7"], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    # msg-A counted once, msg-B counted once — 2 lines, not 3
    assert lines[0] == (
        "next: 2 lines over 1 sessions — names-item 0 · none 0 · operator-decision 0 · "
        "blocked 0 · free-text 2"
    )


def test_dedup_falls_back_to_row_uuid_when_message_id_absent(tmp_path: Path) -> None:
    root = tmp_path / "root"
    repo_dir = root / "-opt-alpha"
    _write_transcript(
        repo_dir / "s.jsonl",
        [
            _assistant_entry("NEXT: write the report", row_uuid="row-uuid-1"),
            _assistant_entry("NEXT: write the report", row_uuid="row-uuid-1"),
        ],
    )
    env = _env(tmp_path)
    result = _run(["--root", str(root), "--since", "7"], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    assert lines[0] == (
        "next: 1 lines over 1 sessions — names-item 0 · none 0 · operator-decision 0 · "
        "blocked 0 · free-text 1"
    )


def test_dedup_is_global_across_session_files(tmp_path: Path) -> None:
    root = tmp_path / "root"
    repo_a = root / "-opt-alpha"
    repo_b = root / "-opt-beta"
    _write_transcript(
        repo_a / "s1.jsonl",
        [_assistant_entry("NEXT: shared duplicate text", message_id="msg-shared")],
    )
    _write_transcript(
        repo_b / "s2.jsonl",
        [_assistant_entry("NEXT: shared duplicate text", message_id="msg-shared")],
    )
    env = _env(tmp_path)
    result = _run(["--root", str(root), "--since", "7"], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    # the row counts globally only once, and so does its session: the second file holds no
    # assistant text row of its own (a verbatim copy), so it is not a second session
    assert lines[0] == (
        "next: 1 lines over 1 sessions — names-item 0 · none 0 · operator-decision 0 · "
        "blocked 0 · free-text 1"
    )


# ---------------------------------------------------------------------------
# Item 4 — the Claude Code project-directory naming convention
# ---------------------------------------------------------------------------


def test_dir_name_for_path_replaces_every_non_alnum_character() -> None:
    mod = _census_module()
    dir_name = mod._dir_name_for_path(Path("/opt/web-ecommerce-factory"))
    assert dir_name == "-opt-web-ecommerce-factory"
    assert mod._display_repo(dir_name) == "web-ecommerce-factory"
    # a character other than "/" or "-" (an os.sep-only replace would leave it untouched) must
    # ALSO become "-" — this is what actually distinguishes the fix from the old behaviour
    assert mod._dir_name_for_path(Path("/opt/foo_bar.baz")) == "-opt-foo-bar-baz"


# ---------------------------------------------------------------------------
# Item 6 — a line whose JSON parse overflows the recursion limit is skipped, not fatal
# ---------------------------------------------------------------------------


def test_recursion_error_on_parse_is_skipped_not_fatal(tmp_path: Path) -> None:
    root = tmp_path / "root"
    repo_dir = root / "-opt-alpha"
    repo_dir.mkdir(parents=True, exist_ok=True)
    path = repo_dir / "session.jsonl"
    with path.open("wb") as fh:
        fh.write(json.dumps(_assistant_entry("NEXT: file the finding")).encode("utf-8") + b"\n")
        fh.write(b"[" * 200_000 + b"]" * 200_000 + b"\n")
    env = _env(tmp_path)
    result = _run(["--root", str(root), "--since", "7"], env, timeout=90)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    assert lines[0] == (
        "next: 1 lines over 1 sessions — names-item 0 · none 0 · operator-decision 0 · "
        "blocked 0 · free-text 1"
    )
    skipped_line = next(ln for ln in lines if ln.startswith("skipped:"))
    assert skipped_line == "skipped: 0 file(s), 1 line(s)"


# ---------------------------------------------------------------------------
# Item 7 — every non-JSON line counts as skipped (never a silent pre-filtered drop)
# ---------------------------------------------------------------------------


def test_line_without_type_substring_now_counted_as_skipped(tmp_path: Path) -> None:
    root = tmp_path / "root"
    repo_dir = root / "-opt-alpha"
    repo_dir.mkdir(parents=True, exist_ok=True)
    path = repo_dir / "session.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(_assistant_entry("NEXT: file the finding")) + "\n")
        fh.write("totally not json and carries no type field at all\n")
    env = _env(tmp_path)
    result = _run(["--root", str(root), "--since", "7"], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    skipped_line = next(ln for ln in lines if ln.startswith("skipped:"))
    assert skipped_line == "skipped: 0 file(s), 1 line(s)"


def test_clean_run_prints_zero_skipped_both_kinds(tmp_path: Path) -> None:
    root = tmp_path / "root"
    repo_dir = root / "-opt-alpha"
    _write_transcript(repo_dir / "session.jsonl", [_assistant_entry("NEXT: file the finding")])
    env = _env(tmp_path)
    result = _run(["--root", str(root), "--since", "7"], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    assert lines[-1] == "skipped: 0 file(s), 0 line(s)"


def test_skipped_files_counts_an_unreadable_file(tmp_path: Path) -> None:
    """T-L1 (round 2): nothing in the round-1 suite ever produced a nonzero ``skipped_files`` —
    breaking that increment left all 26 tests green. An unreadable transcript beside a readable
    one must count as exactly one skipped FILE, and the readable session still counts fully."""
    if os.geteuid() == 0:
        pytest.skip("root bypasses file permission bits — chmod 000 would not block the read")
    root = tmp_path / "root"
    repo_dir = root / "-opt-alpha"
    unreadable = repo_dir / "bad.jsonl"
    _write_transcript(unreadable, [_assistant_entry("NEXT: must never be read")])
    readable = repo_dir / "ok.jsonl"
    _write_transcript(readable, [_assistant_entry("NEXT: file the finding")])
    unreadable.chmod(0o000)
    try:
        env = _env(tmp_path)
        result = _run(["--root", str(root), "--since", "7"], env)
    finally:
        unreadable.chmod(0o644)  # restore before tmp_path teardown
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    assert lines[0] == (
        "next: 1 lines over 1 sessions — names-item 0 · none 0 · operator-decision 0 · "
        "blocked 0 · free-text 1"
    )
    skipped_line = next(ln for ln in lines if ln.startswith("skipped:"))
    assert skipped_line == "skipped: 1 file(s), 0 line(s)"


# ---------------------------------------------------------------------------
# Item 8 — a NEXT: inside a fenced code block is never read
# ---------------------------------------------------------------------------


def test_next_inside_a_fence_is_skipped_next_outside_still_counts(tmp_path: Path) -> None:
    root = tmp_path / "root"
    repo_dir = root / "-opt-alpha"
    text = (
        "some prose before the fence\n"
        "```\n"
        "NEXT: this is inside a fence and must never count\n"
        "```\n"
        "NEXT: this is outside the fence and must count"
    )
    _write_transcript(repo_dir / "session.jsonl", [_assistant_entry(text)])
    env = _env(tmp_path)
    result = _run(["--root", str(root), "--since", "7"], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    assert lines[0] == (
        "next: 1 lines over 1 sessions — names-item 0 · none 0 · operator-decision 0 · "
        "blocked 0 · free-text 1"
    )


# ---------------------------------------------------------------------------
# Item 10 — --since rejects a non-positive window
# ---------------------------------------------------------------------------


def test_since_arg_rejects_nonpositive_but_since_7_still_works(tmp_path: Path) -> None:
    env = _env(tmp_path)
    root = tmp_path / "root"
    for bad in ("0", "-1", "-7"):
        result = _run(["--root", str(root), "--since", bad], env)
        assert result.returncode == 2, (bad, result.stdout, result.stderr)
    result = _run(["--root", str(root), "--since", "7"], env)
    assert result.returncode == 0, result.stderr


def test_bad_argument_exits_two(tmp_path: Path) -> None:
    env = _env(tmp_path)
    result = _run(["--since", "not-a-number"], env)
    assert result.returncode == 2


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
    assert skipped_line == "skipped: 0 file(s), 1 line(s)"


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
    assert lines[-1] == "skipped: 0 file(s), 0 line(s)"


# ---------------------------------------------------------------------------
# Item 9 — an import failure is reported plainly, never a fake all-zero census
# ---------------------------------------------------------------------------


def _write_mirror_with_broken_work(tmp_path: Path) -> Path:
    """A private copy of ``scripts/sysadmin/next_census.py`` beside a deliberately BROKEN
    ``scripts/work.py`` — the real tree's ``scripts/work.py`` is never touched (DO-NOT)."""
    mirror = tmp_path / "mirror"
    (mirror / "scripts" / "sysadmin").mkdir(parents=True)
    (mirror / "scripts" / "sysadmin" / "next_census.py").write_text(
        SCRIPT.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (mirror / "scripts" / "work.py").write_text(
        "raise RuntimeError('boom - deliberately broken for the test')\n", encoding="utf-8"
    )
    return mirror / "scripts" / "sysadmin" / "next_census.py"


def test_import_failure_reports_plainly_never_a_fake_census(tmp_path: Path) -> None:
    mirror_script = _write_mirror_with_broken_work(tmp_path)
    env = _env(tmp_path)
    result = subprocess.run(
        [sys.executable, str(mirror_script), "--root", str(tmp_path / "root"), "--since", "7"],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout.strip()
    assert out.startswith("census unavailable — work.py import failed: ")
    # never the misleading all-zero census the old code printed on this path
    assert "next: 0 lines over 0 sessions" not in out
    assert "skipped:" not in out


# ---------------------------------------------------------------------------
# Item 5 — streaming read: every count the whole suite above already re-proves unchanged
# (the fix only changes HOW the file is read, never what is counted).
# ---------------------------------------------------------------------------


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
    """``next_at_days_ago`` may be NEGATIVE to place the item in the future (clock skew)."""
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


def _write_closed_marker(repo: Path, item_id: str) -> None:
    """A closed marker written by ANOTHER tree (``tree`` names a path unequal to ``repo``, so
    ``work._is_residue`` returns False and the marker hides ``item_id`` from ``_iter_items``'s
    reading via ``_closed_ids``)."""
    closed_dir = repo / ".git" / "fabrik-work" / "closed"
    closed_dir.mkdir(parents=True, exist_ok=True)
    marker = {
        "agent": "infra",
        "at": time.time(),
        "decision": "",
        "evidence": "",
        "id": item_id,
        "note": "",
        "session": "s2",
        "status": "done",
        "tree": "/nonexistent/some-other-worktree",
    }
    (closed_dir / f"{item_id}.json").write_text(json.dumps(marker), encoding="utf-8")


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
    assert v5_line == "V5: PASS — 2 open next item(s) <= 2 qualifying session(s), 1 live claim(s)"


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


# ---------------------------------------------------------------------------
# Item 2 — V5's window: 2 days ago counts, 8 days ago does not, and (the fix) neither does a
# next_at set 2 days in the FUTURE
# ---------------------------------------------------------------------------


def test_v5_window_excludes_future_and_stale_items(tmp_path: Path) -> None:
    env = _env(tmp_path)
    repo = _make_repo(tmp_path, env)
    _init_store(repo, env)
    _write_next_item(repo, "W-0000ddd1", next_at_days_ago=2)  # counts
    _write_next_item(repo, "W-0000ddd2", next_at_days_ago=8)  # too old, excluded
    _write_next_item(repo, "W-0000ddd3", next_at_days_ago=-2)  # 2 days in the future, excluded
    _write_live_claim(repo, "W-0000ccc1")

    transcripts_root = tmp_path / "transcripts"
    project_dir = transcripts_root / _project_dir_name(repo)
    anchor_next = "NEXT: phase B of the plan — docs/development/plans/2026-09-25-x/T06.md"
    _write_transcript(project_dir / "s1.jsonl", [_assistant_entry(anchor_next)])  # 1 session

    result = _run(["--root", str(transcripts_root), "--since", "7", "--repo", str(repo)], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    v5_line = next(ln for ln in lines if ln.startswith("V5:"))
    # only the 2-days-ago item counts (1) <= 1 qualifying session, with a live claim -> PASS
    assert v5_line == "V5: PASS — 1 open next item(s) <= 1 qualifying session(s), 1 live claim(s)"


# ---------------------------------------------------------------------------
# Item 11 — mutant coverage the round-1 review named directly: the item bound, the isSidechain
# skip, and the closed-id filter
# ---------------------------------------------------------------------------


def test_v5_fail_when_open_items_exceed_sessions_bound(tmp_path: Path) -> None:
    env = _env(tmp_path)
    repo = _make_repo(tmp_path, env)
    _init_store(repo, env)
    _write_next_item(repo, "W-0000eee1")
    _write_next_item(repo, "W-0000eee2")
    _write_live_claim(repo, "W-0000ccc1")

    transcripts_root = tmp_path / "transcripts"
    transcripts_root.mkdir()  # no transcripts at all -> 0 qualifying sessions for this repo

    result = _run(["--root", str(transcripts_root), "--since", "7", "--repo", str(repo)], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    v5_line = next(ln for ln in lines if ln.startswith("V5:"))
    assert v5_line == "V5: FAIL — 2 open next item(s) > 0 qualifying session(s)"


def test_v5_closed_marker_excludes_the_item_even_though_locally_open(tmp_path: Path) -> None:
    env = _env(tmp_path)
    repo = _make_repo(tmp_path, env)
    _init_store(repo, env)
    _write_next_item(repo, "W-0000fff1")  # still reads status "open" in this tree's own file
    _write_closed_marker(repo, "W-0000fff1")  # but another tree already closed it
    _write_live_claim(repo, "W-0000ccc1")

    transcripts_root = tmp_path / "transcripts"
    transcripts_root.mkdir()  # 0 qualifying sessions

    result = _run(["--root", str(transcripts_root), "--since", "7", "--repo", str(repo)], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    v5_line = next(ln for ln in lines if ln.startswith("V5:"))
    # the closed marker hides the only item -> 0 open next items <= 0 sessions, live claim present
    assert v5_line == "V5: PASS — 0 open next item(s) <= 0 qualifying session(s), 1 live claim(s)"


def test_sidechain_row_never_becomes_the_sessions_last_next(tmp_path: Path) -> None:
    root = tmp_path / "root"
    repo_dir = root / "-opt-projA"
    _write_transcript(
        repo_dir / "s1.jsonl",
        [
            _assistant_entry("NEXT: tidy the notes"),  # real turn, free-text, NOT anchor-accepted
            _assistant_entry(
                "NEXT: phase B of the plan — docs/development/plans/2026-09-25-x/T06.md",
                sidechain=True,  # a dispatched subagent's inline row — must be ignored
            ),
        ],
    )
    env = _env(tmp_path)
    result = _run(["--root", str(root), "--since", "7"], env)
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    sessions_line = next(ln for ln in lines if ln.startswith("sessions with an accepted"))
    # the sidechain row's anchor-worthy value must never be read as the session's own last turn
    assert sessions_line == "sessions with an accepted free-text NEXT: 0"


# ---------------------------------------------------------------------------
# W-a9de5fb3 — the census measures what V5 means: the harvest's own NEXT reader, real sessions,
# and the hub's linked-worktree sessions
# ---------------------------------------------------------------------------


def test_harvest_shaped_next_lines_count(tmp_path: Path) -> None:
    """Bold and bulleted footers are NEXT lines to the harvest (thread_anchor._next_values), so the
    census counts them too — a strict `NEXT:`-prefix reader missed both."""
    root = tmp_path / "root"
    _write_transcript(
        root / "-opt-alpha" / "s1.jsonl",
        [
            _assistant_entry("work done\n\n**NEXT:** W-12345678 keep going with the audit"),
            _assistant_entry("more\n\n- NEXT: none — terminal"),
        ],
    )
    result = _run(["--root", str(root), "--since", "7"], _env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert _lines(result.stdout)[0] == (
        "next: 2 lines over 1 sessions — names-item 1 · none 1 · operator-decision 0 · "
        "blocked 0 · free-text 0"
    )


def test_quoted_next_counts_when_no_plain_one_exists(tmp_path: Path) -> None:
    """The harvest takes a quoted `> NEXT:` footer when the turn has no unquoted one; an anchored
    one then qualifies its session."""
    root = tmp_path / "root"
    _write_transcript(
        root / "-opt-alpha" / "s1.jsonl",
        [
            _assistant_entry(
                "> NEXT: phase B of the plan — docs/development/plans/2026-09-25-x/T06.md"
            )
        ],
    )
    result = _run(["--root", str(root), "--since", "7"], _env(tmp_path))
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    assert lines[0].startswith("next: 1 lines over 1 sessions"), lines[0]
    assert "sessions with an accepted free-text NEXT: 1 (alpha 1)" in lines


def test_textless_transcript_is_not_a_session(tmp_path: Path) -> None:
    """A transcript with no main-thread assistant text (a user-only file, a sidechain-only file)
    is not a session for the census denominator."""
    root = tmp_path / "root"
    project = root / "-opt-alpha"
    _write_transcript(project / "real.jsonl", [_assistant_entry("NEXT: none — terminal")])
    _write_transcript(project / "user-only.jsonl", [_user_entry("hello")])
    _write_transcript(
        project / "sidechain-only.jsonl", [_assistant_entry("NEXT: x", sidechain=True)]
    )
    result = _run(["--root", str(root), "--since", "7"], _env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert _lines(result.stdout)[0].startswith("next: 1 lines over 1 sessions"), result.stdout


def test_v5_counts_linked_worktree_sessions(tmp_path: Path) -> None:
    """A session run in a linked worktree of the repo counts toward the repo's V5 bound: hub work
    runs in worktrees whose transcripts live under their own project directories."""
    env = _env(tmp_path)
    repo = _make_repo(tmp_path, env)
    _init_store(repo, env)
    _write_next_item(repo, "W-0000aaa1")
    _write_live_claim(repo, "W-0000ccc1")
    linked = (repo / ".claude" / "worktrees" / "intel").resolve()
    _git(repo, env, "worktree", "add", "-q", "--detach", str(linked))

    transcripts_root = tmp_path / "transcripts"
    anchor_next = "NEXT: phase B of the plan — docs/development/plans/2026-09-25-x/T06.md"
    _write_transcript(
        transcripts_root / _project_dir_name(linked) / "s1.jsonl", [_assistant_entry(anchor_next)]
    )

    result = _run(["--root", str(transcripts_root), "--since", "7", "--repo", str(repo)], env)
    assert result.returncode == 0, result.stderr
    v5_line = next(ln for ln in _lines(result.stdout) if ln.startswith("V5:"))
    assert v5_line == "V5: PASS — 1 open next item(s) <= 1 qualifying session(s), 1 live claim(s)"


def test_session_counts_when_an_earlier_turn_qualified(tmp_path: Path) -> None:
    """V5 counts a session that ENDED AT LEAST ONE TURN on a qualifying NEXT: a later turn ending
    on free text the register ignores leaves the session's open item in place."""
    root = tmp_path / "root"
    _write_transcript(
        root / "-opt-alpha" / "s.jsonl",
        [
            _assistant_entry("NEXT: phase B of the rollout"),
            _user_entry("go on"),
            _assistant_entry("NEXT: tidy the docs"),
        ],
    )
    result = _run(["--root", str(root), "--since", "7"], _env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "sessions with an accepted free-text NEXT: 1 (alpha 1)" in _lines(result.stdout)


def test_mid_turn_next_is_not_what_the_turn_ended_on(tmp_path: Path) -> None:
    """Only a turn's FINAL text is harvested: a NEXT in an earlier row of the same turn — a tool
    result between them is not a new turn — makes no item and no qualifying session."""
    root = tmp_path / "root"
    tool_result = {
        "type": "user",
        "isSidechain": False,
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}],
        },
    }
    _write_transcript(
        root / "-opt-alpha" / "s.jsonl",
        [
            _assistant_entry("Plan:\nNEXT: phase B of the rollout"),
            tool_result,
            _assistant_entry("Done, nothing more."),
        ],
    )
    result = _run(["--root", str(root), "--since", "7"], _env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "sessions with an accepted free-text NEXT: 0" in _lines(result.stdout)


def test_v5_leaves_out_harness_worktree_sessions(tmp_path: Path) -> None:
    """A harness worktree (``agent-<hex>``) is a subagent's tree; no Stop hook harvests there, so
    its sessions never loosen the repo's V5 bound."""
    env = _env(tmp_path)
    repo = _make_repo(tmp_path, env)
    _init_store(repo, env)
    _write_next_item(repo, "W-0000aaa1")
    _write_live_claim(repo, "W-0000ccc1")
    harness = repo / ".claude" / "worktrees" / "agent-0123456789abcdef0"
    transcripts_root = tmp_path / "transcripts"
    anchor_next = "NEXT: phase B of the plan — docs/development/plans/2026-09-25-x/T06.md"
    _write_transcript(
        transcripts_root / _project_dir_name(harness.resolve()) / "s1.jsonl",
        [_assistant_entry(anchor_next)],
    )
    result = _run(["--root", str(transcripts_root), "--since", "7", "--repo", str(repo)], env)
    assert result.returncode == 0, result.stderr
    v5_line = next(ln for ln in _lines(result.stdout) if ln.startswith("V5:"))
    assert v5_line == "V5: FAIL — 1 open next item(s) > 0 qualifying session(s)"


def _linked_store(repo: Path, env: dict[str, str], name: str) -> Path:
    """A registered worker tree ``<repo>/.claude/worktrees/<name>`` holding its own store (the
    store files are uncommitted in the fixture repo, so the config is copied across)."""
    linked = (repo / ".claude" / "worktrees" / name).resolve()
    _git(repo, env, "worktree", "add", "-q", "--detach", str(linked))
    store = linked / ".fabrik" / "work"
    store.mkdir(parents=True, exist_ok=True)
    config = repo / ".fabrik" / "work" / "config.json"
    (store / "config.json").write_text(config.read_text(encoding="utf-8"), encoding="utf-8")
    return linked


def test_v5_counts_worker_tree_items_once_per_id(tmp_path: Path) -> None:
    """A worktree session harvests into its OWN tree's store until the branch merges, so V5 reads
    items from every worker tree too — and an id present in two trees counts once."""
    env = _env(tmp_path)
    repo = _make_repo(tmp_path, env)
    _init_store(repo, env)
    _write_live_claim(repo, "W-0000ccc1")
    linked = _linked_store(repo, env, "intel")
    _write_next_item(linked, "W-0000aaa1")
    _write_next_item(linked, "W-0000aaa2")
    _write_next_item(repo, "W-0000aaa2")
    _write_next_item(repo, "W-0000aaa3")
    result = _run(
        ["--root", str(tmp_path / "transcripts"), "--since", "7", "--repo", str(repo)], env
    )
    assert result.returncode == 0, result.stderr
    v5_line = next(ln for ln in _lines(result.stdout) if ln.startswith("V5:"))
    # aaa1 only in the worker, aaa3 only in main, aaa2 in both — three ids
    assert v5_line == "V5: FAIL — 3 open next item(s) > 0 qualifying session(s)"


def test_v5_from_a_worktree_keys_sessions_on_the_main_checkout(tmp_path: Path) -> None:
    """``--repo`` pointed at a worktree reads the same V5 as the main checkout: sessions are keyed
    on the main checkout's project directory, not the worktree's own."""
    env = _env(tmp_path)
    repo = _make_repo(tmp_path, env)
    _init_store(repo, env)
    _write_live_claim(repo, "W-0000ccc1")
    linked = _linked_store(repo, env, "intel")
    _write_next_item(linked, "W-0000aaa1")
    transcripts_root = tmp_path / "transcripts"
    anchor_next = "NEXT: phase B of the plan — docs/development/plans/2026-09-25-x/T06.md"
    _write_transcript(
        transcripts_root / _project_dir_name(repo) / "s1.jsonl", [_assistant_entry(anchor_next)]
    )
    result = _run(["--root", str(transcripts_root), "--since", "7", "--repo", str(linked)], env)
    assert result.returncode == 0, result.stderr
    v5_line = next(ln for ln in _lines(result.stdout) if ln.startswith("V5:"))
    assert v5_line == "V5: PASS — 1 open next item(s) <= 1 qualifying session(s), 1 live claim(s)"


def _tool_use_row() -> dict:
    return {
        "type": "assistant",
        "isSidechain": False,
        "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "t1"}]},
    }


def _tool_result_row() -> dict:
    return {
        "type": "user",
        "isSidechain": False,
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}],
        },
    }


def _meta_row(text: str) -> dict:
    row = _user_entry(text)
    row["isMeta"] = True
    return row


def test_injected_rows_end_a_turn_only_where_stop_fired(tmp_path: Path) -> None:
    """A row Claude Code injects after a tool result (a loaded skill) is the middle of a turn;
    one written after the assistant's last row (Stop-hook feedback) follows a real Stop."""
    root = tmp_path / "root"
    _write_transcript(
        root / "-opt-alpha" / "s.jsonl",
        [
            _assistant_entry("NEXT: phase B of the rollout"),
            _tool_use_row(),
            _tool_result_row(),
            _meta_row("Base directory for this skill: /x"),
            _assistant_entry("Done, nothing more."),
        ],
    )
    _write_transcript(
        root / "-opt-beta" / "s.jsonl",
        [
            _assistant_entry("NEXT: phase B of the rollout"),
            _meta_row("Stop hook feedback: COMMAND STILL RUNNING"),
            _assistant_entry("Still waiting on the review."),
        ],
    )
    result = _run(["--root", str(root), "--since", "7"], _env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "sessions with an accepted free-text NEXT: 1 (beta 1)" in _lines(result.stdout)


def test_an_image_only_prompt_ends_a_turn(tmp_path: Path) -> None:
    """A prompt with no text block (an image paste) still starts a new turn: the turn before it
    ended where Stop fired, and its final text was judged."""
    root = tmp_path / "root"
    image_prompt = {
        "type": "user",
        "isSidechain": False,
        "message": {"role": "user", "content": [{"type": "image", "source": {}}]},
    }
    _write_transcript(
        root / "-opt-alpha" / "s.jsonl",
        [
            _assistant_entry("NEXT: phase B of the rollout"),
            image_prompt,
            _assistant_entry("NEXT: tidy the docs"),
        ],
    )
    result = _run(["--root", str(root), "--since", "7"], _env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "sessions with an accepted free-text NEXT: 1 (alpha 1)" in _lines(result.stdout)


def test_a_bare_string_row_is_never_the_turns_final_text(tmp_path: Path) -> None:
    """The harvest's final-message reader skips an assistant row whose content is a bare string,
    so the census judges the last LIST-content row of the turn."""
    root = tmp_path / "root"
    string_row = {
        "type": "assistant",
        "isSidechain": False,
        "message": {"role": "assistant", "content": "Done."},
    }
    _write_transcript(
        root / "-opt-alpha" / "s.jsonl",
        [_assistant_entry("NEXT: phase B of the rollout"), string_row],
    )
    result = _run(["--root", str(root), "--since", "7"], _env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "sessions with an accepted free-text NEXT: 1 (alpha 1)" in _lines(result.stdout)


def test_a_resumed_copy_is_not_a_second_session(tmp_path: Path) -> None:
    """A file made only of rows already seen (a resumed session's verbatim copy) adds nothing to
    the session denominator."""
    root = tmp_path / "root"
    row = _assistant_entry("NEXT: none — terminal", row_uuid="u-1")
    _write_transcript(root / "-opt-alpha" / "a.jsonl", [row])
    _write_transcript(root / "-opt-alpha" / "b.jsonl", [row])
    result = _run(["--root", str(root), "--since", "7"], _env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert _lines(result.stdout)[0].startswith("next: 1 lines over 1 sessions"), result.stdout


def test_v5_survives_a_prunable_worker_tree(tmp_path: Path) -> None:
    """A worker tree still registered but deleted from disk is skipped, never a traceback."""
    env = _env(tmp_path)
    repo = _make_repo(tmp_path, env)
    _init_store(repo, env)
    _write_live_claim(repo, "W-0000ccc1")
    linked = _linked_store(repo, env, "intel")
    shutil.rmtree(linked)
    result = _run(
        ["--root", str(tmp_path / "transcripts"), "--since", "7", "--repo", str(repo)], env
    )
    assert result.returncode == 0, result.stderr
    v5_line = next(ln for ln in _lines(result.stdout) if ln.startswith("V5:"))
    assert v5_line == "V5: PASS — 0 open next item(s) <= 0 qualifying session(s), 1 live claim(s)"


def test_v5_an_id_closed_in_any_tree_is_closed(tmp_path: Path) -> None:
    """An item a worker tree has closed (its branch not merged yet) is closed, whatever the main
    checkout's stale copy says."""
    env = _env(tmp_path)
    repo = _make_repo(tmp_path, env)
    _init_store(repo, env)
    _write_live_claim(repo, "W-0000ccc1")
    linked = _linked_store(repo, env, "intel")
    _write_next_item(repo, "W-0000aaa1")
    _write_next_item(linked, "W-0000aaa1")
    item_path = linked / ".fabrik" / "work" / "W-0000aaa1.json"
    item = json.loads(item_path.read_text(encoding="utf-8"))
    item["status"] = "dropped"
    item_path.write_text(json.dumps(item), encoding="utf-8")
    result = _run(
        ["--root", str(tmp_path / "transcripts"), "--since", "7", "--repo", str(repo)], env
    )
    assert result.returncode == 0, result.stderr
    v5_line = next(ln for ln in _lines(result.stdout) if ln.startswith("V5:"))
    assert v5_line == "V5: PASS — 0 open next item(s) <= 0 qualifying session(s), 1 live claim(s)"


def test_v5_sessions_need_a_valid_worker_name(tmp_path: Path) -> None:
    """The sessions side accepts the worker names ``work._workers`` accepts on the items side; a
    directory name no worker can carry adds no sessions."""
    env = _env(tmp_path)
    repo = _make_repo(tmp_path, env)
    _init_store(repo, env)
    _write_next_item(repo, "W-0000aaa1")
    _write_live_claim(repo, "W-0000ccc1")
    odd = repo / ".claude" / "worktrees" / "Bad_Name"
    transcripts_root = tmp_path / "transcripts"
    anchor_next = "NEXT: phase B of the plan — docs/development/plans/2026-09-25-x/T06.md"
    _write_transcript(
        transcripts_root / _project_dir_name(odd) / "s1.jsonl", [_assistant_entry(anchor_next)]
    )
    result = _run(["--root", str(transcripts_root), "--since", "7", "--repo", str(repo)], env)
    assert result.returncode == 0, result.stderr
    v5_line = next(ln for ln in _lines(result.stdout) if ln.startswith("V5:"))
    assert v5_line == "V5: FAIL — 1 open next item(s) > 0 qualifying session(s)"


def test_a_copied_final_row_is_never_judged_as_this_files_turn(tmp_path: Path) -> None:
    """When a turn's final row is a copy of another file's row, that turn belongs to the other
    file: an earlier row of the copy must not stand in as its final text."""
    root = tmp_path / "root"
    copied = _assistant_entry("Done.", row_uuid="u-2")
    _write_transcript(root / "-opt-alpha" / "a.jsonl", [copied])
    _write_transcript(
        root / "-opt-beta" / "b.jsonl",
        [_assistant_entry("NEXT: phase B of the rollout", row_uuid="u-3"), copied],
    )
    result = _run(["--root", str(root), "--since", "7"], _env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "sessions with an accepted free-text NEXT: 0" in _lines(result.stdout)


def test_v5_keys_sessions_on_the_raw_directory_name(tmp_path: Path) -> None:
    """Two project directories can share a display name (``/opt/x`` and ``/x`` both show as
    ``x``); V5 counts only the directory that IS this repo's."""
    env = _env(tmp_path)
    repo = _make_repo(tmp_path, env)
    _init_store(repo, env)
    _write_next_item(repo, "W-0000aaa1")
    _write_live_claim(repo, "W-0000ccc1")
    transcripts_root = tmp_path / "transcripts"
    twin = "-opt-" + _project_dir_name(repo).lstrip("-")
    anchor_next = "NEXT: phase B of the plan — docs/development/plans/2026-09-25-x/T06.md"
    _write_transcript(transcripts_root / twin / "s1.jsonl", [_assistant_entry(anchor_next)])
    result = _run(["--root", str(transcripts_root), "--since", "7", "--repo", str(repo)], env)
    assert result.returncode == 0, result.stderr
    v5_line = next(ln for ln in _lines(result.stdout) if ln.startswith("V5:"))
    assert v5_line == "V5: FAIL — 1 open next item(s) > 0 qualifying session(s)"


def test_a_row_that_asks_for_a_tool_keeps_the_turn_open(tmp_path: Path) -> None:
    """An assistant row with text AND a tool_use block is mid-turn: a row injected right after it
    is not where Stop fired."""
    root = tmp_path / "root"
    text_and_tool = {
        "type": "assistant",
        "isSidechain": False,
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "NEXT: phase B of the rollout"},
                {"type": "tool_use", "id": "t1"},
            ],
        },
    }
    _write_transcript(
        root / "-opt-alpha" / "s.jsonl",
        [text_and_tool, _meta_row("Base directory for this skill: /x"), _assistant_entry("Done.")],
    )
    result = _run(["--root", str(root), "--since", "7"], _env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "sessions with an accepted free-text NEXT: 0" in _lines(result.stdout)


def test_an_interrupted_turn_is_never_judged(tmp_path: Path) -> None:
    """Stop does not fire on a user interrupt, so the harvest never judged that turn's text."""
    root = tmp_path / "root"
    _write_transcript(
        root / "-opt-alpha" / "s.jsonl",
        [
            _assistant_entry("NEXT: phase B of the rollout"),
            _user_entry("[Request interrupted by user]"),
            _user_entry("go on"),
            _assistant_entry("NEXT: tidy the docs"),
        ],
    )
    result = _run(["--root", str(root), "--since", "7"], _env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "sessions with an accepted free-text NEXT: 0" in _lines(result.stdout)


def test_a_row_written_twice_in_one_file_keeps_its_turn(tmp_path: Path) -> None:
    """The same row written twice in ONE transcript counts once, and its turn is still judged."""
    root = tmp_path / "root"
    row = _assistant_entry("NEXT: phase B of the rollout", row_uuid="u-1")
    _write_transcript(root / "-opt-alpha" / "s.jsonl", [row, row])
    result = _run(["--root", str(root), "--since", "7"], _env(tmp_path))
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    assert lines[0].startswith("next: 1 lines over 1 sessions"), result.stdout
    assert "sessions with an accepted free-text NEXT: 1 (alpha 1)" in lines


def test_the_older_file_keeps_a_shared_row(tmp_path: Path) -> None:
    """A resumed session's copy is written after the original, so the OLDER file keeps a shared
    row's turn, whatever the file names sort to."""
    root = tmp_path / "root"
    row = _assistant_entry("NEXT: phase B of the rollout", row_uuid="u-1")
    original = root / "-opt-beta" / "zzz.jsonl"
    copy = root / "-opt-alpha" / "aaa.jsonl"
    _write_transcript(original, [row])
    _write_transcript(copy, [row])
    now = time.time()
    os.utime(original, (now - 3600, now - 3600))
    os.utime(copy, (now, now))
    result = _run(["--root", str(root), "--since", "7"], _env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "sessions with an accepted free-text NEXT: 1 (beta 1)" in _lines(result.stdout)


def test_v5_a_stale_worker_copy_never_vetoes_a_live_item(tmp_path: Path) -> None:
    """A worker forks with master's items; its old copy of an id must not hide main's refreshed,
    in-window copy — the window is judged on the freshest next_at."""
    env = _env(tmp_path)
    repo = _make_repo(tmp_path, env)
    _init_store(repo, env)
    _write_live_claim(repo, "W-0000ccc1")
    linked = _linked_store(repo, env, "intel")
    _write_next_item(repo, "W-0000aaa1")
    _write_next_item(linked, "W-0000aaa1", next_at_days_ago=10)
    result = _run(
        ["--root", str(tmp_path / "transcripts"), "--since", "7", "--repo", str(repo)], env
    )
    assert result.returncode == 0, result.stderr
    v5_line = next(ln for ln in _lines(result.stdout) if ln.startswith("V5:"))
    assert v5_line == "V5: FAIL — 1 open next item(s) > 0 qualifying session(s)"


def test_a_compaction_summary_row_opens_the_file_without_a_judgement(tmp_path: Path) -> None:
    """A compacted session's file opens with its summary as a user row; it ends nothing, and the
    first real turn after it is judged as usual."""
    root = tmp_path / "root"
    summary = _user_entry("This session is being continued from a previous conversation.")
    summary["isCompactSummary"] = True
    _write_transcript(
        root / "-opt-alpha" / "s.jsonl",
        [summary, _assistant_entry("NEXT: phase B of the rollout")],
    )
    result = _run(["--root", str(root), "--since", "7"], _env(tmp_path))
    assert result.returncode == 0, result.stderr
    lines = _lines(result.stdout)
    assert lines[0].startswith("next: 1 lines over 1 sessions"), result.stdout
    assert "sessions with an accepted free-text NEXT: 1 (alpha 1)" in lines
