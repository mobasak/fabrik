#!/usr/bin/env python3
# AFTER-EDIT: docs/reference/hibernate.md | commands/_sources/hibernate.md | tests/test_hibernate.py
"""hibernate.py — the machinery behind /hibernate (W-1e9ae1e5): find every repo's live agents, hand out the pause
text, prove the box is safe to sleep, and tell a woken agent that the box slept.

  targets [--json] [--self SID]   every LIVE agent session grouped by repo, each repo's coordinator (its ledger's merge
                                  owner) and the pool sessions that are never messaged
  brief --role coordinator|agent --words "<the operator's words>"   the pause text to send
  mark --words "…"                start a pause (the only writer of ~/.claude/state/hibernate.json)
  lift                            end the pause without a sleep (the hub, when no resume-wake will come)
  status [--json] [--self SID]    one table: every live agent's worktree clean and pushed, no run `running`;
                                  prints SAFE TO HIBERNATE only when every blocking row is clean
  woke [--self SID]               exit 0 when the box slept (or the hub lifted) after the current pause and this
                                  session has not resumed yet; never writes

A session is LIVE when its record (`~/.claude*/sessions/<pid>.json`, `~/.claude-fleet/*/sessions/<pid>.json`) names a
pid whose /proc stat start time equals the record's `procStart` and whose comm is `claude`. Only an `entrypoint` of
`cli` or `claude-vscode` is an agent; `sdk-cli`/`sdk-ts` sessions are pool workers or review seats (`claude -p`): they
are listed, never messaged, never a coordinator (every record carries kind "interactive", so `kind` cannot tell).
The agent's name comes from CLAUDE_AGENT in its environ, else its newest identity-store binding. Each repo's
coordinator is `decisions.py --merge-owner <repo>` (D-874), never a position. Everything read from another repo is
read-only (`git status`, `git rev-list`, `git branch -r --contains`).

Cobra (D-253): the cheapest way past `status` is a table with nothing in it — so no live session found, or the caller
not among them, is exit 2, never SAFE; and the cheapest way past `woke` is an old wake read as new — so a wake counts
only after the CURRENT mark, and a session already running its work again reads "already resumed".
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

AGENT_ENTRYPOINTS = {"cli", "claude-vscode"}
DECISIONS = Path(__file__).resolve().parent.parent / "decisions.py"
WAKE_GAP_FLOOR_S = 900  # the rotation tick's own resume-wake floor (claude_rotate.py), so a 15-minute lid close counts
NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")


# ── discovery ────────────────────────────────────────────────────────────────────────────────────────────────────


def _session_files(home: Path) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for pattern in (str(home / ".claude*" / "sessions" / "*.json"), str(home / ".claude-fleet" / "*" / "sessions" / "*.json")):
        for f in sorted(glob.glob(pattern)):
            real = os.path.realpath(f)
            if real not in seen:
                seen.add(real)
                out.append(Path(f))
    return out


def _proc_start(proc: Path, pid: int) -> str | None:
    try:
        return (proc / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def _environ_agent(proc: Path, pid: int) -> str | None:
    try:
        for kv in (proc / str(pid) / "environ").read_bytes().split(b"\0"):
            if kv.startswith(b"CLAUDE_AGENT="):
                return kv.split(b"=", 1)[1].decode(errors="replace") or None
    except OSError:
        return None
    return None


def _ppid(proc: Path, pid: int) -> int | None:
    try:
        return int((proc / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()[1])
    except (OSError, IndexError, ValueError):
        return None


def _bindings(store: Path) -> dict[str, str]:
    """session id -> the name on its LAST row (whoami_agent.py's rule)."""
    owner: dict[str, str] = {}
    try:
        lines = store.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return owner
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict) and isinstance(r.get("session_id"), str) and isinstance(r.get("name"), str):
            owner[r["session_id"]] = r["name"]
    return owner


def live_sessions(home: Path, proc: Path) -> list[dict]:
    names = _bindings(home / ".claude" / "state" / "agent-identity.jsonl")
    out = []
    for f in _session_files(home):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            pid = int(d["pid"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if d.get("procStart") is None or str(_proc_start(proc, pid)) != str(d.get("procStart")):
            continue
        try:
            if (proc / str(pid) / "comm").read_text().strip() != "claude":
                continue
        except OSError:
            continue
        sid = d.get("sessionId") or ""
        cwd = d.get("cwd") or ""
        out.append(
            {
                "pid": pid,
                "ppid": _ppid(proc, pid),
                "sid": sid,
                "cwd": cwd,
                "peer": d.get("name") or "",
                "entrypoint": d.get("entrypoint") or "",
                "agent": _environ_agent(proc, pid) or names.get(sid) or "",
                "repo": "/opt/" + cwd[5:].split("/")[0] if cwd.startswith("/opt/") and len(cwd) > 5 else "",
            }
        )
    return out


def merge_owner(repo: str) -> tuple[str, str]:
    """(name, why) — the name is "" when the repo declares none or the lookup fails."""
    if not (Path(repo) / "docs" / "DECISIONS.md").is_file():
        return "", "no ledger"
    try:
        out = subprocess.run(
            [sys.executable, str(DECISIONS), "--merge-owner", repo], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "", f"lookup failed ({exc})"
    if out.returncode == 0:
        return out.stdout.strip(), "the ledger's merge owner"
    if out.returncode == 3:
        return "", "the ledger declares no merge owner"
    return "", f"lookup failed (exit {out.returncode})"


def targets(home: Path, proc: Path, self_sid: str) -> dict:
    sessions = live_sessions(home, proc)
    agents = [s for s in sessions if s["entrypoint"] in AGENT_ENTRYPOINTS]
    pool = [s for s in sessions if s["entrypoint"] not in AGENT_ENTRYPOINTS]
    agent_pids = {s["pid"] for s in agents}
    for p in pool:  # a seat whose parent chain reaches a live agent is that agent's own subagent work
        p["parent_agent"] = ""
        pid, hops = p.get("ppid"), 0
        while pid and hops < 8:
            if pid in agent_pids:
                p["parent_agent"] = next(a["agent"] or a["peer"] for a in agents if a["pid"] == pid)
                break
            pid, hops = _ppid(proc, pid), hops + 1
    repos: dict[str, dict] = {}
    outside = []
    self_repo = ""
    for s in agents:
        if s["sid"] == self_sid:
            self_repo = s["repo"]
            continue
        if not s["repo"]:
            outside.append(s)
            continue
        repos.setdefault(s["repo"], {"repo": s["repo"], "sessions": []})["sessions"].append(s)
    for repo, row in repos.items():
        owner, why = merge_owner(repo)
        holders = [s for s in row["sessions"] if owner and s["agent"] == owner]
        if not owner and len(row["sessions"]) == 1:
            holders, why = row["sessions"], "the repo's only live agent session (no merge owner declared)"
        row["owner"], row["owner_why"] = owner, why
        row["coordinator"] = holders[0] if len(holders) == 1 else None
        if len(holders) > 1:
            row["note"] = f"{len(holders)} live sessions hold {owner} — message each session directly"
        elif not holders and repo == self_repo:
            row["note"] = "this is your own repo — send the agent text to each session directly"
        elif not holders:
            row["note"] = "no live coordinator — message each session directly"
        else:
            row["note"] = ""
        row["others"] = [s for s in row["sessions"] if s not in holders or len(holders) > 1]
    return {"repos": [repos[k] for k in sorted(repos)], "outside": outside, "pool": pool, "self": self_sid}


# ── the pause text ───────────────────────────────────────────────────────────────────────────────────────────────


def brief(role: str, words: str) -> str:
    hub = str(Path(__file__).resolve())
    agent = f"""URGENT — PAUSE NOW for a hibernate. The operator, verbatim: "{words}".
1. Finish the step you are on and stop there; a foreground wait or poll ends now. Let your OWN subagents and review
   seats finish (never stop one mid-write); dispatch nothing new and start no new step.
2. Commit your WIP on your own worktree branch (explicit pathspecs, provenance trailers; "wip(pause): …" is fine) and
   push it. Never commit on a default branch's main checkout what you did not author (leave runtime files untracked).
3. Close every live run record with the operator's words, the first form your command_run.py accepts:
   a. python3 scripts/command_run.py blocked --command <the live run> --paused --reason "operator: {words}"
   b. no --paused in your copy: python3 scripts/command_run.py handoff --command <the run> --reason "operator pause: {words}" --resume <a file with a ## RESUME block>
   c. handoff refused too (a receipt owed): python3 scripts/command_run.py blocked --command <the run> --reason "operator pause (no --paused in this copy): {words}"
4. The wake DROPS your cached prompt: you resume from what is on disk, nothing else. Write your resume point to memory
   (and the run's RESUME note): the item, the files, the seed path the close printed, and the exact next step.
5. Reply ONE line: PAUSED — <item> — branch pushed <sha> — seed <path|none> — next <step>
After the wake: run `python3 {hub} woke` when a wake line arrives (the self-watch may still say "the fleet-quota hold
LIFTED" for a sleep — run it anyway). Exit 0 means the box slept: resume the SAME item from its seed without being
told again (`command_run.py start --command <name> --phases <N> --resume-from <seed>`, the parent run first)."""
    if role == "agent":
        return agent
    return f"""URGENT — HIBERNATE: pause every agent you coordinate, then report. The operator, verbatim: "{words}".
1. Send the AGENT text below, verbatim, to each of your live agents (ListAgents; `python3 {hub} targets` shows
   them by repo). Pool and review-seat sessions (`claude -p`) are never messaged.
2. Do the same steps yourself: finish your step, commit and push what you hold, close your runs (same three forms).
3. Collect each agent's PAUSED line. When all are in (or after 15 minutes), reply to the hub with the lines, one per
   agent, and name any agent that did not answer.

--- the AGENT text ---
{agent}"""


# ── pause marker ─────────────────────────────────────────────────────────────────────────────────────────────────


def _marker(home: Path) -> Path:
    return home / ".claude" / "state" / "hibernate.json"


def _read_marker(home: Path) -> dict:
    try:
        d = json.loads(_marker(home).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_marker(home: Path, data: dict) -> None:
    path = _marker(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".hibernate.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.replace(tmp, path)


def woke(home: Path, self_sid: str) -> tuple[int, str]:
    m = _read_marker(home)
    paused_at = m.get("paused_at")
    if not isinstance(paused_at, (int, float)):
        return 1, "no pause is marked (hibernate.py mark was never run) — nothing to resume from here"
    wake = None
    if isinstance(m.get("lifted_at"), (int, float)) and m["lifted_at"] >= paused_at:
        wake = ("lifted by the hub", m["lifted_at"])
    ledger = home / ".claude" / "state" / "rotate-ledger.jsonl"
    try:
        for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines():
            if "resume-wake" not in line:  # a cheap pre-filter; the field test below decides
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if not isinstance(r, dict) or r.get("event") != "resume-wake":
                continue
            ts, gap = r.get("ts"), r.get("gap_s")
            if (
                isinstance(ts, (int, float))
                and isinstance(gap, (int, float))
                and ts > paused_at
                and gap >= WAKE_GAP_FLOOR_S
                and (wake is None or ts > wake[1])
            ):
                wake = (f"the box slept {int(gap)} s (resume-wake)", ts)
    except OSError:
        pass
    if wake is None:
        return 1, f"no wake since the pause at {time.strftime('%F %T', time.localtime(paused_at))} — stay paused"
    if self_sid:
        try:
            rec = json.loads((home / ".claude" / "state" / "command-runs" / f"{self_sid}.json").read_text("utf-8"))
        except (OSError, ValueError):
            rec = {}
        if rec.get("state") == "running" and float(rec.get("started_epoch") or 0) > wake[1]:
            return 1, "already resumed: your run is running again since the wake"
    return 0, f"RESUME — {wake[0]} at {time.strftime('%F %T', time.localtime(wake[1]))}: resume your item from its seed"


# ── status ───────────────────────────────────────────────────────────────────────────────────────────────────────


def _git(path: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", "-C", path, *args], capture_output=True, text=True, timeout=60, env=env)


def worktree_state(path: str) -> tuple[bool, str]:
    """(blocks, why) for one live agent's worktree."""
    if not Path(path).is_dir():
        return True, "missing"
    st = _git(path, "status", "--porcelain")
    if st.returncode != 0:
        return True, "not a git checkout"
    lines = [ln for ln in st.stdout.splitlines() if ln]
    tracked = [ln for ln in lines if not ln.startswith("??")]
    untracked = len(lines) - len(tracked)
    if tracked:
        return True, f"{len(tracked)} uncommitted change(s)"
    head = _git(path, "symbolic-ref", "-q", "HEAD")
    if head.returncode != 0:
        return True, "detached HEAD"
    up = _git(path, "rev-list", "--count", "@{u}..HEAD")
    if up.returncode == 0:
        ahead = int(up.stdout.strip() or 0)
        if ahead:
            return True, f"{ahead} commit(s) not pushed"
    else:
        on_remote = _git(path, "branch", "-r", "--contains", "HEAD")
        if on_remote.returncode != 0 or not on_remote.stdout.strip():
            return True, "no upstream and HEAD is on no remote branch"
    return False, "clean, pushed" + (f" ({untracked} untracked file(s))" if untracked else "")


def status(home: Path, proc: Path, self_sid: str) -> tuple[int, list[dict]]:
    sessions = [s for s in live_sessions(home, proc) if s["entrypoint"] in AGENT_ENTRYPOINTS]
    if not sessions:
        return 2, [{"error": "no live agent session found — the session records or /proc are not readable from here"}]
    if self_sid and not any(s["sid"] == self_sid for s in sessions):
        return 2, [{"error": f"this session ({self_sid}) is not among the live sessions — wrong records dir or pid namespace"}]
    rows = []
    for s in sessions:
        if s["sid"] == self_sid:
            continue
        blocks, why = worktree_state(s["cwd"])
        try:
            rec = json.loads((home / ".claude" / "state" / "command-runs" / f"{s['sid']}.json").read_text("utf-8"))
        except (OSError, ValueError):
            rec = {}
        if rec.get("state") == "running":
            blocks, why = True, f"run /{rec.get('command', '?')} still running; " + why
        rows.append({"repo": s["repo"] or "outside /opt", "agent": s["agent"] or s["peer"], "cwd": s["cwd"], "blocks": blocks, "why": why})
    rows.sort(key=lambda r: (r["repo"], r["agent"]))
    return (1 if any(r["blocks"] for r in rows) else 0), rows


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--home", default=os.path.expanduser("~"), help=argparse.SUPPRESS)
    ap.add_argument("--proc", default="/proc", help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="verb", required=True)
    for name in ("targets", "status"):
        p = sub.add_parser(name)
        p.add_argument("--json", action="store_true")
        p.add_argument("--self", default=os.environ.get("CLAUDE_CODE_SESSION_ID", ""))
    b = sub.add_parser("brief")
    b.add_argument("--role", choices=("coordinator", "agent"), required=True)
    b.add_argument("--words", required=True)
    mk = sub.add_parser("mark")
    mk.add_argument("--words", required=True)
    sub.add_parser("lift")
    w = sub.add_parser("woke")
    w.add_argument("--self", default=os.environ.get("CLAUDE_CODE_SESSION_ID", ""))
    a = ap.parse_args(argv)
    home, proc = Path(a.home), Path(a.proc)

    if a.verb == "brief":
        print(brief(a.role, a.words))
        return 0
    if a.verb == "mark":
        _write_marker(home, {"paused_at": time.time(), "words": a.words})
        print(f"hibernate: pause marked in {_marker(home)}")
        return 0
    if a.verb == "lift":
        m = _read_marker(home)
        if "paused_at" not in m:
            print("hibernate: no pause is marked — nothing to lift", file=sys.stderr)
            return 1
        m["lifted_at"] = time.time()
        _write_marker(home, m)
        print("hibernate: pause lifted — every paused agent's `woke` now answers RESUME")
        return 0
    if a.verb == "woke":
        rc, msg = woke(home, a.self)
        print(msg)
        return rc
    if a.verb == "targets":
        t = targets(home, proc, a.self)
        if a.json:
            print(json.dumps(t, indent=2))
            return 0
        for r in t["repos"]:
            c = r["coordinator"]
            print(f"{r['repo']}: coordinator {r['owner'] or '-'} ({r['owner_why']})" + (f" → peer {c['peer']}" if c else ""))
            if r["note"]:
                print(f"  ! {r['note']}")
            for s in r["others"]:
                print(f"  - {s['agent'] or '(unnamed)'} → peer {s['peer']}  [{s['cwd']}]")
        for s in t["outside"]:
            print(f"outside /opt: {s['agent'] or '(unnamed)'} → peer {s['peer']}  [{s['cwd']}] — send the agent text directly")
        if t["pool"]:
            seats = sum(1 for p in t["pool"] if p.get("parent_agent"))
            print(f"pool: {len(t['pool'])} headless session(s), never messaged ({seats} are a live agent's own seats)")
        return 0
    rc, rows = status(home, proc, a.self)
    if a.json:
        print(json.dumps({"rc": rc, "rows": rows}, indent=2))
        return rc
    if rc == 2:
        print(f"hibernate: NOT SAFE — {rows[0]['error']}", file=sys.stderr)
        return 2
    for r in rows:
        print(f"{'BLOCKS' if r['blocks'] else 'ok    '}  {r['repo']:28} {r['agent']:24} {r['why']}  [{r['cwd']}]")
    print("SAFE TO HIBERNATE" if rc == 0 else f"NOT SAFE — {sum(r['blocks'] for r in rows)} row(s) block")
    return rc


if __name__ == "__main__":
    sys.exit(main())
