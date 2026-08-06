"""T4-03 G-J2 — `fabrik export` / `fabrik import` portability tests.

Two-layer coverage:

1. **Schema invariants** (carried over from the T4-02 skeleton) — the
   state-file schema must stay free of machine-local fields so a bundle
   written on one workstation is interpretable on another.

2. **Bundle contract** — every export must satisfy the security invariants
   from the ticket Pass-2 checklist:

   - No plaintext secret values inside the tarball.
   - No Coolify UUIDs in any exported section.
   - Bundle includes manifest.json, README.md, secrets-redacted.json.

The Coolify API surface is mocked at the ``CoolifyClient`` boundary so
tests don't require network access or a live token.
"""

from __future__ import annotations

import json
import tarfile
from pathlib import Path
from unittest.mock import MagicMock

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


class TestSecretsRedaction:
    def test_only_key_names_emitted_never_values(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text(
            "# Comment\n"
            "COOLIFY_API_TOKEN=actually-secret-value\n"
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
            "COOLIFY_API_TOKEN": "REDACTED",
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


def _fake_coolify_client():
    """Mock CoolifyClient that returns realistic payloads with UUIDs."""
    client = MagicMock()
    client.list_applications.return_value = [
        {
            "uuid": "app-uuid-aaaaaaaaaaaaaaaa",
            "name": "translator",
            "fqdn": "translator.vps1.ocoron.com",
            "destination": {"server_uuid": "srv-uuid-aaaaaaaaaaaaaaaaaa", "name": "vps1"},
        }
    ]
    client.list_services.return_value = [
        {"uuid": "svc-uuid-aaaaaaaaaaaaaaaa", "name": "authelia", "type": "authelia"},
    ]
    client.list_projects.return_value = [
        {"uuid": "prj-uuid-aaaaaaaaaaaaaaaa", "name": "fabrik-services"},
    ]
    return client


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
            "FAKE_TOKEN=should-never-appear\nCOOLIFY_API_TOKEN=also-secret\n"
        )
        return tmp_path

    def test_tarball_created_and_contains_required_sections(self, tmp_path):
        root = self._setup_repo(tmp_path)
        out = tmp_path / "bundle.tar.gz"
        portability.export_bundle(
            out,
            fabrik_root=root,
            coolify_client=_fake_coolify_client(),
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
            "coolify/applications.json",
            "coolify/services.json",
            "coolify/projects.json",
        ):
            assert required in names, f"missing required entry: {required}"

    def test_tarball_contains_no_plaintext_secrets(self, tmp_path):
        """SECURITY INVARIANT: scan every byte of the bundle for the secret
        values that lived in .env. None must appear."""
        root = self._setup_repo(tmp_path)
        out = tmp_path / "bundle.tar.gz"
        portability.export_bundle(
            out, fabrik_root=root, coolify_client=_fake_coolify_client(), skip_remote=True
        )
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

    def test_tarball_contains_no_coolify_uuids(self, tmp_path):
        """SECURITY INVARIANT: no Coolify UUID survives the export."""
        root = self._setup_repo(tmp_path)
        out = tmp_path / "bundle.tar.gz"
        portability.export_bundle(
            out, fabrik_root=root, coolify_client=_fake_coolify_client(), skip_remote=True
        )
        with tarfile.open(out, "r:gz") as tar:
            for member in tar.getmembers():
                if not member.name.startswith(("coolify/", "state/")):
                    continue
                f = tar.extractfile(member)
                if f is None:
                    continue
                content = f.read().decode("utf-8")
                for uuid_marker in (
                    "app-uuid-aaaaaaaaaaaaaaaa",
                    "srv-uuid-aaaaaaaaaaaaaaaaaa",
                    "svc-uuid-aaaaaaaaaaaaaaaa",
                    "prj-uuid-aaaaaaaaaaaaaaaa",
                    "abcabcabcabcabcabcabcabc",  # state coolify_uuid
                ):
                    assert uuid_marker not in content, (
                        f"UUID {uuid_marker!r} leaked into {member.name}"
                    )

    def test_secrets_redacted_json_has_keys_only(self, tmp_path):
        root = self._setup_repo(tmp_path)
        out = tmp_path / "bundle.tar.gz"
        portability.export_bundle(
            out, fabrik_root=root, coolify_client=_fake_coolify_client(), skip_remote=True
        )
        with tarfile.open(out, "r:gz") as tar:
            f = tar.extractfile("secrets-redacted.json")
            assert f is not None
            data = json.loads(f.read().decode("utf-8"))
        assert data == {"COOLIFY_API_TOKEN": "REDACTED", "FAKE_TOKEN": "REDACTED"}

    def test_manifest_lists_sections_and_marks_import_untested(self, tmp_path):
        root = self._setup_repo(tmp_path)
        out = tmp_path / "bundle.tar.gz"
        portability.export_bundle(
            out, fabrik_root=root, coolify_client=_fake_coolify_client(), skip_remote=True
        )
        with tarfile.open(out, "r:gz") as tar:
            f = tar.extractfile("manifest.json")
            assert f is not None
            manifest = json.loads(f.read().decode("utf-8"))
        assert manifest["version"] == portability.BUNDLE_VERSION
        assert "import" in manifest["untested_paths"]
        assert manifest["sections"]["specs"] == 1
        assert manifest["sections"]["state"] == 1


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
        portability.export_bundle(
            bundle, fabrik_root=root, coolify_client=_fake_coolify_client(), skip_remote=True
        )
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

        The Coolify client may make real API calls here. The
        ``--skip-remote`` flag suppresses VPS-side ssh pulls. If the
        Coolify token is missing or the API is down, the export still
        succeeds (best-effort per pack §28 — empty coolify section).
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
