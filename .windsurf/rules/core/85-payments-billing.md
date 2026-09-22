---
activation: glob
globs: ["**/billing/**", "**/payments/**", "**/paddle/**", "**/paytr/**", "**/iyzico/**", "**/webhooks/**", "**/subscriptions/**"]
description: Payments & billing discipline — the vendored fabrik-lib `payments` module; Paddle Billing (MoR, international), iyzico (TRY subscriptions) and PayTR (TRY one-off) routed by billing model; no Non3D on any lane; webhook verification + idempotency; webhook-derived entitlements
trigger: glob
currency_pass: 2026-09-23
---
<!-- CONSUMER: Coding agents building SaaS billing
     GOAL: provider routing, webhook security, entitlement model, tax documentation — through the vendored module
     AGENT USAGE: Vendor fabrik-lib/payments and follow this pack; the module README's Gotchas are part of the rule. -->

# Payments & Billing Rules

Apply when working on SaaS payment integration, subscription lifecycle, entitlements, webhook processing, or checkout flows. Skip for unrelated API, UI, or infrastructure work.

**Scope exclusion — WooCommerce:** WooCommerce storefront checkout is governed by `00-domain-wordpress.md` §9 (Monetization): it is product e-commerce, not SaaS billing. The exclusion is about the checkout MODEL, not the gateway — PayTR is this pack's own Turkish one-off rail.

**Scope exclusion — Mobile IAP:** Google Play Billing, App Store StoreKit, RevenueCat and mobile-specific Turkey constraints are `81-mobile-billing.md`. Do not apply this pack's patterns to mobile digital goods.

---

## Reference Implementation — vendor `fabrik-lib/payments`

Billing is built by VENDORING `/opt/fabrik-lib/payments/` (copy, never import across repos), not by hand. It implements this pack: one `PaymentProvider` interface over Paddle, iyzico and PayTR, billing-model routing, raw-byte webhook verification, `(provider, event_id)` idempotency, webhook-derived entitlements, `org_id` row-level security, and a hosted-surface UI. Its README's **Gotchas** are binding — each records a live failure (a price-of-record trap, a silent env-var discard, a lane that closes rather than degrades).

- **Driver:** psycopg, the generation with the `conn.transaction()` API (`store.process_webhook` uses it); a psycopg2 connection fails on the first webhook.
- **Queue:** fulfilment INSERTs into a `jobs` table — vendor `fabrik-lib/job-queue` alongside it (`75-workers-jobs.md`).
- **Cross-tenant webhook writes:** set `shape.needs_payments_ingest: true` (with `needs_database: true`) in the service spec; `fabrik apply` mints the scoped `NOBYPASSRLS` ingest role and injects `PAYMENTS_INGEST_DATABASE_URL` (`95-multi-tenant-saas.md` § Admin & Maintenance Access). Wire the router's webhook `get_conn` to that DSN — that wiring IS the guard. The module's `verify_service_role` defaults to expecting `BYPASSRLS` and refuses the scoped role; passing `allow_policy_based=True` silences it but then checks NOTHING (it returns for any role, tenant or `BYPASSRLS` alike), so to actually assert, query `SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user` at boot and require both false (`docs/CONFIGURATION.md` § Payments webhook ingest). The fulfilment worker never uses this role. Never route ingest through `fabrik_admin` or any `BYPASSRLS` role.
- **Configuration:** `PAYMENTS_{PADDLE,IYZICO,PAYTR}_ENABLED`, `PADDLE_*`, `IYZICO_*`, `PAYTR_*` env vars — the module README § Configuration is the list. ALL provider credentials — `PADDLE_*`, `IYZICO_*`, `PAYTR_*` — must be real process env: the module's `.env` autoload loads `PAYMENTS_*` keys only and drops anything else SILENTLY, so a secret put in a project `.env` looks configured and is not (every Paddle webhook then 401s).

---

## Payment Providers

Routing splits by **billing model**, not by precedence (fabrik-lib D-084, operator ruling):

| Lane | Provider | What it is |
|---|---|---|
| International (any currency but TRY) | **Paddle Billing** | Merchant of Record: Paddle calculates, collects and remits VAT/GST and invoices the buyer. The Turkish LLC receives one B2B service-export payout. |
| Turkish domestic, **subscription** (TRY) | **iyzico** | iyzico's subscription engine (products, pricing plans, its own scheduler, signed renewal webhooks). |
| Turkish domestic, **one-off** (TRY) | **PayTR** | 3-D Secure iFrame; no subscription object. |

- **Neither domestic lane is the other's fallback, under any circumstance.** A routed-but-disabled provider RAISES (`ProviderUnavailable` → HTTP 409); `PAYMENTS_PAYTR_ENABLED=false` CLOSES domestic one-off checkout, it does not hand it to iyzico — while in-flight callbacks still ingest (webhooks gate on verification, not on the enabled set). Charging a customer through an unintended processor is never an acceptable default.
- **No Non3D processing on any lane** (fabrik-lib D-083, operator ruling): never request PayTR's Non3D permission or its recurring-payment flag; never use iyzico's raw-card subscription start. ⚠️ **iyzico processes EVERY subscription charge as NON3D, the first one included, and its hosted Checkout Form does not change that** (its Turkish docs, claim `iyzico-subscription-non3d`) — so the TRY subscription lane conflicts with the policy it must obey. There is also no iyzico merchant account yet (fabrik-lib D-235). A product that needs TRY recurring billing is therefore a PLANNING decision to escalate and record in `docs/DECISIONS.md`, never a code choice.
- **Live-provider status:** the PayTR lane was built from PayTR's published docs with no merchant account behind it — a green suite proves the code matches the docs, not that PayTR settles a payment; treat the first live transaction as the real test. ⚠️ **OPEN BLOCKER on enabling PayTR in production:** `purchases` accepts writes only from a `BYPASSRLS` role (its sole tenant policy is `FOR SELECT`, and the ingest role holds no grant on it), while `95-multi-tenant-saas.md` bans `BYPASSRLS` for ingest and workers — so under the hub's role model no role can record a one-off, and the first live payment would charge without fulfilling. Filed to fabrik-lib and fleet; until one of them provides the write path — a scoped non-`BYPASSRLS` role for the fulfilment worker holding `INSERT` and `SELECT` on `purchases` plus BOTH an `INSERT` and a `SELECT` policy for it (`record_purchase`'s `ON CONFLICT … RETURNING` is refused under the `INSERT` policy alone, and a grant alone is refused by FORCE RLS; measured) — keep `PAYMENTS_PAYTR_ENABLED=false` in production. Not the ingest role: the fulfilment worker never uses it (above). Once it exists, a one-off is persisted only when YOUR fulfilment worker calls `PgWebhookStore.record_purchase` with the plan and amount from YOUR checkout record keyed on `merchant_oid`: nothing persists the quote at checkout and `record_purchase` verifies no amount — keep that record and compare PayTR's `total_amount` to it yourself, gated on `status == 'success'` (module README Gotchas).
- **Stripe is not an option.** Turkey is not a Stripe-supported country, so the Turkish LLC cannot open an account (claim `stripe-unsupported-turkey`); reaching it would mean operating through a foreign entity — out of scope. If no lane can meet a requirement, escalate it as a planning decision and record the outcome.

The provider SET grew from two to three on 2026-09-03 and its routing was settled on 2026-09-05, both by rulings made in fabrik-lib (hub D-120 records the first). A change to either is a ruling first, recorded in `docs/DECISIONS.md`, then this pack.

---

## Paddle Integration

Paddle **Billing** (not Paddle Classic): its versioned REST API (the `Paddle-Version` header — the account default applies when omitted) and the Billing-only Paddle.js SDK `@paddle/paddle-js` (claim `paddle-billing-api-basics`).

### Checkout Pattern

- **Overlay Checkout** — `initializePaddle({ environment, token })` then `paddle.Checkout.open({ items: [{ priceId, quantity }] })`. The user stays on your domain while Paddle handles localization, currency and payment capture.
- **Banned (house policy):** Inline Checkout — Paddle documents it as first-class but needing more engineering; not worth it for a solo operator. Hosted Checkout (breaks the flow) and custom payment forms (PCI burden) likewise.

### Subscription Management

- Cancellation, plan changes, payment-method updates and invoices go through the **Paddle customer portal**: the backend calls `POST /customers/{customer_id}/portal-sessions` (optionally with `subscription_ids`) and the frontend redirects to the returned `urls.general.overview` or a per-subscription URL.
- Portal links carry a temporary token with an undocumented lifetime: create a session per click, never store or cache the URL, never embed it in an iframe.
- **Never** build custom billing-management UI.

### Webhook Security

- Verify over the **raw, unparsed bytes** (`await request.body()`) before any JSON or Pydantic parse — re-serialization changes the bytes and breaks the signature.
- `Paddle-Signature: ts=<unix>;h1=<hex>`. The signed payload is **`f"{ts}:{raw_body}"`** — the body alone is the classic "always invalid" bug — HMAC-SHA256 keyed with that notification destination's secret. Accept more than one `h1` (Paddle announces multiple values for future secret rotation).
- Compare with `hmac.compare_digest()`; `==` is banned (timing leak) — claim `paddle-webhook-signature`.
- **Replay window:** the module rejects a `ts` more than `PADDLE_TS_TOLERANCE_S` (default 5 s, Paddle's SDK default) from now in either direction — so a host clock drifting toward 5 s rejects EVERY webhook with a 401 (network latency counts against the margin). Run NTP on every webhook host; fix the clock rather than widening the window.
- `PADDLE_WEBHOOK_SECRET` from settings, never hardcoded.

### Webhook Processing

- Paddle's limit is **five seconds**; answer `200` within **3 s** — the margin covers network and TLS — and do the database work, email and third-party calls in the job queue (`75-workers-jobs.md`).
- **At-least-once delivery:** live retries 60 times within 3 days (20 in the first hour, 47 in the first day); sandbox 3 times within 15 minutes; any non-2xx, refusal or timeout counts as a failure (claim `paddle-webhook-delivery`).
- **Order is not guaranteed** — use `occurred_at`; the module's entitlement state machine converges for most out-of-order histories and names the exceptions.

### Webhook Idempotency

- `webhook_events` (module schema) records every event under a UNIQUE `(provider, event_id)` — a Paddle id and an iyzico reference that collide stay distinct.
- `INSERT … ON CONFLICT (provider, event_id) DO NOTHING`; no row inserted = duplicate → `200` and skip.
- Verify + record + enqueue run in ONE transaction (`store.process_webhook`): an enqueue failure rolls the record back so the provider's retry re-processes cleanly.

### Refunds & Adjustments

- There is **no `transaction.refunded` event.** Refunds and credits are `POST /adjustments` with `action: "refund" | "credit"`, `type: "full" | "partial"` (partial needs `items[]`), `transaction_id`, `reason`. The other five actions — four chargeback ones and `credit_reverse` — are created BY Paddle; code never posts them. Live refunds usually start `pending_approval` until Paddle reviews them (claim `paddle-adjustments`).
- Subscribe to `adjustment.created` and `adjustment.updated`, recorded through the same idempotency.
- As Merchant of Record, Paddle nets the tax out inside the adjustment (`tax_mode` defaults to tax-inclusive); the seller reverses nothing separately.
- ⚠️ **`adjustment.created` does NOT revoke access.** One event covers seven actions (credit, refund, chargebacks and their reversals), full or partial, so revoking on it punished partial refunds, goodwill credits and won chargebacks. The fulfilment worker resolves the adjustment through `provider.sync_state()` → `reconcile()`. If a product treats a full refund as a cancellation, cancel the subscription too — the cancellation event is what revokes.

### Environment Isolation

- Sandbox and live are separate accounts with separate data and keys (`pdl_sdbx_…` / `pdl_live_…` API keys, `test_…` / `live_…` client tokens): `PADDLE_ENVIRONMENT`, `PADDLE_CLIENT_TOKEN`, `PADDLE_API_KEY`, `PADDLE_WEBHOOK_SECRET`. `PADDLE_ENVIRONMENT` is case-sensitive and refuses unknown values at startup.
- Before any deploy, run the lifecycle in sandbox: checkout, trial expiry, cancellation, upgrade, downgrade, refund.

---

## iyzico Integration (Turkish Domestic)

### When iyzico Applies

iyzico is the TRY **subscription** lane (§ Payment Providers — with the NON3D conflict and the missing merchant account stated there). A non-recurring iyzico Checkout Form is an ordinary 3-D Secure checkout; the Non3D exposure is exactly the recurring branch.

### Checkout Pattern

- Use the **iyzico Checkout Form** (hosted form, iframe or redirect) — `POST /v2/subscription/checkoutform/initialize` for a subscription. Never the raw-card `POST /v2/subscription/initialize`.
- No custom card forms.
- A recurring plan needs `IyzicoProvider(catalog=…, plan_refs={plan_id: pricingPlanReferenceCode}, buyer_resolver=…)` — both seams REFUSE (HTTP 400, constant body) rather than degrade to a one-off.
- **iyzico's pricing plan is the price of record** on this lane, and plans are near-immutable — a price change is a NEW plan. Run `await provider.verify_plan_refs()` at startup or in the deploy check (never per checkout): it is the only guard against the catalog and iyzico drifting apart. Provision plans once, admin-side, with `display_name=` (display text — `Plan.name` is an i18n key). Module README Gotchas.

### Webhook Security

- Webhooks are configured in the merchant panel (Settings → Merchant Settings → Merchant Notifications, HTTPS only). The first notification arrives 10–15 s after the attempt; iyzico resends every 15 minutes until it gets a 2xx and gives up after about three more tries (the TR and EN pages count them differently) — claim `iyzico-webhooks`.
- **Signature:** `X-IYZ-SIGNATURE-V3`, HMAC-SHA256 hex keyed with the secret key over a field concatenation that differs by event family (direct API, hosted form, subscription); V1/V2 are no longer supported. ⚠️ The header is only sent once webhook signing is ENABLED on the account (request it from iyzico). ⚠️ **The module's verifier implements the SUBSCRIPTION family only** (`subscription.order.success` / `.failure`): iyzico's direct-API and Checkout Form webhooks use different concatenations it does not verify — never point them at `/webhooks/iyzico` (every delivery 401s and reads as a bad secret). Never re-derive a formula the module does verify.
- **Confirm server-side, never from the payload alone:** after a subscription notification or checkout redirect, re-read the subscription's current status through `sync_state → reconcile` — the module has no subscription-checkout readback call (its `confirm_payment(token=…)` reads the one-off Checkout Form, a lane billing-model routing refuses for iyzico). There is no general refund webhook.
- Renewal webhooks for subscriptions go to a DIFFERENT URL from checkout callbacks, and their absence is silent (module README Gotchas).
- `IYZICO_API_KEY`, `IYZICO_SECRET_KEY`, `IYZICO_MERCHANT_ID` from the environment.

### Webhook Processing

- Same `(provider, event_id)` idempotency and deferred processing as Paddle.

### Environment Isolation

- `IYZICO_ENVIRONMENT` separates sandbox from live. The subscription engine is a PAID panel add-on (Eklentiler) — budget it before the sandbox run (claim `iyzico-subscription-non3d`).
- Run the full lifecycle in sandbox before production.

---

## PayTR Integration (Turkish Domestic One-Off)

- **3-D Secure iFrame only** (`PayTRProvider`, one-off; `portal_url` is 501 — PayTR has no hosted portal). Never the Direkt API's `non_3d`, never recurring payments: both need a Non3D permission, which the policy forbids.
- **Callback authentication:** `base64(HMAC-SHA256(merchant_key, merchant_oid + merchant_salt + status + total_amount))`, compared in constant time before trusting anything — skipping it is a direct money-loss path. Answer with the plain text **`OK`** and nothing else; without it PayTR treats the notification as failed and retries (about a minute later per its English docs), so duplicates arrive (claim `paytr-iframe-callback`). The module keys the event on `(paytr, <merchant_oid, casefolded>:<status>)` and the purchase on `(paytr, merchant_oid)` — keep your own records keyed consistently; a redelivery is answered `OK` without re-fulfilling.
- ⚠️ **PayTR eventually STOPS retrying and does not resume on its own** — someone must press *Duran Bildirimleri Yeniden Başlat* in the merchant panel. Name that operator duty; past a few hundred orders per window, detect drift from the panel's transaction report instead (module README Gotchas).
- ⚠️ PayTR's Turkish callback docs mark MORE fields authenticated than the English ones, and its English page carries the retry interval the Turkish one omits — read both languages for anything load-bearing.
- `PAYTR_TEST_MODE` (default `"1"`, a STRING concatenated into the token hash) keeps the store on test transactions until the operator switches it.
- `PAYTR_*` credentials are operator-provisioned process env: a missing key fails loud at the vendor boundary and is a BLOCKED escalation — never guessed, defaulted or hardcoded.

---

## Entitlement Model

- Entitlements are **webhook-derived, never client-asserted**, and decoupled from billing identity:
  - **`subscriptions`** — per `org_id`: provider, provider subscription id, `status`, `plan_id`, `current_period_end`;
  - **the plan catalog** (`plans` + features, the module's typed `Plan`/`PlanFeature`) — each `plan_id` maps feature keys to a numeric limit or a boolean.
- Authorization reads features BY KEY; **never** hardcode plan names (`if plan == "pro"` is banned). Pricing and packaging changes are data changes.
- The module maps `payment_failed` to grace even from `none` — a first declined payment entitles (open upstream, fabrik-lib D-133). YOUR fulfilment worker must run `sync_state → reconcile` before granting from `none`; grace is meant only for an already-entitled subscription. `canceled` → revoked; Paddle adjustments resolve through reconciliation (§ Refunds & Adjustments).
- **iyzico and PayTR refunds are issued outside the module** (panel or provider API) and emit no webhook it ingests: revoke from your own purchase/subscription record in the same act, and for an iyzico subscription re-read status through `sync_state → reconcile`.
- A **one-off purchase and a subscription cannot share one entitlement state** — features are exclusive, not additive, so folding a one-off into a subscriber's state silently revokes what they pay for. Key add-ons separately (module README Gotchas).

---

## Pricing Strategy

- Default to **flat-rate** or **tiered** pricing — boolean or integer entitlement checks.
- **Usage-based (metered) billing is banned** until the product is stable: it needs a highly available event-ingestion pipeline, which is not a solo operator's overhead to carry.

---

## Resilience

Paddle, iyzico and PayTR are external dependencies (`58-resilience.md`):

- **Checkout failures:** a provider the routing cannot serve is 409 and a seam refusal 400, both with constant bodies (the reason goes to logs); a routing or plan validation error is 400 and echoes its reason (it is the caller's own input); a provider rejection is 502 with a constant body — the frontend shows a clear error and a retry path on each; never leave the user in a broken state.
- **Webhook endpoints:** retries are the provider's; the endpoint must be idempotent, fast, and cap the body it reads (the module refuses oversized bodies with 413 before opening a database connection).
- **Portal-session and verification calls:** timeout + bounded retry; if Paddle's portal is down, say "billing portal temporarily unavailable".
- **If a provider cannot be reached to confirm a payment, do NOT grant the entitlement** — log, alert, and let reconciliation settle it.
- Every enabled provider has a row in `docs/RESILIENCE.md` §2a.

---

## Observability

Billing events are high-value — structured logs per `55-observability.md` (structlog in Python, pino in Node), never `print()`:

```python
logger.info("subscription_created",
    provider="paddle",
    event_type="subscription.created",
    subscription_id=sub_id,
    org_id=org_id,
    plan_id=plan_id,
    amount=amount,
    currency=currency,
)
```

- Log every webhook received (provider, event type, event id, outcome) and every entitlement change (the module's `audit.record_entitlement_change`).
- Card data never appears in a log: no PAN or CVV ever reaches these servers (hosted surfaces only).
- GlitchTip captures unhandled exceptions in webhook handlers.

---

## Tax Documentation (Turkish LLC / Teknokent)

<!-- Verify with your mali müşavir before treating as binding rules. -->

- **Paddle payouts:** Paddle is the Merchant of Record, so the buyer-facing tax is Paddle's. For the Teknokent _döviz beyanı_, export Paddle's monthly **reverse invoices** and **transactions reports** — they evidence the inflow as a software service export.
- **Service-export exemption** (KDV Kanunu md. 11/1-a) applies to services performed for a customer abroad AND used abroad (md. 12/2) — the second condition must be evidenced, not assumed (claim `kdv-rate-and-export-exemption`).
- **iyzico and PayTR payouts:** neither is a Merchant of Record — you are the merchant. Issue e-Arşiv invoices to each Turkish customer; domestic sales carry **20% KDV**.
- **Gross invoicing and platform commissions:** see `81-mobile-billing.md` § Teknokent Tax Treatment (KVK exemption, KDV 0%/20% split, KDV2 reverse charge, W-8BEN-E); the treatment is the same for SaaS payouts.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Stripe / LemonSqueezy / Braintree / a custom PSP | Paddle (international), iyzico (TRY subscription), PayTR (TRY one-off). Stripe is not available to a Turkish entity. |
| Hand-rolling provider adapters, webhook verifiers or entitlement logic | Vendor `fabrik-lib/payments` |
| One domestic lane as the other's fallback, or any silent re-route | Billing-model routing; a disabled provider raises (409) |
| Non3D on any lane (PayTR `non_3d` / recurring, iyzico raw-card subscription start) | 3-D Secure iFrame / Checkout Form; TRY recurring escalated as a planning decision |
| Inline Checkout or custom payment forms | Paddle Overlay Checkout / iyzico Checkout Form / PayTR iFrame |
| Custom billing-management UI | Paddle customer portal session, created per click |
| `request.json()` or a Pydantic model before signature verification | Raw `await request.body()` first |
| Signing the Paddle body alone | HMAC over `f"{ts}:{raw_body}"` |
| `==` for signature comparison | `hmac.compare_digest()` |
| A webhook host without NTP, or a widened Paddle tolerance to paper over drift | Fix the clock; keep the 5 s window |
| Revoking access on `adjustment.created` | Reconcile through `sync_state()`; cancellation revokes |
| Posting chargeback adjustments | Only `refund` and `credit` are yours to create |
| Heavy work inside the webhook request | Answer 200 within 3 s (Paddle's limit is 5 s); defer to the job queue |
| Provider API calls without a timeout | Timeout + bounded retry per `58-resilience.md` |
| Idempotency keyed on `event_id` alone | UNIQUE `(provider, event_id)` |
| Trusting an iyzico or PayTR callback payload | Signature/hash check + server-side confirmation |
| Anything but the literal `OK` in a PayTR callback response | Plain-text `OK` |
| One entitlement state for one-offs and subscriptions | Keyed separately |
| Hardcoded plan names (`if plan == "pro"`) | Feature lookup by key from the catalog |
| Usage-based / metered billing | Flat-rate or tiered |
| Webhook ingest through `fabrik_admin` or a `BYPASSRLS` role | `shape.needs_payments_ingest` → scoped `NOBYPASSRLS` ingest role |
| `print()` in billing code | Structured logs with provider, event_type, amount, currency |
| `localhost` in the DB connection | `postgres-main:5432` |

---

## Related Rule Packs

- `10-python.md` — FastAPI patterns, Pydantic Settings for API keys
- `20-typescript.md` — frontend Paddle.js integration (`@paddle/paddle-js`)
- `55-observability.md` — structured logging for billing events
- `58-resilience.md` — timeout/retry/breaker for provider calls
- `75-workers-jobs.md` — the job queue that takes deferred webhook processing
- `81-mobile-billing.md` — mobile IAP (a different model — RevenueCat, not this pack)
- `88-saas-launch-checklist.md` — SaaS launch gates including billing readiness
- `95-multi-tenant-saas.md` — `org_id` RLS and the payments-ingest role
- `00-domain-saas.md` — planning-level billing decisions (§4 architecture, §7 pricing)

---

## Done When

- [ ] PayTR stays disabled in production until the `purchases` write path is settled upstream (§ Payment Providers).
- [ ] `fabrik-lib/payments` vendored (package, schema + migrations, frontend) with a psycopg connection that has `conn.transaction()` and a `jobs` queue; `shape.needs_payments_ingest` set when webhooks write cross-tenant.
- [ ] Routing by billing model: international → Paddle, TRY one-off → PayTR, and TRY subscription → iyzico ONLY where `docs/DECISIONS.md` records the planning decision accepting iyzico's NON3D recurring charges (§ Payment Providers, the Non3D bullet); no provider falls back to another.
- [ ] No Non3D anywhere; any TRY recurring requirement is recorded as a planning decision in `docs/DECISIONS.md`, not coded around.
- [ ] Paddle Overlay Checkout; iyzico Checkout Form; PayTR 3-D Secure iFrame — no custom payment forms, no inline checkout.
- [ ] Subscription management through a Paddle customer-portal session created per click — no custom billing UI.
- [ ] Every webhook verified over raw bytes before parsing (Paddle `ts:body`, iyzico V3 subscription family enabled on the account, PayTR hash) with `hmac.compare_digest()`; NTP runs on every webhook host; the webhook `get_conn` is the ingest DSN and a boot query proves that role has neither `BYPASSRLS` nor superuser.
- [ ] Webhooks answer within 3 s; heavy processing deferred to the job queue; PayTR callbacks answer the literal `OK`, and someone owns restarting stopped PayTR notifications.
- [ ] `webhook_events` UNIQUE `(provider, event_id)`; verify + record + enqueue in one transaction.
- [ ] iyzico and PayTR results confirmed server-side before any entitlement is granted.
- [ ] Refunds via Paddle adjustments (`refund`/`credit` only); access revoked by cancellation or reconciliation, never by `adjustment.created`.
- [ ] If that iyzico decision exists: `plan_refs`/`buyer_resolver` wired and `verify_plan_refs()` in the deploy check.
- [ ] Entitlements webhook-derived and read by feature key; a fresh org is never granted on `payment_failed`; one-offs and subscriptions keyed separately; TRY-lane refunds revoke in the same act; no hardcoded plan names.
- [ ] All provider credentials from environment variables — `PADDLE_*`, `IYZICO_*`, `PAYTR_*` as real process env, never a project `.env`.
- [ ] Sandbox lifecycle tested (checkout, cancel, upgrade, downgrade, refund) on every enabled provider; once the PayTR blocker clears, its first live transaction treated as the real test.
- [ ] Every enabled provider has a row in `docs/RESILIENCE.md` §2a.
- [ ] Billing events logged as structured records with provider, event_type, subscription_id, amount, currency.
- [ ] Teknokent tax documentation: Paddle reverse invoices exported; iyzico/PayTR sales invoiced directly with KDV; export-exemption evidence kept.
