# AFTER-EDIT: scripts/sysadmin/emit_mcp_project_config.py | none
"""Plan-3 A1 — the emitter's 11 contracted behaviors, written red-first.

Real temp-dir fixture repos with real project.yaml/.env files; the live /opt
tree is never a test target. Server DEFINITIONS come from a fixture defs file
passed via --defs, so no test depends on the box's live rosters.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
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
    "rea",
]
UNIVERSAL = {
    "session-recall",
    "exa",
    "brave-search",
    "firecrawl",
    "postgres-pro",
    "serena",
    "fabrik-scrape",
    "rea",
}
U5_NO_DB = UNIVERSAL - {"postgres-pro"}  # absent-until-configured (no connecting DATABASE_URL)


@pytest.fixture(autouse=True)
def _hermetic_git(tmp_path, monkeypatch):
    """The gitignore guard asks git: the box's global or system excludes must not decide these tests."""
    empty = tmp_path / "empty.gitconfig"
    empty.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


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


def make_repo(
    root: Path, name: str, rtype: str | None, env: str | None = None, real_git: bool = True
) -> Path:
    """A REAL git repo whose .gitignore ignores `.mcp.json`, as every scaffolded repo's does (the emitter asks git for
    every repo, W-c0d9cea5); `real_git=False` makes a bare `.git` dir git cannot answer for."""
    d = root / name
    if real_git:
        d.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(d)], check=True)
        (d / ".gitignore").write_text(".mcp.json\n")
    else:
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


def test_untyped_gitless_and_unguarded_repos(tmp_path, defs_file, capsys):
    """D-1246 ("rea must be available to system wide for all repos"): an untyped git repo gets the universal
    set — but only when its .gitignore keeps `.mcp.json` out of git, since the file carries filled credentials;
    image-generation is no longer excluded by name; a non-git dir and fabrik-lib are still skipped."""
    guarded = git_repo(tmp_path, "no-yaml", "node_modules/\n.mcp.json\n")
    unguarded = git_repo(tmp_path, "vendor-clone", "node_modules/\n")
    gitless = tmp_path / "not-a-repo"
    gitless.mkdir()
    (gitless / "project.yaml").write_text("name: not-a-repo\ntype: python-api\n")
    formerly_condemned = make_repo(tmp_path, "image-generation", "python-api")
    lib = make_repo(tmp_path, "fabrik-lib", None)
    run(tmp_path, defs_file)
    assert servers_of(guarded) == U5_NO_DB
    assert not (unguarded / ".mcp.json").exists(), "no gitignore line, no secrets file"
    out = capsys.readouterr().out
    assert "vendor-clone: SKIP (git does not ignore `.mcp.json`" in out
    # a `.git` git cannot read: no answer, never written, and the line says so
    unanswerable = make_repo(tmp_path, "unanswerable", None, real_git=False)
    run(tmp_path, defs_file)
    assert not (unanswerable / ".mcp.json").exists()
    assert "unanswerable: SKIP (git could not say" in capsys.readouterr().out
    assert not (gitless / ".mcp.json").exists()
    assert servers_of(formerly_condemned) == U5_NO_DB
    assert not (lib / ".mcp.json").exists(), "fabrik-lib's own agent lands its file"


def git_repo(root: Path, name: str, gitignore: str | None) -> Path:
    """A REAL git repo (the guard asks `git check-ignore`), untyped, with an optional .gitignore."""
    d = root / name
    d.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(d)], check=True)
    if gitignore is not None:
        (d / ".gitignore").write_text(gitignore)
    return d


@pytest.mark.parametrize(
    "gitignore, emitted",
    [
        ("x\n.mcp.json\n", True),
        ("x\n/.mcp.json\n", True),
        ("*.json\n", True),  # any rule git honours counts
        ("x\n# .mcp.json\n", False),
        ("x\n.mcp.json.bak\n", False),
        (".mcp.json\n!.mcp.json\n", False),  # a later negation un-ignores it
        (None, False),
    ],
    ids=["plain", "rooted", "glob", "comment", "other-file", "negated", "no-gitignore"],
)
def test_the_gitignore_guard_asks_git(tmp_path, defs_file, gitignore, emitted):
    repo = git_repo(tmp_path, "untyped", gitignore)
    run(tmp_path, defs_file)
    assert (repo / ".mcp.json").exists() is emitted


def test_the_gitignore_guard_refuses_a_tracked_file(tmp_path, defs_file):
    """A tracked .mcp.json is not ignored whatever .gitignore says: inlined keys would be committed."""
    repo = git_repo(tmp_path, "untyped", "x\n")
    (repo / ".mcp.json").write_text('{"mcpServers": {}}\n')
    subprocess.run(["git", "-C", str(repo), "add", "-f", ".mcp.json"], check=True)
    (repo / ".gitignore").write_text(".mcp.json\n")
    run(tmp_path, defs_file)
    assert (repo / ".mcp.json").read_text() == '{"mcpServers": {}}\n', "never overwritten"


def test_untyped_repo_gets_the_universal_set_and_an_unknown_type_stays_unruled(tmp_path):
    defs = {n: {"command": n} for n in ALL_SERVERS}
    untyped = make_repo(tmp_path, "rn-kit-sandbox", None)
    no_type_line = make_repo(tmp_path, "half", None)
    (no_type_line / "project.yaml").write_text("name: half\n")
    typo = make_repo(tmp_path, "typo-saas", "sass-skeleton")
    unparsed = make_repo(tmp_path, "quoted", None)
    (unparsed / "project.yaml").write_text('name: quoted\ntype: "python api"\n')
    commented = make_repo(tmp_path, "commented", None)
    (commented / "project.yaml").write_text("name: commented\ntype: saas-skeleton  # web\n")
    assert set(emitter.ruled_server_names(untyped, defs)) == UNIVERSAL
    assert set(emitter.ruled_server_names(no_type_line, defs)) == UNIVERSAL
    assert emitter.ruled_server_names(typo, defs) is None, "a typo stays a visible SKIP"
    assert emitter.ruled_server_names(unparsed, defs) is None, (
        "an unreadable type line is not untyped"
    )
    assert "playwright" in emitter.ruled_server_names(commented, defs), "a trailing comment is read"
    # YAML reads `#` as a comment only after whitespace, and an empty `type:` is no type the roster knows
    for name, line in (("glued", "type: saas-skeleton#web"), ("empty", "type:")):
        r = make_repo(tmp_path, name, None)
        (r / "project.yaml").write_text(f"name: {name}\n{line}\nother: x\n")
        assert emitter.ruled_server_names(r, defs) is None, line


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


def test_malformed_yaml_reads_as_untyped_and_the_run_continues(tmp_path, defs_file, capsys):
    """A project.yaml with no `type:` line is untyped (D-1246): with no gitignore line it is skipped, said by
    name, and the rest of the run still emits."""
    bad = make_repo(tmp_path, "broken", None)
    (bad / ".gitignore").unlink()
    (bad / "project.yaml").write_text("::: not yaml :::\n")
    good = make_repo(tmp_path, "good-api", "python-api")
    run(tmp_path, defs_file)
    assert not (bad / ".mcp.json").exists()
    assert (good / ".mcp.json").exists(), "one bad repo must not strand the rest"
    assert "broken: SKIP" in capsys.readouterr().out


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


def test_rea_reaches_every_repo_the_emitter_serves(tmp_path):
    """D-1239 (operator 2026-10-26: "enable rea for all repos wide asap!!!") supersedes D-1199's
    hub-class-only grant: REA is in the universal set, so every scaffold type carries it with no
    overlay row; the hub and fabrik-lib carry it through the full catalog."""
    defs = json.loads(CATALOG.read_text())["mcpServers"]
    assert "rea" in emitter.UNIVERSAL
    assert "rea" in emitter.ruled_server_names(make_repo(tmp_path, "fabrik", None), defs)
    assert "rea" in emitter.ruled_server_names(make_repo(tmp_path, "fabrik-lib", None), defs)
    for rtype in emitter.TYPE_SETS:
        repo = make_repo(tmp_path, f"p-{rtype}", rtype)
        assert "rea" in emitter.ruled_server_names(repo, defs), rtype


def test_existing_worktree_copies_are_refreshed_and_none_is_created(tmp_path, defs_file):
    """W-7e29c9b9: `.worktreeinclude` copies `.mcp.json` into a linked worktree only at creation, so a
    re-emission that rewrote the repo root alone left 214 of 215 worktree copies without `rea`. The
    emitter refreshes every EXISTING copy under `<repo>/.claude/worktrees/*/` with the root's payload;
    it creates none, leaves a symlinked copy alone, and `--check` writes nothing."""
    repo = make_repo(tmp_path, "some-api", "python-api")
    wts = repo / ".claude" / "worktrees"
    stale, bare, linked = wts / "wt1", wts / "wt2", wts / "wt3"
    for w in (stale, bare, linked):
        w.mkdir(parents=True)
    (stale / ".mcp.json").write_text('{"mcpServers": {"session-recall": {}}}\n')
    target = tmp_path / "elsewhere.json"
    target.write_text("{}\n")
    (linked / ".mcp.json").symlink_to(target)

    lines = run(tmp_path, defs_file, check=True)
    assert stale.joinpath(".mcp.json").read_text() == '{"mcpServers": {"session-recall": {}}}\n'
    assert any("1 worktree cop" in line for line in lines), lines

    lines = run(tmp_path, defs_file)
    assert servers_of(stale) == servers_of(repo) == U5_NO_DB
    assert not (bare / ".mcp.json").exists(), "a worktree without a copy gets none"
    assert target.read_text() == "{}\n", "a symlinked copy is never written through"
    assert run(tmp_path, defs_file) == ["some-api: OK"], "a refreshed copy reads OK next time"


def test_a_symlinked_worktree_directory_is_never_followed(tmp_path, defs_file):
    """Review pass 2 (N1): `/opt/fabrik/.claude/worktrees/fabrik-lib -> /opt/fabrik-lib` is a real entry
    on this box; following it would write the hub's set over fabrik-lib's own file (D-638 keeps it the
    full roster). Only a copy whose worktree directory lives inside `<repo>/.claude/worktrees` counts."""
    repo = make_repo(tmp_path, "some-api", "python-api")
    other = tmp_path / "elsewhere"
    other.mkdir()
    (other / ".mcp.json").write_text("{}\n")
    wts = repo / ".claude" / "worktrees"
    wts.mkdir(parents=True)
    (wts / "linked").symlink_to(other, target_is_directory=True)
    run(tmp_path, defs_file)
    assert (other / ".mcp.json").read_text() == "{}\n", (
        "a symlinked worktree dir must not be written through"
    )


def test_an_unreadable_worktree_copy_never_blocks_the_root(tmp_path, defs_file):
    """Review pass 2 (N2): a copy the emitter cannot read (invalid UTF-8 here; a permission error is the
    same class) is reported in the verdict and skipped — the repo's root and its other copies still land."""
    repo = make_repo(tmp_path, "some-api", "python-api")
    wts = repo / ".claude" / "worktrees"
    bad, good = wts / "bad", wts / "good"
    for w in (bad, good):
        w.mkdir(parents=True)
    (bad / ".mcp.json").write_bytes(b"\xff\xfe\x00broken")
    (good / ".mcp.json").write_text("{}\n")
    lines = run(tmp_path, defs_file)
    assert servers_of(repo) == U5_NO_DB, lines
    assert servers_of(good) == U5_NO_DB, lines
    assert any("1 unreadable" in line for line in lines), lines


def test_a_symlinked_claude_directory_is_never_followed(tmp_path, defs_file):
    """Review pass 3 (P1): a symlink HIGHER in the path (`<repo>/.claude -> elsewhere`) must not carry the
    refresh outside the repo — a copy counts only when its real path is `<repo>/.claude/worktrees/<dir>/`."""
    repo = make_repo(tmp_path, "some-api", "python-api")
    ext = tmp_path / "ext"
    (ext / "worktrees" / "w").mkdir(parents=True)
    (ext / "worktrees" / "w" / ".mcp.json").write_text("{}\n")
    (repo / ".claude").symlink_to(ext, target_is_directory=True)
    run(tmp_path, defs_file)
    assert (ext / "worktrees" / "w" / ".mcp.json").read_text() == "{}\n"


def test_a_copy_that_cannot_be_written_is_reported_as_unwritable(tmp_path, defs_file):
    """Review pass 3 (P2): a readable copy the emitter cannot write says so — never "unreadable"."""
    repo = make_repo(tmp_path, "some-api", "python-api")
    w = repo / ".claude" / "worktrees" / "w"
    w.mkdir(parents=True)
    copy = w / ".mcp.json"
    copy.write_text("{}\n")
    copy.chmod(0o444)
    try:
        lines = run(tmp_path, defs_file)
    finally:
        copy.chmod(0o644)
    assert any("1 unwritable" in line for line in lines), lines


def test_an_in_repo_alias_of_a_worktree_is_counted_once(tmp_path, defs_file):
    """Review pass 4 (Q1): two entries naming the same real worktree directory are one copy, so `--check`
    predicts exactly what the real run does."""
    repo = make_repo(tmp_path, "some-api", "python-api")
    wts = repo / ".claude" / "worktrees"
    (wts / "w").mkdir(parents=True)
    (wts / "w" / ".mcp.json").write_text("{}\n")
    (wts / "alias").symlink_to(wts / "w", target_is_directory=True)
    assert run(tmp_path, defs_file, check=True) == ["some-api: CREATE (+1 worktree copy)"]


def test_a_root_that_cannot_be_written_is_skipped_as_an_error_not_unreadable(tmp_path, defs_file):
    """Review pass 4 (P4-4): a failure writing the ROOT names its exception without calling it a read failure."""
    repo = make_repo(tmp_path, "some-api", "python-api")
    (repo / ".mcp.json").write_text("{}\n")
    (repo / ".mcp.json").chmod(0o444)
    try:
        lines = run(tmp_path, defs_file)
    finally:
        (repo / ".mcp.json").chmod(0o644)
    assert lines == ["some-api: SKIP (error: PermissionError)"], lines


_STUB_PSYCOPG = """
import os


class _Conn:
    def close(self):
        pass


def connect(dsn, connect_timeout=None):
    with open("/proc/self/cmdline", "rb") as f:
        argv = f.read()
    with open(os.environ["STUB_PSYCOPG_LOG"], "ab") as f:
        f.write(argv + b"\\n")
    if dsn != os.environ["STUB_PSYCOPG_DSN"]:
        raise RuntimeError("refused")
    return _Conn()
"""


def test_the_uri_probe_hands_the_child_the_uri_and_never_its_argv(tmp_path, monkeypatch):
    """W-d095d60b: a resolved DATABASE_URL carries a password, and a child's argv is readable by every local user in
    `ps` and /proc/<pid>/cmdline. The REAL probe child runs here, against a stub psycopg that records its own
    cmdline: it must receive the exact URI (a non-ASCII password included) and its argv must not carry it."""
    (tmp_path / "stub" / "psycopg").mkdir(parents=True)
    (tmp_path / "stub" / "psycopg" / "__init__.py").write_text(_STUB_PSYCOPG)
    log = tmp_path / "cmdline.log"
    uri = "postgresql://owner:s3cretPWé@db.example:5432/app"
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "stub"))
    monkeypatch.setenv("STUB_PSYCOPG_LOG", str(log))
    monkeypatch.setenv("STUB_PSYCOPG_DSN", uri)
    assert emitter._uri_connects(uri) is True
    assert emitter._uri_connects(uri.replace("s3cret", "wrong")) is False
    seen = log.read_bytes()
    assert seen.count(b"\n") == 2, seen  # both probes reached the stub's connect
    assert b"s3cretPW" not in seen and b"wrong" not in seen, seen


def _cli_rc(root: Path, defs: Path) -> int:
    """The script run as a PROCESS, so its `__main__` wiring is what is graded."""
    r = subprocess.run(
        [sys.executable, str(_SCRIPT), "--root", str(root), "--defs", str(defs)],
        capture_output=True,
        timeout=60,
    )
    return r.returncode


def test_the_script_exits_1_when_a_repo_or_a_copy_fails_and_0_on_a_ruled_skip(tmp_path, defs_file):
    """W-d095d60b: the script exits 1 when a verdict is `_failed` (an exception, a worktree copy left unwritten,
    git unable to answer) and 0 on a clean run or a ruled SKIP (an unknown type is a policy verdict)."""
    make_repo(tmp_path, "typo-type", "no-such-type")
    repo = make_repo(tmp_path, "some-api", "python-api")
    assert _cli_rc(tmp_path, defs_file) == 0
    assert "typo-type: SKIP" in run(tmp_path, defs_file, check=True)

    (repo / ".mcp.json").write_text("{}\n")
    (repo / ".mcp.json").chmod(0o444)
    try:
        assert _cli_rc(tmp_path, defs_file) == 1
    finally:
        (repo / ".mcp.json").chmod(0o644)

    assert _cli_rc(tmp_path, defs_file) == 0
    copy = repo / ".claude" / "worktrees" / "w" / ".mcp.json"
    copy.parent.mkdir(parents=True)
    copy.write_text("{}\n")
    copy.chmod(0o444)
    try:
        assert _cli_rc(tmp_path, defs_file) == 1
    finally:
        copy.chmod(0o644)


@pytest.mark.parametrize(
    ("verdict", "failed"),
    [
        ("OK", False),
        ("CREATE (+1 worktree copy)", False),
        ("SKIP", False),
        (
            "SKIP (git does not ignore `.mcp.json` — make .gitignore ignore it, with no later `!.mcp.json`, and if git"
            " tracks it run `git rm --cached .mcp.json`; the file carries credentials)",
            False,
        ),
        ("SKIP (error: PermissionError)", True),
        (
            "SKIP (git could not say whether `.mcp.json` is ignored — never written)",
            True,
        ),
        ("OK (1 unreadable)", True),
        ("UPDATE (+2 worktree copies, 1 unwritable)", True),
    ],
)
def test_failed_reads_the_verdict_only(verdict, failed):
    """W-d095d60b: which verdicts fail the run. A repo NAME holding the error text never does (main passes the
    verdict, not the printed line)."""
    assert emitter._failed(verdict) is failed


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
    )


def _not_ignored(repo: Path, shape: str) -> None:
    """Put `<repo>/.mcp.json` in one shape git does NOT ignore (measured, W-c0d9cea5 measure.md)."""
    if shape == "no-rule":
        (repo / ".gitignore").unlink()
    elif shape == "negation":
        (repo / ".gitignore").write_text(".mcp.json\n!.mcp.json\n")
    else:  # tracked, or tracked with skip-worktree (the trade-intelligence shape: git status hides the filled copy)
        _git(repo, "add", "-f", ".gitignore", ".mcp.json")
        _git(repo, "commit", "-q", "-m", "tracked")
        if shape == "skip-worktree":
            _git(repo, "update-index", "--skip-worktree", ".mcp.json")


@pytest.mark.parametrize("shape", ["skip-worktree", "tracked", "no-rule", "negation"])
@pytest.mark.parametrize("name, rtype", [("some-api", "python-api"), ("fabrik", None)])
def test_a_typed_repo_whose_file_git_tracks_is_never_written(
    tmp_path, defs_file, capsys, shape, name, rtype
):
    """W-c0d9cea5: the emitted file inlines credentials, so a TYPED or HUB repo whose `.mcp.json` git does not ignore
    (tracked, skip-worktree, no rule, a later `!`) is never written; the file keeps its bytes and the line says how to
    fix it. A rule alone is no fix for a tracked file, so the line names both steps."""
    repo = make_repo(tmp_path, name, rtype)
    (repo / ".mcp.json").write_text('{"placeholder": "${EXA_API_KEY}"}\n')
    _not_ignored(repo, shape)
    before = (repo / ".mcp.json").read_bytes()
    lines = run(tmp_path, defs_file)
    assert (repo / ".mcp.json").read_bytes() == before
    verdict = next(v for v in lines if v.startswith(f"{name}: "))
    assert verdict.startswith(f"{name}: SKIP (git does not ignore `.mcp.json`"), verdict
    assert "git rm --cached .mcp.json" in verdict and "!.mcp.json" in verdict, verdict
    assert not emitter._failed(verdict.split(": ", 1)[1]), "a ruled SKIP: the repo's owner fixes it"


def test_a_typed_repo_whose_file_git_ignores_is_written(tmp_path, defs_file):
    """W-c0d9cea5: a typed repo whose .gitignore ignores `.mcp.json` is written, from no file at all (the fresh-scaffold
    case: git answers for a path that does not exist yet)."""
    repo = make_repo(tmp_path, "some-api", "python-api")
    assert not (repo / ".mcp.json").exists()
    assert run(tmp_path, defs_file) == ["some-api: CREATE"]
    assert servers_of(repo)


def test_a_typed_repo_git_cannot_answer_for_fails_the_run(tmp_path, defs_file):
    """W-c0d9cea5: a typed repo git cannot answer for (a bare `.git` dir) is never written, and that verdict fails the
    run, since nothing may be written on an unknown answer."""
    repo = make_repo(tmp_path, "some-api", "python-api", real_git=False)
    lines = run(tmp_path, defs_file)
    assert not (repo / ".mcp.json").exists()
    assert lines == [
        "some-api: SKIP (git could not say whether `.mcp.json` is ignored — never written)"
    ], lines
    assert _cli_rc(tmp_path, defs_file) == 1
