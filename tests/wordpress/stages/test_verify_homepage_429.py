"""Tests for homepage 404 + 429 rate-limiting fixes in the deploy pipeline.

Covers:
  1. pages.py:find_page() — empty-slug guard prevents false-positive match
  2. pages.py:create_all() — stores homepage under both "" and actual slug keys
  3. stages/pages.py — homepage lookup finds the page via "home" key
  4. stages/plugins.py — Wordfence whitelist uses wp eval with wfConfig PHP API
  5. stages/verify.py — 429 retry with exponential backoff
"""

import json
from unittest.mock import MagicMock, call, patch

import httpx
import pytest

from fabrik.wordpress.pages import CreatedPage, PageCreator
from fabrik.wordpress.stages import pages as pages_stage
from fabrik.wordpress.stages import plugins as plugins_stage
from fabrik.wordpress.stages import verify as verify_stage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_wp():
    """Mock WordPressClient for testing."""
    from fabrik.drivers.wordpress import WordPressClient

    wp = MagicMock(spec=WordPressClient)
    wp.plugin_list.return_value = []
    wp.run.return_value = ""
    return wp


@pytest.fixture
def mock_api():
    """Mock WordPressAPIClient for testing."""
    from fabrik.drivers.wordpress_api import WordPressAPIClient

    return MagicMock(spec=WordPressAPIClient)


@pytest.fixture
def minimal_spec():
    """Minimal spec for stages."""
    return {
        "site": {"name": "test-site", "domain": "test.example.com"},
        "deployment": {"vps_ip": "192.0.2.1"},
        "seo": {},
        "contact": {},
        "navigation": {},
        "dry_run": True,
    }


# ---------------------------------------------------------------------------
# 1. find_page empty-slug guard
# ---------------------------------------------------------------------------


class TestFindPageEmptySlug:
    """find_page('') must NOT send ?slug= to the REST API (returns all pages)."""

    def test_empty_slug_searches_for_home(self, mock_wp, mock_api):
        """find_page('') delegates to find_page('home')."""
        # REST API returns a page when queried with slug="home"
        mock_api._request.return_value = [
            {
                "id": 42,
                "title": {"rendered": "Home"},
                "slug": "home",
                "link": "https://test.example.com/",
            }
        ]

        creator = PageCreator("test-site", wp_client=mock_wp, api_client=mock_api)
        result = creator.find_page("")

        assert result is not None
        assert result.id == 42
        assert result.slug == "home"
        # REST API must have been called with slug="home", not slug=""
        mock_api._request.assert_called_once_with("GET", "/pages", params={"slug": "home"})

    def test_empty_slug_returns_none_when_no_home(self, mock_wp, mock_api):
        """find_page('') returns None if no 'home' page exists."""
        mock_api._request.return_value = []

        creator = PageCreator("test-site", wp_client=mock_wp, api_client=mock_api)
        result = creator.find_page("")

        assert result is None


# ---------------------------------------------------------------------------
# 2. create_all stores homepage under both "" and actual slug
# ---------------------------------------------------------------------------


class TestCreateAllHomepageKeys:
    """create_all stores homepage under both '' and the WordPress-assigned slug."""

    def test_homepage_stored_under_empty_and_actual_slug(self, mock_wp, mock_api):
        """A page with spec slug='' should be stored under both '' and its actual slug."""
        # find_page("home") returns None — page doesn't exist yet
        mock_api._request.side_effect = [
            [],  # find_page("home") → no existing page
            {  # create page POST (WordPress auto-assigns slug "home")
                "id": 99,
                "title": {"rendered": "Home"},
                "slug": "home",
                "link": "https://test.example.com/",
            },
        ]

        creator = PageCreator("test-site", wp_client=mock_wp, api_client=mock_api)
        pages = [{"slug": "", "title": "Home", "content": "<p>Welcome</p>"}]

        result = creator.create_all(pages)

        # Must have both keys
        assert "" in result
        assert "home" in result
        assert result[""].id == 99
        assert result["home"].id == 99

    def test_non_empty_slug_stored_under_slug_only(self, mock_wp, mock_api):
        """A page with a non-empty slug should NOT get a duplicate '' key."""
        mock_api._request.side_effect = [
            [],  # find_page("about") → no existing page
            {  # create page POST
                "id": 50,
                "title": {"rendered": "About"},
                "slug": "about",
                "link": "https://test.example.com/about",
            },
        ]

        creator = PageCreator("test-site", wp_client=mock_wp, api_client=mock_api)
        pages = [{"slug": "about", "title": "About", "content": ""}]

        result = creator.create_all(pages)

        assert "about" in result
        assert "" not in result


# ---------------------------------------------------------------------------
# 3. stages/pages.py — homepage lookup + cache_flush
# ---------------------------------------------------------------------------


class TestPagesStageHomepageLookup:
    """stages/pages.py correctly sets homepage via 'home' key and flushes caches."""

    @patch("fabrik.wordpress.stages.pages.generate_pages")
    @patch("fabrik.wordpress.stages.pages.PageCreator")
    def test_homepage_set_from_home_key(
        self, mock_creator_cls, mock_generate, minimal_spec, mock_wp, mock_api, tmp_path
    ):
        """When pages_created has 'home' key (not ''), homepage is still found."""
        spec = {**minimal_spec, "dry_run": False}
        mock_generate.return_value = [
            {"slug": "", "title": "Home", "content": "<p>Welcome</p>"},
        ]

        home_page = CreatedPage(id=99, title="Home", slug="home", url="https://test.example.com/")
        mock_creator = MagicMock()
        # create_all returns page under both keys (our fix)
        mock_creator.create_all.return_value = {"": home_page, "home": home_page}
        mock_creator_cls.return_value = mock_creator

        result = pages_stage.apply(spec, mock_wp, mock_api, tmp_path)

        assert result.success
        mock_creator.set_homepage.assert_called_once_with(99)
        mock_wp.rewrite_flush.assert_called_once()
        mock_wp.cache_flush.assert_called_once()


# ---------------------------------------------------------------------------
# 4. stages/plugins.py — Wordfence whitelist uses wp eval
# ---------------------------------------------------------------------------


class TestWordfenceWhitelist:
    """Wordfence IP whitelist uses wp eval with wfConfig PHP API."""

    def _write_manifest(self, tmp_path, entries):
        manifests_dir = tmp_path / "manifests"
        manifests_dir.mkdir(parents=True, exist_ok=True)
        (manifests_dir / "plugins.json").write_text(json.dumps(entries), encoding="utf-8")

    def test_whitelist_uses_wp_eval(self, minimal_spec, mock_wp, mock_api, tmp_path):
        """When Wordfence is active, wp eval is called with wfConfig PHP code."""
        mock_wp.plugin_list.return_value = [{"name": "wordfence", "status": "active"}]
        mock_wp.run.return_value = "added"
        self._write_manifest(tmp_path, [])

        spec = {**minimal_spec, "dry_run": False}
        result = plugins_stage.apply(spec, mock_wp, mock_api, tmp_path)

        assert result.success
        # First wp.run call after plugin_list should be `eval ...`
        eval_calls = [c for c in mock_wp.run.call_args_list if "eval" in str(c)]
        assert len(eval_calls) == 1
        call_str = str(eval_calls[0])
        assert "wfConfig" in call_str
        assert "whitelistedIPs" in call_str

    def test_whitelist_uses_vps_ip_from_spec(self, minimal_spec, mock_wp, mock_api, tmp_path):
        """VPS IP is read from spec.deployment.vps_ip, not hardcoded."""
        mock_wp.plugin_list.return_value = [{"name": "wordfence", "status": "active"}]
        mock_wp.run.return_value = "added"
        self._write_manifest(tmp_path, [])

        spec = {**minimal_spec, "dry_run": False}
        spec["deployment"]["vps_ip"] = "10.0.0.99"
        plugins_stage.apply(spec, mock_wp, mock_api, tmp_path)

        eval_calls = [c for c in mock_wp.run.call_args_list if "eval" in str(c)]
        assert len(eval_calls) == 1
        assert "10.0.0.99" in str(eval_calls[0])

    def test_whitelist_failure_is_non_fatal(self, minimal_spec, mock_wp, mock_api, tmp_path):
        """Wordfence whitelist failure does not block plugin stage."""
        mock_wp.plugin_list.return_value = [{"name": "wordfence", "status": "active"}]
        mock_wp.run.side_effect = RuntimeError("wp eval failed")
        self._write_manifest(tmp_path, [])

        spec = {**minimal_spec, "dry_run": False}
        result = plugins_stage.apply(spec, mock_wp, mock_api, tmp_path)

        # Stage should still succeed — whitelist is best-effort
        assert result.success

    def test_no_whitelist_when_wordfence_not_active(
        self, minimal_spec, mock_wp, mock_api, tmp_path
    ):
        """No wp eval call when Wordfence is not in the installed list."""
        mock_wp.plugin_list.return_value = [{"name": "akismet", "status": "active"}]
        self._write_manifest(tmp_path, [])

        spec = {**minimal_spec, "dry_run": False}
        plugins_stage.apply(spec, mock_wp, mock_api, tmp_path)

        # No wp.run calls at all (no plugins to install, no wordfence)
        mock_wp.run.assert_not_called()


# ---------------------------------------------------------------------------
# 5. stages/verify.py — 429 retry with backoff
# ---------------------------------------------------------------------------


def _make_checks_json(tmp_path, urls=None, extra=None):
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir(exist_ok=True)
    checks = {"urls": urls or [{"url": "/", "expected_status": 200}]}
    if extra:
        checks.update(extra)
    with open(manifests_dir / "checks.json", "w") as f:
        json.dump(checks, f)


class TestVerify429Retry:
    """Verify stage retries 429 responses with exponential backoff."""

    def test_429_retried_then_succeeds(self, minimal_spec, mock_wp, mock_api, tmp_path):
        """First request returns 429, retry returns 200 → check passes."""
        _make_checks_json(tmp_path)

        with (
            patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
            patch("fabrik.wordpress.stages.verify._run_baseline_checks", return_value=[]),
            patch("fabrik.wordpress.stages.verify.time.sleep"),
        ):
            mock_client = mock_client_cls.return_value.__enter__.return_value

            responses = []
            r429 = MagicMock()
            r429.status_code = 429
            responses.append(r429)
            r200 = MagicMock()
            r200.status_code = 200
            responses.append(r200)

            mock_client.get.side_effect = responses

            spec = {**minimal_spec, "dry_run": False}
            result = verify_stage.apply(spec, mock_wp, mock_api, tmp_path)

        assert result.success
        assert len(result.errors) == 0

    def test_429_all_retries_exhausted(self, minimal_spec, mock_wp, mock_api, tmp_path):
        """All retries return 429 → check fails with final 429 status."""
        _make_checks_json(tmp_path)

        with (
            patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
            patch("fabrik.wordpress.stages.verify._run_baseline_checks", return_value=[]),
            patch("fabrik.wordpress.stages.verify.time.sleep"),
        ):
            mock_client = mock_client_cls.return_value.__enter__.return_value

            r429 = MagicMock()
            r429.status_code = 429
            mock_client.get.return_value = r429

            spec = {**minimal_spec, "dry_run": False}
            result = verify_stage.apply(spec, mock_wp, mock_api, tmp_path)

        assert not result.success
        assert any("429" in e for e in result.errors)

    def test_429_backoff_timing(self, minimal_spec, mock_wp, mock_api, tmp_path):
        """Verify exponential backoff: 3s, 6s between retries."""
        _make_checks_json(tmp_path)

        with (
            patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
            patch("fabrik.wordpress.stages.verify._run_baseline_checks", return_value=[]),
            patch("fabrik.wordpress.stages.verify.time.sleep") as mock_sleep,
        ):
            mock_client = mock_client_cls.return_value.__enter__.return_value
            r429 = MagicMock()
            r429.status_code = 429
            mock_client.get.return_value = r429

            spec = {**minimal_spec, "dry_run": False}
            verify_stage.apply(spec, mock_wp, mock_api, tmp_path)

        # sleep calls include the inter-request delay (not applicable for
        # first URL) and the retry backoff sleeps.
        # For 1 URL with 3 retries: sleep(3) after attempt 0, sleep(6) after attempt 1.
        sleep_values = [c.args[0] for c in mock_sleep.call_args_list]
        assert 3 in sleep_values  # _RETRY_BACKOFF_BASE * 2^0
        assert 6 in sleep_values  # _RETRY_BACKOFF_BASE * 2^1

    def test_503_also_retried(self, minimal_spec, mock_wp, mock_api, tmp_path):
        """503 responses are also retried, not just 429."""
        _make_checks_json(tmp_path)

        with (
            patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
            patch("fabrik.wordpress.stages.verify._run_baseline_checks", return_value=[]),
            patch("fabrik.wordpress.stages.verify.time.sleep"),
        ):
            mock_client = mock_client_cls.return_value.__enter__.return_value

            r503 = MagicMock()
            r503.status_code = 503
            r200 = MagicMock()
            r200.status_code = 200
            mock_client.get.side_effect = [r503, r200]

            spec = {**minimal_spec, "dry_run": False}
            result = verify_stage.apply(spec, mock_wp, mock_api, tmp_path)

        assert result.success

    def test_non_retryable_status_not_retried(self, minimal_spec, mock_wp, mock_api, tmp_path):
        """404 is not retried — only 429 and 503 trigger retries."""
        _make_checks_json(tmp_path)

        with (
            patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
            patch("fabrik.wordpress.stages.verify._run_baseline_checks", return_value=[]),
            patch("fabrik.wordpress.stages.verify.time.sleep"),
        ):
            mock_client = mock_client_cls.return_value.__enter__.return_value

            r404 = MagicMock()
            r404.status_code = 404
            mock_client.get.return_value = r404

            spec = {**minimal_spec, "dry_run": False}
            result = verify_stage.apply(spec, mock_wp, mock_api, tmp_path)

        assert not result.success
        # Only 1 call (no retries for 404)
        assert mock_client.get.call_count == 1

    def test_verify_headers_include_user_agent(self, minimal_spec, mock_wp, mock_api, tmp_path):
        """httpx.Client is created with a Fabrik User-Agent header."""
        _make_checks_json(tmp_path)

        with (
            patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
            patch("fabrik.wordpress.stages.verify._run_baseline_checks", return_value=[]),
            patch("fabrik.wordpress.stages.verify.time.sleep"),
        ):
            r200 = MagicMock()
            r200.status_code = 200
            mock_client_cls.return_value.__enter__.return_value.get.return_value = r200

            spec = {**minimal_spec, "dry_run": False}
            verify_stage.apply(spec, mock_wp, mock_api, tmp_path)

        # Check that httpx.Client was called with our headers
        client_call_kwargs = mock_client_cls.call_args
        assert "headers" in client_call_kwargs.kwargs
        assert "User-Agent" in client_call_kwargs.kwargs["headers"]
        assert "Fabrik" in client_call_kwargs.kwargs["headers"]["User-Agent"]
