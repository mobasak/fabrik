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
    "fabrik-citation-verifier",
    "grafana",
    "fabrik-scrape",
]
UNIVERSAL = {
    "session-recall",
    "exa",
    "brave-search",
    "firecrawl",
    "postgres-pro",
    "serena",
    "fabrik-scrape",
}
U5_NO_DB = UNIVERSAL - {"postgres-pro"}  # absent-until-configured (no connecting DATABASE_URL)


@pytest.fixture()
def defs_file(tmp_path: Path) -> Path:
    defs = {
        name: {"type": "stdio", "command": "npx", "args": ["-y", f"{name}-mcp"]}
        for name in ALL_SERVERS
    }
    defs["fabrik-citation-verifier"] = {"type": "http", "url": "http://127.0.0.1:8033/mcp"}
    defs["fabrik-scrape"] = {"type": "http", "url": "http://127.0.0.1:8034/mcp"}
    p = tmp_path / "defs.json"
    p.write_text(json.dumps({"mcpServers": defs}))
    return p


SERVICE_UNITS = {
    "fabrik-scrape": "fabrik-scrape-mcp.service",
    "fabrik-citation-verifier": "fabrik-citation-verifier-mcp.service",
}


def _install_units(unit_dir: Path, units, enabled: bool = True) -> None:
    """Lay out `units` the way `systemctl enable` leaves them: the file, plus its `*.wants/` link."""
    wants = unit_dir / "multi-user.target.wants"
    wants.mkdir(parents=True, exist_ok=True)
    for unit in units:
        (unit_dir / unit).write_text("[Unit]\n")
        if enabled:
            (wants / unit).symlink_to(unit_dir / unit)


@pytest.fixture(autouse=True)
def unit_dir(tmp_path: Path, monkeypatch) -> Path:
    """Every service unit installed and enabled by default (W-07298e38), so no test reads the box's
    /etc/systemd/system — the env var reaches the real-subprocess scaffold test too."""
    d = tmp_path / "systemd"
    _install_units(d, SERVICE_UNITS.values())
    monkeypatch.setenv("FABRIK_SYSTEMD_UNIT_DIR", str(d))
    monkeypatch.setattr(emitter, "UNIT_DIR", d, raising=False)
    return d


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


def test_headless_gets_exactly_the_universal_set(tmp_path, defs_file, monkeypatch):
    monkeypatch.setattr(emitter, "_uri_connects", lambda uri: True)
    r = make_repo(
        tmp_path, "some-api", "python-api", env="DATABASE_URL=postgresql://u:p@localhost:5432/x\n"
    )
    run(tmp_path, defs_file)
    assert servers_of(r) == UNIVERSAL


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
    r = make_repo(
        tmp_path,
        "db-api",
        "python-api",
        env="DATABASE_URL=postgresql://u:p@localhost:5432/db_api\n",
    )
    run(tmp_path, defs_file)
    entry = json.loads((r / ".mcp.json").read_text())["mcpServers"]["postgres-pro"]
    assert entry["env"]["DATABASE_URI"] == "postgresql://u:p@localhost:5432/db_api"


def test_postgres_pro_env_omitted_when_uri_refused(tmp_path, defs_file):
    """REAL probe, deterministic refusal: a closed local port refuses instantly."""
    r = make_repo(
        tmp_path,
        "dead-db-api",
        "python-api",
        env="DATABASE_URL=postgresql://u:p@localhost:59999/nope\n",
    )
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


def test_hub_gets_full_defs_set_minus_the_heavy_four(tmp_path, defs_file):
    """Operator ruling 2026-10-07 (mail 01M4AR32MY): the hub-class set is every light server, never
    maestro / mobile-mcp / playwright / chrome-devtools — those spawn a JVM or a browser per
    session and outlived their sessions by days (48 orphans after a hibernate resume)."""
    r = make_repo(tmp_path, "fabrik", None)
    run(tmp_path, defs_file)
    heavy = {"maestro", "mobile-mcp", "playwright", "chrome-devtools"}
    assert (
        servers_of(r) == set(ALL_SERVERS) - {"postgres-pro"} - heavy
    )  # no connecting DB in the fixture
    assert not (servers_of(r) & heavy)


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


def test_scaffold_helper_emits_mcp_config(tmp_path, monkeypatch):
    """Plan-3 follow-up (operator 2026-08-30): NEW projects get their .mcp.json at
    scaffold time via scaffold._emit_mcp_config — crash-safe, real emitter subprocess. It runs
    only inside a provisioning opt-in (W-e2f0b6e5)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from fabrik.scaffold import _emit_mcp_config, provisioning

    monkeypatch.delenv("FABRIK_SCAFFOLD_OFFLINE", raising=False)
    repo = make_repo(tmp_path, "fresh-api", "python-api")
    with provisioning():
        _emit_mcp_config(repo)
    assert (repo / ".mcp.json").exists(), "scaffold must emit the repo's ruled .mcp.json"
    assert servers_of(repo) == U5_NO_DB


def test_postgres_pro_container_host_rewritten_to_localhost(tmp_path, defs_file):
    """Live defect 2026-08-30: a .env DATABASE_URL carrying the VPS-side container
    host (postgres-main) made postgres-mcp block 31.5s in a DNS-failing pool retry
    — past Claude's 30s handshake timeout. .mcp.json is consumed ONLY by WSL
    windows, where the env-layer host mapping is localhost (CLAUDE.md two-envs law)."""
    seen = {}
    r = make_repo(
        tmp_path,
        "vps-env-api",
        "python-api",
        env="DATABASE_URL=postgresql://u:p@postgres-main:5432/appdb\n",
    )
    real = emitter._uri_connects
    emitter._uri_connects = lambda uri: seen.setdefault("uri", uri) and True
    try:
        run(tmp_path, defs_file)
    finally:
        emitter._uri_connects = real
    assert seen["uri"] == "postgresql://u:p@localhost:5432/appdb", (
        "probe must see the LOCALHOST form"
    )
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
    r = make_repo(
        tmp_path,
        "async-api",
        "python-api",
        env="DATABASE_URL=postgresql+asyncpg://u:p@localhost:5432/adb\n",
    )
    run(tmp_path, defs_file)
    assert seen["uri"] == "postgresql://u:p@localhost:5432/adb"
    entry = json.loads((r / ".mcp.json").read_text())["mcpServers"]["postgres-pro"]
    assert entry["env"]["DATABASE_URI"] == "postgresql://u:p@localhost:5432/adb"


def test_catalog_placeholders_are_filled_from_the_roster_never_left_as_placeholders(
    tmp_path, monkeypatch
):
    """Push-protection regression 2026-08-30 + D-641: the committed catalog carries ${VAR}
    placeholders only; _load_defs fills them from the CANONICAL sources (the fleet roster, then the
    hub .env) and never leaves one standing — nor reads the emitter's own prior output."""
    cat = tmp_path / "cat.json"
    cat.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "grafana": {
                        "command": "docker",
                        "args": [],
                        "env": {
                            "GRAFANA_SERVICE_ACCOUNT_TOKEN": "${GRAFANA_SERVICE_ACCOUNT_TOKEN}"
                        },
                    }
                }
            }
        )
    )
    roster = tmp_path / "roster.json"
    roster.write_text(
        json.dumps(
            {"mcpServers": {"grafana": {"env": {"GRAFANA_SERVICE_ACCOUNT_TOKEN": "glsa-live"}}}}
        )
    )
    monkeypatch.setattr(emitter, "ROSTER_PATH", roster)
    monkeypatch.setattr(emitter, "HUB_ENV_PATH", tmp_path / "absent.env")
    defs = emitter._load_defs(str(cat))
    assert defs["grafana"]["env"]["GRAFANA_SERVICE_ACCOUNT_TOKEN"] == "glsa-live"


def test_committed_catalog_carries_no_token_shapes():
    """The catalog is a COMMITTED file: placeholders only, never live credentials."""
    import re as _re

    txt = (Path(__file__).resolve().parent.parent / "scripts/sysadmin/mcp_defs.json").read_text()
    assert not _re.search(r"glsa_|sk-[A-Za-z0-9]{20}|fc-[A-Za-z0-9]{20}", txt)
    assert "${GRAFANA_SERVICE_ACCOUNT_TOKEN}" in txt


def test_an_own_agent_hub_class_repo_is_never_swept_by_default_but_derives_hub_class(
    tmp_path, defs_file
):
    """fabrik-lib is hub-class for derivation (`--repo /opt/fabrik-lib`, run by ITS agent) and must
    stay out of the default sweep even if it ever gains a project.yaml (review 2026-10-07, A-S2);
    it keeps the FULL roster, maestro included (operator ruling 2026-10-07)."""
    lib = make_repo(tmp_path, "fabrik-lib", "python-api")
    run(tmp_path, defs_file)
    assert not (lib / ".mcp.json").exists(), "the default sweep must not land fabrik-lib's file"
    emitter.main(["--root", str(tmp_path), "--defs", str(defs_file), "--repo", str(lib)])
    got = servers_of(lib)
    # operator ruling 2026-10-07: maestro is for mobile projects AND fabrik-lib — it keeps the full
    # roster; HUB_EXCLUDE trims the hub alone
    assert {"grafana", "maestro", "mobile-mcp"} <= got, got
    assert got == set(ALL_SERVERS) - {"postgres-pro"}


def _placeholder_defs(tmp_path: Path) -> Path:
    p = tmp_path / "defs-ph.json"
    p.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "exa": {
                        "type": "stdio",
                        "command": "/usr/bin/exa-mcp",
                        "env": {"EXA_API_KEY": "${EXA_API_KEY}"},
                    },
                    "grafana": {
                        "type": "stdio",
                        "command": "docker",
                        "args": ["run", "mcp/grafana"],
                        "env": {
                            "GRAFANA_SERVICE_ACCOUNT_TOKEN": "${GRAFANA_SERVICE_ACCOUNT_TOKEN}",
                            "GRAFANA_URL": "https://g",
                        },
                    },
                }
            }
        )
    )
    return p


def test_credentials_come_from_the_roster_then_the_hub_env_never_the_prior_output(
    tmp_path, monkeypatch
):
    """Operator follow-up (b) on 1c22b3de1 / D-641: a rotated key must reach the emitted file and the
    emitter's own prior .mcp.json is never a donor."""
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({"mcpServers": {"exa": {"env": {"EXA_API_KEY": "exa-ROTATED"}}}}))
    dotenv = tmp_path / "hub.env"
    dotenv.write_text("# hub\nGRAFANA_SERVICE_ACCOUNT_TOKEN='glsa-FRESH'\nUNRELATED=1\n")
    monkeypatch.setattr(emitter, "ROSTER_PATH", roster)
    monkeypatch.setattr(emitter, "HUB_ENV_PATH", dotenv)
    stale = tmp_path / "fabrik" / ".mcp.json"  # the hub's prior output carries STALE values
    stale.parent.mkdir()
    stale.write_text(json.dumps({"mcpServers": {"exa": {"env": {"EXA_API_KEY": "exa-STALE"}}}}))
    defs = emitter._load_defs(str(_placeholder_defs(tmp_path)))
    assert defs["exa"]["env"]["EXA_API_KEY"] == "exa-ROTATED"
    assert defs["grafana"]["env"]["GRAFANA_SERVICE_ACCOUNT_TOKEN"] == "glsa-FRESH"
    assert defs["grafana"]["env"]["GRAFANA_URL"] == "https://g"


def test_an_unresolved_credential_aborts_naming_the_key(tmp_path, monkeypatch):
    monkeypatch.setattr(emitter, "ROSTER_PATH", tmp_path / "no-roster.json")
    monkeypatch.setattr(emitter, "HUB_ENV_PATH", tmp_path / "no.env")
    with pytest.raises(SystemExit) as exc:
        emitter._load_defs(str(_placeholder_defs(tmp_path)))
    msg = str(exc.value)
    assert "exa.env.EXA_API_KEY" in msg and "grafana.env.GRAFANA_SERVICE_ACCOUNT_TOKEN" in msg
    assert "prior output" in msg


def test_a_placeholder_left_in_the_hub_env_or_a_partial_placeholder_is_unresolved(
    tmp_path, monkeypatch
):
    """A-S1 / A-S5 (review 2026-10-07): `${VAR}` written into the hub .env is not a credential, and a
    composite `prefix-${VAR}` in the catalog is never emitted verbatim — both abort naming the key."""
    monkeypatch.setattr(emitter, "ROSTER_PATH", tmp_path / "no-roster.json")
    dotenv = tmp_path / "hub.env"
    dotenv.write_text("EXA_API_KEY=${EXA_API_KEY}\nGRAFANA_SERVICE_ACCOUNT_TOKEN=glsa-ok\n")
    monkeypatch.setattr(emitter, "HUB_ENV_PATH", dotenv)
    cat = tmp_path / "cat.json"
    cat.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "exa": {
                        "command": "/usr/bin/exa-mcp",
                        "env": {"EXA_API_KEY": "${EXA_API_KEY}"},
                    },
                    "grafana": {
                        "command": "docker",
                        "args": ["run", "mcp/grafana"],
                        "env": {
                            "GRAFANA_SERVICE_ACCOUNT_TOKEN": "${GRAFANA_SERVICE_ACCOUNT_TOKEN}",
                            "GRAFANA_URL": "https://${HOST}/g",
                        },
                    },
                }
            }
        )
    )
    with pytest.raises(SystemExit) as exc:
        emitter._load_defs(str(cat))
    msg = str(exc.value)
    assert "exa.env.EXA_API_KEY" in msg and "grafana.env.GRAFANA_URL" in msg
    assert "GRAFANA_SERVICE_ACCOUNT_TOKEN" not in msg


CATALOG = Path(__file__).resolve().parent.parent / "scripts/sysadmin/mcp_defs.json"


def test_rea_is_an_absolute_local_stdio_launch_never_a_package_runner():
    """W-eff97ae7: REA reaches a session through this catalog, never through its own `setup`
    (which writes ~/.claude.json and a personal skill). The entry launches the global install the
    roster pins (docs/workstation/mcp-roster.md § REA — the version lives there, not in the path) —
    an `npx -y rea-agents@latest` entry would fetch and run whatever the registry serves at each
    session start, and run its dependencies' install scripts."""
    entry = json.loads(CATALOG.read_text())["mcpServers"]["rea"]
    assert entry["type"] == "stdio" and entry["args"] == ["mcp"], entry
    assert entry["command"].startswith("/") and entry["command"].endswith("/bin/rea-agents"), entry
    assert "npx" not in json.dumps(entry) and "@latest" not in json.dumps(entry), entry
    assert entry["env"] == {}, "REA takes no credential"


def test_rea_reaches_the_hub_class_and_no_project_type(tmp_path):
    """The roster row (D-1199, W-eff97ae7): REA is a hub-class server — the hub and fabrik-lib —
    and no scaffold type carries it; a project gains it by an overlay row (roster first), never by
    hand."""
    defs = json.loads(CATALOG.read_text())["mcpServers"]
    assert "rea" in emitter.ruled_server_names(make_repo(tmp_path, "fabrik", None), defs)
    assert "rea" in emitter.ruled_server_names(make_repo(tmp_path, "fabrik-lib", None), defs)
    for rtype in emitter.TYPE_SETS:
        repo = make_repo(tmp_path, f"p-{rtype}", rtype)
        assert "rea" not in emitter.ruled_server_names(repo, defs), rtype


def _fresh_unit_dir(tmp_path: Path, monkeypatch, **state: str) -> Path:
    """A unit dir where each SERVICE_UNITS server is `enabled`, `installed` (file only) or `absent`."""
    d = tmp_path / "systemd-fresh"
    d.mkdir()
    for server, unit in SERVICE_UNITS.items():
        how = state.get(server.replace("-", "_"), "enabled")
        if how != "absent":
            _install_units(d, [unit], enabled=how == "enabled")
    monkeypatch.setattr(emitter, "UNIT_DIR", d)
    return d


_WITHHELD = "withheld: fabrik-scrape (unit fabrik-scrape-mcp.service not installed and enabled)"


@pytest.mark.parametrize("how", ["absent", "installed"])
def test_a_service_without_its_enabled_unit_is_withheld_and_named(
    tmp_path, defs_file, monkeypatch, how
):
    """W-07298e38: fabrik-scrape shipped to the hub .mcp.json with no unit behind it — a dead entry in
    every session. A unit that is absent, or copied in but never enabled, withholds the server and the
    verdict says so."""
    _fresh_unit_dir(tmp_path, monkeypatch, fabrik_scrape=how)
    r = make_repo(tmp_path, "some-api", "python-api")
    defs = emitter._load_defs(str(defs_file))
    assert emitter.emit_repo(r, defs, check=False) == f"CREATE — {_WITHHELD}"
    assert servers_of(r) == U5_NO_DB - {"fabrik-scrape"}
    assert emitter.emit_repo(r, defs, check=False) == f"OK — {_WITHHELD}"


def test_the_hub_withholds_an_uninstalled_service_too(tmp_path, defs_file, monkeypatch):
    _fresh_unit_dir(
        tmp_path, monkeypatch, fabrik_scrape="absent", fabrik_citation_verifier="installed"
    )
    r = make_repo(tmp_path, "fabrik", None)
    run(tmp_path, defs_file)
    got = servers_of(r)
    assert "fabrik-scrape" not in got and "fabrik-citation-verifier" not in got
    assert "grafana" in got and "session-recall" in got


def test_an_unreadable_unit_dir_withholds_not_skips(tmp_path, defs_file, monkeypatch):
    """`Path.is_file()` raises PermissionError under an unreadable directory; unwrapped it would escape to
    main's `SKIP (unreadable …)` and leave a stale file carrying the dead entry in place."""
    d = _fresh_unit_dir(tmp_path, monkeypatch)
    root = tmp_path / "opt"  # the sweep root, apart from the unreadable unit dir
    r = make_repo(root, "some-api", "python-api")
    (r / ".mcp.json").write_text(json.dumps({"mcpServers": {"fabrik-scrape": {}}}))
    d.chmod(0)
    try:
        lines = run(root, defs_file)
    finally:
        d.chmod(0o755)
    assert not any("SKIP" in line for line in lines), lines
    assert "fabrik-scrape" not in servers_of(r)


def test_a_withheld_service_stays_ruled(tmp_path, defs_file, monkeypatch):
    """check_mcp_scope grades present ⊆ ruled: the ruling must still name a withheld server, so the
    omission reads as legal (absent-until-configured, like postgres-pro)."""
    _fresh_unit_dir(tmp_path, monkeypatch, fabrik_scrape="absent")
    r = make_repo(tmp_path, "some-api", "python-api")
    defs = emitter._load_defs(str(defs_file))
    assert "fabrik-scrape" in emitter.ruled_server_names(r, defs)
    assert "fabrik-scrape" not in emitter.derive_servers(r, defs)


def test_every_loopback_http_def_names_its_unit():
    """The next loopback service MCP must not skip the guard: every catalog entry served on this box's
    loopback names the systemd unit that serves it."""
    from urllib.parse import urlparse

    for name, entry in json.loads(CATALOG.read_text())["mcpServers"].items():
        host = urlparse(entry.get("url") or "").hostname
        if host in ("127.0.0.1", "localhost", "::1"):
            assert name in emitter.SERVICE_UNITS, (
                f"{name} serves {entry['url']} with no SERVICE_UNITS row"
            )
    assert emitter.SERVICE_UNITS == SERVICE_UNITS
