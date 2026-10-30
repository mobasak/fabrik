"""`scripts/sysadmin/install_mesh.sh` (W-6e656dac T04, spec § Lifecycle) and the tracked mesh copies.

The installer puts a reviewed copy of the three tracked mesh scripts (`scripts/sysadmin/mesh/`) into
`~/.claude/bin`: every copy passes `bash -n` and the harness first, each live file is backed up to
`~/.claude/bin/backups/<f>.backup.<ts>` before anything is replaced, and each replace is a rename. Every test here
runs it against a TEMP home and a temp destination with a stub harness — never the operator's ~/.claude/bin.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "scripts" / "sysadmin" / "install_mesh.sh"
MESH = ROOT / "scripts" / "sysadmin" / "mesh"
FILES = ("claude-selfwatch.sh", "claude-reboot-sweep.sh", "claude-mesh-test.sh")


def _src(tmp: Path, **override: str) -> Path:
    src = tmp / "src"
    src.mkdir()
    for f in FILES:
        (src / f).write_text(
            override.get(f, f"#!/usr/bin/env bash\necho new {f}\n"), encoding="utf-8"
        )
    return src


def _dest(tmp: Path) -> Path:
    dest = tmp / "home" / ".claude" / "bin"
    dest.mkdir(parents=True)
    for f in FILES:
        (dest / f).write_text(f"#!/usr/bin/env bash\necho old {f}\n", encoding="utf-8")
        (dest / f).chmod(0o755)
    return dest


def _harness(tmp: Path, rc: int = 0) -> tuple[Path, Path]:
    log = tmp / "harness.log"
    h = tmp / "harness.sh"
    h.write_text(
        f'#!/usr/bin/env bash\necho "src=$MESH_TEST_SRC" >> "{log}"\nexit {rc}\n', encoding="utf-8"
    )
    return h, log


def _run(
    tmp: Path,
    *args: str,
    harness: Path | None,
    stubs: Path | None = None,
    home: bool = True,
) -> subprocess.CompletedProcess[str]:
    """`harness=None` leaves MESH_INSTALL_HARNESS unset; `stubs` is a folder put FIRST on PATH; `home=False` runs
    with HOME unset."""
    env = {"PATH": (f"{stubs}:" if stubs else "") + "/usr/bin:/bin"}
    if home:
        env["HOME"] = str(tmp / "home")  # never the operator's home
    if harness is not None:
        env["MESH_INSTALL_HARNESS"] = str(harness)
    return subprocess.run(
        ["bash", str(INSTALL), *args], capture_output=True, text=True, timeout=60, env=env
    )


def _stub(folder: Path, name: str, body: str) -> Path:
    """An executable stub on PATH; asserted executable, since a non-executable one falls through to the real binary."""
    folder.mkdir(exist_ok=True)
    p = folder / name
    p.write_text("#!/bin/bash\n" + body, encoding="utf-8")
    p.chmod(0o755)
    assert os.access(p, os.X_OK)
    return folder


def _snapshot(dest: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(dest.rglob("*")) if p.is_file()}


def test_backup_first_then_an_atomic_replace(tmp_path: Path) -> None:
    """Each live file is backed up (byte-for-byte) under backups/, then replaced by a rename — a new inode, mode
    0755, no temp file left — after the harness ran on the copies being installed."""
    src, dest = _src(tmp_path), _dest(tmp_path)
    harness, log = _harness(tmp_path)
    old = {f: ((dest / f).read_bytes(), (dest / f).stat().st_ino) for f in FILES}
    out = _run(tmp_path, "--src", str(src), "--dest", str(dest), harness=harness)
    assert out.returncode == 0, out.stderr
    assert log.read_text(encoding="utf-8").split() == [f"src={src}"]
    for f in FILES:
        backups = sorted((dest / "backups").glob(f"{f}.backup.*"))
        assert len(backups) == 1, (f, backups)
        assert re.fullmatch(rf"{re.escape(f)}\.backup\.\d{{8}}-\d{{6}}", backups[0].name)
        assert backups[0].read_bytes() == old[f][0]
        assert (dest / f).read_bytes() == (src / f).read_bytes()
        assert (dest / f).stat().st_ino != old[f][1], f"{f} was rewritten in place, not renamed"
        assert (dest / f).stat().st_mode & 0o777 == 0o755
    assert sorted(p.name for p in dest.iterdir()) == sorted([*FILES, "backups"])
    # T04 F4: a harness other than the copies' own is said, every time
    assert f"install_mesh: HARNESS OVERRIDDEN by MESH_INSTALL_HARNESS={harness}" in out.stderr, (
        out.stderr
    )


def test_the_copies_own_harness_is_not_reported_as_an_override(tmp_path: Path) -> None:
    """T04 F4's mirror: with MESH_INSTALL_HARNESS unset (or naming the copies' own harness) no override is said."""
    src, dest = _src(tmp_path), _dest(tmp_path)
    for harness in (None, src / "claude-mesh-test.sh"):
        out = _run(tmp_path, "--src", str(src), "--dest", str(dest), harness=harness)
        assert out.returncode == 0, out.stderr
        assert "OVERRIDDEN" not in out.stderr, (harness, out.stderr)


def _two_installs_one_second(tmp_path: Path) -> tuple[Path, Path, subprocess.CompletedProcess[str]]:
    src, dest = _src(tmp_path), _dest(tmp_path)
    harness, _ = _harness(tmp_path)
    stubs = _stub(
        tmp_path / "stubs", "date", "echo 20261030-120000\n"
    )  # both runs in the same second
    first = _run(tmp_path, "--src", str(src), "--dest", str(dest), harness=harness, stubs=stubs)
    assert first.returncode == 0, first.stderr
    for f in FILES:
        (src / f).write_text(f"#!/usr/bin/env bash\necho newer {f}\n", encoding="utf-8")
    second = _run(tmp_path, "--src", str(src), "--dest", str(dest), harness=harness, stubs=stubs)
    return src, dest, second


def test_a_second_install_in_the_same_second_keeps_the_first_backup(tmp_path: Path) -> None:
    """T04 F16: backup names have one-second granularity; a second install in the same second must not overwrite the
    first run's backup of the ORIGINAL file."""
    src, dest, second = _two_installs_one_second(tmp_path)
    assert second.returncode == 0, second.stderr
    for f in FILES:
        backups = {p.read_text(encoding="utf-8") for p in (dest / "backups").glob(f"{f}.backup.*")}
        assert backups == {
            f"#!/usr/bin/env bash\necho old {f}\n",
            f"#!/usr/bin/env bash\necho new {f}\n",
        }, (
            f,
            backups,
        )
        assert (dest / f).read_bytes() == (src / f).read_bytes()


def test_a_failed_replace_restores_every_file_already_replaced(tmp_path: Path) -> None:
    """T04 F15: the install is all-or-nothing — the 2nd replace fails after the 1st landed, so the 1st is restored
    from its backup and the run exits 1 saying what it restored; no mixed, un-harnessed mesh stays live."""
    src, dest = _src(tmp_path), _dest(tmp_path)
    harness, _ = _harness(tmp_path)
    before = {f: (dest / f).read_bytes() for f in FILES}
    stubs = _stub(
        tmp_path / "stubs",
        "mv",
        'case "${@: -1}" in */claude-reboot-sweep.sh) exit 1 ;; esac\nexec /bin/mv "$@"\n',
    )
    out = _run(tmp_path, "--src", str(src), "--dest", str(dest), harness=harness, stubs=stubs)
    assert out.returncode == 1, out.stderr
    assert "restored" in out.stderr and str(dest / FILES[0]) in out.stderr, out.stderr
    assert {f: (dest / f).read_bytes() for f in FILES} == before
    assert sorted(p.name for p in dest.iterdir()) == sorted([*FILES, "backups"]), (
        "a temp file was left"
    )


def test_a_failed_replace_removes_a_file_that_was_new(tmp_path: Path) -> None:
    """T04 F15: a file this run installed where none was before is removed when a later replace fails."""
    src, dest = _src(tmp_path), _dest(tmp_path)
    harness, _ = _harness(tmp_path)
    (dest / FILES[0]).unlink()
    stubs = _stub(
        tmp_path / "stubs",
        "mv",
        'case "${@: -1}" in */claude-reboot-sweep.sh) exit 1 ;; esac\nexec /bin/mv "$@"\n',
    )
    out = _run(tmp_path, "--src", str(src), "--dest", str(dest), harness=harness, stubs=stubs)
    assert out.returncode == 1, out.stderr
    assert not (dest / FILES[0]).exists(), (
        "a file new to this run stayed live after the install failed"
    )
    assert (dest / FILES[1]).read_text(
        encoding="utf-8"
    ) == f"#!/usr/bin/env bash\necho old {FILES[1]}\n"


def test_a_backup_that_differs_refuses_with_nothing_replaced(tmp_path: Path) -> None:
    """T04 F18(b): the backup is compared byte for byte — a `cp` that writes a different backup refuses the install
    before any file is replaced."""
    src, dest = _src(tmp_path), _dest(tmp_path)
    harness, _ = _harness(tmp_path)
    before = {f: (dest / f).read_bytes() for f in FILES}
    stubs = _stub(
        tmp_path / "stubs",
        "cp",
        'case "${@: -1}" in */backups/*) /bin/cp "$@"; rc=$?; echo corrupt >> "${@: -1}"; exit $rc ;; esac\n'
        'exec /bin/cp "$@"\n',
    )
    out = _run(tmp_path, "--src", str(src), "--dest", str(dest), harness=harness, stubs=stubs)
    assert out.returncode == 1 and "backup" in out.stderr, out.stderr
    assert {f: (dest / f).read_bytes() for f in FILES} == before


def test_dest_given_needs_no_home(tmp_path: Path) -> None:
    """T04 F17: the default destination is resolved after the arguments, so `--dest X` with HOME unset installs."""
    src, dest = _src(tmp_path), _dest(tmp_path)
    harness, _ = _harness(tmp_path)
    out = _run(tmp_path, "--src", str(src), "--dest", str(dest), harness=harness, home=False)
    assert out.returncode == 0, out.stderr
    for f in FILES:
        assert (dest / f).read_bytes() == (src / f).read_bytes()


def test_no_home_and_no_dest_is_a_usage_error(tmp_path: Path) -> None:
    """T04 F17: HOME unset AND no --dest exits 2 with the usage line, before the harness runs."""
    src = _src(tmp_path)
    harness, log = _harness(tmp_path)
    out = _run(tmp_path, "--src", str(src), harness=harness, home=False)
    assert out.returncode == 2 and "usage" in out.stderr and not log.exists(), out.stderr


@pytest.mark.parametrize("flag", ["--dest", "--src"])
def test_an_empty_dest_or_src_is_a_usage_error(tmp_path: Path, flag: str) -> None:
    """T04 G3: the default applies only when the flag was NOT given — `--dest ""` must never fall back to the live
    $HOME/.claude/bin, and `--src ""` never to the tracked copies; both exit 2 with nothing installed."""
    src = _src(tmp_path)
    home_bin = _dest(
        tmp_path
    )  # $HOME/.claude/bin of the temp home: the fallback a bad parse would hit
    before = _snapshot(home_bin)
    harness, log = _harness(tmp_path)
    args = (
        ("--src", str(src), "--dest", "")
        if flag == "--dest"
        else ("--src", "", "--dest", str(home_bin))
    )
    out = _run(tmp_path, *args, harness=harness)
    assert out.returncode == 2 and "usage" in out.stderr and not log.exists(), (
        out.returncode,
        out.stderr,
    )
    assert _snapshot(home_bin) == before


def test_no_backup_means_no_replace(tmp_path: Path) -> None:
    """A backup that cannot be written refuses the install before ANY file is replaced."""
    src, dest = _src(tmp_path), _dest(tmp_path)
    harness, _ = _harness(tmp_path)
    (dest / "backups").mkdir()
    (dest / "backups").chmod(0o555)
    before = _snapshot(dest)
    try:
        out = _run(tmp_path, "--src", str(src), "--dest", str(dest), harness=harness)
    finally:
        (dest / "backups").chmod(0o755)
    assert out.returncode != 0 and "backup" in out.stderr, out.stderr
    assert _snapshot(dest) == before


def test_a_copy_failing_bash_n_installs_nothing(tmp_path: Path) -> None:
    src = _src(tmp_path, **{"claude-reboot-sweep.sh": "#!/usr/bin/env bash\nif then fi (\n"})
    dest = _dest(tmp_path)
    harness, log = _harness(tmp_path)
    before = _snapshot(dest)
    out = _run(tmp_path, "--src", str(src), "--dest", str(dest), harness=harness)
    assert (
        out.returncode != 0 and "bash -n" in out.stderr and "claude-reboot-sweep.sh" in out.stderr
    ), out.stderr
    assert _snapshot(dest) == before and not log.exists()


def test_a_red_harness_installs_nothing(tmp_path: Path) -> None:
    src, dest = _src(tmp_path), _dest(tmp_path)
    harness, _ = _harness(tmp_path, rc=1)
    before = _snapshot(dest)
    out = _run(tmp_path, "--src", str(src), "--dest", str(dest), harness=harness)
    assert out.returncode != 0 and "harness" in out.stderr, out.stderr
    assert _snapshot(dest) == before


def test_a_missing_source_installs_nothing(tmp_path: Path) -> None:
    src, dest = _src(tmp_path), _dest(tmp_path)
    (src / "claude-selfwatch.sh").unlink()
    harness, log = _harness(tmp_path)
    before = _snapshot(dest)
    out = _run(tmp_path, "--src", str(src), "--dest", str(dest), harness=harness)
    assert out.returncode != 0 and "claude-selfwatch.sh" in out.stderr, out.stderr
    assert _snapshot(dest) == before and not log.exists()


def test_an_identical_file_is_left_alone_and_a_new_one_needs_no_backup(tmp_path: Path) -> None:
    src, dest = _src(tmp_path), _dest(tmp_path)
    harness, _ = _harness(tmp_path)
    (dest / FILES[0]).write_bytes((src / FILES[0]).read_bytes())
    os.utime(dest / FILES[0], ns=(1_000_000_000, 1_000_000_000))  # an mtime no rewrite can keep
    same = (dest / FILES[0]).stat()
    (dest / FILES[1]).unlink()
    out = _run(tmp_path, "--src", str(src), "--dest", str(dest), harness=harness)
    assert out.returncode == 0, out.stderr
    # T04 F18(a): LEFT ALONE — the same inode and mtime, not a rename of an equal copy
    now = (dest / FILES[0]).stat()
    assert (now.st_ino, now.st_mtime_ns) == (same.st_ino, same.st_mtime_ns)
    backups = os.listdir(dest / "backups")
    assert len(backups) == 1 and backups[0].startswith(f"{FILES[2]}.backup."), backups
    for f in FILES:
        assert (dest / f).read_bytes() == (src / f).read_bytes()


def test_defaults_are_the_tracked_copies_and_home_bin(tmp_path: Path) -> None:
    """With no flags the source is the script's own mesh/ folder and the destination $HOME/.claude/bin (a temp
    home here)."""
    dest = _dest(tmp_path)
    harness, log = _harness(tmp_path)
    out = _run(tmp_path, harness=harness)
    assert out.returncode == 0, out.stderr
    assert log.read_text(encoding="utf-8").split() == [f"src={MESH}"]
    for f in FILES:
        assert (dest / f).read_bytes() == (MESH / f).read_bytes()


@pytest.mark.parametrize("bad", [("--src",), ("--bogus", "x")])
def test_bad_arguments_are_a_usage_error(tmp_path: Path, bad: tuple[str, ...]) -> None:
    harness, log = _harness(tmp_path)
    out = _run(tmp_path, *bad, harness=harness)
    assert out.returncode == 2 and "usage" in out.stderr and not log.exists(), out.stderr


# --- the tracked sweep (spec L4) ---------------------------------------------------------------------------------
SWEEP = MESH / "claude-reboot-sweep.sh"


def test_tracked_sweep_state_line_is_byte_identical() -> None:
    """The writer (session_orient.py) and the sweep derive the persistent marker dir independently;
    tests/test_session_orient_hook.py checks only the LIVE sweep, so the tracked copy is pinned here."""
    lines = SWEEP.read_text(encoding="utf-8").splitlines()
    assert [ln for ln in lines if ln.startswith("state=")] == [
        'state="${MESH_STATE_DIR:-$HOME/.claude/state/autonomous}"'
    ]


_ASSIGN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
_WRAPPERS = {"env", "timeout", "nohup", "setsid", "exec", "command", "nice", "stdbuf", "sudo"}
_SEPARATORS = {"|", "||", "&", "&&", ";", ";;", "(", ")", "$(", "`"}


def _logical(text: str) -> list[str]:
    """Shell LOGICAL lines: a line ending in an unescaped backslash continues on the next (T04 residue 4)."""
    return re.sub(r"(?<!\\)\\\n", " ", text).splitlines()


def _commands(line: str) -> list[list[str]]:
    """The simple commands of one logical line, each as its words with quotes removed: split at `|`, `;`, `&&`,
    `||`, `&` and parentheses, a `#` comment dropped. A line shlex cannot parse (an unbalanced quote that a heredoc
    or a multi-line awk program leaves) falls back to whitespace words, the conservative reading."""
    import shlex

    lex = shlex.shlex(line, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    try:
        words = list(lex)
    except ValueError:
        words = line.split()
    out: list[list[str]] = [[]]
    for w in words:
        if w in _SEPARATORS or set(w) <= set("|&;()"):
            out.append([])
        else:
            out[-1].append(w)
    return [c for c in out if c]


def _argv(cmd: list[str]) -> list[str]:
    """The command word and its arguments: leading `X=1` assignments and wrappers (`env`, `timeout 60`, `nohup` …,
    with their own options) skipped."""
    i = 0
    while i < len(cmd):
        w = cmd[i]
        if _ASSIGN.match(w):
            i += 1
        elif w in _WRAPPERS:
            i += 1
            while i < len(cmd) and (cmd[i].startswith("-") or _ASSIGN.match(cmd[i])):
                i += 1
            if w == "timeout" and i < len(cmd) and re.fullmatch(r"[0-9.]+[smhd]?", cmd[i]):
                i += 1
        else:
            break
    return cmd[i:]


def _flags(args: list[str]) -> tuple[bool, bool]:
    """(print, resume) for claude's arguments: `--print` and `--resume`/`--continue` in full or abbreviated to 3+
    letters (`--cont`, `--res=`), and short flags alone or clustered (`-p`, `-r`, `-c`, `-pr`, `-cp`)."""
    p = r = False
    for a in args:
        if a.startswith("--"):
            name = a[2:].split("=", 1)[0]
            if len(name) >= 3:
                p = p or "print".startswith(name)
                r = r or "resume".startswith(name) or "continue".startswith(name)
        elif re.fullmatch(r"-[A-Za-z]+", a):
            p = p or "p" in a
            r = r or "r" in a or "c" in a
    return p, r


def _headless_resume(line: str) -> bool:
    """A logical line that resumes or continues a session headless (T04 F5, G2, residue 4): a command whose word is
    `claude` (any path) given a print flag, or one whose word is a variable expansion (`"$CLAUDE_BIN"`, `${c}`)
    given a print flag AND a resume/continue flag. Another command's own `-p`/`-r` (`cp -p -r`, `mkdir -p`) is no
    claude flag, and a fresh headless run through a variable with no resume flag is not a resume."""
    for cmd in _commands(line):
        argv = _argv(cmd)
        if not argv:
            continue
        word, args = argv[0], argv[1:]
        p, r = _flags(args)
        if os.path.basename(word) == "claude" and p:
            return True
        if word.startswith("$") and p and r:
            return True
    return False


def test_the_headless_resume_matcher_catches_every_spelling() -> None:
    """The matcher below would pass a sweep that spelled the resume any other way than `claude -p` — so it is shown
    catching every spelling, and passing the sweep's own harmless `-p` uses and a fresh headless run."""
    caught = [
        '"$CLAUDE_BIN" -p --resume "$sid"',
        'claude --print --resume "$sid"',
        'env X=1 "$c" -p --resume "$sid"',
        'timeout 60 claude --resume "$sid" -p "go on"',
        'claude -p "resume your task"',
        '"$CLAUDE_BIN" -p -r "$sid"',
        'claude -c -p "go on"',
        '"$c" -p --continue',
        '"$c" --print --resume="$sid"',
        # T04 residue 4: an abbreviated long flag, a `\` continuation, a clustered short flag
        '"$c" -p --cont',
        '"$c" --pri --res "$sid"',
        '"$c" -p \\\n    --resume "$sid"',
        '"$c" -pr "$sid"',
        'x=1; timeout 60 "$c" -cp "go on"',
    ]
    assert [s for s in caught if not any(_headless_resume(ln) for ln in _logical(s))] == []
    harmless = [
        'mkdir -p -m 700 "$state"',
        'cp -p "$a" "$b"',
        'resume_hint="--resume $sid"',
        '"$c" -p "start a new task"',
        'tail -n 1 "$outf" | cut -c1-200',
        # T04 residue 4: another command's own -p/-r is no claude flag
        'cp -p -r "$a" "$b"',
        'cp -pr "$a" "$b" && "$c" -p "new task"',
        'printf "%s\\n" "-p --resume" | grep -c -- -p',
    ]
    assert [s for s in harmless if any(_headless_resume(ln) for ln in _logical(s))] == []


def test_tracked_sweep_never_resumes_with_claude_p() -> None:
    code = [
        ln
        for ln in _logical(SWEEP.read_text(encoding="utf-8"))
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    assert [ln for ln in code if _headless_resume(ln)] == []
    assert not [ln for ln in code if "CLAUDE_MESH_AUTONOMOUS=1" in ln]
