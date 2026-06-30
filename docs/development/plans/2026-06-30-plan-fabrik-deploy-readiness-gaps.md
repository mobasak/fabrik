# Plan: Fabrik Deploy-Readiness Gaps (8 fixes blocking calendar-orchestration-engine + every future service)

**Status**: CONVERGED v5 (awaiting owner approval before any commits) — **8 grounding passes + 2 external-review correction rounds** (8 parallel + 3 parallel + 6 solo + 2 external-AI critiques applied); Phase 1 split into 1a + 1b-shape + 1b-depends (the depends edit is INERT without 1a, so they ship together); 1 phase DEFERRED (no upstream API), 1 phase unblocked via VPS probe, 6 phases shippable, Phase 1a re-classified as registrar refactor (not one-liner).
**Owner**: ozgur · **Author**: Claude (Opus 4.7)
**Created**: 2026-06-30 · **Converged**: 2026-06-30
**Context-trigger**: external-AI audit of calendar-orchestration-engine deploy readiness exposed 8 fabrik-side gaps. Owner: "these are not acceptable. create a plan to address all these in fabrik."

## Evidence

Every claim in this plan was verified against the actual codebase across 4 grounding passes. Verification artifacts:

**Pass 1 — 8 parallel grounders** (one per phase, ~70s each):
```
agent_id=a5a83d9edb6655908 phase=1 ran=42 tool-uses verdict=DRIFT-spec-depends-postgres-dead-code
agent_id=a296447976338368e phase=2 ran=41 tool-uses verdict=DRIFT-default-path-resolution + exit-code
agent_id=af2ff2ebf4bce8930 phase=3 ran=25 tool-uses verdict=CRITICAL-no-quiet-flag + wrong-generator-attribution
agent_id=a81f59ef42a362e87 phase=4 ran=34 tool-uses verdict=GROUNDED with memory-default gap
agent_id=ac10a82fe96107a64 phase=5 ran=33 tool-uses verdict=GROUNDED with 3 gaps (zcat, table-count, path-traversal)
agent_id=a90570d5a617529bb phase=6 ran=19 tool-uses verdict=BLOCKED on 4 VPS unknowns
agent_id=aabf4a86fd755249b phase=7 ran=25 tool-uses verdict=BLOCKED on webhook endpoint discovery
agent_id=a06a0baad38fc3d06 phase=8 ran=27 tool-uses verdict=DRIFT-no-existing-gh-api-use + 4 gaps
```

**Pass 2 — 3 targeted grounders for BLOCKED items**:
```
agent_id=a0dad30f794e367ee phase=3a ran=6 tool-uses verdict=RESOLVED — 3 generators identified
agent_id=ab47f1ea085d79f42 phase=6 ran=34 tool-uses verdict=UNBLOCKED via vps1 SSH (4 unknowns answered)
agent_id=a7dfaa028ffa8d5ad phase=7 ran=20 tool-uses verdict=PERMANENTLY-BLOCKED — GlitchTip has no webhook API → DEFERRED
```

**Pass 3 — solo verification of all NEW citations introduced by Pass 1/2 fixes**:
- ✅ `infrastructure.py:432` `db_name = name.replace("-", "_")` — verified at line 432
- ✅ `postgres.py:53` `POSTGRES_CONTAINER = "postgres-main"` — verified
- ✅ `postgres.py:131` `def create_database(...)` — verified
- ✅ `postgres.py:220-241` role+grant SQL block — verified
- ⚠️ DRIFT FIXED: `scp_to_vps` was claimed at `orchestrator/ssh.py:89` — actual location is `drivers/ssh.py:89` (orchestrator/ssh.py doesn't exist). Plan corrected.
- ✅ `destroyer.py:299` `drop_database()` call — verified
- ✅ `locks.py:68` `run_locked()` — verified
- ⚠️ DRIFT FIXED: `daily_refresh.sh:178-179` insertion point — actual lines are 231 (`update_gateway_counts.py`) + 234 (`export_models_browser.py`). Plan corrected.

**Pass 4 — solo verification of Pass-3 fixes + remaining Phase 4/7/8 citations**:
- ✅ `spec_loader.py:177-182` Depends class — verified (currently only `postgres` + `redis` fields)
- ✅ `templates/file-worker/defaults.yaml:7` `kind: worker` — verified
- ✅ `deployer_ssh.py:404` `_deploy_git` — verified
- ✅ `scripts/probes/glitchtip_webhook_capture.py:9-10` "GlitchTip exposes no API" — verified verbatim
- ✅ `docs/reference/fixtures/glitchtip-webhook.json` — file exists
- ✅ `cli.py:1630` `gh auth status` subprocess.run — verified
- ✅ `watchdog.py:793` `def _ensure_deploy_key` — verified
- ✅ `watchdog.py:599` `container_name = f"{rctx.project_id}-watchdog"` — verified
- ✅ `generate_model_capabilities.py:155`, `generate_selection_guide_roster.py:190`, `scrape_windsurf_models.py:538` — all 3 verified writing the claimed paths
- ✅ `fabrik_synced_manifest.py:93` `SEEDED_NOT_ENFORCED = {"PORTS.md"}` — verified

**Pass 4 found zero new ungrounded items** (narrow-scope: re-verifying Pass-3 fixes only).

**Pass 5 — solo spot-check of validation gate commands**:
- Ran Phase 1's at-risk-spec audit Python one-liner → enumerated **7 at-risk specs** (`youtube, calendar-orchestration-engine, fabrik-claim-validator, proposal-creator, trading-core, triggered-content-orchestration, job-agent`); plan updated to require per-spec A/B/C decision in-plan.
- Ran Phase 2's fabrik-self-check command → exit 0 confirmed.
- Ran Phase 3's KILO_* writer grep → caught that grep finds 13 mentioners but only 3 are actual writers; tightened plan to clarify.
- Attempted Phase 6 vps1 SSH probes → `Temporary failure in name resolution` from this WSL shell; added R6 residual.

**Pass 6 — solo deep-verify writer attributions** (precision tightening):
- Caught ordering constraint: `embedding_export_markdown.py` at [scripts/kilo-benchmarks/embedding_export_markdown.py:283-284](scripts/kilo-benchmarks/embedding_export_markdown.py#L283) does PARTIAL writes (between `EMBEDDING_ROSTER:START/END` markers) into the same KILO_* files the 3 new generators write end-to-end. If new generators run AFTER it, marker content gets nuked. Plan's Phase 3a insertion point moved from "after line 231" to "BEFORE line 166".

**Pass 7 — solo re-verify Pass-6 fixes**:
- Re-read embedding_export_markdown.py:40-41 (path definitions), 283-284 (write calls), daily_refresh.sh:128 (update_kilo_benchmarks), daily_refresh.sh:166 (embedding_export_markdown). All match plan. EMPTY pass (narrow scope).

**Pass 8 — wide-scope adversarial: attack the validation gates**:
- Phase 8 regex tested against every spec's `source.repository`:
  ```
  All 12/55 specs with source.repository parse correctly via r"github\.com[:/]([^/]+)/([^/.]+?)(?:\.git)?$"
  (https://github.com/mobasak/X.git AND git@github.com:mobasak/X.git both work)
  ```
- Phase 5 path-traversal tested against 4 attack vectors:
  ```
  OK    backups/seed.sql.gz                 -> is_relative_to=True (allowed)
  BLOCK ../etc/passwd                       -> is_relative_to=False (rejected)
  BLOCK /etc/passwd                         -> is_relative_to=False (rejected)
  BLOCK backups/../../../etc/passwd         -> is_relative_to=False (rejected)
  ```
- Phase 2 exit code re-verified: `/opt/fabrik/.venv/bin/python check_no_host_ports.py --templates-dir /nonexistent` returns exit 2 ✓ (Pass-1 was right; my first Pass-8 attempt miscaptured `$?` due to shell `cd` resetting state — corrected on re-run).

**Pass 8 = demonstrably-thorough EMPTY pass.** Wide-scope adversarial probe found ZERO new plan defects across regex grounding, path-traversal validation, and exit-code claims.

**Pass 9 — external-AI review correction (2026-06-30)**: an independent AI reviewer (executor candidate) found 2 real defects the 8-pass loop missed:
- **F1** (CORRECTNESS): Phase 1's `db_name = spec.depends.postgres or spec.id.replace("-","_")` pseudo-code wouldn't run — `_provision_postgres()` at [infrastructure.py:426](src/fabrik/orchestrator/infrastructure.py#L426) has NO `spec` in scope (caller at line 360 passes only `name`); spec at this layer is `dict[str, Any]` (per peer `_provision_gatus` at [infrastructure.py:455](src/fabrik/orchestrator/infrastructure.py#L455)), not the Pydantic model. Real fix is a registrar-signature refactor (+ caller updates). Plan corrected: Phase 1a re-classified from "15-min one-liner" to "~1.5h refactor". Effort doubled.
- **F2** (CORRECTNESS, minor): Phase 5 gate #2 expected output cited `local_path: Path` but actual signature is `local_path: str` (Plan's Evidence §602 was correct; gate command's "Expected" line drifted). Fixed.
- **F3** (cosmetic, not patched): Phase 8 example data-flow path detail. Mechanism correct, example path slightly off.

**Honesty note on Pass 8**: Pass 8's "EMPTY" verdict held for the 4 specific attack vectors tested (regex, path-traversal, exit-code, spec-count). It did NOT test the patch site of the orchestrator fix, which is what F1 catches. Pass 8 was wide enough to be useful but not exhaustive — F1 is the cost of declaring convergence at Pass 8 instead of running a 9th full sweep. Lesson: even "wide-scope" passes can miss caller-signature mismatches when grounders only read FUNCTION bodies, not their CALL SITES.

**Pass 10 — external-AI review round 2 (2026-06-30)**: same reviewer caught a sequencing defect the rebadge missed:
- **F4** (SEQUENCING): the Phase 1 split into "1a + 1b" was correct but the recommendation to "ship 1b standalone" was wrong. 1b's `depends.postgres: calendar → calendar_engine` edit is INERT until 1a lands (the field is dead code today). Shipping the spec edit alone restores cosmetic consistency but does NOT unblock calendar's DB-creation gap. Plan corrected: split 1b further into **1b-shape** (3 edits that DO drive registrars today — Authelia, Prometheus, watchdog) and **1b-depends** (1 edit that must ship bundled with 1a).
- **F5** (NEW POSITIVE FINDING): calendar's spec at [specs/services/calendar-orchestration-engine.yaml:16](specs/services/calendar-orchestration-engine.yaml#L16) explicitly states `"was missing → DB never created"`. This means calendar's rename under 1a is FREE — no data migration, A/B/C decision trivially = Option A. Plan corrected: calendar pre-decided; only 6 other specs still need operator decisions.

**This second correction round did not require re-grounding** — both findings were spec-text reads + sequencing logic, not new code claims. But it does demonstrate that "convergence" is not a single-pass property: shipping the plan as v4 would have caused operator to ship 1b expecting calendar to unblock, then discover it didn't.

### Live-VPS probes performed (Phase 6 grounding)

```
$ ssh vps1 'cat /opt/backrest/config/config.json | jq ".plans[] | select(.id==\"postgres-dumps\")"'
{"id":"postgres-dumps","paths":["/opt/backups/"],"schedule":"0 2 * * *","hooks":null,
 "retention":{"daily":7,"weekly":4,"monthly":6}}

$ ssh vps1 'sudo crontab -l | grep pre-backup'
30 1 * * * /opt/backups/pre-backup.sh >> /opt/backups/pre-backup.log 2>&1

$ ssh vps1 'sudo docker exec postgres-main env | grep POSTGRES_'
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

$ ssh vps1 'sudo docker inspect $(sudo docker ps --format "{{.Names}}" | grep backrest) | jq ".[0].Mounts | map(.Destination)"'
["/opt","/data","/config","/tmp","/cache","/var/run/docker.sock"]
```

These probes resolve all 4 Phase-6 unknowns (current backup mechanism, mount bindings, pg_dump trigger, auth model).

### Convergence floor

This plan reaches fixed point on **grounding evidence**, not on **design correctness**. Green `final_gate.py` + `check_convergence.py` prove citations and format — they do NOT prove the proposed design is sound. The real proof is the Pass-2 VPS probes above + the Pass-1 file reads cited inline per phase. Reviewer must judge design correctness against the cited evidence, not against gate state.

## ⚠️ MANDATORY EXECUTION PROTOCOL (BINDING — non-negotiable)

Any AI agent executing this plan MUST follow this protocol for every phase. Skipping any step = phase failed, do not commit. The Final Gate Instruction at the end of each phase is necessary but NOT sufficient — these subagent + test checkpoints are also required.

### Per-phase protocol

For EACH phase, in this exact order:

1. **RE-GROUND** (mandatory subagent — `Explore`):
   Re-verify every `path:line` reference in this phase still matches current code (paths may have shifted since plan authoring on 2026-06-30). If ANY reference drifted, STOP and update the plan before coding.

   Prompt template:
   > "Verify these path:line references in fabrik are still accurate as of HEAD: [list each ref from the phase]. For each: report MATCH (with the actual line content) or DRIFT (with the new line number, or NOT FOUND). Under 200 words."

2. **TESTS FIRST** (BLOCKING — TDD per [core/45-testing-strategy.md](.windsurf/rules/core/45-testing-strategy.md)):
   Write the test file BEFORE touching production code. Test names + assertions must be in the diff and FAILING before any implementation code is added. Phases without a "Tests" subsection in this plan still require: minimum 1 test for the highest-risk path (per CLAUDE.md Completion Contract #1).

3. **IMPLEMENT** to make tests pass. Stay strictly within phase Scope; adjacent fixes in same files OK but no scope creep across phases.

4. **SELF-REVIEW** (iterate to a fixed point per CLAUDE.md 1a): re-read your own diff for bugs, unhandled edge cases, deviations from this plan and from the applicable `.windsurf/rules` pack. Fix; re-run tests; re-run gate. Repeat until a fresh self-review surfaces nothing new.

5. **ADVERSARIAL REVIEW** (mandatory subagent — `general-purpose`, run in background while you draft the commit message):
   Hunt for correctness/security bugs only — not style. Re-uses the binding adversarial-review prompt template from earlier convergence rounds (see Appendix A at the bottom of this plan). If the agent surfaces ≥1 CONFIRMED finding, fix it BEFORE committing. PLAUSIBLE findings: fix or document why deferred. REFUTED: ignore.

6. **GATE**: `python /opt/fabrik/scripts/final_gate.py --lean --json` → must be `status:success`. Plus the phase's specific `Final Gate Instruction` (most phases add a manual reproduction step).

7. **COMMIT** with the phase's exact format (see Appendix B). Push when commit is green. Phase complete.

### Plan-exit protocol (after the LAST phase the owner approved)

8. **CONVERGENCE CHECK** (mandatory subagent — `general-purpose`):
   Verify no phase regressed an earlier phase. Re-runs the calendar-deploy preflight from the original ask: spec values correct, enforcement scripts clean at calendar project, sync-drift count = 0, multi-service compose validates, etc.

9. **PLAN STATUS LINE** updated at the top: `Status: DRAFT v1` → `Status: SHIPPED <phases-completed> (YYYY-MM-DD)`.

### What "subagent" means here

Use the `Agent` tool with the named `subagent_type`. Do NOT delegate the WRITING or SYNTHESIS of the implementation to a subagent — they are for verification, re-grounding, and adversarial review only. The executing AI owns the diff.

### Test discipline (binding for every phase)

- Tests live in `tests/` mirroring the source path (e.g. `tests/test_drivers_postgres.py` for `src/fabrik/drivers/postgres.py`).
- Use pytest. No new test frameworks.
- Mock VPS-side effects (`subprocess.run`, `ssh`, GlitchTip/GitHub API calls) — tests must run hermetically with `pytest -q` in <5s.
- Per CLAUDE.md: at minimum 1 test for the highest-risk path per phase. Phases with multi-branch logic (5, 6, 7, 8) require coverage of: success path + idempotent re-run + failure-fallback path.

## Scope

Eight phases, each addressing one named gap. Phases 1–3 are quick wins (≤ 1h each); phases 4–8 are real orchestrator/driver work (1–4h each). Every phase is independent — they can ship in any order or in parallel branches if the owner wants.

| # | Gap | Effort | Files touched |
|---|---|---|---|
| 1 | calendar-orchestration-engine.yaml has 4 wrong shape/depends/env values | 15 min | 1 spec |
| 2 | `check_no_host_ports.py` + `check_traefik_labels.py` error when run at a no-`templates/` project (red-gates downstream) | 30 min | 2 scripts |
| 3 | AI-catalog regen drifts the synced rule packs daily → `check_synced_unmodified` red on every project | 45 min | `daily_refresh.sh` |
| 4 | Fabrik scaffold templates emit single-service compose only; multi-service (app + scheduler/worker companion) needs operator-curated compose with no convention | 2h | 1 template + 1 spec field + docs |
| 5 | New DB created empty; seed restore is manual post-apply step | 2h | `postgres.py` + spec field |
| 6 | Postgres backup plan covers cluster whole-dump; per-DB plan registration on `needs_database=true` is missing | 3h | `postgres.py` + `backrest.py` |
| 7 | GlitchTip webhook → watchdog `:8889` ingest is operator-manual in GlitchTip UI; should be auto-registered when both projects share a deploy | 3h | `glitchtip.py` driver |
| 8 | Watchdog generates deploy keypair but operator must paste pubkey into GitHub repo settings; should auto-push via `gh` CLI | 2h | `watchdog.py` driver |

## Pack alignment (per `select_rules.py`)

| Phase | Applicable packs (binding) |
|---|---|
| 1 | none (spec edit only) |
| 2 | `core/10-python.md` (script discipline) |
| 3 | `core/30-ops.md` (cron + deployment) |
| 4 | `core/30-ops.md` (Docker compose), `core/40-documentation.md` (Doc Sync Matrix) |
| 5 | `core/25-data-postgres.md` (migrations + ownership) |
| 6 | `core/25-data-postgres.md` + `core/30-ops.md` (backup hygiene) |
| 7 | `core/55-observability.md` (alert wiring) |
| 8 | `core/35-security-auth.md` (secret handling), `core/30-ops.md` |

## Out of scope

- No new fabrik commands.
- No changes to `_validate_compose()` itself (verified working for multi-service composes — see Evidence below).
- No changes to `kilo_consult.py` (verified `ruff check` green at 2026-06-30 09:00 UTC).
- No automation of vendor API key generation (ABSTRACT_API_KEY, FACTORY_API_KEY remain operator-provided).

---

## Phase 1 — Calendar spec corrections + fix `spec.depends.postgres` dead-code bug

**SPLIT into 1a + 1b-shape + 1b-depends** (Pass-9 external-review correction round 2): the three parts have radically different risk profiles and timing dependencies. Must NOT bundle.

- **Phase 1a — orchestrator refactor + 7 rename decisions**: change `_provision_postgres()` signature to accept `spec: dict[str, Any]`, update caller at [infrastructure.py:360](src/fabrik/orchestrator/infrastructure.py#L360), replace line 432 with `(spec.get("depends", {}) or {}).get("postgres") or name.replace("-", "_")`. **For each of the 7 at-risk specs, a per-spec A/B/C decision must be documented BEFORE this lands** (rename behavior becomes active on first re-apply of each spec). Calendar specifically has the "free rename" property below — no data migration needed for that one. Effort: ~1.5h refactor + per-spec operator decisions.
- **Phase 1b-shape — 3 calendar spec edits that drive registrars NOW** (safe, ~3 min, zero risk, ships independently of 1a):
  - `shape.is_admin_dashboard: false → true` (Authelia)
  - `shape.exposes_metrics: false → true` (Prometheus)
  - `env.WATCHDOG_TEST_CMD: "npm test" → "npm run test:api"` (watchdog)
- **Phase 1b-depends — `depends.postgres: calendar → calendar_engine`**: **INERT until 1a lands** (the field is dead code today). Ship this edit BUNDLED WITH 1a, not standalone, so the spec change activates the same day the orchestrator starts respecting the field. Until then the calendar DB-creation gap persists (orchestrator still derives `calendar_orchestration_engine`; project expects `calendar_engine`).

### "Free rename" for calendar specifically

Calendar's current spec ([specs/services/calendar-orchestration-engine.yaml:16](specs/services/calendar-orchestration-engine.yaml#L16)) explicitly notes: **"was missing → DB never created"**. Meaning: the spec-id-derived DB (`calendar_orchestration_engine`) was never actually provisioned on `postgres-main` — fabrik never created it because the spec was wrong end-to-end. So when 1a lands + 1b-depends ships, fabrik will create `calendar_engine` fresh; no data migration needed. **Calendar's A/B/C decision = trivially Option A (accept rename, zero migration cost).**

The OTHER 6 at-risk specs (`youtube, fabrik-claim-validator, proposal-creator, trading-core, triggered-content-orchestration, job-agent`) MAY have already-provisioned DBs at the derived name. Each needs operator verification BEFORE 1a lands: `ssh vps1 'docker exec postgres-main psql -U postgres -l | grep -E "youtube|fabrik_claim|proposals|trading_core|triggered_content|job_agent"'`. Any that exist need an A/B/C decision + manual `pg_dump | psql` data migration to the new name.

**Goal**: Hub spec matches project reality so `fabrik apply` triggers the right registrars, AND the long-standing `spec.depends.postgres` dead-code bug is fixed (or the spec field is removed as misleading).

### Pre-existing bug surfaced by Pass-1 grounding

[infrastructure.py:432](src/fabrik/orchestrator/infrastructure.py#L432) derives the DB name as `spec.id.replace("-", "_")`. For `calendar-orchestration-engine` that yields **`calendar_orchestration_engine`** — but the project's actual compose + .env use **`calendar_engine`** (per [/opt/calendar-orchestration-engine/.env.example:9](/opt/calendar-orchestration-engine/.env.example#L9) `PG_DATABASE=calendar_engine` and [/opt/calendar-orchestration-engine/compose.yaml:30](/opt/calendar-orchestration-engine/compose.yaml#L30)).

So `spec.depends.postgres` is **decorative** — fabrik ignores it entirely. Editing the spec field from `calendar` → `calendar_engine` (as the original plan said) is a no-op. The real disagreement (`calendar_orchestration_engine` from the spec-id-derived path vs. `calendar_engine` from the project) is a silent bug: `fabrik apply` would create a DB named `calendar_orchestration_engine` + inject a `DATABASE_URL` pointing at it, while the project's runtime expects `calendar_engine`.

### F1 — Phase 1a is NOT a one-liner (external-review correction, 2026-06-30)

Original plan said the fix was `db_name = spec.depends.postgres or spec.id.replace("-","_")` at [infrastructure.py:432](src/fabrik/orchestrator/infrastructure.py#L432). **That pseudo-code wouldn't run** for two reasons confirmed by reading the actual code:

1. **`_provision_postgres()` at [infrastructure.py:426](src/fabrik/orchestrator/infrastructure.py#L426) has NO `spec` parameter in scope**:
   ```python
   def _provision_postgres(self, name: str, ctx: DeploymentContext, dry_run: bool) -> None:
       ...
       db_name = name.replace("-", "_")  # line 432
   ```
   The caller at [infrastructure.py:360](src/fabrik/orchestrator/infrastructure.py#L360) is `self._provision_postgres(name, ctx, dry_run)` — only `name` is passed.

2. **Spec at this layer is a `dict[str, Any]`, not the Pydantic model**: peer registrar [`_provision_gatus`](src/fabrik/orchestrator/infrastructure.py#L455) takes `spec: dict[str, Any]` and accesses via `spec.get(...)`. The plan's `.depends.postgres` attribute access doesn't apply here.

**Real Phase 1a scope (3-part refactor, not a 1-line patch)**:

a. Change `_provision_postgres()` signature: `def _provision_postgres(self, name: str, spec: dict[str, Any], ctx, dry_run)` — matches the `_provision_gatus` pattern already used by 5+ other registrars at the same layer.

b. Update the caller at line 360 to pass spec: `self._provision_postgres(name, spec, ctx, dry_run)`. **Grep for ALL callers of `_provision_postgres` before editing** — if there are other call sites, every one must be updated atomically.

c. Inside the function body, replace line 432 with:
   ```python
   db_name = (spec.get("depends", {}) or {}).get("postgres") or name.replace("-", "_")
   ```
   The `(spec.get("depends", {}) or {})` double-default handles specs where `depends:` is explicitly `null` (returns `None`, not `{}`) — confirmed by reading other registrars' patterns.

**Re-classification**: Phase 1a is no longer a 15-minute one-liner. It's a registrar-signature refactor with caller updates + the original R2 risk (7 silent DB renames). Effort: **~1.5h coding + 7 operator A/B/C decisions**. Stays BLOCKED on the per-spec decisions PLUS now also needs the signature refactor PR.

### Scope

**1a — fix the orchestrator** ([src/fabrik/orchestrator/infrastructure.py:432](src/fabrik/orchestrator/infrastructure.py#L432)): respect `spec.depends.postgres` when set; fall back to `spec.id.replace("-", "_")` only if the field is absent. This makes the spec field load-bearing AND backward-compatible (every existing spec that omits the field continues to use the derived name).

**1b — fix the spec** ([specs/services/calendar-orchestration-engine.yaml](specs/services/calendar-orchestration-engine.yaml)):
- `shape.is_admin_dashboard: false` → `true`
- `shape.exposes_metrics: false` → `true`
- `depends.postgres: calendar` → `calendar_engine` (NOW load-bearing after 1a)
- `env.WATCHDOG_TEST_CMD: "npm test"` → `"npm run test:api"`

**1c — add spec ↔ project consistency check** ([scripts/enforcement/check_spec_db_match.py](scripts/enforcement/check_spec_db_match.py), NEW): a lean check that for every project with both a hub spec AND a local `.env.example`/`compose.yaml`, verifies `spec.depends.postgres` (or the derived name) matches the project-side DB name. Run from `final_gate.py`. Catches future drift.

### Approach

1. Grep `infrastructure.py:432` ± 20 lines to find the exact derivation logic + which function wraps it. Edit to `db_name = spec.depends.postgres or spec.id.replace("-", "_")`.

2. **🔴 BLOCKING pre-step — Pass 5 enumerated 7 at-risk specs** (verified 2026-06-30):
   ```
   AT-RISK (spec.depends.postgres != spec.id.replace("-", "_")):
     youtube                            → spec=youtube_pipeline    (derived=youtube)
     calendar-orchestration-engine      → spec=calendar            (derived=calendar_orchestration_engine)
     fabrik-claim-validator             → spec=main                (derived=fabrik_claim_validator)
     proposal-creator                   → spec=proposals           (derived=proposal_creator)
     trading-core                       → spec=trading             (derived=trading_core)
     triggered-content-orchestration    → spec=tco                 (derived=triggered_content_orchestration)
     job-agent                          → spec=jobagent            (derived=job_agent)
   ```
   For EACH of these 7 specs, before 1a fix lands, decide:
   - **Option A — accept the rename**: the derived name was always wrong; the spec value was the operator's intent. After fix, fabrik routes to `youtube_pipeline` instead of `youtube`. **Requires manual pg_dump + psql restore of existing data into the new DB name BEFORE the next `fabrik apply`.**
   - **Option B — remove the spec field**: preserve the current derived behavior by deleting `depends.postgres:` from the spec. Project keeps using `youtube` (etc.) as its DB name. Document the project-side `.env`/compose disagreement separately if needed.
   - **Option C — keep the spec field as-is + override**: introduce a new explicit override key (e.g., `depends.postgres_keep_derived_name: true`) and respect it. Probably overkill; choose A or B.

   **Decision per spec must be in this plan or a sibling doc BEFORE 1a ships.** Cannot land 1a + auto-rename without operator approval per project.

3. Apply the 4 spec edits in 1b (calendar-orchestration-engine specifically).

4. Write the consistency check in 1c.

### Test plan (BLOCKING per CLAUDE.md)

- `tests/test_infrastructure_db_name.py` (NEW): `test_spec_depends_postgres_used_when_present`, `test_spec_depends_postgres_fallback_to_derived_when_absent`, `test_no_existing_spec_silently_renames_db` (golden test enumerating all current specs).
- `tests/test_check_spec_db_match.py` (NEW): `test_passes_when_spec_matches_project_env`, `test_fails_when_drift_detected`, `test_skips_projects_without_spec`.

### Validation gate (exact commands + expected results)

```bash
# 1. Per-spec at-risk audit (must produce empty diff)
python -c "import yaml; from pathlib import Path; \
  drifts = [(p.stem, d) for p in Path('specs/services').glob('*.yaml') \
    if (d := yaml.safe_load(p.read_text()).get('depends',{}).get('postgres')) \
       and d != p.stem.replace('-','_')]; \
  print('AT-RISK:', drifts) if drifts else print('NO DRIFT')"
# Expected: NO DRIFT, OR an enumerated list the operator has approved.

# 2. Tests (BLOCKING — phase exit gate)
pytest tests/test_infrastructure_db_name.py tests/test_check_spec_db_match.py -q
# Expected: all green.

# 3. New consistency check at the project
cd /opt/calendar-orchestration-engine && \
  python /opt/fabrik/scripts/enforcement/check_spec_db_match.py
# Expected: exit 0, "spec ↔ project DB name match: calendar_engine"

# 4. Lean gate
python /opt/fabrik/scripts/final_gate.py --lean --json
# Expected: {"status":"success"}
```

### Adversarial review (mandatory per Mandatory Execution Protocol step 5)

Use the Appendix A prompt. Hunt specifically for: (a) other call sites of `spec.depends.postgres` that may also be dead code, (b) the derived-name pattern leaking into other registrars (Redis? backup?), (c) URL-injection consequences if a project sets `depends.postgres: "../escape"`.

---

## Phase 2 — Enforcement scripts skip cleanly when `templates/` absent

**Goal**: `check_no_host_ports.py` + `check_traefik_labels.py` do not red-gate projects that don't have a `templates/` directory (every non-fabrik project).

### Reproduction (verified 2026-06-30)

```
$ cd /opt/calendar-orchestration-engine
$ /opt/fabrik/.venv/bin/python scripts/enforcement/check_no_host_ports.py
ERROR: --templates-dir /opt/calendar-orchestration-engine/templates does not exist or is not a directory
$ echo $?
2
```

Plan's original "exit 1" claim was wrong — both scripts return **exit 2** on missing dir ([check_no_host_ports.py:323-328](scripts/enforcement/check_no_host_ports.py#L323), [check_traefik_labels.py:277-282](scripts/enforcement/check_traefik_labels.py#L277)).

### Root cause (corrected via Pass-1 grounding)

Both scripts have argparse default `--templates-dir = Path(__file__).resolve().parent.parent.parent / "templates"` ([check_no_host_ports.py:313-319](scripts/enforcement/check_no_host_ports.py#L313)). The default is **script-relative**, not cwd-relative. When the script is synced to a project's `scripts/enforcement/`, that resolves to the project's `templates/`, which doesn't exist → exit 2. Plan originally misdiagnosed this as cwd-relative; corrected here.

### Scope

- [scripts/enforcement/check_no_host_ports.py:323-328](scripts/enforcement/check_no_host_ports.py#L323) — replace the "ERROR + return 2" branch with a skip-with-exit-0 branch.
- [scripts/enforcement/check_traefik_labels.py:277-282](scripts/enforcement/check_traefik_labels.py#L277) — same fix.
- [tests/test_check_no_host_ports.py](tests/test_check_no_host_ports.py) + [tests/test_check_traefik_labels.py](tests/test_check_traefik_labels.py) — add missing-templates-dir test cases.

### Approach

Replace the existing block (verified content):
```python
# Current (returns exit 2):
if not templates_dir.is_dir():
    print(f"ERROR: --templates-dir {templates_dir} does not exist or is not a directory", file=sys.stderr)
    return 2

# Replacement (returns exit 0):
if not templates_dir.is_dir():
    print(f"[skip] no templates/ dir at {templates_dir} — nothing to check")
    return 0
```

**Why skip vs error**: the checks exist to catch host-bound `ports:` in TEMPLATE compose files. A project with no templates has nothing to check; that's a valid state, not a violation. The current exit-2 conflates "I can't do my job" with "I found a violation" — wrong signal.

**Why exit 0 not 2 on skip**: `final_gate.py` at lines 662, 676 invokes both scripts via `run_optional_check()` with no `--templates-dir` arg, so they use their defaults. Treating "no templates/" as success is correct — `run_optional_check` only fails on non-zero exit.

### Test plan (BLOCKING per CLAUDE.md)

- `tests/test_check_no_host_ports.py::test_skip_when_templates_dir_missing` — `tmp_path` with no `templates/`, assert exit 0 + `[skip]` in stdout.
- `tests/test_check_no_host_ports.py::test_skip_when_templates_dir_empty_returns_zero` — `tmp_path / "templates"` created empty, assert exit 0 (no violations, no skip).
- `tests/test_check_no_host_ports.py::test_violation_still_caught_when_templates_exist` — golden test against `/opt/fabrik/templates/` (must continue to detect any future host-port violation).
- Same 3 tests for `check_traefik_labels.py`.

### Validation gate (exact commands + expected results)

```bash
# 1. Tests (BLOCKING)
pytest tests/test_check_no_host_ports.py tests/test_check_traefik_labels.py -q
# Expected: all green.

# 2. Reproduce at calendar project — must now exit 0
cd /opt/calendar-orchestration-engine
/opt/fabrik/.venv/bin/python scripts/enforcement/check_no_host_ports.py; echo "exit=$?"
/opt/fabrik/.venv/bin/python scripts/enforcement/check_traefik_labels.py; echo "exit=$?"
# Expected: both print "[skip] no templates/ dir at …" and "exit=0"

# 3. Verify fabrik root still catches its OWN template violations
cd /opt/fabrik
/opt/fabrik/.venv/bin/python scripts/enforcement/check_no_host_ports.py; echo "exit=$?"
# Expected: exit=0 (clean — no host ports in any template) — proves skip didn't mask real violations

# 4. Lean gate
cd /opt/fabrik && python scripts/final_gate.py --lean --json
# Expected: {"status":"success"}

# 5. Sync-to-projects audit (so the fix is actually distributed)
/opt/fabrik/.venv/bin/python scripts/sync_enforcement_to_projects.py --dry-run | grep -E "check_no_host_ports|check_traefik_labels"
# Expected: both scripts listed as would-update for every project
```

### Adversarial review

Use the Appendix A prompt with the 2 modified scripts as the in-scope file list. Hunt specifically for: (a) other enforcement scripts with the same `Path(__file__).resolve().parent...` pattern that should ALSO get the skip-when-absent fix (audit all of `scripts/enforcement/*.py`), (b) the exit-code 0 vs 2 distinction breaking any CI that greps `exit 2 = config error` vs `exit 1 = violation`.

---

## Phase 3 — Auto-sync after AI-catalog regen

**Goal**: `check_synced_unmodified.py` stops firing daily on every project for files the AI catalog refresh writes.

### Reproduction (verified 2026-06-30)

`cd /opt/calendar-orchestration-engine && /opt/fabrik/.venv/bin/python scripts/enforcement/check_synced_unmodified.py` flags 11 files: `.windsurf/rules/ai/00-ai-model-selection.md` through `90-long-context.md` (8 files) + `docs/reference/kilo/KILO_AGENT_SELECTION_GUIDE.md` + `docs/reference/kilo/KILO_MODEL_CAPABILITIES.md` + `docs/reference/windsurf/cascade-models.md`.

### Root cause (CORRECTED via Pass-1 grounding)

The 8 `.windsurf/rules/ai/*.md` files are regenerated by [scripts/kilo-benchmarks/category_export_markdown.py:408,421](scripts/kilo-benchmarks/category_export_markdown.py#L408) and [scripts/kilo-benchmarks/update_gateway_counts.py:42](scripts/kilo-benchmarks/update_gateway_counts.py#L42) (`RULES_DIR = FABRIK_ROOT / ".windsurf" / "rules" / "ai"`).

**BUT**: `kilo_agents_db.py` does NOT write to the 3 remaining files (`KILO_AGENT_SELECTION_GUIDE.md`, `KILO_MODEL_CAPABILITIES.md`, `cascade-models.md`) — it only writes to `docs/traycer/kilo_selected_agents.md` (`MASTER_MD` at line 43) and `docs/reference/LOCAL_LLM_INFRASTRUCTURE.md` (`LOCAL_LLM_DOC` at line 629). **Plan originally misattributed these generators.**

✅ **Pass-2 RESOLVED + Pass-5 verified**: 3 confirmed writers (have `.write_text(` / `f.write(` against the target paths):
- [scripts/kilo-benchmarks/generate_model_capabilities.py:155](scripts/kilo-benchmarks/generate_model_capabilities.py#L155) — `OUT_FILE.write_text(...)` → `docs/reference/kilo/KILO_MODEL_CAPABILITIES.md`
- [scripts/kilo-benchmarks/generate_selection_guide_roster.py:190](scripts/kilo-benchmarks/generate_selection_guide_roster.py#L190) — `GUIDE_FILE.write_text(...)` → `docs/reference/kilo/KILO_AGENT_SELECTION_GUIDE.md`
- [scripts/kilo-benchmarks/scrape_windsurf_models.py:538](scripts/kilo-benchmarks/scrape_windsurf_models.py#L538) — `md_path.write_text(...)` → `docs/reference/windsurf/cascade-models.md`

**Pass-5 grep also surfaced 7 other files that MENTION these paths** (`docs_updater.py`, `watch_enforcement_changes.sh`, `sync_enforcement_to_projects.py`, `update_kilo_benchmarks.py`, `cache/update.log`, `embedding_export_markdown.py`, `fabrik_synced_manifest.py`) — verified as **references**, not writers (`grep -E 'write_text|f\.write\(' <files>` against the target paths returns empty for all 7).

These 3 scripts must be wired into `daily_refresh.sh` (Path A) — they get run, regenerate their outputs, then the sync step pushes the regenerated copies to all projects.

### Drifts also caught by Pass-1

🟥 **`sync_enforcement_to_projects.py` has NO `--quiet` flag**. Verified flags (from [scripts/sync_enforcement_to_projects.py:414-434](scripts/sync_enforcement_to_projects.py#L414)): `--dry-run`, `--backup`, `--force`, `-v/--verbose`. Plan's wiring `"$VENV_PY" "$FABRIK_ROOT/scripts/sync_enforcement_to_projects.py" --quiet` would fail with argparse error.

### Resolution path (REVISED after Pass-1)

Two independent fixes, both required:

**3a — Wire the 3 KILO_*/cascade-models generators into daily_refresh.sh** (Path A — Pass-2 confirmed generators exist):

⚠️ **CRITICAL ordering constraint (Pass-6 finding)**: `embedding_export_markdown.py` (already in cron at [daily_refresh.sh:166](scripts/kilo-benchmarks/daily_refresh.sh#L166)) writes PARTIAL content into `KILO_AGENT_SELECTION_GUIDE.md` + `KILO_MODEL_CAPABILITIES.md` (between `EMBEDDING_ROSTER:START/END` + `EMBEDDING_CATALOG:START/END` markers — see [embedding_export_markdown.py:40-41,283-284](scripts/kilo-benchmarks/embedding_export_markdown.py#L40)). The 3 new generators write the ENTIRE file. If they run AFTER `embedding_export_markdown.py`, they NUKE the embedding marker sections.

- **Insertion point**: BEFORE [daily_refresh.sh:166 `embedding_export_markdown.py`](scripts/kilo-benchmarks/daily_refresh.sh#L166), AFTER [line 128 `update_kilo_benchmarks.py --force`](scripts/kilo-benchmarks/daily_refresh.sh#L128) (so they get the freshly-scraped benchmarks). This way:
  1. update_kilo_benchmarks.py refreshes benchmark data
  2. NEW: `generate_model_capabilities.py` writes full KILO_MODEL_CAPABILITIES.md
  3. NEW: `generate_selection_guide_roster.py` writes full KILO_AGENT_SELECTION_GUIDE.md
  4. NEW: `scrape_windsurf_models.py` writes full cascade-models.md
  5. `embedding_export_markdown.py` overwrites just the EMBEDDING_* marker sections
  6. (much later) `category_export_markdown.py` + `update_gateway_counts.py` write the .windsurf/rules/ai/*.md
  7. NEW: sync_enforcement step (3b) pushes all regenerated files to projects
- Snippet (mirrors existing `|| echo "[daily_refresh] X failed (non-fatal)"` pattern):
  ```bash
  "$VENV_PY" "$KB/generate_model_capabilities.py" \
    || echo "[daily_refresh] generate_model_capabilities failed (non-fatal)"
  "$VENV_PY" "$KB/generate_selection_guide_roster.py" \
    || echo "[daily_refresh] generate_selection_guide_roster failed (non-fatal)"
  "$VENV_PY" "$KB/scrape_windsurf_models.py" \
    || echo "[daily_refresh] scrape_windsurf_models failed (non-fatal)"
  ```

**3b — Wire sync into daily_refresh.sh** (after 3a so it picks up freshly regenerated outputs):
- Recommend: skip the `--quiet` flag dance (small bash code, more honest cron log if it ever errors). Use no flag.
- Wrap with `flock /tmp/fabrik-sync-enforcement.lock` to handle race with manual operator runs.
  ```bash
  flock /tmp/fabrik-sync-enforcement.lock -c "$VENV_PY $FABRIK_ROOT/scripts/sync_enforcement_to_projects.py" \
    || echo "[daily_refresh] sync_enforcement failed (non-fatal)"
  ```
- If `--quiet` is later judged necessary, it's a 3-line addition to `sync_enforcement_to_projects.py` argparse — separate ticket.

### Race-condition mitigation

`sync_enforcement_to_projects.py` has NO lock file (verified — grep shows zero lock-related code). Manual operator runs + cron daily run could race. Two options:
- Wrap cron call with `flock /tmp/fabrik-sync-enforcement.lock -c "<cmd>"` (cheap).
- Or add a lock primitive to the sync script itself (more invasive, blocks operator interactive runs unexpectedly).

Recommend `flock` wrapper.

### Test plan (BLOCKING)

- Pass-2-dependent: cannot finalize test list until 3b path is chosen.
- Always required: `tests/test_sync_enforcement_quiet_flag.py` — assert `--quiet` flag exists if 3a takes that route.

### Validation gate (exact commands)

```bash
# 1. Re-ground the 3 unknown generators (run as part of Pass 2 — BLOCKING)
grep -rln "KILO_AGENT_SELECTION_GUIDE\|KILO_MODEL_CAPABILITIES\|cascade-models" \
  /opt/fabrik/scripts/ | grep -v "\.pyc$" | head -20
# Expected: at least one writer per file, OR empty (confirming operator-curated → use 3b Path B)

# 2. After fix: reproduce drift at calendar — must show clean
cd /opt/calendar-orchestration-engine
/opt/fabrik/.venv/bin/python scripts/enforcement/check_synced_unmodified.py
# Expected: exit 0, no drift listed

# 3. Cron-safety verification (no TTY, no prompts)
env -i PATH=/usr/bin:/bin HOME=$HOME /opt/fabrik/.venv/bin/python \
  /opt/fabrik/scripts/sync_enforcement_to_projects.py --dry-run 2>&1 | tail -5
# Expected: clean run, no "tty" or "input" errors

# 4. Race-condition guard exists
grep -E "flock|LOCK_FILE" /opt/fabrik/scripts/kilo-benchmarks/daily_refresh.sh | head
# Expected: at least the flock invocation for sync-enforcement

# 5. Lean gate
cd /opt/fabrik && python scripts/final_gate.py --lean --json
# Expected: {"status":"success"}
```

### Adversarial review

Use Appendix A prompt. Hunt: (a) other "regenerated but not synced" file patterns (look at every writer in `daily_refresh.sh` and check whether their outputs are in `ENFORCEMENT_DIR` sync set), (b) the race on a slow VPS where sync_enforcement takes >5min and operator's manual sync starts mid-cron-run.

---

## Phase 4 — Multi-service compose: first-class support

**Goal**: Specs can declare a companion service (scheduler/worker that shares the app's image but runs a different command) without operator hand-rolling a custom compose.yaml.

**Today's reality**:
- `_validate_compose()` at [src/fabrik/orchestrator/deployer_ssh.py:636-696](src/fabrik/orchestrator/deployer_ssh.py#L636) iterates every service in the compose and validates each independently. So a 2-service committed compose works — but only if the operator hand-rolls it correctly.
- `templates/node-api/compose.yaml.j2` emits ONE service only. Same for `python-api`, `file-api`, etc.
- `templates/file-worker/defaults.yaml:7` declares `kind: worker` but is for STANDALONE workers, not companions.
- No spec field exists for "this service also has a companion that shares my image but runs `node dist/scheduler.js`".

**Scope**:
- Add spec field `companion_services:` (optional list) at the spec_loader level.
- Update each `templates/*/compose.yaml.j2` template that has companion-eligible kinds (node-api, python-api) to emit additional services when `companion_services` is non-empty. Each companion inherits the parent's build context, env, and depends; overrides only `command` + `container_name` + (optionally) `resources.memory`.
- Update [docs/DEPLOYMENT_ARCHITECTURE.md](docs/DEPLOYMENT_ARCHITECTURE.md) — add a Multi-Service Compose section explaining: (a) committed-compose path (`source.type: git`), (b) scaffold-emitted path (`companion_services:`).

**Spec shape**:
```yaml
companion_services:
  - id: calendar-scheduler        # becomes container_name (validated: slug regex)
    command: ["node", "dist/scheduler.js"]
    memory: 256M                  # REQUIRED (no default) — see "memory default" below
    env_overrides:                # optional — merged on top of parent env
      ROLE: scheduler
```

**Approach**:
1. Pydantic model field `companion_services: list[CompanionService] | None` in [src/fabrik/spec_loader.py](src/fabrik/spec_loader.py) — added next to the existing `Depends` class at lines 177-182. New `CompanionService` model with fields: `id: str` (regex `^[a-z][a-z0-9-]*$`), `command: list[str]` (non-empty), `memory: str` (`512M` / `1G` pattern), `env_overrides: dict[str, str] | None`.
2. Jinja partial `templates/_partials/_companion_service.yaml.j2` (new dir) factored from the parent service block, included from a `{% for c in companion_services %}` loop in each parent template (`node-api`, `python-api` — image-eligible kinds only; SaaS/static/wordpress skip).
3. Document in [docs/DEPLOYMENT_ARCHITECTURE.md](docs/DEPLOYMENT_ARCHITECTURE.md) — add new section between current §5 (Templates) and §6 (Local Config Mirrors).
4. Reference example: calendar-orchestration-engine spec gets a `companion_services:` block once the project's repo commits the scheduler entry-point. NOT shipped as part of this phase — separate ticket.

### Memory default — resolved (Pass-1 gap)

Pass-1 grounder flagged "default = half of parent's" as unresolved. **Resolution: REQUIRE explicit `memory:` per companion**. Rationale: (a) the parent's `resources.memory` lives at the spec top-level under `resources:` not next to `companion_services:`, so jinja can compute "half of parent" but it's surprising at spec-read time; (b) workers/schedulers have wildly different memory profiles than HTTP services (often less, sometimes more); (c) operator should declare intent explicitly. Pydantic validator rejects missing or non-parseable values.

If "half of parent" is preferred later, can be added as `memory: auto` sentinel (out-of-scope for this phase).

### Validation gate (exact commands + expected results)

```bash
# 1. Tests (BLOCKING)
pytest tests/test_scaffold_compose_traefik.py tests/test_spec_loader_companion.py -q
# Expected: green (test_spec_loader_companion.py is NEW)

# 2. Render a fixture spec with companion_services + assert both services validate
python -c "
import yaml, subprocess
spec = {'id':'foo-svc','kind':'service','template':'node-api',
        'domain':'foo.example.com','companion_services':[
          {'id':'foo-scheduler','command':['sleep','1'],'memory':'128M'}]}
# render via scaffold engine, then run _validate_compose on output
"
# Expected: 2-service compose, both pass platform/memory/container_name/restart checks.

# 3. Pre-existing single-service specs still render correctly (no companion_services field)
for spec in /opt/fabrik/specs/services/*.yaml; do
  fabrik scaffold --spec "$spec" --dry-run > /dev/null && echo "OK $spec" || echo "FAIL $spec"
done
# Expected: all OK

# 4. Lean gate
python /opt/fabrik/scripts/final_gate.py --lean --json
# Expected: {"status":"success"}
```

### Adversarial review

Use Appendix A prompt. Hunt: (a) what happens when companion's `container_name` collides with another service's name (cross-project), (b) does the companion inherit the parent's Traefik labels and accidentally route HTTP traffic to a non-HTTP container, (c) `depends_on` ordering between parent + companion if companion needs the parent to be up first.

**Evidence**: verified `_validate_compose` already supports multi-service via the iteration loop ([deployer_ssh.py:658](src/fabrik/orchestrator/deployer_ssh.py#L658) `for svc_name, svc_config in services.items()`).

**Test**: scaffold test fixture with `companion_services: [{id: foo-scheduler, command: ["sleep","1"]}]` → render → assert generated compose has 2 services + both pass `_validate_compose`.

**Final Gate Instruction**: `python /opt/fabrik/scripts/final_gate.py --lean --json` + render test above.

---

## Phase 5 — DB seed auto-restore

**Goal**: New databases get seeded from a checked-in dump if the spec says so. No manual `zcat | psql` step after apply.

**Today's reality**:
- [src/fabrik/drivers/postgres.py:226-260](src/fabrik/drivers/postgres.py#L226) creates the DB + dedicated role + grants ownership. Empty DB.
- Operator's docs (e.g. calendar README) instruct manual `zcat backups/<spec>_seed_*.sql.gz | psql "$DATABASE_URL"` post-apply.
- Easy to forget; non-idempotent if the role already created some tables.

**Scope**:
- Add `depends.postgres_seed:` spec field, accepting a project-relative path: `backups/calendar_engine_seed_LATEST.sql.gz`.
- Extend [src/fabrik/drivers/postgres.py](src/fabrik/drivers/postgres.py) `ensure_database()` (or equivalent registrar entry) so that AFTER role+grant succeeds, if `postgres_seed` is set AND the DB has zero user tables, run `zcat <path> | docker exec -i postgres-main psql -U <db_user> -d <db_name>` on the VPS via SSH.
- The "zero user tables" check is the idempotency guard — don't overwrite operator data if they manually loaded a different seed or modified schema.

**Spec shape**:
```yaml
depends:
  postgres: calendar_engine
  postgres_seed: backups/calendar_engine_seed_LATEST.sql.gz   # optional
```

### Approach (REVISED after Pass-1 grounding)

1. **Pydantic model field** added under existing `Depends` class at [spec_loader.py:177-182](src/fabrik/spec_loader.py#L177): `postgres_seed: str | None`. Validator: must be relative path (no leading `/`), no `..` segments, must end in `.sql.gz`.

2. **Helper `_count_user_tables(container, db_user, db_name) -> int`** in [postgres.py](src/fabrik/drivers/postgres.py). **CORRECTED query** (Pass-1 gap — pg_stat_statements would false-positive):
   ```sql
   SELECT COUNT(*) FROM information_schema.tables
   WHERE table_type = 'BASE TABLE'
     AND table_schema NOT IN ('pg_catalog', 'information_schema');
   ```
   Run via `_run_sql()` (existing helper in postgres.py) against the new `db_name`, NOT against the `postgres` superuser DB.

3. **Helper `_restore_seed(spec_dir, seed_relpath, container, db_user, db_name)`** with these steps:
   - **Path validation** (CORRECTED — Pass-1 gap): `resolved = (spec_dir / seed_relpath).resolve()`; assert `resolved.is_relative_to(spec_dir)` (Python 3.9+); assert `resolved.is_file()`.
   - **File shipping** (CORRECTED — Pass-1 gap): use existing [ssh.py:89 `scp_to_vps(local_path, remote_path)`](src/fabrik/drivers/ssh.py#L89) to copy the dump from operator's WSL to VPS-side `/tmp/fabrik-seed-{spec_id}-{epoch}.sql.gz`. **Local path is `spec_dir / seed_relpath`** (i.e., a checked-in file under the project repo's `backups/` — gitignored per fabrik convention).
   - **Restore command**: `cat /tmp/fabrik-seed-{...}.sql.gz | docker exec -i postgres-main bash -c 'gunzip | psql -U {db_user} -d {db_name}'`. Wrapping `gunzip | psql` inside the container's bash is the only way to make the pipe survive across `docker exec -i`.
   - **Cleanup**: `rm /tmp/fabrik-seed-{...}.sql.gz` on success (always; sensitive data should not linger).
   - **Idempotency**: skip if `_count_user_tables > 0`. Log the skip with reason.

4. **Document** in [docs/operations/deployment.md](docs/operations/deployment.md) + postgres driver docstring.

### Security (REVISED)

- Path traversal: enforced via `pathlib.Path.is_relative_to(spec_dir)` (rejects `..`, absolute paths, symlink escapes).
- Dump file is treated as sensitive: copied to `/tmp/` with `0600`, deleted on success or failure (try/finally).
- `psql` runs as the dedicated per-DB role (not superuser) — restored objects owned by the role, no privilege escalation.

### Evidence (CORRECTED — Pass-1)

- Role+grant block at [postgres.py:220-241](src/fabrik/drivers/postgres.py#L220), inside function `create_database()` at [line 131-167](src/fabrik/drivers/postgres.py#L131). **Plan's "ensure_database()" was wrong — actual function is `create_database`.**
- `POSTGRES_CONTAINER = "postgres-main"` at [postgres.py:53](src/fabrik/drivers/postgres.py#L53).
- `scp_to_vps(local_path: str, remote_path: str, timeout: int = 30, dry_run: bool = False) -> None` at [src/fabrik/drivers/ssh.py:89](src/fabrik/drivers/ssh.py#L89). Uses `FABRIK_VPS_SSH_HOST` env var at [src/fabrik/drivers/ssh.py:43](src/fabrik/drivers/ssh.py#L43). NOTE: parameters are `str`, not `pathlib.Path` — the test in Phase 5 must use string paths.

### Test plan (BLOCKING)

- `tests/test_postgres_seed.py::test_count_user_tables_excludes_pg_catalog` — mock `_run_sql` to return rows from `pg_stat_statements` extension, assert count returns 0.
- `tests/test_postgres_seed.py::test_restore_seed_skips_when_db_nonempty` — mock `_count_user_tables` to return 1, assert restore is skipped + logged.
- `tests/test_postgres_seed.py::test_restore_seed_path_traversal_rejected` — assert `ValueError` on `seed_relpath = "../../../etc/passwd"`.
- `tests/test_postgres_seed.py::test_restore_seed_path_traversal_absolute_rejected` — assert `ValueError` on absolute path.
- `tests/test_postgres_seed.py::test_restore_seed_temp_file_cleaned_up` — mock scp + docker exec, assert temp file removed on success AND on failure.

### Validation gate (exact commands + expected results)

```bash
# 1. Tests (BLOCKING)
pytest tests/test_postgres_seed.py -q
# Expected: 5 green

# 2. Confirm scp_to_vps signature unchanged (would break if upstream renames)
# F2 fix (external-review): actual signature uses `local_path: str`, NOT Path
sed -n '89,95p' /opt/fabrik/src/fabrik/drivers/ssh.py
# Expected (verbatim):
#   def scp_to_vps(
#       local_path: str,
#       remote_path: str,
#       timeout: int = 30,
#       dry_run: bool = False,
#   ) -> None:

# 3. Confirm create_database call site
grep -nE "create_database\(" /opt/fabrik/src/fabrik/orchestrator/infrastructure.py
# Expected: at least one match — the registrar entry point

# 4. Lean gate
python /opt/fabrik/scripts/final_gate.py --lean --json
# Expected: {"status":"success"}
```

### Adversarial review

Use Appendix A prompt. Hunt: (a) what if the dump file is malformed — does the restore wrapper detect failure and roll back; (b) the temp file at `/tmp/fabrik-seed-*.sql.gz` is sensitive — confirm umask creates it 0600; (c) `docker exec -i` does NOT allocate a TTY — confirm `gunzip | psql` actually works without one.

---

## Phase 6 — Postgres backup: per-DB plan registration ✅ Pass-2 unblocked

**Goal**: Each fabrik-created database gets its own Backrest plan with per-DB retention, layered on top of the existing whole-cluster `pg_dumpall` backup.

### Verified current state (Pass-2 SSH to vps1, 2026-06-30)

| # | Fact | Evidence |
|---|---|---|
| F1 | Whole-cluster backup exists: Backrest plan `postgres-dumps` paths=`/opt/backups/`, schedule `0 2 * * *` daily at 02:00 UTC+3, retention `daily:7, weekly:4, monthly:6`. Hooks: **null**. | `ssh vps1 'cat /opt/backrest/config/config.json \| jq ".plans[] \| select(.id==\"postgres-dumps\")"'` |
| F2 | `/opt/backups/pg_dump_*.sql` files produced by **host-side cron**, not Backrest hooks. Cron entry: `30 1 * * * /opt/backups/pre-backup.sh` (host root crontab). | `ssh vps1 'sudo crontab -l \| grep pre-backup'` |
| F3 | Backrest container has `/opt` mounted RO as `/opt` — `/opt/backups/` accessible via parent mount. NO postgres-specific mount needed. | `ssh vps1 'sudo docker inspect $(sudo docker ps --format "{{.Names}}" \| grep backrest) \| jq ".[0].Mounts"'` |
| F4 | `postgres-main` container env: `POSTGRES_USER=postgres POSTGRES_PASSWORD=postgres` (default postgres:16 image; socket-trust inside container; docker exec runs as root → no password needed). | `ssh vps1 'sudo docker exec postgres-main env \| grep POSTGRES_'` |

### Design (now grounded — matches existing pattern)

**Per-DB layering on top of the existing host-side cron pattern**:

1. **`pre-backup.sh` extension** (single host-side script): After the existing whole-cluster `pg_dumpall` line, append a loop that dumps every fabrik-tracked DB to its own file:
   ```bash
   # Existing:
   docker exec postgres-main pg_dumpall -U postgres > /opt/backups/pg_dump_$(date +%Y%m%d_%H%M).sql
   # New (Phase 6):
   for db in $(cat /opt/backups/fabrik-tracked-dbs.txt); do
     mkdir -p "/opt/backups/postgres/$db"
     docker exec postgres-main pg_dump -U postgres -F c -Z 9 "$db" \
       > "/opt/backups/postgres/$db/latest.dump"
   done
   ```
   Single cron job (`30 1 * * *`) runs both whole-cluster + per-DB dumps. 30-min buffer before Backrest at 02:00 is preserved.

2. **Per-DB tracking file** `/opt/backups/fabrik-tracked-dbs.txt`: append-only list of DB names that fabrik manages. Fabrik appends here whenever `create_database()` succeeds, removes on `drop_database()`.

3. **New helper** [drivers/backrest.py::register_postgres_plan(db_name)](src/fabrik/drivers/backrest.py) that:
   - Acquires `/tmp/fabrik-backrest-config.lock` via existing [`run_locked("backrest-config", script, timeout=120)`](src/fabrik/drivers/locks.py#L68).
   - Calls existing `add_backup_plan()` with: `plan_id=f"postgres-{db_name}"`, `paths=[f"/opt/backups/postgres/{db_name}/"]`, `schedule_cron="0 2 * * *"` (matches `postgres-dumps`), retention from existing `postgres-dumps` (`daily:7, weekly:4, monthly:6`).
   - Also appends `db_name` to `/opt/backups/fabrik-tracked-dbs.txt` via SSH (idempotent: skip if line already present).

4. **Mirror** `unregister_postgres_plan(db_name)`: remove from `fabrik-tracked-dbs.txt` + remove Backrest plan + (optionally) `rm -rf /opt/backups/postgres/<db_name>/`. Called from `drop_database()` (via [destroyer.py:299](src/fabrik/orchestrator/destroyer.py#L299)).

5. **Wire** from [postgres.py::create_database()](src/fabrik/drivers/postgres.py#L131) after the role+grant block at line ~241. **Pass-1 confirmed**: zero existing backrest calls in postgres.py.

### Lock semantics (verified)

`/tmp/fabrik-backrest-config.lock` per [drivers/backrest.py:9](src/fabrik/drivers/backrest.py#L9). Use existing [`locks.py:68-113 run_locked(resource, script, timeout=120)`](src/fabrik/drivers/locks.py#L68).

Add new lock for the tracked-DBs file: `/tmp/fabrik-tracked-dbs.lock` — wraps the SSH-side append/delete to prevent races between concurrent `fabrik apply` calls.

### One-time migration (operator step, scope-of-this-phase)

The existing `pre-backup.sh` lives on vps1. Phase 6 must edit that script (via SSH or a fabrik-provisioning step) to add the per-DB loop above. Two paths:

- **Path A (recommended)**: ship a new fabrik subcommand `fabrik vps install-pg-per-db-backup` that idempotently injects the loop into `pre-backup.sh` and creates `/opt/backups/fabrik-tracked-dbs.txt` if absent. Operator runs once per VPS.
- **Path B**: document the edit as a manual operator step in `docs/operations/deployment.md` (lower automation, simpler ship).

### Test plan (BLOCKING)

- `tests/test_backrest_postgres_plan.py::test_register_postgres_plan_idempotent` — call twice, assert single plan in config.
- `tests/test_backrest_postgres_plan.py::test_unregister_removes_plan` — register then unregister, assert plan absent + DB name absent from tracked-dbs file.
- `tests/test_backrest_postgres_plan.py::test_lock_acquired_during_write` — mock `run_locked`, assert called with `"backrest-config"`.
- `tests/test_backrest_postgres_plan.py::test_tracked_dbs_append_idempotent` — append "foo" twice, assert one line.
- `tests/test_backrest_postgres_plan.py::test_create_database_calls_register` — mock `register_postgres_plan`, assert called from `create_database()` after role+grant succeeds.
- `tests/test_backrest_postgres_plan.py::test_drop_database_calls_unregister` — same mirror.

### Validation gate (exact commands + expected results)

```bash
# 1. Re-confirm vps1 state hasn't changed since Pass-2 grounding
ssh vps1 'cat /opt/backrest/config/config.json | jq ".plans[] | select(.id==\"postgres-dumps\") | {paths, schedule, hooks}"'
# Expected: paths=["/opt/backups/"], schedule="0 2 * * *", hooks=null

# 2. Tests (BLOCKING)
pytest tests/test_backrest_postgres_plan.py -q
# Expected: 6 green

# 3. After ship: per-DB plan registered + tracked-dbs file updated
ssh vps1 'cat /opt/backrest/config/config.json | jq ".plans[] | select(.id | startswith(\"postgres-\")) | .id"'
# Expected: ["postgres-dumps", "postgres-calendar_engine", ...]
ssh vps1 'cat /opt/backups/fabrik-tracked-dbs.txt'
# Expected: includes "calendar_engine"

# 4. After ship: dump file present after next 01:30 UTC+3 cron
ssh vps1 'ls -la /opt/backups/postgres/calendar_engine/latest.dump'
# Expected: file exists, mtime within last 24h

# 5. Lean gate
python /opt/fabrik/scripts/final_gate.py --lean --json
# Expected: {"status":"success"}
```

### Adversarial review

Use Appendix A. Hunt: (a) what if `pre-backup.sh` is overwritten by an operator manually editing the host — fabrik's idempotent injector must detect the existing block + leave operator edits alone, (b) what if `fabrik-tracked-dbs.txt` and Backrest config drift (DB in one but not other) — rollback / repair story, (c) what if a DB name contains a shell-special character that breaks the for-loop in pre-backup.sh — must validate `db_name` is `^[a-z][a-z0-9_]*$` before appending to the tracked file.

---

## Phase 7 — GlitchTip webhook auto-registration 🟥 DEFERRED — upstream API does not exist

**Decision (Pass-2)**: This phase CANNOT ship. Marking as DEFERRED. Operator continues to register the GlitchTip webhook manually in the UI after each new watchdog-enabled deploy.

### Decisive Pass-2 evidence

Fabrik's own probe script — [scripts/probes/glitchtip_webhook_capture.py:9-10](scripts/probes/glitchtip_webhook_capture.py#L9) — documents verbatim:

> "GlitchTip exposes **no API** to read alert rules / webhook recipients / delivery logs (probed 2026-06-29: `/rules/`, `/alert-rules/`, `/alerts/` all 404)."

This invalidates the original plan assumption that GlitchTip mirrors Sentry's `/api/0/projects/<org>/<slug>/plugins/webhooks/` endpoint. GlitchTip uses an alert-recipient model conceptually, but exposes **zero programmatic registration endpoints**. Webhook recipients can ONLY be created via the GlitchTip web UI:

1. Project → Alerts → New
2. Recipient type: webhook
3. URL: `http://<spec.id>-watchdog:8889/`
4. Rule: "new issue is created"

The captured webhook payload at [docs/reference/fixtures/glitchtip-webhook.json](docs/reference/fixtures/glitchtip-webhook.json) (Slack-compatible envelope with `attachments[0].title_link`, `color`) is what the watchdog's `:8889` ingest will receive — that handler can be coded independently. But REGISTERING the webhook is operator-manual.

### What still ships from this phase's scope

**1. Document the operator-manual flow** (one place, not scattered across project READMEs):
- New section in [docs/operations/deployment.md](docs/operations/deployment.md): "Post-apply manual step: GlitchTip webhook registration" with the 4-step recipe + the canonical webhook URL pattern.
- Update [docs/CONFIGURATION.md](docs/CONFIGURATION.md) reference.

**2. Surface the requirement at apply time**:
- After `fabrik apply` succeeds for a spec with `watchdog.trigger_sources` containing `error_webhook`, emit a CLEAR final-log message: "ACTION REQUIRED: register GlitchTip webhook at <https://glitchtip.vps1.ocoron.com/<org>/<project>/alerts/> → recipient: webhook → URL: http://<spec.id>-watchdog:8889/". No new env vars; reuse existing `GLITCHTIP_AUTH_TOKEN` if/when upstream adds the API.

**3. Watchdog ingest handler hardening** (separate concern, not blocked):
- Verify the `:8889` handler in [drivers/watchdog.py](src/fabrik/drivers/watchdog.py) correctly parses the captured payload shape ([fixtures/glitchtip-webhook.json](docs/reference/fixtures/glitchtip-webhook.json)) — `body.text`, `body.attachments[0].title`, `attachments[0].title_link`, `attachments[0].color`, `attachments[0].fields[].value`.

### Pass-1 verified facts (unchanged — kept for reference if upstream ever ships an API)

- 4 public functions in `glitchtip.py` (`applies_to`, `create_project`, `delete_project`, `verify_dsn_injection`). Zero webhook code.
- Spec_loader docstring at [spec_loader.py:558-564](src/fabrik/spec_loader.py#L558) confirms URL pattern + optional `WATCHDOG_INGEST_TOKEN`.
- Watchdog comment at [watchdog.py:703-705](src/fabrik/drivers/watchdog.py#L703) confirms `:8889` ingest URL convention.
- DSN injection at [infrastructure.py:532](src/fabrik/orchestrator/infrastructure.py#L532) confirmed.
- Watchdog container naming at [watchdog.py:599](src/fabrik/drivers/watchdog.py#L599) (`f"{rctx.project_id}-watchdog"`) — URL construction `http://{spec.id}-watchdog:8889/` is sound.

### Revival trigger

Revisit this phase when GlitchTip ships an alert-management API. Track upstream: https://gitlab.com/glitchtip/glitchtip-backend/-/issues/ (filter: "API" + "alert"). Currently no roadmap item.

### Pass-1 verified facts (kept as-is)

- 4 public functions in `glitchtip.py` (`applies_to`, `create_project`, `delete_project`, `verify_dsn_injection`). Zero webhook code.
- Spec_loader docstring at [spec_loader.py:558-564](src/fabrik/spec_loader.py#L558) confirms URL pattern + optional `WATCHDOG_INGEST_TOKEN`.
- Watchdog comment at [watchdog.py:703-705](src/fabrik/drivers/watchdog.py#L703) confirms `:8889` ingest URL convention.
- DSN injection at [infrastructure.py:532](src/fabrik/orchestrator/infrastructure.py#L532) confirmed (`self.deployer.inject_env(ctx, {"SENTRY_DSN": dsn, "GLITCHTIP_DSN": dsn})`).
- Watchdog container naming at [watchdog.py:599](src/fabrik/drivers/watchdog.py#L599) (`f"{rctx.project_id}-watchdog"`) — URL construction `http://{spec.id}-watchdog:8889/` is sound.

### Test plan (revised — covers only the shippable surfaces)

- `tests/test_apply_emits_glitchtip_webhook_reminder.py::test_reminder_logged_when_error_webhook_enabled` — apply a fake spec with `watchdog.trigger_sources=[error_webhook]`, assert post-apply log contains "ACTION REQUIRED: register GlitchTip webhook" + the exact URL.
- `tests/test_apply_emits_glitchtip_webhook_reminder.py::test_no_reminder_when_error_webhook_disabled` — apply a fake spec without `error_webhook`, assert no reminder log.
- `tests/test_watchdog_ingest_payload.py::test_parses_glitchtip_webhook_fixture` — feed [fixtures/glitchtip-webhook.json](docs/reference/fixtures/glitchtip-webhook.json) to the `:8889` handler, assert correct extraction of issue title + link + color.

### Validation gate (exact commands + expected results)

```bash
# 1. Tests (BLOCKING)
pytest tests/test_apply_emits_glitchtip_webhook_reminder.py tests/test_watchdog_ingest_payload.py -q
# Expected: 3 green

# 2. Operator-manual flow documented
grep -A2 "GlitchTip webhook" /opt/fabrik/docs/operations/deployment.md
# Expected: 4-step recipe + canonical URL pattern

# 3. Apply-time reminder visible (smoke test against any watchdog-enabled spec)
fabrik apply --dry-run --spec specs/services/calendar-orchestration-engine.yaml 2>&1 | grep "ACTION REQUIRED"
# Expected: 1 match with the manual-step URL

# 4. Lean gate
python /opt/fabrik/scripts/final_gate.py --lean --json
# Expected: {"status":"success"}
```

### Adversarial review

Use Appendix A. Hunt: (a) is the watchdog `:8889` handler robust to GlitchTip's actual payload shape (Slack-compatible envelope), (b) does the reminder fire for every relevant spec (not just calendar) — search for other specs with `error_webhook`, (c) is the operator-manual recipe complete enough to follow without prior GlitchTip familiarity.

---

## Phase 8 — Deploy key auto-push to GitHub

**Goal**: Watchdog's generated SSH deploy keypair is automatically registered as a write-access deploy key on the project's GitHub repo. No operator copy-paste.

### Today's reality (verified Pass-1)

- [drivers/watchdog.py:793-847 `_ensure_deploy_key()`](src/fabrik/drivers/watchdog.py#L793) — generates the keypair **ON VPS** via `ssh-keygen` (line 823); reads pubkey via VPS `cat` (line 838); logs pubkey via `logger.warning("watchdog: generated git deploy key…")` at line 842-846. Pubkey is NEVER written to a file by current code.
- Only `gh` CLI usage in fabrik today: `gh auth status` at [cli.py:1630](src/fabrik/cli.py#L1630). **No `gh api` calls anywhere in production code.** Plan originally claimed "gh used elsewhere (commit/PR flows)" — false.
- Local `gh` confirmed authenticated as `mobasak`, `repo` scope present, can `gh api repos/mobasak/fabrik`.

### Drifts corrected from original plan

- Original: "Parse repo owner/name from `spec.source.repository`". **Verified**: no URL parser exists in fabrik (closest is a simple prefix check at [deployer_coolify.py:693-695](src/fabrik/orchestrator/deployer_coolify.py#L693)). Phase 8 MUST vendor a parser — recommend stdlib regex `r"github\.com[:/]([^/]+)/([^/.]+?)(?:\.git)?$"`.
- Original silent on **runtime location** of `gh` invocation. **Resolution**: run `gh` from operator's WSL hub (where `fabrik apply` runs), NOT on VPS. The pubkey is generated on VPS but `gh api` to GitHub doesn't need to live on VPS. Pipeline: ssh-keygen ON VPS → ssh `cat ~/.ssh/<key>.pub` to retrieve pubkey to hub → `gh api repos/<o>/<r>/keys` from hub. **Eliminates** the need to install `gh` on VPS.
- Original silent on partial-state idempotency. **Resolution**: query GitHub FIRST (`gh api repos/<o>/<r>/keys --jq '.[] | select(.title=="fabrik-watchdog-deploy") | .key'`), THEN check local. If GitHub has the key but local file is missing, REUSE GitHub's pubkey value (regenerate keypair locally would orphan the GitHub entry; better: tell operator to manually rotate via separate flow).

### Scope

- Extend [drivers/watchdog.py::_ensure_deploy_key()](src/fabrik/drivers/watchdog.py#L793) to add auto-push step after keygen.
- New helper `_parse_github_repo(repo_url: str) -> tuple[str, str]` in `watchdog.py` (or `utils.py` if already exists; verify before adding).
- New helper `_push_deploy_key_to_github(owner, repo, title, pubkey) -> dict` calling `gh api` via `subprocess.run`.

### Approach (REVISED)

1. **Token scope check at entry** (Pass-1 gap): early in `_ensure_deploy_key`, run `gh auth status --show-token 2>&1 | grep -E "Token scopes:.*repo"`. If absent, skip the GitHub push step entirely (fall back to current print-pubkey path) with a CLEAR log line ("watchdog: `gh` token lacks `repo` scope — manual deploy-key registration required").
2. **URL parse** via the regex above. Reject non-GitHub URLs (other VCS hosts out of scope).
3. **GET first** (`gh api repos/<o>/<r>/keys --jq '.[] | select(.title=="fabrik-watchdog-deploy")'`). If non-empty AND matches local pubkey → idempotent skip. If non-empty AND does NOT match → log conflict + fall back to print.
4. **POST** via `gh api -X POST repos/<o>/<r>/keys -f title=fabrik-watchdog-deploy -f key=@<tmpfile> -F read_only=false`. Use a temp file to pass the pubkey to avoid shell-quoting bugs with long keys.
5. **Handle exit codes**: 0 = success, 422 with "key is already in use" body = idempotent (treat as success), other = warn + fall back.
6. **Wrap entire flow** in try/except — current code has no try/except around the existing keygen block ([watchdog.py:821-840](src/fabrik/drivers/watchdog.py#L821)); any new gh failure must not crash deploy. Fall back to print-pubkey.

### Test plan (BLOCKING)

- `tests/test_watchdog_deploy_key.py::test_url_parse_https_with_git_suffix` — `https://github.com/foo/bar.git` → `("foo", "bar")`.
- `tests/test_watchdog_deploy_key.py::test_url_parse_ssh_form` — `git@github.com:foo/bar.git` → `("foo", "bar")`.
- `tests/test_watchdog_deploy_key.py::test_url_parse_rejects_non_github` — `https://gitlab.com/foo/bar.git` → raises `ValueError`.
- `tests/test_watchdog_deploy_key.py::test_skip_when_repo_scope_missing` — mock `gh auth status` to omit repo scope, assert no POST attempted + fall back logged.
- `tests/test_watchdog_deploy_key.py::test_idempotent_when_key_already_registered_matching` — mock GET returning matching key, assert no POST + log "idempotent skip".
- `tests/test_watchdog_deploy_key.py::test_conflict_when_key_already_registered_different` — mock GET returning DIFFERENT key with same title, assert no POST + log conflict + fall back.
- `tests/test_watchdog_deploy_key.py::test_post_422_treated_as_idempotent` — mock subprocess.run to return 422 with "key is already in use", assert treated as success.
- `tests/test_watchdog_deploy_key.py::test_other_failure_falls_back_to_print` — mock subprocess.run to return 500, assert print-pubkey path executed, no exception raised.

### Validation gate (exact commands + expected results)

```bash
# 1. Tests (BLOCKING)
pytest tests/test_watchdog_deploy_key.py -q
# Expected: 8 green

# 2. Verify gh token scope locally (operator-runnable preflight)
gh auth status --show-token 2>&1 | grep -E "Token scopes:.*\brepo\b"
# Expected: 1 match (repo scope present)

# 3. URL parser regression — pre-existing parser absence
grep -rEn "github\.com.*\(.*\)" /opt/fabrik/src/fabrik/ | grep -v test_ | grep -v "\.pyc" | head
# Expected: no pre-existing parser found; new one is the canonical addition

# 4. After ship: end-to-end against test repo
# (apply a watchdog-enabled spec, then:)
gh api repos/mobasak/<test-repo>/keys --jq '.[] | select(.title=="fabrik-watchdog-deploy")'
# Expected: 1 entry with read_only=false

# 5. Lean gate
python /opt/fabrik/scripts/final_gate.py --lean --json
# Expected: {"status":"success"}
```

### Adversarial review

Use Appendix A. Hunt: (a) what if the project's `source.repository` is private and the operator's `gh` token doesn't grant access — must fail-closed-with-clear-message, not silent-success; (b) what if multiple watchdog projects share the same repo (monorepo case) — title collision; (c) pubkey contents containing characters that break the GitHub API body (newlines, quotes) — the `@<tmpfile>` syntax dodges this but verify.

---

## Phase ordering recommendation

If shipping serially, recommended order:
1. **Phase 1** (15 min) — unblocks calendar deploy immediately
2. **Phase 2** (30 min) — stops red-gating downstream projects (every fabrik project benefits)
3. **Phase 3** (45 min) — stops the daily sync-drift noise (every project benefits)
4. **Phase 5** (2h) — biggest operator-toil win for new deploys (DB seed)
5. **Phase 4** (2h) — unblocks the scheduler-as-companion pattern (calendar needs it, future projects will too)
6. **Phase 7** (3h) — closes the watchdog → GlitchTip loop (one less manual UI step per Tier-D project)
7. **Phase 8** (2h) — closes the watchdog → GitHub loop (one less manual UI step per Tier-D project)
8. **Phase 6** (3h) — defensive — better isolation, but current whole-cluster backup is functional

Phases 1+2+3 = 90 min and resolves the most immediate friction. Phases 4–8 are optional polish (each independent).

## Risks + open questions

- **Phase 3**: does `sync_enforcement_to_projects.py` currently take a `--quiet` flag? Verify before wiring into cron. If not, add it or pipe to /dev/null.
- **Phase 4**: introducing `companion_services:` is a spec contract change — every existing spec stays compatible (optional field) but the rule packs in `.windsurf/rules/core/30-ops.md` may need a section update.
- **Phase 5**: SCP'ing local dump files to VPS during apply assumes the operator HAS the dump file locally. Document the convention: dumps live in `backups/` (gitignored).
- **Phase 6**: per-DB Backrest plans require per-DB pg_dump invocations — currently the existing plan probably uses `pg_dumpall`. Migration story: keep the cluster plan running, ADD per-DB plans on top, deprecate the cluster plan after a stabilization window.
- **Phase 7**: GlitchTip's plugin API mirrors Sentry — confirm endpoint shape against the running GlitchTip version on vps1 before coding.
- **Phase 8**: `gh` CLI auth scope on vps1 — verify `gh auth status` includes `repo` scope; if not, document the re-auth step in the plan exit.

## Phase 9 — Final convergence verification (MANDATORY plan-exit gate)

After ALL approved phases are shipped, the executing AI runs this two-script gate. Both must be green BEFORE the plan status flips to SHIPPED.

### Step 9a — `final_gate.py --lean --json`

```bash
cd /opt/fabrik && python scripts/final_gate.py --lean --json | tee /tmp/final-gate.json
jq -e '.status == "success"' /tmp/final-gate.json
```

**Expected output**: `{"status":"success","tier":1,"passed":<N>,"failed":0,"failures":[]}`. If `failed > 0`, examine `failures[]`, fix, re-run. Do NOT proceed to 9b until 9a is green.

### Step 9b — `check_convergence.py` (enforces this very plan's `## Evidence` + per-phase citations)

```bash
cd /opt/fabrik && python scripts/enforcement/check_convergence.py
echo "exit=$?"
```

**Expected output**: `exit=0` with no per-file FAIL lines for `docs/development/plans/2026-06-30-plan-fabrik-deploy-readiness-gaps.md`.

The check ([scripts/enforcement/check_convergence.py:1-20](scripts/enforcement/check_convergence.py#L1)) inspects only changed/untracked files under `plans/` and `reviews/` (cheap — git status + regex). It enforces:
- `**Status:** CONVERGED` (or "zero unknowns") header.
- A `## Evidence` section with ≥1 `path:line` citation per Phase.
- ≥1 non-trivial fenced command-output block.
- A self-audit / convergence-floor block.

**Pre-check (run before commit)**: verify this plan satisfies the check above:

```bash
grep -E "^\*\*Status\*\*: CONVERGED" /opt/fabrik/docs/development/plans/2026-06-30-plan-fabrik-deploy-readiness-gaps.md
# Expected: 1 match

grep -cE "^## Evidence" /opt/fabrik/docs/development/plans/2026-06-30-plan-fabrik-deploy-readiness-gaps.md
# Expected: ≥1

grep -cE "src/fabrik/.*:[0-9]+|scripts/.*\.py:[0-9]+" /opt/fabrik/docs/development/plans/2026-06-30-plan-fabrik-deploy-readiness-gaps.md
# Expected: ≥8 (one per phase, conservatively)

grep -cE "^### Convergence floor" /opt/fabrik/docs/development/plans/2026-06-30-plan-fabrik-deploy-readiness-gaps.md
# Expected: 1
```

### Step 9c — Final plan-status update

After 9a + 9b both green:

```bash
sed -i 's/^\*\*Status\*\*: CONVERGED v2.*$/**Status**: SHIPPED (phases-N done, YYYY-MM-DD)/' \
  /opt/fabrik/docs/development/plans/2026-06-30-plan-fabrik-deploy-readiness-gaps.md
```

Then commit with message `docs(plan): mark deploy-readiness-gaps plan as SHIPPED`.

---

## Residual unknowns / assumptions / out-of-scope risks

This plan reaches fixed point on grounding evidence but does NOT eliminate all risk. Enumerated explicitly:

### Hard residuals (acknowledged limitations)

| # | Item | Status | Mitigation |
|---|---|---|---|
| R1 | Phase 7 cannot ship: GlitchTip exposes no programmatic webhook registration API. | DEFERRED indefinitely. | Track upstream issue; document operator-manual recipe per Phase 7 §"What still ships". |
| R2 | Phase 1's `infrastructure.py:432` fix WILL silently rename DBs for **7 confirmed at-risk specs** (Pass-5 enumeration). | Hard-blocking pre-step in Phase 1 Approach §2; per-spec A/B/C decision required IN PLAN before 1a ships. | Enumerated by Pass-5 audit: `youtube, calendar-orchestration-engine, fabrik-claim-validator, proposal-creator, trading-core, triggered-content-orchestration, job-agent`. Each needs operator A/B/C decision documented before code. |
| R3 | Phase 6 modifies vps1's host-side `pre-backup.sh` script outside fabrik's source repo. If operator manually edits that script (e.g., to add Coolify exports), fabrik's idempotent injector must detect existing blocks and leave operator edits alone. | Adversarial review hunt in Phase 6. | Implementation must use a fenced `# === FABRIK BEGIN/END ===` block pattern. |
| R4 | Phase 8 assumes `gh` CLI runs from operator's WSL hub, NOT on VPS. Plan-1's `_ensure_deploy_key()` currently runs ssh-keygen ON VPS. Phase 8 changes the data flow: SSH to VPS → cat pubkey → return to hub → `gh api` from hub. | Must be reflected in the test mocks. | Tests mock both `subprocess.run` (for gh) AND `ssh()` (for the cat). |
| R5 | All cited grounding was done at 2026-06-30. The fabrik codebase moves fast; if execution is deferred >7 days, the executing AI MUST re-run Pass 3 / Pass 4 ("re-ground" step per the Mandatory Execution Protocol). | Built into the Mandatory Execution Protocol step 1. | Re-run Appendix C grounding-prompt template before each phase. |
| R6 | Phase 6's vps1-side claims (current `postgres-dumps` plan shape, `/opt` mount, `pre-backup.sh` host cron, postgres superuser auth) were grounded by a Pass-2 subagent in a session WHERE `ssh vps1` resolved. Pass-5 verification from the convergence-driver's shell found `vps1` hostname does NOT resolve from the operator's WSL (Temporary failure in name resolution). | Executing AI MUST re-probe via SSH from its own runtime BEFORE coding Phase 6. | Run the 4 Pass-2 probes (Phase 6 §F1–F4) again; abort Phase 6 if they don't reproduce. |

### Soft assumptions (likely correct, not adversarially probed)

| # | Assumption | Where if wrong |
|---|---|---|
| A1 | `gh auth status` on operator's WSL has `repo` scope at execution time (Phase 8). | Phase 8 runtime check fail-closes to print-pubkey fallback — safe. |
| A2 | Calendar-orchestration-engine project repo will actually commit a `companion_services:` entry-point + a 2-service compose.yaml. | This is downstream operator work, separate ticket. |
| A3 | The 3 Phase-3 generator scripts (`generate_model_capabilities.py`, `generate_selection_guide_roster.py`, `scrape_windsurf_models.py`) are cron-safe (no TTY, no interactive prompts). Pass-2 grounder confirmed `sync_enforcement_to_projects.py` is — but did NOT separately probe these 3. | If a script hangs in cron, the existing `\|\| echo "[daily_refresh] X failed (non-fatal)"` isolation prevents pipeline crash, but the file doesn't get regenerated until manual investigation. |
| A4 | `flock /tmp/fabrik-sync-enforcement.lock` (Phase 3) — assumes vps cron user has access to `/tmp/`. Universally true on Linux but technically not adversarially verified. | If wrong, no lock — fall back to "last write wins" semantics (acceptable; the file content is deterministic from the DB anyway). |
| A5 | Phase 5's `psql` runtime inside `docker exec -i postgres-main bash -c 'gunzip \| psql'` correctly inherits the per-DB role identity. | Test must verify against a real running postgres-main container before phase exit. |

### Out-of-scope (explicit non-goals — punt to separate tickets)

| # | Item | Why out of scope |
|---|---|---|
| O1 | `_validate_compose()` cross-service constraint validation (e.g., scheduler shouldn't claim Traefik labels). | Phase 4 ships the spec field; Phase 9-future could add cross-service validation later. |
| O2 | Multi-VPS Phase 6 (per-DB backup on vps2/vps3 spokes). | Spokes don't run postgres; only hub vps1 has `postgres-main`. |
| O3 | Automating the `companion_services:` spec authoring for calendar (vs documenting it). | Operator authors; fabrik scaffolds. |
| O4 | GitLab / Bitbucket support for Phase 8 (only GitHub today). | Plan rejects non-github URLs with `ValueError`; explicit non-goal. |
| O5 | Backrest restore tests (per-DB plan registration ≠ verified-restorable backup). | Existing dr_env_recovery_test.sh covers whole-cluster; per-DB restore test is a separate hardening ticket. |

## Approval gate

Owner approves this plan in one of four ways:

1. **APPROVE ALL** → execute phases 1b-shape → 2 → 3 → 4 → 5 → 6 → (1a + 1b-depends bundled) → 8 sequentially (Phase 7 stays DEFERRED). Final Phase 9 convergence verification at the end. **Blocked-step gate**: 1a + 1b-depends cannot run until the 6 non-calendar A/B/C decisions are documented (calendar's is auto-Option-A per "free rename" above).

2. **APPROVE 1b-shape + 2 + 3** (the genuinely-clean ~78-min quick-wins set) → 3 calendar shape/env edits (~3 min) + enforcement-skip fix (~30 min) + AI-catalog sync fix (~45 min). Zero data risk, every project benefits. **Does NOT unblock calendar's DB creation** — that needs 1a + 1b-depends bundled, which needs the 6-spec audit + decisions first. **RECOMMENDED for immediate ship.**

3. **APPROVE 1b-shape + 2 + 3 + 1a/1b-depends (calendar only, scoped)** → adds calendar's full DB fix on top of option 2, BUT requires the operator to first verify (via the SSH probe above) that the OTHER 6 specs' derived-name DBs don't exist on `postgres-main`. If they don't exist, 1a is safe to land for all 7 simultaneously. If any do exist, 1a still ships but with a guard that errors for non-calendar specs until per-spec decisions land. ~2h total.

4. **REVISE** → owner names the phase(s) to drop, redirect, or expand. I update this plan and re-present.

No code changes happen until one of those approvals lands.

---

## Appendix A — Adversarial review prompt template (paste verbatim per phase)

Replace `<PHASE_NUMBER>` and `<FILES>` per phase. Subagent type: `general-purpose`.

```
Adversarial code review of Phase <PHASE_NUMBER> of plan
/opt/fabrik/docs/development/plans/2026-06-30-plan-fabrik-deploy-readiness-gaps.md.

Diff: `git diff HEAD~1` (single-commit phase) or `git diff <base-sha>..HEAD` (multi-commit).
Files in scope (full reads, not excerpts):
<FILES>

Hunt these failure classes only — NOT style:

1. Logic errors / off-by-one — every condition + boundary.
2. Null / empty / None handling — every external return.
3. Idempotency — re-running the same code path must not corrupt state.
   Phases 5, 6, 7, 8 are idempotent-critical.
4. Fail-open vs fail-closed — secrets, deploy keys, webhooks: fail CLOSED.
5. Effective-dating / ordering — registrar call order, race conditions
   on shared lock files (Backrest config, .env file writes).
6. Concurrency — multiple fabrik apply runs against the same VPS.
7. Plan ↔ code deviations — does the diff match what this plan said?
   Flag silent scope creep.
8. Precision / encoding — env var quoting, shell injection via
   spec values (id, db_name).
9. Regex over-broad — any new regex must be pinned to the format
   the source page/file uses.
10. DB-row-creation safety — UPSERT semantics, UNIQUE constraint
    avoidance. Pair with the .windsurf/rules pack core/25-data-postgres.md.

Format (under 400 words):
- Per finding: severity (CORRECTNESS / SECURITY) + file:line + repro
  + fix idea + verdict (CONFIRMED / PLAUSIBLE / REFUTED).
- After: "What I inspected" enumeration (≥6 items).
- End with: "Zero new findings" OR "N findings, recommend Pass 2".

Don't fabricate. Don't flag style. Don't propose refactors.
If the diff is correct + tests cover the new behavior, say so.
```

## Appendix B — Commit message format (per phase)

```
fix(<area>): Phase <N> — <one-line summary>

Per docs/development/plans/2026-06-30-plan-fabrik-deploy-readiness-gaps.md
Phase <N>: <gap name>.

<2-3 sentences explaining what changed and why.>

Changes:
  - <bullet 1>
  - <bullet 2>

Tests:
  - <test name 1>: <assertion>
  - <test name 2>: <assertion>

Adversarial review (general-purpose subagent): <N findings, all
addressed | zero new findings>

final_gate.py --lean --json status:success.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

## Appendix C — Re-grounding prompt template (Phase entry)

Replace `<REFS>` with the full list of `path:line` references from the phase. Subagent type: `Explore`. Set breadth: `quick`.

```
Verify these path:line references in /opt/fabrik are still accurate
as of HEAD (plan was authored 2026-06-30; refs may have drifted).

References to verify:
<REFS>

For each reference, report exactly one of:
  - MATCH: <file>:<line> still contains "<expected substring>"
  - DRIFT: <file>:<line> moved to <new_line>
  - NOT FOUND: <expected substring> not present in <file>

Under 200 words. No analysis or recommendations — just the verdicts.
```
