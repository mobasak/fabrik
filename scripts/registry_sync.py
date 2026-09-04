#!/usr/bin/env python3
# AFTER-EDIT: scripts/registry_db.py db/services_registry_schema.sql scripts/tests/test_registry_sync.py scripts/gen_dashboard.py
"""Load secrets/all-envs.env (the #svc-annotated consolidation) into the local Postgres registry.

Reads each #svc block + its KEY=value lines and upserts `services` + `api_keys`. Stores
value_sha256 (SHA-256 of the secret) — NEVER the raw secret (the secret lives only in
all-envs.env, chmod 600). Idempotent: ON CONFLICT upserts and only bumps last_seen on re-run.
internal-config vars are excluded (not services).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(Path(__file__).resolve().parent) not in sys.path:  # once (B67-8, FG1)
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import gather_envs  # noqa: E402 - the one classifier of secret vs config, shared with the scan
import registry_db  # noqa: E402
from credit_fetchers import fetch_balance  # noqa: E402

ALL_ENVS = REPO / "secrets" / "all-envs.env"
SVC_RE = gather_envs.SVC_LINE_RE  # ONE header shape, owned by the generator that writes it: the classifier validates a triage header against it BEFORE the paid dispatch, this reader refuses what it does not match (E67-7, FG1)
# A key NAME that carries a credential (the value is a secret): the fetcher's input.
CREDENTIAL_KEY_RE = re.compile(
    r"(API_KEY|APIKEY|API_TOKEN|ACCESS_TOKEN|TOKEN|SECRET|PASSWORD|PASSPHRASE|PASSWD|AUTH_KEY"
    r"|CREDENTIALS|(?<!MON)(?<!TUR)(?<!HOC)(?<!JOC)(?<!DON)KEY|(?<!BY)(?<!COM)(?<!SUR)(?<!TRES)PASS"
    r"|(?:^|_)(?:PW|PWD|CREDS))S?(_\d+)?$",  # numbered keys anchored (AM1/AM8)
    re.I,  # `KEY`/`PASS` stay glued-anchored (SEDO_SIGNKEY, MASTERKEY, DBPASS — AS2) minus the
)  # measured English noise (MONKEY, TURKEY, HOCKEY, JOCKEY, DONKEY, BYPASS, COMPASS, SURPASS, TRESPASS — AP8)
# The fetcher-grade subset of the anchored names: a key/token outranks a password, and a name
# marked PUBLIC/ANON/PUBLISHABLE is the last resort (`NEXT_PUBLIC_SUPABASE_ANON_KEY` must never
# beat `SUPABASE_SECRET_KEY` — AP3)
FETCHER_KEY_RE = re.compile(
    r"(API_KEY|APIKEY|API_TOKEN|ACCESS_TOKEN|SECRET_KEY|SERVICE_ROLE_KEY|APPLICATION_KEY|TOKEN)S?(_\d+)?$",
    re.I,
)
PUBLIC_NAME_RE = re.compile(
    r"(?:^|_)(PUBLIC|ANON|PUBLISHABLE|PUBKEY|PUB)(?:_|$)", re.I
)  # bounded: CANONICAL is not ANON (AS8)


# Public identifiers (OAuth client/tenant/account/project ids) are long, alphanumeric and NOT
# secrets — value entropy alone calls them credentials (AD1: M365_CLIENT_ID, GOOGLE_CLIENT_ID,
# R2_ACCOUNT_ID …, 26 live pairs). A credential is credential-shaped by NAME, or secret-shaped by
# value with a name that is not an identifier.
# The identifier token may carry ONE trailing qualifier (`CLOUDFLARE_ZONE_ID_OCORON`,
# `N8N_WEBHOOK_CONTENT` — a per-tenant or per-purpose suffix, AJ4); a qualifier that is itself a
# secret token (`_HOST_AUTH`) never demotes — `is_credential` checks it. Locators (`_FILE`, `_PATH`,
# `_REPOSITORY`, `_WEBHOOK`, `_PROXY`) and account names (`_USER`) are identifiers too.
IDENTIFIER_KEY_RE = re.compile(
    r"(_ID|_IDS|_UUID|_NUMBER|_ARN|_REGION|_ZONE|_HOST|_PORT|_MODEL|_VERSION|_URL|_URLS|_ENDPOINT"
    r"|_BASE|_DOMAIN|_FILE|_PATH|_DIR|_DIRS|_FOLDER|_THUMBPRINT|_REPOSITORY|_REPO|_WEBHOOK|_PROXY|_USER|_USERNAME)"
    r"(?P<qualifier>_[A-Z0-9]+)?$",
    re.I,
)
# a DSN/URL that CARRIES a password (`scheme://user:pw@host`, or the scheme-less proxy form
# `user:pw@host:port` — AM7) is a credential whatever its name
# scheme form: the username may be EMPTY (`redis://:pw@host`, the canonical Redis/AMQP shape —
# AP5); scheme-less form: only the proxy shape `user:pw@host:port` (AM7), never any `x:y@…`
# (`sip:alice@example.com` is not a credential — AP6)
USERINFO_RE = re.compile(r"(?:^[^/@\s:]*:[^/@\s:]+@[^/@\s:]+:\d+$|://[^/@\s:]*:[^/@\s]+@)")
# a knob VALUE: a bare word (`false`, `basic`, `on`) or a number — never a secret, whatever the
# name's unanchored token says (`WEBSHARE_IP_AUTH=false`, AH1); a weak real secret (`1234` under
# `_PASSPHRASE`) stays a credential because its NAME is anchored (AM6)
KNOB_VALUE_RE = re.compile(r"[A-Za-z_-]{1,12}|\d+(\.\d+)?")


def is_credential(key: str, value: str) -> bool:
    """`kind` is decided by the NAME first — the value-entropy branch of `gather_envs.is_secret`
    calls any 24+-char alphanumeric value a secret (API URLs, tenant ids, model names — 48 live
    vendor rows, AF1). Order: an ANCHORED credential suffix (`_API_KEY`, `_TOKEN`, `_SECRET`,
    `_PASSWORD` …) → yes; a value embedding `user:pw@` → yes; URL/identifier-shaped name → no; an
    UNANCHORED secret token in the name (`_AUTH`, `DSN`, `SIGNING` — `WEBSHARE_IP_AUTH=false`, AH1)
    counts unless the value is knob-shaped (a bare word or a number); otherwise the value decides."""
    if gather_envs.PATH_VALUE_RE.fullmatch(value):
        return False  # a path is a LOCATOR whatever the name says (GOOGLE_APPLICATION_CREDENTIALS=/…/sa.json, AM11)
    if CREDENTIAL_KEY_RE.search(key):
        return True
    if USERINFO_RE.search(value):
        return True
    ident = IDENTIFIER_KEY_RE.search(key)
    if ident and not gather_envs.SECRET_KEY_RE.search(ident.group("qualifier") or ""):
        return False
    return gather_envs.is_secret(key, value) and not (
        gather_envs.SECRET_KEY_RE.search(key) and KNOB_VALUE_RE.fullmatch(value)
    )


def catalog_provenance() -> tuple[list[tuple[str, str]], set[tuple[str, str]]] | None:
    """(every matcher longest-first, the MODEL-merged subset) from the catalog, loaded once per
    sync — or None when the catalog cannot be read (unreadable, not an object, an unround-trippable
    key — `load_catalog` fails closed on all of them, BS2): provenance UNKNOWN, so no key is
    attributable and no credit fetch happens, while the DB sync itself still runs (fail closed on
    the fetch only — BK1/BK7). An EMPTY catalog is KNOWN, not unknown: nothing curated and nothing
    model-merged, so every key is its derived block's own — conflating the two made a bootstrap
    registry exit 2 forever (BR3)."""
    try:
        catalog, matchers = gather_envs.load_catalog()
    except gather_envs.CatalogError as exc:
        print(
            f"WARNING: catalog provenance UNKNOWN — {exc}", file=sys.stderr
        )  # the REASON, or the exit-2 page names nothing (BS8)
        return None
    return matchers, set(gather_envs.merged_matchers(catalog))


def owned_by(
    key: str, provider: str, prov: tuple[list[tuple[str, str]], set[tuple[str, str]]] | None
) -> bool:
    """False when the prefix that ROUTED this key (the longest match over curated + merged
    prefixes) is a MODEL-merged one — classify's AD2 merge of a flagged provider into an existing
    vendor, the one route by which a wrong model `name` puts another provider's secret in this
    block. A curated `match` alias (`HF_TOKEN` → huggingface) is ownership even when a shorter
    merged prefix (`HF`) would also match (BH1/BK3). Unknown provenance is never ownership (BK1)."""
    if prov is None:
        return False
    matchers, merged = prov
    hits = gather_envs.prefix_hits(key, matchers)  # one token per prefix, `EXA_` == `EXA` (BS4)
    if not hits:
        return True
    longest = max(len(t) for t, _ in hits)
    top = {(t, pr) for t, pr in hits if len(t) == longest}
    merged_tokens = {(str(p).upper().rstrip("_"), pr) for p, pr in merged}
    # a key is owned only when the LONGEST token that routes it is THIS block's provider's and
    # curated: a stale block carrying another vendor's key (`DEEPL_API_KEY` under `exa`) is never
    # that vendor's fetcher input (BM1). Equal-length tokens of TWO providers are a collision the
    # catalog cannot settle: ambiguous is unowned in every JSON order — taking the first hit of a
    # stable length-sort gave the key to whichever vendor sorted first (BQ1).
    return {pr for _, pr in top} == {provider} and not (top & merged_tokens)


def credential_rank(key: str, value: str) -> int:
    """The credit fetcher's input, chosen by KEY ROLE (N1/O5, restored after AH2 made it positional
    — AM1; tiers split after AP3 found 21 of 24 multi-credential providers still tied at rank 0):
    0 = a fetcher-grade anchored NAME (`_API_KEY`, `_TOKEN`, `_SECRET_KEY`, numbered too),
    1 = another anchored name (`_PASSWORD`, `_ACCESS_KEY`), 2 = a credential-kind value that is
    not URL-shaped (`X_SIGNATURE=<secret>`), 3 = a userinfo DSN (a provider whose ONLY credential
    is a DSN still feeds the fetcher, AH2), 4 = an anchored name marked PUBLIC/ANON/PUBLISHABLE —
    the LAST resort, below every real secret (AS9). Equal ranks break by the file's order, which
    `gather_envs` writes name-sorted and, for two values under ONE name, value-sorted — a stated,
    deterministic rule (rotating a key can therefore change which value the fetcher reports, AS7)."""
    if CREDENTIAL_KEY_RE.search(key):
        if PUBLIC_NAME_RE.search(key):
            return 4
        return 0 if FETCHER_KEY_RE.search(key) else 1
    if "://" in value or USERINFO_RE.search(value):
        return 3
    return 2


def ensure_schema(cur) -> None:
    """Idempotent forward migration: `api_keys.kind` ('credential' | 'config' | 'code-host' | 'credential-unattributed') — a code
    call-site row is a public URL's digest, not a secret, and the dashboard must not count it
    as a key (review 2026-09-02, O4). `db/services_registry_schema.sql` carries the column for
    fresh installs; this brings an existing registry level on its next sync."""
    # Probe first: even a no-op `ADD COLUMN IF NOT EXISTS` takes ACCESS EXCLUSIVE, which waits
    # behind ANY open reader transaction (an idle dashboard-server read stalled the daily sync
    # in review, closing pass — N3). The probe is ACCESS SHARE; the ALTER runs once, ever.
    cur.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() "
        "AND table_name='api_keys' AND column_name='kind'"
    )
    if cur.fetchone() is None:
        cur.execute(
            "ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'credential'"
        )


KV_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def parse(path: Path) -> list[dict]:
    """Return [{meta:{name,category,...,used_by}, keys:[(key, value, aliases)]}] per provider."""
    provs: list[dict] = []
    cur: dict | None = None
    bad: list[str] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        s = re.sub(
            r"^[\s\ufeff]+|[\s\ufeff]+$", "", line
        )  # a hand-edit's leading space/tab or a mid-file BOM is not a second provider (FC3); EVERY BOM, anywhere in the MARGIN — a mixed `\ufeff \ufeff` survived two strips (FD7/FE5); the margin ONLY: the whole-line replace mutated a value and stored a digest of a secret that does not exist (FF1)
        if re.match(r"#.*═", s) and not re.match(r"#[#\s]*#?svc\b", s, re.I):
            # section header — on the STRIPPED line, like the #svc header (FD7); `#═══` with the space dropped by a hand-edit is a header too (FE5); `## ═══` commented twice is a header too, like `## #svc` — 315 internal-config names folded under the provider above it otherwise (FF1)
            cur = None  # a header ends the current provider block (incl. internal-config)  # a `#svc` line is NEVER a header, whatever its free-text capability holds: `#.*═` swallowed a provider whose capability carried `═` and dropped it with no `bad` entry — then the prune deleted its keys and credit history (R68-C1, FH1)
            continue
        if re.match(
            r"#[#\s]*#svc\b", s, re.I
        ):  # `## #svc` — a line commented twice — folded its keys under the neighbour (FE5)
            cur = None  # a COMMENTED-OUT provider ends the block: its keys belong to nobody, never to the neighbour (FD7)
            continue
        m = SVC_RE.fullmatch(
            s
        )  # `.match` accepted a line that CONCATENATED two providers, folding the second's keys under the first — the very AP2 class (EY3); trailing whitespace tolerated (EZ4)
        if m:
            name = m.group("name")
            if name != name.lower() or not gather_envs.SVC_NAME_RE.fullmatch(
                name
            ):  # ONE rule, shared with the classifier's pre-spend guard (E68-3, FH1)
                cur = None
                bad.append(
                    f"provider name the catalog cannot hold: {name!r}"
                )  # the catalog's own key rule (lowercase, one token) — the classifier refuses it BEFORE the spend, this reader refuses it here (F67-11)
                continue
            if name in seen:
                # two blocks under one name: the second's keys silently DELETED the first's on
                # the same sync — refused like any unreadable header (FC3)
                cur = None
                bad.append(f"duplicate #svc name={name}")
                continue
            seen.add(name)
            cur = {"meta": m.groupdict(), "keys": []}
            provs.append(cur)
            continue
        if re.match(r"#svc(\s|$)", s, re.I):
            # the TOKEN, in any case, however indented: a leading space or `#SVC` folded the next
            # provider's keys under the previous one after FB1 (which caught a tab and a bare
            # `#svc`); `#svcs are listed below` is a comment, never a header (FC3)
            # a #svc line SVC_RE cannot read ENDS the block and FAILS the sync: absorbing the next
            # provider's keys under the previous one would prune the provider, misattribute its
            # keys and hand its secret to another vendor's credit fetcher (AP2)
            cur = None
            bad.append(line[:120])
            continue
        kv = KV_RE.match(
            s
        )  # the HEADER's order: an indented-then-BOM key was dropped by the FD7 order and then pruned (FE5)
        if cur is not None and not kv and s and not s.startswith("#"):
            # a non-blank, non-comment line inside a provider block that is not KEY=value (`A-B=1`,
            # `1KEY=x`) was silently dropped — then PRUNED from the registry; fail closed like an
            # unreadable #svc line (FE5)
            cur = None
            bad.append(
                re.sub(r"=.*", "=<redacted>", line)[:120]
            )  # a KEY=value line's VALUE is a secret and this message rides into the chain log in cleartext (R68-C7, FH1)
            continue
        if cur is not None and kv:
            key, rest = kv.group(1), kv.group(2)
            # "   # " (3-space-hash-SPACE) is gather_envs' exact note delimiter; splitting on it
            # (not "   #") avoids truncating a value that merely contains "   #".
            value = rest.split("   # ", 1)[0]
            if value.endswith("   #") and line.rstrip("\r\n").endswith("   # "):
                value = value[
                    :-4
                ]  # an EMPTY note (`   # ` with the space stripped by the margin rule) is no value (FF1) — decided on the RAW line's trailing space, so a value that legitimately ends in `   #` keeps it (R67-11)
            value = value.strip()
            note_text = rest.split("   # ", 1)[1] if "   # " in rest else ""
            if (
                "multi-line value, newlines escaped" in note_text
            ):  # the NOTE, never the value: a secret that merely CONTAINS the marker phrase had every literal `\n` in it rewritten, and the stored digest was of a string that is not the secret (R68-C5, FH1)
                value = re.sub(
                    r"\\(.)", lambda m: "\n" if m.group(1) == "n" else m.group(1), value
                )  # the symmetric inverse of `_escape_newlines` (backslash-aware): gather escapes a real newline so this reader can read the line at all; the DIGEST and the fetch credential must be the SECRET, not its rendering (E67-2, FG1). Mirror: a secret that literally contains backslash-n collides with one holding a newline — the note is the discriminator, and the generator only writes it for a real newline
            aliases: list[str] = []
            per_key_used: list[str] = []
            if "   # " in rest:
                note = rest.split("   # ", 1)[1]
                if "aliases:" in note:
                    seg = note.split("aliases:", 1)[1].split("·")[0]
                    aliases = [a.strip() for a in seg.split(",") if a.strip()]
                if "used by:" in note:
                    seg = note.split(
                        "used by:", 1
                    )[
                        1
                    ].split(
                        "·"
                    )[
                        0
                    ]  # up to the separator, like `aliases:` — the FF4 multi-line note landed AFTER `used by:` and two fake projects were written to the DB (E67-1, FG1)
                    per_key_used = [p.strip() for p in seg.split(",") if p.strip()]
            cur["keys"].append((key, value, aliases, per_key_used))
    if bad:
        raise ValueError(
            f"{len(bad)} unreadable line(s) (a #svc header, a duplicate name, or a KEY=value line) in {path} — fail closed (AP2/FE5): {bad[:5]}"
        )  # the message named every refusal an "unparseable #svc line" — a KV line sent the operator to the wrong construct (FF1)
    return provs


def sync_registry(
    dsn: str | None = None,
    fetch_credits: bool = False,
    prune: bool = True,
    prune_keys: bool
    | None = None,  # default = prune; a PARTIAL file must not delete a provider's other keys (Z7)
) -> dict:
    if dsn:
        os.environ["SERVICES_REGISTRY_DSN"] = dsn
    provs = parse(ALL_ENVS)
    stats = {
        "services": 0,
        "api_keys": 0,
        "credit_snapshots": 0,
        "pruned": 0,
        "keys_pruned": 0,
        "unattributed": 0,
        "provenance_unknown": False,
    }
    to_fetch: list[tuple[int, str, str]] = []
    prov = (
        catalog_provenance()
    )  # model-merged prefixes never feed a fetcher; unknown = none do (BH1/BK1)
    stats["provenance_unknown"] = prov is None
    conn = registry_db.connect()
    # Schema first, in its OWN short transaction: an ALTER inside the sync transaction holds an
    # ACCESS EXCLUSIVE lock on api_keys for the whole run (measured: the no-op ADD COLUMN IF NOT
    # EXISTS still takes it), blocking the live dashboard server's reads (closing review 2026-09-02).
    try:
        with conn, conn.cursor() as cur:
            ensure_schema(cur)
    except Exception:
        conn.close()
        raise
    try:
        with conn, conn.cursor() as cur:
            # Bounded-prune denominator: the PRE-EXISTING registry size, captured BEFORE the
            # upserts below insert this file's providers — else a corrupt file that ADDS many
            # bogus rows inflates the denominator and a mass real-provider delete slips under
            # the cap (the exact irreversible outcome the bound exists to prevent).
            cur.execute("SELECT count(*) FROM services")
            preexisting_total = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM api_keys")
            preexisting_keys = int(
                (cur.fetchone() or (0,))[0] or 0
            )  # the key-prune bound's denominator (FE5)
            for p in provs:
                meta = p["meta"]
                ub = meta.get("used_by") or ""
                used_by = [x for x in ub.split(",") if x and x != "-"]
                cur.execute(
                    """INSERT INTO services (provider, category, cost_tier, url, status)
                       VALUES (%s,%s,%s,%s,%s)
                       ON CONFLICT (provider) DO UPDATE SET category=EXCLUDED.category,
                         cost_tier=EXCLUDED.cost_tier, url=EXCLUDED.url, status=EXCLUDED.status
                       RETURNING id""",
                    (meta["name"], meta["category"], meta["cost"], meta["url"], meta["status"]),
                )
                sid = cur.fetchone()[0]
                stats["services"] += 1
                fetch_candidates: list[tuple[int, str, str]] = []  # (rank, value, digest)
                digests: list[str] = []
                kinds_by_digest: dict[str, str] = {}
                used_by_digest: dict[str, set[str]] = {}
                aliases_by_digest: dict[str, list[str]] = {}
                for _key, value, aliases, per_key_used in p["keys"]:
                    if not value:
                        continue
                    # The credit fetcher gets the first CREDENTIAL, chosen by the KEY's role, never
                    # by line order: `CODE_HOST_URL` sorts before `DEEPL_API_KEY` and
                    # `AZURE_ACCOUNT_NAME` before `AZURE_API_KEY` (review 2026-09-02, N1 + O5).
                    # `code-host` is the SYNTHETIC key only — never a value shape: a proxy URL with
                    # userinfo (`NAMECHEAP_PROXY_URL=http://u:pw@…`) is a credential (pass 2, G3)
                    if _key == "CODE_HOST_URL":
                        kind = "code-host"
                    elif is_credential(_key, value):
                        kind = "credential"
                    else:
                        kind = "config"  # a URL/host/port/model/ID knob under a vendor prefix — never a key (AC6/AD1)
                    if kind == "credential" and not owned_by(_key, meta["name"], prov):
                        # the key reached this block through a MODEL-merged prefix (or provenance is
                        # unknown): stored as UNATTRIBUTED — never counted as the vendor's key on the
                        # dashboard, never a fetcher candidate, and said aloud (a NAME, never a
                        # value) so the misattribution is visible even where no fetcher exists (BH1/BK8)
                        kind = "credential-unattributed"
                        stats["unattributed"] += 1
                        print(
                            f"WARNING: {meta['name']}: {_key} is not attributable to it (model-merged prefix or unknown provenance) — stored unattributed, no credit fetch",
                            file=sys.stderr,
                        )
                    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
                    if (
                        kind == "credential"
                        and kinds_by_digest.get(digest) == "credential-unattributed"
                    ):
                        kind = "credential-unattributed"  # two names, one value: the RESTRICTIVE kind wins whatever the order (BM5)
                    if kind == "credential-unattributed":
                        kinds_by_digest[digest] = kind
                    if kind == "credential":
                        # a fetch CANDIDATE only, chosen after the loop once every name carrying
                        # this value is seen: chosen here, a value later stored unattributed under
                        # its other name had already been sent to the vendor (BS12)
                        fetch_candidates.append((credential_rank(_key, value), value, digest))
                    if (
                        digest not in digests
                    ):  # one ROW per digest — the counter said 808 for 802 rows (BS7)
                        stats["api_keys"] += 1
                    digests.append(digest)
                    # per-key attribution when present (a multi-key provider's keys differ),
                    # else the provider-wide union from the #svc used_by= field.
                    key_used = per_key_used or used_by
                    # two names, one value: the row is ONE per digest, so its attribution is the
                    # UNION over every name that carries the value — the last name's list alone
                    # dropped projects (2 live rows, BR6); the last upsert carries the full union
                    seen_used = used_by_digest.setdefault(digest, set())
                    seen_used.update(key_used)
                    seen_alias = aliases_by_digest.setdefault(digest, [])
                    seen_alias.extend(a for a in aliases if a not in seen_alias)
                    cur.execute(
                        """INSERT INTO api_keys (service_id, value_sha256, aliases, used_by_projects, kind)
                           VALUES (%s,%s,%s,%s,%s)
                           ON CONFLICT (service_id, value_sha256)
                           DO UPDATE SET last_seen=now(), aliases=EXCLUDED.aliases,
                             used_by_projects=EXCLUDED.used_by_projects, kind=EXCLUDED.kind""",
                        (sid, digest, seen_alias, sorted(seen_used), kind),
                    )
                # Keys that LEFT this provider (a code host no longer referenced, a var moved to
                # internal-config) are deleted — upsert-only rows lived forever, and the code-host
                # input makes churn daily (closing review 2026-09-02, N2). Per-service, never global.
                if digests and (
                    prune if prune_keys is None else prune_keys
                ):  # `<> ALL('{}')` is TRUE for every row
                    cur.execute(
                        "DELETE FROM api_keys WHERE service_id=%s AND value_sha256 <> ALL(%s)",
                        (sid, digests),
                    )
                    stats["keys_pruned"] += cur.rowcount
                    keys_allowed = max(
                        10, preexisting_keys // 5
                    )  # CUMULATIVE over the lap (a systemic parse failure prunes a few keys from EVERY provider — a per-DELETE bound never fires). The floor is ABSOLUTE: FF1's `len(provs)` term read the denominator from the corrupt INPUT and was 54% of the live key table (456 of 839 deletable in one lap; a regeneration emitting 5 000 providers would allow 5 000) — the inflation GUARD 1 refuses (R67-1, FG1); ten covers six honest rotations on a 20-key registry
                    if stats["keys_pruned"] > keys_allowed and os.getenv(
                        "REGISTRY_PRUNE_FORCE", ""
                    ).strip().lower() not in ("1", "true", "yes"):
                        # GUARD 2 for api_keys: a systemic KV-parse failure dropped every key from
                        # every provider while `services` stayed intact, so the service guard never
                        # fired and the whole key history went in one lap (FE5)
                        raise RuntimeError(
                            f"bounded prune: refusing to delete {stats['keys_pruned']}/{preexisting_keys} "
                            f"api_keys (> {keys_allowed} allowed) — all-envs.env is likely corrupt/"
                            "truncated; no changes applied (transaction rolled back). Set "
                            "REGISTRY_PRUNE_FORCE=1 to override deliberately."
                        )
                cred = next(
                    (
                        v
                        for _rank, v, d in sorted(fetch_candidates, key=lambda c: c[0])
                        if kinds_by_digest.get(d) != "credential-unattributed"
                    ),
                    None,
                )  # by role then file order (AM1/AH2); only OWNED credentials, never a value stored unattributed under another name (BH1/BK8/BS12)
                if fetch_credits and cred:
                    to_fetch.append((sid, meta["name"], cred))  # fetch AFTER commit
            # Prune orphans: services no longer in all-envs.env (e.g. a provider recatalogued
            # under a new match prefix leaves its old `?` row behind). Children cascade-delete.
            # GUARD 1: never prune when the parse yielded nothing — an empty/corrupt file must not
            # wipe the whole registry. `prune=False` is for callers syncing a PARTIAL file (e.g.
            # tests with a one-provider fixture) that must not delete the rest of the registry.
            # GUARD 2 (bounded prune): a mass-delete means the FILE is wrong (corrupted #svc lines
            # dropping providers from `seen`), not the registry — cascade-deleting credit_snapshots
            # history is irreversible, so refuse loudly instead of pruning silently. Cap: roughly
            # >20% of the registry (integer //5, min 5) aborts the whole transaction (upserts
            # included — sync fails loud).
            seen = [p["meta"]["name"] for p in provs]
            if prune and seen:
                cur.execute("DELETE FROM services WHERE provider <> ALL(%s)", (seen,))
                allowed = max(5, preexisting_total // 5)
                # Explicit truthy values ONLY — a conventional "0"/"false"/"no" must NOT
                # silently disable a data-loss guard (any-non-empty truthiness would).
                force = os.getenv("REGISTRY_PRUNE_FORCE", "").strip().lower() in (
                    "1",
                    "true",
                    "yes",
                )
                if cur.rowcount > allowed and not force:
                    raise RuntimeError(
                        f"bounded prune: refusing to delete {cur.rowcount}/{preexisting_total} "
                        f"services (> {allowed} allowed) — all-envs.env is likely corrupt/"
                        "truncated; no changes applied (transaction rolled back). If this is a "
                        "LEGITIMATE mass recatalog, re-run once with REGISTRY_PRUNE_FORCE=1."
                    )
                stats["pruned"] = cur.rowcount
    finally:
        conn.close()
    # Hybrid credit: fetch balances OUTSIDE the upsert transaction — network I/O must never hold
    # the services/api_keys row locks. fetch_balance never raises (guarded); a dead vendor => no
    # snapshot. The REAL key stays host-side (sent only to the vendor's own API).
    if to_fetch:
        # the sync transaction above has COMMITTED: a failure here is a credit-phase failure of a
        # registry that IS written — it was reported as "nothing written" and the chain skipped
        # the dashboard for a synced registry (FC3)
        conn2 = None
        try:
            conn2 = registry_db.connect()  # a failure here is a WARNING and exit 3: the chain alerts it without failing the step (FD7)
            for sid, name, value in to_fetch:
                snap = fetch_balance(name, value)
                if snap is not None:
                    with conn2, conn2.cursor() as cur:
                        cur.execute(
                            "INSERT INTO credit_snapshots (service_id, balance, unit) VALUES (%s,%s,%s)",
                            (sid, snap.balance, snap.unit),
                        )
                    stats["credit_snapshots"] += 1
        except Exception as exc:  # noqa: BLE001 - said, never a registry-sync refusal
            stats["credit_phase_failed"] = 1
            print(
                f"WARNING: registry synced; the credit fetch aborted after the commit ({exc.__class__.__name__}: {' '.join(str(exc).split())}) — balances age until the next lap",
                file=sys.stderr,
            )
        finally:
            if conn2 is not None:
                conn2.close()
    if stats["provenance_unknown"]:
        print(
            f"WARNING: catalog provenance UNKNOWN — {stats['unattributed']} credential(s) stored unattributed, no credit fetch; the dashboard counts 0 keys until the catalog is readable (BM2)",
            file=sys.stderr,
        )
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--fetch-credits",
        action="store_true",
        help="also call each provider's credit fetcher and store a credit_snapshots row "
        "(network; the daily path passes it, a quick manual sync omits it)",
    )
    args = ap.parse_args()
    if not ALL_ENVS.exists():
        print(f"{ALL_ENVS} missing — run scripts/gather_envs.py --apply first", file=sys.stderr)
        return 1
    try:
        stats = sync_registry(fetch_credits=args.fetch_credits)
    except Exception as exc:  # noqa: BLE001 - a dead DB (psycopg OperationalError) is the likeliest failure and was still a traceback (FB1)
        # ONE line that names the CLASS: libpq's connection-refused text is two lines with a tab,
        # and a defect in our own code wore a dead-DB costume — a builtin exception that is not a
        # refusal also prints its traceback, since that one IS a bug to fix (FC3)
        print(
            f"ERROR: registry sync refused ({exc.__class__.__name__}): {' '.join(str(exc).split())} — nothing written",
            file=sys.stderr,
        )
        if type(exc).__module__ == "builtins" and not isinstance(
            exc, (ValueError, RuntimeError, OSError)
        ):
            traceback.print_exc()
        return 1
    print(
        f"synced {stats['services']} services, {stats['api_keys']} api_keys, "
        f"{stats['credit_snapshots']} credit snapshots into the registry "
        f"(pruned {stats['pruned']} services, {stats['keys_pruned']} stale keys)"
    )
    if stats["provenance_unknown"]:
        # under unknown provenance NO key is attributable, nothing is fetched, so the credit phase
        # cannot fail: the FF1 "exit 2 masks 3" line was unreachable by construction (R67-7, FG1)
        return 2  # a degraded registry must not read LIVE: the chain's _step alerts and skips the dashboard (BM2)
    if stats.get("credit_phase_failed"):
        return 3  # registry WRITTEN, credit phase failed: a WARNING alone was never alerted — the chain pages on 3 and still runs the dashboard step (FD7; the step runs, whether it renders is its own outcome — F67-10)
    return 0


if __name__ == "__main__":
    sys.exit(main())
