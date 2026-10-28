"""Behaviour graders for the PreToolUse seat guard (.claude/hooks/seat_guard.py, W-6569a3fa).

Review seats (agent_type fabrik-reviewer) run Bash in the lead's shared tree. Three repos took
live damage from a seat's `git checkout/reset/commit` in a main checkout and a seat's
`pkill -f`; the guard refuses those two classes at the tool layer, for seats only.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / ".claude" / "hooks" / "seat_guard.py"
SID = "sid-seat"
SCRATCH = f"/tmp/claude-1000/-opt-x/{SID}/scratchpad"


def _run(
    command: str,
    *,
    agent_type: str | None = "fabrik-reviewer",
    cwd: str = "/opt/fabrik",
    raw: str | None = None,
) -> str:
    payload: dict = {
        "session_id": SID,
        "cwd": cwd,
        "scratchpad_dir": SCRATCH,
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }
    if agent_type is not None:
        payload["agent_id"] = "agent-1"
        payload["agent_type"] = agent_type
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=raw if raw is not None else json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout


def _denied(out: str) -> bool:
    if not out.strip():
        return False
    return json.loads(out)["hookSpecificOutput"].get("permissionDecision") == "deny"


_PREFIX = "export PYTHON_DOTENV_DISABLED=1"


def _rewritten(out: str) -> dict | None:
    """The `updatedInput` a seat's allowed call is rewritten to, or None."""
    if not out.strip():
        return None
    return json.loads(out)["hookSpecificOutput"].get("updatedInput")


def test_pattern_kills_are_denied_numeric_pids_pass() -> None:
    for cmd in (
        "pkill -f mail_watch_arm.sh",
        "killall python3",
        "kill $(pgrep -f watch)",
        "echo x && pkill watch",
    ):
        assert _denied(_run(cmd)), cmd
    for cmd in ("kill 1234", "kill -9 1234", "kill -s TERM 1234 5678", "kill %1"):
        assert not _denied(_run(cmd)), cmd


def test_git_writes_only_in_scratch() -> None:
    for cmd in (
        "git reset --hard",
        "git checkout -- .",
        "git commit -m x",
        "git stash",
        "git -C /opt/fabrik commit -am x",
        "git clean -fdx",
    ):
        assert _denied(_run(cmd)), cmd
    for cmd in (
        f"git -C {SCRATCH}/repo commit -m x",
        f"git -C {SCRATCH}/repo reset --hard",
        "git -C /tmp/probe/r checkout -b t",
    ):
        assert not _denied(_run(cmd)), cmd
    # the payload cwd itself inside scratch is allowed
    assert not _denied(_run("git commit -m x", cwd=f"{SCRATCH}/repo"))


def test_cd_and_bash_c_are_followed() -> None:
    assert _denied(_run("cd /opt/x && git checkout .", cwd=SCRATCH))
    assert not _denied(_run(f"cd {SCRATCH}/repo && git commit -m x"))
    assert _denied(_run('bash -c "git reset --hard"'))
    assert _denied(_run("sh -c 'pkill -f x'"))


def test_read_only_git_passes() -> None:
    for cmd in (
        "git status",
        "git log --oneline -5",
        "git diff HEAD",
        "git show HEAD:x",
        "git -C /opt/fabrik ls-files",
        f"git archive HEAD -o {SCRATCH}/a.tar",
        "git worktree list",
        "timeout 120 /usr/bin/grep -rn x .",
        "ls -la",
    ):
        assert not _denied(_run(cmd)), cmd


def test_lead_and_other_agents_are_untouched() -> None:
    assert not _denied(_run("git reset --hard", agent_type=None))
    assert not _denied(_run("pkill -f x", agent_type=None))
    assert not _denied(_run("git reset --hard", agent_type="general-purpose"))


def test_the_deny_names_the_safe_form() -> None:
    reason = json.loads(_run("git commit -m x"))["hookSpecificOutput"]["permissionDecisionReason"]
    assert "git -C" in reason and "scratch" in reason


def test_fail_open() -> None:
    assert _run("", raw="not json") == ""
    assert _run("", raw=json.dumps({"tool_name": "Bash"})) == ""


# ── rework (round 1 + the Opus design critique, every payload executed) ──────────────────


def test_quoted_data_is_never_a_command() -> None:
    """A commit message or printed text holding `;`, `&&`, `|` or a git/kill word is data."""
    for cmd in (
        f'git -C {SCRATCH}/repo commit -m "build && test; done | ok"',
        "printf '%s\\n' 'git reset --hard; pkill -f x' > " + SCRATCH + "/probe.txt",
        'echo "cd /opt/x && git checkout ."',
        "python3 -c 'print(\"git reset --hard\")'",
    ):
        assert not _denied(_run(cmd)), cmd


def test_a_quoted_separator_does_not_hide_a_write() -> None:
    assert _denied(_run('git commit -m "subject; body"'))
    assert _denied(_run('git -C /opt/fabrik commit -m "a | b"'))


def test_redirected_git_targets_are_followed() -> None:
    for cmd in (
        "git --git-dir=/opt/x/.git --work-tree=/opt/x checkout .",
        "git --git-dir /opt/x/.git --work-tree /opt/x reset --hard",
        "GIT_DIR=/opt/x/.git GIT_WORK_TREE=/opt/x git reset --hard",
        "env -C /opt/x git reset --hard",
        f"git -C {SCRATCH} --work-tree=/opt/x checkout .",
    ):
        assert _denied(_run(cmd, cwd=SCRATCH)), cmd


def test_subshells_groups_and_nested_shells() -> None:
    for cmd in (
        "(cd /opt/x; git reset --hard)",
        "{ cd /opt/x; git reset --hard; }",
        "if true; then git reset --hard; fi",
        'bash -lc "git reset --hard"',
        'bash -e -c "git status; git reset --hard"',
        "bash -c \"bash -c 'git reset --hard'\"",
        'bash -c "cd /opt/fabrik && git checkout ."',
    ):
        assert _denied(_run(cmd)), cmd


def test_kill_variants() -> None:
    for cmd in (
        "pgrep -f watch | xargs kill",
        "xargs pkill -f x < pids.txt",
        "kill -9 -1",
        "kill -- -1",
        "kill 0",
        "kill -TERM -4242",
    ):
        assert _denied(_run(cmd)), cmd
    for cmd in ("kill -l", "kill -l TERM", "kill -term 1234", "kill -s term 1234", "kill -0 1234"):
        assert not _denied(_run(cmd)), cmd


def test_read_only_forms_of_write_verbs_pass() -> None:
    for cmd in (
        "git stash list",
        "git stash show -p",
        "git clean -n",
        "git clean --dry-run -d",
        "git branch --show-current",
        "git config --get user.name",
        f"git worktree add {SCRATCH}/probe HEAD",
    ):
        assert not _denied(_run(cmd)), cmd


def test_shared_store_writes_and_worktree_moves_outside_scratch_are_denied() -> None:
    for cmd in (
        "git worktree add /opt/evil HEAD",
        "git worktree remove --force /opt/fabrik/.claude/worktrees/intel",
        "git branch -f master HEAD~1",
        "git update-ref refs/heads/master HEAD~1",
        "git config core.hooksPath /dev/null",
        "git tag -d v1",
    ):
        assert _denied(_run(cmd)), cmd


def test_the_scratch_root_is_this_session_not_all_of_tmp() -> None:
    """Another session's scratch (a sibling's probe worktree) is NOT this seat's scratch."""
    other = "/tmp/claude-1000/-opt-fabrik--claude-worktrees-intel/other-sid/scratchpad/cf/probe"
    assert _denied(_run(f"git -C {other} reset --hard"))
    assert not _denied(_run(f"git -C {SCRATCH}/repo reset --hard"))


def test_an_unparseable_seat_command_with_a_write_verb_is_denied() -> None:
    """Fail-CLOSED for a seat when the text cannot be tokenised and names a git write or a kill."""
    assert _denied(_run('git commit -m "unterminated'))
    assert not _denied(_run('echo "unterminated'))


# ── v2 review round 1 (every payload executed by a seat) ─────────────────────────────


def test_substitutions_are_scanned_and_make_a_target_unknown() -> None:
    for cmd in (
        "git -C $(pwd) commit -m x",
        "git -C `pwd` reset --hard",
        "D=$(mktemp -d); git -C /opt/x init",
    ):
        assert _denied(_run(cmd, cwd=SCRATCH)), cmd
    for cmd in ("cat <(git reset --hard)", "echo $(git reset --hard)", "echo `pkill -f x`"):
        assert _denied(_run(cmd)), cmd  # cwd /opt/fabrik: the substituted command itself writes
    assert not _denied(_run("D=$(mktemp -d); echo $D", cwd=SCRATCH))


def test_merged_punctuation_still_splits() -> None:
    assert _denied(_run("(cd /tmp/a);git -C /opt/x reset --hard", cwd=SCRATCH))
    assert _denied(_run("true&&git -C /opt/x reset --hard", cwd=SCRATCH))


def test_core_worktree_and_pushd_are_followed() -> None:
    assert _denied(_run("git -c core.worktree=/opt/x checkout .", cwd=SCRATCH))
    assert _denied(_run("pushd /opt/x && git reset --hard", cwd=SCRATCH))
    assert _denied(_run("pushd /opt/x; git reset --hard; popd", cwd=SCRATCH))


def test_a_subshell_cd_does_not_leak() -> None:
    assert _denied(_run("(cd /tmp/x); git reset --hard"))  # cwd /opt/fabrik


def test_heredoc_bodies_are_data() -> None:
    body = f"cat > {SCRATCH}/notes.txt << 'EOF'\ngit reset --hard\npkill -f x\nEOF"
    assert not _denied(_run(body))
    body2 = f"cat <<EOF > {SCRATCH}/n\nkill -9 -1\nEOF\ngit -C /opt/x reset --hard"
    assert _denied(_run(body2))  # the line AFTER the terminator is a command again


def test_a_marker_the_shell_does_not_read_as_a_heredoc_hides_nothing() -> None:
    """W-223704c1: only an unquoted, uncommented `<<WORD` opens a body; anything else that
    looks like one (quoted text, a comment, a here-string, an arithmetic shift, an escaped
    `<`) must leave the following lines in the scan."""
    for cmd in (
        "echo 'x <<EOF'\ngit -C /opt/fabrik commit -m y",
        'echo "see <<EOF"\ngit reset --hard',
        "echo 'a\n<<EOF'\ngit reset --hard",
        "echo x # <<EOF\ngit reset --hard",
        "# <<EOF\npkill -f x",
        "cat <<<EOF\ngit reset --hard",
        "echo $((1<<x))\ngit reset --hard",
        "(( y = 1<<x ))\ngit reset --hard",
        "echo x \\<<EOF\ngit reset --hard",
        "echo $'it\\'s <<EOF'\ngit reset --hard",
        "echo ${x:-<<EOF}\ngit reset --hard",
        "echo `echo <<EOF`\ngit reset --hard",
        'echo "$(echo "<<EOF")"\ngit reset --hard',
        'echo ${x:-"}"}" <<EOF"\ngit reset --hard',
        'echo ${x:-"}"}" <<EOF" ${y:-"}"}\ngit reset --hard',
        'echo "$( (true); echo "<<EOF" )"\ngit reset --hard',
    ):
        assert _denied(_run(cmd)), cmd


def test_real_heredoc_spellings_still_hold_data() -> None:
    for cmd in (
        f'cat > {SCRATCH}/n <<"EOF"\ngit reset --hard\nEOF',
        f"cat > {SCRATCH}/n <<-EOF\n\tpkill -f x\n\tEOF",
        f"cat <<A > {SCRATCH}/a; cat <<'B' > {SCRATCH}/b\ngit reset --hard\nA\npkill -f x\nB",
        f"echo 'it''s' && cat <<EOF > {SCRATCH}/n\ngit reset --hard\nEOF",
        # the usual commit-message shape: a heredoc inside "$(…)", its body an unbalanced quote
        f"git -C {SCRATCH}/repo commit -m \"$(cat <<'EOF'\ndon't git reset --hard\nEOF\n)\"",
        # a closed "$(…)" or an inner subshell returns the walk to the right context
        f'echo "$(date)" && cat > {SCRATCH}/n <<EOF\ngit reset --hard\nEOF',
        "x=\"$( (true); cat <<'EOF'\ngit reset --hard\nEOF\n)\"",
        f"echo `date` ${{HOME}} && cat > {SCRATCH}/n <<EOF\ngit reset --hard\nEOF",
        f"echo $((1+1)) && cat > {SCRATCH}/n <<EOF\ngit reset --hard\nEOF",
        f"echo $[1+1] && cat > {SCRATCH}/n <<EOF\ngit reset --hard\nEOF",
        # a closed `case` (and a word merely ending in "case") leaves `)` closing "$(…)" again
        f'x="$(case a in a) :;; esac)"; cat > {SCRATCH}/n <<EOF\ngit reset --hard\nEOF',
        f'x="$(echo showcase)"; cat > {SCRATCH}/n <<EOF\ngit reset --hard\nEOF',
        f'x="$(cases a)"; cat > {SCRATCH}/n <<EOF\ngit reset --hard\nEOF',
    ):
        assert not _denied(_run(cmd)), cmd


def test_review_round_one_markers_hide_nothing() -> None:
    """W-223704c1 review round 1: a `case` pattern's `)` closed the enclosing `$(…)`, `$[…]`
    arithmetic read as a heredoc, and a delimiter was cut to its identifier prefix (`<<E-OF`
    ended at a line `E`) — each hid the next command from the scan."""
    for cmd in (
        'echo "$(case $x in a) echo "<<EOF";; esac)"\ngit reset --hard',
        "echo $[1<<n]\ngit reset --hard",
        f"cat > {SCRATCH}/n <<E-OF\nx\nE-OF\ngit reset --hard",
        f"cat > {SCRATCH}/n <<EOF-\nx\nEOF-\ngit reset --hard",
        f"cat > {SCRATCH}/n <<-EOF\n\tbody\n\tEOF\ngit reset --hard",
        # each shape below passes the word-boundary rule, so only its own clause decides
        "echo $[1<<n ]\ngit reset --hard",
        'echo "$(case $x in a) echo " <<EOF ";; esac)"\ngit reset --hard',
        # review round 2: `case`/`esac` are keywords only at command position (`echo case` is an
        # argument), else a `)` that closes "$(…)" was held open and a data `<<EOF` hid line 2
        "echo ${x:-$(echo case) <<EOF }\ngit reset --hard",
        "echo ${x:-$(grep -c case f) <<EOF }\ngit reset --hard",
        'x="$(case a in a) echo esac;; b) echo " <<EOF ";; esac)"\ngit reset --hard',
        'x="$(if true; then case a in a) echo " <<EOF ";; esac; fi)"\ngit reset --hard',
        'echo "$(echo case)<<EOF\n"\ngit reset --hard',
        # review round 2: the delimiter is the whole shell word, quoting removed — an opener read
        # as an identifier left its body in the scan, where an inner `<<Z` hid the line after it
        f"cat > {SCRATCH}/n <<E-OF\n<<Z\nE-OF\ngit reset --hard\nZ",
        f"cat > {SCRATCH}/n <<\\EOF\n <<Z\nEOF\ngit reset --hard\nZ",
        f"cat > {SCRATCH}/n <<E'OF'\nx\nEOF\ngit reset --hard",
    ):
        assert _denied(_run(cmd)), cmd


def test_strip_heredocs_drops_each_body_and_keeps_what_follows() -> None:
    """Review round 2 (B-haiku-7): the hook swallows a scanner exception, so an allow assertion
    through `_run` passes even when `_strip_heredocs` crashes. Graded here directly."""
    spec = importlib.util.spec_from_file_location("seat_guard_strip", HOOK)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for cmd, word in (
        ("cat <<E-OF\nBODY\nE-OF\nAFTER", "E-OF"),
        ("cat <<\\EOF\nBODY\nEOF\nAFTER", "EOF"),
        ("cat <<E'OF'\nBODY\nEOF\nAFTER", "EOF"),
        ('cat <<"a b"\nBODY\na b\nAFTER', "a b"),
        ('cat <<"a\\"b"\nBODY\na"b\nAFTER', 'a"b'),
        ("cat <<-EOF\n\tBODY\n\tEOF\nAFTER", "EOF"),
    ):
        out = mod._strip_heredocs(cmd)
        assert "BODY" not in out and out.endswith("\nAFTER"), (cmd, out)
        assert mod._heredoc_word(cmd.split("<<", 1)[1].split("\n", 1)[0].lstrip("-")) == word


def test_a_line_that_only_looks_like_the_terminator_keeps_the_body_data() -> None:
    """W-223704c1 review round 1: the terminator was compared after strip(), so an indented or
    space-trailed `EOF` ended the body early and the body's own lines were scanned as commands."""
    for cmd in (
        f"cat > {SCRATCH}/n <<EOF\n  EOF\ngit reset --hard\nEOF",
        f"cat > {SCRATCH}/n <<EOF\nEOF \ngit reset --hard\nEOF",
        f"cat > {SCRATCH}/n <<EOF\n\tEOF\ngit reset --hard\nEOF",
        f"cat > {SCRATCH}/n <<-EOF\n  EOF\ngit reset --hard\nEOF",
    ):
        assert not _denied(_run(cmd)), cmd


def test_explicit_git_dir_and_work_tree_in_scratch_pass() -> None:
    cmd = f"git --git-dir={SCRATCH}/r/.git --work-tree={SCRATCH}/r reset --hard"
    assert not _denied(_run(cmd))  # cwd /opt/fabrik is irrelevant when both are given


def test_job_zero_is_not_a_job() -> None:
    assert _denied(_run("kill %0"))
    assert not _denied(_run("kill %1"))


# ── v2 closing pass (round 2) ───────────────────────────────────────────────────────


def test_a_subshell_pushd_does_not_leak_to_the_parent_stack() -> None:
    assert _denied(_run("(cd /tmp/claude-1000 && pushd .); popd; git commit -m x"))


def test_unbalanced_substitutions_fail_closed() -> None:
    for cmd in ("git -C $(pwd commit -m x", "git reset `pwd", "echo $(git reset --hard"):
        assert _denied(_run(cmd, cwd=SCRATCH)), cmd


def test_the_fail_closed_fallback_sees_flags_before_the_verb() -> None:
    assert _denied(_run('git -C /opt/x reset --hard "unterminated'))
    assert _denied(_run("git --no-pager -C /opt/x checkout . 'unterminated"))
    assert not _denied(_run('echo "unterminated git'))


def test_a_seat_command_runs_with_dotenv_disabled() -> None:
    """site-provisioner 01M4F154S2 / 01M4F1KHHW: a seat that imported the live tree's app had
    `load_dotenv()` restore every provider credential. An allowed seat call is rewritten so every
    program it starts inherits PYTHON_DOTENV_DISABLED=1 — and it is NOT approved: the output
    carries no permissionDecision, so the normal permission flow still judges the call."""
    out = _run("python3 probe.py --x", agent_type="fabrik-reviewer")
    hso = json.loads(out)["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hso["updatedInput"]["command"] == _PREFIX + "\npython3 probe.py --x"


def test_the_rewrite_keeps_the_other_inputs_and_is_not_doubled() -> None:
    payload = {
        "session_id": "s1",
        "cwd": str(REPO),
        "scratchpad_dir": SCRATCH,
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "agent_id": "agent-1",
        "agent_type": "fabrik-reviewer",
        "tool_input": {"command": "ls", "description": "list", "timeout": 1234},
    }
    got = _rewritten(_run("", raw=json.dumps(payload)))
    assert got == {"command": _PREFIX + "\nls", "description": "list", "timeout": 1234}
    payload["tool_input"]["command"] = _PREFIX + "\nls"
    assert _rewritten(_run("", raw=json.dumps(payload))) is None
    # a near-miss value is not the prefix: "=10" is not truthy to python-dotenv
    payload["tool_input"]["command"] = "export PYTHON_DOTENV_DISABLED=10\nls"
    assert _rewritten(_run("", raw=json.dumps(payload)))["command"].startswith(_PREFIX + "\n")


def test_the_lead_other_agents_denials_and_empty_commands_are_not_rewritten() -> None:
    assert _run("python3 probe.py", agent_type=None) == ""  # the lead
    assert _run("python3 probe.py", agent_type="general-purpose") == ""
    denied = _run("pkill -f x", agent_type="fabrik-reviewer")
    assert _denied(denied) and _rewritten(denied) is None
    assert _run("   ", agent_type="fabrik-reviewer") == ""


def test_a_child_python_under_the_rewrite_loads_no_dotenv(tmp_path) -> None:
    """The outcome, executed: the rewritten command's child python runs `load_dotenv` on a .env
    holding a dummy credential and sees nothing."""
    (tmp_path / ".env").write_text("NAMECHEAP_API_KEY=dummy.invalid\n", encoding="utf-8")
    probe = (
        f'{sys.executable} -c \'import os, dotenv; dotenv.load_dotenv("{tmp_path}/.env"); '
        'print(os.environ.get("NAMECHEAP_API_KEY"))\''
    )
    cmd = _rewritten(_run(probe, agent_type="fabrik-reviewer"))["command"]
    env = {k: v for k, v in os.environ.items() if k != "NAMECHEAP_API_KEY"}
    env.pop("PYTHON_DOTENV_DISABLED", None)
    r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=60, env=env)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "None"


def test_a_scan_that_raises_still_rewrites(monkeypatch) -> None:
    """The deny half fails open by charter; the rewrite must not fail with it — a seat whose
    command the scanner cannot handle still runs with dotenv disabled."""
    spec = importlib.util.spec_from_file_location("seat_guard_raise", HOOK)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def boom(*a, **k):
        raise RuntimeError("scanner bug")

    monkeypatch.setattr(mod, "_scan", boom)
    payload = {
        "agent_id": "a",
        "agent_type": "fabrik-reviewer",
        "tool_name": "Bash",
        "tool_input": {"command": "python3 x.py"},
    }
    monkeypatch.setattr(mod.sys, "stdin", io.StringIO(json.dumps(payload)))
    buf = io.StringIO()
    monkeypatch.setattr(mod.sys, "stdout", buf)
    assert mod.main() == 0
    out = json.loads(buf.getvalue())["hookSpecificOutput"]
    assert out["updatedInput"]["command"] == _PREFIX + "\npython3 x.py"


def test_an_existing_export_with_a_trailing_semicolon_is_not_doubled() -> None:
    """D-801 review A-S1: `export PYTHON_DOTENV_DISABLED=1;` as the first statement already sets
    the switch; a second prefix ahead of it is noise the transcript and classifier read."""
    out = _run("export PYTHON_DOTENV_DISABLED=1; python3 x.py", agent_type="fabrik-reviewer")
    assert out == ""
    out = _run("  export PYTHON_DOTENV_DISABLED=1 ;\nls", agent_type="fabrik-reviewer")
    assert out == ""


def test_malformed_seat_payloads_produce_nothing() -> None:
    """D-801 review B-S3: shapes the harness should never send still exit 0 with no output."""
    base = {"tool_name": "Bash", "agent_id": "a", "agent_type": "fabrik-reviewer"}
    for ti in ("notadict", None, {"command": None}, {"command": ["ls"]}, {}):
        assert _run("", raw=json.dumps({**base, "tool_input": ti})) == "", ti
