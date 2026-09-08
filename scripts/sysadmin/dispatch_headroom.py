#!/usr/bin/env python3
# AFTER-EDIT: .windsurf/rules/core/62-using-subagents.md, docs/workstation/claude-account-rotation.md, commands/_fragments/subagents-core.md
"""dispatch_headroom — the seat budget for a native fan-out, from the BOX and the FLEET, not from prose.

D-186/D-188 size a fan-out by the surface's independent units with a floor of three. The operator's
full objective (2026-09-08) binds five things at once: the maximum count of viable seats, box
capacity without OOMs, the fastest finish, affordable tokens, and the right model per role. Prose
cannot hold five constraints in an agent's head at dispatch time; this prints the number.

    python3 scripts/sysadmin/dispatch_headroom.py --units 6            # read-only seats
    python3 scripts/sysadmin/dispatch_headroom.py --units 6 --heavy    # seats that run pytest/builds
    python3 scripts/sysadmin/dispatch_headroom.py --units 6 --json

seats = min(units × angles + the Opus seat(s), CONCURRENCY_CAP, box_cap, quota_cap) — D-191: every
unit wants one Sonnet breadth seat and one Haiku mechanical seat (`--mechanical <M>`, 0 on a judgement
surface), plus one Opus seat per risky unit and at least one; `full_mix` pads to the floor (3, D-188)
with real seats and `trim` cuts for coverage when a cap binds. The floor never raises past a HARD
cap — a box with room for two heavy seats gets two, with the reason, never three. A native seat runs INSIDE its parent claude process, so its
memory is its TOOL subprocesses — and a "read-only" finder still runs pytest through Bash (measured
2026-09-08 at 1.19 GB max RSS), so the box bound applies to every seat: 2 GB planned per `--heavy`
seat, 1 GB per read-only seat. Seats already dispatched by OTHER live sessions on this box are
subtracted first (their DISPATCH stamps, `command_run.py dispatch --seats`), so three sessions cannot each take
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
import re
import subprocess
import sys
import time
from pathlib import Path

FLOOR = 3
# D-191 (operator, three times: "maximum count of viable and useful subagents"): the BOX is the
# ceiling and the units are the PARTITION. Every unit gets one seat per ANGLE — breadth (Sonnet),
# mechanical (Haiku) — plus the authoritative Opus seats (one per risky unit, at least one). A
# seat is "useful" when its brief is a distinct unit x angle; the box, the CLI cap and the quota
# are what make it "viable". Before this, `units` capped the count: the box allowed 23 and the
# rule dispatched 3 (measured 2026-09-08).
# Three angles, not two: a RISKY unit also carries an authoritative Opus seat, so it has three
# seats (cost 8) — the Opus and Sonnet briefs on it share the unit but not the angle (authoritative
# re-derivation vs breadth). A mechanical seat is grep-shaped and therefore GLOBAL: when the budget
# trims below one per unit, each remaining Haiku seat sweeps ONE grep-able class across every
# unit; a grounding or adjudication unit has no grep-able angle at all (`--mechanical 0`).
ANGLES = {"breadth": "sonnet", "mechanical": "haiku", "authoritative": "opus"}
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
# A sibling's seats are RESERVED from their DISPATCH stamp for the life of a seat: measured
# 2026-09-08 on 245 seat transcripts since 09-07 (first to last line — a lower bound on the true
# span), median 550 s, p90 1085 s, p95 1354 s; a 15-minute window left 16 % of seats, the longest
# ones, unreserved (round-4 finding). 25 minutes covers the p95 with the launch/return margin. The box probe sees a running
# seat's tools too, so late in a seat's life this double-counts — accepted, because the floor
# clause below means a reservation can never starve a session the box has room for.
SIBLING_FRESH_S = 25 * 60

# Price multipliers, operator ruling 2026-09-08 (D-190): haiku 1x · sonnet 2x · opus 5x · fable 10x.
# "Affordable" is a NUMBER: cost = sum(seats x multiplier) in haiku-units. Breadth on Sonnet costs 2
# per seat; the same seat on Opus costs 5; a Fable adjudicator costs 10 — so the cheapest mix that
# still meets the D-186 floor is one Opus authoritative seat plus Sonnet breadth.
PRICE = {"haiku": 1, "sonnet": 2, "opus": 5, "fable": 10}
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
    "haiku": "the mechanical seat (grep-able classes, format, inventory) — one per unit, class-wide when trimmed, none on a judgement surface; never codes",
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
        # a reading of None is UNKNOWN, never 0 % — `or 0` priced an active account with no
        # reading as cool and set no quota cap at all (round-5 finding)
        vals = (
            [
                float(v)
                for v in (act.get("session_pct"), act.get("weekly_pct"))
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            ]
            if act
            else []
        )
        hottest = max(vals) if vals else None
        # `eligible` is the rotation's STANDBY state; the account doing the work is `active`. A
        # standby that is ITSELF in the drain band is no fallback — count the COOL ones (round-6
        # finding: the only standby sat at exactly the band and the caution stayed silent)
        eligible_raw = sum(1 for a in accounts if a.get("state") == "eligible")
        # a standby the picker did not grade (`in_drain_band` absent) is UNKNOWN, never cool —
        # the same direction `hottest_pct is None` takes for the active account (round-7 finding)
        eligible = sum(
            1 for a in accounts if a.get("state") == "eligible" and a.get("in_drain_band") is False
        )
        band = float((pic.get("thresholds") or {}).get("drain_band") or 85.0)
        return {
            "ok": True,
            "active": active,
            "hottest_pct": hottest,
            "eligible": eligible,
            "eligible_raw": eligible_raw,
            "active_in_band": bool(act.get("in_drain_band")) if act else None,
            "hold": bool(pic.get("hold")),
            "drain_band": band,
        }
    except Exception as exc:  # noqa: BLE001 — a malformed picture (a row that is not a dict, a
        # list where a dict was promised) crashed the CLI through main() (round-5 finding);
        # every probe fails SOFT to the floor and says why
        return {"ok": False, "why": f"quota probe failed: {exc}"}


_SCRIPTS_DIR = str(Path(__file__).resolve().parents[1])


def _import_command_run():
    """`scripts/command_run.py` — the authority on record names; inserted on sys.path ONCE."""
    if _SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, _SCRIPTS_DIR)
    import command_run  # noqa: PLC0415

    return command_run


def _safe_stem(sid: str) -> str:
    """The FILENAME `command_run.py` writes for a sid (`_safe_sid`) — the own-record test compares
    stems, and a raw sid with a dot or a slash never matched its own file (round-5 finding)."""
    try:
        return str(_import_command_run()._safe_sid(sid))
    except Exception:  # noqa: BLE001
        return sid


def own_session_id() -> tuple[str, str]:
    """The record `command_run.py` keys on for THIS session — derived by command_run.py ITSELF
    (`_session_id`: explicit → CLAUDE_SESSION_ID → CLAUDE_CODE_SESSION_ID → the repo-scoped
    `nosession-<repo>`), never a second copy of that ladder: a copy without the nosession
    fallback returned "" in an id-less shell and the own record was counted again (round-5
    finding). Fail-soft: if command_run.py cannot be imported, the env ladder alone — returned
    as `(sid, source)` with source "command_run" or "env", never a module global (round-7 finding:
    the global ratcheted to "env" on one failed import and never reset in that process)."""
    try:
        return str(_import_command_run()._session_id(None) or "").strip(), "command_run"
    except Exception:  # noqa: BLE001 — a probe fails soft, and SAYS so (round-6 finding)
        sid = (
            os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("CLAUDE_CODE_SESSION_ID") or ""
        ).strip()
        return sid, "env"


def siblings(
    now: float | None = None, runs_dir: Path = RUNS_DIR, exclude_sid: str | None = None
) -> dict:
    """Seats OTHER live sessions on this box have dispatched — the fresher of each running
    record's DISPATCH stamp and its last round's `seats` (the larger wins when both are fresh).
    The caller's OWN record is excluded (`exclude_sid`, default this session): a session that
    subtracted its own stamp sized round N+1 against a box it had emptied itself (round-4
    finding). Three sessions reading the same free memory in the same minute would otherwise each
    take all of it (TOCTOU on the box). Fail-soft: an unreadable record counts 0 and is named."""
    now = time.time() if now is None else now
    own, own_source = own_session_id() if exclude_sid is None else (exclude_sid, "explicit")
    own_stem = _safe_stem(own) if own else ""
    out: dict = {
        "ok": True,
        "seats": 0,
        "sessions": 0,
        "unrecorded": 0,
        "skipped": [],
        "excluded_own": False,
        "own_source": own_source,
    }
    try:
        for p in runs_dir.glob("*.json"):
            if own_stem and p.stem == own_stem:
                out["excluded_own"] = True
                continue
            try:
                rec = json.loads(p.read_text())
                if rec.get("state") != "running":
                    continue
                # the DISPATCH stamp (command_run.py dispatch --seats, written before the seats
                # are sent) is the reservation; a record without one falls back to its last
                # round's seats at its last touch — which is written AFTER the seats returned, so
                # it reserves nothing while they run (round-3 finding: the guard was inert)
                disp = rec.get("dispatch")
                rounds = rec.get("rounds") or []
                if not isinstance(rounds, list):
                    raise TypeError("rounds is not a list")
                last = rounds[-1] if rounds else {}
                disp_seats = disp.get("seats") if isinstance(disp, dict) else None
                released = isinstance(disp, dict) and bool(disp.get("released"))
                if not released and not disp_seats and not last.get("seats"):
                    # running, no seat figure at all: no stamp, an EMPTY stamp, or a round row at
                    # the CLI's own default (`round --seats` 0 = "not recorded") — a LOWER bound,
                    # counted and named, never a known zero (round-6 finding); a RELEASE marker
                    # (seats 0, released) is a known zero and skips nothing
                    out["unrecorded"] += 1
                    continue
                # the DISPATCH stamp (written before the seats went out, released when they
                # returned) is the reservation; the round row is only the fallback for a record
                # without one, dated by the round's OWN stamp — `updated_ts` is a generic
                # last-touch and re-dated a two-hour-old round on a bare `step` (round-5 finding)
                if disp_seats is not None:
                    if disp.get("ts") is None:
                        raise ValueError("dispatch stamp without ts")  # named, never silently 0
                    # a RELEASE marker is a known zero whatever `seats` says — the CLI never writes
                    # `released` beside a count, so a record that does is contradictory and the
                    # release wins (round-7 finding: `released, seats 5` counted 5 in flight)
                    ts, seats = float(disp["ts"]), 0 if released else int(disp_seats or 0)
                else:
                    ts = float(last.get("ts") or 0)
                    seats = int(last.get("seats") or 0)
                if not math.isfinite(ts) or now - ts > SIBLING_FRESH_S:
                    continue  # a NaN stamp read as forever-fresh (round-3 finding)
            except Exception:  # noqa: BLE001 — classify-and-name only; a probe fails SOFT
                # a malformed record (non-numeric seats/ts, Infinity, a round that is not a dict)
                # counts 0 and is named — two narrower tuples each let one shape crash the CLI
                out["skipped"].append(p.name)
                continue
            if seats > 0:
                out["seats"] += seats
                out["sessions"] += 1
    except OSError as exc:
        out.update(ok=False, why=f"sibling probe failed: {exc}")
    return out


def cost(mix: dict[str, int]) -> dict:
    """Relative cost of a seat mix in haiku-units, per the D-190 multipliers. An unknown model name
    or a non-positive count is REFUSED by name — the first draft silently dropped a negative count
    from the sum while still printing it in the mix, the same priced-at-zero shape the unknown-name
    refusal exists to prevent (round-1 finding)."""
    unknown = sorted(k for k in mix if k not in PRICE)
    if unknown:
        raise ValueError(f"unknown model(s) {unknown}; priced models: {sorted(PRICE)}")
    bad = sorted(k for k, v in mix.items() if int(v) <= 0)
    if bad:
        raise ValueError(f"seat count must be >= 1 for {bad}")
    parts = {k: int(v) * PRICE[k] for k, v in mix.items()}
    return {"units": sum(parts.values()), "parts": parts}


def full_mix(units: int, risky: int = 0, mechanical: int | None = None) -> dict[str, int]:
    """The MAXIMUM useful mix for a surface of `units`: one Sonnet breadth seat per unit, the
    authoritative Opus seats (one per risky unit, at least one), and the Haiku mechanical seats —
    one per unit by default, or `mechanical` of them: the count of grep-able classes the surface
    HAS (0 for a grounding/adjudication surface — a judgement unit has no mechanical angle, and a
    Haiku seat there returns a claim the orchestrator must refute; round-2 finding). Every seat is
    a distinct unit x angle brief; the caller trims it to the budget with `trim()`."""
    if units <= 0:
        return {}
    opus = max(1, min(risky, units))
    haiku = units if mechanical is None else max(0, mechanical)
    sonnet = units
    # the FLOOR is three REAL seats (D-188): a one-unit judgement surface has only two angles
    # (authoritative + breadth), so the third seat is a second breadth reader — the measured
    # same-brief technique (1 seat found 0; 3 found 0/5/0). "SEATS: 3" beside a 2-seat mix was
    # F10 wearing a new flag (round-3 finding)
    if opus + sonnet + haiku < FLOOR:
        sonnet += FLOOR - (opus + sonnet + haiku)
    return {k: v for k, v in (("opus", opus), ("sonnet", sonnet), ("haiku", haiku)) if v > 0}


def trim(mix: dict[str, int], seats: int) -> dict[str, int]:
    """Cut a full mix down to `seats` for maximum UNIT COVERAGE per haiku-unit: Haiku first (grep-
    shaped, so the survivors sweep class-wide), then the EXTRA Opus seats (a risky unit keeps its
    Sonnet seat — same unit, cheaper), then Sonnet, never below one Opus. The first draft shed
    Sonnet before Opus: a 3-unit surface at 2 seats became two Opus seats (cost 10) with one unit
    read by nobody, where {opus 1, sonnet 1} covers the same units for 7 (round-2 finding)."""
    if seats <= 0:
        return {}
    out = dict(mix)
    while sum(out.values()) > seats and out.get("haiku", 0) > 0:
        out["haiku"] -= 1
    while sum(out.values()) > seats and out.get("opus", 0) > 1:
        out["opus"] -= 1
    while sum(out.values()) > seats and out.get("sonnet", 0) > 0:
        out["sonnet"] -= 1
    return {k: v for k, v in out.items() if v > 0}


def parse_mix(text: str) -> dict[str, int]:
    """`opus=1,sonnet=5` -> {"opus": 1, "sonnet": 5}. Every part is `name=count`, nothing implied:
    a bare name, an empty name or a non-numeric count is refused with the part quoted."""
    mix: dict[str, int] = {}
    for part in filter(None, (x.strip() for x in text.split(","))):
        k, eq, v = part.partition("=")
        k = k.strip().lower()
        if not eq or not k or not re.fullmatch(r"-?\d+", v.strip()):
            raise ValueError(f"--mix part {part!r} is not name=count (e.g. opus=1,sonnet=5)")
        mix[k] = int(v)
    return mix


def budget(
    units: int,
    heavy: bool,
    b: dict,
    q: dict,
    s: dict | None = None,
    risky: int = 0,
    mechanical: int | None = None,
) -> dict:
    s = s or {"ok": True, "seats": 0, "sessions": 0, "skipped": []}
    reasons: list[str] = []
    if CAP_NOTE:
        reasons.append(CAP_NOTE)
    # D-191: the units are the partition, not the cap — the WANTED count is one seat per unit per
    # angle plus the authoritative seats; the box, the CLI cap and the quota are the caps
    wanted = sum(full_mix(max(units, 0), risky, mechanical).values())
    caps = {"wanted": wanted, "concurrency_cap": CONCURRENCY_CAP}
    if risky > units > 0:
        reasons.append(
            f"risky={risky} exceeds units={units} — clamped to {units} Opus seat(s); the risky units "
            "are a subset of the surface"
        )
    per_seat = HEAVY_GB_PER_SEAT if heavy else LIGHT_GB_PER_SEAT
    if b.get("ok"):
        mem = b["mem_available_gb"]
        if "commit_headroom_gb" in b:
            mem = min(mem, b["commit_headroom_gb"])
        by_mem = int(mem // per_seat)
        by_cpu = max(int(b["cores"] - math.ceil(b["load1"])), 0)
        taken = int(s.get("seats") or 0)
        phys = min(by_mem, by_cpu)
        # siblings RESERVE, they never starve: a session always gets the floor when the BOX has
        # room for it — three sessions each at 13 seats left the third at 0 (round-2 finding). But
        # a box that is itself below the floor keeps the reservation in full: `max(phys - taken,
        # min(phys, FLOOR))` let three sessions each claim a 2-seat box (round-3 finding)
        cap = max(phys - taken, 0)
        if cap < FLOOR <= phys:
            cap = FLOOR
        caps["box_cap"] = cap
        reasons.append(
            f"box allows {cap} {'heavy' if heavy else 'read-only'} seats "
            f"(mem {mem:.1f}GB/{per_seat}GB={by_mem}, cores {b['cores']}-load {b['load1']:.1f}={by_cpu}"
            + (
                f", minus {taken} seat(s) dispatched < {SIBLING_FRESH_S // 60} min ago in "
                f"{s.get('sessions')} running record(s), never below the floor of {FLOOR}"
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
    if s.get("unrecorded"):
        # its own line: nested under the `taken` clause it never printed for the common case — a
        # sibling that has just `start`ed and dispatched nothing yet (round-6 finding)
        reasons.append(
            f"{s['unrecorded']} running sibling session(s) carry NO seat figure — the box number "
            "is a LOWER bound"
        )
    if s.get("own_source") == "env":
        reasons.append(
            "own-session id came from the env only (command_run.py not importable) — an id-less "
            "shell may be counting its own record as a sibling"
        )
    if q.get("ok"):
        if q["hold"]:
            caps["quota_cap"] = 0
            reasons.append("fleet-exhausted HOLD is on — dispatch nothing until relief")
        else:
            band = float(q.get("drain_band") or 85.0)
            unknown = q["hottest_pct"] is None
            # the picture publishes its own in_drain_band predicate; read it, don't re-derive it
            hot = unknown or bool(q.get("active_in_band")) or q["hottest_pct"] >= band
            if hot:
                caps["quota_cap"] = FLOOR
                reasons.append(
                    (
                        f"quota: the active account could not be identified ({q['active']!r}) — "
                        "treated as HOT, never as cool"
                        if unknown
                        else f"quota: active {q['active']} is at {q['hottest_pct']}% — in the drain "
                        f"band ({band}%, the rotation picture's own predicate)"
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
    if units <= 0:
        # no surface to partition: the floor is a rule about seats PER SURFACE, and "SEATS: 3"
        # beside a mix of {} recorded three phantom seats (round-1 finding) — say it, dispatch none
        caps["wanted"] = 0
        reasons.append(
            f"units={units} — nothing to partition; give --units >= 1 (one unit is already the floor of 3)"
        )
    elif (
        caps["wanted"] < FLOOR
    ):  # unreachable: full_mix pads to the floor itself; kept as the guard
        reasons.append(
            f"wanted={caps['wanted']} raised to the floor of {FLOOR} — three seats on DIFFERENT "
            f"angles over the whole surface (D-188)"
        )
        caps["wanted"] = FLOOR
    seats = min(caps.values())
    if seats < caps["wanted"]:
        binding = [k for k, v in caps.items() if v == seats and k != "wanted"]
        reasons.append(
            f"wanted {caps['wanted']} (units x angles + authoritative), bound to {seats} by "
            f"{', '.join(binding)} — the box/quota decide, the surface only asks"
        )
    if seats < FLOOR and units > 0:
        hard = [k for k, v in caps.items() if v == seats and k != "wanted"]
        reasons.append(
            f"below the floor because a HARD cap binds ({', '.join(hard)}={seats}) — "
            + (
                "dispatch nothing until relief"
                if seats == 0 and "quota_cap" in hard
                else "wait for the box or the sibling rounds to finish; never dispatch past a hard cap"
            )
        )
    return {"seats": seats, "caps": caps, "reasons": reasons}


def _mix_story(a: argparse.Namespace, mix: dict[str, int], full: dict[str, int]) -> str:
    """The sentence beside COST must describe THIS mix — the first draft glued "one Sonnet + one
    Haiku seat per unit" to a mix the budget had already trimmed, and an agent reading it literally
    would dispatch past a hard cap (round-2 finding)."""
    tail = " — D-190: haiku 1x · sonnet 2x · opus 5x · fable 10x"
    if a.mix:
        return tail
    haiku = mix.get("haiku", 0)
    if mix == full:
        pad = mix.get("sonnet", 0) - a.units
        padded = (
            f"; the extra {pad} Sonnet seat(s) are SECOND breadth readers on the same unit — a "
            "deliberate duplicate brief padding to the floor of 3 (D-188), not a distinct unit"
            if pad > 0
            else ""
        )
        if not haiku:
            mech = (
                "; no mechanical seat (--mechanical 0: a judgement surface has no grep-able angle)"
            )
        elif haiku == a.units:
            mech = f", {haiku} Haiku mechanical seat(s) — one per unit"
        else:
            mech = f", {haiku} Haiku mechanical seat(s) — one per grep-able class, each swept across every unit"
        return (
            f" — the MAXIMUM useful mix for {a.units} unit(s): one Sonnet breadth seat per unit, "
            f"the Opus authoritative seat(s) (--risky N: one per risky unit){mech}{padded}; dispatch "
            "ALL of it in ONE message, each seat a distinct unit x angle brief" + tail
        )
    # an Opus seat on a risky unit reads that unit too; a judgement surface never HAD mechanical
    # classes, so nothing "waits" (round-3 finding: the story told --mechanical 0 to sweep them)
    # units read by NOBODY this round: the Sonnet seats plus the Opus seats, which a trimmed
    # round places on units WITHOUT a Sonnet seat (each seat is a distinct unit x angle brief) —
    # the earlier formula forced the Opus seat onto a Sonnet-read unit and over-reported the gap
    # in half of all trimmed mixes (round-6 finding, 83,600 of 165,957 combinations)
    sonnet = mix.get("sonnet", 0)
    covered = min(sonnet + min(mix.get("opus", 0), max(a.risky, 1)), a.units)
    uncovered = max(a.units - covered, 0)
    if haiku:
        left = (
            f": {haiku} Haiku seat(s) left — each sweeps ONE grep-able class across every unit "
            "(class-wide, not per unit)"
        )
    elif full.get("haiku"):
        left = ": no Haiku seat left — the mechanical classes wait for the next round"
    else:
        left = ""
    gap = (
        f"; {uncovered} unit(s) have NO seat at all this round — re-sweep them next round, never "
        "dispatch past the cap"
        if uncovered
        else ""
    )
    return f" — TRIMMED from {sum(full.values())} wanted to the budget{left}{gap}{tail}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])

    # REQUIRED: a default of FLOOR let a caller who forgot the flag read a plausible "SEATS: 3" as a
    # constrained verdict instead of "you never said how big the surface is" (round-1 finding).
    def _count(text: str) -> int:
        n = int(text)
        if n < 0:
            raise argparse.ArgumentTypeError(f"{n} is not a count")
        return n

    ap.add_argument("--units", type=_count, required=True, help="independent units in the surface")
    ap.add_argument("--heavy", action="store_true", help="each seat runs tests/builds/renders")
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--mix",
        default="",
        help='price a seat mix, e.g. "opus=1,sonnet=5" (D-190: haiku 1x, sonnet 2x, opus 5x, fable 10x)',
    )
    ap.add_argument(
        "--risky", type=_count, default=0, help="units that are auth/schema/secrets (Opus)"
    )
    ap.add_argument(
        "--mechanical",
        type=_count,
        default=None,
        help="Haiku seats wanted: the grep-able classes the surface HAS (default: one per unit; "
        "0 for a grounding/adjudication surface — a judgement unit has no mechanical angle)",
    )
    a = ap.parse_args(argv)
    b, q, s = box(), quota(), siblings()
    r = budget(a.units, a.heavy, b, q, s, a.risky, a.mechanical)
    full = full_mix(a.units, a.risky, a.mechanical)
    try:
        # the MAXIMUM useful mix, trimmed to what is viable — never the minimum by default
        mix = parse_mix(a.mix) if a.mix else trim(full, r["seats"])
        priced = cost(mix)
    except ValueError as exc:
        print(f"dispatch_headroom.py: error: {exc}", file=sys.stderr)
        return 2
    # the adjudicator is ONE seat per run on Fable (10x) that no mix returns — a COST that
    # omitted it understated every run by 10 units, always in the cheap direction
    adjudicator = {"model": "fable", "units": PRICE["fable"], "counted_in_seats": False}
    mix_seats = sum(mix.values())
    if mix_seats != r["seats"]:
        r["reasons"].append(
            f"mix has {mix_seats} seat(s) but the budget is {r['seats']} — reprice or resize; "
            "SEATS and COST must describe the same round"
        )
    # both box bounds in one probe, so a caller that wants the pair (the board banner) runs this
    # script — and its fleet round-trip — ONCE, not twice
    box_caps = {
        "read_only": budget(a.units, False, b, q, s, a.risky, a.mechanical)["caps"].get("box_cap"),
        "heavy": budget(a.units, True, b, q, s, a.risky, a.mechanical)["caps"].get("box_cap"),
    }
    r.update(
        box=b,
        quota=q,
        siblings=s,
        tiers=TIERS,
        units=a.units,
        heavy=a.heavy,
        price=PRICE,
        mix=mix,
        full_mix=full,
        cost=priced,
        adjudicator=adjudicator,
        box_caps=box_caps,
        floor=FLOOR,  # the board labels a cap the floor raised (round-7 finding)
    )
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
            f"  quota: active {q['active']} hottest {q['hottest_pct']}%, cool standbys "
            f"{q['eligible']} of {q.get('eligible_raw', q['eligible'])} eligible, hold={q['hold']}, "
            f"drain band {q.get('drain_band')}%"
        )
    if mix:
        shown = " + ".join(f"{n} {k} x{PRICE[k]}" for k, n in mix.items())
        print(f"  COST: {priced['units']} haiku-units for {shown}{_mix_story(a, mix, full)}")
        print(
            f"  + {adjudicator['units']} for the orchestrator/adjudicator on fable x10 — one per run, "
            "not in the seat total. RELATIVE and dimensionless: assumes equal tokens per seat, and "
            "the orchestrator's own reading (at its own multiplier, growing with every seat's "
            "report) is NOT counted — the absolute anchor waits on `round --seats` rows."
        )
    else:
        print("  COST: 0 haiku-units — nothing to dispatch (see the reasons above)")
    print(
        "  record the dispatch BEFORE you send it: python3 scripts/command_run.py dispatch "
        "--seats <n>   (the stamp sibling sessions subtract; a round --seats at the close "
        "reserves nothing while the seats run)"
    )
    print(
        "  then close the round: python3 scripts/command_run.py round --seats <n> "
        "--findings <n> --classes-swept … --classes-new …"
    )
    print("  tiers (model by the seat's JOB; the per-dispatch token is Agent(model=...)):")
    for k, v in TIERS.items():
        print(f"    {k:7} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
