"""The `# AFTER-EDIT:` coupling header must be parsed in BOTH separator styles.

WHY. The corpus writes the coupled-file list two ways — `a.py, b.md` and `a.py | b.md` — and the
check split on `[,\\s]+` only. Every pipe therefore parsed as a coupled FILE named `|`, which is
never staged, so every script using the majority `scripts/sysadmin/` style warned on its own edit:

    liveness_audit.py: `# AFTER-EDIT:` lists coupled file(s) not updated in this change:
    |, |, .fabrik/liveness-registry.json, |, scripts/sysadmin/kaizen_metrics.py, |.

The bug is old; it was invisible because the check was registered with neither `advisory=` nor
`warn_only=`, so `run_optional_check` DISCARDED its stdout on exit 0. Declaring the row advisory
(2026-08-16) surfaced it on the first run — which is the argument for making a warn-only row
visible rather than leaving it silently green.

These tests drive `main()` against a throwaway git repo, so they exercise the real staged-diff
path, not a re-implementation of it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECK = REPO_ROOT / "scripts" / "enforcement" / "check_script_headers.py"


def _repo(tmp_path: Path, script_body: str) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for cfg in (("user.email", "t@fabrik.local"), ("user.name", "t")):
        subprocess.run(["git", "-C", str(tmp_path), "config", *cfg], check=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "thing.py").write_text(script_body, encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "coupled.md").write_text("# coupled\n", encoding="utf-8")
    return tmp_path


def _run(cwd: Path, *stage: str) -> str:
    subprocess.run(["git", "-C", str(cwd), "add", *stage], check=True)
    proc = subprocess.run(
        [sys.executable, str(CHECK)], cwd=cwd, capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, "WARN-only by contract — it must never block"
    return proc.stdout + proc.stderr


@pytest.mark.parametrize(
    "header",
    [
        "# AFTER-EDIT: docs/coupled.md, docs/other.md",
        "# AFTER-EDIT: docs/coupled.md | docs/other.md",
        "# AFTER-EDIT: docs/coupled.md|docs/other.md",
    ],
)
def test_a_pipe_separator_is_not_a_filename(tmp_path: Path, header: str) -> None:
    """Only the genuinely-unstaged `docs/other.md` may be named — never a bare `|`."""
    out = _run(_repo(tmp_path, f"{header}\nx = 1\n"), "scripts/thing.py", "docs/coupled.md")
    assert "docs/other.md" in out, "the real unstaged coupled file must still be reported"
    assert "|" not in out.replace(header, ""), f"a separator was parsed as a filename: {out}"


def test_every_coupled_file_staged_warns_about_nothing(tmp_path: Path) -> None:
    """The liveness_audit.py case: a pipe-separated header, all coupled files staged."""
    repo = _repo(tmp_path, "# AFTER-EDIT: docs/coupled.md | docs/coupled.md\nx = 1\n")
    out = _run(repo, "scripts/thing.py", "docs/coupled.md")
    assert "WARNING" not in out, f"a fully-satisfied pipe header must be silent, got: {out}"


def test_a_missing_header_is_still_warned(tmp_path: Path) -> None:
    """The rule the check exists for — untouched by the separator fix."""
    out = _run(_repo(tmp_path, "x = 1\n"), "scripts/thing.py")
    assert "no `# AFTER-EDIT:` header" in out


# ── the denominator: a silent pass is indistinguishable from a check that never ran ──────


def test_the_clean_path_states_how_many_scripts_it_inspected(tmp_path: Path) -> None:
    """A "0 findings" verdict must say how many subjects it examined.

    Reported by web-ecommerce-factory (01M1E6S1EAK7DNP74C1K9YHP3Z): running this check bare
    produced NO output at all, so a genuine pass and a no-op looked identical. Their diagnosis of
    the trigger was off — their scripts were modified-UNSTAGED and this check is staged-scoped by
    design — but the defect is real and is the silent-green class: three different outcomes
    (nothing staged, no scripts staged, everything clean) all printed nothing.
    """
    repo = _repo(tmp_path, "# AFTER-EDIT: docs/coupled.md\nx = 1\n")
    out = _run(repo, "scripts/thing.py", "docs/coupled.md")
    assert "WARNING" not in out, f"this fixture is clean by construction, got: {out}"
    assert "1 staged script(s) inspected" in out, (
        f"the clean path must state its denominator, got: {out!r}"
    )


def test_nothing_staged_says_so_rather_than_exiting_mute(tmp_path: Path) -> None:
    """The early-return path — the shape the bare run in the report actually hit."""
    repo = _repo(tmp_path, "# AFTER-EDIT: none\nx = 1\n")
    out = _run(repo)  # stage nothing at all
    assert "nothing staged" in out, f"an empty index must be explained, not silent: {out!r}"
    assert "staged-scoped" in out, "it must name WHY it inspected nothing"


def test_staged_non_scripts_are_counted_honestly(tmp_path: Path) -> None:
    """Staging only a doc: the index is non-empty but zero SCRIPTS were inspected — the count
    must reflect the scripts, not the staged files, or the line would overstate its own sweep."""
    repo = _repo(tmp_path, "# AFTER-EDIT: none\nx = 1\n")
    out = _run(repo, "docs/coupled.md")
    assert "0 staged script(s) inspected" in out, f"expected an honest zero, got: {out!r}"


def test_quiet_suppresses_the_denominator_but_never_a_warning(tmp_path: Path) -> None:
    """`--quiet` is the GATE's flag; warnings must survive it or the check would go silent-green.

    The denominator lines were first shipped unconditionally, which put a content-free row under
    `[ADVISORY] Script Coupling Header` on every green gate — in human mode AND in `--json`,
    because this check is registered warn_only=True and the `advisory` array applies no ⚠ filter
    (only `warnings` does). Confirmed live on the fleet copies before the fix. The flag must
    suppress ONLY the clean-path chatter.
    """
    repo = _repo(tmp_path, "# AFTER-EDIT: docs/coupled.md\nx = 1\n")
    subprocess.run(
        ["git", "-C", str(repo), "add", "scripts/thing.py", "docs/coupled.md"], check=True
    )
    quiet = subprocess.run(
        [sys.executable, str(CHECK), "--quiet"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert quiet.returncode == 0
    assert quiet.stdout.strip() == "", (
        f"--quiet must print nothing on a clean run: {quiet.stdout!r}"
    )

    # ...but a real WARNING still speaks under --quiet.
    repo2 = _repo(tmp_path / "b", "x = 1\n")  # no AFTER-EDIT header at all
    subprocess.run(["git", "-C", str(repo2), "add", "scripts/thing.py"], check=True)
    warned = subprocess.run(
        [sys.executable, str(CHECK), "--quiet"],
        cwd=repo2,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "no `# AFTER-EDIT:` header" in warned.stdout, (
        f"--quiet silenced a real finding — that is silent-green: {warned.stdout!r}"
    )


@pytest.mark.parametrize(
    "header",
    [
        "# AFTER-EDIT: docs/coupled.md | none",
        "# AFTER-EDIT: docs/coupled.md | (none)",
        "# AFTER-EDIT: docs/coupled.md · scripts/thing.py (§ fix-first) | none",
    ],
)
def test_the_none_sentinel_and_prose_tokens_are_never_coupled_files(
    tmp_path: Path, header: str
) -> None:
    """The mandated `<files | none>` sentinel split into a phantom coupled file named `none` — an
    unclosable WARN on 27 of 106 inspectable hub headers; `(none)`, a `·` and prose words were the
    same class through other doors (10 more). A coupled file has a path shape (DU2/DW2)."""
    repo = _repo(tmp_path, f"{header}\nprint('x')\n")
    out = _run(repo, "scripts/thing.py", "docs/coupled.md")
    assert "WARNING" not in out, out


def test_an_unreadable_staged_script_is_a_warning_not_a_traceback(tmp_path: Path) -> None:
    """A staged path that exists but cannot be read raised out of `main` — a non-zero exit that
    FAILS a warn-only gate naming the wrong cause (DW2)."""
    import os

    repo = _repo(tmp_path, "# AFTER-EDIT: docs/coupled.md\nprint('x')\n")
    subprocess.run(
        ["git", "-C", str(repo), "add", "scripts/thing.py", "docs/coupled.md"], check=True
    )
    (repo / "scripts" / "thing.py").chmod(0)
    try:
        if os.access(repo / "scripts" / "thing.py", os.R_OK):
            pytest.skip("running as root — permissions are not enforced")
        proc = subprocess.run(
            [sys.executable, str(CHECK)], cwd=repo, capture_output=True, text=True, timeout=60
        )
    finally:
        (repo / "scripts" / "thing.py").chmod(0o644)
    assert proc.returncode == 0 and "cannot read the header" in proc.stdout + proc.stderr, (
        proc.stdout + proc.stderr
    )
