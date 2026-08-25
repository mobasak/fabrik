---
activation: glob
globs: ["**/audit_log*", "**/libs/audit_log/**", "**/audit_log.py", "**/billing/**/webhook*", "**/auth/login*", "**/auth/password*", "**/auth/mfa*", "**/admin/**/impersonat*", "**/gdpr/**", "**/watchdog/actions*"]
description: Tamper-evident audit log for sensitive operations — canonical action vocabulary, hash-chain verification, retention policy
trigger: glob
---
<!-- CONSUMER: Coding agents (all) + Traycer (tech-plan step)
     GOAL: One append-only, hash-chained record of every sensitive op in the system.
     TRAYCER USAGE: For every Security / Billing / Admin / GDPR / Watchdog epic, include an "audit log" ticket that records the relevant actions per the canonical vocabulary.
     AGENT USAGE: Vendor /opt/fabrik-lib/app-audit-log/. Call al.record_event() at every sensitive op site. Don't invent new action strings — extend the vocabulary in this rule pack first. -->

# Audit Log Rules

**Activation:** Glob — audit log code paths, sensitive operation sites (auth, billing, admin, GDPR, watchdog actions).
**Purpose:** Every sensitive operation logged once, tamper-evidently, with a canonical action vocabulary that compliance review and watchdog accountability both depend on.

---

## When to Use

Vendor `app-audit-log` and call `record_event()` in projects that:

- Take payments (billing.*).
- Have user accounts with auth (auth.*).
- Have any admin tooling that acts on behalf of users (admin.*).
- Must comply with GDPR / KVKK data-subject rights (gdpr.*, consent.*).
- Run the watchdog sidecar (watchdog.*) — autonomous actions need an accountability trail.

If your service is none of the above (pure static site, internal worker with no human-visible actions), skip this module.

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

Adding a prefix: a new AUTONOMOUS component class gets a bare literal (like `system`); anything
acting FOR an identifiable principal gets a `<prefix>:<id>` form. Add the row here in the same
change that first writes it.

## Canonical Action Vocabulary

**Rule:** Never invent a new action string in code. If the action doesn't exist in this vocabulary, add it here first, then use it.

The action string is a dotted identifier `<domain>.<verb>` (lowercase, snake_case). `domain` corresponds to the prefixes below; `verb` is past-tense ("succeeded", "revoked", "granted").

### `auth.*` — authentication and session events

| Action | Triggers | `details` shape | `target_*` |
| --- | --- | --- | --- |
| `auth.login_success` | Successful login (any factor) | `{ip, user_agent, mfa_used: bool}` | `user`, user_id |
| `auth.login_failure` | Wrong password / failed MFA | `{ip, user_agent, reason: "wrong_password" \| "mfa_failed" \| ...}` | `user`, user_id (if known) |
| `auth.logout` | User-initiated logout | `{ip}` | `user`, user_id |
| `auth.password_changed` | User changed their own password | `{}` | `user`, user_id |
| `auth.email_changed` | User changed account email | `{old_email_hash, new_email_hash}` (hash, not plain) | `user`, user_id |
| `auth.mfa_enabled` | User added MFA factor | `{factor_type: "totp" \| "webauthn" \| ...}` | `user`, user_id |
| `auth.mfa_disabled` | User removed MFA factor | `{factor_type}` | `user`, user_id |
| `auth.session_revoked` | Session invalidated (any reason) | `{reason: "user_action" \| "admin" \| "suspicious"}` | `session`, session_id |

### `billing.*` — payment and subscription events

| Action | Triggers | `details` shape | `target_*` |
| --- | --- | --- | --- |
| `billing.subscription_created` | New subscription wired | `{plan, amount_usd, currency, billing_period}` | `subscription`, sub_id |
| `billing.subscription_updated` | Plan change / quantity change | `{old_plan_id, new_plan_id, old_status, new_status, reason}` | `subscription`, sub_id |
| `billing.subscription_cancelled` | User or system cancelled | `{reason}` | `subscription`, sub_id |
| `billing.charge_succeeded` | Money received | `{amount_usd, currency, provider_txn_id}` | `subscription`, sub_id |
| `billing.charge_failed` | Charge attempt failed | `{amount_usd, currency, provider_error_code}` | `subscription`, sub_id |
| `billing.refund_issued` | Refund processed | `{amount_usd, currency, reason}` | `subscription`, sub_id |
| `billing.dispute_opened` | Chargeback / dispute filed | `{amount_usd, currency, provider_dispute_id}` | `subscription`, sub_id |

### `admin.*` — operator actions on user data

| Action | Triggers | `details` shape | `target_*` |
| --- | --- | --- | --- |
| `admin.user_impersonated` | Admin acts as another user | `{admin_user_id}` | `user`, impersonated_user_id |
| `admin.user_quota_overridden` | Admin changes a user's quota | `{from, to, reason}` | `user`, user_id |
| `admin.feature_flag_toggled` | Admin flips a feature flag | `{flag, from, to}` | `feature_flag`, flag_name |
| `admin.data_exported` | Admin downloaded user data | `{admin_user_id, format}` | `user`, user_id |
| `admin.user_deleted` | Admin hard-deleted a user | `{admin_user_id, reason}` | `user`, user_id |

### `gdpr.*` and `consent.*` — privacy-rights events

| Action | Triggers | `details` shape | `target_*` |
| --- | --- | --- | --- |
| `gdpr.export_requested` | User requested data export | `{}` | `user`, user_id |
| `gdpr.export_delivered` | Export file delivered to user | `{file_bytes, format}` | `user`, user_id |
| `gdpr.deletion_requested` | User requested account erasure | `{}` | `user`, user_id |
| `gdpr.deletion_purged` | Hard purge executed (post-grace) | `{purged_rows: int}` | `user`, user_id |
| `consent.granted` | User opted in (any purpose) | `{purpose, source: "web" \| "api" \| "import"}` | `user`, user_id |
| `consent.withdrawn` | User opted out | `{purpose, source}` | `user`, user_id |

### `watchdog.*` — autonomous sidecar actions

| Action | Triggers | `details` shape | `target_*` |
| --- | --- | --- | --- |
| `watchdog.tier_a_action` | Sidecar took an autonomous Tier A action | `{action: "restart_container" \| "clear_cache" \| ..., reason, llm_provider, llm_model}` | `container`, container_name |
| `watchdog.tier_b_action` | Sidecar took an opt-in Tier B action | same as Tier A | `container`, container_name |
| `watchdog.tier_c_escalation` | Sidecar escalated to owner (no autonomous action) | `{reason, severity: "warn" \| "urgent"}` | `container`, container_name |
| `watchdog.llm_call` | Sidecar issued an LLM call (success or failure) | `{provider, model, in_tokens, out_tokens, cost_usd, incident_id, confidence}` | `incident`, incident_id |
| `watchdog.budget_kill_switch` | Sidecar dropped to rule-only mode (cap reached) | `{daily_usd_spent, daily_usd_cap, daily_invocations_spent, daily_invocations_cap}` | `project`, project_id |

---

## Retention Policy

**Default TTL: 12 months from `ts`.** Apply via `data_retention.sql` from your scheduler (or watchdog sidecar).

**Exempt action prefixes (kept indefinitely):**

- `billing.*` — tax law retention (5–10 years in most jurisdictions; TR: 5 years).
- `consent.*` — GDPR Art. 7 evidence of opt-in.
- `gdpr.*` — KVKK / GDPR compliance evidence.

To adjust: edit the `NOT LIKE` clauses in your project's vendored `data_retention.sql`. Document the change in your project's `docs/COMPLIANCE.md`.

## Hash-Chain Verification

**When to verify:**

- **Weekly:** a cron / scheduler / admin endpoint calls `al.verify_chain(conn, since=last_week_ts)`. Empty result = chain intact.
- **On admin demand:** "Verify audit log" button in admin tooling.
- **After retention DELETE:** retention removes rows; the chain now has gaps at the boundary. That's expected — bound `verify_chain(since=...)` to the post-retention range.

**When a break is detected:**

1. **Freeze writes** to `audit_log` (set a feature flag, or block at the application layer).
2. **Run `audit_log_chain_check` view** for fast SQL-only pointer-break enumeration.
3. **Run `verify_chain()` with no `since` bound** for full content-hash verification.
4. **Alert ops** (Apprise / Telegram). Treat as a potential security incident until proven otherwise.
5. **Investigate** — common false positives: retention DELETE crossed an unbounded `verify_chain()`; two concurrent recorders both pointed at the same tip (rare under solo-dev throughput, documented anti-pattern under high concurrency).

## Anti-Patterns (what NOT to do)

- **Inventing action strings in code.** Always extend this vocabulary first.
- **Logging passwords, secret tokens, full PANs, or anything you wouldn't email to your auditor.** Use last-4, hashes, or opaque IDs only.
- **Logging high-cardinality product events** (page views, searches, feature impressions). Those belong in product analytics; the audit log is for *intentional* actions.
- **Logging application errors / stack traces.** Those belong in GlitchTip. The audit log records *what happened on purpose*, not what crashed.
- **Test data in production audit log.** Use a `test.` action prefix that retention strips after 24h, OR write to a separate test DB. Mixing real and synthetic events corrupts compliance review.
- **Calling `verify_chain()` with no bounds on every request.** It's O(N) per call — fine for periodic review, hostile in a hot path.
- **Catching exceptions from `record_event()` and continuing silently.** If the audit log is unwritable, the business operation should ABORT or escalate. The whole point of fail-loud here is to make data drops impossible.

## Upgrade Path to A1 (Trigger Enforcement)

The schema columns are already in place. To enforce hashing at the database level (defense against application bugs that bypass the helper):

1. Write a `BEFORE INSERT` trigger that computes `prev_hash` from the latest row and `current_hash` from the new row's content (use `pgcrypto` `digest()` or call a PL/Python function).
2. Strip the Python-side `_select_tip_hash` and `_canonical_payload` calls from `record_event()`.
3. `verify_chain()` keeps working unchanged.

No schema migration; only the write path changes.

## Worked Example

A Paddle webhook handler receives a `transaction.completed` event:

```python
@app.post("/webhooks/paddle")
async def paddle_webhook(req: Request, conn = Depends(get_db)):
    payload = await req.json()
    verify_paddle_signature(req.headers, payload)

    if payload["event_type"] == "transaction.completed":
        sub_id = payload["data"]["subscription_id"]
        amount = float(payload["data"]["details"]["totals"]["total"]) / 100

        # Update the business state.
        mark_subscription_paid(conn, sub_id, amount)

        # Record the audit event. record_event() raises on DB failure;
        # if it raises we want the whole webhook to fail so Paddle retries.
        al.record_event(
            conn,
            actor="system",
            action="billing.charge_succeeded",
            target_type="subscription",
            target_id=sub_id,
            details={
                "amount_usd": amount,
                "currency": payload["data"]["currency_code"],
                "provider_txn_id": payload["data"]["id"],
            },
        )
        return {"ok": True}
```

The audit row survives indefinitely (the `billing.*` prefix exempts it from the 12-month retention). A year later, a compliance reviewer can `query_events(action="billing.charge_succeeded", since=last_year, until=last_year_plus_30d)` and reconstruct exactly what charges were recorded — with hash-chain proof that the records haven't been altered since.
