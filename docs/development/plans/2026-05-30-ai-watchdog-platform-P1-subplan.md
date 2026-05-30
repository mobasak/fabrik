# P1 Sub-plan — Foundations (app-audit-log + cost-budget + 2 rule packs + postgres registrar wire-in)

**Date:** 2026-05-30
**Phase:** P1 of the AI Watchdog Platform plan (15–18-day build)
**Parent plan:** [2026-05-30-ai-watchdog-platform.md](2026-05-30-ai-watchdog-platform.md)
**Prompt that produced this:** [2026-05-30-ai-watchdog-platform-prompts.md § P1.A](2026-05-30-ai-watchdog-platform-prompts.md)
**Status:** Approved — owner resolved all three open items (2026-05-30). Ready for P1.B code prompts.
**Effort:** 3–4 days (per parent plan)

## Changes from initial draft (2026-05-30 same-day owner directives)

- **Directive 1:** SSH live VPS to confirm container name + DB inventory. **Done.** Container is plain `postgres-main`. `fabrik_analytics` DB does not exist yet. PostgreSQL 16.11 with only `plpgsql` extension. Evidence inlined in § V5.
- **Directive 2:** Exact insertion line in `infrastructure.py` deferred to P1.B coding (when we open the file with the code prompt active). The general call site is unambiguous; pinning the line costs nothing during coding and avoids speculative line numbers in the sub-plan.
- **Directive 3:** Watchdog uses the **same role as the project's own DB user** (no separate `watchdog_writer`). Mechanism in § 5.5: postgres registrar `GRANT INSERT, SELECT ON cost_ledger TO "<project_id>_rw"` after `create_database()`. Two DSNs share the same role + password — no second secret to rotate.

---

## Verification evidence (no assumptions)

### V1 — Does fabrik run schema migrations on `postgres-main` today?

**Mechanism exists, but `CREATE TABLE` on `postgres-main` is NOT in the current code path.**

- `src/fabrik/drivers/postgres.py:98-124` defines `_run_sql(sql, container, dry_run)` — a generic SQL-via-stdin path: base64-encodes SQL, decodes on VPS, pipes to `sudo docker exec -i postgres-main psql -U postgres -tA`. This is the only mechanism that touches `postgres-main`.
- Today `_run_sql` is called only for: `CREATE DATABASE`, `DROP DATABASE`, `CREATE ROLE`/`GRANT` (see `postgres.py:188`, `postgres.py:216-223`, `postgres.py:317`).
- Grep for any other `CREATE TABLE` against `postgres-main` returns: `src/fabrik/ai/tracker.py:22` — but that targets **SQLite** (`sqlite3.connect(self.database_path)`), not `postgres-main`. So there's a fabrik-internal precedent for an LLM cost tracker, but it's a local-CLI SQLite ledger — not at the same layer as our cross-project shared ledger.
- **Side finding (RESOLVED 2026-05-30 via live VPS check):** `POSTGRES_CONTAINER = "postgres-main-l0k4gk0kggc8okcwk0s4c8s8"` at `postgres.py:53` is the **stale Coolify UUID**. Live VPS verification (`ssh vps "sudo docker ps --format '{{.Names}}' | grep postgres"`) returns `postgres-main` (and `postgres-exporter`). The constant MUST be updated to plain `"postgres-main"` in a small prep commit BEFORE wiring our new migration. This is a pre-existing latent bug — the only reason current `fabrik apply` paths haven't blown up is that nothing has called `create_database` since the Coolify→SSH+Compose migration (verifiable via `git log -p src/fabrik/drivers/postgres.py` history).

**Implication for P1:** the mechanism (`_run_sql`) is right there. Wiring `cost_ledger` migration is a matter of adding a function that calls `_run_sql` with our `CREATE TABLE` + `CREATE INDEX` statements, invoked from the postgres registrar's provision step.

### V2 — Does fabrik-lib have a precedent for vendoring a module that uses the SHARED `postgres-main`?

**No precedent — this is a new pattern.**

- All 6 fabrik-lib modules with `schema.sql` (`abuse-prevention`, `adaptive-dispatch`, `api-auth`, `credits`, `gdpr-data-rights`, `webhooks`) target the **host project's own database**. They take a DB-API `conn` parameter (psycopg2 or psycopg3), let the host project apply `schema.sql` to its own DB via `psql "$DATABASE_URL"`, and never reference `postgres-main` by name.
- Grep `grep -rln "postgres-main\|POSTGRES_CONTAINER\|docker exec.*postgres" /opt/fabrik-lib/` returns only one match — a docs-site privacy text mentioning `postgres-main` in a paragraph, not code.
- **Verdict for `cost-budget/`:** this module is the **first** fabrik-lib module to depend on a shared `postgres-main` table for cross-project queryability. The architectural consequence: the shared `cost_ledger` table cannot be created by each vendoring project (would race / duplicate); it must be created **once** by the postgres registrar at `fabrik apply` time, then projects' vendored `cost-budget/` Python helpers just `INSERT`/`SELECT` against it.

### V3 — What DB driver convention does `abuse-prevention` assume?

**Stdlib only at module level; DB driver is the host project's dep.** (`/opt/fabrik-lib/abuse-prevention/requirements.txt:1-7`)

- Header: "abuse-prevention runtime deps: NONE (Python standard library only)."
- Note: "The DB-touching functions expect a DB-API connection passed in by the host project, so the database driver is the project's dependency, not this module's."
- Typical host project deps it mentions: `psycopg2-binary>=2.9` OR `psycopg[binary]>=3.1`.
- Behavior: all DB-touching functions **fail open** on DB errors (return `None` to allow, never block).

**Implication for P1:** both `app-audit-log/` and `cost-budget/` follow the same convention — no DB driver in their `requirements.txt`; accept a `conn: DBAPIConnection` parameter; fail-open on DB errors where the failure is non-critical, fail-loud where the failure compromises the security/billing contract.

### V4 — pg_cron availability on `postgres-main`?

**Cannot verify from this environment, but no fabrik code references pg_cron.** Grep returns zero matches.

- `gdpr-data-rights/data_retention.sql` USES pg_cron but explicitly documents: "If pg_cron is unavailable, run the UPDATE/DELETE bodies from an app-side scheduler."
- **Verdict:** pg_cron is the host-project's optional convenience; we cannot assume it's installed in `postgres-main`. Both `app-audit-log/data_retention.sql` and any cost-budget retention path **default to app-level scheduling**, with pg_cron offered as a documented alternative.

### V5 — Live VPS state verification (DONE 2026-05-30)

`ssh vps` output captured:

```bash
$ ssh vps "sudo docker ps --format '{{.Names}}' | grep -i postgres"
postgres-main
postgres-exporter

$ ssh vps "sudo docker exec postgres-main psql -U postgres -c '\l'"
(returns 5 DBs: glitchtip, postgres, site_provisioner, template0, template1 — NO fabrik_analytics yet)

$ ssh vps "sudo docker exec postgres-main psql -U postgres -c 'SELECT version();'"
PostgreSQL 16.11 on x86_64-pc-linux-musl (Alpine compiled)

$ ssh vps "sudo docker exec postgres-main psql -U postgres -c 'SELECT extname FROM pg_extension;'"
plpgsql
```

**Confirmed facts:**

- Container name is plain `postgres-main`. Update `postgres.py:53` constant in a tiny prep commit before P1.B code starts.
- `fabrik_analytics` DB does not exist yet → our `ensure_shared_analytics_db()` will be its first creator.
- PostgreSQL **16.11** — `gen_random_uuid()` is built-in (PG13+), so `UUID PRIMARY KEY DEFAULT gen_random_uuid()` works without `pgcrypto`. (Note: we generate uuid7 in Python — `uuid_utils.compat.uuid7` per Fabrik convention — and INSERT the value explicitly; we do NOT rely on `DEFAULT gen_random_uuid()` which would give uuid4.)
- Only `plpgsql` extension installed. **No pg_cron, no pgcrypto, no uuid-ossp.** Confirms our app-level retention design (V4) and Python-side uuid7 generation.
- **Side note (out of scope for P1):** the Postgres image is Alpine-compiled, which technically conflicts with the `core/30-ops.md` "no Alpine" rule for our own services. `postgres-main` is shared infra (third-party image), not a Fabrik-built service, so the rule doesn't apply here — but worth flagging in a Side findings sweep someday.

---

## 1. `app-audit-log/` module — file-level spec

Location: `/opt/fabrik-lib/app-audit-log/`

### 1.1 `schema.sql`

```sql
-- app-audit-log :: schema for the host project's audit log.
-- PostgreSQL 16+. Idempotent.
-- Lives in the HOST PROJECT'S own database (not postgres-main).
-- The host project applies this to its own DB during deploy.

-- ---------------------------------------------------------------------------
-- 1) audit_log — append-only, hash-chained record of sensitive operations.
--    Hash chain (A2 decision): app-level Python helper computes
--      current_hash = sha256( prev_hash || canonical_json(payload) )
--    where canonical_json serializes (id, ts, actor, action, target,
--    details, prev_hash) in stable key order. See audit_log.py.
--    Both prev_hash and current_hash live on every row from day one so a
--    future upgrade to A1 (Postgres trigger) is a write-path-only change.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id           UUID         PRIMARY KEY,                -- uuid7 (sortable)
    ts           TIMESTAMPTZ  NOT NULL DEFAULT now(),
    actor        TEXT         NOT NULL,                   -- 'user:<id>' | 'system' | 'watchdog'
    action       TEXT         NOT NULL,                   -- canonical verb, see rule pack
    target_type  TEXT,                                    -- 'user' | 'subscription' | 'container' | ...
    target_id    TEXT,                                    -- the affected entity id (text for polymorphism)
    details      JSONB        NOT NULL DEFAULT '{}'::jsonb,
    prev_hash    TEXT,                                    -- NULL only on genesis row of a chain
    current_hash TEXT         NOT NULL,                   -- sha256 hex, 64 chars
    CHECK (length(current_hash) = 64),
    CHECK (prev_hash IS NULL OR length(prev_hash) = 64)
);

-- Time-ordered queries (the dominant access pattern for compliance review).
CREATE INDEX IF NOT EXISTS idx_audit_log_ts ON audit_log (ts DESC);

-- Per-actor history (e.g., "all admin actions by user X in last 30 days").
CREATE INDEX IF NOT EXISTS idx_audit_log_actor_ts ON audit_log (actor, ts DESC);

-- Per-target history (e.g., "all events on subscription Y").
CREATE INDEX IF NOT EXISTS idx_audit_log_target ON audit_log (target_type, target_id, ts DESC)
    WHERE target_type IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 2) audit_log_chain_check view — convenience view for read-time verification.
--    Returns rows whose computed hash mismatches the stored current_hash.
--    Empty result set = chain intact. Non-empty = tampering detected.
--    Implementation: a lateral subquery recomputes sha256 against prev row.
--    NOTE: the heavy lifting (canonical JSON) is done in Python, not SQL.
--    This view is therefore an OPTIONAL fast-path: it can detect missing
--    rows (gaps in chain) and broken prev_hash references purely in SQL;
--    full hash recomputation happens in audit_log.py's verify_chain().
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW audit_log_chain_check AS
SELECT a.id,
       a.ts,
       a.prev_hash AS stored_prev_hash,
       b.current_hash AS expected_prev_hash,
       (a.prev_hash IS DISTINCT FROM b.current_hash) AS prev_hash_mismatch
  FROM audit_log a
  LEFT JOIN LATERAL (
      SELECT current_hash
        FROM audit_log
       WHERE ts <= a.ts AND id <> a.id
       ORDER BY ts DESC, id DESC
       LIMIT 1
  ) b ON true;
-- SELECT * FROM audit_log_chain_check WHERE prev_hash_mismatch;  -- should be empty
```

**Hash algorithm (locked):** SHA-256 over the UTF-8 bytes of the canonical JSON serialization of `{id, ts (ISO 8601), actor, action, target_type, target_id, details, prev_hash}` with sorted keys + no whitespace + sorted keys recursively in `details`. Implemented in `audit_log.py`; the view above only catches `prev_hash`-pointer breaks, not content tampering. Full content-tamper detection requires running `verify_chain()` in Python.

**Retention partitioning scheme:** **NOT in v1.** Justification: PostgreSQL declarative partitioning on `audit_log` would require dropping + recreating the parent table on schema migration (or careful `ATTACH PARTITION` work), which is heavier than the v1 retention target needs. v1 ships with a single monolithic table; the rule pack documents the retention path as "app-level cron deletes rows older than 12 months, or owner archives + truncates quarterly." Partitioning is documented as a v2 upgrade path with the partition key (`PARTITION BY RANGE (ts)` monthly) named in `core/app-audit-log.md` so the migration is non-surprising.

### 1.2 `audit_log.py` — signatures only (no implementation)

```python
"""
app-audit-log — append-only hash-chained audit log for sensitive operations.

Framework-agnostic. Vendor it: cp -r /opt/fabrik-lib/app-audit-log
/opt/<project>/libs/audit_log/

The DB-touching functions accept a DB-API connection passed in by the host
project (psycopg2 / psycopg 3). No global DB import. No web-framework import.

Threat model (A2 — Locked decisions in plan v2):
- Solo-dev VPS; only the owner has direct DB write access. The hash chain
  is tamper-EVIDENCE (read-time verification), not tamper-prevention. A
  future upgrade to A1 (Postgres trigger enforcement) is non-breaking
  because prev_hash + current_hash already live in the schema.

Failure semantics:
- record_event() FAILS LOUD on DB error. An audit log silently dropping a
  row defeats its purpose. Caller must handle the exception (typically
  retry or escalate to ops).
- verify_chain() never raises on chain breaks — it returns a structured
  report so the caller can choose to alert vs heal.
"""
from typing import Any, Iterable, Optional, TypedDict
from datetime import datetime


# ───────────────────────── data shapes ──────────────────────────

class AuditEvent(TypedDict):
    """Shape of one audit-log row, post-recording (id + hashes filled in)."""
    id: str                  # uuid7 hex string
    ts: datetime
    actor: str
    action: str
    target_type: Optional[str]
    target_id: Optional[str]
    details: dict[str, Any]
    prev_hash: Optional[str]
    current_hash: str


class ChainBreak(TypedDict):
    """One detected break in the hash chain. See verify_chain()."""
    row_id: str
    ts: datetime
    reason: str              # 'prev_hash_mismatch' | 'content_hash_mismatch' | 'missing_genesis'


# ───────────────────────── core API ──────────────────────────

def record_event(
    conn,
    *,
    actor: str,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    table: str = "audit_log",
) -> AuditEvent:
    """Record one event in the audit log; return the inserted row.

    Computes prev_hash by SELECT'ing the most recent row's current_hash,
    then computes current_hash = sha256(canonical_json(payload)). Performs
    the INSERT in a single transaction so concurrent recorders see a
    consistent chain (Postgres row locking + read-committed isolation
    on the SELECT-MAX is sufficient for solo-dev throughput; for higher
    concurrency a SELECT FOR UPDATE on a sentinel row would be needed —
    documented as a future-work note in the rule pack).

    Raises:
        psycopg.Error / psycopg2.Error on DB failure (FAIL LOUD).
        ValueError if actor/action are empty or contain control chars.
    """


def verify_chain(
    conn,
    *,
    table: str = "audit_log",
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: Optional[int] = None,
) -> list[ChainBreak]:
    """Walk the chain (optionally bounded by ts) and report breaks.

    Recomputes current_hash for each row from its content and validates
    against the stored current_hash. Validates that prev_hash equals the
    previous row's current_hash. Returns an empty list when the chain
    is intact over the requested range.

    This is read-only and side-effect-free; safe to call from a cron job
    or admin endpoint.
    """


def query_events(
    conn,
    *,
    actor: Optional[str] = None,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    table: str = "audit_log",
) -> Iterable[AuditEvent]:
    """Filtered read of audit_log; supports pagination via limit/offset.

    Read-only. Does NOT verify chain integrity inline — call verify_chain()
    separately if needed. The audit_log_chain_check view (defined in
    schema.sql) is a fast SQL-only check for prev_hash pointer breaks.
    """


# ───────────────────────── internals (private) ──────────────────────────

def _canonical_payload(
    *,
    id_: str,
    ts: datetime,
    actor: str,
    action: str,
    target_type: Optional[str],
    target_id: Optional[str],
    details: dict[str, Any],
    prev_hash: Optional[str],
) -> bytes:
    """Return the canonical JSON bytes to be hashed for current_hash.

    Rules (locked):
      - JSON, UTF-8 encoded.
      - Sorted keys, recursively (json.dumps with sort_keys=True is fine
        for nested dicts; lists preserve order).
      - No whitespace (separators=(",", ":")).
      - ts serialized as ISO 8601 with 'Z' suffix and microsecond precision.
      - prev_hash None → JSON null, not omitted.
    """


def _sha256_hex(payload: bytes) -> str:
    """Return the 64-char lowercase hex SHA-256 of payload."""
```

### 1.3 `data_retention.sql`

Per V4 above, **app-level scheduling is the default**; pg_cron is offered as a documented alternative. The file ships with:

```sql
-- app-audit-log :: retention.
--
-- Default mode: APP-LEVEL. The host project runs the bodies below from its
-- own scheduler (APScheduler, Celery beat, a cron container, fabrik
-- watchdog). pg_cron is NOT required — and is NOT installed on
-- postgres-main by default (verified 2026-05-30; no `pg_cron` references in
-- fabrik core).
--
-- Optional pg_cron mode: if you have it, uncomment the SELECT cron.schedule()
-- wrappers (commented out below) — the bodies are identical.

-- Recommended TTL: 12 months. Adjust per compliance scope (KVKK / GDPR /
-- domain-specific). Tax/billing events: set the action_prefix exemption.

-- ---------------------------------------------------------------------------
-- JOB 1: Trim rows older than 12 months EXCEPT compliance-critical actions.
--        The 'action LIKE' guard preserves billing-, consent-, and
--        erasure-related entries indefinitely (their host project decides
--        when those age out under tax/law retention rules).
-- ---------------------------------------------------------------------------
-- App-level (default): run the body below daily at 03:15 from your scheduler.
DELETE FROM audit_log
 WHERE ts < now() - interval '12 months'
   AND action NOT LIKE 'billing.%'
   AND action NOT LIKE 'consent.%'
   AND action NOT LIKE 'gdpr.%';

-- ---------------------------------------------------------------------------
-- (Optional) pg_cron wrapper. Requires pg_cron in shared_preload_libraries.
-- ---------------------------------------------------------------------------
-- SELECT cron.schedule(
--     'audit-log-trim',
--     '15 3 * * *',
--     $$
--     DELETE FROM audit_log
--      WHERE ts < now() - interval '12 months'
--        AND action NOT LIKE 'billing.%'
--        AND action NOT LIKE 'consent.%'
--        AND action NOT LIKE 'gdpr.%';
--     $$
-- );
```

### 1.4 `requirements.txt`

```
# app-audit-log runtime deps: NONE (Python standard library only).
#
# The DB-touching functions expect a DB-API connection passed in by the host
# project, so the database driver is the project's dependency, not this
# module's. Typical host project will already have one of:
#   psycopg2-binary>=2.9      # psycopg2
#   psycopg[binary]>=3.1      # psycopg 3
#
# The hash chain uses hashlib.sha256 (stdlib).
# uuid7 generation uses the project's uuid_utils (per Fabrik rule pack
# core/25-data-postgres.md UUIDv7 convention) OR a hand-rolled fallback;
# the module documents both paths in README.
```

### 1.5 `README.md` — outline

(Matching `gdpr-data-rights` style — verified file content above. Specific sections:)

1. Title + one-paragraph intro: what it is, what it's not (it's a pattern, not a plug-and-play library; per the gdpr-data-rights convention).
2. **What's included** — file table (4 rows: schema.sql, audit_log.py, data_retention.sql, requirements.txt).
3. **Vendor it** — `cp -r /opt/fabrik-lib/app-audit-log /opt/<project>/libs/audit_log` + `psql "$DATABASE_URL" -f libs/audit_log/schema.sql`.
4. **Configuration** — env-var table (empty initially; module is config-less in v1, takes parameters via function args).
5. **Usage example** — Python snippet showing `record_event()` for a billing charge + a watchdog action.
6. **Compliance checklist** (the deliverable focus, mirroring gdpr-data-rights):
   - [ ] Every sensitive op logged — full canonical action vocabulary (auth, billing, admin, data export, watchdog actions) lifted from the rule pack.
   - [ ] Hash chain verified weekly by an admin endpoint or cron — show example.
   - [ ] Retention policy documented + tested.
   - [ ] Compliance-exempt action prefixes (`billing.`, `consent.`, `gdpr.`) understood by the team.
7. **What NOT to log here** — PII beyond what's strictly needed; passwords or secrets in `details`; high-cardinality noise (page views, search queries — those go in product analytics, not audit log).
8. **Notes on chain breaks** — what a break means, how to investigate, when to alert.
9. **Testing** — apply schema; insert events; verify chain; tamper one row; re-verify; confirm break detected.
10. **Dependencies** — stdlib only; DB driver is the host project's.

---

## 2. `cost-budget/` module — file-level spec

Location: `/opt/fabrik-lib/cost-budget/`

**Architectural note** (per V2 above — this is a new pattern): unlike other fabrik-lib modules, `cost-budget/` writes to a **shared table on `postgres-main`** (the `cost_ledger` table, created once by the postgres registrar). The vendored Python module does NOT contain `CREATE TABLE` for `cost_ledger` — that schema is provisioned by `fabrik apply`. The module's `schema.sql` only contains the local SQLite WAL schema (project-side, file path: `/opt/<project>/watchdog/cost_wal.db`).

### 2.1 `schema.sql` — split into two files

**a. `schema_pg.sql`** — the shared `postgres-main` table. **NOT applied by the host project.** Provisioned by the postgres registrar at `fabrik apply` time. This file lives in the module for reference + as the canonical DDL the registrar reads.

```sql
-- cost-budget :: shared cost_ledger table.
-- Lives on postgres-main, in a dedicated 'fabrik_analytics' database.
-- Provisioned by the postgres registrar at fabrik apply — NOT by host projects.
-- This file is the canonical DDL the registrar reads.

CREATE TABLE IF NOT EXISTS cost_ledger (
    id          UUID         PRIMARY KEY,                  -- uuid7 (sortable)
    project_id  TEXT         NOT NULL,                     -- spec.id
    ts          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    provider    TEXT         NOT NULL,                     -- 'claude-code' | 'openrouter'
    model       TEXT         NOT NULL,                     -- 'claude-sonnet-4-6' | 'gemini-2.5-flash' | ...
    in_tokens   INTEGER      NOT NULL CHECK (in_tokens >= 0),
    out_tokens  INTEGER      NOT NULL CHECK (out_tokens >= 0),
    cost_usd    NUMERIC(10,6) NOT NULL CHECK (cost_usd >= 0),  -- 0.000000 for claude-code subscription
    incident_id TEXT,                                       -- nullable; links to watchdog incident
    action_id   TEXT                                        -- nullable; links to audit_log.id
);

CREATE INDEX IF NOT EXISTS idx_cost_ledger_project_ts ON cost_ledger (project_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_cost_ledger_ts ON cost_ledger (ts DESC);

-- Optional: provider-scoped query index for subscription-burn visibility.
CREATE INDEX IF NOT EXISTS idx_cost_ledger_provider_ts ON cost_ledger (provider, ts DESC);
```

**b. `schema_sqlite.sql`** — the local WAL schema. Applied by the host project via `cost_budget.py` on first use (or by the watchdog sidecar at first boot).

```sql
-- cost-budget :: write-ahead buffer for cost_ledger inserts.
-- Local SQLite at /opt/<project>/watchdog/cost_wal.db.
-- Applied on first use by cost_budget.wal_init().

CREATE TABLE IF NOT EXISTS cost_wal (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,        -- monotonic insert order
    payload     TEXT    NOT NULL,                          -- JSON-serialized cost_ledger row
    enqueued_at TEXT    NOT NULL DEFAULT (datetime('now', 'utc')),
    last_attempt_at TEXT,                                  -- nullable; updated on each replay attempt
    attempts    INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_cost_wal_seq ON cost_wal (seq);
```

### 2.2 `cost_budget.py` — signatures only

```python
"""
cost-budget — per-project LLM (and any paid-API) cost caps with a shared
postgres ledger + local SQLite write-ahead buffer.

Framework-agnostic. Vendor it. The shared cost_ledger table on postgres-main
is provisioned by the fabrik postgres registrar — projects do NOT create it.

Failure semantics (B2 fail-open WAL — Locked decisions in plan v2):
- record_cost() writes to local SQLite WAL FIRST (cheap, near-zero failure).
  Then attempts a synchronous postgres-main insert.
  On postgres-main unreachable → returns success (FAIL OPEN); the WAL row
  stays queued; replay drains it within ~30s of postgres-main returning.
- check_caps() reads the LOCAL WAL first (counts pending rows) plus the
  shared postgres-main aggregate (queries cost_ledger). Total = cap check.
  If postgres-main unreachable → uses last-known cached aggregate plus
  WAL; documents the staleness window.
- drop_to_rule_only_mode() is a host-project hook: returns True/False from
  check_caps(); the host (watchdog sidecar) reacts.
"""
from typing import Optional, Any
from dataclasses import dataclass
from datetime import datetime


# ───────────────────────── data shapes ──────────────────────────

@dataclass
class CostEvent:
    """One LLM call's cost telemetry, ready for the ledger."""
    project_id: str
    provider: str                # 'claude-code' | 'openrouter'
    model: str
    in_tokens: int
    out_tokens: int
    cost_usd: float              # 0.0 for claude-code subscription calls
    incident_id: Optional[str] = None
    action_id: Optional[str] = None


@dataclass
class BudgetState:
    """Result of check_caps() — what the watchdog needs to decide rule-only mode."""
    project_id: str
    daily_usd_spent: float
    daily_usd_cap: float
    daily_invocations_spent: int
    daily_invocations_cap: int
    over_cap: bool               # True if any cap exceeded
    stale: bool                  # True if postgres-main was unreachable when this was computed


# ───────────────────────── core API ──────────────────────────

def record_cost(
    *,
    pg_conn,                     # connection to postgres-main / fabrik_analytics DB; may be None for WAL-only
    wal_path: str,               # path to local cost_wal.db
    event: CostEvent,
) -> None:
    """Record one cost event. Writes to WAL synchronously, then attempts
    postgres-main insert. Never raises on postgres failure — that's
    fail-open semantics. Raises on WAL failure (which is local SQLite —
    a real bug, not a network condition).
    """


def replay_wal(
    *,
    pg_conn,                     # connection to postgres-main / fabrik_analytics DB
    wal_path: str,
    batch_size: int = 100,
    max_age_seconds: int = 60 * 60 * 24 * 7,  # drop rows older than 7d to avoid unbounded growth
) -> dict[str, int]:
    """Drain WAL rows into postgres-main. Idempotent (UUID primary key on
    cost_ledger means re-replay of an already-inserted row is a no-op).
    Called from the watchdog sidecar's check loop OR a host-project cron.

    Returns: {'replayed': n, 'failed': m, 'dropped_stale': k}.
    """


def check_caps(
    *,
    pg_conn,
    wal_path: str,
    project_id: str,
    daily_usd_cap: float,
    daily_invocations_cap: int,
    window_start: Optional[datetime] = None,  # default: today UTC 00:00
) -> BudgetState:
    """Aggregate today's spend from postgres-main + WAL; return state.
    If postgres-main unreachable, use WAL alone and set state.stale=True.
    """


def drop_to_rule_only_mode(state: BudgetState) -> bool:
    """Pure function: True if state.over_cap. Exists as a named hook so the
    rule pack can cite a single function name, and so future caller code
    reads `if cb.drop_to_rule_only_mode(state):` instead of `if state.over_cap:`.
    """


# ───────────────────────── Prometheus metrics (optional) ──────────────────────────

def prometheus_metrics(state: BudgetState) -> str:
    """Render BudgetState as Prometheus text-format metrics:
        llm_cost_dollars_total{project="..."} <value>
        llm_invocations_total{project="...",provider="..."} <value>
    Host project's /metrics handler can call this directly.
    """


# ───────────────────────── internals (private) ──────────────────────────

def _wal_init(wal_path: str) -> None: ...
def _wal_enqueue(wal_path: str, event: CostEvent) -> int: ...
def _wal_drain_batch(wal_path: str, batch_size: int): ...
def _pg_insert(pg_conn, event: CostEvent) -> None: ...
def _pg_aggregate_today(pg_conn, project_id: str, window_start: datetime) -> tuple[float, int]: ...
```

### 2.3 Cap-enforcement algorithm (locked)

1. **On every LLM call:** sidecar (or any consumer) calls `check_caps(pg_conn, wal_path, project_id, ...)` BEFORE issuing the LLM request.
2. `check_caps()`:
   - Query postgres-main `cost_ledger` for `(SUM(cost_usd), COUNT(*))` where `project_id=$1 AND ts >= window_start`.
   - Read local WAL: count un-replayed pending rows for this project + sum their `cost_usd`.
   - `BudgetState.over_cap = (pg_sum + wal_sum > daily_usd_cap) OR (pg_count + wal_count > daily_invocations_cap)`.
3. **If over cap:** caller drops to rule-only mode (no LLM call, alerts continue via rules).
4. **If under cap:** caller issues LLM call, then synchronously calls `record_cost()` with the resulting `CostEvent`.
5. **Replay loop:** sidecar's main loop calls `replay_wal()` every 30 seconds (configurable). Replay is idempotent (UUID PK).
6. **Failure modes:**
   - postgres-main down during check_caps → use WAL aggregate alone + `stale=True`; caller decides whether to risk over-spend or be conservative (rule pack recommends: trust the cap during outage, since WAL has every uncommitted call).
   - postgres-main down during record_cost → WAL row stays queued; replay drains later.
   - WAL corrupted → fail loud; sidecar refuses to start (data integrity > availability for billing data).

### 2.4 WAL design specifics

- **Storage:** SQLite file at `/opt/<project>/watchdog/cost_wal.db`. Owned by sidecar UID (non-root).
- **Replay batch size:** 100 rows per `replay_wal()` call.
- **Drop-stale threshold:** rows older than 7 days are dropped from the WAL with a logged warning (postgres-main was down for a week → data loss on this row is acceptable vs. unbounded WAL growth that could exhaust disk).
- **Failure handling:** each WAL row tracks `attempts`. After 5 failed replays, the row is flagged via a Prometheus metric `cost_wal_stuck_rows` for ops investigation.
- **Idempotency:** UUID PK on `cost_ledger` → ON CONFLICT (id) DO NOTHING in the INSERT, so re-replay is safe.

### 2.5 `requirements.txt`

```
# cost-budget runtime deps: NONE (Python standard library only).
#
# Same convention as abuse-prevention / app-audit-log: the DB driver is
# the host project's dependency. SQLite is stdlib.
#
# Typical host project will already have:
#   psycopg2-binary>=2.9      # psycopg2
#   psycopg[binary]>=3.1      # psycopg 3
```

### 2.6 `README.md` — outline

(Same convention as gdpr-data-rights / abuse-prevention. Specific sections:)

1. Title + one-paragraph intro: per-project cost caps with shared cross-project ledger; designed for the watchdog sidecar but vendorable into any service that calls paid APIs.
2. **Architecture note** — explicit call-out that `cost_ledger` is on `postgres-main` (shared, provisioned by fabrik registrar), `cost_wal.db` is local. Different from typical fabrik-lib modules; readers should not be surprised.
3. **What's included** — file table (5 rows: schema_pg.sql, schema_sqlite.sql, cost_budget.py, requirements.txt, and a note that schema_pg.sql is reference-only for projects).
4. **Vendor it** — `cp -r /opt/fabrik-lib/cost-budget /opt/<project>/libs/cost_budget`. Note that the postgres-main side is provisioned automatically by `fabrik apply` — projects don't need to apply `schema_pg.sql` themselves.
5. **Configuration** — env-var table:
   - `COST_BUDGET_PG_DSN` — postgres-main / fabrik_analytics DSN (set by fabrik registrar via env injection at apply time)
   - `COST_BUDGET_WAL_PATH` — defaults to `/opt/<project>/watchdog/cost_wal.db`
   - `COST_BUDGET_REPLAY_INTERVAL_SECONDS` — default 30
6. **Usage example** — Python snippet showing `check_caps()` before an LLM call + `record_cost()` after, with a watchdog-flavored use case.
7. **Operations checklist:**
   - [ ] postgres-main `cost_ledger` table created by `fabrik apply` (verify with `SELECT * FROM cost_ledger LIMIT 1`).
   - [ ] WAL replay running (Prometheus `cost_wal_stuck_rows` metric near zero).
   - [ ] Per-project caps set in spec `watchdog.daily_budget_usd` + `daily_invocations_cap`.
   - [ ] Portfolio-spend dashboard wired (sample SQL in rule pack).
8. **Portfolio queries** — exact SQL snippets from plan v2 § Locked decisions B2 (monthly spend per project; Claude Code call count).
9. **Testing** — unit tests for hash/cap math; integration test that exercises the WAL drain under postgres-main outage simulation (docker stop postgres-main; record_cost N times; assert WAL grows; docker start postgres-main; assert WAL drains within 30s).
10. **Dependencies** — stdlib only; DB driver is the host project's.

---

## 3. `core/app-audit-log.md` rule pack — section outline

Frontmatter matches existing core packs (verify against `core/58-resilience.md` shape during code phase).

1. **When to use the audit log** — every backend service touching billable / auth / admin / privacy-sensitive operations; the rule pack lists explicit triggers.
2. **What events to log** (enumerated canonical action vocabulary):
   - `auth.login_success`, `auth.login_failure`, `auth.logout`, `auth.password_changed`, `auth.email_changed`, `auth.mfa_enabled`, `auth.mfa_disabled`, `auth.session_revoked`
   - `billing.subscription_created`, `billing.subscription_updated`, `billing.subscription_cancelled`, `billing.charge_succeeded`, `billing.charge_failed`, `billing.refund_issued`, `billing.dispute_opened`
   - `admin.user_impersonated`, `admin.user_quota_overridden`, `admin.feature_flag_toggled`, `admin.data_exported`, `admin.user_deleted`
   - `gdpr.export_requested`, `gdpr.export_delivered`, `gdpr.deletion_requested`, `gdpr.deletion_purged`, `consent.granted`, `consent.withdrawn`
   - `watchdog.tier_a_action`, `watchdog.tier_b_action`, `watchdog.tier_c_escalation`, `watchdog.llm_call`, `watchdog.budget_kill_switch`
   - (Each action documented with: what triggers it, what goes in `details`, what `target_type`/`target_id` should be.)
3. **Retention policy** — 12-month default; exemptions for `billing.*` / `consent.*` / `gdpr.*` (kept indefinitely per tax/law).
4. **Hash-chain verification on read** — when to run `verify_chain()` (weekly compliance review + on-demand from admin panel); what to do when a break is detected (alert, freeze writes, investigate).
5. **Anti-patterns** (what NOT to log here):
   - PII beyond what's required for the event (don't log raw passwords, full PANs, secret tokens).
   - High-cardinality product events (page views, searches) — those belong in analytics, not audit.
   - Application errors — those belong in GlitchTip, not audit.
   - Test data in production audit log (use a `test-*` action prefix that retention will strip after 7 days, or write to a separate test DB).
6. **Upgrade path to A1** — schema columns already in place; switching enforcement requires only adding the Postgres trigger + removing the Python-side hash computation; non-breaking.
7. **Worked example** — one short paragraph showing the recording of a billing charge from a Paddle webhook handler.

### Acceptance for this pack:
- All ~25 canonical actions enumerated with `details` shape specified.
- Anti-patterns names at least 4 concrete don't-do-this items.
- Cites `app-audit-log/audit_log.py` function names explicitly.
- Frontmatter matches other core packs.
- Lints clean (MD060 / MD032 — same patterns we've fought before).

---

## 4. `core/cost-budget.md` rule pack — section outline

1. **When to use cost-budget** — any service that calls a paid LLM API (OpenRouter, Anthropic direct), any service that calls a metered upstream (cloud OCR, paid translation, etc.). Default ON for the watchdog sidecar.
2. **Budget setting per project:**
   - Spec field `watchdog.daily_budget_usd` (OpenRouter cap).
   - Spec field `watchdog.daily_invocations_cap` (Claude Code subscription cap).
   - Per-task soft cap (config in the host project's code; recommended formulas based on incident severity).
3. **Tiered model selection ladder:**
   - **Tier 1 cheap:** Claude Code → Haiku, OpenRouter → Gemini Flash. Returns structured output with self-rated confidence (0.0–1.0).
   - **Tier 2 expensive:** Claude Code → Sonnet, OpenRouter → Sonnet. Used only when Tier 1 confidence < 0.7 OR rule-based heuristic triggers (stack trace present, multi-system failure, etc.).
   - **Always rule-based fallback:** if both providers fail or budget kill-switch is active, fall back to deterministic rules per `core/self-healing.md` escalation ladder.
4. **Kill-switch semantics:**
   - `check_caps()` returns `over_cap=True` → caller MUST NOT issue an LLM call.
   - The host (watchdog) drops to rule-only mode: still observes, still alerts on hard thresholds, no LLM reasoning until the daily window resets.
   - The kill-switch is per-project (one project burning subscription doesn't kill others).
5. **Cost-per-success metric** — recommended: `cost_per_resolved_incident_usd = SUM(cost_usd) / COUNT(DISTINCT incident_id WHERE resolution='auto')` over a rolling 7-day window. Surface in Grafana; alerts when it crosses a per-project threshold.
6. **Portfolio analytics** — direct SQL queries against `cost_ledger` (sample queries from plan v2).
7. **Anti-patterns:**
   - Calling the expensive tier unconditionally for every check (defeats budget purpose — Tier 1 must come first).
   - Ignoring `state.stale=True` (means postgres-main is down; treat the cap as authoritative or hold; don't blindly spend).
   - Mixing test invocations with production rows (use `project_id` prefix `test-` and filter portfolio queries).
8. **Worked example** — one short paragraph showing the watchdog deciding between Tier 1 and Tier 2 for an OOM incident.

### Acceptance for this pack:
- Tiered ladder names all four tiers (Claude Code cheap, Claude Code expensive, OpenRouter cheap, OpenRouter expensive, rule-only).
- Kill-switch semantics unambiguous (per-project, daily window).
- Cost-per-success formula stated.
- Frontmatter matches other core packs.
- Lints clean.

---

## 5. Postgres driver migration wire-in

### 5.1 Where the migration goes

**File:** `/opt/fabrik/src/fabrik/drivers/postgres.py`.

**New function (proposed):**

```python
def ensure_shared_analytics_db(
    *,
    container: str = POSTGRES_CONTAINER,
    dry_run: bool = False,
) -> dict:
    """Idempotently provision the shared 'fabrik_analytics' database and
    apply the canonical DDL from cost_ledger and any future shared tables.

    Called once per `fabrik apply` (the postgres registrar invokes it before
    the per-spec create_database()). Idempotent — re-running is safe.

    Steps:
      1. CREATE DATABASE fabrik_analytics IF NOT EXISTS.
      2. Apply DDL from /opt/fabrik-lib/cost-budget/schema_pg.sql verbatim
         (read at runtime — not vendored into fabrik source — so the
         module's schema_pg.sql remains the single source of truth).

    Returns: {'status': 'created' | 'exists' | 'dry_run', 'database': 'fabrik_analytics'}.
    """
```

### 5.2 Idempotency mechanism

- `CREATE DATABASE` IF-EXISTS via the same `pg_database` check pattern as `create_database()` (postgres.py:171-178). Cannot use `CREATE DATABASE IF NOT EXISTS` (Postgres doesn't support that clause directly).
- `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS` for the DDL inside. Same pattern as every other `schema.sql` in fabrik-lib.

### 5.3 Where in `infrastructure.py` it gets called

In `infrastructure.py` (the dispatcher), the **postgres registrar's provision step** calls `ensure_shared_analytics_db()` once BEFORE provisioning the per-spec database. Function-level location: inside the postgres branch of `InfrastructureProvisioner.provision()` (need to read the full file to pin the exact insertion line — flagged as Day-1 P1 work, but the call site is unambiguous).

### 5.4 `_REGISTRAR_ORDER` changes

**None required.** `postgres` is already first in `_REGISTRAR_ORDER` (`infrastructure.py:84-94`); the watchdog registrar (P2) inserts AFTER `prometheus` and naturally runs after `postgres`. The shared `cost_ledger` will already exist by the time any project's watchdog sidecar starts.

### 5.5 Connection string for the sidecar

**Role decision (LOCKED 2026-05-30 by owner):** the watchdog connects to `fabrik_analytics` using the **same role as the project's own DB user** (the role provisioned by `create_database()` for the project, e.g., `<project_id>_rw`). No separate `watchdog_writer` role.

Mechanism (three steps):

- **Step 1.** `create_database()` already provisions a per-project role (e.g., `myproject_rw`) with a CSPRNG password.
- **Step 2.** After that role exists, `ensure_shared_analytics_db()` performs an additional GRANT on the shared `cost_ledger` table:

  ```sql
  GRANT INSERT, SELECT ON cost_ledger TO "<project_id>_rw";
  ```

- **Step 3.** Watchdog sidecar env gets two DSNs:
  - `DATABASE_URL=postgresql://<project_id>_rw:<password>@postgres-main:5432/<project_id>` (the project's own DB — unchanged from today)
  - `FABRIK_ANALYTICS_URL=postgresql://<project_id>_rw:<password>@postgres-main:5432/fabrik_analytics` (same role, different DB)

Both DSNs use the **same role + same password** the postgres registrar already manages — no second secret to rotate, no new role to drift. The GRANT is idempotent (`GRANT ... TO` is a no-op if already granted) and runs on every `fabrik apply` after the per-project role is created.

**Privilege scope:** `INSERT, SELECT` only — no `UPDATE`, no `DELETE`, no schema mutation. Cap enforcement and replay never need anything beyond INSERT+SELECT. The append-only contract of `cost_ledger` is enforced by the GRANT itself.

**Implication for the `ensure_shared_analytics_db()` signature:** it must be called AFTER `create_database()` for each spec (so the role exists to GRANT to). Function-call order inside `InfrastructureProvisioner.provision()` is therefore: `create_database(spec) → ensure_shared_analytics_db(grant_to=role_name)`. The DB-creation step itself is still idempotent and only runs once per `fabrik apply` cluster-wide; only the GRANT runs per-spec.

---

## 6. Acceptance criteria for P1 (verified against parent plan)

Lifted from plan v2 § Phased implementation P1 row + made testable:

1. **Both modules vendor cleanly into a test project.**
   - Test: `cp -r /opt/fabrik-lib/app-audit-log /tmp/testproj/libs/audit_log && python -c "from libs.audit_log import audit_log"` runs without ImportError.
   - Same for `cost-budget`.

2. **`cost_ledger` table created by postgres registrar on first apply.**
   - Test: scaffold a fresh test project; run `fabrik apply --dry-run`; verify the dispatcher reports `ensure_shared_analytics_db()` will run.
   - Live test: run `fabrik apply` on `/opt/test-saas-for-epic-wf`; then `ssh root@vps "sudo docker exec postgres-main psql -U postgres -d fabrik_analytics -c '\d cost_ledger'"` should show the table + 3 indexes.

3. **WAL replay verified on Postgres outage simulation.**
   - Test script: starts a test project's watchdog sidecar; `docker stop postgres-main`; sidecar issues 10 `record_cost()` calls (all go to WAL); `docker start postgres-main`; within 30 seconds the WAL drains; `SELECT COUNT(*) FROM cost_ledger WHERE project_id='<test-id>'` returns 10; `cost_wal.db` is empty.

4. **READMEs match fabrik-lib/README.md convention.**
   - Both READMEs have: one-paragraph intro, file table, vendor command, configuration table, usage example, dependencies section.
   - Both modules registered in the main `fabrik-lib/README.md` Modules table + "Which Modules Do I Need?" matrix.

5. **Rule packs lint-pass.**
   - `markdownlint-cli2` on both packs passes with the same config the rest of `.windsurf/rules/` uses (MD060 / MD032 in particular — same patterns we've fixed before in plan v2 + 00).
   - Frontmatter matches sibling core packs.

6. **Hash chain unit test passes.**
   - Unit test: record 100 events; call `verify_chain()`; expect empty list. Tamper one row's `details`; re-verify; expect one `ChainBreak` entry with `reason='content_hash_mismatch'`.

7. **Caps enforcement unit test passes.**
   - Unit test: insert events totaling $5; set `daily_usd_cap=10`; `check_caps()` returns `over_cap=False`. Insert one more $6 event; `check_caps()` returns `over_cap=True`.

---

## 7. Order of artifacts to code (smallest leaf first)

(Slight refinement of the prompt's order — `data_retention.sql` is documentation-heavy and small, but it depends on the `audit_log` table existing in the reader's mind, so it stays where the prompt placed it. The split of cost-budget schema into `schema_pg.sql` + `schema_sqlite.sql` adds one filename but no extra coding effort.)

1. `app-audit-log/schema.sql` (smallest leaf — pure DDL, no Python)
2. `app-audit-log/data_retention.sql` (small, just SQL DELETE + commented pg_cron alternative)
3. `app-audit-log/audit_log.py` (~250–350 lines — record_event + verify_chain + query_events + canonicalization)
4. `app-audit-log/requirements.txt` (3 lines)
5. `app-audit-log/README.md` (~120 lines per gdpr-data-rights calibration)
6. `cost-budget/schema_pg.sql` (smaller than schema_sqlite — single CREATE TABLE + 3 indexes)
7. `cost-budget/schema_sqlite.sql` (single CREATE TABLE + 1 index)
8. `cost-budget/cost_budget.py` (~250–350 lines — record_cost + replay_wal + check_caps + prometheus_metrics + WAL internals)
9. `cost-budget/requirements.txt` (4 lines)
10. `cost-budget/README.md` (~140 lines — slightly longer than app-audit-log due to architecture-note + portfolio query snippets)
11. `core/app-audit-log.md` (~120 lines — frontmatter + 7 sections + ~25-action vocabulary table)
12. `core/cost-budget.md` (~140 lines — frontmatter + 8 sections + portfolio queries)
13. Postgres driver migration wire-in: add `ensure_shared_analytics_db()` in `src/fabrik/drivers/postgres.py` (+ a call site in `src/fabrik/orchestrator/infrastructure.py`) — ~60 lines added across both files
14. Update `/opt/fabrik-lib/README.md` modules table + "Which Modules Do I Need?" matrix (+ 2 rows in each table, plus a few-line update to the "Rule:" paragraph at line 57 to mention these for watchdog-having projects)

---

## 8. Side findings (worth flagging for separate tasks)

1. **`POSTGRES_CONTAINER` constant is stale (Coolify UUID).** `src/fabrik/drivers/postgres.py:53` hardcodes `"postgres-main-l0k4gk0kggc8okcwk0s4c8s8"`. **RESOLVED 2026-05-30** — `ssh vps` confirmed live container is plain `postgres-main`. Action item: tiny prep commit updates the constant BEFORE the P1.B `ensure_shared_analytics_db()` code lands, so the new code path doesn't inherit the same bug. The change is one-line; no other call sites need updating (all callers use the module constant).

2. **`src/fabrik/ai/tracker.py` already implements an LLM cost ledger** (SQLite, local, fabrik-CLI's own AI usage). Not blocking our work, but: at some future point it would be cleaner to consolidate (fabrik-CLI's own AI usage could write to the same `cost_ledger` table with `project_id='fabrik-cli'`). Out of scope for this P1; flagged for a future "unify cost telemetry" task.

3. **`fabrik audit-registrars` will need to learn about the watchdog registrar.** Not P1, but a P2 follow-on: `src/fabrik/audit.py` audits each registrar's drift. The watchdog registrar (P2) will need its own `audit_watchdog()` function so drift detection sees stuck sidecars / missing audit_log tables / etc.

4. **pg_cron explicitly NOT assumed.** Verified zero references in fabrik source. App-level scheduling is the default for both `app-audit-log` retention and `cost-budget` WAL replay. Rule packs document the pg_cron path as optional.

5. **`fabrik_analytics` shared database is a net-new concept.** No existing fabrik-lib module uses it. Worth a one-line mention in `AGENTS.md` § Infrastructure Services after P1 lands so future readers know it exists.

6. **The `audit_log_chain_check` view's lateral subquery is O(N²) on read.** Fine for the v1 use case (weekly compliance review on ≤ 100k rows). For projects with high audit volume (>1M rows), it would need pagination or a precomputed `prev_hash_expected` column. Flagged in the rule pack as a future optimization but not blocking.

---

## Self-review against P1.A prompt requirements

Checklist (the 8 sections the prompt mandated):

- [x] **1. app-audit-log/ module file list** — schema.sql full DDL + hash algorithm + retention scheme (single table v1, partitioning deferred to v2); audit_log.py signatures with docstrings; data_retention.sql with app-level default + pg_cron alternative; requirements.txt; README outline.
- [x] **2. cost-budget/ module file list** — schema split into schema_pg.sql (shared, registrar-provisioned) + schema_sqlite.sql (local WAL); cost_budget.py signatures; cap-enforcement algorithm spelled out; WAL design specifics; requirements.txt; README outline.
- [x] **3. core/app-audit-log.md rule pack section outline** — 7 sections including full canonical action vocabulary enumeration plan (~25 actions named).
- [x] **4. core/cost-budget.md rule pack section outline** — 8 sections including tiered ladder, kill-switch, cost-per-success metric.
- [x] **5. Postgres driver migration wire-in** — function name (`ensure_shared_analytics_db()`); file path; idempotency mechanism; insertion location in infrastructure.py; `_REGISTRAR_ORDER` confirmed unchanged.
- [x] **6. Acceptance criteria for P1** — 7 testable acceptance items lifted from plan v2 + made concrete with test recipes.
- [x] **7. Order of artifacts to code** — 14 items in dependency order, smallest leaf first. (One more than the prompt's 12 because cost-budget schema is split into 2 files — flagged in the order.)
- [x] **8. Side findings** — 6 findings including the stale Coolify UUID, ai/tracker overlap, audit-registrars follow-on, pg_cron non-assumption, fabrik_analytics doc need, audit chain view O(N²) limit.

Verification grade: **all reads done, all verifications either completed or explicitly deferred to VPS check.** No assumptions written into the sub-plan that weren't grounded in a file read.

---

## End-of-response file summary

| File | Lines | Change |
|---|---:|---|
| `docs/development/plans/2026-05-30-ai-watchdog-platform-P1-subplan.md` | ~620 | Created — the P1 sub-plan |

No code written. No other files modified. Owner reviews this sub-plan and either approves (then P1.B code prompts begin per artifact) or redirects (then we revise).
