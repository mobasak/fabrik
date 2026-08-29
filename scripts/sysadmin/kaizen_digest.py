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


def _last_two(path: Path) -> list[dict]:
    pts = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            pts.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return pts[-2:]


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
    lines = ["KAIZEN daily digest"]
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
    lines.append(
        "detail: ~/.claude/kaizen.log · docs/reference/agents/kaizen-log-*.md"
    )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    text = compose()
    print(text)
    if "--send" in argv:
        helper = REPO / "scripts" / "sysadmin" / "send-telegram.sh"
        r = subprocess.run(["bash", str(helper), text], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            print(f"[kaizen_digest] TELEGRAM SEND FAILED: {r.stderr.strip()[:300]}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
