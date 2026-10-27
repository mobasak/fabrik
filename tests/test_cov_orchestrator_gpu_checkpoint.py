"""Coverage tests for fabrik.orchestrator.gpu_checkpoint (hermetic, no network)."""

from __future__ import annotations

import hashlib
import json
import re
import threading

import pytest

from fabrik.orchestrator import gpu_checkpoint as gc

_CRED_VARS = ("B2_KEY_ID", "B2_APPLICATION_KEY", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")


class FakeResp:
    def __init__(self, status=200, content=b"", headers=None):
        self.status_code = status
        self.content = content
        self.text = content.decode(errors="replace")
        self.headers = headers or {}


class FakeStore:
    """In-memory stand-in for the B2 bucket, shared by every FakeClient."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.puts: list[dict] = []
        self.gets: list[str] = []
        self.fail_put_status = None
        self.fail_list_status = None
        self.clients: list[FakeClient] = []


class FakeClient:
    store: FakeStore

    def __init__(self, timeout=None):
        self.timeout = timeout
        self.auth = None
        self.closed = False
        self.store.clients.append(self)

    def put(self, url, content=None, headers=None):
        s = self.store
        s.puts.append({"url": url, "content": content, "headers": headers})
        if s.fail_put_status:
            return FakeResp(s.fail_put_status, b"denied" * 100)
        s.objects[url] = content
        return FakeResp(200, b"", {"ETag": '"abc"'})

    def get(self, url):
        s = self.store
        s.gets.append(url)
        if "?prefix=" in url:
            if s.fail_list_status:
                return FakeResp(s.fail_list_status, b"list boom")
            prefix = url.split("?prefix=", 1)[1].split("&", 1)[0]
            base = url.split("?", 1)[0]
            keys = [
                u[len(base) + 1 :] for u in s.objects if u.startswith(f"{base}/{prefix}")
            ]
            xml = "".join(f"<Key>{k}</Key>" for k in keys)
            return FakeResp(200, xml.encode())
        if url in s.objects:
            return FakeResp(200, s.objects[url])
        return FakeResp(404, b"not found")

    def close(self):
        self.closed = True


@pytest.fixture
def store(monkeypatch):
    st = FakeStore()
    FakeClient.store = st
    monkeypatch.setattr(gc.httpx, "Client", FakeClient)
    return st


@pytest.fixture(autouse=True)
def creds(monkeypatch, tmp_path):
    for v in _CRED_VARS:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(gc, "SYSADMIN_ENV", tmp_path / "missing.env")
    monkeypatch.setenv("B2_KEY_ID", "kid")
    monkeypatch.setenv("B2_APPLICATION_KEY", "secret")


def _url(key, bucket=gc.DEFAULT_BUCKET):
    return f"{gc.DEFAULT_S3_ENDPOINT}/{bucket}/{key}"


# ---------------------------------------------------------------- helpers


def test_object_key_format_is_zero_padded():
    k = gc._object_key(project="p", run_id="r1", step=42, ts="20260101T000000Z")
    assert k == "fabrik-gpu-checkpoints/p/r1/checkpoint-00000042-20260101T000000Z.tar.gz"


def test_metadata_key_format():
    assert gc._metadata_key(project="p", run_id="r") == "fabrik-gpu-checkpoints/p/r/_meta.json"


def test_now_iso_shape():
    assert re.fullmatch(r"\d{8}T\d{6}Z", gc._now_iso())


# ---------------------------------------------------------------- creds


def test_creds_from_b2_env():
    assert gc._load_b2_creds() == ("kid", "secret")


def test_creds_fall_back_to_aws_vars(monkeypatch):
    monkeypatch.delenv("B2_KEY_ID")
    monkeypatch.delenv("B2_APPLICATION_KEY")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ak")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "sk")
    assert gc._load_b2_creds() == ("ak", "sk")


def test_creds_missing_raises(monkeypatch):
    monkeypatch.delenv("B2_KEY_ID")
    monkeypatch.delenv("B2_APPLICATION_KEY")
    with pytest.raises(gc.CheckpointError, match="B2_KEY_ID"):
        gc._load_b2_creds()


def test_creds_key_without_secret_raises(monkeypatch):
    monkeypatch.delenv("B2_APPLICATION_KEY")
    with pytest.raises(gc.CheckpointError):
        gc._load_b2_creds()


def test_creds_loaded_from_sysadmin_env_file(monkeypatch, tmp_path):
    env = tmp_path / "sys.env"
    env.write_text("B2_KEY_ID=filekey\nB2_APPLICATION_KEY=filesecret\n")
    monkeypatch.setattr(gc, "SYSADMIN_ENV", env)
    # register undo so load_dotenv's os.environ writes do not leak
    for v in _CRED_VARS:
        monkeypatch.setenv(v, "x")
        monkeypatch.delenv(v)
    assert gc._load_b2_creds() == ("filekey", "filesecret")


def test_sysadmin_file_not_read_when_env_already_set(monkeypatch, tmp_path):
    env = tmp_path / "sys.env"
    env.write_text("B2_KEY_ID=filekey\nB2_APPLICATION_KEY=filesecret\n")
    monkeypatch.setattr(gc, "SYSADMIN_ENV", env)
    assert gc._load_b2_creds() == ("kid", "secret")


# ---------------------------------------------------------------- B2Uploader


def test_uploader_init_sets_auth_and_strips_endpoint_slash(store):
    up = gc.B2Uploader("k", "s", endpoint="https://e.example/", timeout=5.0)
    client = store.clients[-1]
    assert up.endpoint == "https://e.example"
    assert client.auth == ("k", "s")
    assert client.timeout == 5.0


def test_put_object_bytes_returns_sha1_and_etag(store):
    up = gc.B2Uploader("k", "s")
    res = up.put_object("a/b.bin", b"hello")
    assert res == {
        "key": "a/b.bin",
        "etag": '"abc"',
        "sha1": hashlib.sha1(b"hello", usedforsecurity=False).hexdigest(),
    }
    put = store.puts[0]
    assert put["url"] == _url("a/b.bin")
    assert put["content"] == b"hello"
    assert put["headers"]["Content-Type"] == "application/octet-stream"
    assert put["headers"]["x-amz-content-sha256"] == "UNSIGNED-PAYLOAD"


def test_put_object_reads_file_like_body(store):
    import io

    up = gc.B2Uploader("k", "s")
    up.put_object("k", io.BytesIO(b"streamed"), content_type="text/plain")
    assert store.puts[0]["content"] == b"streamed"
    assert store.puts[0]["headers"]["Content-Type"] == "text/plain"


def test_put_object_error_raises_with_truncated_body(store):
    store.fail_put_status = 403
    up = gc.B2Uploader("k", "s")
    with pytest.raises(gc.CheckpointError, match="B2 PUT failed: 403") as ei:
        up.put_object("k", b"x")
    assert len(str(ei.value)) < 300


def test_get_object_roundtrip_and_error(store):
    up = gc.B2Uploader("k", "s", bucket="bkt")
    store.objects[_url("x", "bkt")] = b"data"
    assert up.get_object("x") == b"data"
    with pytest.raises(gc.CheckpointError, match="B2 GET failed: 404"):
        up.get_object("missing")


def test_list_objects_parses_keys(store):
    up = gc.B2Uploader("k", "s")
    store.objects[_url("pre/one")] = b"1"
    store.objects[_url("pre/two")] = b"2"
    store.objects[_url("other/three")] = b"3"
    assert sorted(up.list_objects("pre/")) == ["pre/one", "pre/two"]
    assert store.gets[-1].endswith("?prefix=pre/&list-type=2")


def test_list_objects_empty(store):
    assert gc.B2Uploader("k", "s").list_objects("nothing") == []


def test_list_objects_error(store):
    store.fail_list_status = 500
    with pytest.raises(gc.CheckpointError, match="B2 LIST failed: 500"):
        gc.B2Uploader("k", "s").list_objects("p")


def test_close_closes_http_client(store):
    up = gc.B2Uploader("k", "s")
    up.close()
    assert store.clients[-1].closed


# ---------------------------------------------------------------- checkpoint_to_b2


def test_sync_upload_writes_object_and_meta(store):
    res = gc.checkpoint_to_b2(b"PAYLOAD", project="proj", run_id="r1", step=7, async_upload=False)
    assert isinstance(res, dict)
    assert re.fullmatch(
        r"fabrik-gpu-checkpoints/proj/r1/checkpoint-00000007-\d{8}T\d{6}Z\.tar\.gz", res["key"]
    )
    assert store.objects[_url(res["key"])] == b"PAYLOAD"
    meta = json.loads(store.objects[_url("fabrik-gpu-checkpoints/proj/r1/_meta.json")])
    assert meta["latest_step"] == 7
    assert meta["latest_key"] == res["key"]
    assert meta["project"] == "proj" and meta["run_id"] == "r1"
    assert all(c.closed for c in store.clients)


def test_custom_bucket_used(store):
    gc.checkpoint_to_b2(b"x", project="p", run_id="r", step=1, async_upload=False, bucket="mine")
    assert all("/mine/" in p["url"] for p in store.puts)


def test_missing_creds_fail_before_any_upload(store, monkeypatch):
    monkeypatch.delenv("B2_KEY_ID")
    with pytest.raises(gc.CheckpointError):
        gc.checkpoint_to_b2(b"x", project="p", run_id="r", step=1, async_upload=False)
    assert store.puts == []


def test_async_upload_returns_started_daemon_thread(store):
    done = []
    t = gc.checkpoint_to_b2(
        b"x", project="p", run_id="r", step=3, on_complete=lambda r: done.append(r)
    )
    assert isinstance(t, threading.Thread)
    assert t.daemon and t.name == "gpu-checkpoint-p-r-3"
    t.join(timeout=10)
    assert not t.is_alive()
    assert len(done) == 1 and done[0]["key"].startswith("fabrik-gpu-checkpoints/p/r/")


def test_on_complete_receives_result_sync(store):
    got = []
    res = gc.checkpoint_to_b2(
        b"x", project="p", run_id="r", step=1, async_upload=False, on_complete=got.append
    )
    assert got == [res]


def test_on_complete_exception_is_swallowed(store, caplog):
    def boom(_):
        raise ValueError("cb")

    res = gc.checkpoint_to_b2(
        b"x", project="p", run_id="r", step=1, async_upload=False, on_complete=boom
    )
    assert res["key"]
    assert "on_complete callback raised" in caplog.text


def test_upload_failure_propagates_and_closes_client(store):
    store.fail_put_status = 500
    with pytest.raises(gc.CheckpointError, match="PUT failed"):
        gc.checkpoint_to_b2(b"x", project="p", run_id="r", step=1, async_upload=False)
    assert store.clients[-1].closed


def test_meta_update_failure_is_non_fatal(store, monkeypatch, caplog):
    def bad(*a, **k):
        raise RuntimeError("meta down")

    monkeypatch.setattr(gc, "_update_meta", bad)
    got = []
    res = gc.checkpoint_to_b2(
        b"x", project="p", run_id="r", step=1, async_upload=False, on_complete=got.append
    )
    assert res["key"] and got == [res]
    assert "meta update failed" in caplog.text


# ---------------------------------------------------------------- _update_meta


def test_update_meta_does_not_regress_to_older_step(store):
    up = gc.B2Uploader("k", "s")
    gc._update_meta(up, project="p", run_id="r", latest_step=10, latest_key="k10")
    gc._update_meta(up, project="p", run_id="r", latest_step=5, latest_key="k5")
    meta = json.loads(store.objects[_url(gc._metadata_key(project="p", run_id="r"))])
    assert meta["latest_step"] == 10 and meta["latest_key"] == "k10"
    assert len(store.puts) == 1


def test_update_meta_advances_to_newer_step(store):
    up = gc.B2Uploader("k", "s")
    gc._update_meta(up, project="p", run_id="r", latest_step=1, latest_key="k1")
    gc._update_meta(up, project="p", run_id="r", latest_step=2, latest_key="k2")
    meta = json.loads(store.objects[_url(gc._metadata_key(project="p", run_id="r"))])
    assert meta["latest_key"] == "k2"
    assert store.puts[-1]["headers"]["Content-Type"] == "application/json"


# ---------------------------------------------------------------- load_latest_checkpoint


def test_load_uses_meta_pointer_fast_path(store):
    store.objects[_url("fabrik-gpu-checkpoints/p/r/_meta.json")] = json.dumps(
        {"latest_key": "the/key", "latest_step": 3}
    ).encode()
    store.objects[_url("the/key")] = b"BLOB"
    payload, meta = gc.load_latest_checkpoint("p", "r")
    assert payload == b"BLOB"
    assert meta["latest_step"] == 3
    assert not any("?prefix=" in g for g in store.gets)
    assert store.clients[-1].closed


def test_load_falls_back_to_list_and_picks_highest_step(store):
    pre = "fabrik-gpu-checkpoints/p/r/"
    for step in (2, 10, 9):
        store.objects[_url(f"{pre}checkpoint-{step:08d}-20260101T000000Z.tar.gz")] = f"s{step}".encode()
    payload, meta = gc.load_latest_checkpoint("p", "r")
    assert payload == b"s10"
    assert meta["via"] == "list_fallback"
    assert meta["latest_key"].endswith("checkpoint-00000010-20260101T000000Z.tar.gz")


def test_load_returns_none_when_nothing_stored(store):
    assert gc.load_latest_checkpoint("p", "r") is None
    assert store.clients[-1].closed


def test_load_corrupt_meta_falls_back_to_list(store):
    store.objects[_url("fabrik-gpu-checkpoints/p/r/_meta.json")] = b"{not json"
    k = "fabrik-gpu-checkpoints/p/r/checkpoint-00000001-20260101T000000Z.tar.gz"
    store.objects[_url(k)] = b"one"
    payload, meta = gc.load_latest_checkpoint("p", "r")
    assert payload == b"one" and meta["via"] == "list_fallback"


def test_load_meta_without_latest_key_falls_back(store):
    store.objects[_url("fabrik-gpu-checkpoints/p/r/_meta.json")] = b"{}"
    assert gc.load_latest_checkpoint("p", "r") is None


def test_load_list_error_propagates_and_closes(store):
    store.fail_list_status = 500
    with pytest.raises(gc.CheckpointError, match="LIST"):
        gc.load_latest_checkpoint("p", "r")
    assert store.clients[-1].closed


def test_load_missing_payload_raises(store):
    store.objects[_url("fabrik-gpu-checkpoints/p/r/_meta.json")] = json.dumps(
        {"latest_key": "gone"}
    ).encode()
    with pytest.raises(gc.CheckpointError, match="GET failed"):
        gc.load_latest_checkpoint("p", "r")


def test_load_missing_creds_raises(store, monkeypatch):
    monkeypatch.delenv("B2_APPLICATION_KEY")
    with pytest.raises(gc.CheckpointError):
        gc.load_latest_checkpoint("p", "r")


def test_checkpoint_then_load_roundtrip(store):
    gc.checkpoint_to_b2(b"R", project="p", run_id="r", step=4, async_upload=False)
    payload, meta = gc.load_latest_checkpoint("p", "r")
    assert payload == b"R" and meta["latest_step"] == 4


# ---------------------------------------------------------------- tarball


def test_tarball_roundtrip():
    blob = gc.write_checkpoint_to_tarball({"w": [1, 2, 3]}, {"step": 9})
    assert blob[:2] == b"\x1f\x8b"
    out = gc.read_checkpoint_from_tarball(blob)
    assert out["state"] == {"w": [1, 2, 3]}
    assert out["extras"] == {"step": 9}
    assert re.fullmatch(r"\d{8}T\d{6}Z", out["ts"])


def test_tarball_extras_default_empty():
    out = gc.read_checkpoint_from_tarball(gc.write_checkpoint_to_tarball({}))
    assert out["extras"] == {}


def test_read_tarball_garbage_raises():
    with pytest.raises(Exception):  # noqa: B017 - gzip.BadGzipFile / OSError
        gc.read_checkpoint_from_tarball(b"not a tarball")


def test_read_tarball_wrong_member_raises():
    import gzip
    import io
    import tarfile

    buf = io.BytesIO()
    with gzip.GzipFile(mode="wb", fileobj=buf) as gz:
        with tarfile.open(mode="w", fileobj=gz) as tar:
            info = tarfile.TarInfo(name="other.txt")
            info.size = 1
            tar.addfile(info, io.BytesIO(b"x"))
    with pytest.raises(KeyError):
        gc.read_checkpoint_from_tarball(buf.getvalue())


def test_read_tarball_directory_member_raises_checkpoint_error():
    import gzip
    import io
    import tarfile

    buf = io.BytesIO()
    with gzip.GzipFile(mode="wb", fileobj=buf) as gz:
        with tarfile.open(mode="w", fileobj=gz) as tar:
            info = tarfile.TarInfo(name="checkpoint.pkl")
            info.type = tarfile.DIRTYPE
            tar.addfile(info)
    with pytest.raises(gc.CheckpointError, match="missing"):
        gc.read_checkpoint_from_tarball(buf.getvalue())
