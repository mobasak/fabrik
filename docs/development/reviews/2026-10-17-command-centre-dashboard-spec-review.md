# Spec review — the operator's command-and-control centre (W-573fae88)

**Command:** /fabrik-spec-review
**Spec:** `docs/superpowers/specs/2026-10-16-command-centre-dashboard-design.md` (DRAFT at bc1793413)
**Research ledger:** `docs/reference/research/2026-10-16-command-centre-dashboard-ledger.md`
**Shape:** agent-tool (the Workflow tool runs only on the operator's explicit opt-in)
**Status:** CONVERGED

## Pass Ledger

| Pass | seats · axes re-checked (intake · personas · facts · vendor · approach · completeness · constraints) | counters | method | spec md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (slice R: design, contract, digest, decisions) + sonnet×1 (slice S: personas → intake, ledger) + sonnet×1 fabrik-researcher (slice F: cited facts, U2) · all axes | found: 26, new: 26, confirmed: 21, fixed: 21, unexecuted: 0, edits: 27 | method: citation — full pass over the pin; every candidate executed by the orchestrator (`adjudicate573.py`, `probes.py`); 5 found by the orchestrator's own pre-pin probes | 7f82be30… → 630a62c2… |
| Pass 2 | opus×1 + sonnet×1 + sonnet×1 fabrik-researcher (round-1 owners) · delta over every round-1 hunk + one hop | found: 9, new: 9, confirmed: 7, fixed: 7, unexecuted: 0, edits: 10 | method: re-derivation — R1–R11, S1–S9 and the F facts re-executed DEFECT_ABSENT (merge rule over 761 records and 4 fixture cases, ordering over 43 items, TTLs, anchors); 7 own-fix defects inside round-1 hunks (own-fix: round 1) | 630a62c2… → 570c7670… |
| Pass 3 | opus×1 + sonnet×1 + sonnet×1 fabrik-researcher (round-1 owners) · delta over the round-2 hunks + one hop | found: 4, new: 4, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — P2-1…P2-7 re-executed DEFECT_ABSENT (agent states agent_status.py:340-347/:373, HOST/PORT :50-51, the health probe's Host, _merge_owner :297/:1927 over 9 repos, the 100 basis); standing clean since pass 2: every other class | 570c7670… → 570c7670… ✓ |
| Pass 4 | opus×1 + sonnet×1 (round-1 owners) · delta over the approval panel's ACCEPTED changes (fix-panel.diff, 106 lines) + one hop | found: 10, new: 10, confirmed: 7, fixed: 7, unexecuted: 0, edits: 9 | method: re-derivation — every panel change re-executed (work.py:3813/:3830-3838, quota_dashboard.py:2740/:2983/:2361, agent_status.py:385-387, an AST scan of HTML-emitting functions, a key census of the 43 awaiting items); 7 own-fix defects inside the panel hunks; SCOPE GROWTH stop fired (7/7 → 0/0 → 7/7), remaining own-fix routed to the backlog row | 570c7670… → b5375c43… |
| Pass 5 | opus×1 + sonnet×1 (round-1 owners) · the pass-4 fixed set only (scope-growth remainder round) | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 1 | method: re-derivation — N2–N5 and P1–P3 re-executed DEFECT_ABSENT (AST scan re-run: 31 HTML-emitting functions; intake rows re-counted 18 = 17 IN + 1 OUT); N1 still present in one Validation line (own-fix: round 4) | b5375c43… → 841588be… |
| Pass 6 | opus×1 (round-1 owner of the fixed set) · N1 only (scope-growth remainder round) | found: 1, new: 1, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — N1 re-executed DEFECT_ABSENT (grep -c options → 0; the token's fields agree across § Which actions confirm, Contract deltas and Validation); standing clean since pass 5: every other class; one gap RECORDED to W-f4063aa8 | 841588be… → 841588be… ✓ → **CONVERGED** |

## Findings

| Id | Pass | Anchor | Verdict |
|---|---|---|---|
| O1 | 1 | § What exists — `_posture.py` (4) | FIXED r1 (pytest collects 9) |
| O2 | 1 | § Why / § Lifecycle — 11 hub gates, the >25 trigger | FIXED r1 (43 across 8 repos, 13 hub; grouping by repo is the default; new trigger at 100) — same as R7, S3 |
| O3 | 1 | Digest / Responsive — design-system-template.md:1343 | FIXED r1 (the rule sits at :1344) — same as S10 |
| R1 | 1 | § Which actions confirm — 409 on `block_digest` | FIXED r1 (block_digest is written once, scripts/work.py:4347; the token is derived from what the card shows) |
| R2 | 1 | INV-1 — actions unchanged | FIXED r1 (the target registries are published by the page builders, :2750, :2810, rebuilt via _repos_page :2664, :2735; INV-1 now moves them with the page layer) |
| R3 | 1 | INV-5 — skip while a field holds text | FIXED r1 (today's refresh carries typed text :2943 and forces after a write :2925; INV-5 restated) |
| R4 | 1 | § Overview 1 — Accept/Reject on every item | FIXED r1 (work.py:3813 refuses non-decision items; Accept/Reject only for kind decision) |
| R5 | 1 | § Overview 2 — "newest record is refused" | FIXED r1 (newest = greatest ULID id; catchup-refused counts, merge_request.py:1767; in-flight not blocked) — with S2 |
| R6 | 1 | INV-2 — nothing dropped | FIXED r1 (Holds column, dormant counts, the three banners, warnings, return and pending rows, ext intro and rotation note given homes) |
| R7 | 1 | § Lifecycle trigger | DUPLICATE of O2 |
| R8 | 1 | Freshness — two missed intervals | FIXED r1 (on-demand views use their collector TTL) |
| R9 | 1 | Which actions confirm — Pause no dialog; Comment no state change | FIXED r1 (Pause keeps its confirmation as a dialog, DT8; Comment appends a note) |
| R10 | 1 | INV-1 responses unchanged vs the 409 | FIXED r1 (INV-1 names the additive 409) |
| R11 | 1 | Digest — "verbatim" | FIXED r1 (verbatim apart from inline markup, 6 rows) — with S10 |
| S1 | 1 | Blocked merges hub-only | FIXED r1 (every repo's .git/fabrik-merge; 761 readable records, 9 repos) |
| S2 | 1 | `_parked` cited as the writer; 44 refused read as blocked | FIXED r1 (merge_request.py writes the records; _parked :1936 reads catchup-refused; 1 branch blocked now) |
| S3 | 1 | Growth trigger already exceeded | DUPLICATE of O2 |
| S4 | 1 | Intake I14 → § Next | FIXED r1 (points at § Open / blocking unknowns and the receipt's approval row) |
| S5 | 1 | Why — one 720 px breakpoint | FIXED r1 (three max-width queries 720/1100/620, :3184, :3210, :3211; OS-follow dark exists) |
| S6 | 1 | I# collides between intake and invariants | FIXED r1 (invariants renamed INV-1…INV-6) |
| S7 | 1 | Step budget and persona gaps | FIXED r1 (a step defined; skip-link target; product-repo agents persona; test-rewrite holder named) |
| S8 | 1 | Rejected — tab-5 cited for dropped semantics | FIXED r1 (tab-3, tab-4 cited; Safari 17 caveat) |
| S9 | 1 | Lifecycle / Rejected gaps | FIXED r1 ("one release" → 14 days; render baseline measured at build; W-7def1b78 reworded as related; TUI, cron static HTML and Alpine rejected with reasons). The "Overview-tab-only" variant: REFUTED (it is approach A as written) |
| S10 | 1 | Digest quotes vs raw | DUPLICATE of R11 |
| S-m | 1 | Repos frame 3,123 px not reproduced (2,785 px) | RECORDED — measured (both readings real: in the page's iframe vs opened directly; the spec now states both) |
| U2 | 1 | Open unknown — custom-header CSRF | FIXED r1 (OWASP accepts the header, csrf-1; DNS rebinding needs a Host allowlist, csrf-4; INV-6 and DT7) |
| P2-1 | 2 | INV-6 — `Host` "names this server's loopback address" (own-fix: round 1) | FIXED r2 (the allowlist is `127.0.0.1`, `localhost`, `[::1]` at the configured port; a test serves `localhost:5051`) |
| P2-2 | 2 | Personas — coordinator "owns every blocked merge" vs product repos (own-fix: round 1) | FIXED r2 (hub's only; a card names the repo's own merge owner, `_merge_owner`, merge_request.py:1927) |
| P2-3 | 2 | Overview 3 — dormant agents "expand to rows"; stale agents homeless (own-fix: round 1) | FIXED r2 (one row per collector-listed agent in any state, agent_status.py:340-347; dormant stays a count, :373) |
| P2-4 | 2 | INV-1 exceptions omit 421/403 (own-fix: round 1) | FIXED r2 (INV-1 names INV-6's 421 and 403, DT7) |
| P2-5 | 2 | Freshness — Commands has no interval (own-fix: round 1) | FIXED r2 (Commands reads live and never goes stale) |
| P2-6 | 2 | U2/INV-6 — csrf-4 cited for the header-bypass reasoning (own-fix: round 1) | FIXED r2 (marked as this review's reasoning; csrf-4 cited for the Host allowlist only) |
| P2-7 | 2 | Lifecycle — 100-decision trigger without a basis (own-fix: round 1) | FIXED r2 (basis: over twice the 43 counted 2026-10-17) |
| P2-r1 | 2 | External deps — "raw fetch" label on WCAG | REFUTED (the orchestrator's own urllib fetch of w3.org/TR/WCAG22, 511,724 bytes, 2026-10-16) |
| P2-r2 | 2 | Sec-Fetch-Site absent / same-site behaviour unstated | FIXED r2 within P2-1's hunk (same-origin, same-site, none and absent pass to the Host check) — counted in P2-1 |
| P3-1 | 3 | INV-6 — a configured `QUOTA_DASH_HOST` other than 127.0.0.1 would fail the `--ensure` health probe's Host | RECORDED — measured (the variable is unset in crontab and in both live board processes; destination: the plan's INV-6 step adds the configured host to the allowlist) |
| P3-2 | 3 | Freshness cell lists "commands on a source-file change" beside "never goes stale" | RECORDED — measured (wording; changes no behaviour) |
| P3-3 | 3 | Blocked-merge card when `_merge_owner` refuses (no declared owner) | RECORDED — measured (one hop out; destination: the plan's blocked-merge reader shows "owner unresolved" with the resolver's message, and its Validation case) |
| P3-4 | 3 | `[::1]` allowlisted while the server binds IPv4 only (:3987) | RECORDED — measured (harmless and unreachable; changes no behaviour) |
| PN-1 | panel | Opus — Overview fills with 43 full-question cards; quota band buried | FIXED (summary strip, item 0; RED/WALL raises Quota and Health; groups collapsed but the first; 3-line clamp) — ACCEPTED |
| PN-2 | panel | Opus — Accept with a note disappears | FIXED (the Accept dialog takes an optional note, :2740, :2983) — ACCEPTED |
| PN-3 | panel | Opus — INV-2 tests controls only | FIXED (data fields in the inventory test) — ACCEPTED |
| PN-4 | panel | Opus + Fable — no test for the string catalogue | FIXED (catalogue test in Validation; INV-4 catalogue sentence) — ACCEPTED |
| PN-5 | panel | Opus — absent token passes; token omits ground | FIXED (ground in the token; token required after the 14-day window) — ACCEPTED |
| PN-6 | panel | Opus — keyboard focus claim fragile | FIXED (focus order pinned in the smoke test) — ACCEPTED |
| PN-7 | panel | Opus — Accounts "history if present" hedge | FIXED (dropped; only Commands has sub-views) — ACCEPTED |
| PN-8 | panel | Fable — Work view would lose Accept/Reject on open items | FIXED (today's rule cited, :2361, work.py:3813, :3830-3838) — ACCEPTED |
| PN-9 | panel | Fable — Resume without a dialog contradicts D-916 | FIXED (Resume keeps a dialog, DT8) — ACCEPTED |
| PN-10 | panel | Fable — escape scan vs kept builders; plan undersized | FIXED (INV-4: every HTML-emitting function moves onto the components; sized on the scan) — ACCEPTED |
| PN-11 | panel | Fable — external-services page untouched | FIXED (§ Why says it is another generator's page; follow-up W-3e9e2f4c) — ACCEPTED |
| PN-12 | panel | Opus + Fable — U3 ruling: catalogue enough, tr later, D-row | FIXED (U3 resolved, DT6, I16; exemption row minted at the flip) — ACCEPTED |
| P4-1 | 4 | Snapshot token and dialog cite "options", a field items do not carry (own-fix: panel) | FIXED r4 (dropped; key census of 43 items) |
| P4-2 | 4 | Resume dialog "who set each" needs collector output (own-fix: panel) | FIXED r4 (names the markers and the first's actor, agent_status.py:385-387) |
| P4-3 | 4 | INV-4 builder list short by 17 (own-fix: panel) | FIXED r4 (every HTML-emitting function, 31 by AST scan) |
| P4-4 | 4 | Required token contradicts INV-1 "additive", DT5, Validation (own-fix: panel) | FIXED r4 (all three say additive then required; existing tests gain a token) |
| P4-5 | 4 | Collapsed groups vs the 4-step budget; empty hub group (own-fix: panel) | FIXED r4 (4 steps expanded, 5 collapsed; first non-empty group expanded) |
| P4-6 | 4 | Step 1, Goal and I7 stale against the summary strip (own-fix: panel) | FIXED r4 |
| P4-7 | 4 | I16 still ASK; exemption claimed in the past tense; no intake row for the strip (own-fix: panel) | FIXED r4 (I16 IN; tense; I18 added; 18 items) |
| P4-r1 | 4 | `_with_stale_banner` hard-codes a colour (:3459) | RECORDED — measured (one hop out; destination: the plan — INV-3 already bans colour literals, the banner moves onto tokens with every other builder) |
| P4-r2 | 4 | Overview item 3 says Pause / Resume "as today" while both now use dialogs | RECORDED — measured (wording; DT8 governs; destination: backlog W-f4063aa8) |
| P5-1 | 5 | Validation still tests "the snapshot token covering ground and options" (own-fix: round 4, N1's fix incomplete) | FIXED r5 ("options" removed; 0 hits in the spec) |
| P5-r1 | 5 | Traceability names no intake row for the summary strip; Health-alone reorder unstated | RECORDED — measured (wording, one hop out; destination: backlog W-f4063aa8) |

## Ask ↔ spec comparison

Built against the closing-round text (md5 570c767096c0b18120c7143e46d65c0d). The operator's own words first, then the
coordinator's brief (relayed), then every spec section nobody asked for.

| # | Asked (own words) | What the spec says | Anchor | Disposition |
|---|---|---|---|---|
| 1 | "dashboard, repos have a mess ui" | The board is rebuilt: one shell, one stylesheet, one script, no iframes; the Repos tab becomes the Work view | § Chosen approach, INV-3, § Information architecture | IN |
| 2 | "i want it to be done in best user friendly way" | Exception-first Overview, 4-step decision loop, verb-labelled dialogs, error / empty / loading states everywhere | § Personas (step budget), § Components, § Which actions confirm | IN |
| 3 | "best ui practises" | Grounded in WCAG 2.2 AA, APG tabs and dialog, NN/g, Grafana, Google SRE, Roselli, the house rule packs (32 quoted rules) | § Constraints Digest, research ledger (85 rows) | IN |
| 4 | "it will be our command and control centre" | Overview answers what needs the operator now; six views one level below; every action the board has today stays | § Overview, INV-1, INV-2 | IN |
| 5 | (brief) overview answers "what needs the operator now" first | *Needs you* is the Overview's first section and the skip link's target | § Overview item 1, § Personas | IN |
| 6 | (brief) awaiting gates with inline Accept/Reject | Decision cards grouped by repo, Accept/Reject on decision items, Comment on all, snapshot check | § Overview item 1, § Which actions confirm | IN |
| 7 | (brief) blocked merges | Fleet-wide reader of `.git/fabrik-merge`, newest-record rule, the repo's merge owner named | § Overview item 2 | IN |
| 8 | (brief) each agent's NOW/NEXT | Every collector-listed agent with state, NOW, Holds, NEXT, Pause/Resume | § Overview item 3 | IN |
| 9 | (brief) the quota band | Quota strip: band, active account, three windows, hold tier | § Overview item 4 | IN |
| 10 | (brief) IA, screens, states, components | Six-view IA, Overview layout, component table with states | § Information architecture, § Components | IN |
| 11 | (brief) keyboard- and mobile-friendly | Skip link, focus ring, APG patterns; mobile-first CSS, 375 px, 200 % zoom, table scroll regions | § Theme, motion, keyboard | IN |
| 12 | (brief) light/dark | Three-state toggle, no flash, contrast computed for both themes | § Theme | IN |
| 13 | (brief) the Opus + Fable panel approves, then build | This gate | review receipt § Approval | IN |
| 14 | — | Phone / remote access left out | INV-6, W-7def1b78 | ADDED (out of scope, filed) — implied by "mobile-friendly"; needs its own auth design |
| 15 | — | `Host` allowlist and cross-site POST refusal | INV-6, DT7 | ADDED — a console the operator acts through must not be reachable by DNS rebinding (U2) |
| 16 | — | Snapshot check (409) on verdicts | DT5 | ADDED — an approval holds only for what the operator saw |
| 17 | — | English with a string catalogue, `tr` for the panel | U3, DT6 | ADDED — the i18n mandate, ruled here |
| 18 | — | Rejected alternatives, Lifecycle, Documentation landing sites, Personas | those sections | ADDED — this command mandates them |

## Approval

The design-approval gate was answered by the Opus + Fable panel in the operator's place (D-613). Both seats returned sound-with-changes; every concern was ACCEPTED (rows PN-1 … PN-12) and re-verified in passes 4-6. Approval row D-925; i18n exemption row D-926. Final spec md5 c03e56d4b54952427b19b30c28a377d2.

Panel: opus="VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-16-command-centre-dashboard-design.md" fable="VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-16-command-centre-dashboard-design.md" → both-approve
