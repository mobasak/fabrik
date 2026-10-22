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


# --- W-72dfd448: a seat writes only under its scratch dir (plan 2026-10-15-plan-2, D-1116) -------------------------
# Spec docs/superpowers/specs/2026-10-15-review-seat-write-isolation-design.md § The delta; the rows are the plan's
# Phase A Behavior Contract, A1-A11.

AGENT_DEF = REPO / "commands" / "_agents" / "fabrik-reviewer.md"


def _frontmatter_tools() -> list[str]:
    text = AGENT_DEF.read_text(encoding="utf-8")
    head = text.split("---", 2)[1]
    line = next(ln for ln in head.splitlines() if ln.startswith("tools:"))
    return [t.strip() for t in line.split(":", 1)[1].split(",") if t.strip()]


def test_a1_the_review_seat_holds_no_file_writing_tool() -> None:
    tools = _frontmatter_tools()
    assert tools, "the tools: line is empty"
    assert not set(tools) & {"Write", "Edit", "NotebookEdit", "MultiEdit"}, tools


def test_a2_the_lead_and_other_agents_may_write_anywhere() -> None:
    for agent in (None, "general-purpose"):
        for cmd in ("echo x > Makefile", "rm -rf src"):
            assert not _denied(_run(cmd, agent_type=agent)), (agent, cmd)


def test_a3_a_seat_redirect_to_a_live_path_is_denied_naming_it() -> None:
    for cmd in (
        "echo x > Makefile",
        "echo x >> docs/a.md",
        "ls | tee Makefile",
        "cmd &> out.log",
        "cmd >& out.log",
        "cmd &>2",
        "cmd <> Makefile",
        "> Makefile",
        "{ echo x; } > Makefile",
        "(true) > Makefile",
        "for i in a; do echo; done > Makefile",
        "exec 3> Makefile",
        f"cp {SCRATCH}/a 2 >/dev/null",
    ):
        out = _run(cmd)
        assert _denied(out), cmd
        assert "outside it" in json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"], (
            cmd
        )


def test_a4_dev_fd_and_scratch_destinations_are_allowed() -> None:
    for cmd in (
        "cmd > /dev/null 2>&1",
        "cmd 2>&1 | head",
        "cmd >&2",
        f"echo x > {SCRATCH}/a",
        f"cd {SCRATCH} && echo x > a",
        f"mkdir -p {SCRATCH}/d 2>/dev/null",
        f"truncate -s 0 {SCRATCH}/f",
        f"rm -f {SCRATCH}/*.tmp",
        "dd if=f of=/dev/null",
        "ls | tee /dev/stderr",
        "cmd > /dev/stdout",
        "curl -s -o /dev/null https://example.com",
        f"gzip -c f > {SCRATCH}/f.gz",
        'echo "2>x"',
    ):
        assert not _denied(_run(cmd)), cmd


def test_a5_reads_of_the_live_tree_into_scratch_are_allowed() -> None:
    for cmd in (
        f"cp /opt/fabrik/Makefile {SCRATCH}/",
        f"cp -r src {SCRATCH}/s",
        "cat Makefile",
        "perl -Mstrict -ne print Makefile",
    ):
        assert not _denied(_run(cmd)), cmd


def test_a6_a_seat_write_verb_aimed_at_the_live_tree_is_denied() -> None:
    for cmd in (
        f"cp {SCRATCH}/x Makefile",
        "mv a b",
        f"mv Makefile {SCRATCH}/",
        f"rsync --remove-source-files Makefile {SCRATCH}/",
        "rm -rf src",
        "unlink f",
        "gzip Makefile",
        "touch x",
        "mkdir d",
        "truncate -s 0 f",
        "sed -i s/a/b/ f",
        "sed -Ei s/a/b/ f",
        "sed --in-place=.bak s/a/b/ f",
        "perl -pi -e 1 f",
        "perl -i -pe 1 f",
        "dd if=/dev/zero of=f",
        "install -t bin x",
        f"cp -rt src {SCRATCH}/x",
        "install -d live",
        f"ln -s {SCRATCH}/x",
        "sort -o f in",
        "bash -c 'rm -rf src'",
        "cd src > log",
        "echo x > /dev/../opt/fabrik/Makefile",
    ):
        assert _denied(_run(cmd)), cmd


def test_a7_unknown_home_brace_glob_and_ancestor_destinations_are_denied() -> None:
    slug_dir = SCRATCH.rsplit("/", 2)[0]  # /tmp/claude-1000/-opt-x
    for cmd in (
        'rm -rf "$D"',
        "echo x > $(pwd)/x",
        "touch ~/x",
        f"cd {SCRATCH} && touch ~/x",
        "rm -rf /tmp/*",
        "rm -rf /tmp/claude-1000",
        f"rm -rf {slug_dir}",
        f"touch {SCRATCH}/{{x,/../../opt/f}}",
        f"rm {SCRATCH}/*/../../opt/f",
        "rm -rf /tmp/cl*",
        f"rm -rf {slug_dir[:-2]}*",
        'cp /tmp/s/a "2">/dev/null',
    ):
        assert _denied(_run(cmd)), cmd


def test_a8_an_untokenisable_write_is_denied_and_a_bare_echo_is_not() -> None:
    assert _denied(_run('echo "x > Makefile'))
    assert not _denied(_run('echo "unterminated'))
    assert not _denied(_run('echo "unterminated 2>/dev/null'))


def test_a9_a_crash_in_the_write_rule_fails_open_and_keeps_the_git_rule(monkeypatch) -> None:
    spec = importlib.util.spec_from_file_location("seat_guard_write_raise", HOOK)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def boom(*a, **k):
        raise RuntimeError("write rule bug")

    monkeypatch.setattr(mod, "_write_reason", boom)

    def run(command: str) -> dict | None:
        payload = {
            "agent_id": "a",
            "agent_type": "fabrik-reviewer",
            "session_id": SID,
            "cwd": "/opt/fabrik",
            "scratchpad_dir": SCRATCH,
            "tool_name": "Bash",
            "tool_input": {"command": command},
        }
        monkeypatch.setattr(mod.sys, "stdin", io.StringIO(json.dumps(payload)))
        buf = io.StringIO()
        monkeypatch.setattr(mod.sys, "stdout", buf)
        assert mod.main() == 0
        return json.loads(buf.getvalue())["hookSpecificOutput"] if buf.getvalue().strip() else None

    out = run("echo x > Makefile")
    assert out is not None and "permissionDecision" not in out and "updatedInput" in out
    out = run("touch x; git reset --hard")
    assert out is not None and out.get("permissionDecision") == "deny"
    assert _run("", raw="not json") == ""


def test_a10_env_dash_c_moves_the_cwd_for_its_own_command_only() -> None:
    assert _denied(_run(f"env -C {SCRATCH} true; rm -rf src"))
    assert _denied(_run(f"env -C {SCRATCH} true; git reset --hard"))
    assert not _denied(_run(f"env -C {SCRATCH} touch x"))


def test_a11_a_here_string_hides_nothing() -> None:
    assert _denied(_run("cat <<< hi\ngit reset --hard\nhi"))


def test_a12_a_repo_tmp_run_folder_is_scratch_but_not_a_siblings() -> None:
    # the false-refusal replay (D-1116 condition 2): seats are briefed into the D-836 run folder and fabrik-lib's
    # `<worktree>/.tmp/<run>/seat-…` folders
    for cmd in (
        f"mkdir -p /opt/fabrik/.tmp/runs/{SID}/fabrik-review-x/seat-sonnet",
        f"mkdir -p {REPO}/.tmp/sb116/seat-opus/tree",  # a worktree: its `.git` is a file
        "cd .tmp/w1/seat && echo x > out.txt",
    ):
        assert not _denied(_run(cmd)), cmd
    for cmd in (
        "rm -rf /opt/fabrik/.tmp/runs/other-sid/fabrik-review-x",
        "rm -rf /opt/fabrik/.tmp/runs",
        "rm -rf /opt/fabrik/.tmp",
        "rm -rf /opt/fabrik/.tmp/*",
        "rm -rf /opt/fabrik/.tmp/../src",
    ):
        assert _denied(_run(cmd)), cmd


def test_a13_a_variable_assigned_a_literal_on_the_line_is_resolved() -> None:
    for cmd in (
        f"S={SCRATCH}/run; mkdir -p $S/seat && cp Makefile $S/seat/",
        f"export S={SCRATCH}; P=${{S}}/pins; mkdir -p $P",
        f"S={SCRATCH}\ncd $S && touch x",
    ):
        assert not _denied(_run(cmd)), cmd
    for cmd in (
        "S=/opt/fabrik; rm -rf $S/src",
        f"S={SCRATCH}; S=$(pwd); rm -rf $S/x",
        f"(S={SCRATCH}); rm -rf $S/x",
        f"S={SCRATCH} true; rm -rf $S/x",
        'rm -rf "$D"',
    ):
        assert _denied(_run(cmd)), cmd


def test_a14_quoting_escapes_and_dry_runs_are_read_as_the_shell_reads_them() -> None:
    # the replay's extractor classes: an escaped backtick, a quote inside the other quote, <( ) in double quotes
    for cmd in (
        'grep -n "only a \\`<date>-plan\\`" f',
        'grep "intel\'s \\`x > y\\`" f',
        "echo '$(touch x)'",
        'echo "a <(b) >(c)"',
        "rsync -an src/ /opt/elsewhere/",
        "rsync --dry-run src/ /opt/elsewhere/",
        f"cd {SCRATCH} && S=$PWD && touch $S/x",
    ):
        assert not _denied(_run(cmd)), cmd
    for cmd in (
        'echo "$(touch x)"',
        "echo `touch x`",
        "rsync -a src/ /opt/elsewhere/",
        "S=$PWD; touch $S/x",
    ):
        assert _denied(_run(cmd)), cmd


def test_a15_a_for_loop_over_plain_words_is_resolved_and_a_path_word_is_not(tmp_path) -> None:
    real = str(tmp_path)  # an existing scratch dir: a `cd` into it is certain past the `&&` chain
    assert not _denied(
        _run(f"cd {real} && for m in prune lock; do rm -rf mm_$m; cp -r src mm_$m; done")
    )
    assert not _denied(_run(f"for m in a b; do mkdir -p {SCRATCH}/m$m; done"))
    # every value is judged, so a loop variable may sit mid-path (review round 1)
    assert not _denied(_run(f"cd {real} && for m in m1 m2; do mkdir -p $m/tests; done"))
    # a glob loop word with no `/` is a name in the cwd (review round 2)
    assert not _denied(_run(f"cd {real}; for f in *.json; do sort $f -o $f.sorted; done"))
    for cmd in (
        "for * in x; do :; done; rm -rf /opt/fabrik/src",  # an invalid name never disarms the rule
        f"cd {real}; for f in .*; do rm -rf $f/x; done",  # `.*` can match `..`
    ):
        assert _denied(_run(cmd)), cmd
    for cmd in (
        f"for m in a ../../../opt/x; do rm -rf {SCRATCH}/$m; done",
        f"for m in a ..; do rm -rf {SCRATCH}/x/$m/..; done",
        f"for m in $(ls); do rm -rf {SCRATCH}/$m; done",
        f"for m; do rm -rf {SCRATCH}/$m; done",
        "for m in a b; do rm -rf mm_$m; done",
    ):
        assert _denied(_run(cmd)), cmd


# --- review round 1 (W-72dfd448 Phase A /fabrik-review-scoped): the classes its three readers confirmed ---------


def test_a16_a_variable_never_loosens_the_kill_or_git_rule() -> None:
    # a resolved variable judges WRITE destinations only; the kill and git rules keep refusing `$P`/`$S`
    for cmd in (
        "P=4242; read P <<< -1; kill -9 $P",
        "P=4242; kill -9 $P",
        f"S={SCRATCH}; git -C $S reset --hard",
        f"S={SCRATCH}; unset S; git --git-dir=$S/opt/fabrik/.git --work-tree=$S/opt/fabrik reset --hard",
    ):
        assert _denied(_run(cmd)), cmd


def test_a17_the_variable_table_forgets_what_the_shell_may_have_changed() -> None:
    for cmd in (
        f"S={SCRATCH}; unset S; rm -rf $S/x",
        f"S={SCRATCH}; read S <<< /opt/fabrik; rm -rf $S/x",
        f"S={SCRATCH}; printf -v S %s /opt/fabrik; rm -rf $S/x",
        f"S={SCRATCH}; declare -g S=/opt/fabrik; rm -rf $S/x",
        f"S={SCRATCH}; eval S=/opt/fabrik; rm -rf $S/x",
        f"S=/opt/fabrik; S+={SCRATCH}; touch $S/f",  # really /opt/fabrik/tmp/…
        f"S=/opt/fabrik; for i in 1; do S={SCRATCH}; done; rm $S/f",  # a loop may run zero times
        f"S=/opt/fabrik; if false; then S={SCRATCH}; fi; rm $S/f",
        f"S={SCRATCH} | true; touch $S/f",
        f"S={SCRATCH} & touch $S/f",
        f"false && S={SCRATCH}; touch $S/f",
        f'S="{SCRATCH} /opt/fabrik/f"; touch $S',
        f"S={SCRATCH}/*; rm -rf $S",
        f"S={SCRATCH}; bash -c 'touch $S/f'",
        "for d in tmp opt; do rm -rf /$d/fabrik; done",
    ):
        assert _denied(_run(cmd)), cmd
    for cmd in (
        f"S={SCRATCH} && mkdir -p $S/a && touch $S/a/b",
        f"cd {SCRATCH} && S=$PWD && touch $S/x",
        f"S={SCRATCH}; v=$(true); touch $S/f",
    ):
        assert not _denied(_run(cmd)), cmd


def test_a18_a_quoted_or_escaped_character_is_data() -> None:
    for cmd in (
        "grep -n '>' Makefile",
        'grep -c ";" Makefile',
        "grep -n '$S' Makefile",
        "python3 -c 'import sys\n# a comment\nprint(1)' > /dev/null",  # `#` inside a multi-line quoted script
        "grep -c x Makefile # count, then compare > 3",  # a comment is not a redirect
    ):
        assert not _denied(_run(cmd)), cmd
    for cmd in (
        f"S={SCRATCH}; touch '$S'",
        f"S={SCRATCH}; touch \\$S",
        "echo `echo \\`git -C /opt/fabrik reset --hard\\``",
        "echo $'\\'' $(git -C /opt/fabrik reset --hard) \\'",
        "echo $'\\'' `git -C /opt/fabrik reset --hard` \\'",  # only the extractor sees this one
        'echo "<<EOF"\nrm -rf /opt/fabrik/src',
        "echo hi # <<EOF\nrm -rf /opt/fabrik/src",
        'bash -e -c "git status; git reset --hard"',
    ):
        assert _denied(_run(cmd)), cmd


def test_a19_cd_scope_repeated_options_tmp_roots_and_the_fallback(tmp_path) -> None:
    real = str(tmp_path)  # an existing directory under /tmp: the seat's scratch
    assert not _denied(_run(f"cd {real}; touch x"))
    assert not _denied(_run(f"mkdir -p {real}/new/x; cd {real}/new/x; touch y"))  # made on the line
    for cmd in (
        f"cd {real}/missing; touch x",  # the cd fails, so the touch lands in the repo
        f"cd {real} | cat; touch x",  # a pipeline's cd changes nothing
        "curl -o /etc/x http://u1 -o /tmp/a http://u2",
        "rsync -a --exclude -n src/ /opt/elsewhere/",
        "rsync -a -e'ssh -n' a /opt/elsewhere/",
        "rsync -a -- -n src/ /opt/elsewhere/",
        'curl -o /etc/x "http://u',
        'echo hi &> /etc/x "x',
        "rm -rf /home/u/.tmp/x",
        "touch /tmp/claude-1000/-opt-x/sid-other/proj/.tmp/x",
        "kill ²; pkill -f mail",
    ):
        assert _denied(_run(cmd)), cmd


def test_a20_round_2_wrapped_builtins_case_arms_hidden_heredocs_cd_chains_and_globs(
    tmp_path,
) -> None:
    real = str(tmp_path)
    os.symlink("/opt/fabrik", f"{real}/l")  # a link already inside scratch
    for cmd in (
        f"S={SCRATCH}; IFS= read -r S <<< /opt/fabrik; rm -rf $S/src",
        f"S={SCRATCH}; builtin read S <<< /opt/fabrik; rm -rf $S/src",
        f"S={SCRATCH}; command unset S; rm -rf $S/src",
        f"S={SCRATCH}; command printf -v S %s /opt/fabrik; rm -rf $S/src",
        f"S={SCRATCH}; printf -vS %s /opt/fabrik; rm -rf $S/src",
        f"S=/opt/fabrik; case z in a) S={SCRATCH};; esac; rm -rf $S/src",
        "echo $'\\'' x ' <<EOF'\nrm -rf /opt/fabrik/src\nEOF",
        "echo $((a<<b))\nrm -rf /opt/fabrik/src\nb",  # a shift, not a heredoc that hides the rm
        f"cd {real}/missing && echo ok; rm -rf src",  # the chain ended; the cd may have failed
        f"rm -rf {real}/gone; cd {real}/gone; rm -rf src",  # `rm` names a dir, it does not make one
        f"rm -rf {real}/*/",  # the glob matches the link into /opt/fabrik
    ):
        assert _denied(_run(cmd)), cmd
    for cmd in (
        f"mkdir {real}/n; cd {real}/n; touch f",
        f"S={real}; mkdir -p $S/a/b; cd $S/a/b; touch f",  # a variable mkdir operand (review round 3)
        f"cd {real}; (cd {real}/nope && true); touch f",  # a subshell's unsure cd dies with it
    ):
        assert not _denied(_run(cmd)), cmd


def test_a21_round_3_no_tree_walk_only_mkdir_makes_and_multiline_quotes(tmp_path) -> None:
    import time

    real = str(tmp_path)
    os.symlink("/opt/fabrik", f"{real}/l")
    t0 = time.monotonic()
    assert _denied(_run("rm -rf /opt/*/*/*/*/*/*/zz-none /opt/fabrik/src"))
    assert time.monotonic() - t0 < 4, "the hook has 5 s; a glob must never walk a tree"
    for cmd in (
        f"cd {real}; for d in *; do touch $d/zz-new; done",  # `*` reaches the link into /opt/fabrik
        f"echo venv {real}/v; cd {real}/v; rm -rf src",  # no command makes a dir by naming `venv`
        f"cp /nope/x {real}/r; cd {real}/r; touch x",  # a cp may fail or make a file
        f"git clone -q /nope {real}/c; cd {real}/c; touch x",
        f"mkdir {real}/no/a; cd {real}/no/a; rm -rf src",  # no -p and no parent: mkdir fails
        "echo 'a\n<<EOF b'\ngit -C /opt/fabrik reset --hard\nEOF",  # a quote open across lines
        'echo "a\n<<EOF b"\nrm -rf /opt/fabrik/src\nEOF',
    ):
        assert _denied(_run(cmd)), cmd


def test_a19b_a_repo_inside_another_sessions_tmp_tree_lends_it_no_scratch() -> None:
    import shutil
    import uuid

    other = f"/tmp/claude-{os.getuid()}/-opt-seat-guard-test/{uuid.uuid4()}"
    try:
        os.makedirs(f"{other}/proj/.git")  # a repo (a probe worktree) inside ANOTHER session's tree
        assert _denied(_run(f"touch {other}/proj/.tmp/x"))
    finally:
        shutil.rmtree(os.path.dirname(other), ignore_errors=True)
