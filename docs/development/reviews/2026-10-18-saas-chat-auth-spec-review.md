# Spec review — the saas-skeleton chat that only a signed-in, rate-limited user can spend (W-ab242b11 slice 2)

**Command:** /fabrik-spec-review
**Spec:** `docs/superpowers/specs/2026-10-18-saas-skeleton-chat-auth-design.md` (CONVERGED, md5 b2a4e384a4a39063a80a0f435547e368; approval row D-1010)
**Research ledger:** `docs/reference/research/2026-10-18-saas-chat-auth-ledger.md`
**Shape:** agent-tool (D-961: the Workflow tool is never called)
**Status:** CONVERGED

## Pass Ledger

| Pass | seats · axes re-checked (intake · personas · facts · vendor · approach · completeness · constraints) | counters | method | spec md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (slice A, rules: digest, chosen approach, fabrik-lib verdict, shape, docs, decisions) + sonnet×1 (slice B, the rest: personas → intake, lifecycle, validation, unknowns) + sonnet×1 fabrik-researcher (slice R, the cited facts) · all axes | found: 24, new: 24, confirmed: 20, fixed: 20, unexecuted: 0, edits: 24 | method: every candidate re-executed by the lead — `infra/vps1/redis/compose.yaml:6` allkeys-lru, `router.py:150-155` empty `client_ip`, `scaffold.py:2725-2735` `aclose`, the slice-1 grader's "openrouter" bans (`:82`, `:106`), the fabrik-lib README module rows (:16, :18, :20, :23, :28, :175), `cost-budget` `reserve` signature, the passwordless `_RATE_LUA`, Redis eval-intro raw-fetched with curl | fca6efaaceecbce4cb5c31c5467179e8 → 00f5d2d09d520440c9583b87bd105f26 |
| Pass 2 | opus×1 + sonnet×1 + sonnet×1 fabrik-researcher (round-1 owners) · delta over the round-1 fix + one hop | found: 12, new: 12, confirmed: 10, fixed: 10, unexecuted: 0, edits: 13 | method: re-derivation — K1-K12 and the seven slice-B items re-executed (closed but N1-N7); new candidates re-executed by the lead: `infrastructure.py:1424-1454` and `spec_loader.py:331-337` (each app gets its own logical DB — the "shared DB 0" premise was false), README:68 `api-quota/`, `router.py:153-154`, `passwordless.py:174-181`, the seven-repo census `ls /opt/*/app/api/chat/route.ts` (6 identical header md5s + 1 variant) | 00f5d2d09d520440c9583b87bd105f26 → fc2d459d800f01f9534d81374733e429 |
| Pass 3 | opus×1 + sonnet×1 (round-1 owners) · delta over the round-2 fix + one hop; slice R standing clean from Pass 2 (no fact changed) | found: 6, new: 6, confirmed: 5, fixed: 5, unexecuted: 0, edits: 6 | method: re-derivation — N1-N7 re-executed CLOSED; new by the lead: `dependencies.py:84-89` (direct-call wrapper), `cost_reservations.py:226` `a_reserve`, `drivers/redis.py:298` `release_db_index(flushdb=False)` | fc2d459d800f01f9534d81374733e429 → 9522e3a8d25fc310f5bcdf0e6fd79ef8 |
| Pass 4 | opus×1 (round-1 owner) · the pass-3 fixed set only (scope-growth remainder round) | found: 2, new: 2, confirmed: 2, fixed: 2, unexecuted: 0, edits: 2 | method: re-derivation — the six pass-3 hunks re-executed; `cost_reservations.py:23`, `:65` (psycopg, not asyncpg); the residual-risk bullet's two remedies | 9522e3a8d25fc310f5bcdf0e6fd79ef8 → 7ee6c649c44a3a8ab1e0da0ea05a9ead |
| Pass 5 | sonnet×1 (round-1 owner of slice B) · the pass-4 fixed set only (scope-growth remainder round) | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 1 | method: re-derivation — `redis.py:349-351` FLUSHDB only under `if flushdb:`; the no-evict remedy is fleet Redis config (`compose.yaml:6`), not a driver change | 7ee6c649c44a3a8ab1e0da0ea05a9ead → 7a1f7c09556c485c6903fd752b7f2037 |
| Pass 6 | sonnet×1 (round-1 owner) · the pass-5 fixed line only; slices A and R standing clean | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — `compose.yaml:6`, `redis.py:298` signature, the FLUSHDB guard and the one-window bound re-executed; hygiene `--phrase` sweep 0 hits (proven able to fire on a planted phrase); `check_citations_resolve.py --doc` 26 graded, all land; `check_spec_convergence.py` on a flipped scratch copy: 1 CONVERGED spec examined, 0 findings | 7a1f7c09556c485c6903fd752b7f2037 → 7a1f7c09556c485c6903fd752b7f2037 |
| Pass 7 | opus×1 + fable×1 (the design-approval panel, D-613; independent, same brief, author-blind) · design gate over the converged spec | found: 17, new: 17, confirmed: 13, fixed: 13, unexecuted: 0, edits: 22 | method: both seats sound-with-changes; every concern re-executed by the lead before folding — `settings.py:72`, `:103`, `:109` (15-minute access cookie, open auto-signup), `router.py:1203-1205` (tenantless signup), `SSEStream.tsx:32-36`, `:52-58`, `:85`, `:88-90`, `:96`, `scaffold.py:2266`, `dependencies.py` imports (a leaf, but the package `__init__` needs argon2), `csrf.py:199`, the template's missing login page | 7a1f7c09556c485c6903fd752b7f2037 → 160e7a2d23795f70602d11f5ed55ad00 |
| Pass 8 | opus×1 + sonnet×1 (round-1 owners) · delta over the panel fold + one hop | found: 15, new: 15, confirmed: 10, fixed: 10, unexecuted: 0, edits: 13 | method: re-derivation — every panel hunk re-checked; new by the lead: `router.py:777-789` (a cookie refresh rotates the CSRF token), `settings.py:13` email-validator and `.venv` `import email_validator` → ModuleNotFoundError (fleet item W-0ae9b7e1), `pause_state.py:156-167`, `dependencies.py:64`, the stale Degradation list | 160e7a2d23795f70602d11f5ed55ad00 → 6ec551574307a48f2cd32d4310bf2389 |
| Pass 9 | opus×1 + sonnet×1 (round-1 owners) · the pass-8 fixed set only | found: 7, new: 7, confirmed: 5, fixed: 5, unexecuted: 0, edits: 7 | method: re-derivation — 12 pass-8 items re-executed CLOSED; new: `ip_address('')` raises ValueError (so "keyed as written" covered the empty value), the dropped TTL re-arm made "always carries a TTL" false, `Retry-After` had no floor | 6ec551574307a48f2cd32d4310bf2389 → e9d696c0d76dfb59f9e517356077d140 |
| Pass 10 | opus×1 (round-1 owner of slice A) · the pass-9 fixed set only (scope-growth remainder round); slices B and R standing clean | found: 4, new: 4, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — the 7 pass-9 lines re-executed (6 CLOSED); `router.py:149-154` return values and the unparseable-IP skip re-checked; the two own-fix residues and two plan-time items are RECORDED below, not confirmed (scope-growth stop, D-355) | e9d696c0d76dfb59f9e517356077d140 → e9d696c0d76dfb59f9e517356077d140 |

The scope-growth stop fired at Pass 9 (own-fix 9 of 10 at Pass 8, 5 of 5 at Pass 9). Own-fix residue raised after it is RECORDED onto the slice-2 re-plan (`/fabrik-plan-after-chat`, then `/fabrik-plan-review`, under W-ab242b11). It does not reopen this loop.

## Recorded, not confirmed

| Id | Pass | Anchor | Verdict |
|---|---|---|---|
| R-research-cluster | 1 | E5 redis-py cluster pipelines | RECORDED — measured (redis-main is standalone Redis 7, `compose.yaml:3`; E5 later removed with the move to one Lua script) |
| R-reasoning-tokens | 2 | `CHAT_MAX_TOKENS` default 1024 on reasoning models | RECORDED — measured (ledger chat-16; the default's choice goes to the plan) |
| R-e9-verbatim | 2 | E9 quotes unverified verbatim | RECORDED — measured (openrouter.ai returns 403 to WebFetch, exa and curl; the spec's Method line says so; ledger chat-11, chat-12) |
| R-step-budget | 8 | owner and user step counts treat the login page and the allowlist as one step each | RECORDED — measured (wording; changes no behaviour) |
| R-mechanism-phrasing | 8 | "refused from Content-Length…", "a streaming decode…" read as mechanism | RECORDED — measured (wording; changes no behaviour) |
| R-concurrency | 2 | no per-user concurrent-stream cap | RECORDED — measured (bounded by the user bucket, 60 per hour) |
| R-pttl-order | 10 | spec :107 — whether the refusal's `PTTL` is read before or after the TTL re-arm (before gives `Retry-After: 1` on a locked bucket) | RECORDED — measured (own-fix residue after the scope-growth stop; routed to the slice-2 plan under W-ab242b11: the returned TTL is the re-armed one, the Lua test asserts `Retry-After` equals the window) |
| R-above-limit | 10 | spec :107 — "at its limit" vs a manual write above it | RECORDED — measured (own-fix residue after the stop; routed to the slice-2 plan: "at or above its limit") |
| R-testclient-ip | 10 | TestClient's `request.client.host` is "testclient", which skips the IP bucket | RECORDED — measured (plan-time; routed to the slice-2 plan's test section: the IP-bucket rows set a parseable peer) |
| R-503-label | 10 | how the identity wrapper tells a denylist 503 from other refusals | RECORDED — measured (plan-time; routed to the slice-2 plan's chat.py design) |

## Ask ↔ spec

| # | The ask, in its owners' words | What the closing spec says | Anchor | Verdict |
|---|---|---|---|---|
| 1 | "any visitor can stream completions on the app's own OPENROUTER_API_KEY" | slice 1 deleted the public route (D-1005); slice 2's route refuses anonymous requests with a 401 | § Why this exists; § Chosen approach, order of checks | IN |
| 2 | "7 scaffolded projects carry the same route" | seven repos named by census, one adoption item each after merge | § Personas; I4 | IN |
| 3 | "needs a session/auth check" | `build_current_user` (header, then cookie, then a fail-closed denylist) | § Chosen approach, Identity | IN |
| 4 | "and a rate limit" | one Lua script over app, tenant, user and IP buckets, check-before-increment | § Chosen approach, Limits | IN, CHANGED (the app-wide bucket added by the panel because signup is open) |
| 5 | "before a scaffolded app goes public" | new scaffolds get it at merge; live projects adopt by item | § Lifecycle, Adoption | IN |
| 6 | "it's security" | full spec chain and review; fail-closed on every outage | § Lifecycle, Degradation | IN |
| 7 | "design the auth hook against the template's auth story (fastapi-user-auth / D-xxx)" | the vendored fastapi-user-auth, through a seam | § What exists today; § Chosen approach | IN |
| 8 | "the design trade-off you laid out (backend route vs /auth/me check vs Next-side limiter)" | A chosen; B2 (`/me` check), B1 and C rejected with reasons | § Rejected alternatives; § Decisions taken | IN |
| 9 | "ship slice 1 first … Then the W-ab242b11 spec amendment, then /fabrik-spec-review and the re-plan" | slice 1 shipped; this review; the re-plan is next | header; I22 | IN |
| — | (not asked) the client changes in `SSEStream.tsx` | credentials, CSRF header, refresh-once, cross-chunk buffer | § Chosen approach, Client | ADDED (without them every browser chat request is a 403 and frames are dropped) |
| — | (not asked) the request body cap and per-request token bound | 413 over 64 KiB; `max_tokens` | § Chosen approach, Body and Upstream | ADDED (bounds one request's cost and memory) |
| — | (not asked) residual risks | eviction, index reuse, the app bucket's availability trade-off | § Lifecycle | ADDED (accepted, each with its remedy) |

## Gates

Run at the close. The receipt was first graded while `IN-PROGRESS`, then flipped and graded again.

```text
$ python3 scripts/enforcement/check_spec_convergence.py docs/superpowers/specs/2026-10-18-saas-skeleton-chat-auth-design.md
spec convergence: 1 CONVERGED spec(s) examined of 1 named, 0 with findings (artifact-only; citations not re-fetched)
$ python3 scripts/enforcement/check_review_coverage.py docs/development/reviews/2026-10-18-saas-chat-auth-spec-review.md
check_review_coverage: OK — 0 unproven coverage claims across 1 explicitly-named review artifact(s)
$ python3 scripts/enforcement/check_citations_resolve.py --doc docs/superpowers/specs/2026-10-18-saas-skeleton-chat-auth-design.md --root .
✓ citations resolve — 28 `path:line` citation(s) across 1 docs all land — 28 graded of 55 found (15 bare filename, 1 ambiguous, 11 not under root /opt/fabrik/.claude/worktrees/fleet)
$ python3 scripts/check_research_ledger.py docs/reference/research/2026-10-18-saas-chat-auth-ledger.md
check_research_ledger: 0 refused of 16 rows across 1 ledger(s)
```

Hygiene ran at Pass 6 and before the Pass 8 pin (`check_review_hygiene.py --phrase` over the retired wording, 0 hits, shown able to fire on a planted phrase). Before Pass 6 it did not run at every pin. The design-approval panel: both seats sound-with-changes, every concern ACCEPTED, so both approve (D-1010):

Panel: opus="VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-18-saas-skeleton-chat-auth-design.md" fable="VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-18-saas-skeleton-chat-auth-design.md" → both-approve
