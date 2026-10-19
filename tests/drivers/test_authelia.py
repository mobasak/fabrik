"""Unit tests for fabrik.drivers.authelia — mocked ssh + run_locked.

No network, no VPS, no Authelia container required. The live contract
is validated by the Phase 4g live smoke (see plan file).
"""

from __future__ import annotations

import base64
from unittest.mock import patch

import pytest
import yaml as yaml_lib

from fabrik.drivers import authelia
from fabrik.drivers.authelia import (
    SHAPE_FLAG,
    VALID_POLICIES,
    _build_add_script,
    _build_remove_script,
    _compute_insert_index,
    _domain_shadows,
    _validate_domain,
    _validate_policy,
    _validate_resources,
    add_access_rule,
    applies_to,
    remove_access_rule,
)

# --------------------------------------------------------------------------- #
# applies_to                                                                   #
# --------------------------------------------------------------------------- #


class TestAppliesTo:
    def test_opt_in(self):
        assert applies_to({SHAPE_FLAG: True}) is True

    def test_opt_out(self):
        assert applies_to({SHAPE_FLAG: False}) is False
        assert applies_to({}) is False

    def test_non_dict(self):
        assert applies_to(None) is False  # type: ignore[arg-type]
        assert applies_to([]) is False  # type: ignore[arg-type]

    def test_other_keys_ignored(self):
        assert applies_to({"kind": "service", SHAPE_FLAG: False}) is False


# --------------------------------------------------------------------------- #
# validators                                                                   #
# --------------------------------------------------------------------------- #


class TestValidators:
    @pytest.mark.parametrize(
        "d",
        ["coolify.vps1.ocoron.com", "a.b", "x.y.z.w", "a1-b2.example.com"],
    )
    def test_valid_domains(self, d):
        _validate_domain(d)

    @pytest.mark.parametrize(
        "d",
        [
            "",
            "-leading.example.com",
            "trailing-.example.com",
            "has space.com",
            "under_score.example.com",  # underscores not allowed in hostnames
            "a" * 254,  # > 253 total
            "*.wildcard.com",  # wildcard not valid as BARE host
        ],
    )
    def test_invalid_domains(self, d):
        with pytest.raises(ValueError):
            _validate_domain(d)

    def test_non_string_domain(self):
        with pytest.raises(ValueError):
            _validate_domain(42)  # type: ignore[arg-type]

    @pytest.mark.parametrize("p", sorted(VALID_POLICIES))
    def test_valid_policies(self, p):
        _validate_policy(p)

    @pytest.mark.parametrize("p", ["", "2fa", "two-factor", "TWO_FACTOR", "admin"])
    def test_invalid_policies(self, p):
        with pytest.raises(ValueError):
            _validate_policy(p)

    def test_resources_none_ok(self):
        _validate_resources(None)

    @pytest.mark.parametrize("r", [["^/api/"], ["^/public/", "^/webhook/"], ["^/a.*$"]])
    def test_valid_resources(self, r):
        _validate_resources(r)

    def test_resources_not_list(self):
        with pytest.raises(ValueError):
            _validate_resources("^/api/")  # type: ignore[arg-type]

    @pytest.mark.parametrize("r", [[""], ["\x00"], ["line1\nline2"], ["€uro"]])
    def test_invalid_resource_contents(self, r):
        with pytest.raises(ValueError):
            _validate_resources(r)


# --------------------------------------------------------------------------- #
# script builders — structural assertions                                      #
# --------------------------------------------------------------------------- #


class TestBuildAddScript:
    def _make(self, **kw):
        defaults = {
            "container": "authelia-xyz",
            "rule_b64": "QQ==",
            "domain": "my.example.com",
            "insert_mode": "append",
        }
        defaults.update(kw)
        return _build_add_script(**defaults)

    def test_starts_with_strict_pipefail(self):
        s = self._make()
        assert s.startswith("set -euo pipefail\n"), s[:50]

    def test_uses_shlex_quoted_container(self):
        """Container name with a space-bearing shell injection attempt
        must be shell-quoted, not interpolated raw."""
        s = self._make(container="authelia; rm -rf /")
        # shlex.quote wraps unsafe strings in single quotes
        assert "'authelia; rm -rf /'" in s
        # And the raw injection substring never appears unquoted
        assert "CONT=authelia; rm -rf /" not in s

    def test_quoted_heredoc_prevents_bash_expansion(self):
        """The Python block MUST be framed with <<'PY' (quoted).
        Without quotes, bash would expand $RULE_B64 into the Python
        body, bricking the driver."""
        s = self._make()
        assert "<<'PY'" in s
        # Sanity: no unquoted <<PY variant
        assert "<<PY\n" not in s and "<<PY " not in s

    def test_python_uses_os_environ_not_shell_interp(self):
        """Variables reach Python via os.environ — the <<'PY' heredoc
        blocks bash-side interpolation, so referencing $VAR inside would
        literally read '$VAR'. Must use os.environ['VAR']."""
        s = self._make()
        assert "os.environ['WORK']" in s
        assert "export WORK" in s  # sudo -E passes only exported variables
        assert "os.environ['RULE_B64']" in s
        assert "os.environ['DOMAIN']" in s
        assert "os.environ['INSERT_MODE']" in s

    def test_idempotent_noop_branch(self):
        """If Python prints IDEMPOTENT_NOOP and does NOT create
        $WORK/new.yml, the outer bash skips docker cp and docker
        restart — Authelia is NOT bounced for a no-op."""
        s = self._make()
        assert 'sys.stdout.write("IDEMPOTENT_NOOP\\n")' in s
        # The file-existence test that gates the restart runs under sudo: the
        # work dir is root 0700 and the ssh user cannot search it.
        assert 'if ! sudo test -f "$WORK/new.yml"; then' in s
        assert 'echo "idempotent-noop"' in s

    def test_docker_restart_happens_on_change_only(self):
        """docker restart MUST appear AFTER the idempotent-noop exit —
        never unconditionally."""
        s = self._make()
        noop_exit_idx = s.index('echo "idempotent-noop"')
        restart_idx = s.index("sudo docker restart")
        assert restart_idx > noop_exit_idx, "docker restart must only run in the non-noop branch"

    def test_timestamp_used_for_backup(self):
        s = self._make()
        assert "TS=$(date +%Y%m%d-%H%M%S)" in s
        assert (
            'sudo mktemp --suffix=.yml /var/backups/fabrik-authelia/authelia.bak."$TS".XXXXXX' in s
        )

    def test_backup_rotation_keeps_last_10(self):
        s = self._make()
        assert "tail -n +11" in s
        assert "xargs -r rm -f" in s

    def test_cleanup_uses_sudo_rm(self):
        """Regression test for the live-smoke failure 2026-04-19 19:45:
        staging files are root-owned (created via `sudo tee` /
        `sudo -E python3`). Non-sudo `rm` fails with 'Operation not
        permitted'. See LESSONS_LEARNT §8.17. The work dir is now removed
        by the EXIT trap, under sudo, keeping the script's exit code."""
        s = self._make()
        trap = [line for line in s.splitlines() if line.startswith("trap ")]
        assert trap == [
            'trap \'rc=$?; sudo rm -rf -- "$WORK" || '
            'echo "WARN: cleanup failed: $WORK" >&2; exit $rc\' EXIT'
        ], trap

    def test_round_trip_yaml_validation(self):
        """Written YAML must round-trip through yaml.safe_load BEFORE
        being cp'd into the container. A YAML emit-only bug would
        otherwise brick Authelia."""
        s = self._make()
        # The script opens new_path and calls yaml.safe_load on it
        assert "with open(new_path) as f:" in s
        # Two occurrences expected: write then validate
        assert s.count("yaml.safe_load") >= 2

    def test_before_twofactor_insertion_logic_present(self):
        s = self._make(insert_mode="before_twofactor")
        assert "before_twofactor" in s
        assert "rules.insert(idx, new_rule)" in s

    def test_append_mode_uses_rules_append(self):
        s = self._make(insert_mode="append")
        # Both modes include the else-branch append, but append-only
        # mode must not claim 'before_twofactor' behavior
        assert "rules.append(new_rule)" in s


class TestBuildRemoveScript:
    def test_filters_by_domain(self):
        s = _build_remove_script("authelia-xyz", "my.example.com")
        # Filter expression
        assert "[r for r in rules if r.get('domain') != domain]" in s

    def test_idempotent_when_no_matches(self):
        s = _build_remove_script("authelia-xyz", "my.example.com")
        # If no rules removed, skip docker cp + restart
        assert 'sys.stdout.write("IDEMPOTENT_NOOP\\n")' in s
        assert 'if ! sudo test -f "$WORK/new.yml"; then' in s

    def test_shell_quoted(self):
        s = _build_remove_script("authelia; rm -rf /", "my.example.com")
        assert "'authelia; rm -rf /'" in s
        assert "CONT=authelia; rm -rf /" not in s


# --------------------------------------------------------------------------- #
# add_access_rule — mocked ssh + run_locked                                    #
# --------------------------------------------------------------------------- #


class TestAddAccessRule:
    def _patch_infra(self, locked_returns="ok\n"):
        """Return a context manager that patches ssh + run_locked."""
        return (
            patch.object(authelia, "ssh", return_value="authelia-abc\n"),  # _resolve_container
            patch.object(authelia, "run_locked", return_value=locked_returns),
        )

    def test_dry_run_no_network(self):
        with patch.object(authelia, "ssh") as s, patch.object(authelia, "run_locked") as rl:
            r = add_access_rule("my.example.com", dry_run=True)
        assert r == {"status": "dry_run", "domain": "my.example.com"}
        s.assert_not_called()
        rl.assert_not_called()

    def test_invalid_domain_raises_before_any_ssh(self):
        with patch.object(authelia, "ssh") as s, patch.object(authelia, "run_locked") as rl:
            with pytest.raises(ValueError):
                add_access_rule("not a domain")
            s.assert_not_called()
            rl.assert_not_called()

    def test_invalid_policy_raises_before_any_ssh(self):
        with patch.object(authelia, "ssh") as s, patch.object(authelia, "run_locked") as rl:
            with pytest.raises(ValueError):
                add_access_rule("my.example.com", policy="admin")
            s.assert_not_called()
            rl.assert_not_called()

    def test_invalid_resources_raises_before_any_ssh(self):
        with patch.object(authelia, "ssh") as s, patch.object(authelia, "run_locked") as rl:
            with pytest.raises(ValueError):
                add_access_rule("my.example.com", resources=["line1\nline2"])
            s.assert_not_called()
            rl.assert_not_called()

    def test_success_returns_added(self):
        with (
            patch.object(authelia, "ssh", return_value="authelia-abc\n"),
            patch.object(authelia, "run_locked", return_value="ok\n") as rl,
        ):
            r = add_access_rule("my.example.com")
        assert r == {"status": "added", "domain": "my.example.com"}
        rl.assert_called_once()

    def test_idempotent_returns_exists(self):
        """run_locked's stdout contains 'idempotent-noop' on a no-op run."""
        with (
            patch.object(authelia, "ssh", return_value="authelia-abc\n"),
            patch.object(authelia, "run_locked", return_value="idempotent-noop\n"),
        ):
            r = add_access_rule("my.example.com")
        assert r == {"status": "exists", "domain": "my.example.com"}

    def test_container_not_found_raises(self):
        with patch.object(authelia, "ssh", return_value=""):
            with pytest.raises(RuntimeError, match="container not found"):
                add_access_rule("my.example.com")

    def test_rule_yaml_is_base64_encoded_in_script(self):
        """Rule crosses the wire as base64 in an env var, never as
        inline YAML (which would invite shell-escape issues)."""
        captured = {}

        def fake_run_locked(resource, script, timeout):
            captured["resource"] = resource
            captured["script"] = script
            captured["timeout"] = timeout
            return "ok"

        with (
            patch.object(authelia, "ssh", return_value="authelia-abc\n"),
            patch.object(authelia, "run_locked", side_effect=fake_run_locked),
        ):
            add_access_rule("my.example.com", policy="two_factor", resources=["^/api/"])

        script = captured["script"]
        assert "RULE_B64=" in script
        assert captured["resource"] == "authelia-config"
        # Extract the b64 payload and round-trip it — must deserialize
        # to exactly the rule we asked for.
        import re

        m = re.search(r"RULE_B64=(\S+)", script)
        assert m
        b64 = m.group(1).strip("'\"")
        payload = yaml_lib.safe_load(base64.b64decode(b64).decode())
        assert payload == [
            {
                "domain": "my.example.com",
                "policy": "two_factor",
                "resources": ["^/api/"],
            }
        ]

    def test_lock_resource_is_authelia_config(self):
        """All Authelia config mutations serialize on the same lock —
        otherwise two concurrent `fabrik apply` invocations could
        interleave reads/writes and lose a rule."""
        captured = {}

        def fake_run_locked(resource, script, timeout):
            captured["resource"] = resource
            return "ok"

        with (
            patch.object(authelia, "ssh", return_value="authelia-abc\n"),
            patch.object(authelia, "run_locked", side_effect=fake_run_locked),
        ):
            add_access_rule("my.example.com")
        assert captured["resource"] == "authelia-config"

    def test_insert_before_twofactor_mode_passed_through(self):
        captured = {}

        def fake_run_locked(resource, script, timeout):
            captured["script"] = script
            return "ok"

        with (
            patch.object(authelia, "ssh", return_value="authelia-abc\n"),
            patch.object(authelia, "run_locked", side_effect=fake_run_locked),
        ):
            add_access_rule(
                "my.example.com",
                policy="bypass",
                resources=["^/api/"],
                insert_before_twofactor=True,
            )
        # The env var crosses to bash as INSERT_MODE=before_twofactor
        assert "INSERT_MODE=before_twofactor" in captured["script"]


# --------------------------------------------------------------------------- #
# remove_access_rule                                                           #
# --------------------------------------------------------------------------- #


class TestRemoveAccessRule:
    def test_dry_run_no_network(self):
        with patch.object(authelia, "ssh") as s, patch.object(authelia, "run_locked") as rl:
            assert remove_access_rule("my.example.com", dry_run=True) is True
            s.assert_not_called()
            rl.assert_not_called()

    def test_success_returns_true(self):
        with (
            patch.object(authelia, "ssh", return_value="authelia-abc\n"),
            patch.object(authelia, "run_locked", return_value="ok"),
        ):
            assert remove_access_rule("my.example.com") is True

    def test_ssh_failure_returns_false_never_raises(self):
        with patch.object(authelia, "ssh", side_effect=RuntimeError("ssh dead")):
            assert remove_access_rule("my.example.com") is False

    def test_run_locked_failure_returns_false(self):
        with (
            patch.object(authelia, "ssh", return_value="authelia-abc\n"),
            patch.object(authelia, "run_locked", side_effect=RuntimeError("lock timeout")),
        ):
            assert remove_access_rule("my.example.com") is False

    def test_invalid_domain_raises(self):
        """Unlike other failures, an invalid domain is a programming
        error — caller wrote bad code; surface it."""
        with pytest.raises(ValueError):
            remove_access_rule("not a domain")


# --------------------------------------------------------------------------- #
# Precedence-aware insert helpers (T2-08 Part C / Lesson 56)                   #
# --------------------------------------------------------------------------- #


class TestDomainShadows:
    def test_exact_match(self):
        assert _domain_shadows("images.vps1.ocoron.com", "images.vps1.ocoron.com")

    def test_wildcard_shadows_single_label(self):
        assert _domain_shadows("*.vps1.ocoron.com", "images.vps1.ocoron.com")

    def test_wildcard_does_not_shadow_multi_label(self):
        # *.vps1.ocoron.com matches one label, so x.api.vps1 must NOT match
        assert not _domain_shadows("*.vps1.ocoron.com", "x.api.vps1.ocoron.com")

    def test_different_domain_not_shadowed(self):
        assert not _domain_shadows("*.example.com", "images.vps1.ocoron.com")

    def test_list_form_shadows_if_any_member_matches(self):
        rule_domain = ["pdf.vps1.ocoron.com", "*.vps1.ocoron.com"]
        assert _domain_shadows(rule_domain, "images.vps1.ocoron.com")

    def test_list_form_no_member_matches(self):
        rule_domain = ["pdf.vps1.ocoron.com", "search.vps1.ocoron.com"]
        assert not _domain_shadows(rule_domain, "images.vps1.ocoron.com")

    def test_none_domain_is_no_shadow(self):
        assert not _domain_shadows(None, "images.vps1.ocoron.com")

    def test_non_string_member_skipped(self):
        # YAML round-trip can produce a list with mixed types in pathological
        # cases; the helper must not crash, just skip non-strings.
        assert _domain_shadows([None, "*.vps1.ocoron.com"], "images.vps1.ocoron.com")


class TestComputeInsertIndex:
    def test_append_mode_returns_none(self):
        rules = [{"domain": "*.vps1.ocoron.com", "policy": "two_factor"}]
        new_rule = {"domain": "images.vps1.ocoron.com", "policy": "bypass"}
        assert _compute_insert_index(rules, new_rule, "append") is None

    def test_specific_bypass_inserts_before_wildcard_two_factor(self):
        # The canonical T1-04 scenario.
        rules = [
            {"domain": "ocoron.com", "policy": "bypass"},
            {"domain": "*.vps1.ocoron.com", "policy": "bypass", "resources": ["^/health$"]},
            {"domain": "*.vps1.ocoron.com", "policy": "two_factor"},
        ]
        new_rule = {"domain": "images.vps1.ocoron.com", "policy": "bypass", "resources": ["^/api/"]}
        assert _compute_insert_index(rules, new_rule, "before_twofactor") == 2

    def test_exact_match_two_factor_still_works(self):
        # Existing pre-T2-08 callers may have a same-domain two_factor rule.
        rules = [
            {"domain": "images.vps1.ocoron.com", "policy": "two_factor"},
        ]
        new_rule = {"domain": "images.vps1.ocoron.com", "policy": "bypass", "resources": ["^/api/"]}
        assert _compute_insert_index(rules, new_rule, "before_twofactor") == 0

    def test_no_shadowing_rule_appends(self):
        # No two_factor rule with matching/wildcard domain → caller appends.
        rules = [
            {"domain": "ocoron.com", "policy": "bypass"},
            {"domain": "pdf.vps1.ocoron.com", "policy": "bypass"},
        ]
        new_rule = {"domain": "images.vps1.ocoron.com", "policy": "bypass", "resources": ["^/api/"]}
        assert _compute_insert_index(rules, new_rule, "before_twofactor") is None

    def test_unknown_mode_appends(self):
        rules = [{"domain": "*.vps1.ocoron.com", "policy": "two_factor"}]
        new_rule = {"domain": "images.vps1.ocoron.com", "policy": "bypass"}
        assert _compute_insert_index(rules, new_rule, "weird") is None

    def test_non_string_new_domain_appends(self):
        rules = [{"domain": "*.vps1.ocoron.com", "policy": "two_factor"}]
        new_rule = {"domain": None, "policy": "bypass"}
        assert _compute_insert_index(rules, new_rule, "before_twofactor") is None

    def test_returns_first_shadow_index(self):
        # Multiple shadowing rules — return the first (lowest index)
        rules = [
            {"domain": "*.vps1.ocoron.com", "policy": "two_factor"},
            {"domain": "images.vps1.ocoron.com", "policy": "two_factor"},
        ]
        new_rule = {"domain": "images.vps1.ocoron.com", "policy": "bypass", "resources": ["^/api/"]}
        assert _compute_insert_index(rules, new_rule, "before_twofactor") == 0


class TestHeredocMirrorsHelper:
    """Sanity check: the heredoc-embedded logic produces the same insert
    position as the importable helper for the canonical scenario."""

    def test_heredoc_inlines_domain_shadows(self):
        # Build a fresh add script and assert the heredoc body defines an
        # inline _domain_shadows function (mirror of the helper).
        script = _build_add_script(
            "authelia-test", "ZHVtbXk=", "images.vps1.ocoron.com", "before_twofactor"
        )
        assert "def _domain_shadows" in script
        assert "rd.startswith('*.')" in script
        assert "insert_mode == 'before_twofactor'" in script


# --------------------------------------------------------------------------- #
# The scripts EXECUTED — a fake sudo/docker on a tmp root (W-3d834ded)         #
# --------------------------------------------------------------------------- #

_FAKE_SUDO = """#!/bin/bash
# runs its argv as the caller: -E (keep env) is the only flag the scripts pass
echo "sudo $*" >> "$FAKE_LOG"
[ "$1" = "-E" ] && shift
exec "$@"
"""
_FAKE_DOCKER = """#!/bin/bash
echo "docker $*" >> "$FAKE_LOG"
case "$1" in
  exec) cat "$FAKE_CONFIG" ;;
  cp) cp "$2" "$FAKE_INSTALLED" ;;
  restart) [ -n "${FAIL_RESTART:-}" ] && exit "$FAIL_RESTART"; exit 0 ;;
esac
"""
# drops -o/-g (a non-root test cannot chown) and keeps every other argument
_FAKE_INSTALL = """#!/bin/bash
args=()
while [ $# -gt 0 ]; do
  case "$1" in -o|-g) shift 2 ;; *) args+=("$1"); shift ;; esac
done
exec /usr/bin/install "${args[@]}"
"""
_FAKE_RM = """#!/bin/bash
[ -n "${FAIL_RM:-}" ] && exit 1
exec /bin/rm "$@"
"""


def _rule_b64(domain: str = "new.example.com") -> str:
    return base64.b64encode(
        yaml_lib.safe_dump([{"domain": domain, "policy": "bypass"}]).encode()
    ).decode()


class TestScriptsExecuted:
    """Each script runs under bash against fakes rooted at tmp_path: staging stays inside a
    mktemp work dir only sudo touches, the work dir goes on every exit with the exit code kept,
    and the backup is root-only, unique and taken only when the config changes."""

    @pytest.fixture
    def env(self, tmp_path, monkeypatch):
        import stat
        import sys

        bindir = tmp_path / "bin"
        bindir.mkdir()
        for name, body in {
            "sudo": _FAKE_SUDO,
            "docker": _FAKE_DOCKER,
            "install": _FAKE_INSTALL,
            "rm": _FAKE_RM,
        }.items():
            p = bindir / name
            p.write_text(body)
            p.chmod(p.stat().st_mode | stat.S_IXUSR)
        (bindir / "python3").symlink_to(sys.executable)  # PyYAML lives in the venv
        work_root = tmp_path / "tmp"
        work_root.mkdir()
        cfg = tmp_path / "configuration.yml"
        cfg.write_text(yaml_lib.safe_dump({"access_control": {"rules": []}}))
        monkeypatch.setattr(
            authelia, "_WORK_TEMPLATE", str(work_root / "fabrik-XXXXXXXXXX"), raising=False
        )
        monkeypatch.setattr(authelia, "_BACKUP_DIR", str(tmp_path / "backups"), raising=False)
        run_env = {
            "PATH": f"{bindir}:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "FAKE_LOG": str(tmp_path / "calls.log"),
            "FAKE_CONFIG": str(cfg),
            "FAKE_INSTALLED": str(tmp_path / "installed.yml"),
        }
        return {"tmp": tmp_path, "work_root": work_root, "cfg": cfg, "env": run_env}

    def _run(self, env, script, **extra):
        import subprocess

        assert "/tmp/authelia." not in script, "the script still stages under a predictable name"
        return subprocess.run(
            ["bash", "-c", script],
            env={**env["env"], **extra},
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    def _add(self, domain="new.example.com"):
        return _build_add_script("authelia-xyz", _rule_b64(domain), domain, "append")

    def test_add_script_stages_only_in_a_private_work_dir(self, env):
        r = self._run(env, self._add())
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip().endswith("ok")
        installed = yaml_lib.safe_load((env["tmp"] / "installed.yml").read_text())
        assert installed["access_control"]["rules"] == [
            {"domain": "new.example.com", "policy": "bypass"}
        ]
        assert list(env["work_root"].iterdir()) == [], "the work dir must be removed on success"
        log = (env["tmp"] / "calls.log").read_text()
        assert f"sudo mktemp -d {env['work_root']}/fabrik-XXXXXXXXXX" in log

        # noop: the rule is already there — no copy, no restart, no backup, work dir gone
        env["cfg"].write_text((env["tmp"] / "installed.yml").read_text())
        (env["tmp"] / "calls.log").write_text("")
        r = self._run(env, self._add())
        assert r.returncode == 0, r.stderr
        assert "idempotent-noop" in r.stdout
        assert "docker cp" not in (env["tmp"] / "calls.log").read_text()
        assert list(env["work_root"].iterdir()) == []
        assert len(list((env["tmp"] / "backups").iterdir())) == 1, "a noop takes no backup"

        # a failing step keeps its exit code and still removes the work dir
        r = self._run(env, self._add("other.example.com"), FAIL_RESTART="7")
        assert r.returncode == 7
        assert list(env["work_root"].iterdir()) == []

    def test_every_work_dir_touch_is_under_sudo(self):
        """The ssh user cannot search a root 0700 dir: a bare `[ -f "$WORK/…" ]` reads false,
        so every change would silently report a noop; a bare prune of the backup dir silently
        never prunes, and a bare `install -d` aborts every add. The fake sudo of the executed
        tests runs as the test user, so only this check sees a dropped `sudo`."""
        for script in (self._add(), _build_remove_script("authelia-xyz", "my.example.com")):
            bash = script.split("<<'PY'")[0] + script.split("\nPY\n")[1]
            code = [line for line in bash.splitlines() if not line.lstrip().startswith("#")]
            assert any("$WORK" in line for line in code), "the script never touches its work dir"
            for token in ("$WORK", authelia._BACKUP_DIR, "$BAK"):
                for line in (ln for ln in code if token in ln):
                    assert "sudo " in line.split(token)[0], (token, line)
            tmp_mentions = [ln for ln in script.splitlines() if "/tmp/" in ln]
            assert tmp_mentions, "the mktemp template names /tmp"
            assert all("mktemp -d" in ln for ln in tmp_mentions), tmp_mentions

    def test_add_script_backs_up_only_on_change_root_only_and_prunes_to_ten(self, env):
        import os

        backups = env["tmp"] / "backups"
        backups.mkdir(mode=0o700)
        for i in range(12):
            old = backups / f"authelia.bak.20200101-0000{i:02d}.aaaaaa.yml"
            old.write_text("old")
            os.utime(old, (1_600_000_000 + i, 1_600_000_000 + i))
        r = self._run(env, self._add())
        assert r.returncode == 0, r.stderr
        kept = sorted(backups.iterdir())
        assert len(kept) == 10
        new = [p for p in kept if p.read_text() != "old"]
        assert len(new) == 1, "exactly one fresh backup, holding the pre-change config"
        assert yaml_lib.safe_load(new[0].read_text()) == {"access_control": {"rules": []}}
        assert new[0].stat().st_mode & 0o777 == 0o600
        assert backups.stat().st_mode & 0o777 == 0o700

    def test_remove_script_stages_only_in_a_private_work_dir(self, env):
        env["cfg"].write_text(
            yaml_lib.safe_dump(
                {"access_control": {"rules": [{"domain": "my.example.com", "policy": "bypass"}]}}
            )
        )
        r = self._run(env, _build_remove_script("authelia-xyz", "my.example.com"))
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip().endswith("ok")
        installed = yaml_lib.safe_load((env["tmp"] / "installed.yml").read_text())
        assert installed == {"access_control": {"rules": []}}
        assert list(env["work_root"].iterdir()) == []
        assert not (env["tmp"] / "backups").exists(), "the remove script takes no backup"

    def test_a_failing_cleanup_keeps_the_exit_code(self, env):
        r = self._run(env, self._add(), FAIL_RM="1")
        assert r.returncode == 0, r.stderr
        assert "WARN: cleanup failed" in r.stderr
        r = self._run(env, self._add("other.example.com"), FAIL_RM="1", FAIL_RESTART="7")
        assert r.returncode == 7
