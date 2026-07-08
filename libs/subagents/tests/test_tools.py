"""Phase A — tools.py: registry + workdir-scoped executors.

Highest-risk surface = arbitrary tool execution. These tests pin the three
containment guarantees BEFORE the implementation exists (TDD):
  1. no path escapes the agent's workdir,
  2. run_command honours the command allow-list,
  3. run_command is bounded by a timeout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from subagents.tools import (
    TOOL_SCHEMAS,
    ToolResult,
    WorkdirEscape,
    _resolve_in_workdir,
    execute_tool,
)


def test_write_file_rejects_workdir_escape(tmp_path: Path) -> None:
    """A ../ traversal must NOT write outside the workdir."""
    outside = tmp_path.parent / "escapee.txt"
    if outside.exists():
        outside.unlink()

    res = execute_tool(
        "write_file",
        {"path": "../escapee.txt", "content": "pwned"},
        workdir=str(tmp_path),
    )

    assert isinstance(res, ToolResult)
    assert res.ok is False
    assert not outside.exists(), "traversal escaped the workdir"


def test_resolve_in_workdir_raises_on_escape(tmp_path: Path) -> None:
    """The low-level resolver raises WorkdirEscape on any out-of-workdir path."""
    try:
        _resolve_in_workdir("../../etc/passwd", str(tmp_path))
    except WorkdirEscape:
        return
    raise AssertionError("expected WorkdirEscape")


def test_resolve_in_workdir_allows_nested(tmp_path: Path) -> None:
    """A legitimate nested path resolves under the workdir."""
    resolved = _resolve_in_workdir("sub/dir/file.txt", str(tmp_path))
    assert resolved.startswith(str(tmp_path.resolve()))


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    w = execute_tool(
        "write_file",
        {"path": "hello.txt", "content": "world"},
        workdir=str(tmp_path),
    )
    assert w.ok is True
    r = execute_tool("read_file", {"path": "hello.txt"}, workdir=str(tmp_path))
    assert r.ok is True
    assert "world" in r.output


def test_run_command_allowlist_rejects_rm(tmp_path: Path) -> None:
    """A non-allow-listed binary is refused and never executed."""
    victim = tmp_path / "keep.txt"
    victim.write_text("keep me", encoding="utf-8")

    res = execute_tool("run_command", {"cmd": "rm -rf ."}, workdir=str(tmp_path))

    assert res.ok is False
    assert victim.exists(), "rm was executed despite the allow-list"


def test_run_command_rejects_cat_ls_grep(tmp_path: Path) -> None:
    """cat/ls/grep are NOT in the default allow-list (they have confined tool
    equivalents) — this closes the trivial `cat /etc/passwd` read escape."""
    for binary in ("cat", "ls", "grep", "git"):
        res = execute_tool(
            "run_command", {"cmd": f"{binary} /etc/hostname"}, workdir=str(tmp_path)
        )
        assert res.ok is False, f"{binary} should not be allow-listed by default"


def test_run_command_allow_list_is_caller_overridable(tmp_path: Path) -> None:
    """A caller can forbid ALL execution with an empty allow-list."""
    res = execute_tool(
        "run_command",
        {"cmd": 'python -c "print(1)"'},
        workdir=str(tmp_path),
        allowed_commands=frozenset(),
    )
    assert res.ok is False


def test_run_command_unbalanced_quote_returns_error(tmp_path: Path) -> None:
    """A malformed command (unbalanced quote) must not crash the loop."""
    res = execute_tool("run_command", {"cmd": 'echo "oops'}, workdir=str(tmp_path))
    assert res.ok is False
    assert res.error is not None


def test_grep_invalid_regex_returns_error(tmp_path: Path) -> None:
    """A bad regex pattern must not crash the loop (re.error caught)."""
    (tmp_path / "f.txt").write_text("hello", encoding="utf-8")
    res = execute_tool("grep", {"pattern": "(", "path": "."}, workdir=str(tmp_path))
    assert res.ok is False
    assert res.error is not None


def test_grep_does_not_follow_symlink_outside_workdir(tmp_path: Path) -> None:
    """A symlink inside the workdir pointing OUT must not be read by grep."""
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("TOPSECRET-VALUE", encoding="utf-8")
    link = tmp_path / "leak"
    try:
        link.symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unsupported on this platform")
    res = execute_tool(
        "grep", {"pattern": "TOPSECRET", "path": "."}, workdir=str(tmp_path)
    )
    assert "TOPSECRET-VALUE" not in res.output, (
        "grep followed a symlink out of the workdir"
    )


def test_grep_finds_match_inside_workdir(tmp_path: Path) -> None:
    """Positive path: grep still returns in-workdir matches after the symlink guard."""
    (tmp_path / "a.txt").write_text("alpha\nNEEDLE here\nbeta", encoding="utf-8")
    res = execute_tool(
        "grep", {"pattern": "NEEDLE", "path": "."}, workdir=str(tmp_path)
    )
    assert res.ok is True
    assert "a.txt:2:NEEDLE here" in res.output


def test_apply_patch_applies_valid_in_workdir_diff(tmp_path: Path) -> None:
    """Positive path: a legitimate in-workdir new-file patch applies."""
    patch = (
        "diff --git a/new.txt b/new.txt\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/new.txt\n"
        "@@ -0,0 +1 @@\n"
        "+hello from patch\n"
    )
    res = execute_tool("apply_patch", {"patch": patch}, workdir=str(tmp_path))
    assert res.ok is True, res.error
    assert (tmp_path / "new.txt").read_text(
        encoding="utf-8"
    ).strip() == "hello from patch"


def test_apply_patch_rejects_escaping_target(tmp_path: Path) -> None:
    """A patch whose target path traverses out of the workdir is refused."""
    escaping = (
        "diff --git a/../evil.txt b/../evil.txt\n"
        "--- a/../evil.txt\n"
        "+++ b/../evil.txt\n"
        "@@ -0,0 +1 @@\n"
        "+pwned\n"
    )
    res = execute_tool("apply_patch", {"patch": escaping}, workdir=str(tmp_path))
    assert res.ok is False
    assert not (tmp_path.parent / "evil.txt").exists()


def test_run_command_rejects_shell_metachars(tmp_path: Path) -> None:
    """Even an allow-listed head is refused if shell metacharacters are present."""
    res = execute_tool(
        "run_command",
        {"cmd": "echo hi > /tmp/x && echo bye"},
        workdir=str(tmp_path),
    )
    assert res.ok is False


def test_run_command_timeout(tmp_path: Path) -> None:
    """A long-running allow-listed command is killed at the timeout. (Tests the timeout
    mechanic itself — `sandbox_on=False` so it runs on hosts without bwrap; the sandbox
    is covered by test_sandbox.py.)"""
    res = execute_tool(
        "run_command",
        {"cmd": 'python -c "import time; time.sleep(5)"'},
        workdir=str(tmp_path),
        timeout_s=0.5,
        sandbox_on=False,
    )
    assert res.ok is False
    assert res.error is not None
    assert "timeout" in res.error.lower()


def test_run_command_allowed_runs(tmp_path: Path) -> None:
    """Allow-listed command executes (mechanic; `sandbox_on=False` for portability —
    the sandboxed default path is proven in test_sandbox.py)."""
    res = execute_tool(
        "run_command",
        {"cmd": 'python -c "print(2+2)"'},
        workdir=str(tmp_path),
        sandbox_on=False,
    )
    assert res.ok is True
    assert "4" in res.output


def test_unknown_tool_is_error(tmp_path: Path) -> None:
    res = execute_tool("nonexistent", {}, workdir=str(tmp_path))
    assert res.ok is False


def test_grep_completes_with_symlink_cycle_present(tmp_path: Path) -> None:
    """A symlink cycle inside the workdir must not hang/crash the walk
    (followlinks=False guarantees the symlinked dir is never descended)."""
    (tmp_path / "a.txt").write_text("NEEDLE here\n", encoding="utf-8")
    try:
        (tmp_path / "loop").symlink_to(tmp_path)  # sub -> . : a cycle
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unsupported")
    res = execute_tool(
        "grep", {"pattern": "NEEDLE", "path": "."}, workdir=str(tmp_path)
    )
    assert res.ok is True  # returned (did not hang)
    assert "a.txt" in res.output


def test_grep_caps_the_walk_and_signals_truncation(
    tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
) -> None:
    """The grep walk is bounded (a huge tree can't stall the worker) and the
    truncation is SIGNALLED to the model, not silent."""
    import subagents.tools as tools_mod

    monkeypatch.setattr(tools_mod, "_MAX_GREP_FILES", 3)
    for i in range(10):
        (tmp_path / f"f{i}.txt").write_text("NEEDLE\n", encoding="utf-8")
    res = execute_tool(
        "grep", {"pattern": "NEEDLE", "path": "."}, workdir=str(tmp_path)
    )
    assert res.ok is True
    assert "file scan stopped at 3 files" in res.output  # truncation is surfaced


def test_grep_exactly_cap_files_is_not_flagged_truncated(
    tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
) -> None:
    """EXACTLY _MAX_GREP_FILES files is complete — no false truncation warning."""
    import subagents.tools as tools_mod

    monkeypatch.setattr(tools_mod, "_MAX_GREP_FILES", 3)
    for i in range(3):  # exactly the cap
        (tmp_path / f"f{i}.txt").write_text("NEEDLE\n", encoding="utf-8")
    res = execute_tool(
        "grep", {"pattern": "NEEDLE", "path": "."}, workdir=str(tmp_path)
    )
    assert res.ok is True
    assert "file scan stopped" not in res.output  # complete, not over-warned


def test_execute_tool_non_dict_arguments_is_total(tmp_path: Path) -> None:
    """Defense-in-depth: a non-dict arguments reaching execute_tool returns
    ok=False (TypeError caught), never raises."""
    res = execute_tool("read_file", [1, 2, 3], workdir=str(tmp_path))  # type: ignore[arg-type]
    assert res.ok is False
    assert res.error is not None


def test_tool_schemas_are_openrouter_function_tools() -> None:
    assert isinstance(TOOL_SCHEMAS, list)
    assert TOOL_SCHEMAS, "at least one tool schema"
    names = set()
    for schema in TOOL_SCHEMAS:
        assert schema["type"] == "function"
        fn = schema["function"]
        assert isinstance(fn["name"], str)
        assert "parameters" in fn
        names.add(fn["name"])
    # every advertised tool must be dispatchable
    assert {
        "read_file",
        "list_dir",
        "grep",
        "write_file",
        "apply_patch",
        "run_command",
    } <= names


def test_default_allow_list_has_security_scanners_not_git() -> None:
    """bandit + semgrep are allow-listed (static scanners — read code, don't run it);
    git stays excluded (it would escape the worktree/mutate shared .git)."""
    from subagents.tools import DEFAULT_ALLOWED_COMMANDS

    assert {"bandit", "semgrep"} <= DEFAULT_ALLOWED_COMMANDS
    assert "git" not in DEFAULT_ALLOWED_COMMANDS
