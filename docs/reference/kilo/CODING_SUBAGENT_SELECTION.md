# Coding subagent selection

**Generated:** 2026-07-27 · **Source:** `scripts/kilo-benchmarks/kilo_agents.db` · **Generator:** `scripts/kilo-benchmarks/rank_coding_subagents.py`

Ranked candidates for coding-subagent dispatch across the GLM (z-ai), Kimi (moonshotai), Minimax, and DeepSeek families. Regenerated daily by `scripts/kilo-benchmarks/daily_refresh.sh` after pricing and microbench data refreshes.

> **Score composition**: 45% best-verified code score (max of SWE-bench-Verified and Aider-Polyglot; falls back to our own live HumanEval+/MBPP+ `coding_score` × 0.7 when neither external benchmark is populated) · 20% AA intelligence index · 15% Arena ELO · 10% output tok/s · 10% cost-inverse. Every component normalized to [0,1] before its weight is applied. Higher = better fit.

> **Doc↔Code grade + pass@1**: coding capability. `†` = MEASURED — the measured **coding** grade from `scripts/kilo-benchmarks/microbench_coding_direct.py` (LiveCodeBench pass@1, shown in the `pass@1` column) wins when present; else the measured **review** grade from `microbench_review.py` (ground-truth planted-bug corpus — code-understanding proxy); unmarked = the heuristic composite of context size + verified code-understanding score + general intelligence. `pass@1` = LiveCodeBench coding accuracy (contamination-free); `—` until the coding bench has run on that model. (The row **sort** is the composite `Score`, not the grade — the grade/pass@1 are the coding signal; `pick_models("code")` ranks on the measured `model_task_baseline` prior.)

> **Column key** — `Reason` = native reasoning / thinking capability (may need `reasoning={"exclude":true}` in the request body for pure code — see API recipes). `Bench` = ✅ if `scripts/kilo-benchmarks/microbench_coding.py` has run our own live HumanEval+/MBPP+ pass_at_1 on this model (`humaneval_score` populated); `—` = external benchmarks only, our own live signal is not yet available. Un-benched candidates worth prioritizing are listed under **Candidates not yet benched by us** below.

## Ranked table

### code

Auto tier — OpenRouter output ≤ $1.5/Mtok. `pick_models` auto-selects freely from this table (no operator approval required).

| # | Model | OR | OR_prov | Reason | Bench | db_tps | In $/M | Out $/M | SWE | Aider | AA | Arena | Ctx | Doc↔Code | pass@1 | Score |
|---:|---|:-:|---|:-:|:-:|---:|---:|---:|---:|---:|---:|---:|---:|:-:|---:|---:|
| 1 | `minimax/minimax-m2.5` | ✅ | Inceptron | ✅ | — | 54 | 0.150 | 0.900 | 75.8 | — | — | 1436 | 204k | **A†** | 81% | 0.572 |
| 2 | `deepseek/deepseek-v3.2` | ✅ | Baidu | ✅ | — | 63 | 0.269 | 0.400 | 70.0 | 70.2 | — | 1431 | 163k | **B+†** | 78% | 0.551 |
| 3 | `bytedance-seed/seed-2.0-mini` | ✅ | Seed | ✅ | ✅ | 135 | 0.100 | 0.400 | — | — | — | — | 262k | **A+†** | 90% | 0.474 |
| 4 | `bytedance-seed/seed-1.6-flash` | ✅ | Seed | ✅ | ✅ | 132 | 0.075 | 0.300 | — | — | — | — | 262k | **A†** | 84% | 0.464 |
| 5 | `qwen/qwen3-coder-30b-a3b-instruct` | ✅ | Novita | — | ✅ | 104 | 0.070 | 0.270 | — | — | — | — | 262k | **C+** | — | 0.458 |
| 6 | `qwen/qwen3-coder-flash` | ✅ | Alibaba | — | ✅ | 123 | 0.195 | 0.975 | — | — | — | — | 1000k | **B+†** | 74% | 0.452 |
| 7 | `minimax/minimax-m2` | ✅ | Minimax | ✅ | — | 54 | 0.255 | 1.020 | 61.0 | — | — | — | 204k | **C+** | — | 0.440 |
| 8 | `minimax/minimax-m3` | ✅ | GMICloud | ✅ | — | 73 | 0.300 | 1.200 | — | — | 44 | 1485 | 1048k | **B†** | 67% | 0.417 |
| 9 | `z-ai/glm-4.7-flash` | ✅ | DeepInfra | ✅ | ✅ | 54 | 0.060 | 0.400 | — | — | — | — | 202k | **A+†** | 95% | 0.413 |
| 10 | `deepseek/deepseek-v4-flash` | ✅ | DeepInfra | ✅ | — | 121 | 0.140 | 0.280 | — | — | 38 | 1460 | 1048k | **A+†** | 94% | 0.398 |
| 11 | `minimax/minimax-m2.7` | ✅ | Mara | ✅ | — | 69 | 0.250 | 1.000 | — | — | 38 | 1448 | 204k | **A†** | 84% | 0.370 |
| 12 | `deepseek/deepseek-v4-pro` | ✅ | DeepSeek | ✅ | — | 75 | 0.435 | 0.870 | — | — | 44 | — | 1048k | **A+†** | 92% | 0.317 |
| 13 | `qwen/qwen3-coder-next` | ✅ | Ionstream | — | — | 129 | 0.110 | 0.800 | — | — | 21 | — | 262k | **A+†** | 90% | 0.254 |
| 14 | `minimax/minimax-m2.1` | ✅ | Minimax | ✅ | — | 61 | 0.300 | 1.200 | — | — | — | 1430 | 204k | **B-** | — | 0.225 |
| 15 | `z-ai/glm-4.5-air` | ✅ | Novita | ✅ | — | 105 | 0.130 | 0.850 | — | — | — | 1410 | 131k | **A†** | 80% | 0.224 |
| 16 | `deepseek/deepseek-v3.2-exp` | ✅ | Novita | ✅ | — | 35 | 0.270 | 0.410 | — | — | — | 1431 | 163k | **A+†** | 92% | 0.224 |
| 17 | `deepseek/deepseek-chat-v3.1` | ✅ | DeepInfra | ✅ | — | 23 | 0.250 | 0.950 | — | — | — | 1430 | 163k | **C+** | — | 0.210 |
| 18 | `deepseek/deepseek-chat-v3-0324` | ✅ | Novita | — | — | 27 | 0.270 | 1.120 | — | — | — | 1391 | 163k | **C** | — | 0.182 |
| 19 | `minimax/minimax-m2-her` | ✅ | Minimax | — | — | 87 | 0.300 | 1.200 | — | — | — | — | 65k | **C** | — | 0.172 |
| 20 | `deepseek/deepseek-r1-distill-llama-70b` | ✅ | Novita | ✅ | — | 45 | 0.800 | 0.800 | — | — | — | — | 8k | **A†** | 83% | 0.163 |
| 21 | `deepseek/deepseek-chat` | ✅ | StreamLake | — | — | 42 | 0.200 | 0.800 | — | — | — | 1337 | 163k | **C** | — | 0.162 |
| 22 | `z-ai/glm-4.6v` | ✅ | Novita | ✅ | — | 33 | 0.300 | 0.900 | — | — | — | — | 131k | **C** | — | 0.157 |
| 23 | `deepseek/deepseek-v3.1-terminus` | ✅ | DeepInfra | ✅ | — | 24 | 0.270 | 1.000 | — | — | — | — | 163k | **C** | — | 0.150 |
| 24 | `minimax/minimax-01` | ✅ | Minimax | — | — | 22 | 0.200 | 1.100 | — | — | — | — | 1000k | **B** | — | 0.148 |

### code-onrequest

On-request tier — OpenRouter output > $1.5/Mtok. Operator opt-in only: `pick_models` NEVER auto-promotes these. Selectable when the operator names one this turn and says why the Auto tier didn't suffice for this specific hard task. A pricier model that benchmarks brilliantly stays here until its OR output price drops ≤ $1.5/Mtok, at which point it auto-joins Auto on the next daily refresh.

| # | Model | OR | OR_prov | Reason | Bench | db_tps | In $/M | Out $/M | SWE | Aider | AA | Arena | Ctx | Doc↔Code | pass@1 | Score |
|---:|---|:-:|---|:-:|:-:|---:|---:|---:|---:|---:|---:|---:|---:|:-:|---:|---:|
| 1 | `z-ai/glm-5` | ✅ | StreamLake | ✅ | — | 68 | 0.950 | 2.550 | 72.8 | — | — | 1461 | 204k | **A†** | 90% | 0.564 |
| 2 | `z-ai/glm-4.6` | ✅ | Venice | ✅ | — | 68 | 0.500 | 2.000 | 68.2 | — | — | 1458 | 204k | **B** | — | 0.547 |
| 3 | `z-ai/glm-4.5` | ✅ | Z.AI | ✅ | — | 69 | 0.600 | 2.200 | 64.2 | — | — | 1448 | 131k | **C+** | — | 0.520 |
| 4 | `deepseek/deepseek-r1` | ✅ | Novita | ✅ | — | 18 | 0.700 | 2.500 | — | 71.4 | — | 1382 | 163k | **B** | — | 0.475 |
| 5 | `moonshotai/kimi-k2.5` | ✅ | DigitalOcean | ✅ | — | 46 | 0.570 | 2.850 | 70.8 | — | — | — | 262k | **A+†** | 98% | 0.462 |
| 6 | `bytedance-seed/seed-2.0-lite` | ✅ | Seed | ✅ | ✅ | 73 | 0.250 | 2.000 | — | — | — | — | 262k | **A+†** | 100% | 0.450 |
| 7 | `moonshotai/kimi-k2` | ✅ | Novita | — | — | 37 | 0.570 | 2.300 | — | 59.1 | — | 1402 | 131k | **C+** | — | 0.450 |
| 8 | `bytedance-seed/seed-1.6` | ✅ | Seed | ✅ | ✅ | 48 | 0.250 | 2.000 | — | — | — | — | 262k | **A+†** | 98% | 0.443 |
| 9 | `z-ai/glm-5.1` | ✅ | StreamLake | ✅ | — | 74 | 0.966 | 3.036 | — | — | 40 | 1506 | 204k | **A+†** | 98% | 0.400 |
| 10 | `z-ai/glm-5.2` | ✅ | StreamLake | ✅ | — | 183 | 0.718 | 2.257 | — | — | 42 | — | 1048k | **A+†** | 96% | 0.316 |
| 11 | `moonshotai/kimi-k2.6` | ✅ | Inceptron | ✅ | — | 37 | 0.646 | 2.720 | — | — | 44 | — | 262k | **A+†** | 98% | 0.287 |
| 12 | `moonshotai/kimi-k2.7-code` | ✅ | CoreWeave | ✅ | — | 48 | 0.780 | 3.500 | — | — | 42 | — | 262k | **A+†** | 98% | 0.277 |
| 13 | `z-ai/glm-4.7` | ✅ | DeepInfra | ✅ | — | 70 | 0.400 | 1.750 | — | — | — | 1460 | 204k | **B** | — | 0.245 |
| 14 | `deepseek/deepseek-r1-0528` | ✅ | DeepInfra | ✅ | — | 16 | 0.500 | 2.150 | — | — | — | 1436 | 163k | **C+** | — | 0.196 |
| 15 | `moonshotai/kimi-k2-0905` | ✅ | Novita | — | — | 38 | 0.600 | 2.500 | — | — | — | 1403 | 262k | **B-** | — | 0.183 |
| 16 | `minimax/minimax-m1` | ✅ | Minimax | ✅ | — | 41 | 0.550 | 2.200 | — | — | — | 1369 | 1000k | **B** | — | 0.162 |
| 17 | `z-ai/glm-4.5v` | ✅ | Novita | ✅ | — | 50 | 0.600 | 1.800 | — | — | — | — | 65k | **C** | — | 0.155 |
| 18 | `qwen/qwen3-coder-plus` | ✅ | Alibaba | — | — | 36 | 0.650 | 3.250 | — | — | — | — | 1000k | **A†** | 88% | 0.135 |
| 19 | `z-ai/glm-5-turbo` | ✅ | Z.AI | ✅ | — | 43 | 1.200 | 4.000 | — | — | — | — | 202k | **A+†** | 98% | 0.129 |
| 20 | `z-ai/glm-5v-turbo` | ✅ | Z.AI | ✅ | — | 36 | 1.200 | 4.000 | — | — | — | — | 202k | **B+†** | 76% | 0.126 |

## Candidates not yet benched by us

Auto-tier coding candidates (OR-reachable, output ≤ $1.5/Mtok) with no live pass_at_1 from `scripts/kilo-benchmarks/microbench_coding.py` AND no external SWE-bench / Aider-Polyglot / AA-idx signal. Their composite score rests only on TPS + cost until benched, so their ranking is provisional — an explicit `microbench_coding.py --models <id> --datasets humaneval,mbpp` run would move them into (or out of) the top of the Auto tier.

| Model | In $/M | Out $/M | db_tps | Ctx | Arena | Reason | Score (provisional) |
|---|---:|---:|---:|---:|---:|:-:|---:|
| `minimax/minimax-m2.1` | 0.300 | 1.200 | 61 | 204k | 1430 | ✅ | 0.225 |
| `z-ai/glm-4.5-air` | 0.130 | 0.850 | 105 | 131k | 1410 | ✅ | 0.224 |
| `deepseek/deepseek-v3.2-exp` | 0.270 | 0.410 | 35 | 163k | 1431 | ✅ | 0.224 |
| `deepseek/deepseek-chat-v3.1` | 0.250 | 0.950 | 23 | 163k | 1430 | ✅ | 0.210 |
| `deepseek/deepseek-chat-v3-0324` | 0.270 | 1.120 | 27 | 163k | 1391 | — | 0.182 |
| `minimax/minimax-m2-her` | 0.300 | 1.200 | 87 | 65k | — | — | 0.172 |
| `deepseek/deepseek-r1-distill-llama-70b` | 0.800 | 0.800 | 45 | 8k | — | ✅ | 0.163 |
| `deepseek/deepseek-chat` | 0.200 | 0.800 | 42 | 163k | 1337 | — | 0.162 |
| `z-ai/glm-4.6v` | 0.300 | 0.900 | 33 | 131k | — | ✅ | 0.157 |
| `deepseek/deepseek-v3.1-terminus` | 0.270 | 1.000 | 24 | 163k | — | ✅ | 0.150 |
| `minimax/minimax-01` | 0.200 | 1.100 | 22 | 1000k | — | — | 0.148 |

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
