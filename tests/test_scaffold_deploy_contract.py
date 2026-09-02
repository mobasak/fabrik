"""Phase C of docs/development/plans/2026-09-01-plan-1-deployment-verification.md — born compliant.

Every SCAFFOLDABLE type seeds the deployment-verification contract stub (exits 2 until authored),
the vendored health-probe it imports, and the fleet-AI doc sections; `wordpress` is refused, not
seeded; a `docusaurus` scaffold publishes none of the new doc sections (they are deployed-docs,
which that type never receives). Scaffolds are cached per type — every test here only READS.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from fabrik.scaffold import SCAFFOLD_TYPES, create_project

REPO = Path(__file__).resolve().parents[1]
_HUB_VENDORED = REPO / "libs" / "health_probe"
_LIB_SRC = Path("/opt/fabrik-lib/health-probe")
TEMPLATE = REPO / "templates" / "scaffold" / "scripts" / "verify_prod_parity.py"
SCAFFOLDABLE = sorted(t for t in SCAFFOLD_TYPES if t != "wordpress")

_CACHE: dict[str, Path] = {}


def _scaffold(tmp_path_factory: pytest.TempPathFactory, project_type: str) -> Path:
    cached = _CACHE.get(project_type)
    if cached is not None and cached.exists():
        return cached
    base = tmp_path_factory.mktemp(f"dc-{project_type}")
    name = f"dc-{project_type}"
    create_project(
        name=name,
        project_type=project_type,
        description="deploy-contract test",
        base=base,
        generate_spec=False,
    )
    out = base / name
    _CACHE[project_type] = out
    return out


def _run(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(cwd)}
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_denominator_is_the_live_registry_minus_wordpress():
    assert len(SCAFFOLDABLE) == len(SCAFFOLD_TYPES) - 1, SCAFFOLD_TYPES


@pytest.mark.parametrize("project_type", SCAFFOLDABLE)
def test_stub_seeded_and_exits_2(tmp_path_factory, project_type):
    p = _scaffold(tmp_path_factory, project_type)
    stub = p / "scripts" / "verify_prod_parity.py"
    assert stub.is_file(), f"{project_type}: stub not seeded"
    assert os.access(stub, os.X_OK), f"{project_type}: stub not executable"
    hdr = json.loads(_run(stub, "--header", cwd=p).stdout)
    assert hdr["parsed"] == "true" and hdr["status"] == "DRAFT" and hdr["version"] == "v0"
    r = _run(stub, "--json", cwd=p)
    assert r.returncode == 2, (
        f"{project_type}: an unfilled contract must fail closed (exit 2), got {r.returncode}: {r.stderr}"
    )
    rows = json.loads(r.stdout)
    assert rows and rows[0]["system"] == "l0_health_probe_vendored" and rows[0]["match"] is True, (
        rows
    )


@pytest.mark.parametrize("project_type", SCAFFOLDABLE)
def test_health_probe_vendored_and_in_sync(tmp_path_factory, project_type):
    p = _scaffold(tmp_path_factory, project_type)
    for name in ("health_probe.py", "fingerprint.py", "__init__.py"):
        seeded = p / "libs" / "health_probe" / name
        assert seeded.is_file(), f"{project_type}: {name} not seeded"
        assert seeded.read_bytes() == (_HUB_VENDORED / name).read_bytes(), (
            f"{project_type}: {name} differs from the hub's copy"
        )


@pytest.mark.skipif(not _LIB_SRC.is_dir(), reason="fabrik-lib not present on this box")
def test_hub_copy_differs_from_fabrik_lib_only_by_the_vendoring_header():
    for name in ("health_probe.py", "fingerprint.py"):
        hub = (_HUB_VENDORED / name).read_text(encoding="utf-8").splitlines(keepends=True)
        lib = (_LIB_SRC / name).read_text(encoding="utf-8").splitlines(keepends=True)
        assert hub[0].startswith(f"# VENDORED-FROM fabrik-lib health-probe/{name} @ "), hub[0]
        assert hub[1] == "# ruff: noqa\n" and hub[2] == "# fmt: off\n"
        assert hub[3:] == lib, f"{name}: drift below the header — re-vendor, never edit"


def test_vendored_dir_is_in_the_synced_manifest():
    sys.path.insert(0, str(REPO / "scripts"))
    from fabrik_synced_manifest import VENDORED_DIRS  # noqa: PLC0415

    assert "libs/health_probe" in VENDORED_DIRS


def test_stub_without_vendored_module_fails_closed(tmp_path):
    """The lazy import: no libs/health_probe on the path → the precondition row is UNVERIFIABLE,
    exit 2, no traceback."""
    stub = REPO / "templates" / "scaffold" / "scripts" / "verify_prod_parity.py"
    bare = tmp_path / "bare"
    bare.mkdir()
    r = _run(stub, "--json", cwd=bare)
    assert r.returncode == 2 and "Traceback" not in r.stderr, r.stderr
    rows = json.loads(r.stdout)
    assert rows[0]["match"] is None and rows[0]["detail"].startswith(
        "UNVERIFIABLE (health_probe not vendored"
    )


def test_wordpress_is_not_scaffolded(tmp_path):
    with pytest.raises(NotImplementedError):
        create_project(
            name="dc-wp",
            project_type="wordpress",
            description="x",
            base=tmp_path,
            generate_spec=False,
        )
    assert not (tmp_path / "dc-wp").exists()


def test_fleet_ai_sections_present_in_the_templates():
    dep = (REPO / "templates/scaffold/docs/DEPLOYMENT_TEMPLATE.md").read_text()
    ops = (REPO / "templates/scaffold/docs/OPERATIONS_TEMPLATE.md").read_text()
    assert (
        "## Fleet-AI interface — what to deploy" in dep
        and "{PROJECT_NAME}: to be filled by /fabrik-deploy-checklist" in dep
    )
    assert (
        "## 5b. Fleet-AI interface — what runs" in ops
        and "{PROJECT_NAME}: to be filled by /fabrik-deploy-checklist" in ops
    )
    # the sentinel is one check_doc_stubs recognises (its PLACEHOLDERS tuple), so an unfilled stub is visible
    sys.path.insert(0, str(REPO / "scripts" / "enforcement"))
    from check_doc_stubs import PLACEHOLDERS  # noqa: PLC0415

    assert "{PROJECT_NAME}" in PLACEHOLDERS


def test_docusaurus_does_not_publish_fleet_ai_sections(tmp_path_factory):
    """docusaurus publishes its whole docs/ tree; the deployed-docs bucket (DEPLOYMENT/OPERATIONS)
    is never seeded there — so the new sections cannot leak. Assert the absence, not a config."""
    p = _scaffold(tmp_path_factory, "docusaurus")
    assert not (p / "docs" / "DEPLOYMENT.md").exists()
    assert not (p / "docs" / "OPERATIONS.md").exists()
    assert not list(p.rglob("*Fleet-AI interface*"))


# ── review 2026-09-02 (shipped-surface review, fit for the first real run) — seen RED first ──────────


def _run_as_documented(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """`python scripts/verify_prod_parity.py …` exactly as the two commands document it — NO
    PYTHONPATH injection (the `_run` rig above injects the project root, which is precisely what
    masked the defect: `sys.path[0]` is `scripts/`, so `libs.health_probe` was never importable)."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_precondition_row_finds_the_vendored_module_when_run_as_documented(
    tmp_path: Path,
) -> None:
    """A project with `libs/health_probe/` vendored and the stub run the documented way
    (`python scripts/verify_prod_parity.py --json`, cwd = project root, no PYTHONPATH) must see the
    module: the l0 row is a real comparison row with `match: True`, not UNVERIFIABLE 'not vendored'."""
    proj = tmp_path / "proj"
    (proj / "scripts").mkdir(parents=True)
    shutil.copytree(REPO / "libs" / "health_probe", proj / "libs" / "health_probe")
    stub = proj / "scripts" / "verify_prod_parity.py"
    shutil.copy(TEMPLATE, stub)
    r = _run_as_documented(stub, "--json", cwd=proj)
    rows = json.loads(r.stdout)
    l0 = next(x for x in rows if x["system"] == "l0_health_probe_vendored")
    assert l0["match"] is True, l0
    assert not str(l0.get("detail", "")).startswith("UNVERIFIABLE"), l0


def test_a_frozen_contract_with_no_parity_row_is_never_confirmed() -> None:
    """A check that cannot fail is a defect: a FROZEN header over an empty parity denominator must
    fail closed (exit 2), not certify '0 of 0'."""
    sys.path.insert(0, str(REPO / "scripts"))
    import verify_prod_parity as vp  # noqa: PLC0415

    v = vp.verdict([], {"status": "FROZEN", "version": "v1", "date": "2026-09-02", "mode": "B"})
    assert v["verdict"] != "CONFIRMED" and v["exit"] == 2, v
    v2 = vp.verdict(
        [vp.liveness_row("l1_health", True, "200")],
        {"status": "FROZEN", "version": "v1", "date": "2026-09-02", "mode": "B"},
    )
    assert v2["verdict"] != "CONFIRMED" and v2["exit"] == 2, v2


def test_self_check_refuses_a_contract_that_only_carries_the_precondition_row(
    tmp_path: Path,
) -> None:
    """The seeded stub's single row is the module precondition; freezing THAT certifies nothing.
    `--self-check` must report a miss until at least one corpus row is authored."""
    proj = tmp_path / "proj"
    (proj / "scripts").mkdir(parents=True)
    shutil.copytree(REPO / "libs" / "health_probe", proj / "libs" / "health_probe")
    stub = proj / "scripts" / "verify_prod_parity.py"
    shutil.copy(TEMPLATE, stub)
    r = _run_as_documented(stub, "--self-check", cwd=proj)
    assert r.returncode == 2, (r.returncode, r.stdout)
    assert "precondition" in r.stdout.lower(), r.stdout


def test_an_unknown_flag_prints_usage_instead_of_silently_running_the_contract(
    tmp_path: Path,
) -> None:
    """`--verdcit` (a typo) must not fall through to the default contract run and exit 2 as if it
    had evaluated something — usage on stderr, exit 64 (EX_USAGE); `--help` is the same text, exit 0."""
    proj = tmp_path / "proj"
    (proj / "scripts").mkdir(parents=True)
    stub = proj / "scripts" / "verify_prod_parity.py"
    shutil.copy(TEMPLATE, stub)
    bad = _run_as_documented(stub, "--verdcit", cwd=proj)
    assert bad.returncode == 64 and "usage" in bad.stderr.lower(), (bad.returncode, bad.stderr)
    helped = _run_as_documented(stub, "--help", cwd=proj)
    assert helped.returncode == 0 and "--verdict" in helped.stdout, helped.stdout


# ── review 2026-09-02 (second pass, after tryton-crm's first real freeze) — seen RED first ─────────


def _vp():
    sys.path.insert(0, str(REPO / "scripts"))
    import importlib

    import verify_prod_parity as vp  # noqa: PLC0415

    return importlib.reload(vp)


def test_header_without_mode_parses_and_an_older_header_with_mode_still_parses(
    tmp_path: Path,
) -> None:
    """The modes are gone: `# Status · Version · Date` is the header. A contract frozen before the
    change carries a trailing `· Mode: B` — it must keep parsing (tryton-crm v1 is such a file)."""
    vp = _vp()
    new = tmp_path / "new.py"
    new.write_text("#!/usr/bin/env python3\n# Status: FROZEN · Version: v2 · Date: 2026-09-02\n")
    old = tmp_path / "old.py"
    old.write_text(
        "#!/usr/bin/env python3\n# Status: FROZEN · Version: v1 · Date: 2026-09-02 · Mode: B\n"
    )
    assert vp.parse_header(new)["parsed"] == "true" and vp.parse_header(new)["status"] == "FROZEN"
    assert vp.parse_header(old)["parsed"] == "true" and vp.parse_header(old)["version"] == "v1"


def test_self_check_never_executes_a_row(tmp_path: Path) -> None:
    """`--self-check` is the FREEZE CHECKLIST, run repeatedly while authoring: it must be STATIC. tryton-crm's
    first freeze showed why — its self-check fired 20 HTTPS probes and a failed-login POST at production on
    every run because the seeded stub executed every row to 'check the shape'."""
    proj = tmp_path / "proj"
    (proj / "scripts").mkdir(parents=True)
    shutil.copytree(REPO / "libs" / "health_probe", proj / "libs" / "health_probe")
    stub = proj / "scripts" / "verify_prod_parity.py"
    src = TEMPLATE.read_text()
    sentinel = proj / "row-was-executed"
    src = src.replace(
        "ROWS: list[Callable[[], dict[str, Any]]] = [l0_health_probe_vendored]",
        "def l9_probe():\n"
        f"    Path({str(sentinel)!r}).write_text('x')\n"
        "    return liveness_row('l9_probe', True, 'ran')\n\n"
        "ROWS: list[Callable[[], dict[str, Any]]] = [l0_health_probe_vendored, l9_probe]",
    )
    stub.write_text(src)
    r = _run_as_documented(stub, "--self-check", cwd=proj)
    assert not sentinel.exists(), "self-check executed a row (it must be static)"
    assert r.returncode == 0, (r.returncode, r.stdout)


def test_rows_declare_a_site_and_site_filters_the_run(tmp_path: Path) -> None:
    """Every row carries a SITE — hub (public surface), host (the VPS host: docker ps, volumes) or container
    (inside the app container: the DB, redis, the internal network). `--site X` runs only X's rows, so the
    runner can execute each leg where it can reach, and merge."""
    vp = _vp()
    ran: list[str] = []

    @vp.site("container")
    def l2_db():
        ran.append("db")
        return vp.liveness_row("l2_db", True, "")

    def l4_public():
        ran.append("public")
        return vp.liveness_row("l4_public", True, "")

    assert (
        vp.row_site(l2_db) == "container" and vp.row_site(l4_public) == "hub"
    )  # hub is the default
    rows = vp.run_rows([l2_db, l4_public], site="hub")
    assert ran == ["public"] and [r["system"] for r in rows] == ["l4_public"]


def test_a_leg_that_could_not_run_is_emitted_unverifiable_not_dropped(tmp_path: Path) -> None:
    """`--site container --unreachable "<why>"` emits that site's rows as UNVERIFIABLE (fail closed) so the
    denominator is never quietly shortened by a leg the runner could not reach."""
    vp = _vp()

    @vp.site("container")
    def l2_db():
        raise AssertionError("must not run")

    rows = vp.run_rows([l2_db], site="container", unreachable="no ssh to vps1")
    assert rows[0]["system"] == "l2_db" and rows[0]["match"] is None
    assert "no ssh to vps1" in rows[0]["detail"] and rows[0]["detail"].startswith("UNVERIFIABLE")


def test_verdict_merges_row_files_from_several_legs(tmp_path: Path) -> None:
    """`--verdict --rows-from a.json b.json` applies the algebra to the UNION of the legs' rows."""
    proj = tmp_path / "proj"
    (proj / "scripts").mkdir(parents=True)
    stub = proj / "scripts" / "verify_prod_parity.py"
    src = TEMPLATE.read_text().replace(
        "# Status: DRAFT · Version: v0 · Date: —",
        "# Status: FROZEN · Version: v1 · Date: 2026-09-02",
    )
    stub.write_text(src)
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(
        json.dumps(
            [
                {
                    "system": "x",
                    "status": "OK",
                    "detail": "",
                    "expected": 1,
                    "actual": 1,
                    "match": True,
                }
            ]
        )
    )
    b.write_text(
        json.dumps(
            [
                {
                    "system": "y",
                    "status": "OK",
                    "detail": "",
                    "expected": 1,
                    "actual": 2,
                    "match": False,
                }
            ]
        )
    )
    ok = _run_as_documented(stub, "--verdict", "--rows-from", str(a), cwd=proj)
    assert ok.returncode == 0 and "VERDICT: CONFIRMED" in ok.stdout, ok.stdout
    both = _run_as_documented(stub, "--verdict", "--rows-from", str(a), str(b), cwd=proj)
    assert both.returncode == 2 and "1 disagree" in both.stdout and " of 2 " in both.stdout, (
        both.stdout
    )


def test_not_obligated_set_is_wired_into_the_cli_verdict(tmp_path: Path) -> None:
    """The stub declares `NOT_OBLIGATED` and `--verdict` must apply it — tryton-crm had to add the wiring
    by hand because the seeded `main()` never passed it."""
    proj = tmp_path / "proj"
    (proj / "scripts").mkdir(parents=True)
    stub = proj / "scripts" / "verify_prod_parity.py"
    src = TEMPLATE.read_text().replace(
        "# Status: DRAFT · Version: v0 · Date: —",
        "# Status: FROZEN · Version: v1 · Date: 2026-09-02",
    )
    src = src.replace(
        "NOT_OBLIGATED: frozenset[str] = frozenset()",
        'NOT_OBLIGATED: frozenset[str] = frozenset({"x"})',
    )
    assert 'frozenset({"x"})' in src
    stub.write_text(src)
    a = tmp_path / "a.json"
    a.write_text(
        json.dumps(
            [
                {
                    "system": "x",
                    "status": "OK",
                    "detail": "",
                    "expected": 1,
                    "actual": 2,
                    "match": False,
                },
                {
                    "system": "y",
                    "status": "OK",
                    "detail": "",
                    "expected": 1,
                    "actual": 1,
                    "match": True,
                },
            ]
        )
    )
    r = _run_as_documented(stub, "--verdict", "--rows-from", str(a), cwd=proj)
    assert r.returncode == 0 and "1 not obligated" in r.stdout and " of 1 " in r.stdout, r.stdout


def test_a_misspelt_site_or_a_bare_unreachable_is_a_usage_error(tmp_path: Path) -> None:
    """`--site contaner` must not silently run zero rows (which would fail closed with a misleading
    'empty denominator'); `--unreachable` without `--site` would mark EVERY row unverifiable. Both: usage, 64."""
    proj = tmp_path / "proj"
    (proj / "scripts").mkdir(parents=True)
    stub = proj / "scripts" / "verify_prod_parity.py"
    shutil.copy(TEMPLATE, stub)
    bad_site = _run_as_documented(stub, "--json", "--site", "contaner", cwd=proj)
    assert bad_site.returncode == 64 and "site" in bad_site.stderr, (
        bad_site.returncode,
        bad_site.stderr[:200],
    )
    bare = _run_as_documented(stub, "--json", "--unreachable", "no ssh", cwd=proj)
    assert bare.returncode == 64 and "--site" in bare.stderr, (bare.returncode, bare.stderr[:200])
