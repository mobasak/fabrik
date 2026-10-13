# The Coolify-bound verbs move to the SSH + Compose model and the Coolify code leaves the tree

**Status:** CONVERGED
**Profile:** delta

Work item W-36571dff (fleet; infra-assigned 2026-10-13; it supersedes W-ef765f8d and folds W-00485146's code half).
Routed here by `/fabrik-task`'s SIZE gate (refusal LR-59996fe9: appetite 600 > 240 min, `oneway=yes`, `tradeoffs=yes`).
Research ledger: `docs/reference/research/2026-10-14-coolify-verb-retirement-ledger.md` (48 rows, every one dispositioned).
Measured against the hub at d468ed13d (worktree-fleet), read-only, no VPS touched.

## Personas

- **PRIMARY — the operator at the hub CLI**, in the item's words: *"the CLI verbs still bound to the retired Coolify
  API … are broken: retire or rebase each on the SSH+Compose deploy model."* Their loop today for the one question
  these verbs answer — *is this spec deployed and alive?* — is (1) `fabrik status specs/services/<id>.yaml`, (2) read
  `⚠️ Could not check: <connection error>`, (3) ssh to the VPS by hand, (4) `cd /opt/<id>`, (5) `docker compose ps`.
  Step budget: 5 steps; after this delta it is 1 step — the verb answers from the live host. For *re-run the registrars
  fleet-wide* the loop is (1) `fabrik reconcile-all`, (2) read `Failed to query Coolify`, exit 1, (3) `fabrik apply`
  each spec by hand: 2 + N steps, after the delta 1.
- **The hub agents (fleet, infra) in a session** — the same verbs, plus the `audit-registrars` hint at `cli.py:1477`
  (*"consider 'fabrik reconcile-all'"*) that today points at a dead verb. fleet builds this (the item is fleet's, charter
  beat: `fabrik apply`/VPS); infra merges (the merge owner); the Opus + Fable panel approves the design (D-613, D-558).
- **AUTOMATED consumers:** `scripts/generate_capability_index.py` renders `docs/CAPABILITIES.md` from the verbs' click
  docstrings (`:3`, `:588`) — a docstring delta rides a regeneration, no hand edit; `scripts/sync_projects.py` reads the
  state records' `coolify_uuid`/`coolify_app_name` keys into `data/projects.yaml` (`:264-265`) and keeps doing so (D9);
  `tests/test_state.py` (21) and `tests/test_sync_projects_state.py` (10) pin that schema. The hub's own `/health`
  (`health_app.py`, run by `Dockerfile:48`) has NO automated consumer today — no `specs/services/*.yaml` deploys the hub
  image and no `configs/` Gatus entry names it (0 of 69 specs, 0 config lines; `grep -rln health_app configs specs`).
- **The threat of silent wrongness, not a human:** `fabrik destroy` tells the operator it will remove a *"Coolify
  application"* (`cli.py:1124`) and `fabrik export` promises *"Coolify Applications/Services/Projects"* (`cli.py:2886`) —
  claims about a control plane that has not existed since 2026-05-30. Every such sentence is a persona-facing lie and is
  in scope (D10).

## Goal

No verb, module, test, env row or doc sentence in the hub binds to the Coolify API. The three verbs with a live purpose
— `fabrik status`, `fabrik reconcile-all`, `fabrik projects --sync` — answer from the SSH + Compose model
(`deployer_ssh.py`, the state records, the project scanner). The one dead path — `fabrik apply --legacy` and
`fabrik.deploy.deploy_to_coolify` — is removed. The Coolify driver, the Coolify deployer, the compose updater, the
alias-watcher write side and their 53 tests are deleted; git history is the archive. The persisted state-record keys
keep their names.

## Why this exists

Coolify was removed from vps1 on 2026-05-30 (`docs/CONFIGURATION.md:50`; `drivers/coolify.py:4`). Five months later
`fabrik status` still says *"🐳 Coolify status: ⚠️ Could not check"* for every spec (`cli.py:752-784`), `fabrik
reconcile-all` exits 1 before it reconciles anything (`cli.py:1561-1565` — the deployed set is
`CoolifyClient.list_applications()`), `fabrik projects --sync` prints *"Sync error"* and syncs nothing (`cli.py:1625-1648`),
and `fabrik apply --legacy` reaches a function that raises `NotImplementedError` (`deploy.py:18-23`). The hub's own
`/health` is permanently `503 degraded` because its `coolify` check can never pass (`health_app.py:55-67`,
`docs/reference/health-monitoring.md:101`). 2,437 lines (`wc -l` over the five modules) of driver, deployer, updater, alias writer and deploy helper and 53 tests run under every
gate, every ruff and mypy pass and every review for code that cannot execute against anything (*"code is a liability,
not an asset"*, ledger cr-12). The docs carry both stories at once: the CLI reference already describes the TARGET
behaviour of `status` and `--sync` (`docs/reference/fabrik-cli-reference.md:270`, `:354`) while `CONFIGURATION.md:52-55`
lists the same verbs as *"non-functional … Known broken"*. The chosen approach removes the binding at its root: each
verb reads the thing that is actually true now (the VPS over ssh, the state record, the scanner), and the code nobody
can run is gone, so the question *"is this verb still Coolify?"* has no object left to ask about.

## What exists today (grounded)

| # | Surface | Today | `path:line` |
|---|---|---|---|
| W1 | `fabrik status <spec>` | prints `apps/<id>` files, then lists Coolify applications to say "Found in Coolify" | `src/fabrik/cli.py:723-784` (Coolify block `:752-784`) |
| W2 | `fabrik logs` | Loki query + `--local` compose tail — NOT Coolify-bound (0 `coolify` lines in `:785-870`) | `src/fabrik/cli.py:785-870` |
| W3 | `fabrik reconcile-all` | deployed set = `CoolifyClient.list_applications()`; any error → exit 1; else per spec `orch.refresh_infrastructure` under a file lock | `src/fabrik/cli.py:1535-1615` (`:1549`, `:1561-1565`, skip `:1584`) |
| W4 | `fabrik projects --sync` | help "Sync with Coolify first"; writes `coolify_uuid`/`coolify_name`/`domain` into the registry | `src/fabrik/cli.py:1616-1665` (`:1618`, `:1625-1648`, `registry.update :1636-1643`) |
| W5 | `fabrik apply --legacy` (+ hidden no-op `--use-orchestrator`) | the pre-orchestrator pipeline: render → DNS → `deploy_to_coolify`, which raises | `src/fabrik/cli.py:402-417`, branch `:517` (`if not legacy:`) to `:692`, import `:679`; `src/fabrik/deploy.py:1-23` |
| W6 | hub `/health` | `asyncio.gather(_check_coolify_sync, _check_dns_sync)`; 503 unless both healthy | `src/fabrik/health_app.py:17`, `:55-67`, `:84-93`; `Dockerfile:46-48`; `compose.yaml:13-16` requires `COOLIFY_API_URL/TOKEN` |
| W7 | `fabrik export` | `_collect_coolify` → `coolify/{applications,services,projects}.json`, always empty since the API is gone; manifest counts it; `import` indexes the `coolify/` prefix | `src/fabrik/portability.py:226-254`, `:493`, `:506`, `:524`, `:539`, `:558-559`, `:645`, `:657`; `cli.py:2886` |
| W8 | `RollbackManager` | `coolify_client` ctor arg + lazy `CoolifyClient()`; `rt == "coolify"` → `_rollback_coolify` (`delete_application`) | `src/fabrik/orchestrator/rollback.py:20-43`, `:142-145`, `:170-183` |
| W9 | `fabrik.drivers` package | re-exports `CoolifyClient`; docstring lists "coolify: Coolify deployment API" | `src/fabrik/drivers/__init__.py:5`, `:12`, `:22` |
| W10 | `drivers/coolify.py` | 934 lines, 52 `def`s in 3 classes; its own docstring: "LEGACY … any call will fail at the network layer … New code must NOT import this" | `src/fabrik/drivers/coolify.py:1-13` |
| W11 | `orchestrator/deployer_coolify.py` | 845 lines, `ServiceDeployer`; imported only by `tests/orchestrator/test_deployer.py:10` (19 tests) | `src/fabrik/orchestrator/deployer_coolify.py:24` |
| W12 | `drivers/compose_updater.py` | 451 lines; imported by nothing but its own tests (20) and a docstring in `coolify.py:838` | `src/fabrik/drivers/compose_updater.py:72` |
| W13 | `orchestrator/coolify_alias.py` | the alias-watcher WRITE side; docstring "DECOMMISSIONED 2026-05-30 … New code paths must NOT call into this module"; callers: none (`postgres.py:1835` mentions it in a docstring); 12 tests | `src/fabrik/orchestrator/coolify_alias.py:1-7`; `tests/test_coolify_alias.py` |
| W14 | state records | `coolify_uuid` holds the compose app name (= `/opt/<name>`), `coolify_app_name` the spec name; the directory is gitignored and per-checkout (`.gitignore:120` `/.fabrik/state/`): the main checkout holds 9 records (4 real services, 5 test ids; `_destroyed/` beside them is the archive), this worktree 5; `uuid` is None or the app name — never a Coolify UUID since 2026-05-31 | `src/fabrik/state.py:26-27`, `:53`, `:150-151`, `:165-168`, `:204-205`; writer `orchestrator/__init__.py:540-541`; reader `scripts/sync_projects.py:242-246`, `:264-265` |
| W15 | `DeploymentContext.coolify_uuid` | the storage field behind the `app_name` property, kept "for state-file backward compat" | `src/fabrik/orchestrator/context.py:15`, `:45-49`, `:68-81` |
| W16 | registry | `Project.coolify_uuid`/`coolify_name` fields, written only by W4 | `src/fabrik/registry.py:23-24`, `:31-34`, `:49-50` |
| W17 | env + config | `.env.example` carries two COOLIFY blocks "as placeholders until that legacy code is removed"; `config.py` keeps the readers commented out | `.env.example:14-28`, `:305-312`; `src/fabrik/config.py:104-109` |
| W18 | the SSH model already has the primitives | `find_existing(name)`: `test -f /opt/<name>/compose.yaml` then `docker compose ps --format json`; `_target_vps_env(ctx)` swaps `FABRIK_VPS_SSH_HOST` to the spoke; the deploy path logs `compose ps --format json` after `up` | `src/fabrik/orchestrator/deployer_ssh.py:273-291`, `:123-145`, `:544`; `src/fabrik/drivers/ssh.py:59-69` (host alias read per call) |
| W19 | the fleet's Compose | 2.40.3 measured (the deployer's own comments on `--wait`, written against it) | `src/fabrik/orchestrator/deployer_ssh.py:1206`, `:1210` |
| W20 | tests pinning the importers | `test_health_app` 2 · `test_portability` 26 (9 pass `coolify_client=`) · `test_rollback` 22 (6 Coolify-specific) · `test_e2e_rollback` 3 (mock `CoolifyClient`) · `test_infrastructure` patches `fabrik.drivers.coolify.CoolifyClient` at `:366`, `:476` · `test_deployer` 19 · `test_compose_updater` 20 · `test_coolify` 2 · `test_coolify_alias` 12; **0 tests pin the three verbs' Coolify output** (`grep -rn "Found in Coolify\|Syncing with Coolify\|no Coolify app" tests/` → 0 of 11 files naming `list_applications`/`coolify_uuid`) | the files named |
| W21 | docs saying "broken" or "legacy Coolify" | `CONFIGURATION.md:50-55`, `:659-666`; `SERVICES.md:64-67`; `DEPLOYMENT_ARCHITECTURE.md:103`, `:137`, `:166-167`; `reference/architecture.md:70`, `:85`, `:184`, `:207`, `:219`, `:233`; `reference/modules/drivers.md:5-10`, `:28`, `:40`, `:62-69`, `:315`; `reference/health-monitoring.md:101`; `reference/fabrik-cli-reference.md:463`, `:466`; `operations/deployment.md:489-490`; `TROUBLESHOOTING.md:186`, `:202`; `agents-fabrik.md:102`, `:404`, `:409`; `README.md:56`, `:559`, `:704`; `INDEX.md:261`, `:1704`, `:1711`; `FEATURES.md:313`, `:686`; `docs/CAPABILITIES.md:37`, `:46` (generated) | each cited |
| W23 | hub scripts bound to the driver (found by the review's Opus slice — the 1a census had stopped at `src/fabrik`) | six LIVE scripts import `CoolifyClient`: `scripts/health_check_autonomous.py:17` (its whole purpose: Coolify health, apps, databases, services), `scripts/migrate_db_rename.py:37` (a Coolify-era one-off: "Postgres database rename for Coolify-managed apps", T1-05), `scripts/snapshot_vps_state.py:36-39` (`snapshot_coolify`, diffed at `:153-156`), `scripts/update_vps_docs.py:153-158` (`collect_coolify_apps`, rendered at `:256`, `:372`, `:399`, `:410`), `scripts/vps_sync.py:409-422` (test-named Coolify apps) and `:455-487` (Authelia rules vs Coolify fqdns), `scripts/proof_run.py:337-339` (`_delete_coolify_app_by_name`), `:603-605` (diagnostics), `:738-756` (the app lookup the worker proof reads at `:758-764`) plus its `--use-orchestrator` argv (`:12`, `:518`); callers of these scripts: none in `scripts/sysadmin/*.sh` or any crontab line (`grep -rln` over `*.sh`, `Makefile`, `*.yaml` → only `scripts/dr_env_backup.sh:96`, a comment); tests: `tests/test_update_vps_docs.py` (pins `update_vps_docs.py`); archive hits that are not live code: `scripts/.archive/2026-06-17-coolify-era-cleanup/delete_uptime_kuma.py:16`, `templates/.archive/KILO_CONSULT_WORKFLOW.md:185`, and the comment `scripts/enforcement/check_health.py:28` | `command grep -rn "drivers.coolify\|CoolifyClient\|drivers import coolify" scripts --include=*.py` → 29 lines in 8 files |
| W22 | the Coolify era in the ledger | no hub D-row records the Coolify retirement itself (`grep -ci coolify docs/DECISIONS.md` → 2 rows, both incidental: D-079, D-122) | `docs/DECISIONS.md:432`, `:475` |

`fabrik logs` (W2) is NOT in scope: the item mis-attributes it. The docs that call it a Coolify verb (`CONFIGURATION.md:53`,
`:662`; `drivers.md:10`; `coolify.py:6`) are corrected by D10, which is all the item's "logs" row needs.

## The delta

Invariants, then the per-surface deltas.

1. **A verb answers from a source that exists.** The live truth for *is it deployed / alive* is the target host's
   Compose over ssh; the hub-side truth for *what did the last apply do* is the state record; the registry truth is the
   scanner. No verb reads an HTTP control plane. **"Deployed" means: Compose knows a project with at least one container,
   running or stopped** — `compose ls -a` enumerates projects from container labels (E2, cr-37), so a stack brought
   `down`, or a directory whose first `up` never created a container, has no row even with `-a`; `status` still reports
   such a directory (its file probe sees `compose.yaml`) with zero containers, and `reconcile-all` skips it — a change
   from today's file-based `refresh_infrastructure` (`orchestrator/__init__.py:491-493` via `find_existing`'s `test -f`),
   stated here because it is the axis the judge panel ranked on (Ls · Probe · State); the plan's R1 measures how many such
   downed-but-present stacks exist (U3).
2. **A probe failure is a row, never an abort — and the exit code still tells the truth.** `reconcile-all` and `status`
   print the host's error beside the spec and continue to the next; `status` exits 0 whatever the probe says (it is a
   report; a spec that fails to load exits 1 as today, `cli.py:732-736`); `reconcile-all` exits 1 when NO host's `ls`
   succeeded (nothing could be read — today's `:1563-1565` kept that signal and it stays), and under `--yes` also when any
   row ended `host-unreachable`, `error`, `spec-error` or `lock-timeout`, so an automated caller (`agents-fabrik.md:97`,
   `:102` name the verb as the drift responder's target) never reads a dead host as "reconciled"; otherwise exit 0 — a dry
   run REPORTS its failure rows and does not fail on them; the `--filter` is applied to the file stem BEFORE the spec
   loads (the stem equals `spec.id` in 69 of 69 specs today, so the match is unchanged) (today it is applied after, `cli.py:1572-1577`, so a broken spec outside the filter would still earn a
   `spec-error` row), so a `--filter` that matches no spec names no host and exits 0 with an empty table; no spec file at
   all stays exit 1 (`cli.py:1556-1558`, unchanged); and the "no host could be read" rule applies only when at least one
   host was named — a run whose every loaded spec is `spec-error` names none, so without `--yes` it exits 0 over its
   `spec-error` rows and with `--yes` it exits 1. The cheapest way to satisfy the per-row table without reconciling anything — every host
   down — is exactly the case the exit code refuses (D-253).
3. **The Compose JSON contract is the executed one, not the docs example.** `ps --format json` is JSON Lines (one
   object per line, since v2.21.0 — cr-22); the docs example shows nine keys but the live formatter emits one key per
   exported no-argument single-return `ContainerContext` method (docker/cli's `reflect.go`, cr-46) — 20 keys at the
   fleet's 2.40.3, executed locally on 2026-10-14; compose `main` adds `Engine`, a 21st, ignored like any unknown key
   (`Command, CreatedAt,
   ExitCode, Health, ID, Image, Labels, LocalVolumes, Mounts, Name, Names, Networks, Ports, Project, Publishers,
   RunningFor, Service, Size, State, Status`; cr-46, cr-23 corrected) — so the parser reads `Name`, `Service`, `State`,
   `Health`, `ExitCode` and IGNORES every other key; `ID` is truncated to 12 characters and `Command` is an ellipsized
   string, so neither is an identifier. `State` ∈ `created|running|paused|restarting|removing|exited|dead` (cr-34);
   `Health` ∈ `healthy|unhealthy|starting`, and `""` is what Compose emits both for a container with no healthcheck AND
   for every non-running container (`containerHealthAndExitCode` sets it only while running — cr-47), so the printer
   labels `""` "no healthcheck" only on a `running` row and `—` otherwise; `"none"` (moby's constant, cr-35) is
   accepted the same way. The parser also accepts a leading `[` (the pre-2.21 array) so an older host does not break the
   verb. `ls -a --format json` is a plain array of `{Name, Status, ConfigFiles}` where `ConfigFiles` is ONE string, the
   paths joined by `,` (executed locally: `"/opt/tryton-crm/compose.yaml,/opt/tryton-crm/compose.dev.yaml"` — cr-48,
   cr-28, cr-37), split before matching; `Status` is never parsed (U2). Neither command's exit code says anything about
   health (cr-33).
4. **Delete, do not shim.** A module whose backend is gone is removed with its tests in the same change as its
   importers (cr-21); a reader who needs it runs `git log -G CoolifyClient` (cr-13, cr-20).
5. **Persisted names stay.** The on-disk state keys `coolify_uuid`/`coolify_app_name` and `DeploymentContext.coolify_uuid`
   are a persisted format with nine records in the main checkout (five in this worktree) and three readers; this delta
   corrects their DOCSTRINGS, not their names.

| D# | Surface | Delta | Touchpoints |
|---|---|---|---|
| D1 | `fabrik apply --legacy`, `deploy.py` | **RETIRE.** The `--legacy` option (`cli.py:408-417`), the hidden no-op `--use-orchestrator` (`:402-407`) and the legacy FALL-THROUGH — everything after the `if not legacy:` block, which always exits (`:517-559`): `:560-705`, including the summary only that path reaches — are removed and the block dedented; `--skip-dns`/`--skip-deploy` (`:399-400`, `:445-446`), read only on that path (`:638`, `:667`) and never passed to `orchestrator.deploy` (`:522-528`), go with it (`--dry-run` is the preview), as does the `if use_orchestrator:` notice (`:510-514`); `--yes` STAYS, as a stated no-op with the help text "accepted for compatibility; the orchestrator path never prompts" — it is read only at `:614` inside the removed path, but `scripts/proof_run.py:518` and the docs pass it, so removing it would break every documented invocation for nothing (review O2-8); `src/fabrik/deploy.py` is deleted. A stale flag gets click's own `No such option` (exit 2). MIRROR: `--use-orchestrator` has ONE caller, `scripts/proof_run.py:518` (docstring `:12`) — dropped in D11; the docs that name it are D10's. The deprecated-stub shape was evaluated and NOT taken: click's `deprecated=` prints and then RUNS the callback (cr-2), so a stub would have to raise itself (cr-6); the item names no verb that is retired outright — every verb has a live rebase — and the dead path is a set of OPTIONS, for which click's refusal is already the actionable message (cr-45). `hidden=True` on a signpost was refuted as a documented pattern (cr-42). | `src/fabrik/cli.py:398-417`, `:445-449`, `:458-466` (docstring), `:510-514`, `:517-705`; `src/fabrik/deploy.py` (delete); `scripts/proof_run.py:12`, `:518` |
| D2 | `fabrik status <spec>` | **REBASE** (judge panel, 3 of 3 seats: Ls/Delete ranked first on both axes — § Decisions taken). After the `apps/<id>` block, two sections replace the Coolify block: (a) **Last apply** from `state.load(spec.id)` — `applied_at`, `git_sha[:12]`, `target_vps`, the `registrars_applied` types, each `registrar_failures` row; "no state record — never applied from this checkout" when absent; (b) **Live containers** from a NEW `SSHDeployer.probe_app(path) -> {"exists": bool, "ps": str, "error": str \| None}`: first the WHOLE test inside one `sudo sh -c`, the `_read_env_file` pattern (`deployer_ssh.py:941-948`): `sudo sh -c <shlex.quote("[ -f " + shlex.quote(path + "/compose.yaml") + " ] && echo exists \|\| echo absent")>` — rc 0 either way and a refused sudo prints NOTHING (the bare `sudo test -f … \|\| echo absent` shape would print `absent` on a refused sudo, the trap `:941-943` documents), so a `RuntimeError` OR `subprocess.TimeoutExpired` (`drivers/ssh.py:113`, `:119`) from it means the HOST failed, never the file — then on `exists` `cd <quoted path> && sudo docker compose ps -a --format json` (`-a` so an exited container is a row, cr-25); either call's exception is captured into `error`, and so is a stdout that is neither `exists` nor `absent` (a login banner, the dry-run empty string `drivers/ssh.py:92-94`, a refused sudo) or a `ps` body that is not JSON — never a crash (review O2-13, O3-2). `find_existing` is UNTOUCHED: it returns `None` when its FIRST call raises `RuntimeError` (`deployer_ssh.py:278-281` — an absent directory and an unreachable host look the same), swallows a `RuntimeError` from the `ps` call into `status: ""` and still returns the dict (`:287-290`), lets a `TimeoutExpired` from either call propagate, is pinned by `tests/orchestrator/test_deployer_ssh.py:408-411`, is read by `_deploy_inner` `:209`/`:224`, `_deploy_local` `:690`, `_build_env` `:742`, `refresh_infrastructure` (`orchestrator/__init__.py:491-499`, reads `existing["name"]`) and `redeploy` (`cli.py:1332`), and it cannot tell an unreachable host from an absent directory (judge seat 2, review O2). The app directory comes from one module-level helper, `app_dir(spec) -> list[str]` (accepting the validator's dict and the `Spec` model alike, as `_deploy_local` does at `:668-671`), shared with D3 and `refresh_infrastructure`: it returns the CANDIDATE directories in probe order — for a local source the single entry `source.path`, normalised (no trailing slash) and RAW — quoting happens once, at the shell boundary inside `probe_app` — with NO `fabrik-` fallback, and a local path whose parent is not `/opt` raises `ProvisioningError` before any probe, because D3's basename rule reads the directory as `/opt/<basename>` (7 of 69 specs are local; `fabrik-file-worker` → `/opt/file-worker`; all seven are direct children of `/opt` today); otherwise `[/opt/<id>, /opt/fabrik-<id>]`, the fallback `refresh_infrastructure` applies today (`:490-497`) — and every caller runs `probe_app` on each entry in order until one `exists` (an `error` on any entry whose `exists` is False stops the walk, so an unreachable host is never reported as "no compose project"); `probe_app` takes a PATH, where `find_existing` takes a NAME under `/opt` (`_validate_name`, `:279`); the host is the spec's `target_vps` (default `vps1`), run inside the host swap, and when the record's `target_vps` differs both are printed (a record can carry `vps1` for any spec `refresh_infrastructure` persisted — D3). The `ps` text is parsed per invariant 3 into one row per container: `Service · State · Health · ExitCode`. Messages: "no <dir>/compose.yaml on <host>"; "⚠️ could not reach <host>: <error>"; "⚠️ could not read containers on <host>: <error>". Exit 0 in every probe outcome (invariant 2). | `src/fabrik/cli.py:752-784`; `src/fabrik/orchestrator/deployer_ssh.py` (+ `probe_app` beside `find_existing` `:273-291`, `_host_env` from `:123-145` — see D3, `_parse_compose_ps`) |
| D3 | `fabrik reconcile-all` | **REBASE.** The deployed set is read ONCE per distinct target host named by the loaded specs (`spec.target_vps`, default `vps1` — today 1 of 69 specs names `vps2`, `spoke-canary.yaml:8`, so two hosts, two calls): `list_compose_projects(host)` runs `sudo docker compose ls -a --format json` over ssh under that host's swap (60 s timeout, cached for the run) and parses the array; a spec is deployed when a project's `Name` is `spec.id` or `fabrik-<spec.id>`, OR one of its `ConfigFiles` paths (the string split on `,`) has as parent directory one of the spec's `app_dir(spec)` candidates — `source.path` for a local source, else `/opt/<id>` or `/opt/fabrik-<id>` (the fallback `refresh_infrastructure` already applies, `orchestrator/__init__.py:490-497`; the deployer runs `cd <dir> && docker compose up`, `deployer_ssh.py:540`, `:693`, so the project name defaults to the directory and no scaffold compose sets `name:` — executed: `grep -ln "^name:" templates/*/compose.yaml.j2` → 0 of 8). Rows: `reconciled`/`dry-run` as today; `skipped — no compose project (no containers) on <host>`; `host-unreachable — <error>` for every spec on a host whose `ls` raised `RuntimeError` or `TimeoutExpired` (the run continues to the other hosts; today's exit 1 at `:1563-1565` becomes invariant 2's exit rule: 1 when no host could be read (at least one named), and under `--yes` when any row is `host-unreachable`, `error`, `spec-error` or `lock-timeout`; otherwise 0). `refresh_infrastructure` sets `ctx.target_vps` from the spec (`orchestrator/__init__.py:473` builds the ctx with the default `vps1`; `deploy` resolves it at `:147`; `:544` persists it) and wraps ONLY its `probe_app` walk over the `app_dir(spec)` candidates — the walk that replaces its two `find_existing` calls (`:491`, `:493`) — in `_target_vps_env(ctx)`; never the whole call, and `reconcile-all` never wraps `refresh_infrastructure`: a pipeline-level swap was tried and reverted on 2026-06-02 because the hub-side registrars (postgres, gatus, authelia on vps1) would ssh to the spoke (`:141-146`, `context.py:53-56`, `deployer_ssh.py:127-131`; review O2-1). `refresh_infrastructure` also resolves the directories it probes through `app_dir(spec)` (D2) instead of `/opt/<name>` alone, probing each candidate in order with the path-taking `probe_app`, so a local source living elsewhere (`fabrik-file-worker`, `path: /opt/file-worker`) stops raising "No compose app found" (`:494-497`; `_deploy_local` already handles that shape, `deployer_ssh.py:686-690`; review O2-2); a walk stops with a HOST error only when a candidate returns `exists` False with `error` set — a candidate that returns `exists` True is a match whatever its `ps` half returned (today `find_existing` swallows a `ps` failure the same way, `deployer_ssh.py:288-289`) — and that host error raises `ProvisioningError("could not reach <host>: <error>")` instead of today's "No compose app found" (so `redeploy --refresh-infra`, which has no `ls` pre-filter, reports the host, never a missing app); when every candidate is `absent` the error names every probed directory. `ctx.app_name` is the BASENAME of the candidate that matched — exactly today's `existing["name"]` (`orchestrator/__init__.py:499`), the value `read_env`/`inject_env` resolve to `/opt/<app_name>` (`deployer_ssh.py:326`, `:363`), so a stack under `/opt/fabrik-<id>` keeps receiving its registrar injections where it lives; every candidate `app_dir` yields is under `/opt` (both forms are `/opt/<x>`, and 7 of 7 local sources today point at `/opt/<x>`), which is what makes the basename the injection path. For a local source whose basename differs from the spec id (`file-worker`) that basename is where the files ARE, and `deploy`'s own `ctx.app_name = name` (`:232`) is the half that disagrees — U6 / W-9550a69c; until that lands, `reconcile-all` on such a spec injects into the right directory and `apply` into the wrong one, and the record's `coolify_uuid` flips between them (panel C3, re-ruled at pass 6: the matched directory wins because the injection path reads it). `tests/orchestrator/test_refresh_infrastructure.py`'s five `find_existing` stubs (`:53`, `:68`, `:79`, `:88`, `:103`) move to `probe_app`, the not-found test asserting the new `ProvisioningError` on a walk that returns `exists` False for every candidate (panel C1). Its second caller, `redeploy --refresh-infra` (`cli.py:1281`, which runs BEFORE redeploy's own host swap `:1309-1325`), passes its `--target-vps` through a new `target_vps: str | None = None` parameter with `deploy`'s precedence — flag > spec > `vps1` (`:147`); `reconcile-all` passes nothing (review O3-6). `_target_vps_env` is refactored to take a host string (`_host_env(host)`), the `ctx` form delegating to it. | `src/fabrik/cli.py:1549`, `:1561-1565`, `:1572-1577`, `:1580-1585`, `:1281`; `src/fabrik/orchestrator/deployer_ssh.py:123-145` (+ `_host_env`, `app_dir`, `list_compose_projects`); `src/fabrik/orchestrator/__init__.py:473`, `:491-499`, `:544`; `tests/orchestrator/test_refresh_infrastructure.py:53-103` |
| D4 | `fabrik projects --sync` | **REBASE.** `--sync` runs the project scanner (`scripts/sync_projects.py`, the same subprocess `fabrik scan` runs at `cli.py:1673-1681`) before listing — which is what `docs/reference/fabrik-cli-reference.md:354` already says it does; the `ProjectRegistry` is constructed AFTER the subprocess returns (its `__init__` loads `data/projects.yaml`, `registry.py:63-69`, the file the scanner rewrites — today it is built first, `cli.py:1623`, review O15); help text "Re-scan /opt and merge the deploy state before listing"; the `--status` help (`cli.py:1617`, "deployed/ready/development") drops `deployed`, whose only writer was the Coolify sync (`:1640`) — the scanner writes production/development/archived/paused (`scripts/sync_projects.py:225-226`; panel C2). `Project.coolify_uuid`/`coolify_name` and their `to_dict`/`from_dict` lines are removed — no writer remains; a `data/projects.yaml` row still carrying the keys is ignored on load (`from_dict` reads named keys only, `registry.py:44-55`). MIRROR: `registry.update(name, coolify_uuid=…)` had one caller (`cli.py:1636-1643`), gone with it. | `src/fabrik/cli.py:1617-1618`, `:1623-1648`; `src/fabrik/registry.py:23-24`, `:31-34`, `:49-50` |
| D5 | hub `/health` | **RETIRE the check, add nothing.** `_check_coolify_sync`, the `CoolifyClient` import and the `coolify` key leave; `/health` aggregates `{"dns": …}` alone and keeps its 200/503 rule. No ssh-reachability probe replaces it: a liveness endpoint stays shallow so a dependency outage never cascades into restarts (cr-43, cr-44), and the hub image has no consumer that could use a readiness signal (§ Personas). `compose.yaml:13-16` drops the four `COOLIFY_*` lines (two are `:?`-required, so the hub image could not even start without a dead token). Module docstring `health_app.py:1-5` says "DNS manager". `tests/test_health_app.py` loses its Coolify doubles and monkeypatches (`:8-14`, `:24-26`, `:38`, `:47`, `:52`). | `src/fabrik/health_app.py:3-4`, `:17`, `:55-67`, `:84-93`; `compose.yaml:13-16`; `tests/test_health_app.py:8-14`, `:24-26`, `:38`, `:47`, `:52` |
| D6 | `fabrik export` / `import` | **RETIRE the Coolify section.** `_collect_coolify` and the `coolify_client` parameter of `export_bundle`/`import_bundle` go; the tarball has no `coolify/` tree; the manifest's `coolify` count goes; the README template's Coolify prerequisites and restore steps (`:412-415`, `:421`, `:434-436`, `:453`) and the module docstring's tree and invariants (`:14-18`, `:34-35`) are rewritten for SSH + Compose; `cli.py:2886`'s docstring stops promising Coolify exports. `import_bundle`'s prefix index drops `coolify/` from `prefixes` and counts a legacy bundle's `coolify/*` members under `plan["ignored_legacy"]` (a top-level key beside `sections`/`actions`) so an old bundle imports with the count visible, never a silent drop — and `fabrik import`'s printer (`cli.py:2963-2983`, which prints `manifest`, `sections`, `actions` and `secrets_to_repopulate` and nothing else) prints the line `ignored legacy members (coolify/*): <n>`, or the key would be computed and never shown (panel). The real-run comment `:655-660` loses step 1 ("Recreate Coolify Projects"). `_collect_authelia`'s Coolify-volume comments (`:307-325`) are U5's. MIRROR: `export_bundle(coolify_client=…)` at 6 test call sites (`tests/test_portability.py:359`, `:384`, `:403`, `:428`, `:440`, `:466`) and the `_fake_coolify_client` fixture (`:310`) are removed with the parameter; the member assertion `:372-374` flips to "no `coolify/` member" and `:398-407` loses its `coolify/` filter. | `src/fabrik/portability.py:14-18`, `:34-35`, `:226-254`, `:412-453`, `:493`, `:506`, `:524`, `:539`, `:558-559`, `:588`, `:602`, `:645`, `:655-660`; `src/fabrik/cli.py:2883-2889` |
| D7 | `RollbackManager` | **RETIRE the branch.** The `coolify_client` ctor argument, the lazy `coolify_client` property and `_rollback_coolify` go; `rt == "coolify"` falls to the existing `else: logger.warning("Unknown resource type")` — the only live `add_resource("coolify", …)` is `deployer_coolify.py:101`, deleted by D8 (`grep -rn 'add_resource("coolify"' src/` → 1 hit in 1 file); the SSH deployer records `compose` (`deployer_ssh.py:225`). The docstring `:129-132` ("legacy `coolify`/`dns`/`monitor` types") and the comment `:267-270` ("contrast with `_rollback_coolify`/`_rollback_dns` … a lingering Coolify app") name `dns` alone. MIRROR: `RollbackManager(coolify_client=…)` — callers in `src/`: 0 (`orchestrator/__init__.py:93` passes nothing); in tests: `test_rollback.py:16`, `:45`, `:61`, `:88`, `:150`, `:359` (with its `:364` `add_resource("coolify")` and `:406` delete assertion), `test_e2e_rollback.py:164-166`. | `src/fabrik/orchestrator/rollback.py:20-43`, `:129-132`, `:142-145`, `:170-183`, `:267-270` |
| D8 | the Coolify modules | **DELETE** `src/fabrik/drivers/coolify.py` (934), `src/fabrik/orchestrator/deployer_coolify.py` (845), `src/fabrik/drivers/compose_updater.py` (451), `src/fabrik/orchestrator/coolify_alias.py` (144), `src/fabrik/deploy.py` (63), and their tests `tests/drivers/test_coolify.py` (2), `tests/orchestrator/test_deployer.py` (19), `tests/drivers/test_compose_updater.py` (20), `tests/test_coolify_alias.py` (12). `drivers/__init__.py` loses the import, the `__all__` entry and the docstring line; `config.py:104-109`'s commented readers and `.env.example:14-28`, `:305-312` go (W-00485146's code half; its `.env.example` CAPTCHA row is not this spec's). `drivers/postgres.py:1835`'s docstring sentence names the pattern without the module. Every `patch("fabrik.drivers.coolify.CoolifyClient")` goes (the target would no longer import): `tests/orchestrator/test_infrastructure.py:366`, `:476`, `:665`, `:717` (and its `:727` `coolify_cls…assert_not_called()`), `tests/orchestrator/test_e2e_rollback.py:257`, `:395`, `:450` — `grep -rn fabrik.drivers.coolify tests` → 8 lines, the eighth being `test_coolify.py:10`, deleted. | the files named; `src/fabrik/drivers/__init__.py:5`, `:12`, `:22`; `src/fabrik/config.py:104-109`; `.env.example:14-28`, `:305-312`; `src/fabrik/drivers/postgres.py:1835`; `tests/orchestrator/test_infrastructure.py:366`, `:476`, `:665`, `:717-727`; `tests/orchestrator/test_e2e_rollback.py:257`, `:395`, `:450` |
| D9 | state + context keys | **KEEP the names, fix the words.** `state.py`'s schema docstring and `save()` docstring describe `coolify_uuid` as "the compose app name (= the app directory under `/opt`), kept under its historical key" and drop `coolify` from the `ResourceRecord` type list (`:53`); `context.py:15`'s comment lists `"compose", "dns", "monitor"`. `sync_projects.py:242-246` keeps its `fabrik-<name>` fallback (state files written under either id form exist). `portability._collect_state` keeps stripping `coolify_uuid` (`:203`, `:219-221`): over the 9 records the value is `None` ×4, equal to `coolify_app_name` ×4 and a test id's label once (`no-glitchtip-smoke` → `smoke-app`), so the export loses nothing a restore reads; its docstring says "the compose app name, re-derived from the spec on import" (review O14). | `src/fabrik/state.py:26-27`, `:53`, `:165-168`; `src/fabrik/orchestrator/context.py:15`, `:45-49`; `src/fabrik/portability.py:203`, `:219-221` |
| D11 | hub scripts bound to the driver (W23) | **DELETE** `scripts/health_check_autonomous.py` (106 lines — every check it makes is a Coolify API call) and `scripts/migrate_db_rename.py` (688 — a Coolify-managed-app rename, run once at T1-05); `INDEX.md` carries no row for either (executed: 0 hits), so only `docs/CAPABILITIES.md`'s regeneration changes; **REBASE** the other four: `scripts/snapshot_vps_state.py` loses `snapshot_coolify` (`:36-56`), its `"coolify"` key (`:131`) and the app-uuid diff (`:153-156`); `scripts/update_vps_docs.py` loses `collect_coolify_apps` (`:153-163`), `render_coolify_apps` (`:256-271` — `render_limits_summary` `:273-286` STAYS, it is called at `:391` and `:412`), the call `:372`, the `len(apps)` print `:376`, the two `coolify_apps` section writes (`:399` into `docs/infrastructure/vps-urls.md`, `:410` into `vps-complete-inventory.md` — both no-ops today: `grep -rc 'AUTO:coolify_apps' docs/infrastructure` → 0 markers in 62 files, 14 of them top-level) and the docstring word (`:6`); `scripts/vps_sync.py` loses section 1 (`:409-422`, test-named Coolify apps) and ALL of section 4 (`:455-487`: without `active_fqdns` its loop can never report, and its container filter `label=coolify.serviceName=authelia` `:459` is itself a Coolify label); `scripts/proof_run.py` loses `_delete_coolify_app_by_name` (`:333-356`) and its call in `cleanup`'s no-spec branch (`:255-257` → a log line "no spec, nothing to destroy"), the Coolify half of `dump_diagnostics` (`:602-654`, docstring `:585-597`), the `load_env` COOLIFY_* keys (`:198-202`), `result["coolify_uuid"]` (`:700`), the `write_proof` "Coolify UUID" column (`:814`, `:821`), the docstring `:419`, and the app lookup `:738-756` — which is NOT cosmetic: the worker-type proof reads `app["status"]` (`:758-764`), so that proof is REBASED on `probe_app`'s `State` (every container `running`); plus `--use-orchestrator` (`:12`, `:518`) and the comments that describe the Coolify steps (`:65`, `:234`, `:239`, `:423`, `:504-506`). `vps_sync.py`'s remaining Coolify words (`:5`, `:395`, `:736`, `:759`) are reworded; its section 6 filters by `label=coolify.serviceName=meilisearch` (`:512`) — a docker label the Coolify-era container may still carry — and is NOT changed here: the plan's R1 read on vps1 records whether that label still matches a container, and the row stays or goes on that reading (review O3-8). `tests/test_update_vps_docs.py` pins nothing Coolify (`grep -c coolify` → 0) and is untouched. The archive copies (`scripts/.archive/2026-06-17-coolify-era-cleanup/`, `templates/.archive/`) are frozen history and stay; `scripts/enforcement/check_health.py:28`'s comment names `DNSClient` alone. | the six scripts at the lines named; `docs/CAPABILITIES.md` (regenerated) |
| D10 | docs and wording | every W21 line brought current; `cli.py:1124` ("- Coolify application") and `:1129` leave the destroy preview; `:891` (`--partial` help) says "no DNS removal, no file cleanup"; `:2402` "pre-deploy sequence", `:2473` "ready for deployment"; `audit-registrars`' hint `:1477` keeps naming `reconcile-all`, which is now true. `docs/CAPABILITIES.md` is regenerated, never hand-edited. `docs/development/plans/archived/2026-05-28-ssh-deployer.md § Known Broken` is a frozen archive and is NOT edited; the live docs that point at it (`CONFIGURATION.md:54`, `:663`) stop calling the verbs broken. | § Documentation landing sites |

Ordering (cr-21): one plan, phases by blast radius — (A) the three rebases + their graders (D2–D4, the deployer helpers);
(B) the retirements inside kept files (D1, D5, D6, D7, D9, D11's four rebased scripts) with their test edits; (C) the
deletions (D8, D11's two scripts) in ONE commit with every remaining importer and test edit, so no commit leaves an
import that cannot resolve; (D) docs (D10) and the
capability regeneration. A commit never deletes a module whose importer is deleted in a later commit. The appetite is
600 minutes and the panel's estimate 450–650: the plan marks the end of (C) as the session's hard stop, (D) and D11's four
script rebases may spill into a second session, each stop point green on its own.

## Contract deltas

No data-contract or ui-design freeze changes (the hub has neither). The CLI contract changes are: `fabrik apply`
loses `--legacy`, `--use-orchestrator`, `--skip-dns` and `--skip-deploy`; `fabrik projects --sync` means "re-scan";
`fabrik status` prints the last-apply and live-container sections; `fabrik reconcile-all` no longer aborts on a probe
failure — it finishes the table and exits 1 when no host could be read (at least one named), or under `--yes` when any
row is `host-unreachable`, `error`, `spec-error` or `lock-timeout`; otherwise 0 (invariant 2). The Python contract changes are: `fabrik.drivers` no longer exports `CoolifyClient`; `export_bundle`/
`import_bundle` lose `coolify_client`; `RollbackManager.__init__` loses `coolify_client`; `Project` loses two fields;
`SSHDeployer` gains `probe_app` and `list_compose_projects`; `deployer_ssh.py` gains the module-level `_host_env(host)` (the
existing `_target_vps_env(ctx)` delegates to it, so every deploy and `inject_env` reaches it) and `app_dir(spec)` (dict or
`Spec`); `refresh_infrastructure` gains `target_vps: str | None = None`, persists the spec's (or the flag's) host instead of
`vps1`, and records a local source's directory basename as the app name — all additions, so no caller breaks;
`find_existing` is unchanged. Each removal is a MIRROR row in the table above with its measured callers.

## Rejected alternatives

- **A1 — retire `status`/`reconcile-all`/`projects --sync` outright.** Each has a live question only it answers;
  deleting `status` moves the operator back to the five manual steps § Personas counts, deleting `reconcile-all` to
  `2 + N` applies by hand, and deleting `--sync` leaves `fabrik scan` as the only way to refresh the listing the verb
  prints (one extra verb per listing).
- **A2 — a `deprecated="…"` stub per retired path for one release** (cr-7, cr-9 convention). Nothing here is a retired
  VERB: the three verbs are rebased, and the retired path is an option whose absence click already reports with the
  option's name. A stub would also have to raise itself (cr-2, cr-6) — more code to carry for a signpost one operator
  does not need (cr-11).
- **B1 — `reconcile-all` reads the state records as the deployed set.** The store is gitignored and per-checkout
  (`ls -p /opt/fabrik/.fabrik/state | grep -v / | wc -l` → 9 in the main checkout, 5 in this worktree; `git ls-tree --name-only HEAD
  specs/services/ | grep -c '\.yaml$'` → 69 TRACKED specs — five `.yaml.draft`/`.yaml.superseded` siblings excluded — the
  denominator every count here uses): a service applied before state tracking, from another checkout, or whose record was lost would be skipped
  silently — a drift tool with a silent blind spot (the judge panel ranked it last in every seat for this). The record is the answer to *what did the last apply
  do* (D2 uses it for that); the deployed set is the host's.
- **B2 — one `find_existing` per spec for `reconcile-all`.** Two ssh round trips × 69 specs; `compose ls -a` is one call
  per host (cr-28, cr-37).
- **B3 — keep `drivers/coolify.py` and friends as a `Legacy` package or move them to `docs/archive/`.** Code nobody can
  run still costs every gate run and every reviewer's attention; the retrieval path is `git log -G` (cr-13, cr-20).
  PEP 387's window (cr-15) binds the stdlib (cr-29) and exempts exactly "features no one could reasonably be depending
  on" (cr-16).
- **B4 — rename the persisted `coolify_uuid`/`coolify_app_name` keys to `app_name`/`spec_name`.** A one-way migration
  of ten on-disk records plus a dual-read shim in `sync_projects.py`, `portability.py` and `state.py` for a rename with
  no behaviour change; the `app_name` property already gives new code the right word (`context.py:68-81`).
- **C1 — `/health` probes ssh reachability of vps1 instead of Coolify.** A liveness endpoint that shells out into the
  fleet cascades a network blip into a 503 and, under a restart policy, into restarts (cr-43); the hub image has no
  readiness consumer to serve.
- **C2 — delete `health_app.py`, the `Dockerfile` and `compose.yaml` as well** (nothing deploys the hub image). A
  separate retirement with its own blast radius (the Dockerfile is also the image the scaffold docs cite); out of this
  spec, boarded as a backlog item at close.
- **C3 — keep `coolify_alias.py`** because its name is the only Coolify thing about it. Its own docstring says it is
  decommissioned and must not be called, it has zero callers, and the VPS-side watcher it wrote to is gone; it is dead
  code with a test file (12 tests) that proves only that it still parses.

## Lifecycle

Adoption is one merge: no migration, no VPS change, no env var change on a host. Growth: none — the delta removes a
surface; `probe_app`, `app_dir`, `list_compose_projects` and `_parse_compose_ps` are reached by the two verbs and
`refresh_infrastructure`, `_host_env` by every deploy through the delegating `_target_vps_env`, and a host
with hundreds of projects is still one `ls` call. Degradation: an unreachable host prints a row and the run continues
(invariant 2); a Compose older than v2.21.0 on some future host is read through the array fallback (invariant 3). A
service name on the VPS that differs from `spec.id` and from its directory is reported "no compose project" — the plan's
one read-only `docker compose ls -a --format json` on vps1 (R1) checks that none exists before the verb ships.
Retirement and retrieval: the deleted modules live in history (`git log --oneline -G CoolifyClient`, cr-20); the D-row
at approval records the deletion commit so the retrieval has an address.

## Constraints Digest

Hub repo only; nothing here is governance-synced (`scripts/fabrik_synced_manifest.py` names none of the touched
paths); no VPS mutation; read-only ssh only in the plan's R1.

## Constraints

- Every ssh goes through `fabrik.drivers.ssh.ssh` under a host swap; no new host alias, key or sudo rule.
- `find_existing` is untouched (D2); the verbs' own probe is `probe_app`, a sibling with the same two-call shape plus `-a`,
  `sudo`, a quoted path and an `error` key.
- The deployed-set probe is bounded: one `ls` per distinct host, 60 s timeout each, cached for the run.
- No `.env` is read by this work; the deleted `.env.example` rows are placeholders (their own comment, `:17-18`).
- The plan's graders are red-first in a throwaway worktree; the hub's pytest leg is OFF, so the touched test files run by
  hand and their totals are stated (W20 names them).
- `docs/CAPABILITIES.md` changes only through `scripts/generate_capability_index.py`.

## fabrik-lib verdict

No new capability: ssh, Compose parsing and click are already in the tree; nothing to vendor and nothing new for the
module table (`/opt/fabrik-lib/README.md`).

## External dependencies

| E# | Dependency | Grounded fact | Source (ledger) |
|---|---|---|---|
| E1 | `docker compose ps --format json` | JSON Lines since v2.21.0 (PR #10918 merged 2023-08-25); the live formatter emits one key per exported no-argument single-return `ContainerContext` method (20 keys at 2.40.3, executed; `main` adds `Engine`), the docs example's nine being a subset — the parser tolerates unknown keys; `-a` for stopped; `Health` is `""` for any non-running container; no exit-code signal for health | https://github.com/docker/compose/issues/10958 · https://docs.docker.com/reference/cli/docker/compose/ps/ · https://raw.githubusercontent.com/docker/compose/main/cmd/formatter/container.go · https://github.com/docker/compose/issues/11784 (cr-22, cr-25, cr-32, cr-33, cr-34, cr-35, cr-46, cr-47) |
| E2 | `docker compose ls -a --format json` | a JSON array of `{Name, Status, ConfigFiles}`, `ConfigFiles` one comma-joined string (executed at 2.40.3); `-a` includes stopped projects; host-wide regardless of cwd | https://docs.docker.com/reference/cli/docker/compose/ls/ · https://raw.githubusercontent.com/docker/compose/main/cmd/compose/list.go (cr-28, cr-36, cr-37, cr-48) |
| E3 | click 8.3.1 (the venv, executed: `click.Command.__init__` has `hidden` and `deprecated`; a `deprecated=True, hidden=True` command printed its warning to stderr and ran) | `deprecated=` warns then runs the callback; no built-in non-zero stub | https://click.palletsprojects.com/en/stable/api/ · https://raw.githubusercontent.com/pallets/click/8.3.1/src/click/core.py (cr-1, cr-2, cr-6, cr-42) |
| E4 | the deprecation convention | PEP 387's window and its "no one could reasonably be depending on" exception; the SWE book's "code is a liability" and "let it stop functioning when some external event causes it to break" | https://peps.python.org/pep-0387/ · https://abseil.io/resources/swe-book/html/ch15.html (cr-12, cr-13, cr-16, cr-29, cr-45) |
| E5 | health-endpoint practice | shallow liveness, deep checks only for readiness, "degraded rather than unhealthy" | https://learn.microsoft.com/en-us/azure/architecture/patterns/health-endpoint-monitoring (cr-43) |

1a internal facts were executed, not cited: the state records read (9 files in the main checkout, 5 in this worktree;
keys and `uuid` values listed in W14), the importer census (`command grep -rn "CoolifyClient\|deployer_coolify\|
_rollback_coolify\|_collect_coolify" src/fabrik` → 37 lines in 9 files, all in W1–W13; and over `scripts`
`--include=*.py` → 29 lines in 8 files, W23 — the review found the first census had stopped at `src/fabrik`), the test
counts (W20, `grep -c "def test_"` per file), the fleet Compose version (W19), click's behaviour (E3, run in `.venv`), and
the Compose JSON shapes (invariant 3, run locally at 2.40.3). Fetched 2026-10-14 by four `fabrik-researcher` seats (WebSearch +
WebFetch + exa + firecrawl; the ledger names the arm per row).

## Shape / infra implications

None: no `specs/services/*.yaml` changes, no registrar, no `shape:` flag, no port, no compose service on any host.

## Documentation landing sites

- `docs/reference/fabrik-cli-reference.md` — `:116-129` (the `apply` syntax line and flag table lose `--skip-dns`,
  `--skip-deploy`, `--legacy`; `--yes` reads "accepted, never prompts"), `:268-274` (status: add the two sections),
  `:346-354` (already correct; confirm), `:457` (`apply` loses its `deploy.py::deploy_to_coolify` half), `:463`
  (`reconcile-all` → `deployer_ssh.list_compose_projects` + `refresh_infrastructure`), `:466` (`status` → `cli.py` +
  `deployer_ssh.probe_app`).
- `docs/DEPLOYMENT_ARCHITECTURE.md` — `:75` (the `apply` row's flags), `:103` (legacy file sentence removed), `:137` (row
  removed), `:161` (the `deploy.py` "Dead code" row goes with the file), `:166` (monitor.py row — it is not used by
  `status`/`logs`: 0 imports in `cli.py`; reworded), `:167` (health_app row loses the Coolify note), `:527`, `:547-548`
  (`--skip-dns`/`--skip-deploy` examples).
- `docs/reference/architecture.md:70`, `:85`, `:121` (`--skip-dns`), `:184`, `:189` (`deploy.py` tree line), `:207`, `:219`,
  `:233` — rows and tree lines removed or reworded; `docs/reference/apis/EXTERNAL_SYSTEMS.md:284` (`cli.py:399 --skip-dns`).
- `docs/reference/modules/drivers.md:5-10`, `:28`, `:40`, `:62-69`, `:315` — banner, two rows, the CoolifyClient section
  and the test-file list.
- `docs/SERVICES.md:64-67`; `docs/CONFIGURATION.md:50-57`, `:659-666`; `docs/reference/health-monitoring.md:101`;
  `docs/operations/deployment.md:489-490` (the commented `reconcile-all` becomes a live command);
  `docs/TROUBLESHOOTING.md:186`, `:202` (the retired file is now "removed at <commit>"); `agents-fabrik.md:102`, `:404`,
  `:409`; `README.md:56`, `:559`, `:704`; `INDEX.md:261`, `:1704`, `:1711` (and the rows for the deleted files);
  `docs/FEATURES.md:313`, `:686`.
- `docs/CAPABILITIES.md` — regenerated.
- `docs/TROUBLESHOOTING.md:170`, `docs/reference/modules/deployment-orchestrator.md:21-22`, `:94`, `:100`,
  `docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md:625-630`, `:1212` — the `--use-orchestrator`, `--legacy`, `--skip-dns` and
  `--skip-deploy` mentions go (the same flag blocks carry all four). `INDEX.md` has no row for either deleted script
  (executed: 0 hits), and `docs/infrastructure/` carries no `AUTO:coolify_apps` marker (0 of 62 files, 14 top-level), so neither changes.
- `CHANGELOG.md` — one `### Changed` entry; `docs/DECISIONS.md` — the approval row (reversible) naming the deletion
  commit; the work store — C2 (the hub image's own retirement) is already boarded as `W-2191a0f4`
  (`.fabrik/work/W-2191a0f4.json`, linked to this spec).
- No new reference doc: the verbs are documented where they are documented today.

## Validation

Behaviour graders, red-first in a throwaway worktree (the root conftest pins the checkout src):

- V1 `status` parses a JSON-Lines `ps` fixture carrying the full 20-key shape (running+healthy, exited+`""` printed `—`,
  running+`""` printed "no healthcheck", running+`"none"`) into four rows and the array form of the same fixture into the
  same rows; a fixture row with an unknown extra key is accepted; a record-less spec prints the "never applied" line; a `RuntimeError`
  from ssh prints the "could not reach" line and exits 0.
- V2 `probe_app`'s two commands are pinned on a recorded fake ssh: `sudo sh -c '[ -f <quoted dir>/compose.yaml ] && echo
  exists || echo absent'` (the exact string, quotes included) then `cd <quoted dir> && sudo docker compose ps -a --format
  json`; a `RuntimeError` from the first call yields `error` set and `exists` False, a `TimeoutExpired` from the second
  yields `exists` True with `error` set, an empty or banner stdout from the first yields `error` set, a non-JSON `ps` body
  yields `error` set with `exists` True; a path with a space is quoted; `find_existing`'s recorded commands are unchanged
  (`test_not_found_ssh_fails` still green).
- V3 `reconcile-all` with a fake `ls` returning `[{"Name":"a",…},{"Name":"other","ConfigFiles":"/opt/x/compose.yaml,/opt/b/compose.yaml"}]`
  reconciles specs `a` and `b`, skips `c` with the "skipped — no compose project (no containers) on vps1" row, matches a local-source spec
  `fabrik-file-worker` (`source.path: /opt/file-worker`) through `ConfigFiles: /opt/file-worker/compose.yaml` and a spec
  `d` through the project name `fabrik-d`, and with a second spec on `vps2` whose `ls` raises `TimeoutExpired` prints
  `host-unreachable` for it while the others still reconcile; the `ls` runs once per host (call count); driving the REAL
  `refresh_infrastructure` with a recording fake ssh, the vps2 spec's `probe_app` calls run under
  `FABRIK_VPS_SSH_HOST=vps2`, its ctx carries `target_vps="vps2"`, a hub-side registrar's ssh in the same call still
  sees the default host (the reverted pipeline swap, O2-1), a walk whose SECOND candidate returns `error` (the first
  `absent`) raises `ProvisioningError` naming the host, a walk whose candidate returns `exists` True with `error` set is a
  match, a walk where every candidate is `absent` raises an error naming every probed directory, and the matched
  candidate's basename is `ctx.app_name`; exit codes: 1 when every host's `ls` raises (run WITHOUT `--yes`), 1 under
  `--yes` with one `host-unreachable`, one `error`, one `spec-error` or one `lock-timeout` row (four runs), 0 for the same
  runs without `--yes`, 0 when every row is `reconciled`/`skipped`, 0 for a `--filter` matching nothing while a broken spec
  sits outside the filter, 0 when every loaded spec is `spec-error` and 1 for the same run under `--yes`, 1 for an empty
  specs directory ("No specs found.", unchanged); a local source whose normalised path is not a direct child of `/opt`
  raises `ProvisioningError` from `app_dir` before any probe; `fabrik-file-worker` resolves to `/opt/file-worker` through
  `app_dir` inside `refresh_infrastructure` (O2-2).
- V4 `projects --sync` invokes the scanner subprocess once (recorded argv), lists a project the fake scanner added to
  `data/projects.yaml` (the registry is read after the subprocess), and never imports `fabrik.drivers.coolify` (the module
  no longer exists — an `importlib.util.find_spec` assertion).
- V5 `/health`: dns healthy → 200 with `checks == {"dns": …}` and no `coolify` key; dns failing → 503 `degraded`.
- V6 `export` tarball has no member under `coolify/`; the manifest has no `coolify` count; `import` (dry run) of a
  hand-built legacy bundle with two `coolify/*.json` members reports `ignored_legacy == 2` in the plan AND the `fabrik import`
  CliRunner output contains the line `ignored legacy members (coolify/*): 2`.
- V7 a `DeploymentContext` carrying `add_resource("coolify", "x")` rolls back with a warning and no exception.
- V8 the census: `git grep -l -e drivers.coolify -e CoolifyClient -e deployer_coolify -e compose_updater -e coolify_alias -e deploy_to_coolify -- src scripts tests templates ':!*/.archive/*'` = 0 files (tracked files only — a recursive `grep` would also list the gitignored `__pycache__/*.pyc` leftovers, 6 in this tree; denominator: every tracked `*.py` outside the two frozen `.archive/` trees, `git ls-files -- '*.py' | grep -vc '/.archive/'`), stated in the receipt — the seven non-import hits the regex also matches are each named by a D-row so the live set reads 0: the `check_health.py:28` comment (D11), the `scripts/proof_run.py:419` docstring (D11), the `tests/test_portability.py:16` docstring (D6), `tests/test_health_app.py`'s doubles (D5), `tests/orchestrator/test_e2e_rollback.py:143`, `:319` (a docstring and a comment, D7), and the `src/fabrik/drivers/postgres.py:1835` docstring (D8); `vulture src/fabrik --min-confidence 80` shows no new item against the pre-delta baseline (cr-17); `ruff` F401 clean (cr-18).
- V9 the touched test files run by hand with their totals: `test_health_app`, `test_portability`, `test_rollback`,
  `test_e2e_rollback`, `test_infrastructure`, `test_refresh_infrastructure`, `test_sync_has_user_guide` (the one test
  file that builds `registry.Project` and calls `from_dict` — D4's surface; there is no `test_registry.py`, and no test
  names `ProjectRegistry`), `test_state`, `test_sync_projects_state`, `test_deployer_ssh`, plus the new `tests/test_cli_status_live.py` and `tests/test_reconcile_all_deployed_set.py`.
- V10 `python scripts/final_gate.py --check --json` green; `scripts/generate_capability_index.py` run and its diff committed.

## Open / blocking unknowns

- U1 (resolved by execution) — Compose 2.40.3 emits `"Health":""` for a container with no healthcheck and for every
  non-running container (cr-47, executed locally on `/opt/tryton-crm`); `"none"` was not observed and is accepted anyway.
- U2 (resolved, harmless) — the `ls` `Status` string is `running(6)` / `exited(1)` at 2.40.3 (executed locally, cr-48); never parsed.
- U3 (resolved by design; R1 measures the residue) — a compose project whose `Name` differs from `spec.id`: the
  `ConfigFiles` directory match covers it (the string holds every `-f` file joined by `,`, so a project run with two
  compose files still matches); R1 — the plan's one read-only ssh on vps1 — lists the fleet's project names beside their
  config paths so a third form, if one exists, is seen before the verb ships, AND diffs the `ls -a` names against
  `ls -d /opt/*/compose.yaml`, so the number of downed-but-present stacks `reconcile-all` would now skip (invariant 1) is a
  measured fact, not an assumption.
- U4 (resolved by the review) — `find_existing` is untouched: its readers (`deployer_ssh.py:209`, `:224`, `:690`, `:742`;
  `orchestrator/__init__.py:491-499`; `cli.py:1332`) test truthiness or read `name`, none reads `status`, and D2 probes
  through the new `probe_app` instead of widening the old method.
- U5 (plan-time check) — `portability._collect_authelia` (`:307-325`) reads Authelia's configuration from a Docker volume
  it describes as "a Coolify Service … volume"; whether that volume path still holds the live configuration after the
  2026-05-30 removal is read by the plan's one read-only ssh (R1, beside the `compose ls` listing); the comments are
  reworded to what it finds, and a moved path is a defect of the export the plan fixes.
- U6 (out of this spec, boarded) — `deploy`'s own path resolves `read_env`/`inject_env` at `/opt/{ctx.app_name}`
  (`deployer_ssh.py:326`, `:363-364`) while `_deploy_local` writes a local source's files at `source.path` (`:668-671`,
  `:692`): for `fabrik-file-worker` a registrar injection during `apply` lands in `/opt/fabrik-file-worker/.env`, not
  `/opt/file-worker/.env` — a pre-existing defect of the deploy path the panel found while checking D3; boarded as
  backlog item W-9550a69c linked to this spec, not widened into it.
- Residual assumption: no caller outside the hub imports the deleted modules. Measured 2026-10-14: `command grep -rl
  --include=*.py "from fabrik.drivers\|import fabrik.drivers\|fabrik\.deploy import\|fabrik.drivers.coolify" /opt` (every
  `/opt` directory but the hub, `.venv`, `node_modules` and `.git` skipped) → 1 file of 58 repos searched (59 `/opt`
  directories, the hub excluded), `ai-model-catalog/engine/tests/test_rank_task_subagents.py`,
  which `importorskip`s `fabrik.drivers.postgres` (`:810`), a module this delta keeps; the synced manifest ships no `src/fabrik` module
  (`scripts/fabrik_synced_manifest.py:21` names `scaffold.py` only as the generator of the `.gitignore` block).

## Decisions taken

**Judge panel (D-363), three Sonnet `general-purpose` seats, approaches handed in alphabetical order without a
recommendation, scored on the five criteria and the six reality challenges:** axis 1 (the modules' fate: Archive · Delete ·
Legacy) — Delete ranked first 3 of 3 (Legacy failed "high-maintenance where set-and-forget exists" in every seat; Archive
failed "duplicate functionality" — git history already archives); axis 2 (`reconcile-all`'s deployed set: Ls · Probe · State)
— Ls ranked first 3 of 3 (State last in every seat: a drift tool whose blind spot is silent; Probe second: 2 × 69 ssh calls
for the answer `ls` gives per host). Seat corrections folded: the state-record count (9, not 10 — `_destroyed/` is a
directory), the deleted-line total (2,437, not ~2,230), two hosts named today (not three), `find_existing`'s swallowed
second-call error (D2's `error` key). The recommendation below is the panel's majority on both axes.

Reversible: the three verbs are rebased, `--legacy`/`deploy.py` are removed, the five Coolify modules and 53 tests are
deleted in one commit, the persisted keys keep their names — one D-row at the approval panel (D-613), minted with
`scripts/decisions.py --reserve-id .`, naming the deletion commit as the retrieval address. The reversal is `git revert`
of that commit (the code was never functional, so nothing downstream can have come to depend on the deletion). The
window PEP 387 would give a stdlib feature does not bind an internal CLI whose backend is gone (cr-16, cr-29); the
authority for a change that cannot warn is, here, the panel (cr-30, D-558). Rejected at design time: A1, A2, B1–B4,
C1–C3 above.

## Ask ↔ spec

One row per item of the brief (W-36571dff's title and `next`, the `/fabrik-task` arguments that routed here, the operator's standing rulings), in its own words; then one row per section the brief did not ask for.

| # | The ask (own words) | What the spec says | Anchor | Disposition |
|---|---|---|---|---|
| A1 | *"the CLI verbs still bound to the retired Coolify API (fabrik status, …)"* | `status` reads the state record and the live `docker compose ps -a --format json` over ssh | § The delta D2 | IN |
| A2 | *"… logs, …"* | `fabrik logs` queries Loki and the local compose; it was never Coolify-bound | § What exists today W2 | DROPPED — mis-attributed by the item; the docs that call it a Coolify verb are corrected (D10) |
| A3 | *"… reconcile-all, …"* | the deployed set is one `docker compose ls -a --format json` per target host; a probe failure is a row and the run finishes, with the exit code telling the truth (1 when nothing could be read, or under `--yes` with a failure row) | § The delta D3, invariant 2 | IN |
| A4 | *"… registry --sync"* | `projects --sync` re-runs the project scanner; the two `coolify_*` registry fields go | § The delta D4 | IN — the verb is `projects --sync`; `registry` is not a verb |
| A5 | *"plus health_app/deploy/portability/compose_updater imports"* | the `/health` Coolify check removed, nothing added; `deploy.py` deleted with `apply --legacy`; the export's `coolify/` tree removed, legacy bundles tolerated; `compose_updater.py` deleted | § The delta D5, D1, D6, D8 | IN |
| A6 | *"docs/DEPLOYMENT_ARCHITECTURE.md:137"* | the row and every sibling doc line in W21 brought current | § The delta D10, § Documentation landing sites | IN |
| A7 | *"retire or rebase each on the SSH+Compose deploy model"* | three verbs rebased, one option retired, five modules deleted — per surface in the D-table | § The delta | IN |
| A8 | *"Supersedes the reconcile-all-only W-ef765f8d"* (and its `audit-registrars` hint) | the hint at `cli.py:1477` keeps naming `reconcile-all`, now a live verb | § The delta D10, § Personas | IN |
| A9 | *"orchestrator/deployer_coolify.py and orchestrator/rollback.py (legacy paths)"* (the `/fabrik-task` arguments) | the deployer deleted; the rollback's `coolify` branch and client retired | § The delta D7, D8 | IN |
| A10 | *"src/fabrik/drivers/__init__.py:12 (exports CoolifyClient)"* | the export, the docstring line and the `__all__` entry go | § The delta D8 | IN |
| A11 | *"whether the ~2,200-line driver/deployer/updater and their ~60 tests are deleted (one-way), kept as `Legacy` with a deprecation shim, or moved out"* | deleted — 2,437 lines and 53 tests measured; Archive and Legacy rejected; the judge panel ranked Delete first 3 of 3 | § Rejected alternatives B3, § Decisions taken | IN |
| A12 | *"what `status`/`reconcile-all`/`projects --sync` read as the live truth (state records vs ssh probe vs both)"* | both, each for its own question: the record for the last apply, the host for what is alive, the scanner for the registry | § The delta invariant 1, D2–D4, § Rejected B1 | IN |
| A13 | *"what health_app's dependency check becomes (ssh reachability of vps1? the state store? nothing)"* | nothing — a liveness endpoint stays shallow (cr-43) | § The delta D5, § Rejected C1 | IN |
| A14 | *"the registry's coolify_* fields and state.py's `coolify` resource type"* | registry fields removed; state keys kept under their historical names, the type list corrected | § The delta D4, D9, § Rejected B4 | IN — CHANGED: the state keys are kept, not renamed (a persisted format with nine records in the main checkout and three readers) |
| A15 | *"docs (DEPLOYMENT_ARCHITECTURE.md, QUICKSTART/CLI docs that mention these verbs)"* | the W21 list; QUICKSTART's two lines stay true as written | § Documentation landing sites | IN |
| A16 | *"No D-row in the hub records the Coolify retirement itself"* | the approval row minted at this gate records the retirement and names the deletion commit as the retrieval address (id D-828, reserved with `decisions.py --reserve-id`; the row lands in the CONVERGED commit, so it is absent from `docs/DECISIONS.md` until then) | § Decisions taken | IN |
| A17 | *"Autonomy (D-558) … design approval is the panel's (D-613)"*; Pool OFF; seats never ssh | native seats only; the Opus + Fable panel approves at this gate | this run | IN |
| S1 | `## Personas` (step budgets, automated consumers) | not asked | § Personas | ADDED — the command mandates it (operator law 2026-08-29) |
| S2 | `## Lifecycle` | not asked | § Lifecycle | ADDED — the command mandates it (interrogative floor) |
| S3 | the `coolify_alias.py` deletion | not asked | § The delta D8, § Rejected C3 | ADDED — found in the measure: decommissioned by its own docstring, zero callers, 12 tests |
| S4 | the `destroy`/`export`/`domain` wording and the `--use-orchestrator` no-op flag | not asked | § The delta D1, D10 | ADDED — an existing code path that lies to the operator about a control plane that is gone |
| S5 | the COOLIFY_* `.env.example` rows and `config.py` readers | not asked here (W-00485146) | § The delta D8 | ADDED — the readers die with the driver, so the rows' own "until that legacy code is removed" condition is met |
| S6 | the research ledger and the judge panel | not asked | ledger; § Decisions taken | ADDED — the command mandates both (1c floor, D-363) |
| A18 | the hub image itself (`Dockerfile`, `compose.yaml`, `health_app.py`) — implied by *"health_app … imports"* | no deployer exists for it; its own retirement is a separate decision | § Rejected alternatives C2, I20 | DROPPED — boarded as W-2191a0f4 |
| S7 | six hub scripts still importing the driver | not asked | § The delta D11, W23 | ADDED — found by the review's Opus slice; the item's census had stopped at `src/fabrik` |
| S8 | `apply`'s `--skip-dns`/`--skip-deploy` and the `--yes` no-op | not asked | § The delta D1 | ADDED — an existing code path read only on the removed branch (review O9, O2-8) |
| S9 | `projects --sync`'s registry ordering; `refresh_infrastructure`'s host swap and app directory | not asked | § The delta D3, D4 | ADDED — review findings O15, O2-1, O2-2 on the rebased verbs' mechanics |
| S10 | the deploy path's local-source env mismatch (`inject_env` at `/opt/<app_name>` vs `_deploy_local`'s `source.path`), found by the panel while checking D3 | not asked | § Open/blocking unknowns U6 | DROPPED — out of scope, boarded as W-9550a69c (linked to this spec) |

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"`fabrik status` (cli.py:723-784, CoolifyClient.list_applications)"* (item) | IN | D2 |
| I2 | *"`fabrik logs` (cli.py:785-870)"* (item) | OUT-OF-SCOPE — measured not Coolify-bound (W2); the docs calling it so are corrected | W2, D10 |
| I3 | *"`fabrik reconcile-all` (cli.py:1535-1615)"* (item; W-ef765f8d's `audit-registrars` hint) | IN | D3, D10 (`:1477`) |
| I4 | *"`fabrik registry --sync` (cli.py:1616-1665)"* (item — the verb is `projects --sync`) | IN | D4 |
| I5 | *"the Coolify imports in src/fabrik/health_app.py"* | IN | D5 |
| I6 | *"src/fabrik/portability.py:230-240 (CoolifyClient injected for export)"* | IN | D6 |
| I7 | *"src/fabrik/drivers/compose_updater.py:72 (imports CoolifyClient)"* | IN — deleted | D8 |
| I8 | *"orchestrator/deployer_coolify.py and orchestrator/rollback.py (legacy paths)"* | IN — deployer deleted, rollback branch retired | D7, D8 |
| I9 | *"src/fabrik/drivers/__init__.py:12 (exports CoolifyClient)"* | IN | D8 |
| I10 | *"docs/DEPLOYMENT_ARCHITECTURE.md:137 (drivers/coolify.py 'Legacy' row)"* | IN | D10 |
| I11 | *"fabrik.deploy.deploy_to_coolify already disabled"* / `apply --legacy` Step 3 | IN — removed | D1 |
| I12 | *"whether the ~2,200-line driver/deployer/updater and their ~60 tests are deleted (one-way), kept as `Legacy` with a deprecation shim, or moved out"* (brief) | IN — deleted; measured 2,437 lines and 53 tests; the judge panel ranked Delete first 3 of 3 | D8, B3 |
| I13 | *"what `status`/`reconcile-all`/`projects --sync` read as the live truth (state records vs ssh probe vs both)"* (brief) | IN — both, each for its own question | invariant 1, D2–D4, B1 |
| I14 | *"what health_app's dependency check becomes (ssh reachability of vps1? the state store? nothing)"* (brief) | IN — nothing | D5, C1 |
| I15 | *"the registry's coolify_* fields and state.py's `coolify` resource type"* (brief) | IN — registry fields removed; state keys kept, type list corrected | D4, D9, B4 |
| I16 | *"docs (DEPLOYMENT_ARCHITECTURE.md, QUICKSTART/CLI docs that mention these verbs)"* (brief) | IN | D10; `QUICKSTART.md:108`, `:132-133` stay true as written |
| I17 | `orchestrator/coolify_alias.py` (found in the measure; `agents-fabrik.md:409`) | IN — deleted | D8, C3 |
| I18 | W-00485146: COOLIFY_* `.env.example` rows and `config.py` readers | IN — the code half; its CAPTCHA row stays that item's | D8 |
| I19 | `destroy`/`export`/`domain` wording that still promises Coolify actions | IN | D10 |
| I20 | the hub image itself (`Dockerfile`, `compose.yaml`, `health_app.py`) has no deployer | OUT-OF-SCOPE — boarded as backlog item W-2191a0f4 (`.fabrik/work/W-2191a0f4.json`, linked to this spec) | C2 |
| I21 | *"No D-row in the hub records the Coolify retirement itself"* (brief) | IN — the approval row records it | § Decisions taken |
| I22 | *"Autonomy (D-558) … design approval is the panel's (D-613) at /fabrik-spec-review"*; Pool OFF (D-181); seats never ssh | IN | this run |
| I23 | six hub scripts still import the driver (found by the review's Opus slice; `scripts/proof_run.py` also passes `--use-orchestrator`) | IN — two deleted, four lose their Coolify section | D11, W23 |
| I24 | `apply`'s `--skip-dns`/`--skip-deploy` read only on the legacy path (review O9) | IN — removed with the path | D1 |
| I25 | `projects --sync` builds the registry before the scanner rewrites its file (review O15); `refresh_infrastructure`'s host and directory for spoke and local-source specs (review O2-1, O2-2) | IN | D4, D3 |
| I26 | the deploy path resolves `read_env`/`inject_env` at `/opt/<ctx.app_name>` while `_deploy_local` writes at `source.path` (found by the approval panel, Opus C3 + Fable 4) | OUT-OF-SCOPE — boarded as backlog item W-9550a69c (`.fabrik/work/W-9550a69c.json`, linked to this spec) | U6 |
