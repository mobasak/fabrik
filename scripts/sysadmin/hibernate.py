#!/usr/bin/env python3
# AFTER-EDIT: docs/reference/hibernate.md | commands/_sources/hibernate.md | tests/test_hibernate.py
"""hibernate.py — the machinery behind /hibernate (W-1e9ae1e5): find every repo's live agents, hand out the pause
text, prove the box is safe to sleep, and tell a woken agent that the box slept.

  targets [--json] [--self SID]   every LIVE agent session grouped by repo, each repo's coordinator (its ledger's merge
                                  owner) and the pool sessions that are never messaged
  brief --role coordinator|agent --words "<the operator's words>"   the pause text to send
  mark --words "…"                start a pause (the only writer of ~/.claude/state/hibernate.json)
  lift                            the hub, once awake: every paused agent's `woke` answers RESUME (adds lifted_at),
                                  then prints rotation offers for the agents past the line (rotate_session `due`)
  status [--json] [--self SID]    one table: every live agent's worktree clean and pushed, no run `running` (the
                                  caller's own run excepted); SAFE TO HIBERNATE only when no row blocks
  woke [--self SID]               exit 0 when the box slept (or the hub lifted) after the current pause and this
                                  session has not resumed yet; never writes

A session is LIVE when its record (`~/.claude*/sessions/<pid>.json`, `~/.claude-fleet/*/sessions/<pid>.json`) names a
pid whose /proc stat start time equals the record's `procStart` and whose comm is `claude`. An `entrypoint` of
`sdk-*` (`sdk-cli`, `sdk-ts`, `sdk-py`) is a pool worker or review seat (`claude -p`): listed, never messaged, never a coordinator, never a
`status` row; every other entrypoint, an unknown or missing one included, is an agent (every record carries kind
"interactive", so `kind` cannot tell).
The agent's name comes from CLAUDE_AGENT in its environ, else its newest identity-store binding. Each repo's
coordinator is `decisions.py --merge-owner <repo>` (D-874), never a position. Everything read from another repo is
read-only (`git status`, `git rev-list`, `git branch -r --contains`).

Cobra (D-253): the cheapest way past `status` is a table with nothing in it — so no live session found, or the caller
not among them, is exit 2, never SAFE; and the cheapest way past `woke` is an old wake read as new — so a wake counts
only after the CURRENT mark, and a session already running its work again reads "already resumed".
"""

from __future__ import annotations

import argparse
import contextlib
import glob
import hashlib
import importlib.util
import json
import math
import os
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# The pool is every Agent SDK entrypoint (`sdk-cli`, `sdk-ts`, `sdk-py`, ...); any other entrypoint, an unknown or a
# missing one included, is an agent (fail closed).
POOL_PREFIX = "sdk-"
DECISIONS = Path(__file__).resolve().parent.parent / "decisions.py"
# exit 3 of `decisions.py --merge-owner`: no MERGE OWNER row, or a winning un-adoption row
DECLARES_NONE = "the ledger declares no merge owner"
NO_OWNER = {"no ledger", DECLARES_NONE}  # a FAILED lookup is not "no owner"


# ── discovery ────────────────────────────────────────────────────────────────────────────────────────────────────


def _session_files(home: Path) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for pattern in (
        str(home / ".claude*" / "sessions" / "*.json"),
        str(home / ".claude-fleet" / "*" / "sessions" / "*.json"),
    ):
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
        if (
            isinstance(r, dict)
            and isinstance(r.get("session_id"), str)
            and isinstance(r.get("name"), str)
        ):
            owner[r["session_id"]] = r["name"]
    return owner


def _repo_of(cwd: str, opt: str) -> str:
    """`<opt>/<repo>` for a cwd under it, else "" (an empty first segment — `/opt//x` — is not a repo)."""
    prefix = opt.rstrip("/") + "/"
    if not cwd.startswith(prefix):
        return ""
    first = cwd[len(prefix) :].split("/")[0]
    return prefix + first if first else ""


def live_sessions(home: Path, proc: Path, opt: str = "/opt") -> list[dict]:
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
        sid = d["sessionId"] if isinstance(d.get("sessionId"), str) else ""
        cwd = d["cwd"] if isinstance(d.get("cwd"), str) else ""
        out.append(
            {
                "pid": pid,
                "ppid": _ppid(proc, pid),
                "sid": sid,
                "cwd": cwd,
                "peer": d.get("name") or "",
                "entrypoint": str(d.get("entrypoint") or ""),
                "agent": _environ_agent(proc, pid) or names.get(sid) or "",
                "repo": _repo_of(cwd, opt),
            }
        )
    return out


def merge_owner(repo: str, *, timeout: float = 30) -> tuple[str, str]:
    """(name, why) — the name is "" when the repo declares none or the lookup fails (incl. past `timeout` s)."""
    if not (Path(repo) / "docs" / "DECISIONS.md").is_file():
        return "", "no ledger"
    try:
        out = subprocess.run(
            [sys.executable, str(DECISIONS), "--merge-owner", repo],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "", f"lookup failed ({exc})"
    if out.returncode == 0:
        return out.stdout.strip(), "the ledger's merge owner"
    if out.returncode == 3:
        return "", DECLARES_NONE
    return "", f"lookup failed (exit {out.returncode})"


def _is_pool(s: dict) -> bool:
    return s["entrypoint"].startswith(POOL_PREFIX)


def targets(home: Path, proc: Path, self_sid: str, opt: str = "/opt") -> dict:
    sessions = live_sessions(home, proc, opt)
    agents = [s for s in sessions if not _is_pool(s)]
    pool = [s for s in sessions if _is_pool(s)]
    agent_pids = {s["pid"] for s in agents}
    # a seat whose parent chain reaches a live agent is that agent's own subagent work
    for p in pool:
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
        if repo == self_repo:  # the caller coordinates its own repo; nobody else there relays
            holders = []
        elif not owner and why in NO_OWNER and len(row["sessions"]) == 1:
            holders, why = (
                row["sessions"],
                "the repo's only live agent session (no merge owner declared)",
            )
        row["owner"], row["owner_why"] = owner, why
        row["coordinator"] = holders[0] if len(holders) == 1 else None
        if len(holders) > 1:
            row["note"] = (
                f"{len(holders)} live sessions hold {owner} — message each session directly"
            )
        elif repo == self_repo:
            row["note"] = "this is your own repo — send the agent text to each session directly"
        elif not holders:
            row["note"] = "no live coordinator — message each session directly"
        else:
            row["note"] = ""
        row["others"] = [s for s in row["sessions"] if s not in holders or len(holders) > 1]
    return {
        "repos": [repos[k] for k in sorted(repos)],
        "outside": outside,
        "pool": pool,
        "self": self_sid,
    }


# ── the pause text ───────────────────────────────────────────────────────────────────────────────────────────────


FEEDBACK = "confusion: none · waste: none · change: none · filed: none — surfaces exercised: paused for a hibernate"


def brief(role: str, words: str) -> str:
    hub = str(Path(__file__).resolve())
    fb = f'--feedback "{FEEDBACK}"'
    agent = f"""URGENT — PAUSE NOW for a hibernate. The operator, verbatim: "{words}".
1. Finish the step you are on and stop there; a foreground wait or poll ends now. Let your OWN subagents and review
   seats finish (never stop one mid-write); dispatch nothing new and start no new step.
2. Commit your WIP on your own worktree branch (explicit pathspecs, provenance trailers; "wip(pause): …" is fine) and
   push it. Never commit on a default branch's main checkout what you did not author (leave runtime files untracked).
3. Close every live run record with the operator's words, the first form your command_run.py accepts (each needs the
   four-field feedback; write your own verdicts, or keep the `none` ones):
   a. python3 scripts/command_run.py blocked --command <the live run> --paused --reason {shlex.quote("operator: " + words)} {fb}
   b. no --paused in your copy: python3 scripts/command_run.py handoff --command <the run> --reason {shlex.quote("operator pause: " + words)} --resume <a file with a ## RESUME block> {fb}
   c. handoff refused too (a receipt owed): python3 scripts/command_run.py blocked --command <the run> --reason {shlex.quote("operator pause (no --paused in this copy): " + words)} {fb}
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
   Then reply to the hub — never close the hub's /hibernate run, which is the hub's own.
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
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _safe_sid(sid: str) -> str:
    """command_run.py's record filename for a session id — a copy, pinned to it by tests/test_hibernate.py."""
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in sid)
    if not safe:
        return "nosession"
    if safe != sid:
        safe += "-" + hashlib.blake2s(sid.encode("utf-8", "replace"), digest_size=4).hexdigest()
    return safe


def _run_record(home: Path, sid: str) -> dict | None:
    """The session's run record: {} when it has none, None when one exists but is not a readable JSON object. Callers
    never pass an empty id: its file is the shared `nosession` one, nobody's own."""
    path = home / ".claude" / "state" / "command-runs" / f"{_safe_sid(sid)}.json"
    try:
        rec = json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        return None
    return rec if isinstance(rec, dict) else None


def _epoch(value: object) -> float:
    """A start time as a finite float; anything else (a string, Infinity, NaN) is 0 — it never blocks a resume."""
    try:
        v = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return v if math.isfinite(v) else 0.0


def woke(home: Path, self_sid: str) -> tuple[int, str]:
    m = _read_marker(home)
    paused_at = m.get("paused_at")
    if not isinstance(paused_at, (int, float)):
        return (
            1,
            "no pause is marked (hibernate.py mark was never run) — nothing to resume from here",
        )
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
            # the tick writes resume-wake only past its own gap threshold (CLAUDE_RESUME_GAP_MIN), so no floor here;
            # the EARLIEST wake after the mark is the one a resumed run started after (a later lift is no new wake)
            ts, gap = r.get("ts"), r.get("gap_s")
            if (
                isinstance(ts, (int, float))
                and isinstance(gap, (int, float))
                and ts > paused_at
                and (wake is None or ts < wake[1])
            ):
                wake = (f"the box slept {int(gap)} s (resume-wake)", ts)
    except OSError:
        pass
    if wake is None:
        return (
            1,
            f"no wake since the pause at {time.strftime('%F %T', time.localtime(paused_at))} — stay paused",
        )
    if self_sid:
        rec = _run_record(home, self_sid) or {}
        if rec.get("state") == "running" and _epoch(rec.get("started_epoch")) > wake[1]:
            return 1, "already resumed: your run is running again since the wake"
    return (
        0,
        f"RESUME — {wake[0]} at {time.strftime('%F %T', time.localtime(wake[1]))}: resume your item from its seed",
    )


# ── status ───────────────────────────────────────────────────────────────────────────────────────────────────────


def _git(path: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        return subprocess.run(
            ["git", "-C", path, *args], capture_output=True, text=True, timeout=60, env=env
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(args, 124, "", str(exc))
    except OSError as exc:
        return subprocess.CompletedProcess(args, 127, "", str(exc))


def worktree_state(path: str) -> tuple[bool, str]:
    """(blocks, why) for one live agent's worktree."""
    if not path or not os.path.isabs(path):  # `git -C ""` reads the CALLER's cwd
        return True, "no absolute cwd recorded"
    if not Path(path).is_dir():
        return True, "missing"
    st = _git(path, "status", "--porcelain")
    if st.returncode != 0:
        why = {124: "git timed out", 127: "git could not start"}.get(st.returncode)
        return True, f"not a git checkout ({why})" if why else "not a git checkout"
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


def status(home: Path, proc: Path, self_sid: str, opt: str = "/opt") -> tuple[int, list[dict]]:
    if not self_sid:
        return 2, [{"error": "no session id — pass --self (CLAUDE_CODE_SESSION_ID is unset)"}]
    sessions = [s for s in live_sessions(home, proc, opt) if not _is_pool(s)]
    if not sessions:
        return 2, [
            {
                "error": "no live agent session found — the session records or /proc are not readable from here"
            }
        ]
    if not any(s["sid"] == self_sid for s in sessions):
        return 2, [
            {
                "error": f"this session ({self_sid}) is not among the live sessions — wrong records dir or pid namespace"
            }
        ]
    rows = []
    for s in sessions:
        blocks, why = worktree_state(s["cwd"])
        rec = _run_record(home, s["sid"])
        mine = s["sid"] == self_sid
        if mine:
            why += " (you)"
        if not s["sid"]:
            blocks, why = True, "no session id in its record; " + why
        elif rec is None:
            blocks, why = True, "run record unreadable; " + why
        else:
            # the caller's own /hibernate run is running by design (only the top frame, never a parent under it);
            # every other running frame blocks, the caller's included
            frames = [rec, *(f for f in (rec.get("stack") or []) if isinstance(f, dict))]
            for i, fr in enumerate(frames):
                if fr.get("state") == "running" and not (
                    mine and i == 0 and fr.get("command") == "hibernate"
                ):
                    blocks, why = True, f"run /{fr.get('command', '?')} still running; " + why
                    break
        rows.append(
            {
                "repo": s["repo"] or "outside /opt",
                "agent": s["agent"] or s["peer"],
                "cwd": s["cwd"],
                "blocks": blocks,
                "why": why,
            }
        )
    rows.sort(key=lambda r: (r["repo"], r["agent"]))
    return (1 if any(r["blocks"] for r in rows) else 0), rows


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────────────────────


def _load_rotate():
    """rotate_session, loaded at the call: it loads this module at import, so a top-level import would be circular."""
    spec = importlib.util.spec_from_file_location(
        "_hib_rotate_session", Path(__file__).resolve().parent / "rotate_session.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load rotate_session.py beside hibernate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _offer_rotations(home: Path, proc: Path, opt: str) -> None:
    """After a lift: the agents past the rotation line, as offers (W-f975fee0 slice 3). Advice only — any fault is one
    stderr line and never fails the lift, which is the act."""
    try:
        rs = _load_rotate()
        lines = [
            f"  {r.get('repo') or '(no repo)'} {rs._line(dict(r, trigger='lift') if r['state'] == 'due' else r)}"
            for r in rs.due(home, proc, opt=opt)
        ]
        if lines:
            print(
                "hibernate: rotation offers — run each command at that agent's next boundary (D-1123); "
                "an unread row needs a look:\n" + "\n".join(lines)
            )
    # SystemExit too: rotate_session's import-time loads must not end the lift; a KeyboardInterrupt still does
    except (Exception, SystemExit) as exc:  # noqa: BLE001 — the lift is stamped already; a missing offer is safe
        with contextlib.suppress(Exception):
            print(
                f"hibernate: rotation offers unavailable — {type(exc).__name__}: {exc!r}",
                file=sys.stderr,
            )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--home", default=os.path.expanduser("~"), help=argparse.SUPPRESS)
    ap.add_argument("--proc", default="/proc", help=argparse.SUPPRESS)
    ap.add_argument("--opt", default="/opt", help=argparse.SUPPRESS)
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
        _offer_rotations(home, proc, a.opt)
        return 0
    if a.verb == "woke":
        rc, msg = woke(home, a.self)
        print(msg)
        return rc
    if a.verb == "targets":
        t = targets(home, proc, a.self, a.opt)
        if a.json:
            print(json.dumps(t, indent=2))
            return 0
        for r in t["repos"]:
            c = r["coordinator"]
            print(
                f"{r['repo']}: coordinator {r['owner'] or '-'} ({r['owner_why']})"
                + (f" → peer {c['peer']}" if c else "")
            )
            if r["note"]:
                print(f"  ! {r['note']}")
            for s in r["others"]:
                print(f"  - {s['agent'] or '(unnamed)'} → peer {s['peer']}  [{s['cwd']}]")
        for s in t["outside"]:
            print(
                f"outside /opt: {s['agent'] or '(unnamed)'} → peer {s['peer']}  [{s['cwd']}] — send the agent text directly"
            )
        if t["pool"]:
            seats = sum(1 for p in t["pool"] if p.get("parent_agent"))
            print(
                f"pool: {len(t['pool'])} headless session(s), never messaged ({seats} are a live agent's own seats)"
            )
        return 0
    rc, rows = status(home, proc, a.self, a.opt)
    if a.json:
        print(json.dumps({"rc": rc, "rows": rows}, indent=2))
        return rc
    if rc == 2:
        print(f"hibernate: NOT SAFE — {rows[0]['error']}", file=sys.stderr)
        return 2
    for r in rows:
        print(
            f"{'BLOCKS' if r['blocks'] else 'ok    '}  {r['repo']:28} {r['agent']:24} {r['why']}  [{r['cwd']}]"
        )
    print(
        "SAFE TO HIBERNATE"
        if rc == 0
        else f"NOT SAFE — {sum(r['blocks'] for r in rows)} row(s) block"
    )
    return rc


if __name__ == "__main__":
    sys.exit(main())
