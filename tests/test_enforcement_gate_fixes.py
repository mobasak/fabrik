"""Regression tests for the enforcement-gate fixes (centrally-synced scripts).

Highest stakes — #1/#2: `check_secrets.py` / `check_env_vars.py` were INERT (no
`main()`/`__main__`), so final_gate's "Secrets (Zero Hardcoding)" + ".env Updates
(Secrets)" gates were permanent no-ops on every project — hardcoded secrets and
`localhost` passed the gate. These tests would FAIL on the old code (no `main`)
and pass on the fix. They also pin the standalone relative-import fix (final_gate
runs these as `python <path>`, not `-m`).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.enforcement import check_env_vars, check_secrets  # noqa: E402
from scripts.enforcement.check_doc_sync import _changelog_quality_ok  # noqa: E402


# --- #1 check_secrets -------------------------------------------------------
def test_check_secrets_main_fails_on_hardcoded_secret(tmp_path, monkeypatch):
    leak = tmp_path / "leak.py"
    leak.write_text('TOKEN = "sk-ant-abcdefghijklmnopqrstuvwxyz0123456789"\n')
    monkeypatch.setattr(check_secrets, "_changed_files", lambda: [str(leak)])
    assert check_secrets.main() == 1, "secrets gate must FAIL on a hardcoded credential"


def test_check_secrets_main_passes_when_clean(tmp_path, monkeypatch):
    clean = tmp_path / "ok.py"
    clean.write_text('TOKEN = os.getenv("TOKEN")\n')
    monkeypatch.setattr(check_secrets, "_changed_files", lambda: [str(clean)])
    assert check_secrets.main() == 0


def test_check_secrets_has_entry_point():
    # The whole bug: no main() => running the script did nothing => permanent PASS.
    assert callable(getattr(check_secrets, "main", None)), "check_secrets must expose main()"


# --- template-generator pragma (Phase 3 / CI-parity enablement) -------------
# A generator module (scaffold.py) EMITS config templates (localhost dev URLs,
# <user>:<pass> examples) into new projects — content-scanning secret/localhost checks
# false-fire on it. A file opts out with `# noqa-file: template-generator`. The
# exemption MUST be file-scoped: real secrets in any other file are still caught.
def test_secrets_pragma_skips_generator_file(tmp_path):
    gen = tmp_path / "gen.py"
    gen.write_text(
        '# noqa-file: template-generator\nDSN = "postgresql://u:realpass@localhost/db"\n'
    )
    assert check_secrets.check_file(gen) == []


def test_secrets_pragma_is_file_scoped(tmp_path):
    leak = tmp_path / "app.py"
    leak.write_text('DSN = "postgresql://u:realpass@localhost/db"\n')
    assert check_secrets.check_file(leak), "non-pragma'd file must STILL catch real secrets"


def test_env_vars_pragma_skips_generator_file(tmp_path):
    gen = tmp_path / "gen.py"
    gen.write_text('# noqa-file: template-generator\nURL = "http://localhost:3100/x"\n')
    assert check_env_vars.check_file(gen) == []


def test_env_vars_pragma_is_file_scoped(tmp_path):
    app = tmp_path / "app.py"
    app.write_text('URL = "http://localhost:3100/x"\n')
    assert check_env_vars.check_file(app), "non-pragma'd file must STILL catch localhost"


# --- #2 check_env_vars ------------------------------------------------------
def test_check_env_vars_main_fails_on_hardcoded_localhost(tmp_path, monkeypatch):
    leak = tmp_path / "db.py"
    leak.write_text('DB_HOST = "localhost"\n')
    monkeypatch.setattr(check_env_vars, "_changed_files", lambda: [str(leak)])
    assert check_env_vars.main() == 1, ".env gate must FAIL on hardcoded localhost"


def test_check_env_vars_main_allows_getenv_default(tmp_path, monkeypatch):
    ok = tmp_path / "db.py"
    ok.write_text('DB_HOST = os.getenv("DB_HOST", "localhost")\n')
    monkeypatch.setattr(check_env_vars, "_changed_files", lambda: [str(ok)])
    assert check_env_vars.main() == 0, "os.getenv default is allowlisted — must pass"


def test_check_env_vars_allows_getenv_scheme_prefixed_localhost_default(tmp_path, monkeypatch):
    # Regression: os.getenv("LOKI_URL", "http://localhost:3100") is the sanctioned
    # pattern too (a scheme-prefixed localhost DEFAULT), not just bare "localhost".
    ok = tmp_path / "loki.py"
    ok.write_text('LOKI = os.getenv("LOKI_URL", "http://localhost:3100")\n')
    monkeypatch.setattr(check_env_vars, "_changed_files", lambda: [str(ok)])
    assert check_env_vars.main() == 0, "os.getenv http://localhost default must pass"


def test_check_env_vars_still_fails_literal_http_localhost(tmp_path, monkeypatch):
    # The allowlist must NOT have over-broadened: a literal http://localhost URL
    # outside os.getenv is still a hard-fail.
    leak = tmp_path / "client.py"
    leak.write_text('BASE = "http://localhost:3100"\n')
    monkeypatch.setattr(check_env_vars, "_changed_files", lambda: [str(leak)])
    assert check_env_vars.main() == 1, "literal http://localhost must still FAIL"


# --- #5 check_doc_sync changelog quality ------------------------------------
def test_changelog_quality_rejects_fenced_only_entry(tmp_path, monkeypatch):
    # A `### …` that exists ONLY inside a ``` fence ``` (a template) is not real.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(
        "## [Unreleased]\n\n```\n### Added — Example (2026-01-01)\n```\n\n## [1.0]\n"
    )
    assert _changelog_quality_ok() is False


def test_changelog_quality_accepts_real_entry(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(
        "## [Unreleased]\n\n### Fixed — real thing (2026-06-28)\n\n## [1.0]\n"
    )
    assert _changelog_quality_ok() is True


# W-753040b8: a span is a whole backtick run closed only by an EQUAL run, so a double-backtick quote is one
# quotation and a lone `` is no span (the one-backtick regex read ``TODO`` as two empty spans around a bare TODO,
# and deleted a lone `` to glue `todo``todo` into one word); an odd-count line still fails closed.
@pytest.mark.parametrize(
    ("line", "ok"),
    [
        ("- quotes a ``TODO`` token", True),
        ("- quotes ```` ``TODO`` ```` as a nested quote", True),
        ("- quotes a `TODO` token", True),
        ("- a bare TODO beside ``x``", False),
        ("- todo``todo", False),
        ("- a stray ` and then a TODO", False),
    ],
)
def test_changelog_quality_reads_whole_backtick_runs(tmp_path, monkeypatch, line, ok):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(
        f"## [Unreleased]\n\n### Fixed — real thing (2026-06-28)\n\n{line}\n\n## [1.0]\n"
    )
    assert _changelog_quality_ok() is ok


# --- #8 + enum-identity: validate_conventions must FAIL on a violation -------
def test_validate_conventions_m_fails_on_violation():
    """Run via `python -m` (how final_gate invokes it, with --git-diff). The
    package __init__ double-imports the module, so a Severity-identity comparison
    silently exited 0 on real violations. This plants a hardcoded localhost and
    asserts the validator actually fails (non-zero). Regression guard for the
    tier-3 no-op (#8, missing --git-diff) AND the enum-identity exit-code bug.
    """
    import subprocess

    repo = Path(__file__).resolve().parent.parent
    leak = repo / "scripts" / "_localhost_leak.py"
    leak.write_text('X = "localhost:5432"\n')
    try:
        subprocess.run(["git", "add", "-N", str(leak)], cwd=repo, check=True)
        r = subprocess.run(
            ["python3", "-m", "scripts.enforcement.validate_conventions", "--strict", "--git-diff"],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        assert r.returncode != 0, (
            "validate_conventions must FAIL on a hardcoded localhost; got exit 0 "
            f"(enum-identity / missing --git-diff regression). stdout:\n{r.stdout[-500:]}"
        )
    finally:
        subprocess.run(["git", "rm", "--cached", "-q", str(leak)], cwd=repo, check=False)
        leak.unlink(missing_ok=True)


# --- #9 diff-scoping: the gate never touches/reds a file the change didn't touch ---
# Root cause of the calendar-orchestration block + the 12-file auto-fix churn:
# get_changed_files saw only the working tree, so a committed-clean tree looked empty
# and the gate fell back to whole-tree (ruff-checking a Fabrik-synced E501 line it
# couldn't edit; ruff-format/EOF-sweeping unrelated sibling files). These pin the
# scoping fix.
from scripts import final_gate  # noqa: E402


def test_changed_python_filters_to_existing_py_under_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", tmp_path)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "scripts" / "a.py").write_text("x = 1\n")
    (tmp_path / "src" / "b.py").write_text("y = 2\n")
    (tmp_path / "docs" / "c.md").write_text("# hi\n")
    changed = {"scripts/a.py", "src/b.py", "docs/c.md", "scripts/gone.py", "top.py"}
    # .md dropped, missing file dropped, root-less top.py dropped
    assert final_gate._changed_python(changed) == ["scripts/a.py", "src/b.py"]


def test_fixers_only_touch_files_in_the_change_set(tmp_path, monkeypatch):
    """The churn fix: a sibling's file with pre-existing trailing whitespace is NOT
    rewritten just because the gate ran — only the changed file is."""
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", tmp_path)
    (tmp_path / "scripts").mkdir()
    mine = tmp_path / "scripts" / "mine.py"
    mine.write_text("x = 1  \n")  # trailing ws + no final newline issue
    sibling = tmp_path / "scripts" / "sibling.py"
    sibling.write_text("y = 2  ")  # trailing ws AND missing EOF newline

    ws_ok, _, ws_n = final_gate.fix_trailing_whitespace(["scripts/mine.py"])
    eof_ok, _, _ = final_gate.fix_end_of_files(["scripts/mine.py"])

    assert ws_ok and eof_ok and ws_n == 1
    assert mine.read_text() == "x = 1\n"  # my file fixed
    assert sibling.read_text() == "y = 2  "  # sibling untouched — the whole point


def test_run_formatting_fixes_is_a_noop_on_empty_change_set(tmp_path, monkeypatch):
    """Empty change set (fully-pushed clean tree) → no ruff steps run, nothing mutated."""
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", tmp_path)
    results = final_gate.run_formatting_fixes(tier=2, changed_files=set())
    names = {r[0] for r in results}
    assert "ruff-format" not in names and "ruff --fix" not in names
    assert all(passed for _, passed, _ in results)  # whitespace/eof steps no-op cleanly


def test_synced_files_excluded_from_lint_and_fix_in_consumer(tmp_path, monkeypatch):
    """A Fabrik-synced file (listed in .fabrik/synced.lock) is NOT linted or auto-fixed
    in a consumer project — reformatting a centrally-distributed file to the project's
    ruff style breaks the synced-hash check (the tojlo-mail block), and the project
    can't legally edit it. The project's OWN files are still checked."""
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", tmp_path)
    (tmp_path / "scripts" / "enforcement").mkdir(parents=True)
    (tmp_path / "scripts" / "enforcement" / "check_x.py").write_text("x = 1\n")
    (tmp_path / "scripts" / "app.py").write_text("y = 2\n")
    (tmp_path / ".fabrik").mkdir()
    (tmp_path / ".fabrik" / "synced.lock").write_text(
        '{"scripts/enforcement/check_x.py": "deadbeef"}'
    )
    changed = {"scripts/enforcement/check_x.py", "scripts/app.py"}
    # synced file dropped; the project's own file kept
    assert final_gate._changed_python(changed) == ["scripts/app.py"]
    assert final_gate._changed_text(changed) == ["scripts/app.py"]


def test_synced_paths_empty_in_hub(tmp_path, monkeypatch):
    """In the hub (/opt/fabrik) synced files ARE the source → not excluded (lint them)."""
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", final_gate._FABRIK_ROOT)
    assert final_gate._synced_paths() == set()


def _g(repo, *args):
    import subprocess

    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout


def test_a_fast_forward_onto_master_does_not_widen_the_fixer_scope(tmp_path, monkeypatch):
    """fleet 01M4EPDF7F: a worktree branch fast-forwarded onto origin/master carried 199 sibling
    commits inside `upstream...HEAD`, and a bare gate run rewrote two files no fleet commit
    touched. Only commits on NO published ref (upstream, origin/master) are this session's."""
    origin = tmp_path / "origin.git"
    _g(tmp_path, "init", "-q", "--bare", "-b", "master", str(origin))
    repo = tmp_path / "repo"
    _g(tmp_path, "clone", "-q", str(origin), str(repo))
    (repo / "base.py").write_text("x = 1\n")
    _g(repo, "add", "base.py")
    _g(repo, "commit", "-qm", "base")
    _g(repo, "push", "-q", "origin", "HEAD:master")
    _g(repo, "checkout", "-q", "-b", "work")
    _g(repo, "push", "-q", "-u", "origin", "work")  # upstream origin/work at base
    _g(repo, "checkout", "-q", "master")
    (repo / "sibling.py").write_text("y = 2  \n")
    _g(repo, "add", "sibling.py")
    _g(repo, "commit", "-qm", "sibling")
    _g(repo, "push", "-q", "origin", "master")
    _g(repo, "checkout", "-q", "work")
    _g(repo, "merge", "-q", "--ff-only", "origin/master")  # the fast-forward
    (repo / "mine.py").write_text("z = 3  \n")
    _g(repo, "add", "mine.py")
    _g(repo, "commit", "-qm", "mine")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", repo)
    assert final_gate.get_writable_files() == {"mine.py"}
    assert "sibling.py" not in final_gate.get_changed_files()


def test_trailing_whitespace_fix_keeps_unicode_line_separators(tmp_path, monkeypatch):
    """fleet 01M4EPDF7F: `str.splitlines()` splits on U+2028 and `rstrip()` strips it, so the
    fixer deleted the U+2028 a test case exists to carry (`delta<U+2028>confirmed`). Trailing
    whitespace is ASCII space and tab before a `\\n`; nothing else."""
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", tmp_path)
    f = tmp_path / "t.py"
    body = "a = 'delta\u2028confirmed'  \nb = 'nb\u00a0'\nc = 1\t\r\nd = 2"
    f.write_text(body, encoding="utf-8")
    ok, _, n = final_gate.fix_trailing_whitespace(["t.py"])
    assert ok and n == 1
    raw = f.read_bytes().decode("utf-8")  # read_text() would translate the "\r\n" it checks
    assert raw == "a = 'delta\u2028confirmed'\nb = 'nb\u00a0'\nc = 1\r\nd = 2"


def test_the_eof_fixer_keeps_a_crlf_file_crlf(tmp_path, monkeypatch):
    """Same read-translation defect in fix_end_of_files: a CRLF file missing its final newline
    came back with every line ending rewritten to LF."""
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", tmp_path)
    f = tmp_path / "w.txt"
    f.write_bytes(b"a\r\nb")
    ok, _, n = final_gate.fix_end_of_files(["w.txt"])
    assert ok and n == 1
    assert f.read_bytes() == b"a\r\nb\r\n"


def test_the_fixers_handle_bare_cr_line_endings(tmp_path, monkeypatch):
    """Review A-S1/A-H2: a `\\n`-only split made a classic-Mac CR file one line (inner trailing
    spaces kept), and the EOF fixer appended `\\n` to a CR-only file."""
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", tmp_path)
    f = tmp_path / "mac.txt"
    f.write_bytes(b"a  \rb\t\rc  \r\nd")
    assert final_gate.fix_trailing_whitespace(["mac.txt"])[2] == 1
    assert f.read_bytes() == b"a\rb\rc\r\nd"
    g = tmp_path / "cr.txt"
    g.write_bytes(b"x\ry")
    assert final_gate.fix_end_of_files(["cr.txt"])[2] == 1
    assert g.read_bytes() == b"x\ry\r"


def test_a_file_added_then_removed_in_own_commits_is_not_in_scope(tmp_path, monkeypatch):
    """Review A-S2: the scope is the session's NET change — a file its own commits created and
    deleted again is not part of what it will publish."""
    origin = tmp_path / "origin.git"
    _g(tmp_path, "init", "-q", "--bare", "-b", "master", str(origin))
    repo = tmp_path / "repo"
    _g(tmp_path, "clone", "-q", str(origin), str(repo))
    (repo / "base.py").write_text("x = 1\n")
    _g(repo, "add", "base.py")
    _g(repo, "commit", "-qm", "base")
    _g(repo, "push", "-q", "origin", "HEAD:master")
    (repo / "tmp.py").write_text("t = 1\n")
    _g(repo, "add", "tmp.py")
    _g(repo, "commit", "-qm", "add tmp")
    _g(repo, "rm", "-q", "tmp.py")
    _g(repo, "commit", "-qm", "drop tmp")
    (repo / "mine.py").write_text("m = 1\n")
    _g(repo, "add", "mine.py")
    _g(repo, "commit", "-qm", "mine")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", repo)
    assert final_gate.get_writable_files() == {"mine.py"}


def test_a_git_that_refuses_the_log_falls_back_to_the_diff_base(tmp_path, monkeypatch):
    """Review A-S3: a git without `--diff-merges=remerge` must not silently empty the scope."""
    real = final_gate.run_cmd

    def old_git(cmd, *a, **k):
        if cmd and "--diff-merges=remerge" in cmd:
            return 129, "error: unknown option"
        return real(cmd, *a, **k)

    origin = tmp_path / "origin.git"
    _g(tmp_path, "init", "-q", "--bare", "-b", "master", str(origin))
    repo = tmp_path / "repo"
    _g(tmp_path, "clone", "-q", str(origin), str(repo))
    (repo / "base.py").write_text("x = 1\n")
    _g(repo, "add", "base.py")
    _g(repo, "commit", "-qm", "base")
    _g(repo, "push", "-q", "origin", "HEAD:master")
    (repo / "mine.py").write_text("m = 1\n")
    _g(repo, "add", "mine.py")
    _g(repo, "commit", "-qm", "mine")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", repo)
    monkeypatch.setattr(final_gate, "run_cmd", old_git)
    assert final_gate.get_writable_files() == {"mine.py"}


def _published_repo(tmp_path):
    origin = tmp_path / "origin.git"
    _g(tmp_path, "init", "-q", "--bare", "-b", "master", str(origin))
    repo = tmp_path / "repo"
    _g(tmp_path, "clone", "-q", str(origin), str(repo))
    (repo / "worker").mkdir()
    (repo / "worker" / "old.py").write_text("x=1\n")  # pre-existing format debt
    _g(repo, "add", "worker/old.py")
    _g(repo, "commit", "-qm", "base")
    _g(repo, "push", "-q", "origin", "HEAD:master")
    return repo


def test_a_python_file_added_outside_the_lint_roots_is_selected(tmp_path, monkeypatch):
    """fleet 01M4F5F2WM: a file-worker's worker/*.py was never ruffed. A file the session ADDS
    carries no debt, so it gets the roots' treatment; a modified pre-existing file does not
    (its lint stays the repo-wide ratchet's)."""
    repo = _published_repo(tmp_path)
    (repo / "worker" / "new.py").write_text("y=2\n")
    (repo / "worker" / "old.py").write_text("x=3\n")
    _g(repo, "add", "worker/new.py", "worker/old.py")
    _g(repo, "commit", "-qm", "add new, edit old")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", repo)
    assert final_gate._changed_python({"worker/new.py", "worker/old.py"}) == ["worker/new.py"]
    (repo / "worker" / "staged.py").write_text("z=1\n")
    _g(repo, "add", "worker/staged.py")
    assert "worker/staged.py" in final_gate._changed_python({"worker/staged.py"})


def test_every_ruff_leg_honours_the_repos_exclude(tmp_path, monkeypatch):
    """A file named on the ruff command line bypasses `[tool.ruff] exclude` unless
    `--force-exclude` is passed (executed by both design critiques)."""
    repo = _published_repo(tmp_path)
    (repo / "pyproject.toml").write_text('[tool.ruff]\nextend-exclude = ["gen"]\n')
    (repo / "gen").mkdir()
    (repo / "gen" / "x.py").write_text("import os\nx=1\n")
    _g(repo, "add", "pyproject.toml", "gen/x.py")
    _g(repo, "commit", "-qm", "generated")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", repo)
    rows = final_gate.run_format_check({"gen/x.py"})
    assert all(ok for _, ok, _ in rows), rows
    seen = []
    real = final_gate.run_cmd

    def spy(cmd, *a, **k):
        if cmd and cmd[0] == final_gate.RUFF:
            seen.append(cmd)
        return real(cmd, *a, **k)

    monkeypatch.setattr(final_gate, "run_cmd", spy)
    final_gate.run_formatting_fixes(tier=2, changed_files={"gen/x.py"})
    assert seen and all("--force-exclude" in c for c in seen), seen
    assert (repo / "gen" / "x.py").read_text() == "import os\nx=1\n"  # never reformatted


def test_a_file_moved_out_of_the_lint_roots_stays_ruffed(tmp_path, monkeypatch):
    """Review A-S1: `scripts/x.py -> worker/x.py` (status R) silently left every ruff leg; a
    rename whose source was under the roots keeps its coverage. A rename of a flat-layout file
    adds no new enforcement, and an intent-to-add (`git add -N`) new file counts as added."""
    repo = _published_repo(tmp_path)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "tool.py").write_text("t = 1\n")
    _g(repo, "add", "scripts/tool.py")
    _g(repo, "commit", "-qm", "tool")
    _g(repo, "push", "-q", "origin", "HEAD:master")
    _g(repo, "mv", "scripts/tool.py", "worker/tool.py")
    _g(repo, "mv", "worker/old.py", "worker/older.py")
    (repo / "worker" / "ita.py").write_text("i=1\n")
    _g(repo, "add", "-N", "worker/ita.py")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", repo)
    got = final_gate._changed_python({"worker/tool.py", "worker/older.py", "worker/ita.py"})
    assert got == ["worker/ita.py", "worker/tool.py"]


def test_a_leg_whose_every_file_is_excluded_says_it_did_not_run(tmp_path, monkeypatch):
    """Review A-S2: with every file excluded by the repo's ruff config, a plain PASS asserted a
    check that never ran; the row carries a `(NOT RUN` skip marker instead."""
    repo = _published_repo(tmp_path)
    (repo / "pyproject.toml").write_text('[tool.ruff]\nextend-exclude = ["gen"]\n')
    (repo / "gen").mkdir()
    (repo / "gen" / "x.py").write_text("x = 1\n")
    _g(repo, "add", "pyproject.toml", "gen/x.py")
    _g(repo, "commit", "-qm", "generated")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", repo)
    names = [n for n, ok, _ in final_gate.run_format_check({"gen/x.py"}) if ok]
    assert any("(NOT RUN" in n for n in names), names


def test_an_added_file_with_a_quoted_name_is_read_verbatim(tmp_path, monkeypatch):
    """Review A-S4: `--name-status` C-quotes a path holding a quote, tab or non-ASCII byte, so a
    tab-split stored the escaped text; `-z` gives git's own bytes."""
    repo = _published_repo(tmp_path)
    name = 'worker/we"ird ü.py'
    (repo / name).write_text("q = 1\n")
    _g(repo, "add", name)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", repo)
    assert name in final_gate._added_files()
