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

    def start(self, files, until=()):
        return self._Done(), files, None

    def finish(self, _proc, _files, _log):
        return 1, dict(self.reds), "tail"

    def run(self, files):
        return self.finish(*self.start(files))


def test_a_failing_group_leaves_no_other_group_running():
    slow = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])

    class Runner:
        def start(self, files, until=()):
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
        def start(self, files, until=()):
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
        self.untils: list[list[str]] = []

    def start(self, files, until=()):
        self.calls.append(list(files))
        self.untils.append(sorted(until))
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


# ── W-c80361e4: an ordered re-run stops one item past the reds it verifies ─────────────────────

_STATE_IMPORT = "import sys, os\nsys.path.insert(0, os.path.dirname(__file__))\nimport state\n"
_POLLUTED = {
    "tests/state.py": "polluted = False\n",
    "tests/test_a.py": _STATE_IMPORT + "def test_pollute():\n    state.polluted = True\n",
    "tests/test_b.py": _STATE_IMPORT
    + "def test_red():\n    assert not state.polluted\n\ndef test_next():\n    pass\n\n"
    + "def test_later():\n    pass\n",
    "tests/test_c.py": "import os\nopen(os.environ['CUT_MARK'], 'a').write('c imported\\n')\n\n"
    + "def test_c():\n    pass\n",
}
_ABC = ["tests/test_a.py", "tests/test_b.py", "tests/test_c.py"]


def _cut_runner(tmp_path, monkeypatch, files):
    """A real `_Runner` over ``files`` written under tmp_path, run from there, outer cut unset."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.delenv("FABRIK_MERGE_TESTS_UNTIL", raising=False)
    monkeypatch.setenv("CUT_MARK", str(tmp_path / "mark.txt"))
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    return mts._Runner(work)


def _cut_run(runner, files, until):
    """One real run cut at ``until`` — `_Runner.run` takes none: only `_parallel` cuts."""
    return runner.finish(*runner.start(files, until=until))


def _ran(runner) -> list[str]:
    """The node ids the last run executed, in order (its duration lines, one per report)."""
    out: list[str] = []
    for line in runner.dur_files[-1].read_text(encoding="utf-8").splitlines():
        nid = json.loads(line)["id"]
        if nid not in out:
            out.append(nid)
    return out


def test_an_ordered_cut_runs_to_the_last_red_and_collects_every_file(tmp_path, monkeypatch):
    """The cut keeps the shard's argv: test_c is still imported (D-1275's objection to a prefix run),
    the polluter before the red still runs, and the run stops one item past the red."""
    runner = _cut_runner(tmp_path, monkeypatch, _POLLUTED)
    rc, reds, _tail = _cut_run(runner, _ABC, ["tests/test_b.py::test_red"])
    assert rc == 1 and ("tests/test_b.py::test_red", "call") in reds, reds
    assert _ran(runner) == [
        "tests/test_a.py::test_pollute",
        "tests/test_b.py::test_red",
        "tests/test_b.py::test_next",
    ]
    assert (tmp_path / "mark.txt").read_text() == "c imported\n"
    # several listed reds: the cut follows the LAST of them, so the first never stops the run short
    # of a later one (review pass 1, B1: a `min` cut left test_later unrun, read FLAKY)
    _cut_run(runner, _ABC, ["tests/test_a.py::test_pollute", "tests/test_b.py::test_later"])
    assert "tests/test_b.py::test_later" in _ran(runner), _ran(runner)


@pytest.mark.parametrize(
    "content",
    [
        json.dumps(["tests/test_b.py::nope"]),  # an id the run does not collect
        json.dumps(["tests/test_b.py"]),  # a file-keyed collection error's id
        json.dumps(["tests/test_b.py::test_red", "tests/test_b.py::nope"]),
        "{",
        "5",
        "null",
        json.dumps({"tests/test_b.py::test_red": 1}),
        json.dumps([1, 2]),
        "[]",
        None,  # the file is missing
    ],
)
def test_an_until_the_run_cannot_honour_cuts_nothing(tmp_path, monkeypatch, content):
    """Every input the cut cannot honour runs the whole group, as before the cut, inside RAN — a
    plugin error there is INTERNALERROR, exit 3, a leg with no verdict."""
    _cut_runner(tmp_path, monkeypatch, _POLLUTED)
    work = tmp_path / "work"
    (work / "_fabrik_merge_tests_rec.py").write_text(mts._PLUGIN, encoding="utf-8")
    cut = tmp_path / "until.json"
    if content is not None:
        cut.write_text(content, encoding="utf-8")
    env = {
        **os.environ,
        "PYTHONPATH": str(work),
        "FABRIK_MERGE_TESTS_REC": str(tmp_path / "rec.jsonl"),
        "FABRIK_MERGE_TESTS_UNTIL": str(cut),
    }
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
        + ["-p", "_fabrik_merge_tests_rec", *_ABC],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "1 failed, 4 passed" in r.stdout and "deselected" not in r.stdout, r.stdout


_REORDERS = {
    # registered after the `-p` plugin: a plain trylast cut ran BEFORE it (Fable critique)
    "trylast": "@pytest.hookimpl(trylast=True)\ndef pytest_collection_modifyitems(items):\n"
    "    items.reverse()\n",
    # a wrapper reordering after `yield` ran AFTER a wrapper cut (review pass 1, A1)
    "wrapper": "@pytest.hookimpl(wrapper=True)\ndef pytest_collection_modifyitems(items):\n"
    "    res = yield\n    items.reverse()\n    return res\n",
    "tryfirst-wrapper": "@pytest.hookimpl(wrapper=True, tryfirst=True)\n"
    "def pytest_collection_modifyitems(items):\n    res = yield\n    items.reverse()\n"
    "    return res\n",
}


@pytest.mark.parametrize("hook", sorted(_REORDERS))
def test_the_cut_follows_a_conftest_reorder(tmp_path, monkeypatch, hook):
    """A conftest reorder that runs after the cut would move the polluter past it and deselect it:
    a false green. The cut acts in pytest_collection_finish, on the order every
    pytest_collection_modifyitems impl — plain, trylast or wrapper — left."""
    files = {
        "tests/state.py": "polluted = False\n",
        "tests/conftest.py": "import pytest\n\n\n" + _REORDERS[hook],
        "tests/test_a.py": _STATE_IMPORT + "def test_red():\n    assert not state.polluted\n",
        "tests/test_m.py": "def test_mid():\n    pass\n",
        "tests/test_z.py": _STATE_IMPORT + "def test_pollute():\n    state.polluted = True\n",
        "tests/test_0.py": "def test_zero():\n    pass\n",
        "tests/test_1.py": "def test_one():\n    pass\n",
    }
    runner = _cut_runner(tmp_path, monkeypatch, files)
    # reversed, the run is z, m, a, 1, 0: the cut keeps one past the red and drops test_0 — so it
    # is shown cutting on the reordered list, not merely standing down (review pass 1, B2)
    paths = ["tests/test_0.py", "tests/test_1.py", "tests/test_a.py", "tests/test_m.py"]
    paths.append("tests/test_z.py")
    rc, reds, tail = _cut_run(runner, paths, ["tests/test_a.py::test_red"])
    assert rc == 1 and ("tests/test_a.py::test_red", "call") in reds, tail
    assert "1 deselected" in tail and "tests/test_0.py::test_zero" not in _ran(runner), tail


def test_the_last_listed_red_keeps_its_teardown_line(tmp_path, monkeypatch):
    """With the listed item last, its teardown would also run every module and session finalizer
    and report an exception group — another crash line, read NEW or wrongly pre-existing against
    the base (Opus critique). One item kept past it keeps the whole run's line."""
    files = {
        "tests/conftest.py": "import pytest\n\n\n@pytest.fixture(scope='session', autouse=True)\n"
        "def sess():\n    yield\n    raise RuntimeError('session finalizer failed')\n",
        "tests/test_b.py": "import pytest\n\n\n@pytest.fixture(scope='module')\ndef mod():\n"
        "    yield\n    raise RuntimeError('module finalizer failed')\n\n\n"
        "def test_one(mod):\n    pass\n\n\ndef test_after(mod):\n    pass\n",
        "tests/test_c.py": "def test_c1():\n    pass\n\n\ndef test_c_last():\n    pass\n",
    }
    runner = _cut_runner(tmp_path, monkeypatch, files)
    paths = ["tests/test_b.py", "tests/test_c.py"]
    key = ("tests/test_b.py::test_after", "teardown")
    _rc, whole, _tail = runner.run(paths)
    rc, cut, tail = _cut_run(runner, paths, [key[0]])
    assert rc == 1 and "deselected" in tail, tail
    assert cut[key] == whole[key] == "RuntimeError: module finalizer failed", (cut, whole)


def test_the_ordered_runs_are_cut_after_their_own_reds(tmp_path, monkeypatch):
    """The ordered confirm is cut at its shard's reds not confirmed alone; the ordered base run at
    the order reds its base group still runs (test_c is gone on the base); the shard run and the
    alone runs are never cut."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tests").mkdir()
    for name in ("test_a.py", "test_b.py", "test_c.py"):
        (tmp_path / "tests" / name).write_text("")

    def checkout(commit):
        if commit == "B":
            (tmp_path / "tests" / "test_c.py").unlink(missing_ok=True)

    monkeypatch.setattr(mts, "_checkout", checkout)
    alone_red = ("tests/test_a.py::test_k", "call")
    order_red = ("tests/test_b.py::test_o", "call")
    flaky = ("tests/test_b.py::test_f", "call")
    gone = ("tests/test_c.py::test_g", "call")
    runner = _ScriptedRunner(
        [
            {alone_red: "A", order_red: "O", flaky: "F", gone: "G"},  # the one shard
            {alone_red: "A"},  # the serial confirm
            {order_red: "O", gone: "G"},  # the ordered confirm: two order reds, one flaky
            {alone_red: "A"},  # the base alone run
            {order_red: "O"},  # the ordered base run (test_c absent there)
        ]
    )

    new, out = mts.differential(_ABC, "M", "B", runner, 1, compare=True)

    assert runner.untils == [
        [],
        [],
        sorted([order_red[0], flaky[0], gone[0]]),
        [],
        [order_red[0]],
    ], runner.untils
    assert runner.calls[-1] == ["tests/test_a.py", "tests/test_b.py"], runner.calls
    assert [k for k, _ in new] == [gone], out


def test_a_run_without_until_drops_an_inherited_cut(tmp_path, monkeypatch):
    """A whole run never inherits a parent's cut (a nested leg, a test of this module), and a list
    larger than an environment value allows still launches: it rides in a file."""
    files = dict(_POLLUTED)
    files["tests/test_c.py"] = (
        "import os\n\n\ndef test_c():\n"
        "    open(os.environ['CUT_MARK'], 'a').write(repr(os.environ.get("
        "'FABRIK_MERGE_TESTS_UNTIL')) + '\\n')\n"
    )
    runner = _cut_runner(tmp_path, monkeypatch, files)
    junk = tmp_path / "parent-cut.json"
    junk.write_text(json.dumps(["tests/test_b.py::test_red"]), encoding="utf-8")
    monkeypatch.setenv("FABRIK_MERGE_TESTS_UNTIL", str(junk))
    rc, _reds, _tail = runner.run(_ABC)
    assert rc == 1 and "tests/test_c.py::test_c" in _ran(runner)
    assert (tmp_path / "mark.txt").read_text() == "None\n"
    # every listed id collected, so the cut is honoured, not merely survived (review pass 1, C2)
    pad = "a-long-parametrized-id-" * 3
    (tmp_path / "tests" / "test_wide.py").write_text(
        "import pytest\n\n\n"
        f"@pytest.mark.parametrize('i', range(2600), ids=lambda i: f'{pad}{{i:05d}}')\n"
        "def test_wide(i):\n    pass\n",
        encoding="utf-8",
    )
    big = [f"tests/test_wide.py::test_wide[{pad}{i:05d}]" for i in range(2500)]
    assert len(json.dumps(big)) > 128 * 1024
    rc, _reds, tail = _cut_run(runner, ["tests/test_wide.py"], big)
    assert rc == 0 and "2501 passed, 99 deselected" in tail, tail


# ── W-c832e59f: shards balanced by recorded per-file duration ──────────────────────────────


def _loads(groups, weights):
    return [round(sum(weights.get(f, 0) + mts.IMPORT_S for f in g), 2) for g in groups]


def test_balance_puts_the_longest_files_on_the_lightest_shard():
    """Round-robin stacks the two heavy files of a sorted selection on one shard; the balance gives
    each its own, and many near-zero files spread instead of piling on shard 0 (the critiques' probe:
    zero-weight files all landed on one shard under a bare least-load rule; here 32 beside 8 heavy)."""
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
    """`b` is unrecorded among a=10, c=20, d=60: it weighs their median, 20 — not the max (60), the
    mean (30) or nothing (0) — and the balance places it by that weight."""
    weights = {"t/a.py": 10.0, "t/c.py": 20.0, "t/d.py": 60.0}
    files = ["t/a.py", "t/b.py", "t/c.py", "t/d.py"]
    assert mts._run_weights(files, weights)["t/b.py"] == 20.0
    assert mts._run_weights(files, {}) == dict.fromkeys(
        files, 0.0
    )  # nothing recorded: equal weights
    assert mts.balance(files, 2, weights) == [["t/d.py"], ["t/a.py", "t/b.py", "t/c.py"]]


def test_balance_is_deterministic_and_drops_empty_shards():
    weights = {f"t/f{i}.py": float(i % 5) for i in range(13)}
    files = sorted(weights)
    want = mts.balance(files, 4, weights)
    for perm in (files[::-1], files[1::2] + files[::2]):  # the input order never changes the split
        assert mts.balance(perm, 4, weights) == want, perm
    assert len(want) <= 4 and all(g == sorted(g) for g in want), want
    sparse = mts.balance(["t/a.py", "t/x.py", "t/y.py"], 8, {"t/x.py": 5.0, "t/a.py": 7.0})
    assert len(sparse) == 3 and all(sparse), sparse  # more shards than files: no empty group


_DUR_BASE = {
    "library_x.py": "VALUE = 1\n",
    "tests/test_one.py": "import time, library_x\n\ndef test_one():\n    time.sleep(0.2)\n",
    "tests/test_two.py": "import library_x\n\ndef test_two():\n    pass\n",
}


def _durations_record(repo: Path) -> Path:
    return repo / ".git" / "fabrik-merge" / "merge-tests-durations.txt"


def test_a_leg_records_durations_and_the_next_leg_splits_by_them(tmp_path, monkeypatch, capsys):
    repo = _repo(tmp_path, _DUR_BASE)
    _merge(repo, {"library_x.py": "VALUE = 1  # touched\n"})
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0, out
    rec = json.loads(_durations_record(repo).read_text(encoding="utf-8"))
    assert set(rec) == {"tests/test_one.py", "tests/test_two.py"}, rec
    assert rec["tests/test_one.py"] >= 0.2 > rec["tests/test_two.py"], rec
    assert "merge-tests: shards measured" in out and "shards planned" not in out, out
    # never a `*.json` there: merge_request.py globs fabrik-merge/*.json as its merge records
    assert not list(_durations_record(repo).parent.glob("*.json")), out

    # this second leg checks that a record is read and planned from; the split itself is
    # test_a_merge_legs_shards_follow_the_recorded_durations's (two files spread the same either way)
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
    # test_one's shard carries its recorded run seconds (printed to 2 places, the record to 3)
    assert max(loads) >= rec["tests/test_one.py"] - 0.01, (planned, rec)


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ("{not json", True),
        ("[1, 2]", True),
        ("[" * 100000, True),  # too deep for json: RecursionError, not a leg failure
        ('{"tests/test_one.py": "slow", "tests/test_two.py": -1}', False),
        ('{"tests/test_one.py": true, "tests/test_two.py": NaN}', False),
        ('{"tests/test_one.py": Infinity, "tests/test_two.py": ' + "9" * 400 + "}", False),
    ],
)
def test_a_bad_duration_record_is_ignored_not_fatal(tmp_path, monkeypatch, capsys, text, said):
    repo = _repo(tmp_path, _DUR_BASE)
    _merge(repo, {"library_x.py": "VALUE = 1  # touched\n"})
    _durations_record(repo).parent.mkdir(parents=True, exist_ok=True)
    _durations_record(repo).write_text(text, encoding="utf-8")
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0 and out.strip().splitlines()[-1].startswith("merge-tests: green"), out
    assert "shards planned" not in out, out  # nothing usable was recorded: today's split
    assert ("duration record ignored" in out) is said, out


def test_an_unreadable_duration_record_is_ignored_not_fatal(tmp_path, capsys):
    rec = tmp_path / "d.txt"
    rec.write_bytes(b'{"tests/test_a.py": 1, "\xff": 2}')
    assert mts._load_durations(rec) == {}
    assert "duration record ignored (UnicodeDecodeError" in capsys.readouterr().out


def test_a_save_merges_over_the_old_record_and_drops_files_gone_from_the_tree(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tests").mkdir()
    for name in ("test_a.py", "test_b.py"):
        (tmp_path / "tests" / name).write_text("")
    rec = tmp_path / "rec.txt"
    rec.write_text(
        json.dumps({"tests/test_a.py": 9.0, "tests/test_b.py": 4.0, "tests/test_gone.py": 7.0}),
        encoding="utf-8",
    )
    mts._save_durations(rec, {"tests/test_a.py": 1.0}, complete=True)
    # a's new value replaces the old, b (not run this leg) keeps its own, a deleted file is dropped
    assert json.loads(rec.read_text(encoding="utf-8")) == {
        "tests/test_a.py": 1.0,
        "tests/test_b.py": 4.0,
    }
    mts._save_durations(rec, {"tests/test_a.py": 0.5, "tests/test_b.py": 6.0}, complete=False)
    # an incomplete shard run only raises a value: a killed file's partial sum never lowers it
    assert json.loads(rec.read_text(encoding="utf-8")) == {
        "tests/test_a.py": 1.0,
        "tests/test_b.py": 6.0,
    }


def test_a_failed_duration_append_never_fails_the_test_run(tmp_path, monkeypatch):
    """The plugin's duration line is advisory: an unwritable FABRIK_MERGE_TESTS_DUR (here a
    directory) must not raise inside the pytest hook, which pytest turns into INTERNALERROR."""
    plugin: dict = {}
    exec(mts._PLUGIN, plugin)  # noqa: S102 — the plugin source the leg writes, run as pytest would
    monkeypatch.setenv("FABRIK_MERGE_TESTS_DUR", str(tmp_path))
    monkeypatch.setenv("FABRIK_MERGE_TESTS_REC", str(tmp_path / "rec.jsonl"))

    class Report:
        nodeid, failed, when, duration = "tests/test_a.py::test_a", False, "call", 0.1

    plugin["pytest_runtest_logreport"](Report())  # no exception


def test_a_garbled_duration_line_is_skipped(tmp_path):
    runner = mts._Runner(tmp_path)
    first = tmp_path / "dur-1.jsonl"
    first.write_text(
        '{"f": "tests/test_a.py", "s": 1.5}\n{"f": "tests/test_a.py", "s": 0.5}\n{"f": "tests/te',
        encoding="utf-8",
    )
    later = tmp_path / "dur-2.jsonl"
    later.write_text(
        'garbage\n{"f": "tests/test_a.py", "s": 9}\n{"f": "tests/test_b.py", "s": 2}\n'
        '{"f": "tests/test_b.py", "s": "x"}\n{"f": "tests/test_b.py", "s": -1}\n'
        '{"f": "tests/test_b.py", "s": NaN}\n[1]\n' + "[" * 100000 + "\n",
        encoding="utf-8",
    )
    runner.dur_files += [first, later]
    # only the first `runs` runs count (the shard run; a later confirm run never does), a torn or
    # garbage line is skipped, and a file in several of those runs (a split file) is summed
    assert runner.durations(1) == {"tests/test_a.py": 2.0}
    assert runner.totals == [2.0]
    assert runner.durations(2) == {"tests/test_a.py": 11.0, "tests/test_b.py": 2.0}
    assert runner.totals == [2.0, 11.0]


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


def test_a_shard_run_that_fails_still_saves_what_it_measured(tmp_path, monkeypatch, capsys):
    """The save sits in a `finally` around the shard run: a shard exiting 4 is a leg failure, and the
    files that did run still teach the next leg their cost."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("")

    class Runner(_FakeRunner):
        def finish(self, _proc, _files, _log):
            return 4, {}, "usage error"

        def durations(self, runs, nodes_of=frozenset()):
            self.totals = [3.0]
            return {"tests/test_a.py": 3.0}

    record = tmp_path / "rec" / "d.txt"
    with pytest.raises(mts.LegError, match="exited 4"):
        mts.differential(
            ["tests/test_a.py"],
            "M",
            "B",
            Runner({}),
            1,
            compare=True,
            weights={"tests/test_a.py": 2.0},
            record=record,
        )
    assert json.loads(record.read_text(encoding="utf-8")) == {"tests/test_a.py": 3.0}
    # planned and measured are both run seconds, no import constant, so they compare
    out = capsys.readouterr().out
    assert (
        "merge-tests: shards planned 2.00\n" in out and "merge-tests: shards measured 3.00\n" in out
    )

    # the failed run is incomplete: its partial 3.0 never lowers a recorded 9.0
    record.write_text(json.dumps({"tests/test_a.py": 9.0}), encoding="utf-8")
    with pytest.raises(mts.LegError, match="exited 4"):
        mts.differential(["tests/test_a.py"], "M", "B", Runner({}), 1, compare=True, record=record)
    assert json.loads(record.read_text(encoding="utf-8")) == {"tests/test_a.py": 9.0}

    class Broken(Runner):
        def durations(self, runs, nodes_of=frozenset()):
            raise RuntimeError("boom in the recording")

    # a recording that itself fails never replaces the shard run's own error
    with pytest.raises(mts.LegError, match="exited 4"):
        mts.differential(["tests/test_a.py"], "M", "B", Broken({}), 1, compare=True, record=record)
    assert "duration record not written (RuntimeError" in capsys.readouterr().out


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


# --- W-231f4695 / W-3ba57940: a heavy file runs as node groups across the shards ---------------
# Measured 2026-10-28: tests/test_assemble_dispatch_step.py (1,462 s, a tree grader) set the wall of
# 20 of master's last 20 merge legs, because balance() places files whole.


def _heavy_repo(tmp_path: Path, heavy: str, weights: dict[str, float]) -> Path:
    repo = _repo(
        tmp_path,
        {
            "library_x.py": "VALUE = 1\n",
            "tests/test_heavy.py": heavy,
            "tests/test_light.py": "import library_x\n\ndef test_light():\n    pass\n",
        },
    )
    rec = _durations_record(repo)
    rec.parent.mkdir(parents=True)
    rec.write_text(json.dumps(weights), encoding="utf-8")
    return repo


def _pid_heavy(log: Path, n: int = 4, body: str = "pass") -> str:
    """``n`` tests that each append their process id to ``log``, then run ``body``."""
    tests = "".join(
        f"\ndef test_{c}():\n    open({str(log)!r}, 'a').write(f'{{os.getpid()}}\\n')\n    {body}\n"
        for c in "abcdefgh"[:n]
    )
    return "import os, library_x\n" + tests


_HEAVY = {"tests/test_heavy.py": 100, "tests/test_light.py": 0.1}


def test_a_heavy_file_runs_as_node_groups_across_shards(tmp_path, monkeypatch, capsys):
    log = tmp_path / "pids.log"
    repo = _heavy_repo(tmp_path, _pid_heavy(log), _HEAVY)
    _merge(repo, {"library_x.py": "VALUE = 1  # touched\n"})
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0, out
    assert "merge-tests: split tests/test_heavy.py into 2 node group(s)" in out, out
    pids = log.read_text().split()
    assert len(pids) == 4 and len(set(pids)) == 2, pids  # every test ran once, in two processes


def test_a_light_file_is_never_split():
    def collect(f):
        raise AssertionError(f"collected {f}")  # a file within its share is never collected

    files = ["tests/test_a.py", "tests/test_b.py"]
    # within its share (two 100 s files over two shards), and over its share but under SPLIT_MIN_S
    for weights in (dict.fromkeys(files, 100.0), {files[0]: 10.0, files[1]: 0.1}):
        units, _weights, split = mts._split_heavy(files, weights, 2, collect)
        assert units == files and split == {}, (weights, units, split)
    # one shard: nothing to spread over
    units, _weights, split = mts._split_heavy(files, {files[0]: 100.0, files[1]: 0.1}, 1, collect)
    assert units == files and split == {}, (units, split)


def test_a_split_files_red_is_re_run_by_its_node_id():
    reds = {("tests/h.py::test_a[x y]", "call"): "m", ("tests/w.py::test_b", "call"): "m"}
    assert mts._reruns(reds, {"tests/h.py"}) == ["tests/h.py::test_a[x y]", "tests/w.py"]
    # in the file's collection order, not by name; a split file's module-level error re-runs the file
    reds = {("tests/h.py::b", "call"): "m", ("tests/h.py::a", "call"): "m"}
    assert mts._reruns(reds, {"tests/h.py"}, {"tests/h.py::b": 0, "tests/h.py::a": 1}) == [
        "tests/h.py::b",
        "tests/h.py::a",
    ]
    assert mts._reruns({("tests/h.py", "collect"): "m"}, {"tests/h.py"}) == ["tests/h.py"]


def test_a_shard_of_node_ids_owns_its_reds_and_its_files_module_error():
    members = ["tests/h.py::a", "tests/h.py::b[x y]", "tests/w.py"]
    for nid in ("tests/h.py::a", "tests/h.py::b[x y]", "tests/w.py::t", "tests/h.py"):
        assert mts._owns(members, nid), nid
    for nid in ("tests/h.py::c", "tests/h.py2", "tests/v.py::t"):
        assert not mts._owns(members, nid), nid


def test_the_base_side_keeps_only_what_the_base_can_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tests").mkdir()
    for name in ("h.py", "w.py"):
        (tmp_path / "tests" / name).write_text("")
    split = {"tests/h.py": []}
    monkeypatch.setattr(mts, "_collect", lambda f: ["tests/h.py::a"])
    units = ["tests/h.py::a", "tests/h.py::new", "tests/gone.py", "tests/w.py", "tests/h.py::a"]
    # a node the base lacks and a file the base lacks are dropped; nothing twice
    assert mts._on_base(units, split) == ["tests/h.py::a", "tests/w.py"]
    # a base that will not collect the file runs it whole (a pre-existing red must stay pre-existing)
    monkeypatch.setattr(mts, "_collect", lambda f: None)
    assert mts._on_base(["tests/h.py::a", "tests/h.py::b"], split) == ["tests/h.py"]


class _Proc:
    def __init__(self, rc: int, out: str) -> None:
        self.returncode, self.stdout = rc, out


@pytest.mark.parametrize(
    ("result", "want"),
    [
        (
            _Proc(
                0, "t.py::a\nt.py::b[x y]\nt.py::a\nother.py::c\n\n2 tests collected\nt.py::zz\n"
            ),
            ["t.py::a", "t.py::b[x y]"],
        ),
        (_Proc(2, "t.py::a\nt.py::b\n"), None),
        (subprocess.TimeoutExpired("pytest", 1), None),
        (OSError("no python"), None),
        (UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"), None),
    ],
)
def test_collect_reads_ids_up_to_the_blank_line_and_fails_to_none(monkeypatch, result, want):
    def run(argv, **kw):
        assert kw.get("errors") == "replace"  # a conftest's raw bytes never raise
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(mts.subprocess, "run", run)
    assert mts._collect("t.py") == want


def test_only_split_files_record_node_seconds_and_a_silent_shard_keeps_its_place(tmp_path):
    runner = mts._Runner(tmp_path)
    d1 = tmp_path / "d1.jsonl"
    d1.write_text(
        '{"f": "tests/a.py", "id": "tests/a.py::x", "s": 1}\n'
        '{"f": "tests/b.py", "id": "tests/b.py::y", "s": 2}\n',
        encoding="utf-8",
    )
    runner.dur_files += [tmp_path / "never-written.jsonl", d1]
    got = runner.durations(2, frozenset({"tests/a.py"}))
    assert got == {"tests/a.py": 1.0, "tests/b.py": 2.0, "tests/a.py::x": 1.0}, got
    assert runner.totals == [0.0, 3.0], runner.totals


def test_a_complete_run_replaces_a_split_files_node_keys(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "h.py").write_text("")
    rec = tmp_path / "d.txt"
    rec.write_text(json.dumps({"tests/h.py": 9, "tests/h.py::old": 5, "tests/h.py::a": 1}))
    mts._save_durations(rec, {"tests/h.py": 3, "tests/h.py::a": 2}, complete=True)
    assert json.loads(rec.read_text()) == {"tests/h.py": 3, "tests/h.py::a": 2}
    # a complete leg that ran the file whole keeps none of its old node keys (review pass 2)
    mts._save_durations(rec, {"tests/h.py": 4}, complete=True)
    assert json.loads(rec.read_text()) == {"tests/h.py": 4}
    # an incomplete run never drops a node key: it may not have reached that test
    rec.write_text(json.dumps({"tests/h.py::old": 5, "tests/h.py::a": 1}))
    mts._save_durations(rec, {"tests/h.py::a": 2}, complete=False)
    assert json.loads(rec.read_text()) == {"tests/h.py::a": 2, "tests/h.py::old": 5}


@pytest.mark.parametrize(
    "ids",
    [
        None,
        [],
        ["tests/test_heavy.py::test_a"],
    ],
)
def test_a_file_that_will_not_collect_cleanly_stays_whole(ids, capsys):
    units, _weights, split = mts._split_heavy(
        ["tests/test_heavy.py", "tests/test_light.py"], dict(_HEAVY), 2, lambda f: ids
    )
    assert "tests/test_heavy.py" in units and split == {}, (units, split)
    assert "merge-tests: tests/test_heavy.py kept whole (" in capsys.readouterr().out


def test_a_split_file_is_balanced_by_its_recorded_node_seconds():
    ids = [f"tests/test_heavy.py::test_{c}" for c in "abcde"]
    # the file ran 64 s; three nodes recorded 60 s; d and e (unrecorded) share the 4 s left over —
    # never the recorded median (1 s here, 340 s on the hub's heaviest file: phantom load)
    weights = {"tests/test_heavy.py": 64.0, "tests/test_light.py": 0.1}
    weights.update({ids[0]: 58.0, ids[1]: 1.0, ids[2]: 1.0})
    units, uw, split = mts._split_heavy(
        ["tests/test_heavy.py", "tests/test_light.py"], weights, 2, lambda f: ids
    )
    assert split["tests/test_heavy.py"] == [(i,) for i in ids], split
    assert uw[(ids[3],)] == uw[(ids[4],)] == 2.0, uw
    groups = mts.balance(units, 2, uw)
    assert [(ids[0],)] in groups, groups  # the slow test runs alone; the rest share the other shard


def test_equal_count_groups_are_contiguous_slices_weighed_by_the_files_share():
    ids = [f"tests/test_heavy.py::test_{c}" for c in "abcdefg"]
    units, uw, split = mts._split_heavy(
        ["tests/test_heavy.py", "tests/test_light.py"], dict(_HEAVY), 3, lambda f: ids
    )
    groups = split["tests/test_heavy.py"]
    assert groups == [tuple(ids[0:2]), tuple(ids[2:4]), tuple(ids[4:7])], groups
    assert [uw[g] for g in groups] == [100 / 3] * 3, uw


def test_node_ids_that_differ_between_two_collections_keep_the_file_whole(capsys):
    calls = iter([["t.py::a[1]", "t.py::b[1]"], ["t.py::a[2]", "t.py::b[2]"]])
    units, _uw, split = mts._split_heavy(
        ["t.py", "u.py"], {"t.py": 100, "u.py": 0.1}, 2, lambda f: next(calls)
    )
    assert "t.py" in units and split == {}, (units, split)
    assert (
        "t.py kept whole (its node ids differ between two collections)" in capsys.readouterr().out
    )
    # a second collection that fails is said as such, never as differing ids (review pass 2)
    calls = iter([["t.py::a", "t.py::b"], None])
    units, _uw, split = mts._split_heavy(
        ["t.py", "u.py"], {"t.py": 100, "u.py": 0.1}, 2, lambda f: next(calls)
    )
    assert "t.py" in units and split == {}, (units, split)
    assert "t.py kept whole (its second collection failed)" in capsys.readouterr().out


def test_a_leg_runs_each_shards_nodes_in_the_files_order(tmp_path, monkeypatch, capsys):
    # defined z, y, x, w: by name a shard would run w before x; the file's order is z, y, x, w
    log = tmp_path / "order.log"
    heavy = "import os, library_x\n" + "".join(
        f"\ndef test_{c}():\n    open({str(log)!r}, 'a').write(f'{{os.getpid()}} {c}\\n')\n"
        for c in "zyxw"
    )
    ids = [f"tests/test_heavy.py::test_{c}" for c in "zyxw"]
    repo = _heavy_repo(tmp_path, heavy, {**_HEAVY, **dict.fromkeys(ids, 1.0)})
    _merge(repo, {"library_x.py": "VALUE = 1  # touched\n"})
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0 and "into 4 node(s) by their recorded seconds" in out, out
    by_pid: dict[str, list[str]] = {}
    for line in log.read_text().splitlines():
        pid, name = line.split()
        by_pid.setdefault(pid, []).append(name)
    assert len(by_pid) == 2, by_pid
    for names in by_pid.values():
        assert names == sorted(names, key="zyxw".index), by_pid


def test_a_shard_runs_a_split_files_nodes_in_collection_order():
    rank = {"tests/t.py::b": 1, "tests/t.py::a[z]": 0, "tests/u.py::x": 0}
    got = mts._argv([("tests/t.py::b",), "tests/s.py", ("tests/t.py::a[z]",)], rank)
    assert got == ["tests/s.py", "tests/t.py::a[z]", "tests/t.py::b"], got


def test_a_leg_records_a_split_files_node_seconds_and_the_next_leg_uses_them(
    tmp_path, monkeypatch, capsys
):
    log = tmp_path / "pids.log"
    heavy = _pid_heavy(log) + "\ndef test_slow():\n    __import__('time').sleep(0.5)\n"
    repo = _heavy_repo(tmp_path, heavy, _HEAVY)
    _merge(repo, {"library_x.py": "VALUE = 1  # touched\n"})
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0 and "into 2 node group(s)" in out, out
    rec = json.loads(_durations_record(repo).read_text(encoding="utf-8"))
    # relative, not a sub-second ceiling: a loaded box may stall test_a's setup (review pass 1)
    slow, quick = rec["tests/test_heavy.py::test_slow"], rec["tests/test_heavy.py::test_a"]
    assert slow >= 0.5 and slow > quick, rec
    # the fixture's file runs in milliseconds; keep it heavy (its real 1,462 s twin is) and keep the
    # node seconds the leg just recorded
    rec["tests/test_heavy.py"] = 100
    _durations_record(repo).write_text(json.dumps(rec), encoding="utf-8")

    _git(repo, "checkout", "-qb", "feat2")
    _write(repo, {"library_x.py": "VALUE = 1  # touched again\n"})
    _git(repo, "commit", "-qam", "change 2")
    _git(repo, "checkout", "-q", "master")
    _git(repo, "merge", "--no-ff", "-q", "-m", "merge 2", "feat2")
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0, out
    assert "split tests/test_heavy.py into 5 node(s) by their recorded seconds" in out, out


def test_a_parametrized_id_with_a_space_is_split_and_run(tmp_path, monkeypatch, capsys):
    # 17 of the 89 ids of the hub's heaviest file hold a space in their brackets (critiques, 2026-10-28)
    log = tmp_path / "pids.log"
    heavy = (
        "import os, pytest, library_x\n\n"
        "@pytest.mark.parametrize('w', ['a b', 'c d', 'e f', 'g h'])\n"
        f"def test_p(w):\n    open({str(log)!r}, 'a').write(f'{{os.getpid()}}\\n')\n"
    )
    repo = _heavy_repo(tmp_path, heavy, _HEAVY)
    _merge(repo, {"library_x.py": "VALUE = 1  # touched\n"})
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0, out
    assert "split tests/test_heavy.py into 2 node group(s)" in out, out
    pids = log.read_text().split()
    assert len(pids) == 4 and len(set(pids)) == 2, pids


def _coupled(tests: str) -> str:
    """test_w sets a module flag that makes test_x red when the two share a process (an order red)."""
    bodies = {
        "w": "    global SEEN\n    SEEN = True\n",
        "x": "    assert not SEEN, 'run after test_w'\n",
    }
    return "SEEN = False\n" + "".join(
        f"\ndef test_{c}():\n{bodies.get(c, '    pass' + chr(10))}" for c in tests
    )


def test_an_order_red_in_a_split_group_the_base_lacks_a_node_of_still_gets_a_verdict(
    tmp_path, monkeypatch, capsys
):
    # the ordered base run re-runs the merge's group on the base, which lacks test_new: passed it,
    # pytest exits 4 and the leg had no verdict (review pass 1, B-sonnet)
    repo = _heavy_repo(tmp_path, _coupled("wxabc"), _HEAVY)
    _merge(repo, {"tests/test_heavy.py": _coupled("wnxabc")})
    rc, out = _run(repo, monkeypatch, capsys)
    assert "split tests/test_heavy.py into 2 node group(s)" in out, out
    assert "LEG FAILED" not in out, out
    assert rc == 0, out
    assert "pre-existing on the base — tests/test_heavy.py::test_x (call)" in out, out


def test_a_new_failing_test_added_inside_a_split_file_is_refused_as_new(
    tmp_path, monkeypatch, capsys
):
    # the base lacks the new node id: passed it, pytest exits 4 and the leg would read "no verdict"
    log = tmp_path / "pids.log"
    repo = _heavy_repo(tmp_path, _pid_heavy(log), _HEAVY)
    added = _pid_heavy(log) + "\ndef test_added():\n    assert False, 'new and red'\n"
    _merge(repo, {"tests/test_heavy.py": added})
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 1, out
    assert "split tests/test_heavy.py into 2 node group(s)" in out, out
    assert "merge-tests: NEW red — tests/test_heavy.py::test_added (call)" in out, out
    assert "LEG FAILED" not in out, out


def test_a_new_red_inside_a_split_file_is_refused(tmp_path, monkeypatch, capsys):
    log = tmp_path / "pids.log"
    heavy = _pid_heavy(log) + "\ndef test_value():\n    assert library_x.VALUE == 1\n"
    repo = _heavy_repo(tmp_path, heavy, _HEAVY)
    _merge(repo, {"library_x.py": "VALUE = 2\n"})
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 1, out
    assert "split tests/test_heavy.py into 2 node group(s)" in out, out
    assert "merge-tests: NEW red — tests/test_heavy.py::test_value (call)" in out, out
    assert "red outside the selected files" not in out, out


def test_a_pre_existing_red_inside_a_split_file_is_not_refused(tmp_path, monkeypatch, capsys):
    log = tmp_path / "pids.log"
    heavy = _pid_heavy(log) + "\ndef test_broken():\n    assert False, 'master is red here'\n"
    repo = _heavy_repo(tmp_path, heavy, _HEAVY)
    _merge(repo, {"library_x.py": "VALUE = 1  # touched\n"})
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0, out
    assert "split tests/test_heavy.py into 2 node group(s)" in out, out
    assert "pre-existing on the base — tests/test_heavy.py::test_broken (call)" in out, out


def test_a_split_files_duration_is_the_sum_of_its_groups(tmp_path, monkeypatch, capsys):
    log = tmp_path / "pids.log"
    repo = _heavy_repo(tmp_path, _pid_heavy(log, body="__import__('time').sleep(0.2)"), _HEAVY)
    _merge(repo, {"library_x.py": "VALUE = 1  # touched\n"})
    rc, out = _run(repo, monkeypatch, capsys)
    assert rc == 0, out
    assert "split tests/test_heavy.py into 2 node group(s)" in out, out
    rec = json.loads(_durations_record(repo).read_text(encoding="utf-8"))
    # four 0.2 s tests in two groups: the first group alone would record ~0.4
    assert rec["tests/test_heavy.py"] >= 0.75, rec
    # the measured line is per shard RUN: a per-file sum would print a split file's seconds on no shard
    measured = next(ln for ln in out.splitlines() if "shards measured" in ln)
    loads = [float(x) for x in measured.split("measured ", 1)[1].split()]
    assert len(loads) == 2 and min(loads) >= 0.35, measured
