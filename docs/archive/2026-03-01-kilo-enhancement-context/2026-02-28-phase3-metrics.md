Phase 3 Step 1: Add model performance metrics to kilo_code_review.py

Added:
- ModelMetrics dataclass to track performance per model/file_type
- Properties: avg_iterations, avg_cost, pass_rate
- save_model_metrics() function writes to .droid/kilo_metrics.jsonl
- load_model_metrics() function reads with optional filtering
- Automatic metrics tracking at end of review_files()
- METRICS_FILE constant for file path configuration

Benefits:
- Track which models perform best for different file types
- Analyze iteration counts, costs, and pass rates
- Data-driven model selection optimization
- Historical performance tracking for cost analysis
