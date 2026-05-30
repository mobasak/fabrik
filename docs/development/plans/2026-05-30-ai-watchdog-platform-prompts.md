# Watchdog Platform — Phase Prompts (P1 – P5)

Copy-paste the prompt for the current phase into Claude. Each prompt embeds discipline against shallow / hallucinated work and forces sub-plan → review → code-by-artifact cadence.

Companion to: `docs/development/plans/2026-05-30-ai-watchdog-platform.md` (the plan).

---

## Meta-rules (apply to every phase)

These are quoted into each per-phase prompt below. If you start a fresh session, paste this block first:

```
META-RULES — apply to every step until I say otherwise:

1. NO ASSUMPTIONS, NO HALLUCINATIONS. Before citing any command, file, symbol,
   library API, or schema field — run grep / ls / cat / <tool> --help / Read
   first, and paste the evidence in your response. If you cannot verify, say
   "I cannot verify X" and stop — do not guess.

2. READ BEFORE WRITE. Open every file I name (with the Read tool) before writing
   anything that references it. Cite line numbers when referencing existing code
   (e.g., src/fabrik/spec_loader.py:218).

3. ONE ARTIFACT PER TURN. After each artifact, self-review it against the
   acceptance criteria I named, then STOP and show me. Do not start the next
   artifact until I say go.

4. SCOPE DISCIPLINE. Do only what I asked. If you find adjacent issues, flag
   them in a "Side findings" block but do NOT fix without approval.

5. SUB-PLAN FIRST, CODE SECOND. When I ask for a sub-plan, write the sub-plan
   only; do not write any code. When I approve, code begins.

6. WHEN YOU FAIL A VERIFICATION, SAY SO. "fabrik sync-rules does not exist in
   `fabrik --help` output" is the right shape. Do not paper over.

7. AT THE END OF EACH RESPONSE, name the file paths you touched with line
   counts and a one-sentence summary of what changed. No epic recaps.
```

---

## P1 — Foundations (3–4 days)

**Deliverables:** `fabrik-lib/app-audit-log/` + `fabrik-lib/cost-budget/` + `core/app-audit-log.md` + `core/cost-budget.md` + `postgres` driver migration creating shared `cost_ledger` table.

### P1.A — Sub-plan prompt

```
[Paste META-RULES first]

P1 — Foundations: write the SUB-PLAN only. Do not code anything yet.

Read first (verify they exist with Read):
- /opt/fabrik/docs/development/plans/2026-05-30-ai-watchdog-platform.md
  (the plan we're executing — focus on § Locked decisions and the artifact
  table for items 1, 2, 5, 6 of the net-new list)
- /opt/fabrik-lib/README.md (module convention + "Which Modules Do I Need?"
  matrix — your additions must follow this style)
- /opt/fabrik-lib/gdpr-data-rights/README.md
- /opt/fabrik-lib/gdpr-data-rights/schema.sql
- /opt/fabrik-lib/gdpr-data-rights/data_retention.sql
- /opt/fabrik-lib/abuse-prevention/README.md
- /opt/fabrik-lib/abuse-prevention/requirements.txt
- /opt/fabrik-lib/abuse-prevention/abuse_detection.py (skim — for code style)
- /opt/fabrik/src/fabrik/drivers/postgres.py (full read — you will edit this
  to add the cost_ledger migration; understand its current shape and migration
  conventions)
- /opt/fabrik/src/fabrik/orchestrator/infrastructure.py (lines 1–150 — to see
  the registrar function pattern and _REGISTRAR_ORDER)

Verify (do not assume — run these and paste output):
- Does `postgres-main` container already enforce its schema migration via a
  Fabrik-driven mechanism? Find it; cite the file:line.
- Does fabrik-lib have a precedent for vendoring a module that uses the SHARED
  postgres-main vs the project's own database? If yes, reference it. If no,
  state "no precedent — this is a new pattern."
- What Python DB driver convention does abuse-prevention assume (psycopg2 vs
  psycopg 3 vs asyncpg)? Cite the requirements.txt line.

Write a SUB-PLAN covering:

1. app-audit-log/ module — file list:
   - schema.sql: full DDL for the audit_log table (columns, types, defaults,
     constraints, indexes). Include both prev_hash and current_hash columns
     (A2 decision; non-breaking upgrade path to A1). Specify the hash algorithm
     (SHA-256 over which exact concatenation), retention partitioning scheme
     (monthly), and any helper view for chain verification.
   - audit_log.py: function signatures for record_event(), verify_chain(),
     query_events(). No implementation yet — signatures + docstrings only.
     Specify the DB-API connection style (match abuse-prevention's convention).
   - data_retention.sql: partition rollover + 12-month retention. Specify whether
     this uses pg_cron OR app-level scheduling (verify pg_cron availability first;
     if unverified, default to app-level + flag).
   - requirements.txt: list explicit deps (likely none — DB conn passed in).
   - README.md: outline matching gdpr-data-rights style (Title / Purpose /
     What's included table / Vendor it / Configuration table / Compliance
     checklist).

2. cost-budget/ module — file list:
   - schema.sql: cost_ledger DDL exactly as in plan v2 § Locked decisions B2
     (uuid7 primary key, project_id, ts, provider, model, in_tokens, out_tokens,
     cost_usd, incident_id, action_id, plus the two indexes).
   - cost_budget.py: function signatures for record_cost(), check_caps(),
     drop_to_rule_only_mode(). Cap-enforcement algorithm spelled out (which
     queries run, how often, what triggers kill-switch).
   - wal.py: local SQLite write-ahead buffer schema + replay logic shape.
     Specify SQLite schema, replay batch size, failure handling.
   - requirements.txt: explicit deps.
   - README.md: outline matching the same convention.

3. core/app-audit-log.md rule pack — section outline (no content yet):
   - When to use audit log
   - What events to log (auth, billing, admin, data export, watchdog actions)
     — full enumerated list
   - Retention policy
   - Hash-chain verification on read
   - Anti-patterns (what NOT to log here)

4. core/cost-budget.md rule pack — section outline:
   - When to use cost-budget
   - Budget setting per project (per-product cap, per-task soft cap)
   - Tiered model selection ladder (cheap → expensive)
   - Kill-switch semantics (drop to rule-only mode)
   - Cost-per-success metric

5. postgres driver migration wire-in:
   - Exact file (/opt/fabrik/src/fabrik/drivers/postgres.py) and approximate
     function/place where the cost_ledger CREATE TABLE goes
   - Idempotency mechanism (CREATE TABLE IF NOT EXISTS is fine; what about
     index creation — same pattern?)
   - Whether this requires changes to _REGISTRAR_ORDER (probably not — postgres
     already runs first)

6. Acceptance criteria for P1 (lifted from plan v2):
   - Both modules vendor cleanly into a test project
   - cost_ledger table created by postgres registrar on first apply
   - WAL replay verified on Postgres outage simulation (define the test:
     docker stop postgres-main; sidecar emits N cost rows; docker start
     postgres-main; assert WAL drains within 30s; assert no rows lost)
   - READMEs match fabrik-lib/README.md convention
   - Rule packs lint-pass (markdownlint, with the same MD060/MD032 rules
     we've fought before)

7. Order of artifacts to code (after sub-plan approval):
   - app-audit-log/schema.sql (smallest, leaf, no deps)
   - app-audit-log/data_retention.sql
   - app-audit-log/audit_log.py
   - app-audit-log/requirements.txt + README.md
   - cost-budget/schema.sql
   - cost-budget/wal.py
   - cost-budget/cost_budget.py
   - cost-budget/requirements.txt + README.md
   - core/app-audit-log.md
   - core/cost-budget.md
   - postgres driver migration wire-in
   - Update /opt/fabrik-lib/README.md modules table + matrix

8. Side findings: anything you noticed during the reads that's worth flagging
   for a separate task (not for this phase).

Show me the sub-plan. Do not code.
```

### P1.B — Code prompt (per artifact, after sub-plan approval)

```
P1 sub-plan approved. Code ONE artifact: <name from order list>.

Constraints:
- Match the conventions you verified during the sub-plan.
- Self-review against the acceptance criteria after writing.
- After writing + self-review, STOP. Show me the file and your self-review.
  Do not start the next artifact.
- If you find that the sub-plan was wrong about something, STOP and tell me;
  do not silently improvise.
```

---

## P2 — Watchdog core (6–8 days)

**Deliverables:** `fabrik-lib/watchdog/sidecar/` + `fabrik-lib/watchdog/emitter/` + `core/watchdog.md` + `WatchdogConfig` spec field + `_register_watchdog()` orchestrator function + `src/fabrik/drivers/watchdog.py`.

### P2.A — Sub-plan prompt

```
[Paste META-RULES if fresh session]

P2 — Watchdog core: write the SUB-PLAN only. Do not code anything yet.

Read first (verify each):
- /opt/fabrik/docs/development/plans/2026-05-30-ai-watchdog-platform.md
  (focus on § Watchdog architecture and § Claude Code permission boundaries)
- /opt/fabrik/src/fabrik/drivers/gatus.py (full — your driver template at 283 lines)
- /opt/fabrik/src/fabrik/drivers/glitchtip.py (skim — second template at 467 lines)
- /opt/fabrik/src/fabrik/orchestrator/infrastructure.py (full read — you will
  add _register_watchdog() here; understand the dispatcher dispatch + applicability
  patterns)
- /opt/fabrik/src/fabrik/spec_loader.py:18-340 (Kind enum, Shape model — the
  WatchdogConfig you add lives at the same top-level depth as Shape)
- /opt/fabrik-lib/pause-state/pause_state.py (skim — your Tier A pause action
  uses this directly)
- /opt/fabrik-lib/async-http-client/circuit_breaker.py (skim — your OpenRouter
  fallback chain reuses this)
- The completed P1 modules (app-audit-log + cost-budget — your sidecar depends
  on these; verify the signatures you'll call)

Verify (do not assume — run these and paste output or evidence):
- `claude --help` and `claude -p --help` (confirm the exact flag spellings:
  --bare, --permission-mode, --settings, --allowedTools, --output-format,
  --append-system-prompt — and whether they accept the values you plan to pass)
- Does the host's Claude Code config live at ~/.claude/ — confirm path on the
  VPS (or wherever the sidecar will read it from)
- Docker compose project label syntax: `docker inspect --format
  '{{.Config.Labels}}' <some-container>` — confirm the label key
  (`com.docker.compose.project` or `com.docker.compose.project=<name>`)
- The exact Apprise notification mechanism wired today: cite the file:line in
  fabrik that sends an Apprise alert. If not wired, say so.
- What's the existing pattern for fabrik to register a per-project env var
  channel (like Apprise endpoint URL) — cite the file:line.

Write a SUB-PLAN covering:

1. WatchdogConfig Pydantic class (lives where in spec_loader.py — give
   line-of-insertion):
   - Every field: name, type (with Pydantic validators), default, description
   - The conditional default-by-kind logic (kind: service|worker|wordpress
     defaults enabled=true; kind: static defaults enabled=false)
   - Validator: if enabled=true, daily_budget_usd must be > 0 OR
     daily_invocations_cap must be > 0

2. _register_watchdog() function in src/fabrik/orchestrator/infrastructure.py:
   - Full signature (matching gatus/glitchtip patterns you read)
   - Applicability logic (defer to WatchdogConfig.enabled + spec.shape.kind)
   - Position in _REGISTRAR_ORDER (must run AFTER postgres so cost_ledger
     exists, AFTER prometheus so /metrics endpoint registered; confirm order)
   - What it dispatches to (the driver function)

3. src/fabrik/drivers/watchdog.py:
   - Function-level outline matching gatus.py shape
   - At fabrik apply: inject sidecar service block into project's compose.yaml;
     wire WATCHDOG_* env vars; create per-project watchdog directory at
     /opt/<project>/watchdog/ on VPS via SSH; deploy
     /etc/watchdog/claude-settings.json (project-specific, templated from the
     shape in plan v2)
   - At fabrik destroy: remove sidecar from compose; sudo rm -rf
     /opt/<project>/watchdog/
   - Idempotency: subsequent apply with same config is a no-op
   - Estimated line count

4. fabrik-lib/watchdog/sidecar/ contents:
   - Dockerfile: base image (python:3.13-slim-bookworm — verify; NO Alpine per
     rule pack), non-root UID, mount points (claude config, docker.sock, project
     volume), CMD
   - agent.py: state-machine outline (idle → check → anomaly detected →
     reasoning → action → audit log → cost ledger → idle). Pseudocode, no
     implementation.
   - llm_client.py: Claude Code subprocess invocation + OpenRouter fallback +
     tiered model selection. Pseudocode.
   - actions.py: Tier A action handlers (restart_container, clear_file_cache,
     scale_concurrency, pause_worker, drop_queue_items, rotate_locks).
     Tier B handlers stubbed; Tier C always escalate via apprise.
   - hooks/PreToolUse.sh: shell script that intercepts every Claude Code tool
     call, reads JSON from stdin, exits 0 to allow / non-zero to block based
     on per-project allow-list (action surface from plan v2 § Action surface).
     Decide bash vs python; defend the choice.
   - claude-settings.json.template: exactly the shape in plan v2 § Locked
     decisions / claude-settings.json, with <project_id> and <main_container>
     as placeholders the driver fills.
   - state schema (SQLite): incidents table, actions table, cost-WAL table.
     Full DDL.
   - Estimated total line count for the sidecar (target ~1000 per plan v2)

5. fabrik-lib/watchdog/emitter/ contents:
   - emitter.py: function emit_incident(name, details_dict). Writes to local
     SQLite state.db (which sidecar reads) — define the interface.
   - README.md outline
   - Vendoring instructions (which file lands where in the main app)

6. core/watchdog.md rule pack section outline:
   - When to use (universal default by kind)
   - Action allow-list (Tier A/B/C from plan v2)
   - Owner approval flow for Tier B opt-in (spec config + Apprise alert)
   - Integration with pause-state + async-http-client + abuse-prevention
   - Anti-patterns

7. Acceptance criteria for P2 (lifted from plan v2):
   - Sidecar image builds with Claude Code CLI inherited from host config mount
   - fabrik apply on test spec produces compose with watchdog service
   - emit_incident() writes audit log row + visible to sidecar
   - Restart-action handler works against test container
   - Primary-to-fallback provider chain verified: kill Claude Code session
     mid-test; sidecar falls back to OpenRouter within 60s; emits Tier C alert

8. Order of artifacts to code (smallest leaf first):
   - WatchdogConfig in spec_loader.py
   - claude-settings.json.template
   - hooks/PreToolUse.sh
   - sidecar Dockerfile
   - sidecar llm_client.py
   - sidecar actions.py
   - sidecar agent.py
   - sidecar state schema
   - emitter library
   - core/watchdog.md
   - _register_watchdog() in infrastructure.py
   - drivers/watchdog.py
   - Update fabrik-lib/README.md modules table + matrix

9. Side findings.

Show me the sub-plan. Do not code.
```

### P2.B — Code prompt (per artifact)

Same shape as P1.B — substitute "P2".

---

## P3 — Self-healing synthesis (1 day, no sub-plan needed)

**Deliverables:** `.windsurf/rules/core/self-healing.md`.

### P3 — Direct prompt

```
[Paste META-RULES if fresh session]

P3 — Self-healing rule pack. Single artifact: .windsurf/rules/core/self-healing.md.

Read first (verify each):
- /opt/fabrik/.windsurf/rules/core/58-resilience.md (must coexist with this
  pack; do not duplicate its content)
- /opt/fabrik/.windsurf/rules/core/75-workers-jobs.md (same)
- /opt/fabrik-lib/pause-state/pause_state.py + README.md
- /opt/fabrik-lib/async-http-client/circuit_breaker.py + README.md
- /opt/fabrik-lib/abuse-prevention/README.md
- /opt/fabrik/.windsurf/rules/core/30-ops.md (restart-on-OOM patterns)
- The completed P2 core/watchdog.md (so this pack complements it without
  duplication)

Then write the rule pack. The deliverable is a SYNTHESIS — it must NOT invent
new primitives; it only orchestrates the ones above into one coherent
escalation ladder. Frontmatter must match other packs (read /opt/fabrik/.windsurf/rules/core/58-resilience.md
front matter to confirm shape).

Content sections (committed):
1. Purpose: what self-healing means in Fabrik (autonomous-by-default, not
   uncontrolled). Distinguish from /health real-deps and circuit breakers
   (those exist; this is the LADDER that uses them).
2. The escalation ladder — strict ordered list of self-healing responses to
   common failure classes, with citations:
   - Symptom → diagnosis hint → first response → fallback → escalate
   - Cover at minimum: OOM, queue backlog, upstream rate-limit, upstream timeout,
     signup-flood, DB connection-pool exhaustion, sustained 5xx burst
3. Integration points with watchdog (cite core/watchdog.md): which actions are
   Tier A (autonomous), which escalate.
4. Anti-patterns: things that LOOK self-healing but aren't (retry-without-
   backoff loops, catch-all except blocks, kill-and-restart-everything panic).
5. Worked example (one paragraph): a saas-skeleton that combines abuse-prevention
   + pause-state + circuit-breaker into a coherent ladder.

Acceptance:
- Pack lints clean (no MD060/MD032 warnings).
- Every primitive cited corresponds to a file you READ above (no inventions).
- The escalation ladder has at least 7 distinct failure-class rows.
- Anti-patterns section names at least 3 concrete anti-patterns.

Write the pack. Self-review against acceptance. Show me and stop.
```

---

## P4 — 02 integration (2 days, sub-plan worth writing)

**Deliverables:** edits to `docs/traycer/mega-epic-breakdown/02-epic-decomposition-command.md` integrating the 14 universal categories + scaffold-type overlay.

### P4.A — Sub-plan prompt

```
[Paste META-RULES if fresh session]

P4 — Integrate universal-coverage overlay into 02. Write the SUB-PLAN only;
do not edit anything yet.

Read first (verify each):
- /opt/fabrik/docs/traycer/mega-epic-breakdown/02-epic-decomposition-command.md
  (FULL read — every line; you will be surgically editing this)
- /opt/fabrik/docs/development/plans/2026-05-30-ai-watchdog-platform.md
  § What 02 will enforce after P4 (the 14 categories + 6 overlays)
- /opt/fabrik/docs/traycer/mega-epic-breakdown/00-trigger-workflow-command.md
  (consumer of 02; understand what 02 receives and produces)
- /opt/fabrik/docs/traycer/mega-epic-breakdown/03-expand-epic-files-command.md
  (downstream consumer; the 02 output must remain compatible)
- /opt/fabrik/docs/traycer/mega-epic-breakdown/domain-modules/saas.md (one
  scaffold-overlay reference, to confirm the overlay shape)

Verify (do not assume):
- Confirm 02's current structure (Step 1, Step 2, Step 3, Step 4, Checkpoint,
  Output Contract, Does NOT, Acceptance). Cite line numbers for each.
- Confirm 03's input expectation: what shape does 02 hand off? Quote the
  relevant section from 03.

Write a SUB-PLAN covering:

1. For each of the 14 universal categories: where in 02 does it land?
   - Does it absorb into an existing Step 3 sub-section (Database Strategy,
     Auth Strategy, etc.) — name the sub-section
   - OR does it require a new sub-section — propose the heading
   - OR is it cross-cutting and lives in a new "Universal Coverage Check"
     sub-step inserted between Step 2 and Step 3 — define the sub-step
2. For the new "Universal Coverage Check" sub-step:
   - Where exactly does it insert (line range)
   - What is its purpose (one paragraph)
   - What does it cite for each of the 14 categories (defer to plan v2's
     table)
   - What output shape does it produce in the epic set
3. Scaffold-type overlay integration:
   - Where does the overlay loading happen in 02 (Step 2? Step 3? new step?)
   - How does Traycer choose which overlay to load (from Vision Summary
     scaffold list)
   - How does the overlay's epics merge with the universal categories'
     epics (no duplication)
4. Output contract updates:
   - Does 02's existing Output Contract need new fields? Name them.
   - Does Acceptance Criteria need new rows? Name them.
5. Does NOT updates:
   - Anything that moves into "Does NOT" because it's now covered by P1/P2
     artifacts (e.g., "Does NOT design watchdog" if watchdog wiring is now a
     universal category)
6. Line-count estimate per edit:
   - Total inserted lines (target: 150–200 per plan v2)
   - Total removed lines (likely small)
7. Backward compatibility check:
   - Does 03-expand-epic-files-command still consume 02's output unchanged?
     If not, what changes in 03 are needed? (likely no; flag if yes.)
8. Acceptance criteria for P4 (lifted from plan v2):
   - Traycer cold-read of updated 02 on test Vision Summary produces an epic
     set covering all 14 universal categories + saas-skeleton overlay
   - Existing Step 1–4 + Infrastructure Decisions structure preserved
9. Side findings.

Show me the sub-plan. Do not edit 02.
```

### P4.B — Edit prompt (per insertion / section)

```
P4 sub-plan approved. Edit ONE section of 02: <name>.

Constraints:
- Use Edit tool (NOT Write — do not rewrite the file).
- After the edit, run grep -c on the affected section markers to confirm
  count integrity.
- Self-review against the acceptance criteria.
- STOP after the edit. Show me the diff and self-review.
```

---

## P5 — Dogfood E2E (3 days, no sub-plan needed)

**Deliverables:** end-to-end test on `/opt/test-saas-for-epic-wf`.

### P5 — Direct prompt

```
[Paste META-RULES if fresh session]

P5 — Dogfood E2E. Run the full chain on /opt/test-saas-for-epic-wf and
verify acceptance.

Read first:
- /opt/fabrik/docs/development/plans/2026-05-30-ai-watchdog-platform.md
  § Acceptance criteria (whole plan)
- /opt/fabrik/specs/services/test-saas-for-epic-wf.yaml (the spec)
- ls /opt/test-saas-for-epic-wf

Pre-flight verify:
- All P1 artifacts exist and importable
- All P2 artifacts exist; sidecar Docker image builds
- All P3 + P4 artifacts in place
- postgres-main reachable; cost_ledger table exists
- Apprise configured and reachable

Execute (one step at a time, show me after each):

Step 1: Paste 00-trigger-workflow-command.md into Traycer; declare NEW mode;
feed the test SaaS vision (any small editorial SaaS concept). Capture Vision
Summary.

Step 2: Paste 02-epic-decomposition-command.md into Traycer with the Vision
Summary. Capture epic set. Verify it covers all 14 universal categories +
saas-skeleton overlay. If a category is missing, STOP and report.

Step 3: Paste 03-expand-epic-files-command.md to expand epics into tickets.

Step 4: Pick one ticket; execute it via your normal agent workflow (Claude
Code / Windsurf / Kilo — your choice). Land code.

Step 5: fabrik apply specs/services/test-saas-for-epic-wf.yaml. Capture full
output. Verify:
- cost_ledger table reachable
- watchdog sidecar container running
- emit_incident() callable
- Apprise channel registered

Step 6: Synthetic anomaly test — docker kill <main_container>. Watch sidecar.
Verify within 90s:
- Tier A restart action taken
- audit_log row written (verify hash chain integrity)
- Apprise notification received
- cost_ledger row written for the diagnosis call

Step 7: Provider fallback test — kill the host Claude Code session. Re-trigger
anomaly. Verify within 60s:
- Sidecar falls back to OpenRouter
- Tier C "primary LLM provider unavailable" alert sent
- cost_ledger row has provider='openrouter' with real cost_usd

Step 8: Budget kill-switch test — force cost-budget to zero. Trigger anomaly.
Verify sidecar drops to rule-only mode (no LLM calls).

Step 9: postgres-main outage test — docker stop postgres-main for 60s.
Trigger anomaly. Verify sidecar continues operating; WAL accumulates rows;
on restart, WAL drains within 30s; no rows lost.

After all steps:
- CHANGELOG entries per artifact written
- LESSONS_LEARNT entry for any cross-cutting insight
- Self-review against P5 acceptance criteria

Show me each step's evidence. Do not skip steps. If any verification fails,
STOP — do not paper over.
```

---

## Notes on use

- For every fresh session, start with the META-RULES block.
- Sub-plan prompts (P1.A, P2.A, P4.A) are NON-NEGOTIABLE — they prevent the
  shallow-work failure mode. Even if you're tempted to skip, don't.
- Code prompts (P1.B, P2.B, P4.B) are reusable per artifact. Substitute the
  artifact name; the constraints stay.
- P3 and P5 are direct prompts (no sub-plan) because they're either small
  (P3) or executing pre-designed artifacts (P5).
- If you notice the agent drifting from the prompt mid-task, paste the
  META-RULES again — it resets discipline.
