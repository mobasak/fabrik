#!/usr/bin/env python3
# AFTER-EDIT: tests/test_box_budget_check.py | docs/workstation/vscode-configuration.md | docs/workstation/hooks-index.md | docs/workstation/claude-account-rotation.md
"""The box's shared per-user budgets, watched from the 5-minute rotation tick (W-09957e81, D-xxxx).

On 2026-10-27 at 11:12 `fabrik-rotate.path` failed with result `resources` ("Failed to enter waiting
state: No space left on device"): code-server's three file watchers held 523,576 of this user's
524,288 inotify watches. A failed path unit stays failed — systemd never restarts it — so for most of
an hour no builder in any repo could be rotated, and nothing said so.

Two legs, each alerting ONCE per episode by fabrik-mail to the hub coordinator:

- **unit** — when `fabrik-rotate.path` is ENABLED and reads `failed` or `inactive`, run `reset-failed`
  on it and its service, `start` it, and re-read it. A unit that is not enabled is the operator's
  choice and is left alone (disable it to keep it down: an enabled unit stopped by hand is restarted
  within five minutes). Any other state, or any systemctl error, acts on nothing — the leg fails OPEN,
  so a fault here is one more tick of an outage, never a fight with the operator.
- **inotify** — the watches in use (the `inotify wd:` lines of every /proc/<pid>/fdinfo file of this
  uid's processes) and the inotify instances (fds linking to `anon_inode:inotify`) against
  /proc/sys/fs/inotify/max_user_{watches,instances}. AMBER at 85% of either; the episode clears only
  below 80%, so a reading hovering at the line mails once, not every tick. A process this user cannot
  read is skipped, so the count is a lower bound. The scan costs ~0.9 s at 114,598 watches (measured),
  ~4 s at the full budget: fine for a detached tick child, too slow for a per-prompt hook.

An episode is recorded open only when its mail was sent (rc 0), so a failed send retries next run; a
state file that is missing, unreadable or corrupt reads as "no open episode" — the worst case is one
duplicate mail, never a lost alert. Cobra (D-253): healing a unit that keeps dying could hide the
cause, so a SUCCESSFUL heal mails too (once per episode, `--ack no`), with the readings.

Modes: no argument = the tick run (heal, probe, alert; always exits 0); `--report` = print the
readings and the top holders, change nothing, mail nothing (exit 0).

Seams (tests): BOX_BUDGET_STATE (state file), FABRIK_OPT_DIR (mail.py under <opt>/fabrik/scripts),
BOX_BUDGET_PROC (the /proc root), BOX_BUDGET_SYSTEMCTL (the systemctl command).
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

UNIT = "fabrik-rotate.path"
SERVICE = "fabrik-rotate.service"
AMBER = 0.85
CLEAR = 0.80  # 5 points below AMBER: a reading that hovers at the line opens one episode, not one per tick
TOP = 3
RESTART = f"systemctl --user reset-failed {UNIT} {SERVICE} && systemctl --user start {UNIT}"


def _state_path() -> Path:
    raw = os.environ.get("BOX_BUDGET_STATE")
    return Path(raw) if raw else Path.home() / ".claude" / "state" / "box-budget.json"


def _proc() -> Path:
    return Path(os.environ.get("BOX_BUDGET_PROC", "/proc"))


def _mail_script() -> Path:
    return Path(os.environ.get("FABRIK_OPT_DIR") or "/opt") / "fabrik" / "scripts" / "mail.py"


def _systemctl(*args: str) -> subprocess.CompletedProcess[str] | None:
    cmd = [os.environ.get("BOX_BUDGET_SYSTEMCTL", "systemctl"), "--user", *args]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None


def _user_bus() -> None:
    # cron carries no XDG_RUNTIME_DIR, and without it `systemctl --user` answers "Failed to connect to
    # bus" (measured); the agents_up.sh:413-416 idiom
    run = Path(f"/run/user/{os.getuid()}")
    if not os.environ.get("XDG_RUNTIME_DIR") and (run / "bus").is_socket():
        os.environ["XDG_RUNTIME_DIR"] = str(run)


# ── readings ──────────────────────────────────────────────────────────────────────────────────────


def _unit_state() -> dict[str, str] | None:
    """`{"enabled", "active", "sub", "result"}`, or None when systemctl cannot be asked."""
    en = _systemctl("is-enabled", UNIT)
    show = _systemctl("show", "-p", "ActiveState", "-p", "SubState", "-p", "Result", UNIT)
    if en is None or show is None or show.returncode != 0:
        return None
    vals = dict(ln.split("=", 1) for ln in show.stdout.splitlines() if "=" in ln)
    return {
        "enabled": en.stdout.strip() or "unknown",
        "active": vals.get("ActiveState", ""),
        "sub": vals.get("SubState", ""),
        "result": vals.get("Result", ""),
    }


def _read_int(p: Path) -> int | None:
    try:
        return int(p.read_text().strip())
    except (OSError, ValueError):
        return None


def inotify_reading() -> dict[str, object] | None:
    """Watches and instances in use by this uid, the maxima, and the top watch holders.

    None when a maximum cannot be read (no ratio can be formed)."""
    proc = _proc()
    max_w = _read_int(proc / "sys" / "fs" / "inotify" / "max_user_watches")
    max_i = _read_int(proc / "sys" / "fs" / "inotify" / "max_user_instances")
    if not max_w or not max_i:
        return None
    uid = os.getuid()
    watches = instances = 0
    holders: list[tuple[int, str, str]] = []
    try:
        entries = list(proc.iterdir())
    except OSError:
        return None
    for p in entries:
        if not p.name.isdigit():
            continue
        try:
            if p.stat().st_uid != uid:
                continue
            fds = list((p / "fd").iterdir())
        except OSError:
            continue
        n = 0
        for fd in fds:
            try:
                if os.readlink(fd) != "anon_inode:inotify":
                    continue
                instances += 1
                with (p / "fdinfo" / fd.name).open("rb") as fh:
                    n += sum(1 for ln in fh if ln.startswith(b"inotify wd:"))
            except OSError:
                continue
        if n:
            watches += n
            try:
                cmd = (p / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            except OSError:
                cmd = "?"
            holders.append((n, p.name, cmd.strip()[:100]))
    holders.sort(reverse=True)
    return {
        "watches": watches,
        "max_watches": max_w,
        "instances": instances,
        "max_instances": max_i,
        "load": max(watches / max_w, instances / max_i),
        "top": holders[:TOP],
    }


def _fmt_inotify(r: dict[str, object] | None) -> str:
    if r is None:
        return "inotify: unreadable"
    lines = [
        f"inotify watches {r['watches']}/{r['max_watches']} · instances {r['instances']}/{r['max_instances']}"
        f" · load {float(r['load']):.0%} (a lower bound: unreadable processes are skipped)"
    ]
    for n, pid, cmd in r["top"]:  # type: ignore[attr-defined]
        lines.append(f"  pid {pid}: {n} watches — {cmd}")
    return "\n".join(lines)


# ── episodes and mail ─────────────────────────────────────────────────────────────────────────────


def _load_state() -> dict[str, object]:
    try:
        d = json.loads(_state_path().read_text())
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _save_state(d: dict[str, object]) -> None:
    path = _state_path()
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(d, sort_keys=True))
        os.replace(tmp, path)
    except OSError as e:
        print(f"box-budget: state not written ({e.__class__.__name__}) — the next run may mail again")
        with contextlib.suppress(OSError):
            tmp.unlink()


def _mail(subject: str, body: str, ack: str) -> bool:
    script = _mail_script()
    if not script.is_file():
        print(f"box-budget: no {script} — alert printed only: {subject}")
        return False
    try:
        r = subprocess.run(
            [sys.executable, str(script), "send", "--to", "fabrik", "--to-agent", "coordinator",
             "--kind", "finding", "--ack", ack],
            input=f"{subject}\n\n{body}\n", capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as e:
        print(f"box-budget: mail not sent ({e.__class__.__name__}) — retried next run")
        return False
    if r.returncode != 0:
        print(f"box-budget: mail not sent (rc {r.returncode}) — retried next run")
        return False
    return True


# ── legs ──────────────────────────────────────────────────────────────────────────────────────────


def unit_leg(state: dict[str, object], reading: dict[str, object] | None) -> None:
    s = _unit_state()
    if s is None:
        print(f"box-budget: {UNIT} unreadable (systemctl failed) — nothing done")
        return
    if s["enabled"] != "enabled":
        print(f"box-budget: {UNIT} is {s['enabled']} — left alone")
        return
    if s["active"] == "active":
        if state.pop("unit", None) is not None:
            print(f"box-budget: {UNIT} active — episode closed")
        return
    if s["active"] not in ("failed", "inactive"):
        print(f"box-budget: {UNIT} is {s['active']} — transitional, nothing done")
        return
    was = f"ActiveState={s['active']} SubState={s['sub']} Result={s['result']}"
    _systemctl("reset-failed", UNIT, SERVICE)
    _systemctl("start", UNIT)
    after = _systemctl("is-active", UNIT)
    healed = after is not None and after.stdout.strip() == "active"
    print(f"box-budget: {UNIT} was {was} — restart {'held' if healed else 'FAILED'}")
    if state.get("unit") == ("healed" if healed else "failed"):
        return  # this episode already mailed
    subject = (
        f"{UNIT} was down ({was}) and the rotation tick restarted it"
        if healed
        else f"{UNIT} is down ({was}) and the rotation tick could NOT restart it — no builder can be rotated"
    )
    body = (
        f"WHAT: {subject}.\nWHEN: {time.strftime('%Y-%m-%d %H:%M:%S %z')}.\n"
        f"WHY (likely): a full per-user inotify budget fails a path unit with Result=resources.\n"
        f"{_fmt_inotify(reading)}\n"
        f"HOW: journalctl --user -u {UNIT} -n 20; restart by hand: {RESTART}; "
        f"budgets: python3 scripts/sysadmin/box_budget_check.py --report.\n"
        f"(W-09957e81 — box_budget_check.py, run by claude_rotate.py --tick every 5 min)"
    )
    if _mail(subject, body, "no" if healed else "required"):
        state["unit"] = "healed" if healed else "failed"


def inotify_leg(state: dict[str, object], reading: dict[str, object] | None) -> None:
    if reading is None:
        print("box-budget: inotify maxima unreadable — nothing done")
        return
    load = float(reading["load"])  # type: ignore[arg-type]
    if load < CLEAR:
        if state.pop("inotify", None) is not None:
            print(f"box-budget: inotify load {load:.0%} — episode closed")
        return
    if load < AMBER or state.get("inotify"):
        return
    subject = f"inotify budget at {load:.0%} — path units and file watchers fail at 100%"
    body = (
        f"WHAT: {subject}.\n{_fmt_inotify(reading)}\n"
        "WHY: every process of this user shares one watch budget; at 100% systemd path units "
        "(fabrik-rotate.path among them) fail with Result=resources.\n"
        "HOW: the usual holder is code-server's file watcher — keep its files.watcherExclude "
        "(docs/workstation/vscode-configuration.md § code-server) and reload the window.\n"
        "(W-09957e81 — box_budget_check.py, run by claude_rotate.py --tick every 5 min)"
    )
    print(f"box-budget: AMBER — {subject}")
    if _mail(subject, body, "required"):
        state["inotify"] = "amber"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args not in ([], ["--report"]):
        print("usage: box_budget_check.py [--report]", file=sys.stderr)
        return 2
    _user_bus()
    reading = inotify_reading()
    if args == ["--report"]:
        print(_fmt_inotify(reading))
        s = _unit_state()
        print(f"{UNIT}: " + (" ".join(f"{k}={v}" for k, v in s.items()) if s else "unreadable"))
        return 0
    lock_path = _state_path().with_name(f".{_state_path().name}.lock")
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock = lock_path.open("a")
    except OSError:
        print("box-budget: lock unavailable — nothing done")
        return 0
    with lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print("box-budget: another run holds the lock — nothing done")
            return 0
        try:
            state = _load_state()
            before = dict(state)
            unit_leg(state, reading)
            inotify_leg(state, reading)
            if state != before:
                _save_state(state)
        except Exception as e:  # noqa: BLE001 — a cron child: one line, never a traceback storm
            print(f"box-budget: INTERNAL ERROR {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
