"""Graders for scripts/enforcement/check_mcp_scope.py (operator mail 01M4AR32MY, 2026-10-07):
an emitted `.mcp.json` must be a SUBSET of its repo's ruling, the hub included."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HUB = Path(__file__).resolve().parents[2]
SRC = HUB / "scripts" / "enforcement" / "check_mcp_scope.py"

DEFS = {
    name: {"command": f"/usr/bin/{name}", "args": []}
    for name in (
        "session-recall",
        "exa",
        "brave-search",
        "firecrawl",
        "postgres-pro",
        "serena",
        "playwright",
        "chrome-devtools",
        "shadcn",
        "magicui",
        "maestro",
        "mobile-mcp",
        "pubchem",
        "media-engine",
        "grafana",
    )
}


@pytest.fixture(scope="module")
def check():
    spec = importlib.util.spec_from_file_location("check_mcp_scope", SRC)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def repo(root: Path, name: str, rtype: str | None, servers: list[str]) -> Path:
    d = root / name
    (d / ".git").mkdir(parents=True)
    if rtype:
        (d / "project.yaml").write_text(f"name: {name}\ntype: {rtype}\n")
    (d / ".mcp.json").write_text(json.dumps({"mcpServers": {s: DEFS[s] for s in servers}}))
    return d


def test_the_hub_carrying_a_heavy_server_fails_and_names_the_emitter(check, tmp_path):
    repo(tmp_path, "fabrik", None, ["session-recall", "exa", "maestro"])
    rep = check.audit(tmp_path, HUB, DEFS)
    assert [f["repo"] for f in rep["failures"]] == ["fabrik"]
    assert rep["failures"][0]["extra"] == ["maestro"]
    assert "emit_mcp_project_config.py --repo" in rep["failures"][0]["fix"]


def test_a_subset_passes_and_an_omitted_allowed_server_is_legal(check, tmp_path):
    repo(tmp_path, "some-api", "python-api", ["session-recall", "exa"])  # no postgres-pro: legal
    repo(tmp_path, "app", "mobile-app", ["session-recall", "maestro", "mobile-mcp"])
    rep = check.audit(tmp_path, HUB, DEFS)
    assert rep["failures"] == [] and rep["checked"] == 2


def test_a_headless_repo_carrying_a_browser_server_fails(check, tmp_path):
    repo(tmp_path, "some-api", "python-api", ["session-recall", "playwright"])
    rep = check.audit(tmp_path, HUB, DEFS)
    assert rep["failures"][0]["extra"] == ["playwright"]


def test_an_unruled_repo_and_the_own_agent_hub_class_repo_only_warn(check, tmp_path):
    repo(tmp_path, "mystery", None, ["session-recall", "maestro"])  # no project.yaml
    # fabrik-lib keeps the FULL roster, maestro included (operator ruling 2026-10-07) — no warning
    lib = repo(tmp_path, "fabrik-lib", None, ["session-recall", "maestro", "playwright"])
    rep = check.audit(tmp_path, HUB, DEFS)
    assert rep["failures"] == []
    assert sorted(w["repo"] for w in rep["warnings"]) == ["mystery"]
    # a server outside the roster in an own-agent repo warns (its agent writes the file), never fails
    (lib / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "session-recall": DEFS["session-recall"],
                    "github": {"command": "/usr/bin/github"},
                }
            }
        )
    )
    rep = check.audit(tmp_path, HUB, DEFS)
    assert rep["failures"] == []
    assert [w["repo"] for w in rep["warnings"] if w["repo"] == "fabrik-lib"] == ["fabrik-lib"]


def test_cli_exit_codes(tmp_path):
    repo(tmp_path, "fabrik", None, ["session-recall", "chrome-devtools"])
    r = subprocess.run(
        [sys.executable, str(SRC), "--root", str(tmp_path), "--hub", str(HUB)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1 and "FAIL fabrik" in r.stdout and "chrome-devtools" in r.stdout
    r = subprocess.run(
        [sys.executable, str(SRC), "--root", str(tmp_path / "nowhere"), "--hub", str(HUB)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0 and "SKIP" in r.stdout


def test_projects_skip_without_the_hub_marker(tmp_path):
    fake_hub = tmp_path / "proj"
    fake_hub.mkdir()
    r = subprocess.run(
        [sys.executable, str(SRC), "--root", str(tmp_path), "--hub", str(fake_hub)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0 and "hub-only" in r.stdout


def test_a_condemned_repo_is_skipped_by_name_even_with_a_valid_type(check, tmp_path):
    repo(tmp_path, "image-generation", "python-api", ["session-recall", "maestro"])
    rep = check.audit(tmp_path, HUB, DEFS)
    assert rep["failures"] == [] and rep["warnings"] == [] and rep["checked"] == 0
