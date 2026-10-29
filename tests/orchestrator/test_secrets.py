"""Tests for secrets management."""

import logging
import os
from unittest.mock import patch

import pytest

from fabrik.orchestrator.exceptions import ValidationError
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


class TestLoadDotenvComposeGrammar:
    """W-f62a2cdc: the hub secrets reader reads `.env` as compose does (`fabrik.env_file`, D-1277)."""

    def test_inline_comment_is_not_part_of_the_value(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("KILO_MAX_RETRIES=3 # retries before giving up\n")
        assert load_dotenv(env_file) == {"KILO_MAX_RETRIES": "3"}

    def test_double_quote_escapes_decode(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text('PASSWORD="a\\"b\\$c"\nTRAILING=abc"\n')
        assert load_dotenv(env_file) == {"PASSWORD": 'a"b$c', "TRAILING": 'abc"'}

    def test_dollar_value_is_a_plain_literal(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("BARE=a$b\nQUOTED='x$y'\nESCAPED=\"p\\$q\"\n")
        result = load_dotenv(env_file)
        assert result == {"BARE": "a$b", "QUOTED": "x$y", "ESCAPED": "p$q"}
        assert all(type(v) is str for v in result.values())

    @pytest.mark.parametrize(
        "content",
        ['OK=1\nDB_PASSWORD="s3cretvalue\n', 'OK=1\nDB_PASSWORD="s3cret""value"\n'],
        ids=["unterminated", "quote-after-close"],
    )
    def test_malformed_file_raises_naming_path_not_value(self, tmp_path, content):
        env_file = tmp_path / ".env"
        env_file.write_text(content)
        with pytest.raises(ValidationError) as exc:
            load_dotenv(env_file)
        message = str(exc.value)
        assert str(env_file) in message and "DB_PASSWORD" in message
        assert "s3cret" not in message

    def test_carriage_returns_end_lines(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_bytes(b'CRLF=v # c\r\nA="x"\rB=2\nPEM="l1\r\nl2"\n')
        assert load_dotenv(env_file) == {"CRLF": "v", "A": "x", "B": "2", "PEM": "l1\nl2"}

    def test_unreadable_file_raises_validation_error(self, tmp_path):
        (tmp_path / ".env").mkdir()
        with pytest.raises(ValidationError, match="cannot read"):
            load_dotenv(tmp_path / ".env")

    @pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
    def test_unenterable_folder_raises_validation_error(self, tmp_path):
        locked = tmp_path / "locked"
        locked.mkdir()
        (locked / ".env").write_text("A=1\n")
        locked.chmod(0o600)
        try:
            with pytest.raises(ValidationError, match="cannot read"):
                load_dotenv(locked / ".env")
        finally:
            locked.chmod(0o700)

    def test_non_utf8_file_raises_without_the_byte(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_bytes(b"OK=1\nTOKEN=ab\xffcd\n")
        with pytest.raises(ValidationError) as exc:
            load_dotenv(env_file)
        message = str(exc.value)
        assert str(env_file) in message and "not UTF-8 at byte 13" in message
        assert "0xff" not in message and "\\xff" not in message

    def test_multiline_value_warns_naming_the_key(self, tmp_path, caplog):
        env_file = tmp_path / ".env"
        env_file.write_text('DB_PASS="abc\nAPI_TOKEN=xyz"\nOTHER=1\n')
        with caplog.at_level(logging.WARNING, logger="fabrik.orchestrator.secrets"):
            result = load_dotenv(env_file)
        assert result == {"DB_PASS": "abc\nAPI_TOKEN=xyz", "OTHER": "1"}
        assert len(caplog.records) == 1 and "DB_PASS" in caplog.text
        assert "xyz" not in caplog.text and "abc" not in caplog.text


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

    def test_manager_refuses_malformed_dotenv_instead_of_minting(self, tmp_path):
        """W-f62a2cdc: an unreadable `.env` must stop the deploy, never mint over the real secret."""
        (tmp_path / ".env").write_text("DB_PASSWORD='real-one\n")

        with patch.dict(os.environ, {}, clear=True):
            manager = SecretsManager(project_dir=tmp_path)
            with pytest.raises(ValidationError):
                manager.get("DB_PASSWORD", generate_if_missing=True)
