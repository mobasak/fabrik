"""Coverage sweep for ``fabrik.dev_tools`` (hermetic: no network, docker or real git)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from fabrik import dev_tools


@pytest.fixture
def no_central(monkeypatch, tmp_path):
    """Point FABRIK_ROOT at an empty dir so the central spec fallback misses."""
    root = tmp_path / "fabrik-root"
    root.mkdir()
    monkeypatch.setattr(dev_tools, "FABRIK_ROOT", root)
    return root


@pytest.fixture
def proj(tmp_path):
    p = tmp_path / "myproj"
    p.mkdir()
    return p


def _fake_git(stdout: str):
    def run(args, **kwargs):
        assert args[:2] == ["git", "diff"]
        return SimpleNamespace(stdout=stdout, returncode=0)

    return run


# ---------------------------------------------------------------- find_spec


def test_find_spec_local_first_alphabetical(proj, no_central):
    d = proj / "specs" / "services"
    d.mkdir(parents=True)
    (d / "b.yaml").write_text("x: 1\n")
    (d / "a.yaml").write_text("x: 2\n")
    assert dev_tools.find_spec(proj) == d / "a.yaml"


def test_find_spec_local_beats_central(proj, no_central):
    d = proj / "specs" / "services"
    d.mkdir(parents=True)
    (d / "z.yaml").write_text("x: 1\n")
    central = no_central / "specs" / "services"
    central.mkdir(parents=True)
    (central / "myproj.yaml").write_text("x: 2\n")
    assert dev_tools.find_spec(proj) == d / "z.yaml"


def test_find_spec_central_fallback(proj, no_central):
    central = no_central / "specs" / "services"
    central.mkdir(parents=True)
    (central / "myproj.yaml").write_text("x: 2\n")
    assert dev_tools.find_spec(proj) == central / "myproj.yaml"


def test_find_spec_none(proj, no_central):
    assert dev_tools.find_spec(proj) is None


# ---------------------------------------------------------------- _git_diff


def test_git_diff_returns_stdout_and_passes_args(proj, monkeypatch):
    calls = {}

    def run(args, **kwargs):
        calls["args"] = args
        calls["kwargs"] = kwargs
        return SimpleNamespace(stdout="diff text\n")

    monkeypatch.setattr(dev_tools.subprocess, "run", run)
    assert dev_tools._git_diff(proj, "main") == "diff text\n"
    assert calls["args"] == ["git", "diff", "main"]
    assert calls["kwargs"]["cwd"] == str(proj)
    assert calls["kwargs"]["check"] is False


def test_git_diff_missing_git_binary(proj, monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(dev_tools.subprocess, "run", boom)
    assert dev_tools._git_diff(proj, "HEAD") == ""


# --------------------------------------------------------- build_review_bundle


def test_bundle_no_changes_no_spec_no_preplan(proj, monkeypatch):
    monkeypatch.setattr(dev_tools.subprocess, "run", _fake_git(""))
    body, stats = dev_tools.build_review_bundle(proj, "HEAD", None)
    assert "# Review bundle — myproj" in body
    assert "(no changes)" in body
    assert "`git diff HEAD`" in body
    assert "## Spec" not in body
    assert "## Preplan" not in body
    assert "## Resolved registrars" not in body
    assert body.endswith("\n")
    assert stats == dev_tools.ReviewBundleStats(0, 0, 0, 0, 0)


def test_bundle_whitespace_only_diff_is_no_changes(proj, monkeypatch):
    monkeypatch.setattr(dev_tools.subprocess, "run", _fake_git("  \n\n"))
    body, stats = dev_tools.build_review_bundle(proj, "HEAD", None)
    assert "(no changes)" in body
    assert stats.diff_lines == 2


def test_bundle_diff_lines_counted(proj, monkeypatch):
    monkeypatch.setattr(dev_tools.subprocess, "run", _fake_git("+a\n-b\n+c\n"))
    body, stats = dev_tools.build_review_bundle(proj, "v1", None)
    assert "```diff\n+a\n-b\n+c\n\n```" in body
    assert stats.diff_lines == 3


def test_bundle_includes_preplan(proj, monkeypatch):
    monkeypatch.setattr(dev_tools.subprocess, "run", _fake_git(""))
    (proj / "docs").mkdir()
    (proj / "docs" / "preplan.md").write_text("line1\nline2\n")
    body, stats = dev_tools.build_review_bundle(proj, "HEAD", None)
    assert "## Preplan (`docs/preplan.md`)\n\nline1\nline2\n" in body
    assert stats.preplan_lines == 2


def test_bundle_spec_relative_path_and_resolved_counts(proj, monkeypatch):
    monkeypatch.setattr(dev_tools.subprocess, "run", _fake_git(""))
    spec = proj / "specs" / "services" / "s.yaml"
    spec.parent.mkdir(parents=True)
    spec.write_text("name: s\nport: 1\n")

    seen = {}

    def fake_resolve(d):
        seen["spec"] = d
        return {"a": (True, "r1"), "b": (False, "r2"), "c": (True, "r3")}

    monkeypatch.setattr(dev_tools, "resolve_applicability", fake_resolve)
    monkeypatch.setattr(dev_tools, "format_resolved_summary", lambda r: f"SUMMARY{len(r)}")
    body, stats = dev_tools.build_review_bundle(proj, "HEAD", spec)
    assert seen["spec"] == {"name": "s", "port": 1}
    assert f"## Spec (`{Path('specs/services/s.yaml')}`)" in body
    assert "```yaml\nname: s\nport: 1\n\n```" in body
    assert "## Resolved registrars\n\n```\nSUMMARY3\n```" in body
    assert stats.spec_lines == 2
    assert (stats.registrars_run, stats.registrars_skipped) == (2, 1)


def test_bundle_spec_outside_project_uses_absolute_path(proj, tmp_path, monkeypatch):
    monkeypatch.setattr(dev_tools.subprocess, "run", _fake_git(""))
    spec = tmp_path / "elsewhere.yaml"
    spec.write_text("a: 1\n")
    monkeypatch.setattr(dev_tools, "resolve_applicability", lambda d: {})
    monkeypatch.setattr(dev_tools, "format_resolved_summary", lambda r: "")
    body, _ = dev_tools.build_review_bundle(proj, "HEAD", spec)
    assert f"## Spec (`{spec}`)" in body


def test_bundle_empty_yaml_resolves_empty_dict(proj, monkeypatch):
    monkeypatch.setattr(dev_tools.subprocess, "run", _fake_git(""))
    spec = proj / "e.yaml"
    spec.write_text("")
    seen = {}

    def fake_resolve(d):
        seen["d"] = d
        return {}

    monkeypatch.setattr(dev_tools, "resolve_applicability", fake_resolve)
    monkeypatch.setattr(dev_tools, "format_resolved_summary", lambda r: "")
    _, stats = dev_tools.build_review_bundle(proj, "HEAD", spec)
    assert seen["d"] == {}
    assert (stats.spec_lines, stats.registrars_run, stats.registrars_skipped) == (0, 0, 0)


def test_bundle_resolve_failure_is_reported_not_raised(proj, monkeypatch):
    monkeypatch.setattr(dev_tools.subprocess, "run", _fake_git(""))
    spec = proj / "s.yaml"
    spec.write_text("a: 1\n")

    def boom(d):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(dev_tools, "resolve_applicability", boom)
    body, stats = dev_tools.build_review_bundle(proj, "HEAD", spec)
    assert "_resolve failed: kaboom_" in body
    assert (stats.registrars_run, stats.registrars_skipped) == (0, 0)


def test_bundle_invalid_yaml_is_reported_not_raised(proj, monkeypatch):
    monkeypatch.setattr(dev_tools.subprocess, "run", _fake_git(""))
    spec = proj / "bad.yaml"
    spec.write_text("a: [unclosed\n")
    body, stats = dev_tools.build_review_bundle(proj, "HEAD", spec)
    assert "_resolve failed:" in body
    assert "## Spec" in body
    assert stats.spec_lines == 1


def test_bundle_missing_spec_path_is_ignored(proj, monkeypatch):
    monkeypatch.setattr(dev_tools.subprocess, "run", _fake_git(""))
    body, stats = dev_tools.build_review_bundle(proj, "HEAD", proj / "nope.yaml")
    assert "## Spec" not in body
    assert stats.spec_lines == 0


def test_bundle_section_order(proj, monkeypatch):
    monkeypatch.setattr(dev_tools.subprocess, "run", _fake_git("+x\n"))
    (proj / "docs").mkdir()
    (proj / "docs" / "preplan.md").write_text("plan\n")
    spec = proj / "s.yaml"
    spec.write_text("a: 1\n")
    monkeypatch.setattr(dev_tools, "resolve_applicability", lambda d: {})
    monkeypatch.setattr(dev_tools, "format_resolved_summary", lambda r: "")
    body, _ = dev_tools.build_review_bundle(proj, "HEAD", spec)
    order = [
        body.index(h)
        for h in ("# Review bundle", "## Diff", "## Spec", "## Preplan", "## Resolved")
    ]
    assert order == sorted(order)


def test_bundle_real_resolver_smoke(proj, monkeypatch):
    """Unmocked resolver: bundle builds and never raises on a plain spec."""
    monkeypatch.setattr(dev_tools.subprocess, "run", _fake_git(""))
    spec = proj / "s.yaml"
    spec.write_text("name: demo\n")
    body, stats = dev_tools.build_review_bundle(proj, "HEAD", spec)
    assert "## Resolved registrars" in body
    # The except branch writes the same heading, so the resolver's success is what proves it ran.
    assert "_resolve failed" not in body
    assert stats.registrars_run + stats.registrars_skipped > 0


# ---------------------------------------------------------- save_review_bundle


def test_save_explicit_out_creates_parents(proj, tmp_path):
    out = tmp_path / "deep" / "er" / "b.md"
    assert dev_tools.save_review_bundle(proj, "hello", out=out) == out
    assert out.read_text() == "hello"
    assert not (proj / dev_tools.REVIEW_DIR).exists()


def test_save_default_location_timestamped(proj):
    target = dev_tools.save_review_bundle(proj, "# c")
    assert target.parent == proj / ".fabrik" / "review"
    assert target.suffix == ".md"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{6}", target.stem)
    assert target.read_text() == "# c"


def test_save_default_utf8(proj):
    target = dev_tools.save_review_bundle(proj, "—é")
    assert target.read_bytes() == "—é".encode()


# ------------------------------------------------------------ _has_dev_compose


def test_has_dev_compose(proj):
    assert dev_tools._has_dev_compose(proj) is None
    (proj / "compose.dev.yaml").write_text("services: {}\n")
    assert dev_tools._has_dev_compose(proj) == proj / "compose.dev.yaml"


# -------------------------------------------------------------- run_dev_compose


def test_dev_compose_missing_returns_minus_one_without_running(proj):
    runner = MagicMock()
    assert dev_tools.run_dev_compose(proj, detach=False, runner=runner) == -1
    runner.assert_not_called()


@pytest.mark.parametrize("detach", [False, True])
def test_dev_compose_args(proj, detach):
    (proj / "compose.dev.yaml").write_text("services: {}\n")
    runner = MagicMock(return_value=SimpleNamespace(returncode=0))
    assert dev_tools.run_dev_compose(proj, detach=detach, runner=runner) == 0
    args = runner.call_args.args[0]
    expect = ["docker", "compose", "-f", str(proj / "compose.dev.yaml"), "up"]
    assert args == expect + (["-d"] if detach else [])
    assert runner.call_args.kwargs == {"cwd": str(proj), "check": False}


def test_dev_compose_propagates_exit_code(proj):
    (proj / "compose.dev.yaml").write_text("services: {}\n")
    runner = MagicMock(return_value=SimpleNamespace(returncode=17))
    assert dev_tools.run_dev_compose(proj, detach=False, runner=runner) == 17


def test_dev_compose_default_runner_is_subprocess_run():
    assert dev_tools.run_dev_compose.__defaults__[0] is subprocess.run


# --------------------------------------------------------------- run_local_logs


def test_local_logs_missing_returns_minus_one(proj):
    runner = MagicMock()
    assert dev_tools.run_local_logs(proj, None, False, runner=runner) == -1
    runner.assert_not_called()


@pytest.mark.parametrize(
    ("service", "follow", "tail"),
    [
        (None, False, []),
        (None, True, ["-f"]),
        ("api", False, ["api"]),
        ("api", True, ["-f", "api"]),
        ("", False, []),
    ],
)
def test_local_logs_args(proj, service, follow, tail):
    (proj / "compose.dev.yaml").write_text("services: {}\n")
    runner = MagicMock(return_value=SimpleNamespace(returncode=3))
    assert dev_tools.run_local_logs(proj, service, follow, runner=runner) == 3
    base = ["docker", "compose", "-f", str(proj / "compose.dev.yaml"), "logs"]
    assert runner.call_args.args[0] == base + tail
    assert runner.call_args.kwargs == {"cwd": str(proj), "check": False}
