# Whole-plan validation review — 2026-09-06-plan-2-multi-agent-adoption

**Status:** CONVERGED
**Surface:** `git rev-parse HEAD` = 481c355d04f6170a700654ef5f21a25bb492b754; the cumulative diff `231757fb..HEAD` over the plan's ten code/command/doc paths md5 08ad29a2cec81570b8613aca0d33ed87 (+880/−41 over 10 files at e81de2cb, +31/−38 more in the doc at aedcf64c)
**Plan:** `docs/development/plans/2026-09-06-plan-2-multi-agent-adoption/` (spine + 7 tickets; spec `docs/superpowers/specs/2026-09-06-multi-agent-adoption-design.md`, approved D-155; ruling D-154). Owner: infra. Executed in DISPATCHER mode in the hub's main checkout; coders isolated in Agent worktrees; every merge a private-index squash commit of explicitly named paths.

## Merge ledger

| Ticket | Coder | Review rounds (findings) | Merge commit | Synced |
|---|---|---|---|---|
| T01 | pool ×2 dead/blind → native Sonnet fixup | 2 (2 → 0) | a6ac4cec | — |
| T04 | native Sonnet | 2 (3 → 0) | 7b72b5b6 | hook → 45 projects |
| T02a | pool dead → native Sonnet (NO-POOL) | 3 (9 → 2 → 0) | c2631de2 | script → 45 projects |
| T05 | native Sonnet | 2 (3 → 0 + 1 merge-time text nit) | 21ab52db | corpus rendered |
| T02b | native Sonnet; the first coder died on a 429 mid-round-2, its edits salvaged to a fresh coder | 3 (6 → 2 → 0) | ac72db17 | script → 45 projects |
| T03 | native Sonnet (never-route) | 2 (6 → 0; row 4 re-cut on the spine) | 5cd2ff55 | script + gate → 45 projects |
| T06 | native Sonnet (code half) + the orchestrator (receipt) | 2 (3 → 0) + the D7 doc-cap fix aedcf64c | e81de2cb | template → 45 projects |

Out-of-Merge-Order merges, each stated in its commit body: T04 and T05 merged before T02a/T02b/T03 (no Depends edge; T05 held until T02a so its text never named an unmerged flag).

## Phase verdicts (D1–D7)

- **D1** — lock acquired (15 owned paths = File Scope minus the stem metadata), baseline 231757fb with a green `--check` gate, the IN-PROGRESS flip at ca4ec9ed. PASS.
- **D2** — dispatcher contract: the `.claude/settings.json` permission floor confirmed before the first dispatch; pool-default attempted for T01/T02a (three units: two dead, one blind — the write sandbox cannot run pytest, filed 01M1V98VN3QNS73GCR3GYF9FXH), NO-POOL declared per re-dispatched ticket; never-route T03 native; concurrency ≤3 coders; fixups routed to the SAME coder via SendMessage (context intact) in 5 of 6 rounds, a fresh coder once (T02b, dead session). PASS with the pool finding.
- **D3** — Deltas orchestrator-applied at every merge: one CHANGELOG entry per ticket, INDEX rows for the two new test files, the merge-time text fixup on T05 (≤2 lines, no logic), LESSONS + two STRATEGIC_BACKLOG rows at T06. PASS.
- **D4** — every ticket converged to a coverage-adjudicated exit before merge: pool trio + native Opus per round (21 review rounds; 63 pool units scored 0–4 via `set_quality`; 8 native Opus seats, one stalled and stopped with the orchestrator's executed re-measurement as the closing layer). Artifacts: `2026-09-06-plan-2-multi-agent-adoption-T0{1,2a,2b,3,4,5}-review.md`, each with the rubric invocation, the standing classes, a Pass Ledger with `method: re-derivation`. PASS.
- **D5** — squash merges in one commit each (code + Board flip + applied Deltas + the lock + the review), pushed, forced sync after every synced-surface merge (45 of 45, 0 failed ×4), corpus render from the main checkout for T05. PASS.
- **D6** — lock registry per ticket; one dead coder salvaged (`-salvage-T02b.diff`, 82 lines, applied cleanly by the fresh coder); sizing signals logged in the spine Evidence. PASS.
- **D7** — this receipt; the validation layer below.

## Integration receipts (T06)

### Cross-ticket seam run (the six suites on the merged tree at 5cd2ff55)
```text
$ .venv/bin/python -m pytest tests/test_decisions_helper.py tests/test_docs_updater_adopt.py tests/test_docs_updater.py tests/test_session_orient_hook.py tests/test_vision_reads_work_stores.py tests/test_scaffold_doc_seeding.py -q
193 passed in 3.95s
```

### Fleet fire-rate proof (spec V4) — read-only over the 45 sync targets, merged `docs_updater.py`
| repo | live sessions | merge owner | unowned open plans | untagged backlog rows | would-fire |
|---|---|---|---|---|---|
| ai-model-catalog | 0 | UNDECLARED | 0 | 6 | no |
| apidoccreator | 0 | UNDECLARED | 3 | 34 | no |
| brand-identiy-creator | 0 | UNDECLARED | 2 | 82 | no |
| calendar-orchestration-engine | 0 | UNDECLARED | 1 | 47 | no |
| candle | 0 | UNDECLARED | 1 | - | no |
| compliance-ops | 0 | UNDECLARED | 0 | 6 | no |
| emailgateway | - | not a git repo | - | - | no |
| email-reader | 0 | UNDECLARED | 1 | - | no |
| exam-coach | 0 | UNDECLARED | 0 | 6 | no |
| fabrik-citation-verifier | 0 | UNDECLARED | 0 | - | no |
| fabrik-claim-validator | 0 | UNDECLARED | 0 | 10 | no |
| fabrik-dr-store | 0 | UNDECLARED | 0 | - | no |
| gmail-account-creator | 0 | UNDECLARED | 0 | - | no |
| image-generation | 0 | UNDECLARED | 1 | - | no |
| iterative_image_editor | 3 | UNDECLARED | 0 | 148 | YES |
| job-agent | 0 | UNDECLARED | 7 | 23 | no |
| llm_batch_processor | 0 | UNDECLARED | 1 | - | no |
| logo-export | - | not a git repo | - | - | no |
| longephedia-vault | 0 | UNDECLARED | 0 | 6 | no |
| marketing-argumant-generator | 0 | UNDECLARED | 1 | - | no |
| meb | 0 | UNDECLARED | 0 | - | no |
| obsidian-agents | 0 | UNDECLARED | 1 | 6 | no |
| proposal-creator | 0 | UNDECLARED | 1 | - | no |
| proxy | 0 | UNDECLARED | 1 | - | no |
| Reference_Creator | 0 | UNDECLARED | 1 | - | no |
| rnfinal | 0 | UNDECLARED | 0 | - | no |
| rn-kit-sandbox | 0 | UNDECLARED | 0 | - | no |
| scratch_bhd | - | not a git repo | - | - | no |
| seo | 0 | UNDECLARED | 1 | 18 | no |
| session-recall | 0 | UNDECLARED | 0 | 0 | no |
| site-provisioner | 0 | UNDECLARED | 9 | 32 | no |
| supplement-tracker-advisor | 0 | UNDECLARED | 0 | - | no |
| test-saas-for-epic-wf | - | not a git repo | - | - | no |
| test-saas-platform | 0 | UNDECLARED | 0 | 6 | no |
| test-saas-scaffold | 0 | UNDECLARED | 0 | 6 | no |
| tojlo-mail | 0 | UNDECLARED | 4 | 6 | no |
| trade-intelligence | 0 | UNDECLARED | 4 | 213 | no |
| trading-core | 0 | UNDECLARED | 2 | - | no |
| transdoc | 0 | UNDECLARED | 2 | 25 | no |
| triggered-content-orchestration | 0 | UNDECLARED | 2 | - | no |
| tryton-crm | 0 | UNDECLARED | 1 | 55 | no |
| web-ecommerce-factory | 3 | UNDECLARED | 3 | 170 | YES |
| web-scraper | 0 | UNDECLARED | 3 | - | no |
| whatsapp-agent | 0 | UNDECLARED | 0 | 6 | no |
| youtube | 2 | UNDECLARED | 7 | 308 | YES |

Denominator: 45 sync targets (41 git repos); would-fire: 3; would-fire with <2 sessions (must be 0): 0

Reading: the advisory would fire in every repo with ≥2 live sessions and incomplete ownership and in NO single-session repo (the last line's zero is the contract). The hub is excluded by identity. The numbers are a snapshot of live sessions at the moment of the run (8 shared checkouts in the morning measurement, 3 at this run).

### Doc receipts
```text
$ python3 scripts/enforcement/check_doc_sync.py --range 231757fb..HEAD   → rc 0
$ python3 scripts/enforcement/check_doc_stubs.py --range 231757fb..HEAD  → rc 0
```

### Cross-ticket seam run at HEAD after T06 (seven suites)
```text
1 failed, 204 passed in 4.84s
```
The one red at e81de2cb — `tests/test_docs_updater.py::TestMultiAgentOperatingModelDoc::test_doc_exists_and_names_the_planned_surfaces` (a pre-existing ≤150-line guard; T06's rewrite reached 157) — was fixed by the orchestrator's text trim (aedcf64c, `Agent-Task: T06`, no rule dropped); 41 passed across the two guarding suites after it.

### Docs-review (nested `/fabrik-docs-review`, NO-POOL) — the claim → proof table, executed against master
| MERGE_OWNER_RE identical in decisions.py and docs_updater.py | PASS | ^\**\s*MERGE OWNER:\s*([A-Za-z0-9][A-Za-z0-9_.@-]*) == ^\**\s*MERGE OWNER:\s*([A-Za-z0-9][A-Za-z0-9_.@-]*) |
| --adopt name grammar ^[a-z0-9-]{1,32}$ | PASS | grep _ADOPT_NAME_RE |
| --adopt refuses below 2 sessions unless --single-window | PASS | grep --single-window / count_sessions_sharing |
| scaffold seeds the same Ownership block as run_adopt | PASS | grep in both files |
| PLANS header comment '<!-- Merge owner: … | source: D-NNN -->' | PASS | grep docs_updater |
| hub PLANS.md block header has no 'tail sweep' | PASS | grep docs/development/PLANS.md |
| validate_ownership_advisory guards count + hub only | PASS | read the function body |
| hook _sessions_line guards count + hub + worktree | PASS | read the function body |
| doc states the split suppressions exactly | PASS | grep doc |
| epic_order.py hub-only (0 project copies) | PASS | 0 project copies |
| doc says epic_order.py hub-only | PASS | grep doc |
| operating-model doc ≤150 lines, no 'tail sweep' | PASS | 150 lines |
| template § Orient (d) names --adopt once | PASS | count=1 |
| hooks-index session_orient row names the advisory | PASS | grep hooks-index |
| INDEX row for tests/test_docs_updater_adopt.py and file exists | PASS | grep INDEX + is_file |
| INDEX row for tests/test_vision_reads_work_stores.py and file exists | PASS | grep INDEX + is_file |
| CHANGELOG entry present: decisions.py --merge-owner | PASS | grep CHANGELOG |
| CHANGELOG entry present: docs_updater.py --adopt: PLANS markers | PASS | grep CHANGELOG |
| CHANGELOG entry present: tags the backlog rows in their three real sha | PASS | grep CHANGELOG |
| CHANGELOG entry present: --check advises when | PASS | grep CHANGELOG |
| CHANGELOG entry present: session_orient advises | PASS | grep CHANGELOG |
| CHANGELOG entry present: fabrik-vision EXISTING reads PLANS.md | PASS | grep CHANGELOG |
| CHANGELOG entry present: new repos are born with the PLANS markers | PASS | grep CHANGELOG |
| ledger row D-153 | PASS | count==1 |
| ledger row D-154 | PASS | count==1 |
| ledger row D-155 | PASS | count==1 |
| rendered fabrik-vision names PLANS.md + STRATEGIC_BACKLOG.md | PASS | grep rendered |
| rendered fabrik-epics-review names --merge-owner mint | PASS | grep rendered |
| LESSONS entry present | PASS | grep |
| two backlog rows present | PASS | grep |
| spine Board: 7 rows ✅ | PASS | 7 of 7 |

claims: 31; FAIL: 0

Pass 2 (the doc-level gates):
```text
- Broken link in docs/workflows/development-and-deployment-workflow.md: [docs/traycer/traycer-managed-development-workflow-epic/](../traycer/traycer-managed-development-workflow-epic/)
  - Stale doc (96 days old): docs/TROUBLESHOOTING.md

Run 'python scripts/docs_updater.py --sync' to fix.
check_doc_index: OK — INDEX.md and the live docs tree agree
check_doc_links: OK — 0 broken of 2432 refs across 222 docs
```
The two residual `docs_updater --check` lines are pre-existing and outside this plan (a broken link in `docs/workflows/development-and-deployment-workflow.md`, a 96-day-old TROUBLESHOOTING.md).

## D7 — whole-plan validation

**Finders:** pool ×3 (batch 1: A–C CLEAN; two units dead → re-dispatched: D–F CLEAN with one refuted M, G–J CLEAN with two claims refuted by the receipts above) + a confirming pool unit (no adjudicable output — could not locate the plan dir; scored 1) + the native authoritative seat = the orchestrator (Fable substitutes for Opus here), EXECUTED:

```text
(E) docs_updater.count_sessions_sharing: 3
(E) hook _sessions_line count: 3 | line printed: True
(B/D) advisory BEFORE adopt: ['ADVISORY: 3 sessions share this checkout and ownership is incomplete (merge owner undeclared; 1 unowned plans; 2 untagged backlog rows) — run: python scripts/docs_updater.py --adopt <name>[,<name>…]']
(D) adopt rc 0 | backlog-row lines: 2 | owner-line: 1 | ledger-row: 1 | markers: 1
(B/D) advisory AFTER adopt: []
Traceback (most recent call last):
  File "<stdin>", line 25, in <module>
TypeError: _count_untagged_backlog_rows() missing 1 required positional argument: 'text'
(A) docs_updater.read_merge_owner: ('beta', 'D-004')
(A) decisions --merge-owner: beta rc 0
(C) adopt with a declared owner: rc 0 | ledger-row lines: 0
(C) decisions --check rc 0 
(C) written row cells: 6 | id: D-002 | both readers: ('gamma', 'D-002') gamma
(C) decisions --check on the written row: rc 0
(J) route/endpoint tokens in the cumulative diff: 0
```
(A) both readers agree — `beta` from an earlier-alpha / later-**beta** / short-row / escaped-pipe ledger; (B/D) the advisory fires with all three limbs before `--adopt` and is silent after it, `--adopt` with a declared owner writes no second row, the written row has 6 cells and passes `decisions.py --check`, both readers read it back; (E) the hook's scan and the script's scan count 3 on the same fake tree (claude ×3, claude-foo, bash, a dangling cwd); (F) 114 test functions across the four new/extended suites map the spec's V1–V7 (+V1b); (G) the corpus `--check` clean, the rendered vision names the two stores 4×, the epics-review names the mint 3×; (H) 45 of 45 project copies carry `run_adopt`, `_sessions_line`, and the template's `--adopt` sentence; (I) the regenerated hub PLANS header carries no "tail sweep"; (J) 0 route/endpoint/client tokens in the cumulative diff — no HTTP surface, no live request owed.

**Round 1:** found 1 (the doc over its line guard) → fixed at aedcf64c. **Round 2 (confirming):** the seam suites 41 passed on the guarding pair, the gate green below, the docs-review 31 claims 0 FAIL, the pool confirming unit non-adjudicable and the native seat's re-read of the trimmed doc clean → **found: 0, fixed: 0**.

### Whole-plan gate (read-only, at HEAD after the D7 fix)
```text
$ python scripts/final_gate.py --check --json
{"status": "success", "skipped_checks": ["pytest"], "failures": []}
```
(`pytest` is the hub's standing skip — the plan's own suites were run above.) `check_plan_tickets --plan-dir`: the two READ-budget ERRORs are the logged sizing signals (docs_updater.py grew 59 → 85 KB through the plan's own tickets); `check_convergence` runs at the EXECUTED flip.

## Coverage Checklist

Rubric invocation (verbatim head of the output):

```text
$ python scripts/review_rubric.py --changed scripts/docs_updater.py scripts/decisions.py scripts/final_gate.py .claude/hooks/session_orient.py src/fabrik/scaffold.py commands/_sources/fabrik-vision.md
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
```

| Class | Status |
|---|---|
| core/10-python.md — stdlib only, `datetime.now(UTC)`, no logfile writes, ruff | CLEAN — every merged script/hook/test ruff-clean; `utcnow` absent; the one format wrap (final_gate.py) required by `line-length = 100` |
| core/40-documentation.md — trailers, one CHANGELOG entry per ticket, docs as rules | CLEAN — 7 CHANGELOG entries; every merge commit's `Agent-Task` trailer parsed (the untrailered quota-hold checkpoint 00807525 is named here); the operating-model doc present-tense |
| FLOOR 35/25/30 · 12-FACTOR | CLEAN — no service, no DB, no auth; XI stdout only; the `/proc` scans read `comm` + `cwd`, never `environ` |
| Recurrence: Behavior Contract row without a killing test | CLEAN — 63 mutation probes across the per-ticket rounds, every survivor fixed before merge (T02a 5, T02b 2+1, T03 4, T04 3, T01 1) |
| Recurrence: Touches discipline / governance / spine / lock | CLEAN — every merge's `--name-only` = the ticket's Touches; governance via Deltas; the spine/lock orchestrator-only |
| Recurrence: fleet blast radius of the synced surfaces | CLEAN — one-session repos byte-identical in `--check`, `--sync` and the hook (three native differentials); the fire-rate proof: 0 single-session fires of 45 targets; five forced syncs 45/45 |
| Recurrence: proxy-as-evidence | CLEAN — every claim above is an executed command with its output; the worktree-venv shadowing trap found and recorded |
| Recurrence: denominator on every count | CLEAN — 7 of 7 tickets, 21 rounds, 63 pool units scored of 63, 45 of 45 synced, 1318 → 1303 of 8,637 backlog lines, 205 tests of 205 collected |
| Recurrence: fail-open/fail-closed | CLEAN — the `--adopt` refusal (exit 2) and the name grammar are fail-closed; the advisories are advisory by construction; a refused delegation exits 3 |
| Recurrence: cost/quota accounting | CLEAN — pool 63 units scored via `set_quality`; native Opus 8 seats + 1 stopped; 4 coder re-dispatches logged; one quota hold survived by the checkpoint protocol |
| Recurrence: boundary/sentinel/prefix | CLEAN — the `< 2` boundary, the exact-`comm` match, the tag POSITION, the terminal-status set, the name grammar all pinned by tests after the rounds |
| Recurrence: behavior-without-a-test | CLEAN — see the mutation row; the spec's V1–V7 mapped to merged tests (F) |

## Pass Ledger
| Pass | Layer | Method | Findings → fixed |
|---|---|---|---|
| Pass 1 | pool ×3 (+2 re-dispatched) + native (orchestrator, executed) | method: re-derivation (seams A–J executed on fixtures; the seam suites and the gate re-run at HEAD; the fleet re-counted) | 1 → 1 |
| Pass 2 | pool ×1 (non-adjudicable) + native (orchestrator) + the nested docs-review's 31 executed claims | method: re-derivation (the trimmed doc re-verified line by line against the code; the gate re-run; the Board re-read: 7 of 7 ✅ with commits on master) | 0 → 0 |

## Deltas applied at the merges (orchestrator)
CHANGELOG: 7 entries · INDEX: 2 rows · LESSONS_LEARNT: the 2026-09-06 adoption entry (3 shapes) · STRATEGIC_BACKLOG: 2 `[infra]` rows · DECISIONS: none minted during execution (D-153/D-154/D-155 predate it) · the hub `docs/development/PLANS.md` block regenerated (`--sync`) at the T06 merge.

## Machinery report (the run's own numbers)
7 tickets · 21 per-ticket review rounds · 63 pool units scored (dead/blind: 5 code units, 4 review units) · 8 native Opus finder seats (+1 stalled, stopped) · 4 native coders re-used for 6 fixup rounds via SendMessage (context intact) · 1 dead coder salvaged · 1 fleet quota hold survived (checkpoint 00807525, resume on relief) · 5 forced syncs 45/45 · 1 corpus render · wall-clock ≈ 7 h from D1 (ca4ec9ed) to this receipt.
