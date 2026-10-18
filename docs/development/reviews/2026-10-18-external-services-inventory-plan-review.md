# Plan review — the external-services inventory plan set (W-3e9e2f4c)

**Command:** /fabrik-plan-review
**Plan:** `docs/development/plans/2026-10-18-plan-1-external-services-inventory/` (spine + T01–T04, DRAFT at fd756eadd)
**Spec:** `docs/superpowers/specs/2026-10-18-external-services-page-design.md` (CONVERGED, D-966)
**Shape:** agent-tool (D-961: the Workflow tool is never called)
**Status:** IN REVIEW

## Pass Ledger

| Pass | seats · axes re-checked | counters | method | set md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (slice rules: spine Interfaces, Execution Discipline, Global Constraints, roll-up, File Scope; T02, T04) + sonnet×1 (slice context: T01, T03; spine agreed, intake, breadth, digest, ledger, Evidence, Self-audit, residuals) | found: 20, new: 20, confirmed: 19, fixed: 19, unexecuted: 0, edits: 31 | method: re-derivation — every candidate re-executed by the lead (the one-argument `render` lambda against the keyword call, `link()` over `/admin` and `#top`, a spy on `socket.socket.connect` around `psycopg2.connect`, the chain fakes' answer keys) | 57927e7d695b0abf43104f848437f88f → 346d93a7a99b0a7dc669734bb21d5eeb |
| Pass 2 | opus×1 + sonnet×1 (round-1 owners) · delta over every pass-1 hunk + one hop (fix1.diff, 436 lines) · shape: agent-tool | found: 8, new: 8, confirmed: 8, fixed: 8, unexecuted: 0, edits: 9 | method: re-derivation — 20 pass-1 ids re-executed (19 FIXED, context-7b recorded and accepted); new candidates re-executed by the lead: `link()` against a prefix gate (`http://a b` passes the prefix, `link()` refuses), the chain fake at `tests/test_external_services_chain.py:1643` (Decimal) and :2459 (the connect patch), `scripts/tests/test_registry_sync.py:41-44` (the opt-in writes the LIVE registry), `psycopg2.extensions.connection.cancel` (present); the collector's concurrency paragraph, which drew defects in two consecutive passes, was REWRITTEN whole around one lock and one outcome rule (the spec's error state) | baf2aa3d3422cc15ad18b1a17e467196 → d4eb141c00914aa1ad93ac7850fb4b18 |
| Pass 3 | opus×1 + sonnet×1 (round-1 owners) · the pass-2 fixed set only (scope-growth remainder round) · shape: agent-tool | found: 5, new: 5, confirmed: 5, fixed: 5, unexecuted: 0, edits: 6 | method: re-derivation — NEW-1…NEW-4 and context-9/-10 re-executed FIXED; new: `psycopg2`'s `cancel()` against a fake server that accepts and never answers froze every thread for 28 s (the rules seat's `probe_cancel.py`, re-read by the lead), keepalives left the query blocked over 12 s, the in-flight record held no connection handle, three concurrency rules had no assertion; context-11's claimed coverage absent (no fake answers `api_keys` rows) — the cancel and keepalives removed, the frozen-server wedge stated as an accepted residual, T02's first row guards `keys`/`projects` | f656f6cf8978a5b740dd1011aafb1f03 → 63680a366e9cbdc87333e57ce30139c1 |
| Pass 4 | opus×1 + sonnet×1 (round-1 owners) · the pass-3 fixed set only (scope-growth remainder round) · shape: agent-tool | found: 3, new: 3, confirmed: 2, fixed: 2, unexecuted: 0, edits: 12 | method: re-derivation — P3-1…P3-4 and context-11 re-executed FIXED; new: the accepted wedge departed from the CONVERGED spec's whole-read bound (`docs/superpowers/specs/2026-10-18-external-services-page-design.md:294`, :413 — read by the lead) and credited an unexecuted unix-socket probe; resolved by amending the spec (D-968, line-count neutral, § Amendments): the read runs in a child process killed at its deadline; the context seat's fake-routing note recorded, not a defect (the chain fakes answer `[]` for `api_keys`) | 2b88aae312931ea72add46212ab304a5 → c5e60b86f62025100bf039df4fa3ae11 |

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
