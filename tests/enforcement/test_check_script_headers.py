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
    for cfg in (
        ("user.email", "t@fabrik.local"),
        ("user.name", "t"),
        (
            "commit.gpgsign",
            "false",
        ),  # the operator's ~/.gitconfig is not scrubbed by conftest (L-C5)
        ("core.hooksPath", str(tmp_path / "no-hooks")),
    ):
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
    assert "0 of 0 staged script(s) inspected" in out, (
        out
    )  # the same `N of M` shape as the clean line (pass 49)


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


def test_a_listed_path_without_a_stage_zero_blob_is_skipped_never_read_from_the_worktree(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """The header is read from the STAGED blob (EQ2); a listed path with NO stage-0 blob — a
    `git rm --cached` deletion with the file still on disk, an unresolved merge — is skipped
    with a line saying so. The old fallback read the WORKING TREE and reported the file
    "inspected" (an unreadable one was a WARN — DW2); that content is not what will be
    committed (EW1). In-process: the blob lookup is patched out so the branch is the one
    under test; the file is unreadable to prove it is never opened."""
    import importlib.util
    import os

    spec = importlib.util.spec_from_file_location("check_script_headers_under_test", CHECK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    repo = _repo(tmp_path, "# AFTER-EDIT: docs/coupled.md\nprint('x')\n")
    (repo / "scripts" / "thing.py").chmod(0)
    if os.access(repo / "scripts" / "thing.py", os.R_OK):
        pytest.skip("running as root — permissions are not enforced")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(mod, "_git", lambda args, sep="\n": ["scripts/thing.py", "docs/coupled.md"])
    monkeypatch.setattr(mod, "_staged_head", lambda path: None)
    try:
        assert mod.main() == 0
    finally:
        (repo / "scripts" / "thing.py").chmod(0o644)
    out = capsys.readouterr().out
    assert "staged deletion or unresolved merge — not checked" in out, out
    assert "cannot read" not in out and "inspected" not in out.replace("0 of 1", ""), out


def test_a_git_rm_cached_script_still_on_disk_is_not_inspected(tmp_path: Path) -> None:
    """`git rm --cached` lists the path in `--cached --name-only` with the file on disk and no
    index blob: the worktree header must not be validated as if it were about to be committed (EW1)."""
    repo = _repo(tmp_path, "# AFTER-EDIT: docs/coupled.md\nprint('x')\n")
    subprocess.run(["git", "-C", str(repo), "add", "scripts/thing.py"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.email=t@x",
            "-c",
            "user.name=t",
            "commit",
            "-qm",
            "base",
        ],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo), "rm", "-q", "--cached", "scripts/thing.py"], check=True)
    out = subprocess.run(
        [sys.executable, str(CHECK)], cwd=repo, capture_output=True, text=True, timeout=60
    )
    assert out.returncode == 0
    assert "staged deletion or unresolved merge — not checked" in out.stdout + out.stderr, (
        out.stdout
    )


def test_a_tab_in_a_staged_path_is_still_seen(tmp_path: Path) -> None:
    """`core.quotepath=false` still C-quotes a tab, a backslash or a `"`; `-z` never quotes (EW1)."""
    repo = _repo(tmp_path, "x = 1\n")
    (repo / "scripts" / "wei\trd.py").write_text("x = 1\n", encoding="utf-8")
    out = _run(repo, "scripts/thing.py", "scripts/wei\trd.py")
    assert "scripts/wei\trd.py: no `# AFTER-EDIT:` header" in out, out


def test_a_git_that_does_not_answer_is_a_warning_and_exit_zero(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """A 20 s timeout behind a sibling's `index.lock` raised `TimeoutExpired` out of the check —
    a traceback and exit 1, which the gate counts as a FAILURE of a warn-only check (EW1)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_script_headers_under_test", CHECK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def slow(*a, **k):
        raise subprocess.TimeoutExpired(cmd=a[0], timeout=20)

    monkeypatch.setattr(mod.subprocess, "run", slow)
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert "git did not answer" in out and "not checked" in out, out


def test_a_git_that_answers_with_a_failure_is_the_same_warning_never_nothing_staged(
    tmp_path: Path,
) -> None:
    """A corrupt index (or a cwd inside `.git/`, or no work tree) made git exit 128 with EMPTY
    stdout, which `_git` read as "nothing staged" — a convincing green for a check that could
    not ask its question (EY1). Real git, real corruption."""
    repo = _repo(tmp_path, "x = 1\n")
    subprocess.run(["git", "-C", str(repo), "add", "scripts/thing.py"], check=True)
    (repo / ".git" / "index").write_text("garbage", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(CHECK)], cwd=repo, capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout + proc.stderr
    assert "nothing staged" not in out and "git" in out and "not checked" in out, out
    # from inside .git/: rev-parse fails while diff would answer — the same WARN, never a clean 0-of-N
    repo2 = _repo(tmp_path / "two", "x = 1\n")
    subprocess.run(["git", "-C", str(repo2), "add", "scripts/thing.py"], check=True)
    proc2 = subprocess.run(
        [sys.executable, str(CHECK)], cwd=repo2 / ".git", capture_output=True, text=True, timeout=60
    )
    out2 = proc2.stdout + proc2.stderr
    assert proc2.returncode == 0 and "0 of 1" not in out2 and "not checked" in out2, out2


def test_a_git_show_that_fails_structurally_is_not_a_deletion(monkeypatch) -> None:
    """`git show :path` exits non-zero for a corrupt index too; only the no-stage-0-blob messages
    mean "nothing to commit here" — anything else is git failing (EY1)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_script_headers_under_test", CHECK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class _P:
        returncode = 128
        stdout = b""
        stderr = b"fatal: .git/index: index file smaller than expected"

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: _P())
    with pytest.raises(mod.GitUnavailableError):
        mod._staged_head("scripts/thing.py")
    _P.returncode, _P.stdout, _P.stderr = (
        0,
        b":scripts/thing.py missing\n",
        b"",
    )  # cat-file's own "no stage-0 blob" answer (EZ6)
    assert mod._staged_head("scripts/thing.py") is None


def test_a_symlinked_script_is_not_inspected_as_its_link_text(tmp_path: Path) -> None:
    """The staged blob of a symlink is the link text; the check tokenized it as a script head
    and warned "no header" on every stage of the hub's one symlinked script. A symlink is
    skipped with a line; its target is inspected on its own (EY1)."""
    repo = _repo(tmp_path, "# AFTER-EDIT: none\nx = 1\n")
    (repo / "scripts" / "link.py").symlink_to(repo / "scripts" / "thing.py")
    out = _run(repo, "scripts/thing.py", "scripts/link.py")
    assert "scripts/link.py: symlink — not checked" in out, out
    assert "scripts/link.py: no `# AFTER-EDIT:`" not in out, out


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


def test_a_question_mark_glob_is_a_glob(tmp_path: Path) -> None:
    """`?` and `[` are glob characters too; only `*` was recognised, so `docs/coupled.m?` was a
    literal that nothing could satisfy (pass 49)."""
    repo = _repo(tmp_path, "# AFTER-EDIT: docs/coupled.m?\nprint('x')\n")
    out = _run(repo, "scripts/thing.py", "docs/coupled.md")
    assert "WARNING" not in out, out


def test_a_docstring_example_is_not_a_header(tmp_path: Path) -> None:
    """A script whose docstring QUOTES the convention (as this check's own does) but declares
    no header: the missing-header WARN must fire, and no coupling must be invented from the
    example (EQ2)."""
    repo = _repo(
        tmp_path,
        '"""Usage: put a `# AFTER-EDIT: docs/coupled.md` line at the top."""\nprint("x")\n',
    )
    out = _run(repo, "scripts/thing.py")
    assert "no `# AFTER-EDIT:` header" in out, out
    assert "docs/coupled.md" not in out, out
    repo2 = _repo(
        tmp_path / "two",
        "# AFTER-EDIT: none\n" + '"""Example: `# AFTER-EDIT: docs/coupled.md`."""\n',
    )
    assert "WARNING" not in _run(repo2, "scripts/thing.py")


def test_the_staged_blob_is_read_never_the_working_tree(tmp_path: Path) -> None:
    """What is about to be COMMITTED is the index blob: a header added in the working tree after
    `git add` must not satisfy the check, and a header removed after `git add` must not fail it
    (EQ2)."""
    repo = _repo(tmp_path, "x = 1\n")
    subprocess.run(["git", "-C", str(repo), "add", "scripts/thing.py"], check=True)
    (repo / "scripts" / "thing.py").write_text("# AFTER-EDIT: none\nx = 1\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(CHECK)], cwd=repo, capture_output=True, text=True, timeout=60
    )
    assert "no `# AFTER-EDIT:` header" in proc.stdout, proc.stdout  # the staged blob has none
    subprocess.run(["git", "-C", str(repo), "add", "scripts/thing.py"], check=True)
    (repo / "scripts" / "thing.py").write_text("x = 1\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(CHECK)], cwd=repo, capture_output=True, text=True, timeout=60
    )
    assert "WARNING" not in proc.stdout, proc.stdout  # the staged blob has one


def test_a_script_whose_name_contains_test_is_inspected(tmp_path: Path) -> None:
    """`check_test_proposal.py` is a real, registered enforcement script; a substring skip on
    `test_` hid it (and 22 other headered scripts) from the check for as long as it existed —
    the skip is by path segment (EQ2)."""
    repo = _repo(tmp_path, "# AFTER-EDIT: none\n")
    (repo / "scripts" / "check_test_proposal.py").write_text("x = 1\n", encoding="utf-8")
    out = _run(repo, "scripts/check_test_proposal.py")
    assert "no `# AFTER-EDIT:` header" in out and "check_test_proposal.py" in out, out
    (repo / "scripts" / "tests").mkdir()
    (repo / "scripts" / "tests" / "helper.py").write_text("x = 1\n", encoding="utf-8")
    assert "helper.py" not in _run(repo, "scripts/tests/helper.py")


def test_a_header_beyond_the_scan_window_is_no_header(tmp_path: Path) -> None:
    """The declaration belongs in the first HEADER_SCAN_LINES lines; one on line 30 is not seen
    — the window constant is load-bearing (EQ2)."""
    repo = _repo(tmp_path, "x = 1\n" * 29 + "# AFTER-EDIT: none\n")
    assert "no `# AFTER-EDIT:` header" in _run(repo, "scripts/thing.py")


def test_a_docstring_example_inside_an_unterminated_string_is_not_a_header(tmp_path: Path) -> None:
    """The head is cut at HEADER_SCAN_LINES; a long docstring quoting the convention is
    UNTERMINATED in the head, so tokenize raises before any COMMENT token — the except branch
    must stop, never fall back to a text search that would harvest the example (ES2)."""
    body = (  # the example is INSIDE the 25-line head; the string closes outside it
        '"""Usage:\n'
        + "put a `# AFTER-EDIT: docs/coupled.md` line at the top.\n"
        + "\n" * 30
        + '"""\nprint("x")\n'
    )
    repo = _repo(tmp_path, body)
    out = _run(repo, "scripts/thing.py")
    assert "no `# AFTER-EDIT:` header" in out and "docs/coupled.md" not in out, out


def test_the_scan_window_boundary_is_exact(tmp_path: Path) -> None:
    """A header on line 25 is seen, one on line 26 is not — the constant is 25, not about 25 (ES2)."""
    repo = _repo(tmp_path, "x = 1\n" * 24 + "# AFTER-EDIT: none\n")
    assert "WARNING" not in _run(repo, "scripts/thing.py")
    repo2 = _repo(tmp_path / "two", "x = 1\n" * 25 + "# AFTER-EDIT: none\n")
    assert "no `# AFTER-EDIT:` header" in _run(repo2, "scripts/thing.py")


def test_a_conftest_outside_a_tests_directory_is_inspected(tmp_path: Path) -> None:
    """The skip is by segment: `conftest.py` beside real scripts is a real script (ES2)."""
    repo = _repo(tmp_path, "# AFTER-EDIT: none\n")
    (repo / "scripts" / "conftest.py").write_text("x = 1\n", encoding="utf-8")
    assert "conftest.py" in _run(repo, "scripts/conftest.py")


def test_a_non_ascii_script_path_is_inspected_and_a_non_ascii_coupled_file_counts(
    tmp_path: Path,
) -> None:
    """git C-quotes a path with a non-ASCII byte under its default `core.quotepath`; the quoted
    form matched neither `scripts/` nor the staged set, so a headerless `scripts/naïve.py` was a
    clean 0-of-0 and a staged `docs/cöupled.md` was "not updated" forever (EU1)."""
    repo = _repo(tmp_path, "# AFTER-EDIT: docs/cöupled.md\nx = 1\n")
    (repo / "scripts" / "naïve.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "docs" / "cöupled.md").write_text("# c\n", encoding="utf-8")
    out = _run(repo, "scripts/thing.py", "scripts/naïve.py", "docs/cöupled.md")
    assert "scripts/naïve.py: no `# AFTER-EDIT:` header" in out, out
    assert "not updated" not in out, (
        out
    )  # the staged `docs/cöupled.md` satisfies thing.py's coupling


def test_a_bare_run_from_a_subdirectory_sees_the_staged_scripts(tmp_path: Path) -> None:
    """Staged paths are repo-root-relative whatever the cwd; run from `scripts/`, every real
    script read as "a staged deletion" and the run printed a clean `0 of 1` (EU1)."""
    repo = _repo(tmp_path, "x = 1\n")
    subprocess.run(["git", "-C", str(repo), "add", "scripts/thing.py"], check=True)
    proc = subprocess.run(
        [sys.executable, str(CHECK)],
        cwd=repo / "scripts",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0
    out = proc.stdout + proc.stderr
    assert "scripts/thing.py: no `# AFTER-EDIT:` header" in out, out


def test_a_sentinel_with_a_full_stop_is_still_the_sentinel(tmp_path: Path) -> None:
    """`# AFTER-EDIT: none.` — the period promoted `none.` to a coupled FILE (a `.` is a path
    shape), a false WARN on every edit forever (EY2)."""
    repo = _repo(tmp_path, "# AFTER-EDIT: none.\nx = 1\n")
    assert "WARNING" not in _run(repo, "scripts/thing.py")


def test_the_index_not_the_working_tree_decides_what_is_inspected(tmp_path: Path) -> None:
    """`git add` then `rm` (an AD state): the staged blob is COMMITTED yet the check read the
    missing worktree file as "a deletion" and printed a clean 0-of-1; a script rewritten as a
    symlink after `git add` skipped a real staged violation (EZ6)."""
    repo = _repo(tmp_path, "x = 1\n")  # headerless
    subprocess.run(["git", "-C", str(repo), "add", "scripts/thing.py"], check=True)
    (repo / "scripts" / "thing.py").unlink()
    out = subprocess.run(
        [sys.executable, str(CHECK)], cwd=repo, capture_output=True, text=True, timeout=60
    )
    assert "scripts/thing.py: no `# AFTER-EDIT:` header" in out.stdout + out.stderr, out.stdout
    repo2 = _repo(tmp_path / "two", "# AFTER-EDIT: docs/other.md\nx = 1\n")
    subprocess.run(["git", "-C", str(repo2), "add", "scripts/thing.py"], check=True)
    (repo2 / "scripts" / "thing.py").unlink()
    (repo2 / "scripts" / "thing.py").symlink_to("/etc/hostname")
    out2 = subprocess.run(
        [sys.executable, str(CHECK)], cwd=repo2, capture_output=True, text=True, timeout=60
    )
    assert "not updated in this change: docs/other.md" in out2.stdout + out2.stderr, out2.stdout


def test_one_unanswerable_path_keeps_every_other_scripts_finding(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """A per-file GitUnavailableError aborted the loop and discarded the warnings already
    collected for the other staged scripts (EZ6)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_script_headers_under_test", CHECK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(
        mod,
        "_git",
        lambda args, sep="\n": ["scripts/a.py", "scripts/b.py"]
        if args[0] == "diff"
        else (
            ["100644 x 0\tscripts/a.py", "100644 x 0\tscripts/b.py"]
            if args[0] == "ls-files"
            else [str(tmp_path)]
        ),
    )

    def show(path):
        if path.endswith("b.py"):
            raise mod.GitUnavailableError("git show :scripts/b.py: exit 128: fatal: bad object")
        return "x = 1\n"

    monkeypatch.setattr(mod, "_staged_head", show)
    monkeypatch.chdir(tmp_path)
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert (
        "scripts/a.py: no `# AFTER-EDIT:` header" in out
        and "scripts/b.py: git did not answer" in out
    ), out


def test_a_directory_token_without_its_slash_is_satisfied_by_a_staged_file_under_it(
    tmp_path: Path,
) -> None:
    """`# AFTER-EDIT: docs` (a real directory, no trailing slash) could never be closed by any
    staging action — the prefix branch required the slash (EZ6)."""
    repo = _repo(
        tmp_path, "# AFTER-EDIT: docs/sub\nx = 1\n"
    )  # a `/` makes it a path token (a bare `docs` is prose, EA2)
    (repo / "docs" / "sub").mkdir()
    (repo / "docs" / "sub" / "x.md").write_text("# x\n", encoding="utf-8")
    assert "WARNING" not in _run(repo, "scripts/thing.py", "docs/sub/x.md")


def test_a_non_utf8_path_under_an_eight_bit_locale_is_not_a_traceback(tmp_path: Path) -> None:
    """`_git` decoded `-z` output with the locale codec and no `errors=`: a non-ASCII staged path
    under `LANG=C` (coercion off) was a UnicodeDecodeError out of a warn-only check (EZ6)."""
    import os

    repo = _repo(tmp_path, "x = 1\n")
    (repo / "scripts" / "naïve.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repo), "add", "scripts/thing.py", "scripts/naïve.py"], check=True
    )
    env = {**os.environ, "LANG": "C", "LC_ALL": "C", "PYTHONCOERCECLOCALE": "0", "PYTHONUTF8": "0"}
    proc = subprocess.run(
        [sys.executable, str(CHECK)], cwd=repo, capture_output=True, text=True, timeout=60, env=env
    )
    assert proc.returncode == 0 and "Traceback" not in proc.stderr, proc.stderr
    assert "scripts/thing.py: no `# AFTER-EDIT:` header" in proc.stdout, proc.stdout


def test_a_double_full_stop_sentinel_is_still_the_sentinel(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "# AFTER-EDIT: none..\nx = 1\n")
    assert "WARNING" not in _run(repo, "scripts/thing.py")


def test_a_newline_or_an_undecodable_byte_in_a_staged_path_is_still_inspected(
    tmp_path: Path,
) -> None:
    """`cat-file --batch` read one object name per LINE, so a newline inside a path split the
    request into two `missing` answers — a headerless script read as "a staged deletion"; and
    `_git`'s `errors="replace"` re-encoded a non-UTF-8 path to different bytes, the same false
    deletion (FB2). NUL-delimited input and lossless decoding keep both inspected."""
    import os

    repo = _repo(tmp_path, "x = 1\n")
    (repo / "scripts" / "no\nheader.py").write_text("x = 1\n", encoding="utf-8")
    with open(os.fsencode(str(repo / "scripts")) + b"/bad_\xff\xfe.py", "wb") as fh:
        fh.write(b"x = 1\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A", "scripts"], check=True)
    proc = subprocess.run([sys.executable, str(CHECK)], cwd=repo, capture_output=True, timeout=60)
    out = proc.stdout.decode("utf-8", "replace")
    assert proc.returncode == 0, proc.stderr[-300:]
    assert "staged deletion" not in out, out
    assert out.count("no `# AFTER-EDIT:` header") == 3, (
        out
    )  # thing.py, the newline path, the raw-byte path


def test_trailing_prose_and_a_period_after_a_real_path_never_mint_phantom_files(
    tmp_path: Path,
) -> None:
    """`docs/coupled.md — see the callers.` minted `callers.` as a coupled file (its period is a
    path shape); `docs/coupled.md.` was unsatisfiable forever; `...` was a file (FB2)."""
    repo = _repo(tmp_path, "# AFTER-EDIT: docs/coupled.md — see the callers.\nx = 1\n")
    assert "WARNING" not in _run(repo, "scripts/thing.py", "docs/coupled.md")
    repo2 = _repo(tmp_path / "two", "# AFTER-EDIT: docs/coupled.md.\nx = 1\n")
    assert "WARNING" not in _run(repo2, "scripts/thing.py", "docs/coupled.md")
    repo3 = _repo(tmp_path / "three", "# AFTER-EDIT: ... none\nx = 1\n")
    assert "WARNING" not in _run(repo3, "scripts/thing.py")


def test_a_stat_error_on_a_coupled_token_is_a_warning_never_a_traceback(tmp_path):
    """pathlib swallows ENOENT/ENOTDIR/EBADF/ELOOP only: a >255-byte token (ENAMETOOLONG) or a
    token under a mode-000 directory (EACCES) was a traceback out of a WARN-only check — a red
    gate for a header typo, in ~46 repos (C-1/FC7)."""
    import os

    long = "a" * 300
    repo = _repo(tmp_path, f"# AFTER-EDIT: docs/{long}.md, {long}, locked/x.md\n")
    locked = repo / "locked"
    locked.mkdir()
    locked.chmod(0)
    try:
        if os.access(locked / "x.md", os.R_OK):
            pytest.skip("running as root — permissions are not enforced")
        out = _run(repo, "scripts/thing.py")
    finally:
        locked.chmod(0o755)
    assert "not updated" in out and "Traceback" not in out, out


def test_an_empty_declaration_is_said_in_both_spellings(tmp_path):
    """`# AFTER-EDIT: ` (trailing space) passed as `none`; `# AFTER-EDIT:` read as "no header" —
    the same forgotten list, two different wrong answers (C-2/FC7)."""
    repo = _repo(tmp_path, "# AFTER-EDIT: \n")
    (repo / "scripts" / "b.py").write_text("# AFTER-EDIT:\n", encoding="utf-8")
    out = _run(repo, "scripts/thing.py", "scripts/b.py")
    assert out.count("empty `# AFTER-EDIT:`") == 2 and "no `# AFTER-EDIT:` header" not in out, out


def test_a_form_feed_in_a_docstring_never_shrinks_the_scan_window(tmp_path):
    """`str.splitlines` breaks on \\x0c/\\u2028 where the tokenizer does not: a form feed on
    line 1 pushed a line-25 header out of the window (C-3/FC7)."""
    repo = _repo(tmp_path, '"""doc\x0c string"""\n' + "# filler\n" * 22 + "# AFTER-EDIT: none\n")
    out = _run(repo, "scripts/thing.py")
    assert "no `# AFTER-EDIT:` header" not in out, out
