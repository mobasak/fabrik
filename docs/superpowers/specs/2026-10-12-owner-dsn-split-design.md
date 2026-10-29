# The owner DSN leaves the app containers' environment

**Status:** CONVERGED
**Profile:** delta
**Size:** small (≈175 lines, 5 code files + 1 Jinja template)

Work item W-4e74ea9d (fleet; filed by infra 2026-09-24 from the audit-log-everywhere work — D-385, D-393, D-410).
Research ledger: `docs/reference/research/2026-10-12-owner-dsn-split-ledger.md`.

## Personas

- **PRIMARY — the project's app containers, as the item states the threat**, in the filer's words: *"Append-only
  on `audit_log` therefore holds against the app's code paths and SQL injection, not against code execution
  inside the container, which can read `DATABASE_URL_OWNER`."* Their loop today: (1) compose starts the service
  with `env_file: .env`, (2) the process reads `DATABASE_URL`, (3) it also holds `DATABASE_URL_OWNER` in its
  environment, unused. Step budget: 3 steps; after this delta step 3 is gone — the owner KEY is not in the file the
  app loads (the owner credential itself leaves the app's environment with the project's cutover, § Goal).
- **The audit-jobs companion** (`<name>-audit-jobs`, `spec_generator.audit_jobs_companion`, scaffold payload for
  python-api, python-api-gpu, chrome-extension, mobile-app, file-worker — 0 deployed today, see § What exists today)
  — the one in-container reader of `DATABASE_URL_OWNER` the hub emits; it keeps reading it from its environment,
  which now comes from a second env file only it loads.
- **A project's `migrate` service** (transdoc's today, `/opt/transdoc/compose.yaml:68-88`; it runs `alembic upgrade
  head` on `DATABASE_URL`, which is still the owner DSN there because no spec has cut over) — at that project's
  app-role cutover its author adds the second env file to the migrate service, repoints Alembic's `env.py` at
  `DATABASE_URL_OWNER` and runs it as `docker compose run --rm migrate alembic upgrade head` — never through the app
  service, which no longer holds the key; the lifecycle runbook gains that line.
- **The operator / the project agent running `db/schema.sql` by hand on the VPS** — the schema header's `psql …
  "$DATABASE_URL_OWNER"` now needs both files sourced; the header and the docs say so.
- **AUTOMATED consumers:** `SSHDeployer` (`_build_env_content`, `inject_env`, `read_env`) writes and reads the two
  files; the postgres registrar's app-role step (`infrastructure.py:1094-1127`) reads the merged view through
  `read_env` and injects through `inject_env` — unchanged call sites; `_persist_git_sha` (`deployer_ssh.py:943-953`)
  writes through the same split writer, so its redeploy-time merge keeps the owner key out of `.env`; `fabrik audit`
  reads the merged view through `read_env`.
- **The threat actor**: code executing inside an app container (a dependency compromise, a template injection).
  Not in scope: a holder of the Docker socket or root on the VPS host — either reads every file and every
  container's environment whatever the layout (ledger ods-14).

## Goal
A project's app containers never receive the owner KEY: the deployer writes `DATABASE_URL_OWNER` to a second file,
`/opt/<name>/.env.owner`, that only the services declaring it load, and never to `.env`. The owner CREDENTIAL leaves the
app's environment the moment the project cuts over (`shape.database_url_app_role: true`, D-385) — until then
`DATABASE_URL` is still the owner DSN by construction, so this split is the precondition that makes the cutover close
the gap, not the protection itself. No project needs a code change for it, no spec flag gates it, and `fabrik apply`
keeps its first-deploy ordering and its app-role cutover and rollback.

## Why this exists

D-385 made `audit_log` append-only through a non-owner app role, so a compromised app process cannot rewrite the
log — the owner's right "to modify or destroy an object is inherent in being the object's owner, and cannot be
granted or revoked in itself" (ods-48), so the owner DSN IS the escalation — unless it reads `DATABASE_URL_OWNER` from its own environment, which `env_file: .env` hands every service
(`docs/operations/fabrik-lifecycle.md:253-255`, `docs/CONFIGURATION.md:254`). The plan that shipped D-385 recorded
this as "the limit" and filed the item. Today the gap is latent: both DSNs are the owner DSN in every project (0 of
69 specs set `shape.database_url_app_role`; the registrar sets both keys to one value at creation,
`infrastructure.py:876-878`, and a rollback sets `DATABASE_URL := DATABASE_URL_OWNER`, `fabrik-lifecycle.md:218`), so the
first cutover would be the moment the limit bites. Closing it before that cutover is the point — new projects are born
with the split, and a project cuts over onto it; the app's environment stops holding the owner credential only when
both are true. What the split does NOT close: a supply-chain compromise of the shared image — the companion and a
`migrate` service run the app's own image and hold the owner DSN legitimately, so a compromised dependency or base layer
executes there with it; the split narrows the credential to the request-less processes, it does not remove it from the
codebase (§ Constraints).

## What exists today (grounded)

- One env file per app, written three ways: `SSHDeployer._build_env_content` merges spec env + secrets over the
  existing `.env` read through `_read_env_file` (`src/fabrik/orchestrator/deployer_ssh.py:693-760`, `:898-920`) and
  every deploy path writes it with `_write_file_to_vps(name, ".env", …)` (`:362`, `:524`, `:607`, `:649`, `:686`);
  `inject_env` merges a registrar's keys into it and restarts (`:328-364`); `read_env` is the fail-closed reader
  (`:308-326`); `_persist_git_sha` read-merge-writes `GIT_SHA` into it (`:943-953`).
- The file lands root-owned: `_write_file_to_vps_path` writes a `tempfile.mkstemp` file (mode 0600 on this box,
  measured), `scp`s it (`src/fabrik/drivers/ssh.py:125-162`, no `-p`; scp carries the source mode), then `sudo mv`
  + `sudo chown root:root` (`deployer_ssh.py:962-1000`). No `chmod` is issued anywhere on the path — the mode is
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
  `spec_generator.audit_jobs_companion`, `spec_generator.py:148-165`), rendered by the partial above.
- The scaffold's `.env.example` names both DSNs with no value (`scaffold.py:3736-3744`); the WSL `.env.local`
  carries both as the same local role (`scaffold.py:2056-2057`); the saas and python `schema.sql` headers tell a
  human to run `psql … "$DATABASE_URL_OWNER" -f db/schema.sql` (`scaffold.py:2217-2219`, `:3595-3597`); the
  jobs module reads `DATABASE_URL_OWNER` from its environment and logs `audit_jobs: not_configured` when unset
  (`scaffold.py:3849-3860`).
- **Measured 2026-10-12 (read-only, this box):** 69 specs in `specs/services/`, 22 with `shape.needs_database: true`,
  0 with `shape.database_url_app_role`, 0 declaring an `audit-jobs` companion (`command grep -l audit-jobs
  specs/services/*.yaml`); 39 `compose.yaml` under `/opt/*/`, 0 naming `DATABASE_URL_OWNER`, 1 with a `migrate`
  service (transdoc); 0 code files under `/opt/*/{src,server,app,scripts,db,alembic,migrations}` (`.py .sh .ts
  .js .sql`, hub excluded) reading `DATABASE_URL_OWNER`; 0 of 11 `compose.dev.yaml` name it. **Denominator:** of the
  22 database specs, 17 have a clone under `/opt/` on this box (the measured set); 3 are image-sourced — evolution-api,
  zitadel, fabrik-smoke-test — and run the deployer's own compose (`deployer_ssh.py:1206-1214`, `env_file: .env`,
  their specs interpolating only `${DATABASE_URL}`), so they cannot read the owner key by construction; 2 —
  test-saas-log and translator — have no tree on the hub and are grepped on vps1 in the plan's one ssh (Phase C). The
  clones measured are the hub's, not what vps1 has checked out (`fabrik redeploy` pulls GitHub); the writer's log line
  (invariant 3) is the net for a reader that appears. The approval panel's wider walk (44,411 code and config files
  under 61 `/opt` directories, hub excluded) found one reader, `fabrik-lib/app-audit-log/schema.sql:5` (a header
  comment), and two TEXTS that tell projects to use the key from a scheduler — the synced pack
  `core/app-audit-log.md:39-41`, `:180` and fabrik-lib's `app-audit-log/README.md:53-58` (invariant 5). The hub's
  scaffold payload is therefore the only in-container reader, and it is not deployed anywhere yet.

## The delta

Invariants (the words the code and the docs will carry):

1. **`DATABASE_URL_OWNER` lives in `/opt/<name>/.env.owner` and nowhere else on the VPS.** The deployer writes it
   there; `.env` never carries it. The key set is one constant, `OWNER_ENV_KEYS = ("DATABASE_URL_OWNER",)`, beside
   `OWNER_ENV_FILE = ".env.owner"` in `spec_loader.py` — the lowest layer: the deployer (which already imports from it,
   `deployer_ssh.py:26`), the check and the loader's own validator import them — the single place a future owner-only
   key joins. A spec `env:` block naming an owner key is REFUSED by the loader (`ServiceSpec`, a `model_validator`):
   the templates render `env:` into EVERY service's `environment:` (`templates/python-api/compose.yaml.j2:42`, the
   companion partial `:29-31`), which would hand the app the very key the split removes; the registrar is the owner
   key's only source. A `secrets.from_env` key naming one is written by the deployer into the files and never rendered,
   so the writer routes it (invariant 3).
2. **The merged view is unchanged for every reader, in ONE round trip.** `_read_env_file` keeps its one probe and one
   `cat`: the probe answers `present`/`absent` for `.env` on its first line as today and a second line `owner` when
   `.env.owner` exists; the second command is today's `sudo cat <env>` alone, or `sudo sh -c 'cat <env> && echo && cat <owner>'` — the `&&` chain
   fails closed (a `;` chain exits with the LAST cat's status, so a missing `.env` beside an owner file returned the owner keys
   alone as the merged view — the plan's Phase A review, grader G2) and the `echo` is a
   SEPARATOR, because a plain two-file `cat` joins the last line of a `.env` that lacks a trailing newline onto the owner
   file's first line (executed at the approval panel on `_parse_env`: the owner key vanished from the parse and the owner
   DSN rode into `REDIS_URL`'s value, which the next write would have put back into `.env`) — so the owner file's keys
   parse last and win a shared key. `read_env`, `_preserve_minted_secrets` and `_build_env_content` therefore see today's view with the
   owner key folded in, and the app-role step's `env.get("DATABASE_URL_OWNER")` and every cutover/rollback/backfill
   branch read exactly what they read today. The one-call invariant at creation (`infrastructure.py:873`) holds — the
   owner password is on disk before anything below it can fail — because the owner file is written FIRST.
3. **One writer, so no path resurrects the key.** `_write_env_files(path, merged, write)` splits by `OWNER_ENV_KEYS`,
   writes `.env.owner` first (only when the owner half is non-empty), then `.env` without any owner key, and logs
   `env: %d owner key(s) kept in .env.owner for %s`. `inject_env`, the four deploy paths and `_persist_git_sha` (which
   read-merge-writes `GIT_SHA` on every redeploy, `deployer_ssh.py:943-953`) all write through it: a project whose `.env`
   still carries the key gets it moved on its next `fabrik apply` or redeploy, with no flag and no runbook step, and a
   stale copy left in `.env` is dropped by the next write while the owner file's value wins the merged read. A `secrets.from_env`
   key that names an owner key is routed the same way; a spec `env:` key naming one is refused by the loader (invariant 1).
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
   command runs (ods-27, ods-28). `required: false` keeps the first-boot ordering `core/30-ops.md:236` describes
   — the registrar writes the files AFTER the first `up`, so a required file would fail `--wait` before it exists;
   with it absent the jobs module logs `not_configured` and idles until the restart `inject_env` performs, exactly as
   `DATABASE_URL` does today (`scaffold.py:3234-3242`). App services keep the plain `- .env`.
5. **The scaffold emits the declaration only for the owner's consumers:** the audit-jobs companion
   (`scaffold.py:4186-4191` and the partial, through a new `CompanionService.owner_env: bool = False` that
   `audit_jobs_companion` sets `True`); every other service is untouched. A project adding its own `migrate` service
   copies the three lines and has its migration tool read `DATABASE_URL_OWNER` from the environment — Alembic's `env.py`,
   the shape `fabrik app-role-check` already requires (`app_role_check.py:17-24`) — and runs it as `docker compose run
   --rm migrate alembic upgrade head`: "the command passed by `run` overrides the command defined in the service
   configuration" (ods-63), so a hand-off written into `command` (`sh -c 'DATABASE_URL="$$DATABASE_URL_OWNER" exec …'`,
   the dollar escaped because compose interpolates `$VAR` in `command` strings and `$$` is the one literal dollar,
   ods-62) is bypassed by the very invocation the packs prescribe; and the app service, which no longer holds the key,
   must never be the `<svc>` of that command. The lifecycle runbook names it as the cutover's step 0. The rule-pack
   sentences this breaks are infra's (sync surfaces), amended on fleet's ONE D-441 request: `core/30-ops.md:161` (a
   companion "overriding only `command` + `container_name` + `memory`" — gains the owner env file as the one further
   override), `core/30-ops.md:445` and `core/10-python.md:297`, `:305` (`docker compose run --rm <svc> alembic upgrade
   head` — `<svc>` becomes "a service that declares `.env.owner`"), and `core/app-audit-log.md:39-41`, `:180` (retention
   "from the project's scheduler, as the database OWNER" — only a service declaring `.env.owner`, the audit-jobs
   companion, or a host shell under `sudo` has the key); fabrik-lib gets the same request for
   `app-audit-log/README.md:53-58`.
6. **Both env files are written root-owned 0600, by name.** `_write_file_to_vps_path` keeps its signature and, when the filename is
   `.env` or `.env.owner`, prefixes its command with `sudo chmod 0600 <tmp> && ` — the mode is set on the remote temp
   file BEFORE the `mv` (which keeps it; the `chown` does not touch it), so the file never sits at its final path wider
   than 0600; every other file keeps today's command byte-for-byte. The mode no longer rests on the temp file's 0600 carried by `scp`, which a stale remote tmp file under a recycled pid
   (`/tmp/fabrik-<pid>-<name>`, `deployer_ssh.py:975-997`) would override.
7. **Compose interpolation of the owner key stops, by design, and the check says so.** Compose substitutes `${VAR}`
   in a compose file from the shell and the project `.env` beside `compose.yaml`, never from a service's `env_file`
   entries (ods-60, ods-61), so after the move `environment: DATABASE_URL: ${DATABASE_URL_OWNER}` — the form
   `fabrik app-role-check` suppresses today as the canonical hand-off (`src/fabrik/app_role_check.py:40-48`, `:470-490`)
   — would resolve to an empty value and let a migration run against no DSN. The check turns that classification into a
   FINDING with the remedy of invariant 5 — and it ACCEPTS the remedy: a compose service whose `env_file` names
   `.env.owner` (the long-syntax `path:` or the plain string, any spelling `normpath` reduces to it) is an OWNER CONSUMER; its
   `compose service named migrate` finding is skipped and a line finding inside its block is dropped only while the line
   names no bare `DATABASE_URL` and the block shares no YAML anchor with a non-consumer (as built — the plan's Phase B review
   narrowed the rule written here); alembic's connection source is scanned on its own (`env.py`), a prisma/drizzle/django
   tool's config is not — the declaration is the evidence (backlog W-94a3b4df). Executed at the approval
   panel on today's scanner: the remedy shape yields TWO findings — `compose service named migrate` (an `env_file` entry
   never matches the owner token) and `alembic upgrade/downgrade` on the `command` line — so without this rule the split
   would make every cutover of a project with a `migrate` service refuse at `infrastructure.py:1177-1182`. The mirror
   is a finding too: an alembic env whose connection source is the owner key while NO compose service declares
   `.env.owner` — `no compose service loads .env.owner` — because after the split that `env.py` reads an empty value in
   every service. Measured 2026-10-12: 0 of 39 `/opt/*/compose.yaml` use the interpolation form, so the flip breaks no
   live project; a project that cuts over later meets the finding in its pre-cutover check.

Touchpoints:

| Where | Change |
|---|---|
| `src/fabrik/orchestrator/deployer_ssh.py:898-920` (`_read_env_file`) | the two-line probe and the one-file `cat` or the SEPARATED, fail-closed two-file read (`cat <env> && echo && cat <owner>`); returns the merged view; signature unchanged |
| `deployer_ssh.py:328-364` (`inject_env`), the four deploy paths' `.env` writes (`:524`, `:607`, `:649`, `:686`) and `_persist_git_sha` (`:943-953`) | every `.env` write goes through the new `_write_env_files` (owner first, then `.env` without owner keys, one log line); `_build_env_content` (`:693-760`) is unchanged |
| `deployer_ssh.py:962-1000` (`_write_file_to_vps_path`) | `sudo chmod 0600 <tmp> && ` BEFORE the `mv` for `.env` and `.env.owner` by filename; signature unchanged. The `:1217-1223` comment ("interpolates ${VAR} in `command:` from env_file") corrected: the source is the project `.env` (ods-60, ods-61) — the two coincide only for an image-sourced app |
| `src/fabrik/app_role_check.py:40-48`, `:462-490`, `:590` | the `${DATABASE_URL_OWNER}` value classification becomes a finding with its remedy; a service declaring `.env.owner` is the accepted owner consumer (its `migrate` and `command`-line findings suppressed); an owner-sourced alembic env with no declaring service is a finding; docstring and comment rewritten |
| `src/fabrik/spec_loader.py` (`CompanionService`) and `src/fabrik/spec_generator.py:148-165` | `OWNER_ENV_KEYS` and `OWNER_ENV_FILE` (the constants' home); `CompanionService.owner_env: bool = False`; `ServiceSpec` refuses an owner key in `env:`; `audit_jobs_companion` sets `owner_env` |
| `templates/_partials/_companion_service.yaml.j2:17-18` | the long-syntax `env_file` block under `{% if c.owner_env %}`; header sentence rewritten |
| `src/fabrik/scaffold.py:4186-4191` | the committed companion carries the same block |
| `scaffold.py:2217-2219`, `:3595-3597`, `:3736-3744` | the schema headers and `.env.example` comment say where the owner DSN lives; the headers' apply line is ONE `sudo sh -c '…'` sourcing both files before `psql` (both are root 0600 — a plain `. ./.env.owner` is `Permission denied` for a non-root operator, and a root shell sourcing them would keep the DSN in its environment and history); `_COMMON_GITIGNORE_PATTERNS` (`scaffold.py:665-669`) gains `.env.owner` |
| `docs/operations/fabrik-lifecycle.md:142`, `:203-205`, `:230-238`, `:253-259` | `:142`'s `<svc>` is a service that declares `.env.owner`; the two-file layout; the runbook's step 0 (declare `.env.owner`, have the tool read the key from its environment — Alembic's `env.py` — and run `docker compose run --rm <that service>`, never the app service; the interpolation form and a hand-off in `command` no longer work, the check reports the first); "The limit" becomes "What the split does not cover" (socket and root, a supply-chain compromise of the shared image; the owner credential leaves the app env only at cutover); `:257-259` says a pinned `DATABASE_URL` in `env:` is REMOVED, not moved to `DATABASE_URL_OWNER`, which the loader refuses |
| `.windsurf/rules/core/30-ops.md:161`, `:445`, `core/10-python.md:297`, `:305`, `core/app-audit-log.md:39-41`, `:180` (infra's sync surfaces) | ONE D-441 request mail: the companion sentence gains "plus the owner env file `.env.owner` in `env_file` where the companion needs the owner DSN"; the three `docker compose run --rm <svc> alembic upgrade head` lines name `<svc>` as a service that declares `.env.owner`; the retention sentences name the declaring service or a host shell under `sudo` as the only holders of the key |
| `/opt/fabrik-lib/app-audit-log/README.md:53-58` (fabrik-lib's) | a D-441 request mail: the apply runs under `sudo sh -c` sourcing both files, or from a service declaring `.env.owner` |
| `docs/operations/credential-recovery.md:121`, `templates/node-api/.gitignore:2-3`, `templates/saas-skeleton/.gitignore:23-27`, `templates/mobile-app/.gitignore:13` | the recovery path scp's `.env` AND `.env.owner` off vps1 (the owner password is otherwise unrecoverable, `infrastructure.py:1121-1124`); the three template gitignores list `.env.owner` (`/opt/<name>` on the VPS is a git working tree — `deployer_ssh.py:419` — so an un-ignored file shows as untracked there and in every clone) |
| `docs/CONFIGURATION.md:245-254`, `templates/scaffold/docs/CONFIGURATION_TEMPLATE.md:32-33`, `:119-153`, `OPERATIONS_TEMPLATE.md:191`, `RESILIENCE_TEMPLATE.md:477-478`, `docs/reference/modules/drivers.md:238` | the sentence "both DSNs live in `.env`" is replaced wherever it appears |

Code estimate: `deployer_ssh.py` ≈ 85 lines, `spec_loader.py` ≈ 15 (the two constants, `owner_env`, the `env:`
validator), `spec_generator.py` ≈ 2, `app_role_check.py` ≈ 40 (the finding, the acceptance rule, its mirror),
`scaffold.py` ≈ 27 (compose block, three doc strings, the gitignore pattern), the Jinja partial ≈ 6 — ≈ 175 lines across FIVE `.py` files
(D-169's ceiling, met exactly) plus one template, tests excluded → `Size: small`. Round 1 of the plan review ruled
`spec_loader.py` and `spec_generator.py` two files, not one.

MIRROR (the shapes this change can break, and why each holds):
- a project whose compose does not declare `.env.owner` and whose code reads `DATABASE_URL_OWNER` from the
  environment — loses the key on its next apply. Measured 0 such projects (§ What exists today); the deployer
  logs every owner write so the one that appears later is visible in the apply log.
- a compose that INTERPOLATES the key — `environment: DATABASE_URL: ${DATABASE_URL_OWNER}` — reads it from the project
  `.env`, so the value becomes empty after the move (invariant 7). Measured 0 of 39 composes; the check reports the
  form from now on, and the runbook's step 0 names the replacement.
- the rule packs — `core/30-ops.md:161` (the companion sentence), `core/30-ops.md:445` and `core/10-python.md:297`,
  `:305` (`docker compose run --rm <svc> alembic upgrade head` — in the app service the owner key is now absent, so the
  first post-cutover migration fails on an empty DSN or falls back to the app role), `core/app-audit-log.md:39-41`,
  `:180` and fabrik-lib's `app-audit-log/README.md:53-58` (retention "from the project's scheduler, as the OWNER" — an
  in-app scheduler loses the key) — false for the split until infra and fabrik-lib land the amendments fleet requests
  (invariant 5).
- a spec `env:` block carrying an owner key — rendered into every service's `environment:` by the templates, so the
  deployer's routing alone would not keep it from the app: the loader refuses it (invariant 1), and
  `fabrik-lifecycle.md:257-259` stops telling the operator to move a pinned `DATABASE_URL` there.
- the manual recovery path — `credential-recovery.md:121` scp's `/opt/<svc>/.env` off vps1; after the split that loses
  the owner password, which `infrastructure.py:1121-1124` cannot recover: the sentence names both files.
- the VPS working tree — `/opt/<name>` is a git checkout (`git reset --hard`, `deployer_ssh.py:419`, leaves untracked
  files alone); an un-ignored `.env.owner` shows as untracked there and in every clone, so the scaffold's common
  gitignore block and the three template `.gitignore`s list it.
- `_persist_git_sha` — read-merge-writes `.env` on every redeploy (`deployer_ssh.py:943-953`); through the shared writer
  it keeps the owner key out of `.env` instead of writing the merged view back (the trap round 1 named).
- a host-side `. .env` that expected the key (the schema.sql header, a runbook) — now sources two files under `sudo`
  in one line (both are root 0600); every such text is in the touchpoints table.
- the WSL `.env.local` — untouched; both keys stay there (one local role), by `scaffold.py:2056-2057`.
- `fabrik app-role-check` and `fabrik audit` reading `.env` — read the merged view — `_read_env_file` itself
  returns it, so `_preserve_minted_secrets`'s direct call (`deployer_ssh.py:265`) sees the owner key too and needs
  nothing from it (mint-once keys are never owner keys).
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
  automatic, logged move is reversible by one constant plus one deletion — `OWNER_ENV_KEYS = ()` sends every key back
  to `.env` on the next write, and `.env.owner` is removed per project by a deletion that checks the write-back
  FIRST — `sudo sh -c 'grep -q "^DATABASE_URL_OWNER=" /opt/<name>/.env && rm -f /opt/<name>/.env.owner'` — because the merged read cats the owner file LAST and a stale one would shadow every later
  write of the key, while a deletion before the write-back would lose the only copy of the owner password
  (§ Decisions taken) — and the plan's grader
  asserts the owner write is logged.
- **(F) keep `${DATABASE_URL_OWNER}` interpolation working by passing the owner file to every `docker compose`
  invocation** (`--env-file .env --env-file .env.owner`) — touches every compose call site in the deployer and the
  redeploy path, needs an owner file to exist for every app (database or not) or a per-site existence test, and
  re-opens interpolation of the owner key into any service that references it; the measured user count of the form is
  0, so the check reports it and the runbook names the `env_file` declaration plus the tool reading the key from its
  environment (Alembic's `env.py`) instead (invariants 5 and 7).
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
or rollback it cannot ground, as today — a file that goes missing LATER idles the companion the same way, which is
today's behaviour for the key absent from `.env` (the panel's Opus #8, recorded: the deployer rewrites the file on every
apply and redeploy, and the app-role step fails closed; no code). Retirement: if the fleet ever moves to a secret store that injects into
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
| `migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes.` | `.windsurf/rules/core/30-ops.md:436` |
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
  legitimate process; the item's threat — code executing in the APP container — reaches none of them. What stays open,
  by design: the companion and a `migrate` service run the app's own image (`core/30-ops.md:161`), so a SUPPLY-CHAIN
  compromise of that image — a dependency, a base layer — executes in a process that legitimately holds the owner DSN;
  the split narrows the credential to the request-less processes (no HTTP input reaches them), it does not close that
  class.
- Both files stay `root:root 0600` on the host, by an explicit `chmod` (invariant 6); the deployer writes them, nobody
  edits them by hand (`core/35-security-auth.md:307` governs the backup if anyone must).
- Until a project cuts over, `DATABASE_URL` in its `.env` IS the owner DSN (`infrastructure.py:876-878`), and after a
  rollback it is again (`fabrik-lifecycle.md:218`): the split removes the owner KEY from the app's environment; the
  owner CREDENTIAL leaves it only with the cutover. The docs say so where they describe the limit.
- Compose `${VAR}` interpolation reads the project `.env`, never a service's `env_file` (ods-60, ods-61): the owner key
  is not interpolable after the split, and `fabrik app-role-check` reports the form (invariant 7).
- No new env var, port, service or dependency; `.env.example` keeps naming both DSNs with no value.

## fabrik-lib verdict

One line: no fabrik-lib module covers deploy-time env delivery (the hub is the deploy control plane,
`agents-fabrik.md:80-86`); nothing to vendor or enhance — BUILD in the hub, five code files and one template.

## External dependencies

Docker Compose on the fleet (measured 2.40.3, `deployer_ssh.py:1217`): `env_file` list + long syntax with
`required` — ledger rows ods-21 to ods-40 (seat A); file secrets' limits — ods-1 to ods-16 (seat B); libpq
password files — ods-17 to ods-20; the practice sources — ods-41 to ods-59 (seat C); the interpolation sources,
read by the lead in the plan review's round 1 — ods-60, ods-61; `docker compose run` overriding `command` — ods-63.
Primary sources the design rests on, as the ledger cites them: Compose `env_file`
(https://docs.docker.com/reference/compose-file/services/#env_file — the list order, `required`), Compose `secrets`
(https://docs.docker.com/reference/compose-file/services/#secrets — `uid`/`gid`/`mode` ignored without Swarm),
interpolation sources (https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/),
`docker compose run` (https://docs.docker.com/reference/cli/docker/compose/run/). No new service, no cost.

## Shape / infra implications

None to `shape:`. One new file per database-backed app directory on each VPS, root-owned 0600.

## Documentation landing sites

`docs/operations/fabrik-lifecycle.md` § App-role cutover and rollback (the layout, the runbook's step 0, the
rewritten limit, the interpolation form the check now reports) · `docs/CONFIGURATION.md` § Project database DSNs · the
three scaffold doc templates and `drivers.md` rows named above · `CHANGELOG.md` · `docs/DECISIONS.md` (one row,
reversible — minted by `/fabrik-plan-review`'s approval panel, D-613, not by a build phase) · the five rule-pack sentences
(`core/30-ops.md:161`, `:445`, `core/10-python.md:297`, `:305`, `core/app-audit-log.md:39-41` + `:180`) through infra
(ONE D-441 request mail carrying each replacement sentence) · fabrik-lib's `app-audit-log/README.md:53-58` through
fabrik-lib (a D-441 request) · `docs/operations/credential-recovery.md:121` · the three template `.gitignore`s · the deployer's and the check's own docstrings. No new
reference doc: the subsystem is the deployer, already documented.

## Validation

Red-first graders in `tests/`: (1) `inject_env({"DATABASE_URL": a, "DATABASE_URL_OWNER": o})` writes `o` to
`.env.owner` first and `a` to `.env`, one restart; (2) `read_env` returns the merged view in one probe and one `cat`, the
owner file winning a shared key, and a bare `present` answer issues today's `cat` exactly; (2b) the separated read —
the two-file command carries the `&& echo &&` separator (fail-closed, G2), and a `.env` without a trailing newline beside an owner file still
parses to both keys intact (the plain `cat` join kept as the negative half); (3) `_write_env_files` on a
merged view carrying the key writes the owner file first, keeps the key out of `.env` and logs it; (3b) every writer —
the four deploy paths and `_persist_git_sha` — goes through it (parametrized, red on today's code); (4) the rendered
companion for a database spec carries the long-syntax block and the app service does not; (5) `_validate_compose`
accepts the long syntax (executed in the spec's probe 2); (6) `.env` and `.env.owner` get `chmod 0600` on the temp file BEFORE the `mv`, other files do
not; (7) the `.env.example` and schema headers name both files; (8) `fabrik app-role-check` reports
`DATABASE_URL: ${DATABASE_URL_OWNER}` as a finding naming `.env.owner`; (9) the check ACCEPTS the remedy — a `migrate`
service declaring `.env.owner` with an owner-reading `env.py` yields NO finding (two today, executed at the panel);
(10) an owner-reading `env.py` with no declaring service yields the `no compose service loads .env.owner` finding;
(11) a spec `env:` naming `DATABASE_URL_OWNER` is refused by the loader; (12) a scaffolded `.gitignore` lists
`.env.owner`. Live check at plan time: `stat` of one
project's `.env` on vps1 (evidence for the chmod, no longer a dependency).

## Open / blocking unknowns

- R1 (open, cheap — evidence only): the live mode of `/opt/<name>/.env` on vps1 — one read-only `stat`; whatever it
  reads, both env files are now chmod'ed explicitly (invariant 6), so a 0644 is recorded as the defect the chmod closes,
  not a widening. Resolution: plan Phase C step 1.
- R2 (resolved by measurement, denominator stated): 0 code readers in the 17 of 22 database projects cloned on this
  box, 3 image-sourced projects cannot read it by construction, 2 (test-saas-log, translator) are unmeasured here and
  are grepped in Phase C's one ssh; the move needs no gate — the writer's log line is the net for a reader that appears.
- R3 (resolved): Compose `env_file` long-syntax `required` exists since 2.24.0 (ods-24, ods-26); the fleet
  measured 2.40.3 (`deployer_ssh.py:1217`), so the long syntax is available and no fallback is needed.

## Decisions taken

Reversible: the owner DSN moves to `.env.owner`, delivered only to services that declare it, with no gate — one
D-row at approval. The reversal is one constant plus one deletion: `OWNER_ENV_KEYS = ()` makes `_split_env` route every key to `.env`
so the next write of each project puts the key back into `.env`; the owner file MUST then be deleted per project, on each
host (spokes included), by a command that checks the write-back happened first — `sudo sh -c 'grep -q "^DATABASE_URL_OWNER=" /opt/<name>/.env && rm -f /opt/<name>/.env.owner'` — because the merged read cats it last, so a stale copy left behind would win over every later write of the key
(round 2 of the plan review executed that shadowing), and a deletion BEFORE the write-back would lose the only copy of
the owner password (`fabrik-lifecycle.md:219`). Rejected at the approval panel: the writer deleting `.env.owner` itself
when `OWNER_ENV_KEYS` is empty — an extra ssh call on every write of every project (round 1's 17 scripted fixtures
again) to automate a reversal nobody has run. Rejected: file secrets, passfile, env override, a per-project flag,
hub-run migrations, keeping compose interpolation of the owner key alive.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"The owner DSN shares the project `.env` with the app DSN"* (W-4e74ea9d) | IN | § Goal, § The delta 1 |
| I2 | *"holds against the app's code paths and SQL injection, not against code execution inside the container"* | IN | § Why this exists, § Personas (threat actor) |
| I3 | *"Closing it means an env file mounted only into the migrate and jobs services"* | IN | § The delta 4-5 |
| I4 | the brief's candidates (A) second env file · (B) compose secrets · (C) environment override | IN | § The delta (A), § Rejected alternatives (B, C) |
| I5 | *"the deployer must never move the key out of `.env` for a project whose compose does not read the second file"* (brief) | IN — CHANGED | § What exists today — measured 0 such projects; the gate is replaced by the logged automatic move, § Rejected (D) |
| I6 | *"how the WSL dev `.env` (both keys) stays unmodified in code"* (brief) | IN | § MIRROR |
| I7 | *"how `fabrik apply`'s first-deploy ordering … survives"* (brief) | IN | § The delta 2, 4 |
| I8 | *"how rollback (`DATABASE_URL` := owner DSN) reads the second file"* (brief) | IN | § The delta 2 |
| I9 | *"how the docs templates … and `fabrik-lifecycle.md` § The limit change"* (brief) | IN | § Touchpoints, § Documentation landing sites |
| I10 | *"Measure the inventory read-only … never touch a VPS, a database or another repo"* (brief) | IN | § What exists today (measured); R1 names the one live `stat` for the plan |
| I11 | operator standing ruling D-746/D-558: *"do not stop again for the things you can handle yourself"*; Pool OFF (D-181) | IN | this run: native seats, no operator question; the approval gate is the panel's (D-613) |
| I12 | plan review round 1 (rules-O1, rest-S1, rules-O3): a second ssh probe for the owner file breaks 17 scripted test fixtures | IN — CHANGED | invariant 2 — one probe (two lines) + one `cat` naming both files |
| I13 | plan review round 1 (rules-O5): compose `${DATABASE_URL_OWNER}` interpolation reads the project `.env` | IN | invariant 7, § MIRROR, § Rejected (F) |
| I14 | plan review round 1 (rules-O6): `core/30-ops.md:161` contradicted by the owner_env companion | IN | invariant 5, § Documentation landing sites (infra's amendment) |
| I15 | plan review round 1 (rules-O7, O11, O12, O8): the reversibility sentence, the un-chmod'ed `.env`, the Goal's overclaim, the file count | IN | § Decisions taken, invariant 6, § Goal + § Constraints, the Size line |
| I16 | approval panel (Opus #1, Fable C2 — CONFIRMED by execution): a two-file `cat` joins lines when `.env` lacks a trailing newline — the owner key vanishes and the owner DSN rides into another value, which the next write puts into `.env` | IN | invariant 2 — the separated read |
| I17 | approval panel (Fable C1 — CONFIRMED by execution; Opus #2): today's check reports TWO findings on the remedy shape, and `docker compose run --rm <svc> …` replaces `command` (ods-63), so the hand-off belongs in `env.py` + `env_file`, never in `command`; three more pack sentences and the audit-log pack/README tell projects to run as owner from the wrong process | IN | invariants 5 and 7 (the acceptance rule and its mirror), § Documentation landing sites |
| I18 | approval panel (Opus #4): the templates render a spec's `env:` into every service's `environment:` | IN | invariant 1 (the loader refuses an owner key in `env:`), § MIRROR |
| I19 | approval panel (Opus #5, #6, #7, #9, #10; Fable C3–C6): the reversal's order, the denominators, the sudo one-liner header, chmod before the `mv`, the Size line, the supply-chain limit, the MIRROR's `_read_env_file` sentence, `credential-recovery.md:121`, the gitignore patterns, the `:1217` comment | IN | § Decisions taken, § What exists today, invariant 6, § Constraints, § MIRROR, Touchpoints |
| I20 | approval panel (Opus #8): `required: false` lets a later-missing owner file idle the companion silently | OUT-OF-SCOPE — RECORDED, not this change's defect: identical to today's key-absent behaviour; the deployer rewrites the file on every apply; the app-role step fails closed on a missing owner key | § Lifecycle (Degradation) |
