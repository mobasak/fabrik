# Cookie Consent, GDPR & Data Export — 2026 Research

**Source:** Gemini Deep Research, 2026-05-26
**Purpose:** Reference for fabrik-lib cookie-consent, gdpr-data-rights, and abuse-prevention modules

---

## Cookie Consent 2026: EU and California Updates

### ePrivacy Regulation & Digital Omnibus

The regulatory framework surrounding cookies in the EU is undergoing significant structural shifts. The EU's proposed Digital Omnibus includes plans to overhaul the ePrivacy Directive's cookie consent rules to combat "banner fatigue." The new proposal aims to introduce a simplified "one-click consent" mechanism that remains valid for six months (Quaritsch, 2026). While initially targeted for August 2026 alongside provisions of the AI Act, industry lobbying may delay the full enforcement of these harmonized standards until 2028 (Quaritsch, 2026).

### Essential-Only Banner Requirements (EDPB)

Under the GDPR and ePrivacy Directive, the threshold for valid consent remains exceedingly strict. "Essential" cookies are strictly defined as those necessary for the technical delivery of a requested service (e.g., session management or security).

* **Opt-In Required:** Non-essential cookies (analytics, targeted advertising, profiling) require prior, freely given, specific, and informed opt-in consent (Mu'awya, 2026).
* **No Forced Consent:** Websites cannot force users to accept non-essential cookies as a condition of accessing content (Mu'awya, 2026).
* **Reject All:** European Data Protection Board (EDPB) guidelines require that rejecting cookies must be as easy as accepting them. Deliberate user interface obstructions—such as hiding the "Reject All" button or requiring users to navigate multiple layers to opt out—are classified as illegal dark patterns and are heavily targeted by regulators (Farronato, 2026; Van Hofslot et al., 2022).

### CCPA & CPRA Updates

Historically, the California Consumer Privacy Act (CCPA) and the California Privacy Rights Act (CPRA) operated on a "Do Not Sell/Share" opt-out model, allowing businesses to fire tracking scripts as soon as a page loaded. However, recent litigation under the California Invasion of Privacy Act (CIPA) has upended this standard. Plaintiffs successfully argued that third-party analytics pixels and session replay tools that activate before a user provides consent constitute illegal "wiretapping" (Snyder, 2026). Consequently, to mitigate CIPA liability, California is practically shifting toward a strict EU-style opt-in model, requiring businesses to block all tracking technologies until explicit consent is recorded (Snyder, 2026).

---

## Disposable Email Source Verification

If you are validating user registrations against temporary or "burner" email providers, community-maintained lists on GitHub remain the industry standard.

* **Repository Status:** The most widely used repository is `ivolo/disposable-email-domains` (and its active forks, such as `martenson/disposable-email-domains`). These repositories are actively maintained via community pull requests as new disposable providers spin up.
* **File Formats:** The standard distribution formats are machine-readable arrays. The repositories typically export an `index.json` file containing a flat array of domain strings (e.g., `["mailinator.com", "10minutemail.com"]`) and an `index.txt` file featuring newline-separated domains, making them trivial to load into server-side validation logic or caching layers.

---

## GDPR Data Export: Article 20 & Retention

### Article 20 Format Requirements

Article 20 of the GDPR (Right to Data Portability) explicitly mandates that organizations must provide a user's personal data in a "structured, commonly used and machine-readable format."

* The regulation avoids mandating proprietary extensions, but **JSON** and **CSV** are the universally accepted industry standards for compliance, as they ensure data interoperability and can be parsed programmatically (Brezac, 2025).
* XML is also acceptable, though JSON is preferred for nested, document-based user data.

### Retention TTL Best Practices

When a user requests a data export, the system typically compiles the information into an object storage bucket (e.g., AWS S3) and provides the user with a secure download link.

* **Data Minimization:** Under the GDPR's data minimization and "right to be forgotten" principles, organizations must actively manage data destruction (Reis, 2021).
* **TTL Implementation:** Best practice requires assigning a strict Time-to-Live (TTL) lifecycle policy to the generated export files. A standard TTL is **7 to 14 days**. Once the TTL expires, the cloud storage layer automatically hard-deletes the export file, ensuring that the exported data does not sit unmonitored in an intermediate bucket indefinitely (Reis, 2021).

---

## Key Takeaways for fabrik-lib Modules

### cookie-consent/ module implications
- **Essential-only sites (our case):** Strictly necessary cookies do NOT require consent under ePrivacy. However, showing an informational banner builds trust and future-proofs for when analytics are added.
- **Design:** "Accept" + "Reject All" must be equally prominent (no dark patterns). One-click mechanism. Consent valid 6 months (upcoming EU standard).
- **California:** Treat as opt-in (block non-essential until consent) due to CIPA litigation shift.

### abuse-prevention/ module implications
- **Disposable domain source:** Use `ivolo/disposable-email-domains` or `martenson/disposable-email-domains` fork. Download `index.json` or newline-separated text file.

### gdpr-data-rights/ module implications
- **Export format:** JSON is the standard (structured, machine-readable, Article 20 compliant). CSV acceptable as alternative.
- **Export file TTL:** 7-14 days, auto-delete from storage after expiry.
- **Export delivery:** Generate → store in B2/S3 → send download link via email → auto-delete after TTL.

---

## References

Brezac, N. (2025). Izbiranje sistema za upravljanje z grafnimi podatkovnimi bazami. Cited by: 1

Farronato, C. (2026). Designing Consent: Choice Architecture and Consumer Welfare in Data Sharing. Cited by: 5

Mu'awya, N. (2026). Automated evaluation of cookie consent and GDPR compliance in educational websites. Cited by: 0

Quaritsch, L. (2026). The EU's Digital Omnibus is Heading in the Wrong Direction. Cited by: 0

Reis, J. (2021). Fundamentals of Data Engineering. Cited by: 146

Snyder, J. D. (2026). Thanks to CIPA Lawsuits, California May Already Be an Opt-In Jurisdiction for Web Tracking. Cited by: 0

Van Hofslot, M., Akdag Salah, A., Gatt, A., & Santos, C. (2022). Automatic Classification of Legal Violations in Cookie Banner Texts. Proceedings of the Natural Legal Language Processing Workshop 2022. https://doi.org/10.18653/v1/2022.nllp-1.27 Cited by: 8
