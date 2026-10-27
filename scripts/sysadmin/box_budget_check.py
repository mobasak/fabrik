#!/usr/bin/env python3
# AFTER-EDIT: tests/test_box_budget_check.py | docs/workstation/vscode-configuration.md | docs/workstation/claude-account-rotation.md
"""The box's shared per-user budgets, watched from the 5-minute rotation tick (W-09957e81).

On 2026-10-27 at 11:12 `fabrik-rotate.path` failed with result `resources` ("Failed to enter waiting
state: No space left on device"): code-server's three file watchers held 523,576 of this user's
524,288 inotify watches. A failed path unit stays failed — systemd never restarts it — so for most of
an hour no builder in any repo could be rotated, and nothing said so.

`claude_rotate.py --tick` spawns this script detached, with no inherited stdio (the quota board reads
the tick through a captured pipe), every five minutes. Two legs, each alerting by fabrik-mail to the
hub coordinator once per EPISODE:

- **unit** — when `fabrik-rotate.path` is ENABLED (`enabled` or `enabled-runtime`) and reads `failed` or `inactive`, read both units'
  Result (a reset wipes the service's), `reset-failed` both, `start` the path unit, re-read it. A unit
  that is not enabled is the operator's choice and is left alone — disable it to keep it down: an
  enabled unit stopped by hand is restarted at the next tick. Any other state (`activating`,
  `deactivating`, `reloading`) or a systemctl that cannot be asked acts on nothing: this leg fails
  OPEN, so a fault here costs one more tick of an outage, never a fight with the operator. Episode:
  opens on a failed/inactive reading (a heal that held mails `--ack no`, one that failed `--ack
  required`); inside it further heals are logged, not mailed, except the first FAILED heal of an
  episode that had only healed (an escalation); it closes only after an hour of `active` since its
  last bad reading, so a unit dying between ticks mails at most hourly, and a close after a failed
  heal mails "recovered". The episode is recorded when it opens, whatever the mail did: a send that
  fails is QUEUED on it and retried, oldest first, on every later run before anything else — a heal
  that held leaves the unit active, so nothing else would ever send it — and the episode closes only
  with its queue empty. A record without a numeric `last_bad` is not one of this script's episodes
  and is dropped.
- **inotify** — watches in use (the `inotify wd:` lines of /proc/<pid>/fdinfo/<fd> for each fd of
  this uid's processes linking to `anon_inode:inotify`) and those instances, against
  /proc/sys/fs/inotify/max_user_{watches,instances}. The scan is an ESTIMATE — a process whose fd table
  cannot be read is skipped (and counted: 9 of 558 measured, non-dumpable daemons and zombies), an fd
  shared across fork is counted per holder (0 such sets measured) — so a CANARY settles exhaustion:
  one `inotify_init1` + `inotify_add_watch` on `/`, closed at once (it creates nothing); EMFILE means
  the instances are gone, ENOSPC the watches. AMBER at 85% of either ratio, EXHAUSTED on a canary
  exhaustion; an episode opened at AMBER mails again once if it reaches EXHAUSTED, and clears only
  below 80% with the canary not exhausted (5 points of hysteresis: a reading hovering at the line mails
  once, not every tick). With no readable process at all the scan is `unknown` and opens nothing
  unless the canary says exhausted. The scan costs ~0.9 s at 114,598 watches (measured), ~4 s at the
  full budget: fine for a detached tick child, too slow for a per-prompt hook. An inotify episode is
  recorded only once its mail was sent (rc 0); while the budget stays high, the next run sends again.

Each leg runs in its own guard and the state is saved after each, so a fault in one leg costs neither
the other leg nor a mail the first one already sent. A state file that is missing, unreadable or
corrupt reads as "no open episode" — the worst case is one duplicate mail, never a lost alert. Log
lines and mail text are written as UTF-8 whatever cron's locale. Cobra (D-253): the cheapest way to silence the
unit alert is to keep healing a unit that keeps dying — every new episode mails (a successful heal
too) and an episode needs an hour of health to close; the cheapest way to silence the budget alert is
a scan that sees nothing — the canary answers that.

Modes: no argument = the tick run (heal, probe, alert; output appended to the log; always exits 0);
`--report` = print the readings to stdout, change and mail nothing; exits 2 when the unit is enabled
and not active or the budget is AMBER or exhausted, 1 when the inotify reading is unknown or systemctl
cannot be asked, else 0.

Seams (tests): BOX_BUDGET_STATE (state file), BOX_BUDGET_LOG (log file), FABRIK_OPT_DIR (mail.py
under <opt>/fabrik/scripts), BOX_BUDGET_PROC (the /proc root), BOX_BUDGET_SYSTEMCTL (the systemctl
command).
"""

from __future__ import annotations

import contextlib
import ctypes
import errno
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
CLEAR = (
    0.80  # 5 points below AMBER: a reading hovering at the line opens one episode, not one per tick
)
HEALTHY_S = 3600  # a unit episode closes after an hour of `active` since its last bad reading
ENABLED = ("enabled", "enabled-runtime")  # `systemctl is-enabled` answers that mean "meant to run"
TOP = 3
SYSTEMCTL_TIMEOUT_S = 10
MAIL_TIMEOUT_S = 30
RESTART = f"systemctl --user reset-failed {UNIT} {SERVICE} && systemctl --user start {UNIT}"
FOOTER = "(W-09957e81 — scripts/sysadmin/box_budget_check.py, spawned by claude_rotate.py --tick every 5 min)"
_IN_NONBLOCK = 0o4000
_IN_CLOEXEC = 0o2000000
_IN_DELETE_SELF = 0x400


def _now() -> float:
    return time.time()


def _state_path() -> Path:
    raw = os.environ.get("BOX_BUDGET_STATE")
    return Path(raw) if raw else Path.home() / ".claude" / "state" / "box-budget.json"


def _log_path() -> Path:
    raw = os.environ.get("BOX_BUDGET_LOG")
    return Path(raw) if raw else _state_path().with_name("box-budget.log")


def _proc() -> Path:
    return Path(os.environ.get("BOX_BUDGET_PROC", "/proc"))


def _mail_script() -> Path:
    return Path(os.environ.get("FABRIK_OPT_DIR") or "/opt") / "fabrik" / "scripts" / "mail.py"


def _log(line: str) -> None:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(_now()))
    with contextlib.suppress(OSError):
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        # UTF-8 whatever cron's locale: a command line or an em dash under LANG=C is a ValueError, not an OSError
        with path.open("a", encoding="utf-8", errors="replace") as fh:
            fh.write(f"{stamp} box-budget: {line}\n")


def _systemctl(*args: str) -> subprocess.CompletedProcess[str] | None:
    cmd = [os.environ.get("BOX_BUDGET_SYSTEMCTL", "systemctl"), "--user", *args]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=SYSTEMCTL_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return None


def _user_bus() -> None:
    # cron carries no XDG_RUNTIME_DIR, and without it `systemctl --user` answers "Failed to connect to
    # bus" (measured); the agents_up.sh:413-416 idiom
    run = Path(f"/run/user/{os.getuid()}")
    if not os.environ.get("XDG_RUNTIME_DIR") and (run / "bus").is_socket():
        os.environ["XDG_RUNTIME_DIR"] = str(run)


# ── readings ──────────────────────────────────────────────────────────────────────────────────────


def _show(unit: str) -> dict[str, str] | None:
    r = _systemctl("show", "-p", "ActiveState", "-p", "SubState", "-p", "Result", unit)
    if r is None or r.returncode != 0:
        return None
    return dict(ln.split("=", 1) for ln in r.stdout.splitlines() if "=" in ln)


def unit_state() -> dict[str, str] | None:
    """The path unit's enablement and state, and the service's Result; None when systemctl cannot be asked."""
    en = _systemctl("is-enabled", UNIT)
    path, svc = _show(UNIT), _show(SERVICE)
    if en is None or path is None:
        return None
    return {
        "enabled": en.stdout.strip() or "unknown",
        "active": path.get("ActiveState", ""),
        "sub": path.get("SubState", ""),
        "result": path.get("Result", ""),
        "service_result": (svc or {}).get("Result", "") or "unknown",
    }


def _canary() -> str:
    """`ok`, `instances` (EMFILE: no inotify instance left), `watches` (ENOSPC: no watch left), or `unknown`."""
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        fd = libc.inotify_init1(_IN_NONBLOCK | _IN_CLOEXEC)
        if fd < 0:
            return "instances" if ctypes.get_errno() == errno.EMFILE else "unknown"
        try:
            # the root always exists, so the canary creates nothing (`--report` changes nothing)
            if libc.inotify_add_watch(fd, b"/", _IN_DELETE_SELF) < 0:
                return "watches" if ctypes.get_errno() == errno.ENOSPC else "unknown"
            return "ok"
        finally:
            os.close(fd)
    except (OSError, AttributeError):
        return "unknown"


def _read_int(p: Path) -> int | None:
    try:
        return int(p.read_text().strip())
    except (OSError, ValueError):
        return None


def inotify_reading() -> dict[str, object] | None:
    """The scan, the maxima and the canary; None when a maximum cannot be read."""
    proc = _proc()
    max_w = _read_int(proc / "sys" / "fs" / "inotify" / "max_user_watches")
    max_i = _read_int(proc / "sys" / "fs" / "inotify" / "max_user_instances")
    if not max_w or not max_i:
        return None
    uid = os.getuid()
    watches = instances = readable = unreadable = 0
    holders: list[tuple[int, int, str, str]] = []
    try:
        entries = list(proc.iterdir())
    except OSError:
        entries = []
    for p in entries:
        if not p.name.isdigit():
            continue
        try:
            if p.stat().st_uid != uid:
                continue
            fds = list((p / "fd").iterdir())
        except OSError:
            unreadable += 1
            continue
        readable += 1
        n = k = 0
        for fd in fds:
            try:
                if os.readlink(fd) != "anon_inode:inotify":
                    continue
                with (p / "fdinfo" / fd.name).open("rb") as fh:
                    n += sum(1 for ln in fh if ln.startswith(b"inotify wd:"))
                k += 1
            except OSError:
                continue
        if k:
            watches += n
            instances += k
            try:
                cmd = (p / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            except OSError:
                cmd = "?"
            holders.append((n, k, p.name, cmd.strip()[:100]))
    w_load, i_load = watches / max_w, instances / max_i
    by_instances = i_load > w_load
    holders.sort(key=lambda h: (h[1], h[0]) if by_instances else (h[0], h[1]), reverse=True)
    return {
        "watches": watches,
        "max_watches": max_w,
        "instances": instances,
        "max_instances": max_i,
        "load": max(w_load, i_load),
        "readable": readable,
        "unreadable": unreadable,
        "canary": _canary(),
        "top": holders[:TOP],
    }


def _known(r: dict[str, object] | None) -> bool:
    return r is not None and int(r["readable"]) > 0  # type: ignore[call-overload]


def _exhausted(r: dict[str, object] | None) -> bool:
    return r is not None and r["canary"] in ("watches", "instances")


def _amber(r: dict[str, object] | None) -> bool:
    return _exhausted(r) or (_known(r) and float(r["load"]) >= AMBER)  # type: ignore[index, arg-type]


def _fmt_inotify(r: dict[str, object] | None) -> str:
    if r is None:
        return "inotify: maxima unreadable"
    canary = {
        "ok": "ok",
        "watches": "EXHAUSTED — inotify_add_watch answered ENOSPC: no watch is left",
        "instances": "EXHAUSTED — inotify_init1 answered EMFILE: no instance is left",
        "unknown": "unknown",
    }[str(r["canary"])]
    head = (
        f"inotify watches {r['watches']}/{r['max_watches']} · instances {r['instances']}/{r['max_instances']}"
        f" · load {float(r['load']):.0%} (estimate; {r['unreadable']} processes unreadable)"  # type: ignore[arg-type]
        if _known(r)
        else f"inotify unknown — no process readable ({r['unreadable']} unreadable)"
    )
    lines = [head, f"canary: {canary}"]
    for n, k, pid, cmd in r["top"]:  # type: ignore[attr-defined]
        lines.append(f"  pid {pid}: {n} watches, {k} instances — {cmd}")
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
        _log(f"state not written ({type(e).__name__}) — the next run may mail again")
        with contextlib.suppress(OSError):
            tmp.unlink()


def _mail(subject: str, body: str, ack: str) -> bool:
    script = _mail_script()
    if not script.is_file():
        _log(f"no {script} — alert logged only: {subject}")
        return False
    try:
        r = subprocess.run(
            [
                sys.executable,
                str(script),
                "send",
                "--to",
                "fabrik",
                "--to-agent",
                "coordinator",
                "--kind",
                "finding",
                "--ack",
                ack,
            ],
            input=f"{subject}\n\n{body}\n{FOOTER}\n",
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=MAIL_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError) as e:
        _log(f"mail not sent ({type(e).__name__}) — retried next run")
        return False
    if r.returncode != 0:
        _log(f"mail not sent (rc {r.returncode}) — retried next run")
        return False
    return True


# ── legs ──────────────────────────────────────────────────────────────────────────────────────────


def _send(ep: dict[str, object], subject: str, body: str, ack: str) -> None:
    """Mail now; a send that fails is QUEUED on the episode, so a later run retries it whatever the unit reads then."""
    if not _mail(subject, body, ack):
        queued = ep.get("unsent")
        ep["unsent"] = [*(queued if isinstance(queued, list) else []), [subject, body, ack]]


def _flush(ep: dict[str, object]) -> None:
    """Retry every queued mail of the episode, oldest first; one that fails again stays queued, with those after it."""
    queued = ep.pop("unsent", None)
    if not isinstance(queued, list):
        return
    for i, item in enumerate(queued):
        if not (
            isinstance(item, list) and len(item) == 3 and all(isinstance(x, str) for x in item)
        ):
            continue  # a malformed entry this script did not write is dropped, never sent
        if not _mail(*item):
            ep["unsent"] = queued[i:]
            return


def unit_leg(state: dict[str, object], reading: dict[str, object] | None) -> None:
    raw = state.get("unit")
    ep: dict[str, object] = raw if isinstance(raw, dict) else {}
    if ep and not isinstance(ep.get("last_bad"), (int, float)):
        ep = {}  # a record without its last bad reading names no episode this script can close
    if ep:
        state["unit"] = (
            ep  # held by reference: what this run changes in it is saved even if a later step raises
        )
        _flush(ep)
    else:
        state.pop("unit", None)
    s = unit_state()
    if s is None:
        _log(f"{UNIT} unreadable (systemctl could not be asked) — nothing done")
        return
    if s["enabled"] not in ENABLED:
        _log(f"{UNIT} is {s['enabled']} — left alone")
        return
    if s["active"] == "active":
        last_bad = ep.get("last_bad")
        if (
            ep
            and not ep.get("unsent")
            and isinstance(last_bad, (int, float))
            and _now() - last_bad >= HEALTHY_S
        ):
            if ep.get("state") == "failed":
                ep["state"] = "recovered"
                _send(
                    ep,
                    f"{UNIT} recovered — active for an hour since the failed restart",
                    f"WHAT: {UNIT} has read active for {HEALTHY_S // 60} min; the episode is closed.",
                    "no",
                )
                if ep.get("unsent"):
                    return  # closed once the recovered mail is out
            state.pop("unit", None)
            _log(f"{UNIT} active for an hour — episode closed")
        return
    if s["active"] not in ("failed", "inactive"):
        _log(f"{UNIT} is {s['active']} — transitional, nothing done")
        return
    was = (
        f"ActiveState={s['active']} SubState={s['sub']} Result={s['result']}"
        f" (service Result={s['service_result']})"
    )
    _systemctl("reset-failed", UNIT, SERVICE)
    _systemctl("start", UNIT)
    after = _systemctl("is-active", UNIT)
    healed = after is not None and after.stdout.strip() == "active"
    _log(f"{UNIT} was {was} — restart {'held' if healed else 'FAILED'}")
    prior = ep.get("state")
    ep["last_bad"] = _now()
    ep["state"] = "failed" if (prior == "failed" or not healed) else "healed"
    state["unit"] = ep
    if prior in (None, "recovered") or (prior == "healed" and not healed):
        subject = (
            f"{UNIT} was down and the rotation tick restarted it"
            if healed
            else f"{UNIT} is down and the rotation tick could NOT restart it — no builder can be rotated"
        )
        body = (
            f"WHAT: {subject}. Before the restart: {was}.\n"
            f"WHEN: {time.strftime('%Y-%m-%d %H:%M:%S %z', time.localtime(_now()))}.\n"
            "WHY (likely): a full per-user inotify budget fails a path unit with Result=resources.\n"
            f"{_fmt_inotify(reading)}\n"
            f"HOW: journalctl --user -u {UNIT} -n 20; restart by hand: {RESTART}; "
            "budgets: python3 scripts/sysadmin/box_budget_check.py --report"
        )
        _send(ep, subject, body, "no" if healed else "required")


def inotify_leg(state: dict[str, object], reading: dict[str, object] | None) -> None:
    if reading is None:
        _log("inotify maxima unreadable — nothing done")
        return
    if not _known(reading) and not _exhausted(reading):
        _log(
            f"inotify unknown — no process readable ({reading['unreadable']} unreadable); canary {reading['canary']}"
        )
        return
    load = float(reading["load"])  # type: ignore[arg-type]
    if not _amber(reading):
        if load < CLEAR and state.pop("inotify", None) is not None:
            _log(f"inotify load {load:.0%} — episode closed")
        return
    level = "exhausted" if _exhausted(reading) else "amber"
    held = state.get("inotify")
    if held == "exhausted" or held == level:
        return  # this episode already mailed at this level or a worse one
    subject = (
        f"inotify budget exhausted ({reading['canary']}) — path units and file watchers are failing"
        if level == "exhausted"
        else f"inotify budget at {load:.0%} — path units and file watchers fail at 100%"
    )
    body = (
        f"WHAT: {subject}.\n{_fmt_inotify(reading)}\n"
        "WHY: every process of this user shares one inotify budget; at 100% systemd path units "
        "(fabrik-rotate.path among them) fail with Result=resources.\n"
        "HOW: the usual holder is code-server's file watcher — keep its files.watcherExclude "
        "(docs/workstation/vscode-configuration.md § code-server) and reload the window."
    )
    _log(f"{level.upper()} — {subject}")
    if _mail(subject, body, "required"):
        state["inotify"] = level


def report() -> int:
    reading = inotify_reading()
    print(_fmt_inotify(reading))
    s = unit_state()
    print(f"{UNIT}: " + (" ".join(f"{k}={v}" for k, v in s.items()) if s else "unreadable"))
    if (s and s["enabled"] in ENABLED and s["active"] != "active") or _amber(reading):
        return 2
    return 0 if _known(reading) and s is not None else 1


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args not in ([], ["--report"]):
        print("usage: box_budget_check.py [--report]", file=sys.stderr)
        return 2
    _user_bus()
    if args == ["--report"]:
        return report()
    lock_path = _state_path().with_name(f".{_state_path().name}.lock")
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock = lock_path.open("a")
    except OSError:
        _log("lock unavailable — nothing done")
        return 0
    with lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            _log("another run holds the lock — nothing done")
            return 0
        reading: dict[str, object] | None = None
        try:
            reading = inotify_reading()
        except Exception as e:  # noqa: BLE001 — a cron child: one log line, never a traceback
            _log(f"INTERNAL ERROR in the scan {type(e).__name__}: {e}")
        state = _load_state()
        for leg in (unit_leg, inotify_leg):
            before = json.dumps(state, sort_keys=True)
            try:
                leg(state, reading)
            except Exception as e:  # noqa: BLE001 — one leg's fault never costs the other leg, or the state
                _log(f"INTERNAL ERROR in {leg.__name__} {type(e).__name__}: {e}")
            # saved after EACH leg: a mail one leg sent is recorded before the next leg can raise
            if json.dumps(state, sort_keys=True) != before:
                _save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
