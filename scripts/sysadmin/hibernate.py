#!/usr/bin/env python3
# AFTER-EDIT: docs/reference/hibernate.md | commands/_sources/hibernate.md | tests/test_hibernate.py
"""hibernate.py — the machinery behind /hibernate (W-1e9ae1e5): find every repo's live agents, hand out the pause
text, prove the box is safe to sleep, and tell a woken agent the pause is over.

  targets [--json] [--self SID]   every LIVE agent session grouped by repo, each repo's coordinator (its ledger's merge
                                  owner) and the pool sessions that are never messaged
  brief --role coordinator|agent --words "<the operator's words>" [--deadline]   the pause text to send; --deadline
                                  adds the marked T-3 and T as clock times
  mark --words "…" [--deadline 10m]   start a pause: a fresh marker (`paused_at`, `words`, `deadline_at` = T)
  paused                          exit 0 while a pause is marked and not lifted, 1 otherwise; a marker file it cannot
                                  read or parse, a home it cannot resolve, or any other error of its own is exit 0
                                  too, with one stderr line —
                                  every launcher reads non-0 as "proceed", so a corrupt marker holds them (review G4)
  lift                            the manual override (the tick lifts otherwise): only the hub's merge owner's session
                                  or the operator's plain shell; writes lifted_at + lift_path=hub (exit 0); 1 no
                                  pause marked; 2 a forged --proc/--home or a marker it cannot write; 3 refused;
                                  after a lift it prints rotation offers for the agents past the line (rotate_session
                                  `due`, advice only)
  status [--json] [--self SID]    one table: every live agent's worktree clean and pushed, no run `running` (the
                                  caller's own run excepted), a held self-watch, no live seat, a minute cron
                                  that beat in the last 3 minutes; with a mark a header names the pause, T-3, T
                                  and the time left; SAFE TO HIBERNATE only when no row blocks on two reads
                                  5 s apart
  woke [--self SID]               exit 0 (RESUME, with this session's seeds since the mark) only after the pause was
                                  lifted, within 24 h, and while this session has started no run since; 1 no
                                  pending resume; 2 it cannot tell (a corrupt marker or run record) — stay paused and
                                  tell the hub coordinator; never writes

The marker is `$ROTATE_STATE_DIR/hibernate.json` when that is set, else `<passwd home>/.claude/state/hibernate.json`
(`$HOME` when the uid has no passwd entry) — the
rotation tick's own state dir, beside the rotate ledger — and every writer goes through `update_marker`, which holds
an flock on `hibernate.json.lock` across its read-modify-write.

A session is LIVE when its record (`~/.claude*/sessions/<pid>.json`, `~/.claude-fleet/*/sessions/<pid>.json`) names a
pid whose /proc stat start time equals the record's `procStart` and whose comm is `claude`. An `entrypoint` of
`sdk-*` (`sdk-cli`, `sdk-ts`, `sdk-py`) is a pool worker or review seat (`claude -p`): listed, never messaged, never a coordinator, its
tree never a `status` row (a live one is a seat of the agent its parent chain reaches, else a headless row); every other entrypoint, an unknown or missing one included, is an agent (every record carries kind
"interactive", so `kind` cannot tell).
The agent's name comes from CLAUDE_AGENT in its environ, else its newest identity-store binding. Each repo's
coordinator is `decisions.py --merge-owner <repo>` (D-874), never a position. Everything read from another repo is
read-only (`git status`, `git rev-list`, `git branch -r --contains`).

Cobra (D-253): the cheapest way past `status` is a table with nothing in it — so no live session found, or the caller
not among them, is exit 2, never SAFE; the cheapest way past `woke` is an old lift read as new — so RESUME needs a lift
after the CURRENT mark, less than 24 h old, and no run this session started since it; and the cheapest way past
`lift`'s caller check is a fresh tmux window or any other real terminal with no claude ancestor, which this check
cannot tell from the operator's shell (no environment variable can claim a terminal: only the real stdin counts) — so
every plain-shell lift writes a `hibernate-lift-shell` ledger row naming its terminal, and the
lift stays visible.

Threat model of `lift`: every agent runs as the operator's uid, so the check cannot stop a session that sets out to
forge it; it stops an accidental or convention-breaking lift, and every lift path leaves a ledger row. So the test
overrides — a `--proc`/`--home` other than the real ones, and the FABRIK_DECISIONS_PY resolver — are refused outside
a test (PYTEST_CURRENT_TEST), and the plain-shell residual stays auditable.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import glob
import hashlib
import importlib.util
import json
import math
import os
import pwd
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# The pool is every Agent SDK entrypoint (`sdk-cli`, `sdk-ts`, `sdk-py`, ...); any other entrypoint, an unknown or a
# missing one included, is an agent (fail closed).
POOL_PREFIX = "sdk-"
DECISIONS = Path(__file__).resolve().parent.parent / "decisions.py"
HUB_DECISIONS = Path("/opt/fabrik/scripts/decisions.py")  # `lift`'s resolver outside a test
HUB = Path(__file__).resolve().parent.parent.parent  # the repo whose merge owner may `lift`
DAY_S = 24 * 3600
T3_S = 180  # the hard hold arms 3 minutes before the deadline
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


def _under_test() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def merge_owner(repo: str, resolver: Path | None = None, *, timeout: float = 30) -> tuple[str, str]:
    """(name, why) — the name is "" when the repo declares none or the lookup fails (incl. past `timeout` s, or an
    empty answer). `resolver` defaults to DECISIONS read at CALL time, so a patched module DECISIONS is honoured."""
    if resolver is None:
        resolver = DECISIONS
    if not (Path(repo) / "docs" / "DECISIONS.md").is_file():
        return "", "no ledger"
    try:
        out = subprocess.run(
            [sys.executable, str(resolver), "--merge-owner", repo],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "", f"lookup failed ({exc})"
    if out.returncode == 0:
        name = out.stdout.strip()
        return (name, "the ledger's merge owner") if name else ("", "lookup failed (empty answer)")
    if out.returncode == 3:
        return "", DECLARES_NONE
    return "", f"lookup failed (exit {out.returncode})"


def _is_pool(s: dict) -> bool:
    return s["entrypoint"].startswith(POOL_PREFIX)


def _agent_ancestor(proc: Path, pool_session: dict, agent_pids: set[int]) -> int | None:
    """The pid of the live agent a pool session's parent chain reaches (8 hops), else None."""
    pid, hops = pool_session.get("ppid"), 0
    while pid and hops < 8:
        if pid in agent_pids:
            return pid
        pid, hops = _ppid(proc, pid), hops + 1
    return None


def targets(home: Path, proc: Path, self_sid: str, opt: str = "/opt") -> dict:
    sessions = live_sessions(home, proc, opt)
    agents = [s for s in sessions if not _is_pool(s)]
    pool = [s for s in sessions if _is_pool(s)]
    agent_pids = {s["pid"] for s in agents}
    # a seat whose parent chain reaches a live agent is that agent's own subagent work
    for p in pool:
        p["parent_agent"] = ""
        owner_pid = _agent_ancestor(proc, p, agent_pids)
        if owner_pid is not None:
            p["parent_agent"] = next(
                a["agent"] or a["peer"] for a in agents if a["pid"] == owner_pid
            )
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


def _clock(epoch: float) -> str:
    return time.strftime("%H:%M", time.localtime(epoch))


def brief(role: str, words: str, deadline_at: float | None = None) -> str:
    hub = str(Path(__file__).resolve())
    fb = f'--feedback "{FEEDBACK}"'
    deadline = ""
    if deadline_at is not None:
        deadline = (
            f"\nDEADLINE: T-3 at {_clock(deadline_at - T3_S)} — from then the hold stops every world-changing tool (only"
            " commit, push, a run-record close and stop pass), so finish steps 2-4 before it; T at"
            f" {_clock(deadline_at)} — the operator closes the lid. Start no foreground Agent call that can outlast"
            " T-3; a seat still running then is abandoned — name each one in your close and RESUME note."
        )
    agent = f"""URGENT — PAUSE NOW for a hibernate. The operator, verbatim: "{words}".{deadline}
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
After the wake: run `python3 {hub} woke` when a RESUME or wake line arrives. It answers 0 only once the pause is
lifted, and lists your seeds newest first: resume the SAME item from them without being told again (each seed's
`command_run.py start --command <name> --phases <N> --resume-from <seed>` line, the parent run first) and re-run only
the seats it says exited with no output. Exit 1 (`no pending resume`): stay paused while it says the pause is not
lifted; otherwise carry on as usual. Exit 2: it cannot tell — stay paused and tell the hub coordinator."""
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


def _state_dir(home: Path) -> Path:
    """The rotation tick's state dir: `$ROTATE_STATE_DIR` when set, else `<home>/.claude/state`."""
    override = os.environ.get("ROTATE_STATE_DIR")
    return Path(override) if override else home / ".claude" / "state"


def marker_path(home: Path) -> Path:
    return _state_dir(home) / "hibernate.json"


def read_marker(home: Path) -> dict:
    """The marker as a dict; {} on ANY read error — so never the answer to "is a pause marked?" (`paused` reads the
    file raw: an unreadable marker is exit 2 there, not "unmarked")."""
    try:
        d = json.loads(marker_path(home).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def update_marker(home: Path, fn) -> dict:  # type: ignore[no-untyped-def]
    """Read-modify-write the marker under an exclusive flock on `hibernate.json.lock`: `fn(old) -> new`, the new dict
    replacing the file atomically. Two writers at once both land (the tick's lift and the hub's `lift` included).
    `fn` returning its argument itself writes nothing (an unreadable marker is never overwritten by a no-op)."""
    path = marker_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_name(path.name + ".lock"), "a", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)  # released when the file closes
        old = read_marker(home)
        new = fn(old)
        if new is old:
            return new
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".hibernate.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(new, fh)
                # durable before it is published (review G5): a host sleep or a VM cut right after the replace must
                # never leave a renamed but empty marker — a torn marker holds every launcher
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        try:  # the rename itself durable: fsync the directory (best effort, never fails the write)
            dfd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except OSError:
            pass
    return new


def _num(value: object) -> float | None:
    """A finite JSON number as a float; a bool, a string, Infinity or NaN is None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    v = float(value)
    return v if math.isfinite(v) else None


MIN_DEADLINE_S = T3_S  # under T-3 the hard hold would arm before the mark
MAX_DEADLINE_S = DAY_S


def _duration(text: str) -> float:
    """`10m`, `5m`, `1h`, `1.5h`; a bare number is minutes. Refused (argparse exit 2, before anything is written):
    under 180 s (T-3 would fall before the mark), over 24 h, or a value no float can hold."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([smh]?)\s*", text)
    if not m:
        raise argparse.ArgumentTypeError(f"not a duration: {text!r} (use 10m, 5m, 1h)")
    seconds = float(m[1]) * {"s": 1, "m": 60, "h": 3600, "": 60}[m[2]]
    if not math.isfinite(seconds) or not MIN_DEADLINE_S <= seconds <= MAX_DEADLINE_S:
        raise argparse.ArgumentTypeError(
            f"deadline {text!r} is outside 3m..24h (T-3 must fall after the mark, and a pause lasts at most a day)"
        )
    return seconds


def load_marker(home: Path) -> tuple[int, dict | None, str]:
    """The marker read RAW and validated: (0, marker, "") · (1, None, why) no marker file · (2, None, why) a file that
    cannot be read or parsed, is no JSON object, carries a non-numeric `paused_at`/`lifted_at`/`deadline_at`, or a
    PRESENT `paused_at` that is null (an absent key is "no pause"; a null `lifted_at`/`deadline_at` is absent). `read_marker`'s {}
    would read every one of those as unmarked; `paused`, `woke` and `lift` use this instead."""
    path = marker_path(home)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return 1, None, "no pause is marked"
    except (OSError, UnicodeDecodeError) as exc:
        return 2, None, f"the pause marker {path} cannot be read ({exc})"
    try:
        m = json.loads(raw)
    except ValueError as exc:
        return 2, None, f"the pause marker {path} is not JSON ({exc})"
    if not isinstance(m, dict):
        return 2, None, f"the pause marker {path} is not a JSON object"
    if (
        "paused_at" in m and _num(m["paused_at"]) is None
    ):  # null is corrupt here: fail-closed, never "not paused"
        return 2, None, f"the pause marker {path} has a null or non-numeric paused_at"
    for key in ("lifted_at", "deadline_at"):  # a null value is an absent key, never a corrupt one
        if m.get(key) is not None and _num(m[key]) is None:
            return 2, None, f"the pause marker {path} has a non-numeric {key}"
    return 0, m, ""


def paused(home: Path) -> tuple[int, str]:
    """0 marked and not lifted · 1 not paused (no marker file, no `paused_at`, or lifted) · 2 a marker file that
    cannot be read or parsed (`load_marker`)."""
    rc, m, why = load_marker(home)
    if m is None:
        return rc, why if rc == 2 else f"not paused — {why}"
    if m.get("paused_at") is None:
        return 1, "not paused — the marker names no pause"
    at = float(m["paused_at"])
    lifted_at = _num(m.get("lifted_at"))
    if lifted_at is not None and lifted_at >= at:
        return (
            1,
            f"not paused — the pause was lifted at {time.strftime('%F %T', time.localtime(lifted_at))}",
        )
    return 0, f"paused since {time.strftime('%F %T', time.localtime(at))}"


_LEDGER_LOCK_WAIT_S = 2.0


def _ledger_fallback() -> Path:
    override = os.environ.get("ROTATE_LEDGER_FALLBACK")
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / f"claude-rotate-ledger-fallback-{os.getuid()}.jsonl"


def _ledger_torn(path: Path) -> bool:
    """True when the ledger's last byte is not a newline. A separate read (the ledger may be write-only to us),
    non-blocking and a regular file only, so a FIFO swapped in at the path never blocks `lift` (G8)."""
    try:
        rfd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
        return False
    try:
        st = os.fstat(rfd)
        return bool(
            stat.S_ISREG(st.st_mode) and st.st_size and os.pread(rfd, 1, st.st_size - 1) != b"\n"
        )
    except OSError:
        return False
    finally:
        os.close(rfd)


def _ledger_row(home: Path, row: dict) -> None:
    """Append one row to the rotate ledger beside the marker — a copy of `claude_rotate.py::_ledger_append`'s
    discipline (never imported): write-only O_APPEND|O_CREAT|O_NONBLOCK, a regular file only, a SHARED flock against a
    trim's rewrite tried for at most 2 s and then appended unlocked, a newline first after a torn last line. Any
    failure puts the row in the fallback file (`ROTATE_LEDGER_FALLBACK`, else `<tempdir>/claude-rotate-ledger-
    fallback-<uid>.jsonl`, O_NOFOLLOW, 0600) and says so on stderr: a row is never dropped in silence."""
    path = _state_dir(home) / "rotate-ledger.jsonl"
    line = json.dumps(row)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NONBLOCK, 0o666)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise OSError(f"{path} is not a regular file")
            deadline = time.monotonic() + _LEDGER_LOCK_WAIT_S
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        break  # contended past the bound: append unlocked rather than hang `lift`
                    time.sleep(0.02)
                except OSError:
                    break  # this filesystem cannot lock
            torn = _ledger_torn(path)
            os.write(fd, (b"\n" if torn else b"") + line.encode("utf-8") + b"\n")
        finally:
            os.close(fd)
        return
    except OSError as exc:
        reason = str(exc)
    fallback = _ledger_fallback()
    try:
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
        fd = os.open(fallback, flags, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as fh:
            st = os.fstat(fh.fileno())
            if not stat.S_ISREG(st.st_mode):
                raise OSError(f"{fallback} is not a regular file")
            if st.st_uid != os.getuid():
                raise PermissionError(f"{fallback} is not owned by this user")
            os.fchmod(fh.fileno(), 0o600)
            fh.write(line + "\n")
        where = f"; kept in {fallback}"
    except OSError:
        where = "; the fallback file failed too"
    print(f"hibernate: rotate ledger write failed ({reason}){where} — row: {line}", file=sys.stderr)


def _safe_sid(sid: str) -> str:
    """command_run.py's record filename for a session id — a copy, pinned to it by tests/test_hibernate.py."""
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in sid)
    if not safe:
        return "nosession"
    if safe != sid:
        safe += "-" + hashlib.blake2s(sid.encode("utf-8", "replace"), digest_size=4).hexdigest()
    return safe


def _runs_dir(home: Path) -> Path:
    """command_run.py's store: `$COMMAND_RUN_DIR` when set, else `<home>/.claude/state/command-runs` (its seeds in
    `<that>/seeds`) — the same resolution as `scripts/command_run.py::_state_dir`."""
    override = os.environ.get("COMMAND_RUN_DIR")
    return Path(override) if override else home / ".claude" / "state" / "command-runs"


def _run_record(home: Path, sid: str) -> dict | None:
    """The session's run record: {} when it has none, None when one exists but is not a readable JSON object. Callers
    never pass an empty id: its file is the shared `nosession` one, nobody's own."""
    path = _runs_dir(home) / f"{_safe_sid(sid)}.json"
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


def _when(epoch: float) -> str:
    return time.strftime("%F %T", time.localtime(epoch))


LIFT_PATHS = (
    "the rotation tick lifts it after a sleep (a resume-wake row whose gap began after the mark and ended at or after"
    " T-3 — a nap during the drain lifts nothing), after a network outage once the API"
    " answers again, or 30 min past T (the pause cancelled); the hub coordinator's `hibernate.py lift` is the manual"
    " override"
)


def _seeds(home: Path, sid: str, since: float) -> list[Path]:
    """This session's seeds (`<command-runs>/seeds/<safe_sid>-…`) written after `since`, newest first — the parent
    run closes last, so it leads. A longer session id that merely shares the prefix is not this session's."""
    safe = _safe_sid(sid)
    seeds = _runs_dir(home) / "seeds"
    out: list[tuple[float, Path]] = []
    for name in glob.glob(str(seeds / (glob.escape(safe) + "*"))):
        p = Path(name)
        if not p.name[len(safe) :].startswith("-"):
            continue
        if p.suffix not in (
            ".json",
            ".md",
        ):  # command_run's in-flight `<name>.<pid>.tmp` is no seed yet
            continue
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        if mtime > since:
            out.append((mtime, p))
    return [p for _, p in sorted(out, key=lambda t: t[0], reverse=True)]


def _seat_state(proc: Path, seat: dict) -> tuple[str, bool]:
    """(the seat's state at the wake, whether to re-run it) — a frozen seat often finishes after the wake, so only one
    that exited with no output is ordered re-run. With no `procStart` recorded, a process on the pid counts only
    when it is `claude` — after a reboot the pid may be anyone's."""
    pid = seat.get("pid")
    if (
        isinstance(pid, int)
        and not isinstance(pid, bool)
        and pid > 0
        and (proc / str(pid)).is_dir()
    ):
        start = seat.get("procStart")
        if start is None:
            try:
                alive = (proc / str(pid) / "comm").read_text().strip() == "claude"
            except OSError:
                alive = False
        else:
            alive = str(_proc_start(proc, pid)) == str(start)
        if alive:
            return f"still running (pid {pid})", False
    output = seat.get("output")
    if isinstance(output, str) and output:
        try:
            if Path(output).stat().st_size > 0:
                return f"finished (output at {output})", False
        except OSError:
            pass
    return "exited, no output", True


def _seed_lines(proc: Path, seed: Path) -> list[str]:
    if seed.suffix != ".json":
        return [f"  - {seed}: a handoff — open a fresh start and follow its ## RESUME"]
    try:
        data = json.loads(seed.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    if not isinstance(data, dict):
        return [f"  - {seed}: unreadable — open it by hand"]
    command = data.get("command") if isinstance(data.get("command"), str) else "<name>"
    phases = data.get("phases") if isinstance(data.get("phases"), int) else "<N>"
    lines = [
        f"  - {seed}: python3 scripts/command_run.py start --command {command} --phases {phases}"
        f" --resume-from {seed}"
    ]
    for seat in data.get("abandoned_seats") or []:
        if not isinstance(seat, dict):
            continue
        state, rerun = _seat_state(proc, seat)
        purpose = seat.get("purpose") or seat.get("brief") or "seat"
        brief_path = seat.get("brief") or "(no brief recorded)"
        lines.append(
            f"      seat {purpose}: {state}"
            + (f" — re-run it from its brief {brief_path}" if rerun else "")
        )
    return lines


def woke(home: Path, proc: Path, self_sid: str, now: float | None = None) -> tuple[int, str]:
    """RESUME (0) only after the hibernate lift (`lifted_at` at or after the mark), never for `lift_path=migration`,
    never 24 h after the lift, and only while this session has started no run since it (in any state); a resume-wake
    row is the lift's evidence, never this answer's. Otherwise 1 `no pending resume`; 2 when the marker is corrupt
    (`load_marker`) or this session's run record exists but cannot be read — it cannot tell, so it never resumes."""
    now = time.time() if now is None else now
    rc, m, why = load_marker(home)
    if rc == 2:
        return (
            2,
            f"cannot answer: {why} — run `hibernate.py paused`, and ask the hub coordinator to lift",
        )
    paused_at = _num((m or {}).get("paused_at"))
    if m is None or paused_at is None:
        return 1, "no pending resume — no pause is marked (hibernate.py mark was never run)"
    lifted_at = _num(m.get("lifted_at"))
    if lifted_at is None or lifted_at < paused_at:
        return (
            1,
            f"no pending resume — the pause marked at {_when(paused_at)} is not lifted yet; stay paused. The lift"
            f" paths: {LIFT_PATHS}",
        )
    if m.get("lift_path") == "migration":
        return 1, "no pending resume — this pause was closed by the marker migration, not by a wake"
    if now - lifted_at >= DAY_S:
        return 1, f"no pending resume — the lift at {_when(lifted_at)} is 24 h old or more"
    if self_sid:
        rec = _run_record(home, self_sid)
        if rec is None:
            path = _runs_dir(home) / f"{_safe_sid(self_sid)}.json"
            return (
                2,
                f"cannot tell whether a run started after the lift: {path} cannot be read or parsed",
            )
        if _epoch(rec.get("started_epoch")) > lifted_at:
            return (
                1,
                "no pending resume — this session started a run after the lift (already resumed)",
            )
    lines = [
        f"RESUME — the hibernate pause ended at {_when(lifted_at)} (lift: {m.get('lift_path') or 'unknown'}):"
        " resume your item from its seed"
    ]
    if not self_sid:
        lines.append("no session id (pass --self): this session's seeds cannot be listed")
    else:
        seeds = _seeds(home, self_sid, paused_at)
        if seeds:
            lines.append(
                f"seeds written since the pause at {_when(paused_at)}, newest first (the parent first):"
            )
            for seed in seeds:
                lines.extend(_seed_lines(proc, seed))
        else:
            lines.append(
                "no seed written since the pause — resume from your RESUME note and memory"
            )
        lines.append(
            f"get_chat: session {self_sid}, the window before the pause at {_when(paused_at)} — for any detail a"
            " compaction dropped"
        )
    return 0, "\n".join(lines)


# ── lift ─────────────────────────────────────────────────────────────────────────────────────────────────────────


def _caller(proc: Path, sessions: dict[int, dict]) -> tuple[dict | None, str]:
    """The nearest live claude session (agent or `sdk-*` alike) on this process's ppid chain, walked to pid 1 with no
    hop cap: (session, "") · (None, "") when the walk reached pid 1 with none · (None, why) when it could not."""
    pid, seen = os.getppid(), set()
    while pid > 1:
        if pid in sessions:
            return sessions[pid], ""
        if pid in seen:
            return None, f"the parent chain loops at pid {pid}"
        seen.add(pid)
        nxt = _ppid(proc, pid)
        if nxt is None:
            return (
                None,
                f"pid {pid} cannot be read under {proc}, so the chain to pid 1 is unprovable",
            )
        pid = nxt
    return None, ""


def _terminal() -> str:
    """The terminal on the REAL stdin, or "" (a process detached with setsid or systemd-run has none). Nothing in the
    environment can claim one: the tests hand the process a real pseudo-terminal."""
    try:
        return os.ttyname(0) if os.isatty(0) else ""
    except OSError:
        return ""


def lift(home: Path, proc: Path, opt: str = "/opt") -> tuple[int, str]:
    """The manual lift: 0 lifted (or already lifted) · 1 no pause is marked · 2 the marker cannot be written (and,
    from `main`, a forged --proc/--home) · 3 refused (a ledger row says why)."""
    now = time.time()
    sessions = {s["pid"]: s for s in live_sessions(home, proc, opt)}
    caller, unprovable = _caller(proc, sessions)
    refusal, tty = "", ""
    if unprovable:
        refusal = unprovable
    elif caller is None:
        tty = _terminal()
        if not tty:
            refusal = "no claude session on the chain to pid 1 and stdin is no terminal (a detached process)"
    elif _is_pool(caller):  # before any name check: a seat inherits its parent's CLAUDE_AGENT
        refusal = f"session {caller['sid']} is a headless {caller['entrypoint']} session"
    else:
        # the resolver seam is a test's only: outside one, the hub's own decisions.py names the owner (F1)
        seam = os.environ.get("FABRIK_DECISIONS_PY")
        resolver = Path(seam) if seam and _under_test() else HUB_DECISIONS
        owner, why = merge_owner(str(HUB), resolver)
        if not owner or caller["agent"] != owner:
            refusal = (
                f"session {caller['sid']} ({caller['agent'] or 'unnamed'}) is not the hub's merge owner"
                f" ({owner or why})"
            )
    if refusal:
        _ledger_row(
            home,
            {
                "event": "hibernate-lift-refused",
                "ts": now,
                "why": refusal,
                "pid": caller["pid"] if caller else None,
                "sid": caller["sid"] if caller else "",
                "agent": caller["agent"] if caller else "",
            },
        )
        return (
            3,
            f"hibernate: lift REFUSED — {refusal}; only the hub coordinator's session or the operator's shell lifts",
        )
    result: dict[str, object] = {}
    path = marker_path(home)

    def apply(m: dict) -> dict:
        if (
            load_marker(home)[0] == 2
        ):  # re-read under the lock: a corrupt marker would stand paused (exit 2) forever
            try:
                at_file = path.stat().st_mtime
            except OSError:
                at_file = now
            result["replaced"] = True
            return {
                "paused_at": at_file,
                "words": "(unreadable marker replaced by lift)",
                "lifted_at": now,
                "lift_path": "hub",
            }
        at = _num(m.get("paused_at"))
        if at is None:
            result["rc"] = 1
            return m
        lifted_at = _num(m.get("lifted_at"))
        if lifted_at is not None and lifted_at >= at:
            result["already"] = (
                lifted_at  # never moved: a session that resumed after it stays resumed
            )
            return m
        return {**m, "lifted_at": now, "lift_path": "hub"}

    try:
        update_marker(home, apply)
    except OSError as exc:  # e.g. a directory standing where the marker should be
        return 2, f"hibernate: the marker {path} cannot be written ({exc})"
    if result.get("rc") == 1:
        return 1, "hibernate: no pause is marked — nothing to lift"
    if tty:
        _ledger_row(home, {"event": "hibernate-lift-shell", "ts": now, "tty": tty})
    if result.get("replaced"):
        _ledger_row(home, {"event": "hibernate-lift-replaced-marker", "ts": now, "path": str(path)})
        return 0, (
            f"hibernate: the marker {path} was unreadable — replaced by a well-formed lifted marker"
            " (lift_path=hub); every paused agent's `woke` now answers RESUME"
        )
    if "already" in result:
        return 0, f"hibernate: the pause was already lifted at {_when(float(result['already']))}"  # type: ignore[arg-type]
    return 0, (
        "hibernate: pause lifted (lift_path=hub) — every paused agent's `woke` now answers RESUME; the tick clears"
        " the hibernate tier"
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
        names = [ln[3:] for ln in tracked[:5]]
        more = f" +{len(tracked) - 5} more" if len(tracked) > 5 else ""
        return True, f"{len(tracked)} uncommitted change(s): {', '.join(names)}{more}"
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


HEARTBEAT_MAX_S = 180  # the minute cron beats every 60 s; three missed beats is no cron
CLOSED_STATES = ("blocked", "handoff", "done")


def _lock_dir() -> Path:
    """The self-watch lock dir, read directly: `$CLAUDE_SOUND_LOCKDIR`, else `/tmp/claude-sound-locks-<uid>`."""
    override = os.environ.get("CLAUDE_SOUND_LOCKDIR")
    return Path(override) if override else Path(f"/tmp/claude-sound-locks-{os.getuid()}")


def _selfwatch_safe(sid: str) -> str:
    """The watcher's own filename transform (`tr -c 'A-Za-z0-9_-' '_' | head -c 64`) — a copy of
    `claude_rotate.py::_selfwatch_safe`, pinned to it by tests/test_hibernate.py."""
    out = bytearray()
    for b in sid.encode("utf-8", "surrogateescape"):
        out.append(b if (chr(b).isalnum() and b < 128) or b in b"_-" else ord("_"))
    return out[:64].decode("ascii")


def _lock_in_proc_locks(st: os.stat_result) -> bool:
    """Positive-only `/proc/locks` read (`selfwatch_check.py`): presence proves a holder, absence proves nothing."""
    try:
        text = Path("/proc/locks").read_text()
    except OSError:
        return False
    want = f"{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x}:{st.st_ino}"
    return any(
        len(parts) >= 6 and parts[1] == "FLOCK" and parts[5] == want
        for parts in (ln.split() for ln in text.splitlines())
    )


def _armed(lock_dir: Path, sid: str) -> bool:
    """The tick's armed rule (`claude_rotate.py::_armed_sids` / `_sid_is_armed`): `<safe>.selfwatch.lock` HELD by a
    live process. A missing dir, a missing file or a lock that cannot be probed is NOT armed (fail closed)."""
    path = lock_dir / f"{_selfwatch_safe(sid)}.selfwatch.lock"
    try:
        fd = os.open(
            str(path), os.O_RDONLY | os.O_NONBLOCK
        )  # never blocks on a FIFO at the lock path
    except OSError:
        return False
    try:
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                return False
            if _lock_in_proc_locks(st):
                return True
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        except OSError:
            return False
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def _minute_cron_alive(home: Path, now: float) -> bool:
    """`$ROTATE_STATE_DIR/battery-tick-last` (the minute cron's epoch) is at most 180 s old; absent, unparsable or
    from the future (over 60 s ahead) is dead."""
    try:
        fd = os.open(_state_dir(home) / "battery-tick-last", os.O_RDONLY | os.O_NONBLOCK)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                return False
            beat = _num(float(os.read(fd, 64).decode("ascii", "replace").strip()))
        finally:
            os.close(fd)
    except (OSError, ValueError):
        return False
    return beat is not None and -60 <= now - beat <= HEARTBEAT_MAX_S


def _live_mark(home: Path) -> tuple[dict | None, str]:
    """(the marker while a pause is marked and not lifted, "") · (None, "") unmarked · (None, why) unreadable."""
    rc, m, why = load_marker(home)
    if rc == 2:
        return None, why
    at = _num((m or {}).get("paused_at"))
    if m is None or at is None:
        return None, ""
    lifted = _num(m.get("lifted_at"))
    return (None, "") if lifted is not None and lifted >= at else (m, "")


def _readable_file(value: object) -> bool:
    """A regular file that reads. Opened O_NONBLOCK and checked with S_ISREG on the fd, so a FIFO swapped in at a
    record-supplied path is "unreadable", never a hang."""
    if not isinstance(value, str) or not value:
        return False
    try:
        fd = os.open(value, os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
        return False
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return False
        os.read(fd, 1)
        return True
    except OSError:
        return False
    finally:
        os.close(fd)


def _clean(text: object) -> str:
    """Marker- or record-derived text made safe to print: every control character (a newline included) becomes a
    visible escape, so it cannot forge a table line."""
    return re.sub(
        r"[\x00-\x1f\x7f-\x9f  ]",
        lambda m: m.group().encode("unicode_escape").decode("ascii"),
        str(text),
    )


def _seat_lines(rec: dict | None) -> list[str]:
    seats = (rec or {}).get("abandoned_seats")
    out = []
    for seat in seats if isinstance(seats, list) else []:
        if isinstance(seat, dict):
            out.append(
                f"abandoned seat: {seat.get('purpose') or 'seat'} ({seat.get('brief') or 'no brief recorded'})"
            )
    return out


def _agent_row(s: dict, blocks: bool, why: str) -> dict:
    return {
        "repo": s["repo"] or "outside /opt",
        "agent": s["agent"] or s["peer"],
        "cwd": s["cwd"],
        "blocks": blocks,
        "why": why,
    }


def status(
    home: Path, proc: Path, self_sid: str, opt: str = "/opt", now: float | None = None
) -> tuple[int, list[dict]]:
    now = time.time() if now is None else now
    if not self_sid:
        return 2, [{"error": "no session id — pass --self (CLAUDE_CODE_SESSION_ID is unset)"}]
    live = live_sessions(home, proc, opt)
    sessions = [s for s in live if not _is_pool(s)]
    pool = [s for s in live if _is_pool(s)]
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
    mark, mark_err = _live_mark(home)
    deadline_at = _num(mark.get("deadline_at")) if mark else None
    in_t3 = deadline_at is not None and now >= deadline_at - T3_S
    phase = "from T-3" if in_t3 else "before T-3"
    paused_at = _num(mark.get("paused_at")) if mark else None
    agent_pids = {s["pid"] for s in sessions}
    seats_of: dict[int, list[dict]] = {}
    rows: list[dict] = []
    for p in (
        pool
    ):  # checks 1 and 2: a live `sdk-*` session is an agent's seat or a headless row of its own
        owner = _agent_ancestor(proc, p, agent_pids)
        if owner is not None:
            seats_of.setdefault(owner, []).append(p)
            continue
        label = f"headless {p['entrypoint']} session pid {p['pid']}"
        rows.append(
            {
                "repo": "headless",
                "agent": p["peer"] or p["entrypoint"],
                "cwd": p["cwd"],
                "blocks": not in_t3,
                "why": f"held (headless) — {label}; the hold stops its tools, its pool requeues it"
                if in_t3
                else f"{label}, no agent's seat — blocks {phase}",
            }
        )
    lock_dir = _lock_dir()
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
        extra_rows: list[dict] = []
        if s["sid"]:
            if not _armed(lock_dir, s["sid"]):  # check 6
                blocks, why = True, "self-watch not armed (no wake reaches it); " + why
            seats = seats_of.get(s["pid"], [])
            if seats:  # check 2
                # the close counts only when it is this pause's: check 5's time bound (a close from before the
                # mark names seats of an earlier run)
                close_ts = _num((rec or {}).get("updated_ts"))
                this_pause = paused_at is not None and (
                    close_ts is None or close_ts + 1 >= math.floor(paused_at)
                )
                named = (
                    _seat_lines(rec)
                    if (rec or {}).get("state") in CLOSED_STATES and this_pause
                    else []
                )
                have = f"{len(seats)} live seat(s)"
                if not in_t3:
                    blocks, why = True, f"{have} — blocks {phase}; " + why
                elif len(named) < len(seats):
                    blocks, why = (
                        True,
                        f"{have} not named by the close ({len(named)} abandoned seat(s) recorded); "
                        + why,
                    )
                else:
                    why = f"{have}, all abandoned by the close; " + why
                if named and in_t3:
                    why += "; " + "; ".join(named)
            if mark and paused_at is not None and not mine and isinstance(rec, dict):  # check 5
                state = rec.get("state")
                closed_ts = _num(rec.get("updated_ts"))
                after_mark = state in CLOSED_STATES and (
                    closed_ts is None or closed_ts + 1 >= math.floor(paused_at)
                )
                if after_mark and state in ("blocked", "handoff"):
                    seeded = _readable_file(rec.get("resume_seed")) or _readable_file(
                        rec.get("resume_copy")
                    )
                    if not seeded:
                        blocks, why = (
                            True,
                            f"closed {state} after the mark with no resume seed; " + why,
                        )
                elif after_mark and state == "done":
                    extra_rows.append(
                        _agent_row(
                            s,
                            False,
                            "done since the mark — verify the item was finished, not abandoned",
                        )
                    )
        rows.append(_agent_row(s, blocks, why))
        rows.extend(extra_rows)
    if mark_err:
        rows.append(
            {"repo": "box", "agent": "pause marker", "cwd": "", "blocks": True, "why": mark_err}
        )
    if not _minute_cron_alive(home, now):
        beat = _state_dir(home) / "battery-tick-last"
        rows.append(
            {
                "repo": "box",
                "agent": "minute cron",
                "cwd": "",
                "blocks": True,
                "why": f"no minute cron — {beat} is absent or older than {HEARTBEAT_MAX_S} s, so"
                " nothing arms the T-3 hold or lifts the pause",
            }
        )
    rows.sort(key=lambda r: (r["repo"], r["agent"]))
    return (1 if any(r["blocks"] for r in rows) else 0), rows


def status_confirmed(
    home: Path,
    proc: Path,
    self_sid: str,
    opt: str = "/opt",
    *,
    gap: float = 5.0,
    sleep=time.sleep,  # type: ignore[no-untyped-def]
) -> tuple[int, list[dict]]:
    """`status` read twice, `gap` seconds apart, before it answers SAFE: a busy count is never instant. A first read
    that blocks (or errors) is the answer at once; the second read's table is the one reported."""
    rc, rows = status(home, proc, self_sid, opt)
    if rc != 0:
        return rc, rows
    sleep(gap)
    return status(home, proc, self_sid, opt)


def _left(seconds: float) -> str:
    m, sec = divmod(int(abs(seconds)), 60)
    text = f"{m} min {sec:02d} s"
    return f"{text} left" if seconds >= 0 else f"T passed {text} ago"


def status_header(home: Path, now: float | None = None) -> str | None:
    """With a pause marked and not lifted: its time, the clock times of T-3 and T and the time left; else None."""
    now = time.time() if now is None else now
    mark, _ = _live_mark(home)
    if not mark:
        return None
    at = float(mark["paused_at"])
    words = _clean(mark.get("words") or "no words")
    head = f"PAUSE marked at {time.strftime('%H:%M:%S', time.localtime(at))} ({words})"
    deadline_at = _num(mark.get("deadline_at"))
    if deadline_at is None:
        return head + " — no deadline set (T-3 and T are undefined)"
    try:
        tier = (
            (_state_dir(home) / "fleet-exhausted")
            .read_text(errors="replace")
            .split("\n")[1]
            .strip()
        )
    except (OSError, IndexError):
        tier = ""
    hold = "hold: hibernate tier standing" if tier == "hibernate" else "hold: not armed yet"
    return (
        f"{head} — T-3 at {_clock(deadline_at - T3_S)}, T at {_clock(deadline_at)}, "
        f"{_left(deadline_at - now)} ({hold})"
    )


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────────────────────


def _default_home() -> Path:
    """The ONE home every verb defaults to: the passwd home, never `$HOME` (which a caller sets as freely) — except
    for a uid with no passwd entry (a container), where `$HOME` (`~`) is all there is. Fails closed: when that
    fallback is not an absolute path (no `$HOME` either, `~` stays literal and would resolve against the cwd) it
    raises RuntimeError, which `main` turns into exit 2 for every verb."""
    try:
        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except KeyError:
        fallback = os.path.expanduser("~")
        if not os.path.isabs(fallback):
            raise RuntimeError(
                "hibernate: no passwd entry for this uid and no usable $HOME — the pause marker cannot be located"
            ) from None
        return Path(fallback)


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
    # None = not given: every verb then reads the passwd home (`_default_home`, never $HOME) and /proc
    ap.add_argument("--home", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--proc", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--opt", default="/opt", help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="verb", required=True)
    for name in ("targets", "status"):
        p = sub.add_parser(name)
        p.add_argument("--json", action="store_true")
        p.add_argument("--self", default=os.environ.get("CLAUDE_CODE_SESSION_ID", ""))
    b = sub.add_parser("brief")
    b.add_argument("--role", choices=("coordinator", "agent"), required=True)
    b.add_argument("--words", required=True)
    b.add_argument(
        "--deadline", action="store_true", help="name the marked T-3 and T as clock times"
    )
    mk = sub.add_parser("mark")
    mk.add_argument("--words", required=True)
    mk.add_argument(
        "--deadline",
        type=_duration,
        help="T, from now, 3m..24h: 10m, 5m, 1h (a bare number is minutes)",
    )
    sub.add_parser("paused")
    sub.add_parser("lift")
    w = sub.add_parser("woke")
    w.add_argument("--self", default=os.environ.get("CLAUDE_CODE_SESSION_ID", ""))
    a = ap.parse_args(argv)
    try:
        home = Path(a.home) if a.home is not None else _default_home()
        real_home = _default_home() if a.verb == "lift" else None
    except RuntimeError as exc:
        # a home it cannot resolve is an error of `paused`'s own: held as paused (exit 0, review N1); others refuse
        if a.verb == "paused":
            print(f"{exc} — held as paused until the hub repairs it", file=sys.stderr)
            return 0
        print(exc, file=sys.stderr)
        return 2
    proc = Path(a.proc if a.proc is not None else "/proc")

    if a.verb == "paused":
        # review G4: every launcher reads anything but 0 as "proceed", so a marker that EXISTS but cannot be read or
        # parsed (the function's 2) — or any error of the verb's own, the unresolvable home above included — exits 0
        # (PAUSED) with one stderr line: a corrupt
        # marker holds every launcher until the hub repairs or lifts it (`status` shows it). A MISSING marker stays 1.
        # The function keeps its 2: the Stop and posture hooks' inline copies follow it and fail OPEN on purpose.
        try:
            rc, msg = paused(home)
        except Exception as exc:
            rc, msg = 2, f"hibernate paused: {type(exc).__name__}: {exc}"
        if rc == 2:
            print(f"{msg} — held as paused until the hub repairs or lifts it", file=sys.stderr)
            return 0
        print(msg)
        return rc
    if a.verb == "brief":
        deadline_at = None
        if a.deadline:
            deadline_at = _num(read_marker(home).get("deadline_at"))
            if deadline_at is None:
                print(
                    "hibernate: no deadline is marked (mark --deadline <d> first)", file=sys.stderr
                )
                return 2
        print(brief(a.role, a.words, deadline_at))
        return 0
    if a.verb == "mark":
        now = time.time()
        fresh: dict[str, object] = {"paused_at": now, "words": a.words}
        if a.deadline is not None:
            fresh["deadline_at"] = now + a.deadline
        update_marker(home, lambda _old: fresh)  # a fresh pause: no key of an earlier one survives
        tail = ""
        if a.deadline is not None:
            tail = f" — T-3 at {_clock(now + a.deadline - T3_S)}, T at {_clock(now + a.deadline)}"
        print(f"hibernate: pause marked in {marker_path(home)}{tail}")
        return 0
    if a.verb == "lift":
        # F2: a forged --proc (a made-up ppid chain) or --home (made-up session records) is a test's only. Each is
        # compared only when GIVEN; not given, every verb reads the passwd home and
        # /proc. A refusal leaves its ledger row like every other one (G7).
        assert real_home is not None  # computed above for this verb
        if not _under_test():
            forged = [
                f"--{name} {given}"
                for name, given, real in (
                    ("proc", a.proc, Path("/proc")),
                    ("home", a.home, real_home),
                )
                if given is not None and Path(given).resolve() != real.resolve()
            ]
            if forged:
                why = f"forged {' and '.join(forged)}: lift reads the real /proc and home only"
                _ledger_row(
                    real_home,
                    {"event": "hibernate-lift-refused", "ts": time.time(), "why": why, "pid": None},
                )
                print(f"hibernate: {why}", file=sys.stderr)
                return 2
        rc, msg = lift(home, proc, a.opt)
        print(msg, file=sys.stdout if rc == 0 else sys.stderr)
        if rc == 0:
            _offer_rotations(home, proc, a.opt)
        return rc
    if a.verb == "woke":
        rc, msg = woke(home, proc, a.self)
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
    gap = 5.0
    if _under_test() and os.environ.get("HIBERNATE_STATUS_GAP_S"):  # the seam: a test's only
        try:
            gap = max(0.0, float(os.environ["HIBERNATE_STATUS_GAP_S"]))
        except ValueError:
            pass
    rc, rows = status_confirmed(home, proc, a.self, a.opt, gap=gap)
    header = status_header(home) if rc != 2 else None
    if a.json:
        print(json.dumps({"rc": rc, "header": header, "rows": rows}, indent=2))
        return rc
    if rc == 2:
        print(f"hibernate: NOT SAFE — {rows[0]['error']}", file=sys.stderr)
        return 2
    if header:
        print(header)
    for r in rows:
        print(
            f"{'BLOCKS' if r['blocks'] else 'ok    '}  {_clean(r['repo']):28} {_clean(r['agent']):24}"
            f" {_clean(r['why'])}  [{_clean(r['cwd'])}]"
        )
    print(
        "SAFE TO HIBERNATE"
        if rc == 0
        else f"NOT SAFE — {sum(r['blocks'] for r in rows)} row(s) block"
    )
    return rc


if __name__ == "__main__":
    sys.exit(main())
