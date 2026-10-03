# AFTER-EDIT: none
"""Fabrik Convention Enforcement Scripts.

Shared validation layer called by scripts/final_gate.py (which the Claude Code Stop hook runs)
and by pre-commit checks.

Exit codes:
    0 = pass (all checks passed)
    1 = warn (issues found but non-blocking)
    2 = block (critical violation, stop action)
"""

from .validate_conventions import main, run_all_checks

__all__ = ["main", "run_all_checks"]
