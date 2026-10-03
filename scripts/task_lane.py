#!/usr/bin/env python3
# AFTER-EDIT: tests/test_task_lane_admission.py · tests/test_task_lane_close.py · tests/test_task_lane_receipt.py · tests/test_task_lane_review_stop.py · scripts/review_receipt.py (the receipt grammar check_review_receipt reads) ·tests/test_lane_replay.py · tests/fixtures/lane_replay.json (re-capture with scripts/lane_replay_capture.py, whose expected_verdict delegates to classify_commit, then --check) · scripts/command_run.py (the `_task_size_gate` caller, T08)
"""The /fabrik-task lane rules — admission and close (plan 2026-10-02-plan-1 T02, T03a; spec D1-D4, D7, D9, D12).

PURE: no import of ``command_run.py``, no environment reads that change an answer. The caller
(``command_run.py``, T08) computes the facts — the declared answers, the normalised ``--file``
list, the governance-sync hits, the appetite, ``--why``, the lane version, the refusal ledger's
path — and this module only decides.

- ``lane_version(root)`` — the repo-owned switch ``.fabrik/lane.json`` (``{"version": 1|2}``),
  else ``_LANE_DEFAULT`` (2 — every repo, D-507). Never a synced file: a pin distributes nothing (D12).
- ``admit(...)`` — the ``start`` verdict. Version 1 is today's gate verbatim (files > 3,
  oneway, tradeoffs → chain; sync, heavy → right-now + full review; decision=no → right-now +
  scoped review). Version 2 replaces ONLY the file-count arm with the module tests: contract
  (path test or ``consumers=external``), oneway, tradeoffs (each now needs ``--why``), appetite
  > 240; sync, heavy, a migration path or more than 5 files keep the lane and select the FULL
  review (D2, D7).
- ``classify_commit(...)`` — the same tests applied to one commit's ``--name-status -M -C``
  rows; graded against T01's pinned replay (``tests/test_lane_replay.py``).
- ``record_refusal(ledger, row)`` — one JSON line per chain-routed start (D9).
- ``measure_close(rec, commits, ...)`` — the close (T03a; D1 close column, D3, D4, § Lifecycle):
  per commit in the given order with rename carry-over; contract and new-source re-checked over
  every committed path before any exclusion; an undeclared path refuses ``done``.
- ``check_review_receipt(path, commits, root=)`` — the full-review receipt a close-time contract
  or new-source hit owes (T03b; D1 checks (a)-(d)).
- ``scope_growth_rounds(stack)`` — the in-lane review's scope-growth stop (T04; D8): ``(1, 1)``
  when the record's immediate parent is a ``fabrik-task`` run, else today's ``(3, 2)``.
- ``contract_hit`` / ``is_new_source`` / ``is_migration`` — the path helpers every rule shares,
  so admission, the replay and the close (T03a) cannot disagree.

THE CHEAPEST WAY TO SATISFY THIS GATE WITHOUT THE OUTCOME (D-253): declare one file, answer
``no`` everywhere, ``consumers=internal`` and no appetite. Nothing at ``start`` can see that, and
nothing here tries to — the counter is the close (T03a): it re-runs ``contract_hit`` and
``is_new_source`` over every COMMITTED path before any exclusion, and refuses an undeclared one.
The ``--why`` requirement has its own cheap path (a one-word reason); the counter is the refusal
ledger, which records the reason verbatim where ``/fabrik-spec``'s DOWNGRADE step and the
feedback report read it.
"""

from __future__ import annotations

import json
import math
import os
import posixpath
import re
import secrets
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# The shipped gate: lane v2 in every repo (operator ruling 2026-10-02, D-507, superseding D12's
# hub-only week); a repo pins v1 with its own `.fabrik/lane.json` `{"version": 1}`.
_LANE_DEFAULT = 2
LANE_FILE = ".fabrik/lane.json"
_KNOWN_VERSIONS = (1, 2)

# Version 1's file cap (today's `_TASK_MAX_FILES`, command_run.py:2809).
_V1_MAX_FILES = 3
# D2: more than this many declared/committed files selects the full review (CLAUDE.md § 1a).
_FULL_REVIEW_FILES = 5
# D1 new-source: more than this many new non-test, non-doc files is a module.
_MAX_NEW_SOURCE = 2
# D1/D4: the appetite default and the one-session bound, in minutes.
APPETITE_DEFAULT = 240
_APPETITE_MAX = 240
# D3.1: at most this many Behaviours in the design note; one more is an UPGRADE.
_MAX_BEHAVIOURS = 7
# D3.4: more added lines than this is a `change:` finding, never a refusal.
_LOC_FINDING = 800
# D4: past this multiple of the appetite the close records `over_appetite`.
_APPETITE_BREAKER = 2

# The dependency-segment, migration-segment and contract-basename tests are case-INSENSITIVE:
# a case-insensitive filesystem (macOS) serves `Vendor/` and `Migrations/` as the same
# directories (T02-O16). The test-path rule below stays case-sensitive.
_DEPENDENCY_SEGMENTS = frozenset({"node_modules", ".venv", "vendor"})
_CONTRACT_BASENAME = re.compile(r"openapi.*\.(json|ya?ml)|.*\.schema\.json", re.IGNORECASE)
_MIGRATION = re.compile(r"(^|/)(migrations|alembic/versions)/", re.IGNORECASE)
# T02-O3: a test is any path with a `tests`/`test`/`__tests__` directory segment at any depth,
# or a basename `test_*`, `*_test.*`, `*.test.*` or `*.spec.*`.
_TEST_DIRS = frozenset({"tests", "test", "__tests__"})
_TEST_BASENAME = re.compile(r"test_.*|.*_test\..*|.*\.test\..*|.*\.spec\..*")
# The declared keys version 2 requires, each with its only legal answers (today's gate,
# command_run.py:3058-3066, plus D1's `consumers`).
_V2_KEYS: dict[str, tuple[str, ...]] = {
    "decision": ("yes", "no"),
    "heavy": ("yes", "no"),
    "mechanism": ("yes", "no"),
    "oneway": ("yes", "no"),
    "tradeoffs": ("yes", "no"),
    "consumers": ("external", "internal"),
}

# The replay measurement's exclusion set (spec § What exists today 6): never counted as a file
# or a new source. The close's own, wider set (the Doc Sync destinations) is T03a's `excluded`.
_MEASURE_EXCLUDE_EXACT = frozenset(
    {
        "CHANGELOG.md",
        "INDEX.md",
        "docs/DECISIONS.md",
        "docs/STRATEGIC_BACKLOG.md",
        "docs/LESSONS_LEARNT.md",
        "docs/CAPABILITIES.md",
    }
)
_MEASURE_EXCLUDE_PREFIX = (
    "docs/reference/",
    "docs/workstation/",
    "docs/development/reviews/",
    ".fabrik/work/",
)

# Environment that would move or reconfigure the repository `lane_version` asks git about.
_GIT_ENV_OVERRIDES = frozenset(
    {
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_COMMON_DIR",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_NAMESPACE",
        "GIT_CEILING_DIRECTORIES",
        "GIT_DISCOVERY_ACROSS_FILESYSTEM",
        "GIT_LITERAL_PATHSPECS",
        "GIT_GLOB_PATHSPECS",
        "GIT_NOGLOB_PATHSPECS",
        "GIT_ICASE_PATHSPECS",
    }
)


@dataclass(frozen=True)
class Verdict:
    """The ``start`` verdict.

    ``route``: ``lane`` · ``chain: contract|oneway|tradeoffs|appetite`` (and ``chain: files`` at
    version 1) · ``right-now + /fabrik-review`` · ``right-now + /fabrik-review-scoped`` ·
    ``refused`` (the input itself is invalid — ``reason`` names the flag). ``review`` is the
    phase-4 review the lane or right-now route owes (``full`` = ``/fabrik-review``); it carries
    no meaning on a ``chain`` or ``refused`` route. ``reason`` is one human line.
    """

    route: str
    review: str
    reason: str


# ── the path helpers (shared by admit, classify_commit and T03a's close) ──────────────────


def _segments(path: str) -> list[str]:
    return path.split("/")


def _in_dependency_dir(path: str) -> bool:
    return any(seg.lower() in _DEPENDENCY_SEGMENTS for seg in _segments(path))


def contract_hit(path: str) -> bool:
    """Is ``path`` read outside this repo? A file under a ``specs/services/`` segment pair at
    any depth, or a basename fully matching ``openapi*.json``/``openapi*.yaml``/``openapi*.yml``/
    ``*.schema.json`` case-insensitively at any depth — never under a
    ``node_modules``/``.venv``/``vendor`` path SEGMENT (spec D1)."""
    if _in_dependency_dir(path):
        return False
    dirs = _segments(path)[:-1]
    if any(dirs[i : i + 2] == ["specs", "services"] for i in range(len(dirs) - 1)):
        return True
    return _CONTRACT_BASENAME.fullmatch(path.rsplit("/", 1)[-1]) is not None


def is_migration(path: str) -> bool:
    """A ``migrations/`` or ``alembic/versions/`` segment at any depth, outside dependency
    directories (spec D2)."""
    return not _in_dependency_dir(path) and _MIGRATION.search(path) is not None


def _measure_excluded(path: str) -> bool:
    return path in _MEASURE_EXCLUDE_EXACT or path.startswith(_MEASURE_EXCLUDE_PREFIX)


def counted(path: str) -> bool:
    """Does ``path`` count toward the more-than-5-files full review? Everything except the
    measurement's exclusion set — the ONE rule ``admit`` and ``classify_commit`` share (O12)."""
    return not _measure_excluded(path)


def is_test(path: str) -> bool:
    """A test file: a ``tests``/``test``/``__tests__`` directory segment at any depth, or a
    basename ``test_*``, ``*_test.*``, ``*.test.*`` or ``*.spec.*``. ``classify_commit`` uses
    this, and ``lane_replay_capture.expected_verdict`` delegates to ``classify_commit`` — one rule."""
    *dirs, base = _segments(path)
    return any(d in _TEST_DIRS for d in dirs) or _TEST_BASENAME.fullmatch(base) is not None


def status_letter(status: str) -> str:
    """The status LETTER of a ``--name-status -M -C`` row. A rename or copy carries its
    similarity score (``R100``, ``C075``); every rule in this module reads the status through
    this one helper, so a raw row and a letter-only row get the same verdict (T03a-O3)."""
    return status.strip()[:1]


def is_new_source(status: str, path: str) -> bool:
    """A NEW source file: status ``A`` or ``C`` (a copy is a new file; a score such as ``C075``
    is read by its letter), not a test, not ``.md`` and not in the measurement's exclusion set
    (which holds ``.fabrik/work/``, never the rest of ``.fabrik/`` — the pinned measurement rule
    is canonical; spec D1), and never under a dependency directory (``node_modules``/``.venv``/
    ``vendor``, as ``contract_hit`` and ``is_migration``). ``.md`` matches in any case."""
    return (
        status_letter(status) in ("A", "C")
        and not path.lower().endswith(".md")
        and not is_test(path)
        and not _measure_excluded(path)
        and not _in_dependency_dir(path)
    )


# ── the switch (D12) ──────────────────────────────────────────────────────────────────────


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes] | None:
    """Read-only git against ``root``: the repository-moving environment is scrubbed (a hook's
    ``GIT_DIR``/``GIT_INDEX_FILE`` must not redirect the question) and optional locks are off,
    so no call ever refreshes or rewrites ``.git/index`` (O10, O15)."""
    env = {k: v for k, v in os.environ.items() if k not in _GIT_ENV_OVERRIDES}
    env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        return subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), *args],
            capture_output=True,
            timeout=10,
            check=False,
            env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _switch_commit(root: Path, content: bytes) -> str | None:
    """The commit that last set ``.fabrik/lane.json`` — only when the working file's bytes
    equal that commit's blob; ``None`` when they differ (uncommitted, untracked, edited — even
    under ``assume-unchanged``/``skip-worktree``, which ``git status`` cannot see) or git
    cannot answer (O14)."""
    log = _git(root, "log", "-1", "--format=%H", "--", LANE_FILE)
    if log is None or log.returncode != 0:
        return None
    sha = log.stdout.decode("ascii", "replace").strip()
    if not sha:
        return None
    blob = _git(root, "show", f"{sha}:{LANE_FILE}")
    if blob is None or blob.returncode != 0 or blob.stdout != content:
        return None
    return sha


def lane_version(root: Path) -> tuple[int, str | None, str | None]:
    """(version, the commit that last set the switch or ``None``, a warning or ``None``).

    No file → ``(_LANE_DEFAULT, None, None)``. Invalid JSON, a non-object, a missing, unknown,
    string or boolean version → ``_LANE_DEFAULT`` with a warning naming the file.
    """
    path = Path(root) / LANE_FILE
    try:
        if not path.is_file():
            return _LANE_DEFAULT, None, None
        content = path.read_bytes()
        data = json.loads(content.decode("utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        return (
            _LANE_DEFAULT,
            None,
            f"⚠ {LANE_FILE}: unreadable ({exc.__class__.__name__}) — lane v{_LANE_DEFAULT}",
        )
    version = data.get("version") if isinstance(data, dict) else None
    if type(version) is not int or version not in _KNOWN_VERSIONS:
        return (
            _LANE_DEFAULT,
            None,
            f"⚠ {LANE_FILE}: version {version!r} is not one of {list(_KNOWN_VERSIONS)} "
            f"— lane v{_LANE_DEFAULT}",
        )
    return version, _switch_commit(Path(root), content), None


# ── admission (D1, D2, D4, D7, D9) ────────────────────────────────────────────────────────


def _admit_v1(declared: dict[str, str], files: list[str], sync_hits: set[str]) -> Verdict:
    """Today's gate, verbatim (command_run.py:3178-3192)."""
    if len(files) > _V1_MAX_FILES:
        return Verdict("chain: files", "scoped", f"files > {_V1_MAX_FILES}")
    if declared.get("oneway") == "yes":
        return Verdict("chain: oneway", "scoped", "oneway")
    if declared.get("tradeoffs") == "yes":
        return Verdict("chain: tradeoffs", "scoped", "tradeoffs")
    if sync_hits:
        return Verdict("right-now + /fabrik-review", "full", "sync")
    if declared.get("heavy") == "yes":
        return Verdict("right-now + /fabrik-review", "full", "heavy")
    if declared.get("decision") != "yes":
        return Verdict("right-now + /fabrik-review-scoped", "scoped", "decision=no")
    return Verdict("lane", "scoped", "admitted")


def admit(
    declared: dict[str, str],
    files: list[str],
    *,
    sync_hits: set[str],
    appetite: Any,
    why: str | None,
    version: int,
) -> Verdict:
    """The ``start`` verdict for ``fabrik-task``. ``files`` is the normalised ``--file`` list
    (duplicates count once); ``sync_hits`` the declared paths the governance-sync regex matched
    (empty in a project repo); ``appetite`` the ``--appetite`` minutes or ``None`` (default 240).

    Version 2 order: (1) invalid input is ``refused`` naming the key or flag — every declared
    key is required, ``yes|no`` (``consumers``: ``external|internal``), as today's gate; (2) the
    ROUTE is decided — contract, then appetite, then oneway/tradeoffs — and ``--why`` is demanded
    only when oneway or tradeoffs is the deciding reason (O19); (3) heavy surfaces select the
    full review. Every ``chain`` verdict is a refused start the caller ledgers with
    ``record_refusal`` — a contract hit included.
    """
    files = list(dict.fromkeys(files))
    if version != 2:
        return _admit_v1(declared, files, sync_hits)

    # (1) invalid input — refused naming the key or flag; no route is decided on it.
    missing = [k for k in _V2_KEYS if k not in declared]
    wrong = [
        f"{k}={declared[k]}"
        for k, ok in _V2_KEYS.items()
        if k in declared and declared[k] not in ok
    ]
    if missing or wrong:
        parts = []
        if missing:
            parts.append("missing --declare keys: " + ", ".join(missing))
        if wrong:
            parts.append(
                "--declare values must be yes|no (consumers: external|internal): "
                + ", ".join(wrong)
            )
        return Verdict("refused", "scoped", "; ".join(parts))
    if appetite is None:
        appetite = APPETITE_DEFAULT
    elif type(appetite) is not int or appetite <= 0:
        return Verdict(
            "refused",
            "scoped",
            f"--appetite must be a positive integer of minutes (got {appetite!r})",
        )

    # (2) the route — any module-test hit is the spec chain. `consumers=internal` never
    # removes a path hit; it can only fail to add one.
    hits = [f for f in files if contract_hit(f)]
    if declared["consumers"] == "external" or hits:
        named = ", ".join(hits) if hits else "consumers=external"
        return Verdict("chain: contract", "scoped", f"contract: {named}")
    if appetite > _APPETITE_MAX:
        return Verdict("chain: appetite", "scoped", f"appetite {appetite} > {_APPETITE_MAX} min")
    deciding = [k for k in ("oneway", "tradeoffs") if declared[k] == "yes"]
    if deciding:
        if not (why or "").strip():
            return Verdict(
                "refused",
                "scoped",
                "--why is required with "
                + " and ".join(f"{k}=yes" for k in deciding)
                + ' — "<what cannot be undone>" or "<approach A> vs <approach B>"',
            )
        return Verdict(f"chain: {deciding[0]}", "scoped", ", ".join(deciding))

    # (3) heavy surfaces keep the lane and select the full review (D2, D7).
    full = []
    if sync_hits:
        full.append("sync")
    if declared["heavy"] == "yes":
        full.append("heavy")
    if any(is_migration(f) for f in files):
        full.append("migration")
    if sum(1 for f in files if counted(f)) > _FULL_REVIEW_FILES:
        full.append(f"files > {_FULL_REVIEW_FILES}")
    review = "full" if full else "scoped"
    if declared["decision"] != "yes":
        route = "right-now + /fabrik-review" if full else "right-now + /fabrik-review-scoped"
        return Verdict(route, review, ", ".join(["decision=no", *full]))
    return Verdict("lane", review, ", ".join(full) if full else "admitted")


def record_refusal(ledger: Path, row: dict[str, Any]) -> str:
    """Append one refusal row (D9) to ``ledger`` and return its id. The caller supplies the
    repo key (its git common dir), session, declared keys, ``--why``, ``--file`` list and the
    refusal line. ``id`` and ``ts`` are ALWAYS generated here — a caller-supplied ``id`` or
    ``ts`` is ignored, so a DOWNGRADE joining on the id can never meet a duplicate (O18).

    The line is written ``ensure_ascii=True``: U+2028/U+2029/U+0085 in a ``--why`` would
    otherwise split the row under ``str.splitlines()``, and a lone surrogate (non-UTF-8 argv
    bytes) would raise before the refusal is ledgered (O1)."""
    refusal_id = f"LR-{secrets.token_hex(4)}"
    out = {
        "id": refusal_id,
        "ts": time.time(),
        **{k: v for k, v in row.items() if k not in ("id", "ts")},
    }
    ledger = Path(ledger)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="ascii") as fh:
        fh.write(json.dumps(out, ensure_ascii=True, sort_keys=True) + "\n")
    return refusal_id


# ── the replay classifier (D12 (1)) ───────────────────────────────────────────────────────


def classify_commit(
    rows: list[tuple[str, str, str | None]], *, repo_kind: str, sync_regex: str
) -> str:
    """One commit's verdict: ``lane`` · ``lane: full-review`` · ``chain: contract`` ·
    ``chain: new-source``. ``rows`` are ``(status, path, old_path)``. The contract, sync and
    migration tests read BOTH the old and the new path of a rename or copy (moving a contract
    away changes what is read outside the repo, O13); the docs-only, new-source and count tests
    read the new path. First match wins: contract (before any exclusion) → docs-only (every
    path ``.md`` or under ``.fabrik/``; full review only for a hub sync hit) → new-source (> 2)
    → full review (hub sync hit, a migration path, > 5 counted paths) → lane. An empty
    ``sync_regex`` matches nothing (H2)."""
    paths = [path for _status, path, _old in rows]
    touched = paths + [old for _status, _path, old in rows if old is not None]
    if any(contract_hit(p) for p in touched):
        return "chain: contract"
    sync = re.compile(sync_regex) if sync_regex else None
    sync_hit = repo_kind == "hub" and sync is not None and any(sync.search(p) for p in touched)
    if all(p.endswith(".md") or p.startswith(".fabrik/") for p in paths):
        return "lane: full-review" if sync_hit else "lane"
    if sum(1 for status, path, _old in rows if is_new_source(status, path)) > _MAX_NEW_SOURCE:
        return "chain: new-source"
    if sync_hit or any(is_migration(p) for p in touched):
        return "lane: full-review"
    if len({p for p in paths if counted(p)}) > _FULL_REVIEW_FILES:
        return "lane: full-review"
    return "lane"


# ── the in-lane review's scope-growth stop (D8, T04) ──────────────────────────────────────

_TASK_COMMAND = "fabrik-task"
# Today's (window, qualify) — the twins of `command_run.py::SCOPE_GROWTH_ROUNDS` and
# `SCOPE_GROWTH_QUALIFY`, pinned by `tests/test_task_lane_review_stop.py` (this module never
# imports `command_run.py`, so the test parses the source).
_SCOPE_GROWTH_DEFAULT = (3, 2)
# Nested under a /fabrik-task run: the FIRST own-fix-only delta round stops the hunting. The
# qualify half is `check_review_coverage.py::_LANE_OWN_FIX_ROUNDS_FOR_STOP`'s twin.
_SCOPE_GROWTH_LANE = (1, 1)


def scope_growth_rounds(stack: list[dict[str, Any]]) -> tuple[int, int]:
    """``(rounds, qualify)`` for the review whose record stack is ``stack`` (D8).

    ``(1, 1)`` when the LAST entry — the immediate parent ``command_run.py`` parked when this
    review started — is a record whose ``command`` is exactly ``fabrik-task`` (the record stores
    the name with its slash stripped); else today's ``(3, 2)``. Only the immediate parent counts:
    a ``fabrik-task`` deeper in the stack means this review was started by something else inside
    the lane (e.g. a plan phase), which keeps the ordinary rule.

    The review still CLOSES only on a confirmed-zero pass (D-355); this shortens the hunting, never
    the close. THE CHEAPEST WAY TO SATISFY THIS WITHOUT THE OUTCOME (D-253): run an ordinary full
    review nested under a throwaway ``/fabrik-task`` start to get the one-round stop. The counter
    is that the lane's own start gate and close measure the change (``admit``, ``measure_close``),
    and the kill criterion (a post-merge fix citing an in-lane review stopped by the one-round
    stop reverts D8) is read from the feedback row's ``parent`` field.
    """
    last = stack[-1] if stack else None
    if isinstance(last, dict) and last.get("command") == _TASK_COMMAND:
        return _SCOPE_GROWTH_LANE
    return _SCOPE_GROWTH_DEFAULT


# ── the close (D1 close column, D3, D4, D7, § Lifecycle) ──────────────────────────────────

_CLOSE_VERBS = ("done", "blocked", "handoff")
# The order `upgrade` lists its tokens in; the feedback row's single `upgrade` is the first.
_UPGRADE_ORDER = ("contract", "new-source", "behaviours", "appetite")

Rows = list[tuple[str, str, str | None]]


@dataclass(kw_only=True)
class LaneRecord:
    """What the close needs from a ``fabrik-task`` run record — T08 builds it.

    ``stamped`` — the record carries ``gate: 2`` (a v2 start); ``files`` the ``--file`` list;
    ``design_paths`` the backticked paths of the design note's APPROACH and MIRROR;
    ``amendments`` one path per ``step --phase 2 --design-amend <path>``, in order (all three
    are normalised here, ``_norm_path``); ``behaviours`` the design note's ``## Behaviours``
    count; ``appetite`` minutes; ``started_at`` epoch seconds — REQUIRED, so a record with no
    start time cannot be built and never reads as over its appetite (T03a-O5); ``consumers`` the
    declared answer; ``sync_hits`` the declared paths the governance-sync regex matched at
    ``start``; ``in_worktree`` the run commits in a linked worktree, where a sync-path run may
    commit several times because distribution waits for the merge (spec D7, T03a-O4).
    """

    started_at: float
    stamped: bool = False
    files: list[str] = field(default_factory=list)
    design_paths: list[str] = field(default_factory=list)
    amendments: list[str] = field(default_factory=list)
    behaviours: int = 0
    appetite: int = APPETITE_DEFAULT
    consumers: str = "internal"
    sync_hits: set[str] = field(default_factory=set)
    in_worktree: bool = False

    def __post_init__(self) -> None:
        # The annotation is not enforced at runtime: refuse ``None``, a string, a bool (an
        # ``int`` subclass) and a non-finite float, so no record reads as over its appetite.
        t = self.started_at
        if type(t) not in (int, float) or not math.isfinite(t):
            raise TypeError(f"LaneRecord.started_at must be a finite int or float (got {t!r})")


@dataclass(frozen=True)
class CloseVerdict:
    """The close's verdict. ``refused`` is the one refusal line (``None`` = the close may
    proceed); ``needs_full_review`` is a close-time contract or new-source hit, which owes a
    full ``/fabrik-review`` receipt on ``done`` and ``handoff`` (the caller checks it, T03b/T08);
    ``upgrade`` every token the close raised, in ``_UPGRADE_ORDER``; ``design_amends`` the
    number of DISTINCT amended paths, equal to ``len(amended_paths)``; ``oversized_mini`` the
    undeclared committed paths; ``findings`` the lines to print (``UPGRADE: …``, ``change: …``,
    ``sync: …``).
    """

    refused: str | None
    needs_full_review: bool
    upgrade: list[str]
    design_amends: int
    amended_paths: list[str]
    oversized_mini: list[str]
    loc_added: int
    over_appetite: bool
    findings: list[str]


def _norm_path(path: str) -> str:
    """A declared path as the committed rows spell it: whitespace stripped, a leading ``./``
    dropped, then posix-normalised (``a//b`` → ``a/b``) — applied alike to ``files``,
    ``design_paths`` and ``amendments`` (T03a-O10)."""
    p = path.strip()
    while p.startswith("./"):
        p = p[2:]
    return posixpath.normpath(p) if p else p


def _norm_all(paths: list[str]) -> list[str]:
    return [q for q in dict.fromkeys(_norm_path(p) for p in paths) if q]


def _undeclared(
    commits: list[Rows], declared: set[str], inherit: set[str], exempt: Callable[[str], bool]
) -> list[str]:
    """The undeclared committed paths, walking ``commits`` in order (D3.2). ``declared`` passes
    the check; ``exempt`` (the caller's exclusions, the receipt) also passes it but grants
    NOTHING. A RENAME's new path inherits membership only from an old path in ``inherit`` — the
    paths the run itself declared — and keeps it in every later commit, so an edit of the
    renamed file stays declared; an excluded or receipt old path cannot launder an undeclared
    source file (T03a-O1). The old path is judged on its own membership. A COPY's new path is
    judged ALONE: its source survives, so inheriting would let ``cp declared.py x.py`` ship an
    undeclared file inside a declared surface (``command_run.py:3519-3541``)."""
    declared, inherit = set(declared), set(inherit)
    out: list[str] = []
    for rows in commits:
        for status, path, old in rows:
            ok = path in declared or exempt(path)
            if old is not None and status_letter(status) == "R":
                if old in inherit:
                    ok = True
                    declared.add(path)
                    inherit.add(path)
                if not (old in declared or exempt(old)):
                    out.append(old)
            if not ok:
                out.append(path)
    return list(dict.fromkeys(out))


def _surviving_new_sources(commits: list[Rows]) -> list[str]:
    """The new source files that EXIST after the last commit (T03a-O6): added (``A``/``C``,
    ``is_new_source``), not deleted later; a rename moves a counted path to its new name (and
    keeps counting it only while the new name is still a source file); the same path added
    twice counts once."""
    alive: dict[str, None] = {}
    for rows in commits:
        for status, path, old in rows:
            letter = status_letter(status)
            if letter == "D":
                alive.pop(path, None)
            elif letter == "R" and old is not None:
                if old in alive:
                    del alive[old]
                    if is_new_source("A", path):
                        alive[path] = None
            elif is_new_source(status, path):
                alive[path] = None
    return list(alive)


def measure_close(
    rec: LaneRecord,
    commits: list[Rows],
    *,
    excluded: Callable[[str], bool],
    verb: str,
    now: float,
    loc_added: int,
    receipt: str | None,
) -> CloseVerdict:
    """Measure a ``fabrik-task`` close. ``commits`` holds one list of ``(status, path, old_path)``
    rows per ``--commit`` SHA, in the order given, each produced with ``--name-status -M -C``
    (raw scores such as ``R100`` are read by their letter, ``status_letter``); ``excluded`` is
    the caller's exclusion set (the ledgers, ``docs/CAPABILITIES.md``, the Doc Sync
    destinations); ``receipt`` the ``--review`` path, exempt from the declaration check only, on
    both the stamped and the unstamped close (T03a-S1).

    UNSTAMPED (no ``gate: 2`` — a record opened before v2, § Lifecycle): today's close — the LAST
    commit only, undeclared paths against ``files`` (never ``design_paths``) recorded as
    ``oversized_mini``, never refused, no upgrade. The caller still unions its own sync-regex
    hits into ``oversized_mini``, as today.

    STAMPED:
    - contract (D1) — ``contract_hit`` over every committed path, old and new, BEFORE
      ``excluded``: a Doc Sync destination cannot hide one;
    - new-source (D1) — more than 2 new source files that still exist after the last commit;
    - behaviours (D3.1) — more than 7; appetite (D4) — elapsed strictly past 2x the appetite;
    - every committed path not ``excluded``, not the receipt, must be in ``design_paths`` or
      ``amendments`` (D3.3): ``done`` is REFUSED naming each; ``blocked``/``handoff`` record it;
    - a run whose ``sync_hits`` is non-empty commits once in the main checkout (D7): more than
      one commit refuses ``done`` unless ``in_worktree``; ``blocked``/``handoff`` get a
      ``sync:`` finding instead, so a sanctioned halt is never trapped;
    - ``loc_added`` over 800 is a ``change:`` finding, never a refusal (D3.4).

    THE CHEAPEST WAY TO SATISFY THIS CLOSE WITHOUT THE OUTCOME (D-253): name every path the
    build might touch in the design note up front, or answer each refusal with a late
    ``--design-amend``. The first is the plan the lane otherwise never writes, so it produces the
    outcome; the second is COUNTED — the feedback row carries ``design_amends``, the count, so an
    amendment is never free; ``amended_paths`` is the ``CloseVerdict``'s own detail, never a
    feedback field. ``excluded`` is the caller's: widening it hides paths
    from the declaration check, which is why the contract test runs before it and why an
    excluded path never lends its membership to a rename. ``in_worktree`` is the caller's too:
    a main-checkout run that claims it skips the one-commit rule, so T08 derives it from git
    (a linked worktree's git dir differs from its common dir), never from a flag.
    """
    if verb not in _CLOSE_VERBS:
        raise ValueError(f"verb must be one of {_CLOSE_VERBS} (got {verb!r})")
    files = _norm_all(rec.files)
    amended = _norm_all(rec.amendments)
    # The receipt is spelled by the operator like a declared path, so it is normalised the
    # same way, once, for both the stamped and the unstamped close (T03a-O11).
    receipt = _norm_path(receipt) or None if receipt is not None else None

    def _exempt(p: str) -> bool:
        return excluded(p) or (receipt is not None and p == receipt)

    if not rec.stamped:
        last = commits[-1:]
        return CloseVerdict(
            refused=None,
            needs_full_review=False,
            upgrade=[],
            design_amends=0,
            amended_paths=[],
            oversized_mini=_undeclared(last, set(files), set(files), _exempt),
            loc_added=loc_added,
            over_appetite=False,
            findings=[],
        )

    rows = [row for c in commits for row in c]
    raised: dict[str, str] = {}
    findings: list[str] = []
    refusals: list[str] = []

    hits = [p for _s, path, old in rows for p in (path, old) if p is not None and contract_hit(p)]
    if hits:
        raised["contract"] = ", ".join(dict.fromkeys(hits))
    new = _surviving_new_sources(commits)
    if len(new) > _MAX_NEW_SOURCE:
        raised["new-source"] = f"{len(new)} new source files > {_MAX_NEW_SOURCE}: {', '.join(new)}"
    if rec.behaviours > _MAX_BEHAVIOURS:
        raised["behaviours"] = f"{rec.behaviours} Behaviours > {_MAX_BEHAVIOURS}"
    elapsed = now - rec.started_at
    over = rec.appetite > 0 and elapsed > _APPETITE_BREAKER * rec.appetite * 60
    if over:
        raised["appetite"] = (
            f"elapsed {int(elapsed // 60)}/{rec.appetite} min, past "
            f"{_APPETITE_BREAKER}x the appetite"
        )
    upgrade = [t for t in _UPGRADE_ORDER if t in raised]
    needs_full = "contract" in raised or "new-source" in raised
    for t in upgrade:
        tail = (
            " — done and handoff need --review <a full /fabrik-review receipt>"
            if t in ("contract", "new-source")
            else ""
        )
        findings.append(f"UPGRADE: {t} — {raised[t]}{tail}")

    declared = set(_norm_all(rec.design_paths)) | set(amended)
    undeclared = _undeclared(commits, declared, declared | set(files), _exempt)
    if undeclared and verb == "done":
        refusals.append(
            "REFUSED — fabrik-task: committed path(s) not named in the design note's APPROACH "
            f"or MIRROR: {', '.join(undeclared)} — add each with "
            "`step --phase 2 --design-amend <path>`, or close with `blocked`"
        )
    if rec.sync_hits and len(commits) > 1 and not rec.in_worktree:
        line = (
            f"a sync-path run commits once (D7); --commit lists {len(commits)} commits "
            f"(sync: {', '.join(sorted(rec.sync_hits))})"
        )
        if verb == "done":
            refusals.append(f"REFUSED — fabrik-task: {line}")
        else:
            findings.append(f"sync: {line}")
    if loc_added > _LOC_FINDING:
        findings.append(
            f"change: loc_added {loc_added} > {_LOC_FINDING} — a feature this size may be a module"
        )

    return CloseVerdict(
        refused="; ".join(refusals) if refusals else None,
        needs_full_review=needs_full,
        upgrade=upgrade,
        design_amends=len(amended),
        amended_paths=amended,
        oversized_mini=undeclared,
        loc_added=loc_added,
        over_appetite=over,
        findings=findings,
    )


# ── the close's review receipt (D1 checks (a)-(d), T03b) ─────────────────────────────────

REVIEWS_DIR = "docs/development/reviews/"
_RECEIPT_COMMAND = "/fabrik-review"
_CHECKER_TIMEOUT = 300
# The header zone — the checker's own (`check_review_coverage._in_progress`): the first 10 raw
# lines, normalised (`_normalized`) and fence-stripped (`_strip_fences`). Every header field
# below is read THERE, as a line-start field, so a body-deep, blockquoted or fenced copy never
# satisfies a check (round-1 O1, O4).
_HEADER_LINES = 10
_COMMAND_FIELD = re.compile(r"^\*\*Command:\*\* (.*)$", re.M)
_SURFACE_FIELD = re.compile(r"^\*\*Surface:\*\*(.*)$", re.M)
# `review_receipt.py --range A..B` writes `… = <HEAD>; range tip <sha>; `git diff …`` on the
# Surface line (review_receipt.py `_surface`); an unresolvable endpoint is written `?`.
_RANGE_TIP = re.compile(r"; range tip ([^\s;]+)")
# Every Status line, case-insensitive, the colon inside or outside the bold (`**Status:**`,
# `**Status**:`, `Status:`); the value is read with EVERY `*` removed, not only the ends — an
# end-only strip leaves `**CONVERGED**-ish` as `CONVERGED**-ish` (O7).
_STATUS_LINE = re.compile(r"^\**Status\**:\**[ \t]*(.*?)[ \t]*$", re.M | re.I)
_CLOSED_STATUS = "CONVERGED"
# CONVERGED followed only by whitespace, `(` or the end — a POSITIVE look-ahead, because a
# negative one (`(?![\w-])`) still admitted `CONVERGED/partial` and `CONVERGED*…` (O7).
_CLOSED_WORD = re.compile(r"CONVERGED(?=\s|\(|$)", re.I)
# ONE checker for both halves of (b) — the copy shipped BESIDE this module, never
# `<root>/scripts/enforcement/check_review_coverage.py`: the lane run being closed can commit
# an edit to the root copy (`raise SystemExit(0)` turns the grammar half into a constant
# pass), and two copies could grade one receipt with two versions (round-1 O5, S1). Imported
# lazily (185 KB) for its header-zone readers; its grammar runs as the (b) subprocess.
_LOCAL_CHECKER = Path(__file__).resolve().parent / "enforcement" / "check_review_coverage.py"
_crc_cache: list[Any] = []


def _crc() -> Any:
    """The co-shipped ``check_review_coverage`` module, loaded once; raises when it cannot load
    (the callers refuse — fail closed)."""
    if not _crc_cache:
        import importlib.util  # noqa: PLC0415 — only a receipt check pays for the 185 KB module

        spec = importlib.util.spec_from_file_location("_task_lane_crc", _LOCAL_CHECKER)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {_LOCAL_CHECKER}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _crc_cache.append(mod)
    return _crc_cache[0]


def _header_zone(crc: Any, text: str) -> str:
    return str(
        crc._strip_fences("".join(crc._normalized(text).splitlines(keepends=True)[:_HEADER_LINES]))
    )


def _status_refusals(crc: Any, zone: str) -> list[str]:
    """The refusal tails for the header Status lines — empty when EVERY one is CLOSED.

    CLOSED is ``CONVERGED`` (any case, bold markers stripped), or a CONVERGED line carrying the
    D-252 scope-growth-stop declaration the checker itself parses — its ``SCOPE_GROWTH_EXIT``
    window, with no ``_EXIT_NEGATION`` in either group. ``IN-PROGRESS``, ``BLOCKED``, any other
    value and a missing line refuse; a second Status line is read too, because the checker
    exempts the whole grammar when ANY header line is ``IN-PROGRESS`` (O1).
    """
    found = list(_STATUS_LINE.finditer(zone))
    if not found:
        return [f"carries no **Status:** line in its first {_HEADER_LINES} lines"]
    out: list[str] = []
    for m in found:
        value = m.group(1).replace("*", "").strip()
        if value.upper() == _CLOSED_STATUS:
            continue
        exit_ = crc.SCOPE_GROWTH_EXIT.search(m.group(0))
        if (
            _CLOSED_WORD.match(value) is not None
            and exit_ is not None
            and not crc._EXIT_NEGATION.search(exit_.group(1))
            and not crc._EXIT_NEGATION.search(exit_.group(2))
        ):
            continue
        out.append(
            f"is **Status:** {value!r} — only {_CLOSED_STATUS} (or the D-252 scope-growth-stop "
            "declaration) closes a review; an unfinished review is not a review"
        )
    return out


def _checker_env() -> dict[str, str]:
    """The (b) subprocess's environment: ``_git``'s scrub, ``GIT_OPTIONAL_LOCKS=0``, and every
    ``PYTHON*`` variable removed but ``PYTHONIOENCODING`` — with ``-I`` on the command line, no
    caller-side ``PYTHONPATH``/``sitecustomize`` can change the verdict (O6)."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in _GIT_ENV_OVERRIDES and (not k.startswith("PYTHON") or k == "PYTHONIOENCODING")
    }
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env


def _resolve_commit(root: Path, rev: str) -> str | None:
    """``rev`` as a full commit SHA, or ``None`` (unknown, AMBIGUOUS, not a commit — never a
    guess). Read-only: ``_git`` scrubs the repository-moving environment and turns optional
    locks off."""
    if not rev or rev.startswith("-"):
        return None
    r = _git(root, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{rev}^{{commit}}")
    if r is None or r.returncode != 0:
        return None
    sha = r.stdout.decode("ascii", "replace").strip()
    return sha or None


def check_review_receipt(path: Path, commits: list[str], *, root: Path) -> list[str]:
    """The refusal reasons for a ``--review <receipt>`` on a ``done``/``handoff`` close that owes
    the full review (``CloseVerdict.needs_full_review``); empty when all four hold. Reasons
    ACCUMULATE — every failing check appends its own, each opening with its check's letter (a
    missing file adds a ``not a file`` reason and stops there, since nothing else is readable):

    (a) the path — normalised as ``measure_close`` normalises the receipt (``_norm_path``),
        joined to the RESOLVED ``root`` and resolved itself (symlinks followed) — lies under the
        resolved ``<root>/docs/development/reviews/``;
    (b) the co-shipped checker (``_LOCAL_CHECKER``, never the root's copy) run as
        ``python -I <checker> --root <root> <receipt>`` in a scrubbed environment exits 0 — a
        missing, crashing, unlaunchable or timed-out checker refuses (fail closed) — AND every
        header Status line is CLOSED (``_status_refusals``);
    (c) the header zone holds exactly one line-start ``**Command:**`` field, and its token — the
        text up to the next `` · `` — is exactly ``/fabrik-review`` (``/fabrik-review-scoped``
        shares the prefix and is refused);
    (d) the header zone holds exactly one ``**Surface:**`` field, its ``range tip`` (written by
        ``review_receipt.py --range``) and the LAST of ``commits`` both resolve with ``git
        rev-parse`` to the same full SHA — a short SHA is compared in full, an ambiguous one
        refuses.

    (d) is TIP-ONLY, as the spec words it: the range's base is not checked, so a receipt over
    ``<last>~1..<last>`` passes for a run with earlier commits.

    THE CHEAPEST WAY TO SATISFY THIS CHECK WITHOUT THE OUTCOME (D-253): ``review_receipt.py
    --init --range <base>..<last>`` and never run the review — the skeleton's
    ``Status: IN-PROGRESS`` is exempt from ``check_review_coverage.py``, so its exit 0 alone
    would pass an unreviewed file; the Status half of (b) is the counter-measure, and running
    the CO-SHIPPED checker keeps the lane's own commits from editing the grader. What is left
    is flipping the Status to CONVERGED on a ledger the checker accepts — which costs the
    checker's own closing-round grammar (a re-derivation pass naming its finder seats), the
    work itself or a lie no text check can see.
    """
    root = Path(root).resolve()
    # Spelled like a declared path (`_norm_path`, as `measure_close` spells the receipt), then
    # RESOLVED — symlinks followed — so a link under reviews/ pointing elsewhere is judged by
    # where it lands.
    rel = _norm_path(os.fspath(path).replace(os.sep, "/"))
    receipt = (root / rel).resolve()
    reviews = (root / REVIEWS_DIR).resolve()
    reasons: list[str] = []
    if not receipt.is_relative_to(reviews) or receipt == reviews:
        reasons.append(f"(a) the receipt {path} resolves to {receipt}, not under {reviews}/")
    try:
        text = receipt.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        reasons.append(f"--review {path}: not a file under {root} ({exc.__class__.__name__})")
        return reasons

    # (b) the co-shipped checker, run as a subprocess and trusted only on exit 0.
    if not _LOCAL_CHECKER.is_file():
        reasons.append(
            f"(b) {_LOCAL_CHECKER} is missing — the receipt cannot be graded (fail closed)"
        )
    else:
        try:
            r = subprocess.run(
                [sys.executable, "-I", str(_LOCAL_CHECKER), "--root", str(root), str(receipt)],
                cwd=root,
                env=_checker_env(),
                capture_output=True,
                text=True,
                timeout=_CHECKER_TIMEOUT,
                check=False,
            )
            rc: int | None = r.returncode
            tail = (r.stdout + r.stderr).strip().splitlines()[-1:] or [""]
        except (OSError, subprocess.SubprocessError) as exc:
            rc, tail = None, [exc.__class__.__name__]
        if rc != 0:
            reasons.append(
                f"(b) {_LOCAL_CHECKER.name} refused the receipt (rc={rc}): {tail[0][:300]}"
            )

    # The header zone every field below is read in; an unreadable one refuses (b), (c), (d).
    try:
        crc = _crc()
        zone: str | None = _header_zone(crc, text)
    except Exception as exc:  # noqa: BLE001 — any load failure refuses (fail closed)
        crc, zone = None, None
        unread = f"the header cannot be read ({exc.__class__.__name__}: {exc})"
        reasons.extend(f"({c}) {unread}" for c in "bcd")
    if zone is None:
        return reasons

    # (b) also: the review FINISHED.
    reasons.extend(f"(b) the receipt {s}" for s in _status_refusals(crc, zone))

    # (c) one header Command field; its token compared whole.
    commands = _COMMAND_FIELD.findall(zone)
    token = commands[0].split(" · ", 1)[0].strip() if len(commands) == 1 else None
    if len(commands) != 1:
        reasons.append(
            f"(c) the receipt's header holds {len(commands)} **Command:** line(s), not exactly one"
        )
    elif token != _RECEIPT_COMMAND:
        reasons.append(
            f"(c) the receipt's **Command:** is {token!r}, not exactly {_RECEIPT_COMMAND!r} "
            "— a contract or new-source hit owes the full review"
        )

    # (d) one header Surface field; its range tip is the run's last commit.
    surfaces = _SURFACE_FIELD.findall(zone)
    m = _RANGE_TIP.search(surfaces[0]) if len(surfaces) == 1 else None
    if not commits:
        reasons.append("(d) no --commit was given, so the receipt's range tip has nothing to match")
    elif len(surfaces) != 1:
        reasons.append(
            f"(d) the receipt's header holds {len(surfaces)} **Surface:** line(s), not exactly one"
        )
    elif m is None:
        reasons.append(
            "(d) the receipt's **Surface:** line carries no range tip — make it with "
            "`review_receipt.py --range <base>..<last commit>`"
        )
    else:
        tip, last = _resolve_commit(root, m.group(1)), _resolve_commit(root, commits[-1])
        if tip is None or last is None or tip != last:
            reasons.append(
                f"(d) the receipt's range tip {m.group(1)} (→ {tip}) is not the last --commit "
                f"{commits[-1]} (→ {last})"
            )
    return reasons
