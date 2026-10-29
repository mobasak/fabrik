"""T03 (Coolify-verb retirement, D3 + invariant 2) — `reconcile-all` reads the deployed set from Compose.

`fabrik reconcile-all` asks each distinct target host ONCE for `docker compose ls -a`
(`SSHDeployer.list_compose_projects`, faked here — never the network) and reconciles a spec
when a project `Name` is `<n>`/`fabrik-<n>` or a `ConfigFiles` parent is one of
`app_dir(spec)`. Failures are rows; the exit code follows invariant 2.
`refresh_infrastructure` walks `app_dir(spec)` through `probe_app` inside the host swap only.
Fixture shapes follow the R1 vps1 probe (2026-10-14): `Name` equals the `/opt/<Name>`
basename, `ConfigFiles` is one comma-joined string.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

import fabrik.cli as cli_module
from fabrik.orchestrator import DeploymentOrchestrator, ProvisioningError
from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.deployer_ssh import SSHDeployer, app_dir

cli = cli_module.cli

R1_PROJECTS = [
    {"Name": "a", "Status": "running(1)", "ConfigFiles": "/opt/a/compose.yaml"},
    {
        "Name": "other",
        "Status": "running(2)",
        "ConfigFiles": "/opt/x/compose.yaml,/opt/b/compose.yaml",
    },
    {"Name": "fabrik-d", "Status": "exited(1)", "ConfigFiles": "/opt/fabrik-d/compose.yaml"},
    {
        "Name": "file-worker",
        "Status": "running(1)",
        "ConfigFiles": "/opt/file-worker/compose.yaml",
    },
]


def _spec(
    specs_dir: Path,
    sid: str,
    *,
    target_vps: str | None = None,
    source: str = "",
    name: str | None = None,
) -> None:
    lines = [f"id: {sid}", "template: python-api", f"domain: {sid}.example.com"]
    if name:
        lines.append(f"name: {name}")
    if target_vps:
        lines.append(f"target_vps: {target_vps}")
    if source:
        lines.append(source)
    (specs_dir / f"{sid}.yaml").write_text("\n".join(lines) + "\n")


def _broken(specs_dir: Path, stem: str) -> None:
    (specs_dir / f"{stem}.yaml").write_text("id: [unterminated\n")


@pytest.fixture
def specs_dir(tmp_path, monkeypatch):
    root = tmp_path / "root"
    d = root / "specs" / "services"
    d.mkdir(parents=True)
    monkeypatch.setattr(cli_module, "FABRIK_ROOT", root)
    return d


class Harness:
    """Records every `list_compose_projects` host and every `refresh_infrastructure` call."""

    def __init__(
        self,
        hosts: dict[str, object],
        lock_timeout: set[str] | None = None,
        refresh_error: dict[str, Exception] | None = None,
    ):
        self.hosts = hosts  # host -> list of projects | exception to raise
        self.ls_calls: list[str] = []
        self.refresh_calls: list[tuple[str, object]] = []
        self.lock_timeout = lock_timeout or set()
        self.refresh_error = refresh_error or {}  # spec id -> what refresh_infrastructure raises

    def ls(self, host):
        self.ls_calls.append(host)
        val = self.hosts[host]
        if isinstance(val, BaseException):
            raise val
        return val

    def refresh(self, spec_path, dry_run=False, target_vps=None):
        self.refresh_calls.append((Path(spec_path).stem, target_vps))
        if Path(spec_path).stem in self.refresh_error:
            raise self.refresh_error[Path(spec_path).stem]
        return MagicMock()

    @contextlib.contextmanager
    def lock(self, key, timeout_seconds=30):
        if key.removeprefix("reconcile-") in self.lock_timeout:
            raise TimeoutError(f"lock {key} busy")
        yield


def _run(harness: Harness, args: list[str], *, real_ls_ssh=None):
    patches = [
        patch.object(DeploymentOrchestrator, "refresh_infrastructure", harness.refresh),
        patch("fabrik.locks_local.file_lock", harness.lock),
    ]
    if real_ls_ssh is None:
        patches.append(patch.object(SSHDeployer, "list_compose_projects", harness.ls))
    else:
        patches.append(patch("fabrik.drivers.ssh.ssh", real_ls_ssh))
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        return CliRunner().invoke(cli, ["reconcile-all", *args])


def _row(output: str, sid: str) -> str:
    """The status/detail cell of the row whose first token is *sid* — sliced AFTER the id, never at a fixed
    column (the table pads ids to 30 characters but never truncates a longer one)."""
    for line in output.splitlines():
        if line.split(" ", 1)[0] == sid:
            return line[len(sid) :].strip()
    raise AssertionError(f"no row for {sid!r} in:\n{output}")


def _fleet(specs_dir: Path) -> None:
    for sid in ("a", "b", "c", "d"):
        _spec(specs_dir, sid)
    _spec(
        specs_dir,
        "fabrik-file-worker",
        source="source:\n  type: local\n  path: /opt/file-worker\n",
    )


class TestDeployedSet:
    def test_rows_follow_name_and_configfiles_match_with_one_ls(self, specs_dir):
        _fleet(specs_dir)
        h = Harness({"vps1": R1_PROJECTS})
        result = _run(h, [])
        assert result.exit_code == 0, result.output
        for sid in ("a", "b", "d", "fabrik-file-worker"):
            assert _row(result.output, sid) == "dry-run", result.output
        assert _row(result.output, "c") == "skipped — no compose project (no containers) on vps1"
        assert h.ls_calls == ["vps1"]

    def test_unreachable_spoke_is_a_row_and_vps1_still_reconciles(self, specs_dir):
        _fleet(specs_dir)
        _spec(specs_dir, "spoke", target_vps="vps2")
        boom = subprocess.TimeoutExpired(cmd="ssh vps2", timeout=60)
        h = Harness({"vps1": R1_PROJECTS, "vps2": boom})
        result = _run(h, [])
        assert _row(result.output, "spoke") == f"host-unreachable — {boom}"
        for sid in ("a", "b", "d", "fabrik-file-worker"):
            assert _row(result.output, sid) == "dry-run"
        assert sorted(h.ls_calls) == ["vps1", "vps2"]

    def test_bad_local_path_and_non_json_host_are_rows_and_table_finishes(self, specs_dir):
        _spec(specs_dir, "srvx", source="source:\n  type: local\n  path: /srv/x\n")
        _spec(specs_dir, "zz")

        def fake_ssh(cmd, timeout=None):
            return "<html>login banner</html>"

        result = _run(Harness({}), [], real_ls_ssh=fake_ssh)
        with pytest.raises(ProvisioningError) as exc:
            app_dir({"id": "srvx", "source": {"type": "local", "path": "/srv/x"}})
        assert _row(result.output, "srvx") == f"error — {str(exc.value)[:80]}"
        zz = _row(result.output, "zz")
        assert zz.startswith("host-unreachable — ") and "vps1" in zz
        assert "Spec" in result.output  # the table header printed — the run finished

    def test_a_spec_defect_still_names_its_host_for_the_exit_rule(self, specs_dir):
        """Invariant 2: the host is read BEFORE the per-spec checks, so a bad-path spec on a dead host
        exits 1 (its host failed) and the same spec beside a dead spoke, with vps1 healthy, exits 0."""
        _spec(specs_dir, "srvx", source="source:\n  type: local\n  path: /srv/x\n")
        down = RuntimeError("ssh down")
        # (b) the only named host is dead -> exit 1, the spec defect still prints as its own row
        h = Harness({"vps1": down})
        result = _run(h, [])
        assert result.exit_code == 1, result.output
        assert _row(result.output, "srvx").startswith("error — local source path")
        assert h.ls_calls == ["vps1"]
        # (a) vps1 healthy, a spoke dead -> each host read once (srvx is still in the dir and reads vps1),
        #     exit 0 without --yes
        _spec(specs_dir, "spoke", target_vps="vps2")
        h = Harness({"vps1": R1_PROJECTS, "vps2": down})
        result = _run(h, [])
        assert result.exit_code == 0, result.output
        assert sorted(h.ls_calls) == ["vps1", "vps2"]
        assert _row(result.output, "spoke") == "host-unreachable — ssh down"

    def test_name_alone_matches_without_configfiles_and_name_wins_over_id(self, specs_dir):
        """Spec D3: a project whose `Name` is `<n>` or `fabrik-<n>` is deployed even with no ConfigFiles,
        and `<n>` is `spec.name or spec.id`."""
        _spec(specs_dir, "nameonly")
        _spec(specs_dir, "pfx")
        _spec(specs_dir, "svc", name="svc-name")
        projects = [
            {"Name": "nameonly", "Status": "running(1)"},
            {"Name": "fabrik-pfx", "Status": "running(1)"},
            {"Name": "svc-name", "Status": "running(1)"},
        ]
        result = _run(Harness({"vps1": projects}), [])
        assert result.exit_code == 0, result.output
        for sid in ("nameonly", "pfx", "svc"):
            assert _row(result.output, sid) == "dry-run", result.output

    def test_configfiles_entries_are_stripped_before_the_parent_match(self, specs_dir):
        _spec(specs_dir, "sp")
        projects = [{"Name": "other", "ConfigFiles": " /opt/sp/compose.yaml , /opt/x/compose.yaml"}]
        result = _run(Harness({"vps1": projects}), [])
        assert _row(result.output, "sp") == "dry-run", result.output

    def test_error_row_detail_is_cut_at_eighty_characters(self, specs_dir):
        long_path = "/srv/" + "x" * 90
        _spec(specs_dir, "longy", source=f"source:\n  type: local\n  path: {long_path}\n")
        with pytest.raises(ProvisioningError) as exc:
            app_dir({"id": "longy", "source": {"type": "local", "path": long_path}})
        assert len(str(exc.value)) > 80
        result = _run(Harness({"vps1": []}), [])
        assert _row(result.output, "longy") == f"error — {str(exc.value)[:80]}"

    def test_refresh_failure_row_is_cut_at_eighty_characters_too(self, specs_dir):
        """The second `error` row — `refresh_infrastructure` raising for a DEPLOYED spec — takes the same cut."""
        _spec(specs_dir, "boom")
        projects = [{"Name": "boom", "ConfigFiles": "/opt/boom/compose.yaml"}]
        h = Harness({"vps1": projects}, refresh_error={"boom": RuntimeError("y" * 120)})
        result = _run(h, [])
        assert h.refresh_calls == [("boom", None)]
        assert _row(result.output, "boom") == "error — " + "y" * 80
        assert result.exit_code == 0, result.output  # an `error` row fails the run only under --yes


def _exit_case(specs_dir, case):
    """Build the fixture for one exit-rule case; return (harness, extra args, real_ls_ssh)."""
    ok = [{"Name": "good", "ConfigFiles": "/opt/good/compose.yaml"}]
    down = RuntimeError("ssh: connect to host failed")
    if case == "all-hosts-raise":
        _spec(specs_dir, "good")
        _spec(specs_dir, "spoke", target_vps="vps2")
        return Harness({"vps1": down, "vps2": down}), None
    if case == "host-unreachable":
        _spec(specs_dir, "good")
        _spec(specs_dir, "spoke", target_vps="vps2")
        return Harness({"vps1": ok, "vps2": down}), None
    if case == "error":
        _spec(specs_dir, "good")
        _spec(specs_dir, "srvx", source="source:\n  type: local\n  path: /srv/x\n")
        return Harness({"vps1": ok}), None
    if case == "spec-error":
        _spec(specs_dir, "good")
        _broken(specs_dir, "broken")
        return Harness({"vps1": ok}), None
    if case == "lock-timeout":
        _spec(specs_dir, "good")
        _spec(specs_dir, "busy")
        busy = [*ok, {"Name": "busy", "ConfigFiles": "/opt/busy/compose.yaml"}]
        return Harness({"vps1": busy}, lock_timeout={"busy"}), None
    if case == "only-host-raises":
        _spec(specs_dir, "good")
        return Harness({"vps1": down}), None
    if case == "only-host-non-json":
        _spec(specs_dir, "good")
        return Harness({}), lambda cmd, timeout=None: "not json at all"
    if case == "all-reconciled-or-skipped":
        _spec(specs_dir, "good")
        _spec(specs_dir, "absent")
        return Harness({"vps1": ok}), None
    if case == "all-spec-error":
        _broken(specs_dir, "broken1")
        _broken(specs_dir, "broken2")
        return Harness({}), None
    raise AssertionError(case)


@pytest.mark.parametrize(
    ("case", "yes", "expected"),
    [
        ("all-hosts-raise", False, 1),
        ("host-unreachable", True, 1),
        ("host-unreachable", False, 0),
        ("error", True, 1),
        ("error", False, 0),
        ("spec-error", True, 1),
        ("spec-error", False, 0),
        ("lock-timeout", True, 1),
        ("lock-timeout", False, 0),
        ("only-host-raises", True, 1),
        ("only-host-raises", False, 1),
        ("only-host-non-json", True, 1),
        ("only-host-non-json", False, 1),
        ("all-reconciled-or-skipped", True, 0),
        ("all-reconciled-or-skipped", False, 0),
        ("all-spec-error", False, 0),
        ("all-spec-error", True, 1),
    ],
)
def test_exit_rule(specs_dir, case, yes, expected):
    harness, real_ls_ssh = _exit_case(specs_dir, case)
    result = _run(harness, ["--yes"] if yes else [], real_ls_ssh=real_ls_ssh)
    assert result.exit_code == expected, result.output
    if case in ("host-unreachable", "error", "spec-error", "lock-timeout"):
        assert case in result.output  # the row the exit rule reads was printed


def test_exit_rule_filter_runs_before_load(specs_dir):
    _broken(specs_dir, "broken")
    _spec(specs_dir, "good")
    h = Harness({"vps1": []})
    result = _run(h, ["--yes", "--filter", "nomatch"])
    assert result.exit_code == 0, result.output
    assert "spec-error" not in result.output
    assert h.ls_calls == []


def test_exit_rule_empty_specs_dir(specs_dir):
    result = _run(Harness({}), [])
    assert result.exit_code == 1
    assert "No specs found." in result.output


class TestRefreshTargetVps:
    def test_real_refresh_probes_the_spoke_and_leaves_registrars_on_the_hub(self, monkeypatch):
        monkeypatch.delenv("FABRIK_VPS_SSH_HOST", raising=False)
        seen: list[tuple[str, str | None]] = []

        def fake_ssh(cmd, timeout=None):
            seen.append((cmd, os.environ.get("FABRIK_VPS_SSH_HOST")))
            if "compose.yaml" in cmd and "echo exists" in cmd:
                return "exists\n"
            return ""

        orch = DeploymentOrchestrator()
        orch.validator = MagicMock()
        orch.validator.load_and_validate.return_value = (
            {"id": "spoky", "name": "spoky", "target_vps": "vps2"},
            "h",
            [],
        )
        got: dict[str, DeploymentContext] = {}

        class _Prov:
            def provision(self, ctx):
                got["ctx"] = ctx
                from fabrik.drivers import ssh as ssh_mod

                ssh_mod.ssh("registrar hub-side", timeout=5)

        orch.infrastructure_provisioner = _Prov()
        with (
            patch("fabrik.drivers.ssh.ssh", fake_ssh),
            patch.object(orch, "_persist_state") as persist,
        ):
            orch.refresh_infrastructure(spec_path=Path("/nonexistent/spoky.yaml"))

        probes = [env for cmd, env in seen if cmd != "registrar hub-side"]
        assert probes and all(env == "vps2" for env in probes)
        assert got["ctx"].target_vps == "vps2"
        persist.assert_called_once()
        assert persist.call_args.args[0] is got["ctx"]
        assert [env for cmd, env in seen if cmd == "registrar hub-side"] == [None]
        assert os.environ.get("FABRIK_VPS_SSH_HOST") is None


def _orch_for(spec: dict) -> DeploymentOrchestrator:
    orch = DeploymentOrchestrator()
    orch.validator = MagicMock()
    orch.validator.load_and_validate.return_value = (spec, "h", [])
    orch.infrastructure_provisioner = MagicMock()
    orch.deployer = MagicMock()
    return orch


ABSENT = {"exists": False, "ps": "", "error": None}


class TestRefreshWalk:
    def test_host_error_after_absent_raises_naming_the_host(self):
        orch = _orch_for({"id": "w", "name": "w", "target_vps": "vps3"})
        by_path = {
            "/opt/w": ABSENT,
            "/opt/fabrik-w": {"exists": False, "ps": "", "error": "RuntimeError: refused"},
        }
        orch.deployer.probe_app.side_effect = lambda p: by_path[p]
        with pytest.raises(ProvisioningError, match="could not reach vps3: RuntimeError: refused"):
            orch.refresh_infrastructure(spec_path=Path("w.yaml"))
        orch.infrastructure_provisioner.provision.assert_not_called()

    def test_exists_with_error_is_a_match(self):
        orch = _orch_for({"id": "w", "name": "w"})
        by_path = {"/opt/w": {"exists": True, "ps": "", "error": "compose ps output is not JSON"}}
        orch.deployer.probe_app.side_effect = lambda p: by_path[p]
        ctx = orch.refresh_infrastructure(spec_path=Path("w.yaml"))
        assert ctx.app_name == "w"
        orch.infrastructure_provisioner.provision.assert_called_once()

    def test_every_candidate_absent_names_every_directory(self):
        orch = _orch_for({"id": "w", "name": "w"})
        orch.deployer.probe_app.side_effect = lambda p: ABSENT
        with pytest.raises(ProvisioningError) as exc:
            orch.refresh_infrastructure(spec_path=Path("w.yaml"))
        assert "/opt/w" in str(exc.value) and "/opt/fabrik-w" in str(exc.value)

    def test_target_vps_flag_wins_over_the_spec_then_vps1(self, monkeypatch):
        """flag > spec > vps1 — the walk runs on the resolved host and ctx records it."""
        monkeypatch.delenv("FABRIK_VPS_SSH_HOST", raising=False)
        envs: list[str | None] = []

        def probe(path):
            envs.append(os.environ.get("FABRIK_VPS_SSH_HOST"))
            return {"exists": True, "ps": "", "error": None}

        orch = _orch_for({"id": "w", "name": "w", "target_vps": "vps2"})
        orch.deployer.probe_app.side_effect = probe
        ctx = orch.refresh_infrastructure(spec_path=Path("w.yaml"), target_vps="vps3")
        assert ctx.target_vps == "vps3" and envs == ["vps3"]
        envs.clear()
        ctx = orch.refresh_infrastructure(spec_path=Path("w.yaml"))
        assert ctx.target_vps == "vps2" and envs == ["vps2"]
        envs.clear()
        orch = _orch_for({"id": "w", "name": "w"})
        orch.deployer.probe_app.side_effect = probe
        ctx = orch.refresh_infrastructure(spec_path=Path("w.yaml"))
        assert ctx.target_vps == "vps1" and envs == [None]  # vps1 is the no-op host

    def test_local_source_match_sets_app_name_to_its_basename(self):
        orch = _orch_for(
            {
                "id": "fabrik-file-worker",
                "name": "fabrik-file-worker",
                "source": {"type": "local", "path": "/opt/file-worker"},
            }
        )
        by_path = {"/opt/file-worker": {"exists": True, "ps": "", "error": None}}
        orch.deployer.probe_app.side_effect = lambda p: by_path[p]
        ctx = orch.refresh_infrastructure(spec_path=Path("fw.yaml"))
        assert ctx.app_name == "file-worker"


class TestTargetVpsPassThrough:
    def test_redeploy_passes_flag_and_reconcile_all_passes_none(self, tmp_path, specs_dir):
        spec_path = tmp_path / "plain.yaml"
        spec_path.write_text("id: plain\ntemplate: python-api\n")
        received: list[object] = []

        def fake_refresh(_self, spec_path, dry_run=False, target_vps="UNSET"):
            received.append(target_vps)
            ctx = DeploymentContext(spec_path=Path(spec_path))
            ctx.spec = {"name": "plain"}
            ctx.app_name = "plain"
            return ctx

        with (
            patch.object(DeploymentOrchestrator, "refresh_infrastructure", fake_refresh),
            patch.object(cli_module, "_post_deploy_sync", lambda: None),
        ):
            result = CliRunner().invoke(
                cli,
                ["redeploy", "--refresh-infra", "--spec", str(spec_path), "--target-vps", "vps2"],
            )
        assert result.exit_code == 0, result.output
        assert received == ["vps2"]

        _spec(specs_dir, "a")
        h = Harness({"vps1": R1_PROJECTS})
        _run(h, [])
        assert h.refresh_calls == [("a", None)]

    def test_help_strings(self):
        out = CliRunner().invoke(cli, ["redeploy", "--help"]).output
        assert "(no image rebuild)" in out and "Coolify" not in out
        assert "with --refresh-infra: this flag > the spec's target_vps > vps1" in " ".join(
            out.split()
        )
