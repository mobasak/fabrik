"""mobile-app scaffold: a coherent lint toolchain and delivery workflows whose local actions exist (W-fc58e9b7).

Until 2026-10-29 a fresh mobile-app scaffold's `pnpm lint` exited 1 (76 errors, all antfu's TOML
rules on the scaffold-emitted `server/pyproject.toml`), its lint set carried react-refresh 0.4.x
under @antfu/eslint-config 7.7.3's `^0.5.0` peer and a second, direct unicorn, and three delivery
workflows `uses:` two local composite actions the template had never shipped. Structure tests run
in the default suite; one `needs_network` test (deselected by default, run with
`-m needs_network`) installs, lints and type-checks a fresh scaffold.

The cheap way past the input-contract test is to give a required input a default, so a workflow
that drops it still passes: the test refuses a required input that carries one, and resolves every
eas-build step's APP_ENV to one of the three profiles that have `build:<env>:<platform>` scripts.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from fabrik.scaffold import create_project

FABRIK_ROOT = Path("/opt/fabrik")
pytestmark = pytest.mark.skipif(
    not FABRIK_ROOT.exists(),
    reason="Requires the full fabrik environment at /opt/fabrik (templates dir)",
)
APP_ENVS = ("development", "preview", "production")


@pytest.fixture(scope="module")
def app(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("mobtool")
    create_project(
        "mobtooltest",
        "mobile toolchain test",
        base=base,
        project_type="mobile-app",
        generate_spec=False,
    )
    return base / "mobtooltest"


def _local_action_steps(app: Path) -> list[tuple[str, str, dict]]:
    """(workflow file, action name, with-mapping) for every `uses: ./.github/actions/<name>` step."""
    steps = []
    for wf in sorted((app / ".github" / "workflows").glob("*.yml")):
        doc = yaml.safe_load(wf.read_text()) or {}
        for job in (doc.get("jobs") or {}).values():
            # a job-level `uses: ./…` is a local reusable workflow, which this walk does not resolve
            assert not str(job.get("uses", "")).startswith("./"), f"{wf.name}: job-level local uses"
            for step in job.get("steps") or []:
                uses = step.get("uses", "")
                if uses.startswith("./"):
                    assert uses.startswith("./.github/actions/"), (
                        f"{wf.name}: unexpected local uses {uses}"
                    )
                    steps.append(
                        (wf.name, uses.removeprefix("./.github/actions/"), step.get("with") or {})
                    )
    return steps


def test_lint_toolchain_ranges(app: Path) -> None:
    dev = json.loads((app / "package.json").read_text())["devDependencies"]
    assert dev["@antfu/eslint-config"] == "~7.7.3"
    assert dev["eslint-plugin-react-refresh"] == "^0.5.0"
    assert dev["@eslint-react/eslint-plugin"] == "^2.11.0"
    # unicorn's rules come through antfu's own unicorn; a direct one is a second copy in the tree
    assert "eslint-plugin-unicorn" not in dev


def test_eslint_config_ignores_server(app: Path) -> None:
    # a live (uncommented) entry inside the `ignores: [ … ]` array, not the string anywhere
    ignores = re.search(
        r"^\s*ignores:\s*\[(.*?)^\s*\],", (app / "eslint.config.mjs").read_text(), re.M | re.S
    )
    assert ignores, "eslint.config.mjs has no ignores array"
    assert re.search(r"^\s*'server/\*\*',\s*$", ignores.group(1), re.M)


def test_local_actions_resolve(app: Path) -> None:
    steps = _local_action_steps(app)
    assert steps, "the delivery workflows use local actions; finding none means the walk is broken"
    for wf, name, _ in steps:
        assert (app / ".github" / "actions" / name / "action.yml").is_file(), (
            f"{wf}: {name} not shipped"
        )


def test_local_action_inputs_match(app: Path) -> None:
    scripts = json.loads((app / "package.json").read_text())["scripts"]
    for wf, name, with_ in _local_action_steps(app):
        inputs = (
            yaml.safe_load((app / ".github" / "actions" / name / "action.yml").read_text()).get(
                "inputs"
            )
            or {}
        )
        assert set(with_) <= set(inputs), (
            f"{wf}: {name} gets undeclared inputs {set(with_) - set(inputs)}"
        )
        for key, spec in inputs.items():
            if spec.get("required"):
                # GitHub does not enforce `required` on a composite action: a default would let a
                # workflow that drops the input run on it silently
                assert "default" not in spec, f"{name}: required input {key} carries a default"
                assert key in with_, f"{wf}: {name} requires {key}"
        if "APP_ENV" in inputs:
            assert with_.get("APP_ENV") in APP_ENVS, f"{wf}: APP_ENV {with_.get('APP_ENV')!r}"
            for platform in ("android", "ios"):
                assert f"build:{with_['APP_ENV']}:{platform}" in scripts, f"{wf}: no build script"


@pytest.mark.skipif(
    shutil.which("pnpm") is None or shutil.which("node") is None,
    reason="requires the node/pnpm toolchain",
)
@pytest.mark.needs_network
@pytest.mark.timeout(
    2400
)  # the three commands' own budgets; the INI's 600 s would cut a cold install
def test_mobile_scaffold_installs_lints_and_typechecks(app: Path) -> None:
    for cmd, timeout in (
        (["pnpm", "install"], 1200),
        (["pnpm", "lint"], 600),
        (["pnpm", "type-check"], 600),
    ):
        run = subprocess.run(cmd, cwd=app, capture_output=True, text=True, timeout=timeout)
        assert run.returncode == 0, (
            f"{' '.join(cmd)} failed:\n{run.stdout[-3000:]}{run.stderr[-1500:]}"
        )
