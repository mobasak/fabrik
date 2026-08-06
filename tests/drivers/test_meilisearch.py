"""Unit tests for fabrik.drivers.meilisearch — mocked ssh, no VPS required."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from fabrik.drivers import meilisearch
from fabrik.drivers.meilisearch import (
    MEILI_INTERNAL_URL,
    SHAPE_FLAG,
    _validate_uid,
    applies_to,
    create_index,
    delete_index,
)

# --------------------------------------------------------------------------- #
# applies_to — shape gating                                                    #
# --------------------------------------------------------------------------- #


class TestAppliesTo:
    def test_true_when_flag_set_true(self):
        assert applies_to({SHAPE_FLAG: True}) is True

    def test_true_when_flag_set_truthy(self):
        assert applies_to({SHAPE_FLAG: 1}) is True
        assert applies_to({SHAPE_FLAG: "yes"}) is True

    def test_false_when_flag_absent(self):
        assert applies_to({"kind": "static-site"}) is False

    def test_false_when_flag_falsy(self):
        assert applies_to({SHAPE_FLAG: False}) is False
        assert applies_to({SHAPE_FLAG: None}) is False
        assert applies_to({SHAPE_FLAG: 0}) is False

    def test_false_on_non_dict(self):
        assert applies_to(None) is False  # type: ignore[arg-type]
        assert applies_to([]) is False  # type: ignore[arg-type]
        assert applies_to("has_search_feature=true") is False  # type: ignore[arg-type]

    def test_flag_name_is_canonical_shape_key(self):
        assert SHAPE_FLAG == "has_search_feature"


# --------------------------------------------------------------------------- #
# _validate_uid                                                                #
# --------------------------------------------------------------------------- #


class TestValidateUid:
    @pytest.mark.parametrize("uid", ["my_project", "Proj-2026", "a", "x" * 128, "A1_b-2"])
    def test_valid(self, uid):
        _validate_uid(uid)

    @pytest.mark.parametrize(
        "uid",
        [
            "",
            "-leading",
            "_leading",
            "has space",
            "has.dot",
            "has/slash",
            'has"quote',
            "x" * 129,  # too long
            "; rm -rf /",
        ],
    )
    def test_invalid(self, uid):
        with pytest.raises(ValueError):
            _validate_uid(uid)

    def test_non_string_raises(self):
        with pytest.raises(ValueError):
            _validate_uid(42)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# create_index                                                                 #
# --------------------------------------------------------------------------- #


class TestCreateIndex:
    def test_dry_run_does_not_invoke_ssh(self):
        with patch.object(meilisearch, "ssh") as mock_ssh:
            result = create_index("my_proj", dry_run=True)
        assert result == {"status": "dry_run", "index": "my_proj"}
        mock_ssh.assert_not_called()

    def test_existing_index_returns_exists_without_post(self):
        calls: list[str] = []

        def fake_ssh(cmd, **_kw):
            calls.append(cmd)
            if "docker ps" in cmd:
                return "meili-container-xyz"
            if "http_code" in cmd:  # existence check
                return "200"
            return ""

        with patch.object(meilisearch, "ssh", side_effect=fake_ssh):
            result = create_index("my_proj")

        assert result == {"status": "exists", "index": "my_proj"}
        # 2 ssh calls: resolve container + existence check — NO POST
        assert len(calls) == 2
        assert not any("POST" in c for c in calls)

    def test_missing_index_posts_and_returns_created(self):
        calls: list[str] = []

        def fake_ssh(cmd, **_kw):
            calls.append(cmd)
            if "docker ps" in cmd:
                return "meili-container-xyz"
            if "http_code" in cmd:
                return "404"
            # Create POST → MeiliSearch returns a task-accepted envelope
            return '{"taskUid":1,"indexUid":"my_proj","status":"enqueued"}'

        with patch.object(meilisearch, "ssh", side_effect=fake_ssh):
            result = create_index("my_proj")

        assert result == {"status": "created", "index": "my_proj"}
        assert any("POST" in c for c in calls)
        post = next(c for c in calls if "POST" in c)
        # body contains the uid + primaryKey
        assert '"uid": "my_proj"' in post or '"uid":"my_proj"' in post
        assert '"primaryKey": "id"' in post or '"primaryKey":"id"' in post

    def test_meili_error_code_raises_runtime_error(self):
        def fake_ssh(cmd, **_kw):
            if "docker ps" in cmd:
                return "meili-container-xyz"
            if "http_code" in cmd:
                return "404"
            return '{"message":"bad","code":"invalid_index_uid","type":"invalid_request"}'

        with patch.object(meilisearch, "ssh", side_effect=fake_ssh):
            with pytest.raises(RuntimeError, match="create_index failed"):
                create_index("my_proj")

    def test_container_not_found_raises_runtime_error(self):
        def fake_ssh(cmd, **_kw):
            if "docker ps" in cmd:
                return ""  # no match
            return ""

        with patch.object(meilisearch, "ssh", side_effect=fake_ssh):
            with pytest.raises(RuntimeError, match="MeiliSearch container not found"):
                create_index("my_proj")

    def test_invalid_uid_raises_before_ssh(self):
        with patch.object(meilisearch, "ssh") as mock_ssh:
            with pytest.raises(ValueError):
                create_index("bad name")
            mock_ssh.assert_not_called()

    def test_invalid_primary_key_raises_before_ssh(self):
        with patch.object(meilisearch, "ssh") as mock_ssh:
            with pytest.raises(ValueError):
                create_index("my_proj", primary_key='bad"key')
            mock_ssh.assert_not_called()

    def test_uses_container_side_sh_c_for_master_key_dereference(self):
        """The master key must be dereferenced INSIDE the container, not on
        the host. Verify the command wraps curl in an ``sh -c``."""
        calls: list[str] = []

        def fake_ssh(cmd, **_kw):
            calls.append(cmd)
            if "docker ps" in cmd:
                return "meili-container-xyz"
            if "http_code" in cmd:
                return "200"
            return ""

        with patch.object(meilisearch, "ssh", side_effect=fake_ssh):
            create_index("my_proj")

        # Every curl command (not the docker ps resolver) must go through sh -c
        curl_cmds = [c for c in calls if "curl" in c]
        assert curl_cmds, calls
        for c in curl_cmds:
            assert "docker exec" in c and "sh -c" in c, c
            # The raw `$MEILI_MASTER_KEY` string must be present — if it were
            # expanded on the host, we'd never see the `$` at all.
            assert "$MEILI_MASTER_KEY" in c

    def test_uses_internal_url_not_public(self):
        """Container-side calls must use localhost:7700, not search.vps1..."""
        calls: list[str] = []

        def fake_ssh(cmd, **_kw):
            calls.append(cmd)
            if "docker ps" in cmd:
                return "meili-container-xyz"
            if "http_code" in cmd:
                return "200"
            return ""

        with patch.object(meilisearch, "ssh", side_effect=fake_ssh):
            create_index("my_proj")

        for c in (c for c in calls if "curl" in c):
            assert MEILI_INTERNAL_URL in c
            assert "search.vps1.ocoron.com" not in c


# --------------------------------------------------------------------------- #
# delete_index — rollback                                                      #
# --------------------------------------------------------------------------- #


class TestDeleteIndex:
    def test_success_returns_true(self):
        def fake_ssh(cmd, **_kw):
            if "docker ps" in cmd:
                return "meili-container-xyz"
            return '{"taskUid":2,"status":"enqueued"}'

        with patch.object(meilisearch, "ssh", side_effect=fake_ssh):
            assert delete_index("my_proj") is True

    def test_ssh_failure_returns_false(self):
        def fake_ssh(*_a, **_kw):
            raise RuntimeError("ssh: connection refused")

        with patch.object(meilisearch, "ssh", side_effect=fake_ssh):
            assert delete_index("my_proj") is False

    def test_container_not_found_returns_false(self):
        def fake_ssh(cmd, **_kw):
            if "docker ps" in cmd:
                return ""
            return ""

        with patch.object(meilisearch, "ssh", side_effect=fake_ssh):
            assert delete_index("my_proj") is False

    def test_dry_run_returns_true_without_ssh(self):
        with patch.object(meilisearch, "ssh") as mock_ssh:
            assert delete_index("my_proj", dry_run=True) is True
            mock_ssh.assert_not_called()

    def test_invalid_uid_raises_value_error_before_try(self):
        """Input validation happens before the try/except guard."""
        with patch.object(meilisearch, "ssh") as mock_ssh:
            with pytest.raises(ValueError):
                delete_index("bad name")
            mock_ssh.assert_not_called()

    def test_issues_delete_method(self):
        calls: list[str] = []

        def fake_ssh(cmd, **_kw):
            calls.append(cmd)
            if "docker ps" in cmd:
                return "meili-container-xyz"
            return ""

        with patch.object(meilisearch, "ssh", side_effect=fake_ssh):
            delete_index("my_proj")

        assert any("DELETE" in c and "/indexes/my_proj" in c for c in calls)
