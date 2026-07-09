"""Tool registry + workdir-scoped executors for tool-looping subagents.

A subagent that runs as a tool-loop is handed a set of tools it may call. This
module defines that set, the OpenRouter function-tool JSON schemas the model
sees (:data:`TOOL_SCHEMAS`), and the executors that run each call.

## Containment model — read this before trusting it

Containment is layered — an OS sandbox on ``run_command`` under review/worktree isolation:

* **``run_command`` is OS-sandboxed by default** (``sandbox_on=True``) via bubblewrap
  (see :mod:`subagents.sandbox`): the whole filesystem is read-only except the worktree,
  with no network. An allow-listed interpreter (``python``/``pytest`` — arbitrary
  execution) that tries to WRITE an absolute path outside the worktree hits ``EROFS``.
  **Fail-closed:** without ``bwrap``/user-namespaces, ``run_command`` is refused, never run
  unsandboxed (``sandbox_on=False`` is the explicit trusted opt-out). The allow-list is
  still caller-overridable (default a minimal dev toolchain; ``allowed_commands=frozenset()``
  forbids all execution). **Residual:** read-only-root is not hidden — a command can still
  *read* host files (and the model's output exfiltrates them), so keep secrets out of
  readable paths; ``_stripped_env`` keeps orchestrator secrets out of the child's env.
* **Writes are ALSO contained by review.** Each subagent runs in its own throwaway git
  *worktree*; its changes are captured as a *diff that is never auto-applied* and are
  scope-checked against the agent's ``owned_paths`` before a human/caller applies them.
* **This file's file-executors** (``read_file``/``list_dir``/``grep``/``write_file``/
  ``apply_patch``) confine every path to ``workdir`` via :func:`_resolve_in_workdir`
  (blocks ``../``, absolute paths, and symlinks).

Executors never raise to the caller: :func:`execute_tool` catches every failure
and returns ``ToolResult(ok=False, …)`` so the loop can feed the error back to
the model as a tool result and continue.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from . import sandbox

# Default binaries run_command may invoke. Deliberately minimal: the *developer
# toolchain* an agent needs to test/lint its work — NOT file utilities like
# cat/ls/grep (those have confined tool equivalents) and NOT git (apply_patch
# covers patching; `git -C <else>` would escape). Every entry is a general
# interpreter and thus arbitrary execution — see the module docstring. Callers
# override via execute_tool(allowed_commands=…).
DEFAULT_ALLOWED_COMMANDS: frozenset[str] = frozenset(
    # dev toolchain: run/lint/type-check + the two static security scanners
    # (bandit reads the AST, semgrep matches patterns — neither executes the code,
    # so they're strictly safer than the `python` already here). All run sandboxed.
    {"python", "python3", "pytest", "ruff", "mypy", "bandit", "semgrep"}
)

# Shell control operators. We never use shell=True, so these are inert even if
# passed — but their presence as a *standalone token* means the model expected to
# chain/redirect, so we refuse rather than silently mis-execute. Checked AFTER
# shlex.split, so a `;`/`|` *inside* a quoted arg (e.g. `python -c "a; b"`) is one
# token and stays allowed — only a bare operator token is rejected.
_SHELL_OPERATORS: frozenset[str] = frozenset(
    {";", "|", "||", "&", "&&", ">", ">>", "<", "<<", "`"}
)

_MAX_OUTPUT = 20_000  # cap captured text so a runaway command can't blow up context
_MAX_READ_BYTES = 5_000_000  # refuse to slurp a file larger than this into memory
_MAX_GREP_FILES = 5_000  # bound the grep walk so a huge tree can't stall the worker


class WorkdirEscapeError(Exception):
    """Raised when a resolved path would leave the agent's workdir."""


@dataclass
class ToolResult:
    """One tool call's outcome. ``ok`` gates whether the loop treats it as a
    success; ``output`` is fed back to the model; ``error`` is set on failure."""

    ok: bool
    output: str
    error: str | None = None


def _resolve_in_workdir(path: str, workdir: str) -> str:
    """Resolve ``path`` relative to ``workdir`` and confirm it stays inside.

    Returns the absolute real path. Raises :class:`WorkdirEscapeError` if the real
    path is not the workdir itself or a descendant of it (blocks ``../`` and
    absolute-path escapes, symlinks included — we resolve before comparing).
    """
    root = Path(workdir).resolve()
    candidate = Path(workdir) / path if not os.path.isabs(path) else Path(path)
    real = candidate.resolve()
    if real != root and root not in real.parents:
        raise WorkdirEscapeError(f"path {path!r} resolves outside workdir {workdir!r}")
    return str(real)


def _stripped_env(workdir: str) -> dict[str, str]:
    """Minimal env for a tool subprocess — no inherited secrets in the *child*.

    NOTE: this removes secrets from the child's own environment; it does not (and
    cannot, without an OS sandbox) stop an interpreter child from reading the
    *parent* process env via /proc. See the module docstring.
    """
    return {"PATH": os.environ.get("PATH", ""), "HOME": workdir}


def _truncate(text: str) -> str:
    return text if len(text) <= _MAX_OUTPUT else text[:_MAX_OUTPUT] + "\n…[truncated]"


def _read_text_bounded(target: Path) -> str:
    """Read a file as text, refusing anything over the size cap (memory guard)."""
    if target.stat().st_size > _MAX_READ_BYTES:
        raise OSError(f"file exceeds {_MAX_READ_BYTES} byte read limit")
    return target.read_text(encoding="utf-8", errors="replace")


def _read_file(arguments: dict, workdir: str) -> ToolResult:
    target = Path(_resolve_in_workdir(str(arguments["path"]), workdir))
    return ToolResult(ok=True, output=_truncate(_read_text_bounded(target)))


def _list_dir(arguments: dict, workdir: str) -> ToolResult:
    target = _resolve_in_workdir(str(arguments.get("path", ".")), workdir)
    entries = sorted(
        p.name + ("/" if p.is_dir() else "") for p in Path(target).iterdir()
    )
    return ToolResult(ok=True, output=_truncate("\n".join(entries)))


def _grep_candidates(root: Path) -> tuple[list[Path], bool]:
    """Files under ``root`` to grep, and whether the walk was TRUNCATED at the cap.

    Walk with ``followlinks=False`` (a symlinked directory is NOT descended —
    blocks a symlink cycle from hanging the walk and a link out of the workdir) and
    cap the count (a huge tree can't stall the worker)."""
    if root.is_file():
        return [root], False
    out: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
        for fn in filenames:
            out.append(Path(dirpath) / fn)
            # collect ONE past the cap so we can tell "exactly cap files" (complete)
            # from "more than cap exist" (truncated) — no false truncation warning
            if len(out) > _MAX_GREP_FILES:
                return out[:_MAX_GREP_FILES], True
    return out, False


def _grep(arguments: dict, workdir: str) -> ToolResult:
    pattern = re.compile(str(arguments["pattern"]))
    root = Path(_resolve_in_workdir(str(arguments.get("path", ".")), workdir))
    matches: list[str] = []
    candidates, truncated = _grep_candidates(root)
    for f in candidates:
        # Skip symlinks and re-confirm each file is really inside the workdir —
        # defense-in-depth on top of the followlinks=False walk (read escape).
        if f.is_symlink() or not f.is_file():
            continue
        try:
            _resolve_in_workdir(os.path.relpath(f, workdir), workdir)
            lines = _read_text_bounded(f).splitlines()
        except (OSError, WorkdirEscapeError):
            continue
        rel = os.path.relpath(f, workdir)
        for lineno, line in enumerate(lines, 1):
            if pattern.search(line):
                matches.append(f"{rel}:{lineno}:{line}")
    # append the truncation notice AFTER capping the match text, so a high match
    # volume can't push the signal past the _truncate limit and drop it
    output = _truncate("\n".join(matches))
    if truncated:
        output += f"\n[grep: file scan stopped at {_MAX_GREP_FILES} files — results may be incomplete]"
    return ToolResult(ok=True, output=output)


def _write_file(arguments: dict, workdir: str) -> ToolResult:
    target = _resolve_in_workdir(str(arguments["path"]), workdir)
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    Path(target).write_text(str(arguments["content"]), encoding="utf-8")
    return ToolResult(ok=True, output=f"wrote {arguments['path']}")


def _patch_targets_escape(patch: str) -> bool:
    """True if any target path in a unified diff is absolute or traverses up.

    Defense-in-depth on top of `git apply`'s own path checks (which are
    git-version-dependent): reject a patch that names `/abs`, `../`, or a
    symlink-style out-of-tree target before we ever hand it to git.
    """
    for line in patch.splitlines():
        if line.startswith(("+++ ", "--- ", "diff --git ", "rename to ", "copy to ")):
            for tok in line.split():
                tok = tok.strip('"')  # git quotes paths with special/non-ASCII chars
                p = tok[2:] if tok.startswith(("a/", "b/")) else tok
                if p in ("/dev/null", "a", "b"):
                    continue
                if os.path.isabs(p) or ".." in Path(p).parts:
                    return True
    return False


def _apply_patch(arguments: dict, workdir: str, timeout_s: float) -> ToolResult:
    patch_text = str(arguments["patch"])
    if _patch_targets_escape(patch_text):
        return ToolResult(
            ok=False, output="", error="patch targets a path outside the workdir"
        )
    scratch = Path(workdir) / ".tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    patch_file = scratch / f"patch-{uuid.uuid4().hex}.diff"
    patch_file.write_text(patch_text, encoding="utf-8")
    try:
        proc = subprocess.run(
            ["git", "apply", str(patch_file)],
            cwd=workdir,
            env=_stripped_env(workdir),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    finally:
        patch_file.unlink(missing_ok=True)
    if proc.returncode != 0:
        return ToolResult(
            ok=False, output=_truncate(proc.stdout), error=_truncate(proc.stderr)
        )
    return ToolResult(ok=True, output="patch applied")


def _run_command(
    arguments: dict,
    workdir: str,
    timeout_s: float,
    allowed: frozenset[str],
    sandbox_on: bool = True,
) -> ToolResult:
    cmd = str(arguments["cmd"])
    argv = shlex.split(
        cmd
    )  # may raise ValueError on unbalanced quotes → caught upstream
    if not argv:
        return ToolResult(ok=False, output="", error="empty command")
    if any(tok in _SHELL_OPERATORS for tok in argv):
        return ToolResult(
            ok=False, output="", error="shell operators (;|&><) are not permitted"
        )
    if argv[0] not in allowed:
        return ToolResult(
            ok=False,
            output="",
            error=f"command {argv[0]!r} is not in the allow-list {sorted(allowed)}",
        )
    # allow-listed commands (python/pytest/…) are still ARBITRARY execution — they can
    # touch any absolute path. Confine them to the worktree with an OS sandbox. FAIL
    # CLOSED: if the sandbox is required but unavailable, refuse rather than run wild.
    run_argv = argv
    # Sandbox UNLESS the caller EXPLICITLY opted out with literal `False`. `is not False`
    # (not a truthiness test) so a stray `sandbox_on=None`/`0`/`""` from a dict/JSON spec
    # still sandboxes — an accidental falsy must never silently run untrusted code raw.
    if sandbox_on is not False:
        try:
            run_argv = sandbox.wrap_command(argv, workdir)
        except sandbox.SandboxUnavailable as exc:
            return ToolResult(ok=False, output="", error=f"sandbox required: {exc}")
    try:
        proc = subprocess.run(
            run_argv,
            cwd=workdir,
            env=_stripped_env(workdir),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(ok=False, output="", error=f"timeout after {timeout_s}s")
    output = _truncate(proc.stdout + (("\n" + proc.stderr) if proc.stderr else ""))
    if proc.returncode != 0:
        return ToolResult(ok=False, output=output, error=f"exit code {proc.returncode}")
    return ToolResult(ok=True, output=output)


def execute_tool(
    name: str,
    arguments: dict,
    *,
    workdir: str,
    timeout_s: float = 30.0,
    allowed_commands: frozenset[str] | None = None,
    sandbox_on: bool = True,
) -> ToolResult:
    """Dispatch one tool call inside ``workdir``. Never raises — every failure
    (unknown tool, workdir escape, bad args, bad regex/quotes, subprocess error)
    is returned as ``ToolResult(ok=False, …)`` so the loop can feed it back to the
    model. ``allowed_commands`` overrides the run_command allow-list (default
    :data:`DEFAULT_ALLOWED_COMMANDS`; pass ``frozenset()`` to forbid execution).
    ``sandbox_on`` (default True) confines ``run_command`` to ``workdir`` via an OS
    sandbox and FAILS CLOSED if unavailable — pass False only for a trusted agent on a
    host without ``bwrap`` (the ``danger-full-access`` equivalent)."""
    allowed = DEFAULT_ALLOWED_COMMANDS if allowed_commands is None else allowed_commands
    try:
        if name == "read_file":
            return _read_file(arguments, workdir)
        if name == "list_dir":
            return _list_dir(arguments, workdir)
        if name == "grep":
            return _grep(arguments, workdir)
        if name == "write_file":
            return _write_file(arguments, workdir)
        if name == "apply_patch":
            return _apply_patch(arguments, workdir, timeout_s)
        if name == "run_command":
            return _run_command(arguments, workdir, timeout_s, allowed, sandbox_on)
        return ToolResult(ok=False, output="", error=f"unknown tool {name!r}")
    except WorkdirEscapeError as exc:
        return ToolResult(ok=False, output="", error=str(exc))
    except KeyError as exc:
        return ToolResult(ok=False, output="", error=f"missing argument {exc}")
    except re.error as exc:
        return ToolResult(ok=False, output="", error=f"invalid regex: {exc}")
    except (ValueError, TypeError, AttributeError) as exc:
        # TypeError/AttributeError: a non-dict `arguments` (valid-JSON list/str/int)
        # subscripted/`.get()`-ed by an executor — return, never sink the run
        return ToolResult(ok=False, output="", error=f"bad argument: {exc}")
    except subprocess.SubprocessError as exc:
        return ToolResult(ok=False, output="", error=f"subprocess failed: {exc}")
    except OSError as exc:
        return ToolResult(ok=False, output="", error=str(exc))


def _fn(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


_STR = {"type": "string"}

# OpenRouter function-tool schemas the model is shown. The model returns each
# call's `arguments` as a JSON *string* (per openrouter-api.md); loop.py parses
# it with json.loads before handing the dict to execute_tool.
TOOL_SCHEMAS: list[dict] = [
    _fn(
        "read_file",
        "Read a UTF-8 text file inside the workspace.",
        {"path": _STR},
        ["path"],
    ),
    _fn("list_dir", "List directory entries inside the workspace.", {"path": _STR}, []),
    _fn(
        "grep",
        "Search files for a regular expression; returns path:line:text matches.",
        {"pattern": _STR, "path": _STR},
        ["pattern"],
    ),
    _fn(
        "write_file",
        "Create or overwrite a text file inside the workspace.",
        {"path": _STR, "content": _STR},
        ["path", "content"],
    ),
    _fn(
        "apply_patch",
        "Apply a unified diff to the workspace via `git apply`.",
        {"patch": _STR},
        ["patch"],
    ),
    _fn(
        "run_command",
        "Run an allow-listed developer command (python/pytest/ruff/mypy) in the workspace. No shell.",
        {"cmd": _STR},
        ["cmd"],
    ),
]
