"""A script whose header says RETIRED must not be a step of either scheduler.

A retirement that edits only the header retires nothing: `generate_kilo_agents.py` carried
`# RETIRED 2026-07-19` for two months while the 06:00 cron ran it every day (D-415). The two
schedulers the hub owns are `scripts/kilo-benchmarks/daily_refresh.sh` (cron) and
`scripts/wsl_startup_hook.sh` (boot); the crontab itself is the operator's and is not in the tree.

It reads the two schedulers' OWN lines, so a retired script reached through a wrapper the
scheduler calls escapes it — a bounded read, stated here rather than hidden.

The cheapest way to satisfy this without the outcome is to delete the RETIRED line from a script
the cron still runs — the header then lies the other way. `test_the_scan_sees_the_retired_set`
keeps the population honest by asserting the scan finds the known retired scripts at all.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCHEDULERS = (
    _ROOT / "scripts" / "kilo-benchmarks" / "daily_refresh.sh",
    _ROOT / "scripts" / "wsl_startup_hook.sh",
)
_SKIP_PARTS = {"archived", ".archive", ".lcb-venv", "node_modules", "__pycache__"}
_RETIRED = re.compile(r"^\s*#\s*RETIRED\b", re.M)


def _retired_scripts() -> list[Path]:
    found = []
    # os.walk with in-place pruning: rglob descends the benchmark venv (tens of thousands of files)
    # before any filter can skip it.
    for dirpath, dirnames, filenames in os.walk(_ROOT / "scripts"):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_PARTS]
        for name in filenames:
            if not name.endswith((".py", ".sh")):
                continue
            path = Path(dirpath) / name
            with path.open(encoding="utf-8", errors="replace") as fh:
                head = "".join(line for _, line in zip(range(25), fh, strict=False))
            if _RETIRED.search(head):
                found.append(path)
    return sorted(found)


def _executable_lines(path: Path) -> list[str]:
    return [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_the_scan_sees_the_retired_set() -> None:
    names = {p.name for p in _retired_scripts()}
    assert {"generate_kilo_agents.py", "kilo_model_sync.py"} <= names, sorted(names)


def test_no_retired_script_is_a_scheduler_step() -> None:
    hits = [
        f"{sched.relative_to(_ROOT)}: {line.strip()}"
        for sched in _SCHEDULERS
        for line in _executable_lines(sched)
        for retired in _retired_scripts()
        if retired.name in line
    ]
    assert not hits, "a RETIRED script is still scheduled:\n" + "\n".join(hits)
