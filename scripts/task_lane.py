#!/usr/bin/env python3
# AFTER-EDIT: tests/test_task_lane_admission.py · tests/test_lane_replay.py · tests/fixtures/lane_replay.json (re-capture with scripts/lane_replay_capture.py, whose expected_verdict delegates to classify_commit, then --check) · scripts/command_run.py (the `_task_size_gate` caller, T08)
"""The /fabrik-task lane rules — admission half (plan 2026-10-02-plan-1 T02; spec D1, D2, D4, D7, D9, D12).

PURE: no import of ``command_run.py``, no environment reads that change an answer. The caller
(``command_run.py``, T08) computes the facts — the declared answers, the normalised ``--file``
list, the governance-sync hits, the appetite, ``--why``, the lane version, the refusal ledger's
path — and this module only decides.

- ``lane_version(root)`` — the repo-owned switch ``.fabrik/lane.json`` (``{"version": 1|2}``),
  else ``_LANE_DEFAULT``. Never a synced file: turning it on distributes nothing (D12).
- ``admit(...)`` — the ``start`` verdict. Version 1 is today's gate verbatim (files > 3,
  oneway, tradeoffs → chain; sync, heavy → right-now + full review; decision=no → right-now +
  scoped review). Version 2 replaces ONLY the file-count arm with the module tests: contract
  (path test or ``consumers=external``), oneway, tradeoffs (each now needs ``--why``), appetite
  > 240; sync, heavy, a migration path or more than 5 files keep the lane and select the FULL
  review (D2, D7).
- ``classify_commit(...)`` — the same tests applied to one commit's ``--name-status -M -C``
  rows; graded against T01's pinned replay (``tests/test_lane_replay.py``).
- ``record_refusal(ledger, row)`` — one JSON line per chain-routed start (D9).
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
import os
import re
import secrets
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# D12: the shipped gate. The day-7 rollout commit flips it to 2; until then a repo opts in with
# its own `.fabrik/lane.json`.
_LANE_DEFAULT = 1
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

# The dependency-segment, migration-segment and contract-basename tests are case-INSENSITIVE:
# a case-insensitive filesystem (macOS) serves `Vendor/` and `Migrations/` as the same
# directories (T02-O16). The test-path rule below stays case-sensitive.
_DEPENDENCY_SEGMENTS = frozenset({"node_modules", ".venv", "vendor"})
_CONTRACT_BASENAME = re.compile(r"openapi.*\.(json|yaml)|.*\.schema\.json", re.IGNORECASE)
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
    """Is ``path`` read outside this repo? ``specs/services/`` at the repo ROOT, or a basename
    fully matching ``openapi*.json``/``openapi*.yaml``/``*.schema.json`` case-insensitively at
    any depth — never under a ``node_modules``/``.venv``/``vendor`` path SEGMENT (spec D1)."""
    if _in_dependency_dir(path):
        return False
    if path.startswith("specs/services/"):
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


def is_new_source(status: str, path: str) -> bool:
    """A NEW source file: status ``A`` or ``C`` (a copy is a new file), not a test, not ``.md``
    and not in the measurement's exclusion set (which holds ``.fabrik/work/``, never the rest of
    ``.fabrik/`` — the pinned measurement rule is canonical; spec D1)."""
    return (
        status in ("A", "C")
        and not path.endswith(".md")
        and not is_test(path)
        and not _measure_excluded(path)
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
    if not path.is_file():
        return _LANE_DEFAULT, None, None
    try:
        content = path.read_bytes()
        data = json.loads(content.decode("utf-8"))
    except (OSError, ValueError) as exc:
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
        return Verdict(f"chain: {deciding[0]}", "scoped", deciding[0])

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
