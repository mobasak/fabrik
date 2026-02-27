"""Property-based tests using Hypothesis."""

from hypothesis import given
from hypothesis import strategies as st
from src.fabrik.scaffold import _get_package_name


class TestGetPackageName:
    """Property tests for _get_package_name."""

    @given(st.text(min_size=0, max_size=100))
    def test_get_package_name_replaces_hyphens(self, name: str) -> None:
        """Property: hyphens are replaced with underscores, length preserved."""
        result = _get_package_name(name)

        assert result == name.replace("-", "_")
        assert len(result) == len(name)
        assert "-" not in result
