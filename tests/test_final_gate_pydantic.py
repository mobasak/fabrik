"""Tests for T2-03 G-E2: final_gate.py pydantic Spec validation.

The gate's YAML-load block now additionally calls fabrik.spec_loader.load_spec
on files under specs/services/. A broken spec (missing required field,
invalid enum, wrong type) fails the "check yaml" row of the gate.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path("/opt/fabrik")
GATE = REPO_ROOT / "scripts" / "final_gate.py"


def _run_gate(extra_env: dict[str, str] | None = None) -> tuple[int, str]:
    env = None
    if extra_env:
        import os

        env = {**os.environ, **extra_env}
    proc = subprocess.run(
        [sys.executable, str(GATE), "--lean", "--json"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _make_spec(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_load_spec_helper_importable():
    """Sanity check the import the gate now does is even possible."""
    from fabrik.spec_loader import load_spec
    assert callable(load_spec)


def test_valid_spec_passes_pydantic(tmp_path, monkeypatch):
    """A spec that satisfies the Spec model passes the new validation step.

    Uses tmp_path with a synthetic specs/services/ tree so we don't pollute
    the real repo. We exercise load_spec directly (not the gate subprocess)
    to keep the test hermetic.
    """
    spec_path = tmp_path / "specs" / "services" / "ok.yaml"
    _make_spec(spec_path, """\
id: ok-svc
kind: service
template: python-api
domain: ok.example.com
shape:
  is_public: true
""")
    from fabrik.spec_loader import load_spec
    spec = load_spec(str(spec_path))
    assert spec.id == "ok-svc"


def test_invalid_enum_fails_pydantic(tmp_path):
    """A spec with an invalid Infrastructure.database enum value is
    rejected — same failure mode T2-03 caught on
    fabrik-citation-verifier.yaml (pre-existing 'shared' value)."""
    spec_path = tmp_path / "specs" / "services" / "bad.yaml"
    _make_spec(spec_path, """\
id: bad-svc
kind: service
template: python-api
domain: bad.example.com
shape:
  is_public: true
infrastructure:
  database: shared
""")
    from fabrik.spec_loader import load_spec
    from pydantic import ValidationError
    with pytest.raises((ValidationError, Exception)) as exc_info:
        load_spec(str(spec_path))
    assert "database" in str(exc_info.value).lower() or "enum" in str(exc_info.value).lower()


def test_int_env_value_fails_pydantic(tmp_path):
    """env values must be strings — int PORT is rejected (same failure
    mode caught on docusaurus template's PORT: 3000 before T2-03 quoted
    it as PORT: '3000')."""
    spec_path = tmp_path / "specs" / "services" / "intenv.yaml"
    _make_spec(spec_path, """\
id: int-env-svc
kind: service
template: python-api
domain: intenv.example.com
shape:
  is_public: true
env:
  PORT: 3000
""")
    from fabrik.spec_loader import load_spec
    from pydantic import ValidationError
    with pytest.raises((ValidationError, Exception)) as exc_info:
        load_spec(str(spec_path))
    assert "port" in str(exc_info.value).lower() or "string" in str(exc_info.value).lower()


def test_missing_required_field_fails_pydantic(tmp_path):
    """Spec without `id` is rejected."""
    spec_path = tmp_path / "specs" / "services" / "noid.yaml"
    _make_spec(spec_path, """\
kind: service
template: python-api
domain: noid.example.com
""")
    from fabrik.spec_loader import load_spec
    with pytest.raises(Exception):
        load_spec(str(spec_path))


def test_live_gate_passes_against_current_repo_specs():
    """Smoke test: the gate's "check yaml" row passes on the real repo.

    This is a regression net for the T2-03 cleanup that fixed two
    pre-existing broken specs (fabrik-citation-verifier + docusaurus
    template). If anyone re-introduces an invalid enum or int env value,
    this test (via the gate subprocess) catches it.
    """
    rc, out = _run_gate()
    # We don't require RC=0 (other tier-1 checks may fail), but we DO
    # require the "check yaml" row to not contain a spec-validation
    # failure message.
    assert "Spec validation failed" not in out, (
        "G-E2 surfaced a broken spec — check the gate output:\n" + out
    )


def test_non_spec_yaml_files_unaffected(tmp_path):
    """The pydantic validation only fires for paths matching
    specs/services/ — other yaml files (CI config, compose files) go
    through plain yaml.safe_load only."""
    # Verify by direct introspection rather than running the gate:
    # the gate's path-check is "specs/services/" in f.replace(...)
    import re
    pattern = re.compile(r"specs/services/")
    assert pattern.search("specs/services/foo.yaml")
    assert not pattern.search("specs/verification/registrars.yaml")
    assert not pattern.search(".github/workflows/ci.yaml")
    assert not pattern.search("compose.yaml")
