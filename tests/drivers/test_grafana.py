"""Unit tests for fabrik.drivers.grafana — mocked requests.

No network, no VPS required. The live contract is validated by
``scripts/probes/grafana_token_check.sh`` (Phase 4-pre Task 3) and the
Phase 4g live smoke (see plan file).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fabrik.drivers import grafana
from fabrik.drivers.grafana import (
    DEPLOYMENT_TAG,
    GRAFANA_URL,
    applies_to,
    delete_annotation,
    post_deployment_annotation,
)

# --------------------------------------------------------------------------- #
# applies_to — unconditional                                                   #
# --------------------------------------------------------------------------- #


class TestAppliesTo:
    def test_always_true_for_any_shape(self):
        assert applies_to({}) is True
        assert applies_to({"kind": "service"}) is True
        assert applies_to({"kind": "static-site"}) is True
        assert applies_to(None) is True


# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #


def _resp(status_code: int, json_body=None, text: str = "", content: bool = True):
    m = MagicMock()
    m.status_code = status_code
    m.text = text
    m.content = b"x" if content else b""
    m.json.return_value = json_body if json_body is not None else {}
    m.raise_for_status = MagicMock()
    if status_code >= 400:
        from requests.exceptions import HTTPError

        m.raise_for_status.side_effect = HTTPError(f"HTTP {status_code}")
    return m


@pytest.fixture
def fake_token(monkeypatch):
    monkeypatch.setenv("GRAFANA_SERVICE_ACCOUNT_TOKEN", "glsa_test-token-XYZ")


# --------------------------------------------------------------------------- #
# post_deployment_annotation                                                  #
# --------------------------------------------------------------------------- #


class TestPostDeploymentAnnotation:
    def test_dry_run_makes_no_network_calls(self, fake_token):
        with patch.object(grafana.requests, "post") as p:
            result = post_deployment_annotation("my-proj", dry_run=True)
        assert result == {
            "status": "dry_run",
            "project": "my-proj",
            "annotation_id": None,
        }
        p.assert_not_called()

    def test_missing_token_returns_skipped_no_raise(self, monkeypatch):
        monkeypatch.delenv("GRAFANA_SERVICE_ACCOUNT_TOKEN", raising=False)
        with patch.object(grafana.requests, "post") as p:
            result = post_deployment_annotation("my-proj")
        assert result["status"] == "skipped"
        assert result["reason"] == "no_token"
        assert result["annotation_id"] is None
        p.assert_not_called()

    def test_success_returns_annotation_id(self, fake_token):
        with patch.object(
            grafana.requests, "post", return_value=_resp(200, {"id": 42})
        ):
            result = post_deployment_annotation("my-proj")
        assert result == {
            "status": "created",
            "annotation_id": 42,
            "project": "my-proj",
        }

    def test_5xx_returns_failed_never_raises(self, fake_token):
        """Core non-fatal invariant: Grafana outages must NEVER break a deploy."""
        with patch.object(
            grafana.requests, "post", return_value=_resp(503, text="unavailable")
        ):
            result = post_deployment_annotation("my-proj")
        assert result["status"] == "failed"
        assert result["annotation_id"] is None
        assert "error" in result

    def test_network_exception_returns_failed(self, fake_token):
        import requests

        with patch.object(
            grafana.requests,
            "post",
            side_effect=requests.ConnectionError("DNS fail"),
        ):
            result = post_deployment_annotation("my-proj")
        assert result["status"] == "failed"
        assert "DNS fail" in result["error"]

    def test_missing_id_in_response_returns_failed(self, fake_token):
        """If Grafana ever changes shape and drops the id field, we must
        NOT return status=created with annotation_id=None — downstream
        delete_annotation would choke on a None id. Better to flag
        failure explicitly."""
        with patch.object(
            grafana.requests, "post", return_value=_resp(200, {"message": "ok"})
        ):
            result = post_deployment_annotation("my-proj")
        assert result["status"] == "failed"
        assert result["error"] == "no_id_in_response"

    def test_time_is_epoch_ms(self, fake_token):
        """Guardrail for the classic Grafana bug — seconds silently lands
        the annotation at epoch 0. We must pass MILLISECONDS."""
        captured = {}

        def fake_post(url, **kw):
            captured["body"] = kw.get("json")
            return _resp(200, {"id": 1})

        with patch.object(grafana.requests, "post", side_effect=fake_post), patch.object(
            grafana.time, "time", return_value=1700000000.123
        ):
            post_deployment_annotation("my-proj")
        # 1700000000 seconds → 1_700_000_000_123 ms
        assert captured["body"]["time"] == 1700000000123

    def test_default_tags_include_deployment_and_project_name(self, fake_token):
        captured = {}

        def fake_post(url, **kw):
            captured["body"] = kw.get("json")
            return _resp(200, {"id": 1})

        with patch.object(grafana.requests, "post", side_effect=fake_post):
            post_deployment_annotation("my-proj")
        assert captured["body"]["tags"] == [DEPLOYMENT_TAG, "my-proj"]

    def test_extra_tags_appended_deduplicated(self, fake_token):
        captured = {}

        def fake_post(url, **kw):
            captured["body"] = kw.get("json")
            return _resp(200, {"id": 1})

        with patch.object(grafana.requests, "post", side_effect=fake_post):
            post_deployment_annotation(
                "my-proj",
                extra_tags=["v2", "deployment", "my-proj", "canary"],  # dup + new
            )
        # "deployment" and "my-proj" already present — must not duplicate
        assert captured["body"]["tags"] == [
            DEPLOYMENT_TAG,
            "my-proj",
            "v2",
            "canary",
        ]

    def test_text_includes_domain_and_git_sha(self, fake_token):
        captured = {}

        def fake_post(url, **kw):
            captured["body"] = kw.get("json")
            return _resp(200, {"id": 1})

        with patch.object(grafana.requests, "post", side_effect=fake_post):
            post_deployment_annotation(
                "my-proj", domain="my.example.com", git_sha="abc1234567"
            )
        txt = captured["body"]["text"]
        assert "Deployed my-proj" in txt
        assert "(abc1234)" in txt  # first 7 chars
        assert "my.example.com" in txt

    def test_url_and_auth_header_correct(self, fake_token):
        captured = {}

        def fake_post(url, **kw):
            captured["url"] = url
            captured["headers"] = kw.get("headers")
            return _resp(200, {"id": 1})

        with patch.object(grafana.requests, "post", side_effect=fake_post):
            post_deployment_annotation("my-proj")
        assert captured["url"] == f"{GRAFANA_URL}/api/annotations"
        assert captured["headers"]["Authorization"] == "Bearer glsa_test-token-XYZ"
        assert captured["headers"]["Content-Type"] == "application/json"

    def test_token_not_in_body(self, fake_token):
        """Defense-in-depth: the token must live in the header, never in
        the request body (where it could be logged by the server)."""
        captured = {}

        def fake_post(url, **kw):
            captured["body"] = kw.get("json")
            return _resp(200, {"id": 1})

        with patch.object(grafana.requests, "post", side_effect=fake_post):
            post_deployment_annotation("my-proj")
        assert "glsa_test-token-XYZ" not in str(captured["body"])


# --------------------------------------------------------------------------- #
# delete_annotation                                                            #
# --------------------------------------------------------------------------- #


class TestDeleteAnnotation:
    def test_success_returns_true(self, fake_token):
        with patch.object(grafana.requests, "delete", return_value=_resp(200)):
            assert delete_annotation(42) is True

    def test_404_returns_true_rollback_idempotent(self, fake_token):
        """Double-rollback must not flip the return to False."""
        with patch.object(grafana.requests, "delete", return_value=_resp(404)):
            assert delete_annotation(42) is True

    def test_5xx_returns_false_no_raise(self, fake_token):
        with patch.object(grafana.requests, "delete", return_value=_resp(503)):
            assert delete_annotation(42) is False

    def test_network_error_returns_false(self, fake_token):
        import requests

        with patch.object(
            grafana.requests,
            "delete",
            side_effect=requests.ConnectionError("gone"),
        ):
            assert delete_annotation(42) is False

    def test_missing_token_returns_false(self, monkeypatch):
        monkeypatch.delenv("GRAFANA_SERVICE_ACCOUNT_TOKEN", raising=False)
        with patch.object(grafana.requests, "delete") as d:
            assert delete_annotation(42) is False
            d.assert_not_called()

    def test_dry_run_skips_http(self, fake_token):
        with patch.object(grafana.requests, "delete") as d:
            assert delete_annotation(42, dry_run=True) is True
            d.assert_not_called()

    def test_non_int_annotation_id_raises(self, fake_token):
        """Programming error — callers must pass the int id returned from
        post_deployment_annotation, never a string. We catch this at the
        boundary rather than silently 404ing the wrong URL."""
        with pytest.raises(TypeError, match="annotation_id must be int"):
            delete_annotation("42")  # type: ignore[arg-type]

    def test_delete_url_uses_id(self, fake_token):
        captured = {}

        def fake_del(url, **kw):
            captured["url"] = url
            return _resp(200)

        with patch.object(grafana.requests, "delete", side_effect=fake_del):
            delete_annotation(99)
        assert captured["url"] == f"{GRAFANA_URL}/api/annotations/99"

    def test_delete_omits_content_type_header(self, fake_token):
        """No JSON body on DELETE — Content-Type is unnecessary and would
        invite a spurious preflight on Grafana's side."""
        captured = {}

        def fake_del(url, **kw):
            captured["headers"] = kw.get("headers")
            return _resp(200)

        with patch.object(grafana.requests, "delete", side_effect=fake_del):
            delete_annotation(42)
        assert "Content-Type" not in captured["headers"]
        assert "Authorization" in captured["headers"]
