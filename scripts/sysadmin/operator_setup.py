#!/usr/bin/env python3
# AFTER-EDIT: tests/test_operator_setup.py | docs/workstation/operator-setup.md | docs/workstation/claude-tab-router.md
"""The operator's ONE-TIME setup (W-d6726a65, docs/reference/operator-agent-requirements.md 1.1).

Claude Code's safety check refuses agents the settings-file and home-dir writes below, so the operator
runs this once; the coordinators do everything after it. Five steps:

  hooks   — the user-level hook entries in every account dir (`install_user_hooks.py`'s own output)
  wrapper — the stage-2 `claude-agent-wrapper.sh` copied to ~/.claude/bin (mode 0755)
  vscode  — `claudeCode.claudeProcessWrapper` in the code-server User and VS Code Machine settings
  archive — the nightly chat backup's systemd user units (W-36687f76): diffed and backed up here, then
            installed by `install_session_archive_timer.sh` itself, which runs FIRST so a systemd
            refusal leaves the other steps unwritten
  ssh     — a keepalive for git pushes (W-030ac2fe): a `Host github.com` block setting ServerAliveInterval 15
            and ServerAliveCountMax 4, put before the first section of ~/.ssh/config because ssh takes the
            first value it reads; planned and verified by what `ssh -G` itself resolves for git@github.com — a
            keepalive already as tight (interval <= 15 s, interval x count <= 60 s) is in place and kept.
            `OPERATOR_SETUP_SSH_HOME=1` (tests only) lets a scratch HOME stand in for the passwd home ssh reads

    python3 /opt/fabrik/scripts/sysadmin/operator_setup.py           # dry run: a diff of every change, writes nothing
    python3 /opt/fabrik/scripts/sysadmin/operator_setup.py --apply   # back up, write, verify, print the undo lines

The whole PLAN (every file's before and after bytes) is built and checked before anything is written; any
refusal writes nothing. A file edited after planning is re-read before the backups and again right before its
own replace, and the run stops there; a save landing in the instant between that re-read and `os.replace` is
the one accepted residue (W-88173de4) — no portable compare-and-swap on a path exists, and a RENAME_EXCHANGE
swap-and-compare still leaves a window. The hooks step runs the installer's own `run([])` against a scratch mirror of HOME
and takes its bytes, so there is no second copy of the installer's repair logic and the dry-run diff IS
what `--apply` writes. `--apply` refuses (exit 2) unless this file sits in the hub MAIN checkout's
`scripts/sysadmin/` and that checkout is on master — the wrapper it installs runs in every chat tab. The
guard proves location and branch, not a clean tree. `OPERATOR_SETUP_HUB` overrides the hub path for
tests and says so loudly.

Exit: 0 done (or nothing to do) · 1 a refusal (nothing written when planning refused), a failed archive installer or
a failed verification · 2 `--apply` outside the hub main checkout on master.

COBRA (D-253): the cheapest way to make the run "succeed" is to plan nothing — a target the planner
silently skips reads as already done. Counter: every skipped VS Code target is a missing PARENT dir (the
editor is not installed there), every refused target fails the run, and `--apply` re-verifies each step
from the live files, the hooks through the installer's own `--check` and the archive through the LOADED
unit (`systemctl --user show`), never the disk copy a hand install could leave unreloaded.
"""

from __future__ import annotations

import argparse
import contextlib
import difflib
import importlib.util
import io
import json
import os
import pwd
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_HUB = "/opt/fabrik"
KEY = "claudeCode.claudeProcessWrapper"
MASTER_HEAD = "ref: refs/heads/master"
ARCHIVE_INSTALLER = "install_session_archive_timer.sh"
ARCHIVE_UNITS = ("session-archive-alert.service", "session-archive.service", "session-archive.timer")
ARCHIVE_ALERT = "session-archive-alert.service"
ARCHIVE_TIMER = "session-archive.timer"
TIMER_WORDS = ("enabled", "enabled-runtime", "disabled", "not-found")  # is-enabled words, measured undo
NO_MANAGER = "cannot reach the user systemd manager"
SSH_TARGET = "git@github.com"  # git's own identity: a `Match user git` resolves differently for a bare host
SSH_WANT = ("15", "4")  # (ServerAliveInterval, ServerAliveCountMax) the block writes
SSH_BLOCK = (
    "# operator_setup (W-030ac2fe): git push keepalive — ssh takes the first value, keep this above other Host blocks",
    "Host github.com",
    "    ServerAliveInterval 15",
    "    ServerAliveCountMax 4",
    "",
)
SSH_SECTION = re.compile(rb"^[ \t]*(host|match)([ \t=]|$)", re.I | re.M)  # bytes: the file is never decoded


class PlanError(Exception):
    """A target the run must not touch; the whole run writes nothing."""


@dataclass
class Change:
    step: str
    path: Path
    rel: str
    before: bytes | None  # None: the file does not exist yet
    old_mode: int | None
    after: bytes
    mode: int


@dataclass
class Plan:
    changes: list[Change]
    archive_run: str | None = None  # why the archive installer must run; None when the archive is in place
    archive_sources: dict[str, bytes] | None = None
    timer_was: tuple[bool, bool] = (True, True)  # the timer (enabled, active) when planned


def _home() -> Path:
    return Path(os.environ.get("HOME") or Path.home())


def _rel(home: Path, path: Path) -> str:
    try:
        rel = path.relative_to(home)
    except ValueError:
        raise PlanError(f"{path} is outside HOME ({home}) — refused") from None
    if ".." in rel.parts:  # `relative_to` is lexical: `<home>/../x` passes it and escapes the backup dir
        raise PlanError(f"{path} climbs out of HOME through `..` — refused")
    return str(rel)


def _read(path: Path) -> tuple[bytes | None, int | None]:
    """The file's bytes and mode, or (None, None) when absent. A symlink or a non-regular file is
    refused: an atomic replace would turn a symlink into a regular file."""
    try:
        st = path.lstat()
    except FileNotFoundError:
        return None, None
    if stat.S_ISLNK(st.st_mode):
        raise PlanError(f"{path} is a symlink — refused; change it by hand")
    if not stat.S_ISREG(st.st_mode):
        raise PlanError(f"{path} is not a regular file — refused")
    return path.read_bytes(), stat.S_IMODE(st.st_mode)


def _installer():
    spec = importlib.util.spec_from_file_location("install_user_hooks", HERE / "install_user_hooks.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@contextlib.contextmanager
def _home_as(path: Path):
    old = os.environ.get("HOME")
    os.environ["HOME"] = str(path)
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old


def plan_hooks(home: Path) -> list[Change]:
    iuh = _installer()
    live: dict[str, tuple[bytes | None, int | None]] = {}
    for target in iuh._targets():
        rel = _rel(home, target)
        data, mode = _read(target)
        if data is not None:
            try:  # the installer's own read (install_user_hooks.run): it skips a file it cannot parse, and keeps
                # only the last of a duplicated key, so a duplicate is refused here as plan_vscode refuses it
                json.loads(data.decode("utf-8") or "{}", object_pairs_hook=_no_duplicates)
            except DuplicateKeyError as exc:
                raise PlanError(f"{target} has a {exc} — the installer would keep only the last; fix it by hand") from None
            except (UnicodeDecodeError, ValueError) as exc:
                raise PlanError(f"{target} does not parse as JSON ({exc}) — the installer would skip it; fix it by hand") from None
        live[rel] = (data, mode)
    with tempfile.TemporaryDirectory(prefix="operator-setup-mirror-") as tmp:
        mirror = Path(tmp)
        for rel, (data, _mode) in live.items():
            dst = mirror / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.parent.parent == mirror / ".claude-fleet":
                (dst.parent / ".claude.json").touch()  # the installer's account-dir marker
            if data is not None:
                dst.write_bytes(data)
        out = io.StringIO()
        with _home_as(mirror), contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = iuh.run([])
            mirrored = sorted(_rel(mirror, t) for t in iuh._targets())
        if mirrored != sorted(live):
            raise PlanError(f"the mirror HOME names other targets than HOME ({mirrored} vs {sorted(live)}) — refused")
        if rc != 0:
            raise PlanError("install_user_hooks.run failed on the mirror:\n" + out.getvalue())
        changes = []
        for rel, (data, mode) in sorted(live.items()):
            after = (mirror / rel).read_bytes()
            if after != data:
                changes.append(Change("hooks", home / rel, rel, data, mode, after, mode if mode is not None else 0o600))
    return changes


def plan_wrapper(home: Path) -> list[Change]:
    src = (HERE / "claude-agent-wrapper.sh").read_bytes()
    dst = home / ".claude" / "bin" / "claude-agent-wrapper.sh"
    data, mode = _read(dst)
    if data == src and mode == 0o755:
        return []
    return [Change("wrapper", dst, _rel(home, dst), data, mode, src, 0o755)]


class DuplicateKeyError(ValueError):
    """A JSON object naming one key twice; `json` would keep the last value silently."""


def _no_duplicates(pairs: list[tuple[str, object]]) -> dict:
    keys = [k for k, _ in pairs]
    dup = sorted({k for k in keys if keys.count(k) > 1})
    if dup:
        raise DuplicateKeyError(f"duplicate key(s) {dup}")
    return dict(pairs)


def _indent(text: str) -> str:
    for line in text.splitlines()[1:]:
        lead = line[: len(line) - len(line.lstrip(" \t"))]
        if lead:
            return lead
    return "    "


def plan_vscode(home: Path) -> list[Change]:
    value = os.path.normpath(str(home / ".claude" / "bin" / "claude-agent-wrapper.sh"))
    changes = []
    for path in (
        home / ".local" / "share" / "code-server" / "User" / "settings.json",
        home / ".vscode-server" / "data" / "Machine" / "settings.json",
    ):
        if not path.parent.is_dir():
            continue  # that editor is not installed here
        data, mode = _read(path)
        hand = f'add by hand: "{KEY}": "{value}"'
        if data is None:
            settings, indent, newline = {}, "    ", True
        else:
            try:
                text = data.decode("utf-8")
                settings = json.loads(text, object_pairs_hook=_no_duplicates) if text.strip() else {}
            except (UnicodeDecodeError, ValueError) as exc:
                raise PlanError(f"{path} is not plain JSON ({exc}) — not rewritten; {hand}") from None
            if not isinstance(settings, dict):
                raise PlanError(f"{path} is not a JSON object — not rewritten; {hand}")
            if isinstance(settings.get("claudeCode"), dict):
                raise PlanError(f"{path} holds a nested claudeCode object — not rewritten; {hand}")
            indent, newline = _indent(text), text.endswith("\n") or not text.strip()
        if settings.get(KEY) == value:
            continue
        settings[KEY] = value
        after = (json.dumps(settings, indent=indent, ensure_ascii=False) + ("\n" if newline else "")).encode("utf-8")
        changes.append(Change("vscode", path, _rel(home, path), data, mode, after, mode if mode is not None else 0o600))
    return changes


def _systemctl(*args: str, word: bool) -> str:
    """One `systemctl --user` read. A valid answer has an empty stderr (`is-enabled`/`is-active` exit non-zero
    on a valid `disabled`/`inactive`); any stderr, a missing binary or — for `word` — anything but one word on
    stdout is a refusal: an unreachable manager must never read as "not enabled" and plan a write."""
    try:
        r = subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PlanError(f"{NO_MANAGER} (systemctl: {exc}) — nothing written") from None
    out = r.stdout.strip()
    if r.stderr.strip() or "\n" in out or (word and not re.fullmatch(r"[a-z-]+", out)):
        said = (r.stderr.strip() or out or "no answer").splitlines()[0]
        raise PlanError(f"{NO_MANAGER} (systemctl --user {' '.join(args)}: {said}) — nothing written")
    return out


def _unit_dir(home: Path) -> Path:
    cfg = os.environ.get("XDG_CONFIG_HOME") or ""  # empty counts as unset, as in the installer's ${…:-…}
    base = Path(cfg) if cfg else home / ".config"
    if not base.is_absolute():
        raise PlanError(f"XDG_CONFIG_HOME={cfg!r} is relative — refused")
    return base / "systemd" / "user"


def plan_archive(home: Path) -> tuple[list[Change], str | None, dict[str, bytes], tuple[bool, bool]]:
    """(unit Changes, why the installer must run or None, the source bytes planned, the timer (enabled, active))."""
    dest = _unit_dir(home)
    sources = {name: (HERE / "systemd" / name).read_bytes() for name in ARCHIVE_UNITS}
    changes = []
    for name, src in sources.items():
        path = dest / name
        data, mode = _read(path)
        if data != src or mode != 0o644:
            changes.append(Change("archive", path, _rel(home, path), data, mode, src, 0o644))
    loaded = _systemctl("show", "-p", "OnFailure", "--value", "session-archive.service", word=False)
    enabled = _systemctl("is-enabled", ARCHIVE_TIMER, word=True)
    active = _systemctl("is-active", ARCHIVE_TIMER, word=True)
    # `enabled` is the ONLY in-place word. Measured on systemd 255 (W-88173de4): enabled-runtime is a /run link that
    # dies at reboot, so the installer's persistent enable is wanted, and the undo's plain `disable` removes only that
    # persistent link — within the same boot the timer reads enabled-runtime again; disabled and not-found are
    # restored the same way. Any other word is refused: an operator alias to this unit reads `indirect` and that
    # `disable` deletes the alias, and the rest (masked, linked, a lower search dir's link) have no measured undo.
    # A symlink AT this unit path was already refused by `_read` above.
    if enabled not in TIMER_WORDS:
        raise PlanError(f"{ARCHIVE_TIMER} reads `{enabled}` — refused: the undo's `disable` could not restore it; "
                        "change it by hand")
    why = [f"{len(changes)} unit(s) differ"] if changes else []
    if ARCHIVE_ALERT not in loaded.split():  # `--value` lists every OnFailure= unit, a drop-in's included
        why.append(f"loaded OnFailure={loaded or '(empty)'}")
    if enabled != "enabled":
        why.append(f"timer {enabled}")
    if active != "active":
        why.append(f"timer {active}")
    if not why:
        return [], None, sources, (True, True)
    user = pwd.getpwuid(os.getuid()).pw_name  # the installer's `id -un`
    try:
        r = subprocess.run(["loginctl", "show-user", user, "-p", "Linger"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PlanError(f"{NO_MANAGER} (loginctl: {exc}) — nothing written") from None
    if r.stdout.strip() != "Linger=yes":
        said = r.stdout.strip() or r.stderr.strip() or "no answer"
        raise PlanError(f"linger is off for {user} ({said}); the archive timer needs it — run once: "
                        f"loginctl enable-linger {user}")
    return changes, ", ".join(why), sources, (enabled == "enabled", active == "active")


def _ssh_resolves(data: bytes) -> tuple[str | None, str | None]:
    """(ServerAliveInterval, ServerAliveCountMax) ssh itself resolves for git@github.com from `data`, graded on a
    0600 copy in a private temp dir: `-F` on the live path exits 255 when the file is absent. `-G` never connects,
    but it runs the config's `Match exec` commands and may do DNS, as every push does; 30 s bounds a hang. Its
    stderr is no error signal (it says "Pseudo-terminal will not be allocated" whenever stdin is not a tty)."""
    with tempfile.TemporaryDirectory(prefix="operator-setup-ssh-") as tmp:
        cfg = Path(tmp) / "config"
        cfg.write_bytes(data)
        cfg.chmod(0o600)
        try:
            r = subprocess.run(["ssh", "-G", "-F", str(cfg), SSH_TARGET], capture_output=True, text=True,
                               errors="replace", stdin=subprocess.DEVNULL, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PlanError(f"cannot grade ~/.ssh/config with `ssh -G` ({exc})") from None
    if r.returncode:
        said = (r.stderr.strip() or "no answer").splitlines()[-1]
        raise PlanError(f"`ssh -G` refuses ~/.ssh/config ({said}) — fix it by hand")
    vals = dict(line.split(" ", 1) for line in r.stdout.splitlines() if " " in line)
    return vals.get("serveraliveinterval"), vals.get("serveralivecountmax")


def _keepalive_ok(got: tuple[str | None, str | None]) -> bool:
    """A keepalive at least as tight as the block's: a dead connection is dropped within 60 s. An operator's own
    tighter value (10/3) is in place and is never overridden; ServerAliveInterval 0 is no keepalive at all."""
    try:
        interval, count = int(got[0] or ""), int(got[1] or "")
    except ValueError:
        return False
    return 1 <= interval <= 15 and count >= 1 and interval * count <= 60


def plan_ssh(home: Path) -> list[Change]:
    if os.environ.get("OPERATOR_SETUP_SSH_HOME") == "1":  # the tests' scratch HOME; any other value is ignored
        print("SSH HOME OVERRIDE in effect: ~/.ssh/config is planned under $HOME", file=sys.stderr)
    else:  # ssh reads ~ from passwd, never $HOME: a config written elsewhere is never read
        pw = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()
        if home.resolve() != pw:
            raise PlanError(f"HOME ({home}) is not the passwd home ssh reads ({pw}) — run it with your own HOME")
    path = home / ".ssh" / "config"
    rel = _rel(home, path)
    sshdir = path.parent
    try:
        data, mode = _read(path)
    except OSError as exc:  # unreadable, or a component that is not a directory
        raise PlanError(f"cannot read {path} ({exc})") from None
    if data is not None:  # ssh's own owner/permission check, which `-F` skips: a config ssh refuses is never "in place"
        if path.lstat().st_uid not in (0, os.getuid()) or mode & 0o022:
            raise PlanError(f"{path} is writable by others or owned by another user (mode {mode:o}) — ssh refuses "
                            "such a config; chmod 600 it and run again")
    current = data or b""
    if _keepalive_ok(_ssh_resolves(current)):
        return []  # nothing to write, so the directory needs nothing either
    # a write is planned: where it lands must take it, or the run stops after the other steps are written
    if sshdir.is_symlink() and not sshdir.exists():
        raise PlanError(f"{sshdir} is a dangling symlink — refused; fix it by hand")
    nearest = sshdir
    while not nearest.exists():  # ~/.ssh absent: the directory it would be created in
        nearest = nearest.parent
    if not nearest.is_dir() or not os.access(nearest, os.W_OK | os.X_OK):
        raise PlanError(f"{nearest} is not a directory this user can write, so {path} cannot be written — "
                        "fix its mode (chmod 700) and run again")
    nl = b"\r\n" if b"\r\n" in current else b"\n"
    block = nl.join(line.encode("utf-8") for line in SSH_BLOCK) + nl
    section = SSH_SECTION.search(current)
    if section:  # before the first section, so its values are the first ssh reads for github.com
        after = current[: section.start()] + block + current[section.start():]
    elif current.strip():
        after = current.rstrip(b"\r\n") + nl + nl + block
    else:
        after = current + block
    got = _ssh_resolves(after)
    if not _keepalive_ok(got):
        raise PlanError(
            f"ssh resolves ServerAliveInterval {got[0]}/ServerAliveCountMax {got[1]} for {SSH_TARGET} from a line read "
            "before the inserted block — a global setting or an Include above the first Host/Match line; move it below, "
            "or set it there to an interval of 15 s or less with interval x count at most 60 s"
        )
    return [Change("ssh", path, rel, data, mode, after, mode if mode is not None else 0o600)]


def plan(home: Path) -> Plan:
    archive, why, sources, was = plan_archive(home)
    return Plan(plan_hooks(home) + plan_wrapper(home) + plan_vscode(home) + archive + plan_ssh(home), why, sources, was)


def _show(changes: list[Change]) -> None:
    for c in changes:
        old = (c.before or b"").decode("utf-8", "replace").splitlines(keepends=True)
        new = c.after.decode("utf-8", "replace").splitlines(keepends=True)
        print(f"== {c.step}: {c.rel}" + (" (new file)" if c.before is None else ""))
        sys.stdout.writelines(difflib.unified_diff(old, new, fromfile=c.rel, tofile=c.rel))
        if c.before == c.after and c.old_mode != c.mode:
            print(f"   mode {c.old_mode:o} -> {c.mode:o}")
        print()


def _guard() -> str | None:
    """None when --apply may run, else the refusal."""
    override = os.environ.get("OPERATOR_SETUP_HUB")
    if override:
        print(f"HUB OVERRIDE {override} in effect", file=sys.stderr)
    hub = Path(override or DEFAULT_HUB).resolve()
    want = hub / "scripts" / "sysadmin"
    if want != HERE:
        return f"this copy is in {HERE}; run it from the hub main checkout: {want / 'operator_setup.py'}"
    try:
        head = (hub / ".git" / "HEAD").read_text(encoding="utf-8").strip()
    except OSError as exc:
        return f"cannot read {hub / '.git' / 'HEAD'} ({exc}) — the hub main checkout is required"
    if head != MASTER_HEAD:
        return f"the hub main checkout is on `{head}`, not master"
    return None


def _mkdir_private(path: Path, root: Path) -> None:
    """Create `path` and any missing parents up to `root`, each 0700."""
    missing = []
    p = path
    while p != root and not p.exists():
        missing.append(p)
        p = p.parent
    for d in reversed(missing):
        d.mkdir()
        d.chmod(0o700)


def _write_atomic(c: Change) -> None:
    _mkdir_private(c.path.parent, Path(c.path.anchor))  # a missing ~/.ssh (or any parent) is made 0700, never at the umask
    fd, tmp = tempfile.mkstemp(dir=c.path.parent, prefix=f".{c.path.name}.operator-setup-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(c.after)
            fh.flush()
            os.fsync(fh.fileno())
            os.fchmod(fh.fileno(), c.mode)
        os.replace(tmp, c.path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _restore_lines(backup: Path | None, done: list[Change], ran: bool, timer_was: tuple[bool, bool]) -> list[str]:
    lines = []
    if ran:  # FIRST: a timer cannot be disabled once its unit file is gone; each half undoes only what it changed
        if not timer_was[0]:
            lines.append(f"systemctl --user disable {ARCHIVE_TIMER}")
        if not timer_was[1]:
            lines.append(f"systemctl --user stop {ARCHIVE_TIMER}")
    for c in done:
        target = '"$HOME"/' + shlex.quote(c.rel)
        if c.before is None:
            lines.append(f"rm -f {target}")
        else:
            lines.append(f"cp -p {shlex.quote(str(backup / c.rel))} {target}")
    if ran:  # LAST: the manager re-reads the restored unit files
        lines.append("systemctl --user daemon-reload")
    return lines


def _changed(c: Change) -> bool:
    """True when the target no longer holds the bytes AND mode planned for it — a mode-only change (the installer's
    0644 over a 0600 unit) counts. Never raises: a target that became a symlink, a non-file or unreadable counts as
    changed, so its undo line is printed and an exception already in flight (an interrupt) is never replaced."""
    try:
        data, mode = _read(c.path)
    except (PlanError, OSError):
        return True
    return data != c.before or mode != c.old_mode


def _run_archive_installer(p: Plan, done: list[Change]) -> int:
    """Run the installer once; every unit it changed joins `done`, whatever happens — it can die after
    writing all three without a word (daemon-reload failing under `set -e`, measured), or be interrupted."""
    print(f"running {HERE / ARCHIVE_INSTALLER} ({p.archive_run})", flush=True)
    try:
        rc = subprocess.run(["bash", str(HERE / ARCHIVE_INSTALLER)]).returncode
    finally:
        done.extend(c for c in p.changes if c.step == "archive" and _changed(c))
    print(f"installer exit {rc}", flush=True)
    return rc


def apply(home: Path, p: Plan) -> int:
    changes = p.changes
    # a file edited since it was planned is not overwritten (bar the re-check→replace instant, see the docstring)
    for c in changes:
        if _changed(c):
            print(f"operator_setup: {c.path} changed since it was planned — nothing written; run again", file=sys.stderr)
            return 1
    for name, planned in (p.archive_sources or {}).items() if p.archive_run else ():  # a hub pull since planning
        try:
            now = (HERE / "systemd" / name).read_bytes()
        except OSError:  # deleted or unreadable since planning
            now = None
        if now != planned:
            print(f"operator_setup: {HERE / 'systemd' / name} changed since it was planned — nothing written; run again",
                  file=sys.stderr)
            return 1
    backup = None
    if changes:
        root = home / ".local" / "state" / "fabrik"
        root.mkdir(parents=True, exist_ok=True)
        backup = root / f"operator-setup-{time.strftime('%Y%m%d-%H%M%S')}"
        try:
            backup.mkdir(mode=0o700)
        except FileExistsError:
            print(f"operator_setup: {backup} already exists — nothing written; run again in a second", file=sys.stderr)
            return 1
        backup.chmod(0o700)
    done: list[Change] = []
    ran = False
    try:  # from here on every exit prints where the backup is, and the undo lines for what was written
        for c in changes:
            if c.before is None:
                continue
            dst = backup / c.rel
            _mkdir_private(dst.parent, backup)
            dst.write_bytes(c.before)
            dst.chmod(c.old_mode if c.old_mode is not None else 0o600)
            if dst.read_bytes() != c.before:
                print(f"operator_setup: the backup of {c.path} does not match — nothing written", file=sys.stderr)
                return 1
        if p.archive_run:  # FIRST: a systemd refusal then leaves the other steps unwritten
            ran = True
            rc = _run_archive_installer(p, done)
            if rc:
                print("operator_setup: the archive installer failed — the other steps were not written", file=sys.stderr)
                return 1
        for c in changes:
            if c.step == "archive":
                continue  # the installer wrote these
            if _changed(c):  # an editor that saved while the installer ran: its save stands, the run stops
                print(f"operator_setup: {c.path} changed since it was planned — not overwritten; the run stopped here",
                      file=sys.stderr)
                return 1
            _write_atomic(c)
            done.append(c)
            print(f"wrote {c.rel} ({c.step})")
    finally:
        print(f"\nBackup: {backup or 'none (no file to change)'}")
        lines = _restore_lines(backup, done, ran, p.timer_was)
        if lines:
            print("To undo, run:")
            for line in lines:
                print(line)
    return 0


def verify(home: Path) -> list[str]:
    bad = []
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        rc = _installer().run(["--check"])
    if rc != 0:
        bad.append("hooks: install_user_hooks.py --check failed:\n" + out.getvalue())
    wrapper = home / ".claude" / "bin" / "claude-agent-wrapper.sh"
    for step, check in (("wrapper", lambda: _verify_wrapper(wrapper)), ("vscode", lambda: _verify_vscode(home)),
                        ("archive", lambda: _verify_archive(home)), ("ssh", lambda: _verify_ssh(home))):
        try:
            why = check()
        except PlanError as exc:
            why = str(exc)
        if why:
            bad.append(f"{step}: {why}")
    return bad


def _verify_wrapper(wrapper: Path) -> str | None:
    data, mode = _read(wrapper)
    if data != (HERE / "claude-agent-wrapper.sh").read_bytes() or mode != 0o755:
        return f"{wrapper} does not match {HERE / 'claude-agent-wrapper.sh'} at mode 0755"
    return None


def _verify_vscode(home: Path) -> str | None:
    return f"{KEY} is still not set" if plan_vscode(home) else None


def _verify_archive(home: Path) -> str | None:
    _changes, why, _sources, _was = plan_archive(home)
    return f"not in place ({why})" if why else None


def _verify_ssh(home: Path) -> str | None:
    return "ssh does not resolve a keepalive of 15 s or tighter for git@github.com" if plan_ssh(home) else None


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="back up, write and verify (default: dry run)")
    args = ap.parse_args(argv)
    if args.apply:
        why = _guard()
        if why:
            print(f"operator_setup: --apply refused — {why}", file=sys.stderr)
            return 2
    home = _home()
    try:
        p = plan(home)
    except PlanError as exc:
        print(f"operator_setup: {exc}\nNothing was written.", file=sys.stderr)
        return 1
    _show(p.changes)
    if p.archive_run:
        print(f"== archive: installer run ({p.archive_run}): bash {HERE / ARCHIVE_INSTALLER}\n")
    if not args.apply:
        if p.changes or p.archive_run:
            todo = f"{len(p.changes)} file(s) would change" + (" and the archive installer would run" if p.archive_run else "")
            print(f"{todo}. Run again with --apply to back them up and write them.")
        else:
            print("Nothing to do: every step is already in place.")
        return 0
    if not p.changes and not p.archive_run:
        print("Nothing to do: every step is already in place.")
    else:
        rc = apply(home, p)
        if rc:
            return rc
    bad = verify(home)
    for line in bad:
        print(f"VERIFY FAILED — {line}", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(run())
