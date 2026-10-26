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

import pytest

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
    tmp_path: Path,
    payload: object,
    stamp: bool,
    tick_fresh: bool,
    extra_env: dict[str, str] | None = None,
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
    env.update(extra_env or {})
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
        r"git status \"; rm -rf x\"",
        "python3 scripts/command_run.py done --command x --evidence \\'; curl evil\\'",
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    # an escaped backslash followed by a REAL quote still opens a span — `\\'a;b'` is data
    assert hook.decide("Bash", "echo \\\\'a;b'", stamp_exists=True, tick_age_s=1.0)[0] == "allow"
    # and a top-level escaped operator stays refused (bash would not run it, but we never
    # need one to stop cleanly — fail closed, as before)
    assert (
        hook.decide("Bash", r"git status \; rm -rf x", stamp_exists=True, tick_age_s=1.0)[0]
        == "deny"
    )


def test_a_lone_ampersand_is_a_command_separator_and_is_held():
    """`git status & evil` runs BOTH — a lone `&` backgrounds the first command and starts the
    second. The whole-line hardening listed `&&` and never the single form, so a held session
    could run anything behind an allowed command. Proven by execution: decide() said allow and
    `bash -c "git status & touch marker"` created the marker (review 2026-09-05, pass 13). The
    fd-duplication forms the checkpoint needs (`2>&1`, `>&2`) stay allowed."""
    for cmd in (
        "git status & evil",
        "git status 2>&1 & evil",
        "git status &",
        "git log >/dev/null&",
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    for cmd in ("git push 2>&1", "git status >&2", "git log >/dev/null 2>&1"):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "allow", cmd
    # the masker keeps a QUOTED ampersand as data
    assert (
        hook.decide("Bash", 'git commit -q -m "a & b" -- x.py', stamp_exists=True, tick_age_s=1.0)[
            0
        ]
        == "allow"
    )


def test_a_quoted_dev_null_target_is_a_known_fail_closed_limit():
    """The masker blanks a QUOTED redirect target, so `>'/dev/null'` cannot be recognised as the
    exempt device and is refused although it writes nothing. Accepted, not fixed: 0 of the hub's
    606 `> /dev/null` idioms quote the target (measured 2026-09-05, pass 13 finder), and the only
    honest fixes would re-open the quoted-argument class. Pinned so the limit is known, not found
    again."""
    for cmd in ("git log >'/dev/null'", 'git log >"/dev/null"'):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd


def test_a_tools_own_write_flag_and_a_destroying_read_tool_are_held():
    """Writes and executions with NO shell operator, every one proven on disk (review 2026-09-05,
    passes 14–17): `find . -name x -delete` destroyed a file; `git log --output=<p>` wrote one;
    `rg --pre <program>` and `git fetch --upload-pack=<program>` / `git push --receive-pack=<program>`
    RAN a program; `git branch -D` deleted a ref; a planted `x/command_run.py` ran because the
    allow regex matched the basename anywhere. `find`, `rg` and `git branch` are off the list;
    git's file-output and program-running flags are vetoed on git lines only; the three scripts
    must live under `scripts/`. The checkpoint forms that read stay allowed — including `grep -o`,
    which the earlier whole-line `-o` veto wrongly refused."""
    for cmd in (
        "find . -name victim.txt -delete",
        "find . -delete",
        "find . -type f",  # even the read form — the tool is off the list, not its flags
        "rg --pre ./pre.sh pattern f",
        "rg --files",
        "git branch -D wip",
        "git branch --show-current",
        "git log -n1 --output=/tmp/x",
        "git log --output /tmp/x",
        "git diff --output=/tmp/d",
        "git fetch --upload-pack=./up.sh .",
        "git fetch --upload-pack ./up.sh origin",
        "git push --receive-pack=./rp.sh ../bare.git HEAD",
        "python3 evil/command_run.py done --command x",
        "python3 command_run.py line",
        "python /tmp/mail.py send",
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    for cmd in (
        "git log -n1 --oneline",
        "git log --format=%h",
        "git rev-parse --abbrev-ref HEAD",
        "git fetch origin",
        "git push",
        "ls -la",
        "ls -R",
        "grep -rl x .",
        "grep -o x f",
        "python3 scripts/command_run.py line",
        "python3 /opt/fabrik/scripts/mail.py list",
        "python scripts/thread_anchor.py done --session s --match m",
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "allow", cmd


def test_a_quoted_or_abbreviated_git_flag_is_still_a_flag():
    """The flag veto read the MASKED line, so a flag inside quotes vanished from its view while
    git still received it: `git log "--output=m"` and `git fetch "--upload-pack=./p" .` wrote / ran
    under `allow` (pass 18, executed). And git accepts any unambiguous prefix of a long option:
    `--upl=./p` and `--receive=./p` ran the program too. The veto now reads ARGV on the raw line
    and holds a token that is a prefix of a vetoed option; an unparseable line is held. A flag
    spelled inside a commit MESSAGE is data — a token that does not start with `--`."""
    for cmd in (
        'git log -1 "--output=m"',
        "git log -1 '--output' m",
        'git fetch "--upload-pack=./pre.sh" .',
        "git fetch --upl=./pre.sh .",
        "git fetch --upload ./pre.sh origin",
        "git push --receive=./pre.sh ../bare.git HEAD",
        "git push --exec=./pre.sh ../bare.git HEAD",
        "git log --out=m",
        'git log "unbalanced --output=m',
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    for cmd in (
        'git commit -m "note: see --output=x in the docs" -- f.py',
        "git commit -m 'flags: --upload-pack is vetoed' -- f.py",
        "git push --set-upstream origin master",
        "git fetch --tags",
        "git log -1 --oneline",
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "allow", cmd


def test_ansi_c_and_locale_quoting_are_held_and_a_flag_after_end_of_options_is_still_checked():
    """`$'--output=m'`, `$'\\x2d\\x2doutput=m'`, `$"--output=m"` and `$'--upl=./p'` all wrote or ran
    under `allow` (pass 19, executed — a pool finder's claim): bash decodes the span to a plain
    word while shlex keeps the `$` glued to the token, so the argv veto saw no `--`. The quote
    char survives masking, so `$` followed by a quote is a veto on the masked line; inside double
    quotes the inner quote is masked and a message containing `$'` stays data. A bare `--` ends
    options for GIT — `git log -- --output=m` is a pathspec (proven: no file) — but not for the
    checker: since pass 23 a flag-shaped token is refused wherever it sits, because a value-taking
    flag can eat the `--` (`git commit -m -- --amend` fired an amend). Fail-closed, named."""
    for cmd in (
        "git log -1 $'--output=m'",
        "git log -1 $'\\x2d\\x2doutput=m'",
        'git log -1 $"--output=m"',
        "git fetch $'--upl=./pre.sh' .",
        "git status $'x'",
        "git log -1 -- --output=m",  # a pathspec to git, a flag to the checker: refused, fail-closed
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    for cmd in (
        'git commit -m "cost $\'s fine" -- f.py',
        "git commit -m 'a $\"b' -- f.py",
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "allow", cmd


def test_the_scripts_anchor_is_absolute_or_bare_and_ext_diff_chmod_are_held():
    """`(?:\\S*/)?scripts/…` admitted `../scripts/command_run.py` — a look-alike reached by
    traversal ran under `allow` (pass 19, P18-A, executed). The prefix is now absolute or absent.
    `--ext-diff` re-ran a pre-set diff.external and `git add --chmod=+x` changed a staged mode
    under `allow`; both join the vetoed prefixes."""
    for cmd in (
        "python3 ../scripts/command_run.py line",
        "python3 x/scripts/mail.py list",
        "python3 ./scripts/thread_anchor.py list",
        "git log --ext-diff -p -1",
        "git show --ext-diff HEAD",
        "git add --chmod=+x f",
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    for cmd in (
        "python3 scripts/command_run.py line",
        "python3 /opt/fabrik/scripts/command_run.py line",
        "python /opt/some-project/scripts/mail.py list",
        "git add f",
        "git log -p -1",
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "allow", cmd


def test_git_verbs_take_only_their_checkpoint_flags():
    """Every DANGEROUS-flag list was wrong the next pass; the convergence sweep (P19-A, 93
    candidates, 23 confirmed on disk) then proved the bare verbs admit CLAUDE.md's own HARD STOPS:
    `push --force`/`-f`/`+ref`/`--delete`/`:ref`, `commit --amend`/`-a`, `add -A`,
    `reset … --hard` trailing a `HEAD\\b` match, `--textconv`, a planted `/x/scripts/command_run.py`,
    `date -s`. The flag set is now POSITIVE per verb — what a checkpoint or a read needs — and an
    unlisted flag holds, git's own abbreviations included (fail-closed, named)."""
    for cmd in (
        "git push --force",
        "git push -f origin master",
        "git push origin +master",
        "git push --delete origin wip",
        "git push -d origin wip",
        "git push origin :wip",
        "git push --mirror",
        "git commit --amend -m x",
        "git commit -a -m x",
        "git commit -am x",
        "git commit --all -m x",
        "git commit --no-verify -m x",
        "git add -A",
        "git add --all",
        "git add -u",
        "git add -p f",
        "git reset HEAD^",
        "git reset -q HEAD~1",
        "git reset -q HEAD --hard",
        "git reset HEAD",
        "git show --textconv HEAD:f",
        "git log --ext-diff -p -1",
        "git log --onel",  # git's abbreviation of --oneline: refused, fail-closed
        "python3 /x/scripts/command_run.py line",
        "python3 /tmp/evil/scripts/mail.py send",
        "date -s 2020-01-01",
        "date",
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    for cmd in (
        "git add f.py docs/x.md",
        "git add -v -- f.py",
        "git commit -m 'checkpoint: held' -- f.py",
        "git commit -q -F /opt/fabrik/msg.txt -- f.py",
        "git commit -m 'note: --force is refused' -- f.py",
        "git push",
        "git push origin master",
        "git push -u origin master",
        "git push origin HEAD:refs/heads/master",
        "git fetch",
        "git status --short --branch",
        "git status -sb",
        "git diff --cached --stat",
        "git diff --name-only HEAD~1 -- f.py",
        "git log -n1 --oneline",
        "git log -5 --format=%h",
        "git log -p -1",
        "git show --stat HEAD",
        "git show HEAD:f.py",
        "git rev-parse --abbrev-ref HEAD",
        "git rev-parse --show-toplevel",
        "git reset -q HEAD -- a.py",
        "git reset HEAD -- a.py",
        "python3 /opt/fabrik/scripts/command_run.py line",
        "python /opt/some-project/scripts/mail.py list",
        "python3 scripts/thread_anchor.py list",
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "allow", cmd


def test_a_sweeping_pathspec_or_a_forced_refspec_is_held_and_the_template_has_a_message():
    """The positive flag set never looked at the POSITIONAL argument: `git add .`, `git commit -m x
    -- .` and `git reset -q HEAD -- .` each swept a sibling's work on disk (pass 21, P20-A);
    `git fetch origin +x:x` force-moved a local branch and `git push origin -- +master` was a
    force push after `--` (pool 20). Also: `command_run.py.bak` and `/opt/../scripts/x.py` passed
    the anchor; `rev-parse -q` and `python3.12` were false denies; the deny message's own
    template lacked `-m` and fails headless."""
    for cmd in (
        "git add .",
        "git add -- .",
        "git commit -m x",  # no pathspec: the whole index, a sibling's staged hunks included
        "git commit -q -F msg.txt",
        "git commit -- f.py",  # no message: only git's headless refusal stood between this and a commit
        "git commit -m x f.py",  # paths without `--`: not the template shape
        "git commit -m x --",  # `--` with nothing after it
        "git commit -- -m",  # a message flag AFTER `--` is a path, not a message
        "git commit -m -- --amend",  # `-m` CONSUMES `--`; git sees the flag (P22-A: an amend fired)
        "git commit -qm -- --amend -- a.py",
        "git log -S -- --output=x",  # the same shape on a read verb
        "git push origin -- --force",
        "git add ../x",
        "git add '*.py'",
        "git add ':(top)f'",
        "git commit -m x -- .",
        "git commit -m x .",
        "git commit -mF . -- f.py",  # `-mF` = message "F"; the `.` is a pathspec, not the value (P26-A)
        "git commit -Fm . -- f.py",
        "git commit -mq . -- f.py",
        "git commit -m5 . -- f.py",  # digits FOLLOW too: message "5", the `.` is a pathspec (pass 28)
        "git commit -qm5 . -- f.py",
        "git commit -5m . -- f.py",  # a leading digit is not a flag letter: refused, fail-closed
        "git reset -q HEAD -- .",
        "git reset HEAD -- ..",
        "git add ./../",
        "git add ././",
        "git commit -m x -- docs/..",
        "git add ''",  # an empty pathspec normalises to `.`
        "git fetch origin +master:master",
        "git fetch origin master:master",
        "git push origin -- +master",
        "git push origin -- :wip",
        "git fetch --prune",
        "git fetch -p",
        "python3 /opt/repo/scripts/command_run.py.bak line",
        "python3 /opt/../scripts/mail.py list",
        "python3 /opt/.hidden/scripts/mail.py list",
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    for cmd in (
        "git add f.py docs/plans/2026-09-05-plan-x/",
        "git commit -m x -- f.py docs/x.md",
        "git reset -q HEAD -- f.py docs/",
        "git add docs/../docs/x.md",
        "git add docs/.",  # the directory form, normalised: named as by design
        "git commit -F msg.txt -- f.py",
        "git commit -m 'fix: globs *.py? and [x]' -- f.py",  # the MESSAGE is not a pathspec
        "git commit -m . -- f.py",
        "git commit -qm . -- f.py",  # a cluster ENDING at m: the next token IS the message
        "git commit -m ':tada: done' -- f.py",
        "git commit --message 'a: b' -- f.py",
        "git log --oneline --",  # a bare `--` is skipped by the checker
        "git commit -qm x -- f.py",
        "git log --oneline -- .",  # a READ verb takes any pathspec
        "git fetch origin",
        "git push origin HEAD",
        "git rev-parse -q --verify HEAD",
        "git rev-parse --abbrev-ref HEAD",
        "python3.12 scripts/command_run.py line",
        "python3 /opt/my.repo-2/scripts/mail.py list",
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "allow", cmd
    assert "git commit -m '<msg>' -- <paths>" in hook._reason(
        "Bash"
    )  # the shape that PASSES the masker: a single-quoted body


def test_an_unquoted_variable_word_splits_and_is_held_but_a_quoted_one_is_data():
    """`git push $PV` with `PV='origin --force'` exported before the hold made a forced update on a
    remote, and `git commit -m $MSG -- f` with a `--amend` inside amended a pushed commit (P23-A,
    executed): the checker's argv has one opaque token where bash, word-splitting the unquoted
    expansion, has two. An unquoted `$NAME` is a veto. A `$` INSIDE quoted text stays data — that
    word starts with text and can never be flag-shaped (the whole-word `"$F"` is the next test)."""
    for cmd in (
        "git push $PV",
        "git commit -m $MSG -- f.py",
        "git log ${OPTS}",
        "git status $X",
        "cat $F",
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    for cmd in (
        'git commit -m "fix: $X was wrong" -- f.py',
        'git commit -m "costs $5" -- f.py',
        "git commit -m 'literal $HOME' -- f.py",
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "allow", cmd


def test_a_quoted_expansion_that_is_a_whole_word_can_be_a_flag_and_is_held():
    """Pass 24 claimed a quoted expansion "cannot become a flag". False for the whole-word form:
    `git push origin "$F" HEAD:master` with `F='--force'` made a forced update on a remote (twice),
    `git add "$X"` with `X='-A'` staged a sibling's untracked file, `git commit -m x -- "$FILES"`
    with `FILES='.'` swept a sibling's staged work (pass 25, own probe + P24-A, executed) — the
    masker hid the `$`, shlex saw `$F`, git got the flag. So a `$` that OPENS a word is a veto —
    unquoted in any form (`$@`, `$*` escaped the old class) or first inside a double-quoted span —
    and the masker keeps exactly that `$` visible. `"fix $X"` stays data: it starts with text."""
    for cmd in (
        'git push origin "$F" HEAD:master',
        'git push "$PV"',
        'git add "$X"',
        'git commit -m x -- "$FILES"',
        'git commit -m x -- "${FILES}"',
        'git commit -m x -- "$@"',
        "git push $@",
        "git push origin $*",
        'git add "./$FILES"',  # `$` inside a positional token: normpath hid it, bash expanded it (P25-A)
        'git commit -m x -- "a/../$FILES"',
        'git reset -q HEAD -- ".//$FILES"',
        'git push origin "x$F"',
        'git commit -m x -- "f`id`.py"',
        'cat "$F"',  # whole-word expansion on a read tool: refused too, fail-closed
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    for cmd in (
        'git commit -m "fix: $X was wrong" -- f.py',
        'git commit -m "costs $5 a month" -- f.py',
        "git commit -m 'literal $HOME' -- f.py",
        'git commit -m "a$B" -- f.py',
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "allow", cmd
    assert "$" in hook._mask_quoted('git push "$F"')  # span-opening `$` stays visible
    assert "$" not in hook._mask_quoted('echo "fix $X"')  # `$` inside text is data
    assert "`" in hook._mask_quoted('echo "a `id` b"')  # a backtick inside double quotes still runs
    # an escaped newline inside double quotes is a continuation bash REMOVES: `"\\<nl>$F"` reached
    # git as `"$F"` while the masked pair hid the newline veto (pass 26, executed) — it stays visible
    assert "\n" in hook._mask_quoted('git push origin "\\\n$F"')
    assert (
        hook.decide(
            "Bash", 'git push origin "\\\n$F" HEAD:master', stamp_exists=True, tick_age_s=1.0
        )[0]
        == "deny"
    )


def test_a_lone_ampersand_after_a_digit_is_still_a_separator():
    """`(?<![0-9>])&` excused an `&` after a digit, for which bash has no legitimate form — the
    fd-duplication `2>&1` puts its `&` after `>`. `git status 1& touch m` and `git log 2>&1& touch m`
    both backgrounded the first command and ran the second under `allow` (pass 17, executed —
    raised by a pool finder, proven on disk). The duplication forms stay allowed."""
    for cmd in ("git status 1& touch m", "git log 2>&1& touch m", "git log 2>&1 & touch m"):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    for cmd in ("git log 2>&1", "git status >&2", "git log 2>/dev/null"):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "allow", cmd


def test_process_substitution_runs_a_command_and_is_held():
    """`<(cmd)` / `>(cmd)` make bash RUN the inner command with no listed operator and nothing to
    mask: `git status <(touch marker)` was allowed and the marker appeared (review 2026-09-05,
    pass 14, executed)."""
    for cmd in ("git status <(touch m)", "cat >(touch m)", "git diff <(cat a) <(cat b)"):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    # a quoted `<(` is data
    assert (
        hook.decide("Bash", 'git log --grep="<(x)"', stamp_exists=True, tick_age_s=1.0)[0]
        == "allow"
    )


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
    # pass 25: a `$` that OPENS the span stays visible (`"$VAR"` is a whole word — it can be a
    # flag); a `$` inside text is data; the `;` is masked either way
    assert "$" in hook._mask_quoted('echo "$VAR;x"') and ";" not in hook._mask_quoted(
        'echo "$VAR;x"'
    )
    assert "$" not in hook._mask_quoted('echo "v=$VAR;x"')
    assert "$(" in hook._mask_quoted('echo "$(whoami)"')
    assert (
        hook._mask_quoted('echo "a\\nb;c"') == 'echo "xxxxxx"'
    )  # a non-special escape masks both (6 chars)


def test_destructive_git_and_every_sed_are_held():
    """`sed -n` was allowed "never with `-i`" — a lookahead on the RAW line that wanted whitespace
    before `-i`. Pass 16 proved six forms past it on disk: `'-i'`, `-Ei`, `--in-place`, GNU's
    prefixes `--i`/`--in` (each truncated the file to 0 bytes — `-n` suppresses the in-place
    output), and with NO flag at all the script's own `w file` (wrote) and `e cmd` (executed).
    The tool is off the list, like `find`: enumerating its write paths is one more list to be
    wrong about, and `cat -n` / `grep -n` cover a held read."""
    for cmd in (
        "git reset --hard HEAD~1",
        "git reset --merge",
        "sed -n -i 's/a/b/' f",
        "sed -i 's/a/b/' f",
        "sed -n '-i' 's/a/b/' f",
        "sed -n -Ei 's/a/b/' f",
        "sed -n --in 's/a/b/' f",
        "sed -n --in-place 's/a/b/' f",
        "sed -n 'w out.txt' f",
        "sed -n '1e touch marker' f",
        "sed -n '1,3p' f",
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "deny", cmd
    for cmd in ("git reset -q HEAD -- a.py", "git reset HEAD -- a.py", "cat -n f", "grep -n x f"):
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


def test_a_garbage_or_nan_stale_bound_is_the_default_never_a_crash_or_a_freeze(monkeypatch):
    """P3-5/P3-6 (closing review): `float(env)` unguarded died with a traceback on every tool call
    in every synced repo for a typo'd value; a NaN bound made `age > stale` False forever — a dead
    cron froze the fleet, the opposite of the documented direction."""
    for bad in ("garbage", "900s", "nan", "inf", ""):
        monkeypatch.setenv("QUOTA_STOP_TICK_STALE_S", bad)
        assert hook.decide("Edit", None, stamp_exists=True, tick_age_s=3600.0)[0] == "allow_warn", (
            bad
        )
        assert hook.decide("Edit", None, stamp_exists=True, tick_age_s=10.0)[0] == "deny", bad


# ── relief wake (plan 2026-09-07-plan-1-relief-wake, Phase C) ────────────────────────────────


def test_taskstop_is_allowed_under_the_hold():
    """A held session must be able to STOP its own native subagent — the exact quota waste the
    hold exists to prevent; measured denied 2026-09-07 01:24 (a 220k-token pass ran on)."""
    assert hook.decide("TaskStop", None, stamp_exists=True, tick_age_s=10.0) == ("allow", "")


def test_monitor_stays_allowed_under_the_hold():
    """The relief wake reaches only an ARMED self-watch, and arming is a Monitor call — the hold
    text orders it, so Monitor must never be denied while the stamp stands (a regression pin:
    `_READ_TOOLS` is fleet-synced and edited by more than one beat)."""
    assert hook.decide("Monitor", None, stamp_exists=True, tick_age_s=10.0) == ("allow", "")


def test_the_self_watch_arm_is_allowed_under_the_hold_in_its_exact_form_only():
    """D-355: the arm is a background Bash task, and the lift wakes only an armed session — so the
    exact arm command passes the hold, and nothing that merely starts with it does."""
    arm = "bash /opt/fabrik/scripts/sysadmin/selfwatch_arm.sh 1970a0ff-baa3-401b-ba52-fb0c5de43261"
    assert hook.decide("Bash", arm, stamp_exists=True, tick_age_s=10.0) == ("allow", "")
    for bad in (
        arm + " && touch x",
        arm + "; rm -rf y",
        "bash /opt/fabrik/scripts/sysadmin/selfwatch_arm.sh",
        "bash /tmp/scripts/sysadmin/selfwatch_arm.sh abc",
        "bash /opt/fabrik/scripts/sysadmin/selfwatch_arm.sh abc > /tmp/x",
        "bash /opt/fabrik/scripts/sysadmin/selfwatch_arm.sh $(evil)",
    ):
        assert hook.decide("Bash", bad, stamp_exists=True, tick_age_s=10.0)[0] == "deny", bad


def test_the_hold_text_orders_the_self_watch_arm():
    """The denial text is the one message every held session is guaranteed to read; it names the
    arm (the background Bash task running the arm wrapper) and says the lift wakes only an armed watch."""
    reason = hook._reason("Bash")
    assert "ARM the self-watch" in reason and "selfwatch_arm.sh" in reason
    assert "run_in_background: true" in reason and "Monitor(" not in reason and "armed" in reason
    assert "<your sid>" in reason, "no session id known → the placeholder, never an empty arg"
    # the payload's session id becomes the LITERAL arm argument (CLAUDE.md's arm rule; an empty
    # arg exits the watch as you arm it)
    with_sid = hook.decide("Edit", None, stamp_exists=True, tick_age_s=10.0, sid="abc-123")[1]
    assert "selfwatch_arm.sh abc-123" in with_sid and "<your sid>" not in with_sid
    assert len(with_sid) < 1000, len(with_sid)


def test_reason_names_the_wall_block_and_the_resume_verb():
    """W-28f260c3 (sp3 01M49B2E91): the wall text told a held session to close its run record and
    named no way back, so the successor record lost its rounds, design and commit window. The
    clause now names the wall close (`blocked --wall`, which keeps a seed) and the reopen
    (`start --resume-from`) — inside the one-message length pin above, with every other pinned
    phrase intact."""
    reason = hook._reason("Bash")
    assert "blocked --wall" in reason, reason
    assert "start --resume-from" in reason, reason
    assert "command_run.py done" in reason, "the done close is still named"
    # the pins the clause must not displace
    assert "git commit -m '<msg>' -- <paths>" in reason
    assert "ARM the self-watch" in reason and "selfwatch_arm.sh" in reason
    # the one-message pin measured where it is TIGHTEST — the arm order interpolates the sid, and
    # `_reason`'s own validator admits 80 chars: a 7-char `abc-123` read 966 while an 80-char sid
    # read 1039 (review code-S2); a real 36-char UUID sits between. Every admitted sid must fit.
    uuid_sid = "1970a0ff-baa3-401b-ba52-fb0c5de43261"
    for sid in (uuid_sid, "a" * 80):
        with_sid = hook.decide("Edit", None, stamp_exists=True, tick_age_s=10.0, sid=sid)[1]
        assert f"selfwatch_arm.sh {sid}" in with_sid
        assert len(with_sid) < 1000, (len(sid), len(with_sid))


def test_the_hold_text_refuses_a_malformed_sid():
    """The sid is interpolated into the arm order the agent will copy verbatim — a payload sid
    carrying a quote, a space or a newline must fall back to the placeholder, never break the
    Monitor call (heavy review of the relief-wake plan, 2026-09-07)."""
    for bad in ('abc"def', "abc def", "abc\ndef", "a" * 81, "abcé", "٣٣٣"):
        text = hook._reason("Edit", bad)
        assert "<your sid>" in text and "selfwatch_arm.sh <your sid>" in text, bad
        assert bad not in text
    good = hook._reason("Edit", "1970a0ff-baa3-401b-ba52-fb0c5de43261")
    assert "selfwatch_arm.sh 1970a0ff-baa3-401b-ba52-fb0c5de43261" in good


def test_a_trailered_commit_passes_the_hold_and_a_multiline_command_does_not():
    """The hold's own message orders `git commit -m <msg> -- <paths>`, and CLAUDE.md's provenance
    trailers put a paragraph break INSIDE that message — a newline inside the double-quoted -m
    body. The masker refused every such commit (three identical refusals under the 2026-09-06
    hold; infra 01M1W6KVH7Y0HQMQ9W3QTXDM7V), so a held session could only commit WITHOUT trailers,
    a HARD STOP. Inside a git-commit line's quoted span (either quote) a newline is data; anywhere
    else it is still the multi-line veto."""
    body = "fix(x): subject\n\nAgent-Role: primary\nAgent-Context: x\nCo-Authored-By: y <n@e>"
    allowed = hook.decide(
        "Bash", f'git commit -m "{body}" -- f.py', stamp_exists=True, tick_age_s=10.0
    )
    assert allowed[0] == "allow", allowed
    single = hook.decide(
        "Bash", f"git commit -m '{body}' -- f.py", stamp_exists=True, tick_age_s=10.0
    )
    assert single[0] == "allow", (
        single
    )  # a single-quoted body is data to the shell exactly the same
    for refused in (
        "git status\ntouch m",
        'git commit -m "x" -- f.py\nrm -rf y',
        "git commit -m 'a\nb' -- f.py\ntouch m",
        'git commit -m "x $(rm -rf y)" -- f.py',
        'git commit -m "\\\n$F" -- f.py',  # an ESCAPED newline is a line continuation bash removes (pass 26)
        'git commit -m "x" -- "\\\n$F"',
        'git push origin "a\nb"',  # the exception is the commit verb's, not git's
        'git add -- "a\nb"',
        "git commit-tree HEAD^{tree} -m a",  # `commit\b` admitted the object-writing cousins (F5)
        "git commit-graph write",
        'echo "a\nb"',
    ):
        assert hook.decide("Bash", refused, stamp_exists=True, tick_age_s=10.0)[0] == "deny", (
            refused
        )


# ── The stamp TIER (D-306): the warning stopped meaning the wall ──────────────────────────────


def _run_tier(tmp_path: Path, payload: object, tier: str | None) -> subprocess.CompletedProcess:
    """Like `_run` with a fresh tick and a stamp, but writing the stamp in the real two-line
    format. `tier=None` writes the PRE-TIER single line every stamp on disk carries today."""
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    (state / "fleet-exhausted").write_text("0" if tier is None else f"0\n{tier}\n")
    log = tmp_path / "rotate-tick.log"
    log.write_text("tick: ok\n")
    env = {**os.environ, "ROTATE_STATE_DIR": str(state), "QUOTA_STOP_TICK_LOG": str(log)}
    return subprocess.run(
        [sys.executable, str(_HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
    )


def test_the_urgent_ninety_tier_is_the_lane_not_a_free_pass(lane):
    """The 90-with-no-successor arm fires nine points before the wall (D-111). D-306 let EVERY
    session spend that runway, so the last points went to whoever asked first (D-1113). The lane
    keeps the runway for the sessions that merge and keep the records — the exempt one is
    ALLOWED (a seat mid-flight is not killed) and told to checkpoint; everyone else is held."""
    r = lane.run({"tool_name": "Edit", "tool_input": {"file_path": "x.py"}, "session_id": "nob"})
    assert r.returncode == 0 and _denied(r), r.stdout
    lane.bind("sc", "coordinator")
    for tool in ("Edit", "Agent"):
        a = lane.run({"tool_name": tool, "tool_input": {"prompt": "p"}, "session_id": "sc"})
        assert "permissionDecision" not in a.stdout, a.stdout
        assert "checkpoint" in a.stderr.lower(), f"it must still say what to do: {a.stderr!r}"
        assert "command_run.py" in a.stderr, "the nudge names the checkpoint verbs"


def test_the_walled_tier_still_holds_every_world_changing_tool(tmp_path):
    """The wall itself is unchanged: default-deny, one path through."""
    r = _run_tier(tmp_path, {"tool_name": "Edit", "tool_input": {"file_path": "x.py"}}, "walled")
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_a_pre_tier_stamp_still_holds(tmp_path):
    """Every stamp already on disk is one numeric line. It must keep holding — the migration
    fails CLOSED, because the lenient reading drops the fleet's only hard stop at a real wall."""
    r = _run_tier(tmp_path, {"tool_name": "Edit", "tool_input": {"file_path": "x.py"}}, None)
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    bad = _run_tier(
        tmp_path, {"tool_name": "Edit", "tool_input": {"file_path": "x.py"}}, "nonsense"
    )
    assert json.loads(bad.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_the_hooks_tier_reader_agrees_with_the_tick_that_writes_it(tmp_path):
    """The hook COPIES the reader rather than importing the tick (it is fleet-synced and must
    stand alone). A copy that drifts is a hold that disagrees with the band — so grade the two
    against the same bytes, including the shapes each is required to fail closed on."""
    spec = importlib.util.spec_from_file_location(
        "claude_rotate_tierparity",
        Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "claude_rotate.py",
    )
    cr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cr)
    s = tmp_path / "fleet-exhausted"
    for body in ("0", "0\nwalled\n", "0\nurgent-90\n", "", "x\nurgent-90", "0\nnonsense\n", "0\n"):
        s.write_text(body)
        assert hook._stamp_tier(s) == cr._stamp_tier(s), f"readers disagree on {body!r}"
    missing = tmp_path / "absent"
    assert hook._stamp_tier(missing) == cr._stamp_tier(missing) == "walled"


def test_the_hook_reader_does_not_hang_or_shift_on_a_hostile_stamp(tmp_path):
    """Two regressions the tier reader introduced over the old bare `.exists()`: a FIFO at the
    stamp path blocked `read_text` forever — a hang is not an OSError, so no handler fired and a
    PreToolUse hook that never returns stalls every tool call in the session (measured: exit 124
    under `timeout 5`, where the pre-D-306 hook exited 0) — and `splitlines()` breaks on
    VT/FF/FS/GS/RS/NEL/U+2028, none of which any writer treats as a line end, so a control byte
    in the promise shifted line 2 and a `walled` stamp was ALLOWED through as `urgent-90`."""
    import os as _os

    s = tmp_path / "fleet-exhausted"
    for sep in ("\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", " ", " "):
        s.write_text(f"0{sep}urgent-90\nwalled\n")
        assert hook._stamp_tier(s) == "walled", f"{sep!r} in line 1 must not shift the tier"
    import subprocess as _sp
    import sys as _sys

    fifo_dir = tmp_path / "fifo"
    fifo_dir.mkdir()
    _os.mkfifo(fifo_dir / "fleet-exhausted")
    assert (fifo_dir / "fleet-exhausted").is_fifo(), "the fixture must really be a FIFO"
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import importlib.util, sys\n"
        "spec = importlib.util.spec_from_file_location('p', sys.argv[1])\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "print(m._stamp_tier(__import__('pathlib').Path(sys.argv[2])))\n"
    )
    try:
        r = _sp.run(
            [_sys.executable, str(probe), str(_HOOK), str(fifo_dir / "fleet-exhausted")],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except _sp.TimeoutExpired:
        raise AssertionError(
            "the FIFO guard is gone — the reader BLOCKED, it did not fail"
        ) from None
    assert r.stdout.strip() == "walled", r.stdout + r.stderr
    # positive control: without it, `== "walled"` is satisfied by ANY non-regular path — a
    # one-character typo in the fixture name passed this grader with the guard removed
    reg = fifo_dir / "regular"
    reg.write_text("0\nurgent-90\n")
    r2 = _sp.run(
        [_sys.executable, str(probe), str(_HOOK), str(reg)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert r2.stdout.strip() == "urgent-90", f"the probe reads nothing at all: {r2.stdout!r}"
    d = tmp_path / "asdir"
    (d / "fleet-exhausted").mkdir(parents=True)
    assert hook._stamp_tier(d / "fleet-exhausted") == "walled"


def test_the_nudge_does_not_claim_nothing_is_held(tmp_path):
    """The sibling hook `quota_posture_hook.py` DENIES `Agent` at the very state this tier
    describes (band RED, no successor — which is `urgent-90`'s own precondition). Three review
    seats and the author's own probe caught the same sentence: telling an agent "nothing is held"
    there is false, and it is false in the direction that wastes a turn on a denied dispatch."""
    msg = hook._nudge()
    assert "Nothing is held yet" not in msg, msg
    assert "fleet-wide hold" in msg.lower(), "say WHICH hold has not armed"
    # ⚠️ Pin the SUBSTANCE, not the phrasing. A review seat named the cobra in the first cut: a
    # positive pin on specific words made the inaccurate clause MANDATORY, so correcting it redded
    # the grader. What must hold is that the message does not assert the system-wide state this
    # hook cannot see, and does point at the one line that can.
    # ⚠️ `--status` OUTRIGHT, not `or`. The whole point of the fix is that the QUOTA line is NOT
    # sufficient — it is absent in two documented states whose only remedy is `--status`. The `or`
    # form was satisfied by the "quota line" arm alone, so a paraphrase ("the sole source that
    # says") reinstated the exact false exclusive and the grader passed. Measured by the closing
    # seat. And the command must be RUNNABLE: `claude_rotate.py` is not on PATH.
    assert "--status" in msg, "name the authority, never the QUOTA line alone"
    assert "scripts/sysadmin/claude_rotate.py --status" in msg, (
        "an agent pastes this: a bare `claude_rotate.py` is not on PATH"
    )
    assert "only place" not in msg.lower() and "sole source" not in msg.lower(), (
        "never a false exclusive over --status"
    )
    assert "fleet-wide hold" in msg.lower(), "name WHICH hold has not armed"
    assert "checkpoint" in msg.lower(), "the actionable half must survive the correction"


def test_every_arm_order_the_hold_prints_is_one_the_hold_allows():
    """Review of D-356, B-S1/A-S2/C-S1: `_reason` embeds any sid it accepts (1–80 chars, `._-`), so the
    allow-list must admit exactly that set — an order the hook prints and then denies strands a held session
    unarmed, and the lift wakes only an armed one."""
    import re as _re

    for sid in ("1970a0ff-baa3-401b-ba52-fb0c5de43261", "a" * 80, "abc.def_ghi-1"):
        order = hook._reason("Edit", sid)
        cmd = _re.search(r'command: "(bash [^"]+)"', order).group(1)
        assert sid in cmd, order
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=10.0) == ("allow", ""), cmd
    too_long = "bash /opt/fabrik/scripts/sysadmin/selfwatch_arm.sh " + "a" * 81
    assert hook.decide("Bash", too_long, stamp_exists=True, tick_age_s=10.0)[0] == "deny"


def test_battery_stamp_message(tmp_path):
    """W-83a8ee68 (D-898): a `battery`-tier stamp holds exactly like the wall — the decision is
    the same deny — but the held session is told it is the BATTERY, and that mains power lifts it;
    a quota stamp keeps the quota wording."""
    state = tmp_path / "state"
    state.mkdir()
    log = tmp_path / "rotate-tick.log"
    log.write_text("tick: ok\n")
    env = {**os.environ, "ROTATE_STATE_DIR": str(state), "QUOTA_STOP_TICK_LOG": str(log)}
    payload = json.dumps(
        {"tool_name": "Edit", "tool_input": {"file_path": "x.py"}, "session_id": "s1"}
    )

    def reason_for(body: str) -> str:
        (state / "fleet-exhausted").write_text(body)
        r = subprocess.run(
            [sys.executable, str(_HOOK)],
            input=payload,
            capture_output=True,
            text=True,
            env=env,
            timeout=20,
        )
        out = json.loads(r.stdout)["hookSpecificOutput"]
        assert out["permissionDecision"] == "deny", out
        return out["permissionDecisionReason"]

    battery = reason_for("0\nbattery\n")
    assert battery.startswith("BATTERY HOLD"), battery
    assert "FLEET QUOTA EXHAUSTED" not in battery
    assert "mains power" in battery and "blocked --wall" in battery
    assert "selfwatch_arm.sh s1" in battery, "the arm order still names the literal sid"
    quota = reason_for("0\nwalled\n")
    assert quota.startswith("FLEET QUOTA EXHAUSTED"), quota


# ── THE LANE (W-18f559d9, D-1113): at `urgent-90` builders park, coordinators continue ─────────
#
# Every fixture below is hermetic: a tmp repo (real `git init`), a tmp identity store, a tmp
# rotation state dir and tick log, and the merge-owner resolver reached through the
# `QUOTA_STOP_DECISIONS_PY` seam — never the live hub ledger, store or stamp.

_DECISIONS_PY = Path(__file__).resolve().parents[1] / "scripts" / "decisions.py"
_WHOAMI_PY = Path(__file__).resolve().parents[1] / "scripts" / "whoami_agent.py"


def _git_q(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    ).stdout.strip()


class _Lane:
    """One repo (with a linked worktree), one identity store, one quota state at `urgent-90`."""

    def __init__(self, tmp: Path, monkeypatch) -> None:
        self.tmp = tmp
        self.main = tmp / "repo"
        self.main.mkdir()
        _git_q(self.main, "init", "-q", "-b", "master")
        _git_q(self.main, "commit", "-q", "--allow-empty", "-m", "base")
        self.wt = tmp / "repo-wt"
        _git_q(self.main, "worktree", "add", "-q", str(self.wt), "-b", "wt")
        self.common = Path(
            _git_q(self.main, "rev-parse", "--path-format=absolute", "--git-common-dir")
        )
        self.work = self.main / ".fabrik" / "work"
        self.work.mkdir(parents=True)
        self.config({"coordinator_mode": True})
        (self.main / "docs").mkdir()
        self.owner("coordinator")
        self.store = tmp / "agent-identity.jsonl"
        self.store.write_text("")
        self.state = tmp / "state"
        self.state.mkdir()
        self.tick = tmp / "rotate-tick.log"
        self.tick.write_text("tick: ok\n")
        self.stamp("0", "urgent-90")
        self.decisions = _DECISIONS_PY
        self.env = {
            "ROTATE_STATE_DIR": str(self.state),
            "QUOTA_STOP_TICK_LOG": str(self.tick),
            "AGENT_IDENTITY_FILE": str(self.store),
            "CLAUDE_PROJECT_DIR": str(self.main),
            "QUOTA_STOP_DECISIONS_PY": str(self.decisions),
        }
        for k, v in self.env.items():
            monkeypatch.setenv(k, v)
        monkeypatch.delenv("CLAUDE_AGENT", raising=False)
        monkeypatch.delenv("QUOTA_STOP_TICK_STALE_S", raising=False)
        self.mp = monkeypatch

    def config(self, cfg: object) -> None:
        (self.work / "config.json").write_text(cfg if isinstance(cfg, str) else json.dumps(cfg))

    def owner(self, name: str) -> None:
        (self.main / "docs" / "DECISIONS.md").write_text(
            "# Decisions\n\n| ID | When | Who | What | Why | Where |\n|---|---|---|---|---|---|\n"
            f"| D-001 | 2026-10-22 | operator | MERGE OWNER: {name} — merges | test | here |\n"
        )

    def bind(
        self,
        sid: str,
        name: str,
        toplevel: Path | str | None = None,
        **extra: object,
    ) -> None:
        row = {
            "session_id": sid,
            "name": name,
            "toplevel": str(self.common if toplevel is None else toplevel),
            "at": int(time.time()),
            **extra,
        }
        with self.store.open("a") as fh:
            fh.write(json.dumps(row) + "\n")

    def item(self, iid: str, **fields: object) -> None:
        doc = {"id": iid, "status": "open", "priority": 0, "owner": "infra", **fields}
        (self.work / f"{iid}.json").write_text(json.dumps(doc))

    def closed(self, iid: str) -> None:
        d = self.common / "fabrik-work" / "closed"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{iid}.json").write_text(json.dumps({"id": iid, "status": "done"}))

    def claim(self, iid: str, sid: str, lease_s: int = 7200) -> None:
        d = self.common / "fabrik-work" / "claims"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{iid}.json").write_text(
            json.dumps({"session": sid, "at": time.time(), "lease_s": lease_s})
        )

    def stamp(self, promise: str, tier: str) -> None:
        (self.state / "fleet-exhausted").write_text(f"{promise}\n{tier}\n")

    def run(self, payload: dict, **extra_env: str) -> subprocess.CompletedProcess:
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_AGENT"}
        env.update(self.env)
        env.update(extra_env)
        return subprocess.run(
            [sys.executable, str(_HOOK)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )


@pytest.fixture
def lane(tmp_path, monkeypatch):
    return _Lane(tmp_path, monkeypatch)


def _denied(r: subprocess.CompletedProcess) -> bool:
    return '"permissionDecision": "deny"' in r.stdout


def _at_lane(cmd: str) -> str:
    return hook.decide(
        "Bash", cmd, stamp_exists=True, tick_age_s=10.0, tier="urgent-90", exempt=False
    )[0]


def test_a_builder_is_parked_at_the_lane_with_the_finishing_verbs(lane):
    """Behaviour 1: a bound builder (not the merge owner, owning no open P0) is HELD at `urgent-90`
    — the wall's allow-list plus the finishing verbs — where D-306 used to allow everything."""
    lane.bind("sb", "infra")
    exempt, _why = hook.lane_exempt("sb", str(lane.main))
    assert exempt is False
    for tool, inp in (
        ("Edit", {"file_path": "x.py"}),
        ("Write", {"file_path": "x.py", "content": "x"}),
        ("Agent", {"prompt": "p"}),
        ("Bash", {"command": "python3 scripts/foo.py"}),
        ("Bash", {"command": "pytest tests/"}),
    ):
        r = lane.run({"tool_name": tool, "tool_input": inp, "session_id": "sb"})
        assert _denied(r), (tool, inp, r.stdout, r.stderr)
    for tool in ("SubagentHandback", "Read", "SendMessage"):
        r = lane.run({"tool_name": tool, "tool_input": {}, "session_id": "sb"})
        assert not _denied(r), (tool, r.stdout)
    for cmd in (
        "git commit -m 'park' -- a.py",
        "git push",
        "python3 scripts/command_run.py blocked --wall --command fabrik-task --reason 'quota wall'",
        "python3 scripts/merge_request.py request --review r.md --item W-0123abcd",
        "python3 /opt/fabrik/scripts/merge_request.py request --review r.md",
        "python3 scripts/work.py claim W-0123abcd",
        "python3 scripts/work.py release W-0123abcd",
        "python3 scripts/mail.py send --to fabrik --body x",
        "bash /opt/fabrik/scripts/sysadmin/selfwatch_arm.sh sb",
    ):
        assert _at_lane(cmd) == "allow", cmd
    for cmd in (
        "python3 scripts/work.py done W-0123abcd",
        "python3 scripts/work.py claim W-0123abcd && touch m",
        "python3 scripts/work.py claim",
        "python3 x/scripts/work.py claim W-0123abcd",
        "python3 scripts/merge_request.py merge",
        "python3 scripts/merge_request.py request > out",
    ):
        assert _at_lane(cmd) == "deny", cmd
    # the finishing verbs are the LANE's, never the wall's: at `walled` they stay held
    for tool, cmd in (("Bash", "python3 scripts/work.py claim W-0123abcd"),
                      ("SubagentHandback", None), ("SendMessage", None)):  # fmt: skip
        assert (
            hook.decide(tool, cmd, stamp_exists=True, tick_age_s=10.0, tier="walled")[0] == "deny"
        ), tool


def test_only_a_bound_coordinator_mode_merge_owner_continues(lane):
    """Behaviour 2: the merge owner of a coordinator_mode repo, bound by session id in THIS repo's
    scope, is exempt; the same name without coordinator_mode, a CLAUDE_AGENT with no binding, and a
    binding scoped to another repo are all held (rulings 1-2: CLAUDE_AGENT is never read)."""
    lane.bind("sc", "coordinator")
    assert hook.lane_exempt("sc", str(lane.main))[0] is True
    # from the linked worktree: one repo, one common dir
    assert hook.lane_exempt("sc", str(lane.wt))[0] is True
    r = lane.run({"tool_name": "Edit", "tool_input": {"file_path": "x.py"}, "session_id": "sc"})
    assert not _denied(r), r.stdout
    assert "lane" in r.stderr.lower() and "checkpoint" in r.stderr.lower(), r.stderr
    # CLAUDE_PROJECT_DIR wins over the payload cwd (a coordinator working in a scratch dir)
    r = lane.run(
        {"tool_name": "Edit", "tool_input": {}, "session_id": "sc", "cwd": str(lane.tmp / "state")}
    )
    assert not _denied(r), r.stdout
    # casefold on both sides of the comparison
    lane.owner("Coordinator")
    assert hook.lane_exempt("sc", str(lane.main))[0] is True
    lane.owner("coordinator")
    # no coordinator_mode → held
    lane.config({"coordinator_mode": False})
    assert hook.lane_exempt("sc", str(lane.main))[0] is False
    lane.config({"coordinator_mode": "true"})  # a string is not the flag
    assert hook.lane_exempt("sc", str(lane.main))[0] is False
    lane.config({"coordinator_mode": True})
    # CLAUDE_AGENT=coordinator with NO binding → held, in-process and end-to-end
    lane.mp.setenv("CLAUDE_AGENT", "coordinator")
    assert hook.lane_exempt("unbound", str(lane.main))[0] is False
    r = lane.run(
        {"tool_name": "Edit", "tool_input": {}, "session_id": "unbound"}, CLAUDE_AGENT="coordinator"
    )
    assert _denied(r), r.stdout
    lane.mp.delenv("CLAUDE_AGENT")
    # a binding for ANOTHER repo's toplevel → held
    lane.bind("sx", "coordinator", toplevel=lane.tmp / "other" / ".git")
    assert hook.lane_exempt("sx", str(lane.main))[0] is False
    # a later row rebinding the sid wins
    lane.bind("sc", "infra")
    assert hook.lane_exempt("sc", str(lane.main))[0] is False


def test_the_owner_of_an_open_p0_continues(lane):
    """Behaviour 3 (ruling 1): the bound OWNER of an open P0 item is exempt — no live claim needed;
    a P1 item, a done item and an item with a closed marker are not."""
    lane.bind("sp", "infra")
    lane.item("W-aaaaaaaa", priority=1)
    assert hook.lane_exempt("sp", str(lane.main))[0] is False
    lane.item("W-aaaaaaaa", priority=0, status="done")
    assert hook.lane_exempt("sp", str(lane.main))[0] is False
    lane.item("W-aaaaaaaa", priority=False)  # a bool is never the int 0
    assert hook.lane_exempt("sp", str(lane.main))[0] is False
    lane.item("W-aaaaaaaa", priority="0")
    assert hook.lane_exempt("sp", str(lane.main))[0] is False
    lane.item("W-aaaaaaaa", owner="fleet")
    assert hook.lane_exempt("sp", str(lane.main))[0] is False
    lane.item("W-aaaaaaaa", owner="INFRA")
    exempt, why = hook.lane_exempt("sp", str(lane.main))
    assert exempt is True and "W-aaaaaaaa" in why, why
    r = lane.run({"tool_name": "Edit", "tool_input": {}, "session_id": "sp"})
    assert not _denied(r), r.stdout
    lane.closed("W-aaaaaaaa")
    assert hook.lane_exempt("sp", str(lane.main))[0] is False
    r = lane.run({"tool_name": "Edit", "tool_input": {}, "session_id": "sp"})
    assert _denied(r), r.stdout


def test_the_park_message_names_the_item_and_lift_and_orders_only_allowed_commands(lane):
    """Behaviour 4: the park message names the session's claimed items (or none) and the lift —
    the stamp's promised resume, else the posture's five_hour reset — and every command it orders
    passes the lane's own allow-list (an order the hook then denies strands a parked session)."""
    import re as _re

    lane.bind("sm", "infra")

    def reason() -> str:
        r = lane.run({"tool_name": "Edit", "tool_input": {}, "session_id": "sm"}, TZ="UTC")
        return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]

    promise = int(time.time()) + 3 * 3600
    lane.stamp(str(promise), "urgent-90")
    msg = reason()
    assert time.strftime("%H:%M", time.gmtime(promise)) in msg, msg
    assert "or earlier when a successor appears" in msg, msg
    assert "your items: none" in msg, msg
    assert "fleet-exhausted" in msg, "command_run.py's _WALL_REASON keys on this phrase"
    assert "claude_rotate.py --status" not in msg, "--status is denied at the lane — never order it"
    lane.claim("W-bbbbbbbb", "sm")
    lane.claim("W-cccccccc", "someone-else")
    lane.claim("W-dddddddd", "sm", lease_s=-10)  # expired
    lane.stamp("0", "urgent-90")
    resets = time.time() + 2 * 3600
    (lane.state / "quota-posture.json").write_text(
        json.dumps({"active": {"windows": {"five_hour": {"resets_at": resets}}}})
    )
    msg = reason()
    assert "your items: W-bbbbbbbb" in msg and "W-cccccccc" not in msg, msg
    assert "W-dddddddd" not in msg, msg
    assert time.strftime("%H:%M", time.gmtime(resets)) in msg, msg
    (lane.state / "quota-posture.json").unlink()
    msg = reason()
    assert "when the 5-hour window resets" in msg, msg
    assert "selfwatch_arm.sh sm" in msg, "the arm order carries the literal sid"
    fill = {"<msg>": "m", "<paths>": "a.py", "<command>": "fabrik-task", "<why>": "quota wall",
            "<receipt>": "r.md", "<W-id>": "W-0123abcd"}  # fmt: skip
    orders = _re.findall(r"`([^`]+)`", msg) + _re.findall(r'command: "(bash [^"]+)"', msg)
    assert len(orders) >= 4, orders
    for order in orders:
        for k, v in fill.items():
            order = order.replace(k, v)
        assert "<" not in order, f"an unfilled placeholder in an order: {order!r}"
        assert _at_lane(order) == "allow", order
    assert "`python3 scripts/work.py next`" in msg, (
        "the rotation resume step is ordered (W-cff56c52)"
    )
    assert "whoami_agent.py" in msg and "`python3 /opt/fabrik/scripts/whoami_agent.py" not in msg, (
        "the re-bind passes only for the window's own name, so it is named in prose, never ordered"
    )


def test_every_lane_error_holds_and_never_raises(lane, tmp_path):
    """Behaviour 5: every unreadable input — store, config, item, ledger, resolver — makes the
    session NOT exempt (held, still able to commit, push and close), never raises, and returns
    within the hook's budget even when the resolver hangs."""
    lane.bind("se", "coordinator")
    assert hook.lane_exempt("se", str(lane.main))[0] is True  # the positive control
    (lane.state / "lane-owner-cache.json").unlink(missing_ok=True)
    for sid, proj in ((None, str(lane.main)), ("", str(lane.main)), ("se", None),
                      ("se", str(tmp_path / "nowhere")), ("se", "relative/dir")):  # fmt: skip
        assert hook.lane_exempt(sid, proj)[0] is False, (sid, proj)
    # the store: garbage, a directory, a FIFO (must not hang)
    good = lane.store.read_text()
    lane.store.write_text('not json\n{"session_id": 3}\n[1]\n')
    assert hook.lane_exempt("se", str(lane.main))[0] is False
    lane.store.unlink()
    lane.store.mkdir()
    assert hook.lane_exempt("se", str(lane.main))[0] is False
    lane.store.rmdir()
    os.mkfifo(lane.store)
    t0 = time.time()
    assert hook.lane_exempt("se", str(lane.main))[0] is False
    assert time.time() - t0 < 3
    lane.store.unlink()
    lane.store.write_text(good)
    # the config: corrupt, not a dict, missing
    for cfg in ("{", "[]", "null"):
        lane.config(cfg)
        assert hook.lane_exempt("se", str(lane.main))[0] is False, cfg
    (lane.work / "config.json").unlink()
    assert hook.lane_exempt("se", str(lane.main))[0] is False
    lane.config({"coordinator_mode": True})
    # the ledger missing; the resolver missing, failing, printing UNDECLARED, hanging
    (lane.main / "docs" / "DECISIONS.md").unlink()
    assert hook.lane_exempt("se", str(lane.main))[0] is False
    lane.owner("coordinator")
    for n, body in enumerate(
        (
            "import sys; sys.exit(1)",
            "print('UNDECLARED'); raise SystemExit(3)",
            "import time; time.sleep(30)",
        )
    ):
        stub = tmp_path / f"stub{n}.py"
        stub.write_text(body + "\n")
        lane.mp.setenv("QUOTA_STOP_DECISIONS_PY", str(stub))
        t0 = time.time()
        assert hook.lane_exempt("se", str(lane.main))[0] is False, body
        assert time.time() - t0 < 3.5, f"the resolver ran past its budget: {body}"
    lane.mp.setenv("QUOTA_STOP_DECISIONS_PY", str(tmp_path / "absent.py"))
    assert hook.lane_exempt("se", str(lane.main))[0] is False
    lane.mp.setenv("QUOTA_STOP_DECISIONS_PY", str(lane.decisions))
    # a corrupt item is skipped, never fatal; a corrupt cache is ignored
    lane.bind("se", "infra")
    (lane.work / "W-eeeeeeee.json").write_text("{")
    lane.item("W-ffffffff")
    assert hook.lane_exempt("se", str(lane.main))[0] is True
    lane.bind("se", "coordinator")
    (lane.state / "lane-owner-cache.json").write_text("{ torn")
    assert hook.lane_exempt("se", str(lane.main))[0] is True
    # a `.git` that is neither a directory nor a gitdir file → held
    odd = tmp_path / "odd"
    odd.mkdir()
    (odd / ".git").write_text("garbage\n")
    assert hook.lane_exempt("se", str(odd))[0] is False
    # end to end with the store gone: the hook still answers (held), exit 0
    lane.store.unlink()
    r = lane.run({"tool_name": "Edit", "tool_input": {}, "session_id": "se"})
    assert r.returncode == 0 and _denied(r), (r.stdout, r.stderr)


def test_the_merge_owner_is_cached_by_ledger_and_resolver_stamp(lane, tmp_path):
    """The resolver spawns once per (ledger, resolver) state: a second call reads the cache, a
    ledger edit re-resolves; a repo without coordinator_mode spawns nothing; the child never sees
    CLAUDE_AGENT and runs isolated (`-I`)."""
    calls = tmp_path / "calls"
    stub = tmp_path / "stub_decisions.py"
    stub.write_text(
        "import pathlib\n"
        f"with pathlib.Path({str(calls)!r}).open('a') as fh: fh.write('x')\n"
        "print('coordinator')\n"
    )
    lane.mp.setenv("QUOTA_STOP_DECISIONS_PY", str(stub))
    lane.bind("sk", "coordinator")
    assert hook.lane_exempt("sk", str(lane.main))[0] is True
    assert hook.lane_exempt("sk", str(lane.main))[0] is True
    assert calls.read_text() == "x", "the second call must read the cache"
    led = lane.main / "docs" / "DECISIONS.md"
    st = led.stat()
    os.utime(led, ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))
    assert hook.lane_exempt("sk", str(lane.main))[0] is True
    assert calls.read_text() == "xx", "a ledger change must re-resolve"
    lane.config({})
    calls.unlink()
    assert hook.lane_exempt("sk", str(lane.main))[0] is False
    assert not calls.exists(), "no coordinator_mode: the resolver must not spawn"
    probe = tmp_path / "probe_decisions.py"
    seen = tmp_path / "seen"
    probe.write_text(
        "import os, pathlib, sys\n"
        f"pathlib.Path({str(seen)!r}).write_text("
        "repr((os.environ.get('CLAUDE_AGENT'), sys.flags.isolated)))\n"
        "print('coordinator')\n"
    )
    lane.config({"coordinator_mode": True})
    lane.mp.setenv("QUOTA_STOP_DECISIONS_PY", str(probe))
    lane.mp.setenv("CLAUDE_AGENT", "coordinator")
    assert hook.lane_exempt("sk", str(lane.main))[0] is True
    assert seen.read_text() == "(None, 1)", seen.read_text()


def test_the_hooks_identity_reader_agrees_with_whoami(lane):
    """The hook reads the identity store itself (it is fleet-synced and imports nothing from
    scripts/). Graded against `whoami_agent.py::resolve_agent_name` on one store with CLAUDE_AGENT
    unset: several sids, a corrupt line, a malformed name, a later row winning."""
    spec = importlib.util.spec_from_file_location("whoami_parity", _WHOAMI_PY)
    who = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(who)
    lane.bind("s1", "infra")
    lane.bind("s2", "fleet")
    with lane.store.open("a") as fh:
        fh.write("{corrupt\n\n[]\n")
        fh.write(json.dumps({"session_id": "s1", "name": "Bad Name", "toplevel": str(lane.common)}))
        fh.write("\n")
    lane.bind("s1", "kaizen")  # the later row wins
    lane.bind("s3", "intel")
    for sid in ("s1", "s2", "s3", "s4"):
        lane.mp.setenv("CLAUDE_CODE_SESSION_ID", sid)
        assert hook._bound_name(sid, lane.common) == who.resolve_agent_name(), sid
    assert hook._bound_name("s1", lane.common) == "kaizen"


def test_an_out_of_range_lift_epoch_never_crashes_the_park(lane):
    """F1 (review round 1, executed): a stamp promise or a posture `five_hour.resets_at` outside the
    platform's time_t range made `time.localtime` raise, `main()` exited 1 with no JSON, and Claude
    Code ran the tool — a parked builder escaped. Every such epoch, a negative one and a past one
    still give the deny JSON at rc 0, with the fallback lift text."""
    lane.bind("so", "infra")
    for promise in ("1e20", "1e300", "1e18", "-5", str(int(time.time()) - 3600)):
        lane.stamp(promise, "urgent-90")
        r = lane.run({"tool_name": "Edit", "tool_input": {}, "session_id": "so"})
        assert r.returncode == 0 and _denied(r), (promise, r.returncode, r.stdout, r.stderr)
        msg = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        assert "when the 5-hour window resets" in msg, (promise, msg)
    lane.stamp("0", "urgent-90")
    for resets in (1e20, 1e300, -5, time.time() - 3600):
        (lane.state / "quota-posture.json").write_text(
            json.dumps({"active": {"windows": {"five_hour": {"resets_at": resets}}}})
        )
        r = lane.run({"tool_name": "Edit", "tool_input": {}, "session_id": "so"})
        assert r.returncode == 0 and _denied(r), (resets, r.returncode, r.stdout, r.stderr)
        msg = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        assert "when the 5-hour window resets" in msg, (resets, msg)
    # review round 2: an integer past float range (JSON reads it as an int, `float()` overflows) and a
    # posture nested past the recursion limit (`json.loads` raises RecursionError) — neither may raise
    for raw in (
        '{"active":{"windows":{"five_hour":{"resets_at":1' + "0" * 400 + "}}}}",
        "[" * 100_000 + "]" * 100_000,
    ):
        (lane.state / "quota-posture.json").write_text(raw)
        r = lane.run({"tool_name": "Edit", "tool_input": {}, "session_id": "so"})
        assert r.returncode == 0 and _denied(r), (raw[:40], r.returncode, r.stdout, r.stderr[-300:])
        msg = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        assert "when the 5-hour window resets" in msg, (raw[:40], msg)
    # a past stamp promise falls through to a live posture reset
    lane.stamp(str(int(time.time()) - 3600), "urgent-90")
    resets = time.time() + 2 * 3600
    (lane.state / "quota-posture.json").write_text(
        json.dumps({"active": {"windows": {"five_hour": {"resets_at": resets}}}})
    )
    r = lane.run({"tool_name": "Edit", "tool_input": {}, "session_id": "so"}, TZ="UTC")
    msg = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert time.strftime("%H:%M", time.gmtime(resets)) in msg, msg


def test_a_lift_on_another_day_names_the_date():
    """F1: a lift that is not today names its date, or `at 08:30` reads as this morning."""
    now = time.time()
    later = now + 3 * 86400
    lift = hook._render_lift(later, now)
    assert time.strftime("%Y-%m-%d", time.localtime(later)) in lift, lift
    assert time.strftime("%H:%M", time.localtime(later)) in lift, lift
    soon = now + 60
    if time.localtime(soon).tm_yday == time.localtime(now).tm_yday:
        assert hook._render_lift(soon, now) == f"at {time.strftime('%H:%M', time.localtime(soon))}"
    assert hook._render_lift(1e300, now) is None
    assert hook._render_lift(now - 10, now) is None


def test_the_finishing_verbs_take_no_trailing_arguments():
    """F3 + F4 (review round 1, executed): `merge_request.py send` is no verb, and the claim branch
    admitted any trailing args (`--session <other sid>`, `--repo /etc`, a second id). The claim
    verbs take exactly one id; `request` takes only `--review`, `--item` and `--base`."""
    for cmd in (
        "python3 scripts/work.py claim W-0123abcd",
        "python3 /opt/fabrik/scripts/work.py release W-0123abcd",
        "python3 scripts/merge_request.py request --review r.md",
        "python3 scripts/merge_request.py request --review /opt/fabrik/.tmp/runs/a/b.json "
        "--item W-0123abcd --base master",
        "python3 scripts/merge_request.py request --item W-0123abcd --review r.md",
    ):
        assert _at_lane(cmd) == "allow", cmd
    for cmd in (
        "python3 scripts/merge_request.py send",
        "python3 scripts/merge_request.py send --to x",
        "python3 scripts/work.py claim W-0123abcd --session other-sid",
        "python3 scripts/work.py claim W-0123abcd --repo /etc",
        "python3 scripts/work.py release W-0123abcd W-4567cdef",
        "python3 scripts/work.py claim W-0123abcdx",
        "python3 scripts/merge_request.py request --review r.md --force",
        "python3 scripts/merge_request.py request --review r.md --item x",
        "python3 scripts/merge_request.py request --review --base",
        "python3 scripts/merge_request.py request extra",
        "python3 scripts/merge_request.py requestx --review r.md",
    ):
        assert _at_lane(cmd) == "deny", cmd


def test_a_p0_item_its_owner_cannot_work_exempts_nobody(lane):
    """F5 (review round 1, executed): a `blocked` or `awaiting-operator` P0 still exempted its
    owner, who cannot work it. Open is status exactly `open` (work.py STATUSES)."""
    lane.bind("sq", "infra")
    lane.item("W-abababab")
    assert hook.lane_exempt("sq", str(lane.main))[0] is True  # the positive control
    for status in ("blocked", "awaiting-operator", "done", "dropped", "", None, "OPEN"):
        lane.item("W-abababab", status=status)
        assert hook.lane_exempt("sq", str(lane.main))[0] is False, status
    r = lane.run({"tool_name": "Edit", "tool_input": {}, "session_id": "sq"})
    assert _denied(r), r.stdout


# ── W-cff56c52: a /clear-rotated window re-binds its own name at the lane ──────────────────────
_REBIND = "python3 /opt/fabrik/scripts/whoami_agent.py --as {} --force"
_CLAUDE_PID, _CLAUDE_START = 4242, 777


def _proc_stat(pid: int, start: int, name: str = "claude") -> str:
    # field 22 (start time) is index 19 after the `)` — the layout `_pid_start` reads
    return f"{pid} ({name}) " + " ".join(["S", *["0"] * 18, str(start), *["0"] * 5]) + "\n"


def _fake_proc(
    root: Path,
    *,
    chain: bool = True,
    btime: int | None = 1,
    live: dict[int, int] | None = None,
    start: int = _CLAUDE_START,
) -> Path:
    """A /proc tree whose ancestry from THIS process climbs a shell (pid 4100, its own start
    tick) to a `claude` (pid 4242, start 777) — the python3 -> sh -> claude shape a hook runs
    under: `chain=False` ends the shell at pid 1 instead; `live` adds other running processes
    {pid: start}."""
    me = os.getpid()
    (root / str(me)).mkdir(parents=True)
    (root / str(me) / "status").write_text("Name:\tpython3\nPPid:\t4100\n")
    (root / "4100").mkdir()
    (root / "4100" / "status").write_text(f"Name:\tbash\nPPid:\t{_CLAUDE_PID if chain else 1}\n")
    (root / "4100" / "stat").write_text(_proc_stat(4100, 555, name="bash"))
    (root / str(_CLAUDE_PID)).mkdir()
    (root / str(_CLAUDE_PID) / "status").write_text("Name:\tclaude\nPPid:\t1\n")
    (root / str(_CLAUDE_PID) / "stat").write_text(_proc_stat(_CLAUDE_PID, start))
    for pid, pstart in (live or {}).items():
        (root / str(pid)).mkdir()
        (root / str(pid) / "status").write_text("Name:\tclaude\nPPid:\t1\n")
        (root / str(pid) / "stat").write_text(_proc_stat(pid, pstart))
    if btime is not None:
        (root / "stat").write_text(f"cpu  1 2 3\nbtime {btime}\n")
    return root


def _main_out(lane, monkeypatch, capsys, cmd: str, *, sid: str = "new-sid", cwd=None) -> str:
    """Run the real `main()` in-process (so the fake /proc tree describes THIS process) and
    return what it printed: a deny is a JSON object, an allow prints nothing on stdout."""
    import io

    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": cmd},
        "session_id": sid,
        "cwd": str(lane.wt if cwd is None else cwd),
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    capsys.readouterr()
    assert hook.main() == 0
    return capsys.readouterr().out


def _mine(lane, sid: str, name: str, **extra: object) -> None:
    lane.bind(sid, name, pid=_CLAUDE_PID, pid_start=_CLAUDE_START, **extra)


def test_a_rotated_window_can_rebind_its_own_name_at_the_lane(lane, tmp_path, monkeypatch, capsys):
    """Behaviour 1 (W-cff56c52): a `/clear` keeps the claude process and mints a new sid; the
    re-bind of the name this process held last passes the lane through the real `main()`, in
    the spelling the rotation prints and the two other shapes the lane admits — and the same
    call with no claude ancestor is held, so the grader reaches the seam rather than an
    allow-everything path."""
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.setenv("QUOTA_STOP_PROC_ROOT", str(_fake_proc(tmp_path / "proc")))
    _mine(lane, "old-sid", "infra-3")
    assert hook.lane_exempt("new-sid", str(lane.main))[0] is False  # parked before the re-bind
    for cmd in (
        _REBIND.format("infra-3"),
        "python3 /opt/fabrik/scripts/whoami_agent.py --as infra-3",
        "python3 /opt/fabrik/scripts/whoami_agent.py --force --as infra-3",
    ):
        assert _main_out(lane, monkeypatch, capsys, cmd) == "", cmd
        assert _main_out(lane, monkeypatch, capsys, cmd, cwd=lane.main) == "", cmd
    monkeypatch.setenv("QUOTA_STOP_PROC_ROOT", str(_fake_proc(tmp_path / "p2", chain=False)))
    assert '"deny"' in _main_out(lane, monkeypatch, capsys, _REBIND.format("infra-3"))


def test_a_rebind_to_a_name_this_window_did_not_hold_last_is_held(
    lane, tmp_path, monkeypatch, capsys
):
    """Behaviour 2: the lane's COBRA guard survives — a parked builder cannot bind the merge
    owner's or another builder's name: never held here, held but not LAST, re-taken by another
    window since, held by a LIVE foreign process (`--force` would override it), judged from
    another repo's cwd, or reached through a nested claude (`CLAUDE_PID` disagreeing)."""
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.setenv("QUOTA_STOP_PROC_ROOT", str(_fake_proc(tmp_path / "proc")))

    def held(name: str, **kw: object) -> bool:
        return '"deny"' in _main_out(lane, monkeypatch, capsys, _REBIND.format(name), **kw)

    lane.bind("coord-sid", "coordinator", pid=9001, pid_start=5)
    _mine(lane, "s1", "infra-3")
    assert held("coordinator")  # never this window's
    _mine(lane, "s2", "infra-5")  # the operator moved this window to infra-5
    assert held("infra-3") and not held("infra-5")
    lane.bind("other", "infra-5", pid=5555, pid_start=1)  # another window took it since
    assert held("infra-5")
    _mine(lane, "s3", "infra-7")
    assert not held("infra-7")
    assert held("infra-7", cwd=tmp_path)  # a cwd outside the judged repo writes another scope
    monkeypatch.setenv("CLAUDE_PID", "31337")
    assert held("infra-7")
    monkeypatch.setenv("CLAUDE_PID", str(_CLAUDE_PID))
    assert not held("infra-7")
    # an OLDER row of the name held by a live foreign process: --force would make two holders
    lane.bind("live", "infra-8", pid=6666, pid_start=2)
    _mine(lane, "s4", "infra-8")
    assert not held("infra-8")  # 6666 is not running in the tree yet: a dead holder is no holder
    live = _fake_proc(tmp_path / "p3", live={6666: 2})
    monkeypatch.setenv("QUOTA_STOP_PROC_ROOT", str(live))
    assert held("infra-8")
    (live / "6666" / "stat").write_text(_proc_stat(6666, 3))  # pid reused by another process
    assert not held("infra-8")
    # a live holder row written before start ticks existed is pid-only, as whoami reads it
    lane.bind("old", "infra-9", pid=6666)
    _mine(lane, "s5", "infra-9")
    assert held("infra-9")
    # an unreadable /proc/<pid> is a live holder (fail closed)
    real_is_dir = Path.is_dir

    def is_dir(self: Path) -> bool:
        if self.name == "6666":
            raise PermissionError(13, "denied")
        return real_is_dir(self)

    monkeypatch.setattr(Path, "is_dir", is_dir)
    (live / "6666" / "stat").write_text(_proc_stat(6666, 2))
    lane.bind("old2", "infra-10", pid=6666, pid_start=2)
    _mine(lane, "s6", "infra-10")
    assert held("infra-10")


def test_same_window_name_fails_closed(lane, tmp_path, monkeypatch):
    """Behaviour 3: every doubt is "" (held) — no claude ancestor, rows without pid or start,
    a bool pid, a row from before this boot, an unreadable boot time, another scope; corrupt
    lines are skipped and digit strings count (whoami's `_as_int`). And the rows whoami's own
    `bind` writes are the ones the hook reads (the writer/reader agreement)."""
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    proc = _fake_proc(tmp_path / "proc", btime=1000)

    def name(root: Path = proc, cwd: Path | None = None) -> str:
        return hook._same_window_name(lane.common, str(lane.wt if cwd is None else cwd), root)

    assert name() == ""  # an empty store
    lane.bind("a", "infra-1")  # no pid at all
    lane.bind("b", "infra-2", pid=_CLAUDE_PID)  # no start
    lane.bind("c", "infra-3", pid=True, pid_start=_CLAUDE_START)
    lane.bind("d", "infra-4", pid=_CLAUDE_PID, pid_start=_CLAUDE_START, at=999)  # pre-boot
    lane.bind("e", "infra-6", toplevel="/elsewhere/.git", pid=_CLAUDE_PID, pid_start=_CLAUDE_START)
    assert name() == ""
    with lane.store.open("a") as fh:
        fh.write("{corrupt\n[]\n")
    lane.bind("f", "infra-9", pid=str(_CLAUDE_PID), pid_start=str(_CLAUDE_START))
    assert name() == "infra-9"
    assert name(_fake_proc(tmp_path / "p2", chain=False)) == ""
    # a bool start tick never equals a real one, even the tick 1 (`True == 1`)
    lane.bind("g", "infra-12", pid=_CLAUDE_PID, pid_start=True)
    assert name(_fake_proc(tmp_path / "p5", start=1)) == ""
    lane.bind("h", "infra-12", pid=_CLAUDE_PID, pid_start=1)
    assert name(_fake_proc(tmp_path / "p6", start=1)) == "infra-12"
    assert name(_fake_proc(tmp_path / "p3", btime=None)) == ""
    assert name(tmp_path / "missing") == ""

    # a hand-edited int name is read as its string, and the walk stops at `claude`, not the shell
    lane.bind("i", 5, pid=_CLAUDE_PID, pid_start=_CLAUDE_START)
    assert name(_fake_proc(tmp_path / "p7")) == "5"
    lane.bind("j", "infra-13", pid=4100, pid_start=555)  # the shell's own key is not this window
    assert name(_fake_proc(tmp_path / "p8")) == "5"

    spec = importlib.util.spec_from_file_location("whoami_parity_rebind", _WHOAMI_PY)
    who = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(who)
    monkeypatch.setattr(who, "_session_pid", lambda: _CLAUDE_PID)
    monkeypatch.setattr(who, "_pid_start", lambda pid: _CLAUDE_START if pid else None)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "fresh")
    monkeypatch.chdir(lane.wt)
    assert who.bind("infra-11", force=True)[0] == 0
    assert name(_fake_proc(tmp_path / "p4", btime=1)) == "infra-11"


def test_the_rebind_shape_is_exact():
    """Behaviour 4: whoami's argparse binds `--a`, `--as=`, `--f` and the LAST of repeated
    `--as` (executed by both critique seats), so the lane admits one literal shape: the hub's
    absolute path, one `--as <name>`, at most one `--force`, nothing else — and only for the
    name the hook resolved for this window."""

    def at_lane(cmd: str, rebind: str = "infra-3") -> str:
        return hook.decide(
            "Bash", cmd, stamp_exists=True, tick_age_s=10.0, tier="urgent-90", exempt=False,
            rebind=rebind,
        )[0]  # fmt: skip

    assert at_lane(_REBIND.format("infra-3")) == "allow"
    assert at_lane(_REBIND.format("infra-3"), rebind="") == "deny"
    assert at_lane(_REBIND.format("coordinator")) == "deny"
    for cmd in (
        "python3 /opt/fabrik/scripts/whoami_agent.py --as=infra-3 --force",
        "python3 /opt/fabrik/scripts/whoami_agent.py --a infra-3 --force",
        "python3 /opt/fabrik/scripts/whoami_agent.py --as infra-3 --as coordinator",
        "python3 /opt/fabrik/scripts/whoami_agent.py --as infra-3 --force --as coordinator",
        "python3 /opt/fabrik/scripts/whoami_agent.py --force --as infra-3 --force",
        "python3 /opt/fabrik/scripts/whoami_agent.py --force --as --force infra-3",
        "python3 /opt/fabrik/scripts/whoami_agent.py --as infra-3 --f",
        "python3 /opt/fabrik/scripts/whoami_agent.py --as infra-3 --force extra",
        "python3 /opt/fabrik/scripts/whoami_agent.py --as INFRA-3",
        "python3 /opt/fabrik/scripts/whoami_agent.py --as -infra-3",
        "python3 /opt/fabrik/scripts/whoami_agent.py infra-3",
        "python3 scripts/whoami_agent.py --as infra-3 --force",
        "python3 /opt/evil/scripts/whoami_agent.py --as infra-3 --force",
        "python3 x/opt/fabrik/scripts/whoami_agent.py --as infra-3 --force",
        _REBIND.format("infra-3") + " && touch m",
        _REBIND.format("infra-3") + "; python3 scripts/foo.py",
        "cd /tmp && " + _REBIND.format("infra-3"),
        _REBIND.format("infra-3") + " > /tmp/x",
    ):
        assert at_lane(cmd) == "deny", cmd


def test_the_lane_admits_work_next_only_bare_and_only_at_urgent():
    """Behaviour 5: `work.py next` is read-only (`cmd_next` prints one line) and the rotation's
    resume prompt runs it, so a parked session may; any argument is held, and at `walled` both
    new verbs stay held like the claim verbs."""
    for cmd in ("python3 scripts/work.py next", "python3 /opt/fabrik/scripts/work.py next"):
        assert _at_lane(cmd) == "allow", cmd
    for cmd in (
        "python3 scripts/work.py next --repo /tmp",
        "python3 scripts/work.py next W-0123abcd",
        "python3 scripts/work.py nextx",
        "python3 scripts/work.py next && touch m",
    ):
        assert _at_lane(cmd) == "deny", cmd
    for cmd, rebind in (
        ("python3 scripts/work.py next", ""),
        (_REBIND.format("infra-3"), "infra-3"),
    ):
        assert (
            hook.decide(
                "Bash", cmd, stamp_exists=True, tick_age_s=10.0, tier="walled", rebind=rebind
            )[0]
            == "deny"
        ), cmd


def test_the_rebind_check_runs_only_on_the_rebind_call_and_fails_closed(
    lane, tmp_path, monkeypatch, capsys
):
    """The /proc walk is lazy (only a Bash call naming whoami_agent.py, so every other parked call
    keeps the hook's 5 s budget) and sits inside main()'s try: a raise there holds the re-bind,
    where an escaped raise would exit 1 and let Claude Code run the tool (fail OPEN)."""
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.setenv("QUOTA_STOP_PROC_ROOT", str(_fake_proc(tmp_path / "proc")))
    _mine(lane, "old-sid", "infra-3")
    calls: list[str] = []

    def boom(*a: object, **k: object) -> str:
        calls.append("called")
        raise RuntimeError("proc walk failed")

    monkeypatch.setattr(hook, "_same_window_name", boom)
    assert _main_out(lane, monkeypatch, capsys, "python3 scripts/work.py next") == ""
    assert '"deny"' in _main_out(lane, monkeypatch, capsys, "python3 scripts/foo.py")
    assert calls == []
    assert '"deny"' in _main_out(lane, monkeypatch, capsys, _REBIND.format("infra-3"))
    assert calls == ["called"]


def test_proc_start_reads_past_a_paren_in_the_process_name(tmp_path):
    """Field 22 is counted after the LAST `)`: a process named `a) b` must not shift it."""
    (tmp_path / "77").mkdir()
    (tmp_path / "77" / "stat").write_text(_proc_stat(77, 4321, name="a) S 9 9"))
    assert hook._proc_start(tmp_path, 77) == 4321
    assert hook._proc_start(tmp_path, 78) is None


def test_the_scope_realpath_runs_once_per_distinct_scope(lane, monkeypatch):
    """`_scoped_rows` runs on every parked call (through `_bound_name`), so a store of many rows
    sharing one scope costs one realpath for it, never one per row (review pass 1: 0.60 -> 2.97
    ms per call on the live 140-row store)."""
    for i in range(30):
        lane.bind(f"s{i}", "infra")
    lane.bind("other", "infra", toplevel="/elsewhere/.git")
    real = os.path.realpath
    seen: list[str] = []

    def counting(p: object, *a: object, **k: object) -> str:
        seen.append(str(p))
        return real(p, *a, **k)

    monkeypatch.setattr(hook.os.path, "realpath", counting)
    assert len(hook._scoped_rows(lane.common)) == 30
    # the judged scope itself, then one per distinct row scope (2): 3, where per-row was 32
    assert len(seen) == 3 and seen.count("/elsewhere/.git") == 1, seen


# --- W-effb7141: a session on an Anthropic API key draws no plan quota --------------------------


@pytest.mark.parametrize("tier", ["walled", "urgent-90"])
def test_an_api_key_session_is_not_held_by_the_wall_or_the_lane(tmp_path, tier):
    state = tmp_path / "state"
    state.mkdir()
    (state / "fleet-exhausted").write_text(f"1\n{tier}\n")
    r = _run(
        tmp_path,
        {"tool_name": "Edit", "tool_input": {"file_path": "x.py"}, "session_id": "s1"},
        stamp=False,
        tick_fresh=True,
        extra_env={"ANTHROPIC_API_KEY": "sk-ant-api03-x"},
    )
    assert r.returncode == 0
    assert r.stdout.strip() == "", r.stdout
    assert "API key" in r.stderr


@pytest.mark.parametrize(
    "extra",
    [
        {"ANTHROPIC_API_KEY": "sk-ant-api03-x", "CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat01-x"},
        {"ANTHROPIC_API_KEY": "  "},
        {},
    ],
    ids=["oauth-token-beside-the-key", "blank-key", "no-key"],
)
def test_a_plan_session_is_still_held_at_the_wall(tmp_path, extra):
    r = _run(
        tmp_path,
        {"tool_name": "Edit", "tool_input": {"file_path": "x.py"}},
        stamp=True,
        tick_fresh=True,
        extra_env=extra,
    )
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize(
    "line2",
    ["battery", "bogus", "", " BATTERY", "walled-ish"],
    ids=["battery", "unknown-tier", "pre-tier", "padded-battery", "near-miss"],
)
def test_only_a_plain_quota_tier_lets_an_api_key_session_through(tmp_path, line2):
    """The battery stamp (D-898) protects the BOX, not plan quota, and any line 2 that is not
    plainly `walled` or `urgent-90` holds — the unknown case is never the lenient one."""
    state = tmp_path / "state"
    state.mkdir()
    (state / "fleet-exhausted").write_text(f"1\n{line2}\n")
    r = _run(
        tmp_path,
        {"tool_name": "Edit", "tool_input": {"file_path": "x.py"}},
        stamp=False,
        tick_fresh=True,
        extra_env={"ANTHROPIC_API_KEY": "sk-ant-api03-x"},
    )
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_a_battery_stamp_that_is_a_directory_still_holds_an_api_key_session(tmp_path):
    state = tmp_path / "state"
    (state / "fleet-exhausted").mkdir(parents=True)
    r = _run(
        tmp_path,
        {"tool_name": "Edit", "tool_input": {"file_path": "x.py"}},
        stamp=False,
        tick_fresh=True,
        extra_env={"ANTHROPIC_API_KEY": "sk-ant-api03-x"},
    )
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_a_stale_tick_keeps_its_own_warning_for_an_api_key_session(tmp_path):
    """A stale tick means the hold is OFF: the session hears the dead-cron warning every plan
    session hears, never a claim that the hold is in force."""
    r = _run(
        tmp_path,
        {"tool_name": "Edit", "tool_input": {"file_path": "x.py"}},
        stamp=True,
        tick_fresh=False,
        extra_env={"ANTHROPIC_API_KEY": "sk-ant-api03-x"},
    )
    assert r.stdout.strip() == ""
    assert "rotation tick has not run" in r.stderr
    assert "API key" not in r.stderr


def test_an_allowed_call_prints_no_exemption_note(tmp_path):
    r = _run(
        tmp_path,
        {"tool_name": "Read", "tool_input": {"file_path": "x.py"}},
        stamp=True,
        tick_fresh=True,
        extra_env={"ANTHROPIC_API_KEY": "sk-ant-api03-x"},
    )
    assert r.stdout.strip() == "" and r.stderr == ""
