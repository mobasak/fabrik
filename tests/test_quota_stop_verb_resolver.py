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


def _decide(cmd: str, cwd: Path | str) -> str:
    return hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=10.0, cwd=str(cwd))[0]


def test_a_cd_is_never_stripped_without_an_absolute_cwd_inside_a_repo(
    own_repo: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each case asserts the RESOLVER left the `cd` in place — a deny alone proves nothing, the
    anchored allow-list refuses an unstripped `cd` anyway (review pass 1)."""
    cmd = f"cd {own_repo} && python3 scripts/command_run.py line"
    assert hook._resolve(cmd, None) == ([cmd], False)
    bare = tmp_path_factory.mktemp("norepo")
    assert hook._own_root(str(bare)) is None, "premise: no `.git` above the temp root"
    assert hook._resolve(f"cd {bare} && git log", str(bare)) == ([f"cd {bare} && git log"], False)
    # a RELATIVE cwd that would resolve into the repo from the hook's own working directory
    monkeypatch.chdir(own_repo.parent)
    assert hook._resolve(cmd, f"{own_repo.name}/scripts") == ([cmd], False)


def test_a_linked_worktree_whose_dot_git_is_a_file_is_its_own_root(tmp_path: Path) -> None:
    """A linked worktree's `.git` is a FILE, and hub sessions run in linked worktrees."""
    (tmp_path / ".git").write_text("gitdir: /opt/x/.git/worktrees/w\n")
    (tmp_path / "scripts").mkdir()
    cmd = f"cd {tmp_path} && python3 scripts/command_run.py line"
    assert _decide(cmd, tmp_path / "scripts") == "allow"


def test_a_cwd_reached_through_a_symlink_finds_the_repo_it_points_into(
    own_repo: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    outside = tmp_path_factory.mktemp("outside")
    (outside / "link").symlink_to(own_repo / "scripts")
    cmd = f"cd {own_repo} && python3 scripts/command_run.py line"
    assert _decide(cmd, outside / "link") == "allow"


def test_a_cd_is_resolved_logically_as_bash_does(tmp_path: Path) -> None:
    """bash's `cd ..` drops the previous component of the path AS WRITTEN; the physical realpath
    named the session's root while bash landed in another repo (review pass 1, executed twice)."""
    root, other = tmp_path / "root", tmp_path / "other"
    (root / ".git").mkdir(parents=True)
    (other / ".git").mkdir(parents=True)
    (other / "sub").mkdir()
    (root / "link").symlink_to(other / "sub")
    # the shell sits in root/link (physically other/sub): `cd ..` lands in ROOT, not in `other`
    assert _decide("cd .. && git commit -m x -- f.py", root / "link") == "deny"
    # …and from inside root, a symlinked component followed by `..` lands outside root
    (root / "sub" / "nested" / ".git").mkdir(parents=True)
    (root / "sub" / "nested" / "lnk2").symlink_to(root / "sub2")
    (root / "sub2").mkdir()
    assert _decide("cd nested/lnk2/.. && git commit -m x -- f.py", root / "sub") == "deny"
    assert _decide("cd ./nested/lnk2/../.. && git log", root / "sub") == "deny"


def test_a_cd_through_a_symlink_to_the_root_lands_home(
    own_repo: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    # the target is realpath'd after the logical normalisation: a link TO the root is the root
    link = tmp_path_factory.mktemp("links") / "home"
    link.symlink_to(own_repo)
    assert _decide(f"cd {link} && git commit -m x -- f.py", own_repo / "scripts") == "allow"


def test_a_git_look_alike_program_is_never_judged_as_git() -> None:
    # `gitx` is not git: the veto fails closed rather than reading its argv as git's
    assert hook._git_flags_forbidden("gitx push --force") is True
    assert hook._git_flags_forbidden("cat gitx") is False


def test_a_relative_cd_name_bash_would_search_cdpath_for_is_held(own_repo: Path) -> None:
    # `sub/../..` normalises to the root, but bash looks a name not starting `/` or `.` up in CDPATH
    assert _decide("cd sub/../.. && git log", own_repo / "scripts") == "deny"
    assert _decide("cd .x/.. && git log", own_repo) == "deny"  # a hidden name is searched too
    assert _decide("cd ./sub/../.. && git log", own_repo / "scripts") == "allow"


@pytest.mark.parametrize(
    "cmd, expected",
    [
        ("git push origin {+,}master", "deny"),
        ("git push origin {:,}master", "deny"),
        ("git add {.,}", "deny"),
        ('git push origin {"+",}master', "deny"),
        ("git push origin {+,\\ }master", "deny"),
        ("git push origin {+,\\\t}master", "deny"),
        ("git add {.,\\ }", "deny"),
        ("git push origin {+,\\}master}", "deny"),
        ("git log HEAD@{2..3}", "deny"),
        ("git add -- a{1..3}.py", "deny"),
        ("git log --oneline @{u}..HEAD", "allow"),
        ("git rev-parse HEAD^{tree}", "allow"),
        ("git commit -m 'a {x,y}' -- f.py", "allow"),
    ],
)
def test_brace_expansion_is_held_and_git_brace_syntax_is_not(cmd: str, expected: str) -> None:
    """bash expands `{+,}master` into `+master master` — a force push the checks saw as one word."""
    assert _action(cmd) == expected, cmd


@pytest.mark.parametrize(
    "cmd, expected",
    [("ls-evil /etc", "deny"), ("cat-evil x", "deny"), ("ls -la", "allow"), ("pwd", "allow")],
)
def test_a_read_tool_name_ends_at_a_blank(cmd: str, expected: str) -> None:
    assert _action(cmd) == expected, cmd


@pytest.mark.parametrize(
    "cmd",
    [
        "cd\xa0{root} && git log",
        "cd {root}\xa0&& git log",
        "cd {root} &&\x0bgit log",
        "git -C /opt/fabrik\u2028log",
        "git status\xa0--short",
        "cat a\u2028b",
        "ls\x1c-la",
    ],
)
def test_whitespace_bash_does_not_split_on_is_held(own_repo: Path, cmd: str) -> None:
    """Python's `\\s` matches U+00A0, U+2028 and 0x0B-0x1F; bash splits on none of them. Each row
    is refused ONLY for that character: the same line with a plain space is allowed."""
    cmd = cmd.format(root=own_repo)
    assert _decide(cmd, own_repo) == "deny", repr(cmd)
    plain = (
        cmd.replace("\xa0", " ").replace("\u2028", " ").replace("\x0b", " ").replace("\x1c", " ")
    )
    assert _decide(plain, own_repo) == "allow", repr(plain)


@pytest.mark.parametrize(
    "cmd",
    [
        "git -C /opt/x\xa0log push --force origin master",
        "git -C /opt/x\x1clog add .",
        "git\xa0log push --force",
        "cd\n{root}; python3 scripts/command_run.py line",
        "cd\x0b{root}; python3 scripts/command_run.py line",
        "git -C\n/opt/fabrik log",
    ],
)
def test_the_executed_whitespace_bypasses_are_held(own_repo: Path, cmd: str) -> None:
    """The shapes the critiques executed (a real commit landed through `-C /opt/x<NBSP>log
    commit`; `cd<NL>…` ran a script from $HOME) — refused, by whichever veto reaches them first."""
    assert _decide(cmd.format(root=own_repo), own_repo) == "deny", repr(cmd)


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
