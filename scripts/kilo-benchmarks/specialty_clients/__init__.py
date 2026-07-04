"""Specialty-service bench clients — one bench_one() function per provider.

Plan 2026-07-03-plan-1-full-speed-coverage-close.md Phase B.3.

Contract:
    bench_one(model_id: str, api_key: str) -> dict
        Returns {"perf_seconds": float|None, "cost_usd": float, "error": str|None}
        On success: perf_seconds > 0, error is None.
        On failure: perf_seconds is None, error is a short string.
"""
