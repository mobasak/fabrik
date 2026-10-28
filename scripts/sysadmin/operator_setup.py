#!/usr/bin/env python3
# AFTER-EDIT: tests/test_operator_setup.py | docs/workstation/operator-setup.md | docs/workstation/claude-tab-router.md
"""The operator's ONE-TIME setup (W-d6726a65, docs/reference/operator-agent-requirements.md 1.1).

Claude Code's safety check refuses agents the settings-file and home-dir writes below, so the operator
runs this once; the coordinators do everything after it. Three steps:

  hooks   — the user-level hook entries in every account dir (`install_user_hooks.py`'s own output)
  wrapper — the stage-2 `claude-agent-wrapper.sh` copied to ~/.claude/bin (mode 0755)
  vscode  — `claudeCode.claudeProcessWrapper` in the code-server User and VS Code Machine settings

    python3 /opt/fabrik/scripts/sysadmin/operator_setup.py           # dry run: a diff of every change, writes nothing
    python3 /opt/fabrik/scripts/sysadmin/operator_setup.py --apply   # back up, write, verify, print the undo lines

The whole PLAN (every file's before and after bytes) is built and checked before anything is written; any
refusal writes nothing. The hooks step runs the installer's own `run([])` against a scratch mirror of HOME
and takes its bytes, so there is no second copy of the installer's repair logic and the dry-run diff IS
what `--apply` writes. `--apply` refuses (exit 2) unless this file sits in the hub MAIN checkout's
`scripts/sysadmin/` and that checkout is on master — the wrapper it installs runs in every chat tab. The
guard proves location and branch, not a clean tree. `OPERATOR_SETUP_HUB` overrides the hub path for
tests and says so loudly.

Exit: 0 done (or nothing to do) · 1 a refusal or a failed verification, nothing written when it is a
refusal · 2 `--apply` outside the hub main checkout on master.

COBRA (D-253): the cheapest way to make the run "succeed" is to plan nothing — a target the planner
silently skips reads as already done. Counter: every skipped VS Code target is a missing PARENT dir (the
editor is not installed there), every refused target fails the run, and `--apply` re-verifies each step
from the live files, the hooks through the installer's own `--check`.
"""

from __future__ import annotations

import argparse
import contextlib
import difflib
import importlib.util
import io
import json
import os
import shlex
import stat
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_HUB = "/opt/fabrik"
KEY = "claudeCode.claudeProcessWrapper"
MASTER_HEAD = "ref: refs/heads/master"


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


def _home() -> Path:
    return Path(os.environ.get("HOME") or Path.home())


def _rel(home: Path, path: Path) -> str:
    try:
        return str(path.relative_to(home))
    except ValueError:
        raise PlanError(f"{path} is outside HOME ({home}) — refused") from None


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
            try:  # the installer's own read (install_user_hooks.run): it skips a file it cannot parse
                json.loads(data.decode("utf-8") or "{}")
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


def _no_duplicates(pairs: list[tuple[str, object]]) -> dict:
    keys = [k for k, _ in pairs]
    dup = sorted({k for k in keys if keys.count(k) > 1})
    if dup:
        raise ValueError(f"duplicate key(s) {dup}")
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


def plan(home: Path) -> list[Change]:
    return plan_hooks(home) + plan_wrapper(home) + plan_vscode(home)


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
    c.path.parent.mkdir(parents=True, exist_ok=True)
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


def _restore_lines(backup: Path, done: list[Change]) -> list[str]:
    lines = []
    for c in done:
        target = '"$HOME"/' + shlex.quote(c.rel)
        if c.before is None:
            lines.append(f"rm -f {target}")
        else:
            lines.append(f"cp -p {shlex.quote(str(backup / c.rel))} {target}")
    return lines


def apply(home: Path, changes: list[Change]) -> int:
    for c in changes:  # a file edited since it was planned is never overwritten
        if _read(c.path)[0] != c.before:
            print(f"operator_setup: {c.path} changed since it was planned — nothing written; run again", file=sys.stderr)
            return 1
    root = home / ".local" / "state" / "fabrik"
    root.mkdir(parents=True, exist_ok=True)
    backup = root / f"operator-setup-{time.strftime('%Y%m%d-%H%M%S')}"
    try:
        backup.mkdir()
    except FileExistsError:
        print(f"operator_setup: {backup} already exists — nothing written; run again in a second", file=sys.stderr)
        return 1
    backup.chmod(0o700)
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
    done: list[Change] = []
    try:
        for c in changes:
            _write_atomic(c)
            done.append(c)
            print(f"wrote {c.rel} ({c.step})")
    finally:
        print(f"\nBackup: {backup}\nTo undo, run:")
        for line in _restore_lines(backup, done):
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
    data, mode = _read(wrapper)
    if data != (HERE / "claude-agent-wrapper.sh").read_bytes() or mode != 0o755:
        bad.append(f"wrapper: {wrapper} does not match {HERE / 'claude-agent-wrapper.sh'} at mode 0755")
    if plan_vscode(home):
        bad.append(f"vscode: {KEY} is still not set")
    return bad


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
        changes = plan(home)
    except PlanError as exc:
        print(f"operator_setup: {exc}\nNothing was written.", file=sys.stderr)
        return 1
    if not args.apply:
        _show(changes)
        if changes:
            print(f"{len(changes)} file(s) would change. Run again with --apply to back them up and write them.")
        else:
            print("Nothing to do: every step is already in place.")
        return 0
    if not changes:
        print("Nothing to do: every step is already in place.")
    else:
        _show(changes)
        rc = apply(home, changes)
        if rc:
            return rc
    bad = verify(home)
    for line in bad:
        print(f"VERIFY FAILED — {line}", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(run())
