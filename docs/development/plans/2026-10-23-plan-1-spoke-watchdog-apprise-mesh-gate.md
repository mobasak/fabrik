# Plan — spoke watchdogs alert through a mesh-only Apprise gate

Status: CONVERGED
Profile: small
**Owner:** fleet
Spec: `docs/superpowers/specs/2026-10-23-spoke-watchdog-apprise-mesh-gate-design.md` (CONVERGED, D-1166)
Work item: W-5dcafaef

**Goal.** Implements the spec's § Goal: a spoke watchdog sidecar alerts through `apprise-mesh-gate` on
`10.99.0.1:8202`, the registrar renders that URL for spoke targets, runs the Claude-login (and, on a spoke, gate)
preflight, and stops refusing spoke watchdogs; spoke-canary drops its opt-out and is the acceptance proof.

**Shape decision.** `Profile: small` monolith, three phases. The spec's own size verdict is about 90 code lines
across 5 code/config files (spec § Size verdict, `:8-12`), inside D-169's ≤ ~400 lines and ≤ 5 code files; the
docs edits are not code. Execution is INLINE (the orchestrator codes each phase in this worktree).

## What we already agreed

All rows cite the CONVERGED spec; approval row D-1166 exists (`docs/DECISIONS.md:1165`), so no approval row is
minted here.

- The gate: an nginx allow-list service beside Apprise, admitting only `POST /notify/alerts` — spec § Chosen
  approach (`:142-196`).
- The attachment lock `APPRISE_ATTACH_SIZE: "0"` — spec § Chosen approach, "The attachment lock" (`:198-201`).
- The spoke URL rewrite `_rewrite_mesh_gated_url` — spec "The spoke URL" (`:203-212`).
- Lift the D-1153 refusal in three places — spec "The spoke refusal is lifted" (`:214-220`).
- The login preflight on every target, real runs only, gate probe on spokes — spec "The login preflight" (`:222-263`).
- No firewall change — spec "Firewall" (`:265-267`).
- Acceptance: drop spoke-canary's opt-out and apply it on vps2 — spec "The acceptance" (`:281-282`), § Validation
  (`:517-529`).
- Rejected alternatives are not re-proposed — spec § Rejected alternatives (`:339-362`).
- Deploy order and rollback — spec § Lifecycle (`:364-396`).
- Doc landing sites — spec § Documentation landing sites (`:408-427`).

**Branch: RICH** — the spec pins goal and approach; no brainstorming.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1-I19 | the spec's own intake rows (spec § Intake Inventory `:486-510`) | IN as the spec disposed them | Phases A-C |
| I20 | coordinator (fabrik-d2, 2026-10-23): "W-2ce2df52, P1 security: vps1 DOCKER-USER lets any 10/8 source reach the mesh-only ports" | OUT-OF-SCOPE | W-2ce2df52 (queued behind this item; spec § Firewall `:265-267`) |
| I21 | coordinator: "W-cb08c877, P1: docker.service on vps1 does not wait for wg0" | OUT-OF-SCOPE | W-cb08c877 (spec U3 `:455`) |
| I22 | coordinator: "W-20a37911 … tagged needs-split … split it into one item each" | OUT-OF-SCOPE | W-20a37911 (its own split, after this item) |
| I23 | grounder seat 3: `libs/alerting` and the Backrest hook use `http://apprise:8000` and "would break on spokes" | OUT-OF-SCOPE (refuted) | `libs/alerting/apprise.py:44-80` ssh-execs curl inside the vps1 apprise container; Backrest edits `/opt/backrest/config/config.json` on vps1 (`src/fabrik/drivers/backrest.py:58`) — both hub-side |

Intake: 23 items — 14 IN (the spec's 19 rows minus its 5 OUT), 9 OUT-OF-SCOPE (the spec's 5 plus I20-I23, each named above), 0 ASK.

## Global Constraints

- Shared backing services: `postgres-main:5432`, `redis-main:6379` by name on vps1; a spoke reaches them at
  `10.99.0.1` (`.windsurf/rules/core/30-ops.md:290`).
- Every compose service declares `deploy.resources.limits.memory` and `container_name` (`30-ops.md:149`, `:150`).
- No host `ports:` except a recorded exception; the gate's mesh-only bind is recorded by D-1166 (spec § Shape
  `:405-406`).
- Debian, not Alpine, base images (`30-ops.md:24`): `nginx:1.30-trixie`.
- 12-Factor: logs to stdout only (XI); no migrations from startup (XII); same backing services everywhere (X); no
  sticky sessions (VI); no daemonizing/PID files (VIII); idempotent jobs (IX); immutable releases, never hot-patch a
  container (V); granular env config, no secrets in code (III); shelled-out binaries pinned in the image (II).
- Every deploy act on vps1 or a spoke runs only after the operator's Gate-2 go, relayed by the coordinator
  (`docs/reference/agents/fleet.md:63` § Escalation); fleet then runs it (spec § Personas, fleet).
- Seats and tests: `.venv/bin/python -m pytest` through `/opt/fabrik/scripts/capped_run.sh`; never `uv sync` from
  this worktree.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `core/30-ops.md` | memory limit, container_name, no host ports (exception recorded), Debian base | `.windsurf/rules/core/30-ops.md:149`, `:150`, `:24`, `:357`, `:290` |
| `core/60-watchdog.md` | `escalate_apprise` is always allowed; the sidecar is on for every kind | `.windsurf/rules/core/60-watchdog.md:105`, `:27` |
| `core/45-testing-strategy.md` | one test per behaviour, watched red first | `.windsurf/rules/core/45-testing-strategy.md:22` |
| `core/10-python.md` | no dependency-file edits | `.windsurf/rules/core/10-python.md:38` |
| `ai/50-agentic.md` | the sidecar's Claude lane rides the subscription OAuth files the preflight checks | `.windsurf/rules/ai/50-agentic.md:56` |
| `core/self-healing.md` | no invented self-healing response — the gate adds none | `.windsurf/rules/core/self-healing.md:65` |
| `core/40-documentation.md` | fenced code only in `PORTS.md`, `vps-urls.md` and the receipts | `.windsurf/rules/core/40-documentation.md:244` |
| fabrik-lib `watchdog_sidecar` (vendored, unchanged) | POSTs `{title, body}` to `WATCHDOG_APPRISE_URL`, any 2xx = delivered, no retry on 503 | `/opt/fabrik-lib/watchdog/watchdog_sidecar/agent.py:561-576`, `:244` |
| fabrik-lib reverse proxy | none exists — consume the official nginx image (spec vendor ladder `:284-291`) | no 🆕 candidate |
| `agents-fabrik.md` § Infrastructure Services / Observability | Apprise on vps1, Gatus alerts through it | `/opt/fabrik/agents-fabrik.md:193`, `:221` |
| `specs/services/spoke-canary.yaml` `watchdog:` | the opt-out to remove (no `shape:` flag changes) | `specs/services/spoke-canary.yaml:28-30` |

## Constraints Digest

| Quote | Source |
|---|---|
| Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik. | `.windsurf/rules/core/30-ops.md:357` |
| `deploy.resources.limits.memory` is mandatory. | `.windsurf/rules/core/30-ops.md:149` |
| Use Debian/Ubuntu, NOT Alpine: | `.windsurf/rules/core/30-ops.md:24` |
| `escalate_apprise` \| POST to Apprise → Telegram \| always allowed | `.windsurf/rules/core/60-watchdog.md:105` |
| Watched-fail-first | `.windsurf/rules/core/45-testing-strategy.md:22` |
| Do not modify these files unless the ticket authorises it. | `.windsurf/rules/core/10-python.md:38` |
| Agents run on the subscription's OAuth through the unmodified CLI | `.windsurf/rules/ai/50-agentic.md:56` |
| If a failure class doesn't appear in the table above, the | `.windsurf/rules/core/self-healing.md:65` |
| Fenced code blocks only — never indented code (AI treats it inconsistently) | `.windsurf/rules/core/40-documentation.md:244` |

How each row binds: row 1 — the gate's `10.99.0.1:8202` bind is the D-1166-recorded exception (spec `:405-406`);
row 2 — 32M; row 3 — `nginx:1.30-trixie`; row 4 — the gate makes `escalate_apprise` reachable from spokes; row 5 —
every new test in Phase A is watched red; row 6 — no `pyproject.toml`/`uv.lock` edit; row 7 — the preflight checks
the files that lane needs; row 8 — `unconstrained`: no self-healing step is added; row 9 — the doc edits of Phase B step 6 add table rows and prose only, any command they carry fenced.

## File Scope (owned paths)

- src/fabrik/orchestrator/infrastructure.py
- src/fabrik/drivers/watchdog.py
- tests/test_watchdog_spoke_preflight.py
- tests/orchestrator/test_spoke_dsn_mesh.py
- tests/test_watchdog_driver.py
- infra/vps1/apprise/compose.yaml
- configs/gatus/apps/apprise.yaml
- specs/services/spoke-canary.yaml
- PORTS.md
- docs/infrastructure/vps-urls.md
- docs/development/reviews/2026-10-23-plan-1-spoke-watchdog-apprise-mesh-gate-review.md

## Phase A — Registrar: mesh URL, refusal lifted, login preflight

Appetite: 120

**Interfaces.**
- Produces: `_rewrite_mesh_gated_url(url: str, target_vps: str | None) -> str` and constants `_APPRISE_HOST_AUTHORITY
  = "//apprise:8000/"`, `_APPRISE_MESH_GATE_AUTHORITY = f"//{_HUB_MESH_IP}:8202/"` in
  `src/fabrik/orchestrator/infrastructure.py` beside `_HUB_MESH_IP` (`:121`);
  `InfrastructureProvisioner._watchdog_login_preflight(self, ctx, target: str) -> str | None` (returns `None` when
  the check passes or is skipped, else the one-line failure text).
- Consumes: `fabrik.drivers.ssh.ssh(cmd, timeout=30)` (`src/fabrik/drivers/ssh.py:182`, raises `RuntimeError` /
  `subprocess.TimeoutExpired` / `SshHostError` / `JumpConfigError`, `:104`, `:121`, `:195-200`);
  `fabrik.orchestrator.deployer_ssh._host_env` (`src/fabrik/orchestrator/deployer_ssh.py:123-145`);
  `fabrik.drivers.watchdog.VPS_CLAUDE_HOME` (`src/fabrik/drivers/watchdog.py:143`).
- Wired consumer: `WatchdogDriver` render at `src/fabrik/drivers/watchdog.py:546` (URL) and `_provision_watchdog`
  (`src/fabrik/orchestrator/infrastructure.py:1591`, preflight) — both production paths of `fabrik apply`.

**Behavior Contract** (spec § Testing approach `:316-337`; one test each, highest risk first):
- (1) **Given** a spoke target, **When** the sidecar env is rendered, **Then** it carries
  `http://10.99.0.1:8202/notify/alerts`; vps1 keeps `http://apprise:8000/notify/alerts`; a URL naming another host,
  or a userinfo URL, is untouched.
- (2) **Given** a spoke target whose preflight passes, **When** a real apply runs, **Then** it calls the driver (no
  refusal) and `provision()` provisions the watchdog roles and analytics for vps2
  (`record_failure`/`provision_watchdog_roles` true).
- (3) **Given** the preflight's ssh output, exactly the parse rule probed in § Evidence Phase A (v2, 14 cases),
  **When** the registrar reads it, **Then**: both files present (+ `gate reachable` on a spoke) → driver runs; one
  missing → a red row naming that file; both missing → both named; `gate unreachable` → "gate unreachable from
  <target>"; a missing file AND `gate unreachable` → both named in one row; empty, extra, duplicated or
  contradictory lines, a gate line on vps1, or no gate line on a spoke → "could not check <target>: unexpected
  output"; `RuntimeError`, `TimeoutExpired`, `JumpConfigError` → "could not check <target>: …"; every failure
  records `watchdog:` in `ctx.registrar_failures` naming the target and the ssh alias hit, and never calls the
  driver; a spec-only `target_vps` (no `ctx.target_vps`) is probed on that spoke.
- (4) **Given** an openrouter-only provider (`llm_provider_primary` and `llm_provider_fallback` both not
  `claude-code`), **When** the watchdog registrar runs, **Then** it makes no ssh call.
- (5) **Given** a dry run, **When** the watchdog registrar runs, **Then** it makes no ssh call and logs "would check
  the Claude login files on <target>" only when the provider pair names `claude-code`.
- (6) **Given** a spoke target, **When** `resolve_applicability` renders the `fabrik plan` text, **Then** it no
  longer names D-1153.
- **Mocked:** `fabrik.drivers.ssh.ssh` (the preflight probe's output and exceptions) and `WatchdogDriver.provision`; the
  registrar, the URL rewrite and the parse rule run real.

**Steps.**
1. Preflight probe of the toolchain: `.venv/bin/python -c "import fabrik, pytest; print('ok')"` → `ok`.
2. **Test first (highest risk, behaviour 3).** Rewrite `tests/test_watchdog_spoke_preflight.py`:
   - invert `test_a_spoke_watchdog_is_refused_and_the_driver_never_runs` (`:28-43`),
     `test_a_spoke_named_only_in_the_spec_is_refused_too` (`:60-68`) and
     `test_the_spoke_refusal_never_imports_the_driver` (`:71-78`) into "the driver runs for vps2 after a passing
     preflight" (patch `fabrik.drivers.ssh.ssh` to return `present <home>.json\npresent <home>/.credentials.json\ngate
     reachable`);
   - re-expect `test_provision_withholds_the_watchdog_roles_and_analytics_failure_on_a_spoke` (`:81-99`) to
     `lives=True` for both targets (behaviour 2);
   - re-point `test_plan_names_the_spoke_refusal` (`:102-110`) to assert neither "refused" nor "D-1153" appears
     (behaviour 6); keep `test_plan_does_not_call_a_switched_off_registrar_refused` (`:113-126`) as-is;
   - `test_a_vps1_watchdog_is_unchanged` (`:46-57`) patches the ssh call with a passing vps1 stdout;
   - add the preflight matrix (behaviours 3-5) and the `_rewrite_mesh_gated_url` unit tests (behaviour 1: vps2,
     vps1, `None` target, another host, a userinfo URL, a falsy URL) in this file, importing the new names INSIDE each
     test function as the file already does for `resolve_applicability` (`:103`), so a missing name fails each test
     red rather than erroring the whole file at collection;
   - in `tests/test_watchdog_driver.py`, extend `test_a_spoke_sidecar_reaches_the_shared_data_plane_by_mesh_ip`
     (`:146-158`) with `spoke.apprise_url == "http://10.99.0.1:8202/notify/alerts"` and
     `hub.apprise_url == "http://apprise:8000/notify/alerts"` (behaviour 1 at the render seam; no test asserts
     `apprise_url` today — grounder census).
   - **Untouched, with the reason:** `tests/orchestrator/test_infrastructure.py:369`, `:439`, `:476`, `:609`, `:640`,
     `:695`, `:755`, `:785`, `:827` run real `provision()` with the watchdog applicable and no ssh mock; the conftest
     fleet guard (`tests/conftest.py:579-589`) raises `RuntimeError` on the preflight's ssh, which the preflight
     catches and records via `_nonfatal`, and none of them asserts `registrar_failures` or a watchdog resource — the
     same path the real driver already takes today (`infrastructure.py:1639-1651`). `:416` and `:720` are dry runs.
     `tests/orchestrator/test_plan1_defects.py:99-101` renders with `ctx=None`; the rewrite falls back to vps1 (`:560`).
   Run: `/opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_watchdog_spoke_preflight.py -q`
   → the new/rewritten tests FAIL (red) for the right reason (refusal still present / function missing).
3. Implement in `src/fabrik/orchestrator/infrastructure.py`:
   - add the two constants and `_rewrite_mesh_gated_url` after `_rewrite_shared_infra_host` (`:137-157`): no-op for
     a falsy URL or `(target_vps or "vps1") == "vps1"`, else `url.replace(_APPRISE_HOST_AUTHORITY,
     _APPRISE_MESH_GATE_AUTHORITY)` — no `@` arm (spec `:205-209`);
   - delete the refusal block in `_provision_watchdog` (`:1607-1619`) and its docstring paragraph (`:1601-1605`);
   - add `import shlex` beside the module imports (`:87-94`);
   - after the dry-run branch (`:1620-1627`; extend its log with "would check the Claude login files on <target>"
     when the provider pair names `claude-code`)
     and before the driver import (`:1628`), call `self._watchdog_login_preflight(ctx, target)`; on a returned text,
     `self._nonfatal(ctx, "watchdog", RuntimeError(text))` and return;
   - `_watchdog_login_preflight`: read the provider pair from `ctx.spec["watchdog"]` with the driver's defaults
     (`claude-code`/`openrouter`, `src/fabrik/drivers/watchdog.py:596-597`); skip when neither is `claude-code`; build
     the spec's sudo command (`:229-231`) with `shlex.quote` on both paths, append the gate probe (`:238-240`) when
     `target != "vps1"`; run `ssh(cmd, timeout=30)` inside `_host_env(target)` — the target `_watchdog_target`
     resolved, so a spec-only `target_vps` is probed on its own host (production always sets `ctx.target_vps`,
     `src/fabrik/orchestrator/__init__.py:162`, `:537`, where the two agree); switch the driver call's
     `with _target_vps_env(ctx):` (`:1646`) to the same `_host_env(target)`, so the preflight and the sidecar it
     clears run on one host; parse with the v2 rule of § Evidence Phase A (spec "How the result is read",
     `:245-257`, its "any other output" arm applied to extra, duplicated and contradictory lines); catch `Exception` → "could not check <target>: <one-line text>"; every text
     names `target` and the ssh alias actually hit — `fabrik.drivers.ssh._ssh_host()` read INSIDE the `with`
     (`_host_env` sets `FABRIK_VPS_SSH_HOST` to the raw target and restores it on exit,
     `src/fabrik/orchestrator/deployer_ssh.py:132-145`; on vps1 it is the default alias `vps`,
     `src/fabrik/drivers/ssh.py:34`, `:76-83`). The provider pair is read as the driver does
     (`wcfg = (ctx.spec or {}).get("watchdog", {}) or {}`, `src/fabrik/drivers/watchdog.py:521`, `:596-597`;
     `WatchdogConfig` carries the same defaults, `src/fabrik/spec_loader.py:586`, `:594`);
   - `provision()` (`:764-766`): `watchdog_lives = should_run["watchdog"]`; rewrite the `:764` comment to state the
     accepted residue (roles survive a failed preflight and are re-used, spec `:260-261`);
   - `resolve_applicability` (`:455-462`): drop the refusal clause;
   - `_watchdog_target` docstring (`:131-132`): drop the D-1153 refusal wording.
4. In `src/fabrik/drivers/watchdog.py` after `:571`, add `apprise_url = _rewrite_mesh_gated_url(apprise_url,
   target_vps)` and extend the local import at `:566`.
5. Re-point `tests/orchestrator/test_spoke_dsn_mesh.py::TestWatchdogSpokeRouting` (`:276-296`): patch the preflight
   to pass and assert `seen == ["vps2", None]` — the vps2 driver call runs with the host swapped, vps1 unswapped
   (`_host_env` writes the raw target, `src/fabrik/orchestrator/deployer_ssh.py:136-138`); rewrite its docstring.
6. Run green: `/opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_watchdog_spoke_preflight.py
   tests/orchestrator/test_spoke_dsn_mesh.py tests/test_watchdog_driver.py -q` → all pass; then the slice the census
   names: `/opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/orchestrator
   tests/test_watchdog_db_roles.py tests/test_app_role_provision.py -q` → all pass
   (`tests/orchestrator/test_registrar_failures_not_green.py` runs inside `tests/orchestrator`).
7. Red-on-revert for behaviours 1 and 3, BEFORE the step-8 commit, in a throwaway worktree that carries the
   uncommitted phase: `git diff HEAD -- <the Phase A paths> > <scratch>/phase-a.diff`; `git worktree add --detach
   <scratch>/probe HEAD`; `git -C <scratch>/probe apply <scratch>/phase-a.diff`; in the probe only, delete the
   `_rewrite_mesh_gated_url` call in `watchdog.py` and the `_watchdog_login_preflight` call in `_provision_watchdog`;
   run `tests/test_watchdog_driver.py` and `tests/test_watchdog_spoke_preflight.py` from inside the probe under
   `capped_run.sh` (the root conftest pins the checkout it runs in) and watch behaviours 1 and 3 fail; `git worktree
   remove --force <scratch>/probe`.
8. Closing sequence: (1) the phase gate above green; (2) stage the phase's own paths (`git add <them>`), then
   `python scripts/enforcement/check_doc_sync.py` (it reads the STAGED diff, `check_doc_sync.py:393-405`) + the
   docstring/comment rewrites of step 3 (the spec's code-resident landing sites `:418-419`); (3) **`/fabrik-review-scoped`
   on Phase A's changed surface** — a BLOCKING gate run to a closing pass that confirms zero defects (`Profile: small`:
   the heavy round is at Finish); (4) commit Phase A by explicit pathspec with Agent Provenance Trailers, push.

## Phase B — vps1 gate mirror, Gatus endpoint, canary opt-out, docs

Appetite: 60

**Interfaces.**
- Produces: the `apprise-mesh-gate` service + top-level `configs: apprise-mesh-gate-conf` in
  `infra/vps1/apprise/compose.yaml`; `APPRISE_ATTACH_SIZE: "0"` on `apprise`; a Gatus endpoint
  `apprise-mesh-gate`.
- Consumes: Phase A's spoke URL `http://10.99.0.1:8202/notify/alerts` (the gate's only admitted path).

**Behavior Contract.**
- (1) **Given** the edited `infra/vps1/apprise/compose.yaml` (with the external network and volume declared),
  **When** `docker compose -f infra/vps1/apprise/compose.yaml config` renders it, **Then** it shows the gate service
  with `container_name: apprise-mesh-gate`, `ports` `10.99.0.1:8202:8202`, memory 32M, the config mounted at
  `/etc/nginx/conf.d/default.conf`, and no `depends_on`.
- (2) **Given** the gate run locally against the mirror's own config, **When** every row of the spec's probe
  (`:469-483`) is sent, **Then**: `POST /notify/alerts` → 200, upstream sees `POST /notify/alerts`;
  `POST /notify/alerts?tag=all` → 200, upstream sees no query; `GET`, `HEAD`, `PUT /notify/alerts` → 403;
  `POST /notify/alerts/`, `/notify/`, `/notify`, `/NOTIFY/alerts` → 403; `POST /notify/%61lerts`,
  `/notify//alerts`, `/notify/alerts/../alerts` → 200, upstream sees `POST /notify/alerts`; `GET /get/alerts`,
  `/json/urls/alerts`, `/details`, `/metrics`, `/` → 403; `POST /add/alerts` → 403; `GET /healthz` → 200; a 900 KB
  POST → 200, a 1.1 MB POST → 413; 24 rapid POSTs → 21 × 200 then 503.
- (3) **Given** `specs/services/spoke-canary.yaml` after step 5, **When** it loads through `load_spec`, **Then** it
  has no `watchdog:` override (WatchdogConfig defaults).
- **Mocked:** nothing — the upstream is a local echo stub standing in for apprise; compose, nginx and `load_spec`
  run real.

Behaviours 1 and 2 are probes of a config file, run before the edit (no gate service in the render; nothing on
`127.0.0.1:18202`) and after it; behaviour 3's check is run before step 5's edit and prints `enabled=False` — its red.

**Steps.**
1. Probe: `docker version --format '{{.Client.Version}}'` and `docker compose version` → present in WSL.
2. Edit `infra/vps1/apprise/compose.yaml`: rewrite the header (`:3-4`) to name the gate; add
   `APPRISE_ATTACH_SIZE: "0"` after `:12`; add the `apprise-mesh-gate` service exactly as spec `:147-157` plus
   `container_name: apprise-mesh-gate` (30-ops.md container_name mandate) and `configs: [{source:
   apprise-mesh-gate-conf, target: /etc/nginx/conf.d/default.conf}]`; add top-level `configs:
   apprise-mesh-gate-conf: content: |` holding spec `:164-177` with every `$` written `$$` (spec `:180`).
3. Run the local policy probe from a scratch dir (never on vps1): a docker network, a Python echo stand-in aliased
   `apprise`, the mirror's gate service brought up with `docker compose -p gateprobe up -d apprise-mesh-gate` from a
   scratch copy whose `ports:` is rewritten to `127.0.0.1:18202:8202` and whose network is the probe network; curl
   each row of behaviour 2; tear down with `docker compose -p gateprobe down` (no volumes exist in the probe).
4. Edit `configs/gatus/apps/apprise.yaml`: add endpoint `apprise-mesh-gate`, group `apps`, url
   `http://10.99.0.1:8202/healthz`, `interval: 120s`, `[STATUS] == 200`, `alerts: [type: custom]` (spec `:305-308`;
   the by-name fallback `http://apprise-mesh-gate:8202/healthz` is written only by Phase C step 6, on probe 4).
5. Edit `specs/services/spoke-canary.yaml`: delete `:28-30` (the D-1153 comment and `watchdog: enabled: false`).
   Check: `.venv/bin/python -c "from fabrik.spec_loader import load_spec; s=load_spec('specs/services/spoke-canary.yaml'); print(s.watchdog)"`
   → the WatchdogConfig defaults (enabled).
6. Docs (spec § Documentation landing sites `:408-427`): `PORTS.md` — a row `| 8202 | **apprise-mesh-gate** … |`
   after `:57`, mesh-only, and `:34`'s "no host port" rewritten; `docs/infrastructure/vps-urls.md` — `:149` clause
   replaced by the spoke URL, a § Mesh URLs row after `:168`, a mesh-only row after `:295`.
7. Closing sequence: (1) behaviours 1-3 green; (2) stage the phase's own paths, then
   `python scripts/enforcement/check_doc_sync.py` (staged mode); (3)
   **`/fabrik-review-scoped` on Phase B's changed surface** — BLOCKING, to a closing pass confirming zero defects;
   (4) commit by explicit pathspec with trailers, push.

## Phase C — Finish: whole-plan review, deploy gate, acceptance

Appetite: 90

**Behavior Contract.** The spec's § Validation (`:517-529`), verbatim as acceptance.

**Steps.** The order is the spec's adoption order (`:366-381`): the gate is live and probed BEFORE the code that
points spoke sidecars at it is merged.

1. **The Finish `/fabrik-review`** over the whole-plan diff (base `0a398d12e` .. HEAD) — the D7 floor: ≥1 Opus
   authoritative seat plus one Sonnet and one Haiku seat per independent failure-class group
   (`python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --units <groups>` prints the seats), stamped first with
   `python3 scripts/command_run.py dispatch --seats <n>`; ONE receipt at
   `docs/development/reviews/2026-10-23-plan-1-spoke-watchdog-apprise-mesh-gate-review.md`; run to a closing pass
   that confirms zero defects.
2. `/fabrik-docs-review` over the plan's doc surface to a fixed point.
3. Governance ledgers through the private-index recipe: `CHANGELOG.md` (one `### Added` entry); no new D-row (D-1166
   records the approval and the 30-ops exception).
4. `python scripts/enforcement/check_doc_sync.py --range 0a398d12e..HEAD` (the whole-plan coverage receipt,
   `check_doc_sync.py:396-401`), `python scripts/final_gate.py --check --json` → `"status":"success"`, and
   `python scripts/enforcement/check_convergence.py` → green. A green gate is necessary, not sufficient — the Evidence
   below is the proof. Push.
5. **Deploy gate (operator, `gate: deploy`)** — a `DECISION NEEDED (ground: gate)` block sent to the coordinator by
   `SendMessage` (the operator talks only to the coordinator, `docs/reference/agents/fleet.md:63`), naming steps 6
   and 7 below as the acts; the run closes `handoff` with `## RESUME` naming step 6. Nothing below runs before the go.
6. After the go, spec § Lifecycle adoption steps 1-3 (`:366-380`), on vps1 through
   `ssh -o ProxyJump=vps2 vps` (the hub's route, D-973), in this order, each output recorded:
   - **The attachment lock first.** `sudo cp /opt/apprise/compose.yaml /opt/apprise/compose.yaml.bak-<UTC stamp>`;
     copy in the mirror from the pushed branch commit (`scp` of `infra/vps1/apprise/compose.yaml` to a temp path,
     then `sudo install -m 0644` over `/opt/apprise/compose.yaml`); `cd /opt/apprise && sudo docker compose up -d
     --no-deps apprise`.
   - Probe U4: `sudo docker exec apprise curl -s -o /dev/null -w '%{http_code}' -X POST -F body=attach-probe
     -F attach=http://apprise:8000/ http://localhost:8000/notify/alerts` — the attach URL is one Apprise CAN fetch,
     so a refusal means parsing is off, never a failed fetch. Expected: a non-2xx code. A 2xx is the U4 stop: run
     step 10's rollback, never bring the gate up.
   - `sudo bash -s -- --check < scripts/sysadmin/ensure-apprise-alerts-config.sh` (the repo copy streamed over the
     ssh) → exit 0, the alerts path answering 200.
   - `cd /opt/apprise && sudo docker compose up -d --no-deps apprise-mesh-gate`.
   - Probe 1, from a vps2 container (`ssh vps2`): `sudo docker run --rm curlimages/curl:8.10.1 -s -o /dev/null -w
     '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{"title":"[fabrik] gate probe","body":"vps2"}'
     http://10.99.0.1:8202/notify/alerts` → `200`.
   - Probe 2, the same container: `-s -o /dev/null -w '%{http_code}' http://10.99.0.1:8202/get/alerts` → `403`.
   - Probe 3, from WSL (a public source): `curl -s -m 5 -o /dev/null -w '%{http_code}'
     http://notify.vps1.ocoron.com:8202/healthz` → `000` (connect dropped by vps1's DOCKER-USER chain).
   - Probe 4, from a vps1 container: `sudo docker run --rm --network fabrik curlimages/curl:8.10.1 -s -o /dev/null
     -w '%{http_code}' http://10.99.0.1:8202/healthz` → `200` keeps B4's mesh URL; anything else rewrites
     `configs/gatus/apps/apprise.yaml`'s gate endpoint to `http://apprise-mesh-gate:8202/healthz` on a follow-up
     commit (explicit pathspec, trailers, pushed) before step 7.
   - Any other unexpected result: step 10.
7. `python3 scripts/merge_request.py request --review <the Finish receipt> --item W-5dcafaef`; send the printed
   `SendMessage` lines, the request text quoting steps 6's probe codes so the coordinator merges a live gate. Then
   send kaizen the 30-ops landing (spec `:421-423`): write `<scratch>/kaizen-30ops.md` — asking that
   `.windsurf/rules/core/30-ops.md:290`'s mesh-published list gain `:8202` (the Apprise gate, `POST /notify/alerts`
   only), citing D-1166 and the pushed branch-tip sha the merge request names (the merge sha does not exist yet),
   its first line `Subject: 30-ops:290 gains the :8202 Apprise mesh gate
   (D-1166)` — and run `python scripts/mail.py send --to fabrik --to-agent kaizen --kind request --body-file
   <scratch>/kaizen-30ops.md` (`scripts/mail.py:2966-2995`: the body comes from the file; there is no subject flag).
8. After the coordinator merges: `fabrik apply specs/services/spoke-canary.yaml` (hub CLI, main checkout; the
   operator's step-5 go covers it) → green, the watchdog preflight passing on vps2 (the apply log shows no
   `watchdog:` registrar failure).
9. Acceptance (spec § Validation `:517-529`): `ssh vps2 "sudo docker exec spoke-canary-watchdog python -c
   \"import httpx,os; print(httpx.post(os.environ['WATCHDOG_APPRISE_URL'], json={'title':'[fabrik] spoke watchdog
   acceptance','body':'vps2'}, timeout=10).status_code)\""` → `200`, and the operator confirms the Telegram message
   (relayed by the coordinator). Record every step-6, 8 and 9 output in the Finish receipt's `## Deploy evidence`,
   commit it (explicit pathspec, trailers, pushed) with a message naming W-5dcafaef, send a follow-up merge request
   for it, then `python3 scripts/work.py done W-5dcafaef --evidence <that commit's sha>`.
10. **Rollback, on any failure in steps 6, 8 or 9** — spec § Lifecycle rollback (`:382-387`), in reverse order: re-add
    spoke-canary's `watchdog: {enabled: false}` and ask the coordinator to revert the code merge (if merged);
    `ssh vps2 "sudo docker rm -f spoke-canary-watchdog"` (an `enabled: false` re-apply leaves it running); `cd
    /opt/apprise && sudo docker compose rm -sf apprise-mesh-gate`; restore `/opt/apprise/compose.yaml` from the step-6
    backup and `sudo docker compose up -d --no-deps apprise`, then the `--check` → 200. Record the outputs and file
    the finding as a new item (`python3 scripts/work.py add`), linked from W-5dcafaef.

## Coverage Checklist

| Class | Status |
|---|---|
| ai/50-agentic (the Claude lane's login files the preflight checks) | CLEAN — the preflight checks the two OAuth files the sidecar mounts (`src/fabrik/drivers/watchdog.py:143`); no API key enters the path; hunted: Phase A step 3, `ai/50-agentic.md:56` |
| core/10-python | CLEAN — no dependency-file edit; `shlex` is stdlib, added at `infrastructure.py:87-94` (pass 1, S11); hunted: Phase A steps 3-4 |
| core/40-documentation (PORTS.md, vps-urls.md, the receipt) | CLEAN — the doc edits are table rows and prose; every command in the plan is fenced or inline; hunted: Phase B step 6, Phase C step 9 |
| core/45-testing-strategy (watched red, one test per behaviour) | FIXED — red-on-revert now runs on a probe carrying the uncommitted phase (S1), new names import per test (S11), Phase B behaviour 3 is watched red (S10) |
| core/60-watchdog (escalation reachability) | CLEAN — `escalate_apprise` reaches Apprise from spokes through the gate; the canary's opt-out is removed (Phase B step 5); hunted: `60-watchdog.md:27`, `:105` |
| core/self-healing | CLEAN — no ladder step is added; hunted: every phase |
| FLOOR core/35-security-auth (gate allow-list, no credential on the path) | CLEAN — the gate holds no secret and admits only `POST /notify/alerts`; the attachment lock is probed at deploy with a fetchable URL (C step 6); hunted: Phase B behaviour 2, spec `:142-201` |
| FLOOR core/25-data-postgres (watchdog roles provisioned on spokes) | CLEAN — spoke roles ride the existing mesh DSN rewrite (`watchdog.py:568-571`); `watchdog_lives` drops its vps1 test (Phase A step 3); hunted: `infrastructure.py:764-784` |
| FLOOR core/30-ops (ports exception, memory, container_name) | FIXED — the container_name mandate is now cited at `30-ops.md:150` (O4); the mesh-only port is D-1166's recorded exception |
| 12-FACTOR | CLEAN — no logfile, no startup migration, no sticky session; the gate is an immutable image with a compose-inline config; hunted: Phase B step 2 |
| fail-open vs fail-closed on every gate/guard | FIXED — the preflight parse read contradictory or duplicated lines and a vps1 gate line as a pass or a definite verdict (O3), and a missing file hid the gate result (O2); v2 probed over 14 cases |
| cost/quota/limit accounting edges (unknown≠0, per-call vs batch) | CLEAN — the per-spoke rate (30/min, burst 20) and the 1m body cap are spec-probed rows of Phase B behaviour 2; the sidecar budget is unchanged |
| boundary/sentinel/prefix collisions | CLEAN — the rewrite matcher is probed against `:80000`, a no-slash URL, a userinfo URL and another host (§ Evidence Phase A) |
| behavior-without-a-test | FIXED — Phase B behaviours 1-2 are named as before/after probes and behaviour 3 gains its red (S10); every Phase A behaviour maps to a test step |

```
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: a default turns one bad/empty JWT into a cross-tenant read, and a raise turns a deny into a 500. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- `POST /auth/passwordless/request` is ALREADY capped per email and per IP in Redis by the library (`AUTH_PASSWORDLESS_REQUEST_CAP`, `AUTH_PASSWORDLESS_IP_REQUEST_CAP`): tune those, add no second limiter, and never answer it with 429 — it returns 202 either way, so throttling never reveals an account. `POST /auth/passwordless/verify` has a per-code attempt cap (`AUTH_PASSWORDLESS_ATTEMPT_CAP`) but no per-IP bound; the project adds that bucket.
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- A dedicated admin host on its own domain — never the customer-facing app's domain — behind 2FA: set `shape.is_admin_dashboard: true` there. The Authelia registrar adds a per-domain `two_factor` rule on `fabrik apply`, so every path on that domain sits behind 2FA except the standing `/health` and `/metrics` bypasses (D-366, `saas/60-saas-ui.md` § Admin). API services with bearer auth: set `shape.has_bearer_api: true` — the registrar inserts an Authelia **bypass** rule *before* the `two_factor` catch-all so machine/bearer callers aren't hit with interactive 2FA. Don't add Traefik `authelia-forward` middlewares manually — the scaffolder + registrars emit them.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: the plain upstream PostgreSQL Alpine image, `plpgsql` only — `CLAIMS.yaml` row `fleet-postgres-main-no-pgvector`); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
**"Own database" means a DATABASE on `postgres-main`, never a database SERVER.** Per-project isolation is a separate database (its own name, its own role) on the shared container — isolation, quota and backup are all satisfied at that grain. A dedicated Postgres instance is a decision, not a default: it needs its own `docs/DECISIONS.md` row naming what the shared server cannot serve (web-ecommerce-factory 01M1Q8X9, 2026-09-05: "one DB per store" read naively as one server per customer).
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an APPLICATION's settings surface**:
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.** The rubric FLOOR-injects this mandate *and* `35-security-auth`'s "config via env vars only (`os.getenv("KEY", "default")`)" into every finder prompt on every review, so a finder reading both literally has two rules it cannot both satisfy, and files a false positive on whichever it applies. The carve-out: `BaseSettings` governs a SERVICE's config surface (a `Settings` object, DB/Redis DSNs, secrets). A **vendored fabrik-lib module** has no settings object by design — it reads its own knobs with bare `os.getenv("KEY", "default")`, which is `35-security-auth`'s mandate being satisfied, not this … (wrapped further — read the pack)
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }` opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default to flip.
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a bare `curl` of a path you assumed.
- remove it` on the hub) names a plan that protects nothing. Never add a service-named plan.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout.  An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency.
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (probed 2026-09-01: the plain upstream PostgreSQL Alpine image at the fleet major recorded in `CLAIMS.yaml` row `pg-fleet-major` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- `docker compose run --rm <svc> alembic upgrade head` (against deployed environment) — `<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed
- > **`fabrik run` and `.fabrik/hooks/post-deploy/` do NOT exist** — the real CLI answers `Error: No such command 'run'`, the hook path appears nowhere in the platform, and `_post_deploy_sync()` (`cli.py:64`) only refreshes `data/projects.yaml`; an agent following either ships a deploy where migrations never run. Do not re-add either without a `path:line` in `src/fabrik/` that executes it.
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### ai/50-agentic.md  (hit: src/fabrik/orchestrator/infrastructure.py, tests/orchestrator/test_spoke_dsn_mesh.py)
- is never the only thing between the agent and an irreversible act.
- **Auth boundary.** Agents run on the subscription's OAuth through the unmodified CLI, never `ANTHROPIC_API_KEY` (ai/00). Never pass `bare=True` on that lane: bare mode never reads OAuth credentials and fails with "Not logged in". A deployed service declares `shape.uses_claude_cli` and mounts the rotated `~/.claude`, never a static token. Anthropic's terms say subscription OAuth is for ordinary, individual use of Claude Code and its own apps; developers building products or services, including with the Agent SDK, should use an API key, and Anthropic does not permit routing requests through Free, Pro or Max credentials on behalf of their users, reserving the right to enforce that without notice. The operator's own development and automation through the unmodified CLI is the closest fit to that … (wrapped further — read the pack)
- output, and some models never return them. Pick the rate per model from the bake-off browser (hub-only), using its tools chip.

### core/10-python.md  (hit: src/fabrik/drivers/watchdog.py, src/fabrik/orchestrator/infrastructure.py, tests/orchestrator/test_spoke_dsn_mesh.py)
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Type the package, never `.`: the root walks the hub-synced `scripts/`, where mypy finds the same file under two module names and stops on every fresh project. file-worker types `mypy --explicit-package-bases worker`; a `server/` backend (saas-skeleton, static-site, office-extension, chrome-extension, mobile-app) runs `mypy src` from `server/` (D-605).
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (`<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed) (see `30-ops.md` § Release & Admin Processes).
| `alembic upgrade head` in `lifespan` / startup hook | One-off admin process against the deployed release: `docker compose run --rm <svc> alembic upgrade head`, `<svc>` a service that declares `.env.owner` (a `migrate` service), never the app service (D-754) (concurrent replicas race the version table) |

### core/40-documentation.md  (hit: PORTS.md, docs/development/reviews/2026-10-23-plan-1-spoke-watchdog-apprise-mesh-gate-review.md, docs/infrastructure/vps-urls.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
| `Agent-Role` | `primary` · `orchestrator` · `subagent` · `review-fix` · `ci-fix` | every AI commit (`ci-fix` ONLY when one of the hub's two unattended writers made the commit — the CI-fix dispatcher's `claude -p` run in THIS repo after a GitHub Actions failure, or the hub's own rules-version cron; any other session never writes it) |
| `Agent-Name` | the name the operator gave your window — your `CLAUDE.md` § Agent Provenance Trailers owns the rule (in a project: write it by hand; never invent one) | every AI commit |
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/orchestrator/test_spoke_dsn_mesh.py, tests/test_watchdog_driver.py, tests/test_watchdog_spoke_preflight.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A subagent seat runs no package-manager verb and runs `.venv/bin/python -m pytest` instead (`10-python.md` § Package Manager). A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests pass the throwaway guard before connecting — `require_throwaway(TEST_DATABASE_URL)` where the scaffold emitted `tests/conftest.py`; where it did not (an unscaffolded repo has no such helper), this anchored predicate, verbatim: `dbname = urlparse(url).path.lstrip('/'); assert dbname.lower().endswith(('_test', 'throwaway', 'scratch')), dbname` — never point them at a dev/shared DB.

### core/60-watchdog.md  (hit: specs/services/spoke-canary.yaml, src/fabrik/drivers/watchdog.py)
- AGENT USAGE: Vendor watchdog/emitter/ into projects that need watchdog catch. Never call the sidecar from main app — emit incidents to the inbox instead. Don't put secrets in details. -->
| any `kind` — `service`, `worker`, `wordpress`, `static` | **on** | tune the caps (`daily_budget_usd`, `daily_invocations_cap`), never the switch |
- ⚠️ **This table previously claimed a shape-driven default** (`python-api`/`node-api` conditional on `is_admin_dashboard` OR `has_persistent_data`; `static-site`/`docusaurus` off). That was **never what the resolver did** — `resolve_applicability` is a one-line unconditional `watchdog_cfg.get("enabled", True)` with **no `kind` test at all** (`orchestrator/infrastructure.py`:359-373, whose own comment says the matrix here "stays operator discipline, not encoded behaviour"). So the table described a discipline, not a behavior, and the discipline is now superseded. Anything relying on the old rows — including a spec comment justifying an opt-out — is stale.
**Make it project-specific** — set `watchdog.project_system_prompt_file: docs/WATCHDOG_PROMPT.md` (project-relative Markdown, ≤32 KB). The driver injects its contents as `WATCHDOG_SYSTEM_PROMPT`; the sidecar appends it as a `## This project` section *after* the canonical veteran-sysadmin prompt (rails never replaced). Use it to teach the watchdog THIS app's architecture, failure modes, what "healthy" means, and hands-off zones. **Fail-soft:** a missing / unreadable / oversized / absolute / `..`-escaping path is ignored (logged warning) and the sidecar runs the canonical prompt only — a prompt-file problem never disables the watchdog or blocks the deploy, and a bad path is never read. Commit the prompt file to the repo before `fabrik apply` (the driver reads it hub-side at render).
- `/opt/<project_id>/` (RO) — the project tree for `Read`/`Grep`/`Glob`. This is the `/project` mount the fix lane reads conventions from (`.windsurf/rules/*` + `CLAUDE.md` are gitignored, so a bare clone would lose them); code changes materialize into a writable scratch worktree, never the RO mount.
- Per-project by design: each sidecar's DSN reaches ONLY its own DB (a compromised RO cred can't read another tenant). Password lifecycle mirrors `DATABASE_URL`: a fresh password is minted + injected only when a role is newly created; an existing role is preserved (no rotation), so its `.env` DSN stays valid and a cached-image re-apply never breaks a running sidecar. The batch runs under `\set ON_ERROR_STOP on` (failures raise, never false-succeed); grants are re-applied every apply (idempotent — covers newly-added tables); `ALTER DEFAULT PRIVILEGES` targets the real DB owner (looked up from `pg_database.datdba`, omitted when unresolvable), so it works on postgres-owned legacy DBs. Roles are non-owner / non-superuser (least privilege) — on `FORCE ROW LEVEL SECURITY` tables the RO lane sees only policy-permitted rows; a multi-tenant app needing cross-tenant diagnosis adds a policy for `{db}_wd_ro` upstream. Teardown: `drop_database` also drops the two roles (`DROP ROLE IF EXISTS`, on both the DB-present and already-gone paths) so a drop+recreate never orphans them; a provisioning failure surfaces as a `watchdog-db-roles` entry in the deploy resource summary (not just a log warning). (Distinct from the shared, manual `scripts/provision_watchdog_ro.py` escape hatch, which this supersedes for the auto path.)
- 4. Per incident: cost-cap check (ops-only path — see the ⚠️ below) → LLM diagnose (Claude Code primary, OpenRouter fallback) → action dispatch → **if code-class and Tier-D enabled: generate+test fix → Telegram-gate → apply via deploy adapter → verify/rollback → record**; else record → escalate if Tier C. ⚠️ With `auto_code_fix` on, the coordinator diagnoses with no cap check and records neither the diagnosis nor its fix runs — the daily caps do not bound Tier D (`core/cost-budget.md` § The Watchdog's Caps; filed to fabrik-lib).
- ⚠️ **`drop_queue_items` and `rotate_locks` are NO LONGER Tier A** — the module moved them to the Tier-C **approved-write lane** (`actions.py::TIER_C_WRITE_HANDLERS`), fail-closed behind TWO gates: `WATCHDOG_ALLOW_DB_WRITES` (default OFF) and a provisioned `WATCHDOG_DB_URL_RW`. Absent either, the handler returns `skipped`, not a mutation. § Architecture already said this ("Consumed only by the Tier-C approved-write lane"); this table had not caught up, so the pack promised two automatic DB-mutating actions that are impossible by default. Since fabrik-lib SB-103 the model is offered one only when all four hold, all set in the project `.env`: it is listed in `WATCHDOG_LLM_ACTIONS` (with the spec's `watchdog.llm_actions` unset — a non-empty field overrides that line, and refuses the pair because no spec field carries the allowlist), `WATCHDOG_DB_WRITE_ALLOWLIST` has an entry for that action naming the tables and columns it may touch (a malformed value disables both), and both gates above are open.
**Tier D** — code-remediation, **off by default**, opt-in like B/C and **human-gated**. This is the only tier that can change running code, and it never does so silently.
| `create_fix_pr` | the dispatch key the coordinator's code-class fork reads (`coordinator.py::_is_code_fix`), routing the incident to REMEDIATE — there is no separate Tier-D action key, and the fork runs only for a trigger-bus signal (`trigger_sources` + `critical_paths`, [self-healing § Tier D](self-healing.md)); the always-on poll path never offers it (`agent.py` builds its menu with `code_fix_enabled=False`, so `check_proposal` refuses a reply naming it — fabrik-lib D-412); on the trigger-bus lane the chain is: generate a fix on `watchdog/<incident_id>` → tests pass (**HARD gate**) → secret-scan the diff → blast-radius guard → Telegram the diff with **Approve / Reject / STOP** → on approval **OR** silence past `code_fix_window_sec` → `deploy_adapter.apply(branch)` → VERIFY health → **auto-rollback on regression** | Isolated clone only (never the RO `/project` mount); deploy mechanism **injected** (no in-place src edit); every apply/rollback written to the `deploys` audit table; push restrictions apply to the **LLM's own bash** (hook + settings deny-list: no main/master, no force-push, no `git config`/`rebase`/`reset --hard`/`tag`); the **deploy adapter is the sole sanctioned main-push path** — it merges the fix branch into `deploy_branch` (default `main`) and uses `--force-with-lease` ONLY on rollback |
- ⚠️ **We chose the MINORITY convention on silence, deliberately — know what it rests on.** The prevailing pattern in published autonomous-remediation designs is **"silence is denial"**: an approval request that times out resolves to REJECTION, and an unanswered approval never converts into consent. Ours is the inverse — `TIMEOUT` routes through the same branch as `APPROVE` and the fix deploys. That is defensible here for a specific reason: this fleet is unattended, so silence-as-denial would mean a green-tested fix for a live incident simply never lands, and the incident continues. But the inversion is only safe while THREE things hold, and all three are load … (wrapped further — read the pack)
- **No response within `code_fix_window_sec`** (default **300 s**, spec range 60–3600; D-378) → treated as approval and applied. A fix that silence can auto-apply has already passed the tests, the secret scan and the blast-radius guard; it deploys only after a pre-apply snapshot marker is recorded, and rolls back to the previous code ref when post-apply health (or the opt-in golden check) regresses — so the default is short. Rollback catches a health regression and, where a golden file covers it, a known-answer regression; a wrong fix that passes both is never caught, so a project that wants a longer human review sets the field explicitly. It IS the operator-bound terminal (see [self-healing](self-healing.md) acceptance checklist), not a fully-autonomous layer.
- **Per-incident cost.** ⚠️ NOT enforced by a `--max-budget-usd` flag — that is explicitly banned (`llm_client.py`: *"no $ caps on sysadmin"*, per the operator directive that per-call caps break the diagnose loop), and `per_incident_cap_usd` is accepted for API compatibility but not enforced at the call site. Spend is OBSERVED (`total_cost_usd` from the Claude envelope) and bounded by the daily caps, not clipped mid-incident. OpenRouter fallback timeout is 60s.
- **Bypassing the PreToolUse hook.** Hook + claude-settings allow-list + sandbox.filesystem + docker.sock scoping are 4-layer defense-in-depth. If you "just need" to let Claude run an arbitrary `bash` command, the right move is to add the command to claude-settings.json — never `chmod -x` the hook.
- **Editing `/opt/<id>/src` in-place from the sidecar.** In-place src editing from the sidecar is still **banned** — code changes go through the isolated workspace + injected deploy adapter. **Without Tier-D opt-in, watchdog never merges** (operator merges, via the PR workspace at `/var/lib/watchdog/proposed/<project_id>/` pushed to `watchdog/<incident_id>`). **With Tier-D**, watchdog MAY apply a tested, secret-scanned, blast-radius-clean fix via the deploy adapter after explicit Telegram approval or a configured silence window, with auto-rollback armed and a STOP kill-switch.
- fleet-AI blind spot — the deploy agent cannot reason about a container it has never been told about.
- ⚠️ Measured 2026-09-01: `tryton-crm` runs `tryton-crm-watchdog` (up, healthy) and **neither** its `OPERATIONS.md` nor its `DEPLOYMENT.md` mentions a watchdog at all. So this is the live default, not a hypothetical.

### core/self-healing.md  (hit: specs/services/spoke-canary.yaml, src/fabrik/drivers/watchdog.py)
- AGENT USAGE: Pick the failure class, walk the ladder top-to-bottom, stop at the first step that resolves. Never invent a step. Never skip a step. -->
- [`60-watchdog`](60-watchdog.md) — the escalation engine and the owner of its tiers. Tier A acts automatically (it registers `restart_container`, `clear_file_cache`, `pause_worker`); Tier B is opt-in; Tier C escalates — and carries the **approved-write lane** (`drop_queue_items`, `rotate_locks`), off by default; **Tier D** (opt-in, Telegram-gated) applies a tested code fix with auto-rollback. ⚠️ Registered is not runnable — see **What the sidecar can execute today** below.
- Each row reads left-to-right: **Symptom** (an observable signal) → **First response** (a `58-resilience` primitive or the module that implements it) → **Fallback** (another primitive or a `60-watchdog` action) → **Escalate** (operator-bound). The agent picks the row matching the active failure, walks left-to-right, and **stops at the first step that resolves**. Never skip rightward.
| 11 | **Postgres allocation registry drift** (HUB-side, not a service: a database in `pg_database` with no `allocations.json` entry) | the hourly drift cron (`scripts/audit_all_registrars.py`) finds a database no registry row claims | Additive reconcile (`src/fabrik/registry_reconcile.py`, D-500): registers it in-lock, never overwrites or deletes; `report` (writes nothing) unless the cron line sets `FABRIK_REGISTRY_RECONCILE=apply` | Refuse, never guess, and write nothing: a name two specs claim is counted as `fabrik_registry_heal_total{outcome="shared"}`; any other refusal (an incomplete claim map, an unresolved owner, an error) as `fabrik_registry_heal_failed{spec_id,db,reason}` | `FabrikRegistryHealFailed` (a `heal_failed` refusal standing 2 h; a shared claim alerts on neither) or `FabrikAuditStale` (no clean audit run in 3 h, or none recorded) — `configs/prometheus/rules/fabrik-drift.yml` |
**⚠️ Row 10 is NOT the deadman timer, and the difference is the whole point.** The Tier-C deadman below (`spec.watchdog.deadman_timeout_seconds`, 60–3600, default 300 s, rendered as `WATCHDOG_DEADMAN_TIMEOUT`) measures **operator silence** — it arms only
- If a failure class doesn't appear in the table above, the rule is: **add the row to this pack first, then the response logic to the code.** Never silently invent a self-healing response — it'll diverge from the operator's mental model and break the ladder's discipline.
- 4. **Self-healing without a visible signal.** A pause flag, breaker, or rate-limit reject that doesn't increment a counter and emit a structured log line is invisible — when it misfires, you can't tell. Every ladder step MUST emit a counter AND a `structlog.info()` (or `pino.info()`) row carrying the resource name + reason; without that, the next operator audit has no way to tell the difference between "step fired and recovered" and "step never ran". **Tier-D steps (stabilize / remediate / apply / rollback) are held to the same bar:** each MUST emit a counter + structured log AND write the `incidents` / `approvals` / `deploys` tables — an unaudited or irreversible code-remediation is not self-healing, it's an unreviewed deploy.
- 2. **Fallback — `pause-state` (Redis-backed).** When `signups_per_ip_per_minute` for a specific IP stays high after the first defense's per-IP cap fires, the worker emits an incident; the watchdog sidecar reads the inbox and proposes Tier A `pause_worker` with `resource=signup_<ip_hash>` (the action accepts `^[a-z][a-z0-9_]{0,31}$` and a TTL of 5–3600 s, so truncate the hash to fit — and it runs only once the spec lists `watchdog.llm_actions: [pause_worker]`, above; until then that step escalates and the app sets this pause itself with `pause_state.set_global_pause(...)`). Every signup-handling worker checks `pause_state.is_paused("signup_<ip_hash>")` from the vendored fabrik-lib `pause-state` (the scaffold's own `pause_state.py` has no `is_paused`), with `PAUSE_KEY_PREFIX` equal to `<project_id>:pause:`, and bails without touching the DB. Never gate other workers on `is_globally_paused()` while per-IP keys share the prefix — it reports ANY key under it, so one IP would stop them all.

# promote-to-check_*: 109 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
- `fabrik-lib/fastapi-user-auth` `DELETE … RETURNING` `jti` `agents-fabrik.md § Supabase`
- `chrome-extension` `chrome.identity.launchWebAuthFlow` `https://<ext-id>.chromiumapp.org/` `chrome.storage.session`
- `desktop-app` `safeStorage` `desktop-app/72-desktop.md`
- `fabrik` `X-Internal-Token` `internal_auth.py` `hmac.compare_digest` `APIKeyHeader`
- `auth.uid()` `current_tenant_id()` `NULL` `EXCEPTION WHEN OTHERS THEN RETURN NULL` `SELECT auth.uid()` `NULL`
- `openssl rand -hex 32`
- `algorithms=["HS256"]` `alg` `alg: none`
- `redis-main`
- `expo-secure-store` `80-mobile.md`
- `localStorage` `sessionStorage`
- `chrome.storage.session` `TRUSTED_CONTEXTS` `chrome.runtime.sendMessage` `chrome.identity.launchWebAuthFlow` `code_verifier` `crypto.subtle` `storage.session`
- `x-middleware-subrequest` `middleware.ts` `proxy.ts` `middleware.ts`
- `CORSMiddleware` `allow_origins`
- `X-Frame-Options: DENY` `frame-ancestors`
- `APIKeyHeader` `require_api_key` `SERVICE_API_KEY` `PROXY_API_KEY` `python-api` `internal_auth.py` `metrics.py` `/metrics` `SERVICE_INTERNAL_SECRET_KEY`
- `os.getenv("KEY", "default")` `config/production.yml` `settings.production`
- `POST /auth/passwordless/request` `AUTH_PASSWORDLESS_REQUEST_CAP` `AUTH_PASSWORDLESS_IP_REQUEST_CAP` `POST /auth/passwordless/verify`
- `expo-secure-store`
- `shape.is_admin_dashboard: true` `two_factor` `fabrik apply` `/health` `/metrics` `saas/60-saas-ui.md` `shape.has_bearer_api: true` `two_factor`
- `^/api/` `/api/*` `/api/v1` `/api/*` `shape.bearer_bypass_prefix: "^/api/v1"` `fabrik apply` `^/` `orchestrator/verifier.check_api_bypass` `/api/*` `^/api/`
```

## Evidence

### Phase A

- `src/fabrik/orchestrator/infrastructure.py:1607-1619` — the refusal block; `:764-766` — `watchdog_lives`;
  `:455-462` — the plan clause; `:137-157` — the shared rewrite the new function sits beside.
- `src/fabrik/drivers/watchdog.py:546` — the default URL; `:560` `target_vps`; `:566` the local import; `:568-571`
  the existing spoke rewrite.
- `src/fabrik/drivers/ssh.py:182-241` — `ssh()`'s raise surface.

```
$ command grep -rn "D-1153\|W-5dcafaef\|refused on spoke" src tests specs --include=*.py --include=*.yaml
src/fabrik/orchestrator/infrastructure.py:132:    way ``drivers/watchdog.py`` does, so the registrar's spoke refusal (D-1153) and the driver never disagree."""
src/fabrik/orchestrator/infrastructure.py:460:                f" — refused on spoke {spec['target_vps']} until apprise is mesh-published (D-1153)"
src/fabrik/orchestrator/infrastructure.py:764:        # D-1153: a spoke watchdog is refused in _provision_watchdog; nothing it alone needs is provisioned
src/fabrik/orchestrator/infrastructure.py:1616:                    "this spec, or wait for W-5dcafaef (apprise mesh-published, a spoke login preflight)"
tests/test_watchdog_spoke_preflight.py:78:    assert any(f.startswith("watchdog:") and "W-5dcafaef" in f for f in ctx.registrar_failures)
tests/test_watchdog_spoke_preflight.py:109:    assert "refused on spoke vps2" in spoke[1] and "D-1153" in spoke[1]
specs/services/spoke-canary.yaml:28:# D-1153: a spoke watchdog cannot alert (apprise is vps1-only) and is refused; W-5dcafaef lifts this once mesh-published.
```

The two new rules (Phase A step 3) run before the first pin, over the Behavior Contract inputs plus near-misses (`/fabrik-plan-review` arming step 2). A spoke URL with no path (`http://apprise:8000`) stays untouched by design — the matcher includes the slash (spec `:207-209`) and the default URL always carries `/notify/alerts` (`src/fabrik/drivers/watchdog.py:546`).

```python
# Throwaway probe of the plan's two new rules (Phase A step 3), over the Behavior Contract inputs (v2).
HUB = "10.99.0.1"
A = "//apprise:8000/"
G = f"//{HUB}:8202/"


def rewrite(url, t):
    if not url or (t or "vps1") == "vps1":
        return url
    return url.replace(A, G)


for url, t in [
    ("http://apprise:8000/notify/alerts", "vps2"),
    ("http://apprise:8000/notify/alerts", "vps1"),
    ("http://apprise:8000/notify/alerts", None),
    ("http://other:8000/notify/alerts", "vps2"),
    ("http://u:p@apprise:8000/notify/alerts", "vps2"),
    ("", "vps2"),
    (None, "vps2"),
    ("http://apprise:80000/x", "vps2"),
    ("http://apprise:8000", "vps2"),
]:
    print("rewrite", repr(url), t, "->", repr(rewrite(url, t)))

H = "/home/ozgur/.claude"
P = [H + ".json", H + "/.credentials.json"]
GATE = ("gate reachable", "gate unreachable")


def parse(out, spoke, target="vps2", alias="vps2"):
    """None = pass; else the one-line failure text (spec :245-257)."""
    lines = out.splitlines()
    files = [ln for ln in lines if ln.startswith(("present ", "missing "))]
    gate = [ln for ln in lines if ln in GATE]
    named = [ln[8:] for ln in files]
    if (
        len(lines) != len(files) + len(gate)
        or sorted(named) != sorted(P)
        or len(gate) != (1 if spoke else 0)
    ):
        return f"could not check {target} ({alias}): unexpected output"
    parts = [f"missing {ln[8:]}" for ln in files if ln.startswith("missing ")]
    if gate and gate[0] == "gate unreachable":
        parts.append(f"gate unreachable from {target}")
    return f"{target} ({alias}): " + "; ".join(parts) if parts else None


ok = f"present {P[0]}\npresent {P[1]}"
for name, out, spoke in [
    ("both present vps1", ok, False),
    ("both present spoke", ok + "\ngate reachable", True),
    ("spoke, no gate line", ok, True),
    ("one missing", f"present {P[0]}\nmissing {P[1]}", False),
    ("both missing", f"missing {P[0]}\nmissing {P[1]}", False),
    ("empty", "", False),
    ("banner", ok + "\nWelcome!", False),
    ("gate unreachable", ok + "\ngate unreachable", True),
    ("missing + gate unreachable", f"missing {P[0]}\npresent {P[1]}\ngate unreachable", True),
    ("truncated", f"present {P[0]}", False),
    ("other path", f"present {P[0]}\npresent /etc/x", False),
    ("contradictory", f"present {P[0]}\nmissing {P[0]}\npresent {P[1]}", False),
    ("gate line on vps1", ok + "\ngate unreachable", False),
    ("two gate lines", ok + "\ngate reachable\ngate unreachable", True),
]:
    print("parse", name, "->", parse(out, spoke))
```

```
$ python3 rules.py   # v2, after pass 1
rewrite 'http://apprise:8000/notify/alerts' vps2 -> 'http://10.99.0.1:8202/notify/alerts'
rewrite 'http://apprise:8000/notify/alerts' vps1 -> 'http://apprise:8000/notify/alerts'
rewrite 'http://apprise:8000/notify/alerts' None -> 'http://apprise:8000/notify/alerts'
rewrite 'http://other:8000/notify/alerts' vps2 -> 'http://other:8000/notify/alerts'
rewrite 'http://u:p@apprise:8000/notify/alerts' vps2 -> 'http://u:p@apprise:8000/notify/alerts'
rewrite '' vps2 -> ''
rewrite None vps2 -> None
rewrite 'http://apprise:80000/x' vps2 -> 'http://apprise:80000/x'
rewrite 'http://apprise:8000' vps2 -> 'http://apprise:8000'
parse both present vps1 -> None
parse both present spoke -> None
parse spoke, no gate line -> could not check vps2 (vps2): unexpected output
parse one missing -> vps2 (vps2): missing /home/ozgur/.claude/.credentials.json
parse both missing -> vps2 (vps2): missing /home/ozgur/.claude.json; missing /home/ozgur/.claude/.credentials.json
parse empty -> could not check vps2 (vps2): unexpected output
parse banner -> could not check vps2 (vps2): unexpected output
parse gate unreachable -> vps2 (vps2): gate unreachable from vps2
parse missing + gate unreachable -> vps2 (vps2): missing /home/ozgur/.claude.json; gate unreachable from vps2
parse truncated -> could not check vps2 (vps2): unexpected output
parse other path -> could not check vps2 (vps2): unexpected output
parse contradictory -> could not check vps2 (vps2): unexpected output
parse gate line on vps1 -> could not check vps2 (vps2): unexpected output
parse two gate lines -> could not check vps2 (vps2): unexpected output
```

### Phase B

- `infra/vps1/apprise/compose.yaml:3-4` header, `:10-12` environment, `:30-33` memory format, no `configs:`/`ports:`.
- `configs/gatus/apps/apprise.yaml:1-9` — the endpoint shape to copy.
- `specs/services/spoke-canary.yaml:28-30` — the opt-out.
- `scripts/update_vps_docs.py:367-371` rewrites only vps-urls.md's timestamp, so hand rows survive;
  `scripts/enforcement/check_env_contract.py:120-130` skips `infra/vps1/apprise/` (no `.env.example`), and the new
  env value is a literal `"0"`.

```
$ command grep -rlI "apprise:8000\|notify/alerts" src scripts infra configs templates libs   # 20 files; none uses attachments (spec Derivations)
src/fabrik/spec_loader.py
src/fabrik/drivers/backrest.py
src/fabrik/drivers/watchdog.py
scripts/sysadmin/monthly-backup-verify.sh
scripts/sysadmin/proactive-check.sh
scripts/sysadmin/system-prompt.txt
scripts/sysadmin/ensure-apprise-alerts-config.sh
scripts/sysadmin/daily-digest.sh
scripts/sysadmin/morning-report.sh
scripts/sysadmin/fabrik-alert-canary.sh
scripts/sysadmin/weekly-maintenance.sh
scripts/sysadmin/weekly-security.sh
configs/gatus/core/infra.yaml
configs/gatus/apps/apprise.yaml
configs/gatus/_base.yaml
configs/n8n/workflows/backup-notification.json
configs/n8n/workflows/uptime-alert.json
libs/alerting/apprise.py
libs/alerting/README.md
libs/alerting/__init__.py
```

### Phase C

- spec § Lifecycle `:364-396`, § Validation `:517-529`; the live vps1 state the spec executed on 2026-10-23
  (`:109-118`).

## Self-audit

- Grounding passes: three native seats (Opus authoritative: registrar census + test fallout; Sonnet: infra/docs
  landing sites; Sonnet: sidecar contract and what the spec's anchors miss) plus the lead's own reads above.
  Findings merged: the spoke-canary comment cites D-1153 (not D-1156) — Phase B deletes `:28-30` whole; seat 3's
  "libs/alerting and Backrest break on spokes" refuted (I23); vps-urls.md hand rows survive the sync script.
- (a) Coverage: every "What we already agreed" row maps to a phase — gate, attachment lock → B (mirror) + C (deploy);
  URL, refusal lift, preflight → A; firewall → none (no change); acceptance → C8-C9; lifecycle → C5-C9, rollback
  → C10; docs → B6, A3, C7.
- (b) Signatures: `_rewrite_mesh_gated_url(url, target_vps)` is produced in A3 and consumed in A4 with the same name;
  the preflight returns `str | None` and is consumed once in `_provision_watchdog`.
- Fixed point: reached — `/fabrik-plan-review` pass 3 confirmed 0 with the plan md5 unchanged (§ Pass Ledger);
  receipt `docs/development/reviews/2026-10-23-spoke-watchdog-apprise-mesh-gate-plan-review.md`.

## Pass Ledger

| Pass | seats · axes re-checked (claims · gates · interfaces · completeness) | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (header, Global Constraints, Context Ledger, Constraints Digest, File Scope, Coverage Checklist, Evidence, Self-audit, Pass Ledger, Residuals) + sonnet×1 (What we agreed, Intake, Phases A-C) · all axes · shape: agent-tool (D-961) | found: 21, new: 21, confirmed: 20, fixed: 20, unexecuted: 0, edits: 26 | method: citation — full pass; every candidate executed by the orchestrator (the parse fail-opens re-run as rules2.py, 14 cases; `check_doc_sync.py:393-405` staged mode read; `work.py:6485-6499`; `mail.py:2966-2995`; the missing test path `ls`-ed; the curl image tag probed 200); 1 RECORDED — measured (wording; changes no behaviour: the provider read is the registrar's form of `watchdog.py:521`); flip gates at pass 1 on a flipped copy in a throwaway worktree: `check_convergence` graded it (red only on UNCHECKED rows and no re-derivation row), `check_rule_grounding` 5 CONVERGED in-window plans, 0 findings, `check_plan_quality` 0 findings and red on an Appetite-less mutant | 2a7f0ac3… → 6d251bd2… |
| Pass 2 | the round-1 slice owners (opus×1 + sonnet×1) · their own claims over the pass-1 fix diff + one hop · shape: agent-tool | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 1 | method: re-derivation — opus slice 8/8 claims re-verified, the v2 probe re-run from the pin (23 of 23 lines identical); sonnet slice 11/12 verified, S9 residue confirmed (own-fix: round 1 — C step 7's kaizen mail cited a merge sha before the merge); RECORDED — measured: probe 3 proves little since the gate binds only 10.99.0.1 (spec `:379` wording, W-2ce2df52); the step-6 Gatus follow-up commit lands after the `--range` doc-sync (trivial); nobody named to resume at step 8 (pre-existing); the probe's vps1-gate-line case keeps the vps2 label (the Phase A test passes `target="vps1"`); the ledger row cannot hold its own file's md5 (by construction) | 95e84baf… → 434d24fe… |
| Pass 3 | sonnet×1 (round-1 owner of the only slice holding an open claim; opus-rule stands at 8/8 from pass 2) · the two pass-2 hunks + one hop · shape: agent-tool | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — S9 re-executed against `merge_request.py:283-292` (the request records the pushed tip); the pins-2 → pins-3 diff is exactly the two hunks (7 lines); the Intake counts (23 · 14 IN · 9 OUT) and Phase C's ten steps re-derived from the pin; standing clean since pass 2: every other class | 2681694c… → 2681694c… ✓ |

## Residual unknowns

- **Resolved:** the D-1156 vs D-1153 comment (Phase B deletes the lines whole); vps-urls.md sync safety; the env
  contract.
- **Open — U3 (W-cb08c877):** docker before wg0 on vps1; owned there, the gate inherits it (spec `:455`).
- **Self-service — U4, measured at deploy (C step 6):** the refused-`attach` probe; if not refused, C step 10's
  rollback runs, the gate is never brought up and a new item is filed (spec `:456-458`).
- **Self-service — the Gatus URL form:** B4 writes the mesh form; if deploy probe 4 (C step 6) shows a vps1
  container cannot reach the mesh IP, C step 6 rewrites the endpoint to `http://apprise-mesh-gate:8202/healthz` on
  a follow-up commit before the merge request (C step 7).
