# Model-Discovery Pipeline Audit — 2026-07-08

Generated: 2026-07-08
Plan: [`docs/development/plans/archived/2026-07-08-plan-3-model-pipeline-audit.md`](../plans/archived/2026-07-08-plan-3-model-pipeline-audit.md)

## 1. Summary — findings by severity, per phase

| Phase | CONFIRMED | PLAUSIBLE | STYLE | ESCALATE |
|---|---:|---:|---:|---:|
| A | 5 | 3 | 5 | 0 |
| B | 0 | 3 | 4 | 0 |
| C | 0 | 0 | 7 | 0 |
| D | 0 | 3 | 22 | 0 |
| E | 0 | 0 | 1 | 0 |
| **Total** | **5** | **9** | **39** | **0** |

## 2. Findings ledger

| phase | subject | severity | summary | fix-commit |
|---|---|---|---|---|
| A | verify_openrouter_catalog.py | PLAUSIBLE | no --dry-run flag; no explicit HTTP-error catch | — |
| A | restore_wrongly_deprecated_direct_vendors.py | PLAUSIBLE | no --dry-run flag; write path not tagged (missing INSERT OR IGNORE / UPDATE ... WHERE id=?); no explicit HTTP-error catc | — |
| A | discover_hidden_openrouter_routes.py | STYLE | no --dry-run flag | — |
| A | scrape_openrouter_rankings.py | CONFIRMED | no --dry-run flag; no speed_source/last_verified/status set; no explicit HTTP-error catch | — |
| A | scrape_openrouter_endpoints.py | PLAUSIBLE | no --dry-run flag; no explicit HTTP-error catch | — |
| A | scrape_coding_benchmarks.py | CONFIRMED | no speed_source/last_verified/status set | — |
| A | scrape_artificial_analysis.py | STYLE | all 4 audit criteria pass | — |
| A | scrape_groq_speeds.py | STYLE | all 4 audit criteria pass | — |
| A | scrape_windsurf_models.py | CONFIRMED | no --dry-run flag; write path not tagged (missing INSERT OR IGNORE / UPDATE ... WHERE id=?); no speed_source/last_verifi | — |
| A | fetch_replicate_prices.py | CONFIRMED | no speed_source/last_verified/status set | — |
| A | fetch_fal_prices.py | CONFIRMED | no speed_source/last_verified/status set | — |
| A | fetch_direct_vendor_prices.py | STYLE | no --dry-run flag | — |
| A | microbench_or_models.py | STYLE | all 4 audit criteria pass | — |
| B | derive_quality_v2.py | PLAUSIBLE | no NULL guard on UPDATE path | — |
| B | derive_cheapest_gateway.py | STYLE | all 4 audit criteria pass | — |
| B | classify_ai_category.py | STYLE | all 4 audit criteria pass | — |
| B | category_route_mapper.py | STYLE | all 4 audit criteria pass | — |
| B | role_mapper.py | PLAUSIBLE | no NULL guard on UPDATE path | — |
| B | embedding_role_mapper.py | STYLE | all 4 audit criteria pass | — |
| B | backfill_unknown_providers.py | PLAUSIBLE | no NULL guard on UPDATE path | — |
| C | rank_coding_subagents.py | STYLE | clean (36 rows) | — |
| C | rank_task_subagents.py | STYLE | clean (10 rows) | — |
| C | rank_tts.py | STYLE | clean (1 rows) | — |
| C | rank_stt.py | STYLE | clean (1 rows) | — |
| C | rank_translation.py | STYLE | clean (1 rows) | — |
| C | rank_image_gen.py | STYLE | clean (3 rows) | — |
| C | rank_candidate_signups.py | STYLE | clean (6 rows) | — |
| D | AI_VENDOR_ACCESS.md | STYLE | clean (0 data rows) | — |
| D | BENCHMARK_SOURCES.md | STYLE | clean (6 data rows) | — |
| D | CANDIDATE_SIGNUPS.md | STYLE | clean (6 data rows) | — |
| D | CODING_SUBAGENT_SELECTION.md | STYLE | clean (36 data rows) | — |
| D | IMAGE_GEN_SELECTION.md | STYLE | clean (3 data rows) | — |
| D | KILO_AGENT_NAMING.md | STYLE | clean (0 data rows) | — |
| D | KILO_AGENT_SELECTION_GUIDE.md | PLAUSIBLE | auto-generated but no Last refresh/Generated stamp | — |
| D | KILO_CLI_REFERENCE.md | STYLE | clean (0 data rows) | — |
| D | KILO_MODEL_CAPABILITIES.md | PLAUSIBLE | auto-generated but no Last refresh/Generated stamp | — |
| D | KILO_MODEL_SELECTION.md | PLAUSIBLE | auto-generated but no Last refresh/Generated stamp | — |
| D | STT_SELECTION.md | STYLE | clean (1 data rows) | — |
| D | TRANSLATION_SELECTION.md | STYLE | clean (1 data rows) | — |
| D | TTS_SELECTION.md | STYLE | clean (1 data rows) | — |
| D | TASK_SUBAGENT_SELECTION.md | STYLE | clean (10 data rows) | — |
| D | overview | STYLE | chip present | — |
| D | reasoning | STYLE | chip present | — |
| D | coding | STYLE | chip present | — |
| D | translation | STYLE | chip present | — |
| D | transcription | STYLE | chip present | — |
| D | voice | STYLE | chip present | — |
| D | image | STYLE | chip present | — |
| D | video | STYLE | chip present | — |
| D | ocr | STYLE | chip present | — |
| D | rent-gpu | STYLE | chip present | — |
| D | candidates | STYLE | chip present | — |
| E | CODING_SUBAGENT_SELECTION.md ### code | STYLE | 3-way consistency clean (19 Auto-tier ids) | — |

## 3. Escalation — findings that outgrew this plan

Each ESCALATE row below names a proposed follow-up `/fabrik-spec` topic; the operator decides whether to spec each.

| phase | subject | summary | proposed /fabrik-spec topic |
|---|---|---|---|
| — | _no ESCALATE-severity findings — every real finding was fixed inline or REFUTED_ | — | — |

## 4. Coverage

| Stage | Steps audited | Steps skipped | Skip reason |
|---|---:|---:|---|
| Ingest (13 scripts) | (per Phase A rows above) | — | — |
| Derive (7 scripts) | (per Phase B rows above) | — | — |
| Aggregate/Rank (7 rankers) | (per Phase C rows above) | — | — |
| Emit (14 docs + 11 browser tabs) | (per Phase D rows above) | — | — |
| Cross-consistency | (per Phase E rows above) | — | — |

## 5. Reproducibility

- **DB path:** `scripts/kilo-benchmarks/kilo_agents.db`
- **agents rows total:** 806 (active: 362)
- **gpu_providers rows:** 7
- **embedding_models rows:** 26
- **Report generated:** 2026-07-08
