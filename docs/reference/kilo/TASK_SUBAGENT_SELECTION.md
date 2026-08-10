Last refresh: 2026-08-10
Formula: shrunk_q = (n·avg_q + 10·tier_baseline) / (n+10); quality-gate at shrunk_q ≥ 2.5; then cost-asc among survivors; top-2 slots require n ≥ 10 | tier_baseline T1=1.0, T2=2.5, T3=4.0 | Window: 90 days | Min runs: 3



## ✅ Selected subagents — the gate shortlists (`pick_models` picks from these)

### Reviewers — 8 selected
_gate: precision ≥ 0.99 · $/1k ≤ 0.70 · $/run < 0.007 · score5 ≥ 3.5 · p50 ≤ 10s_
| model | grade | score5 | recall | $/1k | $/run | p50 s |
|---|:-:|--:|--:|--:|--:|--:|
| `claude-code/haiku` | A | 4.21 | 0.73 | $35.549 | $1.0665 | 16.5 |
| `qwen/qwen3-max` | A | 4.07 | 0.69 | $0.165 | $0.0033 | 1.9 |
| `claude-code/fable` | A | 4.05 | 0.68 | $448.486 | $13.4546 | 10.3 |
| `claude-code/opus` | A | 4.05 | 0.68 | $215.978 | $6.4794 | 8.0 |
| `claude-code/sonnet` | A | 4.05 | 0.68 | $160.349 | $4.8105 | 12.4 |
| `google/gemini-3-flash-preview` | A | 4.05 | 0.68 | $0.226 | $0.0068 | 1.3 |
| `deepseek/deepseek-v4-flash` | B+ | 3.71 | 0.59 | $0.207 | $0.0062 | 7.9 |
| `deepseek/deepseek-v3.2-exp` | B+ | 3.53 | 0.55 | $0.105 | $0.0032 | 2.1 |

### Coders — 6 selected (by tier)
_gate: n_err ≤ 1 · pass@1 ≥ 0.90 · $/1k ≤ 3.5 · p50 ≤ 10s_
**daily-driver:**
| model | grade | pass@1 | $/1k | $/run | p50 s |
|---|:-:|--:|--:|--:|--:|
| `google/gemini-3-flash-preview` | A+ | 1.000 | $1.180 | $0.0590 | 3.0 |
| `deepseek/deepseek-v3.2-exp` | A+ | 0.920 | $0.296 | $0.0148 | 6.2 |
| `qwen/qwen3-coder-next` | A+ | 0.900 | $0.830 | $0.0415 | 4.5 |
| `openai/gpt-5.4-mini` | A+ | 0.900 | $1.332 | $0.0666 | 1.8 |

**premium:**
| model | grade | pass@1 | $/1k | $/run | p50 s |
|---|:-:|--:|--:|--:|--:|
| `openai/gpt-5.6-luna` | A+ | 0.980 | $2.620 | $0.1310 | 3.8 |
| `writer/palmyra-x5` | A+ | 0.940 | $3.300 | $0.1650 | 7.6 |

### code (n_total=14)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `qwen/qwen3-coder-next` | 3.92 | 0.33 | $0.0369 | 2.00 | 1 | 3 |
| 2 | `google/gemini-3-flash-preview` | [benchmark] | — | — | — | 3 | 0 |
| 3 | `openai/gpt-5.6-luna` | [benchmark] | — | — | — | 2 | 0 |
| 4 | `writer/palmyra-x5` | [benchmark] | — | — | — | 2 | 0 |
| 5 | `deepseek/deepseek-v3.2-exp` | [benchmark] | — | — | — | 3 | 0 |
| 6 | `openai/gpt-5.4-mini` | [benchmark] | — | — | — | 2 | 0 |

### docs (n_total=120)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `minimax/minimax-m3` | 3.20 | 0.47 | $0.0210 | 3.40 | 2 | 36 |
| 2 | `deepseek/deepseek-v4-pro` | 3.05 | 0.46 | $0.0722 | 2.78 | 3 | 35 |
| 3 | `minimax/minimax-m2.5` | 3.53 | 0.33 | $0.0170 | 3.00 | 3 | 9 |
| 4 | `deepseek/deepseek-v4-flash` | 2.72 | 0.25 | $0.0274 | 3.00 | 2 | 8 |
| 5 | `deepseek/deepseek-v3.2` | 3.62 | 0.67 | $0.0584 | 3.00 | 3 | 6 |

### plan (n_total=32)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `deepseek/deepseek-v4-pro` | 3.21 | 0.91 | $0.0166 | 3.08 | 3 | 32 |

### research (n_total=234)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `z-ai/glm-4.5-air` | 2.64 | 0.52 | $0.0017 | 2.67 | 2 | 48 |
| 2 | `minimax/minimax-m3` | 2.56 | 0.54 | $0.0079 | 2.58 | 2 | 52 |
| 3 | `deepseek/deepseek-v4-pro` | 3.76 | 0.52 | $0.0091 | 3.74 | 3 | 128 |
| 4 | `deepseek/deepseek-v3.2` | 4.00 | 0.50 | $0.0035 | 4.00 | 3 | 6 |

### review (n_total=5086)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `deepseek/deepseek-v4-flash` | 3.00 | 0.39 | $0.0013 | 2.96 | 2 | 179 |
| 2 | `deepseek/deepseek-v3.2-exp` | 2.89 | 0.47 | $0.0013 | 2.86 | 3 | 255 |
| 3 | `google/gemini-3-flash-preview` | 3.09 | 0.50 | $0.0040 | 3.05 | 3 | 230 |
| 4 | `qwen/qwen3-max` | 2.77 | 0.47 | $0.0079 | 2.60 | 2 | 79 |

### spec (n_total=155)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `z-ai/glm-5` | 4.47 | 1.00 | $0.0090 | 4.50 | 3 | 155 |


## Full review benchmark results — all measured columns (display only; not parsed for routing)
_source: `microbench_review.py` → `model_review_metrics`. `eligible` = passes the reviewer gate (precision ≥ 0.99 · $/1k ≤ 0.70 · $/run < 0.007 · score5 ≥ 3.5 · p50 ≤ 10s). `score5` = F1(recall,precision)×5._
_⚠️ **`claude-code/*` review rows — RE-TEST IN PROGRESS (operator call, 2026-07-22).** The initial full-corpus runs of 2026-07-22 (opus · sonnet · haiku · fable, measured in 2-model batches) are considered **INVALID** and must not be used for comparison or routing judgement. Each tier is being re-measured **one model at a time** on the SAME unchanged 22-mutant corpus the OpenRouter models were scored on._

_**Re-test status** — ✅ `haiku` (2026-07-22): 4.054→**4.21**, recall 68%→**73%** (15→16 of 22 caught) · ✅ `sonnet` (2026-07-23): **4.05 unchanged**, recall 68% (15 of 22) — reproduced its batched score exactly · ✅ `fable` (2026-07-23): **4.05 unchanged**, recall 68% (15 of 22) — also reproduced exactly · ⏳ `opus` — still carrying its INVALID batched score, to be re-run on operator instruction (not scheduled; do not auto-run)._

_Why one-at-a-time: a single 22-item pass carries enough sampling variance to shift a tier by ~5pp of recall (haiku moved 5pp on an identical corpus; repeated-trial probing showed the same item flipping correct/incorrect across calls on identical input), so a batched run is not a sound basis for ranking. The corpus itself is UNCHANGED and remains byte-identical to the one all 57 OpenRouter models were measured against — those rows are unaffected and stay valid._

_**Resolution caveat (per-item probing, 2026-07-23):** of this corpus's 22 mutants, 15 are caught by every strong model and 6 by none — exactly 1 item discriminates at the frontier, so near-identical scores among top models here reflect the INSTRUMENT's ceiling, not equal capability. For separating frontier models use the HARD corpus (`microbench_review.py --hard` → its own table below): 10 hand-planted subtle logic bugs, kill-proven by differential tests, persisted separately and never touching this baseline or routing._
_`claude-code/*` rows: `$/1k` = ① API-equivalent (a list-price valuation of the subscription run's tokens, comparable to the pool — a RATE). `②total$` is a different unit: the REAL subscription-derived lump SUM for that row's whole measured run (expect it many orders of magnitude below `$/1k`, NOT a per-1k/per-run rate). Context — ② amortized ≈$0.005/M · ③ last run's weekly-quota draw ≈0.0% (from `claude_p_cost.json`; ③ is a capacity estimate, not a precise meter). A `claude-code/*` `✅` reflects the QUALITY floors only — the carve-out bypasses the printed cost/latency gate, and these tiers are **spawn-native (display-only, NOT pool-dispatched)**, so `pick_models` never returns them._
| model | grade | score5 | recall | prec | $/1k | $/M-out | $/run | ②total$ | p50 s | tok/s | n_mut | n_ctrl | eligible |
|---|:-:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|:-:|
| `openai/o3-mini` | A | 4.36 | 0.77 | 1.00 | $3.814 | $4.40 | $0.1144 | — | 3.4 | 204 | 22 | 8 | — |
| `anthropic/claude-haiku-4.5` | A | 4.21 | 0.73 | 1.00 | $1.867 | $5.00 | $0.0560 | — | 3.5 | 83 | 22 | 8 | — |
| `claude-code/haiku` | A | 4.21 | 0.73 | 1.00 | $35.549 | $5.00 | $1.0665 | $0.008118 | 16.5 | 60 | 22 | 8 | ✅ |
| `qwen/qwen3-max` | A | 4.07 | 0.69 | 1.00 | $0.165 | $3.90 | $0.0033 | — | 1.9 | 8 | 16 | 4 | ✅ |
| `bytedance-seed/seed-1.6` | A | 4.05 | 0.68 | 1.00 | $1.041 | $2.00 | $0.0312 | — | 6.5 | 48 | 22 | 8 | — |
| `bytedance-seed/seed-2.0-lite` | A | 4.05 | 0.68 | 1.00 | $1.335 | $2.00 | $0.0400 | — | 7.5 | 73 | 22 | 8 | — |
| `claude-code/fable` | A | 4.05 | 0.68 | 1.00 | $448.486 | $50.00 | $13.4546 | $0.009980 | 10.3 | 16 | 22 | 8 | ✅ |
| `claude-code/opus` | A | 4.05 | 0.68 | 1.00 | $215.978 | $25.00 | $6.4794 | $0.009704 | 8.0 | 17 | 22 | 8 | ✅ |
| `claude-code/sonnet` | A | 4.05 | 0.68 | 1.00 | $160.349 | $15.00 | $4.8105 | $0.015371 | 12.4 | 35 | 22 | 8 | ✅ |
| `google/gemini-3-flash-preview` | A | 4.05 | 0.68 | 1.00 | $0.226 | $3.00 | $0.0068 | — | 1.3 | 10 | 22 | 8 | ✅ |
| `moonshotai/kimi-k2.7-code` | A | 4.05 | 0.68 | 1.00 | $2.674 | $4.40 | $0.0802 | — | 5.0 | 87 | 22 | 8 | — |
| `openai/o4-mini-high` | A | 4.05 | 0.68 | 1.00 | $2.278 | $4.40 | $0.0683 | — | 5.1 | 78 | 22 | 8 | — |
| `qwen/qwen3.7-max` | A | 4.05 | 0.68 | 1.00 | $3.563 | $4.42 | $0.1069 | — | 11.5 | 50 | 22 | 8 | — |
| `x-ai/grok-4.5` | A | 4.05 | 0.68 | 1.00 | $3.363 | $6.00 | $0.1009 | — | 9.3 | 45 | 22 | 8 | — |
| `z-ai/glm-5.1` | A | 4.05 | 0.68 | 1.00 | $4.611 | $3.04 | $0.1383 | — | 17.8 | 51 | 22 | 8 | — |
| `z-ai/glm-5.2` | A | 4.05 | 0.68 | 1.00 | $0.643 | $0.92 | $0.0193 | — | 9.9 | 39 | 22 | 8 | — |
| `z-ai/glm-5v-turbo` | A | 4.05 | 0.68 | 1.00 | $6.899 | $4.00 | $0.2070 | — | 39.0 | 43 | 22 | 8 | — |
| `thinkingmachines/inkling` | A | 4.00 | 0.67 | 1.00 | $2.531 | $4.05 | $0.0734 | — | 5.8 | 65 | 21 | 8 | — |
| `poolside/laguna-m.1` | B+ | 3.97 | 0.73 | 0.88 | $0.458 | $0.40 | $0.0137 | — | 11.7 | 73 | 22 | 8 | — |
| `writer/palmyra-x5` | B+ | 3.91 | 0.64 | 1.00 | $0.512 | $6.00 | $0.0092 | — | 1.5 | 4 | 14 | 4 | — |
| `aion-labs/aion-3.0` | B+ | 3.89 | 0.64 | 1.00 | $5.758 | $6.00 | $0.1728 | — | 23.8 | 30 | 22 | 8 | — |
| `openai/gpt-5.6-luna` | B+ | 3.89 | 0.64 | 1.00 | $0.965 | $6.00 | $0.0289 | — | 2.7 | 34 | 22 | 8 | — |
| `openai/o3-mini-high` | B+ | 3.89 | 0.64 | 1.00 | $10.157 | $4.40 | $0.3047 | — | 5.7 | 241 | 22 | 8 | — |
| `qwen/qwen3.7-plus` | B+ | 3.89 | 0.64 | 1.00 | $1.183 | $1.28 | $0.0355 | — | 14.3 | 50 | 22 | 8 | — |
| `z-ai/glm-5-turbo` | B+ | 3.89 | 0.64 | 1.00 | $2.436 | $4.00 | $0.0731 | — | 29.9 | 18 | 22 | 8 | — |
| `nvidia/nemotron-3-ultra-550b-a55b` | B+ | 3.83 | 0.68 | 0.88 | $3.318 | $3.60 | $0.0995 | — | 14.7 | 78 | 22 | 8 | — |
| `openai/o4-mini` | B+ | 3.83 | 0.68 | 0.88 | $2.036 | $4.40 | $0.0611 | — | 4.9 | 77 | 22 | 8 | — |
| `bytedance-seed/seed-2.0-mini` | B+ | 3.71 | 0.59 | 1.00 | $0.935 | $0.40 | $0.0280 | — | 13.5 | 118 | 22 | 8 | — |
| `deepseek/deepseek-v4-flash` | B+ | 3.71 | 0.59 | 1.00 | $0.207 | $0.20 | $0.0062 | — | 7.9 | 61 | 22 | 8 | ✅ |
| `qwen/qwen3-max-thinking` | B+ | 3.71 | 0.59 | 1.00 | $0.327 | $3.90 | $0.0098 | — | 1.7 | 7 | 22 | 8 | — |
| `qwen/qwen3.5-flash-02-23` | B+ | 3.71 | 0.59 | 1.00 | $1.449 | $0.26 | $0.0435 | — | 36.2 | 151 | 22 | 8 | — |
| `xiaomi/mimo-v2.5-pro` | B+ | 3.71 | 0.59 | 1.00 | $2.284 | $0.87 | $0.0685 | — | 38.0 | 50 | 22 | 8 | — |
| `nvidia/nemotron-3-super-120b-a12b` | B+ | 3.68 | 0.64 | 0.88 | $0.175 | $0.46 | $0.0053 | — | 5.5 | 36 | 22 | 8 | — |
| `deepseek/deepseek-v3.2-exp` | B+ | 3.53 | 0.55 | 1.00 | $0.105 | $0.41 | $0.0032 | — | 2.1 | 6 | 22 | 8 | ✅ |
| `minimax/minimax-m3` | B+ | 3.53 | 0.55 | 1.00 | $1.050 | $1.20 | $0.0315 | — | 9.3 | 78 | 22 | 8 | — |
| `openai/gpt-5.1-codex-mini` | B+ | 3.53 | 0.55 | 1.00 | $0.343 | $2.00 | $0.0103 | — | 1.7 | 54 | 22 | 8 | — |
| `openai/gpt-5.6-luna-pro` | B+ | 3.53 | 0.55 | 1.00 | $6.139 | $6.00 | $0.1842 | — | 5.0 | 95 | 22 | 8 | — |
| `nvidia/nemotron-3-nano-30b-a3b` | B | 3.44 | 0.64 | 0.75 | $0.192 | $0.20 | $0.0058 | — | 7.1 | 111 | 22 | 8 | — |
| `moonshotai/kimi-k2.5` | B | 3.33 | 0.50 | 1.00 | $6.671 | $2.85 | $0.2001 | — | 48.5 | 49 | 22 | 8 | — |
| `xiaomi/mimo-v2.5` | B | 3.33 | 0.50 | 1.00 | $0.367 | $0.28 | $0.0110 | — | 19.1 | 45 | 22 | 8 | — |
| `deepseek/deepseek-v3.2` | B | 3.31 | 0.59 | 0.75 | $0.067 | $0.40 | $0.0020 | — | 1.5 | 28 | 22 | 8 | — |
| `minimax/minimax-m2.7` | B | 3.18 | 0.50 | 0.88 | $1.716 | $1.00 | $0.0515 | — | 22.8 | 53 | 22 | 8 | — |
| `bytedance-seed/seed-1.6-flash` | B | 3.16 | 0.55 | 0.75 | $0.387 | $0.30 | $0.0116 | — | 7.0 | 144 | 22 | 8 | — |
| `deepseek/deepseek-r1-distill-llama-70b` | B | 3.12 | 0.45 | 1.00 | $1.950 | $0.80 | $0.0585 | — | 106.2 | 22 | 22 | 8 | — |
| `tencent/hy3-preview` | C+ | 2.99 | 0.45 | 0.88 | $0.557 | $0.21 | $0.0167 | — | 18.4 | 110 | 22 | 8 | — |
| `minimax/minimax-m2.5` | C+ | 2.90 | 0.41 | 1.00 | $1.019 | $0.90 | $0.0306 | — | 9.9 | 74 | 22 | 8 | — |
| `openai/gpt-5.4-mini` | C+ | 2.90 | 0.41 | 1.00 | $0.376 | $4.50 | $0.0113 | — | 1.0 | 20 | 22 | 8 | — |
| `poolside/laguna-xs-2.1` | C+ | 2.88 | 0.68 | 0.50 | $0.161 | $0.12 | $0.0048 | — | 14.6 | 84 | 22 | 8 | — |
| `amazon/nova-pro-v1` | C+ | 2.80 | 0.64 | 0.50 | $0.562 | $3.20 | $0.0169 | — | 1.2 | 61 | 22 | 8 | — |
| `deepseek/deepseek-v4-pro` | C+ | 2.67 | 0.36 | 1.00 | $0.700 | $0.87 | $0.0210 | — | 2.8 | 30 | 22 | 8 | — |
| `qwen/qwen3-coder-next` | C+ | 2.67 | 0.36 | 1.00 | $0.035 | $0.80 | $0.0010 | — | 0.8 | 12 | 22 | 8 | — |
| `moonshotai/kimi-k2.6` | C | 2.41 | 0.32 | 1.00 | $7.787 | $4.00 | $0.2336 | — | 20.0 | 86 | 22 | 8 | — |
| `nousresearch/hermes-4-405b` | C | 2.41 | 0.32 | 1.00 | $0.536 | $3.00 | $0.0161 | — | 2.7 | 14 | 22 | 8 | — |
| `z-ai/glm-4.7-flash` | C | 2.41 | 0.32 | 1.00 | $0.942 | $0.40 | $0.0283 | — | 37.6 | 62 | 22 | 8 | — |
| `tencent/hy3` | C | 2.40 | 0.32 | 1.00 | $0.048 | $0.80 | $0.0011 | — | 3.1 | 5 | 19 | 4 | — |
| `qwen/qwen3-coder-plus` | C | 2.29 | 0.59 | 0.38 | $0.316 | $3.25 | $0.0095 | — | 2.5 | 14 | 22 | 8 | — |
| `stepfun/step-3.7-flash` | C | 2.14 | 0.27 | 1.00 | $2.689 | $1.15 | $0.0807 | — | 17.9 | 132 | 22 | 8 | — |
| `z-ai/glm-5` | C | 2.14 | 0.27 | 1.00 | $5.589 | $3.15 | $0.1677 | — | 57.9 | 34 | 22 | 8 | — |
| `z-ai/glm-4.5-air` | D | 1.85 | 0.23 | 1.00 | $1.485 | $0.85 | $0.0446 | — | 36.0 | 56 | 22 | 8 | — |
| `stepfun/step-3.5-flash` | D | 1.54 | 0.18 | 1.00 | $0.751 | $0.30 | $0.0225 | — | 48.7 | 51 | 22 | 8 | — |
| `qwen/qwen3-coder-flash` | F | 0.00 | 0.77 | 0.00 | $0.072 | $0.97 | $0.0022 | — | 1.4 | 24 | 22 | 8 | — |

## HARD review benchmark — hand-planted subtle logic bugs (diagnostic only; NOT comparable with the table above, never parsed for routing)
_source: `microbench_review.py --hard` → `model_review_hard_metrics`. 10 hand-planted single-line logic bugs in realistic functions (stateful traces, stdlib semantics, contract-vs-code, placement bugs — every bug kill-proven by differential execution, every ground truth derived from a docstring contract) + 10 clean controls. Built to separate frontier models the operator-flip corpus ties. No eligibility gate — this table ranks, it does not route._
_`claude-code/*` rows: `$/1k` = ① API-equivalent (a list-price valuation of the subscription run's tokens, comparable to the pool — a RATE). `②total$` is a different unit: the REAL subscription-derived lump SUM for that row's whole measured run (expect it many orders of magnitude below `$/1k`, NOT a per-1k/per-run rate). Context — ② amortized ≈$0.005/M · ③ last run's weekly-quota draw ≈0.0% (from `claude_p_cost.json`; ③ is a capacity estimate, not a precise meter). A `claude-code/*` `✅` reflects the QUALITY floors only — the carve-out bypasses the printed cost/latency gate, and these tiers are **spawn-native (display-only, NOT pool-dispatched)**, so `pick_models` never returns them._
| model | grade | score5 | recall | prec | $/1k | $/M-out | $/run | ②total$ | p50 s | tok/s | n_mut | n_ctrl |
|---|:-:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| `claude-code/haiku` | A+ | 5.00 | 1.00 | 1.00 | $41.500 | $5.00 | $0.8300 | $0.006101 | 25.2 | 60 | 10 | 10 |
| `claude-code/sonnet` | A+ | 5.00 | 1.00 | 1.00 | $166.464 | $15.00 | $3.3293 | $0.008998 | 16.3 | 28 | 10 | 10 |
| `claude-code/fable` | A+ | 4.74 | 0.90 | 1.00 | $494.925 | $50.00 | $9.8985 | $0.007139 | 12.1 | 15 | 10 | 10 |
| `claude-code/opus` | A | 4.44 | 0.80 | 1.00 | $237.073 | $25.00 | $4.7415 | $0.006946 | 13.8 | 10 | 10 | 10 |

## Full coding benchmark results — LiveCodeBench pass@1 (display only; not parsed for routing)
_source: `microbench_coding_direct.py` → `model_coding_metrics` (contamination-free LiveCodeBench). `pass@1` = fraction solved · `score5` = pass@1×5 · `value` = score5÷$/1k · `eligible` = clears the code gate (n_err ≤ 1 · pass@1 ≥ 0.90 · $/1k ≤ 3.5 · p50 ≤ 10s) · `tier` = curated use-case._
_`claude-code/*` rows: `$/1k` = ① API-equivalent (a list-price valuation of the subscription run's tokens, comparable to the pool — a RATE). (no per-row ② column here — this harness doesn't persist raw tokens per run.) Context — ② amortized ≈$0.005/M · ③ last run's weekly-quota draw ≈0.0% (from `claude_p_cost.json`; ③ is a capacity estimate, not a precise meter). A `claude-code/*` `✅` reflects the QUALITY floors only — the carve-out bypasses the printed cost/latency gate, and these tiers are **spawn-native (display-only, NOT pool-dispatched)**, so `pick_models` never returns them._
| model | grade | pass@1 | score5 | $/1k | $/run | p50 s | tok/s | value | family | n_graded | n_err | eligible | tier |
|---|:-:|--:|--:|--:|--:|--:|--:|--:|:-:|--:|--:|:-:|:-:|
| `google/gemini-3-flash-preview` | A+ | 1.000 | 5.00 | $1.180 | $0.0590 | 3.0 | 102 | 4.2 | google | 50 | 0 | ✅ | daily-driver |
| `poolside/laguna-m.1` | A+ | 1.000 | 5.00 | $3.757 | $0.0263 | 220.2 | 46 | 1.3 | poolside | 7 | 43 | — | — |
| `bytedance-seed/seed-2.0-lite` | A+ | 1.000 | 5.00 | $7.196 | $0.3598 | 39.7 | 82 | 0.7 | bytedance-seed | 50 | 0 | — | — |
| `openai/gpt-5.6-luna` | A+ | 0.980 | 4.90 | $2.620 | $0.1310 | 3.8 | 33 | 1.9 | openai | 50 | 0 | ✅ | premium |
| `qwen/qwen3.5-flash-02-23` | A+ | 0.980 | 4.90 | $5.838 | $0.2919 | 114.1 | 167 | 0.8 | qwen | 50 | 0 | — | — |
| `bytedance-seed/seed-1.6` | A+ | 0.980 | 4.90 | $7.354 | $0.3677 | 50.4 | 55 | 0.7 | bytedance-seed | 50 | 0 | — | — |
| `moonshotai/kimi-k2.7-code` | A+ | 0.980 | 4.90 | $9.876 | $0.4938 | 18.2 | 50 | 0.5 | moonshotai | 50 | 0 | — | — |
| `qwen/qwen3.7-max` | A+ | 0.980 | 4.90 | $11.326 | $0.5663 | 35.6 | 54 | 0.4 | qwen | 50 | 0 | — | — |
| `x-ai/grok-4.5` | A+ | 0.980 | 4.90 | $11.818 | $0.5909 | 14.3 | 54 | 0.4 | x-ai | 50 | 0 | — | — |
| `openai/gpt-5.6-luna-pro` | A+ | 0.980 | 4.90 | $12.558 | $0.6279 | 6.7 | 118 | 0.4 | openai | 50 | 0 | — | — |
| `xiaomi/mimo-v2.5-pro` | A+ | 0.979 | 4.90 | $3.358 | $0.1612 | 41.5 | 39 | 1.5 | xiaomi | 48 | 2 | — | — |
| `moonshotai/kimi-k2.5` | A+ | 0.979 | 4.89 | $16.898 | $0.7942 | 94.3 | 30 | 0.3 | moonshotai | 47 | 3 | — | — |
| `moonshotai/kimi-k2.6` | A+ | 0.978 | 4.89 | $20.967 | $0.9645 | 113.1 | 40 | 0.2 | moonshotai | 46 | 4 | — | — |
| `z-ai/glm-5-turbo` | A+ | 0.977 | 4.89 | $15.809 | $0.6956 | 136.0 | 14 | 0.3 | z-ai | 44 | 6 | — | — |
| `z-ai/glm-5.1` | A+ | 0.977 | 4.88 | $12.012 | $0.5165 | 36.3 | 41 | 0.4 | z-ai | 43 | 7 | — | — |
| `qwen/qwen3.7-plus` | A+ | 0.960 | 4.80 | $3.612 | $0.1806 | 31.8 | 54 | 1.3 | qwen | 50 | 0 | — | — |
| `z-ai/glm-5.2` | A+ | 0.957 | 4.79 | $3.094 | $0.1454 | 26.5 | 36 | 1.5 | z-ai | 47 | 3 | — | — |
| `nvidia/nemotron-3-ultra-550b-a55b` | A+ | 0.956 | 4.78 | $10.887 | $0.4899 | 18.1 | 123 | 0.4 | nvidia | 45 | 5 | — | — |
| `z-ai/glm-4.7-flash` | A+ | 0.950 | 4.75 | $2.058 | $0.0823 | 78.1 | 47 | 2.3 | z-ai | 40 | 10 | — | — |
| `thinkingmachines/inkling` | A+ | 0.950 | 4.75 | $15.695 | $0.6278 | 49.4 | 42 | 0.3 | thinkingmachines | 40 | 10 | — | — |
| `writer/palmyra-x5` | A+ | 0.940 | 4.70 | $3.300 | $0.1650 | 7.6 | 22 | 1.4 | writer | 50 | 0 | ✅ | premium |
| `deepseek/deepseek-v4-flash` | A+ | 0.939 | 4.69 | $1.084 | $0.0531 | 17.3 | 58 | 4.3 | deepseek | 49 | 1 | — | — |
| `openai/gpt-5.1-codex-mini` | A+ | 0.939 | 4.69 | $4.667 | $0.2287 | 7.6 | 59 | 1.0 | openai | 49 | 1 | — | — |
| `openai/o4-mini-high` | A+ | 0.939 | 4.69 | $16.412 | $0.8042 | 21.9 | 82 | 0.3 | openai | 49 | 1 | — | — |
| `poolside/laguna-xs-2.1` | A+ | 0.935 | 4.67 | $0.804 | $0.0370 | 75.4 | 92 | 5.8 | poolside | 46 | 4 | — | — |
| `nvidia/nemotron-3-super-120b-a12b` | A+ | 0.933 | 4.67 | $2.162 | $0.0973 | 40.9 | 36 | 2.2 | nvidia | 45 | 5 | — | — |
| `qwen/qwen3-max` | A+ | 0.930 | 4.65 | $2.909 | $0.1251 | 4.7 | 57 | 1.6 | qwen | 43 | 7 | — | — |
| `stepfun/step-3.5-flash` | A+ | 0.923 | 4.62 | $1.615 | $0.0630 | 65.6 | 44 | 2.9 | stepfun | 39 | 11 | — | — |
| `stepfun/step-3.7-flash` | A+ | 0.921 | 4.61 | $5.500 | $0.2090 | 25.7 | 124 | 0.8 | stepfun | 38 | 12 | — | — |
| `deepseek/deepseek-v3.2-exp` | A+ | 0.920 | 4.60 | $0.296 | $0.0148 | 6.2 | 34 | 15.5 | deepseek | 50 | 0 | ✅ | daily-driver |
| `deepseek/deepseek-v4-pro` | A+ | 0.920 | 4.60 | $13.936 | $0.6968 | 19.7 | 46 | 0.3 | deepseek | 50 | 0 | — | — |
| `xiaomi/mimo-v2.5` | A+ | 0.918 | 4.59 | $1.137 | $0.0557 | 105.7 | 28 | 4.0 | xiaomi | 49 | 1 | — | — |
| `openai/o3-mini-high` | A+ | 0.911 | 4.56 | $42.278 | $1.9025 | 25.1 | 180 | 0.1 | openai | 45 | 5 | — | — |
| `tencent/hy3-preview` | A+ | 0.907 | 4.54 | $1.184 | $0.0509 | 37.8 | 56 | 3.8 | tencent | 43 | 7 | — | — |
| `qwen/qwen3-coder-next` | A+ | 0.900 | 4.50 | $0.830 | $0.0415 | 4.5 | 109 | 5.4 | qwen | 50 | 0 | ✅ | daily-driver |
| `openai/gpt-5.4-mini` | A+ | 0.900 | 4.50 | $1.332 | $0.0666 | 1.8 | 94 | 3.4 | openai | 50 | 0 | ✅ | daily-driver |
| `bytedance-seed/seed-2.0-mini` | A+ | 0.900 | 4.50 | $2.354 | $0.1177 | 34.6 | 129 | 1.9 | bytedance-seed | 50 | 0 | — | — |
| `z-ai/glm-5` | A | 0.897 | 4.49 | $11.372 | $0.4435 | 106.3 | 23 | 0.4 | z-ai | 39 | 11 | — | — |
| `qwen/qwen3-coder-plus` | A | 0.880 | 4.40 | $2.220 | $0.1110 | 6.3 | 47 | 2.0 | qwen | 50 | 0 | — | — |
| `qwen/qwen3-max-thinking` | A | 0.880 | 4.40 | $2.898 | $0.1449 | 4.5 | 60 | 1.5 | qwen | 50 | 0 | — | — |
| `openai/o4-mini` | A | 0.880 | 4.40 | $8.986 | $0.4493 | 12.0 | 89 | 0.5 | openai | 50 | 0 | — | — |
| `aion-labs/aion-3.0` | A | 0.880 | 4.40 | $18.918 | $0.9459 | 84.4 | 35 | 0.2 | aion-labs | 50 | 0 | — | — |
| `bytedance-seed/seed-1.6-flash` | A | 0.840 | 4.20 | $2.142 | $0.1071 | 30.0 | 169 | 2.0 | bytedance-seed | 50 | 0 | — | — |
| `minimax/minimax-m2.7` | A | 0.837 | 4.19 | $5.430 | $0.2335 | 94.9 | 30 | 0.8 | minimax | 43 | 7 | — | — |
| `deepseek/deepseek-r1-distill-llama-70b` | A | 0.828 | 4.14 | $3.228 | $0.0936 | 183.4 | 21 | 1.3 | deepseek | 29 | 21 | — | — |
| `openai/o3-mini` | A | 0.816 | 4.08 | $18.698 | $0.9162 | 9.7 | 188 | 0.2 | openai | 49 | 1 | — | — |
| `minimax/minimax-m2.5` | A | 0.808 | 4.04 | $5.772 | $0.2713 | 61.2 | 48 | 0.7 | minimax | 47 | 3 | — | — |
| `z-ai/glm-4.5-air` | A | 0.804 | 4.02 | $4.050 | $0.1863 | 46.7 | 38 | 1.0 | z-ai | 46 | 4 | — | — |
| `deepseek/deepseek-v3.2` | B+ | 0.780 | 3.90 | $0.340 | $0.0170 | 6.3 | 34 | 11.5 | deepseek | 50 | 0 | — | — |
| `z-ai/glm-5v-turbo` | B+ | 0.760 | 3.80 | $14.448 | $0.7224 | 65.7 | 40 | 0.3 | z-ai | 50 | 0 | — | — |
| `qwen/qwen3-coder-flash` | B+ | 0.740 | 3.70 | $0.788 | $0.0394 | 4.2 | 95 | 4.7 | qwen | 50 | 0 | — | — |
| `tencent/hy3` | B+ | 0.700 | 3.50 | $0.234 | $0.0117 | 5.0 | 47 | 15.0 | tencent | 50 | 0 | — | — |
| `anthropic/claude-haiku-4.5` | B+ | 0.700 | 3.50 | $5.078 | $0.2539 | 5.9 | 154 | 0.7 | anthropic | 50 | 0 | — | — |
| `minimax/minimax-m3` | B | 0.674 | 3.37 | $4.026 | $0.1852 | 25.3 | 55 | 0.8 | minimax | 46 | 4 | — | — |
| `nvidia/nemotron-3-nano-30b-a3b` | B | 0.667 | 3.33 | $0.789 | $0.0284 | 25.8 | 90 | 4.2 | nvidia | 36 | 14 | — | — |
| `nousresearch/hermes-4-405b` | C+ | 0.540 | 2.70 | $3.558 | $0.1779 | 8.6 | 14 | 0.8 | nousresearch | 50 | 0 | — | — |
| `amazon/nova-pro-v1` | C | 0.440 | 2.20 | $0.980 | $0.0490 | 1.5 | 108 | 2.2 | amazon | 50 | 0 | — | — |
