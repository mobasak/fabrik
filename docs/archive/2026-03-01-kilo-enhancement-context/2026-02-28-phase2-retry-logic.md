Phase 2 Step 1: Add retry logic with exponential backoff to kilo_code_review.py

Added:
- MAX_RETRIES env var (default 3)
- RETRYABLE_EXIT_CODES (124 timeout, 503 service unavailable)
- Wrapped run_kilo_review subprocess calls in retry loop
- On retryable failures: exponential backoff (1s, 2s, 4s), informative logging
- Handles subprocess.TimeoutExpired and TimeoutError
- After MAX_RETRIES, raises with attempt count
