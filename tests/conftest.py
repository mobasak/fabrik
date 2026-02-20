"""Pytest configuration and Hypothesis profiles."""

import os
from datetime import timedelta

from hypothesis import Phase, settings

settings.register_profile(
    "ci",
    max_examples=100,
    deadline=None,
    phases=[Phase.generate, Phase.target, Phase.shrink],
)

settings.register_profile(
    "dev",
    max_examples=10,
    deadline=timedelta(milliseconds=5000),
)

settings.register_profile(
    "thorough",
    max_examples=1000,
    deadline=None,
)

settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
