# Manifesto command pass — whole-plan integration receipt (T01–T34)

Status: DONE
Surface: plan set docs/development/plans/2026-08-31-plan-1-manifesto-command-pass/ — cumulative corpus diff `git diff 0ddfbb96..HEAD -- commands/_sources commands/_fragments` (36 files, +286/−98, pre-T34; +2 back-flip fixes in this commit).

## The run in one paragraph

All 32 command sources + the 21-fragment baseline were evaluated against checklist item 63b's six manifesto intersections, one serial ticket each (T01–T33), each with minimal fixes, a per-ticket author-blind verification review converged to its quiet round, and an atomic merge (source + artifact + Board flip + CHANGELOG + render + push). **The per-ticket verifier falsified the initial stamp 33 times in 33 tickets** — the floor is measurably load-bearing. Three ledger rulings were minted en route (D-048 exit vocabulary; D-050 rivals budget pair; D-051 design-system ladder), one duplicate id healed (D-047→D-049), and the decision-mint law now runs the full pipeline: authoring-session rulings (spec/plan-after-chat/deploy-plan) → freeze/flip mints (flows/data-contract/ui-design + review twins, plan-review, spec-review triple) → approval mints (spec-review) → operational mints (release cut/waiver, repo-review security deferrals, upstream ranked-options, decommission/deploy/conformance/catchup/docs-review/execute-plan/features).

## Per-ticket ledger (33/33 + this receipt)

| T | commit | surface | outcome |
|---|---|---|---|
| T01 | da616e2c | 21 fragments | baseline 21/21, 2 fixed |
| T02 | f08fd7bc (+back-flip here) | design-review | output-shape fix; D-048 termination fix landed at T34 via sanctioned back-flip |
| T03 | 2c3ed015 | fabrik-catchup | same-change atomicity + undecidable downgrade |
| T04 | e85c6c93 ⚠ | fabrik-conformance-review | exit regression killed + SUPERSEDED routing (⚠ the emit-gate WARN: this commit touched T01's Touches under Agent-Task: T04 — the sanctioned orchestrator-applied fragment fix, recorded then) |
| T05 | 2879f16d | fabrik-data-contract | freeze mints SAME-change |
| T06 | f02f00e8 | fabrik-decommission | retirement row + ONE-WAY superseding row law |
| T07 | d39ac778 | fabrik-deploy | "built X at Y" mint (mirror fixed in T09's commit, D4 back-flip) |
| T08 | ca3193e7 | fabrik-deploy-plan | authoring-time mints; abandoned-DRAFT class established |
| T09 | 3b108e31 | fabrik-deploy-plan-review | flip mint + staging recipe (the instruction-vs-recipe class) |
| T10 | 007f014d | fabrik-deploy-verify | four-token verdicts |
| T11 | 4b8a1869 | fabrik-doc-converge | ripple same-run + keyed mechanical edits |
| T12 | f24f7227 | fabrik-docs-review | DEAD-retirement routing + synced-docs denominator |
| T13 | adda9022 (+back-flip here) | fabrik-execute-plan | received-ruling mint + D6 salvage; D7 D-048 termination fix landed at T34 via sanctioned back-flip |
| T14 | 647ecf81 | fabrik-features | EARLY provenance + disposition routing + mode defaults |
| T15 | fc258ce1 | fabrik-flows | freeze mint, classify-at-mint, same-COMMIT staging |
| T16 | ad4564f1 | fabrik-flows-review | re-freeze + DRAFT-flip mints; freeze-law exception (cross-file) |
| T17 | fb31c245 | fabrik-generate-tests | scoped commits + fanout=None fail-mode |
| T18 | 34fe8ce2 | fabrik-plan-after-chat | chat-born mints (verifier-rebuilt; spec-approval routed to T28) |
| T19 | 8ee3e76c | fabrik-plan-review | CONVERGED-flip mint + symbol-referenced cites |
| T20 | 05107d05 | fabrik-release | waiver + cut mints (honest adjacent-commit recipe); @{u} fix |
| T21 | 5b846af5 | fabrik-repo-review | secrets carve-out; security-deferral mint; backlog append |
| T22 | 5a1cc329 | fabrik-review + term-coverage | D-048 RULED + fragment-root fix; D-047 dup → D-049 |
| T23 | a4c6fe3a | fabrik-review-scoped | runnable scope ref + ownership honesty |
| T24 | 3b0a1445 | fabrik-rivals | source conforms; D-050 minted |
| T25 | facedce0 | fabrik-rules-review | ledger-read both modes; secrets carve-out; D-048 counting |
| T26 | 84f45b6a | fabrik-service-test + cert-handoff-grammar | P0–P3 criteria at fragment root; credential carve-out |
| T27 | f965cfd1 | fabrik-spec | authoring-session mint (the T08 class) |
| T28 | 6d95eb47 | fabrik-spec-review | the triple mint — T18 route CLOSED |
| T29 | 483433d7 | fabrik-ui-design | freeze mint; in-review exception; carve-out; D-051 |
| T30 | c136f1a2 | fabrik-ui-design-review | both T16 mints mirrored |
| T31 | 58fa9915 | fabrik-upstream | live seeded-set; ranked-options mint; deferred backlog |
| T32 | 119f80d8 | fabrik-user-test | full-form carve-out + committed-evidence redaction |
| T33 | 7493aa03 | fabrik-workflow-review | artifact-vs-stale-lock fork; secrets class REFUTED-with-argument |
| — | 414d176d | assemble_commands.py | promoted renderer fix (red-first, 2 regression tests) |
| — | 603a8db0 / 58ae9d11 | backlog / hub CLAUDE.md | orchestrator side-commits |

Per-command 63b verdict tables: `docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-T##-<cmd>-review.md` — **32/32 command sources adjudicated** (T02–T33; T01 covers the 21 fragments) + this receipt = 34 artifacts, all in INDEX.md.

## Rubric (armed the whole-plan pass — verbatim `review_rubric.py --changed <the 36 diffed corpus paths>` output, first 40 lines of the FLOOR)

```
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3)

### core/35-security-auth.md
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: an error-open helper turns one bad/empty JWT into a full cross-tenant read. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on `middleware.ts` for access control.** CVE-2025-29927 allows complete middleware bypass via header manipulation.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.

### core/25-data-postgres.md
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.**
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Critical:** import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID` subclass). **PostgreSQL 18** (released Sep 2025) added native `uuidv7()` — if your instance is PG18+, you can use `DEFAULT uuidv7()` at the schema level instead of app-side generation. On PG16/17, generate app-side as above.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)

### core/30-ops.md
```

(The corpus diff is prose/contract text — the rubric's code-facing FLOOR classes map onto it as the four standing recurrence classes adjudicated below.)

## Coverage Checklist (whole-plan cumulative-diff review)

| class | verdict | evidence |
|---|---|---|
| mint-law consistency (24 files, 36 DECISIONS.md hits) | CLEAN | classify-at-mint present or CLAUDE.md-cited everywhere; ONE sanctioned staging deviation (release-cut adjacent-commit, reasoned in-source); pen-holder consistent (dispatching session) |
| D-048 propagation | FIXED(2) | design-review.md:37 + fabrik-execute-plan D7 (:553-556) still counted re-raises — cite-not-count landed via sanctioned back-flip in THIS commit; term-coverage/fabrik-review/conformance-review/rules-review verified already-correct against QUIET_PASS |
| secrets/credential carve-out family | CLEAN (5 landed + 1 refuted + 4 adjudicated-lower-risk) | repo-review/rules-review/service-test/ui-design/user-test phrasings compatible; workflow-review refuted-with-argument (T33 artifact); flows-review/plan-review/plan-after-chat/docs-review grounders are external-web-research-shaped — recorded as a standing observation (below), not silently passed |
| freeze-law family | CLEAN | flows/ui-design + review twins consistent post-T15/T16/T29/T30; data-contract legitimately twin-less (verifier-confirmed) |
| pass-introduced cross-references | CLEAN | T18→spec-review §After-CONVERGED (:263), T31→property 2, T33→09-revise-requirements — all resolve |
| regression sweep (hunks ± context) | CLEAN | @{u} fix consistent in both files; post-commit sync claim consistent with CLAUDE.md; flip-back mint split (deploy-plan-review no-row vs flows/ui-design-review row) resolves as mechanical-truth-restoration vs reviewer-judgment — noted below |
| fail-open/fail-closed (standing class) | CLEAN | the pass's own subject: every termination fix (D-048 family) converts an unreachable/fail-open exit into a closed checkable one; the fanout=None fail-mode (T17), the !!-void rule verified (T24), the blocked-close loudness (T16/T30) — all fail-closed; no gate/guard in the diff fails open |
| cost/quota accounting (standing class) | CLEAN | the no-ceiling ruling RECORDED not assumed (D-050); truncated=True stays a LOUD finding; the release cut refuses hollow versions; no unknown≠0 conflation introduced by the diff |
| boundary/sentinel/prefix (standing class) | FIXED(in-pass) | the PRIMARY-PATH marker-counting law verified intact (T15/T16); anchor-drift — the pass's dominant residue class — corrected in every artifact by per-ticket re-derivation; the phantom-line citations (T20/T28) caught and killed |
| behavior-without-a-test (standing class) | CLEAN | the one code change (assemble_commands.py agents_dest, 414d176d) shipped red-first with 2 regression tests; the corpus diff is otherwise prose contracts with no runtime behavior — the graders (QUIET_PASS, check_review_coverage, check_frozen_chain) are the standing tests and all verified live against the new text |

## Pass Ledger (the whole-plan review)

| Pass | finders | found | new | fixed | method | verdict |
|---|---|---|---|---|---|---|
| Pass 1 | native whole-plan verifier — 6 classes over the full cumulative diff (×2 reads + 24-file mint grep + corpus-wide D-048 grep) | 6 | 6 | 2 | independent adversarial sweep | not done (changed code — the two back-flip fixes) |
| Pass 2 | orchestrator closing sweep — both back-flip fixes re-read in place, all 10 checklist classes re-swept, every count/enumeration/anchor in this receipt re-derived from its primary source (commit list from git log, 34/34 INDEX rows counted on disk, QUIET_PASS regex re-read at check_convergence.py:150, both back-flip hunks re-opened) | 0 | 0 | 0 | method: re-derivation | → EXIT (found: 0, fixed: 0) |

Round ledger in the run record (command_run) mirrors these rows; the standing observations below are CITED, not counted (D-048).

## Standing observations (recorded, routed — none blocking)

1. **Lower-risk carve-out asymmetry** (flows-review/plan-review/plan-after-chat/docs-review grounders): predominantly external-web research units; the one named vector (plan-after-chat ticket-grounding of secrets-adjacent compose text) is bounded by never-route Touches. Routed: fold into the next corpus maintenance pass; not fixed at integration per the T34 DO-NOT.
2. **fabrik-catchup's mint clause** omits the inline classify-at-mint restatement its ~12 siblings carry — not a contradiction (CLAUDE.md binds); style-harmonization candidate.
3. **Flip-back mint split** (deploy-plan-review: no row; flows/ui-design-review: row) — resolves on reading (mechanical truth-restoration vs reviewer judgment) but is under-cross-referenced; a one-line disambiguation is a maintenance candidate.
4. **fabrik_synced_manifest.py:331 docstring** still says SEEDED_NOT_ENFORCED is singular — out of plan File Scope (scripts/); post-plan one-liner.
5. **T33's unresolved angle**: a check_convergence Coverage-Checklist collision IF a converged workflow artifact ever lands under docs/development/plans/ with a convergence-claiming Status — persistence path speculative; watch item.
6. **The e85c6c93 WARN** (T04 touching T01's Touches) — the sanctioned orchestrator-applied fragment fix, recorded in T04's artifact; no action.

## Gate + render proofs (this commit's turn)

- `python scripts/final_gate.py --check --json` → `"status":"success"` after this receipt exists (the two pre-receipt failures were INDEX.md rows pointing at this file — self-clearing; re-run verbatim in the T34 merge turn, see spine Evidence).
- `python scripts/enforcement/check_convergence.py` → exit 0.
- `python scripts/enforcement/check_doc_sync.py --range 0ddfbb96..HEAD` → the 33-artifact INDEX WARN clears with this commit's INDEX.md rows (34 added).
- `python commands/assemble_commands.py --check` → "check OK — installed commands + skills match rendered sources" (re-run post-back-flip render in the merge turn).
- /fabrik-docs-review REPORT-mode over the two out-of-scope reference docs: `docs/reference/command-evaluation-checklist.md` + `docs/reference/operating-manifesto.md` were read as the yardstick on every ticket; no drift findings surfaced against either across 33 verifier rounds — both remain truthful as written. No edits owed.
