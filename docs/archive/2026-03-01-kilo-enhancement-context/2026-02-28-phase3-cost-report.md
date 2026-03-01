Phase 3 Step 2: Create kilo_cost_report.py utility

Created utility script to analyze Kilo usage and costs:

FEATURES:
- Load and parse .droid/kilo_usage.jsonl (usage tracking)
- Load and parse .droid/kilo_metrics.jsonl (performance metrics)
- Generate cost summary (total runs, cost, tokens, avg cost per run)
- Breakdown by model (runs, cost, tokens per model)
- Breakdown by file type (reviews, avg iterations, cost, pass rate)
- Output formats: text (human-readable tables) and JSON

CLI OPTIONS:
- --usage-log: Path to usage log (default: .droid/kilo_usage.jsonl)
- --metrics: Path to metrics file (default: .droid/kilo_metrics.jsonl)
- --format: text or json (default: text)
- --by-model: Show model breakdown
- --by-filetype: Show file type breakdown

USAGE EXAMPLES:
```bash
# Basic cost summary
python scripts/kilo_cost_report.py

# JSON output with all breakdowns
python scripts/kilo_cost_report.py --format json

# Show file type performance
python scripts/kilo_cost_report.py --by-filetype
```

BENEFITS:
- Visibility into Kilo spending
- Identify expensive models/file types
- Optimize model selection based on data
- Budget forecasting
