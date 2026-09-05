"""dr_env_backup.sh commits with a PATHSPEC — never a bare `git commit`.

A bare commit takes the WHOLE index; on a shared tree that is a sibling's staged work
(update_vps_docs.py shipped one that way at 5b9c420d — fleet 01M1QB46, 2026-09-05). The DR
store is a dedicated repo today, but a script's commit discipline must not depend on where it
happens to run. Structural pin: the one `git commit` in the script names its pathspec.
"""

from __future__ import annotations

import re
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "dr_env_backup.sh"


def test_the_backup_commit_carries_a_pathspec():
    text = SCRIPT.read_text(encoding="utf-8")
    commits = [line for line in text.splitlines() if re.match(r"^\s*git commit\b", line)]
    assert len(commits) == 1, commits
    assert re.search(r'\s--\s+"\$DR_PATHS"', commits[0]), commits[0]
    # single-sourced: the add reads the SAME variable, and the variable names env/
    assert re.search(r'^git add -- "\$DR_PATHS"$', text, re.M), "add must read DR_PATHS"
    assert re.search(r'^DR_PATHS="env/"', text, re.M), "DR_PATHS must name env/"
