#!/usr/bin/env python3
# AFTER-EDIT: .windsurf/rules/core/62-using-subagents.md, docs/workstation/claude-account-rotation.md
"""dispatch_headroom — the seat budget for a native fan-out, from the BOX and the FLEET, not from prose.

D-186/D-188 size a fan-out by the surface's independent units with a floor of three. The operator's
full objective (2026-09-08) binds five things at once: the maximum count of viable seats, box
capacity without OOMs, the fastest finish, affordable tokens, and the right model per role. Prose
cannot hold five constraints in an agent's head at dispatch time; this prints the number.

    python3 scripts/sysadmin/dispatch_headroom.py --units 6            # read-only seats
    python3 scripts/sysadmin/dispatch_headroom.py --units 6 --heavy    # seats that run pytest/builds
    python3 scripts/sysadmin/dispatch_headroom.py --json

seats = min(units, CONCURRENCY_CAP, box_cap, quota_cap), never below the floor of 3 unless the
fleet is on hold. A native seat runs INSIDE its parent claude process — its memory is its TOOL
subprocesses, so `--heavy` (each seat runs a test suite, a build, a render) is what the box bound
applies to; read-only seats are bounded by the CLI's per-session cap and the quota alone.

Every probe fails SOFT and says so: an unreadable /proc or a rotation script that raises prints the
floor with the reason, never a silent 20.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

FLOOR = 3
# CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS ?? 20 — read out of the CLI bundle v2.1.263 (core/62
# § Parallelism (Runtime A)); a seat past it is REFUSED, not queued.
CONCURRENCY_CAP = int(os.getenv("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS") or 20)
# a heavy seat's tool subprocesses (pytest, node build, corpus render) measured 2026-09-08 at
# ~0.5-2 GB each; 2 GB is the conservative planning figure, 1.5 cores the CPU share.
HEAVY_GB_PER_SEAT = 2.0
HEAVY_CORES_PER_SEAT = 1.5
# quota: floor at >=85% on the active account's hottest window (the rotation's own drain_band), or
# when NO standby is eligible. The picture's `eligible` counts STANDBYS — the active account carries
# state=active — so the first draft's `< 2` fired with a 7%-used active and one fresh standby and
# turned the operator's MAXIMUM into a permanent 3 (orchestrator's own sweep + two seats, 2026-09-08).
QUOTA_HOT_PCT = 85.0
MIN_STANDBYS = 1
ROTATE = Path(__file__).resolve().parent / "claude_rotate.py"

# model tiering by ROLE — the operator's four names, one job each (canonical: core/62)
TIERS = {
    "fable": "orchestrator/adjudicator + the final validation's authoritative seat; never a routine finder",
    "opus": "the authoritative pass (>=1 per review) + design-heavy never-route coding",
    "sonnet": "breadth — one seat per independent unit; default never-route coder",
    "haiku": "trivial-mechanical checks (grep-able classes, format, inventory); never codes",
}


def box() -> dict:
    """MemAvailable, cores, 1-min load — from /proc, fail-soft."""
    out: dict = {"ok": True}
    try:
        mem = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, _, v = line.partition(":")
            mem[k] = int(v.split()[0])
        out["mem_available_gb"] = round(mem["MemAvailable"] / 1024 / 1024, 1)
        out["mem_total_gb"] = round(mem["MemTotal"] / 1024 / 1024, 1)
        out["cores"] = os.cpu_count() or 1
        out["load1"] = os.getloadavg()[0]
    except (OSError, KeyError, ValueError, IndexError) as exc:
        out.update(ok=False, why=f"box probe failed: {exc}")
    return out


def quota() -> dict:
    """The active account's hottest window + eligible-account count, via claude_rotate.py."""
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
        eligible = sum(1 for a in accounts if a.get("state") == "eligible")
        return {
            "ok": True,
            "active": active,
            "hottest_pct": hottest,
            "eligible": eligible,
            "hold": bool(pic.get("hold")),
        }
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError) as exc:
        return {"ok": False, "why": f"quota probe failed: {exc}"}


def budget(units: int, heavy: bool, b: dict, q: dict) -> dict:
    reasons: list[str] = []
    caps = {"units": max(units, 0), "concurrency_cap": CONCURRENCY_CAP}
    if heavy:
        if b.get("ok"):
            by_mem = int(b["mem_available_gb"] // HEAVY_GB_PER_SEAT)
            by_cpu = int(max(b["cores"] - b["load1"], 0) // HEAVY_CORES_PER_SEAT)
            caps["box_cap"] = max(min(by_mem, by_cpu), 0)
            reasons.append(
                f"heavy seats: box allows {caps['box_cap']} "
                f"(mem {b['mem_available_gb']}GB/{HEAVY_GB_PER_SEAT}GB={by_mem}, "
                f"cpu ({b['cores']}-{b['load1']:.1f})/{HEAVY_CORES_PER_SEAT}={by_cpu})"
            )
        else:
            caps["box_cap"] = FLOOR
            reasons.append(f"{b.get('why')} — heavy seats held at the floor")
    if q.get("ok"):
        if q["hold"]:
            caps["quota_cap"] = 0
            reasons.append("fleet-exhausted HOLD is on — dispatch nothing until relief")
        else:
            hot = q["hottest_pct"] is not None and q["hottest_pct"] >= QUOTA_HOT_PCT
            thin = q["eligible"] < MIN_STANDBYS
            if hot or thin:
                caps["quota_cap"] = FLOOR
                why = " and ".join(
                    w
                    for w, on in (
                        (
                            f"active {q['active']} is at {q['hottest_pct']}% (>= {QUOTA_HOT_PCT}%)",
                            hot,
                        ),
                        (f"no eligible standby ({q['eligible']} < {MIN_STANDBYS})", thin),
                    )
                    if on
                )
                reasons.append(f"quota: {why} — run the FLOOR, sweep the rest next round")
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
                else "run read-only seats instead (no box bound), or wait for the box"
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
    b, q = box(), quota()
    r = budget(a.units, a.heavy, b, q)
    r.update(box=b, quota=q, tiers=TIERS, units=a.units, heavy=a.heavy)
    if a.json:
        print(json.dumps(r, indent=2, default=str))
        return 0
    print(
        f"SEATS: {r['seats']}  (units={a.units}, {'heavy' if a.heavy else 'read-only'}; caps {r['caps']})"
    )
    for line in r["reasons"]:
        print(f"  - {line}")
    if b.get("ok"):
        print(
            f"  box: {b['mem_available_gb']}/{b['mem_total_gb']} GB available, "
            f"load {b['load1']:.1f} on {b['cores']} cores"
        )
    if q.get("ok"):
        print(
            f"  quota: active {q['active']} hottest {q['hottest_pct']}%, eligible {q['eligible']}, hold={q['hold']}"
        )
    print("  tiers (model by the seat's JOB):")
    for k, v in TIERS.items():
        print(f"    {k:7} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
