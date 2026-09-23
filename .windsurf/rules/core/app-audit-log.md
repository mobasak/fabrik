---
activation: glob
globs: ["**/db/schema.sql", "**/alembic/**", "**/migrations/**", "**/audit_log*", "**/libs/audit_log/**", "**/audit_log.py", "**/billing/**/webhook*", "**/billing_routes.py", "**/webhooks.py", "**/webhooks.ts", "**/webhooks.js", "**/api/**/webhook*/**", "**/auth/login*", "**/auth/password*", "**/auth/mfa*", "**/auth.py", "**/auth.ts", "**/auth.js", "**/admin/**/impersonat*", "**/gdpr/**", "**/watchdog/actions*"]
applies_to: ["saas-skeleton", "python-api", "python-api-gpu", "node-api", "file-api", "file-worker", "office-extension", "chrome-extension", "mobile-app", "desktop-app", "static-site", "docusaurus"]
description: Tamper-evident audit log, MANDATORY in every project (D-368) — vendoring, canonical actor/action vocabulary, the concurrency lock, hash-chain verification, retention by legal period
trigger: glob
currency_pass: 2026-09-23
---
<!-- CONSUMER: Coding agents (all) + the planning commands (a plan that touches a sensitive op carries its audit ticket)
     GOAL: One append-only, hash-chained record of every sensitive op in the system.
     AGENT USAGE: Vendor /opt/fabrik-lib/app-audit-log/. Call al.record_event() at every sensitive op site. Don't invent new action strings — extend the vocabulary in this rule pack first. -->

# Audit Log Rules

**Activation:** Glob — `db/schema.sql`, which every scaffold type emits (a placeholder where no database exists yet), and `alembic/`/`migrations/` for repos that moved off it (a vendored or `node_modules` migrations folder matches too) — so it loads in every project whenever the schema or a sensitive site is in context — plus the audit-log code paths and sensitive operation sites (auth, billing, admin, GDPR, watchdog actions).
**Purpose:** Every sensitive operation logged once, tamper-evidently, with a canonical action vocabulary that compliance review and watchdog accountability both depend on.

---

## Every project has it (operator ruling 2026-09-23, D-368)

The audit log is MANDATORY in every project, whatever its scaffold type. "Properly" means all five:

1. **Vendored** — `cp -r /opt/fabrik-lib/app-audit-log <project>/libs/audit_log` (vendor-don't-import).
2. **The table in the project's schema** — `libs/audit_log/schema.sql` folded into the project's own
   `db/schema.sql` (the backend's, e.g. `server/db/schema.sql`, where the project has one). ⚠️ Append-only is a
   ROLE-SEPARATION property, not a grant: Fabrik's registrar makes the app's role the database OWNER, and an
   owner can always re-grant itself `DELETE`, so the module's `REVOKE UPDATE, DELETE` cannot bind it. Until the
   registrar provisions a separate non-owning app role (filed to fleet), the hash chain is tamper-EVIDENCE, not
   tamper-proof — say so in the project's `docs/COMPLIANCE.md`, and never call the table append-only in a
   compliance claim. Where the watchdog sidecar is enabled, the registrar's `<db>_wd_rw` role also gets
   `UPDATE, DELETE` on every table by default privileges, `audit_log` included — run
   `REVOKE UPDATE, DELETE ON audit_log FROM <db>_wd_rw` when you fold the table in — and again after every registrar
   provisioning run, which re-grants it; where the watchdog is enabled (the role exists only
   there) the weekly job checks `has_table_privilege('<db>_wd_rw', 'audit_log', 'UPDATE') OR
   has_table_privilege('<db>_wd_rw', 'audit_log', 'DELETE')` and treats TRUE as an incident (also filed to fleet).
3. **Every sensitive operation recorded** — the vocabulary below: auth, billing, admin actions on user
   data, privacy rights and consent, and autonomous watchdog actions. A client-only surface (extension,
   mobile, desktop or static page) records through the backend it calls, never with a client-side write.
4. **Retention scheduled** — `data_retention.sql` from the project's scheduler, as the owner role (the app's
   role today; `<db>_wd_rw` can delete too until revoked). The watchdog sidecar does NOT run it, whatever the module's README and
   `data_retention.sql` header say (filed to fabrik-lib); register it yourself.
5. **Weekly verification** — `verify_chain(conn, since=<ts of the LAST row the previous run verified>)` from the
   scheduler: `verify_chain` skips the pointer check of the first row in its window, so starting at the previous
   run's last row makes every NEW row's pointer checked. A non-empty result is an incident (§ Hash-Chain Verification).

No scaffold type emits any of this yet (every emitted `db/schema.sql` lacks the table — filed to fleet), so
in a new project it is the first backend ticket; in an existing one it is owed now.

**Per type:** the Python-backed types (`saas-skeleton`, `python-api`, `python-api-gpu`, `file-worker`, and the `server/` that `office-extension`, `chrome-extension`, `mobile-app` and `static-site`
emit) vendor the module as above. `node-api` and `file-api` (both Node) have no fabrik-lib port yet (filed to fabrik-lib); until it lands
it owes the table plus a writer that hashes byte-identically to `canonical_payload`. A `desktop-app` or
`docusaurus` project with no backend records through whatever backend it calls; one that calls none has no
sensitive operation and says so in `docs/COMPLIANCE.md` rather than vendoring a module nothing can run.
`wordpress` is scaffolded by `/opt/wpf`, not the hub, and is outside this pack.

## Canonical Actor Vocabulary

**Rule (mirror of the action rule):** never invent a new actor form in code — the set below is
closed; extend it HERE first, then use it. Two projects inventing different prefixes (`admin:` vs
`operator:`) produce audit logs that cannot be correlated, and nothing detects it because each is
internally consistent (a consumer hit exactly this citation gap: `schema.sql` referenced a
vocabulary this pack did not carry).

| Actor form | Meaning |
| --- | --- |
| `user:<id>` | an authenticated end user; `<id>` is the app's canonical user id |
| `admin:<id>` | a human operating an admin surface; same id space as `user:` |
| `system` | the application itself (scheduled jobs, lifecycle hooks, cascades) |
| `watchdog` | the autonomous monitoring/self-healing layer |
| `anonymous` | an unauthenticated caller of an endpoint that still leaves a trace (the default IdP's logout with an expired session) |

Adding a prefix: a new AUTONOMOUS component class gets a bare literal (like `system`); anything
acting FOR an identifiable principal gets a `<prefix>:<id>` form. Add the row here in the same
change that first writes it.

## Canonical Action Vocabulary

**Rule:** Never invent a new action string in code. If the action doesn't exist in this vocabulary, add it here first, then use it.

The action string is a dotted identifier `<domain>.<verb>` (lowercase, snake_case). `domain` corresponds to the prefixes below; `verb` is past-tense for a state change ("revoked", "granted", "created") and an event noun where no state changes (`login_success`, `llm_call`).

### `auth.*` — authentication and session events

`account.*` is NOT a domain: account changes are `auth.*` (profile, email, sessions) or `gdpr.*` (deletion).

⚠️ **What the default IdP (`fabrik-lib/fastapi-user-auth`) actually writes** — `auth.signup`, `auth.login`,
`auth.logout`, `auth.password_reset` and `auth.passwordless_login`, through a hook that SWALLOWS every audit
failure and writes out-of-band on its own connection. It emits no `auth.login_failure`,
`auth.passwordless_requested` or `auth.passwordless_refused`, no `auth.signup` for a passwordless auto-signup (only
`auth.passwordless_login`), `auth.login` should be `auth.login_success`, and every
row it writes carries `target_type=NULL` and empty `details` — the `details`/`target_*` columns below are what
a project's OWN call sites owe.
All of this is filed to fabrik-lib (rename `auth.login`, emit the failure and refusal rows, and escalate a
failed audit write instead of passing). Until it lands, a vendoring project reads the module's `auth.login`
as `auth.login_success` and records the missing rows itself, at its own call sites.
The three `auth.passwordless_*` rows below are additive, not optional: the IdP already writes
`action="auth.passwordless_login"`.
Without them a vendored module violates this closed vocabulary by construction, and the vendoring
project cannot fix it — `.windsurf/rules/` is synced and `check_synced_unmodified.py` correctly blocks the local edit. `binding_mismatch` is a named refusal reason on
purpose: an approval link opened in a browser that never requested the login must leave its own
audit trace.

| Action | Triggers | `details` shape | `target_*` |
| --- | --- | --- | --- |
| `auth.login` | DEPRECATED alias the default IdP writes for `auth.login_success` until fabrik-lib renames it — query both; never write it from project code | none (the IdP writes no details) | `target_type` NULL, `target_id` = user_id |
| `auth.login_success` | Successful password/MFA login (a passwordless success is `auth.passwordless_login`) | `{ip, user_agent, mfa_used: bool}` | `user`, user_id |
| `auth.login_failure` | Wrong password / failed MFA | `{ip, user_agent, reason: "wrong_password" \| "mfa_failed" \| ...}` | `user`, user_id (if known) |
| `auth.signup` | An account was created (password signup, or a passwordless first login) | `{ip, user_agent, via: "password" \| "passwordless"}` | `user`, user_id |
| `auth.logout` | User-initiated logout | `{ip}` | `user`, user_id |
| `auth.password_changed` | User changed their own password | `{}` | `user`, user_id |
| `auth.password_reset` | A password was reset through the emailed reset flow | `{ip}` | `user`, user_id |
| `auth.passwordless_requested` | A magic-link / OTP login was requested | `{ip, user_agent, email_hash}` | `user`, user_id (if known) |
| `auth.passwordless_login` | Passwordless login succeeded | `{ip, user_agent, via: "link" \| "code"}` | `user`, user_id |
| `auth.passwordless_refused` | A passwordless approval was REFUSED | `{ip, reason: "expired" \| "already_used" \| "binding_mismatch"}` | `user`, user_id (if known) |
| `auth.profile_updated` | User changed profile fields (name, locale, timezone) | `{fields: [..]}` (names only, never values) | `user`, user_id |
| `auth.avatar_set` | User set or removed an avatar | `{}` | `user`, user_id |
| `auth.email_changed` | User changed account email | `{old_email_hash, new_email_hash}` (hash, not plain) | `user`, user_id |
| `auth.mfa_enabled` | User added MFA factor | `{factor_type: "totp" \| "webauthn" \| ...}` | `user`, user_id |
| `auth.mfa_disabled` | User removed MFA factor | `{factor_type}` | `user`, user_id |
| `auth.session_revoked` | Session invalidated (any reason) | `{reason: "user_action" \| "admin" \| "suspicious"}` | `session`, session_id |

### `billing.*` — payment and subscription events

`amount_minor` is the provider's amount as a string in the currency's lowest unit (Paddle's `totals.total`), never a float — rounding in an audit row is a finding. (Renamed from `amount_usd` on 2026-09-23; no fleet row carried the old key.)

| Action | Triggers | `details` shape | `target_*` |
| --- | --- | --- | --- |
| `billing.subscription_created` | New subscription wired | `{plan, amount_minor, currency, billing_period}` | `subscription`, sub_id |
| `billing.subscription_updated` | Plan change / quantity change | `{old_plan_id, new_plan_id, old_status, new_status, reason}` | `subscription`, sub_id |
| `billing.subscription_cancelled` | User or system cancelled | `{reason}` | `subscription`, sub_id |
| `billing.charge_succeeded` | Money received | `{amount_minor, currency, provider_txn_id}` | `subscription`, sub_id (`transaction`, txn_id for a one-time purchase) |
| `billing.charge_failed` | Charge attempt failed | `{amount_minor, currency, provider_error_code}` | `subscription`, sub_id |
| `billing.refund_issued` | Refund processed | `{amount_minor, currency, reason}` | `subscription`, sub_id |
| `billing.dispute_opened` | Chargeback / dispute filed | `{amount_minor, currency, provider_dispute_id}` | `subscription`, sub_id |

### `admin.*` — operator actions on user data

| Action | Triggers | `details` shape | `target_*` |
| --- | --- | --- | --- |
| `admin.user_impersonated` | Admin acts as another user | `{admin_user_id}` | `user`, impersonated_user_id |
| `admin.user_quota_overridden` | Admin changes a user's quota | `{from, to, reason}` | `user`, user_id |
| `admin.feature_flag_toggled` | Admin flips a feature flag | `{flag, from, to}` | `feature_flag`, flag_name |
| `admin.data_exported` | Admin downloaded user data | `{admin_user_id, format}` | `user`, user_id |
| `admin.user_deleted` | Admin hard-deleted a user | `{admin_user_id, reason}` | `user`, user_id |
| `admin.api_key_created` | An API key was issued | `{key_prefix, scopes}` (never the key) | `api_key`, key_id |
| `admin.api_key_revoked` | An API key was revoked | `{reason}` | `api_key`, key_id |

### `gdpr.*` and `consent.*` — privacy-rights events

| Action | Triggers | `details` shape | `target_*` |
| --- | --- | --- | --- |
| `gdpr.export_requested` | User requested data export | `{}` | `user`, user_id |
| `gdpr.export_delivered` | Export file delivered to user | `{file_bytes, format}` | `user`, user_id |
| `gdpr.deletion_requested` | User requested account erasure | `{}` | `user`, user_id |
| `gdpr.deletion_cancelled` | User withdrew an erasure request within the grace period | `{}` | `user`, user_id |
| `gdpr.deletion_purged` | Hard purge executed (post-grace) | `{purged_rows: int}` | `user`, user_id |
| `consent.granted` | User opted in (any purpose) | `{purpose, source: "web" \| "api" \| "import"}` | `user`, user_id |
| `consent.withdrawn` | User opted out | `{purpose, source}` | `user`, user_id |

### `watchdog.*` — autonomous sidecar actions

The fabrik-lib watchdog sidecar does not write these rows yet — it keeps its own deploys table (filed to
fabrik-lib). Until it does, a project running the sidecar records them from its own wiring where it can.

| Action | Triggers | `details` shape | `target_*` |
| --- | --- | --- | --- |
| `watchdog.tier_a_action` | Sidecar took an autonomous Tier A action | `{action: "restart_container" \| "clear_cache" \| ..., reason, llm_provider, llm_model}` | `container`, container_name |
| `watchdog.tier_b_action` | Sidecar took an opt-in Tier B action | same as Tier A | `container`, container_name |
| `watchdog.tier_c_escalation` | Sidecar escalated to owner (no autonomous action) | `{reason, severity: "warn" \| "urgent"}` | `container`, container_name |
| `watchdog.llm_call` | Sidecar issued an LLM call (success or failure) | `{provider, model, in_tokens, out_tokens, cost_usd, incident_id, confidence}` | `incident`, incident_id |
| `watchdog.budget_kill_switch` | Sidecar dropped to rule-only mode (cap reached) | `{daily_usd_spent, daily_usd_cap, daily_invocations_spent, daily_invocations_cap}` | `project`, project_id |

---

## Retention Policy

**Default TTL: 12 months from `ts`.** Apply via `data_retention.sql` from your project's scheduler, as the owner
role (the app's role today — § Every project has it (operator ruling 2026-09-23, D-368)); the watchdog sidecar does not run it.

**Longer periods — keep for the legal period, then purge (never indefinitely):**

- `billing.*` — 10 years from the end of the record's year: this house's policy, matched to TTK Art. 82 for the
  accounting documents the rows corroborate (VUK Art. 253's 5 years is only the tax floor). The row is
  evidence, not the invoice — where Paddle is merchant of record it issues the invoice — so counsel confirms
  the period in `docs/COMPLIANCE.md`.
- `consent.*` — evidence of consent (GDPR Art. 7(1): the controller must be able to demonstrate it), kept
  while the processing it authorises lasts plus the claim-limitation period your counsel names.
- `gdpr.*` — evidence that data-subject requests were honoured (GDPR Art. 5(2) accountability), on the same basis.

KVKK Art. 7 and GDPR storage limitation require personal data to be deleted once the reason for keeping it
ends, so "kept forever" is itself a violation. The shipped `data_retention.sql` only EXEMPTS these prefixes
from the 12-month delete (filed to fabrik-lib: give each prefix its own end date). Until it does, add to your
vendored copy a second `DELETE … WHERE action LIKE 'billing.%' AND ts < date_trunc('year', now()) - interval
'10 years'` — counted from year end, as the law counts. Never give `consent.*` or `gdpr.*` a bare `ts <` cutoff:
a `consent.granted` row is proof while that consent is still in force, however old it is. Purge them only once
the processing has ended (after the matching `consent.withdrawn` or `gdpr.deletion_purged` row, plus the
documented period). Record every period in the project's `docs/COMPLIANCE.md`.

## Concurrency — one writer at a time on the chain

ONE concurrent pair of writers is enough to fork the chain (two rows pointing at the same tip), and a clock
that steps back forks it with no concurrency at all. So every writer:

- takes `pg_advisory_xact_lock(AUDIT_CHAIN_LOCK_KEY)` in the SAME transaction as the write — every writer,
  sync or async, on that one module constant (an advisory lock needs no table privilege, which the
  append-only table denies; `SELECT … FOR UPDATE` needs `UPDATE` and cannot be used);
- runs a vendored copy recent enough to clamp `ts` against the tip (`_select_tip` present, not only
  `_select_tip_hash`) — re-vendor an older copy before reading any break as tampering.

- runs the lock, the tip read and the INSERT in ONE explicit transaction and then commits: under
  `autocommit=True` with no `conn.transaction()` block each statement commits on its own, so the lock releases before the INSERT (a silent no-op), and `record_event` itself never commits.

`verify_chain(strict=False)` is a TEST-scoping tool only — never in the weekly job or an alert path, where it would
silence a real fork.

**`record_event` takes a SYNC DB-API connection** (psycopg). An async app (asyncpg) writes through the module's
public transport helpers (`canonical_payload`, `sha256_hex`, `validate_*`) in the SAME transaction as the business
change, taking `AUDIT_CHAIN_LOCK_KEY` — the module's constant, never a key of its own, or two writers serialise
against nothing — and re-implements what the helpers do not cover exactly as `record_event` does: the tip read
(`_select_tip`), the `ts` clamp against the tip, and the `str()` coercion of `target_*`. The IdP's `reference_adapter.py` is NOT a model: it takes no lock, never commits and writes
out-of-band. The module ships no async writer yet (both filed to fabrik-lib).

## Hash-Chain Verification

**When to verify:**

- **Weekly:** a cron / scheduler / admin endpoint calls `al.verify_chain(conn, since=<ts of the last row the previous run verified>)` (§ Every project has it (operator ruling 2026-09-23, D-368), item 5). Empty result = chain intact.
- **On admin demand:** "Verify audit log" button in admin tooling.
- **After retention DELETE:** retention deletes rows from the MIDDLE of the chain (auth rows between kept billing rows), so every kept row whose predecessor was deleted has a dangling `prev_hash` and can never be chain-verified again — only its own content hash remains as evidence. Keep every verification run inside the post-retention window, and never claim chain linearity across a retention gap (preserving it across retention is filed to fabrik-lib).

**When a break is detected:**

1. **Freeze writes** to `audit_log` (set a feature flag, or block at the application layer).
2. **Run the `audit_log_chain_check` view** for fast SQL-only pointer-break enumeration, filtered to `WHERE ts >= now() - interval '12 months' AND prev_hash_mismatch` — the view has no time window, and every older mismatch, and the first row of the window, is a retention gap, not a break.
3. **Run `verify_chain()` over the post-retention window** (an unbounded run is meaningful only before retention has ever run; after it, it always reports the retention gaps).
4. **Alert ops** (Apprise / Telegram). Treat as a potential security incident until proven otherwise.
5. **Investigate** — common false positives: retention DELETE crossed an unbounded `verify_chain()`; two recorders pointed at the same tip (a fork).

## Anti-Patterns (what NOT to do)

- **Inventing action strings in code.** Always extend this vocabulary first.
- **Logging passwords, secret tokens, full PANs, or anything you wouldn't email to your auditor.** Use last-4, hashes, or opaque IDs only.
- **Logging high-cardinality product events** (page views, searches, feature impressions). Those belong in product analytics; the audit log is for *intentional* actions.
- **Logging application errors / stack traces.** Those belong in GlitchTip. The audit log records *what happened on purpose*, not what crashed.
- **Test data in production audit log.** Write tests to a separate test DB — the shipped retention SQL has no `test.` clause, so a `test.` prefix is never stripped. Mixing real and synthetic events corrupts compliance review.
- **Calling `verify_chain()` with no bounds on every request.** It's O(N) per call — fine for periodic review, hostile in a hot path.
- **Catching exceptions from `record_event()` and continuing silently.** If the audit log is unwritable, the business operation should ABORT or escalate (log and alert). The whole point of fail-loud here is to make data drops impossible — which the default IdP's audit hook currently violates (filed to fabrik-lib).

## Upgrade Path to A1 (Trigger Enforcement)

The schema columns are already in place. To enforce hashing at the database level (defense against application bugs that bypass the helper):

1. Write a `BEFORE INSERT` trigger that computes `prev_hash` from the latest row and `current_hash` from the new row's content (`pgcrypto`'s `digest(data, 'sha256')` returns `bytea` — encode it to hex to match the Python helper's digest), taking the same advisory lock.
2. Strip the Python-side `_select_tip_hash` and `_canonical_payload` calls from `record_event()`.
3. `verify_chain()` keeps working unchanged — only if the trigger emits `canonical_payload`'s exact bytes (fixed key order, compact separators, sorted `details`, unescaped UTF-8 (`ensure_ascii=False`), Python's float rendering, the module's `ts` format; `jsonb::text` does not). Prove it with `verify_chain()` over trigger-written rows before switching.

No schema migration; only the write path changes.

## Worked Example

A Paddle webhook handler receives a `transaction.completed` event. Paddle may deliver the same event more than
once (live: up to 60 retries over 3 days), so the FIRST statement of the transaction CLAIMS the envelope's
`event_id` with a unique insert — a concurrent or later redelivery finds the claim taken and records nothing —
and the audit row commits in the same transaction as the business update.

```python
# CREATE TABLE webhook_events (event_id TEXT PRIMARY KEY, received_at TIMESTAMPTZ NOT NULL DEFAULT now());
# (the PRIMARY KEY is what makes ON CONFLICT fire — without it every redelivery is recorded again)

async def verified_paddle_payload(req: Request) -> dict:
    body = await req.body()                              # the raw bytes the signature covers
    return verify_paddle_signature(req.headers, body)    # raises on a bad signature

@app.post("/webhooks/paddle")
def paddle_webhook(payload: dict = Depends(verified_paddle_payload),
                   conn = Depends(get_sync_db)):         # psycopg 3, autocommit=True: transaction() below is then the one real transaction
    if payload["event_type"] != "transaction.completed":
        return {"ok": True}
    data = payload["data"]
    with conn.transaction():
        claimed = conn.execute(
            "INSERT INTO webhook_events (event_id) VALUES (%s) ON CONFLICT DO NOTHING RETURNING event_id",
            (payload["event_id"],),
        ).fetchone()
        if claimed is None:                              # already processed (a retry or a concurrent delivery)
            return {"ok": True}
        mark_transaction_paid(conn, data["id"], data["subscription_id"])  # subscription_id is null for one-time purchases
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (al.AUDIT_CHAIN_LOCK_KEY,))  # one writer on the chain, held only for the write
        al.record_event(                                 # raises on failure → the transaction rolls back → Paddle retries
            conn,
            actor="system",
            action="billing.charge_succeeded",
            target_type="subscription" if data["subscription_id"] else "transaction",
            target_id=data["subscription_id"] or data["id"],
            details={
                "amount_minor": data["details"]["totals"]["total"],   # a string, in the currency's lowest unit
                "currency": data["currency_code"],
                "provider_txn_id": data["id"],
            },
        )
    return {"ok": True}
```

The `billing.*` prefix keeps this row past the 12-month delete, for its policy period (§ Retention Policy). A
reviewer can later `query_events(action="billing.charge_succeeded", since=…, until=…)` and reconstruct which
charges were recorded, with each row's content hash as evidence; chain linearity is provable only inside the
post-retention window (§ Hash-Chain Verification).
