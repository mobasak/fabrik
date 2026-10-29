#!/usr/bin/env python3
# AFTER-EDIT: none
"""Gate check: Fabrik-synced files must not be modified locally.

Files listed in ``scripts/fabrik_synced_manifest.py`` are centrally distributed from
``/opt/fabrik`` by ``sync_enforcement_to_projects.py``. Editing a copy inside a project is
futile — the next sync overwrites it. This check fails the gate when a project's copy of a
synced file has been LOCALLY EDITED, so the agent is told to make the change upstream.

**Compares against the per-project lock (``.fabrik/synced.lock``), NOT live /opt/fabrik.**
The sync writes that lock at distribution time: the md5 of every synced file AS GIVEN to
THIS project. So a project merely BEHIND the advancing hub (its rules/scripts are an
older-but-unmodified published version, pending the next sync) matches its own lock and is
never flagged — which permanently kills the recurring false positive where updating a
governance file on the hub red-flagged every project that hadn't re-synced yet. Only a
genuine local edit — a file differing from the hash it was distributed with — fails.

No lock yet in a LINKED WORKTREE (it is born without one) → graded against the main checkout's
lock, the rows the worktree holds only (an absent row was never received; ``synced_lock``). No
lock anywhere (a project not re-synced since the lock was introduced) → skip gracefully; the
next sync writes it and the check activates. Self-exempt inside ``/opt/fabrik`` (the source) and
its worktrees.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

FABRIK_ROOT = Path("/opt/fabrik")
LOCK_REL = ".fabrik/synced.lock"


def _md5(path: Path) -> str:
    h = hashlib.md5(usedforsecurity=False)  # drift detection, never crypto
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# The two manifest lists this check reads. A missing one is a LOUD failure (W-5feb6e9c): the old
# `from fabrik_synced_manifest import X` / `except ImportError` read a missing SYMBOL exactly like
# a missing module (both raise ImportError, both with `name == "fabrik_synced_manifest"`) and ran
# the check with an empty list, so a hub rename red-flagged ~46 projects for edits they were
# allowed to make, with no word about the hub. The REQUIRED_MANIFEST_ATTRS rule is
# check_sync_trigger_coverage.py's; unlike its loader (OSError only), this one names anything the
# manifest raises while it loads or while its lists are read, except a bare KeyboardInterrupt (the
# operator's), SystemExit and GeneratorExit included, consults no manifest object once the lists
# are read, and refuses a present list of the wrong shape (the boundary — a manifest that reaches
# into this module can rewrite it — is stated at the load in `_manifest_lists`).
REQUIRED_MANIFEST_ATTRS = ("SEEDED_NOT_ENFORCED", "RETIRED_VENDORED_DIRS")
MANIFEST_REL = "scripts/fabrik_synced_manifest.py"


class ManifestError(Exception):
    """The hub manifest exists but cannot answer — the hub's defect, never the project's."""


def _is_file(path: Path) -> bool | None:
    """`path.is_file()`, or None when the path cannot be examined: `is_file` swallows only
    ENOENT-class errors and RAISES PermissionError for a hub another uid owns."""
    try:
        return path.is_file()
    except OSError:
        return None


def _path_list(path: Path, name: str, value: object, *, tuple_entries: bool) -> list[object]:
    """`value` as a list of paths, or ManifestError: a present list of the wrong shape is a guessed
    list too (`set(None)` crashed bare; a string exploded into one-character prefixes).

    EXACT built-in types only, tested by identity (`type(x) is T`), never `isinstance` or `==` (a
    metaclass answers both): a subclass's `__iter__`, `__str__` or `rstrip`, or a `__class__`
    property, is the manifest's code running after its load is over, where a `sys.exit(0)` ended
    the check GREEN (W-3d6a6236). The value is iterated ONCE, so the entries checked are the entries
    returned. The message names a refused entry by its type, never its `repr`, for the same reason."""
    if not any(type(value) is t for t in (set, frozenset, list, tuple)):  # a str is none of these
        raise ManifestError(
            f"{path}: {name} is a {type(value).__name__}, not a collection of paths"
        )
    items = list(value)
    for item in items:
        head = item[0] if tuple_entries and type(item) is tuple and item else item
        if type(head) is not str:
            raise ManifestError(f"{path}: {name} holds a {type(head).__name__}, not a path")
    return items


def _manifest_lists() -> tuple[set[str], tuple[str, ...]]:
    """(seeded-not-enforced files, retired vendored dirs) from the hub's live manifest.

    Seeded files are distributed once but allowed to diverge (never flagged). Retired vendored
    dirs are the PROJECT'S now — deleting or editing them is the sanctioned action.

    Both are empty when the hub or its manifest FILE is absent, or cannot be examined (e.g. on a
    VPS, or a hub another uid owns) — a rare, acceptable degradation; `main()` then names the hub
    beside any drift it reports when the hub is present but its manifest is absent, because a
    moved manifest, not a project edit, may be the cause. A manifest that is present but fails to
    load, lacks either list, or holds one of the wrong shape raises ManifestError: a guessed list
    grades the wrong rule. Loaded by file location, never `sys.path` + import, so no cached or
    shadowing module can answer for the hub's file; the manifest therefore imports only the stdlib
    (graded by `tests/test_check_synced_unmodified_manifest.py`, which also loads the repo's own
    manifest through this function).

    Why retired dirs exist (found 2026-09-08 by the independent closing pass of the D-196 retirement):
    this check iterates the project's `.fabrik/synced.lock`, which is a FROZEN SNAPSHOT rewritten
    only by a sync. `RETIRED_VENDORED_DIRS` tells projects they "may delete it at their own pace",
    but a lock row whose file is absent is a hard failure here — so in any target the sync no
    longer reaches, following that instruction reds `final_gate` forever with no way to clear it.
    Measured: 2 of 47 locks under /opt still carry the 26 `libs/subagents` rows, both in
    worktree-shaped repos that the SYNC skips by design (`scripts/sync_enforcement_to_projects.py`
    `main()`, `.git` is a file — this `main()` has no such check and processes them, which is why
    their frozen locks matter here), both frozen since
    2026-09-03 — and both belong to fabrik-lib, the repo that REQUESTED the retirement.
    """
    path = FABRIK_ROOT / MANIFEST_REL
    if not _is_file(path):
        return set(), ()
    spec = importlib.util.spec_from_file_location("fabrik_synced_manifest", path)
    if spec is None or spec.loader is None:
        raise ManifestError(f"cannot load {path}")
    man = importlib.util.module_from_spec(spec)
    # The module's own dict, taken BEFORE any manifest code runs: the lists are read from it, never
    # through the module object, whose class the manifest can swap (a `__dict__` property) and
    # whose `__getattr__` it can define.
    names = man.__dict__
    # Anything the manifest raises while it loads, or while its lists are read, is the hub's and is
    # NAMED, never swallowed — SystemExit too (a manifest calling sys.exit(0) would otherwise end
    # the check GREEN), and GeneratorExit or any other BaseException (a bare traceback named
    # nothing; W-3d6a6236). Only a bare KeyboardInterrupt (exactly that type) is let through: it is
    # the operator's. The exception's own `str()` and its type's `__name__` are the manifest's code
    # too and could exit 0 from inside this handler, so each gets the same guard. What the catch cannot reach: a manifest that
    # ends the process (os._exit) or installs a side effect that outlives its load (an atexit hook,
    # sys.excepthook, a signal handler) — it is the hub's own stdlib-only file, not a sandboxed one.
    # A manifest that deliberately reaches into THIS module (a frame walk, gc) can rewrite the check
    # itself — replacing `_md5` passes any drift with nothing raised — so these guards close what an
    # honest manifest can get wrong, never an attack (W-3d6a6236 review pass 2).
    try:
        spec.loader.exec_module(man)
        missing = [a for a in REQUIRED_MANIFEST_ATTRS if a not in names]
        if missing:
            raise ManifestError(
                f"{path} has no {', '.join(missing)} — renamed or removed in the hub?"
            )
        seeded = _path_list(
            path, "SEEDED_NOT_ENFORCED", names["SEEDED_NOT_ENFORCED"], tuple_entries=False
        )
        retired = _path_list(
            path, "RETIRED_VENDORED_DIRS", names["RETIRED_VENDORED_DIRS"], tuple_entries=True
        )
        # Exact built-in strs and tuples only past this line, so nothing below runs manifest code.
        return {str(s) for s in seeded}, tuple(retired)  # type: ignore[arg-type]
    except BaseException as e:
        # This check's own refusal passes as raised — the exact type holding exact-str args, so a
        # ManifestError subclass, or the exact class re-raised with a hostile argument (whose
        # `__str__` would run when `main()` prints it), is named like any other failure.
        if type(e) is KeyboardInterrupt:
            raise
        if (
            type(e) is ManifestError
            and type(e.args) is tuple
            and all(type(a) is str for a in e.args)
        ):
            raise
        # Both halves of the message run manifest code — the exception's `__str__` and its
        # metaclass's `__name__` (W-deb8eb0f) — so each is read inside its own guard, and each
        # must be an EXACT str: a str subclass's `__format__` would run in the f-string below.
        try:
            name = type(e).__name__
            if type(name) is not str:
                raise TypeError("not an exact str")
        except BaseException as inner:
            if type(inner) is KeyboardInterrupt:
                raise
            name = "<its type name could not be read>"
        try:
            detail = str(e)
            if type(detail) is not str:
                raise TypeError("not an exact str")
        except BaseException as inner:
            if type(inner) is KeyboardInterrupt:
                raise
            detail = "<its message raised too>"
        raise ManifestError(f"{path} failed to load or answer: {name}: {detail}") from e


_GIT_ENV_OVERRIDES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE")


def _main_checkout(project_root: Path) -> Path | None:
    """The main checkout when `project_root` IS a LINKED worktree's root (its git-dir differs from
    the shared git-common-dir), else None. A submodule has a `.git` FILE too, so the file's shape is
    never the test. command_run.py's `_main_checkout` identity rule (W-c77f91c6): git runs with the
    caller's GIT_DIR/GIT_WORK_TREE stripped (a hook's leftover would answer for another repo), the
    common dir must be named `.git` (a bare or --separate-git-dir repo's parent is no checkout),
    and the toplevel must be `project_root` (a subdirectory is not the worktree). Any git failure
    reads as "not a linked worktree"."""
    env = {k: v for k, v in os.environ.items() if k not in _GIT_ENV_OVERRIDES}
    try:
        out = subprocess.run(
            [
                "git",
                "-C",
                str(project_root),
                "rev-parse",
                "--path-format=absolute",
                "--git-dir",
                "--git-common-dir",
                "--show-toplevel",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    lines = out.stdout.splitlines()
    if out.returncode != 0 or len(lines) < 3:
        return None
    git_dir, common = Path(lines[0]).resolve(), Path(lines[1]).resolve()
    if git_dir == common or common.name != ".git":
        return None
    if Path(lines[2]).resolve() != project_root.resolve():
        return None
    return common.parent


def _never_received(dest: Path) -> bool:
    """True when nothing at or above `dest` shows it was ever written: `dest` has no entry and its
    nearest ancestor that has one is a directory. A dangling symlink at `dest`, or an ancestor that
    is a dangling symlink or a plain file, means the path was received and broken (W-c77f91c6
    review), which reds DELETED as it does under an own lock."""
    if os.path.lexists(dest):
        return False
    for ancestor in dest.parents:
        if os.path.lexists(ancestor):
            return ancestor.is_dir()
    return True


def synced_lock(project_root: Path) -> tuple[Path | None, bool, str]:
    """(the lock to grade `project_root` against, borrowed?, why there is none).

    The project's own `.fabrik/synced.lock` when it has one. A LINKED worktree is born without
    one (the `.worktreeinclude` copy carries this check but not the lock; the sync copies the main
    checkout's lock in on its next run, and only under `.claude/worktrees/`), so it borrows its
    MAIN checkout's lock — never the live hub or git HEAD, which re-introduce the version-skew
    false positive. The hub's own worktrees are the source. `final_gate._synced_paths` reads this
    too, so the gate never reformats a file this check grades. Cobra (D-253): deleting a
    worktree's own lock to dodge the strict rule lands here, where absent rows still go unflagged
    but every present copy is graded — tighter than the skip it replaced."""
    own = project_root / LOCK_REL
    if own.exists():
        return own, False, ""
    main_checkout = _main_checkout(project_root)
    if main_checkout is not None and main_checkout == FABRIK_ROOT.resolve():
        return None, False, "(source repo worktree — synced-files check skipped)"
    if main_checkout is None or not (main_checkout / LOCK_REL).exists():
        return (
            None,
            False,
            f"(no {LOCK_REL} — project not yet re-synced; synced-files check skipped)",
        )
    return main_checkout / LOCK_REL, True, ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Fabrik-synced files are unmodified.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    project_root = args.project_root.resolve()

    # Self-exemption: this IS the canonical source.
    if project_root == FABRIK_ROOT.resolve():
        print("(source repo — synced-files check skipped)")
        return 0

    lock_path, borrowed, why = synced_lock(project_root)
    if lock_path is None:
        print(why)
        return 0
    try:
        lock: dict[str, str] = json.loads(lock_path.read_text())
    except Exception as e:
        print(f"({lock_path if borrowed else LOCK_REL} unreadable: {e} — skipped)")
        return 0

    try:
        seeded, retired_dirs = _manifest_lists()
    except ManifestError as e:
        print(f"❌ the hub's synced manifest cannot answer this check: {e}")
        print("This is the HUB's defect, not this project's — report it to /opt/fabrik (infra).")
        print("Without it the check cannot tell a sanctioned seeded/retired edit from drift.")
        return 1
    # `item[0] if tuple` mirrors check_sync_trigger_coverage.py:247 — these manifest lists accept
    # a tuple entry by convention, and an uncaught AttributeError here would fire in ~46 repos.
    retired = tuple((d[0] if isinstance(d, tuple) else d).rstrip("/") + "/" for d in retired_dirs)
    drifted: list[str] = []
    changed: list[str] = []  # differs or deleted — the stale-worktree remedy's subjects
    not_received = 0  # a borrowed lock's rows this worktree never held
    graded = 0  # rows compared byte for byte (seeded, retired and not-received rows excluded)
    for rel, distributed_hash in lock.items():
        if rel in seeded:
            continue
        dest = project_root / rel
        # A retired dir is the PROJECT'S now — deleting it AND editing it are both sanctioned,
        # and neither can ever be cleared by a sync that no longer reaches it. The first version
        # skipped only the deletion, so a project that kept the dir and changed one line reds
        # `final_gate` forever, under a remedy text ("the next sync restores it") that is false
        # for a retired path. `startswith(())` is False, so an empty tuple (a hub or manifest file
        # that is absent or cannot be examined) degrades to the old behaviour with no special case — verified, not assumed.
        if rel.startswith(retired):
            continue
        # A dangling symlink, at the file or a parent, was received and broken, so it reds DELETED
        # below exactly as under an own lock — only `_never_received` paths are not received.
        if borrowed and _never_received(dest):
            not_received += 1
        elif not dest.exists():
            drifted.append(f"{rel} — DELETED locally (a Fabrik-synced file must exist)")
            changed.append(rel)
        else:
            graded += 1
            if _md5(dest) != distributed_hash:
                drifted.append(rel)
                changed.append(rel)

    if drifted and borrowed:
        # This worktree never had its own lock, so a fresh copy older than the main checkout's
        # last sync is the likelier cause than an edit — the header must not claim an edit.
        print(
            f"❌ Fabrik-synced files differ from the main checkout's lock ({lock_path}; "
            f"{not_received} not yet received) — a copy older than the main checkout's last "
            "sync, or a local edit:"
        )
        for rel in sorted(drifted):
            print(f"   - {rel}")
    elif drifted:
        print(
            "❌ Fabrik-synced files modified locally — these are CENTRALLY MANAGED and are "
            "overwritten on every sync:"
        )
        for rel in sorted(drifted):
            print(f"   - {rel}")
        print()
        print("You edited a synced copy (it differs from what was distributed to this")
        print("project). Revert it (the next sync restores it), or, if the change is right for")
        print("ALL projects, edit /opt/fabrik/<path>: the hub distributes it. Never fork here.")
    if drifted:
        manifest = FABRIK_ROOT / MANIFEST_REL
        # `is False`, never falsy: a manifest that cannot be examined (None) is "cannot tell". A
        # clean False means every stat on the way resolved, so `exists()` below cannot raise.
        if _is_file(manifest) is False and FABRIK_ROOT.exists():
            print()
            print(f"⚠ The hub manifest {manifest} is missing, so the seeded and retired")
            print("exemptions could not be applied: a hub-side move, not a project edit, may be")
            print("the cause of some rows above — report it to /opt/fabrik (infra).")
        # A borrowed lock already names its main checkout (`<main>/.fabrik/synced.lock`); asking
        # git again could name another one, so the header and the remedy would disagree.
        main_checkout = lock_path.parent.parent if borrowed else _main_checkout(project_root)
        if main_checkout is not None and changed:
            # W-800579be: in a linked worktree the copy may be STALE instead — the sync never
            # overwrites a worktree file it cannot prove it wrote, while the main checkout's
            # fresh lock lands here. The gate stays red (a stale rule is still a stale rule);
            # only the remedy is named honestly.
            print()
            print("This is a linked worktree: if you edited nothing, a copy may be STALE (the hub")
            print("re-synced the main checkout after this worktree was made). Re-copy it:")
            for rel in sorted(changed):
                src = main_checkout / rel
                if src.is_file() and _md5(src) == lock[rel]:
                    print(f"   cp {shlex.quote(str(src))} {shlex.quote(rel)}")
                else:
                    print(
                        f"   {rel}: the main checkout does not match the lock either — re-run the sync"
                    )
        return 1

    if borrowed:
        print(
            f"✓ all {graded} Fabrik-synced files present match the main "
            f"checkout's lock ({lock_path}); {not_received} not yet received"
        )
        return 0
    print(f"✓ all {len(lock)} Fabrik-synced files match what was distributed ({LOCK_REL})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
