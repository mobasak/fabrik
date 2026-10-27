# AFTER-EDIT: scripts/sysadmin/emit_mcp_project_config.py | none
"""W-f7772267 (b)(g): the MCP emitter's credential chain and an unreadable project.yaml.

Kept out of tests/test_emit_mcp_project_config.py, which intel's plan lock owns, so its rebase reads no hunk here."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts/sysadmin/emit_mcp_project_config.py"
_spec = importlib.util.spec_from_file_location("emit_mcp_project_config_fillins", _SCRIPT)
emitter = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(emitter)


@pytest.fixture(autouse=True)
def _hermetic(tmp_path, monkeypatch):
    """Git asks no global or system config, and the credential chain reads only this test's roster and .env."""
    empty = tmp_path / "empty.gitconfig"
    empty.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    (tmp_path / "empty-xdg").mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty-xdg"))
    monkeypatch.setattr(emitter, "ROSTER_PATH", tmp_path / "roster.json")
    monkeypatch.setattr(emitter, "HUB_ENV_PATH", tmp_path / "hub.env")


@pytest.fixture()
def defs_file(tmp_path: Path) -> Path:
    p = tmp_path / "defs.json"
    p.write_text(json.dumps({"mcpServers": {"session-recall": {"command": "sr"}}}))
    return p


def _repo(root: Path, name: str, rtype: str | None) -> Path:
    d = root / name
    d.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(d)], check=True)
    (d / ".gitignore").write_text(".mcp.json\n")
    if rtype is not None:
        (d / "project.yaml").write_text(f"name: {name}\ntype: {rtype}\n")
    return d


@pytest.mark.parametrize(
    "roster",
    [
        [],
        "not an object",
        {"mcpServers": 7},
        {"mcpServers": {"exa": "not an object"}},
        {"mcpServers": {"exa": {"env": ["not", "an", "object"]}}},
        {"mcpServers": {"exa": {"env": 7}}},
        "[" * 100_000,  # json.loads raises RecursionError, which is no ValueError (review pass 1)
    ],
    ids=["list", "string", "servers-int", "entry-string", "env-list", "env-int", "nested-100k"],
)
def test_a_wrong_shape_roster_falls_through_to_the_hub_env(tmp_path, roster):
    """(b): a roster of any wrong shape is no donor — the chain falls through to the hub .env, never an
    AttributeError or RecursionError that takes the whole emitter (and check_mcp_scope, which loads the defs) down.
    Every case here raised before the fix; a falsy shape (`{"mcpServers": []}`) never did, so it proves nothing."""
    text = roster if isinstance(roster, str) and roster.startswith("[") else json.dumps(roster)
    (tmp_path / "roster.json").write_text(text)
    (tmp_path / "hub.env").write_text("EXA_API_KEY=from-dotenv\n")
    loaded = {"exa": {"command": "exa", "env": {"EXA_API_KEY": "${EXA_API_KEY}"}}}
    assert emitter._fill_credentials(loaded) == []
    assert loaded["exa"]["env"]["EXA_API_KEY"] == "from-dotenv"


def test_a_well_formed_roster_still_wins_over_the_hub_env(tmp_path):
    (tmp_path / "roster.json").write_text(
        json.dumps({"mcpServers": {"exa": {"env": {"EXA_API_KEY": "from-roster"}}}})
    )
    (tmp_path / "hub.env").write_text("EXA_API_KEY=from-dotenv\n")
    loaded = {"exa": {"command": "exa", "env": {"EXA_API_KEY": "${EXA_API_KEY}"}}}
    assert emitter._fill_credentials(loaded) == []
    assert loaded["exa"]["env"]["EXA_API_KEY"] == "from-roster"


def test_an_unreadable_project_yaml_is_a_named_failure(tmp_path, defs_file):
    """(g): a project.yaml the emitter cannot read is no ruling to apply, and the run did not do its job: the verdict
    names the cause and the CLI exits 1. A type the roster does not know stays a bare policy SKIP at exit 0."""
    bad = _repo(tmp_path, "bad-yaml", "python-api")
    (bad / "project.yaml").chmod(0)
    try:
        if os.access(bad / "project.yaml", os.R_OK):
            pytest.skip("running as a user who can read a mode-000 file")
        argv = ["--repo", str(bad), "--defs", str(defs_file), "--check"]
        (line,) = emitter.main(argv)
        assert line.startswith("bad-yaml: SKIP (error: project.yaml unreadable"), line
        assert emitter.cli(argv) == 1
    finally:
        (bad / "project.yaml").chmod(0o644)
    # a type the roster does not know, and a `type:` line the grammar cannot parse, are policy SKIPs at exit 0
    typo = _repo(tmp_path, "typo-type", "sass-skeleton")
    quoted = _repo(tmp_path, "quoted-type", None)
    (quoted / "project.yaml").write_text('name: quoted-type\ntype: "python api"\n')
    for repo in (typo, quoted):
        argv = ["--repo", str(repo), "--defs", str(defs_file), "--check"]
        assert emitter.main(argv) == [f"{repo.name}: SKIP"]
        assert emitter.cli(argv) == 0


@pytest.mark.parametrize("shape", ["directory", "dangling link", "link loop", "fifo"])
def test_a_project_yaml_that_is_no_readable_file_is_a_named_failure(tmp_path, defs_file, shape):
    """(g), review passes 1-2: a project.yaml that exists but is no regular file is not a missing one, so the repo is
    never emitted as untyped (the universal set, dropping its typed servers): it is the same named failure, and it is
    never opened — a FIFO's read blocks with no writer, which hung the emitter and check_mcp_scope (pass 2)."""
    repo = _repo(tmp_path, "odd-yaml", None)
    py = repo / "project.yaml"
    if shape == "directory":
        py.mkdir()
    elif shape == "dangling link":
        py.symlink_to(repo / "gone.yaml")
    elif shape == "link loop":
        py.symlink_to(py)
    else:
        os.mkfifo(py)
    argv = ["--repo", str(repo), "--defs", str(defs_file), "--check"]
    (line,) = emitter.main(argv)
    assert line.startswith("odd-yaml: SKIP (error: project.yaml unreadable"), line
    assert emitter.cli(argv) == 1


_NO_SERVERS = "hold no non-empty `mcpServers` object"


@pytest.mark.parametrize(
    "catalog, tail",
    [
        ({"mcpServers": {"exa": "not an object"}}, "wrong shape: exa"),
        (
            {"mcpServers": {"exa": {"command": "exa", "env": ["not", "an", "object"]}}},
            "wrong shape: exa.env",
        ),
        ({"mcpServers": {"exa": {"command": "exa", "env": 7}}}, "wrong shape: exa.env"),
        ({"mcpServers": {"exa": {"command": 5}}}, "wrong shape: exa.command"),
        ({"mcpServers": {"exa": {"command": "exa", "args": 5}}}, "wrong shape: exa.args"),
        ({"mcpServers": {"exa": {"command": "exa", "args": [1]}}}, "wrong shape: exa.args"),
        ([{"mcpServers": {}}], _NO_SERVERS),
        ({"mcpServers": ["exa"]}, _NO_SERVERS),
        ({"mcpServers": {}}, _NO_SERVERS),
        ({}, _NO_SERVERS),
        ("{not json", None),
        ('{"mcpServers": {"exa": {"command": "exa", "timeout": NaN}}}', None),
        ("absent", None),
        ("locked", None),
    ],
    ids=[
        "entry-string",
        "env-list",
        "env-int",
        "command-int",
        "args-int",
        "args-int-item",
        "top-list",
        "servers-list",
        "servers-empty",
        "servers-missing",
        "unparsable",
        "nan-constant",
        "absent",
        "locked-dir",
    ],
)
def test_a_wrong_shape_catalog_is_a_named_abort(tmp_path, catalog, tail):
    """(k), review pass 1: the emitter's own server catalog of a wrong shape — and an explicit `--defs` it cannot read
    at all, a missing file or one in a directory this user cannot search included — is a SystemExit naming the file
    and the entry, which check_mcp_scope prints as one FAIL line: never an AttributeError, a JSONDecodeError or a
    PermissionError traceback, and never a silent fall-back to mcp_defs.json (the run would emit the default servers
    while the operator named another catalog)."""
    p = tmp_path / "defs.json"
    locked = tmp_path / "locked"
    if catalog == "locked":
        locked.mkdir()
        p = locked / "defs.json"
        p.write_text(json.dumps({"mcpServers": {"exa": {"command": "exa"}}}))
        locked.chmod(0)
    elif catalog != "absent":
        p.write_text(catalog if isinstance(catalog, str) else json.dumps(catalog))
    try:
        if catalog == "locked" and os.access(locked, os.X_OK):
            pytest.skip("running as a user who can search a mode-000 directory")
        with pytest.raises(SystemExit) as exc:
            emitter._load_defs(str(p))
    finally:
        if catalog == "locked":
            locked.chmod(0o755)
    msg = str(exc.value)
    assert msg.startswith(f"emit_mcp: server definitions {p} "), msg
    assert msg.endswith(tail) if tail else "could not be read as JSON" in msg, msg


def test_a_well_formed_catalog_of_every_entry_shape_loads(tmp_path):
    """The mirror: the shapes the committed catalog carries — a stdio entry with args and env, a `type: http` entry
    with only a url, an entry with `"env": null`, one with no args — all still load."""
    p = tmp_path / "defs.json"
    servers = {
        "stdio": {"type": "stdio", "command": "x", "args": ["-y", "pkg"], "env": {"K": "v"}},
        "remote": {"type": "http", "url": "http://localhost:1/mcp"},
        "null-env": {"command": "x", "env": None},
        "bare": {"command": "x"},
    }
    p.write_text(json.dumps({"mcpServers": servers}))
    assert emitter._load_defs(str(p)) == servers
