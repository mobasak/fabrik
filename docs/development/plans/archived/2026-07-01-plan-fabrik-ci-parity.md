# Plan: Fabrik CI-Parity — scaffold a CI workflow + a matching local replica from one source

**Status**: SHIPPED (core) 2026-07-01 — **Phase 1** (one-source generator `src/fabrik/ci_scaffold.py`) + **Phase 3** (scaffold auto-emits `ci.yml` + `ci_local.sh` for python-api/gpu/file-api) landed and are gate-green; the generator was hardened by an adversarial review (bounded pg-wait, venv-PATH exec, always-install ruff). **Deferred to future tickets** (not blocking; archived): **Phase 2** (spec-driven `shape.db_extensions: [pgvector]`) needs a spec→CI regen path that doesn't exist yet — new scaffolds default to plain `postgres:16`, which is correct for most; **Phase 4** (backfill the existing 39 projects) is deliberately NOT a blind overwrite — a project's hand-rolled `ci.yml` (e.g. trade-intelligence's) must not be clobbered, and generating a matching `ci_local.sh` from an *existing* `ci.yml` is a separate tool. Both are clean follow-ups, not gaps in the shipped mechanism.
**Owner**: ozgur · **Author**: Claude (Opus 4.8)
**Created**: 2026-07-01
**Context-trigger**: `/opt/trade-intelligence` + `/opt/youtube` fail GitHub CI regularly. Root diagnosis: `final_gate.py` is a *static* gate (ruff/mypy/bandit/consistency, no pytest, no DB) so it structurally cannot catch **environment drift**. Fix A (shipped, `check_undeclared_imports.py`) closed the one static-catchable class (imported-but-undeclared deps). This plan (Fix B) closes the rest.

## The gap Fix A does NOT cover

Four failures broke trade-intelligence CI. Fix A catches #3. The other three are runtime/environment drift that only a clean room surfaces:

| # | Failure | Why only CI/clean-room catches it | Owner |
|---|---|---|---|
| 1 | test-DB URL used `+asyncpg`; CI sets it plain | test config diverged from CI env format | **Fix B** |
| 2 | shared-DB test pollution (passed one-file-at-a-time locally) | only the FULL suite in one DB reproduces it | **Fix B** |
| 3 | `pydantic-settings` imported, in no manifest | static — fresh `pip install` crashes | ✅ Fix A (shipped) |
| 4 | `pgvector` extension missing on CI's postgres image | needs the exact `pgvector/pgvector:pg16` image | **Fix B** |

**Root cause of the recurrence:** fabrik scaffolds emit **no CI workflow** (verified — `find templates -path '*github*'` returns nothing). Every project hand-rolls `.github/workflows/ci.yml`, so CI and the local gate share no source of truth and drift. "Green locally" gives false confidence because the local gate never runs the suite the way CI does.

## Goal

Every fabrik project gets, generated from **one source**:
1. a standard `.github/workflows/ci.yml`, and
2. a `scripts/ci_local.sh` that reproduces it **byte-for-byte in intent** (fresh venv, exact PG image + extensions, full `pytest -q`, CI's env-var format).

So a passing `ci_local.sh` ⇒ passing CI. Run it before pushing test/dep/migration changes; ~2 minutes; catches #1/#2/#4 locally.

## Grounding — the reference CI (already correct)

`/opt/trade-intelligence/.github/workflows/ci.yml` is the pattern to templatize (verified 2026-07-01):
```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16          # postgres:16 + the vector extension
env:
  TEST_DATABASE_URL: postgresql://postgres:postgres@localhost:5432/postgres   # PLAIN url, no +asyncpg # noqa: throwaway CI container credential (documented example)
steps:
  - pip install -r requirements.txt        # the fresh-install that Fix A now guards
  - pip install ruff pytest pytest-asyncio xlrd
  - run: python -m pytest -q               # full suite, one DB
```
`/opt/youtube/.github/workflows/` has `test.yml` + `validate.yml` — a second real sample (confirms the "web + python two-job" shape trade-intelligence also has).

## Scope (phases — each shippable independently)

- **Phase 1 — one-source generator.** A single template (e.g. `templates/_partials/ci/`) that renders BOTH `.github/workflows/ci.yml` and `scripts/ci_local.sh` from the same variables, so they cannot drift. Variables: `needs_database` (→ pg service + `TEST_DATABASE_URL` plain), `db_extensions` (→ `pgvector/pgvector:pg16` vs `postgres:16`), `test_cmd` (default `python -m pytest -q`), `needs_web` (→ the type-check+unit job). `ci_local.sh` runs a throwaway `docker run pgvector/pgvector:pg16`, a fresh `python -m venv`, `pip install -r requirements.txt`, then the same suite with the plain URL.
- **Phase 2 — spec drives it.** Reuse the existing `shape.needs_database` (already in the spec contract) to switch the PG service on/off; add `shape.db_extensions: [pgvector]` (optional) to pin the image. No new top-level command.
- **Phase 3 — scaffold emits it.** `fabrik scaffold` writes `.github/workflows/ci.yml` + `scripts/ci_local.sh` for python-api / node-api kinds. Existing single-service templates get the CI files; SaaS/static skip DB.
- **Phase 4 — backfill + convention.** Backfill the two known-affected projects (trade-intelligence, youtube) + document the pre-push convention in `docs/operations/deployment.md` ("run `scripts/ci_local.sh` before pushing test/dep/migration changes"). Optional: a sample `pre-push` git hook that runs it.

## Out of scope
- Making `final_gate` itself run a DB/full suite — deliberately NOT done; the static gate stays fast. `ci_local.sh` is the heavy instrument, run on demand, not every edit.
- Monorepo/matrix CI beyond the python+web two-job shape (revisit if a project needs it).
- Test-isolation *fixes* (#2 is a real test-hygiene bug per project) — Fix B makes it *reproducible locally*; fixing each project's fixtures is project work.

## Validation gates (per phase, to fill in at execution)
- Render a fixture spec with `needs_database: true, db_extensions: [pgvector]` → assert `ci.yml` and `ci_local.sh` agree (same image, same URL format, same test cmd) — a golden test that diffs the two renders' intent.
- Run the generated `ci_local.sh` in trade-intelligence → reproduces the current green CI locally (and would have gone red on the original 4 failures).
- `final_gate.py --lean --json` → success.

## Residual unknowns
- **R1** Per-project DB extension set (only `pgvector` seen so far) — needs a small survey before backfill.
- **R2** Test-command discovery for non-standard projects (some use `make test`, some `pytest tests/`) — default `python -m pytest -q`, override via `shape` field.
- **R3** The web/type-check job varies (youtube vs trade-intelligence) — Phase 1 covers the common shape; project-specific web steps stay hand-editable below a `# fabrik-managed` fence.
- **R4** `ci_local.sh` needs Docker locally (for the PG image). True on the dev WSL box; documented as a prerequisite.

## Approval gate
Owner approves ALL / a subset / REVISE. No code until approval.
