"""Tests for plugins stage."""

from fabrik.wordpress.stages import plugins


def test_plugins_no_op(minimal_spec, mock_wp, mock_api, tmp_path):
    """Test plugins stage is a no-op."""
    result = plugins.apply(minimal_spec, mock_wp, mock_api, tmp_path)

    assert result.success
    assert result.name == "plugins"
