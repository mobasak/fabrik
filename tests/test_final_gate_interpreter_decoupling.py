"""The gate's interpreter must not be hostage to where ruff lives.

transdoc 01M171R8 (2026-08-29, reproduced on pristine HEAD): `PYTHON` selected the venv
only if `.venv/bin/ruff` ALSO existed, so on a box with a single global ruff the whole
test suite ran under `sys.executable` — collected fine, then died (or half-passed) on
application imports that interpreter never had. The venv owns the APPLICATION's
dependencies; ruff is resolved separately (venv → PATH) and invoked as a binary.
Fleet blast radius measured before landing: 3 repos (transdoc fixed; candle/proxy go
SETUP-loud via the toolchain probe, which is the designed outcome for an unprovisioned
venv).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE = REPO / "scripts" / "final_gate.py"


def _constants_under(fake_root: Path) -> tuple[str, str]:
    """Import the gate with cwd=fake_root and return (PYTHON, RUFF)."""
    code = (
        "import sys, json; sys.path.insert(0, %r); import final_gate as g; "
        "print(json.dumps([g.PYTHON, getattr(g, 'RUFF', '')]))" % str(GATE.parent)
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        cwd=fake_root,
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "CLAUDE_MESH_HEADLESS": "1"},
    )
    assert r.returncode == 0, r.stderr[-500:]
    py, ruff = json.loads(r.stdout.strip().splitlines()[-1])
    return py, ruff


def test_venv_python_is_selected_even_without_a_venv_ruff(tmp_path):
    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").symlink_to(sys.executable)
    # deliberately NO .venv/bin/ruff — the transdoc box shape
    py, ruff = _constants_under(tmp_path)
    assert py.endswith(".venv/bin/python"), (
        f"the venv owns the app deps; got {py} (the ruff-coupled fallback)"
    )
    assert ruff, "RUFF must resolve separately (venv -> PATH), never disappear"


def test_a_venv_ruff_still_wins_when_present(tmp_path):
    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").symlink_to(sys.executable)
    (venv_bin / "ruff").symlink_to(sys.executable)  # existence is what's probed
    py, ruff = _constants_under(tmp_path)
    assert py.endswith(".venv/bin/python")
    assert ruff.endswith(".venv/bin/ruff")


def test_no_ruff_leg_runs_through_the_interpreter():
    """The decoupling is only real if no call site still does `PYTHON -m ruff` — that
    form re-couples the two the moment a venv lacks the ruff MODULE."""
    src = GATE.read_text(encoding="utf-8")
    assert '"-m", "ruff"' not in src, "a ruff leg still runs through the interpreter"
