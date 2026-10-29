# Spec review — the external-services inventory in the command centre (W-3e9e2f4c)

**Command:** /fabrik-spec-review
**Spec:** `docs/superpowers/specs/2026-10-18-external-services-page-design.md` (DRAFT at 159b3bac2)
**Research ledger:** `docs/reference/research/2026-10-18-external-services-page-ledger.md`
**Shape:** agent-tool (D-961: the Workflow tool is never called)
**Status:** CONVERGED

## Pass Ledger

| Pass | seats · axes re-checked (intake · personas · facts · vendor · approach · completeness · constraints) | counters | method | spec md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (slice rules: chosen approach, design, contract deltas, decisions, digest) + sonnet×1 (slice context: personas → intake, lifecycle, docs, unknowns) + sonnet×1 fabrik-researcher (slice research: the cited facts) · all axes | found: 32, new: 32, confirmed: 24, fixed: 24, unexecuted: 0, edits: 27 | method: every candidate re-executed by the lead — census recount from the embedded JSON (attention union 37, account 0 of 466, 17 real categories, 115 categorised), `app.js` read at :10, :36, :453-540, :700-717, `components.table` / `_esc` / `live_region`, `PORTS.md` grep (no 8770), the reference greps | 7ca217c17d4cd1036bfa8ca75c01e1f6 → 4e783eefc45760a2205ee1414a7dd0a6 |
| Pass 2 | opus×1 + sonnet×1 + sonnet×1 fabrik-researcher (round-1 owners) · delta over every round-1 hunk + one hop | found: 16, new: 16, confirmed: 13, fixed: 13, unexecuted: 0, edits: 22 | method: re-derivation — 28 round-1 ids re-executed (27 FIXED, rules-11 FIX_WRONG); new candidates re-executed by the lead: `clamp()` markup and `initClamps` `app.js:587`, the test grep for the removed names (12 sites), `registry_db.connect()` `:35-37`, the 115-row recount (88 keys, 5 bad URLs), `/repos.html` precedent `quota-dashboard.md:249`, the strings keys `:468-471` | 4e783eefc45760a2205ee1414a7dd0a6 → d5ab9930668d0e62184d6b075b7e129b |
| Pass 3 | opus×1 + sonnet×1 (round-1 owners) · the pass-2 fixed set only (scope-growth remainder round) | found: 11, new: 11, confirmed: 9, fixed: 9, unexecuted: 0, edits: 10 | method: re-derivation — 14 pass-2 ids re-executed FIXED; new residues re-executed by the lead: `registry_db.py` `cat -n` (33-35), `refresh-s` grep (overview, work, accounts only), the untriaged project maximum 9, the height sum (20 summaries), the CSP ledger row st-9 | d5ab9930668d0e62184d6b075b7e129b → fc581a0c0164ee6f14f8de4ade3b8cf7 |
| Pass 4 | opus×1 + sonnet×1 (round-1 owners) · the pass-3 fixed set only (scope-growth remainder round) | found: 2, new: 2, confirmed: 2, fixed: 2, unexecuted: 0, edits: 3 | method: re-derivation — 11 pass-3 ids re-executed FIXED (`cat -n registry_db.py`, `CADENCE` `app.js:55`, the `refresh-s` grep, the height sum, the SQL mapping); new: "permanent 303" (both seats) and the CSP heading claim the ledger row st-9 does not hold | fc581a0c0164ee6f14f8de4ade3b8cf7 → 93b5aed990cad959704f3e41c2d17e95 |
| Pass 5 | opus×1 + sonnet×1 (round-1 owners) · the pass-4 fixed set only (scope-growth remainder round); slice research standing clean since Pass 2 | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — rules-p4-1 and context-p4-1 re-executed DEFECT_ABSENT (`grep -n "permanent\|303"` → 0 "permanent", three `303` sites all "no removal date"; the CSP sentence against ledger st-9 `:39`); flip gate `check_spec_convergence.py` on a CONVERGED copy → 0 findings of 1 named | 93b5aed990cad959704f3e41c2d17e95 → 93b5aed990cad959704f3e41c2d17e95 |
| Pass 6 | opus×1 + fable×1 (the design-approval panel, D-613; independent, same brief) · design gate over the converged spec | found: 7, new: 7, confirmed: 7, fixed: 7, unexecuted: 0, edits: 20 | method: both seats approve-with-changes; every change re-executed by the lead before folding — parent spec `:447` "no new dependency", `quota_dashboard.py:44-62` imports nothing from `scripts/`, `registry_db.py:17` top-level psycopg2, `field()` `components.py:227` has no select, `stamp()` `views/__init__.py:66-68` hashes markup, `_credits_lock` `:531`, the pool/API cards `views/services.py:200-210`, `classify_last.json` mtime 2026-09-07 | 93b5aed990cad959704f3e41c2d17e95 → ac364d012acb84e13023e6b22aa88d92 |
| Pass 7 | opus×1 + sonnet×1 (round-1 owners) · delta over the panel fold (panel.diff, 242 lines) + one hop | found: 15, new: 15, confirmed: 12, fixed: 12, unexecuted: 0, edits: 18 | method: re-derivation — 24 panel claims re-executed (11 hold); new candidates re-executed by the lead: `classify_services.py:503-504` returns before the record write, the `_id()` census (12 names fail, not 17; `captcha` is provider and category), `/usr/bin/python3` psycopg2 `2.9.9`, the spliced Failure sentence, `freshness()` text `strings.py:53` | ac364d012acb84e13023e6b22aa88d92 → 0eacbc6247bb04c36819dd4439d05f98 |
| Pass 8 | opus×1 + sonnet×1 (round-1 owners) · the pass-7 fixed set only (scope-growth remainder round) | found: 4, new: 4, confirmed: 4, fixed: 4, unexecuted: 0, edits: 5 | method: re-derivation — 13 of 15 pass-7 ids re-executed FIXED; the data-age line (FIX_WRONG twice) and the opened-by-filter rule were REWRITTEN, not patched: the section's age is the board's standard `card(age=freshness(…))` stamp, the filter records the ids it opened; psycopg2 re-executed both ways (`-I` → 2.9.9 `dist-packages`, plain → 2.9.11 `~/.local`); `ls scripts/*.py` → 77 | 0eacbc6247bb04c36819dd4439d05f98 → a00bc0900dca971097bcdbd6d99dbdc5 |
| Pass 9 | opus×1 + sonnet×1 (round-1 owners) · the pass-8 rewrites only (scope-growth remainder round) | found: 3, new: 3, confirmed: 2, fixed: 2, unexecuted: 0, edits: 4 | method: re-derivation — the data-age rewrite re-executed FIXED (`card()` `components.py:168-188`, `fresh.*` `strings.py:53-58`, `tickFreshness` on every `initView`); new: the filter record inside `qd-filter:<group>` fails `validFilterState` `app.js:492-497` and resets the store `:503` (both seats, one defect), the static empty-registry text | a00bc0900dca971097bcdbd6d99dbdc5 → 536dd9a1aefba9637ddcacd59c6ae05d |
| Pass 10 | opus×1 + sonnet×1 (round-1 owners) · the pass-9 fixed set only (scope-growth remainder round) | found: 2, new: 2, confirmed: 1, fixed: 1, unexecuted: 0, edits: 3 | method: re-derivation — R9-1, R9-2 and rules-p7-6 re-executed FIXED (`grep -n qd-filter app.js` → only `qd-filter:<name>` at :501, :526, :536); new: two `app.js` citations off (`validFilterState` is :492-498, the reset :504) and the "same `try`" wording (`load()`/`save()` each wrap their own, :27-28) | 536dd9a1aefba9637ddcacd59c6ae05d → 9e1c800f16f3b1bca3c1830f872e2693 |
| Pass 11 | opus×1 + sonnet×1 (round-1 owners) · the pass-10 fixed set only (scope-growth remainder round); slices research and panel standing clean | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — rules-p10-1 and the wording point re-executed DEFECT_ABSENT (`sed -n 490,506p app.js`, `sed -n 27,34p`); every class swept clean; flip gate `check_spec_convergence.py` on the CONVERGED spec | 9e1c800f16f3b1bca3c1830f872e2693 → 0c163da4764296f37aa3fd9c62cd633f |

## Findings

| Id | Pass | Anchor | Verdict |
|---|---|---|---|
| rules-1 | 1 | § The design 3 — fourth attention rule "0 today" | FIXED r1 (it matched 16; the rule is rejected while `account` is never set, D4; census per rule stated, 21 rows) — same as context-1 |
| rules-2 | 1 | § The design 5 — untriaged entries lose link and projects | FIXED r1 (each entry carries link, keys and projects) — with context-2 |
| rules-3 | 1 | § The design 2 — "five dropped counts" | FIXED r1 (ten cards mapped one to one; More counts disclosure) — same as context-9 |
| rules-4 | 1 | Filter bar — selects on the existing mechanism | FIXED r1 (SELECT support declared as an `app.js` contract delta) — with context-3 |
| rules-5 | 1 | Filter bar — open-on-match and the count | FIXED r1 (both declared as `app.js` deltas with smoke assertions) — with context-3 |
| rules-6 | 1 | § Chosen approach — static file inlines the filter script | FIXED r1 (static file carries no script, D7; self-containment test asserts no `<script>`) |
| rules-7 | 1 | § Data flow — JSON in the static file | FIXED r1 (static embeds none; the live view only `shell()`'s catalogue) |
| rules-8 | 1 | components — live_region, alignment, row detail | FIXED r1 (no live_region in the fragment; `table()` gains `align`; detail is a `disclosure()` cell, `_esc` passes `Safe`) |
| rules-9 | 1 | Summary counts as filter links | FIXED r1 (plain counts, not controls) |
| rules-10 | 1 | Contract deltas — the board route and its readers | FIXED r1 (route, `ext_page` and link card removed, D8; board tests named in § Personas; access-log trigger dropped) — with context-10's retirement half |
| rules-11 | 1 | Failure — unbounded registry read | FIXED r1 (connect_timeout 3, statement_timeout 3000; a Validation case) |
| rules-12 | 1 | Height estimate not derivable | FIXED r1 (stated as a formula ≈ 2,150 px, budget on the section) |
| rules-13 | 1 | D3 reason; row positions | FIXED r1 (D3 restated; every row has one stated position, attention rows also in their table, unidentified only in attention) |
| rules-14 | 1 | Stale rule cannot use `now` | FIXED r1 (`credit_at` on each row, judged at render) |
| rules-15 | 1 | `synced_at` None | FIXED r1 ("registry never synced") |
| context-4 | 1 | Loader module unnamed; sys.path | FIXED r1 (`inventory.load(conn)`; `gen_dashboard` re-exports `load`, inserts `scripts/sysadmin`) |
| context-5 | 1 | § Personas — test files missing | FIXED r1 (every file that loads a retired or moved symbol named with its disposition) |
| context-6 | 1 | "no other reader" | FIXED r1 (full reference list, launchers checked; `capabilities.json` regenerated) |
| context-7 | 1 | `PORTS.md` 8770 row | FIXED r1 (there is none; claim removed) |
| context-8 | 1 | Missing doc sites | FIXED r1 (DATA_SYNC_WORKFLOW, quota-dashboard :248/:314, strings.py, INDEX :2087/:2376, capabilities.json) |
| context-10 | 1 | Growth trigger unmeasurable | FIXED r1 (a 5,000-row render test and the census count) |
| context-11 | 1 | I8 destination | FIXED r1 (W-7e467f2d, cause the pool going off, D-181) |
| context-12 | 1 | Census — 19 categories include `?` and `unidentified` | FIXED r1 (17 real; the 20-row overlap stated) |
| research-1 | 1 | D3 presented as best practice | FIXED r1 (named as a project decision against NN/g and Primer) — with ux-3, a11y-10, ux-16 qualifications folded into § Chosen approach |
| context-13 | 1 | Personas — launchers, liveness | REFUTED-AS-DEFECT (the chain persona's contract is unchanged; launchers recorded in § Open unknowns) |
| context-fabrik-lib | 1 | "VENDOR as-is (in-repo)" | FIXED r1 (REUSE in-repo) — counted with context-6's edit batch |
| research ux-13, st-2, ux-12, ux-8, ux-11, ux-15 | 1 | cited facts | SUPPORTS — no change |
| rules-11 | 2 | Failure — per-statement bound read as the whole read | FIX_WRONG r1 → FIXED r2 (one 5 s deadline over connect plus every query, `SET LOCAL statement_timeout` re-armed; `registry_db.connect()` gains optional kwargs) — same as context-p2-3 |
| rules-p2-1 | 2 | Unidentified rows had no home | FIXED r2 (an Unidentified table; filter total 466, each provider once) |
| rules-p2-2 | 2 | `clamp()` inert without script and hidden in closed groups | FIXED r2 (no `clamp()` in either output; first three names + native `<details>`) — same as context-p2-1 |
| rules-p2-3 | 2 | `gen_dashboard.load()` shape | FIXED r2 (returns the rows list alone) |
| rules-p2-4 | 2 | Orphaned `services.ext.*` strings | FIXED r2 (all four removed) |
| rules-p2-5 | 2 | Board tests not named | FIXED r2 (12 sites named) — same as context-p2-2 |
| rules-p2-6 | 2 | Count values ambiguous | FIXED r2 (each count a formula with its census value; categories 18, credentials 92 + 5) — with context-p2-5 |
| context-p2-4 | 2 | Growth trigger census no longer reproducible | FIXED r2 (group-summary counts and a registry query) |
| context-p2-6 | 2 | Route goes straight to 404 | FIXED r2 (`303` to `/#services` through `_LEGACY_TOKEN_UNTIL`, the `/repos.html` precedent) |
| context-p2-7 | 2 | "loads in 14 places" | FIXED r2 (14 lines, about 10 loads) |
| rules-r2-cite | 2 | `app.js:10` off by one | FIXED r2 (`:11`) — found by both section seats |
| research-p2-1 | 2 | CSP sentence implied st-9 backing | FIXED r2 (the style directive is the spec's own inference) |
| research-p2-2 | 2 | Ledger ux-3 disposition overstated GOV.UK | FIXED r2 (ledger row reworded; `check_research_ledger.py` 0 refused) |
| R3-1 | 3 | Digest still said 3 s / 3 s | FIXED r3 (2 s connect, 5 s read) |
| R3-2 | 3 | Height sum missed the Unidentified table | FIXED r3 (20 summaries, ≈ 2,200 px) |
| R3-3 | 3 | "up to 25" over the wrong set | FIXED r3 (untriaged maximum 9) — same as rules-p3-5 |
| R3-4 | 3 | Growth SQL vs `load()`'s empty-to-`?` | FIXED r3 (`coalesce(nullif(category,''),'?')`) |
| R3-5 | 3 | Redirect tied to `_LEGACY_TOKEN_UNTIL` | FIXED r3 (a permanent `303`, D8 restated) — same as rules-p3-4 |
| R3-6 | 3 | CSP "concerns scripts" | FIXED r3 (where MDN's warning sits) |
| rules-p3-1 | 3 | Re-arm to 0 disables the bound | FIXED r3 (never below 1 ms; nothing left → error state) |
| rules-p3-2 | 3 | `registry_db.py:35-37` | FIXED r3 (`:33-35`) |
| rules-p3-3 | 3 | Services has no refresh cadence | FIXED r3 (fetch triggers stated from `app.js`; cache rationale restated) |
| rules-p4-1 | 4 | "a permanent `303`" — 303 is not a permanent code | FIXED r4 (a `303` with no removal date, asserted by the board test; D8 and § Contract deltas) — same as context R3-5's nit |
| context-p4-1 | 4 | CSP "inline-JavaScript heading" not held by ledger st-9 | FIXED r4 (the sentence states only what st-9 quotes) |
| panel-1 | 6 | psycopg2 in the board vs the parent's "no new dependency" (opus) | FIXED r6 (D9: a named exception, lazy import inside the guarded collector; the JSON-snapshot alternative recorded) |
| panel-2 | 6 | `load()` cannot receive the deadline (opus) | FIXED r6 (`load(conn, *, before_query=None)`) |
| panel-3 | 6 | Attention misses the data source failing (opus) | FIXED r6 (stale-registry and stalled-classifier entries, D10; `classified_at` passed to `render`) |
| panel-4 | 6 | Filter has no inverse; zero-match groups stay (opus + fable) | FIXED r6 (opened-by-filter mark, zero-match hidden, close on clear, hand-opened kept; smoke assertions) |
| panel-5 | 6 | No `select()` component; substring match makes `free` show `freemium` (fable) | FIXED r6 (`components.select()`, token mode) |
| panel-6 | 6 | Backlog above the live pool/API cards; 20 tombstone rows (fable; opus risk) | FIXED r6 (inventory follows the cards; a reason with more than five rows collapses to a count; height re-derived) |
| P7-1 | 7 | "Classifier stalled" fires forever on an empty queue | FIXED r7 (gated on Untriaged > 0) — same as rules-p7-1 |
| P7-2 | 7 | Raw provider names as ids fail `_id()` | FIXED r7 (`slug(text, prefix)`, a prefix per kind, every `<details>` covered; 12 names, `captcha` collision) — with rules-p7-2 |
| P7-3 | 7 | Spliced cache sentence | FIXED r7 |
| P7-4 | 7 | Data-age wording vs `freshness()` text; static loses the date | FIXED r7 (`services.inv.synced` embeds `freshness(synced_at, 86400)`; static prints the dated instant) — with rules-p7-3 |
| P7-5 | 7 | Collapsed reason "points at its table" across many tables | FIXED r7 (a native `<details>` listing every name) |
| P7-6 | 7 | "12 board test sites" vs 11 listed | FIXED r7 |
| P7-7 | 7 | ~125 KB is the old page's size | FIXED r7 (the new fragment is measured by the build) |
| P7-8 | 7 | `sys.path` insert position | FIXED r7 (append) |
| rules-p7-4 | 7 | psycopg2 2.9.11 | FIXED r7 (2.9.9 on `/usr/bin/python3`) |
| rules-p7-5 | 7 | "cards below" after the move | FIXED r7 ("above the section") |
| rules-p7-6 | 7 | Opened-by-filter mark lost on swap | FIXED r7 (derived again from the filter state on re-apply) |
| rules-p7-7 | 7 | Lazy `sys.path` add grows per request | FIXED r7 (once, at import time, guarded) |
| R8-1 | 8 | Live data-age line reads "Registry Read 3 h ago" — same as rules-p7-3 FIX_WRONG | FIXED r8 (rewritten: the card's standard `freshness()` age; static prints dated, zoned instants) |
| rules-p7-6b | 8 | Re-deriving the filter mark marks hand-opened matching groups | FIXED r8 (rewritten: the filter records the `slug()` ids it opened in its stored state) |
| R8-2 | 8 | psycopg2 2.9.9 vs 2.9.11 | FIXED r8 (both stated: 2.9.11 user site with `HOME`, 2.9.9 system site) |
| R8-3 | 8 | "80-odd" script names | FIXED r8 (77) |
| R9-2 | 9 | Opened-by-filter record inside `qd-filter:<group>` resets the store | FIXED r9 (its own key `qd-filter-open:<group>`; a filter → swap → clear smoke step) — same as rules-p7-6c |
| rules-p10-1 | 10 | `app.js:489-495` / `:499-506` citations off | FIXED r10 (`:492-498`, the reset at `:504`; the helper wording) |
| R9-1 | 9 | Static file has no text for `synced_at = None` | FIXED r9 ("Registry never synced") |
| panel-7 | 6 | Plan risks (both seats) | FIXED r6 (§ Risks the plan carries; stable disclosure ids, `freshness()` age, cache lock written into § Data flow / § Failure) |
