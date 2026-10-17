"""The command-centre dashboard's page layer: escaped components, the string catalogue, and the one
stylesheet and one script under `static/` (plan 2026-10-17-plan-1, T01).

This package never imports `quota_dashboard` — that module runs as `__main__`, and a second import
would split its registries. It hands data in; the package hands markup back.
"""

# AFTER-EDIT: docs/workstation/quota-dashboard.md

from __future__ import annotations

from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent / "static"

__all__ = ["STATIC_DIR", "components", "strings"]
