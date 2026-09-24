"""Distribution contract for ``scripts/work.py`` (ticket T07).

``work.py`` is fleet-synced like ``thread_anchor.py``: it must ride ``CORE_SCRIPTS`` (and the
generated project ``.gitignore`` block that follows from it), the ``governance-sync`` files-filter
in ``.pre-commit-config.yaml`` (so a commit touching it distributes), and the Task-tools env block
in ``.claude/settings.json`` (D-397). Three rows, one per Behavior-Contract line in
``T07-distribution.md``.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(REPO / "scripts"))
import fabrik_synced_manifest as m  # noqa: E402


def test_core_scripts_and_gitignore_name_work_and_thread_anchor_together() -> None:
    """spec § The CLI: work.py travels with thread_anchor.py through CORE_SCRIPTS, and the
    generated gitignore block (derived from CORE_SCRIPTS) follows automatically."""
    assert "work.py" in m.CORE_SCRIPTS
    assert "thread_anchor.py" in m.CORE_SCRIPTS
    # work.py is never accidentally also RETIRED (the two lists must stay disjoint).
    assert "work.py" not in m.RETIRED_CORE_SCRIPTS

    synced_scripts = m.gitignore_dest_paths()["Synced scripts"]
    assert "scripts/work.py" in synced_scripts
    assert "scripts/thread_anchor.py" in synced_scripts

    block = m.gitignore_block_text()
    assert "scripts/work.py" in block
    assert "scripts/thread_anchor.py" in block


def _governance_sync_files_filter(pre_commit_config: Path) -> str:
    """Read the ``governance-sync`` hook's ``files:`` regex the way
    ``scripts/governance_sync_postcommit.sh`` reads it back out of the YAML at runtime."""
    cfg = yaml.safe_load(pre_commit_config.read_text())
    for repo in cfg.get("repos", []):
        for hook in repo.get("hooks", []):
            if hook.get("id") == "governance-sync":
                return hook.get("files", "")
    raise AssertionError("no governance-sync hook found in .pre-commit-config.yaml")


def test_governance_sync_regex_matches_work_and_thread_anchor_and_nothing_new() -> None:
    """spec § Shape / infra: the merged filter matches scripts/work.py, still matches
    scripts/thread_anchor.py, and matches no other tracked path it did not already match —
    proven over every path ``git ls-files`` lists, before and after this ticket's edit."""
    filter_after = _governance_sync_files_filter(REPO / ".pre-commit-config.yaml")
    regex_after = re.compile(filter_after)

    # The pre-ticket regex: this edit's only change to the alternation was inserting
    # "work|" immediately before "whoami_agent" (T07-distribution.md step 2). Reconstructing
    # it by removing exactly that substring — rather than hand-typing a second copy of the
    # whole regex — means this test cannot drift from the real edit's shape.
    needle = "thread_anchor|work|whoami_agent"
    assert needle in filter_after, (
        "expected 'work' inserted right after 'thread_anchor' in the alternation; "
        f"got: {filter_after!r}"
    )
    filter_before = filter_after.replace(needle, "thread_anchor|whoami_agent", 1)
    assert filter_before != filter_after
    regex_before = re.compile(filter_before)

    all_paths = subprocess_git_ls_files()
    assert all_paths, "git ls-files returned nothing — the population is empty, refusing to assert"

    matched_before = {p for p in all_paths if regex_before.search(p)}
    matched_after = {p for p in all_paths if regex_after.search(p)}

    assert "scripts/work.py" in matched_after
    assert "scripts/work.py" not in matched_before  # the new coverage this ticket adds
    assert "scripts/thread_anchor.py" in matched_before
    assert "scripts/thread_anchor.py" in matched_after  # unchanged sibling still matches

    # No other path it did not match before: the only newcomer is scripts/work.py.
    newly_matched = matched_after - matched_before
    assert newly_matched == {"scripts/work.py"}, newly_matched
    # And nothing that used to match stopped matching.
    assert matched_before <= matched_after


def subprocess_git_ls_files() -> list[str]:
    import subprocess

    out = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [line for line in out.splitlines() if line]


def test_settings_json_env_adds_task_tools_without_changing_existing_keys() -> None:
    """spec § The native Task list (D-392 ruling 1, D-397): CLAUDE_CODE_ENABLE_TASKS and
    CLAUDE_CODE_ENABLE_TODO_TOOLS are both "1", and every other top-level key is untouched."""
    settings = json.loads((REPO / ".claude" / "settings.json").read_text())

    assert settings["env"] == {
        "CLAUDE_CODE_ENABLE_TASKS": "1",
        "CLAUDE_CODE_ENABLE_TODO_TOOLS": "1",
    }

    # Every key this ticket's Touches list did not authorise to change stays exactly as it was.
    assert settings["enableAllProjectMcpServers"] is True
    assert settings["worktree"] == {"baseRef": "head", "symlinkDirectories": [".venv"]}
    assert "Stop" in settings["hooks"]
    assert "SessionStart" in settings["hooks"]
    assert "UserPromptSubmit" in settings["hooks"]
    assert "PreToolUse" in settings["hooks"]
    assert "Bash(git status:*)" in settings["permissions"]["allow"]
    # The env block is additive: no pre-existing top-level key was removed.
    assert set(settings) == {
        "enableAllProjectMcpServers",
        "env",
        "permissions",
        "hooks",
        "worktree",
    }
