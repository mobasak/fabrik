"""The dashboard's pure formatters — moved verbatim out of `quota_dashboard` (plan 2026-10-17-plan-1, T02).

Nine helpers today's HTML builders use and the views share: each reads only its arguments, the
clock and the environment, never a module-level name of the dashboard module (an AST scan at
18d619f1e). The dashboard imports them back under their old private names, so its builders and
tests are untouched; a view imports them from here, because no view may import the dashboard module.
`read_ts` is the one helper written for the views: the gate every collector timestamp passes before
`components.freshness`, which refuses a bad one by design.
"""

# AFTER-EDIT: docs/workstation/quota-dashboard.md

from __future__ import annotations

import math
import os
import time
from datetime import datetime
from pathlib import Path

__all__ = [
    "ago",
    "cap",
    "fmt_age",
    "fmt_reset",
    "opt_root",
    "posture_sub",
    "read_ts",
    "repo_order",
    "stage_tone",
    "tone",
]


def opt_root() -> Path:
    return Path(os.environ.get("FABRIK_OPT_DIR") or "/opt")


def ago(ts: object) -> str:
    try:
        s = max(0, int(time.time() - float(ts)))  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return ""
    return (
        f"{s // 60} min ago"
        if s < 3600
        else f"{s // 3600} h ago"
        if s < 172800
        else f"{s // 86400} d ago"
    )


def cap(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def fmt_age(age_s: float | None) -> str:
    if age_s is None:
        return ""
    h = age_s / 3600.0
    return f"cached {h:.0f}h ago" if h >= 1 else f"cached {age_s / 60:.0f}m ago"


def fmt_reset(epoch: float | None) -> str:
    if not epoch:
        return "—"
    dt = datetime.fromtimestamp(float(epoch)).astimezone()
    delta = float(epoch) - time.time()
    if delta <= 0:
        return dt.strftime("%a %d %b %H:%M") + " (due)"
    hours = delta / 3600.0
    left = f"{hours:.0f}h" if hours >= 1 else f"{delta / 60:.0f}m"
    if hours >= 24:
        left = f"{hours / 24:.1f}d"
    return f"{dt.strftime('%a %d %b %H:%M')} · in {left}"


def posture_sub(posture: object, key: str) -> str:
    """The burn and the nearer of wall-or-reset for one window, from the posture file (D-269).

    Empty string when there is nothing to say, so a caller can concatenate it unconditionally. The
    numbers are the tick's own — the board does not re-derive them, because two derivations of one
    fact are two things to drift.
    """
    if not isinstance(posture, dict):
        return ""
    act = posture.get("active") if isinstance(posture.get("active"), dict) else {}
    wins = act.get("windows") if isinstance(act.get("windows"), dict) else {}
    w = wins.get(key)
    if not isinstance(w, dict) or w.get("utilization") is None:
        return ""
    burn = w.get("burn_per_min")
    if not (isinstance(burn, (int, float)) and not isinstance(burn, bool) and math.isfinite(burn)):
        return " · no burn yet"
    verdict = w.get("verdict")
    mins = w.get("minutes_to_wall") if verdict == "wall_first" else w.get("minutes_to_reset")
    if not (isinstance(mins, (int, float)) and not isinstance(mins, bool) and math.isfinite(mins)):
        return f" · {burn:.2f}%/m"
    which = "wall" if verdict == "wall_first" else "reset"
    return f" · {burn:.2f}%/m, {which} in ~{int(mins)}m"


# the latest read time a stamp may show: 2096, under every platform's time_t and datetime range
READ_TS_MAX = 4e9


def read_ts(x: object) -> float | None:
    """A collector's read time as epoch seconds a freshness stamp can show, or None.

    Anything but a finite real number in (0, `READ_TS_MAX`) — a bool, a string, NaN, infinity, a
    negative or a far-future value — is None, which `components.freshness` renders as "not read",
    so one broken timestamp costs its region the stamp instead of raising out of the whole view.
    """
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    try:
        v = float(x)
    except OverflowError:  # an int past float's range
        return None
    return v if math.isfinite(v) and 0 < v < READ_TS_MAX else None


def repo_order(repos: list[dict]) -> list[dict]:
    """fabrik first, then by remaining count (desc), then by name."""
    return sorted(repos, key=lambda r: (r["name"] != "fabrik", -len(r["items"]), r["name"]))


def stage_tone(stage: str) -> str:
    if stage == "gate":
        return "crit"
    if stage == "utility":
        return "stale"
    return "cap"


def tone(remaining: float) -> str:
    if remaining <= 5:
        return "crit"
    if remaining <= 25:
        return "warn"
    return "ok"
