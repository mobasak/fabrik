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
