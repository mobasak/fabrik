"""The dashboard's pure formatters — moved verbatim out of `quota_dashboard` (plan 2026-10-17-plan-1, T02).

Nine helpers the views share: each reads only its arguments, the clock, the environment and the
string catalogue (every word they return is a `strings.t` key, so a stand-in catalogue reaches them
too), never a module-level name of the dashboard module (an AST scan at 18d619f1e). A view imports
them from here, because no view may import the dashboard module.
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

from .strings import t

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
    if s < 3600:
        return t("fmt.ago_min", n=s // 60)
    return t("fmt.ago_h", n=s // 3600) if s < 172800 else t("fmt.ago_d", n=s // 86400)


def cap(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def fmt_age(age_s: float | None) -> str:
    if age_s is None:
        return ""
    h = age_s / 3600.0
    return t("fmt.cached_h", n=f"{h:.0f}") if h >= 1 else t("fmt.cached_m", n=f"{age_s / 60:.0f}")


def fmt_reset(epoch: float | None) -> str:
    if not epoch:
        return t("fmt.reset_none")
    dt = datetime.fromtimestamp(float(epoch)).astimezone()
    when = dt.strftime("%a %d %b %H:%M")
    delta = float(epoch) - time.time()
    if delta <= 0:
        return t("fmt.reset_due", when=when)
    hours = delta / 3600.0
    if hours >= 24:
        left = t("fmt.left_d", n=f"{hours / 24:.1f}")
    elif hours >= 1:
        left = t("fmt.left_h", n=f"{hours:.0f}")
    else:
        left = t("fmt.left_m", n=f"{delta / 60:.0f}")
    return t("fmt.reset_in", when=when, left=left)


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
        return t("fmt.no_burn")
    verdict = w.get("verdict")
    mins = w.get("minutes_to_wall") if verdict == "wall_first" else w.get("minutes_to_reset")
    if not (isinstance(mins, (int, float)) and not isinstance(mins, bool) and math.isfinite(mins)):
        return t("fmt.burn", burn=f"{burn:.2f}")
    key = "fmt.burn_wall" if verdict == "wall_first" else "fmt.burn_reset"
    return t(key, burn=f"{burn:.2f}", mins=int(mins))


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
