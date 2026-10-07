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
    assert {"kilo_cost_tracker.py"} <= names, sorted(names)


def test_no_retired_script_is_a_scheduler_step() -> None:
    hits = [
        f"{sched.relative_to(_ROOT)}: {line.strip()}"
        for sched in _SCHEDULERS
        for line in _executable_lines(sched)
        for retired in _retired_scripts()
        if retired.name in line
    ]
    assert not hits, "a RETIRED script is still scheduled:\n" + "\n".join(hits)


def test_no_scheduler_runs_an_archived_script() -> None:
    """The retired scan prunes `archived/`, so a scheduler line naming an archived script would pass the
    test above; this closes it for every file in `scripts/archived/`."""
    archived = {p.name for p in (_ROOT / "scripts" / "archived").iterdir() if p.is_file()}
    hits = [
        f"{sched.relative_to(_ROOT)}: {line.strip()}"
        for sched in _SCHEDULERS
        for line in _executable_lines(sched)
        if "scripts/archived/" in line or any(name in line for name in archived)
    ]
    assert not hits, "a scheduler runs an archived script:\n" + "\n".join(hits)


# The argv HEAD, not a flag: `[kilo_path, "models", ...]` or `["kilo", "models", ...]` in any flag order,
# plus the shell form. Bounded to `.py`/`.sh` under `scripts/` outside the _SKIP_PARTS directories, so
# the `scripts/backups/*.bak` and `scripts/archive/*.backup.*` copies are out of reach on purpose.
_KILO_MODELS = re.compile(r"""(\bkilo\w*|["']kilo["'])\s*,\s*["']models["']|\bkilo\s+models\b""")


def _live_scripts() -> list[Path]:
    found = []
    for dirpath, dirnames, filenames in os.walk(_ROOT / "scripts"):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_PARTS]
        found.extend(Path(dirpath) / n for n in filenames if n.endswith((".py", ".sh")))
    return found


def test_no_live_script_runs_kilo_models() -> None:
    """Mail 01M4AR32: a `kilo models` call under a subprocess timeout orphans the `.kilo` node
    grandchild (the timeout kills only the launcher). Kilo is retired (D-102), so no script outside
    `archived/` may call it at all; the two retired callers live in `scripts/archived/`."""
    hits = [
        str(f.relative_to(_ROOT))
        for f in _live_scripts()
        if _KILO_MODELS.search(f.read_text(encoding="utf-8", errors="replace"))
    ]
    assert not hits, hits
    archived = _ROOT / "scripts" / "archived"
    assert (archived / "kilo_model_sync.py").is_file()
    assert (archived / "kilo_model_sync_startup.sh").is_file()
    assert not (_ROOT / "scripts" / "kilo_model_sync.py").exists()
    assert not (_ROOT / "scripts" / "kilo_model_sync_startup.sh").exists()


def test_liveness_registry_watches_no_retired_job() -> None:
    """A watched cron whose script is archived is an alarm on a log nobody writes any more."""
    import json

    reg = json.loads((_ROOT / ".fabrik" / "liveness-registry.json").read_text(encoding="utf-8"))
    archived = {p.name for p in (_ROOT / "scripts" / "archived").iterdir()}
    watched = [
        s.get("id")
        for s in reg["surfaces"]
        if isinstance(s, dict) and any(a in str(s.get("cron_match", "")) for a in archived)
    ]
    assert not watched, watched
