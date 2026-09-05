"""Epic containment in check_plan_tickets (T05a).

Every test builds a throwaway plan SET under tmp_path
(``<root>/docs/development/plans/<dated-dir>/``) plus the epic file its spine names,
and drives the check's real CLI (``--plan-dir … --project-root … --json``) — the
author's emit-gate path, where findings keep full severity.

The rule under test (spec § Chain consolidation (e)): every ticket's Touches ⊆ the
spine's File Scope ⊆ the epic's ``owned_paths``, with the epic side GLOB-aware.
"""

from __future__ import annotations

import fnmatch
import importlib.util
import inspect
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from scripts.enforcement import check_plan_tickets as cpt

REPO = Path(__file__).resolve().parents[2]
CHECK = REPO / "scripts" / "enforcement" / "check_plan_tickets.py"
DIRNAME = "2026-01-02-plan-1-widget"
# The commit this rule lands on (T04b) — the "today's output" a no-`Epic:` spine must stay
# byte-identical to. Resolved through `git show`; the test SKIPS when the ref is not in the
# checkout (a shallow clone, a rewritten history).
BASE_REF = "2f982a5f"

EPIC_TEMPLATE = """---
kind: story
title: "Epic 1 — x"
status: 0
epic_n: 1
slug: x
depends_on: []
parallel_with: []
owned_paths: {owned}  # the concurrency contract (carried from 02)
---

# Epic 1 — x

Body.
"""


def _as_list(v: str | list[str] | tuple[str, ...]) -> list[str]:
    return [v] if isinstance(v, str) else list(v)


def _ticket(
    tid: str,
    title: str,
    touches: str | list[str],
    *,
    integration: bool = False,
    depends: str = "none",
) -> str:
    paths = _as_list(touches)
    touch = paths[0]
    return "\n".join(
        [
            f"# {tid} — {title}",
            "",
            f"Depends: {depends}",
            "Parallel: ⛓️",
            f"Complexity: {'native' if integration else 'simple'}",
            "Docs: none",
            f"Gate: pytest -q tests/test_{title}.py",
            *(["Integration: true"] if integration else []),
            "",
            "## Scope",
            "",
            f"{title} work.",
            "",
            "## Touches",
            "",
            *(f"- {p}" for p in paths),
            "",
            "## Behavior Contract",
            "",
            f"- **Given** the {title} fixture, **When** the check runs, "
            f"**Then** it is graded ({touch}:1).",
            "",
            "## Context Files",
            "",
            "- docs/small-context.md",
            "",
        ]
    )


def _spine(epic_line: str | None, scope: list[str], rows: list[tuple[str, str, str]]) -> str:
    board = "\n".join(f"| {tid} | {title} | — | ⛓️ | ⬜ | |" for tid, title, _ in rows)
    order = "\n".join(f"{i + 1}. {tid}" for i, (tid, _, _) in enumerate(rows))
    behaviors = "\n".join(
        f"- **Given** the {title} fixture, **When** the check runs, "
        f"**Then** it is graded ({touch}:1)."
        for _, title, touch in rows
    )
    scope_bullets = "\n".join(f"- {s}" for s in scope)
    return "\n".join(
        [
            "# Plan: widget",
            "",
            "Status: DRAFT",
            "**Owner:** tester",
            *([epic_line] if epic_line else []),
            "",
            "## File Scope",
            "",
            scope_bullets,
            "",
            "## Ticket Board",
            "",
            "| Ticket | Title | Depends | Parallel | State | Commit |",
            "|---|---|---|---|---|---|",
            board,
            "",
            "## Merge Order",
            "",
            order,
            "",
            "## Behavior Contract",
            "",
            behaviors,
            "",
        ]
    )


def _build(
    root: Path,
    *,
    epic_line: str | None = "Epic: docs/development/epics/1-x.md",
    owned_paths: tuple[str, ...] | list[str] | None = ("src/a/**",),
    t01_touch: str | list[str] = "src/a/x.py",
    integration_touch: str | list[str] = "src/a/receipts.md",
    scope: list[str] | None = None,
    write_epic: bool = True,
    epic_text: str | None = None,
    first_tid: str = "T01",
) -> Path:
    """Writes a two-ticket plan set (+ the epic its spine names); returns the plan dir."""
    plan_dir = root / "docs" / "development" / "plans" / DIRNAME
    plan_dir.mkdir(parents=True)
    t01_paths, t99_paths = _as_list(t01_touch), _as_list(integration_touch)
    rows = [(first_tid, "schema", t01_paths[0]), ("T99", "integration", t99_paths[0])]
    if scope is None:
        scope = [t01_paths[0], t99_paths[0]]
    (plan_dir / f"{DIRNAME}.md").write_text(_spine(epic_line, scope, rows), encoding="utf-8")
    (plan_dir / f"{first_tid}-schema.md").write_text(
        _ticket(first_tid, "schema", t01_paths), encoding="utf-8"
    )
    (plan_dir / "T99-integration.md").write_text(
        _ticket("T99", "integration", t99_paths, integration=True, depends=first_tid),
        encoding="utf-8",
    )
    if write_epic:
        epics = root / "docs" / "development" / "epics"
        epics.mkdir(parents=True)
        owned = "[]" if owned_paths is None else json.dumps(list(owned_paths))
        body = EPIC_TEMPLATE.format(owned=owned) if epic_text is None else epic_text
        (epics / "1-x.md").write_text(body, encoding="utf-8")
    return plan_dir


def _run(
    plan_dir: Path, root: Path, *, script: Path | None = None, as_json: bool = True
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(REPO)}
    cmd = [
        sys.executable,
        str(script or CHECK),
        "--plan-dir",
        str(plan_dir),
        "--project-root",
        str(root),
    ]
    if as_json:
        cmd.append("--json")
    return subprocess.run(
        cmd, cwd=REPO, capture_output=True, text=True, env=env, timeout=120, check=False
    )


def _findings(proc: subprocess.CompletedProcess[str]) -> list[dict]:
    assert proc.stdout, f"no output (rc={proc.returncode}): {proc.stderr}"
    return json.loads(proc.stdout)


def _epic_errors(proc: subprocess.CompletedProcess[str]) -> list[dict]:
    return [
        r for r in _findings(proc) if r["severity"] == "error" and "epic" in r["message"].lower()
    ]


# --- The predicate, directly -----------------------------------------------------------
# The CLI tests below exercise the RULE; these exercise the PREDICATE, because 6 of 9
# semantic mutants of `_glob_matches` / `_seg_regex` / `_carved_out` survived the CLI
# suite alone (acceptance round 1). Each test names the mutant it kills, and each mutant
# was applied on disk and watched fail before this file was committed.


def test_mid_double_star_spans_zero_segments():
    """Kills M1 — a mid `**` that requires ≥1 segment. `libs/**/x/**` must cover
    `libs/x/y.py`: `**/` is "any number of directories, zero included"."""
    assert cpt._glob_covers("libs/**/product_entitlements_bridge/**", "libs/peb/y.py") is False
    assert (
        cpt._glob_covers(
            "libs/**/product_entitlements_bridge/**", "libs/product_entitlements_bridge/y.py"
        )
        is True
    )
    assert (
        cpt._glob_covers(
            "libs/**/product_entitlements_bridge/**", "libs/a/b/product_entitlements_bridge/y.py"
        )
        is True
    )


def test_question_mark_never_crosses_a_separator():
    """Kills M3 — `?` translated to `.` instead of `[^/]`. (With the segment-wise matcher
    the crossing is also structurally impossible: `?` is only ever matched inside ONE
    segment. The assertion stays as the CONTRACT — it is what a future rewrite back to a
    single regex would have to keep true.)"""
    assert cpt._glob_covers("src/a?c/x.py", "src/abc/x.py") is True
    assert cpt._glob_covers("src/a?c/x.py", "src/a/c/x.py") is False
    # White-box, and the assertion that actually KILLS the mutant: the frontier never
    # feeds `_seg_matches` a string containing "/", so only this reaches the class.
    assert cpt._seg_matches("a?c", "a/c") is False
    assert cpt._seg_matches("a*c", "a/c") is False  # `*` does not cross one either


def test_literal_metacharacters_are_escaped():
    """Kills M4' — literals ceasing to be literal in `_seg_matches` (its ancestor mutant,
    dropping `re.escape`, died with the segment regex itself). `app/(admin)/**` is a
    LIVE epic shape (web-ecommerce-factory epic-7); unescaped, `(admin)` becomes a regex
    group that matches `admin` and misses the real directory."""
    assert cpt._glob_covers("app/(admin)/**", "app/(admin)/page.tsx") is True
    assert cpt._glob_covers("app/(admin)/**", "app/admin/page.tsx") is False
    assert (
        cpt._glob_covers("alembic/versions/(deploy)**", "alembic/versions/(deploy)_001.py") is True
    )


def test_directory_entry_needs_its_whole_subtree():
    """Kills M5 — dropping the SECOND subtree probe. One probe cannot separate these two:
    `docs/PROBE` matches `docs/*` as happily as `docs/**`."""
    assert cpt._glob_covers("docs/**", "docs/x/") is True
    assert cpt._glob_covers("docs/*", "docs/x/") is False
    assert cpt._glob_covers("docs/*", "docs/x.md") is True
    # The shape only the SECOND probe rejects: `docs/*/*` covers `docs/x/a.md` but not
    # `docs/x/y/z.md`, so it does not cover the DIRECTORY `docs/x/`. One probe says True.
    assert cpt._glob_covers("docs/*/*", "docs/x/") is False


def test_trailing_double_star_is_the_whole_subtree():
    """Kills M9 — a trailing `**` translated to `[^/]*` (one segment deep)."""
    assert cpt._glob_covers("src/a/**", "src/a/b/c/deep.py") is True
    assert cpt._glob_covers("src/a/**", "src/b/x.py") is False


def test_chained_double_stars_do_not_backtrack():
    """The frontier matcher replaced a `(?:[^/]+/)*`-per-`**` regex that backtracked
    exponentially: measured on this box, a 22-segment non-matching path took 3.7 s at 10
    chained `**`, 11.2 s at 11 and 32.2 s at 12 — on a pattern read from an epic file a
    project agent writes, with no timeout in the call path."""
    path = "libs/" + "/".join(f"seg{i}" for i in range(20)) + "/file.py"
    pattern = "libs/" + "/".join(["**"] * 12) + "/zzz/**"
    started = time.perf_counter()
    assert cpt._glob_covers(pattern, path) is False
    assert time.perf_counter() - started < 0.05


def test_carve_out_skips_governance_and_own_plan_metadata(tmp_path):
    """Kills M6 — `_carved_out` always False. A stem-scoped review receipt and a
    governance file are LEGAL ticket Touches (or already carry their own dedicated
    ERROR); an epic never owns either, so a raw containment loop would accuse both."""
    receipt = f"docs/development/reviews/{DIRNAME}-review.md"
    plan_dir = _build(
        tmp_path,
        owned_paths=["src/a/**"],
        t01_touch=["src/a/x.py", receipt],
        integration_touch=["src/a/receipts.md", "CHANGELOG.md"],
        scope=["src/a/x.py", "src/a/receipts.md"],
    )
    proc = _run(plan_dir, tmp_path)
    offenders = [
        r["message"]
        for r in _epic_errors(proc)
        if "reviews/" in r["message"] or "CHANGELOG.md" in r["message"]
    ]
    assert offenders == [], offenders


def test_ticket_touches_outside_the_epic_errors(tmp_path):
    """Ticket Touches ⊄ epic owned_paths → ERROR naming the ticket, the path and the epic."""
    plan_dir = _build(
        tmp_path,
        owned_paths=["src/a/**"],
        t01_touch="src/b/x.py",
        scope=["src/b/x.py", "src/a/receipts.md"],
    )
    proc = _run(plan_dir, tmp_path)
    hits = [
        r
        for r in _epic_errors(proc)
        if "T01" in r["message"] and "src/b/x.py" in r["message"] and "1-x.md" in r["message"]
    ]
    assert hits, [r["message"] for r in _findings(proc)]
    assert proc.returncode == 1


def test_ticket_inside_a_globbed_epic_raises_nothing(tmp_path):
    """`src/a/x.py` IS inside `src/a/**` — where the literal `_covered_by` says False."""
    assert cpt._covered_by("src/a/**", "src/a/x.py") is False  # the predicates are distinct
    plan_dir = _build(tmp_path, owned_paths=["src/a/**"], t01_touch="src/a/x.py")
    proc = _run(plan_dir, tmp_path)
    assert _epic_errors(proc) == []


def test_double_star_in_the_middle_matches(tmp_path):
    """`libs/**/product_entitlements_bridge/**` — the shape live epics actually use."""
    plan_dir = _build(
        tmp_path,
        owned_paths=["libs/**/product_entitlements_bridge/**"],
        t01_touch="libs/x/product_entitlements_bridge/y.py",
        integration_touch="libs/x/product_entitlements_bridge/receipts.md",
    )
    proc = _run(plan_dir, tmp_path)
    assert _epic_errors(proc) == []


def test_file_scope_entry_outside_the_epic_errors(tmp_path):
    """The SPINE link: a File Scope entry outside the epic ERRORs, tickets clean or not."""
    plan_dir = _build(
        tmp_path,
        owned_paths=["src/a/**"],
        scope=["src/a/x.py", "src/a/receipts.md", "src/c/"],
    )
    proc = _run(plan_dir, tmp_path)
    hits = [
        r
        for r in _epic_errors(proc)
        if "src/c/" in r["message"] and str(r["file_path"]).endswith(f"{DIRNAME}.md")
    ]
    assert hits, [r["message"] for r in _findings(proc)]


def test_single_star_does_not_cross_a_separator(tmp_path):
    """`src/a/b/deep.py` is NOT inside `src/a/*` — the fnmatch trap, closed."""
    assert fnmatch.fnmatch("src/a/b/deep.py", "src/a/*") is True  # what bare fnmatch admits
    plan_dir = _build(
        tmp_path,
        owned_paths=["src/a/*"],
        t01_touch="src/a/b/deep.py",
        integration_touch="src/a/receipts.md",
        scope=["src/a/b/deep.py", "src/a/receipts.md"],
    )
    proc = _run(plan_dir, tmp_path)
    assert [r for r in _epic_errors(proc) if "src/a/b/deep.py" in r["message"]], [
        r["message"] for r in _findings(proc)
    ]


def test_unresolvable_epic_path_errors(tmp_path):
    """A header the check cannot resolve is containment that never ran — never silent."""
    plan_dir = _build(tmp_path, epic_line="Epic: docs/development/epics/nope.md")
    proc = _run(plan_dir, tmp_path)
    # The arm's OWN message. Naming the path is not enough: the `except OSError` arm names
    # it too, so dropping the `is_file()` check left this test green.
    assert [
        r
        for r in _epic_errors(proc)
        if "no such file under" in r["message"] and "docs/development/epics/nope.md" in r["message"]
    ], [r["message"] for r in _findings(proc)]


@pytest.mark.parametrize(
    "declaration",
    ["owned_paths: []", "owned_paths:", 'owned_paths: ""'],
    ids=["empty-inline-list", "bare-key", "empty-scalar"],
)
def test_epic_with_an_empty_owned_paths_declaration_errors(tmp_path, declaration):
    """The three genuinely-EMPTY declarations, which must keep reading as "carries no
    owned_paths" — the blank-ITEM shape beside them is a malformed ENTRY and gets named
    instead."""
    epic = f"---\nkind: story\nepic_n: 1\nslug: x\n{declaration}\n---\n\n# Epic 1 — x\n"
    plan_dir = _build(tmp_path, epic_text=epic, t01_touch="src/a/x.py")
    proc = _run(plan_dir, tmp_path)
    assert [r for r in _epic_errors(proc) if "carries no owned_paths" in r["message"]], [
        r["message"] for r in _findings(proc)
    ]


def test_epic_without_owned_paths_errors(tmp_path):
    """Same fail-closed direction: an epic whose frontmatter carries no owned_paths."""
    plan_dir = _build(tmp_path, owned_paths=None)
    proc = _run(plan_dir, tmp_path)
    # The SPECIFIC message. "owned_paths" + the epic name also appears in the containment
    # ACCUSATION ("… is outside the epic's owned_paths (…1-x.md: )"), which is exactly what
    # a silent-on-empty regression produces — four false accusations, and a test that
    # cannot tell them from the guard.
    assert [r for r in _epic_errors(proc) if "carries no owned_paths" in r["message"]], [
        r["message"] for r in _findings(proc)
    ]
    assert [r for r in _epic_errors(proc) if "is outside the epic" in r["message"]] == []


def test_blockquoted_epic_header_is_parsed(tmp_path):
    """A `>`-quoted header must still key containment. The field family below `_F` refuses
    blockquotes because parsing a quoted `Depends:`/`Integration:` example LICENSES an
    overlap (fail-open); here the direction is inverted — NOT parsing means containment
    silently never runs, which is the exact fail-open this rule exists to close. Same
    split `STATUS_RE` already makes for the same reason."""
    plan_dir = _build(
        tmp_path,
        epic_line="> Epic: docs/development/epics/1-x.md",
        owned_paths=["src/a/**"],
        t01_touch="src/b/x.py",
        scope=["src/b/x.py", "src/a/receipts.md"],
    )
    proc = _run(plan_dir, tmp_path)
    assert [
        r for r in _epic_errors(proc) if "T01" in r["message"] and "src/b/x.py" in r["message"]
    ], [r["message"] for r in _findings(proc)]


def test_two_epic_headers_error(tmp_path):
    """First-wins on two headers is a silent fail-open: the second epic's scope is never
    enforced, and the hint promises ONE path per spine."""
    plan_dir = _build(
        tmp_path,
        epic_line="Epic: docs/development/epics/1-x.md\nEpic: docs/development/epics/2-y.md",
        owned_paths=["src/a/**"],
    )
    proc = _run(plan_dir, tmp_path)
    hits = [r for r in _epic_errors(proc) if "1-x.md" in r["message"] and "2-y.md" in r["message"]]
    assert hits, [r["message"] for r in _findings(proc)]


def test_duplicate_owned_paths_key_errors(tmp_path):
    """The ported parser RECORDS a duplicate key in `_dup_keys` and the consumer used to
    discard it: last-wins silently, so a ticket covered by the FIRST list gets a
    believable false accusation."""
    epic = (
        '---\nkind: story\ntitle: "Epic 1 — x"\nstatus: 0\nepic_n: 1\nslug: x\n'
        'owned_paths: ["src/a/**"]\n'
        'owned_paths: ["src/z/**"]\n'
        "---\n\n# Epic 1 — x\n"
    )
    plan_dir = _build(tmp_path, epic_text=epic, t01_touch="src/a/x.py")
    proc = _run(plan_dir, tmp_path)
    assert [r for r in _epic_errors(proc) if "twice" in r["message"]], [
        r["message"] for r in _findings(proc)
    ]
    # and NOT the false accusation the last-wins read produced
    assert [r for r in _epic_errors(proc) if "src/a/x.py" in r["message"]] == []


def test_bracket_class_in_owned_paths_is_refused(tmp_path):
    """`[seq]` is OUT OF CONTRACT for this matcher: `_seg_matches` compares `[` as an ordinary
    character, so `src/[ab]/**` would silently false-RED every ticket under `src/a/`. Refused loudly on
    the EPIC side (0 of 45 live owned_paths values carry a bracket). The TICKET side keeps
    reading `[id]` as a literal — the bound matters, so it is named: 8 of the 1,007
    Touches/File-Scope tokens in the 15 live non-archived plan sets (7 repos, the gate's
    own scope) carry a bracket, and all 8 are Next.js dynamic routes
    (`app/(app)/projects/[id]/`, `[token]`) which this file already documents as literal —
    refusing there would false-red real work. 0 are alternation sets."""
    plan_dir = _build(tmp_path, owned_paths=["src/[ab]/**"], t01_touch="src/a/x.py")
    proc = _run(plan_dir, tmp_path)
    assert [r for r in _epic_errors(proc) if "src/[ab]/**" in r["message"]], [
        r["message"] for r in _findings(proc)
    ]
    assert [r for r in _epic_errors(proc) if "src/a/x.py" in r["message"]] == []


def test_next_js_dynamic_route_touches_stay_literal(tmp_path):
    """The other half of that decision, guarded: a `[id]` Touches path under a globbed
    epic is covered, not refused."""
    assert cpt._glob_covers("app/**", "app/(app)/projects/[id]/page.tsx") is True
    plan_dir = _build(
        tmp_path,
        owned_paths=["app/**"],
        t01_touch="app/(app)/projects/[id]/page.tsx",
        integration_touch="app/receipts.md",
    )
    assert _epic_errors(_run(plan_dir, tmp_path)) == []


@pytest.mark.parametrize("shape", ["absolute", "dotdot", "absolute-after-a-valueless-line"])
def test_out_of_repo_epic_header_errors(tmp_path, shape):
    """The unusable-token arm — an absolute / `..` / glob header. Two things this test got
    wrong until round 5, both of which made it PASS while the guard was gone: it named a
    path that does not exist (so the missing-file arm answered for the guard), and it
    asserted only that some epic-flavoured error mentioned the string (which the
    false-accusation fallback also satisfies). It now points at a file that EXISTS outside
    the repo root — `root / "/abs/x"` is the absolute RHS pathlib REPLACES root with, i.e.
    a real traversal — and asserts the guard's own message.

    (It also covers the round-2 NameError: the stale `raw_header` reference ruff caught,
    which is a traceback on the CLI path and a swallowed NOTE on the adapter path.)"""
    outside = tmp_path / "outside_the_repo"
    outside.mkdir()
    (outside / "1-x.md").write_text(EPIC_TEMPLATE.format(owned='["src/a/**"]'), encoding="utf-8")
    # BOTH escape shapes, because they are two different arms of the same condition and the
    # `..` arm had no test: an ABSOLUTE header (pathlib REPLACES root with an absolute RHS)
    # and a `..` header (which climbs out of it). Each names a file that EXISTS, so an
    # unguarded read succeeds and enforces a FOREIGN epic.
    header = (
        str(outside / "1-x.md") if shape.startswith("absolute") else "../outside_the_repo/1-x.md"
    )
    # A valueless line BEFORE the offending one: the ERROR must still name the token that
    # was adjudicated, not `raw_headers[0]` (which is the empty one).
    line = (
        f"- **Epic:**\nEpic: {header}"
        if shape == "absolute-after-a-valueless-line"
        else f"Epic: {header}"
    )
    plan_dir = _build(tmp_path / "repo", epic_line=line, write_epic=False)
    proc = _run(plan_dir, tmp_path / "repo")
    hits = [r for r in _epic_errors(proc) if "is unusable" in r["message"]]
    assert hits, [r["message"] for r in _findings(proc)]
    assert header in hits[0]["message"], hits[0]["message"]


def test_star_chain_in_one_segment_does_not_backtrack():
    """Item 1's grader. `_seg_regex` emitted one `[^/]*` per `*`, so a `*` chain inside ONE
    segment backtracked catastrophically on a non-match: measured on this box against a
    41-character name, `src/a*a*a…b/**` took 0.80 s at 8 stars, 9.8 s at 10 and 74.7 s at
    12 — reachable from an epic file, with no timeout in the call path. 5 of 45 live
    `owned_paths` values already carry multi-`*` segments."""
    name = "a" * 40 + "c"
    pattern = "src/" + "a" + "*a" * 12 + "b" + "/**"
    started = time.perf_counter()
    assert cpt._glob_covers(pattern, f"src/{name}/x.py") is False
    assert time.perf_counter() - started < 0.05


def test_nested_and_tight_blockquote_headers_parse(tmp_path):
    r"""Item 3. `(?:[-*>]\s+)?` took ONE marker and required whitespace, so `>> Epic:`,
    `> > Epic:` and `>Epic:` parsed to nothing — containment silently skipped, the exact
    direction round 2 closed for the single `> ` form."""
    for prefix in (">> ", "> > ", ">"):
        root = tmp_path / f"case{len(prefix)}{prefix.count(' ')}"
        root.mkdir()
        plan_dir = _build(
            root,
            epic_line=f"{prefix}Epic: docs/development/epics/1-x.md",
            owned_paths=["src/a/**"],
            t01_touch="src/b/x.py",
            scope=["src/b/x.py", "src/a/receipts.md"],
        )
        proc = _run(plan_dir, root)
        assert [r for r in _epic_errors(proc) if "src/b/x.py" in r["message"]], (
            prefix,
            [r["message"] for r in _findings(proc)],
        )


def _git(cwd: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def test_staleness_quotes_the_trailer_as_written(tmp_path):
    """Item 4 (pre-existing, adjacent): `_staleness` keyed trailers UPPERCASE to join the
    Board and then QUOTED the uppercased key, so the ERROR said `Agent-Task: T05A` while
    the commit and the spine both say `T05a` — grep the string it prints and you find
    nothing."""
    plan_dir = _build(tmp_path, epic_line=None, write_epic=False, first_tid="T01a")
    src = tmp_path / "src" / "a"
    src.mkdir(parents=True)
    (src / "x.py").write_text("x = 1\n", encoding="utf-8")
    (src / "receipts.md").write_text("receipts\n", encoding="utf-8")
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    baseline = _git(tmp_path, "rev-parse", "HEAD")
    lock_dir = tmp_path / ".fabrik" / "plan-locks"
    lock_dir.mkdir(parents=True)
    (lock_dir / f"{DIRNAME}.json").write_text(
        json.dumps({"status": "active", "baseline_commit": baseline, "owned_paths": ["src/a/"]}),
        encoding="utf-8",
    )
    (src / "x.py").write_text("x = 2\n", encoding="utf-8")
    _git(tmp_path, "add", "src/a/x.py")
    _git(tmp_path, "commit", "-q", "-m", "work\n\nAgent-Task: T01a")
    messages = [r["message"] for r in _findings(_run(plan_dir, tmp_path))]
    flipped = [m for m in messages if "Board row is still" in m]
    assert flipped, messages
    assert all("Agent-Task: T01a" in m for m in flipped), flipped
    assert not any("T01A" in m for m in flipped), flipped


def test_star_is_a_wildcard_even_against_a_literal_star():
    """The literal-comparison branch ran BEFORE the star branch, so a pattern `*` aligned
    with a literal `*` in the NAME was consumed as an equal literal and no backtrack point
    was recorded — `_seg_matches("*", "**")` was False, against the docstring's "`*` = any
    run of non-`/` characters" (62 of 130,049 fuzz pairs, all of this one shape).
    Unreachable through today's two callers (`_carved_out` rejects `*` on the path side
    first), and a latent trap on a fleet-synced file the moment a third caller appears."""
    assert cpt._seg_matches("*", "**") is True
    assert cpt._seg_matches("*", "*x") is True
    assert cpt._seg_matches("a*", "a*b") is True
    assert cpt._seg_matches("*", "a*b") is True
    assert cpt._glob_covers("src/*/x.py", "src/*/x.py") is True


def test_mixed_bullet_and_quote_prefixes_parse(tmp_path):
    """`- > Epic:` and `> - Epic:` — a quoted bullet and a bulleted quote. The alternation
    took a bullet OR quote markers, never both, so each parsed to nothing: containment
    silently skipped, the same fail-open direction rounds 2 and 3 closed. WIDENED rather
    than documented out of contract, for consistency with those rounds (0 box-wide today,
    so the fire rate is unchanged either way)."""
    for prefix in ("- > ", "> - "):
        root = tmp_path / f"case{prefix.strip().replace('>', 'q').replace('-', 'b')}"
        root.mkdir()
        plan_dir = _build(
            root,
            epic_line=f"{prefix}Epic: docs/development/epics/1-x.md",
            owned_paths=["src/a/**"],
            t01_touch="src/b/x.py",
            scope=["src/b/x.py", "src/a/receipts.md"],
        )
        proc = _run(plan_dir, root)
        assert [r for r in _epic_errors(proc) if "src/b/x.py" in r["message"]], (
            prefix,
            [r["message"] for r in _findings(proc)],
        )


def test_dot_slash_epic_entry_is_normalised(tmp_path):
    """An epic entry is `.strip()`ed but was never path-normalised, unlike every Touches
    token — so `./src/a/**` matched nothing and LOUDLY accused every ticket the epic really
    owns. Normalised with a glob-SAFE normaliser, not `_norm_path`: that one strips
    symmetric emphasis wraps and would eat `**/x/**` down to `/x/`, which matches nothing
    (the second assertion guards exactly that)."""
    assert cpt._glob_covers("**/x/**", "a/x/y.py") is True  # must survive normalisation
    for entry in ("./src/a/**", "src/./a/**"):
        root = tmp_path / entry.replace("/", "_").replace(".", "d").replace("*", "s")
        root.mkdir()
        plan_dir = _build(root, owned_paths=[entry], t01_touch="src/a/x.py")
        proc = _run(plan_dir, root)
        assert _epic_errors(proc) == [], (entry, [r["message"] for r in _findings(proc)])


# --- The epic-side TOLERANCE arms: each silent today, each a false accusation if deleted -


def test_backticked_owned_paths_entry_is_tolerated(tmp_path):
    """`_norm_glob`'s quote/backtick strips — BOTH of them, and the second is reachable only
    through the first. The frontmatter parser strips a QUOTE pair, so a bare `"src/a/**"`
    never keeps its quotes; a markdown-decorated entry keeps its BACKTICKS, and a backticked
    QUOTED entry hands the quoted form on to the quote strip. Kept rather than deleted as
    out-of-contract (0 of 45 live values are decorated): four lines that turn a decorated
    entry from four false accusations into a silent pass.
    """
    for inner in ("`src/a/**`", '`"src/a/**"`'):
        root = tmp_path / f"case{len(inner)}"
        root.mkdir()
        epic = (
            f"---\nkind: story\nepic_n: 1\nslug: x\nowned_paths: [{inner}]\n---\n\n# Epic 1 — x\n"
        )
        plan_dir = _build(root, epic_text=epic, t01_touch="src/a/x.py")
        proc = _run(plan_dir, root)
        assert _epic_errors(proc) == [], (inner, [r["message"] for r in _findings(proc)])


def test_repeated_identical_epic_header_is_tolerated(tmp_path):
    """The distinct-TOKEN dedupe. Two headers naming the SAME epic are one epic — only a
    second, DIFFERENT epic is the ambiguity the more-than-one guard exists for."""
    line = "Epic: docs/development/epics/1-x.md"
    plan_dir = _build(tmp_path, epic_line=f"{line}\n{line}", t01_touch="src/a/x.py")
    proc = _run(plan_dir, tmp_path)
    assert _epic_errors(proc) == [], [r["message"] for r in _findings(proc)]


def test_glob_free_owned_paths_entry_is_tolerated(tmp_path):
    """`_glob_covers`'s fallback to `_covered_by`. An epic may own a bare directory or a
    single file (`db/schema.sql` is a live shape); without the fallback a glob-free entry
    would be matched as a pattern and cover only itself."""
    plan_dir = _build(
        tmp_path,
        owned_paths=["src/a"],
        t01_touch="src/a/x.py",
        integration_touch="src/a/receipts.md",
    )
    assert _epic_errors(_run(plan_dir, tmp_path)) == []


def test_scalar_owned_paths_is_tolerated(tmp_path):
    """The str -> [str] wrap. `owned_paths: "src/a/**"` (no brackets) genuinely parses to a
    STRING, and iterating a string yields CHARACTERS — an epic owning `s`, `r`, `c`, … ,
    which covers nothing."""
    epic = '---\nkind: story\nepic_n: 1\nslug: x\nowned_paths: "src/a/**"\n---\n\n# Epic 1 — x\n'
    plan_dir = _build(tmp_path, epic_text=epic, t01_touch="src/a/x.py")
    assert _epic_errors(_run(plan_dir, tmp_path)) == []


# (entry, the REASON its refusal must carry). The reason is asserted per shape and not as
# a generic " is unusable — ", because that substring is also produced by the message's own
# tail (" — containment cannot run"): a reason-dropping regression passed the generic form.
@pytest.mark.parametrize(
    "entry,reason",
    [
        ("../src/a/**", "`..` traversal"),
        ("/abs/**", "an absolute path"),
        ("~/x/**", "a `~`-rooted path"),
        ("src//a/**", "an empty path segment"),
        ("src\\a\\**", "separator"),
        (".", "the repo-root token"),
        ("src/[ab]/**", "bracket class"),
    ],
)
def test_structurally_unusable_owned_paths_entry_is_refused(tmp_path, entry, reason):
    """Item 3. Each of these matches NOTHING, so the epic-containment loops accused every
    ticket instead of naming the malformed entry — the fail direction this file's own
    `[seq]` doctrine already rejects. 0 of the 45 live owned_paths values carry any of
    these shapes (the denominator that justified normalising `./`)."""
    plan_dir = _build(tmp_path, owned_paths=[entry], t01_touch="src/a/x.py")
    proc = _run(plan_dir, tmp_path)
    refusals = [r for r in _epic_errors(proc) if "cannot run" in r["message"]]
    assert refusals, [r["message"] for r in _findings(proc)]
    # The entry as it lands IN THE FILE: `_build` writes the inline list with json.dumps,
    # so a backslash entry is stored escaped and the parser (which does no JSON unescaping)
    # reads the escaped form — the message quotes what the epic file actually says.
    assert json.dumps(entry)[1:-1] in refusals[0]["message"], refusals[0]["message"]
    # The REASON half — the whole point of refusing instead of accusing is that the message
    # says WHY the entry can never match, per shape.
    assert reason in refusals[0]["message"], refusals[0]["message"]
    assert [r for r in _epic_errors(proc) if "is outside the epic" in r["message"]] == []


@pytest.mark.parametrize("entry", ["src/..hidden/**", "src/a..b/**", "a..b/**"])
def test_dotdot_inside_a_segment_is_not_a_traversal(tmp_path, entry):
    """The `..` refusal is SEGMENT equality, not a substring test — `src/..hidden/**`,
    `src/a..b/**` and `a..b/**` are ordinary directory names (a dotfile-ish dir, a version
    range, a namespace), and a substring form would refuse all three and accuse every
    ticket beneath them."""
    touch = entry.replace("/**", "/x.py")
    receipts = entry.replace("/**", "/receipts.md")
    plan_dir = _build(
        tmp_path,
        owned_paths=[entry],
        t01_touch=touch,
        integration_touch=receipts,
        scope=[touch, receipts],
    )
    proc = _run(plan_dir, tmp_path)
    assert _epic_errors(proc) == [], [r["message"] for r in _findings(proc)]


@pytest.mark.parametrize("header", ["Epic:", "Epic: ", "> Epic:", "Epic:\t"])
def test_valueless_epic_header_fails_closed(tmp_path, header):
    """A header with no value used to match NOTHING, and matching nothing is containment
    silently not running — the fail-open every widening of this prefix has closed. It now
    parses to an empty token and takes the unusable-path ERROR."""
    plan_dir = _build(tmp_path, epic_line=header, write_epic=False)
    proc = _run(plan_dir, tmp_path)
    assert [r for r in _epic_errors(proc) if "is unusable" in r["message"]], [
        r["message"] for r in _findings(proc)
    ]


def test_owned_paths_entry_that_normalises_to_nothing_is_classified(tmp_path):
    """`"./"` normalises to the empty string. Dropping it silently made the epic report
    "carries no owned_paths" against a file that DECLARES one — true about the parsed value,
    false about the epic, and it sends the author to the wrong line (its sibling `"."` gets
    a precise reason)."""
    plan_dir = _build(tmp_path, owned_paths=["./"], t01_touch="src/a/x.py")
    proc = _run(plan_dir, tmp_path)
    assert [r for r in _epic_errors(proc) if "empty path once normalised" in r["message"]], [
        r["message"] for r in _findings(proc)
    ]
    assert [r for r in _epic_errors(proc) if "carries no owned_paths" in r["message"]] == []


@pytest.mark.parametrize("order", ["real-first", "valueless-first"])
def test_a_valueless_line_beside_a_real_header_does_not_shadow_it(tmp_path, order):
    """Round 6 made a valueless `Epic:`-shaped line parse — which handed the two-header
    guard an EMPTY token as a first-class epic. A spine whose real header is correct plus
    any such line (`- **Epic:**` in prose is one word away from the shape) then read as
    "2 different Epic: headers", took the early return, and skipped containment ENTIRELY:
    a pre-round-6 clean spine hard-reds and the rule stops running. Containment must still
    run — asserted by a ticket OUTSIDE the epic still being caught."""
    # BOTH orderings: picking `tokens[0]` instead of the first REAL token reads the
    # valueless line as the epic when it comes first, so `epic_rel` is "" and the
    # unusable-path ERROR fires — the same shadow fail-open from the other side.
    real, valueless = "Epic: docs/development/epics/1-x.md", "- **Epic:**"
    header = f"{real}\n{valueless}" if order == "real-first" else f"{valueless}\n{real}"
    inside = _build(tmp_path / f"in-{order}", epic_line=header, t01_touch="src/a/x.py")
    proc = _run(inside, tmp_path / f"in-{order}")
    assert _epic_errors(proc) == [], [r["message"] for r in _findings(proc)]

    outside = _build(
        tmp_path / f"out-{order}",
        epic_line=header,
        t01_touch="src/b/x.py",
        scope=["src/b/x.py", "src/a/receipts.md"],
    )
    proc = _run(outside, tmp_path / f"out-{order}")
    assert [r for r in _epic_errors(proc) if "src/b/x.py" in r["message"]], [
        r["message"] for r in _findings(proc)
    ]


def test_a_spine_whose_only_header_is_valueless_errors_once(tmp_path):
    """V6's intent, kept: the valueless header is still the loud unusable-path ERROR when
    it is the ONLY one — and exactly one finding, not a two-header complaint about an
    empty token."""
    plan_dir = _build(tmp_path, epic_line="Epic:", write_epic=False)
    proc = _run(plan_dir, tmp_path)
    errors = _epic_errors(proc)
    assert len(errors) == 1, [r["message"] for r in errors]
    assert "is unusable" in errors[0]["message"], errors[0]["message"]


def test_one_epic_named_twice_with_a_trailing_slash_is_one_epic(tmp_path):
    """`X` and `X/` are the same file. Backticks and `./` already deduped (both are
    normalised before the set); a trailing slash did not, so the same epic named twice in
    two spellings read as two epics and skipped containment."""
    line = "Epic: docs/development/epics/1-x.md"
    plan_dir = _build(tmp_path, epic_line=f"{line}\n{line}/", t01_touch="src/a/x.py")
    proc = _run(plan_dir, tmp_path)
    assert _epic_errors(proc) == [], [r["message"] for r in _findings(proc)]


def test_blank_block_list_item_is_named_not_misreported(tmp_path):
    """A BLANK block-list item (`- ` on its own) survives the block parser, and dropping it
    produced the very "carries no owned_paths" misreport the entry-classification comment
    says it closed — against a file that declares an entry. The inline path never had this
    shape (its splitter discards empties), which is why it hid."""
    epic = "---\nkind: story\nepic_n: 1\nslug: x\nowned_paths:\n  - \n---\n\n# Epic 1 — x\n"
    plan_dir = _build(tmp_path, epic_text=epic, t01_touch="src/a/x.py")
    proc = _run(plan_dir, tmp_path)
    assert [r for r in _epic_errors(proc) if "empty path once normalised" in r["message"]], [
        r["message"] for r in _findings(proc)
    ]
    assert [r for r in _epic_errors(proc) if "carries no owned_paths" in r["message"]] == []


@pytest.mark.parametrize("line", ["**Epic: {E}**", "*Epic: {E}*", "**Epic:** {E}"])
def test_whole_line_emphasis_header_is_read(tmp_path, line):
    """Whole-line bold/italic is ordinary markdown, and the CLOSING run stayed glued to the
    path (`…1-x.md**`), tripping the glob arm of the unusable-path guard — a hard red on a
    legitimate line. Peeled with a lookahead rather than an end-anchor: the anchored form
    stops matching the one live header on the box (an archived spine whose line carries
    trailing prose) and turns it into a SILENT non-parse, which is the fail-open every
    widening of this regex has closed."""
    header = line.format(E="docs/development/epics/1-x.md")
    plan_dir = _build(tmp_path, epic_line=header, t01_touch="src/a/x.py")
    proc = _run(plan_dir, tmp_path)
    assert _epic_errors(proc) == [], [r["message"] for r in _findings(proc)]


def test_trailing_prose_after_the_header_path_still_parses(tmp_path):
    """The shape the end-anchor would have broken — the ONE header line live on the box
    (`docs/…/epic-2-….md (epic_n 2, depends_on [1])`). Containment must RUN, which is
    asserted by a ticket outside the epic still being caught."""
    plan_dir = _build(
        tmp_path,
        epic_line="Epic: docs/development/epics/1-x.md (epic_n 1, depends_on [])",
        t01_touch="src/b/x.py",
        scope=["src/b/x.py", "src/a/receipts.md"],
    )
    proc = _run(plan_dir, tmp_path)
    assert [r for r in _epic_errors(proc) if "src/b/x.py" in r["message"]], [
        r["message"] for r in _findings(proc)
    ]


@pytest.mark.parametrize("value", ["epics/*", "docs/development/epics/1-x.md*", "docs/x/**"])
def test_a_trailing_star_in_the_value_is_not_emphasis(tmp_path, value):
    """The peel is SYMMETRIC — a tail run is emphasis only when one OPENED the line. The
    unpaired peel ate a `*`/`**` that belongs to the VALUE, and the two failure shapes are
    different sizes: `epics/*` and `docs/x/**` lost their glob and came back refused for the
    WRONG reason ("no such file"), while `<real-file>.md*` truncated to a path that EXISTS —
    a malformed header silently ACCEPTED and the wrong epic read. Here the epic file exists,
    so a silent accept shows up as zero findings."""
    plan_dir = _build(tmp_path, epic_line=f"Epic: {value}", t01_touch="src/a/x.py")
    proc = _run(plan_dir, tmp_path)
    hits = [r for r in _epic_errors(proc) if "is unusable" in r["message"]]
    assert hits, [r["message"] for r in _findings(proc)]
    assert value in hits[0]["message"], hits[0]["message"]


# --- The frontmatter reader: 20 fixtures, and parity with the source module -------------
# `_parse_frontmatter` here is a VERBATIM port of scripts/epic_order.py's (T03a, 544cf2ab).
# The hand-rolled reader it replaced diverged on 5 of these 20 — and NOT in the fail-closed
# direction it claimed: F05/F06/F10 SILENTLY TRUNCATE or empty a block list, which makes the
# gate accuse a ticket of escaping an epic that really does own its path. Each fixture is
# `(id, frontmatter text, expected owned_paths)`; the five divergent ones are marked.
FM_FIXTURES: list[tuple[str, str, object]] = [
    (
        "F01 inline list",
        '---\nowned_paths: ["src/a/**", "src/b/**"]\n---\n',
        ["src/a/**", "src/b/**"],
    ),
    (
        "F02 inline list + trailing comment (the schema's own example)",
        '---\nowned_paths: ["src/a/**"]  # the concurrency contract\n---\n',
        ["src/a/**"],
    ),
    ("F03 empty inline list", "---\nowned_paths: []\n---\n", []),
    (
        "F04 block list",
        "---\nowned_paths:\n  - src/a/**\n  - src/b/**\n---\n",
        ["src/a/**", "src/b/**"],
    ),
    (
        "F05 block list with a BLANK line between items (DIVERGED: truncated to 1)",
        "---\nowned_paths:\n  - src/a/**\n\n  - src/b/**\n---\n",
        ["src/a/**", "src/b/**"],
    ),
    (
        "F06 block list with a COMMENT line between items (DIVERGED: [])",
        "---\nowned_paths:\n  # the concurrency contract\n  - src/a/**\n  - src/b/**\n---\n",
        ["src/a/**", "src/b/**"],
    ),
    (
        "F07 UNINDENTED block list (predecessor handled it — its item regex made indent optional)",
        "---\nowned_paths:\n- src/a/**\n- src/b/**\n---\n",
        ["src/a/**", "src/b/**"],
    ),
    (
        "F08 key whose value is only a comment (DIVERGED: '#x' kept)",
        "---\nowned_paths: #x\n---\n",
        "",
    ),
    (
        "F09 hash inside a QUOTED block item (DIVERGED: cut at the hash)",
        '---\nowned_paths:\n  - "src/a #b/**"\n---\n',
        ["src/a #b/**"],
    ),
    (
        "F10 block list with a whitespace-only interior line (DIVERGED: truncated to 1)",
        "---\nowned_paths:\n  - src/a/**\n   \n  - src/b/**\n---\n",
        ["src/a/**", "src/b/**"],
    ),
    (
        "F11 scalar with a trailing comment",
        '---\nowned_paths: ["src/a/**"]\nslug: x  # short name\n---\n',
        ["src/a/**"],
    ),
    (
        "F12 spaces around the colon",
        '---\nowned_paths : ["src/a/**"]\n---\n',
        ["src/a/**"],
    ),
    (
        "F13 duplicate key — last wins, recorded",
        '---\nowned_paths: ["src/a/**"]\nowned_paths: ["src/b/**"]\n---\n',
        ["src/b/**"],
    ),
    (
        "F14 block list under a SCALAR key stays a scalar",
        '---\ntitle:\n  - a\nowned_paths: ["src/a/**"]\n---\n',
        ["src/a/**"],
    ),
    ("F15 quoted single value", '---\nowned_paths: "src/a/**"\n---\n', "src/a/**"),
    (
        "F18 `----` opener is NOT a fence — the file has no frontmatter",
        '----\nowned_paths: ["src/a/**"]\n---\n',
        None,
    ),
    (
        "F19 indented `  ---` interior line is NOT a fence (the block ends, the scan goes on)",
        "---\nowned_paths:\n  - src/a/**\n  ---\n  - src/b/**\n---\n",
        ["src/a/**"],
    ),
    (
        "F20 interior `--- note` is NOT a fence — no premature close",
        '---\nslug: x\n--- note\nowned_paths: ["src/a/**"]\n---\n',
        ["src/a/**"],
    ),
    ("F16 no frontmatter at all", "# Epic 1\n\nBody.\n", None),
    ("F17 unterminated frontmatter", '---\nowned_paths: ["src/a/**"]\n', None),
]


@pytest.mark.parametrize(
    "fid,text,expected", FM_FIXTURES, ids=[f[0].split()[0] for f in FM_FIXTURES]
)
def test_frontmatter_fixture(fid, text, expected):
    """The 20-fixture contract of the ported reader (5 of them RED against the
    hand-rolled predecessor this replaced)."""
    fm = cpt._parse_frontmatter(text)
    if expected is None:
        assert fm is None, fid
    else:
        assert fm is not None and fm.get("owned_paths") == expected, (fid, fm)


def test_frontmatter_parser_matches_epic_order_verbatim():
    """PARITY with the source module, SYMBOL BY SYMBOL — the port's whole point.

    Compares the source TEXT of every ported function (so a reworded docstring or a
    changed line shows up as a diff, not as a silently equal parse) plus the two ported
    constants' values, then the behaviour over every fixture. Hub-only: `epic_order.py` is
    not synced to projects, and a hub checkout that predates T03a's fence fixup has no
    `_find_fences` — both cases SKIP with the honest reason rather than fail.
    """
    hub = Path("/opt/fabrik/scripts/epic_order.py")
    if not hub.is_file():
        pytest.skip("scripts/epic_order.py is hub-only (not synced to projects)")
    spec = importlib.util.spec_from_file_location("_epic_order_for_parity", hub)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    for gate in ("_classify_fm_line", "_find_fences"):
        if not hasattr(mod, gate):
            pytest.skip(f"hub epic_order.py predates T03a's parser (no {gate})")

    # PORTED_SYMBOLS is `_parse_frontmatter`'s closure, read from the source at port time.
    functions = [
        "_strip_unquoted_comment",
        "_line_terminator",
        "_line_content",
        "_classify_fm_line",
        "_find_fences",
        "_collect_block_items",
        "_parse_frontmatter",
    ]
    text_drift = [
        name
        for name in functions
        if inspect.getsource(getattr(cpt, name)) != inspect.getsource(getattr(mod, name))
    ]
    assert text_drift == [], text_drift
    for const in ("_LIST_KEYS", "_LINE_TERMINATORS"):
        assert getattr(cpt, const) == getattr(mod, const), const

    behaviour_drift = [
        (fid, cpt._parse_frontmatter(text), mod._parse_frontmatter(text))
        for fid, text, _ in FM_FIXTURES
        if cpt._parse_frontmatter(text) != mod._parse_frontmatter(text)
    ]
    assert behaviour_drift == [], behaviour_drift


def test_no_epic_line_output_is_byte_identical_to_base(tmp_path):
    """A spine with no `Epic:` line behaves exactly as it did before this rule existed."""
    base_src = subprocess.run(
        ["git", "-C", str(REPO), "show", f"{BASE_REF}:scripts/enforcement/check_plan_tickets.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    if base_src.returncode != 0:
        pytest.skip(f"base ref {BASE_REF} not in this checkout")
    base_file = tmp_path / "base_check_plan_tickets.py"
    base_file.write_text(base_src.stdout, encoding="utf-8")
    plan_dir = _build(tmp_path, epic_line=None, write_epic=False)
    now = _run(plan_dir, tmp_path, as_json=False)
    before = _run(plan_dir, tmp_path, script=base_file, as_json=False)
    assert now.stdout == before.stdout
    assert now.returncode == before.returncode
