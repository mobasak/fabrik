"""Behavior contract for ``scripts/sysadmin/next_census.py`` (plan
2026-09-25-plan-1-work-store-single-tracker, ticket T06 + its round-1 review fixes).

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
import re
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
            _assistant_entry("just some closing prose, nothing to report"),
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
    # 2 sessions (2 files), but the row counts globally only once
    assert lines[0] == (
        "next: 1 lines over 2 sessions — names-item 0 · none 0 · operator-decision 0 · "
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
    assert v5_line == "V5: PASS"


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
    assert v5_line == "V5: PASS"


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
