# AFTER-EDIT: scripts/enforcement/validate_conventions.py
"""Behaviour contract for the pending-activation downgrade in validate_conventions.

The one behaviour this file exists to pin: `_as_warnings` built `Severity.WARNING` on an enum
whose members are PASS / WARN / ERROR. That raises `AttributeError` the instant a result carries
`Severity.ERROR` — which is precisely when the downgrade has something to downgrade, i.e. the
first time the anti-sprawl check it guards actually fires. The mechanism was green only because
it had never had work to do. Found 2026-09-11 by mypy while reviewing a sibling file.
"""

import importlib.util
from pathlib import Path

REPO = Path("/opt/fabrik")


def _load():
    spec = importlib.util.spec_from_file_location(
        "validate_conventions", REPO / "scripts" / "enforcement" / "validate_conventions.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_as_warnings_downgrades_an_error_without_raising():
    m = _load()
    result = m.CheckResult(
        check_name="x", severity=m.Severity.ERROR, message="m", file_path=None, fix_hint=None
    )
    assert m._as_warnings([result])[0].severity is m.Severity.WARN


def test_every_severity_the_module_references_exists_on_the_enum():
    """The class, not the instance: any `Severity.<NAME>` in the source must be a real member."""
    import re

    m = _load()
    src = (REPO / "scripts" / "enforcement" / "validate_conventions.py").read_text(encoding="utf-8")
    referenced = set(re.findall(r"\bSeverity\.([A-Z_]+)\b", src))
    members = {s.name for s in m.Severity}
    assert referenced <= members, f"not on the enum: {sorted(referenced - members)}"
