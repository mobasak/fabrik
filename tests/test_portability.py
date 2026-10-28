"""T4-03 G-J2 — `fabrik export` / `fabrik import` portability tests.

Two-layer coverage:

1. **Schema invariants** (carried over from the T4-02 skeleton) — the
   state-file schema must stay free of machine-local fields so a bundle
   written on one workstation is interpretable on another.

2. **Bundle contract** — every export must satisfy the security invariants
   from the ticket Pass-2 checklist:

   - No plaintext secret values inside the tarball.
   - No UUID-shaped fields in any exported section.
   - Bundle includes manifest.json, README.md, secrets-redacted.json.

Remote (SSH) pulls are skipped with ``skip_remote=True`` so tests don't
require network access.
"""

from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from fabrik import portability
from fabrik.cli import cli

# ---------------------------------------------------------------------------
# Schema invariants (carried from T4-02 skeleton)
# ---------------------------------------------------------------------------


def test_state_schema_has_no_local_machine_fields():
    """Lock in: the state-file schema (T2-01) deliberately excludes WSL-side
    machine-local fields. If a future ticket adds e.g. ``writer_hostname`` or
    ``wsl_distro``, this test should fail and prompt a portability review.
    """
    import inspect

    from fabrik.state import save

    sig = inspect.signature(save)
    forbidden = {"writer_hostname", "wsl_distro", "operator_email", "host_id"}
    overlap = forbidden & set(sig.parameters)
    assert not overlap, (
        f"state.save() gained machine-local field(s) {overlap}; portability "
        "broken. Either remove them (preferred) or amend T4-03 to handle them."
    )


# ---------------------------------------------------------------------------
# UUID stripping
# ---------------------------------------------------------------------------


class TestUuidStripping:
    def test_top_level_uuid_field_removed(self):
        before = {"uuid": "abc123abc123abc123abc123", "name": "x"}
        after = portability._strip_uuids(before)
        assert "uuid" not in after
        assert after["name"] == "x"

    def test_nested_uuid_fields_removed(self):
        before = {
            "name": "app",
            "destination": {"server_uuid": "u" * 24, "name": "vps1"},
            "deployments": [
                {"deployment_uuid": "d" * 24, "status": "ok"},
                {"deployment_uuid": "e" * 24, "status": "ok"},
            ],
        }
        after = portability._strip_uuids(before)
        assert "server_uuid" not in after["destination"]
        for d in after["deployments"]:
            assert "deployment_uuid" not in d

    def test_uuid_shaped_string_value_blanked(self):
        # A bare 24-alphanum value (not in a strip-list key) is still UUID-like
        # and should be nulled out so it can't be used as a key on the target.
        before = {"misc": "abc123abc123abc123abc123"}
        after = portability._strip_uuids(before)
        assert after["misc"] is None

    def test_non_uuid_strings_preserved(self):
        before = {"name": "translator", "domain": "translator.vps1.ocoron.com"}
        assert portability._strip_uuids(before) == before


# ---------------------------------------------------------------------------
# Secrets redaction
# ---------------------------------------------------------------------------


class TestSensitiveFieldRedaction:
    """Convergence-pass regression guard (T4-03 2026-05-16 fix).

    Initial implementation of `_collect_authelia` / `_collect_backrest`
    bundled their on-VPS configs as-is. Live probe revealed Authelia's
    ``configuration.yml`` carries inline ``jwt_secret``, ``session.secret``,
    ``encryption_key``; Backrest's ``config.json`` carries
    ``repos[].password`` (restic encryption), ``repos[].env`` (S3 creds),
    and ``auth.users`` (web-UI auth). All would have leaked.

    These tests lock in the YAML/JSON-aware redactor so future
    contributions can't regress: every sensitive-keyed field must be
    replaced with ``"REDACTED"`` before the file enters the bundle.
    """

    def test_redactor_strips_authelia_inline_secrets(self):
        sample = {
            "default_redirection_url": "https://login.example.com",
            "session": {
                "secret": "REAL_SESSION_SECRET_abc123",
                "name": "authelia_session",
            },
            "storage": {
                "encryption_key": "REAL_ENCRYPTION_KEY_xyz",
                "local": {"path": "/config/db.sqlite3"},
            },
            "identity_validation": {
                "reset_password": {
                    "jwt_secret": "REAL_JWT_SECRET_qqq",
                },
            },
            "access_control": {
                "default_policy": "deny",
                "rules": [{"domain": "ocoron.com", "policy": "bypass"}],
            },
        }
        result = portability._redact_sensitive_fields(sample)
        # Two field-level redactions (session.secret, storage.encryption_key)
        assert result["session"]["secret"] == "REDACTED"
        assert result["storage"]["encryption_key"] == "REDACTED"
        # The whole identity_validation.reset_password subtree → REDACTED
        # because "reset_password" matches the conservative 'password'
        # pattern. This is intentional over-redaction — better to nuke
        # an entire password-related section than risk leaking a nested
        # secret. Operator re-creates from documentation on target.
        assert result["identity_validation"]["reset_password"] == "REDACTED"
        # Structural fields preserved
        assert result["session"]["name"] == "authelia_session"
        assert result["storage"]["local"]["path"] == "/config/db.sqlite3"
        assert result["access_control"]["rules"][0]["domain"] == "ocoron.com"
        # Defence-in-depth: serialized form has none of the actual secrets
        serialized = json.dumps(result)
        for live_secret in (
            "REAL_SESSION_SECRET_abc123",
            "REAL_ENCRYPTION_KEY_xyz",
            "REAL_JWT_SECRET_qqq",
        ):
            assert live_secret not in serialized, f"redactor missed {live_secret!r}"

    def test_redactor_strips_backrest_repo_secrets(self):
        sample = {
            "version": 4,
            "instance": "fabrik",
            "repos": [
                {
                    "id": "main",
                    "uri": "s3:https://s3.backblazeb2.com/bucket-1/path",
                    "password": "REAL_RESTIC_PASSWORD_456",
                    "env": ["AWS_ACCESS_KEY_ID=AKIAREAL", "AWS_SECRET_ACCESS_KEY=REAL_SECRET"],
                    "flags": ["--insecure-tls"],
                    "prunePolicy": {"keepDaily": 7},
                },
            ],
            "plans": [{"id": "daily", "schedule": "0 3 * * *"}],
            "auth": {"users": [{"name": "ozgur", "passwordBcrypt": "$2a$12$abc"}]},
        }
        result = portability._redact_sensitive_fields(sample)
        repo = result["repos"][0]
        # Sensitive fields → REDACTED
        assert repo["password"] == "REDACTED"
        assert repo["env"] == "REDACTED"
        assert result["auth"] == "REDACTED"
        # Structural fields preserved
        assert repo["uri"] == "s3:https://s3.backblazeb2.com/bucket-1/path"
        assert repo["id"] == "main"
        assert repo["flags"] == ["--insecure-tls"]
        assert repo["prunePolicy"]["keepDaily"] == 7
        assert result["plans"][0]["id"] == "daily"
        # Defence-in-depth: serialized form has none of the actual secrets
        serialized = json.dumps(result)
        for live_secret in (
            "REAL_RESTIC_PASSWORD_456",
            "AKIAREAL",
            "REAL_SECRET",
            "$2a$12$abc",
        ):
            assert live_secret not in serialized, f"redactor missed {live_secret!r}"

    def test_key_is_sensitive_matches_common_patterns(self):
        for k in (
            "password",
            "PASSWORD",
            "db_password",
            "secret",
            "jwt_secret",
            "API_KEY",
            "private_key",
            "token",
            "github_token",
            "credentials",
            "encryption_key",
        ):
            assert portability._key_is_sensitive(k), f"missed sensitive key: {k}"
        for k in ("uri", "id", "name", "domain", "policy", "schedule", "flags"):
            assert not portability._key_is_sensitive(k), f"false-positive: {k}"


_PEM_BODY = "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7"


class TestPrivateKeyRedaction:
    """W-fc5aee9a: invariant 3 (NO private keys) holds whatever the key is called."""

    def test_redactor_removes_pem_private_key_under_any_key(self):
        pem = f"-----BEGIN PRIVATE KEY-----\n{_PEM_BODY}\n-----END PRIVATE KEY-----\n"
        sample = {
            "identity_providers": {
                "oidc": {"jwks": [{"key_id": "main", "algorithm": "RS256", "material": pem}]}
            }
        }
        out = portability._redact_sensitive_fields(sample)
        jwk = out["identity_providers"]["oidc"]["jwks"][0]
        assert jwk["material"] == "REDACTED"
        assert jwk["key_id"] == "main"
        assert jwk["algorithm"] == "RS256"
        assert _PEM_BODY not in json.dumps(out)

    @pytest.mark.parametrize(
        "value",
        [
            "-----BEGIN PRIVATE KEY-----\nX\n-----END PRIVATE KEY-----",
            "-----BEGIN ENCRYPTED PRIVATE KEY-----\nX",
            "-----BEGIN RSA PRIVATE KEY-----\nX",
            "-----BEGIN EC PRIVATE KEY-----\nX",
            "-----BEGIN DSA PRIVATE KEY-----\nX",
            "-----BEGIN OPENSSH PRIVATE KEY-----\nX",
            "-----BEGIN PGP PRIVATE KEY BLOCK-----\nX",
            "---- BEGIN SSH2 ENCRYPTED PRIVATE KEY ----\nX",
            "----- BEGIN PRIVATE KEY -----\nX",
            "-----BEGIN  RSA  PRIVATE  KEY-----\nX",
            "-----BEGIN\tPRIVATE\tKEY-----\nX",
            "-----BEGIN RSA PRIVATE\nKEY-----\nX",
            "-----begin private key-----\nx",
            "X\n-----END PRIVATE KEY-----",
            "prefix text -----BEGIN PRIVATE KEY----- X",
            b"-----BEGIN PRIVATE KEY-----\nX",
        ],
    )
    def test_redactor_pem_spellings(self, value):
        out = portability._redact_sensitive_fields({"blob": value, "list": ["ok", value]})
        assert out == {"blob": "REDACTED", "list": ["ok", "REDACTED"]}

    @pytest.mark.parametrize(
        "value",
        [
            "-----BEGIN CERTIFICATE-----\nX\n-----END CERTIFICATE-----",
            "-----BEGIN PUBLIC KEY-----\nX\n-----END PUBLIC KEY-----",
            "-----BEGIN RSA PUBLIC KEY-----\nX",
            "https://auth.example.com/.well-known/jwks.json",
        ],
    )
    def test_redactor_keeps_public_pem(self, value):
        assert portability._redact_sensitive_fields({"blob": value}) == {"blob": value}

    def test_key_is_sensitive_bare_key(self):
        sample = {
            "a": {"key": f"-----BEGIN PRIVATE KEY-----\n{_PEM_BODY}"},
            "b": {"key": {"kty": "RSA", "d": "c2VjcmV0"}},
            "c": {"key": _PEM_BODY},
        }
        out = portability._redact_sensitive_fields(sample)
        assert out == {"a": {"key": "REDACTED"}, "b": {"key": "REDACTED"}, "c": {"key": "REDACTED"}}
        assert portability._key_is_sensitive("key")
        assert portability._key_is_sensitive("KEY")
        for k in ("keyring", "key_id", "monkey"):
            assert not portability._key_is_sensitive(k), f"false-positive: {k}"

    def test_redactor_backrest_priv_keys(self):
        sample = {
            "multihost": {"identity": {"keyid": "k1", "ed25519priv": "QUJD"}},
            "sync": {"privkey": True, "peer": "vps2"},
        }
        out = portability._redact_sensitive_fields(sample)
        assert out["multihost"] == "REDACTED"
        assert out["sync"] == {"privkey": "REDACTED", "peer": "vps2"}
        assert portability._key_is_sensitive("ed25519priv")

    @pytest.mark.parametrize(
        "doc",
        ["a:\n  1: x\n", "a:\n  yes: x\n", "a:\n  null: x\n", "a:\n  !!binary aGk=: x\n"],
    )
    def test_redactor_non_string_keys(self, doc, caplog):
        import yaml

        parsed = yaml.safe_load(doc)
        (orig_key,) = parsed["a"]
        assert not isinstance(orig_key, str)
        with caplog.at_level("WARNING", logger="fabrik.portability"):
            out = portability._redact_sensitive_fields(parsed)
        (new_key,) = out["a"]
        assert type(new_key) is type(orig_key)
        assert out["a"][new_key] == "REDACTED"
        assert "non-string" in caplog.text

    def test_collect_authelia_keeps_section_with_non_string_key(self, monkeypatch):
        raw = "server:\n  port: 9091\nrules:\n  1: hunter2\n"
        monkeypatch.setattr(portability, "_ssh_cat", lambda path: raw)
        out = portability._collect_authelia()["authelia/configuration.yml"]
        assert "9091" in out
        assert "hunter2" not in out


class TestCollectAuthelia:
    def test_live_bind_mount_path_probed_first_and_read(self, monkeypatch):
        live = "/opt/authelia/config/configuration.yml"
        probed: list[str] = []

        def fake_cat(path):
            probed.append(path)
            return "jwt_secret: hunter2\nserver:\n  port: 9091\n" if path == live else None

        monkeypatch.setattr(portability, "_ssh_cat", fake_cat)
        out = portability._collect_authelia()
        assert probed[0] == live
        assert out["authelia/configuration.yml"]
        assert "hunter2" not in out["authelia/configuration.yml"]
        assert "9091" in out["authelia/configuration.yml"]


class TestSecretsRedaction:
    def test_only_key_names_emitted_never_values(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text(
            "# Comment\n"
            "OTHER_API_TOKEN=actually-secret-value\n"
            "CLOUDFLARE_API_TOKEN=cloudflare-secret\n"
            "STRIPE_SECRET_KEY=sk_live_abc123\n"
            "\n"
            "# blank-line above\n"
            "WP_SUPER_ADMIN_PASSWORD=correcthorsebatterystaple\n",
            encoding="utf-8",
        )
        result = portability._redact_env_keys(env)
        assert result == {
            "CLOUDFLARE_API_TOKEN": "REDACTED",
            "OTHER_API_TOKEN": "REDACTED",
            "STRIPE_SECRET_KEY": "REDACTED",
            "WP_SUPER_ADMIN_PASSWORD": "REDACTED",
        }
        # Defence-in-depth: the values must not appear anywhere in the
        # redacted dict's serialized form.
        serialized = json.dumps(result)
        for secret in (
            "actually-secret-value",
            "cloudflare-secret",
            "sk_live_abc123",
            "correcthorsebatterystaple",
        ):
            assert secret not in serialized, f"value {secret!r} leaked into redacted output"

    def test_empty_env_returns_empty_dict(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("# only comments\n# nothing else\n", encoding="utf-8")
        assert portability._redact_env_keys(env) == {}

    def test_missing_env_file_returns_empty_dict(self, tmp_path):
        assert portability._redact_env_keys(tmp_path / "nonexistent.env") == {}

    def test_malformed_lines_silently_skipped(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("not an env var\nKEY=val\n1BAD=val\n_OK=val\n", encoding="utf-8")
        result = portability._redact_env_keys(env)
        # KEY and _OK are valid env-var names; 1BAD starts with digit so invalid;
        # "not an env var" has no '=' so skipped.
        assert "KEY" in result
        assert "_OK" in result
        assert "1BAD" not in result


# ---------------------------------------------------------------------------
# Local file collection
# ---------------------------------------------------------------------------


class TestCollectLocal:
    def _setup_repo(self, tmp_path: Path) -> Path:
        """Build a fake fabrik repo with specs + state."""
        (tmp_path / "specs" / "services").mkdir(parents=True)
        (tmp_path / "specs" / "services" / "a.yaml").write_text("id: a\n")
        (tmp_path / "specs" / "services" / "b.yaml").write_text("id: b\n")
        (tmp_path / ".fabrik" / "state").mkdir(parents=True)
        (tmp_path / ".fabrik" / "state" / "a.json").write_text(
            json.dumps(
                {
                    "applied_at": "2026-05-16T00:00:00+00:00",
                    "coolify_uuid": "abc" * 8,  # must be stripped
                    "registrars_applied": [{"type": "postgres", "id": "a", "data_bearing": True}],
                }
            )
        )
        return tmp_path

    def test_collect_specs(self, tmp_path):
        root = self._setup_repo(tmp_path)
        out = portability._collect_specs(root)
        assert "specs/services/a.yaml" in out
        assert "specs/services/b.yaml" in out

    def test_collect_state_strips_coolify_uuid(self, tmp_path):
        root = self._setup_repo(tmp_path)
        out = portability._collect_state(root)
        assert "a" in out
        # CRITICAL: coolify_uuid must NOT survive.
        assert "coolify_uuid" not in out["a"]
        # Other fields preserved.
        assert out["a"]["registrars_applied"][0]["type"] == "postgres"


# ---------------------------------------------------------------------------
# End-to-end bundle creation
# ---------------------------------------------------------------------------


class TestExportBundle:
    def _setup_repo(self, tmp_path: Path) -> Path:
        (tmp_path / "specs" / "services").mkdir(parents=True)
        (tmp_path / "specs" / "services" / "demo.yaml").write_text(
            "id: demo\ndomain: demo.vps1.ocoron.com\n"
        )
        (tmp_path / ".fabrik" / "state").mkdir(parents=True)
        (tmp_path / ".fabrik" / "state" / "demo.json").write_text(
            json.dumps(
                {
                    "applied_at": "2026-05-16T00:00:00+00:00",
                    "coolify_uuid": "abc" * 8,
                    "registrars_applied": [],
                }
            )
        )
        (tmp_path / "configs" / "grafana" / "dashboards").mkdir(parents=True)
        (tmp_path / "configs" / "grafana" / "dashboards" / "d.json").write_text("{}")
        (tmp_path / ".env").write_text(
            "FAKE_TOKEN=should-never-appear\nOTHER_API_TOKEN=also-secret\n"
        )
        return tmp_path

    def test_tarball_created_and_contains_required_sections(self, tmp_path):
        root = self._setup_repo(tmp_path)
        out = tmp_path / "bundle.tar.gz"
        portability.export_bundle(
            out,
            fabrik_root=root,
            skip_remote=True,
        )
        assert out.exists()
        with tarfile.open(out, "r:gz") as tar:
            names = set(tar.getnames())
        # Required top-level entries
        for required in (
            "manifest.json",
            "README.md",
            "secrets-redacted.json",
            "specs/services/demo.yaml",
            "state/demo.json",
        ):
            assert required in names, f"missing required entry: {required}"
        # D6: the Coolify section is gone — no member under coolify/.
        assert not [n for n in names if n.startswith("coolify/")]

    def test_tarball_contains_no_plaintext_secrets(self, tmp_path):
        """SECURITY INVARIANT: scan every byte of the bundle for the secret
        values that lived in .env. None must appear."""
        root = self._setup_repo(tmp_path)
        out = tmp_path / "bundle.tar.gz"
        portability.export_bundle(out, fabrik_root=root, skip_remote=True)
        body = out.read_bytes()
        # tarballs are gzipped — extract everything and concat for the scan.
        with tarfile.open(out, "r:gz") as tar:
            concat = b""
            for member in tar.getmembers():
                f = tar.extractfile(member)
                if f is not None:
                    concat += f.read()
        for forbidden in (b"should-never-appear", b"also-secret"):
            assert forbidden not in concat, f"plaintext secret leaked: {forbidden!r}"
            assert forbidden not in body, f"plaintext secret in gzip stream: {forbidden!r}"

    def test_tarball_contains_no_legacy_uuids(self, tmp_path):
        """SECURITY INVARIANT: no state-file UUID survives the export."""
        root = self._setup_repo(tmp_path)
        out = tmp_path / "bundle.tar.gz"
        portability.export_bundle(out, fabrik_root=root, skip_remote=True)
        with tarfile.open(out, "r:gz") as tar:
            for member in tar.getmembers():
                if not member.name.startswith("state/"):
                    continue
                f = tar.extractfile(member)
                if f is None:
                    continue
                content = f.read().decode("utf-8")
                for uuid_marker in (
                    "abcabcabcabcabcabcabcabc",  # state coolify_uuid
                ):
                    assert uuid_marker not in content, (
                        f"UUID {uuid_marker!r} leaked into {member.name}"
                    )

    def test_secrets_redacted_json_has_keys_only(self, tmp_path):
        root = self._setup_repo(tmp_path)
        out = tmp_path / "bundle.tar.gz"
        portability.export_bundle(out, fabrik_root=root, skip_remote=True)
        with tarfile.open(out, "r:gz") as tar:
            f = tar.extractfile("secrets-redacted.json")
            assert f is not None
            data = json.loads(f.read().decode("utf-8"))
        assert data == {"OTHER_API_TOKEN": "REDACTED", "FAKE_TOKEN": "REDACTED"}

    def test_manifest_lists_sections_and_marks_import_untested(self, tmp_path):
        root = self._setup_repo(tmp_path)
        out = tmp_path / "bundle.tar.gz"
        portability.export_bundle(out, fabrik_root=root, skip_remote=True)
        with tarfile.open(out, "r:gz") as tar:
            f = tar.extractfile("manifest.json")
            assert f is not None
            manifest = json.loads(f.read().decode("utf-8"))
        assert manifest["version"] == portability.BUNDLE_VERSION
        assert "import" in manifest["untested_paths"]
        assert manifest["sections"]["specs"] == 1
        assert manifest["sections"]["state"] == 1
        assert "coolify" not in manifest["sections"]

    def test_coolify_client_parameter_is_gone(self, tmp_path):
        with pytest.raises(TypeError):
            portability.export_bundle(
                tmp_path / "x.tar.gz", fabrik_root=tmp_path, coolify_client=object()
            )

    def test_readme_names_ssh_compose_and_no_coolify(self, tmp_path):
        root = self._setup_repo(tmp_path)
        out = tmp_path / "bundle.tar.gz"
        portability.export_bundle(out, fabrik_root=root, skip_remote=True)
        with tarfile.open(out, "r:gz") as tar:
            f = tar.extractfile("README.md")
            assert f is not None
            readme = f.read().decode("utf-8")
        assert "coolify" not in readme.lower()
        assert "SSH" in readme
        assert "Compose" in readme
        assert "does not apply anything" in readme
        assert "fabrik apply specs/services/<id>.yaml" in readme
        assert "fabrik audit-registrars" in readme


# ---------------------------------------------------------------------------
# Import (dry-run / mocked)
# ---------------------------------------------------------------------------


class TestImportBundle:
    def _make_bundle(self, tmp_path):
        root = tmp_path / "src-fab"
        root.mkdir()
        (root / "specs" / "services").mkdir(parents=True)
        (root / "specs" / "services" / "demo.yaml").write_text("id: demo\n")
        (root / ".env").write_text("DEMO_KEY=val\n")
        bundle = tmp_path / "b.tar.gz"
        portability.export_bundle(bundle, fabrik_root=root, skip_remote=True)
        return bundle

    def test_dry_run_returns_plan_without_executing(self, tmp_path):
        bundle = self._make_bundle(tmp_path)
        plan = portability.import_bundle(bundle, dry_run=True)
        assert plan["dry_run"] is True
        assert plan["sections"]["specs"] == 1
        assert plan["secrets_to_repopulate"] == ["DEMO_KEY"]
        assert any(a.get("phase") == "noop" for a in plan["actions"])

    def test_apply_returns_stub_plan(self, tmp_path):
        bundle = self._make_bundle(tmp_path)
        plan = portability.import_bundle(bundle, dry_run=False)
        assert plan["dry_run"] is False
        assert any(
            a.get("phase") == "real_run" and a.get("status") == "stub" for a in plan["actions"]
        )

    def _legacy_bundle(self, tmp_path):
        bundle = tmp_path / "legacy.tar.gz"
        with tarfile.open(bundle, "w:gz") as tar:
            for name in ("manifest.json", "coolify/applications.json", "coolify/services.json"):
                data = b"{}"
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        return bundle

    def test_legacy_coolify_members_counted_not_sectioned(self, tmp_path):
        plan = portability.import_bundle(self._legacy_bundle(tmp_path), dry_run=True)
        assert plan["ignored_legacy"] == 2
        assert "coolify" not in plan["sections"]

    def test_legacy_count_is_regular_files_and_normalises_dot_slash(self, tmp_path):
        bundle = tmp_path / "legacy2.tar.gz"
        with tarfile.open(bundle, "w:gz") as tar:
            d = tarfile.TarInfo(name="coolify")
            d.type = tarfile.DIRTYPE
            tar.addfile(d)
            for name in ("coolify/a.json", "./coolify/b.json"):
                info = tarfile.TarInfo(name=name)
                info.size = 2
                tar.addfile(info, io.BytesIO(b"{}"))
            sym = tarfile.TarInfo(name="coolify/link.json")
            sym.type = tarfile.SYMTYPE
            sym.linkname = "a.json"
            tar.addfile(sym)
            hard = tarfile.TarInfo(name="coolify/hard.json")
            hard.type = tarfile.LNKTYPE
            hard.linkname = "coolify/a.json"
            tar.addfile(hard)
        plan = portability.import_bundle(bundle, dry_run=True)
        assert plan["ignored_legacy"] == 4

    def test_dot_slash_names_normalised_for_sections_and_legacy(self, tmp_path):
        bundle = tmp_path / "dot.tar.gz"
        with tarfile.open(bundle, "w:gz") as tar:
            for name in ("./specs/a.yaml", "./coolify/b.json"):
                info = tarfile.TarInfo(name=name)
                info.size = 2
                tar.addfile(info, io.BytesIO(b"{}"))
        plan = portability.import_bundle(bundle, dry_run=True)
        assert plan["sections"]["specs"] == 1
        assert plan["ignored_legacy"] == 1

    def test_dot_slash_manifest_and_secrets_are_read(self, tmp_path):
        bundle = tmp_path / "dot.tar.gz"
        members = {
            "./manifest.json": json.dumps({"version": 1}).encode(),
            "./secrets-redacted.json": json.dumps(
                {"B_KEY": "<redacted>", "A_KEY": "<redacted>"}
            ).encode(),
        }
        with tarfile.open(bundle, "w:gz") as tar:
            for name, body in members.items():
                info = tarfile.TarInfo(name=name)
                info.size = len(body)
                tar.addfile(info, io.BytesIO(body))
        plan = portability.import_bundle(bundle, dry_run=True)
        assert plan["manifest"] == {"version": 1}
        assert plan["secrets_to_repopulate"] == ["A_KEY", "B_KEY"]

    def test_clean_bundle_has_no_ignored_legacy_key(self, tmp_path):
        plan = portability.import_bundle(self._make_bundle(tmp_path), dry_run=True)
        assert "ignored_legacy" not in plan

    def test_import_coolify_client_parameter_is_gone(self, tmp_path):
        with pytest.raises(TypeError):
            portability.import_bundle(
                self._make_bundle(tmp_path), dry_run=True, coolify_client=object()
            )

    def test_cli_import_prints_ignored_legacy_line(self, tmp_path):
        # `import` is a dry run by default (no --dry-run flag exists).
        result = CliRunner().invoke(cli, ["import", str(self._legacy_bundle(tmp_path))])
        assert result.exit_code == 0, result.output
        assert "ignored legacy members (coolify/*): 2" in result.output

    def test_missing_bundle_raises_clear_error(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            portability.import_bundle(tmp_path / "nope.tar.gz", dry_run=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestExportCli:
    def test_export_help_exits_zero(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["export", "--help"])
        assert result.exit_code == 0
        assert "T4-03" in result.output or "portable bundle" in result.output

    def test_import_help_exits_zero(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["import", "--help"])
        assert result.exit_code == 0
        assert "DRY-RUN" in result.output or "dry-run" in result.output

    def test_export_then_import_dry_run_via_cli(self, tmp_path):
        """End-to-end CLI smoke test on the real fabrik repo.

        Notes on the boundary: the CLI's ``export`` resolves ``FABRIK_ROOT``
        from ``fabrik.config`` at module-import time, so a tmp_path
        monkeypatch on ``portability.FABRIK_ROOT`` doesn't affect it.
        Rather than build a synthetic fabrik-root (which would require
        patching every consumer's import-time alias), we exercise the CLI
        end-to-end on the live repo and assert the security invariants:

        - Bundle gets created with exit 0.
        - Import dry-run parses the bundle and produces a plan.
        - The plan flags secrets-to-repopulate via the manifest path.

        The ``--skip-remote`` flag suppresses VPS-side ssh pulls, so the
        export needs no network.
        """
        bundle = tmp_path / "out.tar.gz"
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["export", "-o", str(bundle), "--skip-remote"],
        )
        assert result.exit_code == 0, result.output
        assert bundle.exists()
        assert "Bundle saved" in result.output

        result = runner.invoke(cli, ["import", str(bundle)])
        assert result.exit_code == 0, result.output
        assert "DRY RUN" in result.output
        assert "Re-populate" in result.output or "secrets" in result.output.lower()

    def test_import_missing_bundle_exit_1(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["import", str(tmp_path / "nope.tar.gz")])
        assert result.exit_code == 2  # click: path must exist
