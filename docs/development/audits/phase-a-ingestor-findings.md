# Phase A — Findings

Generated: 2026-07-08

| script | ran | dry-run | writes-tagged | fail-soft | severity | summary | fix-commit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| verify_openrouter_catalog.py | yes | no | yes | no | PLAUSIBLE | no --dry-run flag; no explicit HTTP-error catch | — |
| restore_wrongly_deprecated_direct_vendors.py | yes | no | no | no | PLAUSIBLE | no --dry-run flag; write path not tagged (missing INSERT OR IGNORE / UPDATE ... WHERE id=?); no explicit HTTP-error catc | — |
| discover_hidden_openrouter_routes.py | yes | no | yes | yes | STYLE | no --dry-run flag | — |
| scrape_openrouter_rankings.py | yes | no | yes | no | CONFIRMED | no --dry-run flag; no speed_source/last_verified/status set; no explicit HTTP-error catch | — |
| scrape_openrouter_endpoints.py | yes | no | yes | no | PLAUSIBLE | no --dry-run flag; no explicit HTTP-error catch | — |
| scrape_coding_benchmarks.py | yes | yes | yes | yes | CONFIRMED | no speed_source/last_verified/status set | — |
| scrape_artificial_analysis.py | yes | yes | yes | yes | STYLE | all 4 audit criteria pass | — |
| scrape_groq_speeds.py | yes | yes | yes | yes | STYLE | all 4 audit criteria pass | — |
| scrape_windsurf_models.py | yes | no | no | yes | CONFIRMED | no --dry-run flag; write path not tagged (missing INSERT OR IGNORE / UPDATE ... WHERE id=?); no speed_source/last_verifi | — |
| fetch_replicate_prices.py | yes | yes | yes | yes | CONFIRMED | no speed_source/last_verified/status set | — |
| fetch_fal_prices.py | yes | yes | yes | yes | CONFIRMED | no speed_source/last_verified/status set | — |
| fetch_direct_vendor_prices.py | yes | no | yes | yes | STYLE | no --dry-run flag | — |
| microbench_or_models.py | yes | yes | yes | yes | STYLE | all 4 audit criteria pass | — |
