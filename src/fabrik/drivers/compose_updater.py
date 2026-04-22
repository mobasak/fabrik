"""Compose YAML updater for Coolify-managed resources.

Plan §9 / acceptance criterion at
``docs/development/plans/2026-04-18-zero-touch-deployment.md:2089``:

    compose_updater.update(uuid) branches on app.build_pack +
    app.git_repository. Git-sourced → temp-clone → surgical edit → commit
    → push → POST /deploy. Pure Coolify service → PATCH /services/{uuid}.
    Unit-tested with a mock Coolify returning both app kinds; wrong path
    raises AssertionError.

Why this module exists
----------------------
Coolify stores compose YAML in two fundamentally different places depending
on how an application was created:

1. **Git-sourced applications** — the compose file lives in the user's git
   repo (GitHub / GitLab). Coolify clones on every deploy. A direct
   ``PATCH /applications/{uuid}`` with ``docker_compose_raw`` would be
   silently overwritten by the next git sync. The ONLY way to change the
   compose for these is to push a new commit upstream and trigger a
   redeploy.

2. **Inline-compose applications** — created via
   ``POST /applications/dockercompose`` with ``docker_compose_raw``. No
   git repo. Coolify stores the compose in its own DB and uses it verbatim.
   Update via ``PATCH /applications/{uuid}`` with the new base64-encoded
   compose.

3. **One-click services** — created via ``POST /services``. Separate
   resource type than applications. Update via ``PATCH /services/{uuid}``.

Choosing the wrong path is a silent-failure class of bug: PATCH on a
git-sourced app appears to succeed (HTTP 200) but the change evaporates
on next deploy. This module routes correctly AND asserts its private path
methods aren't called for the wrong resource kind, so a future refactor
that shuffles the dispatch wiring fails loudly in tests rather than
silently in production.

Base64 contract
---------------
Coolify rejects plain YAML in ``docker_compose_raw`` with HTTP 422
(``docs/LESSONS_LEARNT.md §1``). Both PATCH paths base64-encode at the
boundary so callers pass plain YAML and don't have to remember the quirk.

Dependencies
------------
* :class:`fabrik.drivers.coolify.CoolifyClient` for the HTTP API
* ``subprocess.run`` + ``git`` binary on PATH for the git path
* ``tempfile.TemporaryDirectory`` for the clone — always cleaned up, even
  if ``git push`` fails mid-flight (context-manager semantics)
"""

from __future__ import annotations

import base64
import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx

from fabrik.drivers.coolify import CoolifyClient

logger = logging.getLogger(__name__)

ResourceKind = Literal["git_application", "inline_application", "service"]

_GIT_CLONE_TIMEOUT = 120  # seconds — clone one repo; generous but bounded
_GIT_COMMIT_TIMEOUT = 30
_GIT_PUSH_TIMEOUT = 120  # allow for large-repo push over thin uplink

_DEFAULT_COMPOSE_LOCATION = "/docker-compose.yml"

# Identity used for the commit. Kept as constants so a future "who touched
# the repo" audit has a stable grep-target. These MUST be valid RFC 5322
# email + name — git refuses otherwise.
_FABRIK_GIT_EMAIL = "fabrik@ocoron.com"
_FABRIK_GIT_NAME = "Fabrik Bot"


@dataclass(frozen=True)
class UpdateResult:
    """Structured return of :meth:`ComposeUpdater.update`.

    Attributes:
        kind: Which of the three resource-kind paths was taken.
        path_taken: Short human-readable description for log output.
        deployment_uuid: UUID of the Coolify deployment triggered by the
            update, if one was returned by ``coolify.deploy()``. May be
            ``None`` if the deploy endpoint returned an unexpected shape
            — check logs in that case; the update itself still succeeded.
        git_commit_sha: SHA of the commit pushed upstream (git path only).
        dry_run: True if this was a ``dry_run=True`` invocation. No
            mutations were performed — neither git push nor Coolify PATCH.
    """

    kind: ResourceKind
    path_taken: str
    deployment_uuid: str | None = None
    git_commit_sha: str | None = None
    dry_run: bool = False


class ComposeUpdater:
    """Pushes a new compose YAML to a Coolify-managed resource.

    Example:
        >>> updater = ComposeUpdater(coolify=CoolifyClient())  # doctest: +SKIP
        >>> result = updater.update("app-uuid-123", new_compose_yaml)  # doctest: +SKIP
        >>> result.kind  # doctest: +SKIP
        'git_application'

    The update is performed in-place — no explicit rollback. If the caller
    needs rollback semantics, record the prior compose before calling and
    invoke ``update`` again with the old value.
    """

    def __init__(
        self,
        coolify: CoolifyClient,
        *,
        dry_run: bool = False,
    ) -> None:
        self.coolify = coolify
        self.dry_run = dry_run

    # ====================================================================== #
    # Public entry point                                                     #
    # ====================================================================== #

    def update(
        self,
        uuid: str,
        new_compose: str,
        *,
        commit_message: str = "fabrik: update compose",
    ) -> UpdateResult:
        """Update the compose for a Coolify application or service.

        Routes to the correct endpoint based on resource kind. See module
        docstring for the three-path model.

        Args:
            uuid: Coolify resource UUID (application OR service).
            new_compose: Full compose YAML as a string. Base64 encoding
                is applied internally for PATCH paths — callers pass
                plain YAML.
            commit_message: Git commit message for the ``git_application``
                path. Ignored for PATCH paths.

        Returns:
            :class:`UpdateResult` describing which path was taken.

        Raises:
            httpx.HTTPStatusError: Non-404 HTTP error from Coolify during
                resource classification, or any HTTP error during PATCH.
            RuntimeError: A git subprocess failed (non-zero exit).
            AssertionError: Internal consistency error — a private path
                method was called against the wrong resource kind.
        """
        kind, data = self._classify(uuid)

        if kind == "git_application":
            return self._update_via_git(uuid, new_compose, data, commit_message=commit_message)
        if kind == "inline_application":
            return self._patch_application_compose(uuid, new_compose, data)
        if kind == "service":
            return self._patch_service_compose(uuid, new_compose, data)

        # Unreachable under the Literal type, but belt-and-braces guard
        # so a future kind added to the enum without a dispatch entry
        # fails loudly instead of returning None.
        raise AssertionError(  # pragma: no cover
            f"Unknown Coolify resource kind for uuid={uuid!r}: {kind!r}"
        )

    # ====================================================================== #
    # Classification                                                          #
    # ====================================================================== #

    def _classify(self, uuid: str) -> tuple[ResourceKind, dict[str, Any]]:
        """Determine which of the three paths applies to ``uuid``.

        Algorithm:
            1. ``GET /applications/{uuid}``. If 200 → application; check
               ``git_repository`` to sub-classify as git vs inline.
            2. If 404 → fall back to ``GET /services/{uuid}``. Services
               have no git; they're always the PATCH path.
            3. Any other HTTP error (500 / 403 / …) — re-raise. This is
               NOT a classification signal; it's a real API failure the
               caller needs to see unswallowed.

        The ``git_repository`` discriminator treats empty string the same
        as ``None`` — Coolify sometimes returns ``""`` for "no git", and
        an empty-string repo URL would fail a clone anyway.
        """
        try:
            app = self.coolify.get_application(uuid)
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                raise
            # 404 on /applications/ → try /services/
            svc = self.coolify.get_service(uuid)
            return ("service", svc)

        if app.get("git_repository"):
            return ("git_application", app)
        return ("inline_application", app)

    # ====================================================================== #
    # Path: git_application (clone → edit → commit → push → deploy)           #
    # ====================================================================== #

    def _update_via_git(
        self,
        uuid: str,
        new_compose: str,
        app: dict[str, Any],
        *,
        commit_message: str,
    ) -> UpdateResult:
        """Clone → write compose → commit → push → trigger Coolify deploy.

        Contract: only for git-sourced applications. The assertion guards
        against future refactors that accidentally route an inline-compose
        app here — the PATCH would be silently overwritten on next deploy.
        """
        assert app.get("git_repository"), (
            f"_update_via_git called on non-git app uuid={uuid!r}: "
            f"git_repository={app.get('git_repository')!r}"
        )
        repo_url = app["git_repository"]
        branch = app.get("git_branch") or "main"
        # ``docker_compose_location`` is an absolute-looking path in the
        # Coolify schema (e.g. ``/docker-compose.yml``). Strip the leading
        # slash so we can join it onto the clone tmpdir without Path
        # treating it as an absolute override.
        compose_location = (app.get("docker_compose_location") or _DEFAULT_COMPOSE_LOCATION).lstrip(
            "/"
        )

        if self.dry_run:
            logger.info(
                "[DRY RUN] compose_updater.git: clone %s@%s, write %s, push, deploy %s",
                repo_url,
                branch,
                compose_location,
                uuid,
            )
            return UpdateResult(
                kind="git_application",
                path_taken=f"dry-run git push → deploy for {repo_url}@{branch}",
                dry_run=True,
            )

        with tempfile.TemporaryDirectory(prefix="fabrik-compose-") as tmp_str:
            tmp = Path(tmp_str)
            # Shallow clone keeps the tmpdir small. ``--depth=1`` is safe
            # because we only need to compose-edit + commit on top of HEAD;
            # we don't need history.
            self._run_git(
                ["git", "clone", "--depth=1", "-b", branch, repo_url, str(tmp)],
                cwd=None,
                timeout=_GIT_CLONE_TIMEOUT,
            )

            target = tmp / compose_location
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(new_compose, encoding="utf-8")

            # ``git add`` is a no-op if the file is unchanged — intentional.
            # A subsequent ``git commit`` with no staged changes would fail,
            # so we pass through to commit and let git decide. For now we
            # don't bother with a "no-change" short-circuit because the
            # caller is expected to only invoke us when the compose HAS
            # actually changed.
            self._run_git(
                ["git", "add", str(target.relative_to(tmp))],
                cwd=str(tmp),
                timeout=_GIT_COMMIT_TIMEOUT,
            )
            # ``-c key=value`` passes config to this git invocation only —
            # does NOT pollute the user's global git config. Essential for
            # agent-driven runs where no default identity is set.
            self._run_git(
                [
                    "git",
                    "-c",
                    f"user.email={_FABRIK_GIT_EMAIL}",
                    "-c",
                    f"user.name={_FABRIK_GIT_NAME}",
                    "commit",
                    "-m",
                    commit_message,
                ],
                cwd=str(tmp),
                timeout=_GIT_COMMIT_TIMEOUT,
            )
            sha = self._run_git(
                ["git", "rev-parse", "HEAD"],
                cwd=str(tmp),
                timeout=_GIT_COMMIT_TIMEOUT,
            ).strip()
            self._run_git(
                ["git", "push", "origin", branch],
                cwd=str(tmp),
                timeout=_GIT_PUSH_TIMEOUT,
            )

        # Trigger Coolify to pull the new HEAD. The API returns a dict
        # with ``deployment_uuid`` on success; shape varies if the user's
        # Coolify is mid-upgrade, so we .get() defensively.
        deploy_result = self.coolify.deploy(uuid)
        deployment_uuid = (
            deploy_result.get("deployment_uuid") if isinstance(deploy_result, dict) else None
        )
        return UpdateResult(
            kind="git_application",
            path_taken=f"git clone→edit→commit→push→deploy for {repo_url}@{branch}",
            deployment_uuid=deployment_uuid,
            git_commit_sha=sha,
        )

    # ====================================================================== #
    # Path: inline_application (PATCH /applications/{uuid})                   #
    # ====================================================================== #

    def _patch_application_compose(
        self, uuid: str, new_compose: str, app: dict[str, Any]
    ) -> UpdateResult:
        """PATCH /applications/{uuid} with base64-encoded docker_compose_raw.

        Contract: only for inline-compose applications (no git). The
        assertion guards against routing a git-sourced app here — the
        PATCH would appear to succeed but the change would be erased on
        the next git-triggered deploy.
        """
        assert not app.get("git_repository"), (
            f"_patch_application_compose called on git-sourced app uuid={uuid!r}: "
            f"git_repository={app.get('git_repository')!r}. "
            f"Git-sourced apps require the push-and-deploy path — a direct "
            f"PATCH will be silently overwritten on next deploy."
        )

        b64 = base64.b64encode(new_compose.encode("utf-8")).decode("ascii")

        if self.dry_run:
            logger.info(
                "[DRY RUN] compose_updater.inline: PATCH /applications/%s "
                "docker_compose_raw=<%d bytes base64>",
                uuid,
                len(b64),
            )
            return UpdateResult(
                kind="inline_application",
                path_taken=f"dry-run PATCH /applications/{uuid} → deploy",
                dry_run=True,
            )

        self.coolify.update_application(uuid, docker_compose_raw=b64)
        deploy_result = self.coolify.deploy(uuid)
        deployment_uuid = (
            deploy_result.get("deployment_uuid") if isinstance(deploy_result, dict) else None
        )
        return UpdateResult(
            kind="inline_application",
            path_taken=f"PATCH /applications/{uuid} → deploy",
            deployment_uuid=deployment_uuid,
        )

    # ====================================================================== #
    # Path: service (PATCH /services/{uuid})                                  #
    # ====================================================================== #

    def _patch_service_compose(
        self, uuid: str, new_compose: str, service: dict[str, Any]
    ) -> UpdateResult:
        """PATCH /services/{uuid} with base64-encoded docker_compose_raw.

        Services are structurally distinct from applications in Coolify's
        data model — they live under ``/services/`` and have their own
        start/stop/restart endpoints. A service never has ``git_repository``
        (the field doesn't exist on the service schema), so there's no
        assertion here — the ``service`` classification itself guarantees
        we're in the right place.
        """
        del service  # unused — classification already confirmed kind

        b64 = base64.b64encode(new_compose.encode("utf-8")).decode("ascii")

        if self.dry_run:
            logger.info(
                "[DRY RUN] compose_updater.service: PATCH /services/%s "
                "docker_compose_raw=<%d bytes base64>",
                uuid,
                len(b64),
            )
            return UpdateResult(
                kind="service",
                path_taken=f"dry-run PATCH /services/{uuid} → deploy",
                dry_run=True,
            )

        self.coolify.update_service(uuid, docker_compose_raw=b64)
        deploy_result = self.coolify.deploy(uuid)
        deployment_uuid = (
            deploy_result.get("deployment_uuid") if isinstance(deploy_result, dict) else None
        )
        return UpdateResult(
            kind="service",
            path_taken=f"PATCH /services/{uuid} → deploy",
            deployment_uuid=deployment_uuid,
        )

    # ====================================================================== #
    # Internal helpers                                                        #
    # ====================================================================== #

    def _run_git(self, args: list[str], *, cwd: str | None, timeout: int) -> str:
        """Invoke ``git`` via subprocess; raise on non-zero exit.

        Kept as a method (not a module-level function) so tests can patch
        ``fabrik.drivers.compose_updater.subprocess.run`` to a single
        place, and so a future subclass could substitute an in-process
        git library (``pygit2``, ``dulwich``) without touching callers.
        """
        logger.debug("git: %s (cwd=%s)", " ".join(args), cwd)
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git {args[1] if len(args) > 1 else '<?>'} failed "
                f"(rc={result.returncode}): {result.stderr.strip()}"
            )
        return result.stdout
