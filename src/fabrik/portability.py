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
    ├── state/*.json                    # .fabrik/state/<id>.json (legacy coolify_uuid stripped)
    ├── secrets-redacted.json           # .env key NAMES only (never values)
    ├── monitoring/
    │   ├── gatus/                      # SSH-pulled /opt/monitoring/configs/gatus/
    │   ├── prometheus.yml              # /opt/monitoring/configs/prometheus/prometheus.yml
    │   ├── alertmanager.yml            # /opt/monitoring/configs/alertmanager/alertmanager.yml
    │   ├── grafana-dashboards/         # local mirror configs/grafana/dashboards/
    │   ├── redis-assignments.json      # /opt/monitoring/configs/redis/assignments.json
    │   └── postgres-allocations.json   # /opt/monitoring/configs/postgres/allocations.json (T4-01)
    ├── authelia/
    │   └── configuration.yml           # SSH pull of the host-mounted Authelia config
    └── backrest/
        └── config.json                 # SSH pull from backrest config

Security invariants enforced by tests:
    1. Bundle contains NO plaintext secret values (only key names).
    2. Bundle contains NO legacy ``coolify_uuid`` values (stripped from state files).
    3. Bundle contains NO private keys.

A legacy bundle's ``coolify/*`` members are never restored; ``import_bundle``
counts them under ``plan["ignored_legacy"]``.

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

# Pattern of a legacy platform UUID — 24 alphanumeric chars. Used by the
# recursive UUID-stripper over ``.fabrik/state/*.json`` (its only consumer,
# ``_collect_state``). Matches more permissively than strictly necessary to
# catch timestamp-suffixed names too.
_COOLIFY_UUID_RE = re.compile(r"^[a-z0-9]{24}$")

# Sensitive-key patterns for the generic config redactor. Any field whose
# name (or path) matches one of these patterns has its value replaced with
# the literal string ``"REDACTED"`` before the file enters the bundle.
# Conservative bias: false-positive redactions are operator-recoverable
# (re-populate on target); false-negative leaks are not. The one value-level
# exception is :data:`_PEM_PRIVATE_RE` (invariant 3: a private key under any name).
_SENSITIVE_KEY_PATTERNS = (
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"priv", re.IGNORECASE),  # private_key, privkey, Backrest ed25519priv
    re.compile(r"^key$", re.IGNORECASE),  # Authelia identity_providers.oidc.jwks[].key
    re.compile(r"^multihost$", re.IGNORECASE),  # Backrest multihost.identity (raw key)
    re.compile(r"encryption[_-]?key", re.IGNORECASE),
    re.compile(r"jwt[_-]?secret", re.IGNORECASE),
    re.compile(r"session[_-]?secret", re.IGNORECASE),
    re.compile(r"^auth$", re.IGNORECASE),  # Backrest .auth = {users:[...]}
    re.compile(r"users$", re.IGNORECASE),  # Backrest .auth.users
    re.compile(r"^env$", re.IGNORECASE),  # Backrest .repos[].env (AWS creds)
    re.compile(r"credentials", re.IGNORECASE),
    re.compile(r"webhook", re.IGNORECASE),
)

# A PEM/OpenSSH/PGP/SSH2 private-key armour line (BEGIN or END), anywhere in a
# value: label words between BEGIN and PRIVATE, any whitespace (a re-wrapped
# value splits it), any case. CERTIFICATE and PUBLIC KEY armour never matches.
_PEM_PRIVATE_RE = re.compile(
    r"(?:BEGIN|END)[ \t\r\n]*(?:[A-Z0-9]+[ \t\r\n]+)*PRIVATE[ \t\r\n]+KEY", re.IGNORECASE
)


def _key_is_sensitive(key: str) -> bool:
    """Match a key name against the conservative sensitive-pattern list."""
    return any(p.search(key) for p in _SENSITIVE_KEY_PATTERNS)


def _is_private_key_text(value: Any) -> bool:
    if isinstance(value, bytes):
        value = value.decode("latin-1")
    return isinstance(value, str) and bool(_PEM_PRIVATE_RE.search(value))


def _redact_sensitive_fields(obj: Any) -> Any:
    """Recursively walk a JSON/YAML structure, replacing every value whose
    KEY name matches one of :data:`_SENSITIVE_KEY_PATTERNS` with the
    literal string ``"REDACTED"``.

    Redaction happens at the KEY level — we don't heuristically detect
    "this string looks like a secret" on values, which avoids false
    positives on URLs, paths, etc. — with ONE value-level exception: a
    str/bytes value carrying a private-key armour line
    (:data:`_PEM_PRIVATE_RE`) is redacted whatever it is called, because
    invariant 3 promises no private keys and a PEM armour line is never a
    URL or path. A mapping key that is not a string (YAML ints, bools,
    nulls, ``!!binary``) cannot spell a sensitive name, so its value is
    redacted (fail closed) and the key kept with its type.
    """
    if isinstance(obj, dict):
        out: dict[Any, Any] = {}
        for k, v in obj.items():
            if not isinstance(k, str):
                logger.warning(
                    "portability: redacting the value under a non-string %s mapping key",
                    type(k).__name__,
                )
                out[k] = "REDACTED"
            elif _key_is_sensitive(k):
                out[k] = "REDACTED"
            else:
                out[k] = _redact_sensitive_fields(v)
        return out
    if isinstance(obj, list):
        return [_redact_sensitive_fields(item) for item in obj]
    if _is_private_key_text(obj):
        return "REDACTED"
    return obj


# Keys ``_strip_uuids`` always strips from state-file payloads (legacy UUIDs + sensitive refs).
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

    Used by ``_collect_state`` over ``.fabrik/state/*.json``, where legacy
    UUIDs can sit in nested objects; explicit recursion catches every
    variant.
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
    (the compose app name, re-derived from the spec on import). Other fields kept verbatim.

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
    """Authelia configuration.yml.

    Authelia's configuration is bind-mounted from the host path
    ``/opt/authelia/config`` (read-only vps1 reading R1, 2026-10-14), not a
    named Docker volume, so that path is probed first. The two legacy
    named-volume/service-directory paths and the volume-find discovery stay
    after it as legacy fallbacks.

    **Plaintext-secret redaction (T4-03 convergence pass).** The on-disk
    configuration.yml carries inline ``jwt_secret``, ``session.secret``,
    and ``storage.encryption_key`` values. We parse the YAML, redact every
    key whose name matches :data:`_SENSITIVE_KEY_PATTERNS`, then re-emit.
    The structural fields (access_control rules, providers, redirects) are
    preserved so the bundle stays restore-useful.
    """
    candidates = [
        # Live path: host bind mount (R1).
        "/opt/authelia/config/configuration.yml",
        # Legacy fallbacks follow. Named-volume path:
        "/var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml",
        # Legacy service-directory path, last-ditch fallback:
        "/data/coolify/services/hks48k8sg8o4co4co08co00o/authelia/configuration.yml",
    ]
    raw: str | None = None
    for path in candidates:
        raw = _ssh_cat(path)
        if raw:
            break
    if not raw:
        # Volume-name discovery fallback.
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
    ``/config`` mount). The mount is a host bind, so this path is stable
    across redeploys.

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

    Documents the prerequisites the target VPS must satisfy (SSH access,
    Docker Compose, postgres-main + redis-main bootstrapped, the Fabrik
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

1. **SSH access** to the target VPS and **Docker Compose** installed. Verify:
   `ssh <vps> docker compose version`.
2. **`postgres-main`** Compose project deployed and reachable as `postgres-main:5432`
   from the `fabrik` Docker network.
3. **`redis-main`** Compose project deployed and reachable as `redis-main:6379`.
4. **Fabrik governance files** synced (`AGENTS.md`, `CLAUDE.md`) — typically via
   `python3 scripts/sync_enforcement_to_projects.py --force` from a fabrik
   checkout on the target.
5. **DNS provider** access (Cloudflare token) — not in this bundle; operator
   provides per environment.
6. **Compose files** for the services under `/opt/<id>/compose.yaml` — restored by
   `fabrik apply specs/services/<id>.yaml` from the bundle's `specs/`.

## Restore steps

```bash
# 1. Extract the bundle
tar -xzf fabrik-export-<vps>-<date>.tar.gz -C /tmp/fabrik-restore

# 2. Re-populate /opt/fabrik/.env on the target with the secret VALUES.
#    The bundle's `secrets-redacted.json` lists the KEY NAMES you need to
#    provide. Pack §28 § Secrets ergonomics: this is the ~0.5 day manual cost.
cat /tmp/fabrik-restore/secrets-redacted.json | jq -r 'keys[]'

# 3. Run fabrik import — best-effort: plans the Authelia/Backrest/monitoring
#    config restore and reports it; it does not apply anything. Then, by hand,
#    run `fabrik apply specs/services/<id>.yaml` for each spec (SSH + Compose)
#    and `fabrik audit-registrars` to verify the rebuild.
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
- **Legacy platform UUIDs** are stripped from state files; the target
  starts from fresh state.
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

    # 2. VPS-side configs (skippable for tests).
    remote_monitoring: dict[str, str] = {}
    authelia: dict[str, str] = {}
    backrest: dict[str, str] = {}
    if not skip_remote:
        remote_monitoring = _collect_monitoring_remote()
        authelia = _collect_authelia()
        backrest = _collect_backrest()

    # 3. Manifest + README.
    sections = {
        "specs": len(specs),
        "state": len(state),
        "monitoring": len(local_monitoring) + len(remote_monitoring),
        "authelia": len(authelia),
        "backrest": len(backrest),
        "secrets_redacted_keys": len(secrets),
    }
    section_names = [name for name, count in sections.items() if count]
    manifest = _build_manifest(source_vps, timestamp, sections, include_data)
    readme = _build_readme(source_vps, timestamp, section_names)

    # 4. Write the tarball.
    with tarfile.open(output, "w:gz") as tar:
        _add_text(tar, "manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        _add_text(tar, "README.md", readme)
        _add_text(tar, "secrets-redacted.json", json.dumps(secrets, indent=2, sort_keys=True))
        for rel, text in specs.items():
            _add_text(tar, rel, text)
        for spec_id, payload in state.items():
            _add_text(tar, f"state/{spec_id}.json", json.dumps(payload, indent=2, sort_keys=True))
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
) -> dict[str, Any]:
    """Best-effort restore of a portability bundle on the target VPS.

    **NOT roundtrip-verified in this epic** (T4-03). The real test
    happens during vps2 stand-up. Default ``dry_run=True`` so accidental
    invocations don't mutate live state — operator must pass
    ``dry_run=False`` explicitly.

    Args:
        tarball: Path to the ``.tar.gz`` produced by :func:`export_bundle`.
        dry_run: When True (default), parse the bundle, build a restore
            plan, and emit it as the return value without mutating anything.

    Returns:
        A plan dict: ``{"sections": {...}, "actions": [...], "secrets_to_repopulate": [...]}``,
        plus ``"ignored_legacy": <n>`` when a legacy bundle carries ``coolify/*`` members
        (counted, never restored).
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
        members = tar.getmembers()
        # One normalised name per member, so a `tar -C dir .` bundle (./-prefixed) reads the same.
        by_name = {m.name.removeprefix("./"): m for m in members}
        names = [m.name.removeprefix("./") for m in members]
        plan["sections"]["total_entries"] = len(names)

        # Read manifest if present
        plan["manifest"] = None
        manifest_member = by_name.get("manifest.json")
        if manifest_member is not None:
            f = tar.extractfile(manifest_member)
            if f:
                plan["manifest"] = json.loads(f.read().decode("utf-8"))

        # Read secrets-redacted.json — populate the to-repopulate list
        secrets_member = by_name.get("secrets-redacted.json")
        if secrets_member is not None:
            f = tar.extractfile(secrets_member)
            if f:
                redacted = json.loads(f.read().decode("utf-8"))
                plan["secrets_to_repopulate"] = sorted(redacted.keys())

        # Index sections by prefix
        prefixes = ("specs/", "state/", "monitoring/", "authelia/", "backrest/")
        for prefix in prefixes:
            count = sum(1 for n in names if n.startswith(prefix))
            if count:
                plan["sections"][prefix.rstrip("/")] = count
        legacy = sum(
            1
            for m, n in zip(members, names, strict=True)
            if not m.isdir() and n.startswith("coolify/")
        )
        if legacy:
            plan["ignored_legacy"] = legacy

    if dry_run:
        plan["actions"].append({"phase": "noop", "reason": "dry_run=True (default)"})
        return plan

    # ── Real-run path: not exercised in this epic (see CHANGELOG note). ──
    # Order mirrors pack §28 lines 102–112:
    #   1. Re-inject env vars (operator must re-populate secrets).
    #   2. Re-create Authelia rules.
    #   3. Re-create Backrest plans (repo definitions need re-auth).
    #   4. Re-create Prometheus / Gatus / Grafana configs.
    #   5. Restore postgres dumps if --include-data was used at export.
    #   6. Run `fabrik audit-registrars` to verify post-import state.
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
