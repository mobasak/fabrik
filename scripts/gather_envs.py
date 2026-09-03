#!/usr/bin/env python3
# AFTER-EDIT: scripts/service_catalog.json scripts/tests/test_gather_envs.py scripts/registry_sync.py
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

SECOND INPUT — code call sites (2026-09-02): env keys are a PROXY for "the fleet uses vendor X",
and the proxy leaks — a vendor reached with no key (a public API, a scrape target, an SDK whose
token is named unusually) never appears in any .env. So every git repo under /opt/ is also
scanned (ripgrep, source files only) for `https://<host>` literals; each host is attributed to
the catalog provider whose `url` shares its registrable domain (or whose `match` prefix equals
it), adding the referencing repos to `used_by`; a host that matches no provider lands in the
same NEEDS-TRIAGE block as an unknown key, as `CODE_HOST_URL=https://<host>`, so the classifier
grounds it exactly like an unknown key. Own domains, placeholders (example/test/evil), and
reference-only hosts (docs, package registries, schemas, CDNs — unless `api.`-prefixed) are
ignored; measured 2026-09-02 before this input: 239 of 495 code-referenced hosts were in neither
the registry nor the fleet index.

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
import stat
import subprocess
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

OPT = Path("/opt")
REPO = (
    Path(__file__).resolve().parent.parent
)  # a sandboxed copy must never write the REAL secrets file (BS17)
OUTPUT = REPO / "secrets" / "all-envs.env"
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


# ── code call-site scan: the second input (hosts reached WITHOUT an env key) ─────────────────
# optional userinfo (`user:pw@`) is skipped — `https://allowed.com@evil.com` names evil.com, not
# allowed.com (review 2026-09-02, pass 2: a comment cost a paid classify unit and a bogus tombstone)
HOST_RE = re.compile(r"https?://(?:[^/\s@]+@)?([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")
CODE_TYPES = (
    "py",
    "ts",
    "js",
    "sh",
    "yaml",
    "docker",
)  # rg types (ts ⊃ tsx, js ⊃ mjs/cjs, docker = Dockerfile*)
CODE_EXCLUDE_GLOBS = (
    "!node_modules",
    "!.venv",
    "!venv",
    "!.git",
    "!dist",
    "!.next",
    "!__pycache__",
    "!.mypy_cache",
    "!.ruff_cache",
    "!htmlcov",
    "!coverage",
    "!.tmp",
    "!secrets",
    "!backups",
    "!archived",
    "!docs",
    "!tests",
    "!test",
    "!__tests__",
    "!__mocks__",
    "!mocks",
    "!fixtures",
    "!e2e",
    "!cypress",
    "!test_*",
    "!*_test.*",
    "!*.test.*",
    "!*.spec.*",
    "!*.min.*",
    "!*.lock",
    "!*.d.ts",
    # a repo's OWN `build/` or `cache/` SOURCE dir must survive — these two are root-only.
    # rg anchors a leading `/` to the CWD, not to each search root (measured 2026-09-02: from
    # /opt/fabrik with roots /opt/<repo>, `!/build` excluded nothing) — so the scan runs with
    # cwd=/opt and RELATIVE repo names, and `/*/build` means `<repo>/build` exactly.
    "!/*/build",
    "!/*/cache",
)
# Hosts that are never an external SYSTEM: the fleet's own domains + local/test TLDs.
OWN_HOST_SUFFIXES = (  # every entry dotted: a bare "localhost" matched `attacker.fakelocalhost` by suffix (ES4); the exact host `localhost` is the dotted entry's `lstrip(".")` case
    ".ocoron.com",
    ".ozgurbasak.com",
    ".local",
    ".localhost",
    ".test",
    ".example",
    ".invalid",
    ".internal",
    ".lan",
    ".home.arpa",
)
# Registrable-domain labels that are placeholders in code/fixtures, not vendors.
PLACEHOLDER_SLD = frozenset(
    {
        "example",
        "a",
        "b",
        "c",
        "x",
        "company",
        "yourdomain",
        "your-domain",
        "yourcompany",
        "testsite",
        "mysite",
        "myapp",
        "yourapp",
        "acme",
        "foo",
        "bar",
        "baz",
        "test",
        "placeholder",
        "domain",
        "site",
        "evil",
        "attacker",
        "malicious",
        "changeme",
        "todo",
    }
)
# Reference-only domains: cited in comments/links, never CALLED — package registries, schema
# hosts, standards bodies, CDNs, Q&A sites, front-end libraries. NEVER a vendor's own domain:
# `graph.microsoft.com` and `registry-1.docker.io` are call sites (review 2026-09-02 — `microsoft`,
# `docker`, `sentry`, `grafana` sat here and silently dropped real fleet dependencies). A vendor's
# DOCUMENTATION subdomain is ignored by prefix instead (DOC_HOST_PREFIXES); `api.*` always survives.
REFERENCE_ONLY_SLD = frozenset(
    {
        "w3",
        "schema",
        "json-schema",
        "schemastore",
        "iana",
        "ietf",
        "rfc-editor",
        "python",
        "nodejs",
        "npmjs",
        "pypi",
        "readthedocs",
        "mozilla",
        "stackoverflow",
        "wikipedia",
        "wikimedia",
        "github",
        "githubusercontent",
        "gitlab",
        "jsdelivr",
        "unpkg",
        "cdnjs",
        "gstatic",
        "apache",
        "gnu",
        "opensource",
        "creativecommons",
        "xmlsoap",
        "purl",
        "ogp",
        "shields",
        "badgen",
        "openapis",
        "swagger",
        "sitemaps",
        "unicode",
        "whatwg",
        "oasis-open",
        "typescriptlang",
        "reactjs",
        "nextjs",
        "vitejs",
        "tailwindcss",
        "fontawesome",
        "googlefonts",
        "react",
        "prisma",
        "eslint",
        "pytorch",
        "lucide",
        "radix-ui",
        "remixicon",
        "phosphoricons",
        "openfontlicense",
        "openxmlformats",
        "designtokens",
        "nodesource",
        "httpstatuses",
        "ycombinator",
        "mankier",
        "labnol",
        "kubernetes",
        "postgresql",
        "nginx",
        "sqlite",
    }
)
DOC_HOST_PREFIXES = (
    "docs.",
    "doc.",
    "learn.",
    "developer.",
    "developers.",
    "help.",
    "support.",
    "blog.",
    "wiki.",
    "community.",
    "forum.",
    "changelog.",
)
_CC_SECOND_LEVEL = frozenset({"co", "com", "org", "net", "gov", "edu", "ac", "or", "ne", "go"})
# Multi-service platform domains: the registrable label names a CLOUD, not a vendor product —
# `email.us-east-1.amazonaws.com` is SES, `truststore.pki.rds.amazonaws.com` is RDS; `gmail.
# googleapis.com` is Gmail, `generativelanguage.googleapis.com` is Gemini. Attributing them
# by registrable label mis-credited an RDS truststore fetch to `aws-ses` (measured 2026-09-02).
PLATFORM_SLD = frozenset({"amazonaws", "googleapis", "azure", "windows", "cloudfront"})


def host_domain(host: str) -> str:
    """Registrable DOMAIN of a host (label + public suffix): api.foo.com → foo.com, x.foo.co.uk →
    foo.co.uk — the wildcard key of the catalog url index, so `api.foo.org` is never credited to
    the vendor at `foo.com` (C5)."""
    parts = host.lower().rstrip(".").split(".")
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in _CC_SECOND_LEVEL:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else parts[0]


def host_sld(host: str) -> str:
    """Registrable label of a host: api.posthog.com → posthog; foo.co.uk → foo."""
    parts = host.lower().rstrip(".").split(".")
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in _CC_SECOND_LEVEL:
        return parts[-3]
    return parts[-2] if len(parts) >= 2 else parts[0]


def ignored_host(host: str) -> bool:
    h = host.lower().rstrip(".")
    tld = h.rsplit(".", 1)[-1]
    if not tld.isalpha() or len(tld) < 2:  # IPs, ports-in-host, junk
        return True
    if any(h == suf.lstrip(".") or h.endswith(suf) for suf in OWN_HOST_SUFFIXES):
        return True
    sld = host_sld(h)
    if (
        len(sld) < 2 or len(sld) > 40
    ):  # one-letter labels are fixtures; `qq.com`/`hp.com` are vendors
        return True
    if sld in PLACEHOLDER_SLD:
        return True
    if h.startswith("api."):
        return False
    if h.startswith(DOC_HOST_PREFIXES):
        return True
    return sld in REFERENCE_ONLY_SLD


def project_dirs() -> list[Path]:
    """Every git repo under /opt (not only the ones with a .env — keyless repos are the point)."""
    out = []
    for d in sorted(OPT.iterdir()):
        if not d.is_dir() or d.name.startswith("_") or d.name == "archived":
            continue
        if (d / ".git").exists():
            out.append(d)
    return out


class CatalogError(ValueError):
    """The catalog is readable but a provider entry cannot round-trip (a whitespace key) — the one
    ValueError `main` reports as a one-liner; any other ValueError is a bug and keeps its traceback (BB6)."""


class CodeScanError(RuntimeError):
    """ripgrep could not run — the caller must NOT write a consolidation missing every code host
    (yesterday's complete file beats today's truncated one; a silent drop would feed a ~200-provider
    delete into registry_sync's prune guard and only THEN surface, as a refusal)."""


def scan_code_hosts(dirs: list[Path]) -> dict[str, dict[str, set[str]]]:
    """host -> {"projects": {repo names}, "files": {paths}} for every external host literal in
    source under `dirs`. One ripgrep over all repos. Raises CodeScanError when rg cannot run
    (missing binary, timeout, exit 2) — fail-CLOSED, never a silent empty result."""
    if not dirs:
        return {}
    cmd = [
        "rg",
        "-oNH",
        "--no-heading",
        "--color",
        "never",
        "--max-filesize",
        "1M",
    ]
    for t in CODE_TYPES:
        cmd += ["-t", t]
    for g in CODE_EXCLUDE_GLOBS:
        cmd += ["-g", g]
    cmd += [HOST_RE.pattern, *[d.name for d in dirs]]  # relative to OPT — see the glob note above
    try:
        cp = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600, check=False, cwd=str(OPT)
        )
    except (
        OSError,
        subprocess.TimeoutExpired,
        UnicodeDecodeError,
    ) as exc:  # undecodable output IS a scan that could not run (CM4)
        raise CodeScanError(f"code-host scan could not run: {exc}") from exc
    if cp.returncode not in (0, 1):  # rg: 0 = matches, 1 = no matches, 2 = an error occurred
        err = cp.stderr.strip()[:600]
        if not cp.stdout.strip():
            raise CodeScanError(f"ripgrep exited {cp.returncode} with no matches: {err}")
        # Matches came back alongside an error (one unreadable dir): a PARTIAL scan beats
        # aborting all 45 repos — say so, loudly, with rg's own text naming the path.
        print(f"WARNING: code-host scan partial (rg exit {cp.returncode}): {err}", file=sys.stderr)
    hosts: dict[str, dict[str, set[str]]] = {}
    for line in cp.stdout.splitlines():
        cut = line.find(":http")
        if cut < 0:
            continue
        path, match = line[:cut], line[cut + 1 :]
        m = HOST_RE.search(match)
        if not m:
            continue
        host = m.group(1).lower().rstrip(".")
        if ignored_host(host):
            continue
        parts = Path(path).parts  # `<repo>/…` because rg ran with cwd=OPT and relative roots
        if not parts:
            continue
        project = parts[0]
        rec = hosts.setdefault(host, {"projects": set(), "files": set()})
        rec["projects"].add(project)
        rec["files"].add(str(OPT / path))
    return hosts


def catalog_url_index(catalog: dict) -> dict[str, str]:
    """Two-level index from each catalog entry's url: exact hostname -> provider, plus
    `*.<registrable-domain>` -> provider ONLY where exactly one vendor owns that domain. A label
    shared by several entries (`backrest`'s url is a github.com repo link; safe-browsing, youtube
    and gemini all sit under google.com) is AMBIGUOUS and is dropped rather than resolved by
    JSON key order (review 2026-09-02)."""
    hosts: dict[str, set[str]] = {}
    owners: dict[str, set[str]] = {}
    for provider, meta in catalog.items():
        extras = meta.get("hosts") or []
        for extra in (
            extras if isinstance(extras, list) else [extras]
        ):  # merged hosts (AB3); scalar-safe (AF14)
            hosts.setdefault(str(extra).lower(), set()).add(provider)
        url = str(meta.get("url") or "")
        try:
            host = urlsplit(url).hostname if url.startswith("http") else None
        except ValueError:  # a model-authored url with `]` in the netloc is not a url (BB6)
            host = None
        if not host:
            continue
        hosts.setdefault(host.lower(), set()).add(provider)
        owners.setdefault(host_domain(host), set()).add(
            provider
        )  # keyed by registrable DOMAIN, TLD included (C5)
    idx: dict[str, str] = {}
    for host, provs in hosts.items():
        if len(provs) == 1:  # a hostname two entries share (a repo link) names neither
            idx[host] = next(iter(provs))
    for sld, provs in owners.items():
        if len(provs) == 1:
            idx.setdefault(f"*.{sld}", next(iter(provs)))
    return idx


def host_label(host: str) -> str:
    """The name a host contributes to the triage queue: its registrable label, or for a
    multi-service platform domain the SERVICE label too (`gmail.googleapis`, `email.amazonaws`)."""
    sld = host_sld(host)
    if sld in PLATFORM_SLD:
        first = host.lower().split(".")[0]
        return f"{first}.{sld}" if first != sld else sld
    return sld


def provider_for_host(host: str, catalog: dict, url_index: dict[str, str], matchers) -> str | None:
    h = host.lower()
    sld = host_sld(h)
    if sld in PLATFORM_SLD:  # never credit a whole cloud to one catalog vendor …
        if h in url_index:  # … unless an entry claims this exact host (a merged `hosts` entry, AB3)
            return url_index[h]
        label = host_label(h)
        if label in catalog:  # … but a platform SERVICE the classifier already named/tombstoned
            return label  # keeps its entry, or it is re-billed on every cycle (review 2026-09-02)
        first = h.split(".")[0]
        return match_provider(f"{first.upper().replace('-', '_')}_API_KEY", matchers)
    if h in url_index:  # exact hostname
        return url_index[h]
    dom = host_domain(h)
    if f"*.{dom}" in url_index:  # unambiguous registrable domain, TLD included (C5)
        return url_index[f"*.{dom}"]
    if sld in catalog:
        # the label alone is evidence only when the entry has no url of its own, or its url sits on
        # the SAME registrable domain — `api.foo.org` is not the vendor at `foo.com` (C5)
        url = str(catalog[sld].get("url") or "")
        try:
            own = urlsplit(url).hostname if url.startswith("http") else None
        except ValueError:  # an unparseable catalog url is not evidence, never a crash (BB6/BR1)
            own = None
        if not own or host_domain(own) == host_domain(h):
            return sld
        # the entry's url sits on ANOTHER registrable domain: not this vendor — and never re-credited
        # by falling through to its own `<SLD>_API_KEY` prefix (most vendors curate it: 82 of 109;
        # the C5 grader passed `matchers=[]`, the one shape production never has — BS3). Said
        # aloud: 14 live hosts of 8 vendors sit on a sibling domain (`fal.run`, `replicate.delivery`)
        # and belong in the entry's `hosts` — silent None triaged them as their own blocks (BW1)
        print(
            f"WARNING: host {h} carries catalogued label {sld} but {sld}'s url is on {host_domain(own)} — add it to {sld}'s `hosts` or it is triaged as its own block",
            file=sys.stderr,
        )
        return None
    return match_provider(f"{sld.upper().replace('-', '_')}_API_KEY", matchers)


def code_only_block_name(host: str, catalog: dict) -> str:
    """The block a NON-attributed code host is filed under: its label — unless the label IS a
    catalogued vendor the domain check just refused, where the vendor's own name would send the
    block to paid triage and let the classifier's answer OVERWRITE the curated entry; then the
    registrable domain (`fal.run` → `fal-run`), which the classifier's merge path folds into the
    vendor's `hosts` (BW1)."""
    label = host_label(host)
    if label in catalog:
        return _svc_token(host_domain(host.lower()).replace(".", "-"))
    return label


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


# a POSIX path: ≥2 slash-separated segments, EACH a file/dir name — lowercase after its first
# character (`/opt/fabrik/certs/m365-cert-2026.pem`, `~/.ssh/id_ed25519`, `/Users/x`). A base64
# secret can start with `/` and carry a second `/` (≈0.4 % of 40-char values), but its segments are
# mixed-case throughout; measured 2026-09-02: 34 of 34 live path values fit, 0 secrets do (AL1)
PATH_VALUE_RE = re.compile(r"(~|\.{1,2})?(/[A-Za-z.][a-z0-9._-]*){2,}/?")  # ≥2 segments (AO1)


def credential_grade(value: str) -> bool:
    """True only for a real, unique credential worth deduping ACROSS different names."""
    v = value.strip()
    if len(v) < 8:
        return False
    if v.lower() in PLACEHOLDERS:
        return False
    if re.fullmatch(r"(.)\1*", v):  # all-same-char, e.g. "xxxxxxxx"
        return False
    if PATH_VALUE_RE.fullmatch(
        v
    ):  # a file path (M365_CERT_KEY_FILE=/opt/…/cert.pem) is a locator, AJ1
        return False
    return not (v.startswith("<") and v.endswith(">"))  # <your-key> is not a credential


def internal_reason(key: str) -> str | None:
    """Why a key is internal config: "exact" / "prefix" (explicit declarations) or "substr"
    (a generic token such as _DB_PASSWORD that a vendor credential can legitimately carry)."""
    up = key.upper()
    if up in INTERNAL_EXACT:
        return "exact"
    if any(up.startswith(p) for p in INTERNAL_PREFIX):
        return "prefix"
    if any(tok in up for tok in INTERNAL_SUBSTR):
        return "substr"
    return None


def is_internal_config(key: str) -> bool:
    return internal_reason(key) is not None


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
    except (
        OSError
    ):  # the glob proved the path existed this run: unreadable, vanished or not a file → the
        raise  # "env files" cause, one line via CP2 — a silently dropped project fed DELETEs to the sync (CS2/CU2)
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
    hub_env = (
        OPT / "fabrik" / ".env"
    )  # the hub's own env is never a project's — wherever THIS copy lives (BW3)
    for env in sorted(OPT.glob("*/.env")):
        if env in (hub_env, OUTPUT, REPO / ".env"):
            continue
        if env.parent.name.startswith("_"):
            continue
        # the glob listed it: a listing the scan cannot stat (unreadable, vanished, a dangling
        # symlink) is the SAME refusal as an unreadable read (CS2/CU2) — `is_file()` swallowed
        # ENOENT and re-raised EACCES out of main as a traceback (CW1); a venv `.env` DIRECTORY or
        # a FIFO is no env file at all (CU1)
        if not stat.S_ISREG(env.stat().st_mode):
            continue
        files.append(env)
    return files


def load_catalog() -> tuple[dict, list[tuple[str, str]]]:
    """Catalog + matchers `[(PREFIX, provider)]` — curated `match` and model-merged `merged_match`.
    Fail-CLOSED on every catalog the chain cannot trust: unreadable, undecodable, not a JSON
    object (BS2) or a key that cannot round-trip (whitespace — AU7) is `CatalogError`, which
    `main` reports as a one-line error and exit 1, so the chain alerts and NOTHING is written —
    the previous consolidation stands. (BH3/BH6 once degraded these to "every provider flagged";
    synced into the registry that blanked every vendor's metadata, stored every credential
    unattributed and pruned under the bound.) A non-dict value under a provider key is metadata,
    ignored (AY8)."""
    try:
        raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (
        OSError,
        json.JSONDecodeError,
        UnicodeDecodeError,
    ) as exc:  # undecodable IS unreadable (BH3)
        raise CatalogError(f"{CATALOG_PATH} unreadable: {exc}") from exc  # fail closed (BS2)
    if not isinstance(raw, dict):  # a JSON list/string at the top level is unreadable too (BH6)
        raise CatalogError(f"{CATALOG_PATH} is not a JSON object")
    catalog = {k: v for k, v in raw.items() if not k.startswith("_") and isinstance(v, dict)}
    bad_keys = [k for k in catalog if _svc_token(k) != k]
    if bad_keys:  # a hand-edited key with whitespace would round-trip as a DIFFERENT provider (AU7)
        raise CatalogError(
            f"{CATALOG_PATH}: catalog keys must be single tokens (no whitespace): {bad_keys[:5]}"
        )
    matchers: list[tuple[str, str]] = []
    for provider, meta in catalog.items():
        for field in ("match", "merged_match"):  # curated prefixes + model-merged ones (BH1)
            raw_match = meta.get(field) or []
            for prefix in (
                raw_match if isinstance(raw_match, list) else [raw_match]
            ):  # a scalar is ONE prefix (BE4)
                if prefix is None or str(prefix) == "":
                    continue  # an empty prefix would match every `_`-prefixed key (BH8)
                matchers.append((str(prefix).upper(), provider))
    matchers.sort(
        key=lambda pm: len(pm[0]), reverse=True
    )  # readable dumps; match_provider/owned_by re-derive the longest from the hit set (BQ1)
    claims: dict[str, set[str]] = {}
    for prefix, provider in matchers:
        token = prefix.rstrip("_")
        if (
            token
        ):  # an all-`_` prefix routes nothing (prefix_hits skips it) and claims nothing (BW6)
            claims.setdefault(token, set()).add(provider)
    ties = {t: o for t, o in claims.items() if len(o) > 1}
    if ties:
        # a tie routes its keys to NEITHER vendor (BQ1) and re-flags the derived block for PAID
        # triage every run with tombstone and merge both inert (BS5): a catalog defect that costs
        # money daily FAILS the scan like a whitespace key does — the chain alerts, the previous
        # consolidation stands; a stderr warning in a cron log nobody tails was no channel (BW5)
        raise CatalogError(
            f"{CATALOG_PATH}: prefix claimed by two providers — keys under it route to neither: "
            + "; ".join(f"{t} ({', '.join(sorted(o))})" for t, o in sorted(ties.items()))
        )
    return catalog, matchers


def merged_matchers(catalog: dict) -> list[tuple[str, str]]:
    """Only the MODEL-merged prefixes (`merged_match`, written by classify's merge path) — the
    ones a credit fetcher must never trust (BH1)."""
    out: list[tuple[str, str]] = []
    for provider, meta in catalog.items():
        raw_c = meta.get("match") or []
        curated = {
            str(p).upper().rstrip("_") for p in (raw_c if isinstance(raw_c, list) else [raw_c])
        }
        raw = meta.get("merged_match") or []
        for prefix in raw if isinstance(raw, list) else [raw]:
            if prefix is None or str(prefix) == "":
                continue
            if str(prefix).upper().rstrip("_") in curated:
                # the same token the operator curated (`HF_` vs a merged `HF`): the model's copy adds
                # nothing but would disown the vendor's own keys through `top & merged` (BW4)
                continue
            out.append((str(prefix).upper(), provider))
    out.sort(key=lambda pm: len(pm[0]), reverse=True)
    return out


def prefix_hits(key: str, matchers: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Every `(TOKEN, provider)` whose prefix routes `key` — token-boundary (BRAVE matches
    BRAVE_API_KEY but NOT BRAVERY_API_KEY), and `EXA_` is the SAME token as `EXA`: a trailing `_`
    made two lengths of one token, so a one-character catalog edit beat the tie check and claimed
    another vendor's keys in every order (BS4). Shared by match_provider and registry_sync.owned_by."""
    up = key.upper()
    out: list[tuple[str, str]] = []
    for prefix, provider in matchers:
        token = str(prefix).upper().rstrip("_")
        if token and (up == token or up.startswith(token + "_")):
            out.append((token, provider))
    return out


def match_provider(key: str, matchers: list[tuple[str, str]]) -> str | None:
    """The provider whose LONGEST token routes `key`; None when nothing matches — or when two
    providers claim the same longest token: routing that tie by list order hands one vendor's key
    to the other, so it is attributed to neither, in every order (BQ1; registry_sync.owned_by
    mirrors)."""
    hits = prefix_hits(key, matchers)
    if not hits:
        return None
    longest = max(len(t) for t, _ in hits)
    top = {provider for t, provider in hits if len(t) == longest}
    return top.pop() if len(top) == 1 else None


def derive_provider(key: str) -> str:
    key = re.sub(
        r"_\d+$", "", key
    )  # GROQ_API_KEY_2 is groq's second key, not a vendor `groq_api_key_2` (AC1)
    stem = SERVICE_SHAPE_RE.sub("", key)
    stem = re.sub(
        r"_(SECRET_KEY|ACCESS_KEY|SECRET|TOKEN|KEY|URL|PASSWORD|USER|PASS|DSN)S?$",
        "",
        stem,
        flags=re.I,
    )
    # a `_`-prefixed name would be invisible to load_catalog (metadata convention) and re-billed
    # forever once tombstoned (AU4)
    return (
        (stem or key).lstrip("_") or key.lstrip("_") or "unnamed"
    ).lower()  # never `_`-prefixed or empty (AU4/AY3)


def _svc_token(v) -> str:
    """One whitespace-free token for the #svc line: whitespace (a model's `free tier`) becomes `_` — an
    unreadable line makes the consumer fail CLOSED (registry_sync AP2), so never emit one."""
    return (
        re.sub(r"[\s,]+", "_", str(v or "?").strip()) or "?"
    )  # `,` is the consumer's list delimiter (AY7)


def svc_line(name: str, meta: dict, used_by: set[str]) -> str:
    # one line, no quotes: keep the #svc line parseable by registry_sync.SVC_RE (AP2)
    cap = " ".join(str(meta.get("capability") or "?").split()).replace('"', "'") or "?"
    ub = ",".join(_svc_token(p) for p in sorted(used_by)) if used_by else "-"  # AS4
    # `or "?"` (not .get default) so an EMPTY catalog field still emits a \S+ token — else the
    # consumer regex (registry_sync.SVC_RE) fails to match and the whole service is dropped.
    cat = (
        _svc_token(meta.get("category")) if real_category(meta.get("category")) else "?"
    )  # a list's repr reached the DB while the block sat in triage (CP1)
    cost = _svc_token(meta.get("cost"))
    url = (
        re.sub(r"\s+", "_", str(meta.get("url") or "?").strip()) or "?"
    )  # a url may carry a legal `,` — only whitespace breaks a token here (C7)
    status = _svc_token(meta.get("status"))
    return (
        f"#svc name={_svc_token(name)} category={cat} cost={cost} "
        f'capability="{cap}" url={url} status={status} used_by={ub}'
    )


def cat_header(label: str) -> str:
    pad = "═" * 20
    return f"# {pad} {label} {pad}"


def consolidate(files: list[Path], code_dirs: list[Path] | None = None) -> tuple[str, dict]:
    """Build the category-grouped, #svc-annotated body + summary stats.

    `code_dirs` (repos to scan for `https://<host>` call sites) is the second input; None skips
    the scan (the env-key-only behaviour every pre-2026-09-02 test pins)."""
    catalog, matchers = load_catalog()
    adopted: set[str] = (
        set()
    )  # keys filed under a catalogued entry by NAME — said in the summary (CD3)

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
            # an explicit internal-config name (ALLOWED_ORIGINS, PORT, …) is never a service, even
            # when a catalog `match` prefix happens to cover it (review 2026-09-02, pass 2: a
            # code-host tombstone `allowed` with match ALLOWED swallowed a CORS setting)
            provider = match_provider(key, matchers)
            reason = internal_reason(key) if provider else None
            # an explicit declaration wins — except when BOTH the name and the value say credential
            # (`PROXY_API_KEY=<secret>` under a generic INTERNAL_PREFIX token must not be hidden, AF9).
            # The value half is `credential_grade`, not `is_secret` — the latter is true on the
            # NAME alone, which made the test one-factor and flipped `M365_CERT_KEY_FILE=/…/x.pem`
            # (a path under an explicit prefix) into a vendor credential (AJ1/AJ10)
            explicit_wins = reason == "exact" or (
                reason == "prefix" and not (SECRET_KEY_RE.search(key) and credential_grade(value))
            )
            if explicit_wins or (reason == "substr" and not is_secret(key, value)):
                # an EXPLICIT declaration (INTERNAL_EXACT / INTERNAL_PREFIX, e.g. M365_CERT_*) wins
                # unless name AND value both say credential; a GENERIC token (_DB_PASSWORD, _TIMEOUT) is decided by the value: a
                # vendor-prefixed config knob (ANTHROPIC_READ_TIMEOUT=120) is internal, a vendor
                # secret carrying the token (SUPABASE_DB_PASSWORD) stays the vendor's (T1/Z1/AC7)
                provider = None
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
                # a key NAMED for a catalogued vendor (`HUGGINGFACE_API_KEY` → `huggingface`) is that
                # vendor's — the name is the same evidence a model answer `name: huggingface` would
                # be — so it files under the entry instead of going to paid triage every lap (17 of
                # 109 entries curate no prefix for their own key; the classifier never sees a curated
                # name now, and the keeps that tried to protect it there are gone — CC1)
                meta = (
                    dict(catalog[name])
                    if name in catalog
                    else {
                        "category": "?",
                        "cost": "?",
                        "capability": "?",
                        "url": "?",
                        "status": "?",
                    }
                )
                if name in catalog:
                    adopted.add(name)
                dedupe = is_secret(key, value) and credential_grade(value)
                slot = value if dedupe else f"{key}\x00{value}"
                rec = svc_bucket(name, meta)[slot]
                rec["names"].add(key)
                rec["projects"].add(project)
            else:
                internal[(key, value)].add(project)

    # ---- second input: code call sites → attribute to a provider, or flag for triage ----
    code_hosts = scan_code_hosts(code_dirs) if code_dirs else {}
    url_index = catalog_url_index(catalog)
    code_only: set[str] = set()
    for host in sorted(code_hosts):
        provider = provider_for_host(host, catalog, url_index, matchers)
        if provider:
            name, meta = provider, catalog[provider]
        else:
            name = code_only_block_name(host, catalog)
            meta = {
                "category": "?",
                "cost": "?",
                "capability": "?",
                "url": f"https://{host}",
                "status": "?",
            }
        if name not in services:
            code_only.add(name)
        elif not real_category(services[name]["meta"].get("category")):  # the same predicate (CP1)
            if provider:  # an env-derived `?` bucket whose host names a CATALOGUED vendor adopts it
                services[name]["meta"] = dict(meta)  # … and leaves NEEDS-TRIAGE (pass 2, G8)
            elif services[name]["meta"].get("url", "?") == "?":
                # copy, never mutate: the bucket may reference a catalog entry by identity (Z15)
                services[name]["meta"] = dict(services[name]["meta"], url=f"https://{host}")
        rec = svc_bucket(name, meta)[f"CODE_HOST_URL\x00https://{host}"]
        rec["names"].add("CODE_HOST_URL")
        rec["projects"] |= code_hosts[host]["projects"]

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
            note.append(
                "used by: " + ", ".join(_svc_token(p) for p in sorted(rec["projects"]))
            )  # AU6
            lines.append(f"{primary}={value}   # " + " · ".join(note))

    by_cat: dict[str, list[str]] = defaultdict(list)
    for name, data in services.items():
        cat = data["meta"].get("category")
        by_cat[cat.strip() if real_category(cat) else "?"].append(
            name
        )  # `null`/a list/blank/` ? ` is `?` (BH6/CS1)

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

    catalogued = sum(1 for d in services.values() if real_category(d["meta"].get("category")))
    stats = {
        "projects": project_count,
        "total_lines": total_lines,
        "skipped_empty": skipped_empty,
        "services": len(services),
        "catalogued": catalogued,
        "flagged": len(services) - catalogued,
        "internal_lines": len(internal),
        "code_hosts": len(code_hosts),
        "code_only": len(code_only),
        "adopted": sorted(adopted),
    }
    return "\n".join(lines), stats


def real_category(cat) -> bool:
    """The ONE predicate for "this entry is catalogued": a non-empty string other than `?`. The
    bucketing, the `catalogued` stat and the classifier's tombstone loop all apply it — three
    hand-written variants once disagreed on `null`, a list and blank, so a block could count as
    catalogued while rendering under NEEDS-TRIAGE (CM3)."""
    return (
        isinstance(cat, str) and bool(cat.strip()) and cat.strip() != "?"
    )  # blank is `?` everywhere (CP1)


def refuse_emptied_catalog() -> None:
    """`{}` is a legitimate BOOTSTRAP (BR3) — not a catalog that just lost its vendors: when the
    previous consolidation carries catalogued `#svc` lines and the catalog now has no providers,
    the scan fails closed and the previous file stands (an emptied catalog would blank every vendor
    to `?` and hand the whole file to paid triage — BW11)."""
    if not OUTPUT.exists():
        return
    known = sum(
        1
        for ln in read_existing_body(OUTPUT).splitlines()
        if ln.startswith("#svc ")
        and not re.match(
            r"#svc name=\S+ category=\?(?: |$)", ln
        )  # the FIELD at its position, never the literal in a capability (CM6/CP3)
    )
    if known and not load_catalog()[0]:
        raise CatalogError(
            f"{CATALOG_PATH} has no providers but the last consolidation knew {known} catalogued vendor(s) — an emptied catalog would blank them all; restore it"
        )


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


def inputs_refusal(exc: OSError) -> str:
    """The one line for every input the scan could not list, stat or read (CS2/CP2/CW1)."""
    return f"ERROR: the scan could not read its inputs ({getattr(exc, 'filename', None) or exc}) — nothing written; the previous consolidation stands"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the file (default: dry-run)")
    args = ap.parse_args()

    try:
        files = project_env_files()
    except OSError as exc:  # a listed `.env` the scan cannot stat — the "env files" cause, the same one line as the read (CW1); an unlistable `/opt` never raises (the glob yields nothing) and takes the line below
        print(inputs_refusal(exc), file=sys.stderr)
        return 1
    if not files:
        print(
            "No project .env files found under /opt/*/.env (or /opt cannot be listed)",
            file=sys.stderr,
        )
        return 1

    try:
        refuse_emptied_catalog()
    except CatalogError as exc:  # the guard's own refusal (BW11): the typed one-liner
        print(f"ERROR: {exc} — nothing written; the previous consolidation stands", file=sys.stderr)
        return 1
    except OSError as exc:  # the guard's read of the previous file — the same one line as the write (CE7/CJ1); ONLY the guard, so an OSError elsewhere is never blamed on the output file (CM5)
        print(
            f"ERROR: cannot read or write {OUTPUT}: {exc} — nothing written; the previous consolidation stands",
            file=sys.stderr,
        )
        return 1
    try:
        body, stats = consolidate(files, code_dirs=project_dirs())
    except (
        CodeScanError,
        CatalogError,
    ) as exc:  # only the TYPED catalog error is a one-liner (AY4/BB6/BD1)
        print(f"ERROR: {exc} — nothing written; the previous consolidation stands", file=sys.stderr)
        return 1
    except OSError as exc:  # an unreadable project env file (CS2), or `/opt` losing its listing between the glob and the scan: the "env files" cause, one line (CP2)
        print(inputs_refusal(exc), file=sys.stderr)
        return 1
    header = (
        "# AUTO-GENERATED by scripts/gather_envs.py - DO NOT EDIT BY HAND\n"
        "# Service metadata is sourced from scripts/service_catalog.json (edit THERE).\n"
        f"# Generated: {datetime.now(UTC).isoformat(timespec='seconds')}\n"
        f"# {stats['projects']} projects | {stats['services']} services "
        f"({stats['catalogued']} catalogued, {stats['flagged']} need triage) | "
        f"{stats['internal_lines']} internal-config vars | "
        f"{stats['code_hosts']} code-referenced hosts ({stats['code_only']} providers seen ONLY in code)\n#\n"
    )
    content = header + body + "\n"

    summary = (
        f"{stats['projects']} projects | {stats['total_lines']} env lines "
        f"({stats['skipped_empty']} empty skipped) -> {stats['services']} services "
        f"({stats['catalogued']} catalogued, {stats['flagged']} NEED TRIAGE), "
        f"{stats['internal_lines']} internal-config, "
        f"{stats['code_hosts']} code hosts ({stats['code_only']} code-only providers)"
    )

    # the scan's one silent routing decision, said on EVERY path — dry-run, no-change and write —
    # as the ENTRIES a key named for them adopted (names only; CD3/CE6)
    print("entries adopted by a key named for them:", ", ".join(stats["adopted"]) or "none")
    if not args.apply:
        print("[dry-run]", summary)
        print("Re-run with --apply to write", OUTPUT)
        return 0

    try:  # every OSError on the output path — mkdir, the previous file, the write — is one line (CD4/CE7)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        swept = sweep_stale_tmp(OUTPUT)  # also on a no-change day (BA2)
        if swept:  # a killed run left the credential set beside the target — say so (BE9)
            print(
                f"WARNING: swept {swept} stale secrets tmp file(s) beside {OUTPUT}", file=sys.stderr
            )
        if read_existing_body(OUTPUT).rstrip() == body.rstrip():
            print("no change - already up to date:", OUTPUT)
            return 0
        write_secret_file(OUTPUT, content)
    except OSError as exc:
        print(
            f"ERROR: cannot read or write {OUTPUT}: {exc} — nothing written; the previous consolidation stands",
            file=sys.stderr,
        )
        return 1
    print("wrote", OUTPUT, "|", summary)
    return 0


def sweep_stale_tmp(out: Path) -> int:
    """Remove a crashed run's leftover tmp beside `out`: any `<out>.tmp*` REGULAR file older than an
    hour — the legacy shared name included, age-gated like the rest (a pre-AW1 writer still on an
    old checkout is a live sibling during the transition — BB7), our own pid included (a leftover
    under a reused pid would otherwise make `O_EXCL` fail — BB2). Runs on EVERY apply, before the
    no-change short-circuit (BA2). `lstat`, never follow a symlink; a sibling run unlinking the
    same file first, a directory or a dangling link is a skipped entry, never a traceback (BA1/BB3)."""
    swept = 0
    for stale in out.parent.glob(out.name + ".tmp*"):
        try:
            st = stale.lstat()
            if not stat.S_ISREG(st.st_mode) or time.time() - st.st_mtime <= 3600:
                continue
            stale.unlink()
            swept += 1
        except OSError:  # gone (a sibling swept it) or not ours to touch — skip
            continue
    return swept


def write_secret_file(out: Path, content: str) -> None:
    """Atomic 0600 write: mode 0600 from the first byte (write-then-chmod leaves a world-readable
    window with every fleet credential on disk), and the tmp never outlives a CATCHABLE failure
    (AU10) — a SIGKILL (`timeout -k`) cannot be caught, so a per-process leftover is swept by
    `sweep_stale_tmp` on the next apply — change or no change — once it is an hour old (AW1/AY6/BA2);
    it is 0600 and gitignored meanwhile."""
    # a PER-PROCESS tmp name: with one shared `.tmp` a manual run racing the cron unlinked the other
    # writer's in-progress file and the first `os.replace` then installed the second writer's
    # PARTIAL file as the secrets file (AW1). `O_EXCL` on a fresh name also refuses a planted
    # symlink. A crashed run's leftover (SIGKILL — the except below covers everything else) is
    # swept only when it is older than an hour, so a live sibling's tmp is never touched.
    tmp = out.with_name(f"{out.name}.tmp.{os.getpid()}")
    # a leftover under OUR pid younger than the sweep's hour (a crash and a pid reuse within it)
    # cannot belong to a live process — no other live process has our pid — so it is ours to
    # remove before `O_EXCL` (BD4)
    try:
        tmp.unlink(missing_ok=True)
    except OSError:  # a DIRECTORY at our own tmp name: let O_EXCL below say so (BH7)
        pass
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.chmod(tmp, 0o600)
        os.replace(tmp, out)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    sys.exit(main())
