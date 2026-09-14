"""`--adopt --dry-run` must write nothing, and the template predicate must not drift from its twin.

T12.9 (01M1S2MYZ, 01M1Z0PEB). `--dry-run`'s own `--help` says "Preview changes without writing"
and `run_adopt` never received the flag: reproduced on a scratch repo, a preview modified three
files and CREATED two more, minting a `D-001 (MERGE OWNER)` row in `docs/DECISIONS.md`. On a tree
three sessions share, a preview was writing to the decision ledger and the backlog.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "scripts" / "docs_updater.py"
DOC_LINKS = ROOT / "scripts" / "enforcement" / "check_doc_links.py"

PLAN = """# Plan 1 — probe

Status: DRAFT

## Ticket Board

| Ticket | Title | Owner | Status |
|---|---|---|---|
| T01 | do a thing | — | OPEN |
"""


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "docs" / "development" / "plans").mkdir(parents=True)
    (tmp_path / "scripts" / "docs_updater.py").write_bytes(UPDATER.read_bytes())
    (tmp_path / "docs" / "development" / "plans" / "2026-09-14-plan-1-probe.md").write_text(PLAN)
    (tmp_path / "docs" / "STRATEGIC_BACKLOG.md").write_text(
        "# Strategic backlog\n\n- [ ] **[?]** a row that wants an owner\n"
    )
    (tmp_path / "docs" / "development" / "plans" / "README.md").write_text("# Plans\n")
    for argv in (["git", "init", "-q"], ["git", "add", "-A"]):
        subprocess.run(argv, cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=tmp_path, check=True)
    return tmp_path


def _adopt(project: Path, *extra: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "scripts/docs_updater.py", "--adopt", "probe", "--single-window", *extra],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _dirty(project: Path) -> str:
    return subprocess.run(
        ["git", "status", "--porcelain"], cwd=project, capture_output=True, text=True, check=True
    ).stdout


def test_adopt_dry_run_writes_nothing(project: Path) -> None:
    """The defect, reproduced: before the fix this run modified three files and created two."""
    clean = _dirty(project)
    rc, out = _adopt(project, "--dry-run")
    assert rc == 0, out
    assert _dirty(project) == clean, (
        f"--dry-run mutated the tree:\n{_dirty(project)}\n(--help promises 'without writing')"
    )
    assert not (project / "docs" / "DECISIONS.md").exists(), (
        "a preview minted a decision row — the ledger's own rows are immutable once written"
    )


def test_adopt_dry_run_reports_exactly_what_a_real_run_would_do(project: Path) -> None:
    """A dry run that under-reports is worse than none: the point is to see the real plan. Every
    row the real run emits must appear in the dry run's report."""
    _rc, dry = _adopt(project, "--dry-run")
    _rc2, real = _adopt(project)
    for token in ("owner-line", "ledger-row", "backlog-row", "markers"):
        assert token in dry, f"dry run omitted a {token} row that the real run performs"
        assert token in real
    assert _dirty(project) != "", "the real run must still mutate — the guard must not disarm it"


def test_the_template_predicate_agrees_with_its_twin_in_check_doc_links() -> None:
    """T12.9's other half: `check_doc_links.py` has excluded scaffold templates since /opt/seo
    reported 21 of 28 false "broken" refs; `docs_updater.py`'s own link walk never grew it, so two
    synced checks disagreed about the same tree. Measured over four repos' docs/: seo carries 24
    `*_TEMPLATE.md` plus a `scaffold-templates/` dir among 176 docs, the hub 2 of 1,203, two of the
    four none. Two predicates for one rule is two things to drift."""
    du = _load("du_t129", UPDATER)
    dl = _load("dl_t129", DOC_LINKS)
    twin = dl._is_template_source
    for case in (
        "docs/a_TEMPLATE.md",
        "docs/scaffold-templates/x.md",
        "docs/normal.md",
        "docs/deep/b_TEMPLATE.md",
        "docs/TEMPLATE.md",
        "docs/x/scaffold-templates/y/z.md",
        "docs/scaffold-templates.md",
    ):
        assert du._is_scaffold_template(case) == twin(case), case


def test_the_link_walk_actually_skips_a_template(tmp_path: Path, monkeypatch) -> None:
    """The predicate existing is not the fix — it has to be REACHED by the walk."""
    du = _load("du_t129b", UPDATER)
    docs = tmp_path / "docs"
    (docs / "scaffold-templates").mkdir(parents=True)
    (docs / "real.md").write_text("[x](does-not-exist.md)\n")
    (docs / "tpl_TEMPLATE.md").write_text("[x](also-missing.md)\n")
    (docs / "scaffold-templates" / "s.md").write_text("[x](gone.md)\n")
    monkeypatch.setattr(du, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(du, "_gitignored", lambda paths: set())
    issues = du.check_link_integrity()
    blob = "\n".join(issues)
    assert "real.md" in blob, "the walk must still report a genuinely broken link"
    assert "tpl_TEMPLATE.md" not in blob
    assert "scaffold-templates" not in blob
