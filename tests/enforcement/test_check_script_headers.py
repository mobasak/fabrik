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


def test_a_slashless_dotted_coupled_file_is_still_enforced(tmp_path: Path) -> None:
    """The `.` half of the path-shape rule guards precisely the Doc Sync Matrix files
    (`CHANGELOG.md`, `INDEX.md`, `CLAUDE.md`, `PORTS.md`, `.env.example` — 17 of 217 hub tokens);
    it was ungraded (DY2)."""
    # the file is deliberately NOT on disk: an existing file is coupled by `exists()` whatever
    # its shape, so only a missing dotted name isolates the `.` half (sandbox R6c, pass 47)
    repo = _repo(tmp_path, "# AFTER-EDIT: CHANGELOG.md\nprint('x')\n")
    out = _run(repo, "scripts/thing.py")
    assert "WARNING" in out and "CHANGELOG.md" in out, out


@pytest.mark.parametrize(
    ("header", "extra", "stage"),
    [
        # script-relative: `tests/test_thing.py` beside scripts/thing.py
        (
            "# AFTER-EDIT: tests/test_thing.py",
            "scripts/tests/test_thing.py",
            "scripts/tests/test_thing.py",
        ),
        # a glob
        ("# AFTER-EDIT: docs/**", None, "docs/coupled.md"),
        # a directory (trailing slash)
        ("# AFTER-EDIT: docs/", None, "docs/coupled.md"),
        # `n/a` carries a `/` but is a sentinel, never a file
        ("# AFTER-EDIT: docs/coupled.md, n/a", None, "docs/coupled.md"),
    ],
)
def test_script_relative_glob_directory_and_sentinel_tokens_can_be_closed(
    tmp_path: Path, header: str, extra: str | None, stage: str
) -> None:
    """8 of 106 hub headers named a coupled file the check could never see staged — a name
    relative to the script's own directory, a glob, a directory — so their WARN was unclosable by
    any staging action (DY2); and `n/a` (a `/`) must stay a sentinel."""
    repo = _repo(tmp_path, f"{header}\nprint('x')\n")
    if extra:
        (repo / extra).parent.mkdir(parents=True, exist_ok=True)
        (repo / extra).write_text("# t\n", encoding="utf-8")
    out = _run(repo, "scripts/thing.py", stage)
    assert "WARNING" not in out, out


def test_an_extension_less_file_that_exists_is_a_coupled_file(tmp_path: Path) -> None:
    """`Makefile` / `Dockerfile` have no path shape; a token that EXISTS on disk names a file
    whatever its spelling — the drop stays for prose only (DY2)."""
    repo = _repo(tmp_path, "# AFTER-EDIT: Makefile\nprint('x')\n")
    (repo / "Makefile").write_text("all:\n", encoding="utf-8")
    out = _run(repo, "scripts/thing.py")
    assert "WARNING" in out and "Makefile" in out, out


def test_a_dangling_symlink_is_named(tmp_path: Path) -> None:
    """A dangling symlink fails `exists()` and used to fall through the staged-deletion branch —
    warned about nowhere (DY2); the counter placement is graded by the deletion test below."""
    repo = _repo(tmp_path, "# AFTER-EDIT: none\n")
    (repo / "scripts" / "dead.py").symlink_to("/nonexistent/target")
    out = _run(repo, "scripts/dead.py")
    assert "WARNING: scripts/dead.py: dangling symlink" in out, out


def test_the_clean_line_counts_scripts_read_not_scripts_collected(tmp_path: Path) -> None:
    """A staged deletion is collected, never read: `1 staged script(s) inspected` for 0 read was
    the collected-vs-attempted overstatement (DY2)."""
    repo = _repo(tmp_path, "# AFTER-EDIT: none\n")
    _run(repo, "scripts/thing.py")
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
    subprocess.run(["git", "-C", str(repo), "rm", "-q", "scripts/thing.py"], check=True)
    proc = subprocess.run(
        [sys.executable, str(CHECK)], cwd=repo, capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0 and "0 of 1 staged script(s) inspected" in proc.stdout, proc.stdout


def test_a_same_named_file_in_the_script_directory_never_closes_a_root_coupling(
    tmp_path: Path,
) -> None:
    """`# AFTER-EDIT: README.md` on scripts/thing.py means the ROOT file; staging
    `scripts/README.md` beside the script must not satisfy it (EA2 — the script-relative reading
    applies only when the repo-rooted path does not exist)."""
    repo = _repo(tmp_path, "# AFTER-EDIT: README.md\nprint('x')\n")
    (repo / "README.md").write_text("# root\n", encoding="utf-8")
    (repo / "scripts" / "README.md").write_text("# local\n", encoding="utf-8")
    out = _run(repo, "scripts/thing.py", "scripts/README.md")
    assert "WARNING" in out and "README.md" in out, out


def test_a_glob_token_is_a_coupled_file_when_nothing_matches_it(tmp_path: Path) -> None:
    """The inclusion half: a glob nobody staged under must WARN — dropping glob tokens as prose
    passed the satisfied-path case just as well (pass 48)."""
    repo = _repo(tmp_path, "# AFTER-EDIT: docs/**\nprint('x')\n")
    out = _run(repo, "scripts/thing.py")
    assert "WARNING" in out and "docs/**" in out, out


def test_a_glob_matching_only_the_script_itself_is_not_satisfied(tmp_path: Path) -> None:
    """`scripts/**` staged with the script alone matched the script — a coupling that could never
    fire (EA2)."""
    repo = _repo(tmp_path, "# AFTER-EDIT: scripts/**\nprint('x')\n")
    out = _run(repo, "scripts/thing.py")
    assert "WARNING" in out and "scripts/**" in out, out


def test_a_script_relative_directory_token_keeps_its_slash(tmp_path: Path) -> None:
    """`as_posix()` dropped the trailing `/`, so a script-relative directory token could never be
    closed (EA2)."""
    repo = _repo(tmp_path, "# AFTER-EDIT: fixtures/\nprint('x')\n")
    (repo / "scripts" / "fixtures").mkdir()
    (repo / "scripts" / "fixtures" / "golden.json").write_text("{}\n", encoding="utf-8")
    out = _run(repo, "scripts/thing.py", "scripts/fixtures/golden.json")
    assert "WARNING" not in out, out


def test_a_prose_word_naming_a_directory_is_not_a_coupled_file(tmp_path: Path) -> None:
    """`docs` exists as a DIRECTORY in every repo; a prose token equal to it must not be promoted
    to a phantom coupled file by the exists() rule (EA2 — files only)."""
    repo = _repo(tmp_path, "# AFTER-EDIT: docs/coupled.md (and docs of the callers)\nprint('x')\n")
    out = _run(repo, "scripts/thing.py", "docs/coupled.md")
    assert "WARNING" not in out, out
