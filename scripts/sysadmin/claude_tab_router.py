#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/claude-tab-router.md | tests/test_claude_tab_router.py
"""claude_tab_router.py — the VS Code chat-tab ROUTER behind claude-agent-wrapper.sh (W-ea993618).

The Claude extension scopes a new chat tab to its window's first folder, so from one window no tab can open another
repo's agent. Every chat runs through `claudeCode.claudeProcessWrapper` (scripts/sysadmin/claude-agent-wrapper.sh,
installed at ~/.claude/bin/claude-agent-wrapper.sh); on a stream-json chat launch that wrapper calls `route`:

  route --cwd <the tab's cwd> -- <the launch argv>   prints <cwd> NUL <CLAUDE_AGENT or ""> NUL <argv...> and exits 0
                                                     when the tab must run elsewhere or as a role; exits 1 with
                                                     nothing printed for a plain launch — cancel, a refused pick, no
                                                     display, any error — and the wrapper launches exactly as today
  entries [--json]                                   the list `route` would show, for a terminal or a test

`route` shows no picker for a launch that already resumes a session: one from the tab's own project directory is the
operator's history pick and launches as today; one whose transcript lives under another project directory is a
restored routed tab, RE-ROOTED silently to that session's own cwd with the role recorded for it. Otherwise it shows a
Tk list (Enter or double-click picks; Esc, closing it, the 30 s deadline or the wrapper's death cancels):
"Plain chat — as today" first, then per repo with known agents:
  a role whose session runs in a live process            listed "live elsewhere (pid N)", REFUSED on pick (one
                                                          process per session id — coordinator ruling 2026-10-21)
  a role not live, with a transcript                     "Resume <role>" — its newest session; the tab runs in the
                                                          cwd whose slug is that transcript's project directory
  a role not live                                        "New session as <role>"
  every repo                                             "New session in <repo>" (no role)
A new session gets `--session-id <uuid4>` and a row in ~/.claude/state/tab-router.jsonl, so its role is found again.
Every pick drops each `--add-dir`: a routed agent gets no access to the window's own folders. A role name that
whoami_agent.py would not bind (`_NAME_RE`) is listed "cannot bind", never offered.

Roles come from each repo's `.fabrik/session-agents.json` (sid -> role), the identity store
(~/.claude/state/agent-identity.jsonl, last row per sid wins, as whoami_agent.py reads it), this router's own map, and
the repo's merge owner (`decisions.py --merge-owner`). Liveness is hibernate.live_sessions; a live process holding the
very sid this tab resumes is this tab reattaching, never "elsewhere".

Fail direction: OPEN, to today's plain launch, on every error — the wrapper sits under every chat tab on the box. A
process that is neither CLAUDE_AGENT-tagged nor bound in the identity store is invisible to the liveness check, so
its role can be offered twice (open on the one-process rule; docs/workstation/claude-tab-router.md says so).
Cobra (D-253): the cheapest way past "the picker works" is a list that hides what it cannot open, so a live role is
always LISTED with its pid, never dropped.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(Path(__file__).resolve().parent.parent))
import hibernate  # noqa: E402  (same directory: live_sessions, merge_owner)
from whoami_agent import _NAME_RE  # noqa: E402  (scripts/: the names an agent can bind)

PLAIN, RESUME, NEW_ROLE, NEW_REPO, LIVE, UNBINDABLE = (
    "plain",
    "resume",
    "new-role",
    "new-repo",
    "live",
    "unbindable",
)
RESUME_FLAGS = {"--resume", "-r"}
CONTINUE_FLAGS = {"--continue", "-c"}
# The extension fails a chat whose process has not initialised within 60 s (extension.js initializeTimeoutMs):
# the picker's ABSOLUTE deadline plus the CLI's own start-up must stay under that; the wrapper's `timeout` sits above.
DEADLINE_SECONDS = 30
MAP_NAME = "tab-router.jsonl"


def slug(path: str) -> str:
    """The CLI's project-directory name for a cwd: every non-alphanumeric character becomes '-'."""
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _jsonl(path: Path) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _transcript(projects: Path, sid: str) -> Path | None:
    hits = [p for p in projects.glob(f"*/{sid}.jsonl") if p.is_file()]
    return max(hits, key=lambda p: p.stat().st_mtime) if hits else None


def session_cwd(transcript: Path) -> str:
    """The cwd a resume of this transcript must run in: the recorded cwd whose slug IS the transcript's project
    directory and which still exists; "" when none qualifies (a moved or removed worktree)."""
    want = transcript.parent.name
    try:
        with transcript.open(encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i > 400:
                    break
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                cwd = rec.get("cwd") if isinstance(rec, dict) else None
                if isinstance(cwd, str) and slug(cwd) == want and os.path.isdir(cwd):
                    return cwd
    except OSError:
        return ""
    return ""


def known_agents(home: Path, opt: str) -> dict[str, dict[str, list[str]]]:
    """repo -> role -> session ids."""
    out: dict[str, dict[str, list[str]]] = {}

    def add(repo: str, role: str, sid: str) -> None:
        sids = out.setdefault(repo, {}).setdefault(role, [])
        if sid and sid not in sids:
            sids.append(sid)

    for f in sorted(Path(opt).glob("*/.fabrik/session-agents.json")):
        data = _read_json(f)
        if isinstance(data, dict):
            for sid, role in data.items():
                if isinstance(sid, str) and isinstance(role, str) and role:
                    add(str(f.parent.parent), role, sid)
    state = home / ".claude" / "state"
    last: dict[str, tuple[str, str]] = {}  # sid -> (name, repo): the LAST row per sid wins
    for rec in _jsonl(state / "agent-identity.jsonl"):
        sid, name, top = rec.get("session_id"), rec.get("name"), rec.get("toplevel")
        if isinstance(sid, str) and isinstance(name, str) and name and isinstance(top, str):
            last[sid] = (name, top[: -len("/.git")] if top.endswith("/.git") else top)
    for rec in _jsonl(state / MAP_NAME):
        sid, role, repo = rec.get("sid"), rec.get("role"), rec.get("repo")
        if isinstance(sid, str) and isinstance(role, str) and role and isinstance(repo, str):
            last[sid] = (role, repo)
    prefix = opt.rstrip("/") + "/"
    for sid, (name, repo) in last.items():
        if repo.startswith(prefix):
            add(repo, name, sid)
    return out


def _projects(home: Path) -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or str(home / ".claude")) / "projects"


def entries(home: Path, proc: Path, opt: str = "/opt", own_sid: str = "") -> list[dict]:
    projects = _projects(home)
    live = [
        s for s in hibernate.live_sessions(home, proc, opt) if not own_sid or s["sid"] != own_sid
    ]
    live_by_sid = {s["sid"]: s for s in live if s["sid"]}
    live_by_agent: dict[str, dict] = {}
    for s in live:
        if s.get("agent"):
            live_by_agent.setdefault(s["agent"], s)
    agents = known_agents(home, opt)
    rows: list[dict] = []
    for repo in sorted(agents):
        roles = dict(agents[repo])
        owner, _why = hibernate.merge_owner(repo)
        if owner:
            roles.setdefault(owner, [])
        name = Path(repo).name
        for role in sorted(roles):
            sids = roles[role]
            if not _NAME_RE.fullmatch(role):
                rows.append(
                    {
                        "kind": UNBINDABLE,
                        "repo": repo,
                        "role": role,
                        "label": f"{role} ({name}) — cannot bind (not a valid agent name)",
                    }
                )
                continue
            hit = next(
                (live_by_sid[s] for s in sids if s in live_by_sid), None
            ) or live_by_agent.get(role)
            if hit is not None:
                rows.append(
                    {
                        "kind": LIVE,
                        "repo": repo,
                        "role": role,
                        "pid": hit["pid"],
                        "label": f"{role} ({name}) — live elsewhere (pid {hit['pid']})",
                    }
                )
                continue
            best = None
            for sid in sids:
                t = _transcript(projects, sid)
                if t is not None and (best is None or t.stat().st_mtime > best[1].stat().st_mtime):
                    best = (sid, t)
            if best is not None:
                cwd = session_cwd(best[1])
                if cwd:
                    when = datetime.fromtimestamp(best[1].stat().st_mtime).strftime("%m-%d %H:%M")
                    rows.append(
                        {
                            "kind": RESUME,
                            "repo": repo,
                            "role": role,
                            "sid": best[0],
                            "cwd": cwd,
                            "label": f"Resume {role} ({name}) — last {when}",
                        }
                    )
            rows.append(
                {
                    "kind": NEW_ROLE,
                    "repo": repo,
                    "role": role,
                    "cwd": repo,
                    "label": f"New session as {role} in {name}",
                }
            )
        rows.append(
            {
                "kind": NEW_REPO,
                "repo": repo,
                "role": "",
                "cwd": repo,
                "label": f"New session in {name}",
            }
        )
    return rows


def resume_sid(argv: list[str]) -> str:
    for i, a in enumerate(argv[1:], start=1):
        name, eq, val = a.partition("=")
        if name in RESUME_FLAGS:
            return (
                val
                if eq
                else (argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("-") else "")
            )
    return ""


def rewrite_args(argv: list[str], pick: dict, new_cwd: str) -> list[str]:
    """argv[0] is the binary; the argv the tab runs for `pick` (PLAIN = unchanged)."""
    if pick["kind"] == PLAIN:
        return list(argv)
    out = [argv[0]] if argv else []
    i = 1
    while i < len(argv):
        a = argv[i]
        name, eq, val = a.partition("=")
        takes_next = i + 1 < len(argv) and not argv[i + 1].startswith("-")
        if name in RESUME_FLAGS:
            i += 1 if eq or not takes_next else 2
            continue
        if name in CONTINUE_FLAGS and not eq:
            i += 1
            continue
        if name == "--session-id":
            i += 1 if eq else 2
            continue
        if name == "--add-dir":  # every one: a routed agent gets none of the window's folders
            i += 1 if eq or not takes_next else 2
            continue
        out.append(a)
        i += 1
    if pick["kind"] == RESUME:
        out.append(f"--resume={pick['sid']}")
    elif pick.get("new_sid"):
        out.append(f"--session-id={pick['new_sid']}")
    return out


def is_chat_launch(argv: list[str]) -> bool:
    for i, a in enumerate(argv):
        if a == "--input-format=stream-json" or (
            a == "--input-format" and i + 1 < len(argv) and argv[i + 1] == "stream-json"
        ):
            return True
    return False


def role_of(home: Path, sid: str) -> str:
    """The role a session runs as: this router's map, else the identity store (last row per sid wins in each)."""
    state = home / ".claude" / "state"
    for store, key, field in (
        (MAP_NAME, "sid", "role"),
        ("agent-identity.jsonl", "session_id", "name"),
    ):
        role = ""
        for rec in _jsonl(state / store):
            if rec.get(key) == sid and isinstance(rec.get(field), str):
                role = rec[field]
        if role and _NAME_RE.fullmatch(role):
            return role
    return ""


def wrapper_alive(pid: int) -> bool:
    """False only when `pid` names no process — 0 (not given) is never dead."""
    if pid <= 0:
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def record(home: Path, sid: str, role: str, repo: str, cwd: str) -> None:
    path = home / ".claude" / "state" / MAP_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"sid": sid, "role": role, "repo": repo, "cwd": cwd, "at": int(time.time())}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def pick_with_tk(rows: list[dict], cwd: str, wrapper_pid: int = 0) -> dict | None:
    """The picker: None on cancel, the deadline, the wrapper's death, a signal or no display."""
    import tkinter as tk

    choices = [{"kind": PLAIN, "label": f"Plain chat in {cwd} — as today"}, *rows]
    try:
        root = tk.Tk()
    except tk.TclError:  # no display: a plain launch
        return None
    root.title("Claude — open which agent in this tab?")
    root.attributes("-topmost", True)
    clock = tk.Label(root, anchor="w")
    clock.pack(fill="x", padx=8, pady=(8, 0))
    box = tk.Listbox(root, width=80, height=min(len(choices), 24), font=("monospace", 10))
    for c in choices:
        box.insert(tk.END, c["label"])
    box.selection_set(0)
    box.pack(padx=8, pady=8)
    result: dict = {}
    deadline = time.monotonic() + DEADLINE_SECONDS

    def close(*_args):
        try:
            root.destroy()
        except tk.TclError:
            pass

    def choose(_event=None):
        sel = box.curselection()
        if sel:
            result["pick"] = choices[sel[0]]
        close()

    def watch():
        left = int(deadline - time.monotonic())
        if left <= 0 or not wrapper_alive(wrapper_pid):
            close()
            return
        clock.config(text=f"Enter to open · Esc for a plain chat · {left} s")
        root.after(500, watch)

    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, close)
    box.bind("<Double-Button-1>", choose)
    root.bind("<Return>", choose)
    root.bind("<Escape>", close)
    root.protocol("WM_DELETE_WINDOW", close)
    watch()
    root.lift()
    root.focus_force()
    root.bell()
    box.focus_set()
    root.mainloop()
    return result.get("pick")


def route(
    cwd: str,
    argv: list[str],
    home: Path,
    proc: Path,
    opt: str,
    chooser=pick_with_tk,
    wrapper_pid: int = 0,
) -> list[str] | None:
    """[cwd, agent, *argv] when the tab must run elsewhere or as a role; None for a plain launch."""
    if len(argv) < 2 or not is_chat_launch(argv):
        return None
    sid = resume_sid(argv)
    if sid:
        t = _transcript(_projects(home), sid)
        if t is None or t.parent.name == slug(cwd):
            return None  # the operator's own history pick (or an unknown sid): launch as today, no picker
        target = session_cwd(t)
        if not target:
            return None
        kept = rewrite_args(argv, {"kind": RESUME, "sid": sid}, target)
        return [target, role_of(home, sid), *kept]
    if chooser is pick_with_tk:
        pick = pick_with_tk(entries(home, proc, opt), cwd, wrapper_pid)
    else:
        pick = chooser(entries(home, proc, opt), cwd)
    if not pick or pick["kind"] in (PLAIN, LIVE, UNBINDABLE):
        return None
    target = pick["cwd"]
    if not os.path.isdir(target):
        return None
    if pick["kind"] in (NEW_ROLE, NEW_REPO):
        pick = {**pick, "new_sid": str(uuid.uuid4())}
        if pick["role"]:
            record(home, pick["new_sid"], pick["role"], pick["repo"], target)
    return [target, pick.get("role", ""), *rewrite_args(argv, pick, target)]


def main(args: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--home", default=os.path.expanduser("~"), help=argparse.SUPPRESS)
    ap.add_argument("--proc", default="/proc", help=argparse.SUPPRESS)
    ap.add_argument("--opt", default="/opt", help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("route")
    r.add_argument("--cwd", required=True)
    r.add_argument("--wrapper-pid", type=int, default=0)
    r.add_argument("argv", nargs=argparse.REMAINDER)
    e = sub.add_parser("entries")
    e.add_argument("--json", action="store_true")
    ns = ap.parse_args(args)
    home, proc = Path(ns.home), Path(ns.proc)
    if ns.cmd == "entries":
        rows = entries(home, proc, ns.opt)
        print(json.dumps(rows, indent=2) if ns.json else "\n".join(r["label"] for r in rows))
        return 0
    argv = ns.argv[1:] if ns.argv[:1] == ["--"] else ns.argv
    try:
        out = route(ns.cwd, argv, home, proc, ns.opt, wrapper_pid=ns.wrapper_pid)
    except Exception:  # noqa: BLE001 — fail OPEN: the wrapper launches exactly as today
        return 1
    if not out:
        return 1
    sys.stdout.write("\0".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
