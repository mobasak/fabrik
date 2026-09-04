---
activation: glob
globs: ["**/billing/**", "**/payments/**", "**/paddle/**", "**/paytr/**", "**/iyzico/**", "**/webhooks/**", "**/subscriptions/**"]
description: Payments & billing discipline — Paddle Billing v2 (MoR, international), PayTR (Turkish domestic) with iyzico as its fallback, webhook idempotency, entitlement modeling, subscription lifecycle
trigger: glob
---
<!-- CONSUMER: Coding agents building SaaS billing + Traycer (epic-brief for SaaS)
     GOAL: Paddle/iyzico integration, webhook security, entitlement model, tax documentation
     TRAYCER USAGE: Shapes billing epic. Injects provider selection + entitlement model into tickets.
     AGENT USAGE: Follow verbatim for Paddle/iyzico checkout, webhook, and entitlement implementation. -->

# Payments & Billing Rules

Apply when working on SaaS payment integration, subscription lifecycle, entitlements, webhook processing, or checkout flows. Skip for unrelated API, UI, or infrastructure work.

**Scope exclusion — WooCommerce:** WooCommerce storefront checkout is governed by `00-domain-wordpress.md` §9 (Monetization), not this pack, because it operates as product e-commerce rather than SaaS subscription billing. (The exclusion is about the CHECKOUT MODEL, not the gateway: PayTR is this pack's own Turkish domestic rail as of 2026-09-03 — see § Payment Providers. This line previously read "PayTR for physical D2C", which grepped as "PayTR is out of scope here" at the moment it became the primary in-scope processor.)

**Scope exclusion — Mobile IAP:** For Google Play Billing, App Store StoreKit, RevenueCat entitlements, and mobile-specific Turkey constraints, see `81-mobile-billing.md`. Mobile IAP is a fundamentally different billing model — do not apply this pack's Paddle/iyzico patterns to mobile digital goods.

---

## Payment Providers

THREE providers as of 2026-09-03, chosen at planning time by the product's target market:

- **Paddle Billing v2 (MoR)** — for international customers. Paddle handles global VAT/GST calculation, collection, remittance, and invoicing. The Turkish LLC receives a single B2B service export transaction, classified as zero-rated VAT under Turkish law.
- **PayTR** — the Turkish DOMESTIC processor (Turkish Lira pricing, local payment methods, Turkish consumer protection compliance).
- **iyzico** — PayTR's FALLBACK for the same domestic lane. Not removed, not paused: the adapter and its tests exist and are gated behind `PAYMENTS_IYZICO_ENABLED`.
- **Paddle + the domestic rail together** — when the product serves both international AND Turkish domestic markets.

⚠️ **"Fallback" is not yet a defined behaviour, and a design must not assume one.** `fabrik-lib/payments` has no fallback concept and deliberately refuses one — `ProviderUnavailable` exists so a routed-but-disabled provider RAISES, because *charging a customer through an unintended processor is never an acceptable default*. Whether the iyzico fallback is config-time failover, outage-time retry, or a per-currency precedence list is an OPEN design question owned by that module (fabrik-lib D-080). Until it is settled, treat the domestic rail as PayTR and iyzico as a configured alternative — never as an automatic runtime failover.

Traycer decides which configuration applies during `epic-brief` or `trigger-workflow` based on the product's target customer geography.

**Stripe** is NOT available to a Turkey-resident entity — Turkey is not a Stripe-supported country, so the Ocoron LLC cannot open a Stripe account directly. Accessing Stripe would require incorporating in a supported country (e.g. a US LLC) and operating through that foreign entity — out of scope for this pack and not a viable "fallback." That exclusion is STRUCTURAL and does not go stale. The provider SET does: it is **Paddle (international, MoR) + PayTR (Turkish domestic) + iyzico (PayTR's fallback)**, and it grew from two to three on 2026-09-03 by exactly the escalation this paragraph prescribes (fabrik-lib D-080 — this pack asserted a CLOSED two-provider set for a day after the ruling, because the decision was made in a sync-excluded repo that cannot edit this file). There is no Stripe fallback; if none of the three can handle a requirement, escalate it as a planning decision, not a code choice — and record the outcome in `docs/DECISIONS.md`, or the next reader inherits the same stale set.

---

## Paddle Integration

### Checkout Pattern

- Use the **Overlay Checkout** exclusively (`Paddle.Checkout.open()` via `@paddle/paddle-js`). The user stays on your domain while Paddle handles localization, currency, and payment capture.
- **Banned**: Inline Checkout (high frontend maintenance), Hosted Checkout (breaks UX flow), custom payment forms (PCI compliance burden).

### Subscription Management

- All subscription lifecycle operations (cancellation, plan changes, payment method updates, invoice downloads) must use **Paddle Customer Portal sessions** generated via the backend API (`/customers/{id}/portal-sessions`).
- **Never** build custom billing management UI. The backend returns a time-limited portal URL; the frontend redirects.

### Webhook Security

- Verify webhook signatures using the **raw, unparsed byte stream** (`await request.body()`). Never parse the payload into JSON or Pydantic models before HMAC verification — JSON re-serialization alters byte layout and invalidates the signature.
- The `Paddle-Signature` header has the form `ts=<unix_ts>;h1=<hash>`. Parse out `ts` and `h1`, then compute `HMAC-SHA256(secret, f"{ts}:{raw_body}")` and `compare_digest` against `h1`. **The signed payload is `ts:body`, not body alone** — signing the body by itself is the #1 cause of "signature always invalid." Optionally reject stale `ts` (replay protection).
- Use `hmac.compare_digest()` for all signature comparisons. Standard `==` string equality is **banned** — it leaks timing information to attackers.
- Load `PADDLE_WEBHOOK_SECRET` from Pydantic Settings (`get_settings().paddle_webhook_secret`). Never hardcode.

### Webhook Processing

- Paddle enforces a **5-second timeout**. Return `200 OK` within 3 seconds. Defer all heavy processing (DB writes, email sends, third-party calls) to background tasks or the PostgreSQL job queue (per `75-workers-jobs.md`).
- Accept **at-least-once delivery** — Paddle retries failed deliveries with exponential backoff: **60 retries over 3 days** on live (20 attempts in the first hour, 47 by end of day 1). Sandbox: 3 retries over 15 minutes. Any non-2xx, connection refusal, or timeout = retry.

### Webhook Idempotency

- Record every webhook `event_id` in a `webhook_events` PostgreSQL table (on `postgres-main:5432`) with a unique constraint.
- Use `INSERT INTO webhook_events (event_id, ...) ... ON CONFLICT DO NOTHING`. If no rows inserted, the event is a duplicate — return `200 OK` and skip processing.
- This prevents double-provisioning, duplicate subscription creation, or erroneous cancellations from Paddle retries.

### Refunds & Adjustments

- Paddle Billing has **no `transaction.refunded` event** — it does not exist. Refunds, credits, and chargebacks are modelled through the **Adjustments API**: `POST /adjustments` with `action: "refund"`, `type: "full" | "partial"`, `transaction_id`, a `reason` string, and (for partial) an `items[]` array of `{ item_id, type, amount }`. An **`adjustment.created`** webhook fires (later state changes emit **`adjustment.updated`**); subscribe to both and record them in `webhook_events` for the same idempotency guarantee.
- As **Merchant of Record, Paddle reverses the proportional sales tax/VAT automatically inside the adjustment** — `items[].amount` is tax-inclusive by default. The seller does **not** separately reverse or reclaim tax on a refund; the adjustment totals already net it out. (Teknokent _döviz beyanı_: the monthly Transactions/Reverse-Invoice reports already reflect adjustments.)
- Map adjustment events to your metrics: a full-refund `adjustment.created` reverses the corresponding conversion and decrements MRR; revoke the entitlement (`subscriptions.status`) accordingly.

### Environment Isolation

- Paddle Sandbox and Live environments must be strictly separated via environment variables: `PADDLE_ENVIRONMENT`, `PADDLE_CLIENT_TOKEN`, `PADDLE_API_KEY`, `PADDLE_WEBHOOK_SECRET`.
- Before any deployment, validate the full lifecycle in Sandbox: successful checkout, trial expiration, cancellation, upgrade, downgrade.

---

## iyzico Integration (Turkish Domestic)

### When iyzico Applies

The Turkish domestic lane (TRY pricing, B2B SaaS sold to Turkish companies, consumer products with Turkish pricing) is served by **PayTR** since 2026-09-03; **iyzico is its configured fallback**, and everything below still binds wherever iyzico is the provider in use.

⚠️ **There is no PayTR integration section in this pack yet, and one must not be invented.** PayTR's checkout pattern, webhook signature scheme, retry policy and idempotency story are NOT grounded here — fabrik-lib's D-080 records its terms as operator-supplied and explicitly not vendor-verified. Building on PayTR means grounding it live first (the `/fabrik-spec` § 1a research gate), through fabrik-lib's `payments` module, which owns the adapter. Writing PayTR rules from memory here would be exactly the version-literal drift this corpus exists to prevent.

### Checkout Pattern

- Use **iyzico Checkout Form** (hosted form embedded via iframe or redirect). iyzico handles Turkish card processing, installment options, and 3D Secure.
- Do not build custom card forms — PCI compliance burden is unacceptable for a solo developer.

### Webhook Security

- iyzico sends payment notifications to a callback URL (configured in Merchant Portal → Settings → Merchant Settings → Merchant Notifications; HTTPS required). First notification ~10–15s after the attempt; iyzico retries every 15 min until your server returns 2xx, then stops after 3 attempts.
- Verify payment status by calling the **iyzico API** server-side to confirm the transaction (do not trust the callback payload alone — it can be spoofed). Webhook `status` values: `SUCCESS` (paid), `FAILURE`, plus 3DS/APM intermediate states; `CONTACTLESS_REFUND` signals a refund.
- If you enable signed webhooks, verify the **`X-Iyz-Signature-V3`** header (V1/V2 are deprecated): `HMAC-SHA256` (hex) over `merchantId + secretKey + eventType + subscriptionReferenceCode + orderReferenceCode + customerReferenceCode`, compared with `hmac.compare_digest()`.
- Load `IYZICO_API_KEY` and `IYZICO_SECRET_KEY` from environment variables.

### Webhook Processing

- Same idempotency pattern as Paddle: `webhook_events` table with unique constraint on the transaction ID.
- Defer heavy processing to background tasks.

### Environment Isolation

- iyzico Sandbox and Live environments must be strictly separated via environment variables: `IYZICO_ENVIRONMENT`, `IYZICO_API_KEY`, `IYZICO_SECRET_KEY`.
- Test full lifecycle in Sandbox before production.

---

## Entitlement Model

- Decouple billing identity from application authorization. The PostgreSQL schema (on `postgres-main:5432`) must separate:
  - **`subscriptions`** — maps `user_id` to `paddle_subscription_id` (or `iyzico_subscription_id`), `status`, `plan_id`, `current_period_end`.
  - **`plan_features`** — maps `plan_id` to `feature_key` with `max_limit` (integer) and `is_enabled` (boolean).
- Authorization checks query the `plan_features` table dynamically. **Never** hardcode plan names in application logic (`if plan == "pro"` is banned).
- Pricing/packaging changes become data-only operations — insert new rows, zero code changes.

---

## Pricing Strategy

- Default to **Flat-Rate** or **Tiered** pricing models. These require simple boolean or integer entitlement checks.
- **Usage-based (metered) billing is banned** until the product reaches stability. Metered billing requires high-availability event ingestion pipelines — unacceptable overhead for a solo developer.

---

## Resilience

Paddle and iyzico APIs are external dependencies. Apply `58-resilience.md` basic resilience:

- **Checkout failures:** graceful fallback — show a clear error message with retry option. Never leave the user in a broken state.
- **Webhook endpoint:** timeout + retry is handled by the provider (Paddle retries 60 times over 3 days). Your endpoint must be idempotent and return 200 fast.
- **Portal session API calls:** wrap with `httpx.AsyncClient` + timeout (10s) + retry (3 attempts). If Paddle is down, show a message: "Billing portal temporarily unavailable."
- **iyzico payment verification calls:** wrap with timeout + retry. If iyzico is unreachable, do NOT grant entitlement — log the event and alert.
- Both providers must have a row in `docs/RESILIENCE.md` §2a.

---

## Observability

Billing events are high-value — log them with full context:

```python
logger.info("subscription_created",
    provider="paddle",
    event_type="subscription.created",
    subscription_id=sub_id,
    user_id=user_id,
    plan_id=plan_id,
    amount=amount,
    currency=currency,
)
```

- Use `structlog` — no `print()`. See `55-observability.md`.
- Log every webhook received (event_type, event_id, processing status).
- Log every entitlement change (user_id, old_status, new_status, reason).
- GlitchTip captures unhandled exceptions in webhook handlers automatically.

---

## Tax Documentation (Turkish LLC / Teknokent)

<!-- Verify with your mali müşavir before treating as binding rules. -->

- **Paddle payouts:** Paddle is the Merchant of Record. For Teknokent _döviz beyanı_ (foreign exchange declaration), export Paddle's monthly **Reverse Invoices** and **Transactions Reports**. These prove the incoming transfer is from legitimate software exports, securing income and corporate tax exemptions.
- **iyzico payouts:** iyzico is NOT a MoR — you are the merchant. Invoice each Turkish customer directly. 20% KDV applies to domestic sales.
- **Gross invoicing rule:** same as mobile — invoice the gross amount, expense platform commissions via KDV2. See `81-mobile-billing.md` § Teknokent Tax Treatment for the full breakdown (KVK exemption, KDV 0%/20% split, KDV2 reverse charge, W-8BEN-E). The rules are identical for SaaS and mobile payouts.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| LemonSqueezy / Braintree / Stripe / custom PSP | Paddle (international) and/or iyzico (Turkish domestic). Stripe is not available to a TR entity — do not design around it. |
| Inline Checkout or custom payment forms | Paddle Overlay Checkout / iyzico Checkout Form |
| Custom billing management UI (cancel, upgrade, invoices) | Paddle Customer Portal session redirect |
| `request.json()` or Pydantic model before HMAC verification | `await request.body()` raw bytes first |
| `==` for signature comparison | `hmac.compare_digest()` |
| Synchronous heavy processing in webhook handler | Return 200 immediately, defer to background via PG job queue |
| Hardcoded plan names in conditionals (`if plan == "pro"`) | `plan_features` table join for entitlement checks |
| Usage-based / metered billing | Flat-rate or tiered pricing |
| Trusting iyzico callback payload without server-side verification | Verify via iyzico API call |
| Paddle/iyzico API calls without timeout | `httpx.AsyncClient` + timeout + retry per `58-resilience.md` |
| `print()` in billing code | `structlog` with provider, event_type, amount, currency |
| `localhost` in DB connection for webhook_events | `postgres-main:5432` |

---

## Related Rule Packs

- `10-python.md` — FastAPI patterns, Pydantic Settings for API keys
- `20-typescript.md` — frontend Paddle SDK integration (`@paddle/paddle-js`)
- `55-observability.md` — structured logging for billing events
- `58-resilience.md` — timeout/retry/CB for Paddle and iyzico API calls
- `75-workers-jobs.md` — PG job queue for deferred webhook processing
- `81-mobile-billing.md` — mobile IAP (different model — RevenueCat, not Paddle)
- `88-saas-launch-checklist.md` — SaaS launch gates including billing readiness
- `95-multi-tenant-saas.md` — tenant-scoped subscription data
- `00-domain-saas.md` — planning-level billing decisions (§4 architecture, §7 pricing)

---

## Done When

- [ ] Paddle Overlay Checkout integrated — no custom payment forms or inline checkout.
- [ ] iyzico Checkout Form integrated for Turkish domestic (if applicable).
- [ ] Subscription management uses Paddle Customer Portal sessions — no custom billing UI.
- [ ] Paddle webhook verifies HMAC signature on raw `request.body()` bytes before JSON parsing.
- [ ] iyzico callback verified server-side via API call — not trusted from payload alone.
- [ ] Signature comparison uses `hmac.compare_digest()` exclusively.
- [ ] Webhooks return 200 within 3 seconds — heavy processing deferred to PG job queue.
- [ ] `webhook_events` table on `postgres-main` with unique `event_id` constraint for idempotency.
- [ ] Entitlements use `plan_features` mapping table — no hardcoded plan names in code.
- [ ] All provider credentials loaded from environment variables.
- [ ] Sandbox lifecycle tested (checkout, cancel, upgrade) before production deploy on both providers.
- [ ] Both Paddle and iyzico have rows in `docs/RESILIENCE.md` §2a.
- [ ] Billing events logged via `structlog` with provider, event_type, subscription_id, amount, currency.
- [ ] Teknokent tax documentation: Paddle reverse invoices exported; iyzico invoiced directly with KDV.
