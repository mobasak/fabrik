# AFTER-EDIT: scripts/fleet_doc_audit.py | none
"""Behavior contract for the fleet doc-freshness audit's pure probes."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import fleet_doc_audit as fda  # noqa: E402


def test_lag_days_code_leads_docs():
    assert fda.lag_days(100 * 86400, 79 * 86400) == 21


def test_lag_days_docs_current_or_newer_is_zero():
    assert fda.lag_days(100 * 86400, 100 * 86400) == 0
    assert fda.lag_days(100 * 86400, 200 * 86400) == 0


def test_lag_days_no_code_commits_is_zero():
    assert fda.lag_days(None, 50 * 86400) == 0


def test_stub_hits_counts_template_sentinels():
    text = "# [Project Name]\n\n**Last Updated:** YYYY-MM-DD\n\n- goal: [TBD — fill]\n- ok line\n"
    assert fda.stub_hits(text) == 3


def test_stub_hits_filled_doc_is_clean():
    text = "# seo\n\n**Last Updated:** 2026-08-07\n\n- goal: rank tracking\n"
    assert fda.stub_hits(text) == 0


def test_required_docs_compares_basenames_against_registry(tmp_path):
    # Day-review regression: the allowlist carries BARE basenames while KEY_DOCS
    # are docs/-prefixed — the naive membership test made the MISSING probe dead
    # code fleet-wide on first ship.
    (tmp_path / "project.yaml").write_text("type: python-api\n", encoding="utf-8")
    req = fda._required_docs(tmp_path)
    assert "docs/SERVICES.md" in req and "docs/RESILIENCE.md" in req


def test_audit_project_docs_never_committed_is_labeled_not_epoch(tmp_path):
    # Day-review regression: docs/ with zero git history must read as its own
    # failure mode, never an epoch-sized (~20,000d) lag that tops the report.
    import subprocess as sp

    sp.run(["git", "init", "-q"], cwd=tmp_path, check=True, timeout=15)
    sp.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], check=True, timeout=15)
    sp.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True, timeout=15)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "m.py").write_text("x=1\n", encoding="utf-8")
    sp.run(["git", "-C", str(tmp_path), "add", "src/m.py"], check=True, timeout=15)
    sp.run(["git", "-C", str(tmp_path), "commit", "-qm", "code"], check=True, timeout=15)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "notes.md").write_text("n\n", encoding="utf-8")  # untracked
    row = fda.audit_project(tmp_path)
    assert row is not None
    assert row.lag < 3650, f"epoch inflation: {row.lag}"
    assert any("never committed" in s for s in row.stale)


# ── INDEX self-indexing (added 2026-09-02) ───────────────────────────────────────────────
# THE DEFECT: the weekly cron wrote a new dated report every Monday and never touched
# INDEX.md, so check_doc_index went red for whoever ran the next unrelated gate — three
# earlier reports had been indexed BY HAND after the fact. Fixed at the generator; these
# tests are the guard, seen red before the helper existed.

_ANCHOR = "| [fleet-doc-audit-latest.md](docs/infrastructure/probe-reports/fleet-doc-audit-latest.md) | Newest fleet doc-freshness report |\n"


def _index(tmp_path, body: str):
    p = tmp_path / "INDEX.md"
    p.write_text(body, encoding="utf-8")
    return p


def test_ensure_index_row_inserts_exactly_one_row_before_the_latest_anchor(tmp_path):
    p = _index(tmp_path, "| a | b |\n" + _ANCHOR + "| z | z |\n")
    assert fda.ensure_index_row(p, "fleet-doc-audit-2026-09-02.md", "2026-09-02") is True
    lines = p.read_text(encoding="utf-8").splitlines()
    assert lines[1].startswith(
        "| [fleet-doc-audit-2026-09-02.md](docs/infrastructure/probe-reports/fleet-doc-audit-2026-09-02.md) |"
    )
    assert "2026-09-02" in lines[1]
    assert lines[2] == _ANCHOR.rstrip("\n"), (
        "the row must sit immediately BEFORE the -latest anchor"
    )
    assert sum("fleet-doc-audit-2026-09-02.md" in ln for ln in lines) == 1


def test_ensure_index_row_is_idempotent(tmp_path):
    p = _index(tmp_path, _ANCHOR)
    assert fda.ensure_index_row(p, "fleet-doc-audit-2026-09-02.md", "2026-09-02") is True
    before = p.read_text(encoding="utf-8")
    assert fda.ensure_index_row(p, "fleet-doc-audit-2026-09-02.md", "2026-09-02") is False
    assert p.read_text(encoding="utf-8") == before


def test_ensure_index_row_without_anchor_changes_nothing_and_says_so(tmp_path):
    p = _index(tmp_path, "| a | b |\n")
    assert fda.ensure_index_row(p, "fleet-doc-audit-2026-09-02.md", "2026-09-02") is False
    assert p.read_text(encoding="utf-8") == "| a | b |\n"


def test_ensure_index_row_finds_the_anchor_by_link_target_not_link_text(tmp_path):
    # F2 (scoped review 2026-09-02): a full-prefix match broke on any edit to the anchor row's
    # link text/description and failed only into a cron log nobody reads. Match the TARGET.
    p = _index(
        tmp_path,
        "| [latest audit](docs/infrastructure/probe-reports/fleet-doc-audit-latest.md) | some other wording |\n",
    )
    assert fda.ensure_index_row(p, "fleet-doc-audit-2026-09-02.md", "2026-09-02") is True
    assert "[fleet-doc-audit-2026-09-02.md](" in p.read_text(encoding="utf-8").splitlines()[0]


def test_index_is_clean_treats_a_staged_sibling_edit_as_dirty(tmp_path):
    # F1 (scoped review 2026-09-02, reproduced live): `git diff --quiet -- INDEX.md` compares the
    # worktree to the INDEX, so a sibling's staged-but-uncommitted edit read as clean and would be
    # swept into the cron's commit. The fail-safe must compare against HEAD.
    import subprocess

    def git(*a):
        return subprocess.run(
            ["git", "-C", str(tmp_path), *a], check=True, capture_output=True, text=True
        )

    git("init", "-q", ".")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (tmp_path / "INDEX.md").write_text("base\n", encoding="utf-8")
    git("add", "INDEX.md")
    git("commit", "-qm", "base")
    assert fda.index_is_clean(tmp_path) is True
    (tmp_path / "INDEX.md").write_text("base\nSIBLING STAGED EDIT\n", encoding="utf-8")
    git("add", "INDEX.md")  # staged, not committed — the trap
    assert fda.index_is_clean(tmp_path) is False


# ── A doc left as its scaffold template (added 2026-10-05, mail 01M4664J) ─────────────────
# THE DEFECT: the stub probe knew three hand-picked sentinels over five docs, and seeding
# substitutes two of them, so a doc the scaffold seeded and nobody filled read clean —
# brand-identiy-creator's OPERATIONS.md, and 32 of 36 fleet OPERATIONS.md. The template's own
# text is now the sentinel, read through the same substitutions the scaffold applies.

ROOT = Path(__file__).resolve().parents[1]


def _seed(template: str) -> str:
    """The doc the scaffold writes from ``template`` (its seeding substitutions applied)."""
    text = (ROOT / "templates" / "scaffold" / template).read_text(encoding="utf-8")
    for old in fda.SEED_SUBSTITUTED:
        text = text.replace(old, "demo")
    return text


def _project(tmp_path, docs: dict[str, str]):
    import subprocess as sp

    proj = tmp_path / "proj"
    (proj / "docs").mkdir(parents=True)
    sp.run(["git", "init", "-q"], cwd=proj, check=True, timeout=15)
    for rel, body in docs.items():
        (proj / rel).write_text(body, encoding="utf-8")
    return proj


def test_every_seeded_never_filled_doc_is_a_stub(tmp_path):
    docs = fda.templated_docs()
    assert len(docs) >= 9, docs  # the registry's fill-from-template docs, not an empty read
    row = fda.audit_project(_project(tmp_path, {rel: _seed(t) for rel, t in docs}))
    assert row is not None
    flagged = {s.split(" (")[0] for s in row.stubs if "template text left" in s}
    assert flagged == {Path(rel).name for rel, _ in docs}


def test_a_filled_doc_is_not_a_stub(tmp_path):
    seeded = _seed("docs/OPERATIONS_TEMPLATE.md")
    kept = [ln for ln in seeded.splitlines() if len(ln.strip()) > 25][:10]
    filled = "# Operations\n\nNightly sync at 02:00 UTC, owner: ops.\n" + "\n".join(kept) + "\n"
    row = fda.audit_project(_project(tmp_path, {"docs/OPERATIONS.md": filled}))
    assert row is not None
    assert not any("template text left" in s for s in row.stubs)


def test_kept_shape_docs_are_not_template_scanned(tmp_path):
    seeded = {"CHANGELOG.md": _seed("docs/CHANGELOG_TEMPLATE.md")}
    seeded["docs/LESSONS_LEARNT.md"] = _seed("docs/LESSONS_LEARNT_TEMPLATE.md")
    row = fda.audit_project(_project(tmp_path, seeded))
    assert row is not None
    assert not any("template text left" in s for s in row.stubs)


def test_a_key_doc_left_as_template_gets_one_entry(tmp_path):
    body = _seed("docs/SERVICES_TEMPLATE.md") + "\n[TBD — owner]\n"
    row = fda.audit_project(_project(tmp_path, {"docs/SERVICES.md": body}))
    assert row is not None
    assert [s for s in row.stubs if s.startswith("SERVICES.md")] == [
        next(s for s in row.stubs if "template text left" in s)
    ]


def test_seed_substituted_mirrors_every_scaffold_seeding_loop():
    import ast

    tree = ast.parse((ROOT / "src" / "fabrik" / "scaffold.py").read_text(encoding="utf-8"))
    loops = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.For)
        and isinstance(n.target, ast.Tuple)
        and [getattr(e, "id", None) for e in n.target.elts] == ["old", "new"]
        and isinstance(n.iter, ast.List)
    ]
    assert loops, "scaffold.py's seeding loops moved — re-point this mirror"
    olds = {e.elts[0].value for loop in loops for e in loop.iter.elts}
    assert olds == set(fda.SEED_SUBSTITUTED)


def test_repo_flag_audits_one_project_without_writing(tmp_path, monkeypatch, capsys):
    proj = _project(tmp_path, {"docs/OPERATIONS.md": _seed("docs/OPERATIONS_TEMPLATE.md")})
    reports = tmp_path / "reports"
    monkeypatch.setattr(fda, "REPORT_DIR", reports)
    monkeypatch.setattr(sys, "argv", ["fleet_doc_audit.py", "--repo", str(proj)])
    assert fda.main() == 0
    out = capsys.readouterr().out
    assert "project: proj" in out and "OPERATIONS.md (template text left:" in out
    assert not reports.exists()


def test_a_sentinel_in_a_templated_doc_outside_the_key_docs_is_counted(tmp_path):
    body = "# Business model\n\n## Customer\n\n[TBD — role, company size, region]\n"
    row = fda.audit_project(_project(tmp_path, {"docs/BUSINESS_MODEL.md": body}))
    assert row is not None
    assert "BUSINESS_MODEL.md (1)" in row.stubs


def test_seeded_fill_in_tokens_are_sentinels():
    text = "| api | [API — fill in] | [purpose] | [free · $X/mo] |\n"
    assert fda.stub_hits(text) == 2


def test_a_doc_seeded_from_an_older_template_version_is_a_stub(tmp_path):
    import subprocess as sp

    rel = "templates/scaffold/docs/DEPLOYMENT_TEMPLATE.md"
    shas = sp.run(
        ["git", "-C", str(ROOT), "log", "--format=%H", "--", rel],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout.split()
    assert len(shas) >= 2, "needs a template with history"
    old = sp.run(
        ["git", "-C", str(ROOT), "show", f"{shas[-1]}:{rel}"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout
    current = (ROOT / rel).read_text(encoding="utf-8")
    assert fda.template_left_pct(old, "docs/DEPLOYMENT_TEMPLATE.md") == 100
    for x in fda.SEED_SUBSTITUTED:
        old = old.replace(x, "demo")
    assert _seed("docs/DEPLOYMENT_TEMPLATE.md") != old and current != old
    row = fda.audit_project(_project(tmp_path, {"docs/DEPLOYMENT.md": old}))
    assert row is not None
    assert any(s.startswith("DEPLOYMENT.md (template text left:") for s in row.stubs)


# ── Round-1 review fixes: precision, boundaries, git env ─────────────────────────────────


@pytest.fixture
def toy_template(tmp_path, monkeypatch):
    """A 4-line template under a non-git FABRIK_ROOT (no history), caches cleared both ways."""
    root = tmp_path / "hub"
    tpl = root / "templates" / "scaffold"
    tpl.mkdir(parents=True)
    lines = [f"template line number {i} with enough characters" for i in range(4)]
    (tpl / "T.md").write_text(
        "\n".join([*lines, "short line", "# [Project Name] heading line long"])
    )
    monkeypatch.setattr(fda, "FABRIK_ROOT", root)
    monkeypatch.setattr(fda, "TEMPLATE_DIR", tpl)
    fda.template_versions.cache_clear()
    fda.template_history_complete.cache_clear()
    yield lines
    fda.template_versions.cache_clear()
    fda.template_history_complete.cache_clear()


def test_seed_lines_skip_short_and_seed_substituted_lines(toy_template):
    assert fda.template_versions("T.md") == (frozenset(toy_template),)


def test_template_rule_boundaries(toy_template):
    own = [f"our own documentation line {i}, written for this project" for i in range(4)]
    half = "\n".join(toy_template[:2])
    assert fda.template_verdict(half, "T.md") == 50  # 2 of 4 template lines, all of the doc
    assert fda.template_verdict(toy_template[0], "T.md") is None  # 25%
    assert fda.template_verdict(half + "\n" + "\n".join(own[:2]), "T.md") == 50  # doc share 50%
    assert fda.template_verdict(half + "\n" + "\n".join(own[:3]), "T.md") is None  # doc share 40%


def test_a_long_filled_doc_keeping_template_blocks_is_not_a_stub(tmp_path):
    whole = _seed("docs/OPERATIONS_TEMPLATE.md")
    assert fda.template_left_pct(whole, "docs/OPERATIONS_TEMPLATE.md") == 100
    own = "\n".join(
        f"- runbook step {i}: rotate the {i}th feed credential and re-run" for i in range(400)
    )
    row = fda.audit_project(_project(tmp_path, {"docs/OPERATIONS.md": whole + "\n" + own}))
    assert row is not None
    assert not any("template text left" in s for s in row.stubs)


def test_an_inherited_git_dir_never_redirects_the_hub_history(tmp_path, monkeypatch):
    import subprocess as sp

    other = tmp_path / "other"
    other.mkdir()
    sp.run(["git", "init", "-q"], cwd=other, check=True, timeout=15)
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    fda.template_versions.cache_clear()
    try:
        assert len(fda.template_versions("docs/DEPLOYMENT_TEMPLATE.md")) >= 2
    finally:
        fda.template_versions.cache_clear()


def test_repo_flag_says_when_template_history_is_unavailable(
    toy_template, tmp_path, monkeypatch, capsys
):
    proj = _project(tmp_path, {"docs/OPERATIONS.md": "# ops\n"})
    monkeypatch.setattr(sys, "argv", ["fleet_doc_audit.py", "--repo", str(proj)])
    assert fda.main() == 0
    assert "template history: unavailable" in capsys.readouterr().out


def test_history_is_incomplete_for_a_hub_copy_inside_another_repo(tmp_path, monkeypatch):
    import subprocess as sp

    fda.template_history_complete.cache_clear()
    assert fda.template_history_complete() is True  # the real hub: its own, full history
    outer = tmp_path / "outer"
    (outer / "hub").mkdir(parents=True)
    sp.run(["git", "init", "-q"], cwd=outer, check=True, timeout=15)
    monkeypatch.setattr(fda, "FABRIK_ROOT", outer / "hub")
    fda.template_history_complete.cache_clear()
    try:
        assert fda.template_history_complete() is False
    finally:
        fda.template_history_complete.cache_clear()


def test_git_reads_ignore_an_inherited_git_dir(tmp_path, monkeypatch):
    import subprocess as sp

    other = tmp_path / "other"
    other.mkdir()
    sp.run(["git", "init", "-q"], cwd=other, check=True, timeout=15)
    mine = tmp_path / "mine"
    mine.mkdir()
    (mine / "INDEX.md").write_text("# index\n")
    sp.run(["git", "init", "-q"], cwd=mine, check=True, timeout=15)
    sp.run(["git", "add", "INDEX.md"], cwd=mine, check=True, timeout=15)
    ident = ["-c", "user.name=t", "-c", "user.email=t@t"]
    sp.run(["git", *ident, "commit", "-qm", "i"], cwd=mine, check=True, timeout=15)
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))  # an empty repo: no HEAD to read
    assert fda._git_ts(mine) is not None
    assert fda.index_is_clean(mine) is True


def test_weekly_report_carries_the_history_note(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(fda, "template_history_complete", lambda: False)
    monkeypatch.setattr(fda, "OPT", tmp_path)
    assert fda.run(write_report=False) == 0
    assert "template history: unavailable" in capsys.readouterr().out
