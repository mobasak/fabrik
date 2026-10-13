# Plan — the Coolify-bound verbs move to SSH + Compose and the Coolify code leaves the tree (W-36571dff)

Status: DRAFT
Profile: delta
**Owner:** fleet
Spec: docs/superpowers/specs/2026-10-14-coolify-verb-retirement-design.md (CONVERGED, panel-approved D-828; md5 35e84255394b562cfa1097570fd05f1d, 454 lines)
**Surface:** `git rev-parse HEAD` = 5fd9a6711614edd3e107928a4874cbf48fc262ac (worktree-fleet, master merged in); the spec's 157 `path:line` citations all land here and `git diff --stat 6319349e2 5fd9a6711 -- src scripts tests` touched none of its cited source files.

A spine + ticket SET: thirteen tickets in four lifecycle phases (spec § Lifecycle ordering, cr-21) — (A) the rebases built beside
the old code: T01 → T02 → T03 → T04; (B) the retirements inside kept files: T05 → T06, T07a, T07b, T08; (C) the deletions:
T09; (D) docs and the capability index: T10a, T10b → T11. **Appetite:** the spec's 600 minutes bind phases A + B + C
without D11's script rebases (T01–T07b + T09 = 525); the whole set is 780, and T08 (90), T10a/T10b (105) and T11 (60)
are the 255 that may spill into a second session — the spec marks the END OF PHASE C (T09 merged) as this session's hard
stop, each stop point green on its own. Estimated diff: ≈ +900 / −2,700 code lines (the five modules and 53 tests are
2,437 lines; the helpers, the two verbs and their graders ≈ 900), tests excluded, across 25 code files.

## What we already agreed

Every line cites the spec section it comes from; nothing the section already says is restated.

- The goal, the three verbs' fate and the five invariants — spec § Goal, § The delta (invariants 1–5).
- D1 retire `apply --legacy`/`--use-orchestrator`/`--skip-dns`/`--skip-deploy`, keep `--yes`, delete `deploy.py` — spec § The delta D1 → T05.
- D2 `status` = state record + `probe_app` walk over `app_dir`; `find_existing` untouched — spec § The delta D2 → T01, T02.
- D3 `reconcile-all` = one `compose ls -a --format json` per host, the match rule, the exit rule, `refresh_infrastructure`'s swap around the `probe_app` walk only, `ctx.app_name` = matched basename, `target_vps` parameter — spec § The delta D3, invariant 2 → T01, T03.
- D4 `projects --sync` = the scanner, registry built after, Coolify fields gone — spec § The delta D4 → T04.
- D5 `/health` drops the Coolify check and adds nothing — spec § The delta D5 → T07b.
- D6 export/import lose the Coolify section; `ignored_legacy` counted and printed — spec § The delta D6 → T06.
- D7 the rollback branch retired — spec § The delta D7 → T07a.
- D8 the five modules, their tests and the patches deleted; `drivers/__init__` edited in the same commit — spec § The delta D8, invariant 4 → T07a (patches), T09.
- D9 the persisted keys keep their names; docstrings corrected — spec § The delta D9, invariant 5 → T07b.
- D10 every W21 line current; `docs/CAPABILITIES.md` regenerated — spec § The delta D10, § Documentation landing sites → T10a, T10b, T11.
- D11 two scripts deleted, four rebased — spec § The delta D11 → T08, T09.
- The Compose JSON contract (20 keys, JSON Lines + array fallback, `Health` `""`, `ConfigFiles` comma-joined) — spec § The delta invariant 3, § External dependencies E1–E2 → T01.
- Graders red-first in a throwaway worktree; the hub's pytest leg is OFF, so touched test files run by hand with totals — spec § Constraints, § Validation V9 → every ticket's Gate.
- R1, the plan's ONE read-only ssh to vps1 (`docker compose ls -a --format json` beside `ls -d /opt/*/compose.yaml`, the `label=coolify.serviceName=meilisearch` container, the Authelia volume path) — spec § Open unknowns U3, U5, D11 → § Execution Discipline (the orchestrator's step before T03's dispatch).
- `fabrik logs` is out of scope; the hub image's own fate is W-2191a0f4 (parked, tagged `waits-w36571dff-plan`); the deploy path's local-source env defect is W-9550a69c — spec § What exists today W2, § Rejected alternatives C2, § Open unknowns U6.
- Received decisions this run (no operator ruling; the spec's gaps the grounding seats found, filled by plan-level decisions and rowed in `docs/DECISIONS.md` with this plan's commit): (1) `app_dir` keys on `name or id` (the code keys on name: `orchestrator/__init__.py:483`, `deployer_ssh.py:180`; 0 of 69 specs set `name`); (2) the `fabrik-` fallback candidate is skipped when the id already starts with `fabrik-` (today's guard, `cli.py:1581-1582`; 11 of 69 ids); (3) a local `path: None` falls back to `/opt/<name>` as `_deploy_local` does; (4) a non-JSON `ls` body is a `host-unreachable` row, an `app_dir` `ProvisioningError` is an `error` row in `reconcile-all` and `Error:` + exit 1 in `status`; (5) `docs/infrastructure/`'s generated Coolify-era content (79 live lines) is OUT of this plan — backlog item W-53f8a3f3 regenerates it with one read-only ssh after execution; (6) `docs/CAPABILITIES.md` and `docs/reference/apis/EXTERNAL_SYSTEMS.md` are owned by the Integration ticket (each alone exceeds the READ budget).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "Plan it as Profile: delta with the spec's § Lifecycle ordering — (A) … (B) … (C) … (D)" (the invocation) | IN | the four phases above; § Merge Order |
| I2 | "the END OF PHASE C is the session's hard stop (appetite 600 min, panel estimate 450–650; D and D11's four script rebases may spill)" | IN | the header's appetite paragraph; § Execution Discipline |
| I3 | "R1 (the one read-only vps1 ssh …) belongs to the plan's first phase as evidence, not a dependency; a VPS touch beyond that one read is never in scope" | IN | § Execution Discipline (R1), § Global Constraints |
| I4 | "Graders red-first per § Validation V1–V10 … measured in a throwaway worktree (the root conftest pins the checkout src)" | IN | § Execution Discipline (Red first); every ticket's Behavior Contract |
| I5 | "Ground every step at path:line in the tree at 5fd9a6711 … re-check anchors that master's merges may have moved" | IN | § Evidence (every anchor re-read by the four grounding seats; none moved) |
| I6 | spec D1–D11, invariants 1–5 (spec § The delta) | IN | T01–T11, see § What we already agreed |
| I7 | spec § Validation V1–V10 | IN | V1 → T01/T02 · V2 → T01 · V3 → T03 · V4 → T04 · V5 → T07b · V6 → T06 · V7 → T07a · V8 → T09, T11 · V9 → every Gate · V10 → T11 |
| I8 | spec § Documentation landing sites (every line) + the three uncited rows the grounding found (`INDEX.md:1712` not `:1711`, `INDEX.md:1981`/`:1984`, `docs/reference/health-monitoring.md:282-286`) | IN | T10a, T10b, T11; `Docs:` fields for the governance files |
| I9 | U1 grounding: "`refresh_infrastructure` never sets `ctx.target_vps` … the ticket should say ADD a target_vps-resolution line" | IN | T03 Scope ("ADDS") |
| I10 | U4 grounding: "the code keys on NAME first … `app_dir` should use `name or id`" | IN — received decision (1) | T01; § What we already agreed |
| I11 | U4 grounding: "`cli.py:1581`'s `fabrik-` guard is dropped without saying so … 11 specs whose ids already start with `fabrik-`" | IN — received decision (2) | T01 |
| I12 | U4 grounding: "A local source with `path: None` is unspecified for `app_dir`" | IN — received decision (3) | T01 |
| I13 | U4 grounding: "which row a non-JSON or banner `ls` body becomes … which row an `app_dir` `ProvisioningError` … becomes" | IN — received decision (4) | T02, T03 |
| I14 | U4 grounding: "Setting `ctx.target_vps` changes registrar behaviour, not just the probe" | IN | T03 Behavior row 5 asserts the ctx the provisioner receives; § Residual unknowns R-open-3 |
| I15 | U4 grounding: deletion order — "coolify.py must go LAST, in the same commit as the `drivers/__init__.py:12` edit" | IN | T09 Scope, § Merge Order |
| I16 | U2 grounding: "LIFO (:58-78) and continue-on-error (:80-103) tests need a body rewrite … the spec's MIRROR note treats them identically to the trivial cases" | IN | T07a |
| I17 | U2 grounding: `tests/test_portability.py:16-17` and `:523-526` docstrings stale after D6 | IN | T06 |
| I18 | U3 grounding: `check_health.py:29`'s `check_coolify` regex literal goes dead | IN | T09 |
| I19 | U3 grounding: "`docs/infrastructure/` non-archive generated docs … cannot be fixed by this plan's source edits alone" | OUT-OF-SCOPE — needs a live read of vps1 beyond R1; boarded as backlog item W-53f8a3f3 (`.fabrik/work/W-53f8a3f3.json`, linked to the spec) | — |
| I20 | U3 grounding: `check_retired_terms.py` bans `Coolify` over `docs/**/*.md` + `README.md` only, WARN-only, never fails a gate | IN | T10a/T10b Gates state the WARN count before and after |
| I21 | U4 grounding: V8 baseline — 26 files today, 981 tracked `*.py` outside the archives; vulture baseline 1 item (`coolify.py:705`) | IN | T09, T11, § Evidence |
| I22 | "W-2191a0f4 (hub image fate — parked, infra tagging it), W-9550a69c (deploy-path local-source env defect — out of scope), W-08be3ec9 (review residue)" | OUT-OF-SCOPE — each already boarded with its own item | — |
| I23 | spec U5: `portability._collect_authelia`'s volume comments reworded to what R1 reads | IN | T06 Scope; § Execution Discipline (R1 hands T06 the reading) |
| I24 | "Quota: the active account is near its 5h wall with a successor — commit and push at every phase boundary" | IN | § Execution Discipline (Commits) |
| I25 | "finished work → merge_request.py request" | IN | § Execution Discipline (Merge) |

Intake: 25 items — 23 IN, 2 OUT-OF-SCOPE (I19 → W-53f8a3f3; I22 → W-2191a0f4, W-9550a69c, W-08be3ec9), 0 ASK.

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | deployer helpers: `app_dir`, `_host_env`, `probe_app`, `list_compose_projects`, `_parse_compose_ps` | — | ⚡ | ⬜ | |
| T02 | `fabrik status` prints the last apply and the live containers | T01 | ⛓️ | ⬜ | |
| T03 | `fabrik reconcile-all` reads the deployed set from Compose; `refresh_infrastructure` walks `app_dir` | T01, T02 | ⛓️ | ⬜ | |
| T04 | `fabrik projects --sync` re-scans `/opt`; the registry loses its Coolify fields | T03 | ⛓️ | ⬜ | |
| T05 | `fabrik apply` loses its legacy flags; `deploy.py` is deleted; cli wording | T04 | ⛓️ | ⬜ | |
| T06 | export/import drop the Coolify section; legacy members counted | T05 | ⛓️ | ⬜ | |
| T07a | `RollbackManager` loses its Coolify branch; vestigial patches leave the orchestrator tests | — | ⚡ | ⬜ | |
| T07b | hub `/health` drops the Coolify check; state and context words; env placeholders go | — | ⚡ | ⬜ | |
| T08 | the four hub scripts bound to the driver are rebased | T01, T05 | ⚡ | ⬜ | |
| T09 | the Coolify modules, their tests and the two dead scripts are deleted in one commit | T06, T07a, T07b, T08 | ⛓️ | ⬜ | |
| T10a | the reference, module and operations docs stop calling the verbs broken | T09 | ⚡ | ⬜ | |
| T10b | the root docs, the configuration doc and the infra map say what the hub does now | T09 | ⚡ | ⬜ | |
| T11 | Integration: the capability index, the two over-budget docs, the whole-plan gate and the receipt | T10a, T10b | ⛓️ | ⬜ | |

## Merge Order

1. T01
2. T02
3. T03
4. T04
5. T05
6. T06
7. T07a
8. T07b
9. T08
10. T09
11. T10a
12. T10b
13. T11

The deployer helpers first (T01), then the four `cli.py` tickets serialized on that one file (T02 → T03 → T04 → T05 → T06);
T07a and T07b share no file with the chain and may merge at any point before T09; T08 waits for T01 (its `probe_app`
rebase) and T05 (the `--use-orchestrator` flag it drops from `proof_run.py:518`); the deletions (T09) after every importer
is edited; the two docs tickets in parallel after T09 (they name its sha); the integration last. No two Depends-unconnected
tickets share a path.

## Interfaces

- **T01 → T02, T03, T08 — the deployer helpers** (`src/fabrik/orchestrator/deployer_ssh.py`, module level unless noted):
  - `def app_dir(spec: dict[str, Any] | Spec) -> list[str]` — the candidate directories in probe order; `<n>` is `name or id`; a local source yields `[normalised path]` (RAW, no trailing slash; `path: None` → `/opt/<n>`), a parent other than `/opt` raises `ProvisioningError`; otherwise `[/opt/<n>, /opt/fabrik-<n>]` with the second only when `<n>` does not start with `fabrik-`.
  - `@contextlib.contextmanager def _host_env(host: str | None) -> Iterator[None]` — sets `FABRIK_VPS_SSH_HOST` for the block and restores or pops it after; `"vps1"` and `None` are a no-op (`drivers/ssh.py`'s `DEFAULT_SSH_HOST` is the alias `vps`). `_target_vps_env(ctx)` delegates: `with _host_env(getattr(ctx, "target_vps", None)): yield`.
  - `SSHDeployer.probe_app(self, path: str) -> dict[str, Any]` — `{"exists": bool, "ps": str, "error": str | None}`; two ssh calls (timeouts 10 and 15), `shlex.quote` applied once at the shell boundary; never raises.
  - `SSHDeployer.list_compose_projects(self, host: str) -> list[dict[str, Any]]` — `sudo docker compose ls -a --format json`, `timeout=60`, under `_host_env(host)`; raises `RuntimeError`/`subprocess.TimeoutExpired`, a non-JSON body as `RuntimeError` naming the host.
  - `def _parse_compose_ps(text: str) -> list[dict[str, str]]` — JSON Lines or a leading-`[` array → rows of `Service`, `State`, `Health`, `ExitCode`.
  - Seam tests, owned by the consumers: `tests/test_cli_status_live.py` (T02) runs the REAL `_parse_compose_ps` on the fixture and fakes only `probe_app`; `tests/test_reconcile_all_deployed_set.py` (T03) drives the REAL `refresh_infrastructure` + `app_dir` + `probe_app` over a fake `fabrik.drivers.ssh.ssh`; T08's `proof_run.py` reads `probe_app(app_dir(spec)[0])`.
- **T03 → `cli.py` redeploy (same ticket)** — `DeploymentOrchestrator.refresh_infrastructure(self, spec_path: Path, dry_run: bool = False, target_vps: str | None = None) -> DeploymentContext`; precedence flag > `spec.target_vps` > `"vps1"`; `ctx.target_vps` set before the walk and persisted.
- **T06 → `cli.py` import printer (same ticket)** — `plan["ignored_legacy"]: int`, a top-level key beside `sections`/`actions`, present only when a legacy `coolify/*` member was seen; the printer line `ignored legacy members (coolify/*): <n>`.
- **T09 → T10a, T10b** — T09's merge commit sha is the "removed at <sha>" address the docs cite; the orchestrator passes it in the two docs tickets' dispatch briefs.
- **The orchestrator → T03, T06, T08 — R1's reading** (a file under the plan's scratch, pasted into § Evidence at execution): the `compose ls -a --format json` array for vps1 beside `ls -d /opt/*/compose.yaml`, whether a container carries `label=coolify.serviceName=meilisearch`, and the Authelia configuration volume path.

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket, on the coder's return, runs the full `/fabrik-review` on its changed surface to a coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green. T09 touches `scripts/enforcement/check_health.py` (never-route) and is coded natively; the Finish `/fabrik-review` over the whole-plan diff is T11's, file-partitioned (Sonnet + Haiku finders per slice, the orchestrator executing every refutation — D-344, D-335), one receipt.
- **Dispatch policy** — native Claude seats for every fan-out (the pool is OFF, D-181/D-182): `dispatch_headroom.py` then `python3 scripts/command_run.py dispatch --seats N` before each fan-out. Coders: Opus for T01 and T03 (`native` — the deployer seam and the host-swap/exit-rule design), Sonnet for T02, T04, T05, T06, T07a, T07b, T10a, T10b (`simple`) and T08 (`complex`); T09 is `never-route` (Sonnet by default, Opus if the deletion commit needs the importer graph re-derived); T11 is the orchestrator's. Haiku never codes.
- **R1 is the orchestrator's, before T03 is dispatched** — ONE read-only ssh to vps1 (`sudo docker compose ls -a --format json`; `ls -d /opt/*/compose.yaml`; `sudo docker ps --filter label=coolify.serviceName=meilisearch --format '{{.Names}}'`; the Authelia configuration volume path) — its output pasted into § Evidence and handed to T03, T06 and T08 as a file. No seat ever sshes; no VPS mutation anywhere in this plan.
- **Red first** — every ticket's graders are written and SEEN RED before its code in a throwaway worktree (`git worktree add <scratch>/probe HEAD`; the root conftest pins the checkout src, so a PYTHONPATH copy is vacuous); the hub's pytest leg is OFF, so each ticket's Gate names its test files and the review states the `N passed` totals.
- **Commits** — every ticket's merge is one commit with explicit pathspecs and `Agent-Name: fleet` trailers; pushed at once (the active account runs near its 5h wall with a successor — a phase boundary is never left unpushed). The deletion commit (T09) deletes `drivers/coolify.py` and edits `drivers/__init__.py` together, after every importer is gone.
- **Parallelism + merge** — T01 alone; then the `cli.py` chain T02 → T03 → T04 → T05 → T06 serialized on one file, with T07a and T07b fanned out beside it and T08 after T05; T09 after all; T10a ∥ T10b after T09; T11 last. Every merge happens in § Merge Order through `merge_request.py` (fleet works in `.claude/worktrees/fleet`; infra merges).
- **Hard stop** — the end of phase C (T09 merged, pushed, its review CONVERGED) is this session's stop point when the appetite is spent; T08, T10a, T10b and T11 may open a second session, each stop point green.
- **Appetite (D11, dogfooded)** — each ticket's `Appetite:` is minutes; a ticket past 2× is re-planned with `/fabrik-plan-after-chat`, never pushed through.
- **Breadth advisory (`check_ticket_breadth.py`)** — 13 of 13 flagged at the emit gate (score = Behavior rows + areas; the provisional threshold of 5 flags every ticket with four or more rows). KEPT, with the reason: each ticket is ONE file-owning unit (one `cli.py` verb, one module, one script set) whose rows are the spec's V-rows for that surface, and splitting rows would multiply the serialized `cli.py` chain without dividing any file; the two splits the READ budget forced are already made (T07a/T07b, T10a/T10b). The flag is a prompt to look, not a verdict (its own calibration note: rho = 0.45); narrowing further is the operator's call.
- **Ids** — every D-row this plan mints uses `python3 scripts/decisions.py --reserve-id .`.

## Behavior Contract

- **Given** a recording fake `fabrik.drivers.ssh.ssh` (the `patch("fabrik.drivers.ssh.ssh")` shape of `tests/orchestrator/test_deployer_ssh.py:395-415`), **When** `SSHDeployer().probe_app("/opt/my app")` runs, **Then** the first command recorded is `sudo sh -c ` + `shlex.quote("[ -f " + shlex.quote("/opt/my app/compose.yaml") + " ] && echo exists || echo absent")` with `timeout=10` and the second is `cd ` + `shlex.quote("/opt/my app")` + ` && sudo docker compose ps -a --format json` with `timeout=15` (spec § The delta D2; V2).
- **Given** the first ssh call raises `RuntimeError` or `subprocess.TimeoutExpired`, **When** `probe_app` runs, **Then** the result is `exists` False, `ps` `""`, `error` naming the exception, and the second command is never sent; given the first call returns `""` or a login banner, **Then** `exists` is False and `error` is set (spec § The delta D2).
- **Given** the first call returns `exists` and the second raises `TimeoutExpired` or returns a non-JSON body, **When** `probe_app` runs, **Then** `exists` is True, `ps` holds the raw text and `error` is set — never an exception (spec § The delta D2; V2).
- **Given** a JSON-Lines `ps` fixture carrying the 20-key shape of invariant 3 plus one unknown key — rows running+healthy, exited+`""`, running+`""`, running+`"none"` — and the same rows wrapped as a `[` array, **When** `_parse_compose_ps` runs on each, **Then** both yield the same four rows of `Service`, `State`, `Health`, `ExitCode` and nothing else (spec § The delta invariant 3; V1's parser half).
- **Given** a dict spec `{"name": "refresh-test", "id": "refresh-test"}` with no `source`, a dict with `source: {type: local, path: "/opt/file-worker/"}`, a `Spec` model with a local `path`, a local `path: None`, and a spec whose id is `fabrik-citation-verifier`, **When** `app_dir` runs on each, **Then** it returns `["/opt/refresh-test", "/opt/fabrik-refresh-test"]`, `["/opt/file-worker"]` (slash stripped, RAW), the same for the model, `["/opt/<name>"]`, and `["/opt/fabrik-citation-verifier"]` with no `fabrik-fabrik-` candidate; a local `path: "/srv/x"` raises `ProvisioningError` naming the path (spec § The delta D2, D3; `cli.py:1581-1582`).
- **Given** `_host_env("vps1")`, `_host_env(None)` and `_host_env("vps2")`, **When** each block is entered and left (once by exception), **Then** the first two leave `FABRIK_VPS_SSH_HOST` untouched, the third sets it to `vps2` inside and restores the previous value or pops it after, and `_target_vps_env(ctx)` with `ctx.target_vps == "vps2"` produces the same env inside the block (spec § Contract deltas; `deployer_ssh.py:122-148`).
- **Given** a fake ssh returning `[{"Name":"a","Status":"running(2)","ConfigFiles":"/opt/a/compose.yaml,/opt/a/compose.dev.yaml"}]`, **When** `list_compose_projects("vps2")` runs, **Then** the command recorded is `sudo docker compose ls -a --format json` with `timeout=60`, `FABRIK_VPS_SSH_HOST` read `vps2` during the call and is restored after, and the result is that one-element list; a body that is not JSON raises `RuntimeError` whose message names `vps2` (spec § The delta D3, invariant 3).
- **Given** `tests/orchestrator/test_deployer_ssh.py` unchanged, **When** it runs after this ticket, **Then** 153 of 153 pass — `find_existing`'s recorded commands are byte-identical to today's (spec § Constraints; V2's last clause).
- **Given** a state record for the spec carrying `applied_at`, a 40-character `git_sha`, `target_vps: vps2`, two `registrars_applied` types and one `registrar_failures` row, **When** `fabrik status <spec>` runs with `probe_app` faked, **Then** the Last-apply section prints the timestamp, the sha truncated to 12 characters, `vps2`, both types and the failure row (spec § The delta D2a).
- **Given** no state record for the spec, **When** `fabrik status` runs, **Then** the Last-apply section prints `no state record — never applied from this checkout` and the exit code is 0 (spec § The delta D2a).
- **Given** `probe_app` returning `exists` True and the four-row JSON-Lines fixture of T01, **When** `fabrik status` runs, **Then** the REAL `_parse_compose_ps` yields four `Service · State · Health · ExitCode` lines, the running `""` row labelled `no healthcheck` and the exited `""` row labelled `—` (spec § The delta invariant 3; V1).
- **Given** `probe_app` returning `exists` False with `error` None for every candidate, **When** `fabrik status` runs, **Then** one `no <dir>/compose.yaml on vps1` line per candidate prints and the exit code is 0; given `exists` False with `error` set the line is `⚠️ could not reach vps1: <error>`; given `exists` True with `error` set it is `⚠️ could not read containers on vps1: <error>` — exit 0 in all three (spec § The delta D2, invariant 2).
- **Given** a record whose `target_vps` is `vps1` while the spec names `vps2`, **When** `fabrik status` runs, **Then** both hosts are printed, and `probe_app`'s calls ran with `FABRIK_VPS_SSH_HOST=vps2` (spec § The delta D2).
- **Given** a spec whose local `source.path` is `/srv/x`, **When** `fabrik status` runs, **Then** the output is `Error: ` + the `ProvisioningError` message and the exit code is 1, no ssh call made (plan decision; `cli.py:732-736` is the precedent).
- **Given** the rebased `status` function, **When** `inspect.getsource(fabrik.cli.status)` is searched, **Then** it contains neither `coolify` nor `Coolify` (spec § The delta D2; V8).
- **Given** a fake `list_compose_projects` returning `[{"Name":"a"},{"Name":"other","ConfigFiles":"/opt/x/compose.yaml,/opt/b/compose.yaml"},{"Name":"fabrik-d"}]` and a specs directory holding `a`, `b`, `c`, `d` and `fabrik-file-worker` (local `source.path: /opt/file-worker`, matched through a `ConfigFiles: /opt/file-worker/compose.yaml` row), **When** `fabrik reconcile-all` runs (dry run) with `refresh_infrastructure` faked, **Then** `a`, `b`, `d` and `fabrik-file-worker` print `dry-run`, `c` prints `skipped — no compose project (no containers) on vps1`, and `list_compose_projects` was called exactly once (spec § The delta D3; V3).
- **Given** the same run plus a spec on `vps2` whose `ls` raises `TimeoutExpired`, **When** `reconcile-all` runs, **Then** that spec's row is `host-unreachable — <error>`, every vps1 spec still reconciles, and `list_compose_projects` ran once for `vps1` and once for `vps2` (spec § The delta D3, invariant 2; V3).
- **Given** the exit rule of invariant 2, **When** `reconcile-all` runs under each case, **Then** the exit code is 1 when every host's `ls` raises (run without `--yes`); 1 under `--yes` with one `host-unreachable`, one `error`, one `spec-error` or one `lock-timeout` row (four runs) and 0 for the same four runs without `--yes`; 0 when every row is `reconciled` or `skipped`; 0 for a `--filter` matching no stem while a broken spec sits outside the filter (the filter runs before the load, so no `spec-error` row prints); 0 when every loaded spec is `spec-error` and 1 for the same run under `--yes`; 1 for an empty specs directory with `No specs found.` (spec § The delta invariant 2; V3).
- **Given** a spec whose local `source.path` is `/srv/x` and a host whose `ls` returns a non-JSON body, **When** `reconcile-all` runs, **Then** the rows are `error — <ProvisioningError message>` and `host-unreachable — <message naming the host>` and the run finishes its table (plan decision filling spec D3; invariant 2).
- **Given** the REAL `refresh_infrastructure` with a recording fake `fabrik.drivers.ssh.ssh`, a stubbed validator returning a dict with `target_vps: vps2` and a stubbed provisioner, **When** it runs, **Then** every `probe_app` command ran with `FABRIK_VPS_SSH_HOST=vps2`, the ctx the provisioner received has `target_vps == "vps2"`, `_persist_state` was called with that ctx, and a hub-side registrar ssh issued by the stubbed provisioner inside the same call sees `FABRIK_VPS_SSH_HOST` unset (spec § The delta D3, the 2026-06-02 revert; V3).
- **Given** `probe_app` stubs keyed by path, **When** `refresh_infrastructure` walks `app_dir`, **Then** a walk whose first candidate is `absent` and whose second returns `error` raises `ProvisioningError` whose message names the host; a candidate returning `exists` True with `error` set is a match; a walk where every candidate is `absent` raises naming `/opt/<n>` and `/opt/fabrik-<n>`; and the matched candidate `/opt/file-worker` sets `ctx.app_name == "file-worker"` (spec § The delta D3, panel C1; V3).
- **Given** `fabrik redeploy --refresh-infra --target-vps vps2 <spec>` on a spec with no `target_vps`, **When** it runs with `refresh_infrastructure` faked, **Then** the fake receives `target_vps="vps2"`; `reconcile-all` calls it with `target_vps=None` (spec § The delta D3, review O3-6; `cli.py:1281`).
- **Given** `tests/orchestrator/test_refresh_infrastructure.py` rewritten onto `probe_app` stubs keyed by path, **When** it runs, **Then** 5 of 5 pass and the not-found test asserts the every-directory `ProvisioningError` message (spec § The delta D3, panel C1).
- **Given** `fabrik projects --sync` with `subprocess.run` replaced by a recording fake that writes one new project row into the registry file, **When** it runs, **Then** the fake was called once with the argv `fabrik scan` uses (`cli.py:1673-1681`) and the new project appears in the listing — the registry was read after the subprocess returned (spec § The delta D4, review O15; V4).
- **Given** `fabrik projects --help`, **When** it runs, **Then** the `--sync` help reads `Re-scan /opt and merge the deploy state before listing` and the `--status` help names `ready/development` and not `deployed` (spec § The delta D4, panel C2).
- **Given** a `data/projects.yaml` row carrying `coolify_uuid` and `coolify_name`, **When** `ProjectRegistry` loads it, **Then** the `Project` has no such attributes, `to_dict()` emits neither key, and the row's other fields load unchanged (spec § The delta D4, MIRROR).
- **Given** the rebased `projects` function, **When** `inspect.getsource(fabrik.cli.projects)` is searched, **Then** it contains neither `coolify` nor `Coolify`, and `registry.update` is called nowhere in `cli.py` (spec § The delta D4, MIRROR; V4).
- **Given** `tests/test_sync_has_user_guide.py`, **When** it runs after the field removal, **Then** 5 of 5 pass (spec § Validation V9).
- **Given** `fabrik apply <spec> --legacy`, `--use-orchestrator`, `--skip-dns` and `--skip-deploy`, **When** each is invoked through `CliRunner`, **Then** each exits 2 with click's `No such option` naming the flag (spec § The delta D1).
- **Given** `fabrik apply <spec> --yes --dry-run` with the orchestrator faked, **When** it runs, **Then** `--yes` is accepted, the fake is called once, and `fabrik apply --help` carries `accepted for compatibility; the orchestrator path never prompts` (spec § The delta D1, review O2-8).
- **Given** the tree after this ticket, **When** inspected, **Then** `src/fabrik/deploy.py` is absent, `git grep -n deploy_to_coolify -- src` returns 0 lines, and `inspect.getsource(fabrik.cli.apply)` contains neither `legacy` nor `use_orchestrator` (spec § The delta D1; V8).
- **Given** the `destroy` preview and the `--partial` help, **When** `fabrik destroy --help` and the preview text are read, **Then** the help says `no DNS removal, no file cleanup` and no `Coolify application` line remains in `cli.py:1120-1130` (spec § The delta D10).
- **Given** `git grep -n -i coolify -- src/fabrik/cli.py` after this ticket, **When** it runs, **Then** every remaining hit lies inside the `export`/`import` lines T06 owns (`:2883-2889`, `:2963-2983`) and none elsewhere (spec § The delta D1, D10; V8).
- **Given** an export over a fixture repo, **When** `export_bundle` runs, **Then** the tarball has no member under `coolify/` and the manifest carries no `coolify` count (spec § The delta D6; V6).
- **Given** a hand-built legacy bundle with two `coolify/*.json` members, **When** `fabrik import --dry-run <bundle>` runs through `CliRunner`, **Then** `plan["ignored_legacy"] == 2` and the output contains the line `ignored legacy members (coolify/*): 2` (spec § The delta D6, panel; V6).
- **Given** `export_bundle` and `import_bundle`, **When** called with `coolify_client=object()`, **Then** each raises `TypeError` — the parameter is gone (spec § The delta D6, MIRROR).
- **Given** the README template written into a bundle, **When** read, **Then** its prerequisites and restore steps name SSH + Compose and carry no `Coolify` word (spec § The delta D6).
- **Given** `tests/test_portability.py` after the edits, **When** it runs, **Then** every test passes with the six call sites and the fixture removed, and `git grep -n -i coolify -- tests/test_portability.py` returns only the `coolify_uuid` key rows of D9's `test_collect_state_strips_coolify_uuid` (spec § The delta D6, D9; V9).
- **Given** a `DeploymentContext` carrying `add_resource("coolify", "x")`, **When** `RollbackManager().rollback(ctx)` runs, **Then** a warning naming `Unknown resource type` is logged and no exception is raised (spec § The delta D7; V7).
- **Given** `RollbackManager(coolify_client=object())`, **When** constructed, **Then** `TypeError` is raised, and `hasattr(RollbackManager, "_rollback_coolify")` is False (spec § The delta D7, MIRROR).
- **Given** three `dns`/`monitor` resources, **When** the rewritten LIFO test and continue-on-error test run, **Then** they assert three rollback calls in reverse order and one error recorded while the others complete — on surviving types, never through the retired branch (spec § The delta D7; `tests/orchestrator/test_rollback.py:58-103`).
- **Given** `tests/orchestrator/test_e2e_rollback.py` and `tests/orchestrator/test_infrastructure.py` after the edits, **When** they run, **Then** `git grep -n "fabrik.drivers.coolify" -- tests/orchestrator` returns 0 lines and 3 of 3 and 41 of 41 tests pass (spec § The delta D8; V8, V9).
- **Given** `src/fabrik/drivers/postgres.py:1835`'s docstring, **When** read, **Then** it names the alias-watcher pattern without the module name `coolify_alias` (spec § The delta D8).
- **Given** the DNS client faked healthy, **When** `GET /health` runs, **Then** the response is 200 and `checks == {"dns": …}` with no `coolify` key; given the DNS client faked failing, **Then** 503 with status `degraded` (spec § The delta D5; V5).
- **Given** `src/fabrik/health_app.py`, **When** inspected, **Then** it imports nothing from `fabrik.drivers.coolify`, its docstring names the DNS manager alone, and `compose.yaml` parsed with `yaml.safe_load` carries no `COOLIFY_*` environment entry (spec § The delta D5; V8).
- **Given** `src/fabrik/state.py` and `src/fabrik/orchestrator/context.py`, **When** read, **Then** the `coolify_uuid` docstrings describe the compose app name, the `ResourceRecord` type list and the `:15` comment hold `compose`, `dns`, `monitor` and no `coolify`, and `tests/test_state.py` (21) and `tests/test_sync_projects_state.py` (10) pass byte-unchanged (spec § The delta D9, invariant 5).
- **Given** `src/fabrik/config.py` and `.env.example`, **When** searched, **Then** `git grep -n -i coolify -- src/fabrik/config.py .env.example` returns 0 lines and `python3 scripts/final_gate.py --check --json`'s `.env` contract row stays green (spec § The delta D8, W17).
- **Given** the four rebased scripts, **When** `git grep -n -i coolify -- scripts/snapshot_vps_state.py scripts/update_vps_docs.py scripts/proof_run.py` runs, **Then** it returns 0 lines, and over `scripts/vps_sync.py` it returns only the `:512` label filter when R1 read that label on a live container (else 0) (spec § The delta D11; V8).
- **Given** `scripts/proof_run.py`, **When** `.venv/bin/python scripts/proof_run.py --help` runs, **Then** it exits 0, lists no `--use-orchestrator`, and `grep -n "COOLIFY_" scripts/proof_run.py` returns 0 lines (spec § The delta D11, D1).
- **Given** the worker-type proof with `probe_app` faked to return the four-row fixture of T01, **When** `proof_run`'s worker check runs, **Then** it reads every container's `State` through `_parse_compose_ps` and passes only when all are `running` (spec § The delta D11; `scripts/proof_run.py:758-764`).
- **Given** `scripts/update_vps_docs.py` after the edit, **When** `tests/test_update_vps_docs.py` runs, **Then** 5 of 5 pass and `render_limits_summary` is still called at its two sites (spec § The delta D11).
- **Given** the four scripts, **When** `py_compile` and `ruff check` run, **Then** both exit 0 — no unused import left by the removals (spec § Validation V8's `ruff` F401 clause).
- **Given** the tree after the commit, **When** `git grep -l -e drivers.coolify -e CoolifyClient -e deployer_coolify -e compose_updater -e coolify_alias -e deploy_to_coolify -- src scripts tests templates ':!*/.archive/*'` runs, **Then** it lists 0 files (26 at 5fd9a6711; denominator `git ls-files -- '*.py' | grep -vc '/.archive/'` = 981), the ten paths above are absent, and the seven non-import hits the spec names are each gone or reworded by their D-row (spec § Validation V8).
- **Given** `src/fabrik/drivers/__init__.py` after the edit, **When** `.venv/bin/python -c "import fabrik.drivers.ssh"` runs, **Then** it exits 0, and `from fabrik.drivers import CoolifyClient` raises `ImportError` (spec § The delta D8, MIRROR).
- **Given** `scripts/enforcement/check_health.py`, **When** read, **Then** `:28` names `DNSClient` alone and the `GOOD_PATTERNS` regex at `:29` carries no `check_coolify`; `tests/enforcement` tests that import it stay green (spec § The delta D11; U3 finding).
- **Given** `.venv/bin/python -m vulture src/fabrik --min-confidence 80`, **When** it runs after the deletion, **Then** it reports 0 items (the pre-delta baseline is 1: `src/fabrik/drivers/coolify.py:705: unused variable 'is_secret'`), and `.venv/bin/ruff check src scripts tests` is F401-clean (spec § Validation V8).
- **Given** the Gate's test directories, **When** they run, **Then** every collected test passes and the run's own `N passed` total is stated in the ticket's review (the hub's pytest leg is OFF, spec § Constraints; V9).
- **Given** the nine docs after the edit, **When** `git grep -n -i -e coolify -e "--skip-dns" -e "--skip-deploy" -e "--legacy" -e "--use-orchestrator" -- <the nine paths>` runs, **Then** every remaining hit is a sentence that says the surface was REMOVED or names the historical key (`coolify_uuid`), none describes a live Coolify dependency or a broken verb (spec § The delta D10; W21).
- **Given** `docs/reference/fabrik-cli-reference.md`, **When** read at the `apply`, `status` and `reconcile-all` rows, **Then** `apply`'s flag table lists no `--skip-dns`, `--skip-deploy` or `--legacy`, `--yes` reads "accepted, never prompts", `status` documents the Last-apply and Live-containers sections, and `reconcile-all` names `deployer_ssh.list_compose_projects` + `refresh_infrastructure` (spec § Documentation landing sites).
- **Given** `docs/reference/health-monitoring.md:282-286`, **When** read, **Then** it no longer says `coolify_alias.py` lives in the repo (grounding finding U3; spec § The delta D8).
- **Given** `docs/TROUBLESHOOTING.md:186` and `:202`, **When** read, **Then** the retired file is named "removed at <sha>" with T09's commit sha (spec § Documentation landing sites).
- **Given** the Gate, **When** `check_doc_links.py` and `check_retired_terms.py` run, **Then** both exit 0 and the retired-terms WARN count over the nine files is lower than before the edit (both numbers stated) (spec § Validation V10's doc half).
- **Given** `docs/DEPLOYMENT_ARCHITECTURE.md` after the edit, **When** read at `:75`, `:103`, `:137`, `:161`, `:166-167`, `:527`, `:547-548`, **Then** no `--skip-dns`/`--skip-deploy`/`--legacy` example remains, the `drivers/coolify.py` and `deploy.py` rows are gone, and the health_app row names the DNS check alone (spec § Documentation landing sites).
- **Given** `docs/CONFIGURATION.md:50-57` and `:659-666`, **When** read, **Then** `status`, `reconcile-all` and `projects --sync` are described by what they do now and no `COOLIFY_API_URL`/`COOLIFY_API_TOKEN` row remains — matching `.env.example` after T07b (spec § The delta D10; Doc Sync Matrix).
- **Given** `agents-fabrik.md:102` and `README.md:56`, `:559`, `:704`, **When** read, **Then** `reconcile-all` is named as the drift responder's live target and no sentence calls a verb Coolify-bound (spec § Documentation landing sites; `agents-fabrik.md:97-102`).
- **Given** the Gate, **When** `check_doc_links.py`, `check_retired_terms.py` and `check_doc_sync.py` run on the staged diff, **Then** all exit 0 and the retired-terms WARN count over the four files is lower than before the edit, both numbers stated (spec § Validation V10's doc half).
- **Given** the merged tree, **When** `scripts/generate_capability_index.py` runs, **Then** `docs/CAPABILITIES.md` lists neither `health_check_autonomous.py` nor `migrate_db_rename.py` and a second run produces no diff (spec § The delta D11; V10).
- **Given** `docs/reference/apis/EXTERNAL_SYSTEMS.md:284`, **When** read, **Then** it no longer cites `cli.py:399 --skip-dns` (spec § Documentation landing sites).
- **Given** the whole-plan diff, **When** V8's census runs over the merged tree, **Then** it lists 0 files of the 981-file denominator, `vulture src/fabrik --min-confidence 80` reports 0 items, and the receipt states both numbers with the commands (spec § Validation V8).
- **Given** the receipt, **When** `check_convergence.py` and `final_gate.py --check --json` run, **Then** the gate's `"status":"success"` envelope is pasted verbatim in the receipt, the receipt is CONVERGED after the Finish review's closing pass confirms 0, and the plan's `Status:` is EXECUTED (spec § Validation V10).

## Global Constraints

- Hub repo only; nothing touched is governance-synced (`scripts/fabrik_synced_manifest.py` names none of the paths); `libs/subagents/` is never touched (D-137).
- No VPS mutation; read-only ssh ONLY in R1, by the orchestrator; seats never ssh, never read any `.env` (`.env.example` is a documented placeholder file and IS edited by T07b), never read `~/.claude*`.
- Every ssh goes through `fabrik.drivers.ssh.ssh` under `_host_env`; no new host alias, key or sudo rule; `"vps1"` stays a no-op swap because the driver's default alias is `vps`.
- `find_existing` is untouched; `probe_app` is its sibling with `-a`, `sudo`, a quoted path and an `error` key.
- The deployed-set probe is bounded: one `ls` per distinct host, 60 s timeout, cached for the run.
- `docs/CAPABILITIES.md` changes only through `scripts/generate_capability_index.py`; `docs/development/plans/archived/2026-05-28-ssh-deployer.md` and the `.archive/` trees are frozen history.
- Python runs as `.venv/bin/python …`; no `uv run`/`uv sync`/`pip install` (the worktree `.venv` is shared); no deps-file edit.
- Infra invariants inherited from `agents-fabrik.md:78-105` and `:361-379`: `postgres-main:5432`/`redis-main:6379` never `localhost`; the external `fabrik` network; per-service `deploy.resources.limits.memory`; no host `ports:`; Traefik routes; stable container DNS; `fabrik apply` SSHes to the target VPS and runs Compose there (trigger, never execute, from a project).
- 12-Factor non-negotiables (every phase inherits): logs = unbuffered JSON to stdout only, never a logfile (XI); migrations never from `lifespan`/startup (XII); same backing services in dev/test/prod — no SQLite-for-Postgres, no `fakeredis` (X); no sticky sessions, session state in `redis-main` + `shape.needs_cache: true` (VI); no daemonizing / PID files (VIII); workers requeue in-flight jobs on SIGTERM, jobs idempotent (IX); releases immutable, never hot-patch a container (V); config = granular env vars, no grouped env sets, no secrets in code (III); shelled-out binaries installed + pinned in the Dockerfile (II). The hub's `/health` (T07b) stays a SHALLOW liveness endpoint (spec D5, E5).

## Constraints Digest

| Quote | Source |
|---|---|
| a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:22` |
| one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones | `.windsurf/rules/core/45-testing-strategy.md:20` |
| Zero new tests. Existing integration/E2E tests must pass. | `.windsurf/rules/core/45-testing-strategy.md:33` |
| a bare catch silently converts your 403/404 responses into 500s | `.windsurf/rules/core/10-python.md:190` |
| entry under ## [Unreleased]; INDEX.md reflects change | `.windsurf/rules/core/40-documentation.md:67` |
| The app writes structured events, unbuffered, to stdout and nothing else | `.windsurf/rules/core/55-observability.md:72` |
| the call gives up; the next is unaffected | `.windsurf/rules/core/58-resilience.md:57` |
| Never silently invent a self-healing response | `.windsurf/rules/core/self-healing.md:65` |
| runs as native subagents per core/62-using-subagents.md | `.windsurf/rules/ai/50-agentic.md:67` |
| ZERO secrets/constants in code | `.windsurf/rules/core/35-security-auth.md` (FLOOR, via `review_rubric.py`) |
| deploy.resources.limits.memory is mandatory. | `.windsurf/rules/core/30-ops.md:149` |

Rows 1–3 bind every ticket's graders (red-first; T09 is the Refactor row — zero new tests, every existing test green); row 4 binds `probe_app`'s and `reconcile-all`'s exception capture (specific exceptions, never a bare `except` that hides the cause); row 5 binds the governance files T11's `Docs:` owns; rows 6–8 bind T07b (`/health` logs to stdout, stays shallow) and T01/T03 (the 60 s `ls` timeout bounds one call); row 9 binds § Execution Discipline; rows 10–11 bind T07b's `compose.yaml`/`.env.example` edits (no secret, the memory limit untouched).

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | Behavior Contract per ticket; watched-fail-first; Refactor = zero new tests | `:20`, `:22`, `:33` |
| `.windsurf/rules/core/10-python.md` (ACTIVE) | exception discipline in the probe and the verbs; `.venv/bin/python` invocations | `:186-192`, `:231-243` |
| `.windsurf/rules/core/40-documentation.md` (ACTIVE) | the Doc Sync Matrix rows T10a/T10b/T11 own; CHANGELOG + INDEX on every change | `:24`, `:55-57`, `:67` |
| `.windsurf/rules/core/55-observability.md`, `58-resilience.md`, `self-healing.md` (ACTIVE on `health_app.py`) | `/health` stays shallow and logs to stdout; the 60 s timeout bounds the `ls` | `55:72`, `58:57`, `self-healing:65` |
| `.windsurf/rules/ai/50-agentic.md` (ACTIVE on the orchestrator) | native subagents for every fan-out | `:67` |
| FLOOR packs `35-security-auth`, `25-data-postgres`, `30-ops` (always injected) | no secret in code; the memory-limit invariant | `review_rubric.py` output in § Coverage Checklist |
| `fabrik-lib` | NO new capability — ssh, Compose parsing and click are in the tree; nothing to vendor | spec § fabrik-lib verdict |
| `agents-fabrik.md` deploy pipeline | `reconcile-all` is Gap 3's target (the drift responder); `fabrik apply` SSHes and runs Compose | `agents-fabrik.md:97-105`, `:361-379` item 7 |
| `specs/services/*.yaml` `shape:` | none changes — no registrar, flag, port or compose service | spec § Shape / infra implications |
| `docs/data-contract.md`, `docs/ui-design.md` | not present — the hub has neither | spec § Contract deltas |
| Research ledger | the Compose JSON facts (cr-22, cr-25, cr-28, cr-32–37, cr-46–48), click (cr-1, cr-2, cr-6, cr-42) | `docs/reference/research/2026-10-14-coolify-verb-retirement-ledger.md` (48 rows) |
| Routed residuals | W-53f8a3f3 (generated docs regeneration), W-2191a0f4 (hub image), W-9550a69c (deploy-path env), W-08be3ec9 (review residue) | `.fabrik/work/` |

## File Scope (owned paths)

- .env.example
- compose.yaml
- docs/CAPABILITIES.md
- docs/CONFIGURATION.md
- docs/DEPLOYMENT_ARCHITECTURE.md
- docs/SERVICES.md
- docs/TROUBLESHOOTING.md
- docs/development/reviews/2026-10-14-plan-1-coolify-verb-retirement-review.md
- docs/operations/deployment.md
- docs/reference/apis/EXTERNAL_SYSTEMS.md
- docs/reference/architecture.md
- docs/reference/fabrik-cli-reference.md
- docs/reference/health-monitoring.md
- docs/reference/modules/deployment-orchestrator.md
- docs/reference/modules/drivers.md
- docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md
- agents-fabrik.md
- README.md
- scripts/enforcement/check_health.py
- scripts/health_check_autonomous.py
- scripts/migrate_db_rename.py
- scripts/proof_run.py
- scripts/snapshot_vps_state.py
- scripts/update_vps_docs.py
- scripts/vps_sync.py
- src/fabrik/cli.py
- src/fabrik/config.py
- src/fabrik/deploy.py
- src/fabrik/drivers/__init__.py
- src/fabrik/drivers/compose_updater.py
- src/fabrik/drivers/coolify.py
- src/fabrik/drivers/postgres.py
- src/fabrik/health_app.py
- src/fabrik/orchestrator/__init__.py
- src/fabrik/orchestrator/context.py
- src/fabrik/orchestrator/coolify_alias.py
- src/fabrik/orchestrator/deployer_coolify.py
- src/fabrik/orchestrator/deployer_ssh.py
- src/fabrik/orchestrator/rollback.py
- src/fabrik/portability.py
- src/fabrik/registry.py
- src/fabrik/state.py
- tests/drivers/test_compose_updater.py
- tests/drivers/test_coolify.py
- tests/orchestrator/test_deployer.py
- tests/orchestrator/test_deployer_probe.py
- tests/orchestrator/test_e2e_rollback.py
- tests/orchestrator/test_infrastructure.py
- tests/orchestrator/test_refresh_infrastructure.py
- tests/orchestrator/test_rollback.py
- tests/test_cli_apply_flags.py
- tests/test_cli_status_live.py
- tests/test_coolify_alias.py
- tests/test_health_app.py
- tests/test_portability.py
- tests/test_projects_sync.py
- tests/test_reconcile_all_deployed_set.py
- tests/test_sync_has_user_guide.py

## Evidence

Grounded 2026-10-14 at 5fd9a6711 by four native seats (three Sonnet units + one Opus authoritative, stamped `dispatch --seats 4`) and the orchestrator's own reads. Every anchor the spec cites was re-read; none moved.

- **T01** — `src/fabrik/orchestrator/deployer_ssh.py:122-148` (`_target_vps_env`: `target = getattr(ctx, "target_vps", None) or "vps1"`; `if target == "vps1": yield; return`), `:273-291` (`find_existing`), `:667-670` (`_deploy_local`'s two input shapes). The driver: `src/fabrik/drivers/ssh.py:69` `ssh(cmd: str, timeout: int = 60, dry_run: bool = False) -> str`. `src/fabrik/orchestrator/exceptions.py:22` `class ProvisioningError(DeploymentError)`.

```text
$ git grep -n "def app_dir\|def probe_app\|def _host_env\|def list_compose_projects" -- src/fabrik/orchestrator/deployer_ssh.py
(no output — all four are new)
$ .venv/bin/python -c "import yaml,glob;print(sum(1 for p in glob.glob('specs/services/*.yaml') if (yaml.safe_load(open(p)) or {}).get('name')))"
0
```

- **T02** — `src/fabrik/cli.py:723-784` (`status`; the Coolify block `:752-782`, the lazy import `:755`); `tests/test_cli.py` holds one unrelated test; no test invokes `status` through `CliRunner` today (`grep -rn "\"status\"" tests/*.py` → 0 relevant hits).
- **T03** — `src/fabrik/cli.py:1535-1615` (`reconcile_all`: options `:1536-1537`; `No specs found` `:1556-1558`; the Coolify query `:1560-1565`; `summary` `:1568`; `load_spec` `:1573`, `spec-error` `:1575`, the filter `:1577`; the `fabrik-` guard `:1581-1582`; rows `:1584`, `:1590`, `:1595`, `:1597`; the table `:1599-1606`; reminders `:1610-1613`; the function falls off the end — exit 0 whatever the rows); `src/fabrik/orchestrator/__init__.py:435-439` (signature without `target_vps`), `:473` (`ctx = DeploymentContext(spec_path=spec_path, dry_run=dry_run)` — nothing sets `target_vps`), `:483` (`spec_name = spec.get("name") or spec.get("id")`), `:491-499`, `:544`; `src/fabrik/orchestrator/context.py:57` (`target_vps: str = "vps1"`); `tests/orchestrator/test_refresh_infrastructure.py:38` (the fixture dict has no `source`, no `target_vps`), `:53`, `:68`, `:79`, `:88`, `:103` (the five `find_existing` stubs), `:81` (`match="No compose app found"`).

```text
$ sed -n 491,499p src/fabrik/orchestrator/__init__.py
        existing = self.deployer.find_existing(spec_name)
        if not existing:
            existing = self.deployer.find_existing(f"fabrik-{spec_name}")
        if not existing:
            raise ProvisioningError(
                f"No compose app found at /opt/{spec_name}/ or /opt/fabrik-{spec_name}/",
                resource_type="infrastructure",
            )
        ctx.app_name = existing["name"]  # stores app name, not UUID
```

- **T04** — `src/fabrik/cli.py:1616-1665` (`projects`: `ProjectRegistry()` at `:1623` BEFORE the sync block `:1625-1648`; `registry.update(... coolify_uuid=..., coolify_name=...)` `:1636-1643`); `src/fabrik/registry.py:23-24`, `:31-34`, `:49-50`, `:63-69`, `:124` (`update(self, name, **kwargs)`); `ProjectRegistry` is named by 0 tests (`grep -rn ProjectRegistry tests/*.py` → exit 1); `tests/test_sync_has_user_guide.py` has 5 tests.
- **T05** — `src/fabrik/cli.py:398-417`, `:445-449`, `:458-466`, `:510-514`, `:517-559` (the `if not legacy:` block, every branch exits), `:560-705` (`deploy_to_coolify` import `:679`); `src/fabrik/deploy.py` = 63 lines; no test exercises the four flags through `CliRunner`.
- **T06** — `src/fabrik/portability.py:16-19`, `:34-35`, `:226-254`, `:412-453`, `:493`, `:506`, `:524`, `:539`, `:558-559`, `:588`, `:655-660`; `src/fabrik/cli.py:2883-2889`, `:2963-2983` (prints `manifest`, `sections`, `secrets_to_repopulate`, `actions` — nothing else); `tests/test_portability.py:310`, `:359`, `:384`, `:403`, `:428`, `:440`, `:466`, `:372-374`, `:398-407`, docstrings `:16-17`, `:523-526`; 26 tests.
- **T07a** — `src/fabrik/orchestrator/rollback.py:20-43`, `:129-132`, `:142-145`, `:170-183`, `:267-270`; `tests/orchestrator/test_rollback.py:13-28`, `:42-56`, `:58-78`, `:80-103`, `:349-410` (22 tests); `tests/orchestrator/test_e2e_rollback.py:164-166`, `:257`, `:395`, `:450` (3 tests); `tests/orchestrator/test_infrastructure.py:366`, `:476`, `:665`, `:717-727` (41 tests; `git grep -n CoolifyClient src/fabrik/orchestrator/infrastructure.py` → 0 — the patches are vestigial); `src/fabrik/drivers/postgres.py:1835`.
- **T07b** — `src/fabrik/health_app.py:17`, `:55-67`, `:84-93` (`checks = {"coolify": coolify_status, "dns": dns_status}`); `compose.yaml:13-16` (four `COOLIFY_*` lines, two `:?`-required); `src/fabrik/state.py:26-27`, `:53`, `:145-157` (`save()`'s kwargs keep the names), `:165-168`; `src/fabrik/orchestrator/context.py:15`, `:45-49`; `src/fabrik/config.py:104-109`; `.env.example:14-28`, `:305-312`; `tests/test_health_app.py` (2), `tests/test_state.py` (21), `tests/test_sync_projects_state.py` (10).
- **T08** — `scripts/snapshot_vps_state.py:36-56`, `:131`, `:153-156`; `scripts/update_vps_docs.py:6`, `:153-163`, `:256-271`, `:273-286`, `:372`, `:376`, `:391`, `:399`, `:410`, `:412`; `scripts/vps_sync.py:5`, `:395`, `:409-422`, `:455-487`, `:512`, `:736`, `:759`; `scripts/proof_run.py:12`, `:65`, `:198-202`, `:234-257`, `:333-356`, `:419-423`, `:504-518`, `:584-654`, `:700`, `:738-764`, `:814-821`; `tests/test_update_vps_docs.py` (5 tests, `grep -c coolify` → 0).
- **T09** — the importer graph, executed by the Opus seat: `drivers/coolify.py` has three EAGER importers (`drivers/__init__.py:12`, `compose_updater.py:72`, `health_app.py:17`) and lazy ones in `deployer_coolify.py:43`, `rollback.py:40`, `portability.py:236`, `cli.py:755`/`:1549`/`:1631`, the four scripts, the two dead scripts (top-level), `tests/drivers/test_coolify.py:10` and the seven patch targets; `compose_updater` ← only its test (`:38`); `deployer_coolify` ← only `test_deployer.py:10`; `coolify_alias` ← only `test_coolify_alias.py:14`; `deploy.py` ← only `cli.py:679`. `scripts/enforcement/check_health.py:28-29`.

```text
$ git grep -l -e drivers.coolify -e CoolifyClient -e deployer_coolify -e compose_updater -e coolify_alias -e deploy_to_coolify -- src scripts tests templates ':!*/.archive/*' | wc -l
26        (7 scripts, 11 src, 8 tests, 0 templates)
$ git ls-files -- '*.py' | grep -vc '/.archive/'
981
$ .venv/bin/python -m vulture src/fabrik --min-confidence 80
src/fabrik/drivers/coolify.py:705: unused variable 'is_secret' (100% confidence)
(exit 3 — one item; the post-deletion baseline is 0)
$ .venv/bin/python -m vulture --version
vulture 2.14
```

- **T10a, T10b** — every § Documentation landing sites anchor re-read: all still carry the wording the spec describes, except `INDEX.md:1711` (the Coolify row is `:1712`); `INDEX.md:1981`/`:1984` (the `coolify_alias.py` rows) and `docs/reference/health-monitoring.md:282-286` are uncited by the spec and owned here. `scripts/enforcement/check_retired_terms.py:21` bans `Kilo CLI|Windsurf Cascade|Coolify|Supabase` over `git ls-files docs/**/*.md docs/*.md README.md` only, WARN-only (`return 0` unconditionally).

```text
$ git grep -n -i coolify -- docs README.md INDEX.md agents-fabrik.md CLAUDE.md | wc -l
2982      (archives/plans/reviews/specs ≈ 2,278; live docs ≈ 625; docs/infrastructure non-archive 79 → W-53f8a3f3)
$ grep -n "health_check_autonomous\|migrate_db_rename" docs/CAPABILITIES.md
214:... health_check_autonomous.py ...
233:... migrate_db_rename.py ...
$ grep -n "health_check_autonomous\|migrate_db_rename" INDEX.md
(no output)
```

- **T11** — `docs/CAPABILITIES.md` 83,315 bytes and `docs/reference/apis/EXTERNAL_SYSTEMS.md` 537,674 bytes (`wc -c`), each over `READ_BUDGET_BYTES = 262144` (`scripts/enforcement/check_plan_tickets.py:102`); `scripts/generate_capability_index.py:613` `def main(root: Path = REPO, out_dir: Path | None = None) -> int`.
- **R1** — not run at plan time (no seat sshes; the orchestrator runs it before T03's dispatch and pastes the output here).

## Self-audit

- Grounding passes: four seats (U1 rebase surface, U2 retirement surface, U3 scripts + docs, U4 Opus authoritative on the reconcile-all seam and the deletion order) over the spec's 157 citations at 5fd9a6711 — 0 moved anchors; 8 spec gaps surfaced and dispositioned (I9–I18); 3 doc anchors corrected (I8).
- (a) Coverage — every "What we already agreed" line names its ticket above; every spec D-row has a ticket (D1 T05 · D2 T01/T02 · D3 T01/T03 · D4 T04 · D5 T07b · D6 T06 · D7 T07a · D8 T07a/T09 · D9 T07b · D10 T10a/T10b/T11 · D11 T08/T09); every V-row has a Behavior Contract row (I7). No gap found.
- (b) Cross-ticket signature consistency — `app_dir(spec) -> list[str]`, `_host_env(host)`, `probe_app(path) -> {"exists","ps","error"}`, `list_compose_projects(host)`, `_parse_compose_ps(text)` are spelled identically in T01's Produces and in T02, T03, T08's Behavior rows; `refresh_infrastructure(..., target_vps: str | None = None)` in T03 and § Interfaces; `plan["ignored_legacy"]` and the printer line `ignored legacy members (coolify/*): <n>` in T06 and the spec; `ctx.app_name` = matched basename in T01, T03 and the spec D3.
- (c) Deletion order — T09's Depends (T06, T07a, T07b, T08) cover every importer named in § Evidence T09; `deploy.py` leaves with T05 (its only importer `cli.py:679` goes in the same ticket).
- (d) Budget — every non-Integration ticket's Touches + Context Files were sized (`wc -c`): the largest, T03 (145,051 + 30,727 + 4,116 + 64,113 + the T01 ticket), stays under 262,144; the two over-budget docs are T11's by the hatch.
- Fixed point: not yet — `/fabrik-plan-review` grades this DRAFT; the emit gate `check_plan_tickets --plan-dir` ran clean before the commit (its summary line is in the commit message).

## Coverage Checklist

Armed 2026-10-14 by running `python3 scripts/review_rubric.py --changed src/fabrik/cli.py src/fabrik/orchestrator/deployer_ssh.py src/fabrik/orchestrator/__init__.py src/fabrik/health_app.py src/fabrik/portability.py src/fabrik/orchestrator/rollback.py scripts/proof_run.py docs/DEPLOYMENT_ARCHITECTURE.md` from the worktree root: 3 FLOOR packs + the 12-Factor block + 6 MATCHED packs, plus the four standing recurrence classes. Every row is graded by `/fabrik-plan-review` at the CONVERGED flip.

| Class | Source | State |
|---|---|---|
| security-auth floor (no secret in code; `.env.example` placeholders removed, nothing added) | `core/35-security-auth.md` | ⬜ |
| data-postgres floor (no DB call changes; `postgres.py:1835` docstring only) | `core/25-data-postgres.md` | ⬜ |
| ops floor (`compose.yaml` keeps its memory limit; no host ports) | `core/30-ops.md` | ⬜ |
| 12-Factor (XI stdout-only logging in `health_app.py`; no grouped env sets) | rubric 12-FACTOR block | ⬜ |
| agentic (native seats, dispatch stamped) | `ai/50-agentic.md` | ⬜ |
| python (exception capture in `probe_app`/`reconcile-all`; `.venv/bin/python`) | `core/10-python.md` | ⬜ |
| documentation (Doc Sync rows: CHANGELOG, INDEX, CONFIGURATION, FEATURES) | `core/40-documentation.md` | ⬜ |
| observability (shallow `/health`, stdout logs) | `core/55-observability.md` | ⬜ |
| resilience (the 60 s `ls` timeout; a probe failure is a row) | `core/58-resilience.md` | ⬜ |
| self-healing (no invented response; `/health` 200/503 rule kept) | `core/self-healing.md` | ⬜ |
| standing: citation drift (every `path:line` lands at the reviewed tip) | review coverage | ⬜ |
| standing: roll-up mismatch (spine rows == ticket rows) | review coverage | ⬜ |
| standing: never-route / governance-file placement (T09 never-route; seven governance files out of Touches) | review coverage | ⬜ |
| standing: unexecuted claim (every Evidence block pasted from a run) | review coverage | ⬜ |

```text
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

### ai/50-agentic.md  (hit: src/fabrik/orchestrator/__init__.py, src/fabrik/orchestrator/deployer_ssh.py, src/fabrik/orchestrator/rollback.py)
- is never the only thing between the agent and an irreversible act.
- **Auth boundary.** Agents run on the subscription's OAuth through the unmodified CLI, never `ANTHROPIC_API_KEY` (ai/00). Never pass `bare=True` on that lane: bare mode never reads OAuth credentials and fails with "Not logged in". A deployed service declares `shape.uses_claude_cli` and mounts the rotated `~/.claude`, never a static token. Anthropic's terms say subscription OAuth is for ordinary, individual use of Claude Code and its own apps; developers building products or services, including with the Agent SDK, should use an API key, and Anthropic does not permit routing requests through Free, Pro or Max credentials on behalf of their users, reserving the right to enforce that without notice. The operator's own development and automation through the unmodified CLI is the closest fit to that … (wrapped further — read the pack)
- output, and some models never return them. Pick the rate per model from the bake-off browser (hub-only), using its tools chip.

### core/10-python.md  (hit: scripts/proof_run.py, src/fabrik/cli.py, src/fabrik/health_app.py)
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

### core/40-documentation.md  (hit: docs/DEPLOYMENT_ARCHITECTURE.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/55-observability.md  (hit: src/fabrik/health_app.py)
- ⚠️ **The shipper is Promtail today and Promtail reached END OF LIFE (2026-03-02)** — no updates, no support. Grafana Alloy is the successor (`alloy convert` migrates the config). Fleet migration is an infra action, not a per-project one; until it lands, nothing about the rules below changes.
- **The label set is the PIPELINE's, not yours** — live: `container_name`, `filename`, `host`, `job`, `service_name`, `stream`. An app cannot add labels by logging a field; a JSON field is queried with `| json`, never as a label.
- > *"A twelve-factor app never concerns itself with routing or storage of its output stream. It should not attempt to write to or manage logfiles."*
**Mandate.** The app writes structured events, unbuffered, to `stdout` and **nothing else**. The app MUST NEVER write, rotate, append to, truncate, compress, age out, or otherwise manage a logfile, and MUST NEVER decide where logs are stored, how long they are kept, or how they are routed. Routing, rotation, retention, and storage are exclusively the **execution environment's** concern.
**BANNED in app code:**
- The scaffolded logger (structlog / pino — see § Pre-Scaffolded Logging) writes to stdout. Do not add a second handler, sink, or transport alongside the stdout one.
- ❌ **BANNED — in-app file logging:**
- > **⚠️ THE SERVER'S OWN LOGGERS ARE NOT YOURS — and they leak plain text by default.**
**Chrome extension frontend:** Use `chrome.storage.local` buffer pattern per the Chrome Extension Telemetry section below. Do not use pino directly in service workers.
- Every `python-api` and `node-api` scaffold emits a pre-configured `/metrics` endpoint. DO NOT create custom metrics modules. **A VENDORED module (fabrik-lib copies) never constructs its own `Counter`/`Histogram` either:** the scaffold serves `/metrics` from a PRIVATE `CollectorRegistry` (`scaffold.py::metrics_app`), so a module-made metric on the global default registry is invisible on most `/metrics` surfaces and the module cannot know which registry its host scrapes. A module exposes an injectable callback (`on_<event>: Callable | None`) and a structured log-once; the HOST wires the callback to the registry it owns in one line. Precedent: fabrik-lib `async-http-client` (01M1GVYN, 01M1GY91).
- Name metrics with `snake_case` and a **base-unit** suffix (`_seconds`, `_bytes`); `_total` is the COUNTER suffix and composes with units (`process_cpu_seconds_total`). ⚠️ `prometheus_client` appends `_total` to a Counter itself — declare `Counter("requests", …)`, never `Counter("requests_total", …)`, and never `_count` (an OpenMetrics reserved suffix).
- ⚠️ **Know which failure YOUR stack gives you — they are not the same.** Under an OTel SDK, a metric that overflows its cardinality limit fails SILENTLY: totals stay correct while queries that *filter or group by* an attribute UNDERCOUNT, so dashboards and SLOs keep rendering numbers that are quietly too low. **Our scaffolded stack is `prometheus_client`, which has no such limit** — here a blowup is memory/TSDB growth, and Prometheus's own `sample_limit` fails the whole scrape LOUDLY (`up=0`) rather than skewing a breakdown. Loud is survivable; the reason to care about both is that a service moving to OTel inherits the silent one.
- is named, never dropped because someone remembered to remove it — and `_keep()` additionally enforces LEAF SHAPE: an allowlisted key holding an unexpected container is nulled. That last rule is what closes a channel nobody enumerated, which is the whole reason this is a shape rather than a list.
- `include_local_variables=False`, `max_request_body_size="never"`, `include_source_context=False`, `max_breadcrumbs=0`, and the fleet logging default `LoggingIntegration(event_level=logging.ERROR, level=None)` (D-126).
- ⚠️ **That last one is COUPLED to the allowlist and the two must move together.** The upstream reference uses `event_level=None`, which closes the log channel by never creating an event. The fleet keeps ERROR records as events — we want them in GlitchTip — so the channel is open, and what NARROWS it (it does not close it) is `_ALLOWED_LOGENTRY_KEYS == {"message"}`: the message TEMPLATE survives, `params` and `formatted` (the interpolated text) do not. Verified: `logger.error("otp=%s", secret)` yields one event with `logentry == {'message': 'otp=%s'}` and no secret. That holds for DEFERRED interpolation only: an eagerly built message (an f-string, `.format`, `+` or `%` inside the call) IS the template and ships its … (wrapped further — read the pack)
- Every `sentry_sdk.init` / `Sentry.init` in the fleet MUST still set both:
| `max_request_body_size="never"` | **n/a — see below** | the request BODY, attached irrespective of `send_default_pii` (that flag gates COOKIES). Every auth, payments-webhook and token-exchange route is exposed the moment it logs an error while handling its request. **PYTHON ONLY** |
- ⚠️ **The two SDKs are NOT symmetric.** `maxRequestBodySize` is a PYTHON option name; `@sentry/node` has no such init key, so a project that dutifully added it got a silently-ignored unknown key — a line that reads like a fix and does nothing. In `@sentry/node` the body channel is already closed by `sendDefaultPii: false`, which makes the SDK report body **size only, never content**. If a project wants it structural regardless of PII, the real control is `httpIntegration({ maxIncomingRequestBodySize: 'none' })` — note `'none'`, not `'never'`. `includeLocalVariables: false` IS correct and needed for Node (locals default ON for Node runtimes).
**Never port an option name across SDKs by symmetry; check that SDK's own docs.**
- `api_key`/`token`/`secret` BY KEY. ⚠️ **This section used to conclude "so the HTTP-header channel is closed out of the box". That was wrong and is corrected here.** The scrubber matches a FIXED list of NAMES — 37 in sentry-sdk 2.68.1 (`DEFAULT_DENYLIST` 33 + `DEFAULT_PII_DENYLIST` 4), of which about a dozen are header-shaped (`authorization`, `cookie`, `token`, `api_key`, `secret`, `x_csrftoken`, …) — so a header the fleet invents sails straight through it. Measured, not assumed: `X-Signing-Secret` matches nothing in that list. Sentry maintaining the list does not help when the name is ours. The header channel is closed by the vendored scrubber's header ALLOWLIST, not by the SDK: unknown header names are … (wrapped further — read the pack)
- message, or a span name is the residual, and it ships. Never interpolate a secret into either. That is the honest boundary — not "only free-text remains after two flags", which was the claim that left four channels open.
**Verify on the CAPTURED EVENT, never the init kwarg.** Swap the SDK transport in a test, make a real dependency raise, and assert on what the event actually contains — asserting the kwarg was passed proves you configured it, not that nothing leaks. The hub's own guard is the pattern to copy: `tests/test_scaffold_glitchtip_security.py` swaps `capture_envelope`, raises inside a real request with six secrets in play, and substring-searches everything the transport would ship — never a field list — asserting the TRANSACTION event as well as the error, since `before_send` never sees it.
- ⚠️ **A project scaffolded before 2026-09-05 has the OLD init — the two flags at best, and the four channels above open.** Nothing back-fills it. Vendor `templates/scaffold/python/glitchtip_init.py` from the hub over your own `src/{package}/glitchtip_init.py`, keeping your `{pkg}` import line and your service name, then prove it with the captured-event guard rather than by reading the diff.
- This is intentional: services without DSN configured never pay for SDK runtime cost
- ⚠️ **Outside that set nothing captures it.** A deliberate 401/403/429 you WANT audited reaches GlitchTip never — widen `failed_request_status_codes` in the init rather than sprinkling `capture_exception` through handlers.
- For `chrome-extension`: use `@sentry/browser` in the popup/options/side-panel (trusted extension pages). **In content scripts, never call the global `Sentry.init`** — a content script shares the host page's `window`, so global-state integrations hijack host-page errors. Build an isolated `BrowserClient` + `Scope` (drop `GlobalHandlers` / `Breadcrumbs`) and wrap with `makeBrowserOfflineTransport` (IndexedDB buffer/flush). Service workers use the `chrome.storage.local` buffer pattern (see Chrome Extension Telemetry below).
- **Caught-and-handled** exceptions: log with stack traces via `exc_info=True` in Python (dedicated JSON attribute, never raw multi-line text). **Unhandled** exceptions (FastAPI 500s, uncaught throws): do NOT log tracebacks — GlitchTip auto-captures them. Log a short event name + `correlation_id` only. See § Error Reporting above.
- In FastAPI: use `contextvars` + ASGI middleware to bind the ID to `structlog` context. Never use `threading.local()` in async code.
- ⚠️ **Why this fleet stops at a correlation ID, and what to name the field.** Probed across ALL THREE fleet hosts (vps1/vps2/vps3): Loki + Prometheus + Grafana only — **no DEDICATED trace backend (Tempo/Jaeger) and no OTel collector on any of them**, and Grafana carries exactly two datasources (loki, prometheus). ⚠️ Not "no spans at all": Sentry-SDK services already emit performance transactions to GlitchTip at `GLITCHTIP_TRACES_SAMPLE_RATE` (§ config above) — that is the only span-shaped signal here, and it is not a queryable trace store. So do NOT instrument distributed tracing here: spans with nowhere to go are cost without a consumer, and "add OpenTelemetry" is over-engineering until a backend exists. A request-scoped correlation ID … (wrapped further — read the pack)
- Never rely on downstream log processors (Promtail, Logstash) for redaction — unredacted data may persist in transport buffers.
- **Never** use high-cardinality values as Loki stream labels. `request_id`, `user_id`, `session_id`, `client_ip` must remain inside the JSON payload only.
- ⚠️ **The label set is the PIPELINE's — an app cannot create one by logging a field.** See § Loki above for the LIVE set; `service`, `environment` and `level` are *not* labels on this fleet, they are JSON fields queried with `| json`.
- `/health` is Authelia-bypassed on all services. The bypass is **resource-based, not domain-bound** — `/health`, `/healthz`, `/metrics`, `/api/health` are bypassed on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file`). Never protect these paths.
- Never use UUID or timestamp-suffixed container names in Gatus configs or inter-service URLs — they drift per redeploy.
- MV3 service workers are ephemeral (terminated after ~30s idle). Do not hold logs in memory waiting for a batch window.
- Do not propose OTel instrumentation for a fleet service without new evidence. Measured against this stack: OTel **logs** remain the weakest-maturity signal in both Python and JS — exactly the one Loki already serves well — and adoption would mean a stateful Collector on memory-constrained VPSes plus re-instrumenting every project to gain distributed tracing nobody has asked for. The logs + metrics + errors triad stays.
- GlitchTip DSN comes from `GLITCHTIP_DSN` env var injected by the orchestrator from the GlitchTip registrar — do NOT hardcode the DSN in the repo.

### core/58-resilience.md  (hit: src/fabrik/health_app.py)
- indexed here, never restated; "can actually suffer" is decided by § Per-Scaffold Applicability above. An N/A with a reason is a complete answer, a silent gap is not.
- ⚠️ **Rows 9 and 22 make "autorecovery" honest.** Everything else recovers a *call*; row 9 recovers the
- **`httpx.AsyncClient`** is the only HTTP client for async FastAPI. Never use `requests` (sync, blocks the event loop).
**`wait_random_exponential` / `wait_exponential_jitter`, never bare `wait_exponential`**. Not a style preference: tenacity's own docstring says `wait_exponential`'s intervals "are fixed (i.e. there is no jitter) … *not* suitable for resolving contention between multiple processes for a shared resource". N workers that fail together retry in lockstep and re-hammer the dependency exactly as it recovers — the thundering herd. Every worker fleet here is that "multiple processes" case.
- 400/401/403/404/422 — a permanent client error retried is just load. ⚠️ **`429` and `408` are the exceptions and they matter most**: `429` is the commonest retryable response from a rate-limited vendor and `408` is transient by definition, so a flat "never retry 4xx" makes an agent give up on precisely the failure backoff exists for.
- curve does. ⚠️ **Two legal formats**: delay-seconds (`120`) *or* an HTTP-date (`Wed, 21 Oct 2026 07:28:00 GMT`). Parse both, **clamp both ends** (a hostile `86400` must not park a worker for a day; a hostile `-1` must not raise out of your retry machinery), and fall back to jittered backoff when absent or unparseable. `tenacity.wait_exception` exposes the response for this.
- **⚠️ Inline retry vs PAUSE — and `429` is where they meet.** An inline retry handles a **blip**; a pause handles a **condition**, where every job will hit the same wall and retrying inline just multiplies load across the queue. The test is not the status code but **whether the next job would fail for the same reason**: a single `429` with a short `Retry-After` → honour it inline; repeated `429`s, or a `Retry-After` beyond your inline budget → `set_pause(key, ttl)` so one worker's discovery spares the whole queue. ⚠️ **Clamp that TTL too** (§7a): the inline cap stops a hostile `86400` parking ONE worker for a day; the same unvalidated value in a pause key parks the ENTIRE … (wrapped further — read the pack)
- **⚠️ Retry at ONE layer.** Retries compose multiplicatively: tenacity ×3 in a job, a queue retry ×3 around it, your caller ×3 = up to **27** upstream calls per logical operation, long before a breaker sees a pattern. Pick the owning layer; make the inner ones fail fast. For worker jobs the queue retry IS the retry — do not also wrap the call in `@retry`.
- **⚠️ Retrying a non-idempotent write can double-charge, double-send or double-create.** A `POST` (or non-idempotent `PATCH`) needs an `Idempotency-Key` before it gets a retry — otherwise retrying after a timeout you never saw the response to is a second real mutation. `PUT`/`DELETE` are idempotent by HTTP semantics. `15-api-contracts` owns the SERVING side; this pack owns the caller's question —
- **Graceful fallback** — cached data, a default, or a clear error. Never let an external failure crash your endpoint. ⚠️ That includes the *parse*: a `200` with malformed JSON raises `JSONDecodeError`, which is not an `httpx.HTTPError` and will sail straight past the `except` above.
- Clients call a **self-hosted FastAPI backend** (Pattern A — `fabrik-lib/fastapi-user-auth`), never a database-as-a-service SDK directly. Browser `fetch` / mobile HTTP clients have no built-in timeout or retry — wire them explicitly:
- **Backend outage fallback:** cached data (MMKV on mobile, localStorage on web) or a clear error state — never a blank screen or crash.
- **Auth token refresh:** the app's auth client owns the refresh flow (`35-security-auth.md` Pattern A). Never scatter ad-hoc refresh logic across service calls.
| **`open` returns the fallback IMMEDIATELY**, never a queued timeout wait | you re-pay the read timeout on every call to a dead dependency |
- distributed breaker: never back it with Redis to "share" state. ⚠️ Corollary: with N workers, up to `N × failure_threshold` calls hit a dead dependency first. When that matters the fleet-wide stop is a
- **Never auto-run migrations at startup** — a one-shot deploy step (`30-ops` § Release & Admin).
- ⚠️ **The "fail readiness first, then drain" step in every Kubernetes guide does NOT apply here by default** — it lets a load balancer deregister one replica while its siblings serve, and this stack does not set `deploy.replicas` on app services (`30-ops`). Add it only with real multi-replica Traefik routing; unconditionally it buys a longer outage per deploy, not a shorter one.
- **The signal must arrive.** Shell-form `CMD` makes `/bin/sh` PID 1, which never forwards SIGTERM — exec-form, or `sh -c "exec ..."` (`30-ops`).
- stampedes the origin — a herd from your own cache, not a retry loop, so jitter and backoff never touch it. Coalesce behind a single-flight lock, or refresh before expiry.
| **Backblaze B2** (S3 API, `boto3`) | 30s connect / 120s read | return an error; never block a request on an upload |
- B2 uploads go async via the job queue, never inline in a handler. **boto3 is sync** — keep it in the worker or a thread executor, never inside an `async def` route.
- B2 downloads use server-side presigned URLs (generation is local, no I/O — safe in async). Never proxy file bytes through FastAPI.
- ⚠️ **Never point `HEALTHCHECK` at the dependency-checking endpoint** — one `postgres-main` blip would flip every container on the fleet to `unhealthy` at once. A DB blip degrades readiness; it must never mark the container unhealthy.
- Both endpoints are Authelia-bypassed on all services. Never protect them.
- ⚠️ **Docker does NOT restart an unhealthy container.** `restart: unless-stopped` acts on process EXIT only; health status feeds `up --wait`, `depends_on: service_healthy` and Traefik routing — never a restart. A process that is **wedged but alive** is recovered by nothing in compose: that is the watchdog's Tier A `restart_container` (`60-watchdog`), and it is why the watchdog exists. Never design as if the daemon will do it.
- see pause state without it firing Gatus alerts. ⚠️ That deliberate green is exactly why a long pause must escalate on its own (§ The Four Properties, property 2).
- 1. **Detection is proactive AND reactive.** Beat tasks poll vendor balance APIs *before* workers fail; error classifiers map exceptions to pause keys on the way through. Never one without the other for a critical dependency.
- ⚠️ **So a pause carries its FIRST-set time and escalates exactly once past N× its TTL** (`self-healing` row 4). ⚠️ **`fabrik-lib/alerting/` does NOT give you that property, and the provider-death row 3 of § Provider-death resilience points here rather than repeating it** — NOT the coverage map's row 3, which is the circuit-breaker row. Read at `/opt/fabrik-lib/alerting/__init__.py`, its dedup is a module-level `_last_sent` dict, so it is per-process — and a forked child INHERITS the parent's, rather than starting clean. Four things it is not. (1) Not a latch: the window is `ALERT_MIN_INTERVAL` … (wrapped further — read the pack)
- boot). Sliding TTL: every detection event calls `set_pause(...)` with a fresh TTL — never `setnx`, never permanent. Scope (§2c of the project's RESILIENCE.md):
- your dependencies, never inline at a call site.
- The classifier maps transient signals → pause. Its mirror-image rule is just as load-bearing: **an operational failure must never be written as a terminal *content* verdict.** Model the outcome on two axes — **(transport outcome) × (content evidence)** — and record a content terminal (`deleted`, `private`, `unavailable`…) only on **positive content evidence**. Everything else is transient.
| 1 | **No single point of death** — one model or endpoint dying must not stop the loop | **Declare** the mechanism in §2b. Outage-aware routing is step 1 of OpenRouter's default strategy and a `models` array falls back on **any** error. ⚠️ **The trap: setting `sort` or `order` DISABLES load balancing, and the outage step is *part of* it** — pinning silently opts you out of the protection you think you have (claims row `openrouter-pin-disables-failover`); if you pin, you owe the `models` array explicitly | **Build it**: probe the quality-ordered candidates **once at run start** (never per item) and rebuild the chain from live survivors, best first, so it self-restores on recovery. Base it on `fabrik-lib/health-probe/`; the chain-rebuild helper is `health_probe.live_chain()` (fabrik-lib `health-probe/`, vendored to projects as `libs/health_probe/` by the governance sync). Needs **intra-provider** (2+ models of one provider) AND **cross-provider** diversity |
| 3 | **Absence of progress is alarmed** — N minutes of zero progress fires ONE alert, cleared on recovery | No gateway provides this. Export a monotonically-increasing **progress** counter (rows done, items classified) and alert on *it*, not on error codes. Threshold ≥ 2 full loop runs, a §7a knob. ⚠️ The exactly-one half is YOURS to build — `fabrik-lib/alerting/` does not provide it; see the pause-escalation bullet under § Advanced: Autonomous Pause-State Pipeline → The Four Properties for what it actually does and why — this file's own section, not `RESILIENCE.md` §7 | Same |
| Worker clears `dispatched:<id>` flag when paused | Worker MUST keep the flag on pause-skip (queue bloat) |
| Backup that has never been restored to staging | Run §10 drill within 30 days or it doesn't exist |
| A fallback chain whose **bottom rung has never been executed** | Exercise the last resort on a schedule — an untested fallback is a silently-dead one, and the chain is a rung shorter than its author believes |
- one-shot migration step boot must never do
- [ ] Retries use **jittered** backoff (`wait_random_exponential`/`wait_exponential_jitter`, never bare `wait_exponential`) on transient errors only.
- naming only `TimeoutException`/`ConnectError` never retries a 429.
- state — never a blank screen.

### core/self-healing.md  (hit: src/fabrik/health_app.py)
- AGENT USAGE: Pick the failure class, walk the ladder top-to-bottom, stop at the first step that resolves. Never invent a step. Never skip a step. -->
- [`60-watchdog`](60-watchdog.md) — the escalation engine and the owner of its tiers. Tier A acts automatically (it registers `restart_container`, `clear_file_cache`, `scale_concurrency`, `pause_worker`); Tier B is opt-in; Tier C escalates — and carries the **approved-write lane** (`drop_queue_items`, `rotate_locks`), off by default; **Tier D** (opt-in, Telegram-gated) applies a tested code fix with auto-rollback. ⚠️ Registered is not runnable — see **What the sidecar can execute today** below.
- Each row reads left-to-right: **Symptom** (an observable signal) → **First response** (a `58-resilience` primitive or the module that implements it) → **Fallback** (another primitive or a `60-watchdog` action) → **Escalate** (operator-bound). The agent picks the row matching the active failure, walks left-to-right, and **stops at the first step that resolves**. Never skip rightward.
| 11 | **Postgres allocation registry drift** (HUB-side, not a service: a database in `pg_database` with no `allocations.json` entry) | the hourly drift cron (`scripts/audit_all_registrars.py`) finds a database no registry row claims | Additive reconcile (`src/fabrik/registry_reconcile.py`, D-500): registers it in-lock, never overwrites or deletes; `report` (writes nothing) unless the cron line sets `FABRIK_REGISTRY_RECONCILE=apply` | Refuse, never guess, and write nothing: a name two specs claim is counted as `fabrik_registry_heal_total{outcome="shared"}`; any other refusal (an incomplete claim map, an unresolved owner, an error) as `fabrik_registry_heal_failed{spec_id,db,reason}` | `FabrikRegistryHealFailed` (a `heal_failed` refusal standing 2 h; a shared claim alerts on neither) or `FabrikAuditStale` (no clean audit run in 3 h, or none recorded) — `configs/prometheus/rules/fabrik-drift.yml` |
**⚠️ Row 10 is NOT the deadman timer, and the difference is the whole point.** The Tier-C deadman below (`spec.watchdog.deadman_timeout_seconds`, 60–3600, default 300 s, rendered as `WATCHDOG_DEADMAN_TIMEOUT`) measures **operator silence** — it arms only
- **What the sidecar can execute today:** the model returns each action with its params, and `check_proposal` refuses anything off the offered menu, or with a bad or missing param, before a side effect (fabrik-lib D-412). The model's menu is `restart_container` + `escalate_apprise` until the spec lists more in `watchdog.llm_actions` (fabrik-lib D-412): `clear_file_cache` and `pause_worker` (Tier A) run once listed; `wipe_redis_cache` and `reset_db_pool` (Tier B, port defaulting to 8000) run once listed AND `auto_tier_b: true`. `scale_concurrency`, `drop_queue_items`, `rotate_locks` and `install_log_drop_rule` are never offered, and `create_fix_pr` has its own lane (`propose_fix_prs`) — this ladder names three of the never-offered ones (`scale_concurrency` and `drop_queue_items` in row 2, `rotate_locks` in row 8): in those rows the watchdog step resolves to Tier C escalate plus the deadman restart. Treat each row's first response as the step that actually heals.
- If a failure class doesn't appear in the table above, the rule is: **add the row to this pack first, then the response logic to the code.** Never silently invent a self-healing response — it'll diverge from the operator's mental model and break the ladder's discipline.
- 4. **Self-healing without a visible signal.** A pause flag, breaker, or rate-limit reject that doesn't increment a counter and emit a structured log line is invisible — when it misfires, you can't tell. Every ladder step MUST emit a counter AND a `structlog.info()` (or `pino.info()`) row carrying the resource name + reason; without that, the next operator audit has no way to tell the difference between "step fired and recovered" and "step never ran". **Tier-D steps (stabilize / remediate / apply / rollback) are held to the same bar:** each MUST emit a counter + structured log AND write the `incidents` / `approvals` / `deploys` tables — an unaudited or irreversible code-remediation is not self-healing, it's an unreviewed deploy.
- 2. **Fallback — `pause-state` (Redis-backed).** When `signups_per_ip_per_minute` for a specific IP stays high after the first defense's per-IP cap fires, the worker emits an incident; the watchdog sidecar reads the inbox and proposes Tier A `pause_worker` with `resource=signup_<ip_hash>` (the action accepts `^[a-z][a-z0-9_]{0,31}$` and a TTL of 5–3600 s, so truncate the hash to fit — and it is unreachable today, above, so until upstream carries parameters the app sets this pause itself with `pause_state.set_global_pause(...)`). Every signup-handling worker checks `pause_state.is_paused("signup_<ip_hash>")` from the vendored fabrik-lib `pause-state` (the scaffold's own `pause_state.py` has no `is_paused`), with `PAUSE_KEY_PREFIX` equal to `<project_id>:pause:`, and bails without touching the DB. Never gate other workers on `is_globally_paused()` while per-IP keys share the prefix — it reports ANY key under it, so one IP would stop them all.
- [ ] The per-project ladder does not count on a watchdog step that is never offered (`scale_concurrency`, `drop_queue_items`, `rotate_locks`): each such row's healing step is the app's own first response, and the doc says the watchdog step escalates. If the approved-write lane is wanted once it is reachable, the project `.env` sets `WATCHDOG_ALLOW_DB_WRITES=true` and the RW DSN is provisioned.

# promote-to-check_*: 135 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
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
- `expo-secure-store`
- `shape.is_admin_dashboard: true` `two_factor` `fabrik apply` `/health` `/metrics` `saas/60-saas-ui.md` `shape.has_bearer_api: true` `two_factor`
- `^/api/` `/api/*` `/api/v1` `/api/*` `shape.bearer_bypass_prefix: "^/api/v1"` `fabrik apply` `^/` `orchestrator/verifier.check_api_bypass` `/api/*` `^/api/`
- `postgres-main` `fabrik-lib/rag` `plpgsql` `CLAIMS.yaml` `fleet-postgres-main-no-pgvector` `postgres-main`
```

## Pass Ledger

| Pass | seats · axes re-checked | counters | method | plan md5 (start → end) |
|---|---|---|---|---|

## Residual unknowns

Resolved at plan time:
- Every spec anchor lands at 5fd9a6711 (157 of 157; `check_citations_resolve.py --doc`), and the four seats re-read each cited line — none moved.
- The V8 baseline: 26 files match the census today; 981 tracked `*.py` outside the archives; `vulture` baseline 1 item.
- `name == id` for 69 of 69 specs, so `app_dir`'s `name or id` keying changes no live match.
- `check_retired_terms.py` cannot fail a gate (WARN-only, docs + README only).

Still open, each with its resolution step:
- R-open-1 — R1's reading (the downed-but-present stacks `reconcile-all` would now skip; whether a container still carries `label=coolify.serviceName=meilisearch`; the Authelia configuration volume path). Resolution: the orchestrator runs R1 before T03's dispatch and pastes the output into § Evidence; T03, T06 and T08 receive it as a file.
- R-open-2 — the appetite: 780 minutes across the set against the spec's 600 for A + B + C; T08/T10a/T10b/T11 (255) are the named spill. Resolution: `/fabrik-execute-plan` passes each ticket's `Appetite:` at `step`; past 2× on any ticket, re-plan the remainder with `/fabrik-plan-after-chat`.
- R-open-3 — setting `ctx.target_vps` in `refresh_infrastructure` reaches every registrar that reads it (`infrastructure.py:870`, `:908`, `:947`, `:1004`, `:1252`, `:1286`, `:1437`; `drivers/watchdog.py:604`, `:744`, `:1102`), which is the spec's intent for a spoke spec (today `vps1` is persisted for every spec). Resolution: T03's Behavior row 5 asserts the ctx the provisioner receives; the registrars' own host rewriting under `vps2` is exercised by their existing tests, and the Finish review's slice over `orchestrator/__init__.py` names it as a hunt priority.
- R-open-4 — `docs/infrastructure/`'s 79 live generated lines stay stale until W-53f8a3f3 runs the rebased scripts against vps1 (read-only). Resolution: that item, after this plan is EXECUTED.
