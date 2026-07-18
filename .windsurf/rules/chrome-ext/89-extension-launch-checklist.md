---
activation: glob
globs: ["**/manifest.json", "**/extension/**", "**/popup.{js,ts,html}", "**/background.{js,ts}", "**/content-script*.{js,ts}"]
description: Chrome extension launch checklist — Web Store account, listing assets, privacy practices tab, review-trap avoidance, staged rollout, post-launch
trigger: glob
---
<!-- CONSUMER: Traycer (primary) + coding agents (verification)
     GOAL: Extension launch-blocking gates — dev account, bundle hygiene, listing, privacy disclosures, review traps, rollout
     TRAYCER USAGE: PRIMARY CONSUMER. Reads during epic decomposition to ensure every gate maps to a ticket.
     AGENT USAGE: Verify completeness at epic closure / via /fabrik-release. Check items against Done When list. -->

# Chrome Extension Launch Checklist

Launch-blocking gates for publishing to the Chrome Web Store. Facts grounded against
https://developer.chrome.com/docs/webstore/publish and
https://developer.chrome.com/docs/webstore/review-process (fetched 2026-07-18).
The human operator clicks **Submit for Review** — that is Gate 2 (R14); no agent submits.

## 1. Developer account (one-time)

- Chrome Web Store developer account registered, **one-time $5 USD fee** paid.
- **2-Step Verification ON** for the publishing Google account (account takeover = every user compromised).
- Account item cap: the dashboard enforces a per-account published-item limit (the official docs state no
  number — verify a free slot in YOUR dashboard before assuming this account publishes it).
- Publisher email verified; contact email set in the dashboard (Google notifies rejections there).

**Done When:** dashboard reachable, fee paid, 2SV on, a free item slot exists, contact email verified.

## 2. Bundle hygiene (the pre-zip gate)

- **MV3 only** (`"manifest_version": 3`). No MV2 anywhere.
- **No secrets in the bundle** — an extension zip is readable by anyone who installs it; every secret lives in
  the backend `[canonical: chrome-ext/00-domain-chrome-ext.md § backend is Epic 1]`.
- **No remote-hosted code** — MV3 bans executing code fetched at runtime; all logic ships in the zip.
- **Permissions minimized** — every `permissions` / `host_permissions` entry maps to shipped code that needs
  it (the `chrome.*` API surface or host it gates — cite the `path:line` that uses it; permissions are not
  1:1 with single calls, so map by capability); unused or broad host permissions (`<all_urls>`) are the #1
  in-depth-review trigger.
- **No obfuscation.** Minification is allowed; obfuscated code triggers deep review and rejection risk.
- `version` bumped (the store rejects a re-upload of the same version); semver, matches CHANGELOG.
- Zip contains only the built extension (no sourcemaps, no `.env`, no dev artifacts) and stays within
  `size-limit` budget `[canonical: chrome-ext/70-chrome-ext.md § performance gate]`.

**Done When:** a fresh production zip passes: MV3 ✓, secret-grep clean ✓, each permission mapped to a using
`path:line` ✓, version bumped ✓, no obfuscation ✓.

## 3. Store listing assets

- **Icons:** 128×128 (store + install), 48×48, 16×16 — all three in the manifest.
- **Screenshots:** at least one, **1280×800 or 640×400** (real UI, no device frames with fake data).
- Title ≤ store limit, description written for users (what it does, not how), category chosen.
- A support/homepage URL (the product site or repo).

**Done When:** all assets exist at exact pixel sizes; listing text drafted and spell-checked.

## 4. Privacy practices tab (rejection trap #1)

All four are dashboard-mandatory before Submit:

- **Single-purpose statement** — one sentence; a multi-purpose extension gets rejected, split it.
- **Per-permission justification** — one line per requested permission explaining the user-visible need.
- **Data-use certification** — certify user data is used only for the extension's functionality, per the
  Limited Use policy.
- **Privacy policy URL** — hosted and public (project site page; a repo-hosted page is acceptable), covering
  KVKK/GDPR basics: what is collected, why, retention, contact `[canonical: saas/88-saas-launch-checklist.md § legal]`.

**Done When:** all four answers written down in the repo (`docs/DEPLOYMENT.md § store listing`) before the
dashboard is opened — never improvised in the form.

## 5. Review expectations & traps

- Review takes **days to weeks**; longer for new developers, new extensions, dangerous permissions, or big diffs.
- Reviewed factors: broad host permissions, sensitive execution permissions, code volume/formatting, obfuscation.
- Rejection ⇒ notification of the violated policy; the listing is unchanged. Fix and resubmit — do not argue
  scope in the appeal; reduce permissions instead.
- Plan the calendar: never gate a customer commitment on same-week approval.

**Done When:** the release ticket carries a review-latency buffer and a rejection-response owner.

## 6. Rollout & post-launch

- **Staged rollout** (percentage rollout to 100%) for updates with risk; new items ship at 100%.
- Post-launch watch: dashboard stats + user reviews weekly; crash/error telemetry via the backend
  `[canonical: core/55-observability.md]` (the extension itself must not ship third-party trackers).
- Update cadence: version bump + CHANGELOG per release; re-run this checklist §2–§4 on every resubmission
  (a new permission re-triggers full review).
- Keep the publishing account's recovery methods current; the account owns the listing.

**Done When:** first-week review-response owner named; update path (§2 rerun) documented in `docs/DEPLOYMENT.md`.
