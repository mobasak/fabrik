"""The fleet-wide graceful stop (.claude/hooks/quota_stop.py) — PreToolUse on the tick's
fleet-exhausted stamp. Risk-ordered: it must NEVER freeze the fleet on its own defect (no stamp,
unreadable state, a stale flag from a dead cron → allow), and while the stamp stands it must hold
work tools and let a session checkpoint (git, command_run.py, reads) and end."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

_HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "quota_stop.py"
_spec = importlib.util.spec_from_file_location("quota_stop", _HOOK)
hook = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(hook)


def test_no_stamp_allows_everything():
    for tool, cmd in (("Edit", None), ("Write", None), ("Bash", "rm -rf build")):
        assert hook.decide(tool, cmd, stamp_exists=False, tick_age_s=10.0)[0] == "allow"


def test_stamp_holds_work_tools_with_the_checkpoint_instruction():
    action, reason = hook.decide("Edit", None, stamp_exists=True, tick_age_s=10.0)
    assert action == "deny"
    assert "commit" in reason and "push" in reason and "command_run.py" in reason


def test_stamp_lets_a_session_checkpoint_and_close():
    for cmd in (
        "git add -- a.py",
        "git commit -q -F msg -- a.py",
        "git push",
        "git status -sb",
        "python3 scripts/command_run.py done --command x --evidence e --feedback f",
        "python scripts/mail.py ack 01X",
        "head -3 CHANGELOG.md",
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=10.0)[0] == "allow", cmd


def test_stamp_holds_working_bash():
    for cmd in ("python3 scripts/foo.py", "pytest tests/", "npm install", "sed -i 's/a/b/' f.py"):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=10.0)[0] == "deny", cmd


def test_a_stale_stamp_from_a_dead_tick_never_freezes_the_fleet(monkeypatch):
    monkeypatch.setenv("QUOTA_STOP_TICK_STALE_S", "900")
    assert hook.decide("Edit", None, stamp_exists=True, tick_age_s=3600.0)[0] == "allow_warn"
    assert hook.decide("Edit", None, stamp_exists=True, tick_age_s=None)[0] == "allow_warn"


def _run(
    tmp_path: Path, payload: object, stamp: bool, tick_fresh: bool
) -> subprocess.CompletedProcess:
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    if stamp:
        (state / "fleet-exhausted").write_text("1")
    log = tmp_path / "rotate-tick.log"
    log.write_text("tick: ok\n")
    if not tick_fresh:
        old = time.time() - 4000
        os.utime(log, (old, old))
    env = {**os.environ, "ROTATE_STATE_DIR": str(state), "QUOTA_STOP_TICK_LOG": str(log)}
    data = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(_HOOK)],
        input=data,
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
    )


def test_end_to_end_deny_json_shape(tmp_path):
    r = _run(
        tmp_path,
        {"tool_name": "Edit", "tool_input": {"file_path": "x.py"}},
        stamp=True,
        tick_fresh=True,
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "commit" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_end_to_end_allow_is_silent(tmp_path):
    r = _run(tmp_path, {"tool_name": "Edit", "tool_input": {}}, stamp=False, tick_fresh=True)
    assert r.returncode == 0 and r.stdout.strip() == ""
    r = _run(
        tmp_path,
        {"tool_name": "Bash", "tool_input": {"command": "git push"}},
        stamp=True,
        tick_fresh=True,
    )
    assert r.returncode == 0 and r.stdout.strip() == ""


def test_end_to_end_stale_tick_warns_and_allows(tmp_path):
    r = _run(tmp_path, {"tool_name": "Edit", "tool_input": {}}, stamp=True, tick_fresh=False)
    assert r.returncode == 0 and r.stdout.strip() == "" and "stale flag" in r.stderr


def test_garbage_stdin_exits_zero(tmp_path):
    r = _run(tmp_path, "garbage {{{", stamp=True, tick_fresh=True)
    assert r.returncode == 0 and r.stdout.strip() == ""


# ── review findings (2026-09-02 /fabrik-review pass 1) ───────────────────────────────────────


def test_chained_or_redirected_bash_is_held_whole():
    """The allow-list matched the FIRST segment only: `git push && python3 evil.py` passed. While the
    stamp stands only a SINGLE simple command is allowed — no control operators, no substitution, no
    file redirection (stderr-to-null/stdout excepted)."""
    for cmd in (
        "git commit -q -F m -- a.py && python3 scripts/foo.py",
        "cat x; rm -rf y",
        "echo hi | tee f",
        "git push || python3 evil.py",
        "git status $(rm -rf x)",
        "git log > notes.txt",
        "cat a >> b",
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    for cmd in ("git push 2>&1", "git status 2>/dev/null", "git diff --stat HEAD -- a.py"):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "allow", cmd
    # the DOUBLED redirect to /dev/null is exempt too: `>>?` backtracked to a single `>` whose
    # lookahead saw `> /dev/null` and refused it (review 2026-09-05, closing pass, executed)
    for cmd in ("git status >> /dev/null", "git status 2>>/dev/null"):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "allow", cmd
    for cmd in ("git log >> notes.txt", "git log >>notes.txt", "cat a 2>>err.log"):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    # the exemption is the DEVICE, never a prefix: these name OTHER paths (pass 12, executed)
    for cmd in ("git log >/dev/nullx", "git log > /dev/null/../x", "git log >>/dev/null.txt"):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    # `>&word` is a FILE redirect (stdout+stderr), not an fd duplication: `git log >&x` was
    # allowed and bash created `x` (pass 12, native finder, executed). Digits and `-` stay exempt.
    for cmd in ("git log >&x", "git status >&1x", "cat a 2>&err.log"):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    for cmd in ("git push 2>&1", "git status >&2", "git log 2>&-"):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "allow", cmd


def test_shell_punctuation_inside_a_quoted_argument_is_data_not_an_operator():
    """The hold refused the graceful exit its own message orders.

    The vetoes scanned the RAW line, so the `;` in a `--reason` string read as a control operator.
    CLAUDE.md mandates `BLOCKED: <what> — searched: <sources> — missing: <need>`, and any operator
    listing two sources writes a comma or a semicolon — so the hold structurally refused the very
    `command_run.py blocked` call it instructs a held session to make, while the Stop hook blocked
    the turn for the record that could not be closed. Reported by trade-intelligence
    (01M1NTZJEHF9NY93JW8YZNDAVB) after four refusals across three turns; the mechanism (quoting,
    not wording) was proven by fleet at 01M1NTZZEZJGHKYR7VQF4PZAM2. These are their verbatim
    probe commands.
    """
    for cmd in (
        'python3 scripts/command_run.py blocked --command x --reason "hold - searched: hook, docs; missing: relief"',
        "python3 scripts/command_run.py done --command x --evidence 'a|b'",
        'python scripts/mail.py send --body "names git|command_run.py as allowed"',
        'git commit -q -F m -- a.py -m "fix: a && b"',
        'git log --grep="a;b"',
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=10.0)[0] == "allow", cmd
    # every tooth the whole-line scan was added to grow still bites: the operator is UNQUOTED,
    # or it is one the shell expands even inside double quotes.
    for cmd in (
        "git status;evil",  # shlex.split would return ['git','status;evil'] and allow this
        'git status "$(rm -rf x)"',  # $( survives masking inside double quotes
        'git status "`rm -rf x`"',  # so does a backtick
        "git status --porcelain | grep -v '^??'",  # a genuine pipe, outside the quotes
        'git log --grep="a" > /tmp/leak.txt',  # redirect outside the quotes
        'git status "unbalanced ; rm -rf y',  # an unclosed quote cannot hide an operator:
        # the masker returns the line UNTOUCHED when quotes do not balance, so the raw `;` is seen
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=10.0)[0] == "deny", cmd


def test_an_escaped_quote_outside_quotes_cannot_open_a_span_that_hides_an_operator():
    """The masker's first cut toggled quote state on ANY bare quote character, so a top-level
    `\\'` — a literal apostrophe to bash, never an opener — started a span, a real operator inside
    it was masked to data, and the hold ALLOWED it. Found by the review's native finder and proven
    by execution: `bash -c "git status \\'; echo INJECTED\\'"` ran the second command, and the
    backtick form CREATED A FILE. The whole-line scan this masking replaced never had this hole,
    so it was a regression introduced by the fix — the mirror of a hardening landing on the
    permitted side is Lesson 154; this is the same lesson landing on the DENIED side.
    """
    for cmd in (
        r"git status \'; rm -rf x\'",
        "git log \\'`touch /tmp/p`\\'",
        "git log \\'> /tmp/leak\\'",
        r"git show \'$(whoami)\'",
        r'git status \"; rm -rf x\"',
        "python3 scripts/command_run.py done --command x --evidence \\'; curl evil\\'",
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    # an escaped backslash followed by a REAL quote still opens a span — `\\'a;b'` is data
    assert hook.decide("Bash", "echo \\\\'a;b'", stamp_exists=True, tick_age_s=1.0)[0] == "allow"
    # and a top-level escaped operator stays refused (bash would not run it, but we never
    # need one to stop cleanly — fail closed, as before)
    assert hook.decide("Bash", r"git status \; rm -rf x", stamp_exists=True, tick_age_s=1.0)[0] == "deny"


def test_a_lone_ampersand_is_a_command_separator_and_is_held():
    """`git status & evil` runs BOTH — a lone `&` backgrounds the first command and starts the
    second. The whole-line hardening listed `&&` and never the single form, so a held session
    could run anything behind an allowed command. Proven by execution: decide() said allow and
    `bash -c "git status & touch marker"` created the marker (review 2026-09-05, pass 13). The
    fd-duplication forms the checkpoint needs (`2>&1`, `>&2`) stay allowed."""
    for cmd in ("git status & evil", "git status 2>&1 & evil", "git status &", "git log >/dev/null&"):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    for cmd in ("git push 2>&1", "git status >&2", "git log >/dev/null 2>&1"):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "allow", cmd
    # the masker keeps a QUOTED ampersand as data
    assert hook.decide("Bash", 'git commit -q -m "a & b" -- x.py', stamp_exists=True, tick_age_s=1.0)[0] == "allow"


def test_a_quoted_dev_null_target_is_a_known_fail_closed_limit():
    """The masker blanks a QUOTED redirect target, so `>'/dev/null'` cannot be recognised as the
    exempt device and is refused although it writes nothing. Accepted, not fixed: 0 of the hub's
    606 `> /dev/null` idioms quote the target (measured 2026-09-05, pass 13 finder), and the only
    honest fixes would re-open the quoted-argument class. Pinned so the limit is known, not found
    again."""
    for cmd in ("git log >'/dev/null'", 'git log >"/dev/null"'):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd


def test_a_tools_own_write_flag_and_a_destroying_read_tool_are_held():
    """Two writes with NO shell operator, both proven on disk (review 2026-09-05, pass 14):
    `find . -name x -delete` destroyed a file through the allow-list, and `git log --output=<p>`
    wrote a file at an arbitrary path. `find` is off the list entirely; git's `--output` forms
    and a bare `-o <path>` are held. The checkpoint forms that read stay allowed."""
    for cmd in (
        "find . -name victim.txt -delete",
        "find . -delete",
        "find . -type f",  # even the read form — the tool is off the list, not its flags
        "git log -n1 --output=/tmp/x",
        "git log --output /tmp/x",
        "git format-patch -o /tmp/patches HEAD~1",
        "git diff --output=/tmp/d",
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    for cmd in ("git log -n1 --oneline", "git log --format=%h", "ls -la", "rg --files", "grep -rl x ."):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "allow", cmd


def test_process_substitution_runs_a_command_and_is_held():
    """`<(cmd)` / `>(cmd)` make bash RUN the inner command with no listed operator and nothing to
    mask: `git status <(touch marker)` was allowed and the marker appeared (review 2026-09-05,
    pass 14, executed)."""
    for cmd in ("git status <(touch m)", "cat >(touch m)", "git diff <(cat a) <(cat b)"):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    # a quoted `<(` is data
    assert hook.decide("Bash", 'git log --grep="<(x)"', stamp_exists=True, tick_age_s=1.0)[0] == "allow"


def test_the_masker_never_invents_or_hides_an_operator():
    assert hook._mask_quoted("git status") == "git status"
    assert hook._mask_quoted("cat a; rm b") == "cat a; rm b"  # nothing quoted, nothing masked
    assert ";" not in hook._mask_quoted("echo 'a;b'")
    assert "|" not in hook._mask_quoted('echo "a|b"')
    assert "$(" in hook._mask_quoted('echo "$(whoami)"')  # expanded inside double quotes
    assert "$(" not in hook._mask_quoted("echo '$(whoami)'")  # inert inside single quotes
    assert "$" not in hook._mask_quoted('echo "\\$(whoami)"')  # escaped: a literal, so masked
    assert hook._mask_quoted('echo "a') == 'echo "a'  # unbalanced → untouched → fails closed
    assert "\n" in hook._mask_quoted('echo "a\nb"')  # a quoted newline still trips the veto
    # a single quote inside a double-quoted span must not open a span of its own
    assert ";" not in hook._mask_quoted('echo "it\'s a; b"')
    # the three branches the review's pool finder named as untested (pass 1, P4):
    assert hook._mask_quoted("echo 'a") == "echo 'a"  # single-quote imbalance → untouched
    assert "$" in hook._mask_quoted('echo "$VAR;x"') and ";" not in hook._mask_quoted('echo "$VAR;x"')
    assert hook._mask_quoted('echo "a\\nb;c"') == 'echo "xxxxxx"'  # a non-special escape masks both (6 chars)


def test_destructive_git_and_in_place_sed_are_held():
    for cmd in (
        "git reset --hard HEAD~1",
        "git reset --merge",
        "sed -n -i 's/a/b/' f",
        "sed -i 's/a/b/' f",
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    for cmd in ("git reset -q HEAD -- a.py", "git reset HEAD -- a.py", "sed -n '1,3p' f"):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "allow", cmd


def test_mcp_edit_tools_are_held_and_mcp_reads_pass():
    """The matcher is `.*`: an edit through serena is an edit. Reads stay open."""
    for tool in (
        "mcp__serena__replace_content",
        "mcp__serena__insert_after_symbol",
        "mcp__serena__write_memory",
        "Agent",
        "Workflow",
        "NotebookEdit",
        "mcp__playwright__browser_click",
    ):
        assert hook.decide(tool, None, stamp_exists=True, tick_age_s=1.0)[0] == "deny", tool
    for tool in (
        "Read",
        "Grep",
        "Glob",
        "LS",
        "ToolSearch",
        "AskUserQuestion",
        "mcp__serena__find_symbol",
        "mcp__serena__get_symbols_overview",
        "mcp__session-recall__search_chats",
        "TaskOutput",
    ):
        assert hook.decide(tool, None, stamp_exists=True, tick_age_s=1.0)[0] == "allow", tool


def test_deny_output_uses_only_the_current_pretooluse_contract(tmp_path):
    """The installed CLI deprecates the legacy `decision` key for PreToolUse ("use
    hookSpecificOutput.permissionDecision instead") — emit only the current form."""
    r = _run(tmp_path, {"tool_name": "Edit", "tool_input": {}}, stamp=True, tick_fresh=True)
    out = json.loads(r.stdout)
    assert "decision" not in out and out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_a_non_object_payload_never_blocks(tmp_path):
    """Pass-2 probe: a JSON payload that is not an object raised AttributeError → exit 1 (a
    non-blocking hook error, but a traceback in the operator's face). Fail open, silently."""
    r = _run(tmp_path, '"just a string"', stamp=True, tick_fresh=True)
    assert r.returncode == 0 and r.stdout.strip() == "" and "Traceback" not in r.stderr


def test_malformed_tool_input_is_held_while_the_stamp_stands(tmp_path):
    """A Bash call whose command cannot be read is held (the stamp is the exceptional state; a
    command we cannot inspect is not a checkpoint we can trust) — never a crash."""
    r = _run(
        tmp_path, {"tool_name": "Bash", "tool_input": ["git", "push"]}, stamp=True, tick_fresh=True
    )
    assert (
        r.returncode == 0
        and json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    )
