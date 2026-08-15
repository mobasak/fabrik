"""Behaviour tests for scripts/check_commit_trailers.py.

Two layers, and the second matters as much as the first: the guard must reject the right
messages, AND it must actually be WIRED to run. A correct check that nothing invokes is the
inert-check class this repo has been bitten by before (`check_doc_sprawl` sat inert for weeks
while reporting green), so `test_the_guard_is_wired_*` are not ceremony — they are the tests
that keep the other five from becoming decorative.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
GUARD = REPO / "scripts" / "check_commit_trailers.py"

GOOD = (
    "fix(worker): handle OOM exit code -9\n"
    "\n"
    "Some explanatory prose about the change.\n"
    "\n"
    "Agent-Role: primary\n"
    "Agent-Context: added OOM detection\n"
    "Co-Authored-By: Claude <noreply@anthropic.com>\n"
)
# The exact shape of the 190/190 fleet-wide failure: a blank line demotes everything above it.
BLANK_INSIDE = GOOD.replace(
    "Agent-Context: added OOM detection\nCo-Authored-By:",
    "Agent-Context: added OOM detection\n\nCo-Authored-By:",
)
# The mirror-image failure, introduced by the very commit that fixed the one above.
PROSE_GLUED = GOOD.replace("change.\n\nAgent-Role:", "change.\nAgent-Role:")


def run(message: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text(message, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(GUARD), str(msg)],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO,
    )


def test_a_correctly_formed_trailer_block_is_accepted(tmp_path):
    assert run(GOOD, tmp_path).returncode == 0


def test_a_blank_line_inside_the_block_is_rejected(tmp_path):
    """The defect that cost 190 of 200 hub commits their provenance."""
    result = run(BLANK_INSIDE, tmp_path)
    assert result.returncode == 1
    assert "BLANK LINE" in result.stderr, "the message must name the specific defect"


def test_prose_glued_to_the_top_of_the_block_is_rejected(tmp_path):
    result = run(PROSE_GLUED, tmp_path)
    assert result.returncode == 1
    assert "GLUED" in result.stderr


def test_a_commit_without_agent_role_passes_through(tmp_path):
    """Merges, reverts, and human commits are not this hook's business."""
    assert run("chore: a human wrote this\n", tmp_path).returncode == 0


def test_gits_editor_comments_are_not_mistaken_for_prose(tmp_path):
    """`git commit` appends `# …` lines; counting them as prose would false-red every commit."""
    commented = GOOD + "\n# Please enter the commit message for your changes.\n#\n# On branch master\n"
    assert run(commented, tmp_path).returncode == 0


def test_the_guard_delegates_to_git_rather_than_reimplementing_its_rules(tmp_path):
    """A hand-rolled parser drifts from git; drift is how a guard goes quietly vacuous.

    Asserting the strings "interpret-trailers" and "--parse" appear in the source proved
    nothing: both occur in the module DOCSTRING, so swapping in a hand-rolled parser while
    leaving the prose kept the test green. Prove delegation by BEHAVIOUR — take git away and
    the verdict must change, which is only possible if git was being consulted.
    """
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text(BLANK_INSIDE, encoding="utf-8")
    args = [sys.executable, str(GUARD), str(msg)]

    with_git = subprocess.run(args, capture_output=True, text=True, check=False, cwd=REPO)
    without_git = subprocess.run(
        args, capture_output=True, text=True, check=False, cwd=REPO, env={"PATH": "/nonexistent"}
    )
    assert with_git.returncode == 1, "the malformed block should be rejected when git is present"
    assert without_git.returncode == 0, (
        "with git unavailable the guard must fail open, not reject and not traceback"
    )
    assert "Traceback" not in without_git.stderr, without_git.stderr


def test_the_guard_is_not_routed_through_pre_commit(tmp_path):
    """pre-commit's commit-msg stage stashes unstaged work a SECOND time, per commit.

    This tree is shared by three concurrent agents and a pre-commit stash has already reverted
    uncommitted work here once. Routing the guard through pre-commit doubled that window and
    added a second site for the "Your pre-commit configuration is unstaged" abort — both
    observed live. A plain `.git/hooks/commit-msg` shim has neither failure mode, so the guard
    must NOT reappear as a pre-commit hook.
    """
    config = yaml.safe_load((REPO / ".pre-commit-config.yaml").read_text())
    # A top-level `default_stages: [commit-msg]` routes hooks that declare NO stages of their
    # own — reading only per-hook `stages` missed that entirely.
    default_stages = config.get("default_stages") or []
    hooks = [h for r in config["repos"] for h in r.get("hooks", [])]
    offenders = [
        h for h in hooks
        if "commit-msg" in (h.get("stages") or default_stages)
    ]
    assert not offenders, (
        f"a commit-msg-stage pre-commit hook reintroduces the doubled stash cycle: {offenders}"
    )

    # ⚠️ The config is not the ground truth — `pre-commit install --hook-type commit-msg`
    # REPLACES .git/hooks/commit-msg with pre-commit's generated hook (moving ours to
    # commit-msg.legacy) and restores the doubled stash cycle, while this config stays clean.
    # Reproduced live. Assert on what is actually INSTALLED.
    hook = _installed_hook()
    if hook is not None and hook.exists():
        text = hook.read_text(errors="replace")
        assert "check_commit_trailers" in text and "pre_commit" not in text, (
            "the installed commit-msg hook has been taken over by pre-commit — the doubled "
            "stash cycle is back. Reclaim it: "
            "`python3 scripts/check_commit_trailers.py --install --force`"
        )


def _installed_hook():
    """Resolve .git/hooks/commit-msg via git, so worktrees resolve to the SHARED hooks dir."""
    common = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        capture_output=True, text=True, check=False, cwd=REPO,
    )
    if common.returncode != 0:
        return None
    return (REPO / common.stdout.strip()).resolve() / "hooks" / "commit-msg"


def test_the_commit_msg_hook_is_actually_installed_and_points_at_this_guard():
    """A correct guard nothing invokes is the inert-check class — assert it is really wired."""
    # ⚠️ Resolve the hooks dir via git, never as REPO/".git"/"hooks". In a WORKTREE — which is
    # how plan execution runs here — `.git` is a FILE, not a directory, so an `is_dir()` guard
    # skips and the test goes vacuously green in the very environment where a missing hook
    # matters. `--git-common-dir` resolves to the shared hooks dir from a worktree too.
    common = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        capture_output=True, text=True, check=False, cwd=REPO,
    )
    if common.returncode != 0:
        pytest.skip("not a git checkout")
    hook = (REPO / common.stdout.strip()).resolve() / "hooks" / "commit-msg"
    # Only meaningful where hooks are installed at all. A fresh clone that has never run any
    # installer is not a regression — but a repo with hooks installed and THIS one missing is.
    if not (hook.parent / "pre-commit").exists() and not hook.exists():
        pytest.skip("no git hooks installed in this checkout at all")
    assert hook.exists(), (
        "the commit-msg hook is not installed, so the guard never runs on a real commit: "
        "run `python3 scripts/check_commit_trailers.py --install`"
    )
    assert "check_commit_trailers" in hook.read_text(errors="replace"), (
        "a commit-msg hook exists but does not invoke this guard"
    )
    # ⚠️ git SILENTLY IGNORES a non-executable hook — it prints a notice and the commit lands.
    # Reproduced with chmod 644: the malformed commit went through while both content
    # assertions above still passed. Only install() ever sets the mode.
    assert os.access(hook, os.X_OK), (
        f"{hook} is not executable, so git ignores it entirely and the guard never runs: "
        f"re-run `python3 scripts/check_commit_trailers.py --install`"
    )


# The verdict must be git's verdict. Anything the guard does to the message before asking git
# is room for the two to disagree — and a guard that disagrees with the tool it guards is worse
# than no guard, because it is trusted. These are the seven shapes a real commit message takes.
DIFFERENTIAL = {
    "editor comments appended": "fix: x\n\nAgent-Role: primary\nCo-Authored-By: Y <y@z>\n\n"
    "# Please enter the commit message.\n# On branch master\n",
    "comment inside the block": "fix: x\n\nAgent-Role: primary\n# note\nCo-Authored-By: Y <y@z>\n",
    "blank line inside block": "fix: x\n\nAgent-Role: primary\n\nCo-Authored-By: Y <y@z>\n",
    "prose glued to top": "fix: x\n\nprose.\nAgent-Role: primary\nCo-Authored-By: Y <y@z>\n",
    "issue ref in body": "fix: x\n\ncloses #123\n\nAgent-Role: primary\nCo-Authored-By: Y <y@z>\n",
    "markdown heading in body": "fix: x\n\n# Heading\nprose\n\nAgent-Role: primary\n"
    "Co-Authored-By: Y <y@z>\n",
    "comment-only final paragraph": "fix: x\n\nAgent-Role: primary\n\n# just a comment\n",
}


def _git_verdict(message: str, tmp_path: Path) -> bool:
    """Independent oracle: make a REAL commit and read the trailer back with `git log`.

    Using the guard's own `parsed_trailers()` as the oracle was circular — it could only ever
    test main()'s pre/post-processing and was blind to any drift INSIDE parsed_trailers itself.
    `git log --format='%(trailers:...)'` is the query CLAUDE.md says the trailers exist for, so
    it is the verdict that actually matters.
    """
    repo = tmp_path / "oracle"
    repo.mkdir()
    run_git = lambda *a: subprocess.run(  # noqa: E731
        ["git", *a], cwd=repo, capture_output=True, text=True, check=False
    )
    run_git("init", "-q", ".")
    run_git("config", "user.email", "t@t")
    run_git("config", "user.name", "t")
    (repo / "f").write_text("x")
    run_git("add", "f")
    # -c commit.gpgsign=false: a machine-global signing config with no key makes the commit
    # fail rc=128, and an unchecked return code turned that into a silent `False` — which reads
    # as "git cannot parse this", making the malformed cases agree VACUOUSLY.
    committed = run_git("-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m", message)
    assert committed.returncode == 0, (
        f"the oracle could not create its commit, so its verdict would be meaningless: "
        f"{committed.stderr.strip()}"
    )
    return bool(
        run_git("log", "-1", "--format=%(trailers:key=Agent-Role,valueonly)").stdout.strip()
    )


@pytest.mark.parametrize("name", sorted(DIFFERENTIAL))
def test_the_guards_verdict_never_diverges_from_git(name, tmp_path):
    """Whatever git parses, the guard must accept; whatever git cannot, it must reject."""
    message = DIFFERENTIAL[name]
    git_can_parse = _git_verdict(message, tmp_path)
    guard_accepts = run(message, tmp_path).returncode == 0
    assert guard_accepts == git_can_parse, (
        f"{name}: git {'parses' if git_can_parse else 'CANNOT parse'} Agent-Role but the guard "
        f"{'accepts' if guard_accepts else 'rejects'} — the guard has diverged from git"
    )


def test_a_non_utf8_commit_message_does_not_crash_the_hook(tmp_path):
    """A traceback from a git hook is an unactionable failure; degrade, don't explode."""
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_bytes(b"fix: caf\xe9\n\nAgent-Role: primary\nCo-Authored-By: Y <y@z>\n")
    result = subprocess.run(
        [sys.executable, str(GUARD), str(msg)], capture_output=True, text=True, check=False, cwd=REPO
    )
    assert "Traceback" not in result.stderr, result.stderr
    assert result.returncode == 0


# `git commit -v` appends the whole diff below a scissors line, UNCOMMENTED. Any commit editing
# a file that contains the literal string "Agent-Role:" — this script, these tests, CLAUDE.md —
# therefore carries that string in its buffer without being an agent commit at all.
VERBOSE_DIFF = (
    "docs: edit the trailer documentation\n"
    "\n"
    "A normal commit that declares no trailers of its own.\n"
    "\n"
    "# ------------------------ >8 ------------------------\n"
    "# Do not modify or remove the line above.\n"
    "diff --git a/CLAUDE.md b/CLAUDE.md\n"
    "+Agent-Role: primary\n"
)


def test_a_verbose_commit_whose_diff_mentions_agent_role_is_not_hijacked(tmp_path):
    """The diff below the scissors line is not the author's text and must not be read as such."""
    result = run(VERBOSE_DIFF, tmp_path)
    assert result.returncode == 0, (
        "a commit that merely EDITS a file containing 'Agent-Role:' was rejected as a "
        f"malformed agent commit:\n{result.stderr}"
    )


def test_a_verbose_commit_with_a_real_broken_block_is_still_rejected(tmp_path):
    """The scissors fix must not become a bypass: authored trailers are still checked."""
    broken = BLANK_INSIDE + "\n# ------------------------ >8 ------------------------\ndiff --git a/x b/x\n"
    assert run(broken, tmp_path).returncode == 1


def test_the_unattended_pipeline_commit_is_not_blocked_by_this_guard(tmp_path):
    """The boot-time auto-commit runs with no human present — a false reject is invisible.

    autocommit_pipeline_outputs.sh always `exit 0`s, so its caller's `|| echo … errored` can
    never fire: a persistently failing commit-msg hook would disable the auto-commit SILENTLY
    and FOREVER, and the tree would just go quietly dirty for every subsequent agent. Nothing
    pinned its message form against this guard, so a single shape change on either side breaks
    it with no signal. This test is that pin: it extracts the ACTUAL trailer block from the
    shell script and runs it through the real guard.
    """
    script = (REPO / "scripts" / "kilo-benchmarks" / "autocommit_pipeline_outputs.sh").read_text()
    # ⚠️ Extract EVERY -m argument, in order, and join them the way git does. Hand-slicing only
    # the `-m "Agent-Role:…"` argument and prepending a made-up subject meant a THIRD -m added
    # after the trailer block — a plausible "add a note" edit — left this test green while the
    # message git actually builds is REJECTED. Both measured. Since the script always exits 0,
    # that would disable the boot auto-commit silently and permanently: exactly the catastrophe
    # this test claims to prevent, waved through by an approximation of the input.
    invocation = script[script.index("git commit"):]
    invocation = invocation[: invocation.index("\n  -- ")]
    m_args = re.findall(r'-m "((?:[^"\\]|\\.)*)"', invocation, re.S)
    assert len(m_args) >= 2, f"expected at least a subject and a trailer block, got {m_args!r}"
    assert any(a.startswith("Agent-Role:") for a in m_args), m_args

    # git joins multiple -m arguments with a BLANK LINE between each.
    message = "\n\n".join(m_args) + "\n"
    # Shell expansions are irrelevant to trailer parsing; neutralise them so the harness does
    # not depend on runtime values.
    message = re.sub(r"\$\{?\w+\}?|\$\([^)]*\)", "x", message)
    result = run(message, tmp_path)
    assert result.returncode == 0, (
        "the unattended boot-time auto-commit would be REJECTED by this guard, which silently "
        f"disables it forever:\n{result.stderr}"
    )


def test_a_conflict_resolution_commit_is_still_checked(tmp_path):
    """MERGE_HEAD is NOT a replayed message — it is a normal authored commit.

    Reproduced before this guard was narrowed: after a conflicted `git merge`, the resolver
    runs `git commit`, MERGE_HEAD still exists, and a malformed trailer went through
    unchecked. `git revert --no-edit` and rebase replay never fire this hook at all, so
    listing them alongside cherry-pick bought nothing and only widened the exemption.
    """
    repo = tmp_path / "merge"
    repo.mkdir()
    g = lambda *a: subprocess.run(  # noqa: E731
        ["git", *a], cwd=repo, capture_output=True, text=True, check=False
    )
    g("init", "-q", "-b", "main", ".")
    g("config", "user.email", "t@t")
    g("config", "user.name", "t")
    (repo / "f").write_text("base\n")
    g("add", "f")
    g("commit", "-q", "-m", "base")
    g("checkout", "-q", "-b", "side")
    (repo / "f").write_text("side\n")
    g("add", "f")
    g("commit", "-q", "-m", "side")
    g("checkout", "-q", "main")
    (repo / "f").write_text("main\n")
    g("add", "f")
    g("commit", "-q", "-m", "main")
    g("merge", "side")
    assert (repo / ".git" / "MERGE_HEAD").exists(), "expected a conflicted merge"

    (repo / "f").write_text("resolved\n")
    g("add", "f")
    hook = repo / ".git" / "hooks" / "commit-msg"
    hook.write_text(f'#!/bin/sh\nexec {sys.executable} {GUARD} "$1"\n')
    hook.chmod(0o755)

    result = g("commit", "-m", BLANK_INSIDE)
    assert result.returncode != 0, (
        "a malformed trailer block passed during conflict resolution — MERGE_HEAD was treated "
        "as a replayed message when the commit is genuinely authored here"
    )


def test_a_body_line_mentioning_8_is_not_treated_as_a_scissors_line(tmp_path):
    """`# >8 threads regressed` truncated the message and silently bypassed the guard."""
    message = (
        "perf: tune the worker pool\n"
        "\n"
        "# >8 threads regressed throughput on the shared box\n"
        "\n"
        "Agent-Role: primary\n"
        "\n"
        "Co-Authored-By: Y <y@z>\n"
    )
    assert run(message, tmp_path).returncode == 1, (
        "the malformed trailer below a `# >8 ...` prose line was never checked — the loose "
        "scissors match discarded everything under it"
    )
