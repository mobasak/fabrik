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
import math
import os
import re
import shlex
import statistics
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path

SHARDS = 8
# a selected file heavier than its selection's per-shard share runs as node groups across the shards
# (W-231f4695); under this many seconds a file is never split — its collect step and the per-group
# re-import would cost more than the minutes a split can save
SPLIT_MIN_S = 60.0
COLLECT_TIMEOUT_S = 120
# a file's collection (import) cost, which no pytest report carries: `pytest --collect-only` on this box
# took 0.17 s for one file and 1.55 s for ten (W-c832e59f design critique); added to every file's weight
# so files whose tests are near-instant spread across shards instead of piling on the first
IMPORT_S = 0.15
# per-file run seconds the merge leg measured, shared by every leg of the repo (W-c832e59f)
# (JSON in a `.txt`: `merge_request.py` globs `fabrik-merge/*.json` as its merge records)
DURATIONS_FILE = "merge-tests-durations.txt"
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
# (a relative one, `tmpk3j9_2xq/out`, is a component only when a `/` follows it)
_TMPNAME = re.compile(r"(?<=/)tmp[a-z0-9_]{8}(?![\w-])|(?<![\w./-])tmp[a-z0-9_]{8}(?=/)")
# a record line naming no id: the leg refused without a verdict, so the base-alone run measures nothing
_LEG_MARK = "#leg-failed"
# The recording plugin: one JSON line per failed report (a collection error's id is the file), and
# under FABRIK_MERGE_TESTS_DUR one line per report's duration, passed or failed (W-c832e59f).
# Under FABRIK_MERGE_TESTS_UNTIL (a JSON file of node ids, W-c80361e4) an ordered re-run stops one
# item past the last listed red: every file is still collected and the order up to there is the
# shard's, so an earlier file's pollution still shows, and the listed item's teardown sees the
# whole run's next item. The cut is a wrapper that acts after `yield` — after every plain
# modifyitems, a conftest's reorder registered later included (a plain trylast impl ran before one
# and read a polluted red green). Any input it cannot honour cuts nothing: a cut too early reads an
# order-dependent red FLAKY, a false green; a cut not taken only costs the old whole-shard run.
_PLUGIN = """
import json, os
import pytest

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
    dur = os.environ.get("FABRIK_MERGE_TESTS_DUR")
    if dur:
        try:  # advisory: a lost duration costs balance, never the run (an error here is INTERNALERROR)
            with open(dur, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"f": report.nodeid.split("::")[0], "id": report.nodeid, "s": report.duration}) + "\\n")
        except OSError:
            pass

def pytest_collectreport(report):
    if report.failed:
        _write(report, "collect")

def _until():
    path = os.environ.get("FABRIK_MERGE_TESTS_UNTIL")
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            want = json.load(fh)
    except (OSError, ValueError):
        return None
    if isinstance(want, list) and want and all(isinstance(x, str) for x in want):
        return set(want)
    return None

@pytest.hookimpl(wrapper=True, trylast=True)
def pytest_collection_modifyitems(session, config, items):
    res = yield
    want = _until()
    ids = [item.nodeid for item in items]
    if want and want <= set(ids):
        keep = max(i for i, nid in enumerate(ids) if nid in want) + 2
        if keep < len(items):
            config.hook.pytest_deselected(items=items[keep:])
            del items[keep:]
    return res
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
        rf"\bfrom\s+{pkg}\s+import\s*(?:\((?:[^)#]|#[^\n]*)*?|(?:[ \t\w,]|\\\r?\n)*?)(?<![\w.]){name}(?![\w])",
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
    # `merge_request.py request --pretest` runs this leg outside the merge lock and points the records
    # at a private directory, so a pretest never rewrites the record a concurrent merge's base-alone
    # re-run reads (W-1fb11ec8)
    override = os.environ.get("FABRIK_MERGE_TESTS_RECORDS")
    if override:
        return Path(override) / f"merge-tests-{base}.txt"
    common = Path(_git("rev-parse", "--path-format=absolute", "--git-common-dir").strip())
    return common / "fabrik-merge" / f"merge-tests-{base}.txt"


def _green_path(branch_head: str) -> Path:
    """The last merge of ``branch_head`` this leg passed — a rebuild after a ledger-only base move
    (``_merge_into_base``'s failed CAS, W-347cd0c3) reads it to skip a re-test of the same code."""
    return _record_path(branch_head).with_name(f"merge-tests-green-{branch_head}.txt")


def _green_merge(head: str, parents: list[str]) -> tuple[str, str]:
    """``(G, "")`` for a green merge of HEAD's branch head that HEAD only re-merges onto a newer base,
    else ``("", why)`` — the record is a claim, so every way it can name the wrong merge is checked."""
    try:
        text = _green_path(parents[1]).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "", ""
    except (OSError, UnicodeDecodeError) as exc:
        return "", f"unreadable: {exc}"
    if not re.fullmatch(r"[0-9a-f]{40}", text):
        return "", "not a commit id"
    r = subprocess.run(
        ["git", "show", "-s", "--format=%P", f"{text}^{{commit}}"], capture_output=True, text=True
    )
    if r.returncode:
        return "", "names no commit here"
    if text == head:
        return "", "it names this merge"
    g_parents = r.stdout.split()
    if len(g_parents) != 2 or g_parents[1] != parents[1]:
        return "", "not a merge of this branch head"
    behind = subprocess.run(["git", "merge-base", "--is-ancestor", g_parents[0], parents[0]])
    if behind.returncode:
        return "", "its base is not behind this one"
    return text, ""


def _write_record(base: str, keys: list[str], rec: Path | None = None) -> None:
    rec = rec or _record_path(base)
    rec.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=rec.parent, prefix=rec.name + ".")  # never a shared temp name
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("".join(k + "\n" for k in keys))
        os.replace(tmp, rec)  # a reader never sees half a list
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _durations_path() -> Path:
    """The shared duration record — never under FABRIK_MERGE_TESTS_RECORDS: that override isolates a
    pretest's verdict-bearing reds from a concurrent merge (W-1fb11ec8), and `merge_request.py` sets it
    to a directory deleted with the leg, so a record there would be read empty and thrown away by the
    pretest and queue legs that most need the balance. A duration is advisory; sharing it is the point."""
    common = Path(_git("rev-parse", "--path-format=absolute", "--git-common-dir").strip())
    return common / "fabrik-merge" / DURATIONS_FILE


def _seconds(value: object) -> float | None:
    """A finite, non-negative number of seconds, else None (a bool, a string, NaN, inf, a negative,
    or an int too large for a float are all no duration)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        s = float(value)
    except OverflowError:
        return None
    return s if math.isfinite(s) and s >= 0 else None


def _load_durations(path: Path) -> dict[str, float]:
    """The recorded per-file seconds; a bad record costs only balance, never the leg."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, RecursionError) as exc:  # ValueError covers UnicodeDecodeError
        print(f"merge-tests: duration record ignored ({type(exc).__name__}: {exc})"[:300])
        return {}
    if not isinstance(data, dict):
        print(f"merge-tests: duration record ignored (a {type(data).__name__}, not an object)")
        return {}
    return {k: s for k, v in data.items() if isinstance(k, str) and (s := _seconds(v)) is not None}


def _save_durations(path: Path, measured: dict[str, float], *, complete: bool) -> None:
    """``measured`` over the old record, keys absent from this tree dropped. A complete shard run's
    values replace the old ones; an incomplete one (a shard failed, the others were killed mid-file)
    never LOWERS a recorded value, since a killed file's partial sum would under-weigh it — a file
    with no record yet takes that partial sum until a complete run replaces it. Two legs
    saving at once lose one update (last writer wins), never tear the file."""
    old = _load_durations(path)
    if complete:
        # a complete run measured every file it ran, and every node of each it split: the old node keys
        # of every measured file go (renamed or removed tests never pile up, and a file this leg ran
        # whole keeps none); a file's own key is not one
        renewed = {k.split("::")[0] for k in measured}
        old = {k: v for k, v in old.items() if not ("::" in k and k.split("::")[0] in renewed)}
    merged = (
        {**old, **measured}
        if complete
        else {**old, **{k: max(v, old.get(k, 0.0)) for k, v in measured.items()}}
    )
    # a node id key (`<file>::<test>`, a split file's, W-231f4695) is kept while its file is
    keep = {k: round(v, 3) for k, v in sorted(merged.items()) if Path(k.split("::")[0]).is_file()}
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(keep, fh, indent=0)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _run_weights(files: list[str], weights: dict[str, float]) -> dict[str, float]:
    """Each file's run seconds as the balance counts them: its recorded value, an unrecorded file the
    median of the recorded files here, 0 when none is."""
    known = [weights[f] for f in files if f in weights]
    default = statistics.median(known) if known else 0.0
    return {f: weights.get(f, default) for f in files}


def balance(files: list[str], shards: int, weights: dict[str, float]) -> list[list[str]]:
    """``files`` split into at most ``shards`` groups by weight, heaviest first to the least-loaded
    group (ties: lowest index); each group in name order, empties dropped. A file weighs its
    ``_run_weights`` seconds plus IMPORT_S. With equal weights this is ``files[i::shards]`` exactly
    (file k lands on group k mod shards), so a repo with no record keeps today's split.

    Cobra (D-253): a balance over stale or empty weights is balanced on paper only — every merge leg
    rewrites the record from its own shard run and prints planned beside measured, so the gap shows."""
    run = _run_weights(files, weights)
    load = [0.0] * max(1, shards)
    groups: list[list[str]] = [[] for _ in load]
    # `key=str`: a unit is a file or a tuple of node ids (`_split_heavy`), never compared directly; a
    # string's own order is unchanged
    for f in sorted(files, key=lambda f: (-run[f], str(f))):
        i = min(range(len(load)), key=lambda j: (load[j], j))
        groups[i].append(f)
        load[i] += run[f] + IMPORT_S
    return [sorted(g, key=str) for g in groups if g]


def _collect(path: str) -> list[str] | None:
    """The node ids pytest collects from ``path`` in this tree, in run order (the runner's interpreter and
    environment), or None when it will not collect: a non-zero exit, a timeout, a launch failure. The ids
    are the lines up to the first blank one that start with ``<path>::``, each once — a parametrized id
    may hold spaces, which is fine: every id reaches pytest as its own argv element, never through a
    shell. Output that is not UTF-8 is decoded with replacement, never raised (a conftest may write raw
    bytes to fd 1)."""
    try:
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "--collect-only",
                "-q",
                "-p",
                "no:cacheprovider",
                path,
            ],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=COLLECT_TIMEOUT_S,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    ids: dict[str, None] = {}
    for line in r.stdout.splitlines():
        if not line.strip():
            break
        if line.startswith(path + "::"):
            ids[line] = None
    return list(ids)


def _split_heavy(
    files: list[str], weights: dict[str, float], shards: int, collect=_collect
) -> tuple[list, dict, dict[str, list[tuple[str, ...]]]]:
    """``files`` as balance units: a file heavier than its selection's per-shard share (and than
    SPLIT_MIN_S) becomes node units — one per node id, weighed by its recorded seconds, once a leg
    has recorded any of the file's nodes; else up to ``shards`` CONTIGUOUS groups near-equal by count,
    each weighing the file's seconds over the group count — and every other file stays a string unit.
    Returns (units, unit weights, {split file: its units in collection order}). A heavy file that
    collects fewer than two ids, or ids that differ between two collections (a parametrize id built
    from a clock or a random value would be "not found" in its shard: pytest exit 4, no verdict),
    stays whole and says so (W-231f4695: one 1,462 s file set the wall of every hub merge leg).

    Cobra (D-253): the cheap way to look faster is to split a file whose tests depend on each other —
    each group then fails alone. Counter: the base runs the same groups, so such a red reads
    pre-existing, never a refusal of a merge that did not cause it; but it also masks a real regression
    of the coupled test, a RESIDUAL a coupled file pays (none in the hub's heaviest file, 2026-10-28)."""
    run = _run_weights(files, weights)
    share = sum(run.values()) / max(1, shards)
    units: list = []
    uw: dict = {}
    split: dict[str, list[tuple[str, ...]]] = {}
    for f in files:
        if run[f] <= share or run[f] < SPLIT_MIN_S:  # one shard: share == total, nothing exceeds it
            units.append(f)
            uw[f] = run[f]
            continue
        ids = collect(f)
        why = ""
        if ids is None or len(ids) < 2:
            why = "it did not collect" if ids is None else f"{len(ids)} node id(s)"
        else:
            again = collect(f)
            if again is None:
                why = "its second collection failed"
            elif again != ids:
                why = "its node ids differ between two collections"
        if why or ids is None:
            print(f"merge-tests: {f} kept whole ({why})")
            units.append(f)
            uw[f] = run[f]
            continue
        known = {i: weights[i] for i in ids if i in weights}
        if known:
            # the file's cost sits in a few of its tests (measured 2026-10-28: 11 of the 89 nodes of the
            # hub's heaviest file held 1,950 of its 1,976 s), so once a leg has recorded its nodes each
            # is its own unit, weighed by its seconds, and balance spreads the slow ones; an unrecorded
            # node takes an equal part of what the recorded ones leave of the file's seconds
            rest = [i for i in ids if i not in known]
            spare = max(0.0, run[f] - sum(known.values())) / max(1, len(rest))
            groups: list[tuple[str, ...]] = [(i,) for i in ids]
            split[f] = groups
            print(f"merge-tests: split {f} into {len(ids)} node(s) by their recorded seconds")
            for g in groups:
                units.append(g)
                uw[g] = known.get(g[0], spare)
            continue
        n = min(shards, len(ids))
        groups = [tuple(ids[len(ids) * k // n : len(ids) * (k + 1) // n]) for k in range(n)]
        split[f] = groups
        print(f"merge-tests: split {f} into {n} node group(s)")
        for g in groups:
            units.append(g)
            uw[g] = run[f] / n
    return units, uw, split


def _argv(group: list, rank: dict[str, int] | None = None) -> list[str]:
    """A balanced group's units as pytest arguments: a file, or each node id of a tuple unit — the
    node ids of one file in that file's own collection order (``rank``), so a shard runs a split
    file's tests in the order a whole-file run would."""
    rank = rank or {}
    items = [x for u in group for x in (u if isinstance(u, tuple) else (u,))]
    return sorted(items, key=lambda x: (x.split("::")[0], rank.get(x, -1)))


def _owns(members: list[str], nid: str) -> bool:
    """Whether a shard run over ``members`` (files and node ids) produced the report ``nid``: a member
    file owns every id in it, a member node id owns itself, and a node member owns its file's
    module-level error (that report's id is the file: an import that fails only in that shard's
    process, which `_collect` cannot rule out) — the confirm then re-runs that file whole."""
    return any(m in (nid.split("::")[0], nid) or m.split("::")[0] == nid for m in members)


def _reruns(reds, split: set[str], rank: dict[str, int] | None = None) -> list[str]:
    """What re-runs ``reds`` alone: a split file's red by its node id (re-running the whole file costs
    the minutes the split saved; its module-level error by the file), any other red's whole file (the
    alone confirm's established shape); a split file's ids in its collection order (``rank``)."""
    out = set()
    for key in reds:
        nid = key[0]
        f = nid.split("::")[0]
        out.add(nid if f in split and nid != f else f)
    rank = rank or {}
    return sorted(out, key=lambda x: (x.split("::")[0], rank.get(x, -1), x))


def _on_base(units: list[str], split: dict) -> list[str]:
    """``units`` (files and node ids) that the checked-out base can run: a file only when it exists,
    and a split file's node id only when the base collects it — passed one the base lacks, pytest
    exits 4 ("not found") and the whole leg would read as no verdict, where today's whole-file base run
    simply finds the red absent and calls it NEW (Opus critique, W-231f4695). A split file whose
    collection fails on the base (a timeout under load, a crash) runs whole there instead, as before
    the split: dropping its ids would read a pre-existing red as NEW and refuse a merge for a red it
    did not cause (review pass 1)."""
    ids: dict[str, set[str] | None] = {}
    out: list[str] = []
    for u in units:
        f = u.split("::")[0]
        if not Path(f).is_file():
            continue
        pick = u
        if u != f and f in split:
            if f not in ids:
                got = _collect(f)
                ids[f] = None if got is None else set(got)
            have = ids[f]
            if have is None:
                pick = f
            elif u not in have:
                continue
        if pick not in out:
            out.append(pick)
    return out


def _record_green(head: str, parents: list[str]) -> None:
    try:
        _write_record("", [head], _green_path(parents[1]))
    except OSError as exc:  # the verdict stands; a later rebuild only re-tests in full
        print(f"merge-tests: green record not written ({exc})")


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
        self.dur_files: list[Path] = []
        self.totals: list[float] = []

    def start(
        self, files: list[str], until: list[str] | tuple[str, ...] = ()
    ) -> tuple[subprocess.Popen, Path, Path]:
        """Start one pytest run over ``files``; ``until`` (node ids) stops it one item past the
        last of them (the plugin's cut). The list rides in a file: an environment value is capped
        at 128 KiB, which one polluter reddening ~2,000 later tests would pass."""
        self.n += 1
        rec = self.dir / f"rec-{self.n}.jsonl"
        rec.write_text("", encoding="utf-8")
        log = self.dir / f"log-{self.n}.txt"
        dur = self.dir / f"dur-{self.n}.jsonl"
        self.dur_files.append(dur)
        path = os.pathsep.join(p for p in (os.environ.get("PYTHONPATH", ""), str(self.dir)) if p)
        env = {
            **os.environ,
            "PYTHONPATH": path,
            "FABRIK_MERGE_TESTS_REC": str(rec),
            "FABRIK_MERGE_TESTS_DUR": str(dur),
        }
        env.pop("FABRIK_MERGE_TESTS_UNTIL", None)  # an inherited cut never reaches a whole run
        if until:
            cut = self.dir / f"until-{self.n}.json"
            cut.write_text(json.dumps(sorted(set(until))), encoding="utf-8")
            env["FABRIK_MERGE_TESTS_UNTIL"] = str(cut)
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

    def durations(self, runs: int, nodes_of: frozenset[str] = frozenset()) -> dict[str, float]:
        """Each file's summed test seconds over the first ``runs`` runs — the parallel shard run, under
        the leg's real load. A file split into node groups (``_split_heavy``) is in several of those
        runs, so its seconds are summed across them; the confirm and base runs started later are never
        counted (``runs`` stops before them, whenever this is called). For each file in ``nodes_of``
        every node id's seconds are returned too, keyed by the id, so the next leg can spread that
        file's slow tests. A torn or garbage line costs only balance, so it is skipped."""
        out: dict[str, float] = {}
        nodes: dict[str, float] = {}
        self.totals = []  # each of those runs' seconds, for the `shards measured` line
        for dur in self.dur_files[:runs]:
            run: dict[str, float] = {}
            try:
                lines = dur.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                # a shard that wrote nothing still has its place on the `shards measured` line
                self.totals.append(0.0)
                continue
            for line in lines:
                try:
                    d = json.loads(line)
                    f, s = d["f"], _seconds(d["s"])
                except (ValueError, KeyError, TypeError, RecursionError):
                    continue
                if isinstance(f, str) and s is not None:
                    run[f] = run.get(f, 0.0) + s
                    nid = d.get("id")
                    if f in nodes_of and isinstance(nid, str) and nid.startswith(f + "::"):
                        nodes[nid] = nodes.get(nid, 0.0) + s
            self.totals.append(sum(run.values()))
            for f, s in run.items():
                out[f] = out.get(f, 0.0) + s
        return {**out, **nodes}


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


def _parallel(
    runner: _Runner, groups: list[list[str]], what: str, until: list[list[str]] | None = None
) -> dict:
    """Each group in its own process, its files in order; the reds of all, or a LegError.
    ``until``, aligned with ``groups``, is each group's cut (``_Runner.start``)."""
    started: list = []
    reds: dict = {}
    try:
        for i, g in enumerate(groups):  # one by one: a start that fails still reaps its elders
            if g:
                started.append(runner.start(g, until=until[i] if until else ()))
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


def _record_durations(
    runner: _Runner,
    groups: list[list[str]],
    record: Path,
    *,
    complete: bool,
    nodes_of: frozenset[str] = frozenset(),
) -> None:
    """Save the shard run's measured seconds (per file, and per node id of each split file) and print
    them per shard. Advisory end to end: any error here prints one line and never replaces the leg's
    verdict or the error the shard run raised."""
    try:
        measured = runner.durations(len(groups), nodes_of)
        if not measured:
            return
        _save_durations(record, measured, complete=complete)
        # per shard run, not per file: a split file's seconds belong to several shards
        print("merge-tests: shards measured " + " ".join(f"{s:.2f}" for s in runner.totals))
    except Exception as exc:  # noqa: BLE001 — the record steers only the next split
        print(f"merge-tests: duration record not written ({type(exc).__name__}: {exc})"[:300])


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
    weights: dict[str, float] | None = None,
    record: Path | None = None,
) -> tuple[list[tuple], list[str]]:
    """Run ``files`` in shards on ``merge``; returns the reds NEW against ``base`` (each
    ``((id, when), crash line)``) and the lines to print. ``compare`` is the merge leg's alone:
    it checks the tree out and cleans it, which in a requester's own worktree would destroy
    uncommitted work — there the confirmed reds are returned unverified against the base.
    ``weights`` (recorded seconds per file) balances the shards; ``record``, given only in a merge
    check, is where the shard run's measured seconds are saved, even when a shard is red."""
    out: list[str] = []
    if not files:
        return [], out
    weights = weights or {}
    units, unit_weights, split = _split_heavy(files, weights, shards)
    unit_groups = balance(units, shards, unit_weights)
    rank = {i: n for gs in split.values() for n, i in enumerate(x for g in gs for x in g)}
    groups = [_argv(g, rank) for g in unit_groups]
    if any(f in weights for f in files):  # run seconds, as `shards measured` prints them
        print(
            "merge-tests: shards planned "
            + " ".join(f"{sum(unit_weights[u] for u in g):.2f}" for g in unit_groups)
        )
    complete = False
    try:
        first = _parallel(runner, groups, "shard")
        complete = True
    finally:
        if record is not None:
            _record_durations(runner, groups, record, complete=complete, nodes_of=frozenset(split))
    if not first:
        return [], out
    group_of = {key: next((g for g in groups if _owns(g, key[0])), None) for key in first}
    stray = sorted(key[0] for key, g in group_of.items() if g is None)
    if stray:  # a red no selected file owns cannot be confirmed or compared: no verdict
        raise LegError(f"red outside the selected files: {', '.join(stray)}")
    # confirm each red alone first (cheap); one green alone is re-run in its shard's own order,
    # since another file of that shard may be what makes it red (rare, so the cost is too)
    if compare:
        _checkout(merge)
    rc, alone, tail = runner.run(
        _reruns(first, set(split), rank)
    )  # `tail`: the MERGE's, printed with its reds
    if rc not in RAN:
        raise LegError(f"the serial confirm exited {rc}:\n{tail}")
    confirmed = {k: v for k, v in alone.items() if k in first}
    ordered: list[list[str]] = []
    if len(confirmed) < len(first):
        ordered = [g for g in groups if any(group_of[k] is g for k in first if k not in confirmed)]
        if compare:
            _checkout(merge)
        # each re-run stops just past the reds it is asked about (the plugin's cut, W-c80361e4):
        # the shard's later tests cannot change an earlier red's outcome
        cuts = [[k[0] for k in first if k not in confirmed and group_of[k] is g] for g in ordered]
        again = _parallel(runner, ordered, "the ordered confirm of shard", cuts)
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
        alone_files = _on_base(
            _reruns((k for k in confirmed if k in alone), set(split), rank), split
        )
        on_base: dict = {}
        if alone_files:
            rc, on_base, base_tail = runner.run(alone_files)
            if rc not in RAN:
                raise LegError(f"the base run exited {rc}:\n{base_tail}")
        # only a red the ORDERED confirm found needs its shard's order on the base: one confirmed
        # alone is compared with its own alone run above (alone with alone; the ordered base run used
        # to overwrite that with its in-order result), and one green in order too was flaky, with
        # nothing to compare (a whole ~8 min shard per flaky leg, 2026-10-27)
        by_order = [k for k in confirmed if k not in alone]
        base_ordered = [g for g in ordered if any(group_of[k] is g for k in by_order)]
        if base_ordered:
            _checkout(base)
            in_order = [_on_base(g, split) for g in base_ordered]
            # cut at the order reds the base still runs: one whose file or id the base lacks would
            # disable the cut for the whole group
            cuts = [
                [k[0] for k in by_order if group_of[k] is g and _owns(members, k[0])]
                for g, members in zip(base_ordered, in_order, strict=True)
            ]
            in_order_base = _parallel(runner, in_order, "the ordered base run of shard", cuts)
            on_base.update({k: v for k, v in in_order_base.items() if k in by_order})
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
            if in_merge and not args.list:
                green, why = _green_merge(head, parents)
                if why:
                    print(f"merge-tests: green record ignored ({why})")
                delta = (
                    _git("diff", "--name-only", "--no-renames", "-z", green, head) if green else ""
                )
                if green and all(SKIP.fullmatch(p) for p in delta.split("\0") if p):
                    _record_path(base).unlink(missing_ok=True)
                    _record_green(head, parents)
                    print(
                        "merge-tests: re-test skipped — only ledger/work-item paths changed since the "
                        f"green merge {green[:12]}\nmerge-tests: green in {time.monotonic() - t0:.0f}s"
                    )
                    return 0
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
            record = _durations_path()
            new, lines = differential(
                files,
                head,
                base,
                runner,
                max(1, args.shards),
                compare=in_merge,
                weights=_load_durations(record),
                record=record if in_merge else None,  # a branch-local leg records nothing
            )
            rc = 1 if new else 0
            if in_merge and new:
                _write_record(base, [f"{nid}\t{when}" for (nid, when), _ in new])
            elif in_merge:
                _record_path(base).unlink(missing_ok=True)
                _record_green(head, parents)
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
