#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/fabrik-deck.md | tests/test_fabrik_deck.py | docs/workstation/hooks-index.md | scripts/sysadmin/install_user_hooks.py
"""fabrik_deck.py code-server | install [--hub DIR] [--start] — the Fabrik Deck's code-server as a systemd user service.

The Deck (docs/superpowers/specs/2026-10-21-fabrik-deck-design.md, D-1106) shows every repo as a code-server workbench
in a Vivaldi tab. A hand-started code-server died with the 2026-10-21 WSL restart and nothing restarted it
(W-e89a9b5b), so it now runs as `fabrik-deck-code.service`, a user unit that starts at boot (linger on) and restarts on
a crash. The board, the attention hook, the profile and the launcher are the Deck plan's; this script grows with it.

code-server — exec `~/.local/bin/code-server --bind-addr 127.0.0.1:<FABRIK_DECK_CODE_PORT, default 8443>` with ONLY
the keep-list below in its environment, so the starting session's variables (`CLAUDE_AGENT`, the session id, the
messaging token) never reach the workbenches' claude processes. code-server's extension host then re-resolves the
login shell's environment for its children, which is how node and the login profile reach them. Logs go to stdout,
which the unit hands to the journal (`journalctl --user -u fabrik-deck-code`).

install — the session-archive installer's steps (scripts/sysadmin/install_session_archive_timer.sh). Every check runs
before the first write, so a refusal (exit 1) leaves both files as they were: linger must be on; `--hub` holds no
space, %, $, backslash or quote (the unit's ExecStart would split or expand it); the unit's ExecStart target and the
code-server binary must exist (`systemd-analyze verify` cannot see either); a unit file without our marker is never
overwritten; the rendered unit must pass `systemd-analyze --user verify` printing nothing (a misplaced key is only a
warning at rc 0); the env file's port must parse; with `--start`, nothing may listen on the port (the unit would fail
to bind). Then the env file ~/.config/fabrik-deck/env is created, or on a present one every line is kept and only
missing keys are appended (named on stderr), so an operator's override wins; files are written temp-then-rename,
keeping an existing file's mode; then daemon-reload, enable, and with `--start` start — a failing `systemctl` exits 1
with the files already written. The default only enables: the cutover from a hand start kills the claude processes in
the open Deck tabs, so it is run deliberately. The unit restarts a crashed code-server every 10 s with no limit
(StartLimitIntervalSec=0), but a startup failure exits 2 and RestartPreventExitStatus=2 stops it there.

`--hub` (default /opt/fabrik, the main checkout) is where the unit runs this script from; after changing it, run
`systemctl --user restart fabrik-deck-code` — a running unit keeps the old path until it restarts.

COBRA (D-253): the cheapest way to pass the tests is a unit that verifies and enables and never serves — no test
starts systemd. The counter is the live proof the coordinator asked for: after `wsl --shutdown`, Windows reaches
the Deck's port without anyone starting anything (the check is docs/workstation/fabrik-deck.md § Proof).
"""

from __future__ import annotations

import argparse
import json
import os
import pwd
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

UNIT_NAME = "fabrik-deck-code.service"
MARKER = "# Written by scripts/sysadmin/fabrik_deck.py install (W-e89a9b5b) — re-run it rather than editing this file."
KEEP = (
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "PATH",
    "LANG",
    "DISPLAY",
    "WAYLAND_DISPLAY",
    "XDG_RUNTIME_DIR",
    "CLAUDE_CONFIG_DIR",
    "CLAUDE_QUOTA_HOME",
    "FABRIK_DECK",
)
DEFAULT_PORT = 8443


def _die(code: int, msg: str) -> None:
    print(f"fabrik_deck: {msg}", file=sys.stderr)
    sys.exit(code)


def _parse_port(raw: str | None) -> int | None:
    """The port, or None when `raw` is not an ASCII integer in 1-65535 (`"²".isdigit()` is True, so isascii first)."""
    if raw is None:
        return DEFAULT_PORT
    if raw.isascii() and raw.isdigit() and 1 <= int(raw) <= 65535:
        return int(raw)
    return None


def code_server() -> None:
    # Every startup failure exits 2, which the unit's RestartPreventExitStatus=2 turns into a stop instead of a
    # retry every 10 s forever (StartLimitIntervalSec=0); only a crash of a running code-server restarts it.
    raw = os.environ.get("FABRIK_DECK_CODE_PORT")
    port = _parse_port(raw)
    if port is None:
        _die(2, f"FABRIK_DECK_CODE_PORT={raw!r} is not a port (1-65535)")
    home = Path(os.environ.get("HOME") or pwd.getpwuid(os.getuid()).pw_dir)
    binary = home / ".local" / "bin" / "code-server"
    env = {k: os.environ[k] for k in KEEP if k in os.environ}
    sys.stdout.flush()
    try:
        os.execve(str(binary), [str(binary), "--bind-addr", f"127.0.0.1:{port}"], env)
    except OSError as exc:
        _die(2, f"cannot start {binary}: {exc}")


def _env_defaults(home: Path) -> list[tuple[str, str]]:
    active = f"{home}/.claude-fleet/active"
    return [
        ("FABRIK_DECK_CODE_PORT", str(DEFAULT_PORT)),
        ("CLAUDE_CONFIG_DIR", active),
        ("CLAUDE_QUOTA_HOME", active),
        ("PATH", f"{home}/.local/bin:/usr/local/bin:/usr/bin:/bin"),
        ("FABRIK_DECK", "1"),
        ("DISPLAY", ":0"),
        ("WAYLAND_DISPLAY", "wayland-0"),
    ]


def _read_env(text: str, warn: bool = False) -> dict[str, str]:
    """KEY=value lines as systemd's EnvironmentFile= reads them (checked with `systemd-run --user -p
    EnvironmentFile=…`, 2026-10-21): `#` and `;` lines are comments; a line whose key is not a plain variable name —
    `export KEY=…` included — is ignored by systemd, so it is ignored here and named on stderr; one pair of matching
    surrounding quotes is removed; an inline `# …` stays part of the value, so `9000 # mine` is not a port to
    either reader."""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] in "#;" or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            if warn:
                print(
                    f"fabrik_deck: ignoring {line!r} — systemd ignores it too (not KEY=value)",
                    file=sys.stderr,
                )
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key] = value
    return out


def _atomic_write(path: Path, text: str) -> None:
    """Write via a temp file and rename; an existing file keeps its permission bits (the env file may be 0600)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _home() -> Path:
    return Path(os.environ.get("HOME") or pwd.getpwuid(os.getuid()).pw_dir)


def _env_path(home: Path) -> Path:
    return home / ".config" / "fabrik-deck" / "env"


def _state_dir(home: Path, environ: dict[str, str] | os._Environ[str]) -> Path:
    """FABRIK_DECK_STATE from the environment, else from the env file, else ~/.local/state/fabrik-deck. The hook runs
    in sessions that never load the env file (R-P10), so it reads the file itself; warn=False keeps every session's
    stderr clean."""
    value = environ.get("FABRIK_DECK_STATE")
    if not value:
        try:
            # errors="replace": one stray non-UTF-8 byte in the file must not silence every session's hook
            value = _read_env(_env_path(home).read_text(errors="replace")).get("FABRIK_DECK_STATE")
        except OSError:
            value = None
    if value:
        # `~` is expanded; a value that is still relative would land in whatever repo the session runs in, so it
        # falls back to the default instead.
        path = Path(value).expanduser()
        if path.is_absolute():
            return path
    return home / ".local" / "state" / "fabrik-deck"


WAITING = ("permission_prompt", "idle_prompt", "elicitation_dialog")


def hook() -> None:
    """One attention file per waiting session: <state>/attention/<session_id>.json = {cwd, type, origin, at}.

    Registered for Notification, UserPromptSubmit, Stop, PostToolUse and SessionEnd in every session on the box, so it
    prints nothing on stdout and main() turns every failure into exit 0. A denied permission fires PostToolUseFailure,
    not PostToolUse, so that dot becomes `turn_ended` at the next Stop and clears at the next prompt.
    """
    if sys.stdin.isatty():
        return
    try:
        payload = json.loads(sys.stdin.read())
    except ValueError:
        return
    if not isinstance(payload, dict):
        return
    sid = payload.get("session_id")
    if not isinstance(sid, str) or not sid or "/" in sid or sid in (".", ".."):
        return
    event = payload.get("hook_event_name")
    path = _state_dir(_home(), os.environ) / "attention" / f"{sid}.json"

    def write(kind: str) -> None:
        if os.environ.get("TMUX"):
            origin = "tmux"
        elif os.environ.get("FABRIK_DECK") == "1":
            origin = "deck"
        else:
            origin = "other"
        record = {
            "cwd": str(payload.get("cwd") or ""),
            "type": kind,
            "origin": origin,
            "at": time.time(),
        }
        _atomic_write(path, json.dumps(record))

    if event == "Notification":
        if payload.get("notification_type") in WAITING:
            write(payload["notification_type"])
    elif event == "Stop":
        write("turn_ended")
    elif event == "PostToolUse":
        # Every tool call of every session lands here: stat first, read only when a file exists.
        if path.exists():
            try:
                kind = json.loads(path.read_text()).get("type")
            except (OSError, ValueError, AttributeError):
                return
            if kind == "permission_prompt":
                path.unlink(missing_ok=True)
    elif event in ("UserPromptSubmit", "SessionEnd"):
        path.unlink(missing_ok=True)


def _render_unit(hub: Path, env_file: Path) -> str:
    return (
        f"{MARKER}\n"
        "# The Fabrik Deck's code-server (docs/workstation/fabrik-deck.md, D-1106).\n"
        "[Unit]\n"
        "Description=Fabrik Deck code-server (127.0.0.1, auth none)\n"
        "StartLimitIntervalSec=0\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"EnvironmentFile={env_file}\n"
        f"ExecStart=/usr/bin/python3 {hub}/scripts/sysadmin/fabrik_deck.py code-server\n"
        "Restart=always\n"
        "RestartSec=10\n"
        "RestartPreventExitStatus=2\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


def _systemctl(*args: str) -> None:
    r = subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True)
    if r.returncode != 0:
        _die(1, f"systemctl --user {' '.join(args)} failed (rc {r.returncode}): {r.stderr.strip()}")


def _listening(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def install(hub: Path, start: bool) -> None:
    user = pwd.getpwuid(os.getuid()).pw_name
    home = Path(os.environ.get("HOME") or pwd.getpwuid(os.getuid()).pw_dir)

    linger = subprocess.run(
        ["loginctl", "show-user", user, "-p", "Linger"], capture_output=True, text=True
    )
    if linger.stdout.strip() != "Linger=yes":
        _die(
            1,
            f"linger is off for {user} ({linger.stdout.strip() or 'no answer'}); enable it once with: "
            f"loginctl enable-linger {user}",
        )
    if any(c in str(hub) for c in " \t\n%$\\\"'"):
        _die(
            1,
            f"--hub {str(hub)!r} holds a space, %, $, \\ or a quote, which the unit's ExecStart would split or expand",
        )
    target = hub / "scripts" / "sysadmin" / "fabrik_deck.py"
    binary = home / ".local" / "bin" / "code-server"
    for path in (target, binary):
        if not path.is_file():
            _die(1, f"{path} does not exist — the unit would fail at every start")

    env_file = _env_path(home)
    unit_path = home / ".config" / "systemd" / "user" / UNIT_NAME
    if unit_path.exists() and not unit_path.read_text().startswith(MARKER):
        _die(1, f"{unit_path} exists and was not written by this script — move it aside first")

    unit_text = _render_unit(hub, env_file)
    with tempfile.TemporaryDirectory() as tmp:
        probe = Path(tmp) / UNIT_NAME
        probe.write_text(unit_text)
        v = subprocess.run(
            ["systemd-analyze", "--user", "verify", str(probe)], capture_output=True, text=True
        )
    if v.returncode != 0 or v.stderr.strip() or v.stdout.strip():
        _die(
            1, f"systemd-analyze --user verify rejected the unit: {(v.stderr or v.stdout).strip()}"
        )

    # Every check above and here runs before the first write, so a refusal leaves both files as they were.
    existing = env_file.read_text() if env_file.exists() else ""
    present = _read_env(existing, warn=True)
    missing = [(k, v_) for k, v_ in _env_defaults(home) if k not in present]
    sep = "" if not existing or existing.endswith("\n") else "\n"
    merged = existing + (sep + "".join(f"{k}={v_}\n" for k, v_ in missing) if missing else "")
    raw = _read_env(merged).get("FABRIK_DECK_CODE_PORT")
    port = _parse_port(raw)
    if port is None:
        _die(1, f"{env_file}: FABRIK_DECK_CODE_PORT={raw!r} is not a port (1-65535)")
    if start and _listening(port):
        _die(
            1,
            f"127.0.0.1:{port} is already in use — stop the process holding it, then re-run with --start",
        )

    if missing:
        if existing:
            print(
                f"fabrik_deck: {env_file}: appending missing keys {', '.join(k for k, _ in missing)}",
                file=sys.stderr,
            )
        _atomic_write(env_file, merged)
    _atomic_write(unit_path, unit_text)
    _systemctl("daemon-reload")
    _systemctl("enable", UNIT_NAME)
    if start:
        _systemctl("start", UNIT_NAME)
    r = subprocess.run(
        ["systemctl", "--user", "is-enabled", UNIT_NAME], capture_output=True, text=True
    )
    print(f"{UNIT_NAME}: {r.stdout.strip() or r.stderr.strip()}")


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["hook"]:
        # Before argparse: a usage error or any exception must never block the session that fired the hook.
        try:
            hook()
        except BaseException as exc:  # noqa: BLE001 — the hook's contract is exit 0, always
            # With fd 2 closed sys.stderr is None, and print(file=None) would write to STDOUT — which UserPromptSubmit
            # injects into the session. So: stderr or nothing, and a broken stderr never becomes a non-zero exit.
            if sys.stderr is not None:
                try:
                    print(f"fabrik_deck hook: {type(exc).__name__}: {exc}", file=sys.stderr)
                except BaseException:  # noqa: BLE001
                    pass
        sys.exit(0)
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser(
        "code-server", help="exec code-server with the clean environment (the unit's ExecStart)"
    )
    ins = sub.add_parser("install", help="install and enable fabrik-deck-code.service")
    ins.add_argument(
        "--hub",
        type=Path,
        default=Path("/opt/fabrik"),
        help="checkout the unit runs this script from",
    )
    ins.add_argument(
        "--start", action="store_true", help="also start it (refused while the port is in use)"
    )
    sub.add_parser("hook", help="the attention hook (stdin: the hook event JSON); always exits 0")
    args = ap.parse_args(argv)
    if args.cmd == "code-server":
        code_server()
    else:
        if shutil.which("systemd-analyze") is None:
            _die(1, "systemd-analyze is not installed")
        install(args.hub.resolve(), args.start)


if __name__ == "__main__":
    main()
