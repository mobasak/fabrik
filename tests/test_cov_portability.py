"""Coverage sweep for ``fabrik.portability`` (export/import bundle). Hermetic: ssh is mocked."""

from __future__ import annotations

import io
import json
import sys
import tarfile
import types
from pathlib import Path

import pytest
import yaml

from fabrik import portability as p


def _members(tarball: Path) -> dict[str, str]:
    out = {}
    with tarfile.open(tarball, "r:gz") as tar:
        for m in tar.getmembers():
            f = tar.extractfile(m)
            if f:
                out[m.name] = f.read().decode("utf-8")
    return out


def _make_tar(path: Path, files: dict[str, str], dirs: tuple[str, ...] = ()) -> Path:
    with tarfile.open(path, "w:gz") as tar:
        for d in dirs:
            info = tarfile.TarInfo(d)
            info.type = tarfile.DIRTYPE
            tar.addfile(info)
        for name, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path


@pytest.fixture
def root(tmp_path: Path) -> Path:
    r = tmp_path / "root"
    (r / "specs" / "services").mkdir(parents=True)
    (r / "specs" / "services" / "b.yaml").write_text("id: b\n")
    (r / "specs" / "services" / "a.yaml").write_text("id: a\n")
    (r / "specs" / "services" / "note.txt").write_text("ignored")
    (r / ".fabrik" / "state" / "_destroyed").mkdir(parents=True)
    (r / ".fabrik" / "state" / "_destroyed" / "old.json").write_text("{}")
    (r / ".fabrik" / "state" / "svc.json").write_text(
        json.dumps({"coolify_uuid": "x", "uuid": "u", "name": "svc", "nested": {"id": 1, "k": "v"}})
    )
    (r / ".env").write_text("# c\nFOO=secretvalue\n\nBAR = x\nbad key=1\nNOEQ\n_OK=1\n")
    (r / "configs" / "grafana" / "dashboards").mkdir(parents=True)
    (r / "configs" / "grafana" / "dashboards" / "d.json").write_text('{"d": 1}')
    return r


# ── key redaction ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "key",
    [
        "password",
        "DB_PASSWORD",
        "jwt_secret",
        "api-key",
        "apiKey",
        "private_key",
        "auth",
        "users",
        "env",
        "credentials",
        "webhook_url",
        "Token",
    ],
)
def test_key_is_sensitive_true(key):
    assert p._key_is_sensitive(key)


@pytest.mark.parametrize("key", ["name", "host", "schedule", "authority", "envx", "repo"])
def test_key_is_sensitive_false(key):
    assert not p._key_is_sensitive(key)


def test_redact_sensitive_fields_recurses_dicts_and_lists():
    obj = {
        "a": 1,
        "password": "pw",
        "repos": [{"uri": "s3://x", "env": ["AWS=1"]}],
        "auth": {"users": [{"n": "u"}]},
    }
    out = p._redact_sensitive_fields(obj)
    assert out["a"] == 1
    assert out["password"] == "REDACTED"
    assert out["repos"] == [{"uri": "s3://x", "env": "REDACTED"}]
    assert out["auth"] == "REDACTED"
    assert p._redact_sensitive_fields("plain") == "plain"
    assert obj["password"] == "pw"  # input untouched


# ── uuid stripping ───────────────────────────────────────────────────────────


def test_strip_uuids_removes_keys_and_uuid_shaped_strings():
    obj = {
        "uuid": "z",
        "id": 3,
        "keep": "ok",
        "u24": "a" * 24,
        "l": ["b" * 24, "short", {"server_uuid": 1, "x": 2}],
    }
    assert p._strip_uuids(obj) == {"keep": "ok", "u24": None, "l": [None, "short", {"x": 2}]}


def test_strip_uuids_scalar_passthrough():
    assert p._strip_uuids(5) == 5
    assert p._strip_uuids("A" * 24) == "A" * 24  # uppercase is not matched


# ── env redaction ────────────────────────────────────────────────────────────


def test_redact_env_keys_names_only_sorted(root):
    out = p._redact_env_keys(root / ".env")
    assert out == {"BAR": "REDACTED", "FOO": "REDACTED", "_OK": "REDACTED"}
    assert list(out) == sorted(out)
    assert "secretvalue" not in json.dumps(out)


def test_redact_env_keys_missing_file(tmp_path):
    assert p._redact_env_keys(tmp_path / "nope") == {}


# ── local collectors ─────────────────────────────────────────────────────────


def test_collect_specs_sorted_yaml_only(root):
    out = p._collect_specs(root)
    assert list(out) == ["specs/services/a.yaml", "specs/services/b.yaml"]
    assert out["specs/services/a.yaml"] == "id: a\n"


def test_collect_specs_missing_dir(tmp_path):
    assert p._collect_specs(tmp_path) == {}


def test_collect_state_strips_and_skips_destroyed(root):
    out = p._collect_state(root)
    assert list(out) == ["svc"]
    assert out["svc"] == {"name": "svc", "nested": {"k": "v"}}


def test_collect_state_skips_corrupt_file(root, caplog):
    (root / ".fabrik" / "state" / "bad.json").write_text("{not json")
    out = p._collect_state(root)
    assert "bad" not in out and "svc" in out
    assert "skip unreadable state file" in caplog.text


def test_collect_state_missing_dir(tmp_path):
    assert p._collect_state(tmp_path) == {}


@pytest.mark.xfail(
    strict=True,
    reason="_collect_state crashes (AttributeError on .pop) when a state file is valid JSON but not an object",
)
def test_collect_state_non_object_json_does_not_crash(root):
    (root / ".fabrik" / "state" / "list.json").write_text("[1, 2]")
    p._collect_state(root)


def test_collect_monitoring_local(root):
    assert p._collect_monitoring_local(root) == {"configs/grafana/dashboards/d.json": '{"d": 1}'}


def test_collect_monitoring_local_missing(tmp_path):
    assert p._collect_monitoring_local(tmp_path) == {}


# ── ssh helpers ──────────────────────────────────────────────────────────────


def _fake_ssh_module(monkeypatch, fn):
    """Install a stand-in ``fabrik.drivers.ssh`` so no real driver/ssh is imported."""
    mod = types.ModuleType("fabrik.drivers.ssh")
    mod.ssh = fn
    monkeypatch.setitem(sys.modules, "fabrik.drivers.ssh", mod)


def test_ssh_cat_success(monkeypatch):
    calls = []
    _fake_ssh_module(monkeypatch, lambda cmd, *a, **k: calls.append(cmd) or "content")
    assert p._ssh_cat("/x/y") == "content"
    assert calls == ["sudo cat /x/y"]


def test_ssh_cat_failure_returns_none(monkeypatch, caplog):
    def boom(cmd, *a, **k):
        raise RuntimeError("down")

    _fake_ssh_module(monkeypatch, boom)
    assert p._ssh_cat("/x") is None
    assert "ssh cat /x failed" in caplog.text


def test_collect_monitoring_remote_skips_none(monkeypatch):
    def fake(path):
        return None if "alertmanager" in path else f"data:{path}"

    monkeypatch.setattr(p, "_ssh_cat", fake)
    out = p._collect_monitoring_remote()
    assert set(out) == {
        "monitoring/prometheus.yml",
        "monitoring/redis-assignments.json",
        "monitoring/postgres-allocations.json",
    }
    assert out["monitoring/prometheus.yml"].endswith("prometheus.yml")


# ── authelia ─────────────────────────────────────────────────────────────────

_AUTHELIA = "jwt_secret: hunter2\nsession:\n  secret: s3\nstorage:\n  encryption_key: k\naccess_control:\n  rules:\n    - domain: a.com\n"


def test_collect_authelia_redacts_secrets(monkeypatch):
    seen = []
    monkeypatch.setattr(p, "_ssh_cat", lambda path: seen.append(path) or _AUTHELIA)
    out = p._collect_authelia()
    assert seen == ["/opt/authelia/config/configuration.yml"]  # first candidate wins
    text = out["authelia/configuration.yml"]
    assert "hunter2" not in text and "s3" not in yaml.safe_load(text)["session"].values()
    parsed = yaml.safe_load(text)
    assert parsed["jwt_secret"] == "REDACTED"
    assert parsed["storage"]["encryption_key"] == "REDACTED"
    assert parsed["access_control"]["rules"] == [{"domain": "a.com"}]


def test_collect_authelia_falls_back_through_candidates_and_discovery(monkeypatch):
    seen = []

    def fake(path):
        seen.append(path)
        return _AUTHELIA if path.startswith("$(sudo find") else None

    monkeypatch.setattr(p, "_ssh_cat", fake)
    assert "authelia/configuration.yml" in p._collect_authelia()
    assert len(seen) == 4


def test_collect_authelia_nothing_found(monkeypatch):
    monkeypatch.setattr(p, "_ssh_cat", lambda path: None)
    assert p._collect_authelia() == {}


def test_collect_authelia_invalid_yaml_fails_closed(monkeypatch):
    monkeypatch.setattr(p, "_ssh_cat", lambda path: "a: [unclosed\npassword: leak")
    assert p._collect_authelia() == {}


def test_collect_authelia_empty_yaml_document(monkeypatch):
    monkeypatch.setattr(p, "_ssh_cat", lambda path: "# only a comment\n")
    out = p._collect_authelia()
    assert yaml.safe_load(out["authelia/configuration.yml"]) == {}


# ── backrest ─────────────────────────────────────────────────────────────────


def test_collect_backrest_redacts(monkeypatch):
    raw = json.dumps(
        {
            "repos": [{"uri": "s3://b", "password": "pw", "env": ["K=V"]}],
            "auth": {"users": [{"name": "u", "passwordBcrypt": "h"}]},
            "instance": "i",
        }
    )
    monkeypatch.setattr(p, "_ssh_cat", lambda path: raw)
    out = p._collect_backrest()["backrest/config.json"]
    assert "pw" not in out and "K=V" not in out and '"h"' not in out
    parsed = json.loads(out)
    assert parsed["repos"][0] == {"uri": "s3://b", "password": "REDACTED", "env": "REDACTED"}
    assert parsed["instance"] == "i"
    assert out == json.dumps(parsed, indent=2, sort_keys=True)


def test_collect_backrest_missing_and_invalid(monkeypatch):
    monkeypatch.setattr(p, "_ssh_cat", lambda path: None)
    assert p._collect_backrest() == {}
    monkeypatch.setattr(p, "_ssh_cat", lambda path: "{nope")
    assert p._collect_backrest() == {}


# ── README / manifest ────────────────────────────────────────────────────────


def test_build_readme_lists_sorted_sections():
    r = p._build_readme("vps9", "2026-01-01T00:00:00+00:00", ["state", "specs"])
    assert "**Source:** vps9" in r and "2026-01-01T00:00:00+00:00" in r
    assert f"**Bundle version:** {p.BUNDLE_VERSION}" in r
    assert r.index("- `specs/`") < r.index("- `state/`")


def test_build_manifest_shape():
    m = p._build_manifest("v", "t", {"b": 1, "a": 2}, True)
    assert m["version"] == p.BUNDLE_VERSION and m["source_vps"] == "v" and m["created_at"] == "t"
    assert m["include_data"] is True
    assert list(m["sections"]) == ["a", "b"]
    assert m["untested_paths"] == ["import"]
    assert m["out_of_scope"]


def test_add_text_roundtrip():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        p._add_text(tar, "d/f.txt", "héllo")
    buf.seek(0)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        m = tar.getmember("d/f.txt")
        assert m.mode == 0o644 and m.size == len("héllo".encode())
        assert tar.extractfile(m).read().decode() == "héllo"


# ── export_bundle ────────────────────────────────────────────────────────────


def test_export_bundle_skip_remote(root, tmp_path):
    out = tmp_path / "deep" / "dir" / "b.tar.gz"
    res = p.export_bundle(
        out, fabrik_root=root, skip_remote=True, source_vps="vpsX", include_data=True
    )
    assert res == out and out.exists()
    files = _members(out)
    assert set(files) == {
        "manifest.json",
        "README.md",
        "secrets-redacted.json",
        "specs/services/a.yaml",
        "specs/services/b.yaml",
        "state/svc.json",
        "configs/grafana/dashboards/d.json",
    }
    manifest = json.loads(files["manifest.json"])
    assert manifest["source_vps"] == "vpsX" and manifest["include_data"] is True
    assert manifest["sections"] == {
        "specs": 2,
        "state": 1,
        "monitoring": 1,
        "authelia": 0,
        "backrest": 0,
        "secrets_redacted_keys": 3,
    }
    assert json.loads(files["secrets-redacted.json"]) == {
        "BAR": "REDACTED",
        "FOO": "REDACTED",
        "_OK": "REDACTED",
    }
    assert "secretvalue" not in "".join(files.values())
    assert "coolify_uuid" not in files["state/svc.json"]
    assert "vpsX" in files["README.md"]
    assert "- `authelia/`" not in files["README.md"]  # empty sections omitted


def test_export_bundle_with_remote(root, tmp_path, monkeypatch):
    monkeypatch.setattr(p, "_collect_monitoring_remote", lambda: {"monitoring/prometheus.yml": "p"})
    monkeypatch.setattr(p, "_collect_authelia", lambda: {"authelia/configuration.yml": "a"})
    monkeypatch.setattr(p, "_collect_backrest", lambda: {"backrest/config.json": "{}"})
    files = _members(p.export_bundle(tmp_path / "b.tar.gz", fabrik_root=root))
    assert files["monitoring/prometheus.yml"] == "p"
    assert files["authelia/configuration.yml"] == "a"
    assert files["backrest/config.json"] == "{}"
    assert json.loads(files["manifest.json"])["sections"]["monitoring"] == 2


def test_export_bundle_skip_remote_never_calls_ssh(root, tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("ssh called")

    monkeypatch.setattr(p, "_ssh_cat", boom)
    p.export_bundle(tmp_path / "b.tar.gz", fabrik_root=root, skip_remote=True)


def test_export_bundle_empty_root(tmp_path):
    files = _members(
        p.export_bundle(tmp_path / "b.tar.gz", fabrik_root=tmp_path / "empty", skip_remote=True)
    )
    assert set(files) == {"manifest.json", "README.md", "secrets-redacted.json"}
    assert json.loads(files["secrets-redacted.json"]) == {}


# ── import_bundle ────────────────────────────────────────────────────────────


def test_import_missing_tarball(tmp_path):
    with pytest.raises(FileNotFoundError, match="bundle not found"):
        p.import_bundle(tmp_path / "nope.tar.gz")


def test_import_roundtrip_dry_run(root, tmp_path):
    t = p.export_bundle(tmp_path / "b.tar.gz", fabrik_root=root, skip_remote=True)
    plan = p.import_bundle(t)
    assert plan["dry_run"] is True
    assert plan["actions"] == [{"phase": "noop", "reason": "dry_run=True (default)"}]
    assert plan["secrets_to_repopulate"] == ["BAR", "FOO", "_OK"]
    assert plan["manifest"]["version"] == p.BUNDLE_VERSION
    assert plan["sections"]["specs"] == 2 and plan["sections"]["state"] == 1
    assert plan["sections"]["total_entries"] == 7
    assert "monitoring" not in plan["sections"]  # grafana mirror lives under configs/
    assert "ignored_legacy" not in plan
    assert plan["tarball"] == str(t)


def test_import_real_run_is_stub(root, tmp_path):
    t = p.export_bundle(tmp_path / "b.tar.gz", fabrik_root=root, skip_remote=True)
    plan = p.import_bundle(t, dry_run=False)
    assert plan["dry_run"] is False
    assert [a["phase"] for a in plan["actions"]] == ["real_run"]
    assert plan["actions"][0]["status"] == "stub"


def test_import_dot_prefixed_names_and_legacy_count(tmp_path):
    t = _make_tar(
        tmp_path / "legacy.tar.gz",
        {
            "./manifest.json": '{"version": 1}',
            "./secrets-redacted.json": '{"Z": "R", "A": "R"}',
            "./specs/services/a.yaml": "x",
            "./coolify/one.json": "{}",
            "./coolify/two.json": "{}",
        },
        dirs=("./coolify/sub",),
    )
    plan = p.import_bundle(t)
    assert plan["manifest"] == {"version": 1}
    assert plan["secrets_to_repopulate"] == ["A", "Z"]
    assert plan["sections"]["specs"] == 1
    assert plan["ignored_legacy"] == 2  # directory entry not counted


def test_import_without_manifest_or_secrets(tmp_path):
    t = _make_tar(
        tmp_path / "m.tar.gz", {"backrest/config.json": "{}", "authelia/configuration.yml": "a"}
    )
    plan = p.import_bundle(t)
    assert plan["manifest"] is None
    assert plan["secrets_to_repopulate"] == []
    assert plan["sections"] == {"total_entries": 2, "authelia": 1, "backrest": 1}


def test_import_corrupt_manifest_raises(tmp_path):
    t = _make_tar(tmp_path / "c.tar.gz", {"manifest.json": "{bad"})
    with pytest.raises(json.JSONDecodeError):
        p.import_bundle(t)


def test_import_accepts_str_path(root, tmp_path):
    t = p.export_bundle(tmp_path / "b.tar.gz", fabrik_root=root, skip_remote=True)
    assert p.import_bundle(str(t))["tarball"] == str(t)


def test_public_api():
    assert set(p.__all__) == {"BUNDLE_VERSION", "export_bundle", "import_bundle"}
