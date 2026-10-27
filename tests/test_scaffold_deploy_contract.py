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
from typing import Any

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


def _load_template_module():
    """Import the template by path under a private module name.

    `scripts/verify_prod_parity.py` is a SYMLINK to this same file, so `_vp()` loads the identical
    source — the reason not to reuse it is that it mutates `sys.path` and `importlib.reload`s a
    shared module name, which this grader must not do to its siblings."""
    import importlib.util  # noqa: PLC0415

    spec = importlib.util.spec_from_file_location("_vpp_template", TEMPLATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_value_flag_with_no_value_prints_usage_instead_of_crashing(tmp_path: Path) -> None:
    """Reported by web-ecommerce-factory (01M2SJT2ZVYP1SM573GDEJYG5Z): `_parse` indexed `vals[0]`
    on an empty list, so a value flag with no value died with IndexError before the usage error it
    had already recorded could print.

    This asserts the CLASS, not one repair. Three review rounds showed why: recording `""` also
    avoids the crash, and is WORSE — `run_rows` sentinels on `unreachable is not None`, so a
    recorded value of ANY kind emits `UNVERIFIABLE (<site> leg not run — <it>)` — a why-less row
    when it is empty, which this module's own contract forbids in its docstring (`--self-check`
    does NOT enforce that; it never inspects a row's detail, so the prose obligation and this
    grader are the only guards). So the rule is that a flag given no value records NO ENTRY, and
    the assertion is `flag not in values` rather than a falsy test — `0`, `False` and `[]` are all
    falsy and all reproduce the hazard.

    A BLANK value counts as no value too: `--unreachable ""` is what the runner's own documented
    `--unreachable "<why>"` placeholder produces when the substitution is empty.

    `--unreachable --site hub` is load-bearing and must stay: every other shape is re-caught by
    `main()`'s flag-specific checks, so it is the ONLY shape that reds when `_parse`'s own
    `unknown.append` stops firing — whether by deletion or by an `is None` condition that can never
    be true. Its guard below fails loudly if `--unreachable` is ever retired, because the shape
    would silently decay into a duplicate of the unknown-flag test above.
    """
    vp = _load_template_module()
    positive = sorted(f for f, n in vp._VALUE_FLAGS.items() if n >= 0)
    assert positive, vp._VALUE_FLAGS
    assert "--unreachable" in vp._VALUE_FLAGS, vp._VALUE_FLAGS

    proj = tmp_path / "proj"
    (proj / "scripts").mkdir(parents=True)
    stub = proj / "scripts" / "verify_prod_parity.py"
    shutil.copy(TEMPLATE, stub)

    shapes = [[f] for f in positive] + [["--unreachable", "--site", "hub"]]
    shapes += [["--unreachable", "", "--site", "hub"], ["--unreachable", "   ", "--site", "hub"]]
    for argv in shapes:
        r = _run_as_documented(stub, *argv, cwd=proj)
        assert r.returncode == 64, (argv, r.returncode, r.stdout, r.stderr)
        assert "usage" in r.stderr.lower(), (argv, r.stderr)

    for flag in positive:
        for argv in ([flag], [flag, ""]):
            _, values, unknown = vp._parse(argv)
            assert flag not in values, (argv, values)
            assert any("needs a value" in u for u in unknown), (argv, unknown)

    rows = vp._rows_for(vp._parse(["--unreachable", "--site", "hub"])[1])
    assert rows, "the probe produced no rows, so it asserts nothing"
    assert all("— )" not in r.get("detail", "") for r in rows), rows


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


_XY_CONTRACT = (
    'def x() -> dict[str, Any]:\n    return liveness_row("x", True, "")\n\n\n'
    'def y() -> dict[str, Any]:\n    return liveness_row("y", True, "")\n\n\n'
    "ROWS: list[Callable[[], dict[str, Any]]] = [x, y]"
)


def _frozen_xy_stub(proj: Path) -> Path:
    """The seeded stub, FROZEN, with a contract declaring rows `x` and `y` — `--rows-from` refuses a row the
    contract does not declare and a merge missing one (kaizen D-769), so leg files for x and y need a
    contract that names them. The merge never RUNS x and y — only their names matter here; the leg files
    carry whatever rows the test needs."""
    (proj / "scripts").mkdir(parents=True)
    stub = proj / "scripts" / "verify_prod_parity.py"
    src = TEMPLATE.read_text().replace(
        "# Status: DRAFT · Version: v0 · Date: —",
        "# Status: FROZEN · Version: v1 · Date: 2026-09-02",
    )
    assert src.count(_ROWS_LINE) == 1
    stub.write_text(src.replace(_ROWS_LINE, _XY_CONTRACT))
    return stub


_ROWS_LINE = "ROWS: list[Callable[[], dict[str, Any]]] = [l0_health_probe_vendored]"


def test_verdict_merges_row_files_from_several_legs(tmp_path: Path) -> None:
    """`--verdict --rows-from a.json b.json` applies the algebra to the legs' rows CONCATENATED — every
    contract row exactly once across the files (a doubled or missing row is refused, never merged)."""
    proj = tmp_path / "proj"
    stub = _frozen_xy_stub(proj)
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    b_ok = tmp_path / "b_ok.json"
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
    b_ok.write_text(json.dumps([{"system": "y", "status": "OK", "detail": "pong"}]))
    ok = _run_as_documented(stub, "--verdict", "--rows-from", str(a), str(b_ok), cwd=proj)
    assert ok.returncode == 0 and "VERDICT: CONFIRMED" in ok.stdout, (ok.stdout, ok.stderr)
    both = _run_as_documented(stub, "--verdict", "--rows-from", str(a), str(b), cwd=proj)
    assert both.returncode == 2 and "1 disagree" in both.stdout and " of 2 " in both.stdout, (
        both.stdout
    )
    # one leg alone is NOT a merge: the contract's `y` is missing — refused, never a verdict (D-769)
    alone = _run_as_documented(stub, "--verdict", "--rows-from", str(a), cwd=proj)
    assert alone.returncode == 64 and "'y': missing" in alone.stderr, (alone.stdout, alone.stderr)
    assert "VERDICT:" not in alone.stdout


def test_not_obligated_set_is_wired_into_the_cli_verdict(tmp_path: Path) -> None:
    """The stub declares `NOT_OBLIGATED` and `--verdict` must apply it — tryton-crm had to add the wiring
    by hand because the seeded `main()` never passed it."""
    proj = tmp_path / "proj"
    stub = _frozen_xy_stub(proj)
    src = stub.read_text()
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


# ── tryton-crm's v2/v3 run (01M1J0QP8J, 01M1J185FS) — seen RED first ─────────────────────────


def test_the_contract_declares_its_container_leg_service_and_header_carries_it(
    tmp_path: Path,
) -> None:
    """A DB-free bridge in front of a stateful backend is a common stack shape: the container that can
    reach the database is not "the app container". The contract DECLARES it (`CONTAINER_LEG_SERVICE`)
    and `--header` carries it, so the runner never guesses which container to `docker exec`."""
    proj = tmp_path / "proj"
    (proj / "scripts").mkdir(parents=True)
    stub = proj / "scripts" / "verify_prod_parity.py"
    src = TEMPLATE.read_text()
    assert 'CONTAINER_LEG_SERVICE: str = ""' in src  # seeded empty = the project's own app service
    stub.write_text(
        src.replace('CONTAINER_LEG_SERVICE: str = ""', 'CONTAINER_LEG_SERVICE: str = "trytond"')
    )
    hdr = json.loads(_run_as_documented(stub, "--header", cwd=proj).stdout)
    assert hdr["container_leg_service"] == "trytond", hdr
    stub.write_text(src)
    hdr = json.loads(_run_as_documented(stub, "--header", cwd=proj).stdout)
    assert hdr["container_leg_service"] == "", (
        hdr
    )  # empty → the runner uses the project's app service


def test_rows_for_takes_only_the_parsed_values() -> None:
    """`_rows_for(flags, values)` never read `flags` — a project's ruff (ARG001) refused the seeded stub
    outright (tryton-crm). The helper takes the values it uses."""
    import inspect

    vp = _vp()
    assert list(inspect.signature(vp._rows_for).parameters) == ["values"]


# ── W-82cff1ac item 1 (2026-10-11): where the stub finds the comparator under the runner's recipes ────────
# `/fabrik-deploy-verify`'s host leg copies the stub to /tmp and stages the comparator FLAT beside it
# (`scp -r libs/health_probe <vps>:/tmp/health_probe`); the VPS checkout never holds the gitignored module.
# Pre-fix the stub derived its root from `__file__` alone, so every host-leg comparison row read UNVERIFIABLE.


def _owner_only_modes(staged: Path) -> None:
    """Give a staged `health_probe/` the modes a 022 umask gives (dirs 755, files 644), never what the
    test process or the checkout happened to have. A merge leg runs under umask 002, where a copied or
    freshly written copy is group-writable, and the stub rightly refuses it as "writable by others", so
    a test meant to reach the stub's other branches was red only in merge legs (W-17fc722a)."""
    staged.chmod(0o755)
    for f in staged.rglob("*"):
        f.chmod(0o755 if f.is_dir() else 0o644)


def _flat_stage(dst_dir: Path) -> Path:
    """The recipe's staging layout: the stub beside a FLAT `health_probe/` copy of the comparator."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(REPO / "libs" / "health_probe", dst_dir / "health_probe")
    _owner_only_modes(dst_dir / "health_probe")
    stub = dst_dir / "verify_prod_parity.py"
    shutil.copy(TEMPLATE, stub)
    return stub


def _l0(r: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    rows = json.loads(r.stdout)
    row = next((x for x in rows if x["system"] == "l0_health_probe_vendored"), None)
    assert row is not None, (r.returncode, [x.get("system") for x in rows], r.stderr[-300:])
    return row


def test_parity_root_reads_the_recipes_flat_staging_copy_beside_the_script(tmp_path: Path) -> None:
    """B1 — the host-leg recipe AS WRITTEN: the stub in a bare dir beside a flat `health_probe/` copy,
    cwd an unrelated bare dir (the VPS clone, which holds no comparator) → the precondition row is a
    real comparison with `match: True`. RED pre-fix (the root resolved to the bare dir's parent)."""
    stub = _flat_stage(tmp_path / "tmp")
    cwd = tmp_path / "clone"
    cwd.mkdir()
    r = _run_as_documented(stub, "--json", cwd=cwd)
    l0 = _l0(r)
    assert l0["match"] is True, l0


def test_parity_root_prefers_a_vendored_clone_over_a_flat_sibling(tmp_path: Path) -> None:
    """B2 — a REGRESSION GUARD against a sibling-first implementation (GREEN pre-fix, which only ever
    read the clone): the stub in A/scripts with A vendoring the real module AND a poisoned flat
    `health_probe/` beside the stub → the clone wins and the row is `match: True`."""
    proj = tmp_path / "A"
    (proj / "scripts").mkdir(parents=True)
    shutil.copytree(REPO / "libs" / "health_probe", proj / "libs" / "health_probe")
    poisoned = proj / "scripts" / "health_probe"
    poisoned.mkdir()
    (poisoned / "__init__.py").write_text("raise ImportError('poisoned flat sibling')\n")
    (poisoned / "health_probe.py").write_text("raise ImportError('poisoned flat sibling')\n")
    stub = proj / "scripts" / "verify_prod_parity.py"
    shutil.copy(TEMPLATE, stub)
    r = _run_as_documented(stub, "--json", cwd=tmp_path)
    assert _l0(r)["match"] is True, _l0(r)


def test_parity_root_unvendored_detail_names_both_paths_looked_for(tmp_path: Path) -> None:
    """B3 — nothing qualifies: an un-vendored clone and no flat sibling → UNVERIFIABLE (exit 2, no
    traceback) with the pinned prefix and a detail naming BOTH module paths looked for, so the reader
    is sent to vendor or stage, never to 'run the fleet sync'. RED pre-fix on the detail."""
    proj = tmp_path / "proj"
    (proj / "scripts").mkdir(parents=True)
    stub = proj / "scripts" / "verify_prod_parity.py"
    shutil.copy(TEMPLATE, stub)
    r = _run_as_documented(stub, "--json", cwd=proj)
    assert r.returncode == 2, (r.returncode, r.stderr[-400:])
    assert "Traceback" not in r.stderr, r.stderr[-400:]
    detail = str(_l0(r)["detail"])
    assert detail.startswith("UNVERIFIABLE (health_probe not vendored"), detail
    assert str(proj / "libs" / "health_probe" / "health_probe.py") in detail, detail
    assert str(proj / "scripts" / "health_probe" / "health_probe.py") in detail, detail
    assert "run the fleet sync" not in detail, detail


def test_parity_root_ignores_a_pycache_only_leftover_in_the_clone(tmp_path: Path) -> None:
    """B4 — the marker is the MODULE, not the directory: a clone whose `libs/health_probe/` holds only
    `__pycache__` (a retired-dir leftover the sync's gitignore block keeps) does not qualify, so the
    good flat sibling wins → `match: True`. RED pre-fix (the clone was inserted and the import failed)."""
    stub = _flat_stage(tmp_path / "stage")
    (tmp_path / "libs" / "health_probe" / "__pycache__").mkdir(parents=True)
    r = _run_as_documented(stub, "--json", cwd=tmp_path)
    assert _l0(r)["match"] is True, _l0(r)


def test_hub_symlinked_stub_reads_unverifiable_naming_the_template_dir(tmp_path: Path) -> None:
    """B5 — the hub's own `scripts/verify_prod_parity.py` is a symlink into `templates/scaffold/`, which
    has no `libs/` and no flat sibling, so the hub's own run reads UNVERIFIABLE (today's outcome, kept)
    and the detail now SAYS which path it looked for — the shape stays stated, never silently flips."""
    r = _run_as_documented(REPO / "scripts" / "verify_prod_parity.py", "--json", cwd=tmp_path)
    l0 = _l0(r)
    assert l0["match"] is None, l0
    looked = REPO / "templates" / "scaffold" / "libs" / "health_probe" / "health_probe.py"
    assert str(looked) in str(l0["detail"]), l0


@pytest.mark.parametrize(
    ("body", "cause"),
    [
        ("def compare_not_here():\n    pass\n", "not the vendored comparator: no compare()"),
        ("import a_dependency_nobody_installed_xyz\n", "ModuleNotFoundError"),
    ],
)
def test_parity_root_found_but_unusable_module_names_the_cause(
    tmp_path: Path, body: str, cause: str
) -> None:
    """B6 — a module file that QUALIFIES by path but is not the vendored comparator (a same-named
    foreign package, or the real one with a dependency missing) is reported as FOUND BUT UNUSABLE
    with the cause, never as 'not vendored' and never as a traceback or a 'row raised' detail."""
    stage = tmp_path / "stage"
    (stage / "health_probe").mkdir(parents=True)
    (stage / "health_probe" / "__init__.py").write_text("")
    (stage / "health_probe" / "health_probe.py").write_text(body)
    _owner_only_modes(stage / "health_probe")
    stub = stage / "verify_prod_parity.py"
    shutil.copy(TEMPLATE, stub)
    r = _run_as_documented(stub, "--json", cwd=tmp_path)
    assert r.returncode == 2 and "Traceback" not in r.stderr, (r.returncode, r.stderr[-400:])
    detail = str(_l0(r)["detail"])
    assert detail.startswith("UNVERIFIABLE (health_probe found at "), detail
    assert cause in detail and "not vendored" not in detail and "row raised" not in detail, detail


@pytest.mark.parametrize("mode", [0o777, 0o775], ids=["other-writable", "group-writable"])
def test_parity_root_refuses_a_staged_copy_writable_by_others(tmp_path: Path, mode: int) -> None:
    """B7 — a shared /tmp lets another local user plant `health_probe/` beside the script: a staged
    directory writable by group or others is REFUSED, the row is UNVERIFIABLE and the detail says why.
    The group-only case is its own row: a check narrowed to the other-write bit passes 0777."""
    stub = _flat_stage(tmp_path / "stage")
    (tmp_path / "stage" / "health_probe").chmod(mode)
    r = _run_as_documented(stub, "--json", cwd=tmp_path)
    l0 = _l0(r)
    assert l0["match"] is None, l0
    assert "writable by others" in str(l0["detail"]), l0


@pytest.mark.parametrize("mode", [0o666, 0o664], ids=["other-writable", "group-writable"])
def test_parity_root_refuses_a_staged_module_file_writable_by_others(
    tmp_path: Path, mode: int
) -> None:
    """B8 — the check covers the module FILE, not only its directory: a `health_probe.py` writable by
    group or others inside an owned 0755 directory is REFUSED the same way (round 2 of the scoped review
    reproduced the gap: the directory passed both checks and a 0666 file was loaded and executed)."""
    stub = _flat_stage(tmp_path / "stage")
    (tmp_path / "stage" / "health_probe").chmod(0o755)
    (tmp_path / "stage" / "health_probe" / "health_probe.py").chmod(mode)
    r = _run_as_documented(stub, "--json", cwd=tmp_path)
    l0 = _l0(r)
    assert l0["match"] is None, l0
    assert "writable by others" in str(l0["detail"]), l0
