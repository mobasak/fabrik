"""W-ed75e99d — a MISSING synced hook script warns, it never blocks.

The fleet-synced ``.claude/settings.json`` wires every hook as ``python3 "${CLAUDE_PROJECT_DIR}/<script>"``.
In a checkout that lacks the gitignored synced copies (a linked worktree made by a bare ``git worktree add``,
or one whose ``.worktreeinclude`` copy did not fire) Python exits 2 with ``can't open file`` — and exit 2 is
Claude Code's BLOCKING code, so on ``UserPromptSubmit`` EVERY prompt died with "operation blocked by hook"
before the agent could be told the remedy. Each hook line now carries a file-exists guard with a VISIBLE
notice on the channel the event shows — stdout + exit 0 on ``UserPromptSubmit``/``SessionStart`` (context
Claude sees), stderr + the non-blocking exit 1 on ``Stop``/``PreToolUse`` (a transcript ``hook error`` notice
carrying stderr's first line) — instead of a silent exit, the cobra (D-253) a bare ``|| exit 0`` would be.

Input domain: the live ``.claude/settings.json`` of this checkout, every ``hooks.*[].hooks[].command``. Each
command is EXECUTED through ``bash -c`` (and ``sh -c``, dash on this box) with ``CLAUDE_PROJECT_DIR`` pointed
at a tmp project whose path carries a SPACE, the env stripped to PATH/HOME, stdin a minimal hook payload. No
fixtures borrowed. Legacy lines that were already missing-safe by their own design (``agent_status.py``:
``test -f … || true``; ``seat_guard.py``: ``[ -f "$f" ] || exit 0``, W-6569a3fa) are exempt from the NOTICE
assertion only — never exit 2 is asserted for every line.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SETTINGS = REPO / ".claude" / "settings.json"
#: the two lines guarded before this change, silently — their rc 0 is asserted, their (absent) notice is not
LEGACY_SILENT = {"scripts/agent_status.py", ".claude/hooks/seat_guard.py"}
#: the events whose exit-0 stdout Claude Code adds as context (docs § Exit codes); elsewhere the notice is
#: stderr + exit 1, and a transcript notice carries stderr's FIRST line
STDOUT_EVENTS = {"UserPromptSubmit", "SessionStart"}
PAYLOAD = '{"tool_name":"Bash","tool_input":{"command":"ls"},"prompt":"x","session_id":"s1"}'
_SCRIPT = re.compile(r'\$\{CLAUDE_PROJECT_DIR\}/([^"]+)"')
#: the flags each wired line passes after its script — PINNED here, never derived from the command under test
#: (a derived expectation moves with the mutant that drops the flag; review seat B-sonnet's surviving mutant)
EXPECTED_FLAGS: dict[tuple[str, str], list[str]] = {
    ("SessionStart", ".claude/hooks/final_gate_stop.py"): ["--baseline"],
    ("SessionStart", "scripts/thread_anchor.py"): ["line", "--hook"],
    ("UserPromptSubmit", "scripts/thread_anchor.py"): ["line", "--hook"],
}


def _commands() -> list[tuple[str, str]]:
    d = json.loads(SETTINGS.read_text(encoding="utf-8"))
    return [
        (ev, h["command"])
        for ev, rules in d["hooks"].items()
        for r in rules
        for h in r.get("hooks", [])
    ]


def _script_of(cmd: str) -> str | None:
    """The repo-relative script a command runs, or None for a line of another shape (collection must never
    die on one: `test_every_hook_line_has_the_guardable_shape` names it instead)."""
    m = _SCRIPT.search(cmd)
    return m.group(1) if m else None


def _guardable() -> list[tuple[str, str]]:
    return [(ev, cmd) for ev, cmd in _commands() if _script_of(cmd)]


def _ids() -> list[str]:
    return [f"{ev}:{Path(str(_script_of(cmd))).name}" for ev, cmd in _guardable()]


def _line(event: str, script: str) -> str:
    return next(c for ev, c in _commands() if ev == event and _script_of(c) == script)


def _run(cmd: str, project_dir: Path, shell: str = "bash") -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ.get("HOME", "/"),
        "CLAUDE_PROJECT_DIR": str(project_dir),
    }
    return subprocess.run(
        [shell, "-c", cmd],
        env=env,
        input=PAYLOAD,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _bare_project(tmp_path: Path) -> Path:
    """A checkout holding only the synced settings.json — the shape a bare `git worktree add` leaves — under a
    path with a SPACE, so every `"$f"` quote in the guard is load-bearing."""
    proj = tmp_path / "w t"
    (proj / ".claude").mkdir(parents=True)
    (proj / ".claude" / "settings.json").write_text(
        SETTINGS.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return proj


def _checker():
    spec = importlib.util.spec_from_file_location(
        "check_hooks_index", REPO / "scripts" / "enforcement" / "check_hooks_index.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_every_hook_line_has_the_guardable_shape() -> None:
    """B0 — every wired command runs `python3 "${CLAUDE_PROJECT_DIR}/<script>"`: a line of another shape
    (an inline `node`, an unquoted path) is named here instead of erroring the whole module at collection."""
    odd = [(ev, cmd) for ev, cmd in _commands() if not _script_of(cmd)]
    assert not odd, odd


@pytest.mark.parametrize(
    "shell", ["bash", "sh"]
)  # the hook shell is the user's; /bin/sh is dash on this box
@pytest.mark.parametrize(("event", "cmd"), _guardable(), ids=_ids())
def test_every_wired_hook_survives_a_missing_script(
    tmp_path: Path, event: str, cmd: str, shell: str
) -> None:
    """B1 — the script is absent: never the blocking exit 2; the notice names the missing path and the remedy
    on the channel the event shows (stdout + 0 on UserPromptSubmit/SessionStart, the FIRST stderr line + 1
    elsewhere), under bash and dash."""
    proj = _bare_project(tmp_path)
    r = _run(cmd, proj, shell)
    assert r.returncode != 2, (event, cmd, r.returncode, r.stderr)  # 2 is the one code that blocks
    script = str(_script_of(cmd))
    if script in LEGACY_SILENT:
        assert r.returncode == 0, (event, r.returncode, r.stderr)
        return
    notice = f"HOOK MISSING: {proj}/{script}"
    if event in STDOUT_EVENTS:
        assert r.returncode == 0 and notice in r.stdout and "main checkout" in r.stdout, (
            event,
            r.stdout,
            r.stderr,
        )
    else:
        first = r.stderr.splitlines()[0] if r.stderr else ""
        assert r.returncode == 1 and first.startswith(notice) and "main checkout" in first, (
            event,
            r.stdout,
            r.stderr,
        )


def test_the_notice_keeps_a_backslash_in_the_path_literal(tmp_path: Path) -> None:
    """B1b — dash's `echo` interprets backslash escapes, so a path holding `\\t` printed a TAB; the notice is
    written with `printf '%s\\n'` (review seat A-sonnet). The project dir here carries a literal backslash-t."""
    proj = tmp_path / "x\\ty"
    (proj / ".claude").mkdir(parents=True)
    (proj / ".claude" / "settings.json").write_text(
        SETTINGS.read_text(encoding="utf-8"), encoding="utf-8"
    )
    for shell in ("bash", "sh"):
        r = _run(_line("UserPromptSubmit", ".claude/hooks/skill_router.py"), proj, shell)
        assert (
            r.returncode == 0 and f"HOOK MISSING: {proj}/" in r.stdout and "\t" not in r.stdout
        ), (shell, r.stdout)


@pytest.mark.parametrize(("event", "cmd"), _guardable(), ids=_ids())
def test_the_guard_keeps_a_present_hooks_exit_code(tmp_path: Path, event: str, cmd: str) -> None:
    """B2 — the script is PRESENT and blocks (exit 2): the guarded line returns 2 with the hook's own stderr,
    the whole stdin payload and the line's ORIGINAL flags, so a Stop or PreToolUse block is never masked and
    `--baseline` / `line --hook` survive the guard (kills `…; python3 "$f"; exit 0` and a dropped flag)."""
    script = str(_script_of(cmd))
    if script in LEGACY_SILENT:
        pytest.skip("legacy line, masks by its own design (W-6569a3fa / agent_status `|| true`)")
    proj = _bare_project(tmp_path)
    stub = proj / script
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_text(
        "import sys\nn = len(sys.stdin.read())\n"
        "sys.stderr.write(f'STUB-BLOCK len={n} argv={sys.argv[1:]!r}\\n')\nsys.exit(2)\n",
        encoding="utf-8",
    )
    r = _run(cmd, proj)
    # rc 2 with the hook's own stderr, the WHOLE payload (the guard reads no stdin) and the original argv tail
    want = EXPECTED_FLAGS.get((event, script), [])
    assert r.returncode == 2 and f"STUB-BLOCK len={len(PAYLOAD)} argv={want!r}" in r.stderr, (
        event,
        r.returncode,
        r.stderr,
    )
    assert "HOOK MISSING" not in r.stdout + r.stderr, (r.stdout, r.stderr)


def test_the_notice_is_short_and_names_no_second_script(tmp_path: Path) -> None:
    """B3 — each command stays under the 10,000-char hook-output cap and, run through the REAL
    `check_hooks_index._settings_hooks` one command at a time, yields only the hook it runs as a script token
    (the checker reads every `*.py|js|sh` token of a command as a hook owing an index row, so the notice may
    name no second script — the hub's sync script is named without its extension on purpose)."""
    mod = _checker()
    for ev, cmd in _guardable():
        assert len(cmd) < 10_000, (len(cmd), cmd)
        one = tmp_path / f"{ev}.json"
        one.write_text(
            json.dumps({"hooks": {ev: [{"hooks": [{"type": "command", "command": cmd}]}]}})
        )
        tokens = {n for n in mod._settings_hooks(one) if n.endswith((".py", ".js", ".sh"))}
        assert tokens == {Path(str(_script_of(cmd))).name}, (cmd, tokens)


def test_the_hooks_index_checker_still_sees_every_hook() -> None:
    """B4 — `check_hooks_index._settings_hooks` over the live file yields exactly the 10 distinct hook
    basenames the 13 commands run (plus the event names): the guard changed no line's required index row."""
    got = {n for n in _checker()._settings_hooks(SETTINGS) if n.endswith((".py", ".js", ".sh"))}
    want = {Path(str(_script_of(cmd))).name for _ev, cmd in _guardable()}
    assert got == want and len(want) == 10, (sorted(got ^ want), len(want))


@pytest.mark.parametrize(
    ("event", "script"),
    [
        ("UserPromptSubmit", ".claude/hooks/skill_router.py"),
        ("Stop", ".claude/hooks/final_gate_stop.py"),
    ],
)
def test_an_unreadable_present_hook_warns_too(tmp_path: Path, event: str, script: str) -> None:
    """B5 — a present but unreadable script (mode 000) made the bare `python3` exit 2 (`Permission denied`)
    exactly like a missing one; the guard treats it as missing and warns on the event's channel (critique
    seat fable-1, C3) — one stdout event and one stderr event."""
    if os.geteuid() == 0:
        pytest.skip("root reads a mode-000 file")
    proj = _bare_project(tmp_path)
    stub = proj / script
    stub.parent.mkdir(parents=True)
    stub.write_text("raise SystemExit(2)\n", encoding="utf-8")
    stub.chmod(0)
    try:
        r = _run(_line(event, script), proj)
    finally:
        stub.chmod(0o600)
    out = r.stdout if event in STDOUT_EVENTS else r.stderr
    assert (
        r.returncode == (0 if event in STDOUT_EVENTS else 1) and f"HOOK MISSING: {stub}" in out
    ), (
        r.returncode,
        r.stdout,
        r.stderr,
    )


def test_a_directory_at_the_hook_path_warns_too(tmp_path: Path) -> None:
    """B6 — a DIRECTORY at the script path passes `[ -r` (directories are readable), and the bare interpreter
    then exits 1 with no notice and no hook; the guard also requires a regular file (review seat B-haiku)."""
    proj = _bare_project(tmp_path)
    (proj / ".claude" / "hooks" / "skill_router.py").mkdir(parents=True)
    r = _run(_line("UserPromptSubmit", ".claude/hooks/skill_router.py"), proj)
    assert r.returncode == 0 and "HOOK MISSING:" in r.stdout and "skill_router.py" in r.stdout, (
        r.stdout,
        r.stderr,
    )
