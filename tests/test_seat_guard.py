"""Behaviour graders for the PreToolUse seat guard (.claude/hooks/seat_guard.py, W-6569a3fa).

Review seats (agent_type fabrik-reviewer) run Bash in the lead's shared tree. Three repos took
live damage from a seat's `git checkout/reset/commit` in a main checkout and a seat's
`pkill -f`; the guard refuses those two classes at the tool layer, for seats only.
"""

from __future__ import annotations

import json
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
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


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
