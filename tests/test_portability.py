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


# Built at runtime so the repo's detect-private-key hook never sees the armour
# spellings it blocks (fixed, exact-case header strings, single-spaced).
_PK = "PRIVATE" + " KEY"
_PEM_BODY = "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7"


class TestPrivateKeyRedaction:
    """W-fc5aee9a: invariant 3 (NO private keys) holds for an armoured key under any name."""

    def test_redactor_removes_pem_private_key_under_any_key(self):
        pem = f"-----BEGIN {_PK}-----\n{_PEM_BODY}\n-----END {_PK}-----\n"
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
            f"-----BEGIN {_PK}-----\nX\n-----END {_PK}-----",
            f"-----BEGIN ENCRYPTED {_PK}-----\nX",
            f"-----BEGIN RSA {_PK}-----\nX",
            f"-----BEGIN EC {_PK}-----\nX",
            f"-----BEGIN DSA {_PK}-----\nX",
            f"-----BEGIN OPENSSH {_PK}-----\nX",
            f"-----BEGIN PGP {_PK} BLOCK-----\nX",
            f"---- BEGIN SSH2 ENCRYPTED {_PK} ----\nX",
            f"----- BEGIN {_PK} -----\nX",
            "-----BEGIN  RSA  PRIVATE  KEY-----\nX",
            "-----BEGIN\tPRIVATE\tKEY-----\nX",
            "-----BEGIN RSA PRIVATE\nKEY-----\nX",
            "-----begin private key-----\nx",
            f"X\n-----END {_PK}-----",
            f"prefix text -----BEGIN {_PK}----- X",
            f"-----BEGIN {_PK}-----\nX".encode(),
            f"-----BEGIN X9.42 DH {_PK}-----\nX",
            "-----BEGIN\xa0PRIVATE\xa0KEY-----\nX",
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
            "backend private key rotation runs weekly",
            "Begin by uploading your private key",
        ],
    )
    def test_redactor_keeps_public_pem_and_prose(self, value):
        assert portability._redact_sensitive_fields({"blob": value}) == {"blob": value}

    def test_pem_search_is_linear_on_long_values(self):
        import time

        # The unbounded label loop took ~5 s on the first value; bounded it is milliseconds.
        for value in (
            "BEGIN " * 8_000,
            "-----END PRIVATE " * 8_000,
            "----- BEGIN " + "a " * 50_000,
            "-" * 20_000,  # an open-ended dash prefix is retried at every dash (~5 s)
        ):
            start = time.perf_counter()
            portability._redact_sensitive_fields({"blob": value})
            assert time.perf_counter() - start < 1.0

    def test_private_key_as_mapping_key_is_redacted(self):
        import yaml

        pem = f"-----BEGIN {_PK}-----\n{_PEM_BODY}\n-----END {_PK}-----\n"
        for key in (pem, pem.encode()):
            out = portability._redact_sensitive_fields({"a": {key: "x", "port": 1}})
            assert out == {"a": {"REDACTED": "REDACTED", "port": 1}}
            assert _PEM_BODY not in yaml.safe_dump(out)

    @pytest.mark.parametrize(
        ("doc", "expected"),
        [
            (f"a: !!set {{'-----BEGIN {_PK}-----': null}}\n", "REDACTED"),
            ("a: !!omap [{jwt_secret: hunter2}]\n", ["REDACTED"]),  # a list of (k, v) tuples
            (f"a: !!pairs [{{m: '-----BEGIN {_PK}-----'}}]\n", ["REDACTED"]),
        ],
    )
    def test_redactor_unknown_containers_fail_closed(self, doc, expected):
        import yaml

        out = portability._redact_sensitive_fields(yaml.safe_load(doc))
        assert out == {"a": expected}

    def test_key_is_sensitive_bare_key(self):
        sample = {
            "a": {"key": f"-----BEGIN {_PK}-----\n{_PEM_BODY}"},
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
            "multihost": {
                "identity": {"keyid": "k1", "ed25519priv": "QUJD"},
                "knownHosts": [{"instanceId": "vps2", "keyid": "k2"}],
            },
            "sync": {"privkey": True, "private_key": "x", "peer": "vps2"},
        }
        out = portability._redact_sensitive_fields(sample)
        assert out["multihost"]["identity"] == {"keyid": "k1", "ed25519priv": "REDACTED"}
        assert out["multihost"]["knownHosts"] == sample["multihost"]["knownHosts"]
        assert out["sync"] == {"privkey": "REDACTED", "private_key": "REDACTED", "peer": "vps2"}
        for k in ("privacy_policy", "privileged"):
            assert not portability._key_is_sensitive(k), f"false-positive: {k}"

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


_AM_YML = """global:
  resolve_timeout: 5m
  smtp_auth_password: LEAK_AM1
  slack_api_url: https://hooks.slack.com/services/T0/B0/LEAK_AM2
time_intervals:
- name: offhours
  time_intervals:
  - times:
    - start_time: 17:00
      end_time: 24:00
receivers:
- name: pd
  pagerduty_configs:
  - routing_key: LEAK_AM3
    service_key: LEAK_AM4
- name: po
  pushover_configs:
  - user_key: LEAK_AM5
    token: LEAK_AM6
- name: mail
  email_configs:
  - to: ops@example.com
    headers:
      X-Auth: LEAK_AM7
"""

_PROM_YML = """global:
  scrape_interval: 15s
remote_write:
- url: https://user:LEAK_P1@remote.example/api/v1/write
  headers:
    Authorization: Bearer LEAK_P2
remote_read:
- url: https://remote.example/read
  headers:
    X-Scope-Token: LEAK_P3
scrape_configs:
- job_name: node
  basic_auth:
    username: u
    password: LEAK_P4
  proxy_connect_header:
    Proxy-Authorization: [LEAK_P5]
  oauth2:
    client_id: c
    endpoint_params:
      client_assertion: LEAK_P6
  static_configs:
  - targets: ['node-exporter:9100']
"""


class TestMonitoringRedaction:
    """W-64cf1856: the VPS monitoring configs and Backrest hooks ship redacted (invariant 1)."""

    @staticmethod
    def _remote(monkeypatch, files):
        def fake_cat(path):
            for name, text in files.items():
                if path.endswith(name):
                    return text
            return None

        monkeypatch.setattr(portability, "_ssh_cat", fake_cat)
        return portability._collect_monitoring_remote()

    def test_monitoring_files_redact_planted_secrets(self, monkeypatch):
        import yaml

        out = self._remote(monkeypatch, {"alertmanager.yml": _AM_YML, "prometheus.yml": _PROM_YML})
        blob = "\n".join(out.values())
        leaked = [m for m in ("LEAK_AM", "LEAK_P") if m in blob]
        assert leaked == [], blob
        am = yaml.safe_load(out["monitoring/alertmanager.yml"])
        prom = yaml.safe_load(out["monitoring/prometheus.yml"])
        # Structure survives for the operator's restore reference.
        assert am["global"]["resolve_timeout"] == "5m"
        assert am["receivers"][2]["email_configs"][0]["to"] == "ops@example.com"
        assert prom["remote_write"][0]["url"] == "https://REDACTED@remote.example/api/v1/write"
        assert prom["remote_read"][0]["url"] == "https://remote.example/read"
        assert prom["scrape_configs"][0]["basic_auth"]["username"] == "u"
        assert prom["scrape_configs"][0]["static_configs"][0]["targets"] == ["node-exporter:9100"]

    @pytest.mark.parametrize(
        "bad",
        [
            "a: [unclosed\npassword: leak\n",
            "a: 1\n---\nb: 2\n",
            "hunter2\n",
            "42\n",
            "a: !custom x\n",
        ],
    )
    def test_unparseable_or_scalar_monitoring_file_is_omitted(self, monkeypatch, caplog, bad):
        files = {
            "prometheus.yml": bad,
            "alertmanager.yml": "global:\n  resolve_timeout: 5m\n",
            "allocations.json": '"password=hunter2"',
            "assignments.json": "{nope",
        }
        with caplog.at_level("WARNING", logger="fabrik.portability"):
            out = self._remote(monkeypatch, files)
        assert set(out) == {"monitoring/alertmanager.yml"}
        assert "omitting" in caplog.text
        assert "hunter2" not in "".join(out.values())

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("https://u:pw@h.example/x", "https://REDACTED@h.example/x"),
            ("telegram://tok@telegram?chats=1", "telegram://REDACTED@telegram?chats=1"),
            ("https://u:p@ss@h.example/w", "https://REDACTED@h.example/w"),
            ("redis://:pw@redis-main:6379/0", "redis://REDACTED@redis-main:6379/0"),
            (
                "a https://u:1@x/ and smtp://v:2@y:587",
                "a https://REDACTED@x/ and smtp://REDACTED@y:587",
            ),
            ("https://h.example/path@x", "https://h.example/path@x"),
            ("https://h.example?q=a@b", "https://h.example?q=a@b"),
            ("ops@example.com", "ops@example.com"),
        ],
    )
    def test_url_userinfo_redacted_any_key(self, value, expected):
        out = portability._redact_sensitive_fields({"anything": value, "list": [value]})
        assert out == {"anything": expected, "list": [expected]}

    def test_backrest_hook_credentials_redacted(self, monkeypatch):
        config = {
            "repos": [{"id": "r", "uri": "s3:https://ak:LEAK_B1@b2.example/bucket"}],
            "plans": [
                {
                    "id": "p",
                    "hooks": [
                        {
                            "actionShoutrrr": {
                                "shoutrrrUrl": "smtp://user:LEAK_B2@mail.example:587/?to=a@b.c",
                                "template": "{{ .Summary }}",
                            }
                        },
                        {"actionCommand": {"command": "curl -u u:LEAK_B3 https://x"}},
                        {"actionGotify": {"baseUrl": "https://u:LEAK_B4@gotify.example"}},
                    ],
                }
            ],
        }
        monkeypatch.setattr(portability, "_ssh_cat", lambda path: json.dumps(config))
        out = portability._collect_backrest()["backrest/config.json"]
        assert "LEAK_B" not in out
        parsed = json.loads(out)
        assert parsed["repos"][0]["uri"] == "s3:https://REDACTED@b2.example/bucket"
        shoutrrr = parsed["plans"][0]["hooks"][0]["actionShoutrrr"]
        assert shoutrrr == {"shoutrrrUrl": "REDACTED", "template": "{{ .Summary }}"}
        assert parsed["plans"][0]["hooks"][1]["actionCommand"] == {"command": "REDACTED"}

    def test_userinfo_search_is_linear(self):
        import time

        for value in (
            "://" + "a" * 400_000,
            "://a" * 100_000,
            "x@" * 200_000,
            "://" + "@" * 400_000,
        ):
            start = time.perf_counter()
            portability._redact_sensitive_fields({"blob": value})
            assert time.perf_counter() - start < 1.0

    def test_yaml_roundtrip_keeps_scalars(self, monkeypatch):
        import yaml

        # Every plain scalar comes back as written, so the Go parser that reads
        # the restored copy sees the operator's bytes whatever type it decodes to.
        raw = (
            "times:\n- start_time: 17:00\n  end_time: 24:00\n"
            "send_resolved: yes\nflag: on\nmode: 010\nhex: 0x1F\nunder: 1_000\n"
            "version: 1.10\nratio: .50\ne: 6.02e23\nneg: -0\nbig: 1e400\n"
            "t: 2026-04-18T10:00:00Z\nempty:\nnul: null\ntilde: ~\nb: true\nport: 9091\n"
            "qempty: ''\nquoted: '123'\ndq: 'on'\n"
            "message: |\n  line one\n  line two\n"
        )
        out = self._remote(monkeypatch, {"prometheus.yml": raw})["monitoring/prometheus.yml"]
        assert out == raw
        # An explicit tag keeps its meaning: a !!str stays a quoted string.
        out = self._remote(monkeypatch, {"prometheus.yml": "a: !!str 123\n"})
        assert yaml.safe_load(out["monitoring/prometheus.yml"]) == {"a": "123"}
        # Empty or comment-only files ship as an empty mapping.
        out = self._remote(monkeypatch, {"prometheus.yml": "# only a comment\n"})
        assert out["monitoring/prometheus.yml"] == "{}\n"
        # The module's loader never changes PyYAML's global SafeLoader.
        assert yaml.safe_load("a: on\nb: 17:00\n") == {"a": True, "b": 1020}

    @pytest.mark.parametrize(
        "doc",
        [
            "global:\n  smtp_auth_password: &pw hunter2\nother: *pw\n",
            "auth: &a {user: u, pass: hunter2}\nx:\n  <<: *a\n",
        ],
    )
    def test_yaml_aliases_are_refused(self, monkeypatch, caplog, doc):
        with caplog.at_level("WARNING", logger="fabrik.portability"):
            out = self._remote(monkeypatch, {"prometheus.yml": doc})
            authelia = portability._collect_authelia()
        assert out == {}
        assert authelia == {}
        assert "alias" in caplog.text

    def test_authelia_and_backrest_omit_a_bare_scalar(self, monkeypatch):
        monkeypatch.setattr(portability, "_ssh_cat", lambda path: "authelia-jwt-hunter2\n")
        assert portability._collect_authelia() == {}
        monkeypatch.setattr(portability, "_ssh_cat", lambda path: '"password=hunter2"')
        assert portability._collect_backrest() == {}

    def test_url_userinfo_in_a_mapping_key_is_redacted(self):
        out = portability._redact_sensitive_fields({"https://u:pw@h.example": 1})
        assert out == {"https://REDACTED@h.example": 1}
        # A sensitive key loses its userinfo too, not only its value.
        out = portability._redact_sensitive_fields({"https://u:pw@h/token": 1})
        assert out == {"https://REDACTED@h/token": "REDACTED"}

    @pytest.mark.parametrize(
        "doc",
        [
            '1: a\n"1": b\n',  # a plain typed key and a quoted key of the same text
            "on: a\n'on': b\n",
            "https://a:1@h: first\nhttps://b:2@h: second\n",  # equal once redacted
        ],
    )
    def test_no_mapping_entry_is_lost(self, monkeypatch, doc):
        import yaml

        out = self._remote(monkeypatch, {"prometheus.yml": doc})
        if out:
            # Both entries survive (typed keys keep their type, so they stay distinct)…
            assert len(yaml.safe_load(out["monitoring/prometheus.yml"])) == 2
        else:
            # …or the file is omitted: never one entry silently overwriting another.
            assert out == {}

    def test_a_parse_error_never_logs_the_source_line(self, monkeypatch, caplog):
        docs = (
            "x: &a 1\ncreds: {password: LOGLEAK1, copy: *a}\n",
            'password: "LOGLEAK2\nx: [\n',
            "a: !LOGLEAK3_tag x\n",  # PyYAML's problem text quotes the tag
            "a: !!python/name:LOGLEAK4 x\n",
        )
        with caplog.at_level("WARNING", logger="fabrik.portability"):
            for doc in docs:
                assert self._remote(monkeypatch, {"prometheus.yml": doc}) == {}
        assert "omitting" in caplog.text
        assert "LOGLEAK" not in caplog.text

    def test_authorization_policy_is_kept(self):
        sample = {
            "authorization": {"type": "Bearer", "credentials": "x"},
            "Proxy-Authorization": ["y"],
            "identity_providers": {
                "oidc": {"clients": [{"client_id": "c", "authorization_policy": "two_factor"}]}
            },
        }
        out = portability._redact_sensitive_fields(sample)
        assert out["authorization"] == "REDACTED"
        assert out["Proxy-Authorization"] == "REDACTED"
        client = out["identity_providers"]["oidc"]["clients"][0]
        assert client["authorization_policy"] == "two_factor"

    def test_key_patterns_for_monitoring_secrets(self):
        for k in (
            "routing_key",
            "service_key",
            "user_key",
            "secret_key",
            "userKey",
            "slack_api_url",
            "api_url",
            "headers",
            "proxy_connect_header",
            "Authorization",
            "Proxy-Authorization",
            "x-authorization",
            "api-authorization",
            "authorizations",
            "endpoint_params",
            "shoutrrrUrl",
            "command",
        ):
            assert portability._key_is_sensitive(k), f"missed sensitive key: {k}"
        for k in (
            "monkey",
            "hotkey",
            "keyring",
            "key_id",
            "template",
            "commander",
            "url",
            "to",
            "authorization_policy",
            "authorization_policies",
        ):
            assert not portability._key_is_sensitive(k), f"false-positive: {k}"


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

    def test_export_then_import_dry_run_via_cli(self, tmp_path, monkeypatch):
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

        The ``.env`` read is the one host input stubbed: ``FABRIK_ROOT`` is the current hub
        worktree, and a merge leg's throwaway tree has no ``.env``, so the secrets line this test
        reads was absent there on both sides (W-a9b3bc15). ``_redact_env_keys`` itself is covered
        by the library tests above.
        """

        def _one_key(path):
            assert path == portability.FABRIK_ROOT / ".env", path  # still read from the root's .env
            return {"DEMO_KEY": "REDACTED"}

        monkeypatch.setattr(portability, "_redact_env_keys", _one_key)
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
        assert "Re-populate 1 secrets" in result.output and "DEMO_KEY" in result.output, (
            result.output
        )

    def test_import_missing_bundle_exit_1(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["import", str(tmp_path / "nope.tar.gz")])
        assert result.exit_code == 2  # click: path must exist
