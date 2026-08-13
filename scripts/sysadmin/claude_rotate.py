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
import os
import re
import select
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
ACTIVE_CREDS = CLAUDE_DIR / ".credentials.json"
ACCOUNTS_DIR = CLAUDE_DIR / "manager-accounts"
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
                _ledger_append({"event": "switch", "ts": _now(), "to": target.name,
                                "via": "activate"})
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
    """
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
        new_account = (
            _rotate_active_account(avoid=frozenset(tried)) if rotations < max_rotations else None
        )
        if new_account is None:
            break  # no untried account left → give up (all exhausted / <2 accounts)
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
    if died_account is not None and _should_alert_401():
        final = (result.stdout or "") + "\n" + (result.stderr or "")
        host = _hostname()
        if last_target is not None and not is_auth_401(final) and not is_usage_limit(final):
            _notify_telegram(
                f"⚠️ Claude 401 on {host}: account '{died_account}' credentials were dead — "
                f"auto-rotated to '{last_target}' and recovered. (alerts quiet ~12h)"
            )
        else:
            _notify_telegram(
                f"🚨 Claude 401 on {host}: NO working Claude account — all credentials are dead. "
                f"Re-capture a fresh account (claude auth login / claude-manager). (alerts quiet ~12h)"
            )
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
    new_account = _rotate_active_account()
    if new_account:
        match = _find_account(new_account)  # may be None if the snapshot vanished post-rotation
        email = _account_email(match) if match is not None else "?"
        sys.stdout.write(f"rotated active Claude account → {new_account} ({email})\n")
        _reload_hint()
        return 0
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


def _oauth_get(path: str, token: str, timeout_s: float = 15.0) -> dict | None:
    """GET an api/oauth/* resource with a store token. None on ANY failure — a telemetry
    miss must never crash a tick. Never emits token bytes."""
    try:
        import urllib.request
        req = urllib.request.Request(
            f"https://api.anthropic.com/api/oauth/{path}",
            headers={"Authorization": f"Bearer {token}",
                     "anthropic-beta": "oauth-2025-04-20"})
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            return json.load(r)
    except Exception:
        return None


def _account_status(store: Path) -> dict:
    """One telemetry row for a snapshot dir: identity + both quota windows. valid=False when
    the stored token no longer answers (dead snapshot → relogin needed)."""
    row: dict = {"name": store.name, "store": str(store), "valid": False, "email": None,
                 "five_hour": None, "seven_day": None, "refresh_expires_at_epoch": None}
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
        row[key] = {"utilization": float(u),
                    "resets_at_epoch": _iso_to_epoch(w.get("resets_at"))}
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
    return {"accounts": out, "live": live}


def _cmd_status(as_json: bool) -> int:
    pay = _status_payload()
    if as_json:
        print(json.dumps(pay, indent=1))
        return 0
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
            print(f"{mark} {r['name']:32} parked — quota unknown until used"
                  f" (refresh token valid)")
        elif r["valid"]:
            print(f"{mark} {r['email'] or r['name']:32} session {fmt(r['five_hour']):24}"
                  f" weekly {fmt(r['seven_day'])}")
        else:
            print(f"{mark} {r['name']:32} INVALID (relogin needed)")
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
    eligible = [r for r in candidates
                if r.get("valid") and not _walled(r) and r["name"] != current_name]
    if not eligible:
        return None
    far = now + 365 * 86400
    eligible.sort(key=lambda r: (1 if r.get("telemetry") == "unknown-parked" else 0,
                                 (r.get("seven_day") or {}).get("resets_at_epoch") or far,
                                 (r.get("seven_day") or {}).get("utilization", 100.0),
                                 (r.get("five_hour") or {}).get("utilization", 100.0)))
    return eligible[0]["name"]


def _rotate_state_dir() -> Path:
    d = Path(os.environ.get("ROTATE_STATE_DIR") or Path.home() / ".claude" / "state")
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    return d


def _ledger_append(event: dict) -> None:
    try:
        with (_rotate_state_dir() / "rotate-ledger.jsonl").open("a") as fh:
            fh.write(json.dumps(event) + "\n")
    except OSError:
        pass  # the ledger is an audit trail, never a crash source


def _last_switch_ts() -> float | None:
    try:
        lines = (_rotate_state_dir() / "rotate-ledger.jsonl").read_text().splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("event") == "switch":
            ts = e.get("ts")
            return float(ts) if isinstance(ts, (int, float)) else None
    return None


def _mailbox_repos() -> list[str]:
    """Repos that can SURFACE mail (mail.py:157 rule) — enumerated, never hardcoded."""
    out = []
    try:
        entries = sorted(Path("/opt").iterdir())
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
            proc = subprocess.Popen([sys.executable, str(mail), "send", "--to", repo,
                                     "--from", "fabrik", "--kind", "finding", "--ack", "no"],
                                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, text=True)
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
        subprocess.run(["bash", str(sound), "mesh-notify", "quota-rotation",
                        "/opt/fabrik", msg], stdin=subprocess.DEVNULL,
                       capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        pass


def _tick_switch(name: str) -> bool:
    """Install `name`. Closer #3: capture the OUTGOING account's live credentials into its
    own store FIRST — drift-check is hourly, and an hour-stale snapshot holds a superseded
    refresh token (the 2026-08-10 14:37 class, which a 5-minute automatic trigger would
    otherwise replay). Closer #7: the under-lock selector re-validates FITNESS (fresh
    telemetry: valid + un-walled), not just the path — 'TOCTOU-free' must cover the pick."""
    if _cmd_capture_current() != 0:
        sys.stderr.write("claude_rotate: tick pre-switch capture failed — switch aborted"
                         " (a stale outgoing snapshot must not be left behind)\n")
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


def _file_refreshed_credentials(store: Path, payload: dict, verified_email: str | None,
                                provenance: bool = False) -> bool:
    """Atomically install a refreshed credential pair into ITS OWN store — identity-gated
    (the 2026-08-13 mis-filing class must be impossible here): the verified email's local
    part must match the store's name prefix, OR ``provenance=True`` (the pair came from this
    store's own refresh token — OAuth construction proves ownership; used only when the
    verification probe is unreachable). Under ROTATE_LOCK (closer #9 — every sibling
    credential writer holds it); backup to .prev, unique-tmp+rename install."""
    if not provenance:
        local = (verified_email or "").split("@", 1)[0].lower()
        if not local or not store.name.lower().startswith(local + "-"):
            sys.stderr.write(f"claude_rotate: refresh NOT filed — {verified_email!r} does not"
                             f" match store {store.name}\n")
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
    sys.stderr.write(f"claude_rotate: keep-warm unavailable for {store.name} — the token"
                     " grant is CLI-only (403/1010); rotation-through is the warm path\n")
    return False


def _cmd_tick() -> int:
    """The 5-minute rotation daemon tick. Always exits 0 — ENFORCED by the outer guard
    (closer #11), not just documented. Every decision is one printed line."""
    try:
        return _tick_inner()
    except Exception as e:  # noqa: BLE001 — cron-hosted: a broken tick must never look
        #                     like a broken cron; the class+message is the diagnostic
        print(f"tick: INTERNAL ERROR {type(e).__name__}: {e}")
        return 0


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _tick_inner() -> int:
    threshold = _env_float("ROTATE_THRESHOLD", 95.0)
    drain_thr = _env_float("ROTATE_DRAIN_THRESHOLD", 85.0)
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
        hot = max((live.get("five_hour") or {}).get("utilization", 0.0),
                  (live.get("seven_day") or {}).get("utilization", 0.0))
        successor = _pick_successor(rows, live_name, now)
        switch_failed = False
        if hot >= threshold and successor is not None:
            last = _last_switch_ts()
            if last is not None and (now - last) < dwell_s:
                print(f"tick: {hot:.0f}% >= {threshold:.0f}% but within dwell — holding")
                _ledger_append({"event": "tick", "ts": now, "verdict": "dwell-hold"})
                return 0
            if _tick_switch(successor):
                _ledger_append({"event": "switch", "ts": now, "to": successor,
                                "from": live_name, "at_pct": hot})
                _tick_telegram(f"rotated {live_name} -> {successor} at {hot:.0f}%")
                print(f"tick: switched {live_name} -> {successor} at {hot:.0f}%")
                return 0
            # closer #4: a failed switch must be LOUD and must not shadow the drain path —
            # "successor exists but cannot install" burns silently to 100% otherwise
            switch_failed = True
            _tick_telegram(f"quota switch to {successor} FAILED at {hot:.0f}% — "
                           "pool may be draining")
            print(f"tick: switch to {successor} FAILED")
            _ledger_append({"event": "tick", "ts": now, "verdict": "switch-failed"})
        if hot >= drain_thr and (successor is None or switch_failed):
            stamp = _rotate_state_dir() / "drain-stamp"
            try:
                age = now - stamp.stat().st_mtime
            except OSError:
                age = None
            if age is None or age >= 86400:
                resets = [w.get("resets_at_epoch") for r in rows for w in
                          ((r.get("five_hour"), r.get("seven_day")) if r.get("valid") else ())
                          if w and w.get("resets_at_epoch")]
                revive = min(resets) if resets else None
                from datetime import datetime
                revive_s = (datetime.fromtimestamp(revive).strftime("%a %H:%M")
                            if revive else "unknown")
                msg = (f"QUOTA DRAIN: pool exhaustion approaching ({hot:.0f}% on the last "
                       f"eligible account, no installable sibling). Reach a commit-and-push "
                       f"checkpoint NOW; do not start new phases. Work revives at {revive_s}.")
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
    led = _rotate_state_dir() / "rotate-ledger.jsonl"
    try:
        if led.stat().st_size > cap_bytes:
            lines = led.read_text().splitlines(keepends=True)
            led.write_text("".join(lines[len(lines) // 2:]))
    except OSError:
        pass


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
            headers={"Authorization": f"Bearer {tok}", "anthropic-beta": "oauth-2025-04-20"})
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
    hits = [a for a in accounts if a.name.lower().startswith(local + "-")]
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
    verified = _store_for_email(email, _list_accounts())
    if verified is None:
        sys.stderr.write(
            f"claude_rotate: drift-check skipped — no store for live account {email}\n")
        return 0
    if verified != target:
        sys.stderr.write(
            f"claude_rotate: capture RETARGETED {target.name} -> {verified.name} "
            f"(live token belongs to {email})\n")
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
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        sys.stderr.write(
            "usage: claude_rotate.py [--list | --switch <name> | --next | --capture-current"
            " | --drift-check | <claude> args...]\n"
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
    if args[0] == "--tick":
        return _cmd_tick()
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
