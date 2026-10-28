"""W-14832b2a — verify_prod_parity's ownership refusal had no test: with the uid guard disabled the
parity_root tests in test_scaffold_deploy_contract.py all stayed green. The staged copy is built by that
file's `_flat_stage`; the stub then runs with `os.geteuid` patched to a uid that does not own it."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.test_scaffold_deploy_contract import _flat_stage

_WRAPPER = (
    "import os, runpy, sys\n"
    "stub = sys.argv[1]\n"
    "owner = os.stat(stub).st_uid\n"
    "os.geteuid = lambda: owner + 1\n"
    "sys.argv = [stub, '--json']\n"
    "runpy.run_path(stub, run_name='__main__')\n"
)


def test_parity_refuses_a_staged_copy_not_owned_by_the_running_user(tmp_path: Path) -> None:
    stub = _flat_stage(tmp_path / "stage")
    cwd = tmp_path / "clone"
    cwd.mkdir()
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    r = subprocess.run(
        [sys.executable, "-c", _WRAPPER, str(stub)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    rows = json.loads(r.stdout)
    l0 = next(x for x in rows if x["system"] == "l0_health_probe_vendored")
    assert l0["match"] is None, l0
    assert "is not owned by this user" in str(l0["detail"]), l0
