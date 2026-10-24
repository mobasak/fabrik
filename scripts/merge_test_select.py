#!/usr/bin/env python3
# AFTER-EDIT: tests/test_merge_test_select.py, docs/reference/multi-agent-operating-model.md
"""The hub's merge-time test leg (``.fabrik/merge-tests``, W-4e756979).

Without an owner command ``merge_request.py`` runs only the ``tests/`` files a branch touched, so a
repo-wide grader the branch broke but never edited (the hub-write-root search, the contract's line
cites, a command's byte cap) ran nowhere until master was red: 29 red-master fixes in 25 days, the
measured branches each red ALONE before they merged. This runs, in the merge's build tree, every
test file that names a path the merge changed — by file name, module stem or directory — plus every
tree grader (a test running ``git ls-files``), in parallel shards, and refuses only a NEW red: one
failing on the merge that passes on the base, is absent there, or fails there with another crash
line. Master is not green on the full suite (16 ids red in a merge-shaped throwaway, 2026-10-24),
so refusing every red would refuse merges that did not cause it.

Range: in the merge leg (``FABRIK_MERGE_CHECK=1``) HEAD is the merge commit and its first parent the
base. A HEAD with one parent there is ``_base_alone``'s re-run: it re-runs the files of the new reds
recorded for that base under ``<git common dir>/fabrik-merge/``. Outside a merge check the base is
``git merge-base HEAD origin/master`` and nothing is recorded, so a branch can run the leg before it
asks for a merge.

Exit codes: 0 green (pre-existing and flaky reds printed) · 1 a new red · 2 cannot select · 3 the leg
itself failed (a shard exit other than 0/1/5, a checkout git refused) — the verdict is the LAST line.

Cobra (D-253): the cheapest way past this leg is a test whose text names nothing — a grader reaching
files through computed paths is selected only by a directory it spells or by ``ls-files``. Counter:
the miss rate is the red-master series itself (kaizen_waste.waste_red_master_rework), which keeps
measuring after this lands. The second cheapest is a red that is already red on master: it passes
until its crash line changes, so a broken grader on master mutes itself only for the SAME failure.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path

SHARDS = 8
# ledgers and work items change on nearly every branch and are named by hundreds of tests; their own
# graders (decision ids, the store) run in final_gate, so keying on them would select the suite
SKIP = re.compile(
    r"(CHANGELOG\.md|docs/DECISIONS\.md|INDEX\.md|docs/LESSONS_LEARNT\.md|\.fabrik/work/.*)"
)
TEST_FILE = re.compile(r"tests/(?:.*/)?test_[^/]*\.py")
# a directory spelled as a path segment in a test ("commands" / "_sources") selects only when its
# name is specific; these four are named by most of the suite
GENERIC_DIRS = frozenset({"scripts", "tests", "docs", "src"})
MIN_STEM = 6
# a test that lists the tracked tree reaches every file, a new one under a generic directory included
TREE_GRADER = "ls-files"
# pytest's own exits that still mean "the tests ran": 0 green, 1 failures, 5 nothing collected
RAN = (0, 1, 5)
# pytest's per-run temp root, under whatever TMPDIR the leg inherits: the one part of a crash line that
# differs between two runs of one failure (measured on master's reds: raw lines equal 7 of 16,
# with this replaced 16 of 16; a looser mkdtemp rule merged two different failures, so none)
_BASETEMP = re.compile(r"[^\s'\"]*/pytest-of-[^/\s]+/pytest-\d+/")
# and an object's address in its repr (`<function exists at 0x7f…>`), new in every process
_ADDRESS = re.compile(r"\bat 0x[0-9a-fA-F]+\b")
# and a path component `tempfile` names with its default prefix (`/tmpk3j9_2xq`: "tmp" + 8 of
# [a-z0-9_]); only as a path component, since an identifier like `tmp_results` is the failure's
# own, and a custom-prefix name is left alone (that rule merged two different failures)
_TMPNAME = re.compile(r"(?<=/)tmp[a-z0-9_]{8}(?![\w-])")
# a record line naming no id: the leg refused without a verdict, so the base-alone run measures nothing
_LEG_MARK = "#leg-failed"
# The recording plugin: one JSON line per failed report (a collection error's id is the file).
_PLUGIN = """
import json, os

def _crash(report):
    rc = getattr(getattr(report, "longrepr", None), "reprcrash", None)
    if rc is not None:
        return rc.message
    text = str(getattr(report, "longrepr", "") or "").strip().splitlines()
    return text[-1] if text else ""

def _write(report, when):
    with open(os.environ["FABRIK_MERGE_TESTS_REC"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"id": report.nodeid, "when": when, "msg": _crash(report)}) + "\\n")

def pytest_runtest_logreport(report):
    if report.failed:
        _write(report, report.when)

def pytest_collectreport(report):
    if report.failed:
        _write(report, "collect")
"""


class LegError(Exception):
    """The leg could not produce a verdict (exit 3)."""


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
    return r.stdout


def import_patterns(path: str) -> set[str]:
    """Regexes for the ways a test imports a module path: `fabrik.state` (dotted, never inside
    `fabrik.statement` or `xfabrik.state`), and `from fabrik import state` in any of its spellings —
    other names beside it, parentheses, line breaks, tabs, a backslash continuation. A top-level
    module (one part) has neither form; its file name and stem keys select it."""
    p = Path(path)
    if p.suffix != ".py":
        return set()
    mod = list(p.with_suffix("").parts)
    mod = mod[1:] if mod[:1] == ["src"] else mod
    if len(mod) < 2:
        return set()
    name = re.escape(mod[-1])
    pkg = r"\.".join(re.escape(m) for m in mod[:-1])
    return {
        rf"(?<![\w.]){pkg}\.{name}(?![\w])",
        # inside parentheses anything up to the `)` (names, line breaks, comments); without them
        # one logical line: names, commas, blanks and backslash continuations, never a next statement
        rf"\bfrom\s+{pkg}\s+import\s*(?:\([^)]*?|(?:[ \t\w,]|\\\n)*?)(?<![\w.]){name}(?![\w])",
    }


def keys_for(path: str) -> set[str]:
    """The strings whose presence in a test's text selects it for a change to ``path``."""
    p = Path(path)
    keys = {p.name}
    if len(p.stem) >= MIN_STEM:
        keys.add(p.stem)
    parent = p.parent.as_posix()
    if parent not in (".", "tests") and parent not in GENERIC_DIRS:
        keys.add(parent + "/")
        for q in ('"', "'"):
            keys.add(parent + q)
        last = p.parent.name
        if last not in GENERIC_DIRS:
            for q in ('"', "'"):
                keys.add(q + last + q)
    return keys


def select(changed: list[str], tests: dict[str, str]) -> list[str]:
    """``tests`` maps each test file to its text; returns the files to run, sorted."""
    keys: set[str] = set()
    mods: set[str] = set()
    picked = {p for p in changed if p in tests}
    for p in changed:
        if not SKIP.fullmatch(p):
            keys |= keys_for(p)
            mods |= import_patterns(p)
    bounded = re.compile("|".join(sorted(mods))) if mods else None
    if keys:
        for name, text in tests.items():
            if (
                TREE_GRADER in text
                or any(k in text for k in keys)
                or (bounded is not None and bounded.search(text))
            ):
                picked.add(name)
    return sorted(picked)


def normalise(msg: str) -> str:
    """A crash line with pytest's per-run temp root, object addresses and default `tempfile` names
    replaced, so two runs of one failure compare equal."""
    msg = _BASETEMP.sub("<basetemp>/", msg)
    return _TMPNAME.sub("tmp<mkdtemp>", _ADDRESS.sub("at 0x?", msg))


def _ignored() -> set[str]:
    """The files pyproject's pytest ``addopts`` ``--ignore``s: that flag skips a file only while a
    DIRECTORY is collected, so passed by name it would be collected (and fail its shard)."""
    try:
        with open("pyproject.toml", "rb") as fh:
            opts = tomllib.load(fh)["tool"]["pytest"]["ini_options"].get("addopts", "")
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return set()
    words = shlex.split(opts) if isinstance(opts, str) else list(opts)
    out = set()
    for i, w in enumerate(words):
        if w.startswith("--ignore="):
            out.add(w.split("=", 1)[1].rstrip("/"))
        elif w == "--ignore" and i + 1 < len(words):
            out.add(words[i + 1].rstrip("/"))
    return out


def _record_path(base: str) -> Path:
    common = Path(_git("rev-parse", "--path-format=absolute", "--git-common-dir").strip())
    return common / "fabrik-merge" / f"merge-tests-{base}.txt"


def _write_record(base: str, keys: list[str]) -> None:
    rec = _record_path(base)
    rec.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=rec.parent, prefix=rec.name + ".")  # never a shared temp name
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("".join(k + "\n" for k in keys))
    os.replace(tmp, rec)  # a reader never sees half a list


def _tests_here() -> dict[str, str]:
    ignored = _ignored()
    names = [
        p
        for p in _git("ls-files", "-z", "--", "tests").split("\0")
        if TEST_FILE.fullmatch(p) and p not in ignored
    ]
    return {n: Path(n).read_text(encoding="utf-8", errors="replace") for n in names}


class _Runner:
    """Runs pytest over files with the recording plugin; returns (exit, {(id, when): crash line})."""

    def __init__(self, workdir: Path) -> None:
        self.dir = workdir
        (workdir / "_fabrik_merge_tests_rec.py").write_text(_PLUGIN, encoding="utf-8")
        self.n = 0

    def start(self, files: list[str]) -> tuple[subprocess.Popen, Path, Path]:
        self.n += 1
        rec = self.dir / f"rec-{self.n}.jsonl"
        rec.write_text("", encoding="utf-8")
        log = self.dir / f"log-{self.n}.txt"
        path = os.pathsep.join(p for p in (os.environ.get("PYTHONPATH", ""), str(self.dir)) if p)
        env = {**os.environ, "PYTHONPATH": path, "FABRIK_MERGE_TESTS_REC": str(rec)}
        argv = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
        argv += [
            "--continue-on-collection-errors",
            "-p",
            "_fabrik_merge_tests_rec",
            *files,
        ]
        # each run writes to its own file: a pipe left unread while another is awaited fills at
        # 64 KiB and stalls that run, which would serialise the shards
        with log.open("w", encoding="utf-8") as fh:
            proc = subprocess.Popen(argv, stdout=fh, stderr=subprocess.STDOUT, env=env)
        return proc, rec, log

    @staticmethod
    def finish(proc: subprocess.Popen, rec: Path, log: Path) -> tuple[int, dict, str]:
        rc = proc.wait()
        tail = log.read_text(encoding="utf-8", errors="replace").strip()[-3000:]
        reds: dict = {}
        for line in rec.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
                reds[(d["id"], d["when"])] = d["msg"]
            except (
                ValueError,
                KeyError,
                TypeError,
            ) as exc:  # a run killed mid-write: no verdict
                raise LegError(f"an unreadable failure record ({exc}): {line[:200]}") from exc
        return rc, reds, tail

    def run(self, files: list[str]) -> tuple[int, dict, str]:
        return self.finish(*self.start(files))


def _files_of(reds) -> list[str]:
    return sorted({key[0].split("::")[0] for key in reds})


def _checkout(commit: str) -> None:
    """``commit``'s tree with no untracked file left by an earlier run (ignored ones, the copied
    ``.env`` among them, stay): every run the verdict compares starts from the same state."""
    for argv in (
        ["git", "checkout", "-q", "-f", "--detach", commit],
        ["git", "clean", "-fdq"],
    ):
        r = subprocess.run(argv, capture_output=True, text=True)
        if r.returncode != 0:
            raise LegError(f"`{' '.join(argv)}` refused: {(r.stderr or r.stdout).strip()}")


def _parallel(runner: _Runner, groups: list[list[str]], what: str) -> dict:
    """Each group in its own process, its files in order; the reds of all, or a LegError."""
    started: list = []
    reds: dict = {}
    try:
        for g in groups:  # started one by one, so a start that fails still has its elders reaped
            if g:
                started.append(runner.start(g))
        for i, args in enumerate(started):
            rc, got, tail = runner.finish(*args)
            if rc not in RAN:
                raise LegError(f"{what} {i + 1} of {len(started)} exited {rc}:\n{tail}")
            reds.update(got)
    finally:  # one red group never leaves the others running under the next checkout
        for proc, _rec, _log in started:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
    return reds


def _one_line(msg: str, width: int) -> str:
    return " ".join(msg.split())[:width]


def differential(
    files: list[str],
    merge: str,
    base: str,
    runner: _Runner,
    shards: int,
    *,
    compare: bool,
) -> tuple[list[tuple], list[str]]:
    """Run ``files`` in shards on ``merge``; returns the reds NEW against ``base`` (each
    ``((id, when), crash line)``) and the lines to print. ``compare`` is the merge leg's alone:
    it checks the tree out and cleans it, which in a requester's own worktree would destroy
    uncommitted work — there the confirmed reds are returned unverified against the base."""
    out: list[str] = []
    if not files:
        return [], out
    groups = [g for g in (files[i::shards] for i in range(shards)) if g]
    first = _parallel(runner, groups, "shard")
    if not first:
        return [], out
    group_of = {key: next((g for g in groups if key[0].split("::")[0] in g), None) for key in first}
    stray = sorted(key[0] for key, g in group_of.items() if g is None)
    if stray:  # a red no selected file owns cannot be confirmed or compared: no verdict
        raise LegError(f"red outside the selected files: {', '.join(stray)}")
    # confirm each red alone first (cheap); one green alone is re-run in its shard's own order,
    # since another file of that shard may be what makes it red (rare, so the cost is too)
    if compare:
        _checkout(merge)
    rc, alone, tail = runner.run(_files_of(first))  # `tail` is the MERGE's, printed with its reds
    if rc not in RAN:
        raise LegError(f"the serial confirm exited {rc}:\n{tail}")
    confirmed = {k: v for k, v in alone.items() if k in first}
    ordered: list[list[str]] = []
    if len(confirmed) < len(first):
        ordered = [g for g in groups if any(group_of[k] is g for k in first if k not in confirmed)]
        if compare:
            _checkout(merge)
        again = _parallel(runner, ordered, "the ordered confirm of shard")
        confirmed.update({k: v for k, v in again.items() if k in first and k not in confirmed})
    flaky = sorted(k[0] for k in first if k not in confirmed)
    if flaky:
        out.append(
            f"merge-tests: FLAKY (red in a shard, green alone and in order) — {', '.join(flaky)}"
        )
    if not confirmed:
        return [], out
    if not compare:
        out.append(tail)
        for (nid, when), msg in sorted(confirmed.items()):
            out.append(
                f"merge-tests: red, not compared with the base outside a merge check — {nid} ({when}): {_one_line(msg, 200)}"
            )
        return sorted(confirmed.items()), out
    # the base runs the same shapes: each red file alone, and each ordering red in its shard's order
    err: BaseException | None = None
    try:
        _checkout(base)
        alone_files = [
            f for f in _files_of(k for k in confirmed if k in alone) if Path(f).is_file()
        ]
        on_base: dict = {}
        if alone_files:
            rc, on_base, base_tail = runner.run(alone_files)
            if rc not in RAN:
                raise LegError(f"the base run exited {rc}:\n{base_tail}")
        if ordered:
            _checkout(base)
            in_order = [[f for f in g if Path(f).is_file()] for g in ordered]
            on_base.update(_parallel(runner, in_order, "the ordered base run of shard"))
    except BaseException as exc:
        err = exc
        raise
    finally:
        try:
            _checkout(merge)
        except LegError as back:
            if err is not None and not isinstance(err, Exception):
                raise err from back  # an interrupt stays an interrupt; the restore failure rides along
            raise LegError(f"{err!r}; then {back}" if err else str(back)) from err
    new, old = [], []
    for key, msg in sorted(confirmed.items()):
        was = on_base.get(key)
        (old if was is not None and normalise(was) == normalise(msg) else new).append((key, msg))
    if new:
        out.append(tail)
    for (nid, when), msg in old:
        out.append(f"merge-tests: pre-existing on the base — {nid} ({when}): {_one_line(msg, 200)}")
    # last before the verdict, one line each: the refusal quotes only the last 3 lines
    for (nid, when), msg in new:
        out.append(f"merge-tests: NEW red — {nid} ({when}): {_one_line(msg, 300)}")
    return new, out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--shards", type=int, default=int(os.getenv("FABRIK_MERGE_SHARDS", SHARDS)))
    ap.add_argument("--list", action="store_true", help="print the selection and run nothing")
    args = ap.parse_args(argv)
    in_merge = os.environ.get("FABRIK_MERGE_CHECK") == "1"
    t0 = time.monotonic()
    base = ""
    try:
        head = _git("rev-parse", "HEAD").strip()
        parents = _git("show", "-s", "--format=%P", head).split()
        with tempfile.TemporaryDirectory(prefix="merge-tests-") as tmp:
            runner = _Runner(Path(tmp))
            # _base_alone re-runs this at the base, which is itself a merge commit as often as
            # not (4 of master's last 12 first-parent tips): a record for HEAD is what says so,
            # since only a refusal of a merge onto HEAD writes one, the moment before that re-run
            if in_merge and (_record_path(head).exists() or len(parents) < 2):
                return _base_alone(head, runner)
            base = parents[0] if in_merge else _git("merge-base", "HEAD", "origin/master").strip()
            if in_merge:  # until a verdict replaces it, any death reads as "measured nothing"
                _write_record(base, [f"{_LEG_MARK}\tin-progress"])
            changed = [
                p
                for p in _git("diff", "--name-only", "--no-renames", "-z", base, head).split("\0")
                if p
            ]
            files = select(changed, _tests_here())
            print(
                f"merge-tests: {len(files)} test file(s) from {len(changed)} changed path(s) {base[:9]}..{head[:9]}"
            )
            if args.list:
                print("\n".join(files))
                if in_merge:
                    _record_path(base).unlink(missing_ok=True)
                return 0
            new, lines = differential(
                files, head, base, runner, max(1, args.shards), compare=in_merge
            )
            rc = 1 if new else 0
            if in_merge and new:
                _write_record(base, [f"{nid}\t{when}" for (nid, when), _ in new])
            elif in_merge:
                _record_path(base).unlink(missing_ok=True)
    except Exception as exc:  # noqa: BLE001 — every failure without a verdict is exit 3, said so
        if in_merge and base:
            try:
                _write_record(base, [f"{_LEG_MARK}\t{type(exc).__name__}"])
            except Exception:  # noqa: BLE001 — the in-progress mark already says the same
                pass
        print(f"{exc}\nmerge-tests: LEG FAILED — no verdict (exit 3)")
        return 3
    print("\n".join(lines))
    if new:
        ids = ", ".join(nid for (nid, _when), _msg in new)
        what = "new failure(s)" if in_merge else "failure(s), not compared with the base"
        verdict = f"red — {len(new)} {what}: {ids}"[:1000]
    else:
        verdict = "green"
    print(f"merge-tests: {verdict} in {time.monotonic() - t0:.0f}s")
    return rc


def _base_alone(head: str, runner: _Runner) -> int:
    """``_base_alone``'s re-run (HEAD = the base, no merge): the recorded new reds, by id, in the
    files that exist here — red only when one of THOSE ids fails (the files may hold master's own reds)."""
    try:
        keys = {
            tuple(ln.split("\t", 1))
            for ln in _record_path(head).read_text(encoding="utf-8").splitlines()
            if ln
        }
    except FileNotFoundError:
        keys = set()
    if not keys or any(k[0] == _LEG_MARK for k in keys):
        print(
            f"merge-tests: NOT MEASURED on the base — no new red recorded for HEAD {head[:9]} (not a base-side fault)"
        )
        return 2
    present = [f for f in _files_of(keys) if Path(f).is_file()]
    if not present:
        print("merge-tests: green on the base — every new red is in a file new in the branch")
        return 0
    rc, reds, tail = runner.run(present)
    if rc not in RAN:
        print(f"{tail}\nmerge-tests: LEG FAILED on the base (exit {rc})")
        return 3
    again = sorted(k[0] for k in reds if k in keys)
    print(
        f"merge-tests: base run of {len(present)} file(s): {len(again)} of {len(keys)} new red(s) red here too"
    )
    return 1 if again else 0


if __name__ == "__main__":
    sys.exit(main())
