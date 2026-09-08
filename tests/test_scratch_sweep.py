"""Behavior Contract — `scripts/scratch_sweep.py`, the session-scratch / worktree / dead-session sweeper.

The operator's two binding constraints (2026-09-08) are what every test here defends:

  1. "we should not cause data loss" — nothing is deleted blindly. The DEFAULT is a dry-run table;
     `--apply` is opt-in; every candidate carries its class, its reason and its evidence; and a
     hard-coded refusal set keeps held / kept / fresh / dirty / unmerged / locked / foreign /
     backup-holding entries out of the removal set entirely.
  2. "agents must know what will this script do while using it" — `--help` prints the refusal set
     verbatim, and every table names a class and a reason per row.

Four of these graders exist because the plan review found the corresponding data-loss path by
EXECUTION rather than by reading (plan 2026-09-08-plan-1-scratch-sweep, Pass Ledger):

  * the keep-list FILE itself aged past the threshold and the first `--apply` deleted the
    protection (`test_the_keep_list_file_survives_apply`);
  * a directory's own mtime does not move when a file deep inside is rewritten in place, so an
    actively-worked entry read `stale` (`test_a_deep_in_place_edit_keeps_an_entry_fresh`);
  * a gone pid is not a finished session — `--resume` keeps the sid, and all 18 gone-pid dirs on
    the box were younger than 7 d, one 8 minutes old
    (`test_a_freshly_gone_sid_is_not_dead_until_the_dir_is_idle`);
  * a revert-test `.bak` is the only copy of a pre-mutation file, and the hub contract itself tells
    agents to write one (`test_a_stale_entry_holding_a_bak_is_listed_not_removed`).
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "scratch_sweep.py"

NOW = 1_788_800_000  # the fixed test clock; every fixture mtime is derived from it
HOUR = 3600
DAY = 24 * HOUR
SID = "11111111-2222-3333-4444-555555555555"
SLUG = "-opt-fixture"


def _run(
    *args: str, env: dict[str, str] | None = None, stdin: str = ""
) -> subprocess.CompletedProcess[str]:
    """Invoke the real script as a subprocess — the way every caller does."""
    e = {
        "PATH": "/usr/bin:/bin",
        "HOME": os.environ.get("HOME", "/tmp"),
        "SCRATCH_SWEEP_NOW": str(NOW),
    }
    e.update(env or {})
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=60,
        input=stdin,
        env=e,
    )


def _age(path: Path, seconds_old: float) -> None:
    """Set a path's mtime relative to the fixed test clock."""
    when = NOW - seconds_old
    os.utime(path, (when, when))


def _tree_state(root: Path) -> set[tuple[str, int, int]]:
    """(relative path, size, mtime) for every entry — the byte-level no-op assertion."""
    out: set[tuple[str, int, int]] = set()
    for p in sorted(root.rglob("*")):
        st = p.lstat()
        out.add((str(p.relative_to(root)), st.st_size if p.is_file() else 0, int(st.st_mtime)))
    return out


@pytest.fixture
def scratch(tmp_path: Path) -> Path:
    """The plan's canonical session fixture: stale · fresh · kept · held, plus `tasks/` beside it.

    Laid out exactly as the harness lays it out — `<root>/<slug>/<sid>/{scratchpad,tasks}` — so the
    script's own glob-by-sid resolution is what finds it, never a cwd-derived slug.
    """
    root = tmp_path / "claude-1000"
    pad = root / SLUG / SID / "scratchpad"
    pad.mkdir(parents=True)
    (root / SLUG / SID / "tasks").mkdir()
    (root / SLUG / SID / "tasks" / "a.output").write_text("task output", encoding="utf-8")

    stale = pad / "stale-dir"
    stale.mkdir()
    (stale / "copy.py").write_text("x", encoding="utf-8")
    fresh = pad / "fresh-dir"
    fresh.mkdir()
    (fresh / "copy.py").write_text("x", encoding="utf-8")
    kept = pad / "kept-dir"
    kept.mkdir()
    (kept / "copy.py").write_text("x", encoding="utf-8")
    held = pad / "held-dir"
    held.mkdir()
    (held / "open.log").write_text("x", encoding="utf-8")
    (pad / ".keep").write_text("# the keep list\nkept-dir\n", encoding="utf-8")

    for entry, age in ((stale, 7 * HOUR), (kept, 7 * HOUR), (held, 7 * HOUR), (fresh, 1 * HOUR)):
        for p in sorted(entry.rglob("*"), reverse=True):
            _age(p, age)
        _age(entry, age)
    _age(pad / ".keep", 7 * HOUR)
    return root


def _env(root: Path, **extra: str) -> dict[str, str]:
    e = {"SCRATCH_SWEEP_ROOT": str(root)}
    e.update(extra)
    return e


def _classes(stdout: str) -> dict[str, str]:
    """Parse the table into {entry name: class} — the reader's own view of the run."""
    out: dict[str, str] = {}
    for line in stdout.splitlines():
        if "·" not in line or line.lstrip().startswith("#"):
            continue
        cells = [c.strip() for c in line.split("·")]
        if len(cells) < 3:
            continue
        name = Path(cells[0]).name
        cls = cells[2]
        if name and cls:
            out[name] = cls
    return out


def test_dry_run_deletes_nothing_and_names_every_class(scratch: Path) -> None:
    """The DEFAULT invocation classifies and prints; it never mutates the tree.

    This is the constraint-1 floor: an agent runs the bare command, reads the table, and only then
    decides. `tasks/` is the harness's own transcript spool and is not the sweeper's territory at
    all, so it must not even appear.
    """
    before = _tree_state(scratch)
    fd = os.open(str(scratch / SLUG / SID / "scratchpad" / "held-dir" / "open.log"), os.O_RDONLY)
    try:
        proc = _run("--session", SID, env=_env(scratch))
    finally:
        os.close(fd)

    assert proc.returncode == 0, proc.stderr
    seen = _classes(proc.stdout)
    assert seen.get("stale-dir") == "stale", proc.stdout
    assert seen.get("fresh-dir") == "fresh", proc.stdout
    assert seen.get("kept-dir") == "kept", proc.stdout
    assert seen.get("held-dir") == "held", proc.stdout
    assert "tasks" not in seen, "tasks/ is the harness's spool, never a sweep candidate"
    assert _tree_state(scratch) == before, "a dry run must not touch a single byte"


def test_a_deep_in_place_edit_keeps_an_entry_fresh(scratch: Path) -> None:
    """A directory's own mtime does not move when a file deep inside is rewritten in place.

    `mkdir e; touch e/sub/f; sleep; echo x >> e/sub/f` leaves `e`'s mtime frozen at creation, so a
    dir-mtime freshness test reads an actively-worked entry as `stale` and `--apply` deletes it.
    Freshness is therefore the NEWEST mtime in a bounded walk.
    """
    pad = scratch / SLUG / SID / "scratchpad"
    entry = pad / "stale-dir"
    deep = entry / "a" / "b"
    deep.mkdir(parents=True)
    live = deep / "notes.md"
    live.write_text("still working", encoding="utf-8")
    _age(live, 5 * 60)  # touched five minutes ago …
    _age(deep, 7 * HOUR)  # … while every directory above it is hours old
    _age(entry / "a", 7 * HOUR)
    _age(entry, 7 * HOUR)

    proc = _run("--session", SID, env=_env(scratch))
    assert proc.returncode == 0, proc.stderr
    assert _classes(proc.stdout).get("stale-dir") == "fresh", proc.stdout


def test_a_symlinked_entry_is_unclassified_and_its_target_untouched(
    scratch: Path, tmp_path: Path
) -> None:
    """A symlink is never followed and never removed — its target may be anything at all."""
    target = tmp_path / "outside"
    target.mkdir()
    (target / "precious.txt").write_text("do not delete", encoding="utf-8")
    link = scratch / SLUG / SID / "scratchpad" / "link-dir"
    link.symlink_to(target)
    os.utime(link, (NOW - 9 * HOUR, NOW - 9 * HOUR), follow_symlinks=False)

    proc = _run("--session", SID, "--apply", env=_env(scratch))
    assert proc.returncode == 0, proc.stderr
    assert _classes(proc.stdout).get("link-dir") == "unclassified", proc.stdout
    assert link.is_symlink(), "the symlink itself must survive"
    assert (target / "precious.txt").exists(), "the target must never be touched"


def test_a_traversal_sid_is_refused_before_any_scandir(scratch: Path) -> None:
    """A sid is interpolated into a filesystem path, so it is validated before any I/O."""
    before = _tree_state(scratch)
    for bad in ("../../etc", "a/b", "x" * 65, "sid;rm -rf /"):
        proc = _run("--session", bad, env=_env(scratch))
        assert proc.returncode == 1, f"{bad!r} → rc {proc.returncode}"
        assert "malformed" in proc.stderr.lower(), proc.stderr
    assert _tree_state(scratch) == before


def test_the_session_dir_is_found_by_sid_not_by_slug(tmp_path: Path) -> None:
    """The harness slug maps EVERY non-alphanumeric to `-`, so a cwd-derived path is wrong.

    `/opt/iterative_image_editor` lives at `-opt-iterative-image-editor`; a `replace("/", "-")`
    computes `-opt-iterative_image_editor`, finds nothing, and reports a false "clean" while the
    residue sits there.
    """
    root = tmp_path / "claude-1000"
    pad = root / "-opt-iterative-image-editor" / SID / "scratchpad"
    pad.mkdir(parents=True)
    stale = pad / "residue"
    stale.mkdir()
    _age(stale, 9 * HOUR)

    proc = _run("--session", SID, "--cwd", "/opt/iterative_image_editor", env=_env(root))
    assert proc.returncode == 0, proc.stderr
    assert _classes(proc.stdout).get("residue") == "stale", proc.stdout


def test_the_keep_list_file_survives_apply(scratch: Path) -> None:
    """`scratchpad/.keep` is an entry of the same scandir — without a rule it deletes itself.

    It is written once and never touched again, so it ages past the threshold like anything else,
    and the FIRST `--apply` would remove the file that holds every other entry's protection.
    """
    keep = scratch / SLUG / SID / "scratchpad" / ".keep"
    proc = _run("--session", SID, "--apply", env=_env(scratch))
    assert proc.returncode == 0, proc.stderr
    assert keep.exists(), "the keep list deleted its own protection"
    assert (scratch / SLUG / SID / "scratchpad" / "kept-dir").exists()


def test_an_unmatched_or_traversing_keep_name_is_reported_not_silent(scratch: Path) -> None:
    """A keep list that silently protects nothing is worse than none."""
    pad = scratch / SLUG / SID / "scratchpad"
    (pad / ".keep").write_text("kept-dir\ngone-dir\n../escape\n", encoding="utf-8")
    _age(pad / ".keep", 7 * HOUR)

    proc = _run("--session", SID, env=_env(scratch))
    assert proc.returncode == 0, proc.stderr
    assert "keep-unmatched" in proc.stdout and "gone-dir" in proc.stdout, proc.stdout
    assert "keep-invalid" in proc.stdout and "escape" in proc.stdout, proc.stdout


def test_a_stale_entry_holding_a_bak_is_listed_not_removed(scratch: Path) -> None:
    """A revert-test `.bak` can be the only copy of a pre-mutation file.

    The hub contract tells agents to `cp f /tmp/f.bak` before a revert test; an interrupted run
    leaves that backup to age past the threshold like ordinary residue.
    """
    entry = scratch / SLUG / SID / "scratchpad" / "stale-dir"
    (entry / "main.py.bak").write_text("the only copy", encoding="utf-8")
    for p in sorted(entry.rglob("*"), reverse=True):
        _age(p, 9 * HOUR)
    _age(entry, 9 * HOUR)

    proc = _run("--session", SID, "--apply", env=_env(scratch))
    assert proc.returncode == 0, proc.stderr
    assert _classes(proc.stdout).get("stale-dir") == "holds-backups", proc.stdout
    assert (entry / "main.py.bak").exists(), "a backup shape must survive a bare --apply"

    proc2 = _run("--session", SID, "--apply", "--include-backups", env=_env(scratch))
    assert proc2.returncode == 0, proc2.stderr
    assert not entry.exists(), "--include-backups is the explicit opt-in"


def _fake_proc(tmp_path: Path, *, uid: int, unreadable_fd: bool) -> Path:
    """A `/proc` whose single pid denies `/fd` — the gap the probe must count or ignore."""
    proc_root = tmp_path / "proc"
    pid = proc_root / "4793"
    pid.mkdir(parents=True)
    (pid / "comm").write_text("(sd-pam)\n", encoding="utf-8")
    (pid / "status").write_text(
        f"Name:\tsd-pam\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n", encoding="utf-8"
    )
    fd = pid / "fd"
    fd.mkdir()
    if unreadable_fd:
        os.chmod(fd, 0o000)
    return proc_root


def test_an_unreadable_same_uid_proc_pid_is_reported_as_a_gap_and_the_entry_stays_stale(
    scratch: Path, tmp_path: Path
) -> None:
    """The DEFAULT: a gap is COUNTED and NAMED, never blocking.

    Measured 2026-09-08: 152 of 466 pids deny `/fd` and 150 are foreign-uid; the two same-uid
    deniers are permanent. Blocking on them would make the tool inert on every run, forever — so
    the gap is reported in the summary line and the classification stands.
    """
    proc_root = _fake_proc(tmp_path, uid=os.getuid(), unreadable_fd=True)
    try:
        proc = _run("--session", SID, env=_env(scratch, FABRIK_PROC_ROOT=str(proc_root)))
        assert proc.returncode == 0, proc.stderr
        assert "proc-gaps 1" in proc.stdout, proc.stdout
        assert "4793" in proc.stdout, "the gap names the pid it could not read"
        assert _classes(proc.stdout).get("stale-dir") == "stale", proc.stdout
    finally:
        os.chmod(proc_root / "4793" / "fd", 0o755)


def test_a_foreign_uid_proc_gap_is_not_counted(scratch: Path, tmp_path: Path) -> None:
    """A foreign-uid process cannot hold a descriptor under the 0700 scratch root.

    Counting those would report a gap on every run (150 of 152 deniers today) and make
    `--strict-proc` unusable — the real uid comes from `status`, never `os.stat().st_uid`.
    """
    proc_root = _fake_proc(tmp_path, uid=os.getuid() + 1, unreadable_fd=True)
    try:
        proc = _run("--session", SID, env=_env(scratch, FABRIK_PROC_ROOT=str(proc_root)))
        assert proc.returncode == 0, proc.stderr
        assert "proc-gaps" not in proc.stdout, proc.stdout
    finally:
        os.chmod(proc_root / "4793" / "fd", 0o755)


def test_strict_proc_downgrades_stale_to_probe_error(scratch: Path, tmp_path: Path) -> None:
    """The opt-in: an operator who wants the conservative reading passes `--strict-proc`."""
    proc_root = _fake_proc(tmp_path, uid=os.getuid(), unreadable_fd=True)
    try:
        proc = _run(
            "--session", SID, "--strict-proc", env=_env(scratch, FABRIK_PROC_ROOT=str(proc_root))
        )
        assert proc.returncode == 0, proc.stderr
        assert _classes(proc.stdout).get("stale-dir") == "probe-error", proc.stdout
    finally:
        os.chmod(proc_root / "4793" / "fd", 0o755)


def test_apply_removes_only_stale(scratch: Path) -> None:
    """`--apply` removes the candidates and nothing else, and says what it removed."""
    pad = scratch / SLUG / SID / "scratchpad"
    fd = os.open(str(pad / "held-dir" / "open.log"), os.O_RDONLY)
    try:
        proc = _run("--session", SID, "--apply", env=_env(scratch))
    finally:
        os.close(fd)
    assert proc.returncode == 0, proc.stderr
    assert "REMOVED" in proc.stdout and "stale-dir" in proc.stdout, proc.stdout
    assert not (pad / "stale-dir").exists()
    assert (
        (pad / "fresh-dir").exists() and (pad / "kept-dir").exists() and (pad / "held-dir").exists()
    )
    assert (scratch / SLUG / SID / "tasks" / "a.output").exists(), "tasks/ is never the sweeper's"


def test_apply_continues_past_a_row_that_vanished(scratch: Path) -> None:
    """One racing removal must never abandon the rest — `apply()` catches PER ROW."""
    pad = scratch / SLUG / SID / "scratchpad"
    second = pad / "stale-two"
    second.mkdir()
    _age(second, 9 * HOUR)
    rows = [
        ("gone", pad / "vanished"),
        ("real", second),
    ]
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("scratch_sweep_apply_probe", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        # Register BEFORE exec: @dataclass resolves annotations via sys.modules[cls.__module__].
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        out = []

        class _Sink:
            def write(self, s: str) -> None:
                out.append(s)

            def flush(self) -> None:
                pass

        removed = mod.apply_rows(
            [
                mod.Row(str(rows[0][1]), "entry", "stale", "vanished before we got there"),
                mod.Row(str(rows[1][1]), "entry", "stale", "real"),
            ],
            {"stale"},
            out=_Sink(),
        )
    finally:
        sys.path.pop(0)
    assert removed == 1, "the surviving row must still be removed"
    assert not second.exists()


def test_a_second_concurrent_apply_is_a_one_line_noop_not_a_wait(scratch: Path) -> None:
    """A held lock is rc 0 and one line — never a wait, and never a silent partial sweep."""
    lock = Path(os.path.expanduser("~/.claude/state/scratch-sweep.lock"))
    lock.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock), os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        started = time.monotonic()
        proc = _run("--session", SID, "--apply", env=_env(scratch))
        elapsed = time.monotonic() - started
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    assert proc.returncode == 0, proc.stderr
    assert "another sweep holds the lock" in proc.stdout, proc.stdout
    assert elapsed < 10, f"a held lock must not wait ({elapsed:.1f}s)"
    assert (scratch / SLUG / SID / "scratchpad" / "stale-dir").exists(), (
        "nothing swept while locked"
    )


def test_apply_on_another_live_sid_is_refused(scratch: Path, tmp_path: Path) -> None:
    """Another LIVE session owns its scratch. The dry-run still prints; only `--apply` refuses."""
    other = "99999999-8888-7777-6666-555555555555"
    pad = scratch / SLUG / other / "scratchpad"
    pad.mkdir(parents=True)
    stale = pad / "their-residue"
    stale.mkdir()
    _age(stale, 9 * HOUR)

    sessions = tmp_path / "sessions"
    sessions.mkdir()
    # A genuinely FOREIGN live process — pid 1 is always running and is never our ancestor. Using
    # the test runner's own pid would make the peer indistinguishable from this very session, which
    # `_is_own_ancestor` now (correctly) treats as sweepable.
    with open("/proc/1/stat", encoding="utf-8") as fh:
        raw = fh.read()
    proc_start = raw[raw.rindex(")") + 2 :].split()[19]
    (sessions / "peer.json").write_text(
        json.dumps({"pid": 1, "sessionId": other, "procStart": proc_start}), encoding="utf-8"
    )
    env = _env(scratch, SCRATCH_SWEEP_SESSIONS_DIRS=str(sessions))

    refused = _run("--session", other, "--apply", env=env)
    assert refused.returncode == 2, refused.stdout + refused.stderr
    assert stale.exists(), "a live sibling's scratch is never removed"

    dry = _run("--session", other, env=env)
    assert dry.returncode == 0, dry.stderr
    assert _classes(dry.stdout).get("their-residue") == "stale", dry.stdout


def test_help_names_the_refusal_set() -> None:
    """Constraint 2: an agent reading `--help` knows exactly what the script will not touch."""
    proc = _run("--help")
    assert proc.returncode == 0, proc.stderr
    for clause in (
        "NEVER TOUCHES",
        "scratch-sweep.lock",
        "docker anything",
        "another LIVE session's scratch",
        "--include-backups",
        "wt-foreign",
    ):
        assert clause in proc.stdout, f"missing from --help: {clause}"


# ── the janitor ─────────────────────────────────────────────────────────────────────────────────
def _own_proc_start() -> str:
    raw = Path(f"/proc/{os.getpid()}/stat").read_text(encoding="utf-8")
    return raw[raw.rindex(")") + 2 :].split()[19]


@pytest.fixture
def graveyard(tmp_path: Path) -> tuple[Path, Path, Path]:
    """`(root, sessions dir, transcripts dir)` covering every janitor verdict at once."""
    root = tmp_path / "claude-1000"
    sessions = tmp_path / "sessions"
    transcripts = tmp_path / "projects" / "-opt-fixture"
    sessions.mkdir(parents=True)
    transcripts.mkdir(parents=True)

    live_sid = "aaaaaaaa-1111-1111-1111-111111111111"
    dead_sid = "bbbbbbbb-2222-2222-2222-222222222222"
    unknown_sid = "cccccccc-3333-3333-3333-333333333333"
    fresh_dead_sid = "dddddddd-4444-4444-4444-444444444444"
    backup_sid = "eeeeeeee-5555-5555-5555-555555555555"

    for sid, age in (
        (live_sid, 30 * DAY),
        (dead_sid, 30 * DAY),
        (unknown_sid, 30 * DAY),
        (fresh_dead_sid, 8 * 60),  # a gone pid whose dir was touched 8 minutes ago
        (backup_sid, 30 * DAY),
    ):
        pad = root / SLUG / sid / "scratchpad"
        pad.mkdir(parents=True)
        (pad / "copy.py").write_text("x", encoding="utf-8")
        if sid == backup_sid:
            (pad / "main.py.bak").write_text("the only copy", encoding="utf-8")
        for p in sorted((root / SLUG / sid).rglob("*"), reverse=True):
            _age(p, age)
        _age(root / SLUG / sid, age)

    (sessions / "1.json").write_text(
        json.dumps({"pid": os.getpid(), "sessionId": live_sid, "procStart": _own_proc_start()}),
        encoding="utf-8",
    )
    for sid in (dead_sid, fresh_dead_sid, backup_sid):
        (sessions / f"{sid[:4]}.json").write_text(
            json.dumps({"pid": 999_999, "sessionId": sid, "procStart": "1"}), encoding="utf-8"
        )

    for name, days in (
        ("payments-c4", 10),
        ("fe-pristine", 10),
        ("mcp-health-cache", 10),
        ("recent-thing", 1),
    ):
        d = root / name
        d.mkdir(parents=True)
        (d / "f").write_text("x", encoding="utf-8")
        _age(d / "f", days * DAY)
        _age(d, days * DAY)

    slug_idle = root / "-opt-old-project" / "ffffffff-6666-6666-6666-666666666666"
    slug_idle.mkdir(parents=True)
    _age(slug_idle, 10 * DAY)
    _age(root / "-opt-old-project", 10 * DAY)
    return root, sessions, transcripts


def _dead_env(bundle: tuple[Path, Path, Path], **extra: str) -> dict[str, str]:
    root, sessions, transcripts = bundle
    e = {
        "SCRATCH_SWEEP_ROOT": str(root),
        "SCRATCH_SWEEP_SESSIONS_DIRS": str(sessions),
        "SCRATCH_SWEEP_TRANSCRIPT_DIRS": str(transcripts.parent),
        "CLAUDE_SOUND_LOCKDIR": str(root.parent / "no-locks"),
    }
    e.update(extra)
    return e


def test_janitor_removes_only_dead_sids(graveyard: tuple[Path, Path, Path]) -> None:
    """Live stays, unknown stays, a backup-holder stays; only a three-signal `dead` sid goes."""
    root, _, _ = graveyard
    proc = _run("--dead", "--apply", env=_dead_env(graveyard))
    assert proc.returncode == 0, proc.stderr
    seen = _classes(proc.stdout)
    assert seen.get("aaaaaaaa-1111-1111-1111-111111111111") == "live", proc.stdout
    assert seen.get("bbbbbbbb-2222-2222-2222-222222222222") == "dead", proc.stdout
    assert seen.get("cccccccc-3333-3333-3333-333333333333") == "unclassified", proc.stdout
    assert seen.get("eeeeeeee-5555-5555-5555-555555555555") == "dead-holds-backups", proc.stdout

    assert not (root / SLUG / "bbbbbbbb-2222-2222-2222-222222222222").exists()
    for survivor in (
        "aaaaaaaa-1111-1111-1111-111111111111",
        "cccccccc-3333-3333-3333-333333333333",
        "eeeeeeee-5555-5555-5555-555555555555",
    ):
        assert (root / SLUG / survivor).exists(), survivor


def test_a_freshly_gone_sid_is_not_dead_until_the_dir_is_idle(
    graveyard: tuple[Path, Path, Path],
) -> None:
    """A gone pid is NOT a finished session — `--resume` keeps the sid.

    Measured 2026-09-08: 18 sids had a gone-pid sessions file and a live directory, ALL of them
    younger than 7 d and one 8 minutes old. Those are exactly the quota-hold and network-death
    interruptions this tool exists to serve, so the dir's own idleness is a third required signal.
    The 2-day twin is the discriminator: it passes a 6 h threshold and must still be spared under
    the janitor's own 7 d default, so an implementer who wires one shared `default="6h"` goes red.
    """
    root, _, _ = graveyard
    two_day = root / SLUG / "77777777-9999-9999-9999-999999999999"
    (two_day / "scratchpad").mkdir(parents=True)
    _age(two_day / "scratchpad", 2 * DAY)
    _age(two_day, 2 * DAY)
    (graveyard[1] / "two-day.json").write_text(
        json.dumps({"pid": 999_998, "sessionId": two_day.name, "procStart": "1"}), encoding="utf-8"
    )

    proc = _run("--dead", "--apply", env=_dead_env(graveyard))
    assert proc.returncode == 0, proc.stderr
    seen = _classes(proc.stdout)
    assert seen.get("dddddddd-4444-4444-4444-444444444444") == "unclassified", proc.stdout
    assert seen.get(two_day.name) == "unclassified", "2 days passes 6h but not the janitor's 7d"
    assert (root / SLUG / "dddddddd-4444-4444-4444-444444444444").exists()
    assert two_day.exists()


def test_a_held_selfwatch_lock_is_liveness(
    graveyard: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """A held self-watch lock means the pane is alive even with no sessions file."""
    root, _, _ = graveyard
    locks = tmp_path / "locks"
    locks.mkdir()
    sid = "cccccccc-3333-3333-3333-333333333333"
    fd = os.open(str(locks / f"{sid}.selfwatch.lock"), os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        proc = _run("--dead", env=_dead_env(graveyard, CLAUDE_SOUND_LOCKDIR=str(locks)))
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    assert proc.returncode == 0, proc.stderr
    assert _classes(proc.stdout).get(sid) == "live", proc.stdout


def test_a_process_under_the_dir_is_liveness(graveyard: tuple[Path, Path, Path]) -> None:
    """A process holding a descriptor inside a sid dir keeps it alive, whatever the records say."""
    root, _, _ = graveyard
    sid = "bbbbbbbb-2222-2222-2222-222222222222"
    fd = os.open(str(root / SLUG / sid / "scratchpad" / "copy.py"), os.O_RDONLY)
    try:
        proc = _run("--dead", "--apply", env=_dead_env(graveyard))
    finally:
        os.close(fd)
    assert proc.returncode == 0, proc.stderr
    assert _classes(proc.stdout).get(sid) == "live", proc.stdout
    assert (root / SLUG / sid).exists()


def test_an_idle_transcript_is_the_death_signal(graveyard: tuple[Path, Path, Path]) -> None:
    """With no sessions file at all, an idle transcript is the positive death signal."""
    root, _, transcripts = graveyard
    sid = "cccccccc-3333-3333-3333-333333333333"
    tx = transcripts / f"{sid}.jsonl"
    tx.write_text("{}\n", encoding="utf-8")
    _age(tx, 8 * DAY)

    proc = _run("--dead", env=_dead_env(graveyard))
    assert _classes(proc.stdout).get(sid) == "dead", proc.stdout

    _age(tx, 1 * DAY)
    proc2 = _run("--dead", env=_dead_env(graveyard))
    assert _classes(proc2.stdout).get(sid) == "unclassified", proc2.stdout


def test_an_unowned_pristine_baseline_is_protected(graveyard: tuple[Path, Path, Path]) -> None:
    """The root level is where the operator's baselines actually sit.

    `fe-pristine/` carries the marker in its NAME and nothing in its contents, so a contents-only
    test classes it ordinary residue and `--unowned-older-than 7 --apply` deletes a source baseline.
    A slug dir is never `unowned` at all — it is the janitor's own per-sid territory.
    """
    root, _, _ = graveyard
    proc = _run("--dead", "--unowned-older-than", "7", "--apply", env=_dead_env(graveyard))
    assert proc.returncode == 0, proc.stderr
    seen = _classes(proc.stdout)
    assert seen.get("fe-pristine") == "protected", proc.stdout
    assert seen.get("mcp-health-cache") == "protected", proc.stdout
    assert seen.get("recent-thing") == "protected", "1 day is under the 7-day threshold"
    assert seen.get("payments-c4") == "unowned", proc.stdout
    assert "-opt-old-project" not in seen, "a slug dir is classified per-sid, never as unowned"

    assert not (root / "payments-c4").exists()
    for survivor in ("fe-pristine", "mcp-health-cache", "recent-thing", "-opt-old-project"):
        assert (root / survivor).exists(), survivor


def test_an_unreadable_root_makes_no_sid_dead(
    graveyard: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """A root we cannot list has no enumerable sids — the LIVE signal collapses, DEATH survives.

    So the whole table degrades to `unclassified` and `--apply` refuses, rather than the unattended
    cron deleting a session whose only liveness record lived in the unreadable root.
    """
    root, _, _ = graveyard
    blocked = tmp_path / "blocked-sessions"
    blocked.mkdir()
    os.chmod(blocked, 0o000)
    env = _dead_env(graveyard)
    env["SCRATCH_SWEEP_SESSIONS_DIRS"] = (
        f"{env['SCRATCH_SWEEP_SESSIONS_DIRS']}{os.pathsep}{blocked}"
    )
    try:
        proc = _run("--dead", "--apply", env=env)
    finally:
        os.chmod(blocked, 0o755)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "REFUSED" in proc.stdout, proc.stdout
    assert "dead " not in proc.stdout.split("REFUSED")[0].split("\n")[-2], proc.stdout
    assert (root / SLUG / "bbbbbbbb-2222-2222-2222-222222222222").exists(), "nothing removed"


def test_a_sid_whose_sessions_file_lives_in_an_unscanned_root_is_never_dead(
    graveyard: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """Config roots are DISCOVERED, never a hand-written pair.

    `~/.claude-youtube-headless` is a real root holding 132 session files that a two-root scan
    missed entirely, and a live process can declare a root outside `~/.claude*` via
    `CLAUDE_CONFIG_DIR` — so a sid whose only record lives there must never read `dead`.
    """
    root, sessions, _ = graveyard
    extra = tmp_path / "headless-profile" / "sessions"
    extra.mkdir(parents=True)
    sid = "bbbbbbbb-2222-2222-2222-222222222222"
    (extra / "live.json").write_text(
        json.dumps({"pid": os.getpid(), "sessionId": sid, "procStart": _own_proc_start()}),
        encoding="utf-8",
    )
    env = _dead_env(graveyard)
    env["SCRATCH_SWEEP_SESSIONS_DIRS"] = f"{sessions}{os.pathsep}{extra}"

    proc = _run("--dead", "--apply", env=env)
    assert proc.returncode == 0, proc.stderr
    assert _classes(proc.stdout).get(sid) == "live", proc.stdout
    assert (root / SLUG / sid).exists()


def test_a_dead_dir_holding_a_bak_is_listed_not_removed(graveyard: tuple[Path, Path, Path]) -> None:
    """`--include-backups` is the explicit opt-in; a bare `--apply` spares the backup holder."""
    root, _, _ = graveyard
    sid = "eeeeeeee-5555-5555-5555-555555555555"
    bare = _run("--dead", "--apply", env=_dead_env(graveyard))
    assert bare.returncode == 0, bare.stderr
    assert (root / SLUG / sid).exists(), "a bare --apply must spare a backup holder"

    opt_in = _run("--dead", "--apply", "--include-backups", env=_dead_env(graveyard))
    assert opt_in.returncode == 0, opt_in.stderr
    assert not (root / SLUG / sid).exists()


# ── the worktree classifier ─────────────────────────────────────────────────────────────────────
def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=30, check=False
    ).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo on `main` carrying one worktree per verdict the classifier can reach."""
    main = tmp_path / "repo"
    main.mkdir()
    _git(main, "init", "-q", "-b", "main")
    _git(main, "config", "user.email", "t@t")
    _git(main, "config", "user.name", "t")
    (main / "a.txt").write_text("base", encoding="utf-8")
    (main / ".gitignore").write_text(".venv/\ndata/\n", encoding="utf-8")
    _git(main, "add", "-A")
    _git(main, "commit", "-qm", "base")

    def wt(name: str, branch: str) -> Path:
        path = tmp_path / name
        _git(main, "worktree", "add", "-q", str(path), "-b", branch)
        return path

    merged = wt("wt-merged", "feat-merged")
    (merged / "m.txt").write_text("m", encoding="utf-8")
    _git(merged, "add", "-A")
    _git(merged, "commit", "-qm", "feat")
    _git(main, "merge", "-q", "--no-ff", "feat-merged", "-m", "merge feat")

    squashed = wt("wt-squashed", "feat-squashed")
    (squashed / "s.txt").write_text("s", encoding="utf-8")
    _git(squashed, "add", "-A")
    _git(squashed, "commit", "-qm", "squash work")
    _git(
        main,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "squash\n\nMerged-From: other-branch (x), feat-squashed (y)\n",
    )

    near = wt("wt-nearmiss", "feat-squashed-2")
    (near / "n.txt").write_text("n", encoding="utf-8")
    _git(near, "add", "-A")
    _git(near, "commit", "-qm", "near miss")

    unmerged = wt("wt-unmerged", "feat-unmerged")
    (unmerged / "u.txt").write_text("u", encoding="utf-8")
    _git(unmerged, "add", "-A")
    _git(unmerged, "commit", "-qm", "unmerged work")

    dirty = wt("wt-dirty", "feat-dirty")
    _git(main, "merge", "-q", "--no-ff", "feat-dirty", "-m", "merge dirty")
    (dirty / "uncommitted.txt").write_text("in flight", encoding="utf-8")

    stashed = wt("wt-stashed", "feat-stashed")
    _git(main, "merge", "-q", "--no-ff", "feat-stashed", "-m", "merge stashed")
    (stashed / "a.txt").write_text("stashed edit", encoding="utf-8")
    _git(stashed, "stash", "-q")

    ign_data = wt("wt-ignored-data", "feat-ign-data")
    _git(main, "merge", "-q", "--no-ff", "feat-ign-data", "-m", "merge ign-data")
    (ign_data / "data").mkdir()
    (ign_data / "data" / "only-copy.jsonl").write_text("payload", encoding="utf-8")

    ign_cache = wt("wt-ignored-cache", "feat-ign-cache")
    _git(main, "merge", "-q", "--no-ff", "feat-ign-cache", "-m", "merge ign-cache")
    (ign_cache / ".venv").mkdir()
    (ign_cache / ".venv" / "pyvenv.cfg").write_text("rebuildable", encoding="utf-8")

    locked = wt("wt-locked", "feat-locked")
    _git(main, "merge", "-q", "--no-ff", "feat-locked", "-m", "merge locked")
    _git(main, "worktree", "lock", str(locked))

    harness_dir = main / ".claude" / "worktrees"
    harness_dir.mkdir(parents=True)
    harness = harness_dir / "agent-x"
    _git(main, "worktree", "add", "-q", str(harness), "-b", "worktree-agent-x")
    _git(main, "merge", "-q", "--no-ff", "worktree-agent-x", "-m", "merge agent-x")
    (main / ".git" / "worktrees" / "agent-x" / "CLAUDE_BASE").write_text(
        _git(main, "rev-parse", "HEAD").strip() + "\n", encoding="utf-8"
    )
    (harness_dir / "agent-orphan").mkdir()
    (harness_dir / "agent-orphan" / "left.py").write_text("x", encoding="utf-8")

    gone = wt("wt-gone", "feat-gone")
    _git(main, "merge", "-q", "--no-ff", "feat-gone", "-m", "merge gone")
    shutil_rmtree(gone)

    # Every registration must look NEWER than the session start the classifier compares against.
    for meta in (main / ".git" / "worktrees").iterdir():
        os.utime(meta / "gitdir", (NOW, NOW))
    return main


def shutil_rmtree(path: Path) -> None:
    import shutil as _sh

    _sh.rmtree(path)


def _wt_env(**extra: str) -> dict[str, str]:
    # A session start EARLIER than every registration: provenance passes, so the other classes show.
    e = {
        "SCRATCH_SWEEP_SESSIONS_DIRS": "/nonexistent",
        "SCRATCH_SWEEP_FORCE_START": str(NOW - DAY),
        "SCRATCH_SWEEP_TEST": "1",  # the provenance seam is gated: it can authorize a removal
    }
    e.update(extra)
    return e


def test_worktree_merge_states(repo: Path) -> None:
    """Merged, squash-merged, near-miss, unmerged and dirty — the five merge-state verdicts.

    The near-miss is the one a substring parse gets wrong: `feat-squashed-2` shares a prefix with
    the `Merged-From` entry for `feat-squashed`, and only a whole-string compare keeps it unmerged.
    """
    proc = _run("--worktrees", str(repo), env=_wt_env())
    assert proc.returncode == 0, proc.stderr
    seen = _classes(proc.stdout)
    assert seen.get("wt-merged") == "wt-removable", proc.stdout
    assert seen.get("wt-squashed") == "wt-removable", proc.stdout
    assert seen.get("wt-nearmiss") == "wt-unmerged", proc.stdout
    assert seen.get("wt-unmerged") == "wt-unmerged", proc.stdout
    assert seen.get("wt-dirty") == "wt-dirty", proc.stdout


def test_worktree_data_guards(repo: Path) -> None:
    """A stash, ignored DATA and a harness tree are each spared; ignored CACHE is not data."""
    proc = _run("--worktrees", str(repo), env=_wt_env())
    assert proc.returncode == 0, proc.stderr
    seen = _classes(proc.stdout)
    assert seen.get("wt-stashed") == "wt-dirty", proc.stdout
    assert seen.get("wt-ignored-data") == "wt-ignored-data", proc.stdout
    assert seen.get("wt-ignored-cache") == "wt-removable", "a .venv is rebuildable, not data"
    assert seen.get("agent-x") == "wt-harness", proc.stdout
    assert seen.get("agent-orphan") == "wt-orphan-dir", proc.stdout


def test_worktree_lock_prune_and_detached(repo: Path) -> None:
    """Locked stays; a gone registration prunes; a detached main checkout classifies nothing."""
    proc = _run("--worktrees", str(repo), env=_wt_env())
    seen = _classes(proc.stdout)
    assert seen.get("wt-locked") == "wt-locked", proc.stdout
    assert seen.get("wt-gone") == "wt-prunable", proc.stdout

    _git(repo, "checkout", "-q", "--detach")
    detached = _run("--worktrees", str(repo), env=_wt_env())
    assert detached.returncode == 0, detached.stderr
    classes = set(_classes(detached.stdout).values())
    assert classes == {"unclassified"}, detached.stdout


def test_worktree_apply_never_forces(repo: Path) -> None:
    """`--apply` removes only the removable, with `-d` and never `--force`/`-D`.

    A SQUASH-merged branch is not an ancestor, so `git branch -d` REFUSES it: the worktree goes and
    the branch survives with git's refusal printed. That is the correct conservative end state.
    """
    proc = _run("--worktrees", str(repo), "--apply", env=_wt_env())
    assert proc.returncode == 0, proc.stderr
    assert not (repo.parent / "wt-merged").exists(), "the merged+clean worktree is removed"
    assert not (repo.parent / "wt-squashed").exists(), "the squash-merged worktree is removed"
    for kept in (
        "wt-unmerged",
        "wt-nearmiss",
        "wt-dirty",
        "wt-stashed",
        "wt-ignored-data",
        "wt-locked",
    ):
        assert (repo.parent / kept).exists(), f"{kept} must survive"
    assert (repo / ".claude" / "worktrees" / "agent-x").exists(), "harness needs --include-harness"
    branches = _git(repo, "branch", "--list")
    assert "feat-merged" not in branches, "an ancestor-merged branch is deleted with -d"
    assert "feat-squashed" in branches, "a squash-merged branch survives -d's refusal"


def test_include_harness_still_refuses_dirty_and_unmerged_harness_trees(
    repo: Path, tmp_path: Path
) -> None:
    """The harness test TAGS; it never short-circuits the chain.

    A first-match "harness" rule would make a dirty or unmerged harness tree removable under the
    flag — saved only by git's own refusal, which a CLEAN-but-unmerged tree never gets.
    """
    dirty_harness = repo / ".claude" / "worktrees" / "agent-dirty"
    _git(repo, "worktree", "add", "-q", str(dirty_harness), "-b", "worktree-agent-dirty")
    (dirty_harness / "wip.txt").write_text("in flight", encoding="utf-8")
    os.utime(repo / ".git" / "worktrees" / "agent-dirty" / "gitdir", (NOW, NOW))

    proc = _run("--worktrees", str(repo), "--apply", "--include-harness", env=_wt_env())
    assert proc.returncode == 0, proc.stderr
    assert not (repo / ".claude" / "worktrees" / "agent-x").exists(), (
        "clean+merged harness goes under the flag"
    )
    assert dirty_harness.exists(), "a DIRTY harness tree survives even under --include-harness"


def test_a_worktree_registered_before_this_session_started_is_foreign(repo: Path) -> None:
    """Provenance is the registration's AGE against this session's start.

    `procStart` is CLOCK TICKS SINCE BOOT, so the comparison needs `btime + ticks/HZ`; a raw-tick
    compare classes every worktree not-foreign. And when the start cannot be resolved at all, the
    fail direction is CLOSED — every worktree is foreign and nothing is removable.
    """
    later = _run("--worktrees", str(repo), env=_wt_env(SCRATCH_SWEEP_FORCE_START=str(NOW + DAY)))
    assert later.returncode == 0, later.stderr
    assert set(_classes(later.stdout).values()) <= {"wt-foreign", "wt-orphan-dir"}, later.stdout

    unresolvable = _run(
        "--worktrees", str(repo), env={"SCRATCH_SWEEP_SESSIONS_DIRS": "/nonexistent"}
    )
    assert unresolvable.returncode == 0, unresolvable.stderr
    classes = set(_classes(unresolvable.stdout).values())
    assert classes <= {"wt-foreign", "wt-orphan-dir"}, unresolvable.stdout


# ── the SessionStart hook ───────────────────────────────────────────────────────────────────────
def _hook(scratch: Path, sid: str = SID, cwd: str = "/opt/fabrik", **extra: str):
    return _run(
        "--hook",
        "--session",
        sid,
        env=_env(scratch, **extra),
        stdin=json.dumps({"session_id": sid, "cwd": cwd, "hook_event_name": "SessionStart"}),
    )


def test_hook_line_fires_only_with_candidates_and_never_blocks(scratch: Path) -> None:
    """One line when there is residue; silence otherwise; exit 0 on every path."""
    proc = _hook(scratch)
    assert proc.returncode == 0, proc.stderr
    assert "🧹 SCRATCH:" in proc.stdout, proc.stdout
    assert "never touches" in proc.stdout, "constraint 2 — the line says what it will not touch"

    for gate, value in (("CLAUDE_MESH_HEADLESS", "1"), ("CLAUDE_MESH_AUTONOMOUS", "1")):
        gated = _hook(scratch, **{gate: value})
        assert gated.returncode == 0 and gated.stdout == "", f"{gate} must silence it"

    outside = _hook(scratch, cwd="/home/somewhere")
    assert outside.returncode == 0 and outside.stdout == "", "a non-/opt cwd is silent"


def test_the_hook_line_reprints_only_when_the_candidate_count_grows(scratch: Path) -> None:
    """The stamp records EVERY evaluation, a silent zero included.

    Recording only on a PRINT would make it a monotone high-water mark that `--apply` never lowers
    — the stamp is a sibling of `scratchpad/` — so an agent that complied and swept would silence
    its own advisory until residue exceeded the first, largest report.
    """
    first = _hook(scratch)
    assert "🧹 SCRATCH:" in first.stdout, first.stdout

    again = _hook(scratch)
    assert again.stdout == "", "an unchanged resume stays silent"

    applied = _run("--session", SID, "--apply", env=_env(scratch))
    assert applied.returncode == 0, applied.stderr
    after_apply = _hook(scratch)
    assert after_apply.stdout == "", "nothing left to report"

    pad = scratch / SLUG / SID / "scratchpad"
    for name in ("new-one", "new-two"):
        d = pad / name
        d.mkdir()
        _age(d, 9 * HOUR)
    grown = _hook(scratch)
    assert "🧹 SCRATCH:" in grown.stdout, "residue grew after a compliant sweep — say so again"


# ── the three data-loss paths the Phase-A review proved by execution ────────────────────────────
def test_include_harness_never_promotes_a_non_removable_chain_verdict(repo: Path) -> None:
    """`--include-harness` gates on the CLASS, so a non-removable chain verdict must BE the class.

    Tagging every harness row `wt-harness` regardless of its chain verdict let the flag delete a
    tree holding ignored DATA and a clean-but-unmerged tree — the latter gets no git refusal to
    save it. The review removed a `data/only-copy.jsonl` this way before the fix.
    """
    data_wt = repo / ".claude" / "worktrees" / "agent-data"
    _git(repo, "worktree", "add", "-q", str(data_wt), "-b", "worktree-agent-data")
    _git(repo, "merge", "-q", "--no-ff", "worktree-agent-data", "-m", "merge agent-data")
    (data_wt / "data").mkdir()
    (data_wt / "data" / "only-copy.jsonl").write_text("the only copy", encoding="utf-8")

    unmerged_wt = repo / ".claude" / "worktrees" / "agent-unmerged"
    _git(repo, "worktree", "add", "-q", str(unmerged_wt), "-b", "worktree-agent-unmerged")
    (unmerged_wt / "work.txt").write_text("unmerged work", encoding="utf-8")
    _git(unmerged_wt, "add", "-A")
    _git(unmerged_wt, "commit", "-qm", "unmerged")
    for name in ("agent-data", "agent-unmerged"):
        os.utime(repo / ".git" / "worktrees" / name / "gitdir", (NOW, NOW))

    proc = _run("--worktrees", str(repo), "--apply", "--include-harness", env=_wt_env())
    assert proc.returncode == 0, proc.stderr
    seen = _classes(proc.stdout)
    assert seen.get("agent-data") == "wt-ignored-data", proc.stdout
    assert seen.get("agent-unmerged") == "wt-unmerged", proc.stdout
    assert (data_wt / "data" / "only-copy.jsonl").exists(), (
        "ignored DATA survived --include-harness"
    )
    assert unmerged_wt.exists(), "a clean-but-unmerged harness tree survived --include-harness"
    assert not (repo / ".claude" / "worktrees" / "agent-x").exists(), (
        "the clean+merged one still goes"
    )


def test_a_dead_proc_probe_never_reads_as_unheld(scratch: Path, tmp_path: Path) -> None:
    """A total `/proc` failure is a RUN-level condition, not silence.

    Both liveness signals depend on `/proc`; if the probe is dead they collapse while the death
    signals survive. Before the fix, an entry with an OPEN fd inside it read `stale` and `--apply`
    removed it, and a LIVE session's dir read `dead` in the janitor.
    """
    missing = tmp_path / "no-proc"
    fd = os.open(str(scratch / SLUG / SID / "scratchpad" / "held-dir" / "open.log"), os.O_RDONLY)
    try:
        proc = _run("--session", SID, "--apply", env=_env(scratch, FABRIK_PROC_ROOT=str(missing)))
    finally:
        os.close(fd)
    assert proc.returncode == 0, proc.stderr
    assert _classes(proc.stdout).get("held-dir") == "probe-error", proc.stdout
    assert (scratch / SLUG / SID / "scratchpad" / "held-dir").exists(), "an open fd was inside it"
    assert (scratch / SLUG / SID / "scratchpad" / "stale-dir").exists(), (
        "nothing is provably unheld"
    )


def test_an_unreadable_sessions_root_refuses_a_peer_apply(scratch: Path, tmp_path: Path) -> None:
    """A peer whose liveness record lives in an unreadable root is not "unclaimed".

    `--dead` already refuses on this; session mode discarded the same list and removed a RUNNING
    peer's scratch (review F3).
    """
    other = "99999999-8888-7777-6666-555555555555"
    pad = scratch / SLUG / other / "scratchpad"
    pad.mkdir(parents=True)
    stale = pad / "their-residue"
    stale.mkdir()
    _age(stale, 9 * HOUR)

    blocked = tmp_path / "blocked-sessions"
    blocked.mkdir()
    os.chmod(blocked, 0o000)
    try:
        proc = _run(
            "--session",
            other,
            "--apply",
            env=_env(scratch, SCRATCH_SWEEP_SESSIONS_DIRS=str(blocked)),
        )
    finally:
        os.chmod(blocked, 0o755)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "REFUSED" in proc.stdout, proc.stdout
    assert stale.exists(), "a peer's scratch survived an unprovable liveness check"


def test_a_truncated_idleness_walk_never_reads_as_dead(graveyard: tuple[Path, Path, Path]) -> None:
    """`--dead` must honour the walk's completeness flag.

    A truncated walk yields the top-level dir's own mtime, which does not move for deep in-place
    edits — so a LIVE dir would read maximally idle and be removed.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("scratch_sweep_trunc_probe", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    root, sessions, _ = graveyard
    sid_dir = root / SLUG / "bbbbbbbb-2222-2222-2222-222222222222"
    exhausted = mod.WalkBudget(stats=0, deadline_s=0.0)
    exhausted.spend()
    newest, complete = mod.newest_mtime(sid_dir, exhausted)
    assert complete is False, "the fixture must actually exhaust the budget"


def test_a_zero_or_negative_threshold_is_refused(scratch: Path) -> None:
    """`--older-than 0` made a directory written one second ago `stale`; `--unowned-older-than 0`
    made every non-protected root entry removable at any age."""
    for flag, value in (
        ("--older-than", "0"),
        ("--older-than", "nan"),
        ("--unowned-older-than", "0"),
    ):
        proc = _run("--session", SID, flag, value, env=_env(scratch))
        assert proc.returncode == 1, (
            f"{flag} {value} → rc {proc.returncode}: {proc.stdout}{proc.stderr}"
        )
    assert (scratch / SLUG / SID / "scratchpad" / "stale-dir").exists()


def test_every_apply_run_prints_the_refusal_set(scratch: Path) -> None:
    """Constraint 2, and the script's own claim about itself: `--help` AND every apply run."""
    proc = _run("--session", SID, "--apply", env=_env(scratch))
    assert proc.returncode == 0, proc.stderr
    assert "NEVER TOUCHES" in proc.stdout, "an --apply run must say what it will not touch"


def test_the_hook_reads_the_session_id_from_its_payload(scratch: Path) -> None:
    """A SessionStart hook is invoked with no `--session` and no env sid — the payload carries it.

    Before the fix the hook exited 1 and printed nothing, so Phase B would have registered an
    entry that could never fire.
    """
    proc = _run(
        "--hook",
        env=_env(scratch),
        stdin=json.dumps(
            {"session_id": SID, "cwd": "/opt/fabrik", "hook_event_name": "SessionStart"}
        ),
    )
    assert proc.returncode == 0, proc.stderr
    assert "🧹 SCRATCH:" in proc.stdout, proc.stdout


def test_the_provenance_seam_is_inert_without_the_test_flag(repo: Path) -> None:
    """`SCRATCH_SWEEP_FORCE_START` can authorize removing another session's worktree, unlike the
    clock seam, so it is gated behind an explicit `SCRATCH_SWEEP_TEST=1`."""
    ungated = _run(
        "--worktrees",
        str(repo),
        env={
            "SCRATCH_SWEEP_SESSIONS_DIRS": "/nonexistent",
            "SCRATCH_SWEEP_FORCE_START": str(NOW - DAY),
        },
    )
    assert ungated.returncode == 0, ungated.stderr
    assert set(_classes(ungated.stdout).values()) <= {"wt-foreign", "wt-orphan-dir"}, ungated.stdout


# ── the round-2 findings ────────────────────────────────────────────────────────────────────────
def test_include_backups_never_removes_a_fresh_or_held_entry(scratch: Path) -> None:
    """`holds-backups` is REMOVABLE under its flag, so it must be reached only from `stale`.

    Testing the backup shape before the holder probe and the freshness check made the guard
    written to protect revert-test baselines the ONLY thing deleting a live, freshly-written one.
    """
    pad = scratch / SLUG / SID / "scratchpad"
    fresh_backup = pad / "live-revert-test"
    fresh_backup.mkdir()
    (fresh_backup / "main.py.bak").write_text("the only copy", encoding="utf-8")
    _age(fresh_backup / "main.py.bak", 60)
    _age(fresh_backup, 60)

    held_backup = pad / "held-revert"
    held_backup.mkdir()
    (held_backup / "api.py.bak").write_text("also the only copy", encoding="utf-8")
    (held_backup / "open.log").write_text("x", encoding="utf-8")
    for p in sorted(held_backup.rglob("*"), reverse=True):
        _age(p, 9 * HOUR)
    _age(held_backup, 9 * HOUR)

    fd = os.open(str(held_backup / "open.log"), os.O_RDONLY)
    try:
        proc = _run("--session", SID, "--include-backups", "--apply", env=_env(scratch))
    finally:
        os.close(fd)
    assert proc.returncode == 0, proc.stderr
    seen = _classes(proc.stdout)
    assert seen.get("live-revert-test") == "fresh", proc.stdout
    assert seen.get("held-revert") == "held", proc.stdout
    assert fresh_backup.exists(), "a FRESH backup holder survives --include-backups"
    assert held_backup.exists(), "a HELD backup holder survives --include-backups"


def test_a_slashed_branch_ref_is_never_truncated(repo: Path) -> None:
    """`refs/heads/feat/foo` is the branch `feat/foo`, not `foo`.

    Truncating at the last slash judged the wrong branch on every consumer, and `git branch -d`
    deleted an unrelated branch that merely shared the basename. Five of 104 live worktree branches
    carry a slash today.
    """
    slashed = repo.parent / "wt-slashed"
    _git(repo, "worktree", "add", "-q", str(slashed), "-b", "feat/foo")
    (slashed / "ahead.txt").write_text("one commit ahead", encoding="utf-8")
    _git(slashed, "add", "-A")
    _git(slashed, "commit", "-qm", "ahead")
    _git(repo, "branch", "foo", "main")  # an unrelated, fully-merged branch sharing the basename
    os.utime(repo / ".git" / "worktrees" / "wt-slashed" / "gitdir", (NOW, NOW))

    proc = _run("--worktrees", str(repo), "--apply", env=_wt_env())
    assert proc.returncode == 0, proc.stderr
    assert _classes(proc.stdout).get("wt-slashed") == "wt-unmerged", proc.stdout
    assert slashed.exists(), "an unmerged slashed branch's worktree must survive"
    assert "foo" in _git(repo, "branch", "--list", "foo"), "the unrelated branch must survive"


def test_an_empty_proc_is_a_dead_probe_not_no_holders(scratch: Path, tmp_path: Path) -> None:
    """A listable but pid-less `/proc` is a dead probe wearing a working one's clothes."""
    empty = tmp_path / "empty-proc"
    empty.mkdir()
    proc = _run("--session", SID, "--apply", env=_env(scratch, FABRIK_PROC_ROOT=str(empty)))
    assert proc.returncode == 0, proc.stderr
    assert _classes(proc.stdout).get("stale-dir") == "probe-error", proc.stdout
    assert (scratch / SLUG / SID / "scratchpad" / "stale-dir").exists()


def test_a_holder_that_appears_after_classification_is_not_removed(scratch: Path) -> None:
    """The classification probe runs seconds before the lock; the removal probe runs inside it."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("scratch_sweep_race_probe", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    pad = scratch / SLUG / SID / "scratchpad"
    entry = pad / "stale-dir"
    rows = [mod.Row(str(entry), "entry", "stale", "classified before the holder arrived")]
    out: list[str] = []

    class _Sink:
        def write(self, s: str) -> None:
            out.append(s)

        def flush(self) -> None:
            pass

    fd = os.open(str(entry / "copy.py"), os.O_RDONLY)  # the holder arrives AFTER classification
    try:
        removed = mod.apply_rows(rows, {"stale"}, out=_Sink())
    finally:
        os.close(fd)
    assert removed == 0, "".join(out)
    assert "KEPT" in "".join(out), "".join(out)
    assert entry.exists(), "a holder that appeared mid-flight must save the entry"


def test_the_apply_line_and_brief_honour_the_flags_actually_passed(scratch: Path) -> None:
    """`render`'s candidate set is what THIS run may remove, not the bare REMOVABLE set.

    With `--include-backups` armed, a REMOVABLE-only test printed no `apply:` line and left
    `--brief` silent while a removal was pending — constraint 2 inverted.
    """
    pad = scratch / SLUG / SID / "scratchpad"
    for d in (pad / "stale-dir", pad / "held-dir"):
        import shutil as _sh

        _sh.rmtree(d)
    backup = pad / "old-backup"
    backup.mkdir()
    (backup / "x.bak").write_text("only copy", encoding="utf-8")
    for p in sorted(backup.rglob("*"), reverse=True):
        _age(p, 9 * HOUR)
    _age(backup, 9 * HOUR)

    dry = _run("--session", SID, "--include-backups", env=_env(scratch))
    assert "apply:" in dry.stdout, dry.stdout
    assert "--include-backups" in dry.stdout, "the printed command must reproduce the listing"

    brief = _run("--session", SID, "--include-backups", "--brief", env=_env(scratch))
    assert brief.stdout.strip(), "--brief must not go silent while a removal is armed"


def test_brief_is_zero_bytes_with_zero_candidates_in_every_mode(
    scratch: Path, graveyard: tuple[Path, Path, Path], repo: Path
) -> None:
    """The close-out shape: nothing to say means nothing printed, in all three modes."""
    fresh_only = scratch / SLUG / SID / "scratchpad"
    for name in ("stale-dir", "held-dir", "kept-dir"):
        import shutil as _sh

        _sh.rmtree(fresh_only / name)
    session = _run("--session", SID, "--brief", env=_env(scratch))
    assert session.stdout == "", repr(session.stdout)

    dead = _run(
        "--dead", "--brief", env=_dead_env(graveyard, SCRATCH_SWEEP_NOW=str(NOW - 40 * DAY))
    )
    assert dead.stdout == "", repr(dead.stdout)

    _git(repo, "checkout", "-q", "--detach")  # every worktree unclassified ⇒ zero candidates
    wt = _run("--worktrees", str(repo), "--brief", env=_wt_env())
    assert wt.stdout == "", repr(wt.stdout)


def test_cwd_scopes_the_classification_to_one_slug(tmp_path: Path) -> None:
    """`--cwd` must actually narrow the listing, not merely appear in the echoed command."""
    root = tmp_path / "claude-1000"
    for slug in ("-opt-fabrik", "-opt-fabrik--claude-worktrees-agent-alpha"):
        pad = root / slug / SID / "scratchpad"
        pad.mkdir(parents=True)
        d = pad / f"residue-{slug[-5:]}"
        d.mkdir()
        _age(d, 9 * HOUR)

    both = _run("--session", SID, env=_env(root))
    assert len(_classes(both.stdout)) == 2, both.stdout

    scoped = _run("--session", SID, "--cwd", "/opt/fabrik", env=_env(root))
    names = _classes(scoped.stdout)
    assert len(names) == 1, scoped.stdout
    assert "alpha" not in " ".join(names), scoped.stdout


def test_an_unreadable_entry_directory_degrades_it_never_crashes_the_run(scratch: Path) -> None:
    """`Path.exists()` RAISES EACCES; it does not return False.

    An entry directory missing the owner x-bit crashed the whole run with a traceback and rc 1,
    which shadowed all three of the deliberate unreadable-tree guards below it — the ones that
    make this fail SAFE rather than loudly.
    """
    pad = scratch / SLUG / SID / "scratchpad"
    blind = pad / "unreadable-dir"
    blind.mkdir()
    (blind / "inside.txt").write_text("x", encoding="utf-8")
    _age(blind / "inside.txt", 9 * HOUR)
    _age(blind, 9 * HOUR)
    os.chmod(blind, 0o000)
    try:
        proc = _run("--session", SID, "--apply", env=_env(scratch))
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert _classes(proc.stdout).get("unreadable-dir") == "probe-error", proc.stdout
        assert blind.exists(), "an unclassifiable entry is never removed"
    finally:
        os.chmod(blind, 0o755)


def test_strict_proc_downgrades_every_removable_class_in_every_mode(
    scratch: Path, graveyard: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """Downgrading `stale` alone INVERTED the protection.

    Under `--strict-proc --include-backups` the plain entries were spared while the ones holding
    revert-test baselines were removed — and the flag was inert in `--dead` and `--worktrees`,
    which is the unattended cron mode.
    """
    proc_root = _fake_proc(tmp_path, uid=os.getuid(), unreadable_fd=True)
    pad = scratch / SLUG / SID / "scratchpad"
    holder = pad / "stale-backup"
    holder.mkdir()
    (holder / "main.py.bak").write_text("the only copy", encoding="utf-8")
    for p in sorted(holder.rglob("*"), reverse=True):
        _age(p, 9 * HOUR)
    _age(holder, 9 * HOUR)
    try:
        session = _run(
            "--session",
            SID,
            "--strict-proc",
            "--include-backups",
            "--apply",
            env=_env(scratch, FABRIK_PROC_ROOT=str(proc_root)),
        )
        assert session.returncode == 0, session.stderr
        seen = _classes(session.stdout)
        assert seen.get("stale-backup") == "probe-error", session.stdout
        assert seen.get("stale-dir") == "probe-error", session.stdout
        assert holder.exists(), "a backup holder must not be the one entry --strict-proc removes"

        env = _dead_env(graveyard, FABRIK_PROC_ROOT=str(proc_root))
        strict = _run("--dead", "--strict-proc", "--apply", env=env)
        assert strict.returncode == 0, strict.stderr
        assert "dead " not in strict.stdout.splitlines()[-1], strict.stdout
        assert (graveyard[0] / SLUG / "bbbbbbbb-2222-2222-2222-222222222222").exists(), (
            strict.stdout
        )
    finally:
        os.chmod(proc_root / "4793" / "fd", 0o755)


def test_a_zero_candidate_apply_does_not_prune_repo_wide(repo: Path) -> None:
    """`git worktree prune` is REPO-WIDE — it drops other sessions' stale registrations too.

    Running it unconditionally made an apply with nothing to remove mutate the repo silently.
    """
    before = _git(repo, "worktree", "list", "--porcelain").count("worktree ")
    _git(repo, "checkout", "-q", "--detach")  # every worktree unclassified ⇒ zero candidates
    proc = _run("--worktrees", str(repo), "--apply", env=_wt_env())
    assert proc.returncode == 0, proc.stderr
    assert "PRUNED" not in proc.stdout, proc.stdout
    after = _git(repo, "worktree", "list", "--porcelain").count("worktree ")
    assert after == before, "a zero-candidate apply must not touch the registry"


def test_a_symlinked_session_dir_can_never_reach_outside_the_root(tmp_path: Path) -> None:
    """The containment guard the plan promised: resolve, then assert `is_relative_to(root)`.

    `is_dir()` FOLLOWS symlinks, so a sid-level symlink pointed the whole classification at another
    tree — and the entries it then yielded were real paths under the target, so the per-entry
    symlink guard never saw a link and `--apply` removed data outside the scratch root entirely.
    """
    root = tmp_path / "claude-1000"
    outside = tmp_path / "elsewhere" / "sid-escape"
    victim = outside / "scratchpad" / "victim"
    victim.mkdir(parents=True)
    (victim / "data.txt").write_text("PRECIOUS", encoding="utf-8")
    for p in sorted(outside.rglob("*"), reverse=True):
        _age(p, 5 * DAY)
    (root / SLUG).mkdir(parents=True)
    escape = root / SLUG / "cafe0000-1111-2222-3333-444444444444"
    escape.symlink_to(outside)

    proc = _run("--session", escape.name, "--apply", env=_env(root))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (victim / "data.txt").read_text(encoding="utf-8") == "PRECIOUS", proc.stdout
    assert "no scratchpad found" in proc.stdout, proc.stdout

    # The same guard one level down: a symlinked scratchpad/ must not escape either.
    inside = root / SLUG / "cafe1111-1111-2222-3333-444444444444"
    inside.mkdir()
    (inside / "scratchpad").symlink_to(outside / "scratchpad")
    proc2 = _run("--session", inside.name, "--apply", env=_env(root))
    assert proc2.returncode == 0, proc2.stdout + proc2.stderr
    assert (victim / "data.txt").read_text(encoding="utf-8") == "PRECIOUS", proc2.stdout


def test_an_unreadable_keep_list_keeps_everything(scratch: Path) -> None:
    """An unreadable keep list silently disabled every protection it carried.

    That is the opposite of "any probe error ⇒ KEEP": the entries the agent explicitly protected
    were the ones that became sweepable.
    """
    pad = scratch / SLUG / SID / "scratchpad"
    os.chmod(pad / ".keep", 0o000)
    try:
        proc = _run("--session", SID, "--apply", env=_env(scratch))
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "keep-unreadable" in proc.stdout, proc.stdout
        assert (pad / "kept-dir").exists(), "an explicitly kept entry must survive"
        assert (pad / "stale-dir").exists(), "nothing is provably unprotected"
    finally:
        os.chmod(pad / ".keep", 0o644)


def test_a_truncated_walk_never_makes_the_hook_line_reprint(scratch: Path) -> None:
    """A budget-truncated count is a LOWER BOUND, and it varies run to run.

    The unwalked entries default to `fresh`, so the same scratchpad reports 300 then 340 and reads
    as "grown". Measured on the three largest live scratchpads during Phase B's fire-rate
    confirmation: the line reprinted on EVERY SessionStart — the wallpaper the stamp exists to
    prevent. Once said for a sid, an uncertain count never says it again.
    """
    pad = scratch / SLUG / SID / "scratchpad"
    for i in range(40):
        d = pad / f"bulk-{i:02d}"
        d.mkdir()
        (d / "f").write_text("x" * 100, encoding="utf-8")
        _age(d / "f", 9 * HOUR)
        _age(d, 9 * HOUR)

    payload = json.dumps(
        {"session_id": SID, "cwd": "/opt/fabrik", "hook_event_name": "SessionStart"}
    )
    first = _run("--hook", "--session", SID, env=_env(scratch), stdin=payload)
    assert "🧹 SCRATCH:" in first.stdout, first.stdout

    # A tiny budget forces truncation, so the count wobbles below its true value.
    for _ in range(3):
        again = _run(
            "--hook",
            "--session",
            SID,
            env=_env(scratch, SCRATCH_SWEEP_HOOK_BUDGET="5"),
            stdin=payload,
        )
        assert again.stdout == "", f"a truncated count must never reprint: {again.stdout!r}"

    # The third leg is what makes this a grader rather than a restatement of the first two: a
    # truncated run must not WRITE the stamp either. Without that, the silence above comes only
    # from `len(candidates) <= previous` and the guard can be deleted with the test still green
    # (proven by mutation, round 2). So walk the SAME pad COMPLETELY: a stamp a truncated run had
    # lowered to 5 makes this unchanged 40 read as growth and reprint. It must stay silent.
    complete = _run("--hook", "--session", SID, env=_env(scratch), stdin=payload)
    assert complete.stdout == "", (
        "a complete walk over an UNCHANGED pad reprinted — a truncated run wrote the stamp down, "
        f"so its own lower bound now reads as growth: {complete.stdout!r}"
    )

    # And the stamp is not a permanent gag: real growth still speaks (the F2 invariant).
    for i in range(40, 46):
        d = pad / f"bulk-{i:02d}"
        d.mkdir()
        (d / "f").write_text("x" * 100, encoding="utf-8")
        _age(d / "f", 9 * HOUR)
        _age(d, 9 * HOUR)
    grown = _run("--hook", "--session", SID, env=_env(scratch), stdin=payload)
    import re as _re

    def _count(text: str) -> int:
        m = _re.search(r"SCRATCH: (\d+) stale", text)
        assert m, f"no count in {text!r}"
        return int(m.group(1))

    assert "🧹 SCRATCH:" in grown.stdout, (
        "a COMPLETE walk over a grown pad must speak again — the stamp is a high-water mark, not "
        f"a permanent gag: {grown.stdout!r}"
    )
    assert _count(grown.stdout) == _count(first.stdout) + 6, grown.stdout
    settled = _run("--hook", "--session", SID, env=_env(scratch), stdin=payload)
    assert settled.stdout == "", f"an unchanged complete walk stays silent: {settled.stdout!r}"


def test_the_brief_shows_the_oldest_candidates_and_counts_all_of_them(scratch: Path) -> None:
    """The close-out sample is capped AND sorted by age — a head-slice hid the real residue.

    `--brief` prints into the agent's own context at every close, fleet-wide, so it shows
    `BRIEF_ROWS` candidates and a count. `classify_session` yields entries in DIRECTORY order,
    so the cap alone showed five day-old dirs and pushed every 40-day one behind "and N more"
    (round 2) — the exact rows the agent needed to see. The count stays over the whole table.
    """
    pad = scratch / SLUG / SID / "scratchpad"
    for i in range(8):  # young, and first in name order
        d = pad / f"aaa-{i:02d}"
        d.mkdir()
        (d / "f").write_text("x", encoding="utf-8")
        _age(d / "f", 25 * HOUR)
        _age(d, 25 * HOUR)
    for i in range(3):  # ancient, and last in name order
        d = pad / f"zzz-{i:02d}"
        d.mkdir()
        (d / "f").write_text("x", encoding="utf-8")
        _age(d / "f", 40 * DAY)
        _age(d, 40 * DAY)

    out = _run("--session", SID, "--brief", env=_env(scratch)).stdout
    assert out.count("zzz-") == 3, f"the three oldest must all be shown, not hidden:\n{out}"
    shown = [ln for ln in out.splitlines() if " · stale · " in ln]
    assert len(shown) == 5, out
    # the count is the DENOMINATOR — it covers every candidate, not the five that fit. The base
    # fixture contributes its own stale entries, so both numbers are read from this run's output.
    total = int(re.search(r"stale (\d+)", out).group(1))  # type: ignore[union-attr]
    assert total >= 11, out
    assert f"… and {total - 5} more" in out, out

    full = _run("--session", SID, env=_env(scratch)).stdout
    assert full.count("aaa-") == 8 and full.count("zzz-") == 3, "the dry run is uncapped"
    assert "… and" not in full, full
