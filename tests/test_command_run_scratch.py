"""A run's persistent scratch dir (kaizen 01M4V0B03B): `start` gives every run a scratch dir under the
MAIN checkout's `.tmp/runs/`, which survives a WSL /tmp wipe, and prints `SCRATCH: <path>`.

The unit tests drive the helpers against throwaway git repos; the subprocess tests drive `start`
through the `COMMAND_RUN_DIR` seam, which keeps every suite out of a live checkout.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "command_run.py"
DAY = 86400


def _load():
    spec = importlib.util.spec_from_file_location("command_run_scratch_ut", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cr = _load()


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def _repo(tmp_path: Path, gitignore: str | None = None) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    if gitignore is not None:
        (repo / ".gitignore").write_text(gitignore, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    return repo


def _ignored(repo: Path) -> bool:
    return _git(repo, "check-ignore", "-q", "--", ".tmp/runs/x").returncode == 0


def _cr(run_dir: Path, *args: str, sid: str = "s1", cwd: Path | None = None):
    env = {
        "PATH": "/usr/bin:/bin",
        "COMMAND_RUN_DIR": str(run_dir),
        "KAIZEN_EVENTS_DIR": str(run_dir.parent / "events"),
        "CLAUDE_SESSION_ID": sid,
    }
    return subprocess.run(
        ["python3", str(SCRIPT), *args],
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


@pytest.fixture
def no_seam(monkeypatch):
    monkeypatch.delenv("COMMAND_RUN_DIR", raising=False)


def test_start_scratch_lands_in_the_main_checkout(tmp_path: Path, no_seam) -> None:
    """Behaviour 1: the root is <main checkout>/.tmp/runs, and the dir is keyed by session and command."""
    repo = _repo(tmp_path, gitignore=".tmp/\n")
    path, notes = cr._make_scratch(
        str(repo), "abc", "fabrik-task", "2026-10-14T01:46:01+0300", None
    )
    assert path is not None, notes
    assert path == repo / ".tmp" / "runs" / "abc" / "fabrik-task-2026-10-14T01-46-01-0300"
    assert path.is_dir() and _ignored(repo)


def test_exclude_is_added_once_or_no_scratch(tmp_path: Path, no_seam) -> None:
    """Behaviour 2: an un-ignored repo gets ONE info/exclude line; a negation keeps it unignored → no dir."""
    repo = _repo(tmp_path)
    assert not _ignored(repo)
    for key in ("k1", "k2"):
        path, notes = cr._make_scratch(str(repo), "abc", "fabrik-review", key, None)
        assert path is not None and path.is_dir(), notes
    exclude = (repo / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    assert exclude.splitlines().count("/.tmp/runs/") == 1, exclude
    assert _ignored(repo)
    assert _git(repo, "status", "--porcelain").stdout == ""

    (tmp_path / "neg").mkdir()
    neg = _repo(tmp_path / "neg", gitignore="!/.tmp/runs/\n")
    path, notes = cr._make_scratch(str(neg), "abc", "fabrik-review", "k1", None)
    assert path is None and notes, notes
    assert not (neg / ".tmp" / "runs").exists()


def _age(path: Path, days: float) -> None:
    t = time.time() - days * DAY
    for dirpath, _dirnames, filenames in os.walk(path):
        for name in filenames:
            os.utime(Path(dirpath) / name, (t, t))
        os.utime(dirpath, (t, t))


def test_prune_ages_by_newest_file_and_spares_live_dirs(tmp_path: Path, no_seam) -> None:
    """Behaviour 3: age is the NEWEST mtime in the tree; current, referenced and worktree dirs survive."""
    root = tmp_path / "runs"
    stale = root / "old" / "fabrik-task-a"
    nested_fresh = root / "old" / "fabrik-task-b"
    referenced = root / "other" / "fabrik-review-c"
    worktree = root / "other" / "fabrik-review-d"
    current = root / "me" / "fabrik-task-e"
    for d in (stale, nested_fresh / "pin", referenced, worktree, current):
        d.mkdir(parents=True)
        (d / "f.md").write_text("x", encoding="utf-8")
    (worktree / ".git").write_text("gitdir: /nowhere\n", encoding="utf-8")
    for d in (stale, nested_fresh, referenced, worktree, current):
        _age(d, 20)
    (nested_fresh / "pin" / "brief.md").write_text("today", encoding="utf-8")  # a write deep inside

    gone_sid = root / "emptied" / "fabrik-task-f"
    gone_sid.mkdir(parents=True)
    _age(gone_sid, 20)

    notes = cr._prune_scratch(root, keep={current.resolve(), referenced.resolve()})
    assert not stale.exists()
    assert nested_fresh.exists(), "a write in a subdir keeps the run"
    assert referenced.exists() and current.exists() and worktree.exists()
    assert any("fabrik-review-d" in n for n in notes), notes
    assert not (root / "emptied").exists(), "an emptied <sid> dir is removed"


def test_worktree_run_scratch_lives_in_the_main_checkout(tmp_path: Path, no_seam) -> None:
    """Behaviour 4: a run started inside a linked worktree writes to the MAIN checkout's .tmp/runs."""
    repo = _repo(tmp_path)
    wt = tmp_path / "wt"
    assert _git(repo, "worktree", "add", "-q", "--detach", str(wt)).returncode == 0
    path, notes = cr._make_scratch(str(wt), "abc", "fabrik-task", "k", None)
    assert path is not None, notes
    assert path.is_relative_to(repo / ".tmp" / "runs"), path
    assert _ignored(repo) and _ignored(wt)
    assert _git(repo, "worktree", "remove", "--force", str(wt)).returncode == 0
    assert path.is_dir(), "removing the worktree leaves the run's scratch"


def test_resumed_run_in_a_new_session_reuses_the_seed_scratch(tmp_path: Path, no_seam) -> None:
    """Behaviour 5: a resume after a restart runs in a NEW session; it keeps the seed's dir."""
    repo = _repo(tmp_path, gitignore=".tmp/\n")
    first, _ = cr._make_scratch(
        str(repo), "old-sid", "fabrik-task", "2026-10-13T10:00:00+0300", None
    )
    assert first is not None
    (first / "design.md").write_text("kept", encoding="utf-8")
    seed = {
        "scratch": str(first),
        "session_id": "old-sid",
        "started_at": "2026-10-13T10:00:00+0300",
    }
    again, _ = cr._make_scratch(
        str(repo), "new-sid", "fabrik-task", "2026-10-13T10:00:00+0300", seed
    )
    assert again == first and (again / "design.md").read_text(encoding="utf-8") == "kept"

    seed_gone = {"session_id": "old-sid", "scratch": str(tmp_path / "vanished")}
    derived, _ = cr._make_scratch(
        str(repo), "new-sid", "fabrik-task", "2026-10-13T10:00:00+0300", seed_gone
    )
    assert derived == first, "a seed whose dir is gone derives the path from the SEED's session"


def test_scratch_failure_never_refuses_start(tmp_path: Path) -> None:
    """Behaviour 6: start prints SCRATCH under the COMMAND_RUN_DIR seam, and a scratch failure never refuses."""
    run_dir = tmp_path / "runs"
    out = _cr(run_dir, "start", "--command", "fabrik-review", "--phases", "2", "--terminal", "t")
    assert out.returncode == 0, out.stdout + out.stderr
    lines = [ln for ln in out.stdout.splitlines() if ln.startswith("SCRATCH: ")]
    assert len(lines) == 1, out.stdout
    path = Path(lines[0][len("SCRATCH: ") :])
    assert path.is_dir() and path.is_relative_to(run_dir / "scratch"), path
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    assert rec["scratch"] == str(path)

    blocked = tmp_path / "runs2"
    blocked.mkdir()
    (blocked / "scratch").write_text("a file where the dir should be", encoding="utf-8")
    out = _cr(blocked, "start", "--command", "fabrik-review", "--phases", "2", "--terminal", "t")
    assert out.returncode == 0, out.stdout + out.stderr
    # line-anchored: the run-bound folder's own `RUN-SCRATCH:` line carries the same substring
    assert not re.search(r"^SCRATCH: ", out.stdout, re.M) and "scratch" in out.stderr.lower(), (
        out.stdout + out.stderr
    )
    rec = json.loads((blocked / "s1.json").read_text(encoding="utf-8"))
    assert rec["state"] == "running" and "scratch" not in rec
    # the HOME-override isolation style (no COMMAND_RUN_DIR) run from INSIDE a repo: the scratch goes
    # beside the isolated records, never into the checkout (it once landed in /opt/fabrik/.tmp/runs)
    home = tmp_path / "home"
    (tmp_path / "homecase").mkdir()
    repo = _repo(tmp_path / "homecase")
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(home),
        "KAIZEN_EVENTS_DIR": str(tmp_path / "events3"),
        "CLAUDE_SESSION_ID": "s3",
        "PYTEST_CURRENT_TEST": os.environ.get("PYTEST_CURRENT_TEST", "x"),
    }
    out = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "start",
            "--command",
            "fabrik-review",
            "--phases",
            "2",
            "--terminal",
            "t",
        ],
        cwd=str(repo),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert not (repo / ".tmp").exists(), "a test start never writes into the checkout it runs from"
    assert f"SCRATCH: {home / '.claude' / 'state' / 'command-runs' / 'scratch'}" in out.stdout, (
        out.stdout
    )


def test_a_resume_keeps_scratch_across_sessions_and_an_ignore_change(
    tmp_path: Path, no_seam
) -> None:
    """Review A1+A3: a wall-blocked run resumed in a NEW session says its scratch is kept (never "belongs
    to a dead session"), and a seed dir that already exists is reused even if the repo stopped ignoring it."""
    run_dir = tmp_path / "runs"
    assert (
        _cr(
            run_dir, "start", "--command", "fabrik-review", "--phases", "2", "--terminal", "t"
        ).returncode
        == 0
    )
    first = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))["scratch"]
    out = _cr(
        run_dir,
        "blocked",
        "--command",
        "fabrik-review",
        "--wall",
        "--reason",
        "quota wall",
        "--feedback",
        "confusion: none · waste: none · change: none · filed: none — surfaces exercised: test harness wall block",
    )
    assert out.returncode == 0, out.stdout + out.stderr
    seed = re.search(r"--resume-from (\S+)", out.stdout).group(1)
    out = _cr(
        run_dir,
        "start",
        "--command",
        "fabrik-review",
        "--phases",
        "2",
        "--terminal",
        "t",
        "--resume-from",
        seed,
        sid="s2",
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert f"SCRATCH: {first}" in out.stdout and "dead session" not in out.stdout, out.stdout

    repo = _repo(tmp_path, gitignore=".tmp/\n")
    path, _ = cr._make_scratch(str(repo), "old", "fabrik-task", "k", None)
    assert path is not None
    (path / "design.md").write_text("kept", encoding="utf-8")
    (repo / ".gitignore").write_text(".tmp/\n!/.tmp/\n!/.tmp/runs/\n", encoding="utf-8")
    assert not _ignored(repo)
    again, notes = cr._make_scratch(
        str(repo), "new", "fabrik-task", "k", {"scratch": str(path), "session_id": "old"}
    )
    assert again == path and notes, (again, notes)


def test_a_seed_scratch_outside_the_root_is_never_reused(tmp_path: Path, no_seam) -> None:
    """Closing pass A: a seed naming a dir OUTSIDE the current root (another repo, or a live checkout
    while the test seam is on) is not reused — the run gets its own dir under the root and a NOTE."""
    elsewhere = tmp_path / "other" / ".tmp" / "runs" / "sid" / "fabrik-task-k"
    elsewhere.mkdir(parents=True)
    seam = tmp_path / "seam"
    path, notes = cr._make_scratch(
        "", "new", "fabrik-task", "k", {"scratch": str(elsewhere), "session_id": "sid"}, root=seam
    )
    assert path is not None and path.is_relative_to(seam), path
    assert any("outside" in n for n in notes), notes

    repo = _repo(tmp_path, gitignore=".tmp/\n")
    path, notes = cr._make_scratch(
        str(repo), "new", "fabrik-task", "k", {"scratch": str(elsewhere), "session_id": "sid"}
    )
    assert path is not None and path.is_relative_to(repo / ".tmp" / "runs"), path


# ── run-bound scratch (scratch lifecycle plan, Phase A — rows A2, A3) ────────────────────────────
SWEEP_LIB = ROOT / "scripts"


def _slug(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def _cr_rs(
    run_dir: Path,
    harness: Path,
    *args: str,
    sid: str = "s1",
    cwd: Path | None = None,
    lib: Path | None = SWEEP_LIB,
):
    """A subprocess call with the run-scratch seams: the harness root and the module the mint loads."""
    env = {
        "PATH": "/usr/bin:/bin",
        "COMMAND_RUN_DIR": str(run_dir),
        "KAIZEN_EVENTS_DIR": str(run_dir.parent / "events"),
        "CLAUDE_SESSION_ID": sid,
        "SCRATCH_SWEEP_ROOT": str(harness),
        "FABRIK_SCRATCH_SWEEP_LIB": str(lib) if lib is not None else "",
        "FABRIK_SCRATCH_SWEEP": "0",
    }
    return subprocess.run(
        ["python3", str(SCRIPT), *args],
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _start(run_dir: Path, harness: Path, repo: Path, sid: str = "s1", lib: Path | None = SWEEP_LIB):
    return _cr_rs(
        run_dir,
        harness,
        "start",
        "--command",
        "fabrik-probe",
        "--phases",
        "1",
        "--terminal",
        "t",
        sid=sid,
        cwd=repo,
        lib=lib,
    )


def _session_dir(harness: Path, repo: Path, sid: str = "s1") -> Path:
    d = harness / _slug(repo) / sid
    (d / "scratchpad").mkdir(parents=True)
    return d


def _run_scratch_line(out: str) -> str:
    m = re.search(r"^RUN-SCRATCH: (.+)$", out, re.M)
    assert m, out
    return m.group(1)


def test_start_mints_a_marked_run_folder(tmp_path: Path) -> None:
    """A2: `start` mints `<session dir>/scratchpad/run-<key>/.owner` and records `run_scratch`."""
    repo = _repo(tmp_path, gitignore=".tmp/\n")
    harness = tmp_path / "harness"
    sess = _session_dir(harness, repo)
    run_dir = tmp_path / "runs"
    out = _start(run_dir, harness, repo)
    assert out.returncode == 0, out.stdout + out.stderr
    folder = Path(_run_scratch_line(out.stdout))
    assert folder.parent == sess / "scratchpad" and folder.name.startswith("run-"), folder
    owner = json.loads((folder / ".owner").read_text(encoding="utf-8"))
    assert owner["sid"] == "s1" and owner["command"] == "fabrik-probe", owner
    assert owner["state"] == "running" and owner["closed_at"] is None, owner
    assert owner["key"] == folder.name[len("run-") :], owner
    assert Path(owner["repo"]).resolve() == (repo / ".git").resolve(), owner
    assert isinstance(owner["created"], float), owner
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    assert rec["run_scratch"] == str(folder), rec


def test_same_second_starts_get_distinct_keys() -> None:
    """A2 (P4): the record key has one-second resolution, so the folder key carries a suffix."""
    keys = {cr._run_scratch_key("fabrik-probe", "2026-10-15T01:00:00+0300") for _ in range(20)}
    assert len(keys) == 20, keys
    assert all(k.startswith("fabrik-probe-2026-10-15T01-00-00-0300-") for k in keys), keys


def test_mint_fails_open_without_a_session_dir(tmp_path: Path) -> None:
    """A3: no harness session directory → nothing minted, one `none` line, the start succeeds."""
    repo = _repo(tmp_path, gitignore=".tmp/\n")
    harness = tmp_path / "harness"
    harness.mkdir()
    out = _start(tmp_path / "runs", harness, repo)
    assert out.returncode == 0, out.stdout + out.stderr
    assert re.search(r"^RUN-SCRATCH: none — no harness session directory", out.stdout, re.M), (
        out.stdout
    )
    assert not list(harness.rglob("run-*"))


def test_mint_fails_open_without_the_hub_module(tmp_path: Path) -> None:
    """A3: the hub module cannot be loaded → nothing minted, one `none` line, the start succeeds."""
    repo = _repo(tmp_path, gitignore=".tmp/\n")
    harness = tmp_path / "harness"
    sess = _session_dir(harness, repo)
    out = _start(tmp_path / "runs", harness, repo, lib=tmp_path / "no-such-dir")
    assert out.returncode == 0, out.stdout + out.stderr
    assert re.search(
        r"^RUN-SCRATCH: none — the scratch sweep could not be loaded", out.stdout, re.M
    ), out.stdout
    assert not list((sess / "scratchpad").iterdir())


def test_mint_names_an_older_hub_module(tmp_path: Path) -> None:
    """A3: a hub scratch_sweep.py from before run-bound scratch (no RUN_PREFIX) mints nothing and
    SAYS so — never a raw AttributeError (found live on this branch's own first start)."""
    repo = _repo(tmp_path, gitignore=".tmp/\n")
    harness = tmp_path / "harness"
    sess = _session_dir(harness, repo)
    old = tmp_path / "old-lib"
    old.mkdir()
    (old / "scratch_sweep.py").write_text(
        "from pathlib import Path\n"
        "def _scratch_root():\n    return Path('/nowhere')\n"
        "def find_session_dirs(root, sid, cwd=None):\n    return []\n",
        encoding="utf-8",
    )
    out = _start(tmp_path / "runs", harness, repo, lib=old)
    assert out.returncode == 0, out.stdout + out.stderr
    assert re.search(
        r"^RUN-SCRATCH: none — the hub's scratch_sweep\.py predates", out.stdout, re.M
    ), out.stdout
    assert "AttributeError" not in out.stdout
    assert not list((sess / "scratchpad").iterdir())


def test_a_mark_never_raises(tmp_path: Path) -> None:
    """A4: a folder whose parent cannot be entered makes the mark a silent no-op — a close (and
    a start's P11 mark) never fails on scratch, whatever the filesystem raises."""
    locked = tmp_path / "locked"
    (locked / "run-y").mkdir(parents=True)
    locked.chmod(0)
    try:
        cr._mark_run_scratch({"run_scratch": str(locked / "run-y")}, "done", "s")
    finally:
        locked.chmod(0o755)


def test_close_with_an_unenterable_folder_still_closes(tmp_path: Path) -> None:
    """A4: the full close path — record closed, ledger line printed — even when the marker is
    unreachable."""
    repo, harness, run_dir, folder = _minted(tmp_path)
    folder.parent.chmod(0)
    try:
        out = _cr_rs(
            run_dir,
            harness,
            "done",
            "--command",
            "fabrik-probe",
            "--evidence",
            "e",
            "--feedback",
            _FB,
            cwd=repo,
        )
    finally:
        folder.parent.chmod(0o755)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "run record closed" in out.stdout, out.stdout + out.stderr
    assert "error, continuing" not in out.stderr, out.stderr


def test_a_record_that_did_not_persist_leaves_no_folder(tmp_path: Path) -> None:
    """A2: a start whose record save fails removes the folder it just minted — nothing would ever
    heartbeat, mark or close it."""
    repo = _repo(tmp_path, gitignore=".tmp/\n")
    harness = tmp_path / "harness"
    sess = _session_dir(harness, repo)
    run_dir = tmp_path / "runs"
    run_dir.mkdir()
    (run_dir / "s1.json.tmp").mkdir()  # save() writes here first — a directory makes it fail
    out = _start(run_dir, harness, repo)
    assert re.search(
        r"^RUN-SCRATCH: none — the run record could not be written", out.stdout, re.M
    ), out.stdout + out.stderr
    assert not list((sess / "scratchpad").iterdir())


def test_the_mint_never_touches_sys_path(tmp_path: Path, monkeypatch) -> None:
    """A3 (P15): the hub module loads by file location, registered privately — `sys.path`
    unchanged — and a mint through the REAL module succeeds."""
    repo = _repo(tmp_path, gitignore=".tmp/\n")
    harness = tmp_path / "harness"
    sess = _session_dir(harness, repo, sid="sp")
    monkeypatch.setenv("SCRATCH_SWEEP_ROOT", str(harness))
    monkeypatch.setenv("FABRIK_SCRATCH_SWEEP_LIB", str(SWEEP_LIB))
    before = list(sys.path)
    folder, why = cr._mint_run_scratch("sp", str(repo), "fabrik-task", "k-1", str(repo))
    assert sys.path == before
    assert folder is not None and folder.parent == sess / "scratchpad", why


# ── rows A4, A5, A6 — mark at close, the handoff refusal, the heartbeat ──────────────────────────
_FB = "confusion: none · waste: none · change: none · filed: none — harness setup"


def _minted(tmp_path: Path, sid: str = "s1") -> tuple[Path, Path, Path, Path]:
    """A started run with a minted folder: (repo, harness, run_dir, folder)."""
    repo = _repo(tmp_path, gitignore=".tmp/\n")
    harness = tmp_path / "harness"
    _session_dir(harness, repo, sid=sid)
    run_dir = tmp_path / "runs"
    out = _start(run_dir, harness, repo, sid=sid)
    assert out.returncode == 0, out.stdout + out.stderr
    return repo, harness, run_dir, Path(_run_scratch_line(out.stdout))


def _owner(folder: Path) -> dict:
    return json.loads((folder / ".owner").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("verb", "extra", "want"),
    [
        ("done", ["--evidence", "e"], "done"),
        ("blocked", ["--reason", "a plain reason"], "done"),
        ("blocked", ["--reason", "hit it", "--wall"], "resumable"),
        ("blocked", ["--reason", "the fleet quota exhausted"], "resumable"),
        ("handoff", ["--reason", "r"], "done"),
    ],
)
def test_close_marks_state(tmp_path: Path, verb: str, extra: list[str], want: str) -> None:
    """A4 (P5): done, handoff and a plain blocked mark `done`; a wall — flag OR reason — `resumable`."""
    repo, harness, run_dir, folder = _minted(tmp_path)
    if verb == "handoff":
        art = tmp_path / "next.md"
        art.write_text("# next\n\n## RESUME\n- row 1\n", encoding="utf-8")
        extra = [*extra, "--resume", str(art)]
    out = _cr_rs(
        run_dir, harness, verb, "--command", "fabrik-probe", *extra, "--feedback", _FB, cwd=repo
    )
    assert out.returncode == 0, out.stdout + out.stderr
    owner = _owner(folder)
    assert owner["state"] == want, owner
    assert isinstance(owner["closed_at"], float), owner


def test_nested_close_marks_its_own_folder(tmp_path: Path) -> None:
    """A4: a nested run's close marks the CHILD's folder, and the parent's stays `running`."""
    repo, harness, run_dir, parent_folder = _minted(tmp_path)
    child = _cr_rs(
        run_dir,
        harness,
        "start",
        "--command",
        "fabrik-probe-child",
        "--phases",
        "1",
        "--terminal",
        "t",
        cwd=repo,
    )
    assert child.returncode == 0, child.stdout + child.stderr
    child_folder = Path(_run_scratch_line(child.stdout))
    assert child_folder != parent_folder
    out = _cr_rs(
        run_dir,
        harness,
        "done",
        "--command",
        "fabrik-probe-child",
        "--evidence",
        "e",
        "--feedback",
        _FB,
        cwd=repo,
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert _owner(child_folder)["state"] == "done"
    assert _owner(parent_folder)["state"] == "running"


def test_close_without_run_scratch_is_unchanged(tmp_path: Path) -> None:
    """A4: a record carrying no `run_scratch` closes exactly as before (no marker, no error)."""
    rec: dict = {"command": "fabrik-probe", "state": "running"}
    cr._mark_run_scratch(rec, "done", "s1")  # must not raise
    assert "run_scratch" not in rec


@pytest.mark.parametrize(
    "spelling",
    ["abs", "trailing-slash", "realpath", "relative", "run-scratch-line"],
)
def test_handoff_refuses_its_own_run_folder(tmp_path: Path, spelling: str) -> None:
    """A5 (P7): a resume text naming the run's own folder is refused five ways; the record stays
    `running` and the marker is untouched."""
    repo, harness, run_dir, folder = _minted(tmp_path)
    link = tmp_path / "harness-link"
    link.symlink_to(harness)
    text = {
        "abs": f"see {folder}/notes.md",
        "trailing-slash": f"see {folder}/",
        "realpath": f"see {link / folder.relative_to(harness)}",
        "relative": f"see scratchpad/{folder.name}/notes.md",
        "run-scratch-line": f"RUN-SCRATCH: {folder}",
    }[spelling]
    art = tmp_path / "next.md"
    art.write_text(f"# next\n\n## RESUME\n- {text}\n", encoding="utf-8")
    out = _cr_rs(
        run_dir,
        harness,
        "handoff",
        "--command",
        "fabrik-probe",
        "--reason",
        "r",
        "--resume",
        str(art),
        "--feedback",
        _FB,
        cwd=repo,
    )
    assert out.returncode == 1, out.stdout + out.stderr
    assert "own scratch folder" in out.stdout, out.stdout
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    assert rec["state"] == "running", rec
    assert _owner(folder)["state"] == "running"


@pytest.mark.parametrize("other", ["another-folder", "prefix-sharing", "abs-prefix-sharing"])
def test_handoff_naming_another_folder_passes(tmp_path: Path, other: str) -> None:
    """A5 (P7): another folder, or one whose name merely EXTENDS this one's — relative or absolute —
    is not refused."""
    repo, harness, run_dir, folder = _minted(tmp_path)
    text = {
        "another-folder": "see scratchpad/run-elsewhere-123456/x.md",
        "prefix-sharing": f"see scratchpad/{folder.name}2/x.md",
        "abs-prefix-sharing": f"see {folder}2/x.md",
    }[other]
    art = tmp_path / "next.md"
    art.write_text(f"# next\n\n## RESUME\n- {text}\n", encoding="utf-8")
    out = _cr_rs(
        run_dir,
        harness,
        "handoff",
        "--command",
        "fabrik-probe",
        "--reason",
        "r",
        "--resume",
        str(art),
        "--feedback",
        _FB,
        cwd=repo,
    )
    assert out.returncode == 0, out.stdout + out.stderr


def test_heartbeat_bumps_the_marker(tmp_path: Path) -> None:
    """A6: `step`, `round` and `dispatch` each move the marker's mtime forward."""
    repo, harness, run_dir, folder = _minted(tmp_path)
    marker = folder / ".owner"
    for verb, extra in (
        ("step", ["--phase", "1", "--title", "x"]),
        ("dispatch", ["--seats", "1"]),
        ("round", ["--findings", "0", "--confirmed", "0", "--own-fix", "0"]),
    ):
        os.utime(marker, (1_000_000, 1_000_000))
        out = _cr_rs(run_dir, harness, verb, *extra, cwd=repo)
        assert out.returncode == 0, (verb, out.stdout + out.stderr)
        assert marker.stat().st_mtime > 1_000_000, verb
    shutil.rmtree(folder)  # a vanished folder is skipped silently
    out = _cr_rs(run_dir, harness, "step", "--phase", "1", "--title", "y", cwd=repo)
    assert out.returncode == 0, out.stdout + out.stderr


def _start_cmd(run_dir: Path, harness: Path, repo: Path, command: str):
    return _cr_rs(
        run_dir,
        harness,
        "start",
        "--command",
        command,
        "--phases",
        "1",
        "--terminal",
        "t",
        cwd=repo,
    )


def test_start_marks_a_dropped_stack_done(tmp_path: Path) -> None:
    """A7 (P11): the next start over an `expired` record (left by the coroner) marks that record's
    folder AND its parked parent's folder `done` — a new run proves the old ones are over."""
    repo, harness, run_dir, parent_folder = _minted(tmp_path)
    child = _start_cmd(run_dir, harness, repo, "fabrik-probe-child")
    child_folder = Path(_run_scratch_line(child.stdout))
    rec_path = run_dir / "s1.json"
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    rec["state"] = "expired"  # what the coroner's TTL branch writes, with no marker change
    rec_path.write_text(json.dumps(rec), encoding="utf-8")
    out = _start_cmd(run_dir, harness, repo, "fabrik-probe-next")
    assert out.returncode == 0, out.stdout + out.stderr
    assert _owner(child_folder)["state"] == "done"
    assert _owner(parent_folder)["state"] == "done"


def test_start_never_marks_an_already_closed_folder_again(tmp_path: Path) -> None:
    """A7: a folder a close already marked `done` keeps its own `closed_at` — the grace never restarts."""
    repo, harness, run_dir, folder = _minted(tmp_path)
    out = _cr_rs(
        run_dir,
        harness,
        "done",
        "--command",
        "fabrik-probe",
        "--evidence",
        "e",
        "--feedback",
        _FB,
        cwd=repo,
    )
    assert out.returncode == 0, out.stdout + out.stderr
    closed = _owner(folder)["closed_at"]
    out = _start_cmd(run_dir, harness, repo, "fabrik-probe-next")
    assert out.returncode == 0, out.stdout + out.stderr
    assert _owner(folder)["closed_at"] == closed


def test_start_over_a_wall_record_leaves_its_folder_resumable(tmp_path: Path) -> None:
    """A7 (P11's exception): a `blocked` + `wall` record's folder is P12's alone — a plain start
    over it never marks it."""
    repo, harness, run_dir, folder = _minted(tmp_path)
    out = _cr_rs(
        run_dir,
        harness,
        "blocked",
        "--command",
        "fabrik-probe",
        "--reason",
        "x",
        "--wall",
        "--feedback",
        _FB,
        cwd=repo,
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert _owner(folder)["state"] == "resumable"
    out = _start_cmd(run_dir, harness, repo, "fabrik-probe-other")
    assert out.returncode == 0, out.stdout + out.stderr
    assert _owner(folder)["state"] == "resumable"
