# Docs-truth verification ledger — wave: orchestrator (Tier A)

**Plan:** `docs/development/plans/2026-07-20-plan-1-docs-truth-convergence.md` Phase E · **Date:** 2026-07-20
**Method:** claim-level verification (native Opus verifiers, partitioned; every falsifiable claim extracted and checked against the repo; every FALSE/STALE fixed in-place the same day). Verdicts: VERIFIED / FALSE / STALE / UNVERIFIABLE-EXTERNAL.

## Coverage & counts

| Slice | Docs | Claims checked | Non-VERIFIED found |
|---|---|---:|---:|
| ettw 00–02 (+01R) | 4 | ~89 | 1 STALE + 1 count-nuance |
| ettw 03–06 | 4 | ~54 | 4 STALE |
| ettw 07–11 | 5 | ~122 | 1 STALE (disclaimed-transitional) |
| checklists + north-star + wiring + schema | 5 | ~183 | 8 STALE (naming/counts/line-pointers) |
| mega 00/02/03/04 + cockpit ×3 + _retired/05 banner + 17 skills | 25 | ~200 | 3 FALSE + 5 STALE |
| **Total** | **43** | **~648** | **23** |

All 17 `_traycer-skills/*/SKILL.md` byte-identical to their deployed `~/.claude/skills` twins (zero drift).

## Findings → dispositions (all FIXED 2026-07-20 unless noted)

| Doc | Finding | Disposition |
|---|---|---|
| ettw-00:97 | retired mega-05 framed live | FIXED → 04 (absorbed 05) |
| ettw-00:54 | "11 scaffold types" vs 12-member registry | RETAINED-BY-CONVENTION (wordpress deploy-only; consistent repo-wide incl. CLAUDE.md) |
| ettw-03:50 | `scaffold.py:5566` wrong line + route contradiction | FIXED → :5695-5703 + wpf/web-ecommerce-factory distinction stated |
| ettw-03/04 | `SpecShape` — no such symbol | FIXED → `Shape` (:205) + `Kind` (:18) |
| ettw-05:12,100 | AGENTS.md § cite → stub | FIXED → agents-fabrik.md:431 |
| ettw-05 body | retired mega-05 + `-command` refs meaning the live chain | FIXED (7 sites; header "twin of -command" framing correctly retained) |
| ettw-07..10 footers | `-command` refs, twins since landed | FIXED → `-fabrik` |
| ettw checklist items 29,100-102,124,126,129,130,165 | `-command` file names | FIXED → `-fabrik` |
| ettw checklist item 128 | "12 ettw + 5 mega" counts | FIXED → 13 ettw + 4 live mega |
| north-star:109 | fabrik-review.md:110 pointer drift | FIXED → :135-136 |
| north-star:160 R16 | hop list includes retired 05 | FIXED → 02→03→04→agent |
| mega-00:43, 02:37 | select_rules `:108` branch drift | FIXED → `:137` |
| mega-00:367,635,672 | Kilo CLI framed as live gateway | FIXED (retired-noted; underlying packs `65-rag-search`/`ai/30` pending update — recorded in completion report, packs outside this plan's File Scope) |
| mega-03:100 | agent.py:740-742 → sentinel logic | FIXED → :890-892 |
| cockpit ×3 | `fabrik-lib/subagents` literal path | FIXED → `libs/subagents` |
| cockpit-decisions:253 | 03:24 provenance cite | FIXED → :60 |

## Verified load-bearing spot-checks (proof retained in verifier transcripts)

`_REGISTRAR_ORDER` 10 registrars (`infrastructure.py:136`) + watchdog opt-out (`:314`) · `verify.py:394` rollback stub · 12 `SCAFFOLD_TYPES` (`scaffold.py:138`) · `I18N_ENABLED_TYPES` 5 members (`:186`) · 46 enforcement checks · `pick_models` (`select.py:430`) / `fanout` (`agent.py:735`) / `set_quality` (`pg_ledger.py:269`) / `record_run` silent-no-op confirmed · `deployer_ssh.py:684-689` memory-limit gate · `specs/verification/registrars.yaml` exists · CLI subcommands (plan/apply/redeploy/scaffold/verify/preplan/review/dev/export/import/destroy/audit-registrars/reconcile-all/domain-ready/logs) all present · service_catalog = 90 services · retired-tool framing past-tense everywhere post-fix.

**UNRESOLVED rows: 0.**
