"""Every file-worker healthcheck the hub emits reads the heartbeat's AGE (W-c384ff51, W-0bf1a37b).

Two emitters, four checks. `template_renderer.py` renders `templates/file-worker/{Dockerfile,compose.yaml}.j2`,
which ran `find /app/.tmp/worker_heartbeat -mmin -2` — a filter, not a test: it exits 0 on a heartbeat that
exists but is stale, so a hung worker stayed healthy. `fabrik scaffold --type file-worker` wrote
`pgrep -f "python worker/main.py"` into its Dockerfile and compose, and the slim image has no procps, so a
scaffolded worker was never healthy. All four now carry `scaffold.FILE_WORKER_HEARTBEAT_CHECK`: healthy only
when `/app/.tmp/worker_heartbeat` was written in the last 120 s, and never in the future.

This test PARSES each emitted check the way Docker and compose do and then EXECUTES it against a real
heartbeat file, because each failure mode is silent at the container: a Dockerfile `CMD [...]` that is not
valid JSON runs as shell form (never healthy), and compose interpolates `$` inside an exec-form `test:` list.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

from fabrik import scaffold
from fabrik.scaffold import FILE_WORKER_HEARTBEAT_CHECK, _write_canonical_compose, create_project
from fabrik.spec_loader import load_spec
from fabrik.template_renderer import TemplateRenderer

_ROOT = Path(__file__).resolve().parent.parent
_HEARTBEAT = "/app/.tmp/worker_heartbeat"


def _dockerfile_check(dockerfile: str) -> list[str]:
    """The HEALTHCHECK's CMD payload, joined across `\\` continuations, parsed as Docker's exec form."""
    text = dockerfile.replace("\\\n", " ")
    lines = [ln for ln in text.splitlines() if ln.startswith("HEALTHCHECK ")]
    assert len(lines) == 1, lines
    m = re.search(r"\sCMD\s+(.*)$", lines[0])
    assert m, lines[0]
    argv = json.loads(m.group(1))  # not JSON → Docker would silently run it through /bin/sh
    assert isinstance(argv, list) and all(isinstance(a, str) for a in argv), argv
    return argv


def _compose_check(compose: str) -> list[str]:
    services = yaml.safe_load(compose)["services"]
    tests = [svc["healthcheck"]["test"] for svc in services.values() if "healthcheck" in svc]
    assert len(tests) == 1, tests
    test = tests[0]
    assert isinstance(test, list) and test[0] == "CMD", test
    return test[1:]


def _scaffolded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    # pin the scaffold's template sources to this test's checkout
    monkeypatch.setattr(scaffold, "TEMPLATE_DIR", _ROOT / "templates" / "scaffold")
    monkeypatch.setattr(scaffold, "FILE_WORKER_TEMPLATE_DIR", _ROOT / "templates" / "file-worker")
    create_project(
        name="fw-hc", project_type="file-worker", description="healthcheck", base=tmp_path
    )
    project = tmp_path / "fw-hc"
    return {
        "scaffold-Dockerfile": _dockerfile_check((project / "Dockerfile").read_text()),
        "scaffold-compose": _compose_check((project / "compose.yaml").read_text()),
    }


def _rendered(tmp_path: Path) -> dict[str, list[str]]:
    spec_path = tmp_path / "fw-render.yaml"
    spec_path.write_text(
        yaml.safe_dump(
            {
                "id": "fw-render",
                "kind": "service",
                "template": "file-worker",
                "domain": "fw-render.vps1.ocoron.com",
                "source": {"type": "template"},
                "resources": {"memory": "256M", "cpu": "0.5"},
            }
        )
    )
    rendered = TemplateRenderer(
        templates_dir=_ROOT / "templates", output_dir=tmp_path / "out"
    ).render(load_spec(spec_path), dry_run=True)
    return {
        "j2-Dockerfile": _dockerfile_check(rendered["Dockerfile"]),
        "j2-compose": _compose_check(rendered["compose.yaml"]),
    }


@pytest.fixture
def checks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    return {**_scaffolded(tmp_path, monkeypatch), **_rendered(tmp_path)}


def test_the_four_emitted_checks_are_one_check(checks: dict[str, list[str]]) -> None:
    assert sorted(checks) == [
        "j2-Dockerfile",
        "j2-compose",
        "scaffold-Dockerfile",
        "scaffold-compose",
    ]
    for where, argv in checks.items():
        assert argv == ["python", "-c", FILE_WORKER_HEARTBEAT_CHECK], (where, argv)
    assert FILE_WORKER_HEARTBEAT_CHECK.count(_HEARTBEAT) == 1
    assert "$" not in FILE_WORKER_HEARTBEAT_CHECK  # compose would interpolate it inside `test:`


def test_no_emitted_check_runs_pgrep_or_find(checks: dict[str, list[str]]) -> None:
    for where, argv in checks.items():
        words = " ".join(argv)
        assert "pgrep" not in words and "find" not in words, (where, argv)


_AGES = {"fresh": 0.0, "stale": -180.0, "future": 600.0, "missing": None}
_EXPECT = {"fresh": 0, "stale": 1, "future": 1, "missing": 1}


@pytest.mark.parametrize("state", sorted(_AGES))
@pytest.mark.parametrize(
    "where", ["j2-Dockerfile", "j2-compose", "scaffold-Dockerfile", "scaffold-compose"]
)
def test_each_emitted_check_reads_the_heartbeat_age(
    where: str, state: str, checks: dict[str, list[str]], tmp_path: Path
) -> None:
    argv = checks[where]
    assert argv[:2] == ["python", "-c"], argv
    code = argv[2]
    assert code.count(_HEARTBEAT) == 1, code  # the rewrite below must not hide a wrong path
    beat = tmp_path / "hb" / ".tmp" / "worker_heartbeat"
    beat.parent.mkdir(parents=True)
    offset = _AGES[state]
    if offset is not None:
        beat.touch()
        when = time.time() + offset
        os.utime(beat, (when, when))
    r = subprocess.run(
        [sys.executable, "-c", code.replace(_HEARTBEAT, str(beat))],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert r.returncode == _EXPECT[state], (where, state, r.returncode, r.stderr[-500:])


def test_the_pgrep_kind_is_gone(tmp_path: Path) -> None:
    project = tmp_path / "w"
    project.mkdir()
    with pytest.raises(ValueError, match="healthcheck_kind"):
        _write_canonical_compose(project, "w", with_traefik=False, healthcheck_kind="process")


def test_a_drifted_dockerfile_healthcheck_fails_the_scaffold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `Dockerfile.python` whose HEALTHCHECK no longer matches would have kept the curl `/health` check,
    which a worker with no HTTP server can never pass; the scaffold now refuses instead."""
    tpl = tmp_path / "tpl"
    shutil.copytree(_ROOT / "templates" / "scaffold", tpl)
    src = (tpl / "docker" / "Dockerfile.python").read_text()
    drifted = src.replace("--start-period=10s", "--start-period=20s")
    assert drifted != src
    (tpl / "docker" / "Dockerfile.python").write_text(drifted)
    monkeypatch.setattr(scaffold, "TEMPLATE_DIR", tpl)
    monkeypatch.setattr(scaffold, "FILE_WORKER_TEMPLATE_DIR", _ROOT / "templates" / "file-worker")
    project = tmp_path / "fw-drift"
    project.mkdir()
    with pytest.raises(ValueError, match="HEALTHCHECK"):
        scaffold._scaffold_file_worker(project, "fw-drift", "drift")
