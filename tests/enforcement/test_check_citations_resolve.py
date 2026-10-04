"""Behaviour tests for scripts/enforcement/check_citations_resolve.py (01M1J2TP, 01M1GNGS, 01M1JF7Y).

MISSING-FILE was measured and REJECTED as a class: on the hub 500+ of 1600 citations name another
repo's files (old cross-repo plans) — grading them would be wallpaper on day one."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "check_citations_resolve", REPO / "scripts" / "enforcement" / "check_citations_resolve.py"
)
assert _spec and _spec.loader
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "x.py").write_text(
        "a = 1\n\n---\n```\nb = 2\n", encoding="utf-8"
    )  # 5 lines: 2 blank, 3 rule, 4 fence
    return tmp_path


def test_the_three_classes_are_named_and_a_good_citation_is_silent(tmp_path):
    repo = _repo(tmp_path)
    text = (
        "good: scripts/x.py:1 and a range scripts/x.py:1-5\n"
        "blank: scripts/x.py:2 · rule: scripts/x.py:3 · fence: scripts/x.py:4\n"
        "beyond: scripts/x.py:9 · range-beyond: scripts/x.py:4-9\n"
        "missing (not graded — another repo's file): scripts/nope.py:3\n"
        "not a citation: https://host:8000/x and 12:30 and `--limit 5:2`\n"
        "bare filename (ambiguous — another repo's compose shares the name): x.py:9 compose.yaml:60\n"
        "```\nscripts/x.py:999  # inside a fence — not a claim\n```\n"
    )
    seen, findings = chk.check_text(text, repo)
    kinds = [f.split()[0] for f in findings]
    assert kinds == ["BLANK-TARGET", "BLANK-TARGET", "BLANK-TARGET", "BEYOND-EOF", "BEYOND-EOF"], (
        findings
    )
    assert (
        seen == 7
    )  # 2 good + 3 blank + 2 beyond (a missing file, the fenced and non-citation tokens excluded)


def test_repo_walk_covers_the_four_source_families_and_exits_zero(tmp_path, capsys):
    repo = _repo(tmp_path)
    for rel in (
        "docs/superpowers/specs/s.md",
        "docs/development/plans/p.md",
        "docs/development/reviews/r.md",
        "docs/reference/d.md",
    ):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text("see scripts/x.py:2\n", encoding="utf-8")
    ndocs, ncites, findings = chk.check_repo(repo)
    assert (ndocs, ncites, len(findings)) == (4, 4, 4)
    assert chk.main(["--root", str(repo)]) == 0  # advisory: never blocks
    out = capsys.readouterr().out
    assert "4 citation(s) do not land, of 4 examined across 4 docs" in out


def test_it_is_registered_in_the_gate_as_warn_only():
    src = (REPO / "scripts" / "final_gate.py").read_text(encoding="utf-8")
    assert "check_citations_resolve.py" in src
    block = src[src.index("check_citations_resolve.py") :][:400]
    assert "warn_only=True" in block


def test_dated_artifacts_outside_the_window_are_history_and_undated_docs_are_always_graded(
    tmp_path,
):
    repo = _repo(tmp_path)
    (repo / "docs" / "development" / "plans").mkdir(parents=True)
    (repo / "docs" / "reference").mkdir(parents=True)
    (repo / "docs" / "development" / "plans" / "2026-01-01-plan-old.md").write_text(
        "scripts/x.py:2\n"
    )
    (repo / "docs" / "reference" / "current.md").write_text("scripts/x.py:2\n")
    ndocs, ncites, findings = chk.check_repo(repo)  # default window
    assert (ndocs, len(findings)) == (
        1,
        1,
    )  # the January plan is history; the reference doc is graded
    ndocs, _, findings = chk.check_repo(repo, since_days=10_000)
    assert (ndocs, len(findings)) == (2, 2)


def test_changed_mode_grades_only_the_docs_git_reports_as_changed(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    (repo / "docs" / "reference").mkdir(parents=True)
    a = repo / "docs" / "reference" / "a.md"
    b = repo / "docs" / "reference" / "b.md"
    a.write_text("scripts/x.py:2\n")
    b.write_text("scripts/x.py:2\n")
    monkeypatch.setattr(chk, "_changed_docs", lambda r: {a})
    ndocs, _, findings = chk.check_repo(repo, only=chk._changed_docs(repo))
    assert (ndocs, len(findings)) == (1, 1) and "a.md" in findings[0]


def test_line_one_frontmatter_is_a_legitimate_target(tmp_path):
    repo = tmp_path
    (repo / "docs").mkdir()
    (repo / "docs" / "f.md").write_text("---\ntitle: x\n---\nbody\n", encoding="utf-8")
    seen, findings = chk.check_text("see docs/f.md:1 and docs/f.md:3", repo)
    assert seen == 2 and [f.split()[0] for f in findings] == [
        "BLANK-TARGET"
    ]  # :3 is the closing rule, :1 is the head


# ── 01M3PNG4 (fabrik-lib, 2026-09-29): a run that graded nothing must SAY so — seen RED first.
# Measured: the hub copy run from /opt/fabrik-lib graded the HUB's changed docs and printed
# "✓ citations resolve — 0 `path:line` citation(s) across 2 docs all land".


def test_warns_when_run_from_another_repo(tmp_path, capsys, monkeypatch):
    (tmp_path / "graded").mkdir()
    repo = _repo(tmp_path / "graded")
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setattr(chk, "REPO", repo)
    monkeypatch.setattr(chk, "_cwd_toplevel", lambda: other.resolve())
    assert chk.main(["--quiet"]) == 0
    out = capsys.readouterr().out
    assert f"⚠ check_citations_resolve graded {repo}, not the repo it was run from" in out, out
    assert f"pass --root {other.resolve()}" in out, out
    monkeypatch.setattr(chk, "_cwd_toplevel", lambda: repo.resolve())
    assert chk.main(["--quiet"]) == 0
    assert "not the repo it was run from" not in capsys.readouterr().out


def test_summary_counts_citations_outside_the_root(tmp_path, capsys):
    repo = _repo(tmp_path)
    doc = repo / "docs" / "reference" / "d.md"
    doc.parent.mkdir(parents=True)
    doc.write_text(
        "see src/elsewhere/a.py:3 and src/elsewhere/b.py:9-12 and compose.yaml:60\n",
        encoding="utf-8",
    )
    for args in (["--root", str(repo)], ["--root", str(repo), "--quiet"]):
        assert chk.main(args) == 0
        out = capsys.readouterr().out
        assert "⚠ check_citations_resolve NOTHING GRADED across 1 docs" in out, (args, out)
        assert f"0 graded of 3 found (1 bare filename, 2 not under root {repo})" in out, out
        assert "all land" not in out, out


def test_summary_has_no_skip_clause_when_all_cited_paths_exist(tmp_path, capsys):
    repo = _repo(tmp_path)
    doc = repo / "docs" / "reference" / "d.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("see scripts/x.py:1\n", encoding="utf-8")
    assert chk.main(["--root", str(repo)]) == 0
    out = capsys.readouterr().out
    assert "1 `path:line` citation(s) across 1 docs all land" in out, out
    assert f"1 graded of 1 found (0 bare filename, 0 not under root {repo})" in out, out
    assert "⚠" not in out, out


def test_bare_filenames_alone_never_print_nothing_graded(tmp_path, capsys):
    repo = _repo(tmp_path)
    doc = repo / "docs" / "reference" / "d.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("see agents-fabrik.md:158 and compose.yaml:60\n", encoding="utf-8")
    assert chk.main(["--root", str(repo), "--quiet"]) == 0
    assert capsys.readouterr().out == ""  # bare names are non-claims: a quiet run stays silent
    assert chk.main(["--root", str(repo)]) == 0
    assert "0 graded of 2 found (2 bare filename, 0 not under root" in capsys.readouterr().out


def test_an_empty_root_is_nothing_in_scope_not_all_land(tmp_path, capsys):
    assert chk.main(["--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "citations: nothing in scope — 0 docs under" in out, out
    assert "all land" not in out, out
