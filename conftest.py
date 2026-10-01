"""Root pytest configuration: a test process NEVER carries live alerting into a child.

504 of the 526 subprocess spawns across the nine suites measured in round 66 (the mute reaches every suite in the tree, eleven at last count) inherit the parent environment (env=None),
and the hub's own `.env` arms Telegram delivery for every script that autoloads it — two graders
DELIVERED real alerts before their throwaway-root forms landed (the FC6 and FE6 disclosures). Muting
the parent once closes the class for every spawn; a test that needs alerting ARMED un-mutes itself
with `monkeypatch.delenv("ALERT_ENABLED")` — the default is silence (B65-9, FF1).
"""

import os
import sys
from pathlib import Path


def import_this_trees_src() -> None:
    """Import THIS tree's `fabrik`, never the main checkout's (W-83ff5917).

    Every hub worktree shares /opt/fabrik/.venv, whose editable install (`_editable_impl_fabrik
    .pth`) puts /opt/fabrik/src on sys.path, so a test run inside .claude/worktrees/<name> imported
    master's `fabrik` and every red-first/green claim made there graded the wrong code. This root
    conftest loads before any test module under any path, so putting this tree's src first here
    covers the test process; PYTHONPATH (which outranks .pth entries) carries it into every child
    that inherits os.environ. A child built with a hand-written env= gets no PYTHONPATH and still
    resolves the .pth — that spawn names its own path. In the main checkout this is a no-op: its
    src is the one the .pth already names."""
    src = str(Path(__file__).resolve().parent / "src")
    if sys.path[:1] != [src]:
        sys.path.insert(0, src)
    inherited = os.environ.get("PYTHONPATH", "")
    if inherited.split(os.pathsep)[:1] != [src]:
        os.environ["PYTHONPATH"] = os.pathsep.join(p for p in (src, inherited) if p)


def mute_alerting() -> None:
    """Unconditional: an operator shell exporting ALERT_ENABLED=1 must not make a suite deliver."""
    os.environ["ALERT_ENABLED"] = "0"
    os.environ["FABRIK_NO_AUTOLOAD"] = "1"


import_this_trees_src()
mute_alerting()
