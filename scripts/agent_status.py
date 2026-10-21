#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/hooks-index.md
"""Every hub worker's NOW, DONE and NEXT — or, with --json --all, every repo's agents — read from records that already exist.

The coordinator must always know what each agent is doing, has finished and will do next, and
recover it after losing context (operator 2026-10-15, D-880). Nothing here is stored: each run reads

- NOW  — live or no window (work.py ``_present`` over the role's tree, /proc); the role's newest
         ``running`` run record (command_run.py ``_state_dir()``) from ANY repo, the repo named when
         it is not the hub; the item it holds a claim on (work.py ``_live_claims``);
- DONE — the role's last merges on the store's base branch, both merge-owner eras
         (``merge(infra): worktree-<role>`` before D-874, ``merge(coordinator): ...`` after), never a
         builder's back-merge of master; and the distinct items those subjects name in the last 24 h
         (a closed item carries no close time);
- NEXT — the role's queue as ``work.py queue`` counts a pool worker's (``_worker_queues``; ``queue``
         lists no row for the feedback owner, which is shown here all the same), top 3, with
         the queue's size and the role's parked items in the MAIN store (``work.py queue`` counts parked
         in the worker's own tree, so a park not yet merged shows there first).

(W-cfff98dd e, D-880.) The rows are the repo's own BUILDERS (``_roster``, W-16d0ef14): the names in
``.fabrik/session-agents.json`` when it names one, else the names bound to the repo that have a worktree, minus the
distributor (the reader itself), the merge owner and coordinator names. ``--json`` prints the full data. ``--json --all`` is the BOX view instead
(``collect_box``, W-7159f8e2 — the dashboard's Agents block): every repo under ``--opt`` (default
FABRIK_OPT_DIR, else /opt) with a work store or an agent, its agents being the open windows (/proc),
the run records of that repo in the last 7 days and the claim holders, plus each agent's pause
(work.py ``_paused``) and whether the repo's own work.py carries the ``pause`` verb. ``--session-start`` is the
coordinator's SessionStart hook (``.claude/settings.json``, its own entry, so its own 10,000-character
output budget): it prints only for the distributor, never in a ``claude -p`` child, one line when the
identity is unknown, one line on any error, and always exits 0. The modules it uses (work, command_run,
whoami_agent, decisions) sit beside it and are loaded by file path (never via sys.path), read only.

COBRA: the table can read "no run" for an agent busy without a record (an ad-hoc edit, a stale or
missing record) — so the header repeats the charter's rule: no record, or an old one, means ask the
agent; the live/no-window column shows a window that is up but silent.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any

HERE = Path(__file__).resolve().parent
TITLE_CUT = 100  # characters of an item title in the text view
ROLE_CUT = 1400  # characters of one role's block before "… N more"
TOTAL_CUT = 7000  # whole text output — inside the 10,000-character hook cap with the header
MERGES_SHOWN = 3
NEXT_SHOWN = 3
WORK_PY_MAX = (
    4 * 1024 * 1024
)  # bytes of a repo's work.py read for its pause verb (the hub's is ~0.3 MB)
# the Stop hook's DEFAULT stale bound (final_gate_stop.py _STALE_H_DEFAULT): older = likely a dead session.
# Its COMMAND_RUN_STALE_H override is not read: 0 there means "never trap me", which here would mark all stale.
STALE_H = 12
_ITEM_RE = re.compile(r"\bitem (W-[0-9a-f]{8}|none)\b")


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"_agent_status_{name}", HERE / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load scripts/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses and typing introspection look the module up by name
    spec.loader.exec_module(mod)
    return mod


def _age(ts: float, now: float) -> str:
    s = max(0, int(now - ts))
    if s < 3600:
        return f"{s // 60}m ago"
    if s < 86400:
        return f"{s // 3600}h ago"
    return f"{s // 86400}d ago"


def _cut(text: object, n: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _under(path: Path, main: Path) -> bool:
    """True when ``path`` is the main checkout or one of its `.claude/worktrees/*` trees."""
    try:
        p = path.resolve()
    except OSError:
        return False
    return p == main or p.parent == (main / ".claude" / "worktrees").resolve()


def _now(cr: ModuleType, role: str, main: Path) -> dict | None:
    best: dict | None = None
    best_ts = 0.0
    for path in cr._state_dir().glob("*.json"):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
            ts = float(rec.get("updated_ts") or 0) if isinstance(rec, dict) else 0.0
        except (
            OSError,
            ValueError,
            TypeError,
            OverflowError,
        ):  # a 400-digit int stamp overflows float()
            continue  # an unreadable or corrupt record is skipped, never a crash
        if not math.isfinite(ts):
            continue  # "inf"/"nan" parse as floats but are no time (int(now - inf) raises)
        if not isinstance(rec, dict) or rec.get("agent") != role or rec.get("state") != "running":
            continue
        if best is None or ts > best_ts:
            best, best_ts = rec, ts
    return None if best is None else _now_view(best, best_ts, main)


def _now_view(best: dict, best_ts: float, main: Path) -> dict:
    """A running record as the NOW cell: shared by the hub view and the box view."""
    root = str(best.get("repo_root") or "")
    stack = best.get("stack")
    first = stack[0] if isinstance(stack, list) and stack and isinstance(stack[0], dict) else {}
    return {
        "command": str(best.get("command") or ""),
        "phase": best.get("phase"),
        "phases": best.get("phases"),
        "title": str(best.get("phase_title") or ""),
        "surface": str(best.get("surface") or ""),
        "updated_ts": best_ts,
        "stale": time.time() - best_ts > STALE_H * 3600,
        "repo": "" if root and _under(Path(root), main) else root,
        "stack_root": str(first.get("command") or "") if first else "",
        "session": str(best.get("session_id") or ""),
    }


def _merges(main: Path, base: str, roles: list[str], now: float) -> dict[str, dict]:
    out: dict[str, dict[str, Any]] = {r: {"merges": [], "items_24h": 0} for r in roles}
    seen: dict[str, set[str]] = {r: set() for r in roles}
    try:
        log = subprocess.run(
            # filtered to merge subjects BEFORE the limit, so a quiet role's old merge stays in view
            [
                "git",
                "-C",
                str(main),
                "log",
                base,
                "-E",
                "--grep=^merge\\(",
                "-n",
                "400",
                "--format=%h%x09%ct%x09%s",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return out
    # anchored on the branch name, so a builder's back-merge ("merge(x): origin/master into worktree-x")
    # never matches, and a request whose text quotes that phrase is not dropped
    pats = {r: re.compile(rf"^merge\([a-z0-9-]+\): worktree-{re.escape(r)}(?:\s|$)") for r in roles}
    for line in log.splitlines():
        sha, _, rest = line.partition("\t")
        ct, _, subject = rest.partition("\t")
        for role, rx in pats.items():
            if not rx.match(subject):
                continue
            m = _ITEM_RE.search(subject)
            item = m.group(1) if m and m.group(1) != "none" else ""
            ts = float(ct or 0)
            if len(out[role]["merges"]) < MERGES_SHOWN:
                out[role]["merges"].append({"sha": sha, "ts": ts, "item": item, "subject": subject})
            if item and ts >= now - 86400:
                seen[role].add(item)
    for role in roles:
        out[role]["items_24h"] = len(seen[role])
    return out


REGISTRY_MAX = 1 << 20  # bytes of `.fabrik/session-agents.json` read at most


def _coordinators(main: Path, distributor: str) -> set[str]:
    """The names that read the table rather than sit in it: the distributor and the ledger's merge owner."""
    out = {distributor} if distributor else set()
    try:
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            rc = _load("decisions")._merge_owner(main)
        if rc == 0 and buf.getvalue().strip():
            out.add(buf.getvalue().strip())
    except Exception:  # noqa: BLE001 — no ledger reader here: the distributor alone stands for the coordinator
        pass
    return out


def _roster(work: ModuleType, main: Path, distributor: str) -> list[str]:
    """The repo's builders (W-16d0ef14): the names in its `.fabrik/session-agents.json` when that file — a regular
    file, read bounded — is a JSON object naming at least one builder; otherwise the names bound to this repository in
    the identity store that have a registered worktree under `.claude/worktrees/` (a task tree nobody is bound to is
    not a builder). The launcher (agents_up.sh) reads the same registry first; its fallback is every bound name, and
    a pane needs the worktree anyway, so the two agree wherever a pane can exist. Always minus the
    distributor, the ledger's merge owner and any `coordinator` / `*-coordinator` name."""
    skip = _coordinators(main, distributor)

    def builders(names: set[str]) -> list[str]:
        return sorted(
            n
            for n in names
            if _NAME_RE.fullmatch(n)
            and n not in skip
            and n != "coordinator"
            and not n.endswith("-coordinator")
        )

    reg = main / ".fabrik" / "session-agents.json"
    try:
        if stat.S_ISREG(reg.stat().st_mode):
            with reg.open("rb") as fh:
                data = json.loads(fh.read(REGISTRY_MAX).decode("utf-8", "replace"))
            if isinstance(data, dict):
                named = builders({v for v in data.values() if isinstance(v, str)})
                if named:
                    return named
    except (
        OSError,
        ValueError,
        RecursionError,
    ):  # a damaged registry (a deep nest included) falls back
        pass
    bound: set[str] = set()
    try:
        who = _load("whoami_agent")
        for row in who._rows(who.store_path()):
            top = str(row.get("toplevel") or "").rstrip("/")
            top = top[: -len("/.git")] if top.endswith("/.git") else top
            # this repository by PATH — a same-named clone elsewhere on the box binds nothing here; a row whose
            # path cannot resolve (a NUL, a symlink loop) is skipped alone, never the whole roster
            try:
                here = bool(top) and Path(top).resolve() == main
            except (OSError, ValueError, RuntimeError):
                continue
            if here and isinstance(row.get("name"), str):
                bound.add(row["name"])
    except Exception:  # noqa: BLE001 — no identity store: no bound builders
        return []
    base = (main / ".claude" / "worktrees").resolve()
    trees = {t.resolve().name for t in work._worktrees(main)[1:] if t.resolve().parent == base}
    return builders(bound & trees)


def collect(repo: Path) -> dict[str, Any]:
    """The whole view as data: ``{"main", "distributor", "agents": [{role, live, now, claim, done, next}]}``."""
    work, cr = _load("work"), _load("command_run")
    main = work._worktrees(repo.resolve())[0].resolve()
    if not work._has_store(main):
        raise FileNotFoundError(f"no work store in {main}")
    distributor = str(work._read_config(main).get("distributor") or "").strip()
    roles = _roster(work, main, distributor)
    trees = {r: (main / ".claude" / "worktrees" / r) for r in roles}
    trees = {r: (t.resolve() if t.is_dir() else main) for r, t in trees.items()}
    present = work._present({r: t for r, t in trees.items() if t != main})
    claims = work._live_claims(main)
    items = {i["id"]: i for i in work._iter_items(main) if isinstance(i.get("id"), str)}
    now = time.time()
    done = _merges(main, work._base_branch(main), roles, now)
    agents = []
    for role in roles:
        queue = work._worker_queues(main, {role: trees[role]}).get(role, [])
        queue = sorted(
            queue, key=lambda i: (work._priority(i), str(i.get("created") or ""), i["id"])
        )
        parked = sum(
            1
            for i in items.values()
            if i.get("owner") == role
            and i.get("status") in ("open", "blocked")
            and work._is_parked(i)
        )
        held = [(iid, c) for iid, c in claims.items() if c.get("agent") == role]
        claim = None
        if held:
            iid = sorted(held, key=lambda ic: float(ic[1].get("at") or 0))[-1][0]
            claim = {"id": iid, "title": str(items.get(iid, {}).get("title") or "")}
        agents.append(
            {
                "role": role,
                "live": None if present is None else role in present,
                "now": _now(cr, role, main),
                "claim": claim,
                "done": done[role],
                "next": {
                    "queued": len(queue),
                    "parked": parked,
                    "top": [
                        {
                            "id": i["id"],
                            "priority": work._priority(i),
                            "title": str(i.get("title") or ""),
                        }
                        for i in queue[:NEXT_SHOWN]
                    ],
                },
            }
        )
    return {"main": str(main), "distributor": distributor, "agents": agents}


# ── the box view: every repo under the /opt seam (W-7159f8e2) ─────────────────────────────────────
# Operator 2026-10-15: "which agents is active and working on what … for all repos". LIVENESS IS THE
# PROCESS TABLE, never an identity binding: whoami rows are written once at bind time and outlive their
# windows (measured 2026-10-15: 0 of 29 newest bindings had a live pid while 8 windows were up).
# COBRA: an agent working without a run record reads `idle` (a window with no running record) and one
# whose window died mid-run reads `stale`/`away` — the chips state what the records show, so the header
# keeps D-894's rule: no record, or an old one, means ask the agent.
RECENT_D = (
    7  # days a run record keeps a window-less agent listed; older ones are only counted dormant
)
_NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")


def _windows(opt: Path, work: ModuleType) -> list[dict]:
    """Every interactive `claude` process under ``opt`` as {repo, tree, agent}: ``tree`` is the worktree
    name or "" for the main checkout (any cwd under the repo that is not inside a named worktree)."""
    root = Path(os.environ.get("FABRIK_WORK_PROC") or "/proc")
    out: list[dict] = []
    try:
        entries = [e for e in root.iterdir() if e.name.isdigit()]
    except OSError:
        return out
    opt = opt.resolve()
    for entry in entries:
        try:
            if (entry / "comm").read_text(encoding="utf-8").strip() != "claude":
                continue
            argv = work._proc_argv(entry)
            if argv and work._argv_prints(argv):
                continue  # a `claude -p` child is no window (01M4PAJWV1)
            cwd = Path(os.readlink(entry / "cwd")).resolve()
        except OSError:
            continue
        try:  # its own try: an unreadable environ (another owner) only loses the NAME, never the window
            env = (entry / "environ").read_bytes().split(b"\0")
        except OSError:
            env = []
        try:
            rel = cwd.relative_to(opt).parts
        except ValueError:
            continue
        if not rel:
            continue
        tree = rel[3] if len(rel) >= 4 and rel[1:3] == (".claude", "worktrees") else ""
        if tree and (work._HARNESS_RE.fullmatch(tree) or not _NAME_RE.fullmatch(tree)):
            continue  # a harness (subagent isolation) tree is no agent's window, as work._workers rules
        agent = ""
        for kv in env:
            if kv.startswith(b"CLAUDE_AGENT="):
                val = kv.split(b"=", 1)[1].decode("utf-8", "replace").strip()
                agent = val if _NAME_RE.fullmatch(val) else ""
        out.append({"repo": rel[0], "tree": tree, "agent": agent})
    return out


def _records(cr: ModuleType, now: float) -> list[dict]:
    """Run records naming an agent and a repo_root, with a usable time: finite and not in the future
    (an hour of skew allowed) — a far-future stamp would otherwise read `working` for ever."""
    out = []
    for path in cr._state_dir().glob("*.json"):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
            ts = float(rec.get("updated_ts") or 0) if isinstance(rec, dict) else 0.0
        except (OSError, ValueError, TypeError, OverflowError):
            continue
        if not isinstance(rec, dict) or not math.isfinite(ts) or ts > now + 3600:
            continue
        if (
            _NAME_RE.fullmatch(str(rec.get("agent") or ""))
            and isinstance(rec.get("repo_root"), str)
            and rec["repo_root"]
        ):
            out.append({**rec, "_ts": ts})
    return out


def _box_repo(
    name: str,
    main: Path,
    wins: list[dict],
    recs: list[dict],
    bound: set[str],
    work: ModuleType,
    now: float,
) -> dict[str, Any]:
    # the Repos tab's own test for a store (quota_dashboard._collect_work), not work._has_store's
    # config file: the two views of one repo must agree on whether it has work
    store = (main / ".fabrik" / "work").is_dir()
    mine = [r for r in recs if _under(Path(str(r["repo_root"])), main)]
    recent_recs = [r for r in mine if now - r["_ts"] <= RECENT_D * 86400]
    # who works in the MAIN checkout: the newest RECENT record there — an old one names nobody, so a
    # main window with no recent record stays "(unnamed)" rather than wearing a months-old name
    at_main = sorted(
        (r for r in recent_recs if Path(r["repo_root"]).resolve() == main), key=lambda r: r["_ts"]
    )
    main_agent = str(at_main[-1]["agent"]) if at_main else ""
    windows: dict[str, str] = {}  # agent -> how the window was named
    counts: dict[
        str, int
    ] = {}  # agent -> open windows (two windows in one main checkout read as 2)
    win_trees: dict[
        str, set[str]
    ] = {}  # agent -> the worktree names its windows sit in ("" = main)
    for w in wins:
        if w["agent"]:
            who, how = w["agent"], "env"
        elif w["tree"]:
            who, how = w["tree"], "worktree"
        elif main_agent:
            who, how = main_agent, "record"
        else:
            who, how = "(unnamed)", "none"
        windows.setdefault(who, how)
        counts[who] = counts.get(who, 0) + 1
        # a main-checkout window counts as "" — no marker name can match it, so a tree pause over the
        # agent's other windows reads `partial` (work.py's `_is_paused` never stops that window by tree)
        win_trees.setdefault(who, set()).add(w["tree"] or "")
    recent = {str(r["agent"]) for r in recent_recs}
    items: dict[str, dict] = {}
    claims: dict[str, dict] = {}
    if store:
        items = {i["id"]: i for i in work._iter_items(main) if isinstance(i.get("id"), str)}
        claims = work._live_claims(main)
    holders: dict[str, str] = {}
    for iid, c in sorted(claims.items(), key=lambda ic: float(ic[1].get("at") or 0)):
        if _NAME_RE.fullmatch(str(c.get("agent") or "")):
            holders[str(c["agent"])] = iid
    names = sorted(set(windows) | recent | set(holders))
    seen = {str(r["agent"]) for r in mine} | bound
    trees = {n: (main / ".claude" / "worktrees" / n) for n in names}
    trees = {n: (t.resolve() if t.is_dir() else main) for n, t in trees.items()}
    paused, has_config, honoured = _pause_support(work, main)
    queues = work._worker_queues(main, trees) if store and names else {}
    done: dict[str, dict] = {}
    if names:
        try:
            done = _merges(main, work._base_branch(main), names, now)
        except Exception:  # noqa: BLE001 — a repo with no base branch shows no merges, never a crash
            done = {}
    agents = []
    for n in names:
        running = [r for r in mine if r["agent"] == n and r.get("state") == "running"]
        best = max(running, key=lambda r: r["_ts"]) if running else None
        rec_now = _now_view(best, best["_ts"], main) if best else None
        if rec_now and not rec_now["stale"]:
            state = "working"
        elif n in windows:
            state = "idle"
        elif rec_now:
            state = "stale"
        else:
            state = "away"
        queue = sorted(
            queues.get(n, []),
            key=lambda i: (work._priority(i), str(i.get("created") or ""), i["id"]),
        )
        held = holders.get(n)
        agents.append(
            {
                "name": n,
                "window": n in windows,
                "windows": counts.get(n, 0),
                "named_from": windows.get(n, ""),
                "state": state,
                "now": rec_now,
                "claim": {"id": held, "title": str(items.get(held, {}).get("title") or "")}
                if held
                else None,
                "next": {
                    "queued": len(queue),
                    "top": [
                        {
                            "id": i["id"],
                            "priority": work._priority(i),
                            "title": str(i.get("title") or ""),
                        }
                        for i in queue[:NEXT_SHOWN]
                    ],
                },
                "merges": (done.get(n) or {}).get("merges", []),
                # only the main checkout's current agent — the one whose run record there is the newest of
                # the last 7 days, in any state (the same agent a nameless main window is named after) —
                # never every agent that once ran a command there
                "merge_owner": bool(main_agent) and n == main_agent,
                "paused": _pause_of(paused, n, win_trees.get(n, set())),
                "can_pause": has_config and bool(_NAME_RE.fullmatch(n)),
                "pause_honoured": honoured,
            }
        )
    return {
        "name": name,
        "main": str(main),
        "store": store,
        "agents": agents,
        "dormant": len(seen - set(names)),
    }


def _pause_of(paused: dict[str, dict], name: str, trees: set[str]) -> dict | None:
    """The pause covering an agent — its own name, else every paused tree its windows sit in — with
    the marker NAMES a resume must lift (W-7159f8e2 part 3). work.py's `_is_paused` is per WINDOW, so
    `partial` says when only some of the agent's windows are stopped, and `names` carries every
    marker that stops one: a resume lifting only the first would leave a window paused under a row
    that no longer reads paused."""
    keys = [name] if name in paused else sorted(t for t in trees if t in paused)
    if not keys:
        return None
    rec = paused[keys[0]]
    return {
        "name": keys[0],
        "names": keys,
        "partial": name not in paused and len(keys) < len(trees),
        "by": str(rec.get("by") or "?"),
        "at": rec.get("at") or None,
        "why": str(rec.get("why") or ""),
    }


def _pause_support(work: ModuleType, main: Path) -> tuple[dict[str, dict], bool, bool]:
    """(pauses, has_config, honoured) for one repo; never raises. ``has_config`` is work.py's own store
    test (a config.json), which `pause` requires; ``honoured`` is whether the repo's OWN synced
    work.py carries the verb — before its next governance sync a pause written there is ignored."""
    reader = getattr(work, "_paused", None)
    try:
        pauses = reader(main) if reader else {}
    except Exception:  # noqa: BLE001 — no pause information is today's behaviour, never a crash
        pauses = {}
    try:
        has_config = bool(work._has_store(main))
    except Exception:  # noqa: BLE001
        has_config = False
    # only a REGULAR file, read bounded (a FIFO would hang the whole box view — work.py's own
    # `_paused` guards its markers the same way), and the verb as a top-level def, never a comment
    honoured = False
    src = main / "scripts" / "work.py"
    try:
        if stat.S_ISREG(src.stat().st_mode):
            with src.open("rb") as fh:
                text = fh.read(WORK_PY_MAX).decode("utf-8", "replace")
            honoured = re.search(r"^def cmd_pause\(", text, re.M) is not None
    except OSError:
        honoured = False
    return pauses, has_config, honoured


def collect_box(opt: Path) -> dict[str, Any]:
    """Every repo under ``opt`` that keeps a work store or has an agent, with its agents (W-7159f8e2)."""
    work, cr, who = _load("work"), _load("command_run"), _load("whoami_agent")
    opt = opt.resolve()
    now = time.time()
    with work._hook_git_budget():
        wins = _windows(opt, work)
        recs = _records(cr, now)
        bound: dict[str, set[str]] = {}
        for row in who._rows(who.store_path()):
            top = str(row.get("toplevel") or "").rstrip("/")
            top = top[: -len("/.git")] if top.endswith("/.git") else top
            if _NAME_RE.fullmatch(str(row.get("name") or "")) and top:
                bound.setdefault(Path(top).name, set()).add(str(row["name"]))
        names = {p.parent.parent.name for p in opt.glob("*/.fabrik/work")}
        names |= {w["repo"] for w in wins}
        for r in recs:
            try:
                rel = (
                    Path(r["repo_root"]).resolve().relative_to(opt).parts
                )  # never "": _records drops it
            except ValueError:
                continue
            if rel and now - r["_ts"] <= RECENT_D * 86400:
                names.add(rel[0])
        repos = []
        for name in sorted(names):
            main = opt / name
            if not main.is_dir() or main.is_symlink():
                continue
            try:
                entry = _box_repo(
                    name,
                    main.resolve(),
                    [w for w in wins if w["repo"] == name],
                    recs,
                    bound.get(name, set()),
                    work,
                    now,
                )
            except Exception as exc:  # noqa: BLE001 — one repo's failure is its own error row
                entry = {
                    "name": name,
                    "main": str(main),
                    "store": None,
                    "agents": [],
                    "dormant": 0,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            repos.append(entry)
    return {"opt": str(opt), "repos": repos}


def render(data: dict[str, Any]) -> str:
    now = time.time()
    lines = [
        "## AGENTS — NOW / DONE / NEXT (D-880; derived from run records, the work store and merges —"
        " no record, or an old one, means ask the agent)"
    ]
    for a in data["agents"]:
        live = {True: "window up", False: "no window", None: "liveness unknown"}[a["live"]]
        block = [f"### {a['role']} — {live}"]
        n = a["now"]
        if n:
            where = f" in {n['repo']}" if n["repo"] else ""
            root = (
                f" (under /{n['stack_root']})"
                if n["stack_root"] and n["stack_root"] != n["command"]
                else ""
            )
            block.append(
                f"- NOW: /{n['command']}{root}{where} · phase {n['phase']}/{n['phases']} ({_cut(n['title'], 40)})"
                f" · {_cut(n['surface'], TITLE_CUT)} · updated {_age(n['updated_ts'], now)}"
                + (
                    f" · STALE (>{STALE_H} h — likely a dead session; ask the agent)"
                    if n["stale"]
                    else ""
                )
            )
        else:
            block.append("- NOW: no running record")
        if a["claim"]:
            block.append(f"- HOLDS: {a['claim']['id']} — {_cut(a['claim']['title'], TITLE_CUT)}")
        merges = a["done"]["merges"]
        if merges:
            for m in merges:
                block.append(
                    f"- DONE: {m['sha']} {_age(m['ts'], now)} · item {m['item'] or 'none'}"
                )
        else:
            block.append("- DONE: no merges found")
        block.append(f"- DONE 24h: {a['done']['items_24h']} item(s) merged")
        nx = a["next"]
        block.append(f"- NEXT: {nx['queued']} queued, {nx['parked']} parked")
        for i in nx["top"]:
            block.append(f"  - {i['id']} P{i['priority']} {_cut(i['title'], TITLE_CUT)}")
        text, kept = "", 0
        for line in block:
            if len(text) + len(line) + 1 > ROLE_CUT:
                break
            text += line + "\n"
            kept += 1
        if kept < len(block):
            text += f"  … {len(block) - kept} more line(s): python3 scripts/agent_status.py\n"
        lines.append(text.rstrip("\n"))
    out = "\n".join(lines)
    if len(out) > TOTAL_CUT:
        out = out[: TOTAL_CUT - 60].rsplit("\n", 1)[0] + "\n… cut: python3 scripts/agent_status.py"
    return out


def _session_start(repo: Path) -> int:
    """The SessionStart hook: the table for the distributor only; every failure is one line, rc 0."""
    try:
        work = _load("work")
        try:
            raw = sys.stdin.read() if not sys.stdin.isatty() else ""
            payload = json.loads(raw) if raw.strip() else {}
        except ValueError:
            payload = {}
        sid = str(payload.get("session_id") or "") if isinstance(payload, dict) else ""
        main = work._worktrees(repo.resolve())[0].resolve()
        if not work._has_store(main) or work._print_mode():
            return 0
        distributor = str(work._read_config(main).get("distributor") or "").strip()
        if not distributor:
            return 0
        agent = work._agent_name(session=sid)
        if not agent:
            print(
                "agent status: identity unknown — bind this window with `python3 scripts/whoami_agent.py "
                "--as <name>` to see every agent's NOW/DONE/NEXT"
            )
            return 0
        if agent != distributor:
            return 0
        print(render(collect(main)))
    except Exception as exc:  # a SessionStart hook never blocks a session
        print(f"agent status unavailable: {type(exc).__name__}: {_cut(exc, 200)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", default=".", help="any tree of the repository (default: the cwd)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--json", action="store_true", help="the full data as one JSON document")
    mode.add_argument(
        "--session-start", action="store_true", help="the coordinator's SessionStart hook"
    )
    ap.add_argument(
        "--all",
        action="store_true",
        help="with --json: every repo under --opt and its agents (the dashboard's Agents block)",
    )
    ap.add_argument(
        "--opt",
        default=os.environ.get("FABRIK_OPT_DIR") or "/opt",
        help="the repos' parent (default: $FABRIK_OPT_DIR, else /opt)",
    )
    args = ap.parse_args(argv)
    repo = Path(args.repo)
    if args.session_start:
        return _session_start(repo)
    if args.all:
        if not args.json:
            ap.error("--all needs --json")
        print(json.dumps(collect_box(Path(args.opt))))
        return 0
    try:
        data = collect(repo)
    except FileNotFoundError as exc:
        print(f"agent_status: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(data) if args.json else render(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
