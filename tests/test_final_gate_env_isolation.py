# AFTER-EDIT: scripts/final_gate.py
"""The gate process's env must not inherit fabrik's import-time side effects.

Importing fabrik.spec_loader sets os.environ["DATABASE_URL"] via the settings chain;
run_cmd children inherited it, un-skipping env-keyed tests into a connect against the
leaked DSN — the gate's pytest red while the identical command passed standalone
(trade-intelligence, proven end-to-end 2026-08-16, finding 01M0CT0GDXWTB3Y6XXPVXJFN14).
Subprocess-based: the fabrik import is cached per process, so only a clean process can
observe the leak."""

import subprocess
import sys

PROBE_PREMISE = (
    "import os, sys; os.environ.pop('DATABASE_URL', None); sys.path.insert(0, 'src'); "
    "from fabrik.spec_loader import load_spec; print('DATABASE_URL' in os.environ)"
)
PROBE_HELPER = (
    "import os, sys; os.environ.pop('DATABASE_URL', None); sys.path.insert(0, 'scripts'); "
    "import final_gate; ls = final_gate._import_load_spec(); "
    "print(ls is not None, 'DATABASE_URL' in os.environ)"
)


def _run(code: str) -> str:
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       timeout=60, cwd="/opt/fabrik")
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_the_premise_the_bare_import_mutates_env():
    """If this ever goes False, the hub settings chain stopped mutating env at import and
    the isolation wrapper (while harmless) is no longer load-bearing — retire it then."""
    assert _run(PROBE_PREMISE) == "True"


def test_gate_helper_imports_without_leaking():
    out = _run(PROBE_HELPER)
    assert out == "True False", (
        f"helper result (imported, leaked) = {out!r} — load_spec must import AND the gate "
        "process env must stay clean for run_cmd children"
    )
