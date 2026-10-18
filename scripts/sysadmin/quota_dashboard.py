#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/quota-dashboard.md, PORTS.md, docs/workstation/claude-account-rotation.md
#
# The command centre (plan 2026-10-17-plan-1): the localhost board the operator leaves open — six
# views (Overview, Work, Accounts, Usage, Commands, Services) over this module's collectors: every
# Claude account's headroom from the `--status` probe, every repo's work store, every agent's run
# records, the box budget, the spend sidecar, the command corpus, the pool and search-API balances.
# The page layer is `dashboard_ui/` (components, catalogue, views, one stylesheet, one script); this
# module serves it, hands each view its data (`_view_data`) and owns the probe, the routes and the
# guard. Subsystem doc: docs/workstation/quota-dashboard.md.
#
# DESIGN — why there is no regeneration cron:
#   `claude_rotate.py --status --json` makes live API probes for fresh-token dirs. A */5 cron
#   would probe forever whether or not anyone is looking. So the server probes on its own cadence
#   (QUOTA_DASH_PROBE_INTERVAL_S) and a quota view re-probes at most once per QUOTA_DASH_MAX_AGE_S:
#   refresh-spamming a view cannot multiply probe volume. Every view states the age of its own
#   data, and a quota view carries the stale banner — a stale reading is visible, never silent.
#
# The server is stdlib-only, binds loopback by default, and is kept alive by cron
# (@reboot + a periodic --ensure). It never writes outside its own output dir and never
# touches credential files: every rotation fact comes from shelling the rotation CLI, which
# owns that contract. Its writes are the operator's clicks, relayed: the account controls
# (/switch, /park, /cap, /threshold — the rotation CLI and its two maps) and the work controls
# (/agent-pause, /item-verdict — the hub's work.py as the operator). Every POST refuses a request
# without the custom SWITCH_HEADER (a forged cross-origin POST cannot carry one without a CORS
# preflight this server never answers) and a target the board itself did not render; every request
# is refused 421 unless its Host is this board's own (DNS rebinding) and 403 when a POST or a view
# GET is marked cross-site.
"""Serve/generate the Claude account-quota dashboard (see module header)."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# The page layer (plan 2026-10-17-plan-1): this file runs as `__main__`, so its own directory goes on
# sys.path ONCE — the only form under which `dashboard_ui.views.<name>` and the views' own
# `from dashboard_ui import components` resolve. The package never imports this module back.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import dashboard_ui  # noqa: E402
from dashboard_ui import components as _ui  # noqa: E402
from dashboard_ui import snapshot as _snapshot  # noqa: E402
from dashboard_ui import strings as _strings  # noqa: E402
from dashboard_ui import views as _views  # noqa: E402
from dashboard_ui.components import last_resort as _last_resort  # noqa: E402
from dashboard_ui.fmt import opt_root as _opt_root  # noqa: E402

# The child's `synced_at` is read by the PAGE's time rule, so the board and the page agree on what a time
# is (W-a4bc74a6, R27); `dashboard_ui.inventory` is already loaded here through `views.services`.
from dashboard_ui.inventory import _epoch  # noqa: E402
from dashboard_ui.strings import CATALOGUE as _BUILTIN_WORDS  # noqa: E402

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
    os.getenv("ROTATE_THRESHOLD", "99")
)  # the tick's own default (claude_rotate._rotate_threshold) — keep the two literals equal;
# `test_quota_dashboard.py` asserts the equality, because a dashboard that triggers at a different
# line than the tick acts on is a trigger that either fires late or fires into a no-op.
TRIGGER_COOLDOWN_S = float(os.getenv("QUOTA_DASH_TRIGGER_COOLDOWN_S", "120"))


def _trip_line(acct: dict | None) -> float:
    """The flip line for ONE account: its `session_threshold` (claude_rotate's thresholds.json, carried
    on the status row) when set, else TRIGGER_THRESHOLD — the mirror of `claude_rotate._row_threshold`."""
    v = (acct or {}).get("session_threshold")
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return TRIGGER_THRESHOLD
    return float(v)


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
# BLIND bar = the drain band, read lazily + guarded by `_drain_band()` (F4: an import-time
# float(os.getenv) crashed the whole board on a bad value; `_session_bar` was hardened, this was not)
TICK_TIMEOUT_S = float(os.getenv("QUOTA_DASH_TICK_TIMEOUT_S", "180"))
# The SAME lock the cron line takes (`flock -n $HOME/.claude/state/rotate.lock … --tick`): two ticks
# deciding at once is the double-flip race, so the board's tick is skipped while a cron tick holds it.
ROTATE_LOCK = Path(
    os.getenv("QUOTA_DASH_ROTATE_LOCK", str(Path.home() / ".claude" / "state" / "rotate.lock"))
)
SWITCH_HEADER = "X-Quota-Dash"  # required on POST /switch — a custom header forces a CORS preflight
SWITCH_TIMEOUT_S = float(os.getenv("QUOTA_DASH_SWITCH_TIMEOUT_S", "90"))
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_EMAIL_RE = re.compile(r"^[a-z0-9._%+-]{1,64}@[a-z0-9.-]{1,190}\.[a-z]{2,24}$")
_MAX_BODY = 4096

# The quota windows themselves. A cached reading older than its own window describes a window
# that has fully rolled over — reported as unknown, never as a reassuring percentage.
_FIVE_HOUR_S = 5 * 3600
_SEVEN_DAY_S = 7 * 86400

_JSON = OUT_DIR / "quota.json"
# The fleet's active-account pointer (a symlink). Read on every view so a flip — by the tick, a
# --switch, or the button — regenerates the board at once instead of waiting out the floor.
_POINTER = Path(os.getenv("QUOTA_DASH_POINTER", str(Path.home() / ".claude-fleet" / "active")))
# The rotation's per-account WEEKLY caps (`claude_rotate._caps_file`: {email: cap%}, the operator's
# browser reserve; 0 parks). The board edits it in place — same root as the rotation reads.
_THRESHOLDS_FILE = Path(
    os.getenv(
        "QUOTA_DASH_THRESHOLDS_FILE",
        str(
            Path(os.getenv("CLAUDE_FLEET_ROOT", str(Path.home() / ".claude-fleet")))
            / "thresholds.json"
        ),
    )
)
_CAPS_FILE = Path(
    os.getenv(
        "QUOTA_DASH_CAPS_FILE",
        str(Path(os.getenv("CLAUDE_FLEET_ROOT", str(Path.home() / ".claude-fleet"))) / "caps.json"),
    )
)

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
    # `now=None` means NOW. It was the signature's default from the first commit and no caller ever
    # passed it, so every call with a numeric-ts cache on disk raised `TypeError: NoneType - float`
    # and, from `_generate_locked`, froze the whole board at its last render (live 2026-09-06, board
    # stuck 67s and climbing; the guard came in with 610c01b8 and was REMOVED by the review-fix
    # 58041dbd, which aimed at `_display_order`'s dead branch and hit this live one — non-author
    # pass F1/F3, 2026-09-07).
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


# ── Search-API quotas: brave · firecrawl · exa (operator ask 2026-09-07) ─────────────────────
# The matrix says WHICH commands reach these services; this says how much of each is LEFT and when
# it renews. Same discipline as the pool balance above: fetched on a TTL OFF the render path,
# cached to disk, and the render NEVER makes a network call (a third-party endpoint on the critical
# path is how this board froze once already).
#
# ⚠️ WHAT EACH PROVIDER ACTUALLY EXPOSES — probed live 2026-09-07, not assumed:
#   firecrawl  GET /v1/team/credit-usage  →  remaining_credits, plan_credits, billing_period_end.
#              Everything asked for, in one call. Costs no credits.
#   brave      no balance endpoint at all; the quota IS the rate-limit header on any search
#              response — `X-RateLimit-Limit/Policy/Remaining/Reset`, comma-separated as
#              "<per-second>, <monthly>". ⚠️ A monthly value of 0 means UNLIMITED, not exhausted:
#              the docs say "15,000 requests per month (0 for unlimited)"
#              (https://api-dashboard.search.brave.com/documentation/guides/rate-limiting).
#              Reading it as "0 remaining" would paint an unlimited plan as dead. Reset is
#              SECONDS REMAINING in the window, not an epoch. ⚠️ Probing costs one search query,
#              which is why the TTL here is long.
#   exa        NOT AVAILABLE to us, and the panel says so rather than showing a blank. Usage lives
#              at admin-api.exa.ai/team-management/api-keys/{id}/usage and needs a SERVICE key from
#              the team-management surface — our search key gets 403 (Cloudflare 1010) — and even
#              that returns spend, never a balance or a renewal date. `POST /search` carries no
#              quota headers of any kind (verified against the full response header set).
API_QUOTAS_CACHE = OUT_DIR / "api-quotas.json"
API_QUOTAS_TTL_S = float(os.getenv("QUOTA_DASH_API_QUOTAS_TTL_S", "1800"))
API_QUOTAS_TIMEOUT_S = float(os.getenv("QUOTA_DASH_API_QUOTAS_TIMEOUT_S", "12"))
# `_FABRIK_ROOT` is defined further down with the commands block; resolve the repo root the
# same way here rather than reordering module state around a two-element tuple.
_MCP_CONFIGS = (
    Path.home() / ".claude.json",
    Path(__file__).resolve().parents[2] / ".mcp.json",
)


def _mcp_key(server: str, var: str) -> str | None:
    """The API key an MCP server is configured with. Environment wins; otherwise the `env` block of
    the MCP configs, which is where this box actually keeps them. Returns None rather than raising,
    and the VALUE never reaches a log or the page — only whether it exists."""
    if os.getenv(var):
        return os.getenv(var)
    for cfg in _MCP_CONFIGS:
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                block = node.get(server)
                if isinstance(block, dict):
                    val = (block.get("env") or {}).get(var)
                    if isinstance(val, str) and val and "${" not in val:
                        return val
                stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
            elif isinstance(node, list):
                stack.extend(v for v in node if isinstance(v, (dict, list)))
    return None


def _get_json(url: str, headers: dict[str, str]) -> tuple[dict, dict[str, str]]:
    """One GET → (parsed body, lowercased response headers). Isolated so the callers above it are
    testable without a network."""
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=API_QUOTAS_TIMEOUT_S) as resp:  # noqa: S310
        raw = resp.read()
        hdrs = {k.lower(): v for k, v in resp.headers.items()}
        try:
            return json.loads(raw.decode("utf-8")), hdrs
        except ValueError:
            return {}, hdrs


def _hdr_int(parts: list[str], i: int) -> int | None:
    """Element `i` of a comma-split rate-limit header as an int, or None. Never raises: these come
    from a third party, the elements are optional per plan, and one absent or non-numeric field must
    not discard an otherwise good reading."""
    try:
        return int(parts[i])
    except (IndexError, ValueError, TypeError):
        return None


def _brave_quota(now: float) -> dict:
    """Brave's quota rides the rate-limit headers of an ordinary search — there is no balance
    endpoint. Costs one query per probe."""
    key = _mcp_key("brave-search", "BRAVE_API_KEY")
    if not key:
        return {"state": "unconfigured"}
    _, hdrs = _get_json(
        "https://api.search.brave.com/res/v1/web/search?q=fabrik+quota+probe&count=1",
        {"Accept": "application/json", "X-Subscription-Token": key},
    )

    def pair(name: str) -> list[str]:
        return [p.strip() for p in (hdrs.get(name) or "").split(",")]

    limit, remaining, reset = (
        pair("x-ratelimit-limit"),
        pair("x-ratelimit-remaining"),
        pair("x-ratelimit-reset"),
    )
    if len(limit) < 2:
        return {"state": "no-headers"}
    # ⚠️ `limit` is length-checked but `remaining` and `reset` are SEPARATE headers — a plan that
    # sends only the per-second element used to raise IndexError, and a non-numeric element
    # ValueError, either of which discarded the WHOLE Brave reading (plan, rate, renewal) over one
    # missing field. `_hdr_int` makes every element optional and numeric-or-nothing.
    monthly_limit = _hdr_int(limit, 1) or 0
    out = {
        "state": "ok",
        "unit": "queries/mo",
        "per_second": _hdr_int(limit, 0) or 0,
        # 0 IS UNLIMITED, per the docs. Reporting it as "0 left" would read as a dead plan.
        "unlimited": monthly_limit == 0,
        "total": None if monthly_limit == 0 else monthly_limit,
        "remaining": None if monthly_limit == 0 else (_hdr_int(remaining, 1) or 0),
    }
    secs = _hdr_int(reset, 1)
    if secs is not None:
        out["renews_at"] = now + secs  # SECONDS REMAINING, never an epoch
    return out


def _firecrawl_quota(_now: float) -> dict:
    key = _mcp_key("firecrawl", "FIRECRAWL_API_KEY")
    if not key:
        return {"state": "unconfigured"}
    body, _ = _get_json(
        "https://api.firecrawl.dev/v1/team/credit-usage", {"Authorization": f"Bearer {key}"}
    )
    data = body.get("data") or {}
    if "remaining_credits" not in data:
        return {"state": "no-data"}
    out = {
        "state": "ok",
        "unit": "credits",
        "total": data.get("plan_credits"),
        "remaining": data.get("remaining_credits"),
    }
    end = data.get("billing_period_end")
    if isinstance(end, str):
        try:
            out["renews_at"] = datetime.fromisoformat(end.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return out


def _exa_quota(_now: float) -> dict:
    """Exa exposes nothing we can read. Stated, never blank — a missing row and an unavailable one
    are different facts, and only one of them is the operator's problem to fix."""
    if not _mcp_key("exa", "EXA_API_KEY"):
        return {"state": "unconfigured"}
    return {
        "state": "unavailable",
        "why": (
            "no balance endpoint for a search key — usage needs a team-management SERVICE key "
            "(ours gets 403) and returns spend, not a balance or a renewal date"
        ),
    }


API_QUOTA_SOURCES: tuple[tuple[str, str, object], ...] = (
    ("brave", "Brave Search", _brave_quota),
    ("firecrawl", "Firecrawl", _firecrawl_quota),
    ("exa", "Exa", _exa_quota),
)


# The TTL gate must NOT depend on the disk cache succeeding. Measured: with `API_QUOTAS_CACHE`
# unwritable (a stale directory in its place, a full disk, a permissions change), every read misses,
# every refresher cycle re-probes, and the 1800s TTL silently becomes the probe loop's 20s cadence —
# 4,320 Brave queries a day instead of 48, against a metered service, with nothing on the page or in
# the log to say so. The in-memory stamp closes that: disk is the cross-restart cache, memory is the
# rate limiter, and the fetch needs BOTH to be stale.
_api_quotas_mem: dict = {}


def _stamp(d: dict) -> float:
    """A dict's `ts` as a number, or 0.0 — never a raise. The cache is a file a human can edit and
    a `float("soon")` on the render path is another frozen board."""
    v = d.get("ts")
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0


def _api_quotas(now: float | None = None, *, fetch: bool = True) -> dict:
    """``{provider: {...}, "ts": epoch}`` — cached for ``API_QUOTAS_TTL_S``.

    RENDER PATH passes ``fetch=False``: cache only, never a network call, for the same reason the
    pool balance does. A provider that raises is recorded as its own error rather than taking the
    others down with it — three independent services, three independent verdicts.
    """
    global _api_quotas_mem  # rebound at the end; must be declared before the first read below
    now = time.time() if now is None else now
    try:
        cached = json.loads(API_QUOTAS_CACHE.read_text(encoding="utf-8"))
        cached = cached if isinstance(cached, dict) else {}
    except (OSError, ValueError):
        cached = {}
    # whichever reading is NEWER wins; memory covers the run, disk covers the restart.
    # `_stamp` refuses a non-numeric ts instead of letting float() raise: the cache file is
    # hand-editable and a ValueError here lands on the render path.
    mem = _api_quotas_mem
    if _stamp(mem) > _stamp(cached):
        cached = mem
    ts = cached.get("ts")
    ts = ts if isinstance(ts, (int, float)) and not isinstance(ts, bool) else None
    fresh = isinstance(ts, (int, float)) and 0.0 <= now - float(ts) < API_QUOTAS_TTL_S
    if fresh or not fetch:
        if cached:
            return {
                **cached,
                "age_s": now - float(ts) if isinstance(ts, (int, float)) else None,
                "stale": not fresh,
            }
        return {"ts": None, "age_s": None, "stale": True}
    out: dict = {"ts": now}
    for key, _label, fetcher in API_QUOTA_SOURCES:
        try:
            out[key] = fetcher(now)
        except Exception as exc:  # noqa: BLE001 — one dead provider may not blank the other two
            sys.stderr.write(f"quota_dashboard: {key} quota probe failed ({type(exc).__name__})\n")
            prev = cached.get(key)
            out[key] = (
                {**prev, "stale": True}
                if isinstance(prev, dict) and prev.get("state") == "ok"
                else {"state": "error", "error": type(exc).__name__}
            )
    # REBIND, never mutate in place: `{**cached}` above unpacks this very dict, and the refresher
    # thread does not hold `_gen_lock`, so a `.clear()` mid-unpack raised "dictionary changed size
    # during iteration" on the RENDER path — the frozen board, one more time. Rebinding is atomic;
    # a reader sees the whole old dict or the whole new one. Set BEFORE the disk write, because the
    # rate limiter must not depend on the disk (that was the 4,320-queries-a-day bug).
    _api_quotas_mem = out
    try:
        API_QUOTAS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        API_QUOTAS_CACHE.write_text(json.dumps(out), encoding="utf-8")
    except OSError:
        pass  # a lost cache costs the reading across a RESTART, never an extra probe this run
    return {**out, "age_s": 0.0, "stale": False}


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
        _api_quotas()  # TTL-gated inside; same thread, same off-the-render-path guarantee
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


# The external-services inventory (spec docs/superpowers/specs/2026-10-18-external-services-page-design.md
# § Failure, D9): the registry is read by a CHILD PROCESS (`inventory_read.py`) the board spawns and kills at
# the read's deadline, so the board stays stdlib, imports neither registry_db nor psycopg2, and a stalled
# Postgres is the section's error state, never a hung `/v/services`. ONE lock guards two fields — the last
# good read and the read in flight — and is never held across a read.
_INVENTORY_READ = Path(__file__).resolve().parent / "inventory_read.py"
INVENTORY_FRESH_S = 60.0  # the registry changes once a day: at most one read a minute
INVENTORY_REQUEST_S = 5.0  # one deadline per request, from its own arrival
INVENTORY_READ_S = (
    4.5  # a read's deadline from its spawning request's arrival: kill + render fit in 5 s
)
_INV_TIMEOUT = "ReadTimeout: registry read killed at its deadline"
_INV_LOCK_TIMEOUT = "ReadTimeout: registry lock not taken within the request's deadline"
_inv_lock = threading.Lock()
_inv_good: tuple[list, float | None, float] | None = (
    None  # (rows, synced_at, the read's START, monotonic)
)
_inv_flight: _InventoryRead | None = None


class _InventoryRead:
    """The read in flight: its child, its start and deadline (monotonic), a done event and its outcome
    (``("ok", rows, synced_at)`` or ``("err", message)``)."""

    def __init__(self, start: float, deadline_epoch: float) -> None:
        self.start = start
        self.deadline = start + INVENTORY_READ_S
        self.deadline_epoch = deadline_epoch
        self.proc: subprocess.Popen | None = None
        self.done = threading.Event()
        self.outcome: tuple | None = None


def _inventory_spawn(deadline_epoch: float) -> subprocess.Popen:
    """The child that reads the registry; the board suites replace this one name (tests/quota_dashboard_isolation.py)."""
    return subprocess.Popen(  # noqa: S603 — fixed argv, no shell, like the rotation call
        [sys.executable, str(_INVENTORY_READ), "--deadline", repr(deadline_epoch)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _first_line(text: object) -> str:
    return (str(text).splitlines() or [""])[0][:300]


def _inventory_outcome(out: bytes, code: int | None) -> tuple:
    """The child's stdout and exit status as an outcome: a fresh read, the child's own error string, or
    ``ReadFailed`` for anything that is not one JSON object matching its exit status."""
    try:
        obj = json.loads(out.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        obj = None
    if isinstance(obj, dict):
        rows, raw = obj.get("rows"), obj.get("synced_at")
        synced = _epoch(raw)
        if (
            code == 0
            and "error" not in obj
            and isinstance(rows, list)
            and all(isinstance(r, dict) for r in rows)
            and (raw is None or synced is not None)
        ):
            return ("ok", rows, synced)
        if code != 0 and "rows" not in obj and isinstance(obj.get("error"), str):
            return ("err", _first_line(obj["error"]))
    return ("err", f"ReadFailed: exit status {code}")


def _inventory_finish(flight: _InventoryRead, outcome: tuple) -> None:
    """Record the outcome, clear the in-flight field and wake every waiter — the one exit of every read."""
    global _inv_good, _inv_flight
    with _inv_lock:
        if outcome[0] == "ok":
            _inv_good = (outcome[1], outcome[2], flight.start)
        if _inv_flight is flight:
            _inv_flight = None
    flight.outcome = outcome
    flight.done.set()


def _inventory_wait(flight: _InventoryRead) -> None:
    """The spawning request's waiter thread: spawn, read the child until the read's deadline, kill and
    reap it past that — or past whatever else ended the read. ``communicate()`` after ``kill()`` drains
    and closes both pipes and cannot block."""
    outcome: tuple = ("err", "ReadFailed: no outcome")
    proc = None
    try:
        proc = _inventory_spawn(flight.deadline_epoch)
        flight.proc = proc
        try:
            out, _err = proc.communicate(timeout=max(0.0, flight.deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            outcome = ("err", _INV_TIMEOUT)
        else:
            outcome = _inventory_outcome(out or b"", proc.returncode)
    except Exception as exc:  # noqa: BLE001 — a spawn or read fault is the section's error state
        outcome = ("err", f"{type(exc).__name__}: {_first_line(exc)}".rstrip(": "))
    finally:
        if (
            proc is not None and proc.returncode is None
        ):  # a child still running is never left behind
            try:
                proc.kill()
                proc.communicate()
            except Exception:  # noqa: BLE001, S110 — the outcome is already decided; the kill is best effort
                pass
        _inventory_finish(flight, outcome)


def _inventory_classified_at() -> float | None:
    try:
        return _CLASSIFY_STAMP.stat().st_mtime
    except OSError:
        return None


def _inventory(ctx) -> dict:
    """The Services view's inventory data: ``{"rows", "synced_at", "classified_at"}`` or ``{"error": …}``.

    ONE deadline per request (5 s from its arrival), every wait bounded by what is left of it. Under the
    lock, for the length of the decision only: serve the last good read if it STARTED under 60 s ago, else
    spawn the child when none is in flight, else join the one in flight. A request that ends without a
    fresh result (its wait ran out, the child failed or was killed) is the error state; a failed read
    never replaces the last good one, and that one is served only inside its 60 s.
    """
    global _inv_flight
    arrival = time.monotonic()
    deadline = arrival + INVENTORY_REQUEST_S
    if not _inv_lock.acquire(
        timeout=INVENTORY_READ_S
    ):  # leaves room in the 5 s to answer and render
        return {"error": _INV_LOCK_TIMEOUT}
    spawned = False
    fresh = None
    try:
        good = _inv_good
        if good is not None and arrival - good[2] < INVENTORY_FRESH_S:
            fresh = good
        else:
            flight = _inv_flight
            if flight is None:
                flight = _inv_flight = _InventoryRead(arrival, time.time() + INVENTORY_READ_S)
                spawned = True
    finally:
        _inv_lock.release()
    if fresh is not None:  # the stat() runs after the lock is released
        return {
            "rows": fresh[0],
            "synced_at": fresh[1],
            "classified_at": _inventory_classified_at(),
        }
    if spawned:
        try:
            threading.Thread(
                target=_inventory_wait, args=(flight,), daemon=True, name="inventory-read"
            ).start()
        except Exception as exc:  # noqa: BLE001 — no thread, no read: clear the field so the next request starts afresh
            _inventory_finish(flight, ("err", f"{type(exc).__name__}: {_first_line(exc)}"))
    flight.done.wait(max(0.0, deadline - time.monotonic()))
    outcome = flight.outcome if flight.done.is_set() else None
    if outcome is None:
        return {"error": _INV_TIMEOUT}
    if outcome[0] != "ok":
        return {"error": outcome[1]}
    return {
        "rows": outcome[1],
        "synced_at": outcome[2],
        "classified_at": _inventory_classified_at(),
    }


def _pointer_slug() -> str | None:
    """The account the fleet pointer names, by the rotation CLI's own rule — the FINAL target's name
    (`resolve(strict=True).name`), so a pointer through a second symlink is not read as a flip. None
    for a pointer that is no symlink or dangles."""
    if not os.path.islink(_POINTER):
        return None
    try:
        return Path(_POINTER).resolve(strict=True).name or None
    except (OSError, RuntimeError):  # RuntimeError: a symlink loop
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


def _queue_for_render(payload: dict, now: float) -> list[dict]:
    """`_queue` with the SAME perishable-first key `_display_order` uses — one source."""

    def key(a: dict):
        seven = _util(a, "seven_day", now)
        five = _util(a, "five_hour", now)
        reset = (a.get("seven_day") or {}).get("resets_at_epoch")
        return (
            float(reset) if isinstance(reset, (int, float)) else float("inf"),
            seven if seven is not None else 101.0,
            five if five is not None else 101.0,
        )

    return _queue(payload, now, _key=key)


_RESERVE_PCT = float(os.getenv("QUOTA_RESERVE_PCT", "80"))


def _spend_data() -> dict:
    """The Usage view's data: the cost sidecar as written, unchanged — top-level ``built_at`` and
    ``per_model_spend``. Raises on a missing or unparseable file; `_view_data` turns that into the
    view's error state."""
    return json.loads(_COST_SIDECAR.read_text(encoding="utf-8"))


_policy_mod: tuple[float, object] | None = (
    None  # (source mtime, module) — `_pool_policy_on`'s cache
)


def _pool_policy_on() -> bool:
    """D-181/D-182 (2026-09-07): the OpenRouter pool is OFF by ruling while its credentials stay
    provisioned, so a dispatch here would still spend. The ONE policy is
    `scripts/enforcement/check_subagent_flywheel.py::_POOL_POLICY_ON` (fleet-synced; `FABRIK_POOL_POLICY`
    is its test seam). Unknown ⇒ OFF — "cannot read the policy" must never mean "go"."""
    global _policy_mod
    try:
        import importlib.util  # noqa: PLC0415

        path = _FABRIK_ROOT / "scripts" / "enforcement" / "check_subagent_flywheel.py"
        mtime = path.stat().st_mtime
        # re-executed only when the source moves (the `_work_module` shape): a view polls this every
        # refresh, and the function itself still runs per call, so its env seam is read each time
        if _policy_mod is None or _policy_mod[0] != mtime:
            spec = importlib.util.spec_from_file_location("_fabrik_pool_policy_source", path)
            if spec is None or spec.loader is None:
                return False
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(
                mod
            )  # by PATH, under a private name — a bare import could be shadowed
            _policy_mod = (mtime, mod)
        return bool(_policy_mod[1]._pool_policy_on())
    except Exception:  # noqa: BLE001 — unknown policy → no spend
        return False


# the picker's session bar is `_session_bar()` — lazy + guarded (F4); the old import-time
# `_TARGET_SESSION_MAX` constant bound before any monkeypatch and crashed on garbage


def _display_order(payload: dict, now: float) -> list[dict]:
    """Rows in the order rotation will actually use — the account-only projection of `_queue`.
    ONE key and ONE clock: this used to carry its own copy of the perishable-first key (unknown
    reset = now+365d, vs inf in `_queue_for_render`) and read `time.time()` while the old page's
    renderer passed `generated_at` — two copies that could disagree (review 2026-09-06, C5/C6)."""
    return [
        e["acct"]
        for e in _queue_for_render(payload, time.time() if now is None else now)
        if e["kind"] != "return"
    ]


def _returns_at(a: dict, now: float) -> float | None:
    """When an account that is NOT eligible now next becomes eligible — the same two buckets
    `claude_rotate._next_session_relief` uses: a weekly-walled or cap-walled account waits for
    its WEEKLY reset (a session reset does not lift a weekly wall); anything else waits for its
    5h reset. None when the reset is unknown or already past (an unread new account, a stale row),
    and None for a PARKED account, which no reset returns — only `--unpark` does."""
    if a.get("parked") is True:
        return None
    seven = _util(a, "seven_day", now)
    cap = a.get("weekly_cap")
    weekly_blocked = a.get("cap_walled") is True or (
        seven is not None and (seven >= 100.0 or (cap is not None and seven >= float(cap)))
    )
    win = a.get("seven_day") if weekly_blocked else a.get("five_hour")
    r = (win or {}).get("resets_at_epoch") if isinstance(win, dict) else None
    if not (isinstance(r, (int, float)) and float(r) >= now):
        return None
    r = float(r)
    if weekly_blocked:
        # a weekly reset does not lift a session the PICKER refuses (over
        # ROTATE_TARGET_SESSION_MAX_PCT, 85): the return is the LATER of the two — the same rule
        # `_next_session_relief` applies, at the same bar (closing review P3-2)
        bar = _session_bar()
        five = _util(a, "five_hour", now)
        fr = (a.get("five_hour") or {}).get("resets_at_epoch")
        # STRICT: the picker refuses `> bar` (`_flip_candidate_verdict`); `>=` promised a wait at
        # exactly the bar, where the picker takes the account now (R5)
        if five is not None and five > bar and isinstance(fr, (int, float)) and float(fr) > r:
            r = float(fr)
    return r


def _queue(payload: dict, now: float, _key=None) -> list[dict]:
    """The ROTATION QUEUE the Quota tab renders (operator, 2026-09-06): `#1` is the active
    account, `#2` the account the tick would pick now, then the rest in the order they would
    actually come up. Eligible accounts keep the picker's perishable-first order (this is still
    the read-only mirror of `_pick_flip_target`); the INELIGIBLE tail is ordered by WHEN each
    returns (`_returns_at`), unknown last — a session-spent account back in two hours precedes a
    cap-walled one back next week even though its session reads 100%. An active account at or
    over the flip line is about to be flipped away and will come back at its own reset: it gets a
    second entry — kind "return" — at that position, so it is "both #1 and #N", as asked.

    Entries: {"n", "slug", "acct", "kind": active|eligible|returns|return, "returns_at"}."""
    accounts = list(payload.get("accounts") or [])
    active = payload.get("active")
    key = _key or (lambda a: (0,))
    head = [a for a in accounts if active in (a.get("slugs") or [])]
    rest = [a for a in accounts if a not in head]
    eligible = sorted([a for a in rest if _eligible(a, now)], key=key)
    tail = [a for a in rest if not _eligible(a, now)]
    tail.sort(key=lambda a: (_returns_at(a, now) is None, _returns_at(a, now) or 0.0, key(a)))

    def entry(a: dict, kind: str, ra: float | None = None) -> dict:
        return {"slug": (a.get("slugs") or ["?"])[0], "acct": a, "kind": kind, "returns_at": ra}

    entries = [entry(a, "active") for a in head]
    entries += [entry(a, "eligible") for a in eligible]
    returns = [entry(a, "returns", _returns_at(a, now)) for a in tail]
    # a PARKED active account is flipped away and never comes back on a reset — no ghost row on
    # either route below (the relief branch recomputes its return from the raw reset)
    if head and head[0].get("parked") is not True:
        a = head[0]
        five = _util(a, "five_hour", now)
        ra = _returns_at(a, now)
        leaving = five is not None and five >= _trip_line(a)
        if not leaving and _relief_candidate(payload, a, now) is not None:
            # the tick will relief-flip this active away (D-171, R6): it returns when its
            # hottest window resets, not when it trips
            hot_key = (
                "seven_day"
                if (_util(a, "seven_day", now) or 0) >= (_util(a, "five_hour", now) or 0)
                else "five_hour"
            )
            r = (a.get(hot_key) or {}).get("resets_at_epoch")
            ra = float(r) if isinstance(r, (int, float)) and float(r) >= now else None
            leaving = ra is not None
        if leaving and ra is not None:
            ghost = entry(a, "return", ra)
            i = 0
            while i < len(returns) and (returns[i]["returns_at"] or float("inf")) <= ra:
                i += 1
            returns.insert(i, ghost)
    entries += returns
    for n, e in enumerate(entries, 1):
        e["n"] = n
    return entries


def _util(a: dict, k: str, now: float | None = None) -> float | None:
    """The window's utilization, or 0.0 for a CACHED row whose reset has already passed. `now`
    is the caller's clock when it has one (F8: a second clock inside functions handed an explicit
    one let `_util` and `_returns_at` disagree about the same row at render time)."""
    u = (a.get(k) or {}).get("utilization")
    if not isinstance(u, (int, float)):
        return None
    # the picker's rolled-over rule (`_flip_candidate_verdict`): a CACHED row whose reset has
    # passed holds an empty window — the cell renderer said "idle — rolled over" while this
    # read the raw 100% and called the row walled (closing review R4)
    r = (a.get(k) or {}).get("resets_at_epoch")
    t = time.time() if now is None else now
    if a.get("source") == "cache" and isinstance(r, (int, float)) and float(r) <= t:
        return 0.0
    return float(u)


def _env_pct(keys: tuple[str, ...], default: float = 85.0) -> float:
    """The ONE percent-knob parser (F4): each key in order, parsed the way
    `claude_rotate._env_float` parses it — blank/garbage/non-finite → the next key → default.
    Every bar the board reads lazily comes through here; a third parse with a fourth semantics
    once disagreed on 4 of 5 bad values (R6), and an import-time `float(os.getenv(...))` crashed
    the whole board on the very input this guards against."""
    for key in keys:
        raw = os.environ.get(key)
        if raw is None or raw.strip() == "":
            continue
        try:
            v = float(raw)
        except ValueError:
            print(f"quota_dashboard: {key}={raw!r} is not a number — ignored", file=sys.stderr)
            continue
        if math.isfinite(v):
            return v
        # LOUD like the picker's `_env_float`: a silently-disabled bar is the failure mode the
        # knob guards against (native closing reader N8 — the consolidation had dropped the warning)
        print(f"quota_dashboard: {key}={raw!r} is not finite — ignored", file=sys.stderr)
    return default


def _session_bar() -> float:
    """ROTATE_TARGET_SESSION_MAX_PCT, else ROTATE_DRAIN_THRESHOLD, else 85 — the picker's bar."""
    return _env_pct(("ROTATE_TARGET_SESSION_MAX_PCT", "ROTATE_DRAIN_THRESHOLD"))


def _eligible(a: dict, now: float | None = None) -> bool:
    """Would the tick pick this standby? (mirror of `_flip_candidate_verdict`, read-only side).
    `now` is the caller's clock when it has one (closing reader over c233c0b7: `_queue` judged
    eligibility on wall-clock and `returns_at` on the payload clock for the same row)."""
    five, seven = _util(a, "five_hour", now), _util(a, "seven_day", now)
    if a.get("cap_walled") is True or five is None or seven is None:
        return False
    line = _trip_line(a)
    if five >= 100.0 or seven >= 100.0 or five >= line or seven >= line:
        return False
    return five <= _session_bar()


# ── Commands tab (operator ask 2026-09-03) ───────────────────────────────────────────────────
# The second tab lists every /fabrik-* command in pipeline order with purpose / when / skip /
# next — DERIVED from the corpus (each `commands/_sources/fabrik-*.md` frontmatter description +
# the assembler's NEXT map), never typed here. PIPELINE_ORDER is the ONE hand-held fact: the
# order of CLAUDE.md § Pipeline (stages), then the gates, then the utilities — the test refuses a
# source with no slot and a slot with no source, so the list cannot drift from the corpus silently.
_FABRIK_ROOT = Path(__file__).resolve().parents[2]
_CLASSIFY_STAMP = (
    _FABRIK_ROOT / ".tmp" / "external-services" / "classify_last.json"
)  # the classifier's last run
# The amortized cost sidecar `claude_p_cost.py --refresh` rebuilds on the 06:00 cron. Read, never
# recomputed here: the dashboard renders, the producer measures. Resolved AFTER _FABRIK_ROOT but read
# only inside `_spend_data`, so call-time resolution is what matters.
_COST_SIDECAR = Path(
    os.getenv(
        "CLAUDE_P_COST", str(_FABRIK_ROOT / "scripts" / "kilo-benchmarks" / "claude_p_cost.json")
    )
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
    # utilities — /fabrik-task is the lane between a right-now fix and the spec chain
    "fabrik-task",
    "fabrik-docs-review",
    "fabrik-doc-converge",
    "fabrik-catchup",
    "fabrik-upstream",
    "fabrik-decommission",
    "fabrik-command-improve",
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


def _mtime_key(f: Path) -> tuple[str, int, int]:
    """`(path, mtime_ns, size)`, or `(path, -1, -1)` for a file that is not there — NEVER a raise.

    `exists()`-then-`stat()` is a race, and the file it races is the one `assemble_commands.py`
    PRUNES and rewrites: a render unlinks stale commands and writes the rest, so a regeneration
    landing mid-render raised `FileNotFoundError` out of `_load_commands` → `render` → `generate`,
    on the `_regen_async` daemon thread — the board would stop updating and say nothing on the page.
    `-1` is a real key value: absence is a state the key must DISTINGUISH, not drop, so a file
    appearing or vanishing always re-keys. SIZE rides along because mtime alone cannot see a rewrite
    that preserves the timestamp — `cp -p`, a restore, an archive extraction."""
    try:
        st = f.stat()
        return (str(f), st.st_mtime_ns, st.st_size)
    except OSError:
        return (str(f), -1, -1)


_cmd_cache_key: tuple[tuple[str, int, int], ...] | None = None
_cmd_cache_rows: list[dict[str, str]] = []


def _load_commands() -> list[dict[str, str]]:
    """Every `commands/_sources/fabrik-*.md`, in PIPELINE_ORDER (unknown names last, alphabetical,
    so a new command is visible before its slot exists). Cached on the mtimes of the sources, the
    ASSEMBLER (it owns the NEXT column) and the RENDERED corpus (the matrix reads it) — the last two
    change with no `_sources/` mtime moving, and a key missing them freezes the table it feeds."""
    src = _FABRIK_ROOT / "commands" / "_sources"
    files = sorted(src.glob("fabrik-*.md"))
    global _cmd_cache_key, _cmd_cache_rows
    asm = _FABRIK_ROOT / "commands" / "assemble_commands.py"
    # the NEXT column comes from the assembler, which can change with no _sources mtime moving
    # the RENDERED corpus is what the external-services matrix reads, and the assembler can
    # rewrite it with no _sources mtime moving — both belong in the key or the dots go stale
    rendered = [RENDERED_COMMANDS / f.name for f in files]
    key = tuple(_mtime_key(f) for f in [*files, asm, *rendered])
    if _cmd_cache_key == key:
        return list(_cmd_cache_rows)
    nxt = _next_map()
    rows = []
    for f in files:
        try:
            head = f.read_text(encoding="utf-8")[:6000]
        except (OSError, UnicodeDecodeError):
            head = ""  # an unreadable source is an EMPTY description, never a dead board
        m = _DESC_RE.search(head)
        parsed = _parse_description(m.group(1) if m else "")
        services, is_rendered = _command_services(f.stem)
        rows.append(
            {
                "name": f.stem,
                "next": nxt.get(f.stem, "").strip(),
                "services": services,
                "natives": _command_natives(f.stem),
                "rule": _command_seat_rule(f.stem),
                "tiers": _command_tiers(f.stem),
                "rendered": is_rendered,
                **parsed,
            }
        )
    order = {n: i for i, n in enumerate(PIPELINE_ORDER)}
    rows.sort(key=lambda r: (order.get(r["name"], len(order)), r["name"]))
    _cmd_cache_key, _cmd_cache_rows = key, rows
    return list(rows)


# ── External services per command (operator ask 2026-09-06) ──────────────────────────────────
# The matrix under the commands table: which outside-the-box service each command actually
# reaches. DERIVED on every render from the corpus, exactly like the table above — a command
# that starts using firecrawl tomorrow grows its dot with no edit here.
#
# ⚠️ READ THE RENDERED CORPUS, NOT `_sources/`. `assemble_commands.py` appends shared fragments
# (the pool dispatch policy, the close-out FEEDBACK block) to every command, so the source text
# under-reports badly: measured 2026-09-06 the pool reads 17 of 36 in `_sources/` and 26 in
# `~/.claude/commands/`, and fabrik-mail 2 vs 36. The rendered file is what the agent is handed,
# so it is what the board reports; a command with no rendered file falls back to its source and
# the intro says how many rows did (an unrendered corpus under-reports — never silently).
#
# A dot means the command NAMES THE SERVICE'S OWN INVOCATION TOKEN (`fanout(`, `WebSearch`,
# `mcp__firecrawl`, `fabrik apply`) — not that it mentions the service in prose. That precision
# is deliberate: `VPS`, `GitHub` and `flywheel` all appear in the beat-routing table every
# command carries, so a prose match rated all 36 commands as VPS-touching, which is false.
#
# THE ONE HAND-HELD FACT is this registry. Adding an external service to the fleet means adding
# a row here; `tests/test_quota_dashboard.py` holds its shape (unique keys, compiling patterns,
# and each of the three most-used services still detected) but it cannot know about a service
# nobody registered. That is the maintenance contract, and it is the only one.
_EXT_SERVICES: tuple[tuple[str, str, str, str], ...] = (
    (
        "pool",
        "pool",
        "OpenRouter subagent pool — OFF by ruling (D-181/D-182, 2026-09-07); a dot would mean a LIVE "
        "fanout() / pick_models() call survives OUTSIDE the POOL OFF HTML comments the corpus keeps for re-enable",
        # a bare `libs/subagents` PATH is prose about the module, not a call into it (measured:
        # it alone credited fabrik-rivals, whose line names the key autoloader). An import IS a call.
        r"fanout\(|pick_models\(|`fanout`|`pick_models`|(?:from|import) libs\.subagents",
    ),
    (
        "fly",
        "flywheel",
        "Flywheel recording — RETIRED with the pool (D-181/D-182, 2026-09-07): a native seat has no "
        "AgentResult, so nothing records and nothing is scored. A dot here means a LIVE record_agent_run() "
        "or set_quality() call survived outside the POOL OFF HTML comments",
        # the CALL form only: the D-181 banner names both symbols in its suspended-instruction
        # enumeration, which is a retirement notice, not a dispatch (and is blanked below anyway).
        r"record_agent_run\(|set_quality\(",
    ),
    (
        "rec",
        "recall",
        "session-recall MCP — search_chats / recent_chats over past sessions",
        r"search_chats|recent_chats|mcp__session-recall|session-recall",
    ),
    ("web", "web", "Claude's own WebSearch / WebFetch", r"\bWebSearch\b|\bWebFetch\b"),
    ("brv", "brave", "Brave Search MCP", r"brave[_-]web[_-]search|mcp__brave-search|brave-search"),
    (
        "fc",
        "firecrawl",
        "Firecrawl MCP — scrape / search / extract",
        r"firecrawl_[a-z]|mcp__firecrawl",
    ),
    (
        "exa",
        "exa",
        "Exa MCP — web_search_exa / web_fetch_exa",
        r"web_(?:search|fetch)_exa|mcp__exa",
    ),
    (
        "brw",
        "browser",
        "Headless browser — playwright / chrome-devtools / the fabrik-gui subagent",
        # NOT bare "Browserless"/"Gotenberg" — those are fleet SERVICES a project may deploy,
        # prose about someone else's architecture, not this command reaching for a browser.
        r"mcp__playwright|mcp__chrome-devtools|`(?:playwright|chrome-devtools)`"
        r"|@axe-core/playwright|\bbrowser_[a-z][a-z_]+\b|fabrik-gui",
    ),
    (
        "gh",
        "github",
        "GitHub through the gh CLI",
        r"\bgh (?:pr|issue|api|repo|release|run|search|browse|workflow|auth)\b",
    ),
    (
        "vps",
        "VPS",
        "The VPS fleet over SSH — fabrik apply / redeploy / plan, deployer_ssh",
        r"\bfabrik (?:apply|redeploy|plan|destroy|status)\b|\bssh (?:vps|root@)|deployer_ssh|\bvps[1-3]\b",
    ),
    ("aic", "ai-consult", "ai-consult — the metered frontier panel (fabrik-lib)", r"ai[-_]consult"),
    (
        "cit",
        "citations",
        "fabrik-citation-verifier MCP",
        # NOT the bare server name: its only occurrence in the corpus is fabrik-data-contract
        # saying the verifier "does not apply here" — a NEGATION, which no regex can read. The
        # tool token is the invocation; the server name is prose about it.
        r"verify_citation|verify_batch|mcp__fabrik-citation-verifier",
    ),
    (
        "mail",
        "mail",
        "fabrik-mail — scripts/mail.py send / list / ack",
        r"scripts/mail\.py|mail\.py send",
    ),
)
_EXT_COMPILED = tuple((k, re.compile(pat)) for k, _lbl, _t, pat in _EXT_SERVICES)
# The corpus keeps the pool contract inside HTML comments for re-enable (D-181/D-182); a dot must
# follow the LIVE text only, so comments are blanked before any detector runs.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
# Native Claude Task subagent types a command may name (the `subagent_type` vocabulary + the two
# built-ins the corpus dispatches by name). Order = display order.
_NATIVE_TYPES: tuple[str, ...] = (
    "fabrik-reviewer",
    "fabrik-researcher",
    "fabrik-gui",
    "design-review",
    "general-purpose",
)
# The model tier a seat is dispatched on. Read from a ±160-character window around each seat
# mention — the corpus writes them together ("≥1 native `fabrik-reviewer` on **Opus**"), and a
# whole-paragraph window would smear every tier in a paragraph across every seat in it.
_MODEL_TIERS: tuple[str, ...] = ("opus", "sonnet", "haiku", "fable")
_MODEL_RE = re.compile(r"\b(" + "|".join(_MODEL_TIERS) + r")\b", re.I)
_MODEL_WINDOW = 160
# `general-purpose` is the one type that is also an ordinary English adjective, and the corpus
# proves it: 13 of its 14 live mentions are backticked seat references and the 14th is
# fabrik-vision's "Never wire a general-purpose vendor SDK" — prose about someone else's
# architecture. So that one type is counted only in code-span form. The `fabrik-*` names carry no
# such ambiguity and are counted bare too (they are written bare in real dispatches: `subagent_type:
# fabrik-gui`, "dispatches fabrik-gui subagents").
_CODE_SPAN_ONLY = ("general-purpose",)
_NATIVE_COMPILED = tuple(
    (
        n,
        re.compile(
            (r"`" + re.escape(n) + r"`")
            if n in _CODE_SPAN_ONLY
            else (r"(?<![\w/-])" + re.escape(n) + r"(?![\w-])")
        ),
    )
    for n in _NATIVE_TYPES
)
# Boilerplate every command carries by assembly, never a dispatch of its own: the D-181 banner's
# suspended-instruction enumeration and its type enumeration, the subagents fragment's identical
# type enumeration, and the close-out fragment's
# "Subagents are ephemeral" paragraph (measured 2026-09-08: with these live, 35 of 35 commands
# "named" four types; blanked, the column follows the command's own steps).
_BOILERPLATE = (
    re.compile(r"\*\*⚠️ POOL OFF — D-181.*?(?=\*\*⚠️ Floor —|\n\n|\Z)", re.S),
    re.compile(r"\(`fabrik-reviewer` · `fabrik-researcher` · `fabrik-gui` · general-purpose\)"),
    re.compile(r"Claude Task subagents \(`fabrik-reviewer`[^)]*\)"),
    re.compile(r"Subagents are ephemeral\..*?(?:\n\n|\Z)", re.S),
)


def _command_live_text(name: str) -> tuple[str, bool]:
    """(the command's text with HTML comments blanked, whether the RENDERED file was read)."""
    rendered = RENDERED_COMMANDS / f"{name}.md"
    for path, is_rendered in (
        (rendered, True),
        (_FABRIK_ROOT / "commands" / "_sources" / f"{name}.md", False),
    ):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        return _HTML_COMMENT_RE.sub("", text), is_rendered
    return "", False


def _command_stripped_text(name: str) -> str:
    """The command's live text with assembled boilerplate blanked — what its OWN steps say."""
    text, _ = _command_live_text(name)
    for rx in _BOILERPLATE:
        text = rx.sub("", text)
    return text


def _command_tiers(name: str) -> tuple[str, ...]:
    """Every model tier the command's own steps name, attributed to a seat or not.

    The seat column can only report a tier written NEXT to a seat; a command that says "Haiku only
    for trivial-mechanical checks" in its own tiering paragraph names a real tier that no seat
    mention is near (operator, 2026-09-08: "i dont see model names fable? opus? sonnet? haiku?").
    Measured that day, banner blanked: opus 21, sonnet 23, haiku 5, fable 1 of 35 commands.
    """
    found = {m.lower() for m in _MODEL_RE.findall(_command_stripped_text(name))}
    return tuple(sorted(found, key=_MODEL_TIERS.index))


# How many seats a command dispatches is NOT the number of types it names — under D-186 it is one
# seat per INDEPENDENT unit of the surface, and every fanning-out command names its own unit ("per
# screen", "per persona", "per claim", "per rival"). Showing the type count where the reader expects
# a seat count made /fabrik-review read as "1 subagent" when its own steps dispatch an Opus floor
# plus one Sonnet seat per failure-class group (operator, 2026-09-08: "i want to see subagents counts
# correctly"). These two regexes read the RULE out of the command's own steps.
_FLOOR_RE = re.compile(r"Floor — every \w+ dispatches ≥1 native")
# A unit is a DISPATCH unit only when a seat word stands near it: "one seat per claim" is a fan-out,
# "naming, per claim, landed / deferred / refuted" is a report format, and "States per screen: empty
# · loaded" is a UI checklist. The author-blind round on 7178fa27 found five commands whose cell
# named units from report prose, table headers and checklist rows — and missed "per GROUP" (the
# rule's own flagship example), "per TICKET" and "per external dependency". The match now needs a
# seat word within `_DISPATCH_WINDOW` characters, allows one adjective between "per" and the unit,
# and spans a line break ("seat per\nclaim" was the real instruction the regex could not see).
_UNIT_RE = re.compile(
    r"\bper\s+(?:[a-z-]+\s+)?(independent unit|unit|failure-class group|class group|group|lens"
    r"|screen/route|screen|persona|claim|rival|axis|surface|doc/subsystem|pack|behaviou?r"
    r"|journey-bundle|journey|epic file|epic|module/area|entity|flow-bundle|stale doc"
    r"|checklist class|dependency|ticket|fact|phase|file)(?![\w-])",
    re.I,
)
_DISPATCH_RE = re.compile(
    r"\b(seat|seats|subagent|subagents|grounder|grounders|finder|finders|reviewer|reviewers|"
    r"researcher|researchers|reconciler|reconcilers|dispatch|dispatched|fan[- ]?out|in parallel|"
    r"partition|partitions|partitioned)\b",
    re.I,
)
_DISPATCH_WINDOW = 120
_UNIT_LABEL = {
    "independent unit": "unit",
    "failure-class group": "group",
    "class group": "group",
    "screen/route": "screen",
    "doc/subsystem": "doc",
    "behaviour": "behavior",  # both spellings live in the corpus; one unit, not two
    "epic file": "epic",
    "journey-bundle": "journey",
    "flow-bundle": "flow",
}
# a command may state a FIXED floor instead of a per-unit rule — /fabrik-review-scoped's "the floor
# is 3 readers" is the deliberate light-command exception, and reporting it as "no rule" hides a
# real number the reader asked for.
_FIXED_RE = re.compile(r"floor is (\d\s*[–-]\s*\d|\d) (readers?|seats?|native seats?)", re.I)


def _command_seat_rule(name: str) -> tuple[bool, tuple[str, ...]]:
    """(does it carry the Opus authoritative floor, the UNITS its own steps fan out over).

    The shared boilerplate — the D-181 banner, which carries the fragment's sizing paragraph — is
    blanked by `_command_stripped_text` first, so 20 commands that include it do not all report the
    same rule. A unit counts only with a seat word within `_DISPATCH_WINDOW` characters."""
    own = _command_stripped_text(name)
    units: list[str] = []
    for m in _UNIT_RE.finditer(own):
        window = own[max(0, m.start() - _DISPATCH_WINDOW) : m.end() + _DISPATCH_WINDOW]
        if not _DISPATCH_RE.search(window):
            continue
        u = re.sub(r"\s+", " ", m.group(1).lower())
        u = _UNIT_LABEL.get(u, u)
        if u not in units:
            units.append(u)
    if not units:
        m = _FIXED_RE.search(own)
        if m:
            units.append(f"!{m.group(1).replace(' ', '')} {m.group(2)}")
    return bool(_FLOOR_RE.search(own)), tuple(units)


def _command_natives(name: str) -> list[tuple[str, tuple[str, ...]]]:
    """The native subagent types the command's LIVE text names, each with the model tiers named
    beside it, in display order (operator ask 2026-09-08: per command, how many native subagents,
    their names, and on which model)."""
    text = _command_stripped_text(name)
    seats = sorted((m.start(), m.end(), n) for n, rx in _NATIVE_COMPILED for m in rx.finditer(text))
    models: dict[str, list[str]] = {n: [] for n, _rx in _NATIVE_COMPILED}
    # Each tier is awarded to exactly ONE seat — the nearest. An earlier fence bounded each seat's
    # window by its NEIGHBOURS instead, which arbitrates only when a third seat stands between two
    # of them: "`fabrik-reviewer` on Opus and then `general-purpose`" gave Opus to both.
    for tm in _MODEL_RE.finditer(text):
        para_lo = text.rfind("\n\n", 0, tm.start()) + 1
        para_hi = text.find("\n\n", tm.end())
        para_hi = len(text) if para_hi < 0 else para_hi
        best: tuple[int, str] | None = None
        for s, e, n in seats:
            if e <= para_lo or s >= para_hi:
                continue  # a tier named in another paragraph is not "beside" this seat
            gap = s - tm.end() if s >= tm.end() else tm.start() - e
            if gap <= _MODEL_WINDOW and (best is None or gap < best[0]):
                best = (gap, n)
        if best:
            tier = tm.group(1).lower()
            if tier not in models[best[1]]:
                models[best[1]].append(tier)
    out: list[tuple[str, tuple[str, ...]]] = []
    for n, rx in _NATIVE_COMPILED:
        if models[n] or rx.search(text):
            # canonical tier order, so two commands naming the same pair read the same
            out.append((n, tuple(sorted(models[n], key=_MODEL_TIERS.index))))
    return out


RENDERED_COMMANDS = Path(
    os.getenv("QUOTA_DASH_RENDERED_COMMANDS", str(Path.home() / ".claude" / "commands"))
)


def _command_services(name: str) -> tuple[set[str], bool]:
    """(services this command reaches, whether the RENDERED file was the text read).

    Unreadable either way → an empty set and `False`, so the row shows no dots and the intro
    counts it as un-rendered; the board never guesses a service it could not see."""
    # UnicodeDecodeError is a ValueError, NOT an OSError: one non-UTF-8 byte in one command file
    # used to raise straight through `render` into the regeneration thread — `_command_live_text`
    # swallows both, and blanks the HTML comments so a commented pool contract never lights a dot.
    text, is_rendered = _command_live_text(name)
    if not text and not is_rendered:
        return set(), False
    for rx in _BOILERPLATE:
        text = rx.sub("", text)
    return {k for k, rx in _EXT_COMPILED if rx.search(text)}, is_rendered


_BUDGET_TTL_S = 60
_budget_lock = threading.Lock()
# "data" is the parsed reading `_budget_data` serves (None: invalidated or never read)
_budget_cache: dict = {"ts": 0.0, "data": None, "thread": None, "gen": 0}


def _budget_probe(gen: int | None = None) -> dict:
    """The slow half of the box-budget line: ONE `dispatch_headroom.py --json` run — its `box_caps`
    carries the read-only and the heavy bound from the same box probe, so the fleet quota round-trip
    happens once per refresh, not twice (round-2 finding: the banner tripled probe volume on a module
    whose header exists to bound it). NEVER on a request thread — see `_budget_cached`. Reads what the
    box AND the quota allow right now (D-191 — the operator wants the maximum visible); a fleet HOLD
    says "dispatch nothing" instead of the box number beside `hold=True`. Fail-soft to
    ``{"error": …}``: no panel may break the board."""
    script = _FABRIK_ROOT / "scripts" / "sysadmin" / "dispatch_headroom.py"
    try:
        args = [sys.executable, str(script), "--units", "1", "--json"]
        d = json.loads(
            subprocess.run(args, capture_output=True, text=True, timeout=45, check=True).stdout
        )
        data = {**_budget_reading(d), "read_at": time.time()}
    except Exception as exc:  # noqa: BLE001 — a panel may never break the board
        data = {"error": f"{type(exc).__name__}: {exc}"}
    with _budget_lock:
        # a probe that started before an invalidation (an account switch) must not land its
        # OLD-account reading with a fresh stamp: it writes only if its generation is still current
        # (round-5 finding); a synchronous caller (`--once`) passes no generation
        if gen is None or gen == _budget_cache["gen"]:
            _budget_cache.update(ts=time.time(), data=data)
        else:
            # orphaned: kick a probe for the CURRENT generation now, or the placeholder stays
            # until some later render happens to notice this thread is dead (round-6 finding)
            cur = _budget_cache["gen"]
            th = _budget_cache["thread"]
            # one re-kick at a time: K stale generations spawned K fleet probes (round-10 Opus)
            if th and th.is_alive() and th is not threading.current_thread():
                return data
            nxt = threading.Thread(
                target=_budget_probe, args=(cur,), name="budget-banner", daemon=True
            )
            _budget_cache["thread"] = nxt
            nxt.start()
    return data


def _budget_reading(d: dict) -> dict:
    """One `dispatch_headroom.py --json` payload reduced to what the box AND the quota allow now, per
    half — the numbers the Overview's box-budget line prints, computed once. Raises on a payload the
    line cannot read (no ``box_caps``, a non-numeric cap), as the banner always has."""
    caps = d.get("caps") or {}
    q = d.get("quota") or {}
    box_caps = d.get("box_caps")
    if not isinstance(box_caps, dict):
        # an older script without the pair: the read-only cap must never stand in for the
        # heavy one (it is the HIGHER number — a fail-open in the OOM direction; round-3 seat)
        raise ValueError("dispatch_headroom.py --json carries no box_caps — probe out of date")
    seats = []
    for label, key in (("read-only", "read_only"), ("heavy", "heavy")):
        box_cap = box_caps.get(key)
        bound = [box_cap, caps.get("concurrency_cap")] + (
            [caps["quota_cap"]] if "quota_cap" in caps else []
        )
        allowed = 0 if q.get("hold") else min(int(x) for x in bound if x is not None)
        taken = int((d.get("siblings") or {}).get("seats") or 0)
        # "(box 3 after 21 reserved)" read as a 24-seat box when the FLOOR had raised a
        # 2-seat remainder to 3: name the floor when it is what the reader sees (round-7)
        # the label keys on the script's OWN verdict (`box_caps_floored`, from `floor_granted`)
        # — never on `box_cap == floor`: an honest remainder of 3 is not the floor, and a
        # dead box probe's floor is not the siblings' doing (round-8/9 Opus findings)
        floored = bool(taken) and bool((d.get("box_caps_floored") or {}).get(key))
        seats.append(
            {
                "label": label,
                "key": key,
                "allowed": allowed,
                "box": box_cap,
                "taken": taken,
                "floored": floored,
                "quota_cap": caps.get("quota_cap"),
                "has_quota_cap": "quota_cap" in caps,
            }
        )
    return {
        "seats": seats,
        "cli_cap": caps.get("concurrency_cap", "?"),  # read from the payload, never re-hardcoded
        "hold": bool(q.get("hold")),
        "quota": q,
        "caveats": _budget_caveat_lines(d),
    }


def _all_reasons(d: dict) -> list:
    """Every half the probe carries — `reasons` (the run's own), `reasons_read_only`,
    `heavy_reasons` — deduped in order; a payload from a probe that predates the halves says so
    instead of passing as "no heavy caveats" (round-11 Opus finding: the guard was asymmetric)."""
    out: list = []
    seen: set = (
        set()
    )  # dedupe on the RAW line — the prefixed form never matched its twin (round 13)
    for key in ("reasons", "reasons_read_only", "heavy_reasons"):
        for x in d.get(key) or []:
            if isinstance(x, str) and x not in seen:
                seen.add(x)
                # a heavy-ONLY cause is LABELLED — beside a read-only `floor_granted: 0` an
                # unlabelled "floor granted" read as a contradiction (round-12 Opus finding); a
                # cause in BOTH halves renders once, unlabelled — it is not heavy-only (round 14)
                out.append(("heavy half — " + x) if key == "heavy_reasons" else x)
    if "heavy_reasons" not in d:
        out.append(
            "probe payload predates heavy_reasons — the heavy half's caveats are not subtracted"
        )
    return out


def _budget_caveat_lines(d: dict) -> list[str]:
    """The script's own confidence caveats, as PLAIN strings — a failed sibling probe ("seats unknown, not
    subtracted"), sibling sessions with no seat figure (a LOWER bound), an env-only own id. Round-7
    finding: the banner printed a confident 23 while `reasons` said the sibling count was unknown."""
    # every DEGRADED-state reason the script emits (round-8 finding: "held at the floor" — a
    # box or quota probe that failed — rendered as a confident number with no caveat)
    words = (
        "not subtracted",
        "LOWER bound",
        "own-session id",
        "held at the floor",
        "standby",
        "drain band",
        "NO active account",
        "NO usable reading",
        "floor granted",
        "HARD cap binds",
        "is not a number",
        "dispatch nothing",
        "nothing to partition",
    )
    # case-INSENSITIVE (round-9 finding): the script says "NOT subtracted" for an unreadable
    # sibling record — the over-dispatch caveat — and a lowercase word never matched it
    lines = [r for r in _all_reasons(d) if any(w.lower() in r.lower() for w in words)]
    sib = d.get("siblings") or {}
    # the sibling-failure fallback is gated on the SIBLING caveat being absent, not on any
    # caveat at all (round-11 finding: an unrelated HARD-cap line hid a failed sibling probe)
    if (
        isinstance(sib, dict)
        and sib.get("ok") is False
        and not any("sibling seats unknown" in x for x in lines)
    ):
        lines.append(f"{sib.get('why') or 'probe failed'} — sibling seats unknown, not subtracted")
    return lines


def _budget_cached() -> dict | None:
    """The cached reading (None: invalidated or never read). A stale cache starts ONE background
    refresh and returns what it has — never a subprocess on the caller's thread: the probe is a
    subprocess with a fleet round-trip inside it, and a view is served on a request thread (the
    page hang of 2026-08-18)."""
    with _budget_lock:
        data = _budget_cache.get("data")
        fresh = time.time() - _budget_cache["ts"] < _BUDGET_TTL_S and data is not None
        th = _budget_cache["thread"]
        if not fresh and not (th and th.is_alive()):
            th = threading.Thread(
                target=_budget_probe,
                args=(_budget_cache["gen"],),
                name="budget-banner",
                daemon=True,
            )
            _budget_cache["thread"] = th
            th.start()
    return data


def _budget_data() -> dict:
    """The box-budget reading the Overview's Health strip shows, from `_budget_cached`:
    `_budget_reading`'s dict (its ``caveats`` plain strings, for the view to escape once), or
    ``{"error": …}`` when the probe failed, ``{"computing": True}`` before the first reading lands,
    ``{"disabled": True}`` under `QUOTA_DASH_BUDGET=0` (a test or a headless run that must not shell
    out to the fleet probe)."""
    if os.getenv("QUOTA_DASH_BUDGET", "1") == "0":
        return {"disabled": True}
    data = _budget_cached()
    return data if data else {"computing": True}


# ── Repos tab (operator ask 2026-10-11) ─────────────────────────────────────────────────────────
# "a tab should come first named repos. in it i want to be able to select different repos start
# with fabrik first." Every repo under FABRIK_OPT_DIR (the box's /opt seam, which tests/conftest.py
# pins to an empty dir for every test) that keeps a `.fabrik/work` store, and its REMAINING work:
# not done/dropped, not hidden by a closed marker. "Remaining" and "claimed" are work.py's own
# rules, imported by path — a second copy of the closed-marker rule would drift from it.
#
# ISOLATION: the Work and Overview views read it on request in the handler thread, through
# `_cached_collect` (cached REPOS_TTL_S under its own lock). It never runs inside generate(), so a
# slow or broken store can neither stall the 20 s probe loop nor delay the rotation trigger. Every
# git call work.py makes here is capped at 1 s (`_hook_git_budget`); a repo that still fails shows
# its own banner and the others list.
_HUB_OWNERS = ("coordinator", "infra", "fleet", "intel", "kaizen", "operator")
# The hub agents whose owner chip and section show in every repo pane, even with nothing open, so
# "kaizen has nothing" and "kaizen is missing" never look the same (operator ask 2026-10-11).
_HUB_AGENTS = ("coordinator", "infra", "fleet", "intel", "kaizen")
REPOS_TTL_S = float(os.getenv("QUOTA_DASH_REPOS_TTL_S", "20"))
NEXT_CAP = 160  # `next` is the bulk of the rows (1.0 MB of 1.4 MB measured); the cell is capped
NEXT_TIP_CAP = (
    600  # and so is its tooltip — an uncapped tooltip re-adds the whole MB (measured 1.69 MB)
)
_repos_lock = threading.Lock()
_repos_gen = 0  # bumped by every board write; a collect that saw it move is not cached
# The two collectors the Work and Overview views read, cached REPOS_TTL_S under ONE lock and dropped by
# a board write — so a collector never sees two concurrent callers (its warnings sink is one list) and
# runs at most once per REPOS_TTL_S however many views and tabs refresh.
_work_cache: tuple[float, list[dict] | Exception] | None = None
_box_cache: tuple[float, dict | Exception] | None = None
_work_mod: tuple[float, object, list[str]] | None = None  # (work.py mtime, module, warnings sink)


def _work_module():
    """work.py under a PRIVATE module name (never sys.modules["work"], which tests/test_work.py
    owns), re-imported when its mtime moves. Its `_warn` is rebound on this private object to a
    list, never via redirect_stderr — that swaps the process-wide stderr of a threaded server."""
    global _work_mod
    import importlib.util

    path = _FABRIK_ROOT / "scripts" / "work.py"
    mtime = path.stat().st_mtime
    if _work_mod is None or _work_mod[0] != mtime:
        spec = importlib.util.spec_from_file_location("_quota_dash_work", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"{path} cannot be loaded")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sink: list[str] = []
        mod._warn = sink.append
        _work_mod = (mtime, mod, sink)
    return _work_mod[1], _work_mod[2]


def _collect_work(opt: Path) -> list[dict]:
    """One entry per repo with a work store: {name, items, error, skipped, main, root} — ``main`` (the
    main checkout a board write goes to) and ``root`` (the tree the items were read from, where a
    verdict's snapshot token is re-read) only once the store was read."""
    wk, sink = _work_module()
    out: list[dict] = []
    with wk._hook_git_budget():
        seen: set[Path] = set()
        # real directories first, so a symlinked alias never takes a repo's own name
        stores = sorted(opt.glob("*/.fabrik/work"), key=lambda p: (p.parent.parent.is_symlink(), p))
        for store in stores:
            repo = store.parent.parent.resolve()
            if repo in seen:  # a symlink to a repo already listed would double every count
                continue
            seen.add(repo)
            entry: dict = {"name": store.parent.parent.name, "items": [], "error": None}
            del sink[:]
            try:
                if not store.is_dir():  # work.py reads a non-dir store as empty: an all-clear lie
                    raise NotADirectoryError(f"{store} is not a directory")
                items = list(wk._iter_items(repo))
                # where a board write goes: the MAIN checkout, as pause/resume resolve it — never a
                # linked worktree that happens to sit at /opt/<name> (W-e1f1a1bd)
                entry["main"] = str(wk._worktrees(repo)[0].resolve())
                entry["root"] = str(repo)
                closed = wk._closed_ids(repo)
                claims = wk._live_claims(repo)
                for it in items:
                    if it.get("status") in wk.RESOLVED or it.get("id") in closed:
                        continue
                    claim = claims.get(it.get("id"))
                    entry["items"].append(
                        {
                            **it,
                            "_prio": wk._priority(it),
                            "_claim": str(claim.get("agent") or "a session") if claim else "",
                        }
                    )
            except Exception as exc:  # one repo's failure is that repo's banner, never the page's
                entry["error"] = f"{type(exc).__name__}: {exc}"
                entry["items"] = []
            entry["skipped"] = list(sink)  # unreadable item, claim or closed-marker files
            out.append(entry)
    return out


def _cached_collect(which: str, collect):
    """``collect()`` cached REPOS_TTL_S under `_repos_lock`, dropped by a board write
    (`_drop_repos_cache`). A collector that RAISES is cached too, and the same error is raised again
    until the entry expires — a failing (perhaps slow) collector re-run on every render, under the
    lock, would hold every view behind it. A write that landed while it ran makes the result served
    once, never cached."""
    global _work_cache, _box_cache
    with _repos_lock:
        now = time.time()
        cached = _work_cache if which == "work" else _box_cache
        if cached and now - cached[0] < REPOS_TTL_S:
            if isinstance(cached[1], BaseException):
                # its traceback dropped: the same instance re-raised would grow one per hit, all TTL long
                raise cached[1].with_traceback(None)
            return cached[1]
        gen = _repos_gen
        try:
            value = collect()
        except Exception as exc:
            value = exc
        entry = (now, value) if _repos_gen == gen else None
        if which == "work":
            _work_cache = entry
        else:
            _box_cache = entry
        if isinstance(value, BaseException):
            raise value
        return value


def _work_data() -> list[dict]:
    """`_collect_work(_opt_root())`, through `_cached_collect`."""
    return _cached_collect("work", lambda: _collect_work(_opt_root()))


def _box_data() -> dict:
    """`agent_status.collect_box(_opt_root())` — the Agents block's collector — through `_cached_collect`."""
    return _cached_collect("box", lambda: _status_module().collect_box(_opt_root()))


def _owner_order(owners: set[str]) -> list[str]:
    hub = [o for o in _HUB_OWNERS if o in owners]
    rest = sorted(o for o in owners if o and o not in _HUB_OWNERS)
    return hub + rest + ([""] if "" in owners else [])


# ── the agents the Overview lists (operator 2026-10-15, W-7159f8e2) ─────────────────────────────────
# "i also want to see which agents is active and working on what … for all repos". The data is
# scripts/agent_status.py::collect_box — derived from the process table, run records and claims, never
# stored. Loaded by path under a private name and re-imported when its mtime moves, like work.py above.
_status_mod: tuple[float, object] | None = None


def _status_module():
    global _status_mod
    import importlib.util

    path = _FABRIK_ROOT / "scripts" / "agent_status.py"
    mtime = path.stat().st_mtime
    if _status_mod is None or _status_mod[0] != mtime:
        spec = importlib.util.spec_from_file_location("_quota_dash_agent_status", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"{path} cannot be loaded")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _status_mod = (mtime, mod)
    return _status_mod[1]


# ── Pause / Resume from the board (operator 2026-10-15: "i want a button to be added there to send
# pause command to running agent" + "also the resume button"; W-7159f8e2 part 3). The board acts
# only on a (repo, agent) pair it rendered with a button, through the HUB's work.py (`--repo` the
# recorded main checkout), as the OPERATOR: the child gets an ALLOWLISTED environment — no CLAUDE_*
# identity (a server started from an agent shell carries one; measured), no GIT_* (GIT_DIR overrides
# --repo; measured). This rests on work.py's identity being environment-only (whoami_agent.py "from
# the environment ONLY"); a process-tree fallback there would have to revisit it. Every rule about
# who may pause or resume stays work.py's (D-910): the board never writes a marker itself.
# COBRA: the cheapest "working button" lets the server's own identity through — the test sets
# CLAUDE_AGENT, CLAUDE_CODE_SESSION_ID and GIT_DIR on the server and asserts the operator's marker.
_PAUSE_TARGETS: dict[tuple[str, str], dict] = {}  # REPLACED whole on each build, never mutated
# Every publisher's last targets, by slice: the name of the view that rendered them. The two
# registries above and `_ITEM_TARGETS` are the UNION, recomputed whole on each publish, so one view's
# refresh never evicts another view's buttons; a publisher that failed replaces ITS slice with [].
_TARGET_SLICES: dict[str, dict[str, dict]] = {"pause": {}, "item": {}}
_targets_lock = threading.Lock()


def _publish_slice(kind: str, slice_: str, entries: dict) -> None:
    """Store ``entries`` as ``slice_``'s targets of ``kind`` and rebind that registry to the union of
    every slice — all under `_targets_lock`, so an older publisher can never rebind after a newer one.
    The slice is re-inserted LAST, so on a shared key the most recently published slice wins."""
    global _PAUSE_TARGETS, _ITEM_TARGETS
    with _targets_lock:
        slices = _TARGET_SLICES[kind]
        slices.pop(slice_, None)
        slices[slice_] = entries
        union: dict = {}
        for part in slices.values():
            union.update(part)
        if kind == "pause":
            _PAUSE_TARGETS = union
        else:
            _ITEM_TARGETS = union


_PAUSE_ENV_KEEP = ("PATH", "HOME", "LANG", "TZ")
PAUSE_TIMEOUT_S = 30


def _publish_pause_targets(repos: list[dict], slice_: str = "repos") -> None:
    _publish_slice(
        "pause",
        slice_,
        {
            (str(r.get("name")), str(a.get("name"))): {
                "main": str(r.get("main")),
                "paused": a.get("paused"),
            }
            for r in repos
            for a in r.get("agents", [])
            if a.get("can_pause") and not r.get("error")
        },
    )


def pause_agent(repo: object, agent: object, action: object, why: object = "") -> tuple[int, dict]:
    """Pause or resume one agent the board shows. (http_status, json_body): 400 for an unknown pair
    or action (nothing runs), 502 when work.py refuses or times out (its message), 200 on success."""
    if action not in ("pause", "resume") or not isinstance(repo, str) or not isinstance(agent, str):
        return 400, {"ok": False, "error": "body needs repo, agent and action pause|resume"}
    target = _PAUSE_TARGETS.get((repo, agent))
    if target is None:  # a restarted server, or a frame older than the last build: rebuild once
        _rebuild_targets("overview")  # the view whose Agents table carries Pause / Resume
        target = _PAUSE_TARGETS.get((repo, agent))
    if target is None:
        return 400, {
            "ok": False,
            "error": f"{agent!r} in {repo!r} has no pause button on the board",
        }
    hub = _FABRIK_ROOT / "scripts" / "work.py"
    base = [sys.executable, str(hub), "--repo", target["main"]]
    if action == "pause":
        argv = [*base, "pause", "--by=dashboard", f"--why={_clean_note(why)}", "--", agent]
    else:  # every marker the row showed — a pause keyed by a window's tree carries the tree's name
        shown = target.get("paused") or {}
        names = [str(n) for n in shown.get("names") or [shown.get("name") or agent]]
    runs = [argv] if action == "pause" else [[*base, "resume", "--", n] for n in names]
    return _run_work(target["main"], runs)


def _clean_note(text: object) -> str:
    """One printable line of at most 200 characters — a NUL or a lone surrogate would make
    subprocess raise ValueError/UnicodeEncodeError."""
    return " ".join("".join(c for c in str(text or "") if c.isprintable() or c.isspace()).split())[
        :200
    ]


def _run_work(main: str, runs: list[list[str]]) -> tuple[int, dict]:
    """Run each argv in order against ``main`` as the operator (the allowlisted env, ``cwd=main``);
    the first refusal stops the rest. 200 with the outputs, or 502 with work.py's own message."""
    env = {k: v for k, v in os.environ.items() if k in _PAUSE_ENV_KEEP or k.startswith("LC_")}
    out: list[str] = []
    try:
        for cmd in runs:
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=PAUSE_TIMEOUT_S, env=env, cwd=main
            )
            if r.returncode:
                _drop_repos_cache()
                return 502, {
                    "ok": False,
                    "error": (r.stderr or r.stdout or "work.py failed").strip()[:400],
                }
            out.append(r.stdout.strip())
    except subprocess.TimeoutExpired:
        _drop_repos_cache()
        return 502, {
            "ok": False,
            "error": "work.py timed out — nothing confirmed; the next refresh is authoritative",
        }
    except (OSError, ValueError) as exc:
        return 502, {"ok": False, "error": f"work.py could not run: {exc}"[:400]}
    _drop_repos_cache()  # the next page build shows the change
    return 200, {"ok": True, "output": "\n".join(out)[:400]}


# Accept / Reject / comment per work item (operator 2026-10-15: "i want a way to accept or reject them
# manually also add a comment next to them", W-e1f1a1bd): POST /item-verdict acts only on a (repo, id)
# the last build listed, through the HUB's `work.py verdict` as the operator — the same runner, env and
# guard as Pause/Resume (D-916). What accept and reject do to an item stays work.py's.
# (repo, id) -> (main checkout, the tree the card was read from); the union of every slice, REPLACED whole
_ITEM_TARGETS: dict[tuple[str, str], tuple[str, str]] = {}
# The last day of the 14-day window after the redesign (T07, coded 2026-10-17): until it ends a verdict
# with no snapshot token — a page loaded before the redesign — is accepted and `/repos.html` redirects
# to `/#work`; after it the verdict is refused 409 and `/repos.html` is 404 (spec § Lifecycle, § Which
# actions confirm: one date for both). A work item removes the redirect and this legacy branch on it.
_LEGACY_TOKEN_UNTIL: date | None = date(2026, 10, 31)


def _legacy_window_open(today: date | None = None) -> bool:
    """True through `_LEGACY_TOKEN_UNTIL` (local date, inclusive); always True while it is None."""
    return _LEGACY_TOKEN_UNTIL is None or (today or date.today()) <= _LEGACY_TOKEN_UNTIL


def _publish_item_targets(repos: list[dict], slice_: str = "repos") -> None:
    _publish_slice(
        "item",
        slice_,
        {
            (str(r.get("name")), str(i.get("id"))): (
                str(r["main"]),
                str(r.get("root") or r["main"]),
            )
            for r in repos
            if r.get("main") and not r.get("error")
            for i in r.get("items", [])
        },
    )


def _tree_token(tree: str, item: str) -> str | None:
    """The item's snapshot token as it stands in ``tree``; None for a missing, unreadable or
    non-object item file."""
    try:
        current = json.loads(
            (Path(tree) / ".fabrik" / "work" / f"{item}.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    return _snapshot.token(current) if isinstance(current, dict) else None


def _token_refusal(main: str, root: str, item: str, token: object) -> str | None:
    """Why the verdict is refused 409, or None to let it run.

    ``"diverged"``: ``root`` — the tree the card was read from — is not ``main``, the tree
    `work.py verdict --repo main` writes, and the item differs between them. No token the card can show
    would pass, so the refusal says so: the board's checkout is out of step with the repo's main and the
    operator must sync it (fail closed, never a verdict on an item the operator did not see).
    ``"changed"``: the trees agree but the posted token differs from the item as it stands — or the item
    file is missing, unreadable or not an object — or no token came once the legacy window
    (`_LEGACY_TOKEN_UNTIL`, local date, inclusive) has closed. Read before work.py takes its store
    lock — the window between the two is accepted (one operator, one board)."""
    if token is None:
        return None if _legacy_window_open() else "changed"
    if Path(item).name != item:  # the target lookup admits only listed ids; never a path
        return "changed"
    seen = _tree_token(root, item)
    if root != main and seen != _tree_token(main, item):
        return "diverged"
    return None if seen is not None and seen == token else "changed"


def item_verdict(
    repo: object, item: object, action: object, text: object = "", token: object = None
) -> tuple[int, dict]:
    """Accept, reject or comment on one item the board lists. (http_status, json_body): 400 for an
    unknown pair or action, or a reject/comment with no words (nothing runs), 409 ``changed`` when the
    snapshot ``token`` the card carried no longer matches the item, or ``diverged`` when the board's
    tree and main disagree about it (`_token_refusal`; nothing runs), 502 when work.py
    refuses or times out (its message), 200 on success."""
    if (
        action not in ("accept", "reject", "comment")
        or not isinstance(repo, str)
        or not isinstance(item, str)
    ):
        return 400, {"ok": False, "error": "body needs repo, item and action accept|reject|comment"}
    note = _clean_note(text)
    if action != "accept" and not note:
        return 400, {"ok": False, "error": f"{action} needs the operator's words"}
    target = _ITEM_TARGETS.get((repo, item))
    if target is None:  # a restarted server, or a frame older than the last build: rebuild once
        _rebuild_targets("work")  # it lists every open item; the Overview, awaiting ones only
        target = _ITEM_TARGETS.get((repo, item))
    if target is None:  # a faulted Work pane publishes nothing; the Overview's card may show it
        # through the cache the Work rebuild just filled: one store collection per miss, never two
        _render_view("overview", triggers=False)
        target = _ITEM_TARGETS.get((repo, item))
    if target is None:
        return 400, {"ok": False, "error": f"{item!r} in {repo!r} is not on the board"}
    main, root = target
    refusal = _token_refusal(main, root, item, token)
    if refusal is not None:
        return 409, {"ok": False, "error": refusal}
    hub = _FABRIK_ROOT / "scripts" / "work.py"
    opts = [f"--text={note}"] if note else []
    return _run_work(
        main,
        [
            [
                sys.executable,
                str(hub),
                "--repo",
                main,
                "verdict",
                *opts,
                "--by=dashboard",
                "--",
                item,
                str(action),
            ]
        ],
    )


def _drop_repos_cache() -> None:
    """After a board write: the next view re-reads the stores, and a collect already running is not
    cached. Lock-free on purpose — taking `_repos_lock` would wait out a 5 s collect inside the POST."""
    global _repos_gen, _work_cache, _box_cache
    _repos_gen += 1
    _work_cache = None
    _box_cache = None


_gen_lock = threading.Lock()


def generate() -> dict:
    """Probe, write quota.json and `_LAST_STATUS`; returns the payload. Falls back to the last good
    payload on error. SERIALIZED: the probe loop, a past-the-floor view, a pointer-moved view and a
    switch all land here; without this lock two probes could run at once (double API cost) and race
    the file write (scoped review 2026-09-03). A second caller waits for the running probe, never
    starts one."""
    with _gen_lock:
        return _generate_held()


def _generate_held() -> dict:
    """The body of `generate`, run with `_gen_lock` held. A pass that raises (the probe's own failure
    is caught inside; this is everything else) records its error CLASS as the probe failure, so the
    quota views' stale banner names it (W-6a0f3c65: a traceback in the log was all the 2026-09-07
    freeze left, for 16 cycles). Class only — a message can carry paths."""
    try:
        return _generate_locked()
    except Exception as exc:
        _LAST_PROBE_FAILURE[0] = (time.time(), type(exc).__name__)
        sys.stderr.write(f"quota_dashboard: regeneration failed ({type(exc).__name__})\n")
        raise


# The payload `_generate_locked` actually used on its last pass — the fallback included — and the time of
# the last SUCCESSFUL probe behind it, carried unchanged through every fallback pass so an outage ages
# it (None: unknown, stale at once). And when the probe last failed, with its error class, cleared by a
# good probe. Each is one tuple swapped in whole; readers take a single reference.
_LAST_STATUS: list[tuple[float | None, dict] | None] = [None]
_LAST_PROBE_FAILURE: list[tuple[float, str] | None] = [None]
# Every WRITE of `_LAST_STATUS` holds this — the seed's check-read-set and a probe's set — so a slow
# seed from a request thread can never land after (and over) a newer probe's reading.
_status_lock = threading.Lock()


def _set_last_status(ts: float | None, payload: dict) -> None:
    with _status_lock:
        _LAST_STATUS[0] = (ts, payload)


def _carry_last_status(payload: dict) -> None:
    """A fallback pass: ``payload`` under the last GOOD probe's time, unchanged (None: unknown)."""
    with _status_lock:
        prev = _LAST_STATUS[0]
        _LAST_STATUS[0] = (prev[0] if prev else None, payload)


def _seed_last_status() -> None:
    """Seed `_LAST_STATUS` ONCE from quota.json on disk, before any probe of this process can rewrite
    it: the file's mtime when it is a real reading, None when it holds `probe_failed` (the fallback
    wrote it, so its mtime says nothing about the reading's age). A missing file seeds nothing."""
    if _LAST_STATUS[0] is not None:
        return
    with _status_lock:
        if _LAST_STATUS[0] is not None:
            return
        try:
            mtime = _JSON.stat().st_mtime
            payload = json.loads(_JSON.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(payload, dict):
            _LAST_STATUS[0] = (None if payload.get("probe_failed") else mtime, payload)


def _generate_locked() -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _seed_last_status()  # before this pass's fallback can rewrite quota.json and launder its age
    error = None
    try:
        payload = _probe()
        _JSON.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        _set_last_status(time.time(), payload)
        _LAST_PROBE_FAILURE[0] = None
    except Exception as exc:  # transport/CLI/JSON — degrade visibly, never blank the page
        _LAST_PROBE_FAILURE[0] = (time.time(), type(exc).__name__)
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
        _carry_last_status(payload)  # the last GOOD probe's time, unchanged
        try:
            _JSON.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        except OSError:
            pass
    return payload


_regen_lock = threading.Lock()
_LAST_REGEN: list[threading.Thread | None] = [None]  # the most recent background worker, joinable
_LAST_SYNC_REGEN: list[float] = [0.0]  # when the pointer-moved trigger last started a regeneration


def _regen_async() -> threading.Thread | None:
    """One background regeneration at a time; drop the request if one is already running.
    Returns the worker thread (None when the request was dropped) so a caller that must
    observe the regeneration — a test — can ``join`` it instead of racing it."""
    if not _regen_lock.acquire(blocking=False):
        return None

    def work() -> None:
        try:
            generate()
        except Exception:  # noqa: BLE001 — `_generate_held` recorded and logged it; end cleanly
            pass
        finally:
            _regen_lock.release()

    t = threading.Thread(target=work, daemon=True, name="quota-regen")
    try:
        t.start()
    except Exception as exc:  # noqa: BLE001 — no thread: free the lock, or no regeneration runs again
        _regen_lock.release()
        sys.stderr.write(f"quota_dashboard: regeneration could not start ({type(exc).__name__})\n")
        return None
    return t


_LAST_TRIGGER: list[float] = [0.0, 0.0, 0.0]  # [flip, drain, relief] tiers — independent cooldowns


def _drain_band() -> float:
    """ROTATE_DRAIN_THRESHOLD (default 85) — the band the tick's drain-band relief flip keys on
    (D-171); the same parser as `_session_bar` (F4: it was a fourth copy)."""
    return _env_pct(("ROTATE_DRAIN_THRESHOLD",))


def _hottest(a: dict, now: float | None = None) -> float | None:
    vals = [v for v in (_util(a, "five_hour", now), _util(a, "seven_day", now)) if v is not None]
    return max(vals) if vals else None


def _relief_candidate(payload: dict, active_row: dict, now: float | None = None) -> dict | None:
    """The tick's relief precondition, mirrored read-only (R6): the active's hottest window is
    at/over the drain band AND some other account is eligible with BOTH windows below it."""
    hot = _hottest(active_row, now)
    band = _drain_band()
    if hot is None or hot < band:
        return None
    for a in payload.get("accounts") or []:
        if a is active_row or not _eligible(a, now):
            continue
        five, seven = _util(a, "five_hour", now), _util(a, "seven_day", now)
        if five is not None and seven is not None and max(five, seven) < band:
            return a
    return None


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
    bar = _drain_band() if blind else _trip_line(row)
    sess = float(five) if isinstance(five, (int, float)) else None
    hot = sess is not None and sess >= bar
    drain = sess is not None and sess >= DRAIN_TRIGGER_THRESHOLD
    relief = None
    if hot or row.get("cap_walled") is True:
        tier = 0  # flip tier
    elif drain:
        tier = 1  # urgent-drain tier: the tick decides whether a successor exists
    elif (
        relief := _relief_candidate(payload, row)
    ) is not None:  # only when the higher tiers passed
        # relief tier (R6): the tick's drain-band relief flip (D-171) keys on the HOTTEST window,
        # session or weekly — this fast path keyed on the session alone, so a weekly-driven
        # relief waited for the */5 cron while a fresh account idled
        tier = 2
    else:
        return None
    now = time.time()
    if now - _LAST_TRIGGER[tier] < TRIGGER_COOLDOWN_S:
        return None
    _LAST_TRIGGER[tier] = now
    if tier == 2:
        why = (
            f"hottest window {_hottest(row) or 0:.0f}% >= drain band {_drain_band():.0f}% while "
            f"{(relief or {}).get('slugs', ['?'])[0]} is below it (relief tier, D-171)"
        )
    elif tier == 1:
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
                f"quota_dashboard: tick exit {proc.returncode}: "
                f"{' | '.join(p.strip() for p in (proc.stdout or '', proc.stderr or '') if p.strip())[:300]}\n"
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
    _seed_last_status()  # the payload's time, before the first probe can fail and rewrite quota.json

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


def _shell_page() -> str:
    """`GET /`: the app shell, the Overview first (spec § Contract deltas). It carries no data, so it
    answers at once whatever the probe is doing; `app.js` fetches the view the URL names."""
    return _ui.shell([(v, _strings.t(f"nav.{v}")) for v in _views.VIEWS], "overview")


def _quota_json() -> bytes:
    """`GET /quota.json`: the last payload on disk, served at once — never a wait on the probe (on
    2026-08-18 a hung probe held every page load for its full 60 s cap). A payload older than
    MAX_AGE_S, or none at all, starts ONE background regeneration, so a polling client keeps it
    current; nothing on disk yet is ``{}``. A moved fleet pointer starts one even when the file is
    fresh: its ``active`` is then known to be stale, and serving it on until MAX_AGE_S would hide a
    flip the board can already see."""
    try:
        age = time.time() - _JSON.stat().st_mtime
        body = _JSON.read_bytes()
    except OSError:
        age, body = math.inf, b"{}"
    if age >= MAX_AGE_S:
        _LAST_REGEN[0] = _regen_async()
    elif _pointer_moved() and time.time() - _LAST_SYNC_REGEN[0] > PROBE_TIMEOUT_S:
        # the quota views' window (`_status_triggers`): a mismatch that never clears costs one probe
        # per PROBE_TIMEOUT_S, never one per poll
        worker = _regen_async()
        if worker is not None:
            _LAST_SYNC_REGEN[0] = time.time()
            _LAST_REGEN[0] = worker
    return body


# ── the command-centre views (plan 2026-10-17-plan-1, T02) ─────────────────────────────────────────
# `GET /v/<view>` answers one view's fragment. Each view module is a pure renderer (`dashboard_ui.views`);
# this module hands it everything it reads from here as DATA, because no view may import this module.
_QUOTA_VIEWS = (
    "overview",
    "accounts",
)  # the views that show quota data: the stale banner, the triggers
_WILDCARD_HOSTS = {"", "0.0.0.0", "[::]"}  # bind-everything addresses: never an admitted Host


def _host_literal(host: str) -> str:
    """``host`` as a Host header names it: lowercased, an IPv6 literal in brackets."""
    h = host.strip().lower()
    return f"[{h}]" if ":" in h and not h.startswith("[") else h


_STATIC_TYPES = {"app.css": "text/css; charset=utf-8", "app.js": "text/javascript; charset=utf-8"}


def _guarded(fn, *args, **kwargs) -> object:
    """A collector's own output, or ``{"error": "<Type>: <message>"}`` when it raises — that key only."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 — one collector's failure is its own key's state
        return {"error": f"{type(exc).__name__}: {exc}"}


def _status_data() -> dict:
    """`_LAST_STATUS` for a view: ``{"payload", "read_at", "probe_failure"}`` — ``read_at`` the last good
    probe's time (None: unknown) — seeded from quota.json in a fresh process; never a probe."""
    if _LAST_STATUS[0] is None:
        _seed_last_status()
    cur = _LAST_STATUS[0]
    if cur is None:
        return {"error": "no reading yet"}
    fail = _LAST_PROBE_FAILURE[0]
    return {
        "payload": cur[1],
        "read_at": cur[0],
        "probe_failure": {"at": fail[0], "error": fail[1]} if fail else None,
    }


def _stale_after_s() -> float:
    """How old the last good reading may get before it is stale — the ONE bound the stale banner and
    the Overview's Health strip share: one probe interval plus one probe timeout plus a minute, since
    a healthy slow probe reaches interval + timeout before it lands (review round 1, S1)."""
    return PROBE_INTERVAL_S + PROBE_TIMEOUT_S + 60


def _status_stale(now: float) -> bool:
    """The stale banner's bound: the probe failed after the payload's last
    good probe, or that probe is older than one interval plus one timeout plus a minute, or its time is
    unknown. No payload at all is no banner — the view says "no reading yet" itself."""
    cur = _LAST_STATUS[0]
    if cur is None:
        return False
    ts, fail = cur[0], _LAST_PROBE_FAILURE[0]
    if ts is None or (fail is not None and fail[0] > ts):
        return True
    return now - ts > _stale_after_s()


def _status_banner(now: float) -> object:
    """T01's stale banner for a quota view, or None while the payload is fresh."""
    if not _status_stale(now):
        return None
    cur, fail = _LAST_STATUS[0], _LAST_PROBE_FAILURE[0]
    ts = cur[0] if cur else None
    if ts is None:
        age = _strings.t("stale.age_unknown")
    else:
        age_s = max(0.0, now - ts)
        age = (
            _strings.t("stale.age_s", n=f"{age_s:.0f}")
            if age_s < 120
            else _strings.t("stale.age_min", n=f"{age_s / 60:.0f}")
        )
    if fail is not None and (ts is None or fail[0] > ts):
        when = datetime.fromtimestamp(fail[0]).astimezone().strftime("%H:%M:%S")
        cause = _strings.t("stale.cause.failed", time=when, error=fail[1])
    else:
        cause = _strings.t("stale.cause.old")
    return _ui.stale_banner(age, cause)


def _status_triggers() -> None:
    """The two request-side triggers, on the quota views — both BACKGROUND regenerations, so a view
    is never held by a probe (`_view_data`: "never a probe"; the 2026-08-18 hang). A moved pointer
    (measured 2026-09-02: after a --switch the board showed the OLD account until the next probe)
    starts one at once, at most once per PROBE_TIMEOUT_S and none while one is already running; the
    next refresh shows the new account. A payload older than MAX_AGE_S (quota.json's mtime — every
    pass rewrites it) starts one too."""
    if _pointer_moved() and time.time() - _LAST_SYNC_REGEN[0] > PROBE_TIMEOUT_S:
        worker = _regen_async()
        if worker is not None:
            _LAST_SYNC_REGEN[0] = time.time()
            _LAST_REGEN[0] = worker
        return
    try:
        age = time.time() - _JSON.stat().st_mtime
    except OSError:
        age = math.inf
    if age >= MAX_AGE_S:
        _LAST_REGEN[0] = _regen_async()


def _health(data: dict, now: float) -> dict:
    """The Overview's health reading: ``stale`` — the quota reading past `_stale_after_s` (the stale
    banner's own bound, so the strip and the banner never disagree) —
    and ``failed`` — every collector key holding ``error``, plus a probe failure newer than the payload."""
    stale: list[dict] = []
    cur = _LAST_STATUS[0]
    if cur is not None and (cur[0] is None or now - cur[0] > _stale_after_s()):
        stale.append({"view": "accounts", "age_s": None if cur[0] is None else now - cur[0]})
    failed = [
        {"key": k, "error": str(v["error"])}
        for k, v in data.items()
        if isinstance(v, dict) and "error" in v
    ]
    fail = _LAST_PROBE_FAILURE[0]
    if fail is not None and (cur is None or cur[0] is None or fail[0] > cur[0]):
        failed.append({"key": "probe", "error": fail[1], "at": fail[0]})
    return {"stale": stale, "failed": failed}


def _owner_orders(work: object) -> dict[str, list[str]]:
    """Per repo, the owner order the Work view's pane uses: an unowned awaiting item is the
    operator's, every hub agent and the empty owner present even at zero."""
    if not isinstance(work, list):
        return {}
    out: dict[str, list[str]] = {}
    for r in work:
        owners = {
            str(it.get("owner") or "")
            or ("operator" if it.get("status") == "awaiting-operator" else "")
            for it in r.get("items") or []
        }
        out[str(r.get("name"))] = _owner_order(owners | set(_HUB_AGENTS) | {""})
    return out


def _view_data(name: str, ctx) -> dict:
    """What view ``name`` receives: collector outputs unchanged (one that raises becomes
    ``{"error": …}`` for its key only) and the configuration values today's builders read. Never a
    probe: the status is `_LAST_STATUS`, the work and box data the REPOS_TTL_S caches."""
    data: dict = {"now": ctx.now, "refresh_s": REFRESH_S, "probe_interval_s": PROBE_INTERVAL_S}
    if name == "overview":
        data.update(
            work=_guarded(_work_data),
            box=_guarded(_box_data),
            status=_guarded(_status_data),
            budget=_guarded(_budget_data),
        )
        data["health"] = _health(data, ctx.now)
    elif name == "work":
        work = _guarded(_work_data)
        data.update(
            work=work,
            hub_agents=list(_HUB_AGENTS),
            owner_order=_guarded(_owner_orders, work),
            repos_ttl_s=REPOS_TTL_S,
            next_cap=NEXT_CAP,
            next_tip_cap=NEXT_TIP_CAP,
        )
    elif name == "accounts":
        status = _guarded(_status_data)
        data.update(
            status=status,
            queue=(
                _guarded(_queue_for_render, status["payload"], ctx.now)
                if "payload" in status
                else {"error": status["error"]}
            ),
            trigger_threshold=TRIGGER_THRESHOLD,
            reserve_pct=_RESERVE_PCT,
            five_hour_s=_FIVE_HOUR_S,
            seven_day_s=_SEVEN_DAY_S,
            pool_policy_on=_guarded(_pool_policy_on),  # anything but True is OFF to a view
            slug_re=_SLUG_RE.pattern,
            email_re=_EMAIL_RE.pattern,
        )
    elif name == "usage":
        data["spend"] = _guarded(_spend_data)
    elif name == "commands":
        data.update(
            commands=_guarded(_load_commands),
            ext_services=[
                {"key": k, "label": label, "title": title}
                for k, label, title, _pat in _EXT_SERVICES
            ],
            rendered_root=str(RENDERED_COMMANDS),  # the corpus the matrix read — the server's knob
        )
    elif name == "services":
        data.update(
            pool=_guarded(_pool_credits, fetch=False),
            apis=_guarded(_api_quotas, ctx.now, fetch=False),
            inventory=_guarded(_inventory, ctx),
            warn_usd=CREDITS_WARN_USD,  # the pool's drain line, as the alert reads it
        )
    else:
        raise LookupError(f"no view named {name!r}")
    return data


def _render_view(name: str, *, triggers: bool = True) -> str:
    """One view's fragment: its data, its module's ``collect`` (merged over it) and ``render``, the
    stale banner on a quota view, the whole wrapped in a root element whose ``data-stamp`` hashes the
    markup. A view that raises renders its error state in words and empties ITS target slice; every
    other view's targets stay published (the union). EVERY step — the triggers, the banner, the
    wrapper, the publish — runs inside the guard, so no fault drops the connection. ``triggers=False``
    skips the quota views' regeneration triggers (`_rebuild_targets`: a POST needs targets, not a probe)."""
    try:
        if triggers and name in _QUOTA_VIEWS:
            _status_triggers()
        ctx = _views.ViewContext(opt_root=_opt_root(), fabrik_root=_FABRIK_ROOT, now=time.time())
        mod = _views.load(name)
        data = _view_data(name, ctx)
        collect = getattr(mod, "collect", None)
        if callable(collect):
            data = {**data, **collect(ctx)}
        result = mod.render(data, ctx)
        if not isinstance(result, _views.ViewResult):
            raise TypeError(f"render() returned {type(result).__name__}, not ViewResult")
        body = _ui.fragment(_status_banner(ctx.now) if name in _QUOTA_VIEWS else None, result.html)
        out = _ui.group(body, tag="section", data={"view-root": name, "stamp": _views.stamp(body)})
        _publish_pause_targets(result.pause_targets or [], name)
        _publish_item_targets(result.item_targets or [], name)
        return out
    except Exception as exc:  # noqa: BLE001 — one view's fault is that view's error state
        kind = type(exc).__name__
        try:
            sys.stderr.write(f"quota_dashboard: view {name} failed ({kind}: {exc})\n")
        except Exception:  # noqa: BLE001 — an exception whose str() raises still gets its error state
            sys.stderr.write(f"quota_dashboard: view {name} failed ({kind})\n")
        _publish_pause_targets([], name)  # fail-closed: no board, no buttons
        _publish_item_targets([], name)
        return _error_fragment(name, kind)


def _rebuild_targets(view: str) -> None:
    """The guarded POSTs' rebuild-on-miss (INV-1): re-read the stores and render ``view``, which
    publishes the targets it shows — so a restarted server, or a frame older than the last render,
    never answers "not on the board" for a target the operator can see. The fresh read mirrors the
    old page's ``fresh=True`` rebuild; the view's markup is discarded."""
    _drop_repos_cache()
    _render_view(view, triggers=False)


def _error_fragment(name: str, kind: str) -> str:
    """A view's error state, in words — with the stale banner on a quota view (its own guard: a broken
    banner costs the banner, never the error state). If building it raises too, `_last_resort_fragment`."""
    try:
        banner = None
        if name in _QUOTA_VIEWS:
            try:
                banner = _status_banner(time.time())
            except Exception:  # noqa: BLE001
                banner = None
        err = _ui.fragment(
            banner, _ui.region_state("error", _strings.t("view.failed", error=kind), retry=True)
        )
        return _ui.group(err, tag="section", data={"view-root": name, "stamp": _views.stamp(err)})
    except Exception:  # noqa: BLE001 — the error path must answer whatever is broken
        return _last_resort_fragment()


def _last_resort_fragment() -> str:
    """A constant error fragment that cannot raise (`components.last_resort`, bound at import so a
    broken `_ui` cannot reach it): the active catalogue's word through a guarded lookup, else the
    built-in catalogue's."""
    try:
        words = str(_strings.t("state.failed"))
    except Exception:  # noqa: BLE001
        words = _BUILTIN_WORDS.get("state.failed", "")
    return _last_resort(words)


def _known_slugs() -> set[str]:
    """The slugs the board itself last rendered — the ONLY targets the button may name."""
    try:
        payload = json.loads(_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    out: set[str] = set()
    for acct in payload.get("accounts") or []:
        for slug in acct.get("slugs") or []:
            if isinstance(slug, str) and _SLUG_RE.fullmatch(slug):
                out.add(slug)
    return out


def _known_emails() -> set[str]:
    """The account emails the board itself last rendered — the ONLY targets `/park` may name."""
    try:
        payload = json.loads(_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {
        str(a.get("email")).lower()
        for a in payload.get("accounts") or []
        if isinstance(a.get("email"), str) and _EMAIL_RE.fullmatch(str(a.get("email")).lower())
    }


def park_account(email: object, park: object) -> tuple[int, dict]:
    """Relay one park/unpark to the rotation CLI (`--park`/`--unpark`) — same contract as
    :func:`switch_account`: 400 before the CLI for anything the board did not render, 502 with
    the CLI's own stderr on refusal, 200 after a synchronous re-render."""
    if not isinstance(park, bool):
        return 400, {"ok": False, "error": "park must be true or false"}
    if not isinstance(email, str) or email.lower() not in _known_emails():
        return 400, {"ok": False, "error": f"unknown account {email!r} — not on the board"}
    return _run_rotate(["--park" if park else "--unpark", email.lower()])


def switch_account(slug: object) -> tuple[int, dict]:
    """Relay one manual flip to the rotation CLI. Returns (http_status, json_body).

    400 — not a slug the board knows (nothing reaches the CLI); 502 — the CLI refused or
    failed (its stderr is the body, never swallowed); 200 — flipped, and the board has been
    re-rendered synchronously so the reload shows the new pointer, not a floor-cached one.
    """
    if not isinstance(slug, str) or not _SLUG_RE.fullmatch(slug) or slug not in _known_slugs():
        return 400, {"ok": False, "error": f"unknown account {slug!r} — not on the board"}
    return _run_rotate(["--switch", slug])


def _edit_account_map(path: Path, key: str, value: object, what: str) -> tuple[int, dict]:
    """Set (value) or clear (None) ONE account's entry in a {email: number} file the rotation reads
    (caps.json, thresholds.json), then re-render. 502 when the file cannot be read or parsed: rewriting
    it from {} would silently drop every other account's entry. Read-modify-write under a lock file
    beside it (a second click or a second board could otherwise drop an entry — the tick only READS
    these two files), written atomically. Every case-variant of the key is dropped first: the loaders
    lowercase keys and the last duplicate wins, so a hand-written `OB@…` survived a clear of `ob@…`. The caller validated `key` against the board and `value` against the loader."""
    lock_path = path.with_name(path.name + ".lock")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "w") as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                data = {}
            except ValueError as e:
                return 502, {
                    "ok": False,
                    "error": f"{path} is not valid JSON ({e}) — fix it by hand",
                }
            if not isinstance(data, dict):
                return 502, {"ok": False, "error": f"{path} is not a JSON object — fix it by hand"}
            for k in [k for k in data if str(k).lower() == key.lower()]:
                del data[k]
            if value is not None:
                data[key] = value
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            os.replace(tmp, path)
    except OSError as exc:
        return 502, {"ok": False, "error": f"cannot write {path}: {exc}"[:400]}
    shown = "cleared" if value is None else f"{value}%"
    sys.stderr.write(f"quota_dashboard: {what} {key} -> {shown} ({path})\n")
    _rerender()
    return 200, {"ok": True, what: data}


def set_account_cap(email: object, cap: object) -> tuple[int, dict]:
    """ONE account's WEEKLY cap in caps.json (`claude_rotate._caps_file`): int 0..100 (0 parks), or None
    to clear. A bool is a typo, never a cap."""
    if not isinstance(email, str) or email.lower() not in _known_emails():
        return 400, {"ok": False, "error": f"unknown account {email!r} — not on the board"}
    if cap is not None and (
        isinstance(cap, bool) or not isinstance(cap, int) or not 0 <= cap <= 100
    ):
        return 400, {"ok": False, "error": "cap must be a whole number 0..100, or null to clear"}
    return _edit_account_map(_CAPS_FILE, email.lower(), cap, "caps")


def set_account_threshold(email: object, threshold: object) -> tuple[int, dict]:
    """ONE account's ROTATE threshold in thresholds.json (`claude_rotate._thresholds_file`): a number
    50..100, or None for the fleet default. Under 50 is refused — a line that low flips away from a
    half-full account every tick (churn, not a threshold); a bool is a typo."""
    if not isinstance(email, str) or email.lower() not in _known_emails():
        return 400, {"ok": False, "error": f"unknown account {email!r} — not on the board"}
    if threshold is not None and (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not math.isfinite(threshold)
        or not 50 <= threshold <= 100
    ):
        return 400, {
            "ok": False,
            "error": "threshold must be a number 50..100, or null for the default",
        }
    value = (
        None
        if threshold is None
        else (int(threshold) if float(threshold).is_integer() else float(threshold))
    )
    return _edit_account_map(_THRESHOLDS_FILE, email.lower(), value, "thresholds")


def _rerender() -> None:
    """After an account control's write: invalidate the box-budget cache and re-probe NOW."""
    with _budget_lock:  # the budget's own 60 s cache would show the OLD account's headroom
        _budget_cache.update(ts=0.0, data=None)
        _budget_cache["gen"] += 1  # and a probe already in flight may not land its result
    # a fresh reading NOW — bypasses the floor on purpose; at most one probe per click (a budget probe
    # still in flight from before the switch re-kicks for this generation when it lands)
    generate()


def _run_rotate(verb_args: list[str]) -> tuple[int, dict]:
    """Run one validated rotation-CLI verb, then invalidate the banner and re-render the board."""
    try:
        proc = subprocess.run(  # noqa: S603 — fixed argv, validated args, no shell
            [sys.executable, str(ROTATE_CLI), *verb_args],
            capture_output=True,
            text=True,
            timeout=SWITCH_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 502, {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:400]}
    if proc.returncode != 0:
        err = (proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}")[:400]
        return 502, {"ok": False, "error": err}
    _rerender()
    return 200, {"ok": True, "output": proc.stdout.strip()[:400]}


class _Handler(BaseHTTPRequestHandler):
    server_version = "quota-dashboard"
    # Per-connection socket timeout (stdlib knob): a client that promises N body bytes and sends
    # fewer would otherwise park this handler's thread on `rfile.read()` for as long as it
    # stays connected. 15s is generous for a loopback fetch and bounds every read, GET included.
    timeout = float(os.getenv("QUOTA_DASH_SOCKET_TIMEOUT_S", "15"))

    def _json(self, status: int, body: dict, *, close: bool = False) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        if close:  # a refusal that never read the body: the connection cannot carry another request
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        self.wfile.write(raw)

    def _allowed_hosts(self) -> set[str]:
        """The Host values this server answers: the loopback names and the configured QUOTA_DASH_HOST,
        each at the port the server is bound to (a test's port 0 included). INV-6: a DNS-rebinding page
        reaches this socket under ITS name, and that name is not on the list."""
        port = self.server.server_address[1]
        names = {"127.0.0.1", "localhost", "[::1]"}
        conf = _host_literal(HOST)
        if conf not in _WILDCARD_HOSTS:  # a wildcard bind is an address no client names
            names.add(conf)
        allowed = {f"{n}:{port}" for n in names}
        return allowed | names if port == 80 else allowed  # a client omits the default port

    def _cross_site(self) -> bool:
        """Any ``Sec-Fetch-Site`` value — every header, every comma-separated part — is ``cross-site``."""
        values = ",".join(self.headers.get_all("Sec-Fetch-Site") or [])
        return any(v.strip().lower() == "cross-site" for v in values.split(","))

    def _guard(self, method: str) -> bool:
        """Before anything else runs: 421 for a Host outside the allowlist (or more than one Host), 403
        for a POST — or a GET of a view or of `/quota.json`, which can regenerate and republish — that the browser marks
        ``Sec-Fetch-Site: cross-site``; all before the body is read. True: carry on."""
        hosts = self.headers.get_all("Host") or []
        host = hosts[0].strip().lower() if len(hosts) == 1 else ""
        if host not in self._allowed_hosts():
            sys.stderr.write(
                f"quota_dashboard: {method} refused — Host {host[:80]!r} is not this board\n"
            )
            raw = b"misdirected request: this board answers only on its own address\n"
            self.send_response(421)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.close_connection = True
            self.end_headers()
            self.wfile.write(raw)
            return False
        route = self.path.split("?", 1)[0]
        # every request that can re-read the stores or start a regeneration: a POST, a view, quota.json
        guarded = method == "POST" or route.startswith("/v/") or route == "/quota.json"
        if guarded and self._cross_site():
            sys.stderr.write(f"quota_dashboard: {method} {self.path[:80]!r} refused — cross-site\n")
            self._json(403, {"ok": False, "error": "cross-site request refused"}, close=True)
            return False
        return True

    def _static(self, name: str) -> None:
        """``/static/<name>``: only the two files of `_STATIC_TYPES`, revalidated by ETag (no-cache)."""
        ctype = _STATIC_TYPES.get(name)
        if ctype is None:
            self.send_error(404)
            return
        try:
            body = (
                dashboard_ui.STATIC_DIR / name
            ).read_bytes()  # per request: an edit shows at once
        except OSError:
            self.send_error(404)
            return
        etag = f'"{hashlib.sha256(body).hexdigest()[:16]}"'
        sent = {
            t.strip().removeprefix("W/")
            for t in (self.headers.get("If-None-Match") or "").split(",")
        }
        if etag in sent or "*" in sent:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("ETag", etag)
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 (stdlib interface)
        if not self._guard("POST"):
            return
        path = self.path.split("?", 1)[0]
        if path not in ("/switch", "/park", "/cap", "/threshold", "/agent-pause", "/item-verdict"):
            self.send_error(404)
            return
        if not self.headers.get(SWITCH_HEADER):
            # No custom header = not our page's fetch(). A cross-origin form/fetch cannot add
            # one without a preflight, and this server answers no OPTIONS — so this is the
            # whole CSRF story for a loopback-only board.
            sys.stderr.write(f"quota_dashboard: POST {path} refused — no custom header\n")
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
        if path == "/agent-pause":
            b = body if isinstance(body, dict) else {}
            status, out = pause_agent(
                b.get("repo"), b.get("agent"), b.get("action"), b.get("why") or ""
            )
            sys.stderr.write(
                f"quota_dashboard: POST {path} {b.get('repo')!r}/{b.get('agent')!r} {b.get('action')!r}"
                f" -> {status} in {time.time() - t0:.1f}s: {out.get('output') or out.get('error') or ''}\n"
            )
            self._json(status, out)
            return
        if path == "/item-verdict":
            b = body if isinstance(body, dict) else {}
            status, out = item_verdict(
                b.get("repo"),
                b.get("item"),
                b.get("action"),
                b.get("text") or "",
                token=b.get("token"),
            )
            sys.stderr.write(
                f"quota_dashboard: POST {path} {b.get('repo')!r}/{b.get('item')!r} {b.get('action')!r} by operator"
                f" -> {status} in {time.time() - t0:.1f}s: {out.get('output') or out.get('error') or ''}\n"
            )
            self._json(status, out)
            return
        if path == "/threshold":
            if not isinstance(body, dict) or "threshold" not in body:
                self._json(
                    400,
                    {
                        "ok": False,
                        "error": "body needs a threshold (50..100) or null for the default",
                    },
                )
                return
            status, out = set_account_threshold(slug, body.get("threshold"))
        elif path == "/cap":
            if not isinstance(body, dict) or "cap" not in body:
                self._json(
                    400, {"ok": False, "error": "body needs a cap (0..100) or null to clear"}
                )
                return
            status, out = set_account_cap(slug, body.get("cap"))
        elif path == "/park":
            status, out = park_account(slug, body.get("park") if isinstance(body, dict) else None)
        else:
            status, out = switch_account(slug)
        sys.stderr.write(
            f"quota_dashboard: POST {path} {slug!r} -> {status} in {time.time() - t0:.1f}s:"
            f" {out.get('output') or out.get('error') or ''}\n"
        )
        self._json(status, out)

    def do_GET(self) -> None:  # noqa: N802 (stdlib interface)
        if not self._guard("GET"):
            return
        path = self.path.split("?", 1)[0]
        if path.startswith("/static/"):
            self._static(path[len("/static/") :])
            return
        if path.startswith("/v/"):
            if path[len("/v/") :] not in _views.VIEWS:
                self.send_error(404)
                return
            body, ctype = (
                _render_view(path[len("/v/") :]).encode("utf-8"),
                "text/html; charset=utf-8",
            )
        elif path in ("/", "/index.html"):
            body, ctype = _shell_page().encode("utf-8"), "text/html; charset=utf-8"
        elif path == "/quota.json":
            body, ctype = _quota_json(), "application/json"
        elif path == "/health":
            body, ctype = b"ok", "text/plain"
        elif path == "/repos.html":
            # the old Repos page: a bookmark lands on the Work view for the 14-day window, then 404
            if not _legacy_window_open():
                self.send_error(404)
                return
            self.send_response(303)
            self.send_header("Location", "/#work")
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        elif path == "/external-services.html":
            # the old static page: a bookmark lands on the inventory section, on no removal date (D8)
            self.send_response(303)
            self.send_header("Location", "/#services")
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
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

    # a wildcard bind answers on loopback, and only there under a Host the allowlist admits — sending
    # `Host: 0.0.0.0:<port>` would read a healthy server as wedged and SIGTERM it every cron tick
    target = "127.0.0.1" if _host_literal(HOST) in _WILDCARD_HOSTS else HOST
    try:
        c = http.client.HTTPConnection(
            target, PORT, timeout=float(os.getenv("QUOTA_DASH_ENSURE_TIMEOUT_S", "5"))
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
    g.add_argument(
        "--once",
        action="store_true",
        help="probe the fleet once, write quota.json, print its path and exit (the page itself is served live)",
    )
    g.add_argument("--serve", action="store_true", help="run the localhost server (foreground)")
    g.add_argument("--ensure", action="store_true", help="start the server if it is not running")
    args = ap.parse_args(argv)
    if args.once:
        generate()
        sys.stdout.write(f"{_JSON}\n")
        return 0
    if args.ensure:
        return ensure()
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
