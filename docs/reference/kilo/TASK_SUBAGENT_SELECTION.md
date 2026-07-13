Last refresh: 2026-07-13
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

### docs (n_total=46)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `minimax/minimax-m3` | 2.60 | 0.43 | $0.0276 | 2.67 | 2 | 14 |
| 2 | `deepseek/deepseek-v4-pro` | 2.54 | 0.36 | $0.1082 | 1.50 | 3 | 14 |
| 3 | `minimax/minimax-m2.5` | 3.31 | 0.33 | $0.0170 | 1.00 | 3 | 3 |
| 4 | `deepseek/deepseek-v3.2` | 3.14 | 0.75 | $0.0700 | 1.00 | 3 | 4 |

### plan (n_total=28)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `deepseek/deepseek-v4-pro` | 3.30 | 0.96 | $0.0161 | 3.05 | 3 | 28 |

### research (n_total=23)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `deepseek/deepseek-v4-pro` | 3.92 | 0.53 | $0.0085 | 3.88 | 3 | 15 |
| 2 | `minimax/minimax-m3` | 3.17 | 0.75 | $0.0087 | 4.00 | 2 | 8 |

### review (n_total=356)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `deepseek/deepseek-v3.2` | 3.13 | 0.86 | $0.0057 | 2.88 | 3 | 35 |
| 2 | `deepseek/deepseek-v4-pro` | 3.37 | 0.75 | $0.0164 | 3.31 | 3 | 104 |
| 3 | `minimax/minimax-m3` | 3.56 | 0.76 | $0.0182 | 3.61 | 2 | 189 |

### spec (n_total=155)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `z-ai/glm-5` | 4.47 | 1.00 | $0.0090 | 4.50 | 3 | 155 |

