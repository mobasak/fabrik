# saas-skeleton legal pages that pass Paddle onboarding — design spec

Status: BLOCKED — waiting on fabrik-lib's legal-content module (mail 01M3QDBVWD676SD9KGNKP3T2R6)
Split (operator 2026-09-29, "ok proceed"; supersedes D-446's scope): the legal TEXT (Terms, Privacy,
Refund, Cookies, the Paddle reseller clause, KVKK Art. 10, the fill-in markers) is designed and owned by
fabrik-lib; this hub spec is re-cut to the scaffold wiring only — vendor the module, four force-dynamic
routes, server-only `LEGAL_*` runtime config, the links on every marketing page, the docs-site pointers
and the scaffold tests — once fabrik-lib names the module's public interface. Until then the content
sections below (§ Constraints digest, § Config values, § The pages) stand as the REQUIREMENTS handed to
fabrik-lib, not as a hub build.
Profile: full (two of the four pages, `/refund` and `/cookies`, have no code behind them today)
Mail: 01M39AJE8MAJJKX0N1YYD0J56D (fleet, claimed 2026-09-29) · work item W-78319f3d
Research ledger: `docs/reference/research/2026-09-29-saas-skeleton-legal-pages-ledger.md` (59 rows)

## Personas

- **Primary — the seller launching a SaaS from the scaffold.** In the operator's words: *"the
  saas-skeleton finding that its placeholder /terms and /privacy pages fail Paddle onboarding"*. The
  seller is the Fabrik operator (or the agent in the project repo acting for them) taking a freshly
  scaffolded `saas-skeleton` project to its first paid sale through Paddle. The seller may be a
  company or a sole proprietor (pd-14).
- **The buyer** — reads Terms, Refund and Privacy before paying; a TR, EU or UK consumer has a
  statutory withdrawal right the pages must not contradict.
- **The Paddle reviewer** (human or automated) — the domain review checks for Terms, Refund Policy,
  Privacy Policy and the company name in the Terms (pd-01); the seller handbook separately requires
  the reseller clause and a support email and phone (pd-12, pd-15).
- **The data subject** — any visitor whose personal data the app processes; for a TR entity the
  KVKK Art. 10 notice is owed to them.
- **Automated consumers:** the scaffolder (`src/fabrik/scaffold.py` copies `templates/saas-skeleton/`
  into every new project and vendors fabrik-lib's docs-site — it holds the duty of emitting the pages
  and the docs-site pointers); the project's coding agent (holds the duty of filling the config values,
  guided by `.env.example`); the Next.js server (renders the pages per request from runtime env).

**The primary's loop, counted — STEP BUDGET 4:** (1) scaffold the project; (2) set the nine
required `LEGAL_*` values in `.env`; (3) deploy; (4) submit the domain to Paddle, which finds all four pages
linked from every marketing page. Every feature below traces to one of these personas.

## Goal

Every new `saas-skeleton` project emits four real legal pages — `/terms`, `/privacy`, `/refund`,
`/cookies` — that meet Paddle's domain review and seller handbook on the seller's own domain, carry
the seller's company values from one typed config read at runtime, and replace today's boilerplate;
the docs site the same scaffold vendors carries no second, contradicting legal text.

## Why this exists

`templates/saas-skeleton/app/(marketing)/terms/page.tsx:26-27` grants *"personal, non-commercial
transitory viewing only"* and has no billing, refund, termination, liability or governing-law clause;
`:16` renders "Last updated" as the render date (`new Date()`); there is no `/refund` and no `/cookies`
route; only the landing page links Terms and Privacy (`app/(marketing)/page.tsx:93-94`). Paddle's
account verification requires a pricing page, Terms, Privacy and Refund Policy (ledger pd-06), its
domain review requires them "clearly accessible via navigation" with the company name in the Terms
(pd-01), and its handbook requires the verbatim reseller clause and a support email and phone
(pd-12, pd-15). A project that ships today's pages fails onboarding (mail 01M39AJE), and a paid SaaS
whose Terms say "non-commercial viewing only" contradicts its own product. The chosen approach
replaces the text, adds the two routes and links all four from every marketing page, so the pages
the reviewer opens are the real ones.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "render the scaffold's /terms and /privacy from legal-pages … instead of the boilerplate" (mail 01M39AJE) | IN | § Chosen approach, § The pages |
| I2 | "add a /refund (or refund section)" (mail) | IN | § The pages (/refund is its own route) |
| I3 | "and /cookies route to match saas/88 § Legal Pages" (mail) | IN | § The pages (/cookies) |
| I4 | "no billing, refund, termination, liability or governing-law clause" (mail) | IN | § The pages (/terms sections) |
| I5 | "the warning should become unnecessary" (saas/88 line 56, mail SYSTEMIC) | OUT-OF-SCOPE | the rule pack is infra's synced surface; W-d41bdf6e mails infra with the landing commit |
| I6 | operator: "handle all your mails one by one … including this" | IN | this spec is the handling; the build closes the mail |
| I7 | buyer accepts terms + refund before purchase (handbook, pd-19) and the post-purchase email links (pd-17) | OUT-OF-SCOPE | checkout/billing UI, not the pages; W-171d23c5 |
| I8 | TRY-lane pages: distance-sales contract, delivery/return, About, Contact (saas/88:50,56,64) | OUT-OF-SCOPE | the skeleton bills through Paddle; W-0e800dbe |
| I9 | cookie consent banner (saas/60:137, saas/88:67) | OUT-OF-SCOPE | owed only for non-essential cookies; the skeleton sets none (§ The pages, /cookies); a project that adds one vendors `cookie-consent` per saas/88:54 |
| I10 | "English ToS with an 'English version governs' clause" until a lawyer translates (saas/88:165) | IN | § The pages (/terms governing-language clause) |
| I11 | fabrik-lib docs-site `terms.md` / `cookies.md` errors (saas/88:53) | OUT-OF-SCOPE for the module text | saas/88:53 says they are "filed to fabrik-lib"; I12 keeps them off the project's domain |
| I12 | the scaffold also vendors fabrik-lib docs-site, whose `docs/legal/*.md` would put a second, contradicting Terms on the domain (review round 1, R-O4) | IN | § Chosen approach (docs-site legal pointers) |
| I13 | a `[set …]` marker can reach production with no gate before Paddle submission (review round 1, R-O7) | OUT-OF-SCOPE | a deploy-time check belongs to the parity contract; W-8bacadc0 |

Intake: 13 items — 7 IN, 6 OUT-OF-SCOPE (each named above), 0 ASK.

## Constraints digest

| # | Rule | Verbatim | Source |
|---|---|---|---|
| C1 | Paddle requirements | "Paddle's account verification requires a pricing page, Terms of Service, Privacy Policy and Refund Policy, and its seller handbook requires the Terms to carry your legal company name and this text" | `.windsurf/rules/saas/88-saas-launch-checklist.md:50` |
| C2 | Vendor, never from scratch | "Ship them before accepting payment, from the vendored templates — never from scratch" | `saas/88-saas-launch-checklist.md:50` |
| C3 | Replace the placeholders | "The `saas-skeleton` scaffold's own `app/(marketing)/terms` and `privacy` pages are generic placeholders — replace their content from `legal-pages` before launch." | `saas/88-saas-launch-checklist.md:56` |
| C4 | Terms content | "Service description, billing policy, refund policy (above), account termination, liability cap, governing law, legal company name, the Paddle reseller clause (above)." | `saas/88-saas-launch-checklist.md:60` |
| C5 | Jurisdiction | "The templates are drafted for a Turkish entity (Turkish law; `legal-pages` names Istanbul courts, the docs-site copy leaves the city blank) — wrong for a non-TR entity." | `saas/88-saas-launch-checklist.md:60` |
| C6 | Credits clause is house policy | "The credits proration clause (≤10% of credits used → full refund, above → prorated, balance zeroed) is a HOUSE credits policy, not Paddle's." | `saas/88-saas-launch-checklist.md:60` |
| C7 | KVKK notice | "for a TR entity, the KVKK Art. 10 information notice (aydınlatma metni: controller identity, purposes, recipients and transfer purposes, collection method and legal basis, the Art. 11 rights)" | `saas/88-saas-launch-checklist.md:61` |
| C8 | Refund page | "Refund Policy \| `/terms` section or `/refund`, linked from checkout" | `saas/88-saas-launch-checklist.md:62` |
| C9 | Cookie policy | "Cookie Policy \| `/cookies` \| Every cookie listed with its purpose; which are strictly necessary" | `saas/88-saas-launch-checklist.md:66` |
| C10 | Refund windows | "your terms must not promise less than the buyer terms Paddle sells under" | `saas/88-saas-launch-checklist.md:38` |
| C11 | Legal routes | "**Cookie Policy** \| `/cookies` \| EU ePrivacy" | `.windsurf/rules/saas/60-saas-ui.md:136` |
| C12 | Language | "Localized Terms of Service — translated by a lawyer, not AI. Until then: English ToS with an \"English version governs\" clause." | `saas/88-saas-launch-checklist.md:165` |
| C13 | Responsive | "Every SaaS page must be responsive from 375px to 2560px. No exceptions." | `saas/60-saas-ui.md:288` |
| C14 | Dark + light | "**Both dark and light mode are mandatory.**" | `saas/60-saas-ui.md:63` |
| C15 | Billing routing | "international → **Paddle** (MoR)" | `commands/_sources/fabrik-spec.md:150` (§ 1b-bis hard constraint) |

## External dependencies

- **Paddle domain review** — https://www.paddle.com/help/start/account-verification/what-is-domain-verification
  (fetched 2026-09-29): Terms, Refund Policy and Privacy Policy "must be clearly accessible via
  navigation on your website"; company name (or a sole proprietor's brand) in the Terms; per-domain
  approval (ledger pd-01..pd-03, pd-14).
- **Paddle seller handbook** — https://www.paddle.com/seller-guides/seller-handbook (fetched
  2026-09-29): the verbatim reseller clause; "buyer support details (email and phone number)";
  acceptance before purchase (pd-12, pd-15, pd-19).
- **Paddle Refund Policy** — https://www.paddle.com/legal/refund-policy (fetched raw 2026-09-29):
  2.1 local statutory withdrawal rights "apply and override this Policy and any Supplier policy"; 14 days
  statutory in EU/EEA/CH/UK, applying to one-off purchases and the FIRST payment under a subscription
  (2.2.2), and 14 days in TR/IL (2.3.1, which states no subscription scoping); 7 days KR/BR/CN/CA; 5 days SG; elsewhere non-refundable unless the law says
  otherwise (1.1), with a discretionary refund within 14 days that "does not guarantee a refund" (7.1);
  no refund on fraud or refund abuse (1.3); access ends on refund (1.6) (rf-01..rf-06, pd-25).
- **KVKK Law 6698 Art. 10** — https://www.mevzuat.gov.tr/mevzuatmetin/1.5.6698.pdf (fetched
  2026-09-29; rf-11).
- **Cookie information duty** — ICO, https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guide-to-pecr/cookies-and-similar-technologies/
  (fetched 2026-09-29; ap-07, ap-08); CNIL, consent withdrawal as simple as giving it (ap-09).
- **Fixed last-updated date** — 11 CCR § 7011(e)(4), https://www.law.cornell.edu/regulations/california/11-CCR-7011
  (fetched 2026-09-29; ap-11).

No runtime API, no rate limit, no pricing: the pages are server-rendered text.

## fabrik-lib verdict

| Capability | Verdict | Module | Why · upstream note |
|---|---|---|---|
| Terms + Privacy prose | VENDOR + ENHANCE (port) | `/opt/fabrik-lib/legal-pages` (`templates/terms.html`, `templates/privacy.html`) | the substantive clauses are there; the port renders them in TSX, drops the credit-pack clauses and the credits proration (C6) while keeping the subscription clauses, parameterizes jurisdiction, adds the reseller clause and the KVKK Art. 10 notice. Upstream note to fabrik-lib at build close: the reseller clause and the Art. 10 notice are missing from the module too (saas/88:56, :61) |
| Refund + Cookie prose | BUILD (small) | none covers them in-app; saas/88:53 flags the docs-site `cookies.md` as needing correction | written from the Paddle Refund Policy and the ICO duty; part of the same page set, so it rides the same upstream note |
| Cookie consent banner | not needed | `cookie-consent` | the skeleton sets only strictly necessary storage (I9) |
| docs-site legal pages | pointer only | `fabrik-lib/docs-site` (vendored by `_vendor_docs_site`, `src/fabrik/scaffold.py:4152`) | the scaffold overwrites the project copy's `docs/legal/{terms,privacy,cookies}.md` with one-paragraph pointers to the app pages (I12); the module itself is untouched |

## Chosen approach — D, typed-config TSX read at runtime

Four TSX route files under `templates/saas-skeleton/app/(marketing)/` — `terms/`, `privacy/`,
`refund/`, `cookies/` — each a thin **server component** that exports `dynamic = "force-dynamic"` and
renders its sections through one shared `components/legal/LegalPage.tsx` (header with the
product name from `lib/config/legal.ts`, title, fixed last-updated line, a body styled with explicit Tailwind utilities, and
the legal links). Every company value comes from one typed module, `lib/config/legal.ts`, which reads
**server-only** `LEGAL_*` env vars from `process.env` at request time.

**Why runtime env, not `NEXT_PUBLIC_*`:** Next.js replaces `process.env.NEXT_PUBLIC_*` with literals
at `next build`, in server code as well as client code. The template's Dockerfile runs
`npm run build` in a builder stage with no build args (`templates/saas-skeleton/Dockerfile:11-12`),
the emitted `.dockerignore` excludes `.env` from the build context, and compose passes env only to the
running container (review round 1, R-O2/F1-O1). A `NEXT_PUBLIC_LEGAL_*` value would therefore never
reach a deployed page. Server-only names read in a force-dynamic server component come from the
container's runtime env, which compose loads from the project `.env`.

**Navigation:** there is no shared marketing layout (`app/(marketing)/` has no `layout.tsx`; each page
renders its own header). A small `components/legal/LegalLinks.tsx` renders the four links and is used
by the landing footer (replacing `app/(marketing)/page.tsx:93-94`), the pricing and FAQ pages, and
`LegalPage` itself, so every marketing page links all four (pd-01).

**Styling:** `@tailwindcss/typography` is not installed (`templates/saas-skeleton/tailwind.config.ts:79`
loads only `tailwindcss-animate`), so the existing pages' `prose` classes style nothing. `LegalPage`
styles headings, lists and paragraphs with explicit utilities and the theme tokens the template already
uses, so the pages are responsive (C13) and follow dark and light mode (C14) with no new dependency.

**docs-site pointers (I12):** after `_vendor_docs_site` copies fabrik-lib's docs site into the project,
the scaffold writes `docs-site/docs/legal/terms.md`, `privacy.md` and `cookies.md` as one-paragraph
pages that link to the app's `/terms`, `/privacy`, `/refund` and `/cookies`, so the domain carries one
legal text.

Why this is the lean, field-standard shape: per-page TSX legal files are what Makerkit ships
(ap-01), and a single shared legal renderer keyed per page is what next-saas-stripe-starter ships
(ap-03); the template already has the env-backed config pattern (`lib/config/site.ts:2,4`) and no
MDX dependency. The judge panel (three blind Sonnet seats, 2026-09-29) ranked D first unanimously and
killed A (hosted generator: paid vendor where free exists, off self-host policy) and B (link-out:
another domain than the one Paddle reviews, pd-02/pd-03). Neither starter interpolates legal values
into the prose (ap-02, ap-04); doing so here is this design's own choice, made because every emitted
project must carry its own name, contact and jurisdiction and a hand-edited copy per project would drift.

### Config values

`lib/config/legal.ts` exports `getLegalConfig()` (called per request) and `LEGAL_LAST_UPDATED`:

| Key | Env var | Required | When unset |
|---|---|---|---|
| productName | `LEGAL_PRODUCT_NAME` — the product as the buyer sees it | yes (pd-14) | marker |
| serviceDescription | `LEGAL_SERVICE_DESCRIPTION` — one sentence on what the product does | yes (Terms and Privacy both describe the service) | marker |
| entityName | `LEGAL_ENTITY_NAME` — the company name, or a sole proprietor's brand (legal name preferred) | yes (pd-14) | renders `[set LEGAL_ENTITY_NAME]` |
| entityAddress | `LEGAL_ENTITY_ADDRESS` | yes (KVKK controller identity, rf-11) | marker |
| entityCountry | `LEGAL_ENTITY_COUNTRY` — ISO 3166-1 alpha-2, e.g. `TR` | yes (C5, C7) | marker; the KVKK section renders only when it is `TR` |
| supportEmail | `LEGAL_SUPPORT_EMAIL` | yes (pd-15) | marker |
| supportPhone | `LEGAL_SUPPORT_PHONE` | yes (pd-15) | marker |
| privacyEmail | `LEGAL_PRIVACY_EMAIL` | no | falls back to supportEmail |
| jurisdiction | `LEGAL_JURISDICTION` — e.g. "the Republic of Turkey" | yes (C5) | marker |
| courts | `LEGAL_COURTS` — e.g. "Istanbul, Republic of Turkey" | yes (C5) | marker |
| moneyBackDays | `LEGAL_REFUND_DAYS` | no | 14. The value must match `^[0-9]{1,3}$`; it is then clamped to 14..365, and anything else (empty, `30days`, `14.5`, `1e3`) is 14 — so the page never promises less than the statutory 14 days (rf-01, C10) |

Nine values are required. The product name and description are legal config, not `siteConfig`:
`siteConfig.name` is `NEXT_PUBLIC_APP_NAME` inlined at build time with a `"SaaS App"` fallback, and
`siteConfig.description` is the literal `"Your SaaS application description"` (`lib/config/site.ts:2-3`),
so reading either would put a placeholder on the legal pages with no marker. The remaining product values
come from code, not env: the third-party
processors are a typed list in `legal.ts` defaulting to Paddle (payments), the transactional email
provider (Resend), and OpenRouter with the upstream model vendor (the scaffolded chat route sends user
messages there — `templates/saas-skeleton/app/api/chat/route.ts:3,8`); the data categories are a typed
list defaulting to account data, usage data and chat content. A project edits the lists when it adds or
drops a processor.

**Fail-safe: a visible marker, never a build or runtime failure.** An unset required value renders a
bracketed `[set LEGAL_…]` string in place, so an unconfigured page is obviously unfinished to the seller
and to the Paddle reviewer, and a fresh scaffold still builds and runs before anyone has a company name.
A build that throws on unset values was rejected: it reddens every new project's first build and CI
before the seller has anything to put there. The marker can reach production — W-8bacadc0 adds the
deploy-time check (I13). `LEGAL_LAST_UPDATED` is a constant date string edited when the text changes
(ap-11), never the render date.

### The pages

- **/terms** — the `legal-pages` Terms (service description, user responsibility, 18+, account
  termination, data processing, liability cap, changes, contact) with: billing stated for monthly
  subscriptions (renews monthly; cancel any time with access to the end of the paid period; price changes
  announced before the next cycle — pd-20); refunds by pointer to `/refund`; the **Paddle reseller
  clause verbatim** (pd-12) plus a link to Paddle's Buyer Terms (pd-13); the entity name (pd-14);
  support email and phone (pd-15, pd-18); governing law and courts from config (C5); "English version
  governs" (C12).
- **/privacy** — the `legal-pages` Privacy (data collected, use, retention, third parties, cookies
  pointer, rights, GDPR basis, CCPA "we do not sell or share", updates) with the processors and data
  categories from § Config values, and — when `LEGAL_ENTITY_COUNTRY` is `TR` — a **KVKK Art. 10 notice**
  carrying the five items (rf-11): controller identity (entity name + address), purposes, recipients and
  transfer purposes, collection method and legal basis, the Art. 11 rights (C7).
- **/refund** — the seller's **unconditional** money-back guarantee: a full refund on request within
  `moneyBackDays` days of a one-off purchase or of the first payment of a subscription (the scope 2.2.2 gives
  the EU/EEA/CH/UK statutory right; TR/IL's 2.3.1 and every other statutory right still apply through 2.1), with no usage condition (C6, pd-28); renewals can be cancelled at any
  time and run to the end of the paid period. Then Paddle's rules as Paddle states them: statutory
  withdrawal rights where local law grants them apply and override this policy (2.1), with a link to
  Paddle's Refund Policy for the windows by market (rf-01..rf-04, pd-23); access ends when a refund is
  issued (1.6). How to ask:
  paddle.net or the support email (Paddle handles returns — the reseller clause). The page states no
  waiver, no TR instant-performance exception and no fraud or refund-abuse exception: a seller who grants
  at least 14 days never relies on the first two, so neither the consent waiver (rf-06) nor the md. 5(1)(h)
  notice (rf-10) is owed, and Paddle applies its own 1.3 refusal through the linked policy whether or not
  the page repeats it — repeated beside an unconditional guarantee it is a qualifier (pd-28).
- **/cookies** — every cookie and storage key the skeleton sets, each strictly necessary:

  | Name (over HTTPS) | Set by | Purpose | Duration |
  |---|---|---|---|
  | `__Host-session` | `fastapi-user-auth` (`cookies.py:35`) | the signed-in session | 15 minutes (`access_ttl_seconds`, `settings.py:18`) |
  | `__Host-refresh` | `fastapi-user-auth` (`cookies.py:36`) | renews the session | 7 days (`refresh_ttl_seconds`, `settings.py:19`) |
  | `__Host-csrf_token` | `fastapi-user-auth` (`cookies.py:37`) | cross-site request protection | 7 days (same TTL) |
  | `__Host-plbind` | `fastapi-user-auth` (`binding.py:39`) | ties a passwordless sign-in to the browser that started it | 5 minutes (`passwordless_code_ttl_s`, `settings.py:39`) |
  | `lang` | the i18n kit (`templates/i18n-kit/react/I18nProvider.tsx:121`) | the chosen interface language | 1 year |
  | `theme` (localStorage) | read by the root layout (`templates/saas-skeleton/app/layout.tsx:18`); the skeleton ships no control that writes it — a project that adds a theme toggle writes this key | dark or light mode | until cleared |

  The `__Host-` prefix is present only when the IdP runs with `session_cookie_secure` (the default,
  `settings.py:27`); a local HTTP run uses the bare names. The page states that there are no third-party
  or analytics cookies, and that a project which adds a non-essential cookie must add the consent banner
  (I9), list the cookie here, and make withdrawing consent as simple as giving it (ap-07..ap-09). The
  durations are re-read from the vendored modules when the page is built.

## Rejected alternatives

- **A — hosted generator (Termly/iubenda/TermsFeed):** recurring vendor cost for static text the
  platform already owns, a third-party script on pages Paddle audits, and no native place for the
  verbatim reseller clause — killed by the panel.
- **B — link out to a Docusaurus docs site:** a different (sub)domain from the one Paddle approves
  (pd-02, pd-03), a second deploy, and it inherits the docs-site legal text saas/88:53 says needs
  correcting — killed by the panel.
- **C — MDX content files + one renderer:** field-standard (ap-03) but adds an MDX dependency to every
  project's `package.json` and a substitution pass to put config values in prose, for four fixed pages —
  ranked second, not chosen.
- **`NEXT_PUBLIC_*` config:** inlined at build, which the Docker build never feeds (§ Chosen approach).
- **Refund as a section of /terms instead of a route:** allowed (C8). Paddle's domain review lists the
  Refund Policy beside the Terms and Privacy Policy as items reachable through navigation (pd-01), and
  no primary page settles separate-page versus section (pd-22); a route is chosen because it satisfies
  both readings and gives checkout (W-171d23c5) one URL to link.
- **A build failure on unset values:** rejected in § Config values.
- **Keeping the credits proration clause:** a house credits policy (C6), the skeleton bills
  subscriptions, and a usage-qualified refund is reported to fail Paddle review (pd-28, non-primary).
- **Stating the waiver, the TR instant-performance exception or Paddle's 1.3 fraud refusal on /refund:** a qualifier beside an
  unconditional guarantee reads as a contradiction and is what pd-28 reports Paddle rejecting; the
  guarantee makes the first two unnecessary, and Paddle applies its 1.3 refusal through the linked
  policy whether or not the page repeats it (§ The pages).
- **Rendering the legal-pages Jinja fragments server-side:** the skeleton's frontend is Next.js with no
  Jinja runtime; the fragments use Bootstrap classes the template does not load.
- **Adding `@tailwindcss/typography`:** one more dependency in every project for four pages the explicit
  utilities style as well.

## Lifecycle

- **Adoption / first run:** every new saas-skeleton project gets the pages; until the seller sets the
  values they show `[set …]` markers, which is the signal to fill `.env` before submitting the domain.
- **Existing projects:** not touched — the scaffold only emits into new projects; a project that wants
  the pages copies the four routes, the two components and the config module (the build's receipt names
  them).
- **Change:** a seller changing a value edits `.env` and restarts the container (no rebuild — the values
  are read at runtime); changing the text edits the TSX and bumps `LEGAL_LAST_UPDATED`; Paddle must be
  told of refund-policy or contact changes (pd-16). Review the pages at least yearly (ap-12).
- **Growth triggers:** a TRY-lane launch needs the distance-sales pages (W-0e800dbe); a non-essential
  cookie needs the consent banner (I9); a new processor adds a row to the processors list; a lawyer's
  translation replaces the English-governs clause (C12).
- **Degradation:** there is no external runtime dependency; the pages fail only if the app does.
- **Retirement:** superseded if fabrik-lib ships a Next.js-native legal module — the ports then become a
  vendored copy of it.

## Shape / infra implications

Scaffold type `saas-skeleton` only. No `shape:` flag changes (no DB, cache, metrics or search); no new
service, port or npm dependency. Eleven server-only env vars land in `templates/saas-skeleton/.env.example`;
the frontend container already loads the project `.env` at runtime.

## Documentation landing sites

- `templates/saas-skeleton/.env.example` — the eleven `LEGAL_*` vars, one comment each.
- `docs/workflows/SCAFFOLD_STRUCTURE.md` — the saas-skeleton tree gains the four routes, the two
  components, the config module and the docs-site pointer pages.
- `CHANGELOG.md` — one Added entry at build.
- `docs/DECISIONS.md` — the design's D-row at approval.

## Validation

Executable checks the build owes:

1. **Emitted files** — scaffold into a temp dir with
   `create_project("legal-probe", "probe", base=tmp, project_type="saas-skeleton", generate_spec=False)`
   (the conftest pins `FABRIK_SCAFFOLD_OFFLINE=1`) and assert: `app/(marketing)/{terms,privacy,refund,cookies}/page.tsx`
   exist and each contains `export const dynamic = "force-dynamic"`; `terms/page.tsx` contains the reseller
   clause string byte-for-byte and not the string `non-commercial`; no legal page contains `new Date(` or
   `NEXT_PUBLIC_LEGAL`; `refund/page.tsx` contains none of `consumed`, `prorat`, `credits`; `cookies/page.tsx`
   names `session`, `refresh`, `csrf_token`, `plbind`, `lang` and `theme`; `LegalLinks` is imported by the
   landing, pricing and FAQ pages; `docs-site/docs/legal/{terms,privacy,cookies}.md` each link their
   route, and `terms.md` no longer contains `Singapore` — the test first asserts the vendored source
   (`/opt/fabrik-lib/docs-site/docs/legal/terms.md`, whose refund sentence names Singapore) contains it,
   so the check fails if the pointer rewrite never runs.
2. **Config semantics** — a unit test of `lib/config/legal.ts` compiled with the template's TypeScript
   (`npx tsc` on the one module, then `node`) asserting: a missing required value yields
   `[set LEGAL_ENTITY_NAME]`; `LEGAL_REFUND_DAYS` of `7`, `30days`, `14.5` and `1e3` yields 14, `30`
   yields 30, `900` yields 365; the KVKK flag is true only for `LEGAL_ENTITY_COUNTRY=TR`.
3. **Runtime read** — the plan's integration step builds the emitted app (`npm ci && npm run build`)
   with NO `LEGAL_*` set, starts it with them set, and asserts `GET /terms` shows the configured entity
   and product names and no `[set ` marker — proving the values are read at runtime, not inlined.

## Constraints

English-only prose (C12); no new npm dependency; explicit Tailwind utilities, responsive (C13) and dark
and light safe (C14); the reseller clause string is a constant, never config; the legal routes are
server components and never read `NEXT_PUBLIC_*` for company values.

## Open / blocking unknowns

- **U1 (resolved by choice):** separate refund page vs section — no primary source decides it (pd-22); the
  route satisfies both readings (§ Rejected alternatives).
- **U2 (open, non-blocking):** whether Paddle's Buyer Terms forbid seller terms that promise less
  (pd-26 is summary-only). Resolution: the design never promises less — the guarantee floors at 14 days
  and Paddle's statutory windows are stated as overriding it — so the answer cannot change the build.
- **U3 (closed):** the Planet49 paragraph on cookie duration could not be fetched verbatim (eur-lex
  served a challenge page; ap-10). The cookie table lists durations anyway, on the ICO's good-practice
  guidance (ap-08), so no clause of this design rests on it.
- **Not legal advice.** The ported text inherits the legal-pages module's disclaimer
  (`/opt/fabrik-lib/legal-pages/README.md:20`): the seller has counsel confirm before launch
  (saas/88:17).

## Decisions taken

- D (typed-config TSX) over A/B/C — panel-unanimous, recorded at approval as a D-row.
- Company values are server-only `LEGAL_*` env vars read per request; the routes are force-dynamic.
- Refund as its own route; an unconditional money-back guarantee floored at 14 days, with Paddle's
  statutory rules stated as overriding it.
- Visible marker, not a build failure, for unset values; the deploy-time check is W-8bacadc0.
- Entity country is required; the KVKK notice renders only for `TR`.
- The scaffold turns the vendored docs-site legal pages into pointers to the app pages.

## Review record

`/fabrik-spec-review`, native seats partitioned by section (pool off, D-181): Opus on the rule and grammar
sections (R) and on the Paddle facts (F1), Sonnet on the rest (S) and on the non-Paddle facts (F2).

| Pass | Seats | Candidates | Confirmed | Own-fix | Result |
|---|---|---|---|---|---|
| 1 | 8 | 32 | 31 | 0 | rewrite to design D with runtime `LEGAL_*` env; S-S3 refuted |
| 2 | 6 | 6 | 5 | 4 | every round-1 claim re-verified fixed; product name and description moved to legal config; TR/IL scope; the 1.3 qualifier dropped; the `theme` writer; a non-vacuous docs-site assertion |
| 3 | 4 | 1 | 1 | 1 | every pass-2 claim re-verified fixed; one stale count in a rejected alternative, fixed and re-read by the orchestrator |

Closed on the scope-growth stop (two of the last three rounds were mostly defects in this review's own
fix text): the original surface was quiet after pass 2.

