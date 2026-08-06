"""Driver tests for CoolifyClient."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from fabrik.drivers.coolify import CoolifyClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("COOLIFY_API_URL", "https://coolify.test")
    monkeypatch.setenv("COOLIFY_API_TOKEN", "test-token")
    c = CoolifyClient()
    c._resolve_resource_base = MagicMock(return_value="applications")
    return c


class TestBulkUpdateEnvVarsUpsert:
    """Regression for G8 (DEPLOYMENT.md §9.9): noisy 409 on every re-apply.

    Pre-fix: bulk_update_env_vars always POSTed, then caught 409 and PATCHed.
    Every re-apply logged ERRORs even on success. Fix: fetch existing envs,
    pick POST or PATCH per key, avoid the 409 entirely.
    """

    def test_picks_patch_for_existing_keys_post_for_new(self, client):
        """GET returns one existing key → PATCH for it, POST for the new key."""
        calls = []

        def fake_request(method, endpoint, **kwargs):
            calls.append((method, endpoint, kwargs.get("json")))
            if method == "GET":
                return [{"key": "EXISTING", "value": "old"}]
            return {}

        with patch.object(client, "_request", side_effect=fake_request):
            result = client.bulk_update_env_vars("app-uuid", {"EXISTING": "new", "BRAND_NEW": "v"})

        assert result == {"created": 1, "updated": 1}
        methods = [c[0] for c in calls]
        assert methods[0] == "GET"
        patches = [c for c in calls if c[0] == "PATCH"]
        posts = [c for c in calls if c[0] == "POST"]
        assert len(patches) == 1 and patches[0][2]["key"] == "EXISTING"
        assert len(posts) == 1 and posts[0][2]["key"] == "BRAND_NEW"

    def test_409_on_post_still_falls_back_to_patch(self, client):
        """If the pre-fetch GET fails, POST-then-PATCH-on-409 path still works."""

        def fake_request(method, endpoint, **kwargs):
            if method == "GET":
                raise httpx.HTTPStatusError(
                    "fetch failed",
                    request=MagicMock(),
                    response=MagicMock(status_code=500),
                )
            if method == "POST":
                raise httpx.HTTPStatusError(
                    "conflict",
                    request=MagicMock(),
                    response=MagicMock(status_code=409),
                )
            return {}

        with patch.object(client, "_request", side_effect=fake_request):
            result = client.bulk_update_env_vars("app-uuid", {"KEY1": "v"})

        assert result == {"created": 0, "updated": 1}
