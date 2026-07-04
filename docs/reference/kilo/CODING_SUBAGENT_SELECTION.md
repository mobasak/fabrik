# Coding subagent selection

**Generated:** 2026-07-04 · **Source:** `scripts/kilo-benchmarks/kilo_agents.db` · **Generator:** `scripts/kilo-benchmarks/rank_coding_subagents.py`

Ranked candidates for coding-subagent dispatch across the GLM (z-ai), Kimi (moonshotai), Minimax, and DeepSeek families. Regenerated daily by `scripts/kilo-benchmarks/daily_refresh.sh` after pricing and microbench data refreshes.

> **Score composition**: 45% best-verified code score (max of SWE-bench-Verified and Aider-Polyglot — whichever is available) · 20% AA intelligence index · 15% Arena ELO · 10% output tok/s · 10% cost-inverse. Every component normalized to [0,1] before its weight is applied. Higher = better fit.

> **Doc↔Code grade**: composite of context size (fits code + docs together), verified code-understanding score, and general intelligence — measures ability to spot drift between documentation and implementation.

## Ranked table

| # | Model | OR | OR_prov | db_tps | In $/M | Out $/M | SWE | Aider | AA | Arena | Ctx | Doc↔Code | Score |
|---:|---|:-:|---|---:|---:|---:|---:|---:|---:|---:|---:|:-:|---:|
| 1 | `minimax/minimax-m2.5` | ✅ | Inceptron | 54 | 0.120 | 0.480 | 75.8 | — | — | 1436 | 204k | **B+** | 0.576 |
| 2 | `z-ai/glm-5` | ✅ | DeepInfra | 68 | 0.600 | 1.920 | 72.8 | — | — | 1461 | 202k | **B+** | 0.571 |
| 3 | `deepseek/deepseek-v3.2` | ✅ | StreamLake | 63 | 0.229 | 0.343 | 70.0 | 70.2 | — | 1431 | 131k | **B** | 0.551 |
| 4 | `z-ai/glm-4.6` | ✅ | DeepInfra | 68 | 0.430 | 1.740 | 68.2 | — | — | 1458 | 202k | **B** | 0.550 |
| 5 | `z-ai/glm-4.5` | ✅ | Z.AI | 69 | 0.600 | 2.200 | 64.2 | — | — | 1448 | 131k | **C+** | 0.520 |
| 6 | `deepseek/deepseek-r1` | ✅ | Novita | 18 | 0.700 | 2.500 | — | 71.4 | — | 1382 | 163k | **B** | 0.475 |
| 7 | `moonshotai/kimi-k2.5` | ✅ | DigitalOcean | 46 | 0.375 | 2.025 | 70.8 | — | — | — | 262k | **B+** | 0.470 |
| 8 | `moonshotai/kimi-k2` | ✅ | Novita | 37 | 0.570 | 2.300 | — | 59.1 | — | 1402 | 131k | **C+** | 0.450 |
| 9 | `minimax/minimax-m2` | ✅ | Minimax | 54 | 0.255 | 1.020 | 61.0 | — | — | — | 204k | **C+** | 0.440 |
| 10 | `minimax/minimax-m3` | ✅ | Minimax | 94 | 0.300 | 1.200 | — | — | 44 | 1485 | 1048k | **A+** | 0.421 |
| 11 | `deepseek/deepseek-v4-flash` | ✅ | DeepInfra | 102 | 0.090 | 0.180 | — | — | 40 | 1460 | 1048k | **A** | 0.401 |
| 12 | `z-ai/glm-5.1` | ✅ | DigitalOcean | 62 | 0.966 | 3.036 | — | — | 40 | 1506 | 202k | **B** | 0.397 |
| 13 | `minimax/minimax-m2.7` | ✅ | DeepInfra | 51 | 0.180 | 0.720 | — | — | 38 | 1448 | 204k | **B-** | 0.367 |
| 14 | `z-ai/glm-5.2` | ✅ | DeepInfra | 186 | 0.910 | 2.860 | — | — | 51 | — | 1048k | **A+** | 0.339 |
| 15 | `deepseek/deepseek-v4-pro` | ✅ | DeepSeek | 59 | 0.435 | 0.870 | — | — | 44 | — | 1048k | **A** | 0.315 |
| 16 | `moonshotai/kimi-k2.6` | ✅ | Inceptron | 46 | 0.660 | 3.410 | — | — | 43 | — | 262k | **B** | 0.281 |
| 17 | `moonshotai/kimi-k2.7-code` | ✅ | DeepInfra | 46 | 0.740 | 3.500 | — | — | 42 | — | 262k | **B** | 0.276 |
| 18 | `z-ai/glm-4.7` | ✅ | DeepInfra | 70 | 0.400 | 1.750 | — | — | — | 1460 | 202k | **B** | 0.245 |
| 19 | `minimax/minimax-m2.1` | ✅ | Minimax | 61 | 0.300 | 1.200 | — | — | — | 1430 | 204k | **B-** | 0.225 |
| 20 | `z-ai/glm-4.5-air` | ✅ | Novita | 105 | 0.130 | 0.850 | — | — | — | 1410 | 131k | **C+** | 0.224 |
| 21 | `deepseek/deepseek-v3.2-exp` | ✅ | Novita | 35 | 0.270 | 0.410 | — | — | — | 1431 | 163k | **C+** | 0.224 |
| 22 | `deepseek/deepseek-chat-v3.1` | ✅ | DeepInfra | 23 | 0.210 | 0.790 | — | — | — | 1430 | 163k | **C+** | 0.212 |
| 23 | `deepseek/deepseek-r1-0528` | ✅ | DeepInfra | 16 | 0.500 | 2.150 | — | — | — | 1436 | 163k | **C+** | 0.196 |
| 24 | `deepseek/deepseek-v4-flash:discounted` | — | INVALID_ID_8662 | 108 | 0.000 | 0.000 | — | — | — | — | 1048k | **B** | 0.189 |
| 25 | `deepseek/deepseek-chat-v3-0324` | ✅ | DeepInfra | 27 | 0.240 | 0.900 | — | — | — | 1391 | 163k | **C** | 0.184 |
| 26 | `moonshotai/kimi-k2-0905` | ✅ | Novita | 38 | 0.600 | 2.500 | — | — | — | 1403 | 262k | **B-** | 0.183 |
| 27 | `deepseek/deepseek-v4-pro:discounted` | — | INVALID_ID_8662 | 74 | 0.000 | 0.000 | — | — | — | — | 1048k | **B** | 0.181 |
| 28 | `minimax/minimax-m2-her` | ✅ | Minimax | 87 | 0.300 | 1.200 | — | — | — | — | 65k | **C** | 0.172 |
| 29 | `z-ai/glm-4.7-flash` | ✅ | DeepInfra | 54 | 0.060 | 0.400 | — | — | — | — | 202k | **C+** | 0.171 |
| 30 | `deepseek/deepseek-r1-distill-llama-70b` | ✅ | Novita | 45 | 0.800 | 0.800 | — | — | — | — | 128k | **C** | 0.163 |
| 31 | `deepseek/deepseek-chat` | ✅ | StreamLake | 42 | 0.200 | 0.800 | — | — | — | 1337 | 131k | **C** | 0.162 |
| 32 | `minimax/minimax-m1` | ✅ | Minimax | 41 | 0.400 | 2.200 | — | — | — | 1369 | 1000k | **B** | 0.162 |
| 33 | `z-ai/glm-4.6v` | ✅ | Novita | 33 | 0.300 | 0.900 | — | — | — | — | 131k | **C** | 0.157 |
| 34 | `z-ai/glm-4.5v` | ✅ | Novita | 50 | 0.600 | 1.800 | — | — | — | — | 65k | **C** | 0.155 |
| 35 | `deepseek/deepseek-v3.1-terminus` | ✅ | DeepInfra | 24 | 0.270 | 0.950 | — | — | — | — | 163k | **C** | 0.151 |
| 36 | `minimax/minimax-01` | ✅ | Minimax | 22 | 0.200 | 1.100 | — | — | — | — | 1000k | **B** | 0.148 |
| 37 | `z-ai/glm-5-turbo` | ✅ | AtlasCloud | 43 | 1.200 | 4.000 | — | — | — | — | 262k | **C+** | 0.129 |
| 38 | `z-ai/glm-5v-turbo` | ✅ | Z.AI | 36 | 1.200 | 4.000 | — | — | — | — | 202k | **C+** | 0.126 |

## API call recipes (OpenRouter)

Base endpoint: `POST https://openrouter.ai/api/v1/chat/completions` with `Authorization: Bearer $OPENROUTER_API_KEY`.

| Model | Extra body params |
|---|---|
| `minimax/minimax-m2.5` | `{"reasoning":{"exclude":true},"max_tokens":30000}` |
| `z-ai/glm-5` | `{"max_tokens":20000}` |
| `deepseek/deepseek-v3.2` | `{"reasoning":{"exclude":true}}` |
| `minimax/minimax-m3` | `{"provider":{"only":["Minimax","Novita","Parasail","Together"]}}` |

## Excluded from the pool

| Model | Reason |
|---|---|
| `moonshotai/kimi-k2-thinking` | Reasoning-mandatory model that returns 0 output tokens when reasoning is excluded — not a code-producing model. |

## How this file stays fresh

1. Nightly at 06:00 UTC, `daily_refresh.sh` runs the pricing + microbench pipeline that populates `kilo_agents.db`.
2. Immediately after `derive_cheapest_gateway.py`, this script queries the DB and regenerates the table.
3. `EXCLUDE_MODELS`, `PROVIDER_PINS`, and `BODY_HINTS` in the generator are hand-maintained — when a new provider bug or reasoning-only model is discovered, add it there and re-run.
