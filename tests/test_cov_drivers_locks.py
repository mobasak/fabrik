"""Coverage sweep for fabrik.drivers.locks: behaviour not asserted by tests/drivers/test_locks.py.

Hermetic: ``ssh`` is always mocked; nothing touches the network or the filesystem.
"""

from __future__ import annotations

import logging
import shlex
from unittest.mock import patch

import pytest

from fabrik.drivers import locks
from fabrik.drivers.locks import GIT_VERSIONED_DIRS, LOCK_DIR, git_commit_config, run_locked

GATUS = "/opt/monitoring/configs/gatus"


class TestConstants:
    def test_lock_dir_is_root_owned_shared_dir(self):
        assert LOCK_DIR == "/var/lib/fabrik-locks"
        assert not LOCK_DIR.startswith("/tmp")

    def test_whitelist_is_a_set_of_absolute_paths(self):
        assert isinstance(GIT_VERSIONED_DIRS, set)
        assert all(p.startswith("/") for p in GIT_VERSIONED_DIRS)


class TestRunLockedDefaults:
    @patch("fabrik.drivers.locks.ssh")
    def test_default_timeout_is_120_for_flock_and_130_for_ssh(self, mock_ssh):
        mock_ssh.return_value = ""
        run_locked("demo", "true")
        cmd = mock_ssh.call_args.args[0]
        assert "flock -x -w 120 " in cmd
        assert mock_ssh.call_args.kwargs == {"timeout": 130}

    @patch("fabrik.drivers.locks.ssh")
    def test_custom_timeout_flows_to_both_flock_and_ssh(self, mock_ssh):
        mock_ssh.return_value = ""
        run_locked("demo", "true", timeout=7)
        assert "flock -x -w 7 " in mock_ssh.call_args.args[0]
        assert mock_ssh.call_args.kwargs["timeout"] == 17

    @patch("fabrik.drivers.locks.ssh")
    def test_ssh_called_exactly_once(self, mock_ssh):
        mock_ssh.return_value = ""
        run_locked("demo", "true")
        assert mock_ssh.call_count == 1


class TestRunLockedCommandShape:
    @patch("fabrik.drivers.locks.ssh")
    def test_steps_are_chained_with_and_so_a_failure_skips_flock(self, mock_ssh):
        mock_ssh.return_value = ""
        run_locked("demo", "true")
        cmd = mock_ssh.call_args.args[0]
        head = cmd.split(" bash -c ")[0]
        steps = head.split(" && ")
        assert steps[0].startswith("sudo install -d -m 755 -o root -g root")
        assert steps[1].startswith("sudo touch ")
        assert steps[2].startswith("sudo chmod 644 ")
        assert steps[3].startswith("flock -x -w ")
        assert len(steps) == 4

    @patch("fabrik.drivers.locks.ssh")
    def test_command_ends_with_quoted_script_and_parses_back(self, mock_ssh):
        mock_ssh.return_value = ""
        script = "set -euo pipefail\necho 'a b'; echo \"$HOME\" `x` $(y)\n"
        run_locked("demo", script)
        cmd = mock_ssh.call_args.args[0]
        tokens = shlex.split(cmd.split(" && ")[-1])
        assert tokens[-3:-1] == ["bash", "-c"]
        assert tokens[-1] == script

    @patch("fabrik.drivers.locks.ssh")
    def test_empty_script_is_still_quoted_as_empty_arg(self, mock_ssh):
        mock_ssh.return_value = ""
        run_locked("demo", "")
        assert mock_ssh.call_args.args[0].endswith("bash -c ''")

    @patch("fabrik.drivers.locks.ssh")
    def test_lock_file_path_is_used_consistently(self, mock_ssh):
        mock_ssh.return_value = ""
        run_locked("my_res-1", "true")
        cmd = mock_ssh.call_args.args[0]
        lock = f"{LOCK_DIR}/fabrik-my_res-1.lock"
        assert cmd.count(lock) == 3  # touch, chmod, flock


class TestRunLockedResourceValidation:
    @pytest.mark.parametrize("resource", ["a", "A", "0", "_", "-", "backrest-config", "A_b-9"])
    @patch("fabrik.drivers.locks.ssh")
    def test_accepts_plain_words(self, mock_ssh, resource):
        mock_ssh.return_value = ""
        run_locked(resource, "true")
        assert f"fabrik-{resource}.lock" in mock_ssh.call_args.args[0]

    @pytest.mark.parametrize(
        "resource", ["abc\n", "\nabc", "a.b", "é", "a٠", "a\tb", "..", "a/b", "a'b", "a&b"]
    )
    @patch("fabrik.drivers.locks.ssh")
    def test_rejects_edge_cases_without_ssh(self, mock_ssh, resource):
        with pytest.raises(ValueError):
            run_locked(resource, "true")
        mock_ssh.assert_not_called()

    @patch("fabrik.drivers.locks.ssh")
    def test_error_message_shows_repr_of_resource(self, mock_ssh):
        with pytest.raises(ValueError) as exc:
            run_locked("a/b", "true")
        assert "'a/b'" in str(exc.value)
        assert "[A-Za-z0-9_-]+" in str(exc.value)


class TestRunLockedErrorPropagation:
    @patch("fabrik.drivers.locks.ssh")
    def test_runtime_error_from_ssh_propagates(self, mock_ssh):
        mock_ssh.side_effect = RuntimeError("flock: timed out")
        with pytest.raises(RuntimeError, match="timed out"):
            run_locked("demo", "true")

    @patch("fabrik.drivers.locks.ssh")
    def test_other_exceptions_are_not_swallowed(self, mock_ssh):
        mock_ssh.side_effect = OSError("no route")
        with pytest.raises(OSError):
            run_locked("demo", "true")


class TestGitCommitConfigWhitelist:
    @pytest.mark.parametrize(
        "path",
        [
            GATUS + "/",
            GATUS + "/sub",
            "/opt/monitoring/configs",
            "opt/monitoring/configs/gatus",
            "",
            GATUS + " ",
            GATUS.upper(),
        ],
    )
    @patch("fabrik.drivers.locks.ssh")
    def test_near_misses_are_rejected_without_ssh(self, mock_ssh, path):
        with pytest.raises(ValueError, match="not in whitelist"):
            git_commit_config(path, "m")
        mock_ssh.assert_not_called()

    @patch("fabrik.drivers.locks.ssh")
    def test_rejection_message_names_path_and_whitelist(self, mock_ssh):
        with pytest.raises(ValueError) as exc:
            git_commit_config("/etc/secret", "m")
        msg = str(exc.value)
        assert "/etc/secret" in msg
        assert GATUS in msg

    @patch("fabrik.drivers.locks.ssh")
    def test_dry_run_still_validates_whitelist(self, mock_ssh):
        with pytest.raises(ValueError):
            git_commit_config("/etc/secret", "m", dry_run=True)
        mock_ssh.assert_not_called()

    @patch("fabrik.drivers.locks.ssh")
    def test_whitelist_is_checked_against_live_set(self, mock_ssh, monkeypatch):
        monkeypatch.setattr(locks, "GIT_VERSIONED_DIRS", {"/srv/x"})
        git_commit_config("/srv/x", "m")
        assert mock_ssh.call_count == 5


class TestGitCommitConfigDryRun:
    def test_dry_run_logs_intent_and_returns_none(self, caplog):
        with patch("fabrik.drivers.locks.ssh") as mock_ssh, caplog.at_level(logging.INFO):
            result = git_commit_config(GATUS, "hello msg", dry_run=True)
        assert result is None
        mock_ssh.assert_not_called()
        assert any("DRY RUN" in r.getMessage() and "hello msg" in r.getMessage() for r in caplog.records)
        assert any(GATUS in r.getMessage() for r in caplog.records)


class TestGitCommitConfigCommands:
    @patch("fabrik.drivers.locks.ssh")
    def test_runs_five_ssh_steps_in_order(self, mock_ssh):
        git_commit_config(GATUS, "msg")
        cmds = [c.args[0] for c in mock_ssh.call_args_list]
        assert len(cmds) == 5
        assert "git rev-parse --git-dir" in cmds[0] and "git init -q" in cmds[0]
        assert "git config user.name 'Fabrik Automation'" in cmds[1]
        assert "git config user.email 'fabrik@ocoron.com'" in cmds[2]
        assert "chmod 700 .git" in cmds[3]
        assert "git add -A" in cmds[4] and "git commit -m" in cmds[4]

    @patch("fabrik.drivers.locks.ssh")
    def test_every_step_cds_into_the_config_dir(self, mock_ssh):
        git_commit_config(GATUS, "msg")
        for c in mock_ssh.call_args_list:
            assert c.args[0].startswith(f"cd {shlex.quote(GATUS)} && ")

    @patch("fabrik.drivers.locks.ssh")
    def test_commit_allows_empty_and_never_fails_the_shell(self, mock_ssh):
        git_commit_config(GATUS, "msg")
        last = mock_ssh.call_args_list[-1].args[0]
        assert "--allow-empty" in last
        assert last.endswith("|| true")

    @patch("fabrik.drivers.locks.ssh")
    def test_message_is_shell_quoted(self, mock_ssh):
        msg = "it's \"odd\"; rm -rf / $(id)"
        git_commit_config(GATUS, msg)
        last = mock_ssh.call_args_list[-1].args[0]
        assert f"git commit -m {shlex.quote(msg)} " in last

    @patch("fabrik.drivers.locks.ssh")
    def test_returns_none_on_success(self, mock_ssh):
        assert git_commit_config(GATUS, "msg") is None


class TestGitCommitConfigErrors:
    @patch("fabrik.drivers.locks.ssh")
    def test_failure_stops_remaining_steps_and_logs_warning(self, mock_ssh, caplog):
        mock_ssh.side_effect = [None, RuntimeError("boom")]
        with caplog.at_level(logging.WARNING, logger="fabrik.drivers.locks"):
            git_commit_config(GATUS, "msg")
        assert mock_ssh.call_count == 2
        warns = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warns) == 1
        assert "non-fatal" in warns[0].getMessage()
        assert "boom" in warns[0].getMessage()

    @patch("fabrik.drivers.locks.ssh")
    def test_any_exception_type_is_swallowed(self, mock_ssh):
        mock_ssh.side_effect = OSError("conn reset")
        git_commit_config(GATUS, "msg")
        assert mock_ssh.call_count == 1
