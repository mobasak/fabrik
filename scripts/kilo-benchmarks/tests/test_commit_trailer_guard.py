"""Behaviour tests for scripts/check_commit_trailers.py.

Two layers, and the second matters as much as the first: the guard must reject the right
messages, AND it must actually be WIRED to run. A correct check that nothing invokes is the
inert-check class this repo has been bitten by before (`check_doc_sprawl` sat inert for weeks
while reporting green), so `test_the_guard_is_wired_*` are not ceremony — they are the tests
that keep the other five from becoming decorative.
"""

from __future__ import annotations

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
    """A hand-rolled parser drifts from git; drift is how a guard goes quietly vacuous."""
    src = GUARD.read_text()
    assert "interpret-trailers" in src and "--parse" in src


def test_the_guard_is_wired_at_the_commit_msg_stage(tmp_path):
    """pre-commit stage, not commit-msg, would fire when the message cannot yet be read."""
    config = yaml.safe_load((REPO / ".pre-commit-config.yaml").read_text())
    hooks = [h for r in config["repos"] for h in r.get("hooks", [])]
    hook = next((h for h in hooks if h["id"] == "agent-trailers-parse"), None)
    assert hook is not None, "the guard is not registered in .pre-commit-config.yaml — inert"
    assert hook.get("stages") == ["commit-msg"], (
        f"the guard must run at commit-msg (the last point the message is editable); "
        f"got stages={hook.get('stages')!r}"
    )
    assert "check_commit_trailers.py" in hook["entry"]


def test_the_commit_msg_hook_type_is_actually_installed():
    """`pre-commit install` alone installs only pre-commit; commit-msg needs --hook-type."""
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
    assert hook.exists(), (
        "the commit-msg hook is not installed, so the guard never runs on a real commit: "
        "run `pre-commit install --hook-type commit-msg`"
    )
    assert "pre-commit" in hook.read_text(errors="ignore")


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


@pytest.mark.parametrize("name", sorted(DIFFERENTIAL))
def test_the_guards_verdict_never_diverges_from_git(name, tmp_path):
    """Whatever git parses, the guard must accept; whatever git cannot, it must reject."""
    sys.path.insert(0, str(REPO / "scripts"))
    from check_commit_trailers import parsed_trailers

    message = DIFFERENTIAL[name]
    git_can_parse = bool(parsed_trailers(message).get("Agent-Role"))
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
