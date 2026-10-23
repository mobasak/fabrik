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
import shlex
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
    dockerfile = (project / "Dockerfile").read_text()
    # /app is the project root the worker beats under (worker/main.py: <root>/.tmp/worker_heartbeat)
    assert "WORKDIR /app\n" in dockerfile and "COPY . .\n" in dockerfile
    # the template's HTTP comments went with its HTTP check
    assert "/health" not in dockerfile and "customize port and endpoint" not in dockerfile
    return {
        "scaffold-Dockerfile": _dockerfile_check(dockerfile),
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


# Seconds added to "now" for the heartbeat's mtime. The 115/125 pair brackets the 120 s window (an exact
# 120 is not testable against a moving clock); a 30 s or a 300 s window fails one of them.
_AGES = {
    "fresh": 0.0,
    "fresh-115s": -115.0,
    "stale-125s": -125.0,
    "stale": -180.0,
    "future": 600.0,
    "missing": None,
}
_EXPECT = {"fresh": 0, "fresh-115s": 0, "stale-125s": 1, "stale": 1, "future": 1, "missing": 1}


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


@pytest.mark.parametrize("drift, found", [("start-period", 0), ("doubled", 2)])
def test_a_drifted_dockerfile_healthcheck_fails_the_scaffold(
    drift: str, found: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `Dockerfile.python` whose HEALTHCHECK no longer matches would have kept the curl `/health` check,
    which a worker with no HTTP server can never pass, and one with two would have shipped two; the
    scaffold refuses both."""
    tpl = tmp_path / "tpl"
    shutil.copytree(_ROOT / "templates" / "scaffold", tpl)
    src = (tpl / "docker" / "Dockerfile.python").read_text()
    m = re.search(r"(?m)^HEALTHCHECK .*\\\n.*\n", src)
    assert m, "the template's HEALTHCHECK moved"
    if drift == "start-period":
        drifted = src.replace("--start-period=10s", "--start-period=20s")
    else:
        drifted = src.replace(m.group(0), m.group(0) + m.group(0))
    assert drifted != src
    (tpl / "docker" / "Dockerfile.python").write_text(drifted)
    monkeypatch.setattr(scaffold, "TEMPLATE_DIR", tpl)
    monkeypatch.setattr(scaffold, "FILE_WORKER_TEMPLATE_DIR", _ROOT / "templates" / "file-worker")
    project = tmp_path / "fw-drift"
    project.mkdir()
    with pytest.raises(ValueError, match=rf"expected one HTTP HEALTHCHECK .* found {found}$"):
        scaffold._scaffold_file_worker(project, "fw-drift", "drift")
    assert not (project / "Dockerfile").exists()  # refused before anything was written


# W-881752ec: a file-worker's `make docker-smoke` curled /health, which it never serves, so the smoke test always
# printed "Health FAILED"; it now runs FILE_WORKER_HEARTBEAT_CHECK inside the smoke container.
def _smoke_recipe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    monkeypatch.setattr(scaffold, "TEMPLATE_DIR", _ROOT / "templates" / "scaffold")
    monkeypatch.setattr(scaffold, "FILE_WORKER_TEMPLATE_DIR", _ROOT / "templates" / "file-worker")
    create_project(name="fw-smoke", project_type="file-worker", description="smoke", base=tmp_path)
    project = tmp_path / "fw-smoke"
    makefile = (project / "Makefile").read_text()
    start = makefile.index("docker-smoke:")
    return project, makefile[start : makefile.index("\n\n", start)]


_SMOKE_EXEC = f'docker exec $(PROJECT_NAME)-smoke python -c "{FILE_WORKER_HEARTBEAT_CHECK}"'


def test_the_smoke_target_runs_the_heartbeat_check_not_a_curl(tmp_path, monkeypatch):
    project, recipe = _smoke_recipe(tmp_path, monkeypatch)
    assert "curl" not in recipe and "/health" not in recipe, recipe
    assert "-p $(PORT)" not in recipe, recipe  # a worker publishes nothing
    # its own container name: another project's smoke run may hold the template's shared `smoke-test`
    assert "smoke-test" not in (project / "Makefile").read_text()
    lines = recipe.splitlines()
    rm = lines.index("\t@docker rm -f $(PROJECT_NAME)-smoke >/dev/null 2>&1 || true")
    run = lines.index(
        "\t@docker run -d --name $(PROJECT_NAME)-smoke --network none -e WORKER_SMOKE=1"
        " --env-file .env $(PROJECT_NAME) || true"
    )
    assert rm < run, recipe  # a leftover container is never the one judged
    wait = f"\t@for i in 1 2 3 4 5 6 7 8 9 10; do {_SMOKE_EXEC} >/dev/null 2>&1 && break; sleep 1; done"
    verdict = f'\t@{_SMOKE_EXEC} && echo " ✓ Health OK" || echo " ✗ Health FAILED"'
    assert run < lines.index(wait) < lines.index(verdict), recipe


def test_make_hands_the_smoke_check_to_python_intact(tmp_path, monkeypatch):
    if shutil.which("make") is None:
        pytest.skip("GNU make is not on PATH")
    project, _ = _smoke_recipe(tmp_path, monkeypatch)
    out = subprocess.run(
        ["make", "-n", "-C", str(project), "docker-smoke"],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout
    checks = []
    for line in out.splitlines():
        argv = shlex.split(line) if "docker exec fw-smoke-smoke python -c" in line else []
        checks += [
            argv[i + 1] for i, word in enumerate(argv) if word == "-c" and argv[i - 1] == "python"
        ]
    assert len(checks) == 2, out  # the bounded wait and the verdict
    assert all(c == FILE_WORKER_HEARTBEAT_CHECK for c in checks), checks


@pytest.mark.parametrize("line", ["curl", "run", "spaced-target"])
def test_a_drifted_smoke_target_fails_the_scaffold(line, tmp_path, monkeypatch):
    """A drifted smoke line is refused — under any legal spelling of the target, `docker-smoke :` included."""
    tpl = tmp_path / "tpl"
    shutil.copytree(_ROOT / "templates" / "scaffold", tpl)
    mk = tpl / "docker" / "Makefile.python"
    src = mk.read_text()
    old = "docker run -d --name smoke-test -p" if line == "run" else "curl -sf http://localhost"
    assert old in src
    drifted = src.replace(old, old.replace("-", "--", 1))
    if line == "spaced-target":
        assert "\ndocker-smoke: docker-build" in drifted
        drifted = drifted.replace("\ndocker-smoke: docker-build", "\ndocker-smoke : docker-build")
    mk.write_text(drifted)
    monkeypatch.setattr(scaffold, "TEMPLATE_DIR", tpl)
    monkeypatch.setattr(scaffold, "FILE_WORKER_TEMPLATE_DIR", _ROOT / "templates" / "file-worker")
    project = tmp_path / "fw-drift"
    project.mkdir()
    with pytest.raises(ValueError, match="docker-smoke"):
        scaffold._scaffold_file_worker(project, "fw-drift", "drift")


@pytest.mark.parametrize(
    "header",
    [
        "docker-smoke docker-x: docker-build",
        "docker-smoke &: docker-build",
        " docker-smoke: docker-build",
    ],
    ids=["multi-target", "grouped", "leading-space"],
)
def test_a_smoke_rule_the_regex_cannot_read_still_loses_the_live_worker_line(
    header, tmp_path, monkeypatch
):
    """A rule header the guard's regex misses must not leave the template's live-worker run line (W-807b73fd)."""
    tpl = tmp_path / "tpl"
    shutil.copytree(_ROOT / "templates" / "scaffold", tpl)
    mk = tpl / "docker" / "Makefile.python"
    src = mk.read_text()
    assert "\ndocker-smoke: docker-build" in src
    mk.write_text(src.replace("\ndocker-smoke: docker-build", "\n" + header))
    monkeypatch.setattr(scaffold, "TEMPLATE_DIR", tpl)
    monkeypatch.setattr(scaffold, "FILE_WORKER_TEMPLATE_DIR", _ROOT / "templates" / "file-worker")
    project = tmp_path / "fw-header"
    project.mkdir()
    scaffold._scaffold_file_worker(project, "fw-header", "header")
    makefile = (project / "Makefile").read_text()
    runs = [ln for ln in makefile.splitlines() if "docker run" in ln]
    assert runs == [
        "\t@docker run -d --name $(PROJECT_NAME)-smoke --network none -e WORKER_SMOKE=1 --env-file .env $(PROJECT_NAME) || true"
    ], runs


def test_an_unreadable_header_with_both_smoke_lines_drifted_fails_the_scaffold(
    tmp_path, monkeypatch
):
    """Neither the header regex nor the exact smoke lines see this template; the live run line must still be refused."""
    tpl = tmp_path / "tpl"
    shutil.copytree(_ROOT / "templates" / "scaffold", tpl)
    mk = tpl / "docker" / "Makefile.python"
    src = mk.read_text()
    for old, new in [
        ("\ndocker-smoke: docker-build", "\n docker-smoke: docker-build"),
        ("--env-file .env $(PROJECT_NAME)", "--env-file .env  $(PROJECT_NAME)"),
        ("curl -sf", "curl -fs"),
    ]:
        assert src.count(old) == 1, old
        src = src.replace(old, new)
    mk.write_text(src)
    monkeypatch.setattr(scaffold, "TEMPLATE_DIR", tpl)
    monkeypatch.setattr(scaffold, "FILE_WORKER_TEMPLATE_DIR", _ROOT / "templates" / "file-worker")
    project = tmp_path / "fw-double-drift"
    project.mkdir()
    with pytest.raises(ValueError, match="live worker"):
        scaffold._scaffold_file_worker(project, "fw-double-drift", "drift")


def test_a_project_named_like_the_smoke_container_keeps_a_loadable_makefile(tmp_path, monkeypatch):
    """The `smoke-test` rename ran after the name went in, so `x9-smoke-test` got
    `PROJECT_NAME ?= x9-$(PROJECT_NAME)-smoke`, which make refuses to load."""
    monkeypatch.setattr(scaffold, "TEMPLATE_DIR", _ROOT / "templates" / "scaffold")
    monkeypatch.setattr(scaffold, "FILE_WORKER_TEMPLATE_DIR", _ROOT / "templates" / "file-worker")
    create_project(
        name="x9-smoke-test", project_type="file-worker", description="smoke", base=tmp_path
    )
    project = tmp_path / "x9-smoke-test"
    makefile = (project / "Makefile").read_text()
    assert "PROJECT_NAME ?= x9-smoke-test\n" in makefile, makefile[:400]
    if shutil.which("make") is None:
        pytest.skip("GNU make is not on PATH")
    out = subprocess.run(
        ["make", "-n", "-C", str(project), "clean"],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout
    assert "docker stop x9-smoke-test-smoke" in out, out


@pytest.mark.parametrize(
    "makefile",
    [
        ".PHONY: dev docker-smoke\ndev:\n\tuvicorn x.main:app\n",  # a mention, no rule
        "docker-smoke := 1\ndev:\n\tuvicorn x.main:app\n",  # an assignment, no rule
        "docker-smoke ::= 1\ndev:\n\tuvicorn x.main:app\n",  # GNU make's ::= assignment (W-ab66af6f)
        "docker-smoke :::= 1\ndev:\n\tuvicorn x.main:app\n",  # and its :::= form
        "docker-smoke\n: x\ndev:\n\tuvicorn x.main:app\n",  # not a rule: the colon is on the next line
    ],
)
def test_a_template_with_no_smoke_rule_is_left_alone(makefile, tmp_path, monkeypatch):
    """Only a `docker-smoke:` (or `::`) rule is rewritten; a template without one has nothing to refuse."""
    tpl = tmp_path / "tpl"
    shutil.copytree(_ROOT / "templates" / "scaffold", tpl)
    (tpl / "docker" / "Makefile.python").write_text(makefile)
    monkeypatch.setattr(scaffold, "TEMPLATE_DIR", tpl)
    monkeypatch.setattr(scaffold, "FILE_WORKER_TEMPLATE_DIR", _ROOT / "templates" / "file-worker")
    project = tmp_path / "fw-plain"
    project.mkdir()
    scaffold._scaffold_file_worker(project, "fw-plain", "plain")
    assert (project / "Makefile").exists()


# W-1cb0d89f: any line holding `docker [container] run` text must BE the sealed smoke line the scaffold wrote
_LIVE_RUNS = {
    # the substring check let these through
    "double-space": "\t@docker  run -d --env-file .env $(PROJECT_NAME)\n",
    "container-run": "\t@docker container run -d --env-file .env $(PROJECT_NAME)\n",
    "seal-in-comment": "\t@docker run -d --env-file .env $(PROJECT_NAME) # --network none -e WORKER_SMOKE=1\n",
    # a seal in a later command, after every separator spelling
    **{
        f"seal-after-{name}": f"\t@docker run -d $(PROJECT_NAME){sep}echo --network none -e WORKER_SMOKE=1\n"
        for name, sep in {
            "and": " && ",
            "or": " || ",
            "semicolon": ";",
            "pipe": " | ",
            "background": " & ",
            "double-semicolon": " ;; ",
            "pipe-amp": " |& ",
            "semicolon-paren": ";(",
            "pipe-paren": " |(",
        }.items()
    },
    # half a seal, or a seal overridden later in the same run
    "network-only": "\t@docker run -d --network none $(PROJECT_NAME)\n",
    "smoke-only": "\t@docker run -d -e WORKER_SMOKE=1 $(PROJECT_NAME)\n",
    "smoke-overridden": "\t@docker run -d --network none -e WORKER_SMOKE=1 -e WORKER_SMOKE=0 $(PROJECT_NAME)\n",
    "network-overridden": "\t@docker run -d --network none -e WORKER_SMOKE=1 --network host $(PROJECT_NAME)\n",
    "near-miss": "\t@docker run -d --network=nonexistent -e WORKER_SMOKE=10 $(PROJECT_NAME)\n",
    # quoted, backticked, by path, behind a mid-word or quoted `#`, a seal in a plain-image comment or after `;`
    "sh-c": '\t@sh -c "docker run -d $(PROJECT_NAME)"\n',
    "sh-c-container": '\t@sh -c "docker container run -d $(PROJECT_NAME)"\n',
    "backticks": "\t@echo `docker run -d $(PROJECT_NAME)`\n",
    "by-path": "\t@/usr/bin/docker run -d $(PROJECT_NAME)\n",
    "mid-word-hash": "\t@[ $$# -gt 0 ] && docker run -d $(PROJECT_NAME)\n",
    "quoted-hash": "\t@echo '#'; docker run -d img\n",
    "plain-image-comment": "\t@docker run -d img # --network none -e WORKER_SMOKE=1\n",
    "plain-image-semicolon": "\t@docker run -d img;echo --network none -e WORKER_SMOKE=1\n",
    # make's recipe prefixes and a continuation
    "dash-prefix": "\t-docker run -d $(PROJECT_NAME)\n",
    "plus-prefix": "\t+docker run -d $(PROJECT_NAME)\n",
    "continued": "\t@docker run -d \\\n\t\t$(PROJECT_NAME)\n",
    "split-across-continuation": "\t@docker \\\n\t\trun -d $(PROJECT_NAME)\n",
}

# sealed, but not the line the scaffold writes: drift, refused like any drifted smoke line
_DRIFTED_SEALED_RUNS = [
    # split mid-line with no space before the `\`: make + sh run `smoke-test--network none …`, not the sealed line
    "\t@docker run -d --name smoke-test\\\n\t--network none -e WORKER_SMOKE=1 --env-file .env $(PROJECT_NAME) || true\n",
    "\t@docker run  --network none  -e WORKER_SMOKE=1 $(PROJECT_NAME) || true\n",
    "\t@docker container run --network=none --env=WORKER_SMOKE=1 $(PROJECT_NAME)\n",
]


def _scaffold_with_extra_target(tmp_path, monkeypatch, recipe: str) -> Path:
    tpl = tmp_path / "tpl"
    shutil.copytree(_ROOT / "templates" / "scaffold", tpl)
    mk = tpl / "docker" / "Makefile.python"
    mk.write_text(mk.read_text() + "\nextra-run:\n" + recipe)
    monkeypatch.setattr(scaffold, "TEMPLATE_DIR", tpl)
    monkeypatch.setattr(scaffold, "FILE_WORKER_TEMPLATE_DIR", _ROOT / "templates" / "file-worker")
    project = tmp_path / "fw-extra"
    project.mkdir()
    scaffold._scaffold_file_worker(project, "fw-extra", "extra")
    return project


@pytest.mark.parametrize("case", sorted(_LIVE_RUNS))
def test_a_live_run_fails_the_scaffold(tmp_path, monkeypatch, case):
    with pytest.raises(ValueError, match="live worker"):
        _scaffold_with_extra_target(tmp_path, monkeypatch, _LIVE_RUNS[case])


@pytest.mark.parametrize("recipe", _DRIFTED_SEALED_RUNS)
def test_a_sealed_run_the_scaffold_did_not_write_is_refused_as_drift(tmp_path, monkeypatch, recipe):
    with pytest.raises(ValueError, match="live worker"):
        _scaffold_with_extra_target(tmp_path, monkeypatch, recipe)


def test_a_word_that_only_starts_with_run_is_not_a_run():
    sealed = frozenset()
    assert (
        scaffold._live_docker_runs("\t@echo docker runner\n\t@docker running-total\n", sealed) == []
    )
    assert scaffold._live_docker_runs("\t@echo docker run\n", sealed) == ["@echo docker run"]


def test_continuations_join_as_make_and_the_shell_join_them():
    assert scaffold._live_docker_runs("\t@docker \\\n\t\trun -d img\n", frozenset()) == [
        "@docker \trun -d img"
    ]
    # an escaped backslash ends no line: the next line stands alone
    assert (
        scaffold._live_docker_runs(
            "\t@echo x\\\\\n\t@docker run -d img\n", frozenset({"@docker run -d img"})
        )
        == []
    )
    # `docker\` + `run` is the one word `dockerrun` to the shell: no run
    assert scaffold._live_docker_runs("\t@docker\\\n\trun -d img\n", frozenset()) == []
