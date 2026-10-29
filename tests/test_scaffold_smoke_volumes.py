"""Every container a scaffolded Makefile removes goes with its anonymous volumes (W-2c8173fa).

The smoke targets ran `docker rm smoke-test` / `docker rm -f` / `docker rm $(PROJECT_NAME)-test`, so every
smoke run of an image that declares a VOLUME left one anonymous volume behind (sibling of W-2786800d). Every
scaffold type is rendered; each `docker rm` line in each emitted Makefile must carry `-v`, and — where a docker
daemon answers — each one is run against a throwaway container with an anonymous volume, which must be gone.
"""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

from fabrik import scaffold
from fabrik.scaffold import SCAFFOLD_TYPES, create_project

_ROOT = Path(__file__).resolve().parent.parent
_RM = re.compile(r"\bdocker\s+(?:container\s+)?rm\b(?![i-])[^;&|\n]*")
_PROBE = "fabrik-smoke-volume-probe"


@pytest.fixture(scope="module")
def removals(tmp_path_factory: pytest.TempPathFactory) -> list[tuple[str, str]]:
    base = tmp_path_factory.mktemp("scaffolds")
    found: list[tuple[str, str]] = []
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
                for m in _RM.finditer(mk.read_text()):
                    found.append(
                        (f"{project_type}:{mk.relative_to(base / name)}", m.group(0).strip())
                    )
    return found


def test_the_population_is_not_empty(removals):
    # the smoke and clean targets of the python and node templates and of the chrome-extension emitter at least
    assert len({where.split(":")[0] for where, _ in removals}) >= 4, removals


def test_every_container_removal_takes_its_anonymous_volumes(removals):
    bare = [
        (where, cmd)
        for where, cmd in removals
        if not any(re.fullmatch(r"-[a-z]*v[a-z]*", t) for t in cmd.split())
    ]
    assert bare == []


def _volumes() -> set[str]:
    out = subprocess.run(
        ["docker", "volume", "ls", "-q"], capture_output=True, text=True, timeout=60
    )
    return set(out.stdout.split())


def test_each_emitted_removal_leaves_no_anonymous_volume(removals):
    if (
        shutil.which("docker") is None
        or subprocess.run(["docker", "info"], capture_output=True, timeout=60).returncode
    ):
        pytest.skip("no docker daemon answers")
    if subprocess.run(
        ["docker", "image", "inspect", "alpine:3"], capture_output=True, timeout=60
    ).returncode:
        pytest.skip("alpine:3 is not present locally (the test never pulls)")
    for cmd in sorted({c for _, c in removals}):
        # drop `2>/dev/null`-style redirections; the last word is the container name (smoke-test,
        # $(PROJECT_NAME)-smoke or $(PROJECT_NAME)-test), replaced by the probe's
        argv = [t for t in shlex.split(cmd) if ">" not in t]
        argv[-1] = _PROBE
        forced = any(re.fullmatch(r"-[a-z]*f[a-z]*", t) for t in argv[2:])
        before = _volumes()
        subprocess.run(
            ["docker", "run", "-d", "--name", _PROBE, "-v", "/data", "alpine:3", "sleep", "60"],
            check=True,
            capture_output=True,
            timeout=60,
        )
        made = _volumes() - before
        try:
            if not forced:
                subprocess.run(
                    ["docker", "stop", "-t", "0", _PROBE],
                    check=True,
                    capture_output=True,
                    timeout=60,
                )
            subprocess.run(argv, check=True, capture_output=True, timeout=60)
            assert made and not (made & _volumes()), f"{cmd!r} left {sorted(made & _volumes())}"
        finally:
            subprocess.run(["docker", "rm", "-fv", _PROBE], capture_output=True, timeout=60)
            for v in made & _volumes():  # only the volume this test made
                subprocess.run(["docker", "volume", "rm", v], capture_output=True, timeout=60)
