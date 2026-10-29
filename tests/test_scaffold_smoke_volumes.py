"""Every container a scaffolded Makefile removes goes with its anonymous volumes (W-2c8173fa).

The smoke targets ran `docker rm smoke-test` / `docker rm -f` / `docker rm $(PROJECT_NAME)-test`, so every
smoke run of an image that declares a VOLUME left one anonymous volume behind (sibling of W-2786800d). Every
scaffold type `create_project` builds (wordpress is refused) is rendered; each removal in each emitted Makefile
must carry `-v`, every container a recipe starts must have such a removal, and — where a docker daemon answers —
each removal is run against a throwaway container of this test's own, whose volume must be gone. The live leg
touches only the container and the volume it created, by name, never a `docker volume ls` difference.
"""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from fabrik import scaffold
from fabrik.scaffold import SCAFFOLD_TYPES, create_project

_ROOT = Path(__file__).resolve().parent.parent
# a container removal or a compose teardown; `rmi` (an image) is not one
_RM = re.compile(r"\bdocker(?:-compose|\s+compose)?\s+(?:container\s+)?(?:rm|down)\b[^;&|\n]*")
_RUN_NAME = re.compile(r"\bdocker\s+run\b[^\n]*?--name\s+(\S+)")
_KEEPS_VOLUMES = re.compile(r"-[a-z]*v[a-z]*|--volumes")


def _flags_drop_volumes(cmd: str) -> bool:
    return any(_KEEPS_VOLUMES.fullmatch(t) for t in cmd.split("#", 1)[0].split())


@pytest.fixture(scope="module")
def makefiles(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    base = tmp_path_factory.mktemp("scaffolds")
    out: dict[str, str] = {}
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(scaffold, "TEMPLATE_DIR", _ROOT / "templates" / "scaffold")
        mp.setattr(scaffold, "FILE_WORKER_TEMPLATE_DIR", _ROOT / "templates" / "file-worker")
        for i, project_type in enumerate(sorted(SCAFFOLD_TYPES - {"wordpress"})):
            name = f"sv-{i}"
            create_project(
                name=name,
                project_type=project_type,
                description="smoke volumes",
                base=base,
                generate_spec=False,
            )
            for mk in sorted((base / name).rglob("Makefile")):
                out[f"{project_type}:{mk.relative_to(base / name)}"] = mk.read_text()
    return out


def _removals(makefiles: dict[str, str]) -> list[tuple[str, str]]:
    return [
        (where, m.group(0).strip()) for where, text in makefiles.items() for m in _RM.finditer(text)
    ]


def test_every_container_removal_takes_its_anonymous_volumes(makefiles):
    bare = [(where, cmd) for where, cmd in _removals(makefiles) if not _flags_drop_volumes(cmd)]
    assert bare == []


def _recipes(text: str) -> list[list[str]]:
    """Each rule's recipe lines (tab-led), split at every non-tab line."""
    blocks: list[list[str]] = [[]]
    for line in text.splitlines():
        if line.startswith("\t"):
            blocks[-1].append(line)
        elif blocks[-1]:
            blocks.append([])
    return [b for b in blocks if b]


def test_every_started_container_is_removed_with_its_volumes_by_its_own_recipe(makefiles):
    # in the recipe that starts a container, the last line naming it removes it with its volumes — a removal
    # only in `clean` or before the run leaves each smoke run's container and volume behind until then
    started, bare = set(), []
    for where, text in makefiles.items():
        for recipe in _recipes(text):
            for name in {n for ln in recipe for n in _RUN_NAME.findall(ln)}:
                started.add(where.split(":")[0])
                last = [ln for ln in recipe if name in ln.split()][-1]
                ok = any(
                    _flags_drop_volumes(m.group(0)) and name in m.group(0).split()
                    for m in _RM.finditer(last)
                )
                if not ok:
                    bare.append((where, name, last.strip()))
    # the population this guards: the python, node, file-worker and chrome-extension smoke targets
    assert started >= {"python-api", "node-api", "file-worker", "chrome-extension"}, started
    assert bare == []


def _docker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=60)


def test_each_emitted_removal_leaves_no_anonymous_volume(makefiles):
    try:
        if shutil.which("docker") is None or _docker("info").returncode:
            pytest.skip("no docker daemon answers")
        if _docker("image", "inspect", "alpine:3").returncode:
            pytest.skip("alpine:3 is not present locally (the test never pulls)")
    except subprocess.TimeoutExpired:
        pytest.skip("the docker daemon did not answer within 60 s")
    commands = sorted({cmd for _, cmd in _removals(makefiles) if " down" not in cmd})
    assert commands
    for cmd in commands:
        # drop `2>/dev/null`-style redirections; exactly one word after the flags is the container name
        argv = [t for t in shlex.split(cmd.split("#", 1)[0]) if ">" not in t]
        names = [i for i, t in enumerate(argv[2:], 2) if not t.startswith("-")]
        assert len(names) == 1, (
            f"{cmd!r}: expected one container name, got {[argv[i] for i in names]}"
        )
        probe = f"fabrik-smoke-volume-probe-{uuid.uuid4().hex[:12]}"
        argv[names[0]] = probe
        mine: list[str] = []
        try:
            assert not _docker(
                "run", "-d", "--name", probe, "-v", "/data", "alpine:3", "sleep", "60"
            ).returncode
            inspect = _docker("inspect", "-f", "{{range .Mounts}}{{.Name}} {{end}}", probe)
            mine = inspect.stdout.split()
            assert not inspect.returncode and len(mine) == 1, inspect
            if not any(re.fullmatch(r"-[a-z]*f[a-z]*|--force", t) for t in argv[2:]):
                assert not _docker("stop", "-t", "0", probe).returncode
            assert not subprocess.run(argv, capture_output=True, timeout=60).returncode
            assert _docker("volume", "inspect", mine[0]).returncode, (
                f"{cmd!r} left volume {mine[0]}"
            )
        finally:
            _docker("rm", "-fv", probe)  # this test's own container only
            for v in mine:  # this test's own volume only, read from its own container
                _docker("volume", "rm", v)


def test_the_chrome_extension_smoke_cleans_up_on_every_path(makefiles):
    # a leftover of an interrupted run is removed first, a failed `docker run` leaves no Created container,
    # and `make clean` removes the container with its volume (W-2c8173fa round 1: O1, H1)
    text = makefiles["chrome-extension:Makefile"]
    rm_first = "\t@docker rm -fv $(PROJECT_NAME)-test >/dev/null 2>&1 || true\n\t@docker run -d"
    assert rm_first in text
    run = next(ln for ln in text.splitlines() if "docker run -d --name $(PROJECT_NAME)-test" in ln)
    assert run.endswith("|| (docker rm -fv $(PROJECT_NAME)-test >/dev/null 2>&1; exit 1)"), run
    clean = text.split("\nclean:", 1)[1].split("\n\n", 1)[0]
    assert "docker rm -fv $(PROJECT_NAME)-test" in clean, clean
