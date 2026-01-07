"""Tests for secrets management."""

import os
from unittest.mock import patch

from fabrik.orchestrator.secrets import (
    SecretsManager,
    generate_secret,
    load_dotenv,
)


class TestGenerateSecret:
    """Test secret generation."""

    def test_default_length(self):
        """Generated secret should be 32 characters by default."""
        secret = generate_secret()
        assert len(secret) == 32

    def test_custom_length(self):
        """Can generate secrets of custom length."""
        secret = generate_secret(length=64)
        assert len(secret) == 64

    def test_alphanumeric_only(self):
        """Generated secrets should only contain alphanumeric characters."""
        secret = generate_secret()
        assert secret.isalnum()

    def test_uniqueness(self):
        """Generated secrets should be unique."""
        secrets = [generate_secret() for _ in range(100)]
        assert len(set(secrets)) == 100


class TestLoadDotenv:
    """Test .env file loading."""

    def test_load_simple_env(self, tmp_path):
        """Load simple key=value pairs."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=value1\nKEY2=value2\n")

        result = load_dotenv(env_file)
        assert result == {"KEY1": "value1", "KEY2": "value2"}

    def test_skip_comments(self, tmp_path):
        """Skip comment lines."""
        env_file = tmp_path / ".env"
        env_file.write_text("# This is a comment\nKEY=value\n")

        result = load_dotenv(env_file)
        assert result == {"KEY": "value"}

    def test_skip_empty_lines(self, tmp_path):
        """Skip empty lines."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=value1\n\n\nKEY2=value2\n")

        result = load_dotenv(env_file)
        assert result == {"KEY1": "value1", "KEY2": "value2"}

    def test_strip_quotes(self, tmp_path):
        """Strip quotes from values."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=\"quoted\"\nKEY2='single'\n")

        result = load_dotenv(env_file)
        assert result == {"KEY1": "quoted", "KEY2": "single"}

    def test_missing_file(self, tmp_path):
        """Return empty dict for missing file."""
        env_file = tmp_path / ".env"
        result = load_dotenv(env_file)
        assert result == {}


class TestSecretsManager:
    """Test SecretsManager class."""

    def test_env_takes_priority(self, tmp_path):
        """Environment variables take priority over .env."""
        env_file = tmp_path / ".env"
        env_file.write_text("MY_SECRET=from_dotenv\n")

        with patch.dict(os.environ, {"MY_SECRET": "from_env"}):
            manager = SecretsManager(project_dir=tmp_path)
            value = manager.get("MY_SECRET")
            assert value == "from_env"

    def test_dotenv_fallback(self, tmp_path):
        """Falls back to .env if not in environment."""
        env_file = tmp_path / ".env"
        env_file.write_text("MY_SECRET=from_dotenv\n")

        # Ensure not in environment
        with patch.dict(os.environ, {}, clear=True):
            manager = SecretsManager(project_dir=tmp_path)
            value = manager.get("MY_SECRET")
            assert value == "from_dotenv"

    def test_generate_if_missing(self, tmp_path):
        """Generates secret if not found and generate_if_missing=True."""
        manager = SecretsManager(project_dir=tmp_path)

        with patch.dict(os.environ, {}, clear=True):
            value = manager.get("NONEXISTENT", generate_if_missing=True)
            assert value is not None
            assert len(value) == 32

    def test_none_if_not_generating(self, tmp_path):
        """Returns None if not found and generate_if_missing=False."""
        manager = SecretsManager(project_dir=tmp_path)

        with patch.dict(os.environ, {}, clear=True):
            value = manager.get("NONEXISTENT", generate_if_missing=False)
            assert value is None

    def test_load_all(self, tmp_path):
        """Load multiple secrets at once."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=val1\nKEY2=val2\n")

        with patch.dict(os.environ, {}, clear=True):
            manager = SecretsManager(project_dir=tmp_path)
            result = manager.load_all(["KEY1", "KEY2", "KEY3"])

            assert result["KEY1"] == "val1"
            assert result["KEY2"] == "val2"
            assert "KEY3" in result  # Generated

    def test_get_missing(self, tmp_path):
        """Identify which secrets are missing."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=val1\n")

        with patch.dict(os.environ, {"KEY2": "val2"}, clear=True):
            manager = SecretsManager(project_dir=tmp_path)
            missing = manager.get_missing(["KEY1", "KEY2", "KEY3", "KEY4"])
            assert missing == ["KEY3", "KEY4"]
