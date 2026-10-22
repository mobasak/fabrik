#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/fabrik-deck.md | tests/test_fabrik_deck.py | docs/workstation/hooks-index.md | scripts/sysadmin/install_user_hooks.py
"""fabrik_deck.py code-server | serve | hook | install [--hub DIR] [--start] — the Fabrik Deck's code-server as a systemd user service.

The Deck (docs/superpowers/specs/2026-10-21-fabrik-deck-design.md, D-1106) shows every repo as a code-server workbench
in a Vivaldi tab. A hand-started code-server died with the 2026-10-21 WSL restart and nothing restarted it
(W-e89a9b5b), so it now runs as `fabrik-deck-code.service`, a user unit that starts at boot (linger on) and restarts on
a crash. The board, the attention hook, the profile and the launcher are the Deck plan's; this script grows with it.

code-server — exec `~/.local/bin/code-server --bind-addr 127.0.0.1:<FABRIK_DECK_CODE_PORT, default 8443>` with ONLY
the keep-list below in its environment, so the starting session's variables (`CLAUDE_AGENT`, the session id, the
messaging token) never reach the workbenches' claude processes. code-server's extension host then re-resolves the
login shell's environment for its children, which is how node and the login profile reach them. Logs go to stdout,
which the unit hands to the journal (`journalctl --user -u fabrik-deck-code`).

serve — the board on 127.0.0.1:<FABRIK_DECK_PORT, default 8445>: one row per repo (the git repositories under
`--opt-root`, then the registry's other paths), a dot and the agent's name while a session there waits on the
operator, a link opening that repo in code-server. Routes: `/`, `/api/repos`, `/api/attention`, `/api/events` (SSE).
GET only (405 otherwise), and a Host other than localhost/127.0.0.1 at the bound port is refused 421, because a page
reached by DNS rebinding would otherwise read the catalog. Attention files older than 24 h are deleted as they are
read. A bad port, a bound port or an unreadable registry at startup exits 2.

hook — see hook() below; registered by scripts/sysadmin/install_user_hooks.py.

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
import math
import os
import pwd
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import NoReturn

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
DECK_PORT = 8445
HUB = Path(__file__).resolve().parents[2]


def _die(code: int, msg: str) -> NoReturn:
    print(f"fabrik_deck: {msg}", file=sys.stderr)
    sys.exit(code)


def _parse_port(raw: str | None, default: int = DEFAULT_PORT) -> int | None:
    """The port, or None when `raw` is not an ASCII integer in 1-65535 (`"²".isdigit()` is True, so isascii first)."""
    if raw is None:
        return default
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
        try:
            path = Path(value).expanduser()
        except RuntimeError:  # `~someuser` for a user that does not exist
            path = Path(value)
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


# --- serve: the board, its catalog and the attention reader (plan 2026-10-22-plan-1-fabrik-deck, Phase B) ---------

# bytes of a repo's `.fabrik/session-agents.json` read at most (scripts/agent_status.py:189)
AGENTS_MAX = 1 << 20
# an attention file older than this is a session that died without SessionEnd
ATTENTION_TTL = 24 * 3600
# seconds a built catalog is reused: a build takes ~30 ms and every SSE client reads it twice a second
CATALOG_TTL = 10.0


def _session_agents(repo: Path) -> dict[str, str]:
    """`{session id: agent name}` from the repo's `.fabrik/session-agents.json` — a regular file, read bounded, a JSON
    object; anything else (damaged, truncated past the bound, a directory) reads as no agents."""
    reg = repo / ".fabrik" / "session-agents.json"
    try:
        if not stat.S_ISREG(reg.stat().st_mode):
            return {}
        with reg.open("rb") as fh:
            data = json.loads(fh.read(AGENTS_MAX).decode("utf-8", "replace"))
    except (OSError, ValueError, RecursionError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}


def _catalog(registry: Path, opt_root: Path) -> list[dict]:
    """Every repo once: the git repositories directly under `opt_root` (named by their directory), then the registry's
    paths not already seen (named by their key). A missing path is dropped; a registry path that is not a repository is
    kept with `git: false`. Each row carries `_agents`, the session map the attention reader labels with."""
    import yaml  # the unit runs /usr/bin/python3, which carries PyYAML; imported here so `hook` never pays for it

    data = yaml.safe_load(registry.read_text()) or {}
    projects = data.get("projects") if isinstance(data, dict) else None
    candidates: list[tuple[str, Path]] = []
    try:
        with os.scandir(opt_root) as it:
            for entry in sorted(it, key=lambda e: e.name):
                try:
                    if entry.is_dir() and (Path(entry.path) / ".git").exists():
                        candidates.append((entry.name, Path(entry.path)))
                except OSError:  # an unreadable entry, such as /opt/containerd
                    continue
    except OSError:
        pass
    if isinstance(projects, dict):
        for name, spec in projects.items():
            if (
                isinstance(spec, dict)
                and isinstance(spec.get("path"), str)
                and spec["path"].startswith("/")
            ):
                candidates.append((str(name), Path(spec["path"])))
    rows, seen = [], set()
    for name, path in candidates:
        try:  # one bad entry (a NUL in a path, an unsearchable directory) skips that entry, never the catalog
            real = path.resolve()
            if real in seen or not real.is_dir():
                continue
            git = (real / ".git").exists()
        except (OSError, RuntimeError, ValueError):
            continue
        seen.add(real)
        agents = _session_agents(real)
        rows.append(
            {
                "name": name,
                "path": str(real),
                "git": git,
                "agents": sorted(set(agents.values())),
                "_agents": agents,
            }
        )
    return sorted(rows, key=lambda r: r["name"].lower())


def _public(rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]


def catalog(registry: Path, opt_root: Path) -> list[dict]:
    return _public(_catalog(registry, opt_root))


def _label(sid: str, origin: str, repo: str, agents: dict[str, str]) -> str:
    if sid in agents:
        return agents[sid]
    if origin == "deck":
        return f"coordinator ({repo} tab)"
    if origin == "tmux":
        return f"session {sid[:8]} (tmux)"
    return f"session {sid[:8]}"


def attention(state: Path, rows: list[dict], now: float) -> list[dict]:
    """The waiting sessions, each mapped to the catalog repo whose path is the longest whole-component prefix of its
    cwd (so /opt/fabrik-lib never matches /opt/fabrik, and a worktree cwd maps to its repo), else `other`. Files older
    than ATTENTION_TTL are deleted on the way."""
    by_parts = sorted(((Path(r["path"]).parts, r) for r in rows), key=lambda t: -len(t[0]))
    out: list[dict] = []
    try:
        files = sorted((state / "attention").glob("*.json"))
    except OSError:
        return out
    for f in files:
        try:
            rec = json.loads(f.read_text(errors="replace"))
            at = float(rec["at"])
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OverflowError,
            RecursionError,
        ):
            continue
        if not math.isfinite(at) or now - at > ATTENTION_TTL:
            # stale, or a time no clock wrote (NaN would also make the JSON invalid for the board's JSON.parse)
            try:
                f.unlink(missing_ok=True)
            except OSError:
                pass
            continue
        sid = f.stem
        cwd = str(rec.get("cwd") or "/")
        # Catalog paths are resolved, so the cwd is matched as written (normalised) and resolved: a repo reached
        # through a symlink still maps, and `..` never leaves a lexical match behind.
        try:
            forms = {os.path.normpath(cwd), os.path.realpath(cwd)}
        except (OSError, ValueError):
            forms = {os.path.normpath(cwd)}
        match = next(
            (r for p, r in by_parts if any(Path(c).parts[: len(p)] == p for c in forms)), None
        )
        repo = match["name"] if match else "other"
        origin = str(rec.get("origin") or "other")
        out.append(
            {
                "session": sid,
                "repo": repo,
                "path": match["path"] if match else None,
                "label": _label(sid, origin, repo, match["_agents"] if match else {}),
                "type": str(rec.get("type") or ""),
                "at": at,
            }
        )
    return sorted(out, key=lambda a: a["at"])


BOARD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fabrik Deck</title>
<style>
:root{color-scheme:dark;--bg:#1f1f1f;--fg:#ccc;--dim:#888;--line:#333;--dot:#e5a50a;--link:#4daafc}
body{margin:0;background:var(--bg);color:var(--fg);font:14px system-ui,sans-serif}
header{display:flex;gap:8px;align-items:center;padding:12px 16px;border-bottom:1px solid var(--line)}
input{flex:1;background:#2a2a2a;color:var(--fg);border:1px solid var(--line);border-radius:4px;padding:6px 8px}
button{background:#2a2a2a;color:var(--fg);border:1px solid var(--line);border-radius:4px;padding:6px 10px;cursor:pointer}
ul{list-style:none;margin:0;padding:0}
li{display:flex;gap:10px;align-items:center;padding:8px 16px;border-bottom:1px solid var(--line)}
li a{color:var(--link);text-decoration:none;font-weight:600}
.dot{width:10px;height:10px;border-radius:50%;background:var(--dot);flex:none}
.idle{background:transparent}
.who,.path{color:var(--dim)}
.path{margin-left:auto;font-size:12px}
</style></head><body>
<header><input id="q" type="search" placeholder="Filter repos" autofocus>
<button id="notify" type="button">Enable notifications</button></header>
<ul id="list"></ul>
<script>
"use strict";
const CODE_PORT = __CODE_PORT__;
let repos = [], waiting = [], known = null;
const list = document.getElementById("list"), q = document.getElementById("q");
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
function row(name, path, waits) {
  const li = el("li");
  li.append(el("span", waits.length ? "dot" : "dot idle"));
  if (path) {
    const a = el("a", "", name);
    a.href = "http://localhost:" + CODE_PORT + "/?folder=" + encodeURIComponent(path);
    a.target = "_blank"; a.rel = "noopener";
    li.append(a);
  } else li.append(el("strong", "", name));
  if (waits.length) li.append(el("span", "who", waits.map(w => w.label).join(", ")));
  if (path) li.append(el("span", "path", path));
  return li;
}
function render() {
  const f = q.value.trim().toLowerCase(), rows = [];
  for (const r of repos) {
    if (f && !r.name.toLowerCase().includes(f) && !r.path.toLowerCase().includes(f)) continue;
    rows.push(row(r.name, r.path, waiting.filter(w => w.path === r.path)));
  }
  const other = waiting.filter(w => w.path === null);
  if (other.length && (!f || "other".includes(f))) rows.push(row("other", "", other));
  list.replaceChildren(...rows);
}
function notifyNew() {
  const ids = new Set(waiting.map(w => w.session));
  if (known && "Notification" in window && Notification.permission === "granted")
    for (const w of waiting) if (!known.has(w.session)) new Notification(w.repo + " is waiting", { body: w.label, tag: w.session });
  known = ids;
}
q.addEventListener("input", render);
document.getElementById("notify").addEventListener("click", () => { if ("Notification" in window) Notification.requestPermission(); });
const es = new EventSource("/api/events");
es.onmessage = ev => { const d = JSON.parse(ev.data); repos = d.repos; waiting = d.attention; notifyNew(); render(); };
</script></body></html>
"""


def _handler(registry: Path, opt_root: Path, state: Path, code_port: int, rows: list[dict]):
    import http.server

    good = {
        "rows": rows
    }  # the last catalog that read cleanly: a registry being rewritten never empties the board
    board = BOARD.replace("__CODE_PORT__", str(code_port)).encode()

    built = {"at": time.monotonic()}
    lock = threading.Lock()

    def current() -> list[dict]:
        with lock:
            if time.monotonic() - built["at"] >= CATALOG_TTL:
                built["at"] = time.monotonic()
                try:
                    good["rows"] = _catalog(registry, opt_root)
                except Exception:  # noqa: BLE001 — keep serving the last good catalog
                    pass
            return good["rows"]

    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "fabrik-deck"
        protocol_version = "HTTP/1.1"
        timeout = 30  # an idle or half-sent request never holds its thread for ever

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002 — the base class's name
            pass  # one line per request would flood the journal; refusals are logged where they happen

        def end_headers(self) -> None:
            # Here, not in _send, so the base class's own error pages (a malformed request line) carry them too.
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "frame-ancestors 'none'")
            super().end_headers()

        def _send(self, code: int, ctype: str, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            if code == 405:
                self.send_header("Allow", "GET")
            self.send_header("Connection", "close")
            self.close_connection = True
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _host_ok(self) -> bool:
            # DNS rebinding: a hostile page reaches this socket under ITS name (quota_dashboard.py:2806-2850).
            port = self.server.server_address[1]  # type: ignore[index]  # an AF_INET (host, port) pair
            hosts = self.headers.get_all("Host") or []
            host = hosts[0].strip().lower() if len(hosts) == 1 else ""
            if host in (f"localhost:{port}", f"127.0.0.1:{port}"):
                return True
            sys.stderr.write(
                f"fabrik_deck: {self.command} refused — Host {host[:80]!r} is not this board\n"
            )
            self._send(421, "text/plain; charset=utf-8", b"misdirected request\n")
            return False

        def _refuse(self) -> None:
            if self._host_ok():
                self._send(405, "text/plain; charset=utf-8", b"method not allowed\n")

        def do_POST(self) -> None:
            self._refuse()

        def do_PUT(self) -> None:
            self._refuse()

        def do_DELETE(self) -> None:
            self._refuse()

        def do_PATCH(self) -> None:
            self._refuse()

        def do_OPTIONS(self) -> None:
            self._refuse()

        def do_HEAD(self) -> None:
            self._refuse()

        def __getattr__(self, name: str):
            # BaseHTTPRequestHandler answers a method with no do_<METHOD> with 501 before any check runs, so every
            # other method (TRACE, CONNECT, a made-up verb) gets the same Host guard and 405.
            if name.startswith("do_"):
                return self._refuse
            raise AttributeError(name)

        def do_GET(self) -> None:
            if not self._host_ok():
                return
            route = self.path.split("?", 1)[0]
            if route == "/":
                self._send(200, "text/html; charset=utf-8", board)
            elif route == "/api/repos":
                self._send(200, "application/json", json.dumps(_public(current())).encode())
            elif route == "/api/attention":
                self._send(
                    200,
                    "application/json",
                    json.dumps(attention(state, current(), time.time())).encode(),
                )
            elif route == "/api/events":
                self._events()
            else:
                self._send(404, "text/plain; charset=utf-8", b"not found\n")

        def _events(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.close_connection = True
            self.end_headers()
            last, sent_at = None, 0.0
            try:
                while True:
                    now = time.time()
                    rows = current()
                    frame = json.dumps(
                        {"repos": _public(rows), "attention": attention(state, rows, now)}
                    )
                    if frame != last or now - sent_at >= 2:
                        self.wfile.write(f"data: {frame}\n\n".encode())
                        self.wfile.flush()
                        last, sent_at = frame, now
                    time.sleep(0.5)
            except (
                OSError,
                ValueError,
            ):  # a gone client: a reset, an abort, a timeout, a closed file
                return

    Handler.current = staticmethod(current)  # type: ignore[attr-defined]
    return Handler


def serve(registry: Path, opt_root: Path) -> None:
    # Every startup failure exits 2, as code_server() does: the unit's RestartPreventExitStatus=2 stops there.
    import http.server

    raw = os.environ.get("FABRIK_DECK_PORT")
    port = _parse_port(raw, DECK_PORT)
    if port is None:
        _die(2, f"FABRIK_DECK_PORT={raw!r} is not a port (1-65535)")
    raw_code = os.environ.get("FABRIK_DECK_CODE_PORT")
    code_port = _parse_port(raw_code)
    if code_port is None:
        _die(2, f"FABRIK_DECK_CODE_PORT={raw_code!r} is not a port (1-65535)")
    try:
        rows = _catalog(registry, opt_root)
    except Exception as exc:  # noqa: BLE001 — an unreadable or malformed registry is a startup failure
        _die(2, f"cannot read the registry {registry}: {type(exc).__name__}: {exc}")
    state = _state_dir(_home(), os.environ)
    handler = _handler(registry, opt_root, state, code_port, rows)
    try:
        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    except OSError as exc:
        _die(2, f"cannot listen on 127.0.0.1:{port}: {exc}")
    print(f"fabrik_deck: serving http://localhost:{port}/ (state {state})", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


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
    srv = sub.add_parser("serve", help="the board on 127.0.0.1:<FABRIK_DECK_PORT, default 8445>")
    srv.add_argument(
        "--registry", type=Path, default=HUB / "data" / "projects.yaml", help="the project registry"
    )
    srv.add_argument(
        "--opt-root", type=Path, default=Path("/opt"), help="the directory scanned for repositories"
    )
    args = ap.parse_args(argv)
    if args.cmd == "code-server":
        code_server()
    elif args.cmd == "serve":
        serve(args.registry, args.opt_root)
    else:
        if shutil.which("systemd-analyze") is None:
            _die(1, "systemd-analyze is not installed")
        install(args.hub.resolve(), args.start)


if __name__ == "__main__":
    main()
