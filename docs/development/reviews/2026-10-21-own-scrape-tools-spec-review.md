# Spec review — own scrape and crawl tools, Firecrawl as fallback (W-10146d20)

**Command:** /fabrik-spec-review
**Spec:** `docs/superpowers/specs/2026-10-21-own-scrape-tools-design.md` (DRAFT at 1f51cf960)
**Evidence folder:** `/opt/fabrik/.tmp/runs/5ce9d888-9344-466f-b905-652ac93cdf89/fabrik-spec-2026-10-21T16-07-23-0300/`
**Shape:** agent-tool (D-961: the Workflow tool is never called)
**Status:** IN PROGRESS

## Pass Ledger

| Pass | seats · axes re-checked (intake · personas · facts · vendor · approach · completeness · constraints) | counters | method | spec md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (slice rules: Intake, fabrik-lib verdict, Fallback contract, Constraints Digest, Residual unknowns, Open items) + sonnet×1 (slice context: Personas → Lifecycle, Shape, Doc sites) + fabrik-researcher×1 (slice research: External dependencies and every external claim) · all axes | found: 29, new: 29, confirmed: 24, fixed: 24, unexecuted: 0, edits: 1 rewrite | method: citation + re-derivation — every candidate re-executed by the lead: ledger.json rows, `md5sum /opt/*/scripts/rivals_run.py` (50 + 1), rule 57:258-271 (stealth = fingerprint spoofing), the SDK migration guide (`FastMCP` → `MCPServer`), README address-guard lines, W-10146d20 `next` (staged switch), fabrik-lib D-132; ledger re-run with page-specific facts (`ledger2_run.py`), October calls counted (`fc_calls.py`) | 4ec83d67 → e9201bca |
| Pass 2 | the round-1 seats, own slices · delta over 1f51cf960..7de511bf2 + one hop | found: 10, new: 10, confirmed: 9, fixed: 9, unexecuted: 0, edits: 14 | method: re-derivation — 24 round-1 ids re-checked FIXED; U2's absence refuted by a second request method (`inspect5.py`: `Accept: text/markdown` returns the full 1.2 MB reference); U6's DataDome marker grepped in `html/U6.html`; example.com (131 chars) proved the 800-char floor refused real pages | e9201bca → 1937738f |
| Pass 3 | the round-1 seats, own slices · delta over 7de511bf2..d06de0089 + one hop | found: 9, new: 9, confirmed: 9, fixed: 9, unexecuted: 0, edits: 12 | method: re-derivation — rule 57:259-261 ("evades a hard rate limit") for the 429 row; `_cache_key` `webscrape.py`:495 hashes no headers; `is_bot_wall(U6.html)` False with 0 chars | 1937738f → f3a47125 |
| Pass 4 | the round-1 seats, own slices · delta over d06de0089..088443bcb + one hop | found: 5, new: 5, confirmed: 4, fixed: 4, unexecuted: 0, edits: 7 | method: re-derivation — `webscrape.py`:454-465 retries 429 on a fixed 2**attempt sleep and reads no `Retry-After`; `_do_request` `:474` takes no headers; RFC 6585 §4 (Retry-After MAY be sent) | f3a47125 → a3557eb1 |
| Pass 5 | the round-1 seats, own slices · delta over 088443bcb..e82bd323e + one hop | found: 5, new: 5, confirmed: 4, fixed: 4, unexecuted: 0, edits: 6 | method: re-derivation — `curl -H 'Accept: text/markdown' https://docs.firecrawl.dev/features/proxies` (default `auto` retries with enhanced proxies) settled the exa-versus-Firecrawl line; RFC 9110 §10.2.3 via MDN for the Retry-After forms; `fabrik-researcher.md` exa error `CRAWL_LIVECRAWL_TIMEOUT` (exa crawls live) | a3557eb1 → (pass 6 pin) |

## Findings

| Id | Pass | Anchor | Verdict |
|---|---|---|---|
| S-sonnet-1 · S-opus-1 | 1 | Chosen approach — render escalation used stealth | FIXED r1 (plain `/content` only; stealth never called) |
| S-sonnet-2 · S-opus-8 · S-researcher-3 | 1 | U6 — `is_bot_wall` false, "Turnstile" unproven | FIXED r1 (typed `blocked` reasons; U6 relabelled; later DataDome, G11) |
| S-sonnet-3 | 1 | Test ledger — common-word facts | FIXED r1 (pass 2 ledger: page-specific facts + clean ratio) |
| S-sonnet-4 · S-opus-3 | 1 | Lifecycle 6/8 gate; staged switch dropped from intake | FIXED r1 (I14-I16; per-command all-pass ledgers) |
| S-sonnet-5 | 1 | duties with no holder; researcher grant missing | FIXED r1 (P4-P7 duties; `mcpServers`; raw-fetch order) |
| S-sonnet-6..10 | 1 | counts, U5/U8 rows, "nine days", headings | FIXED r1-r2 |
| S-opus-2 | 1 | ladder "unchanged" contradicts CLAUDE.md tier 2 | FIXED r1 (`fabrik-scrape` in tier 1; three contracts + test amended) |
| S-opus-4 | 1 | "no call log" | FIXED r1 (192 October calls from transcripts) |
| S-opus-5, 11, 12 | 1 | vendored web_tools out of scope; D-132 reference; duplicate mail | FIXED r1 |
| S-opus-6 | 1 | robots / 4xx / scope rows missing | FIXED r1 |
| S-opus-7 · S-researcher-2 | 1 | no private-address guard | FIXED r1 (guard on every hop; G7) |
| S-opus-9 | 1 | crawl scoping beyond include paths | FIXED r1 (G2 incl. sitemap; G9) |
| S-opus-10, 13, 14 | 1 | Digest line; render untested; unknowns | FIXED r1 |
| S-researcher-1 | 1 | FastMCP paired with SDK v2.3.0 | FIXED r1 (`mcp>=2.3,<3`, `MCPServer`) |
| S-researcher-4, 5 | 1 | U2 as render evidence; credit API version | FIXED r1 |
| S-researcher-201 | 2 | U2 "parameters on sub-pages" | FIXED r2 (content negotiation measured; G10) |
| S-sonnet-201 | 2 | slice-1 gate unmeetable | FIXED r2 (G8/G10/G11 in slice 1; corrected facts) |
| S-sonnet-202 · S-opus-201 | 2 | 800-char floor refuses short pages | FIXED r2 (`short: true`; `empty` < 50 chars; HTML only) |
| S-sonnet-203..205 | 2 | DataDome; unsaved outputs | FIXED r2 (G11; `fc_calls.out`, `probes.out` saved) |
| S-opus-202, 203 | 2 | fallback order; precedence paraphrase | FIXED r2 (exa first; CLAUDE.md quoted; P1 approves the departure) |
| S-sonnet-301 | 3 | 429 sent to another vendor | FIXED r3 (reported; rule 57 rate-limit clause) |
| S-sonnet-302, 303 | 3 | `short` not in shape; second-method claim | FIXED r3 |
| S-researcher-301, 302 | 3 | "captcha" vs interstitial; unsourced trend | FIXED r3 |
| S-opus-301 | 3 | `empty` falls through to Firecrawl | FIXED r3 |
| S-opus-302..304 | 3 | departure list; verdict row; G10 default for every caller | FIXED r3 (G10 opt-in, Accept in the cache key) |
| S-sonnet-401 · S-researcher-401 · S-opus-401 | 4 | Retry-After promised, not built | FIXED r4 (G12, 30 s cap) |
| S-sonnet-402 | 4 | G10 header threading | FIXED r4 |
| S-opus-402 | 4 | `empty` sent to exa | FIXED r4 (reported only; server-down fallback limited) |
| S-sonnet-501 · S-opus-501 | 5 | exa allowed server-down, barred on `empty`, same reason | FIXED r5 (the line is Firecrawl's documented proxy escalation, cited; exa allowed on `empty` and server-down, never on a known wall; residual unknown on exa's crawler) |
| S-sonnet-502 | 5 | G12 row order; uncapped total wait | FIXED r5 (rows in id order; 60 s total per call) |
| S-researcher-501 | 5 | Retry-After forms cited to RFC 6585 | FIXED r5 (RFC 9110 §10.2.3; HTTP-date test case) |
