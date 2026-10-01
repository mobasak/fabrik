---
activation: glob
globs: ["**/extension/**", "**/popup.{js,ts,html}", "**/background.{js,ts}", "**/content-script*.{js,ts}"]
description: Chrome extension launch checklist — the store channel (account, trader declaration, bundle hygiene, listing, privacy tab, review, rollout) and the developer-mode release for an extension the store will not approve
trigger: glob
currency_pass: 2026-10-02
---
<!-- CONSUMER: /fabrik-release's EXTENSION path (§ 1-6 for a store release; § 7 is the gate set for its unlistable ring, which
     the command is asked to point at — mail 01M3WTFXV99T20Q0ZYSTX8TB4E to infra) and coding agents verifying a release. Code-time facts live in 70-chrome-ext.md; the channel decision is made at
     intake (00-domain-chrome-ext.md Fork 2). tests/test_chrome_launch_pack.py pins the cites, the consumer and the no-version rule. -->

# Chrome Extension Launch Checklist

Launch-blocking gates for both channels: § 1–6 for the Chrome Web Store, § 7 for a developer-mode (unpacked) release of an
extension the store will not approve (D-486). An enterprise force-install release follows `70-chrome-ext.md` § Enterprise
force-install. Shipping is the operator's — **Submit for Review** in the dashboard, or publishing the developer-mode zip, is
Gate 2 (R14); no agent submits or publishes.

## 1. Developer account (one-time)

- **Registration:** the account that creates a publisher pays a **one-time $5 USD fee**. Teammates are **invited** to that
  publisher with a role (Viewer, Item manager, Editor, Admin) and pay nothing — invite them; never register a second publisher
  for a team member.
- **2-Step Verification is required** on the publishing Google account before it can publish or update an item.
- **Item cap:** a new publisher starts with **two** extension slots (themes are not capped). At the limit the dashboard offers
  an increase, usually decided at once and refused for low engagement or a young account — confirm a free slot in YOUR
  dashboard before planning a launch on it.
- **Emails:** rejection and policy notices go to the **developer account email** — make sure someone reads it; the verified
  contact email is only shown on the listing.
- **Trader or non-trader declaration (EU):** every publisher declares one. A trader's legal name, address and SMS-verified
  phone number are shown publicly on the listing. A publisher acting for a business purpose is a trader — a monetized
  extension always, a free one a business publishes for its trade too — so publish from the entity whose details may go public
  (the intake decision is `00-domain-chrome-ext.md` § 2. Monetization Model).

**Done When:** dashboard reachable, fee paid (or the account invited to an existing publisher), 2SV on, a free extension slot, the
account email monitored, the trader/non-trader declaration made from the right entity.

## 2. Bundle hygiene (the pre-zip gate — both channels)

- **MV3 only** (`"manifest_version": 3`). Manifest V2 no longer runs in Chrome.
- **No secrets in the bundle** — an extension zip is readable by anyone who installs it; every secret lives in the backend
  (`00-domain-chrome-ext.md` § 5. Backend Dependency).
- **No remote-hosted code** — the extension CSP refuses it on every channel (`70-chrome-ext.md` § MV3 Constraints); all logic
  ships in the zip.
- **Permissions minimized** — every `permissions` / `host_permissions` entry maps to shipped code that needs it (cite the
  `path:line` that uses the capability; permissions are not 1:1 with single calls, so map by capability). Broad host access and
  sensitive permissions lengthen store review; on the developer-mode channel they are still a larger attack surface on the user.
- **No obfuscation.** Minification is allowed; obfuscated code is refused by the store.
- **`version` raised** — each upload must carry a higher version than the last; semver, matching CHANGELOG.
- **The zip is `wxt zip` from the pushed SHA** — only the built extension (no sourcemaps, no `.env`, no dev artifacts), within the
  `size-limit` budgets (`70-chrome-ext.md` § Bundle Budgets).

**Done When:** a fresh production zip passes: MV3 ✓, secret-grep clean ✓, each permission mapped to a using `path:line` ✓,
version raised ✓, no obfuscation ✓, size-limit green ✓.

## 3. Store listing assets

- **Icon:** a 128×128 PNG (the artwork about 96×96, with transparent padding); 48×48 and 16×16 in the manifest too.
- **Screenshots:** one to five, **1280×800 or 640×400**, of the real UI.
- **Small promo tile:** **440×280**, required. A 1400×560 marquee is optional.
- **Text:** a name of at most 75 characters, the manifest `description` (at most 132 characters — the store shows it), a full
  description written for users (what it does, not how), a category and a language. The dashboard-listing page counts a
  YouTube video link among the required assets while the images page does not — the dashboard's own validation decides.
- A support or homepage URL (the product site or repo).

**Done When:** all assets exist at exact pixel sizes; listing text drafted and spell-checked.

## 4. Privacy practices tab (the most common rejection)

The dashboard's privacy tab has five answers; write all five down before opening it:

- **Single purpose** — one sentence; a multi-purpose extension gets rejected, split it.
- **Per-permission justification** — one line per requested permission explaining the user-visible need.
- **Remote code** — answer truthfully: an MV3 bundle has none, and remote code that is used but not declared is rejected.
- **Data usage** — the data types collected and the Limited Use certifications (user data used only for the extension's
  single purpose).
- **Privacy policy URL** — hosted and public (a project-site page; a repo-hosted page is acceptable), covering what is
  collected, why, retention and contact under KVKK and GDPR (`saas/88-saas-launch-checklist.md` § Legal Pages and
  `saas/88-saas-launch-checklist.md` § Data Protection (GDPR + KVKK)).

**Done When:** all five answers written in `docs/DEPLOYMENT.md` § store listing — create the file if the scaffold did not
seed it — before the dashboard is opened — derived from code you can cite, never improvised in the form.

## 5. Review expectations & traps

- Review usually completes **within a few days and can take weeks**; contact developer support only after three weeks
  pending. There is no expedited review on request — every submission and every update goes through the same review; the one
  fast path is the skip-review opt-in for an update that changes only `declarativeNetRequest` static rulesets.
- Reviewed factors: broad host permissions, sensitive execution permissions, code volume and formatting, obfuscation.
- **A new permission that triggers a warning disables the extension** for existing users until each accepts it — treat a
  permission addition as a breaking release.
- Rejection ⇒ a notice of the violated policy to the developer account email; the listing is unchanged. Fix and resubmit —
  reduce permissions rather than argue scope in an appeal.
- Plan the calendar: never gate a customer commitment on same-week approval.

**Done When:** the release ticket carries a review-latency buffer and a rejection-response owner.

## 6. Rollout & post-launch

- **Partial rollout** is available only to items with more than 10,000 seven-day active users: set the percentage on the
  Distribution tab when submitting, then raise it on the Package tab without another review. Publishing a new version stops a
  rollout in progress. Smaller items ship each version to everyone.
- **Verified uploads — opt in:** on the Package tab, after which every upload must be a `.crx` signed with your key —
  a compromised account then cannot push a malicious update. The private key is a secret, never in the repo.
- Post-launch watch, every channel: crash and error telemetry through the backend (`core/55-observability.md` § Chrome
  Extension Telemetry); product analytics only as `70-chrome-ext.md` § Observability (Extension Side) allows — first-party, consent-gated,
  and declared on the privacy tab. Store releases also: dashboard stats and user reviews weekly.
- Every release: version raised, CHANGELOG entry, § 2–§ 4 re-run.
- Keep the publishing account's recovery methods current; the account owns the listing.

**Done When:** first-week review-response owner named; the update path documented in `docs/DEPLOYMENT.md`.

## 7. Developer-mode (unpacked) release — the unlistable channel

For an extension the store will not approve (D-486; the channel's facts are `70-chrome-ext.md` § Distribution Model). § 1, § 3,
§ 4, § 5 and the store items of § 6 do not apply — never fill a privacy tab or a listing for a submission that will not happen;
§ 2 applies in full and § 6's post-launch watch applies on every channel.

- **Why it is unlistable** is recorded in `docs/DEPLOYMENT.md` § distribution, citing the store policy it conflicts with.
- **§ 2 still applies in full** — MV3, no secrets, no remote code (the CSP refuses it here too), permissions mapped, version
  raised, a `wxt zip` from the pushed SHA.
- **Stable ID:** the manifest `key` is pinned, its private key kept out of the repo, and the backend's CORS allow-list carries
  the exact `chrome-extension://<id>` (`70-chrome-ext.md` § Versioning & Updates).
- **Updates:** the in-extension update checker is live and reads the latest version — from the backend or a hosted version
  manifest (`70-chrome-ext.md` § Versioning & Updates); that value is bumped only after the new zip is reachable — Chrome never
  auto-updates an unpacked extension.
- **Backend compatibility:** the backend still serves the previous extension version — updates are manual here, so old builds
  linger longer than on the store (`70-chrome-ext.md` § Versioning & Updates).
- **Release artifact:** the zip is hosted (VPS static site or B2) with its SHA-256 published beside it.
- **Install guide** beside the zip: turn on Developer mode at `chrome://extensions` → unzip → **Load unpacked** → pick the
  folder; **keep Developer mode on** (Chrome disables unpacked extensions when it is off); on a company-managed Chrome that
  forbids developer mode, use enterprise force-install instead (`70-chrome-ext.md` § Enterprise force-install).
- **Enterprise force-install variant** (managed browsers): a `.crx` packed with the pinned key, an `updates.xml` hosted at the
  manifest's `update_url`, and the `ExtensionInstallForcelist` entry recorded in `docs/DEPLOYMENT.md` § distribution — this
  variant auto-updates.
- **Gate 2:** the operator publishes the zip, its checksum, the guide and the version-manifest bump; no agent publishes.

**Done When:** the unlistable reason recorded, § 2 passed, `key` pinned with the exact-ID CORS entry, the update checker
reading the latest version, the backend serving the previous version, the zip and its SHA-256 hosted, the install guide
published.
