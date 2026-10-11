# Plan — the owner DSN leaves the app containers' environment (W-4e74ea9d)

Status: DRAFT
Profile: small
**Owner:** fleet
**Surface:** `git rev-parse HEAD` = f333de437 at authoring; `src/fabrik/orchestrator/deployer_ssh.py` 1,273 lines,
`src/fabrik/scaffold.py` 7,923 lines (the touched regions are cited by line below)

Spec: `docs/superpowers/specs/2026-10-12-owner-dsn-split-design.md` (DRAFT at f333de437; `Size: small`, `Profile: delta` —
`/fabrik-plan-review` grades its sections together with this plan and flips both; the approval row is minted there, D-613).
Source: infra's backlog row of 2026-09-24 from the audit-log-everywhere work (D-385, D-393, D-410) → work item W-4e74ea9d.
Estimated diff: ≈130 code lines in FOUR code files, tests excluded — `deployer_ssh.py` ≈75 (`OWNER_ENV_KEYS`, `_split_env`,
`_read_env_file(filename=)`, the merged `read_env`, the split `inject_env`, `_build_env_files` + the `_build_env_content`
wrapper, the four deploy paths' second write, `_write_file_to_vps_path(mode=)`), `spec_loader.py` + `spec_generator.py` ≈10
(`CompanionService.owner_env`), `templates/_partials/_companion_service.yaml.j2` ≈6, `scaffold.py` ≈25 (the committed
companion's env_file block, two schema headers, the `.env.example` block). Tests ≈170 lines in two EXISTING files.

## What this plan is

Three inline phases the orchestrator codes itself in the fleet worktree; no coder is dispatched:

- **A — the deployer**: the owner key set, the second file `.env.owner` (written first, root-owned 0600), the merged
  `read_env`, the split `inject_env`, the automatic logged move out of `.env` — with their graders and the fallout
  updates to the tests that pin the one-file shape (spec § The delta 1-3, 6).
- **B — the scaffold and the docs**: `CompanionService.owner_env`, the long-syntax `env_file` block on the audit-jobs
  companion only, the schema headers and `.env.example` text, every doc sentence that says "both DSNs live in `.env`"
  (spec § The delta 4-5, § Touchpoints, § Documentation landing sites).
- **C — the live check and Finish**: the one read-only `stat` on vps1 (spec R1), the whole-plan `/fabrik-review`, the gate,
  the receipt.

Per phase: `/fabrik-review-scoped` on that phase's surface. At Finish: one heavy `/fabrik-review` (the `/fabrik-execute-plan`
D7 floor) and one receipt.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § Intake Inventory I1–I11 (10 IN, 1 CHANGED — the brief's per-project gate replaced by the measured automatic move) | IN as dispositioned there | Phases A and B, per the spec rows |
| I2 | *"Plan it as `Profile: small`"* (this run's brief) | IN | this header |
| I3 | the brief's mechanism list — `OWNER_ENV_KEYS`, merged `read_env`, split `inject_env`, `_build_owner_env_content`, `_read_env_file` `filename`, `_write_file_to_vps_path` `mode`, `CompanionService.owner_env`, the two emitters, the schema headers and `.env.example`, the docs | IN | Phase A (deployer), Phase B (scaffold + docs); `_build_owner_env_content` becomes `_build_env_files` returning both halves (Phase A Interfaces) |
| I4 | *"Red-first graders per the spec's § Validation (seven), measured in a throwaway worktree"* | IN | Phase A steps 1-4 (G1–G6), Phase B steps 1-2 (G7–G9); red-on-revert in a throwaway worktree, Phase A step 5 |
| I5 | *"Plan phase 1 owns the one live read-only check: `stat` of one project's `.env` on vps1 … if still unreachable record it as an assumption"* | IN | Phase C step 1 (spec R1) |
| I6 | *"never touch a VPS beyond that one stat, never a database, never another repo"* | IN | § Global Constraints |
| I7 | *"infra is re-running merge 01M4PKEAJY … say so in the close rather than filing a second request"* | IN | Phase C step 4 |
| I8 | Grounding finding (this run, Evidence Phase A): 6 call sites write `.env`; `tests/orchestrator/test_deployer_ssh.py` pins the LAST write and exact ssh call counts; `tests/orchestrator/test_deployer_git_sha.py:81-85` asserts `filename == ".env"` | IN | Phase A steps 3-4 (the fallout list), § Global Constraints (owner file written FIRST) |
| I9 | Grounding finding: `tests/test_scaffold_audit_log.py:279`, `:530`, `:558` pin the companion's `env_file` (`== [".env"]` at :530); `tests/test_scaffold_saas_backend.py:170` pins the saas services' `[".env"]` and must keep passing | IN | Phase B step 2 (G7–G9) |

## What we already agreed (citations, not restatement)

- Goal, personas, lifecycle: `spec § Goal`, `spec § Personas`, `spec § Lifecycle`; why: `spec § Why this exists`.
- Measured behaviour and every anchor: `spec § What exists today`; the mechanism and its invariants 1-6: `spec § The delta`;
  the shapes it can break: `spec § The delta` (MIRROR); contract deltas none: `spec § Contract deltas`.
- Chosen approach (a second env file loaded only by the services that declare it) and the rejected ones (file secrets,
  passfile, env override, a per-project flag, hub-run migrations): `spec § Rejected alternatives`, `spec § Decisions taken`.
  The approval row is minted by `/fabrik-plan-review` at its gate (a `Size: small` spec is approved there, not here).
- External facts: `spec § External dependencies` → `docs/reference/research/2026-10-12-owner-dsn-split-ledger.md` rows ods-21
  (list order, later wins), ods-24/25 (`required: false`, Compose ≥ 2.24.0; fleet measured 2.40.3 at
  `src/fabrik/orchestrator/deployer_ssh.py:1217`), ods-6 (file secrets ignore mode/uid).
- Residual unknowns R1–R3: `spec § Open / blocking unknowns` — R1 is Phase C step 1; R2 and R3 are resolved there.

## Global Constraints (every phase inherits these)

- **Hub-side surface only.** `src/fabrik/orchestrator/deployer_ssh.py`, `src/fabrik/spec_loader.py`,
  `src/fabrik/spec_generator.py`, `src/fabrik/scaffold.py` and `templates/_partials/` are the hub's own code, none is a
  governance-sync trigger (`.pre-commit-config.yaml`'s `governance-sync` filter names `commands/_sources/`,
  `scripts/enforcement/`, `templates/governance/`, `.windsurf/rules/`, `.claude/hooks/` — read, not recalled, this run);
  `templates/scaffold/docs/*_TEMPLATE.md` are scaffold payload (fleet's beat). No VPS is touched beyond Phase C's one
  read-only `stat`; no database; no other repo.
- **The owner file is written FIRST, then `.env`, then the restart** — in `inject_env` and in every deploy path — so the
  owner password is on disk before anything below it can fail (the T04 invariant, `infrastructure.py:872-878`), and so
  the tests that read the LAST `_write_file_to_vps` call still see `.env` (I8). The owner file is written only when the
  owner half is non-empty; a deploy with no owner key writes exactly what it writes today.
- **Both files root-owned 0600**: `_write_file_to_vps_path` keeps its `scp` → `sudo mv` → `sudo chown root:root` path
  (`deployer_ssh.py:962-1000`) and gains `mode: str | None = None`, appending `&& sudo chmod {mode} {dest}` when given;
  the owner file passes `"0600"`, `.env` passes nothing (its mode stays the temp file's — Evidence probe 3: `0o600`).
- **The merged view is the API**: `read_env` returns `.env` overlaid by `.env.owner`; every reader in
  `infrastructure.py` (`:1094-1096`, `:1114`, `:1126`, `:1187-1191`) is unchanged.
- **One key set**: `OWNER_ENV_KEYS: tuple[str, ...] = ("DATABASE_URL_OWNER",)` at module level in `deployer_ssh.py`; a
  key joins the owner file by membership there and nowhere else (spec § The delta 1).
- **Compose shape**: the long syntax is emitted only under `c.owner_env` / the committed companion; app services keep
  `env_file:\n  - .env` byte-for-byte (`tests/test_scaffold_saas_backend.py:170` keeps passing).
  `_validate_compose` never reads `env_file` (`deployer_ssh.py:1009-1163`, 0 hits — Evidence probe 2).
- **Stdlib only**; no dependency file is touched (`core/10-python.md:30`); no new env var, port or service.
- **12-Factor on this surface**: III — two files, both granular env, no grouped set; XII — the one-off and the scheduled
  consumer get the owner DSN in the deployed environment, never from a laptop (`core/30-ops.md:437`); the rest not engaged.
- Tests: one per behaviour, watched-fail-first (`core/45-testing-strategy.md:20`, `:22`); the deployer graders mock
  `_write_file_to_vps`/`_write_file_to_vps_path` and `fabrik.drivers.ssh.ssh` exactly as `tests/orchestrator/test_deployer_ssh.py`
  does (`:456`, `:972`), asserting on the `(path, filename, content)` tuples and the ssh command strings; the scaffold
  graders render through `TemplateRenderer` and `create_project` as `tests/test_scaffold_audit_log.py` does. Every grader is
  seen red — against today's code, or by the named mutant in Phase A step 5. Red-on-revert runs in a throwaway worktree
  (`git worktree add --detach <scratch>/probe HEAD`), never in the shared checkout; the root conftest pins the checkout's
  `src`, so the probe runs its OWN `tests/` from inside the probe tree.
- Seats never mutate git state (read-only git only); never read `~/.claude*` or any `.env`; never `uv` or `pip`; Python is
  `/opt/fabrik/.venv/bin/python`; seat scratch paths are absolute; a probe copies the pinned module under scratch.
- **Execution discipline (native seats only, D-181):** every phase ends with `/fabrik-review-scoped` on its surface (the
  floor of three native seats, stamped with `command_run.py dispatch`), not handing on until its closing pass confirms
  zero defects. The Finish `/fabrik-review` partitions the whole-plan diff by file into a Sonnet and a Haiku finder per
  slice (D-344), the orchestrator executing every refutation. Within a phase the steps are sequential.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (MATCHED) | no deps-file edit; the DSN arrives complete from env | `core/10-python.md:30`, `:133` |
| `.windsurf/rules/core/35-security-auth.md` (FLOOR) | no fallback for a DSN; `.env` edits are backed up first | `core/35-security-auth.md:273`, `:307` |
| `.windsurf/rules/core/30-ops.md` (FLOOR) | companions share image + env; first-boot DSN ordering; admin processes in the deployed env | `core/30-ops.md:161`, `:236`, `:437` |
| `.windsurf/rules/core/25-data-postgres.md` (FLOOR) | the three env files' roles; `.env` is the active config | `core/25-data-postgres.md:43-45` |
| `.windsurf/rules/core/45-testing-strategy.md` (judgment read — the graders) | one test per behaviour; watched-fail-first | `core/45-testing-strategy.md:20`, `:22` |
| `.windsurf/rules/core/40-documentation.md` (judgment read — Phase B docs) | Doc Sync in the same change | `core/40-documentation.md:242` |
| `ai/50-agentic.md` (MATCHED by the `**/orchestrator/**` glob) | agent loops — not engaged by the deployer | read, no row |
| `agents-fabrik.md` | the hub is the deploy control plane; projects never self-deploy | `agents-fabrik.md:80-86` |
| `docs/operations/fabrik-lifecycle.md` | the app-role cutover/rollback table the merged view must keep true | `fabrik-lifecycle.md:203-205`, `:217-220`, `:253-255` |
| `fabrik-lib` | none covers deploy-time env delivery — BUILD in the hub | `spec § fabrik-lib verdict` |
| `specs/services/*.yaml` `shape:` | not engaged: no flag changes (spec § Contract deltas) | — |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Quote | Source | Rule |
|---|---|---|
| "Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it." | .windsurf/rules/core/10-python.md:30 | Deps |
| "apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env." | .windsurf/rules/core/10-python.md:133 | Config |
| "DSNs and secrets get NO fallback — a missing value fails LOUDLY at boot" | .windsurf/rules/core/35-security-auth.md:273 | No default |
| "Before editing `.env`, `*.key`, `*.pem`, files under `secrets/`, or `.ssh/`:" | .windsurf/rules/core/35-security-auth.md:307 | Backup |
| "First-boot DSN ordering. The registrar injects `DATABASE_URL` POST-deploy, so a container that needs a real DSN at first boot crashes before it arrives." | .windsurf/rules/core/30-ops.md:236 | `required: false` |
| "migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes." | .windsurf/rules/core/30-ops.md:437 | XII |
| "every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one**" | .windsurf/rules/core/45-testing-strategy.md:20 | Behaviour Contract |
| "**Watched-fail-first** (for tests this change adds or modifies" | .windsurf/rules/core/45-testing-strategy.md:22 | Red first |

## Phase A — the deployer: the owner file, the merged read, the split write

Appetite: 120

**Interfaces — Produces** (all in `src/fabrik/orchestrator/deployer_ssh.py`; `spec § The delta` 1-3, 6):
- `OWNER_ENV_KEYS: tuple[str, ...] = ("DATABASE_URL_OWNER",)` — module constant beside `_parse_env` (`:836`).
- `OWNER_ENV_FILE = ".env.owner"` — module constant; the one place the filename is spelled.
- `_split_env(env: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]` — `(app, owner)` by membership in
  `OWNER_ENV_KEYS`; pure, no I/O.
- `_read_env_file(path: str, _ssh: Any, filename: str = ".env") -> dict[str, str]` — the existing fail-closed reader
  (`:898-920`) with the filename parameterised; `f"{path}/{filename}"` replaces the hard-coded `.env` at `:906`; every
  existing caller (`:265`, `:326`, `:723`, `:950`) keeps its meaning.
- `_read_env_merged(path: str, _ssh: Any) -> dict[str, str]` — `_read_env_file(path, _ssh)` overlaid by
  `_read_env_file(path, _ssh, OWNER_ENV_FILE)`; the owner file wins on a shared key (it is the owner's copy).
- `SSHDeployer.read_env(ctx)` (`:308-326`) returns `_read_env_merged(...)` inside `_target_vps_env` — the merged view the
  app-role step reads (`infrastructure.py:1094-1096`).
- `SSHDeployer.inject_env(ctx, env_vars)` (`:328-364`): `merged = self.read_env(ctx); merged.update(env_vars); app, owner =
  _split_env(merged)`; when `owner` is non-empty, `_write_file_to_vps(name, OWNER_ENV_FILE, _format_env(owner), mode="0600")`
  FIRST, then `_write_file_to_vps(name, ".env", _format_env(app))`, then `_compose_up` — one restart. A key that was in
  `.env` and is now in the owner file is logged once: `env: moved %d owner key(s) out of .env into %s for %s`.
- `_build_env_files(ctx, name, existing, app_path=None, *, overrides=None) -> tuple[str, str | None]` — the current
  `_build_env_content` body (`:693-760`) with the existing read through `_read_env_merged` and the result split: returns
  `(_format_env(app), _format_env(owner) or None)`. `_build_env_content(...)` stays as the wrapper returning the first
  element, so its tests (`tests/orchestrator/test_deployer_ssh.py:1089-1354`) keep their call shape.
- The four deploy paths (`_deploy_template` `:519-524`, `_deploy_git` `:604-607`, `_deploy_docker` `:645-649`,
  `_deploy_local` `:685-686`) call `_build_env_files`, write the owner file first when present (`_write_file_to_vps_path`
  for `_deploy_local`, whose `path` may lie outside `/opt`), then `.env`.
- `_write_file_to_vps(name, filename, content, mode=None)` / `_write_file_to_vps_path(path, filename, content, mode=None)`
  (`:957-1000`): `mode` appends `&& sudo chmod {mode} {dest}` to the command at `:997`; `None` leaves today's string
  byte-identical (`tests/orchestrator/test_deployer_ssh.py:1633-1635` asserts it).
- `_persist_git_sha` (`:943-953`) is unchanged: `GIT_SHA` is an app key and it reads/writes `.env` alone.

Steps:
1. **Highest-risk test first — G1 (the split write).** In `tests/orchestrator/test_deployer_ssh.py`, beside the inject_env
   tests (`:614-636`): `SSHDeployer().inject_env(ctx, {"DATABASE_URL": a, "DATABASE_URL_OWNER": o})` with `_read_env_file`
   patched to return `{}` for both files → `mock_write.call_args_list` is `[(name, ".env.owner", <o only>, mode "0600"),
   (name, ".env", <a only>)]` in that order, `_parse_env` of each content holding exactly those keys, and exactly one
   `docker compose up` ssh call. Run it: RED on today's code (one write, both keys in `.env`).
2. Implement the Interfaces above in `deployer_ssh.py`; run G1 → GREEN. `ruff check` + `ruff format --check` on the file.
3. Graders G2–G6, each written, watched red where today's code allows (G2, G3, G6 are red today; G4 and G5 red by the
   step-5 mutant), then green:
   - G2 (the merged view): `_read_env_file` patched to return `{"DATABASE_URL": a}` for `.env` and
     `{"DATABASE_URL_OWNER": o}` for `.env.owner` → `read_env(ctx) == {"DATABASE_URL": a, "DATABASE_URL_OWNER": o}`; a
     stale `DATABASE_URL_OWNER` left in `.env` loses to the owner file's value.
   - G3 (the automatic move): `_build_env_files` over an existing `.env` carrying `DATABASE_URL_OWNER` and no owner file →
     the app half lacks the key, the owner half carries it, and `caplog` holds `moved 1 owner key(s)`; a second build over
     the result is a no-op (owner half equal, no log line).
   - G4 (no owner key, no owner file): `inject_env(ctx, {"K": "v"})` with both reads `{}` → exactly ONE write, of `.env`,
     and the ssh call count is today's plus the owner-file probe (the existing `== 2` at `:627` becomes the new exact
     count, asserted with the reason in the message).
   - G5 (the chmod): `_write_file_to_vps_path("/opt/x", ".env.owner", "K=v\n", mode="0600")` → the ssh command string ends
     `&& sudo chown root:root /opt/x/.env.owner && sudo chmod 0600 /opt/x/.env.owner`; without `mode` the string equals
     today's (`:1633-1635` keeps passing).
   - G6 (the fail-closed reader keeps its contract on the second file): `_read_env_file(path, ssh, ".env.owner")` with a
     probe answering `absent` → `{}`; a refused `sudo` → `DeployError` naming `.env.owner`.
4. **Fallout — the tests that pin the one-file shape**, each updated with the reason in its assertion message, never
   loosened: `tests/orchestrator/test_deployer_ssh.py` — the `call_args[0][2]` reads of the last write (`:466`, `:559`,
   `:574`, `:626`, `:635`) still see `.env` (owner first), and change only where the fixture now carries an owner key; the
   exact ssh counts (`:431`, `:627`) gain the owner-file probe; `:946-948` (`".env"` in the written names) unchanged;
   `_write_file_to_vps_path` asserts (`:982` `assert_called_once`, `:1014-1015` the `("/srv/my-app", ".env")` tuple, `:1034`
   `assert_not_called`) hold because those fixtures carry no owner key; `:1543-1567`'s `fake_write` raising on the first
   call now raises on the owner write when the fixture has one — assert the message names the file.
   `tests/orchestrator/test_deployer_git_sha.py:81-85` — `_Vps.write` learns `.env.owner` (records it under its own key)
   instead of asserting `filename == ".env"`. `tests/test_app_role_provision.py:32-53` — the fake deployer's `read_env` /
   `inject_env` are the merged-view API and need no change; its `:170` ordering assertion stays.
   Run: `/opt/fabrik/.venv/bin/python -m pytest tests/orchestrator/test_deployer_ssh.py tests/orchestrator/test_deployer_git_sha.py
   tests/test_app_role_provision.py tests/orchestrator/test_infrastructure.py tests/orchestrator/test_spoke_dsn_mesh.py
   tests/orchestrator/test_plan1_defects.py -q -p no:cacheprovider` → all pass.
5. **Phase gate**: red-on-revert in a throwaway worktree, one mutant per grader today's code does not already red —
   G4 (the owner file written even when empty), G5 (`mode` ignored) → each named test red, then the worktree removed.
   `/opt/fabrik/.venv/bin/python -m mypy src/fabrik/orchestrator/deployer_ssh.py --ignore-missing-imports` → no new error
   against the pre-phase count. `python scripts/enforcement/check_doc_sync.py` → green (no doc trigger in this phase
   beyond CHANGELOG).
6. **`/fabrik-review-scoped`** on Phase A's surface — BLOCKING, to its closing pass confirming zero defects.
7. Commit Phase A (explicit pathspecs; `CHANGELOG.md` via the private-index recipe; trailers `Agent-Role: primary`,
   `Agent-Phase: A`), push.

**Behavior Contract (Phase A):**
- **Given** a registrar injecting `DATABASE_URL` and `DATABASE_URL_OWNER` in one call, **When** `inject_env` runs, **Then** the owner key is written to `.env.owner` first, the app key to `.env`, and the stack restarts once (spec § The delta 1-2)
- **Given** an existing `.env` that still carries `DATABASE_URL_OWNER`, **When** the next deploy or injection builds the files, **Then** the key moves to `.env.owner`, the move is logged once, and a second build is a no-op (spec § The delta 3)
- **Given** both files on the VPS, **When** the app-role step calls `read_env`, **Then** it sees the merged view with the owner file winning on a shared key (spec § The delta 2)
- **Given** an injection carrying no owner key and no owner file on disk, **When** `inject_env` runs, **Then** `.env` is the only file written (spec § The delta 2)
- **Given** the owner file write, **When** the deployer issues its command, **Then** the file is `chown root:root` and `chmod 0600`, and a write without `mode` issues today's command unchanged (spec § The delta 6)
- **Given** an absent `.env.owner`, **When** the reader probes it, **Then** it returns `{}`; **Given** a refused read, **Then** `DeployError` names the file (spec § What exists today — the fail-closed reader)

## Phase B — the scaffold and the docs

Appetite: 90

**Interfaces — Consumes** (Phase A): `OWNER_ENV_FILE` is the filename the compose block names; the merged view.
**Produces:**
- `spec_loader.CompanionService.owner_env: bool = False` (`src/fabrik/spec_loader.py:818-856`, after `env_overrides` at
  `:852-855`; `extra: forbid` stays).
- `spec_generator.audit_jobs_companion` (`src/fabrik/spec_generator.py:148-165`) constructs with `owner_env=True`.
- `templates/_partials/_companion_service.yaml.j2:17-18` — under `{% if c.owner_env %}` the long syntax (`- .env` then
  `- path: .env.owner` / `required: false`), else today's two lines; the header comment (`:3-5`) says where the owner DSN
  lives now.
- `src/fabrik/scaffold.py::_append_audit_jobs_service` (`:4159-4210`, the env_file lines `:4190-4191`) emits the same
  long-syntax block (the committed compose is the git-sourced deploy's truth).
- `scaffold.py:2217-2219` and `:3595-3597` (the schema headers) read: `set -a; . ./.env; . ./.env.owner; set +a` before the
  `psql … "$DATABASE_URL_OWNER"` line; `_ENV_EXAMPLE_DSN_BLOCK` (`:3736-3744`) says the owner DSN is injected into
  `.env.owner`, which only the migrate/jobs services load.
- Docs: `docs/operations/fabrik-lifecycle.md:203-205` (two files), the runbook gains step 0 before `:232` ("a service that
  needs the owner DSN declares `.env.owner` in its `env_file`; the audit-jobs companion already does"), `:253-255` becomes
  "What the split does not cover" (the socket holder and root, spec § Constraints); `docs/CONFIGURATION.md:247`, `:249`,
  `:254`; `templates/scaffold/docs/CONFIGURATION_TEMPLATE.md:33`, `:119`, `:125`, `:144`, `:153`;
  `OPERATIONS_TEMPLATE.md:191`; `RESILIENCE_TEMPLATE.md:477`; `docs/reference/modules/drivers.md:238`.

Steps:
1. **G7 first (the companion carries the owner file, the app does not)** in `tests/test_scaffold_audit_log.py`: for each
   `_companion_types()` type the committed compose's `<name>-audit-jobs` service has `env_file == [".env", {"path":
   ".env.owner", "required": False}]` and the app service has `[".env"]` — written by changing the `== [".env"]` at `:530`
   and adding the app-service assertion; RED on today's code. Then `spec_loader.py`, `spec_generator.py`, the partial and
   `_append_audit_jobs_service` → GREEN; `:279` and `:558` (`".env" in svc["env_file"]`) keep passing because `.env` stays
   a plain string in the list.
2. G8 (the rendered template's companion, chrome-extension and file-worker, `:548-558`): the same long-syntax shape; G9
   (a node-api companion without `owner_env`): `tests/test_companion_services.py::test_render_emits_two_services` gains the
   assertion that its `env_file == [".env"]` — today's shape, red by the step-4 mutant. `tests/test_scaffold_saas_backend.py:170`
   is run and keeps passing (G10, unchanged test: the saas services never carry the owner file).
3. The schema headers and `_ENV_EXAMPLE_DSN_BLOCK` text; then every doc line in Produces. Run
   `/opt/fabrik/.venv/bin/python -m pytest tests/test_scaffold_audit_log.py tests/test_companion_services.py
   tests/test_scaffold_saas_backend.py tests/test_scaffold_compose_traefik.py tests/test_spec_generator*.py -q -p no:cacheprovider`
   → all pass; `python scripts/enforcement/check_doc_sync.py` → green; `python3 scripts/render_doc_script_links.py --check`
   → green.
4. **Phase gate**: red-on-revert in a throwaway worktree — mutants: the partial emitting the long syntax unconditionally
   (G9 red), `audit_jobs_companion` without `owner_env=True` (G7 red) → each named test red, then the worktree removed.
5. **`/fabrik-review-scoped`** on Phase B's surface — BLOCKING, to its closing pass confirming zero defects.
6. Commit Phase B (explicit pathspecs; `CHANGELOG.md` via the private-index recipe; `Agent-Phase: B`), push.

**Behavior Contract (Phase B):**
- **Given** a database spec of a type with an audit-jobs companion, **When** the scaffold writes the committed compose, **Then** the companion loads `.env` and `.env.owner` (long syntax, `required: false`) and the app service loads `.env` alone (spec § The delta 4-5)
- **Given** the same spec rendered through the template, **When** the companion partial renders, **Then** it carries the same two-file block (spec § The delta 5)
- **Given** a companion declared without `owner_env`, **When** it renders, **Then** its `env_file` is today's `[".env"]` (spec § The delta 5)
- **Given** a human applying `db/schema.sql` on the VPS, **When** they read the header, **Then** it sources both files before the owner `psql` (spec § Personas)
- **Given** an agent reading the lifecycle or configuration docs, **When** it looks up where the owner DSN lives, **Then** every sentence names `.env.owner` and the runbook's step 0 (spec § Documentation landing sites)

## Phase C — the live check and Finish

Appetite: 60

Steps:
1. **R1 (read-only, the one VPS touch):** `ssh -o BatchMode=yes -o ConnectTimeout=20 ozgur@vps1.ocoron.com "sudo -n stat
   -c '%n %U:%G %a' /opt/transdoc/.env /opt/youtube/.env"` → expected `root:root 600` for both. A `644` widens Phase A by one
   `chmod 0600` on `.env` as well (the same `mode` parameter, passed by every `.env` writer) — applied in this phase with its
   grader. If vps1 is unreachable after two tries, the Evidence records the assumption and the first `fabrik apply` after
   merge reads the mode back.
2. **Finish — the heavy `/fabrik-review`** over the whole-plan diff: the D7 floor — file partition, a Sonnet and a Haiku
   finder per slice (D-344), the orchestrator executing every refutation, stamped with `command_run.py dispatch` first — to
   its closing pass confirming zero defects; receipt `docs/development/reviews/2026-10-12-plan-1-owner-dsn-split-review.md`
   embedding the verbatim `final_gate.py --json` success.
3. The full gate: `python scripts/final_gate.py --check --json` → `"status": "success"`, checked with an exit-coded reader
   before any embedding; `python scripts/enforcement/check_convergence.py` → exit 0; `/fabrik-docs-review` over the
   Phase B docs.
4. Commit Phase C (explicit pathspecs; `Agent-Phase: C`), push; plan `Status: EXECUTED`; `work.py done W-4e74ea9d --evidence
   <sha>`; the merge: infra is re-running request 01M4PKEAJY for worktree-fleet after re-vendoring `libs/health_probe` — the
   close SAYS so and files a new `merge_request.py request --review <receipt> --item W-4e74ea9d` only if that request has
   been closed by then (I7).

**Behavior Contract (Phase C):**
- **Given** the merged change, **When** the next `fabrik apply` of a database project runs, **Then** its `.env.owner` exists root-owned 0600 and its `.env` no longer carries the owner key — read back by the apply log's move line (spec § Lifecycle)

## File Scope (owned paths)

- src/fabrik/orchestrator/deployer_ssh.py
- src/fabrik/spec_loader.py
- src/fabrik/spec_generator.py
- src/fabrik/scaffold.py
- templates/_partials/_companion_service.yaml.j2
- templates/scaffold/docs/CONFIGURATION_TEMPLATE.md
- templates/scaffold/docs/OPERATIONS_TEMPLATE.md
- templates/scaffold/docs/RESILIENCE_TEMPLATE.md
- tests/orchestrator/test_deployer_ssh.py
- tests/orchestrator/test_deployer_git_sha.py
- tests/test_scaffold_audit_log.py
- tests/test_companion_services.py
- docs/operations/fabrik-lifecycle.md
- docs/CONFIGURATION.md
- docs/reference/modules/drivers.md
- docs/superpowers/specs/2026-10-12-owner-dsn-split-design.md
- docs/development/reviews/2026-10-12-plan-1-owner-dsn-split-review.md

## Evidence

**Phase A.** The one-file shape today — every `.env` writer and the reader it feeds (seat A of this run, re-read):
```text
src/fabrik/orchestrator/deployer_ssh.py:308:    def read_env(self, ctx: DeploymentContext) -> dict[str, str]:
src/fabrik/orchestrator/deployer_ssh.py:328:    def inject_env(self, ctx: DeploymentContext, env_vars: dict[str, str]) -> None:
src/fabrik/orchestrator/deployer_ssh.py:362:            _write_file_to_vps(name, ".env", env_content)
src/fabrik/orchestrator/deployer_ssh.py:524:        _write_file_to_vps(name, ".env", env_content)
src/fabrik/orchestrator/deployer_ssh.py:607:        _write_file_to_vps(name, ".env", env_content)
src/fabrik/orchestrator/deployer_ssh.py:649:        _write_file_to_vps(name, ".env", env_content)
src/fabrik/orchestrator/deployer_ssh.py:686:        _write_file_to_vps_path(path, ".env", env_content)
src/fabrik/orchestrator/deployer_ssh.py:693:    def _build_env_content(
src/fabrik/orchestrator/deployer_ssh.py:898:def _read_env_file(path: str, _ssh: Any) -> dict[str, str]:
src/fabrik/orchestrator/deployer_ssh.py:906:    env_path = f"{path}/.env"
src/fabrik/orchestrator/deployer_ssh.py:952:        _write_file_to_vps(name, ".env", _format_env(merged))
src/fabrik/orchestrator/deployer_ssh.py:997:            f"{mkdir}sudo mv {shlex.quote(tmp_remote)} {dest} && sudo chown root:root {dest}",
```
The registrar's one-call injection and the app-role step's reads (seat C):
```text
src/fabrik/orchestrator/infrastructure.py:876:                self.deployer.inject_env(
src/fabrik/orchestrator/infrastructure.py:877:                    ctx, {"DATABASE_URL": database_url, "DATABASE_URL_OWNER": database_url}
src/fabrik/orchestrator/infrastructure.py:1094:            env = self.deployer.read_env(ctx)
src/fabrik/orchestrator/infrastructure.py:1096:            owner_dsn = env.get("DATABASE_URL_OWNER")
src/fabrik/orchestrator/infrastructure.py:1114:                self.deployer.inject_env(ctx, {"DATABASE_URL": owner_dsn})
src/fabrik/orchestrator/infrastructure.py:1126:                    self.deployer.inject_env(ctx, {"DATABASE_URL_OWNER": current or ""})
```
Executed this run (`scratchpad/ods-probe.py`, the worktree's deployer module loaded by path): the split is a pure key
partition of today's parse/format pair; the validator accepts the long-syntax `env_file` (its four errors are the probe's
deliberately missing `platform`/`restart` lines, none about `env_file`); the temp file the writer scps is 0600:
```text
== probe 1: parse/format round-trip
keys: ['DATABASE_URL', 'DATABASE_URL_OWNER', 'REDIS_URL']
app half: ['DATABASE_URL', 'REDIS_URL'] | owner half: ['DATABASE_URL_OWNER']
format(app) contains OWNER: False
format(owner): DATABASE_URL_OWNER =<redacted>
== probe 2: _validate_compose on the long-syntax env_file shape
validate errors: ["Service 'demo': missing 'platform: linux/amd64'", "Service 'demo': missing 'restart: unless-stopped'", "Service 'demo-audit-jobs': missing 'platform: linux/amd64'", "Service 'demo-audit-jobs': missing 'restart: unless-stopped'"]
jobs env_file parsed: ['.env', {'path': '.env.owner', 'required': False}]
== probe 3: mkstemp mode
mkstemp mode: 0o600
```
The tests that pin the one-file shape (seat A; the three re-read by the lead):
```text
tests/orchestrator/test_deployer_git_sha.py:81:    def write(self, name: str, filename: str, content: str) -> None:
tests/orchestrator/test_deployer_git_sha.py:82:        assert filename == ".env", filename
tests/orchestrator/test_deployer_ssh.py:626:        assert _parse_env(mock_write.call_args[0][2]) == {"K": "v"}
tests/orchestrator/test_deployer_ssh.py:627:        assert mock_ssh.call_count == 2  # probe, then compose up — no cat
```

**Phase B.** The companion model, its one constructor and the emitters (seat B; the lead re-read `:852-855`, `:17-18`,
`:4190-4191`, `:3736-3744`):
```text
src/fabrik/spec_loader.py:818:class CompanionService(BaseModel):
src/fabrik/spec_loader.py:852:    env_overrides: dict[str, str] | None = Field(
src/fabrik/spec_loader.py:914:    companion_services: list[CompanionService] = Field(default_factory=list)
src/fabrik/spec_generator.py:161:    return CompanionService(
src/fabrik/template_renderer.py:146:        "companion_services": spec.companion_services,
templates/_partials/_companion_service.yaml.j2:17:    env_file:
templates/_partials/_companion_service.yaml.j2:18:      - .env
src/fabrik/scaffold.py:4159:def _append_audit_jobs_service(
src/fabrik/scaffold.py:4190:        "    env_file:\n"
src/fabrik/scaffold.py:4191:        "      - .env\n"
```
The assertions the new shape meets (seat B, re-read):
```text
tests/test_scaffold_audit_log.py:279:    assert ".env" in jobs["env_file"]
tests/test_scaffold_audit_log.py:530:    assert svc["env_file"] == [".env"]
tests/test_scaffold_audit_log.py:558:    assert ".env" in svc["env_file"]
tests/test_scaffold_saas_backend.py:170:        assert services[svc].get("env_file") == [".env"]
```
External facts the block rests on: ledger ods-21 (later file wins), ods-24/25 (`required` since 2.24.0, missing file
ignored), `deployer_ssh.py:1217` (fleet compose 2.40.3).

**Phase C.** The spec's R1: `_write_file_to_vps_path` issues no `chmod` (`deployer_ssh.py:997`), so the live mode is the
temp file's 0600 carried by `scp` — an assumption until the `stat` runs (ssh to vps1 timed out twice on 2026-10-12 at
~02:30 and ~02:45 local; the Grafana MCP and `git push` reached their hosts in the same window, so the failure is the
network's, not the host's).

## Self-audit

- Grounding passes: the spec's 59-row research ledger and its three researcher seats; this run's three Explore seats over
  the deployer (seat A), the emitters and their tests (seat B), the registrar and every other `.env` reader (seat C) —
  seat C found 0 readers of `DATABASE_URL_OWNER` outside `infrastructure.py:1094-1096` (audit.py 0, orchestrator/__init__.py
  0, scripts/ 0, app_role_check.py reads the clone, not the env); three executed probes (above).
- Findings that shaped the plan: the LAST-write assertions and exact ssh counts in `test_deployer_ssh.py` (I8) → the
  owner file is written FIRST and only when non-empty; `_Vps.write`'s `filename == ".env"` (I8) → a named fallout step;
  `_validate_compose` never reads `env_file` (probe 2) → no validator change; `_persist_git_sha` reads `.env` alone →
  unchanged.
- (a) Coverage: spec delta 1 → `OWNER_ENV_KEYS`, G1; delta 2 → `read_env`/`inject_env`, G1, G2, G4; delta 3 → `_build_env_files`,
  G3; delta 4 → the long-syntax block, G7, G8, ods-21/24/25; delta 5 → `owner_env`, G7, G9, G10; delta 6 → `mode`, G5;
  the fail-closed reader on the second file → G6; every spec Validation row (1-7) → G1, G2, G3, G7+G9, probe 2 + G7, G5,
  Phase B step 3; documentation landing sites → Phase B Produces (every path:line) and each phase's commit (CHANGELOG);
  R1 → Phase C step 1; the D-row → the plan review's gate. No gap.
- (b) Signatures: `_split_env` returns `(app, owner)` and is the only partitioner `inject_env` and `_build_env_files` use;
  `_build_env_files` returns `(str, str | None)` and `_build_env_content` returns its `[0]`; `_read_env_file`'s new
  keyword defaults to `".env"`, so `:265`, `:326`, `:723`, `:950` are unchanged; `_write_file_to_vps(_path)`'s `mode`
  defaults to `None`, so every existing call issues today's command; `CompanionService.owner_env` defaults `False`, so
  every spec without it renders today's two lines; `OWNER_ENV_FILE` is the string the compose block and the writer share.
- Fixed point: not yet — `/fabrik-plan-review` grades it.

## Residual unknowns

- **Open — R1** (the live mode of `/opt/<name>/.env`): resolution Phase C step 1, two ssh attempts; unreachable → recorded
  as the assumption the first post-merge apply reads back.
- **Resolved — R2**: 0 code readers of `DATABASE_URL_OWNER` outside the hub (spec § What exists today; seat C re-confirmed
  the hub side).
- **Resolved — R3**: `required: false` exists since Compose 2.24.0 (ods-24, ods-26); the fleet measured 2.40.3.
- **Open — the ssh call-count assertions**: the exact new counts in `test_deployer_ssh.py:431` and `:627` are measured when
  Phase A runs them, never typed into this plan; resolution: Phase A step 4 asserts the measured value with its reason.

## Coverage Checklist

| Class | Status |
|---|---|
| Hunt: `src/fabrik/orchestrator/deployer_ssh.py` — every writer of `.env`, the reader, the restart | open — pass 1 |
| Hunt: `src/fabrik/scaffold.py`, `spec_loader.py`, `spec_generator.py`, the companion partial — the emitted compose shapes | open — pass 1 |
| Hunt: the two test files' pinned shapes — every fallout assertion named, none loosened | open — pass 1 |
| Hunt: the docs — every sentence that says both DSNs live in `.env` | open — pass 1 |
| Recurrence: fail-open/fail-closed — a swallowed error or an absent check that reads as success | open — pass 1 |
| Recurrence: boundary/sentinel/prefix — an off-by-one, a sentinel value, a prefix-vs-exact match | open — pass 1 |
| Recurrence: behavior-without-a-test — a contract row no test kills (mutation asserted) | open — pass 1 |
| Recurrence: denominator on every count — bounded searches state their bound | open — pass 1 |
| Recurrence: cost/quota accounting — native seats counted, a limit at its edges | open — pass 1 |
| Recurrence: proxy-as-evidence — the real check EXECUTED, not read | open — pass 1 |

Rubric invocation (verbatim output — the gate reads the generated header):

```text
$ python scripts/review_rubric.py --changed src/fabrik/orchestrator/deployer_ssh.py src/fabrik/spec_loader.py src/fabrik/spec_generator.py templates/_partials/_companion_service.yaml.j2 src/fabrik/scaffold.py
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

### ai/50-agentic.md  (hit: src/fabrik/orchestrator/deployer_ssh.py)
- is never the only thing between the agent and an irreversible act.
- **Auth boundary.** Agents run on the subscription's OAuth through the unmodified CLI, never `ANTHROPIC_API_KEY` (ai/00). Never pass `bare=True` on that lane: bare mode never reads OAuth credentials and fails with "Not logged in". A deployed service declares `shape.uses_claude_cli` and mounts the rotated `~/.claude`, never a static token. Anthropic's terms say subscription OAuth is for ordinary, individual use of Claude Code and its own apps; developers building products or services, including with the Agent SDK, should use an API key, and Anthropic does not permit routing requests through Free, Pro or Max credentials on behalf of their users, reserving the right to enforce that without notice. The operator's own development and automation through the unmodified CLI is the closest fit to that … (wrapped further — read the pack)
- output, and some models never return them. Pick the rate per model from the bake-off browser (hub-only), using its tools chip.

### core/10-python.md  (hit: src/fabrik/orchestrator/deployer_ssh.py, src/fabrik/scaffold.py, src/fabrik/spec_generator.py)
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
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

# promote-to-check_*: 66 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
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
