"""scripts/merge_test_select.py — the hub's merge-time test leg (W-4e756979).

The selection rules are driven on in-memory test texts; the leg itself (shards, the serial confirm,
the base comparison, the record) on small real git repos under tmp_path, with the selector's own
`main()` as the subject — the inner pytest runs there, never on this repo's suite. The replay reads
this repo's history, read-only.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
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
    # a short module is still selected by the way a test imports it
    imports = {
        "tests/test_dotted.py": "from fabrik.state import load",
        "tests/test_from.py": "from fabrik import state",
        "tests/test_other.py": "from fabrik.statement import x",
        "tests/test_paren.py": "from fabrik import (\n    load,\n    state,\n)",
        "tests/test_list.py": "from fabrik import cli, state as st",
        "tests/test_tab.py": "from\tfabrik  import\tstate",
        "tests/test_cont.py": "from fabrik import cli, \\\n    state",
        "tests/test_prefix.py": "import xfabrik.state",  # another package's module
        "tests/test_inner.py": "a.fabrik.state",  # an attribute path, not the import
        "tests/test_name.py": "from fabrik import statement",
        "tests/test_comment.py": "from fabrik import (\n    cli,  # why\n    state,\n)",
        "tests/test_nextstmt.py": "from fabrik import cli\nimport os\nstate = 2",  # a later line
    }
    assert mts.select(["src/fabrik/state.py"], imports) == [
        "tests/test_comment.py",
        "tests/test_cont.py",
        "tests/test_dotted.py",
        "tests/test_from.py",
        "tests/test_list.py",
        "tests/test_paren.py",
        "tests/test_tab.py",
    ]
    # a top-level module has no import form beyond its own name
    assert mts.import_patterns("library_x.py") == set()


def _imports_state(text: str) -> bool:
    import re

    return any(re.search(p, text) for p in mts.import_patterns("src/fabrik/state.py"))


def test_import_patterns_paren_comment_with_close_paren():
    assert _imports_state("from fabrik import (\n    cli,  # see (why)\n    state,\n)\n")
    assert not _imports_state("from fabrik import (\n    cli,  # see (why)\n    other,\n)\n")


def test_import_patterns_crlf_backslash_continuation():
    assert _imports_state("from fabrik import cli, \\\r\n state\r\n")
    assert not _imports_state("from fabrik import cli, \\\r\n other\r\n")


def test_normalise_relative_default_tempdir():
    assert mts.normalise("missing tmpk3j9_2xq/out.txt") == mts.normalise(
        "missing tmpzz81_q0a/out.txt"
    )
    assert mts.normalise("missing tmpfiles_old/out") != mts.normalise("missing tmpfiles_new/out")


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


@pytest.mark.parametrize(
    "addopts",
    [
        '"--ignore tests/test_ignored.py"',  # the flag and its value as two words
        '["--ignore=tests/test_ignored.py"]',  # a list-valued addopts
    ],
)
def test_every_ignore_spelling_is_dropped(tmp_path, monkeypatch, addopts):
    (tmp_path / "pyproject.toml").write_text(f"[tool.pytest.ini_options]\naddopts = {addopts}\n")
    monkeypatch.chdir(tmp_path)
    assert mts._ignored() == {"tests/test_ignored.py"}


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
    # red on both, its crash line naming pytest's per-run temp root, which differs run to run
    "tests/test_tmp.py": "import library_x\n\ndef test_tmp(tmp_path):\n    assert False, str(tmp_path)\n",
}


def test_differential_verdicts(tmp_path, monkeypatch, capsys):
    repo = _repo(tmp_path, LEG_REPO)
    monkeypatch.setenv("FLAKY_FILE", str(tmp_path / "flaky-ran"))
    newred = "import library_x\n\ndef test_newred():\n    assert False, 'new in the branch'\n"
    base, merge = _merge(
        repo,
        {
            "library_x.py": LIB_BRANCH,
            "tests/test_newred.py": newred,
            "data.txt": "branch\n",
        },
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
    assert pre == {
        "tests/test_keep.py::test_keep",
        "tests/test_broken.py",
        "tests/test_tmp.py::test_tmp",
    }, out
    # every NEW red is recorded, by id, under the base the merge refused onto
    common = Path(_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    record = (common / "fabrik-merge" / f"merge-tests-{base}.txt").read_text().splitlines()
    assert sorted(ln.split("\t")[0] for ln in record) == sorted(new), record
    assert "FLAKY" in out and "tests/test_flaky.py::test_flaky" in out, out
    lines = out.strip().splitlines()
    assert lines[-1].startswith("merge-tests: red — 3 new failure(s): "), out  # the verdict is LAST
    # the refusal quotes the last 3 lines: the verdict names every new red, the 2 above it are NEW
    assert all(nid in lines[-1] for nid in new), out
    assert all("NEW red" in ln for ln in lines[-3:-1]), out
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
    # outside a merge check (a requester's own worktree) nothing is recorded, nothing compared,
    # and the tree is never checked out or cleaned: uncommitted work survives
    monkeypatch.setenv("FLAKY_FILE", str(tmp_path / "unused"))
    _git(repo, "update-ref", "refs/remotes/origin/master", base)
    _git(repo, "checkout", "-q", "master")
    (repo / "wip.txt").write_text("untracked work\n")
    (repo / "library_x.py").write_text(LIB_BRANCH + "# uncommitted\n")
    rc, out = _run(repo, monkeypatch, capsys, merge_check=False)
    assert rc == 1 and not record.exists() and "not compared with the base" in out, out
    # the verdict says so too: nothing was compared, so nothing is called new
    verdict = out.strip().splitlines()[-1]
    assert "not compared with the base" in verdict and "new failure" not in verdict, verdict
    assert (repo / "wip.txt").exists() and "# uncommitted" in (repo / "library_x.py").read_text()
    assert _git(repo, "symbolic-ref", "--short", "HEAD") == "master"
    _git(repo, "checkout", "-q", "--", "library_x.py")
    (repo / "wip.txt").unlink()
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
    # a recorded id that IS red on the base: red there too
    record.write_text("tests/test_mod.py::test_master_red\tcall\n")
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 1 and "1 of 1 new red(s) red here too" in out, out
    # a refusal without a verdict records that it measured nothing
    record.write_text("#leg-failed\tLegError\n")
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 2 and "NOT MEASURED on the base" in out.strip().splitlines()[-1], out


def test_a_base_that_is_itself_a_merge_commit_takes_the_base_alone_path(
    tmp_path, monkeypatch, capsys
):
    """4 of master's last 12 first-parent tips are merge commits: the base-alone re-run lands on
    one as often as not, and must not take it for the merge under check."""
    repo = _repo(
        tmp_path,
        {
            "library_x.py": LIB_BASE,
            "tests/test_mod.py": "import library_x\n\ndef test_mod():\n    assert library_x.VALUE == 1\n",
        },
    )
    _base0, base = _merge(repo, {"README": "an earlier branch\n"})  # the base: a merge commit
    _git(repo, "branch", "-qD", "feat")
    _merge(repo, {"library_x.py": LIB_BRANCH})
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 1 and "NEW red — tests/test_mod.py::test_mod" in out, out
    _git(repo, "checkout", "-q", "--detach", base)
    assert len(_git(repo, "show", "-s", "--format=%P", "HEAD").split()) == 2
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0 and "0 of 1 new red(s) red here too" in out, out


def test_a_red_another_file_of_its_shard_causes_is_compared_in_that_order(
    tmp_path, monkeypatch, capsys
):
    """The branch adds a test that leaves an untracked file behind; a base test fails when it finds
    one. Alone it is green, so a confirm of the file alone would call it flaky and admit it; in its
    shard's order it is red, and on the base — cleaned, the branch's writer absent — green: NEW."""
    reader = (
        "import os, library_x\n\ndef test_reader():\n"
        "    assert not os.path.exists('leftover.flag'), 'a leftover from another test'\n"
    )
    writer = "import library_x\n\ndef test_writer():\n    open('leftover.flag', 'w').close()\n"
    repo = _repo(tmp_path, {"library_x.py": LIB_BASE, "tests/test_b_reader.py": reader})
    _merge(repo, {"library_x.py": LIB_BRANCH, "tests/test_a_writer.py": writer})
    rc, out = _run(repo, monkeypatch, capsys, args=("--shards", "1"))
    assert rc == 1 and "NEW red — tests/test_b_reader.py::test_reader" in out, out
    assert "FLAKY" not in out, out


def test_a_base_run_that_fails_still_restores_the_merge(tmp_path, monkeypatch, capsys):
    repo = _repo(
        tmp_path,
        {
            "library_x.py": LIB_BASE,
            "tests/conftest.py": "import no_such_module_anywhere\n",  # the base cannot run
            "tests/test_mod.py": "import library_x\n\ndef test_mod():\n    assert library_x.VALUE == 1\n",
        },
    )
    _base, merge = _merge(repo, {"library_x.py": LIB_BRANCH, "tests/conftest.py": None})
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 3 and "LEG FAILED" in out.strip().splitlines()[-1], out
    assert _git(repo, "rev-parse", "HEAD") == merge
    # the refusal records that it measured nothing, so the base-alone run says so
    common = Path(_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    record = common / "fabrik-merge" / f"merge-tests-{_base}.txt"
    assert record.read_text().startswith("#leg-failed\t"), record.read_text()


class _FakeRunner:
    """Every run reports the same reds — enough to drive differential's bookkeeping alone."""

    class _Done:
        def poll(self):
            return 1

    def __init__(self, reds):
        self.reds = reds

    def start(self, files):
        return self._Done(), files, None

    def finish(self, _proc, _files, _log):
        return 1, dict(self.reds), "tail"

    def run(self, files):
        return self.finish(*self.start(files))


def test_a_failing_group_leaves_no_other_group_running():
    slow = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])

    class Runner:
        def start(self, files):
            return (slow if files == ["b"] else _FakeRunner._Done()), files, None

        def finish(self, proc, files, _log):
            return (4, {}, "usage error") if files == ["a"] else (0, {}, "")

    with pytest.raises(mts.LegError, match="exited 4"):
        mts._parallel(Runner(), [["a"], ["b"]], "shard")
    assert slow.poll() is not None  # killed and reaped, never left under the next checkout


def test_a_red_outside_the_selected_files_is_a_leg_failure():
    runner = _FakeRunner({("tests/elsewhere.py::test_x", "call"): "boom"})
    with pytest.raises(mts.LegError, match="red outside the selected files"):
        mts.differential(["tests/test_a.py"], "M", "B", runner, 1, compare=False)


def test_a_start_that_fails_still_reaps_the_groups_already_started():
    slow = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])

    class Runner:
        def start(self, files):
            if files == ["b"]:
                raise OSError("too many open files")
            return slow, files, None

        def finish(self, proc, files, _log):
            return 0, {}, ""

    with pytest.raises(OSError, match="too many open files"):
        mts._parallel(Runner(), [["a"], ["b"]], "shard")
    assert slow.poll() is not None


def test_an_interrupt_during_the_base_run_stays_an_interrupt_when_the_restore_fails(monkeypatch):
    runner = _FakeRunner({("tests/test_a.py::test_a", "call"): "boom"})
    calls = []

    def checkout(commit):
        calls.append(commit)
        if len(calls) == 2:
            raise KeyboardInterrupt  # mid base checkout
        if len(calls) == 3:
            raise mts.LegError("the restore failed")

    monkeypatch.setattr(mts, "_checkout", checkout)
    with pytest.raises(KeyboardInterrupt):
        mts.differential(["tests/test_a.py"], "M", "B", runner, 1, compare=True)


def test_a_failed_restore_keeps_the_first_error(monkeypatch):
    runner = _FakeRunner({("tests/test_a.py::test_a", "call"): "boom"})
    calls = []

    def checkout(commit):
        calls.append(commit)
        if len(calls) == 2:
            raise mts.LegError("the base checkout failed")
        if len(calls) == 3:
            raise mts.LegError("the restore failed")

    monkeypatch.setattr(mts, "_checkout", checkout)
    with pytest.raises(mts.LegError) as exc:
        mts.differential(["tests/test_a.py"], "M", "B", runner, 1, compare=True)
    assert "the base checkout failed" in str(exc.value) and "the restore failed" in str(exc.value)
    assert calls == ["M", "B", "M"]


def test_a_leg_that_dies_without_a_verdict_leaves_the_in_progress_mark(
    tmp_path, monkeypatch, capsys
):
    repo = _repo(
        tmp_path,
        {
            "library_x.py": LIB_BASE,
            "tests/test_mod.py": "import library_x\n\ndef test_mod():\n    pass\n",
        },
    )
    base, _merge_sha = _merge(repo, {"library_x.py": LIB_BRANCH})
    common = Path(_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    record = common / "fabrik-merge" / f"merge-tests-{base}.txt"

    def interrupted(*_a, **_k):
        raise KeyboardInterrupt  # not an Exception: no handler runs, as a signal's death

    monkeypatch.setattr(mts, "differential", interrupted)
    with pytest.raises(KeyboardInterrupt):
        _run(repo, monkeypatch, capsys)
    assert record.read_text() == "#leg-failed\tin-progress\n"
    monkeypatch.undo()
    rc, out = _run(repo, monkeypatch, capsys)  # a green leg leaves no record behind
    assert rc == 0 and not record.exists(), out


def test_an_unreadable_failure_record_is_a_leg_failure(tmp_path):
    runner = mts._Runner(tmp_path)
    rec = tmp_path / "torn.jsonl"
    rec.write_text(
        '{"id": "tests/test_x.py::test_x", "when": "call", "msg": "boo'
    )  # killed mid-write
    log = tmp_path / "log.txt"
    log.write_text("")
    proc = subprocess.Popen(["true"])
    with pytest.raises(mts.LegError, match="unreadable failure record"):
        runner.finish(proc, rec, log)


def test_the_merge_tests_line_runs_the_selector_as_the_merge_leg_does(tmp_path):
    """`.fabrik/merge-tests` executed the way `_run_owner_leg` runs it — `sh -e -c <its text>` in
    the build tree with FABRIK_MERGE_CHECK=1 — in a repo whose common dir holds a `.venv`."""
    repo = _repo(tmp_path, {"README": "x\n", "tests/test_ok.py": "def test_ok():\n    pass\n"})
    (repo / "scripts").mkdir()
    (repo / "scripts" / "merge_test_select.py").write_bytes(SCRIPT.read_bytes())
    venv = repo / ".venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").symlink_to(sys.executable)
    _merge(repo, {"README": "y\n"})
    text = (ROOT / ".fabrik" / "merge-tests").read_text(encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "PYTEST_ADDOPTS"}
    r = subprocess.run(
        ["sh", "-e", "-c", text],
        cwd=repo,
        env={**env, "FABRIK_MERGE_CHECK": "1"},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1].startswith("merge-tests: green"), r.stdout


def test_the_crash_line_is_compared_without_the_runs_temp_paths():
    a = "AssertionError: /tmp/pytest-of-ozgur/pytest-4644/test_x0/out.txt missing"
    b = "AssertionError: /tmp/pytest-of-ozgur/pytest-4651/test_x0/out.txt missing"
    assert a != b and mts.normalise(a) == mts.normalise(b)
    # under another TMPDIR too, and quoted
    c = "OSError: '/var/tmp/x/pytest-of-ci/pytest-7/test_x0/out.txt'"
    d = "OSError: '/var/tmp/x/pytest-of-ci/pytest-9/test_x0/out.txt'"
    assert mts.normalise(c) == mts.normalise(d)
    # only pytest's root: two failures naming different paths of their own stay different
    assert mts.normalise("FileNotFoundError: /tmp/fabrik_lib_check") != mts.normalise(
        "FileNotFoundError: /tmp/zzz_other_thing"
    )
    assert mts.normalise("assert 1 == 2") != mts.normalise("assert 1 == 3")
    # an object's address in its repr changes in every process
    e = "assert not True\n +  where True = <function exists at 0x7f3a1c2b9e40>('leftover.flag')"
    f = "assert not True\n +  where True = <function exists at 0x7f88d0a1b160>('leftover.flag')"
    assert mts.normalise(e) == mts.normalise(f)
    assert mts.normalise("value 0x10") != mts.normalise(
        "value 0x20"
    )  # a hex VALUE is not an address
    # a default tempfile name changes in every run; a named directory is the failure's own
    assert mts.normalise("missing /tmp/tmpk3j9_2xq/out") == mts.normalise(
        "missing /tmp/tmpzz81_q0a/out"
    )
    assert mts.normalise("missing /tmp/tmpfiles_old/out") != mts.normalise(
        "missing /tmp/tmpfiles_new/out"
    )
    # only as a path component: an identifier that happens to read tmp + 8 is the failure's own
    assert mts.normalise("NameError: name 'tmp_results' is not defined") != mts.normalise(
        "NameError: name 'tmp_resultz' is not defined"
    )


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
    # live, 2026-10-24: fleet's request merged green under touched-tests-only, then reddened this
    # grader on master (the coordinator's report; W-b4ebe9f7)
    ("66e37e977", "tests/test_hub_write_root.py"),
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


# --- W-347cd0c3: a rebuild after a ledger-only base move re-tests nothing ------------------------

GREEN_REPO = {
    "library_x.py": "VALUE = 1\n",
    "tests/test_mod.py": "import library_x\n\ndef test_mod():\n    assert library_x.VALUE == 1\n",
    ".fabrik/work/W-00000001.json": "{}\n",
    "notes.txt": "notes\n",
}


def _green_record(repo: Path, branch_head: str) -> Path:
    common = Path(_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    return common / "fabrik-merge" / f"merge-tests-green-{branch_head}.txt"


def _rebuild(repo: Path, base_files: dict[str, str | None]) -> str:
    """What `_merge_into_base` does after a failed CAS: the base moved (``base_files`` committed on
    the merge's first parent), and the same branch head is merged ``--no-ff`` again."""
    _git(repo, "checkout", "-q", "-f", "master")
    _git(repo, "reset", "-q", "--hard", "HEAD^1")
    _write(repo, base_files)
    _git(repo, "add", "-A", "--", *base_files)  # never the leg's own __pycache__
    _git(repo, "commit", "-qm", "chore(work): the base moves")
    _git(repo, "merge", "--no-ff", "-q", "-m", "merge again", "feat")
    return _git(repo, "rev-parse", "HEAD")


def test_a_rebuild_after_only_ledger_moves_skips_the_re_test(tmp_path, monkeypatch, capsys):
    repo = _repo(tmp_path, GREEN_REPO)
    _base, first = _merge(repo, {"library_x.py": "VALUE = 1\n# the branch\n"})
    feat = _git(repo, "rev-parse", "feat")
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0 and "1 test file(s)" in out, out
    assert _green_record(repo, feat).read_text().strip() == first
    second = _rebuild(repo, {".fabrik/work/W-00000001.json": '{"a": 1}\n', "CHANGELOG.md": "x\n"})
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0, out
    assert "test file(s) from" not in out, out  # no selection, no leg
    assert (
        f"re-test skipped — only ledger/work-item paths changed since the green merge {first[:12]}"
        in out
    ), out
    assert out.strip().splitlines()[-1].startswith("merge-tests: green"), out
    assert _green_record(repo, feat).read_text().strip() == second  # the latest green merge


def test_a_green_record_short_circuits_only_when_valid_and_ledger_only(
    tmp_path, monkeypatch, capsys
):
    repo = _repo(tmp_path, GREEN_REPO)
    _base, first = _merge(repo, {"library_x.py": "VALUE = 1\n# the branch\n"})
    feat = _git(repo, "rev-parse", "feat")
    assert _run(repo, monkeypatch, capsys)[0] == 0
    record = _green_record(repo, feat)
    # a base move touching any path outside the SKIP set re-runs the full selection
    _rebuild(repo, {"notes.txt": "the base moved\n"})
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0 and "1 test file(s)" in out and "re-test skipped" not in out, out
    # ... and so does one touching a ledger AND a path outside the set (every path must be SKIP)
    _rebuild(repo, {".fabrik/work/W-00000001.json": '{"c": 3}\n', "notes.txt": "again\n"})
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0 and "1 test file(s)" in out and "re-test skipped" not in out, out
    # each invalid record is ignored, with its reason, and the full selection runs
    head = _rebuild(repo, {".fabrik/work/W-00000001.json": '{"b": 2}\n'})
    plain = _git(repo, "rev-parse", "HEAD^1")  # a one-parent commit
    for text, why in (
        ("not a sha\n", "not a commit id"),
        ("f" * 40 + "\n", "names no commit here"),
        (head + "\n", "it names this merge"),
        (plain + "\n", "not a merge of this branch head"),
    ):
        record.write_text(text)
        rc, out = _run(repo, monkeypatch, capsys)
        assert rc == 0 and f"green record ignored ({why})" in out, (text, out)
        assert "1 test file(s)" in out and "re-test skipped" not in out, (text, out)
    # a green merge whose base is not behind this one (another line of history) is ignored too
    _git(repo, "checkout", "-q", "-f", "--orphan", "other")
    _git(repo, "rm", "-rqf", ".")
    _write(repo, {"other.txt": "o\n"})
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "unrelated root")
    _git(repo, "merge", "--no-ff", "-q", "--allow-unrelated-histories", "-m", "m", "feat")
    record.write_text(_git(repo, "rev-parse", "HEAD") + "\n")
    _git(repo, "checkout", "-q", "-f", "--detach", head)
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0 and "green record ignored (its base is not behind this one)" in out, out


def test_the_green_record_is_written_only_on_a_green_merge_check(tmp_path, monkeypatch, capsys):
    repo = _repo(tmp_path, GREEN_REPO)
    _merge(repo, {"library_x.py": "VALUE = 2\n"})  # test_mod goes red
    feat = _git(repo, "rev-parse", "feat")
    record = _green_record(repo, feat)
    assert _run(repo, monkeypatch, capsys)[0] == 1 and not record.exists()
    _git(repo, "checkout", "-q", "-f", "master")
    assert _run(repo, monkeypatch, capsys, args=("--list",))[0] == 0 and not record.exists()
    _git(repo, "update-ref", "refs/remotes/origin/master", "HEAD^1")
    rc, out = _run(repo, monkeypatch, capsys, merge_check=False)
    assert rc == 1 and not record.exists(), out
    # a record that cannot be written leaves a green verdict green, and says so
    _git(repo, "checkout", "-q", "-f", "master")
    _git(repo, "reset", "-q", "--hard", "HEAD^1")
    _git(repo, "branch", "-qD", "feat")
    _merge(repo, {"library_x.py": "VALUE = 1\n# fine\n"})
    record = _green_record(repo, _git(repo, "rev-parse", "feat"))
    record.mkdir(parents=True)  # os.replace onto a directory fails
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0 and "green record not written" in out, out
    assert out.strip().splitlines()[-1].startswith("merge-tests: green"), out


class _ScriptedRunner:
    """Each start takes the next scripted reds; records the files of every run, in order."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls: list[list[str]] = []

    def start(self, files):
        self.calls.append(list(files))
        return _FakeRunner._Done(), self.replies.pop(0), None

    def finish(self, _proc, reds, _log):
        return (1 if reds else 0), dict(reds), "tail"

    def run(self, files):
        return self.finish(*self.start(files))


def test_a_flaky_red_runs_no_ordered_base_shard(tmp_path, monkeypatch):
    """W-d5d1d394: a red green alone AND in its shard's order was flaky — the base has no verdict of
    its to compare, so its shard is not re-run there. The 8-shard hub leg of 2026-10-27 started
    exactly this base run (its ordered confirm passed, 1389 tests in 478 s), beside master reds
    confirmed alone (W-d5d1d394 design.md, cause (2))."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tests").mkdir()
    for name in ("test_a.py", "test_b.py"):
        (tmp_path / "tests" / name).write_text("")
    master_red = ("tests/test_a.py::test_master", "call")
    flaky = ("tests/test_b.py::test_flaky", "call")
    checkouts: list[str] = []
    monkeypatch.setattr(mts, "_checkout", checkouts.append)
    runner = _ScriptedRunner(
        [
            {master_red: "boom"},  # shard of test_a
            {flaky: "timing"},  # shard of test_b
            {master_red: "boom"},  # the serial confirm: the flaky red is green alone
            {},  # the ordered confirm of test_b's shard: green in order too
            {master_red: "boom"},  # the base alone run of test_a: the same crash, pre-existing
            {},  # an ordered base run of test_b's shard, were one (wrongly) started
        ]
    )

    new, out = mts.differential(
        ["tests/test_a.py", "tests/test_b.py"], "M", "B", runner, 2, compare=True
    )

    assert new == []
    assert any("FLAKY" in line and "test_flaky" in line for line in out), out
    assert any("pre-existing on the base" in line for line in out), out
    assert runner.calls[-1] == ["tests/test_a.py"], runner.calls  # the base alone run was the last
    assert len(runner.calls) == 5, runner.calls  # no ordered shard of test_b ran on the base
    assert checkouts.count("B") == 1, checkouts


def _two_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tests").mkdir()
    for name in ("test_a.py", "test_b.py"):
        (tmp_path / "tests" / name).write_text("")
    checkouts: list[str] = []
    monkeypatch.setattr(mts, "_checkout", checkouts.append)
    return checkouts


def test_a_red_found_only_in_order_keeps_its_ordered_base_run(tmp_path, monkeypatch):
    """The half of the W-d5d1d394 rule that stays: a red green alone but red in its shard's order is
    compared in that order on the base, so one that is red there too reads pre-existing, not NEW."""
    _two_files(tmp_path, monkeypatch)
    order_red = ("tests/test_b.py::test_order", "call")
    runner = _ScriptedRunner(
        [
            {order_red: "leftover"},  # the one shard (a, b)
            {},  # the serial confirm: green alone
            {order_red: "leftover"},  # the ordered confirm: red in order
            {order_red: "leftover"},  # the ordered base run: red there too
        ]
    )

    new, out = mts.differential(
        ["tests/test_a.py", "tests/test_b.py"], "M", "B", runner, 1, compare=True
    )

    assert new == [], out
    assert any("pre-existing on the base" in line and "test_order" in line for line in out), out
    assert runner.calls[-1] == ["tests/test_a.py", "tests/test_b.py"], runner.calls


def test_a_flaky_red_beside_an_alone_red_runs_no_ordered_base_shard(tmp_path, monkeypatch):
    """A flaky red and a red confirmed alone in the SAME shard: the alone red is compared alone, and
    the shard is not re-run in order on the base for the flaky one."""
    checkouts = _two_files(tmp_path, monkeypatch)
    master_red = ("tests/test_a.py::test_master", "call")
    flaky = ("tests/test_b.py::test_flaky", "call")
    runner = _ScriptedRunner(
        [
            {master_red: "boom", flaky: "timing"},  # the one shard (a, b)
            {master_red: "boom"},  # the serial confirm: the flaky red is green alone
            {master_red: "boom"},  # the ordered confirm of the shard: the flaky red green in order
            {master_red: "boom"},  # the base alone run of test_a: the same crash, pre-existing
            {},  # an ordered base run of the shard, were one (wrongly) started
        ]
    )

    new, out = mts.differential(
        ["tests/test_a.py", "tests/test_b.py"], "M", "B", runner, 1, compare=True
    )

    assert new == [], out
    assert any("FLAKY" in line and "test_flaky" in line for line in out), out
    assert any("pre-existing on the base" in line and "test_master" in line for line in out), out
    assert runner.calls[-1] == ["tests/test_a.py"], runner.calls  # the base alone run was the last
    assert checkouts.count("B") == 1, checkouts


def test_an_alone_red_keeps_its_alone_base_verdict_beside_an_ordered_red(tmp_path, monkeypatch):
    """A red confirmed alone and a red found only in order share a shard: the ordered base run answers
    the ordered red only, so the alone red's base-alone comparison is never overwritten by its
    in-order crash line there (review W-d5d1d394 pass 1, B-1)."""
    _two_files(tmp_path, monkeypatch)
    alone_red = ("tests/test_a.py::test_k", "call")
    order_red = ("tests/test_b.py::test_k2", "call")
    runner = _ScriptedRunner(
        [
            {alone_red: "A", order_red: "C"},  # the one shard (a, b)
            {alone_red: "A"},  # the serial confirm: the order red is green alone
            {order_red: "C"},  # the ordered confirm: the order red is red in order
            {alone_red: "A"},  # the base alone run of test_a: the same crash, pre-existing
            {alone_red: "B", order_red: "C"},  # the ordered base run: another crash for test_k
        ]
    )

    new, out = mts.differential(
        ["tests/test_a.py", "tests/test_b.py"], "M", "B", runner, 1, compare=True
    )

    assert new == [], out
    assert any("pre-existing on the base — tests/test_a.py::test_k " in line for line in out), out
    assert any("pre-existing on the base — tests/test_b.py::test_k2 " in line for line in out), out


# ── W-c832e59f: shards balanced by recorded per-file duration ──────────────────────────────


def _loads(groups, weights):
    return [round(sum(weights.get(f, 0) + mts.IMPORT_S for f in g), 2) for g in groups]


def test_balance_puts_the_longest_files_on_the_lightest_shard():
    """Round-robin stacks the two heavy files of a sorted selection on one shard; the balance gives
    each its own, and many near-zero files spread instead of piling on shard 0 (the critiques' probe:
    200 zero-weight files went 201 on one shard under a bare least-load rule)."""
    weights = {"t/a.py": 100.0, "t/b.py": 1.0, "t/c.py": 100.0, "t/d.py": 1.0}
    files = sorted(weights)
    rr = [g for g in (files[i::2] for i in range(2)) if g]
    got = mts.balance(files, 2, weights)
    assert got == [["t/a.py", "t/b.py"], ["t/c.py", "t/d.py"]], got
    assert max(_loads(got, weights)) < max(_loads(rr, weights))

    heavy = {f"t/h{i}.py": 60.0 for i in range(8)}
    tiny = {f"t/z{i:02}.py": 0.0 for i in range(32)}
    weights = {**heavy, **tiny}
    sizes = [len(g) for g in mts.balance(sorted(weights), 8, weights)]
    assert max(sizes) - min(sizes) <= 1, sizes

    # the import constant counts: ten instant files are not free beside one 1 s file
    weights = {"t/a.py": 1.0, **{f"t/z{i}.py": 0.0 for i in range(10)}}
    got = mts.balance(sorted(weights), 2, weights)
    assert len(next(g for g in got if "t/a.py" in g)) >= 2, got


@pytest.mark.parametrize("n_files", [0, 1, 5, 17, 40])
@pytest.mark.parametrize("shards", [1, 2, 3, 8, 11])
def test_balance_without_a_record_is_the_round_robin_split(n_files, shards):
    files = [f"tests/test_{i:03}.py" for i in range(n_files)]
    assert mts.balance(files, shards, {}) == [
        g for g in (files[i::shards] for i in range(shards)) if g
    ]


def test_balance_weighs_an_unrecorded_file_at_the_median_of_the_recorded():
    """`b` is unrecorded among a=10, c=30, d=30: at the median (30) it leads the order and pairs
    with `d`; at a bare import constant it would trail and pair with `c` instead."""
    weights = {"t/a.py": 10.0, "t/c.py": 30.0, "t/d.py": 30.0}
    assert mts.balance(["t/a.py", "t/b.py", "t/c.py", "t/d.py"], 2, weights) == [
        ["t/b.py", "t/d.py"],
        ["t/a.py", "t/c.py"],
    ]


def test_balance_is_deterministic_and_drops_empty_shards():
    weights = {"t/x.py": 5.0, "t/y.py": 5.0, "t/a.py": 7.0}
    files = ["t/a.py", "t/x.py", "t/y.py"]
    one, two = mts.balance(files, 8, weights), mts.balance(files, 8, weights)
    assert one == two and len(one) == 3 and all(one), one
    assert all(g == sorted(g) for g in mts.balance(sorted(weights), 2, weights))


_DUR_BASE = {
    "library_x.py": "VALUE = 1\n",
    "tests/test_one.py": "import time, library_x\n\ndef test_one():\n    time.sleep(0.2)\n",
    "tests/test_two.py": "import library_x\n\ndef test_two():\n    pass\n",
}


def _durations_record(repo: Path) -> Path:
    return repo / ".git" / "fabrik-merge" / "merge-tests-durations.json"


def test_a_leg_records_durations_and_the_next_leg_splits_by_them(tmp_path, monkeypatch, capsys):
    repo = _repo(tmp_path, _DUR_BASE)
    _merge(repo, {"library_x.py": "VALUE = 1  # touched\n"})
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0, out
    rec = json.loads(_durations_record(repo).read_text(encoding="utf-8"))
    assert set(rec) == {"tests/test_one.py", "tests/test_two.py"}, rec
    assert rec["tests/test_one.py"] >= 0.2 > rec["tests/test_two.py"], rec
    assert "merge-tests: shards measured" in out and "shards planned" not in out, out

    _git(repo, "checkout", "-qb", "feat2")
    _write(repo, {"library_x.py": "VALUE = 1  # touched again\n"})
    _git(repo, "commit", "-qam", "change 2")
    _git(repo, "checkout", "-q", "master")
    _git(repo, "merge", "--no-ff", "-q", "-m", "merge 2", "feat2")
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0, out
    planned = [line for line in out.splitlines() if line.startswith("merge-tests: shards planned")]
    assert len(planned) == 1, out
    loads = [float(x) for x in planned[0].split("planned ", 1)[1].split()]
    assert max(loads) >= 0.2 + mts.IMPORT_S, planned  # test_one's shard carries its recorded time


@pytest.mark.parametrize(
    "text", ["{not json", "[1, 2]", '{"tests/test_one.py": "slow", "tests/test_two.py": -1}']
)
def test_a_bad_duration_record_is_ignored_not_fatal(tmp_path, monkeypatch, capsys, text):
    repo = _repo(tmp_path, _DUR_BASE)
    _merge(repo, {"library_x.py": "VALUE = 1  # touched\n"})
    _durations_record(repo).parent.mkdir(parents=True, exist_ok=True)
    _durations_record(repo).write_text(text, encoding="utf-8")
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0 and out.strip().splitlines()[-1].startswith("merge-tests: green"), out
    assert "shards planned" not in out, out  # nothing usable was recorded: today's split
    if not text.startswith('{"'):
        assert "duration record ignored" in out, out


def test_a_garbled_duration_line_is_skipped(tmp_path):
    runner = mts._Runner(tmp_path)
    first = tmp_path / "dur-1.jsonl"
    first.write_text(
        '{"f": "tests/test_a.py", "s": 1.5}\n{"f": "tests/test_a.py", "s": 0.5}\n{"f": "tests/te',
        encoding="utf-8",
    )
    later = tmp_path / "dur-2.jsonl"
    later.write_text(
        'garbage\n{"f": "tests/test_a.py", "s": 9}\n{"f": "tests/test_b.py", "s": 2}\n',
        encoding="utf-8",
    )
    runner.dur_files += [first, later]
    # the first run holding a file wins; a torn or garbage line is skipped
    assert runner.durations() == {"tests/test_a.py": 2.0, "tests/test_b.py": 2.0}


def test_a_duration_record_that_cannot_be_written_keeps_the_verdict(tmp_path, monkeypatch, capsys):
    repo = _repo(tmp_path, _DUR_BASE)
    _merge(repo, {"library_x.py": "VALUE = 1  # touched\n"})
    _durations_record(repo).mkdir(parents=True)  # a directory where the file goes: replace fails
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0 and "duration record not written" in out, out
    assert out.strip().splitlines()[-1].startswith("merge-tests: green"), out

    (tmp_path / "local").mkdir()
    other = _repo(tmp_path / "local", _DUR_BASE)
    _merge(other, {"library_x.py": "VALUE = 1  # touched\n"})
    _git(other, "update-ref", "refs/remotes/origin/master", "HEAD~1")
    rc, out = _run(other, monkeypatch, capsys, merge_check=False)
    assert rc == 0 and not _durations_record(other).exists(), (
        out
    )  # a branch-local leg records nothing


def test_a_merge_legs_shards_follow_the_recorded_durations(tmp_path, monkeypatch, capsys):
    """Three files, two shards: round-robin over the sorted selection pairs the two heavy files
    (one, two) on shard 0; the record splits them, so no planned shard carries both."""
    repo = _repo(
        tmp_path,
        {**_DUR_BASE, "tests/test_three.py": "import library_x\n\ndef test_three():\n    pass\n"},
    )
    _merge(repo, {"library_x.py": "VALUE = 1  # touched\n"})
    rec = _durations_record(repo)
    rec.parent.mkdir(parents=True)
    rec.write_text(
        json.dumps({"tests/test_one.py": 5, "tests/test_two.py": 5, "tests/test_three.py": 0.1}),
        encoding="utf-8",
    )
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0, out
    planned = next(line for line in out.splitlines() if "shards planned" in line)
    assert max(float(x) for x in planned.split("planned ", 1)[1].split()) < 6, planned


def test_a_shard_run_that_fails_still_saves_what_it_measured(tmp_path, monkeypatch):
    """The save sits in a `finally` around the shard run: a shard exiting 4 is a leg failure, and the
    files that did run still teach the next leg their cost."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("")

    class Runner(_FakeRunner):
        def finish(self, _proc, _files, _log):
            return 4, {}, "usage error"

        def durations(self):
            return {"tests/test_a.py": 3.0}

    record = tmp_path / "rec" / "d.json"
    with pytest.raises(mts.LegError, match="exited 4"):
        mts.differential(["tests/test_a.py"], "M", "B", Runner({}), 1, compare=True, record=record)
    assert json.loads(record.read_text(encoding="utf-8")) == {"tests/test_a.py": 3.0}


def test_the_duration_record_ignores_the_records_override(tmp_path, monkeypatch, capsys):
    """A pretest or `merge --queue` leg points FABRIK_MERGE_TESTS_RECORDS at a private directory
    deleted with the leg (merge_request.py `_run_leg`, the pretest); the durations still go to the
    common dir every leg shares, or those legs would never balance."""
    repo = _repo(tmp_path, _DUR_BASE)
    _merge(repo, {"library_x.py": "VALUE = 1  # touched\n"})
    private = tmp_path / "private"
    private.mkdir()
    monkeypatch.setenv("FABRIK_MERGE_TESTS_RECORDS", str(private))
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0, out
    assert _durations_record(repo).is_file(), out
    assert not list(private.glob("*durations*")), list(private.iterdir())
