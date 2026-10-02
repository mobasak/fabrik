"""Backrest coverage: read-only discovery, trust, coverage and the shared check (W-5c4ad6a6, D-518).

The registrar used to write a plan at a hardcoded ``/opt/<name>/data`` that existed for none of the 21 persistent
services, so every such plan failed nightly and backed up nothing. These tests pin the read-only replacement: which
paths a service really persists (discovery), which plans Backrest can actually run (trust), whether a path is under
one (coverage), and the table the registrar warns from and the audit reports (``coverage_findings``).

A3/A4 EXECUTE the real discovery script under bash with stub ``sudo``/``docker`` binaries (the pattern of
``tests/test_prometheus_reload_path.py``), so the mount filtering that happens on the VPS is tested, not assumed.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from fabrik.drivers import backrest

# ── A1/A2: trust and coverage (pure) ───────────────────────────────────────────────────────────────────────────────


def _plan(pid, paths, excludes=(), **kw):
    p = {
        "id": pid,
        "paths": list(paths),
        "excludes": list(excludes),
        "iexcludes": [],
        "backup_flags": [],
        "scheduled": True,
        "disabled": False,
    }
    p.update(kw)
    return p


DV = _plan("docker-volumes", ["/var/lib/docker/volumes"], ["prom-data"])
OC = _plan("opt-configs", ["/opt/"], ["**/cache"])
VIS = {"/var/lib/docker/volumes", "/opt"}


def test_a1_coverage_maps_paths_to_trusted_plans_and_respects_excludes():
    paths = [
        "/var/lib/docker/volumes/x_y/_data",
        "/var/lib/docker/volumes/prom-data/_data",
        "/opt/a/data",
        "/opt/a/cache/sub",
        "/opt/ab/x",
        "/srv/z",
    ]
    got = backrest.coverage(paths, [DV, OC], VIS)
    assert [got[p] for p in paths] == [
        "docker-volumes",
        None,
        "opt-configs",
        None,
        "opt-configs",
        None,
    ]


def test_a1_a_path_is_attributed_to_its_most_specific_plan():
    broad, narrow = _plan("a-plan", ["/opt"]), _plan("b-plan", ["/opt/a"])
    assert backrest.coverage(["/opt/a/data"], [broad, narrow], {"/opt", "/opt/a"}) == {
        "/opt/a/data": "b-plan"
    }


def test_a1_a_plan_never_covers_a_sibling_prefix():
    plan = _plan("a", ["/opt/a"])
    assert backrest.coverage(["/opt/ab"], [plan], {"/opt/a"}) == {"/opt/ab": None}
    assert backrest.coverage(["/opt/a/x"], [plan], {"/opt/a"}) == {"/opt/a/x": "a"}


@pytest.mark.parametrize("exclude", ["docker", "cache/", "/var/lib/docker"])
def test_a1_an_exclude_matching_a_component_above_the_plan_root_uncovers_the_path(exclude):
    # restic matches excludes against the whole path; reading only below the root under-excludes.
    plan = _plan("p", ["/var/lib/docker/volumes"], [exclude])
    path = (
        "/var/lib/docker/volumes/cache/_data"
        if exclude == "cache/"
        else "/var/lib/docker/volumes/v/_data"
    )
    assert backrest.coverage([path], [plan], {"/var/lib/docker/volumes"}) == {path: None}


@pytest.mark.parametrize(
    "override",
    [
        {"iexcludes": ["*.tmp"]},
        {"backup_flags": ["--exclude-caches"]},
        {"scheduled": False},
        {"disabled": True},
        {"paths": ["/opt", "/gone"]},  # one plan path Backrest cannot stat fails the whole run
        {"excludes": ["/"]},
        {"excludes": ["[!a]x"]},
        {"excludes": ["\\x"]},
        {"excludes": ["$HOME"]},
        {"excludes": ["!keep"]},
    ],
)
def test_a2_a_plan_backrest_cannot_fully_run_covers_nothing(override):
    plan = _plan("opt-configs", ["/opt"])
    plan.update(override)
    assert backrest.coverage(["/opt/a/data"], [plan], {"/opt"}) == {"/opt/a/data": None}


def test_a2_trusted_needs_every_plan_path_visible():
    assert backrest.trusted(_plan("p", ["/opt"]), {"/opt"}) is True
    assert backrest.trusted(_plan("p", ["/opt", "/x"]), {"/opt"}) is False
    assert backrest.trusted(_plan("p", []), set()) is False


# ── A3/A4: discovery, executed for real under stub binaries ───────────────────────────────────────────────────────

_DOCKER = r"""#!/bin/bash
printf '%s\n' "$*" >> "$DOCKER_LOG"
if [[ "$1" == ps ]]; then
  if [[ "$*" == *"label=com.docker.compose.project="* ]]; then
    for i in $LABEL_IDS; do echo "$i"; done; exit 0
  fi
  if [[ "$*" == *"--filter name="* ]]; then
    pat="${*##*--filter name=}"; pat="${pat%% *}"
    for n in $NAMES; do [[ "$n" =~ $pat ]] && echo "$n"; done; exit 0
  fi
  exit 0
fi
if [[ "$1" == inspect ]]; then printf '%b' "$MOUNTS"; exit 0; fi
exit 0
"""


def _host(tmp_path: Path, *, label_ids="", names="", mounts="") -> dict:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    (bindir / "sudo").write_text('#!/bin/bash\nexec "$@"\n')
    (bindir / "docker").write_text(_DOCKER)
    for f in ("sudo", "docker"):
        (bindir / f).chmod(0o755)
    return {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "LABEL_IDS": label_ids,
        "NAMES": names,
        "MOUNTS": mounts,
        "DOCKER_LOG": str(tmp_path / "docker.log"),
    }


def _run_remote(monkeypatch, env) -> list[str]:
    sent: list[str] = []

    def fake_ssh(cmd, timeout=60, dry_run=False):
        sent.append(cmd)
        r = subprocess.run(
            ["bash", "-c", cmd], capture_output=True, text=True, env=env, timeout=30, check=False
        )
        if r.returncode != 0:
            raise RuntimeError(f"rc={r.returncode}: {r.stderr.strip()}")
        return r.stdout.strip()

    monkeypatch.setattr(backrest, "ssh", fake_ssh)
    return sent


def test_a3_discovery_keeps_named_volumes_and_writable_bind_dirs_only(monkeypatch, tmp_path):
    data_dir = tmp_path / "srv" / "media"
    data_dir.mkdir(parents=True)
    ro_dir = tmp_path / "ro"
    ro_dir.mkdir()
    piped = tmp_path / "a|b"  # a '|' in a path must not cost the mount
    piped.mkdir()
    conf = tmp_path / "app.conf"
    conf.write_text("x")
    anon = "a" * 64
    mounts = (
        f"volume|svc_data|true|/var/lib/docker/volumes/svc_data/_data\\n"
        f"volume|{anon}|true|/var/lib/docker/volumes/{anon}/_data\\n"
        f"bind||true|{data_dir}\\n"
        f"bind||true|{piped}\\n"
        f"bind||false|{ro_dir}\\n"
        f"bind||true|{conf}\\n"
        f"bind||true|/var/run/docker.sock\\n"
        f"tmpfs||true|\\n"
    )
    env = _host(tmp_path, label_ids="c1", mounts=mounts)
    sent = _run_remote(monkeypatch, env)
    found = backrest.discover_persistence("svc")
    assert found == backrest.Persistence(
        containers=1,
        paths=sorted(["/var/lib/docker/volumes/svc_data/_data", str(data_dir), str(piped)]),
        anonymous=1,
    )
    assert sent[0].startswith("bash -o pipefail -c ")
    # the Go template reaches docker intact through shlex + bash -c (the stub cannot evaluate it)
    inspect = [
        ln for ln in (tmp_path / "docker.log").read_text().splitlines() if ln.startswith("inspect")
    ]
    assert inspect == [
        'inspect --format {{range .Mounts}}{{.Type}}|{{.Name}}|{{.RW}}|{{.Source}}{{"\\n"}}{{end}} c1'
    ]


def test_a4_zero_containers_and_the_exact_name_fallback(monkeypatch, tmp_path):
    env = _host(tmp_path, names="svc-other")
    sent = _run_remote(monkeypatch, env)
    assert backrest.discover_persistence("svc") == backrest.Persistence(0, [], 0)
    # the stub models docker's filter; the text assertion pins what real docker receives
    assert "name=^svc$" in sent[0]
    assert "label=com.docker.compose.project=svc" in sent[0]


# ── A5/A6: failure, validation, secrets ───────────────────────────────────────────────────────────────────────────


def test_a5_a_failed_probe_is_none_and_names_are_validated_before_ssh(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("ssh: connect timed out")

    monkeypatch.setattr(backrest, "ssh", boom)
    assert backrest.discover_persistence("tryton-crm") is None
    assert backrest.read_plans() is None
    assert backrest.visible(["/opt"]) is None
    assert backrest.visible([]) == set()  # no SSH for an empty input

    calls: list[str] = []
    monkeypatch.setattr(backrest, "ssh", lambda c, **k: calls.append(c) or "")
    with pytest.raises(ValueError):
        backrest.discover_persistence("bad name; rm -rf /")
    assert calls == []


def test_a6_read_plans_selects_only_plan_fields(monkeypatch):
    sent: list[str] = []
    out = '[{"id":"p","paths":["/opt"],"excludes":[],"iexcludes":[],"backup_flags":[],"scheduled":true,"disabled":false}]'
    monkeypatch.setattr(backrest, "ssh", lambda c, **k: sent.append(c) or out)
    plans = backrest.read_plans()
    assert plans == [_plan("p", ["/opt"])]
    assert "repos" not in sent[0] and "password" not in sent[0]
    for field in ("paths", "excludes", "iexcludes", "backup_flags", "scheduled", "disabled"):
        assert field in sent[0]
    assert set(plans[0]) == {
        "id",
        "paths",
        "excludes",
        "iexcludes",
        "backup_flags",
        "scheduled",
        "disabled",
    }


# ── A7: the shared check — the database is a dump that exists, checked on the hub ─────────────────────────────────


def _fakes(monkeypatch, *, found, plans_by_host, visible_by_host):
    seen: list[tuple[str, str]] = []

    def host():
        return os.environ.get("FABRIK_VPS_SSH_HOST", "")

    def disc(name):
        seen.append(("discover", host()))
        return found

    def rp():
        seen.append(("plans", host()))
        return plans_by_host[host()]

    def vis(paths):
        seen.append(("visible", host()))
        return {p for p in paths if p.rstrip("/") in visible_by_host[host()]}

    monkeypatch.setattr(backrest, "discover_persistence", disc)
    monkeypatch.setattr(backrest, "read_plans", rp)
    monkeypatch.setattr(backrest, "visible", vis)
    return seen


@pytest.mark.parametrize(
    ("hub_visible", "hub_plans", "expect_covered"),
    [
        (
            {"/opt/backups", "/opt/backups/postgres/zitadel"},
            [_plan("postgres-dumps", ["/opt/backups"])],
            True,
        ),
        ({"/opt/backups"}, [_plan("postgres-dumps", ["/opt/backups"])], False),  # dump dir absent
        ({"/opt/backups/postgres/zitadel"}, [], False),  # visible but no trusted plan
    ],
)
def test_a7_the_database_is_covered_only_by_an_existing_dump_on_the_hub(
    monkeypatch, hub_visible, hub_plans, expect_covered
):
    seen = _fakes(
        monkeypatch,
        found=backrest.Persistence(1, ["/var/lib/docker/volumes/z/_data"], 0),
        plans_by_host={"spoke": [DV], "hub": hub_plans},
        visible_by_host={"spoke": {"/var/lib/docker/volumes"}, "hub": hub_visible},
    )
    monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "orig")
    status, findings, _ = backrest.coverage_findings(
        "zitadel", "zitadel", target_host="spoke", hub_host="hub"
    )
    db_finding = "database zitadel: no dump covered"
    assert (db_finding not in findings) is expect_covered
    assert status == ("present" if expect_covered else "drift")
    assert ("discover", "spoke") in seen and ("plans", "hub") in seen
    assert all(h == "hub" for kind, h in seen if kind == "plans" and seen.index((kind, h)) > 1)
    assert os.environ["FABRIK_VPS_SSH_HOST"] == "orig"  # restored


def test_a7_an_invalid_db_name_is_a_finding(monkeypatch):
    _fakes(
        monkeypatch,
        found=backrest.Persistence(1, ["/var/lib/docker/volumes/z/_data"], 0),
        plans_by_host={"t": [DV]},
        visible_by_host={"t": {"/var/lib/docker/volumes"}},
    )
    status, findings, _ = backrest.coverage_findings("svc", "Bad-DB", target_host="t", hub_host="t")
    assert status == "drift"
    assert any("Bad-DB" in f for f in findings)


def test_findings_table_rows(monkeypatch):
    # paper plan, zero containers, shape mismatch, unprotected, unknown
    paper = _plan("svc-data", ["/opt/svc/data"])
    _fakes(
        monkeypatch,
        found=backrest.Persistence(0, [], 0),
        plans_by_host={"t": [DV, paper]},
        visible_by_host={"t": {"/var/lib/docker/volumes"}},
    )
    status, findings, _ = backrest.coverage_findings("svc", None, target_host="t", hub_host="t")
    assert status == "drift" and "paper plan svc-data: remove it" in findings

    _fakes(
        monkeypatch,
        found=backrest.Persistence(0, [], 0),
        plans_by_host={"t": [DV]},
        visible_by_host={"t": set()},
    )
    assert backrest.coverage_findings("svc", None, target_host="t", hub_host="t")[0] == "missing"
    # stopped, but its database dump is uncovered: still a real gap, so drift
    status, findings, _ = backrest.coverage_findings("svc", "svc", target_host="t", hub_host="t")
    assert status == "drift" and findings == ["database svc: no dump covered"]

    _fakes(
        monkeypatch,
        found=backrest.Persistence(2, [], 0),
        plans_by_host={"t": [DV]},
        visible_by_host={"t": set()},
    )
    status, findings, _ = backrest.coverage_findings("svc", None, target_host="t", hub_host="t")
    assert status == "drift" and any("no persistence found" in f for f in findings)

    _fakes(
        monkeypatch,
        found=backrest.Persistence(1, ["/srv/x"], 0),
        plans_by_host={"t": [DV]},
        visible_by_host={"t": {"/var/lib/docker/volumes", "/srv/x"}},
    )
    status, findings, _ = backrest.coverage_findings("svc", None, target_host="t", hub_host="t")
    assert status == "drift" and "unprotected: /srv/x" in findings

    _fakes(monkeypatch, found=None, plans_by_host={"t": [DV]}, visible_by_host={"t": set()})
    assert backrest.coverage_findings("svc", None, target_host="t", hub_host="t")[0] == "unknown"
