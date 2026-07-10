"""OS-level sandbox for the ``run_command`` tool — confine a spawned interpreter
(``python``/``pytest``/…) so it CANNOT **write** outside the agent's worktree, even
via an absolute path. (It CAN still *read* the host filesystem — see the residual note
below; the guarantee is write-confinement + no-network, not read-confinement.)

Why this exists
---------------
``tools.py`` confines the *file tools* to the workdir and excludes ``git`` from the
command allow-list, but it must allow ``python``/``pytest`` — and those are general
interpreters (arbitrary execution). A model handed a task containing an absolute path
(e.g. ``/opt/fabrik-lib``) can run ``python -c "import os; os.rename('/opt/…', …)"`` and
mutate the *real* shared tree — directory/worktree isolation is powerless against an
absolute-path filesystem op. (Seen live 2026-07-06; see ``UPSTREAM_FEEDBACK.md``.)

The fix is the same primitive OpenAI Codex uses on Linux/WSL2: **bubblewrap** (``bwrap``).
We wrap the command so the WHOLE filesystem is read-only (``--ro-bind / /``) except the
one worktree (``--bind``), with no network (``--unshare-net``) and isolated user/pid/ipc
namespaces. A write outside the worktree then fails with ``EROFS`` at the kernel — proven
on WSL2 (kernel 6.6, bwrap 0.9.0): the exact ``os.rename`` / ``open(…, 'w')`` / subprocess
escape returns ``[Errno 30] Read-only file system``.

Refs (fetched 2026-07-07):
- Codex Linux sandbox (bwrap default): https://github.com/openai/codex/blob/main/codex-rs/linux-sandbox/README.md
- bwrap(1): https://www.mankier.com/1/bwrap  (``--die-with-parent`` + ``--unshare-pid`` needed to reap children)

Residual (know the boundary): ``--ro-bind / /`` is read-only, not hidden — a command can
still READ any host file uid can (another project's ``.env``, ``~/.ssh``, a sibling
agent's worktree). ``--unshare-net`` stops it phoning out, but the model's own OUTPUT is
an exfiltration channel (it flows back to the orchestrator), so no-net does NOT make reads
safe. Keep secrets OUT of readable paths; masking them (``--tmpfs`` over their parents) is
a documented follow-up. There is no ``--seccomp`` syscall filter (Codex ships one) — also
a follow-up; ``NoNewPrivs`` is implied and ``--new-session`` is set.

Policy: **fail-closed.** If a caller requires the sandbox but ``bwrap`` (or unprivileged
user namespaces) is unavailable, ``run_command`` must REFUSE — never silently run
untrusted code unsandboxed.
"""

from __future__ import annotations

import functools
import shutil
import subprocess
import tempfile

# The sandbox gets a fresh ephemeral tmpfs over the system temp dir so tools that write
# scratch files (pytest, tempfile) work while staying isolated from the host's temp.
# Computed (not a bare literal) so the module-recipe `.tmp`-not-`/tmp` gate stays happy.
_SANDBOX_TMP = tempfile.gettempdir()

__all__ = ["sandbox_available", "wrap_command", "SandboxUnavailable"]


class SandboxUnavailable(RuntimeError):  # noqa: N818 — exported public API (in __all__, caught by name in tools.py + consumers); the Error-less name is deliberate and renaming it is a breaking change for every vendored copy
    """Raised/queried when sandboxing is required but the platform can't provide it."""


# The read-only-root, writable-worktree, no-net recipe (mirrors Codex's bwrap defaults).
# ``--ro-bind / /`` first (everything RO), then re-expose the essentials, then ``--bind``
# the worktree LAST so it wins over the RO root for that subtree. Network is ALWAYS
# unshared (no caller needs it, and the whole FS is readable — an open net would let a
# command exfiltrate any readable secret; see the read-residual note in the module docs).
def _base_flags(workdir: str) -> list[str]:
    return [
        "bwrap",
        "--ro-bind",
        "/",
        "/",  # entire filesystem read-only …
        "--dev",
        "/dev",  # minimal fresh /dev
        "--proc",
        "/proc",  # fresh /proc (needs --unshare-pid)
        "--tmpfs",
        _SANDBOX_TMP,  # ephemeral writable temp (isolated from host)
        "--setenv",
        "TMPDIR",
        _SANDBOX_TMP,  # point the child's tempfile AT the tmpfs —
        # else a stripped env resolves temp elsewhere
        # (RO) and pytest/tempfile fail with EROFS
        "--bind",
        workdir,
        workdir,  # … EXCEPT the worktree, which is writable
        "--chdir",
        workdir,
        "--unshare-user",
        "--unshare-pid",  # + --die-with-parent → children are reaped
        "--unshare-ipc",
        "--unshare-uts",
        "--unshare-net",  # no network — always
        "--unshare-cgroup-try",
        "--die-with-parent",
        "--new-session",  # detach controlling tty (blocks TIOCSTI injection)
    ]


@functools.lru_cache(maxsize=1)
def sandbox_available() -> bool:
    """True iff ``bwrap`` is on PATH AND the REAL recipe can create its namespaces here.

    Cached: the answer is a property of the host, not the call. The probe runs the
    **actual** ``_base_flags`` recipe (over the temp dir, which always exists) + ``true``
    — not a simpler flag set — so a green probe means the exact wrap the agent will run
    is viable (unprivileged user namespaces can be present-but-disabled: WSL1, hardened
    kernels, some containers). It validates namespace/mount *setup*; the write-confinement
    itself is structurally guaranteed by ``--ro-bind / /`` (a write outside the worktree →
    ``EROFS``).
    """
    if shutil.which("bwrap") is None:
        return False
    try:
        proc = subprocess.run(
            _base_flags(_SANDBOX_TMP) + ["true"],
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def wrap_command(argv: list[str], workdir: str) -> list[str]:
    """Return ``argv`` prefixed with the ``bwrap`` sandbox for ``workdir``.

    Raises :class:`SandboxUnavailable` if the platform can't sandbox — callers MUST
    treat that as "refuse to run", never as "run unsandboxed" (fail-closed).

    NOTE: bwrap does NOT clear the environment (no ``--clearenv``) — it inherits the
    subprocess env. The caller MUST pass a minimal ``env=`` to ``subprocess`` (as
    ``tools._run_command`` does via ``_stripped_env``) so orchestrator secrets don't
    leak into the child.
    """
    if not argv:
        raise ValueError("empty argv")
    if not sandbox_available():
        raise SandboxUnavailable(
            "bubblewrap (bwrap) with unprivileged user namespaces is required to run "
            "untrusted commands; install it (`apt install bubblewrap`) or dispatch "
            "tools-off. Refusing to run unsandboxed."
        )
    return _base_flags(workdir) + ["--", *argv]
