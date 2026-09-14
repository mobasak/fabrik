#!/usr/bin/env python3
# AFTER-EDIT: tests/test_command_feedback_report.py, docs/reference/command-run-protocol.md | none
"""Per-command optimisation report over the fleet-wide close-out ledger (D-175).

Every `command_run.py done|blocked|handoff` appends one row to
`~/.claude/state/command-feedback.jsonl` (beside the run-record dir; `COMMAND_RUN_DIR`'s parent
when set): the command, its wall-clock, its round count and findings trend, and the four usage
fields the agent wrote — confusion, waste, change, filed. This report turns those rows into the
list the corpus is optimised from: per command, how long and how many rounds a run takes, and
the concrete `change:` items agents asked for, ranked by how often they recur.

    python3 scripts/command_feedback_report.py [--since DAYS] [--command NAME] [--json]
                                               [--ledger PATH]

Every count states its bound: `examined` of `total_rows`. A missing ledger is an empty report.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import TypeGuard

_FIELDS = ("confusion", "waste", "change")


def _default_ledger() -> Path | None:
    import os

    raw = os.environ.get("COMMAND_RUN_DIR")
    try:
        base = Path(raw).parent if raw else Path.home() / ".claude" / "state"
    except RuntimeError:  # no resolvable home
        return None
    return base / "command-feedback.jsonl"


def _rows(path: Path | None) -> list[dict]:
    """A missing OR unreadable ledger is an empty report, never a crash (review 2026-09-07)."""
    if path is None:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out: list[dict] = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(r, dict) and r.get("command"):
            out.append(r)
    return out


def _is_none(value: str) -> bool:
    stripped = (value or "").strip()
    head = stripped.lower().split()[0].rstrip(".,;") if stripped else ""
    return not stripped or head in {"none", "nothing", "n/a", "-"}


def _median(values: list) -> float | int:
    if not values:
        return 0
    m = statistics.median(values)
    return int(m) if float(m).is_integer() else round(float(m), 1)


def _num(v: object) -> float | None:
    """A finite number from a ledger cell, else None — one bad row in the shared, append-only
    ledger must never take the whole report down (review pass 22: the pass-21 guard covered
    cost_usd/tok_* only; a string, list, NaN, Infinity or 400-digit `wall_s`/`rounds`/`ts` still
    raised out of build()). None is NO datum: the caller drops it and discloses the row count,
    never a phantom 0 that drags a median (pass 23)."""
    try:
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v)):
            return float(v)
    except OverflowError:  # a 400-digit JSON integer: float() itself overflows
        pass
    return None


def _cost(r: dict) -> float | None:
    v = r.get("cost_usd")
    try:
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v)):
            return float(v)
    except OverflowError:  # a 320-digit JSON integer: float() itself overflows
        pass
    return None  # a non-finite or oversized value in an old row is counted as a run, never summed


_TOK = ("tok_in", "tok_out", "tok_cache_read", "tok_cache_create")
# the SEATS' spend (D-192/D-193): the four fields summed from each seat's own transcript —
# summed separately from the orchestrator's, never folded into `tok_total` (which stays what the
# orchestrator read), because 20M seat tokens beside 160 orchestrator tokens was invisible to every
# rollup here (review 2026-09-08)
_SEAT_TOK = ("tok_seat_in", "tok_seat_out", "tok_seat_cache_read", "tok_seat_cache_create")


def _is_count(v: object) -> TypeGuard[int | float]:
    """A finite non-bool number — the same acceptance `seats_seen` uses, so the two aggregations of
    one field cannot disagree on a `10.0` (round-6 finding)."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def _seat_total(r: dict) -> int | None:
    """Seat tokens on a row (sync fields + background total), or None when the row carries none."""
    total = 0
    seen = False
    for k in _SEAT_TOK:
        v = r.get(k)
        if v is None:
            continue
        if (
            not isinstance(v, (int, float))
            or isinstance(v, bool)
            or not math.isfinite(float(v))
            or v < 0  # the same sign rule: two rows of -10000 and +10000 rendered "0 (2 · —)",
            # which reads as two rows measured at zero rather than as data nobody can trust
        ):
            return None  # a malformed seat field nulls the row's seat sum, never the count
        total += int(v)
        seen = True
    return total if seen else None


def _tok_total(r: dict) -> int | None:
    vals = [r.get(k) for k in _TOK]
    try:
        if any(
            not isinstance(v, (int, float))
            or isinstance(v, bool)
            or not math.isfinite(float(v))
            or v < 0  # a NEGATIVE component, not merely a negative sum: `cache_hit` recombines
            # these same fields per-component behind this whole-row gate, so guarding only the total
            # let one bad field through to print -25% and 250% cache hits from garbage
            for v in vals
        ):
            return None  # a row without (finite, non-negative) transcript data is counted, never zeroed
        return int(sum(vals))
    except OverflowError:
        return None


def _io_total(r: dict) -> int | None:
    """Σ ``tok_in`` + ``tok_out`` on a row, or ``None`` when the row carries neither finitely.

    DELIBERATELY NOT ``_tok_total``, which sums all four token fields including the two cache ones.
    Cache tokens measure how much of a prompt was re-read, not how much work a round did, so folding
    them into a per-round figure would make a long cached conversation look like heavy work. The
    report therefore carries two conventions at once and states both (spec § Q2, § Reproduce R9).
    """
    vals = [r.get(k) for k in ("tok_in", "tok_out")]
    if any(v is None for v in vals):
        return None  # a HALF pair is not a pair (spec § Q2: it contributes to NEITHER side)
    try:
        if any(
            not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(float(v))
            for v in vals
        ):
            return None
        total = int(sum(vals))
    except OverflowError:
        return None
    # a negative token count is corrupt data, never mass: signed sums make the ratio unbounded, so
    # a single bad row could push it over ⅔ and pass the very rule that exists to silence the figure
    return total if total >= 0 else None


def _whole(n: float | None) -> bool:
    """A round count that can be a divisor: a whole number above zero.

    `_num` gates finiteness but not integrality, and `int()` TRUNCATES — a `rounds` of 2.7 would
    have overstated the figure by 26% while a 0.9 silently left its tokens in the mass and out of
    the numerator, which is the asymmetry that silences a command for a reason nobody can see.
    """
    return n is not None and float(n).is_integer() and int(n) > 0


def _tok_per_round(rs: list[dict]) -> dict[str, object]:
    """Tokens per round for one command, behind the MASS RULE, with its own population counts.

    Two ordered clauses, and the order is load-bearing:
      1. total token mass ``T`` is 0  → publish nothing ("zero token mass"). Evaluated FIRST, because
         a ratio over a zero denominator is exactly the division this rule exists to prevent, and a
         0/0 would render as a confident ``0.0``.
      2. the rows carrying BOTH sides hold < ⅔ of ``T`` → publish nothing, and say the measured
         ratio. A figure over a minority of the work describes something other than the command.
    The quantity is Σ(tok_in+tok_out) ÷ Σ rounds over the rows carrying BOTH a finite token pair and
    an integer ``rounds > 0``: a row with tokens and no rounds, and a row with rounds and no tokens,
    contribute to NEITHER side, and so does a row that spent NOTHING — a zero-token row with rounds
    would dilute the divisor while leaving the ratio at a reassuring 1.0, which is the one failure
    the mass rule exists to prevent, passing it at perfect coverage. ``cost_usd`` enters nothing
    here (spec § Q2 — it derives nothing).
    """
    mass = sum(v for v in map(_io_total, rs) if v is not None)
    pairs = [
        (io, int(n))
        for r in rs
        for io in (_io_total(r),)
        for n in (_num(r.get("rounds")),)
        if io is not None and io > 0 and _whole(n)
    ]
    out: dict[str, object] = {
        "rows_with_numerator": sum(1 for r in rs if _io_total(r) is not None),
        "rows_with_denominator": sum(1 for r in rs if _whole(_num(r.get("rounds")))),
        "rows_both": len(pairs),
        "rows_total": len(rs),
        "tok_per_round": None,
        "tok_per_round_reason": None,
        "mass_ratio": None,
    }
    if mass == 0:  # clause 1, BEFORE any ratio
        # a 0 over 0 rows is "nothing looked at", not an honest zero — the file's own rule, applied
        out["tok_per_round_reason"] = (
            "zero token mass" if out["rows_with_numerator"] else "no token-carrying row"
        )
        return out
    covered = sum(io for io, _n in pairs)
    ratio = covered / mass
    out["mass_ratio"] = ratio
    if ratio < 2 / 3:  # clause 2 — `>=` two thirds publishes, so the boundary is inclusive
        out["tok_per_round_reason"] = f"mass ratio {ratio:.4f} < 2/3"
        return out
    rounds = sum(n for _io, n in pairs)
    if rounds == 0:  # unreachable while pairs require rounds > 0; never divide on a guess
        out["tok_per_round_reason"] = "no round-carrying row"
        return out
    out["tok_per_round"] = covered / rounds
    return out


def _k(n: float) -> str:
    if round(n / 1000, 1) >= 1000:  # 999,999 rolls over to 1.0M, never "1000.0k"
        return f"{n / 1_000_000:.1f}M"
    return f"{n / 1000:.1f}k" if n >= 1000 else f"{n:.0f}"


def build(
    rows: list[dict], since_days: float | None, command: str | None, agent: str | None = None
) -> dict:
    total = len(rows)
    cutoff = time.time() - since_days * 86400 if since_days is not None else None  # 0 = now
    kept = [
        r
        for r in rows
        if (cutoff is None or (_num(r.get("ts")) or 0) >= cutoff)
        and (command is None or r.get("command") == command)
        and (agent is None or str(r.get("agent") or "") == agent)
    ]
    per: dict[str, list[dict]] = collections.defaultdict(list)
    for r in kept:
        per[str(r["command"])].append(r)
    commands: dict[str, dict] = {}
    for cmd, rs in sorted(per.items()):
        # rows with a finite value only; the counts beside the medians are their denominators
        walls = [w / 60 for w in map(_num, (r.get("wall_s") for r in rs)) if w is not None]
        # NOT int(): truncating a 2.7 into the median is the same defect `_whole` rejects for the
        # tok/round divisor. A 0-round run is still a real run and stays in the median's population.
        rounds = [n for n in map(_num, (r.get("rounds") for r in rs)) if n is not None]
        commands[cmd] = {
            "runs": len(rs),
            "done": sum(1 for r in rs if r.get("state") == "done"),
            "blocked": sum(1 for r in rs if r.get("state") == "blocked"),
            "handoff": sum(1 for r in rs if r.get("state") == "handoff"),
            "models": sorted(
                {
                    m
                    for r in rs
                    for m in (r.get("models") if isinstance(r.get("models"), list) else [])
                    if isinstance(m, str)
                }
            ),
            # no timed row ⇒ null, never a 0 that reads like a real zero-minute run (pass 24)
            "median_wall_min": round(float(statistics.median(walls)), 1) if walls else None,
            "max_wall_min": round(max(walls), 1) if walls else None,
            "median_rounds": _median(rounds) if rounds else None,
            "wall_rows": len(walls),
            "rounds_rows": len(rounds),
            "change_none": sum(1 for r in rs if _is_none(str(r.get("change") or ""))),
            # summed over the rows that carry a number; rows without one are counted, not zeroed
            "cost_usd": round(sum(c for c in map(_cost, rs) if c is not None), 4),
            "cost_rows": sum(1 for r in rs if _cost(r) is not None),
        }
        toks = [t for t in map(_tok_total, rs) if t is not None]
        ctx = sum(
            int(r["tok_in"]) + int(r["tok_cache_read"]) + int(r["tok_cache_create"])
            for r in rs
            if _tok_total(r) is not None
        )
        read = sum(int(r["tok_cache_read"]) for r in rs if _tok_total(r) is not None)
        seats = [t for t in map(_seat_total, rs) if t is not None]
        commands[cmd].update(
            {
                "tok_total": sum(toks),
                "tok_rows": len(toks),
                "seat_total": sum(seats),
                "seat_rows": len(seats),
                # ONE acceptance (`_is_count`) for the count and its denominator — two textually
                # identical predicates were free to drift (round-9 finding)
                "seats_seen": sum(
                    int(v) for r in rs for v in (r.get("seats_seen"),) if _is_count(v)
                ),  # one malformed row must never take the whole report down (round-4 finding)
                "median_tok": _median(toks) if toks else None,  # no rows ⇒ null, never "0"
                "cache_hit": round(read / ctx, 3) if ctx else None,
                # rows whose scan hit the byte cap inside the window: their sums are lower bounds
                "tok_partial_rows": sum(1 for r in rs if r.get("tok_partial") is True),
                # a seat still writing at the close; and a typed reservation that disagreed with
                # the seat files by more than one — the close's warning, made queryable (round 5)
                # the rows the seat count was read from — a 0 over 0 rows is "nothing looked at",
                # not an honest zero (round-8 Opus finding)
                "seats_seen_rows": sum(1 for r in rs if _is_count(r.get("seats_seen"))),
                "seats_partial_rows": sum(1 for r in rs if r.get("seats_partial") is True),
                # seat files dropped for size/unreadability — a count nobody could read from any
                # rollup while it lived only in the raw row (round-7 finding)
                "seats_skipped": sum(
                    int(v) for v in (r.get("seats_skipped") for r in rs) if _is_count(v)
                ),
                **_tok_per_round(rs),
                "seats_mismatch_rows": sum(
                    1
                    for r in rs
                    if _is_count(r.get("seats_declared"))
                    and _is_count(r.get("seats_seen"))
                    and abs(int(r["seats_declared"]) - int(r["seats_seen"])) > 1
                ),
            }
        )

    def _items(field: str) -> list[dict]:
        counter: collections.Counter[tuple[str, str]] = collections.Counter()
        agents: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
        surfaces: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
        for r in kept:
            v = str(r.get(field) or "").strip()
            if not _is_none(v):
                key = (str(r["command"]), v)
                counter[key] += 1
                a = str(r.get("agent") or "")
                if a and a not in agents[key]:
                    agents[key].append(a)  # EVERY agent that raised it, first-seen order
                sf = str(r.get("surface") or "")
                if sf and sf not in surfaces[key]:
                    surfaces[key].append(sf)  # and EVERY surface — never the first row's only
        return [
            {
                "command": c,
                "item": v,
                "count": n,
                "agent": ",".join(agents[(c, v)]),
                "surface": ", ".join(surfaces[(c, v)]),
            }
            for (c, v), n in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
        ]

    return {
        "conventions": {
            "tok_per_round": (
                "Σ(tok_in+tok_out) ÷ Σ rounds over the rows carrying a POSITIVE token pair and a "
                "whole rounds > 0; cache excluded; mass-weighted, not a median"
            ),
            "median_tok": (
                "cache-inclusive, over the rows carrying ALL FOUR token fields — a DIFFERENT "
                "population from tok_per_round's, neither containing the other: a row with all "
                "four fields and rounds 0 is here and not there, and a row with only the "
                "input/output pair and rounds > 0 is there and not here"
            ),
            "mass_rule": (
                "tok_per_round is silent when the command's token mass is 0 (mass_ratio is then "
                "null — there is nothing to take a ratio of), or when the rows it is computed over "
                "hold under two thirds of that mass, in which case mass_ratio is the measure"
            ),
            "row_counts": (
                "num = rows carrying a token pair; den = rows carrying a whole rounds > 0; both = "
                "the rows the figure is computed over, which additionally requires the pair to be "
                "POSITIVE — a row that measured no tokens has no work to attribute to its rounds"
            ),
        },
        "total_rows": total,
        "examined": len(kept),
        "since_days": since_days,
        "agent": agent,
        "commands": commands,
        "backlog": _items("change"),
        "confusion": _items("confusion"),
        "waste": _items("waste"),
    }


def _cell(text: str) -> str:
    """Free text made safe for a markdown table cell.

    A literal ``|`` inside a cell is an extra column boundary: one pipe in a command or model name
    used to render a 16-cell row under a 13-cell header, silently turning the table into prose for
    every downstream reader. Command names come from a controlled vocabulary; model strings do not.
    """
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _per_round_cell(c: dict) -> str:
    """`<q/T> (num/den/both)` — the figure or the reason it is silent, always with its population."""
    counts = f"({c['rows_with_numerator']}/{c['rows_with_denominator']}/{c['rows_both']})"
    if c.get("tok_per_round") is None:
        return f"— {c.get('tok_per_round_reason') or 'not derived'} {counts}"
    return f"{_k(float(c['tok_per_round']))} {counts}"


def _min(v: float | None) -> str:
    return f"{v} min" if v is not None else "—"


def render(report: dict) -> str:
    lines = [
        f"command feedback — {report['examined']} of {report['total_rows']} ledger rows examined"
        + (f" (last {report['since_days']:g} days)" if report["since_days"] is not None else "")
        + (
            f" · agent {report['agent'] or '(unattributed)'}"
            if report.get("agent") is not None
            else ""
        ),
        "Population: rows are AGENT-CLOSED runs only — coroner-closed (died/expired) runs write no "
        "row; nested runs overlap their parent's window, so per-command token and cost totals are "
        "not additive across commands.",
        "Conventions: tok/round is Σ(tok_in+tok_out) ÷ Σ rounds over the rows carrying a POSITIVE "
        "token pair and a whole rounds > 0 — cache excluded, and mass-weighted rather than a "
        "median, so one heavy run moves it more than a light one. Its (num/den/both) are three "
        "SEPARATE counts: rows carrying a token pair, rows carrying a whole rounds > 0, and the "
        "rows the figure is actually computed over — the third needs BOTH of the first two AND a "
        "positive pair, so num and den usually differ from it because a row carries only one side, "
        "and it drops further only where a row measured no tokens at all. The cell reads — when "
        "the command's token mass is "
        "0, or when those rows hold under two thirds of it; it says which, and --json carries the "
        "measured ratio in the second case (in the first there is nothing to take a ratio of). "
        "median tokens is cache-inclusive and needs all four token fields — a DIFFERENT population "
        "from tok/round's, neither containing the other, so the two row counts do not compare.",
        "",
        "| command | runs | done/blocked/handoff | median wall (rows) | max wall | "
        "median rounds (rows) | change: none | pool $ (rows) | median tokens (rows) | cache hit | "
        "seat tokens (rows · seats) | tok/round (num/den/both) | models |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for cmd, c in report["commands"].items():
        hit = f"{100 * c['cache_hit']:.0f}%" if c.get("cache_hit") is not None else "—"
        lines.append(
            f"| /{_cell(cmd)} | {c['runs']} | {c['done']}/{c['blocked']}/{c['handoff']} | "
            f"{_min(c['median_wall_min'])} ({c['wall_rows']}) | {_min(c['max_wall_min'])} | "
            f"{c['median_rounds'] if c['rounds_rows'] else '—'} ({c['rounds_rows']}) | "
            f"{c['change_none']} of {c['runs']} | "
            f"{c['cost_usd'] if c['cost_rows'] else '—'} ({c['cost_rows']}) | "
            f"{_k(c['median_tok']) if c.get('median_tok') is not None else '—'} "
            f"({c['tok_rows']}) | {hit} | "
            f"{_k(c['seat_total']) if c['seat_rows'] else '—'} ({c['seat_rows']} · "
            f"{c['seats_seen'] if c['seats_seen_rows'] else '—'}"
            f"{' · ' + str(c['seats_skipped']) + ' skipped' if c['seats_skipped'] else ''}) | "
            f"{_per_round_cell(c)} | "
            f"{_cell(', '.join(c['models'])) or '—'} |"
        )
    # the rows whose sums UNDERSTATE — computed since round 5 and rendered only by --json until the
    # round-7 Opus seat read the text report the contract names (F119/F139 were --json-only fixes)
    cav = [
        f"/{c}: {v['seats_mismatch_rows']} declared/seen seat mismatch, "
        f"{v['seats_partial_rows']} seat(s) still running at the close, "
        f"{v['tok_partial_rows']} truncated token scan(s)"
        for c, v in report["commands"].items()
        if v["seats_mismatch_rows"] or v["seats_partial_rows"] or v["tok_partial_rows"]
    ]
    if cav:
        lines += ["", "⚠ LOWER BOUNDS — the sums above understate these rows:"] + [
            f"- {x}" for x in cav
        ]
    for title, key in (
        ("Optimisation backlog (change:)", "backlog"),
        ("Confusion (confusion:)", "confusion"),
        ("Waste (waste:)", "waste"),
    ):
        lines += ["", f"## {title} — {len(report[key])} distinct item(s)"]
        for it in report[key][:40]:
            who = " · ".join(x for x in (it.get("agent"), it.get("surface")) if x)
            tag = f" [{who}]" if who else ""
            lines.append(f"- ×{it['count']} /{it['command']}{tag}: {it['item']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Per-command optimisation report over the feedback ledger."
    )
    ap.add_argument("--since", type=float, default=None, help="only rows from the last N days")
    ap.add_argument("--command", default=None, help="one command name (without the slash)")
    ap.add_argument("--agent", default=None, help="one agent name (CLAUDE_AGENT at start)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--ledger", type=Path, default=None)
    a = ap.parse_args(argv)
    report = build(_rows(a.ledger or _default_ledger()), a.since, a.command, a.agent)
    sys.stdout.write(
        json.dumps(report, indent=1, ensure_ascii=False) + "\n" if a.json else render(report) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
