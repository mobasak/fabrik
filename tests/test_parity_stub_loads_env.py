"""The scaffold's parity stub loads the project `.env` once it imports the vendored health_probe.

fabrik-lib cfd9215f stopped `health_probe` loading `.env` at import (an explicit `load_env()` now).
Parity rows that read os.environ after the stub's lazy import relied on that load, so the stub calls
`load_env()` itself, once, with a real variable still winning (the 714dbf90e re-vendor review).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

_PROBE = """
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("stub", sys.argv[1])
stub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stub)
assert stub._health_probe() is not None
stub._health_probe()
print(os.environ.get("ZZ_PARITY_FROM_DOTENV"), os.environ.get("ZZ_PARITY_REAL"), stub._ENV_LOADED)
"""


def _project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    (proj / "scripts").mkdir(parents=True)
    shutil.copy(REPO / "templates/scaffold/scripts/verify_prod_parity.py", proj / "scripts")
    shutil.copytree(
        REPO / "libs/health_probe",
        proj / "libs/health_probe",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (proj / ".env").write_text("ZZ_PARITY_FROM_DOTENV=loaded\nZZ_PARITY_REAL=from-dotenv\n")
    return proj


# Counts at python-dotenv, the seam every copy of `health_probe.load_env` reaches whenever
# python-dotenv is installed (a declared dependency; `load_env` imports `load_dotenv` at call
# time, and without it this probe fails loudly at `import dotenv`, never passes). The stub loads
# its copy BY FILE PATH as `_parity_health_probe` (D-744), so patching
# `libs.health_probe.health_probe` counted a module the stub never calls — 0.
_COUNTING = """
import importlib.util, os, sys
import dotenv
calls = []
real = dotenv.load_dotenv
dotenv.load_dotenv = lambda *a, **k: (calls.append(a), real(*a, **k))[1]
spec = importlib.util.spec_from_file_location("stub", sys.argv[1])
stub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stub)
stub._health_probe(); stub._health_probe(); stub._health_probe()
print(len(calls), stub._ENV_LOADED)
"""


def _run(code: str, proj: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", code, str(proj / "scripts" / "verify_prod_parity.py"), *extra],
        cwd=proj.parent,
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=True,
    )


def test_three_rows_load_the_env_exactly_once(tmp_path):
    proj = _project(tmp_path)
    assert _run(_COUNTING, proj, str(proj)).stdout.split() == ["1", "True"]


def test_a_project_without_a_dotenv_loads_nothing_and_says_nothing(tmp_path):
    proj = _project(tmp_path)
    (proj / ".env").unlink()
    r = _run(_COUNTING, proj, str(proj))
    assert r.stdout.split() == ["0", "False"] and r.stderr == ""


def test_a_broken_dotenv_is_reported_and_the_rows_carry_on(tmp_path):
    proj = _project(tmp_path)
    (proj / ".env").write_bytes(b"ZZ_BAD=\xff\xfe\n")
    r = _run(_PROBE, proj)
    assert "verify_prod_parity: .env not loaded (UnicodeDecodeError" in r.stderr, r.stderr
    assert "0xff" not in r.stderr, r.stderr  # the reason only, never the byte from the file


def test_a_nul_byte_in_the_dotenv_is_reported_and_the_rows_carry_on(tmp_path):
    """os.environ refuses a value holding a NUL byte with ValueError, which used to escape the
    stub and stop the whole parity run (tryton-crm 01M44BTHQQZ8, web-ecommerce-factory 01M44D5FP670)."""
    proj = _project(tmp_path)
    (proj / ".env").write_bytes(b"ZZ_PARITY_FROM_DOTENV=above\nZZ_PARITY_REAL=a\x00b\n")
    r = _run(_PROBE, proj)
    assert "verify_prod_parity: .env only partly loaded (ValueError" in r.stderr, r.stderr
    # the message names exactly the keys that reached os.environ
    assert "set before the error: ZZ_PARITY_FROM_DOTENV\n" in r.stderr, r.stderr
    assert r.stdout.split() == ["above", "None", "True"], r.stdout


def test_a_nul_byte_on_the_first_line_is_reported_as_not_loaded(tmp_path):
    """Nothing reached os.environ, so the stub must not claim a partial load."""
    proj = _project(tmp_path)
    (proj / ".env").write_bytes(b"ZZ_PARITY_REAL=a\x00b\nZZ_PARITY_FROM_DOTENV=below\n")
    r = _run(_PROBE, proj)
    assert "verify_prod_parity: .env not loaded (ValueError" in r.stderr, r.stderr
    assert "set before the error: none" in r.stderr, r.stderr
    assert r.stdout.split() == ["None", "None", "True"], r.stdout


def test_a_value_os_environ_cannot_encode_is_reported_without_the_value(tmp_path):
    """Under a non-UTF-8 locale os.environ raises UnicodeEncodeError (a ValueError) whose text
    quotes a character of the value; the stub prints the reason and the key names only."""
    proj = _project(tmp_path)
    (proj / ".env").write_bytes(
        "ZZ_PARITY_FROM_DOTENV=above\nZZ_PARITY_REAL=secretcaf\u00e9\n".encode()
    )
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"}
    r = subprocess.run(
        [sys.executable, "-c", _PROBE, str(proj / "scripts" / "verify_prod_parity.py")],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "only partly loaded (UnicodeEncodeError" in r.stderr, r.stderr
    assert "set before the error: ZZ_PARITY_FROM_DOTENV" in r.stderr, r.stderr
    assert "xe9" not in r.stderr and "\u00e9" not in r.stderr, r.stderr


def test_a_dotenv_that_loads_nothing_is_reported(tmp_path):
    """load_env() returns False for a file that sets no variable (or without python-dotenv): the
    rows then read only the real environment, and the operator is told."""
    proj = _project(tmp_path)
    (proj / ".env").write_text("# nothing set here\n")
    r = _run(_COUNTING, proj, str(proj))
    assert r.stdout.split() == ["1", "True"], r.stdout
    assert "verify_prod_parity: .env loaded nothing" in r.stderr, r.stderr


def test_a_disabled_dotenv_is_reported_as_the_third_cause(tmp_path):
    """python-dotenv 1.2 returns False from load_dotenv when PYTHON_DOTENV_DISABLED is truthy, so a
    REAL .env loads nothing and the message must name that cause beside the other two (infra
    01M4V9BKHB) — otherwise the operator hunts a missing package that is installed. The control run
    (same project, no switch) loads both variables and prints no message, so the switch is the cause."""
    import re
    from importlib.metadata import version

    # the switch landed in 1.2.0 while pyproject allows >=1.0.0; a pre-release or odd string ("1.2rc1",
    # "2") never crashes the parse — an unparsable version runs the test rather than skipping it
    m = re.match(r"(\d+)\.(\d+)", version("python-dotenv"))
    if m and (int(m.group(1)), int(m.group(2))) < (1, 2):
        pytest.skip("PYTHON_DOTENV_DISABLED needs python-dotenv >= 1.2")
    proj = _project(tmp_path)  # a .env that DOES set two variables

    def run(env):
        return subprocess.run(
            [sys.executable, "-c", _PROBE, str(proj / "scripts" / "verify_prod_parity.py")],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )

    control = run({"PATH": "/usr/bin:/bin"})
    assert control.stdout.split() == ["loaded", "from-dotenv", "True"], control.stdout
    assert "loaded nothing" not in control.stderr, control.stderr
    disabled = run({"PATH": "/usr/bin:/bin", "PYTHON_DOTENV_DISABLED": "1"})
    assert disabled.stdout.split() == ["None", "None", "True"], (
        disabled.stdout
    )  # nothing reached os.environ
    assert "verify_prod_parity: .env loaded nothing" in disabled.stderr, disabled.stderr
    assert "PYTHON_DOTENV_DISABLED is truthy" in disabled.stderr, disabled.stderr
    # a set-but-falsy value does not disable loading — python-dotenv reads 1/true/t/yes/y only
    falsy = run({"PATH": "/usr/bin:/bin", "PYTHON_DOTENV_DISABLED": "0"})
    assert falsy.stdout.split() == ["loaded", "from-dotenv", "True"], falsy.stdout


def test_the_stub_loads_the_project_env_once_and_a_real_variable_wins(tmp_path):
    proj = _project(tmp_path)
    env = {"PATH": "/usr/bin:/bin", "ZZ_PARITY_REAL": "from-environment"}
    out = subprocess.run(
        [sys.executable, "-c", _PROBE, str(proj / "scripts" / "verify_prod_parity.py")],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert out == ["loaded", "from-environment", "True"], out
