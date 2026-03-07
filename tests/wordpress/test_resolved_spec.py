"""
Tests for WordPress ResolvedSpec

Verifies immutability and hash computation.
"""

from __future__ import annotations

import dataclasses

import pytest

from fabrik.wordpress.resolved_spec import ResolvedSpec


def test_resolved_spec_is_immutable():
    """Test that ResolvedSpec and its data cannot be mutated."""
    original_data = {"domain": "test.com", "nested": {"key": "value"}}
    spec = ResolvedSpec(
        site_id="test.com",
        data=original_data,
    )

    # Cannot set attributes on frozen dataclass
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.site_id = "new.com"

    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.spec_hash = "new_hash"

    # Mutating original input data doesn't affect internal state
    original_data["domain"] = "hacked.com"
    original_data["nested"]["key"] = "hacked"

    assert spec.data["domain"] == "test.com"
    assert spec.data["nested"]["key"] == "value"

    # Mutating the returned data property doesn't affect internal state
    returned_data = spec.data
    returned_data["domain"] = "hacked2.com"
    returned_data["nested"]["key"] = "hacked2"

    assert spec.data["domain"] == "test.com"
    assert spec.data["nested"]["key"] == "value"

    # Verify that the hash hasn't changed
    original_hash = spec.spec_hash
    assert original_hash == spec._compute_hash()

