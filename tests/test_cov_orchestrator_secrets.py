"""Coverage sweep for fabrik.orchestrator.secrets: branches the existing suite leaves unguarded."""

import logging
import string
from pathlib import Path

import pytest

from fabrik.orchestrator import secrets as sec
from fabrik.orchestrator.exceptions import ValidationError
from fabrik.orchestrator.secrets import SecretsManager, generate_secret, load_dotenv


@pytest.fixture
def clean_env(monkeypatch):
    for k in ("COV_A", "COV_B", "COV_C", "COV_MISSING"):
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


class TestGenerateSecret:
    def test_zero_length_is_empty(self):
        assert generate_secret(0) == ""

    def test_characters_come_from_ascii_letters_and_digits(self):
        allowed = set(string.ascii_letters + string.digits)
        assert set(generate_secret(500)) <= allowed

    def test_uses_secrets_choice_not_random(self, monkeypatch):
        calls = []

        def fake_choice(seq):
            calls.append(len(seq))
            return "x"

        monkeypatch.setattr(sec.secrets, "choice", fake_choice)
        assert generate_secret(5) == "xxxxx"
        assert calls == [62] * 5

    def test_result_is_str(self):
        assert type(generate_secret(8)) is str


class TestLoadDotenvEdges:
    def test_empty_file_gives_empty_dict(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("")
        assert load_dotenv(f) == {}

    def test_missing_directory_parent_gives_empty_dict(self, tmp_path):
        assert load_dotenv(tmp_path / "nope" / ".env") == {}

    def test_empty_value_is_kept_as_empty_string(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("EMPTY=\nOTHER=1\n")
        assert load_dotenv(f) == {"EMPTY": "", "OTHER": "1"}

    def test_later_duplicate_key_wins(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("K=first\nK=second\n")
        assert load_dotenv(f) == {"K": "second"}

    def test_utf8_value_survives(self, tmp_path):
        f = tmp_path / ".env"
        f.write_bytes("K=päss\n".encode())
        assert load_dotenv(f) == {"K": "päss"}

    def test_oserror_becomes_validation_error_without_chaining(self, tmp_path, monkeypatch):
        f = tmp_path / ".env"
        f.write_text("A=1\n")

        def boom(self, *a, **k):
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(Path, "read_text", boom)
        with pytest.raises(ValidationError, match="Permission denied") as exc:
            load_dotenv(f)
        assert str(f) in str(exc.value)
        assert exc.value.__cause__ is None

    def test_oserror_without_strerror_names_the_type(self, tmp_path, monkeypatch):
        def boom(self, *a, **k):
            raise OSError()

        monkeypatch.setattr(Path, "read_text", boom)
        with pytest.raises(ValidationError, match="OSError"):
            load_dotenv(tmp_path / ".env")

    def test_valueerror_from_parser_is_wrapped(self, tmp_path, monkeypatch):
        f = tmp_path / ".env"
        f.write_text("A=1\n")

        def bad(_text):
            raise ValueError("line 3: bad thing")

        monkeypatch.setattr(sec, "parse_env", bad)
        with pytest.raises(ValidationError, match=r"cannot read .*line 3: bad thing"):
            load_dotenv(f)

    def test_single_line_values_do_not_warn(self, tmp_path, caplog):
        f = tmp_path / ".env"
        f.write_text("A=1\nB=2\n")
        with caplog.at_level(logging.WARNING, logger="fabrik.orchestrator.secrets"):
            load_dotenv(f)
        assert caplog.records == []


class TestSecretsManagerInit:
    def test_default_project_dir_is_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert SecretsManager().project_dir == Path.cwd()

    def test_explicit_project_dir_kept(self, tmp_path):
        assert SecretsManager(project_dir=tmp_path).project_dir == tmp_path

    def test_construction_does_not_read_dotenv(self, tmp_path):
        (tmp_path / ".env").write_text("K='unterminated\n")
        SecretsManager(project_dir=tmp_path)  # must not raise: lazy


class TestDotenvProperty:
    def test_reads_env_file_in_project_dir(self, tmp_path):
        (tmp_path / ".env").write_text("A=1\n")
        assert SecretsManager(tmp_path).dotenv == {"A": "1"}

    def test_missing_file_gives_empty(self, tmp_path):
        assert SecretsManager(tmp_path).dotenv == {}

    def test_cached_after_first_read(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("A=1\n")
        m = SecretsManager(tmp_path)
        assert m.dotenv == {"A": "1"}
        f.write_text("A=2\n")
        assert m.dotenv == {"A": "1"}

    def test_cache_populated_even_when_empty(self, tmp_path):
        m = SecretsManager(tmp_path)
        assert m.dotenv == {}
        (tmp_path / ".env").write_text("A=1\n")
        assert m.dotenv == {}

    def test_malformed_file_raises_and_is_not_cached(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("A='open\n")
        m = SecretsManager(tmp_path)
        with pytest.raises(ValidationError):
            m.dotenv
        f.write_text("A=ok\n")
        assert m.dotenv == {"A": "ok"}


class TestGet:
    def test_env_hit_does_not_read_dotenv(self, tmp_path, clean_env):
        (tmp_path / ".env").write_text("COV_A='broken\n")
        clean_env.setenv("COV_A", "e")
        assert SecretsManager(tmp_path).get("COV_A") == "e"

    def test_empty_env_var_falls_through_to_dotenv(self, tmp_path, clean_env):
        (tmp_path / ".env").write_text("COV_A=file\n")
        clean_env.setenv("COV_A", "")
        assert SecretsManager(tmp_path).get("COV_A") == "file"

    def test_empty_dotenv_value_falls_through_to_none(self, tmp_path, clean_env):
        (tmp_path / ".env").write_text("COV_A=\n")
        assert SecretsManager(tmp_path).get("COV_A", generate_if_missing=False) is None

    def test_empty_dotenv_value_generates_when_allowed(self, tmp_path, clean_env):
        (tmp_path / ".env").write_text("COV_A=\n")
        v = SecretsManager(tmp_path).get("COV_A")
        assert v and len(v) == 32

    def test_generated_secret_is_not_persisted(self, tmp_path, clean_env):
        m = SecretsManager(tmp_path)
        m.get("COV_MISSING")
        assert not (tmp_path / ".env").exists()
        assert "COV_MISSING" not in m.dotenv

    def test_generated_secret_differs_per_call(self, tmp_path, clean_env):
        m = SecretsManager(tmp_path)
        assert m.get("COV_MISSING") != m.get("COV_MISSING")

    def test_generate_uses_generate_secret(self, tmp_path, clean_env):
        clean_env.setattr(sec, "generate_secret", lambda: "FIXED")
        assert SecretsManager(tmp_path).get("COV_MISSING") == "FIXED"

    def test_generation_logged_without_value(self, tmp_path, clean_env, caplog):
        clean_env.setattr(sec, "generate_secret", lambda: "TOPSECRETVALUE")
        with caplog.at_level(logging.DEBUG, logger="fabrik.orchestrator.secrets"):
            SecretsManager(tmp_path).get("COV_MISSING")
        assert "COV_MISSING" in caplog.text
        assert "TOPSECRETVALUE" not in caplog.text

    def test_loaded_value_never_logged(self, tmp_path, clean_env, caplog):
        clean_env.setenv("COV_A", "hunter2hunter2")
        (tmp_path / ".env").write_text("COV_B=letmein12345\n")
        m = SecretsManager(tmp_path)
        with caplog.at_level(logging.DEBUG, logger="fabrik.orchestrator.secrets"):
            m.get("COV_A")
            m.get("COV_B")
        assert "hunter2" not in caplog.text and "letmein" not in caplog.text

    def test_malformed_dotenv_with_env_miss_raises_even_without_generation(self, tmp_path, clean_env):
        (tmp_path / ".env").write_text("COV_A='open\n")
        with pytest.raises(ValidationError):
            SecretsManager(tmp_path).get("COV_A", generate_if_missing=False)


class TestLoadAll:
    def test_empty_key_list(self, tmp_path):
        assert SecretsManager(tmp_path).load_all([]) == {}

    def test_no_generation_omits_missing_keys(self, tmp_path, clean_env):
        (tmp_path / ".env").write_text("COV_A=1\n")
        r = SecretsManager(tmp_path).load_all(["COV_A", "COV_MISSING"], generate_if_missing=False)
        assert r == {"COV_A": "1"}

    def test_generated_values_are_distinct_per_key(self, tmp_path, clean_env):
        r = SecretsManager(tmp_path).load_all(["COV_A", "COV_B"])
        assert set(r) == {"COV_A", "COV_B"} and r["COV_A"] != r["COV_B"]

    def test_env_beats_dotenv_per_key(self, tmp_path, clean_env):
        (tmp_path / ".env").write_text("COV_A=file\nCOV_B=file\n")
        clean_env.setenv("COV_A", "env")
        assert SecretsManager(tmp_path).load_all(["COV_A", "COV_B"]) == {
            "COV_A": "env",
            "COV_B": "file",
        }

    def test_duplicate_keys_collapse(self, tmp_path, clean_env):
        (tmp_path / ".env").write_text("COV_A=1\n")
        assert SecretsManager(tmp_path).load_all(["COV_A", "COV_A"]) == {"COV_A": "1"}


class TestGetMissing:
    def test_empty_list(self, tmp_path):
        assert SecretsManager(tmp_path).get_missing([]) == []

    def test_preserves_input_order_and_duplicates(self, tmp_path, clean_env):
        assert SecretsManager(tmp_path).get_missing(["COV_B", "COV_A", "COV_B"]) == [
            "COV_B",
            "COV_A",
            "COV_B",
        ]

    def test_does_not_generate_or_mutate(self, tmp_path, clean_env):
        m = SecretsManager(tmp_path)
        m.get_missing(["COV_A"])
        assert m.dotenv == {}

    def test_all_present_gives_empty(self, tmp_path, clean_env):
        (tmp_path / ".env").write_text("COV_A=1\n")
        clean_env.setenv("COV_B", "2")
        assert SecretsManager(tmp_path).get_missing(["COV_A", "COV_B"]) == []

    def test_malformed_dotenv_propagates(self, tmp_path, clean_env):
        (tmp_path / ".env").write_text("COV_A='open\n")
        with pytest.raises(ValidationError):
            SecretsManager(tmp_path).get_missing(["COV_A"])

    @pytest.mark.xfail(
        strict=True,
        reason="secrets.py:150 treats an empty env var / empty .env value as present, "
        "while get() (:103,:110) treats it as missing",
    )
    def test_empty_value_counts_as_missing_like_get(self, tmp_path, clean_env):
        clean_env.setenv("COV_A", "")
        (tmp_path / ".env").write_text("COV_B=\n")
        m = SecretsManager(tmp_path)
        assert m.get("COV_A", generate_if_missing=False) is None
        assert m.get_missing(["COV_A", "COV_B"]) == ["COV_A", "COV_B"]
