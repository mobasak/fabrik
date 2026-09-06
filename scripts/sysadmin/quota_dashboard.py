#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/quota-dashboard.md, PORTS.md, docs/workstation/claude-account-rotation.md
#
# The account-quota dashboard: a localhost page showing every Claude account's session +
# weekly headroom, reset times, the active pointer, caps and warnings — the `--status` board
# rendered for a browser tab the operator leaves open.
#
# DESIGN — why there is no regeneration cron:
#   `claude_rotate.py --status --json` makes live API probes for fresh-token dirs. A */5 cron
#   would probe forever whether or not anyone is looking, and a self-refreshing browser tab
#   would probe on every reload. So the page is regenerated ON DEMAND, at most once per
#   QUOTA_DASH_MAX_AGE_S (default 240s): open tabs stay current, a closed tab costs nothing,
#   and refresh-spamming the page cannot multiply probe volume. The rendered page always
#   states the age of its own data — a stale render is visible, never silent.
#
# The server is stdlib-only, binds loopback by default, and is kept alive by cron
# (@reboot + a periodic --ensure). It never writes outside its own output dir and never
# touches credential files: every rotation fact comes from shelling the rotation CLI, which
# owns that contract. ONE write path exists (2026-09-02): the per-row "switch" button POSTs
# /switch, which shells `claude_rotate.py --switch <slug>` — a manual flip through the same
# code the operator runs by hand. The endpoint refuses a request without the custom
# SWITCH_HEADER (a forged cross-origin POST from any page in the operator's browser cannot
# carry one without a CORS preflight this server never answers) and a slug the board's own
# last payload does not list. The flip is pause-, dwell- and cap-exempt (the CLI's
# manual=True path) — the operator's deliberate act, never automation.
"""Serve/generate the Claude account-quota dashboard (see module header)."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROTATE_CLI = Path(
    os.getenv("QUOTA_DASH_ROTATE_CLI", "/opt/fabrik/scripts/sysadmin/claude_rotate.py")
)
OUT_DIR = Path(os.getenv("QUOTA_DASH_OUT_DIR", str(Path.home() / ".claude" / "quota-dashboard")))
HOST = os.getenv("QUOTA_DASH_HOST", "127.0.0.1")
PORT = int(os.getenv("QUOTA_DASH_PORT", "5051"))
MAX_AGE_S = float(os.getenv("QUOTA_DASH_MAX_AGE_S", "20"))
PROBE_TIMEOUT_S = float(os.getenv("QUOTA_DASH_PROBE_TIMEOUT_S", "60"))
REFRESH_S = int(os.getenv("QUOTA_DASH_REFRESH_S", "20"))
# Operator rules 2026-09-03: the SERVER probes every 20s whether or not a page is open, and
# invokes the rotation tick the moment the active account crosses the flip threshold on its 5h
# window (or is cap-walled) — the cron tick (*/5) stays as the backstop; the board is the fast path.
PROBE_INTERVAL_S = float(os.getenv("QUOTA_DASH_PROBE_INTERVAL_S", "20"))
TRIGGER_THRESHOLD = float(
    os.getenv("ROTATE_THRESHOLD", "95")
)  # the tick's own default (claude_rotate._rotate_threshold) — keep the two literals equal
TRIGGER_COOLDOWN_S = float(os.getenv("QUOTA_DASH_TRIGGER_COOLDOWN_S", "120"))
# The URGENT-DRAIN tier (operator rule 2026-09-03): at/over 90% session the tick must run within
# one probe interval so that, if NO successor is eligible, every repo gets the "stop gracefully,
# hook to the next reset" mail in seconds, not in the cron's 5 minutes. Its cooldown is SEPARATE
# from the flip tier's: a drain tick at 90 must never delay the flip tick at 95 by up to two
# minutes (a burst can cover 95→100 in that time).
DRAIN_TRIGGER_THRESHOLD = float(os.getenv("ROTATE_URGENT_DRAIN_PCT", "90"))
# The BLIND bar (2026-09-03 20:10): `--status --json` timed out seven times in a row (60 s each)
# while ob@ burned 96 → 100, and the last GOOD reading (96 < 98) never re-armed the trigger. When
# the probe is failing the last good reading is minutes old, so the bar drops to the drain line
# and the TICK reads live for itself; the cooldown bounds the blind path exactly like the sighted one.
BLIND_TRIGGER_THRESHOLD = float(os.getenv("ROTATE_DRAIN_THRESHOLD", "85"))
TICK_TIMEOUT_S = float(os.getenv("QUOTA_DASH_TICK_TIMEOUT_S", "180"))
# The SAME lock the cron line takes (`flock -n $HOME/.claude/state/rotate.lock … --tick`): two ticks
# deciding at once is the double-flip race, so the board's tick is skipped while a cron tick holds it.
ROTATE_LOCK = Path(
    os.getenv("QUOTA_DASH_ROTATE_LOCK", str(Path.home() / ".claude" / "state" / "rotate.lock"))
)
SWITCH_HEADER = "X-Quota-Dash"  # required on POST /switch — a custom header forces a CORS preflight
SWITCH_TIMEOUT_S = float(os.getenv("QUOTA_DASH_SWITCH_TIMEOUT_S", "90"))
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_MAX_BODY = 4096

# The quota windows themselves. A cached reading older than its own window describes a window
# that has fully rolled over — reported as unknown, never as a reassuring percentage.
_FIVE_HOUR_S = 5 * 3600
_SEVEN_DAY_S = 7 * 86400

_HTML = OUT_DIR / "index.html"
_JSON = OUT_DIR / "quota.json"
# The fleet's active-account pointer (a symlink). Read on every view so a flip — by the tick, a
# --switch, or the button — regenerates the board at once instead of waiting out the floor.
_POINTER = Path(os.getenv("QUOTA_DASH_POINTER", str(Path.home() / ".claude-fleet" / "active")))

# ── The OpenRouter pool balance: the fleet's OTHER quota ──────────────────────────────────────
# Until 2026-09-04 nothing on this box watched it. The pool ran to -$0.0015 of $225 and three
# repos discovered it by hitting HTTP 402 mid-run — one lost 24 grounder units, another's closing
# review sweep fell back to a lane that records nothing to the flywheel. This board already polls
# every 20s and the key is already on disk, so the balance is one GET away. It is a LEVEL, not a
# projection: 402 "Insufficient credits" is issued on balance, so the number is the direct signal
# rather than a proxy for one. (The burn RATE lives in the flywheel's Postgres rows — intel's
# beat — so no runway estimate is made here rather than one that cannot be defended.)
CREDITS_KEY_FILE = Path(
    os.getenv(
        "QUOTA_DASH_CREDITS_KEY_FILE",
        str(Path.home() / ".config" / "fabrik" / "subagents.env"),
    )
)
CREDITS_URL = os.getenv("QUOTA_DASH_CREDITS_URL", "https://openrouter.ai/api/v1/credits")
# Credits move only when something spends. At the 20s page refresh an uncached read would be
# 4,320 calls a day to learn a number that changes a few times an hour.
CREDITS_TTL_S = float(os.getenv("QUOTA_DASH_CREDITS_TTL_S", "300"))
CREDITS_TIMEOUT_S = float(os.getenv("QUOTA_DASH_CREDITS_TIMEOUT_S", "10"))
# An absolute floor, not a percentage: after a top-up the percentage is meaningless ($20 of $245
# reads as 8% and is the whole runway). Roughly a few fan-outs of warning.
CREDITS_WARN_USD = float(os.getenv("POOL_CREDITS_WARN_USD", "5"))
CREDITS_CACHE = OUT_DIR / "pool-credits.json"
CREDITS_STAMP = OUT_DIR / "pool-credits-drained"  # the once-per-episode latch
_KEY_RE = re.compile(r"^\s*(?:export\s+)?OPENROUTER_API_KEY\s*=\s*[\'\"]?([^\'\"\s#]+)", re.M)


def _openrouter_key() -> str | None:
    """The pool key, from the environment or the subagents env file. Never logged, never
    rendered, never written to the cache — the only thing that leaves this function is a
    balance."""
    key = os.getenv("OPENROUTER_API_KEY")
    if key and key.strip():
        return key.strip()
    try:
        m = _KEY_RE.search(CREDITS_KEY_FILE.read_text(encoding="utf-8"))
    except OSError:
        return None
    return m.group(1) if m else None


def _credits_get(key: str) -> dict:
    """One GET. Isolated so the cache/fallback logic above it is testable without a network."""
    req = urllib.request.Request(CREDITS_URL, headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=CREDITS_TIMEOUT_S) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _pool_credits(now: float | None = None, *, fetch: bool = True) -> dict | None:
    """``{granted, used, remaining, ts, age_s, stale}`` or None when the pool is not configured.

    Cached in ``CREDITS_CACHE`` for ``CREDITS_TTL_S``. FAIL-SOFT in the same direction as the
    account table: a dead endpoint serves the last known balance MARKED STALE with its age, because
    a number with a date on it beats a blank when the operator is deciding whether work can run.
    """
    now = time.time() if now is None else now
    cached: dict | None
    try:
        raw = json.loads(CREDITS_CACHE.read_text(encoding="utf-8"))
        cached = raw if isinstance(raw, dict) else None
    except (OSError, ValueError):
        cached = None
    if cached is not None and isinstance(cached.get("ts"), (int, float)):
        age = now - float(cached["ts"])
        if 0.0 <= age < CREDITS_TTL_S:
            return {**cached, "age_s": age, "stale": False}
    if not fetch:
        # RENDER PATH: cache only, never a network call. The GET is up to CREDITS_TIMEOUT_S and
        # _generate_locked holds _gen_lock, so fetching here would put a third-party endpoint on
        # the board's critical path — the exact shape of the 2026-08-18 hang, where a stalled
        # probe made every page load sit for its full timeout and the operator read the dashboard
        # as "not reachable". The refresher below keeps this cache warm off the lock.
        if cached is not None and isinstance(cached.get("ts"), (int, float)):
            return {**cached, "age_s": now - float(cached["ts"]), "stale": True}
        return None
    key = _openrouter_key()
    if key is None:
        return None  # the pool is not configured on this box — not an error, just nothing to show
    try:
        data = (_credits_get(key) or {}).get("data") or {}
        granted, used = float(data["total_credits"]), float(data["total_usage"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        sys.stderr.write(f"quota_dashboard: pool-credits probe failed ({type(exc).__name__})\n")
        if cached is not None and isinstance(cached.get("ts"), (int, float)):
            return {**cached, "age_s": now - float(cached["ts"]), "stale": True}
        return None
    fresh = {"granted": granted, "used": used, "remaining": granted - used, "ts": now}
    try:
        CREDITS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        CREDITS_CACHE.write_text(json.dumps(fresh), encoding="utf-8")
    except OSError:
        pass  # a lost cache costs one extra GET, never the reading
    return {**fresh, "age_s": 0.0, "stale": False}


def _pool_credits_panel(credits: dict | None) -> str:
    """The board row. Says what the operator will SEE when it runs out, not merely that a number
    is low — "$0.00 remaining" and "every fanout returns 402" are different sentences to act on."""
    if not credits:
        return ""
    remaining = float(credits.get("remaining") or 0.0)
    granted = float(credits.get("granted") or 0.0)
    if remaining <= 0:
        tone = "crit"
        note = (
            " — EXHAUSTED: every <code>fanout()</code> returns HTTP 402 with no output and no "
            "spend. Top up at openrouter.ai/settings/credits."
        )
    elif remaining <= CREDITS_WARN_USD:
        tone = "warn"
        note = (
            f" — under ${CREDITS_WARN_USD:,.0f}; a long fan-out will hit HTTP 402 mid-run. "
            "Top up at openrouter.ai/settings/credits."
        )
    else:
        tone = "ok"
        note = ""
    age = ""
    if credits.get("stale"):
        age = f" · {escape(_fmt_age(float(credits.get('age_s') or 0.0)))}, endpoint unreachable"
    return (
        f'<section class="gov banner {tone}"><b>OpenRouter pool</b> — '
        f"${remaining:,.2f} remaining of ${granted:,.2f}{age}{note}</section>"
    )


def _notify(msg: str) -> None:
    """The box's mesh-notify path, same as the rotation tick's. Best-effort by design."""
    sound = Path.home() / ".claude" / "bin" / "claude-sound.sh"
    if not sound.is_file():
        return
    try:
        subprocess.run(
            ["bash", str(sound), "mesh-notify", "pool-credits", "/opt/fabrik", msg],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _maybe_alert_pool_credits(credits: dict | None) -> None:
    """One message per drain episode, re-armed the moment the balance recovers.

    The latch the fleet wall advisory taught us: an alert that repeats every 20s is an alert
    everyone filters, and a latch with no re-arm goes silent through the NEXT incident. An unknown
    balance (no key, unreadable endpoint with no cache) is silence, never a false alarm.
    """
    if not credits:
        return
    remaining = float(credits.get("remaining") or 0.0)
    if remaining > CREDITS_WARN_USD:
        CREDITS_STAMP.unlink(missing_ok=True)  # relief arrived → re-arm for the next drain
        return
    if CREDITS_STAMP.exists():
        return  # already said it for this episode
    _notify(
        f"OpenRouter pool ${remaining:,.2f} remaining"
        + (" — EXHAUSTED" if remaining <= 0 else f" (under ${CREDITS_WARN_USD:,.0f})")
        + ". Every fanout() will return HTTP 402 with no output; pool-default fan-out is dead "
        "fleet-wide until it is topped up at openrouter.ai/settings/credits."
    )
    try:
        CREDITS_STAMP.parent.mkdir(parents=True, exist_ok=True)
        CREDITS_STAMP.write_text(str(int(time.time())), encoding="utf-8")
    except OSError:
        pass


_credits_lock = threading.Lock()


def _refresh_pool_credits() -> None:
    """TTL-gated fetch + the drain advisory, run OFF the render path and OFF ``_gen_lock``.

    The probe loop calls this once per cycle in its own daemon thread, so a slow or hanging
    OpenRouter endpoint can delay neither the account probe's cadence nor a page load. Overlapping
    calls are dropped rather than queued — one in flight is enough for a number that moves a few
    times an hour.
    """
    if not _credits_lock.acquire(blocking=False):
        return
    try:
        _maybe_alert_pool_credits(_pool_credits())
    except (OSError, ValueError, TypeError) as exc:
        sys.stderr.write(f"quota_dashboard: pool-credits refresh: {type(exc).__name__}\n")
    finally:
        _credits_lock.release()


def _credits_async() -> threading.Thread | None:
    """Start one refresher; drop the request if one is already running. Returns the thread so a
    test can join it instead of racing it."""
    if _credits_lock.locked():
        return None
    th = threading.Thread(target=_refresh_pool_credits, daemon=True, name="quota-credits")
    th.start()
    return th


def _pointer_slug() -> str | None:
    try:
        return os.path.basename(os.readlink(_POINTER)) or None
    except OSError:
        return None


def _rendered_active() -> str | None:
    try:
        val = json.loads(_JSON.read_text(encoding="utf-8")).get("active")
    except (OSError, ValueError):
        return None
    return str(val) if val else None


def _pointer_moved() -> bool:
    """True when the live pointer disagrees with the last rendered payload — a flip happened
    since the render. Unknown on either side → False (never a probe storm on a missing file)."""
    live, rendered = _pointer_slug(), _rendered_active()
    return bool(live and rendered and live != rendered)


def _probe() -> dict:
    """One `--status --json` run. Raises on failure — the caller decides fallback."""
    proc = subprocess.run(
        [sys.executable, str(ROTATE_CLI), "--status", "--json"],
        capture_output=True,
        text=True,
        timeout=PROBE_TIMEOUT_S,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"rotate CLI exited {proc.returncode}: {proc.stderr.strip()[:200]}")
    return json.loads(proc.stdout)


def _fmt_reset(epoch: float | None) -> str:
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


def _fmt_age(age_s: float | None) -> str:
    if age_s is None:
        return ""
    h = age_s / 3600.0
    return f"cached {h:.0f}h ago" if h >= 1 else f"cached {age_s / 60:.0f}m ago"


def _bar(remaining: float, tone: str) -> str:
    return f'<div class="bar"><span class="fill {tone}" style="width:{max(0.0, min(100.0, remaining)):.1f}%"></span></div>'


def _tone(remaining: float) -> str:
    if remaining <= 5:
        return "crit"
    if remaining <= 25:
        return "warn"
    return "ok"


def _row(acct: dict, active: str | None, rank: str | None = None) -> str:
    email = str(acct.get("email", "?"))
    slug = (acct.get("slugs") or ["?"])[0]
    is_active = bool(active) and slug == active
    five = acct.get("five_hour") or {}
    seven = acct.get("seven_day") or {}
    s_used = five.get("utilization")
    w_used = seven.get("utilization")
    s_left = 100.0 - float(s_used) if s_used is not None else None
    w_left = 100.0 - float(w_used) if w_used is not None else None
    cap = acct.get("weekly_cap")
    cap_walled = bool(acct.get("cap_walled"))
    walled = w_used is not None and float(w_used) >= 100.0
    stale = _fmt_age(acct.get("age_s")) if acct.get("source") == "cache" else ""

    badges = []
    if is_active:
        badges.append('<span class="badge active">ACTIVE</span>')
    elif rank:
        tone = "cap" if rank == "NEXT" else ""
        badges.append(f'<span class="badge {tone}">{escape(rank)}</span>')
    if cap is not None:
        badges.append(f'<span class="badge cap">cap {int(cap)}%</span>')
    if cap_walled:
        badges.append('<span class="badge crit">RESERVED — fleet excluded</span>')
    elif walled:
        badges.append('<span class="badge crit">WALLED</span>')
    if stale:
        badges.append(f'<span class="badge stale">{escape(stale)}</span>')

    def cell(
        left: float | None, used: float | None, reset: float | None, window_s: float | None = None
    ) -> str:
        if left is None:
            return '<td class="num muted">no reading<br><span class="sub">—</span></td>'
        # A cached reading OLDER than the window it describes measures a window that has since
        # rolled over — so the NUMBER is not evidence. But the value is still derivable: an
        # account that is not the active pointer cannot be burning FLEET quota (no session binds
        # to it), so its rolled-over window is empty by construction. Say that, rather than
        # printing an unearned percentage ("plenty free" — the permanently-green class) or a
        # useless "unknown". The one blind spot is the operator's own claude.ai browser use,
        # which no probe of ours can see — surfaced on capped accounts, which exist for exactly
        # that reason.
        age = acct.get("age_s")
        # A cached reading is stale-past-rollover if EITHER its age exceeds the window OR the
        # reading's own reset time has already passed. The second clause is the failure the
        # operator hit: a ~47h cache of a 7-DAY window (age < window) whose weekly reset date is
        # already in the past still printed "91% used, resets <past date> (due)" — but that window
        # HAS rolled over, so the number is no longer evidence.
        reset_passed = reset is not None and float(reset) <= time.time()
        if acct.get("source") == "cache" and (
            reset_passed or (window_s and isinstance(age, (int, float)) and age >= window_s)
        ):
            blind = (
                " · browser use is not visible here" if acct.get("weekly_cap") is not None else ""
            )
            note = (
                f"idle — not the active pointer, so no fleet usage since this window rolled{blind}"
                if not is_active
                else "last read "
                + escape(_fmt_age(age))
                + ", older than the "
                + (f"{window_s / 3600:.0f}h window" if window_s else "window")
                + " — re-reads on next use"
            )
            label = "idle" if not is_active else "unknown"
            tone_i = "ok" if not is_active else "warn"
            return (
                f'<td class="num"><span class="pct {tone_i}">{label}</span>'
                f"{_bar(100.0 if not is_active else 0.0, tone_i)}"
                f'<span class="sub">{note}</span></td>'
            )
        tone = _tone(left)
        return (
            f'<td class="num"><span class="pct {tone}">{left:.0f}%</span> left'
            f"{_bar(left, tone)}"
            f'<span class="sub">{used:.0f}% used · resets {escape(_fmt_reset(reset))}</span></td>'
        )

    # Fable-5's separate weekly limit (from the usage `limits` array, keyed by display_name).
    # Rendered in its OWN column with the same remaining-framing as Weekly; a cache-served account
    # that has no Fable reading yet (idle, token not refreshed) shows "no reading" until the tick
    # re-probes it, exactly like any other window.
    fable = (acct.get("model_windows") or {}).get("Fable") or {}
    f_used = fable.get("utilization")
    f_left = 100.0 - float(f_used) if f_used is not None else None

    return (
        f'<tr class="{"is-active" if is_active else ""}">'
        f'<td class="acct"><strong>{escape(email)}</strong><span class="sub">{escape(slug)}</span>'
        f'<div class="badges">{"".join(badges)}</div></td>'
        f"{cell(s_left, s_used, five.get('resets_at_epoch'), _FIVE_HOUR_S)}"
        f"{cell(w_left, w_used, seven.get('resets_at_epoch'), _SEVEN_DAY_S)}"
        f"{cell(f_left, f_used, fable.get('resets_at_epoch'), _SEVEN_DAY_S)}"
        f"{_switch_cell(slug, is_active)}"
        "</tr>"
    )


def _pending_row(slug: str) -> str:
    """A dir `--new-dir` scaffolded that has not had its ONE `/login` yet.

    `--status --json` reports such a dir under `pending`, not `accounts` — it has no identity to
    group by and no quota to read. The board used to read only `accounts`, so the operator who
    had just scaffolded `ozgurbasak` (2026-09-06) saw a four-row board and could not tell "not
    scaffolded" from "not logged in". Rendered greyed, after every account, with NO switch button
    (there is no chain to switch to) and the one action that pins it."""
    if not _SLUG_RE.match(slug):
        return ""
    s = escape(slug)
    no = '<td class="num muted">no reading<br><span class="sub">—</span></td>'
    return (
        '<tr class="is-pending">'
        f'<td class="acct"><strong>{s}</strong><span class="sub">pending-login</span>'
        '<div class="badges"><span class="badge stale">pending-login — identity unverified</span>'
        "</div></td>"
        f"{no}{no}{no}"
        f'<td class="act"><span class="muted">ONE <code>/login</code> in this dir pins it</span></td>'
        "</tr>"
    )


def _switch_cell(slug: str, is_active: bool) -> str:
    """The manual-rotation control: a button on every row that is NOT the active pointer.
    The active row shows nothing clickable — switching to the account you are already on is
    not a rotation, and a button there would only invite a misclick."""
    if is_active or not _SLUG_RE.match(slug):
        return '<td class="act"><span class="muted">active</span></td>'
    return (
        f'<td class="act"><button type="button" class="switch" data-slug="{escape(slug)}" '
        f'title="Make {escape(slug)} the active account for every session">switch →</button></td>'
    )


_RESERVE_PCT = float(os.getenv("QUOTA_RESERVE_PCT", "80"))


def _unclassified_warning(p: dict) -> str:
    """Tokens no tier claimed, said OUT LOUD — everything else on this panel silently excludes them.

    `claude_p_cost._tier_of` matches the four tier NAMES inside a model id. A Claude model named
    outside that vocabulary — Mythos is already one, in Anthropic's own cache-pricing footnote —
    classifies as nothing: its tokens leave the tier table, the cost split AND the calendar with no
    visible trace. The producer has always published them under `unweighted`; this view never
    rendered it, so the omission was invisible by construction. The gap sharpened the moment empty
    months stopped being drawn (D-140): such a month used to appear as a row of blank cells a reader
    might question, and now it does not appear at all.

    Returns "" when nothing is unclassified — a warning that shows when nothing is wrong is
    wallpaper, and wallpaper is how the real one gets read past.
    """
    unc = p.get("unweighted")
    if not isinstance(unc, dict):
        return ""
    tok = sum(int(v) for v in unc.values() if isinstance(v, (int, float)))
    if not tok:
        return ""
    return (
        "<p class='intro' style='color:var(--crit)'>&#9888; <b>"
        f"{tok:,} tokens are NOT in any total on this page</b> &mdash; no tier matched "
        f"{escape(', '.join(sorted(unc)))}. Add the tier to <code>_TIER_WEIGHT</code> in "
        "<code>scripts/claude_p_cost.py</code>; until then that spend is unallocated and those days "
        "are missing from the calendar.</p>"
    )


def _spend_panel() -> str:
    """The Usage tab: tier-weighted subscription spend + a daily token calendar.

    Operator directive 2026-09-05 — measure ALL Claude Code / `claude -p` usage, price it per TIER
    (haiku 1x, sonnet 2x, opus 5x, fable 10x), give it its own tab, and give the daily view a hover
    detail like the Claude Manager extension so that extension can be retired.

    BY TIER, NOT BY MODEL VERSION: every Opus generation shares one weight because they share one
    list price -- verified live, Opus 5 and Opus 4.8 are both $5/$25, Fable 5 and Fable 5.1 both
    $10/$50. The concrete ids that rolled into each tier are shown beside it, because a total whose
    members you cannot see is unverifiable.

    Reads the sidecar, never recomputes (`--refresh` runs on the 06:00 cron). A missing or
    old-format sidecar renders NOTHING rather than a zeroed table that would read as "$0 spent" —
    with ONE exception: `_unclassified_warning` survives that path, because tokens no tier claims are
    exactly what empties `tiers`, and going silent there hides the reason for the silence.
    """
    try:
        d = json.loads(_COST_SIDECAR.read_text(encoding="utf-8"))
        p = d.get("per_model_spend") or {}
        tiers, daily = p.get("tiers") or {}, p.get("daily") or []
        spend, base = p.get("spend_usd"), p.get("base_rate_per_mtok")
        unclassified = _unclassified_warning(p)
        if not tiers or not spend or not base:
            # The warning SURVIVES the blank-panel path, and that is the whole point of computing it
            # here rather than beside the table. Tokens no tier claims are exactly what empties
            # `tiers` — so the one state where every token is unrecognised is the one state where
            # the panel would otherwise go silent, taking the explanation with it.
            return unclassified
    except (OSError, ValueError, TypeError, AttributeError):
        return ""

    rows = []
    for tier, v in sorted(tiers.items(), key=lambda kv: -(kv[1].get("cost_usd") or 0)):
        rows.append(
            f"<tr><td><b>{escape(tier)}</b></td>"
            f"<td class='num'>{v.get('weight', 0):.0f}&times;</td>"
            f"<td class='num'>{v.get('tokens', 0):,}</td>"
            f"<td class='num'>{(v.get('share') or 0) * 100:.1f}%</td>"
            f"<td class='num'>${v.get('rate_per_mtok', 0):.5f}</td>"
            f"<td class='num'><b>${v.get('cost_usd', 0):,.2f}</b></td></tr>"
        )
    total = sum(v.get("cost_usd") or 0 for v in tiers.values())
    tok = sum(v.get("tokens") or 0 for v in tiers.values())
    ok = abs(total - spend) < 0.01
    recon = (
        f"<span style='color:var(--ok)'>reconciles to ${spend:,.2f}</span>"
        if ok
        else f"<span style='color:var(--crit)'>DOES NOT reconcile: ${total:,.2f} vs ${spend:,.2f}</span>"
    )

    # ── the calendar: one block per MONTH, newest first ──────────────────────────────────────────
    # Grouped by whatever months the data contains, so a NEW MONTH APPEARS ON ITS OWN — nothing here
    # enumerates months, and none has to be added when the year turns.
    #
    # Intensity scales to the PEAK day across all history, not an absolute token count: an absolute
    # scale makes every cell the same shade the moment fleet volume shifts, which is how a heatmap
    # stops carrying information. `title=` gives native hover detail — no JS, no tooltip library —
    # which is the Claude Manager behaviour being replaced.
    import calendar as _cal
    import datetime as _dt

    peak = max((x.get("tokens") or 0) for x in daily) if daily else 0
    by_month: dict[str, list] = {}
    for x in daily:
        by_month.setdefault((x.get("date") or "")[:7], []).append(x)

    blocks = []
    for ym in sorted(by_month, reverse=True):  # newest month at the top, going back
        entries = sorted(by_month[ym], key=lambda e: e.get("date") or "")
        m_tok = sum(e.get("tokens") or 0 for e in entries)
        m_cost = sum(e.get("cost_usd") or 0 for e in entries)
        first = _dt.date.fromisoformat(entries[0]["date"])
        # Lead the grid with blanks so the 1st lands under its real weekday — a month grid that does
        # not line up with the week is a bar chart wearing a calendar's clothes.
        pad = "".join("<div class='cal-pad'></div>" for _ in range(first.weekday()))
        cells = []
        for e in entries:
            t = e.get("tokens") or 0
            lvl = 0 if not t or not peak else min(4, int(t / peak * 4) + 1)
            by = e.get("by_tier") or {}
            detail = " | ".join(f"{k} {v / 1e9:.2f}B" for k, v in by.items() if v) or "no usage"
            tip = f"{e.get('date', '')}\n{t:,} tokens - ${e.get('cost_usd', 0):,.2f}\n{detail}"
            day_n = _dt.date.fromisoformat(e["date"]).day
            cells.append(
                f"<div class='cal-cell lvl{lvl}' title='{escape(tip)}'><span>{day_n}</span></div>"
            )
        label = f"{_cal.month_name[first.month]} {first.year}"
        # A partial month is MARKED, not silently smaller: September is in progress and May's history
        # starts on the 13th, so both are allocated fee x coverage. Without the marker the reader
        # cannot tell a cheap month from an incomplete one.
        # The fee that applied in this month, shown for context. It is NOT what the block totals to:
        # days are priced on a ROLLING 30-day window, so a month sums to what its days consumed at
        # the rate prevailing around them, not to that month's invoice.
        fee = (p.get("monthly_spend") or {}).get(ym)
        part = f" &middot; <span class='muted'>fee ${fee:,.0f}/mo</span>" if fee else ""
        blocks.append(
            f"<div class='cal-month'><div class='cal-head'><b>{escape(label)}</b>"
            f"<span class='muted'>{m_tok / 1e9:,.1f}B tokens &middot; ${m_cost:,.2f}{part}</span></div>"
            f"<div class='cal-dow'>"
            + "".join(f"<i>{d}</i>" for d in ("M", "T", "W", "T", "F", "S", "S"))
            + f"</div><div class='cal'>{pad}{''.join(cells)}</div></div>"
        )
    legend = "".join(f"<i class='cal-cell lvl{i}'></i>" for i in range(5))
    cal = (
        "<h2>Daily token consumption</h2>"
        f"<p class='intro'>Every recorded day, newest month first, shaded against the busiest day "
        f"({peak:,} tokens). <b>Hover a day</b> for its exact tokens, allocated cost and per-tier "
        "split. Every day is priced on a <b>rolling 30-day window ending that day</b> — the fee "
        "pro-rated across the months it crosses, over the tokens actually run in it — so a month "
        "block totals what its days consumed at the rate prevailing around them, not that month's "
        "invoice.</p>"
        f"<div class='cal-months'>{''.join(blocks)}</div>"
        f"<p class='intro' style='margin-top:10px'>less {legend} more</p>"
    )
    win = f"{p.get('window_start')} to {p.get('window_end')}"
    built = d.get("built_at") or "-"
    # WHY THE HEADLINE IS NOT THE MONTHLY FEE. The window is a ROLLING 30 days, so it straddles two
    # months whose daily rates differ — a $800 fee is $25.81/day across a 31-day August and
    # $26.67/day across a 30-day September. The sum over 30 such days is therefore never exactly the
    # monthly fee, and reading "$778.49" as the subscription price is the obvious misreading (the
    # operator made it on sight, 2026-09-06, which is the evidence this sentence needed writing).
    # Fail-soft: an unparseable window or a month whose fee the sidecar does not carry drops the
    # breakdown and keeps the number.
    fee_now, win_days, fee_note = 0.0, 0, ""
    try:
        ws = _dt.date.fromisoformat(str(p.get("window_start")))
        we = _dt.date.fromisoformat(str(p.get("window_end")))
        fees = p.get("monthly_spend") or {}
        win_days = (we - ws).days + 1
        per_month: dict[str, int] = {}
        for n in range(win_days):
            per_month[(ws + _dt.timedelta(days=n)).strftime("%Y-%m")] = (
                per_month.get((ws + _dt.timedelta(days=n)).strftime("%Y-%m"), 0) + 1
            )
        fee_now = float(fees.get(we.strftime("%Y-%m")) or 0.0)
        parts = []
        for ym, n in sorted(per_month.items()):
            fee = fees.get(ym)
            if fee is None:
                parts = []
                break
            y, m = int(ym[:4]), int(ym[5:7])
            dim = (_dt.date(y + (m == 12), (m % 12) + 1, 1) - _dt.date(y, m, 1)).days
            parts.append(
                f"{n} {_cal.month_name[m]} day{'s' if n != 1 else ''} at ${fee:,.0f}/{dim}"
            )
        fee_note = escape(" + ".join(parts))
    except (ValueError, TypeError, AttributeError):
        fee_now, win_days, fee_note = 0.0, 0, ""
    priced = (
        f"priced against <b>${spend:,.2f}</b> &mdash; what the <b>${fee_now:,.0f}/month</b> "
        f"subscription costs over THESE {win_days} days ({fee_note}), since a rolling window is "
        "not a calendar month"
        if (fee_now and win_days and fee_note)
        # never assert a breakdown we could not derive
        else f"priced against <b>${spend:,.2f}</b> for that window"
    )
    return (
        "<h2>Claude subscription &mdash; spend by tier</h2>"
        f"<p class='intro'>All Claude Code / <code>claude -p</code> usage over <b>{escape(win)}</b> "
        f"({tok:,} tokens), {priced} &mdash; using "
        f"<b>haiku 1&times; &middot; sonnet 2&times; &middot; opus 5&times; &middot; fable "
        f"10&times;</b>. Base ${base:.6f}/MTok at weight 1. &Sigma; {recon}. "
        "&#9888; An <b>allocation, not an invoice</b> &mdash; the subscription is a flat fee with no "
        "per-model billing; the weights are an operator assumption matching the list-price ratio "
        f"1:2:5:10. Rebuilt by the 06:00 cron; last built {escape(str(built))}.</p>"
        "<table><thead><tr><th>Tier</th><th>Weight</th><th>Tokens</th><th>Share</th>"
        "<th>$/MTok</th><th>Cost</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>{unclassified}{cal}"
    )


def _governor_panel(payload: dict) -> str:
    """The quota governor's current routing verdict for the active ob@ account (single-key VPS).

    Computed from the same payload the table renders — no extra `--status` probe. Mirrors
    quota_governor.QuotaGovernor.route: routine sheds to the pool when the account is `cap_walled`
    or `max(<every utilization window incl. model_windows>) >= RESERVE_PCT`; an incident escalates to
    pool-diagnose only when `cap_walled`.
    """
    active = payload.get("active")
    row = next(
        (a for a in (payload.get("accounts") or []) if active in (a.get("slugs") or [])), None
    )
    if row is None:
        return ""
    utils: list[float] = []
    for k in ("five_hour", "seven_day"):
        u = (row.get(k) or {}).get("utilization")
        if isinstance(u, (int, float)):
            utils.append(float(u))
    for w in (row.get("model_windows") or {}).values():
        u = (w or {}).get("utilization")
        if isinstance(u, (int, float)):
            utils.append(float(u))
    mx = max(utils) if utils else None
    walled = row.get("cap_walled") is True
    # match QuotaGovernor.route(): routine sheds when walled OR headroom is UNKNOWN (mx is None →
    # schema drift) OR max window >= reserve. (The transient single-flight lock + the file-backed
    # reactive cap are process/file state this payload-only panel does not read — it reflects the
    # cap_walled + window signals, the governor's primary inputs.)
    routine = "pool" if (walled or mx is None or mx >= _RESERVE_PCT) else "ob@"
    incident = "pool-diagnose" if walled else "ob@"
    mx_txt = f"{mx:.0f}%" if mx is not None else "unknown"
    tone = "crit" if walled else ("warn" if routine == "pool" else "ok")
    return (
        f'<section class="gov banner {tone}"><b>Quota governor · {escape(str(active or "—"))}</b> — '
        f"max window {mx_txt} · reserve {_RESERVE_PCT:.0f}% · cap_walled {'yes' if walled else 'no'} · "
        f"routine → <b>{routine}</b> · incident → <b>{incident}</b></section>"
    )


_TARGET_SESSION_MAX = float(
    os.getenv("ROTATE_TARGET_SESSION_MAX_PCT", os.getenv("ROTATE_DRAIN_THRESHOLD", "85"))
)


def _display_order(payload: dict) -> list[dict]:
    """Rows in ROTATION order (operator rule 2026-09-03): the active account first, then the standby
    the tick would pick NEXT, then the one after — for any number of accounts. Mirrors the tick's
    `_pick_flip_target`: eligible = not cap-walled, no window ≥100, a KNOWN 5h reading ≤ the target
    budget (`ROTATE_TARGET_SESSION_MAX_PCT`, default = the drain line) and below the flip threshold;
    ranked PERISHABLE-FIRST — soonest weekly reset, then lower weekly, then lower session utilization
    (an unknown reset sorts last). Ineligible accounts follow, by the same key, so the board reads
    top-to-bottom as the order rotation will actually use."""
    active = payload.get("active")
    far = time.time() + 365 * 86400

    def key(a: dict) -> tuple[float, float, float]:
        reset = (a.get("seven_day") or {}).get("resets_at_epoch")
        seven, five = _util(a, "seven_day"), _util(a, "five_hour")
        return (
            float(reset) if isinstance(reset, (int, float)) else far,
            seven if seven is not None else 101.0,
            five if five is not None else 101.0,
        )

    rows = list(payload.get("accounts") or [])
    head = [a for a in rows if active in (a.get("slugs") or [])]
    rest = [a for a in rows if a not in head]
    return (
        head
        + sorted([a for a in rest if _eligible(a)], key=key)
        + sorted([a for a in rest if not _eligible(a)], key=key)
    )


def _util(a: dict, k: str) -> float | None:
    u = (a.get(k) or {}).get("utilization")
    return float(u) if isinstance(u, (int, float)) else None


def _eligible(a: dict) -> bool:
    """Would the tick pick this standby? (mirror of `_flip_candidate_verdict`, read-only side)"""
    five, seven = _util(a, "five_hour"), _util(a, "seven_day")
    if a.get("cap_walled") is True or five is None or seven is None:
        return False
    if five >= 100.0 or seven >= 100.0 or five >= TRIGGER_THRESHOLD or seven >= TRIGGER_THRESHOLD:
        return False
    return five <= _TARGET_SESSION_MAX


# ── Commands tab (operator ask 2026-09-03) ───────────────────────────────────────────────────
# The second tab lists every /fabrik-* command in pipeline order with purpose / when / skip /
# next — DERIVED from the corpus (each `commands/_sources/fabrik-*.md` frontmatter description +
# the assembler's NEXT map), never typed here. PIPELINE_ORDER is the ONE hand-held fact: the
# order of CLAUDE.md § Pipeline (stages), then the gates, then the utilities — the test refuses a
# source with no slot and a slot with no source, so the list cannot drift from the corpus silently.
_FABRIK_ROOT = Path(__file__).resolve().parents[2]
# The external-services page (operator ask 2026-09-03): the STATIC file infra's daily chain regenerates
# (scripts/gen_dashboard.py, 06:00 cron). This board only SERVES and EMBEDS it — never regenerates it.
# The amortized cost sidecar `claude_p_cost.py --refresh` rebuilds on the 06:00 cron. Read, never
# recomputed here: the dashboard renders, the producer measures. Resolved AFTER _FABRIK_ROOT but used
# only inside `_spend_panel`, so call-time resolution is what matters.
_COST_SIDECAR = Path(
    os.getenv(
        "CLAUDE_P_COST", str(_FABRIK_ROOT / "scripts" / "kilo-benchmarks" / "claude_p_cost.json")
    )
)

EXT_SERVICES_HTML = Path(
    os.getenv("QUOTA_DASH_EXT_SERVICES", str(_FABRIK_ROOT / "external-services-dashboard.html"))
)


def _ext_services_intro() -> str:
    """One line above the embedded page: when the generator last wrote it (its mtime), or that it has
    not run yet — the chain's liveness contract is 'mtime <= 30 h', so the age is the useful fact."""
    try:
        age = time.time() - EXT_SERVICES_HTML.stat().st_mtime
    except OSError:
        return (
            f'<p class="intro">External-services page not generated yet — expected at '
            f"<code>{escape(str(EXT_SERVICES_HTML))}</code>, written daily by the external-services chain.</p>"
        )
    return (
        f'<p class="intro">The fleet\'s external services &amp; credentials inventory, regenerated '
        f"{age / 3600:.1f} h ago by the daily chain (<code>scripts/gen_dashboard.py</code>, 06:00) — "
        f'embedded as-is; <a href="/external-services.html" target="_blank">open in its own tab</a>.</p>'
    )


PIPELINE_ORDER: tuple[str, ...] = (
    # 0-vision — the MULTI-EPIC front door (agents-fabrik-core § Front door, tier 3). A vision
    # becomes epics; each epic then enters the per-epic chain below at /fabrik-spec. Feature-scale
    # work skips this block entirely and starts at /fabrik-rivals.
    "fabrik-vision",
    "fabrik-epics",
    "fabrik-epics-review",
    # 1-design
    "fabrik-rivals",
    "fabrik-spec",
    "fabrik-spec-review",
    # 5-certify EARLY position → 2-contract
    "fabrik-features",
    "fabrik-flows",
    "fabrik-flows-review",
    "fabrik-data-contract",
    "fabrik-ui-design",
    "fabrik-ui-design-review",
    # 3-plan → 4-build
    "fabrik-plan-after-chat",
    "fabrik-plan-review",
    "fabrik-execute-plan",
    "fabrik-generate-tests",
    # 5-certify → 6-release (the contract freezes on the CERTIFIED build — D-096)
    "fabrik-user-test",
    "fabrik-service-test",
    "fabrik-deploy-checklist",
    "fabrik-release",
    "fabrik-deploy-plan",
    "fabrik-deploy-plan-review",
    "fabrik-deploy",
    "fabrik-deploy-verify",
    # gates (invoked at boundaries, no fixed position)
    "fabrik-review-scoped",
    "fabrik-review",
    "fabrik-repo-review",
    "fabrik-rules-review",
    "fabrik-conformance-review",
    "fabrik-workflow-review",
    # utilities
    "fabrik-docs-review",
    "fabrik-doc-converge",
    "fabrik-catchup",
    "fabrik-upstream",
    "fabrik-decommission",
)
_DESC_RE = re.compile(r"^description:\s*(.+?)\s*$", re.M)
_SKIP_RE = re.compile(r"\s+SKIP(?:/ESCALATE[^:]{0,40})?:\s+")
_STAGE_RE = re.compile(
    r"\s*\bStage:\s*([A-Za-z0-9-]+)\.?"
)  # anywhere: deploy-verify puts it mid-text


def _parse_description(desc: str) -> dict[str, str]:
    """Split a command's frontmatter description into purpose / when (TRIGGER) / skip / stage.
    Markers absent → the whole text is the purpose and the rest is empty (never a guess)."""
    desc = desc.strip().strip('"')
    stage = ""
    m = _STAGE_RE.search(desc)
    if m:
        stage, desc = m.group(1), (desc[: m.start()] + " " + desc[m.end() :]).strip()
    skip = ""
    sm = _SKIP_RE.search(desc)
    if sm:  # "SKIP:" or "SKIP/ESCALATE to the full /fabrik-review:" (review-scoped)
        desc, skip = desc[: sm.start()], desc[sm.end() :]
    when = ""
    for marker in (" TRIGGER — ", " TRIGGER - "):
        if marker in desc:
            desc, when = desc.split(marker, 1)
            break
    return {"purpose": desc.strip(), "when": when.strip(), "skip": skip.strip(), "stage": stage}


def _next_map() -> dict[str, str]:
    """The assembler's NEXT map, imported from its file (no package; the module only acts under
    `__main__`). Unreadable → empty map, and the column says so rather than inventing a successor."""
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "assemble_commands", _FABRIK_ROOT / "commands" / "assemble_commands.py"
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return dict(getattr(mod, "NEXT", {}))
    except Exception as e:  # noqa: BLE001 — a broken assembler must not take the quota board down
        sys.stderr.write(f"quota_dashboard: NEXT map unreadable: {e}\n")
        return {}


_cmd_cache_key: tuple[tuple[str, int], ...] | None = None
_cmd_cache_rows: list[dict[str, str]] = []


def _load_commands() -> list[dict[str, str]]:
    """Every `commands/_sources/fabrik-*.md`, in PIPELINE_ORDER (unknown names last, alphabetical,
    so a new command is visible before its slot exists). Cached on the sources' mtimes."""
    src = _FABRIK_ROOT / "commands" / "_sources"
    files = sorted(src.glob("fabrik-*.md"))
    global _cmd_cache_key, _cmd_cache_rows
    asm = _FABRIK_ROOT / "commands" / "assemble_commands.py"
    # the NEXT column comes from the assembler, which can change with no _sources mtime moving
    key = tuple((f.name, f.stat().st_mtime_ns) for f in [*files, asm] if f.exists())
    if _cmd_cache_key == key:
        return list(_cmd_cache_rows)
    nxt = _next_map()
    rows = []
    for f in files:
        m = _DESC_RE.search(f.read_text(encoding="utf-8")[:6000])
        parsed = _parse_description(m.group(1) if m else "")
        rows.append({"name": f.stem, "next": nxt.get(f.stem, "").strip(), **parsed})
    order = {n: i for i, n in enumerate(PIPELINE_ORDER)}
    rows.sort(key=lambda r: (order.get(r["name"], len(order)), r["name"]))
    _cmd_cache_key, _cmd_cache_rows = key, rows
    return list(rows)


def _stage_tone(stage: str) -> str:
    if stage == "gate":
        return "crit"
    if stage == "utility":
        return "stale"
    return "cap"


def _commands_table(rows: list[dict[str, str]]) -> str:
    body = []
    for i, r in enumerate(rows, 1):
        stage = r["stage"] or "—"
        body.append(
            f'<tr><td class="ord">{i}</td>'
            f'<td class="cmd"><strong>/{escape(r["name"])}</strong></td>'
            f'<td><span class="badge {_stage_tone(r["stage"])}">{escape(stage)}</span></td>'
            f"<td>{escape(r['purpose'])}</td>"
            f'<td class="when">{escape(r["when"]) or '<span class="muted">—</span>'}</td>'
            f'<td class="when">{escape(r["skip"]) or '<span class="muted">—</span>'}</td>'
            f'<td class="when">{escape(r["next"]) or '<span class="muted">—</span>'}</td></tr>'
        )
    return (
        "<table><thead><tr><th>#</th><th>Command</th><th>Stage</th><th>Purpose</th>"
        "<th>When to use</th><th>Skip when</th><th>Next</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table>"
    )


def render(
    payload: dict, generated_at: float, error: str | None = None, credits: dict | None = None
) -> str:
    accounts = _display_order(payload)
    active = payload.get("active")
    warns = payload.get("fleet_warnings") or []
    pause = payload.get("pause")
    gen = datetime.fromtimestamp(generated_at).astimezone().strftime("%a %d %b %Y · %H:%M:%S %Z")

    banner = ""
    if error:
        banner = (
            f'<div class="banner crit">Live probe failed — showing the last good reading. '
            f"{escape(error)}</div>"
        )
    if pause == "marker":
        banner += '<div class="banner warn">Auto-rotation is PAUSED by the operator marker.</div>'
    elif pause == "error":
        banner += (
            '<div class="banner crit">Pause state unreadable — rotation is failing closed.</div>'
        )
    if not accounts:
        banner += '<div class="banner warn">No fleet accounts reporting yet.</div>'

    warn_html = ""
    if warns:
        items = "".join(f"<li>{escape(str(w))}</li>" for w in warns)
        warn_html = f'<section class="warns"><h2>Warnings</h2><ul>{items}</ul></section>'

    ranks: list[str | None] = []
    n = 0
    for a in accounts:
        if active in (a.get("slugs") or []):
            ranks.append(None)
        elif _eligible(a):
            n += 1
            ranks.append("NEXT" if n == 1 else f"#{n} in line")
        else:
            ranks.append("not eligible")
    rows = "".join(_row(a, active, rank) for a, rank in zip(accounts, ranks, strict=True))
    # Scaffolded-but-unlogged dirs LAST: real rows first, then the one thing the operator still
    # owes. Older payloads (no `pending` key) render nothing extra.
    rows += "".join(_pending_row(str(x)) for x in (payload.get("pending") or []))
    gov_html = _governor_panel(payload)
    credits_html = _pool_credits_panel(credits)
    # Fail-soft by contract: `_spend_panel` returns "" on a missing/old-format sidecar, so the Usage
    # tab stays empty rather than rendering a zeroed table that would read as "we spent nothing this
    # month" — except when the sidecar reports tokens no tier claimed, which is returned even on that
    # path so the pane explains its own emptiness.
    spend_html = _spend_panel()
    cmd_rows = _load_commands()
    cmd_html = _commands_table(cmd_rows)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude quota — {escape(str(active or "no active account"))}</title>
<style>
 :root {{ color-scheme: light dark;
   --bg:#f6f7f9; --card:#fff; --fg:#14161a; --sub:#666e7a; --line:#e3e6ea;
   --ok:#1a9d5a; --warn:#c47f14; --crit:#c8402f; --accent:#3b6fd4; }}
 @media (prefers-color-scheme: dark) {{ :root {{
   --bg:#0f1216; --card:#171b21; --fg:#e8ecf1; --sub:#98a1ae; --line:#242a33;
   --ok:#3ecf8e; --warn:#e8b04b; --crit:#ff6b57; --accent:#6f9bff; }} }}
 * {{ box-sizing:border-box; }}
 body {{ margin:0; padding:24px; background:var(--bg); color:var(--fg);
   font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
 .wrap {{ max-width:1600px; margin:0 auto; }}
 header {{ display:flex; flex-wrap:wrap; gap:12px; align-items:baseline;
   justify-content:space-between; margin-bottom:18px; }}
 h1 {{ font-size:20px; margin:0; font-weight:650; }}
 h1 .who {{ color:var(--accent); }}
 .stamp {{ color:var(--sub); font-size:13px; }}
 .banner {{ padding:10px 14px; border-radius:8px; margin-bottom:12px; font-size:14px; }}
 .banner.warn {{ background:color-mix(in srgb, var(--warn) 16%, transparent); border:1px solid var(--warn); }}
 .banner.crit {{ background:color-mix(in srgb, var(--crit) 16%, transparent); border:1px solid var(--crit); }}
 table {{ width:100%; border-collapse:separate; border-spacing:0; background:var(--card);
   border:1px solid var(--line); border-radius:12px; overflow:hidden; }}
 th, td {{ padding:14px 16px; text-align:left; vertical-align:top;
   border-bottom:1px solid var(--line); }}
 thead th {{ font-size:12px; letter-spacing:.06em; text-transform:uppercase;
   color:var(--sub); font-weight:600; background:transparent; }}
 tbody tr:last-child td {{ border-bottom:none; }}
 tr.is-active {{ background:color-mix(in srgb, var(--accent) 8%, transparent); }}
 .acct strong {{ display:block; font-size:15px; }}
 .sub {{ display:block; color:var(--sub); font-size:12.5px; margin-top:3px; }}
 .num {{ width:32%; }}
 .pct {{ font-size:26px; font-weight:680; letter-spacing:-.02em; }}
 .pct.ok {{ color:var(--ok); }} .pct.warn {{ color:var(--warn); }} .pct.crit {{ color:var(--crit); }}
 .muted {{ color:var(--sub); }}
 .bar {{ height:6px; border-radius:99px; background:var(--line); margin:8px 0 4px; overflow:hidden; }}
 .fill {{ display:block; height:100%; border-radius:99px; }}
 .fill.ok {{ background:var(--ok); }} .fill.warn {{ background:var(--warn); }} .fill.crit {{ background:var(--crit); }}
 .badges {{ display:flex; flex-wrap:wrap; gap:5px; margin-top:7px; }}
 .badge {{ font-size:11px; padding:2px 7px; border-radius:99px; border:1px solid var(--line);
   color:var(--sub); white-space:nowrap; }}
 .badge.active {{ border-color:var(--accent); color:var(--accent); font-weight:650; }}
 .badge.cap {{ border-color:var(--accent); color:var(--accent); }}
 .badge.crit {{ border-color:var(--crit); color:var(--crit); }}
 .warns {{ margin-top:18px; background:var(--card); border:1px solid var(--line);
   border-radius:12px; padding:14px 18px; }}
 .warns h2 {{ font-size:13px; text-transform:uppercase; letter-spacing:.06em;
   color:var(--sub); margin:0 0 8px; }}
 .warns ul {{ margin:0; padding-left:18px; }} .warns li {{ margin:4px 0; font-size:13.5px; }}
 footer {{ margin-top:16px; color:var(--sub); font-size:12.5px; }}
 .act {{ width:1%; white-space:nowrap; vertical-align:middle; }}
 button.switch {{ font:inherit; font-size:13px; font-weight:600; padding:6px 12px; border-radius:8px;
   border:1px solid var(--accent); color:var(--accent); background:transparent; cursor:pointer; }}
 button.switch:hover {{ background:color-mix(in srgb, var(--accent) 12%, transparent); }}
 button.switch[disabled] {{ opacity:.5; cursor:progress; }}
 @media (max-width:720px) {{ .num {{ width:auto; }} th:nth-child(1) {{ width:40%; }} }}
 nav.tabs {{ display:flex; gap:6px; margin-bottom:14px; border-bottom:1px solid var(--line); }}
 nav.tabs button {{ font:inherit; font-size:13.5px; font-weight:600; padding:8px 14px; border:1px solid transparent;
   border-bottom:none; border-radius:8px 8px 0 0; background:transparent; color:var(--sub); cursor:pointer; }}
 nav.tabs button.is-on {{ color:var(--accent); border-color:var(--line); background:var(--card); margin-bottom:-1px; }}
 .badge.stale {{ border-color:var(--line); color:var(--sub); }}
 #pane-commands td {{ font-size:13.5px; }} #pane-commands .ord {{ color:var(--sub); width:1%; }}
 #pane-commands .cmd strong {{ white-space:nowrap; color:var(--accent); }} #pane-commands .when {{ color:var(--sub); }}
 #pane-commands .intro {{ color:var(--sub); font-size:13px; margin:0 0 12px; }}
 #pane-usage .intro {{ color:var(--sub); font-size:13px; margin:0 0 12px; }}
 #pane-usage h2 {{ font-size:13px; text-transform:uppercase; letter-spacing:.06em;
   color:var(--sub); margin:22px 0 8px; }}
 #pane-usage .muted {{ color:var(--sub); font-size:12px; }}
 .cal {{ display:grid; grid-template-columns:repeat(7,1fr); gap:5px; }}
 .cal-months {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }}
 @media (max-width:1100px) {{ .cal-months {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} }}
 @media (max-width:620px) {{ .cal-months {{ grid-template-columns:1fr; }} }}
 .cal-month {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
   padding:14px 16px; }}
 .cal-head {{ display:flex; justify-content:space-between; align-items:baseline; gap:12px;
   margin-bottom:10px; }}
 .cal-head b {{ font-size:14px; }}
 .cal-dow {{ display:grid; grid-template-columns:repeat(7,1fr); gap:5px; margin-bottom:5px; }}
 .cal-dow i {{ font-style:normal; font-size:10px; color:var(--sub); text-align:center; }}
 .cal-pad {{ aspect-ratio:1; }}
 .cal-cell {{ aspect-ratio:1; border-radius:7px; border:1px solid var(--line);
   background:var(--card); display:flex; align-items:flex-end; justify-content:flex-end;
   padding:3px 4px; cursor:default; }}
 .cal-cell span {{ font-size:10px; color:var(--sub); line-height:1; }}
 .cal-cell:hover {{ outline:2px solid var(--accent); outline-offset:1px; }}
 .cal-cell.lvl1 {{ background:color-mix(in srgb, var(--accent) 18%, var(--card)); }}
 .cal-cell.lvl2 {{ background:color-mix(in srgb, var(--accent) 38%, var(--card)); }}
 .cal-cell.lvl3 {{ background:color-mix(in srgb, var(--accent) 60%, var(--card)); }}
 .cal-cell.lvl4 {{ background:color-mix(in srgb, var(--accent) 85%, var(--card)); }}
 .cal-cell.lvl3 span, .cal-cell.lvl4 span {{ color:var(--bg); }}
 i.cal-cell {{ display:inline-block; width:14px; height:14px; aspect-ratio:auto;
   vertical-align:-3px; margin:0 2px; padding:0; }}
</style></head><body><div class="wrap">
<header>
  <h1>Claude account quota — active: <span class="who">{escape(str(active or "none"))}</span></h1>
  <div class="stamp">updated {escape(gen)} · refreshes every {REFRESH_S}s ·
    <span id="conn">live</span></div>
</header>
<nav class="tabs" role="tablist"><button type="button" class="tab is-on" data-tab="quota">Quota</button><button type="button" class="tab" data-tab="usage">Usage</button><button type="button" class="tab" data-tab="commands">Commands</button><button type="button" class="tab" data-tab="external">External services</button></nav>
<section id="pane-quota" class="pane">
{banner}
{gov_html}
{credits_html}
<table>
  <thead><tr><th>Account</th><th>Session (5h) remaining</th><th>Weekly remaining</th><th>Fable 5 weekly remaining</th><th></th></tr></thead>
  <tbody>{rows}</tbody>
</table>
{warn_html}
</section>
<section id="pane-usage" class="pane" hidden>
{spend_html}
</section>
<section id="pane-commands" class="pane" hidden>
{'<div class="banner crit">Command corpus unreadable — no <code>commands/_sources/fabrik-*.md</code> under ' + escape(str(_FABRIK_ROOT)) + ".</div>" if not cmd_rows else ""}
<p class="intro">Every <code>/fabrik-*</code> command in pipeline order ({len(cmd_rows)} sources under <code>commands/_sources/</code>, read live — purpose, when-to-use and skip-when come from each command's own description, the successor from the assembler's NEXT map). Stages run top to bottom; gates are invoked at boundaries; utilities at any point.</p>
{cmd_html}
</section>
<section id="pane-external" class="pane" hidden>
{credits_html}
{_ext_services_intro()}
{'<iframe id="ext-frame" title="External services" data-src="/external-services.html" style="width:100%;min-height:80vh;border:1px solid var(--line);border-radius:12px;background:var(--card)"></iframe>' if EXT_SERVICES_HTML.is_file() else ""}
</section>
<footer>Rotation flips the active pointer at {TRIGGER_THRESHOLD:.0f}% on the 5h window (or either window, or an account's
configured weekly cap). This board probes every {int(PROBE_INTERVAL_S)}s on its own and invokes the rotation tick the
moment the active account crosses that line; the cron tick every 5 minutes is the backstop.
The <em>switch →</em> button flips it NOW (pause-, dwell- and cap-exempt, like <code>--switch</code>);
every session bound to the pointer follows it — no restart.</footer>
</div><script>
/* Health-gated auto-refresh (2026-08-18 — replaces meta http-equiv=refresh). The meta tag
   died on the first failed load after a WSL restart: the browser's error page carries no
   refresh tag, so the tab froze until a manual F5 — the operator hit this twice. This
   reloader NEVER navigates on failure: it polls /health and reloads only when the server
   answers, so the tab rides out server restarts, WSL restarts, and host hibernation, and
   self-heals the moment the box is back. */
(function () {{
  /* Tabs: the choice lives in location.hash so the 20s reload lands on the same tab. */
  var tabs = document.querySelectorAll("nav.tabs button");
  function showTab(name) {{
    tabs.forEach(function (b) {{ b.classList.toggle("is-on", b.getAttribute("data-tab") === name); }});
    document.querySelectorAll("section.pane").forEach(function (p) {{ p.hidden = (p.id !== "pane-" + name); }});
    var fr = document.getElementById("ext-frame");
    if (name === "external" && fr && !fr.getAttribute("src")) {{ fr.setAttribute("src", fr.getAttribute("data-src")); }}
  }}
  tabs.forEach(function (b) {{ b.addEventListener("click", function () {{
    var name = b.getAttribute("data-tab");
    if (history.replaceState) {{ history.replaceState(null, "", name === "quota" ? location.pathname : "#" + name); }}
    showTab(name);
  }}); }});
  // GENERIC restore. This used to name "commands" and "external" literally, so every tab added
  // later fell through to quota on the {REFRESH_S}s auto-reload — the page would silently jump
  // off whatever you were reading. Any pane that exists is now restorable by its own hash.
  var want = (location.hash || "").replace("#", "");
  showTab(want && document.getElementById("pane-" + want) ? want : "quota");
  var conn = document.getElementById("conn");
  setInterval(function () {{
    fetch("/health", {{cache: "no-store"}})
      .then(function (r) {{ if (r.ok) location.reload(); }})
      .catch(function () {{
        if (conn) {{ conn.textContent = "server unreachable — retrying"; }}
      }});
  }}, {REFRESH_S} * 1000);
  document.querySelectorAll("button.switch").forEach(function (btn) {{
    btn.addEventListener("click", function () {{
      var slug = btn.getAttribute("data-slug");
      if (!confirm("Switch the active account to " + slug + " now?\\n\\nEvery Claude session bound to the pointer follows it — no restart needed.")) {{ return; }}
      btn.disabled = true; btn.textContent = "switching…";
      fetch("/switch", {{method: "POST", cache: "no-store",
        headers: {{"Content-Type": "application/json", "{SWITCH_HEADER}": "1"}},
        body: JSON.stringify({{account: slug}})}})
        .then(function (r) {{ return r.json().then(function (j) {{ return [r.status, j]; }}); }})
        .then(function (sj) {{
          if (sj[0] === 200 && sj[1].ok) {{ location.reload(); return; }}
          alert("Switch failed (" + sj[0] + "):\\n" + (sj[1].error || sj[1].raw || JSON.stringify(sj[1])));
          btn.disabled = false; btn.textContent = "switch →";
        }})
        .catch(function (e) {{ alert("Switch request failed: " + e); btn.disabled = false; btn.textContent = "switch →"; }});
    }});
  }});
}})();
</script>
</body></html>"""


_gen_lock = threading.Lock()


def generate() -> str:
    """Probe + write index.html/quota.json. Falls back to the last good payload on error.
    SERIALIZED: the probe loop, a past-the-floor view, a pointer-moved view and a switch all land
    here; without this lock two probes could run at once (double API cost) and race the two file
    writes (scoped review 2026-09-03). A second caller waits for the running probe, never starts one."""
    with _gen_lock:
        return _generate_locked()


def _generate_locked() -> str:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    error = None
    try:
        payload = _probe()
        _JSON.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    except Exception as exc:  # transport/CLI/JSON — degrade visibly, never blank the page
        error = f"{type(exc).__name__}: {exc}"[:200]
        try:
            payload = json.loads(_JSON.read_text(encoding="utf-8"))
        except OSError:
            payload = {}
        except ValueError:
            payload = {}
        sys.stderr.write(f"quota_dashboard: probe failed ({error})\n")
        # The pointer is a LOCAL fact, not a probe result: carry it into the fallback so a flip
        # followed by a probe outage renders the right account and `_pointer_moved()` clears —
        # otherwise every view would re-pay the probe timeout until the probe recovered.
        live = _pointer_slug()
        if live:
            payload = {**payload, "active": live}
        # The fallback SAYS it is blind: the trigger lowers its bar on this key (see
        # _maybe_trigger_rotation) — a reading that cannot be refreshed is a reading to act on early.
        payload = {**payload, "probe_failed": error}
        try:
            _JSON.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        except OSError:
            pass
    # The pool balance rides the SAME loop, behind its own TTL, and can never break the board:
    # _pool_credits already fails soft, and this guard covers anything it did not anticipate.
    # Cache only — see _pool_credits(fetch=False). The refresh happens off this lock.
    credits = _pool_credits(fetch=False)
    html = render(payload, time.time(), error, credits=credits)
    _HTML.write_text(html, encoding="utf-8")
    return html


_regen_lock = threading.Lock()
_LAST_REGEN: list[threading.Thread | None] = [None]  # the most recent background worker, joinable
_LAST_SYNC_REGEN: list[float] = [0.0]  # when the pointer-moved path last regenerated synchronously


def _regen_async() -> threading.Thread | None:
    """One background regeneration at a time; drop the request if one is already running.
    Returns the worker thread (None when the request was dropped) so a caller that must
    observe the regeneration — a test — can ``join`` it instead of racing it."""
    if not _regen_lock.acquire(blocking=False):
        return None

    def work() -> None:
        try:
            generate()
        finally:
            _regen_lock.release()

    t = threading.Thread(target=work, daemon=True, name="quota-regen")
    t.start()
    return t


_LAST_TRIGGER: list[float] = [0.0, 0.0]  # [flip tier, drain tier] — independent cooldowns


def _maybe_trigger_rotation(payload: dict) -> threading.Thread | None:
    """The fast path to a flip: when the ACTIVE account's 5h window is at/over the flip threshold
    (or it is cap-walled), run the rotation tick NOW instead of waiting for the */5 cron. The tick
    keeps every safety it has (dwell, pause, successor validation, flock via its own state lock);
    this only shortens the latency from ≤5 min to ≤ the probe interval. Once per cooldown."""
    active = payload.get("active")
    row = next(
        (a for a in (payload.get("accounts") or []) if active in (a.get("slugs") or [])), None
    )
    if row is None:
        return None
    five = (row.get("five_hour") or {}).get("utilization")
    blind = bool(payload.get("probe_failed"))  # the last GOOD reading, minutes old — bar drops
    bar = BLIND_TRIGGER_THRESHOLD if blind else TRIGGER_THRESHOLD
    sess = float(five) if isinstance(five, (int, float)) else None
    hot = sess is not None and sess >= bar
    drain = sess is not None and sess >= DRAIN_TRIGGER_THRESHOLD
    if hot or row.get("cap_walled") is True:
        tier = 0  # flip tier
    elif drain:
        tier = 1  # urgent-drain tier: the tick decides whether a successor exists
    else:
        return None
    now = time.time()
    if now - _LAST_TRIGGER[tier] < TRIGGER_COOLDOWN_S:
        return None
    _LAST_TRIGGER[tier] = now
    if tier == 1:
        why = f"session {sess:.0f}% >= {DRAIN_TRIGGER_THRESHOLD:.0f}% (urgent-drain tier)"
    elif hot:
        why = (
            f"last good session {sess:.0f}% >= {bar:.0f}% with the probe BLIND"
            if blind
            else f"session {sess:.0f}% >= {bar:.0f}%"
        )
    else:
        why = "cap-walled"
    sys.stderr.write(f"quota_dashboard: active {active} {why} — invoking the rotation tick\n")

    def run() -> None:  # off the loop thread: a slow tick must not stall the probes
        try:
            ROTATE_LOCK.parent.mkdir(parents=True, exist_ok=True)
            proc = subprocess.run(  # noqa: S603 — fixed argv, no shell; flock -n = the cron's own lock
                ["flock", "-n", str(ROTATE_LOCK), sys.executable, str(ROTATE_CLI), "--tick"],
                capture_output=True,
                text=True,
                timeout=TICK_TIMEOUT_S,
            )
            if proc.returncode == 1 and not (proc.stdout or proc.stderr).strip():
                sys.stderr.write(
                    "quota_dashboard: a rotation tick already holds the lock — skipped\n"
                )
                return
            sys.stderr.write(
                f"quota_dashboard: tick exit {proc.returncode}: {(proc.stdout or proc.stderr).strip()[:300]}\n"
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            sys.stderr.write(f"quota_dashboard: tick failed to run: {type(exc).__name__}: {exc}\n")

    t = threading.Thread(target=run, daemon=True, name="quota-tick")
    t.start()
    return t


def _start_probe_loop() -> threading.Event:
    """The server's own cadence: probe every PROBE_INTERVAL_S regardless of viewers, then hand the
    fresh payload to the rotation trigger. Returns the stop event (tests; serve() never sets it)."""
    stop = threading.Event()

    def loop() -> None:
        while not stop.is_set():
            started = time.monotonic()
            try:
                generate()
                _credits_async()  # own thread, own TTL — never delays this cadence
                _maybe_trigger_rotation(json.loads(_JSON.read_text(encoding="utf-8")))
            except Exception as exc:  # noqa: BLE001 — the loop must outlive any single probe
                sys.stderr.write(f"quota_dashboard: probe loop: {type(exc).__name__}: {exc}\n")
            # the interval is a PERIOD: a ~20s probe followed by a 20s pause was a 40s cadence
            stop.wait(max(0.0, PROBE_INTERVAL_S - (time.monotonic() - started)))

    threading.Thread(target=loop, daemon=True, name="quota-probe-loop").start()
    return stop


def _fresh_html() -> str:
    """The last-written page, always served instantly; a stale one triggers a BACKGROUND
    regeneration. A request must never block on the probe: on 2026-08-18 evening the probe
    hung (rotate --status shelling out to the claude CLI) and every page load sat on it for
    its full 60s cap — the operator read the dashboard as "not reachable". The in-page
    reloader re-fetches within 60s anyway, so serving one stale view costs nothing. Only a
    first-ever request (no page on disk yet) generates inline."""
    try:
        age = time.time() - _HTML.stat().st_mtime
        html = _HTML.read_text(encoding="utf-8")
        if _pointer_moved() and time.time() - _LAST_SYNC_REGEN[0] > PROBE_TIMEOUT_S:
            # A flip happened since the render (measured 2026-09-02: the board showed the OLD
            # account for up to floor + reload after a --switch). One synchronous regeneration,
            # bounded by the probe timeout and never more than once per timeout window — a
            # hung probe can cost ONE view the wait, never every view.
            _LAST_SYNC_REGEN[0] = time.time()
            return generate()
        if age >= MAX_AGE_S:
            _LAST_REGEN[0] = _regen_async()
        return html
    except OSError:
        pass
    return generate()


def _known_slugs() -> set[str]:
    """The slugs the board itself last rendered — the ONLY targets the button may name."""
    try:
        payload = json.loads(_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    out: set[str] = set()
    for acct in payload.get("accounts") or []:
        for slug in acct.get("slugs") or []:
            if isinstance(slug, str) and _SLUG_RE.match(slug):
                out.add(slug)
    return out


def switch_account(slug: object) -> tuple[int, dict]:
    """Relay one manual flip to the rotation CLI. Returns (http_status, json_body).

    400 — not a slug the board knows (nothing reaches the CLI); 502 — the CLI refused or
    failed (its stderr is the body, never swallowed); 200 — flipped, and the board has been
    re-rendered synchronously so the reload shows the new pointer, not a floor-cached one.
    """
    if not isinstance(slug, str) or not _SLUG_RE.match(slug) or slug not in _known_slugs():
        return 400, {"ok": False, "error": f"unknown account {slug!r} — not on the board"}
    try:
        proc = subprocess.run(  # noqa: S603 — fixed argv, validated slug, no shell
            [sys.executable, str(ROTATE_CLI), "--switch", slug],
            capture_output=True,
            text=True,
            timeout=SWITCH_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 502, {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:400]}
    if proc.returncode != 0:
        err = (proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}")[:400]
        return 502, {"ok": False, "error": err}
    generate()  # fresh render NOW — bypasses the floor on purpose, one probe per click
    return 200, {"ok": True, "output": proc.stdout.strip()[:400]}


class _Handler(BaseHTTPRequestHandler):
    server_version = "quota-dashboard"
    # Per-connection socket timeout (stdlib knob): a client that promises N body bytes and sends
    # fewer would otherwise park this handler's thread on `rfile.read()` for as long as it
    # stays connected. 15s is generous for a loopback fetch and bounds every read, GET included.
    timeout = float(os.getenv("QUOTA_DASH_SOCKET_TIMEOUT_S", "15"))

    def _json(self, status: int, body: dict) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:  # noqa: N802 (stdlib interface)
        path = self.path.split("?", 1)[0]
        if path != "/switch":
            self.send_error(404)
            return
        if not self.headers.get(SWITCH_HEADER):
            # No custom header = not our page's fetch(). A cross-origin form/fetch cannot add
            # one without a preflight, and this server answers no OPTIONS — so this is the
            # whole CSRF story for a loopback-only board.
            sys.stderr.write("quota_dashboard: POST /switch refused — no custom header\n")
            self._json(403, {"ok": False, "error": f"missing {SWITCH_HEADER} header"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if not 0 <= length <= _MAX_BODY:
            self._json(400, {"ok": False, "error": "bad Content-Length"})
            return
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"ok": False, "error": "body is not JSON"})
            return
        slug = (body or {}).get("account") if isinstance(body, dict) else None
        t0 = time.time()
        status, out = switch_account(slug)
        sys.stderr.write(
            f"quota_dashboard: POST /switch {slug!r} -> {status} in {time.time() - t0:.1f}s:"
            f" {out.get('output') or out.get('error') or ''}\n"
        )
        self._json(status, out)

    def do_GET(self) -> None:  # noqa: N802 (stdlib interface)
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            body, ctype = _fresh_html().encode("utf-8"), "text/html; charset=utf-8"
        elif path == "/quota.json":
            _fresh_html()  # refresh the payload alongside the page
            try:
                body = _JSON.read_bytes()
            except OSError:
                body = b"{}"
            ctype = "application/json"
        elif path == "/health":
            body, ctype = b"ok", "text/plain"
        elif path == "/external-services.html":
            # Only a regular `.html` file is ever served — the env override is the operator's own
            # process env on a 127.0.0.1-only server (single-operator threat model), but a symlink
            # to /etc/hostname was measured to pass through; the suffix + regular-file guard closes it.
            if EXT_SERVICES_HTML.suffix != ".html" or not EXT_SERVICES_HTML.is_file():
                self.send_error(404)
                return
            try:
                body = EXT_SERVICES_HTML.read_bytes()  # byte-for-byte, never cached
            except OSError:
                self.send_error(404)
                return
            ctype = "text/html; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_a) -> None:  # keep cron logs clean
        return


def serve() -> int:
    httpd = ThreadingHTTPServer((HOST, PORT), _Handler)
    sys.stderr.write(
        f"quota_dashboard: serving http://{HOST}:{PORT}/ (probing every {PROBE_INTERVAL_S:.0f}s)\n"
    )
    _start_probe_loop()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


def _listener_pid(port: int) -> int | None:
    """The PID holding *port* on loopback, via `ss -ltnp` (no psutil). None when unknown."""
    try:
        out = subprocess.run(  # noqa: S603 — fixed argv
            ["ss", "-ltnp"], capture_output=True, text=True, timeout=5
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in out.splitlines():
        if f":{port} " in line and "pid=" in line:
            try:
                return int(line.split("pid=", 1)[1].split(",", 1)[0])
            except ValueError:
                return None
    return None


def _health_ok() -> bool:
    """One GET /health with a short timeout. A listener that accepts but never answers is NOT up."""
    import http.client

    try:
        c = http.client.HTTPConnection(
            HOST, PORT, timeout=float(os.getenv("QUOTA_DASH_ENSURE_TIMEOUT_S", "5"))
        )
        c.request("GET", "/health")
        r = c.getresponse()
        return r.status == 200 and r.read(8) == b"ok"
    except (OSError, http.client.HTTPException):
        return False


def ensure() -> int:
    """Keep the server up (cron keepalive): a real HTTP `ok` from /health, or kill whatever holds
    the port and respawn. Connecting to the port used to count as alive — a WEDGED server
    (accepts, never answers) then stayed wedged for as long as the box was up. Nothing is killed
    unless it holds our port AND fails the health probe."""
    import signal
    import socket

    with socket.socket() as s:
        s.settimeout(2.0)
        listening = s.connect_ex((HOST, PORT)) == 0
    if listening:
        if _health_ok():
            return 0  # already up and answering
        pid = _listener_pid(PORT)
        if pid is not None:
            sys.stderr.write(
                f"quota_dashboard: listener pid {pid} holds :{PORT} but /health does not answer — restarting\n"
            )
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
            time.sleep(1.0)
            if _listener_pid(PORT) == pid:  # ignored SIGTERM — the port must be free to respawn
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
                time.sleep(0.5)
    log = Path(os.getenv("QUOTA_DASH_LOG", str(Path.home() / ".claude" / "quota-dashboard.log")))
    with open(log, "a", encoding="utf-8") as fh:
        subprocess.Popen(  # noqa: S603 — fixed argv, no shell
            [sys.executable, str(Path(__file__).resolve()), "--serve"],
            stdout=fh,
            stderr=fh,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--once", action="store_true", help="regenerate the page and exit")
    g.add_argument("--serve", action="store_true", help="run the localhost server (foreground)")
    g.add_argument("--ensure", action="store_true", help="start the server if it is not running")
    args = ap.parse_args(argv)
    if args.once:
        generate()
        sys.stdout.write(f"{_HTML}\n")
        return 0
    if args.ensure:
        return ensure()
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
