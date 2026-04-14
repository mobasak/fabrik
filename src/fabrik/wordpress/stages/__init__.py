"""
Stage runner infrastructure for WordPress deployment pipeline.

Each stage is a self-contained module that exports a single `apply()` function.
Stages are executed sequentially by SiteDeployer.
"""

import functools
import time
from dataclasses import dataclass, field


@dataclass
class StageResult:
    """Result of a stage execution."""

    name: str
    success: bool
    skipped: bool = False  # Reserved for Phase 2b
    warnings: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
    artifacts_written: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)  # For stage-specific data


def time_stage(func):
    """Decorator to time stage execution."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        duration_ms = (time.perf_counter() - start) * 1000
        result.duration_ms = duration_ms
        return result

    return wrapper
