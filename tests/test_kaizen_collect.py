"""kaizen_collect v1 — the run-record closure metric reads the REAL field.

Run records (scripts/command_run.py) persist their lifecycle under ``state`` — the same
key the Stop hook blocks on. A metric reading any other key counts every in-flight run
as closed, which silently reports 100% closure forever.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "sysadmin"))

import kaizen_collect  # noqa: E402


def _write(d: Path, name: str, payload: dict) -> None:
    (d / name).write_text(json.dumps(payload), encoding="utf-8")


def test_running_record_counts_as_running(tmp_path):
    _write(tmp_path, "sid-a.json", {"state": "running", "command": "fabrik-probe"})
    _write(tmp_path, "sid-b.json", {"state": "done", "command": "fabrik-probe"})
    m = kaizen_collect.measure_run_records(tmp_path)
    assert m.value == "1/2 closed"
    assert "1 still marked running" in m.detail
