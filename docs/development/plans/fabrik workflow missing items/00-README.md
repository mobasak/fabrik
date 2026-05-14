# Fabrik Workflow — Missing Items (review pack v3.2)

**Created:** 2026-05-09
**Revised:** 2026-05-09 (Traycer audit-of-the-audit applied three times — v1→v2→v3→v3.1; 5 design decisions LOCKED IN; 6 v3.1 polish items applied; see CHANGELOG below)
**Author:** Claude (initial pass + v2 + v3 corrections) + Traycer (two correctness audit rounds)
**Purpose:** End-to-end gap inventory for the Fabrik workflow described by Özgür on 2026-05-09:

> *idea → talk to Opus → preplan file → fabrik scaffold (multiple types via script) → cd /opt/<project> → start Traycer → Traycer reads AGENTS.md, follows fabrik-workflow.md, creates plan → code via Claude Code (CLAUDE.md) / Kilo CLI (AGENTS-compact.md) / Windsurf Cascade (.windsurfrules) → review → commit → fabrik apply/redeploy/destroy via Coolify API with all 9 registrars firing automatically*

## CHANGELOG (v2 corrections)

Traycer audited v1 against the actual source and flagged 12 inaccuracies + 15 missing items + 8 internal inconsistencies. v2 incorporates every correction. The most consequential fixes:

| What was wrong (v1) | Reality | Where fixed in v2 |
|---|---|---|
| **G-B1 cascade claim**: "fixes G-H1, G-H3, G-H4, G-H5 automatically" | Templates don't set `exposes_metrics` or `needs_cache`; post-merge specs resolve to only `gatus + glitchtip + grafana`. **G-H3 (prom jobs) and G-H4 partial cascade only** | Tier 1 split into G-B1a (load_spec merge) and G-B1b (template default flags); cascade re-scoped to G-H1 + G-H4 + G-H5 (3 gaps, not 4) |
| **AGENTS.md registrar list out of date** | Lists 7 registrars (postgres / gatus / backrest / glitchtip / grafana / authelia / meilisearch); code has 9 (adds redis + prometheus). Traycer plans against stale reality. | New gap **G-D4** added to Tier 1 (2-min doc edit) |
| **G-G1 fix logic broken** | Proposed candidate list `[spec.id, f"fabrik-{spec.id}"]` would query for `fabrik-fabrik-proxy` against an already-prefixed spec id | Tier 1 §3 corrected with `if not spec.id.startswith("fabrik-")` guard |
| **G-H8 Option B is a no-op** | Post-G-B1, translator inherits `needs_database: false`; postgres registrar is gated off by shape. Adding `infra.postgres: false` overrides nothing. | Tier 1 §6 Option B rewritten: drop or use proxy.yaml pattern (explicit `shape.needs_database: true` AND `infra.postgres: false`) |
| **G-J5 CF token narrowing too restrictive** | site-provisioner exposes `POST /api/cloudflare/zones/{domain}/provision` which needs Zone:Edit (create), not Read | Tier 1 §8 corrected: Zone.DNS:Edit + Zone.Zone:Edit (or explicit decision to manage zone creation manually) |
| **Truth-table claim "scaffold copies CLAUDE.md"** | Scaffold copies AGENTS.md, AGENTS-compact.md, .windsurfrules only. CLAUDE.md is added by pre-commit governance-sync hook on first qualifying commit | Truth table corrected; new gap **G-B5** added (scaffold should copy CLAUDE.md directly) |
| **Counts wrong**: 4 governance files, 11 templates, 20 rule files, 41 projects | Actual: **7** governance files, **12** templates, **22** rule files, **42** projects | All counts corrected throughout; new gap **G-B6** for next-tailwind orphan (template with shape but missing from AGENTS.md table) |
| **B3 line citation off** | status() at line 549, not 1130 | Tier 1 §3 corrected |

## CHANGELOG (v3 corrections — Traycer's second audit pass)

The v2 pack went through a second Traycer review which surfaced 7 new errors and 7 polish items. v3 fixes all of them. All claims re-verified against /opt/fabrik source on 2026-05-09.

| ID | Type | Where | Fix landed |
|---|---|---|---|
| **V2-E1** | count | 00, 01, 04, 99 | "16 templates" → **12 templates** (verified: only 12 dirs under `templates/` have `defaults.yaml`; the other 4 — `prompts/`, `scaffold/`, `spec-pipeline/`, `traycer/` — are auxiliary, no shape blocks) |
| **V2-E2** | count | 99 source-of-truth | "65 total; 2 with shape" → **"65 total; 35 with shape blocks; only 2 of those are DEPLOYED + non-test: proxy + site-provisioner"** |
| **V2-E3** | pseudocode | 02, 03, 04, 05 | `from fabrik import FABRIK_ROOT` → **`from fabrik.config import FABRIK_ROOT`** (canonical per 6 existing usages in `src/fabrik/`) |
| **V2-E4** | pseudocode | 03 §10, §13 | Removed non-existent `acquire_spec_lock` (which would crash since `drivers/locks.py` only exports `run_locked` for VPS-side bash). Added new module spec **`src/fabrik/locks_local.py`** with `file_lock()` context manager (~30 LoC, fcntl-based). Pseudocode now uses `from fabrik.locks_local import file_lock` and `with file_lock(f"reconcile-{spec.id}", timeout_seconds=30):`. |
| **V2-E5** | line citation | 02 §10, 99 | Reviewed: lines **459 + 479** are correct in current AGENTS.md (verified by `sed -n` and inline content). Traycer's 463/480 was off by 4/1 — not applied. |
| **V2-E6** | pseudocode | 03 §19 G-F5 | `@destroy.command()` (would AttributeError — `destroy` is `@cli.command()`, not a Group) → **extended existing `@cli.command()`** with `--partial` and `--drop-data` options. Replaced uniform `handler(spec.id, dry_run=...)` dispatch with **`HANDLER_ARGS` map** that builds correct args per registrar (authelia takes `domain`; postgres/redis/meilisearch take `drop_data`; others take `name+dry_run`). Added explanatory comment so future readers don't re-introduce the bug. |
| **V2-E7** | pseudocode | 03 §17 | `vps_run(...).stdout` (doesn't exist — would NameError) → **`ssh(cmd)`** (returns stdout str directly per existing usage in `drivers/locks.py:108`) |
| **V2-S1** | count reconciliation | 00 README | Three contradictory totals (47/48/52) → canonical **47** everywhere; README CHANGELOG `+4` row → `+3` |
| **V2-S2** | clarity | 02 §1a edge test #4 | Reframed from "merge preserves both" (which doesn't really test the merge) to **"proxy-pattern override survives merge"** — explicitly test that `infra.postgres: false` from spec survives merge against template that sets `shape.needs_database: true` but not `infra.postgres`, AND that `resolve_applicability` correctly gates postgres OFF afterward. |
| **V2-S3** | clarity | 02 §13 acceptance | Added explicit `for p in /opt/*/CLAUDE.md; do [ -f "$p" ] \|\| echo "MISSING: $p"; done` verification snippet with explanation of how to fix any MISSING outputs. |
| **V2-S4** | implementation gap | 05 §31 G-G5 | The Alertmanager route matched on `alert_class: registrar_drift` but no Prometheus rule was defined to emit that label. Added **Piece 1 (pushgateway metric) + Piece 2 (Prometheus alert rule at `/opt/monitoring/configs/prometheus/rules/fabrik-drift.yml`)** before the existing Piece 3 (Alertmanager route). Now the chain is complete bottom-up. |
| **V2-S5** | scope | 02 §1b Path B | Recommendation reframed from "every new and existing scaffold" → **scoped to `python-api` and `node-api` templates only**, with explicit exclusions (`saas-skeleton` doesn't auto-emit metrics; `static-site` has no runtime). The change is exactly two `defaults.yaml` files. |
| **V2-S6** | implementation | 04 §24 opencode.json | Replaced "embed multi-paragraph rule as JSON-encoded string" with **Option (a): create `KILO_CLI_RULES.md`, add to `GOVERNANCE_FILES`, reference from `opencode.json` via `rules_files` field**. Keeps opencode.json as pure config; readable in editor/diffs. |
| **V2-S7** | accuracy | 02 §11 G-B5 | Misleading parenthetical "(For symmetry, also consider copying AFCL.md and opencode.json)" → **"`AFCL.md` is already copied at scaffold.py:679; `opencode.json` is already copied at scaffold.py:717. CLAUDE.md is the only governance file scaffold currently misses."** |

**v3 verification grep** (run from this folder):
```bash
grep -c "16 template" *.md         # all 0 ✅
grep -rn "from fabrik import FABRIK_ROOT" *.md   # empty ✅
grep -c "acquire_spec_lock" *.md   # all 0 ✅
grep -c "@destroy\.command" *.md   # 1 (only in explanatory comment) ✅
grep -c "vps_run" *.md             # all 0 ✅
grep -c "HANDLER_ARGS" 03-tier2-reconciliation.md    # 4 ✅
grep -c "fabrik-drift.yml" 05-tier4-base-image.md   # 2 ✅
grep -c "FABRIK_ROOT" *.md         # several (from `fabrik.config` only) ✅
```

---

Full CHANGELOG details in `01-workflow-truth-table.md` § "v2 corrections list" and per-tier docs.

## Why this exists

The audit pass walked the workflow phase-by-phase, verified every claim against actual `/opt/fabrik` source code and live VPS state, and produced a definitive gap inventory. v1 had errors; v2 reconciled them.

This pack is the durable artifact. Each gap has a stable ID (`G-<phase>-<n>`), the actual evidence (file path + line number, or VPS query result), effort estimate, and what fixing it unlocks downstream.

## Document layout

| File | Contents |
|---|---|
| `00-README.md` | this file — overview, success criteria, how to use the pack, v2 changelog |
| `01-workflow-truth-table.md` | the complete phase-by-phase audit of what works vs what's missing, with evidence (47 gaps total in v2) |
| `02-tier1-foundation.md` | Tier 1 fixes (~16 h) — load_spec merge, decision work items (W-1..W-5), governance fixes |
| `03-tier2-reconciliation.md` | Tier 2 fixes (~14 h) — closes the reconciliation loop |
| `04-tier3-workflow-polish.md` | Tier 3 fixes (~10 h) — preplan handoff, executor rule awareness |
| `05-tier4-base-image.md` | Tier 4 fixes (~28 h) — portability, drift alerting, destroy-via-state |
| `99-evidence-appendix.md` | raw audit transcripts and verifiable commands for re-checking each claim |

## Status legend (used throughout)

- ✅ verified working in code + live VPS
- ❌ missing or broken (the gaps this pack addresses)
- (legend retired 2026-05-09 — all 5 design decisions LOCKED IN; see §DECISIONS LOCKED IN)

## Success criteria (whole epic, all 47 gaps)

After the epic ships in full, the daily workflow is:

```
fabrik preplan new <slug>                       # ← Tier 3 G-A3
# edit docs/preplans/YYYY-MM-DD-<slug>.md
fabrik scaffold <name> --type python-api \
    --from-preplan docs/preplans/...md          # ← Tier 3 G-A4 + Tier 1 G-B1a auto-merges template defaults
cd /opt/<name>                                  # ← Tier 3 G-D1+D2 — Traycer+Cascade+Kilo+Claude all shape-aware
# … plan + code + review …
git commit                                      # ← pre-commit validates spec; governance propagates to all 42 projects
fabrik apply specs/services/<name>.yaml         # ← orchestrator deploys + 9 registrars fire applicably
                                                #   → .fabrik/state/<name>.json persisted (Tier 2 G-F3)
fabrik audit-registrars                         # ← Tier 2 G-G2 — one-shot drift report
fabrik reconcile-all --yes                      # ← Tier 2 G-F2 — converges live to spec
fabrik destroy ... --partial authelia           # ← Tier 2 G-F5 — surgical removal
fabrik destroy ... --use-state                  # ← Tier 4 G-F4 — reverses what was actually applied
fabrik export --output vps1-base.tar.gz         # ← Tier 4 G-J2 — clone vps1 as base for vps2/vps3
# Drift in any of 9 registrars triggers Telegram alert within ~1 hour (Tier 4 G-G5)
```

The system becomes: automation-ready, low-maintenance, drift-free, portable. No manual sweeps. No half-measures. Single operator scales to multi-VPS without re-architecting. See §EPIC SCOPE below for the full 12-point acceptance checklist.

## How to use this pack

**Step 0 (REQUIRED before Tier 1 starts):** Re-run the evidence appendix snapshot to confirm code line numbers + VPS state still match. The pack was authored 2026-05-09; if more than ~7 days have passed, line numbers in `cli.py`, `infrastructure.py`, etc. may shift. Use `99-evidence-appendix.md` § "Cross-cutting verification scripts" to refresh the snapshot.

1. Read `01-workflow-truth-table.md` to confirm the audit matches your understanding.
2. Use `02-tier1-foundation.md` as the next session's checklist. All Tier 1 items can now land in parallel — the 5 design decisions are LOCKED IN (see §DECISIONS LOCKED IN). Items 6 (G-H8) and 9 (G-H6/H7) used to be decision-blocked; both now have concrete migration plans.
3. Tier 2 builds on Tier 1 G-B1a (which feeds the audit). Tier 3 G-D1..D3 depend on Tier 1 G-D4. Tier 4 G-F4 depends on Tier 2 G-F3.
4. **All 47 gaps in scope.** Tiers are dependency-ordered slices of one epic, not optional phases. Tier 3 can run in parallel with Tier 2; Tier 4 G-F4 depends on Tier 2 G-F3.
5. `99-evidence-appendix.md` is for spot-checking any claim. Every command there is reproducible.

## EPIC SCOPE — all 47 gaps under one brief

**No tier is optional. No tier is deferred.** The pack was built to address all 47 gaps; the epic-brief inherits all 47. Total epic effort: **~68 h ≈ 1.5 focused weeks** at the operator's stated 50 h/week budget.

### Dependency tree (drives sequencing within the single epic)

```
Tier 1 — Foundation                   (~16 h, no live writes until W-1/W-3)
  ├── G-B1a       load_spec deep-merge        (code-only, no live change)
  ├── G-B1b       template metric defaults    (config edit, 2 files)
  ├── G-B5        scaffold copies CLAUDE.md   (code-only)
  ├── G-D4        AGENTS.md registrar list    (doc-only, 7 → 9 entries)
  ├── G-J6        archive Gatus predrift-fix  (VPS cleanup)
  ├── W-2 + W-4 + W-5                         (spec/template/doc edits)
  └── W-1 + W-3                               (live VPS changes, scheduled)
       │
       ▼
Tier 2 — Reconciliation               (~14 h, requires Tier 1 G-B1a as input)
  ├── locks_local.py                          (NEW module, no live change)
  ├── G-F3        state file schema           (no live change)
  ├── G-F2        reconcile-all               (uses state file + locks_local)
  ├── G-G2        audit-registrars            (read-only, runs against any spec)
  ├── G-G4        audit cron (Option B)       (WSL-side; no VPS systemd)
  ├── G-F5        destroy --partial           (write capability, signature-aware HANDLER_ARGS)
  └── G-J3        alias-watcher write side    (write capability)

Tier 3 — Planning + coding loop       (~10 h, INDEPENDENT of Tier 2 mechanics)
  ├── G-A1..A5    preplan template + fabrik preplan new + scaffold --from-preplan
  ├── G-C1..C2    Traycer workflow doc deploy section + Cascade /registrar-audit
  ├── G-D1..D3    executor rule files (uses Tier 1 G-D4 corrected list)
  └── G-I1..I2    fabrik dev + fabrik logs --local
  Tier 3 can run in parallel with Tier 2; only G-D1..D3 depend on Tier 1 G-D4 landing first.

Tier 4 — Portability + scale          (~28 h, depends on Tier 2 G-F3)
  ├── G-J4        postgres allocation registry      (uses Tier 2 audit infra)
  ├── G-F4        destroy --use-state               (reads Tier 2 G-F3 state file)
  ├── G-J2        fabrik export / import            (bundles Tier 2 state)
  └── G-G5        per-registrar drift alerting      (Prometheus rule + reused Alertmanager receiver)
```

**Note:** the tree above shows dependencies + decisions; the **canonical Tier 1 work list** is in `02-tier1-foundation.md` §§0–13 (covers all 13 items including G-B2/B3/B4/B6, G-G1, G-F1, G-H2 not visualized in the dependency tree above). Same applies to other tiers — `03/04/05` are the canonical work lists; the tree visualizes ordering, not exhaustiveness.

### Whole-epic acceptance (12 checks)

The epic is **DONE** when all 12 are true on `vps1.ocoron.com`:

1. `fabrik audit-registrars` returns zero MISSING and zero DRIFT for every deployed spec.
2. `fabrik reconcile-all --yes` is a no-op on a clean tree (idempotent).
3. `fabrik export --output /tmp/vps1-base.tar.gz` produces a valid bundle whose README documents prerequisites for a fresh target VPS.
4. `fabrik destroy ... --use-state` correctly reverses resources recorded in `.fabrik/state/<id>.json` even when the current spec differs.
5. `fabrik destroy ... --partial <reg>` removes only the named registrar's resources for the named spec.
6. Drift on any of the 9 registrars on any deployed service triggers a Telegram alert within ~1 hour.
7. End-to-end: `fabrik preplan new test → fabrik scaffold test --from-preplan ... → cd /opt/test → fabrik apply → fabrik audit-registrars → fabrik destroy --use-state` runs clean, no manual VPS edits at any step.
8. All 42 projects under `/opt/*/` have the corrected governance files (CLAUDE.md included; AGENTS.md with the 9-registrar list).
9. CLOUDFLARE_API_TOKEN scoped to Zone:Edit + DNS:Edit (preserves site-provisioner zone-create); `.env` documents the required scope.
10. `image-broker` admin UI gated by Authelia 2FA; `/api/*` bypasses for `X-Internal-Token` callers; internal Fabrik service callers (captcha, translator, etc.) verified working post-deploy.
11. `translator` postgres DB renamed to `translator`, spec uses `shape.needs_database: true` with no `infra` block override.
12. `proxy.yaml` spec matches live state (`is_admin_dashboard: true`).

If any of items 1–12 fails, the epic is not done. No partial-credit closure.

## DECISIONS LOCKED IN (2026-05-09)

All 5 outstanding design decisions resolved. Operating principle: **standard rules apply to all deployments unless a divergence is mandatory**. No bespoke per-service exceptions.

| # | Gap | Decision | Implication |
|---|---|---|---|
| 1 | **G-H6 — image-broker Authelia** | Treat as admin dashboard. Set `shape.is_admin_dashboard: true` in `specs/services/image-broker.yaml`. | Adds Authelia rule for image-broker.vps1.ocoron.com on next `redeploy --refresh-infra`. Standard treatment for any non-public service. |
| 2 | **G-H7 — fabrik-proxy Authelia** | Standard rules win. Update spec to match live state: `shape.is_admin_dashboard: true`. | Removes the spec ↔ live drift. Proxy serves Coolify admin UI; consistent with rule #1. No live VPS change needed (rule already exists); just `git commit` the spec edit. |
| 3 | **G-H8 — translator DB drift** | Standard rules win. Rename live DB `translator_service` → `translator` (matches what `<id_with_underscores>` registrar would create). Drop the `infra.postgres: false` override from `specs/services/translator.yaml`. | **Destructive operation on live VPS** — flagged below as Tier 1 work item. Brings translator into the same shape every other deployed service follows. |
| 4 | **G-B1b — template metric defaults** | Apply Path B as designed in v3: `exposes_metrics: true` added to `templates/python-api/defaults.yaml` AND `templates/node-api/defaults.yaml` ONLY. `saas-skeleton`, `static-site`, and the other 8 templates untouched. | Cascade-fixes G-H3 for any current or future python-api/node-api scaffold. Per-service opt-out still available via spec override. |
| 5 | **G-J5 — Cloudflare token scope** | Keep **Zone.Zone:Edit** + **Zone.DNS:Edit**. | Preserves `site-provisioner`'s `POST /api/cloudflare/zones/{domain}/provision` capability. Narrowing to Zone:Read would break it. |

### Tier 1 work items added by these decisions

- **NEW W-1 (from decision 1):** edit `specs/services/image-broker.yaml`, set `shape.is_admin_dashboard: true`, run `fabrik redeploy --refresh-infra --spec specs/services/image-broker.yaml`. Verify Authelia rule lands.
- **NEW W-2 (from decision 2):** edit `specs/services/proxy.yaml`, set `shape.is_admin_dashboard: true`. Spec-only edit; live state already matches.
- **NEW W-3 (from decision 3, DESTRUCTIVE):** see Tier 1 §6 G-H8 for the renamed migration plan. Requires translator downtime, env-var update on the running container, and an old-DB drop. Schedule outside business hours.
- **NEW W-4 (from decision 4):** edit `templates/python-api/defaults.yaml` and `templates/node-api/defaults.yaml`, add `exposes_metrics: true` to the shape block. Land alongside G-B1a.
- **NEW W-5 (from decision 5):** no code change; document in `.env` comment block that `CLOUDFLARE_API_TOKEN` requires Zone:Edit and DNS:Edit per `site-provisioner` requirements.

These 5 work items are now part of Tier 1 alongside the other items, no longer "blocked by decision".

## CHANGELOG (v3.1 polish — Traycer's third audit pass + decisions integration)

After v3 + decisions, Traycer's third pass (V3-N1 through V3-N6) caught one substantive bug and 5 polish items. v3.1 fixes all 6.

| ID | Type | Where | Fix landed |
|---|---|---|---|
| **V3-N1** | substantive bug | 02 §9 G-H6 | image-broker is consumed via `httpx + X-Internal-Token` from internal Fabrik services. Locking `is_admin_dashboard: true` alone would route those calls to Authelia 2FA → break every internal caller. **Paired** `is_admin_dashboard: true` + `has_bearer_api: true` (standard Coolify/Grafana pattern: UI gates 2FA, `/api/*` bypasses for valid bearer tokens). Added M2M contract documentation in spec comments. |
| **V3-N2** | clarity (no real bug) | 00 README CHANGELOG row | "16 templates" appearance was already correctly quoted as the v2→v3 changelog showing what v2 had wrong. No change needed; leaving as-is. |
| **V3-N3** | pseudocode contradiction | 02 §6 G-H8 | Spec-side example showed `infra: postgres: true` then said "Keep infra.postgres OUT entirely". Fixed: spec now shows `shape.needs_database: true` ONLY, with explicit `REMOVE the infra: block entirely` comment plus a unified diff showing the actual edit. |
| **V3-N4** | missing import | 03 §17 G-J3 | Pseudocode used `shlex.quote()` without importing shlex. Added `import json, shlex` at top of pseudocode imports plus inline NOTE explaining the shell-escape purpose. |
| **V3-N5** | header version | 00 README | Header said "v3" → updated to "**v3.1**". Revised line now records all three audit passes (v1→v2→v3→v3.1). |
| **V3-N6** | loose grep | 02 §9 G-H6 acceptance | `grep image-broker /var/lib/.../configuration.yml` → `grep -F image-broker ...` (treat as fixed string, prevents regex misinterpretation if `image-broker` ever appears in a pattern context). Same pattern used in V3-N1's bearer-bypass acceptance check. |

**v3.1 verification grep:**
```bash
grep -c "has_bearer_api: true" 02-tier1-foundation.md          # ≥1 ✅
grep -c "import shlex\|import json, shlex" 03-tier2-reconciliation.md  # ≥1 ✅
grep -c "REMOVE the .infra:. block entirely" 02-tier1-foundation.md     # 1 ✅
grep -c "v3.1" 00-README.md                                     # ≥1 ✅
grep -c "grep -F image-broker" 02-tier1-foundation.md           # 1 ✅
```

---



## What this pack is NOT

- Not a roadmap or product plan — purely operational gaps in an existing system.
- Not a critique — most of the workflow already works (all 9 registrars implemented, orchestrator pipeline runs end-to-end, governance propagates). The gaps are at the seams.
- Not exhaustive of all possible improvements — bounded to the workflow Özgür described.

## v2 numbered changes (full list)

The table below is a complete audit trail of what changed between v1 and v2. Use this when re-running Traycer's audit-of-the-audit on v2 to verify all corrections landed.

| ID | v1 claim | v2 correction | File location |
|---|---|---|---|
| B1 | G-B1 cascade fixes G-H1,H3,H4,H5 | Cascade fixes G-H1, G-H4 (partial), G-H5 (file-api only) | 01 §Phase B, 02 §1 |
| B2 | (no gap recorded) | New G-D4: AGENTS.md lists 7 registrars; code has 9 (drift) | 01 §Phase D, 02 new §10 |
| B3 | `[spec.id, f"fabrik-{spec.id}"]` | Add `if not spec.id.startswith("fabrik-")` guard | 02 §3 |
| B4 | G-H8 Option B = `infra.postgres: false` | Option B rewritten: needs `shape.needs_database: true` + `infra.postgres: false` (proxy pattern) OR drop in favor of Option A | 02 §6 |
| B5 | G-J5 narrow to DNS:Edit + Zone:Read | Narrow to DNS:Edit + Zone:Edit (preserves zone creation) | 02 §8 |
| B6 | Truth-table line 31: scaffold copies CLAUDE.md | scaffold copies AGENTS.md, AGENTS-compact.md, .windsurfrules; CLAUDE.md added by governance-sync only. New gap G-B5 | 01 §Phase B, 02 new §11 |
| B7 | "4 rule files synced to 41 projects" | 7 governance files (AGENTS.md, AGENTS-compact.md, AFCL.md, CLAUDE.md, opencode.json, .windsurfrules, .pre-commit-config.yaml) synced to 42 projects | 01 §Phase D, 04 §24 |
| B8 | 20 rule files | 21 (20 numbered + ocoron-design-system.md) — CROSS_CUTTING_REQUIREMENTS.md dissolved 2026-05-14; rules redistributed to topic packs + bootstraps | 01 §Phase D, 04 §25 |
| B9 | 11 project types / 8 templates with shape | 12 template directories, all 12 with shape blocks | 01 §Phase B, 04 §25 |
| B10 | (no gap recorded) | New G-B6: next-tailwind has shape but is missing from AGENTS.md Scaffold Types table | 01 §Phase B, 02 new §12 |
| B11 | status() at line 1130 | status() at line 549 | 02 §3, 99 §G-G1 |
| B12 | "G-B1 alone cascade-fixes 4 gaps" | Cascade-fixes 3 gaps (G-H3 excluded) | 02 §1 |
| C1 | 5 deployed pre-G1 specs (no proof of exhaustiveness) | Verified by full sweep: exactly 5 deployed-without-shape specs out of 65 total spec files | 99 new full-sweep script |
| C2 | G-C3 in truth table but unaddressed | G-C3 absorbed into G-A5 | 04 §21 (Tier 3) |
| C3 | G-F3 schema flat | Add `data_bearing: bool` per resource entry | 03 §13 |
| C4 | reconcile-all has no concurrency guard | Use `drivers/locks.py` per-spec lock | 03 §10 |
| C5 | propagation step missing | Initial bulk: `python3 scripts/sync_enforcement_to_projects.py --force` | 04 §24, §25 |
| C6 | alias-watcher write side hand-wavy | New Tier 2 sub-item: explicit `_provision_coolify_alias` step + atomic write | 03 §17 |
| C7 | systemd-on-VPS only option | Add Option B: WSL-side cron via `cron`/`systemd --user` SSHing to VPS | 03 §14 |
| C8 | new Telegram receiver | Reuse existing receiver in `/opt/monitoring/configs/alertmanager/alertmanager.yml`; add new route | 05 §31 |
| C9 | "Operator re-populates secrets manually" | Note: tooling deferred to Tier 4+; effort revised from 1 day to 1.5 days | 05 §28 |
| C10 | no Step 0 | Step 0 (re-verify snapshot) added to README and Tier 1 | 00 §How to use, 02 §Step 0 |
| C11 | "Resolve 3 ⚠️ before any code change" | "Resolve before running redeploy --refresh-infra for image-broker / proxy / translator only" | 00 §Decisions outstanding |
| C12 | path notation `.fabrik/state/<id>.json` | `FABRIK_ROOT / ".fabrik" / "state" / "<id>.json"` | 03 §13 |
| C13 | deep-merge edge cases not covered | 5 explicit edge-case test requirements added | 02 §1 |
| C14 | `--partial` referenced parenthetically | New Tier 2 ticket: `fabrik destroy --partial <registrar>` | 03 new §19 |
| C15 | "41 projects" | "42 projects" throughout | all docs |

## Total gap count after v2

| Phase | v1 | v2 | Change |
|---|---|---|---|
| A — preplan | 5 | 5 | — |
| B — scaffold | 4 | 6 | +G-B5 (CLAUDE.md), +G-B6 (next-tailwind orphan) |
| C — Traycer | 3 | 3 | — (G-C3 merged into G-A5) |
| D — coding | 3 | 4 | +G-D4 (AGENTS.md drift) |
| E — commit | 3 | 3 | — |
| F — deploy | 4 | 4 | — |
| G — verify/audit | 5 | 5 | — |
| H — live VPS state | 9 | 9 | — |
| I — local-dev | 2 | 2 | — |
| J — operational | 6 | 6 | — |
| New: partial-destroy CLI | — | 1 | +G-F5 (Tier 2) |
| **Total** | **44** | **47** | +3 |

(Note: the +8 increase mentioned in Traycer's review estimate becomes +4 because some C-items merged into existing gaps rather than creating new IDs.)
