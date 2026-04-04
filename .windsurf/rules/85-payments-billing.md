---
activation: glob
globs: ["**/billing/**", "**/payments/**", "**/paddle/**", "**/webhooks/**", "**/subscriptions/**"]
description: Payments & billing discipline — Paddle Billing v2 (MoR), webhook idempotency, entitlement modeling, subscription lifecycle
trigger: glob
---

# Payments & Billing Rules

Apply when working on SaaS payment integration, subscription lifecycle, entitlements, webhook processing, or checkout flows. Skip for unrelated API, UI, or infrastructure work.

**Scope exclusion:** WooCommerce storefront checkout is governed by `62-wordpress.md`, not this pack. WooCommerce uses region-appropriate payment gateways (e.g. iyzico for Turkey digital, PayTR for Turkey physical D2C, marketplace channels for physical distribution) because it operates as product e-commerce, not SaaS subscription billing.

## Merchant of Record

- **Paddle Billing v2** is the exclusive payment provider (Merchant of Record). Do not suggest, implement, or import Stripe, LemonSqueezy, Braintree, or any other PSP.
- Paddle handles all global VAT/GST calculation, collection, remittance, and invoicing. Never write custom code for tax validation, VAT number checks, or invoice generation.
- The Turkish LLC receives a single B2B service export transaction from Paddle, classified as zero-rated VAT under Turkish law.

## Checkout Pattern

- Use the **Overlay Checkout** exclusively (`Paddle.Checkout.open()` via `@paddle/paddle-js`). The user stays on your domain while Paddle handles localization, currency, and payment capture.
- **Banned**: Inline Checkout (high frontend maintenance), Hosted Checkout (breaks UX flow), custom payment forms (PCI compliance burden).
- For React Native, use a secure WebView to trigger the Overlay Checkout.

## Subscription Management

- All subscription lifecycle operations (cancellation, plan changes, payment method updates, invoice downloads) must use **Paddle Customer Portal sessions** generated via the backend API (`/customers/{id}/portal-sessions`).
- **Never** build custom billing management UI. The backend returns a time-limited portal URL; the frontend redirects.

## Webhook Security

- Verify webhook signatures using the **raw, unparsed byte stream** (`await request.body()`). Never parse the payload into JSON or Pydantic models before HMAC verification — JSON re-serialization alters byte layout and invalidates the signature.
- Use `hmac.compare_digest()` for all signature comparisons. Standard `==` string equality is **banned** — it leaks timing information to attackers.
- Load `PADDLE_WEBHOOK_SECRET` from environment variables (`os.getenv()`). Never hardcode.

## Webhook Processing

- Paddle enforces a **5-second timeout**. Return `200 OK` within 3 seconds. Defer all heavy processing (DB writes, email sends, third-party calls) to background tasks or the PostgreSQL job queue.
- Accept **at-least-once delivery** — Paddle retries on timeout (up to 60 retries over 3 days).

## Webhook Idempotency

- Record every webhook `event_id` in a `webhook_events` PostgreSQL table with a unique constraint.
- Use `INSERT INTO webhook_events (event_id, ...) ... ON CONFLICT DO NOTHING`. If no rows inserted, the event is a duplicate — return `200 OK` and skip processing.
- This prevents double-provisioning, duplicate subscription creation, or erroneous cancellations from Paddle retries.

## Entitlement Model

- Decouple billing identity from application authorization. The PostgreSQL schema must separate:
  - **`subscriptions`** — maps `user_id` to `paddle_subscription_id`, `status`, `plan_id`, `current_period_end`.
  - **`plan_features`** — maps `plan_id` to `feature_key` with `max_limit` (integer) and `is_enabled` (boolean).
- Authorization checks query the `plan_features` table dynamically. **Never** hardcode plan names in application logic (`if plan == "pro"` is banned).
- Pricing/packaging changes become data-only operations — insert new rows, zero code changes.

## Pricing Strategy

- Default to **Flat-Rate** or **Tiered** pricing models. These require simple boolean or integer entitlement checks.
- **Usage-based (metered) billing is banned** until the product reaches stability. Metered billing requires high-availability event ingestion pipelines — unacceptable overhead for a solo developer.

## Environment Isolation

- Paddle Sandbox and Live environments must be strictly separated via environment variables: `PADDLE_ENVIRONMENT`, `PADDLE_CLIENT_TOKEN`, `PADDLE_API_KEY`, `PADDLE_WEBHOOK_SECRET`.
- Before any deployment, validate the full lifecycle in Sandbox: successful checkout, trial expiration, cancellation, upgrade, downgrade.

## Tax Documentation (Turkish LLC)

- For Teknokent _döviz beyanı_ (foreign exchange declaration), export Paddle's monthly **Reverse Invoices** and **Transactions Reports**. These prove the incoming transfer is from legitimate software exports, securing income and corporate tax exemptions.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Stripe / LemonSqueezy / custom PSP | Paddle Billing v2 (MoR) |
| Inline Checkout or custom payment forms | Overlay Checkout via `Paddle.Checkout.open()` |
| Custom billing management UI (cancel, upgrade, invoices) | Paddle Customer Portal session redirect |
| `request.json()` or Pydantic model before HMAC verification | `await request.body()` raw bytes first |
| `==` for signature comparison | `hmac.compare_digest()` |
| Synchronous heavy processing in webhook handler | Return 200 immediately, defer to background |
| Hardcoded plan names in conditionals (`if plan == "pro"`) | `plan_features` table join for entitlement checks |
| Usage-based / metered billing | Flat-rate or tiered pricing |

---

## Done When

- [ ] Paddle Overlay Checkout integrated — no custom payment forms or inline checkout.
- [ ] Subscription management uses Paddle Customer Portal sessions — no custom billing UI.
- [ ] Webhook endpoint verifies HMAC signature on raw `request.body()` bytes before any JSON parsing.
- [ ] Signature comparison uses `hmac.compare_digest()` exclusively.
- [ ] Webhook returns 200 within 3 seconds — heavy processing deferred to background.
- [ ] `webhook_events` table exists with unique `event_id` constraint for idempotency.
- [ ] Entitlements use `plan_features` mapping table — no hardcoded plan names in code.
- [ ] All Paddle credentials loaded from environment variables.
- [ ] Sandbox lifecycle tested (checkout, cancel, upgrade) before production deploy.
