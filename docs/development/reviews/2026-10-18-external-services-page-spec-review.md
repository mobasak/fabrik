# Spec review — the external-services inventory in the command centre (W-3e9e2f4c)

**Command:** /fabrik-spec-review
**Spec:** `docs/superpowers/specs/2026-10-18-external-services-page-design.md` (DRAFT at 159b3bac2)
**Research ledger:** `docs/reference/research/2026-10-18-external-services-page-ledger.md`
**Shape:** agent-tool (D-961: the Workflow tool is never called)
**Status:** IN REVIEW

## Pass Ledger

| Pass | seats · axes re-checked (intake · personas · facts · vendor · approach · completeness · constraints) | counters | method | spec md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (slice rules: chosen approach, design, contract deltas, decisions, digest) + sonnet×1 (slice context: personas → intake, lifecycle, docs, unknowns) + sonnet×1 fabrik-researcher (slice research: the cited facts) · all axes | found: 32, new: 32, confirmed: 24, fixed: 24, unexecuted: 0, edits: 27 | method: every candidate re-executed by the lead — census recount from the embedded JSON (attention union 37, account 0 of 466, 17 real categories, 115 categorised), `app.js` read at :10, :36, :453-540, :700-717, `components.table` / `_esc` / `live_region`, `PORTS.md` grep (no 8770), the reference greps | 7ca217c17d4cd1036bfa8ca75c01e1f6 → 4e783eefc45760a2205ee1414a7dd0a6 |
| Pass 2 | opus×1 + sonnet×1 + sonnet×1 fabrik-researcher (round-1 owners) · delta over every round-1 hunk + one hop | found: 16, new: 16, confirmed: 13, fixed: 13, unexecuted: 0, edits: 22 | method: re-derivation — 28 round-1 ids re-executed (27 FIXED, rules-11 FIX_WRONG); new candidates re-executed by the lead: `clamp()` markup and `initClamps` `app.js:587`, the test grep for the removed names (12 sites), `registry_db.connect()` `:35-37`, the 115-row recount (88 keys, 5 bad URLs), `/repos.html` precedent `quota-dashboard.md:249`, the strings keys `:468-471` | 4e783eefc45760a2205ee1414a7dd0a6 → d5ab9930668d0e62184d6b075b7e129b |

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
