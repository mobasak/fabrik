"""Unit tests for fabrik.drivers.glitchtip — mocked requests + ssh.

No network, no VPS, no GlitchTip required. The live contract is covered
by the phase-4f live smoke (see plan file) and the probe script.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fabrik.drivers import glitchtip
from fabrik.drivers.glitchtip import (
    GLITCHTIP_URL,
    SERVICE_KINDS,
    SHAPE_FLAG,
    _validate_name,
    applies_to,
    create_project,
    delete_project,
    verify_dsn_injection,
)

# --------------------------------------------------------------------------- #
# applies_to                                                                   #
# --------------------------------------------------------------------------- #


class TestAppliesTo:
    def test_explicit_opt_in(self):
        assert applies_to({SHAPE_FLAG: True}) is True
        assert applies_to({SHAPE_FLAG: 1}) is True

    def test_explicit_opt_out_beats_kind_default(self):
        # kind=service would default to True — explicit False MUST win
        assert applies_to({SHAPE_FLAG: False, "kind": "service"}) is False
        assert applies_to({SHAPE_FLAG: None, "kind": "service"}) is False

    def test_kind_based_default_for_service_worker_wordpress(self):
        for kind in SERVICE_KINDS:
            assert applies_to({"kind": kind}) is True, f"should apply for {kind}"

    def test_static_site_and_other_kinds_default_false(self):
        for kind in ("static-site", "docusaurus", "chrome-extension", "mobile-app"):
            assert applies_to({"kind": kind}) is False, f"should NOT apply for {kind}"

    def test_empty_dict_is_false(self):
        assert applies_to({}) is False

    def test_non_dict_is_false(self):
        assert applies_to(None) is False  # type: ignore[arg-type]
        assert applies_to([]) is False  # type: ignore[arg-type]
        assert applies_to("has_error_tracking=true") is False  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# name validation                                                              #
# --------------------------------------------------------------------------- #


class TestValidateName:
    @pytest.mark.parametrize("name", ["a", "my-proj", "Proj_2026", "x" * 128])
    def test_valid(self, name):
        _validate_name(name)

    @pytest.mark.parametrize(
        "name",
        ["", "-leading", "_leading", "has space", "has.dot", "x" * 129, "'; drop"],
    )
    def test_invalid(self, name):
        with pytest.raises(ValueError):
            _validate_name(name)

    def test_non_string(self):
        with pytest.raises(ValueError):
            _validate_name(42)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# environment-var handling                                                     #
# --------------------------------------------------------------------------- #


class TestEnvHandling:
    def test_missing_auth_token_raises_with_remediation(self, monkeypatch):
        monkeypatch.delenv("GLITCHTIP_AUTH_TOKEN", raising=False)
        monkeypatch.setenv("GLITCHTIP_ORG_SLUG", "ocoron")
        monkeypatch.setenv("GLITCHTIP_TEAM_SLUG", "vps1")
        with pytest.raises(RuntimeError, match="GLITCHTIP_AUTH_TOKEN"):
            create_project("my-proj")

    def test_missing_org_or_team_raises(self, monkeypatch):
        monkeypatch.setenv("GLITCHTIP_AUTH_TOKEN", "t" * 40)
        monkeypatch.delenv("GLITCHTIP_ORG_SLUG", raising=False)
        monkeypatch.setenv("GLITCHTIP_TEAM_SLUG", "vps1")
        with pytest.raises(RuntimeError, match="GLITCHTIP_ORG_SLUG"):
            create_project("my-proj")

    def test_token_never_returned_from_headers_builder(self, monkeypatch):
        """Token must be in Authorization header only, never exposed via repr."""
        monkeypatch.setenv("GLITCHTIP_AUTH_TOKEN", "SUPER-SECRET-TOKEN-XYZ")
        h = glitchtip._headers()
        # The token lives in the auth header
        assert "SUPER-SECRET-TOKEN-XYZ" in h["Authorization"]
        # But no other fields leak it
        assert "SUPER-SECRET-TOKEN-XYZ" not in repr({k: v for k, v in h.items() if k != "Authorization"})


# --------------------------------------------------------------------------- #
# create_project                                                               #
# --------------------------------------------------------------------------- #


@pytest.fixture
def fake_env(monkeypatch):
    monkeypatch.setenv("GLITCHTIP_AUTH_TOKEN", "t" * 40)
    monkeypatch.setenv("GLITCHTIP_ORG_SLUG", "ocoron")
    monkeypatch.setenv("GLITCHTIP_TEAM_SLUG", "vps1")


def _resp(status_code: int, json_body=None, text: str = ""):
    m = MagicMock()
    m.status_code = status_code
    m.text = text
    m.json.return_value = json_body if json_body is not None else {}
    m.raise_for_status = MagicMock()
    if status_code >= 400:
        m.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return m


class TestCreateProject:
    def test_dry_run_makes_no_network_calls(self, fake_env):
        with patch.object(glitchtip.requests, "get") as g, patch.object(
            glitchtip.requests, "post"
        ) as p:
            result = create_project("my-proj", dry_run=True)
        assert result == {"status": "dry_run", "project": "my-proj", "dsn": None}
        g.assert_not_called()
        p.assert_not_called()

    def test_existing_project_returns_exists_with_dsn(self, fake_env):
        """Idempotency: GET 200 on project → skip POST, fetch DSN, return exists."""
        calls = []

        def fake_get(url, **_kw):
            calls.append(("GET", url))
            if url.endswith("/projects/ocoron/my-proj/"):
                return _resp(200, {"slug": "my-proj"})
            if url.endswith("/projects/ocoron/my-proj/keys/"):
                return _resp(200, [{"dsn": {"public": "http://abc@host/1"}}])
            return _resp(404)

        with patch.object(glitchtip.requests, "get", side_effect=fake_get), patch.object(
            glitchtip.requests, "post"
        ) as post:
            result = create_project("my-proj")
        assert result == {
            "status": "exists",
            "project": "my-proj",
            "dsn": "http://abc@host/1",
        }
        post.assert_not_called()
        # Exactly 2 GETs: existence check + keys fetch
        assert len(calls) == 2

    def test_missing_project_creates_and_returns_dsn(self, fake_env):
        def fake_get(url, **_kw):
            if url.endswith("/projects/ocoron/new-proj/"):
                return _resp(404)
            if url.endswith("/projects/ocoron/new-proj/keys/"):
                return _resp(200, [{"dsn": {"public": "http://new@host/2"}}])
            return _resp(500)

        def fake_post(url, **_kw):
            assert "teams/ocoron/vps1/projects" in url
            return _resp(201, {"slug": "new-proj"})

        with patch.object(glitchtip.requests, "get", side_effect=fake_get), patch.object(
            glitchtip.requests, "post", side_effect=fake_post
        ):
            result = create_project("new-proj")
        assert result == {
            "status": "created",
            "project": "new-proj",
            "dsn": "http://new@host/2",
        }

    def test_create_failure_raises(self, fake_env):
        def fake_get(url, **_kw):
            return _resp(404)

        def fake_post(url, **_kw):
            return _resp(500, text="server error")

        with patch.object(glitchtip.requests, "get", side_effect=fake_get), patch.object(
            glitchtip.requests, "post", side_effect=fake_post
        ):
            with pytest.raises(Exception, match="HTTP 500"):
                create_project("bad-proj")

    def test_empty_keys_raises_runtime_error(self, fake_env):
        def fake_get(url, **_kw):
            if url.endswith("/projects/ocoron/p/"):
                return _resp(200)
            if url.endswith("/projects/ocoron/p/keys/"):
                return _resp(200, [])  # empty — no auto-created key
            return _resp(404)

        with patch.object(glitchtip.requests, "get", side_effect=fake_get):
            with pytest.raises(RuntimeError, match="no client keys"):
                create_project("p")

    def test_missing_dsn_in_keys_payload_raises(self, fake_env):
        def fake_get(url, **_kw):
            if url.endswith("/projects/ocoron/p/"):
                return _resp(200)
            if url.endswith("/projects/ocoron/p/keys/"):
                return _resp(200, [{"id": "abc"}])  # no dsn field
            return _resp(404)

        with patch.object(glitchtip.requests, "get", side_effect=fake_get):
            with pytest.raises(RuntimeError, match="missing dsn.public"):
                create_project("p")

    def test_invalid_name_raises_before_any_http(self, fake_env):
        with patch.object(glitchtip.requests, "get") as g, patch.object(
            glitchtip.requests, "post"
        ) as p:
            with pytest.raises(ValueError):
                create_project("bad name")
            g.assert_not_called()
            p.assert_not_called()

    def test_existence_check_uses_correct_org_in_url(self, fake_env):
        """Wire-level check: URLs contain the org from env, not hardcoded."""
        captured = []

        def fake_get(url, **_kw):
            captured.append(url)
            return _resp(200, [{"dsn": {"public": "x"}}])

        with patch.object(glitchtip.requests, "get", side_effect=fake_get):
            create_project("p")
        assert all("/ocoron/" in url for url in captured), captured
        assert any("/api/0/projects/ocoron/p/" in url for url in captured)


# --------------------------------------------------------------------------- #
# delete_project (rollback semantics)                                          #
# --------------------------------------------------------------------------- #


class TestDeleteProject:
    def test_success_204_returns_true(self, fake_env):
        with patch.object(glitchtip.requests, "delete", return_value=_resp(204)):
            assert delete_project("p") is True

    def test_404_also_returns_true(self, fake_env):
        """Already-deleted projects must not fail the rollback path."""
        with patch.object(glitchtip.requests, "delete", return_value=_resp(404)):
            assert delete_project("p") is True

    def test_500_returns_false_no_raise(self, fake_env):
        with patch.object(glitchtip.requests, "delete", return_value=_resp(500)):
            assert delete_project("p") is False

    def test_network_exception_returns_false(self, fake_env):
        with patch.object(
            glitchtip.requests, "delete", side_effect=ConnectionError("boom")
        ):
            assert delete_project("p") is False

    def test_dry_run_skips_http(self, fake_env):
        with patch.object(glitchtip.requests, "delete") as d:
            assert delete_project("p", dry_run=True) is True
            d.assert_not_called()

    def test_invalid_name_raises_before_any_http(self, fake_env):
        with patch.object(glitchtip.requests, "delete") as d:
            with pytest.raises(ValueError):
                delete_project("bad name")
            d.assert_not_called()


# --------------------------------------------------------------------------- #
# verify_dsn_injection                                                         #
# --------------------------------------------------------------------------- #


class TestVerifyDsnInjection:
    def test_empty_expected_dsn_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            verify_dsn_injection("p", "")

    def test_matching_dsn_returns_true_on_first_attempt(self):
        calls = []

        def fake_ssh(cmd, **_kw):
            calls.append(cmd)
            if "docker ps" in cmd:
                return "myapp-uuid123"
            if "docker inspect" in cmd:
                return "http://abc@host/1"
            return ""

        with patch.object(glitchtip, "ssh", side_effect=fake_ssh):
            ok = verify_dsn_injection("myapp", "http://abc@host/1", max_wait=5)
        assert ok is True
        # Should have stopped after first success — 2 calls (ps + inspect)
        assert len(calls) == 2

    def test_scratch_image_uses_docker_inspect_not_exec(self):
        """Regression: ``traefik/whoami`` and other scratch/distroless
        images have no shell, so ``docker exec printenv`` fails with
        ``OCI runtime exec failed``. We must read the env var via
        ``docker inspect`` which is a daemon-side metadata read."""
        captured = []

        def fake_ssh(cmd, **_kw):
            captured.append(cmd)
            if "docker ps" in cmd:
                return "myapp-uuid123"
            if "docker inspect" in cmd:
                return "http://abc@host/1"
            return ""

        with patch.object(glitchtip, "ssh", side_effect=fake_ssh):
            ok = verify_dsn_injection("myapp", "http://abc@host/1", max_wait=5)
        assert ok is True
        # Must never call ``docker exec`` — that's the scratch-image bug.
        assert not any("docker exec" in c for c in captured), captured
        assert any("docker inspect" in c for c in captured)

    def test_wrong_dsn_then_correct_dsn_succeeds(self):
        """Simulates a Coolify redeploy where the container comes up with
        the OLD env briefly, then the correct one."""
        state = {"attempts": 0}

        def fake_ssh(cmd, **_kw):
            if "docker ps" in cmd:
                return "myapp-uuid123"
            if "docker inspect" in cmd:
                state["attempts"] += 1
                if state["attempts"] < 3:
                    return "http://OLD@host/1"
                return "http://NEW@host/2"
            return ""

        with patch.object(glitchtip, "ssh", side_effect=fake_ssh), patch.object(
            glitchtip.time, "sleep"
        ):
            ok = verify_dsn_injection(
                "myapp", "http://NEW@host/2", max_wait=60, poll_interval=0.01
            )
        assert ok is True

    def test_container_not_yet_running_retries(self):
        """During Coolify recreate the container may not exist for a bit."""
        state = {"polls": 0}

        def fake_ssh(cmd, **_kw):
            if "docker ps" in cmd:
                state["polls"] += 1
                return "" if state["polls"] < 3 else "myapp-uuid123"
            if "docker inspect" in cmd:
                return "http://abc@host/1"
            return ""

        with patch.object(glitchtip, "ssh", side_effect=fake_ssh), patch.object(
            glitchtip.time, "sleep"
        ):
            ok = verify_dsn_injection(
                "myapp", "http://abc@host/1", max_wait=60, poll_interval=0.01
            )
        assert ok is True

    def test_timeout_returns_false_never_raises(self):
        def fake_ssh(cmd, **_kw):
            return ""  # nothing ever comes up

        with patch.object(glitchtip, "ssh", side_effect=fake_ssh), patch.object(
            glitchtip.time, "sleep"
        ):
            # Use real time.time() — but very short max_wait
            ok = verify_dsn_injection(
                "myapp", "http://x", max_wait=0.1, poll_interval=0.01
            )
        assert ok is False

    def test_prefix_match_prevents_wrong_container(self):
        """Container name match must anchor with `^project-` so that an
        unrelated container (e.g. `other-myapp-1`) is not mistaken for
        ours — same guard gatus/backrest use."""
        captured = []

        def fake_ssh(cmd, **_kw):
            captured.append(cmd)
            if "docker ps" in cmd:
                return ""  # force at least one prefix-match call
            return ""

        with patch.object(glitchtip, "ssh", side_effect=fake_ssh), patch.object(
            glitchtip.time, "sleep"
        ):
            verify_dsn_injection(
                "myapp", "http://x", max_wait=0.05, poll_interval=0.01
            )
        ps_calls = [c for c in captured if "docker ps" in c]
        for c in ps_calls:
            # Allow both Coolify auto-name (``myapp-<uuid>``) and explicit
            # ``container_name: myapp`` (exact match). The regex anchors
            # the project name and then requires either a trailing dash
            # or end-of-line.
            assert "grep -E '^myapp(-|$)'" in c, c


# --------------------------------------------------------------------------- #
# URL/wire shape — defend against regressions in endpoint paths                #
# --------------------------------------------------------------------------- #


class TestWireShape:
    def test_create_url_matches_probe_contract(self, fake_env):
        """Must hit POST /api/0/teams/{org}/{team}/projects/ per
        docs/reference/apis/glitchtip-api.md §Endpoint 1."""
        captured = []

        def fake_get(url, **_kw):
            if url.endswith("/projects/ocoron/p/keys/"):
                return _resp(200, [{"dsn": {"public": "d"}}])
            return _resp(404)

        def fake_post(url, **kw):
            captured.append((url, kw.get("json")))
            return _resp(201)

        with patch.object(glitchtip.requests, "get", side_effect=fake_get), patch.object(
            glitchtip.requests, "post", side_effect=fake_post
        ):
            create_project("p", platform="python")
        assert captured, "POST not made"
        url, body = captured[0]
        assert url == f"{GLITCHTIP_URL}/api/0/teams/ocoron/vps1/projects/"
        assert body == {"name": "p", "platform": "python"}
