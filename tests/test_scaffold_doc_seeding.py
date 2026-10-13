"""Behavior Contract for Phase C — type-aware scaffold doc seeding (driven by the registry SSOT).

Two layers:
  1. Unit tests of `_type_seeds_doc` — the pure gating decision per (type, doc).
  2. Integration tests through `_scaffold_shared` — the seeding loop actually skips/keeps the
     right docs on disk.

Grounded deviation from the plan's criterion #2 (documented): `data-contract.md` keeps its
deliberate all-but-docusaurus behavior rather than a `needs_database` gate — `use_database`
defaults False even for saas-skeleton/static-site (which legitimately carry the contract), so
gating on it would wrongly strip it from them and break `test_static_site_seeds_contract`.
Type-awareness IS applied to the deployed + saas buckets (the primary defect-4 win).
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from fabrik import scaffold

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_registry():
    spec = importlib.util.spec_from_file_location(
        "_doc_registry", REPO_ROOT / "scripts" / "enforcement" / "_doc_registry.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_doc_registry"] = mod
    spec.loader.exec_module(mod)
    return mod


reg = _load_registry()


# ---------------------------------------------------------------------------------------
# Layer 1 — unit tests of the pure gating decision
# ---------------------------------------------------------------------------------------
def test_headless_python_api_skips_product_docs_keeps_deployed_and_universal():
    # BUSINESS_MODEL is product-facing and a headless API has no product story to tell.
    assert not scaffold._type_seeds_doc(reg, "python-api", "docs/BUSINESS_MODEL.md"), (
        "python-api should skip docs/BUSINESS_MODEL.md"
    )
    # ⚠️ STRATEGIC_BACKLOG moved from product-only to UNIVERSAL in 245cb5e7 (2026-08-27,
    # operator rule: every type seeds it, because every project accrues deferred work). This
    # assertion still demanded the old contract and had been RED for two days — unnoticed
    # because the hub's `final_gate` does not run pytest (`_ci_runs_pytest` is false here, and
    # as of 7051a25a there are no workflow files at all), so nothing on this repo executes its
    # own suite unless a human does. Found by a background run started for an unrelated reason.
    assert scaffold._type_seeds_doc(reg, "python-api", "docs/STRATEGIC_BACKLOG.md"), (
        "STRATEGIC_BACKLOG is universal since 245cb5e7 — every type seeds it"
    )
    for dest in (
        "docs/SERVICES.md",
        "docs/OPERATIONS.md",
        "docs/RESILIENCE.md",
        "README.md",
        "docs/QUICKSTART.md",
    ):
        assert scaffold._type_seeds_doc(reg, "python-api", dest), f"python-api should seed {dest}"


def test_saas_seeds_product_docs():
    for dest in ("docs/BUSINESS_MODEL.md", "docs/STRATEGIC_BACKLOG.md", "docs/SERVICES.md"):
        assert scaffold._type_seeds_doc(reg, "saas-skeleton", dest)


def test_client_app_skips_deployed_docs():
    # chrome-extension / mobile-app / desktop-app ship no backend service
    for t in ("chrome-extension", "mobile-app", "desktop-app"):
        for dest in (
            "docs/SERVICES.md",
            "docs/OPERATIONS.md",
            "docs/RESILIENCE.md",
            "docs/BUSINESS_MODEL.md",
        ):
            assert not scaffold._type_seeds_doc(reg, t, dest), f"{t} should skip {dest}"
        # but universal docs still seed
        assert scaffold._type_seeds_doc(reg, t, "README.md")


def test_data_contract_kept_for_all_types_leak_guard_is_separate():
    # _type_seeds_doc returns True for data on every type (the docusaurus leak guard is applied
    # separately by the caller via _NO_DATA_CONTRACT_TYPES)
    for t in ("python-api", "saas-skeleton", "chrome-extension", "docusaurus"):
        assert scaffold._type_seeds_doc(reg, t, "docs/data-contract.md")


# ---------------------------------------------------------------------------------------
# Layer 2 — integration through _scaffold_shared
# ---------------------------------------------------------------------------------------
_DOC_TEMPLATES = [
    "PROJECT_INDEX_TEMPLATE.md",
    "PROJECT_README_TEMPLATE.md",
    "CHANGELOG_TEMPLATE.md",
    "DOCS_INDEX_TEMPLATE.md",
    "QUICKSTART_TEMPLATE.md",
    "CONFIGURATION_TEMPLATE.md",
    "TROUBLESHOOTING_TEMPLATE.md",
    "BUSINESS_MODEL_TEMPLATE.md",
    "STRATEGIC_BACKLOG_TEMPLATE.md",
    "SERVICES_TEMPLATE.md",
    "RESILIENCE_TEMPLATE.md",
    "OPERATIONS_TEMPLATE.md",
    "FEATURES_TEMPLATE.md",
    "data-contract-template.md",
]


@pytest.fixture()
def mock_root():
    """Minimal fabrik root sufficient for _scaffold_shared to run past its required-asset
    checks (mirrors the proven harness in test_scaffold_logging.py)."""
    d = Path(tempfile.mkdtemp())
    scaffold_tpl = d / "templates" / "scaffold" / "docs"
    scaffold_tpl.mkdir(parents=True)
    for tpl in _DOC_TEMPLATES:
        (scaffold_tpl / tpl).write_text("# [Project Name]\n\nYYYY-MM-DD\n[Brief description]\n")
    # required fabrik assets _scaffold_shared copies (else it raises FileNotFoundError)
    (d / ".windsurfrules").write_text("# rules\n")
    (d / ".windsurf" / "rules").mkdir(parents=True)
    (d / ".windsurf" / "rules" / "10-python.md").write_text("# rules\n")
    (d / ".windsurf" / "workflows").mkdir(parents=True)
    (d / ".windsurf" / "workflows" / "test.md").write_text("# wf\n")
    (d / "AGENTS.md").write_text("# AGENTS\n")
    (d / "AGENTS-compact.md").write_text("# AGENTS-compact\n")
    (d / "opencode.json").write_text("{}\n")
    (d / ".pre-commit-config.yaml").write_text("repos: []\n")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _seed(mock_root: Path, project_type: str) -> Path:
    project_dir = mock_root / f"proj-{project_type}"
    project_dir.mkdir()
    with (
        patch.object(scaffold, "FABRIK_ROOT", mock_root),
        patch.object(scaffold, "TEMPLATE_DIR", mock_root / "templates" / "scaffold"),
        patch.object(scaffold, "FABRIK_AGENTS_MD", mock_root / "AGENTS.md"),
        patch("subprocess.run"),
    ):
        scaffold._scaffold_shared(project_dir, "svc", "Test", "2026-07-11", 8099, project_type)
    return project_dir


def test_python_api_seeding_is_type_aware(mock_root: Path):
    p = _seed(mock_root, "python-api")
    # universal + deployed docs present
    assert (p / "README.md").exists()
    assert (p / "docs" / "SERVICES.md").exists()
    assert (p / "docs" / "data-contract.md").exists()  # preserved (grounded deviation)
    # product (saas) docs NOT seeded for a headless api
    assert not (p / "docs" / "BUSINESS_MODEL.md").exists()
    # STRATEGIC_BACKLOG is UNIVERSAL since 245cb5e7 — the integration-layer twin of the same
    # stale assertion fixed above. Both sites demanded the pre-2026-08-27 contract; the registry
    # change updated neither, and nothing ran them.
    assert (p / "docs" / "STRATEGIC_BACKLOG.md").exists()


def test_saas_seeding_gets_product_docs(mock_root: Path):
    p = _seed(mock_root, "saas-skeleton")
    assert (p / "docs" / "BUSINESS_MODEL.md").exists()
    assert (p / "docs" / "STRATEGIC_BACKLOG.md").exists()
    assert (p / "docs" / "SERVICES.md").exists()
    assert (p / "docs" / "data-contract.md").exists()


def test_docusaurus_skips_data_contract_and_deployed_docs(mock_root: Path):
    p = _seed(mock_root, "docusaurus")
    assert not (p / "docs" / "data-contract.md").exists()  # leak guard honored
    assert not (p / "docs" / "SERVICES.md").exists()  # not a deployed backend
    assert (p / "README.md").exists()  # universal still seeded


# --- crash-safety: a registry that raises on use degrades to full seeding, never breaks
def test_should_seed_doc_never_raises_on_malformed_registry():
    class _Bad:
        @property
        def PROJECT_DOCS(self):  # noqa: N802
            raise RuntimeError("schema drift")

    # any registry-use error → seed (True), never propagate
    assert scaffold._should_seed_doc(_Bad(), "python-api", "docs/BUSINESS_MODEL.md") is True
    # None registry → seed everything (prior full-seed behavior)
    assert scaffold._should_seed_doc(None, "chrome-extension", "docs/SERVICES.md") is True


# --- (d) registry-unavailable fallback: seeding degrades to the full untyped set (no gating)
def test_registry_unavailable_falls_back_to_full_seeding(mock_root: Path):
    with patch.object(scaffold, "_load_doc_registry", return_value=None):
        p = _seed(mock_root, "python-api")
    # with the registry off, the pre-change behavior returns: product docs ARE seeded again
    assert (p / "docs" / "BUSINESS_MODEL.md").exists()
    assert (p / "README.md").exists()


# --- the generalized leak guard covers ANY data-bucket doc for docusaurus, not just by-name.
#     Proven with a SYNTHETIC second data doc (not data-contract.md) so the by-name guard can't
#     be what catches it — only the bucket-based path can.
def test_data_leak_guard_generalizes_to_bucket():
    from types import SimpleNamespace

    reg = _load_registry()
    fake_row = SimpleNamespace(
        name="docs/metrics-contract.md",
        applies_to=frozenset({"data"}),
        template="x",
        trigger="",
        fills="agent",
    )
    fake_reg = SimpleNamespace(PROJECT_DOCS=(fake_row,), TYPE_BUCKETS=reg.TYPE_BUCKETS)
    assert scaffold._is_data_doc(fake_reg, "docs/metrics-contract.md")
    # docusaurus skips a NON-data-contract data doc purely via the bucket guard
    assert scaffold._should_seed_doc(fake_reg, "docusaurus", "docs/metrics-contract.md") is False
    # a deployed type keeps it
    assert scaffold._should_seed_doc(fake_reg, "python-api", "docs/metrics-contract.md") is True
    # and the real registry's data-contract is guarded for docusaurus too
    assert scaffold._should_seed_doc(reg, "docusaurus", "docs/data-contract.md") is False


def test_deployment_doc_is_in_the_template_map_and_gated_to_deployed():
    # Template-wave regression (2026-08-07): the registry declared docs/DEPLOYMENT.md
    # (deployed bucket) but SHARED_TEMPLATE_MAP never carried the template — seeding
    # iterates the MAP, so the doc was silently never seeded for any type.
    assert scaffold.SHARED_TEMPLATE_MAP.get("docs/DEPLOYMENT_TEMPLATE.md") == "docs/DEPLOYMENT.md"
    assert scaffold._type_seeds_doc(reg, "python-api", "docs/DEPLOYMENT.md")
    assert not scaffold._type_seeds_doc(reg, "chrome-extension", "docs/DEPLOYMENT.md")


def test_docusaurus_config_excludes_internal_governance_docs(tmp_path):
    # fleet+infra finding 01M19JJNWK: Docusaurus publishes the whole docs/ tree, so internal Fabrik
    # docs in docs/ (seeded governance: DECISIONS/LESSONS_LEARNT/STRATEGIC_BACKLOG; pipeline
    # contracts: flows/ui-design/design-system) would land on a world-readable site. They must stay
    # PRESENT (governance requires docs/DECISIONS.md in every repo) but be content-docs EXCLUDED.
    proj = tmp_path / "proj-docs"
    proj.mkdir()
    scaffold._scaffold_docusaurus(proj, "mysite", "A docs site")
    cfg = (proj / "docusaurus.config.js").read_text()
    # the entries must live INSIDE the docs-preset exclude ARRAY, not merely somewhere in the file
    start = cfg.index("exclude: [")
    block = cfg[start : cfg.index("]", start)]
    for d in scaffold._DOCUSAURUS_UNPUBLISHED_DOCS:
        assert f"'**/{d}'" in block, f"{d} must be in the docusaurus content-docs exclude array"
    # setting `exclude` replaces the plugin default, so the defaults must be re-listed in the array
    assert "'**/_*.{js,jsx,ts,tsx,md,mdx}'" in block, (
        "docusaurus default excludes must be preserved"
    )
    # PRESENT half of present-but-unpublished: the seeded governance docs still SEED to docusaurus
    for dest in ("docs/DECISIONS.md", "docs/LESSONS_LEARNT.md", "docs/STRATEGIC_BACKLOG.md"):
        assert scaffold._type_seeds_doc(reg, "docusaurus", dest), (
            f"{dest} must still SEED to docusaurus"
        )


def test_decisions_doc_is_in_the_template_map_and_universal():
    # Same class as the 2026-08-07 DEPLOYMENT regression (decision-ledger plan-1 B6):
    # the registry declares docs/DECISIONS.md (universal governance surface) but the
    # template landed inert until SHARED_TEMPLATE_MAP carried it — seeding iterates the
    # MAP, so an unmapped registry doc is silently never seeded for any type.
    assert scaffold.SHARED_TEMPLATE_MAP.get("docs/DECISIONS_TEMPLATE.md") == "docs/DECISIONS.md"
    # universal: EVERY scaffold type seeds it — a headless api, a saas, and a client app alike
    for t in ("python-api", "saas-skeleton", "chrome-extension", "docusaurus"):
        assert scaffold._type_seeds_doc(reg, t, "docs/DECISIONS.md"), (
            f"{t} should seed docs/DECISIONS.md"
        )


# ---------------------------------------------------------------------------------------
# T06 — a new repo is born with the PLANS ownership markers (the T02a→T06 seam):
# docs_updater.py --adopt seeds `## Ownership (auto-generated)` + the marker pair into an
# EXISTING PLANS.md that lacks them; the scaffolder now ships that same block already in
# place, below the hand table, so a fresh repo needs no --adopt run to gain the surface.
# ---------------------------------------------------------------------------------------

# The exact seed `docs_updater.run_adopt()` writes when PLANS.md exists but has no markers
# (scripts/docs_updater.py, grep "Ownership (auto-generated)") — reproduced byte-for-byte.
_OWNERSHIP_SEED_BLOCK = (
    "\n## Ownership (auto-generated)\n\n"
    "<!-- AUTO-GENERATED:PLANS:START -->\n<!-- AUTO-GENERATED:PLANS:END -->\n"
)


def test_fresh_scaffold_plans_md_already_carries_the_ownership_markers(mock_root: Path):
    """RED before src/fabrik/scaffold.py's PLANS.md literal grows the block: a fresh
    `_scaffold_shared` must already produce docs/development/PLANS.md with the markers
    below the hand table, byte-equal to the docs_updater --adopt seed constant — so a new
    repo never needs a --adopt run just to gain the surface."""
    p = _seed(mock_root, "python-api")
    plans_md = p / "docs" / "development" / "PLANS.md"
    assert plans_md.exists()
    content = plans_md.read_text(encoding="utf-8")
    assert content.endswith(_OWNERSHIP_SEED_BLOCK), (
        f"docs/development/PLANS.md must end with the byte-for-byte ownership seed block; "
        f"got tail: {content[-200:]!r}"
    )
    # the hand table survives above the markers (never replaced, per the ticket's DO-NOT)
    assert "| (none) | - | - |" in content
    assert content.index("| (none) | - | - |") < content.index(
        "<!-- AUTO-GENERATED:PLANS:START -->"
    )


def test_fresh_scaffold_plans_md_is_regenerable_by_docs_updater_sync(mock_root: Path, monkeypatch):
    """RED before the scaffold literal gains the markers: `docs_updater.sync_plans_index()`
    must regenerate the block IN PLACE against a fresh scaffold's PLANS.md, and — since the
    scratch repo carries no docs/DECISIONS.md yet — the block's second header line must be
    the undeclared-merge-owner line (proves the block is real, not just matching text)."""
    p = _seed(mock_root, "python-api")

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import docs_updater as du

    monkeypatch.setattr(du, "PROJECT_ROOT", p)
    monkeypatch.setattr(du, "PLANS_DIR", p / "docs" / "development" / "plans")
    monkeypatch.setattr(du, "PLANS_INDEX", p / "docs" / "development" / "PLANS.md")

    changed, _msg = du.sync_plans_index()
    assert changed, (
        "a fresh scaffold's PLANS.md has no rows yet — --sync must still write the table"
    )

    content = (p / "docs" / "development" / "PLANS.md").read_text(encoding="utf-8")
    body = du.extract_block_body(content, du.PLANS_BLOCK_RE)
    assert body is not None, "sync_plans_index must find the markers it just regenerated"
    lines = body.splitlines()
    assert lines[1].startswith("<!-- Merge owner: UNDECLARED"), (
        f"second header line must be the undeclared-merge-owner line; got: {lines[1]!r}"
    )


# ---------------------------------------------------------------------------------------
# T06 — docs the ticket owes: the operating-model doc and the project-facing governance
# template name `--adopt`, not the retired "tail sweep" prose (D-154/D-155).
# ---------------------------------------------------------------------------------------
_OPERATING_MODEL_DOC = REPO_ROOT / "docs" / "reference" / "multi-agent-operating-model.md"
_GOVERNANCE_TEMPLATE = REPO_ROOT / "templates" / "governance" / "CLAUDE.md"


def test_operating_model_doc_names_adopt_not_tail_sweep():
    text = _OPERATING_MODEL_DOC.read_text(encoding="utf-8")
    assert "tail sweep" not in text, (
        "the retired 'agent-1's tail sweep' prose must be replaced by the --adopt step (D-154/D-155)"
    )
    assert "docs_updater.py --adopt" in text


def test_operating_model_doc_states_each_advisorys_suppression_exactly():
    """Acceptance-review fix (round 1): the doc must not overclaim a worktree guard the
    `--check` advisory doesn't have. `docs_updater.validate_ownership_advisory()` guards
    only the session count (< 2 → []) and the hub sentinel — it has NO `/.claude/worktrees/`
    check, so ≥2 sessions sharing one worktree checkout WOULD fire it. Only the SessionStart
    line (`session_orient.py::_sessions_line`, which literally tests `"/.claude/worktrees/"
    in cwd`) is worktree-guarded. So: both advisories share the single-session + hub
    suppression; only the SessionStart line ALSO never fires inside a worktree."""
    text = _OPERATING_MODEL_DOC.read_text(encoding="utf-8")
    assert "never fire in a single-session repo or in the hub" in text, (
        "the shared suppression (session count + hub) must be stated for BOTH advisories"
    )
    assert "SessionStart line additionally never fires inside a worktree" in text, (
        "the worktree guard is SessionStart-only (session_orient.py's own cwd check) — "
        "the --check advisory carries no such guard and must not be credited with one"
    )
    # the retired overclaim — one sentence crediting BOTH advisories with a worktree guard
    # neither the --check advisory nor the doc's own code citations actually have.
    assert (
        "neither ever fires in a single-session repo, in the hub, or inside a worktree" not in text
    )


def test_governance_template_names_adopt():
    text = _GOVERNANCE_TEMPLATE.read_text(encoding="utf-8")
    # drift guard: the retired "tail sweep" phrasing never existed in this template (unlike
    # the operating-model doc, which DID carry it) — kept as a tripwire against it creeping
    # in here as a copy-paste of the old operating-model prose, not as evidence of a removal.
    assert "tail sweep" not in text
    assert "docs_updater.py --adopt" in text


def test_no_template_runs_psql_on_a_driver_dsn():
    """Every seeded libpq call on DATABASE_URL / DATABASE_URL_OWNER reaches the variable only as
    `u=$(pgurl "$VAR") && <cmd> ... "$u"`: the rule pack mandates postgresql+asyncpg://, which libpq
    reads as a database NAME, and an asyncpg ?ssl= that libpq refuses (01M464NPPB); any other shape
    (psql "$(pgurl ...)", `;` instead of `&&`) hands psql an empty string when pgurl or the variable
    is missing, and psql then connects to the local default database. Scans every template file and
    scaffold.py, with backslash-continued lines joined."""
    import re

    call = re.compile(r"\b(psql|pg_dump|pg_isready|pg_restore)\b")
    var = re.compile(r"\$\{?DATABASE_URL(_OWNER)?\b")
    closed = re.compile(
        r'\bu=\$\(pgurl "\$\{?DATABASE_URL(_OWNER)?\}?"\) && (psql|pg_dump|pg_isready|pg_restore)\b[^`|]*"\$u"'
    )
    scaffold_py = REPO_ROOT / "src" / "fabrik" / "scaffold.py"
    subjects = [p for p in sorted((REPO_ROOT / "templates").rglob("*")) if p.is_file()]
    subjects.append(scaffold_py)
    hits = []
    for p in subjects:
        raw = p.read_text(encoding="utf-8", errors="replace").splitlines()
        lines, starts, buf, start = [], [], "", 0
        for n, piece in enumerate(raw):
            if not buf:
                start = n
            if piece.rstrip().endswith("\\"):
                buf += piece.rstrip()[:-1] + " "
                continue
            lines.append(buf + piece)
            starts.append(start)
            buf = ""
        for i, line in enumerate(lines):
            if not (call.search(line) and var.search(closed.sub("", line))):
                continue
            if p == scaffold_py:
                prev = lines[i - 1].rstrip() if i else ""
                if prev.endswith(
                    ".replace("
                ):  # the search half of a .replace() that REMOVES a call
                    continue
                # the labelled plain-DSN fallback under a pgurl headline in a db/schema.sql header
                if (
                    line.lstrip(" '\"").startswith("--")
                    and "with a plain postgresql:// DSN" in prev
                ):
                    continue
            hits.append(f"{p.relative_to(REPO_ROOT)}:{starts[i] + 1}: {line.strip()}")
    assert hits == [], hits


def test_driver_dsn_grader_catches_the_fail_open_shapes(tmp_path, monkeypatch):
    """The grader above flags each shape that fails open or bypasses pgurl, and passes the
    fail-closed one; run against a scratch template tree."""
    shapes = {
        'psql "$DATABASE_URL"': True,
        'psql "$(pgurl "$DATABASE_URL")" -c "SELECT 1"': True,
        'u=$(pgurl "$DATABASE_URL"); psql "$u"': True,
        'psql "$DATABASE_URL"  # pgurl it first': True,
        'psql "$(notpgurl "$DATABASE_URL")"': True,
        'psql -1 -v ON_ERROR_STOP=1 \\\n  "$DATABASE_URL_OWNER" -f db/schema.sql': True,
        'u=$(pgurl "$DATABASE_URL") && psql "$u" -c "SELECT 1"': False,
        'u=$(pgurl "$DATABASE_URL_OWNER") && psql -1 -v ON_ERROR_STOP=1 "$u" -f db/schema.sql': False,
    }
    for text, flagged in shapes.items():
        root = tmp_path / str(abs(hash(text)))
        (root / "templates").mkdir(parents=True)
        (root / "src" / "fabrik").mkdir(parents=True)
        (root / "src" / "fabrik" / "scaffold.py").write_text("")
        (root / "templates" / "T.md").write_text(text.replace("\\n", "\n") + "\n")
        monkeypatch.setitem(globals(), "REPO_ROOT", root)
        try:
            test_no_template_runs_psql_on_a_driver_dsn()
            got = False
        except AssertionError:
            got = True
        assert got is flagged, (text, got)


def test_pgurl_rewrites_a_driver_dsn_for_libpq(tmp_path):
    """Both seeded pgurl copies, run by POSIX sh (dash), yield a libpq URI and refuse an empty DSN."""
    import subprocess

    defs = {
        name: next(
            ln
            for ln in (REPO_ROOT / "templates/scaffold/docs" / name)
            .read_text(encoding="utf-8")
            .splitlines()
            if ln.startswith("pgurl()")
        )
        for name in ("TROUBLESHOOTING_TEMPLATE.md", "CONFIGURATION_TEMPLATE.md")
    }
    assert len(set(defs.values())) == 1, "the two pgurl copies drifted"
    definition = next(iter(defs.values()))
    cases = {
        "postgresql+asyncpg://shop@10.99.0.1:5432/shop?ssl=require": (
            "postgresql://shop@10.99.0.1:5432/shop?sslmode=require"
        ),
        "postgresql+psycopg://u@h/d?application_name=x&ssl=prefer": (
            "postgresql://u@h/d?application_name=x&sslmode=prefer"
        ),
        # sslcert/sslkey/sslrootcert are not ssl= — only the bare key is renamed
        "postgresql://u@h/d?sslcert=c&sslkey=k&ssl=require": "postgresql://u@h/d?sslcert=c&sslkey=k&sslmode=require",
        "postgres+asyncpg://u@h/d": "postgres://u@h/d",
        "postgres://u@h/d?ssl=require": "postgres://u@h/d?sslmode=require",  # the plain postgres scheme
        # a percent-encoded VALUE and a glob stay as written (set -f: no pathname expansion of the query)
        "postgresql://u@h/d?application_name=my%20app&sslmode=require": (
            "postgresql://u@h/d?application_name=my%20app&sslmode=require"
        ),
        "postgresql://u@h/d?application_name=a*b&ssl=require": "postgresql://u@h/d?application_name=a*b&sslmode=require",
        # an ENCODED `?` in the password is fine — only the raw character splits the DSN (review pgurl-O8)
        "postgresql://u:p%3Fx@h/d?ssl=require": "postgresql://u:p%3Fx@h/d?sslmode=require",
        # no userinfo, an `@` in a query value: libpq reads no credentials here and neither does pgurl
        "postgresql://h/d?application_name=a@b&ssl=require": "postgresql://h/d?application_name=a@b&sslmode=require",
        "postgresql+asyncpg:///db?host=/var/run/postgresql": "postgresql:///db?host=/var/run/postgresql",
        "postgresql://u:a&ssl=x@h/my&ssl=db": "postgresql://u:a&ssl=x@h/my&ssl=db",
        "postgresql://u:p+asyncpg@h/d": "postgresql://u:p+asyncpg@h/d",
    }
    for dsn, want in cases.items():
        out = subprocess.run(
            ["sh", "-c", definition + '\npgurl "$1"', "sh", dsn],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert out == want, (dsn, out)
    empty = subprocess.run(
        ["sh", "-c", definition + '\nu=$(pgurl "") && echo RAN'], capture_output=True, text=True
    )
    assert empty.returncode != 0 and "RAN" not in empty.stdout
    # A DSN carrying whitespace, a quote or a backslash — a hand-edited or still-quoted .env line — is refused
    # before psql (review 2026-10-13 S3/O4/O6), each alternative of the case pattern exercised alone; a
    # legitimate DSN with URL-encoding, a `#` in the password or a query string is not.
    for bad in (
        "postgresql://o:p@h/d # note",
        'postgresql://o:p@h/d"',
        "postgresql://o:p'x@h/d",  # the quote AFTER the scheme: the quote arm, never the scheme arm
        "postgresql://o:p\\x@h/d",
        "postgresql://o:p@h/d\r",
    ):
        r = subprocess.run(
            ["sh", "-c", definition + '\nu=$(pgurl "$1") && echo RAN', "sh", bad],
            capture_output=True,
            text=True,
        )
        assert r.returncode != 0 and "RAN" not in r.stdout and "pgurl:" in r.stderr, (
            bad,
            r.stdout,
            r.stderr,
        )
    for good in ("postgresql://o:p%40w%23x@h/d?sslmode=require", "postgresql://o:p#x@h/d"):
        r = subprocess.run(
            ["sh", "-c", definition + '\npgurl "$1"', "sh", good],
            capture_output=True,
            text=True,
            check=True,
        )
        assert r.stdout.strip() == good, (good, r.stdout)
    # fabrik-lib 01M4TP1W (2026-10-13), both executed against psql 16: (a) libpq keeps the LAST of duplicate
    # sslmode keys silently, so `?sslmode=require&ssl=disable` renamed blindly connects WITHOUT TLS — more than
    # one ssl/sslmode key (requiressl since 01M4VB91YA) is refused before the rename; (b) the recipe has no `--` before "$u", so a value
    # `-o/etc/<file>` reaches root's psql as an option (psql truncates the file before connecting) — only a
    # postgres://, postgresql:// or +driver form is accepted. Fail-closed hardening: whoever writes .env.owner
    # is already root, but a refused line beats a silent downgrade or a truncated file.
    for bad, needle in (
        ("postgresql://u@h/d?sslmode=require&ssl=disable", "more than one ssl"),
        ("postgresql://u@h/d?ssl=require&sslmode=disable", "more than one ssl"),
        ("postgresql://u@h/d?ssl=prefer&ssl=disable", "more than one ssl"),
        ("postgresql://u@h/d?sslmode=require&x=1&sslmode=disable", "more than one ssl"),
        ("-o/etc/passwd", "not a postgres DSN"),
        ("mysql://u@h/d", "not a postgres DSN"),
        ("u@h/d?sslmode=require", "not a postgres DSN"),
        ("POSTGRESQL://u@h/d", "not a postgres DSN"),
        # a +driver the rewrite cannot strip is refused, never printed unchanged (review pgurl-S1/O6):
        # upper-case, a second `+`, a `.`/`-`, an empty driver
        ("postgresql+AsyncPG://u@h/d?ssl=require", "not a postgres DSN"),
        ("postgresql+asyncpg+x://u@h/d", "not a postgres DSN"),
        ("postgresql+psycopg.3://u@h/d", "not a postgres DSN"),
        ("postgres+://u@h/d", "not a postgres DSN"),
        # libpq percent-decodes query KEYS: `%73slmode` IS sslmode, so the duplicate check alone is blind (pgurl-O1)
        ("postgresql://u@h/d?sslmode=require&%73slmode=disable", "percent-encoded query KEY"),
        ("postgresql://u@h/d?ssl%6dode=disable&sslmode=require", "percent-encoded query KEY"),
        # a raw `?` in the password: libpq scans for `@` first, so ITS query starts later than pgurl's split —
        # the hidden second sslmode would pass both checks (review pgurl-O8, executed: rc 0 before this arm)
        (
            "postgresql://u:p?x=y@h/d?%73slmode=disable&sslmode=require",
            "a ? in the user:password part",
        ),
        ("postgresql://u:p?@h/d?sslmode=require", "a ? in the user:password part"),
        # a still-quoted or space-wrapped line is told the REAL cause — the quote arm runs before the scheme arm (pgurl-O5)
        ("'postgresql://o:p@h/d'", "whitespace, a quote or a backslash"),
        (" postgresql://o:p@h/d", "whitespace, a quote or a backslash"),
        # fabrik-lib 01M4VB91YA (2026-10-14), executed against libpq 17 (psycopg2 parse_dsn): `requiressl` is a
        # deprecated alias that REWRITES sslmode — `?sslmode=verify-full&requiressl=0` resolves to `prefer`, so the
        # pairing is counted like a second sslmode; a lone `requiressl=1` (= require) is not a downgrade and passes.
        ("postgresql://u@h/d?sslmode=require&requiressl=0", "more than one ssl"),
        ("postgresql://u@h/d?requiressl=0&sslmode=verify-full", "more than one ssl"),
        ("postgresql://u@h/d?requiressl=1&ssl=require", "more than one ssl"),
    ):
        r = subprocess.run(
            ["sh", "-c", definition + '\nu=$(pgurl "$1") && echo RAN', "sh", bad],
            capture_output=True,
            text=True,
        )
        assert r.returncode != 0 and "RAN" not in r.stdout and needle in r.stderr, (
            bad,
            r.stdout,
            r.stderr,
        )
    # The key count word-splits the query with the CALLER's IFS (review pg2-O1, 2026-10-14): a root shell that
    # ran `IFS=:` earlier let `?sslmode=require&ssl=disable` through as one word, rc 0 — the subshell pins
    # IFS to a space for its own loop. Executed red on the unpinned line (RAN under IFS=: and under IFS='').
    for ifs_prefix in ("IFS=:\n", "IFS=\n"):
        r = subprocess.run(
            [
                "sh",
                "-c",
                ifs_prefix + definition + '\nu=$(pgurl "$1") && echo RAN',
                "sh",
                "postgresql://u@h/d?sslmode=require&ssl=disable",
            ],
            capture_output=True,
            text=True,
        )
        assert r.returncode != 0 and "RAN" not in r.stdout and "more than one ssl" in r.stderr, (
            ifs_prefix,
            r.stdout,
            r.stderr,
        )
    # `set -f` pinned (fabrik-lib 01M4VB91YA finding b): the query is word-split unquoted, so without `set -f` a
    # key glob that matches a FILE in the cwd is replaced by the filename before the %-key arm reads it — a file
    # named `x73slmode=disable` turns `[%x]73slmode=disable` into a plain key and the %-arm never fires. libpq
    # itself rejects that DSN (`invalid percent-encoded token`), so `set -f` is defence in depth, pinned here:
    # executed red with `set -f; ` removed from the line (the glob expands, rc 0, RAN).
    globdir = tmp_path / "globcwd"
    globdir.mkdir()
    (globdir / "x73slmode=disable").write_text("")
    r = subprocess.run(
        [
            "sh",
            "-c",
            definition + '\nu=$(pgurl "$1") && echo RAN',
            "sh",
            "postgresql://u@h/d?sslmode=require&[%x]73slmode=disable",
        ],
        capture_output=True,
        text=True,
        cwd=globdir,
    )
    assert (
        r.returncode != 0 and "RAN" not in r.stdout and "percent-encoded query KEY" in r.stderr
    ), (
        r.stdout,
        r.stderr,
    )


def test_readme_template_carries_every_section_the_readme_gate_requires():
    """infra 01M4RQ3FH6 (whatsapp-agent 01M4RNRXQJ, 2026-10-12): the template's headings were Overview, Tech
    Stack, Requirements, Documentation while scripts/enforcement/check_readme_md.py requires `## Quick Start`
    too — a README converged toward the template failed the gate. Two hand-kept lists of one contract drift
    silently; this grader reads the gate's `required_sections` literal and asserts every `## ` entry is a
    heading of the template, so the next drift reds here before it reds a project."""
    import ast

    gate_src = (REPO_ROOT / "scripts" / "enforcement" / "check_readme_md.py").read_text(
        encoding="utf-8"
    )
    required: list[str] = []
    for node in ast.walk(ast.parse(gate_src)):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "required_sections" for t in node.targets
        ):
            required = [ast.literal_eval(elt) for elt in node.value.elts]  # type: ignore[attr-defined]
    assert required, (
        "check_readme_md.py no longer defines required_sections — update this grader with the gate"
    )
    template = (
        REPO_ROOT / "templates" / "scaffold" / "docs" / "PROJECT_README_TEMPLATE.md"
    ).read_text(encoding="utf-8")
    headings = {line.strip() for line in template.splitlines() if line.startswith("## ")}
    missing = [s for s in required if s.startswith("## ") and s not in headings]
    assert missing == [], f"template lacks the gate's required section(s): {missing}"
    assert "## Quick Start" in headings


# ONE grammar: the gate's own check is the reader, so the template and the gate cannot drift
# (design critique 2026-10-13 — a private copy here and a stricter one in the check disagreed).
sys.path.insert(0, str(REPO_ROOT / "scripts" / "enforcement"))
import check_data_contract_legend as _legend  # noqa: E402

_BACKING_TOKENS = _legend.LEGEND_TOKENS


def _legend_tokens(text: str) -> list[str]:
    tokens = _legend.legend_tokens(text)
    assert tokens is not None, "no bold Backing legend header"
    return tokens


def _backing_cell_ok(cell: str, tokens: list[str]) -> bool:
    return _legend.backing_cell_ok(cell, tokens)


def test_data_contract_template_backing_legend_is_closed_and_its_rows_and_checklist_obey_it():
    """kaizen 01M4F92G6V (2026-10-13): the registry's `Backing` column had a two-word legend hidden in prose and no
    check; most frozen contracts used tokens it never named. The template now states a CLOSED legend; this grader
    binds the three places that name it — the legend lines, the example rows and the FREEZE CHECKLIST box — so they
    cannot drift, and keeps the whole-cell grammar executable (round 1 of its review: a prefix match let
    `app-enforced` through, a placeholder exemption let anything through, the checklist compare was a prefix)."""
    import re

    text = (REPO_ROOT / "templates" / "scaffold" / "docs" / "data-contract-template.md").read_text(
        encoding="utf-8"
    )
    legend = _legend_tokens(text)
    assert legend == list(_BACKING_TOKENS), legend
    # the example rows obey the grammar — every table row of the registry section, backticked Enum cell or not
    has_section, registry = _legend.registry_rows(text)
    assert has_section and registry is not None, "the template's registry table is not recognised"
    rows = [backing for _enum, backing in registry]
    assert len(rows) == 2 and all(_backing_cell_ok(r, legend) for r in rows), rows
    # the grammar: legitimate shapes seen in frozen contracts pass …
    for good in (
        "native",
        "**CHECK**",
        "doc (unenforced)",
        "native (PG enum)",
        "CHECK *(SHIPPED mig 086/087, §R1)*",
        "file (config/a.yaml / Zod)",
        "native / CHECK",
        "app (no DB CHECK) / doc",
    ):
        assert _backing_cell_ok(good, legend), good
    # … and invented or malformed cells fail — the prefix-match class round 1 found
    for bad in (
        "app-enforced",
        "app-enforced, no DB CHECK",
        "native bespoke junk",
        "native, CHECK",
        "app.foo",
        "`contracts/` bespoke ⇒ Nautilus at runtime",
        "Tryton Selection",
        "jsonb value (§R3)",
        "<anything at all>",
        "",
        # round 2: unbalanced wrappers and a note hiding an invented tail
        "`native",
        "native**",
        "*native",
        "`native`*",
        "native (a) / bespoke junk",
        "CHECK (a) / <x> (b)",
        "native (a (b))",
        # round 3: the note's own wrapper must be balanced, and a note must say something
        "native (a)*",
        "native *(a)",
        "native ()",
        "native *()*",
        "native ( )",
        "native *(  )*",
    ):
        assert not _backing_cell_ok(bad, legend), bad
    for good in ("`CHECK`", "**native**", "*doc* (unenforced)", "CHECK (a) / `app` (b)"):
        assert _backing_cell_ok(good, legend), good
    # the FREEZE CHECKLIST box lists exactly the legend's tokens, in order (full equality, not a prefix)
    lines = text.splitlines()
    i = next(k for k, ln in enumerate(lines) if "is a legend token" in ln)
    box = lines[i]
    for nxt in lines[i + 1 :]:
        if not nxt.startswith("      "):
            break
        box += " " + nxt.strip()
    listed = re.findall(
        r"`([A-Za-z_]+)`", box.split("legend token", 1)[1].split(" — optionally")[0]
    )
    assert listed == legend, (listed, legend)
    # the parser fails loudly on a malformed legend, never silently
    broken = text.replace("`doc` (documented only", "doc (documented only", 1)
    try:
        _legend_tokens(broken)
    except ValueError as exc:
        assert "legend item is not" in str(exc)
    else:  # pragma: no cover — the assertion above is the behaviour under test
        raise AssertionError("a malformed legend item was parsed silently")
