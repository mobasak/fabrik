#!/usr/bin/env python3
# AFTER-EDIT: scripts/service_catalog.json
"""Consolidate all /opt/*/.env files into a single deduped, service-annotated registry.

Gathers every project's .env under /opt/*/ (excluding fabrik's own .env and the output
file) and writes ONE consolidated file, grouped by CAPABILITY CATEGORY, with a
machine-parseable `#svc` annotation line above each external provider's vars:

  # ═══ <category> ═══
  #svc name=<provider> category=<cat> cost=<free|freemium|paid|self-host> \
       capability="<one line>" url=<url> status=<active|testing|unused|retiring>
  PROVIDER_API_KEY=...          # used by: <projects>   (value left EXACTLY as-is)
  ...
  # ═══ internal-config (NOT a service — excluded from inventory) ═══
  PORT=... JWT_SECRET_KEY=... DB_PASSWORD=... ...

The `#svc` metadata comes from the DURABLE catalog scripts/service_catalog.json and is
re-injected on EVERY regeneration, so annotations are never hand-edited into this
(auto-generated) file and never lost to a cron run. Providers absent from the catalog are
auto-flagged `category=? capability="?"` so they surface for one-pass triage instead of
silently vanishing. A downstream generator (Traycer's gen_service_inventory.py) reads only
the `#svc` lines + key NAMES — never a value — so the inventory it renders holds no secrets.

Dedup: within a provider, secrets are deduped BY VALUE (same credential under different
names collapses to one line, aliases noted; distinct values are always kept separate).

Output: /opt/fabrik/secrets/all-envs.env (chmod 600, gitignored).
Idempotent: rewrites only when the body changes (volatile header excluded from compare).

Usage:
    python scripts/gather_envs.py            # dry-run: masked summary, no write
    python scripts/gather_envs.py --apply    # write the consolidated file
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

OPT = Path("/opt")
OUTPUT = Path("/opt/fabrik/secrets/all-envs.env")
FABRIK_ENV = Path("/opt/fabrik/.env")
CATALOG_PATH = Path(__file__).with_name("service_catalog.json")
BODY_MARK = "═══"  # first body line; everything before it is the volatile header

CATEGORY_ORDER = [
    "ai-llm",
    "ai-image",
    "ai-audio",
    "ai-translate",
    "search",
    "scrape",
    "captcha",
    "proxy",
    "domains",
    "email",
    "storage",
    "backup",
    "research-data",
    "media-stock",
    "infra-platform",
    "dev-tools",
    "comms",
    "payments",
]

SECRET_KEY_RE = re.compile(
    r"(KEY|TOKEN|SECRET|PASSWORD|PASSPHRASE|CREDENTIAL|_AUTH|APIKEY|DSN|SIGNING)",
    re.IGNORECASE,
)

# Placeholder values many unrelated keys share -> never dedupe across names on these.
PLACEHOLDERS = frozenset(
    {
        "changeme",
        "change-me",
        "changme",
        "your-key-here",
        "your_api_key",
        "your-api-key",
        "your_token_here",
        "xxx",
        "xxxx",
        "xxxxx",
        "placeholder",
        "replace-me",
        "replaceme",
        "todo",
        "tbd",
        "none",
        "null",
        "n/a",
        "na",
        "test",
        "dummy",
        "example",
        "secret",
        "password",
    }
)

# Keys that are operational config, NOT an external service (excluded from the inventory).
# Kept conservative on purpose: a wrongly-internal service would be HIDDEN, whereas an
# uncatalogued service falls through to an auto-flagged `category=?` entry that stays VISIBLE.
INTERNAL_EXACT = frozenset(
    {
        "PORT",
        "API_HOST",
        "API_PORT",
        "HOST",
        "DEBUG",
        "DEBUG_MODE",
        "ENVIRONMENT",
        "ENV",
        "CORS",
        "CORS_ORIGINS",
        "ALLOWED_ORIGINS",
        "DATABASE_URL",
        "AUTH_DATABASE_URL",
        "REDIS_URL",
        "API_KEY",
        "API_KEYS",
        "API_SECRET_KEY",
        "SERVICE_NAME",
        "SERVICE_API_KEY",
        "SERVICE_INTERNAL_SECRET_KEY",
        "INTERNAL_API_TOKEN",
        "CREDENTIALS_FILE",
        "TOKEN_FILE",
        "JWT_SECRET_KEY",
        "AUTH_JWT_SECRET",
        "DB_PASSWORD",
        "PG_PASSWORD",
        "APINAME_RECOVERY_KEYS",
        "SUBAGENT_RUNS_DSN",
        "SUBAGENT_PROJECT",
    }
)
INTERNAL_SUBSTR = (
    "_DB_PASSWORD",
    "_DB_URL",
    "_DB_URI",
    "_DB_ROOT",
    "DATABASE_URI",
    "POSTGRES",
    "REDIS_",
    "LOG_LEVEL",
    "_LOG_",
    "CACHE_",
    "_CACHE",
    "RATELIMIT",
    "_RATE_",
    "RETRY",
    "TIMEOUT",
    "WORKERS",
    "CONCURRENCY",
    "SESSION_SECRET",
    "ENCRYPTION_KEY",
    "_ADMIN_PASSWORD",
    "_ROOT_PASSWORD",
    "_JWT",
    "PG_PASSWORD",
    "SSH_KEY",
)
# fabrik's OWN internal microservices are not external procurement -> internal-config.
INTERNAL_PREFIX = (
    "AUTHELIA_",
    "TRYTOND_",
    "TEST_",
    "WP_",
    "WPF_",
    "VPS_",
    "M365_CERT",
    "RATE_",
    "SITE_PROVISIONER",
    "EMAIL_GATEWAY",
    "EMAILGATEWAY",
    "DNS_MANAGER",
    "DOMSCAN",
    "EXPO_",
    "PROXY_",
    "OCORON_COM_",
)
SERVICE_SHAPE_RE = re.compile(r"_(API_KEY|API_TOKEN|API_URL|API_BASE|BASE_URL|APIKEY)S?$", re.I)


def is_secret(key: str, value: str) -> bool:
    """Secret-like if the NAME looks like a credential or the VALUE is long+high-entropy."""
    if SECRET_KEY_RE.search(key):
        return True
    return (
        len(value) >= 24
        and re.search(r"[A-Za-z]", value) is not None
        and re.search(r"[0-9]", value) is not None
        and " " not in value
    )


def credential_grade(value: str) -> bool:
    """True only for a real, unique credential worth deduping ACROSS different names."""
    v = value.strip()
    if len(v) < 8:
        return False
    if v.lower() in PLACEHOLDERS:
        return False
    if re.fullmatch(r"(.)\1*", v):  # all-same-char, e.g. "xxxxxxxx"
        return False
    return not (v.startswith("<") and v.endswith(">"))  # <your-key> is not a credential


def is_internal_config(key: str) -> bool:
    up = key.upper()
    if up in INTERNAL_EXACT:
        return True
    if any(up.startswith(p) for p in INTERNAL_PREFIX):
        return True
    return any(tok in up for tok in INTERNAL_SUBSTR)


def normalize_value(raw: str) -> str:
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        v = v[1:-1]
    return v


def parse_env(path: Path) -> list[tuple[str, str]]:
    """Return [(key, value), ...]; robust to comments / blanks / `export` prefix.

    Reads the whole file at once so a half-written file (mid-editor-save) either parses
    cleanly or is skipped - it never yields a torn line."""
    out: list[tuple[str, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("export "):
            s = s[len("export ") :].lstrip()
        if "=" not in s:
            continue
        key, _, raw = s.partition("=")
        key = key.strip()
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            continue
        out.append((key, normalize_value(raw)))
    return out


def project_env_files() -> list[Path]:
    files = []
    for env in sorted(OPT.glob("*/.env")):
        if env in (FABRIK_ENV, OUTPUT):
            continue
        if env.parent.name.startswith("_"):
            continue
        files.append(env)
    return files


def load_catalog() -> tuple[dict, list[tuple[str, str]]]:
    """Return (provider -> meta, [(prefix, provider)...] sorted longest-first).

    Fail-soft: a malformed hand-edited catalog degrades to "everything flagged
    category=?" (still visible) rather than crashing the cron and freezing the file."""
    try:
        raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"WARNING: {CATALOG_PATH} unreadable ({exc}); all providers flagged", file=sys.stderr)
        raw = {}
    catalog = {k: v for k, v in raw.items() if not k.startswith("_")}
    matchers: list[tuple[str, str]] = []
    for provider, meta in catalog.items():
        for prefix in meta.get("match", []):
            matchers.append((prefix.upper(), provider))
    matchers.sort(key=lambda pm: len(pm[0]), reverse=True)  # longest prefix wins
    return catalog, matchers


def match_provider(key: str, matchers: list[tuple[str, str]]) -> str | None:
    up = key.upper()
    for prefix, provider in matchers:
        if up.startswith(prefix):
            return provider
    return None


def derive_provider(key: str) -> str:
    stem = SERVICE_SHAPE_RE.sub("", key)
    stem = re.sub(
        r"_(SECRET_KEY|ACCESS_KEY|SECRET|TOKEN|KEY|URL|PASSWORD|USER|PASS|DSN)S?$",
        "",
        stem,
        flags=re.I,
    )
    return (stem or key).lower()


def svc_line(name: str, meta: dict, used_by: set[str]) -> str:
    cap = str(meta.get("capability", "?")).replace('"', "'")  # keep the #svc line parseable
    ub = ",".join(sorted(used_by)) if used_by else "-"
    return (
        f"#svc name={name} category={meta.get('category', '?')} "
        f'cost={meta.get("cost", "?")} capability="{cap}" '
        f"url={meta.get('url', '?')} status={meta.get('status', '?')} used_by={ub}"
    )


def cat_header(label: str) -> str:
    pad = "═" * 20
    return f"# {pad} {label} {pad}"


def consolidate(files: list[Path]) -> tuple[str, dict]:
    """Build the category-grouped, #svc-annotated body + summary stats."""
    catalog, matchers = load_catalog()

    # provider -> {"meta":..., "values": value -> {"names":set, "projects":set}}
    services: dict[str, dict] = {}
    internal: dict[tuple[str, str], set] = defaultdict(set)
    project_count = 0
    total_lines = 0
    skipped_empty = 0

    def svc_bucket(provider: str, meta: dict) -> dict:
        if provider not in services:
            services[provider] = {
                "meta": meta,
                "values": defaultdict(lambda: {"names": set(), "projects": set()}),
            }
        return services[provider]["values"]

    for env in files:
        project = env.parent.name
        kvs = parse_env(env)
        if not kvs:
            continue
        project_count += 1
        for key, value in kvs:
            total_lines += 1
            if value == "":
                skipped_empty += 1
                continue
            provider = match_provider(key, matchers)
            if provider:
                meta = catalog[provider]
                dedupe = is_secret(key, value) and credential_grade(value)
                slot = value if dedupe else f"{key}\x00{value}"  # non-secrets keyed by key+value
                rec = svc_bucket(provider, meta)[slot]
                rec["names"].add(key)
                rec["projects"].add(project)
            elif is_internal_config(key):
                internal[(key, value)].add(project)
            elif SECRET_KEY_RE.search(key) or SERVICE_SHAPE_RE.search(key):
                # NAME-based only: the value-entropy path in is_secret() misfires on long
                # config values (model names, UUIDs, DSNs), pulling config into services.
                name = derive_provider(key)
                dedupe = is_secret(key, value) and credential_grade(value)
                slot = value if dedupe else f"{key}\x00{value}"
                rec = svc_bucket(
                    name,
                    {"category": "?", "cost": "?", "capability": "?", "url": "?", "status": "?"},
                )[slot]
                rec["names"].add(key)
                rec["projects"].add(project)
            else:
                internal[(key, value)].add(project)

    # ---- render ----
    lines: list[str] = []

    def render_provider(name: str) -> None:
        data = services[name]
        projects: set[str] = set()
        for rec in data["values"].values():
            projects |= rec["projects"]
        lines.append(svc_line(name, data["meta"], projects))
        items = sorted(data["values"].items(), key=lambda kv: (sorted(kv[1]["names"])[0], kv[0]))
        for _slot, rec in items:
            primary = sorted(rec["names"])[0]
            value = _slot.split("\x00", 1)[-1]
            aliases = sorted(n for n in rec["names"] if n != primary)
            note = []
            if aliases:
                note.append("aliases: " + ", ".join(aliases))
            note.append("used by: " + ", ".join(sorted(rec["projects"])))
            lines.append(f"{primary}={value}   # " + " · ".join(note))

    by_cat: dict[str, list[str]] = defaultdict(list)
    for name, data in services.items():
        by_cat[data["meta"].get("category", "?")].append(name)

    ordered = [c for c in CATEGORY_ORDER if c in by_cat]
    ordered += sorted(c for c in by_cat if c not in CATEGORY_ORDER and c != "?")
    for cat in ordered:
        lines.append(cat_header(cat))
        for name in sorted(by_cat[cat]):
            render_provider(name)
        lines.append("")

    if "?" in by_cat:  # uncatalogued providers -> triage
        lines.append(cat_header("NEEDS-TRIAGE (category=? — fabrik AI: fill catalog)"))
        for name in sorted(by_cat["?"]):
            render_provider(name)
        lines.append("")

    lines.append(cat_header("internal-config (NOT a service — excluded from inventory)"))
    for (key, value), projs in sorted(internal.items()):
        suffix = f"   # used by: {len(projs)} projects" if len(projs) > 1 else ""
        lines.append(f"{key}={value}{suffix}")
    lines.append("")

    catalogued = sum(1 for d in services.values() if d["meta"].get("category", "?") != "?")
    stats = {
        "projects": project_count,
        "total_lines": total_lines,
        "skipped_empty": skipped_empty,
        "services": len(services),
        "catalogued": catalogued,
        "flagged": len(services) - catalogued,
        "internal_lines": len(internal),
    }
    return "\n".join(lines), stats


def read_existing_body(path: Path) -> str:
    """Return the stored body (from the first category-header LINE onward), stripping the
    volatile header. Splits on the line boundary - NOT mid-line at the first `═`, which
    would drop the leading `# ` and make the body never compare equal (breaking idempotency)."""
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for i, line in enumerate(lines):
        if BODY_MARK in line:
            return "\n".join(lines[i:])
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the file (default: dry-run)")
    args = ap.parse_args()

    files = project_env_files()
    if not files:
        print("No project .env files found under /opt/*/.env", file=sys.stderr)
        return 1

    body, stats = consolidate(files)
    header = (
        "# AUTO-GENERATED by scripts/gather_envs.py - DO NOT EDIT BY HAND\n"
        "# Service metadata is sourced from scripts/service_catalog.json (edit THERE).\n"
        f"# Generated: {datetime.now(UTC).isoformat(timespec='seconds')}\n"
        f"# {stats['projects']} projects | {stats['services']} services "
        f"({stats['catalogued']} catalogued, {stats['flagged']} need triage) | "
        f"{stats['internal_lines']} internal-config vars\n#\n"
    )
    content = header + body + "\n"

    summary = (
        f"{stats['projects']} projects | {stats['total_lines']} env lines "
        f"({stats['skipped_empty']} empty skipped) -> {stats['services']} services "
        f"({stats['catalogued']} catalogued, {stats['flagged']} NEED TRIAGE), "
        f"{stats['internal_lines']} internal-config"
    )

    if not args.apply:
        print("[dry-run]", summary)
        print("Re-run with --apply to write", OUTPUT)
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if read_existing_body(OUTPUT).rstrip() == body.rstrip():
        print("no change - already up to date:", OUTPUT)
        return 0

    tmp = OUTPUT.with_name(OUTPUT.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, OUTPUT)
    print("wrote", OUTPUT, "|", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
