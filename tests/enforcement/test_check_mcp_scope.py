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
        "fabrik-scrape",
        "playwright",
        "chrome-devtools",
        "shadcn",
        "magicui",
        "maestro",
        "mobile-mcp",
        "pubchem",
        "media-engine",
        "grafana",
        "rea",
    )
}


@pytest.fixture(autouse=True)
def _hermetic_git(tmp_path, monkeypatch):
    """The ownership predicate asks git: the box's global or system excludes must not decide these tests."""
    empty = tmp_path / "empty.gitconfig"
    empty.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


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
    # no postgres-pro: legal
    repo(tmp_path, "some-api", "python-api", ["session-recall", "exa", "fabrik-scrape", "rea"])
    repo(tmp_path, "app", "mobile-app", ["session-recall", "maestro", "mobile-mcp"])
    rep = check.audit(tmp_path, HUB, DEFS)
    assert rep["failures"] == [] and rep["checked"] == 2


def test_a_headless_repo_carrying_a_browser_server_fails(check, tmp_path):
    repo(tmp_path, "some-api", "python-api", ["session-recall", "playwright"])
    rep = check.audit(tmp_path, HUB, DEFS)
    assert rep["failures"][0]["extra"] == ["playwright"]


def test_an_unknown_type_and_the_own_agent_hub_class_repo_only_warn(check, tmp_path):
    repo(
        tmp_path, "mystery", "sass-skeleton", ["session-recall", "maestro"]
    )  # a type the roster lacks
    # an UNTYPED repo the emitter owns (its .gitignore keeps .mcp.json out of git) is ruled since D-1246 (the
    # universal set): a server outside it FAILS; one the emitter would refuse to write only warns, since
    # re-emitting cannot clear it
    owned = tmp_path / "untyped"
    owned.mkdir()
    subprocess.run(["git", "init", "-q", str(owned)], check=True)
    (owned / ".gitignore").write_text(".mcp.json\n")
    (owned / ".mcp.json").write_text(
        json.dumps({"mcpServers": {s: DEFS[s] for s in ("rea", "maestro")}})
    )
    vendor = repo(
        tmp_path, "vendor-clone", None, ["session-recall", "maestro"]
    )  # no gitignore line
    (vendor / ".git").rmdir()
    subprocess.run(["git", "init", "-q", str(vendor)], check=True)
    # a repo git cannot answer for (here a bare `.git` dir) FAILS: an unknown answer never demotes to a warning
    repo(tmp_path, "unanswerable", None, ["session-recall", "maestro"])
    # an UNTYPED directory that is no git repo is not graded, as the emitter never sweeps it
    plain = repo(tmp_path, "plain-dir", None, ["session-recall", "maestro"])
    (plain / ".git").rmdir()
    # …but a TYPED one is a ruled project wherever it sits: graded (the liveness canary's fixture shape)
    typed = repo(tmp_path, "typed-no-git", "python-api", ["session-recall", "maestro"])
    (typed / ".git").rmdir()
    # fabrik-lib keeps the FULL roster, maestro included (operator ruling 2026-10-07) — no warning
    lib = repo(tmp_path, "fabrik-lib", None, ["session-recall", "maestro", "playwright"])
    rep = check.audit(tmp_path, HUB, DEFS)
    assert [(f["repo"], f["extra"]) for f in rep["failures"]] == [
        ("typed-no-git", ["maestro"]),
        ("unanswerable", ["maestro"]),
        ("untyped", ["maestro"]),
    ]
    assert sorted(w["repo"] for w in rep["warnings"]) == ["mystery", "vendor-clone"]
    assert (
        "not ignored by git"
        in next(w for w in rep["warnings"] if w["repo"] == "vendor-clone")["reason"]
    )
    (owned / ".mcp.json").unlink()
    (vendor / ".mcp.json").unlink()
    (tmp_path / "unanswerable" / ".mcp.json").unlink()
    (typed / ".mcp.json").unlink()
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
    lib_warns = [w for w in rep["warnings"] if w["repo"] == "fabrik-lib"]
    assert [w["extra"] for w in lib_warns] == [["github"]], lib_warns


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


def test_the_hub_without_a_git_dir_is_still_graded(check, tmp_path):
    """Hub-class names are ruled by name, never by type: a hub dir with no `.git` (and no project.yaml) carrying a
    heavy server still FAILS — the untyped-non-git skip never reaches it."""
    hub = repo(tmp_path, "fabrik", None, ["session-recall", "maestro"])
    (hub / ".git").rmdir()
    rep = check.audit(tmp_path, HUB, DEFS)
    assert [(f["repo"], f["extra"]) for f in rep["failures"]] == [("fabrik", ["maestro"])]


def test_an_unreadable_project_yaml_warns_never_crashes(check, tmp_path):
    """A project.yaml the gate cannot read (mode 000) is an unknown type — a warning — never a traceback that
    takes the whole gate down; with or without a `.git`."""
    for name in ("unreadable-repo", "unreadable-dir"):
        d = repo(tmp_path, name, "python-api", ["session-recall", "maestro"])
        if name == "unreadable-dir":
            (d / ".git").rmdir()
        (d / "project.yaml").chmod(0)
    try:
        rep = check.audit(tmp_path, HUB, DEFS)
    finally:
        for name in ("unreadable-repo", "unreadable-dir"):
            (tmp_path / name / "project.yaml").chmod(0o644)
    assert rep["failures"] == []
    assert sorted(w["repo"] for w in rep["warnings"]) == ["unreadable-dir", "unreadable-repo"]


def test_image_generation_is_graded_like_any_repo_of_its_type(check, tmp_path):
    """D-1246 emptied CONDEMNED: image-generation now carries an emitted .mcp.json, graded as python-api."""
    repo(tmp_path, "image-generation", "python-api", ["session-recall", "maestro"])
    rep = check.audit(tmp_path, HUB, DEFS)
    assert rep["checked"] == 1
    assert [(f["repo"], f["extra"]) for f in rep["failures"]] == [("image-generation", ["maestro"])]


def test_a_credential_abort_in_the_emitter_is_a_structured_fail(
    tmp_path, monkeypatch, capsys, check
):
    """A-S2 (review 2026-10-07): when the emitter's chain aborts (D-641), the gate prints one
    `check_mcp_scope: FAIL` line and exits 1 — never a bare traceback."""
    repo(tmp_path, "some-api", "python-api", ["session-recall"])

    def boom(root, hub, defs=None):
        raise SystemExit("emit_mcp: credential(s) unresolved — exa.env.EXA_API_KEY")

    monkeypatch.setattr(check, "audit", boom)
    rc = check.main(["--root", str(tmp_path), "--hub", str(HUB)])
    out = capsys.readouterr().out
    assert rc == 1 and "check_mcp_scope: FAIL" in out and "exa.env.EXA_API_KEY" in out
