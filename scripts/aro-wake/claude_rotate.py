#!/usr/bin/env python3
# AFTER-EDIT: scripts/sysadmin/bot.py, scripts/aro-wake/main.py, scripts/sysadmin/claude_rotate.py, scripts/aro-wake/claude_rotate.py
# NB: this file is vendored BYTE-IDENTICAL into scripts/sysadmin/ and scripts/aro-wake/
# (separate rsync trees + venvs on each host — no shared import). Keep the two copies identical.
"""Claude Code CLI usage-limit detection + bounded account rotation.

Self-contained, stdlib-only. Vendored BYTE-IDENTICAL into both ``scripts/sysadmin/``
and ``scripts/aro-wake/`` (separate rsync trees + separate venvs on each host — no
shared import path exists), so this file must never import a sibling.

When a ``claude -p`` call reports a usage/quota limit OR a ``401`` auth failure, rotate the
*active* account to another snapshot and retry (bounded by the account count). A usage-limit
rotates silently (routine quota exhaustion); a ``401`` (the active account's login token is
dead) ALSO fires a best-effort Telegram alert — configured via ``TELEGRAM_BOT_TOKEN`` /
``TELEGRAM_OWNER_ID`` (env, or parsed from ``/opt/fabrik/.env.sysadmin``) — so the operator
knows an account's credentials died. Rotating to a valid standby recovers a 401 the account's
own token-refresh could not; if every account is dead the alert says so and the call gives up.

Security (``core/35-security-auth``): ``~/.claude/*.credentials.json`` are ``chmod 600``
and are **never logged, printed, or returned**. Rotation swaps whole files
(``os.replace`` — atomic) between the ``manager-accounts/<org>/.credentials.json``
snapshots and the active ``~/.claude/.credentials.json``. To tell accounts apart / detect a
usable account it reads the non-secret ``organizationUuid`` AND compares OAuth access tokens
**in memory** — newer Claude Code creds keep the org in ``~/.claude.json`` so
``.credentials.json`` has *no* ``organizationUuid``, and account identity/validity must not
depend on it. A token is never logged, printed, or returned to a caller.
"""

from __future__ import annotations

import fcntl
import json
import math
import os
import re
import select
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

CLAUDE_DIR = Path.home() / ".claude"
ACTIVE_CREDS = CLAUDE_DIR / ".credentials.json"
ACCOUNTS_DIR = CLAUDE_DIR / "manager-accounts"
# MCP roster + per-project trust + onboarding state — NOT credentials (those live in
# .credentials.json). It is the one file a new fleet dir is seeded from, so a fresh dir needs no
# re-onboarding and no re-trusting; the operator's single /login replaces its OAuth section.
USER_CLAUDE_JSON = Path.home() / ".claude.json"
_CRED_MARGIN_S = 300  # never hand over a token that dies mid-switch
BACKUP_CREDS = CLAUDE_DIR / ".credentials.json.prev"  # single rolling backup of outgoing active
ROTATE_LOCK = CLAUDE_DIR / ".claude-rotate.lock"
# Dir-NAME of the currently-active snapshot, written on every install. Org-independent identity:
# the only reliable "which account is active" signal for newer creds that carry no organizationUuid.
ACTIVE_MARKER = CLAUDE_DIR / ".active-account"
# 401 Telegram alerts are DEBOUNCED to once per this window PER HOST (shared across all callers on
# the host) — a persistently-dead account must not flood Telegram from every 15-min cron × N hosts.
ALERT_STATE = CLAUDE_DIR / ".last-401-alert"
_ALERT_DEBOUNCE_S = 12 * 3600
# A ledger timestamp may sit this far ahead of "now" before it is treated as clock skew rather than
# a real switch (NTP correction, and WSL suspend/resume, move this box's clock in both directions).
_CLOCK_SKEW_TOLERANCE_S = 60.0

# The fleet-wall advisory latch fires once per wall episode, but re-arms after this long so a
# sustained total exhaustion re-reminds the operator (the "week without a word" re-arm the old
# per-account advisory carried; without it a presence-only latch silences forever if the walled
# active account never dips below threshold across a reset).
_FLEET_WALL_REARM_S = 7 * 86400.0

# Quota / usage-limit signal (case-insensitive). PURE alternation — no literal spaces
# around '|'. Grounded verbatim (claude-auto-retry README + Anthropic errors docs,
# 2026-07-07): weekly / session / Opus / N-hour / "out of extra usage" variants.
# NB: the "hit your … limit" branch omits the leading "you've" on purpose — the real
# render's apostrophe is sometimes typographic (U+2019), so anchoring on "hit your"
# matches "You've hit your weekly limit" regardless of the quote character.
_USAGE_LIMIT_RE = re.compile(
    r"usage limit reached"
    r"|hit your (?:weekly|session|opus|[0-9]+-hour) limit"
    r"|[0-9]+-hour limit reached"
    r"|out of extra usage"
    r"|limit\s*·\s*resets",
    re.IGNORECASE,
)


def is_usage_limit(text: str) -> bool:
    """True iff *text* carries a Claude usage/quota-limit signal (→ rotate + retry)."""
    return bool(text) and bool(_USAGE_LIMIT_RE.search(text))


def is_auth_401(text: str) -> bool:
    """True iff *text* is a dead-creds auth failure (→ rotate to a standby + alert).

    Two renders qualify:
    (a) a standalone ``401`` alongside auth wording — neither a bare ``line 401``
        nor a ``401`` buried inside a larger number (``14012``) matches;
    (b) the CLI's expired-OAuth render ("OAuth session expired and could not be
        refreshed") — it carries NO "401", which left the keepalive stuck on FAIL
        with no rotation (live-hit 2026-08-03: a re-login on the manager box
        revoked the fleet's copied refresh token mid-window).
    Both mean the ACTIVE account's creds are dead; rotating to a valid standby
    recovers either.
    """
    low = text.lower()
    if "oauth session expired" in low:
        return True
    if not re.search(r"\b401\b", text):
        return False
    return "authentication" in low or "credential" in low


def _read_org(creds_path: Path) -> str | None:
    """Return the non-secret ``organizationUuid`` from a creds file, or None. Never emits tokens."""
    try:
        with open(creds_path) as fh:
            return json.load(fh).get("organizationUuid")
    except (OSError, ValueError):
        return None


def _access_token_from(data: str | bytes) -> str | None:
    """The OAuth access token inside a creds JSON blob (``claudeAiOauth.accessToken``), or None
    if it doesn't parse / has no token. Used ONLY to detect a usable account and to tell two
    accounts apart — the token is compared in memory and is NEVER logged, printed, or returned
    to a CLI caller. This — not ``organizationUuid`` (absent in newer creds) — is the identity
    and validity signal."""
    try:
        oauth = json.loads(data).get("claudeAiOauth")
    except (ValueError, TypeError, AttributeError):
        return None
    if not isinstance(oauth, dict):
        return None
    tok = oauth.get("accessToken")
    return tok if isinstance(tok, str) and tok else None


def _read_access_token(creds_path: Path) -> str | None:
    """``_access_token_from`` for a file on disk (or None if unreadable). Never emits the token."""
    try:
        return _access_token_from(Path(creds_path).read_bytes())
    except OSError:
        return None


def _with_claude_on_path(env: dict) -> dict:
    """Ensure the ``claude`` CLI is resolvable in *env* for a subprocess spawn.

    The CLI installs to ``~/.local/bin`` (a symlink to the versioned binary), but a
    cron job runs with ``PATH=/usr/bin:/bin`` — which excludes it. A bare
    ``["claude", ...]`` spawn under cron then raises ``FileNotFoundError`` and the
    ping fails silently: idle-account readings never refresh and the weekly
    keepalive never fires (observed 2026-08-22 — the */5 tick pinged, every idle
    cred mtime stayed frozen, and the dashboard caches aged past 85h). Prepend the
    user-local bin dir so the tick/keepalive resolve ``claude`` under cron exactly
    as a login shell does. Mutates and returns *env*; idempotent — a no-op when the
    dir is already on PATH (interactive / systemd runs, or a crontab ``PATH=`` line)."""
    local_bin = str(Path.home() / ".local" / "bin")
    parts = env["PATH"].split(os.pathsep) if env.get("PATH") else []
    if local_bin not in parts:
        env["PATH"] = os.pathsep.join([local_bin, *parts]) if parts else local_bin
    return env


def _list_accounts() -> list[Path]:
    """Manager-account snapshot dirs that hold a ``.credentials.json`` (sorted, stable order).
    Fail-soft: an unreadable/inaccessible ``manager-accounts`` (a rare permission mishap) yields no
    snapshots rather than raising — this runs inside ``run_claude``/``_active_account`` on every
    call, and an escaping OSError would be mislabeled by ``main()`` as an exec failure (126) and
    discard a perfectly good claude result."""
    try:
        if not ACCOUNTS_DIR.is_dir():
            return []
        return sorted(
            d for d in ACCOUNTS_DIR.iterdir() if d.is_dir() and (d / ".credentials.json").is_file()
        )
    except OSError:
        # Covers the initial is_dir() stat AND iterdir + per-entry is_dir/is_file: an unsearchable
        # dir/parent or a bad symlink (EACCES/ELOOP, which pathlib re-raises) yields no snapshots
        # rather than an OSError that main() would mislabel 126 and discard a good claude result.
        return []


def _active_account() -> Path | None:
    """The snapshot dir that is currently active, or None — a PURE read (no side effects, so no
    lock-free marker write can race the under-lock one and leave a stale marker). Identity resolves
    by, in order: (1) an access-token match against the LIVE active creds — the freshest signal, so
    it beats a marker left stale by an external ``claude auth login``/switch while the new token is
    fresh; (2) the ``.active-account`` marker — written under the rotation lock on every install
    (``_activate_snapshot``), authoritative for any account THIS tool activated and durable across
    the in-place token refresh that drifts the live token off the frozen snapshot; (3) an
    ``organizationUuid`` match — old-format creds (org is stable across token refresh), which is how
    a never-rotated old-format active (the fleet's bootstrap mob@) is identified with no marker.
    Never emits token bytes.

    Order matters: both signals read from the LIVE active creds (token, org) come BEFORE the
    persisted marker, so a marker left stale by an out-of-band ``claude auth login`` can never
    shadow the true identity of an old-format active (its org is read live and is authoritative).
    The marker is the last resort — used only for a newer no-org account this tool installed, whose
    live token has since drifted off the frozen snapshot."""
    accounts = _list_accounts()
    # (1) access-token match — the freshest live signal.
    active_tok = _read_access_token(ACTIVE_CREDS)
    if active_tok is not None:
        hit = next(
            (a for a in accounts if _read_access_token(a / ".credentials.json") == active_tok), None
        )
        if hit is not None:
            return hit
    # (2) organizationUuid match — read LIVE (authoritative, never stale); org never drifts across
    #     a token refresh. Trusted ONLY when it identifies EXACTLY ONE snapshot: if two snapshots
    #     share an org (two accounts in one Team/Enterprise org, or a duplicated capture) the match
    #     is ambiguous, so fall through to the marker rather than guess the sorted-first snapshot.
    active_org = _read_org(ACTIVE_CREDS)
    if active_org is not None:
        org_hits = [a for a in accounts if _read_org(a / ".credentials.json") == active_org]
        if len(org_hits) == 1:
            return org_hits[0]
    # (3) marker — last resort for a newer no-org account THIS tool installed (set under the lock
    #     in _activate_snapshot) once its live token has drifted off the frozen snapshot.
    try:
        marked = ACTIVE_MARKER.read_text().strip()
    except (OSError, ValueError):
        # ValueError covers UnicodeDecodeError — a truncated/corrupt or non-UTF-8 .active-account
        # (e.g. LANG=C reading a non-ASCII name, or external corruption). _active_account runs on
        # EVERY run_claude call, so an undecodable marker must degrade to "no marker", never raise
        # and crash the whole claude path. (Matches the _telegram_config guard.)
        marked = ""
    if marked:
        hit = next((a for a in accounts if a.name == marked), None)
        if hit is not None:
            return hit
    return None


def _secure_write(dst: Path, data: bytes) -> None:
    """Create *dst* FRESH at mode 0600 and write *data* — no world-readable window and no
    symlink follow. Any pre-existing file/symlink at *dst* is removed first, then created
    with ``O_CREAT|O_EXCL|O_NOFOLLOW`` so an attacker-planted symlink at the predictable
    path cannot redirect the credential bytes (the open fails closed instead). Unlike
    ``shutil.copy2`` (which opens the dest at umask 0644 and only chmods *after* writing),
    the bytes are never on disk group/world-readable, even briefly.
    """
    try:
        os.unlink(dst)  # clear a stale file OR an attacker symlink at the fixed path
    except FileNotFoundError:
        pass
    fd = os.open(str(dst), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        # os.write (raw write(2)) may short-write — loop until ALL bytes land, else a
        # truncated creds blob could be atomically installed and brick the active account.
        view = memoryview(data)
        written = 0
        while written < len(view):
            written += os.write(fd, view[written:])
        # fsync the FILE DATA before the caller's os.replace so a power loss can't leave the
        # active inode naming unwritten blocks (a zero-length/garbage creds file). The caller
        # (_activate_snapshot) additionally fsyncs the CONTAINING DIRECTORY after os.replace so
        # the rename itself is durable — together the swap is genuinely power-loss-safe.
        os.fsync(fd)
    finally:
        os.close(fd)


def _stale_snapshot_reason(blob: bytes, now: float | None = None) -> str | None:
    """Why this snapshot must NOT be installed as the active account, or None if it is safe.

    Token PRESENCE is not usability. Refresh tokens here are SINGLE-USE and four boxes share
    three accounts, so a snapshot whose access token has already expired can only be revived by
    a refresh whose token another box may have already consumed — installing it lands the
    operator on "OAuth session expired and could not be refreshed" and a re-login prompt.

    LIVE INCIDENT 2026-08-10 14:37: mob@ hit its weekly wall, the picker ranked can@ first
    (never walled), and can@'s snapshot was a month old. The switch installed a dead credential
    and logged the operator out mid-session. A rotation target must be usable WITHOUT a refresh.

    Escape hatch: CLAUDE_ROTATE_ALLOW_STALE=1 (an operator who knows the snapshot is fine).
    Never emits token bytes.
    """
    if os.getenv("CLAUDE_ROTATE_ALLOW_STALE") == "1":
        return None
    now = now if now is not None else time.time()
    try:
        oauth = json.loads(blob.decode("utf-8")).get("claudeAiOauth") or {}
        if not isinstance(oauth, dict):
            return "credentials are malformed (claudeAiOauth is not an object)"
    except (ValueError, AttributeError, TypeError):
        # UnicodeDecodeError subclasses ValueError. AttributeError/TypeError cover a payload that
        # is valid JSON but not the expected shape (`123`, `[]`, or a string `claudeAiOauth`) —
        # today `_access_token_from` pre-screens those, but this function is module-level and
        # documented as the authoritative guard, so the next caller without that pre-screen must
        # not crash the rotation path (review finding).
        return None

    def _left(v):
        if not isinstance(v, (int, float)):
            return None
        return (v / 1000 if v > 1e11 else v) - now

    if not oauth.get("refreshToken"):
        # No refresh token at all: the moment the access token lapses there is no way back, and
        # the picker already refused this shape. Two layers disagreeing about one credential is
        # the class that caused the incident (review finding F6).
        return "credentials carry no refresh token — nothing to renew with"
    refresh_left = _left(oauth.get("refreshTokenExpiresAt"))
    if refresh_left is not None and refresh_left <= 0:
        return f"refresh token expired {abs(refresh_left) / 3600:.0f}h ago"
    # NOT a disqualifier: an expired ACCESS token is the NORMAL state of a standby. Only the
    # active account self-refreshes, so a standby's `expiresAt` is frozen at capture and goes stale
    # within ~8-12h — while a weekly wall arrives ~2.x days later. Disqualifying on it meant that
    # by the time rotation was needed, EVERY standby looked dead and rotation was structurally
    # impossible (review finding, and the mirror failure of the bug this guard exists to fix).
    # The live incident is caught by the refresh-token clause above on its own: can@'s month-old
    # snapshot had an EXPIRED refresh token, which is what "could not be refreshed" means.
    # A live access token is a PREFERENCE, applied by ranking in the picker — never a filter.
    access_left = _left(oauth.get("expiresAt"))
    if access_left is None:
        # FAIL CLOSED. A missing expiry field does not mean "still valid" — it means we CANNOT
        # PROVE it authenticates, and an unprovable credential is exactly what logged the operator
        # out. This also removes a cross-layer divergence: the picker (claude-quota.py
        # credentials_usable) already treats a missing field as unusable, and two layers
        # disagreeing about the same credential is the defect class that caused the incident
        # (found independently by review; carried as a self-finding first).
        # Cost asymmetry decides the direction: refusing costs a WAIT for the reset clock;
        # allowing costs a logged-out operator at the keyboard. CLAUDE_ROTATE_ALLOW_STALE=1
        # overrides for a legacy snapshot an operator knows is good.
        return "credentials carry no expiry metadata — cannot prove they still authenticate"
    return None


def _activate_snapshot(
    target: Path | None = None,
    selector: Callable[[], Path | None] | None = None,
) -> str | None:
    """Atomically install a snapshot as the active creds. Serialized via flock so ``bot.py``,
    ``aro-wake`` and a manual ``--switch`` (independent processes, same host) can't race the
    active file. Pass a fixed *target* (manual switch) OR a *selector* callback that picks the
    target **while the lock is held** — the selector runs under the lock so it sees the live
    active account and a concurrent rotation can't make two processes pick the same target,
    clobber the ``.prev`` backup, or report a phantom rotation. Backs the outgoing active up
    to ``.credentials.json.prev`` first (fresh 0600, no symlink follow), then ``os.replace``
    (atomic; ``.tmp`` is in the same dir → same filesystem). Returns the installed account's
    dir name, or None on no target / ANY filesystem error — installing a snapshot is *optional*
    recovery, so a transient FS/symlink error must fail SOFT (never crash the caller). The only
    mutation of the live active file is the final atomic replace, so a failure before it leaves
    the active creds intact. Never logs token bytes.
    """
    try:
        lock_fd = os.open(str(ROTATE_LOCK), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    except OSError:
        return None  # fail-soft: can't take the lock → skip
    tmp = ACTIVE_CREDS.with_name(ACTIVE_CREDS.name + ".tmp")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        if selector is not None:  # pick the target UNDER the lock (race-safe)
            target = selector()
        if target is None:
            return None
        # Read both payloads before mutating anything; the live file is only touched by
        # the atomic os.replace at the end.
        active_bytes = ACTIVE_CREDS.read_bytes() if ACTIVE_CREDS.exists() else None
        target_bytes = (target / ".credentials.json").read_bytes()
        # Never install unreadable creds as the active account. An empty/0-byte/non-JSON snapshot,
        # or one with no OAuth access token (interrupted capture, partial fleet-sync, or a target
        # corrupted AFTER the selector read it — a TOCTOU the lock can't cover for an external
        # writer) would otherwise be atomically swapped in and BRICK auth. Validity is the presence
        # of a usable TOKEN — NOT organizationUuid, which newer creds legitimately omit (keying on
        # org here would wrongly reject a valid new-format account). Refuse fail-soft otherwise,
        # leaving BOTH active and .prev intact. Guards the EXPLICIT --switch/--next path too.
        # Diagnostic names the dir only, never token bytes.
        if _access_token_from(target_bytes) is None:
            sys.stderr.write(
                f"refusing to activate {target.name}: unreadable/corrupt credentials\n"
            )
            return None
        stale = _stale_snapshot_reason(target_bytes)
        if stale is not None:
            # Fail-soft and STAY PUT: a walled-but-authenticated session is recoverable by
            # waiting for the reset clock; a logged-out one needs the operator at the keyboard.
            sys.stderr.write(
                f"refusing to activate {target.name}: {stale}. "
                "Re-authenticate that account, or set CLAUDE_ROTATE_ALLOW_STALE=1 to override.\n"
            )
            return None
        # Single rolling backup of the outgoing active (satisfies the backup-before-swap rule).
        if active_bytes is not None:
            _secure_write(BACKUP_CREDS, active_bytes)
        _secure_write(tmp, target_bytes)
        os.replace(str(tmp), str(ACTIVE_CREDS))  # atomic swap (0600 mode carried from tmp)
        # Record which account is now active BY DIR NAME (org-independent) so the next rotation can
        # identify the active account even when its creds carry no organizationUuid. Best-effort —
        # a marker-write failure must not fail an already-completed swap (token-match still recovers).
        try:
            _secure_write(ACTIVE_MARKER, target.name.encode())
            # closer #5: EVERY switch writer starts the dwell clock — a manual --switch/
            # --next/aro-wake rotation invisible to the ledger let the tick re-rotate
            # minutes later, defeating the hysteresis the plan promises
            try:
                _ledger_append(
                    {"event": "switch", "ts": _now(), "to": target.name, "via": "activate"}
                )
            except Exception:  # noqa: BLE001 — audit only, never a switch-blocker
                pass
        except OSError:
            pass
        # fsync the CONTAINING DIRECTORY so the rename (directory-entry update) is also
        # crash-durable, not just the file data (_secure_write already fsync'd that). Together
        # they make the swap genuinely power-loss-safe. Best-effort — a fsync failure here does
        # not undo a successful replace, so it must not fail the rotation.
        try:
            dir_fd = os.open(str(ACTIVE_CREDS.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
        return target.name
    except OSError:
        # fail-soft on any FS error — active creds are left untouched. Clean up a leftover
        # tmp creds copy (e.g. a failure at os.replace) so no stray token file lingers.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return None
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)


# Everything the rotate STATE DIR can throw at a caller: _rotate_state_dir() mkdirs, so it raises
# OSError, and Path.home() raises RuntimeError when HOME is unset with no passwd entry (a real
# systemd/container config); a corrupt file read adds UnicodeDecodeError (a ValueError). Every
# best-effort reader of that dir swallows exactly this set — widen _STATE_DIR_ERRORS (one name, all
# sites) if _rotate_state_dir ever grows a new failure mode, e.g. a KeyError from an env lookup.
_STATE_DIR_ERRORS = (OSError, ValueError, RuntimeError)

# The two pause REASONS, as constants: they are compared at several call sites (the 401 alert leg,
# --next, --status, the tick), and a bare-string rename in one place fails every comparison
# silently. The guard against that is the TESTS — t15k/t15m/t15n assert the operator-facing strings
# and all three tri-state branches — NOT the type checker: the repo gate does not type-check
# scripts/ (pyproject excludes it), so the Literal below only bites in a standalone mypy run.
_PAUSE_MARKER: Final[Literal["marker"]] = "marker"  # the operator's --pause-switch marker is set
_PAUSE_ERROR: Final[Literal["error"]] = "error"  # the pause state is unreadable → fail closed
# Third withheld-reason value (F-P10): the legacy installer is STRUCTURALLY retired because the
# fleet exists — not operator state, so unlike _PAUSE_MARKER it never silences the 401 all-dead
# alert (a straggler ~/.claude-bound caller on a dead chain will NOT self-heal; the operator
# must hear about it) and _cmd_next skips the misleading "need ≥2 snapshots" hint.
_WITHHELD_FLEET: Final = "fleet-mode"

# ``withheld_reason`` — set by EVERY call into _rotate_active_account: the reason above iff that
# call was refused by the pause gate (nothing installed, nothing even attempted), None on every
# other outcome. It is the gate's own REPORT to `run_claude`/`_cmd_next`, which must never re-derive
# it by re-reading the marker: a re-read is wrong whenever the function was not called at all (a
# 1-snapshot host, or _list_accounts fail-softing to [] → max_rotations == 0), where it silenced a
# TRUE "all credentials are dead" alert, and it races the marker's removal (TOCTOU) at the resume
# moment. THREAD-LOCAL, not a module global: the aro-wake twin calls run_claude from
# ``asyncio.to_thread`` AND from a fire-and-forget task with no lock, so two callers are genuinely
# in the gate at once — with one shared slot, a paused caller's verdict is read by an exhausted
# sibling and silences its alert. Readers use ``getattr(_TLS, "withheld_reason", None)`` — a thread
# that never rotated has no attribute at all.
_TLS = threading.local()


def _pause_state() -> Literal["marker", "error"] | None:
    """Tri-state pause probe — the SINGLE surface every caller uses. Returns ``None`` (not paused),
    ``_PAUSE_MARKER`` (the operator's ``--pause-switch`` marker is present), or ``_PAUSE_ERROR``
    (the pause state could not be READ — an unreachable/unwritable state dir, or ``Path.home()``
    raising RuntimeError when HOME is unset with no passwd entry, a real systemd/container config).

    It swallows exactly ``_STATE_DIR_ERRORS`` — everything :func:`_rotate_state_dir` and
    ``Path.is_file`` can raise today. That set is the contract: an escape mid-``claude``-call is
    mislabeled by ``main()`` as an exec failure (126) and discards a good result, so a future edit
    that gives ``_rotate_state_dir`` a new failure mode must widen ``_STATE_DIR_ERRORS`` (the one
    name every state-dir reader shares).

    **``_PAUSE_ERROR`` fails CLOSED — no pair is installed** — because this function cannot tell
    "no marker" from "cannot look", and T01's invariant is that ZERO processes may swap credentials
    while the operator holds the marker. Refusing costs a wait ``--resume-switch`` ends; permitting
    costs exactly the box-wide swap the marker exists to forbid. But it is NOT the marker: callers
    must keep their alerting ARMED for it (the operator asked for silence when they set the marker
    — never when a state dir broke), which is why this is tri-state and not a bool."""
    try:
        return _PAUSE_MARKER if _switch_paused() else None
    except _STATE_DIR_ERRORS:
        return _PAUSE_ERROR


def _rotate_active_account(avoid: frozenset[str] = frozenset()) -> str | None:
    """Rotate the active account to another snapshot: pick the first snapshot that is NOT in
    *avoid*, is a USABLE account (has an OAuth token — so an empty/0-byte/tokenless snapshot is
    skipped rather than installed, which would brick auth), and is a DIFFERENT account than the
    live active one. "Different" is judged by dir NAME (via the marker/token/org identity in
    ``_active_account``) AND by token bytes — NOT by ``organizationUuid``, which newer creds omit
    (keying on org made a valid no-org account invisible → rotation found no target). With 3+
    accounts, successive calls with a growing *avoid* set walk each other account exactly once.
    Selection runs **inside the install lock** (via the selector), so two concurrent rotations
    can't both target the same account, over-write the ``.prev`` backup, or report a phantom
    no-op rotation. Returns the new account's dir name, or None when there is no eligible target
    or the install fails (fail-soft). Never emits token bytes.

    **Pause gate (the M-pre invariant, 2026-08-15):** while the operator's ``switch-paused``
    marker exists (``--pause-switch``), NOTHING installs a pair — this is the single choke point
    behind ``run_claude``'s usage-limit/401 retry and ``--next``, so gating it here disarms every
    automated credential swap ON THIS BOX. It does NOT reach the hourly fleet-sync
    (``scripts/sysadmin/sync-claude-accounts-to-fleet.sh``), which pushes the live credentials to
    the 3 VPSes with no pause awareness — that push's pause-awareness belongs to the VPS follow-up
    spec, not to this gate. The refusal is LOUD on **stderr** (the CLI passthrough
    mirrors stdout back to its callers, so a stdout line would corrupt their payload) and returns
    None. ``--switch <name>`` does not route through here and stays usable as the manual lever.
    A refusal is REPORTED to callers via ``_TLS.withheld_reason`` (set on every call), so they can
    tell "withheld by the marker" from "withheld fail-closed" from "withheld structurally —
    fleet mode" (``_WITHHELD_FLEET``) from "no target existed" without re-reading the marker
    themselves.

    **Fleet guard (F-P10, first-statement-class):** once ≥1 fleet dir exists, rotation IS the
    pointer flip and NOTHING may install a credential file into ``~/.claude`` — this refusal is
    checked BEFORE the pause gate, because it is structure, not operator state: removing the
    pause marker (the rollout does) must never re-arm the legacy file-swap for a straggler
    ``~/.claude``-bound caller (keepalive shim, sysadmin bot) hitting a usage-limit/401 — the
    chain-destruction class. The 401 all-dead alert stays ARMED for it (unlike the marker):
    the shared dir's dead chain will not self-heal, and the fix — migrate the caller to a
    fleet dir, or the M-sweep — needs the operator. The shared dir's chain itself is left
    untouched for the M-sweep.
    """
    _TLS.withheld_reason = None
    if _fleet_dirs():
        _TLS.withheld_reason = _WITHHELD_FLEET
        sys.stderr.write(
            "claude_rotate: fleet mode is live — rotation is the pointer flip; nothing "
            "installs into ~/.claude (the shared dir's chain is left for the M-sweep). "
            "Migrate this caller to a fleet dir (CLAUDE_CONFIG_DIR), or use --switch <slug>.\n"
        )
        return None
    paused = _pause_state()
    if paused is not None:
        _TLS.withheld_reason = paused
        if paused == _PAUSE_MARKER:
            sys.stderr.write(
                "claude_rotate: rotation PAUSED (switch-paused marker) — no account installed "
                "(override: --resume-switch)\n"
            )
        else:
            sys.stderr.write(
                "claude_rotate: pause-state unreadable — failing CLOSED, no account installed "
                "(fix the rotate state dir; --resume-switch clears a real marker)\n"
            )
        return None
    accounts = _list_accounts()
    if len(accounts) < 2:
        return None

    def _select() -> Path | None:
        active = _active_account()  # re-resolve the live active account — under the lock
        active_name = active.name if active is not None else None
        active_tok = _read_access_token(ACTIVE_CREDS)
        for acc in accounts:
            if acc.name in avoid:
                continue
            tok = _read_access_token(acc / ".credentials.json")
            if tok is None:  # corrupt / empty / tokenless — never install
                continue
            # …and skip one the installer would REFUSE, so a healthy account later in the sort is
            # still reached. Without this the first stale candidate ended rotation entirely: the
            # installer refused it, `run_claude` saw None and broke out, and a fresh standby one
            # index later was never tried (review finding — the mirror of the logout bug: pre-fix
            # it rotated to a dead account, post-fix it rotated NOWHERE). Matters most on the VPS
            # fleet, where this is the ONLY rotation path (no claude-quota.py picker there).
            try:
                if _stale_snapshot_reason((acc / ".credentials.json").read_bytes()) is not None:
                    continue
            except OSError:
                continue
            if acc.name == active_name:  # the account we're rotating away FROM
                continue
            if active_tok is not None and tok == active_tok:  # same account under a different dir
                continue
            return acc
        return None

    return _activate_snapshot(selector=_select)


def _read_piped_stdin(max_wait_s: float = 2.0) -> str | None:
    """Read piped stdin ONCE (so a rotation retry can be re-supplied the same context).
    Returns None for a tty, an absent/closed stdin, or a fd that never has data ready. The
    read is BOUNDED by *max_wait_s* total — a fd that yields partial data but never EOFs
    (e.g. a manual ``ssh host 'sudo bash …'`` without ``-t``) returns what arrived rather
    than blocking forever. The real callers feed an eagerly-materialized, EOF-terminated fd
    (heredoc ``<<<``, a file ``<``, or /dev/null), so they read in full in milliseconds.
    """
    try:
        stdin = sys.stdin
        if stdin is None or stdin.isatty():
            return None
        fd = stdin.fileno()
    except (AttributeError, OSError, ValueError):
        return None
    deadline = time.monotonic() + max_wait_s
    chunks: list[bytes] = []
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break  # bounded — never block past the budget
            if not select.select([fd], [], [], min(remaining, 0.2))[0]:
                if chunks:
                    continue  # partial data but a producer gap → keep polling to the deadline
                return None  # nothing ever ready → not a piped caller
            block = os.read(fd, 65536)
            if not block:
                break  # EOF
            chunks.append(block)
    except (OSError, ValueError):
        pass
    if not chunks:
        return None
    return b"".join(chunks).decode("utf-8", errors="replace")


def _hostname() -> str:
    """This host's name for an alert label (non-secret). '?' if unavailable."""
    try:
        return os.uname().nodename
    except (AttributeError, OSError):
        return "?"


def _should_alert_401() -> bool:
    """True at most once per ``_ALERT_DEBOUNCE_S`` per host — rate-limits the 401 Telegram alert so a
    persistently-dead account can't flood the operator (every 15-min cron + hourly keepalive + bot,
    ×N hosts, each hitting the same 401, otherwise sends hundreds/day). The window is shared across
    all callers on the host via a single state file. Fail-OPEN on any error (a rare alert beats a
    swallowed one); records the send time so the next caller within the window stays quiet."""
    try:
        last = float(ALERT_STATE.read_text().strip())
    except (OSError, ValueError):
        last = 0.0
    if time.time() - last < _ALERT_DEBOUNCE_S:
        return False
    try:
        ALERT_STATE.write_text(str(time.time()))
    except OSError:
        pass
    return True


ENV_SYSADMIN = Path(
    "/opt/fabrik/.env.sysadmin"
)  # fleet sysadmin env (ozgur-readable) — token fallback


def _telegram_config() -> tuple[str, str] | None:
    """``(bot_token, owner_chat_id)`` for the 401 alert — from the environment, else parsed from
    ``/opt/fabrik/.env.sysadmin`` (the fleet's sysadmin env; ``claude-run.sh`` runs us under
    ``sudo -u ozgur`` which resets the environment, so the file is the real source on the fleet).
    None if unconfigured (e.g. the WSL dev box) so the alert simply no-ops. The token is a secret:
    it is used only in the request URL, never logged."""
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_OWNER_ID")
    if not (tok and chat):
        try:
            for raw in ENV_SYSADMIN.read_text().splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                val = val.strip().strip('"').strip("'")
                if key.strip() == "TELEGRAM_BOT_TOKEN" and not tok:
                    tok = val
                elif key.strip() == "TELEGRAM_OWNER_ID" and not chat:
                    chat = val
        except (OSError, ValueError):
            # ValueError covers UnicodeDecodeError from read_text() on a non-UTF-8 .env.sysadmin
            # (corrupted write / a pasted smart-quote) — a config read must never raise into the
            # 401 alert path and abort rotation; an undecodable file simply yields no config.
            pass
    return (tok, chat) if tok and chat else None


def _notify_telegram(text: str) -> bool:
    """Best-effort Telegram alert via the Bot API (stdlib urllib). FAIL-SOFT: a missing config or
    any network/HTTP error is swallowed (returns False) — an alert must NEVER break rotation. The
    bot token appears only in the request URL; neither it nor the response body is ever logged."""
    try:
        # The config read is INSIDE the try too (belt-and-suspenders): _telegram_config already
        # guards its file read, but nothing that runs before the network call may escape this path.
        cfg = _telegram_config()
        if cfg is None:
            sys.stderr.write(
                "claude_rotate: 401 alert skipped — no TELEGRAM_BOT_TOKEN/OWNER_ID configured\n"
            )
            return False
        tok, chat = cfg
        data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{tok}/sendMessage", data=data, method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 (fixed https host)
            return 200 <= resp.status < 300
    except Exception:  # noqa: BLE001
        # An alert MUST NEVER break rotation, so swallow EVERYTHING — not just OSError/ValueError.
        # http.client.HTTPException (BadStatusLine / IncompleteRead / InvalidURL from a
        # captive-portal/proxy/malformed-token) is NOT an OSError subclass and would otherwise
        # escape and abort the retry. Emit a GENERIC line only — never str(e), which for an
        # InvalidURL embeds the full request URL (and thus the bot token).
        sys.stderr.write(
            "claude_rotate: 401 Telegram alert failed to send (best-effort, ignored)\n"
        )
        return False


def run_claude(
    argv: list[str], timeout: int, cwd: str, env: dict[str, str], buffer_stdin: bool = False
) -> subprocess.CompletedProcess:
    """Run ``claude`` (*argv*). On a usage-limit signal OR a 401 auth failure, rotate to another
    account and retry — walking through **each OTHER account at most once** (N-account support:
    mob/ob/can/…). Bounded by the account count, so it can never loop. A 401 (the active account's
    login token is dead) additionally fires a one-shot best-effort Telegram alert (:func:`_notify_
    telegram`) with the outcome — rotating to a valid standby recovers a 401 the account's own
    refresh could not; if no working standby remains the alert says so and the call gives up.
    Returns the (possibly retried) result of the last attempt.

    Wall time: each attempt gets the full *timeout*, so worst case is ``(1 + rotations) *
    timeout``. In practice a usage-limit render returns fast (the retry cost is ~the next
    call, not a timeout), so this only extends time on a genuine per-attempt hang — and
    ``rotations`` is bounded by the (small) account count, so the total stays bounded.

    *buffer_stdin*: when True (the CLI passthrough — ``main()`` → ``claude-run.sh`` →
    stdin-piping sysadmin scripts), piped stdin is buffered ONCE via :func:`_read_piped_stdin`
    and re-supplied on every attempt — otherwise the first attempt reads the fd to EOF and a
    rotation retry (the very case rotation exists for) would run with EMPTY stdin, losing the
    context. Direct callers (``bot.py`` / ``aro-wake`` — argv-based, systemd /dev/null stdin)
    leave it False, so their shared process stdin is never touched (no cross-thread read, no
    behavior change).
    """
    stdin_data = _read_piped_stdin() if buffer_stdin else None
    # Pin subprocess I/O to UTF-8 with errors="replace" (NOT text=True, which re-encodes stdin with
    # the LOCALE's encoding + STRICT errors): _read_piped_stdin decoded leniently, so under a
    # non-UTF-8 locale (LANG=C) a strict re-encode of any non-ASCII byte would raise UnicodeEncodeError
    # — a ValueError that escapes main()'s OSError/TimeoutExpired handlers. UTF-8/replace is symmetric
    # with the decode and locale-independent; claude's own I/O is UTF-8.
    result = subprocess.run(
        argv,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=cwd,
        env=env,
        input=stdin_data,
    )
    accounts = _list_accounts()
    start = _active_account()
    tried: set[str] = {start.name} if start else set()
    # Each OTHER account tried at most once. When the active creds match no snapshot
    # (start is None — e.g. an account whose snapshot isn't captured yet), ALL snapshots
    # are valid targets, so the bound is N, not N-1.
    max_rotations = max(0, len(accounts) - (1 if start else 0))
    rotations = 0
    died_account: str | None = None  # the FIRST account whose creds 401'd (dead), for the alert
    last_target: str | None = None  # the last account we rotated TO
    # Why the LAST rotation attempt gave up: "marker" (the operator withheld it — the alert below
    # stays silent, since nothing is proven dead), "error" (withheld fail-closed on an unreadable
    # pause state — the alert FIRES, saying so), or None (genuine exhaustion). Reported BY the gate
    # per thread (see _TLS), never re-read here: a give-up that never reached the gate
    # (max_rotations == 0 — a 1-snapshot host) correctly stays "exhausted".
    withheld_reason: str | None = None
    while True:
        combined = (result.stdout or "") + "\n" + (result.stderr or "")
        # Rotate on the usage-limit signal OR a 401, REGARDLESS of exit code / output format.
        # Never missing a real limit/401 is this feature's core guarantee, and Claude's exit code
        # is not reliably known — gating on `returncode != 0` (or on "is it valid JSON") would risk
        # silently failing to recover. The cost is a bounded, self-correcting false-positive: a
        # *successful* answer that merely quotes a limit/401 phrase triggers up to N-1 wasted
        # rotations (and, for a 401, a spurious alert) — bounded by the account count, standbys stay
        # valid, the operator still gets an answer. The keepalive ping never quotes such phrases; a
        # sysadmin analysis or operator chat could (accepted, same class as the usage-limit case).
        is_limit = is_usage_limit(combined)
        is_401 = is_auth_401(combined)
        if not is_limit and not is_401:
            break  # success or a non-rotatable error
        if is_401 and died_account is None:
            # Record the account that died BEFORE rotating, so the alert names it (not the target).
            d = _active_account()
            died_account = d.name if d is not None else "?"
        if rotations < max_rotations:
            # Clear THIS thread's slot first: a stubbed/monkeypatched rotate never writes it, and a
            # stale same-thread value from an earlier call would otherwise be read as this call's
            # verdict.
            _TLS.withheld_reason = None
            new_account = _rotate_active_account(avoid=frozenset(tried))
            # WHY it gave up matters for the alert below, and only the gate knows: a withheld
            # rotation is not evidence of dead credentials, while an exhausted one is.
            withheld_reason = getattr(_TLS, "withheld_reason", None)
        else:
            new_account = None  # the gate was never consulted → genuine exhaustion
            withheld_reason = None
        if new_account is None:
            break  # no untried account left → give up (all exhausted / <2 accounts / paused)
        last_target = new_account
        tried.add(new_account)
        rotations += 1
        result = subprocess.run(
            argv,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd,
            env=env,
            input=stdin_data,
        )
    # A 401 (dead creds) alerts AFTER the loop, reflecting the ACTUAL final outcome — never an
    # optimistic mid-loop guess, since a standby we rotated to may itself be dead. Recovery = the
    # final attempt is no longer a 401 (nor a limit). DEBOUNCED per host (_should_alert_401) so a
    # persistently-dead fleet doesn't flood Telegram. Best-effort; never raises (see _notify_telegram).
    if died_account is not None:
        final = (result.stdout or "") + "\n" + (result.stderr or "")
        host = _hostname()
        recovered = last_target is not None and not is_auth_401(final) and not is_usage_limit(final)
        # RULE: while the operator's MARKER is set, the all-dead alert is theirs to own — they are
        # actively working the credential pool and asked for no swaps, so this call is not allowed
        # to declare the fleet dead on their behalf. (That holds even when real standbys were tried
        # and died before the marker landed mid-run: the operator is at the keyboard.) The debounce
        # probe is SKIPPED with it — it records a send time even when nothing is sent, which would
        # mute the next genuine alert for ~12h. A fail-CLOSED refusal (_PAUSE_ERROR) is the
        # opposite case: nobody asked for silence, so the alert fires and names why the box could
        # not heal itself.
        if recovered:
            if _should_alert_401():
                _notify_telegram(
                    f"⚠️ Claude 401 on {host}: account '{died_account}' credentials were dead — "
                    f"auto-rotated to '{last_target}' and recovered. (alerts quiet ~12h)"
                )
        elif withheld_reason != _PAUSE_MARKER and _should_alert_401():
            if withheld_reason == _PAUSE_ERROR:
                why = " (pause-state unreadable — install refused fail-closed)"
            elif withheld_reason == _WITHHELD_FLEET:
                why = (
                    " (fleet mode — this caller still binds the shared ~/.claude; migrate it "
                    "to a fleet dir)"
                )
            else:
                why = ""
            _notify_telegram(
                f"🚨 Claude 401 on {host}: NO working Claude account — all credentials are dead."
                f"{why} Re-capture a fresh account (claude auth login / claude-manager). "
                f"(alerts quiet ~12h)"
            )
    # ── governor telemetry hooks (single-key quota governance, 2026-08-30) — both best-effort ──
    # A real claude call is the ONE moment the stored token is guaranteed fresh (the CLI just
    # rolled the chain; the direct oauth refresh is Cloudflare-403'd), so capture the account's
    # usage into the current-usage cache HERE — the governor's --probe-current reads it when the
    # token has gone stale between calls. And when the FINAL result still carries a usage-limit
    # (rotation exhausted or unavailable — the single-key case), signal the governor's reactive
    # cap so the NEXT routine call sheds instead of burning another attempt. Kill-switch:
    # CLAUDE_ROTATE_NO_USAGE_CAPTURE=1 disables both (and keeps old callers byte-identical).
    if not os.environ.get("CLAUDE_ROTATE_NO_USAGE_CAPTURE"):
        final_text = (result.stdout or "") + "\n" + (result.stderr or "")
        if is_usage_limit(final_text):
            _signal_governor_capped(final_text)
        else:
            _capture_current_usage()
    return result


def _account_email(acc: Path) -> str:
    """Best-effort account label from the (non-secret, world-readable) profile.json. No tokens.
    Tolerates a missing / malformed / non-object profile.json (returns "?", never raises)."""
    try:
        prof = json.loads((acc / "profile.json").read_text())
    except (OSError, ValueError):
        return "?"
    if not isinstance(prof, dict):
        return "?"
    inner = prof.get("account", prof)
    if not isinstance(inner, dict):
        inner = prof
    return inner.get("email_address") or inner.get("emailAddress") or prof.get("email") or "?"


def _find_account(name: str) -> Path | None:
    """Resolve *name* to a snapshot dir by exact dir name, exact email, or an **unambiguous**
    dir-name prefix (so ``--switch can`` finds ``can-ocoron-com-s-organization``). An empty
    name, or a prefix that matches more than one account, resolves to None — never an
    arbitrary pick (which would silently switch to the wrong identity)."""
    if not name:
        return None
    accounts = _list_accounts()
    exact = next((a for a in accounts if a.name == name), None)
    if exact is not None:
        return exact
    # Email branch: never resolve the "?" sentinel (profile-less accounts), and require a
    # UNIQUE match — an ambiguous email must not silently pick an arbitrary identity.
    if name != "?":
        by_email = [a for a in accounts if _account_email(a) == name]
        if len(by_email) == 1:
            return by_email[0]
        if len(by_email) > 1:
            return None
    prefix_matches = [a for a in accounts if a.name.startswith(name)]
    return prefix_matches[0] if len(prefix_matches) == 1 else None


def _cmd_list() -> int:
    active = _active_account()
    active_name = active.name if active else None
    accounts = _list_accounts()
    if not accounts:
        sys.stderr.write(f"no account snapshots under {ACCOUNTS_DIR}\n")
        return 1
    for acc in accounts:
        mark = "* " if acc.name == active_name else "  "
        sys.stdout.write(f"{mark}{acc.name}  ({_account_email(acc)})\n")
    if active_name is None:
        sys.stdout.write(
            "(active creds match no snapshot — capture the account via the claude-manager extension)\n"
        )
    return 0


def _reload_hint() -> None:
    sys.stdout.write(
        "Reload the VS Code workspace to pick it up "
        "(Ctrl/Cmd+Shift+P → 'Developer: Reload Window'). No restart needed.\n"
    )


def _cmd_switch(name: str) -> int:
    fleet_dirs = _fleet_dirs()
    if fleet_dirs:
        return _cmd_fleet_switch(name, fleet_dirs)
    target = _find_account(name)
    if target is None:
        sys.stderr.write(f"no account matching {name!r} — run `--list` to see options\n")
        return 1
    if _activate_snapshot(target):
        sys.stdout.write(
            f"switched active Claude account → {target.name} ({_account_email(target)})\n"
        )
        _reload_hint()
        return 0
    sys.stderr.write(
        "switch failed (unreadable creds, or the snapshot cannot authenticate — see above) — active account unchanged\n"
    )
    return 1


def _cmd_next() -> int:
    _TLS.withheld_reason = None  # this thread's slot is stale until the gate writes it
    new_account = _rotate_active_account()
    if new_account:
        match = _find_account(new_account)  # may be None if the snapshot vanished post-rotation
        email = _account_email(match) if match is not None else "?"
        sys.stdout.write(f"rotated active Claude account → {new_account} ({email})\n")
        _reload_hint()
        return 0
    if getattr(_TLS, "withheld_reason", None) is not None:
        # The gate already printed WHY on stderr (marker held, or pause state unreadable). The
        # "need ≥2 snapshots" hint below would send the operator to `--list` hunting a missing
        # snapshot that is not the problem.
        return 1
    sys.stderr.write("no other account to rotate to (need ≥2 snapshots) — run `--list`\n")
    return 1


def _cred_generation(data: bytes) -> int:
    """The credential's own generation marker: `claudeAiOauth.expiresAt` (ms epoch), or 0
    when absent/unparseable. Used to refuse a REGRESSION — a newer snapshot is never
    overwritten by an older live file."""
    try:
        oauth = json.loads(data).get("claudeAiOauth")
        val = oauth.get("expiresAt") if isinstance(oauth, dict) else None
        return int(val) if isinstance(val, (int, float)) else 0
    except (ValueError, TypeError, AttributeError):
        return 0


def _cred_generation_of(path: Path) -> int:
    try:
        return _cred_generation(path.read_bytes())
    except OSError:
        return 0


def _cmd_capture_current(into: Path | None = None) -> int:
    """Snapshot the LIVE credentials into the ACTIVE account's dir (plan 2026-08-10-plan-1) —
    or into an EXPLICIT, identity-verified ``into`` store (the drift-check's retarget path:
    the gate has already asked the API whose token this is, and its verdict outranks the
    marker-resolved active account).

    Why: a stored snapshot drifts off the live token every time Claude refreshes it. A restore
    of a stale snapshot installs a superseded refresh token, which the server rejects — the
    live 2026-08-10 12:05 "OAuth session expired and could not be refreshed" incident, whose
    snapshot was 1.5 days old. Keeping the snapshot equal to the live token makes that restore
    impossible.

    Atomic (tmp + ``os.replace``, mirroring ``_activate_snapshot``) so a crash mid-write can
    never leave a truncated snapshot — ``_secure_write`` alone unlinks then recreates. MONOTONE
    in the practical sense: identical content is a no-op (no churn, no mtime bump). Never emits
    token bytes.
    """
    live_tok = _read_access_token(ACTIVE_CREDS)
    if live_tok is None:
        sys.stderr.write(
            "claude_rotate: live credentials carry no access token — nothing to capture\n"
        )
        return 1
    target = into if into is not None else _active_account()
    if target is None:
        sys.stderr.write("claude_rotate: cannot resolve the active account — capture skipped\n")
        return 1
    # ⚠ RESIDUAL, deliberately accepted (review 2026-08-10): when the live token matches
    # no snapshot, identity falls back to the `.active-account` marker — and a legitimate
    # token REFRESH is indistinguishable from an out-of-band `claude auth login` as a
    # DIFFERENT account. Refusing marker-resolved captures would block the primary use
    # case (a refreshed token no longer matching its snapshot IS the drift we exist to
    # capture), so capture proceeds and the `.prev` rolling backup below is the recovery
    # path for a mis-capture. Documented in the plan's residuals, not silently ignored.

    dst = target / ".credentials.json"
    try:
        live_bytes = ACTIVE_CREDS.read_bytes()
    except OSError as e:
        sys.stderr.write(f"claude_rotate: cannot read live credentials: {e.strerror}\n")
        return 1
    try:
        if dst.is_file() and dst.read_bytes() == live_bytes:
            return 0  # already in sync — never churn the file
    except OSError:
        pass
    # Collision-proof tmp name (pid alone can repeat across namespaces/recycling).
    # MONOTONE (the plan's word, now enforced): refuse to regress a snapshot. `expiresAt`
    # is the credential's own generation marker — a live file rolled back to an older
    # token must never stamp over a newer stored one (review finding: the previous code
    # only skipped IDENTICAL content, which is idempotency, not monotonicity).
    if _cred_generation(live_bytes) < _cred_generation_of(dst):
        sys.stderr.write(
            f"claude_rotate: live credentials are OLDER than {target.name}'s snapshot —"
            " refusing to regress it (capture skipped)\n"
        )
        return 1
    tmp = dst.with_name(f"{dst.name}.tmp{os.getpid()}.{time.monotonic_ns():x}")
    lock_fd = None
    try:
        # Hold the rotation lock: without it a concurrent _activate_snapshot can land
        # between our identity resolution and this write, so `target` and the live bytes
        # would name two different accounts (review finding).
        try:
            lock_fd = os.open(str(ROTATE_LOCK), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
        except OSError:
            lock_fd = None  # best-effort: os.replace still keeps readers atomic
        # Roll the OUTGOING snapshot aside first — a capture must never be the operation
        # that loses a usable credential (mirrors _activate_snapshot's BACKUP_CREDS).
        if dst.is_file():
            try:
                _secure_write(dst.with_name(dst.name + ".prev"), dst.read_bytes())
            except OSError:
                pass  # best-effort backup; never block the capture itself
        _secure_write(tmp, live_bytes)
        os.replace(tmp, dst)  # atomic swap: a reader sees old-or-new, never a torn file
    except OSError as e:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        sys.stderr.write(f"claude_rotate: capture failed: {e.strerror}\n")
        return 1
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
            except OSError:
                pass
    print(f"captured live credentials into {target.name}")
    return 0


# ── quota rotation v2 (plan 2026-08-13-plan-2; spec dd79fe9a) ──────────────────────────────


def _now() -> float:
    return time.time()


def _iso_to_epoch(s: object) -> float | None:
    """ISO-8601 → epoch seconds; None on garbage (the endpoint's resets_at fields)."""
    if not isinstance(s, str) or not s:
        return None
    try:
        from datetime import datetime

        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


_OAUTH_HOSTS = ("api.anthropic.com", "platform.claude.com")
"""Probe hosts, tried in order. A module constant so the retry BOUND is derivable: the total
worst-case call count is ``len(_OAUTH_HOSTS) * attempts``, not ``attempts``. It was a literal
inside ``_oauth_get`` when the second host landed (d365a0a1, 2026-08-30), which silently doubled
a bound the test had pinned exactly 8 days earlier (627f8815) — the test then read 4 == 2 and sat
red until fleet ran the full suite and reported it (01M1MG98SC90HB863AW18XJKQ6)."""


def _oauth_get(
    path: str,
    token: str,
    timeout_s: float | None = None,
    attempts: int | None = None,
    backoff_s: float = 0.3,
) -> dict | None:
    """GET an api/oauth/* resource with a store token. None on ANY failure — a telemetry
    miss must never crash a tick. Never emits token bytes.

    Bounded retry for TRANSIENT failures (timeout / connection reset / 5xx) with a short
    per-attempt timeout, so a single network blip does not blank the quota dashboard: the
    ping-free ``--status`` path this feeds runs behind a 60s subprocess cap, and one stalled
    ``urlopen`` under a flaky link (VPN drop) used to trip it (observed 2026-08-22 — the board
    showed "Live probe failed — TimeoutExpired after 60s"). A 4xx (esp. 401/403) is DEFINITIVE
    auth, NEVER retried — retrying a dead/wrong token only burns the budget. Both knobs are
    env-tunable (``OAUTH_GET_TIMEOUT_S`` / ``OAUTH_GET_ATTEMPTS``).

    ⚠️ ``attempts`` is PER HOST. The worst case is ``len(_OAUTH_HOSTS) * attempts`` calls, so the
    8s default bounds a total of ~32s, not ~16s — still inside the caller's 60s subprocess cap,
    but the number to check when either knob moves."""
    import urllib.error
    import urllib.request

    if timeout_s is None:
        timeout_s = _env_float("OAUTH_GET_TIMEOUT_S", 8.0)
    if attempts is None:
        attempts = max(1, int(_env_float("OAUTH_GET_ATTEMPTS", 2.0)))
    # TWO hosts, tried in order. Measured live on vps1 (2026-08-30): the SAME valid token got
    # HTTP 429 from api.anthropic.com (datacenter-IP throttling — every VPS probe blanked, which
    # silently starved the governor's usage capture) and HTTP 200 from platform.claude.com. A 429
    # is a HOST verdict, not a token verdict — falling through to the sibling host turns a
    # permanently-throttled vantage into a working probe. 401/403 stays definitive (dead/wrong
    # token — no host will differ); 5xx retries the same host.
    for host in _OAUTH_HOSTS:
        req = urllib.request.Request(
            f"https://{host}/api/oauth/{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "anthropic-beta": "oauth-2025-04-20",
                # Cloudflare bot-blocks urllib's default "Python-urllib/3.x" UA on
                # platform.claude.com (measured on vps1: default UA → 403, this UA → 200 with
                # the same token). A named UA is also just honest client identification.
                "User-Agent": "claude-rotate/1.0",
            },
        )
        for i in range(attempts):
            try:
                with urllib.request.urlopen(req, timeout=timeout_s) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    return None  # definitive (dead/wrong token) — no other host will differ
                if e.code < 500:
                    break  # 429/other-4xx: this HOST refuses — try the next host
                # 5xx is a transient server error → fall through to the retry
            except Exception:
                pass  # timeout / URLError / socket / malformed JSON — transient, retry
            if i < attempts - 1:
                time.sleep(backoff_s * (i + 1))
    return None


def _account_status(store: Path) -> dict:
    """One telemetry row for a snapshot dir: identity + both quota windows. valid=False when
    the stored token no longer answers (dead snapshot → relogin needed)."""
    row: dict = {
        "name": store.name,
        "store": str(store),
        "valid": False,
        "email": None,
        "five_hour": None,
        "seven_day": None,
        "refresh_expires_at_epoch": None,
    }
    tok = _read_access_token(store / ".credentials.json")
    if tok is None:
        return row
    try:
        blob = json.loads((store / ".credentials.json").read_text())
        exp_ms = (blob.get("claudeAiOauth") or {}).get("refreshTokenExpiresAt")
        if isinstance(exp_ms, (int, float)) and exp_ms > 0:
            row["refresh_expires_at_epoch"] = float(exp_ms) / 1000.0
    except (OSError, ValueError):
        pass
    prof = _oauth_get("profile", tok)
    usage = _oauth_get("usage", tok)
    if not prof or not usage:
        # A dead ACCESS token (they expire ~8h) with a LIVE refresh token is NOT a dead
        # account — the CLI will refresh it the moment it becomes live. Mark it usable but
        # UNKNOWN so the successor ranking prefers accounts with real telemetry and only
        # falls back to these (the spec's documented degradation path). A store whose
        # REFRESH token is also expired is genuinely dead → relogin.
        rexp = row.get("refresh_expires_at_epoch")
        if rexp is not None and rexp > _now():
            row["valid"] = True
            row["telemetry"] = "unknown-parked"
        return row
    row["email"] = (prof.get("account") or {}).get("email")
    # FAIL-CLOSED parse (closer F6): a 200 with a changed/partial shape must read as
    # UNKNOWN (row invalid), never as 0% — 0% makes a walled sibling the most attractive
    # successor and stops the live account from ever rotating.
    windows_ok = True
    for key in ("five_hour", "seven_day"):
        w = usage.get(key)
        u = w.get("utilization") if isinstance(w, dict) else None
        if not isinstance(u, (int, float)):
            windows_ok = False
            row[key] = None
            continue
        row[key] = {"utilization": float(u), "resets_at_epoch": _iso_to_epoch(w.get("resets_at"))}
    row["valid"] = row["email"] is not None and windows_ok
    return row


def _is_live_store(store: Path) -> bool:
    """True when this store's tokens ARE the live file's (same guard family as
    _keepwarm_refresh's) — token-compared, never marker-trusted."""
    live = _read_access_token(ACTIVE_CREDS)
    return live is not None and _read_access_token(store / ".credentials.json") == live


def _collect_statuses() -> tuple[list[dict], str | None]:
    """(all store rows, the live store's name). Seam for tests and the tick."""
    active = _active_account()
    rows = [_account_status(a) for a in _list_accounts()]
    return rows, (active.name if active is not None else None)


def _status_payload() -> dict:
    rows, live = _collect_statuses()
    out = []
    for r in rows:
        row = dict(r)
        if not row["valid"]:
            row["note"] = "INVALID (relogin needed)"
        out.append(row)
    # The pause state rides the JSON too (not just the text banner): a machine consumer reading a
    # healthy-looking payload while switching is off entirely has no way to know rotation is
    # withheld. null = running, "marker" = operator paused, "error" = pause state unreadable.
    # fleet_warnings rides the JSON too: the carrier invariant fails OPEN, so a machine consumer
    # reading a healthy-looking payload has no other way to learn a window silently rejoined the
    # shared chain. Empty list = every mapped carrier present and occupancy within bounds.
    return {
        "accounts": out,
        "live": live,
        "pause": _pause_state(),
        "fleet_warnings": _fleet_warnings(),
    }


def _cmd_status(as_json: bool) -> int:
    # Fleet mode (login-once architecture): ≥1 scaffolded fleet dir flips --status into the
    # per-ACCOUNT view (grouped dirs, freshest-token quota, cached-with-age fallback). The
    # legacy manager-accounts view below stays BYTE-unchanged for the empty-fleet box
    # (regression-guarded in tests/test_claude_fleet.py).
    fleet_dirs = _fleet_dirs()
    if fleet_dirs:
        return _cmd_fleet_status(fleet_dirs, as_json)
    pay = _status_payload()
    if as_json:
        print(json.dumps(pay, indent=1))
        return 0
    pause = pay["pause"]  # already probed for the payload; soft, so it never crashes --status
    if pause == _PAUSE_MARKER:
        print("⏸ auto-switch PAUSED (--resume-switch to re-enable)")
    elif pause == _PAUSE_ERROR:
        print(
            "⏸ auto-switch PAUSED (pause state unreadable — assumed paused; "
            "check the rotate state dir)"
        )
    from datetime import datetime

    def fmt(w):
        if not w:
            return "-"
        rs = w.get("resets_at_epoch")
        rs_s = datetime.fromtimestamp(rs).strftime("%a %H:%M") if rs else "?"
        return f"{w['utilization']:.0f}% (resets {rs_s})"

    for r in pay["accounts"]:
        mark = "*" if r["name"] == pay["live"] else " "
        if r.get("telemetry") == "unknown-parked":
            print(f"{mark} {r['name']:32} parked — quota unknown until used (refresh token valid)")
        elif r["valid"]:
            print(
                f"{mark} {r['email'] or r['name']:32} session {fmt(r['five_hour']):24}"
                f" weekly {fmt(r['seven_day'])}"
            )
        else:
            print(f"{mark} {r['name']:32} INVALID (relogin needed)")
    for warn in pay.get("fleet_warnings") or []:
        print(warn)
    return 0


def _walled(row: dict) -> bool:
    if row.get("telemetry") == "unknown-parked":
        return False  # no evidence of a wall; ranked last (see _pick_successor)
    for key in ("five_hour", "seven_day"):
        w = row.get(key)
        if not w:
            return True  # no telemetry → not a safe switch target
        if w["utilization"] >= 100.0:
            return True
    return False


def _pick_successor(candidates: list[dict], current_name: str | None, now: float) -> str | None:
    """PERISHABLE-FIRST (operator-settled): among valid, un-walled, non-current rows, the
    soonest weekly reset wins (quota about to refresh is the cheapest to burn); ties break to
    lower weekly then lower session utilization."""
    eligible = [
        r for r in candidates if r.get("valid") and not _walled(r) and r["name"] != current_name
    ]
    if not eligible:
        return None
    far = now + 365 * 86400
    eligible.sort(
        key=lambda r: (
            1 if r.get("telemetry") == "unknown-parked" else 0,
            (r.get("seven_day") or {}).get("resets_at_epoch") or far,
            (r.get("seven_day") or {}).get("utilization", 100.0),
            (r.get("five_hour") or {}).get("utilization", 100.0),
        )
    )
    return eligible[0]["name"]


# ── the fleet: one config dir per window, one OAuth refresh chain per dir ─────────────────────
# The login-once architecture (docs/superpowers/specs/2026-08-15-login-once-credentials-design.md).
# Every long-lived window points CLAUDE_CONFIG_DIR *and* CLAUDE_QUOTA_HOME at its own
# <fleet-root>/<slug>/, so its refresh chain has exactly ONE owner. Refresh tokens are single-use:
# sharing one chain across N processes is what produces the morning relogin wave. CLAUDE_QUOTA_HOME
# rides along because the wall/resume layer resolves its home from that variable, not from
# CLAUDE_CONFIG_DIR — without it every window would sleep on every other window's quota wall.

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Shared state that must NOT fragment across ~15 dirs. DIRECTORIES are symlinked: a rename inside a
# symlinked dir resolves through the link and lands on the canonical inode, so the link survives
# every write (proven: test_writethrough_survives_a_directory_symlink).
_SHARED_DIR_LINKS: Final = ("agents", "commands", "skills", "projects")
# settings.json is COPIED, never symlinked. WRITE-THROUGH PROBE (2026-08-15): the CLI writes config
# with tmp+rename, and POSIX rename(2) operates on the LINK rather than its target — os.replace onto
# a FILE symlink REPLACES the link with a regular file. A symlinked settings.json would therefore
# fork off the canonical copy on the CLI's first settings write (the leftover
# `.claude.json.tmp.<pid>.<hex>` files in ~/.claude-youtube-headless/ are that mechanism's
# fingerprint). The copy is re-pushed by --sync-shared instead. Guarded by
# test_writethrough_rename_replaces_a_file_symlink: if POSIX ever changes, that test goes red and
# this decision is re-taken deliberately.
_SHARED_FILE_COPIES: Final = ("settings.json",)

# BOTH variables or the carrier is a no-op — see the CLAUDE_QUOTA_HOME note above.
_CARRIER_ENV_KEYS: Final = ("CLAUDE_CONFIG_DIR", "CLAUDE_QUOTA_HOME")
# Live claude sessions still bound to the SHARED ~/.claude allowed once the fleet exists: the
# operator's ad-hoc runs plus a straggler. Above this, sessions have SILENTLY REJOINED the shared
# chain — the failure this architecture exists to prevent, and one that is otherwise invisible
# (a missing carrier fails OPEN: the session just works, on the wrong chain).
_SHARED_BOUND_MAX_DEFAULT = 3
# The hub checkout. Its 3 concurrent windows share this cwd, so a cwd-keyed carrier cannot split
# them — and a settings `env` entry OVERRIDES each window's own value, which would collapse all
# three onto ONE dir and ONE chain: strictly worse than today. The hub therefore gets NO carrier;
# each window carries the two variables in its own environment. --project refuses it (spec rule).
HUB_REPO = Path("/opt/fabrik")
# Module constant so tests can point the session scan at a fixture tree instead of the live kernel.
PROC_DIR = Path("/proc")
# Where project repos live — the fleet tick's drain-mail routing resolves a slug to /opt/<slug>.
# Module constant so tests route against a fixture tree, never the real /opt.
OPT_DIR = Path("/opt")
# An account's quota is read LIVE only with a token fresh enough to still answer (~8h access-token
# life); the freshness signal is the credential file's MTIME — the CLI rewrites it on every
# refresh, so mtime IS last-use. Older than this → the cached last-known row (marked stale).
_FLEET_TOKEN_FRESH_S = 8 * 3600
# --keepalive pings a dir whose chain has idled longer than this (weekly cron beats the ~30-day
# refresh-token idle lapse with three weeks of margin).
_KEEPALIVE_MAX_IDLE_S = 7 * 86400


def _pull_opts(args: list[str], names: tuple[str, ...]) -> tuple[list[str], dict[str, str], bool]:
    """Split ``--name value`` options out of *args*. Returns (positionals, options, malformed).

    *malformed* is True for an option given without a value or an unknown ``--flag``, so the caller
    prints usage instead of silently treating the flag as a positional (``--new-dir seo --project``
    must not scaffold a dir literally named ``--project``).
    """
    rest: list[str] = []
    opts: dict[str, str] = {}
    i = 0
    while i < len(args):
        token = args[i]
        if token in names:
            if i + 1 >= len(args):
                return rest, opts, True
            opts[token] = args[i + 1]
            i += 2
            continue
        if token.startswith("--"):
            return rest, opts, True
        rest.append(token)
        i += 1
    return rest, opts, False


def _fleet_root() -> Path:
    """Root of the per-window config-dir fleet: ``CLAUDE_FLEET_ROOT`` or ``~/.claude-fleet``.

    Resolved at CALL time (never cached in a module constant) so a test env and a changed HOME are
    both honored. Unlike :func:`_rotate_state_dir` it NEVER mkdirs: every READER here (``--status``,
    ``--sync-mcp``) must be able to report "no fleet yet" without conjuring one, and a stray mkdir
    from a status probe would make the migration's own progress unreadable. ``--new-dir`` is the
    only creator.
    """
    return Path(os.environ.get("CLAUDE_FLEET_ROOT") or Path.home() / ".claude-fleet")


def _assignments_path() -> Path:
    """The routing table: slug → {account, created, identity, project?}. The advisor, ``--status``
    and the drain mail all read it; it is the only record of which account a dir belongs to."""
    return _fleet_root() / "assignments.json"


def _load_assignments(strict: bool) -> dict:
    """Read the routing table.

    ``strict=True`` is the WRITE path: a corrupt/absurd file RAISES, because appending a row to
    bytes we could not parse would destroy the routing for every other window. ``strict=False`` is
    the READ path (``--status``): it degrades to ``{}`` — a broken table must not take the status
    banner down with it. Both treat "no file yet" as an empty table, never a fault.
    """
    path = _assignments_path()
    try:
        raw = path.read_text()
    except FileNotFoundError:
        return {}
    except _STATE_DIR_ERRORS:
        if strict:
            raise
        return {}
    try:
        data = json.loads(raw) if raw.strip() else {}
    except ValueError:
        if strict:
            raise
        return {}
    if isinstance(data, dict):
        return data
    if strict:
        raise ValueError(f"{path} is not a JSON object")
    return {}


def _write_json_atomic(dst: Path, data: object, mode: int = 0o600) -> None:
    """tmp+rename *within the destination's own directory* — same filesystem, so the rename is
    atomic and a reader never sees a half-written table. The temp file is unlinked on any failure
    so a crashed write leaves no `.tmp.` litter behind (the fingerprint we diagnosed the symlink
    fork from)."""
    fd, tmp = tempfile.mkstemp(dir=str(dst.parent), prefix=f".{dst.name}.tmp.")
    try:
        # The fd is closed EXACTLY once, by exactly one owner. os.fdopen ADOPTS the descriptor, so
        # the manual close belongs only on the path where fdopen itself raised and adoption never
        # happened; once `fh` exists, the with-block owns it and this function must never touch the
        # number again. An EBADF guard is NOT good enough: between the with-block's close and a
        # later os.close(fd), a sibling thread can be handed the same fd number by the kernel — and
        # this twin runs under asyncio.to_thread in aro-wake — so the "harmless" close would shut
        # someone else's file.
        try:
            fh = os.fdopen(fd, "w")
        except BaseException:
            os.close(fd)  # fdopen did not adopt it; we are still the owner
            raise
        with fh:
            json.dump(data, fh, indent=1, sort_keys=True)
            fh.write("\n")
        os.chmod(tmp, mode)
        os.replace(tmp, dst)
    except BaseException:
        try:
            os.unlink(tmp)  # never leave `.tmp.` litter behind
        except OSError:
            pass
        raise


def _carrier_path(repo: Path) -> Path:
    """The project's carrier file. ``settings.local.json``, NOT ``settings.json``: the latter is a
    governance-synced surface (``fabrik_synced_manifest.py``) and would be overwritten fleet-wide."""
    return repo / ".claude" / "settings.local.json"


def _load_carrier(repo: Path) -> dict:
    """Existing carrier contents, or ``{}`` when there is none.

    RAISES on anything we cannot safely merge INTO. Three live projects already keep Claude Code
    permissions state in this file (2026-08-15), so a clobber costs the operator real approvals —
    unparseable means refuse loudly, never overwrite.
    """
    path = _carrier_path(repo)
    try:
        raw = path.read_text()
    except FileNotFoundError:
        return {}
    if not raw.strip():
        return {}
    data = json.loads(raw)  # ValueError propagates — the caller refuses
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    if not isinstance(data.get("env", {}), dict):
        raise ValueError(f"{path} has a non-object 'env' section")
    return data


def _write_carrier(repo: Path, cfg_dir: Path) -> Path:
    """Deep-set BOTH env vars in the project's carrier, preserving every other key it holds."""
    data = _load_carrier(repo)
    env = dict(data.get("env") or {})
    for key in _CARRIER_ENV_KEYS:
        env[key] = str(cfg_dir)
    data["env"] = env
    path = _carrier_path(repo)
    # PRESERVE an existing file's mode. Merging into someone's carrier must not silently widen (or
    # narrow) its permissions as a side effect — an operator who chmod 600'd theirs keeps it. 0644
    # applies only to a carrier we are creating: it is not a secret and other tooling reads it.
    try:
        mode = path.stat().st_mode & 0o777
    except OSError:
        mode = 0o644
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(path, data, mode=mode)
    return path


def _assignments_lock_fd() -> int:
    """An exclusive flock over the routing table, held across READ-MODIFY-WRITE.

    Without it two concurrent ``--new-dir`` runs both read the table, both add their own row to
    their own copy, and the second write LOSES the first row — the dir exists but nothing routes to
    it (reproduced). Same ``fcntl.flock`` idiom the credential swap uses; a dedicated lock file so
    it never contends with rotation.
    """
    root = _fleet_root()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return os.open(str(root / "assignments.lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)


def _roster_source(spec: str | None = None) -> Path:
    """The ``.claude.json`` to read the MCP roster (and a new dir's seed) FROM.

    *spec* accepts a fleet SLUG (``seo``), a directory, or a direct file path; ``None`` falls back
    to ``~/.claude.json``. The fallback is a REAL hazard once the fleet exists: post-migration
    ``~/.claude.json`` is the ad-hoc leftover, so syncing from it would push a stale roster over
    every dir's current one. Callers warn when they take the fallback with dirs present.
    """
    if spec is None:
        return USER_CLAUDE_JSON
    path = (
        Path(spec).expanduser() if ("/" in spec or spec.endswith(".json")) else _fleet_root() / spec
    )
    return path / ".claude.json" if path.is_dir() else path


def _replace_file(dst: Path, body: bytes, mode: int = 0o600) -> None:
    """Write *body* to *dst* via tmp+rename.

    NOT ``write_bytes``: that truncates in place (a reader mid-write sees a partial file) and it
    writes THROUGH a symlink — which would silently re-fork the seeding decision this module pinned,
    pushing bytes into the canonical ``~/.claude`` file instead of the dir's own copy. ``os.replace``
    onto a symlink path replaces the LINK with the real file, which is exactly the copy branch.
    """
    fd, tmp = tempfile.mkstemp(dir=str(dst.parent), prefix=f".{dst.name}.tmp.")
    try:
        # Single-owner fd discipline — see the identical note in _write_json_atomic.
        try:
            fh = os.fdopen(fd, "wb")
        except BaseException:
            os.close(fd)  # fdopen did not adopt it; we are still the owner
            raise
        with fh:
            fh.write(body)
        os.chmod(tmp, mode)
        os.replace(tmp, dst)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _has_credentials(dest: Path) -> bool:
    """True when this dir holds a credential file — i.e. an account has logged in here.

    The single most important predicate in this command: it is the difference between "an
    abandoned half-built dir I may complete or delete" and "a LIVE OAuth chain that must never be
    touched". ``is_symlink`` counts too — a dangling credential symlink still means hands off.
    """
    creds = dest / ".credentials.json"
    return creds.is_symlink() or creds.exists()


def _cmd_new_dir(
    slug: str, email: str, project: str | None = None, source: str | None = None
) -> int:
    """Scaffold — or RESUME — one fleet dir:
    ``--new-dir <slug> <account-email> [--project /opt/<repo>]``.

    Creates ``<fleet-root>/<slug>/`` at 0700, seeds ``.claude.json`` from the roster source, links
    or copies the shared surfaces per the seeding contract, records the assignments row, and — when
    a repo is given — writes that repo's two-variable carrier. It NEVER reads or writes a credential
    byte: the dir is created empty of credentials and filled by ONE operator ``/login``.

    **Every step is IDEMPOTENT and the command is RESUMABLE.** A dir that exists but holds no
    credentials is an unfinished scaffold, not a live chain, so re-running COMPLETES it (seeding
    what is absent, linking what is absent, writing the carrier if absent or incomplete) and exits
    0. That converts every partial-failure state into "fix the cause, re-run" instead of a
    permanently wedged slug.

    For an existing slug the assignments ROW is truth. It refuses (rc 1) on exactly the states where
    re-running would destroy or duplicate something: the dir holds a ``.credentials.json`` (a live
    chain — never re-seeded); the row names a DIFFERENT account; the row has no usable ``account``
    (corrupt — never claimed); the row is already bound to a DIFFERENT project (moving a binding is
    an operator action, never a scaffold side effect); or the routing table cannot be parsed. With
    ``--project`` omitted, a resume completes the binding the row already records.

    The whole body runs under the assignments flock, so two concurrent runs on any slug serialize
    rather than losing each other's row.
    """
    if not _SLUG_RE.match(slug):
        sys.stderr.write(
            f"claude_rotate: refusing slug {slug!r} — kebab-case [a-z0-9-] only "
            "(the slug becomes a directory name under the fleet root)\n"
        )
        return 2
    if slug == _ACTIVE_POINTER_NAME:
        sys.stderr.write(
            f"claude_rotate: refusing slug {slug!r} — reserved for the fleet's active-pointer "
            "symlink (scaffolding it would write INTO whichever account dir the pointer names)\n"
        )
        return 2
    if "@" not in email:
        sys.stderr.write(f"claude_rotate: refusing account {email!r} — expected an email address\n")
        return 2

    repo: Path | None = None
    if project is not None:
        repo = Path(project).expanduser().resolve()
        if not repo.is_dir():
            sys.stderr.write(f"claude_rotate: --project {repo} is not a directory\n")
            return 2
        try:
            hub = HUB_REPO.resolve()
        except OSError:
            hub = HUB_REPO
        if repo == hub:
            sys.stderr.write(
                f"claude_rotate: refusing --project {repo} — the hub gets NO carrier. Its 3 windows "
                "share this cwd, and a settings 'env' entry OVERRIDES each window's own value, so a "
                "carrier here would collapse all three onto ONE dir and ONE chain. Create the role "
                "dirs without --project and set CLAUDE_CONFIG_DIR per window instead.\n"
            )
            return 1
        # PRE-FLIGHT the carrier merge BEFORE any mutation: a corrupt settings.local.json must abort
        # the whole command rather than leave a dir that no carrier points at (which would read as
        # "migrated" in assignments.json while the project silently stays on ~/.claude).
        try:
            _load_carrier(repo)
        except (OSError, ValueError) as e:
            sys.stderr.write(
                f"claude_rotate: {_carrier_path(repo)} exists but cannot be parsed ({e}) — "
                "refusing; fix or move it by hand (it holds this project's permissions state)\n"
            )
            return 1

    try:
        lock_fd = _assignments_lock_fd()
    except _STATE_DIR_ERRORS as e:
        sys.stderr.write(f"claude_rotate: cannot lock the fleet root ({e}) — refusing\n")
        return 1
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        return _new_dir_locked(slug, email, repo, _roster_source(source))
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)


def _new_dir_locked(slug: str, email: str, repo: Path | None, source: Path) -> int:
    """The scaffold/resume body — runs with the assignments flock held (see :func:`_cmd_new_dir`)."""
    root = _fleet_root()
    dest = root / slug

    try:
        table = _load_assignments(strict=True)
    except _STATE_DIR_ERRORS as e:
        # strict: never append a row to bytes we could not parse — that would silently REPLACE the
        # routing table for every other window with a table containing only this row.
        sys.stderr.write(
            f"claude_rotate: {_assignments_path()} cannot be parsed ({e}) — refusing to append "
            "(it is the routing table for every other window)\n"
        )
        return 1

    existing = table.get(slug) if isinstance(table.get(slug), dict) else None
    if existing is not None:
        # The ROW is truth for an existing slug. assignments.json is hand-editable, so a row whose
        # account is missing/null/blank is CORRUPT, not "unclaimed": treating it as claimable let
        # any email take over an existing slug's dir (same family as the unparseable-table refusal).
        claimed = existing.get("account")
        if not isinstance(claimed, str) or not claimed.strip():
            sys.stderr.write(
                f"claude_rotate: the {slug} row in {_assignments_path()} has no usable 'account' "
                f"({claimed!r}) — refusing. Repair the row by hand; a corrupt row is never claimed.\n"
            )
            return 1
        if claimed != email:
            sys.stderr.write(
                f"claude_rotate: {slug} is already assigned to {claimed!r}, not {email!r} — "
                "refusing (rebalancing an account is a deliberate re-login, not a re-scaffold)\n"
            )
            return 1
        # …and truth for the PROJECT binding too. Silently re-pointing it would leave the OLD repo's
        # carrier in place and live: two repos bound to one chain, with --status blind to the first
        # (it only ever checks the row's current project).
        bound = existing.get("project")
        if bound and repo is not None and str(repo) != str(bound):
            sys.stderr.write(
                f"claude_rotate: {slug} is already bound to {bound} (carrier "
                f"{_carrier_path(Path(str(bound)))}), not {repo} — refusing. Moving a binding is an "
                "operator action: remove the old carrier and edit the assignments row, never a "
                "scaffold side effect (two live carriers would share one chain, unmonitored).\n"
            )
            return 1
        if bound and repo is None:
            repo = Path(str(bound))  # resume completes the binding the row already records
    if _has_credentials(dest):
        sys.stderr.write(
            f"claude_rotate: {dest} holds a .credentials.json — refusing. That is a LIVE OAuth "
            "chain; re-seeding it would overwrite config under a running session.\n"
        )
        return 1

    resuming = dest.is_symlink() or dest.exists()
    if resuming and not dest.is_dir():
        sys.stderr.write(f"claude_rotate: {dest} exists but is not a directory — refusing\n")
        return 1

    notes: list[str] = []
    created_here = False
    try:
        if not resuming:
            root.mkdir(mode=0o700, parents=True, exist_ok=True)
            dest.mkdir(mode=0o700)
            created_here = True
        # mkdir's mode is umask-masked, and a resumed dir may predate this line: assert 0700 either
        # way — the dir will hold an OAuth chain.
        os.chmod(dest, 0o700)
        _scaffold_dir(dest, notes, source)
    except _STATE_DIR_ERRORS as e:
        # One clean line, not a traceback — and best-effort remove the partial dir so the slug is
        # retryable instead of permanently wedged. ONLY when THIS invocation created it and it holds
        # no credentials: a resumed dir is someone else's state, and a dir with a chain is sacred.
        cleaned = ""
        if created_here and not _has_credentials(dest):
            try:
                shutil.rmtree(dest)
                cleaned = " (partial dir removed — re-run when fixed)"
            except OSError:
                cleaned = f" (could NOT remove the partial dir {dest} — remove it by hand)"
        sys.stderr.write(f"claude_rotate: scaffolding {dest} failed ({e}){cleaned}\n")
        return 1

    from datetime import UTC, datetime

    row: dict = dict(existing or {})
    row["account"] = email
    # Preserve the ORIGINAL creation stamp across a resume — it dates the dir, not the last attempt.
    row.setdefault("created", datetime.now(UTC).isoformat(timespec="seconds"))
    # Identity is pinned ONCE, at the login that follows — never re-probed per status, so the
    # dead-token identity gate that lost an account's chain is not reintroduced. A resume must not
    # reset an already-pinned identity back to pending.
    row.setdefault("identity", "pending-login")
    if repo is not None:
        row["project"] = str(repo)
    table[slug] = row
    try:
        _write_json_atomic(_assignments_path(), table)
    except _STATE_DIR_ERRORS as e:
        sys.stderr.write(f"claude_rotate: cannot write {_assignments_path()} ({e})\n")
        return 1

    verb = "resumed" if resuming else "fleet dir"
    print(f"{verb}: {dest} (account {email}, identity {row['identity']})")
    if repo is not None:
        # The parse hazard was pre-flighted, so what is left is a WRITE failure (a read-only
        # checkout, a full disk). Report it as a non-zero exit rather than a traceback: the dir and
        # its row exist, the carrier monitor now names this project on every --status until it is
        # written, and re-running resumes — a visible, self-announcing half-state, never a silent one.
        try:
            carrier = _write_carrier(repo, dest)
        except (OSError, ValueError) as e:
            sys.stderr.write(
                f"claude_rotate: fleet dir ready, but the carrier {_carrier_path(repo)} "
                f"could not be written ({e}) — --status will WARN; fix and re-run to resume\n"
            )
            return 1
        print(f"carrier:   {carrier} → {', '.join(_CARRIER_ENV_KEYS)}")
    for note in notes:
        print(f"  note: {note}")
    print("  next: ONE /login in this dir's context — no credential bytes were copied")
    return 0


def _scaffold_dir(dest: Path, notes: list[str], source: Path) -> None:
    """Seed + link the shared surfaces INTO *dest*, idempotently (absent pieces only).

    Skipping what already exists is what makes ``--new-dir`` resumable: a re-run completes a
    half-built dir without disturbing anything the first run (or a login) already put there.
    """
    target = dest / ".claude.json"
    if not target.exists():
        try:
            seed = source.read_bytes()
        except OSError:
            seed = b"{}\n"
            notes.append(f"seeded an EMPTY .claude.json — {source} is unreadable")
        # 0600 + O_EXCL|O_NOFOLLOW: .claude.json carries the account identity and machine ID, and
        # the path is predictable. The same guard the credential writes use.
        _secure_write(target, seed)

    for name in _SHARED_DIR_LINKS:
        link = dest / name
        if link.is_symlink() or link.exists():
            continue
        src = CLAUDE_DIR / name
        if not src.is_dir():
            notes.append(f"skipped the {name}/ symlink — {src} does not exist")
            continue
        link.symlink_to(src, target_is_directory=True)

    for name in _SHARED_FILE_COPIES:
        copy = dest / name
        if copy.exists():
            continue
        src = CLAUDE_DIR / name
        try:
            body = src.read_bytes()
        except OSError:
            notes.append(f"skipped the {name} copy — {src} does not exist")
            continue
        # 0644, like the carrier and like the canonical file: shared config, not a secret, and other
        # tooling reads it. Without an explicit mode it would inherit _replace_file's 0600 default.
        _replace_file(copy, body, mode=0o644)


def _merge_roster_once(target: Path, roster: dict) -> str | None:
    """Merge *roster* into one dir's ``.claude.json``. Returns None on success, else a reason.

    Read-modify-write against a file a LIVE CLI also writes (a ``/login`` completing mid-sync writes
    the OAuth section). The target's mtime is captured before the read and re-checked immediately
    before the replace; a change means our in-memory copy is stale and would DISCARD that login, so
    we re-read and re-merge once, then give up rather than clobber. Residual: the re-check→replace
    window is still not atomic (no lock is available on the CLI side), so a write landing inside
    those microseconds is lost — acceptable on a single-operator box where the operator is the one
    running the sync, and strictly better than the unconditional overwrite it replaces.
    """
    for attempt in (0, 1):
        try:
            before = target.stat().st_mtime_ns
            blob = json.loads(target.read_text())
            if not isinstance(blob, dict):
                raise ValueError("not a JSON object")
        except FileNotFoundError:
            return "no .claude.json (was it made by --new-dir?)"
        except (OSError, ValueError) as e:
            return f".claude.json unreadable ({e}) — NOT overwritten"
        blob["mcpServers"] = roster
        try:
            if target.stat().st_mtime_ns != before:
                if attempt == 0:
                    continue  # a live write landed under us — re-read and re-merge onto it
                return "changed under us twice (a live session is writing it) — skipped"
            _write_json_atomic(target, blob)
        except (OSError, ValueError) as e:
            return f"write failed ({e})"
        return None


def _cmd_sync_shared(include_settings: bool, source: str | None = None) -> int:
    """Re-push the SHARED surfaces into every fleet dir.

    ``--sync-mcp`` pushes only the MCP roster; ``--sync-shared`` additionally re-pushes the shared
    file copies (``settings.json``), which are copies rather than symlinks (see
    ``_SHARED_FILE_COPIES``). The roster push is a section-level MERGE, never a file copy: each
    dir's other ``.claude.json`` sections — above all its own OAuth account and per-project trust —
    are read, preserved and written back untouched, and a dir whose ``.claude.json`` cannot be
    parsed is SKIPPED rather than overwritten.

    ``--from <slug|path>`` selects the roster SOURCE. This matters after migration: ``~/.claude.json``
    becomes the ad-hoc leftover, so the default source goes stale and syncing from it would REVERT
    every dir to an old roster. Taking the default with dirs present prints a loud warning naming
    the fix.
    """
    src = _roster_source(source)
    root = _fleet_root()
    try:
        dirs = sorted(d for d in root.iterdir() if d.is_dir())
    except FileNotFoundError:
        sys.stderr.write(f"claude_rotate: no fleet root at {root} — nothing to sync\n")
        return 1
    except OSError as e:
        sys.stderr.write(f"claude_rotate: cannot list {root} ({e})\n")
        return 1

    if source is None and dirs:
        sys.stderr.write(
            f"claude_rotate: WARNING — syncing FROM {src}, the shared ad-hoc dir, while "
            f"{len(dirs)} fleet dir(s) exist. Once windows are migrated that file stops being the "
            "live roster, and this push REVERTS every dir to it. Pass --from <slug> to sync from a "
            "migrated dir's roster instead.\n"
        )

    try:
        roster = json.loads(src.read_text()).get("mcpServers")
    except (OSError, ValueError) as e:
        sys.stderr.write(f"claude_rotate: cannot read {src} ({e})\n")
        return 1
    if not isinstance(roster, dict):
        sys.stderr.write(f"claude_rotate: {src} has no 'mcpServers' object — nothing to sync\n")
        return 1

    shared: dict[str, bytes] = {}
    if include_settings:
        for name in _SHARED_FILE_COPIES:
            try:
                shared[name] = (CLAUDE_DIR / name).read_bytes()
            except OSError as e:
                sys.stderr.write(f"claude_rotate: cannot read the canonical {name} ({e})\n")
                return 1

    failures = 0
    for d in dirs:
        reason = _merge_roster_once(d / ".claude.json", roster)
        if reason is not None:
            sys.stderr.write(f"  SKIP {d.name}: {reason}\n")
            failures += 1
            continue
        pushed = []
        for name, body in shared.items():
            try:
                _replace_file(d / name, body, mode=0o644)  # shared config, not a secret
                pushed.append(name)
            except OSError as e:
                sys.stderr.write(f"  {d.name}: {name} not pushed ({e})\n")
                failures += 1
        extra = (" + " + ", ".join(pushed)) if pushed else ""
        print(f"  {d.name}: {len(roster)} MCP servers{extra}")
    return 1 if failures else 0


def _is_claude_process(argv: list[str]) -> bool:
    """True iff *argv* is a Claude Code CLI process.

    Keyed on argv[0]'s BASENAME, never on a substring of the whole command line. Measured on this
    box: a `"claude" in cmdline` test matched 42 processes of which only 14 were the CLI — the rest
    were `bash -c` wrappers, hook scripts, `uvicorn` and `node` servers that merely carry "claude"
    in a path. A monitor built on that would warn about its own hooks forever.
    """
    if not argv:
        return False
    if os.path.basename(argv[0]) == "claude":
        return True
    # `node /path/to/claude` / `bun …` launcher form.
    return (
        len(argv) > 1
        and os.path.basename(argv[0]) in ("node", "bun")
        and os.path.basename(argv[1]) == "claude"
    )


def _has_config_dir(environ: bytes) -> bool:
    """True iff this process's environment binds it to a fleet dir.

    The value must be NON-EMPTY. ``CLAUDE_CONFIG_DIR=`` (exported empty — how a shell "unsets" it in
    place) makes the CLI fall back to the shared ``~/.claude``, so counting the bare NAME as
    isolated would report a shared-bound session as migrated: an UNDERCOUNT, i.e. the monitor going
    quiet exactly when a window silently rejoined.
    """
    prefix = b"CLAUDE_CONFIG_DIR="
    return any(
        var.startswith(prefix) and var[len(prefix) :].strip() for var in environ.split(b"\0")
    )


def _shared_bound_sessions() -> int | None:
    """How many LIVE claude sessions are still bound to the SHARED ``~/.claude``, or ``None`` when
    that cannot be determined.

    This is the "silent rejoin" detector. It replaces an open-handle count (``fuser``/``lsof``),
    which measured the wrong thing: the CLI opens ``.credentials.json``, reads it and closes it, so
    the handle count is ~always 0 — measured 0 with 46 live sessions on this box, i.e. a detector
    that could never fire. What actually identifies the condition is a running claude whose
    environment carries no ``CLAUDE_CONFIG_DIR``: that process IS on the shared chain.

    Reads ``/proc/<pid>/environ``, which is readable for same-uid processes — exactly the ones that
    could be sharing this user's chain. FAIL-SOFT: ``None`` when ``/proc`` is unusable or when
    claude processes were found but none could be inspected; a false ``0`` all-clear would be worse
    than no signal at all. Never raises — ``--status`` must survive it.
    """
    try:
        entries = [p for p in PROC_DIR.iterdir() if p.name.isdigit()]
    except OSError:
        return None
    matched = readable = shared = 0
    for proc in entries:
        try:
            raw = (proc / "cmdline").read_bytes()
        except OSError:
            continue  # the process exited, or is not ours to inspect
        argv = [a.decode("utf-8", "replace") for a in raw.split(b"\0") if a]
        if not _is_claude_process(argv):
            continue
        matched += 1
        try:
            environ = (proc / "environ").read_bytes()
        except OSError:
            continue  # a foreign-uid claude cannot be sharing OUR chain, and cannot be read anyway
        readable += 1
        if not _has_config_dir(environ):
            shared += 1
    if matched and not readable:
        return None  # found sessions, could inspect none → unknown, never a false all-clear
    return shared


def _shared_bound_max() -> int:
    try:
        return max(
            0, int(os.environ.get("CLAUDE_FLEET_OCCUPANCY_MAX") or _SHARED_BOUND_MAX_DEFAULT)
        )
    except ValueError:
        return _SHARED_BOUND_MAX_DEFAULT


def _fleet_warnings() -> list[str]:
    """The carrier-presence + occupancy WARNs shown by ``--status``.

    The architecture's load-bearing invariant — every mapped project carries BOTH env vars — fails
    OPEN and INVISIBLY: a project whose carrier went missing (a fresh git worktree, a hand-edit, a
    reverted file) just quietly rejoins the shared ``~/.claude`` chain and re-creates the relogin
    wave. A missing carrier must therefore be a NAMED alert. Never raises — it is decoration on a
    status banner that has to print regardless.
    """
    warns: list[str] = []
    try:
        table = _load_assignments(strict=False)
    except _STATE_DIR_ERRORS:
        return warns
    if not table:
        # No fleet yet (pre-migration, or a box that never gets one): EVERY process is legitimately
        # on the shared chain, so probing occupancy here would fire a WARN on normal operation every
        # single run — and a monitor that cries wolf for weeks is not read on the day it is right.
        return warns
    for slug, row in sorted(table.items()):
        project = row.get("project") if isinstance(row, dict) else None
        if not project:
            continue  # hub role dirs + headless callers carry the env on the launch line, not a file
        carrier = _carrier_path(Path(str(project)))
        try:
            data = json.loads(carrier.read_text())
        except FileNotFoundError:
            warns.append(
                f"⚠ {slug}: carrier MISSING — {carrier} "
                "(that project's sessions rejoin the shared ~/.claude chain)"
            )
            continue
        except (OSError, ValueError) as e:
            warns.append(f"⚠ {slug}: carrier unreadable — {carrier} ({e})")
            continue
        env = data.get("env") if isinstance(data, dict) else None
        missing = [k for k in _CARRIER_ENV_KEYS if not (isinstance(env, dict) and env.get(k))]
        if missing:
            warns.append(f"⚠ {slug}: carrier {carrier} lacks {', '.join(missing)}")
    count = _shared_bound_sessions()
    cap = _shared_bound_max()
    if count is not None and count > cap:
        warns.append(
            f"⚠ occupancy: {count} live claude sessions carry no CLAUDE_CONFIG_DIR (>{cap}) — "
            f"they share {ACTIVE_CREDS}; unmapped windows have silently rejoined the shared chain"
        )
    return warns


def _rotate_state_dir() -> Path:
    d = Path(os.environ.get("ROTATE_STATE_DIR") or Path.home() / ".claude" / "state")
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    return d


def _switch_paused() -> bool:
    """Operator pause marker (``--pause-switch``): while present the tick NEVER installs a
    pair. Set it when the successor pool is unverified or known-dead (2026-08-15: after a
    chain loss, an auto-switch would have installed a consumed pair box-wide — killing every
    session at once). The tick keeps ticking: telemetry, keep-warm and the DRAIN warning all
    stay armed; only the install is withheld."""
    return (_rotate_state_dir() / "switch-paused").is_file()


def _drain_stamp_path() -> Path:
    """Where the 24h DRAIN dedupe stamp lives. Falls back to the temp dir when the rotate state dir
    is unreachable (``_rotate_state_dir`` raising): the drain warning must still be deduped during
    a state-dir outage, or the tick re-broadcasts the same "reach a checkpoint NOW" mail + telegram
    every 5 minutes for the length of it. A temp-dir stamp is weaker (a reboot clears it) — one
    extra broadcast, versus hundreds."""
    try:
        return _rotate_state_dir() / "drain-stamp"
    except _STATE_DIR_ERRORS:
        return Path(tempfile.gettempdir()) / "claude-drain-stamp"


# The ledger is an audit trail, never a crash source — an escape from these readers aborts the tick
# mid-flight, taking the drain broadcast with it.
def _ledger_append(event: dict) -> None:
    try:
        with (_rotate_state_dir() / "rotate-ledger.jsonl").open("a") as fh:
            fh.write(json.dumps(event) + "\n")
    except _STATE_DIR_ERRORS:
        pass


def _last_switch_ts(event: str = "switch") -> tuple[float | None, bool]:
    """When the last install happened, for the tick's dwell guard — as ``(timestamp, degraded)``.

    *event* selects the ledger record the dwell keys on: ``"switch"`` (the legacy credential
    install) or ``"flip"`` (the fleet's active-pointer flip) — same guard, same fail-closed
    contract, per-event clocks so a legacy install never holds a fleet flip or vice versa.

    ``(None, False)`` means "no switch on record" and lets the tick install: it is only ever
    returned when the ledger legitimately has no switch entry (a fresh box has no ledger at all
    and must still be able to make its first switch).

    A ledger that cannot be READ — unreachable/corrupt bytes, a permission error, or a well-formed
    switch record whose ``ts`` is not a number — fails **CLOSED**: ``(now, True)``, which reads as
    "just switched" and holds the guard. Answering "no recent switch" to a question we cannot
    answer lets the tick install a fresh pair on every 5-minute run for as long as the fault lasts.
    ``degraded=True`` is the second half of that contract: the hold is a GUESS, so the caller must
    NOT treat it as a healthy dwell — the tick routes it into the DRAIN broadcast, because nobody
    is installing while the live account burns toward the wall."""
    try:
        lines = (_rotate_state_dir() / "rotate-ledger.jsonl").read_text().splitlines()
    except FileNotFoundError:
        return None, False  # no ledger yet = nothing has ever switched (fresh box, not a fault)
    except _STATE_DIR_ERRORS:
        sys.stderr.write(
            "claude_rotate: rotate-ledger unreadable/corrupt — dwell guard failing CLOSED "
            "(holding; no account installed)\n"
        )
        return _now(), True
    for line in reversed(lines):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("event") == event:
            ts = e.get("ts")
            if isinstance(ts, (int, float)) and float(ts) <= _now() + _CLOCK_SKEW_TOLERANCE_S:
                return float(ts), False
            # Two unknowns, one verdict. A non-numeric ts cannot be compared at all; a ts stamped
            # in the FUTURE makes ``now - last`` negative, which reads as "within dwell" for as
            # long as the skew lasts — a silent hold with no drain (WSL suspend/resume moves this
            # box's clock). Neither may read as "no recent switch".
            sys.stderr.write(
                f"claude_rotate: rotate-ledger {event} record has an unusable ts "
                f"({ts!r} — non-numeric or clock-skewed into the future) — dwell guard failing "
                "CLOSED (holding; no account installed)\n"
            )
            return _now(), True
    return None, False


def _mailbox_repos() -> list[str]:
    """Repos that can SURFACE mail (mail.py:157 rule) — enumerated, never hardcoded. Scans
    ``OPT_DIR`` (== /opt in production) so tests have ONE seam, shared with the fleet
    drain-mail routing's existence checks."""
    out = []
    try:
        entries = sorted(OPT_DIR.iterdir())
    except OSError:
        return out
    for d in entries:
        try:
            if (d / ".claude" / "hooks" / "mail_notify.py").is_file():
                out.append(d.name)
        except OSError:
            continue
    return out


def _drain_mail(repos: list[str], msg: str) -> None:
    mail = Path("/opt/fabrik/scripts/mail.py")
    if not mail.is_file():
        return
    for repo in repos:
        try:
            # fire-and-forget (closer #8): ~49 serial 30s-timeout sends could hold the tick
            # flock for ~25 min at exactly the draining moment; Popen detaches each send
            proc = subprocess.Popen(
                [
                    sys.executable,
                    str(mail),
                    "send",
                    "--to",
                    repo,
                    "--from",
                    "fabrik",
                    "--kind",
                    "finding",
                    "--ack",
                    "no",
                    "--broadcast",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            if proc.stdin is not None:
                proc.stdin.write(msg)
                proc.stdin.close()
        except (OSError, subprocess.SubprocessError):
            continue  # one refused mailbox must not stop the broadcast


def _tick_telegram(msg: str) -> None:
    sound = Path.home() / ".claude" / "bin" / "claude-sound.sh"
    if not sound.is_file():
        return
    try:
        subprocess.run(
            ["bash", str(sound), "mesh-notify", "quota-rotation", "/opt/fabrik", msg],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _tick_switch(name: str) -> bool:
    """Install `name`. Closer #3: capture the OUTGOING account's live credentials into its
    own store FIRST — drift-check is hourly, and an hour-stale snapshot holds a superseded
    refresh token (the 2026-08-10 14:37 class, which a 5-minute automatic trigger would
    otherwise replay). Closer #7: the under-lock selector re-validates FITNESS (fresh
    telemetry: valid + un-walled), not just the path — 'TOCTOU-free' must cover the pick."""
    if _cmd_capture_current() != 0:
        sys.stderr.write(
            "claude_rotate: tick pre-switch capture failed — switch aborted"
            " (a stale outgoing snapshot must not be left behind)\n"
        )
        return False

    def _selector() -> Path | None:
        hit = next((a for a in _list_accounts() if a.name == name), None)
        if hit is None:
            return None
        row = _account_status(hit)
        if not row.get("valid") or _walled(row):
            sys.stderr.write(f"claude_rotate: {name} no longer fit at install time — abort\n")
            return None
        return hit

    return _activate_snapshot(selector=_selector) is not None


def _file_refreshed_credentials(
    store: Path, payload: dict, verified_email: str | None, provenance: bool = False
) -> bool:
    """Atomically install a refreshed credential pair into ITS OWN store — identity-gated
    (the 2026-08-13 mis-filing class must be impossible here): the verified email's local
    part must match the store's name prefix, OR ``provenance=True`` (the pair came from this
    store's own refresh token — OAuth construction proves ownership; used only when the
    verification probe is unreachable). Under ROTATE_LOCK (closer #9 — every sibling
    credential writer holds it); backup to .prev, unique-tmp+rename install."""
    if not provenance:
        local = (verified_email or "").split("@", 1)[0].lower()
        if not local or not store.name.lower().startswith(local + "-"):
            sys.stderr.write(
                f"claude_rotate: refresh NOT filed — {verified_email!r} does not"
                f" match store {store.name}\n"
            )
            return False
    dst = store / ".credentials.json"
    try:
        lock_fd = os.open(str(ROTATE_LOCK), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
    except OSError:
        lock_fd = None  # best-effort: os.replace still keeps readers atomic
    try:
        if dst.exists():
            _secure_write(store / ".credentials.json.prev", dst.read_bytes())
        tmp = store / f".credentials.json.tmp{os.getpid()}.{time.monotonic_ns()}"
        _secure_write(tmp, json.dumps(payload).encode())
        os.replace(tmp, dst)
        return True
    except OSError as e:
        sys.stderr.write(f"claude_rotate: refresh filing failed for {store.name}: {e}\n")
        return False
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
            except OSError:
                pass


def _keepwarm_refresh(store: Path) -> bool:
    """BLOCKED BY THE ENDPOINT (live-probed 2026-08-13): a script-side refresh POST to
    /v1/oauth/token returns HTTP 403 (Cloudflare 1010) on BOTH platform.claude.com and
    console.anthropic.com — the grant is issued only to the CLI's own client. Defeating that
    check is out of bounds, so keep-warm-by-HTTP does not exist.

    What keeps accounts warm instead (no code needed): USE. The CLI refreshes the LIVE
    credentials in place, and `--drift-check` captures them hourly — so any account the
    rotation visits stays warm by construction, and this pool rotates every few days against
    a ~30-day refresh-token life. A store parked longer than that needs one rotate-through
    (switch to it, let a session use it, switch back) — an operator/cron action, not a
    silent token spend. Returns False always; the tick logs it once per parked store."""
    sys.stderr.write(
        f"claude_rotate: keep-warm unavailable for {store.name} — the token"
        " grant is CLI-only (403/1010); rotation-through is the warm path\n"
    )
    return False


def _email_for_token(token: str) -> str | None:
    """The account email a specific token belongs to (the identity authority, applied to a
    token that is NOT the live one — the touch path's verification seam)."""
    prof = _oauth_get("profile", token)
    email = ((prof or {}).get("account") or {}).get("email")
    return email if isinstance(email, str) and "@" in email else None


def _touch_run_cli(cfg_dir: Path, store: Path) -> bool:
    """Run one trivial `claude -p` against an ISOLATED config dir so the official client
    performs its own token refresh. Never touches the live credentials file — the account
    being touched is parked, and live sessions keep using ACTIVE_CREDS untouched."""
    env = os.environ.copy()
    env["CLAUDE_CONFIG_DIR"] = str(cfg_dir)
    env["CLAUDE_MESH_HEADLESS"] = "1"
    env["CLAUDE_SOUND_NO_REVIVE"] = "1"
    env.setdefault("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")
    _with_claude_on_path(env)  # cron PATH lacks ~/.local/bin → bare spawn would FileNotFoundError
    try:
        p = subprocess.run(
            ["claude", "-p", "ping"],
            env=env,
            capture_output=True,
            text=True,
            timeout=int(os.environ.get("TOUCH_TIMEOUT", "150")),
        )
        return p.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _cmd_touch(only: str | None = None) -> int:
    """Keep PARKED accounts' refresh chains alive (operator ask 2026-08-14: never log in
    again). Refresh tokens are single-use but ~30-day-lived, and the CLI rotates them on
    use — so one trivial call per account per week keeps every chain current WITHOUT any
    login, email automation, or impact on live sessions. Isolated per account via
    CLAUDE_CONFIG_DIR; a refreshed pair is identity-verified before it is filed."""
    active = _active_account()
    live_name = active.name if active is not None else None
    touched = 0
    for store in _list_accounts():
        if store.name == live_name:
            continue  # the live account refreshes naturally on every real turn
        if only is not None and not store.name.lower().startswith(only.lower()):
            continue
        src = store / ".credentials.json"
        if not src.is_file():
            continue
        before = src.read_bytes()
        tmpdir = Path(tempfile.mkdtemp(prefix=f"claude-touch-{store.name[:12]}-"))
        try:
            os.chmod(tmpdir, 0o700)
            _secure_write(tmpdir / ".credentials.json", before)
            cj = store / ".claude.json"
            if cj.is_file():
                _secure_write(tmpdir / ".claude.json", cj.read_bytes())
            _touch_run_cli(tmpdir, store)
            after_path = tmpdir / ".credentials.json"
            after = after_path.read_bytes() if after_path.is_file() else before
            if after == before:
                print(f"touch: {store.name} — unchanged (chain already current)")
                continue
            try:
                payload = json.loads(after)
            except ValueError:
                print(f"touch: {store.name} — unreadable refreshed pair, not filed")
                continue
            tok = (payload.get("claudeAiOauth") or {}).get("accessToken")
            # STRUCTURAL LIVENESS GATE (live defect 2026-08-14): `claude -p` in an isolated
            # config can write a BLANKED pair (empty refreshToken, expiresAt=0) — filing it
            # destroys a perfectly good snapshot. A refreshed blob is fileable only when it
            # is alive: a non-empty refresh token AND a future access-token expiry. And the
            # identity must POSITIVELY verify — no provenance fallback here, because the
            # existing snapshot is still valid and doing nothing is always the safer branch.
            o = payload.get("claudeAiOauth") or {}
            exp_ms = o.get("expiresAt")
            alive = (
                bool(o.get("refreshToken"))
                and isinstance(exp_ms, (int, float))
                and (exp_ms / 1000.0) > _now()
            )
            if not alive:
                print(
                    f"touch: {store.name} — CLI returned a dead/blanked pair, keeping the"
                    " existing snapshot"
                )
                continue
            email = _email_for_token(tok) if tok else None
            if not email:
                print(f"touch: {store.name} — refreshed pair unverifiable, not filed")
                continue
            ok = _file_refreshed_credentials(store, payload, verified_email=email)
            if ok:
                touched += 1
                print(f"touch: {store.name} — refreshed and filed")
                _ledger_append({"event": "touch", "ts": _now(), "store": store.name})
        finally:
            try:
                for f in tmpdir.iterdir():
                    f.unlink()
                tmpdir.rmdir()
            except OSError:
                pass
    print(f"touch: done — {touched} account(s) refreshed")
    return 0


def _cmd_tick() -> int:
    """The 5-minute rotation daemon tick. Always exits 0 — ENFORCED by the outer guard
    (closer #11), not just documented. Every decision is one printed line.

    Fleet mode dispatches to :func:`_fleet_tick_inner` BEFORE :func:`_tick_inner` ever runs:
    the legacy tick is single-live-account-shaped (``live_name`` from ``_active_account()``
    matches no fleet slug) and could reach ``_tick_switch`` — the fleet branch must be
    structurally unable to install anything."""
    try:
        fleet_dirs = _fleet_dirs()
        if fleet_dirs:
            return _fleet_tick_inner(fleet_dirs)
        return _tick_inner()
    except Exception as e:  # noqa: BLE001 — cron-hosted: a broken tick must never look
        #                     like a broken cron; the class+message is the diagnostic
        print(f"tick: INTERNAL ERROR {type(e).__name__}: {e}")
        return 0


def _env_float(name: str, default: float) -> float:
    """An env override as a float, falling back to *default* on anything unusable.

    NON-FINITE values are rejected LOUDLY: ``nan`` compares False against everything, so
    ``ROTATE_DRAIN_THRESHOLD=nan`` disables the DRAIN warning permanently and invisibly — the
    threshold clamp cannot even fire to report it — and ``inf`` does the same by never being
    reached. A silently-disabled warning is the failure mode this whole ticket exists to prevent."""
    try:
        val = float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    if not math.isfinite(val):
        sys.stderr.write(
            f"claude_rotate: {name} is not a finite number ({val}) — using the default {default}\n"
        )
        return default
    return val


def _rotate_threshold() -> float:
    """The flip-away threshold on either quota window — ONE source for every call site.

    Default **95** (operator rule 2026-09-03, restated twice after the wall was hit anyway: "when
    we see 95% at these checks we need to switch next account"). It was briefly 98 the same day;
    98 lost, because the gap between two checks is BURSTY — measured over 34 real inter-tick gaps:
    median 4 points, p90 10, max 16 — so an account read at 93 could be past 100 before the next
    look. 95 restores the margin a burst needs. `ROTATE_THRESHOLD` overrides.

    The weekly leg is governed by the account's ``caps.json`` cap when one exists (the cap IS the
    operator's weekly rule) and by this threshold otherwise — see ``_fleet_flip_leg``."""
    return _env_float("ROTATE_THRESHOLD", 95.0)


def _tick_inner() -> int:
    threshold = _rotate_threshold()
    drain_thr = _env_float("ROTATE_DRAIN_THRESHOLD", 85.0)
    if drain_thr > threshold:
        # The warning must never sit ABOVE the action it warns about: between the two there is a
        # band where the tick refuses to switch (paused / no successor) and also refuses to warn,
        # printing a hold line and then ledgering "ok" — a silent burn to the wall.
        sys.stderr.write(
            f"claude_rotate: ROTATE_DRAIN_THRESHOLD ({drain_thr:.0f}) is above ROTATE_THRESHOLD "
            f"({threshold:.0f}) — clamping the drain warning to the switch threshold\n"
        )
        drain_thr = threshold
    dwell_s = _env_float("ROTATE_DWELL_MIN", 30.0) * 60
    now = _now()
    rows, live_name = _collect_statuses()
    try:
        # keep-warm runs for EVERY tick outcome (closer #12): no-live and dwell-hold are
        # exactly the degraded states where parked snapshots must not age out
        live = next((r for r in rows if r["name"] == live_name), None)
        if live is None or not live.get("valid"):
            print("tick: live account unresolvable/invalid — no action")
            _ledger_append({"event": "tick", "ts": now, "verdict": "no-live"})
            return 0
        hot = max(
            (live.get("five_hour") or {}).get("utilization", 0.0),
            (live.get("seven_day") or {}).get("utilization", 0.0),
        )
        successor = _pick_successor(rows, live_name, now)
        pause = _pause_state()  # soft: an unreadable state dir must not kill the DRAIN broadcast
        if successor is not None and pause is not None:
            # successor=None routes ≥drain_thr ticks into the DRAIN broadcast, so a paused
            # pool warns before the wall instead of silently hitting it
            why = "operator marker" if pause == _PAUSE_MARKER else "pause state unreadable"
            print(f"tick: auto-switch PAUSED ({why}) — {successor} not installed")
            successor = None
        switch_failed = False
        if hot >= threshold and successor is not None:
            last, degraded = _last_switch_ts()
            # `degraded` withholds STRUCTURALLY — never via the dwell arithmetic below. The
            # fail-closed timestamp is "now", so `(now - last) < dwell_s` only happens to be true
            # because the two clock reads differ by microseconds: with ROTATE_DWELL_MIN=0 that
            # comparison is False and the tick would install off an unreadable ledger anyway.
            if degraded:
                # A fail-closed hold is a guess, not a real recent switch: no install happened and
                # none will while the ledger is unreadable, so the account burns to the wall
                # unannounced unless this reaches the DRAIN broadcast. Clearing `successor` is what
                # carries it there — the same carrier the paused/no-successor case uses. The
                # verdict is its OWN string: post-hoc, a fail-closed hold and a genuine dwell hold
                # are different incidents.
                print("tick: dwell guard fail-closed (unusable ledger) — holding, routing to DRAIN")
                _ledger_append({"event": "tick", "ts": now, "verdict": "dwell-hold-degraded"})
                successor = None
            elif last is not None and (now - last) < dwell_s:
                print(f"tick: {hot:.0f}% >= {threshold:.0f}% but within dwell — holding")
                _ledger_append({"event": "tick", "ts": now, "verdict": "dwell-hold"})
                return 0
            elif _tick_switch(successor):
                _ledger_append(
                    {
                        "event": "switch",
                        "ts": now,
                        "to": successor,
                        "from": live_name,
                        "at_pct": hot,
                    }
                )
                _tick_telegram(f"rotated {live_name} -> {successor} at {hot:.0f}%")
                print(f"tick: switched {live_name} -> {successor} at {hot:.0f}%")
                return 0
            else:
                # closer #4: a failed switch must be LOUD and must not shadow the drain path —
                # "successor exists but cannot install" burns silently to 100% otherwise. Reached
                # only when `_tick_switch` above actually ran and returned False: the elif chain
                # excludes both hold arms, so a held tick never reports a switch failure.
                switch_failed = True
                _tick_telegram(
                    f"quota switch to {successor} FAILED at {hot:.0f}% — pool may be draining"
                )
                print(f"tick: switch to {successor} FAILED")
                _ledger_append({"event": "tick", "ts": now, "verdict": "switch-failed"})
        if hot >= drain_thr and (successor is None or switch_failed):
            # The stamp DEBOUNCES the broadcast to once per 24h. An unreachable state dir must
            # never abort the drain warning (it used to raise straight into _cmd_tick's blanket
            # except, losing the mail AND the telegram) — and must not lose the dedupe either, or
            # the drain re-broadcasts on every 5-minute tick for the whole outage.
            stamp = _drain_stamp_path()
            try:
                age = now - stamp.stat().st_mtime
            except OSError:
                age = None
            if age is not None and age < -_CLOCK_SKEW_TOLERANCE_S:
                # Same skew clamp as _last_switch_ts / the fleet advisory stamp: a stamp mtime
                # in the FUTURE must read EXPIRED, never "suppressed until the clock catches up".
                age = None
            if age is None or age >= 86400:
                resets = [
                    w.get("resets_at_epoch")
                    for r in rows
                    for w in ((r.get("five_hour"), r.get("seven_day")) if r.get("valid") else ())
                    if w and w.get("resets_at_epoch")
                ]
                revive = min(resets) if resets else None
                from datetime import datetime

                revive_s = (
                    datetime.fromtimestamp(revive).strftime("%a %H:%M") if revive else "unknown"
                )
                msg = (
                    f"QUOTA DRAIN: pool exhaustion approaching ({hot:.0f}% on the last "
                    f"eligible account, no installable sibling). Reach a commit-and-push "
                    f"checkpoint NOW; do not start new phases. Work revives at {revive_s}."
                )
                _drain_mail(_mailbox_repos(), "quota drain warning\n\n" + msg)
                _tick_telegram(msg)
                try:
                    stamp.touch()
                    os.utime(stamp, (now, now))
                except OSError:
                    pass
                _ledger_append({"event": "drain", "ts": now, "at_pct": hot})
                print(f"tick: DRAIN broadcast at {hot:.0f}%")
            else:
                print("tick: drain condition holds but suppressed (stamp)")
        elif not switch_failed:
            print(f"tick: ok — live {live_name} at {hot:.0f}%")
            _ledger_append({"event": "tick", "ts": now, "verdict": "ok", "pct": hot})
        return 0
    finally:
        _keepwarm_pass(rows, live_name, now)
        _ledger_rotate()


def _keepwarm_pass(rows: list[dict], live_name: str | None, now: float) -> None:
    for r in rows:
        if r["name"] == live_name or not r.get("valid"):
            continue
        exp = r.get("refresh_expires_at_epoch")
        if exp is not None and (exp - now) < 48 * 3600 and r.get("store"):
            if _keepwarm_refresh(Path(r["store"])):
                print(f"tick: kept warm {r['name']}")
                _ledger_append({"event": "keepwarm", "ts": now, "store": r["name"]})


def _ledger_rotate(cap_bytes: int = 1_000_000) -> None:
    """Bound the append-only ledger (closer #15): keep the newest half when it crosses the
    cap — the dwell scan only ever needs the recent tail."""
    try:
        led = _rotate_state_dir() / "rotate-ledger.jsonl"
        if led.stat().st_size > cap_bytes:
            lines = led.read_text().splitlines(keepends=True)
            led.write_text("".join(lines[len(lines) // 2 :]))
    except _STATE_DIR_ERRORS:
        pass  # runs in _tick_inner's finally — an escape here would mask the tick's own outcome


# ── fleet mode: per-ACCOUNT dirs + ONE `active` pointer, flipped by quota headroom ────────────
# Feature-detected: ≥1 scaffolded dir under _fleet_root() flips --status and --tick into the
# fleet view; an empty fleet root leaves the legacy manager-accounts machinery untouched (the
# successor plan retires it — never this module). The fleet branches are REWRITTEN, not reused:
# _tick_inner is single-live-account-shaped (live_name from _active_account() matches no fleet
# slug), so fleet mode must never reach it. The rollout model (operator redesign 2026-08-15):
# each ACCOUNT owns exactly one fleet dir (slug = account: ob, can, sarp, mob), logged in ONCE —
# its OAuth chain never moves again; every project window follows the single `active` symlink at
# <fleet-root>/active, and the tick FLIPS that pointer to the account with the most quota
# headroom when the active one crosses ROTATE_THRESHOLD. The load-bearing invariant that
# replaces the retired file-swap rotation: a flip renames a SYMLINK — it moves ZERO credential
# bytes (asserted structurally + behaviorally in tests/test_claude_fleet.py). Credential
# HANDLING contract: this section reads a dir's access token in memory for the profile/usage
# probes (the same never-logged pattern _account_status uses) and checks the credential file's
# MTIME — it never writes, copies, or relocates a credential byte, and the keepalive staleness
# gate is mtime-only.

# The reserved name of the active-pointer symlink under the fleet root. Never a dir slug.
_ACTIVE_POINTER_NAME: Final = "active"
# A refresh chain inside this window of its expiry gets a --status/tick warning: the keepalive
# cadence is 7 days, so a chain seen under 5 days from lapse means the keepalive net has already
# failed for it and an operator nudge is the remaining defense.
_CHAIN_EXPIRY_WARN_S = 5 * 86400
# The identity-mismatch net's live leg: ONE profile probe per pinned account per this interval
# (~24/account/day, not one per 5-min tick). Detection latency ≤1h is deliberate — the
# mid-refresh race's aftermath and a wrong-dir login both PERSIST until fixed, so a bounded
# probe finds them; an unbounded one only finds them faster while multiplying probe volume ×12.
_IDENTITY_PROBE_INTERVAL_S = 3600.0


def _fleet_dirs() -> list[Path]:
    """Scaffolded fleet dirs (sorted). [] when the root is absent/unreadable — which IS the
    feature detection: no dirs, no fleet mode. SYMLINKS are excluded: the `active` pointer is
    itself a dir-symlink under the root, and counting it would double-count its target account
    (a phantom pending-login row on --status, a double keepalive ping, an off-by-one dir count)."""
    try:
        return sorted(d for d in _fleet_root().iterdir() if d.is_dir() and not d.is_symlink())
    except OSError:
        return []


def _active_pointer_path() -> Path:
    """The ONE pointer every session follows: ``<fleet-root>/active``, a symlink to the active
    account's dir. Sessions bind ``CLAUDE_CONFIG_DIR`` to this path, so repointing the link
    re-homes the whole fleet in one rename — no session restart, no credential movement."""
    return _fleet_root() / _ACTIVE_POINTER_NAME


def _resolve_active() -> str | None:
    """The slug the active pointer currently names, or None (no pointer, dangling, or not a
    symlink) — the tick treats None as "no active account" and flips to the best immediately."""
    ptr = _active_pointer_path()
    try:
        if not ptr.is_symlink():
            return None
        dest = ptr.resolve(strict=True)  # FileNotFoundError (an OSError) on a dangling link
    except OSError:
        return None
    return dest.name if dest.is_dir() else None


def _chain_stale_reason(dest: Path) -> str | None:
    """Why *dest*'s chain must NOT become the fleet's active pointer, or None if it is live.

    The flip-path liveness gate (F-P1, review round 1 — probe-proven gap): file PRESENCE is not
    usability, and one dead pointer is a fleet-WIDE auth outage (every session follows it) — the
    2026-08-10 dead-credential incident class, amplified. Delegates to the module's own
    :func:`_stale_snapshot_reason` (expired/absent refresh token, missing expiry metadata;
    ``CLAUDE_ROTATE_ALLOW_STALE=1`` honored), clock-pinned to ``_now()``, plus a token-presence
    screen for the unparseable-blob shapes that guard deliberately passes. In-memory read via
    the sanctioned reader pattern; never emits token bytes."""
    try:
        blob = (dest / ".credentials.json").read_bytes()  # ONE read; both checks share it
    except OSError:
        return "credentials unreadable"
    if _access_token_from(blob) is None:
        return "credentials unreadable or carry no access token"
    return _stale_snapshot_reason(blob, now=_now())


def _refresh_expiry_epoch(creds: Path) -> float | None:
    """``claudeAiOauth.refreshTokenExpiresAt`` as epoch seconds, or None. The --status/tick
    chain-health signal (a dying chain must be visible BEFORE it is a flip candidate). Same
    in-memory read `_account_status` uses; never emits token bytes."""
    try:
        exp = (json.loads(creds.read_bytes()).get("claudeAiOauth") or {}).get(
            "refreshTokenExpiresAt"
        )
    except (OSError, ValueError, AttributeError, TypeError):
        return None
    return float(exp) / 1000.0 if isinstance(exp, (int, float)) and exp > 0 else None


def _identity_probe_stamp(slug: str) -> Path:
    """The identity-probe verdict stamp for ONE fleet dir, keyed by SLUG (F-P9): verdicts
    belong to dirs, so a fresh pin on a sibling dir can never mask another dir's unresolved
    mismatch, and slugs are ``_SLUG_RE``-validated kebab — the sanitize regex below is the
    identity function on them (collision-free by construction; it survives only as defense
    for hand-made dirs). Same temp-dir fallback contract as the advisory stamp — the budget
    must survive a state-dir outage without spamming probes."""
    safe = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")
    try:
        return _rotate_state_dir() / f"fleet-idcheck-{safe}"
    except _STATE_DIR_ERRORS:
        return Path(tempfile.gettempdir()) / f"claude-fleet-idcheck-{safe}"


def _identity_probe_due(slugs: list[str], now: float) -> bool:
    """True when the ACCOUNT's hourly identity-probe budget allows a new probe: verdicts are
    stored per SLUG, but the cadence is per account — ANY of the account's dir stamps younger
    than ``_IDENTITY_PROBE_INTERVAL_S`` (a fresh probe or a fresh pin on a sibling) holds the
    budget. Missing/unreadable stamps never hold it; a stamp mtime AHEAD of now beyond
    ``_CLOCK_SKEW_TOLERANCE_S`` is INVALID and never holds it either (the advisory-stamp
    convention — clock skew must never silence a detector)."""
    for slug in slugs:
        try:
            age = now - _identity_probe_stamp(slug).stat().st_mtime
        except OSError:
            continue
        if age < -_CLOCK_SKEW_TOLERANCE_S:
            continue  # future-dated stamp = invalid: it cannot hold the budget
        if age < _IDENTITY_PROBE_INTERVAL_S:
            return False
    return True


def _identity_probe_record(slug: str, probed: str | None, now: float) -> None:
    """Record a COMPLETED identity probe for *slug*'s dir: *probed* is the email the dir's
    token answered with (STORED in the stamp, so the verdict stays visible on every
    --status/tick between hourly probes — a mismatch is sticky until a later probe of THAT
    dir re-verifies), or None for a 200-with-no-email shape change (budget honored via mtime,
    stored verdict unchanged). A transport FAILURE must never reach here — it retries next
    tick, neither silencing nor spamming the net. Best-effort: a lost stamp write costs one
    extra probe, never the pass."""
    stamp = _identity_probe_stamp(slug)
    try:
        if probed is not None:
            stamp.write_text(probed + "\n")
        else:
            stamp.touch()
        os.utime(stamp, (now, now))
    except OSError:
        pass


def _identity_probe_result(slug: str) -> str | None:
    """The last recorded probe answer for *slug*'s dir, or None (no completed probe / no
    usable verdict). Read UNCONDITIONALLY every pass for every pinned dir (F-P7) — reporting
    a stored verdict is never gated by token freshness: the likely aftermath of a corrupted
    dir is that it goes IDLE, and an idle dir's mismatch must keep warning, not vanish 8h
    later while the stamp still holds it."""
    try:
        val = _identity_probe_stamp(slug).read_text().strip()
    except _STATE_DIR_ERRORS:
        return None
    return val if "@" in val else None


def _flip_active(
    slug: str, *, manual: bool = False, ignore_dwell: bool = False, at_pct: float | None = None
) -> bool:
    """Repoint ``active`` at *slug*'s fleet dir — the ONLY rotation act in fleet mode.

    A flip moves ZERO credential bytes: it creates a temp symlink beside the pointer and
    ``os.replace``s it over — atomic, so ``active`` always resolves (old target or new, never
    absent). POSIX ``rename(2)`` operates on the LINK, not through it — os.replace atomically
    replaces a directory-symlink with a symlink (probed 2026-08-15, pinned by
    test_rename_replaces_a_directory_symlink; the file-symlink twin is T02a's write-through
    probe). Never unlink-then-symlink: that opens a window where every session's config dir is
    missing.

    Refusals (all fail-soft, stderr names the fix, pointer untouched):
    - *slug* has no ``.credentials.json`` — the fleet is never pointed at an empty chain;
    - *slug*'s chain fails the LIVENESS gate (:func:`_chain_stale_reason` — expired/absent
      refresh token, unprovable expiry): UNCONDITIONAL, manual included — a manual flip to a
      dead chain is never right; the revival path is ONE /login in that dir;
    - the operator's pause marker is set, or the pause state is unreadable (fail-closed) —
      unless *manual* (``--switch`` is the deliberate escape hatch, same as legacy);
    - within the 30-min dwell of the last flip (``ROTATE_DWELL_MIN``, ledger-timed with the
      ``_CLOCK_SKEW_TOLERANCE_S`` clamp; unreadable ledger fails CLOSED) — unless *manual* or
      *ignore_dwell* (the missing/dangling-pointer repair, where holding means fleet outage —
      and, since 2026-09-03, EVERY trip flip of the tick's flip leg: a trip is a wall, never churn).

    Every completed flip is ledgered ({"event": "flip", ts, from, to, at_pct}) — the dwell
    clock and the audit trail. Flipping to the already-active slug is an idempotent no-op
    success (no ledger churn) — checked BEFORE the liveness gate, since the pointer does not
    move: a decayed active chain is surfaced as a stderr WARNING, never a failure (F-P8).

    Accepted residuals (single-operator threat model):
    - Liveness-gate TOCTOU: the gate runs at flip time and the target's chain could die in the
      check→replace microseconds — unpreventable without a cross-process fs lock on the chain;
      the gate at flip time is the best available (same shape as the legacy installer's guard).
    - Mid-refresh race (detection net, not prevention): the CLI renews credentials
      read→HTTP→write THROUGH the pointer, so a flip landing inside that ~1-2s window makes the
      CLI write account A's rolled chain into account B's dir — B's chain is lost locally, one
      relogin owed. Rare (flips are dwell-limited) and undetectable at flip time from our side;
      the NET is the identity-mismatch check in the fleet rows (pinned identity vs the email
      the hourly bounded profile probe answers with — usage payloads carry no email, probed
      live 2026-08-15, so that probe IS the net's live leg; `_fleet_row_warnings` prints it),
      which also catches a manual login into the wrong dir. Detection latency is ≤1h by design
      (both faults persist until fixed). Recovery is ONE /login in the named dir, never a file
      copy."""
    root = _fleet_root()
    dest = root / slug
    if dest.is_symlink() or not dest.is_dir() or not _has_credentials(dest):
        sys.stderr.write(
            f"claude_rotate: refusing to flip active -> {slug}: not a credentialed fleet dir "
            "(the pointer is never aimed at an empty/absent chain — ONE /login there first)\n"
        )
        return False
    if _resolve_active() == slug:
        # F-P8: the idempotent no-op comes BEFORE the liveness gate — the pointer does not
        # move, so there is nothing to gate; failing here would break the documented
        # "self-flip is a no-op success" contract exactly when the active chain has decayed
        # in place. A decayed chain is SURFACED, not failed (--status already warns on it).
        stale = _chain_stale_reason(dest)
        if stale is not None:
            sys.stderr.write(
                f"claude_rotate: WARNING — {slug} is already active but its chain is dying: "
                f"{stale}. Revive it with ONE /login in that dir (the pointer is unchanged).\n"
            )
        return True  # no ledger churn: nothing moved
    stale = _chain_stale_reason(dest)
    if stale is not None:
        # UNCONDITIONAL — manual included: pointing the whole fleet at a dead chain is never
        # right, and the operator's real lever is a /login in that dir, not a flip to it.
        sys.stderr.write(
            f"claude_rotate: refusing to flip active -> {slug}: {stale} — one dead pointer is "
            "a fleet-wide auth outage; revive the chain with ONE /login in that dir first\n"
        )
        return False
    if not manual:
        paused = _pause_state()
        if paused is not None:
            if paused == _PAUSE_MARKER:
                sys.stderr.write(
                    "claude_rotate: flip PAUSED (switch-paused marker) — pointer unchanged "
                    "(override: --resume-switch, or --switch <slug> for a deliberate flip)\n"
                )
            else:
                sys.stderr.write(
                    "claude_rotate: pause-state unreadable — failing CLOSED, pointer unchanged "
                    "(fix the rotate state dir; --switch <slug> remains the manual lever)\n"
                )
            return False
        if not ignore_dwell:
            last, degraded = _last_switch_ts(event="flip")
            if degraded:
                sys.stderr.write(
                    "claude_rotate: flip dwell guard fail-closed (unusable ledger) — "
                    "pointer unchanged\n"
                )
                return False
            dwell_s = _env_float("ROTATE_DWELL_MIN", 30.0) * 60
            if last is not None and (_now() - last) < dwell_s:
                sys.stderr.write(
                    f"claude_rotate: flip to {slug} within dwell "
                    f"({dwell_s / 60:.0f}m of the last flip) — holding\n"
                )
                return False
    prev = _resolve_active()  # the no-op case already returned above; this is the ledger "from"
    ptr = _active_pointer_path()
    tmp = root / f".{_ACTIVE_POINTER_NAME}.tmp{os.getpid()}.{time.monotonic_ns():x}"
    try:
        os.symlink(slug, tmp)  # RELATIVE target — the fleet root stays relocatable
        os.replace(tmp, ptr)  # atomic over a file/dir-symlink or nothing; never a missing window
    except OSError as e:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        sys.stderr.write(f"claude_rotate: flip to {slug} failed ({e}) — pointer unchanged\n")
        return False
    _ledger_append(
        {
            "event": "flip",
            "ts": _now(),
            "from": prev,
            "to": slug,
            "at_pct": at_pct,
            "via": "switch" if manual else "tick",
        }
    )
    return True


def _account_flip_dir(slugs: list[str]) -> str | None:
    """An account's flip target among its dirs: the freshest-mtime credentialed one (most
    recently used = the chain proven alive most recently), or None when none holds credentials.
    Dirs whose chain fails the liveness gate are skipped (F-P1) — both auto selectors
    (:func:`_pick_flip_target`, :func:`_freshest_credentialed_slug`) inherit the gate here."""
    best: str | None = None
    best_m: float | None = None
    for slug in slugs:
        d = _fleet_root() / slug
        try:
            m = (d / ".credentials.json").stat().st_mtime
        except OSError:
            continue
        if _chain_stale_reason(d) is not None:
            continue  # a dead/dying chain is never a flip target, however good its quota looks
        if best_m is None or m > best_m:
            best, best_m = slug, m
    return best


def _flip_churn_excluded(
    utils: dict[str, float | None], cap: float | None, threshold: float
) -> bool:
    """The ONE candidate-exclusion predicate, shared by :func:`_pick_flip_target` (cached
    readings) and :func:`_validated_pick` (live re-verify) — F-C1: the two sites drifting
    apart IS the churn bug, so they cannot each carry their own copy. Excluded when: either
    window ≥100 (walled — revives on reset, never by a flip), weekly ≥ its ``caps.json`` cap
    (cap-walled — the operator's reserve), or either window ≥ ``ROTATE_THRESHOLD`` (flipping
    there just trips the flip-away next tick — pointless churn)."""
    if any(u is not None and u >= 100.0 for u in utils.values()):
        return True
    wu = utils.get("seven_day")
    if cap is not None and wu is not None and wu >= cap:
        return True
    return any(u is not None and u >= threshold for u in utils.values())


def _pick_flip_target(
    accounts: list[dict], exclude: frozenset[str] | set[str] = frozenset()
) -> tuple[str, str] | None:
    """The flip successor as ``(slug, email)``: PERISHABLE-FIRST (operator rule 2026-09-02, the
    same rule :func:`_pick_successor` applies on the reactive path) — the SOONEST weekly reset
    wins (quota about to refresh is the cheapest to burn), ties to lowest seven_day then lowest
    five_hour utilization, an unknown reset time sorts last — among accounts whose dirs
    hold LIVE-chained credentials (the F-P1 gate, via ``_account_flip_dir``) — excluding the
    *exclude* emails, walled ones (either window ≥100%), CAP-walled ones (weekly ≥ its
    ``caps.json`` cap — the operator's browser reserve), ones already at/over
    ``ROTATE_THRESHOLD`` on either window (flipping there just trips the flip-away next tick —
    pointless churn), and accounts with no quota reading at all (headroom that cannot be proven
    is not headroom; adapted from the legacy ``_walled`` no-telemetry rule). This is the ONE
    choke point: the tick's flip leg and the pointer-repair fallback both inherit these
    exclusions through here. Cached readings count — ``_validated_pick`` live-verifies them
    before a flip. None when nothing qualifies (→ the drain advisory is the only recourse)."""
    threshold = _rotate_threshold()
    far = _now() + 365 * 86400  # an unknown reset time is unprovable perishability — sorts last
    ranked: list[tuple[tuple[float, float, float], str, str]] = []
    for row in accounts:
        if row.get("email") in exclude:
            continue
        slug, utils, reason = _flip_candidate_verdict(row, threshold)
        if reason is not None or slug is None:
            continue  # the ONE predicate source — the diagnostic line prints the same reason
        wk = row.get("seven_day")
        reset = wk.get("resets_at_epoch") if isinstance(wk, dict) else None
        reset_at = float(reset) if isinstance(reset, (int, float)) else far
        weekly = utils["seven_day"] if utils["seven_day"] is not None else 100.0
        session = utils["five_hour"] if utils["five_hour"] is not None else 100.0
        ranked.append(((reset_at, weekly, session), slug, str(row.get("email"))))
    if not ranked:
        return None
    ranked.sort()
    return ranked[0][1], ranked[0][2]


def _cache_trust_s() -> float:
    """How old a cached reading may be and still stand in for a failed live re-verify. Defaults
    to the tick's own reading-refresh interval (``ROTATE_READING_MAX_AGE_S``) so one knob moves
    both: a reading the tick would not yet refresh is, by the same rule, still trusted."""
    return _env_float("ROTATE_CACHE_TRUST_S", _env_float("ROTATE_READING_MAX_AGE_S", 3600.0))


def _flip_candidate_verdict(
    row: dict, threshold: float
) -> tuple[str | None, dict[str, float | None], str | None]:
    """The ONE candidate predicate, returning ``(slug, utils, reason)`` — ``reason`` is None
    when the row is a flip candidate. :func:`_pick_flip_target` DECIDES on it and
    :func:`_flip_exclusion_reasons` PRINTS it, so the two can never drift (F-C1: two copies of
    an exclusion predicate drifting apart IS the churn bug). The cached-unverifiable outcome is
    not a predicate here — it is :func:`_validated_pick`'s live verdict — so the diagnostic
    names it from the row's ``source``/``age_s`` instead."""
    slug = _account_flip_dir(row.get("slugs") or [])
    utils: dict[str, float | None] = {}
    for key in ("five_hour", "seven_day"):
        w = row.get(key)
        u = w.get("utilization") if isinstance(w, dict) else None
        utils[key] = float(u) if isinstance(u, (int, float)) else None
    # A CACHED standby whose 5h reset time has already passed holds a ROLLED-OVER window: an idle
    # account cannot burn fleet quota, so that window is empty by construction (the board applies
    # the same rule). Read it as 0% — the stale 100% is not evidence of anything current.
    fh = row.get("five_hour")
    fh_reset = fh.get("resets_at_epoch") if isinstance(fh, dict) else None
    if (
        row.get("source") == "cache"
        and utils["five_hour"] is not None
        and isinstance(fh_reset, (int, float))
        and float(fh_reset) <= _now()
    ):
        utils["five_hour"] = 0.0
    if slug is None:
        return None, utils, "no live-chained credentialed dir (chain stale or no credentials)"
    if utils["five_hour"] is None and utils["seven_day"] is None:
        return slug, utils, "no quota reading"
    if any(u is not None and u >= 100.0 for u in utils.values()):
        return slug, utils, "walled (a window at 100%)"  # the sharpest fact first
    # OPERATOR RULE (2026-09-02): never rotate to an account that has no 5h session budget. A
    # weekly reading alone proves nothing about the session window, and a sibling near its own
    # session wall would be flipped to and flipped away from on the next tick.
    # Default = the drain threshold: a target at/over it would be advisory-flagged the moment it
    # became active, so "has 5h budget" and "not yet draining" are ONE line, not two knobs.
    session_max = _env_float(
        "ROTATE_TARGET_SESSION_MAX_PCT", _env_float("ROTATE_DRAIN_THRESHOLD", 85.0)
    )
    if utils["five_hour"] is None:
        return slug, utils, "no session reading — 5h budget unproven"
    if utils["five_hour"] > session_max:
        return (
            slug,
            utils,
            (
                f"session {utils['five_hour']:.0f}% used — no 5h budget (target max {session_max:.0f}%)"
            ),
        )
    if _flip_churn_excluded(utils, row.get("weekly_cap"), threshold):
        wu = utils.get("seven_day")
        cap = row.get("weekly_cap")
        if cap is not None and wu is not None and wu >= cap:
            return slug, utils, f"weekly {wu:.0f}% ≥ cap {cap}"
        return slug, utils, f"a window ≥ {threshold:.0f}% (flip-away next tick)"
    return slug, utils, None


def _flip_exclusion_reasons(
    accounts: list[dict], exclude: set[str] | frozenset[str], threshold: float
) -> list[str]:
    """One ``email: reason`` per sibling the flip leg could NOT pick, from the SAME predicate the
    picker decides on (:func:`_flip_candidate_verdict`), printed when the pick is None. "NO
    successor has headroom" with no reason was undiagnosable twice on 2026-09-02."""
    out: list[str] = []
    for row in accounts:
        email = str(row.get("email"))
        if email in exclude:
            continue
        _slug, _utils, reason = _flip_candidate_verdict(row, threshold)
        if reason is None:
            if row.get("source") == "cache":
                age = row.get("age_s")
                age_s = f"{age / 60:.0f}m" if isinstance(age, (int, float)) else "?"
                reason = (
                    f"cached {age_s} ago and the live re-verify failed or the cache is older"
                    f" than the trust window ({_cache_trust_s() / 60:.0f}m)"
                )
            else:
                reason = "eligible on paper — the flip was withheld elsewhere (see stderr)"
        out.append(f"{email}: {reason}")
    return out


def _freshest_credentialed_slug(dirs: list[Path]) -> str | None:
    """Repair fallback when NO account has a provable quota reading: the freshest credentialed
    dir fleet-wide — a missing/dangling pointer is an outage, and pointing at the most recently
    live chain beats leaving every session with no config dir at all."""
    return _account_flip_dir([d.name for d in dirs])


def _validated_pick(
    accounts: list[dict], exclude: set[str], *, verbose: bool = False
) -> tuple[str, str] | None:
    """F-P2: :func:`_pick_flip_target`, with cached candidates LIVE-verified before they can
    become the fleet's pointer. A candidate whose reading was live THIS tick is returned as-is;
    one ranked off a CACHED row gets ONE usage probe with its own dir's token — probe failure
    (dead/unreachable) or a walled live reading excludes it and the next-best is considered.
    Cached-and-unverifiable must never become the fleet's sole pointer. None when nobody
    survives (→ the caller falls through to the no-headroom advisory)."""
    threshold = _rotate_threshold()
    exclude = set(exclude)
    while True:
        pick = _pick_flip_target(accounts, exclude=exclude)
        if pick is None:
            return None
        slug, email = pick
        row = next((r for r in accounts if r.get("email") == email), None)
        if row is None or row.get("source") != "cache":
            return pick  # reading is live this tick — already validated
        tok = _read_access_token(_fleet_root() / slug / ".credentials.json")
        windows = _usage_windows(_oauth_get("usage", tok)) if tok is not None else None
        if windows is None:
            # F-P2 AMENDED (2026-09-02, measured on the 14:35 tick: "NO successor has headroom"
            # while can@ sat at 12%/12%): the probe runs with the STANDBY's own access token,
            # which is expired by construction — only the active chain self-refreshes
            # (_stale_snapshot_reason says so) — so it 401s for every idle sibling and nothing
            # cached could ever become the pointer. A reading younger than ROTATE_CACHE_TRUST_S
            # on a chain that passes the liveness gate is accepted (the refresh token is what
            # makes the standby usable; the CLI rolls the access token on first use). An OLDER
            # cache stays excluded — the rosy-cache class F-P2 exists for.
            age = row.get("age_s")
            if (
                isinstance(age, (int, float))
                and age <= _cache_trust_s()
                and _chain_stale_reason(_fleet_root() / slug) is None
            ):
                if verbose:  # the flip leg only — the advisory leg re-asks and must not repeat
                    print(
                        f"tick: {email} cached reading {age / 60:.0f}m old accepted — live probe"
                        " failed (a standby's access token is expired by design; chain gate passed)"
                    )
                return pick
            exclude.add(email)  # cached-and-unverifiable (or too old) — never the fleet's pointer
            continue
        # ONLY the two quota windows are utilization dicts — `model_windows` (added 2026-08-22)
        # rides along and crashed a `.items()` comprehension here with KeyError 'utilization'.
        # The live reading REPLACES the cached windows and goes through the SAME candidate verdict
        # the picker applied to the cache (F-C1 — walled / cap / ≥threshold / the 5h-budget gate):
        # a rosy cache that probes live at 90% session is not a target, whatever the cache said.
        live_row = {**row, "source": "live"}
        for k in ("five_hour", "seven_day"):
            if isinstance(windows.get(k), dict):
                live_row[k] = windows[k]
        _slug2, _utils2, live_reason = _flip_candidate_verdict(live_row, threshold)
        if live_reason is not None:
            exclude.add(email)
            continue
        return pick


def _cmd_fleet_switch(name: str, dirs: list[Path]) -> int:
    """``--switch <slug>`` in fleet mode: a MANUAL flip through the same :func:`_flip_active`
    the tick uses — pause-exempt and dwell-exempt, the deliberate operator escape hatch (same
    semantics as the legacy ``--switch``). Resolves *name* by exact dir slug, else a UNIQUE
    prefix — ambiguity is refused, never guessed (the ``_find_account`` rule)."""
    names = [d.name for d in dirs]
    matches: list[str] = []
    if name:
        exact = [n for n in names if n == name]
        matches = exact or [n for n in names if n.startswith(name)]
    if len(matches) != 1:
        sys.stderr.write(
            f"claude_rotate: no unique fleet dir matching {name!r} — dirs: {', '.join(names)}\n"
        )
        return 1
    if _flip_active(matches[0], manual=True):
        print(f"active fleet account -> {matches[0]} (pointer flip — zero credential bytes moved)")
        # The cap never binds the operator: a manual flip to a capped account is honored, with
        # one line naming the cap — their deliberate act, same escape-hatch contract as pause.
        arow = _load_assignments(strict=False).get(matches[0])
        identity = arow.get("identity") if isinstance(arow, dict) else None
        cap = _account_caps().get(identity.lower()) if isinstance(identity, str) else None
        if cap is not None:
            print(
                f"note: {identity} carries a weekly cap of {cap}% (caps.json) — manual "
                "override honored; the tick flips away once weekly ≥ cap"
            )
        return 0
    sys.stderr.write("switch failed — active pointer unchanged (see above)\n")
    return 1


def _pin_pending_identities(dirs: list[Path]) -> dict:
    """Flip ``pending-login`` rows to their VERIFIED email — the pin moment (spine Interfaces).

    A pending row gets ONE profile probe with that dir's OWN access token (in memory, never
    logged). Success → the verified email is written back to assignments.json and the row is
    never probed again (the pin is permanent — the dead-token identity gate that lost an
    account's chain is not reintroduced). Failure → the row stays pending and is excluded from
    account grouping. Probes run BEFORE the flock (never hold a lock across the network); the
    write-back re-reads the table under the lock so a concurrent --new-dir row is never lost.
    Returns the table with the pins applied (in memory even if persisting failed — an unpersisted
    pin re-probes next run, which only costs one call).
    """
    table = _load_assignments(strict=False)
    pins: dict[str, str] = {}
    for d in dirs:
        row = table.get(d.name)
        if not isinstance(row, dict) or row.get("identity") != "pending-login":
            continue
        tok = _read_access_token(d / ".credentials.json")
        if tok is None:
            continue  # no login yet (or unreadable) — nothing to verify
        prof = _oauth_get("profile", tok)
        email = ((prof or {}).get("account") or {}).get("email")
        if isinstance(email, str) and "@" in email:
            pins[d.name] = email
            # The pin IS a live identity verification — record it as THIS DIR's first verdict
            # (under its own slug, F-P9: it must never mask a sibling dir's unresolved
            # mismatch), or the account-rows pass would immediately re-probe what it proved.
            _identity_probe_record(d.name, email, _now())
    if not pins:
        return table
    try:
        lock_fd = _assignments_lock_fd()
    except _STATE_DIR_ERRORS:
        lock_fd = None  # cannot lock → apply in memory only; never risk clobbering the table
    try:
        if lock_fd is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            table = _load_assignments(strict=False)  # re-read under the lock
        changed = False
        for slug, email in pins.items():
            row = table.get(slug)
            if isinstance(row, dict) and row.get("identity") == "pending-login":
                row["identity"] = email
                changed = True
        if lock_fd is not None and changed:
            try:
                _write_json_atomic(_assignments_path(), table)
            except _STATE_DIR_ERRORS as e:
                sys.stderr.write(f"claude_rotate: identity pin not persisted ({e})\n")
        return table
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)


def _usage_windows(usage: dict | None) -> dict | None:
    """Both quota windows from a usage payload, or None on ANY malformed part. FAIL-CLOSED like
    _account_status: a changed/partial shape must read as "no reading" (→ the cached row), never
    as 0% — a false 0% would silence the advisory exactly when an account nears its wall."""
    if not isinstance(usage, dict):
        return None
    out: dict = {}
    for key in ("five_hour", "seven_day"):
        w = usage.get(key)
        u = w.get("utilization") if isinstance(w, dict) else None
        if not isinstance(u, (int, float)):
            return None
        out[key] = {"utilization": float(u), "resets_at_epoch": _iso_to_epoch(w.get("resets_at"))}
    # Per-MODEL weekly limits arrive as scoped entries in the `limits` array, each carrying the
    # model's own display_name — this is the authoritative, self-labeling source for a model's
    # separate weekly quota. Fable-5 lives ONLY here (kind="weekly_scoped",
    # scope.model.display_name="Fable"); it has no top-level window key, which is why an earlier
    # top-level-only scan never found it (2026-08-22). The undocumented top-level codename
    # windows (nimbus_quill, tangelo, …) are deliberately NOT surfaced — they are noise, always
    # 0/None. Additive and NEVER fail-closed: a malformed limits array leaves the required
    # five_hour/seven_day reading intact.
    models: dict = {}
    limits = usage.get("limits")
    if isinstance(limits, list):
        for lim in limits:
            if not isinstance(lim, dict) or lim.get("kind") != "weekly_scoped":
                continue
            scope = lim.get("scope")
            model = scope.get("model") if isinstance(scope, dict) else None
            name = model.get("display_name") if isinstance(model, dict) else None
            pct = lim.get("percent")
            if isinstance(name, str) and name and isinstance(pct, (int, float)):
                models[name] = {
                    "utilization": float(pct),
                    "resets_at_epoch": _iso_to_epoch(lim.get("resets_at")),
                }
    if models:
        out["model_windows"] = models
    return out


def _usage_cache_path() -> Path:
    return _rotate_state_dir() / "fleet-usage-cache.json"


def _load_usage_cache() -> dict:
    try:
        data = json.loads(_usage_cache_path().read_text())
        return data if isinstance(data, dict) else {}
    except _STATE_DIR_ERRORS:
        return {}


def _account_caps() -> dict[str, int]:
    """Per-account WEEKLY utilization caps: ``<fleet_root>/caps.json`` = {"email": cap%}.

    Operator contract (2026-08-15): "do not consume ob@'s weekly quota more than 90% — I also
    use it in the claude.ai browser regularly." At/over its cap an account is flipped AWAY from
    and excluded from automated selection exactly like a walled one — the remainder is the
    operator's browser reserve. The cap never touches manual ``--switch`` (warned, honored),
    keepalive, or the identity/liveness nets. Lives in the fleet root deliberately: it travels
    with the fleet and shares no keyspace with assignments.json's slugs.

    Fail direction: a broken caps file must never HALT rotation, but must never be silent
    either — missing file → no caps; unparseable/wrong-shape → loud stderr naming the file +
    no caps; non-numeric entries skipped with a warning. Values clamp to 1..100. Keys are
    normalized to LOWERCASE (every consumer lowercases its comparison email too — F-C2: a case
    mismatch silently doing nothing violates this loader's own never-silent contract), and a
    key matching no known account warns via :func:`_fleet_row_warnings`.
    """
    path = _fleet_root() / "caps.json"
    try:
        raw = path.read_text()
    except FileNotFoundError:
        return {}
    except OSError as e:
        sys.stderr.write(f"claude_rotate: cannot read {path} ({e}) — rotating UNCAPPED\n")
        return {}
    try:
        data = json.loads(raw)
    except ValueError as e:
        sys.stderr.write(f"claude_rotate: {path} is not valid JSON ({e}) — rotating UNCAPPED\n")
        return {}
    if not isinstance(data, dict):
        sys.stderr.write(f"claude_rotate: {path} is not a JSON object — rotating UNCAPPED\n")
        return {}
    caps: dict[str, int] = {}
    for email, cap in data.items():
        # bool is an int subclass — `true` as a cap is a typo, never "cap at 1%"
        if isinstance(cap, bool) or not isinstance(cap, (int, float)) or not math.isfinite(cap):
            sys.stderr.write(
                f"claude_rotate: {path}: cap for {email!r} is not a number ({cap!r}) — "
                "entry skipped\n"
            )
            continue
        caps[str(email).lower()] = int(min(100, max(1, cap)))
    return caps


def _fleet_account_rows(
    dirs: list[Path], *, allow_pings: bool = False
) -> tuple[list[dict], list[dict]]:
    """(account rows, pending entries) — the fleet view's data, shared by --status and the tick.

    Grouping keys on the PINNED identity in assignments.json (never a live re-probe). Usage is
    read once per account with the FRESHEST dir's token (~4 calls/tick) — live only while that
    token is <8h old (mtime, the CLI's rewrite-on-refresh signal); otherwise the cached
    last-known row rides with its age, marked stale. The cache means an idle account is an
    upper bound with a date on it — never today's "parked — quota unknown" blindness.

    ``allow_pings`` — ONLY the tick passes True. The stale-reading refresh ping shells out to
    the claude CLI (150s timeout, up to 3 per run ≈ 7½ min worst case); leaving it reachable
    from ``--status`` hung the quota dashboard behind its 60s probe cap on 2026-08-18 evening
    (every page load blocked, the operator read it as "not reachable"). ``--status`` is a
    report: it must stay a pure read that finishes in seconds, and it can — the */5 tick keeps
    the cache fresh, so status never needs to ping to be current.
    """
    now = _now()
    table = _pin_pending_identities(dirs)
    groups: dict[str, list[dict]] = {}
    pending: list[dict] = []
    for d in dirs:
        row = table.get(d.name)
        row = row if isinstance(row, dict) else {}
        try:
            mtime: float | None = (d / ".credentials.json").stat().st_mtime  # MTIME, never bytes
        except OSError:
            mtime = None
        entry = {"slug": d.name, "dir": d, "mtime": mtime}
        identity = row.get("identity")
        if isinstance(identity, str) and "@" in identity:
            groups.setdefault(identity, []).append(entry)
        else:
            pending.append(entry)
    cache = _load_usage_cache()
    caps = _account_caps()
    accounts: list[dict] = []
    cache_dirty = False
    # The stale-reading refresh pings are allocated BEFORE the pass below, oldest reading
    # first, because the pass itself walks `sorted(groups)` — see :func:`_ping_slots`.
    ping_slots = _ping_slots(groups, cache, now) if allow_pings else set()
    for email in sorted(groups):
        members = sorted(groups[email], key=lambda m: m["slug"])
        with_creds = sorted(
            (m for m in members if m["mtime"] is not None),
            key=lambda m: m["mtime"],
            reverse=True,
        )
        exps = [
            e
            for e in (_refresh_expiry_epoch(m["dir"] / ".credentials.json") for m in with_creds)
            if e is not None
        ]
        row = {
            "email": email,
            "slugs": [m["slug"] for m in members],
            "five_hour": None,
            "seven_day": None,
            "source": "none",
            "age_s": None,
            # the account's soonest chain lapse — --status/tick warn under 5d (before the
            # F-P1 flip gate would silently drop it from candidacy)
            "refresh_expires_epoch": min(exps) if exps else None,
            "identity_mismatches": [],
            "weekly_cap": caps.get(email.lower()),
            "cap_walled": False,
        }
        windows = None
        if with_creds and (now - with_creds[0]["mtime"]) < _FLEET_TOKEN_FRESH_S:
            tok = _read_access_token(with_creds[0]["dir"] / ".credentials.json")
            if tok is not None:
                payload = _oauth_get("usage", tok)
                windows = _usage_windows(payload)
                # F-P4 net (mid-refresh flip race / login into the wrong dir): compare the
                # pinned identity against what THIS already-made probe answers — no probe
                # volume is added (review constraint), so the net keys on the identity the
                # usage payload itself carries.
                acct = payload.get("account") if isinstance(payload, dict) else None
                probed = acct.get("email") if isinstance(acct, dict) else None
                if isinstance(probed, str) and "@" in probed and probed != email:
                    row["identity_mismatches"].append(
                        {"slug": with_creds[0]["slug"], "probe_email": probed}
                    )
        # F-P6: the identity net's LIVE leg. Probed live 2026-08-15: the /api/oauth/usage
        # payload carries NO account.email (top-level keys are the quota windows only), so the
        # zero-cost comparison above can never fire on today's API shape — it stays only as a
        # free upgrade if the field ever appears. The net's liveness rests on THIS bounded
        # probe: ONE profile GET per pinned account per hour (stamp-budgeted per ACCOUNT,
        # skew-clamped — ~24/account/day, not 288), made against the account's FRESHEST dir
        # and only while that token is fresh enough to answer (the usage leg's mtime gate —
        # the mid-refresh race and a wrong-dir login both leave a freshly-rewritten credential
        # file, so the gate never blinds the net's targets). The verdict is recorded under
        # THAT DIR'S SLUG (F-P9 — a fresh pin on a sibling dir can never mask another dir's
        # mismatch). Probe FAILURE updates nothing: no warning (a transport blip is not a
        # mismatch) and no stamp (next tick retries — a blip must not silence the net for an
        # hour either).
        member_slugs = [m["slug"] for m in members]
        if (
            with_creds
            and (now - with_creds[0]["mtime"]) < _FLEET_TOKEN_FRESH_S
            and _identity_probe_due(member_slugs, now)
        ):
            tok = _read_access_token(with_creds[0]["dir"] / ".credentials.json")
            prof = _oauth_get("profile", tok) if tok is not None else None
            if prof is not None:
                acct = prof.get("account") if isinstance(prof, dict) else None
                probed = acct.get("email") if isinstance(acct, dict) else None
                _identity_probe_record(
                    with_creds[0]["slug"],
                    probed if isinstance(probed, str) and "@" in probed else None,
                    now,
                )
        # F-P7: REPORTING a stored verdict is UNCONDITIONAL — every pinned dir's slug stamp is
        # read every pass, regardless of any mtime. The freshness gate above governs NEW probes
        # only: the likely aftermath of a corrupted dir is that it goes IDLE, and its recorded
        # mismatch must keep warning until a later probe of that dir re-verifies (which the
        # recovery /login triggers — it rewrites the credential file, making the dir fresh and
        # probe-able again).
        flagged = {m["slug"] for m in row["identity_mismatches"]}
        for slug in member_slugs:
            if slug in flagged:
                continue
            last = _identity_probe_result(slug)
            if last is not None and last != email:
                row["identity_mismatches"].append({"slug": slug, "probe_email": last})
        if windows is None and with_creds:
            # ALWAYS-CURRENT READINGS (operator mandate 2026-08-18: the dashboard "must always
            # show up-to-date usage" — parked stores previously went dark when their 8h access
            # token died, and the 43h-stale walls it displayed were the incident's dashboard
            # symptom). When the reading would fall to a cache row older than
            # ROTATE_READING_MAX_AGE_S (default 1h), refresh THIS account's chain via the
            # sole-owner keepalive ping (the CLI-lawful path — no credential byte touched by
            # this script) and probe once more. Stamp-budgeted per account per interval and
            # capped per run, so a dead chain is never hammered every tick. A FAILED ping is
            # itself the signal: `ping_failed` marks the chain DEAD, and the flip leg treats a
            # dead ACTIVE chain as a flip trigger (the 2026-08-17 21:00 outage sat undetected
            # for 9h precisely because quota, not liveness, was the only trigger).
            # WHICH accounts get this run's pings is decided ONCE, before this pass, by
            # STALENESS — see :func:`_ping_slots`. Spending the budget in `sorted(groups)`
            # order starved whichever account sorted last (2026-09-04).
            if email in ping_slots:
                ping_slots.discard(email)
                _touch_refresh_stamp(email)
                if _keepalive_ping(with_creds[0]["dir"]):
                    tok = _read_access_token(with_creds[0]["dir"] / ".credentials.json")
                    if tok is not None:
                        windows = _usage_windows(_oauth_get("usage", tok))
                else:
                    row["ping_failed"] = True
        if windows is not None:
            row.update(windows)
            row["source"] = "live"
            cache[email] = {"ts": now, **windows}
            cache_dirty = True
        else:
            c = cache.get(email)
            if isinstance(c, dict) and isinstance(c.get("ts"), (int, float)):
                row["five_hour"] = c.get("five_hour")
                row["seven_day"] = c.get("seven_day")
                if c.get("model_windows"):
                    row["model_windows"] = c["model_windows"]
                row["source"] = "cache"
                row["age_s"] = max(0.0, now - float(c["ts"]))
        wk = row["seven_day"]
        wu = wk.get("utilization") if isinstance(wk, dict) else None
        row["cap_walled"] = bool(
            row["weekly_cap"] is not None
            and isinstance(wu, (int, float))
            and wu >= row["weekly_cap"]
        )
        accounts.append(row)
    if cache_dirty:
        try:
            _write_json_atomic(_usage_cache_path(), cache)
        except _STATE_DIR_ERRORS:
            pass  # a lost cache write costs one stale row later, never the status itself
    return accounts, pending


def _fmt_quota_window(w: dict | None) -> str:
    """Fleet-view window formatter (the legacy _cmd_status keeps its own — that view must stay
    byte-identical while the fleet exists nowhere)."""
    if not isinstance(w, dict) or not isinstance(w.get("utilization"), (int, float)):
        return "-"
    rs = w.get("resets_at_epoch")
    if rs:
        from datetime import datetime

        rs_s = datetime.fromtimestamp(rs).strftime("%a %H:%M")
    else:
        rs_s = "?"
    return f"{w['utilization']:.0f}% (resets {rs_s})"


def _fleet_quota_text(row: dict) -> str:
    """One account's quota cell: live values, a cached row with its age, or an honest 'no
    reading yet' — NEVER the legacy "parked — quota unknown" line this view retires."""
    if row["source"] == "none":
        return "no quota reading yet (idle >8h, nothing cached)"
    text = (
        f"session {_fmt_quota_window(row['five_hour']):24}"
        f" weekly {_fmt_quota_window(row['seven_day'])}"
    )
    if row.get("weekly_cap") is not None:
        text += f" (cap {row['weekly_cap']})"
    if row["source"] == "cache":
        text += f"  STALE — cached {row['age_s'] / 3600:.0f}h ago"
    return text


def _fleet_row_warnings(accounts: list[dict]) -> list[str]:
    """Chain-health warnings derived from data already on the account rows (this function adds
    no probes; the rows were built with at most one hourly identity probe per account), printed
    by --status and the tick alike: (1) a refresh chain inside the 5-day expiry window — the
    keepalive cadence is 7d, so this firing means that net already missed it; (2) the F-P4/F-P6
    identity-mismatch net — a dir whose probed token answers as a DIFFERENT account than its
    pinned identity (a flip landed inside a CLI credential refresh, or a login went into the
    wrong dir). Recovery for both is a /login or a claude turn IN THAT DIR — never a file copy."""
    warns: list[str] = []
    now = _now()
    for row in accounts:
        label = ", ".join(row.get("slugs") or [])
        exp = row.get("refresh_expires_epoch")
        if isinstance(exp, (int, float)):
            left = exp - now
            if left <= 0:
                warns.append(
                    f"⚠ {row['email']}: refresh chain EXPIRED {-left / 86400:.1f}d ago — "
                    f"ONE /login in [{label}] re-mints it"
                )
            elif left < _CHAIN_EXPIRY_WARN_S:
                warns.append(
                    f"⚠ {row['email']}: refresh chain expires in {left / 86400:.1f}d — run one "
                    f"claude turn in [{label}] before it lapses (keepalive cadence is 7d)"
                )
        for mm in row.get("identity_mismatches") or []:
            warns.append(
                f"⚠ {mm['slug']}: IDENTITY MISMATCH — dir pinned to {row['email']} but its "
                f"token answers as {mm['probe_email']} (a flip landed inside a credential "
                "refresh, or a login went into the wrong dir). Recovery: ONE /login in that "
                "dir re-mints its chain; do NOT copy credential files"
            )
        if row.get("cap_walled"):
            wk = row.get("seven_day")
            wu = wk.get("utilization") if isinstance(wk, dict) else None
            at = f"{wu:.0f}%" if isinstance(wu, (int, float)) else "?"
            warns.append(
                f"⚠ {row['email']}: cap-walled — weekly {at} ≥ cap {row['weekly_cap']} "
                "(caps.json) — reserved for operator use until weekly reset; automated flips "
                "exclude it (--switch still may, deliberately)"
            )
    # F-C2: a caps.json key matching NO known account email (pinned identities + assignments
    # accounts, all lowercased) is a typo silently doing nothing — surface it. File reads
    # only, no probes (the docstring contract above holds).
    caps = _account_caps()
    if caps:
        known = {str(row.get("email", "")).lower() for row in accounts}
        for arow in _load_assignments(strict=False).values():
            if isinstance(arow, dict):
                for field in ("identity", "account"):
                    v = arow.get(field)
                    if isinstance(v, str) and "@" in v:
                        known.add(v.lower())
        for key in sorted(caps):
            if key not in known:
                warns.append(
                    f"⚠ caps.json key {key!r} matches no account — cap inactive (typo? "
                    "known accounts are the pinned identities and assignments entries)"
                )
    return warns


def _cmd_fleet_status(dirs: list[Path], as_json: bool) -> int:
    accounts, pending = _fleet_account_rows(dirs)
    warns = _fleet_row_warnings(accounts) + _fleet_warnings()
    active = _resolve_active()  # slug | None (missing/dangling pointer)
    if as_json:
        print(
            json.dumps(
                {
                    "fleet_root": str(_fleet_root()),
                    "accounts": accounts,
                    "active": active,
                    "pending": [p["slug"] for p in pending],
                    "pause": _pause_state(),
                    "fleet_warnings": warns,
                },
                indent=1,
            )
        )
        return 0
    # No raw root path in the text header — a path can smuggle arbitrary words into the banner
    # (a tmp root literally containing "occupancy" false-fired a warn assertion); the JSON
    # payload carries fleet_root for machine consumers.
    print(f"fleet: {len(dirs)} dir(s) · {len(accounts)} account(s) · active: {active or 'none'}")
    for row in accounts:
        label = ", ".join(row["slugs"])
        mark = "*" if active is not None and active in row["slugs"] else " "
        print(f"{mark} {row['email']:32} {_fleet_quota_text(row)}  [{label}]")
    for p in pending:
        print(
            f"  {p['slug']:32} pending-login — identity unverified (ONE /login in this dir pins it)"
        )
    for warn in warns:
        print(warn)
    return 0


def _fleet_exhaustion_stamp() -> Path:
    """The fleet-wide wall latch: present = the "active account is walled, no auto-relief"
    advisory has already fired for the CURRENT wall episode. Cleared the instant the active
    account is no longer walled (a flip to headroom, or a reset), so the next genuine wall
    speaks fresh. Same tmp fallback as the other stamps — epoch-free, no clock-skew concern."""
    try:
        return _rotate_state_dir() / "fleet-exhausted"
    except _STATE_DIR_ERRORS:
        return Path(tempfile.gettempdir()) / "claude-fleet-exhausted"


def _fleet_refresh_stamp(email: str) -> Path:
    """PER-ACCOUNT stale-reading refresh stamp — rate-limits the keepalive-ping refresh so a
    dead chain is pinged at most once per interval, never on every 5-minute tick."""
    safe = re.sub(r"[^a-z0-9]+", "-", email.lower()).strip("-")
    try:
        return _rotate_state_dir() / f"fleet-refresh-{safe}"
    except _STATE_DIR_ERRORS:
        return Path(tempfile.gettempdir()) / f"claude-fleet-refresh-{safe}"


def _ping_slots(groups: dict[str, list[dict]], cache: dict, now: float) -> set[str]:
    """Which accounts spend this run's stale-reading refresh pings — the OLDEST reading first.

    The budget (``ROTATE_REFRESH_MAX_PER_RUN``, default 3) used to be spent inside
    ``for email in sorted(groups)``, so a fleet with more stale accounts than budget starved
    whichever account sorted LAST — deterministically, every run, for ever. Measured on the
    2026-09-04 freeze: four accounts, budget 3, and sarp@ (last in sort) reached a 405-minute
    reading while can@/mob@/ob@ were re-pinged each tick. :func:`_validated_pick` refuses any
    cache past ``ROTATE_CACHE_TRUST_S`` (60m), so the ONE account that had headroom — 30% on its
    first live reading after the operator switched to it BY HAND, 10h41m after the urgent drain
    mail — was structurally
    invisible to the picker, and the tick printed "NO successor has headroom" 47 times (the whole tail run of that line; 87 is the log-wide count, all accounts, all time).

    Serving the stalest first CANNOT starve: an account dropped this run is staler next run and
    outranks the ones just served. The gates are EXACTLY the ones the pass applied — a
    credentialed account whose cached reading is at or past ``ROTATE_READING_MAX_AGE_S``, whose
    own per-account stamp budget has elapsed — so no ping is issued that the old code would not
    have issued; only the ORDER of spending changes. In particular it does NOT skip an account
    whose token is fresh enough to probe live (the first cut did, and the review caught it): an
    account becomes a candidate only once its reading is ALREADY an hour old, so a fresh token
    with a stale reading means the PROBE is failing — precisely the account that needs the ping.
    Skipping it would also have narrowed the dead-chain detector in silence, because
    ``ping_failed`` is set only on that ping and it is what makes a dead ACTIVE chain a flip
    trigger (the 2026-08-17 21:00 outage sat undetected for 9h when quota was the only trigger).
    """
    budget = int(_env_float("ROTATE_REFRESH_MAX_PER_RUN", 3.0))
    if budget <= 0:
        return set()
    max_age = _env_float("ROTATE_READING_MAX_AGE_S", 3600.0)
    ranked: list[tuple[float, str]] = []
    for email, members in groups.items():
        if not any(m["mtime"] is not None for m in members):
            continue  # no credentialed dir — there is no chain to ping
        c = cache.get(email)
        age = (
            now - float(c["ts"])
            if isinstance(c, dict) and isinstance(c.get("ts"), (int, float))
            else None
        )
        if age is not None and age < max_age:
            continue  # the reading is still inside the freshness window
        if not _refresh_ping_due(email, now):
            continue  # this account's own stamp budget says not yet
        # No cached reading at all is the STALEST state there is — it outranks any age.
        ranked.append((float("inf") if age is None else age, email))
    ranked.sort(key=lambda r: (-r[0], r[1]))  # oldest first; email breaks ties deterministically
    return {email for _, email in ranked[:budget]}


def _refresh_ping_due(email: str, now: float) -> bool:
    """True when this account's stale-reading refresh is allowed (stamp older than the
    interval, or absent). Future-skewed stamps count as due — same safe direction as the
    keepalive's clamp: a spurious ping is cheap, a silently skipped one leaves the operator
    staring at a stale wall (the 2026-08-18 incident's dashboard symptom)."""
    interval = _env_float("ROTATE_READING_MAX_AGE_S", 3600.0)
    stamp = _fleet_refresh_stamp(email)
    try:
        age = now - stamp.stat().st_mtime
    except OSError:
        return True
    return age >= interval or age < -_CLOCK_SKEW_TOLERANCE_S


def _touch_refresh_stamp(email: str) -> None:
    try:
        _fleet_refresh_stamp(email).touch()
    except OSError:
        pass  # a lost stamp costs one extra ping next tick, never the status itself


_TICK_BURN_MAX_AGE_S = 900.0  # three tick intervals: an older memory says nothing about the next 5 min


def _tick_burn(email: str, row: dict, now: float) -> dict[str, float]:
    """The active account's PROJECTED burn until the next tick — the positive delta per window
    since the previous tick's reading of the SAME account in the SAME window (reset epoch
    unchanged), read from and written to ``<state>/tick-last-reading.json``. Zero when nothing
    comparable is remembered (first tick after a flip, a rolled-over window, a memory older than
    ``_TICK_BURN_MAX_AGE_S``, a corrupt or unwritable file). Never raises: the flip leg falls
    back to the plain threshold. Why (2026-09-03 19:50): the tick saw ob@ at 89 → 93 → 96 and the
    next tick found it at 100 with the operator already switched by hand — a 98% trip point is
    UNOBSERVABLE at a 5-minute cadence when the inter-tick burn is 3–4%, so each leg trips on
    reading + burn: the flip lands on the last tick that can still precede the wall."""
    burn = {"five_hour": 0.0, "seven_day": 0.0}
    current: dict[str, object] = {"email": email, "ts": now}
    for key in ("five_hour", "seven_day"):
        w = row.get(key)
        u = w.get("utilization") if isinstance(w, dict) else None
        r = w.get("resets_at_epoch") if isinstance(w, dict) else None
        current[key] = float(u) if isinstance(u, (int, float)) else None
        current[key + "_reset"] = float(r) if isinstance(r, (int, float)) else None
    try:
        path = _rotate_state_dir() / "tick-last-reading.json"
        try:
            prev = json.loads(path.read_text())
        except (OSError, ValueError):
            prev = None
        if (
            isinstance(prev, dict)
            and prev.get("email") == email
            and isinstance(prev.get("ts"), (int, float))
            and 0.0 <= now - float(prev["ts"]) <= _TICK_BURN_MAX_AGE_S
        ):
            for key in burn:
                pu, cu = prev.get(key), current[key]
                pr, cr_ = prev.get(key + "_reset"), current[key + "_reset"]
                # Same window = same reset epoch WITHIN A MINUTE: the endpoint derives the epoch
                # per call and it jitters by a fraction of a second (found by the first live tick:
                # 1788470999.95 → 1788471000.35 — exact equality never matched, burn was always 0).
                same_window = (
                    isinstance(pr, (int, float))
                    and isinstance(cr_, (int, float))
                    and abs(float(pr) - float(cr_)) < 60.0
                ) or (pr is None and cr_ is None)
                if isinstance(pu, (int, float)) and isinstance(cu, float) and same_window:
                    burn[key] = max(0.0, cu - float(pu))
        path.write_text(json.dumps(current))
    except _STATE_DIR_ERRORS:
        pass
    return burn


def _fleet_flip_leg(dirs: list[Path], accounts: list[dict], threshold: float) -> None:
    """The tick's pointer decision — one printed line per outcome, never raises past the
    ledger/stderr writers already guarded inside :func:`_flip_active`.

    Missing/dangling pointer → flip to the best-headroom account NOW (dwell-exempt repair;
    the pause marker still holds it — the operator's freeze outranks the repair, and their
    ``--switch`` lever stays live). No account rankable by telemetry → fall back to the
    freshest credentialed dir. Healthy pointer → flip only when the active account is at/over
    *threshold* on either window AND a credentialed, un-walled sibling has headroom."""
    active_slug = _resolve_active()
    if active_slug is None:
        pick = _validated_pick(accounts, set())
        slug = pick[0] if pick else _freshest_credentialed_slug(dirs)
        if slug is None:
            print("tick: active pointer missing and NO credentialed dir exists — cannot repair")
            return
        if _flip_active(slug, ignore_dwell=True):
            print(f"tick: active pointer missing/dangling — repaired -> {slug}")
        else:
            print(f"tick: active pointer missing — repair flip to {slug} withheld (see stderr)")
        return
    row = next((r for r in accounts if active_slug in (r.get("slugs") or [])), None)
    if row is None:
        print(f"tick: active {active_slug} — identity pending, no flip decision possible")
        return
    # DEAD-ACTIVE CHAIN IS A FLIP TRIGGER (root cause of the 2026-08-17 21:00 incident: the
    # active chain died at 93% quota and the tick said "no flip" from cache for 9 hours while
    # every screen begged for login). `ping_failed` = the stale-reading refresh ping could not
    # roll this chain. Gate on a PROVEN-UP network — at least one OTHER account probed live
    # this run — so a box-wide outage never triggers a pointless flip storm.
    if row.get("ping_failed") and any(r.get("source") == "live" for r in accounts if r is not row):
        pick = _validated_pick(accounts, {row["email"]})
        if pick is not None:
            slug, email = pick
            if _flip_active(slug, ignore_dwell=True):
                print(f"tick: active {row['email']} chain DEAD — flipped -> {email} ({slug})")
                _tick_telegram(
                    f"active account {row['email']} OAuth chain is DEAD (refresh ping failed;"
                    f" siblings reachable) — auto-flipped to {email}. Its slot needs ONE"
                    " /login when convenient."
                )
            else:
                print(f"tick: active {row['email']} chain DEAD — flip to {slug} withheld")
            return
        print(
            f"tick: active {row['email']} chain DEAD and NO successor has headroom — "
            + "; ".join(_flip_exclusion_reasons(accounts, {row["email"]}, threshold))
        )
        _tick_telegram(
            f"active account {row['email']} OAuth chain is DEAD and no sibling has headroom —"
            " every screen will prompt for login until ONE /login re-pins a chain"
        )
        return
    utils = {}
    for key in ("five_hour", "seven_day"):
        w = row.get(key)
        u = w.get("utilization") if isinstance(w, dict) else None
        utils[key] = u if isinstance(u, (int, float)) else None
    present = [u for u in utils.values() if u is not None]
    if not present:
        print(f"tick: active {row['email']} — no quota reading, no flip decision possible")
        return
    hot = max(present)
    # TWO legs, decided separately (scoped review 2026-09-03 — `min(threshold, cap)` tripped a
    # cap of 99 at 98 the moment the session threshold moved): the SESSION leg trips at
    # ROTATE_THRESHOLD; the WEEKLY leg trips at the account's caps.json cap when one exists (the
    # cap IS the operator's weekly rule — can/mob 99, sarp 90, ob 80) and at the threshold otherwise.
    cap = row.get("weekly_cap")
    weekly_thr = float(cap) if cap is not None else threshold
    # PROJECTED trip: reading + the burn since the previous tick (see _tick_burn) — a line that
    # is only checked every 5 minutes must be crossed BEFORE the wall, not observed after it.
    burn = _tick_burn(str(row.get("email")), row, _now())
    session_trip = (
        utils["five_hour"] is not None and utils["five_hour"] + burn["five_hour"] >= threshold
    )
    weekly_trip = (
        utils["seven_day"] is not None and utils["seven_day"] + burn["seven_day"] >= weekly_thr
    )
    ordinary_trip = session_trip or (cap is None and weekly_trip)
    cap_trip = cap is not None and weekly_trip
    if not (ordinary_trip or cap_trip):
        proj = max(burn.values())
        print(
            f"tick: active {row['email']} at {hot:.0f}%"
            + (f" (+{proj:.0f} since last tick)" if proj > 0 else "")
            + f" — session below {threshold:.0f}%"
            + (f", weekly below cap {cap}" if cap is not None else "")
            + ", no flip"
        )
        return
    # F-C3: the audit trail records the value that actually TRIPPED — the weekly reading on a
    # cap-only trip; the hottest window when the ordinary threshold fired (legacy shape kept).
    cap_only = cap_trip and not ordinary_trip
    at_pct = utils["seven_day"] if cap_only else hot
    projected = " (projected — reading + burn since the last tick)" if max(burn.values()) > 0 else ""
    at_desc = (
        f"at weekly {utils['seven_day']:.0f}% ≥ cap {cap} (operator reserve, caps.json){projected}"
        if cap_only
        else f"at {hot:.0f}%{projected}"
    )
    pick = _validated_pick(accounts, {row["email"]}, verbose=True)
    if pick is None:
        # Every sibling is walled/cap-walled/unreadable/credential-less: nothing to flip to. The
        # ≥85% advisory loop below is the recourse (Telegram + drain mail), exactly as before.
        print(
            f"tick: active {row['email']} {at_desc} but NO successor has headroom — "
            + "; ".join(_flip_exclusion_reasons(accounts, {row["email"]}, threshold))
        )
        return
    slug, email = pick
    # A TRIP IS A WALL, NEVER CHURN (operator directive 2026-09-03: "session limits immediately
    # stop all running agents … I don't want my running agents stopped while I pay for 4 Max
    # accounts"): the dwell never holds a trip flip. Today's log had mob@ cap-walled and `flip to
    # ob within dwell (30m of the last flip) — holding` until the operator switched by hand. Churn
    # is already prevented where it belongs — the candidate predicate never targets a sibling at
    # or over the threshold or without 5h budget — so the dwell has nothing left to protect here.
    if _flip_active(slug, at_pct=at_pct, ignore_dwell=True):
        print(f"tick: flipped active {row['email']} -> {email} ({slug}) {at_desc}")
    else:
        print(f"tick: flip {row['email']} -> {email} ({slug}) withheld (see stderr)")


def _active_account_walled(accounts: list[dict], threshold: float) -> tuple[bool, dict | None]:
    """Is the account the fleet's ``active`` pointer resolves to (AFTER this tick's flip leg)
    walled? Uses the ONE shared exclusion predicate (:func:`_flip_churn_excluded`) — a pointer
    sitting on a ≥threshold / cap-walled / ≥100 account IS the real "no active quota left"
    signal, and it stays true across a pause (the flip was held) or a no-successor tick (nothing
    to flip to). Unresolvable pointer / no reading → not-walled: never cry wolf."""
    active_slug = _resolve_active()
    row = (
        next((r for r in accounts if active_slug in (r.get("slugs") or [])), None)
        if active_slug
        else None
    )
    if row is None:
        return False, None
    utils = {
        key: (w.get("utilization") if isinstance(w, dict) else None)
        for key, w in (("five_hour", row.get("five_hour")), ("seven_day", row.get("seven_day")))
    }
    if all(v is None for v in utils.values()):
        return False, row  # no reading → no claim
    return _flip_churn_excluded(utils, row.get("weekly_cap"), threshold), row


def _promised_resume(stamp: Path) -> float | None:
    """The resume epoch the current wall episode's message promised, or None.

    The stamp's CONTENT carries it; no other reader consumes that content (``quota_stop.py``
    tests ``.exists()``, the latch reads mtime), which is why it can hold this without a new
    file. None whenever there is no live promise to break: an unreadable or non-numeric stamp,
    the ``0`` written when no relief time could be given, and — deliberately — a value that is
    not in the future OF THE STAMP ITSELF. That last case is how stamps written before this
    field existed migrate silently: they hold their own write time, which is never later than
    their mtime, so they fall through to the week-long re-arm instead of re-firing every tick.
    """
    try:
        promised = float(stamp.read_text(encoding="utf-8").strip())
        written = stamp.stat().st_mtime
    except (OSError, ValueError):
        return None
    return promised if promised > written else None


def _urgent_drain_pct() -> float:
    """The SESSION line at which, with NO eligible successor, every repo is told to stop
    gracefully and hook itself to the next session reset. Default **90** (operator rule
    2026-09-03: "when we see 90% session limit reached and if no account is available we must
    send an URGENT mail to repos"). Below the flip line on purpose: the flip at 95 is the
    remedy when a successor exists; this is the remedy when none does, and it needs the five
    points of runway a graceful stop takes. ``ROTATE_URGENT_DRAIN_PCT`` overrides."""
    return _env_float("ROTATE_URGENT_DRAIN_PCT", 90.0)


def _next_session_relief(
    accounts: list[dict], active_email: str, now: float
) -> tuple[float, str, str] | None:
    """When will the fleet next have an eligible account? ``(epoch, email, window)`` or None.

    Prefers the SOONEST 5h-window reset among siblings that are blocked ONLY by their session
    (weekly under its cap and under 100) — those become eligible the moment their session
    resets, which is hours, not days. Falls back to the soonest WEEKLY reset among siblings
    blocked by their weekly window. None when no sibling has a reset time at all. A reset
    already in the past is skipped (a stale cached row); the active account is never a
    candidate for its own relief.
    """
    session_wait: list[tuple[float, str]] = []
    weekly_wait: list[tuple[float, str]] = []
    for row in accounts:
        email = str(row.get("email") or "")
        if not email or email == active_email:
            continue
        # Bind THEN narrow: `x.get(k) if isinstance(x.get(k), dict) else {}` is two lookups and
        # mypy cannot narrow through them (3 union-attr errors this function carried since it
        # was written yesterday).
        fh, wk = row.get("five_hour"), row.get("seven_day")
        fh = fh if isinstance(fh, dict) else {}
        wk = wk if isinstance(wk, dict) else {}
        wu = wk.get("utilization")
        cap = row.get("weekly_cap")
        weekly_blocked = (isinstance(wu, (int, float)) and wu >= 100.0) or (
            cap is not None and isinstance(wu, (int, float)) and wu >= float(cap)
        )
        fr = fh.get("resets_at_epoch")
        wr = wk.get("resets_at_epoch")
        if not weekly_blocked and isinstance(fr, (int, float)) and float(fr) > now:
            session_wait.append((float(fr), email))
        elif weekly_blocked and isinstance(wr, (int, float)) and float(wr) > now:
            weekly_wait.append((float(wr), email))
    if session_wait:
        epoch, email = min(session_wait)
        return epoch, email, "session"
    if weekly_wait:
        epoch, email = min(weekly_wait)
        return epoch, email, "weekly"
    return None


def _drain_trigger_reason(row: dict, session_pct: float | None, walled: bool) -> str:
    """WHICH window actually triggered this notice, with its number and its UNIT.

    The notice used to hardcode "its 5-hour session window" and print whatever `session_pct` held,
    so a WEEKLY wall reported the SESSION number: the 2026-09-04T12:59Z notice said the account was
    "at 10% of its 5-hour session window" and ordered an immediate graceful stop — a number arguing
    against its own instruction (fabrik-lib 01M1P86NZ2DEDGKJ62CS3K346A raised the ambiguity; the
    wrong-window half was found reading it). "CONSUMED" is explicit because "at 90%" and "at 10%"
    ordered a stop on consecutive days and read in opposite directions.
    """
    wk = row.get("seven_day") if isinstance(row.get("seven_day"), dict) else {}
    wu = wk.get("utilization") if isinstance(wk, dict) else None
    cap = row.get("weekly_cap")
    if walled:
        if isinstance(wu, (int, float)):
            if cap is not None and float(wu) < 100.0:
                return (
                    f"its weekly window is {float(wu):.0f}% CONSUMED, at or over the "
                    f"{float(cap):.0f}% reserve we set for it in caps.json"
                )
            return f"its weekly window is {float(wu):.0f}% CONSUMED (walled)"
        return "it is walled with no readable weekly figure"
    if session_pct is not None:
        return f"its 5-hour session window is {float(session_pct):.0f}% CONSUMED"
    return "it has no readable quota figure"


def _urgent_drain_message(active_email: str, reason: str, relief: tuple[float, str, str] | None) -> str:
    """The operator's wording, with the concrete time the repos must hook themselves to."""
    head = (
        f"URGENT — fleet quota: the active account {active_email} cannot continue — {reason} — "
        "and NO other account is available to switch to (every sibling is session-exhausted, "
        "weekly-walled or cap-walled). STOP YOUR WORK ASAP, GRACEFULLY: reach a "
        "commit-and-push checkpoint now, then stop."
    )
    if relief is None:
        # The board's URL is env-derived (the dashboard's own knobs), never a literal — the
        # localhost ban this repo enforces applies to message text too, and rightly: a hardcoded
        # URL here would drift the moment the port moves.
        board = os.getenv(
            "QUOTA_DASH_URL",
            f"http://{os.getenv('QUOTA_DASH_HOST', '127.0.0.1')}:{os.getenv('QUOTA_DASH_PORT', '5051')}/",
        )
        return head + (
            " No sibling reports a reset time, so no resume time can be given — wait for the "
            f"operator or re-check the quota board ({board}) before resuming."
        )
    epoch, email, window = relief
    resume = int(epoch) + 60
    local = datetime.fromtimestamp(resume).strftime("%a %d %b %H:%M %Z").strip()
    utc = datetime.fromtimestamp(resume, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return head + (
        f" NEXT WINDOW: {email}'s {window} window resets at {local} (UTC {utc}); the earliest "
        f"sensible resume is one minute later, epoch {resume}."
        " ⚠️ A FOLLOW-UP NOTICE IS THE MECHANISM — another message like this one will arrive"
        " carrying the next time to try, and that is what wakes you. A self-scheduled timer is a"
        " COURTESY, not coverage: a background `sleep` is session-scoped and dies with the very"
        " stop it is timing (measured — a repo armed one for 21:31Z and resumed 15.5h late, only"
        f" when the next notice landed). If you want one anyway: `sleep $(( {resume} -"
        " $(date +%s) ))`. Relief is EXPECTED, not promised: the rotation switches to that account"
        " only if it really has headroom when the window turns."
    )


def _fleet_active_wall_advisory(accounts: list[dict], now: float, threshold: float) -> None:
    """Fire ONE advisory only when the fleet's ACTIVE account is walled with no auto-relief.

    Under one-active-pointer-for-all-projects (memory rotation_continuity_over_binding), an
    individual account crossing the threshold is a NON-event — the flip leg above re-points to a sibling
    with headroom and every agent keeps working. The "reach a checkpoint before the wall"
    advisory is TRUE only when the account agents are ACTUALLY using is walled and this tick
    could not relieve it (no successor with headroom, or the operator's pause held the flip).
    (Historical: until 2026-09-03 a flip could be held by the 30-min dwell; trips are dwell-exempt now,
    D-104, so this branch is reachable only through the pause.) A flip merely held while a headroom sibling exists is NOT
    exhaustion — relief is minutes away — so it is suppressed. Firing per-account on every ≥85%
    crossing was both spam — 10 near-identical mails on 2026-08-25, trade-intelligence 01M0YAB2 —
    and a false alarm. Fire once on entry to the walled state; suppress while it persists (the
    latch); re-arm the instant relief arrives, on a future-dated (clock-skew) stamp, or after a
    week of unbroken exhaustion. Dedup is epoch-free: no reset-timestamp key to churn (the
    51181918 defect class — a raw sliding reset epoch re-fired every tick, mob@ 8x at a steady
    95%). (2026-08-26, operator directive: "only fire when we don't have any active quota left".)"""
    walled, row = _active_account_walled(accounts, threshold)
    # URGENT tier (operator rule 2026-09-03): the active account's SESSION at/over 90 with no
    # eligible successor is the same emergency as the wall, five points earlier — the runway a
    # graceful stop needs. Same latch, same re-arm, one message per episode.
    session_pct = None
    if row is not None and isinstance(row.get("five_hour"), dict):
        v = row["five_hour"].get("utilization")
        session_pct = float(v) if isinstance(v, (int, float)) else None
    urgent = session_pct is not None and session_pct >= _urgent_drain_pct()
    stamp = _fleet_exhaustion_stamp()
    if row is None or not (walled or urgent):
        stamp.unlink(missing_ok=True)  # relief arrived (flip/reset) → re-arm for the next wall
        return
    # Relief IS coming when a headroom successor exists AND rotation is not paused: the active
    # account is walled only because the flip is held by the transient 30-min dwell, not because
    # the fleet is out of quota. Firing here would reintroduce the exact false alarm this change
    # removed — the hysteresis window (a flip, then the new active burns to ≥threshold inside the
    # dwell while a sibling still has headroom; the reachable state test_fleet_tick_flips_at_
    # threshold's second tick sets up). The operator's PAUSE is the exception: it deliberately
    # froze the safety valve, so a walled active under pause IS a real stall worth the warning.
    if not _switch_paused() and _validated_pick(accounts, {row["email"]}) is not None:
        stamp.unlink(missing_ok=True)  # transient dwell hold, not exhaustion → re-arm
        return
    # Latch: fire once per wall episode. But a latch is not forever — a WEEK of unbroken
    # exhaustion is a fact worth repeating (restores the per-account "week without a word" re-arm
    # the old code carried; a presence-only latch otherwise silences the operator for good if the
    # walled active account never dips below threshold across a reset). A FUTURE-dated stamp (WSL
    # suspend/resume, NTP — the _last_switch_ts clock-skew class) is INVALID and must not silence
    # a live wall until the wall clock catches up: treat it as expired and speak now.
    try:
        age = now - stamp.stat().st_mtime
    except OSError:
        age = None
    # …and a THIRD re-arm: when the resume instant this episode PROMISED has come and gone
    # while the wall still stands. The message orders every repo to sleep until a named epoch
    # and not to poll; if relief does not arrive, the latch would keep the fleet silent until
    # the week-long re-arm. Measured 2026-09-04: one message at 20:55 UTC named 21:31, nothing
    # switched, and the fleet sat walled and unwarned for 10h41m — 47 "NO successor has
    # headroom" ticks — until the operator flipped the pointer by hand.
    promised = _promised_resume(stamp)
    latched = stamp.exists() and not (
        (age is not None and (age > _FLEET_WALL_REARM_S or age < -_CLOCK_SKEW_TOLERANCE_S))
        or (promised is not None and now >= promised)
    )
    if latched:
        return  # already advised for this wall episode — one fact, one message
    hot = max(
        (
            w["utilization"]
            for w in (row.get("five_hour"), row.get("seven_day"))
            if isinstance(w, dict) and isinstance(w.get("utilization"), (int, float))
        ),
        default=0.0,
    )
    relief = _next_session_relief(accounts, str(row["email"]), now)
    msg = _urgent_drain_message(
        str(row["email"]), _drain_trigger_reason(row, session_pct, walled), relief
    )
    _tick_telegram(msg)
    repos = _mailbox_repos()  # a fleet-wide wall concerns every project → broadcast
    if repos:
        _drain_mail(repos, "URGENT fleet quota — stop gracefully, hook to the next reset\n\n" + msg)
    try:
        # CONTENT = the resume epoch this message promised, so the latch can re-arm when the
        # promise comes due (see _promised_resume). "0" when no relief time could be given.
        stamp.write_text(str(int(relief[0]) + 60 if relief else 0), encoding="utf-8")
        os.utime(stamp, (now, now))
    except OSError:
        pass
    _ledger_append(
        {
            "event": "fleet-active-wall",
            "ts": now,
            "account": row["email"],
            "at_pct": hot,
            "tier": "walled" if walled else "urgent-90",
            "resume_epoch": (int(relief[0]) + 60) if relief else None,
        }
    )
    print(
        f"tick: {'ACTIVE-WALL' if walled else 'URGENT-DRAIN'} advisory {row['email']} at "
        f"{hot:.0f}%" + (f" — resume after {relief[1]}'s {relief[2]} reset" if relief else "")
    )


def _fleet_tick_inner(dirs: list[Path]) -> int:
    """The tick, fleet-shaped: telemetry + the POINTER FLIP + the fleet wall advisory.

    REWRITTEN, not reused — _tick_inner's frame installs credential files, which fleet mode
    never does. The flip leg (operator redesign 2026-08-15 — one active account for ALL
    projects): resolve the ``active`` pointer; missing/dangling → flip to the best account
    immediately (dwell-exempt repair — holding a dangling pointer is a fleet outage); the
    active account ≥ROTATE_THRESHOLD (default 95) on EITHER window → flip to the account with
    the most weekly-then-session headroom among credentialed, un-walled siblings. The flip
    moves zero credential bytes and is refused by the pause marker + the 30-min dwell (inside
    :func:`_flip_active`); telemetry and the wall advisory below run REGARDLESS (T01 semantics —
    pause holds action, never signal). The advisory is FLEET-WIDE, not per-account: it fires
    ONLY when the post-flip active account is walled with no auto-relief (no successor, or the
    pause held the flip) — see :func:`_fleet_active_wall_advisory`. A single account crossing
    the threshold while a sibling has headroom is a non-event (the flip relieved it) and fires nothing.
    """
    threshold = _rotate_threshold()
    drain_thr = _env_float("ROTATE_DRAIN_THRESHOLD", 85.0)
    now = _now()
    accounts, pending = _fleet_account_rows(dirs, allow_pings=True)
    _fleet_flip_leg(dirs, accounts, threshold)
    # Unmissable keepalive (2026-08-18): the weekly cron slot can be slept through — the tick
    # cannot, while WSL is up at all. quiet=True: the fresh-dir lines would spam every 5 min;
    # due pings and failures still print + alert.
    _keepalive_sweep(dirs, now, quiet=True)
    for row in accounts:
        windows = [w for w in (row["five_hour"], row["seven_day"]) if isinstance(w, dict)]
        utils = [
            w["utilization"] for w in windows if isinstance(w.get("utilization"), (int, float))
        ]
        stale = f" (cached {row['age_s'] / 3600:.0f}h ago)" if row["source"] == "cache" else ""
        if not utils:
            print(f"tick: {row['email']} — no quota reading (no fresh token, nothing cached)")
            continue
        hot = max(utils)
        status = "ok" if hot < drain_thr else "at/over drain threshold"
        print(f"tick: {status} — {row['email']} at {hot:.0f}%{stale}")
    # The advisory is FLEET-WIDE, not per-account: fire ONLY when the active account (the one
    # every agent is using) is walled with no auto-relief. A single account crossing the threshold is a
    # non-event — the flip leg above already re-pointed to a sibling with headroom.
    _fleet_active_wall_advisory(accounts, now, threshold)
    for warn in _fleet_row_warnings(accounts):
        print(warn)
    for p in pending:
        print(f"tick: {p['slug']} pending-login — excluded from account telemetry")
    _ledger_rotate()
    return 0


def _keepalive_ping(cfg_dir: Path) -> bool:
    """One ``claude -p ping`` bound to *cfg_dir* — the in-place SOLE-OWNER refresh (the
    youtube-proven path): CLAUDE_CONFIG_DIR + CLAUDE_QUOTA_HOME both point at the dir itself,
    so the CLI rolls THIS dir's own chain. NOT the retired --touch temp-dir copy pattern —
    no credential byte is read, copied, or written by this script."""
    env = os.environ.copy()
    env["CLAUDE_CONFIG_DIR"] = str(cfg_dir)
    env["CLAUDE_QUOTA_HOME"] = str(cfg_dir)
    env["CLAUDE_MESH_HEADLESS"] = "1"
    env["CLAUDE_SOUND_NO_REVIVE"] = "1"
    env.setdefault("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")
    _with_claude_on_path(env)  # cron PATH lacks ~/.local/bin → bare spawn would FileNotFoundError
    try:
        timeout = int(os.environ.get("KEEPALIVE_TIMEOUT", "150"))
    except ValueError:
        timeout = 150
    try:
        p = subprocess.run(
            ["claude", "-p", "ping"],
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return p.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _keepalive_sweep(dirs: list, now: float, quiet: bool = False) -> tuple[int, int]:
    """The keepalive core: ping every dir whose credential mtime exceeds the idle ceiling.
    Shared by the weekly cron command AND the 5-minute tick (2026-08-18: the Monday 06:20
    cron missed its slot because WSL was asleep — cron has no catch-up, so a one-shot weekly
    schedule can silently skip; the tick folding this in makes the idle check unmissable
    while WSL is up at all: the stat is ~free, the ping fires only when a dir is >7d idle)."""
    pinged = failures = 0
    for d in dirs:
        try:
            idle_s = now - (d / ".credentials.json").stat().st_mtime
        except OSError:
            if not quiet:
                print(f"keepalive: {d.name} — no credentials yet (pending /login), skipped")
            continue
        skewed = idle_s < -_CLOCK_SKEW_TOLERANCE_S
        if not skewed and idle_s <= _KEEPALIVE_MAX_IDLE_S:
            if not quiet:
                print(f"keepalive: {d.name} — fresh ({idle_s / 86400:.1f}d idle), no ping needed")
            continue
        idle_desc = (
            "future-skewed mtime, treated as due" if skewed else f"{idle_s / 86400:.1f}d idle"
        )
        pinged += 1
        if _keepalive_ping(d):
            print(f"keepalive: {d.name} — pinged ok ({idle_desc})")
        else:
            failures += 1
            print(f"keepalive: {d.name} — PING FAILED ({idle_desc}) — alerted")
            _tick_telegram(
                f"keepalive FAILED for fleet dir {d.name} ({idle_desc}) — its"
                " refresh chain risks the ~30-day idle lapse; run one claude turn in that dir"
                " (or ONE /login if it already lapsed)"
            )
    return pinged, failures


def _cmd_keepalive() -> int:
    """Idle-chain keepalive: ping every fleet dir whose credential MTIME (never content — the
    CLI rewrites the file on each refresh, so mtime IS last-use) is >7 days old, so no chain
    ever reaches the ~30-day idle lapse. Cron-safe: one line per dir on stdout, rc 0 when
    every stale dir refreshed (or none was stale), rc 1 when any ping failed — a failed ping
    also alerts via mesh-notify (the ci_health_probe invocation, via _tick_telegram)."""
    now = _now()
    dirs = _fleet_dirs()
    if not dirs:
        print(f"keepalive: no fleet dirs under {_fleet_root()} — nothing to do")
        return 0
    pinged, failures = _keepalive_sweep(dirs, now, quiet=False)
    print(f"keepalive: done — {pinged} pinged, {failures} failed")
    return 1 if failures else 0


def _live_email(timeout_s: float = 10.0) -> str | None:
    """The LIVE token's account email, from Anthropic's own OAuth profile endpoint — the only
    identity signal that cannot lie (token-match misses after a refresh, newer creds omit the
    org, and the marker goes stale on out-of-band logins: all three failed together on
    2026-08-13 and mis-filed ob@'s tokens into the sarp store). None on any failure — callers
    must treat that as "unknown", never guess. Never emits token bytes."""
    tok = _read_access_token(ACTIVE_CREDS)
    if tok is None:
        return None
    try:
        import urllib.request

        req = urllib.request.Request(
            "https://api.anthropic.com/api/oauth/profile",
            headers={"Authorization": f"Bearer {tok}", "anthropic-beta": "oauth-2025-04-20"},
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            data = json.load(r)
        email = (data.get("account") or {}).get("email")
        return email if isinstance(email, str) and "@" in email else None
    except Exception:
        return None


def _store_for_email(email: str, accounts: list[Path]) -> Path | None:
    """Map an account email to its snapshot dir by the store-naming convention
    (<local-part>-<domain-dashed>-...): unique prefix match on the email's local part.
    None when zero or multiple stores match — ambiguity is never guessed."""
    local = email.split("@", 1)[0].lower()
    hits = [
        a for a in accounts if a.name.lower() == local or a.name.lower().startswith(local + "-")
    ]
    return hits[0] if len(hits) == 1 else None


def _cmd_drift_check() -> int:
    """Capture ONLY when the live token has diverged from the stored snapshot.

    The hourly/SessionStart trigger: read-only and silent in the common case, so it can run on
    every session start without cost. Always exits 0 — a drift-check must never fail a hook.
    """
    live_tok = _read_access_token(ACTIVE_CREDS)
    target = _active_account()
    if live_tok is None or target is None:
        return 0  # nothing resolvable to compare — quiet no-op
    # IDENTITY GATE (2026-08-13 mis-filing incident): before writing anything, ask the API whose
    # token this actually is. A verified email that maps to a DIFFERENT store retargets the
    # capture; a verified email with no matching store, or an unreachable profile endpoint,
    # SKIPS the capture — filing under a guessed name corrupts a sibling account's store, which
    # is strictly worse than one missed hourly capture.
    email = _live_email()
    if email is None:
        sys.stderr.write("claude_rotate: drift-check skipped — live identity unverifiable\n")
        return 0
    # ONBOARDING (2026-08-14 live gap): map against every store DIR, not only those that
    # already hold credentials — _list_accounts excludes credential-less dirs, so a
    # first-ever login for a new account was refused ("no store for live account") and its
    # pair quarantined. A store dir is the operator's declaration that the account belongs
    # to the pool; the identity gate still proves WHOSE token it is before writing.
    try:
        all_stores = sorted(d for d in ACCOUNTS_DIR.iterdir() if d.is_dir())
    except OSError:
        all_stores = _list_accounts()
    verified = _store_for_email(email, all_stores)
    if verified is None:
        sys.stderr.write(
            f"claude_rotate: drift-check skipped — no store for live account {email}\n"
        )
        return 0
    if verified != target:
        sys.stderr.write(
            f"claude_rotate: capture RETARGETED {target.name} -> {verified.name} "
            f"(live token belongs to {email})\n"
        )
        if _cmd_capture_current(into=verified) != 0:
            sys.stderr.write("claude_rotate: retargeted capture FAILED — snapshot is stale\n")
        else:
            try:
                _secure_write(ACTIVE_MARKER, verified.name.encode())
                sys.stderr.write(f"claude_rotate: active marker repaired -> {verified.name}\n")
            except OSError:
                pass
        return 0
    # Compare the WHOLE credential blob, never just the access token: the live incident
    # (2026-08-10) was a stale REFRESH token, and the refresh token rotates independently
    # of the short-lived access token — an accessToken-only compare would see "in sync"
    # while the snapshot carried a dead refresh token (review finding).
    try:
        if (target / ".credentials.json").read_bytes() == ACTIVE_CREDS.read_bytes():
            return 0  # byte-identical — genuinely in sync
    except OSError:
        pass  # unreadable either side → fall through to capture (fail toward freshness)
    if _cmd_capture_current() != 0:
        # Never fail a hook, but never hide a failed capture either: the cron log is the
        # only place an operator would ever see this (review finding).
        sys.stderr.write("claude_rotate: drift detected but capture FAILED — snapshot is stale\n")
    return 0


def _current_usage_cache_path() -> Path:
    """Single-key current-account usage cache (SEPARATE from the fleet cache — different shape,
    different writer: this one is keyed by nothing, it is THE one account's last good reading)."""
    return _rotate_state_dir() / "current-usage-cache.json"


def _capture_current_usage() -> dict | None:
    """Quota-free live usage snapshot of the CURRENT account (``CLAUDE_CONFIG_DIR`` or
    ``~/.claude``), persisted to the current-usage cache on success. Returns the windows dict or
    None; NEVER raises.

    The stored access token is only reliably fresh right AFTER a claude call (the CLI rolls the
    refresh chain itself; the direct ``/v1/oauth/token`` refresh is Cloudflare-403'd — see
    ``_keepwarm_refresh``), which is why ``run_claude`` calls this post-call: each real sysadmin
    claude run leaves behind a current headroom reading for the governor, at zero quota cost
    (``api/oauth/usage`` is metadata, not a completion)."""
    try:
        cfg_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
        tok = _read_access_token(cfg_dir / ".credentials.json")
        if not tok:
            return None
        windows = _usage_windows(_oauth_get("usage", tok))
        if windows is None:
            return None
        _write_json_atomic(_current_usage_cache_path(), {"ts": time.time(), **windows})
        return windows
    except Exception:  # noqa: BLE001 — telemetry capture must never break a claude call/probe
        return None


def _signal_governor_capped(final_text: str) -> None:
    """Best-effort reactive-cap wiring: pipe a final still-limited claude response to
    ``quota_governor.py mark-capped`` so the governor sheds ROUTINE work until the window resets.
    This is the backstop that makes the governor's bootstrap-on-unknown routing safe on the
    single-key VPS. No-op when the governor is not co-located; never raises."""
    gov = Path(__file__).resolve().parent / "quota_governor.py"
    if not gov.is_file():
        return
    try:
        subprocess.run(
            [sys.executable, str(gov), "mark-capped"],
            input=final_text,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception:  # noqa: BLE001 — the cap signal is advisory; the call result stands
        pass


def _cmd_probe_current(as_json: bool) -> int:
    """Governor headroom source for a SINGLE-KEY host (the VPS): the CURRENT account
    (``CLAUDE_CONFIG_DIR`` or ``~/.claude``) in the one-account fleet payload shape the governor
    reads — ``active="current"``, ``slugs=["current"]``.

    Reading order (canary-corrected 2026-08-30): LIVE first — a quota-free ``api/oauth/usage`` GET
    of the stored token (works whenever the token is fresh, i.e. shortly after any claude call);
    else the CURRENT-USAGE CACHE written by ``_capture_current_usage`` after every real claude run,
    accepted within ``PROBE_CACHE_MAX_AGE_S`` (default 7200s — the 15-min proactive-check cron
    keeps it minutes old in steady state); else ``source="unavailable"`` with null windows. The
    governor treats unavailable as bootstrap-run (its single-key semantics), so a cold start can
    never wedge the loop.

    ``--status`` fleet mode only lights up with scaffolded fleet dirs, and the non-fleet
    manager-accounts listing carries only PARKED snapshots (null telemetry) — so a single-key host
    needs this probe to have ANY headroom source. weekly_cap stays None (the operator's
    authoritative cap needs an identity the usage GET does not carry; reserve_pct + the reactive
    cap are the single-key conservation path). Fail-soft throughout; never raises."""
    row: dict = {
        "email": "current",
        "slugs": ["current"],
        "five_hour": None,
        "seven_day": None,
        "weekly_cap": None,
        "cap_walled": False,
        "source": "unavailable",
    }
    windows = _capture_current_usage()
    if windows is not None:
        row.update(windows)
        row["source"] = "live"
    else:
        try:
            cached = json.loads(_current_usage_cache_path().read_text())
            age = time.time() - float(cached["ts"])
            max_age = float(os.environ.get("PROBE_CACHE_MAX_AGE_S") or 7200.0)
            if 0 <= age <= max_age:
                for key in ("five_hour", "seven_day", "model_windows"):
                    if cached.get(key) is not None:
                        row[key] = cached[key]
                row["source"] = "cache"
                row["age_s"] = round(age, 1)
        except Exception:  # noqa: BLE001 — a bad/absent cache reads as unavailable, never raises
            pass
    payload = {"active": "current", "accounts": [row]}
    if as_json:
        print(json.dumps(payload, indent=1))
        return 0

    def _p(w: object) -> str:
        return (
            f"{w['utilization']:.0f}%"
            if isinstance(w, dict) and isinstance(w.get("utilization"), (int, float))
            else "-"
        )

    print(
        f"current account: session {_p(row.get('five_hour'))}  "
        f"weekly {_p(row.get('seven_day'))}  ({row['source']})"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI. Two modes:

    Auto-rotation passthrough (for the keepalive shim / any wrapper):
        ``python3 claude_rotate.py claude -p ping`` → runs claude, rotates on usage-limit,
        passes output + returncode through.

    Manual account management on WSL (switch the active account, then reload the VS Code
    workspace — no VS Code restart):
        ``python3 claude_rotate.py --list``            list accounts, mark the active one
        ``python3 claude_rotate.py --switch <name>``   set active to a named account/email/prefix
        ``python3 claude_rotate.py --next``            cycle to the next other account
        ``python3 claude_rotate.py --capture-current`` snapshot the live creds into the active
                                                       account (keeps the store un-stale)
        ``python3 claude_rotate.py --drift-check``     capture only if the live token diverged

    Fleet dirs (the login-once architecture — one config dir, one OAuth chain, one login):
        ``--new-dir <slug> <email> [--project /opt/<repo>]``  scaffold a dir + its carrier
        ``--sync-mcp``      re-push the MCP roster into every fleet dir
        ``--sync-shared``   …and the settings.json copy with it
        ``--keepalive``     one in-place ``claude -p ping`` per fleet dir idle >7 days
                            (weekly cron; rc 1 + mesh-notify alert on any failed ping)

    Once ≥1 fleet dir exists, ``--status``, ``--tick`` and ``--switch`` switch to the fleet
    view: per-ACCOUNT dirs (pinned identity), quota from the freshest dir's token or the cached
    last-known row with age, one ``active`` pointer symlink every session follows. The tick
    FLIPS that pointer to the account with the most quota headroom when the active one crosses
    ROTATE_THRESHOLD (pause marker + 30-min dwell respected); ``--switch <slug>`` is the manual,
    pause-exempt flip. A flip moves ZERO credential bytes; ≥85% still fires the per-account
    advisory when no successor has headroom.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        sys.stderr.write(
            "usage: claude_rotate.py [--list | --switch <name> | --next | --capture-current"
            " | --drift-check | --status | --probe-current | --tick | --touch | --pause-switch"
            " | --resume-switch | --new-dir <slug> <email> [--project <repo>]"
            " | --sync-mcp | --sync-shared | --keepalive | <claude> args...]\n"
        )
        return 2
    if args[0] == "--list":
        return _cmd_list()
    if args[0] == "--switch":
        if len(args) < 2:
            sys.stderr.write("usage: claude_rotate.py --switch <account-name-or-email>\n")
            return 2
        return _cmd_switch(args[1])
    if args[0] == "--next":
        return _cmd_next()
    if args[0] == "--capture-current":
        return _cmd_capture_current()
    if args[0] == "--drift-check":
        return _cmd_drift_check()
    if args[0] == "--status":
        return _cmd_status(as_json="--json" in args[1:])
    if args[0] == "--probe-current":
        return _cmd_probe_current(as_json="--json" in args[1:])
    if args[0] == "--tick":
        return _cmd_tick()
    if args[0] == "--touch":
        return _cmd_touch(args[1] if len(args) > 1 and not args[1].startswith("-") else None)
    if args[0] == "--new-dir":
        rest, opts, bad = _pull_opts(args[1:], ("--project", "--from"))
        if bad or len(rest) != 2:
            sys.stderr.write(
                "usage: claude_rotate.py --new-dir <slug> <account-email>"
                " [--project /opt/<repo>] [--from <slug|path>]\n"
            )
            return 2
        return _cmd_new_dir(rest[0], rest[1], opts.get("--project"), opts.get("--from"))
    if args[0] == "--keepalive":
        return _cmd_keepalive()
    if args[0] in ("--sync-mcp", "--sync-shared"):
        rest, opts, bad = _pull_opts(args[1:], ("--from",))
        if bad or rest:
            sys.stderr.write(f"usage: claude_rotate.py {args[0]} [--from <slug|path>]\n")
            return 2
        return _cmd_sync_shared(
            include_settings=args[0] == "--sync-shared", source=opts.get("--from")
        )
    if args[0] == "--pause-switch":
        # A broken state dir is exactly the situation the fail-closed messages send the operator
        # here to fix — report it, never traceback out of main().
        try:
            (_rotate_state_dir() / "switch-paused").touch()
        except _STATE_DIR_ERRORS:
            sys.stderr.write(
                "claude_rotate: cannot write the rotate state dir — pause NOT recorded "
                "(rotation is already refusing fail-closed while it is unreadable)\n"
            )
            return 1
        print(
            "auto-switch PAUSED — ticks keep telemetry + drain warnings; no account is"
            " installed until --resume-switch"
        )
        return 0
    if args[0] == "--resume-switch":
        try:
            (_rotate_state_dir() / "switch-paused").unlink()
        except FileNotFoundError:
            pass  # already resumed
        except _STATE_DIR_ERRORS:
            sys.stderr.write(
                "claude_rotate: cannot read/write the rotate state dir — resume NOT applied; "
                "rotation stays refused (fail-closed) until the state dir is fixed\n"
            )
            return 1
        print("auto-switch RESUMED")
        return 0
    env = os.environ.copy()
    env.setdefault("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")
    try:
        timeout = int(os.environ.get("CLAUDE_ROTATE_TIMEOUT", "120"))
    except ValueError:
        timeout = 120
    if timeout <= 0:
        timeout = 120
    # Resolve cwd defensively OUTSIDE the run_claude try: os.getcwd() raises if the process's cwd
    # was unlinked mid-run, and we don't want that mislabeled as a claude exec failure below. Fall
    # back to "/" (always traversable) — claude-run.sh already cd's to a valid dir, so this is a race
    # backstop. Keeping it out of the try is what makes the "only a spawn OSError" comment below true.
    try:
        cwd = os.getcwd()
    except OSError:
        cwd = "/"
    # CLI passthrough (claude-run.sh → stdin-piping sysadmin scripts): buffer stdin so a
    # rotation retry re-supplies the piped context. Convert the subprocess failure modes into clean
    # exits — the service callers (bot.py/aro-wake) catch these, but the cron/keepalive path is
    # main(), where an uncaught FileNotFoundError (claude bin absent on a mis-provisioned host) or
    # TimeoutExpired (a hung attempt) would otherwise dump a traceback into the cron log.
    try:
        result = run_claude(args, timeout=timeout, cwd=cwd, env=env, buffer_stdin=True)
    except FileNotFoundError:
        sys.stderr.write(f"claude_rotate: claude binary not found: {args[0]!r}\n")
        return 127
    except OSError as e:
        # Other spawn-time failures for the SAME mis-provisioned-host class: PermissionError (claude
        # rsync'd without the exec bit), IsADirectoryError, or "Exec format error" (wrong arch/bad
        # shebang). run_claude's own internals guard their OSErrors, so the only OSError that reaches
        # here is subprocess.run's spawn failure → the child never ran; exit 126, don't traceback.
        sys.stderr.write(
            f"claude_rotate: cannot execute {args[0]!r}: {e.strerror or 'exec error'}\n"
        )
        return 126
    except subprocess.TimeoutExpired:
        sys.stderr.write(f"claude_rotate: claude timed out after {timeout}s\n")
        return 124
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
