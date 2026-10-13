# The Coolify-bound verbs move to the SSH + Compose model and the Coolify code leaves the tree

**Status:** DRAFT
**Profile:** delta

Work item W-36571dff (fleet; infra-assigned 2026-10-13; it supersedes W-ef765f8d and folds W-00485146's code half).
Routed here by `/fabrik-task`'s SIZE gate (refusal LR-59996fe9: appetite 600 > 240 min, `oneway=yes`, `tradeoffs=yes`).
Research ledger: `docs/reference/research/2026-10-14-coolify-verb-retirement-ledger.md` (45 rows, every one dispositioned).
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
`CoolifyClient.list_applications()`), `fabrik projects --sync` prints *"Sync error"* and syncs nothing (`cli.py:1624-1648`),
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
| W4 | `fabrik projects --sync` | help "Sync with Coolify first"; writes `coolify_uuid`/`coolify_name`/`domain` into the registry | `src/fabrik/cli.py:1616-1665` (`:1618`, `:1624-1648`, `registry.update :1636-1643`) |
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
| W19 | the fleet's Compose | 2.40.3 measured | `src/fabrik/orchestrator/deployer_ssh.py:1217` |
| W20 | tests pinning the importers | `test_health_app` 2 · `test_portability` 26 (9 pass `coolify_client=`) · `test_rollback` 22 (6 Coolify-specific) · `test_e2e_rollback` 3 (mock `CoolifyClient`) · `test_infrastructure` patches `fabrik.drivers.coolify.CoolifyClient` at `:366`, `:476` · `test_deployer` 19 · `test_compose_updater` 20 · `test_coolify` 2 · `test_coolify_alias` 12; **0 tests pin the three verbs' Coolify output** (`grep -rn "Found in Coolify\|Syncing with Coolify\|no Coolify app" tests/` → 0 of 12 files naming `list_applications`/`coolify_uuid`) | the files named |
| W21 | docs saying "broken" or "legacy Coolify" | `CONFIGURATION.md:50-55`, `:659-666`; `SERVICES.md:64-67`; `DEPLOYMENT_ARCHITECTURE.md:103`, `:137`, `:166-167`; `reference/architecture.md:70`, `:85`, `:184`, `:207`, `:219`, `:233`; `reference/modules/drivers.md:5-10`, `:28`, `:40`, `:62-69`, `:315`; `reference/health-monitoring.md:101`; `reference/fabrik-cli-reference.md:463`, `:466`; `operations/deployment.md:489-490`; `TROUBLESHOOTING.md:186`, `:202`; `agents-fabrik.md:102`, `:404`, `:409`; `README.md:56`, `:559`, `:704`; `INDEX.md:261`, `:1704`, `:1711`; `FEATURES.md:313`, `:686`; `docs/CAPABILITIES.md:37`, `:46` (generated) | each cited |
| W22 | the Coolify era in the ledger | no hub D-row records the Coolify retirement itself (`grep -ci coolify docs/DECISIONS.md` → 2 rows, both incidental: D-079, D-122) | `docs/DECISIONS.md:432`, `:475` |

`fabrik logs` (W2) is NOT in scope: the item mis-attributes it. The docs that call it a Coolify verb (`CONFIGURATION.md:53`,
`:662`; `drivers.md:10`; `coolify.py:6`) are corrected by D10, which is all the item's "logs" row needs.

## The delta

Invariants, then the per-surface deltas.

1. **A verb answers from a source that exists.** The live truth for *is it deployed / alive* is the target host's
   Compose over ssh; the hub-side truth for *what did the last apply do* is the state record; the registry truth is the
   scanner. No verb reads an HTTP control plane.
2. **A probe failure is a row, never an exit.** `reconcile-all` and `status` print the host's error beside the spec and
   continue; only a spec that fails to load exits 1 (as today, `cli.py:732-736`).
3. **The Compose JSON contract is the documented one.** `ps --format json` is JSON Lines (one object per line, since
   v2.21.0 — cr-22) read with only the nine emitted keys (cr-23); `State` ∈ `created|running|paused|restarting|removing|exited|dead`
   (cr-34); `Health` ∈ `healthy|unhealthy|starting`, and `""` or `"none"` means "no healthcheck" (cr-32, cr-35). The
   parser also accepts a leading `[` (the pre-2.21 array) so an older host does not break the verb. `ls --format json`
   is a plain array of `{Name, Status, ConfigFiles}` (cr-28, cr-37); `Status` is never parsed (U2). Neither command's
   exit code says anything about health (cr-33).
4. **Delete, do not shim.** A module whose backend is gone is removed with its tests in the same change as its
   importers (cr-21); a reader who needs it runs `git log -G CoolifyClient` (cr-13, cr-20).
5. **Persisted names stay.** The on-disk state keys `coolify_uuid`/`coolify_app_name` and `DeploymentContext.coolify_uuid`
   are a persisted format with ten records and three readers; this delta corrects their DOCSTRINGS, not their names.

| D# | Surface | Delta | Touchpoints |
|---|---|---|---|
| D1 | `fabrik apply --legacy`, `deploy.py` | **RETIRE.** The `--legacy` option (`cli.py:408-417`), the hidden no-op `--use-orchestrator` (`:402-407`) and the legacy branch (`:517`'s `else` to `:692`) are removed; `src/fabrik/deploy.py` is deleted. A stale `--legacy` gets click's own `No such option` (exit 2). The deprecated-stub shape was evaluated and NOT taken: click's `deprecated=` prints and then RUNS the callback (cr-2), so a stub would have to raise itself (cr-6); the item names no verb that is retired outright — every verb has a live rebase — and the one dead path is an OPTION, for which click's refusal is already the actionable message (cr-45). `hidden=True` on a signpost was refuted as a documented pattern (cr-42). | `src/fabrik/cli.py:402-417`, `:449`, `:458-466` (docstring), `:517-692`; `src/fabrik/deploy.py` (delete) |
| D2 | `fabrik status <spec>` | **REBASE** (judge panel, 3 of 3 seats: Ls/Delete ranked first on both axes — § Decisions taken). After the `apps/<id>` block, two sections replace the Coolify block: (a) **Last apply** from `state.load(spec.id)` — `applied_at`, `git_sha[:12]`, `target_vps`, the `registrars_applied` types, and each `registrar_failures` row; "no state record — never applied from this checkout" when absent; (b) **Live containers** from `SSHDeployer().find_existing(spec.id)` run inside the host swap for the record's `target_vps` (else the spec's, default `vps1`), its `status` text parsed per invariant 3 into one row per container: `Service · State · Health · ExitCode`; "no /opt/<id>/compose.yaml on <host>" when `find_existing` returns None; "⚠️ could not reach <host>: <error>" on a `RuntimeError`. `find_existing`'s `ps` gains `-a` so an exited container is a row, not an absence (cr-25), and its dict gains `"error": <text> | None` — today a `RuntimeError` on the second ssh call is swallowed into `status: ""` (`:287-289`), which `status` would print as "no containers" (judge seat 2: a mid-call network blip on a spoke read as a deployed-but-empty project); the verb prints "⚠️ could not read containers on <host>: <error>" instead. MIRROR: the dict's two readers test truthiness only (`:224`, `:742`), so a new key changes nothing there. Exit 0 in every probe outcome (invariant 2). | `src/fabrik/cli.py:752-784`; `src/fabrik/orchestrator/deployer_ssh.py:273-291` (`-a`), `:123-145` (the host swap takes a host name — see D3); new `_parse_compose_ps(text) -> list[dict]` beside `find_existing` |
| D3 | `fabrik reconcile-all` | **REBASE.** The deployed set is read ONCE per distinct target host named by the loaded specs (`spec.target_vps`, default `vps1` — today 1 of 69 specs names `vps2`, so two hosts, two calls): `sudo docker compose ls -a --format json` over ssh under that host's swap, parsed as an array; a spec is deployed when a project's `Name == spec.id` OR one of its `ConfigFiles` has parent-directory basename `spec.id` (the deployer runs `cd /opt/<name> && docker compose up`, `deployer_ssh.py:540`, so the project name defaults to the directory — the second match covers a compose file that sets `name:`). Rows: `reconciled`/`dry-run` as today; `skipped — no compose project on <host>`; `host-unreachable — <error>` for every spec on a host whose `ls` failed (the run continues; today's exit 1 at `:1564` is gone). `_target_vps_env` is refactored to take a host string (`_host_env(host)`), with the existing `ctx` form delegating to it; the one-call inventory is `list_compose_projects(host) -> list[dict]` in `deployer_ssh.py`. | `src/fabrik/cli.py:1549`, `:1561-1565`, `:1580-1585`; `src/fabrik/orchestrator/deployer_ssh.py:123-145` (+ `_host_env`, `list_compose_projects`) |
| D4 | `fabrik projects --sync` | **REBASE.** `--sync` runs the project scanner (`scripts/sync_projects.py`, the same subprocess `fabrik scan` runs at `cli.py:1669-1673`) before listing — which is what `docs/reference/fabrik-cli-reference.md:354` already says it does; help text "Re-scan /opt and merge the deploy state before listing". `Project.coolify_uuid`/`coolify_name` and their `to_dict`/`from_dict` lines are removed — no writer remains; a `data/projects.yaml` row still carrying the keys is ignored on load (`from_dict` reads named keys only, `registry.py:44-55`). MIRROR: `registry.update(name, coolify_uuid=…)` had one caller (`cli.py:1641`), gone with it. | `src/fabrik/cli.py:1618`, `:1624-1648`; `src/fabrik/registry.py:23-24`, `:31-34`, `:49-50` |
| D5 | hub `/health` | **RETIRE the check, add nothing.** `_check_coolify_sync`, the `CoolifyClient` import and the `coolify` key leave; `/health` aggregates `{"dns": …}` alone and keeps its 200/503 rule. No ssh-reachability probe replaces it: a liveness endpoint stays shallow so a dependency outage never cascades into restarts (cr-43, cr-44), and the hub image has no consumer that could use a readiness signal (§ Personas). `compose.yaml:13-16` drops the four `COOLIFY_*` lines (two are `:?`-required, so the hub image could not even start without a dead token). Module docstring `health_app.py:1-5` says "DNS manager". | `src/fabrik/health_app.py:3-4`, `:17`, `:55-67`, `:84-93`; `compose.yaml:13-16` |
| D6 | `fabrik export` / `import` | **RETIRE the Coolify section.** `_collect_coolify` and the `coolify_client` parameter of `export_bundle`/`import_bundle` go; the tarball has no `coolify/` tree; the manifest's `coolify` count and the README's Coolify line go; `cli.py:2886`'s docstring stops promising Coolify exports. `import_bundle`'s prefix index drops `coolify/` from `prefixes` and counts a legacy bundle's `coolify/*` members under `plan["ignored_legacy"]` so an old bundle imports with the count visible, never a silent drop. The real-run comment `:655-660` loses step 1 ("Recreate Coolify Projects"). MIRROR: `export_bundle(coolify_client=…)` at 9 test call sites and the `_fake_coolify_client` fixture are removed with the parameter. | `src/fabrik/portability.py:14-16` (tree docstring), `:226-254`, `:493`, `:506`, `:524`, `:539`, `:558-559`, `:588`, `:602`, `:645`, `:655-660`; `src/fabrik/cli.py:2883-2889` |
| D7 | `RollbackManager` | **RETIRE the branch.** The `coolify_client` ctor argument, the lazy `coolify_client` property and `_rollback_coolify` go; `rt == "coolify"` falls to the existing `else: logger.warning("Unknown resource type")` — no live path records a `coolify` resource (the SSH deployer records at `deployer_ssh.py:225` only; `grep -rn 'add_resource("coolify"' src/` → 0 in 1 file set). The comment at `:267` ("contrast with `_rollback_coolify`/`_rollback_dns`") names `_rollback_dns` alone. MIRROR: `RollbackManager(coolify_client=…)` — callers in `src/`: 0; in tests: `test_rollback.py:16`, `:45`, `:61`, `:88`, `:150`, `test_e2e_rollback.py:165`. | `src/fabrik/orchestrator/rollback.py:20-43`, `:142-145`, `:170-183`, `:267` |
| D8 | the Coolify modules | **DELETE** `src/fabrik/drivers/coolify.py` (934), `src/fabrik/orchestrator/deployer_coolify.py` (845), `src/fabrik/drivers/compose_updater.py` (451), `src/fabrik/orchestrator/coolify_alias.py`, `src/fabrik/deploy.py`, and their tests `tests/drivers/test_coolify.py` (2), `tests/orchestrator/test_deployer.py` (19), `tests/drivers/test_compose_updater.py` (20), `tests/test_coolify_alias.py` (12). `drivers/__init__.py` loses the import, the `__all__` entry and the docstring line; `config.py:104-109`'s commented readers and `.env.example:14-28`, `:305-312` go (W-00485146's code half; its `.env.example` CAPTCHA row is not this spec's). `drivers/postgres.py:1835`'s docstring sentence names the pattern without the module. `test_infrastructure.py:366`, `:476` drop the `patch("fabrik.drivers.coolify.CoolifyClient")` (the patch target would no longer import). | the files named; `src/fabrik/drivers/__init__.py:5`, `:12`, `:22`; `src/fabrik/config.py:104-109`; `.env.example:14-28`, `:305-312`; `src/fabrik/drivers/postgres.py:1835`; `tests/orchestrator/test_infrastructure.py:366`, `:476` |
| D9 | state + context keys | **KEEP the names, fix the words.** `state.py`'s schema docstring and `save()` docstring describe `coolify_uuid` as "the compose app name (= `/opt/<name>`), kept under its historical key" and drop `coolify` from the `ResourceRecord` type list (`:53`); `context.py:15`'s comment lists `"compose", "dns", "monitor"`. `sync_projects.py:242-246` keeps its `fabrik-<name>` fallback (state files written under either id form exist). | `src/fabrik/state.py:26-27`, `:53`, `:165-168`; `src/fabrik/orchestrator/context.py:15`, `:45-49` |
| D10 | docs and wording | every W21 line brought current; `cli.py:1124` ("- Coolify application") and `:1129` leave the destroy preview; `:891` (`--partial` help) says "no DNS removal, no file cleanup"; `:2402` "pre-deploy sequence", `:2473` "ready for deployment"; `audit-registrars`' hint `:1477` keeps naming `reconcile-all`, which is now true. `docs/CAPABILITIES.md` is regenerated, never hand-edited. `docs/development/plans/archived/2026-05-28-ssh-deployer.md § Known Broken` is a frozen archive and is NOT edited; the live docs that point at it (`CONFIGURATION.md:54`, `:663`) stop calling the verbs broken. | § Documentation landing sites |

Ordering (cr-21): one plan, phases by blast radius — (A) the three rebases + their graders (D2–D4, the deployer helpers);
(B) the retirements inside kept files (D1, D5, D6, D7, D9) with their test edits; (C) the deletions (D8) in ONE commit
with every remaining importer and test edit, so no commit leaves an import that cannot resolve; (D) docs (D10) and the
capability regeneration. A commit never deletes a module whose importer is deleted in a later commit.

## Contract deltas

No data-contract or ui-design freeze changes (the hub has neither). The CLI contract changes are: `fabrik apply`
loses `--legacy` and `--use-orchestrator`; `fabrik projects --sync` means "re-scan"; `fabrik status` prints the
last-apply and live-container sections; `fabrik reconcile-all` no longer exits 1 on a probe failure. The Python
contract changes are: `fabrik.drivers` no longer exports `CoolifyClient`; `export_bundle`/`import_bundle` lose
`coolify_client`; `RollbackManager.__init__` loses `coolify_client`; `Project` loses two fields. Each is a MIRROR row
in the table above with its measured callers.

## Rejected alternatives

- **A1 — retire `status`/`reconcile-all`/`projects --sync` outright.** Each has a live question only it answers (§ Personas
  step budgets); deleting them moves the operator back to five manual steps per spec.
- **A2 — a `deprecated="…"` stub per retired path for one release** (cr-7, cr-9 convention). Nothing here is a retired
  VERB: the three verbs are rebased, and the retired path is an option whose absence click already reports with the
  option's name. A stub would also have to raise itself (cr-2, cr-6) — more code to carry for a signpost one operator
  does not need (cr-11).
- **B1 — `reconcile-all` reads the state records as the deployed set.** The store is gitignored and per-checkout
  (`ls -p /opt/fabrik/.fabrik/state | grep -v / | wc -l` → 9 in the main checkout, 5 in this worktree; `ls specs/services/*.yaml | wc -l`
  → 69): a service applied before state tracking, from another checkout, or whose record was lost would be skipped
  silently — a drift tool with a silent blind spot (the judge panel's seats 2 and 3 both ranked it last for this). The record is the answer to *what did the last apply
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
surface; the new helpers (`list_compose_projects`, `_parse_compose_ps`) are reached only by the two verbs, and a host
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
- `find_existing` keeps its two-call shape (`test -f`, then `ps`) so `_deploy_inner`'s `existing` check behaves as today;
  the `-a` only widens the `status` text.
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
| E1 | `docker compose ps --format json` | JSON Lines since v2.21.0 (2023-08-30); nine emitted keys; `-a` for stopped; no exit-code signal for health | https://github.com/docker/compose/issues/10958 · https://docs.docker.com/reference/cli/docker/compose/ps/ (cr-22, cr-23, cr-25, cr-32, cr-33, cr-34, cr-35) |
| E2 | `docker compose ls -a --format json` | a JSON array of `{Name, Status, ConfigFiles}`; `-a` includes stopped projects; host-wide regardless of cwd | https://docs.docker.com/reference/cli/docker/compose/ls/ · https://raw.githubusercontent.com/docker/compose/main/cmd/compose/list.go (cr-28, cr-36, cr-37) |
| E3 | click 8.3.1 (the venv, executed: `click.Command.__init__` has `hidden` and `deprecated`; a `deprecated=True, hidden=True` command printed its warning to stderr and ran) | `deprecated=` warns then runs the callback; no built-in non-zero stub | https://click.palletsprojects.com/en/stable/api/ · https://raw.githubusercontent.com/pallets/click/8.3.1/src/click/core.py (cr-1, cr-2, cr-6, cr-42) |
| E4 | the deprecation convention | PEP 387's window and its "no one could reasonably be depending on" exception; the SWE book's "code is a liability" and "let it stop functioning when some external event causes it to break" | https://peps.python.org/pep-0387/ · https://abseil.io/resources/swe-book/html/ch15.html (cr-12, cr-13, cr-16, cr-29, cr-45) |
| E5 | health-endpoint practice | shallow liveness, deep checks only for readiness, "degraded rather than unhealthy" | https://learn.microsoft.com/en-us/azure/architecture/patterns/health-endpoint-monitoring (cr-43) |

1a internal facts were executed, not cited: the state records read (10 files, keys and `uuid` values listed in W14), the
importer census (`command grep -rn "CoolifyClient\|deployer_coolify\|_rollback_coolify\|_collect_coolify" src/fabrik`
→ 32 lines in 9 files, all in W1–W13), the test counts (W20, `grep -c "def test_"` per file), the fleet Compose version
(W19), and click's behaviour (E3, run in `.venv`). Fetched 2026-10-14 by four `fabrik-researcher` seats (WebSearch +
WebFetch + exa + firecrawl; the ledger names the arm per row).

## Shape / infra implications

None: no `specs/services/*.yaml` changes, no registrar, no `shape:` flag, no port, no compose service on any host.

## Documentation landing sites

- `docs/reference/fabrik-cli-reference.md` — `:268-274` (status: add the two sections), `:346-354` (already correct;
  confirm), `:463` (`reconcile-all` → `deployer_ssh.list_compose_projects` + `refresh_infrastructure`), `:466`
  (`status` → `cli.py` + `deployer_ssh.find_existing`).
- `docs/DEPLOYMENT_ARCHITECTURE.md` — `:103` (legacy file sentence removed), `:137` (row removed), `:166` (monitor.py row
  — it is not used by `status`/`logs`: 0 imports in `cli.py`; reworded), `:167` (health_app row loses the Coolify note).
- `docs/reference/architecture.md:70`, `:85`, `:184`, `:207`, `:219`, `:233` — rows and tree lines removed or reworded.
- `docs/reference/modules/drivers.md:5-10`, `:28`, `:40`, `:62-69`, `:315` — banner, two rows, the CoolifyClient section
  and the test-file list.
- `docs/SERVICES.md:64-67`; `docs/CONFIGURATION.md:50-57`, `:659-666`; `docs/reference/health-monitoring.md:101`;
  `docs/operations/deployment.md:489-490` (the commented `reconcile-all` becomes a live command);
  `docs/TROUBLESHOOTING.md:186`, `:202` (the retired file is now "removed at <commit>"); `agents-fabrik.md:102`, `:404`,
  `:409`; `README.md:56`, `:559`, `:704`; `INDEX.md:261`, `:1704`, `:1711` (and the rows for the deleted files);
  `docs/FEATURES.md:313`, `:686`.
- `docs/CAPABILITIES.md` — regenerated.
- `CHANGELOG.md` — one `### Changed` entry; `docs/DECISIONS.md` — the approval row (reversible) naming the deletion
  commit; `docs/STRATEGIC_BACKLOG.md`/work store — C2 (the hub image's own retirement) boarded.
- No new reference doc: the verbs are documented where they are documented today.

## Validation

Behaviour graders, red-first in a throwaway worktree (the root conftest pins the checkout src):

- V1 `status` parses a JSON-Lines `ps` fixture (running+healthy, exited+`""`, running+`"none"`) into three rows and the
  array form of the same fixture into the same rows; a record-less spec prints the "never applied" line; a `RuntimeError`
  from ssh prints the "could not reach" line and exits 0.
- V2 `find_existing`'s second command contains `docker compose ps -a --format json` (string pin on the recorded ssh call).
- V3 `reconcile-all` with a fake `ls` returning `[{"Name":"a",…},{"Name":"other","ConfigFiles":"/opt/b/compose.yaml"}]`
  reconciles specs `a` and `b`, skips `c` with the "no compose project on vps1" row, and with a second spec on `vps2`
  whose `ls` raises prints `host-unreachable` for it while `a`/`b` still reconcile; the `ls` runs once per host (call count).
- V4 `projects --sync` invokes the scanner subprocess once (recorded argv) and never imports `fabrik.drivers.coolify`
  (the module no longer exists — an `importlib.util.find_spec` assertion).
- V5 `/health`: dns healthy → 200 with `checks == {"dns": …}` and no `coolify` key; dns failing → 503 `degraded`.
- V6 `export` tarball has no member under `coolify/`; the manifest has no `coolify` count; `import` (dry run) of a
  hand-built legacy bundle with two `coolify/*.json` members reports `ignored_legacy == 2`.
- V7 a `DeploymentContext` carrying `add_resource("coolify", "x")` rolls back with a warning and no exception.
- V8 the census: `command grep -rln "drivers.coolify\|CoolifyClient\|deployer_coolify\|compose_updater\|coolify_alias\|deploy_to_coolify" src scripts tests templates` = 0 files (denominator: every tracked `*.py`, `git ls-files -- '*.py' | wc -l`), stated in the receipt; `vulture src/fabrik --min-confidence 80` shows no new item against the pre-delta baseline (cr-17); `ruff` F401 clean (cr-18).
- V9 the touched test files run by hand with their totals: `test_health_app`, `test_portability`, `test_rollback`,
  `test_e2e_rollback`, `test_infrastructure`, `test_registry`, `test_state`, `test_sync_projects_state`,
  `test_deployer_ssh`, plus the new `tests/test_cli_status_live.py` and `tests/test_reconcile_all_deployed_set.py`.
- V10 `python scripts/final_gate.py --check --json` green; `scripts/generate_capability_index.py` run and its diff committed.

## Open / blocking unknowns

- U1 (open, handled) — whether Compose 2.40.3 ever emits `"Health":"none"` (cr-35): the parser treats `""` and `"none"`
  alike, so the answer changes nothing; the plan's R1 read on vps1 records which one the fleet prints.
- U2 (open, harmless) — the `ls` `Status` string format (cr-38): never parsed.
- U3 (resolved by design) — a compose project whose `Name` differs from `spec.id`: the `ConfigFiles` directory match
  covers it; R1 lists the fleet's project names beside their config paths so a third form, if one exists, is seen before
  the verb ships.
- U4 (plan-time measurement) — `find_existing`'s `status` text has one consumer in `_deploy_inner`'s `existing` handling
  (`deployer_ssh.py:178-234`); the plan reads it before adding `-a` and asserts callers use truthiness/`path` only.
- Residual assumption: no caller outside the hub imports the deleted modules. Measured 2026-10-14: `command grep -rl
  --include=*.py "from fabrik.drivers\|import fabrik.drivers\|fabrik\.deploy import\|fabrik.drivers.coolify" /opt` (every
  `/opt` directory but the hub, `.venv`, `node_modules` and `.git` skipped) → 1 file of 59 repos, `ai-model-catalog/engine/tests/test_rank_task_subagents.py`,
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
| I20 | the hub image itself (`Dockerfile`, `compose.yaml`, `health_app.py`) has no deployer | OUT-OF-SCOPE — boarded as C2 at close | C2 |
| I21 | *"No D-row in the hub records the Coolify retirement itself"* (brief) | IN — the approval row records it | § Decisions taken |
| I22 | *"Autonomy (D-558) … design approval is the panel's (D-613) at /fabrik-spec-review"*; Pool OFF (D-181); seats never ssh | IN | this run |
