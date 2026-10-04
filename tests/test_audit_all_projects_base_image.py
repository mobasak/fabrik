"""W-f7882a97: the audit's base-image rule follows the fleet's pinned Debian codename.

`.windsurf/rules/versions.yaml`'s `debian_codename` is the one owner of the pin (D-064); the
audit read a hard-coded bookworm, so a Dockerfile built to the rule (trixie) read as critical
and every hint pointed back at bookworm.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "audit_all_projects.py"


def _audit_module():
    spec = importlib.util.spec_from_file_location("audit_all_projects_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def audit(tmp_path, monkeypatch):
    """The module with its codename source pointed at a throwaway versions.yaml."""
    mod = _audit_module()
    versions = tmp_path / "versions.yaml"
    versions.write_text('versions:\n  debian_codename: "trixie"\n', encoding="utf-8")
    monkeypatch.setattr(mod, "VERSIONS_FILE", versions)
    mod._pinned_codename.cache_clear()
    return mod


def _issues_for(mod, final: str):
    a = mod.ProjectAudit(name="p", path=Path("/nonexistent"))
    a.dockerfile_final_base = final
    a.dockerfile_from_lines = [final]
    a.dockerfile_has_healthcheck = True
    mod.build_issues(a)
    return [i for i in a.issues if "base" in i.title.lower()]


@pytest.mark.parametrize(
    "image",
    [
        "python:3.14-slim-trixie",
        "node:24-trixie-slim",
        "debian:trixie-slim",
        "python:3.14-slim-trixie AS app",
    ],
)
def test_pinned_codename_bases_are_compliant(audit, image):
    assert audit._is_base_compliant(image)
    assert _issues_for(audit, image) == []
    a = audit.ProjectAudit(name="p", path=Path("/nonexistent"))
    a.dockerfile_final_base = image
    audit.build_constraints(a)
    assert a.constraints["no_alpine"].startswith("✅")


@pytest.mark.parametrize("image", ["python:3.12-slim-bookworm", "node:22-bookworm-slim"])
def test_superseded_codename_is_medium_and_names_the_pin(audit, image):
    assert not audit._is_base_compliant(image)
    (issue,) = _issues_for(audit, image)
    assert issue.severity == "medium"
    assert "trixie" in issue.fix and "bookworm" not in issue.required


@pytest.mark.parametrize("image", ["python:3.14-alpine", "node:24", "ubuntu:24.04"])
def test_noncompliant_base_is_critical_and_hint_names_the_pin(audit, image):
    (issue,) = _issues_for(audit, image)
    assert issue.severity == "critical"
    assert "trixie" in issue.required + issue.fix
    assert "bookworm" not in issue.required + issue.fix


def test_codename_follows_versions_yaml(audit, tmp_path):
    flipped = tmp_path / "flipped.yaml"
    flipped.write_text('versions:\n  debian_codename: "forky"\n', encoding="utf-8")
    audit.VERSIONS_FILE = flipped
    audit._pinned_codename.cache_clear()
    assert audit._is_base_compliant("python:3.14-slim-forky")
    assert not audit._is_base_compliant("python:3.14-slim-trixie")


@pytest.mark.parametrize("content", [None, "versions:\n  python_stable: '3.14'\n"])
def test_unreadable_versions_yaml_exits(audit, tmp_path, content):
    broken = tmp_path / "broken.yaml"
    if content is not None:
        broken.write_text(content, encoding="utf-8")
    audit.VERSIONS_FILE = broken
    audit._pinned_codename.cache_clear()
    with pytest.raises(SystemExit) as exc:
        audit._is_base_compliant("python:3.14-slim-trixie")
    assert str(broken) in str(exc.value)


@pytest.mark.parametrize(
    "image", ["python:3.11-slim-bullseye", "debian:sid-slim", "node:18-buster-slim"]
)
def test_a_codename_d064_never_allowed_stays_critical(audit, image):
    """Only the codename D-064 retired is migration debt; one that was never compliant is not
    softened to medium."""
    (issue,) = _issues_for(audit, image)
    assert issue.severity == "critical"


@pytest.mark.parametrize(
    "image",
    [
        "python:3.14.0-slim-trixie",
        "node:24.1-trixie-slim",
        "python:3.14-slim-trixie@sha256:" + "a" * 64,
        "--platform=linux/amd64 python:3.14-slim-trixie",
    ],
)
def test_pinned_image_written_strictly_is_still_pinned(audit, image):
    assert audit._is_base_compliant(image)


def test_final_stage_from_an_earlier_alias_resolves_to_its_image(audit, tmp_path):
    (tmp_path / "Dockerfile").write_text(
        "FROM python:3.12-slim-bookworm AS builder\n"
        "FROM python:3.12-slim-bookworm AS runtime\n"
        "FROM runtime AS job\n",
        encoding="utf-8",
    )
    _, final, _ = audit.check_dockerfile_deep(tmp_path)
    assert audit._strip_as_alias(final) == "python:3.12-slim-bookworm"
    (issue,) = _issues_for(audit, final)
    assert issue.severity == "medium"


def test_a_versions_yaml_that_is_not_a_mapping_exits(audit, tmp_path):
    listed = tmp_path / "listed.yaml"
    listed.write_text("- trixie\n", encoding="utf-8")
    audit.VERSIONS_FILE = listed
    audit._pinned_codename.cache_clear()
    with pytest.raises(SystemExit):
        audit._is_base_compliant("python:3.14-slim-trixie")


def test_issues_are_ordered_critical_first(audit):
    a = audit.ProjectAudit(name="p", path=Path("/nonexistent"))
    a.dockerfile_final_base = "python:3.12-slim-bookworm"
    a.dockerfile_from_lines = [a.dockerfile_final_base]
    audit.build_issues(a)
    ranks = [audit._SEVERITY_RANK.get(i.severity, 9) for i in a.issues]
    assert ranks == sorted(ranks) and "medium" in [i.severity for i in a.issues]


def test_codename_reads_when_run_as_a_script_from_any_directory():
    """The script imports its sibling `sysadmin/rules_render_versions.py` by path, so the real
    invocation works from any working directory (a pytest import alone cannot show that)."""
    import subprocess

    code = f"import runpy; m = runpy.run_path({str(SCRIPT)!r}, run_name='audit'); print(m['_pinned_codename']())"
    r = subprocess.run(
        [sys.executable, "-c", code], cwd="/", capture_output=True, text=True, timeout=60
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip()


# ── review round 1 (W-f7882a97): the shapes 19 surviving mutants slipped through ─────────────


@pytest.mark.parametrize(
    ("image", "status"),
    [
        ("node:24-trixie-slim@sha256:" + "b" * 64, "pinned"),
        ("debian:trixie-slim@sha256:" + "c" * 64, "pinned"),
        ("python:3.14-slim-trixie@sha256:" + "a" * 63, "noncompliant"),  # a digest is 64 hex
        ("python:3.14-slim-trixie-extra", "noncompliant"),  # anchored at the end
        ("python:2.7-slim-trixie", "noncompliant"),  # the python shape is 3.x
        ("python:3.12-slim-bullseye", "noncompliant"),  # two releases back is not "superseded"
    ],
)
def test_shape_edges(audit, image, status):
    assert audit._base_status(image) == status


def test_superseded_is_the_release_just_before_the_pin(audit, tmp_path):
    flipped = tmp_path / "forky.yaml"
    flipped.write_text('versions:\n  debian_codename: "forky"\n', encoding="utf-8")
    audit.VERSIONS_FILE = flipped
    audit._pinned_codename.cache_clear()
    assert audit._base_status("python:3.14-slim-trixie") == "superseded"
    assert audit._base_status("python:3.12-slim-bookworm") == "noncompliant"


@pytest.mark.parametrize(
    "content",
    [
        "versions: [\n",  # not YAML
        "versions:\n  debian_codename:\n",  # null, which load_versions turns into "None"
        'versions:\n  debian_codename: "Trixie"\n',  # not a lowercase codename
        "versions:\n  debian_codename: 13\n",
        'versions:\n  debian_codename: "trixe"\n',  # a typo: not a known Debian release
        "versions:\n  debian_codename: none\n",
    ],
)
def test_an_unusable_codename_exits(audit, tmp_path, content):
    bad = tmp_path / "bad.yaml"
    bad.write_text(content, encoding="utf-8")
    audit.VERSIONS_FILE = bad
    audit._pinned_codename.cache_clear()
    with pytest.raises(SystemExit) as exc:
        audit._pinned_codename()
    assert str(bad) in str(exc.value)


def _final(audit, tmp_path, dockerfile: str) -> str:
    (tmp_path / "Dockerfile").write_text(dockerfile, encoding="utf-8")
    return audit.check_dockerfile_deep(tmp_path)[1]


def test_alias_resolution_follows_docker(audit, tmp_path):
    chain = (
        "FROM python:3.14-slim-trixie AS base\n"
        "FROM base as Builder\n"  # lowercase `as`, mixed-case name
        "FROM builder AS runtime\n"
        "FROM --platform=linux/amd64 runtime AS job\n"
    )
    assert _final(audit, tmp_path, chain) == "python:3.14-slim-trixie"
    later = (
        "FROM builder AS runtime\n"  # `builder` is not declared yet: a registry image
        "FROM python:3.12-slim-bookworm AS builder\n"
        "FROM runtime\n"
    )
    assert _final(audit, tmp_path, later) == "builder"
    split = "FROM node:24-alpine AS assets\nFROM python:3.14-slim-trixie\n"
    assert _final(audit, tmp_path, split) == "python:3.14-slim-trixie"  # the LAST stage
    mixed = "FROM python:3.14-slim-trixie AS Runtime\nFROM RUNTIME\n"
    assert _final(audit, tmp_path, mixed) == "python:3.14-slim-trixie"
    twice = "FROM python:3.14-slim-trixie AS app\nFROM alpine AS app\nFROM app\n"
    assert _final(audit, tmp_path, twice) == "python:3.14-slim-trixie"  # the first wins


def test_a_resolved_alias_is_labelled_as_resolved(audit, tmp_path):
    (tmp_path / "Dockerfile").write_text(
        "FROM python:3.12-slim-bookworm AS runtime\nFROM runtime AS job\n", encoding="utf-8"
    )
    lines, final, _ = audit.check_dockerfile_deep(tmp_path)
    a = audit.ProjectAudit(name="p", path=tmp_path)
    a.dockerfile_from_lines, a.dockerfile_final_base = lines, final
    audit.build_issues(a)
    (issue,) = [i for i in a.issues if "base" in i.title.lower()]
    assert "FROM runtime AS job" in issue.current
    assert "resolves to `python:3.12-slim-bookworm`" in issue.current
    assert "trixie" in issue.required and "bookworm" not in issue.required


def test_the_constraint_cell_and_stage_marks_name_the_verdict(audit):
    a = audit.ProjectAudit(name="p", path=Path("/nonexistent"))
    a.dockerfile_final_base = "python:3.12-slim-bookworm"
    a.dockerfile_from_lines = ["python:3.12-slim-bookworm", "python:3.14-slim-trixie AS x"]
    audit.build_constraints(a)
    cell = a.constraints["no_alpine"]
    assert cell.startswith("⚠️") and "move to `trixie` on the next rebuild" in cell
    audit.build_issues(a)
    md = audit.generate_research_md(a)
    assert "`FROM python:3.12-slim-bookworm` ⚠️" in md
    assert "`FROM python:3.14-slim-trixie AS x` ✅" in md


def test_an_unknown_severity_sorts_after_the_known_ones(audit):
    rows = [
        audit.Issue("other", "x", "f", "c", "r", "f"),
        audit.Issue("low", "l", "f", "c", "r", "f"),
        audit.Issue("critical", "c", "f", "c", "r", "f"),
    ]
    assert [i.severity for i in audit._by_severity(rows)] == ["critical", "low", "other"]


def test_main_stops_on_an_unusable_versions_yaml_before_reading_any_project(
    audit, tmp_path, monkeypatch
):
    """The early read in main(): a bad pin exits before the project loop writes any report."""
    bad = tmp_path / "bad.yaml"
    bad.write_text("versions:\n  python_stable: '3.14'\n", encoding="utf-8")
    audit.VERSIONS_FILE = bad
    audit._pinned_codename.cache_clear()
    touched: list[str] = []
    monkeypatch.setattr(audit, "audit_project", lambda *a, **k: touched.append("x"))
    monkeypatch.setattr(sys, "argv", ["audit_all_projects.py", "--dry-run"])
    with pytest.raises(SystemExit):
        audit.main()
    assert touched == []


@pytest.mark.parametrize("body", [None, "def broken(:\n", "import a_module_that_is_not_there\n"])
def test_an_unloadable_renderer_exits_naming_it(audit, tmp_path, monkeypatch, body):
    """Missing, unparsable, or with a failing import: each is the named SystemExit."""
    fake = tmp_path / "scripts" / "audit_all_projects.py"
    (fake.parent / "sysadmin").mkdir(parents=True)
    fake.write_text("", encoding="utf-8")
    if body is not None:
        (fake.parent / "sysadmin" / "rules_render_versions.py").write_text(body, encoding="utf-8")
    monkeypatch.setattr(audit, "__file__", str(fake))
    audit._pinned_codename.cache_clear()
    with pytest.raises(SystemExit) as exc:
        audit._pinned_codename()
    assert "rules_render_versions.py" in str(exc.value)


def test_the_oldest_release_has_no_superseded_one(audit, tmp_path):
    oldest = tmp_path / "oldest.yaml"
    oldest.write_text(
        f'versions:\n  debian_codename: "{audit._DEBIAN_RELEASES[0]}"\n', encoding="utf-8"
    )
    audit.VERSIONS_FILE = oldest
    audit._pinned_codename.cache_clear()
    assert audit._superseded_codename() is None


def test_a_missing_loader_file_exits_naming_it(audit, tmp_path, monkeypatch):
    """`spec_from_file_location` hands back a spec for a file that is not there; the failure
    comes at exec and must still be the named SystemExit, never a raw FileNotFoundError."""
    fake = tmp_path / "scripts" / "audit_all_projects.py"
    fake.parent.mkdir()
    fake.write_text("", encoding="utf-8")
    monkeypatch.setattr(audit, "__file__", str(fake))
    audit._pinned_codename.cache_clear()
    with pytest.raises(SystemExit) as exc:
        audit._pinned_codename()
    assert "rules_render_versions.py" in str(exc.value)


def test_the_empty_scaffold_return_is_ordered_too(audit):
    a = audit.ProjectAudit(name="p", path=Path("/nonexistent"))
    a.dockerfile_final_base = "python:3.12-slim-bookworm"
    a.dockerfile_from_lines = [a.dockerfile_final_base]
    a.dockerfile_has_healthcheck = True
    a.is_empty_scaffold = True
    a.status = "production"  # the empty-scaffold row is critical, emitted after the medium one
    audit.build_issues(a)
    assert [i.severity for i in a.issues][:2] == ["critical", "medium"]


def test_the_noncompliant_hint_names_the_image_it_replaces(audit):
    (issue,) = _issues_for(audit, "python:3.14-alpine")
    assert "`python:3.14-alpine`" in issue.fix


def test_a_stage_built_from_an_alias_is_marked_by_its_image(audit):
    a = audit.ProjectAudit(name="p", path=Path("/nonexistent"))
    a.dockerfile_from_lines = [
        "python:3.14-slim-trixie AS runtime",
        "--platform=linux/amd64 runtime AS job",
    ]
    a.dockerfile_final_base = "python:3.14-slim-trixie"
    audit.build_issues(a)
    md = audit.generate_research_md(a)
    assert "`FROM --platform=linux/amd64 runtime AS job` ✅" in md
