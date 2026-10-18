# Plan review — the external-services inventory plan set (W-3e9e2f4c)

**Command:** /fabrik-plan-review
**Plan:** `docs/development/plans/2026-10-18-plan-1-external-services-inventory/` (spine + T01–T04, DRAFT at fd756eadd)
**Spec:** `docs/superpowers/specs/2026-10-18-external-services-page-design.md` (CONVERGED, D-966)
**Shape:** agent-tool (D-961: the Workflow tool is never called)
**Status:** CONVERGED

## Pass Ledger

| Pass | seats · axes re-checked | counters | method | set md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (slice rules: spine Interfaces, Execution Discipline, Global Constraints, roll-up, File Scope; T02, T04) + sonnet×1 (slice context: T01, T03; spine agreed, intake, breadth, digest, ledger, Evidence, Self-audit, residuals) | found: 20, new: 20, confirmed: 19, fixed: 19, unexecuted: 0, edits: 31 | method: re-derivation — every candidate re-executed by the lead (the one-argument `render` lambda against the keyword call, `link()` over `/admin` and `#top`, a spy on `socket.socket.connect` around `psycopg2.connect`, the chain fakes' answer keys) | 57927e7d695b0abf43104f848437f88f → 346d93a7a99b0a7dc669734bb21d5eeb |
| Pass 2 | opus×1 + sonnet×1 (round-1 owners) · delta over every pass-1 hunk + one hop (fix1.diff, 436 lines) · shape: agent-tool | found: 8, new: 8, confirmed: 8, fixed: 8, unexecuted: 0, edits: 9 | method: re-derivation — 20 pass-1 ids re-executed (19 FIXED, context-7b recorded and accepted); new candidates re-executed by the lead: `link()` against a prefix gate (`http://a b` passes the prefix, `link()` refuses), the chain fake at `tests/test_external_services_chain.py:1643` (Decimal) and :2459 (the connect patch), `scripts/tests/test_registry_sync.py:41-44` (the opt-in writes the LIVE registry), `psycopg2.extensions.connection.cancel` (present); the collector's concurrency paragraph, which drew defects in two consecutive passes, was REWRITTEN whole around one lock and one outcome rule (the spec's error state) | baf2aa3d3422cc15ad18b1a17e467196 → d4eb141c00914aa1ad93ac7850fb4b18 |
| Pass 3 | opus×1 + sonnet×1 (round-1 owners) · the pass-2 fixed set only (scope-growth remainder round) · shape: agent-tool | found: 5, new: 5, confirmed: 5, fixed: 5, unexecuted: 0, edits: 6 | method: re-derivation — NEW-1…NEW-4 and context-9/-10 re-executed FIXED; new: `psycopg2`'s `cancel()` against a fake server that accepts and never answers froze every thread for 28 s (the rules seat's `probe_cancel.py`, re-read by the lead), keepalives left the query blocked over 12 s, the in-flight record held no connection handle, three concurrency rules had no assertion; context-11's claimed coverage absent (no fake answers `api_keys` rows) — the cancel and keepalives removed, the frozen-server wedge stated as an accepted residual, T02's first row guards `keys`/`projects` | f656f6cf8978a5b740dd1011aafb1f03 → 63680a366e9cbdc87333e57ce30139c1 |
| Pass 4 | opus×1 + sonnet×1 (round-1 owners) · the pass-3 fixed set only (scope-growth remainder round) · shape: agent-tool | found: 3, new: 3, confirmed: 2, fixed: 2, unexecuted: 0, edits: 12 | method: re-derivation — P3-1…P3-4 and context-11 re-executed FIXED; new: the accepted wedge departed from the CONVERGED spec's whole-read bound (`docs/superpowers/specs/2026-10-18-external-services-page-design.md:294`, :413 — read by the lead) and credited an unexecuted unix-socket probe; resolved by amending the spec (D-968, line-count neutral, § Amendments): the read runs in a child process killed at its deadline; the context seat's fake-routing note recorded, not a defect (the chain fakes answer `[]` for `api_keys`) | 2b88aae312931ea72add46212ab304a5 → c5e60b86f62025100bf039df4fa3ae11 |
| Pass 5 | opus×1 + sonnet×1 (round-1 owners) · the pass-4 fixed set and the spec amendment (D-968) + one hop · shape: agent-tool | found: 6, new: 6, confirmed: 6, fixed: 6, unexecuted: 0, edits: 8 | method: re-derivation — R4-1 and R4-2 re-executed FIXED; the child design probed (`kill()`+`wait()` on a child blocked in `recv()`: 0.001 s; spawn 0.046 s); new: the board-to-child contract incomplete, a stale § Data flow hook sentence, the `quota_dashboard.py:493` precedent wrong (only :592 runs `sys.executable`), unclosed pipes after a kill, the 5 s overrun after a kill, an isolation DSN that could look up a name — the last executed by the lead (`postgresql:///none?host=<missing dir>` fails in 0.0 s); the context seat confirmed 0 (13 spec cites re-read) | fc170c6d984ff3f6121d02d9a4ee4791 → c6f56ab63dca950194c675fa8bfc7c55 |
| Pass 6 | opus×1 + sonnet×1 (round-1 owners) · the pass-5 fixed set (the board-to-child contract, the spec edits) + one hop · shape: agent-tool | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 4 | method: re-derivation — F5-1..F5-6 re-executed FIXED (`kill()`+`communicate()` 0.001 s, both pipes closed; the isolation DSN fails in 0.000 s); new: the board had no test telling the child's line from a raw traceback (an import failure before the handler printed `Traceback (most recent call last):`, probed) — fixed by imports inside the child's one `try` and a one-line `^[A-Za-z_][\w.]*: ` test, executed by the lead (handled → the class line, crash and silent exit → `ReadFailed`); the context seat confirmed 0 (13 spec cites re-read, 565 lines) | f8bab6847243d5d31bb1b8198ac03e55 → 10f78772dba1ff6ceb7bd6bad00dd213 |
| Pass 7 | opus×1 (the rules slice's round-1 owner; the context slice untouched since its pass-6 zero) · the pass-6 fix (T04's child error line) + one hop · shape: agent-tool | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 3 | method: re-derivation — F6-1 re-executed FIXED (6 classification cases); new: a warning printed before the child's line defeated the one-line test (`ReadFailed: <string>:2: UserWarning: w`, probed) — the site's second defect, so the rule was REWRITTEN, not patched: the board classifies the LAST non-empty stderr line against `^[A-Za-z_][\w.]*:`, which also reads a traceback's closing class line; row 4 pins it; executed by the lead over 7 cases (handled, crash, silent exit, warning + handled, warning + crash, empty message, stray last line) | 10f78772dba1ff6ceb7bd6bad00dd213 → 616f1005d6de380e101bc05d3dae3b89 |
| Pass 8 | opus×1 (the rules slice's round-1 owner; the context slice untouched since its pass-6 zero) · the pass-7 rewrite (T04's stderr classification) + one hop · shape: agent-tool | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 3 | method: re-derivation — F7-1 re-executed FIXED (7 of 7 cases); new: argparse's `SystemExit` escapes `except Exception` and its `inventory_read.py: error: …` line matched the class regex (probed, exit 2) — the stderr site's THIRD defect, so the site is DELETED: every outcome is one JSON object on stdout (`rows` on exit 0, a string `error` on exit 1, built under `except BaseException` with `--deadline` read by hand), stderr is never read, anything else is `ReadFailed: exit status <n>` — which also closes the held exit-0 bad-JSON gap; executed by the lead over 10 cases (success, import, multi-line message, interrupt, empty message, argv missing, argv bad, raw crash, exit-0 junk, exit-0 error) | 616f1005d6de380e101bc05d3dae3b89 → 961001d9bec01ddd3c30fd7c2000d17a |
| Pass 9 | opus×1 (the rules slice's round-1 owner; the context slice untouched since its pass-6 zero) · the pass-8 rewrite (T04's one-JSON-object outcome contract) + one hop · shape: agent-tool | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — F8-1 re-executed FIXED (the JSON outcome contract re-run independently); no contradiction with spec § Failure (`docs/superpowers/specs/2026-10-18-external-services-page-design.md:294`) or T04 rows 1-4; every Coverage Checklist row adjudicated; `check_plan_tickets` 0 findings | 9ea0929b4e22f4897f0888a32b4d401c → 9ea0929b4e22f4897f0888a32b4d401c |

## Findings

| Id | Pass | Anchor | Verdict |
|---|---|---|---|
| context-1 | 1 | T03 — "the keyword-only render keeps the one-argument lambdas valid" | FIXED r1 (`main()`'s keyword call refuses `lambda rows:`; the patches at `tests/test_external_services_chain.py:242`, :255 become `lambda rows, **kw:`) |
| context-2 | 1 | T03 — rules its tests assert left unquoted | FIXED r1 (spec :155-158 and :162-165 quoted; the ten-column map stated; TZ pinned in the test) |
| context-3 | 1 | Self-audit — "the static wrapper measured in T03" | FIXED r1 (T04's browser row opens the static file and measures it) |
| context-4 | 1 | Constraints Digest — two rows truncated | FIXED r1 (whole bullets) |
| context-5 | 1 | T03 `_read()` — who closes the connection | FIXED r1 (`finally` close on every path; a row) |
| context-6 | 1 | T01 — the count texts and their keys | FIXED r1 (`filter.shown`, `filter.group_count` added by T01; read from `shell()`'s catalogue) |
| context-7a | 1 | T01 — a reload of the filter record | FIXED r1 (row covers swap and reload) |
| context-7b | 1 | T01 — option labels outside the literal scan | RECORDED — the labels come from `t()`, the catalogue the scans already cover |
| context-8 | 1 | T03 — "quota_dashboard is never imported" test shape | FIXED r1 (a fresh subprocess) |
| rules-1 | 1 | T02 — synced_at on an empty answer | FIXED r1 (both `None` and `(None,)`; the fakes' literal substrings kept) |
| rules-2 | 1 | T02 — what `link()` refuses | FIXED r1 (`link()` accepts `/…` and `#…`; provider URLs gated to `^https?://` first) |
| rules-3 | 1 | T04 — the socket guard and libpq | FIXED r1 (a loud `registry_db.connect` stub in `after_load`, :46) |
| rules-4 | 1 | T04 — the 5 s bound under a waiting second request | FIXED r1 (one deadline per request from its arrival) |
| rules-5 | 1 | T02 — the filter wire outside its read set | FIXED r1 (`app.js` and `views/commands.py` in Context Files; a data-f row) |
| rules-6 | 1 | T02 — spec § Validation rows unmapped | FIXED r1 (rows 3-4 rewritten over every rule, boundary and None case) |
| rules-7 | 1 | T04 — browser smoke steps missing | FIXED r1 (zero-match hidden, attention unchanged, swap) |
| rules-8 | 1 | T04 — no census-scale fixture | FIXED r1 (`tests/external_services_fixture.py`, owned by T02) |
| rules-9 | 1 | Ticket breadth — T04 indivisibility | FIXED r1 (the route half named as peelable and why it stays) |
| rules-10 | 1 | T04 — abandoned workers unbounded | FIXED r1 (at most one read alive) |
| rules-11 | 1 | T04 — the generator also writes `llms.txt` | FIXED r1 (in Touches and File Scope) |
| rules-12 | 1 | T04 — the slot's 60 s start | FIXED r1 (from the read's start) |
| NEW-1 | 2 | T04 — the start-a-read decision not atomic | FIXED r2 (one lock over every decision, never held across a read; every wait bounded by the request's deadline) — the paragraph rewritten whole |
| NEW-2 | 2 | T04 — two fallback policies | FIXED r2 (one outcome rule: the spec's error state) |
| NEW-3 | 2 | T04 Scope vs the spine's breadth note on the route | FIXED r2 (the route stays by choice, both places) |
| NEW-4 | 2 | T02 — the https gate read as a prefix test | FIXED r2 (a link only when it starts with http(s):// AND link() accepts it whole) |
| PLAUSIBLE-1 | 2 | T04 — a permanently wedged read | FIXED r2 (cancel() at the read's deadline, keepalives on the connection) |
| context-9 | 2 | Ticket breadth — T03 six rows | FIXED r2 (seven) |
| context-10 | 2 | T03 — the Decimal cite | FIXED r2 (:1643-1650 Decimal, :2419-2420 float) |
| context-11 | 2 | Residual — REGISTRY_WRITE_TESTS gate step | FIXED r2 (resolved without a gate run: the opt-in writes the live registry; the shape is covered by the fake-cursor cases) |
| P3-1 | 3 | T04 — the starter's `cancel()` | FIXED r3 (removed: it freezes every board thread against a silent server — executed) |
| P3-2 | 3 | T04 — keepalives claimed to end a stalled read | FIXED r3 (removed; the frozen-server wedge is an accepted residual, every request still answers within 5 s) |
| P3-3 | 3 | T04 — no connection handle in the in-flight record | FIXED r3 (moot: nothing cancels) |
| P3-4 | 3 | T04 row 3 — three concurrency rules untested | FIXED r3 (failed read keeps the last good read, the in-flight field clears, the lock wait is bounded, no thread cancels) |
| context-11b | 3 | Residual — the claimed fake-cursor coverage of keys/projects | FIXED r3 (T02 row 1 feeds api_keys rows of each kind; cites :1117, :2459-2462) |
| R4-1 | 4 | Residual — the accepted wedge vs the spec's whole-read bound | FIXED r4 (spec amended, D-968: the read runs in a child process killed at its deadline; the wedge is gone) |
| R4-2 | 4 | T04 — an unexecuted unix-socket probe credited | FIXED r4 (the keepalive text removed with the mechanism; execution credited only to the TCP probe) |
| context-p4 | 4 | T02 — the new fake must route max(last_seen) before FROM api_keys | RECORDED — T02's own fake; the chain fakes answer [] for api_keys |
| F5-1 | 5 | T04 — the board-to-child contract | FIXED r5 (`--deadline` argv, the JSON shape and types, the stderr line format, fixed classes for a kill and a bare failure) |
| F5-2 | 5 | Spec § Data flow — the hook placed in the collector | FIXED r5 (the child's; § Amendments lists § Data flow; line-count neutral) |
| F5-3 | 5 | Spec and T04 — the :493 precedent | FIXED r5 (only :592) |
| F5-4 | 5 | T04 — pipes left open after a kill | FIXED r5 (`communicate()` after `kill()` reaps and closes both pipes) |
| F5-5 | 5 | T04 — the 5 s overrun after a kill | FIXED r5 (the read's deadline is 4.5 s after the spawning request's arrival) |
| F5-6 | 5 | T04 — the isolation DSN could look up a name | FIXED r5 (a missing unix-socket directory; fails in 0.0 s, executed) |
| F6-1 | 6 | T04 — no stated test for the child's stderr line vs a raw traceback | FIXED r6 (imports inside the child's one `try`; the board takes stderr as the line only when it is one line matching `^[A-Za-z_][\w.]*: `, else `ReadFailed`) |
| F7-1 | 7 | T04 — a warning before the child's line hid the failure's class | FIXED r7 (rewritten: the last non-empty stderr line is classified; row 4 pins a warning before an import failure) |
| F8-1 | 8 | T04 — argparse's exit line read as the failure's class | FIXED r8 (the stderr site deleted: every outcome is one JSON object on stdout, `--deadline` read by hand under `except BaseException`) |

**Carried to /fabrik-execute-plan (T04 builder notes, recorded at pass 9, not defects):** the spawn passes the READ's deadline (the spawning request's arrival + 4.5 s) as `--deadline`; and the board may harden its fresh-read test to `rows` a list of objects and `synced_at` a number or `null` (a child keeping its contract cannot produce another shape — `inventory.load()` returns a list).

## Plan approval (Opus + Fable panel, D-613/D-330)

Two `fabrik-reviewer` seats, one `opus` and one `fable`, the same brief, neither shown the other's answer, over the set pinned at `6bc13faa1`. **Both: APPROVE-WITH-CHANGES.** Both named the same change; the Fable seat named one more. Both were folded and the plan is approved as amended (D-971).

| # | Seat | Change | Disposition |
|---|---|---|---|
| P-1 | opus + fable | `CHANGELOG.md` and `INDEX.md` (spec § Documentation landing sites, `docs/superpowers/specs/2026-10-18-external-services-page-design.md:445`, :452) were owned by no ticket; `check_doc_sync.py` refuses a code commit without its CHANGELOG entry | FOLDED — every ticket's Docs line names its CHANGELOG entry and its INDEX rows; the spine's shared-tree constraint stages those two ledgers in each ticket's commit outside File Scope (the opus seat's point: `check_plan_tickets.py:532-533` keeps shared-append files out of the lock, so File Scope stays as it is) |
| P-2 | fable | T03 row 1 said "only https provider hrefs" where the spec says `https?` (spec :354) | FOLDED — `https?` |

Not changes, both seats: no design question left open (the 4,000 px measurement and the static file's retirement owner are owned by the build); the two carried builder notes stand as notes. Fable's builder note (T02's day-granularity `credit_cell` age may change the data-stamp across a day boundary, which row 8's one-minute window cannot reach) is carried with them.

Set md5 after the folds: `3696940323d10f75cb4df83616c64247` (was `f771705a99c6fb7f7834a3506c629468` at the CONVERGED flip). `check_plan_tickets` 0 findings; `check_citations_resolve` 132 of 132 graded cites land across the five files.
