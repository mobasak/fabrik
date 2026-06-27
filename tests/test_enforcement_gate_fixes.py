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
