"""Unit tests for fabrik.drivers.backrest — mocked run_locked, no VPS required."""

from __future__ import annotations

import base64
import json
import re
from unittest.mock import patch

import pytest

from fabrik.drivers import backrest
from fabrik.drivers.backrest import (
    BACKREST_CONFIG,
    DEFAULT_CRON,
    DEFAULT_EXCLUDES,
    DEFAULT_REPO,
    _build_add_script,
    _build_remove_script,
    _plan_json,
    add_backup_plan,
    remove_backup_plan,
)

# --------------------------------------------------------------------------- #
# _plan_json                                                                   #
# --------------------------------------------------------------------------- #


class TestPlanJson:
    def test_returns_parseable_json(self):
        out = _plan_json("my-plan", ["/opt/my"], DEFAULT_REPO, DEFAULT_CRON, DEFAULT_EXCLUDES)
        parsed = json.loads(out)
        assert parsed["id"] == "my-plan"
        assert parsed["repo"] == DEFAULT_REPO
        assert parsed["paths"] == ["/opt/my"]
        assert parsed["schedule"]["cron"] == DEFAULT_CRON

    def test_excludes_tuple_serialized_as_list(self):
        out = _plan_json("x", ["/a"], DEFAULT_REPO, DEFAULT_CRON, ("**/cache",))
        parsed = json.loads(out)
        assert parsed["excludes"] == ["**/cache"]

    def test_failure_hook_embeds_plan_id(self):
        out = _plan_json("plan-7", ["/a"], DEFAULT_REPO, DEFAULT_CRON, ())
        parsed = json.loads(out)
        hook_cmd = parsed["hooks"][0]["actionCommand"]["command"]
        assert "Backup failed: plan-7" in hook_cmd
        assert "http://apprise:8000/notify/alerts" in hook_cmd
        assert parsed["hooks"][0]["conditions"] == ["CONDITION_ANY_ERROR"]

    def test_multiple_paths_all_present(self):
        out = _plan_json("x", ["/a", "/b", "/c"], DEFAULT_REPO, DEFAULT_CRON, ())
        assert json.loads(out)["paths"] == ["/a", "/b", "/c"]


# --------------------------------------------------------------------------- #
# _build_add_script                                                            #
# --------------------------------------------------------------------------- #


class TestBuildAddScript:
    def test_contains_all_seven_safety_steps(self):
        script = _build_add_script("Zm9v", "test-plan")
        # Marker comments from the driver docstring
        assert "set -euo pipefail" in script
        assert "Idempotency" in script
        assert "Timestamped backup" in script
        assert "jq --argjson" in script
        assert "python3 -m json.tool" in script
        assert "CORRUPT_RESTORED" in script
        assert "mv \"$CFG.tmp\" \"$CFG\"" in script
        assert "docker restart" in script

    def test_backrest_container_matched_by_prefix(self):
        script = _build_add_script("Zm9v", "test-plan")
        # Updated 2026-06-08 from `^backrest-` (Coolify-era suffix-only)
        # to `^backrest(-|$)` so the bare-named `backrest` container that's
        # live post-migration actually matches.
        assert "^backrest(-|$)" in script
        # The docker format literal must survive f-string escaping
        assert "{{.Names}}" in script

    def test_plan_id_json_escaped(self):
        """jq select needs the plan_id JSON-encoded (handles special chars)."""
        script = _build_add_script("Zm9v", 'weird"id')
        # json.dumps quotes the string — the literal JSON string appears
        assert '"weird\\"id"' in script

    def test_base64_payload_pipes_into_base64_d(self):
        # shlex.quote skips quoting for strings without shell metacharacters.
        # Test resilient to either form (``'X' | base64 -d`` or ``X | base64 -d``).
        script = _build_add_script("HELLO_B64", "p")
        assert re.search(r"'?HELLO_B64'? \| base64 -d", script) is not None

    def test_backrest_config_path_matches_constant(self):
        script = _build_add_script("Zm9v", "p")
        assert f"CFG={BACKREST_CONFIG}" in script


# --------------------------------------------------------------------------- #
# _build_remove_script                                                         #
# --------------------------------------------------------------------------- #


class TestBuildRemoveScript:
    def test_idempotent_not_found_branch(self):
        script = _build_remove_script("test-plan")
        assert "NOT_FOUND" in script
        assert "jq -e" in script

    def test_del_on_plan_id(self):
        script = _build_remove_script("test-plan")
        assert 'del(.plans[] | select(.id=="test-plan"))' in script

    def test_restores_from_bak_on_corrupt(self):
        script = _build_remove_script("test-plan")
        assert "CORRUPT_RESTORED" in script
        assert 'cp "$BAK" "$CFG"' in script


# --------------------------------------------------------------------------- #
# add_backup_plan                                                              #
# --------------------------------------------------------------------------- #


class TestAddBackupPlan:
    def test_created_status_from_run_locked(self):
        with patch.object(backrest, "run_locked", return_value="CREATED\n") as mock_rl:
            result = add_backup_plan("my-plan", ["/opt/my-data"])
        assert result == {"status": "created", "plan": "my-plan"}
        assert mock_rl.called
        # run_locked called with the shared backrest-config resource
        assert mock_rl.call_args.args[0] == "backrest-config"

    def test_exists_status_from_run_locked(self):
        with patch.object(backrest, "run_locked", return_value="EXISTS\n"):
            result = add_backup_plan("my-plan", ["/opt/my-data"])
        assert result == {"status": "exists", "plan": "my-plan"}

    def test_dry_run_does_not_invoke_run_locked(self):
        with patch.object(backrest, "run_locked") as mock_rl:
            result = add_backup_plan("my-plan", ["/opt/my-data"], dry_run=True)
        assert result == {"status": "dry_run", "plan": "my-plan"}
        mock_rl.assert_not_called()

    def test_script_contains_base64_encoded_plan(self):
        captured_scripts: list[str] = []

        def capture(_res, script, **_kw):
            captured_scripts.append(script)
            return "CREATED"

        with patch.object(backrest, "run_locked", side_effect=capture):
            add_backup_plan("my-plan", ["/opt/my-data"])

        assert len(captured_scripts) == 1
        # Extract the base64 token — shlex.quote may or may not wrap in single quotes
        match = re.search(r"echo '?([A-Za-z0-9+/=]+)'? \| base64 -d", captured_scripts[0])
        assert match is not None, captured_scripts[0]
        decoded = json.loads(base64.b64decode(match.group(1)).decode())
        assert decoded["id"] == "my-plan"
        assert decoded["paths"] == ["/opt/my-data"]
        assert decoded["repo"] == DEFAULT_REPO

    def test_empty_plan_id_raises(self):
        with patch.object(backrest, "run_locked") as mock_rl:
            with pytest.raises(ValueError):
                add_backup_plan("", ["/opt/my"])
            mock_rl.assert_not_called()

    def test_empty_paths_raises(self):
        with patch.object(backrest, "run_locked") as mock_rl:
            with pytest.raises(ValueError):
                add_backup_plan("my-plan", [])
            mock_rl.assert_not_called()

    def test_non_string_plan_id_raises(self):
        with patch.object(backrest, "run_locked") as mock_rl:
            with pytest.raises(ValueError):
                add_backup_plan(42, ["/opt/my"])  # type: ignore[arg-type]
            mock_rl.assert_not_called()

    def test_non_string_path_raises(self):
        with patch.object(backrest, "run_locked") as mock_rl:
            with pytest.raises(ValueError):
                add_backup_plan("my-plan", ["/opt/my", 42])  # type: ignore[list-item]
            mock_rl.assert_not_called()

    def test_run_locked_timeout_propagates(self):
        def failing(_res, _script, **_kw):
            raise RuntimeError("flock timed out")

        with patch.object(backrest, "run_locked", side_effect=failing):
            with pytest.raises(RuntimeError, match="flock timed out"):
                add_backup_plan("my-plan", ["/opt/my-data"])


# --------------------------------------------------------------------------- #
# remove_backup_plan                                                           #
# --------------------------------------------------------------------------- #


class TestRemoveBackupPlan:
    def test_returns_true_on_removed(self):
        with patch.object(backrest, "run_locked", return_value="REMOVED\n"):
            assert remove_backup_plan("my-plan") is True

    def test_returns_true_on_not_found(self):
        """NOT_FOUND is idempotent success — no plan to delete is still OK."""
        with patch.object(backrest, "run_locked", return_value="NOT_FOUND\n"):
            assert remove_backup_plan("my-plan") is True

    def test_returns_false_on_runtime_error(self):
        def failing(*_a, **_kw):
            raise RuntimeError("corrupt config")

        with patch.object(backrest, "run_locked", side_effect=failing):
            assert remove_backup_plan("my-plan") is False

    def test_dry_run_returns_true_without_run_locked(self):
        with patch.object(backrest, "run_locked") as mock_rl:
            assert remove_backup_plan("my-plan", dry_run=True) is True
            mock_rl.assert_not_called()

    def test_empty_plan_id_raises(self):
        with patch.object(backrest, "run_locked") as mock_rl:
            with pytest.raises(ValueError):
                remove_backup_plan("")
            mock_rl.assert_not_called()
