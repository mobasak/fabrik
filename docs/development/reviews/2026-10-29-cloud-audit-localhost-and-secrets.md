# Cloud audit — localhost-and-secrets (2026-10-29)

**Class:** every hard-coded localhost / 127.0.0.1 database or redis host, and every hard-coded credential-shaped literal, in `src/fabrik`, `scripts` and `templates/` that is not behind `os.getenv("KEY", default)` (tests excluded).
**Date:** 2026-10-29. Read-only audit; nothing but this file changed.

## Population searched

- `src/fabrik` 79 source files · `scripts` 437 · `templates` 151 (by extension: py/sh/yaml/yml/j2/env/json/toml/ts/js); **906 files of any type** under the three roots were grepped (excluding `node_modules`, `__pycache__`; paths matching `/tests?/` or `test_` removed from hits). `scripts/archived/` was included in the localhost greps (1 file hit, doc text) and excluded from the credential-assignment greps.
- Raw localhost/127.0.0.1/0.0.0.0 hits across the roots: 342; of those 39 touch a DB/redis context (the table below); the other ~300 are http service URLs, bind addresses and health probes, which are outside this class (not DB/redis hosts, no credentials).
- Commands (shell `grep` used as `command grep`, so `.gitignore` could not hide the synced paths):
  1. `command grep -rnIE "(localhost|127\.0\.0\.1)" src/fabrik scripts templates | grep -vE "/tests?/|/test_" | grep -iE "(postgres|psql|redis|database_url|db_host|pghost|:5432|:6379|asyncpg|psycopg|sqlalchemy|create_engine|connect\()"`
  2. host keyword forms: `host\s*[=:]\s*["'](localhost|127\.0\.0\.1)["']` and `["'](DB_HOST|PGHOST|POSTGRES_HOST|REDIS_HOST)["']\s*,\s*["'](localhost|127)` — 1 hit (a fix-hint string)
  3. getenv-default form: `(getenv|environ\.get|environ\[)[^)]*(DB|PG|POSTGRES|REDIS|DATABASE)[^)]*(localhost|127\.0\.0\.1)` — 1 hit (same fix-hint string)
  4. redis URLs: `redis(s)?://[^"' ]*(localhost|127\.0\.0\.1)|Redis\([^)]*(localhost|127)` — 3 hits (1 comment, 2 commented `.env.example` lines)
  5. credential shapes: AKIA…, `sk-…`, `ghp_…`, `github_pat_…`, `xox[bap]-…`, PEM private key headers, `AIza…`, JWT, `scheme://user:pass@host` — 2 hits
  6. credential assignments: `(password|secret|token|api_key|private_key|access_key)\s*[:=]\s*"literal"` (excluding getenv/environ lines) — 24 hits, 21 of them i18n UI strings
  7. weak-literal forms: `postgres:postgres`, `:postgres@`, `password=".."`, `PASSWORD: x`
  8. read of every hit's surrounding code (`sed -n`) in `ci_scaffold.py`, `scaffold.py`, `template_renderer.py`, `deployer_ssh.py`, `vps1_pg_scoped_logins.py`, `emit_mcp_project_config.py`, `check_env_vars.py`, `liveness_audit.py`.

Limit stated plainly: this is a pattern search, so a literal assembled by string concatenation or built from a variable would not match. No such construction was seen in the modules read.

## Findings

| # | path:line | verdict | why (one line) | suggested fix (one line) |
|---|---|---|---|---|
| 1 | src/fabrik/ci_scaffold.py:28 | SAFE | `postgres:postgres@localhost` DSN for the throwaway GitHub Actions service container (`:106-110`), carrying an explicit `noqa` rationale; not a real secret or shared DB | none |
| 2 | src/fabrik/ci_scaffold.py:108 | SAFE | `POSTGRES_PASSWORD: postgres` of the same ephemeral CI container | none |
| 3 | src/fabrik/ci_scaffold.py:202 | SAFE | `docker run -e POSTGRES_PASSWORD=postgres -p 127.0.0.1::5432` — loopback-only ephemeral container in emitted CI script | none |
| 4 | src/fabrik/ci_scaffold.py:214 | SAFE | emitted CI `TEST_DATABASE_URL` pointing at that container's `localhost:$PGPORT`; DB name `ci_test` | none |
| 5 | src/fabrik/scaffold.py:2226-2227 | SAFE | text written to the project's `.env.local` (WSL dev layer, role `postgres`, no password); the env layer, not application code | none |
| 6 | src/fabrik/scaffold.py:2232 | SAFE | `TEST_DATABASE_URL` in `.env.local`, DB name ends `_test` (throwaway guard) | none |
| 7 | src/fabrik/scaffold.py:2251 | SAFE | same `TEST_DATABASE_URL` appended to `.env.example` only if absent; dev-only localhost, no password | none |
| 8 | src/fabrik/scaffold.py:2286 | SAFE | emitted test fixture `_DB_ENV` for a mocked driver (`:2282-2283` says no real DB is used) | none |
| 9 | src/fabrik/scaffold.py:2298 | SAFE | emitted test asserts the mocked connect call with the fixture DSN | none |
| 10 | src/fabrik/scaffold.py:4082,4124 | SAFE | emitted `conftest` `os.environ.setdefault(...)` placeholder DSN (user `u`, db `x`), test scope only | none |
| 11 | src/fabrik/scaffold.py:7831-7832 | SAFE | node-api backend `.env.local` dev DSNs, same pattern as #5 | none |
| 12 | src/fabrik/template_renderer.py:265 | SAFE | `app:CHANGEME@postgres-main` is an `.env.example` placeholder line; host is container DNS, not localhost | none |
| 13 | scripts/enforcement/check_env_vars.py:183 | SAFE | the string is only a `fix_hint`; the check itself (`:30-31`, `:230`) flags localhost DSNs | optional: hint says `getenv('DB_HOST','localhost')` while the contract wants container DNS defaults; reword (cosmetic) |
| 14 | scripts/sysadmin/liveness_audit.py:1271,1281 | SAFE | deliberate planted fixtures (`AKIAIOSFODNN7EXAMPLEKEYXX`, a localhost DSN) written to a throwaway tree to prove the checks can fail (`:1275-1278` comment) | none |
| 15 | scripts/sysadmin/vps1_pg_scoped_logins.py:65,74,220 | SAFE | `postgres:postgres@postgres-main` is the OLD weak literal being searched for in live compose files and replaced; the script's new passwords come from `HUB_ENV_KEYS` env keys (`:80`), host is container DNS | none |
| 16 | scripts/sysadmin/emit_mcp_project_config.py:282 | SAFE | rewrites `@postgres-main:` to `@localhost:` for the box-local gitignored `.mcp.json` (WSL env layer); the comment at `:276-279` records why | none |
| 17 | scripts/create_pg_dev_db.sh:30 | SAFE | `echo` of a WSL dev connection hint, no connect, no password | none |
| 18 | templates/mobile-app/.maestro/{auth/login-with-validation,app/tabs,utils/login}.yaml:5 | SAFE | `PASSWORD: password` is an e2e flow fixture for a local test account with the `user@test.com` address | none |
| 19 | templates/node-api/.env.example:15; templates/saas-skeleton/.env.example:38 | SAFE | commented-out `redis://localhost:6379/...` example lines; the saas one is a test-only DB 15 | none |
| 20 | src/fabrik/orchestrator/deployer_ssh.py:1426-1437 | SAFE | this is the guard that rejects `localhost` in compose `DATABASE_URL`/`REDIS_URL`, not a use of it | none |
| 21 | scripts/archived/kilo_docs_enforcer.py:1338,1546 | SAFE | archived script; the lines sit inside doc text it emits | none |
| 22 | templates/scaffold/docs/{DEPLOYMENT,QUICKSTART,CONFIGURATION}_TEMPLATE.md; templates/governance/CLAUDE.md:308,492 | SAFE | documentation prose, many of them telling readers to avoid localhost in production; dev-layer examples carry no password | none |
| 23 | src/fabrik/drivers/postgres.py:321; scripts/cloud_dispatch.py:142; scripts/bootstrap/bootstrap-hub.sh:1474 | SAFE | a docstring sample output, a token FILE NAME, and a dry-run placeholder string — no live credential | none |

## Fix batches

No REAL rows, so no batch is owed. One optional cosmetic item (row 13, `scripts/enforcement/check_env_vars.py:183`, a one-line hint rewrite, hub-synced so it reaches the fleet) can ride any future edit to that file; it is not worth its own branch.

Not covered: values that live only outside the three roots (for example `infra/`, `infrastructure/`, `ops/`, `configs/`), which this task did not search. A prior finding (work item `W-3a814f0d`, a Cloudflare R2 key in `infra/vps1/ocoron-com/compose.yaml`) lives in that unsearched population.

**23 rows covering all found instances: 23 found, 0 real, 23 safe, 0 unsure.**
