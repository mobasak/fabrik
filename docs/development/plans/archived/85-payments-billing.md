# **Architecture Report: Paddle Billing Integration, Entitlement Modeling, and Compliance Strategy for Solo-Developer Operations**

## **1\. Executive Summary**

Architecting a globally available Software-as-a-Service (SaaS) platform under the strict constraints of a solo developer operating with approximately fifty focused hours per week necessitates ruthless prioritization. In this operational reality, time spent on non-core product features—such as global indirect tax compliance, invoice generation, payment gateway maintenance, and subscription state reconciliation—represents a critical misallocation of resources. The integration of payment infrastructure is not merely a technical decision but a profound operational and legal commitment. Comprehensive analysis of available paradigms indicates that adopting a Merchant of Record (MoR) model, specifically leveraging Paddle Billing v2, provides the optimal architectural and business pathway for the Fabrik stack. By acting as the legal reseller of the software, the MoR structurally absorbs the immense complexities of global regulatory compliance, shifting the burden of Value Added Tax (VAT), Goods and Services Tax (GST), and regional digital services taxes entirely away from the developer.1

For a corporate entity registered as a Turkish Limited Liability Company (LLC) operating within a Teknokent (technology development zone), the MoR framework dramatically simplifies the accounting and legal procedures required for cross-border service exports. Under standard Payment Service Provider (PSP) models, the developer must individually assess and remit taxes across dozens of jurisdictions. Conversely, the MoR model allows the Turkish LLC to engage in a singular Business-to-Business (B2B) transaction with Paddle.4 Paddle assumes full responsibility for determining end-user location, validating European VIES VAT numbers, applying reverse-charge logic where applicable, and remitting the correct indirect tax to foreign tax authorities.5 Consequently, the operational burden on the developer is reduced to downloading monthly "Reverse Invoices" and "Transactions Reports" provided by Paddle. These documents serve as the definitive proof of foreign currency inflow (döviz beyanı), which is legally mandated to maintain Teknokent corporate tax and income tax exemptions.4

Technically, the implementation within the predefined Fabrik ecosystem—utilizing an ARM64 Ubuntu Virtual Private Server (VPS) managed via Coolify, PostgreSQL 16, Python/FastAPI, and Next.js 14—must enforce strict decoupling between external billing identity and internal product entitlement. The architectural standard established herein demands the deliberate rejection of highly customized, state-heavy billing interfaces. The system must utilize Paddle's pre-built Overlay Checkout and Customer Portal APIs.9 This "off-the-shelf" strategy drastically reduces the surface area for logic errors, entirely eliminates Payment Card Industry (PCI) compliance overhead for the developer, and ensures the user interface remains modern without continuous frontend maintenance.12

The durability of this architecture relies fundamentally on robust, asynchronous webhook processing. Because Paddle functions as an external state machine, the Fabrik database must maintain an eventual consistency model driven by webhook events. The integration mandates strict cryptographic signature verification utilizing raw byte payloads, immediate HTTP 200 acknowledgments to satisfy strict five-second provider timeouts, and idempotent processing utilizing PostgreSQL 16 unique constraints. This design prevents catastrophic distributed systems failures, such as double-provisioning of resources or erroneous cancellation of active subscriptions.14

Should the platform eventually scale to a volume where the \~5% MoR fee exceeds the cost of hiring an internal finance and compliance team, a migration to a PSP like Stripe becomes viable. However, this migration pathway is strictly limited to Primary Account Number (PAN) data via PCI-compliant vault transfers; historical subscription state, invoice history, and localized tax logic cannot be programmatically migrated and must be manually rebuilt.18 Therefore, the current system architecture must be designed with an agnostic entitlement layer, ensuring that the application logic remains entirely insulated from the specific mechanics of the underlying payment provider.

## **Detailed Architectural Analysis**

To fully justify the canonical rules and execution handoffs that follow, it is necessary to explore the underlying mechanics, trade-offs, and implementation details of the billing architecture.

### **1.1 The Merchant of Record Paradigm vs. Payment Service Providers**

The fundamental divergence between Paddle and Stripe lies in the legal relationship between the buyer, the platform, and the payment processor. Stripe operates as a Payment Service Provider (PSP), providing the application programming interfaces (APIs) to move money, but leaving the legal burden of the sale on the developer. Paddle operates as a Merchant of Record (MoR), meaning Paddle legally purchases the software from the developer and immediately resells it to the end-user.

| Feature Area | Payment Service Provider (e.g., Stripe) | Merchant of Record (e.g., Paddle) |
| :---- | :---- | :---- |
| **Legal Seller** | The Developer (Fabrik / Turkish LLC). | The MoR (Paddle). |
| **Tax Compliance** | Developer must monitor thresholds, register for VAT/GST globally, and file returns in multiple countries.2 | MoR monitors thresholds, calculates, collects, and remits all global indirect taxes automatically.1 |
| **Invoicing & Receipts** | Developer generates invoices; must ensure legal compliance of document formatting per jurisdiction.13 | MoR generates and issues legally compliant tax invoices and receipts directly to the buyer.5 |
| **Customer Ownership** | Developer fully owns the customer relationship and data.2 | MoR legally owns the customer for the transaction. MoR name appears on bank statements.5 |
| **Dispute Management** | Developer handles chargebacks, provides evidence, and bears the financial liability and penalty fees.2 | MoR manages chargeback defense, though funds are still deducted if the dispute is lost. MoR absorbs some administrative overhead.22 |
| **Cost Structure** | Lower base transaction fee (typically 2.9% \+ $0.30), but significant hidden costs in tax software add-ons and accounting.12 | Higher flat rate (typically 5% \+ $0.50), providing an all-inclusive cost structure without hidden compliance fees.12 |

For a solo developer, the PSP model introduces an unacceptable level of operational drag. Even utilizing tools like Stripe Tax, the developer remains legally liable for registering with foreign tax authorities and filing returns once economic nexus thresholds are breached.2 The MoR model trades margin for velocity, allowing the developer to focus exclusively on product engineering.

### **1.2 Evaluation of Paddle Integration Patterns**

Paddle Billing v2 offers multiple pathways for integrating the checkout experience. Selecting the correct pattern is vital for minimizing frontend maintenance within the Next.js 14 and React Native environments.

| Integration Pattern | Mechanism | Maintenance Burden | Recommendation for Solo Developer |
| :---- | :---- | :---- | :---- |
| **Hosted Checkout** | Redirects the user entirely away from the application to a Paddle-hosted checkout.paddle.com URL. | Very Low. Requires almost no frontend state management.24 | **Avoid.** While maintenance is low, it breaks the user experience flow and requires complex redirect handling upon success. |
| **Overlay Checkout** | Injects an iframe over the application utilizing Paddle.js. The user remains on the application domain.9 | Low. Requires basic initialization of Paddle.Environment and opening the checkout via Javascript.9 | **Primary Choice.** Provides a seamless, localized checkout experience with minimal engineering effort. Ideal for web and Chrome extensions.10 |
| **Inline Checkout** | Embeds the checkout form directly into a designated DOM element within the application.10 | High. Demands deep integration with React state, responsive design handling, and CSS container management.10 | **Avoid.** The marginal gain in visual consistency does not justify the significant increase in frontend complexity and maintenance.12 |

The architectural standard mandates the use of the **Overlay Checkout**. By passing a priceId to Paddle.Checkout.open(), the application offloads all localization, currency conversion, tax identification, and payment capture logic to Paddle's optimized infrastructure.9 For the React Native mobile application, utilizing a secure web view to trigger the Overlay Checkout remains the most durable approach, avoiding the complexities of native SDK bridging unless mandated by App Store guidelines.

### **1.3 Subscription Lifecycle and State Management**

Managing the lifecycle of a SaaS subscription involves tracking trials, upgrades, downgrades, pauses, and cancellations. Attempting to build a custom frontend to handle these state changes introduces massive complexity regarding proration calculations, grandfathered pricing, and term-end synchronization.

To maintain a low-ops posture, Fabrik must leverage the Paddle Customer Portal. Instead of building custom React components for billing management, the FastAPI backend must utilize the Paddle API to generate authenticated Customer Portal sessions.

When a user requests to modify their subscription, the flow must operate as follows:

1. The Next.js frontend sends a POST request to the FastAPI backend (e.g., /api/billing/portal).27
2. The backend retrieves the user's paddle\_customer\_id from the PostgreSQL database.
3. The backend makes a server-to-server POST request to Paddle's /customers/{customer\_id}/portal-sessions endpoint.11
4. Paddle returns a secure, time-limited URL.
5. The backend returns this URL to the frontend, which redirects the user.

This pattern entirely eliminates the need to build, test, and maintain complex user interfaces for payment method updates, invoice downloads, or cancellation surveys.11

### **1.4 The Entitlement Model: Decoupling Identity from Billing**

A common anti-pattern in SaaS development is tightly coupling application logic to specific billing plans. Code blocks containing logic such as if user.plan \== 'pro': render\_feature() are inherently fragile. If the business introduces a new 'Enterprise' tier or changes the name of the 'Pro' plan, the application code must be refactored and redeployed across the entire stack.

A durable architecture requires an Entitlement Management System. This system evaluates what an account is allowed to perform based on database mappings rather than hardcoded identities.30 The PostgreSQL 16 schema must separate subscriptions from entitlements.

| Component | Purpose | Database Representation |
| :---- | :---- | :---- |
| **Subscription State** | Tracks the financial relationship with Paddle (Active, Past Due, Canceled, Trialing).31 | subscriptions table containing paddle\_subscription\_id, status, and current\_period\_end. |
| **Plan Mapping** | Defines what features belong to which commercial plan.30 | plan\_features table mapping plan\_id to a feature\_key with integer limits. |
| **Runtime Enforcement** | Determines if the current user can execute an action.30 | A database query joining the active subscription to the plan\_features table to return boolean access or integer limits.32 |

By implementing this schema, pricing and packaging changes become data-only operations. A solo developer can introduce a new pricing tier simply by inserting new rows into the plan\_features table, requiring zero changes to the Next.js or FastAPI codebases.32

### **1.5 Webhook Processing, Idempotency, and Security**

Webhooks form the central nervous system of the billing integration. Paddle pushes events (e.g., subscription.created, transaction.completed) to the FastAPI backend to notify the system of state changes. Because webhooks operate over the public internet, they are subject to delays, out-of-order delivery, duplicated messages, and malicious spoofing attempts.14

#### **1.5.1 Cryptographic Signature Verification**

To ensure a webhook legitimately originated from Paddle, the payload must be cryptographically verified using a Hash-Based Message Authentication Code (HMAC). Paddle generates signatures using SHA-256.33 The most critical security failure in modern web frameworks involves payload parsing prior to verification. Frameworks like FastAPI automatically consume the request body and parse it into JSON. If this JSON is re-serialized into a string to compute the hash, subtle changes in spacing, unicode encoding, or key ordering will alter the byte layout, causing the signature verification to fail.16

The implementation must extract the raw, unparsed byte stream using await request.body(). The mathematical computation follows the standard HMAC construct:

![][image1]
Where ![][image2] is the secret key, ![][image3] is the concatenation of the timestamp and the raw payload, and ![][image4] is the SHA-256 hashing function.16 Furthermore, to prevent timing attacks where an adversary deduces the valid signature based on the microsecond response time of the endpoint, the comparison must exclusively utilize hmac.compare\_digest() rather than standard string equality operators.16

#### **1.5.2 Idempotency and Timeouts**

Paddle expects a successful HTTP response (2xx) within a strict five-second window.14 If the FastAPI backend attempts to execute synchronous database operations, provision third-party resources, or send welcome emails within the webhook request cycle, it risks exceeding this timeout. Upon timeout, Paddle assumes delivery failure and initiates an exponential backoff retry schedule (up to 60 retries over 3 days in the live environment).14

To prevent timeout loops and the resulting duplicate processing (e.g., granting a user two separate subscriptions for a single checkout), the system must implement the fetch-before-process pattern with robust idempotency.14

1. Extract the event\_id from the webhook payload.
2. Attempt to insert the event\_id into a PostgreSQL webhook\_events table using an atomic INSERT... ON CONFLICT DO NOTHING statement.15
3. If the insertion returns no rows (indicating the event was already received), immediately return a 200 OK.
4. If the insertion is successful, dispatch the payload to a background task (e.g., FastAPI BackgroundTasks or a Celery queue) and immediately return a 200 OK to Paddle.35

### **1.6 Price Modeling Strategies**

Selecting the correct monetization model impacts both revenue trajectory and engineering complexity. Solo developers must optimize for models that require the least amount of infrastructure to monitor and bill.

| Pricing Model | Definition | Engineering Complexity | Recommendation |
| :---- | :---- | :---- | :---- |
| **Flat-Rate** | A single fixed price for unlimited access to the product.36 | Very Low. Requires simple boolean entitlement checks. | **Highly Recommended.** Ideal for initial launch phases due to predictable revenue and zero metering overhead.38 |
| **Tiered Pricing** | Multiple fixed price points (e.g., Basic, Pro, Enterprise) unlocking different features.39 | Low. Requires the plan\_features database mapping schema.30 | **Highly Recommended.** Provides upselling pathways while maintaining predictable billing cycles. |
| **Per-Seat** | Billing scales linearly based on the number of users within an organization.39 | Medium. Requires organizational grouping in the database and proration logic when adding/removing seats mid-cycle. | **Acceptable.** Suitable for B2B tools, provided Paddle's subscription update APIs are utilized to handle proration automatically. |
| **Usage-Based (Metered)** | Billing is purely variable based on consumption (e.g., per API call, per GB of storage).40 | Very High. Requires highly available, high-throughput event ingestion pipelines to prevent dropped usage events.36 | **Strictly Banned.** The engineering overhead of building reliable metering and handling unpredictable billing disputes is unmanageable for a solo developer.38 |

### **1.7 Taxation, Compliance, and Turkish LLC Accounting**

Operating as a Turkish Limited Liability Company within a Teknokent provides substantial tax benefits, provided strict regulatory reporting procedures are followed. The interaction between the Turkish legal entity and the UK/US-based Merchant of Record requires careful accounting.

According to Turkish Value Added Tax Law No. 3065, Article 11/1-a, services provided to customers residing abroad and utilized abroad are classified as "service exports" and are exempt from Turkish VAT (0% rate).41 In the MoR paradigm, the Turkish LLC does not sell directly to the global end-user; rather, it sells the software license to Paddle. Because Paddle is a foreign entity, this transaction qualifies as a B2B service export, exempt from local VAT.

Paddle assumes the liability for assessing the end-user's location and collecting the appropriate local VAT (e.g., 20% in the UK, 21% in Spain).6 The funds collected by Paddle, minus their fee and the remitted taxes, are accumulated as a balance.

When Paddle issues a monthly payout to the Turkish LLC's USD or EUR International Bank Account Number (IBAN), they simultaneously generate a "Reverse Invoice".8 This document serves as a self-billed invoice from the developer to Paddle. For Teknokent compliance, the developer must submit this Reverse Invoice alongside the "Transactions Report" (which details the gross sales, taxes withheld, and fees) to their Turkish accountant.7 These documents constitute the mandatory *döviz beyanı* (foreign exchange declaration), proving that the incoming SWIFT or Wise transfer originates from legitimate software exports, thereby securing the applicable income and corporate tax exemptions.

### **1.8 Testing and Migration Pathways**

Testing the billing integration requires isolating development environments. Paddle provides a comprehensive Sandbox environment. The architectural standard dictates strict separation utilizing environment variables (PADDLE\_ENVIRONMENT=sandbox, PADDLE\_CLIENT\_TOKEN, PADDLE\_API\_KEY, PADDLE\_WEBHOOK\_SECRET).26 Before any deployment, the complete lifecycle must be simulated in the Sandbox, including successful checkout, trial expiration, scheduled cancellation, and immediate upgrade.25

A common strategic concern is the migration path away from Paddle if the company scales to a point where establishing foreign entities and internal finance teams becomes cost-effective. A migration from an MoR to a PSP like Stripe is highly restricted. While Stripe's Data Migrations team can perform a secure, PCI-compliant transfer of Primary Account Numbers (PANs) and credit card tokens, the business logic cannot be exported.18 The migration process entails exporting an encrypted JSON mapping file of card details; however, active subscriptions, historical invoices, local tax configurations, and dispute histories remain locked within the Paddle ecosystem.19 Consequently, any future migration requires a hard cutover, necessitating the manual reconstruction of subscription states in the new provider. This reality reinforces the necessity of the decoupled PostgreSQL entitlement schema; the application database must serve as the single source of truth for user capabilities, remaining entirely agnostic to the external billing provider.

## ---

**2\. Canonical Rules for this Rule File**

The following directives constitute the immutable technical and operational constraints for all payment and billing implementations within the Fabrik ecosystem.

* **MoR Exclusivity:** All global payment processing, tax calculation, invoicing, and compliance must be delegated to Paddle Billing v2. The system must never calculate local VAT or generate customer tax invoices directly.
* **Checkout Pattern:** Implementation must exclusively utilize the Paddle Overlay Checkout via Paddle.js. Inline or custom-hosted checkouts are prohibited due to higher maintenance overhead and state synchronization complexities.
* **Customer Management:** All subscription lifecycle modifications (cancellations, payment method updates, invoice history retrieval) must be routed through authenticated Paddle Customer Portal sessions. Custom account management UI for billing is strictly forbidden.
* **Webhook Verification:** Webhook signatures must be cryptographically verified in FastAPI using the unparsed, raw byte stream (request.body()). Parsing the payload into JSON before verification is a critical security vulnerability and will result in HMAC validation failures.
* **Cryptographic Timing Security:** Signature comparisons must exclusively utilize hmac.compare\_digest() to prevent timing attacks. Standard string equality operators (==) are banned.
* **Asynchronous Processing:** Webhook endpoints must acknowledge receipt (200 OK) within 3 seconds to avoid Paddle's 5-second timeout and subsequent exponential backoff retries. Heavy processing must be deferred to background tasks or message queues.
* **Idempotency Enforcement:** Every webhook event must be checked against a webhook\_events PostgreSQL table using the unique event\_id. Duplicate events must be discarded gracefully while still returning a 200 OK status.
* **Entitlement Decoupling:** The PostgreSQL schema must isolate users, subscriptions, and entitlements. Authorization checks must query an entitlements or plan\_features mapping table, never hardcoding plan names (e.g., if plan \== "pro") in the application logic.
* **Pricing Simplicity:** The initial monetization strategy must employ a Flat-Rate or Tiered pricing model. Usage-based (metered) billing is prohibited until the core product reaches absolute stability, due to the high engineering cost of reliable event metering.
* **Environment Parity:** Paddle Sandbox and Live environments must be isolated using strict environment variable separation. Sandbox testing must validate the full lifecycle (upgrade, downgrade, cancellation) prior to any deployment.
* **Tax Documentation:** For Turkish LLC accounting, the system must export Paddle's monthly "Reverse Invoices" and "Transactions Reports" to satisfy Teknokent *döviz beyanı* (foreign exchange declaration) requirements, classifying the revenue as a zero-rated service export.
* **Base Image Consistency:** All microservices handling billing must utilize slim-bookworm Debian images. Alpine Linux is strictly banned due to musl libc compatibility issues with standard Python cryptography compilation.

## **3\. Anti-Patterns / Banned Patterns**

The adherence to a low-ops philosophy requires the explicit identification and prohibition of practices that generate technical debt, increase latency, or create compliance liabilities.

* **The JSON Parsing Trap:** The most prevalent failure mode in payment integrations occurs during webhook signature verification. Frameworks like FastAPI automatically consume and parse request bodies if Pydantic models are injected into the route definition. If the request body is serialized back to a string for HMAC computation, the byte layout changes, resulting in an invalid signature. **Banned:** Utilizing request.json() or Pydantic models prior to passing the raw await request.body() to the cryptographic verification function.
* **Hardcoded Plan Logic:** Embedding subscription tiers directly into application code creates fragile access control. Statements such as if user.plan \== 'Pro': grant\_access() require a complete deployment cycle to introduce a new pricing tier or a legacy grandfathered plan. **Banned:** Plan-based conditional logic in application code. The system must evaluate entitlements via database joins.
* **Synchronous Webhook State Mutations:** Executing database transactions, provisioning third-party resources, and sending welcome emails synchronously within the webhook HTTP request lifecycle guarantees timeout failures under load. **Banned:** Processing complex business logic before returning the HTTP 200 acknowledgment.
* **Custom Cancellation Flows:** Building custom user interfaces to handle subscription pauses, downgrades, or cancellations requires complex API orchestrations and state synchronizations. **Banned:** Developing custom billing management UI. All billing modifications must redirect the user to a Paddle-generated Customer Portal session URL.
* **Custom VAT Validation:** Attempting to validate European VIES VAT numbers or applying reverse-charge logic manually negates the primary benefit of the MoR model. **Banned:** Collecting or validating tax identification numbers within the Fabrik frontend. Paddle Checkout must handle all tax compliance.

## **4\. What to Enforce in Execute Handoffs**

When AI agents operating within the Fabrik environment transition between frontend, backend, and infrastructure tasks, they must enforce strict state contracts regarding billing implementation.

* **Frontend to Backend Handoff:** When the Next.js frontend team requests subscription data from the FastAPI backend, the handoff must dictate that the backend only returns a boolean entitlement matrix or an opaque Customer Portal URL. The frontend agent must not be handed raw Paddle API keys or subscription payload IDs. The contract must specify: "Backend provides /api/billing/portal which returns { "url": "https://..." }. Frontend implements a simple redirect."
* **Backend to Database Handoff:** When generating PostgreSQL schemas for subscription tracking, the execution handoff must enforce the creation of a normalized structure. The database agent must receive instructions to implement a webhook\_events table for idempotency with a primary key on the Paddle event\_id, a subscriptions table linked to the core users table, and an entitlements schema mapping integer-based limits to the active subscription.
* **Testing Handoff:** Any execution block that implements billing endpoints must conclude with a handoff to the testing framework. The testing agent must be instructed to simulate Paddle webhooks by generating a local HMAC-SHA256 signature using a test secret, appending it to a mock header, and asserting that the backend successfully parses the components without raising 403 Forbidden errors.

## **5\. What to Verify in final\_gate.py**

The final\_gate.py continuous integration script must enforce the durability and security of the billing infrastructure through static analysis (AST) and regex validations.

| Check Category | Verification Mechanism | Rationale |
| :---- | :---- | :---- |
| **Cryptography Security** | AST check ensuring hmac.compare\_digest is used for all signature verification logic involving Paddle secrets. | Prevents timing attacks where an attacker can guess the HMAC signature based on response times. |
| **Raw Body Integrity** | Regex check: await request\\.body\\(\\) must exist in the FastAPI webhook route or middleware. | Ensures the unmodified byte stream is used for HMAC verification. |
| **Timeout Prevention** | AST check: Webhook endpoints must delegate processing to BackgroundTasks or an external queue, avoiding await db\_commit() before return Response(). | Adheres to Paddle's 5-second timeout constraint to prevent retry loops. |
| **Base Image Compliance** | Regex check on Dockerfile: FROM.\*slim-bookworm must be present. alpine raises a fatal error. | Guarantees compatibility with pre-compiled Python wheels for cryptography libraries. |
| **Secret Management** | Abstract Syntax Tree scan to ensure PADDLE\_WEBHOOK\_SECRET and PADDLE\_API\_KEY are read strictly from os.getenv() or pydantic-settings and never hardcoded. | Prevents catastrophic credential leakage. |

## **6\. What belongs in AGENTS.md / AGENTS-compact.md**

To ensure AI agents consistently output compliant code, the system instructions must be augmented with the following billing-specific constraints.

**For AGENTS.md (Verbose Context):**

You are a senior software architect managing a high-leverage solo-developer stack. Your priority is to minimize future maintenance. Paddle Billing v2 is our exclusive Merchant of Record. Do not suggest Stripe, LemonSqueezy, or custom Braintree implementations. Do not write code to calculate VAT or manage tax receipts. Entitlements must be mapped dynamically in PostgreSQL. Assume a user has an active plan, but verify their capability through an entitlements table mapping. Use atomic transactions (ON CONFLICT DO NOTHING) for webhook idempotency to prevent race conditions. Never build custom UI for subscription cancellation, payment method updates, or invoice downloads. Always utilize the Paddle API to generate a Customer Portal Session and redirect the user. Use the Overlay Checkout (Paddle.Checkout.open()) via Next.js client components.

**For AGENTS-compact.md (Token-Optimized Rules):**

BILLING: Exclusively Paddle v2 MoR. Use Overlay Checkout & Customer Portal API (no custom billing UI). Webhooks: verify via raw await request.body(), hmac.compare\_digest, return 200 instantly, process async. Idempotency enforced via Postgres event\_id PK. Entitlements DB-mapped, never hardcoded in app. Images: slim-bookworm only.

## **7\. Minimal Practical Examples for Fabrik Stack**

The following implementations demonstrate the required patterns for integrating Paddle within the Fabrik constraints.

### **7.1 PostgreSQL 16 Entitlement and Idempotency Schema**

The database must decouple the user identity from the billing lifecycle, allowing for seamless upgrades and historical tracking.

SQL

\-- Idempotency tracking to prevent webhook replay/duplicate processing
CREATE TABLE webhook\_events (
    event\_id VARCHAR(255) PRIMARY KEY,
    event\_type VARCHAR(100) NOT NULL,
    occurred\_at TIMESTAMPTZ NOT NULL,
    processed\_at TIMESTAMPTZ DEFAULT NOW()
);

\-- Core subscription state tracking
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen\_random\_uuid(),
    user\_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    paddle\_customer\_id VARCHAR(255) NOT NULL,
    paddle\_subscription\_id VARCHAR(255) UNIQUE,
    status VARCHAR(50) NOT NULL, \-- 'active', 'past\_due', 'paused', 'canceled'
    plan\_id VARCHAR(100) NOT NULL,
    current\_period\_end TIMESTAMPTZ NOT NULL,
    updated\_at TIMESTAMPTZ DEFAULT NOW()
);

\-- Entitlement mapping (Decouples plan names from application logic)
CREATE TABLE plan\_features (
    plan\_id VARCHAR(100) NOT NULL,
    feature\_key VARCHAR(100) NOT NULL,
    max\_limit INTEGER, \-- NULL implies unlimited
    is\_enabled BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (plan\_id, feature\_key)
);

### **7.2 FastAPI Webhook Signature Verification and Idempotency**

The webhook handler must mathematically verify the HMAC signature utilizing the raw request body, instantly return a 200 OK, and dispatch processing to a background task.

Python

import hmac
import hashlib
import json
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, status

router \= APIRouter()
PADDLE\_WEBHOOK\_SECRET \= "pdl\_ntfset\_..." \# Loaded securely via environment variables

def verify\_paddle\_signature(signature\_header: str, raw\_body: bytes, secret: str) \-\> bool:
    """Cryptographically verifies the Paddle webhook signature to prevent spoofing."""
    try:
        parts \= dict(item.split("=") for item in signature\_header.split(";"))
        ts \= parts.get("ts")
        h1 \= parts.get("h1")
        if not ts or not h1:
            return False

        payload \= f"{ts}:{raw\_body.decode('utf-8')}".encode("utf-8")
        expected\_hmac \= hmac.new(
            secret.encode("utf-8"),
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()

        \# MUST use compare\_digest to prevent timing attacks
        return hmac.compare\_digest(expected\_hmac, h1)
    except Exception:
        return False

async def process\_event\_async(event\_id: str, payload: dict):
    """Background task to process the event, enforcing database idempotency."""
    \# Execute atomic insertion:
    \# INSERT INTO webhook\_events (event\_id, event\_type, occurred\_at)
    \# VALUES (...) ON CONFLICT DO NOTHING RETURNING event\_id
    \# If row is successfully inserted, parse payload and update 'subscriptions' table.
    pass

@router.post("/webhooks/paddle")
async def paddle\_webhook(request: Request, background\_tasks: BackgroundTasks):
    signature \= request.headers.get("Paddle-Signature")
    if not signature:
        raise HTTPException(status\_code=401, detail="Missing signature")

    \# CRITICAL: Extract raw body before any JSON parsing occurs in the framework
    raw\_body \= await request.body()

    if not verify\_paddle\_signature(signature, raw\_body, PADDLE\_WEBHOOK\_SECRET):
        raise HTTPException(status\_code=403, detail="Invalid signature")

    \# Safe to parse JSON only after cryptographic validation has succeeded
    payload \= json.loads(raw\_body)
    event\_id \= payload.get("event\_id")

    \# Defer heavy database I/O to background task to satisfy Paddle's 5-second timeout
    background\_tasks.add\_task(process\_event\_async, event\_id, payload)

    return {"status": "accepted"}

### **7.3 Next.js 14 Checkout Overlay and Customer Portal**

The frontend integration prioritizes minimal state management by utilizing Paddle.js for the overlay and a backend API route to generate Customer Portal sessions.

TypeScript

// app/components/CheckoutButton.tsx
'use client';
import { initializePaddle, Paddle } from '@paddle/paddle-js';
import { useEffect, useState } from 'react';

export default function CheckoutButton({ priceId }: { priceId: string }) {
  const \[paddle, setPaddle\] \= useState\<Paddle | undefined\>();

  useEffect(() \=\> {
    // Isolate Sandbox and Production environments securely
    initializePaddle({ environment: 'sandbox', token: process.env.NEXT\_PUBLIC\_PADDLE\_CLIENT\_TOKEN })
     .then((paddleInstance) \=\> setPaddle(paddleInstance));
  },);

  const openCheckout \= () \=\> {
    paddle?.Checkout.open({
      items: \[{ priceId: priceId, quantity: 1 }\],
      settings: { displayMode: 'overlay' } // Strict enforcement of the Overlay pattern
    });
  };

  return \<button onClick={openCheckout}\>Upgrade to Pro\</button\>;
}

## **8\. Recommended Final Content for 85-payments-billing.md**

The following section provides the exact markdown content to be saved as the permanent rule file 85-payments-billing.md.

# ---

**85-payments-billing.md: Fabrik Payments and Entitlement Architecture**

This rule file governs all payment integration, subscription lifecycle management, and entitlement authorization within the Fabrik ecosystem. Due to solo-developer operational constraints, all billing logic heavily indexes on low-maintenance, off-the-shelf Merchant of Record (MoR) capabilities.

## **1\. Core Paradigm: MoR Exclusivity**

* **Paddle Billing v2** is the exclusive Merchant of Record.
* **Tax and VAT:** Never write custom code to validate European VAT numbers, apply reverse-charge logic, or generate tax-compliant invoices. Paddle handles global indirect tax liabilities and remits them to respective jurisdictions.
* **Turkish LLC Compliance:** For Teknokent *döviz beyanı* (export of service proof), rely on Paddle's automated monthly "Reverse Invoices" and "Transactions Reports". Revenue is classified as a B2B service export to Paddle.

## **2\. Integration Patterns**

* **Checkout:** Use the **Overlay Checkout** (Paddle.Checkout.open()) initialized via @paddle/paddle-js on the client side. Avoid inline or custom-hosted checkouts to minimize UI state synchronization.
* **Customer Management:** Never build custom UI for cancellations, plan downgrades, or invoice downloads. Always generate a Paddle Customer Portal Session via the Paddle backend API and redirect the user.
* **Pricing Model:** Default to Flat-Rate or simple Tiered pricing. Avoid metered/usage-based pricing to prevent the engineering overhead of building distributed, reliable event-aggregation pipelines.

## **3\. Webhook Security and State Management**

Paddle webhooks dictate the definitive state of the system. Their processing must be flawless.

* **Cryptographic Validation:** Signatures MUST be verified using the raw, unparsed byte stream (await request.body()). Never use request.json() or Pydantic models before validation; JSON serialization alters the byte layout and invalidates the HMAC.
* **Timing Attack Prevention:** Signature string comparisons must exclusively utilize hmac.compare\_digest().
* **Timeouts:** Paddle enforces a strict 5-second timeout. Webhook endpoints must return a 200 OK almost instantly. All heavy database I/O, email dispatching, or third-party API calls must be deferred to BackgroundTasks or a Celery/Redis queue.
* **Idempotency:** A PostgreSQL webhook\_events table must record every event\_id. Use INSERT... ON CONFLICT DO NOTHING to gracefully discard duplicate events generated by Paddle's retry mechanisms.

## **4\. PostgreSQL Entitlement Schema**

Billing identity must be decoupled from user authorization.

* **Subscriptions Table:** Map users.id to paddle\_customer\_id and paddle\_subscription\_id. Track the status enum (active, past\_due, canceled).
* **Entitlements Table:** Never hardcode plan conditionals (e.g., if user.plan \== "pro"). Use a plan\_features mapping table to define integer limits or boolean capabilities (e.g., max\_projects: 10). The application logic queries these limits dynamically.

## **5\. Stripe Migration Acknowledgment**

While Stripe offers lower baseline processing fees, it requires massive engineering overhead for global tax compliance. If a migration from Paddle to Stripe occurs in the future, it is restricted by data portability limits.

* **Data Transfer:** Only Primary Account Numbers (PAN / Credit Card Tokens) can be securely migrated via PCI-compliant vault transfers.
* **State Loss:** Subscription logic, invoice history, and localized tax configurations do not transfer. Do not architect the current system assuming seamless data portability to a Payment Service Provider.

## **6\. Docker and Infrastructure Constraints**

* **Base Images:** All Python microservices utilizing cryptographic libraries for webhook verification must use slim-bookworm. alpine is banned due to musl libc compilation failures with standard cryptography wheels.
* **Environment Isolation:** Ensure strict physical separation between Paddle Sandbox (test\_... tokens) and Live environments.

## **7\. Banned Anti-Patterns**

1. **Parsing JSON before HMAC verification.**
2. **Synchronous provisioning inside the webhook request/response cycle.**
3. **Building custom cancellation screens.**
4. **Hardcoding product tier names in access control logic.**

#### **Works cited**

1. How Paddle is able to take on your VAT and tax responsibilities \- Help Center, accessed March 31, 2026, [https://www.paddle.com/help/start/intro-to-paddle/how-paddle-is-able-to-take-on-your-vat-and-tax-responsibilities](https://www.paddle.com/help/start/intro-to-paddle/how-paddle-is-able-to-take-on-your-vat-and-tax-responsibilities)
2. Paddle vs Stripe: Which Payment Platform Is Right for Your SaaS?, accessed March 31, 2026, [https://dodopayments.com/blogs/paddle-vs-stripe](https://dodopayments.com/blogs/paddle-vs-stripe)
3. Paddle vs. Stripe: The Ultimate 2026 Comparison | UniBee, accessed March 31, 2026, [https://unibee.dev/blog/paddle-vs-stripe-the-ultimate-comparison/](https://unibee.dev/blog/paddle-vs-stripe-the-ultimate-comparison/)
4. How Paddle handles VAT on your behalf \- Help Center, accessed March 31, 2026, [https://www.paddle.com/help/sell/tax/how-paddle-handles-vat-on-your-behalf](https://www.paddle.com/help/sell/tax/how-paddle-handles-vat-on-your-behalf)
5. Understanding VAT, invoices, and Paddle billing \- Usermaven, accessed March 31, 2026, [https://usermaven.com/docs/account-settings/vat-and-invoices](https://usermaven.com/docs/account-settings/vat-and-invoices)
6. Turkish VAT on e-services \- Avalara, accessed March 31, 2026, [https://www.avalara.com/us/en/vatlive/country-guides/asia/turkey/turkish-vat-electronic-services.html](https://www.avalara.com/us/en/vatlive/country-guides/asia/turkey/turkish-vat-electronic-services.html)
7. An Insight into the Transactions Report \- Help Center \- Paddle, accessed March 31, 2026, [https://www.paddle.com/help/manage/reporting/a-comprehensive-insight-into-the-transactions-report](https://www.paddle.com/help/manage/reporting/a-comprehensive-insight-into-the-transactions-report)
8. What statements will I receive? \- Help Center \- Paddle, accessed March 31, 2026, [https://www.paddle.com/help/manage/get-paid/what-statements-will-i-receive](https://www.paddle.com/help/manage/get-paid/what-statements-will-i-receive)
9. Using overlay checkout in Paddle and configuring webhook for one time payments \- Medium, accessed March 31, 2026, [https://medium.com/@girish1729/using-overlay-checkout-in-paddle-and-configuring-webhook-for-one-time-payments-3ea02f099624](https://medium.com/@girish1729/using-overlay-checkout-in-paddle-and-configuring-webhook-for-one-time-payments-3ea02f099624)
10. Build an overlay checkout \- Paddle Developer, accessed March 31, 2026, [https://developer.paddle.com/build/checkout/build-overlay-checkout](https://developer.paddle.com/build/checkout/build-overlay-checkout)
11. Use customer portal links in your app \- Paddle Developer, accessed March 31, 2026, [https://developer.paddle.com/build/customers/integrate-customer-portal](https://developer.paddle.com/build/customers/integrate-customer-portal)
12. Stripe vs Paddle: Fees, Tax Handling & MoR Compared \- DesignRevision, accessed March 31, 2026, [https://designrevision.com/blog/stripe-vs-paddle](https://designrevision.com/blog/stripe-vs-paddle)
13. Paddle vs Stripe Billing 2024: Complete Comparison Guide for SaaS | Flowjam, accessed March 31, 2026, [https://www.flowjam.com/blog/paddle-vs-stripe-billing-2024-complete-comparison-guide-for-saas](https://www.flowjam.com/blog/paddle-vs-stripe-billing-2024-complete-comparison-guide-for-saas)
14. Guide to Paddle Webhooks: Features and Best Practices \- Hookdeck, accessed March 31, 2026, [https://hookdeck.com/webhooks/platforms/guide-to-paddle-webhooks-features-and-best-practices](https://hookdeck.com/webhooks/platforms/guide-to-paddle-webhooks-features-and-best-practices)
15. webhook-handler-patterns | Skills Ma... \- LobeHub, accessed March 31, 2026, [https://lobehub.com/skills/neversight-learn-skills.dev-webhook-handler-patterns](https://lobehub.com/skills/neversight-learn-skills.dev-webhook-handler-patterns)
16. Verify Paddle Billing Webhook Signatures in Python | Josh Karamuth, accessed March 31, 2026, [https://joshkaramuth.com/blog/verify-paddle-billing-webhooks-python/](https://joshkaramuth.com/blog/verify-paddle-billing-webhooks-python/)
17. Receive Webhooks with Python (FastAPI) \- Svix, accessed March 31, 2026, [https://www.svix.com/guides/receiving/receive-webhooks-with-python-fastapi/](https://www.svix.com/guides/receiving/receive-webhooks-with-python-fastapi/)
18. Five steps to accelerate your data migration to Stripe, accessed March 31, 2026, [https://stripe.com/se/guides/five-steps-to-accelerate-your-data-migration-to-stripe](https://stripe.com/se/guides/five-steps-to-accelerate-your-data-migration-to-stripe)
19. Overview | Stripe Documentation, accessed March 31, 2026, [https://docs.stripe.com/get-started/data-migrations/overview](https://docs.stripe.com/get-started/data-migrations/overview)
20. Request a payment data export \- Stripe Documentation, accessed March 31, 2026, [https://docs.stripe.com/get-started/data-migrations/pan-export](https://docs.stripe.com/get-started/data-migrations/pan-export)
21. Switching from Paddle to Stripe : r/SaaS \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/SaaS/comments/1brd0yo/switching\_from\_paddle\_to\_stripe/](https://www.reddit.com/r/SaaS/comments/1brd0yo/switching_from_paddle_to_stripe/)
22. Paddle vs Stripe: Why Businesses Outgrow Stripe, accessed March 31, 2026, [https://www.paddle.com/compare/stripe](https://www.paddle.com/compare/stripe)
23. A Detailed Comparison of Stripe vs. Paddle vs. FastSpring, accessed March 31, 2026, [https://fastspring.com/blog/stripe-vs-paddle/](https://fastspring.com/blog/stripe-vs-paddle/)
24. Paddle Checkout \- Paddle Developer, accessed March 31, 2026, [https://developer.paddle.com/concepts/sell/self-serve-checkout](https://developer.paddle.com/concepts/sell/self-serve-checkout)
25. Paddle payment integrations : r/SaaS \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/SaaS/comments/18zx45m/paddle\_payment\_integrations/](https://www.reddit.com/r/SaaS/comments/18zx45m/paddle_payment_integrations/)
26. Integrating Paddle in Next js 14 App directory \- niraj, accessed March 31, 2026, [https://www.niraj.com.np/blog/paddle-integration-in-next-js-14](https://www.niraj.com.np/blog/paddle-integration-in-next-js-14)
27. Paddle Billing Integration — Implementation Guide \- DEV Community, accessed March 31, 2026, [https://dev.to/arshan\_nawaz/paddle-billing-integration-implementation-guide-25op](https://dev.to/arshan_nawaz/paddle-billing-integration-implementation-guide-25op)
28. Generate authenticated customer portal links \- Paddle Developer, accessed March 31, 2026, [https://developer.paddle.com/changelog/2024/customer-portal-sessions](https://developer.paddle.com/changelog/2024/customer-portal-sessions)
29. The new built-in Paddle Customer Portal \- The Inside Scoop from the Developer Preview, accessed March 31, 2026, [https://www.youtube.com/watch?v=PS5XCkmUxxQ](https://www.youtube.com/watch?v=PS5XCkmUxxQ)
30. Entitlement Management System for SaaS (2026 Guide) \- Schematic, accessed March 31, 2026, [https://schematichq.com/blog/entitlement-management-system](https://schematichq.com/blog/entitlement-management-system)
31. Subscription creation \- Paddle Developer, accessed March 31, 2026, [https://developer.paddle.com/build/lifecycle/subscription-creation](https://developer.paddle.com/build/lifecycle/subscription-creation)
32. Plans and entitlements database schema for upgrades and add-ons \- AppMaster, accessed March 31, 2026, [https://appmaster.io/blog/plans-entitlements-database-schema](https://appmaster.io/blog/plans-entitlements-database-schema)
33. Verify webhook signatures \- Paddle Developer, accessed March 31, 2026, [https://developer.paddle.com/webhooks/signature-verification](https://developer.paddle.com/webhooks/signature-verification)
34. Fast.io Webhook Security & Signature Verification Guide, accessed March 31, 2026, [https://fast.io/resources/fastio-webhook-security-signature-verification/](https://fast.io/resources/fastio-webhook-security-signature-verification/)
35. How to Build Webhook Handlers in Python \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2026-01-25-webhook-handlers-python/view](https://oneuptime.com/blog/post/2026-01-25-webhook-handlers-python/view)
36. Understanding SaaS Billing Models: From Flat-Rate to Usage-Based Pricing \- Medium, accessed March 31, 2026, [https://medium.com/@TomasZezula/understanding-saas-billing-models-from-flat-rate-to-usage-based-pricing-89a73c178aca](https://medium.com/@TomasZezula/understanding-saas-billing-models-from-flat-rate-to-usage-based-pricing-89a73c178aca)
37. Subscription Pricing Models: 4 Strategies for Growth in 2023 \- Paddle, accessed March 31, 2026, [https://www.paddle.com/blog/subscription-pricing](https://www.paddle.com/blog/subscription-pricing)
38. How do you decide between usage-based pricing vs flat monthly rate? Stuck on this for our tool. : r/SaaS \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/SaaS/comments/1pljy8e/how\_do\_you\_decide\_between\_usagebased\_pricing\_vs/](https://www.reddit.com/r/SaaS/comments/1pljy8e/how_do_you_decide_between_usagebased_pricing_vs/)
39. SaaS Pricing Models and Strategies \- Paddle, accessed March 31, 2026, [https://www.paddle.com/blog/saas-pricing-models-strategies-fltr](https://www.paddle.com/blog/saas-pricing-models-strategies-fltr)
40. Usage-based billing models: A guide for businesses \- Stripe, accessed March 31, 2026, [https://stripe.com/resources/more/usage-based-billing-models-a-guide-for-businesses](https://stripe.com/resources/more/usage-based-billing-models-a-guide-for-businesses)
41. How to Invoice Abroad from Turkey: 0% VAT & 2026 Rules for Foreigners \- Vergi Merkezi, accessed March 31, 2026, [https://vergimerkezi.com.tr/invoicing-abroad-from-turkey-vat-exemption/](https://vergimerkezi.com.tr/invoicing-abroad-from-turkey-vat-exemption/)
42. Service Export VAT Refund Procedures \- Ozbek CPA, accessed March 31, 2026, [https://ozbekcpa.com/service-export-vat-refund-procedures/](https://ozbekcpa.com/service-export-vat-refund-procedures/)
43. Which countries does Paddle charge sales tax or VAT for? \- Help Center, accessed March 31, 2026, [https://www.paddle.com/help/sell/tax/which-countries-does-paddle-charge-sales-tax-or-vat-for](https://www.paddle.com/help/sell/tax/which-countries-does-paddle-charge-sales-tax-or-vat-for)
44. Your Guide to Reports in Paddle Billing \- Help Center, accessed March 31, 2026, [https://www.paddle.com/help/manage/reporting/your-guide-to-reports-in-paddle-billing](https://www.paddle.com/help/manage/reporting/your-guide-to-reports-in-paddle-billing)
45. Behind webhooks at Paddle: Insights into event delivery at scale, accessed March 31, 2026, [https://paddle.engineering/blog/hookdeck-podcast-event-delivery-scale/](https://paddle.engineering/blog/hookdeck-podcast-event-delivery-scale/)

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABYAAAAfCAYAAADjuz3zAAABuElEQVR4Xs1WsUoDQRCdxUrQRixEbNRCsBAsxM7CQrATCwuxsLCOf2AhiB9gGZR8gI1YWNjb2dnaqEhQrGwshHPmZvZudjN7l0sEffCS7JuZt7OTzRGAGrhYqEXzCgiKBqrXGMpgqOIIzjKzNI+qWJ84QD4iH5Bt4b1o1yqPsCF6Gzf2uVRnNrKM3EFeIbOcDi5EW9KJ+drBR57DvEVuW6Ya58DJn3FAYRT5jdyLAxGCrV6BjS+1qLAKbDoWBxIozOV4bi0IcbgDPNvGmIdybvoY9PkNX46KVUOcApvSF+MxIdqs0qoRbMyLJ2CTjqj7sibOiTZQx95kBfgKEb9Eu1N5Cdg76vmS2ZYktpRO1ywJ27acb3GVJJHevPExS82A99dR8ZnfWXVwA+WmjeG7WowDiCko45tRLEYwETLLHBem0AWOd5PDNOCfD+9xwJUu1Knvmk6QxAhyGrnueHZUQI++GSgKC9NJ5InkEOkHtIAc9wn6FIdy9Ey+NM3nMi0HbfwC/JzIKbW7QVYlauZnhS3td9DYOShQi2qj3mg/yn+AdGU2Z4oKrndCVomlEVL638H8d1SDVMkPMgti8fz5RwwAAAAASUVORK5CYII=>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABUAAAAfCAYAAAAIjIbwAAABgUlEQVR4Xr2SO0oEQRCGq4MFAw3EwFwzNdBAEBMxFtwTGBp4Ce8gZorgAQzFRJA103MIYmKiCMIKWtVV1dtT3fNY7fGDYmb/v6YevQ3QJ84KCe0ZHakWypfNq57ESoQWavNrjYguOT0i7eMpGidqNHvG9y4wQIES/0J1zlmMMWrf+NwVDTPcDT5JozjTZGQJ403yxxirkRf4xBhg0hVwgXXwyW5B/C3RTzAuMB5EJ0biLUYabGNcy7sW/ZjYAZ34PCi87dCxfhR05B5jRd5fIdMVmSfdUbP07z0lD2NoDYLSyaSjsBwAe1TA8gzsUeOETWDz1hrII7CnGykD0XODeC6BE/aMTjvoeVqaNvDoec4Z3Z8n8JqWF6iuThvRdSMcn6fLrhGmmfxH/m1G9PdI/NIMYsNfCxeuVoye57LRteid/B5h7AQXOQROWItFmegJzAQRx8DfUewbrxTpJZ6Cto+9L0nVhyGvErFTn1WKug51eifMHfw1f/t6Okr0KlHD8AOrUEyrm2gkwwAAAABJRU5ErkJggg==>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABYAAAAfCAYAAADjuz3zAAABm0lEQVR4XsWWsUoEMRCGJ4iVaCfIYiFcZyFYWNn5BGLhE2gh9r6CDyHKPcL5AtdYCwo2FlpY2IhvcHDOJJNJMtnNxd0TP5jLZuafZHbIhgNADP0w8fOfYDf47S7teu9V0XZxPTpf5kZHauiTU6SwIIbOcHhDe0G7sWbgkX1jlq3zfCIaZzR/ZU22yyHaKbrvcZyz3VkfwB5rVnh+jvle88S+E9YE1Ba3QAkGvlN3wibI5mZDvFmtKZ/gksbKH3MBTjNbuFpAXnFfRyKewb3VVAe6GJnQ31ItXnOsA11cg0v40oGIqL/2lCiSctwEfz8g9LfpsCvWzEqvxIjCV1Jj0/jrLO0xgpBUwmukv6VFiSX0NyLazZ9f+kAEVU10fhdCqTbdV3KQhFPc+aX+VrILSX87u5b1l8jUkcPdD6DuBxHYB+yvfJXF/tJN1WDOEbieUQJdmdtoW6Iy9nkH7YE1c9yGchrTUixxCeHVghk7vrNmLYtL1XZcZd3yaC21jWphHcOXG75CF8NW7pVdkeQlvf5r/CtU8OCiey7wA02bbL41icPHAAAAAElFTkSuQmCC>
