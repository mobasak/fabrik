"""Coverage sweep for fabrik.drivers.image_broker.ImageBrokerClient (hermetic)."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from fabrik.drivers.image_broker import ImageBrokerClient


@pytest.fixture
def mock_http():
    with patch("fabrik.drivers.image_broker.httpx.Client") as cls:
        inst = MagicMock()
        cls.return_value = inst
        inst.cls = cls
        yield inst


def _resp(data=None, content=b""):
    r = MagicMock()
    r.json.return_value = data if data is not None else {}
    r.content = content
    return r


# ---- __init__ -------------------------------------------------------------


def test_init_explicit_base_url_wins_over_env(monkeypatch, mock_http):
    monkeypatch.setenv("IMAGE_BROKER_URL", "http://env:1")
    assert ImageBrokerClient(base_url="http://arg:2").base_url == "http://arg:2"


def test_init_uses_env_var(monkeypatch, mock_http):
    monkeypatch.setenv("IMAGE_BROKER_URL", "http://env:1")
    assert ImageBrokerClient().base_url == "http://env:1"


def test_init_default_url(monkeypatch, mock_http):
    monkeypatch.delenv("IMAGE_BROKER_URL", raising=False)
    assert ImageBrokerClient().base_url == "http://localhost:18016"


def test_init_empty_base_url_falls_back_to_default(monkeypatch, mock_http):
    monkeypatch.delenv("IMAGE_BROKER_URL", raising=False)
    assert ImageBrokerClient(base_url="").base_url == "http://localhost:18016"


def test_init_client_gets_timeout_and_json_headers(mock_http):
    c = ImageBrokerClient(base_url="http://x", timeout=7.5)
    assert c.timeout == 7.5
    kwargs = mock_http.cls.call_args.kwargs
    assert kwargs["timeout"] == 7.5
    assert kwargs["headers"] == {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def test_init_default_timeout(mock_http):
    assert ImageBrokerClient(base_url="http://x").timeout == 60.0


# ---- _request -------------------------------------------------------------


def test_request_builds_url_and_returns_json(mock_http):
    mock_http.request.return_value = _resp({"ok": 1})
    c = ImageBrokerClient(base_url="http://b:1")
    assert c._request("GET", "/p", params={"a": 1}) == {"ok": 1}
    mock_http.request.assert_called_once_with("GET", "http://b:1/p", params={"a": 1})


def test_request_raises_on_http_status_error(mock_http):
    r = _resp()
    r.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500", request=MagicMock(), response=MagicMock()
    )
    mock_http.request.return_value = r
    with pytest.raises(httpx.HTTPStatusError):
        ImageBrokerClient(base_url="http://b")._request("GET", "/x")
    r.json.assert_not_called()


# ---- auto_download --------------------------------------------------------


def test_auto_download_default_payload(mock_http):
    mock_http.request.return_value = _resp({"success": True})
    ImageBrokerClient(base_url="http://b").auto_download("q")
    args, kwargs = mock_http.request.call_args
    assert args == ("POST", "http://b/api/v1/auto-download")
    assert kwargs["json"] == {
        "query": "q",
        "intent": "hero",
        "count": 1,
        "image_type": "photo",
        "need_faces": False,
    }


def test_auto_download_optional_fields_included_when_set(mock_http):
    mock_http.request.return_value = _resp({"success": True})
    ImageBrokerClient(base_url="http://b").auto_download(
        "q",
        intent="inline",
        count=3,
        image_type="vector",
        orientation="landscape",
        topic="people",
        need_faces=True,
    )
    payload = mock_http.request.call_args.kwargs["json"]
    assert payload["intent"] == "inline"
    assert payload["count"] == 3
    assert payload["image_type"] == "vector"
    assert payload["orientation"] == "landscape"
    assert payload["topic"] == "people"
    assert payload["need_faces"] is True


def test_auto_download_omits_orientation_and_topic_when_none(mock_http):
    mock_http.request.return_value = _resp({"success": True})
    ImageBrokerClient(base_url="http://b").auto_download("q")
    payload = mock_http.request.call_args.kwargs["json"]
    assert "orientation" not in payload
    assert "topic" not in payload


def test_auto_download_empty_string_orientation_is_sent(mock_http):
    mock_http.request.return_value = _resp({"success": True})
    ImageBrokerClient(base_url="http://b").auto_download("q", orientation="", topic="")
    payload = mock_http.request.call_args.kwargs["json"]
    assert payload["orientation"] == ""
    assert payload["topic"] == ""


def test_auto_download_missing_success_key_is_none(mock_http):
    mock_http.request.return_value = _resp({"selected": [1]})
    assert ImageBrokerClient(base_url="http://b").auto_download("q") is None


def test_auto_download_returns_full_dict(mock_http):
    data = {"success": True, "selected": [{"local_url": "/a"}], "provider_used": "pexels"}
    mock_http.request.return_value = _resp(data)
    assert ImageBrokerClient(base_url="http://b").auto_download("q") == data


def test_auto_download_none_on_status_error(mock_http):
    r = _resp({"success": True})
    r.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock()
    )
    mock_http.request.return_value = r
    assert ImageBrokerClient(base_url="http://b").auto_download("q") is None


def test_auto_download_logs_warning_on_failure(mock_http, caplog):
    mock_http.request.side_effect = httpx.ConnectError("refused")
    with caplog.at_level("WARNING", logger="fabrik.drivers.image_broker"):
        assert ImageBrokerClient(base_url="http://b").auto_download("zzz") is None
    assert "zzz" in caplog.text


def test_auto_download_logs_warning_on_success_false(mock_http, caplog):
    mock_http.request.return_value = _resp({"success": False})
    with caplog.at_level("WARNING", logger="fabrik.drivers.image_broker"):
        ImageBrokerClient(base_url="http://b").auto_download("nothing")
    assert "success=false" in caplog.text


def test_auto_download_non_http_error_propagates(mock_http):
    mock_http.request.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError):
        ImageBrokerClient(base_url="http://b").auto_download("q")


def test_auto_download_invalid_json_propagates(mock_http):
    r = _resp()
    r.json.side_effect = ValueError("not json")
    mock_http.request.return_value = r
    with pytest.raises(ValueError):
        ImageBrokerClient(base_url="http://b").auto_download("q")


# ---- search ---------------------------------------------------------------


def test_search_default_params(mock_http):
    mock_http.request.return_value = _resp({"results": []})
    out = ImageBrokerClient(base_url="http://b").search("office")
    assert out == {"results": []}
    args, kwargs = mock_http.request.call_args
    assert args == ("GET", "http://b/api/v1/search")
    assert kwargs["params"] == {"query": "office", "per_page": 10}


def test_search_with_orientation_and_per_page(mock_http):
    mock_http.request.return_value = _resp({})
    ImageBrokerClient(base_url="http://b").search("x", orientation="square", per_page=3)
    assert mock_http.request.call_args.kwargs["params"] == {
        "query": "x",
        "per_page": 3,
        "orientation": "square",
    }


def test_search_propagates_http_errors(mock_http):
    mock_http.request.side_effect = httpx.ConnectError("down")
    with pytest.raises(httpx.ConnectError):
        ImageBrokerClient(base_url="http://b").search("x")


# ---- download_image -------------------------------------------------------


def test_download_image_writes_bytes_and_returns_path(mock_http, tmp_path):
    mock_http.get.return_value = _resp(content=b"\x89PNGdata")
    dest = tmp_path / "img.png"
    out = ImageBrokerClient(base_url="http://b").download_image("http://c/i.png", str(dest))
    assert out == str(dest)
    assert dest.read_bytes() == b"\x89PNGdata"
    mock_http.get.assert_called_once_with("http://c/i.png")


def test_download_image_overwrites_existing_file(mock_http, tmp_path):
    dest = tmp_path / "i.jpg"
    dest.write_bytes(b"old-old-old")
    mock_http.get.return_value = _resp(content=b"new")
    ImageBrokerClient(base_url="http://b").download_image("http://c/i", str(dest))
    assert dest.read_bytes() == b"new"


def test_download_image_status_error_writes_nothing(mock_http, tmp_path):
    r = _resp(content=b"junk")
    r.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock()
    )
    mock_http.get.return_value = r
    dest = tmp_path / "x.jpg"
    with pytest.raises(httpx.HTTPStatusError):
        ImageBrokerClient(base_url="http://b").download_image("http://c/x", str(dest))
    assert not dest.exists()


def test_download_image_missing_parent_dir_raises(mock_http, tmp_path):
    mock_http.get.return_value = _resp(content=b"d")
    with pytest.raises(FileNotFoundError):
        ImageBrokerClient(base_url="http://b").download_image(
            "http://c/x", str(tmp_path / "nope" / "x.jpg")
        )


def test_download_image_accepts_pathlike_dest_returns_it_unchanged(mock_http, tmp_path):
    mock_http.get.return_value = _resp(content=b"d")
    dest = tmp_path / "p.bin"
    assert ImageBrokerClient(base_url="http://b").download_image("u", dest) == dest


# ---- health ---------------------------------------------------------------


def test_health_calls_endpoint(mock_http):
    mock_http.request.return_value = _resp({"status": "ok"})
    assert ImageBrokerClient(base_url="http://b").health() == {"status": "ok"}
    assert mock_http.request.call_args.args == ("GET", "http://b/api/v1/health")


def test_health_propagates_errors(mock_http):
    mock_http.request.side_effect = httpx.ConnectError("down")
    with pytest.raises(httpx.ConnectError):
        ImageBrokerClient(base_url="http://b").health()


# ---- lifecycle ------------------------------------------------------------


def test_close_closes_client(mock_http):
    ImageBrokerClient(base_url="http://b").close()
    mock_http.close.assert_called_once_with()


def test_context_manager_returns_self_and_closes(mock_http):
    with ImageBrokerClient(base_url="http://b") as c:
        assert isinstance(c, ImageBrokerClient)
        mock_http.close.assert_not_called()
    mock_http.close.assert_called_once_with()


def test_context_manager_closes_on_exception(mock_http):
    with pytest.raises(KeyError):
        with ImageBrokerClient(base_url="http://b"):
            raise KeyError("x")
    mock_http.close.assert_called_once_with()
