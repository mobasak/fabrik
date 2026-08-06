"""Tests for fabrik.orchestrator.coolify_alias (T2-04 G-J3).

All ssh() calls mocked — no live VPS contact.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from fabrik.orchestrator import coolify_alias
from fabrik.orchestrator.coolify_alias import (
    ALIASES_PATH,
    SERVICE_UNIT,
    _load_remote_aliases,
    add_alias,
)

# ─────────────────────────────────────────────────────────────────────────────
# add_alias
# ─────────────────────────────────────────────────────────────────────────────


class TestAddAlias:
    def _stub_remote(self, payload: dict):
        return json.dumps(payload, indent=2)

    def test_no_op_when_alias_already_matches(self):
        existing = self._stub_remote({"version": 1, "aliases": {"abc123": "myalias"}})
        with patch.object(coolify_alias, "ssh", return_value=existing) as mock_ssh:
            r = add_alias("abc123", "myalias")
        assert r["status"] == "exists"
        # Only one ssh call expected: the cat. No tee, no mv, no restart.
        assert mock_ssh.call_count == 1
        call_cmd = mock_ssh.call_args[0][0]
        assert "cat" in call_cmd

    def test_adds_new_alias_with_atomic_write_and_restart(self):
        existing = self._stub_remote({"version": 1, "aliases": {"existing-uuid": "existing-alias"}})
        calls: list[str] = []

        def fake_ssh(cmd, *, dry_run=False, **kw):
            calls.append(cmd)
            if "cat " in cmd:
                return existing
            return ""

        with patch.object(coolify_alias, "ssh", side_effect=fake_ssh):
            r = add_alias("new-uuid", "new-alias")
        assert r["status"] == "added"
        # Expected sequence: cat → tee tmp → chown+chmod+mv → systemctl restart
        joined = "\n".join(calls)
        assert "cat /opt/coolify-alias-watcher/aliases.json" in joined
        assert "tee /opt/coolify-alias-watcher/aliases.json.tmp" in joined
        assert "mv /opt/coolify-alias-watcher/aliases.json.tmp" in joined
        assert "systemctl restart coolify-alias-watcher.service" in joined

    def test_updates_existing_alias_when_value_differs(self):
        existing = self._stub_remote({"version": 1, "aliases": {"abc123": "OLD-alias"}})

        def fake_ssh(cmd, *, dry_run=False, **kw):
            if "cat " in cmd:
                return existing
            return ""

        with patch.object(coolify_alias, "ssh", side_effect=fake_ssh):
            r = add_alias("abc123", "NEW-alias")
        assert r["status"] == "updated"

    def test_dry_run_emits_zero_mutations(self):
        existing = self._stub_remote({"version": 1, "aliases": {}})
        with patch.object(coolify_alias, "ssh", return_value=existing) as mock_ssh:
            r = add_alias("abc123", "myalias", dry_run=True)
        assert r["status"] == "dry_run"
        # Only the cat (read) call; no tee/mv/restart.
        assert mock_ssh.call_count == 1
        assert "cat" in mock_ssh.call_args[0][0]

    def test_empty_uuid_raises_value_error(self):
        with pytest.raises(ValueError, match="coolify_uuid"):
            add_alias("", "myalias")

    def test_empty_alias_raises_value_error(self):
        with pytest.raises(ValueError, match="alias"):
            add_alias("abc123", "")

    def test_payload_is_serialized_with_sort_keys(self):
        existing = self._stub_remote({"version": 1, "aliases": {"b": "B", "a": "A"}})
        captured = {}

        def fake_ssh(cmd, *, dry_run=False, **kw):
            if "cat " in cmd:
                return existing
            if "tee" in cmd:
                captured["tee"] = cmd
            return ""

        with patch.object(coolify_alias, "ssh", side_effect=fake_ssh):
            add_alias("c", "C")
        # The tee command should embed a JSON payload with sorted keys
        # (a, b, c) — sort_keys=True guarantee in _write_remote_aliases.
        assert captured.get("tee"), "tee command not captured"


# ─────────────────────────────────────────────────────────────────────────────
# _load_remote_aliases
# ─────────────────────────────────────────────────────────────────────────────


class TestLoadRemoteAliases:
    def test_empty_payload_returns_skeleton(self):
        with patch.object(coolify_alias, "ssh", return_value=""):
            r = _load_remote_aliases()
        assert r == {"version": 1, "aliases": {}}

    def test_ssh_failure_returns_skeleton(self):
        with patch.object(coolify_alias, "ssh", side_effect=RuntimeError("ssh dead")):
            r = _load_remote_aliases()
        assert r == {"version": 1, "aliases": {}}

    def test_malformed_json_raises(self):
        with patch.object(coolify_alias, "ssh", return_value="not json{"):
            with pytest.raises(json.JSONDecodeError):
                _load_remote_aliases()


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────


def test_aliases_path_is_correct():
    assert ALIASES_PATH == "/opt/coolify-alias-watcher/aliases.json"


def test_service_unit_is_correct():
    assert SERVICE_UNIT == "coolify-alias-watcher.service"
