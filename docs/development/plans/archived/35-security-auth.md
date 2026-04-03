# **Security and Authentication Architecture for the Fabrik Platform**

## **1\. Executive Summary**

The architectural landscape for solo-developer platforms demands an uncompromising balance between rigorous security standards and low-maintenance operational durability. In an environment constrained by a fifty-hour workweek, deploying across a multi-client ecosystem—encompassing a Next.js 14 web application, a React Native mobile application, and a Manifest V3 Chrome Extension—requires a unified, centralized authentication strategy. The Fabrik stack, utilizing FastAPI on an ARM64 Ubuntu VPS managed via Coolify, necessitates an architecture that avoids the high operational overhead of distributed identity meshes while maintaining absolute zero-trust principles.

This comprehensive research report establishes the definitive security and authentication framework for the Fabrik platform. The analysis evaluates the dichotomy between stateful session management and stateless JSON Web Tokens (JWTs), concluding that a hybrid approach—stateless access tokens paired with stateful, database-backed refresh tokens—provides the optimal security posture for a budget-conscious, low-maintenance environment.1 Furthermore, the deployment of this architecture across disparate client types mandates a divergent token storage strategy: HttpOnly cookies for web clients to mitigate Cross-Site Scripting (XSS) vulnerabilities 3, and Bearer tokens stored in secure enclaves (e.g., SecureStore) for mobile and extension clients.5

Additionally, the analysis addresses critical security vulnerabilities specific to the chosen stack, notably the Next.js 14 middleware authorization bypass (CVE-2025-29927) 7, enforcing a defense-in-depth protocol where authentication is verified cryptographically at the route handler level, rather than relying solely on edge middleware. Cross-Origin Resource Sharing (CORS) policies are strictly mapped to prevent misconfigurations across mobile and extension origins 9, and Content Security Policy (CSP) headers are defined to support Next.js 14's App Router using nonce-based dynamic injection.10

The culmination of this research dictates the permanent rules, automated programmatic checks for continuous integration (final\_gate.py), and execution handoff requirements. These directives ensure that the Fabrik platform remains impenetrable, highly performant, and architecturally sound for the foreseeable operational future, eliminating technical debt and minimizing ongoing maintenance burdens.

## **2\. The Solo Developer's Authentication Paradigm**

### **Evaluating Authentication Infrastructure**

The initial architectural decision for a modern application involves selecting the identity provider (IdP). The market currently offers a spectrum of Backend-as-a-Service (BaaS) solutions, including Clerk, Supabase Auth, Auth0, and open-source frameworks like Auth.js (formerly NextAuth).11 While hosted solutions like Clerk provide rapid integration and polished user interfaces, they introduce significant vendor lock-in, external network latency, and usage-based pricing cliffs that threaten a budget-conscious solo developer.13

Conversely, relying on Next.js-centric libraries like Auth.js forces the authentication logic into the frontend server.15 While excellent for monolithic Next.js applications, this approach fractures the architecture when a React Native mobile application and a Chrome Extension must authenticate against the same backend data layer. The FastAPI backend would be forced to blindly trust the Next.js server or implement complex cross-verification mechanisms.16

For the Fabrik platform, the most durable, low-maintenance approach is to establish the FastAPI backend as the sole, centralized Identity Provider.17 By utilizing robust, async-native libraries such as fastapi-users or implementing a secure OAuth2PasswordBearer flow, the developer retains complete data sovereignty and eliminates recurring SaaS costs.18 The FastAPI service handles credential hashing (utilizing Argon2 or bcrypt), token issuance, and validation, while the Next.js web app, React Native app, and Chrome Extension operate strictly as consumers of the API.2

| Authentication Strategy | Operational Maintenance | Vendor Lock-in | Multi-Client Suitability | Fabrik Recommendation |
| :---- | :---- | :---- | :---- | :---- |
| **Hosted BaaS (Clerk/Auth0)** | Low | High | High (via multiple SDKs) | Reject (Cost/Lock-in) |
| **Frontend Auth (Auth.js)** | Medium | Low | Low (Next.js coupled) | Reject (Architecture mismatch) |
| **FastAPI Centralized IdP** | Medium (Initial Setup) | None | Optimal (Agnostic API) | **Adopt** |

### **Cryptographic Algorithms and Entropy**

JSON Web Tokens (JWTs) rely on cryptographic signatures to guarantee token integrity. The selection of the signing algorithm dictates the computational overhead and the complexity of key management. The two predominant algorithms are HS256 (HMAC with SHA-256), a symmetric algorithm, and RS256 (RSA Signature with SHA-256), an asymmetric algorithm utilizing a public-private key pair.19

RS256 is vital in distributed microservice architectures where multiple distinct services must verify a token without possessing the capability to forge one.19 However, in the Fabrik architecture, the FastAPI backend is both the sole issuer and the sole verifier of access tokens. Implementing RS256 introduces unnecessary complexity regarding key rotation, public key distribution (JWKS endpoints), and computational latency.19

Therefore, HS256 is the mandated algorithm for Fabrik.21 The critical security requirement for HS256 is the entropy of the shared secret. The secret key must be a cryptographically secure random string of at least 256 bits (32 bytes), injected into the FastAPI runtime via environment variables.22 Generating this secret using a secure random generator (e.g., openssl rand \-hex 32\) ensures that brute-force attacks against the token signature are mathematically infeasible.

### **The Hybrid Token Lifecycle**

Stateless JWTs present a well-documented security challenge: they cannot be revoked prior to their expiration without introducing stateful blacklists, which defeats the purpose of statelessness.23 To balance performance with security, Fabrik must implement a hybrid token lifecycle.2

The FastAPI backend issues a short-lived Access Token (e.g., 15 minutes) and a long-lived Refresh Token (e.g., 7 days).25 The short lifespan of the access token limits the vulnerability window in the event of token interception.23 The refresh token is an opaque, cryptographically random string (not a JWT) stored persistently in the PostgreSQL database alongside the user record and device metadata.2 When the access token expires, the client submits the refresh token; the backend verifies its existence and validity in the database before issuing a new access token. This mechanism allows the solo developer to instantly revoke access by deleting the refresh token from the database, satisfying both security and low-maintenance requirements.1

## **3\. Client-Specific Token Storage Architecture**

The assumption that a singular token storage mechanism can be universally applied across web, mobile, and extension clients is a dangerous anti-pattern.1 Each runtime environment possesses unique threat vectors that dictate strict storage protocols.

### **Web Application (Next.js 14\)**

In browser environments, storing authentication tokens in localStorage or sessionStorage exposes the application to catastrophic Cross-Site Scripting (XSS) attacks.4 Any malicious script executing on the page can freely read storage APIs and exfiltrate the tokens.27

For the Next.js 14 client, JWTs must be managed exclusively via HttpOnly cookies.24 The FastAPI backend's authentication endpoint must return a Set-Cookie header containing the JWT, configured with the following flags 1:

* HttpOnly: Prevents JavaScript access, mitigating XSS.
* Secure: Ensures the cookie is only transmitted over encrypted HTTPS connections.
* SameSite=Lax (or Strict): Mitigates Cross-Site Request Forgery (CSRF) by preventing the browser from sending the cookie with cross-origin requests.

During Server-Side Rendering (SSR) or within Next.js Server Actions, the Next.js server automatically receives these cookies and can forward them to the FastAPI backend for data retrieval.29

### **Mobile Application (React Native)**

Native mobile environments do not share the browser's DOM vulnerabilities; HttpOnly cookies are largely irrelevant and notoriously difficult to manage consistently within native HTTP clients and WebViews.30 In React Native, the FastAPI backend must return the JWT in the JSON response payload.

The React Native client must store this token in the operating system's hardware-backed secure enclave.5 Depending on the framework utilized (e.g., Expo), libraries such as expo-secure-store leverage the iOS Keychain and the Android Keystore system.31 This encrypts the token at rest, protecting it even if the physical device is compromised. The client application retrieves the token from the secure store into memory upon initialization and attaches it as an Authorization: Bearer \<token\> header for all subsequent API requests.

### **Chrome Extension (Manifest V3)**

The migration to Manifest V3 (MV3) fundamentally altered the security architecture of Chrome Extensions. The persistent background pages of MV2 have been replaced by ephemeral service workers.32 Because service workers can be terminated by the browser at any time to conserve resources, relying on in-memory global variables for token storage is unstable.33

Furthermore, standard web localStorage is not accessible within service workers, and storing tokens there within content scripts reintroduces XSS vulnerabilities, as extensions operate across highly variable and potentially hostile DOMs.34 The mandatory storage mechanism for Chrome Extensions is the chrome.storage.session API.35 This API keeps data securely in memory, sharing it seamlessly between the extension's popup, content scripts, and service worker, without ever writing the sensitive tokens to the user's hard drive.6 Like the mobile client, the extension attaches the token via the Authorization: Bearer header.

| Client Runtime | Mandated Storage Mechanism | Transmission Header | Primary Threat Mitigated |
| :---- | :---- | :---- | :---- |
| **Next.js 14 (Web)** | HttpOnly, Secure Cookie | Automatic (Cookie) | XSS (Cross-Site Scripting) |
| **React Native** | OS Secure Enclave (Keychain) | Authorization: Bearer | Physical device compromise |
| **Chrome Ext. (MV3)** | chrome.storage.session | Authorization: Bearer | Ephemeral worker state / XSS |

## **4\. Securing the Next.js 14 App Router**

The introduction of the App Router and React Server Components in Next.js shifted the paradigm of frontend development, merging server-side data fetching with UI rendering. This integration significantly expands the attack surface if authentication boundaries are misunderstood.7

### **Mitigating Middleware Authorization Bypass (CVE-2025-29927)**

A highly critical vulnerability disclosed in March 2025 (CVE-2025-29927, CVSS 9.1) allows attackers to completely bypass Next.js middleware by manipulating the x-middleware-subrequest header.7 Historically, developers relied on middleware.ts to inspect incoming request cookies, validate the JWT, and redirect unauthenticated users away from protected routes.

If an application relies *solely* on middleware for security, an attacker exploiting this CVE can directly access protected Server Components and Server Actions without credentials.14 Therefore, Fabrik must enforce a strict Zero Trust model within the Next.js architecture.7

Middleware should be utilized strictly for optimistic User Experience (UX) enhancements—such as fast redirects to the /login page for missing cookies.37 However, the actual cryptographic verification of the session must occur within the specific Server Action, Route Handler, or Server Component executing the sensitive logic.7 This is achieved by creating a Data Access Layer (DAL) utility (e.g., verifySession()) that parses the cookie, communicates with the FastAPI backend to ensure token validity, and returns the user context before any database mutations or sensitive data retrievals occur.38

## **5\. Cross-Origin Resource Sharing (CORS) Engineering**

CORS is a browser-enforced security mechanism designed to prevent malicious websites from making unauthorized requests to an API.40 For the Fabrik platform, correctly mapping the CORS policy matrix is vital to ensure that the Next.js, React Native, and Chrome Extension clients can communicate with the FastAPI backend without exposing the API to the public internet.9

A pervasive and critical anti-pattern in CORS configuration is the use of the wildcard origin (allow\_origins=\["\*"\]) in conjunction with allowing credentials (allow\_credentials=True).9 Modern browsers strictly prohibit this combination; if a backend accepts cookies or Authorization headers, it must explicitly define the exact domains permitted to make those requests.9

FastAPI utilizes the Starlette-based CORSMiddleware.42 The allow\_origins array must be populated dynamically via environment variables to accommodate environment promotion (staging vs. production).41

* **Web Origins**: The exact HTTPS domain of the Next.js application (e.g., https://fabrik-app.com).
* **Mobile Origins**: React Native applications utilizing Capacitor or Expo often serve local files via custom URI schemes to bypass standard HTTP restrictions. The CORS policy must explicitly allow these schemes, such as capacitor://localhost or app://localhost.44
* **Extension Origins**: Chrome Extensions operating via Manifest V3 make requests from an origin defined by their unique hash ID. The origin format is chrome-extension://\<extension-id\>.46 During development, when the ID fluctuates, developers may utilize the allow\_origin\_regex parameter in FastAPI (e.g., allow\_origin\_regex=r"chrome-extension://.\*") to prevent blockage.46 However, prior to production deployment, the exact, immutable ID of the published extension must be hardcoded into the allow\_origins array to prevent malicious extensions from accessing the API.46

| Client Application | Origin Signature | Credentials Allowed | Implementation Note |
| :---- | :---- | :---- | :---- |
| **Next.js Web** | https://fabrik.app.com | True | Requires exact match, no trailing slashes. |
| **React Native** | capacitor://localhost | True | Depends on the specific native bundler scheme. |
| **Chrome Extension** | chrome-extension://\<id\> | True | Use regex in dev; strict hardcoded ID in prod. |

## **6\. Content Security Policy (CSP) and Defensive Headers**

Hardening the HTTP responses against client-side injection attacks is a non-negotiable requirement. This defense is achieved through the implementation of robust security headers on both the Next.js frontend and the FastAPI backend.47

### **Next.js 14 Nonce-Based CSP**

A Content Security Policy (CSP) dictates which external resources (scripts, styles, images) a browser is permitted to load and execute.10 For modern React applications, strict CSP implementation requires the use of nonces. A nonce (number used once) is a unique, unguessable string generated on every individual HTTP request. The CSP header specifies the valid nonce, and only \<script\> tags bearing the matching nonce attribute are executed.10

In Next.js 14, nonces are implemented via middleware.ts. The middleware generates a secure crypto.randomUUID(), formats the Content-Security-Policy header, and applies it to the response.49 Because the nonce must be unique per request, implementing a nonce-based CSP forces the application to abandon Static Site Generation (SSG) in favor of dynamic Server-Side Rendering (SSR) for all protected routes.10 This is a necessary performance trade-off to achieve an impenetrable XSS defense layer in a highly dynamic SaaS environment.

### **FastAPI ASGI Security Middleware**

While the frontend manages CSP, the FastAPI backend must secure its own HTTP responses against MIME-sniffing, clickjacking, and protocol downgrade attacks.51 The most efficient method to apply these headers in FastAPI is through a custom ASGI middleware.53

To maintain the low latency required by the platform, these header strings must be precomputed as constants outside the execution path.47 The mandatory headers include:

* Strict-Transport-Security (HSTS): Enforces HTTPS connections. For production, max-age=31536000; includeSubDomains; preload ensures browsers refuse HTTP connections for one year.52
* X-Content-Type-Options: Set to nosniff to prevent browsers from misinterpreting executable files masked as safe media types.51
* X-Frame-Options: Set to DENY to prevent the API endpoints from being embedded in malicious iframes, mitigating clickjacking.51
* Referrer-Policy: Set to strict-origin-when-cross-origin to prevent the leakage of sensitive URL parameters to external sites.47

## **7\. Internal Service Authentication and Secrets Management**

The Fabrik deployment utilizes Coolify to orchestrate Docker Compose containers on an ARM64 Ubuntu VPS. While Coolify establishes a private Docker network—meaning containers can communicate via internal DNS (e.g., http://backend:8000) without exposing ports to the host interface—network isolation alone does not satisfy zero-trust architecture.54

If an attacker manages to achieve Remote Code Execution (RCE) on a secondary container, they could pivot laterally and access the unauthenticated backend API. Therefore, all internal machine-to-machine communication must be explicitly authenticated.

To maintain a low-ops profile, managing complex OAuth client credentials for internal cron jobs or background workers is excessive. Instead, Fabrik utilizes a Shared Secret pattern. A high-entropy key, designated SERVICE\_INTERNAL\_SECRET\_KEY, is generated securely and passed into the Docker containers via environment variables or Docker Secrets.56 When an internal service queries the FastAPI backend, it attaches this secret via an X-Internal-Token header. A dedicated FastAPI dependency function validates this header in constant time, rejecting unauthorized internal traffic with a 403 Forbidden response.56

## **8\. Account Recovery and Transactional Email Logistics**

The architecture of authentication is incomplete without reliable account recovery mechanisms. Password resets and email verification flows rely entirely on the latency and deliverability of the transactional email provider.

In a low-maintenance, solo-developer environment, debugging email delivery failures is an unacceptable operational burden. Analytical comparisons between modern providers like Resend and established MTAs (Message Transfer Agents) like Postmark reveal stark architectural differences.58 Resend operates as an abstraction layer over Amazon SES, meaning emails are queued twice (once at Resend, once at AWS) and dispatched from shared, high-volume IP pools.59 This introduces measurable latency and a benchmarked error rate of 0.07%.60

Postmark, conversely, owns its infrastructure end-to-end and strictly isolates transactional email streams from bulk marketing broadcasts.58 This guarantees sub-second delivery latency and a benchmarked 0.00% error rate.60 For time-sensitive authentication payloads like One-Time Passwords (OTPs) and password reset links, Postmark is the mandated provider.

FastAPI will implement password resets by generating a cryptographically signed, short-lived JWT containing the user's ID and a specific reset claim. This token is appended to a Next.js frontend URL and dispatched via Postmark's REST API. Upon user click, the frontend extracts the token and submits it alongside the new password to the backend for verification and update.

## ---

**9\. Canonical Rules for this Rule File**

1. **FastAPI as Sole Identity Provider**: FastAPI exclusively owns all user identity, credential hashing (Argon2), and token issuance. Next.js, React Native, and Chrome Extensions act strictly as API clients.
2. **Stateless Access, Stateful Refresh**: Implement short-lived (15 minute) JWT access tokens alongside long-lived, opaque refresh tokens stored persistently in the PostgreSQL database to facilitate immediate session revocation.
3. **Strict Token Storage Segmentation**:
   * **Web**: JWTs must be stored exclusively in HttpOnly, Secure, SameSite=Lax cookies.
   * **Mobile**: JWTs must be stored in OS-level secure enclaves (e.g., Expo SecureStore).
   * **Extension**: JWTs must be stored via the chrome.storage.session API.
4. **HS256 Cryptographic Standard**: Utilize the HS256 algorithm for JWT signing, backed by a minimum 256-bit cryptographically secure random secret injected via environment variables.
5. **Defense-in-Depth Authentication**: Next.js must cryptographically verify user sessions at the Server Action and Server Component layer. Never rely solely on Next.js Edge Middleware for access control (mitigating CVE-2025-29927).
6. **Explicit CORS Enforcement**: The allow\_origins array in FastAPI must explicitly define valid domains. The use of allow\_origins=\["\*"\] combined with allow\_credentials=True is universally banned.
7. **Dynamic CSP Nonce Injection**: Next.js must utilize middleware.ts to inject a cryptographically secure x-nonce into the Content-Security-Policy header, enforcing dynamic rendering for all protected routes.
8. **Precomputed FastAPI Security Headers**: FastAPI must implement a lightweight ASGI middleware to inject Strict-Transport-Security, X-Content-Type-Options: nosniff, and X-Frame-Options: DENY on all HTTP responses.
9. **Internal Network Zero-Trust**: Docker-to-Docker communication within the Coolify network must be authenticated via an X-Internal-Token header validated against a shared SERVICE\_INTERNAL\_SECRET\_KEY.
10. **Transactional Email Isolation**: Utilize Postmark via its REST API for all authentication-related emails to ensure sub-second latency and absolute deliverability.
11. **Cryptographic Rate Limiting**: Hard rate limits must be enforced on all /auth/login, /auth/register, and /auth/reset endpoints using Redis or in-memory token buckets to prevent credential stuffing.
12. **Base Image Enforcement**: All Dockerfiles must inherit from python:3.12-slim-bookworm or node:20-slim-bookworm. Alpine Linux is strictly banned due to musl libc DNS and performance anomalies on ARM64 architectures.

## **10\. Anti-Patterns / Banned Patterns**

* **localStorage for JWTs**: Storing JWTs in browser localStorage or sessionStorage is banned due to severe XSS payload exposure.
* **Middleware-Only Authorization**: Trusting Next.js middleware.ts as the sole gatekeeper for protected routes without secondary validation in the server context is banned.
* **Wildcard CORS with Credentials**: Using \* for CORS origins when dealing with HttpOnly cookies or Authorization headers is mathematically invalid and banned.
* **Resend/SES for Critical Auth Flows**: Using Resend for password reset emails is banned due to double-queue latency and shared SES IP pool reputation risks. Use Postmark.
* **Asymmetric Keys (RS256) for Internal Verification**: Do not implement complex Public/Private key pairs if FastAPI is the only service signing and verifying the tokens.
* **Alpine Linux Base Images**: Using node:alpine or python:alpine is banned to avoid high-maintenance build compilation issues and DNS resolution bugs on ARM64 Coolify infrastructure.

## **11\. What to Enforce in Execute Handoffs**

When an AI agent finishes generating or modifying authentication modules, the handoff instruction must explicitly command the next execution phase to:

* Ensure that the FastAPI /login/web endpoint strictly returns a Set-Cookie header with the configured flags, while the /login/mobile endpoint returns a standard JSON { "access\_token": "..." } payload.
* Verify that any newly created Next.js Server Component that fetches user-specific data invokes the internal verifySession() Data Access Layer utility rather than assuming the route is protected by the edge middleware.
* Confirm that the CORSMiddleware array in FastAPI receives its origins from a strictly typed Pydantic Settings class, designed to fail fast upon boot if the environment variable is missing or malformed.
* Check that the Docker Compose configuration explicitly defines the internal network and maps the SERVICE\_INTERNAL\_SECRET\_KEY to all backend microservices securely.

## **12\. What to Verify in final\_gate.py**

The final\_gate.py script acts as the automated CI/CD enforcer. It must programmatically parse the AST (Abstract Syntax Tree) and utilize regex configurations to verify:

* **CORS Array Safety Check**: Regex/AST scan main.py for CORSMiddleware. Fail the build immediately if allow\_origins=\["\*"\] is detected alongside allow\_credentials=True.
* **Cookie Flag Verification**: Scan FastAPI authentication routes for the set\_cookie method. Fail the build if httponly=True, secure=True, and samesite="lax" (or strict) are not explicitly present in the AST.
* **Security Header Presence**: Scan FastAPI middleware definitions for the explicit presence of the strings "Strict-Transport-Security" and "X-Content-Type-Options".
* **Next.js Server Action Auth Validation**: Scan all Next.js files ending in actions.ts or containing the "use server" directive. Fail the build if the file mutates data but lacks a call to the authorization utility (e.g., verifySession()).
* **No LocalStorage Auth**: Scan all React/Next.js frontend components for localStorage.setItem('token' or localStorage.getItem('token'. Fail the build if found.
* **Base Image Compliance**: Scan all Dockerfile manifests. Fail the build if FROM alpine or FROM python:\*-alpine is detected. Ensure slim-bookworm is explicitly utilized.

## **13\. What Belongs in AGENTS.md / AGENTS-compact.md**

**AGENTS.md Context:**

"When generating authentication workflows, Fabrik uses a hybrid unified architecture designed for low maintenance. FastAPI is the absolute sole identity provider. Web clients receive JWTs via HttpOnly cookies to prevent XSS. Mobile and Chrome Extension clients receive Bearer tokens stored in secure enclaves. Never implement external BaaS libraries like NextAuth.js or Clerk; write direct integrations against the FastAPI backend. Always secure Next.js Server Components at the component level, never relying entirely on middleware due to bypass vulnerabilities. Use Postmark for transactional auth emails to ensure deliverability."

**AGENTS-compact.md Context:**

"Auth: FastAPI IdP. Web \= HttpOnly cookies. Mobile/Ext \= Bearer tokens. Next.js: verify auth inside Server Actions/Components, avoid middleware-only auth. Security: Strict CORS, no \*. Use Postmark. Base image: slim-bookworm."

## **14\. Minimal Practical Examples for Fabrik Stack**

### **FastAPI Precomputed Security Headers Middleware**

To ensure zero latency degradation, security headers are precomputed as constants and applied via a lightweight ASGI middleware interceptor.

Python

from fastapi import FastAPI, Request
from starlette.datastructures import MutableHeaders

app \= FastAPI()

\# Precomputed constants to prevent per-request latency
HSTS \= "max-age=31536000; includeSubDomains; preload"
XCTO \= "nosniff"
XFO \= "DENY"

@app.middleware("http")
async def security\_headers(request: Request, call\_next):
    response \= await call\_next(request)
    headers \= MutableHeaders(response.headers)

    \# HSTS enforces HTTPS strictly
    headers.setdefault("Strict-Transport-Security", HSTS)
    headers.setdefault("X-Content-Type-Options", XCTO)
    headers.setdefault("X-Frame-Options", XFO)

    return response

### **Next.js 14 Safe Server Action (Bypass Protection)**

This example demonstrates the required Data Access Layer (DAL) pattern, ensuring cryptographic validation occurs at the execution level, neutralizing middleware bypass attacks.

TypeScript

"use server"
import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'

export async function secureServerAction(data: FormData) {
  // MUST verify here, do not trust middleware routing for security
  const cookieStore \= cookies()
  const token \= cookieStore.get('auth\_token')?.value

  if (\!token) {
    redirect('/login')
  }

  // Validate token cryptographically with FastAPI backend
  const res \= await fetch(\`${process.env.API\_URL}/api/users/me\`, {
    headers: { 'Cookie': \`auth\_token=${token}\` }
  })

  if (\!res.ok) throw new Error("Unauthorized Access Attempt")

  // Proceed with secure database mutation
}

## **15\. Recommended Final Content for the Rule File**

### **35-security-auth.md**

# **Fabrik Auth & Security Architecture**

## **1\. Unified Authentication Strategy**

* **Sole Identity Provider**: FastAPI handles all credential hashing (Argon2), user state, and token generation. Do not use NextAuth.js, Clerk, or Firebase. Maintain total data sovereignty.
* **Stateless Access / Stateful Refresh**: Use short-lived JWT access tokens (15m) and database-backed refresh tokens to allow for immediate session revocation without the overhead of distributed caching.
* **HS256 Encryption**: Use HS256 for JWT signing with a 256-bit cryptographically secure secret. Do not overcomplicate with RS256 unless third-party external verification is strictly required by the architecture.

## **2\. Multi-Client Token Storage Matrices**

* **Next.js 14 (Web)**: JWTs MUST be stored in HttpOnly, Secure, SameSite=Lax cookies. localStorage is explicitly banned for tokens to prevent XSS exfiltration.
* **React Native (Mobile)**: JWTs MUST be stored in expo-secure-store or equivalent OS-level secure enclaves. Transmit via Authorization: Bearer \<token\>.
* **Chrome Extension (MV3)**: JWTs MUST be stored in chrome.storage.session. Transmit via Authorization: Bearer \<token\>.

## **3\. Defense Against Middleware Bypass (CVE-2025-29927)**

* **Zero-Trust UI Boundaries**: Next.js middleware.ts can be used for UX redirects, but NEVER as the sole security gate. All Server Actions and Server Components MUST cryptographically verify the session token directly via a Data Access Layer before accessing sensitive data or executing mutations.

## **4\. CORS and Edge Security**

* **Strict CORS Constraints**: CORSMiddleware in FastAPI must explicitly define allow\_origins via environment variables. Using allow\_origins=\["\*"\] combined with allow\_credentials=True is an insta-fail vulnerability.
* **Next.js CSP**: Implement a middleware that injects a cryptographically secure x-nonce into the Content-Security-Policy header. Force dynamic rendering for protected routes to support nonce generation.
* **FastAPI Security Headers**: Use ASGI middleware to inject precomputed strings for Strict-Transport-Security, X-Content-Type-Options: nosniff, and X-Frame-Options: DENY.

## **5\. Internal Services & External Integrations**

* **Coolify Network Auth**: Internal microservices communicating over the private Docker network must authenticate using an X-Internal-Token header validated against a shared SERVICE\_INTERNAL\_SECRET\_KEY to prevent lateral RCE attacks.
* **Transactional Emails**: Use Postmark for password resets and verification flows to ensure absolute deliverability and minimal latency. Avoid shared-pool MTAs like Resend.
* **Base Images**: Dockerfiles must use slim-bookworm. Alpine Linux is mathematically banned due to MUSL compilation overhead on ARM64.

## **6\. final\_gate.py CI/CD Enforcement**

* **AST Check**: allow\_origins=\["\*"\] fails the build if allow\_credentials=True.
* **AST Check**: set\_cookie must explicitly declare httponly=True and secure=True.
* **AST/Regex Check**: Next.js Server Actions ("use server") must invoke auth validation functions.
* **Regex Check**: Prohibit localStorage.setItem('token' in all frontend codebases.
* **Regex Check**: Prohibit FROM alpine in all Dockerfiles.

#### **Works cited**

1. Best Practices When Using JWTs With Web and Mobile Apps \- Duende Software, accessed March 31, 2026, [https://duendesoftware.com/learn/best-practices-using-jwts-with-web-and-mobile-apps](https://duendesoftware.com/learn/best-practices-using-jwts-with-web-and-mobile-apps)
2. Handling Authentication and Authorization with FastAPI and Next.js \- David Crimi, accessed March 31, 2026, [https://www.david-crimi.com/blog/user-auth](https://www.david-crimi.com/blog/user-auth)
3. JWT Storage in React: Local Storage vs Cookies Security Battle \- Cyber Sierra, accessed March 31, 2026, [https://cybersierra.co/blog/react-jwt-storage-guide/](https://cybersierra.co/blog/react-jwt-storage-guide/)
4. Comparing JWT Authentication Strategies: HTTP-Only Cookies vs LocalStorage | by Nijat Aliyev | Medium, accessed March 31, 2026, [https://medium.com/@developer.nijat/comparing-jwt-authentication-strategies-http-only-cookies-vs-localstorage-05254ed99722](https://medium.com/@developer.nijat/comparing-jwt-authentication-strategies-http-only-cookies-vs-localstorage-05254ed99722)
5. Best Practices of using Authentication (OAuth, JWT, Firebase Auth) in React Native Projects, accessed March 31, 2026, [https://medium.com/@tusharkumar27864/best-practices-of-using-authentication-oauth-jwt-firebase-auth-in-react-native-projects-2c8d03cc45d1](https://medium.com/@tusharkumar27864/best-practices-of-using-authentication-oauth-jwt-firebase-auth-in-react-native-projects-2c8d03cc45d1)
6. JWT Chrome Extension: Decode, Debug & Secure Your Tokens Effortlessly – Master API Authentication Now\! \- CodeGive, accessed March 31, 2026, [https://codegive.com/blog/jwt\_chrome\_extension.php](https://codegive.com/blog/jwt_chrome_extension.php)
7. Next.js Security Best Practices: Complete 2026 Guide \- Authgear, accessed March 31, 2026, [https://www.authgear.com/post/nextjs-security-best-practices](https://www.authgear.com/post/nextjs-security-best-practices)
8. CVE-2025-29927: Next.js Middleware Authorization Bypass \- Technical Analysis, accessed March 31, 2026, [https://projectdiscovery.io/blog/nextjs-middleware-authorization-bypass](https://projectdiscovery.io/blog/nextjs-middleware-authorization-bypass)
9. 10 FastAPI CORS Fixes That Saved My Frontend | by Bhagya Rana \- Medium, accessed March 31, 2026, [https://medium.com/@bhagyarana80/10-fastapi-cors-fixes-that-saved-my-frontend-c508ad61ac8f](https://medium.com/@bhagyarana80/10-fastapi-cors-fixes-that-saved-my-frontend-c508ad61ac8f)
10. How to set a Content Security Policy (CSP) for your Next.js application, accessed March 31, 2026, [https://nextjs.org/docs/app/guides/content-security-policy](https://nextjs.org/docs/app/guides/content-security-policy)
11. better-auth vs NextAuth vs Clerk — Authentication Comparison 2026 | supastarter, accessed March 31, 2026, [https://supastarter.dev/blog/better-auth-vs-nextauth-vs-clerk](https://supastarter.dev/blog/better-auth-vs-nextauth-vs-clerk)
12. The Complete Guide to Authentication Tools for Next.js Applications (2025) \- Clerk, accessed March 31, 2026, [https://clerk.com/articles/authentication-tools-for-nextjs](https://clerk.com/articles/authentication-tools-for-nextjs)
13. Building Scalable Authentication in Next.js: Complete 2025 Developer Guide \- Clerk, accessed March 31, 2026, [https://clerk.com/articles/building-scalable-authentication-in-nextjs](https://clerk.com/articles/building-scalable-authentication-in-nextjs)
14. User Authentication for Next.js: Top Tools and Recommendations for 2025 \- Clerk, accessed March 31, 2026, [https://clerk.com/articles/user-authentication-for-nextjs-top-tools-and-recommendations-for-2025](https://clerk.com/articles/user-authentication-for-nextjs-top-tools-and-recommendations-for-2025)
15. NextAuth.js 2025: Secure Authentication for Next.js Apps \- Strapi, accessed March 31, 2026, [https://strapi.io/blog/nextauth-js-secure-authentication-next-js-guide](https://strapi.io/blog/nextauth-js-secure-authentication-next-js-guide)
16. Secure Authentication and Authorization with Next.js, Next-auth, and FastAPI Backend using MongoDB Adapter \#7148 \- GitHub, accessed March 31, 2026, [https://github.com/nextauthjs/next-auth/discussions/7148](https://github.com/nextauthjs/next-auth/discussions/7148)
17. Top 5 authentication solutions for secure FastAPI apps in 2026 \- WorkOS, accessed March 31, 2026, [https://workos.com/blog/top-authentication-solutions-fastapi-2026](https://workos.com/blog/top-authentication-solutions-fastapi-2026)
18. Best auth system for React \+ FastAPI? BetterAuth or something else? \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/FastAPI/comments/1mzt6rm/best\_auth\_system\_for\_react\_fastapi\_betterauth\_or/](https://www.reddit.com/r/FastAPI/comments/1mzt6rm/best_auth_system_for_react_fastapi_betterauth_or/)
19. RS256 vs HS256 \- Understanding the Difference in JWT Signing \- SuperTokens, accessed March 31, 2026, [https://supertokens.com/blog/rs256-vs-hs256](https://supertokens.com/blog/rs256-vs-hs256)
20. RS256 vs HS256: What's the difference? \- Stack Overflow, accessed March 31, 2026, [https://stackoverflow.com/questions/39239051/rs256-vs-hs256-whats-the-difference](https://stackoverflow.com/questions/39239051/rs256-vs-hs256-whats-the-difference)
21. JWT Algorithm Confusion: Turning RS256 Tokens into HS256 Disasters | by InstaTunnel, accessed March 31, 2026, [https://medium.com/@instatunnel/jwt-algorithm-confusion-turning-rs256-tokens-into-hs256-disasters-db1923774873](https://medium.com/@instatunnel/jwt-algorithm-confusion-turning-rs256-tokens-into-hs256-disasters-db1923774873)
22. JWT Security Best Practices for 2025, accessed March 31, 2026, [https://jwt.app/blog/jwt-best-practices](https://jwt.app/blog/jwt-best-practices)
23. What are the reasons that I should use JWTs instead of cookie based authentication?, accessed March 31, 2026, [https://www.reddit.com/r/AskProgramming/comments/1qz0gvu/what\_are\_the\_reasons\_that\_i\_should\_use\_jwts/](https://www.reddit.com/r/AskProgramming/comments/1qz0gvu/what_are_the_reasons_that_i_should_use_jwts/)
24. Building a Secure JWT Authentication System with FastAPI and Next.js \- Medium, accessed March 31, 2026, [https://medium.com/@sl\_mar/building-a-secure-jwt-authentication-system-with-fastapi-and-next-js-301e749baec2](https://medium.com/@sl_mar/building-a-secure-jwt-authentication-system-with-fastapi-and-next-js-301e749baec2)
25. Refresh Tokens & JWT Expiry: The Complete Guide with Spring Boot and React | by Vishwanath Patil | Medium, accessed March 31, 2026, [https://medium.com/@vishipatil/refresh-tokens-jwt-expiry-the-complete-guide-with-spring-boot-and-react-749674551005](https://medium.com/@vishipatil/refresh-tokens-jwt-expiry-the-complete-guide-with-spring-boot-and-react-749674551005)
26. JWT vs Cookies in Next.js: What Should We Really Use for Authentication?, accessed March 31, 2026, [https://dev.to/anurag112/jwt-vs-cookies-in-nextjs-what-should-we-really-use-for-authentication-603](https://dev.to/anurag112/jwt-vs-cookies-in-nextjs-what-should-we-really-use-for-authentication-603)
27. JWT Best Practices for Secure Authentication in 2025 | by Muhammad Raihan Rahman, accessed March 31, 2026, [https://medium.com/@raihanr090/jwt-best-practices-for-secure-authentication-in-2025-aa514099d9af](https://medium.com/@raihanr090/jwt-best-practices-for-secure-authentication-in-2025-aa514099d9af)
28. 5 Key Differences Between JWT and JSCookies \- Strapi, accessed March 31, 2026, [https://strapi.io/blog/differences-between-jwt-and-jscookies](https://strapi.io/blog/differences-between-jwt-and-jscookies)
29. Seamless Authentication solution with cookies and JWT in Next.js and Express Backend., accessed March 31, 2026, [https://medium.com/@mohdjamikhann/seamless-authentication-solution-with-cookies-and-jwt-in-next-js-and-express-backend-f8c0bc9d079c](https://medium.com/@mohdjamikhann/seamless-authentication-solution-with-cookies-and-jwt-in-next-js-and-express-backend-f8c0bc9d079c)
30. HttpOnly cookies-based authentication : r/reactnative \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/reactnative/comments/r44r4i/httponly\_cookiesbased\_authentication/](https://www.reddit.com/r/reactnative/comments/r44r4i/httponly_cookiesbased_authentication/)
31. Secure Authentication in React Native: Best Practices & Implementation Guide, accessed March 31, 2026, [https://iamhusnain.com/blog/secure-authentication-react-native/](https://iamhusnain.com/blog/secure-authentication-react-native/)
32. Understanding Chrome Extensions: A Developer's Guide to Manifest V3 \- DEV Community, accessed March 31, 2026, [https://dev.to/javediqbal8381/understanding-chrome-extensions-a-developers-guide-to-manifest-v3-233l](https://dev.to/javediqbal8381/understanding-chrome-extensions-a-developers-guide-to-manifest-v3-233l)
33. Manifest V2 vs Manifest V3 (Chrome Extensions): What Changed, and Why 2025 Was the Turning Point | by mossab \- Medium, accessed March 31, 2026, [https://medium.com/@idmossab/nifest-v2-vs-manifest-v3-chrome-extensions-what-changed-and-why-2025-was-the-turning-point-53b031b70fc6](https://medium.com/@idmossab/nifest-v2-vs-manifest-v3-chrome-extensions-what-changed-and-why-2025-was-the-turning-point-53b031b70fc6)
34. Chrome Extension (Manifest v3) \- using Auth0 in a secure manner, accessed March 31, 2026, [https://community.auth0.com/t/chrome-extension-manifest-v3-using-auth0-in-a-secure-manner/125433](https://community.auth0.com/t/chrome-extension-manifest-v3-using-auth0-in-a-secure-manner/125433)
35. Cookie-based Authentication for your Browser Extension and Web App (MV3), accessed March 31, 2026, [https://boryssey.medium.com/cookie-based-authentication-for-your-browser-extension-and-web-app-mv3-4837d7603f54](https://boryssey.medium.com/cookie-based-authentication-for-your-browser-extension-and-web-app-mv3-4837d7603f54)
36. Complete Authentication Guide for Next.js App Router in 2025 \- Clerk, accessed March 31, 2026, [https://clerk.com/articles/complete-authentication-guide-for-nextjs-app-router](https://clerk.com/articles/complete-authentication-guide-for-nextjs-app-router)
37. Guides: Authentication \- Next.js, accessed March 31, 2026, [https://nextjs.org/docs/pages/guides/authentication](https://nextjs.org/docs/pages/guides/authentication)
38. Guides: Data Security \- Next.js, accessed March 31, 2026, [https://nextjs.org/docs/app/guides/data-security](https://nextjs.org/docs/app/guides/data-security)
39. Building authentication in Next.js App Router: The complete guide for 2026 \- WorkOS, accessed March 31, 2026, [https://workos.com/blog/nextjs-app-router-authentication-guide-2026](https://workos.com/blog/nextjs-app-router-authentication-guide-2026)
40. The Ultimate Guide to CORS: Making Your Web Apps Play Nice \- Medium, accessed March 31, 2026, [https://medium.com/@ashishpandey2062/the-ultimate-guide-to-cors-making-your-web-apps-play-nice-e86703222228](https://medium.com/@ashishpandey2062/the-ultimate-guide-to-cors-making-your-web-apps-play-nice-e86703222228)
41. Blocked by CORS in FastAPI? Here's How to Fix It \- David Muraya, accessed March 31, 2026, [https://davidmuraya.com/blog/fastapi-cors-configuration/](https://davidmuraya.com/blog/fastapi-cors-configuration/)
42. CORS (Cross-Origin Resource Sharing) \- FastAPI, accessed March 31, 2026, [https://fastapi.tiangolo.com/tutorial/cors/](https://fastapi.tiangolo.com/tutorial/cors/)
43. FastAPI: Configuring CORS for Python's ASGI Framework \- StackHawk, accessed March 31, 2026, [https://www.stackhawk.com/blog/configuring-cors-in-fastapi/](https://www.stackhawk.com/blog/configuring-cors-in-fastapi/)
44. Capacitor 6.1.x on both Android and iOS http connection always return CORS error, accessed March 31, 2026, [https://stackoverflow.com/questions/78711402/capacitor-6-1-x-on-both-android-and-ios-http-connection-always-return-cors-error](https://stackoverflow.com/questions/78711402/capacitor-6-1-x-on-both-android-and-ios-http-connection-always-return-cors-error)
45. How to fix CORS issue when using capacitor for an ios app? \- Okta Support, accessed March 31, 2026, [https://support.okta.com/help/s/question/0D51Y00008j8b9sSAA/how-to-fix-cors-issue-when-using-capacitor-for-an-ios-app?language=en\_US](https://support.okta.com/help/s/question/0D51Y00008j8b9sSAA/how-to-fix-cors-issue-when-using-capacitor-for-an-ios-app?language=en_US)
46. How to configure CORS to allow a Chrome Extension in FastAPI? \- Stack Overflow, accessed March 31, 2026, [https://stackoverflow.com/questions/76766436/how-to-configure-cors-to-allow-a-chrome-extension-in-fastapi](https://stackoverflow.com/questions/76766436/how-to-configure-cors-to-allow-a-chrome-extension-in-fastapi)
47. FastAPI Security Headers That Don't Slow You Down | by Nexumo \- Medium, accessed March 31, 2026, [https://medium.com/@Nexumo\_/fastapi-security-headers-that-dont-slow-you-down-7c8ac864a5ee](https://medium.com/@Nexumo_/fastapi-security-headers-that-dont-slow-you-down-7c8ac864a5ee)
48. Content-Security-Policy (CSP) Header Quick Reference, accessed March 31, 2026, [https://content-security-policy.com/](https://content-security-policy.com/)
49. Content Security Policy (CSP) in Next.js \- how to pass it to full application? \- Stack Overflow, accessed March 31, 2026, [https://stackoverflow.com/questions/77153136/content-security-policy-csp-in-next-js-how-to-pass-it-to-full-application](https://stackoverflow.com/questions/77153136/content-security-policy-csp-in-next-js-how-to-pass-it-to-full-application)
50. Next Js Content-Security-Policy , script-src requires 'unsafe-inline' in production \#81703, accessed March 31, 2026, [https://github.com/vercel/next.js/discussions/81703](https://github.com/vercel/next.js/discussions/81703)
51. How to Secure FastAPI Applications Against OWASP Top 10 \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2025-01-06-fastapi-owasp-security/view](https://oneuptime.com/blog/post/2025-01-06-fastapi-owasp-security/view)
52. FastAPI HSTS/HPKP/CSP Playbook: Ship Secure-by-Default APIs Without Breaking Browsers \- Medium, accessed March 31, 2026, [https://medium.com/@2nick2patel2/fastapi-hsts-hpkp-csp-playbook-ship-secure-by-default-apis-without-breaking-browsers-b8170811c1ff](https://medium.com/@2nick2patel2/fastapi-hsts-hpkp-csp-playbook-ship-secure-by-default-apis-without-breaking-browsers-b8170811c1ff)
53. Add security headers as middlewares · fastapi fastapi · Discussion \#8548 \- GitHub, accessed March 31, 2026, [https://github.com/fastapi/fastapi/discussions/8548](https://github.com/fastapi/fastapi/discussions/8548)
54. Docker Compose | Coolify Docs, accessed March 31, 2026, [https://coolify.io/docs/knowledge-base/docker/compose](https://coolify.io/docs/knowledge-base/docker/compose)
55. Security Hardening Your Coolify Server: A Production-Ready Checklist | MassiveGRID Blog, accessed March 31, 2026, [https://massivegrid.com/blog/coolify-security-hardening/](https://massivegrid.com/blog/coolify-security-hardening/)
56. Service-to-Service Communication \- SGIVU \- Mintlify, accessed March 31, 2026, [https://www.mintlify.com/stevenrq/sgivu/security/service-communication](https://www.mintlify.com/stevenrq/sgivu/security/service-communication)
57. Secrets in Compose \- Docker Docs, accessed March 31, 2026, [https://docs.docker.com/compose/how-tos/use-secrets/](https://docs.docker.com/compose/how-tos/use-secrets/)
58. Postmark vs. Resend: a detailed comparison for 2026, accessed March 31, 2026, [https://postmarkapp.com/compare/resend-alternative](https://postmarkapp.com/compare/resend-alternative)
59. Resend vs Postmark: Modern DX vs Proven Reliability (2026) \- Transmit, accessed March 31, 2026, [https://xmit.sh/versus/resend-vs-postmark](https://xmit.sh/versus/resend-vs-postmark)
60. Postmark vs Resend | Email API benchmarks \- Knock, accessed March 31, 2026, [https://knock.app/email-api-benchmarks/compare/postmark-vs-resend](https://knock.app/email-api-benchmarks/compare/postmark-vs-resend)
