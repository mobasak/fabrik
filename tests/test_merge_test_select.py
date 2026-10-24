"""scripts/merge_test_select.py — the hub's merge-time test leg (W-4e756979).

The selection rules are driven on in-memory test texts; the leg itself (shards, the serial confirm,
the base comparison, the record) on small real git repos under tmp_path, with the selector's own
`main()` as the subject — the inner pytest runs there, never on this repo's suite. The replay reads
this repo's history, read-only.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "merge_test_select.py"


def _load():
    spec = importlib.util.spec_from_file_location("_merge_test_select", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mts = _load()


def test_name_and_stem_select():
    tests = {
        "tests/test_a.py": "load('scripts/merge_request.py')",
        "tests/test_b.py": "import merge_request",
        "tests/test_c.py": "nothing relevant",
    }
    assert mts.select(["scripts/sysadmin/merge_request.py"], tests) == [
        "tests/test_a.py",
        "tests/test_b.py",
    ]
    # a stem under MIN_STEM characters is not a key: `run` would select half the suite
    assert mts.select(["scripts/run.py"], {"tests/test_d.py": "run the thing"}) == []


def test_directory_and_tree_grader_keys():
    tests = {
        "tests/test_path.py": 'ROOT / "commands/_sources/x.md"',
        "tests/test_join.py": 'ROOT / "commands" / "_sources"',
        "tests/test_generic.py": 'ROOT / "scripts" / "other.py"',
    }
    picked = mts.select(["commands/_sources/new-command.md"], tests)
    assert picked == ["tests/test_join.py", "tests/test_path.py"]
    # a generic last component ("scripts") is never a quoted key
    assert mts.select(["scripts/brand_new_tool.py"], {"tests/test_g.py": '"scripts"'}) == []
    # a tree grader (it runs `git ls-files`) reaches every file, a new one under a generic directory
    # included — measured: without this rule a new scripts/*.py selected nothing against the real
    # hub-write-root grader, the source of 7 of the 32 red-master fixes
    grader = (ROOT / "tests" / "test_hub_write_root.py").read_text(encoding="utf-8")
    for new in ("scripts/brand_new_tool.py", "scripts/new_hook.sh", "docs/x.md"):
        assert mts.select([new], {"tests/test_hub_write_root.py": grader}) == [
            "tests/test_hub_write_root.py"
        ], new


def test_ledgers_are_not_keys():
    tests = {
        "tests/test_l.py": "CHANGELOG.md DECISIONS.md INDEX.md LESSONS_LEARNT.md .fabrik/work/",
        "tests/test_tree.py": "git ls-files",
    }
    changed = [
        "CHANGELOG.md",
        "docs/DECISIONS.md",
        "INDEX.md",
        "docs/LESSONS_LEARNT.md",
        ".fabrik/work/W-0123abcd.json",
    ]
    assert mts.select(changed, tests) == []  # a ledger-only merge runs no tree grader either
    assert mts.select(["tests/test_x.py"], {"tests/test_x.py": ""}) == ["tests/test_x.py"]


# --- the leg on real repos -----------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r.stdout.strip()


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "master")
    _write(repo, files)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    return repo


def _write(repo: Path, files: dict[str, str | None]) -> None:
    for rel, text in files.items():
        p = repo / rel
        if text is None:
            p.unlink()
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def _merge(repo: Path, branch_files: dict[str, str | None]) -> tuple[str, str]:
    """Commit ``branch_files`` on a branch and merge it ``--no-ff`` into master, as `_build` does."""
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-qb", "feat")
    _write(repo, branch_files)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "change")
    _git(repo, "checkout", "-q", "master")
    _git(repo, "merge", "--no-ff", "-q", "-m", "merge", "feat")
    return base, _git(repo, "rev-parse", "HEAD")


def _run(repo: Path, monkeypatch, capsys, *, merge_check: bool = True, args=("--shards", "2")):
    monkeypatch.chdir(repo)
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    if merge_check:
        monkeypatch.setenv("FABRIK_MERGE_CHECK", "1")
    else:
        monkeypatch.delenv("FABRIK_MERGE_CHECK", raising=False)
    rc = mts.main(list(args))
    return rc, capsys.readouterr().out


def test_pyproject_ignores_are_dropped(tmp_path, monkeypatch, capsys):
    repo = _repo(
        tmp_path,
        {
            "tool_one.py": "x = 1\n",
            "tests/test_tool_one.py": "# reads tool_one.py\ndef test_ok():\n    pass\n",
            "tests/test_ignored.py": "# tool_one.py\nimport no_such_module\n",
            "pyproject.toml": '[tool.pytest.ini_options]\naddopts = "--ignore=tests/test_ignored.py"\n',
        },
    )
    _merge(repo, {"tool_one.py": "x = 2\n"})
    rc, out = _run(repo, monkeypatch, capsys, args=("--list",))
    assert rc == 0 and "tests/test_tool_one.py" in out and "test_ignored" not in out, out


# library_x.py (stem >= MIN_STEM) is named by every test below, so a change to it selects them all
LIB_BASE = "VALUE = 1\nMSG = 'base message'\n"
LIB_BRANCH = "VALUE = 2\nMSG = 'branch message'\n"
LEG_REPO = {
    "library_x.py": LIB_BASE,
    # red on the base, red the same way on the merge -> pre-existing
    "tests/test_keep.py": "import library_x\n\ndef test_keep():\n    assert False, 'always red'\n",
    # green on the base, red on the merge -> NEW
    "tests/test_mod.py": "import library_x\n\ndef test_mod():\n    assert library_x.VALUE == 1\n",
    # red on both, but its crash line names the changed message -> NEW
    "tests/test_crash.py": "import library_x\n\ndef test_crash():\n    raise RuntimeError(library_x.MSG)\n",
    # a collection error on both: its id is the file; the flag keeps its shard's other files running
    "tests/test_broken.py": "# library_x\nimport no_such_module_anywhere\n",
    # red the first time it runs, green after -> FLAKY (the counter lives outside the tree)
    "tests/test_flaky.py": (
        "import os, library_x\n\ndef test_flaky():\n"
        "    p = os.environ['FLAKY_FILE']\n    first = not os.path.exists(p)\n"
        "    open(p, 'a').close()\n    assert not first, 'first run red'\n"
    ),
    # leaves the tree dirty: a tracked file rewritten, as a test running a writer in cwd can
    "data.txt": "base\n",
    "tests/test_dirty.py": (
        "import library_x\n\ndef test_dirty():\n    open('data.txt', 'w').write('dirtied')\n"
    ),
}


def test_differential_verdicts(tmp_path, monkeypatch, capsys):
    repo = _repo(tmp_path, LEG_REPO)
    monkeypatch.setenv("FLAKY_FILE", str(tmp_path / "flaky-ran"))
    newred = "import library_x\n\ndef test_newred():\n    assert False, 'new in the branch'\n"
    base, merge = _merge(
        repo, {"library_x.py": LIB_BRANCH, "tests/test_newred.py": newred, "data.txt": "branch\n"}
    )
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 1, out
    new = {ln.split(" — ")[1].split(" (")[0] for ln in out.splitlines() if "NEW red" in ln}
    assert new == {
        "tests/test_mod.py::test_mod",
        "tests/test_crash.py::test_crash",
        "tests/test_newred.py::test_newred",
    }, out
    pre = {ln.split(" — ")[1].split(" (")[0] for ln in out.splitlines() if "pre-existing" in ln}
    assert pre == {"tests/test_keep.py::test_keep", "tests/test_broken.py"}, out
    assert "FLAKY" in out and "tests/test_flaky.py::test_flaky" in out, out
    assert out.strip().splitlines()[-1].startswith("merge-tests: red"), out  # the verdict is LAST
    assert _git(repo, "rev-parse", "HEAD") == merge  # back at the merge, though a test dirtied it
    # the same merge with only master's own reds is green (the leg left HEAD detached at the merge,
    # as the merge leg's build tree is; master is reset under it)
    _git(repo, "checkout", "-q", "-f", "master")
    _git(repo, "reset", "-q", "--hard", base)
    _git(repo, "branch", "-qD", "feat")
    (tmp_path / "flaky-ran").unlink()
    _merge(repo, {"library_x.py": LIB_BASE + "# a comment\n"})
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0 and "NEW red" not in out and "pre-existing" in out, out


def test_a_shard_that_did_not_run_its_tests_is_a_leg_red(tmp_path, monkeypatch, capsys):
    repo = _repo(
        tmp_path,
        {
            "library_x.py": LIB_BASE,
            "tests/sub/conftest.py": "import no_such_module_anywhere\n",
            "tests/sub/test_s.py": "import library_x\n\ndef test_s():\n    pass\n",
        },
    )
    _merge(repo, {"library_x.py": LIB_BRANCH})
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 3 and "LEG FAILED" in out.strip().splitlines()[-1], out


def test_the_record_and_the_base_alone_run(tmp_path, monkeypatch, capsys):
    repo = _repo(
        tmp_path,
        {
            "library_x.py": LIB_BASE,
            # the new red's file also holds one of master's own reds, which the base-alone run must
            # not count as the new red failing there
            "tests/test_mod.py": (
                "import library_x\n\ndef test_mod():\n    assert library_x.VALUE == 1\n\n"
                "def test_master_red():\n    assert False, 'always red'\n"
            ),
        },
    )
    base, _merge_sha = _merge(repo, {"library_x.py": LIB_BRANCH})
    common = Path(_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    record = common / "fabrik-merge" / f"merge-tests-{base}.txt"
    # outside a merge check (a requester's run) nothing is recorded
    monkeypatch.setenv("FLAKY_FILE", str(tmp_path / "unused"))
    _git(repo, "update-ref", "refs/remotes/origin/master", base)
    rc, out = _run(repo, monkeypatch, capsys, merge_check=False)
    assert rc == 1 and not record.exists(), out
    # the merge leg records the NEW red by id, keyed by its base
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 1 and record.read_text().split("\n")[0] == "tests/test_mod.py::test_mod\tcall"
    # _base_alone: HEAD = the base, one parent; the recorded id is green there (test_master_red, in
    # the same file and red there too, is master's own and not counted)
    _git(repo, "checkout", "-q", "--detach", base)
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0 and "0 of 1 new red(s) red here too" in out, out
    # a base with no record says it measured nothing — never a base-side fault
    _git(repo, "checkout", "-q", "--detach", "master")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "a later base")
    _git(repo, "checkout", "-q", "--detach", "HEAD")
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 2 and "NOT MEASURED on the base" in out.strip().splitlines()[-1], out
    # every recorded red in a file new in the branch: nothing to run on the base, green
    record.write_text("tests/test_only_in_branch.py::test_x\tcall\n")
    _git(repo, "checkout", "-q", "--detach", base)
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0 and "file new in the branch" in out, out


def test_the_crash_line_is_compared_without_the_runs_temp_paths():
    a = "AssertionError: /tmp/pytest-of-ozgur/pytest-4644/test_x0/out.txt missing in /tmp/merge-q1w2e3r4/x"
    b = "AssertionError: /tmp/pytest-of-ozgur/pytest-4651/test_x0/out.txt missing in /tmp/merge-zz99xx88/x"
    assert a != b and mts.normalise(a) == mts.normalise(b)
    assert mts.normalise("assert 1 == 2") != mts.normalise("assert 1 == 3")


# (cause commit, the grader its merge left red) — measured 2026-10-23, W-4e756979's measure.md
REPLAY = [
    ("477a1d208", "tests/test_hub_write_root.py"),
    ("e68efa2e0", "tests/test_fabrik_task_source.py"),
    ("dc99ebd76", "tests/test_orient_fragment.py"),
    ("c4a3f26a1", "tests/test_governance_template_split.py"),
    ("a90b35a3b", "tests/test_mail_addressing.py"),
    ("f2921f71e", "tests/test_scratch_sweep.py"),
    ("4c614aabd", "tests/test_identifier_checks_fullmatch.py"),
    ("986b8ce22", "tests/test_assemble_dispatch_step.py"),
    ("e7057ec0a", "tests/test_hub_write_root.py"),
    ("46b3a76b6", "tests/test_review_queue_pass.py"),
    ("04413b533", "tests/test_governance_template_split.py"),
    ("f6031e952", "tests/test_scaffold_doc_seeding.py"),
    ("fb96a7464", "tests/test_hub_write_root.py"),
    ("816625088", "tests/test_kaizen_outcomes.py"),
    ("3530aa790", "tests/test_hub_write_root.py"),
    ("9595c8d73", "tests/test_hub_write_root.py"),
]


def _show(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True).stdout


@pytest.mark.parametrize(("cause", "grader"), REPLAY)
def test_replay_of_measured_red_merges(cause, grader):
    parents = _show("show", "-s", "--format=%P", cause).split()
    if not parents:
        pytest.skip(f"{cause} is not in this clone's history")
    changed = [
        p for p in _show("diff", "--name-only", "--no-renames", parents[0], cause).splitlines() if p
    ]
    names = [
        p
        for p in _show("ls-tree", "-r", "--name-only", cause, "tests/").splitlines()
        if mts.TEST_FILE.fullmatch(p)
    ]
    tests = {n: _show("show", f"{cause}:{n}") for n in names}
    assert grader in mts.select(changed, tests)


def test_merge_tests_file_runs_the_selector_under_the_main_checkouts_venv():
    text = (ROOT / ".fabrik" / "merge-tests").read_text(encoding="utf-8")
    assert "scripts/merge_test_select.py" in text and "git-common-dir" in text, text
    assert os.access(SCRIPT, os.R_OK)
