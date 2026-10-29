"""Extra coverage for fabrik.deploy_validator — branches the base suite leaves unguarded."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from fabrik import deploy_validator as dv
from fabrik.deploy_validator import (
    ValidationResult,
    _check_dockerfile,
    _check_health_endpoint,
    _check_template_exists,
    format_warnings,
    validate,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class _FakeRenderer:
    def __init__(self, exists: bool, seen: list[str]):
        self._exists = exists
        self._seen = seen

    def template_exists(self, project_type: str) -> bool:
        self._seen.append(project_type)
        return self._exists


# --- ValidationResult -------------------------------------------------------


def test_validation_result_is_frozen():
    r = ValidationResult("c", True, "m")
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.passed = False  # type: ignore[misc]


def test_validation_result_equality():
    assert ValidationResult("c", True, "m") == ValidationResult("c", True, "m")
    assert ValidationResult("c", True, "m") != ValidationResult("c", False, "m")


# --- _check_template_exists -------------------------------------------------


def test_template_found_uses_renderer(monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(dv, "TemplateRenderer", lambda: _FakeRenderer(True, seen))
    r = _check_template_exists("python-api")
    assert r == ValidationResult("deploy_template", True, "Deploy template found: python-api")
    assert seen == ["python-api"]


def test_template_missing_reports_failure(monkeypatch):
    monkeypatch.setattr(dv, "TemplateRenderer", lambda: _FakeRenderer(False, []))
    r = _check_template_exists("weird")
    assert r.passed is False
    assert r.message == "No deploy template for type: weird"


def test_electron_type_never_consults_renderer(monkeypatch):
    def boom():
        raise AssertionError("renderer must not be built for desktop-app")

    monkeypatch.setattr(dv, "TemplateRenderer", boom)
    r = _check_template_exists("desktop-app")
    assert r.passed is True
    assert r.message.startswith("desktop-app:")


# --- _check_dockerfile ------------------------------------------------------


# Spelled out, never read from dv._NO_DOCKERFILE_TYPES: a parametrize over the module's own
# constant drops a case silently when a member is removed.
_EXPECTED_NO_DOCKERFILE = [
    "chrome-extension",
    "desktop-app",
    "docusaurus",
    "mobile-app",
    "static-site",
    "wordpress",
]


def test_dockerfile_exempt_set_is_exactly_the_expected_types():
    assert frozenset(_EXPECTED_NO_DOCKERFILE) == dv._NO_DOCKERFILE_TYPES


@pytest.mark.parametrize("ptype", _EXPECTED_NO_DOCKERFILE)
def test_dockerfile_exempt_types_pass_without_file(tmp_path, ptype):
    r = _check_dockerfile(tmp_path, ptype)
    assert r.passed is True
    assert r.message == f"N/A for {ptype} (no root Dockerfile expected)"


@pytest.mark.parametrize("ptype", ["python-api", "node-api", "file-worker", "saas-skeleton"])
def test_dockerfile_required_for_other_types(tmp_path, ptype):
    r = _check_dockerfile(tmp_path, ptype)
    assert r.passed is False
    assert "Dockerfile missing" in r.message


def test_dockerfile_present_message(tmp_path):
    _write(tmp_path / "Dockerfile", "FROM x\n")
    assert _check_dockerfile(tmp_path, "node-api").message == "Dockerfile present"


def test_dockerfile_other_name_not_accepted(tmp_path):
    _write(tmp_path / "Dockerfile.dev", "FROM x\n")
    assert _check_dockerfile(tmp_path, "python-api").passed is False


# --- _check_health_endpoint -------------------------------------------------


@pytest.mark.parametrize("ptype", ["docusaurus", "static-site"])
def test_health_static_types_message(tmp_path, ptype):
    r = _check_health_endpoint(tmp_path, ptype)
    assert r.passed is True
    assert "Static site" in r.message


def test_health_wordpress_message(tmp_path):
    r = _check_health_endpoint(tmp_path, "wordpress")
    assert r.passed is True
    assert "code lives outside src/" in r.message


def test_health_python_ignores_js_files(tmp_path):
    _write(tmp_path / "src" / "app.js", 'get("/health")')
    r = _check_health_endpoint(tmp_path, "python-api")
    assert r.passed is False
    assert r.message.startswith("Health endpoint not detected")


def test_health_node_ignores_python_files(tmp_path):
    _write(tmp_path / "src" / "app.py", '@app.get("/health")')
    assert _check_health_endpoint(tmp_path, "node-api").passed is False


def test_health_file_api_scans_nested_ts(tmp_path):
    _write(tmp_path / "src" / "deep" / "routes.ts", 'r.get("/health")')
    assert _check_health_endpoint(tmp_path, "file-api").passed is True


def test_health_found_in_nested_python(tmp_path):
    _write(tmp_path / "src" / "pkg" / "sub" / "api.py", 'route("/health")')
    assert _check_health_endpoint(tmp_path, "python-api").passed is True


def test_health_python_api_gpu_uses_src(tmp_path):
    _write(tmp_path / "src" / "m.py", 'get("/healthz")')  # contains "/health"
    assert _check_health_endpoint(tmp_path, "python-api-gpu").passed is True


def test_health_chrome_extension_ignores_root_src(tmp_path):
    _write(tmp_path / "src" / "m.py", 'get("/health")')
    r = _check_health_endpoint(tmp_path, "chrome-extension")
    assert r.passed is False
    assert "src/ directory not found" in r.message


def test_health_mobile_app_missing_server_dir(tmp_path):
    r = _check_health_endpoint(tmp_path, "mobile-app")
    assert r.passed is False
    assert r.message == "src/ directory not found"


def test_health_scanned_file_without_route_fails(tmp_path):
    _write(tmp_path / "src" / "app.py", '@app.get("/ready")')
    r = _check_health_endpoint(tmp_path, "python-api")
    assert r.passed is False
    assert r.message.startswith("Health endpoint not detected")


def test_health_src_dir_empty_fails(tmp_path):
    (tmp_path / "src").mkdir()
    r = _check_health_endpoint(tmp_path, "python-api")
    assert r.passed is False
    assert "not detected" in r.message


def test_health_skips_unreadable_file_and_continues(tmp_path, monkeypatch):
    bad = _write(tmp_path / "src" / "a_bad.py", 'get("/health")')
    good = _write(tmp_path / "src" / "b_good.py", 'get("/health")')
    real = Path.read_text
    real_rglob = Path.rglob
    read = []

    def flaky(self, *a, **kw):
        read.append(self)
        if self == bad:
            raise OSError("denied")
        return real(self, *a, **kw)

    def bad_first(self, pattern):
        # rglob's order is the filesystem's; pin the unreadable file first so the
        # `except OSError: continue` is what lets the good file be reached.
        if self == tmp_path / "src":
            return iter([bad, good])
        return real_rglob(self, pattern)

    monkeypatch.setattr(Path, "read_text", flaky)
    monkeypatch.setattr(Path, "rglob", bad_first)
    assert _check_health_endpoint(tmp_path, "python-api").passed is True
    assert read == [bad, good]


def test_health_only_unreadable_file_fails_without_raising(tmp_path, monkeypatch):
    _write(tmp_path / "src" / "a.py", 'get("/health")')

    def always(self, *a, **kw):
        raise OSError("denied")

    monkeypatch.setattr(Path, "read_text", always)
    assert _check_health_endpoint(tmp_path, "python-api").passed is False


def test_health_tolerates_non_utf8_bytes(tmp_path):
    p = tmp_path / "src" / "m.py"
    p.parent.mkdir()
    p.write_bytes(b"\xff\xfe junk /health \xff")
    assert _check_health_endpoint(tmp_path, "python-api").passed is True


def test_health_desktop_app_exempt_even_with_nothing_present(tmp_path):
    r = _check_health_endpoint(tmp_path, "desktop-app")
    assert r.passed is True


# --- validate ---------------------------------------------------------------


def test_validate_check_order_and_names(tmp_path, monkeypatch):
    monkeypatch.setattr(dv, "TemplateRenderer", lambda: _FakeRenderer(True, []))
    names = [r.check for r in validate(tmp_path, "python-api", specs_dir=tmp_path)]
    assert names == [
        "deploy_template",
        "env_example",
        "dockerfile",
        "health_endpoint",
        "spec_exists",
    ]


def test_validate_uses_project_dir_name_for_spec(tmp_path, monkeypatch):
    monkeypatch.setattr(dv, "TemplateRenderer", lambda: _FakeRenderer(True, []))
    proj = tmp_path / "my-proj"
    proj.mkdir()
    specs = tmp_path / "specs"
    _write(specs / "my-proj.yaml", "id: x\n")
    spec = validate(proj, "python-api", specs_dir=specs)[-1]
    assert "overwritten" in spec.message


def test_validate_default_specs_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(dv, "TemplateRenderer", lambda: _FakeRenderer(True, []))
    captured = {}

    def fake_spec(name, specs_dir):
        captured["args"] = (name, specs_dir)
        return ValidationResult("spec_exists", True, "x")

    monkeypatch.setattr(dv, "_check_spec_exists", fake_spec)
    validate(tmp_path / "proj", "python-api")
    assert captured["args"] == ("proj", Path("/opt/fabrik/specs/services"))


def test_validate_missing_template_flagged(tmp_path, monkeypatch):
    monkeypatch.setattr(dv, "TemplateRenderer", lambda: _FakeRenderer(False, []))
    failed = [r.check for r in validate(tmp_path, "python-api", specs_dir=tmp_path) if not r.passed]
    assert "deploy_template" in failed


def test_validate_desktop_app_bare_project(tmp_path):
    results = validate(tmp_path, "desktop-app", specs_dir=tmp_path)
    assert results[0].passed and results[2].passed and results[3].passed
    assert not results[1].passed  # .env.example still required


# --- format_warnings --------------------------------------------------------


def test_format_warnings_empty_input():
    assert format_warnings([]) == []


def test_format_warnings_exact_string_and_order():
    out = format_warnings(
        [
            ValidationResult("a", False, "first"),
            ValidationResult("b", True, "ok"),
            ValidationResult("c", False, "third"),
        ]
    )
    assert out == ["⚠️  [a] first", "⚠️  [c] third"]
