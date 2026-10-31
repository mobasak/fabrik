#!/usr/bin/env python3
# AFTER-EDIT: docs/reference/tmux-agents.md | tests/test_watch_builders.py | scripts/sysadmin/selfwatch_check.py
"""watch_builders.py <session_id> <repo> — the coordinator's ONE-WAKE builder watch (W-c814836f, D-1396 duty 3).

Arm (the per-prompt check `selfwatch_check.py` prints this for a coordinator window whose watch is not held):
  Bash(run_in_background: true, command: "python3 /opt/fabrik/scripts/sysadmin/watch_builders.py <sid> <repo>")

It holds `<lockdir>/<safe-sid>.builderwatch.lock` for its life (a duplicate arm exits at once), and every
BUILDER_WATCH_POLL seconds (30) reads every builder pane of the repo's agents_up grid (`rotate_session.builder_panes`,
the PANE WAITING scan's filter) and the repo's mailbox. It WAKES — prints one line naming every hit and the re-arm
order, then exits 0, which re-invokes the session — when a builder pane that was busy is not busy any more, a pane
shows a turn end it did not show at the last look (a finished turn, however short), or mail for the coordinator
landed or was re-routed to it (`agent:` the repo's distributor, `coordinator`, or none; never its own). What it last
saw persists in `<lockdir>/<safe-sid>.builderwatch.state.json`, so a finish while the coordinator handles a wake is
named by the next arm; with no state the first look is a baseline that wakes nobody.

It exits with a line when its lock file vanished (a /tmp wipe) or the pane scan failed three looks running, and
without one when its parent died (PR_SET_PDEATHSIG, then a getppid check). A background Bash task has no deadline
(D-356), so there is no timeout. Busy is `rotate_session.pane_state`: a spinner, not a truncated `…`, and leftover
background shells are idle.

COBRA (D-253): the cheapest way to make this watch "quiet" is to read more screens as busy — every `…`, every
`shells still running` — which is exactly how the hand-made loop it replaces hid idle builders for hours; the busy
rules live in one function with a test over live captures, and a rule that reads idle wrongly costs a false wake, never
a hidden builder.
"""

from __future__ import annotations

import contextlib
import ctypes
import fcntl
import importlib.util
import json
import os
import shlex
import signal
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BLIND_LOOKS = 3  # failed pane scans in a row before the watch says it is blind
LOCK_TRIES = (
    5  # 5 × 50 ms: a shared-lock probe lasts microseconds, a standing watch holds the lock for good
)
LOOK_BUDGET_S = (
    20.0  # one look's tmux calls share it: a listing plus ~20 captures at ~5 ms each, far inside
)


def _safe(sid: str) -> str:
    """The self-watch's own lock-name transform (`selfwatch_check._safe`): every byte outside [A-Za-z0-9_-] → `_`,
    cut at 64 bytes, so the per-prompt check probes the same file."""
    out = bytearray()
    for b in sid.encode("utf-8", "surrogateescape"):
        out.append(b if (chr(b).isalnum() and b < 128) or b in b"_-" else ord("_"))
    return out[:64].decode("ascii")


def _rotate_session():
    spec = importlib.util.spec_from_file_location("_wb_rotate_session", HERE / "rotate_session.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {HERE / 'rotate_session.py'}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pdeathsig() -> None:
    """Die with the parent (selfwatch_arm.sh's `setpriv --pdeathsig`): an orphan would hold the lock — the check reads
    "armed" — and print its wake into a dead pipe. Best effort; the getppid check per look is the fallback."""
    with contextlib.suppress(Exception):
        ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGTERM, 0, 0, 0)  # PR_SET_PDEATHSIG = 1


def _role(main: Path) -> str:
    try:
        return (
            str(
                json.loads((main / ".fabrik" / "work" / "config.json").read_text()).get(
                    "distributor"
                )
                or ""
            ).strip()
            or "coordinator"
        )
    except (OSError, ValueError, AttributeError):
        return "coordinator"


def _frontmatter(path: Path) -> dict[str, str]:
    """The mail's `key: value` head between its two `---` rows; {} when it has none."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {}
    if not lines or lines[0].strip() != "---":
        return {}
    head: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return head
        key, sep, value = line.partition(":")
        if sep and key.strip() not in head:  # the first of a repeated key, as mail.py reads it
            head[key.strip()] = value.strip()
    return {}  # no closing rule: not a complete head


def _for_coordinator(head: dict[str, str], role: str, mailbox: str) -> bool:
    if not head:
        return False
    if head.get("from") == mailbox and head.get("from-agent") == role:
        return False  # this coordinator's own mail
    return head.get("agent", "") in (role, "coordinator", "")


def _inbox(inbox: Path) -> dict[str, int]:
    """{file name: mtime_ns} of the inbox's mails; mail.py publishes a dotfile then links it, so a `*.md` is whole."""
    out: dict[str, int] = {}
    with contextlib.suppress(OSError):
        for p in inbox.iterdir():
            if p.name.endswith(".md") and not p.name.startswith("."):
                with contextlib.suppress(OSError):
                    out[p.name] = p.stat().st_mtime_ns
    return out


def _load(path: Path) -> dict | None:
    try:
        st = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (
        not isinstance(st, dict)
        or not isinstance(st.get("panes"), dict)
        or not isinstance(st.get("mail"), dict)
    ):
        return None
    return st


def _save(path: Path, st: dict) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(st, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not argv[0] or not argv[1]:
        print("usage: watch_builders.py <session_id> <repo>")
        return 2
    sid, main_dir = argv[0], Path(argv[1]).resolve()
    parent = (
        os.getppid()
    )  # read BEFORE prctl: a parent that died first is caught by the check below
    _pdeathsig()
    if os.getppid() != parent:
        return 0  # orphaned before the death signal was armed: nobody reads a wake
    safe = _safe(sid)
    locks = Path(os.environ.get("CLAUDE_SOUND_LOCKDIR") or f"/tmp/claude-sound-locks-{os.getuid()}")
    lock_path = locks / f"{safe}.builderwatch.lock"
    rearm = (
        f'Bash(run_in_background: true, command: "python3 {Path(__file__).resolve()} {safe} '
        f'{shlex.quote(str(main_dir))}")'
    )
    try:
        locks.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(lock_path), os.O_WRONLY | os.O_CREAT, 0o644)
    except OSError as exc:
        print(f"builder-watch NOT armed: cannot open {lock_path}: {exc}")
        return 1
    # a few short retries: the per-prompt check probes this lock with a transient SHARED lock, and a first take that
    # lands inside that probe must not read as "already armed" (review Bh-4); a real standing watch holds it throughout
    for attempt in range(LOCK_TRIES):
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if attempt < LOCK_TRIES - 1:
                time.sleep(0.05)
    else:
        print(
            f"builder-watch already armed for {safe} — this duplicate exits; the standing watch stays"
        )
        return 0
    try:
        return _watch(
            fd, lock_path, locks / f"{safe}.builderwatch.state.json", main_dir, parent, safe, rearm
        )
    except Exception as exc:  # noqa: BLE001 — every exit prints its line: a traceback alone tells the coordinator nothing
        print(
            f"BUILDER WATCH FAILED: {type(exc).__name__}: {exc} — this watch EXITS; re-arm it: {rearm}"
        )
        return 1


def _watch(
    fd: int, lock_path: Path, state_path: Path, main_dir: Path, parent: int, safe: str, rearm: str
) -> int:
    rs = _rotate_session()
    role = _role(main_dir)
    mailbox = main_dir.name
    inbox = Path(os.environ.get("FABRIK_MAIL_ROOT") or "/opt/fabrik-mail") / mailbox / "inbox"
    poll = float(os.environ.get("BUILDER_WATCH_POLL") or 30)
    prev = _load(state_path)
    blind = 0
    first = True
    while True:
        if not first:
            time.sleep(poll)
        first = False
        if os.getppid() != parent:
            return 0  # orphaned: nobody reads a wake
        try:
            if not os.path.samestat(os.fstat(fd), os.stat(lock_path)):
                raise FileNotFoundError
        except FileNotFoundError:
            print(
                f"builder-watch for {safe}: its lock file vanished — this watch EXITS; re-arm it: {rearm}"
            )
            return 0
        old_panes = prev["panes"] if prev is not None else {}
        try:
            deadline = time.monotonic() + LOOK_BUDGET_S
            panes = rs._builder_panes(deadline, str(main_dir), "")
            now: dict[str, dict] = {}
            for pane, agent in panes.items():
                # no -e: a dim cell is still text here; bytes decoded with replacement
                screen = rs._grid_tmux(deadline, "capture-pane", "-p", "-t", pane)
                if screen is None:
                    # closed between the listing and the capture: keep what was last seen, so the next look —
                    # which no longer lists it — names it GONE
                    if isinstance(old_panes.get(pane), dict):
                        now[pane] = old_panes[pane]
                    continue
                busy, turn = rs.pane_state(screen)
                now[pane] = {"agent": agent, "busy": busy, "turn_id": turn}
            blind = 0
        except Exception as exc:  # noqa: BLE001 — a failed look is counted, never read as "nobody changed"
            blind += 1
            if blind >= BLIND_LOOKS:
                print(
                    f"BUILDER WATCH BLIND: {type(exc).__name__}: {exc} — this watch EXITS; re-arm it: {rearm}"
                )
                return 0
            continue
        mail = _inbox(inbox)
        state = {"panes": now, "mail": mail}
        if prev is None:  # no saved look: this one is the baseline
            _save(state_path, state)
            prev = state
            continue
        hits: list[str] = []
        for pane, cur in now.items():
            old = old_panes.get(pane)
            if not isinstance(old, dict) or cur["busy"]:
                continue  # a pane first seen is recorded; a busy pane has nothing to report
            if old.get("busy") or (cur["turn_id"] and cur["turn_id"] != old.get("turn_id")):
                hits.append(f"IDLE: {cur['agent']} ({pane})")
        # a pane the last look saw and this listing lacks: a crash, a dead tmux server, or a removal — said, never
        # silent (a removal the coordinator made itself costs one wake)
        for pane, old in sorted(old_panes.items()):
            if pane not in now and isinstance(old, dict):
                hits.append(f"GONE: {old.get('agent', '?')} ({pane})")
        for name, mtime in sorted(mail.items()):
            if prev["mail"].get(name) == mtime:
                continue
            head = _frontmatter(inbox / name)
            if _for_coordinator(head, role, mailbox):
                hits.append(
                    f"MAIL: {name[:-3]} from {head.get('from', '?')}/{head.get('from-agent') or '?'} · {head.get('kind', '?')}"
                )
        if hits:
            print("BUILDER WAKE: " + " · ".join(hits))
            print(
                f"This wake ENDED the watch (one wake per arm) — read those panes or that mail, then re-arm it: {rearm}"
            )
            # printed BEFORE the state is saved: a kill between the two repeats this wake on the next arm, never
            # loses it (review D-5)
            _save(state_path, state)
            return 0
        _save(state_path, state)
        prev = state


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
