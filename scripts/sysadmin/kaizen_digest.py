#!/usr/bin/env python3
# AFTER-EDIT: tests/test_kaizen_digest.py, docs/workstation/kaizen.md | none
"""Kaizen daily digest — the READER half of the measurement pipeline.

Built 2026-08-30 on the operator's challenge: the collector had published real series for
days (37k events; 144/177 closes with verdicts) into ``~/.claude/kaizen.log`` and a
reference doc nobody is shown — measurement without a reader. This composes ONE short
message from the published day-series (latest point + delta vs the prior point, highest
series version per metric — the published-series law) and sends it to the operator's
Telegram via the existing ``send-telegram.sh`` helper.

Usage:
    kaizen_digest.py            # print the digest to stdout
    kaizen_digest.py --send     # print AND send via scripts/sysadmin/send-telegram.sh

Cron (operator-installed — agent crontab writes are classifier-blocked on this box):
    50 6 * * * /opt/fabrik/.venv/bin/python /opt/fabrik/scripts/sysadmin/kaizen_digest.py --send >> $HOME/.claude/kaizen-digest.log 2>&1
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path("/opt/fabrik")
_SERIES_RE = re.compile(r"^(?P<metric>[\w-]+)@v(?P<ver>\d+)\.jsonl$")

# Curated headline order; anything else appends alphabetically. A metric missing from the
# store simply doesn't print — but an EMPTY store prints loudly (silence reads as health).
_HEADLINE = (
    "first_attempt_gate_pass",
    "review_rounds",
    "premature_stop_rate",
    "hole_count",
    "unclassified_rate",
)


def _state_dir() -> Path:
    return Path(os.getenv("KAIZEN_STATE_DIR", "") or (Path.home() / ".claude/state/kaizen"))


def _latest_series(root: Path) -> dict[str, Path]:
    """metric -> the HIGHEST-version series file (a published series is never overwritten;
    a definition change writes a new version — the old file is history, not signal)."""
    best: dict[str, tuple[int, Path]] = {}
    sdir = root / "series"
    if not sdir.is_dir():
        return {}
    for f in sdir.iterdir():
        m = _SERIES_RE.match(f.name)
        if not m:
            continue
        ver = int(m.group("ver"))
        cur = best.get(m.group("metric"))
        if cur is None or ver > cur[0]:
            best[m.group("metric")] = (ver, f)
    return {k: v[1] for k, v in best.items()}


def _jsonl(path: Path) -> list[dict]:
    rows = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _points(path: Path) -> list[dict]:
    """A series' points in DAY order (stable): a backfill appends older days after a daily
    publish, so file order is not time order (W-02472911)."""
    return sorted(_jsonl(path), key=lambda p: str(p.get("day", "")))


def _last_two(path: Path) -> list[dict]:
    return _points(path)[-2:]


# ── the waste series' control chart (W-02472911, D-1118) ─────────────────────────────
# XmR individuals chart with FROZEN Phase-I limits: the baseline is the first BASELINE_N judged
# points of the series, or from the newest `kaizen_waste.py --rebaseline` row — rolling limits
# would absorb a sustained regression within BASELINE_N days, the one thing CONTROL must see.
# sigma = MRbar / 1.128 (d2 for n=2). Out of control = beyond 3 sigma, or RUN_N consecutive
# judged points on one side of the centre. A ratio day with fewer than MIN_CLOSES top-level
# closes is plotted, never judged. Categories and formulas: docs/reference/kaizen-waste-define.md.
BASELINE_N = 14
RUN_N = 8
MIN_CLOSES = 20
_RATIO_WASTE = frozenset(
    {"waste_context_per_call", "waste_seat_share", "waste_wall_rate", "waste_output_per_call"}
)
_COUNT_WASTE = frozenset({"waste_red_master_rework"})  # event counts: c-chart, not XmR


def _num(v: object) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def _control(root: Path, series: dict[str, Path]) -> list[str]:
    waste = sorted(m for m in series if m.startswith("waste_"))
    if not waste:
        return []
    breakdown = _jsonl(root / "waste-breakdown@v1.jsonl")
    cut: dict[tuple[str, str], list[dict]] = {}
    for row in breakdown:
        cut.setdefault((str(row.get("day")), str(row.get("metric"))), []).append(row)
    rebase: dict[str, str] = {}
    for row in _jsonl(root / "waste-baselines.jsonl"):
        if isinstance(row.get("metric"), str) and isinstance(row.get("from"), str):
            rebase[row["metric"]] = row["from"]  # the newest row wins
    alarms: list[str] = []
    notes: list[str] = []
    in_control = 0
    for metric in waste:
        pts = [p for p in _points(series[metric]) if _num(p.get("value")) is not None]
        if not pts:
            continue

        def judged(p: dict, metric: str = metric) -> bool:
            if metric not in _RATIO_WASTE:
                return True
            rows = cut.get((str(p.get("day")), metric), [])
            closes = [r for r in rows if r.get("by") == "total" and r.get("key") == "closes"]
            return bool(closes) and (_num(closes[0].get("value")) or 0) >= MIN_CLOSES

        latest = pts[-1]
        if not judged(latest):
            notes.append(
                f"{metric}: {latest.get('day')} under {MIN_CLOSES} closes — plotted, not judged"
            )
            continue
        start = rebase.get(metric, "")
        eligible = [p for p in pts if judged(p) and str(p.get("day")) >= start]
        before = [p for p in eligible if str(p.get("day")) < str(latest.get("day"))]
        base = before[:BASELINE_N]
        if len(base) < BASELINE_N:
            notes.append(f"{metric}: baseline {len(base)}/{BASELINE_N} — no limits yet")
            continue
        vals = [_num(p["value"]) or 0.0 for p in base]
        mean = sum(vals) / len(vals)
        if metric in _COUNT_WASTE:
            # a rare event count (mostly 0) has MRbar 0 and an XmR chart that can never alarm:
            # the c-chart's Poisson sigma = sqrt(cbar); cbar 0 makes any event a signal
            sigma = mean**0.5
        else:
            mrbar = sum(abs(a - b) for a, b in zip(vals[1:], vals[:-1], strict=True)) / (
                len(vals) - 1
            )
            if mrbar == 0:
                notes.append(f"{metric}: flat baseline — no limits")
                continue
            sigma = mrbar / 1.128
        ucl, lcl = mean + 3 * sigma, max(0.0, mean - 3 * sigma)
        v = _num(latest["value"]) or 0.0
        rule = ""
        if v > ucl or v < lcl:
            rule = "beyond 3 sigma"
        else:
            after = [p for p in eligible if str(p.get("day")) > str(base[-1].get("day"))][-RUN_N:]
            sides = {
                (_num(p["value"]) or 0.0) > mean for p in after if (_num(p["value"]) or 0.0) != mean
            }
            if (
                len(after) == RUN_N
                and len(sides) == 1
                and all((_num(p["value"]) or 0.0) != mean for p in after)
            ):
                rule = f"{RUN_N} in a row on one side"
        if not rule:
            in_control += 1
            continue
        tops = []
        for by in ("agent", "command"):
            rows = [r for r in cut.get((str(latest.get("day")), metric), []) if r.get("by") == by]
            total = sum(_num(r.get("numerator")) or 0.0 for r in rows)
            for r in sorted(rows, key=lambda r: -(_num(r.get("numerator")) or 0.0))[:3]:
                share = 100 * (_num(r.get("numerator")) or 0.0) / total if total else 0.0
                tops.append(f"{by}={r.get('key')} {share:.0f}%")
        arrow = "↑" if v > mean else "↓"
        alarms.append(
            f"OUT OF CONTROL {arrow} {metric}: {latest.get('cell') or v} @ {latest.get('day')} "
            f"({rule}; UCL {ucl:.4g}, centre {mean:.4g}, baseline {base[0].get('day')}..{base[-1].get('day')})"
            + (f" — top: {', '.join(tops[:3])}" if tops else "")
        )
    if in_control:
        notes.append(f"CONTROL: {in_control} waste series in control")
    return alarms + notes


def _fmt_delta(cur: dict, prev: dict | None) -> str:
    try:
        cv, pv = float(cur.get("value")), float(prev.get("value")) if prev else None
    except (TypeError, ValueError):
        return ""
    if pv is None:
        return ""
    d = cv - pv
    if abs(d) < 1e-9:
        return " (=)"
    arrow = "↑" if d > 0 else "↓"
    return f" ({arrow}{abs(d):.2g} vs {prev.get('day', 'prev')})"


def compose(state: Path | None = None) -> str:
    root = state or _state_dir()
    series = _latest_series(root)
    if not series:
        return (
            "KAIZEN digest — ⚠️ NO PUBLISHED SERIES in "
            f"{root}/series. The collector has not run (or the store moved): check "
            "~/.claude/kaizen.log and the daily-kaizen-collect cron. An empty digest is a "
            "finding, never a healthy quiet."
        )
    lines = ["KAIZEN daily digest", *_control(root, series)]
    ordered = [m for m in _HEADLINE if m in series] + sorted(
        m for m in series if m not in _HEADLINE
    )
    for metric in ordered:
        pts = _last_two(series[metric])
        if not pts:
            lines.append(f"· {metric}: series file empty")
            continue
        cur = pts[-1]
        prev = pts[-2] if len(pts) == 2 else None
        cell = cur.get("cell") or str(cur.get("value"))
        lines.append(f"· {metric}: {cell} @ {cur.get('day', '?')}{_fmt_delta(cur, prev)}")
    lines.append("detail: ~/.claude/kaizen.log · docs/reference/agents/kaizen-log-*.md")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    text = compose()
    print(text)
    if "--send" in argv:
        helper = REPO / "scripts" / "sysadmin" / "send-telegram.sh"
        r = subprocess.run(["bash", str(helper), text], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            print(
                f"[kaizen_digest] TELEGRAM SEND FAILED: {r.stderr.strip()[:300]}", file=sys.stderr
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
