# AFTER-EDIT: none
"""Register the `integration` pytest marker locally (plan-scope only).

The specialty-bench smoke suite in this directory is opt-in against real
provider APIs. We register the marker via a directory-local conftest rather
than editing the top-level pyproject.toml (a HARD-STOP deps file).
"""

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: real provider API — opt-in via `pytest -m integration`",
    )


def pytest_collection_modifyitems(config, items):
    """Auto-skip @pytest.mark.integration unless explicitly requested via `-m`.

    Prevents accidental paid API calls when the whole tests/ tree is collected
    (`pytest scripts/kilo-benchmarks/tests/`) — an operator has to say `-m
    integration` (or a matching selector) to opt in.
    """
    marker_expr = (config.getoption("-m", default="") or "").strip()
    if "integration" in marker_expr:
        return
    skip_int = pytest.mark.skip(reason="integration test — pass `-m integration` to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_int)
