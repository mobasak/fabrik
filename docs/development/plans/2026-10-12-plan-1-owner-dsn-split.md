# Plan — the owner DSN leaves the app containers' environment (W-4e74ea9d)

Status: EXECUTED 2026-10-12 (Phase A c2ec25e4c + 2935a2da9 · Phase B 2de2c1097 + 1e93f89cf, 2b9aefffe, 67a843ccb, 7dd78e1c9, dbf0e5c13 · Phase C: Finish review fixes 1a82aa9b7, a6d0da75c, c60a0ef10; scoped reviews A 12→0, B 21→9→2→2→1→0; Finish /fabrik-review 20→4→0, receipt docs/development/reviews/2026-10-12-plan-1-owner-dsn-split-review.md; final_gate --check success) — approved by the Opus + Fable panel at /fabrik-plan-review's gate (D-754, D-613). Review-driven deviations: the two-file read is `&& echo &&` (fail-closed), the deploy paths hand the merged dict to `_write_env_files` (G7), `_deploy_template` renders the secrets without the owner keys (G32), the hand-off scan runs only over a compose that parses (G30), scaffold.py spells the owner file through `OWNER_ENV_FILE` (G31). Deferred: W-94a3b4df (non-alembic connection sources), W-c03bf797 (first-move WARNING), W-8dd25072 (mktemp staging). R1 (the live `.env` mode) unmeasured — none of the four named paths exist on vps1; the first post-merge apply reads it back.
Profile: small
**Owner:** fleet
**Surface:** `git rev-parse HEAD` = f333de437 at authoring; `src/fabrik/orchestrator/deployer_ssh.py` 1,273 lines,
`src/fabrik/scaffold.py` 7,923 lines (the touched regions are cited by line below)

Spec: `docs/superpowers/specs/2026-10-12-owner-dsn-split-design.md` (DRAFT at f333de437; `Size: small`, `Profile: delta` —
`/fabrik-plan-review` grades its sections together with this plan and flips both; the approval row is minted there, D-613).
Source: infra's backlog row of 2026-09-24 from the audit-log-everywhere work (D-385, D-393, D-410) → work item W-4e74ea9d.
Estimated diff: ≈175 code lines in FIVE `.py` files plus one Jinja template, tests excluded — `deployer_ssh.py` ≈85
(`_split_env`, the two-line probe + the separated read in `_read_env_file`, `_write_env_files`, its six callers, the
filename-keyed `chmod` before the `mv`, the `:1217` comment), `spec_loader.py` ≈15 (`OWNER_ENV_KEYS`, `OWNER_ENV_FILE`,
`CompanionService.owner_env`, the `env:` validator), `spec_generator.py` ≈2, `app_role_check.py` ≈40 (the
`${DATABASE_URL_OWNER}` hand-off becomes a finding with its remedy; the `.env.owner` acceptance rule; its
no-declaring-service mirror), `scaffold.py` ≈27 (the committed companion's env_file block, two schema headers, the
`.env.example` block, the gitignore pattern); `templates/_partials/_companion_service.yaml.j2` ≈6. Five code files is the
D-169 ceiling, met exactly (round 1 of the plan review ruled `spec_loader.py` and `spec_generator.py` two files, not one;
the panel's additions land in files already counted). Tests ≈260 lines in five existing files — File Scope's test set, `tests/test_spec_loader.py` included (WRITTEN for G14);
`test_deployer_git_sha.py` is run, never edited.

## What this plan is

Three inline phases the orchestrator codes itself in the fleet worktree; no coder is dispatched:

- **A — the deployer**: the owner key set, the second file `.env.owner` (written first, root-owned 0600), the merged
  `read_env`, the split `inject_env`, the automatic logged move out of `.env` — with their graders and the fallout
  updates to the tests that pin the one-file shape (spec § The delta 1-3, 6).
- **B — the scaffold, the check and the docs**: `CompanionService.owner_env`, the long-syntax `env_file` block on the
  audit-jobs companion only, the app-role check's `${DATABASE_URL_OWNER}` hand-off turned into a finding with its remedy and
  the `.env.owner` acceptance rule (with its no-declaring-service mirror) that keeps the remedy itself clean, the loader's
  refusal of an owner key in `env:`, the schema headers (one `sudo sh -c` line), `.env.example` and gitignore text, every
  doc sentence that says "both DSNs live in `.env`" plus the recovery path, and the two D-441 mails — infra for the five
  rule-pack sentences the split makes false, fabrik-lib for the audit-log README (spec § The delta 1, 4-5 and 7,
  § Touchpoints, § Documentation landing sites).
- **C — the live check and Finish**: the one read-only `stat` on vps1 (spec R1), the whole-plan `/fabrik-review`, the gate,
  the receipt.

Per phase: `/fabrik-review-scoped` on that phase's surface. At Finish: one heavy `/fabrik-review` (the `/fabrik-execute-plan`
D7 floor) and one receipt.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § Intake Inventory I1–I11 (10 IN, 1 CHANGED — the brief's per-project gate replaced by the measured automatic move) | IN as dispositioned there | Phases A and B, per the spec rows |
| I2 | *"Plan it as `Profile: small`"* (this run's brief) | IN | this header |
| I3 | the brief's mechanism list — `OWNER_ENV_KEYS`, merged `read_env`, split `inject_env`, `_build_owner_env_content`, `_read_env_file` `filename`, `_write_file_to_vps_path` `mode`, `CompanionService.owner_env`, the two emitters, the schema headers and `.env.example`, the docs | IN | Phase A (deployer), Phase B (scaffold, check + docs); the brief's `_build_owner_env_content` and `mode` parameter became `_write_env_files` (one writer for both files) and a filename-keyed `chmod` after round 1 (Phase A Interfaces) |
| I4 | *"Red-first graders per the spec's § Validation (seven), measured in a throwaway worktree"* | IN | Phase A steps 1-3 (G1–G7), Phase B steps 1-3 (G8–G11); red-on-revert in a throwaway worktree, Phase A step 5 and Phase B step 4 |
| I5 | *"Plan phase 1 owns the one live read-only check: `stat` of one project's `.env` on vps1 … if still unreachable record it as an assumption"* | IN | Phase C step 1 (spec R1) |
| I6 | *"never touch a VPS beyond that one stat, never a database, never another repo"* | IN | § Global Constraints |
| I7 | *"infra is re-running merge 01M4PKEAJY … say so in the close rather than filing a second request"* | IN | Phase C step 4 |
| I8 | Grounding finding (this run, Evidence Phase A): 6 call sites write `.env`; `tests/orchestrator/test_deployer_ssh.py` pins the LAST write and exact ssh call counts; `tests/orchestrator/test_deployer_git_sha.py:81-85` asserts `filename == ".env"` | IN | Phase A steps 3-4 (the fallout list), § Global Constraints (owner file written FIRST) |
| I9 | Grounding finding: `tests/test_scaffold_audit_log.py:279`, `:530`, `:558` pin the companion's `env_file` (`== [".env"]` at :530); `tests/test_scaffold_saas_backend.py:170` pins the saas services' `[".env"]` and must keep passing | IN | Phase B step 2 (G8–G10) |
| I10 | Review round 1 (rules-O1, rest-S1, rules-O3): a second probe+cat for the owner file breaks 17 scripted ssh fixtures in `tests/orchestrator/test_deployer_ssh.py` (`[present, content, '']` lists, `call_count == 1`) | CHANGED | the read stays ONE probe + ONE `cat`: the probe answers a second line for the owner file, the `cat` names both files — every scripted fixture answering `present`/`absent` + one content keeps its shape (Phase A Interfaces) |
| I11 | Review round 1 (rules-O5): Compose `${DATABASE_URL_OWNER}` interpolation in a service's `environment:` reads the project `.env`, not `env_file`, so the app-role check's suppressed "canonical hand-off" would resolve to an empty DSN after the move | IN | Phase B step 3 (`app_role_check.py`), spec § The delta 7, § MIRROR |
| I12 | Review round 1 (rules-O6): `core/30-ops.md:161` says a companion shares the app's env "overriding only command + container_name + memory" — the owner_env companion no longer satisfies that sentence; `.windsurf/rules/` is infra's sync surface | IN | Phase B step 5 (D-441 request mail to infra with the sentence), § Context Ledger |
| I14 | Approval panel (Opus #1, Fable C2 — CONFIRMED by execution on `_parse_env`): `sudo cat <env> <owner>` joins lines when `.env` lacks a trailing newline — the owner key vanishes and the owner DSN rides into `REDIS_URL`, which the next write puts into `.env` | IN | Phase A Interfaces (the separated read), G2, G2b |
| I15 | Approval panel (Fable C1 — CONFIRMED by execution on today's scanner: 2 findings on the remedy shape; Opus #2): Phase B as written removed the one accepted migrate shape and added none, so every cutover with a `migrate` service would refuse; `docker compose run --rm <svc> …` replaces `command` (ods-63) | IN | Phase B Produces (the acceptance rule, its mirror), G11–G13, the infra mail's five sentences, the fabrik-lib mail |
| I16 | Approval panel (Opus #4): the templates render a spec's `env:` into every service's `environment:` (`compose.yaml.j2:42`, the partial `:29-31`) | IN | Phase B Produces (the loader refuses an owner key in `env:`), G14; the constants move to `spec_loader.py` |
| I17 | Approval panel (Opus #5, #6, #7, #9, #10; Fable C3–C6): the reversal's order (a checked deletion), the denominators (17/22 cloned, 3 by construction, 2 on vps1), the sudo one-liner schema header, chmod BEFORE the `mv`, the Size line, the supply-chain limit, the MIRROR's `_read_env_file` sentence, `credential-recovery.md:121`, the gitignore patterns, the `:1217` comment, the plan's test-file count | IN | § Global Constraints, Phase A/B Produces, Phase C step 1, File Scope |
| I18 | Approval panel (Opus #8): `required: false` lets a later-missing owner file idle the companion silently | RECORDED — today's behaviour for the key absent from `.env`; the deployer rewrites the file on every apply; the app-role step fails closed (`infrastructure.py:1119-1125`) | spec § Lifecycle |
| I13 | Review round 1 (rules-O11, rest-S5): `.env`'s mode rested on the temp file's 0600 carried by `scp`, and a stale remote tmp file under a recycled pid keeps its own mode | IN | both env files are `chmod 0600` by name in `_write_file_to_vps_path` (Global Constraints, G5) |

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
  `src/fabrik/spec_generator.py`, `src/fabrik/app_role_check.py`, `src/fabrik/scaffold.py` and `templates/_partials/` are the
  hub's own code, none is a governance-sync trigger (`.pre-commit-config.yaml`'s `governance-sync` filter names
  `commands/_sources/`, `scripts/enforcement/`, `templates/governance/`, `.windsurf/rules/`, `.claude/hooks/` — read, not
  recalled, this run); `templates/scaffold/docs/*_TEMPLATE.md` are scaffold payload (fleet's beat). The ONE sync-surface
  sentence this change makes false — `.windsurf/rules/core/30-ops.md:161` — is infra's: Phase B sends the D-441 request
  with the replacement sentence and never edits the pack. No VPS is touched beyond Phase C's one read-only `stat`; no
  database; no other repo.
- **One round trip for the read, as today.** `_read_env_file` keeps ONE probe and ONE `cat`: the probe prints `present`
  or `absent` for `.env` on its first line and, on a second line, `owner` when `.env.owner` exists (a probe answer with
  no second line means no owner file — every scripted test fixture that answers a bare `present`/`absent` keeps its
  meaning); the second command is today's `sudo cat <env>` alone, or `sudo sh -c 'cat <env> && echo && cat <owner>'` (as built —
  the Phase A review made the chain `&&`, fail-closed) — the `echo` SEPARATES
  the files, because a plain two-file `cat` joins a `.env` lacking a trailing newline onto the owner file's first line
  (executed at the panel: the owner key vanished and the owner DSN rode into `REDIS_URL`) — so the owner file's keys
  parse LAST and win. No fixture gains an ssh call (round 1, rules-O1/rest-S1).
- **One writer for the two files.** `_write_env_files(path, merged)` splits by `OWNER_ENV_KEYS`, writes `.env.owner`
  FIRST (only when the owner half is non-empty), then `.env` (the app half, never an owner key), and logs one line
  `env: %d owner key(s) kept in %s for %s`. Every `.env` writer calls it — `inject_env`, the four deploy paths and
  `_persist_git_sha` — so no path can resurrect the key into `.env` from a merged read (round 1, rules-O4/O7). The owner
  password is on disk before anything below it can fail (the T04 invariant, `infrastructure.py:872-878`), and the tests
  that read the LAST `_write_file_to_vps` call still see `.env` (I8).
- **Both env files `root:root 0600`, by name.** `_write_file_to_vps_path` keeps its signature and prefixes
  `sudo chmod 0600 {tmp_remote} && ` when `filename` is `.env` or `.env.owner` (`deployer_ssh.py:962-1000`) — the mode
  is set BEFORE the `mv`, so the file never sits at its final path wider than 0600 (panel, Opus #9); every other file
  keeps today's command byte-for-byte. The mode no longer depends on the temp file's or on a stale remote tmp file's
  (round 1, rules-O11/rest-S5); R1's `stat` becomes evidence, not a dependency.
- **The merged view is the API**: `read_env` and `_read_env_file` return `.env` overlaid by `.env.owner`; every reader
  in `infrastructure.py` (`:1094-1096`, `:1114`, `:1126`, `:1187-1191`), `_preserve_minted_secrets` (`:265`) and
  `_build_env_content` (`:723`) are unchanged.
- **One key set**: `OWNER_ENV_KEYS: tuple[str, ...] = ("DATABASE_URL_OWNER",)` and `OWNER_ENV_FILE = ".env.owner"` at
  module level in `spec_loader.py` — the lowest layer: `deployer_ssh.py` (already importing from it, `:26`) and
  `app_role_check.py` import them, and the loader's own `ServiceSpec` validator refuses an owner key in a spec's `env:`
  block, because the templates render `env:` into EVERY service's `environment:` (`templates/python-api/compose.yaml.j2:42`,
  the partial `:29-31`) — the deployer's routing alone would hand the app the key (panel, Opus #4); a key joins the owner
  file by membership there and nowhere else (spec § The delta 1). Reversal is `OWNER_ENV_KEYS = ()` PLUS deleting
  `.env.owner` per project, on each host, by a command that checks the write-back FIRST —
  `sudo sh -c 'grep -q "^DATABASE_URL_OWNER=" /opt/<name>/.env && rm -f /opt/<name>/.env.owner'` — after the next write has put every key back into `.env`: the merged read cats the owner
  file LAST, so a stale one left behind would win over every later write of the key, and a deletion before the write-back
  would lose the only copy of the owner password (spec § Decisions taken; round 2 executed that shadowing; the panel
  rejected an automatic deletion in the writer — an ssh call on every write of every project).
- **Compose shape**: the long syntax is emitted only under `c.owner_env` / the committed companion; app services keep
  `env_file:\n  - .env` byte-for-byte (`tests/test_scaffold_saas_backend.py:170` keeps passing). `_validate_compose`
  never reads `env_file` (`deployer_ssh.py:1009-1163`, 0 hits — Evidence probe 2). Compose `${VAR}` interpolation reads
  the project `.env` beside `compose.yaml`, never an `env_file` entry (ledger ods-60, ods-61), so after the move
  `environment: DATABASE_URL: ${DATABASE_URL_OWNER}` resolves to an empty value: the app-role check classifies that
  value as a FINDING with the remedy (`env_file` naming `.env.owner` + the tool reading `DATABASE_URL_OWNER` from its
  environment, as Alembic's `env.py` already must — never a hand-off in `command`, which `docker compose run --rm <svc>
  <args>` replaces, ods-63), where today it suppresses it as the canonical hand-off (`src/fabrik/app_role_check.py:40-48`,
  `:470-471`); and the check ACCEPTS the remedy — a service whose `env_file` names `.env.owner` is the owner consumer: its
  `compose service named migrate` finding and the migration-tool pattern on its `command` line are suppressed (today's
  scanner reports both on the remedy shape — executed at the panel, 2 findings — so without the rule every cutover with
  a `migrate` service would refuse at `infrastructure.py:1177-1182`); the mirror — an owner-sourced alembic env while no
  service declares the file — is the finding `no compose service loads .env.owner`. Measured 2026-10-12: 0 of
  39 `/opt/*/compose.yaml` use the interpolation form.
- **Stdlib only**; no dependency file is touched (`core/10-python.md:30`); no new env var, port or service.
- **12-Factor on this surface**: III — two files, both granular env, no grouped set; XII — the one-off and the scheduled
  consumer get the owner DSN in the deployed environment, never from a laptop (`core/30-ops.md:436`); the rest not engaged.
- Tests: one per behaviour, watched-fail-first (`core/45-testing-strategy.md:20`, `:22`); the deployer graders mock
  `_write_file_to_vps`/`_write_file_to_vps_path` and `fabrik.drivers.ssh.ssh` exactly as `tests/orchestrator/test_deployer_ssh.py`
  does (`:456`, `:972`), asserting on the `(path, filename, content)` tuples and the ssh command strings; the scaffold
  graders render through `TemplateRenderer` and `create_project` as `tests/test_scaffold_audit_log.py` does; the check's
  graders build a repo in `tmp_path` as `tests/test_app_role_check.py` does (`:770-783`). Every grader is seen red —
  against today's code (G1–G3, G2b, G5–G9, G11–G15 — G5 and G2b by the command string, G9 by the absent `owner_env`,
  G12 by today's two findings, G13 by today's scan lacking the mirror finding, G14 by today's accepting loader, G15 by today's gitignore) or by
  the named mutant in Phase A step 5 (G4: the owner file written unconditionally, even empty) and Phase B step 4 (G10: the partial
  emitting the long syntax unconditionally). Red-on-revert runs in a throwaway worktree (`git worktree add --detach
  <scratch>/probe HEAD`), never in the shared checkout; the root conftest pins the checkout's `src`, so the probe runs
  its OWN `tests/` from inside the probe tree.
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
| `.windsurf/rules/core/30-ops.md` (FLOOR) | companions share image + env "overriding only `command` + `container_name` + `memory`" — a sentence the owner_env companion no longer satisfies: Phase B mails infra the amendment (the pack is a sync surface); first-boot DSN ordering; admin processes in the deployed env | `core/30-ops.md:161`, `:236`, `:436` |
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
| "migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes." | .windsurf/rules/core/30-ops.md:436 | XII |
| "every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one**" | .windsurf/rules/core/45-testing-strategy.md:20 | Behaviour Contract |
| "**Watched-fail-first** (for tests this change adds or modifies" | .windsurf/rules/core/45-testing-strategy.md:22 | Red first |

## Phase A — the deployer: the owner file, the merged read, the split write — ✅ EXECUTED 2026-10-12 (c2ec25e4c; review fixes 2935a2da9)
Appetite: 120

**Interfaces — Produces** (all in `src/fabrik/orchestrator/deployer_ssh.py`; `spec § The delta` 1-3, 6):
- `OWNER_ENV_KEYS: tuple[str, ...] = ("DATABASE_URL_OWNER",)` and `OWNER_ENV_FILE = ".env.owner"` — module constants
  in `src/fabrik/spec_loader.py` beside `CompanionService` (`:818`), imported by `deployer_ssh.py` (which already imports
  `Source, SourceType` from there, `:26`) and, in Phase B, by `app_role_check.py` and the loader's own validator; the
  only places the key set and the filename are spelled.
- `_split_env(env: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]` — `(app, owner)` by membership in
  `OWNER_ENV_KEYS`; pure, no I/O.
- `_read_env_file(path: str, _ssh: Any) -> dict[str, str]` (`:898-920`) keeps its signature and its ONE probe + ONE `cat`,
  and returns the MERGED view. The probe's inner command becomes `[ -f <env> ] && echo present || echo absent;
  [ -f <owner> ] && echo owner || true` (one `sudo sh -c`, as today); the answer is parsed by lines: line 1 is
  `present`/`absent` exactly as today (anything else raises `DeployError` as today), a second line `owner` means the
  owner file exists, no second line means it does not. `absent` returns `{}` even when an owner line follows: the
  deployer always writes `.env` whenever it writes the owner file, so an orphan `.env.owner` survives on disk untouched
  (the owner write happens only for a non-empty owner half) and is read the moment `.env` exists. The second command
  is `sudo cat <env>` when no owner line came back — today's command byte-for-byte — and `sudo sh -c 'cat <env> && echo && cat <owner>'`
  (as built; the Phase A execution notes record the `;` → `&&` change)
  when it did: the `echo` SEPARATES the two files (a plain `cat <env> <owner>` joins the last line of a `.env` lacking a
  trailing newline onto the owner file's first line — executed at the panel on `_parse_env`: `REDIS_URL` absorbed
  `DATABASE_URL_OWNER=…` and the owner key vanished, I14), so the owner file's keys parse last and win a shared key.
- `SSHDeployer.read_env(ctx)` (`:308-326`) is unchanged in text: it returns the merged view through `_read_env_file`.
- `_write_env_files(path: str, merged: dict[str, str], write: Callable[[str, str, str], None]) -> None` — splits
  `merged`; when the owner half is non-empty, `write(path, OWNER_ENV_FILE, _format_env(owner))` FIRST; then
  `write(path, ".env", _format_env(app))`; logs `env: %d owner key(s) kept in %s for %s`. `write` is a one-line
  adapter over `_write_file_to_vps(name, …)` for `inject_env`, `_persist_git_sha`, `_deploy_template`, `_deploy_git` and
  `_deploy_docker` — the five writers that call `_write_file_to_vps` today, whose tests patch only that name
  (`tests/orchestrator/test_deployer_ssh.py:456`, `test_deployer_git_sha.py:107`) — and `_write_file_to_vps_path` itself
  only for `_deploy_local`, which writes through it today (`:686`, patched at `:972`). A deploy path calling the path
  writer directly would reach the live `scp` under test (round 2, rules-O14: 15 failures, 2 with the adapter).
- `SSHDeployer.inject_env(ctx, env_vars)` (`:328-364`): `merged = self.read_env(ctx); merged.update(env_vars);
  _write_env_files(…)` inside `_target_vps_env`, then `_compose_up` — one restart.
- `_build_env_content(...)` (`:693-760`) is unchanged: it returns the merged content; the four deploy paths
  (`_deploy_template` `:519-524`, `_deploy_git` `:604-607`, `_deploy_docker` `:645-649`, `_deploy_local` `:685-686`) parse
  it back (`_parse_env`) and call `_write_env_files` in place of their `_write_file_to_vps(…, ".env", …)` line.
- `_persist_git_sha` (`:943-953`) calls `_write_env_files` too: the merged read now carries the owner key and the
  writer keeps it out of `.env`; its fail-open contract (log and write nothing on a failed read or write) is unchanged.
- `_write_file_to_vps_path(path, filename, content)` (`:962-1000`, signature unchanged): the command at `:997` is
  prefixed with `sudo chmod 0600 {tmp_remote} && ` when `filename in (".env", OWNER_ENV_FILE)` — the mode lands on the
  temp file BEFORE the `mv` (the `mv` keeps it, the `chown` does not touch it), so the file never sits at `{dest}` wider
  than 0600; every other filename issues today's string. The comment at `:1217-1223` ("interpolates ${VAR} in `command:`
  from env_file") is corrected in the same edit: the source is the project `.env` beside `compose.yaml` (ods-60, ods-61)
  — for an image-sourced app the two files coincide, which is why the 2.40.3 check could not tell them apart.

Steps:
1. **Highest-risk test first — G1 (the split write).** In `tests/orchestrator/test_deployer_ssh.py`, beside the inject_env
   tests (`:614-636`): `SSHDeployer().inject_env(ctx, {"DATABASE_URL": a, "DATABASE_URL_OWNER": o})` with `mock_ssh`
   answering `absent` then `""` → `mock_write.call_args_list` is `[(name, ".env.owner", <o only>), (name, ".env", <a only>)]`
   in that order, `_parse_env` of each content holding exactly those keys, and exactly one `docker compose up` ssh call.
   Run it: RED on today's code (one write, both keys in `.env`).
2. Implement the Interfaces above (the two constants in `spec_loader.py`, the rest in `deployer_ssh.py`); run G1 → GREEN.
   `ruff check` + `ruff format --check` on both files.
3. Graders G2, G2b, G3–G7, each written and watched red — on today's code for G2 (today's `cat` names one file), G2b
   (today's second command is a plain `cat`), G3 (today writes the key into `.env`), G5 (today's command string lacks the
   `chmod` prefix), G6 (today's probe parse rejects a two-line
   answer) and G7 (today each deploy path writes the owner key into `.env`); G4 is GREEN on today's code by construction
   (one key, one write) and is proven by its step-5 mutant, never claimed red before it — then green:
   - G2 (the merged view, one round trip): `mock_ssh` answering `present\nowner\n` then `DATABASE_URL=a\nDATABASE_URL_OWNER=stale\n\nDATABASE_URL_OWNER=o\n`
     (what the separated read prints when `.env` still carries a stale copy) → `read_env(ctx) == {"DATABASE_URL": a,
     "DATABASE_URL_OWNER": o}` and `mock_ssh.call_count == 2`, the second command being
     `sudo sh -c 'cat /opt/<name>/.env && echo && cat /opt/<name>/.env.owner'` exactly (as built, fail-closed); a bare `present\n` answer → the second
     command is today's `sudo cat /opt/<name>/.env` exactly.
   - G2b (the separator is load-bearing): `_parse_env` of a `.env` content WITHOUT a trailing newline joined to the owner
     content as a plain `cat` would print it LACKS the owner key (the panel's reproduction, kept as the negative half:
     `REDIS_URL` ends in `DATABASE_URL_OWNER=…`); the same two contents joined by the separator parse to both keys
     intact; and G2's command-string assertion is what makes the separator load-bearing — the step-5 mutant drops the
     `echo`.
   - G3 (the automatic move): `_write_env_files("/opt/x", {"DATABASE_URL": a, "DATABASE_URL_OWNER": o, "K": "v"}, write)`
     → two `write` calls, owner first, the `.env` content lacking the owner key, and `caplog` holding `1 owner key(s) kept
     in .env.owner`; `_write_env_files("/opt/x", {"K": "v"}, write)` → one call, `.env` only, no log line.
   - G4 (no owner key, no owner write): `inject_env(ctx, {"K": "v"})` with `mock_ssh` answering `absent` → exactly ONE
     write, of `.env`, and `mock_ssh.call_count == 2` exactly as today (`:627` keeps its assertion).
   - G5 (the chmod by name, BEFORE the `mv`): `_write_file_to_vps_path("/opt/x", ".env.owner", "K=v\n")` and `(…, ".env",
     …)` → the ssh command string is `sudo chmod 0600 <tmp> && sudo mv <tmp> <dest> && sudo chown root:root <dest>` —
     the `chmod` precedes the `mv`, asserted by position; `(…, "compose.yaml", …)` → today's string, no `chmod`.
   - G6 (the probe protocol is fail-closed): first line `absent` + second line `owner` → `{}`; first line `nonsense` →
     `DeployError` naming the path; a refused `sudo` (empty answer) → `DeployError`, as today.
   - G7 (every writer goes through the one writer): parametrized over `_deploy_template`, `_deploy_git`, `_deploy_docker`,
     `_deploy_local` and `_persist_git_sha` with an existing `.env` carrying `DATABASE_URL_OWNER` (the shape of
     `tests/orchestrator/test_deployer_ssh.py:998-1001`) → the owner file is written first, the `.env` written last lacks
     the key, and no write puts the key into `.env`.
4. **Fallout — the tests that pin the one-file shape**, each updated with the reason in its assertion message, never
   loosened: `tests/orchestrator/test_deployer_ssh.py:1017` asserts `DATABASE_URL_OWNER` on the LAST write of
   `test_local_source_off_opt_keeps_registrar_injected_keys` — it now reads the owner write (the first) for that key and
   the last write for `DATABASE_URL`; `:1633-1635` asserts the exact `.env` command string — it gains the PREFIX `sudo chmod 0600
   /tmp/fabrik-<pid>-.env && ` (the test's `self._tmp('.env')` already spells that path). Confirmed UNCHANGED by the design (round 1, rules-O1/O2/O3, rest-S1/S2 — re-derived at the
   pin): every scripted `side_effect`/`return_value` fixture (`:458`, `:505`, `:511`, `:513` `call_count == 1`, `:524`,
   `:551`, `:555`, `:566`, `:570`, `:598`, `:622`, `:627` `call_count == 2`, `:631`, `:1164`, `:1197`, `:1260`, `:1279`,
   `:1296`, `:1320`), the last-write reads (`:466`, `:559`, `:574`, `:626`, `:635`), `:982` `assert_called_once`, `:1014-1015`
   (the `.env` write is still the last), `:1034`, `:1543-1567`'s `fake_write` (its fixture carries no owner key, and the
   writer keeps the 3-argument `(name, fname, content)` call), `:431` (`delete()`, never touched), `:1288` (asserts on
   `_build_env_content`'s merged output, unchanged); `tests/orchestrator/test_deployer_git_sha.py:57` and `:81-85`
   (`_Vps` answers `sudo cat …/.env` and asserts `filename == ".env"` — its fixtures inject `GIT_SHA` only, so no owner
   write ever reaches it); `tests/test_app_role_provision.py:32-53` (the fake deployer's `read_env`/`inject_env` are the
   merged-view API; `:170`'s ordering assertion stays).
   Run: `/opt/fabrik/.venv/bin/python -m pytest tests/orchestrator/test_deployer_ssh.py tests/orchestrator/test_deployer_git_sha.py
   tests/test_app_role_provision.py tests/orchestrator/test_infrastructure.py tests/orchestrator/test_spoke_dsn_mesh.py
   tests/orchestrator/test_plan1_defects.py -q -p no:cacheprovider` → all pass.
5. **Phase gate**: red-on-revert in a throwaway worktree — the mutant for G7 (one deploy path writing `.env` directly
   again), for G3 (the owner write skipped when the owner half is non-empty) for G4 (`_write_env_files` writing
   `.env.owner` unconditionally, even when the owner half is empty) and for G2b (the `echo` dropped from the two-file
   command) → each named test red, then the worktree removed. `/opt/fabrik/.venv/bin/python -m mypy
   src/fabrik/orchestrator/deployer_ssh.py src/fabrik/spec_loader.py --ignore-missing-imports` → no
   new error against the pre-phase count. `python scripts/enforcement/check_doc_sync.py` → green (no doc trigger in this
   phase beyond CHANGELOG).
6. **`/fabrik-review-scoped`** on Phase A's surface — BLOCKING, to its closing pass confirming zero defects.
7. Commit Phase A (explicit pathspecs; `CHANGELOG.md` via the private-index recipe; trailers `Agent-Role: primary`,
   `Agent-Phase: A`), push.

**Behavior Contract (Phase A):**
- **Given** a registrar injecting `DATABASE_URL` and `DATABASE_URL_OWNER` in one call, **When** `inject_env` runs, **Then** the owner key is written to `.env.owner` first, the app key to `.env`, and the stack restarts once (spec § The delta 1-2)
- **Given** an existing `.env` that still carries `DATABASE_URL_OWNER`, **When** any writer — a deploy path, `inject_env` or `_persist_git_sha` — builds the files, **Then** the key lands in `.env.owner` and never in `.env`, and the writer logs it once (spec § The delta 3)
- **Given** both files on the VPS, **When** `read_env` runs, **Then** it sees the merged view in one probe and one `cat`, the owner file winning on a shared key (spec § The delta 2)
- **Given** an injection carrying no owner key and no owner file on disk, **When** `inject_env` runs, **Then** `.env` is the only file written and the ssh call count is today's (spec § The delta 2)
- **Given** a write of `.env` or `.env.owner`, **When** the deployer issues its command, **Then** the temp file is `chmod 0600` BEFORE the `mv` and the result is `chown root:root`; any other file issues today's command unchanged (spec § The delta 6)
- **Given** a `.env` without a trailing newline beside an owner file, **When** `read_env` runs, **Then** both files' keys parse intact — the separated read, never a joined line (spec § The delta 2)
- **Given** a probe answer that is not `present`/`absent` on its first line, or an empty answer, **When** the reader parses it, **Then** `DeployError` names the path; an `absent` first line returns `{}` whatever follows (spec § What exists today — the fail-closed reader)

**Phase A execution notes (2026-10-12):** the `/fabrik-review-scoped` pass over c2ec25e4c (three readers + a refuter,
12 candidates, 9 confirmed, 3 refuted) changed two Interfaces as written above, both for the better and both graded:
(1) the two-file read is `sudo sh -c 'cat <env> && echo && cat <owner>'`, not `; echo;` — a `;` chain exits with the
LAST cat's status, so a missing or unreadable `.env` beside an owner file returned the owner keys alone as the merged
view (executed: rc 0), where the ssh driver raises only on a non-zero rc; `&&` fails closed and
`test_g2_a_failed_two_file_read_raises_never_returns_the_owner_half` holds it; (2) the deploy paths hand the merged
DICT to `_write_env_files` through a new `SSHDeployer._build_env(...) -> dict` (`_build_env_content` is its formatted
view, kept for its readers and tests) instead of parsing `_build_env_content`'s string back — the format→parse round
trip loses a value holding a newline (executed: `a\nb` → `"a`), so the Interfaces' "parse it back" clause is retired
and `test_g7_deploy_paths_write_a_newline_value_intact` holds the seam. Also added: graders for the probe parser's
fail-closed clauses and its per-line strip (O3/O5), and the constants' comment in `spec_loader.py` names no consumer
that does not exist yet (O7). Refuted with evidence: the git-sha test fake's `.env`-only assert (a loud failure on a
future owner fixture, never a silent one; the file is read-and-run only) and the Phase A→B rollout order (0 of 69
specs declare the companion, 0 of 39 composes name the key; Phase B lands on the same branch before any merge).
Mutants red in a throwaway worktree for every clause (M-G7, M-G3, M-G4, M-G2b, M-G5; then the `;` chain back, each
probe clause dropped, the strip dropped, the docker path round-tripping); restored tree green; 305 tests on the Phase
A list; ruff and mypy clean. The review-scoped record is the artifact (`--review-waived` per Execution Contract 3b).

## Phase B — the scaffold and the docs — ✅ EXECUTED 2026-10-12 (2de2c1097; review fixes 1e93f89cf, 2b9aefffe, 67a843ccb, 7dd78e1c9, dbf0e5c13)
Appetite: 90

**Interfaces — Consumes** (Phase A): `OWNER_ENV_FILE` is the filename the compose block names; the merged view.
**Produces:**
- `spec_loader.CompanionService.owner_env: bool = False` (`src/fabrik/spec_loader.py:818-856`, after `env_overrides` at
  `:852-855`; `extra: forbid` stays); and a `ServiceSpec` `@model_validator(mode="after")` (beside `:951-958`) refusing
  any `env:` key in `OWNER_ENV_KEYS` with a message naming the key, `.env.owner` and the reason — the templates render
  `env:` into every service's `environment:` (`templates/python-api/compose.yaml.j2:42`, the partial `:29-31`); the
  registrar is the owner key's only source (panel, Opus #4; I16).
- `spec_generator.audit_jobs_companion` (`src/fabrik/spec_generator.py:148-165`) constructs with `owner_env=True`.
- `templates/_partials/_companion_service.yaml.j2:17-18` — under `{% if c.owner_env %}` the long syntax (`- .env` then
  `- path: .env.owner` / `required: false`), else today's two lines; the header comment (`:3-5`) says where the owner DSN
  lives now.
- `src/fabrik/scaffold.py::_append_audit_jobs_service` (`:4159-4210`, the env_file lines `:4190-4191`) emits the same
  long-syntax block (the committed compose is the git-sourced deploy's truth).
- `src/fabrik/app_role_check.py` — three pieces. (i) `_classify_database_url_env` (`:474-486`) returns `owner` for a
  value that fullmatches `${DATABASE_URL_OWNER}` / `$DATABASE_URL_OWNER` as today, but `_scan_compose_structure`
  (`:590-598`) no longer suppresses it — it becomes a finding whose `pattern` reads: `the owner DSN is not interpolable
  from compose after the owner split (it lives in .env.owner, which compose interpolation never reads): give the service
  env_file [.env, {path: .env.owner, required: false}] and have the tool read DATABASE_URL_OWNER from its environment
  (alembic: in env.py); run it as docker compose run --rm <that service> …`. A hand-off in `command` is NOT the remedy:
  `run` with arguments "overrides the command defined in the service configuration" (ods-63), and a `$VAR` in `command`
  is interpolated by compose from the project `.env` unless written `$$VAR` (ods-62; round 2, rules-O17). The remedy is
  the `Finding.pattern` string (`app_role_check.py:266-270` — `Finding` carries `path`, `line`, `pattern` and nothing
  else), so the pattern text IS the remedy. (ii) The ACCEPTANCE rule (panel, Fable C1 — I15): a service whose `env_file`
  list contains `.env.owner` (the string, or a mapping whose `path` is `.env.owner`) is an OWNER CONSUMER —
  `_scan_compose_structure` suppresses `compose service named migrate` for it (`:566-588`), and the line scan (`:340-348`)
  suppresses a `_LINE_PATTERNS` match on a line inside that service's block (the block ranges `_service_block_range`
  already computes; the connection source is the tool's own config, which `_scan_alembic_env` `:352-368` covers).
  Executed at the panel on today's scanner (`scratchpad/ods-panel-probe-c1.py`): the remedy shape yields
  `[('compose.yaml', 12, 'alembic upgrade/downgrade'), ('compose.yaml', 6, 'compose service named migrate')]` — two
  findings — so without (ii) Phase B would make every cutover with a `migrate` service refuse at
  `infrastructure.py:1177-1182`. (iii) The mirror, in `scan_repo` (`:613`) after the walk: an alembic env (by content,
  `_ALEMBIC_IMPORT_RE`) whose text names `DATABASE_URL_OWNER` (`_OWNER_TOKEN_RE`) while no compose file's service declares
  `.env.owner` → `Finding(path=<env.py>, line=<the owner line>, pattern="alembic env.py reads DATABASE_URL_OWNER but no
  compose service loads .env.owner")` — after the split that env reads an empty value in every service. The module
  docstring (`:36-52`) and the `_OWNER_FULLMATCH_RE` comment (`:462-469`) say all three.
- `scaffold.py:2217-2219` and `:3595-3597` (the schema headers) read ONE line: `sudo sh -c 'set -a; . /opt/<name>/.env;
  . /opt/<name>/.env.owner; set +a; psql -1 -v ON_ERROR_STOP=1 "$DATABASE_URL_OWNER" -f db/schema.sql'` (both files are
  root 0600 — a plain `. ./.env.owner` is `Permission denied` for a non-root operator, and a root shell sourcing them would
  keep the owner DSN in its environment and history; the `pgurl` form wraps the same way — panel, Opus #7);
  `_COMMON_GITIGNORE_PATTERNS` (`scaffold.py:665-669`), `templates/node-api/.gitignore:2-3`,
  `templates/saas-skeleton/.gitignore:23-27` and `templates/mobile-app/.gitignore:13` (whose `.env*.local` does not match
  `.env.owner`) gain `.env.owner` — `/opt/<name>` on the VPS is a git working tree (`deployer_ssh.py:419`, `git reset
  --hard` leaves untracked files alone), so an un-ignored `.env.owner` shows as untracked there and in every clone (panel,
  Fable C6b); `_ENV_EXAMPLE_DSN_BLOCK` (`:3736-3744`) says the owner DSN is injected into
  `.env.owner`, which only the migrate/jobs services load.
- Docs: `docs/operations/fabrik-lifecycle.md:142` (`<svc>` is a service that declares `.env.owner`), `:203-205` (two
  files), the runbook gains step 0 before `:232` ("a service that needs the owner DSN declares `.env.owner` in its
  `env_file` and has its tool read `DATABASE_URL_OWNER` from the environment — Alembic: `env.py`; migrations run as
  `docker compose run --rm <that service> alembic upgrade head`, never through the app service, which no longer holds the
  key; the `DATABASE_URL: ${DATABASE_URL_OWNER}` interpolation form and a hand-off in `command` no longer work, and
  `fabrik app-role-check` reports the first; the audit-jobs companion already declares the file"), `:253-255` becomes
  "What the split does not cover" (the socket holder and root, a supply-chain compromise of the shared image, spec
  § Constraints; and that the owner credential leaves the app's environment only once the project cuts over), `:257-259`
  says a pinned `DATABASE_URL` in `env:` is REMOVED — an owner key in `env:` is refused by the loader, not a place to move
  it; `docs/operations/credential-recovery.md:121` names `.env` AND `.env.owner` as the files to scp off vps1 (the owner
  password is otherwise unrecoverable, `infrastructure.py:1121-1124` — panel, Fable C6a); `docs/CONFIGURATION.md:247`, `:249`, `:254`; `templates/scaffold/docs/CONFIGURATION_TEMPLATE.md:33`, `:119`,
  `:125`, `:144`, `:153`; `OPERATIONS_TEMPLATE.md:191`; `RESILIENCE_TEMPLATE.md:477`; `docs/reference/modules/drivers.md:238`.
- The D-441 request mail to infra (`python scripts/mail.py send --to fabrik --to-agent infra --kind request`), ONE mail,
  five sentences: (1) `.windsurf/rules/core/30-ops.md:161` — "overriding only `command` + `container_name` + `memory`"
  becomes "overriding only `command` + `container_name` + `memory`, plus the owner env file `.env.owner` in `env_file`
  where the companion needs the owner DSN (the audit-jobs companion does)"; (2) `core/30-ops.md:445`, (3)
  `core/10-python.md:297` and (4) `:305` — `docker compose run --rm <svc> alembic upgrade head` gains "`<svc>` is a service
  that declares `.env.owner` (the owner DSN is not in the app service's environment after the owner split)"; (5)
  `core/app-audit-log.md:39-41` and `:180` — "as the database OWNER (`DATABASE_URL_OWNER`)" gains "which only a service
  declaring `.env.owner` (the audit-jobs companion) or a host shell under `sudo` holds"; cite this plan and the spec; the
  packs are infra's sync surfaces (panel, Opus #2, #3).
- The D-441 request mail to fabrik-lib (`--to fabrik-lib --kind request`): `app-audit-log/README.md:53-58` — on a fleet
  host `DATABASE_URL_OWNER` lives in `/opt/<name>/.env.owner`, root 0600; the apply runs under `sudo sh -c` sourcing both
  files, or from a service declaring the file (panel, Opus #3).

Steps:
1. **G8 first (the companion carries the owner file, the app does not)** in `tests/test_scaffold_audit_log.py`: for each
   `_companion_types()` type the committed compose's `<name>-audit-jobs` service has `env_file == [".env", {"path":
   ".env.owner", "required": False}]` and the app service has `[".env"]` — written by changing the `== [".env"]` at `:530`
   and adding the app-service assertion; RED on today's code. Then `spec_loader.py`, `spec_generator.py`, the partial and
   `_append_audit_jobs_service` → GREEN; `:279` and `:558` (`".env" in svc["env_file"]`) keep passing because `.env` stays
   a plain string in the list.
2. G9 (the rendered template's companion, chrome-extension and file-worker, `:548-558`): the same long-syntax shape; G10
   (a node-api companion without `owner_env`): `tests/test_companion_services.py::test_render_emits_two_services` gains the
   assertion that its `env_file == [".env"]` — today's shape, red by the step-4 mutant. `tests/test_scaffold_saas_backend.py:170`
   is run and keeps passing (the saas services never carry the owner file).
3. **G11 (the hand-off is a finding)** in `tests/test_app_role_check.py`: `test_migrate_service_canonical_owner_handoff_is_suppressed`
   (`:770-783`) is rewritten as `test_migrate_service_owner_interpolation_is_a_finding_after_the_split` — the same
   compose yields ONE finding whose `pattern` names `.env.owner`, `env_file` and `DATABASE_URL_OWNER` read from the
   environment; the four other tests
   that pin the suppression flip with it — `test_suppression_owner_as_real_connection_source_clears_every_site` (`:193`),
   `test_compose_environment_owner_value_is_suppressed` (`:286`), `test_migrate_list_form_owner_handoff_is_suppressed`
   (`:975`) and `test_migrate_canonical_owner_handoff_stays_suppressed_after_d7` (`:1040`) — each rewritten to assert the
   finding (round 2, rules-O16: the `:590` flip reds exactly these 5 of 71); `test_compose_variable_names_are_case_sensitive_for_owner`
   (`:961`) is untouched — `${database_url_owner}` is already an override finding. RED on today's code (0 findings), then
   `app_role_check.py` → GREEN; the other 66 tests of the module pass unchanged.
3b. **G12 (the check accepts its own remedy)** in `tests/test_app_role_check.py`: a `tmp_path` repo whose compose has `app`
   (`env_file: [.env]`) and `migrate` (`env_file: [.env, {path: .env.owner, required: false}]`, `command: alembic upgrade
   head`) and an `alembic/env.py` reading `os.environ["DATABASE_URL_OWNER"]` → `scan_repo(repo).findings == []`. RED today
   (the panel's executed reproduction: 2 findings). **G13 (the mirror)**: the same repo with `migrate`'s `env_file` back to
   `[.env]` → the findings include exactly ONE whose `pattern` names `no compose service loads .env.owner`, at the
   env.py's owner line — beside the two today's scanner already reports for a `migrate` service with no owner source
   (`compose service named migrate`, `alembic upgrade/downgrade` on its `command` line), which STAY: that service is not
   an owner consumer. RED today because no finding names the missing declaration — today's scan returns exactly those
   two (executed at round 5: the env.py line is suppressed as owner-sourced and nothing cross-checks it against the
   compose). Then Produces (ii) and (iii) → both GREEN; G11 stays green (the interpolation value is still a finding on
   an owner-consumer service: the rule suppresses the `migrate` and `command`-line findings, never the `owner`
   classification of the interpolation value, which (i) turns into the finding).
3c. **G14 (the loader refuses an owner key in `env:`)** in `tests/test_spec_loader.py`: a spec with `env:
   {DATABASE_URL_OWNER: x}` raises `ValidationError` whose message names the key and `.env.owner`; the same spec with
   `env: {FOO: x}` loads. RED today, then the validator → GREEN. **G15 (the gitignore)** in `tests/test_scaffold_audit_log.py`
   beside G8: the scaffolded `.gitignore` of a database project lists `.env.owner`; RED today.
4. The schema headers, `_ENV_EXAMPLE_DSN_BLOCK`, the gitignore patterns (scaffold + three templates); then every doc line
   in Produces. Run
   `/opt/fabrik/.venv/bin/python -m pytest tests/test_scaffold_audit_log.py tests/test_companion_services.py
   tests/test_scaffold_saas_backend.py tests/test_scaffold_compose_traefik.py tests/test_app_role_check.py
   tests/test_spec_loader.py tests/test_spec_generator.py -q -p no:cacheprovider`
   → all pass; `python scripts/enforcement/check_doc_sync.py` → green; `python3 scripts/render_doc_script_links.py --check`
   → green. **Phase gate**: red-on-revert in a throwaway worktree — mutants: the partial emitting the long syntax
   unconditionally (G10 red), `audit_jobs_companion` without `owner_env=True` (G8 red) → each named test red, then the
   worktree removed.
5. Send the two D-441 request mails — infra (the five pack sentences) and fabrik-lib (the README) — (Produces, last two
   bullets); record both ids in the Evidence.
6. **`/fabrik-review-scoped`** on Phase B's surface — BLOCKING, to its closing pass confirming zero defects.
7. Commit Phase B (explicit pathspecs; `CHANGELOG.md` via the private-index recipe; `Agent-Phase: B`), push.

**Behavior Contract (Phase B):**
- **Given** a database spec of a type with an audit-jobs companion, **When** the scaffold writes the committed compose, **Then** the companion loads `.env` and `.env.owner` (long syntax, `required: false`) and the app service loads `.env` alone (spec § The delta 4-5)
- **Given** the same spec rendered through the template, **When** the companion partial renders, **Then** it carries the same two-file block (spec § The delta 5)
- **Given** a companion declared without `owner_env`, **When** it renders, **Then** its `env_file` is today's `[".env"]` (spec § The delta 5)
- **Given** a compose whose service sets `DATABASE_URL: ${DATABASE_URL_OWNER}`, **When** `fabrik app-role-check` scans it, **Then** it reports one finding whose remedy names `.env.owner` and `env_file` (spec § The delta 7)
- **Given** a `migrate` service declaring `.env.owner` whose `env.py` reads `DATABASE_URL_OWNER`, **When** the check scans it, **Then** it reports nothing (spec § The delta 7)
- **Given** an owner-reading `env.py` and no service declaring `.env.owner`, **When** the check scans it, **Then** one finding names the missing declaration (spec § The delta 7)
- **Given** a spec whose `env:` names `DATABASE_URL_OWNER`, **When** it loads, **Then** the loader refuses it naming `.env.owner` (spec § The delta 1)
- **Given** a human applying `db/schema.sql` on the VPS, **When** they read the header, **Then** it sources both files under `sudo` in one line before the owner `psql` (spec § Personas)
- **Given** a scaffolded database project, **When** its `.gitignore` is read, **Then** it lists `.env.owner` (spec § MIRROR)
- **Given** an agent reading the lifecycle or configuration docs, **When** it looks up where the owner DSN lives, **Then** every sentence names `.env.owner`, the runbook's step 0 and the interpolation form that no longer works (spec § Documentation landing sites)

**Phase B execution notes (2026-10-12):** the two D-441 request mails of step 5 are `01M4Q22F278ZQ1Y4BG7595CPCS`
(infra — the five rule-pack sentences: `core/30-ops.md:161`, `:445`, `core/10-python.md:297`, `:305`,
`core/app-audit-log.md:39-41` + `:180`) and `01M4Q22F4XA9MBG8RKQ76RQ7JR` (fabrik-lib — `app-audit-log/README.md:53-58`).
Grader fix-ups found while running them: the clears-every-site fixture declares `.env.owner` on its `migrate` service
(the canonical post-split repo — the mirror otherwise fires, correctly); the app service of the node-api, python-api-gpu
and chrome-extension templates renders no `env_file` key at all, so G8/G9/G10 assert that NO other service lists the
owner file instead of `== [".env"]`; the mirror fires only in a repo that has a compose file (an alembic-only fixture
has no service to name). 409 tests on the Phase B list; seven mutants red in a throwaway worktree (which needed
`<scratch>/fabrik-lib -> /opt/fabrik-lib` beside it: the scaffold resolves the module tree relative to the repo root).
The `/fabrik-review-scoped` pass over 2de2c1097 (seven finders — a Sonnet and a Haiku per unit, Opus on the check unit —
three refuters; 24 candidates, 21 confirmed by execution, 3 refuted: the gitignore claims compared the pin against the
unrelated main checkout, the cited pack sections exist, `.env.local` is the scaffold's WSL dev file) found the check
module's owner-consumer rule WIDER than its premise and the compose hand-off NARROWER than the mechanism, so Produces (ii)
reads differently as built. Round 1 (1e93f89cf): inside an owner consumer a line clears only while it names no bare
`DATABASE_URL` (`psql "$$DATABASE_URL"` in the block stays; the executed probe had returned `[]`); an unescaped
`$DATABASE_URL_OWNER` anywhere in a compose file, or the key named in a service not loading `.env.owner`, is the
`OWNER_HANDOFF_REMEDY` finding (the former `compose_block_spans` test pinned the opposite — it is G16 now); `./.env.owner`
and the scalar form count (`posixpath.normpath`); the mirror stays silent on an unparseable compose and its text names
the remedy; `run_check` appends ` reaches DATABASE_URL` to label patterns only; the loader also refuses the owner key in a
companion's `env_overrides` (the partial renders them into `environment:`) — G16–G25. Round 2 (2b9aefffe): the hand-off
is matched on the RAW line (a `--dbname` before it had fed the comment stripper), an odd run of `$` interpolates
(`$$$DATABASE_URL_OWNER`), one finding per service (a folded `environment:` value had yielded two), and a consumer line
defining a YAML anchor another service aliases stays (the range filter reads text, not the resolved graph) — G26–G29.
Rounds 3–5 (67a843ccb, 7dd78e1c9, dbf0e5c13): the anchor rule moved from the finding's line to the BLOCK — a declaring block that defines a YAML anchor aliased outside it is no consumer range at all (the folded-anchor, `<<: *base` and aliased-psql shapes the Opus seat reproduced), and G17's neighbour is a flow-style service so a range widened by one at the end reds; round 4 made the alias end where an anchor name ends (`&cmd-`) and exempted every declaring block from "outside" (two consumers sharing an anchored `env_file` both stay consumers); round 5 iterated that exemption to a fixpoint so a share counts through any number of merge hops. The scope-growth stop (D-355) tripped at round 4 — from there each round confirmed only a defect inside the review's own fix text — so each closing pass re-verified the fixed set alone: 6 passes, 21 → 9 → 2 → 2 → 1 → 0. Recorded by design: a `labels:` value naming
the key in a non-consumer is a finding (the module's raw-line rule), and a prisma/drizzle/django consumer's connection
source is not scanned — the declaration is the evidence (backlog `W-94a3b4df`). Thirty mutants red across the
phase and its five rounds; 461 tests on the Phase B list plus the loader's consumers. Appetite: 90 min planned, 182 min at the review's close — the overrun is the six-round review of the check module (a guard whose premise the first draft stated wider than its code), recorded as the lane's UPGRADE finding; the phase has no remaining step to re-plan.

## Phase C — the live check and Finish — ✅ EXECUTED 2026-10-12 (Finish review fixes 1a82aa9b7, a6d0da75c, c60a0ef10)

Appetite: 60

Steps:
1. **R1 + R2's remainder (read-only, the one VPS touch):** `ssh -o BatchMode=yes -o ConnectTimeout=20 ozgur@vps1.ocoron.com
   "sudo -n stat -c '%n %U:%G %a' /opt/transdoc/.env /opt/youtube/.env; sudo -n grep -rl --exclude='.env*'
   --exclude-dir=.git --exclude-dir=node_modules DATABASE_URL_OWNER /opt/test-saas-log /opt/translator"` — ONE ssh: the
   mode, expected `root:root 600` for both, and the two database projects this box cannot measure (R2's denominator:
   17 of 22 cloned here, 3 image-sourced by construction, these 2 only on vps1); `-l` prints file NAMES only and `.env*`
   is excluded, so no DSN crosses the wire; expected: no file named. The mode half is EVIDENCE, not a
   dependency: Phase A chmods both env files by name whatever the live mode is. A `644` is recorded in the receipt as the
   defect the chmod closes. If vps1 is unreachable after two tries, the Evidence records that, and the first `fabrik apply`
   after merge reads the mode back.
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
   been closed by then (I7). The approval D-row was minted by `/fabrik-plan-review`'s panel gate (D-613) before this plan
   executed; no phase mints a second row (`docs/DECISIONS.md` is a governance file outside File Scope by the plan grammar).

**Behavior Contract (Phase C):**
- **Given** the merged change, **When** the next `fabrik apply` of a database project runs, **Then** its `.env.owner` exists root-owned 0600 and its `.env` no longer carries the owner key — read back by the apply log's move line (spec § Lifecycle)

**Phase C execution notes (2026-10-12):** step 1 — the one ssh ran twice: attempt 1 at 06:12:09Z timed out
(`Connection timed out`, rc 255); attempt 2 at 06:12:35Z reached vps1 (ssh rc 0) and found NONE of the four paths:
`stat: cannot statx '/opt/transdoc/.env': No such file or directory`, the same for `/opt/youtube/.env`, and
`grep: /opt/test-saas-log: No such file or directory`, `grep: /opt/translator: No such file or directory` (grep rc 2).
So R1 stays unmeasured — those four projects are not deployed on vps1 today (0 of 4 paths exist; the plan named them
from the hub's clones and specs, not from a live inventory) — and the chmod both env files now get is the evidence the
first post-merge `fabrik apply` reads back, as the step's own fallback says; R2's two vps1-only projects have no checkout
there to grep, so the 0-reader count stands on the 17 of 22 measured here plus the 3 image-sourced by construction. No DSN
crossed the wire (`-l`, `--exclude='.env*'`, and the files were absent). Step 2 — the Finish `/fabrik-review` over
`a2fd75dde..HEAD`: four file slices (deployer · scaffold · check · docs), a Sonnet and a Haiku finder per slice plus the D7
Opus floor on the deployer, a refuter per slice, 13 seats stamped; pass 1 raised 20 candidates, 17 confirmed by the
refuters and the orchestrator's own execution, 3 refuted (the plan's D-355 sentence, the generator's alias keying, the
redeploy target — `cli.py:1317-1325` env-swaps the host); 13 fixed in two commits (1a82aa9b7: `scaffold.py` spells the
owner file through `OWNER_ENV_FILE` at every emitted site with G31, the hand-off scan runs only over a compose that parses
with G30, spec invariants 2 and 7 as built, the lifecycle notice paragraph; a6d0da75c: `_deploy_template` renders the
secrets WITHOUT the owner keys so a `secrets.from_env` owner key never lands in compose.yaml with G32, G1/G3 assert no DSN
value reaches the log, the cutover pin refusal says remove the pin, the spec's touchpoint row and Validation (2b) and this
plan's G2 text show `&& echo &&`, step 0 no longer claims a pre-split companion declares the file); 3 recorded by design
(an orphan `.env.owner` is deleted only by D-754's reversal; an orphan beside an absent `.env` is not adopted until a write
recreates `.env`; a prisma/drizzle/django consumer's connection source is not scanned — backlog `W-94a3b4df`); 1 recorded
pre-existing (the pid-named `/tmp` staging path and the scp-before-chmod window — `a2fd75dde:deployer_ssh.py:975` stages
the same way; backlog `W-8dd25072`, `mktemp -m 0600`); the first-move WARNING half of the degradation finding is backlog
`W-c03bf797`; `W-766ce3f2` (filed on the redeploy premise) is dropped with the reason. Pass 2 (the round-1 seats over the
two fix commits, 13 seats) found the two halves the fixes left: `_read_env_file`'s docstring still named
`_build_env_content` as the deploy merge reader (it is `_build_env`), and the check module's docstring promised ONE hand-off
finding per service without the per-line fallback its comment states for a block the text scan cannot locate — both
docstring edits, c60a0ef10. Pass 3 (the round-1 deployer and check seats — a Sonnet, a Haiku and the Opus floor on the deployer, a Sonnet and a Haiku on the check module; 0 candidates, so no refuter was dispatched) confirmed 0. Receipt:
`docs/development/reviews/2026-10-12-plan-1-owner-dsn-split-review.md`. Two seat-isolation defects of the loop machinery,
recorded in the receipt and the FEEDBACK line: a round-1 Haiku finder wrote `arch-tests.tar` into the worktree root
(removed, untracked, never staged), and the brief's archive-roots list omitted `scripts/` and `.windsurf/`, which the
scaffold and deployer tests import (the seats added them). Step 3 — `final_gate.py --check --json` success twice (before
and after the receipt's Status flip), `check_convergence.py` exit 0; `/fabrik-docs-review` over the Phase B docs is
SKIPPED as a separate run: every Phase B doc was a slice of the Finish review (docs slice, Sonnet + Haiku + refuter, two
passes), and the per-file claims it would re-check are the receipt's docs rows. Step 4 — this commit (the Phase C commit)
carries the plan, the lock release and the receipt; `work.py done W-4e74ea9d`; merge request 01M4PX76WPDWVX2JKT1J1W6XVF
(a2fd75dde) was acked `blocked` by infra at 01:59Z (a dirty `kaizen-log-fleet.md` in the main checkout), so a fresh
`merge_request.py request --review <receipt> --item W-4e74ea9d` is sent at the close (I7). Appetite: 60 min planned,
the Finish review ran from 09:36 to 21:10 local, roughly five hours of it the operator's retention interruption; the plan's own time was the review's three passes and two fix rounds, recorded as the lane's UPGRADE finding at the close — the Finish review's two fix rounds. The archive move to `docs/development/plans/archived/` is
the merge owner's at merge time: D-754 cites this path.

## File Scope (owned paths)
- src/fabrik/orchestrator/deployer_ssh.py
- src/fabrik/spec_loader.py
- src/fabrik/spec_generator.py
- src/fabrik/app_role_check.py
- src/fabrik/scaffold.py
- templates/_partials/_companion_service.yaml.j2
- templates/scaffold/docs/CONFIGURATION_TEMPLATE.md
- templates/scaffold/docs/OPERATIONS_TEMPLATE.md
- templates/scaffold/docs/RESILIENCE_TEMPLATE.md
- tests/orchestrator/test_deployer_ssh.py
- tests/test_scaffold_audit_log.py
- tests/test_companion_services.py
- tests/test_app_role_check.py
- tests/test_spec_loader.py
- templates/node-api/.gitignore
- templates/saas-skeleton/.gitignore
- templates/mobile-app/.gitignore
- docs/operations/fabrik-lifecycle.md
- docs/operations/credential-recovery.md
- docs/CONFIGURATION.md
- docs/reference/modules/drivers.md
- docs/superpowers/specs/2026-10-12-owner-dsn-split-design.md
- docs/development/reviews/2026-10-12-plan-1-owner-dsn-split-review.md

Read and RUN, never written (the plan grammar's File Scope is the WRITE set): `tests/orchestrator/test_deployer_git_sha.py`
(its `:57` and `:81-85` stay as they are — Phase A step 4; G7 lives in `test_deployer_ssh.py`), `tests/test_app_role_provision.py`,
`tests/orchestrator/test_infrastructure.py`, `tests/orchestrator/test_spoke_dsn_mesh.py`, `tests/orchestrator/test_plan1_defects.py`,
`tests/test_scaffold_saas_backend.py`, `tests/test_scaffold_compose_traefik.py`, `tests/test_spec_generator.py`
(`tests/test_spec_loader.py` moved to the write set for G14). The seven governance files
(`check_plan_tickets.py::GOVERNANCE_FILES` — CHANGELOG, INDEX, docs/README, FEATURES, LESSONS_LEARNT, DECISIONS,
STRATEGIC_BACKLOG) stay out of File Scope by that grammar; `CHANGELOG.md` is written at each phase's commit step through
the shared-tree recipe.

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
- Grounding passes: the spec's 61-row research ledger and its three researcher seats; this run's three Explore seats over
  the deployer (seat A), the emitters and their tests (seat B), the registrar and every other `.env` reader (seat C) —
  seat C found 0 readers of `DATABASE_URL_OWNER` outside `infrastructure.py:1094-1096` (audit.py 0, orchestrator/__init__.py
  0, scripts/ 0, app_role_check.py reads the clone, not the env); three executed probes (Evidence); the plan review's
  round 1 (an Opus and a Sonnet finder, a refuter each: 18 candidates, 17 confirmed by execution, 1 refuted by executing
  the rule-grounding matcher).
- Findings that shaped the plan: round 1 — a second ssh probe for the owner file broke 17 scripted fixtures, so the
  read stays one probe (two lines) + one `cat` (I10); compose interpolation reads the project `.env`, so the hand-off
  form becomes a check finding (I11); `core/30-ops.md:161` is contradicted, so infra gets the amendment request (I12);
  `.env`'s mode rested on the temp file, so both env files are chmod'ed by name (I13); `_persist_git_sha` would have
  written the merged view back into `.env`, so every writer goes through `_write_env_files` (G7); the reversal is one
  constant plus a checked deletion; the Goal no longer claims the credential leaves the app before the cutover; five code
  files, not four. The approval panel (Opus + Fable, D-613; both `sound-with-changes`): the two-file `cat` joined lines
  (I14 → the separated read, G2b); the check refused its own remedy and `run --rm` bypasses a `command` hand-off (I15 →
  the acceptance rule, G12/G13, the env.py shape, five pack sentences + the fabrik-lib README); the templates render `env:`
  into every service (I16 → the loader's refusal, G14, the constants' home); the reversal's order, the denominators, the
  sudo header, chmod before `mv`, the recovery doc, the gitignores, the `:1217` comment, the Size line (I17); Opus #8
  recorded (I18).
  Earlier: the LAST-write assertions (I8) → owner file written FIRST; `_validate_compose` never reads `env_file`
  (probe 2) → no validator change.
- (a) Coverage: spec delta 1 → `OWNER_ENV_KEYS`/`OWNER_ENV_FILE` in `spec_loader.py`, G1, the `env:` refusal G14; delta 2
  → the two-line probe + the separated read, G2, G2b, G6; delta 3 → `_write_env_files` and its six callers, G1, G3, G4,
  G7; delta 4 → the long-syntax block, G8, G9, ods-21/24/25; delta 5 → `owner_env`, G8, G10, the infra and fabrik-lib
  request mails (Phase B step 5), ods-63; delta 6 → the filename-keyed `chmod` before the `mv`, G5; delta 7 →
  `app_role_check.py`, G11, G12, G13; every spec Validation row (1-12) → G1, G2, G2b, G3+G7, G8+G10, probe 2, G5, Phase B
  step 4, G11, G12, G13, G14, G15; documentation landing sites → Phase B Produces (every path:line), each phase's commit (CHANGELOG), the approval
  D-row at the plan review's gate; R1 → Phase C step 1 as evidence. No gap.
- (b) Signatures: `_split_env` returns `(app, owner)` and is the only partitioner `_write_env_files` uses;
  `_write_env_files(path, merged, write)` takes the same `(path, filename, content)` writer the deploy paths already
  have (`_write_file_to_vps_path`) and a one-line adapter over `_write_file_to_vps(name, …)` for the five writers that call it today
  (`inject_env`, `_persist_git_sha`, `_deploy_template`, `_deploy_git`, `_deploy_docker`; the path writer only for
  `_deploy_local` — round 2, rules-O14), so the existing `mock_write` patches keep their three-argument shape;
  `OWNER_ENV_KEYS`/`OWNER_ENV_FILE` are defined once in `spec_loader.py` and imported, never redefined; `_read_env_file(path, _ssh)`
  keeps its signature and returns the merged view, so `:265`, `:326`, `:723`, `:950` are unchanged; `_write_file_to_vps_path`'s
  signature is unchanged (the `chmod` keys on the filename); `CompanionService.owner_env` defaults `False`, so every
  spec without it renders today's two lines; `OWNER_ENV_FILE` is the string the compose block, the probe, the `cat` and
  the writer share; `_classify_database_url_env` keeps returning `owner` — only its caller's treatment changes.
- Fixed point: not yet — `/fabrik-plan-review` grades it.

## Residual unknowns
- **Open — R1** (the live mode of `/opt/<name>/.env`): resolution Phase C step 1, two ssh attempts; evidence for the
  chmod both env files now get, never a dependency; unreachable → recorded, and the first post-merge apply reads it back.
- **Resolved — R2, denominator stated**: 0 code readers of `DATABASE_URL_OWNER` in the 17 of 22 database projects cloned
  on this box (0 of 39 `compose.yaml`, 0 of 11 `compose.dev.yaml`, 0 code files; the clones are the hub's — vps1 pulls
  GitHub), 3 image-sourced projects cannot read it by construction, 2 (test-saas-log, translator) are grepped on vps1 in
  Phase C's single ssh (spec § What exists today; seat C re-confirmed the hub side); the one non-code reader — compose
  interpolation of `${DATABASE_URL_OWNER}` — is measured at 0 of 39 and becomes a check finding (I11); the two TEXTS that
  tell projects to read the key from a scheduler are the infra and fabrik-lib requests (I15).
- **Resolved — R3**: `required: false` exists since Compose 2.24.0 (ods-24, ods-26); the fleet measured 2.40.3.
- **Resolved — the ssh call counts**: no fixture gains a call — the owner file rides the existing probe and `cat`
  (I10); `:513` (`call_count == 1`) and `:627` (`call_count == 2`) keep their assertions.
- **Open — the rule-pack amendments** (`core/30-ops.md:161`, `:445`, `core/10-python.md:297`, `:305`,
  `core/app-audit-log.md:39-41`, `:180`): infra's, by the one D-441 request Phase B sends; until they land the sentences
  and the split disagree, which the request names. Resolution: infra's reply, recorded in the receipt.
- **Open — the fabrik-lib README amendment** (`app-audit-log/README.md:53-58`): fabrik-lib's, by the D-441 request Phase B
  sends. Resolution: its reply, recorded in the receipt.

## Ask ↔ spec comparison (the approval gate's table, D-153 — recomputed against the CONVERGED text)

One row per item of the operator's brief (the work item's words and the `/fabrik-spec` brief), then every spec section the ask did not name.

| # | The ask, in its own words | What the spec says | Anchor | Disposition |
|---|---|---|---|---|
| A1 | *"The owner DSN shares the project `.env` with the app DSN"* (W-4e74ea9d) | `DATABASE_URL_OWNER` lives in `/opt/<name>/.env.owner` and nowhere else; `.env` never carries it | spec § The delta 1 | IN |
| A2 | *"not against code execution inside the container, which can read `DATABASE_URL_OWNER`"* | the app containers never receive the owner KEY; the credential leaves their environment with the cutover | spec § Goal, § Constraints | IN |
| A3 | *"an env file mounted only into the migrate and jobs services"* | `env_file` long syntax with `required: false`, emitted for the audit-jobs companion; a `migrate` service copies the three lines | spec § The delta 4-5 | IN |
| A4 | the brief's candidates (A) second env file · (B) compose secrets · (C) environment override | (A) chosen; (B) and (C) rejected on primary sources (ods-6, ods-29/35) | spec § Rejected alternatives | IN |
| A5 | *"the deployer must never move the key out of `.env` for a project whose compose does not read the second file"* | replaced by the automatic, logged move — measured 0 readers outside the hub (39 composes, 22 database specs, 0 code files); the one non-code reader, compose interpolation, becomes a check finding | spec § What exists today, § The delta 3 and 7 | CHANGED (the gate would gate nothing; the measurement is the evidence) |
| A6 | *"how the WSL dev `.env` (both keys) stays unmodified in code"* | the `.env.local` keeps both keys as one local role | spec § The delta (MIRROR) | IN |
| A7 | *"how `fabrik apply`'s first-deploy ordering … survives"* | owner file first, then `.env`, one restart; `required: false` keeps the first-boot ordering | spec § The delta 2 and 4 | IN |
| A8 | *"how rollback (`DATABASE_URL` := owner DSN) reads the second file"* | the merged view in one round trip, the owner file winning a shared key | spec § The delta 2 | IN |
| A9 | *"how the docs templates … and `fabrik-lifecycle.md` § The limit change"* | every landing site named with its line | spec § Documentation landing sites, plan § Phase B | IN |
| A10 | *"Measure the inventory read-only … never touch a VPS, a database or another repo"* | measured on this box; the one live `stat` is Phase C evidence | spec § What exists today, plan § Phase C | IN |
| S1 | — (not asked) the one-round-trip read protocol | two-line probe, one `cat` | spec § The delta 2 | ADDED — an existing code path's test fixtures required it (review round 1) |
| S2 | — (not asked) `fabrik app-role-check` reports the `${DATABASE_URL_OWNER}` interpolation form | delta 7 | spec § The delta 7 | ADDED — a contract the move breaks; the check is the only place a project meets it before cutover |
| S3 | — (not asked) the rule-pack amendment request to infra | `core/30-ops.md:161` | spec § Documentation landing sites | ADDED — a sync surface the companion no longer satisfies |
| S4 | — (not asked) both env files `chmod 0600` by name | delta 6 | spec § The delta 6 | ADDED — the mode rested on a temp file's bits (review round 1) |
| S5 | — (not asked) the reversal procedure (one constant plus one CHECKED deletion) | § Decisions taken | spec § Decisions taken | ADDED — this command mandates a stated reversal for a reversible row; the panel added the order check |
| S6 | — (not asked) the separated two-file read | delta 2 | spec § The delta 2 | ADDED — the approval panel executed the `cat` join (I14) |
| S7 | — (not asked) the check accepts its remedy; the `env.py` hand-off shape; the no-declaring-service mirror | delta 7, delta 5 | spec § The delta 5, 7 | ADDED — the approval panel executed the check on the remedy (I15) |
| S8 | — (not asked) the loader refuses an owner key in `env:` | delta 1 | spec § The delta 1 | ADDED — the templates render `env:` into every service (I16) |
| S9 | — (not asked) four more pack sentences + the fabrik-lib README, the recovery doc, the gitignores, the supply-chain limit | § Documentation landing sites, § Constraints | spec § Documentation landing sites | ADDED — readers the touchpoints missed (I15, I17) |

## Pass Ledger

Joint loop over this plan and its `Size: small` spec (md5 pairs: plan · spec; the pin of each round is the row's start).

| Pass | seats · axes re-checked | counters | method | md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (plan § Global Constraints, § Constraints Digest, § Phase A, § File Scope, § Evidence, § Coverage Checklist; spec § The delta, § Constraints Digest, § Constraints, § Validation) + sonnet×1 (every other section of both) + one Sonnet refuter per slice · all axes | found: 18, new: 18, confirmed: 17, fixed: 17, unexecuted: 0, edits: 28 | method: re-derivation — the refuters executed every candidate (17 confirmed: the second-probe fixture breakage reproduced on a copy of the module, the `:431` delete test read, the `:998-1001` fixture read, the compose interpolation sources fetched, `30-ops.md:161` read, the signatures and file counts re-derived); the orchestrator re-ran rules-O10's check with the gate's own matcher over all 16 digest rows (16 matched) → REFUTED | 35588cb0 · bdf7c313 → a8613296 · 117836c0 |
| Pass 2 | opus×1 + sonnet×1 (the round-1 slice owners) + one Sonnet refuter per slice · delta over the round-1 fixes + one hop | found: 6, new: 5, confirmed: 5, fixed: 5, unexecuted: 0, edits: 13 | method: re-derivation — rules: 12 of 12 ledger claims re-executed on patched copies of the module (O1–O8, O11–O13 NOW_FALSE; O9 STILL_TRUE: G4 passes today's code, so it is proven by its mutant); 4 NEW from the fixes, each executed: O14 the writer seam (15 tests reach the live scp when a deploy path passes the path writer — the adapter is now named per caller), O16 the G11 fallout (the `:590` flip reds 5 of 71 tests, named), O17 the remedy's `$` interpolated by compose (the `$$` escape, ods-62), O18 the stale owner file shadowing the reversal (the deletion is now part of the reversal); rest: 5 of 5 NOW_FALSE, its re-raised rest-S3 REFUTED (the run command's `tests/test_spec_generator*.py` glob matches the file; `test_spec_loader.py` added anyway) | 51f16e7c · 117836c0 → 319e9223 · f71a2fc5 |
| Pass 3 | opus×1 (the rules slice owner; the rest slice closed at Pass 2 with 5 of 5 NOW_FALSE) + one Sonnet refuter · the round-2 fixed set only — scope-growth stop (D-355) | found: 2, new: 1, confirmed: 2, fixed: 2, unexecuted: 0, edits: 3 | method: re-derivation — O14 re-run on a patched copy (2 failed / 174, the two named fallouts, no live scp), O16 the `:590` flip re-run (5 of 71 defs red, :961 unchanged), O17 the two command examples both `$$`-escaped and ods-62 read, O9 the labels read (G4 and G10 the only mutant-only graders) → NOW_FALSE; O18 STILL_TRUE in the plan's Global Constraints sentence (fixed: the reversal names the deletion) and O9-residual NEW (the Coverage Checklist row carried the round-1 label; fixed); the spec's md5 and the round-2 end pair re-derived (the end hash excludes the three ledger rows written after it) | 8ba5bf2e · f71a2fc5 → 8cf35dd3 · 1dfbfc3a |
| Pass 4 | opus×1 (the rules slice owner) + one Sonnet refuter · the round-3 fixed set alone (D-355 closing remainder) | found: 0, new: 0, **confirmed: 0**, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — O18 and O9-residual re-read at the pin (the plan's and the spec's reversal statements agree on the constant, the deletion, its order and its reason; the Coverage Checklist row and the Tests bullet agree on G4/G10 mutant-only and G9 red today; 0 lines of 689 carry the retired labels); the Pass 3 row's end pair re-derived (the spec pin hashes to 1dfbfc3a, the plan with the Pass 3 row removed to 8cf35dd3); standing clean since Pass 1: every other class | be47b0d9 · 1dfbfc3a → be47b0d9 · 1dfbfc3a ✓ (quiet; then the approval panel re-opened the loop — Pass 5) |
| Pass 5 | opus×1 (the rules slice owner) + sonnet×1 (the rest slice owner) + one Sonnet refuter per slice · the approval panel's fold (D-613: Opus 5.5 + Fable 5.1, both `sound-with-changes`; 11 ledger claims, one per accepted concern cluster) re-verified over the edited sentences + one hop | found: 2, new: 2, confirmed: 2, fixed: 2, unexecuted: 0, edits: 7 | method: re-derivation — 11 of 11 claims re-executed by the seats and the refuter (the `_parse_env` join and the separated fixture, `scan_repo` on the G12 shape, the jinja renders of `env.items()`, `_format_env`'s line shape, the reversal command's three sites, the 22-spec inventory, every cited doc line, the I14↔I16 offset): 9 NOW_FALSE; 2 confirmed, both inside the fold's own text — rules-O1 the G13 red claim (today's scan returns 2 findings on that shape, re-executed by the lead: the mirror comes BESIDE them) and rules-O2 spec Rejected (F) still naming the `command` hand-off; plus two side notes fixed (the `owner` classification wording; `test_deployer_git_sha.py` read-only) — the D-355 scope-growth stop fired (own-fix 2/2), so round 6 re-verifies the fixed set alone | 136590f9 · dfc9eeb3 → 83e377e8 · 0798cb35 |
| Pass 6 | opus×1 (the rules slice owner) + one Sonnet refuter · the round-5 fixed set alone (D-355 closing remainder) | found: 0, new: 0, **confirmed: 0**, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — the Opus owner re-executed scan_repo on the G13 shape against the 3073d897b module (exactly the two findings step 3b now names) and _classify_database_url_env (owner); grepped both pins for every remaining command-hand-off mention (7 of 7 the rejected shape); read File Scope, the Estimated diff and Phase A step 4 for the test_deployer_git_sha.py move; 4 of 4 NOW_FALSE, 0 candidates, closable | 83e377e8 · 0798cb35 → 3dd6ded8 · 0798cb35 ✓ → **CONVERGED** |

## Residual

| Id | Verdict |
|---|---|
| rules-O10 | REFUTED — the refuter's per-line `grep -F` is stricter than the gate: `check_rule_grounding.py` matches a quote as a substring of the WHOLE cited file with whitespace collapsed and backticks and `*` dropped; executed over all 16 digest rows of both artifacts, 16 matched (`scratchpad/ods-digest-probe.out`) |
| rules-O13 (governance files) | REFUTED in part — `CHANGELOG.md` and `docs/DECISIONS.md` are two of the seven `check_plan_tickets.py::GOVERNANCE_FILES`, which the plan grammar keeps OUT of File Scope on purpose (the lock would collide with every concurrent plan); the D-row's owning step is `/fabrik-plan-review`'s approval gate, now said in Phase C step 4 and the spec's landing sites — FIXED for that half |
| rest-S3 (read-only tests) | REFUTED in part — File Scope is the WRITE set by grammar; the test files the steps RUN but never edit are now listed under File Scope as "read and run, never written" — FIXED for the visibility half |
| rules-O12 | FIXED — the Goal, § Why this exists and § Constraints now say the owner credential leaves the app's environment only with the cutover; the lifecycle paragraph will say the same (Phase B) |
| rest-S3 (round 2) | REFUTED — the claim predicted 0 hits for `test_spec_generator` in the plan; the Phase B run command at the pin named `tests/test_spec_generator*.py`, a glob pytest expands to the file; `tests/test_spec_loader.py` is added to the run list and the read-only set regardless |
| rules-O12 (round 2 residual) | FIXED — spec § Personas:16-17 now says the owner KEY leaves the file the app loads and the credential leaves with the cutover |
| panel Opus #1 / Fable C2 | CONFIRMED by the lead's own execution (`scratchpad/ods-panel-probe1.py`: the joined parse lost the owner key, `REDIS_URL` absorbed the owner DSN) — FIXED: the separated read, G2b (I14) |
| panel Fable C1 | CONFIRMED by the lead's own execution (`scratchpad/ods-panel-probe-c1.py`: 2 findings on each remedy shape, 1 on today's form) — FIXED: the acceptance rule, its mirror, the env.py hand-off, G12/G13 (I15) |
| panel Opus #2, #3, #4, #5, #6, #7, #9, #10; Fable C3, C4, C5, C6a–d | ACCEPTED on read (each anchor re-opened by the lead: the four pack lines, the audit-log pack and README lines, `compose.yaml.j2:42` + the partial `:29-31`, `credential-recovery.md:121`, `scaffold.py:665-669` + the three template gitignores, `deployer_ssh.py:1217-1223`, the 22-spec inventory re-run: 17 cloned / 3 image / 2 absent) — FIXED (I16, I17) |
| panel Opus #8 | REJECTED (recorded, I18) — a later-missing `.env.owner` idles the companion exactly as a missing key in `.env` does today; the deployer rewrites the file on every apply and redeploy; the app-role step fails closed on a missing owner key (`infrastructure.py:1119-1125`); no code |
| lead (while folding) | FIXED — spec § Personas said `_persist_git_sha` "keeps touching `.env` only" and plan § Self-audit (b) still named the round-1 adapter callers; both now match invariant 3 and the round-2 writer seam |
| lead (gate grammar, after round 6) | FIXED — `check_spec_convergence.py` on the CONVERGED spec: APPROACH-FLOOR (0 cited URLs in the spec body — four primary-source URLs the ledger already carries appended to § External dependencies) and HOLLOW-INTAKE (I5/I12 `CHANGED` → `IN — CHANGED`, I20 `RECORDED` → `OUT-OF-SCOPE — RECORDED`, the gate's tokens); wording and citations only, no design sentence touched — the spec's committed md5 is therefore fecd5db5, not the Pass 6 end pair's 0798cb35; the gate re-run on the named spec reports 0 findings |

## Coverage Checklist

| Class | Status |
|---|---|
| Hunt: `src/fabrik/orchestrator/deployer_ssh.py` — every writer of `.env`, the reader, the restart | FIXED r1 (rules-O1/O3/rest-S1: the read stays one probe + one `cat` — every scripted fixture keeps its shape; rules-O4/O7: `_write_env_files` is the one writer for `inject_env`, the four deploy paths and `_persist_git_sha`, so no path writes the merged view back; rules-O11/rest-S5: both env files chmod'ed by name); panel r5 (Opus #1/Fable C2, executed): the two-file `cat` joined lines — the separated read, G2b; Opus #9: `chmod` before the `mv`, G5; Fable C6c: the `:1217` comment |
| Hunt: `src/fabrik/scaffold.py`, `spec_loader.py`, `spec_generator.py`, `app_role_check.py`, the companion partial — the emitted compose shapes and the check | FIXED r1 (rules-O5: the `${DATABASE_URL_OWNER}` interpolation form reads the project `.env` — `app_role_check.py:470-490`, `:590` now reports it, G11; rules-O6: `core/30-ops.md:161` contradicted — the D-441 request to infra, Phase B step 5); panel r5 (Fable C1, executed): the check refused its own remedy — the `.env.owner` acceptance rule, its mirror, the env.py hand-off, G12/G13; Opus #4: the loader refuses an owner key in `env:`, G14, the constants' home; Fable C6b: the gitignores, G15 |
| Hunt: the test files' pinned shapes — every fallout assertion named, none loosened | FIXED r1 (rules-O2/rest-S2: `:431` is `delete()`, removed; rules-O3: `:1017` asserts the owner key on the last write and is the one real fallout, with `:1633-1635`; every scripted fixture re-derived unchanged under the one-round-trip read, Phase A step 4) |
| Hunt: the docs — every sentence that says both DSNs live in `.env` | FIXED r1 (rules-O12: the Goal and § Constraints no longer claim the credential leaves the app before the cutover; the lifecycle's limit paragraph says so; the runbook's step 0 names the interpolation form the check reports); panel r5: four more pack sentences + the audit-log README (Opus #2/#3), `credential-recovery.md:121` (Fable C6a), `lifecycle.md:142`/`:257-259`, the supply-chain limit (Fable C3), the MIRROR's `_read_env_file` sentence (Fable C4), the sudo header (Opus #7) |
| Recurrence: fail-open/fail-closed — a swallowed error or an absent check that reads as success | FIXED r1 (the probe stays the fail-closed gate — a non-`present`/`absent` first line or an empty answer raises, G6; `required: false` on the owner file is the first-boot ordering the pack mandates, not a swallowed error); panel r5 (Opus #8) RECORDED — a later-missing owner file idles the companion as today's missing key does; no code |
| Recurrence: boundary/sentinel/prefix — an off-by-one, a sentinel value, a prefix-vs-exact match | FIXED r1 (rules-O2: the wrong `:431` anchor; the two-line probe answer is parsed by line, never by prefix — a bare `present` keeps its meaning, G2/G6) |
| Recurrence: behavior-without-a-test — a contract row no test kills (mutation asserted) | FIXED r1 (rules-O4: G7 parametrized over the four deploy paths and `_persist_git_sha`; rules-O9: the red/green table re-labelled in r2 — G1–G3, G5–G9, G11 red on today's code, G4 and G10 by their named mutants); panel r5: G2b, G12, G13, G14, G15 added, each red today |
| Recurrence: denominator on every count — bounded searches state their bound | FIXED r1 (rules-O8/rest-S4: five `.py` files + one template, ≈150 lines, stated in both artifacts; 0 of 39 composes use the interpolation form; 0 of 69 specs cut over); panel r5 (Opus #6/Fable C5): 17 of 22 database projects cloned here, 3 image-sourced by construction, 2 grepped on vps1 in Phase C's one ssh; 0 of 11 `compose.dev.yaml` |
| Recurrence: cost/quota accounting — native seats counted, a limit at its edges | CLEAN (docs/development/plans/2026-10-12-plan-1-owner-dsn-split.md § Global Constraints — three native seats per scoped review, the D7 floor at Finish, every dispatch stamped; the Appetite per phase 120/90/60) |
| Recurrence: proxy-as-evidence — the real check EXECUTED, not read | REFUTED r1 (rules-O10: the digest quotes were called non-verbatim by a per-line `grep -F`; the gate's own rule — whitespace collapsed, backticks and `*` dropped, substring of the whole file — was executed over all 16 rows, 16 matched; `scratchpad/ods-digest-probe.out`) |

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
