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
    """True iff *text* is a Claude auth (401) failure (→ alert, NEVER rotate).

    Requires the auth wording alongside a standalone ``401`` so neither a bare
    ``line 401`` nor a ``401`` buried inside a larger number (``14012``) matches.
    """
    if not re.search(r"\b401\b", text):
        return False
    low = text.lower()
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
            sys.stderr.write(f"refusing to activate {target.name}: unreadable/corrupt credentials\n")
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


ENV_SYSADMIN = Path("/opt/fabrik/.env.sysadmin")  # fleet sysadmin env (ozgur-readable) — token fallback


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
        sys.stderr.write("claude_rotate: 401 Telegram alert failed to send (best-effort, ignored)\n")
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
        argv, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=cwd, env=env, input=stdin_data
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
            argv, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=cwd, env=env, input=stdin_data
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
    sys.stderr.write("switch failed (filesystem error) — active account unchanged\n")
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
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        sys.stderr.write(
            "usage: claude_rotate.py [--list | --switch <name> | --next | <claude> args...]\n"
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
        sys.stderr.write(f"claude_rotate: cannot execute {args[0]!r}: {e.strerror or 'exec error'}\n")
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
