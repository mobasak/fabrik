# Strategic Backlog

**Last Updated:** 2026-08-25 — every item now carries an owner tag (see § Ownership).
Current split of the 16 open items: **infra 3 · fleet 11 · intel 1 · operator 1** (5 infra rows closed 2026-08-25).

> **Purpose:** Track work that's been deliberately deferred from active development — not because it's unimportant, but because it's not yet ready for a focus window, blocked on operator action, or correctly waiting for a triggering incident.

Generated from the end-of-day plan-state on 2026-06-07 after the trio Phase 5.1.a ship. Each item below is something we explicitly DIDN'T do this session and explicitly DIDN'T commit to today — and why.

---

## Ownership — every item carries an owner

Three hub agents share this repo, each with a charter in [`docs/reference/agents/`](reference/agents/)
injected at SessionStart by `agent_role.py` (keyed on `CLAUDE_AGENT`). **An untagged item is work
nobody owns** — the same failure the fabrik-mail addressee solved for messages, applied to the
backlog. Tag every new row.

| Tag | Agent | Beat |
| :--- | :--- | :--- |
| `[infra]` | infra | command corpus (`commands/_sources/`), enforcement checks, gates, mail/`command_run` machinery, governance docs |
| `[fleet]` | fleet | VPS + deploy (`specs/services/`, registrar, compose), monitoring/alerting, DR, scaffolding |
| `[intel]` | intel | research, model selection, the subagent flywheel |
| `[operator]` | — | needs a human: credentials, third-party consoles, or a decision only the operator can make |

**Cross-beat items name BOTH halves** rather than being split into two rows — one owner drives, the
other is named in the text (e.g. CI-parity Phase 4 is `[infra]` for the existing-repo sweep while the
scaffold half is fleet's).

---

## Now — Ready for Focus Window

| Effort | Owner | Item | Why Priority | Ready When |
| :--- | :--- | :--- | :--- | :--- |
| ~~**M**~~ | `[infra]` | ~~**fabrik-mail DISPATCHER — Layer-1.5 auto-processing**~~ ✅ **RESOLVED as ENFORCEMENT, not a dispatcher (2026-08-26)** — the operator broke the frame after five dispatcher reviews: the send path is hub-owned and fleet-synced, so unaddressed hub mail became IMPOSSIBLE at `mail.py send` (the addressing guard: `--to-agent infra\|fleet\|intel`, `--broadcast` for deliberate all-agents — refuses `ack:required` — or a `kind: reply` thread, which inherits the parent's owner). Every automated sender updated (both claude_rotate twins, kaizen = one addressed obligation per beat); the destination side kept ONLY the escalation digest (`scripts/sysadmin/mail_escalate.py`, cron ≤6h + local-date day-stamp = 1 Telegram/day max, three populations incl. archive strands). Rejected alternative E in the spec archives the whole dispatcher design (tier-0 regex 26% + Haiku probe 85.2% retained as measured fallback). Spec+plan: `docs/superpowers/specs/2026-08-25-fabrik-mail-dispatcher-design.md` (v3.1). | Delivery-to-owner enforced at the source; obligations that rot despite an owner escalate daily. | Operator installs the cron line + logrotate (docs/workstation/fabrik-mail.md § Escalation). |
| ~~**M**~~ | `[fleet]` | ~~**Spoke DR — end-to-end measured recovery**~~ ✅ **DRILLED LIVE 2026-06-08** against vps4. Round-trip measured: provision → bootstrap → mesh+DNS fleet-add → destroy with `--reverse-fleet-add` = **~5–6 min wall-clock**, **~$0.06 cost** (vc2-2c-4gb in lax). Drove out **4 real bugs** (provision had no `-y` flag, dns.py defaulted to dead `coolify` network, no sshd-ready poll between Vultr-API-active and bootstrap, step_02 UFW-enable SSH-drop aborted bootstrap) — all fixed + unit-tested in commits [`f8a5359`](https://github.com/mobasak/fabrik/commit/f8a5359) → [`c48f3c0`](https://github.com/mobasak/fabrik/commit/c48f3c0) → [`cbbdb99`](https://github.com/mobasak/fabrik/commit/cbbdb99). Verified live: mesh ping vps1↔vps4 = 1.25ms, DNS apex + wildcard live via Cloudflare, Loki ingesting from vps4. Full breakdown in [`docs/reference/fabrik-vultr.md`](reference/fabrik-vultr.md) § "Live-run measurements". Two follow-ups recorded: step_04 `iptables-persistent` install removes ufw on Ubuntu 24.04 (affects step_15 aro-wake UFW rules); `provision` doesn't auto-register the new spoke in Prometheus/Gatus. Both are minor compared to what we proved works. | The OS+bootstrap recovery path is now proven end-to-end against a real billed instance, not just `--skip-mesh --skip-dns` hermetic drills. | n/a — drilled. |
| **M** | `[fleet]` | **Hub DR — measured recovery against a real billed test hub**. `fabrik vultr drill hub` is shipped but the hub bootstrap is ~90 min and the path is heavier than the spoke. End-to-end "vps1 disk dies → fresh droplet → bootstrap-hub.sh → restore from B2 (postgres-dumps + docker-volumes + opt-configs + host-state) → 31 containers green → DNS cut over → Gatus green" has never been measured. The plan target is ≤90 min for bootstrap alone; restore + container deploy is unmeasured. | Until this wall-clock exists, the "DR-in-hours" claim is paper-only. | ~3-hour focus window + ~$0.10 droplet cost + acceptance that the live mutation will be heavier than for the spoke case. |
| ~~**L**~~ | `[fleet]` | ~~**`fabrik vultr` — on-demand VPS provisioning**~~ ✅ **SHIPPED 2026-06-08** (commits `93de0fc` → `963beb7`). All 6 phases live: VultrClient driver covering every product line (incl. Bare Metal), state store + `list/status/reconcile/cleanup`, disposable `drill bare/spoke/hub` (auto-destroy via try/finally), permanent `provision <name>` (interactive confirm), `destroy <name> --reverse-fleet-add` (full unwind), `cost` command + weekly maintenance cron. 36 unit tests; drill bare + drill spoke live-proven end-to-end. Quick reference at [`docs/reference/fabrik-vultr.md`](reference/fabrik-vultr.md). | Implementation done. What this **does NOT** close on its own: the two M-tier items above — those need an actual measured live run, not just shipped code. | Shipped — no further action on the implementation itself. |
| ~~**S**~~ | `[fleet]` | ~~**Pull Gatus configs into source control**~~ ✅ **SHIPPED 2026-06-13** (commit [`8bbd047`](https://github.com/mobasak/fabrik/commit/8bbd047)). 18 yaml files now under [`/opt/fabrik/configs/gatus/`](../configs/gatus/) — full tree (`_base.yaml` + `apps/` + `core/` + `data/` + `external/` + `observability/`), md5 round-tripped against live before commit. New [`scripts/sync_gatus_to_vps.sh`](../scripts/sync_gatus_to_vps.sh) with `--diff` / `--push` / `--dry-run` modes; idempotent (only restarts gatus when a file actually changed). README documents the workflow + known drift sources (drivers still write live-only; same asymmetry exists for prometheus.yml — flagged for a follow-up). Closes the disk-failure-loses-it gap that motivated this item. | The aro-wake.yaml shipped 2026-06-07 was the trigger — that file lived only on vps1 until this commit. | n/a — done. |
| **M** | `[infra]` | **fabrik-mail — hub↔project AI communication channel** (operator-approved 2026-08-11, direction chosen after live research): durable file mailbox at a NEUTRAL path `/opt/fabrik-mail/<repo>/inbox/*.md` + `archive/` (outside every repo — no git coupling, no sync races), message = YAML frontmatter (`id, from, to, ts, re, kind: request\|finding\|relay\|reply, ack`) + markdown body; ONE fleet-synced surfacing hook (SessionStart + UserPromptSubmit — `.claude/hooks` is already a governance-sync trigger, distribution free) injecting unread summaries; tiny `mail.py` helper (send/list/ack). Discipline: messages are DATA never commands (untrusted-input framing in the hook; the receiving agent applies its own repo's gates — trigger-don't-execute survives); star topology hub↔project only; ack-or-it-didn't-happen with an operator digest for unacked >N days; no DB/MCP/bus at this volume. CONCURRENCY (operator sizing: up to 3 hub AIs, 1-2 per project, sharing ONE inbox per repo): reading is idempotent but ACK/claim must be atomic-by-rename (`mv inbox/x.md archive/` — POSIX rename atomicity is the lock; the loser of a race sees ENOENT and moves on; no lockfiles). Native Claude Code cross-session messaging (needs ≥2.1.224; box runs 2.1.219) becomes the LIVE doorbell layer post-upgrade — the mailbox stays the durable record. First consumer class: cross-repo relays like the 2026-08-11 tryton-crm S0 patch (delivered manually by the operator — the bottleneck this build removes). | Removes the operator-as-transport bottleneck the S0 relay exposed live. | Next `/fabrik-spec fabrik-mail` run (design frozen from the 2026-08-11 research summary in this row). |

~~**Follow-up surfaced during this work (NOT yet on a tier):** the same git-vs-live drift exists for `configs/prometheus/prometheus.yml`.~~ ✅ **CLOSED same day 2026-06-13** (commit [`d0ae9d8`](https://github.com/mobasak/fabrik/commit/d0ae9d8)). Snapshot caught up the drift, 3 files now in [`configs/prometheus/`](../configs/prometheus/) (`prometheus.yml`, `rules/alerts.yml`, `rules/fabrik-drift.yml`). New [`scripts/sync_prometheus_to_vps.sh`](../scripts/sync_prometheus_to_vps.sh) with `--diff` / `--push` / `--dry-run` / `--verify-secrets`. **Side-fix surfaced + applied live:** `prometheus.yml` had a Meilisearch Bearer token inline — switched the live config to `credentials_file: /etc/prometheus/secrets/meilisearch-key` (Prometheus-native pattern), token now lives only on vps1 at `/opt/monitoring/configs/prometheus/secrets/`, never in git. **Driver fix:** [`drivers/prometheus.py::_write_config`](../src/fabrik/drivers/prometheus.py) now writes to BOTH vps1 AND the git mirror atomically — so future `add_scrape_target` / `add_aro_wake_target` calls keep the snapshot truthful. 2 new tests cover dual-write + best-effort mirror failure.

---

## Later

- [ ] **[infra]** **Traycer-chain command evaluation — run the orchestrator commands natively, retire the Traycer layer** (operator ruling 2026-08-30, ledger D-012: "we rarely use traycer instead, i want to use their commands here"). The chain already executes in Claude Code (Traycer is a layer; the _traycer-skills are thin wrappers over docs/orchestrator/ canonical docs), so the evaluation scopes: which of the ettw/mega commands become first-class rendered /commands, what the cockpit/card layer loses, and what dies with the Traycer dependency (server-side My Workflow already retired wiring). SEQUENCED by the operator: starts only after (1) the MCP evaluation (the per-type roster split decision + implementation) and (2) the rules evaluation are finished. Blocked by: those two, in order.
- [x] **[fleet+infra]** **Universal governance docs publish to PUBLIC docusaurus sites — audit the class** (fleet's observation in `01M19JJNWKAKNEZBA65TVDT5A1`, 2026-08-30, raised while wiring the DECISIONS scaffold seed) — **RESOLVED at the generator 2026-08-30 (commit `62858b50`).** Measured (the "measure first" step): **0 live docusaurus projects fleet-wide** (39 `project.yaml` + `data/projects.yaml` registry), so there is no live site leaking today and no retro-fix. Fix chosen: a docusaurus content-docs `exclude` in the scaffold generator (`_DOCUSAURUS_UNPUBLISHED_DOCS` in `src/fabrik/scaffold.py`) covering the seeded governance docs (DECISIONS/LESSONS_LEARNT/STRATEGIC_BACKLOG) AND the pipeline-generated contracts a UI-bearing docusaurus project writes into the same `docs/` (flows/ui-design/design-system) — present-but-unpublished, rendered `**/<name>`. Reviewed via /fabrik-review (pool + native Opus; report `docs/development/reviews/2026-08-30-docusaurus-governance-doc-exclude-review.md`). Infra's build-time-exclude + enforcement-guard alternative is now moot for new scaffolds; the only residual is an OPTIONAL enforcement guard to catch a hand-authored docusaurus that removes the exclude — low value at 0 live sites (infra's call).

- [ ] **[infra]** **Plan-lock release check — a finished plan must not hold its lock** (specced 2026-08-25, operator-requested follow-on). **Nothing writes a plan lock but the agent.** `grep` across `scripts/` and `.claude/hooks/` returns zero writers: `check_plan_tickets.py:561`, `check_phase_tests.py:36` and `final_gate_stop.py:785` all only READ. The lock is created by prose (`/fabrik-execute-plan` Before-You-Start step 7) and released by prose (Finish step 5), so the whole protocol is honour-system — with the honour supplied by an LLM following a paragraph it read hours earlier at the far end of a long run. **Two live instances, both measured this session.** (1) `2026-08-19-plan-1-kaizen-m1-event-stream.json` sat `status:"active"` with `completed_at:"2026-08-21"` and `final_commit:null` — one field of a three-field write landed — while its plan was `Status: EXECUTED` in `plans/archived/` with 9/9 tickets `merged`. It BLOCKED the inert-rule-packs plan on three high-traffic hub paths (`final_gate.py`, `select_rules.py`, `review_rubric.py`) until the operator ruled, because D1/step-7 forbids agent auto-reclaim unconditionally and correctly. (2) `2026-07-26-plan-1-ai-model-catalog-extraction.json` is STILL `active` today holding 10 owned paths (`scripts/kilo-benchmarks/`, `tests/kilo_benchmarks/`, …) with its plan archived and `completed_at`/`final_commit` both null — it will block the next plan touching those paths. **Two mechanically-decidable facts, no judgement needed:** a lock whose plan is `Status: EXECUTED` or lives under `plans/archived/` must not be `status:"active"`; and a lock with `completed_at` set must have `final_commit` set (a half-applied Finish is the exact signature of instance 1). Advisory WARN on landing, per this repo's own doctrine that a check firing fleet-wide on day one gets ignored. **Why it matters beyond tidiness:** the paths involved are the ones every plan touches, so one unreleased lock silently blocks the next several plans, and the failure surfaces as a hard BLOCKED halt at another agent's step 7 — far from its cause, days later. | The protocol has readers and no writer, and its two failure modes are decidable from the lock file plus the plan's own status line. | A short focus window; both instances are already measured, so this is implementation, not investigation.
- [ ] **[infra]** **Plan-stage pack-routing gaps** (transdoc `01M0WN9RXJJY9SDQTF8183GTYW` items 4a–4c, filed 2026-08-25 with the inert-glob findings; the glob class itself is fixed — 15/75 by the D7 plan, 86 this sitting — these three are the COMMAND-CORPUS half): (4a) plan-time pack routing is by ticket TOPIC, not the ticket's FILES — `review_rubric.py --changed` already maps paths→packs but runs only at review time; teach `select_rules.py` a `--changed`, or have `/fabrik-plan-after-chat` route packs per ticket via `review_rubric.py --changed` on the ticket's declared files, and `/fabrik-plan-review` diff glob-matched packs against each ticket's Context Files (non-empty difference = finding). (4b) a Constraints Digest may cite a pack and drop its HARD STOPs in summarisation — transdoc's spine cited 15-api-contracts and kept only the RFC 9457 clause, dropping the codegen ban that would have prevented 19 phantom frontend calls; require a cited pack's Banned Patterns verbatim in the Digest. (4c) `/fabrik-execute-plan` D7 is satisfiable by green suites alone — no step requires one live request against a running service; transdoc's whole finding list came from a one-minute read of `app.openapi()["paths"]` that no gate ever forced. Blocked by: next command-corpus focus window.
- [ ] **[fleet]** **Fleet container-name/alias reconciliation check** (deploy-triad root-cause #1, 2026-08-11): nothing mechanically reconciles a project compose's `container_name`/service keys against LIVE fleet container names + fabrik-net aliases — the tryton-crm `gotenberg` collision (a standalone container squatting the name for 4 weeks, the compose's own "no such service exists anywhere on the fleet" comment false when written) reached a deploy plan before anything caught it. Candidate shapes: a `/fabrik-deploy-plan` Phase-2 mandatory probe (it now does this for tryton-crm ad hoc), a `fabrik validate` extension, or an enforcement check. Blocked by: next deploy plan for a multi-service stack, or a spare S-window.
- [ ] **[fleet]** **Scaffold/validate warning for dependency-asserting compose healthchecks** (deploy-triad root-cause #1): a compose healthcheck pointing at a READINESS route (one that 503s on an unreachable dependency — tryton-crm's `/health` pings trytond as a login that doesn't exist pre-init) deadlocks `docker compose up --wait` on first deploy AND invites healer restart-storms on dependency blips. Docker healthchecks should be liveness. Candidate: a compose-lint in `fabrik validate`/`deployer_ssh._validate_compose` flagging healthcheck URLs that match the app's readiness route when a `/healthz` liveness route exists. Blocked by: a focus window; the class is now documented in the tryton plan + Lesson 110's neighborhood.
- [ ] **[fleet]** **Scaffold a captured-event GlitchTip secret-leak test (+ vacuity guard)** (tryton-crm `01M145D3N`, passed back 2026-08-28 after fixing the emitter leak `f273064c`). The emitter now sets `include_local_variables=False` + `max_request_body_size="never"` (Python) / `includeLocalVariables:false` (Node), and the hub test asserts the emitted INIT carries them — but no scaffolded project verifies its own RUNTIME behavior on the captured event. tryton-crm built exactly this (`tests/test_glitchtip_no_secret_leak.py`, verified d2ca9d9) and flagged two things the scaffold should emit for every DB/auth project: **(1) a kept VACUITY GUARD** — a second test that re-runs the same capture with `include_local_variables=True` and asserts the secret DOES appear, so a green leak-test can't certify nothing when the SDK's capture path changes (~10 lines); **(2) a Transport SUBCLASS, not a callable** — sentry-sdk 2.64 deprecated function transports, and a security test that silently stops capturing on an SDK bump is the worst failure mode. Candidate: emit `tests/test_glitchtip_no_secret_leak.py` from the fastapi-backend scaffolder (mirror the `_TEST_DB_GUARD_CONFTEST` emission pattern) + a hub test asserting the emission. Blocked by: a focus window; the emitter leak itself is already fixed fleet-forward, this is per-project self-verification.
- [ ] **[fleet]** **Deploy ordering breaks init-at-boot images (registrar injects `DATABASE_URL` AFTER first `up`)** (found live in the Zitadel deploy-plan review, 2026-08-28, plan finding D1). `deploy()` runs `deployer.deploy` (`docker compose up -d --wait`) at `orchestrator/__init__.py:163`, then the postgres registrar injects `DATABASE_URL` at `:173` — so the container's FIRST boot has no DSN. Services whose entrypoint connects lazily (evolution-api etc.) tolerate this; an image that runs migrations synchronously at boot and **exits with no retry** (Zitadel `start-from-init` — grounded via zitadel issues #5810/#11942 + troubleshooting docs) crashes, `up --wait` raises, and the deploy rolls back at `:207` **before** the registrar ever runs → the DB is never created → a repeated `fabrik apply` re-crashes identically. Such a service **cannot be stood up by a plain `fabrik apply`**. Candidate fixes: (a) a `shape`/spec flag that provisions the DB + injects `DATABASE_URL` BEFORE the app's first `up` for init-at-boot images; (b) a DB-reachability wait-wrapper the emitter injects; (c) a documented bootstrap runbook (pre-create DB+role, pre-seed the DSN into the remote `.env`, then `up`). Blocked by: a focus window; the class is measured + documented in the Zitadel plan's D1, and it currently blocks that deploy at Gate 2.
- [ ] **[fleet]** **`generate` secrets lack a remote-`.env` preservation read — re-apply re-mints a stable-forever key** (found live authoring the Zitadel deploy plan, 2026-08-28, `docs/development/plans/archived/2026-08-28-plan-deploy-zitadel.md` finding F1). `orchestrator/__init__.py:301-303` resolves `secrets.generate` via `secrets_manager.load_all(generate)` — process-env + a **hub-local** dotenv only (`secrets.py:60,77-101`). Only `from_env` gets the remote-`.env` preservation read (`__init__.py:306-320`), and even that targets a hub-local `/opt/<id>/.env` that never exists for a remote-only third-party service. Consequence: a secret minted on FIRST `fabrik apply` into the **remote** `/opt/<id>/.env` is **re-minted** on any SECOND apply (the hub resolver never sees the remote value) and `inject_env`'s `merged.update()` (`deployer_ssh.py:235`) overlays the new value. For an ordinary generated password this is a silent auth break; for a **stable-forever encryption key** (Zitadel's `ZITADEL_MASTERKEY`, which decrypts stored data) it is **catastrophic data loss**. Candidate fix: give `generate` the same remote-`.env` preservation read `from_env` has — read the target VPS's `/opt/<id>/.env` over SSH before resolving, and never regenerate a key already present there (mint-once). The Zitadel deploy works around it with an apply-once + updates-via-`redeploy` runbook invariant, but every future generate-secret service inherits the trap. Blocked by: a focus window; the class is now measured + documented in the Zitadel plan's F1.
- [ ] **[infra]** **Spec-comment truth discipline** (deploy-triad root-cause #4, Lesson-105 class): three tryton spec comments were code-false (shared-token "accepts TI's token too" — dev-only in production; `expose.internal_only` — a DEAD field no orchestrator code reads; RPC_PASSWORD "creates the login WITH it" — the script generates its own). Candidate: extend the review commands' checklists (done for deploy plans — class 8 doc-truth) and/or a periodic spec-comment audit against the code. Blocked by: recurrence. **RECURRENCE CHECKED 2026-08-25 — it has NOT recurred, so this stays deferred on evidence rather than assumption.** The three original tryton comments were corrected in place with the finding recorded beside them (`tryton-crm.yaml:96` now reads "create_rpc_service_user.py IGNORES it and GENERATES its own"; `:85` records the A4 removal). Across the 75 specs on disk, 38 comment lines are assertion-shaped; three live ones were verified against code and all three are TRUE: `seo.yaml:55` (auto-generate) vs `orchestrator/secrets.py:77,100 generate_if_missing`; `spoke-canary.yaml:3` (docker source) vs `deployer_ssh.py:150 SourceType.DOCKER`; `site-provisioner.yaml:44` (registrar overwrite + restart) vs `inject_env`'s contract. **Do not build the periodic auditor until a real second instance appears** — enforcement for a non-recurring class is the churn this backlog exists to avoid. The deploy-plan review's class-8 doc-truth check already covers the path where it bit.
- [x] **[infra]** **`/fabrik-deploy-plan` Output contract omits the gate-required `## Behavior Contract` section** (found live on the first run — the plans gate demands it on every new plan; the command's four gate-required sections don't name it, the executing agent discovers it at gate time). One-line corpus fix in `commands/_sources/fabrik-deploy-plan.md` + render. Blocked by: nothing; fold into the next corpus touch. ✅ **CLOSED 2026-08-25** — the Output contract now names FIVE gate-required sections incl. `## Behavior Contract`, with the shape to author and the reason it is easy to miss (the demanding gate is `check_test_proposal`, NOT `check_plan_quality`, whose Behavior-Contract pillar is spine-only). Proven: a deploy-shaped monolith went False→True against `evaluate_plan`.
- [ ] **[infra]** **Store-terminal adjudication** (deploy-triad recorded residual): the plan-frozen release NEXT routes STORE surfaces post-submit to `/fabrik-deploy-verify`, whose contract is spec-driven VPS-only — a store agent dead-ends cleanly at target resolution. Options: a store analogue inside deploy-verify, or reword the store terminal across all FOUR encoding surfaces (NEXT dict + release body line + § Pipeline parenthetical + 6-release stage row, the latter two in BOTH CLAUDE.md copies). Blocked by: first real store-surface release (mobile-app etc.). **PARTIALLY CLOSED 2026-08-25 — the live dead-end is fixed; the analogue stays blocked.** `/fabrik-deploy-verify` Phase 0 now opens with a SURFACE GUARD: a store-surface target stops with a clean hand-back naming what a store release actually needs verified (build provenance from a pushed SHA, vendor-console review/rollout state, first-ring crash/ANR) instead of failing at step 1 on a `specs/services/<id>.yaml` that store types never have — which read as a missing file rather than an inapplicable command. Same rule as the enforcement-battery audit: a command that cannot ask its question must SAY so. **Still open and still correctly blocked:** the store ANALOGUE itself, plus the four-surface reword — grounding what it should probe needs the first real store release, and the guard now makes the aspirational routing honest at the point of use meanwhile.
- [x] **[infra]** **North-star "deploy = manual `fabrik apply`" lines** (`docs/orchestrator/00-autonomous-factory-north-star.md:143`, also :44/:200): predate the deploy triad; `/fabrik-deploy`'s Gate-2 tiebreak absorbs them (the operator's dispatch IS that manual act for plan-governed deploys). Cosmetic doc alignment when the north-star is next edited. ✅ **CLOSED 2026-08-25** — all three lines aligned to the deploy triad: Gate 2 is the operator's explicit go, after which `/fabrik-deploy-plan` → `/fabrik-deploy-plan-review` → `/fabrik-deploy` executes and calls `fabrik apply` underneath. Nobody types it by hand, so the old phrasing described a workflow that no longer exists. Verified: zero remaining "manual `fabrik apply`" occurrences in the file.
- [x] **[infra]** **Three pre-existing adjacents from the triad's gate B** (recorded, non-behavioral): `skill_router.py:128` comment still says wordpress "deploy-only" (the retired phrasing); `scaffold.py:5768-5772` wordpress `NotImplementedError` still points at the archived `wpf` CLI; `templates/governance/CLAUDE.md:24`'s "All projects … deploy via `fabrik apply`" overstates for store surfaces. Fold into the next touch of each file. ✅ **CLOSED 2026-08-25** — all three corrected: `skill_router.py` no longer calls wordpress "deploy-only" (it is out of fabrik; `/opt/wpf` archived 2026-08-07), `scaffold.py`'s NotImplementedError no longer points callers at the deleted `wpf` CLI, and the governance line no longer claims ALL projects deploy via `fabrik apply` (store surfaces do not).
- [x] **[infra]** **Whole-tree docs_updater debt** (pre-existing, reported 2026-08-11 during the triad's docs sweep — NOT the triad's): docs/CAPABILITIES.md link rot (auto-generated — fix the generator's link targets), stale docs/QUICKSTART.md (111d) + docs/CONFIGURATION.md (107d), broken links in old plans/specs. Blocked by: a docs focus window or the next `/fabrik-docs-review` full run. **UPDATED 2026-08-25:** the CAPABILITIES.md half is CLOSED — its generator wrote repo-root doc_links (`AGENTS.md`) into a file that lives in `docs/`, so every one resolved to a non-existent copy one directory too deep. **273 of the repo's 386 broken links were that single bug (71%)**; fixed at the generator + regression-tested, total now **113**. What REMAINS is not the same class: 111 of the 113 are citations inside `docs/development/plans/**` and `docs/superpowers/specs/**` — historical artifacts that `check_doc_links` deliberately EXEMPTS as sources (plans cite files as they were; specs forward-reference). `docs_updater` scans them anyway, so the two link checkers disagree by design — reconcile the scopes before treating those 111 as debt. Genuinely open: stale `docs/QUICKSTART.md` (125d) + `docs/CONFIGURATION.md` (121d), which need a content pass, not a link fix. ✅ **CLOSED 2026-08-25 (second half).** Both stale docs verified against code, corrected, and their currency headers refreshed — stale count 2 → 0. QUICKSTART's executable surface was already accurate: all 10 documented `fabrik` subcommands exist and every documented flag (`--from-preplan`, `--github-create`, `--dry-run`, `--filter`, `--yes`, `--spec`, `-n`) resolves. CONFIGURATION carried the REAL rot — two live pointers to `/opt/wpf` ("the real driver is /opt/wpf/src/wpf/drivers/wordpress.py", and the WP credentials line), a path ARCHIVED on 2026-08-07 and gone from disk. Both rewritten as tombstones so nobody re-adds the variables thinking they were an oversight. Newest env vars (FABRIK_MAIL_*, FABRIK_OPT_ROOT) confirmed present in BOTH `.env.example` and this doc, per the Doc Sync Matrix. **Note on the metric:** staleness is measured from the `**Last Updated:**` header, not git mtime — CONFIGURATION had been edited 2 days before it was flagged. Bumping the header alone would have been a lie; content first, then the date.
- [x] **[infra]** **`fabrik-deploy-verify.md` cite range off-by-one-sentence** (Phase-D whole-pack review nit, pre-existing): its `:16,148` cite of `fabrik-catchup.md:68-75` anchors the right item but the bridge-namespace sentence itself sits at catchup `:76-78`. Fold into the next corpus touch of that file. ✅ **ALREADY CLOSED** (0883b987, 2026-08-16) — both cites were de-numbered to a section anchor (`§ the local-`fabrik`-bridge probe`), which cannot drift; the anchor resolves at `fabrik-catchup.md:77`. No action was needed; this row was stale.
- [x] **[intel]** **Flywheel `refuses-ungrounded` axis** — BUILT 2026-08-29 (plan `2026-08-28-plan-1-canary-grounding`, Phases A+B; the `select.py` multiplier rides the fabrik-lib filing). Original row (job-agent `01M13TM8FN`, 2026-08-28): "does this model fabricate when its grounding input is absent" is invisible in normal scoring — on a well-formed prompt both models look fine. Measured differential on an identical missing-input grounder: `gemini-3-flash-preview` refused to invent in its first sentence; `deepseek-v3.2-exp` produced a line-numbered analysis of a file it never saw, wrong in the direction that plans the wrong fix. Candidate shape: a per-model boolean/score column fed by deliberate missing-input probes (a tiny periodic canary batch), consumed by `pick_models` as a penalty for grounding-class task types. Needs a small spec (ledger schema + probe design + ranking integration) — deferred per the no-spec boundary of the sitting that filed this row. The 62-pack warning (same commit) covers the caller-side trap meanwhile.
- [ ] **[intel]** **Reconcile the 2026-08-28 transdoc score contamination in `subagent_runs`** (transdoc 01M154PZQ, self-reported): ~226 historical review runs (2026-08-21→28, other sessions' agent_ids) received `status='scored'` deltas at 2026-08-28T21:3x from project=transdoc with per-model constants (v3.2-exp 4.0, qwen3-max 4.0, gemini-3-flash 3.0, v4-flash 3.0) — under latest-wins those now shadow real adjudications. MEASURE FIRST (the fix directive): count affected agent_ids whose prior latest score differed, split had-prior-score (re-assert prior latest via fresh deltas — INSERT-only-compatible) vs never-scored (needs an aggregation-side exclusion or acceptance — decide on measured counts). Module-side guards (refuse re-score without override + ownership warning) filed to fabrik-lib the same day.
- [ ] **[intel]** **Wire `MISTRAL_MONTHLY_CAP_USD` to a real enforcer** (2026-08-29, found by the key-wiring self-review): the $10/month hard cap across ALL Mistral keys is provisioned in `.env` + documented in CONFIGURATION.md, but NO consumer reads it — an advisory cap on a paid API is the stored-and-never-read class. Mitigated today: all four Mistral keys 401 (monthly free credit EXHAUSTED — operator-confirmed; usable again at the credit reset, which makes the enforcer MORE urgent, not less: an unbudgeted consumer burns the whole month's credit in a day). Resolution: when the Mistral account activates and a first consumer appears (crowdlex haiku-replacement is the candidate), route its spend through the cost-budget seam reading this var — monthly + total across keys, never per-call (sysadmin-loop rule).
- [ ] **[intel]** **Kilo golden-parity standing red — routes/IMAGE_GEN/ai-pack marker drift** (2026-08-29, surfaced during the canary Phase B review): 10 `test_golden_parity` failures list ONLY foreign artifacts — `scripts/kilo_openrouter_routes_final.json` structure change + OPENROUTER_ROUTES marker rows collapsed to 0 across the ai/ packs + `IMAGE_GEN_SELECTION.md` 3→1 rows — the routes half of the daily pipeline has gone husk; `capture_golden --verify` (a `severity='critical'` daily gate) is red on it. Deliberately NOT frozen over during the canary work (freezing empties makes them "never red again"). Fix the routes pipeline, then re-snapshot.
- [ ] **[intel]** **Flywheel back-scoring debt — ~1093 unrecorded pool runs** (box-wide advisory printed on every `fanout`; predates this session): `audit_unrecorded('/opt/fabrik/.tmp/subagents/ledger.jsonl')` lists them; `pick_models` cannot learn from unrecorded runs. Blocked by: a focus window; decide score-vs-write-off per batch (Lesson-97 discipline: errored runs are non-results, never 0-scored).
- [ ] **[fleet]** **CI-parity Phase 2 — spec-driven `shape.db_extensions: [pgvector]`**: deferred from [`archived/2026-07-01-plan-fabrik-ci-parity.md`](development/plans/archived/2026-07-01-plan-fabrik-ci-parity.md). The one-source CI generator (`src/fabrik/ci_scaffold.py`) already accepts `db_extensions=("pgvector",)` → `pgvector/pgvector:pg16`, but scaffolding runs *before* a spec exists, so there's no spec→CI regen path to drive it — new scaffolds default to plain `postgres:16` (correct for most). Blocked by: a project that actually needs pgvector in CI AND a decision on the regen trigger (a `fabrik ci-refresh <spec>` step vs an apply-time registrar). Not urgent — the default is right for the common case.
- [x] ~~**[infra]** **CI-parity Phase 4 — backfill existing projects with `ci_local.sh`**~~ ✅ **MOOT 2026-08-29** — the operator retired CI checks in every existing and future repo, so there is no workflow left to mirror. Every repo's check workflows are `disabled_manually` (verified fleet-wide: zero active), the scaffold no longer emits `ci.yml`, and enforcement moved to `final_gate` plus the hub's pre-push gate. I flagged this as likely-moot in the 2026-08-25 thread; it is now decided. Original text follows for the record. ~~: deferred from the same plan. New python scaffolds now auto-emit `ci.yml` + `ci_local.sh`. **Scope re-measured 2026-08-25 — the earlier "~39 projects" estimate was wrong by an order of magnitude, and counting only `ci.yml` undercounts it (repos also carry `test.yml`, `type-check.yml`).** Counting ANY `.github/workflows/*.yml`: **15 repos have workflows, 7 lack a local replica** — `fabrik` (the hub itself, 2 workflows), `proxy`, `trade-intelligence`, `youtube`, plus `rnfinal` / `rn-kit-sandbox` / `supplement-tracker-advisor` (13 workflows each — RN-template output, likely out of scope; confirm before touching). The remaining ~33 repos have no workflow at all, so there is nothing to mirror. Deliberately NOT a blind overwrite: a project's hand-rolled workflow must not be clobbered, and a faithful `ci_local.sh` must mirror *that* project's actual workflow (the generator renders from `CiConfig`, not by parsing an existing one). Blocked by: a small "generate `ci_local.sh` from an existing workflow" tool, or a per-project decision to adopt the generated `ci.yml`. Real remaining scope is **4 repos**, not 39 — small enough to do by hand if the tool is not worth building.
- [ ] **[fleet]** **PostgreSQL 16 → 18 upgrade** (WSL dev + VPS hub): plan at [`archived/2026-05-25-postgresql-18-upgrade.md`](development/plans/archived/2026-05-25-postgresql-18-upgrade.md). Created 2026-05-25, never started. 14 dbs on `postgres-main` would need pg_dumpall → PG18 cluster bootstrap → restore + verify, plus matching upgrade on the WSL dev DB to keep "same code in 3 envs" valid. PG16 reaches EOL November 2028 so there's no urgency; the existing setup is healthy. Blocked by: (a) a focus window of 2–3 hours, OR (b) a real PG18-only feature need (none today). When ready, unarchive the plan and run.
- [ ] **[fleet]** **propose/ack peer-protocol verbs** (trio plan Phase 5, deferred): Today the cross-host destructive bridge is operator Telegram `reply "go"`. Build the `propose`/`ack` HTTP verbs in aro-wake only when a real incident proves the bridge is insufficient — don't speculate. The "real cross-host destructive action" use case hasn't shown up yet. Blocked by: first real incident where consult-only + operator-bridge is provably too slow.
- [ ] **[fleet]** **Apprise pre-route through aro-wake** (trio plan Phase 5, deferred): Gatus / GlitchTip / Backrest webhooks currently go straight to Telegram. AI never sees them. Wire Apprise to aro-wake first with `continue: true` semantics like Alertmanager Phase 4. Blocked by: first real incident proving Alertmanager-only triage missed something.
- [ ] **[fleet]** **Loki ruler with starting rule set** (trio plan Phase 5, deferred): Log-pattern alerts not generated at all today. Sidecars catch their own container's logs; cross-container log signals on vps1 aren't observed. Blocked by: first incident that log-pattern-rule would have caught earlier than container-state probe.
- [ ] **[fleet]** **Grafana `aro-wake` dashboard**: 8 SLI metrics + 2 alert rules live on full fleet since 2026-06-06. PromQL + Telegram alerts cover real operator needs today. Build a dashboard only when ad-hoc PromQL queries become tedious. Blocked by: operator running the same PromQL recipe 3+ times in a week.
- [ ] **[fleet]** **"Repeated-flag-no-action" pattern detector** (complement to `detect_reversals.py`): The 2026-06-07 netdata flood was 24 benign "anomaly detected" wakes with no AI action taken — `detect_reversals.py` correctly doesn't fire (no AI action to reverse), but a different correlator could flag "AI flagged X N times in a row, operator never acted → AI is wrong OR alert is misconfigured". Same `lessons-pending.jsonl` output stream, different correlator. Blocked by: second occurrence of a similar pattern that's not the netdata case (which is now fixed).
- [ ] **[fleet]** **Bake the new operator-reversal cron line into the live cron-template DEPLOY path for existing hosts**: Today I appended to `/etc/cron.d/vps-sysadmin` on all 3 hosts manually and also updated [`sysadmin-cron.template`](../scripts/bootstrap/templates/sysadmin-cron.template) for future spokes. There's no `fabrik`-level redeploy step that re-renders the cron template on existing hosts after a template change. Blocked by: another cron template change that needs to propagate.
- [ ] **[fleet]** **Reset `/opt/fabrik/` ownership on vps2 + vps3 from `root:root` to `ozgur:ozgur`** (cosmetic): Today's bootstrap-vps.sh change covers fresh installs going forward, but the live state on vps2/vps3 still has `/opt/fabrik` as `root:root`. Nothing is breaking — the venv was already created earlier — but the asymmetry would be discovered during the first real maintenance touch. Blocked by: nothing; one-liner SSH per spoke, but not worth interrupting steady state for.
- [ ] **[operator]** **Bot token rotation** for `SysAdminVPS2` (`8838110344:...`) + `SysAdminVPS3` (`8674270904:...`): Operator declared this private chat 2026-06-07 and declined rotation. Re-evaluate if the chat scope ever changes. Blocked by: operator decision.

- [ ] **[infra]** **Un-extracted duplication across command sources** (measured 2026-08-29 while fixing the `/fabrik-review` ↔ `/fabrik-generate-tests` copy). That fix single-sourced ONE pipeline into `commands/_fragments/test-generation-loop.md`; a sweep for the same class across all 31 sources found **4 more source pairs sharing 95 six-line windows**, dominated by ~~`fabrik-service-test.md` + `fabrik-user-test.md` at 65 windows~~ ✅ **EXTRACTED 2026-08-29 (cmd 15/31 audit):** the gauntlet pair now renders four shared fragments (`cert-board-contract` · `cert-execution` · `cert-handoff-grammar` · `cert-visual-deliverable`), rendered-parity md5-proven, residual shared windows **0** — and the extraction erased two REAL drifts the cmd-14 fixes had just created (the recorder naming and the grader-honesty split existed only in user-test). Remaining pairs: `fabrik-spec.md` + `fabrik-spec-review.md` (11), `fabrik-flows-review.md` + `fabrik-ui-design-review.md` (10), and `fabrik-data-contract.md` + `fabrik-flows.md` + `fabrik-ui-design.md` (9). Each is a contract maintained in two files where an editor of one cannot see the other. ⚠️ **The measure has a known blind spot and it is the important one:** it normalises whitespace and emphasis but not WORDING, so it scored the review/generate-tests pair at **0** — the copy that motivated all of this had been lightly reworded. A duplication gate built on this measure would therefore miss the exact defect class it is named for; the honest framing is that it finds *un-factored twins*, not *drifted copies*. Fix direction: extract per pair into `_fragments/`, largest first, and re-measure. Blocked by: the audits of the remaining pairs' commands (spec/spec-review at cmd 16+; the audit is at command 15 of 31 done).

- [ ] **[infra]** **`final_gate` has NO TypeScript/JS checks — and CI was the only thing running them** (surfaced 2026-08-29 when CI checks were retired fleet-wide). `grep -n "tsc\|eslint\|vitest\|npm test\|type-check" scripts/final_gate.py` returns **nothing**. trade-intelligence's CI ran a whole job the gate cannot replace — `npm run type-check`, `npm run test:unit`, `npm run test:components` — and it was FAILING on all five of its last runs. Disabling CI moved the python half to a stricter place (the gate blocks the commit instead of emailing after the push) but moved the web half to **nowhere**: a green `final_gate` in a repo with a web surface now asserts nothing about its TypeScript. Affected: any repo with `package.json` + a web surface (trade-intelligence confirmed; the three RN repos carry `lint-ts`/`type-check`/`test` workflows but two of them have no git remote so those never ran anyway). Fix direction: a diff-scoped web tier in `final_gate` — run `type-check`/`lint`/`unit` **only when the diff touches web paths and the scripts exist in `package.json`**, `warn_only` on landing per this repo's own doctrine that a check firing fleet-wide on day one gets ignored. ⚠️ Measure the fire rate first: an unknown number of these suites are already red, which is exactly how CI ended up ignored. Blocked by: a focus window; nothing is waiting on a decision.

- [ ] **[infra]** **/fabrik-rivals driver: `--seed-rival` flag** (fabrik-lib `01M15DM2G`, module SHIPPED bebc57b→6cf6a74, 515 tests green): `competitor_intel.run` now accepts seeds; the driver half is `scripts/rivals_run.py` — expose the flag per the module contract in the mail. Closes trade-intelligence's pinned-vendor upstream ask. Small; next rivals window.
- [ ] **[infra]** **Plan lint: Scope-mentioned paths ⊆ Touches** (brand-identiy `01M15PMZ3` #1, proven live: a T07 Scope bound two files its Touches omitted; cards wiped at review-mount): candidate `check_plan_tickets.py` extension — flag a ticket whose Scope sentences name paths absent from Touches/Context Files. MEASURE fire rate on the plan archive first per doctrine.
- [ ] **[infra]** **Gate behavior question: a STAGED plan with no HEAD commit reds every session's diff-scoped gate un-attributably** (fleet `01M16Q0KQ`, two live occurrences): should `check_test_proposal`/the gate skip index-only plans, or warn-attributing to the stager? Needs a decided semantics, not a patch — the red is real work-in-flight, the tax is cross-session.
- [ ] **[infra]** **check_doc_links blind spots** (youtube `01M15AYX5` #2): cannot see cross-refs inside `docs/development/` or `docs/superpowers/`, and omits `CHANGELOG.md` from root sources — a Doc-Sync-mandated link class is never checked. Extend + measure the new fire rate before landing (archived plans link freely; a naive widening floods).
- [ ] **[infra]** **Playwright-MCP roots vs scratchpad directive contradiction** (brand-identiy `01M15PMZ3` #3): the MCP refuses the system-prompt scratchpad (`outside allowed roots`); agents work around via gitignored `.playwright-mcp/`. Either add the session scratchpad to MCP roots (settings) or sanction `.playwright-mcp/` in the fabrik-gui agent def — one of the two, documented.

---

## Context

- ⚠️ **Stale Prometheus scrape targets cause Telegram floods via the Phase 4 wire**. The netdata flood on 2026-06-06→07 ran for ~12 hours (24 messages every 30 min) because a `netdata:19999` scrape target was left in `prometheus.yml` after the container was retired 2026-05-30. Pattern: removing a service from compose MUST also remove its scrape job from `prometheus.yml`. Captured in commit `f5c6e48`. Should make this a registrar invariant check long-term.
- 💡 **Cross-mesh container→host scrape pattern works** via docker MASQUERADE rewriting the source IP to vps1's wg0 IP (`10.99.0.1`), which the spokes' existing `from 10.99.0.0/24 to any port <port>` UFW rules permit. Documented in [`prometheus-app-metrics-setup.md`](infrastructure/prometheus-app-metrics-setup.md) § aro-wake SLI metrics. Reusable for any future host-service that needs Prometheus scrape coverage from spokes (no firewall changes needed beyond the existing mesh allow).
- 💡 **Loop-guard counters are in-memory by design** — restart = reset = safe default. `rate()` / `increase()` in PromQL handle this via the `_created` timestamps that prometheus_client emits. Don't migrate to persistent counters; the reset semantics are correct.
- 💡 **Operator-reversal detector deduplicates by `(ai_source, ai_ts, operator_ts)` tuple** in [`detect_reversals.py`](../scripts/sysadmin/detect_reversals.py). Re-running 2× after a match produces 0 new entries. If we ever extend the schema, preserve this idempotency property.
- ⚠️ **sqlite3 `-csv` mode quotes timestamp fields with embedded space**, breaking `strptime` unless you strip quotes. The default `-list` (pipe-separator) mode works cleanly for our 3 simple columns. Documented in `detect_reversals.py` `collect_sidecar_actions()`.
- 💡 **Trio loop guards (4 layers) are sufficient for `consult`-only protocol AND future `propose`/`ack` Phase 5 work**. Same handler, same guards. No protocol version bump needed when Phase 5 ships propose/ack. Documented in [`scripts/sysadmin/peer-protocol.md`](../scripts/sysadmin/peer-protocol.md) §3.2.1.
- 💡 **Watchdog sidecar action log (`state.db`) is the canonical source for "AI took an action"** today — `sysadmin-actions.jsonl` is mostly diagnose-only wakes for now. When host-AI gains explicit action verbs (e.g., autonomous container restart from proactive-check), add the `action_name` + `target` fields to the jsonl entry so `detect_reversals.py::collect_host_sysadmin_actions()` starts firing.
- ⚠️ **Gatus configs live ONLY on vps1** (not in this repo) — see "Now" row above. If you edit an existing endpoint and want it source-controlled, you need to also pull the file into the repo manually OR do the gatus-source-control work first.

---

## [infra] The git-isolation scrub has no end-to-end regression test (2026-09-01, owner: infra = me)

`tests/conftest.py`'s `pytest_configure` strips 14 `GIT_*` vars session-wide after incident
`f7627885` (a red-on-revert experiment's `git add -A` committed a sibling's WIP to master).
`tests/enforcement/test_git_env_isolation.py` asserts the scrub and the resulting behaviour — but
**both of its tests are green with the scrub reverted** under normal invocation, because nothing in
a normal environment sets `GIT_DIR`; they only red when the harness itself is started with it, and
no gate does that.

**The attempt and why it failed:** spawn a victim repo, run a NESTED pytest with a hostile
`GIT_DIR`, assert the victim's modified file is still UNSTAGED (` M`, not `M `). It red-failed
against correct code — the nested test file was written under `tmp_path`, which is outside the
`tests/` tree, so `tests/conftest.py` never loaded for it. It measured an unprotected process and
blamed the scrub. Writing the nested file inside `tests/` would work but is a tree mutation this
suite should not make mid-run.

**Current proof status:** the scrub is verified by a MEASUREMENT recorded in `d36239cc` (decoy repo,
pytest under a hostile GIT_DIR, victim HEAD and index confirmed unchanged) — not by a regression
test. So a future edit that deletes the scrub ships green.

**Shape of the fix:** a session-scoped fixture that writes the nested test into a temp dir *inside*
`tests/` and removes it afterwards, or a `pytest_configure` unit test that asserts the hook is
registered and pops the right keys from a synthetic environ. The second is weaker but has no tree
mutation.

**Trigger:** next time anything touches `tests/conftest.py`, or the next git-isolation incident.

---

## [infra] warn_only checks that print on a ZERO-finding run — 7 of 18, fleet-wide (2026-09-01, owner: infra = me)

**Measured**, not estimated: 18 of 19 `warn_only=True` registration sites in `scripts/final_gate.py`
run as scripts (the other 3 `warn_only` hits are runner/printer code). Each was executed bare in a
CLEAN fleet repo (`/opt/youtube`); **7 print on a zero-finding run**, so every green gate in the 48
synced repos carries that many content-free rows — in the human listing AND in the `--json`
`advisory` array, which applies no ⚠ filter (`scripts/final_gate.py`, `advisory_rows` is gated only
on `WARN_ONLY_CHECKS` membership).

| check | bytes on a clean run | what it prints |
|---|---:|---|
| `check_mutation` | 238 | `MUTATION (advisory): skipped in the per-commit gate …` — unconditional; can never carry a finding in gate mode |
| `check_pack_reachability` | 385 | dumps `reachable:` inventory with zero findings |
| `check_feedback_duty` | 272 | clean case not exercised (both probe repos had a real finding) — UNPROVEN |
| `check_plan_lock_release` | 225 | `0 stale | 0 likely-stale | 0 half-applied | …` |
| `check_spec_convergence` | 105 | `4 CONVERGED spec(s) examined, 0 with findings` |
| `check_vps_docs` | 90 | `PASS: check_vps_docs — 0 error(s), 0 warning(s)` (tier 3 only) |
| `check_phase_tests` | 85 | `PHASE-TESTS (advisory): OK — no active plan window …` |
| `check_rivals_dossier` | 76 | `rivals dossiers: 1 examined, 0 with findings` |

Clean-silent and correct: `check_vendored_drift`, `check_rule_grounding`, `check_trigger_routing`,
`check_frozen_chain`, `check_decisions_unique`, `check_doc_stubs`, `check_env_example`,
`check_ticket_breadth` (0 bytes each). `check_retired_terms` prints 6870 bytes of GENUINE warn rows —
not an offender.

**Why it is here and not fixed:** `22a1a062` gave `check_script_headers` a `--quiet` flag that the
gate passes, closing exactly ONE instance. Fixing 7 more scripts is outside that diff's surface and
is its own change. Recording it rather than letting the class die in a session's context.

⚠️ **Attribution corrected** — the finder reported these as "same defect, same author, same commit
range" as `d2e0d4f2`. They are not: `git log -S` puts the `N examined, 0 with findings` strings at
`9342ae9f` and `15bcec7a`, and the finder confused `test_plan_lock_release` (which that commit
touched) with `check_plan_lock_release` (which it did not). Pre-existing, repo-owned.

**Two fix shapes, both viable:** (a) add `--quiet` to each of the 7 scripts and pass it at each
registration site — explicit, skew-safe, precedented, 7 small diffs; (b) suppress zero-finding stdout
inside `run_optional_check` — one diff, but it changes a synced contract for every advisory row and
would need a sentinel convention. ⚠️ Do NOT "just pass `--quiet` to every warn_only check" from the
runner: scripts using `argparse` would exit 2 on an unknown flag, which `run_optional_check` treats
as a broken warn_only contract and FAILS the gate.

**Trigger:** the next time a warn_only check is added or edited, or the next gate-noise complaint.

---

## [infra] Review-machinery findings — ROUTED from the 2026-09-01 triage deep review (owner: infra = me)

Raised by author-blind finders during `/fabrik-review` of the LOCAL-vs-ARCHITECTURAL triage. Both are
OUT of that review's surface (pre-existing, different files) and are recorded here with owner + trigger
rather than smuggled into a command-corpus commit. Disposition: ROUTED, not deferred-to-nobody.

- **`command_run.py --reason` is unvalidated free text.** `:891` advertises "one of the three sanctioned
  BLOCKED cases" and `:1435-1438` stores whatever it is given — so an unauthorized fourth cause closes a
  run record cleanly. This is not theoretical: the escalation bullet deleted in `e82e7a0a` would have
  done exactly that. The three-case restriction is prose-only at the one moment it could be mechanical.
  **Trigger to build:** measure first, per FIX-directive verb 5 — count closed `blocked` records and how
  many cite a non-sanctioned cause (`~/.claude/state/command-runs/`); if >0, add a WARN-tier validator
  (rollout law: warn before block).
- **Two disposition vocabularies that no command cross-references.** `check_review_coverage.py:293-304`
  accepts a `## BLOCKED` section ONLY with 3-attempts evidence, while `:49-50` already carries
  `ROUTED(n)` for the "adjudicated, not open, not fixed" case — and no command source teaches `ROUTED`.
  That gap is precisely why my escalation bullet pointed at the path the grader rejects instead of the
  one it accepts. **Fix shape:** teach `ROUTED(n)` in the review commands' disposition vocabulary, and
  cross-reference the two in the grader's docstring so the next author cannot repeat the mistake.
- **`assemble_commands.py:829` mislabels source drift.** It prints `HAND-EDITED (N diff lines)` naming
  the INSTALLED file when the real cause is an uncommitted edit to the SOURCE — the message points at
  the wrong file. Same at `:690` (agents) and `:837` (skills). Cost me a re-check this session.
- **`CLAUDE.md` line-wrapping defeats phrase greps** (a bounded-search negative on that file is
  unreliable without `tr -d '\n'`) — the denominator-honesty class, hit live by a finder this run.
- **Corrected framing, fleet-wide:** the command corpus is NOT per-repo synced (`commands/` appears in
  neither the governance-sync files-filter nor `fabrik_synced_manifest.py`). Its blast radius is
  BOX-WIDE via `~/.claude/commands/` — one install, every repo on the box. My own commit messages said
  "ships to ~46 repos"; that is the wrong mechanism, and anyone sizing risk from it mis-models the
  change. Measured by a finder: 43 git repos under /opt; 223 paths in a project's synced.lock, none
  under `commands/`.

## [infra] Rules currency pass (operator-dispatched 2026-09-01, file-by-file) — cross-pack class findings

**DETECTOR GAP — `_LOOSE` misses several literal shapes (re-measured 2026-09-02; the first version
of this entry was WRONG and is corrected below).**

`rules_render_versions.py::_LOOSE` catches `Node 24` / `Debian 13` but not everything. Denominator:
**56 rule files** (`find .windsurf/rules -name '*.md' | wc -l`). Spanned lines excluded.

| shape | hits | pattern (the instrument) | verdict |
|---|---:|---|---|
| tool-name outside the alternation | 6 | `\b(React\|Electron\|Vite\|Next\.js\|…)\s+\d+\b` | **REAL** — `Electron 30`×4, `Next.js 14`, `React 19`. The exact class `_LOOSE` was built for; only the name list is short |
| bare package pin `x.y.z` | 10 | `(?<![\w.:/-])\d+\.\d+\.\d+(?![\w.])` | **MOSTLY REAL** — `sentry-sdk[fastapi]>=2.18.0`, `1.4.11`; 2 are dates (`23.05.2026`) |
| bare Debian **codename** | 7 | `\b(trixie\|bookworm\|bullseye)\b` | **REAL, and the worst** — see below |
| `>=N` | 20 | `>=\s?\d+` | **NOISE** — `CHECK (balance >= 0)`, `>= 99.5%` crash-free, `>= 500` status codes. ~1 of 20 is a version |
| `^N` / `~N` | 0 / 1 | `\^\d+` / `~\d+\.\d+` | **EMPTY** post-fix; the one `~1.05x` is a throughput ratio |
| `vN` | see note | `\bv\d` → 111 occurrences / 25 files | **MIXED** — `Recraft v4.1` real; `v1 = one workflow`, `/v1/` paths not |

⚠️ **The first version of this entry claimed `>=N`/`^N`/`~N` were "high signal — dependency ranges"
and proposed widening for them. That is backwards**: after file 14's fix the corpus holds ~zero true
positives in those shapes, and widening would red ~10 packs entirely on thresholds and ratios — the
wallpaper FIX-directive verb 5 forbids. It also quoted a `vN` count of 59 with no pattern recorded;
`\bv\d` yields 111. A count without its instrument, in the ledger whose governance anchor is
denominator honesty.

⚠️ **The codename shape is the one with NO detector at all, and it silently defeats the span test.**
`nginx:mainline-trixie` contains no digit, so `_LOOSE` cannot see it: unwrap a `debian_codename`
span and nothing fires. That is why the pinned span COUNT matters (file 14 was pinned at 4 against 9
actual — five spans removable with zero signal until corrected). The 7 live hits are `bookworm` in
`75-workers-jobs` (×3) and `76-gpu-workers` — the D-064 debt already deferred to those packs' turns.

**Deliberate fix, when taken:** extend the name alternation (cheap, high signal), add a codename
watch keyed off `versions.yaml::debian_codename`, and leave `>=`/`^`/`~`/`vN` alone. Not done here:
it touches a fleet-synced detector and belongs in one measured change, not mid-pass.

## [infra] Rules currency pass (operator-dispatched 2026-09-01, file-by-file) — cross-pack class findings

**PACK-SIZE PRESSURE — RESOLVED by retiring the cap (D-071, 2026-09-02); one sub-item survives it.**
File 13 was trimmed from 61 KB back under the then-blocking 50 KB auto-load cap. **That cap has since
been removed** — it was a Windsurf-era context budget and Windsurf is retired — so byte pressure is no
longer a reason to shed rule content anywhere in the corpus. The trimming itself stands: every byte cut
was a duplicated implementation (a hand-rolled `CircuitBreaker` that fabrik-lib ships as
`CircuitBreakerRegistry`, a `TRANSIENT_PATTERNS` table the scaffold emits, a second TS client
re-implementing `fetchWithRetry` — the defective one).

**Still open, and NOT about bytes:** `58-resilience`'s globs are overbroad — `**/client*`,
`**/health*`, `**/dispatch*` activate it on nearly any service touch (a `clients/` dir, a Redux
`dispatcher.ts`). That is real context cost the byte cap only ever proxied for, and it is unaffected by
the cap's removal. Related option, now optional rather than forced: splitting the worker-only
§ Autonomous Pause-State Pipeline into its own pack (the section already declares "applies ONLY to
`file-worker`/`file-api`", and every `python-api`/`saas-skeleton`/`mobile-app` project currently loads
worker rules it can never use).

**FILE 12 RE-AUDIT (2026-09-02) — three classes deferred to their OWNING surfaces (bar row 9), all
found by the author-blind opinion and verified:**
- **`15-api-contracts` has ZERO webhook text** (`grep -in "webhook|hmac|compare_digest"` → 0 hits)
  while 57 says an inbound receiver "is a served route: `15-api-contracts` applies". 57 now carries
  the receiver's auth posture + delivery semantics itself; at 15's turn decide whether the inbound
  receiver contract (signature, timestamp tolerance, event-id dedup, ack-fast) is 15's to own or 57's
  to keep — one home, then a pointer from the other.
- **The command corpus never asks for the profile** — 0 of 32 `commands/_sources/*.md` mention
  "Capability Profile" or `57-external`. The pack's "teeth at plan time" is currently 57 alone. A
  single bullet in `/fabrik-plan-review`'s checklist ("every external dependency in the plan has a
  profile, or an `UNKNOWN — <tried>` per field") is the measured first step — command corpus,
  merge-time render only.
- **fabrik-lib `async-http-client` surfaces neither `Deprecation`/`Sunset` headers nor a
  distinct expired-credential outcome** (`grep -in "sunset|deprecat|401|expir"` over the module → only
  the breaker's own "OPEN + expired"). Profile fields 9/10 are therefore project-local to implement
  today. A one-hook request to fabrik-lib (log-once + counter on first `Deprecation` seen; a typed
  `CredentialRejected` outcome) is the lean fix — cross-repo, so filed by mail, not edited from here.

**SEEDED FOR FILE 13 — `core/58-resilience.md` says "Never retry 4xx" and never mentions 429.**
Measured 2026-09-01: `grep -c 429 .windsurf/rules/core/58-resilience.md` → **0**;
`grep -ci retry-after` → **0**; the rule at `:86` reads "Retry transient errors: timeout,
connection, and 5xx … Never retry 4xx." 429 IS a 4xx and is the canonical retryable one — an agent
following 58 literally will never retry a rate limit, which is backwards, and will ignore
`Retry-After` because 58 never names it. Surfaced by file 12's new Capability Profile field 2
("429 + `Retry-After`?"), which an agent can now answer correctly and then be told by 58 not to act
on. Fix in 58's own turn: carve 429 (and 408) out of the never-retry-4xx rule and require honouring
`Retry-After` when present.



**THE GOAL (D-062, operator verbatim):** always-uptodate · correct · lean · efficient ·
low-maintenance · free · resilient · traceable · logged · fastest · agile · best-practice.
**Standing ruling:** version literals are banned from packs — tripwires are triage (D-061);
the solve is a machine-updated version source + render-time injection (pipeline proposal owed
during the pass). Scope: core/ then ALL folders, to completion.

- ✅ **bookworm→trixie FLIPPED (D-064, 2026-09-01, 30-ops's turn).** Grounds: Debian 12 regular
  security ended 2026-07-12 — the fleet had built on an EOL-full-support layer for 7 weeks; trixie
  stable since 2025-08, images live. One yaml line + one render because the spans were laid
  file-by-file (the D-062 machinery's first class-flip in anger). 40-documentation had already
  dropped its literal; 50-code-review reworded version-free. Scaffold emission now TWO axes stale
  (bookworm + 3.12) — see the interpreter-gap alignment row.
- Evaluated so far: 10-python (2026-09-01 — 3.13→3.14 current-stable fixed; Alpine rationale
  updated to the PEP-656 reality; distro literal deferred to the class commit) · 12-node
  (2026-09-01 — full bar; record below).
- **Tripwire ARMED** (`rules_currency_watch.py`, weekly-cron rider): pinned python/node vs
  endoflife.date, mails infra per new upstream release (watermarked, silent on blips). First
  scheduled firing: node 26 LTS on 2026-10-28 (packs pin 24). This is the "what happens in one
  year" answer — the drift now pages instead of waiting for a re-read.
- **File-1 SECOND OPINION adjudicated** (mandatory subagent bar, backfilled 2026-09-01): 14
  verdicts → 9 ACCEPTED+applied (fail-open secret exemplar; temp-rule rationale rewritten
  honest incl. ephemeral/persistent split; global-handler-default + `from exc`; /healthz–/health
  split defined pack-side; single-process-uvicorn made an explicit rule; async-discipline block
  [task refs · shared AsyncClient · now(UTC)]; ruff `ASYNC`/`B`/`S` baseline; pinning policy;
  router-tutorial shrunk + testing section pointed at 45) · 2 REGISTERED as aging claims
  (glitchtip-5xx-capture → 55's turn; musl-allocator) · 2 CLASS-DEFERRED (30-ops HEALTHCHECK
  target + the duplicated CMD block — 30-ops's turn) · 1 REFUTED (in-file prose↔table dedup:
  the banned table is an INDEX of the prose, one truth + one index, not two truths).
- **Scaffold alignment owed** (rule leads, scaffold follows): emit /healthz in python-api
  template; emit ruff ASYNC/B/S selection in scaffolded pyproject. Trigger: next scaffolder window.
- **DEEPENED same day (operator: "very shallow") → CLAIMS REGISTER (D-061):** `.windsurf/rules/
  CLAIMS.yaml` — every external assertion as a dated, verify-hinted row; the watcher mails infra
  when a claim outlives its window; the pass grows the register file-by-file (10-python's 7 claims
  + 2 class rows seeded). Version regex = layer 1; claim windows = layer 2.
- **File-2 (12-node) COMPLETE under the full bar (2026-09-01).** Own research legs: Node 22 is
  Maintenance-only (pack said "both active LTS" — false); type stripping stable+default (the
  `--experimental-strip-types` prescription was a self-contradicting relic); Express current
  major is npm `latest` since 2025 (pack said "post-2026 maybe"); helmet/pino/vitest headings
  de-literalized; CVE trio re-grounded to the 2026-03-24 advisory. All 18 `_LOOSE` hits +
  regex-blind shapes (Fastify 5, Express 4/5, pino v9+, Helmet 7+, chalk v5+, Paddle v2) triaged;
  spans: `node_lts`, new `node_engines_floor`, `debian_codename`. **SECOND OPINION (Fable 5,
  author-blind, D-063 dispatch pin): 33 verdicts → 18 KEEP · 14 FIX + 1 ADD adjudicated as: 8
  already covered by my own pass, 9 newly applied** (Express-major pin warning; Mastra
  `easy-day-js` RESTORED — it verified the incident my search missed and I had wrongly deleted;
  ALS ~7%-overhead causality inversion fixed → negligible-under-AsyncContextFrame; 20s-backstop
  false rationale → scaffold `stop_grace_period: 45s` grounded at scaffold.py:3126; ungrounded
  "Traefik strips __proto__" safety claim deleted → patched-runtime floor rule ADDED;
  `@fastify/helmet` clause; CVE-21713 recast as bug-class-not-userland-mitigation; nonexistent
  `@stripe/stripe-node` → real `stripe` package, both occurrences), **literal-bearing correction
  shapes REJECTED** (its "helmet 8+"/"pino v10" suggestions re-literalize; staleness findings
  accepted, shape overruled per D-062 — the subagent is deliberately blind to the ban). 9 new
  claims rows + node-lts-line widened. Pinned tests now parametrized over CLEANED_PACKS.
- **Scaffold alignment owed (12-node additions):** compose template already emits
  `stop_grace_period: 45s` (verified); Node scaffolds still declare `engines.node ">=22.0.0"` —
  when the previous LTS EOLs (Apr 2027) raise the floor AND flip `node_engines_floor` in
  versions.yaml in the same change.
- **Scaffold alignment owed (15-api-contracts):** the pack now mandates the un-prefixed
  `Idempotency-Key` header (industry-consensus name — the IETF httpapi draft EXPIRED at -07;
  RFC 6648 deprecates `X-`); the scaffold's widget example still reads `X-Idempotency-Key`
  (`scaffold.py:2990` — its docstring also cites the pack by line number, which shifted). Rule
  leads, scaffold follows: flip the emission to accept `Idempotency-Key` (keep `X-` as legacy
  fallback) at the next scaffolder window. Note the scaffold example is a POST — still
  key-required under the narrowed POST/non-idempotent-PATCH scope.
- **TWO OPERATOR LENSES ADDED TO THE BAR (2026-09-01, post-file-6):** (a) `docs/infrastructure/`
  fleet docs are mandated grounding for deploy/VPS-surface packs — read AND live-verified (they
  rot both ways: the inventory had the true redis tag while agents-fabrik:183 had aspirational
  pgvector); (b) **D-065**: OPERATIONS.md + DEPLOYMENT.md are fleet-AI interfaces — fully
  current, machine-consumable (what/how to deploy; which VPS services: workers, systemd, cron).
  Enforcement lands at 40-documentation + 75-workers-jobs + deploy-surface turns: check the
  rules ENFORCE currency + consumability, not merely name the files.
- **File-11 (55-observability) COMPLETE under the full bar (2026-09-01) — the largest pack (501 lines) and the most FICTION.**
  Triggered by the operator's live symptom ("agents are not creating a proper logging system"),
  measured to root cause rather than guessed. **Answer: the machinery works, the SCAFFOLD leaks** —
  site-provisioner emits textbook structlog JSON *and* raw uvicorn access lines on the same stdout
  (34.6% of its 24h lines carry no `{`), because scaffold.py:799 uses `PrintLoggerFactory()` which
  bypasses stdlib entirely and the emitted CMD runs uvicorn with default access logging. Rules side
  fixed here; scaffold side filed (01M1EP16E2HBFYA2G4XKJV9X1C). **THE FILE-1 CLAIM DISCHARGED:
  glitchtip-5xx-capture VERIFIED TRUE IN SOURCE** (`_DEFAULT_FAILED_REQUEST_STATUS_CODES =
  frozenset(range(500,600))`) with three precisions the row had hidden — 5xx ONLY (4xx captured by
  nothing), duck-typed on `.status_code`, recorded `handled: True`; row rewritten, window 180→365.
  **SECOND OPINION (Opus 5, 39 verdicts — the deepest of the pass): accepted wholesale.** Its
  findings, each re-verified by me at the source before acting: the Loki section named THREE LABELS
  THAT DO NOT EXIST (`service`/`environment`/`level`; the live set is container_name/filename/host/
  job/service_name/stream — my own probe) so its worked LogQL example returned zero rows; the
  pipeline diagram described docker.sock auto-discovery when the config uses a filesystem glob;
  the metrics code block called ACTIVE_JOBS/PROCESSING_COUNT Gauges when they are a **Histogram**
  and a **Counter** (`.set()` would raise) and taught `Counter("request_count")` when the client
  auto-appends `_total`; `src/metrics.js` HAS NEVER EXISTED; the matrix claimed `file-worker` serves
  /health + /metrics when it scaffolds no HTTP server at all (deps: boto3/structlog/supabase/pypdf);
  TWO of five alert rows describe alerts that exist nowhere in configs/, and "never page on CPU/RAM"
  is contradicted by five shipped paging rules; and the pack claimed enforcement from
  `check_health.py`/`check_watchdog.py` — both WARN-only AND documented UNWIRED in final_gate.py.
  It also corrected MY OWN uvicorn prescription from this same turn (it silenced rather than routed
  and omitted `log_config=None`, without which uvicorn re-applies its dictConfig over yours) — now
  a 3-step form. **OTel: measured REJECTION recorded** (logs are the weakest OTel signal; adoption
  costs a Collector + re-instrumenting 46 projects for tracing nobody needs) with the nuance that
  the forced Promtail→Alloy migration adopts it at the COLLECTION layer anyway. Fleet findings
  filed: 01M1EQ3NCA98EF178ZY366V47T (**Promtail EOL 2026-03-02, still running**; node-api template
  default sets exposes_metrics with no metrics module → permanently broken scrape target).
  Net +33 lines on a 501-line pack: mostly deletions of fiction plus ~8 corrective sentences.
- **File-10 (50-code-review) COMPLETE under the full bar (2026-09-01) — the worst-contradiction pack.**
  Own legs: TWO drift-anchor INVERSIONS shipping to ~46 repos — "the user commits and pushes,
  coding agents only implement and fix" (vs commit-at-task-end + push-at-task-end, both § UNIVERSAL
  anchors) and "Max 5 review iterations then STOP" (a fourth halt condition vs converge-to-fixed-
  point + the three BLOCKED cases); § D prescribed TWO NONEXISTENT scripts (kilo_code_review.py /
  kilo_docs_enforcer.py — in the sync's RETIRED_CORE_SCRIPTS, i.e. actively deleted from projects:
  a guaranteed-fail instruction, not merely stale) → replaced with the real /fabrik-review family;
  stale "one of 14 trigger-based doc updates" (matrix carries 25) → SSOT pointer, no count.
  **SECOND OPINION ran on OPUS 5 — first exercise of the D-063 quota fallback (Fable 5 limit hit
  mid-turn).** Its verdict: all four legs CONFIRMED real (and #1 worse than I stated — the sync
  guarantees the script's absence), and then it caught that FOUR of its top five were MY OWN FIX
  RESIDUE: I fixed instances and never swept the file for the class (FIX-directive verb 2). All
  accepted and swept this turn — `:97` Key Reminder contradicted my new `:36` 61 lines apart;
  "full gate at milestone, not every task" survived in THREE places (header, § C heading, Key
  Reminders) against the per-task completion-gate law; Output Format shipped a COMPETING
  GATE:/NEXT: grammar with PASS/FAIL where the gate emits "status": "success"; "stop and ask"
  against the question bar / operator-decision bar; orphaned Systemic Gate H3 under § D; dead
  "iteration limits" vocabulary; bare `--lean` in the child-project note. ADDED per its verdicts:
  FIX-DIRECTIVE + 62-using-subagents pointers. **External-practice research (13 sources) REJECTED
  a new mechanism** — 2026 consensus keeps a ceiling but as a BUDGET exit with a different report,
  never as the quality gate; our convergence law + 3-round escalation already matches the shape,
  and the false-consensus risk it names is already mitigated by "refuted with the disproving line".
  Rejection recorded per FIX-directive verb 5. CROSS-REPO ROUTED: /opt/fabrik-lib is sync-EXCLUDED
  and still carries the entire pre-fix pack — mail 01M1ENAVE3MD0KV5HMWC74QEXJ (with the systemic
  ask: excluded repos need a periodic pack-diff, or their rules contradict the anchors their own
  drift check enforces).
- **File-9 (45-testing-strategy) COMPLETE under the full bar (2026-09-01).** Own legs: the pack's
  biggest policy line MOVED with the world — the blanket Vitest/RTL ban for Next.js narrowed to the
  ASYNC-RSC boundary (official Next.js docs now recommend Vitest for the unit lane; async Server
  Components remain Playwright-only BY DESIGN) + two consensus E2E-discipline lines (never stub a
  server action from Playwright; test the production build); @playwright/test >=1.59 floor →
  version-free wording + claims-row boundary. **SECOND OPINION (Fable 5, 15 verdicts): the two
  lenses DISAGREED on both my edits and the adjudication is recorded — (a) Playwright floor: their
  keep-it-load-bearing point (fix only 5 months old, old pins live) is sound, but the version-free
  wording carries the same protection and D-062 wins on shape; (b) Vitest ban: they'd keep it as
  Trophy-coherent; I hold the narrowing (a rule contradicting the official docs erodes pack trust;
  Trophy bias kept explicit). Their FOUR new catches all accepted: the fixture example silently
  depended on asyncio_mode="auto" (breaks under pytest-asyncio 1.4 strict default — exactly in the
  no-pyproject fabrik-lib carve-out; disclosure line added); example default `testdb` was REFUSED
  by the pack's own require_throwaway guard (→ myproject_test); ASGITransport-never-runs-lifespan
  caveat added (scaffolded apps are lifespan-based); and the CROSS-PACK CLASS: `src.main:app`
  matches NO scaffolded layout (scaffold emits src/<package>/main.py, scaffold.py:1487/:4834) —
  swept in the same change across 45 (regen one-liner), 30-ops (CMD ×2), 10-python (×3); the 2
  residual mentions are deliberate never-do-this references.** 3 claims rows. Zero literals.
- **File-8 (40-documentation) COMPLETE under the full bar (2026-09-01) — the D-065 owner turn.**
  A registry-derivation pack whose hand-forked enumerations had all drifted from their own SSOTs.
  Own legs: D-065 fleet-AI interface bar landed (deployed-types callout + deploy-config/scheduled-
  jobs matrix rows); DECISIONS.md added everywhere it was absent (universal list + matrix row +
  allowlist — a fleet-synced doc pack with no decision ledger, post-D-000); retired-docs self-
  contradiction closed (matrix + allowlist still mandated API_REFERENCE/DATABASE_SCHEMA/DOCS_INDEX
  that line 41 retires — registry sides with retirement); trailers table caught up (ci-fix,
  Agent-Name, post-commit verify line); dead my-workflow/06-* citations repointed (§ Step 8
  verified at :124). **SECOND OPINION (Fable 5, 23 verdicts): accepted — STRATEGIC_BACKLOG
  mis-bucketed as SaaS (registry :272-281 made it UNIVERSAL, operator rule 2026-08-27);
  docs/flows.md missing entirely (registry :254-260); matrix canonicality claim false (PROJECT_DOCS
  is SSOT, table now says it renders it); 7 more project-side matrix rows (flows/ui/design-system/
  data-contract/troubleshooting/docs-index/backlog); docs/traycer/** allowlist line dropped (gate
  flags it); plan-SET shape added; AGENTS.md open-standard line (Linux Foundation, 60k+ repos).
  PUSHED BACK on one: "Traycer machinery is gone" is overbroad — the PATH is dead but Traycer is
  the operator's live planning tool (open thread this week); citations fixed, Traycer kept.
  Gate-vs-gate fix in-beat: VALID_DOCS_SUBDIRS lacked user-guide while check_user_guide REQUIRES
  it — one-line fix in check_structure.py.** 2 claims rows. Zero literals (internal-facts pack).
  SEPARATE finding filed: 19 enforcement tests RED at committed HEAD (D-053 coverage-gate family,
  sibling mid-flight surface) — mail 01M1EKG4BFS4HCNK516ZQ5HBK3.
- **File-7 (35-security-auth) COMPLETE under the full bar (2026-09-01) — the high-risk pack.**
  HEADLINE: the committed file was AMPUTATED — commit 6e404160 (the 12-factor pass) wrote it back
  from a truncated read, ending with a literal '…[truncated]' line; 7 Done When rows + the entire
  security-critical Spec Contract — Auth Registrars section (bearer-bypass warning) were absent
  from HEAD for weeks and survived that pass's reviews. Restored from 6e404160~1, all citations
  re-verified live (check_api_bypass verifier.py:465); corpus swept (1 amputation total); guard
  test added (rules + commands/_sources + templates), Lesson 147. Own legs: JWT alg-pinning rule
  (allow-list verifier, none rejected); HS256 scoped to issuer==verifier w/ EdDSA/ES256 escape;
  frame-ancestors added (XFO formally obsolete); CVE-2025-29927 recast (patched; rule outlives).
  **SECOND OPINION (Fable 5, 25 verdicts, zero FALSE claims, every in-repo cite verified exact):
  all FIX/ADD accepted — middleware.ts→proxy.ts staleness (current Next.js SILENTLY IGNORES a
  leftover middleware.ts: nonce/redirects stop, no error — highest blast radius), CSP directive
  gains frame-ancestors+form-action (was contradicting the pack's own checklist), Factor III ✅
  example shipped a hub-BANNED localhost silent fallback (now fail-loud os.environ), denylist
  two-sources-of-truth fixed (lib SHIPS it), Argon2→Argon2id (OWASP; lib defaults exceed minimums),
  passkeys honest-limit line (OTP not phishing-resistant; fabrik-lib request first), sticky-session
  ❌ example was invalid Python with mislabeled mechanism (fixed), settings.py path nit.** 6 claims
  rows. Convergences with my legs: frame-ancestors + RS256→ES256/EdDSA found independently by both.
- **File-6 (30-ops) COMPLETE under the full bar (2026-09-01) — the class-owner turn.** D-064
  bookworm→trixie EXECUTED (own grounds: debian.org + endoflife + Docker Hub tag probes; the
  opinion independently endorsed with digest-level proof). File-1 deferrals closed: HEALTHCHECK
  → dep-free /healthz (migration clause for pre-split services; compose-override mirror named);
  base-image table span-carried. Parity section rewritten to PROBED truth (VPS runs
  postgres:16-alpine + redis:7-alpine; U+2011 hyphens killed; Alpine ban scoped to images WE
  build). **SECOND OPINION (Fable 5, 17 verdicts + flip endorsement): 4 FIX + 1 ADD accepted:
  apt exact-pin example was BROKEN on the pack's own new base (ffmpeg=7:6.1.1-3 absent from
  trixie — the only Follow-verbatim block that failed verbatim; pins dropped, base-is-the-
  boundary rule); unpinned pip-install-uv → Astral's COPY --from with span-owned uv_version pin;
  file-1's debian-slim-variant claims row was over-broad (bare -slim = trixie TRUE for python,
  FALSE for node, digest-proven) → superseded (3rd supersede of the day); redis-fleet-major
  horizon row added (7.x security ends 2029-12, current 8.x); builder/runtime same-base ABI
  sentence added. Its empirical re-proof that deploy.resources.limits works under plain compose
  v2 (live docker inspect) retired that lore-caveat question.** 30-ops: 10 spans, zero residual.
  pgvector probed NOT INSTALLED in postgres-main → 25-data corrected + claims row; fleet mail
  owed (agents-fabrik.md:183 claims it "fully self-hosted" — aspirational-as-fact).
- **File-5 (25-data-postgres) COMPLETE under the full bar (2026-09-01).** Own legs (brave + exa +
  WebFetch endoflife/SQLAlchemy/pgbouncer.org + live psql probe): stdlib `uuid.uuid7()` (Python
  3.14) replaces the uuid_utils idiom for current-python services; PgBouncer guidance rewritten
  two-layer; pg16 literals → new `postgres_major` span (fleet state, agents-fabrik.md:165, flip
  tripwire in claims); PG18-uuidv7 boundary → capability-probe phrasing. **THE SWEEP ITSELF had a
  blind spot: `_LOOSE` spelled 'PostgresQL' so real 'PostgreSQL 16' never fired, nor PG18/pgvector:pg16
  shapes — widened red→green; 7 literals surfaced in this pack that the sweep had passed** (16
  advisory WARNs now corpus-wide — other packs' hits belong to their turns). **SECOND OPINION
  (Fable 5): 20 verdicts → 15 KEEP · 4 FIX + 1 ADD; convergent with my legs on the two big ones
  (stdlib uuid7, PgBouncer staleness — it graded the old mandate 'the pack's one materially stale
  rule', inherited from asyncpg's own unrevised FAQ). Two of its catches corrected MY fresh work:
  (1) 'the scaffold default' phrasing was FALSE — scaffold.py:4809 still emits python:3.12 +
  uuid-utils (verified myself), pack now says so; (2) my pgbouncer claims row said 'default 0/off'
  — pgbouncer.org primary says DEFAULT 200 (ON) in current releases → row refuted + superseded
  (second supersede today).** saas/ prefix fixed. 3+1 claims rows, 1 superseded.
- **Scaffold alignment owed (25-data + file-1 follow-through — the INTERPRETER GAP, now TWO axes):**
  scaffold emits `python:3.12-slim-bookworm` (scaffold.py:4809, ×4) while the corpus spans
  python_stable=3.14 AND debian_codename=trixie (D-064) — interpreter and distro both drifted. At
  the scaffold window: bump the emission to the span values, drop `uuid-utils` from scaffolded
  requirements (scaffold.py:2042) in favor of stdlib uuid.uuid7, emit /healthz alongside /health
  (the health split), flip the idempotency header emission, and source the Dockerfile pin from
  versions.yaml so it cannot re-drift. (This row now aggregates ALL scaffold-alignment debt from
  files 1-6.)
- **File-4 (20-typescript) COMPLETE under the full bar (2026-09-01).** Own legs (brave + exa +
  earlier WebSearch/WebFetch): TypeScript's native-compiler major is GA (ships as `tsc`, API
  port next minor) — pack got a version-free currency line; zod 4 stable, pack idiom unchanged.
  **SECOND OPINION (Fable 5): 17 verdicts → 11 KEEP · 4 FIX + 2 ADD, all accepted** with
  literal-bearing phrasings converted to spans/version-free per D-062: `erasableSyntaxOnly`
  ADDED to the strict block (turns 12-node's erasable-syntax prose ban into a compiler error —
  the unwired checkable gate); the numeric-only enum ban was a CROSS-PACK CONFLICT with 12-node
  (native stripping refuses ALL enums) — banned-table row widened; `forceConsistentCasingInFileNames`
  DELETED (TS 5.0 default = dead weight); both `FROM node:24-bookworm-slim` literals wrapped in
  spans (the known debt item — this pack now auto-flips with node_lts on 2026-10-28); `paths`
  without `baseUrl` (hard error in the current major); dev-side type-stripping cross-ref;
  12-node added to Related Packs (asymmetric backlink); saas/ prefix on 60-saas-ui (×2).
  4 claims rows. CLEANED_PACKS += 20-typescript (4 spans).
- **RETIRED-CONSUMERS class, split disposition (2026-09-01):** mechanical header mentions of
  Windsurf Cascade / Kilo CLI swept from 10-python, 20-typescript, 50-code-review, 67-file-api,
  72-desktop (12-node done at its turn). SUBSTANTIVE Kilo-as-gateway content remains in
  **65-rag-search (gateway tables + a Done When line mandating OpenRouter/Kilo), ai/00-ai-model-selection
  (peer-gateway policy + dual-route counts), ai/60-code, ocoron-design-system (i18n levels 2-3),
  saas/60-saas-ui:325** — real guidance contradicting the retirement ruling (LLM access = Claude
  Max OAuth + OpenRouter only); owned by each pack's own evaluation turn, NOT a sed sweep.
- **File-3 (15-api-contracts) COMPLETE under the full bar (2026-09-01).** Own legs (multi-engine:
  brave + exa + WebFetch/PyPI + WebSearch): header flip, hey-api pin-exact, oasdiff v1.26
  currency, idemptx existence. **SECOND OPINION (Fable 5): 17 clusters → 12 KEEP · 4 FIX + 1 ADD,
  all accepted**: idempotency scope narrowed to POST/non-idempotent PATCH (PUT/DELETE idempotent
  per RFC 9110); idemptx name dropped (decorator-not-middleware, semi-stale redis<6 pin,
  off-culture named dep); OFFSET ban got the bounded-admin recorded exception; Deprecation header
  re-grounded on RFC 9745 (date-valued) + Sunset RFC 8594; store-key scoping rule ADDED
  (endpoint+principal); saas/ prefix on the 95-multi-tenant pointer; oasdiff CI-absence grep
  re-verified 2026-09-01. **One reversal of MY leg: the IETF idempotency draft is EXPIRED, not
  standards-track — my same-day claims row refuted and superseded (the register's supersede
  discipline exercised for real).** One defect neither lens caught alone, fixed while editing:
  flow step 4 said "Key absent" where it meant "key not yet in Redis". Zero literals (0 spans —
  claims-rot pack, not literal-rot).

## Activation

Items move to active development when:

1. **Focus window opens**: A block of 3+ hours of uninterrupted time is identified — applies to "Now" tier specifically (DR drill needs 3-4 hours, Gatus migration needs 1-2 hours).
2. **Triggering incident**: A "deferred until real case" item gets a real case (propose/ack, Apprise pre-route, Loki ruler, repeated-flag detector).
3. **Repeated friction**: The same operational pain hits 3+ times in a week — e.g., the same PromQL query becomes "type this AGAIN" → Grafana dashboard tier.
4. **Resource availability**: External tools / budgets / operator availability — DR drill needs a throwaway VPS purchase.

The hardest discipline here is the second one — resisting the urge to build "propose/ack" speculatively because it sounds important. The Phase 5 plan explicitly says: each new incident teaches; capability expands from incidents, not architecture.

## [fleet] Zitadel /debug/metrics not enabled — Prometheus target DOWN (2026-08-29)

Zitadel v4.17.1 deployed at auth.ocoron.com does NOT serve `/debug/metrics` by default (404) — the
`specs/services/zitadel.yaml` spec declares `exposes_metrics: true` + `monitoring.metrics_path: /debug/metrics`
but never sets the env that ENABLES Zitadel metrics, so the Prometheus scrape target is registered but
`health=down` (404). `docs/reference/zitadel.md:52` wrongly claims metrics is "enabled by default via
`ZITADEL_METRICS_TYPE: otel`". FIX: ground the correct Zitadel v4 metrics-enable env, add it to the spec,
re-apply (`fabrik apply` re-syncs env), confirm `/debug/metrics`=200 + the Prometheus target flips to `up`;
correct the reference doc's default claim. The IdP itself is fully live + functional — this is monitoring polish.

## [infra] Measure the hub's own test suite — the self-exclusion has let it rot (revisited 2026-08-29)

**Revisit requested by the operator** (3 stale-test findings traced to it). Grounded this session:
`final_gate.py:842 _ci_runs_pytest()` runs a repo's suite only on a `.fabrik/run-pytest` marker OR a
CI-workflow pytest mention. **fabrik has neither + 225 test files**, so its suite never runs at the gate —
"unmeasured." The exclusion was "measured and REJECTED for now" (`final_gate.py:855`) to avoid reding the
gate with stale suites on landing day.

**Empirical result of running it (2026-08-29): 25 failed, 4964 passed, 5 skipped in 1h20m01s.** Two
independent reasons a naive `.fabrik/run-pytest` marker is WRONG: (1) it would red every session's gate
with the 25 failures; (2) an 80-min suite cannot run on every gate touching src/tests/scripts even all-green.

**The 25 are overwhelmingly STALE TESTS (code evolved, tests didn't) — the exact rot the exclusion hid:**
`test_shape_phase_4k` (Shape gained `has_bearer_api`/`needs_payments_ingest`/`uses_claude_cli`/`claude_cli_home`);
`test_state::test_save_writes_all_8_fields` (state now writes a 9th field `target_vps`); plus contract-drift in
gate-canaries, session-orient-hook (×4), kaizen (×3), final-gate-symlinks (×5), scaffold, mail-addressing,
file-worker-logger, select-rules (this one reads sibling-dirty `.windsurf/rules` + `libs/subagents/select.py` —
verify vs a clean worktree before attributing). Scoped run: 23 failed / 113 passed in 20s.

**Path to measurement (the revisit's recommendation):** (a) triage + clear the ~25 on a CLEAN worktree
(distinguish stale-test → update the contract, real-bug → fix, sibling-WIP → ignore); (b) add a marker that
runs a FAST curated subset at the gate (seconds, network/integration tests excluded), NOT the 80-min full
suite; (c) OR a scheduled nightly full run that alerts on new failures (the ci-health-probe pattern) without
gating interactive work. Same reasoning for `iterative_image_editor` (separate repo — its owner adds its marker).
Do NOT flip the marker until (a) is done. Blocked by: a quiet-tree window for the triage + the subset design.

## [infra] Gate pytest leg — project-declared environment/command (transdoc 01M171R8, 2026-08-29)

The gate now runs the suite under the RIGHT interpreter (the ruff-coupling fix, cmd-29 audit turn) and
names an exit-4 refusal distinctly (`pytest (SUITE REFUSED — usage error)`), but a project whose suite
NEEDS environment (`TEST_DATABASE_URL`) still cannot pass the leg — transdoc's conftest deliberately
refuses rather than skip-to-green. Their ranked ask: honour a project-declared env/command (e.g.
`.fabrik/pytest-env` or `[tool.fabrik.gate]`) so such repos supply what their suite needs instead of
carrying a permanent named red. **Measured need: 1 repo** (transdoc; every other marker-armed repo
passes env-free) — below the build threshold; revisit when a second repo hits it or transdoc asks
again. Blocked by: nothing — deliberately deferred at n=1.

## [infra] governance-sync as pre-commit is the widest concurrent-writer window (2026-08-29)

Two sessions hit "files were modified by this hook" aborts in one day (infra cmd-26 retries; intel
01M178GME0 twice + a justified SKIP on daf984f5). Measured: the sync writes NOTHING inside
/opt/fabrik (hub excluded from discovery, write-site audit clean) — the abort is pre-commit's
tree-delta detection catching a CONCURRENT writer during the slowest hook's ~30s×47-repo window
(evidence: .windsurf/rules/ai mtimes regenerating from a live session mid-window). Root
contributors: (1) the `.windsurf/rules/ai/**` renders lost their committer at the Phase-D cutover
(autocommit_pipeline_outputs.sh removed them deliberately — the ai-model-catalog ENGINE owns
publishing now, and its commit half is intel's to wire); (2) structurally, distribution does not
need to GATE the commit — a post-commit sync would eliminate the window class entirely. DECIDED +
SHIPPED same day (operator sign-off 2026-08-29): governance-sync is now a POST-COMMIT hook —
`scripts/governance_sync_postcommit.sh`, always_run + re-applying the config's own `files:` regex
against HEAD (measured first: post-commit passes NO file list, so a naive stage move silently
disables the sync). It can no longer abort a commit and has no stash window; a sync failure prints
loudly with the manual re-run command. Residual: the `.windsurf/rules/ai/**` renders' missing
committer stays intel's engine-side item.

## [infra] kaizen coroner books headless claude -p workers as died-silent sessions (2026-08-30)

The digest's first compose flagged hole_count 10→105→116→336; re-derivation by project matched 336
exactly and named the driver: 315 of 336 are HEADLESS `claude -p` sessions from the rivals driver's
neutral-cwd invocations (youtube 149, fabrik-lib 117, -tmp 49) — by-design one-shots that never
emit stop_pass, booked by kaizen_coroner.holes() as silent deaths. Fix direction: the coroner
classifies known-headless session shapes (neutral-cwd project names, -p transcripts) as their own
class instead of holes — the metric then measures what it names. Also noted: stop_block_causes
unpushed=970 dwarfs all others; partly the push law working, partly tonight's transient
github DNS/SSH resets forcing retry loops — watch, don't build.

## [infra] Audit the check set for staged-only scoping (transdoc 01M17VA9's meta-question, 2026-08-30)

check_doc_index's tracked-only enumeration gave the run that CREATES a doc a false green (fixed:
untracked docs under the INDEX-governed tree now count as live). transdoc explicitly flagged the
class question — how many OTHER gate checks enumerate via `git ls-files`/staged-only scope and
therefore cannot fire on the run that owes the obligation — as a hub measurement. Sweep
scripts/enforcement/ for `ls-files`/`diff --cached`-scoped denominators and judge each: some are
deliberate (sibling-WIP protection, the review-coverage '??' carve-out), some are this defect.
Next window; measure before changing any.

## [infra] Canary-completeness debt: 10 registered checks lack CANARIES pairs (2026-08-30)

test_gate_check_canaries' two completeness tests are red (part of the accepted-queued suite reds):
10 registered checks (check_certification_coverage, check_command_corpus, check_feedback_duty,
check_frozen_chain, check_pack_reachability, check_plan_lock_release, check_rivals_dossier,
check_spec_convergence, check_trigger_routing, check_vendored_drift) have neither a canary pair
in liveness_audit.CANARIES nor a recorded UNREACHABLE/warn_only reason. Accumulated across
sessions as checks landed without their canaries; none added today. Each needs a deliberately-bad
fixture proven to trip its check — real authoring work per check, not a fixture tweak. Author in
batches at the next enforcement window; the two tests are the ledger of what remains.

## [infra] check_changelog verifies existence, not correspondence (found by /fabrik-review 2026-08-30)

`scripts/enforcement/check_changelog.py` only requires that *some* `###` entry exist under
`## [Unreleased]` when `CHANGELOG.md` is staged — it never checks the entry's content against the
staged file list, so two real code fixes (the Stop-hook regex, the decisions.py duplicate check)
initially landed with zero CHANGELOG mention while the gate read green (piggybacking on unrelated
doc entries in the same commit; caught by a review finder, fixed by hand). A correspondence check
(staged code paths ↔ entry text) is buildable but is a new mechanism — per the rollout law, measure
the miss rate first: if reviews keep catching this class, promote; if this was a one-off, don't
build wallpaper. Trigger: the next occurrence of a code change landing entry-less.

## [fleet] .fabrik/state/<id>.json has no durable record of registrar FAILURES (review finding 2026-09-01)

The 01M1CKEK fix makes `fabrik apply`/`redeploy --refresh-infra` exit 2 and print each failed
registrar — but that truth lives only in the one terminal's stdout+exit code. The persisted
state file's 8-field G-F3 schema records `registrars_applied` by omission only; `fabrik
audit-registrars` and the state file both answer "did our last apply finish clean?" with
silence. Fix direction: a `registrar_failures: [...]` field (schema addition — G-F3 consumers:
`state.py` docstring names them) written by `_persist_state`. Deliberately NOT folded into the
01M1CKEK change: a schema change deserves its own consumer sweep. Trigger: the next state-file
or audit-registrars window.

## [infra] tests/orchestrator/test_infrastructure.py's dispatch tests SSH to PROD (measured 2026-08-31)

`TestProvisionDispatch` calls `provision()` with only the per-registrar drivers patched —
`_provision_shared_analytics` and `_provision_watchdog` run REAL: observed live as pytest child
processes `ssh vps sudo docker build -t fabrik/watchdog:my-project` and `ssh vps mkdir -p
/tmp/fabrik-watchdog-build` during a plain local test run, and the box carries a
`fabrik/watchdog:my-project` image built 5 HOURS EARLIER by a previous unnoticed run (leftover;
junk image, removable). A unit suite that mutates the shared VPS on every run is both a prod
hazard and why the suite takes minutes. Fix direction: an autouse fixture (or conftest guard)
that patches `fabrik.drivers.ssh.ssh`/`scp_to_vps` to raise in tests unless a marker opts in —
which also converts the two unpatched provisioning paths into loud failures instead of silent
prod writes. My new `test_registrar_failures_not_green.py` patches both explicitly.
Trigger: next test-infra window; the guard is one conftest fixture.

## [infra] Concurrent pre-commit stash windows DELETED 15 dirty files from the shared tree (live 2026-08-31, recovered)

The daily pipeline's auto-commit (a216a4c2, VPS-docs updater, 19:30 UTC) triggered THREE pre-commit
stash processes within 2 seconds (`~/.cache/pre-commit/patch1788204608-32641`, `patch1788204610-32730`,
`patch1788204610-32863` — preserved in the session scratchpad). The earliest patch records the true
WIP (15 files `M`); the two later ones record the same files as `deleted file mode` — the deletion
happened INSIDE the first hook window, and the last stash-restore faithfully restored the broken
state. Result: 15 tracked dirty files (two sessions' WIP incl. `docs/DECISIONS.md` and
`scripts/final_gate.py`) vanished from the working tree with no process left to restore them.
Recovered same-hour by hand: `git checkout -- <15 paths>` + `git apply` of the earliest patch
(excluding the one survivor file) + the later patch's DECISIONS.md hunk; verified against the
session-start status snapshot, tests green. CLASS: concurrent `pre-commit` runs share one working
tree and one stash namespace; their checkout/apply interleaving is destructive — the same class as
the documented pre-commit-stash near-misses, now with a measured data-loss occurrence. Fix
direction (measure first): serialize hook runs with a repo-scoped lock (flock in a pre-commit
local hook or wrapping the pipeline's commit path), and/or make the pipeline's auto-commit refuse
to run while the tree carries foreign dirty files. Trigger for promotion: this row IS the second
occurrence class-wide — a third means build it without further debate.

## [infra] assemble_commands.render() silently defaults agents_dest to the LIVE ~/.claude/agents (found by a review finder 2026-08-31)

`render(dest)` with `agents_dest=None` resolves to the live installed agents dir
(assemble_commands.py:31,~706) — only the CLI `--check` path passes a temp dir. A read-only review
finder doing `import assemble_commands; render(tmpdir)` for inspection silently OVERWROTE the 4 live
agent files (benign that day — sources unchanged, post-hoc byte-match to a fresh render — but there
was no pre-call snapshot to prove it). Fix direction: `render()` requires an explicit `agents_dest`,
or `_emit_agents` refuses/warns when overwriting a file its own `agent_drift` check would call
HAND-EDITED. Out of plan-1's File Scope (the renderer is not a source/fragment); parked per the
rollout law — the trigger for promotion is a second live mutation.
**PROMOTED + FIXED 2026-08-31:** the second live mutation was measured the same day (T02's verifier's
`--dest` probe); `render()` now derives `agents_dest` from dest (live AGENTS only when dest == OUT,
else `dest/_agents`), red-first proven with 2 regression tests (tests/test_assemble_agents_dest.py).

## [infra] command_run.py `done` never reads round content — the found:0/new:0 conventions are honour-bound at close (found by T02's verifier, 2026-08-31)

`_close()` checks name/state/artifact-existence (6 named commands)/feedback substance — never the last
round's `findings`. A `/design-review` (or any round-convention command) can close `done` after a
`findings: 5` round. Enforcement candidate under the rollout law — but NOT a naive `findings != 0`
refusal: the sanctioned `new: 0` exit legitimately closes with `found > 0` standing rows (the exact
fabrik-review-vs-check_convergence tension T22 of the manifesto pass adjudicates). Design the check
AFTER T22 settles which exit vocabulary is canonical; promotion trigger = T22's ruling + one measured
false close. **T22 RULED 2026-08-31 (D-048): the quiet `found: 0 · fixed: 0` exit is canonical —
re-raises of adjudicated standing rows are cited, never counted — so a naive `findings != 0` refusal
is now designable; remaining trigger = one measured false close.**

## [infra] release_cut.py stages only CHANGELOG.md — a same-commit DECISIONS.md cut-row is impossible; the versioning-adoption carve-out itself has no ledger row (found by T20's verifier, 2026-08-31)

`release_cut.py:149,162` hardcodes `git add -- CHANGELOG.md` / `git commit -- CHANGELOG.md`, so the
manifesto-pass mint law ("built X at vY" → its `docs/DECISIONS.md` row) cannot ride the cut commit —
`/fabrik-release` now instructs an ADJACENT commit in the same push and says why (the honest recipe,
not the preferred one). Fix direction when promoted: `release_cut.py` stages `docs/DECISIONS.md` when
modified (or gains `--extra-path`), restoring same-COMMIT atomicity. Related provenance gap the same
verifier measured: the "versioning adoption" carve-out the command description cites ("the one
sanctioned publish-shaped act") has ZERO hits in `docs/DECISIONS.md` — the standing policy lives only
in prose; mint its provenance row when the operator confirms. Out of plan-1's File Scope (scripts/).
Promotion trigger: the first cut that actually mints a row (proves the two-commit shape in anger).

## [infra] No fixture test asserts the corpus's own quoted exit strings parse under the graders (found by the fresh corpus review's native finder, 2026-08-31)

The finding-2 class (a completion sentence naming a ledger shape `check_convergence.py`/
`check_review_coverage.py` reject) was only findable by hand-running the graders on a constructed
fixture — prose and grader can drift with zero mechanical signal. Candidate: a ~10-line test that
extracts the exit-row examples quoted in `commands/_sources`/`_fragments` and asserts they parse
under `_pass_counters` + QUIET_PASS. Measure-first per the fix directive: one confirmed occurrence
so far (the `found: 0 · new: 0` two-token QUIET sentence, fixed 2026-08-31); promote if the class
recurs. Trigger: the next prose-vs-grader mismatch found by any review.

## [infra] Two dead fragments: grounding-research + grounding-rules-cite (0 consumers, 0 renderer refs — found by the fresh corpus review round 5, 2026-08-31)

`grep -l "{{include:<name>}}" commands/_sources/*.md` returns 0 for both, and `assemble_commands.py`
names neither (unlike `close-feedback`/`agent-feedback`, which are auto-appended). Either dead files
to delete in a maintenance pass, or a second injection path nobody documented — decide, then either
delete or document. Pre-existing (not touched by the manifesto-pass diff).

## [infra] check_command_corpus.py never grounds scaffold-type enumerations against SCAFFOLD_TYPES (found by the fresh corpus review round 12, 2026-08-31)

`office-extension` (registry since D-039) was absent from all 57 corpus files while the checker
printed green — it validates chain targets/scripts/trailers but not type enumerations. Measured
fire rate at promotion time: 7 files enumerated ≥3 registry types with ≥1 omitted (all fixed
in-round; the checker would have been red on real drift, green after). Fix direction: import
SCAFFOLD_TYPES, fail when a corpus file enumerates ≥3 registry types yet omits one. Promote on the
next registry-drift recurrence.

## [infra] Mailbox-clear 2026-08-31 — accepted-direction majors (each cites its finding mail)

- **final_gate --json honesty cluster** (01M19R99M, 01M1CAE2F4): `degraded:[...]` key for
  NOT-INSTALLED tools; `passed` as a list of check names; a status-level warning when the diff adds
  N test files and the gate ran none; tolerate DECLARED opt-in skips in the skip-advisory.
- **WATCH: wef arms `.fabrik/run-pytest` when two lanes go green** (01M1CW5P): their intake lane
  committed to arming the sentinel same-day once the section-registry 29 + content-lane 7 test
  failures are fixed by their owners. Conditional offer, tracked nowhere until this line — if a
  future wef status shows both groups green and no sentinel, this is the thread to pull.
- **Fleet-check design law: import-and-call, never source-grep** (01M1CWKE, wef's glitchtip-PII fix):
  a source grep passes on a commented-out flag, a dead branch, or a shadowed kwarg — their test
  captures the ACTUAL kwargs reaching sentry_sdk.init. Binding on any future fleet-wide config
  sweep check (PII flags, security kwargs); recorded here so the advice outlives the ack.
- **Stop-hook resumed-session false positive** (01M19970HP): `final_gate_stop.py:573-580,1228-1229`
  re-fires "UNREVIEWED SPONTANEOUS WORK" after a record closed — scope the authored set to
  uncommitted∩dirty, or let a closed review-family record satisfy has_any_record.
- **transdoc post-mortem corpus candidates** (01M19YFM2F): walking-skeleton mandate, seam-test
  floor (generated OpenAPI client only), core-journey certification at phase boundaries, MVP tier
  in FEATURES EARLY — four dispositions, each a design change; take as one corpus pass.
- **READ-budget waiver for narrow edits to a pre-existing monolith** (01M1A6SSEY — youtube is
  mechanically BLOCKED on this): line-range Touches syntax or a gate-recognized waiver line.
  PRIORITY: a live plan cannot flip.
- **check_review_coverage formatting-fix ratchet** (01M1CA0WJ3): a parser-visible formatting repair
  to a COMMITTED review escalates advisory→hard gate; exempt edits whose parsed counter rows are
  value-identical before/after.
- ~~**Synced per-repo DECISIONS duplicate-id gate check**~~ ✅ **LANDED 2026-09-01** (01M1CBJWQS →
  D-057 sequencing → wef repair 5a58c11 + reply 01M1CW4S = the trigger → `check_decisions_unique.py`,
  WARN-tier, keyed on the row ID CELL per wef's repair-experience request, 0/49 fleet ledgers firing
  at landing — verify: `for f in /opt/*/docs/DECISIONS.md; do grep -oE "^\| D-[0-9]+ \|" "$f" | sort | uniq -c | awk '$1>1'; done`). Remaining half deliberately unbuilt: the origin/HEAD stale-max WARN needs a fetch —
  revisit only if collisions recur despite detection + pull-before-mint. wef's generalization
  learning recorded in the check docstring: BOTH-CITED is the common case; first-committed carries
  the tiebreak.
- **mcp-config-changed hook precision** (01M1BXBRKM): name WHICH servers changed / suppress when
  the repo-assigned set is unaffected (false-fired on wef3 AND on this session today). ALSO
  (operator, 2026-09-01: "i restarted all windows why does you and all agents keep saying"): the
  warning re-fires on EVERY prompt of a resumed conversation — a window restart cannot clear it
  (resumed conversations keep the old tool universe by design; only a NEW conversation gets the
  new roster). Add told-once suppression per session, and say "start a NEW chat" not "reload".
- **tech-stack guide engine-neutral ecommerce row** (01M19G0HM0 + correction 01M19G66X8): replace
  the Vendure default with the choice criterion (copyleft tolerance, payment-provider availability);
  point iyzico-reaching projects at fabrik-lib payments/ first.
- **release HANDOFF closed-by overlay** (01M1A00DS1): an appendable `closed-by <commit/test>` line
  in the grammar so closure doesn't require editing a ratcheted report.
- **waitForHydration adoption** (01M1B0BHZN): replace the hand-rolled networkidle+waitFor pattern
  in the certification fragment with fabrik-lib's `@fabrik/ui-verify` primitive.
- **deploy triad remainder from the consolidated v3** (01M1C95A2S): infra-wiring FLOOR (name the 10
  registrars), supersede step-diff, rollback-on-failure semantics, cumulative window expiry, S0
  credential write-time verification, citation-precision check. (F11 quoting + F12 redaction +
  F14 amend-trailer + cold-start + capability-check are DONE.)
- **[fleet] subagents fleet re-vendor sweep** (01M1B35GKQ): NVIDIA_API_KEY dotenv fix + lane_chain
  landed upstream; every vendored copy behind.
- **[intel→fabrik-lib] fanout resilience** (01M1CGKVWC): pre-flight credits check, 402/404 unit
  re-route to next ranked model, dead-unit count surfaced in the return. OPERATOR: OpenRouter
  credits tail is SPENT — top-up needed.
- **I1 watch item** (01M1CCNMGT): auto-mode permission-classifier outages (31× in one project) are
  indistinguishable from agent stalls — harness-level; watch for recurrence post-CLI-updates —
  and it fired AGAIN on this very session while this row was being written.
- **[infra] fabrik-researcher brief + grounding fragment drift** (2026-09-02, 10 dispatches, 10/10
  reported it): the agent has NO shell, so a brief that says "run `awk …`" is unexecutable (each agent
  substituted Grep+Read; the dispatch template should give a Read/Grep recipe); the fragment's claim that
  non-HTML (JSON) content is unreachable via exa was refuted twice in one day (api.bls.gov and
  api.cerebras.ai JSON fetched raw); WebFetch does not follow cross-host redirects (api.slack.com →
  docs.slack.dev, cloud.google.com → docs.cloud.google.com cost a full extra round each) and truncates
  long pages silently then asserts a NEGATIVE ("no Outlook section") — WebFetch output must be treated as
  bounded-search evidence, never as a negative. Fix in `commands/_sources/_fragments/` at next touch.
- **[infra] check_subagent_flywheel: on shared master the cycle boundary is HEAD** (2026-09-02, /fabrik-review):
  the check counts local-ledger pool rows newer than `merge-base HEAD <ref>`, which on a shared master
  with no branch is HEAD itself — so a SIBLING's commit at 13:34 made this session's four pool review
  rows from 13:19 "not this cycle" and the gate BLOCKED a run that had used the pool minutes earlier.
  Measured once; the fix candidates (key the window on the staged files' oldest mtime, or on the last
  commit AUTHORED by this session) need a fire-rate measurement before shipping (FIX verb 5). Until
  then a later-pass pool dispatch re-satisfies it.

## [infra] fabrik-review finder brief: pin the ledger high-water mark AND finder imports to a sha (found by the external-services review pass 9, 2026-09-02)

The pass-9 Opus finder, briefed on commit `fae20651` with reads pinned to `git show <sha>:<path>`,
still `sys.path.insert(0, "/opt/fabrik/scripts")`-imported the LIVE modules for its measurement
scripts — and the live tree carried a sibling's uncommitted `is_credential` edit for ~20 min of the
run, so three measurements reported on the wrong code (caught by `inspect.getsource()` vs the diff).
The same brief named the standing-row scope as letters ("P…AF, AG1") while the worktree ledger
already held AH1/AH2, so a pass was spent re-deriving a fixed row. Two edits to the finder brief in
`commands/_sources/fabrik-review.md` (+ the finder fragment): (1) "measure by extracting the pinned
sha to a sandbox and asserting the loaded module's provenance — never import from the live tree on a
shared master"; (2) "state the ledger's high-water mark as the review file's sha/timestamp at
dispatch". Not applied mid-run: a corpus edit renders box-wide and needs its own scoped review.
Related: [[feedback_test_real_invariant_not_proxy]] (this session's own flip-set measurement was
vacuous for the same reason — a temp-loaded module found no catalog — until the paths were pinned).
