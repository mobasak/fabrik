# Plan — Watchdog deploy-side: GlitchTip payload capture + Tier-D driver wiring

**Status:** IN PROGRESS — Phase A tooling shipped + validated; **Phase B complete**; **Phase C code complete, OFF BY DEFAULT, awaiting the diff-review checkpoint before any `fabrik apply`**. §5 unknowns all resolved from fabrik-lib (see §5). Phase C: `auto_code_fix`/`code_fix_window_sec`/`critical_paths` spec fields + validator, rendered consumer `bootstrap.py`, conditional Dockerfile CMD switch, Tier-D env, deploy-time gates (git-remote hard-fail, no-HEALTHCHECK degrade). Default path byte-identical. All four bootstrap import paths + ctor args verified against the live library; unit-tested SSH-free. **Not yet enabled on any project; no fleet mutation performed.**
**Date:** 2026-06-29
**Owner:** Fabrik AI (`/opt/fabrik`, fleet/deploy side)
**Origin:** Two issues handed off from the fabrik-lib watchdog autonomous-remediation work (PR #1, branch `feat/watchdog-autonomous-remediation`). This plan covers only the `/opt/fabrik` half. The library half (`/opt/fabrik-lib`) is the other agent's.

## Operating model — pro-grade, AI-managed, (mostly) fully-automated dev → deploy → VPS

This pipeline is AI-managed and automated end to end: scaffold → spec → `fabrik apply` (SSH + Docker Compose to the VPS fleet) → watchdog observe/remediate. The design bias follows:

- **Manual operator steps are defects to automate, not the plan.** Wherever this plan says "operator does X in a UI", treat it as a TODO to drive X via API / container exec / declarative spec. The one residual manual step (GlitchTip's alert→webhook — no REST API) is automatable via the GlitchTip container's Django management/admin on the VPS (full fleet access available, `sudo docker` confirmed) with n8n (`auto.vps1`, on the `fabrik` net) as the listener; Phase A's tool already does capture/teardown — only the alert wiring remains to automate.
- **Everything is testable + dry-runnable.** Each driver/tool ships test files so changes are unit-tested and `dry_run=True`/`--dry-run` exercised without touching the fleet (`tests/test_watchdog_driver.py`, `tests/test_glitchtip_webhook_capture.py`, `tests/test_check_ai_pack_freshness.py`).
- **Autonomy with automated guardrails, not manual gates.** Tier-D auto-applies on the silence-window with tests + secret-scan + auto-rollback + STOP; the rails are automated. Human-in-the-loop is the exception (high blast radius), not the default.
- **Specs are the source of truth.** Hand-deployed live infra gets reconciled into declarative specs so `fabrik apply` owns it (done this pass for GlitchTip → `specs/infrastructure/glitchtip.yaml`).

---

## 0. Validation of the handoff (what's true vs. stale)

| Handoff claim | Reality | Source |
|---|---|---|
| "driver not yet shipped" | **Stale — it exists.** Builds image, writes `compose.watchdog.yaml`, brings the sidecar up. Lacks Tier-D wiring + deploy-key + app healthcheck. | `src/fabrik/drivers/watchdog.py` |
| design spec at `docs/superpowers/specs/…` | **Not in `/opt/fabrik`.** Authoritative set is in fabrik-lib. | `/opt/fabrik-lib/docs/superpowers/specs/2026-06-28-watchdog-autonomous-remediation-design.md` + 7 plans + convergence-review |
| Tier-D contradicts the rule packs | **Resolved** — Tier-D canonical, synced fleet-wide, gate-green. | `convergence-review.md:40`; `.windsurf/rules/core/60-watchdog.md:77-105` |
| issue 1 = "confirm field set" | **Bigger** — the parser is a pure function **not wired into the bus** (`TriggerBus(sources={})`), no HTTP ingest exists, and GlitchTip exposes **no API** to read webhook config/logs. | `agent.py:623-624`; `error_tracker_webhook.py:109-123`; `docs/reference/glitchtip-api.md` |

**Conclusion:** both issues are real and worth doing; the framing was stale. Net scope is larger than the handoff implied (deploy-key + app-healthcheck + bus-wiring are prerequisites, not afterthoughts).

---

## 1. Cross-repo boundary (who owns what)

- **`/opt/fabrik` (this plan):** the driver that renders/mounts/injects so the sidecar self-configures; the GlitchTip capture harness + fixture + drift-check.
- **`/opt/fabrik-lib` (other agent):** the `configure()` consumer planes already exist; **but** the error-tracker trigger source is *not registered* in the bus and there is *no HTTP ingest* — wiring that is a **fabrik-lib** task (flagged below as a dependency for the end-to-end error-tracker trigger, NOT for issue 1's capture deliverable).

---

## 2. Issue 1 — GlitchTip webhook payload: capture, pin, and keep pinned

### 2.1 Why it can't be an API read
GlitchTip's documented API (`docs/reference/glitchtip-api.md`) covers only project create / DSN fetch / delete / list-teams — **no** alert-rule, webhook-recipient, or delivery-log endpoint, and **no** documented event-ingest endpoint. So the only way to see the real outgoing envelope is to **receive it at a listener** after a real event.

### 2.2 The parser we must pin against
`from_payload` (`/opt/fabrik-lib/watchdog/.../error_tracker_webhook.py:109-123`) tries the Slack-style **envelope** first, then a Sentry **issue** fallback:
- envelope: `attachments[0].title` (`:49`), `title_link`→url (`:52`), `color`→severity (`#e52b50`/`red`→urgent, `:54`), leading exception class→`error_type` (`:55`).
- fallback: `issue.title|message` (`:94`), `issue.metadata.type` (`:96`), `issue.level|severity`→hint (`:98-100`).

The current fixture (`test_trigger_error_tracker_webhook.py:6-27`) is **hand-constructed, not live-captured** — that's what we replace.

### 2.3 Capture harness (the permanent, automated workflow)
New `scripts/probes/glitchtip_webhook_capture.py` (reusing `drivers/glitchtip.py`: `_headers` `:202`, `create_project` `:281`, `_fetch_dsn` `:257`, `delete_project` `:341`):

1. Create a disposable project `__watchdog-webhook-probe` (idempotent; cleaned up at end).
2. Stand up a capture listener. **Preferred:** an n8n webhook node on the existing `auto.vps1.ocoron.com` n8n (`specs/infrastructure/n8n.yaml:11`) that logs the verbatim body to a file; **fallback:** a one-off `http.server` on a reachable port. (The webhook→listener wiring inside GlitchTip is the one manual UI step if no alert-rule API exists — the script prints exact instructions and waits.)
3. Send a real error event into the project via its DSN (Sentry `store`/`envelope` ingest using the fetched DSN).
4. Persist the **verbatim** JSON to `docs/reference/fixtures/glitchtip-webhook-<integration>.json` + record the active integration name.
5. Tear down the disposable project.

### 2.4 Pin + drift-check
- Hand the captured JSON to the fabrik-lib agent to assert the parser against the real fixture (their offer).
- Add `scripts/probes/glitchtip_webhook_capture.py --verify` mode: re-run capture (or re-load the fixture) and assert the parser's field map still resolves all of `name/url/severity_hint/error_type` non-empty. Wire it into the daily WSL pipeline as **warn-only** (mirrors `check_ai_pack_freshness.py`) so an envelope change is flagged, not silently broken.

### 2.5 Enablement gating
Leave the error-tracker source **out** of `WATCHDOG_TRIGGER_SOURCES` (default `emitter,health`, `bus.py:19`) until (a) the fixture is pinned **and** (b) fabrik-lib registers the source token + ingest. Document this as a cross-repo dependency; until then the trigger source is dormant by design.

### 2.6 Evidence (Issue 1)
- No webhook/alert/log API: `docs/reference/glitchtip-api.md` (create/keys/delete/teams only).
- Parser branches: `error_tracker_webhook.py:37-67` (envelope), `:70-106` (fallback).
- Bus default + unwired source: `bus.py:19`, `agent.py:623-624`.
- Reusable driver surface: `src/fabrik/drivers/glitchtip.py:202,257,281,341`.

---

### 2.7 Phase A status — tooling shipped + automatable parts validated (2026-06-29)

Built `scripts/probes/glitchtip_webhook_capture.py` (modes `inspect`/`lifecycle`/`send-test`/`listen`/`verify`/`cleanup`) + `tests/test_glitchtip_webhook_capture.py` (8 drift-check cases).

Validated live from the hub:
- **`inspect`** — confirmed (not assumed) the **no-alert-API** constraint: `/rules/`, `/alert-rules/`, `/alerts/` all 404 at `errors.vps1.ocoron.com` (org/team `ocoron`/`vps1`).
- **`lifecycle`** — disposable project create → DSN fetch → delete round-trips cleanly (auto-deleted, no leftover). Caught + fixed a real call-signature bug along the way (`create_project(name, platform=…)` — the 2nd arg is `platform`, not a description).
- **`verify`** drift-check — 8 hermetic tests green.

**Correction to §2.4:** the drift-check cannot run unattended-daily — capture requires a live event reaching a **VPS-reachable listener**, and the hub sandbox is not reachable by the VPS (and there is no alert-config API). So `verify --check` is a **post-capture / CI** guard, **not** a `wsl_startup_hook.sh` step (not wired in).

**Operator hand-off (the one step the missing API forces):** `listen` on a VPS-reachable host → GlitchTip UI: add a webhook recipient = that listener URL on a "new issue" rule → `send-test` (or a real error) → captured fixture lands at `docs/reference/fixtures/glitchtip-webhook.json` → hand to the fabrik-lib parser-pin → `cleanup`. Runbook is in the tool docstring.

Phase A is **complete to the limit of what the hub can reach**; the live fixture capture is the operator's one manual step.

### 2.8 Live fixture CAPTURED — Issue 1 resolved (2026-06-29)

The "one manual step" was **eliminated**, not performed manually. Instead of the UI alert→webhook + live-event dance, the envelope was captured by invoking GlitchTip's **own** sender (`apps/alerts/webhooks.py::send_issue_as_webhook`, which serializes `asdict(WebhookPayload)` — line 142/88) inside the live `glitchtip-web` Django shell against a representative **in-memory** `Issue` (monkeypatching `send_webhook` to intercept the exact outgoing JSON). **Strictly read-only** — no DB rows created (an unsaved Issue + synthetic id); the only writes were the disposable probe project via the tool's REST path (auto-cleaned). The `recipient_type='webhook'` ("General Slack-compatible webhook", confirmed from `AlertRecipient` choices) is the type whose envelope matches the parser's primary branch.

Captured envelope (verbatim) → `docs/reference/fixtures/glitchtip-webhook.json`:
`{text:"GlitchTip Alert", attachments:[{title:"<ExcClass: msg>", title_link:<issue url>, text:<culprit>, color:"#e52b50", fields:[{title:"Project",…}], mrkdown_in:["text"]}]}`

`verify --check` **green** — all four parser fields resolve (`name`/`url`/`severity_hint`(color #e52b50→urgent)/`error_type`(leading class)). One real wart recorded in the fixture: `title_link` is `http://localhost:8000/…` because `GLITCHTIP_DOMAIN` is the loopback host on the live app — this is the value GlitchTip actually emits; the parser only needs `url` present.

**Still cross-repo (R-G):** hand the fixture to the fabrik-lib agent to pin `from_payload` against it, and register the error-tracker source token + HTTP ingest there before the trigger fires end-to-end. The capture deliverable does not depend on that.

## 3. Issue 2 — extend `drivers/watchdog.py` to deploy the Tier-D planes

### 3.1 The central architectural fact
The library **ships ops-only**: `configure()` is **never called** — `agent.main()` only reads `get_deps()` which defaults to an empty `OrchestrationDeps()` (`__init__.py:39,48-50`; `agent.py:621`). `code_fix_enabled` requires **all four** of `deploy_adapter`, `remediator`, `telegram_bot`, `approval_manager` non-None (`coordinator.py:42-50`). So:

> The driver must render a **consumer bootstrap** that constructs the four planes (with project-specific constructor args) and calls `configure(...)` **before** `agent.main()`. The library stays deploy-agnostic by design (`design.md:131-132,170-171`); the bootstrap is the consumer's job and lives in the per-project build context, not the lib.

`GitPushDeployAdapter(repo_dir, deploy_branch="main", redeploy_cmd=None, push=True, runner=subprocess.run)` (`deploy_adapter/git_push.py:14-27`); canonical `redeploy_cmd=["ssh","vps1","fabrik","redeploy","<id>"]` (`deploy-adapter.md:564-567`).

### 3.2 Prerequisites (pre-existing gaps that block Tier-D **and** today's `propose_fix_prs`)
1. **Deploy key is documented but unimplemented.** Docstring claims it (`watchdog.py:20-24`) but there is no `ssh-keygen`/mount; the image already expects it at `/var/lib/watchdog/keys/git-deploy.key` via `GIT_SSH_COMMAND` (`Dockerfile:118-121`). → Implement generate-once + mount RO mode 600. (Standalone value: unblocks the existing PR path too.)
2. **App-container HEALTHCHECK.** `verify_health` defaults to PASS unless docker reports literal `"unhealthy"` (`coordinator.py:430-441`; `agent.gather_snapshot` `:198-207`); with no HEALTHCHECK, auto-rollback-on-health is a **no-op**. → Driver must ensure the watched app has a real `HEALTHCHECK` (or inject a custom `verify_health`), and consider `depends_on: condition: service_healthy` (today it's a bare list, `watchdog.py:395`).
3. **`SIDECAR_SOURCE` path mismatch — RESOLVED 2026-06-29.** Constant was `…/watchdog/sidecar/`, but fabrik-lib renamed the tree to `…/watchdog/watchdog_sidecar/` (Jun 29), so `_build_image()` would abort on **every** watchdog `fabrik apply` today (the live `watchdog-test` image was built 2026-06-04, pre-rename — that's why it exists but a fresh apply would fail). Fixed `watchdog.py:92` + docstring; regression-guarded by `tests/test_watchdog_driver.py::TestSidecarSource`. A driver test file (dry-run + render-context + path guard, no SSH) now exists so this class of break is caught.
4. **Driver bypasses Pydantic.** It reads raw `wcfg.get()` with its own defaults (`watchdog.py:248-273`), not `WatchdogConfig`. → Any new field must be threaded through **4** sites.

### 3.3 Spec opt-in
Add to `WatchdogConfig` (`spec_loader.py:335`, `extra="forbid"` so mandatory): `auto_code_fix: bool = False` and `code_fix_window_sec: int = 300` (per `60-watchdog.md:79`). Thread through `_RenderContext` (`watchdog.py:116`), `_build_render_context` (`watchdog.py:248`), `_render_env` (`watchdog.py:470`).

### 3.4 What the driver renders/mounts/sets when `auto_code_fix: true` (and only then)
1. **Bootstrap** rendered into the build context (e.g. `bootstrap.py`) that `configure(...)`s the 4 planes with this project's `repo_dir` (the remediator's isolated clone), `deploy_branch`, `redeploy_cmd=["ssh","vps1","fabrik","redeploy","<id>"]`, `approval_window_sec=code_fix_window_sec`, `critical_paths` (from `WATCHDOG_CRITICAL_PATHS`), then calls `agent.main()`. CMD switches to the bootstrap **only** in the opt-in path; default path keeps `python3 -m watchdog_sidecar.agent` (`Dockerfile:161`) → backward-compatible.
2. **Deploy key** mounted RO at `/var/lib/watchdog/keys/git-deploy.key` (prereq #1). `GIT_SSH_COMMAND` already baked in the image — driver only mounts the key.
3. **`claude-settings.json`** already rendered (`watchdog.py:288-296`); confirm `WATCHDOG_CLAUDE_SETTINGS` points at the rendered file, not `.template` (fixer reads it, `remediation/fixer.py:36-40`).
4. **Env**: add `WATCHDOG_AUTO_CODE_FIX`, `WATCHDOG_CODE_FIX_WINDOW`/`WATCHDOG_APPROVAL_WINDOW_SEC`, `WATCHDOG_CRITICAL_PATHS`, `WATCHDOG_TELEGRAM_BOT_TOKEN`/`_CHAT_ID`, `WATCHDOG_TEST_CMD`, ensure `WATCHDOG_PROJECT_GIT_REMOTE` is set (it is, `watchdog.py` env list) — **not** the deprecated `WATCHDOG_REPO_URL/_TOKEN` (`orchestration.md:944`). Telegram/window read by `control_plane/telegram_bot.py:71,76` + `control_plane/approval.py:34`.
5. **App HEALTHCHECK** (prereq #2).

### 3.5 Honor the Tier-D contract (`60-watchdog.md:77-105`)
Opt-in only; tests-gated (HARD); secret-scanned diff; Telegram Approve/Reject/STOP with silence-window auto-apply; isolated clone (never the RO `/project` mount); every apply/rollback → `deploys` table, approval → `approvals`; auto-rollback on VERIFY regression; STOP kill-switch. The driver renders the wiring; the library enforces the gates.

### 3.6 Evidence (Issue 2)
- configure never called / empty default: `__init__.py:39,48-50`, `agent.py:621`, `coordinator.py:42-50`.
- adapter signature: `deploy_adapter/git_push.py:14-27`.
- verify_health no-op without healthcheck: `coordinator.py:430-441`, `agent.py:198-207`.
- driver gaps: `watchdog.py:20-24` (key docstring, unimplemented), `:92` (path), `:248-273` (raw wcfg), `:395` (bare depends_on), `:468-498` (env).
- spec gap: `spec_loader.py:335-519` (no `auto_code_fix`).
- Dockerfile contract: `Dockerfile:112-121,135-145,152-153,161`.

---

## 4. Sequencing & risk

1. **Phase A (low risk, no prod mutation): Issue 1 capture harness + fixture + drift-check.** Touches a disposable GlitchTip project + a listener; read-mostly. Unblocks the parser pin.
2. **Phase B (prereqs): deploy-key impl + `SIDECAR_SOURCE` verify + app-healthcheck rendering.** Standalone value (fixes the existing PR path). No new autonomy yet.
3. **Phase C (prod-affecting, gated): spec fields + bootstrap + `configure()` wiring + env.** Behind `auto_code_fix` opt-in; default path byte-identical. **Requires a diff review checkpoint before any `fabrik apply`** — this is the only code that can mutate prod.

**Risk posture (single-operator threat model):** the danger here is not an attacker but an *unintended autonomous prod change*. Mitigations are the Tier-D contract gates (opt-in + tests + secret-scan + Telegram + silence-window + auto-rollback + STOP + audit). Phase C ships **off by default**; first enablement should be one non-critical project with the operator watching.

**Cross-repo dependency:** the end-to-end error-tracker *trigger* (issue 1's downstream) needs fabrik-lib to register the source token + ingest (`agent.py:623-624` `sources={}`). Issue 1's deliverable (captured fixture) does not depend on that.

---

## 5. Open design decisions — ALL RESOLVED 2026-06-29 (pinned from fabrik-lib)

1. **`repo_dir` identity — RESOLVED: the stable per-project clone, not a separate checkout.** `agent.propose_fix` (`agent.py:388-422`) clones idempotently into `PROPOSED_WORKSPACE_ROOT/<project_id>` (= `/var/lib/watchdog/proposed/<id>`) once, then `fetch`+`reset --hard origin/HEAD`+`checkout -B watchdog/<incident>` each incident — the **directory is stable**, only the branch is per-incident. `remediator.remediate(ws,…)` operates in `ws.path` (= that dir); `GitPushDeployAdapter.apply(branch)` operates in its constructed `repo_dir` and merges the per-incident branch into the deploy branch. So the bootstrap constructs `GitPushDeployAdapter(repo_dir=/var/lib/watchdog/proposed/<id>)` once and passes the branch at call time. (`coordinator.py:281-300,410-417`; `git_push.py:14-27,44-57`.)
2. **Constructor args — RESOLVED & verified live.** `configure(**kwargs)→OrchestrationDeps` (`__init__.py:42-45`; deps fields incl. `approval_window_sec`, `critical_paths` at `coordinator.py:28-50`). `GitPushDeployAdapter(repo_dir, deploy_branch="main", redeploy_cmd=None, push=True, runner=subprocess.run)`. `Remediator(test_cmd: list[str], max_attempts=2, …)` — `test_cmd` REQUIRED. `TelegramBot(token, chat_id, http=None)` + `.from_env()` (reads `WATCHDOG_TELEGRAM_BOT_TOKEN`/`_CHAT_ID`). `ApprovalManager(state_conn, window_sec=None, *, state=None)`. The bootstrap opens `state.connect(STATE_DB_PATH)` (same `STATE_DB_PATH` `agent.main()` uses, `agent.py:614`). All import paths + args statically re-verified against the live package.
3. **Bootstrap vs. conditional entrypoint — RESOLVED: separate `bootstrap.py` + CMD switch.** The library CMD is the single `CMD ["python3","-u","-m","watchdog_sidecar.agent"]` (`Dockerfile:161`); there is no env-branch hook. The driver renders `bootstrap.py` at WORKDIR (`/home/watchdog/sidecar`, next to the package so `import watchdog_sidecar` resolves) and replaces the CMD with it **only** in the `auto_code_fix` path — default image byte-identical. A guard hard-fails the build if the upstream CMD string ever changes (so the patch can't silently no-op).
4. **App HEALTHCHECK source — RESOLVED: detect + gate, never inject.** The driver can't own the app's `compose.yaml` (`SSHDeployer` does), so it inspects the running app container and **degrades Tier-D to escalate-only** when no HEALTHCHECK is present (R-B), rather than synthesizing one or shipping blind auto-rollback. `verify_health` left at the library default (it reads docker health, which the pre-flight now guarantees is meaningful).

---

## 6. Self-audit

- **Grounding:** every phase cites real `path:line` across both repos (verified by three independent read-only investigations 2026-06-29). No step rests on an assumed API.
- **Known unknowns surfaced, not hidden:** `repo_dir` identity, three plane constructors, `SIDECAR_SOURCE` resolution — all listed in §5 as resolve-at-implementation, not silently assumed.
- **Scope honesty:** the handoff under-scoped this (deploy-key + healthcheck + bus-wiring). This plan states the true scope.
- **Not claimed:** this is DRAFT; nothing is built, no live call made, no "converged"/"done" claim. The prod-affecting phase is explicitly gated behind a review checkpoint.
- **Reversibility:** Phases A/B are reversible; Phase C ships off-by-default and is itself reversible (auto-rollback + STOP).

---

## 7. Residual risks & mitigations

Every residual risk this plan carries, with how it is addressed — none left merely "accepted":

| # | Residual risk | Mitigation in this plan |
|---|---|---|
| R-A | **Phase C can auto-apply code to prod** (the core hazard). | Ships **off by default** (`auto_code_fix: false`), enabled per-project. Tier-D gates every apply: tests HARD-gate, secret-scan, Telegram Approve/Reject/STOP, silence-window, auto-rollback on VERIFY regression, STOP kill-switch, full `deploys`/`approvals` audit (`60-watchdog.md:77-105`). First enablement on one non-critical project, operator watching (§4). |
| R-B | **`verify_health` is a no-op without an app HEALTHCHECK** → auto-rollback can't fire (`coordinator.py:430-441`). | Phase B renders/requires an app-container `HEALTHCHECK` (or injects a custom `verify_health`); Phase C refuses to enable Tier-D for a project lacking one — degrade to escalate-only rather than ship blind auto-rollback. |
| R-C | **Deploy key documented but unimplemented** → autonomous push *and* today's `propose_fix_prs` silently fail (`watchdog.py:20-24` vs none; `Dockerfile:118-121`). | Phase B implements generate-once + RO mode-600 mount at the path the image already expects; Phase C depends on it. Standalone value (unblocks the existing PR path). |
| R-D | **`SIDECAR_SOURCE` path mismatch** (`watchdog.py:92` `sidecar/` vs real `watchdog_sidecar/`) — build may already not resolve. | Phase B step 1 is a **blocking pre-check**: verify what `fabrik apply` actually resolves before any extension. |
| R-E | **Driver bypasses Pydantic defaults** (raw `wcfg.get()`, `watchdog.py:248-273`) → a new field can diverge in two places. | Thread `auto_code_fix`/`code_fix_window_sec` through all 4 sites + a test asserting driver default == Pydantic default. |
| R-F | **Four unresolved design unknowns** (`repo_dir` identity; Remediator/TelegramBot/ApprovalManager constructors; bootstrap-vs-entrypoint; healthcheck source). | §5: each pinned from the fabrik-lib design docs **before** writing Phase C code — none assumed. |
| R-G | **Cross-repo dependency:** error-tracker trigger can't fire end-to-end until fabrik-lib registers the source token + ingest (`agent.py:623-624` `sources={}`). | Issue-1's deliverable (captured fixture) does **not** depend on it; the source stays out of `WATCHDOG_TRIGGER_SOURCES` until both halves land. Coordinate with the fabrik-lib agent. |
| R-H | **GlitchTip capture needs a live event + listener** (no API to read webhook config/logs). | Phase A uses a **disposable** project (auto-cleaned) + a controlled listener; the one manual step (alert→webhook UI wiring) is printed and waited on; a warn-only daily drift-check keeps the fixture honest thereafter. |

Each risk is eliminated within a phase (R-B/C/D/E), gated off-by-default with reversibility (R-A), pinned-before-code (R-F), or explicitly sequenced/coordinated across repos (R-G/H).
