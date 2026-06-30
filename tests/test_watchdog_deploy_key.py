"""Phase 8 of deploy-readiness-gaps: deploy key auto-push to GitHub.

Closes the watchdog → GitHub copy-paste loop. After `_ensure_deploy_key`
generates the keypair on VPS, also POST the public key to the project's
GitHub repo via `gh api`.

Per docs/development/plans/2026-06-30-plan-fabrik-deploy-readiness-gaps.md
Phase 8.

What we deliberately mock:
- `subprocess.run` (gh CLI invocations)
- `fabrik.drivers.watchdog.ssh` (VPS-side ssh-keygen + cat)

All tests are hermetic — no live GitHub API calls.
"""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, patch

import pytest

from fabrik.drivers import watchdog


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------
class TestParseGithubRepo:
    """The plan §"Drifts corrected": no URL parser existed in fabrik."""

    def test_https_with_git_suffix(self) -> None:
        assert watchdog._parse_github_repo("https://github.com/foo/bar.git") == ("foo", "bar")

    def test_https_without_git_suffix(self) -> None:
        assert watchdog._parse_github_repo("https://github.com/foo/bar") == ("foo", "bar")

    def test_ssh_form(self) -> None:
        assert watchdog._parse_github_repo("git@github.com:foo/bar.git") == ("foo", "bar")

    def test_ssh_form_without_git_suffix(self) -> None:
        assert watchdog._parse_github_repo("git@github.com:foo/bar") == ("foo", "bar")

    def test_rejects_non_github(self) -> None:
        with pytest.raises(ValueError, match="github"):
            watchdog._parse_github_repo("https://gitlab.com/foo/bar.git")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError):
            watchdog._parse_github_repo("")

    def test_rejects_malformed(self) -> None:
        with pytest.raises(ValueError):
            watchdog._parse_github_repo("not-a-url")


# ---------------------------------------------------------------------------
# _has_repo_scope — gh CLI scope check
# ---------------------------------------------------------------------------
class TestHasRepoScope:
    def test_returns_true_when_repo_scope_present(self) -> None:
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="Token scopes: 'gist', 'read:org', 'repo', 'workflow'\n",
            )
            assert watchdog._has_repo_scope() is True

    def test_returns_false_when_repo_scope_missing(self) -> None:
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="Token scopes: 'gist', 'read:org'\n",
            )
            assert watchdog._has_repo_scope() is False

    def test_returns_false_when_gh_not_installed(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert watchdog._has_repo_scope() is False

    def test_returns_false_when_gh_auth_failed(self) -> None:
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=1, stdout="", stderr="not authenticated")
            assert watchdog._has_repo_scope() is False


# ---------------------------------------------------------------------------
# _push_deploy_key_to_github — orchestration
# ---------------------------------------------------------------------------
class TestPushDeployKey:
    PUBKEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleExampleExample watchdog-test@fabrik"
    OTHER_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDifferentDifferentDiff watchdog-test@fabrik"

    def test_skip_when_repo_scope_missing(self, caplog: pytest.LogCaptureFixture) -> None:
        with patch("fabrik.drivers.watchdog._has_repo_scope", return_value=False), \
             patch("subprocess.run") as mock_run, \
             caplog.at_level(logging.WARNING, logger="fabrik.drivers.watchdog"):
            result = watchdog._push_deploy_key_to_github(
                owner="foo", repo="bar", title="fabrik-watchdog-deploy", pubkey=self.PUBKEY,
            )
        assert result["status"] == "skipped"
        assert result["reason"] == "no_repo_scope"
        mock_run.assert_not_called()
        assert any("manual deploy-key registration required" in r.message for r in caplog.records)

    def test_idempotent_when_key_already_registered_matching(self) -> None:
        existing = [{"title": "fabrik-watchdog-deploy", "key": self.PUBKEY}]
        with patch("fabrik.drivers.watchdog._has_repo_scope", return_value=True), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=json.dumps(existing), stderr="",
            )
            result = watchdog._push_deploy_key_to_github(
                owner="foo", repo="bar", title="fabrik-watchdog-deploy", pubkey=self.PUBKEY,
            )
        assert result["status"] == "idempotent"
        # Only the GET (single subprocess call), no POST
        assert mock_run.call_count == 1
        gh_args = mock_run.call_args.args[0]
        assert gh_args[0] == "gh"
        assert "api" in gh_args
        # Must not contain -X POST (case-insensitive scan)
        joined = " ".join(gh_args)
        assert "-X POST" not in joined

    def test_conflict_when_key_already_registered_different(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        existing = [{"title": "fabrik-watchdog-deploy", "key": self.OTHER_KEY}]
        with patch("fabrik.drivers.watchdog._has_repo_scope", return_value=True), \
             patch("subprocess.run") as mock_run, \
             caplog.at_level(logging.WARNING, logger="fabrik.drivers.watchdog"):
            mock_run.return_value = MagicMock(
                returncode=0, stdout=json.dumps(existing), stderr="",
            )
            result = watchdog._push_deploy_key_to_github(
                owner="foo", repo="bar", title="fabrik-watchdog-deploy", pubkey=self.PUBKEY,
            )
        assert result["status"] == "conflict"
        # GET only; no POST
        assert mock_run.call_count == 1
        assert any("conflict" in r.message.lower() for r in caplog.records)

    def test_post_when_no_existing_key(self) -> None:
        calls = []

        def fake_run(args, **kw):
            calls.append(args)
            if "GET" in args or args.count("api") >= 1 and "-X" not in args:
                # First call: GET — no existing keys
                return MagicMock(returncode=0, stdout="[]", stderr="")
            # Second call: POST — succeeds with HTTP 201
            return MagicMock(returncode=0, stdout=json.dumps({"id": 42}), stderr="")

        with patch("fabrik.drivers.watchdog._has_repo_scope", return_value=True), \
             patch("subprocess.run", side_effect=fake_run):
            result = watchdog._push_deploy_key_to_github(
                owner="foo", repo="bar", title="fabrik-watchdog-deploy", pubkey=self.PUBKEY,
            )
        assert result["status"] == "registered"
        # GET + POST = 2 subprocess calls
        assert len(calls) == 2
        post_args = calls[1]
        assert "-X" in post_args and "POST" in post_args
        assert any("keys" in a for a in post_args)

    def test_post_422_treated_as_idempotent(self) -> None:
        """Race-free: another fabrik apply may have just registered the key."""
        calls = []

        def fake_run(args, **kw):
            calls.append(args)
            if "-X" in args and "POST" in args:
                return MagicMock(
                    returncode=1,
                    stdout="",
                    stderr=(
                        '{"message":"Validation Failed",'
                        '"errors":[{"resource":"PublicKey","code":"custom",'
                        '"message":"key is already in use"}]}'
                    ),
                )
            return MagicMock(returncode=0, stdout="[]", stderr="")

        with patch("fabrik.drivers.watchdog._has_repo_scope", return_value=True), \
             patch("subprocess.run", side_effect=fake_run):
            result = watchdog._push_deploy_key_to_github(
                owner="foo", repo="bar", title="fabrik-watchdog-deploy", pubkey=self.PUBKEY,
            )
        assert result["status"] == "idempotent"
        assert result.get("reason") == "key_already_in_use"

    def test_other_failure_falls_back_to_print(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A 500 (or any non-422 error) must NOT raise — falls back to
        print-pubkey path so the deploy can still proceed."""
        def fake_run(args, **kw):
            if "-X" in args and "POST" in args:
                return MagicMock(returncode=1, stdout="", stderr="500 Server Error")
            return MagicMock(returncode=0, stdout="[]", stderr="")

        with patch("fabrik.drivers.watchdog._has_repo_scope", return_value=True), \
             patch("subprocess.run", side_effect=fake_run), \
             caplog.at_level(logging.WARNING, logger="fabrik.drivers.watchdog"):
            result = watchdog._push_deploy_key_to_github(
                owner="foo", repo="bar", title="fabrik-watchdog-deploy", pubkey=self.PUBKEY,
            )
        assert result["status"] == "failed"
        assert any("fall" in r.message.lower() or "manual" in r.message.lower() for r in caplog.records)

    def test_subprocess_filenotfounderror_falls_back(self) -> None:
        """gh CLI not installed → don't crash."""
        with patch("fabrik.drivers.watchdog._has_repo_scope", return_value=True), \
             patch("subprocess.run", side_effect=FileNotFoundError):
            result = watchdog._push_deploy_key_to_github(
                owner="foo", repo="bar", title="fabrik-watchdog-deploy", pubkey=self.PUBKEY,
            )
        assert result["status"] == "failed"
