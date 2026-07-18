Last refresh: 2026-07-18
Formula: shrunk_q = (n·avg_q + 10·tier_baseline) / (n+10); quality-gate at shrunk_q ≥ 2.5; then cost-asc among survivors; top-2 slots require n ≥ 10 | tier_baseline T1=1.0, T2=2.5, T3=4.0 | Window: 90 days | Min runs: 3


### code (n_total=4)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `deepseek/deepseek-v4-flash` | 3.19 | 0.75 | $0.0627 | 4.90 | 2 | 4 |
| 2 | `minimax/minimax-m2.5` | [benchmark] | — | — | — | 3 | 0 |
| 3 | `deepseek/deepseek-v3.2` | [benchmark] | — | — | — | 3 | 0 |
| 4 | `bytedance-seed/seed-2.0-mini` | [benchmark] | — | — | — | 3 | 0 |
| 5 | `bytedance-seed/seed-1.6-flash` | [benchmark] | — | — | — | 3 | 0 |
| 6 | `qwen/qwen3-coder-30b-a3b-instruct` | [benchmark] | — | — | — | 3 | 0 |
| 7 | `qwen/qwen3-coder-flash` | [benchmark] | — | — | — | 3 | 0 |
| 8 | `minimax/minimax-m2` | [benchmark] | — | — | — | 3 | 0 |
| 9 | `minimax/minimax-m3` | [benchmark] | — | — | — | 2 | 0 |
| 10 | `z-ai/glm-4.7-flash` | [benchmark] | — | — | — | 3 | 0 |

### docs (n_total=87)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `z-ai/glm-4.5-air` | 2.79 | 0.43 | $0.0116 | 3.00 | 2 | 14 |
| 2 | `minimax/minimax-m3` | 3.06 | 0.52 | $0.0209 | 3.25 | 2 | 29 |
| 3 | `deepseek/deepseek-v4-pro` | 3.04 | 0.48 | $0.0697 | 2.71 | 3 | 29 |
| 4 | `minimax/minimax-m2.5` | 3.31 | 0.33 | $0.0170 | 1.00 | 3 | 3 |
| 5 | `deepseek/deepseek-v4-flash` | 2.69 | 0.33 | $0.0282 | 3.00 | 2 | 6 |
| 6 | `deepseek/deepseek-v3.2` | 3.62 | 0.67 | $0.0584 | 3.00 | 3 | 6 |

### plan (n_total=28)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `deepseek/deepseek-v4-pro` | 3.30 | 0.96 | $0.0161 | 3.05 | 3 | 28 |

### research (n_total=115)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `minimax/minimax-m3` | 2.66 | 0.64 | $0.0061 | 2.78 | 2 | 14 |
| 2 | `deepseek/deepseek-v4-pro` | 3.88 | 0.53 | $0.0070 | 3.87 | 3 | 98 |

### review (n_total=4459)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `tencent/hy3` | 2.64 | 0.38 | $0.0001 | 2.67 | 2 | 80 |
| 2 | `deepseek/deepseek-v3.2-exp` | 2.90 | 0.33 | $0.0001 | 2.83 | 3 | 90 |
| 3 | `google/gemini-3-flash-preview` | 3.71 | 0.33 | $0.0002 | 3.67 | 3 | 90 |
| 4 | `openai/gpt-5.1-codex-mini` | 3.50 | 0.33 | $0.0004 | 3.50 | 2 | 90 |
| 5 | `deepseek/deepseek-v4-flash` | 3.16 | 0.06 | $0.0005 | 3.07 | 2 | 67 |
| 6 | `z-ai/glm-5.2` | 3.85 | 0.34 | $0.0006 | 3.82 | 3 | 91 |
| 7 | `deepseek/deepseek-v4-pro` | 3.48 | 0.62 | $0.0137 | 3.50 | 3 | 379 |
| 8 | `qwen/qwen3-max` | [benchmark] | — | — | — | 2 | 0 |
| 9 | `writer/palmyra-x5` | [benchmark] | — | — | — | 2 | 0 |
| 10 | `qwen/qwen3-max-thinking` | [benchmark] | — | — | — | 1 | 0 |
| 11 | `openai/gpt-5.4-mini` | [benchmark] | — | — | — | 2 | 0 |
| 12 | `qwen/qwen3-coder-next` | [benchmark] | — | — | — | 1 | 0 |
| 13 | `nousresearch/hermes-4-405b` | [benchmark] | — | — | — | 1 | 0 |

### spec (n_total=155)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `z-ai/glm-5` | 4.47 | 1.00 | $0.0090 | 4.50 | 3 | 155 |

