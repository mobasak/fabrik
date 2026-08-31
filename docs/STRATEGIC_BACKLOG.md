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
  at landing). Remaining half deliberately unbuilt: the origin/HEAD stale-max WARN needs a fetch —
  revisit only if collisions recur despite detection + pull-before-mint. wef's generalization
  learning recorded in the check docstring: BOTH-CITED is the common case; first-committed carries
  the tiebreak.
- **mcp-config-changed hook precision** (01M1BXBRKM): name WHICH servers changed / suppress when
  the repo-assigned set is unaffected (false-fired on wef3 AND on this session today).
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
