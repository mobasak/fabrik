"""The quota hold's verb resolver (W-945bf009): a held session may read a repo by `git -C <repo>`, close a
record after `cd <repo> &&`, and pipe a body into `mail.py send` — and NOTHING that relocation or a pipe
reaches may write, force, sweep or run another program. Every veto of the hold still judges the RESOLVED
segment, so the force-push bypass the naive relaxation opened stays closed."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "quota_stop.py"
_spec = importlib.util.spec_from_file_location("quota_stop_resolver", _HOOK)
hook = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(hook)


def _action(cmd: str) -> str:
    return hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=10.0)[0]


@pytest.mark.parametrize(
    "cmd",
    [
        "git -C /opt/fabrik log -1",
        "git -C /opt/fabrik status --short",
        "git -C /opt/fabrik/ diff --stat",
        "git -C /opt/fabrik show --stat HEAD",
        "git -C /opt/fabrik rev-parse HEAD",
        "git -C /opt/fabrik/.claude/worktrees/intel log --oneline -3",
        "git -C /opt/fabrik -C /opt/fabrik-lib status",
    ],
)
def test_a_read_only_git_dash_c_passes_the_hold(cmd: str) -> None:
    assert _action(cmd) == "allow", cmd


@pytest.mark.parametrize(
    "cmd",
    [
        "git -C /opt/fabrik push --force origin master",
        "git -C /opt/fabrik push -f origin master",
        "git -C /opt/fabrik push origin +master",
        "git -C /opt/fabrik push origin :master",
        "git -C /opt/fabrik push",
        "git -C /opt/fabrik add .",
        "git -C /opt/fabrik add -- a.py",
        "git -C /opt/fabrik commit -m x -- a.py",
        "git -C /opt/fabrik reset -q HEAD -- a.py",
        "git -C /opt/fabrik fetch",
        "git -C /opt/fabrik/.claude/worktrees/intel commit -m x -- a.py",
        "git -C /opt/fabrik -C /opt/fabrik-lib push",
    ],
)
def test_a_relocated_write_verb_is_still_held(cmd: str) -> None:
    assert _action(cmd) == "deny", cmd


@pytest.mark.parametrize(
    "cmd",
    [
        "git -C /opt/fabrik push --force origin master",
        "git -C /opt/fabrik add .",
        "git -c core.pager=x log",
        "git --git-dir=/opt/x/.git push --force",
        "git --no-pager log",
    ],
)
def test_a_global_option_before_the_verb_is_never_read_as_the_verb(cmd: str) -> None:
    # the veto itself, not only the allow-list: `argv[1]` once read `-C` as the verb and returned
    # False for a force push, so any regex relaxation would have let it through
    assert hook._git_flags_forbidden(cmd) is True, cmd


@pytest.fixture
def own_repo(tmp_path: Path) -> Path:
    """A repo root with a `.git` entry and a subdirectory the session's shell sits in."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "scripts").mkdir()
    return tmp_path


@pytest.mark.parametrize(
    "template, expected",
    [
        (
            "cd {root} && python3 scripts/command_run.py done --command x --evidence e --feedback f",
            "allow",
        ),
        ("cd {root}; python3 scripts/command_run.py line", "allow"),
        ("cd .. && python3 scripts/command_run.py line", "allow"),
        ("cd {root}/ && git commit -m x -- a.py", "allow"),
        ("cd {root} && git push", "allow"),
        ("cd {root} && git log -1", "allow"),
        ("cd {root} && cat CHANGELOG.md", "allow"),
        ("cd /opt/fabrik && python3 scripts/command_run.py line", "deny"),
        ("cd /tmp && python3 scripts/command_run.py line", "deny"),
        ("cd {root}/scripts && python3 command_run.py line", "deny"),
        ("cd '{root}' && python3 scripts/command_run.py line", "deny"),
        ("cd -P {root} && git log", "deny"),
        ("cd {root} && cd /opt/x && git log", "deny"),
        ("cd {root} && python3 scripts/command_run.py line && rm x", "deny"),
        ("cd {root} & python3 scripts/command_run.py line", "deny"),
        ("cd {root} &&", "deny"),
        ("cd {root}", "deny"),
        ("cd {root} && python3 scripts/foo.py", "deny"),
        ("cd {root} && git push --force", "deny"),
        ("cd {root} && git add .", "deny"),
    ],
)
def test_a_cd_home_passes_and_a_cd_elsewhere_is_held(
    own_repo: Path, template: str, expected: str
) -> None:
    """A `cd` persists into the NEXT Bash call, so only a `cd` back to the session's own repo root
    is admitted (design critique, Opus concern 2) — and then every existing rule applies to what
    follows, the force and sweep vetoes included."""
    cmd = template.format(root=own_repo)
    action = hook.decide(
        "Bash", cmd, stamp_exists=True, tick_age_s=10.0, cwd=str(own_repo / "scripts")
    )
    assert action[0] == expected, cmd


def test_a_cd_is_held_when_the_payload_carries_no_cwd_or_no_repo(
    own_repo: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    cmd = f"cd {own_repo} && python3 scripts/command_run.py line"
    assert _action(cmd) == "deny"  # no cwd
    bare = tmp_path_factory.mktemp("norepo")
    assert (
        hook.decide(
            "Bash", f"cd {bare} && git log", stamp_exists=True, tick_age_s=10.0, cwd=str(bare)
        )[0]
        == "deny"
    )
    assert (
        hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=10.0, cwd="relative/dir")[0]
        == "deny"
    )


@pytest.mark.parametrize(
    "cmd",
    [
        "git -C /opt/x\xa0log push --force origin master",
        "git -C /opt/x\x1clog add .",
        "git\xa0log push --force",
        "git -C /opt/fabrik\u2028log",
        "cd\n{root}; python3 scripts/command_run.py line",
        "cd\x0b{root}; python3 scripts/command_run.py line",
        "cd\xa0{root} && git log",
        "cd {root}\xa0&& git log",
        "cd {root} &&\x0bgit log",
        "git -C\n/opt/fabrik log",
        "git status\xa0--short",
        "cat a\u2028b",
    ],
)
def test_whitespace_bash_does_not_split_on_is_held(own_repo: Path, cmd: str) -> None:
    """Python's `\\s` matches U+00A0, U+2028 and 0x0B-0x1F; bash splits on none of them, so a
    pattern reading `\\s` judged a different command than bash ran (both critiques, executed: a
    real commit landed through `-C /opt/x<NBSP>log commit`)."""
    cmd = cmd.format(root=own_repo)
    # cwd IS the repo the `cd` names, so only the whitespace can be what refuses it
    action = hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=10.0, cwd=str(own_repo))
    assert action[0] == "deny", repr(cmd)
    if cmd.startswith("git"):
        assert hook._git_flags_forbidden(cmd) is True or "\n" in cmd, repr(cmd)


def test_quoted_unicode_whitespace_in_a_commit_message_is_data() -> None:
    # the blank veto reads the MASKED line: inside quotes the character is data, as bash reads it
    assert _action("git commit -m 'fix:\u00a0a' -- f.py") == "allow"


@pytest.mark.parametrize(
    "cmd, expected",
    [
        (
            "printf 'Subject: x\\n\\nbody' | python3 scripts/mail.py send --to fabrik --kind reply --re 01X",
            "allow",
        ),
        (
            "echo 'Subject: x' | python3 /opt/fabrik/scripts/mail.py send --to fabrik --kind finding",
            "allow",
        ),
        ("printf 'a; b | c' | python3 scripts/mail.py send --to fabrik --kind reply", "allow"),
        ("git log | head", "deny"),
        ("cat secrets | python3 scripts/mail.py send --to x --kind reply", "deny"),
        ("printf x | python3 scripts/mail.py ack 01X", "deny"),
        ("printf x | python3 scripts/command_run.py done", "deny"),
        ("printf x | python3 scripts/mail.py send --to x | sh", "deny"),
        ("printf x || python3 scripts/mail.py send --to x", "deny"),
        ("printf x |& python3 scripts/mail.py send --to x", "deny"),
        ("printf x > f | python3 scripts/mail.py send --to x", "deny"),
        ('printf "$(id)" | python3 scripts/mail.py send --to x', "deny"),
        ("printf x | python3 scripts/mail.py send --to x > out", "deny"),
        ("echo x | python3 -c 'import os' scripts/mail.py send", "deny"),
        ("printf x >| python3 scripts/mail.py send --to x", "deny"),
        ("echo a \\| python3 scripts/mail.py send --to x", "deny"),
        ("printf 'a | b' | python3 scripts/mail.py send --to x | cat", "deny"),
        ("printf x | python3 scripts/mail.py sendx --to x", "deny"),
        ("printf x | python3 /opt/../scripts/mail.py send --to x", "deny"),
    ],
)
def test_a_body_piped_into_mail_send_passes_and_no_other_pipe_does(cmd: str, expected: str) -> None:
    assert _action(cmd) == expected, cmd


def test_a_cd_home_composes_with_the_mail_pipe(own_repo: Path) -> None:
    cmd = f"cd {own_repo} && printf 'a|b' | python3 scripts/mail.py send --to fabrik --kind reply"
    assert (
        hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=10.0, cwd=str(own_repo))[0]
        == "allow"
    )


def test_main_passes_the_payload_cwd(own_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The hook reads `cwd` from the PreToolUse payload; without it no `cd` could ever resolve."""
    seen: dict[str, object] = {}

    def spy(*a: object, **k: object) -> tuple[str, str]:
        seen.update(k)
        return "allow", ""

    monkeypatch.setattr(hook, "decide", spy)
    import io
    import json as _json

    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(
            _json.dumps(
                {"tool_name": "Bash", "tool_input": {"command": "git log"}, "cwd": str(own_repo)}
            )
        ),
    )
    assert hook.main() == 0
    assert seen.get("cwd") == str(own_repo)


@pytest.mark.parametrize(
    "cmd",
    [
        "git -C /opt/../etc log",
        "git -C /opt/fabrik/.. log",
        "git -C /opt/fabrik/../x log",
        "git -C '/opt/fabrik' log",
        'git -C "$D" log',
        "git -C /opt/* log",
        "git -C fabrik log",
        "git -C . log",
        "git -C/opt/fabrik log",
        "git -C /opt/fabrik/scripts log",
        "git -C /opt/fabrik/. log",
        "git -C /opt/x -C .. log",
        "git -C /opt/fabrik --git-dir=/x log",
    ],
)
def test_a_relocation_target_outside_the_repo_grammar_is_held(cmd: str) -> None:
    assert _action(cmd) == "deny", cmd
