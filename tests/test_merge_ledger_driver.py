"""The ledger merge driver (W-53360407): `merge_request.py merge-ledger %O %A %B %P` resolves
concurrent insertions into the five ledgers inside an ordinary `git merge`, and every failure falls
back to git's markers (spec docs/superpowers/specs/2026-10-30-ledger-merge-driver-design.md)."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HUB = Path(__file__).resolve().parents[1]
SCRIPT = HUB / "scripts" / "merge_request.py"
FALLBACK = "git merge-file --marker-size %L -L ours -L base -L theirs %A %O %B"
# the string scripts/install_post_commit_hook.sh registers (tree-relative, run at the worktree top)
LEDGER_DRIVER = f"python3 scripts/merge_request.py merge-ledger %O %A %B %P || {FALLBACK}"
CHANGELOG = "# Changelog\n\n## [Unreleased]\n\n### Fixed — old (2026-10-01)\nold\n"
DECISIONS = "| id | what |\n|---|---|\n| D-1389 | x |\n"
ATTRS = "/CHANGELOG.md merge=ledger\n/docs/DECISIONS.md merge=ledger\n"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=check
    )


def _driver(script: Path) -> str:
    return f"{sys.executable} {script} merge-ledger %O %A %B %P || {FALLBACK}"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "r"
    subprocess.run(["git", "init", "-q", "-b", "master", str(r)], check=True)
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "t")
    (r / "docs").mkdir()
    (r / "CHANGELOG.md").write_text(CHANGELOG)
    (r / "docs" / "DECISIONS.md").write_text(DECISIONS)
    (r / ".gitattributes").write_text(ATTRS)
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "base")
    return r


def _entry(repo: Path, branch_from: str, name: str, d_row: str | None) -> None:
    _git(repo, "switch", "-qc", name, branch_from)
    cl = repo / "CHANGELOG.md"
    cl.write_text(
        cl.read_text().replace(
            "## [Unreleased]\n", f"## [Unreleased]\n\n### Fixed — {name} (2026-10-31)\n{name}\n", 1
        )
    )
    if d_row:
        with (repo / "docs" / "DECISIONS.md").open("a") as fh:
            fh.write(d_row + "\n")
    _git(repo, "commit", "-qam", name)


def _two_branches(repo: Path, ours_row: str | None, theirs_row: str | None) -> None:
    _entry(repo, "master", "theirs", theirs_row)
    _entry(repo, "master", "ours", ours_row)


def _run_verb(tmp_path: Path, base: str, ours: str, theirs: str, path: str):
    o, a, b = tmp_path / "o", tmp_path / "a", tmp_path / "b"
    o.write_text(base)
    a.write_text(ours)
    b.write_text(theirs)
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "merge-ledger", str(o), str(a), str(b), path],
        capture_output=True,
        text=True,
    )
    return res, a


def test_without_the_driver_the_pair_conflicts(repo: Path) -> None:
    _two_branches(repo, "| D-1390 | ours |", "| D-1391 | theirs |")
    res = _git(repo, "merge", "-q", "--no-edit", "theirs", check=False)
    assert res.returncode != 0
    assert "<<<<<<<" in (repo / "CHANGELOG.md").read_text()


def test_the_driver_merges_both_insertions_clean(repo: Path) -> None:
    _git(repo, "config", "merge.ledger.driver", _driver(SCRIPT))
    _two_branches(repo, "| D-1390 | ours |", "| D-1391 | theirs |")
    _git(repo, "merge", "-q", "--no-edit", "theirs")
    cl = (repo / "CHANGELOG.md").read_text()
    assert "### Fixed — ours" in cl and "### Fixed — theirs" in cl and "<<<<<<<" not in cl


def test_the_driver_resolves_a_rebase_too(repo: Path) -> None:
    _git(repo, "config", "merge.ledger.driver", _driver(SCRIPT))
    _two_branches(repo, "| D-1390 | ours |", "| D-1391 | theirs |")
    _git(repo, "rebase", "-q", "theirs")
    cl = (repo / "CHANGELOG.md").read_text()
    assert "### Fixed — ours" in cl and "### Fixed — theirs" in cl and "<<<<<<<" not in cl


@pytest.mark.parametrize(
    "ours_row,theirs_row",
    [("| D-1390 | o |", "| D-1391 | t |"), ("| D-1391 | o |", "| D-1390 | t |")],
)
def test_decisions_puts_the_higher_id_first_whichever_side_is_ours(
    repo: Path, ours_row: str, theirs_row: str
) -> None:
    # the one assertion that proves %P reached the verb (panel, Fable concern 2)
    _git(repo, "config", "merge.ledger.driver", _driver(SCRIPT))
    _two_branches(repo, ours_row, theirs_row)
    _git(repo, "merge", "-q", "--no-edit", "theirs")
    text = (repo / "docs" / "DECISIONS.md").read_text()
    assert text.index("| D-1391 |") < text.index("| D-1390 |")


def test_a_duplicate_id_refuses_and_leaves_both_rows_in_markers(repo: Path, tmp_path: Path) -> None:
    _git(repo, "config", "merge.ledger.driver", _driver(SCRIPT))
    _two_branches(repo, "| D-1390 | o |", "| D-1390 | t |")
    res = _git(repo, "merge", "-q", "--no-edit", "theirs", check=False)
    assert res.returncode != 0
    assert "D-1390" in res.stderr
    text = (repo / "docs" / "DECISIONS.md").read_text()
    assert "<<<<<<<" in text and "| D-1390 | o |" in text and "| D-1390 | t |" in text
    ours = DECISIONS + "| D-1390 | o |\n"
    direct, a = _run_verb(
        tmp_path, DECISIONS, ours, DECISIONS + "| D-1390 | t |\n", "docs/DECISIONS.md"
    )
    assert direct.returncode == 1
    assert a.read_text() == ours


def test_a_duplicate_theirs_already_holds_twice_still_refuses(tmp_path: Path) -> None:
    # tells the spec's rule (result minus OURS's duplicates) from the looser prototype rule
    base = "| D-5 | a |\n"
    ours = base + "| D-7 | o |\n"
    res, a = _run_verb(tmp_path, base, ours, base + "| D-5 | b |\n", "docs/DECISIONS.md")
    assert res.returncode == 1
    assert a.read_text() == ours


def test_an_edit_of_a_landed_row_refuses_with_rc_1_and_ours_untouched(
    repo: Path, tmp_path: Path
) -> None:
    base = "| D-1 | x |\n| D-2 | y |\n"
    ours = "| D-1 | x |\n| D-2 | Y |\n| D-3 | o |\n"
    theirs = base + "| D-4 | t |\n"
    res, a = _run_verb(tmp_path, base, ours, theirs, "docs/DECISIONS.md")
    assert res.returncode == 1
    assert a.read_text() == ours
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".merge-ledger-")]
    # through git, the same pair leaves markers with both sides
    (repo / "docs" / "DECISIONS.md").write_text(base)
    _git(repo, "commit", "-qam", "landed rows")
    _git(repo, "config", "merge.ledger.driver", _driver(SCRIPT))
    _git(repo, "switch", "-qc", "t2")
    (repo / "docs" / "DECISIONS.md").write_text(theirs)
    _git(repo, "commit", "-qam", "t2")
    _git(repo, "switch", "-qc", "o2", "master")
    (repo / "docs" / "DECISIONS.md").write_text(ours)
    _git(repo, "commit", "-qam", "o2")
    merged = _git(repo, "merge", "-q", "--no-edit", "t2", check=False)
    assert merged.returncode != 0
    text = (repo / "docs" / "DECISIONS.md").read_text()
    assert "<<<<<<<" in text and "| D-2 | Y |" in text and "| D-4 | t |" in text


def test_a_failed_write_leaves_ours_untouched_and_no_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = importlib.util.spec_from_file_location("merge_request_under_test", SCRIPT)
    assert spec and spec.loader
    mr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mr)
    o, a, b = tmp_path / "o", tmp_path / "a", tmp_path / "b"
    o.write_text(CHANGELOG)
    ours = CHANGELOG.replace(
        "## [Unreleased]\n", "## [Unreleased]\n\n### Fixed — o (2026-10-31)\no\n"
    )
    a.write_text(ours)
    b.write_text(
        CHANGELOG.replace("## [Unreleased]\n", "## [Unreleased]\n\n### Fixed — t (2026-10-31)\nt\n")
    )

    def boom(*_args, **_kw):
        raise OSError("disk full")

    monkeypatch.setattr(mr.os, "replace", boom)
    with pytest.raises(OSError):
        mr._merge_ledger(str(o), str(a), str(b), "CHANGELOG.md")
    assert a.read_text() == ours
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".merge-ledger-")]


def test_a_tree_without_the_verb_falls_back_to_markers(repo: Path, tmp_path: Path) -> None:
    old = tmp_path / "old_merge_request.py"
    old.write_text(
        "import argparse\np = argparse.ArgumentParser()\n"
        "p.add_subparsers(dest='cmd').add_parser('merge')\np.parse_args()\n"
    )
    _git(repo, "config", "merge.ledger.driver", _driver(old))
    _two_branches(repo, "| D-1390 | o |", "| D-1391 | t |")
    res = _git(repo, "merge", "-q", "--no-edit", "theirs", check=False)
    assert res.returncode != 0
    assert "invalid choice: 'merge-ledger'" in res.stderr  # proves the driver ran
    assert "<<<<<<<" in (repo / "CHANGELOG.md").read_text()


def test_a_merge_clean_without_the_driver_stays_byte_identical_with_it(
    repo: Path, tmp_path: Path
) -> None:
    # both sides change the SAME ledger far apart: git calls a driver only for a file changed on
    # both sides, and plain git merges these edits cleanly (panel, Opus concern 3)
    long_cl = CHANGELOG + "".join(f"\n### Fixed — e{i} (2026-09-01)\ne{i}\n" for i in range(12))
    (repo / "CHANGELOG.md").write_text(long_cl)
    _git(repo, "commit", "-qam", "long")
    _git(repo, "switch", "-qc", "theirs")
    (repo / "CHANGELOG.md").write_text(long_cl.replace("e11\n", "e11 (theirs)\n"))
    _git(repo, "commit", "-qam", "t")
    _git(repo, "switch", "-qc", "ours", "master")
    (repo / "CHANGELOG.md").write_text(long_cl.replace("# Changelog\n", "# Changelog (ours)\n"))
    _git(repo, "commit", "-qam", "o")
    plain = _git(repo, "merge-tree", "--write-tree", "ours", "theirs")
    assert plain.returncode == 0
    want = _git(repo, "show", f"{plain.stdout.split()[0]}:CHANGELOG.md").stdout
    log = tmp_path / "driver-exit.log"
    wrapper = tmp_path / "drv.sh"
    wrapper.write_text(
        f'#!/bin/sh\n{sys.executable} {SCRIPT} merge-ledger "$1" "$2" "$3" "$4"\n'
        f"rc=$?\necho $rc >> {log}\nexit $rc\n"
    )
    wrapper.chmod(0o755)
    _git(repo, "config", "merge.ledger.driver", f"{wrapper} %O %A %B %P || {FALLBACK}")
    merged = _git(repo, "merge", "-q", "--no-edit", "theirs", check=False)
    assert merged.returncode == 0
    assert log.read_text().split() == ["0"]  # the driver ran and itself succeeded
    assert (repo / "CHANGELOG.md").read_text() == want


def test_the_installer_string_runs_from_a_linked_worktree(repo: Path, tmp_path: Path) -> None:
    # the literal registered string, tree-relative, from a linked worktree (the shape of
    # _build's throwaway) — panel, Opus concern 4
    (repo / "scripts").mkdir()
    shutil.copy(SCRIPT, repo / "scripts" / "merge_request.py")
    _git(repo, "add", "scripts")
    _git(repo, "commit", "-qm", "the verb")
    _git(repo, "config", "merge.ledger.driver", LEDGER_DRIVER)
    _two_branches(repo, "| D-1390 | o |", "| D-1391 | t |")
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", "--detach", str(wt), "ours")
    env = {**os.environ, "PATH": f"{Path(sys.executable).parent}:{os.environ.get('PATH', '')}"}
    res = subprocess.run(
        ["git", "-C", str(wt), "merge", "-q", "--no-edit", "theirs"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert res.returncode == 0, res.stderr
    assert "<<<<<<<" not in (wt / "CHANGELOG.md").read_text()
