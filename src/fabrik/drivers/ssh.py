"""SSH + SCP helpers for Fabrik VPS operations.

Thin, dependency-free wrappers around `subprocess.run` for executing commands
and copying files to the Fabrik VPS. Both functions obey `FABRIK_VPS_SSH_HOST`
(default: ``"vps"`` — a ``~/.ssh/config`` alias that resolves to the actual
host, user, and key) so the underlying VPS can be swapped without a code
change and tests can target a throwaway alias.

Design notes
------------
* These helpers are the foundation for every Fabrik driver that mutates VPS
  state (Backrest, Authelia, Gatus). They MUST NOT attempt to hold remote
  file locks on their own — use :func:`fabrik.drivers.locks.run_locked` to
  run a full bash script under ``flock`` instead. See the locks module
  docstring for the proof that Python-orchestrated SSH chains cannot hold a
  remote lock.
* ``dry_run=True`` is a universal no-op switch used by ``fabrik apply
  --dry-run`` to surface the commands that *would* run without touching the
  VPS.
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
import shlex
import subprocess
from collections.abc import Callable

logger = logging.getLogger(__name__)

DEFAULT_SSH_HOST = "vps"
"""Default SSH alias resolved via ``~/.ssh/config``. Overridable via
``FABRIK_VPS_SSH_HOST``.
"""

# Mask base64 payloads piped to `base64 -d` before they hit a DEBUG log. Callers
# like ``postgres._run_sql`` ship SQL — which may carry a role ``PASSWORD`` — as
# ``echo <base64> | base64 -d | … psql``; without this, enabling DEBUG (or wiring
# a Loki sink at DEBUG) trivially leaks every generated DB-role password.
_B64_PIPE = re.compile(r"echo\s+[A-Za-z0-9+/=]{20,}\s*\|\s*base64\s+-d")


_SECRETY_ASSIGN = re.compile(
    r"(\w*(?:TOKEN|SECRET|KEY|PASSWORD|PASSWD|CREDENTIAL)S?\w*\s*=\s*)(\S+)", re.I
)


def _redact(cmd: str) -> str:
    """Return ``cmd`` with base64 payloads AND secret-shaped assignments masked.

    The assignment mask (F12, 2026-08-31): a failing .env-write echoed the whole
    heredoc — CONSUMER_TOKENS included — through the error path; base64 masking
    alone never touched it.
    """
    out = _B64_PIPE.sub("echo <redacted-base64> | base64 -d", cmd)
    return _SECRETY_ASSIGN.sub(r"\1<redacted>", out)


def _one_line(text: str, empty: str = "no stderr") -> str:
    """Return remote ``text`` (ssh stderr, a reply) fit for an error or a log line: masked, then ``repr``-quoted.

    ``repr`` escapes CR, LF, NUL, U+2028 and every other line break or control character, so the remote side
    cannot forge a log line (W-9a560686), and keeps printable non-ASCII as itself. The mask runs FIRST:
    after ``repr`` an escaped ``\\r\\n`` is no longer whitespace, so ``_SECRETY_ASSIGN`` masks past it, and a
    base64 payload whose ``| base64 -d`` sits on the next line no longer matches. ``_redact``'s own gaps stay
    (a payload split mid-run, a value's tail after a line break). An empty or whitespace-only ``text`` reads
    ``empty``.
    """
    masked = _redact(text.strip())
    return repr(masked) if masked else empty


# Remote output is read as UTF-8 whatever the hub's locale, with `surrogateescape` so the decode itself never
# raises: a stray byte used to raise UnicodeDecodeError inside subprocess.run, before the return code was read
# — hiding a failed command's rc and stderr, crashing a successful one, and slipping past every caller that
# catches the driver's RuntimeError (W-5597922e). stderr only feeds a message, so its escaped bytes are shown
# as `\xNN`; stdout is DATA, so an escaped byte there is refused (`_undecodable`), never handed on.
_REMOTE_TEXT = {"text": True, "encoding": "utf-8", "errors": "surrogateescape"}


class UndecodableAnswerError(RuntimeError):
    """A command that SUCCEEDED (rc 0) answered with stdout that is not valid UTF-8. A RuntimeError, so every
    caller that handles a failed command handles it; a caller that ignores the output and whose next step is
    destructive (the redeploy's rollback) catches it first — the remote step itself succeeded."""


def _shown(text: str) -> str:
    """Remote ``text`` with each escaped (undecodable) byte written as ``\\xNN`` (``_one_line``'s ``repr``
    then doubles the backslash)."""
    return text.encode("utf-8", "surrogateescape").decode("utf-8", "backslashreplace")


def _undecodable(text: str) -> bool:
    """True when ``text`` holds a lone surrogate — decoding with ``surrogateescape`` yields one (U+DC80..U+DCFF)
    for each byte that was not valid UTF-8, and valid UTF-8 never decodes to one."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return True
    return False


def _ssh_host() -> str:
    """Return the SSH host alias, reading ``FABRIK_VPS_SSH_HOST`` at call time.

    Function-level (not module-level) lookup is deliberate: module-level
    reads capture the value at import time, which breaks tests that
    monkeypatch ``os.environ`` *after* the module is loaded.
    """
    return os.getenv("FABRIK_VPS_SSH_HOST", DEFAULT_SSH_HOST)


JUMP_ENV_PREFIX = "FABRIK_SSH_JUMP_"
"""Per-alias opt-in jump (W-2b657bee): ``FABRIK_SSH_JUMP_VPS=vps2`` routes ssh/scp to the
``vps`` alias through ``vps2`` — here, in ``drivers/dns.py``, in ``audit._ssh_check`` and in
``preflight.verify_host_reachable``. Unset, the argv is exactly what it was before. Never an
automatic reroute: a dead path is named by ``preflight.verify_host_reachable`` instead.
"""

# An ssh destination as fabrik names one: ``[user@]host``. It lands in ssh's argv, so a leading
# ``-``, a space or a shell character is refused rather than passed; IPv6 literals too (name the
# host by an alias). The alias of FABRIK_VPS_SSH_HOST and every ProxyJump hop share it (W-6a96f699).
_USER_HOST = r"(?:(?P<user>[A-Za-z0-9_][A-Za-z0-9_.-]*)@)?(?P<host>[A-Za-z0-9_][A-Za-z0-9_.-]*)"
_ALIAS = re.compile(_USER_HOST)
# One ProxyJump hop is ``[user@]host[:port]``; several are comma-separated (OpenSSH's own
# -J syntax). Checked per hop with fullmatch; ``none``, ProxyJump's disable keyword, is refused
# by parse_hop, since it would silently mean "direct" while every message said "via jump".
_JUMP_HOP = re.compile(_USER_HOST + r"(?::(?P<port>[1-9][0-9]{0,4}))?")


class SshHostError(ValueError):
    """The ssh host from the environment is not an ssh alias, so it never reaches argv. A
    ``ValueError`` like :class:`JumpConfigError`: the ``except RuntimeError`` sites read an ssh
    failure as "absent" (``find_existing`` → ``None``), and a config error must not pass as that."""


def is_alias(host: str) -> bool:
    """True when *host* is ``[user@]host`` in the grammar above — safe as an ssh argv element."""
    return _ALIAS.fullmatch(host) is not None


def _checked(host: str, var: str = "FABRIK_VPS_SSH_HOST") -> str:
    if not is_alias(host):
        raise SshHostError(f"{var}={host!r} is not an ssh alias — refused before ssh ran")
    return host


class JumpConfigError(ValueError):
    """``FABRIK_SSH_JUMP_<ALIAS>`` holds a non-ProxyJump value. Its own type so a caller's
    broad ``except Exception`` fallback (the orchestrator's DNS step) can let it through."""


def parse_hop(hop: str) -> tuple[str | None, str, int | None] | None:
    """Split one hop into ``(user, host, port)``, or ``None`` when it is outside the grammar
    (host ``none`` — ProxyJump's disable keyword — and ports past 65535 included)."""
    m = _JUMP_HOP.fullmatch(hop)
    if not m or m["host"].lower() == "none":
        return None
    port = int(m["port"]) if m["port"] else None
    if port is not None and port > 65535:
        return None
    return m["user"], m["host"], port


def jump_env_name(host: str) -> str:
    """Return the variable that names *host*'s jump: ``vps`` → ``FABRIK_SSH_JUMP_VPS``.

    Every character outside ``[A-Z0-9]`` becomes ``_``, so ``vps-1`` and ``vps_1`` share one.
    The user part never selects the jump: ``deploy@vps`` reads ``FABRIK_SSH_JUMP_VPS`` too, or a
    user-qualified alias would silently take the direct path (W-6a96f699).
    """
    return JUMP_ENV_PREFIX + re.sub(r"[^A-Z0-9]", "_", host.rpartition("@")[2].upper())


def jump_for(host: str) -> str | None:
    """Return the ProxyJump value set for *host*, or ``None`` (unset or empty).

    Raises:
        JumpConfigError: the variable is set to something outside the hop grammar. Fail
            closed: a typo must not silently fall back to the dead direct path.
    """
    name = jump_env_name(host)
    value = os.getenv(name, "")
    if not value:
        return None
    hops = value.split(",")
    if not all(parse_hop(h) for h in hops):
        raise JumpConfigError(
            f"{name}={value!r} is not a ProxyJump value: [user@]host[:port] hops, comma-"
            "separated, port 1-65535 (no IPv6 literals — use an ssh alias; 'none' is refused)"
        )
    return value


def _jump_opts(jump: str | None) -> list[str]:
    return ["-o", f"ProxyJump={jump}"] if jump else []


def jump_args(host: str) -> list[str]:
    """Return the ssh/scp options that route *host* through its jump — ``[]`` when none is set."""
    return _jump_opts(jump_for(host))


def _via(jump: str | None) -> str:
    """`` via jump 'vps2'`` for a failure message, or ``""`` when no jump is set."""
    return f" via jump {jump!r}" if jump else ""


def ssh(cmd: str, timeout: int = 60, dry_run: bool = False) -> str:
    """Execute a shell command on the Fabrik VPS via SSH and return stdout.

    Args:
        cmd: Shell command to run on the VPS. Passed as a single argument to
            ``ssh <host> <cmd>``, so the remote shell handles word splitting.
        timeout: Seconds to wait for the SSH call to complete. Exceeding the
            timeout raises :class:`subprocess.TimeoutExpired`.
        dry_run: If True, log the command at INFO level and return empty
            string without invoking ``ssh``.

    Returns:
        The command's stdout with trailing whitespace stripped.

    Raises:
        RuntimeError: SSH returned a non-zero exit code. Stderr is included
            in the exception message for quick diagnosis. Also raised, naming
            no byte, when a successful command's stdout is not valid UTF-8.
        subprocess.TimeoutExpired: The SSH call exceeded ``timeout`` seconds.
        JumpConfigError: ``FABRIK_SSH_JUMP_<ALIAS>`` is set to a non-ProxyJump value.
        SshHostError: ``FABRIK_VPS_SSH_HOST`` is not an ssh alias.

    Example:
        >>> ssh("uname -m")  # doctest: +SKIP
        'x86_64'
    """
    if dry_run:
        logger.info("[DRY RUN] SSH: %s", cmd)
        return ""

    host = _checked(_ssh_host())
    jump = jump_for(host)  # read once: the argv and the error text name the same jump
    logger.debug("SSH %s: %s", host, _redact(cmd))
    try:
        result = subprocess.run(
            ["ssh", *_jump_opts(jump), host, cmd],
            capture_output=True,
            timeout=timeout,
            check=False,
            **_REMOTE_TEXT,
        )
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
    if timed_out:
        # Re-raised OUTSIDE the except block: TimeoutExpired's str/repr carry the full
        # argv, and `_run_sql`'s argv holds the base64 SQL batch (`ALTER ROLE … PASSWORD`),
        # which registrars log via str(e). Raising here leaves no __context__ holding it.
        raise subprocess.TimeoutExpired(
            ["ssh", *_jump_opts(jump), host, "<command redacted>"], timeout
        ) from None
    if result.returncode != 0:
        # _redact the FAILURE surface too (F12, 01M1C95A2S: a failing .env-write heredoc
        # echoed a live CONSUMER_TOKENS bearer token verbatim into the apply log twice —
        # the debug line above redacts the command, but the error path shipped raw stderr,
        # forcing a mid-deploy credential rotation) — and on one line (W-9a560686).
        raise RuntimeError(
            f"SSH to {host!r}{_via(jump)} failed (rc={result.returncode}): "
            f"{_one_line(_shown(result.stderr))}"
        )
    if _undecodable(result.stdout):
        # The output may be a whole .env: the message names no byte, the raise sits outside any except
        # block of the driver's own (no decode error as __context__), and `result` is dropped first so the
        # traceback's frame holds no reference to the text either.
        del result
        raise UndecodableAnswerError(f"SSH to {host!r}{_via(jump)}: the answer is not valid UTF-8")
    return result.stdout.strip()


def scp_to_vps(
    local_path: str,
    remote_path: str,
    timeout: int = 30,
    dry_run: bool = False,
) -> None:
    """Copy a local file to the Fabrik VPS via ``scp``.

    Args:
        local_path: Absolute or relative path to the local source file.
        remote_path: Absolute destination path on the VPS.
        timeout: Seconds to wait for the copy to complete.
        dry_run: If True, log the intended copy and return without running.

    Raises:
        RuntimeError: ``scp`` returned a non-zero exit code.
        subprocess.TimeoutExpired: The copy exceeded ``timeout`` seconds.
        JumpConfigError: ``FABRIK_SSH_JUMP_<ALIAS>`` is set to a non-ProxyJump value.
        SshHostError: ``FABRIK_VPS_SSH_HOST`` is not an ssh alias.

    Example:
        >>> scp_to_vps("/tmp/config.yml", "/opt/svc/config.yml")  # doctest: +SKIP
    """
    if dry_run:
        logger.info("[DRY RUN] SCP: %s -> vps:%s", local_path, remote_path)
        return

    host = _checked(_ssh_host())
    jump = jump_for(host)
    logger.debug("SCP %s -> %s:%s", local_path, host, remote_path)
    result = subprocess.run(
        # `--`: a local path starting with `-` would otherwise be read as an option (W-894fdc5f)
        ["scp", *_jump_opts(jump), "--", local_path, f"{host}:{remote_path}"],
        capture_output=True,
        timeout=timeout,
        check=False,
        **_REMOTE_TEXT,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"SCP to {host!r}{_via(jump)} failed (rc={result.returncode}): "
            f"{_one_line(_shown(result.stderr))}"
        )


# The only answer `remote_mktemp` accepts — a validation pattern, no file is created from it.
_MKTEMP_PATH_RE = re.compile(r"/tmp/fabrik-[A-Za-z0-9]{10}")  # nosec B108


def remote_mktemp(ssh_fn: Callable[..., str], *, directory: bool = False) -> str:
    """Make a private staging file (0600) or dir (0700) on the VPS with ``mktemp`` and return its path.

    A fixed or pid-derived ``/tmp`` name lets another local VPS user pre-create, swap or read what
    is staged there (W-8dd25072, W-719b2678); ``mktemp`` picks a random name with O_EXCL, owned by the
    ssh user. ``ssh_fn`` is the caller's own ssh callable, so a test that patches the caller's
    ``ssh`` name still intercepts this call. Only the LAST line of the answer is the path (a login
    shell may print before it); anything else fails closed with RuntimeError, after removing a
    path-shaped line mktemp did create (a shell that printed AFTER the path).
    """
    # str(): a None or non-text answer is refused below, never a TypeError past a caller's handler
    answer = str(ssh_fn(f"mktemp {'-d ' if directory else ''}/tmp/fabrik-XXXXXXXXXX", timeout=10))  # nosec B108 — the REMOTE mktemp template: a random O_EXCL name, the fix for predictable /tmp paths
    lines = answer.strip().splitlines()
    path = lines[-1].strip() if lines else ""
    if _MKTEMP_PATH_RE.fullmatch(path):
        return path
    rm = "rm -rf" if directory else "rm -f"
    for line in lines:
        if _MKTEMP_PATH_RE.fullmatch(line.strip()):
            try:
                ssh_fn(f"{rm} {shlex.quote(line.strip())}", timeout=5)
            except Exception:  # noqa: BLE001, S110 — best-effort; the refusal below is the error
                pass
    raise RuntimeError(f"remote mktemp returned an unexpected path: {path!r}")


def install_world_readable(
    ssh_fn: Callable[..., str], scp_fn: Callable[..., None], local_path: str, dest: str
) -> None:
    """Install a local file at ``dest`` on the VPS as root:root 0644 (world-readable), via a mktemp stage.

    The stage comes from :func:`remote_mktemp`, so no other VPS user can pre-create or swap it
    (W-42e79070). It is made root:root 0644 BEFORE the ``sudo mv``, so ``dest`` never carries another
    owner or mode, and a failure before the move leaves ``dest`` as it was. When ``/tmp`` and
    ``dest`` share a filesystem the move is one rename, so a watcher of its directory (Gatus) never
    sees a partial file; across filesystems ``mv`` copies, as the old fixed-name staging did. The
    content is readable by every VPS user once the
    stage is 0644, exactly as the installed file is; a file that must not be is not for this
    helper. The stage is removed (``sudo rm -f``: it may be root's by then) on every failure, an
    interrupt included; after a successful ``mv`` there is nothing left to remove. ``ssh_fn`` and
    ``scp_fn`` are the caller's own callables, so a test patching the caller's names still
    intercepts them.
    """
    stage = remote_mktemp(ssh_fn)
    quoted = shlex.quote(stage)
    try:
        scp_fn(local_path, stage)
        ssh_fn(
            f"sudo chown root:root {quoted} && sudo chmod 644 {quoted} && "
            f"sudo mv {quoted} {shlex.quote(dest)}"
        )
    except BaseException:
        # best-effort: a failing cleanup never masks the original error
        with contextlib.suppress(Exception):
            ssh_fn(f"sudo rm -f {quoted}", timeout=5)
        raise
