#!/usr/bin/env python3
# AFTER-EDIT: scripts/sysadmin/bot.py, scripts/aro-wake/main.py, scripts/sysadmin/claude_rotate.py, scripts/aro-wake/claude_rotate.py
# NB: this file is vendored BYTE-IDENTICAL into scripts/sysadmin/ and scripts/aro-wake/
# (separate rsync trees + venvs on each host — no shared import). Keep the two copies identical.
"""Claude Code CLI usage-limit detection + bounded account rotation.

Self-contained, stdlib-only. Vendored BYTE-IDENTICAL into both ``scripts/sysadmin/``
and ``scripts/aro-wake/`` (separate rsync trees + separate venvs on each host — no
shared import path exists), so this file must never import a sibling.

When a ``claude -p`` call reports a usage/quota limit, rotate the *active* account to
the operator's other snapshot and retry ONCE. A ``401`` (dead creds) is NOT a rotate
trigger — rotation cannot fix expired credentials; the caller alerts on that.

Security (``core/35-security-auth``): ``~/.claude/*.credentials.json`` are ``chmod 600``
and are **never logged, printed, or returned**. Rotation swaps whole files
(``os.replace`` — atomic) between the ``manager-accounts/<org>/.credentials.json``
snapshots and the active ``~/.claude/.credentials.json``; it only ever reads the
non-secret ``organizationUuid`` to tell the two accounts apart — never a token byte.
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
from collections.abc import Callable
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
ACTIVE_CREDS = CLAUDE_DIR / ".credentials.json"
ACCOUNTS_DIR = CLAUDE_DIR / "manager-accounts"
BACKUP_CREDS = CLAUDE_DIR / ".credentials.json.prev"  # single rolling backup of outgoing active
ROTATE_LOCK = CLAUDE_DIR / ".claude-rotate.lock"

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


def _list_accounts() -> list[Path]:
    """Manager-account snapshot dirs that hold a ``.credentials.json`` (sorted, stable order)."""
    if not ACCOUNTS_DIR.is_dir():
        return []
    return sorted(
        d for d in ACCOUNTS_DIR.iterdir() if d.is_dir() and (d / ".credentials.json").is_file()
    )


def _active_account() -> Path | None:
    """The snapshot dir whose org matches the currently-active creds, or None."""
    active_org = _read_org(ACTIVE_CREDS)
    if active_org is None:
        return None
    for acc in _list_accounts():
        if _read_org(acc / ".credentials.json") == active_org:
            return acc
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
        # Single rolling backup of the outgoing active (satisfies the backup-before-swap rule).
        if active_bytes is not None:
            _secure_write(BACKUP_CREDS, active_bytes)
        _secure_write(tmp, target_bytes)
        os.replace(str(tmp), str(ACTIVE_CREDS))  # atomic swap (0600 mode carried from tmp)
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
    """Rotate the active account to another snapshot: pick the first account whose dir name
    is NOT in *avoid* and whose org differs from the active creds — so with 3+ accounts
    (mob/ob/can), successive calls with a growing *avoid* set walk through each other account
    exactly once. Selection runs **inside the install lock** (via the selector), so two
    concurrent rotations can't both target the same account, over-write the ``.prev`` backup,
    or report a phantom no-op rotation. Returns the new account's dir name, or None when there
    is no eligible target or the install fails (fail-soft).
    """
    accounts = _list_accounts()
    if len(accounts) < 2:
        return None

    def _select() -> Path | None:
        active_org = _read_org(ACTIVE_CREDS)  # re-read live active — under the lock
        return next(
            (
                acc
                for acc in accounts
                if acc.name not in avoid and _read_org(acc / ".credentials.json") != active_org
            ),
            None,
        )

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


def run_claude(
    argv: list[str], timeout: int, cwd: str, env: dict[str, str], buffer_stdin: bool = False
) -> subprocess.CompletedProcess:
    """Run ``claude`` (*argv*). On a usage-limit signal (and not a 401), rotate to another
    account and retry — walking through **each OTHER account at most once** (N-account
    support: mob/ob/can/…). Bounded by the account count, so it can never loop. A 401/auth
    failure is never a rotate trigger (dead creds, not quota) and returns unchanged for the
    caller to alert on. Returns the (possibly retried) result of the last attempt.

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
    result = subprocess.run(
        argv, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env, input=stdin_data
    )
    accounts = _list_accounts()
    if len(accounts) < 2:
        return result  # 0 or 1 account → nothing to rotate to
    start = _active_account()
    tried: set[str] = {start.name} if start else set()
    # Each OTHER account tried at most once. When the active creds match no snapshot
    # (start is None — e.g. an account whose snapshot isn't captured yet), ALL snapshots
    # are valid targets, so the bound is N, not N-1.
    max_rotations = len(accounts) - (1 if start else 0)
    rotations = 0
    while rotations < max_rotations:
        combined = (result.stdout or "") + "\n" + (result.stderr or "")
        # Rotate on the usage-limit signal REGARDLESS of exit code / output format. Never
        # missing a real limit is this feature's core guarantee, and Claude's exit code on a
        # limit is not reliably known — gating on `returncode != 0` (or on "is it valid JSON")
        # would risk silently failing to recover from a real limit that happened to exit 0.
        # The cost is a bounded, self-correcting false-positive: a *successful* answer that
        # merely quotes a limit phrase triggers up to N-1 wasted rotations (standby accounts
        # stay valid, the operator still gets an answer). The operational callers (keepalive
        # ping, aro-wake alerts) never quote limit phrases; only operator chat could.
        if not is_usage_limit(combined) or is_auth_401(combined):
            break
        new_account = _rotate_active_account(avoid=frozenset(tried))
        if not new_account:
            break  # no untried account left → give up (all exhausted)
        tried.add(new_account)
        rotations += 1
        result = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env, input=stdin_data
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
    timeout = int(os.environ.get("CLAUDE_ROTATE_TIMEOUT", "120"))
    # CLI passthrough (claude-run.sh → stdin-piping sysadmin scripts): buffer stdin so a
    # rotation retry re-supplies the piped context.
    result = run_claude(args, timeout=timeout, cwd=os.getcwd(), env=env, buffer_stdin=True)
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
