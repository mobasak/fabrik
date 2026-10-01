"""Pins `mobile-app/89-mobile-launch-checklist.md` to the scaffold it gates.

`/fabrik-release` runs every gate in this pack, so a gate that names a field, file or channel the scaffold does
not have blocks a release on nothing (the pack once demanded `min_required_version` and `app.json`, neither of
which the scaffold ships). Three facts are pinned:

1. The `/app-config` contract the forced-upgrade gate relies on: the query parameters and response keys it names.
2. Which EAS build profiles carry update channels.
3. The app config file: `app.config.ts`, never `app.json` — and every `<pack>.md § <section>` the pack cites exists.

The cheapest way to satisfy (1) without the outcome is to name only keys the scaffold happens to return; the test
also requires the gate to block on `update_required`, the key that carries the decision.
"""

from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path

import pytest

from fabrik.scaffold import create_project

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules"
PACK = RULES / "mobile-app" / "89-mobile-launch-checklist.md"

requires_fabrik_env = pytest.mark.skipif(
    not (ROOT / "templates" / "mobile-app").is_dir(),
    reason="needs the hub's templates/mobile-app",
)


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("mobile-launch")
    os.environ.setdefault("FABRIK_ROOT", str(ROOT))
    create_project(
        "mobilelaunch", "probe", base=base, project_type="mobile-app", generate_spec=False
    )
    return base / "mobilelaunch"


def _pack() -> str:
    return PACK.read_text(encoding="utf-8")


def _gate(heading_prefix: str) -> str:
    """The bullet under § OTA Updates & Forced Upgrade whose bold label starts with `heading_prefix`."""
    line = next(
        (ln for ln in _pack().splitlines() if ln.startswith(f"- [ ] **{heading_prefix}")), ""
    )
    assert line, f"no gate starting {heading_prefix!r}"
    return line


@requires_fabrik_env
def test_forced_upgrade_gate_names_the_real_app_config_contract(project: Path) -> None:
    route = (project / "server" / "src" / "app" / "routes" / "app_config.py").read_text(
        encoding="utf-8"
    )
    params = {
        a.arg
        for n in ast.walk(ast.parse(route))
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "get_app_config"
        for a in n.args.args
    }
    config = (project / "server" / "src" / "mobile_config" / "config.py").read_text(
        encoding="utf-8"
    )
    keys = set(re.findall(r'^\s+"(\w+)":', config, re.M)) | set(
        re.findall(r'payload\["(\w+)"\]', route)
    )
    gate = _gate("Forced upgrade gate")
    for named in re.findall(r"`(\w+)`", gate):
        if named in {"update_required", "update_available", "kill_switch", "store_urls"}:
            assert named in keys, f"the gate names {named!r}, which /app-config does not return"
    assert {"platform", "version"} <= params, (
        f"/app-config now takes {sorted(params)}: update the gate"
    )
    assert "platform=" in gate and "version=" in gate
    assert "Block on `update_required`" in gate


@requires_fabrik_env
def test_update_channels_are_the_profiles_the_pack_names(project: Path) -> None:
    builds = json.loads((project / "eas.json").read_text(encoding="utf-8"))["build"]
    with_channel = sorted(
        name for name, p in builds.items() if isinstance(p, dict) and "channel" in p
    )
    assert with_channel == ["preview", "production"], (
        f"EAS profiles with update channels are now {with_channel}: update § OTA Updates & Forced Upgrade"
    )
    gate = _gate("EAS Update configured")
    assert "`preview` and `production`" in gate and "`development` profile has none" in gate


@requires_fabrik_env
def test_app_config_is_app_config_ts_not_app_json(project: Path) -> None:
    assert (project / "app.config.ts").is_file()
    assert not (project / "app.json").exists(), (
        "the scaffold ships app.json again: re-check the pack's wording"
    )
    body = _pack().split("---", 2)[
        2
    ]  # skip the frontmatter, whose glob still matches older apps' app.json
    assert "app.json" not in body, (
        "the pack tells agents to edit app.json, which the scaffold does not have"
    )


_CITE = re.compile(
    r"`(?:\.windsurf/rules/)?(?:[a-z-]+/)?(\d\d-[a-z0-9-]+\.md)`((?:\s*\+?\s*§ [^.;:*()—`]+)+)"
)


def test_every_cited_section_exists() -> None:
    missing = []
    found = 0
    for m in _CITE.finditer(_pack()):
        for section in re.findall(r"§ ([^§+]+)", m.group(2)):
            section = re.sub(r"\s+(?:and|or)$", "", section.split(",")[0].strip())
            if not section[:1].isupper():
                continue
            found += 1
            target = next(RULES.rglob(m.group(1)), None)
            heads = [
                ln.lstrip("#").strip()
                for ln in (target.read_text(encoding="utf-8").splitlines() if target else [])
                if ln.startswith("#")
            ]
            if not any(h.startswith(section) for h in heads):
                missing.append(f"{m.group(1)} § {section}")
    assert found >= 6, f"the cite parser found only {found} cites: check _CITE"
    assert not missing, f"cited sections not found: {missing}"
