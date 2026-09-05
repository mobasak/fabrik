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
    assert "git commit -m <msg> -- <paths>" in hook._reason("Bash")


def test_an_unquoted_variable_word_splits_and_is_held_but_a_quoted_one_is_data():
    """`git push $PV` with `PV='origin --force'` exported before the hold made a forced update on a
    remote, and `git commit -m $MSG -- f` with a `--amend` inside amended a pushed commit (P23-A,
    executed): the checker's argv has one opaque token where bash, word-splitting the unquoted
    expansion, has two. An unquoted `$NAME`/`${NAME}` is a veto; the quoted form expands to one
    word and cannot become a flag, so it stays data."""
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
        'cat "$F"',
    ):
        assert hook.decide("Bash", cmd, stamp_exists=True, tick_age_s=1.0)[0] == "allow", cmd


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
    # since pass 24 a plain `"$VAR"` is data (one word — it cannot become a flag); `"$("` stays visible
    assert "$" not in hook._mask_quoted('echo "$VAR;x"') and ";" not in hook._mask_quoted(
        'echo "$VAR;x"'
    )
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
