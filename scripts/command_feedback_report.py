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
import statistics
import sys
import time
from pathlib import Path

_FIELDS = ("confusion", "waste", "change")


def _default_ledger() -> Path:
    import os

    raw = os.environ.get("COMMAND_RUN_DIR")
    base = Path(raw).parent if raw else Path.home() / ".claude" / "state"
    return base / "command-feedback.jsonl"


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out: list[dict] = []
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
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
    head = value.strip().lower().split(" ")[0].rstrip(".,;") if value else ""
    return not value or head in {"none", "nothing", "n/a", "-"}


def _median(values: list) -> float | int:
    if not values:
        return 0
    m = statistics.median(values)
    return int(m) if float(m).is_integer() else round(float(m), 1)


def _cost(r: dict) -> float | None:
    v = r.get("cost_usd")
    return float(v) if isinstance(v, (int, float)) else None


def build(
    rows: list[dict], since_days: float | None, command: str | None, agent: str | None = None
) -> dict:
    total = len(rows)
    cutoff = time.time() - since_days * 86400 if since_days is not None else None  # 0 = now
    kept = [
        r
        for r in rows
        if (cutoff is None or float(r.get("ts") or 0) >= cutoff)
        and (command is None or r.get("command") == command)
        and (agent is None or str(r.get("agent") or "") == agent)
    ]
    per: dict[str, list[dict]] = collections.defaultdict(list)
    for r in kept:
        per[str(r["command"])].append(r)
    commands: dict[str, dict] = {}
    for cmd, rs in sorted(per.items()):
        walls = [float(r.get("wall_s") or 0) / 60 for r in rs]
        rounds = [int(r.get("rounds") or 0) for r in rs]
        commands[cmd] = {
            "runs": len(rs),
            "done": sum(1 for r in rs if r.get("state") == "done"),
            "blocked": sum(1 for r in rs if r.get("state") == "blocked"),
            "median_wall_min": round(float(statistics.median(walls)), 1) if walls else 0.0,
            "max_wall_min": round(max(walls), 1) if walls else 0.0,
            "median_rounds": _median(rounds),
            "change_none": sum(1 for r in rs if _is_none(str(r.get("change") or ""))),
            # summed over the rows that carry a number; rows without one are counted, not zeroed
            "cost_usd": round(sum(c for c in map(_cost, rs) if c is not None), 4),
            "cost_rows": sum(1 for r in rs if _cost(r) is not None),
        }

    def _items(field: str) -> list[dict]:
        counter: collections.Counter[tuple[str, str]] = collections.Counter()
        agents: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
        first: dict[tuple[str, str], dict] = {}
        for r in kept:
            v = str(r.get(field) or "").strip()
            if not _is_none(v):
                key = (str(r["command"]), v)
                counter[key] += 1
                a = str(r.get("agent") or "")
                if a and a not in agents[key]:
                    agents[key].append(a)  # EVERY agent that raised it, first-seen order
                first.setdefault(key, r)  # the surface of the row that raised it first
        return [
            {
                "command": c,
                "item": v,
                "count": n,
                "agent": ",".join(agents[(c, v)]),
                "surface": str(first[(c, v)].get("surface") or ""),
            }
            for (c, v), n in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
        ]

    return {
        "total_rows": total,
        "examined": len(kept),
        "since_days": since_days,
        "agent": agent,
        "commands": commands,
        "backlog": _items("change"),
        "confusion": _items("confusion"),
        "waste": _items("waste"),
    }


def render(report: dict) -> str:
    lines = [
        f"command feedback — {report['examined']} of {report['total_rows']} ledger rows examined"
        + (f" (last {report['since_days']:g} days)" if report["since_days"] is not None else "")
        + (f" · agent {report['agent']}" if report.get("agent") else ""),
        "",
        "| command | runs | done/blocked | median wall | max wall | median rounds | change: none "
        "| pool $ (rows) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for cmd, c in report["commands"].items():
        lines.append(
            f"| /{cmd} | {c['runs']} | {c['done']}/{c['blocked']} | {c['median_wall_min']} min | "
            f"{c['max_wall_min']} min | {c['median_rounds']} | {c['change_none']} of {c['runs']} | "
            f"{c['cost_usd']} ({c['cost_rows']}) |"
        )
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
