# The owner DSN leaves the app containers' environment

**Status:** DRAFT
**Profile:** delta
**Size:** small (≈130 lines, 4 files)

Work item W-4e74ea9d (fleet; filed by infra 2026-09-24 from the audit-log-everywhere work — D-385, D-393, D-410).
Research ledger: `docs/reference/research/2026-10-12-owner-dsn-split-ledger.md`.

## Personas

- **PRIMARY — the project's app containers, as the item states the threat**, in the filer's words: *"Append-only
  on `audit_log` therefore holds against the app's code paths and SQL injection, not against code execution
  inside the container, which can read `DATABASE_URL_OWNER`."* Their loop today: (1) compose starts the service
  with `env_file: .env`, (2) the process reads `DATABASE_URL`, (3) it also holds `DATABASE_URL_OWNER` in its
  environment, unused. Step budget: 3 steps; after this delta step 3 is gone — the owner DSN is not in the file the
  app loads.
- **The audit-jobs companion** (`<name>-audit-jobs`, `spec_generator.audit_jobs_companion`, scaffold payload for
  python-api, python-api-gpu, chrome-extension, mobile-app, file-worker — 0 deployed today, see § What exists today)
  — the one in-container reader of `DATABASE_URL_OWNER` the hub emits; it keeps reading it from its environment,
  which now comes from a second env file only it loads.
- **A project's `migrate` service** (transdoc's today, `/opt/transdoc/compose.yaml:68-88`; it runs `alembic upgrade
  head` on `DATABASE_URL`, which is still the owner DSN there because no spec has cut over) — at that project's
  app-role cutover its author adds the second env file to the migrate service and repoints Alembic at
  `DATABASE_URL_OWNER`; the lifecycle runbook gains that line.
- **The operator / the project agent running `db/schema.sql` by hand on the VPS** — the schema header's `psql …
  "$DATABASE_URL_OWNER"` now needs both files sourced; the header and the docs say so.
- **AUTOMATED consumers:** `SSHDeployer` (`_build_env_content`, `inject_env`, `read_env`) writes and reads the two
  files; the postgres registrar's app-role step (`infrastructure.py:1094-1127`) reads the merged view through
  `read_env` and injects through `inject_env` — unchanged call sites; `_persist_git_sha` (`deployer_ssh.py:945-953`)
  keeps touching `.env` only; `fabrik audit`'s env reads stay on `.env`.
- **The threat actor**: code executing inside an app container (a dependency compromise, a template injection).
  Not in scope: a holder of the Docker socket or root on the VPS host — either reads every file and every
  container's environment whatever the layout (ledger ods-14).

## Goal

A project's app containers never receive `DATABASE_URL_OWNER`: the deployer writes it to a second file,
`/opt/<name>/.env.owner`, that only the services declaring it load, and never to `.env`. No project needs a
code change for it, no spec flag gates it, and `fabrik apply` keeps its first-deploy ordering and its app-role
cutover and rollback.

## Why this exists

D-385 made `audit_log` append-only through a non-owner app role, so a compromised app process cannot rewrite the
log — the owner's right "to modify or destroy an object is inherent in being the object's owner, and cannot be
granted or revoked in itself" (ods-48), so the owner DSN IS the escalation — unless it reads `DATABASE_URL_OWNER` from its own environment, which `env_file: .env` hands every service
(`docs/operations/fabrik-lifecycle.md:253-255`, `docs/CONFIGURATION.md:254`). The plan that shipped D-385 recorded
this as "the limit" and filed the item. Today the gap is latent: both DSNs are the owner DSN in every project (0 of
69 specs set `shape.database_url_app_role`), so the first cutover would be the moment the limit bites. Closing it
before that cutover is the point — new projects are born with the split, and a project cuts over onto it.

## What exists today (grounded)

- One env file per app, written three ways: `SSHDeployer._build_env_content` merges spec env + secrets over the
  existing `.env` read through `_read_env_file` (`src/fabrik/orchestrator/deployer_ssh.py:693-760`, `:898-920`) and
  every deploy path writes it with `_write_file_to_vps(name, ".env", …)` (`:362`, `:524`, `:607`, `:649`, `:686`);
  `inject_env` merges a registrar's keys into it and restarts (`:328-364`); `read_env` is the fail-closed reader
  (`:308-326`); `_persist_git_sha` read-merge-writes `GIT_SHA` into it (`:945-953`).
- The file lands root-owned: `_write_file_to_vps_path` writes a `tempfile.mkstemp` file (mode 0600 on this box,
  measured), `scp`s it (`src/fabrik/drivers/ssh.py:125-162`, no `-p`; scp carries the source mode), then `sudo mv`
  + `sudo chown root:root` (`deployer_ssh.py:960-1000`). No `chmod` is issued anywhere on the path — the mode is
  the temp file's. **Assumption, to verify at plan time with one `stat` on vps1:** the live `/opt/<name>/.env` is
  `root:root 0600`.
- The postgres registrar injects `DATABASE_URL` and `DATABASE_URL_OWNER` in ONE `inject_env` call at creation,
  because the owner password exists only then (`src/fabrik/orchestrator/infrastructure.py:869-880`). The app-role
  step reads both back through `read_env` and converges by the table in `fabrik-lifecycle.md:217-220`:
  cutover injects `DATABASE_URL` + `DATABASE_URL_OWNER`, rollback injects `DATABASE_URL := DATABASE_URL_OWNER`,
  the backfill injects `DATABASE_URL_OWNER` alone (`infrastructure.py:1094-1127`, `:1185-1193`).
- Every compose the hub emits loads the one file: the saas three services (`src/fabrik/scaffold.py:3264`,
  `:3299`, `:3337`), the python-api template's app service (`templates/python-api/compose.yaml.j2:77-79`), the
  committed audit-jobs companion (`scaffold.py:4186-4191`), the companion partial
  (`templates/_partials/_companion_service.yaml.j2:17-18`, whose header calls `.env` "the only place
  registrar-injected keys such as DATABASE_URL_OWNER live"), and the deployer's own compose for image-sourced
  apps (`deployer_ssh.py:1213`). The python-api template loads NO env file when `spec.source.image` is set
  (`compose.yaml.j2:76-79`).
- `CompanionService` is `id · command · memory · env_overrides` (`src/fabrik/spec_loader.py`, built by
  `spec_generator.audit_jobs_companion`, `spec_generator.py:150-166`), rendered by the partial above.
- The scaffold's `.env.example` names both DSNs with no value (`scaffold.py:3736-3744`); the WSL `.env.local`
  carries both as the same local role (`scaffold.py:2056-2057`); the saas and python `schema.sql` headers tell a
  human to run `psql … "$DATABASE_URL_OWNER" -f db/schema.sql` (`scaffold.py:2217-2219`, `:3595-3597`); the
  jobs module reads `DATABASE_URL_OWNER` from its environment and logs `audit_jobs: not_configured` when unset
  (`scaffold.py:3849-3860`).
- **Measured 2026-10-12 (read-only, this box):** 69 specs in `specs/services/`, 22 with `shape.needs_database: true`,
  0 with `shape.database_url_app_role`, 0 declaring an `audit-jobs` companion (`command grep -l audit-jobs
  specs/services/*.yaml`); 39 `compose.yaml` under `/opt/*/`, 0 naming `DATABASE_URL_OWNER`, 1 with a `migrate`
  service (transdoc); 0 code files under `/opt/*/{src,server,app,scripts,db,alembic,migrations}` (`.py .sh .ts
  .js .sql`, hub excluded) reading `DATABASE_URL_OWNER`. The hub's scaffold payload is therefore the only
  in-container reader, and it is not deployed anywhere yet.

## The delta

Invariants (the words the code and the docs will carry):

1. **`DATABASE_URL_OWNER` lives in `/opt/<name>/.env.owner` and nowhere else on the VPS.** The deployer writes it
   there; `.env` never carries it. The key set is one constant, `OWNER_ENV_KEYS = ("DATABASE_URL_OWNER",)`, in
   `deployer_ssh.py` — the single place a future owner-only key joins.
2. **The merged view is unchanged for every reader.** `read_env` returns `.env` overlaid by `.env.owner`, so the
   app-role step's `env.get("DATABASE_URL_OWNER")` and every cutover/rollback/backfill branch read exactly what
   they read today; `inject_env` splits by key: owner keys to `.env.owner`, the rest to `.env`, both written in the
   same call before the restart, so the registrar's one-call invariant at creation (`infrastructure.py:873`)
   holds — the owner password is on disk before anything below it can fail.
3. **The move is automatic and idempotent.** `_build_env_content` and `inject_env` strip owner keys out of the
   `.env` they read and fold them into `.env.owner` (an existing `.env.owner` wins over a stale `.env` copy, the
   older copy is logged as moved, never silently dropped); a project whose `.env` still carries the key gets it
   moved on its next `fabrik apply`, with no flag and no runbook step. A spec `env:` or secret that names an owner
   key is routed the same way.
4. **Only a service that declares the file loads it.** Compose `env_file` long syntax, `required: false`:
   ```yaml
   env_file:
     - .env
     - path: .env.owner
       required: false
   ```
   A list is "processed from the top down" and "the value from the last file in the list stands" (ods-21);
   `required` exists since Compose 2.24.0 (ods-24; the fleet measured 2.40.3, `deployer_ssh.py:1217`) and a missing
   file with it false is "silently ignored" (ods-25), where a missing required file fails the model load before any
   command runs (ods-27, ods-28). `required: false` keeps the first-boot ordering `core/30-ops.md:236` describes — the registrar writes the files
   AFTER the first `up`, so a required file would fail `--wait` before it exists; with it absent the jobs module
   logs `not_configured` and idles until the restart `inject_env` performs, exactly as `DATABASE_URL` does today
   (`scaffold.py:3234-3242`). App services keep the plain `- .env`.
5. **The scaffold emits the declaration only for the owner's consumers:** the audit-jobs companion
   (`scaffold.py:4186-4191` and the partial, through a new `CompanionService.owner_env: bool = False` that
   `audit_jobs_companion` sets `True`); every other service is untouched. A project adding its own `migrate`
   service copies the three lines; the lifecycle runbook names it as the cutover's step 0.
6. **Both files are written root-owned 0600** by the same `_write_file_to_vps_path` path; the owner file
   additionally gets an explicit `sudo chmod 0600` so the mode does not depend on the temp file's — the one place
   a `chmod` enters this writer.

Touchpoints:

| Where | Change |
|---|---|
| `src/fabrik/orchestrator/deployer_ssh.py:308-364` (`read_env`, `inject_env`) | merged read of `.env` + `.env.owner`; split write by `OWNER_ENV_KEYS`; one restart |
| `deployer_ssh.py:693-760` (`_build_env_content`) and its five `_write_file_to_vps(name, ".env", …)` callers | returns the app half; a sibling `_build_owner_env_content` returns the owner half; each deploy path writes both (the owner file only when non-empty) |
| `deployer_ssh.py:898-920` (`_read_env_file`) | gains a `filename` parameter (default `.env`), so `.env.owner` reads through the same fail-closed probe |
| `deployer_ssh.py:945-953` (`_persist_git_sha`) | unchanged — `GIT_SHA` is an app key |
| `deployer_ssh.py:960-1000` (`_write_file_to_vps_path`) | optional `mode` → `sudo chmod` after the `mv` |
| `src/fabrik/spec_loader.py` (`CompanionService`) and `src/fabrik/spec_generator.py:150-166` | `owner_env: bool = False`; `audit_jobs_companion` sets it |
| `templates/_partials/_companion_service.yaml.j2:17-18` | the long-syntax `env_file` block under `{% if c.owner_env %}`; header sentence rewritten |
| `src/fabrik/scaffold.py:4186-4191` | the committed companion carries the same block |
| `scaffold.py:2217-2219`, `:3595-3597`, `:3736-3744` | the schema headers and `.env.example` comment say where the owner DSN lives and how a human sources both files |
| `docs/operations/fabrik-lifecycle.md:203-205`, `:253-255` | the two-file layout; "The limit" becomes "What the split does not cover" (socket and root) |
| `docs/CONFIGURATION.md:245-254`, `templates/scaffold/docs/CONFIGURATION_TEMPLATE.md:32-33`, `:119-153`, `OPERATIONS_TEMPLATE.md:191`, `RESILIENCE_TEMPLATE.md:477-478`, `docs/reference/modules/drivers.md:238` | the sentence "both DSNs live in `.env`" is replaced wherever it appears |

Code estimate: `deployer_ssh.py` ≈ 70 lines, `spec_loader.py` + `spec_generator.py` ≈ 10, the partial ≈ 6,
`scaffold.py` ≈ 20 (compose block + three doc strings) — ≈ 110-130 lines across 4 code files (the Jinja partial
counted as code), tests excluded → `Size: small`.

MIRROR (the shapes this change can break, and why each holds):
- a project whose compose does not declare `.env.owner` and whose code reads `DATABASE_URL_OWNER` from the
  environment — loses the key on its next apply. Measured 0 such projects (§ What exists today); the deployer
  logs every move so the one that appears later is visible in the apply log.
- a host-side `. .env` that expected the key (the schema.sql header, a runbook) — now sources two files; every
  such text is in the touchpoints table.
- the WSL `.env.local` — untouched; both keys stay there (one local role), by `scaffold.py:2056-2057`.
- `fabrik app-role-check` and `fabrik audit` reading `.env` — read the merged view where they go through
  `read_env`; a direct `_read_env_file(path, _ssh)` call keeps reading `.env` alone (`deployer_ssh.py:265`) and is
  listed for the plan to confirm it needs no owner key.
- a spoke-targeted app — both files are written inside `_target_vps_env`, as `.env` is today.

## Contract deltas

None. No data-contract or ui-design field changes; no spec `shape:` flag is added (the measured consumer count made a gate unnecessary — a flag would be a knob nobody turns).

## Rejected alternatives

- **(B) Compose file-based `secrets:`** holding the owner password or DSN, mounted into the privileged services.
  A secret is mounted as a file at `/run/secrets/<name>` (ods-3). Without Swarm it is a bind mount of the host file (ods-9, ods-10) whose `uid`/`gid`/`mode` are
  "silently ignored" (ods-6); the default mode documented for secrets is 0444 (ods-5); the jobs module and the
  schema header would have to learn a `_FILE` convention our images do not have (ods-12, ods-16); `docker inspect`
  still names the host path (ods-14). Docker's own guidance prefers secrets over environment variables for
  passwords (ods-38, ods-54) and OWASP discourages environment variables "unless the other methods are not
  possible" (ods-44); the best-practice seat recommended exactly this shape with `mode: "0400"` and the
  service's uid (ods-59). It does not hold on this fleet: the mode and uid it relies on are the attributes Compose
  ignores for a file source (ods-6), so the bind mount carries the HOST file's owner and mode — a root 0600 file is
  unreadable by the `appuser` the scaffold images run as (`templates/scaffold/docker/Dockerfile.python:44-45`,
  `Dockerfile.node:37-38`), and a file loosened to 0644 is readable by every local user on the host. "The benefit
  is scope, not encryption" (ods-55), and the scope this item needs — the owner DSN absent from the app services —
  is exactly what a second env file gives with zero code change. More code in the scaffold payload for no exposure
  gain over an env file the same host reads as root.
- **(B′) libpq `passfile` / `PGPASSFILE`** — libpq ignores a password file whose mode is not 0600 (ods-19), the
  file still has to reach the container (as in B), and asyncpg-based code reads a DSN, not a service file
  (ods-17, ods-18, ods-20 rejected).
- **(C) keep one `.env` and blank the key per app service with `environment: DATABASE_URL_OWNER=`** — `environment`
  does override `env_file` (ods-29), but the value still reaches the host-side model and `docker compose config`
  (ods-35), and the one file keeps carrying the owner DSN for anyone who can read it; it hides the key from the
  process's environment only, which is the weaker half of the property.
- **(D) a spec flag gating the move per project** (the `shape.database_url_app_role` pattern) — the measured
  consumer count is 0, so the flag would gate nothing today and would have to be flipped 22 times later; the
  automatic, logged move is reversible by restoring the key to `.env` with one `inject_env`, and the plan's
  grader asserts the move is logged.
- **(E) run migrations from the hub or a CI runner with the owner credential never on the app host** — the jobs
  companion is scheduled and long-running, not a one-off, and `core/30-ops.md:429-437` (with 12-factor's "admin
  code must ship with application code", ods-42) mandates admin processes run in the deployed environment —
  Heroku's release phase is the same one-shot in the app's own environment (ods-57), which the compose `migrate`
  service already is. A second trust domain holding the owner credential is what OWASP warns about for CI
  (ods-45), and `postgres-main` is reachable only from the hub mesh (ods-58); the credential has to be on the host
  for the compose to deliver it.
- **A new file name other than `.env.owner`** — `.env.<role>` reads as a role-scoped sibling of `.env`;
  `owner.env` would sort away from it in a listing.

## Lifecycle

Adoption: the next `fabrik apply` of each database-backed project moves its key (22 projects, no action by them);
new scaffolds are born with the layout. Growth: a second owner-only key joins `OWNER_ENV_KEYS` in one place; a
project with a `migrate` service adds the three compose lines at its cutover. Degradation: a missing `.env.owner`
leaves the jobs companion at `not_configured` (logged, never a crash) and makes the app-role step refuse a cutover
or rollback it cannot ground, as today. Retirement: if the fleet ever moves to a secret store that injects into
the process environment per service, `OWNER_ENV_KEYS` names exactly what moves.

## Constraints Digest

| Quote | Source |
|---|---|
| `DSNs and secrets get NO fallback — a missing value fails LOUDLY at boot` | `.windsurf/rules/core/35-security-auth.md:273` |
| `Before editing .env, *.key, *.pem, files under secrets/, or .ssh/:` | `.windsurf/rules/core/35-security-auth.md:307` |
| `apps read a complete DATABASE_URL (postgresql+asyncpg://user:pass@host:port/db) and REDIS_URL from env.` | `.windsurf/rules/core/10-python.md:133` |
| `.env → Active config (gitignored, copy from .env.local for dev)` | `.windsurf/rules/core/25-data-postgres.md:45` |
| `Companion service (same image, different command) — yes, same codebase. Declare it in the spec; the scaffolder emits a 2nd compose service that shares the app's build/image + env + DATABASE_URL/REDIS_URL, overriding only command + container_name + memory.` | `.windsurf/rules/core/30-ops.md:161` |
| `First-boot DSN ordering. The registrar injects DATABASE_URL POST-deploy, so a container that needs a real DSN at first boot crashes before it arrives.` | `.windsurf/rules/core/30-ops.md:236` |
| `migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes.` | `.windsurf/rules/core/30-ops.md:437` |
| `Credentials in project .env` | `.windsurf/rules/core/30-ops.md:184` |

`ai/50-agentic.md` matched by the `**/orchestrator/**` glob only; it governs agent loops, not the deployer — read,
no row. `core/40-documentation.md` governs the doc edits in the touchpoints table (Doc Sync Matrix).

## Constraints

- An env file is read on the host by the Compose CLI and resolved into the service's environment; the container
  never mounts it (ods-32, ods-34, ods-40 — the container half is an inference from the loader and the
  `--no-env-resolution` flag, marked so). So an app container that does not declare `.env.owner` holds nothing
  of it, which is the whole property.
- The two privileged services DO hold the owner DSN in their environment, with the known residuals of any
  environment variable: `docker inspect` and `docker compose config` show it to a Docker-socket holder (ods-35,
  ods-36), a crash handler may log it (ods-43), and a process running as the same uid can read `/proc/1/environ`
  (ods-52). Every one of those actors is already root-equivalent on the host (ods-46) or is the owner's own
  legitimate process; the item's threat — code executing in the APP container — reaches none of them.
- Both files stay `root:root 0600` on the host (invariant 6); the deployer writes them, nobody edits them by
  hand (`core/35-security-auth.md:307` governs the backup if anyone must).
- No new env var, port, service or dependency; `.env.example` keeps naming both DSNs with no value.

## fabrik-lib verdict

One line: no fabrik-lib module covers deploy-time env delivery (the hub is the deploy control plane,
`agents-fabrik.md:80-86`); nothing to vendor or enhance — BUILD in the hub, 4 files.

## External dependencies

Docker Compose on the fleet (measured 2.40.3, `deployer_ssh.py:1217`): `env_file` list + long syntax with
`required` — ledger rows ods-21 to ods-40 (seat A); file secrets' limits — ods-1 to ods-16 (seat B); libpq
password files — ods-17 to ods-20; the practice sources — ods-41 to ods-59 (seat C). No new service, no cost.

## Shape / infra implications

None to `shape:`. One new file per database-backed app directory on each VPS, root-owned 0600.

## Documentation landing sites

`docs/operations/fabrik-lifecycle.md` § App-role cutover and rollback (the layout, the runbook's step 0, the
rewritten limit) · `docs/CONFIGURATION.md` § Project database DSNs · the three scaffold doc templates and
`drivers.md` rows named above · `CHANGELOG.md` · `docs/DECISIONS.md` (one row, reversible) · the deployer's own
docstrings. No new reference doc: the subsystem is the deployer, already documented.

## Validation

Red-first graders in `tests/`: (1) `inject_env({"DATABASE_URL": a, "DATABASE_URL_OWNER": o})` writes `o` to
`.env.owner` and never to `.env`, one restart; (2) `read_env` returns the merged view with the owner file winning;
(3) `_build_env_content` on an existing `.env` carrying the key moves it (logged) and the next build is a no-op;
(4) the rendered companion for a database spec carries the long-syntax block and the app service does not;
(5) `_validate_compose` accepts the long syntax; (6) the written owner file gets `chmod 0600`; (7) the
`.env.example` and schema headers name both files. Live check at plan time: `stat` of one project's `.env` on
vps1 (the assumption above).

## Open / blocking unknowns

- R1 (open, cheap): the live mode of `/opt/<name>/.env` on vps1 — one read-only `stat`; a 0644 finding widens the
  delta by one `chmod` on `.env` too. Resolution: plan phase 1.
- R2 (resolved by measurement): no project code outside the hub reads `DATABASE_URL_OWNER` (0 of the measured
  tree); the move needs no gate.
- R3 (resolved): Compose `env_file` long-syntax `required` exists since 2.24.0 (ods-24, ods-26); the fleet
  measured 2.40.3 (`deployer_ssh.py:1217`), so the long syntax is available and no fallback is needed.

## Decisions taken

Reversible: the owner DSN moves to `.env.owner`, delivered only to services that declare it, with no gate — one
D-row at approval. Rejected: file secrets, passfile, env override, a per-project flag, hub-run migrations.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"The owner DSN shares the project `.env` with the app DSN"* (W-4e74ea9d) | IN | § Goal, § The delta 1 |
| I2 | *"holds against the app's code paths and SQL injection, not against code execution inside the container"* | IN | § Why this exists, § Personas (threat actor) |
| I3 | *"Closing it means an env file mounted only into the migrate and jobs services"* | IN | § The delta 4-5 |
| I4 | the brief's candidates (A) second env file · (B) compose secrets · (C) environment override | IN | § The delta (A), § Rejected alternatives (B, C) |
| I5 | *"the deployer must never move the key out of `.env` for a project whose compose does not read the second file"* (brief) | CHANGED | § What exists today — measured 0 such projects; the gate is replaced by the logged automatic move, § Rejected (D) |
| I6 | *"how the WSL dev `.env` (both keys) stays unmodified in code"* (brief) | IN | § MIRROR |
| I7 | *"how `fabrik apply`'s first-deploy ordering … survives"* (brief) | IN | § The delta 2, 4 |
| I8 | *"how rollback (`DATABASE_URL` := owner DSN) reads the second file"* (brief) | IN | § The delta 2 |
| I9 | *"how the docs templates … and `fabrik-lifecycle.md` § The limit change"* (brief) | IN | § Touchpoints, § Documentation landing sites |
| I10 | *"Measure the inventory read-only … never touch a VPS, a database or another repo"* (brief) | IN | § What exists today (measured); R1 names the one live `stat` for the plan |
| I11 | operator standing ruling D-746/D-558: *"do not stop again for the things you can handle yourself"*; Pool OFF (D-181) | IN | this run: native seats, no operator question; the approval gate is the panel's (D-613) |
