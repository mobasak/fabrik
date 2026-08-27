# Cross-Epic Validation Report
Surface: 07804ac7f037147b3e112779783f7731

Rounds (found counts refuted candidates too; FULL hashes, chained — round N's end = round N+1's start):
| round | found: | fixed: | md5(start) → md5(end) |
|------:|-------:|-------:|---|
| 1 | found: 0 | fixed: 0 | 07804ac7f037147b3e112779783f7731 → 07804ac7f037147b3e112779783f7731 |
| 2 | found: 0 | fixed: 0 | 07804ac7f037147b3e112779783f7731 → 07804ac7f037147b3e112779783f7731 |

**Scope:** the umbrella-SSO hub epic set (2 epics) — `2026-08-27-epic-1-zitadel-umbrella-idp.md`,
`2026-08-27-epic-2-cross-saas-sso-integration.md`. Reviewers: pool `fanout("review")` ×2 (deepseek, gemini —
flywheel-scored) + orchestrator Opus (authoritative refute/merge/decide). Rubric-armed (FLOOR: core/35, core/25,
core/30). Both rounds edit-free (identical chained hashes) — genuinely quiet, not asserted.

## Feature Coverage: PASS — 6 in-scope features across 2 epics · orphans: none · duplicates: none
Vision Full Feature Inventory #1,#2 → Epic 1; #5,#6,#7,#8 → Epic 2 (each in exactly one). #3,#4 are the
vision's Out-of-Scope (fabrik-lib `oauth-login` adapter + `product-entitlements` module) — external by design,
correctly NOT claimed by any hub epic. No phantom features.

## Epic Tickets: PASS
- Epic 1 — Title `Epic 1 — Zitadel Umbrella IdP Deployment` (em-dash, single spaces) ✓; Summary/Scope(In+Out)/
  7 Success Criteria (deploy-gate #1 + feature #2 + resilience #3 + audit #4)/Out of Scope/Dependencies (all 5
  sub-bullets incl. real `Owned paths`)/15-row Metadata — all present.
- Epic 2 — Title `Epic 2 — Cross-SaaS SSO Integration + Entitlements` ✓; 8 Success Criteria (deploy-gate #1 +
  feature #2 + the two HARD constraints #3 revocation-live-teardown & #1 needs_cache + reconciler-idempotency
  #4 + audit #8); Dependencies name specific artifacts (OIDC issuer, client creds, Authorization-v2 API); 15-row
  Metadata. All present.

## Dependency Graph: PASS — no cycles · roots: [Epic 1] · parallel lanes: [none — both sequential]
Epic 1 `Produces` (OIDC issuer `auth.ocoron.com` + per-RP client creds + Authorization-v2 grant API) ==
Epic 2 `Consumes` — seam consistent. Frontmatter `depends_on: [1]` on Epic 2 matches the `### Dependencies`
prose and the graph. Minimal: Epic 2's edge to Epic 1 is justified (consumes the live issuer). Owned-paths
disjoint (E1: `specs/services/zitadel.yaml`, `docs/reference/zitadel.md`; E2: `libs/**/product_entitlements_bridge/**`,
`docs/reference/umbrella-sso-integration.md`) → no `Parallel with:` claims, so the disjointness/migration gates
are N/A. **Critical path: (external fabrik-lib) → Epic 1 → Epic 2 (3 deep)**; SPLIT-CANDIDATE stated on each
in the proposal (E1 no; E2 yes-per-RP-tickets). Epic-count sanity: **2** — legitimate (a self-contained IdP
deploy + a dependent multi-product rollout with a hard live-issuer dependency; the 3rd unit is external
fabrik-lib), not a mis-split.

## Infrastructure Decisions: PASS — no contradictions, no missing sections
`docs/superpowers/specs/2026-08-27-umbrella-sso-infrastructure-decisions.md` carries all shared sections
(Database, Auth, Email, Background Processing, Self-Healing, Watchdog Wiring [opt-out], Observability, Cost
Guardrails [N/A], Backing/External Services, Domain, Shared Env, Shared Shape) + the `## Deferred Compliance
(not actioned this run)` section (empty — all constraints folded into Epic 2). Both tickets **reference** it by
full path, neither duplicates it. No cross-ticket contradictions.

## Handoff Readiness: PASS — 15-field Metadata complete; Registrars match Shape; ports free in PORTS.md
- **Registrars ↔ Shape** (semantic): Epic 1 — needs_database⇒postgres ✓, exposes_metrics+domain⇒prometheus ✓,
  is_public+domain⇒gatus ✓, has_persistent_data⇒backrest ✓, grafana(always)+glitchtip(kind=service) ✓; NOT
  redis/authelia (Zitadel *is* the auth) ✓; watchdog opt-out declared ✓. Epic 2 — needs_cache⇒redis ✓ (the new
  per-RP flag), no new deploy unit.
- **Port:** Epic 1 Traefik-routed on `auth.ocoron.com`, no host port (PORTS.md host ranges untouched); Epic 2
  none new. No collision.
- 15 metadata fields value-shaped (Universal categories verbatim from 02's 2h; Email/Abuse/FINANCIALS
  contract-valued). Both tickets self-sufficient with the Infrastructure Decisions spec.

## Overall: PASS  ·  Fixups this run: 0  ·  Routed back: none

### Accepted out-of-scope finding (operator-ruled this turn)
`epic_order.py` globs `docs/development/epics/` flat; the pre-existing `2026-07-14-epic-1-fleet-ci-deploy-debt.md`
(a TOTALLY DIFFERENT, still-OPEN hub epic that predates the frontmatter schema) reads as "no frontmatter —
cannot map to a graph node". **Operator ruling: it STAYS, untouched** (not archived, not backfilled — a
different OPEN initiative). The SSO set validates cleanly **in isolation** (`epic_order --check --expected-count
2` → INTEGRITY: PASS). Structural note for a future run: two epic initiatives cannot share this dir under the
flat glob — date-scoping `epic_order` (or separating the dirs) is the durable fix (operator/infra call, out of
this SSO run's scope).

## Recommended Execution Order  (topological phases; `⚡` = parallel within a phase)
Phase 1 (root): Epic 1 — Zitadel Umbrella IdP Deployment
Phase 2: Epic 2 — Cross-SaaS SSO Integration + Entitlements
(external prerequisite: the fabrik-lib `oauth-login` adapter + `product-entitlements` module — largely done —
must land before Epic 2 federates.)
