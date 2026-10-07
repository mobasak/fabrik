#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/mcp-roster.md (per-type sets + per-repo overlays are CANONICAL there) · tests/test_emit_mcp_project_config.py · scripts/enforcement/check_mcp_scope.py | none
"""Emit each /opt repo's project-scope `.mcp.json` from the MCP split rulings.

Plan: docs/development/plans/2026-08-30-plan-3-mcp-split.md.
Authority: docs/DECISIONS.md D-003 + D-013..D-027; the per-type sets and
per-repo overlays below MIRROR docs/workstation/mcp-roster.md (canonical —
edit the roster first, then this table, same change; the AFTER-EDIT header
couples them).

Derivation per repo: universal 6 + per-type set (live `project.yaml::type`
read at run time) + per-repo overlay row. The hub gets the full defs set minus
HUB_EXCLUDE (the per-session heavy servers — operator ruling 2026-10-07); fabrik-lib keeps
the full roster, maestro included (the same ruling).
Server DEFINITIONS are read from --defs, else scripts/sysadmin/mcp_defs.json; their
`${VAR}` credentials are filled from the active fleet roster, then the hub .env, and an
unresolved one aborts the run naming the key (D-641) — the emitter's own prior output is
never a donor.

The emitted file is GITIGNORED fleet-wide (manifest gitignore group "MCP
config") because postgres-pro's env carries the repo's resolved DATABASE_URL
inline — `${VAR}` expansion reads the shell env, not the repo `.env`, so
inline-and-untracked is the deliberate shape (plan decision row 1).

Write-set contract: the ONLY path this script creates or mutates in a target
repo is `<repo>/.mcp.json` — never a commit, never another file (decision
row 2: sanctioned distribution path of the governance-sync class).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

UNIVERSAL6 = [
    "session-recall",
    "exa",
    "brave-search",
    "firecrawl",
    "postgres-pro",
    "serena",
]  # D-013 + D-020 + D-021

TYPE_SETS: dict[str, list[str]] = {
    # D-015 (+D-019 chrome-devtools rides with playwright) · D-014 shadcn/magicui saas
    "saas-skeleton": ["playwright", "chrome-devtools", "shadcn", "magicui"],
    "chrome-extension": ["playwright", "chrome-devtools"],
    "desktop-app": ["playwright", "chrome-devtools"],  # shadcn only via overlay (roster footnote 2)
    "static-site": ["playwright", "chrome-devtools"],
    "docusaurus": ["playwright", "chrome-devtools"],
    "office-extension": [
        "playwright",
        "chrome-devtools",
    ],  # PENDING type (roster row; proposal 01M19PSJN3)
    "mobile-app": ["maestro", "mobile-mcp"],  # D-014
    "python-api": [],
    "python-api-gpu": [],
    "node-api": [],
    "file-api": [],
    "file-worker": [],
    "wordpress": [],
}

# MIRRORS docs/workstation/mcp-roster.md § per-REPO overlays — keyed by repo dir name.
OVERLAYS: dict[str, list[str]] = {
    "web-ecommerce-factory": [
        "playwright",
        "chrome-devtools",
        "shadcn",
        "magicui",
        "pubchem",
        "media-engine",
    ],  # D-016/017/018/019/022
    "brand-identiy-creator": ["media-engine"],  # D-018
    "youtube": ["media-engine"],  # D-018
    "transdoc": ["fabrik-citation-verifier"],  # D-022-adjacent (pre-existing grant)
    "fabrik-citation-verifier": ["pubchem"],  # D-022 (claim-validator MCP pending build)
    "fabrik-claim-validator": ["fabrik-citation-verifier", "pubchem"],  # D-022
    "longephedia-vault": ["fabrik-citation-verifier", "pubchem"],  # D-025
    "supplement-tracker-advisor": ["fabrik-citation-verifier", "pubchem"],  # D-025
}

HUB_REPOS = {"fabrik"}  # hub-class (D-015); fabrik-lib is hub-class too but lands via its own agent
# The hub-class set is the full defs set MINUS the per-session heavy servers no hub task needs
# (operator ruling 2026-10-07, mail 01M4AR32MY): every hub window spawned a Maestro JVM and two
# browser servers; the JVMs outlived their sessions (48 orphans, ~11 GB swap after a hibernate
# resume). The hub keeps every light server (research, grafana, media-engine, shadcn/magicui,
# pubchem, the citation verifier) — a mobile or browser task runs in the owning repo.
HUB_EXCLUDE = {"maestro", "mobile-mcp", "playwright", "chrome-devtools"}  # the HUB only
HUB_CLASS = HUB_REPOS | {"fabrik-lib"}  # derivation only — never in the default sweep
# fabrik-lib KEEPS the full roster, maestro included (operator ruling 2026-10-07: "only mobile
# projects and fabrik-lib" need maestro — it vendors and tests the mobile modules); HUB_EXCLUDE
# applies to HUB_REPOS alone.
HUB_FULL_ROSTER = HUB_CLASS - HUB_REPOS
CONDEMNED = {"image-generation"}  # D-023 ARCHIVE pending with fleet — excluded BY NAME
NEVER_EMIT = {"fabrik-claim-validator"}  # D-022 planned row: no MCP endpoint exists yet

_TYPE_RE = re.compile(r"^type:\s*(\S+)\s*$", re.M)
_DBURL_RE = re.compile(r"^DATABASE_URL=(.+)$", re.M)


ROSTER_PATH = Path.home() / ".claude-fleet/active/.claude.json"  # the active account's roster
HUB_ENV_PATH = Path("/opt/fabrik/.env")  # the hub's own secret file (gitignored)
_PLACEHOLDER_RE = re.compile(r"^\$\{([A-Z0-9_]+)\}$")


def _env_file_values(path: Path) -> dict[str, str]:
    """`KEY=value` lines of a dotenv file (quotes stripped, comments and blanks ignored)."""
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        if k.startswith("export "):
            k = k[len("export ") :].strip()
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        if k and v:
            out[k] = v
    return out


def _fill_credentials(loaded: dict[str, dict]) -> list[str]:
    """Resolve every `${VAR}` placeholder in the catalog from the CANONICAL secret sources, in
    order: the active fleet roster (`ROSTER_PATH`, per-server env), then the hub `.env`
    (`HUB_ENV_PATH`, by variable name). Returns the placeholders still unresolved as
    `server.env.VAR` strings. The emitter's own prior output (`/opt/fabrik/.mcp.json`) is NEVER a
    donor (operator ruling 2026-10-07, D-641): filling from it re-wrote a revoked Grafana token
    twice while printing OK (01M1A3A698), and a rotated key can never be re-emitted stale when the
    only sources are the places a rotation is written to."""
    roster: dict[str, dict] = {}
    try:
        data = json.loads(ROSTER_PATH.read_text())
        roster = data.get("mcpServers") or {}
    except (OSError, ValueError):
        roster = {}
    dotenv = _env_file_values(HUB_ENV_PATH)
    unresolved: list[str] = []
    for name, entry in loaded.items():
        env = entry.get("env") or {}
        donor = (roster.get(name) or {}).get("env") or {}
        for k, v in env.items():
            if not (isinstance(v, str) and _PLACEHOLDER_RE.match(v)):
                continue
            var = _PLACEHOLDER_RE.match(v).group(1)
            candidates = (donor.get(k), dotenv.get(var))
            value = next((c for c in candidates if _is_credential(c)), None)
            if value is None:
                unresolved.append(f"{name}.env.{k}")
            else:
                env[k] = value
    # a PARTIAL placeholder (`prefix-${VAR}`) is neither a credential nor a template the chain can
    # fill: it is reported unresolved too, never emitted verbatim (review 2026-10-07, A-S5)
    for name, entry in loaded.items():
        for k, v in (entry.get("env") or {}).items():
            if isinstance(v, str) and "${" in v and f"{name}.env.{k}" not in unresolved:
                unresolved.append(f"{name}.env.{k}")
    return unresolved


def _is_credential(value: object) -> bool:
    """A donor value counts only when it is a non-empty string carrying no `${` — an unexpanded
    placeholder left in the roster or the hub .env is NOT a credential (review 2026-10-07, A-S1)."""
    return isinstance(value, str) and bool(value.strip()) and "${" not in value


def _load_defs(defs_arg: str | None) -> dict[str, dict]:
    """The server DEFINITIONS: `--defs`, else the hand-curated `mcp_defs.json` beside this script
    (the STATIC catalog heads the chain — BLOCKER regression, author-blind review 2026-08-30: the
    hub's own emitted .mcp.json is DERIVED/conditional and using it as the defs source stripped
    postgres-pro from every repo). Credentials are then filled by `_fill_credentials`; an
    unresolved one FAILS the run naming the key — never a silent placeholder, never the prior
    output."""
    candidates = ([Path(defs_arg)] if defs_arg else []) + [
        Path(__file__).resolve().parent / "mcp_defs.json",
    ]
    loaded: dict[str, dict] | None = None
    for p in candidates:
        if not p.is_file():
            continue
        data = json.loads(p.read_text())
        servers = data.get("mcpServers")
        if isinstance(servers, dict) and servers:
            loaded = json.loads(json.dumps(servers))  # deep copy
            break
    if loaded is None:
        raise SystemExit("emit_mcp: no server definitions source found (pass --defs)")
    unresolved = _fill_credentials(loaded)
    if unresolved:
        raise SystemExit(
            "emit_mcp: credential(s) unresolved — "
            + ", ".join(unresolved)
            + f" — set them in the fleet roster ({ROSTER_PATH}) or {HUB_ENV_PATH}; the emitter never "
            "fills a credential from its own prior output (D-641), so nothing was written"
        )
    return loaded


def _repo_type(repo: Path) -> str | None:
    py = repo / "project.yaml"
    if not py.is_file():
        return None
    m = _TYPE_RE.search(py.read_text(encoding="utf-8", errors="replace"))
    return m.group(1) if m else None


def _database_url(repo: Path) -> str | None:
    env = repo / ".env"
    if not env.is_file():
        return None
    try:
        m = _DBURL_RE.search(env.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    if not m:
        return None
    # .mcp.json is consumed ONLY by WSL windows (box-local, gitignored): rewrite the
    # VPS-side container-DNS host to the WSL env-layer form (CLAUDE.md two-envs law).
    # Verbatim postgres-main made postgres-mcp block 31.5s in a DNS-failing pool retry,
    # past Claude's 30s handshake timeout (live defect 2026-08-30, hub + apidoccreator).
    url = m.group(1).strip().replace("@postgres-main:", "@localhost:")
    # SQLAlchemy dialect suffixes (postgresql+asyncpg://...) choke psycopg's parser
    # AND postgres-mcp itself — normalize for both the probe and the emitted URI
    # (3 live repos were wrongly denied the server; author-blind review 2026-08-30).
    return re.sub(r"^postgres(ql)?\+\w+://", "postgresql://", url)


def _uri_connects(uri: str) -> bool | None:
    """True/False = probed; None = no probe available (psycopg missing everywhere).

    postgres-mcp v1.29 blocks its MCP handshake ~30s on ANY non-connecting URI
    (DNS and auth failures alike, both measured 2026-08-30) — past Claude's 30s
    connect timeout. So a URI is emitted only when it PROVABLY connects; an
    omitted env means the server starts unconnected in ~2s with tools present.
    """
    probe = "import psycopg,sys; psycopg.connect(sys.argv[1], connect_timeout=3).close()"
    for py in (sys.executable, "/opt/fabrik/.venv/bin/python"):
        if not Path(py).exists():
            continue
        try:
            r = subprocess.run([py, "-c", probe, uri], capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        if b"ModuleNotFoundError" in r.stderr:
            continue  # this interpreter has no psycopg — try the next
        return r.returncode == 0
    return None


def ruled_server_names(repo: Path, defs: dict[str, dict]) -> list[str] | None:
    """The NAMES a repo's ruling allows, in emission order, or None for a repo the ruling does
    not know (no `project.yaml::type`, or a type outside TYPE_SETS). No probe runs here — this is
    the roster side of the contract, shared with `scripts/enforcement/check_mcp_scope.py`, which
    grades every emitted `.mcp.json` as a SUBSET of it (an entry absent-until-configured, such as
    postgres-pro without a connecting URL, is a legal omission; an extra server is not)."""
    name = repo.name
    if name in HUB_CLASS:
        drop = set() if name in HUB_FULL_ROSTER else HUB_EXCLUDE
        wanted = [s for s in defs if s not in NEVER_EMIT and s not in drop]
    else:
        rtype = _repo_type(repo)
        if rtype is None or rtype not in TYPE_SETS:
            return None
        wanted = list(UNIVERSAL6) + TYPE_SETS[rtype] + OVERLAYS.get(name, [])
    return [s for s in dict.fromkeys(wanted) if s not in NEVER_EMIT and s in defs]


def derive_servers(repo: Path, defs: dict[str, dict]) -> dict[str, dict] | None:
    """The repo's ruled server map, or None to skip (with reason printed by caller)."""
    wanted = ruled_server_names(repo, defs)
    if wanted is None:
        return None
    out: dict[str, dict] = {}
    for s in dict.fromkeys(wanted):  # ordered de-dup
        if s in NEVER_EMIT or s not in defs:
            continue
        entry = json.loads(json.dumps(defs[s]))  # deep copy
        if s == "postgres-pro":
            # postgres-mcp v1.29 blocks its handshake ~30s on ANY non-connecting URI
            # and refuses to start with none — a repo without a PROVEN-connecting
            # DATABASE_URL gets NO entry (absent-until-configured; re-emission
            # restores it). None = unprobeable → trust the URI.
            url = _database_url(repo)
            if not url or _uri_connects(url) is False:
                continue
            entry.pop("env", None)
            entry["env"] = {"DATABASE_URI": url}
        out[s] = entry
    return out


def emit_repo(repo: Path, defs: dict[str, dict], check: bool) -> str:
    servers = derive_servers(repo, defs)
    if servers is None:
        return "SKIP"
    target = repo / ".mcp.json"
    payload = json.dumps({"mcpServers": servers}, indent=2, sort_keys=True) + "\n"
    if target.is_file() and target.read_text() == payload:
        return "OK"
    verdict = "UPDATE" if target.exists() else "CREATE"
    if not check:
        target.write_text(payload)
    return verdict


def _candidate_repos(root: Path) -> list[Path]:
    out = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name in CONDEMNED or d.name in (HUB_CLASS - HUB_REPOS):
            continue  # fabrik-lib is hub-class for derivation (--repo) but its own agent lands the file
        if not (d / ".git").exists():
            continue
        if d.name in HUB_REPOS or (d / "project.yaml").is_file():
            out.append(d)
    return out


def main(argv: list[str] | None = None) -> list[str]:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default="/opt", help="directory holding the repos (default /opt)")
    ap.add_argument("--repo", help="single repo path instead of a full-root run")
    ap.add_argument("--defs", help="server-definitions JSON (mcpServers shape)")
    ap.add_argument("--check", action="store_true", help="report only, never write")
    args = ap.parse_args(argv)

    defs = _load_defs(args.defs)
    repos = [Path(args.repo)] if args.repo else _candidate_repos(Path(args.root))
    lines: list[str] = []
    for repo in repos:
        try:
            verdict = emit_repo(repo, defs, args.check)
        except Exception as exc:  # one bad repo never strands the rest (plan A1 test 11)
            verdict = f"SKIP (unreadable: {type(exc).__name__})"
        line = f"{repo.name}: {verdict}"
        lines.append(line)
        print(line)
    return lines


if __name__ == "__main__":
    main()
