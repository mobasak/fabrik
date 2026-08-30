# AFTER-EDIT: scripts/sysadmin/emit_mcp_project_config.py | none
"""Plan-3 A1 — the emitter's 11 contracted behaviors, written red-first.

Real temp-dir fixture repos with real project.yaml/.env files; the live /opt
tree is never a test target. Server DEFINITIONS come from a fixture defs file
passed via --defs, so no test depends on the box's live rosters.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts/sysadmin/emit_mcp_project_config.py"
_spec = importlib.util.spec_from_file_location("emit_mcp_project_config", _SCRIPT)
emitter = importlib.util.module_from_spec(_spec)
sys.modules["emit_mcp_project_config"] = emitter
_spec.loader.exec_module(_spec and emitter)

ALL_SERVERS = [
    "session-recall", "exa", "brave-search", "firecrawl", "postgres-pro", "serena",
    "playwright", "chrome-devtools", "shadcn", "magicui", "maestro", "mobile-mcp",
    "pubchem", "media-engine", "fabrik-citation-verifier", "grafana",
]
UNIVERSAL6 = {"session-recall", "exa", "brave-search", "firecrawl", "postgres-pro", "serena"}
U5_NO_DB = UNIVERSAL6 - {"postgres-pro"}  # absent-until-configured (no connecting DATABASE_URL)


@pytest.fixture()
def defs_file(tmp_path: Path) -> Path:
    defs = {
        name: {"type": "stdio", "command": "npx", "args": ["-y", f"{name}-mcp"]}
        for name in ALL_SERVERS
    }
    defs["fabrik-citation-verifier"] = {"type": "http", "url": "http://127.0.0.1:8033/mcp"}
    p = tmp_path / "defs.json"
    p.write_text(json.dumps({"mcpServers": defs}))
    return p


def make_repo(root: Path, name: str, rtype: str | None, env: str | None = None) -> Path:
    d = root / name
    (d / ".git").mkdir(parents=True)
    if rtype is not None:
        (d / "project.yaml").write_text(f"name: {name}\ntype: {rtype}\n")
    if env is not None:
        (d / ".env").write_text(env)
    return d


def run(root: Path, defs: Path, check: bool = False) -> list[str]:
    argv = ["--root", str(root), "--defs", str(defs)]
    if check:
        argv.append("--check")
    return emitter.main(argv)


def servers_of(repo: Path) -> set[str]:
    return set(json.loads((repo / ".mcp.json").read_text())["mcpServers"])


def test_headless_gets_exactly_universal_6(tmp_path, defs_file, monkeypatch):
    monkeypatch.setattr(emitter, "_uri_connects", lambda uri: True)
    r = make_repo(tmp_path, "some-api", "python-api",
                  env="DATABASE_URL=postgresql://u:p@localhost:5432/x\n")
    run(tmp_path, defs_file)
    assert servers_of(r) == UNIVERSAL6


def test_saas_adds_the_web_gui_four(tmp_path, defs_file):
    r = make_repo(tmp_path, "some-saas", "saas-skeleton")
    run(tmp_path, defs_file)
    assert servers_of(r) == U5_NO_DB | {"playwright", "chrome-devtools", "shadcn", "magicui"}


def test_wef_overlay_includes_media_engine_d018(tmp_path, defs_file):
    r = make_repo(tmp_path, "web-ecommerce-factory", "saas-skeleton")
    run(tmp_path, defs_file)
    got = servers_of(r)
    assert {"media-engine", "pubchem"} <= got, "D-016/017/018/019/022 overlay grants missing"
    assert {"playwright", "chrome-devtools", "shadcn", "magicui"} <= got


def test_health_repos_get_d025_overlays(tmp_path, defs_file):
    r = make_repo(tmp_path, "supplement-tracker-advisor", "mobile-app")
    run(tmp_path, defs_file)
    got = servers_of(r)
    assert {"fabrik-citation-verifier", "pubchem"} <= got, "D-025 health overlays missing"
    assert {"maestro", "mobile-mcp"} <= got


def test_postgres_pro_env_only_when_uri_connects(tmp_path, defs_file, monkeypatch):
    """The URI is emitted ONLY if it provably connects at emission time — postgres-mcp
    v1.29 blocks its MCP handshake ~30s on ANY non-connecting URI (DNS and auth alike,
    both measured 2026-08-30), which reads as a dead server in Claude's 30s timeout."""
    monkeypatch.setattr(emitter, "_uri_connects", lambda uri: True)
    r = make_repo(tmp_path, "db-api", "python-api",
                  env="DATABASE_URL=postgresql://u:p@localhost:5432/db_api\n")
    run(tmp_path, defs_file)
    entry = json.loads((r / ".mcp.json").read_text())["mcpServers"]["postgres-pro"]
    assert entry["env"]["DATABASE_URI"] == "postgresql://u:p@localhost:5432/db_api"


def test_postgres_pro_env_omitted_when_uri_refused(tmp_path, defs_file):
    """REAL probe, deterministic refusal: a closed local port refuses instantly."""
    r = make_repo(tmp_path, "dead-db-api", "python-api",
                  env="DATABASE_URL=postgresql://u:p@localhost:59999/nope\n")
    run(tmp_path, defs_file)
    assert "postgres-pro" not in servers_of(r)


def test_postgres_pro_absent_when_no_database_url(tmp_path, defs_file):
    """postgres-mcp blocks ~30s on ANY non-connecting URI and refuses to start with
    none — so a repo without a working DB gets NO entry (absent-until-configured);
    re-emission restores it when .env gains a connecting DATABASE_URL."""
    r = make_repo(tmp_path, "plain-api", "python-api", env="OTHER=1\n")
    run(tmp_path, defs_file)
    assert "postgres-pro" not in servers_of(r)


def test_idempotent_second_run_writes_nothing(tmp_path, defs_file):
    r = make_repo(tmp_path, "some-api", "python-api")
    run(tmp_path, defs_file)
    before = (r / ".mcp.json").stat().st_mtime_ns
    run(tmp_path, defs_file)
    assert (r / ".mcp.json").stat().st_mtime_ns == before


def test_check_mode_never_writes(tmp_path, defs_file):
    r = make_repo(tmp_path, "some-api", "python-api")
    run(tmp_path, defs_file, check=True)
    assert not (r / ".mcp.json").exists()


def test_untyped_gitless_and_condemned_skipped(tmp_path, defs_file):
    untyped = make_repo(tmp_path, "no-yaml", None)
    gitless = tmp_path / "not-a-repo"
    gitless.mkdir()
    (gitless / "project.yaml").write_text("name: not-a-repo\ntype: python-api\n")
    condemned = make_repo(tmp_path, "image-generation", "python-api")
    run(tmp_path, defs_file)
    assert not (untyped / ".mcp.json").exists()
    assert not (gitless / ".mcp.json").exists()
    assert not (condemned / ".mcp.json").exists(), "condemned repo must be skipped BY NAME"


def test_claim_validator_never_emitted(tmp_path, defs_file):
    r = make_repo(tmp_path, "fabrik-claim-validator", "python-api")
    run(tmp_path, defs_file)
    assert "fabrik-claim-validator" not in servers_of(r)
    assert {"fabrik-citation-verifier", "pubchem"} <= servers_of(r)


def test_hub_gets_full_defs_set(tmp_path, defs_file):
    r = make_repo(tmp_path, "fabrik", None)
    run(tmp_path, defs_file)
    assert servers_of(r) == set(ALL_SERVERS) - {"postgres-pro"}  # no connecting DB in the fixture


def test_write_set_containment(tmp_path, defs_file):
    make_repo(tmp_path, "some-api", "python-api", env="DATABASE_URL=postgresql://x@h/d\n")
    before = {p.relative_to(tmp_path) for p in tmp_path.rglob("*")}
    run(tmp_path, defs_file)
    after = {p.relative_to(tmp_path) for p in tmp_path.rglob("*")}
    assert after - before == {Path("some-api/.mcp.json")}


def test_malformed_yaml_skipped_run_continues(tmp_path, defs_file, capsys):
    bad = make_repo(tmp_path, "broken", None)
    (bad / "project.yaml").write_text("::: not yaml :::\n")
    good = make_repo(tmp_path, "good-api", "python-api")
    run(tmp_path, defs_file)
    assert not (bad / ".mcp.json").exists()
    assert (good / ".mcp.json").exists(), "one bad repo must not strand the rest"
    assert "broken" in capsys.readouterr().out


def test_scaffold_helper_emits_mcp_config(tmp_path):
    """Plan-3 follow-up (operator 2026-08-30): NEW projects get their .mcp.json at
    scaffold time via scaffold._emit_mcp_config — crash-safe, real emitter subprocess."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from fabrik.scaffold import _emit_mcp_config

    repo = make_repo(tmp_path, "fresh-api", "python-api")
    _emit_mcp_config(repo)
    assert (repo / ".mcp.json").exists(), "scaffold must emit the repo's ruled .mcp.json"
    assert servers_of(repo) == U5_NO_DB


def test_postgres_pro_container_host_rewritten_to_localhost(tmp_path, defs_file):
    """Live defect 2026-08-30: a .env DATABASE_URL carrying the VPS-side container
    host (postgres-main) made postgres-mcp block 31.5s in a DNS-failing pool retry
    — past Claude's 30s handshake timeout. .mcp.json is consumed ONLY by WSL
    windows, where the env-layer host mapping is localhost (CLAUDE.md two-envs law)."""
    seen = {}
    r = make_repo(tmp_path, "vps-env-api", "python-api",
                  env="DATABASE_URL=postgresql://u:p@postgres-main:5432/appdb\n")
    real = emitter._uri_connects
    emitter._uri_connects = lambda uri: seen.setdefault("uri", uri) and True
    try:
        run(tmp_path, defs_file)
    finally:
        emitter._uri_connects = real
    assert seen["uri"] == "postgresql://u:p@localhost:5432/appdb", "probe must see the LOCALHOST form"
    entry = json.loads((r / ".mcp.json").read_text())["mcpServers"]["postgres-pro"]
    assert entry["env"]["DATABASE_URI"] == "postgresql://u:p@localhost:5432/appdb"


def test_default_defs_chain_always_carries_postgres_pro():
    """BLOCKER regression (author-blind review 2026-08-30): the hub's own emitted
    .mcp.json lost postgres-pro (D-031) while ALSO being the default defs source —
    a default-invocation re-emission silently deleted the server from every
    qualifying repo. The static catalog (mcp_defs.json) now heads the chain and
    must always carry the full template set."""
    defs = emitter._load_defs(None)
    assert "postgres-pro" in defs, "the defs chain must never lose a ruled server's template"
    assert "context7" not in defs and "github" not in defs, "retired servers stay out"


def test_sqlalchemy_driver_suffix_normalized(tmp_path, defs_file, monkeypatch):
    """MAJOR regression: postgresql+asyncpg:// DSNs failed the psycopg probe AND would
    choke postgres-mcp itself — normalize the scheme for both probe and emission."""
    seen = {}
    monkeypatch.setattr(emitter, "_uri_connects", lambda uri: seen.setdefault("uri", uri) and True)
    r = make_repo(tmp_path, "async-api", "python-api",
                  env="DATABASE_URL=postgresql+asyncpg://u:p@localhost:5432/adb\n")
    run(tmp_path, defs_file)
    assert seen["uri"] == "postgresql://u:p@localhost:5432/adb"
    entry = json.loads((r / ".mcp.json").read_text())["mcpServers"]["postgres-pro"]
    assert entry["env"]["DATABASE_URI"] == "postgresql://u:p@localhost:5432/adb"
