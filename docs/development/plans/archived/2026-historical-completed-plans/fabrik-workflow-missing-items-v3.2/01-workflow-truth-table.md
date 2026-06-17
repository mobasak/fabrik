# 01 — Workflow Truth Table (v3.2)

**Phase-by-phase audit of the full workflow, with file/line evidence.**

For each phase: ✅ what works, ❌ what's missing. Each ❌ has a stable ID matching the fix tier docs.

**v2 changes:** all counts corrected (12 templates, 22 rule files, 7 governance files, 42 projects); G-B5/G-B6/G-D4/G-F5 added; cascade scope re-stated; truth-table claim "scaffold copies CLAUDE.md" corrected to reality. See `00-README.md` § CHANGELOG for the full list.

---

## Phase A — Idea → Opus → preplan file

| Status | ID | Item | Evidence |
|---|---|---|---|
| ❌ | G-A1 | No preplan template anywhere | `find . -name "*preplan*"` → 0 hits in repo |
| ❌ | G-A2 | No defined location convention | `docs/preplans/`, `preplans/`, `.fabrik/preplans/` — none exist |
| ❌ | G-A3 | No CLI shortcut (`fabrik preplan new`) | `fabrik --help` lists no preplan command |
| ❌ | G-A4 | `fabrik scaffold` doesn't accept `--from-preplan <file>` | `fabrik scaffold --help` shows `-d <description>` only |
| ❌ | G-A5 | `fabrik-workflow.md` doesn't define preplan→epic-brief handoff (absorbs G-C3) | Workflow chain starts at `epic-brief` assuming context already in chat |

**Reality today:** preplan files are improvised — no convention, no template, no CLI link. The transition from "Opus session output" to "Traycer epic-brief input" is verbal.

---

## Phase B — Scaffold (12 template directories, all with shape blocks)

| Status | ID | Item | Evidence |
|---|---|---|---|
| ✅ | — | All 12 templates have `defaults.yaml` with shape blocks pre-filled | `for t in templates/*/defaults.yaml; do grep -c "^shape:" "$t"; done` returns 1 for all 12 (chrome-extension, desktop-app, docusaurus, file-api, file-worker, mobile-app, next-tailwind, node-api, python-api, saas-skeleton, static-site, wordpress ) |
| ✅ | — | Auto-creates `specs/services/<name>.yaml` | `src/fabrik/spec_generator.py:507` `save_spec(spec, spec_path)` |
| ✅ | — | Auto-runs `sync_projects.py` | `src/fabrik/scaffold.py:3208`, non-fatal on failure |
| ✅ | — | Copies AGENTS.md, AGENTS-compact.md, .windsurfrules | `src/fabrik/scaffold.py:650` (.windsurfrules), :666 (AGENTS.md), :671 (AGENTS-compact.md). **Does NOT copy CLAUDE.md** — see G-B5 below |
| ✅ | — | Creates `compose.dev.yaml` for local dev | `src/fabrik/scaffold.py` (jinja template `compose.dev.yaml.j2`) |
| ✅ | — | Allocates port from `data/ports.yaml` | central registry exists |
| ❌ | G-B1a | `load_spec()` does NOT merge template defaults at LOAD time (load_spec merge — code-only fix) | `src/fabrik/spec_loader.py:425`: function body goes from `yaml.safe_load(f)` directly to `return Spec(**raw)` at line 457; no template lookup |
| ❌ | G-B1b | python-api/node-api template defaults don't include `exposes_metrics: true` | Without this, post-G-B1a merge for shape-less specs resolves prometheus to skip. **Decision required** (see 00-README §"Decisions also outstanding") |
| ❌ | G-B2 | `fabrik scaffold` doesn't auto-create GitHub repo | manual step today |
| ❌ | G-B3 | No `fabrik-file-worker` production spec | only test fixtures (`test-file-worker.yaml`, `fabrik-test-file-worker.yaml`) |
| ❌ | G-B4 | `fabrik scaffold` doesn't print Traycer next-step command | manual transition |
| ❌ | G-B5 | `fabrik scaffold` does NOT copy CLAUDE.md | New scaffolds have no CLAUDE.md until first qualifying commit triggers `governance-sync` hook (`scripts/sync_enforcement_to_projects.py:GOVERNANCE_FILES`). Claude Code in fresh scaffolds runs blind for the first commit cycle |
| ❌ | G-B6 | `next-tailwind` template is orphaned from AGENTS.md | `templates/next-tailwind/defaults.yaml` exists with valid shape block, but `grep -c "next-tailwind" AGENTS.md` → 0. Either deprecate the template OR add it to the Scaffold Types table at AGENTS.md line ~461 |

**The G-B1 cascade — corrected scope:** because `load_spec()` doesn't auto-merge, the 5 deployed pre-G1 specs (captcha, emailgateway, file-api, image-broker, translator) — which lack `shape:` blocks — cause `fabrik apply` to skip ALL 9 registrars. **Fixing G-B1a alone cascades to fix:**

- ✅ G-H1 (5 specs lack shape — they now inherit template defaults)
- ✅ G-H4 partial (Gatus endpoints created for the 4 that have `is_public=true` + domain — captcha, emailgateway, image-broker, translator; file-api also gets one)
- ✅ G-H5 (Backrest plan for file-api — `has_persistent_data: true` is set in `templates/file-api/defaults.yaml`)
- ❌ G-H3 does NOT cascade-fix — templates don't set `exposes_metrics: true`. Needs G-B1b OR per-spec overrides.

So G-B1a alone fixes 3 of 5 G-H gaps, not 4. G-B1b (template default flags) is needed to also close G-H3.

---

## Phase C — Traycer planning (in /opt/<project>)

| Status | ID | Item | Evidence |
|---|---|---|---|
| ✅ | — | `docs/traycer/fabrik-workflow.md` exists | full planner contract |
| ✅ | — | Per-type workflow chains defined | epic-brief → core-flows → tech-plan → ticket-breakdown → execute → implementation-validation → revise-requirements |
| ✅ | — | AGENTS.md auto-loaded by Traycer | 6-7 mentions of shape/registrar |
| ✅ | — | 10 `.windsurf/workflows/` files | bug-fix, deploy, kilo, kilo-review, local-coder, local-docs, local-fixer, local-review, new-feature, review |
| ❌ | G-C1 | Traycer fabrik-workflow.md has ZERO references to `fabrik apply`/`deploy`/`destroy`/registrars | `grep "fabrik apply\|fabrik deploy\|fabrik destroy\|fabrik redeploy\|registrar" docs/traycer/fabrik-workflow.md` → 0 hits |
| ❌ | G-C2 | No `.windsurf/workflows/registrar-audit.md` | for Traycer to run drift detection mid-session |
| — | ~~G-C3~~ | absorbed into G-A5 (preplan handoff) | (was: "no preplan→epic-brief handoff workflow") |

**Implication:** Traycer's contract stops at "code is written and validated." Deploy is **out of Traycer's scope today**.

---

## Phase D — Coding (Kilo CLI / Cascade / Claude Code)

| Status | ID | Item | Evidence |
|---|---|---|---|
| ✅ | — | 7 governance files synced to all 42 /opt projects | `scripts/sync_enforcement_to_projects.py`: `GOVERNANCE_FILES` list = AGENTS.md, AGENTS-compact.md, AFCL.md, CLAUDE.md, opencode.json, .windsurfrules, .pre-commit-config.yaml. Plus `.windsurf/rules/` directory |
| ✅ | — | `.windsurf/rules/` has 21 rule files | 20 numbered (10-python through 95-multi-tenant-saas) + ocoron-design-system.md. CROSS_CUTTING_REQUIREMENTS.md was dissolved 2026-05-14; its rules redistributed into topic packs (30-ops / 35-security-auth / 50-code-review / 55-observability) and always-on content into the three bootstrap files. |
| ❌ | G-D1 | AGENTS-compact.md, CLAUDE.md, .windsurfrules, AFCL.md, opencode.json have ZERO shape/registrar mentions | `grep -c "shape\|registrar\|fabrik apply\|InfrastructureProvisioner"` → 0/0/0 across the 5 (only AGENTS.md has 6-7) |
| ❌ | G-D2 | None of 22 `.windsurf/rules/` mention shape/registrar/InfrastructureProvisioner | cross-cutting rules cover language/framework, not deploy contracts |
| ❌ | G-D3 | No `fabrik review` bundle-and-dispatch | manual diff+spec+plan packaging today |
| ❌ | G-D4 | **AGENTS.md registrar list is itself out of date** | AGENTS.md line 459 + 479 enumerate registrars as `postgres / gatus / backrest / glitchtip / grafana / authelia / meilisearch` (7). Code's `_REGISTRAR_ORDER` tuple in `src/fabrik/orchestrator/infrastructure.py` lines 86-94 has 9 (adds redis + prometheus). Traycer plans against stale 7-registrar reality while code runs 9 |

**Implication:** Kilo CLI / Claude Code / Cascade write code without knowing what registrars apply to the spec. They can produce code that contradicts the shape contract (e.g., adding postgres calls to a service whose spec has `needs_database: false`) and nothing catches it before deploy. Worse, even Traycer (which DOES read AGENTS.md) is reading drift.

---

## Phase E — Commit (pre-commit + final_gate.py)

| Status | ID | Item | Evidence |
|---|---|---|---|
| ✅ | — | `.pre-commit-config.yaml` runs absolute blockers | large-files (>500KB), merge-conflict, secret detection, governance-sync to all 42 projects |
| ✅ | — | `scripts/final_gate.py` is deterministic gate before commit | auto-fix lint, ruff, mypy, bandit, semgrep, yaml/json validation, structure, conventions |
| ❌ | G-E1 | pre-commit doesn't run `fabrik plan` for changed specs | a spec with shape contradictions reaches `fabrik apply` and fails late |
| ❌ | G-E2 | `final_gate.py` does YAML-loadability only, NOT pydantic Spec validation | `scripts/final_gate.py:471` only `yaml.safe_load()`, never calls `load_spec()` or `Spec(**raw)` |
| ❌ | G-E3 | No `fabrik plan` integration into pre-commit for `specs/services/` changes | — |

---

## Phase F — Deploy (`fabrik apply` / `deploy` / `redeploy` / `destroy`)

| Status | ID | Item | Evidence |
|---|---|---|---|
| ✅ | — | `fabrik apply <spec>` is default zero-touch path (since G1, 2026-05-05) | full 9-registrar sweep |
| ✅ | — | `fabrik deploy` uses project.yaml metadata | routes WP vs generic |
| ✅ | — | `fabrik redeploy <app> --force` for plain Coolify rebuild | works |
| ✅ | — | **`fabrik redeploy --refresh-infra --spec <path>`** = the reconcile tool | `src/fabrik/cli.py:850-889`; verified working in dry-run on site-provisioner |
| ✅ | — | `fabrik destroy <spec>` reverses all 9 registrars (8 destroy + grafana annotation skip) | shape-driven via `resolve_applicability(spec_dict)` at `destroyer.py:433` |
| ✅ | — | Destroy preserves data by default | `--drop-data` opt-in (lines 164, 275, 291) |
| ✅ | — | All 9 driver files real implementations | postgres 279L, redis 293L, gatus 249L, backrest 273L, glitchtip 481L, grafana 291L, authelia 520L, meilisearch 262L, prometheus 366L |
| ✅ | — | All 9 `_provision_*` wired in `infrastructure.py` lines 318-342 | bodies 12-75 lines each, real logic |
| ✅ | — | All 8 `_destroy_*` (grafana intentionally skipped per docstring) | annotations are informational, by design — `destroyer.py:469` |
| ✅ | — | All 9 `_rollback_*` in `rollback.py` | postgres + meilisearch are "destructive-no-op by design" (data-bearing) |
| ❌ | G-F1 | `fabrik plan <spec>` does NOT call `resolve_applicability()` | `cli.py:197` plan() loads spec but never resolves; output shows generic actions only (line 274 hardcoded) |
| ❌ | G-F2 | No `fabrik reconcile-all` sweep | single-spec command exists; multi-spec sweep doesn't |
| ❌ | G-F3 | `fabrik apply` doesn't persist deploy state | `DeploymentContext.add_resource()` is in-memory only; no `.fabrik/state/<id>.json` |
| ❌ | G-F4 | `fabrik destroy` is shape-driven, not live-state-driven | intentional per `destroyer.py:23` docstring; risk: spec edited between apply and destroy |
| ❌ | G-F5 | No `fabrik destroy --partial <registrar>` | needed to surgically remove individual registrar resources (e.g., proxy.vps1 Authelia rule) without manual VPS edits |

**Reality:** the deploy story is the strongest part of the workflow. The orchestrator works. The reconcile tool exists (`redeploy --refresh-infra`). The gaps are at the edges — surfacing what'll happen (plan), sweeping multiple specs (reconcile-all), persisting state (state file), using state on destroy (use-state), and surgical partial destroy.

---

## Phase G — Verify / audit / drift detection

| Status | ID | Item | Evidence |
|---|---|---|---|
| ✅ | — | `fabrik verify <domain>` runs DNS + deploy postcondition checks | works |
| ✅ | — | `fabrik status <spec>` exists | command at `cli.py:549` |
| ✅ | — | `audit_authelia_gates.py` checks Authelia↔Traefik label drift | weekly-cron-intent docstring |
| ✅ | — | `audit_all_projects.py` audits scaffold compliance | works |
| ✅ | — | `snapshot_vps_state.py` captures pre/post-deploy state | works |
| ❌ | G-G1 | `fabrik status` is BROKEN for site-provisioner | `cli.py:581`: lookup is single-variant `[a for a in apps if a.get("name") == spec.id]`. Some apps stored as `<id>` (site-provisioner), others as `fabrik-<id>` (fabrik-captcha). Fix needs guard: only prefix when `not spec.id.startswith("fabrik-")` |
| ❌ | G-G2 | No `fabrik audit-registrars` command | no one-shot way to verify "for spec X, are all registrar side-effects present?" |
| ❌ | G-G3 | `fabrik verify` has no `registrars` verifier spec | only `dns` and `deploy` exist |
| ❌ | G-G4 | `audit_authelia_gates.py` is NOT scheduled | `systemctl list-timers` → no fabrik/audit/authelia entries; "weekly cron" is intent-only |
| ❌ | G-G5 | No drift alerting beyond authelia | no equivalent for postgres, redis, gatus, prom, backrest |

---

## Phase H — VPS infrastructure registrars (live state)

These are the actual missing side-effects on the VPS today. **Cascade scope corrected from v1**: G-B1a alone cascade-fixes G-H1, G-H4 (partial), G-H5 — **NOT G-H3** (needs G-B1b or per-spec overrides).

| Status | ID | Item | Evidence | Cascade-fix from G-B1a? |
|---|---|---|---|---|
| ❌ | G-H1 | 5 deployed specs lack `shape:` block | captcha, emailgateway, file-api, image-broker, translator (all `grep -c "^shape:"` → 0). Verified exhaustive via full-sweep of 65 spec files. | ✅ yes |
| ❌ | G-H2 | `/opt/monitoring/configs/redis/assignments.json` missing on VPS | live: db3=authelia, db4=glitchtip-web manually configured | ❌ no, manual seed |
| ❌ | G-H3 | 0 of 7 services have a per-service Prometheus scrape job | all 13 prom jobs are infra-level | ❌ **NOT cascade-fixed** — needs G-B1b OR per-spec `exposes_metrics: true` |
| ❌ | G-H4 | 0 of 7 services have a per-service Gatus endpoint | 21 endpoints exist, all infra-level | ✅ yes (partial — 4 of 5 specs are public+domain, file-api also) |
| ❌ | G-H5 | `file-api` missing Backrest plan `file-api-data` | per code naming `<name>-data` | ✅ yes (file-api template defaults set `has_persistent_data: true`) |
| ❌ | G-H6 | `image-broker` has NO Authelia rule | service publicly exposed | ✅ DECIDED 2026-05-09: ADD Authelia rule (set `shape.is_admin_dashboard: true`) |
| ❌ | G-H7 | `fabrik-proxy` Authelia drift | rule exists but spec.shape.is_admin_dashboard=false (`specs/services/proxy.yaml:16`) | ✅ DECIDED 2026-05-09: update spec to match live state (`shape.is_admin_dashboard: true`) |
| ❌ | G-H8 | `translator` postgres DB naming mismatch | live DB=`translator_service`, code would create `translator` | ✅ DECIDED 2026-05-09: rename live DB → `translator`, set spec `shape.needs_database: true` (destructive — see Tier 1 §6) |
| ❌ | G-H9 | `fabrik-file-worker` deployed without spec | only test fixtures exist (G-B3) | n/a |

---

## Phase I — Local-dev workflow

| Status | ID | Item | Evidence |
|---|---|---|---|
| ✅ | — | `compose.dev.yaml` per scaffold | local dev story exists |
| ✅ | — | `.env.local` convention | local secrets |
| ✅ | — | `from_env` SecretsPolicy maps WSL `/opt/fabrik/.env` → Coolify env on apply | works |
| ❌ | G-I1 | No `fabrik dev` to start local stack with hot-reload | manual `cd /opt/<p> && docker compose -f compose.dev.yaml up` |
| ❌ | G-I2 | No `fabrik logs --local` to tail local docker logs | only remote Loki tail today |

---

## Phase J — Operational + base-image readiness

| Status | ID | Item | Evidence |
|---|---|---|---|
| ✅ | — | `data/ports.yaml` central port allocation registry | works |
| ✅ | — | Coolify DB volume backed up by Backrest | `docker-volumes` plan |
| ✅ | — | postgres-main DBs backed up | `postgres-dumps` plan |
| ✅ | — | `/opt` configs backed up | `opt-configs` plan |
| ❌ | G-J1 | `data/projects.yaml` lacks `coolify_uuid`/`spec_path`/`last_apply_status`/`last_apply_sha` | only static scaffold metadata; `total_projects: 42` is the only live counter |
| ❌ | G-J2 | No `fabrik export`/`fabrik import` for portability | base-image cloning impossible without manual UUID rewriting |
| ❌ | G-J3 | `coolify-alias-watcher` watches a hardcoded list of 4 service UUIDs | meilisearch, gotenberg, browserless, glitchtip-web; new deploys with custom aliases need manual editing of `/opt/coolify-alias-watcher/watcher.sh` |
| ❌ | G-J4 | No central postgres allocation registry | parallel to redis assignments.json missing |
| ❌ | G-J5 | Cloudflare token has overly broad scope; narrowing has caveats | `cfut_nNprCT...` Workers Scripts + Account Settings; should narrow to **Zone.DNS:Edit + Zone.Zone:Edit** (NOT just Read — site-provisioner exposes `POST /api/cloudflare/zones/{domain}/provision` which needs zone create) |
| ❌ | G-J6 | 2 leftover `*.predrift-fix.20260506` files | in `/opt/monitoring/configs/gatus/apps/` |

---

## Total gap count (v2)

| Phase | Gaps | Notes |
|---|---|---|
| A — preplan | 5 | G-A5 absorbs former G-C3 |
| B — scaffold | 6 | adds G-B5 (CLAUDE.md), G-B6 (next-tailwind orphan), splits G-B1 into G-B1a + G-B1b |
| C — Traycer | 2 | G-C3 merged into G-A5 |
| D — coding | 4 | adds G-D4 (AGENTS.md drift) |
| E — commit | 3 | |
| F — deploy | 5 | adds G-F5 (partial-destroy) |
| G — verify/audit | 5 | |
| H — live VPS state | 9 | cascade scope corrected (3 gaps fix from G-B1a, not 4) |
| I — local-dev | 2 | |
| J — operational | 6 | |
| **Total** | **47** | |

Counts in the README CHANGELOG say "48" because that table shows the running delta from v1's 44 — the actual count above sums to 47 (the README count was off by 1 due to including the absorbed G-C3 in the "no change" row). Use this section as canonical.

After applying tier 1 + tier 2: ~32 gaps closed (24 in code + 8 cascade-from-G-B1a). Remaining are workflow polish + base-image architectural items.
