"""mobile-app scaffold: a coherent lint toolchain and delivery workflows whose local actions exist (W-fc58e9b7).

Until 2026-10-29 a fresh mobile-app scaffold's `pnpm lint` exited 1 (76 errors, all antfu's TOML
rules on the scaffold-emitted `server/pyproject.toml`), its lint set carried react-refresh 0.4.x
under @antfu/eslint-config 7.7.3's `^0.5.0` peer and a second, direct unicorn, and three delivery
workflows `uses:` two local composite actions the template had never shipped. Structure tests run
in the default suite; one `needs_network` test (deselected by default, run with
`-m needs_network`) installs, lints and type-checks a fresh scaffold.

The cheap way past the input-contract test is to delete a workflow's `with:` key instead of
declaring it; that is caught by the needs_network run only if the key mattered, so the test also
pins each APP_ENV a workflow passes to the `build:<env>:<platform>` scripts the action calls.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from fabrik.scaffold import create_project

FABRIK_ROOT = Path("/opt/fabrik")
pytestmark = pytest.mark.skipif(
    not FABRIK_ROOT.exists() or os.getenv("CI") == "true",
    reason="Requires the full fabrik environment at /opt/fabrik (templates dir)",
)


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
        doc = yaml.safe_load(wf.read_text())
        for job in (doc.get("jobs") or {}).values():
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
    assert "'server/**'," in (app / "eslint.config.mjs").read_text()


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
            if spec.get("required") and "default" not in spec:
                assert key in with_, f"{wf}: {name} requires {key}"
        if "APP_ENV" in with_:
            for platform in ("android", "ios"):
                assert f"build:{with_['APP_ENV']}:{platform}" in scripts, f"{wf}: no build script"


@pytest.mark.skipif(
    shutil.which("pnpm") is None or shutil.which("node") is None,
    reason="requires the node/pnpm toolchain",
)
@pytest.mark.needs_network
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
