#!/usr/bin/env python3
# AFTER-EDIT: .windsurf/rules/core/62-using-subagents.md, docs/workstation/claude-account-rotation.md
"""dispatch_headroom — the seat budget for a native fan-out, from the BOX and the FLEET, not from prose.

D-186/D-188 size a fan-out by the surface's independent units with a floor of three. The operator's
full objective (2026-09-08) binds five things at once: the maximum count of viable seats, box
capacity without OOMs, the fastest finish, affordable tokens, and the right model per role. Prose
cannot hold five constraints in an agent's head at dispatch time; this prints the number.

    python3 scripts/sysadmin/dispatch_headroom.py --units 6            # read-only seats
    python3 scripts/sysadmin/dispatch_headroom.py --units 6 --heavy    # seats that run pytest/builds
    python3 scripts/sysadmin/dispatch_headroom.py --units 6 --json

seats = min(units raised to the floor, CONCURRENCY_CAP, box_cap, quota_cap). The floor (3, D-188)
raises the UNIT count; it never raises past a HARD cap — a box with room for two heavy seats gets
two, with the reason, never three. A native seat runs INSIDE its parent claude process, so its
memory is its TOOL subprocesses — and a "read-only" finder still runs pytest through Bash (measured
2026-09-08 at 1.19 GB max RSS), so the box bound applies to every seat: 2 GB planned per `--heavy`
seat, 1 GB per read-only seat. Seats already dispatched by OTHER live sessions on this box are
subtracted first (their run records carry `seats` per round), so three sessions cannot each take
the whole box in the same minute.

Every probe fails SOFT and says so: an unreadable /proc, a rotation script that raises, or an
unidentifiable active account prints the floor with the reason — never a silent 20, and never
"cool" by default.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

FLOOR = 3
# CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS ?? 20 — read out of the CLI bundle v2.1.263 (core/62
# § Parallelism (Runtime A)); a seat past it is REFUSED, not queued. A non-numeric value must not
# kill the script at import ("fails SOFT" is the contract): it falls back to 20 with a reason.
_CAP_RAW = os.getenv("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS")
try:
    CONCURRENCY_CAP = int(_CAP_RAW) if _CAP_RAW else 20
    CAP_NOTE = ""
except ValueError:
    CONCURRENCY_CAP = 20
    CAP_NOTE = f"CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS={_CAP_RAW!r} is not a number — using 20"
# Planning figures, measured on this box 2026-09-08 with /usr/bin/time: `pytest tests/enforcement`
# (1035 tests) peaks at 1.19 GB, `mypy` at 120 MB, `ruff` at 94 MB, the corpus render at 19 MB.
# 2 GB per heavy seat is 1.7x the largest thing measured; 1 GB per read-only seat covers a finder
# that runs a test slice through Bash. CPU: one core per seat — `ruff` alone took 14.5 cores for
# 60 ms, so a per-seat CPU share is not a planning figure; the CPU term only refuses to put seats
# onto a box whose load already fills its cores.
HEAVY_GB_PER_SEAT = 2.0
LIGHT_GB_PER_SEAT = 1.0
ROTATE = Path(__file__).resolve().parent / "claude_rotate.py"
RUNS_DIR = Path.home() / ".claude" / "state" / "command-runs"
# a sibling's run record counts as LIVE for this purpose when it is `running` and was touched
# within this window — an abandoned record (the Stop hook's stale bound is 12 h) must not hold
# the box hostage
SIBLING_FRESH_S = 30 * 60

# model tiering by ROLE — the operator's four names, one job each (canonical: core/62). Fable is
# METERED (the CLI bundle: "Fable 5 requires usage credits"), not a subscription window — it is
# NOT visible to the quota probe below; a Fable seat that refuses falls back to Opus BY NAME and
# the fallback is recorded, never silent.
TIERS = {
    "fable": (
        "orchestrator/adjudicator + the final validation's authoritative seat; never a routine "
        "finder — METERED usage credits, not subscription quota: check before the run, fall back "
        "to Opus by name"
    ),
    "opus": "the authoritative pass (>=1 per review) + design-heavy never-route coding",
    "sonnet": "breadth — one seat per independent unit; default never-route coder",
    "haiku": "trivial-mechanical checks (grep-able classes, format, inventory); never codes",
}


def box() -> dict:
    """MemAvailable, the commit headroom, cores, 1-min load — from /proc, fail-soft. Raw GB kept
    for the arithmetic; rounding is for display only."""
    out: dict = {"ok": True}
    try:
        mem = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, _, v = line.partition(":")
            mem[k] = int(v.split()[0])
        out["mem_available_gb"] = mem["MemAvailable"] / 1024 / 1024
        out["mem_total_gb"] = mem["MemTotal"] / 1024 / 1024
        # the quantity that reaches zero BEFORE the OOM killer runs; MemAvailable ignores it
        if "CommitLimit" in mem and "Committed_AS" in mem:
            out["commit_headroom_gb"] = (
                max(mem["CommitLimit"] - mem["Committed_AS"], 0) / 1024 / 1024
            )
        out["cores"] = os.cpu_count() or 1
        out["load1"] = os.getloadavg()[0]
    except (OSError, KeyError, ValueError, IndexError) as exc:
        out.update(ok=False, why=f"box probe failed: {exc}")
    return out


def quota() -> dict:
    """The active account's hottest window + eligible-standby count, via claude_rotate.py. The
    drain band is read from the picture, not re-hardcoded, so the two cannot drift."""
    try:
        raw = subprocess.run(
            [sys.executable, str(ROTATE), "--status", "--json"],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        ).stdout
        pic = json.loads(raw).get("picture") or {}
        accounts = pic.get("accounts") or []
        active = pic.get("active")
        act = next((a for a in accounts if a.get("email") == active), None)
        hottest = (
            max(float(act.get("session_pct") or 0), float(act.get("weekly_pct") or 0))
            if act
            else None
        )
        # `eligible` is the rotation's STANDBY state; the account doing the work is `active`
        eligible = sum(1 for a in accounts if a.get("state") == "eligible")
        band = float((pic.get("thresholds") or {}).get("drain_band") or 85.0)
        return {
            "ok": True,
            "active": active,
            "hottest_pct": hottest,
            "eligible": eligible,
            "hold": bool(pic.get("hold")),
            "drain_band": band,
        }
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError) as exc:
        return {"ok": False, "why": f"quota probe failed: {exc}"}


def siblings(now: float | None = None, runs_dir: Path = RUNS_DIR) -> dict:
    """Seats OTHER live sessions on this box have dispatched — the sum of the last round's `seats`
    over run records that are `running` and fresh. Three sessions reading the same free memory in
    the same minute would otherwise each take all of it (TOCTOU on the box). Fail-soft: an
    unreadable record counts 0 and is named."""
    now = time.time() if now is None else now
    out: dict = {"ok": True, "seats": 0, "sessions": 0, "skipped": []}
    try:
        for p in runs_dir.glob("*.json"):
            try:
                rec = json.loads(p.read_text())
            except (OSError, ValueError):
                out["skipped"].append(p.name)
                continue
            if rec.get("state") != "running":
                continue
            ts = float(rec.get("updated_ts") or 0)
            if now - ts > SIBLING_FRESH_S:
                continue
            rounds = rec.get("rounds") or []
            seats = int((rounds[-1] if rounds else {}).get("seats") or 0)
            if seats > 0:
                out["seats"] += seats
                out["sessions"] += 1
    except OSError as exc:
        out.update(ok=False, why=f"sibling probe failed: {exc}")
    return out


def budget(units: int, heavy: bool, b: dict, q: dict, s: dict | None = None) -> dict:
    s = s or {"ok": True, "seats": 0, "sessions": 0, "skipped": []}
    reasons: list[str] = []
    if CAP_NOTE:
        reasons.append(CAP_NOTE)
    caps = {"units": max(units, 0), "concurrency_cap": CONCURRENCY_CAP}
    per_seat = HEAVY_GB_PER_SEAT if heavy else LIGHT_GB_PER_SEAT
    if b.get("ok"):
        mem = b["mem_available_gb"]
        if "commit_headroom_gb" in b:
            mem = min(mem, b["commit_headroom_gb"])
        by_mem = int(mem // per_seat)
        by_cpu = max(int(b["cores"] - math.ceil(b["load1"])), 0)
        taken = int(s.get("seats") or 0)
        cap = max(min(by_mem, by_cpu) - taken, 0)
        caps["box_cap"] = cap
        reasons.append(
            f"box allows {cap} {'heavy' if heavy else 'read-only'} seats "
            f"(mem {mem:.1f}GB/{per_seat}GB={by_mem}, cores {b['cores']}-load {b['load1']:.1f}={by_cpu}"
            + (
                f", minus {taken} seat(s) live in {s.get('sessions')} sibling session(s)"
                if taken
                else ""
            )
            + ")"
        )
    else:
        caps["box_cap"] = FLOOR
        reasons.append(f"{b.get('why')} — box unknown, held at the floor")
    if not s.get("ok"):
        reasons.append(f"{s.get('why')} — sibling seats unknown, not subtracted")
    if q.get("ok"):
        if q["hold"]:
            caps["quota_cap"] = 0
            reasons.append("fleet-exhausted HOLD is on — dispatch nothing until relief")
        else:
            band = float(q.get("drain_band") or 85.0)
            unknown = q["hottest_pct"] is None
            hot = unknown or q["hottest_pct"] >= band
            if hot:
                caps["quota_cap"] = FLOOR
                reasons.append(
                    (
                        f"quota: the active account could not be identified ({q['active']!r}) — "
                        "treated as HOT, never as cool"
                        if unknown
                        else f"quota: active {q['active']} is at {q['hottest_pct']}% "
                        f"(>= drain band {band}%)"
                    )
                    + " — run the FLOOR, sweep the rest next round"
                )
            if q["eligible"] == 0:
                reasons.append(
                    "quota: NO eligible standby — the active account has no fallback; the round "
                    "runs, but a fan-out that exhausts it stops the fleet, so keep the seats you "
                    "dispatch proportionate to its remaining window"
                )
    else:
        caps["quota_cap"] = FLOOR
        reasons.append(f"{q.get('why')} — quota unknown, held at the floor")
    # The floor raises the UNIT-derived count (D-188: never solo, never two) — it never overrides a
    # HARD cap. The first draft raised any sub-floor result back to 3, including a box_cap of 0, so
    # "--heavy" on a box with no room printed 3 heavy seats: the exact OOM this tool exists to
    # prevent (author-blind round 1, 2026-09-08). Now: units up to the floor first, then the caps.
    if caps["units"] < FLOOR:
        reasons.append(
            f"units={caps['units']} raised to the floor of {FLOOR} — three seats on DIFFERENT angles "
            f"over the whole surface (D-188)"
        )
        caps["units"] = FLOOR
    seats = min(caps.values())
    if seats < FLOOR:
        hard = [k for k, v in caps.items() if v == seats and k != "units"]
        reasons.append(
            f"below the floor because a HARD cap binds ({', '.join(hard)}={seats}) — "
            + (
                "dispatch nothing until relief"
                if seats == 0 and "quota_cap" in hard
                else "wait for the box or the sibling rounds to finish; never dispatch past a hard cap"
            )
        )
    return {"seats": seats, "caps": caps, "reasons": reasons}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    # REQUIRED: a default of FLOOR let a caller who forgot the flag read a plausible "SEATS: 3" as a
    # constrained verdict instead of "you never said how big the surface is" (round-1 finding).
    ap.add_argument("--units", type=int, required=True, help="independent units in the surface")
    ap.add_argument("--heavy", action="store_true", help="each seat runs tests/builds/renders")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    b, q, s = box(), quota(), siblings()
    r = budget(a.units, a.heavy, b, q, s)
    r.update(box=b, quota=q, siblings=s, tiers=TIERS, units=a.units, heavy=a.heavy)
    if a.json:
        print(json.dumps(r, indent=2, default=str))
        return 0
    print(
        f"SEATS: {r['seats']}  (units={a.units}, {'heavy' if a.heavy else 'read-only'}; "
        f"caps {r['caps']})"
    )
    for line in r["reasons"]:
        print(f"  - {line}")
    if b.get("ok"):
        print(
            f"  box: {b['mem_available_gb']:.1f}/{b['mem_total_gb']:.1f} GB available"
            + (
                f", commit headroom {b['commit_headroom_gb']:.1f} GB"
                if "commit_headroom_gb" in b
                else ""
            )
            + f", load {b['load1']:.1f} on {b['cores']} cores"
        )
    if q.get("ok"):
        print(
            f"  quota: active {q['active']} hottest {q['hottest_pct']}%, eligible standbys "
            f"{q['eligible']}, hold={q['hold']}, drain band {q.get('drain_band')}%"
        )
    print(
        "  record what you dispatch: python3 scripts/command_run.py round --seats <n> "
        "--findings <n> --classes-swept … --classes-new …"
    )
    print("  tiers (model by the seat's JOB; the per-dispatch token is Agent(model=...)):")
    for k, v in TIERS.items():
        print(f"    {k:7} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
