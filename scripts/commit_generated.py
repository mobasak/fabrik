#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/kaizen.md
"""Commit a generator's OWN output in a main checkout — and nothing else (W-5568be8d).

A generator that rewrites a tracked file in the hub's MAIN checkout leaves it dirty, and
``merge_request.py``'s preflight then refuses every merge touching it ("dirty in the main
checkout (not a ledger)"). The generator calls this module around its write instead::

    before = commit_generated.snapshot(paths)   # BEFORE the write
    ...write the files...
    commit_generated.commit_own(paths, before, writer="kaizen-collector", context="…")

``commit_own`` lands ONE pathspec commit (``git commit --only --no-verify -F <msg> -- <paths>``,
so the shared index entry and the branch ref move together under git's own index.lock and a
failure lands nothing) holding only the paths that are provably this run's own, judged against
the HEAD read just before the commit:

* the repo is a MAIN checkout (git-dir == common-dir) on branch ``master`` or ``main``, not
  mid merge/cherry-pick/revert/rebase/bisect, with no unmerged path;
* the path exists at HEAD, and its shared index entry equals HEAD's blob (nobody staged it);
* the bytes before the write equal HEAD's blob, or equal the bytes this helper last left
  UNCOMMITTED for that path while HEAD's blob is still the one recorded then (the state file).

Anything else is left dirty with a reason — exactly today's behaviour, so every guard fails
OPEN. It never fetches or pushes (the merge owner's next push carries a local-ahead master;
every master writer works in the hub's one main checkout, so origin cannot move past a
local-only commit), and it never raises: it returns one status line, ``committed <sha> …`` or
``left dirty: …``. Paths are literal pathspecs (``GIT_LITERAL_PATHSPECS``), so a name holding a
glob character matches itself only, and every git call runs with the caller's repo-locating
``GIT_*`` variables removed. ``--no-verify`` skips pre-commit and commit-msg only: the post-commit
hook still runs — in the hub that is the governance-sync shim, which syncs nothing for a path
outside the governance-sync filter (the kaizen logs are outside it).

COBRA (D-253): the cheapest way to make the main checkout read clean is to commit everything
dirty. The before-bytes rule is the counter — a sibling's uncommitted edit fails it — and
``tests/test_commit_generated.py::test_preexisting_edit_is_never_committed`` holds it.

Residuals, named rather than prevented, each detected after landing and named on stderr:
someone writing the same file in the milliseconds between the read at entry and
``git commit --only`` has their bytes ride along (the committed blob differs from the bytes
read); and a ref-only move of the branch (the merge owner's ``update-ref``) that changes the
same path in the same milliseconds is reverted by the commit (HEAD^'s blob for the path differs
from the one judged). Only the coordinator and the daily pipeline write the main checkout, and
neither edits a generated file by hand.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

BRANCHES = ("master", "main")
#: a peer's ``git commit`` holds index.lock for milliseconds to seconds (its hooks included);
#: three tries 0.5 s apart outlast the common case, and a lock that outlives them is recorded
#: so the next run lands the commit rather than waiting a day.
LOCK_TRIES = 3
LOCK_RETRY_S = 0.5
GIT_TIMEOUT_S = 60
_IN_PROGRESS = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG")
_IN_PROGRESS_DIRS = ("rebase-merge", "rebase-apply")
#: the variables that point git at a repo, index or object store other than ``-C <top>``'s
_REPO_ENV = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_PREFIX",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_NAMESPACE",
    "GIT_CEILING_DIRECTORIES",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM",
)


def _state_path() -> Path:
    override = os.environ.get("FABRIK_GENERATED_STATE", "")
    if override:
        return Path(override)
    return Path.home() / ".claude" / "state" / "generated-output.json"


def _git(top: Path, *args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in _REPO_ENV}
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_LITERAL_PATHSPECS"] = "1"
    argv = ["git", "-C", str(top), *args]
    try:
        return subprocess.run(
            argv, input=stdin, capture_output=True, timeout=GIT_TIMEOUT_S, env=env, check=False
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            argv, 124, b"", f"timed out after {GIT_TIMEOUT_S}s".encode()
        )


def _out(top: Path, *args: str) -> str | None:
    r = _git(top, *args)
    return r.stdout.decode("utf-8", "replace").strip() if r.returncode == 0 else None


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def snapshot(paths: list[Path]) -> dict[str, bytes | None]:
    """Each path's bytes before the generator writes (``None`` when the file is absent)."""
    before: dict[str, bytes | None] = {}
    for p in paths:
        try:
            before[str(Path(p).resolve())] = Path(p).read_bytes()
        except OSError:
            before[str(Path(p).resolve())] = None
    return before


def _main_checkout(path: Path) -> tuple[Path, str] | str:
    """(toplevel, branch) when ``path`` sits in a main checkout fit to commit in, else a reason."""
    probe = path.parent if path.parent.is_dir() else path
    r = _git(probe, "rev-parse", "--path-format=absolute", "--show-toplevel", "--git-dir",
             "--git-common-dir")  # fmt: skip
    if r.returncode != 0:
        return "not a git checkout"
    lines = r.stdout.decode().strip().splitlines()
    if len(lines) != 3:
        return "git rev-parse gave no toplevel"
    top, git_dir, common = (Path(x).resolve() for x in lines)
    if git_dir != common:
        return "a linked worktree (its own agent commits there)"
    branch = _out(top, "symbolic-ref", "--short", "-q", "HEAD")
    if not branch:
        return "detached HEAD"
    if branch not in BRANCHES:
        return f"branch {branch} is not {' or '.join(BRANCHES)}"
    for name in _IN_PROGRESS:
        if (git_dir / name).exists():
            return f"repo is mid-operation ({name})"
    for name in _IN_PROGRESS_DIRS:
        if (git_dir / name).is_dir():
            return f"repo is mid-rebase ({name})"
    if _out(top, "ls-files", "--unmerged"):
        return "unmerged paths present"
    return top, branch


@contextlib.contextmanager
def _state_lock() -> Iterator[None]:
    """Serialise the state file's read-modify-write across concurrent runs (a manual run beside the
    cron); a lock that cannot be taken degrades to the unlocked path, never to a failure."""
    path = _state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(path.with_name(path.name + ".lock"), "a")  # noqa: SIM115 - held for the block
    except OSError:
        yield
        return
    with fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        yield


def _load_state() -> dict:
    try:
        data = json.loads(_state_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    path = _state_path()
    tmp: str | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=1, sort_keys=True)
        os.replace(tmp, path)
        tmp = None
    except OSError as exc:
        print(f"[commit_generated] state not saved ({exc!r})", file=sys.stderr)
    finally:
        if tmp is not None:
            with contextlib.suppress(OSError):
                os.unlink(tmp)


def _head_blob(top: Path, rel: str, rev: str = "HEAD") -> str | None:
    return _out(top, "rev-parse", "-q", "--verify", f"{rev}:{rel}")


def _index_blob(top: Path, rel: str) -> str | None:
    line = _out(top, "ls-files", "-s", "--", rel)
    if not line or "\n" in line:
        return None
    return line.split()[1]


def _blob_of(top: Path, rel: str, data: bytes) -> str | None:
    """The blob ``data`` becomes when committed at ``rel`` (``--path`` applies that path's filters,
    so an autocrlf or clean-filter normalisation is compared like for like)."""
    r = _git(top, "hash-object", f"--path={rel}", "--stdin", stdin=data)
    return r.stdout.decode().strip() if r.returncode == 0 else None


def _eligible(
    top: Path, rel: str, head: str | None, before: bytes | None, now: bytes, state: dict
) -> str | None:
    """None when ``rel`` is provably this run's own output, else the reason it is not."""
    if head is None:
        return "not tracked at HEAD"
    if _index_blob(top, rel) != head:
        return "staged differently from HEAD"
    if _blob_of(top, rel, now) == head:
        return "unchanged"
    if before is not None and _blob_of(top, rel, before) == head:
        return None
    own = state.get(f"{top}:{rel}")
    if (
        isinstance(own, dict)
        and before is not None
        and own.get("sha") == _sha(before)
        and own.get("head") == head
    ):
        return None
    return "dirty before this write (not this generator's bytes)"


def _message(writer: str, context: str) -> str:
    return (
        f"chore(generated): {writer} commits its own output ({time.strftime('%Y-%m-%d')})\n\n"
        "Agent-Role: primary\n"
        f"Agent-Name: {writer}\n"
        f"Agent-Context: {' '.join(context.split())}\n"
    )


def _commit(top: Path, rels: list[str], msg: str) -> tuple[bool, str]:
    lock = Path(_out(top, "rev-parse", "--path-format=absolute", "--git-path", "index.lock") or "")
    with tempfile.NamedTemporaryFile("w", suffix=".msg", delete=False, encoding="utf-8") as fh:
        fh.write(msg)
        msg_file = fh.name
    try:
        for attempt in range(LOCK_TRIES):
            if lock.name and lock.exists():
                if attempt + 1 < LOCK_TRIES:
                    time.sleep(LOCK_RETRY_S)
                continue
            r = _git(top, "commit", "--only", "--no-verify", "-q", "-F", msg_file, "--", *rels)
            if r.returncode == 0:
                return True, ""
            err = r.stderr.decode("utf-8", "replace").strip()
            if "index.lock" not in err:
                return False, err.splitlines()[-1] if err else f"git commit rc {r.returncode}"
            if attempt + 1 < LOCK_TRIES:
                time.sleep(LOCK_RETRY_S)
        return False, f"index.lock held past {LOCK_TRIES} tries"
    finally:
        with contextlib.suppress(OSError):
            os.unlink(msg_file)


def commit_own(
    paths: list[Path], before: dict[str, bytes | None], *, writer: str, context: str
) -> str:
    """Commit the paths that are provably this run's own output; never raises."""
    try:
        return _commit_own(paths, before, writer=writer, context=context)
    except Exception as exc:  # noqa: BLE001 — a generator's run must never fail on its commit
        reason = f"left dirty: commit_generated crashed ({exc!r})"
        print(f"[commit_generated] {reason}", file=sys.stderr)
        return reason


def _commit_own(
    paths: list[Path], before: dict[str, bytes | None], *, writer: str, context: str
) -> str:
    groups: dict[Path, list[tuple[str, bytes | None, bytes]]] = {}
    reasons: list[str] = []
    for p in paths:
        p = Path(p).resolve()
        shape = _main_checkout(p)
        if isinstance(shape, str):
            reasons.append(f"{p.name}: {shape}")
            continue
        top, _branch = shape
        try:
            now = p.read_bytes()
        except OSError:
            reasons.append(f"{p.name}: unreadable after the write")
            continue
        groups.setdefault(top, []).append((p.relative_to(top).as_posix(), before.get(str(p)), now))

    landed: list[str] = []
    if groups:  # no git group → no state read or write at all (a tmp log, a linked worktree)
        with _state_lock():
            landed = _commit_groups(groups, reasons, writer=writer, context=context)
    for reason in reasons:
        print(f"[commit_generated] {writer}: left dirty — {reason}", file=sys.stderr)
    if landed:
        return "committed " + "; ".join(landed)
    return "left dirty: " + ("; ".join(reasons) if reasons else "nothing changed")


def _commit_groups(
    groups: dict[Path, list[tuple[str, bytes | None, bytes]]],
    reasons: list[str],
    *,
    writer: str,
    context: str,
) -> list[str]:
    state = _load_state()
    changed = False
    landed: list[str] = []
    for top, items in groups.items():
        judged = _out(top, "rev-parse", "HEAD")
        mine: list[tuple[str, bytes, str]] = []
        for rel, prev, now in items:
            head = _head_blob(top, rel)
            why = _eligible(top, rel, head, prev, now, state)
            if why is None:
                mine.append((rel, now, head or ""))
                continue
            if why == "unchanged":
                changed |= state.pop(f"{top}:{rel}", None) is not None
            else:
                reasons.append(f"{rel}: {why}")
        if not mine:
            continue
        rels = [rel for rel, _, _ in mine]
        ok, err = _commit(top, rels, _message(writer, context))
        if not ok and all(_head_blob(top, rel) == _blob_of(top, rel, now) for rel, now, _ in mine):
            ok = True  # it landed after all (a slow post-commit hook timed the call out)
        if not ok:
            for rel, now, head in mine:
                state[f"{top}:{rel}"] = {"sha": _sha(now), "head": head}
            changed = True
            reasons.append(f"{', '.join(rels)}: {err}")
            continue
        sha = _out(top, "rev-parse", "HEAD") or "?"
        parent_moved = _out(top, "rev-parse", "HEAD^") != judged
        for rel, now, head in mine:
            changed |= state.pop(f"{top}:{rel}", None) is not None
            if parent_moved and _head_blob(top, rel, "HEAD^") != head:
                print(
                    f"[commit_generated] WARNING: {rel} changed at HEAD between the eligibility "
                    f"check and the commit — {sha[:12]} REVERTS that change; restore it from "
                    f"{sha[:12]}^",
                    file=sys.stderr,
                )
            if _head_blob(top, rel, sha) != _blob_of(top, rel, now):
                print(
                    f"[commit_generated] WARNING: {rel} changed between the generator's write and "
                    f"the commit — {sha[:12]} holds bytes this generator did not write",
                    file=sys.stderr,
                )
        landed.append(f"{sha[:12]} ({', '.join(rels)})")
    if changed:
        _save_state(state)
    return landed
