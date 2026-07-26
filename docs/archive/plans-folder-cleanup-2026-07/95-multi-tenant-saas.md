# **Durable SaaS Infrastructure: Engineering Standards for Payment Systems and Multi-Tenant Architectures in the Fabrik Ecosystem**

The development of a Software-as-a-Service (SaaS) platform by a solo developer requires a disciplined focus on durability, maintenance-light architectures, and the minimization of operational complexity. Within the Fabrik ecosystem, where developers operate under significant time constraints (approximately 50 hours per week) and budget-consciousness, the selection of technological standards must prioritize long-term stability over ephemeral trends. This report establishes the technical foundation for two critical pillars of the Fabrik stack: Rule 85 (Payments and Billing) and Rule 95 (Multi-Tenant SaaS). By utilizing the robust capabilities of PostgreSQL 16, FastAPI, and the Stripe ecosystem, the following analysis details a "fail-closed" engineering framework designed to persist for three years or more without significant refactoring.

## **Executive Summary**

The transition from a minimum viable product to a production-grade SaaS necessitates a move away from manual state management toward database-enforced invariants. In the domain of payments and billing, research indicates that Stripe Checkout is the superior integration pattern for solo developers due to its handling of PCI compliance, Strong Customer Authentication (SCA), and global tax regulations with minimal custom code.1 For data isolation, the adoption of PostgreSQL Row-Level Security (RLS) provides a centralized, database-level defense against cross-tenant data leakage, which is more sustainable for a single developer on a single VPS than managing hundreds of disparate schemas or databases.4

The integration of these systems relies on high-fidelity webhook processing and strict tenant context propagation. Webhooks must be architected with database-backed idempotency to handle the "at-least-once" delivery guarantee of the Stripe API.7 Concurrently, the multi-tenant architecture must ensure that every database connection is scoped to a specific tenant ID via FastAPI dependency injection and PostgreSQL session variables, preventing accidental data exposure even in the event of application-level logic errors.4 The following sections provide a deep technical dive into these standards, followed by a formal rule file proposal for the Fabrik platform.

## **85-payments-billing.md: Subscription and Revenue Engineering**

The revenue infrastructure of a SaaS platform is often the most complex component to maintain due to the volatility of global tax laws, the evolution of payment methods, and the intricate state machine of subscription lifecycles. For a solo developer, every hour spent on custom billing logic is an hour diverted from the core product. Consequently, the Fabrik standard mandates the use of hosted Stripe components wherever possible.

### **Comparison of Stripe Integration Patterns**

The choice between Stripe Checkout and Stripe Elements is frequently debated, but for the Fabrik persona, the decision is governed by maintenance overhead. Stripe Checkout provides a hosted payment page that handles the entire transaction UI, including localization, error handling, and the dynamic display of relevant local payment methods.1

| Feature | Stripe Checkout (Hosted) | Stripe Elements (Embedded) |
| :---- | :---- | :---- |
| **Initial Integration Time** | 1-2 days 12 | 2-4 weeks 12 |
| **Ongoing Maintenance** | Minimal; Stripe handles UI/method updates 1 | High; Developer manages validation and UI 11 |
| **Security/Compliance** | Lowest PCI burden; No card data in DOM 2 | Higher; Requires careful script management 11 |
| **SCA/3DS Handling** | Fully automated 1 | Requires manual redirect logic 13 |
| **Tax Calculation** | Integrated via Stripe Tax 1 | Requires separate API calls/integration 1 |
| **Revenue Recovery** | Automated dunning and smart retries 12 | Manual implementation of retry logic 15 |

Research shows that Stripe Checkout allows a developer to launch with annual billing, usage-based components, and a customer portal from day one.2 While Elements offers pixel-perfect CSS control, the trade-off is a significantly higher technical debt load as the developer must manually implement discount logic, tax calculation, and currency conversion.1 For Fabrik, the hosted Checkout model is the only durable choice for a solo operator.

### **Subscription State and Lifecycle Management**

A subscription is a dynamic entity that transitions through multiple states based on payment success, user action, or trial expiration. The application must accurately mirror these states in the local PostgreSQL database to ensure service continuity and prevent unauthorized access.

| Stripe Status | Local Database Action | Access Level |
| :---- | :---- | :---- |
| active | Update status to active | Full access per plan 16 |
| trialing | Set trial\_end timestamp | Full access; trigger "trial ending" emails 17 |
| past\_due | Flag as "grace period" | Limited/Temporary access; show dunning banner 13 |
| unpaid | Mark as inactive | Revoke access; redirect to billing portal 19 |
| canceled | Delete/Soft-delete subscription | Access denied; keep data for 30-day reactivation 17 |
| incomplete | Flag as pending | Access denied; wait for payment confirmation 20 |

The "past\_due" state is particularly critical for revenue retention. Involuntary churn, caused by expired or declined cards, can be mitigated by allowing a 3- to 7-day grace period while Stripe's "Smart Retries" attempt to recover the payment.12 The application must be architected to check the local subscriptions table for a valid status during every request, rather than querying the Stripe API in real-time, which would introduce unacceptable latency and dependency on a third-party service.2

### **Webhook Reliability and Idempotency**

Webhooks provide the asynchronous connection between Stripe and the application database. Because Stripe uses an "at-least-once" delivery mechanism, the application must be designed to handle duplicate events gracefully.7 Furthermore, network issues or application crashes during webhook processing can leave the database in an inconsistent state.

The mandatory pattern for webhook handling in FastAPI involves three distinct steps:

1. **Verification**: The handler must use the raw request body (the exact bytes sent by Stripe) to verify the stripe-signature header against the STRIPE\_WEBHOOK\_SECRET.21 Parsing the JSON before verification will cause the signature check to fail due to byte-level differences in encoding or whitespace.21
2. **Idempotency**: The application must store every processed event.id in a dedicated processed\_stripe\_events table with a unique constraint.7 If a handler receives an event ID that already exists in this table, it must return a 200 OK immediately without re-executing any business logic.7
3. **Atomic Transactions**: All database updates related to a webhook (e.g., updating a user's plan and logging the event) must be wrapped in a single transaction. This prevents partial state updates if the application fails mid-process.23

### **Entitlement Modeling and Feature Gating**

Feature gating should never be hardcoded as if user.plan \== 'pro'. Such patterns are brittle and difficult to manage as pricing models evolve. Instead, the application should implement an "Entitlement Model" where plans are mapped to specific feature keys.24

Stripe's new Entitlements API allows developers to define features in the Stripe Dashboard and attach them to products.17 The application then queries the customer's active entitlements. For a more maintenance-light approach that avoids real-time API calls, a local mapping table is recommended:

SQL

CREATE TABLE plan\_features (
    plan\_id TEXT NOT NULL,
    feature\_key TEXT NOT NULL,
    limit\_value INTEGER,
    PRIMARY KEY (plan\_id, feature\_key)
);

This structure allows the solo developer to experiment with pricing tiers—such as moving "Advanced Reporting" from a Basic to a Pro plan—entirely through database configuration or the Stripe Dashboard, without modifying the application code.24

### **Global Tax Compliance (Stripe Tax)**

Tax compliance is a significant risk for SaaS businesses scaling internationally. Stripe Tax automates the calculation of sales tax, VAT, and GST based on the customer's location.3 For a solo developer, the "Merchant of Record" (MoR) model provided by Paddle is often cited as a lower-maintenance alternative because Paddle handles the filing and remittance of taxes.12 However, Paddle's higher fees (typically 5% \+ $0.50) and lack of direct customer ownership make it less attractive for high-volume or high-ticket SaaS platforms.12

For Fabrik, the recommended path is **Stripe Tax** used in conjunction with automated invoicing. While the developer remains responsible for filing in jurisdictions where they have "nexus," Stripe Tax provides the data and registration assistance necessary to remain compliant as the business grows.3

### **Mobile Integration with React Native**

When integrating payments into a React Native application, the developer must utilize the PaymentSheet from the @stripe/stripe-react-native SDK.14 This provides a native UI that handles the complexities of 3D Secure authentication and mobile wallet integration (Apple/Google Pay).30

The mobile subscription flow differs from the web flow in its use of the SetupIntent. A SetupIntent is used to securely collect and verify payment details for future use without making an immediate charge.13 This is essential for recurring billing where the initial charge may be $0 (for a trial) or a prorated amount.13 The server-side responsibility is limited to creating a Customer, an Ephemeral Key for temporary access, and the SetupIntent or PaymentIntent, returning the client secrets to the mobile app for processing.13

## **95-multi-tenant-saas.md: Database Isolation and Tenant Lifecycle**

In a multi-tenant SaaS environment, data leakage between customers is a catastrophic failure. For a solo developer managing a single VPS via Coolify, the isolation strategy must balance absolute security with minimal operational complexity. PostgreSQL 16 offers several strategies for multi-tenancy, each with distinct trade-offs in terms of maintenance and scalability.

### **Comparison of Isolation Strategies**

| Strategy | Operational Complexity | Isolation Strength | Solo-Dev Suitability |
| :---- | :---- | :---- | :---- |
| **Database-per-tenant** | Extremely High; Backups and migrations are complex 33 | Absolute | Low |
| **Schema-per-tenant** | High; Migration scaling issues (Alembic runs per schema) 6 | High | Medium |
| **Shared-DB with RLS** | Low; Single migration, single backup 4 | Engine-enforced (High) | **High (Recommended)** |
| **App-level filtering** | Very Low | Weak; Prone to developer error 4 | Low |

The research strongly supports **PostgreSQL Row-Level Security (RLS)** as the optimal choice for the Fabrik platform.4 RLS allows all tenants to share the same tables while the database engine itself enforces that a given connection can only see rows belonging to a specific tenant\_id.4

### **Deep Dive: PostgreSQL Row-Level Security (RLS)**

To implement RLS, every tenant-scoped table must include a tenant\_id column, usually as a UUID. The security model relies on "policies" that are applied to SELECT, INSERT, UPDATE, and DELETE operations.

#### **Security Invariants and Policies**

By default, enabling RLS on a table triggers a "deny-all" policy.35 The developer must then explicitly allow access. A critical "fail-closed" invariant is that the database owner or superuser often bypasses RLS by default.4 To prevent this, the FORCE ROW LEVEL SECURITY command must be used to ensure that even the table owner (the application's database user) is subject to the policies.4

The recommended policy structure for a Fabrik table:

SQL

ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant\_isolation\_policy ON invoices
FOR ALL
TO PUBLIC
USING (tenant\_id \= current\_tenant\_id())
WITH CHECK (tenant\_id \= current\_tenant\_id());

The USING clause controls which rows are visible to the user, while the WITH CHECK clause ensures that any data inserted or updated by the user also belongs to their tenant.34

#### **The Session Context Pattern**

PostgreSQL needs a reliable way to identify the current tenant. The standard pattern involves using a transaction-scoped session variable 4:

SQL

\-- Function to retrieve the tenant ID from the session context
CREATE OR REPLACE FUNCTION current\_tenant\_id() RETURNS UUID AS $$
BEGIN
    RETURN NULLIF(current\_setting('app.tenant\_id', true), '')::UUID;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;

At the start of every request, the application executes SET LOCAL app.tenant\_id \= '...'. Because SET LOCAL is scoped to the current transaction, it is automatically cleared when the connection is returned to the pool, preventing context leakage to subsequent requests.4

### **Tenant Context Propagation in FastAPI**

In a high-concurrency FastAPI environment, using global state or simple middleware for tenant context can lead to race conditions where one request's tenant ID leaks into another.9 This is because the asyncio event loop may switch context between concurrent requests while they share the same database connection if the pool is not managed correctly.

The durable solution is to use **Python ContextVars** within a FastAPI dependency.10 ContextVars are native to Python and are specifically designed to store state that is local to an asynchronous task.

**The Tenant Resolution Lifecycle:**

1. **Resolution**: The tenant ID is extracted from the request (e.g., a X-Tenant-ID header or a subdomain like acme.fabrik.dev).33
2. **Context Setting**: The ID is stored in a ContextVar.
3. **DB Dependency**: The get\_db dependency acquires a connection and immediately runs the SET LOCAL app.tenant\_id command using the ID from the ContextVar.4
4. **Automatic Filtering**: The developer writes standard queries like SELECT \* FROM invoices. PostgreSQL automatically appends the equivalent of WHERE tenant\_id \= '...' based on the RLS policy.4

### **Performance Optimization for RLS**

A common concern with RLS is that the added filtering logic will degrade query performance. However, if indexed correctly, the performance impact is negligible.

1. **Mandatory Indexing**: Every table with RLS enabled must have an index on the tenant\_id column. Without this, every query will result in a full table scan as the database checks every row against the policy.4
2. **Composite Indexes**: For queries that filter on other columns (e.g., email or status), a composite index like (tenant\_id, email) is highly efficient as it allows the database to narrow down the search space to a specific tenant's data before applying secondary filters.4
3. **LEAKPROOF Functions**: PostgreSQL optimizer will not push down functions into the RLS scan if it believes the function might leak information via error messages. For complex logic within a policy, the function must be marked as LEAKPROOF to allow the query planner to use indexes effectively.38

### **Multi-Tenant Caching with Redis**

Caching presents a significant risk for cross-tenant data leaks. If Tenant A caches their "Settings" object under the key settings, and Tenant B later requests settings, they may receive Tenant A's sensitive configuration.44

The mandatory pattern for Fabrik is **Tenant-Prefixed Keys**. All Redis keys must include the tenant ID as a prefix 44:

Python

\# Correct key format
cache\_key \= f"tenant:{tenant\_id}:settings"

For performance-critical paths, a "Multi-Level Cache" (L1/L2) can be used. Hot data is stored in the application's local memory (L1) for sub-microsecond access, while the rest resides in Redis (L2).47 However, the L1 cache must also be tenant-aware to prevent leaks between concurrent requests in the same Python process.

### **Admin Operations and Tenant Management**

Solo developers often need "God-mode" access for debugging or support. Managing this while maintaining RLS requires a specialized role.

1. **The Admin Role**: Create a dedicated database role fabrik\_admin with the BYPASSRLS attribute.4 This role should only be used by migration scripts, backups, and internal admin panels—never by the public-facing API.
2. **Tenant Offboarding**: When a tenant cancels, their data should be soft-deleted. A background job can later purge the data. The deletion logic must be explicitly tested to ensure it doesn't accidentally cascade to other tenants.49
3. **Data Export**: Tenants should be able to export their data in a standard format (JSON/CSV). Since RLS is enabled, a simple SELECT \* from all tables while the tenant context is set will naturally produce a clean export of only that tenant's data.34

## **Canonical Rules for Payments and Multi-Tenancy**

The following rules are to be treated as mandatory engineering standards for the Fabrik platform.

### **Rule File: 85-payments-billing.md**

1. **Prefer Hosted UI**: Always use Stripe Checkout for new subscription checkouts and one-time payments. Custom Elements are only permitted if a multi-step user journey is architecturally required.1
2. **State Mirroring**: All subscription statuses (active, past\_due, unpaid, trialing) must be mirrored in the local subscriptions table. Do not use the Stripe API as a primary source for real-time access checks.16
3. **Mandatory Idempotency**: Every Stripe webhook handler must check for a unique event.id in a processed\_stripe\_events table before execution.7
4. **Raw Body Verification**: Webhook signature verification must use the raw request body string, not the parsed JSON object.21
5. **Entitlement Gating**: Implement feature flags via a plan\_features mapping table. Checking specific plan IDs (e.g., price\_123) in business logic is prohibited.24
6. **Stripe Customer Portal**: Use the hosted Stripe Customer Portal for all subscription management, including plan changes, cancellations, and payment method updates.2
7. **SCA/3DS Compliance**: All payment flows must support Strong Customer Authentication. Stripe Checkout handles this natively.2
8. **Stripe Tax**: Enable and use Stripe Tax for automated calculation and collection of global taxes at checkout.3
9. **Idempotency Keys for API Calls**: All POST requests to the Stripe API from the server must include an Idempotency-Key to prevent double-charging during network retries.7
10. **Test Clock Discipline**: Use Stripe Test Clocks to simulate subscription renewals and trial expirations during integration testing.13
11. **Grace Periods**: Implement a 3-day grace period for past\_due subscriptions before revoking service access.13
12. **Environment Secret Hygiene**: Stripe Secret Keys must never be committed to version control; they must be managed via Coolify environment variables or a secure secret manager.14

### **Rule File: 95-multi-tenant-saas.md**

1. **RLS Default**: Every table containing tenant-specific data MUST have Row-Level Security enabled.4
2. **Force RLS**: Every tenant table must use ALTER TABLE... FORCE ROW LEVEL SECURITY to ensure isolation applies to the table owner.4
3. **Transaction Scoping**: The tenant context must be set using SET LOCAL app.tenant\_id at the start of every database transaction.4
4. **Tenant ID Consistency**: All tenant tables must use a tenant\_id column of type UUID with a foreign key to the central tenants table.
5. **Fail-Closed Policy**: Policies must default to denying all access if app.tenant\_id is not set or is empty.4
6. **ContextVar Propagation**: Use Python ContextVars to propagate the tenant ID through the FastAPI request lifecycle to avoid race conditions.10
7. **Mandatory Tenant Indexing**: Every RLS-protected table must have an index on (tenant\_id) at a minimum.4
8. **Redis Namespacing**: All keys in Redis must be prefixed with t:{tenant\_id}:. Global keys must be explicitly marked as global:.44
9. **Isolated Caching**: L1 (in-memory) caches must be cleared or partitioned per-tenant to prevent cross-request contamination.47
10. **Admin Separation**: Only the fabrik\_admin role may possess BYPASSRLS. This role is strictly for maintenance and must not be used by the application tier.4
11. **No Application-Level Filtering**: Developers are prohibited from manually adding WHERE tenant\_id \=... to queries. The database must handle isolation.4
12. **Rate Limiting**: Implement per-tenant rate limiting using Redis to prevent a "noisy neighbor" from exhausting VPS resources.45

## **Anti-Patterns and Banned Patterns**

### **Payments Anti-Patterns**

* **Local Card Storage**: Storing any portion of a credit card number in the local database is a critical failure. Use Stripe's PaymentMethod IDs.2
* **Polling for Status**: Using a cron job to poll the Stripe API for subscription status is inefficient. Use webhooks.7
* **Manual Refund Logic**: Implementing complex refund calculation logic in code. Use the Stripe Dashboard for manual refunds or the Stripe API for automated ones to ensure tax and fee reversal is handled correctly.1
* **Hardcoded Plan Pricing**: Defining subscription costs in application code. Prices should be retrieved from Stripe or stored in the DB as metadata.1

### **Multi-Tenancy Anti-Patterns**

* **Database-per-Tenant (VPS)**: Creating a new PostgreSQL database for every user. This will exhaust connection limits and RAM on a solo-dev VPS.33
* **Schema-per-Tenant (Large Scale)**: Using schemas for isolation when the tenant count exceeds 100\. Migration management becomes a source of high operational risk.6
* **Shared Connection Variables**: Setting app.tenant\_id at the connection pool level rather than the transaction level. This leads to intermittent data leaks.4
* **Unprefixed Redis Keys**: Storing user\_session\_1 without a tenant prefix. This allows session hijacking across tenants if IDs are predictable.44

## **Enforcement and Verification**

The durability of the Fabrik platform depends on the automated enforcement of these standards.

### **Handoff Enforcement (Execution)**

1. **Schema Check**: Every new migration adding a table must be checked for a tenant\_id column and the corresponding ENABLE ROW LEVEL SECURITY statement.
2. **Webhook Boilerplate**: Every new webhook route must include the standard signature verification and idempotency check block.
3. **Dependency Usage**: All routes accessing the database must use the get\_db or get\_tenant\_db dependency. Use of raw engine connections is prohibited.

### **Verification (final\_gate.py)**

1. **RLS Audit**: Run a SQL query against the pg\_policy and pg\_tables catalogs to identify any tables where RLS is not enabled or where FORCE ROW LEVEL SECURITY is missing.4
2. **Secret Scan**: Scan the codebase for hardcoded sk\_live\_ or whsec\_ strings.
3. **Index Audit**: Verify that every column named tenant\_id has an associated index.
4. **Redis Key Scan**: In staging environments, run a scan of Redis keys to ensure they follow the t:{tenant\_id}: pattern.

### **AGENTS.md / AGENTS-compact.md**

* "Always inherit from TenantBase for all SQL models."
* "All billing changes must be performed through the Stripe Dashboard; code only handles the webhook response."
* "Never use Session.query() directly without the tenant\_db context."

## **Minimal Practical Examples for Fabrik Stack**

### **Multi-Tenant FastAPI Context Manager**

Python

from contextvars import ContextVar
from fastapi import Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession

\# The task-local storage for tenant ID \[10\]
tenant\_context: ContextVar\[str\] \= ContextVar("tenant\_id", default="")

async def get\_db\_with\_rls():
    tenant\_id \= tenant\_context.get()
    async with AsyncSessionLocal() as session:
        \# SET LOCAL ensures this is cleared at the end of the transaction \[4\]
        await session.execute(text(f"SET LOCAL app.tenant\_id \= '{tenant\_id}'"))
        yield session

@app.middleware("http")
async def tenant\_resolution\_middleware(request: Request, call\_next):
    \# Resolve tenant from header
    t\_id \= request.headers.get("X-Tenant-ID", "public")
    token \= tenant\_context.set(t\_id)
    try:
        response \= await call\_next(request)
    finally:
        tenant\_context.reset(token)
    return response

### **Idempotent Webhook Handler**

Python

@app.post("/stripe-webhook")
async def stripe\_webhook(request: Request, db: AsyncSession \= Depends(get\_db)):
    payload \= await request.body()  \# Critical: raw bytes for signature
    sig \= request.headers.get("stripe-signature")

    try:
        event \= stripe.Webhook.construct\_event(payload, sig, WEBHOOK\_SECRET)
    except Exception:
        return Response(status\_code=400)

    \# Database-backed idempotency
    stmt \= insert(ProcessedEvent).values(id\=event.id).on\_conflict\_do\_nothing()
    result \= await db.execute(stmt)

    if result.rowcount \== 0:
        return {"status": "already\_processed"}

    \# Business logic...
    await db.commit()
    return {"status": "ok"}

## **Recommended Final Content for Rule File**

### **Rule 85: Payments and Billing**

1. **Architecture**: Stripe Checkout is mandatory for payment collection. Stripe Customer Portal is mandatory for subscription management.
2. **Webhooks**: Must implement signature verification using request.body(). Must implement idempotency using a processed\_stripe\_events table.
3. **Access Control**: Entitlements must be gated by feature keys in the local DB. Mirror subscription status (active, past\_due) to avoid Stripe API dependency.
4. **Compliance**: Enable Stripe Tax. Store no PCI data locally.
5. **Testing**: Use Test Clocks for all time-based scenarios.

### **Rule 95: Multi-Tenant SaaS**

1. **Isolation**: PostgreSQL Row-Level Security (RLS) is mandatory for all tenant data.
2. **RLS Setup**: Tables must use ENABLE ROW LEVEL SECURITY and FORCE ROW LEVEL SECURITY.
3. **Context**: Set app.tenant\_id via SET LOCAL in every transaction. Propagate tenant ID via ContextVars in FastAPI.
4. **Caching**: All Redis keys must use the t:{tenant\_id}: prefix.
5. **Performance**: Every tenant\_id column must have a B-Tree index.

## **Deep Insights on System Longevity**

The durability of the Fabrik stack is rooted in its alignment with "Standard PostgreSQL." By utilizing RLS, the developer avoids locking themselves into a proprietary multi-tenancy library that may become unmaintained. PostgreSQL 16's RLS implementation is a mature, core feature used by enterprise-grade platforms (e.g., Supabase) and is guaranteed to be supported in versions 17, 18, and beyond.

Similarly, the choice of Stripe Checkout reflects a strategic decision to outsource the "front-end of finance." As new regulations like PSR3 in Europe emerge or as payment methods like "FedNow" in the US gain traction, Stripe will update the Checkout UI automatically. A developer using Stripe Elements would be forced to refactor their checkout code every time the regulatory or payment landscape shifts, whereas a Stripe Checkout user simply enjoys the updates without a single line of code change.

In the domain of multi-tenancy, the use of ContextVars over global middleware state is a critical safeguard against the "leaky connection" problem. In high-concurrency Python environments, the event loop's ability to interleave execution of different requests means that any state stored in a non-task-local manner will eventually be overwritten by a concurrent request, leading to data corruption or leakage. The standard established here ensures that the tenant context is inextricably bound to the execution thread of the specific request, providing a robust defense-in-depth against one of the most common security failures in SaaS development.

Finally, the emphasis on database-backed state mirroring for subscriptions addresses the "Third-Party Reliability" risk. If the Stripe API experiences a latency spike or outage, a system that queries Stripe in the request path will fail globally. By mirroring the status locally and using webhooks for updates, the Fabrik platform remains functional during Stripe outages, fulfilling the "durable and low-ops" requirement of the solo developer.

### **Future Outlook: AI Agents and Autonomous Billing**

As Fabrik moves toward an agent-driven development model, the strictness of these rules becomes even more vital. AI agents are proficient at generating repetitive boilerplate (like RLS policies) but struggle with nuanced security decisions. By codifying these standards into final\_gate.py and AGENTS.md, the developer ensures that any code generated by an agent—whether it's a new database model or a new payment flow—automatically adheres to the isolation and reliability standards of the platform. This creates a "safe sandbox" where the solo developer can leverage AI to accelerate development without risking the security or financial integrity of the SaaS.

## **Conclusion**

The engineering standards detailed in this report provide a comprehensive framework for building durable, maintenance-light SaaS applications on the Fabrik stack. By enforcing Stripe Checkout for revenue and PostgreSQL Row-Level Security for multi-tenancy, a solo developer can achieve enterprise-grade security and reliability while maintaining a high velocity of feature development. The focus on "fail-closed" systems, automated verification, and standard-compliant architectures ensures that the platform remains viable for the next three years, providing a stable foundation for growth and innovation within the Fabrik ecosystem.

#### **Works cited**

1. Compare the Checkout Sessions and Payment Intents APIs \- Stripe Documentation, accessed March 31, 2026, [https://docs.stripe.com/payments/checkout-sessions-and-payment-intents-comparison](https://docs.stripe.com/payments/checkout-sessions-and-payment-intents-comparison)
2. Adding Stripe Checkout to a Solo SaaS: Lessons from PatentLLM's $1K/mo Plan, accessed March 31, 2026, [https://dev.to/soytuber/adding-stripe-checkout-to-a-solo-saas-lessons-from-patentllms-1kmo-plan-1c4d](https://dev.to/soytuber/adding-stripe-checkout-to-a-solo-saas-lessons-from-patentllms-1kmo-plan-1c4d)
3. A guide to nexus and sales tax nexus \- Stripe, accessed March 31, 2026, [https://stripe.com/resources/more/nexus-tax-101](https://stripe.com/resources/more/nexus-tax-101)
4. How to Secure Multi-Tenant Data with Row-Level Security in PostgreSQL \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2026-01-25-row-level-security-postgresql/view](https://oneuptime.com/blog/post/2026-01-25-row-level-security-postgresql/view)
5. Underrated Postgres: Build Multi-Tenancy with Row-Level Security \- Vela \- simplyblock, accessed March 31, 2026, [https://vela.simplyblock.io/blog/row-level-security-postgres/](https://vela.simplyblock.io/blog/row-level-security-postgres/)
6. django-rls-tenants \-- database-enforced multitenancy using PostgreSQL RLS \- Show & Tell, accessed March 31, 2026, [https://forum.djangoproject.com/t/django-rls-tenants-database-enforced-multitenancy-using-postgresql-rls/44522](https://forum.djangoproject.com/t/django-rls-tenants-database-enforced-multitenancy-using-postgresql-rls/44522)
7. Stripe Webhooks Integration Example: Handle Payments with Signature Verification, accessed March 31, 2026, [https://codehooks.io/docs/examples/webhooks/stripe](https://codehooks.io/docs/examples/webhooks/stripe)
8. Migrate from snapshot events to thin events \- Stripe Documentation, accessed March 31, 2026, [https://docs.stripe.com/webhooks/migrate-snapshot-to-thin-events](https://docs.stripe.com/webhooks/migrate-snapshot-to-thin-events)
9. FastAPI Middleware for Postgres Multi-Tenant Schema Switching Causes Race Conditions with Concurrent Requests \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/FastAPI/comments/1iogeor/fastapi\_middleware\_for\_postgres\_multitenant/](https://www.reddit.com/r/FastAPI/comments/1iogeor/fastapi_middleware_for_postgres_multitenant/)
10. Usage of ContextVar in Fastapi \#8628 \- GitHub, accessed March 31, 2026, [https://github.com/fastapi/fastapi/discussions/8628](https://github.com/fastapi/fastapi/discussions/8628)
11. Stripe Elements | Custom Checkout Design and UI, accessed March 31, 2026, [https://stripe.com/payments/elements](https://stripe.com/payments/elements)
12. Stripe vs Paddle: Fees, Tax Handling & MoR Compared \- DesignRevision, accessed March 31, 2026, [https://designrevision.com/blog/stripe-vs-paddle](https://designrevision.com/blog/stripe-vs-paddle)
13. A Founder's Guide to the Stripe Subscription API for Mobile Apps | RapidNative, accessed March 31, 2026, [https://www.rapidnative.com/blogs/subscription-api-stripe](https://www.rapidnative.com/blogs/subscription-api-stripe)
14. Native Stripe Integration Guide for Mobile Apps | HubiFi, accessed March 31, 2026, [https://www.hubifi.com/blog/native-stripe-integration-guide](https://www.hubifi.com/blog/native-stripe-integration-guide)
15. The Ultimate Practical Guide to SaaS Payment Solutions (From Real-World Experience) | by Sunny Dodeja | Medium, accessed March 31, 2026, [https://medium.com/@gdoitwebpvtltd/the-ultimate-practical-guide-to-saas-payment-solutions-from-real-world-experience-9734ab00e35c](https://medium.com/@gdoitwebpvtltd/the-ultimate-practical-guide-to-saas-payment-solutions-from-real-world-experience-9734ab00e35c)
16. Build a subscriptions integration with Elements \- Stripe Documentation, accessed March 31, 2026, [https://docs.stripe.com/payments/advanced/build-subscriptions](https://docs.stripe.com/payments/advanced/build-subscriptions)
17. Integrate a SaaS business on Stripe, accessed March 31, 2026, [https://docs.stripe.com/saas](https://docs.stripe.com/saas)
18. Configure trial offers on subscriptions \- Stripe Documentation, accessed March 31, 2026, [https://docs.stripe.com/billing/subscriptions/trials](https://docs.stripe.com/billing/subscriptions/trials)
19. FastAPI Stripe Payment Gateway Integration \- Tutorial with Examples (2025), accessed March 31, 2026, [https://www.fast-saas.com/blog/fastapi-stripe-integration/](https://www.fast-saas.com/blog/fastapi-stripe-integration/)
20. Build a subscriptions integration \- Stripe Documentation, accessed March 31, 2026, [https://docs.stripe.com/billing/subscriptions/build-subscriptions](https://docs.stripe.com/billing/subscriptions/build-subscriptions)
21. Why Stripe webhook signature verification fails (and how to debug it properly) \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/webdev/comments/1r8cbn1/why\_stripe\_webhook\_signature\_verification\_fails/](https://www.reddit.com/r/webdev/comments/1r8cbn1/why_stripe_webhook_signature_verification_fails/)
22. stripe-webhooks | Skills Marketplace \- LobeHub, accessed March 31, 2026, [https://lobehub.com/it/skills/aykustik-dev-agent-stripe-webhooks](https://lobehub.com/it/skills/aykustik-dev-agent-stripe-webhooks)
23. Building a Production-Grade Async Backend with FastAPI ..., accessed March 31, 2026, [https://dev.to/rosewabere/building-a-production-grade-async-backend-with-fastapi-sqlalchemy-postgresql-and-alembic-2ca4](https://dev.to/rosewabere/building-a-production-grade-async-backend-with-fastapi-sqlalchemy-postgresql-and-alembic-2ca4)
24. Entitlements | Stripe Documentation, accessed March 31, 2026, [https://docs.stripe.com/billing/entitlements](https://docs.stripe.com/billing/entitlements)
25. Stripe Billing | Subscription Models, Features, and More, accessed March 31, 2026, [https://stripe.com/billing/features](https://stripe.com/billing/features)
26. A guide to SaaS subscription models \- Billing \- Stripe, accessed March 31, 2026, [https://stripe.com/resources/more/saas-subscription-models-101-a-guide-for-getting-started](https://stripe.com/resources/more/saas-subscription-models-101-a-guide-for-getting-started)
27. A guide to SaaS pricing models \- Stripe, accessed March 31, 2026, [https://stripe.com/resources/more/saas-pricing-models-101](https://stripe.com/resources/more/saas-pricing-models-101)
28. Paddle vs Stripe Billing 2024: Complete Comparison Guide for SaaS | Flowjam, accessed March 31, 2026, [https://www.flowjam.com/blog/paddle-vs-stripe-billing-2024-complete-comparison-guide-for-saas](https://www.flowjam.com/blog/paddle-vs-stripe-billing-2024-complete-comparison-guide-for-saas)
29. Accept in-app payments \- Stripe Documentation, accessed March 31, 2026, [https://docs.stripe.com/payments/mobile/accept-payment?platform=react-native\&type=payment](https://docs.stripe.com/payments/mobile/accept-payment?platform=react-native&type=payment)
30. Stripe React Native: A Practical Guide to Mobile Payments \- RapidNative, accessed March 31, 2026, [https://www.rapidnative.com/blogs/stripe-react-native](https://www.rapidnative.com/blogs/stripe-react-native)
31. How to Integrate Stripe Payment Sheet in React Native: Complete Guide \- Salman Azam, accessed March 31, 2026, [https://salmanazam.medium.com/how-to-integrate-stripe-payment-sheet-in-react-native-complete-guide-0cc1c10a32ca](https://salmanazam.medium.com/how-to-integrate-stripe-payment-sheet-in-react-native-complete-guide-0cc1c10a32ca)
32. Accept a payment \- Stripe Documentation, accessed March 31, 2026, [https://docs.stripe.com/payments/accept-a-payment?payment-ui=mobile\&platform=react-native](https://docs.stripe.com/payments/accept-a-payment?payment-ui=mobile&platform=react-native)
33. fastapi-tenancy · PyPI, accessed March 31, 2026, [https://pypi.org/project/fastapi-tenancy/](https://pypi.org/project/fastapi-tenancy/)
34. How to Implement PostgreSQL Row Level Security for Multi-Tenant SaaS \- techbuddies.io, accessed March 31, 2026, [https://www.techbuddies.io/2026/01/01/how-to-implement-postgresql-row-level-security-for-multi-tenant-saas/](https://www.techbuddies.io/2026/01/01/how-to-implement-postgresql-row-level-security-for-multi-tenant-saas/)
35. How to Implement Row-Level Security in PostgreSQL \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2026-01-21-postgresql-row-level-security/view](https://oneuptime.com/blog/post/2026-01-21-postgresql-row-level-security/view)
36. Documentation: 18: 5.9. Row Security Policies \- PostgreSQL, accessed March 31, 2026, [https://www.postgresql.org/docs/current/ddl-rowsecurity.html](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
37. Documentation: 18: CREATE POLICY \- PostgreSQL, accessed March 31, 2026, [https://www.postgresql.org/docs/current/sql-createpolicy.html](https://www.postgresql.org/docs/current/sql-createpolicy.html)
38. Common Postgres Row-Level-Security footguns \- Bytebase, accessed March 31, 2026, [https://www.bytebase.com/blog/postgres-row-level-security-footguns/](https://www.bytebase.com/blog/postgres-row-level-security-footguns/)
39. PostgreSQL Row Level Security (RLS): Basics and Examples \- Satori Cyber, accessed March 31, 2026, [https://satoricyber.com/postgres-security/postgres-row-level-security/](https://satoricyber.com/postgres-security/postgres-row-level-security/)
40. Set Postgres config parameters using set\_config (for RLS) \- Retool Forum, accessed March 31, 2026, [https://community.retool.com/t/set-postgres-config-parameters-using-set-config-for-rls/31421](https://community.retool.com/t/set-postgres-config-parameters-using-set-config-for-rls/31421)
41. Adding Context to Each FastAPI Request Using Request State \- Python in Plain English, accessed March 31, 2026, [https://python.plainenglish.io/adding-context-to-each-fastapi-request-using-request-state-1a0f110c536e](https://python.plainenglish.io/adding-context-to-each-fastapi-request-using-request-state-1a0f110c536e)
42. Next.js multi-domain (multi-tenant) site: resolve business in middleware vs in layout/server component? \- Stack Overflow, accessed March 31, 2026, [https://stackoverflow.com/questions/79879716/next-js-multi-domain-multi-tenant-site-resolve-business-in-middleware-vs-in-l](https://stackoverflow.com/questions/79879716/next-js-multi-domain-multi-tenant-site-resolve-business-in-middleware-vs-in-l)
43. Postgres RLS Implementation Guide \- Best Practices, and Common Pitfalls \- Permit.io, accessed March 31, 2026, [https://www.permit.io/blog/postgres-rls-implementation-guide](https://www.permit.io/blog/postgres-rls-implementation-guide)
44. Multi-Tenant Caching Strategies: Why Redis Alone Isn't Enough (Hybrid Pattern) \- Okan Yurt, accessed March 31, 2026, [https://okanyurt.medium.com/multi-tenant-caching-strategies-why-redis-alone-isnt-enough-hybrid-pattern-f404877632e5](https://okanyurt.medium.com/multi-tenant-caching-strategies-why-redis-alone-isnt-enough-hybrid-pattern-f404877632e5)
45. Multitenancy and Azure Cache for Redis \- Microsoft Learn, accessed March 31, 2026, [https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/service/cache-redis](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/service/cache-redis)
46. Redis Best Practices \- Expert Tips for High Performance \- Dragonfly, accessed March 31, 2026, [https://www.dragonflydb.io/guides/redis-best-practices](https://www.dragonflydb.io/guides/redis-best-practices)
47. How to Implement Multi-Level Caching with Redis \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2026-01-21-redis-multi-level-caching/view](https://oneuptime.com/blog/post/2026-01-21-redis-multi-level-caching/view)
48. A Friendly Introduction to RLS Policies in Postgres \- cord, accessed March 31, 2026, [https://cord.com/techhub/architecture/articles/a-friendly-introduction-to-rls-policies-in-postgre](https://cord.com/techhub/architecture/articles/a-friendly-introduction-to-rls-policies-in-postgre)
49. How SaaS vendors operate and what to watch for in contracts \- Stripe, accessed March 31, 2026, [https://stripe.com/resources/more/how-saas-vendors-operate-and-what-to-watch-for-in-contracts](https://stripe.com/resources/more/how-saas-vendors-operate-and-what-to-watch-for-in-contracts)
50. How to Use Row-Level Security in PostgreSQL \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2026-01-25-use-row-level-security-postgresql/view](https://oneuptime.com/blog/post/2026-01-25-use-row-level-security-postgresql/view)
51. Build a subscriptions solution for an AI startup with a usage-based pricing model, accessed March 31, 2026, [https://docs.stripe.com/get-started/use-cases/usage-based-billing](https://docs.stripe.com/get-started/use-cases/usage-based-billing)
52. Redis Anti-Patterns: Common Mistakes Every Developer Should Avoid, accessed March 31, 2026, [https://redis.io/tutorials/redis-anti-patterns-every-developer-should-avoid/](https://redis.io/tutorials/redis-anti-patterns-every-developer-should-avoid/)
53. Best Accounting Software for Stripe Integration \- HubiFi, accessed March 31, 2026, [https://www.hubifi.com/blog/accounting-software-stripe-integration](https://www.hubifi.com/blog/accounting-software-stripe-integration)
