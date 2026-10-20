"""A spec's ``monitoring`` block is validated and kept current on vps1 (W-01815aee).

``add_scrape_target`` wrote ``monitoring.scheme``/``target`` into prometheus.yml unchecked — a bad value makes
promtool refuse the WHOLE file — and matched an existing job by ``job_name`` only, so a changed target, scheme
or path was never rewritten. Now both fields are refused before any read, an existing job's managed keys are
updated in place (hand-added keys and a ``credentials_file`` secret kept), and rollback removes only a job
this run created.
"""

from __future__ import annotations

import copy
from pathlib import Path
from unittest import mock

import pytest

from fabrik.drivers import prometheus as prom
from fabrik.orchestrator.context import DeploymentContext, ResourceRecord
from fabrik.orchestrator.infrastructure import InfrastructureProvisioner
from fabrik.orchestrator.rollback import RollbackManager

_JOB = f"{prom.JOB_PREFIX}svc"


def _wire(monkeypatch, cfg: dict) -> list[dict]:
    written: list[dict] = []
    monkeypatch.setattr(prom, "_read_config", lambda: cfg)
    monkeypatch.setattr(prom, "_write_config", lambda d: written.append(d))
    monkeypatch.setattr(prom, "_reload_prometheus_outcome", lambda: "reloaded")
    return written


def _no_ssh(monkeypatch) -> None:
    def _boom(*a, **k):
        raise AssertionError("validation must refuse before any read or write")

    monkeypatch.setattr(prom, "_read_config", _boom)
    monkeypatch.setattr(prom, "_write_config", _boom)
    monkeypatch.setattr(prom, "_reload_prometheus_outcome", _boom)


def _job(**over) -> dict:
    job = {
        "job_name": _JOB,
        "scheme": "http",
        "metrics_path": "/metrics",
        "scrape_interval": "30s",
        "static_configs": [{"targets": ["svc:8000"]}],
    }
    job.update(over)
    return job


# ── Behaviour 1-2: scheme and target refused before any read ──────────────────────────── #


@pytest.mark.parametrize("scheme", ["HTTPS", "ftp", "", " http", None, 443])
@pytest.mark.parametrize("dry_run", [False, True])
def test_a_bad_scheme_is_refused_before_any_read(monkeypatch, scheme, dry_run) -> None:
    _no_ssh(monkeypatch)
    with pytest.raises(ValueError, match="scheme"):
        prom.add_scrape_target("svc", domain="svc.example.com", scheme=scheme, dry_run=dry_run)


@pytest.mark.parametrize(
    "target",
    [
        "svc",  # missing port (pinned on purpose)
        "svc:0",
        "svc:65536",
        "svc:80/metrics",
        "http://svc:80",
        "svc :80",
        "[fd00::1]:8201",  # IPv6 refused on purpose
        "fd00::1",
        "-svc:80",
        "svc:8o",
        "svc:080",  # leading zero: would never equal the job's spelling
        pytest.param("svc:" + "9" * 5000, id="5000-digit-port"),
        "a" * 64 + ":80",  # label over 63
        ".".join(["a" * 63] * 4) + ":80",  # host over 253
        8000,
    ],
)
@pytest.mark.parametrize("dry_run", [False, True])
def test_a_bad_target_is_refused_before_any_read(monkeypatch, target, dry_run) -> None:
    _no_ssh(monkeypatch)
    with pytest.raises(ValueError, match="target"):
        prom.add_scrape_target("svc", target=target, scheme="http", dry_run=dry_run)


def test_the_scheme_is_checked_before_the_target_is_derived(monkeypatch) -> None:
    _no_ssh(monkeypatch)
    with pytest.raises(ValueError, match="scheme"):
        prom.add_scrape_target("svc", domain="bad domain", scheme="ftp", dry_run=True)


@pytest.mark.parametrize(
    "target",
    [
        "name:8000",
        "my_svc-api:8000",
        "a.b.c:443",
        "10.0.1.1:8201",
        "a" * 63 + ":65535",
        ".".join(["a" * 63] * 3 + ["a" * 61]) + ":1",  # host of exactly 253
    ],
)
def test_legitimate_targets_pass(monkeypatch, target) -> None:
    written = _wire(monkeypatch, {"scrape_configs": []})
    r = prom.add_scrape_target("svc", target=target, scheme="http")
    assert r["status"] == "created" and r["target"] == target
    assert written[0]["scrape_configs"][0]["static_configs"] == [{"targets": [target]}]


def test_a_non_string_metrics_path_is_refused(monkeypatch) -> None:
    _no_ssh(monkeypatch)
    with pytest.raises(ValueError, match="metrics_path"):
        prom.add_scrape_target("svc", target="svc:8000", scheme="http", metrics_path=None)


# ── Behaviour 3-4: a changed job is updated in place, an unchanged one is not ─────────── #


@pytest.mark.parametrize(
    ("over", "kwargs"),
    [
        ({}, {"target": "svc:9000"}),
        ({}, {"scheme": "https"}),
        ({}, {"metrics_path": "/prom"}),
        ({"static_configs": [{"targets": ["old:1"], "labels": {"tier": "x"}}]}, {}),
    ],
    ids=["target", "scheme", "path", "target-with-labels"],
)
def test_a_changed_job_is_updated_in_place_keeping_hand_keys(monkeypatch, over, kwargs) -> None:
    job = _job(relabel_configs=[{"action": "keep"}], scrape_interval="15s", **over)
    written = _wire(monkeypatch, {"scrape_configs": [{"job_name": "infra"}, job]})
    args = {"target": "svc:8000", "scheme": "http", "metrics_path": "/metrics"} | kwargs
    r = prom.add_scrape_target("svc", **args)
    assert r["status"] == "updated" and r["reload"] == "reloaded"
    assert len(written) == 1
    new = written[0]["scrape_configs"][1]
    assert new["scheme"] == args["scheme"] and new["metrics_path"] == args["metrics_path"]
    assert new["static_configs"][0]["targets"] == [args["target"]]
    assert new["relabel_configs"] == [{"action": "keep"}]
    assert new["scrape_interval"] == "15s"  # interval applies on create only
    assert written[0]["scrape_configs"][0] == {"job_name": "infra"}
    if "labels" in str(over):
        assert new["static_configs"][0]["labels"] == {"tier": "x"}


def test_an_unchanged_job_is_not_rewritten(monkeypatch) -> None:
    written = _wire(monkeypatch, {"scrape_configs": [_job()]})
    r = prom.add_scrape_target("svc", target="svc:8000", scheme="http")
    assert r["status"] == "exists" and r["reload"] == "reloaded"
    assert written == []


def test_absent_scheme_and_path_read_as_prometheus_defaults(monkeypatch) -> None:
    job = _job()
    del job["scheme"], job["metrics_path"]
    written = _wire(monkeypatch, {"scrape_configs": [job]})
    assert prom.add_scrape_target("svc", target="svc:8000", scheme="http")["status"] == "exists"
    assert written == []


# ── Behaviour 5: authorization ───────────────────────────────────────────────────────── #


def test_a_credentials_file_secret_is_kept_when_the_spec_has_a_token(monkeypatch) -> None:
    auth = {"type": "Bearer", "credentials_file": "/etc/prometheus/secrets/svc"}
    written = _wire(monkeypatch, {"scrape_configs": [_job(authorization=auth)]})
    r = prom.add_scrape_target("svc", target="svc:8000", scheme="http", bearer_token="t0k")
    assert r["status"] == "exists" and written == []


def test_an_inline_token_that_changed_is_updated(monkeypatch) -> None:
    auth = {"type": "Bearer", "credentials": "old"}
    written = _wire(monkeypatch, {"scrape_configs": [_job(authorization=auth)]})
    r = prom.add_scrape_target("svc", target="svc:8000", scheme="http", bearer_token="new")
    assert r["status"] == "updated"
    assert written[0]["scrape_configs"][0]["authorization"] == {
        "type": "Bearer",
        "credentials": "new",
    }


def test_a_missing_token_block_is_added(monkeypatch) -> None:
    written = _wire(monkeypatch, {"scrape_configs": [_job()]})
    r = prom.add_scrape_target("svc", target="svc:8000", scheme="http", bearer_token="t0k")
    assert r["status"] == "updated"
    assert written[0]["scrape_configs"][0]["authorization"]["credentials"] == "t0k"


def test_no_token_leaves_a_hand_set_auth_block_alone(monkeypatch) -> None:
    auth = {"type": "Bearer", "credentials_file": "/etc/prometheus/secrets/svc"}
    written = _wire(monkeypatch, {"scrape_configs": [_job(authorization=auth)]})
    assert prom.add_scrape_target("svc", target="svc:8000", scheme="http")["status"] == "exists"
    assert written == []


@pytest.mark.parametrize("key", ["basic_auth", "bearer_token", "bearer_token_file", "oauth2"])
def test_a_token_beside_another_auth_form_is_refused(monkeypatch, key) -> None:
    job = _job(**{key: {"x": 1}}, scheme="https")
    before = copy.deepcopy(job)
    written = _wire(monkeypatch, {"scrape_configs": [job]})
    with pytest.raises(ValueError, match=key):
        prom.add_scrape_target("svc", target="svc:8000", scheme="http", bearer_token="t0k")
    assert written == [] and job == before  # refused before anything changed


@pytest.mark.parametrize("key", ["basic_auth", "bearer_token"])
def test_a_null_auth_key_is_no_clash(monkeypatch, key) -> None:
    written = _wire(monkeypatch, {"scrape_configs": [_job(**{key: None})]})
    r = prom.add_scrape_target("svc", target="svc:8000", scheme="http", bearer_token="t0k")
    assert r["status"] == "updated" and len(written) == 1


def test_an_untyped_inline_token_that_matches_is_current(monkeypatch) -> None:
    written = _wire(monkeypatch, {"scrape_configs": [_job(authorization={"credentials": "t"})]})
    r = prom.add_scrape_target("svc", target="svc:8000", scheme="http", bearer_token="t")
    assert r["status"] == "exists" and written == []


# ── Behaviour 6: static_configs shapes ──────────────────────────────────────────────── #


@pytest.mark.parametrize(
    "static", [None, [], [{"targets": None}], [{}]], ids=["none", "empty", "null-targets", "no-key"]
)
def test_an_empty_static_config_is_set(monkeypatch, static) -> None:
    job = _job(static_configs=static)
    if static is None:
        del job["static_configs"]
    written = _wire(monkeypatch, {"scrape_configs": [job]})
    assert prom.add_scrape_target("svc", target="svc:8000", scheme="http")["status"] == "updated"
    assert written[0]["scrape_configs"][0]["static_configs"][0]["targets"] == ["svc:8000"]


@pytest.mark.parametrize(
    "static",
    [
        [{"targets": ["a:1"]}, {"targets": ["b:2"]}],
        "svc:8000",
        ["svc:8000"],
        [{"targets": ["svc:8000", "svc2:8000"]}],
    ],
    ids=["two-entries", "a-string", "non-dict-entry", "two-targets"],
)
def test_a_hand_shaped_static_config_is_refused_before_any_write(monkeypatch, static) -> None:
    job = _job(static_configs=static, scheme="https")
    before = copy.deepcopy(job)
    written = _wire(monkeypatch, {"scrape_configs": [job]})
    with pytest.raises(ValueError, match="static_configs"):
        prom.add_scrape_target("svc", target="svc:8000", scheme="http")
    assert written == [] and job == before


@pytest.mark.parametrize("sd", ["file_sd_configs", "http_sd_configs"])
def test_a_service_discovery_job_is_refused(monkeypatch, sd) -> None:
    job = _job(**{sd: [{"files": ["x.json"]}]})
    del job["static_configs"]
    written = _wire(monkeypatch, {"scrape_configs": [job]})
    with pytest.raises(ValueError, match=sd):
        prom.add_scrape_target("svc", target="svc:8000", scheme="http")
    assert written == [] and "static_configs" not in job


# ── Behaviour 7: rollback removes only a job this run created ─────────────────────────── #


def _provisioned(status: str, reload: str = "reloaded") -> DeploymentContext:
    prov = InfrastructureProvisioner(deployer=mock.MagicMock())
    ctx = DeploymentContext(spec_path=Path("specs/services/svc.yaml"))
    result = {"status": status, "job": _JOB, "target": "svc:8000", "reload": reload}
    with mock.patch("fabrik.drivers.prometheus.add_scrape_target", return_value=result):
        prov._provision_prometheus("svc", "svc.example.com", {}, ctx, False)
    return ctx


@pytest.mark.parametrize(
    ("status", "reload", "removed"),
    [
        ("created", "reloaded", True),
        ("created", "refused", True),  # recorded failed, but this run appended it
        ("exists", "reloaded", False),
        ("updated", "reloaded", False),
        ("updated", "refused", False),
    ],
)
def test_rollback_removes_only_a_job_this_run_created(status, reload, removed) -> None:
    ctx = _provisioned(status, reload)
    (rec,) = ctx.get_resources_by_type("prometheus")
    with mock.patch("fabrik.drivers.prometheus.remove_scrape_target") as rm:
        RollbackManager()._rollback_prometheus(rec)
    assert rm.called is removed


def test_a_legacy_row_without_job_metadata_falls_back_to_status() -> None:
    with mock.patch("fabrik.drivers.prometheus.remove_scrape_target") as rm:
        RollbackManager()._rollback_prometheus(
            ResourceRecord("prometheus", "svc", metadata={"status": "exists"})
        )
        assert not rm.called
        RollbackManager()._rollback_prometheus(
            ResourceRecord("prometheus", "svc", metadata={"status": "created"})
        )
        assert rm.called
