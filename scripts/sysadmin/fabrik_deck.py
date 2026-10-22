#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/fabrik-deck.md | tests/test_fabrik_deck.py | docs/workstation/hooks-index.md | scripts/sysadmin/install_user_hooks.py
"""fabrik_deck.py code-server | serve | hook | install | profile | launcher | up — the Fabrik Deck on this box.

The Deck (docs/superpowers/specs/2026-10-21-fabrik-deck-design.md, D-1106) shows every repo as a code-server workbench
in a Vivaldi tab, with a board that says which repo's agent waits on the operator. Two systemd user units run it,
`fabrik-deck-code.service` (code-server) and `fabrik-deck.service` (the board); they start at boot (linger on) and
restart on a crash, because a hand-started code-server died with the 2026-10-21 WSL restart (W-e89a9b5b).

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

profile — merge PROFILE into code-server's settings.json after copying it to …/User/backups/; a file that is not a
plain JSON object (code-server also accepts comments) is left alone, exit 1.

launcher --desktop DIR — write "Fabrik Deck.bat" there: it runs `up` in WSL, waits up to 30 s for the board to answer
from Windows, then the first time opens the board (and records that in a marker file beside the .bat); afterwards it
starts the browser only when it is not running, with no URL, so the browser's session restore brings the tabs back. A
.bat whose second line is not our marker is never overwritten (exit 2); a hub, distro or browser value cmd would split
is refused (the browser must be a Windows path to an .exe).

up — the .bat's WSL leg: export XDG_RUNTIME_DIR when the user bus is there (a .bat carries none; with no bus it says
so, starts nothing and exits 1), start each unit that is not active and whose port is free (a held port is named on
stderr and that unit left stopped), print the board port — none when another process holds it, so the .bat never
opens a foreign page.

install — the session-archive installer's steps (scripts/sysadmin/install_session_archive_timer.sh), for both units.
Every check runs before the first write, so a refusal (exit 1) leaves every file as it was: linger must be on; `--hub`
is an absolute path of letters, digits and / . _ - (ExecStart and the .bat would split or expand anything else); the
ExecStart target and the
code-server binary must exist (`systemd-analyze verify` cannot see either); a unit file without our marker is never
overwritten; each rendered unit must pass `systemd-analyze --user verify` printing nothing (a misplaced key is only a
warning at rc 0); both ports in the env file must parse and differ; the env file and settings.json must read (an
empty settings.json is no settings); the backups of config.yaml and settings.json are taken (a file that already
holds the Deck's values is neither backed up nor rewritten); with `--desktop`, the .bat must be ours or absent; with `--start`, nothing may listen on the port of a unit that is not active (that unit would
fail to bind; an active unit holds its own port). Then the env file ~/.config/fabrik-deck/env is created, or on a
present one every line is kept and only missing keys are appended (named on stderr), so an operator's override wins;
config.yaml is backed up and its bind-addr, auth and cert lines set (others, such as a password line, kept; mode 0600
for a new file); the profile is applied; the units are written; files go temp-then-rename, keeping an existing file's
mode; then daemon-reload, enable, and with `--start` start — a failing `systemctl` exits 1 with the files already
written; then, with `--desktop`, the .bat. The default only enables: the cutover from a hand start kills the claude
processes in the open Deck tabs, so it is run deliberately. A unit restarts its crashed process every 10 s with no
limit (StartLimitIntervalSec=0), but a startup failure exits 2 and RestartPreventExitStatus=2 stops it there.

`--hub` (default /opt/fabrik, the main checkout) is where the units run this script from; after changing it, run
`systemctl --user restart fabrik-deck-code fabrik-deck` — a running unit keeps the old path until it restarts.

COBRA (D-253): the cheapest way to pass the tests is a unit that verifies and enables and never serves, and a .bat
that no Windows shell ever ran — no test starts systemd or cmd. The counter is the live proof: after `wsl --shutdown`,
Windows reaches the Deck's port without anyone starting anything (docs/workstation/fabrik-deck.md § Proof), and the
operator's § Acceptance run double-clicks the .bat itself.
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
DECK_UNIT_NAME = "fabrik-deck.service"
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
        ("FABRIK_DECK_PORT", str(DECK_PORT)),
        # absolute: systemd's EnvironmentFile= does not expand `~`, and the hook resolves this same value
        ("FABRIK_DECK_STATE", f"{home}/.local/state/fabrik-deck"),
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


def _atomic_write(path: Path, text: str, new_mode: int = 0o644) -> None:
    """Write via a temp file and rename; an existing file keeps its permission bits (the env file may be 0600), a new
    one gets `new_mode`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else new_mode
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
        if not math.isfinite(at) or now - at > ATTENTION_TTL or at - now > 3600:
            # stale, or a time no clock wrote: NaN would make the board's JSON invalid, and a time more than an
            # hour ahead would never expire
            try:
                f.unlink(missing_ok=True)
            except OSError:
                pass
            continue
        sid = f.stem
        cwd = str(rec.get("cwd") or "/")
        # Catalog paths are resolved, so the cwd is matched as written (normalised) and resolved: a repo reached
        # through a symlink still maps, and `..` never leaves a lexical match behind.
        forms = {os.path.normpath(cwd)}
        if os.path.isabs(cwd):  # a relative cwd would resolve against the server's own directory
            try:
                forms.add(os.path.realpath(cwd))
            except (OSError, ValueError):
                pass
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


def _render_unit(hub: Path, env_file: Path, subcommand: str, description: str) -> str:
    return (
        f"{MARKER}\n"
        "# The Fabrik Deck (docs/workstation/fabrik-deck.md, D-1106).\n"
        "[Unit]\n"
        f"Description={description}\n"
        "StartLimitIntervalSec=0\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"EnvironmentFile={env_file}\n"
        f"ExecStart=/usr/bin/python3 {hub}/scripts/sysadmin/fabrik_deck.py {subcommand}\n"
        "Restart=always\n"
        "RestartSec=10\n"
        "RestartPreventExitStatus=2\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


# (unit, its subcommand, its description, the env key of its port, that port's default)
UNITS = (
    (
        UNIT_NAME,
        "code-server",
        "Fabrik Deck code-server (127.0.0.1, auth none)",
        "FABRIK_DECK_CODE_PORT",
        DEFAULT_PORT,
    ),
    (DECK_UNIT_NAME, "serve", "Fabrik Deck board (127.0.0.1)", "FABRIK_DECK_PORT", DECK_PORT),
)


def _systemctl(*args: str) -> None:
    r = subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True)
    if r.returncode != 0:
        _die(1, f"systemctl --user {' '.join(args)} failed (rc {r.returncode}): {r.stderr.strip()}")


def _active(unit: str) -> bool:
    return (
        subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet", unit], capture_output=True
        ).returncode
        == 0
    )


def _listening(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _ports(env: dict[str, str], where: str, code: int) -> dict[str, int]:
    """Each unit's port from the env file's text, parsed before anything is written."""
    out = {}
    for unit, _, _, key, default in UNITS:
        port = _parse_port(env.get(key), default)
        if port is None:
            _die(code, f"{where}: {key}={env.get(key)!r} is not a port (1-65535)")
        out[unit] = port
    if len(set(out.values())) < len(out):
        _die(
            code,
            f"{where}: FABRIK_DECK_PORT and FABRIK_DECK_CODE_PORT are both {port}; the second unit could not bind",
        )
    return out


def _hub_check(hub: Path, code: int) -> None:
    """The hub path reaches a unit's ExecStart (systemd splits on spaces, expands % and $) and the .bat's `for /f`
    line (cmd splits on & | < > ^ ( ) and expands %), unquoted in both; only plain path characters pass."""
    if not re.fullmatch(r"/[A-Za-z0-9/._-]*", str(hub)):
        _die(
            code, f"--hub {str(hub)!r} must be an absolute path of letters, digits and / . _ - only"
        )


def _settings_path(home: Path) -> Path:
    return home / ".local" / "share" / "code-server" / "User" / "settings.json"


def _backups(home: Path) -> Path:
    return home / ".local" / "share" / "code-server" / "User" / "backups"


def _config_yaml_path(home: Path) -> Path:
    return home / ".config" / "code-server" / "config.yaml"


PROFILE = {
    "workbench.colorTheme": "Dark 2026",
    "window.autoDetectColorScheme": False,
    "claudeCode.preferredLocation": "panel",
    "editor.minimap.enabled": False,
    "breadcrumbs.enabled": False,
    "workbench.startupEditor": "none",
    "workbench.activityBar.location": "top",
    "workbench.statusBar.visible": True,
    "workbench.editor.showTabs": "single",
}


def _read_settings(path: Path) -> dict | None:
    """The settings as a dict, None when the file is absent; exit 1 when it is not a JSON object (code-server accepts
    JSONC — comments, trailing commas — which json cannot round-trip, so such a file is left for the operator)."""
    if not path.exists():
        return None
    try:
        text = path.read_text()
        data = (
            json.loads(text) if text.strip() else {}
        )  # code-server treats an empty file as no settings
    except (OSError, ValueError) as exc:
        _die(1, f"{path} is not plain JSON ({type(exc).__name__}: {exc}); left untouched")
    if not isinstance(data, dict):
        _die(1, f"{path} is not a JSON object; left untouched")
    return data


def _backup(path: Path, backups: Path) -> None:
    """Copy `path` to <backups>/<name>.<timestamp>[-n], keeping its mode; nothing when it does not exist."""
    if not path.exists():
        return
    backups.mkdir(parents=True, exist_ok=True)
    stem = f"{path.name}.{time.strftime('%Y%m%d-%H%M%S')}"
    dest, n = backups / stem, 1
    while dest.exists():
        dest, n = backups / f"{stem}-{n}", n + 1
    shutil.copy2(path, dest)


def _profile_text(current: dict | None) -> str | None:
    """The new settings.json text, or None when the file already holds every Deck value (no backup, no rewrite)."""
    if current is not None and all(k in current and current[k] == v for k, v in PROFILE.items()):
        return None
    return json.dumps({**(current or {}), **PROFILE}, indent=4, ensure_ascii=False) + "\n"


def _backup_or_die(path: Path, backups: Path) -> None:
    try:
        _backup(path, backups)
    except OSError as exc:
        _die(1, f"cannot back up {path} to {backups}: {exc}")


def profile() -> None:
    home = _home()
    path = _settings_path(home)
    text = _profile_text(_read_settings(path))
    if text is not None:
        _backup_or_die(path, _backups(home))
        _atomic_write(path, text)
    print(f"fabrik_deck: {path}: the Deck profile is applied")


def _config_yaml_text(old: str, code_port: int) -> str:
    """config.yaml as `key: value` lines (code-server writes three): ours replaced in place, missing ones appended,
    every other line — a `password:` line, a comment — kept as it is."""
    want = {"bind-addr": f"127.0.0.1:{code_port}", "auth": "none", "cert": "false"}
    lines, seen = [], set()
    for line in old.splitlines():
        # a top-level key only: an indented `auth:` belongs to some other map and stays where it is
        key = (
            line.split(":", 1)[0].rstrip().strip("\"'")
            if ":" in line and line[:1] not in ("", " ", "\t", "#")
            else ""
        )
        if key in want:
            if key not in seen:
                lines.append(f"{key}: {want[key]}")
                seen.add(key)
            continue
        lines.append(line)
    lines += [f"{k}: {v}" for k, v in want.items() if k not in seen]
    return "\n".join(lines) + "\n"


BAT_MARKER = "rem generated by /opt/fabrik/scripts/sysadmin/fabrik_deck.py launcher"
BAT_NAME = "Fabrik Deck.bat"
FIRST_RUN = "Fabrik Deck.first-run"
VIVALDI = r"C:\Users\user\AppData\Local\Vivaldi\Application\vivaldi.exe"


def _bat_text(hub: Path, distro: str, browser: str) -> str:
    image = browser.replace("/", "\\").rsplit("\\", 1)[-1]
    up = f"wsl.exe --distribution {distro} --exec /usr/bin/python3 {hub}/scripts/sysadmin/fabrik_deck.py up"
    lines = [
        "@echo off",
        BAT_MARKER,
        "setlocal",
        "set PORT=",
        f"for /f %%p in ('{up}') do set PORT=%%p",
        'if "%PORT%"=="" (echo Fabrik Deck: WSL did not answer with the board port. & pause & exit /b 1)',
        "set TRIES=0",
        ":wait",
        'curl.exe -s -m 2 -o NUL -w "%%{http_code}" http://localhost:%PORT%/ | findstr 200 >NUL && goto ready',
        "set /a TRIES+=1",
        "if %TRIES% GEQ 30 (echo Fabrik Deck: http://localhost:%PORT%/ did not answer within 30 s. & pause & exit /b 1)",
        "timeout /t 1 /nobreak >NUL",
        "goto wait",
        ":ready",
        f'if not exist "%~dp0{FIRST_RUN}" (',
        f'  start "" "{browser}" http://localhost:%PORT%/',
        f'  echo opened> "%~dp0{FIRST_RUN}"',
        "  exit /b 0",
        ")",
        f'tasklist /FI "IMAGENAME eq {image}" /NH | find /I "{image}" >NUL && exit /b 0',
        f'start "" "{browser}"',
    ]
    return "\r\n".join(lines) + "\r\n"


def _bat_check(desktop: Path, distro: str, browser: str, code: int) -> Path:
    """Refuse (exit `code`) a value cmd would split or expand, or a .bat this script did not write; the target."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", distro or ""):
        _die(code, f"--distro {distro!r} is not a WSL distro name ([A-Za-z0-9][A-Za-z0-9._-]*)")
    if not (
        browser.isascii() and re.fullmatch(r"[A-Za-z]:\\[^\"%&|<>^\r\n/]*\.[Ee][Xx][Ee]", browser)
    ):
        _die(
            code,
            f"--browser {browser!r} must be a Windows path to an .exe with no character cmd would split",
        )
    if not desktop.is_dir():
        _die(code, f"--desktop {desktop} is not a directory")
    target = desktop / BAT_NAME
    if target.exists() or target.is_symlink():
        try:
            lines = target.read_bytes().split(b"\r\n")
        except OSError as exc:
            _die(code, f"{target} cannot be read ({exc}); left untouched")
        if not (len(lines) > 1 and lines[1] == BAT_MARKER.encode("ascii")):
            _die(code, f"{target} exists and was not written by this script; left untouched")
    return target


def _write_bat(target: Path, text: str) -> None:
    data = text.encode("ascii")
    tmp = target.with_name(target.name + ".tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, target)
    except OSError:
        tmp.unlink(missing_ok=True)  # a locked target never leaves a stray .tmp on the desktop
        raise
    print(f"fabrik_deck: wrote {target}")


def launcher(desktop: Path, distro: str, browser: str, hub: Path) -> None:
    _hub_check(hub, 2)
    target = _bat_check(desktop, distro, browser, 2)
    _write_bat(target, _bat_text(hub, distro, browser))


def up(runtime_dir: Path) -> None:
    """The .bat's WSL leg: start each unit that is not active and whose port is free, then print the board's port."""
    bus_dir = runtime_dir / str(os.getuid())
    if not os.environ.get("XDG_RUNTIME_DIR") and (bus_dir / "bus").is_socket():
        # a launch from a .bat carries none, and systemctl --user then finds no bus (agents_up.sh:289-293)
        os.environ["XDG_RUNTIME_DIR"] = str(bus_dir)
    env_file = _env_path(_home())
    try:
        env = _read_env(env_file.read_text(errors="replace"))
    except OSError:
        env = {}
    ports = _ports(env, str(env_file), 1)
    if not os.environ.get("XDG_RUNTIME_DIR"):
        # without a bus every systemctl call fails, and a running unit would read as stopped with its port "held"
        print(f"fabrik_deck: no user bus at {bus_dir}/bus; started nothing", file=sys.stderr)
        print(ports[DECK_UNIT_NAME])
        sys.exit(1)
    rc = 0
    for unit, *_ in UNITS:
        try:
            active = _active(unit)
        except (
            OSError
        ) as exc:  # no systemctl at all: say so, and still print the port the .bat waits on
            print(f"fabrik_deck: cannot run systemctl: {exc}", file=sys.stderr)
            rc = 1
            break
        if active:
            continue
        if _listening(ports[unit]):
            print(
                f"fabrik_deck: {unit} left stopped: 127.0.0.1:{ports[unit]} is held by another process",
                file=sys.stderr,
            )
            if unit == DECK_UNIT_NAME:
                # no port on stdout: the .bat would otherwise open whatever page holds the board's port
                sys.exit(1)
            continue
        r = subprocess.run(["systemctl", "--user", "start", unit], capture_output=True, text=True)
        if r.returncode != 0:
            print(
                f"fabrik_deck: systemctl --user start {unit} failed: {r.stderr.strip()}",
                file=sys.stderr,
            )
            rc = 1
    print(ports[DECK_UNIT_NAME])
    sys.exit(rc)


def install(hub: Path, start: bool, desktop: Path | None, distro: str, browser: str) -> None:
    user = pwd.getpwuid(os.getuid()).pw_name
    home = _home()

    linger = subprocess.run(
        ["loginctl", "show-user", user, "-p", "Linger"], capture_output=True, text=True
    )
    if linger.stdout.strip() != "Linger=yes":
        _die(
            1,
            f"linger is off for {user} ({linger.stdout.strip() or 'no answer'}); enable it once with: "
            f"loginctl enable-linger {user}",
        )
    _hub_check(hub, 1)
    target = hub / "scripts" / "sysadmin" / "fabrik_deck.py"
    binary = home / ".local" / "bin" / "code-server"
    for path in (target, binary):
        if not path.is_file():
            _die(1, f"{path} does not exist — the unit would fail at every start")

    env_file = _env_path(home)
    unit_dir = home / ".config" / "systemd" / "user"
    texts = {}
    for unit, sub, description, _, _ in UNITS:
        unit_path = unit_dir / unit
        if unit_path.exists() and not unit_path.read_text(errors="replace").startswith(MARKER):
            _die(1, f"{unit_path} exists and was not written by this script — move it aside first")
        texts[unit] = _render_unit(hub, env_file, sub, description)
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / unit
            probe.write_text(texts[unit])
            v = subprocess.run(
                ["systemd-analyze", "--user", "verify", str(probe)], capture_output=True, text=True
            )
        if v.returncode != 0 or v.stderr.strip() or v.stdout.strip():
            _die(
                1,
                f"systemd-analyze --user verify rejected {unit}: {(v.stderr or v.stdout).strip()}",
            )

    # Every check above and here runs before the first write, so a refusal leaves every file as it was.
    try:
        existing = env_file.read_text() if env_file.exists() else ""
    except (OSError, ValueError) as exc:
        _die(1, f"cannot read {env_file} as UTF-8 text: {exc}")
    present = _read_env(existing, warn=True)
    missing = [(k, v_) for k, v_ in _env_defaults(home) if k not in present]
    sep = "" if not existing or existing.endswith("\n") else "\n"
    merged = existing + (sep + "".join(f"{k}={v_}\n" for k, v_ in missing) if missing else "")
    ports = _ports(_read_env(merged), str(env_file), 1)
    settings = _read_settings(_settings_path(home))
    config_yaml = _config_yaml_path(home)
    try:
        old_config = config_yaml.read_text() if config_yaml.exists() else ""
    except (OSError, ValueError) as exc:
        _die(1, f"cannot read {config_yaml}: {exc}")
    bat = _bat_check(desktop, distro, browser, 1) if desktop is not None else None
    if start:
        for unit, *_ in UNITS:
            if not _active(unit) and _listening(ports[unit]):
                _die(
                    1,
                    f"127.0.0.1:{ports[unit]} is already in use — stop the process holding it, then re-run with --start",
                )

    new_config = _config_yaml_text(old_config, ports[UNIT_NAME])
    settings_text = _profile_text(settings)
    # the backups go first: a backup that fails stops the run before any file is written
    if new_config != old_config:
        _backup_or_die(config_yaml, _backups(home))
    if settings_text is not None:
        _backup_or_die(_settings_path(home), _backups(home))

    if missing:
        if existing:
            print(
                f"fabrik_deck: {env_file}: appending missing keys {', '.join(k for k, _ in missing)}",
                file=sys.stderr,
            )
        _atomic_write(env_file, merged)
    if new_config != old_config:
        _atomic_write(config_yaml, new_config, new_mode=0o600)
    if settings_text is not None:
        _atomic_write(_settings_path(home), settings_text)
    for unit, *_ in UNITS:
        _atomic_write(unit_dir / unit, texts[unit])
    _systemctl("daemon-reload")
    _systemctl("enable", *(u for u, *_ in UNITS))
    if start:
        _systemctl("start", *(u for u, *_ in UNITS))
    if bat is not None:
        _write_bat(bat, _bat_text(hub, distro, browser))
    for unit, *_ in UNITS:
        r = subprocess.run(
            ["systemctl", "--user", "is-enabled", unit], capture_output=True, text=True
        )
        print(f"{unit}: {r.stdout.strip() or r.stderr.strip()}")


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

    def bat_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--distro",
            default=os.environ.get("WSL_DISTRO_NAME", ""),
            help="the WSL distro the .bat starts",
        )
        p.add_argument("--browser", default=VIVALDI, help="the Windows browser the .bat opens")

    ins = sub.add_parser(
        "install", help="install and enable fabrik-deck-code.service and fabrik-deck.service"
    )
    ins.add_argument(
        "--hub",
        type=Path,
        default=Path("/opt/fabrik"),
        help="checkout the units run this script from",
    )
    ins.add_argument(
        "--start",
        action="store_true",
        help="also start them (refused while a stopped unit's port is in use)",
    )
    ins.add_argument("--desktop", type=Path, help="also write the launcher .bat there")
    bat_flags(ins)
    sub.add_parser("hook", help="the attention hook (stdin: the hook event JSON); always exits 0")
    srv = sub.add_parser("serve", help="the board on 127.0.0.1:<FABRIK_DECK_PORT, default 8445>")
    srv.add_argument(
        "--registry", type=Path, default=HUB / "data" / "projects.yaml", help="the project registry"
    )
    srv.add_argument(
        "--opt-root", type=Path, default=Path("/opt"), help="the directory scanned for repositories"
    )
    sub.add_parser(
        "profile", help="merge the Deck's settings into code-server's settings.json, after a backup"
    )
    lau = sub.add_parser("launcher", help=f"write {BAT_NAME!r} on the Windows desktop")
    lau.add_argument(
        "--desktop", type=Path, required=True, help="the Windows desktop, as a WSL path"
    )
    lau.add_argument(
        "--hub",
        type=Path,
        default=Path("/opt/fabrik"),
        help="checkout the .bat runs this script from",
    )
    bat_flags(lau)
    upp = sub.add_parser(
        "up", help="start the stopped units whose port is free; print the board's port"
    )
    upp.add_argument(
        "--runtime-dir", type=Path, default=Path("/run/user"), help="where the user bus lives"
    )
    args = ap.parse_args(argv)
    if args.cmd == "code-server":
        code_server()
    elif args.cmd == "serve":
        serve(args.registry, args.opt_root)
    elif args.cmd == "profile":
        profile()
    elif args.cmd == "launcher":
        launcher(args.desktop, args.distro, args.browser, args.hub)
    elif args.cmd == "up":
        up(args.runtime_dir)
    else:
        if shutil.which("systemd-analyze") is None:
            _die(1, "systemd-analyze is not installed")
        install(args.hub.resolve(), args.start, args.desktop, args.distro, args.browser)


if __name__ == "__main__":
    main()
