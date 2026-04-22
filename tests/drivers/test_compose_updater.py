"""Unit tests for ``fabrik.drivers.compose_updater``.

Covers the Plan §9 acceptance criterion at
``docs/development/plans/2026-04-18-zero-touch-deployment.md:2089``:

    compose_updater.update(uuid) branches on app.build_pack +
    app.git_repository. Git-sourced → temp-clone → surgical edit → commit →
    push → POST /deploy. Pure Coolify service → PATCH /services/{uuid}.
    Unit-tested with a mock Coolify returning both app kinds; wrong path
    raises AssertionError (§9).

Three resource kinds (the plan's "two app kinds" is colloquial — both
non-git paths share the same PATCH shape but hit different endpoints):

  * ``git_application``   — ``GET /applications/{uuid}`` returns a dict
    with ``git_repository`` set. Update via git-push + deploy re-trigger.
  * ``inline_application`` — ``GET /applications/{uuid}`` returns a dict
    with no/empty ``git_repository``. Update via
    ``PATCH /applications/{uuid}`` with base64 ``docker_compose_raw``.
  * ``service``           — ``GET /applications/{uuid}`` → 404, fall back
    to ``GET /services/{uuid}``. Update via ``PATCH /services/{uuid}``.

No network, no VPS, no Coolify. Every git subprocess is mocked; every
Coolify call is on a ``MagicMock``. The live contract will be exercised
by a Phase 4l integration smoke (follow-up) — this suite locks the
branching logic so a future refactor can't silently route the wrong way.
"""

from __future__ import annotations

import base64
import subprocess
from unittest.mock import MagicMock, patch

import httpx
import pytest

from fabrik.drivers.compose_updater import ComposeUpdater

# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #


@pytest.fixture
def git_app() -> dict:
    """A Coolify application backed by a git repo (build_pack=dockercompose)."""
    return {
        "uuid": "app-git-001",
        "name": "my-api",
        "git_repository": "https://github.com/mobasak/my-api.git",
        "git_branch": "main",
        "build_pack": "dockercompose",
        "docker_compose_location": "/docker-compose.yml",
        "fqdn": "https://api.vps1.ocoron.com",
    }


@pytest.fixture
def inline_app() -> dict:
    """A Coolify application with inline compose (no git)."""
    return {
        "uuid": "app-inline-001",
        "name": "my-inline-api",
        "git_repository": None,  # the discriminator — no git
        "git_branch": None,
        "build_pack": "dockercompose",
        "docker_compose_location": None,
        "fqdn": "https://inline.vps1.ocoron.com",
    }


@pytest.fixture
def coolify_service() -> dict:
    """A Coolify one-click service (different resource type than application)."""
    return {
        "uuid": "svc-001",
        "name": "my-service",
        "type": "postgresql",
    }


@pytest.fixture
def new_compose() -> str:
    return (
        "services:\n"
        "  app:\n"
        "    image: myapp:v2\n"
        "    platform: linux/amd64\n"
    )


def _mk_updater(
    coolify_mock: MagicMock | None = None, *, dry_run: bool = False
) -> tuple[ComposeUpdater, MagicMock]:
    coolify = coolify_mock or MagicMock()
    # Sensible default so ``deploy()`` returns a dict shape the code handles.
    coolify.deploy = MagicMock(return_value={"deployment_uuid": "deploy-xyz"})
    return ComposeUpdater(coolify=coolify, dry_run=dry_run), coolify


def _http_404() -> httpx.HTTPStatusError:
    """Build a realistic 404 that ``_classify`` inspects via
    ``e.response.status_code``. The real Coolify client raises this via
    ``response.raise_for_status()``."""
    req = httpx.Request("GET", "http://example/api/v1/applications/x")
    resp = httpx.Response(status_code=404, request=req)
    return httpx.HTTPStatusError("Not Found", request=req, response=resp)


# --------------------------------------------------------------------------- #
# Classification                                                              #
# --------------------------------------------------------------------------- #


class TestClassify:
    def test_application_with_git_repository_classified_as_git_application(
        self, git_app
    ) -> None:
        updater, coolify = _mk_updater()
        coolify.get_application = MagicMock(return_value=git_app)
        kind, data = updater._classify("app-git-001")
        assert kind == "git_application"
        assert data == git_app
        coolify.get_service.assert_not_called()

    def test_application_with_null_git_repository_classified_as_inline(
        self, inline_app
    ) -> None:
        updater, coolify = _mk_updater()
        coolify.get_application = MagicMock(return_value=inline_app)
        kind, _ = updater._classify("app-inline-001")
        assert kind == "inline_application"

    def test_application_with_empty_string_git_repository_classified_as_inline(
        self,
    ) -> None:
        """Coolify sometimes returns ``""`` instead of ``null`` — must be
        treated as "no git" (empty string is falsy, same as None)."""
        updater, coolify = _mk_updater()
        coolify.get_application = MagicMock(
            return_value={"uuid": "x", "git_repository": ""}
        )
        kind, _ = updater._classify("x")
        assert kind == "inline_application"

    def test_404_on_application_falls_back_to_service(self, coolify_service) -> None:
        updater, coolify = _mk_updater()
        coolify.get_application = MagicMock(side_effect=_http_404())
        coolify.get_service = MagicMock(return_value=coolify_service)
        kind, data = updater._classify("svc-001")
        assert kind == "service"
        assert data == coolify_service

    def test_non_404_http_error_on_application_is_re_raised(self) -> None:
        """500/403/etc. must NOT be swallowed — only 404 triggers service
        fallback. Anything else is a real API error the caller needs to see."""
        updater, coolify = _mk_updater()
        req = httpx.Request("GET", "http://x")
        resp = httpx.Response(status_code=500, request=req)
        err = httpx.HTTPStatusError("boom", request=req, response=resp)
        coolify.get_application = MagicMock(side_effect=err)
        with pytest.raises(httpx.HTTPStatusError):
            updater._classify("boom-uuid")
        coolify.get_service.assert_not_called()


# --------------------------------------------------------------------------- #
# Path: git_application (clone → edit → commit → push → deploy)                #
# --------------------------------------------------------------------------- #


class TestGitApplicationPath:
    def test_takes_git_path_and_never_patches(self, git_app, new_compose) -> None:
        updater, coolify = _mk_updater()
        coolify.get_application = MagicMock(return_value=git_app)

        with patch(
            "fabrik.drivers.compose_updater.subprocess.run"
        ) as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="abcdef123456\n", stderr=""
            )
            result = updater.update("app-git-001", new_compose)

        assert result.kind == "git_application"
        assert result.git_commit_sha == "abcdef123456"
        # Deploy is the final step — must be called exactly once.
        coolify.deploy.assert_called_once_with("app-git-001")
        # update_application (the inline-PATCH path) must NOT be called.
        coolify.update_application.assert_not_called()
        # Extract the git VERB from each call, skipping any ``-c key=value``
        # pairs between ``git`` and the verb (the commit call uses
        # ``git -c user.email=... -c user.name=... commit`` to avoid relying
        # on the local git config of whoever runs Fabrik).
        verbs_seen: list[str] = []
        for c in mock_run.call_args_list:
            argv = c.args[0]
            # Find the first non-``-c`` / non-``git`` token.
            i = 1
            while i < len(argv) and argv[i] in ("-c",):
                i += 2  # skip ``-c key=value`` pair
            if i < len(argv):
                verbs_seen.append(argv[i])
        assert verbs_seen == ["clone", "add", "commit", "rev-parse", "push"], (
            f"verb order drifted: {verbs_seen}"
        )

    def test_clone_uses_repo_and_branch_from_app_metadata(
        self, git_app, new_compose
    ) -> None:
        updater, coolify = _mk_updater()
        coolify.get_application = MagicMock(return_value=git_app)

        with patch("fabrik.drivers.compose_updater.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="sha\n", stderr=""
            )
            updater.update("app-git-001", new_compose)

        clone_call = mock_run.call_args_list[0]
        argv = clone_call.args[0]
        assert argv[:2] == ["git", "clone"]
        assert "-b" in argv and argv[argv.index("-b") + 1] == "main"
        assert git_app["git_repository"] in argv

    def test_push_targets_origin_and_correct_branch(self, git_app, new_compose) -> None:
        updater, coolify = _mk_updater()
        # Override with a non-default branch to ensure we aren't hard-coding ``main``.
        git_app["git_branch"] = "deploy"
        coolify.get_application = MagicMock(return_value=git_app)

        with patch("fabrik.drivers.compose_updater.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="sha\n", stderr=""
            )
            updater.update("app-git-001", new_compose)

        push_call = mock_run.call_args_list[-1]
        argv = push_call.args[0]
        assert argv[-3:] == ["push", "origin", "deploy"]

    def test_raises_runtime_error_on_git_subprocess_failure(
        self, git_app, new_compose
    ) -> None:
        updater, coolify = _mk_updater()
        coolify.get_application = MagicMock(return_value=git_app)

        with patch("fabrik.drivers.compose_updater.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["git", "clone"],
                returncode=128,
                stdout="",
                stderr="fatal: repository not found",
            )
            with pytest.raises(RuntimeError, match="repository not found"):
                updater.update("app-git-001", new_compose)

        coolify.deploy.assert_not_called()

    def test_private_git_method_asserts_on_non_git_app(self, inline_app, new_compose) -> None:
        """Contract lock: if a future refactor routes an inline-compose app
        through the git path by accident, AssertionError fires immediately
        rather than silently doing something wrong."""
        updater, _ = _mk_updater()
        with pytest.raises(AssertionError, match="non-git app"):
            updater._update_via_git(
                "app-inline-001", new_compose, inline_app, commit_message="x"
            )


# --------------------------------------------------------------------------- #
# Path: inline_application (PATCH /applications/{uuid})                        #
# --------------------------------------------------------------------------- #


class TestInlineApplicationPath:
    def test_takes_patch_path_and_never_invokes_git(self, inline_app, new_compose) -> None:
        updater, coolify = _mk_updater()
        coolify.get_application = MagicMock(return_value=inline_app)
        coolify.update_application = MagicMock(return_value={"ok": True})

        with patch("fabrik.drivers.compose_updater.subprocess.run") as mock_run:
            result = updater.update("app-inline-001", new_compose)

        assert result.kind == "inline_application"
        coolify.update_application.assert_called_once()
        coolify.deploy.assert_called_once_with("app-inline-001")
        mock_run.assert_not_called()  # no git

    def test_patch_body_carries_base64_encoded_compose(
        self, inline_app, new_compose
    ) -> None:
        """LESSONS_LEARNT §1 — Coolify rejects plain YAML with HTTP 422.
        The compose_raw field must be base64-encoded at the boundary."""
        updater, coolify = _mk_updater()
        coolify.get_application = MagicMock(return_value=inline_app)
        coolify.update_application = MagicMock(return_value={"ok": True})

        updater.update("app-inline-001", new_compose)

        call_kwargs = coolify.update_application.call_args
        (uuid_arg,) = call_kwargs.args
        assert uuid_arg == "app-inline-001"
        b64_sent = call_kwargs.kwargs["docker_compose_raw"]
        assert base64.b64decode(b64_sent).decode() == new_compose, (
            "docker_compose_raw must be valid base64 that round-trips to the "
            "original YAML — Coolify rejects plain YAML with HTTP 422."
        )

    def test_private_patch_method_asserts_on_git_app(self, git_app, new_compose) -> None:
        """Contract lock: wrong-path regression guard for the other direction."""
        updater, _ = _mk_updater()
        with pytest.raises(AssertionError, match="git-sourced app"):
            updater._patch_application_compose(
                "app-git-001", new_compose, git_app
            )


# --------------------------------------------------------------------------- #
# Path: service (PATCH /services/{uuid})                                       #
# --------------------------------------------------------------------------- #


class TestServicePath:
    def test_404_on_application_then_service_path_takes_patch(
        self, coolify_service, new_compose
    ) -> None:
        updater, coolify = _mk_updater()
        coolify.get_application = MagicMock(side_effect=_http_404())
        coolify.get_service = MagicMock(return_value=coolify_service)
        coolify.update_service = MagicMock(return_value={"ok": True})

        with patch("fabrik.drivers.compose_updater.subprocess.run") as mock_run:
            result = updater.update("svc-001", new_compose)

        assert result.kind == "service"
        coolify.update_service.assert_called_once()
        coolify.deploy.assert_called_once_with("svc-001")
        coolify.update_application.assert_not_called()
        mock_run.assert_not_called()  # no git

    def test_service_patch_body_is_base64(self, coolify_service, new_compose) -> None:
        updater, coolify = _mk_updater()
        coolify.get_application = MagicMock(side_effect=_http_404())
        coolify.get_service = MagicMock(return_value=coolify_service)
        coolify.update_service = MagicMock(return_value={"ok": True})

        updater.update("svc-001", new_compose)

        call_args = coolify.update_service.call_args
        (uuid_arg,) = call_args.args
        assert uuid_arg == "svc-001"
        b64_sent = call_args.kwargs["docker_compose_raw"]
        assert base64.b64decode(b64_sent).decode() == new_compose


# --------------------------------------------------------------------------- #
# Dry-run: all three paths must be no-ops                                     #
# --------------------------------------------------------------------------- #


class TestDryRun:
    def test_dry_run_git_path_never_runs_git_or_deploys(
        self, git_app, new_compose
    ) -> None:
        updater, coolify = _mk_updater(dry_run=True)
        coolify.get_application = MagicMock(return_value=git_app)

        with patch("fabrik.drivers.compose_updater.subprocess.run") as mock_run:
            result = updater.update("app-git-001", new_compose)

        assert result.dry_run is True
        assert result.kind == "git_application"
        mock_run.assert_not_called()
        coolify.deploy.assert_not_called()

    def test_dry_run_inline_path_never_patches_or_deploys(
        self, inline_app, new_compose
    ) -> None:
        updater, coolify = _mk_updater(dry_run=True)
        coolify.get_application = MagicMock(return_value=inline_app)

        result = updater.update("app-inline-001", new_compose)

        assert result.dry_run is True
        assert result.kind == "inline_application"
        coolify.update_application.assert_not_called()
        coolify.deploy.assert_not_called()

    def test_dry_run_service_path_never_patches_or_deploys(
        self, coolify_service, new_compose
    ) -> None:
        updater, coolify = _mk_updater(dry_run=True)
        coolify.get_application = MagicMock(side_effect=_http_404())
        coolify.get_service = MagicMock(return_value=coolify_service)

        result = updater.update("svc-001", new_compose)

        assert result.dry_run is True
        assert result.kind == "service"
        # ``update_service`` must not be called — but ``get_application`` +
        # ``get_service`` MUST be (we still classify, just don't mutate).
        coolify.get_application.assert_called_once()
        coolify.get_service.assert_called_once()
        coolify.deploy.assert_not_called()


# --------------------------------------------------------------------------- #
# Assertion-based wrong-path guard (plan §9 explicit requirement)              #
# --------------------------------------------------------------------------- #


class TestWrongPathRaisesAssertionError:
    """Plan §9: 'wrong path raises AssertionError'. Both private path methods
    must refuse to run against the wrong resource kind — cheap insurance
    against future refactors that shuffle the classify → dispatch wiring."""

    def test_git_method_rejects_inline_app(self, inline_app, new_compose) -> None:
        updater, _ = _mk_updater()
        with pytest.raises(AssertionError):
            updater._update_via_git(
                "app-inline-001", new_compose, inline_app, commit_message="x"
            )

    def test_inline_method_rejects_git_app(self, git_app, new_compose) -> None:
        updater, _ = _mk_updater()
        with pytest.raises(AssertionError):
            updater._patch_application_compose(
                "app-git-001", new_compose, git_app
            )
