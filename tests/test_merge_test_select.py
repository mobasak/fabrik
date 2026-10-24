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
    }
    assert mts.select(["src/fabrik/state.py"], imports) == [
        "tests/test_cont.py",
        "tests/test_dotted.py",
        "tests/test_from.py",
        "tests/test_list.py",
        "tests/test_paren.py",
        "tests/test_tab.py",
    ]
    # a top-level module has no import form beyond its own name
    assert mts.import_patterns("library_x.py") == set()


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
