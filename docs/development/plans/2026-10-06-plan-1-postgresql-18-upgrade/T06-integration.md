# T06 — Integration: rehearsal, hand-offs, gates and the receipt

Depends: T01a, T01b, T04a, T04b, T05
Parallel: ⛓️
Complexity: native
Appetite: 120
Integration: true
Gate: python scripts/final_gate.py --check --json
Docs: INDEX.md, docs/README.md, CHANGELOG.md (orchestrator-applied)

## Scope
The orchestrator, after T01a–T05 merge into the branch: (a) rehearses the runbook's hub window on scratch docker — a `postgres:16-alpine` cluster seeded with three databases, each holding at least one table with rows and a sequence, two login roles, a default ACL, an `ALTER SYSTEM` setting, a `CONNECTION LIMIT 20` database and a vector-free extension — through every D1 step to V1 green on `postgres:18.6-alpine`, the output fenced in the receipt (spec § Validation V1); (b) mails infra, after the hub window, the drafted D4 pack edits (`.windsurf/rules/core/25-data-postgres.md` § Primary Keys, `65-rag-search.md:61`, the verbatim `CLAIMS.yaml` `pg-fleet-major` row), the `agents-fabrik.md:170,186,188` lines, the `docs/reference/prebuilt-app-containers.md:87` and `docs/reference/technology-stack-decision-guide.md:21,518` lines and the `postgres_major: "18"` flip, as one request (the PRE-dispatch precondition mail is the orchestrator's, sent at execute start — see the spine); (c) mails brand-identiy-creator the D7 request (spec § The delta › D7); (d) boards the two operator gates — the WSL window and the hub window (Gate 2, production data); (e) applies the `INDEX.md` and `docs/README.md` rows for the runbook and the new tests, the CHANGELOG entry and the `docs/STRATEGIC_BACKLOG.md:131` pointer; (f) files the two merge requests — `fleet-pg18-dr` (T03 alone, merged by infra inside the hub window) and the fleet branch (everything, merged after it) — superseded by D-647: T03 already reached master, so only the fleet-branch request remains; (g) runs the whole-plan gates and writes the receipt.

## Touches
- docs/development/reviews/2026-10-06-plan-1-postgresql-18-upgrade-review.md

## Behavior Contract
- **Given** the scratch rehearsal, **When** it runs the runbook's hub window from a seeded 16 cluster, **Then** V1 is green on 18.6 — counts, content hashes, roles, ACLs, settings and the recorded connection limit — and the restore stderr holds only `role "postgres" already exists` (spec § Validation V1)
- **Given** the hand-offs, **When** infra's and brand-identiy-creator's inboxes are read, **Then** each holds one request naming its exact files, and the two operator gates are open awaiting items (spec § The delta › D4, D7; § Lifecycle)

## Context Files
- docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md
- docs/operations/postgres-major-upgrade-runbook.md
- INDEX.md
- docs/README.md
