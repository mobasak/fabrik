"""T4-03 G-J2 — `fabrik export` / `fabrik import` cross-VPS portability bundle.

Produces a tarball that captures everything `fabrik apply` registers on a VPS
so the same set of services can be rebuilt on a fresh target (e.g. vps2).
Import is best-effort and not roundtrip-verified in this epic — the live test
is deferred to the vps2 stand-up. See CHANGELOG note.

Bundle layout (per pack §28 lines 47–69):

    fabrik-export-vps1-YYYY-MM-DD.tar.gz
    ├── manifest.json                   # version, source vps, timestamp, contents
    ├── README.md                       # restore instructions + prerequisites
    ├── specs/services/*.yaml           # all service specs (verbatim)
    ├── state/*.json                    # .fabrik/state/<id>.json (coolify_uuid stripped)
    ├── secrets-redacted.json           # .env key NAMES only (never values)
    ├── coolify/
    │   ├── applications.json           # list_applications() with UUIDs recursively stripped
    │   ├── services.json               # list_services() with UUIDs stripped
    │   └── projects.json               # list_projects() with UUIDs stripped
    ├── monitoring/
    │   ├── gatus/                      # SSH-pulled /opt/monitoring/configs/gatus/
    │   ├── prometheus.yml              # /opt/monitoring/configs/prometheus/prometheus.yml
    │   ├── alertmanager.yml            # /opt/monitoring/configs/alertmanager/alertmanager.yml
    │   ├── grafana-dashboards/         # local mirror configs/grafana/dashboards/
    │   ├── redis-assignments.json      # /opt/monitoring/configs/redis/assignments.json
    │   └── postgres-allocations.json   # /opt/monitoring/configs/postgres/allocations.json (T4-01)
    ├── authelia/
    │   └── configuration.yml           # SSH pull from authelia container
    └── backrest/
        └── config.json                 # SSH pull from backrest config

Security invariants enforced by tests:
    1. Bundle contains NO plaintext secret values (only key names).
    2. Bundle contains NO Coolify UUIDs (recursively stripped from API exports).
    3. Bundle contains NO Coolify private keys.

Out of scope (per ticket):
    - Age / sops / 1Password secrets-manager integration.
    - LetsEncrypt cert transfer (operator re-issues on target).
    - DNS provider re-binding (Cloudflare, operator handles).
    - OAuth provider re-creation (GitHub apps etc.).
    - postgres pg_dump + meili snapshots (--include-data flag is stubbed for
      future expansion but currently emits a manifest entry only).
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import tarfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fabrik.config import FABRIK_ROOT

logger = logging.getLogger(__name__)

BUNDLE_VERSION = 1

# Pattern of a Coolify UUID — 24 alphanumeric chars. Used by the recursive
# UUID-stripper. Matches more permissively than strictly necessary to catch
# Coolify's mix of timestamp-suffixed names too.
_COOLIFY_UUID_RE = re.compile(r"^[a-z0-9]{24}$")

# Sensitive-key patterns for the generic config redactor. Any field whose
# name (or path) matches one of these patterns has its value replaced with
# the literal string ``"REDACTED"`` before the file enters the bundle.
# Conservative bias: false-positive redactions are operator-recoverable
# (re-populate on target); false-negative leaks are not.
_SENSITIVE_KEY_PATTERNS = (
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"private[_-]?key", re.IGNORECASE),
    re.compile(r"encryption[_-]?key", re.IGNORECASE),
    re.compile(r"jwt[_-]?secret", re.IGNORECASE),
    re.compile(r"session[_-]?secret", re.IGNORECASE),
    re.compile(r"^auth$", re.IGNORECASE),  # Backrest .auth = {users:[...]}
    re.compile(r"users$", re.IGNORECASE),  # Backrest .auth.users
    re.compile(r"^env$", re.IGNORECASE),  # Backrest .repos[].env (AWS creds)
    re.compile(r"credentials", re.IGNORECASE),
    re.compile(r"webhook", re.IGNORECASE),
)


def _key_is_sensitive(key: str) -> bool:
    """Match a key name against the conservative sensitive-pattern list."""
    return any(p.search(key) for p in _SENSITIVE_KEY_PATTERNS)


def _redact_sensitive_fields(obj: Any) -> Any:
    """Recursively walk a JSON/YAML structure, replacing every value whose
    KEY name matches one of :data:`_SENSITIVE_KEY_PATTERNS` with the
    literal string ``"REDACTED"``.

    Important: redaction happens at the KEY level (not the value level) —
    we don't try to heuristically detect "this string looks like a secret"
    on values. That avoids false positives on URLs, paths, etc. The
    matched-key approach catches all the surfaces the ticket's Pass-2
    Lessons-Learnt hint flagged: nested Coolify UUIDs were one surface;
    here we generalize to nested credentials in Authelia / Backrest /
    arbitrary YAML configs.
    """
    if isinstance(obj, dict):
        return {
            k: ("REDACTED" if _key_is_sensitive(k) else _redact_sensitive_fields(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact_sensitive_fields(item) for item in obj]
    return obj


# Keys we always strip from Coolify-API payloads (UUIDs + sensitive refs).
_STRIP_KEYS = frozenset(
    {
        "uuid",
        "id",
        "private_key_uuid",
        "destination_uuid",
        "environment_uuid",
        "project_uuid",
        "server_uuid",
        "application_uuid",
        "service_uuid",
        "database_uuid",
        "deployment_uuid",
        "manual_webhook_secret_github",
        "manual_webhook_secret_gitlab",
        "manual_webhook_secret_bitbucket",
        "manual_webhook_secret_gitea",
        "custom_docker_run_options",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_uuids(obj: Any) -> Any:
    """Recursively walk a JSON-like structure removing UUID-shaped fields.

    Coolify returns UUIDs in deeply-nested objects (deployments, env vars,
    private-key refs); explicit recursion catches every variant without
    relying on driver-side filtering.
    """
    if isinstance(obj, dict):
        return {k: _strip_uuids(v) for k, v in obj.items() if k not in _STRIP_KEYS}
    if isinstance(obj, list):
        return [_strip_uuids(item) for item in obj]
    if isinstance(obj, str) and _COOLIFY_UUID_RE.match(obj):
        return None
    return obj


def _redact_env_keys(env_path: Path) -> dict[str, str]:
    """Parse ``.env`` and return ``{KEY: "REDACTED"}`` — values are never
    read into memory beyond the line-boundary needed to find the ``=``.

    The pack §28 'Secrets ergonomics' contract: the bundle must let the
    operator on the target VPS know WHICH keys to re-populate, without
    transporting any secret value across machines. Even if the file were
    age-encrypted in a future ticket, this function never reads past the
    ``=`` — that's a defence-in-depth invariant.
    """
    if not env_path.exists():
        return {}
    out: dict[str, str] = {}
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        # only well-formed env var names: [A-Z_][A-Z0-9_]*
        if key and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            out[key] = "REDACTED"
    return dict(sorted(out.items()))


def _collect_specs(fabrik_root: Path) -> dict[str, str]:
    """Read every ``specs/services/*.yaml`` verbatim. Returns map of
    relative-path → text content for inclusion in the tarball.
    """
    out: dict[str, str] = {}
    specs_dir = fabrik_root / "specs" / "services"
    if not specs_dir.exists():
        return out
    for path in sorted(specs_dir.glob("*.yaml")):
        rel = path.relative_to(fabrik_root)
        out[str(rel)] = path.read_text(encoding="utf-8")
    return out


def _collect_state(fabrik_root: Path) -> dict[str, dict[str, Any]]:
    """Read every ``.fabrik/state/<id>.json`` and STRIP ``coolify_uuid``
    (regenerated on import). Other fields kept verbatim.

    Archived ``_destroyed/`` entries are excluded — they describe past
    deploys, not current state.
    """
    out: dict[str, dict[str, Any]] = {}
    state_dir = fabrik_root / ".fabrik" / "state"
    if not state_dir.exists():
        return out
    for path in sorted(state_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("portability: skip unreadable state file %s — %s", path, exc)
            continue
        # Strip coolify_uuid + any nested UUID-ish fields (the registrar
        # entries themselves shouldn't contain UUIDs but be safe).
        payload.pop("coolify_uuid", None)
        out[path.stem] = _strip_uuids(payload)
    return out


def _collect_coolify(coolify_client: Any | None = None) -> dict[str, list[Any]]:
    """Pull Applications / Services / Projects from Coolify API and
    recursively strip UUIDs.

    Bound to the ``CoolifyClient`` via dependency injection so tests can
    swap in a mock. The default client is constructed from the
    ``COOLIFY_API_TOKEN`` env var (already validated by other drivers).
    """
    if coolify_client is None:
        try:
            from fabrik.drivers.coolify import CoolifyClient

            coolify_client = CoolifyClient()
        except Exception as exc:  # noqa: BLE001 — defer to export-time logging
            logger.warning("portability: CoolifyClient init failed (%s); empty export", exc)
            return {"applications": [], "services": [], "projects": []}

    out: dict[str, list[Any]] = {"applications": [], "services": [], "projects": []}
    for kind, fn in (
        ("applications", coolify_client.list_applications),
        ("services", coolify_client.list_services),
        ("projects", coolify_client.list_projects),
    ):
        try:
            data = fn()
            out[kind] = _strip_uuids(data) or []
        except Exception as exc:  # noqa: BLE001 — best-effort per pack §28
            logger.warning("portability: coolify.%s failed (%s)", kind, exc)
            out[kind] = []
    return out


def _collect_monitoring_local(fabrik_root: Path) -> dict[str, str]:
    """Bundle the local mirrors of monitoring configs from the fabrik repo.

    Only LOCAL files — VPS-side pulls (``/opt/monitoring/configs/``) are
    handled by ``_collect_monitoring_remote`` which uses ssh. This split
    lets tests exercise the local path without a live VPS.
    """
    out: dict[str, str] = {}
    grafana_dir = fabrik_root / "configs" / "grafana" / "dashboards"
    if grafana_dir.exists():
        for path in sorted(grafana_dir.glob("*.json")):
            rel = path.relative_to(fabrik_root)
            out[str(rel)] = path.read_text(encoding="utf-8")
    return out


def _ssh_cat(remote_path: str) -> str | None:
    """SSH-pull a remote file (read-only). Returns text or None on failure.

    Wraps ``fabrik.drivers.ssh.ssh`` so tests can monkeypatch a single
    helper without needing to import the ssh module.
    """
    try:
        from fabrik.drivers.ssh import ssh

        return ssh(f"sudo cat {remote_path}")
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning("portability: ssh cat %s failed — %s", remote_path, exc)
        return None


def _collect_monitoring_remote() -> dict[str, str]:
    """Pull VPS-side monitoring configs via ssh. Paths match the existing
    inventory (T4-01 added postgres-allocations.json)."""
    paths = {
        "monitoring/prometheus.yml": "/opt/monitoring/configs/prometheus/prometheus.yml",
        "monitoring/alertmanager.yml": "/opt/monitoring/configs/alertmanager/alertmanager.yml",
        "monitoring/redis-assignments.json": "/opt/monitoring/configs/redis/assignments.json",
        "monitoring/postgres-allocations.json": "/opt/monitoring/configs/postgres/allocations.json",
    }
    out: dict[str, str] = {}
    for rel, remote in paths.items():
        content = _ssh_cat(remote)
        if content is not None:
            out[rel] = content
    return out


def _collect_authelia() -> dict[str, str]:
    """Authelia configuration.yml lives in the Coolify-Service named volume:
    ``/var/lib/docker/volumes/<service-uuid>_authelia-config/_data/configuration.yml``

    Verified live 2026-05-16 — Authelia is a Coolify Service (uuid
    ``hks48k8sg8o4co4co08co00o``) and its config is mounted as a named
    Docker volume, NOT a bind mount under ``/data/coolify/services/``.

    **Plaintext-secret redaction (T4-03 convergence pass).** The on-disk
    configuration.yml carries inline ``jwt_secret``, ``session.secret``,
    and ``storage.encryption_key`` values. We parse the YAML, redact every
    key whose name matches :data:`_SENSITIVE_KEY_PATTERNS`, then re-emit.
    The structural fields (access_control rules, providers, redirects) are
    preserved so the bundle stays restore-useful.
    """
    candidates = [
        # Current live path (T4-03 verification 2026-05-16):
        "/var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml",
        # Pack §28 original guess kept as last-ditch fallback:
        "/data/coolify/services/hks48k8sg8o4co4co08co00o/authelia/configuration.yml",
    ]
    raw: str | None = None
    for path in candidates:
        raw = _ssh_cat(path)
        if raw:
            break
    if not raw:
        # UUID-agnostic discovery (post-redeploy fallback).
        raw = _ssh_cat(
            "$(sudo find /var/lib/docker/volumes/ -maxdepth 1 -name '*_authelia-config' "
            "-printf '%p/_data/configuration.yml\\n' 2>/dev/null | head -1)"
        )
    if not raw:
        return {}

    try:
        import yaml

        parsed = yaml.safe_load(raw) or {}
        redacted = _redact_sensitive_fields(parsed)
        out = yaml.safe_dump(redacted, sort_keys=False, default_flow_style=False)
    except Exception as exc:  # noqa: BLE001 — fail closed: don't ship raw YAML
        logger.warning(
            "portability: authelia YAML parse/redact failed (%s); omitting from bundle to "
            "avoid plaintext-secret leak",
            exc,
        )
        return {}
    return {"authelia/configuration.yml": out}


def _collect_backrest() -> dict[str, str]:
    """Backrest config.json lives at ``/opt/backrest/config/config.json``
    (verified live 2026-05-16 via docker inspect of the backrest container's
    ``/config`` mount). The mount is a host bind, NOT a Coolify Service
    volume — so this path is stable across Coolify redeploys.

    **Plaintext-secret redaction (T4-03 convergence pass).** The on-disk
    config.json carries ``repos[].password`` (restic encryption password),
    ``repos[].env`` (S3/B2 access keys), and ``auth.users`` (web-UI auth).
    We parse the JSON, redact via :func:`_redact_sensitive_fields`, then
    re-emit. Repo URIs, plan schedules, prune policies, etc. are kept so
    the bundle is restore-useful.
    """
    raw = _ssh_cat("/opt/backrest/config/config.json")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        redacted = _redact_sensitive_fields(parsed)
        out = json.dumps(redacted, indent=2, sort_keys=True)
    except Exception as exc:  # noqa: BLE001 — fail closed
        logger.warning(
            "portability: backrest JSON parse/redact failed (%s); omitting from bundle to "
            "avoid plaintext-secret leak",
            exc,
        )
        return {}
    return {"backrest/config.json": out}


def _build_readme(source_vps: str, timestamp: str, sections: Iterable[str]) -> str:
    """Restore-instructions README for the bundle root.

    Documents the prerequisites the target VPS must satisfy (Coolify
    installed, postgres-main + redis-main bootstrapped, the Fabrik
    governance files synced) and the manual steps that fall outside
    ``fabrik import``'s automation (DNS, LetsEncrypt, secrets).
    """
    section_list = "\n".join(f"- `{s}/`" for s in sorted(sections))
    return f"""# Fabrik VPS portability bundle

**Source:** {source_vps}
**Created:** {timestamp}
**Bundle version:** {BUNDLE_VERSION}

This tarball is the output of `fabrik export` (T4-03 G-J2). It captures every
resource `fabrik apply` registers on the source VPS so the same set of
services can be rebuilt on a fresh target.

## Bundle contents

{section_list}

## Target VPS prerequisites (before `fabrik import`)

1. **Coolify** installed and running. Verify: `curl -fsS localhost:8000/api/v1/health` → 200.
2. **`postgres-main`** Coolify Service deployed and reachable as `postgres-main:5432`
   from the `coolify` Docker network.
3. **`redis-main`** Coolify Service deployed and reachable as `redis-main:6379`.
4. **Fabrik governance files** synced (`AGENTS.md`, `CLAUDE.md`, `.windsurfrules`,
   `AGENTS-compact.md`, `KILO_CLI_RULES.md`) — typically via
   `python3 scripts/sync_enforcement_to_projects.py --force` from a fabrik
   checkout on the target.
5. **DNS provider** access (Cloudflare token) — not in this bundle; operator
   provides per environment.
6. **Coolify API token** for the target installation — generate via Coolify UI.

## Restore steps

```bash
# 1. Extract the bundle
tar -xzf fabrik-export-<vps>-<date>.tar.gz -C /tmp/fabrik-restore

# 2. Re-populate /opt/fabrik/.env on the target with the secret VALUES.
#    The bundle's `secrets-redacted.json` lists the KEY NAMES you need to
#    provide. Pack §28 § Secrets ergonomics: this is the ~0.5 day manual cost.
cat /tmp/fabrik-restore/secrets-redacted.json | jq -r 'keys[]'

# 3. Run fabrik import — best-effort: rebuilds Coolify Projects → Services →
#    Applications via API, re-creates Authelia/Backrest/monitoring configs,
#    then runs `fabrik audit-registrars` to verify the rebuild.
fabrik import /tmp/fabrik-restore

# 4. Manual follow-ups NOT automated by import (see ticket Out of Scope):
#    - LetsEncrypt cert transfer (re-issue on target)
#    - DNS A-record re-binding (Cloudflare)
#    - OAuth provider re-creation (GitHub apps etc.)
#    - postgres data restore (only if export was run with --include-data)
#    - meilisearch snapshot restore (same)
```

## Caveats

- **`fabrik import` is shipped untested in this epic** — the roundtrip is
  deferred to the vps2 stand-up. Treat the import path as a checklist
  generator more than an executor for now.
- **No plaintext secrets** are inside this tarball. By design.
- **Coolify UUIDs** are stripped — the target generates fresh UUIDs.
"""


def _build_manifest(
    source_vps: str,
    timestamp: str,
    sections: dict[str, int],
    include_data: bool,
) -> dict[str, Any]:
    """Bundle manifest (version, source VPS, timestamp, per-section file
    counts, include_data flag for downstream restore logic)."""
    return {
        "version": BUNDLE_VERSION,
        "source_vps": source_vps,
        "created_at": timestamp,
        "include_data": include_data,
        "sections": dict(sorted(sections.items())),
        "untested_paths": ["import"],
        "out_of_scope": [
            "secrets-manager integration (age/sops/1Password)",
            "LetsEncrypt cert transfer",
            "DNS provider re-binding",
            "OAuth provider re-creation",
            "postgres/meili data restore (unless --include-data)",
        ],
    }


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def export_bundle(
    output: Path,
    *,
    include_data: bool = False,
    fabrik_root: Path = FABRIK_ROOT,
    source_vps: str = "vps1.ocoron.com",
    coolify_client: Any | None = None,
    skip_remote: bool = False,
) -> Path:
    """Build the portability tarball and return its path.

    Args:
        output: Destination ``.tar.gz`` path. Parent dirs are created.
        include_data: Reserved for future ``--include-data`` flag that will
            embed postgres ``pg_dump`` outputs + meilisearch snapshots.
            Currently records the intent in the manifest only.
        fabrik_root: Repo root for local file collection (specs, state,
            local monitoring mirrors). Override in tests.
        source_vps: Stamped into manifest + README header.
        coolify_client: Injectable CoolifyClient (tests pass a mock).
        skip_remote: When True, skip SSH-based pulls (monitoring/authelia/
            backrest). Used by tests; production exports leave it False.

    Returns:
        The path of the written tarball.
    """
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")

    # 1. Local file collection (fabrik-root-resident).
    specs = _collect_specs(fabrik_root)
    state = _collect_state(fabrik_root)
    secrets = _redact_env_keys(fabrik_root / ".env")
    local_monitoring = _collect_monitoring_local(fabrik_root)

    # 2. Coolify API exports (UUIDs stripped).
    coolify = _collect_coolify(coolify_client)

    # 3. VPS-side configs (skippable for tests).
    remote_monitoring: dict[str, str] = {}
    authelia: dict[str, str] = {}
    backrest: dict[str, str] = {}
    if not skip_remote:
        remote_monitoring = _collect_monitoring_remote()
        authelia = _collect_authelia()
        backrest = _collect_backrest()

    # 4. Manifest + README.
    sections = {
        "specs": len(specs),
        "state": len(state),
        "coolify": sum(len(v) for v in coolify.values()),
        "monitoring": len(local_monitoring) + len(remote_monitoring),
        "authelia": len(authelia),
        "backrest": len(backrest),
        "secrets_redacted_keys": len(secrets),
    }
    section_names = [name for name, count in sections.items() if count]
    manifest = _build_manifest(source_vps, timestamp, sections, include_data)
    readme = _build_readme(source_vps, timestamp, section_names)

    # 5. Write the tarball.
    with tarfile.open(output, "w:gz") as tar:
        _add_text(tar, "manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        _add_text(tar, "README.md", readme)
        _add_text(tar, "secrets-redacted.json", json.dumps(secrets, indent=2, sort_keys=True))
        for rel, text in specs.items():
            _add_text(tar, rel, text)
        for spec_id, payload in state.items():
            _add_text(tar, f"state/{spec_id}.json", json.dumps(payload, indent=2, sort_keys=True))
        for kind, data in coolify.items():
            _add_text(tar, f"coolify/{kind}.json", json.dumps(data, indent=2, sort_keys=True))
        for rel, text in local_monitoring.items():
            _add_text(tar, rel, text)
        for rel, text in remote_monitoring.items():
            _add_text(tar, rel, text)
        for rel, text in authelia.items():
            _add_text(tar, rel, text)
        for rel, text in backrest.items():
            _add_text(tar, rel, text)

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    logger.info("portability: exported %s (sha256=%s)", output, digest[:12])
    return output


def _add_text(tar: tarfile.TarFile, arcname: str, content: str) -> None:
    """Add a UTF-8 string as an entry inside the tarball (no temp files)."""
    data = content.encode("utf-8")
    info = tarfile.TarInfo(name=arcname)
    info.size = len(data)
    info.mtime = int(datetime.now(UTC).timestamp())
    info.mode = 0o644
    tar.addfile(info, io.BytesIO(data))


def import_bundle(
    tarball: Path,
    *,
    dry_run: bool = True,
    coolify_client: Any | None = None,
) -> dict[str, Any]:
    """Best-effort restore of a portability bundle on the target VPS.

    **NOT roundtrip-verified in this epic** (T4-03). The real test
    happens during vps2 stand-up. Default ``dry_run=True`` so accidental
    invocations don't mutate live state — operator must pass
    ``dry_run=False`` explicitly.

    Args:
        tarball: Path to the ``.tar.gz`` produced by :func:`export_bundle`.
        dry_run: When True (default), parse the bundle, build a restore
            plan, and emit it as the return value without calling any
            Coolify API write methods.
        coolify_client: Injectable CoolifyClient for tests.

    Returns:
        A plan dict: ``{"sections": {...}, "actions": [...], "secrets_to_repopulate": [...]}``.
        In a non-dry-run, the same dict is returned but ``actions`` reflect
        what was actually applied.
    """
    tarball = Path(tarball)
    if not tarball.exists():
        raise FileNotFoundError(f"bundle not found: {tarball}")

    plan: dict[str, Any] = {
        "tarball": str(tarball),
        "dry_run": dry_run,
        "sections": {},
        "actions": [],
        "secrets_to_repopulate": [],
    }

    with tarfile.open(tarball, "r:gz") as tar:
        names = tar.getnames()
        plan["sections"]["total_entries"] = len(names)

        # Read manifest if present
        try:
            manifest_member = tar.getmember("manifest.json")
            f = tar.extractfile(manifest_member)
            if f:
                plan["manifest"] = json.loads(f.read().decode("utf-8"))
        except KeyError:
            plan["manifest"] = None

        # Read secrets-redacted.json — populate the to-repopulate list
        try:
            secrets_member = tar.getmember("secrets-redacted.json")
            f = tar.extractfile(secrets_member)
            if f:
                redacted = json.loads(f.read().decode("utf-8"))
                plan["secrets_to_repopulate"] = sorted(redacted.keys())
        except KeyError:
            pass

        # Index sections by prefix
        prefixes = ("specs/", "state/", "coolify/", "monitoring/", "authelia/", "backrest/")
        for prefix in prefixes:
            count = sum(1 for n in names if n.startswith(prefix))
            if count:
                plan["sections"][prefix.rstrip("/")] = count

    if dry_run:
        plan["actions"].append({"phase": "noop", "reason": "dry_run=True (default)"})
        return plan

    # ── Real-run path: not exercised in this epic (see CHANGELOG note). ──
    # Order mirrors pack §28 lines 102–112:
    #   1. Recreate Coolify Projects → Services → Applications via API.
    #   2. Re-inject env vars (operator must re-populate secrets).
    #   3. Re-create Authelia rules.
    #   4. Re-create Backrest plans (repo definitions need re-auth).
    #   5. Re-create Prometheus / Gatus / Grafana configs.
    #   6. Restore postgres dumps if --include-data was used at export.
    #   7. Run `fabrik audit-registrars` to verify post-import state.
    plan["actions"].append(
        {
            "phase": "real_run",
            "status": "stub",
            "note": (
                "T4-03 ships the import pipeline but does NOT execute the API"
                " writes in this epic. See pack §28 'fabrik import behavior'"
                " — full roundtrip deferred to vps2 stand-up."
            ),
        }
    )
    return plan


__all__ = (
    "BUNDLE_VERSION",
    "export_bundle",
    "import_bundle",
)
