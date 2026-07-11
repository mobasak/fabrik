"""Behavior Contract for the `--range` cumulative coverage mode on the doc-sync checks.

The whole-plan coverage receipt: `check_doc_sync --range <base>..HEAD` (+ check_doc_stubs) asserts every
fired-trigger doc was touched across the WHOLE plan, not just the last staged commit — with the exact same
trigger→doc rules, only the input file-set widened. The default (no --range) staged behavior must be
byte-identical to before (a regression guard).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ENF = Path(__file__).resolve().parents[1] / "scripts" / "enforcement"
if str(_ENF) not in sys.path:
    sys.path.insert(0, str(_ENF))

import check_doc_stubs as cds_stubs  # noqa: E402
import check_doc_sync as cds_sync  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _mk_repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t.dev")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "README.md").write_text("base\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


# ── the coverage receipt reports a fired-trigger doc that went untouched across the whole range ──
def test_range_reports_missing_changelog(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("x = 1\n")  # significant code change, NO CHANGELOG
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "code without changelog")
    monkeypatch.chdir(repo)
    # ERROR-tier: a significant code change across the range with CHANGELOG untouched
    assert cds_sync.main(["--range", "HEAD~1..HEAD"]) == 1


# ── clean when the doc WAS touched somewhere in the range ──
def test_range_clean_when_changelog_touched(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("x = 1\n")
    (repo / "CHANGELOG.md").write_text("## [Unreleased]\n\n### Added — x (2026-07-11)\n\nbody\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "code + changelog")
    monkeypatch.chdir(repo)
    assert cds_sync.main(["--range", "HEAD~1..HEAD"]) == 0


# ── a bad/unresolvable range is fail-safe (git diff fails → empty file set → exit 0) ──
def test_range_bad_ref_failsafe(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    monkeypatch.chdir(repo)
    assert cds_sync.main(["--range", "nonexistent0badref123..HEAD"]) == 0


# ── the default (no --range) staged behavior is UNCHANGED — the regression guard ──
def test_default_staged_unchanged(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("x = 1\n")
    _git(repo, "add", "src/app.py")  # STAGED significant code, no CHANGELOG staged
    monkeypatch.chdir(repo)
    assert cds_sync.main([]) == 1  # same ERROR the staged path always produced
    # and with nothing staged → exit 0 (unchanged)
    _git(repo, "reset", "-q")
    assert cds_sync.main([]) == 0


# ── check_doc_stubs --range reuses ds._range + is advisory — assert it ACTUALLY fires (not vacuous) ──
def test_stubs_range_advisory(tmp_path, monkeypatch, capsys):
    repo = _mk_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "QUICKSTART.md").write_text("[Project Name] still a stub\n")  # a NAME placeholder
    (repo / "app.py").write_text("@app.get('/x')\ndef h():\n    return 1\n")  # route → QUICKSTART trigger
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "route + stub doc")
    monkeypatch.chdir(repo)
    assert cds_stubs.main(["--range", "HEAD~1..HEAD"]) == 0  # advisory never blocks
    # …but it must genuinely have run over the range: the route trigger fired the QUICKSTART stub WARN.
    # (A broken ds._range reuse → no files → no trigger → no WARN → this assertion fails.)
    assert "QUICKSTART.md" in capsys.readouterr().out
    assert cds_stubs.main([]) == 0  # default path still advisory


# ── the ADR / _range_adr path fires across a range (INDEX is WARN-tier, so CHANGELOG present → exit 0) ──
def test_range_index_warn_on_added_file(tmp_path, monkeypatch, capsys):
    repo = _mk_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "new_mod.py").write_text("y = 2\n")  # a NEW file (added/removed/renamed set)
    (repo / "CHANGELOG.md").write_text("## [Unreleased]\n\n### Added — y (2026-07-11)\n\nbody\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "new file + changelog, no INDEX")
    monkeypatch.chdir(repo)
    rc = cds_sync.main(["--range", "HEAD~1..HEAD"])
    out = capsys.readouterr().out
    assert rc == 0  # INDEX is WARN-tier and CHANGELOG is present → no ERROR
    assert "INDEX.md" in out  # _range_adr fired the INDEX WARN across the range


# ── an explicitly-empty --range is a hard ERROR, not a silent staged fallback (false-clean receipt) ──
def test_empty_range_is_error(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    monkeypatch.chdir(repo)
    assert cds_sync.main(["--range", ""]) == 1
    assert cds_sync.main(["--range", "   "]) == 1


# ── the ERROR-tier schema trigger is case-insensitive (WP-2) — consistent with check_doc_stubs/Tier-1 ──
def test_schema_error_trigger_case_insensitive(tmp_path, monkeypatch):
    repo = _mk_repo(tmp_path)
    (repo / "db" / "MIGRATIONS").mkdir(parents=True)  # UPPERCASE subdir under lowercase db/
    (repo / "db" / "schema.sql").write_text("-- schema dump\n")  # tracked dump (db/schema.sql)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base with schema dump")
    (repo / "db" / "MIGRATIONS" / "001.sql").write_text("CREATE TABLE x (id int);\n")
    (repo / "CHANGELOG.md").write_text("## [Unreleased]\n\n### Added — m (2026-07-11)\n\nb\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "uppercase MIGRATIONS subdir, schema dump NOT updated")
    monkeypatch.chdir(repo)
    # db/schema.sql was not updated for the `db/MIGRATIONS/…` change → ERROR (exit 1). This only fires
    # if the migration match is case-insensitive; case-sensitive `/migrations/` would miss `MIGRATIONS`.
    assert cds_sync.main(["--range", "HEAD~1..HEAD"]) == 1


# ── _schema_doc_for resolves the dump case-insensitively too (no half-applied fix) ──
def test_schema_doc_for_case_insensitive():
    assert cds_sync._schema_doc_for("Db/Migrations/x.sql") == "Db/schema.sql"  # preserves original case
    assert cds_sync._schema_doc_for("web/DB/migrations/y.sql") == "web/DB/schema.sql"
    assert cds_sync._schema_doc_for("db/models.py") == "db/schema.sql"
    assert cds_sync._schema_doc_for("src/app.py") == "db/schema.sql"  # no db component → root fallback


# ── _git degrades to [] on a real subprocess error (git missing / timeout) — no gate crash ──
def test_git_failsafe_on_subprocess_error(monkeypatch):
    def _boom(*a, **k):
        raise subprocess.SubprocessError("git exploded")

    monkeypatch.setattr(cds_sync.subprocess, "run", _boom)
    assert cds_sync._git(["diff", "--cached", "--name-only"]) == []  # error swallowed → empty
    assert cds_sync.main([]) == 0  # the default (staged) path degrades safely, doesn't crash the gate


# ── the .sql schema trigger is case-insensitive (P4-8 fix) ──
def test_schema_trigger_case_insensitive():
    detectors = cds_stubs._trigger_detectors()
    schema = detectors["docs/data-contract.md"]
    assert schema(["db/SCHEMA.SQL"]) is True  # uppercase extension still fires
    assert schema(["db/schema.sql"]) is True
    assert schema(["src/app.py"]) is False
