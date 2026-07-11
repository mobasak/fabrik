Last refresh: 2026-07-11
Formula: shrunk_q = (n·avg_q + 10·tier_baseline) / (n+10); quality-gate at shrunk_q ≥ 2.5; then cost-asc among survivors; top-2 slots require n ≥ 10 | tier_baseline T1=1.0, T2=2.5, T3=4.0 | Window: 90 days | Min runs: 3


### code (n_total=3)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `deepseek/deepseek-v4-flash` | 3.03 | 0.67 | $0.0836 | 4.80 | 2 | 3 |

### docs (n_total=5)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `minimax/minimax-m3` | 2.56 | 1.00 | $0.0027 | 2.67 | 2 | 5 |

### plan (n_total=28)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `deepseek/deepseek-v4-pro` | 3.30 | 0.96 | $0.0161 | 3.05 | 3 | 28 |

### research (n_total=7)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `minimax/minimax-m3` | 3.07 | 1.00 | $0.0129 | 4.50 | 2 | 4 |
| 2 | `deepseek/deepseek-v4-pro` | 4.12 | 0.67 | $0.0132 | 4.50 | 3 | 3 |

### review (n_total=309)
| rank | model | shrunk_q | success | avg_cost | avg_quality | quality_tier | n |
|---:|---|---:|---:|---:|---:|:-:|---:|
| 1 | `deepseek/deepseek-v3.2` | 3.14 | 0.85 | $0.0060 | 2.88 | 3 | 33 |
| 2 | `deepseek/deepseek-v4-pro` | 3.49 | 0.79 | $0.0150 | 3.42 | 3 | 84 |
| 3 | `minimax/minimax-m3` | 3.61 | 0.77 | $0.0163 | 3.67 | 2 | 173 |

