# Phase B — Findings

Generated: 2026-07-08

| script | deterministic | no-null-propagation | in-order | cross-consistent | severity | summary | fix-commit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| derive_quality_v2.py | yes | no | yes | n/a | PLAUSIBLE | no NULL guard on UPDATE path | — |
| derive_cheapest_gateway.py | yes | yes | yes | yes | STYLE | all 4 audit criteria pass | — |
| classify_ai_category.py | yes | yes | yes | yes | STYLE | all 4 audit criteria pass | — |
| category_route_mapper.py | yes | yes | yes | n/a | STYLE | all 4 audit criteria pass | — |
| role_mapper.py | yes | no | yes | n/a | PLAUSIBLE | no NULL guard on UPDATE path | — |
| embedding_role_mapper.py | yes | no | yes | n/a | STYLE | all 4 audit criteria pass | — |
| backfill_unknown_providers.py | yes | no | yes | n/a | PLAUSIBLE | no NULL guard on UPDATE path | — |
