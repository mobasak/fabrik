#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_check_plan_tickets.py, commands/_sources/fabrik-plan-after-chat.md, commands/_sources/fabrik-plan-review.md, commands/_sources/fabrik-execute-plan.md, scripts/final_gate.py | none
"""Spine↔ticket plan-set contract gate (the spine+ticket plan shape).

Fires ONLY for files inside a dated plan directory
(``docs/development/plans/YYYY-MM-DD-plan-<slug>/``); monolith plans never enter it;
``plans/archived/<dated-dir>/`` is exempt (the whole-directory archive move must
never re-enter this gate — detected structurally as ``…/plans/archived/<dir>``,
NEVER by scanning absolute-path parts, so a repo living under a directory named
``archived`` is unaffected).

Checks (per the 2026-08-04 spine-ticket plan, the canonical grammar):

- **Structure:** a same-stem spine exists; Ticket-Board rows ↔ ticket files 1:1
  (join key: the ``T\\d{2}[a-z]?`` ID from the filename prefix vs the Board-row ID
  token, Board-section-scoped); every ``Depends:`` target exists; the graph is
  acyclic; ``## Merge Order`` is a topological sort of Depends; exactly one
  ``Integration: true`` ticket, last in Merge Order; the spine
  ``## Behavior Contract`` roll-up equals the union of ticket G/W/T rows.
- **Ownership:** Touches are the WRITE set — two tickets whose Touches entries
  OVERLAP (same path, or a directory entry covering another ticket's path) is an
  ERROR unless a Depends path connects them or a ``Serialized:`` row names the
  path; union(Touches) ⊆ spine File Scope; governance files never in Touches.
- **Routing cross-check:** a pool-tier ticket (Complexity simple/complex) whose
  Touches match the never-route set is an ERROR (``.env.example`` is exempt — a
  routine Doc-Sync file, not a secret).
- **Grounding floor:** every non-Integration ticket carries ≥1 ``path:line``.
- **Sizing:** READ budget ≤ READ_BUDGET_BYTES; ≤8 behaviors (WARN); ≤3 Gate lines
  (WARN). Severity by invocation context: cli/flip = ERROR; the gate path = WARN
  while the spine is DRAFT or IN-PROGRESS. (validate_conventions exempts this
  check's WARNs from --strict promotion — they are designed advisories.)
- **Board-staleness:** only when this plan's lock carries ``baseline_commit``.
  One bulk ``git log --first-parent -m --name-only`` over the window (merge
  commits diffed vs their first parent — orchestrator squash/merge commits are
  exactly the ones that must not escape): a commit touching a ticket's Touches
  without that ticket's own ``Agent-Task: T<id>`` trailer is an ERROR; a trailer
  commit whose Board row is still ⬜ (never flipped) is an ERROR. Sanctioned
  back-flips (✅→🔵/🔴) are compliant states. Any git error → NOTE + skip.

Deliberate design decisions (do not re-raise): enforcement is claim-transition
-scoped via check_convergence (a post-settlement evidence strip is out of the
single-operator threat model); a leading-pipe-less GFM Board table is out of
scope (the emitting command always writes leading pipes).

Calibration: READ_BUDGET_BYTES ships at 262144; the next plan touching this file
processes accumulated SIZING DEFECT Evidence rows and adjusts the constant.

Exit codes (CLI): 0 = pass/warn, 1 = any ERROR (or an invalid --plan-dir).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    from .check_convergence import PROOF
    from .validate_conventions import CheckResult, Severity
except ImportError:  # direct-script invocation (python scripts/enforcement/…py)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.enforcement.check_convergence import PROOF
    from scripts.enforcement.validate_conventions import CheckResult, Severity

READ_BUDGET_BYTES = 262144  # recalibrated from orchestrator-logged SIZING DEFECT rows
MAX_BEHAVIORS = 8
MAX_GATES = 3

# Canonical grammar regexes — keep byte-identical with check_convergence.py /
# check_plans.py / check_plan_quality.py / check_test_proposal.py / docs_updater.py
# (single-definition rule; a future consolidation imports from ONE module).
PLAN_DIR_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-plan-[a-z0-9-]+$")
TICKET_FILE_RE = re.compile(r"^(T\d{2}[a-z]?)-[a-z0-9-]+\.md$")
BOARD_SECTION_RE = re.compile(r"^##\s+Ticket Board\b(.*?)(?=^##\s|\Z)", re.I | re.M | re.S)
# Board rows tolerate a bold-wrapped ID cell (| **T01** | …).
BOARD_ROW_RE = re.compile(r"^\|\s*\**\s*(T\d{2}[a-z]?)\b", re.M)
MERGE_ORDER_SECTION_RE = re.compile(r"^##\s+Merge Order\b(.*?)(?=^##\s|\Z)", re.I | re.M | re.S)
# Order lines tolerate `1.`/`1)`/bullets and a bold-wrapped ID (same tolerance
# family as the Board/Serialized/Given regexes — silent format intolerance
# disables the topological + Integration-last checks with zero signal).
ORDER_LINE_RE = re.compile(r"^\s*(?:\d+[.)]|[-*])\s+\**\s*(T\d{2}[a-z]?)\**\s*$", re.M)
# Path — IDs separator tolerates em-dash, en-dash, or 1-2 hyphens; indentable.
SERIALIZED_LINE_RE = re.compile(r"^\s*Serialized:\s*(\S+)\s*[—–-]{1,2}\s*(.+)$", re.M)
# Status token: colon MANDATORY + same-line value ([^\S\n], never \s — \s crosses
# the newline). Bold-or-plain, colon inside or outside the bold.
STATUS_RE = re.compile(
    r"^\s*(?:[-*>]\s+)?\*{0,2}Status\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*(?:✅[^\S\n]*)?"
    r"\*{0,2}[^\S\n]*(DRAFT|PLANNED|CONVERGED|IN-PROGRESS|EXECUTED|BLOCKED)\b",
    re.I | re.M,
)
# PLANNED is DRAFT's sanctioned synonym (fabrik-plan-after-chat Phase 4).
_DRAFT_LIKE = ("DRAFT", "PLANNED", "")
# G/W/T rows: indentable bullets, case-insensitive, bold optional (aligned with
# check_test_proposal's counter). Scoped to the Behavior Contract SECTION by the
# callers — a Given quoted in ## Scope must not become a phantom roll-up row.
GIVEN_ROW_RE = re.compile(r"^\s*[-*]\s+(.*\*{0,2}Given\*{0,2}\b.*)$", re.I | re.M)
AGENT_TASK_RE = re.compile(r"^Agent-Task:\s*(T\d{2}[a-z]?)\b", re.I | re.M)
# Field lines tolerate a bullet prefix (bulleted metadata is natural markdown —
# same tolerance as the Board/Order/Serialized/Given regexes).
_F = r"^\s*(?:[-*>]\s+)?"
GATE_LINE_RE = re.compile(_F + r"Gate:", re.I | re.M)
INTEGRATION_RE = re.compile(_F + r"Integration:\s*true\b", re.I | re.M)
COMPLEXITY_RE = re.compile(_F + r"Complexity:\s*(\S+)", re.I | re.M)
DEPENDS_RE = re.compile(_F + r"Depends:\s*(.+)$", re.I | re.M)
PARALLEL_RE = re.compile(_F + r"Parallel:\s*(\S+)", re.I | re.M)
TICKET_ID_RE = re.compile(r"T\d{2}[a-z]?")
# Fenced blocks are QUOTED content — never counted (a `Gate:`/`Status:` inside an
# example must not trip the field counters).
_FENCE_RE = re.compile(
    # PARSING CONTRACT (recorded, review round 9): fences are BALANCED backtick
    # fences — a 3+-backtick opener closed by an EQUAL-length line-start closer —
    # plus inline single-line ```…``` quotes. Out of contract (documented, not
    # chased): tilde fences, over-long closers, and unpaired line-start fence
    # PAIRS — the emitting commands write balanced 3-backtick fences and quote
    # templates with 4-backtick outers, both in-contract; no live fleet file
    # violates this (verified 2026-08-05).
    # Line-anchored BLOCK fences + inline single-line fences. NEVER a bare
    # ```.*?``` — an unpaired backtick in prose would pair with the NEXT
    # block's opener and swallow real document body (live fleet regression:
    # calendar-orchestration-engine 2026-07-25 plan lost ## File Scope).
    r"(?:^[ \t]*(`{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$|```[^`\n]+```)",
    re.M | re.S,
)


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text)


GOVERNANCE_FILES = ("CHANGELOG.md", "INDEX.md", "docs/README.md", "docs/FEATURES.md")
NEVER_ROUTE_PREFIXES = (
    "scripts/enforcement/",
    "scripts/final_gate.py",
    "alembic/",
    "db/migrations/",
    "secrets/",
)
# `.env` and `.env.*` are secret material — EXCEPT `.env.example` (a routine
# Doc-Sync-Matrix file every env-var change touches).
_ENV_EXEMPT = ".env.example"
# File-Scope orphan-WARN exemptions (spine-metadata paths).
_SCOPE_WARN_EXEMPT = ("docs/development/reviews/", ".fabrik/plan-locks/", "~/")

# Adapter dedupe: one dir-level validation per process run, attached to the FIRST
# file seen from that dir (spine-only attachment would silently drop everything
# when only a ticket is staged).
_SEEN_DIRS: set[Path] = set()


def _section(text: str, title: str) -> str:
    # No trailing \b — a title ending in a non-word char (e.g. ')') would make the
    # boundary unmatchable. Prefix semantics: "File Scope" also matches
    # "File Scope (owned paths)".
    m = re.search(rf"^##\s+{re.escape(title)}(.*?)(?=^##\s|\Z)", text, re.I | re.M | re.S)
    return m.group(1) if m else ""


def _norm_path(p: str) -> str:
    p = p.strip().strip("`").strip("*").strip()
    if p.startswith("./"):
        p = p[2:]
    return p


def _list_paths(section_body: str) -> list[str]:
    """Bullet OR numbered lines → first token as a repo-relative path (markers
    after it ignored). Tolerates tab-indented bullets and bold-wrapped entries —
    a silently-empty parse would disable overlap/containment/never-route/budget
    checks with zero signal."""
    out: list[str] = []
    for line in section_body.splitlines():
        m = re.match(r"^\s*(?:[-*]|\d+[.)])\s+(\S+)", line)
        if m:
            token = _norm_path(m.group(1))
            if token:
                out.append(token)
    return out


def _covered_by(entry: str, path: str) -> bool:
    """DIRECTIONAL containment: `entry` covers `path`. Trailing slashes are
    insignificant on BOTH sides (`src/app` ≡ `src/app/`, as an entry AND as the
    covered path)."""
    return path.rstrip("/") == entry.rstrip("/") or path.startswith(entry.rstrip("/") + "/")


def _path_covers(entry: str, path: str) -> bool:
    """SYMMETRIC overlap (either side may be the covering dir) — for collision
    detection only; containment tests use the directional _covered_by."""
    return _covered_by(entry, path) or _covered_by(path, entry)


def _never_route(p: str) -> bool:
    """Bidirectional: a Touches entry that IS, is UNDER, or COVERS a never-route
    path is never-route (a `scripts/` or slash-less `scripts` dir entry owns
    scripts/enforcement/ too)."""
    if p == _ENV_EXEMPT:
        return False
    if p == ".env" or p.startswith(".env."):
        return True
    return any(_covered_by(n, p) or _covered_by(p, n) for n in NEVER_ROUTE_PREFIXES)


def _norm_behavior(line: str) -> str:
    line = line.strip().lstrip("-*").strip().rstrip(".")
    line = re.sub(r"\s*\(\d+\)\s*\.?$", "", line)  # trailing (N) row markers — house style
    return re.sub(r"\s+", " ", line.replace("**", "")).lower().rstrip(".")


@dataclass
class Ticket:
    tid: str
    path: Path
    text: str
    touches: list[str] = field(default_factory=list)
    context_files: list[str] = field(default_factory=list)
    depends: list[str] = field(default_factory=list)
    parallel: str = ""
    complexity: str = ""
    integration: bool = False
    behaviors: list[str] = field(default_factory=list)


def _err(
    msg: str, path: Path, severity: Severity = Severity.ERROR, hint: str | None = None
) -> CheckResult:
    return CheckResult(
        check_name="plan_tickets",
        severity=severity,
        message=msg,
        file_path=str(path),
        fix_hint=hint,
    )


def _parse_ticket(path: Path) -> Ticket:
    text = path.read_text(encoding="utf-8", errors="replace")
    # ONE policy: every semantic scan runs on FENCE-STRIPPED text (a fenced
    # `Depends: T05` / `Integration: true` example must neither false-red nor
    # quietly eat the integration role). Only the PROOF citation scan stays raw —
    # evidence legitimately lives inside fenced output blocks.
    scan = _strip_fences(text)
    tid = TICKET_FILE_RE.match(path.name).group(1)  # type: ignore[union-attr]
    dep_m = DEPENDS_RE.search(scan)
    depends = TICKET_ID_RE.findall(dep_m.group(1)) if dep_m else []
    par_m = PARALLEL_RE.search(scan)
    cpx_m = COMPLEXITY_RE.search(scan)
    return Ticket(
        tid=tid,
        path=path,
        text=text,
        touches=_list_paths(_section(scan, "Touches")),
        context_files=_list_paths(_section(scan, "Context Files")),
        depends=depends,
        parallel=par_m.group(1) if par_m else "",
        complexity=(cpx_m.group(1).lower() if cpx_m else ""),
        integration=bool(INTEGRATION_RE.search(scan)),
        # Section-scoped — a Given-row quoted elsewhere in the ticket must not
        # become a phantom entry in the roll-up equality check.
        behaviors=[
            _norm_behavior(m) for m in GIVEN_ROW_RE.findall(_section(scan, "Behavior Contract"))
        ],
    )


def _depends_connected(a: str, b: str, edges: dict[str, list[str]]) -> bool:
    """True when a transitive Depends path connects a↔b (either direction)."""

    def _reaches(src: str, dst: str) -> bool:
        stack, seen = [src], set()
        while stack:
            cur = stack.pop()
            if cur == dst:
                return True
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(edges.get(cur, []))
        return False

    return _reaches(a, b) or _reaches(b, a)


def _find_cycle(edges: dict[str, list[str]]) -> bool:
    white, gray, black = 0, 1, 2
    color = dict.fromkeys(edges, white)

    def _visit(n: str) -> bool:
        color[n] = gray
        for m in edges.get(n, []):
            if color.get(m, white) == gray:
                return True
            if color.get(m, white) == white and _visit(m):
                return True
        color[n] = black
        return False

    return any(color[n] == white and _visit(n) for n in list(edges))


def _sizing_severity(context: str, spine_status: str) -> Severity:
    if context in ("cli", "flip"):
        return Severity.ERROR
    # validate_conventions gate path: sibling-session / mid-run protection.
    if spine_status in (*_DRAFT_LIKE, "IN-PROGRESS"):
        return Severity.WARN
    return Severity.ERROR


def _is_plans_layout(plan_dir: Path) -> bool:
    """True when plan_dir sits at <root>/docs/development/plans/<name>."""
    parts = plan_dir.parts
    return len(parts) >= 4 and parts[-4:-1] == ("docs", "development", "plans")


def _is_archived(plan_dir: Path) -> bool:
    """plans/archived/<dated-dir> — structural, never an absolute-path parts scan."""
    parts = plan_dir.parts
    return len(parts) >= 5 and parts[-5:-1] == ("docs", "development", "plans", "archived")


def _repo_root(plan_dir: Path) -> Path | None:
    if not _is_plans_layout(plan_dir):
        return None
    return plan_dir.resolve().parents[3]


def _board_states(spine_text: str) -> dict[str, str]:
    """Board-row ID → state cell, header-aware (a reordered/extra column must not
    silently read the wrong cell; falls back to index 5 when no header names State)."""
    board = BOARD_SECTION_RE.search(spine_text)
    if not board:
        return {}
    state_idx = 5
    lines = board.group(1).splitlines()
    for line in lines:
        if line.strip().startswith("|") and "State" in line:
            cells = [c.strip() for c in line.split("|")]
            if "State" in cells:
                state_idx = cells.index("State")
                break
    states: dict[str, str] = {}
    for m in BOARD_ROW_RE.finditer(board.group(1)):
        cells = [c.strip() for c in m.string[m.start() :].split("\n", 1)[0].split("|")]
        # Strip the emoji variation selector (U+FE0F) — editors emit ⬜️ freely,
        # and exact-glyph equality would silently disable the never-flipped check.
        states[m.group(1).upper()] = (
            (cells[state_idx] if len(cells) > state_idx else "").replace("️", "").strip()
        )
    return states


def _staleness(plan_dir: Path, spine_text: str, tickets: dict[str, Ticket]) -> list[CheckResult]:
    """Execution-window board-currency checks — fail-safe (NOTE + skip) on git errors."""
    root = _repo_root(plan_dir)
    if root is None:
        return []
    lock = root / ".fabrik" / "plan-locks" / f"{plan_dir.name}.json"
    try:
        baseline = json.loads(lock.read_text(encoding="utf-8")).get("baseline_commit")
    except (OSError, ValueError):
        return []  # no lock/baseline → execution has not started → skip entirely
    if not baseline:
        return []
    results: list[CheckResult] = []
    states = _board_states(spine_text)
    try:
        # ONE bulk call: merge commits diffed vs their FIRST parent (-m + --first-parent)
        # — orchestrator squash/merge commits are exactly the ones that must not escape.
        out = subprocess.run(
            [
                "git",
                "log",
                "--first-parent",
                "-m",
                "--name-only",
                "--format=%x01%H%x02%B%x02",
                f"{baseline}..HEAD",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        ).stdout
    except Exception as e:  # noqa: BLE001 — fail-safe by convention, but observable
        print(f"NOTE: plan_tickets staleness skipped (git error: {e!r})")
        return results
    for record in out.split("\x01"):
        if not record.strip():
            continue
        try:
            sha, body, files_blob = record.split("\x02", 2)
        except ValueError:
            continue
        files = [f.strip() for f in files_blob.splitlines() if f.strip()]
        trailers = {t.upper() for t in AGENT_TASK_RE.findall(body)}
        # Trailer IDs are PER-PLAN (every plan set has a T01). Plan identity =
        # the commit touches THIS plan's directory — the same-commit Board-flip
        # discipline means every legitimate ticket commit stages the spine, and
        # Touches-overlap is NOT identity (two plans may legally reference the
        # same shared path; alpha's 'Agent-Task: T01' must never red beta).
        plan_prefix = f"docs/development/plans/{plan_dir.name}/"
        # Identity = the commit touches this plan's DIR (the flip discipline) OR
        # any of its tickets' Touches (the forgot-to-flip case MUST still be
        # caught — an identity that only exists when the discipline held would
        # be blind to its own violation). Cross-plan caveat: two active locks
        # with overlapping Touches is an excluded state (lock acquisition BLOCKs
        # on overlap), so the Touches key does not re-open the alpha/beta hole.
        touched_any = any(
            _covered_by(entry, f) for tk in tickets.values() for entry in tk.touches for f in files
        )
        commit_in_plan = any(f.startswith(plan_prefix) for f in files) or touched_any
        for t in tickets.values():
            touched = any(_covered_by(entry, f) for entry in t.touches for f in files)
            if touched and t.tid.upper() not in trailers:
                # WARN, not ERROR: on shared master this commit may be a SIBLING
                # agent's or the daily pipeline's — an unfixable hard-block would
                # red the gate for the plan's whole duration. The acceptance
                # review enforces the discipline; this line keeps it observable.
                results.append(
                    _err(
                        f"commit {sha[:8]} touches {t.tid}'s Touches without an "
                        f"'Agent-Task: {t.tid}' trailer",
                        t.path,
                        severity=Severity.WARN,
                        hint="Ticket work lands with its own Agent-Task trailer "
                        "(the same-commit Board-flip discipline)",
                    )
                )
        for tid in trailers:
            if not commit_in_plan:
                break
            if states.get(tid, "").startswith("⬜"):
                results.append(
                    _err(
                        f"commit {sha[:8]} carries 'Agent-Task: {tid}' but the Board "
                        f"row is still ⬜ (never flipped)",
                        plan_dir / f"{plan_dir.name}.md",
                        hint="Flip the Board row in the SAME commit as the ticket's merge",
                    )
                )
    return results


def check_plan_dir(plan_dir: Path, context: str = "cli") -> list[CheckResult]:
    """Dir-level plan-set validation. context ∈ {'cli','gate','flip'} (severity)."""
    plan_dir = plan_dir.resolve()
    if _is_archived(plan_dir):
        return []
    if not PLAN_DIR_NAME_RE.match(plan_dir.name) or not _is_plans_layout(plan_dir):
        return []
    results: list[CheckResult] = []
    spine = plan_dir / f"{plan_dir.name}.md"
    if not spine.is_file():
        # Gate path: a ticket-first set mid-authoring is the most draft-like state
        # there is (check_plan_quality documents the same) — advisory, never a
        # hard red on a sibling's in-flight work. Full ERROR at cli/flip.
        return [
            _err(
                f"dated plan directory has no same-stem spine ({spine.name})",
                plan_dir,
                severity=Severity.WARN if context == "gate" else Severity.ERROR,
                hint="The spine file name must equal the directory name — four gates key on it",
            )
        ]
    spine_text = spine.read_text(encoding="utf-8", errors="replace")
    # Fence-stripped for ALL semantic scans (a spine documenting its own emitted
    # ticket template must not read the template's `Status: DRAFT` as its own —
    # that would silently downgrade the whole contract to advisory).
    spine_scan = _strip_fences(spine_text)
    status_m = STATUS_RE.search(spine_scan)
    spine_status = status_m.group(1).upper() if status_m else ""
    # A PRESENT-but-unrecognized Status (`Status: COMPLETE`, `Status: Done ✅`, a
    # typo) must FAIL CLOSED — inheriting the absent-status DRAFT protection
    # would let one bad token silence the whole contract at the gate.
    _any_status = re.search(
        r"^\s*(?:[-*>]\s+)?\*{0,2}Status\*{0,2}[^\S\n]*:[^\S\n]*\S", spine_scan, re.M
    )
    if _any_status and not status_m:
        spine_status = "UNRECOGNIZED"  # not in any downgrade set → full severity

    tickets: dict[str, Ticket] = {}
    for f in sorted(plan_dir.glob("*.md")):
        m = TICKET_FILE_RE.match(f.name)
        if m:
            if m.group(1) in tickets:
                results.append(
                    _err(
                        f"duplicate ticket ID {m.group(1)}: {tickets[m.group(1)].path.name} "
                        f"and {f.name} — the later file would silently shadow the earlier",
                        f,
                    )
                )
                continue
            tickets[m.group(1)] = _parse_ticket(f)
    if spine_status == "UNRECOGNIZED":
        results.append(
            _err(
                "spine Status is not a pipeline value "
                "(DRAFT|PLANNED|CONVERGED|IN-PROGRESS|EXECUTED|BLOCKED)",
                spine,
                hint="Fix the Status: line — an unrecognized value fails closed",
            )
        )

    # --- Structure: Board rows ↔ ticket files 1:1 (Board-section-scoped) -------
    board = BOARD_SECTION_RE.search(spine_scan)
    row_ids = [m.group(1) for m in BOARD_ROW_RE.finditer(board.group(1))] if board else []
    for rid in row_ids:
        if rid not in tickets:
            results.append(_err(f"Board row {rid} has no ticket file on disk (orphan row)", spine))
    for tid in tickets:
        if tid not in row_ids:
            results.append(_err(f"ticket file {tid} has no Ticket Board row", spine))

    # --- Depends graph + Merge Order -------------------------------------------
    for t in tickets.values():
        for d in t.depends:
            if d not in tickets:
                results.append(
                    _err(
                        f"{t.tid}: Depends on unknown ticket {d} (no such ticket file)",
                        t.path,
                    )
                )
    edges = {t.tid: [d for d in t.depends if d in tickets] for t in tickets.values()}
    if _find_cycle(edges):
        results.append(_err("Depends: graph has a cycle", spine))
    mo_match = MERGE_ORDER_SECTION_RE.search(spine_scan)
    order = ORDER_LINE_RE.findall(mo_match.group(1)) if mo_match else []
    pos = {tid: i for i, tid in enumerate(order)}
    if set(order) != set(tickets):
        results.append(
            _err(
                "Merge Order does not list exactly the ticket set "
                f"(order={order}, tickets={sorted(tickets)})",
                spine,
            )
        )
    else:
        for t in tickets.values():
            for d in t.depends:
                if d in pos and pos[d] > pos[t.tid]:
                    results.append(
                        _err(f"Merge Order is not topological: {t.tid} depends on {d}", spine)
                    )

    # --- Integration cardinality + position -------------------------------------
    integrations = [t.tid for t in tickets.values() if t.integration]
    if len(integrations) != 1:
        results.append(
            _err(
                f"exactly one 'Integration: true' ticket required (found {len(integrations)})",
                spine,
            )
        )
    elif order and order[-1] != integrations[0]:
        results.append(
            _err(f"Integration ticket {integrations[0]} must be LAST in Merge Order", spine)
        )

    # --- Ownership (OVERLAP-aware: dir-vs-file covered, not just exact match) ----
    serialized: dict[str, set[str]] = {}
    if mo_match:
        for pm in SERIALIZED_LINE_RE.finditer(mo_match.group(1)):
            serialized[_norm_path(pm.group(1))] = set(TICKET_ID_RE.findall(pm.group(2)))
    ticket_list = sorted(tickets.values(), key=lambda t: t.tid)
    for i, ta in enumerate(ticket_list):
        for tb in ticket_list[i + 1 :]:
            if _depends_connected(ta.tid, tb.tid, edges):
                continue
            pair_overlaps: list[str] = []
            for pa in ta.touches:
                for pb in tb.touches:
                    if not _path_covers(pa, pb):
                        continue
                    # Serialized licence: the UNION of both entries' rows (a
                    # short-circuit `get(pa) or get(pb)` would ignore pb's row).
                    lic = (serialized.get(pa) or set()) | (serialized.get(pb) or set())
                    if {ta.tid, tb.tid} <= lic:
                        continue
                    pair_overlaps.append(pa if pa == pb else f"{pa} ~ {pb}")
            if pair_overlaps:
                # ONE finding per ticket pair (a dir-vs-many-files overlap must
                # not emit 20 identical-cause lines).
                sample = ", ".join(pair_overlaps[:3])
                more = f" (+{len(pair_overlaps) - 3} more)" if len(pair_overlaps) > 3 else ""
                results.append(
                    _err(
                        f"Touches overlap between {ta.tid} and {tb.tid} with no Depends "
                        f"path and no Serialized: row — {sample}{more}",
                        spine,
                        hint="Serialize the pair (Serialized: <path> — <ids>) or connect "
                        "them with a Depends edge",
                    )
                )
    for t in tickets.values():
        for p in t.touches:
            if any(_covered_by(p, g) for g in GOVERNANCE_FILES):
                results.append(
                    _err(
                        f"{t.tid}: governance file '{p}' in Touches — it is "
                        "orchestrator-applied via the Deltas block",
                        t.path,
                        hint="List it in Context Files (reads are unrestricted); the "
                        "orchestrator applies the entry at merge",
                    )
                )

    scope_section = _section(spine_scan, "File Scope")
    scope_paths = _list_paths(scope_section)
    if scope_section.strip() and not scope_paths:
        results.append(
            _err(
                "File Scope section is not parseable as a path list (use bullets or "
                "numbered entries) — containment checks are OFF until it parses",
                spine,
                severity=Severity.WARN,
            )
        )
    if scope_paths:
        for t in tickets.values():
            for p in t.touches:
                # DIRECTIONAL: a scope entry must cover the Touches path. The
                # symmetric test would let `Touches: src/` pass against a
                # one-file scope (the subset invariant inverted).
                if not any(_covered_by(s, p) for s in scope_paths):
                    results.append(
                        _err(f"{t.tid}: Touches path '{p}' is outside the spine File Scope", t.path)
                    )
        all_touches = [p for t in tickets.values() for p in t.touches]
        for s in scope_paths:
            if any(s.startswith(x) or x in s for x in _SCOPE_WARN_EXEMPT):
                continue
            if plan_dir.name in s:
                continue  # spine-metadata (the plan set itself / its lock / reviews)
            if not any(_path_covers(s, p) or _path_covers(p, s) for p in all_touches):
                results.append(
                    _err(
                        f"File Scope path '{s}' is owned by no ticket",
                        spine,
                        severity=Severity.WARN,
                    )
                )

    # --- Routing cross-check ------------------------------------------------------
    # The spine's Global Constraints may EXTEND the never-route set:
    # `Never-Route: <path>` lines (concrete prefixes only).
    extra_never_route = tuple(
        _norm_path(m)
        for m in re.findall(
            r"^\s*(?:[-*>]\s+)?Never-Route:\s*(\S+)",
            _section(spine_scan, "Global Constraints"),
            re.I | re.M,
        )
    )
    for t in tickets.values():
        if t.complexity and t.complexity not in ("simple", "complex", "native", "never-route"):
            results.append(
                _err(
                    f"{t.tid}: unrecognized Complexity value '{t.complexity}' "
                    "(simple|complex|native|never-route)",
                    t.path,
                    hint="An unknown tier would silently skip the never-route routing check",
                )
            )
        if t.complexity in ("simple", "complex"):
            for p in t.touches:
                if _never_route(p) or any(
                    _covered_by(n, p) or _covered_by(p, n) for n in extra_never_route
                ):
                    results.append(
                        _err(
                            f"{t.tid}: pool-tier ticket (Complexity: {t.complexity}) touches "
                            f"never-route path '{p}' — route it native",
                            t.path,
                            hint="Set the ticket's Complexity to the never-route tier "
                            "(native worktree coder), per 62-using-subagents.md:118-120",
                        )
                    )

    # --- Grounding floor -----------------------------------------------------------
    for t in tickets.values():
        if not t.integration and not PROOF.search(t.text):
            results.append(
                _err(f"{t.tid}: no path:line citation (per-ticket grounding floor)", t.path)
            )

    # --- Sizing ---------------------------------------------------------------------
    root = _repo_root(plan_dir)
    sev = _sizing_severity(context, spine_status)
    for t in tickets.values():
        if t.integration:
            continue
        read_bytes = 0
        if root is not None:
            for p in dict.fromkeys(t.touches + t.context_files):
                fp = root / p.rstrip("/")
                if fp.is_file():
                    read_bytes += fp.stat().st_size
                elif fp.is_dir():
                    # A directory entry owns its subtree — count it (else the
                    # LARGEST tickets score 0 bytes and the budget fails open).
                    for i, sub in enumerate(fp.rglob("*")):
                        if i > 2000:
                            read_bytes += (
                                READ_BUDGET_BYTES + 1
                            )  # runaway dir = OVER budget, decisively
                            break
                        if sub.is_file():
                            read_bytes += sub.stat().st_size
        if read_bytes > READ_BUDGET_BYTES:
            results.append(
                _err(
                    f"{t.tid}: READ budget {read_bytes} bytes exceeds "
                    f"READ_BUDGET_BYTES={READ_BUDGET_BYTES}",
                    t.path,
                    severity=sev,
                    hint="Split the ticket (author-split T##a/T##b) — a coder cannot hold "
                    "this read set in one context",
                )
            )
        if len(t.behaviors) > MAX_BEHAVIORS:
            results.append(
                _err(
                    f"{t.tid}: {len(t.behaviors)} behaviors > {MAX_BEHAVIORS}",
                    t.path,
                    severity=Severity.WARN,
                )
            )
        if len(GATE_LINE_RE.findall(_strip_fences(t.text))) > MAX_GATES:
            results.append(
                _err(f"{t.tid}: more than {MAX_GATES} Gate: lines", t.path, severity=Severity.WARN)
            )

    # --- Behavior-Contract roll-up equality ------------------------------------------
    spine_rows = {
        _norm_behavior(m) for m in GIVEN_ROW_RE.findall(_section(spine_scan, "Behavior Contract"))
    }
    ticket_rows = {b for t in tickets.values() for b in t.behaviors}
    for missing in sorted(ticket_rows - spine_rows):
        results.append(
            _err(f"spine Behavior Contract roll-up missing a ticket row: {missing[:80]}", spine)
        )
    for extra in sorted(spine_rows - ticket_rows):
        results.append(
            _err(f"spine Behavior Contract roll-up row matches no ticket: {extra[:80]}", spine)
        )

    # --- Board staleness (execution window) --------------------------------------------
    results.extend(_staleness(plan_dir, spine_scan, tickets))

    # --- Gate-context DRAFT downgrade (ALL findings, structural included) ---------------
    # DRAFT/PLANNED (or absent-status) = someone's mid-AUTHORING set on shared
    # master → all advisory in the gate path. IN-PROGRESS is deliberately NOT
    # here (plan Behavior 9 scopes its downgrade to SIZING only, via
    # _sizing_severity): mid-EXECUTION structural breakage is the owner's to fix,
    # and the ⬜-with-trailer staleness ERROR only exists in that window — a
    # blanket downgrade would make it unreachable. Sibling protection for
    # IN-PROGRESS sets comes from the lock_only/advisory paths in main()/check_file.
    if context == "gate" and spine_status in _DRAFT_LIKE:
        results = [
            CheckResult(
                check_name=r.check_name,
                severity=Severity.WARN if r.severity.value == "error" else r.severity,
                message=r.message,
                file_path=r.file_path,
                line_number=r.line_number,
                fix_hint=r.fix_hint,
            )
            for r in results
        ]
    return results


def check_file(file_path: Path) -> list[CheckResult]:
    """validate_conventions per-file adapter: dir-level validation ONCE per dir per
    run, attached to the FIRST file seen from that dir; empty for the rest."""
    if file_path.suffix != ".md":
        return []
    plan_dir = file_path.resolve().parent
    if not PLAN_DIR_NAME_RE.match(plan_dir.name):
        return []
    if _is_archived(plan_dir) or not _is_plans_layout(plan_dir):
        return []
    if plan_dir in _SEEN_DIRS:
        return []
    _SEEN_DIRS.add(plan_dir)
    try:
        found = check_plan_dir(plan_dir, context="gate")
    except Exception as e:  # noqa: BLE001 — fail-safe by convention, but observable
        print(f"NOTE: plan_tickets adapter suppressed: {e!r}")
        return []
    # This per-file adapter (the Tier-3 validate_conventions path) sees UNTRACKED
    # files and cannot tell whose plan a dir is — it is ALWAYS advisory. The
    # enforcing paths are the author's CLI, the CONVERGED/EXECUTED flips, and the
    # Tier-2 no-arg CLI (which carries the lock_only sibling logic).
    return [
        CheckResult(
            check_name=r.check_name,
            severity=Severity.WARN if r.severity.value == "error" else r.severity,
            message=r.message,
            file_path=r.file_path,
            line_number=r.line_number,
            fix_hint=r.fix_hint,
        )
        for r in found
    ]


def _discover_dirs(root: Path) -> tuple[list[Path], set[Path]]:
    """No-arg CLI discovery. Returns (dirs, lock_only) where dirs = dated plan dirs
    containing any changed file PLUS plan dirs whose ACTIVE lock's owned paths
    intersect the changed set, and lock_only = the subset selected ONLY via a lock
    (someone ELSE's plan — its findings are downgraded to advisory WARN by the
    caller: a sibling's mid-execution state must never hard-red this session's
    gate on files this session is forbidden to touch)."""
    changed: set[str] = set()
    wt_changed: set[str] = set()  # working-tree/staged only — MY session's edits
    try:
        # Tracked changes only — UNTRACKED files are a sibling's in-flight draft,
        # checked at staging (the check_convergence `??` policy). The change set
        # includes COMMITTED-BUT-UNPUSHED work (upstream..HEAD) — execute-plan
        # commits per phase and THEN runs the gate, so working-tree-only discovery
        # would go blind in the dominant real-world state.
        wt_cmds = [["diff", "--name-only"], ["diff", "--staged", "--name-only"]]
        cmds = list(wt_cmds)
        up = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "@{upstream}"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if up.returncode == 0 and up.stdout.strip():
            cmds.append(["diff", "--name-only", f"{up.stdout.strip()}..HEAD"])
        for args in cmds:
            proc = subprocess.run(
                ["git", *args], cwd=root, capture_output=True, text=True, timeout=15
            )
            if proc.returncode != 0:
                # Skip THIS command, keep the others (a stale upstream ref must
                # not throw away the working-tree diff results).
                print(
                    f"NOTE: plan_tickets discovery: `git {' '.join(args)}` exit {proc.returncode} — skipped"
                )
                continue
            found_paths = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
            changed.update(found_paths)
            if args in wt_cmds:
                wt_changed.update(found_paths)
    except Exception as e:  # noqa: BLE001
        print(f"NOTE: plan_tickets discovery skipped (git error: {e!r})")
        return [], set()
    # OWN = discovered via MY working-tree/staged edits. A dir seen ONLY via
    # upstream..HEAD is a sibling's committed-but-unpushed work on shared master
    # (the normal state here) — advisory, same as lock-only selection.
    own_dirs: set[Path] = set()
    for c in wt_changed:
        p = Path(c)
        if len(p.parts) >= 4 and p.parts[:3] == ("docs", "development", "plans"):
            if PLAN_DIR_NAME_RE.match(p.parts[3]):
                own_dirs.add(root / "docs" / "development" / "plans" / p.parts[3])
    upstream_dirs: set[Path] = set()
    for c in changed - wt_changed:
        p = Path(c)
        if len(p.parts) >= 4 and p.parts[:3] == ("docs", "development", "plans"):
            if PLAN_DIR_NAME_RE.match(p.parts[3]):
                upstream_dirs.add(root / "docs" / "development" / "plans" / p.parts[3])
    lock_dirs: set[Path] = set()
    locks = root / ".fabrik" / "plan-locks"
    if locks.is_dir():
        for lf in locks.glob("*.json"):
            try:
                data = json.loads(lf.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if data.get("status") != "active":
                continue
            owned = data.get("owned_paths", [])
            if any(any(_path_covers(o, c) for o in owned) for c in changed):
                cand = root / "docs" / "development" / "plans" / lf.stem
                if cand.is_dir():
                    lock_dirs.add(cand)
    dirs = sorted(d for d in own_dirs | lock_dirs | upstream_dirs if d.is_dir())
    advisory = {d for d in (lock_dirs | upstream_dirs) if d not in own_dirs}
    return dirs, advisory


def main() -> int:
    parser = argparse.ArgumentParser(description="Spine↔ticket plan-set contract gate.")
    parser.add_argument("--plan-dir", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.resolve()
    if args.plan_dir:
        target = args.plan_dir.resolve()
        if not target.is_dir() or not PLAN_DIR_NAME_RE.match(target.name):
            print(
                f"✗ --plan-dir {args.plan_dir} is not a dated plan directory "
                "(YYYY-MM-DD-plan-<slug>/)"
            )
            return 1
        if not _is_plans_layout(target):
            print(f"✗ --plan-dir {args.plan_dir} is not under docs/development/plans/")
            return 1
        dirs = [target]
        lock_only: set[Path] = set()
    else:
        _SEEN_DIRS.clear()  # in-process reuse safety (one logical run per main())
        dirs, lock_only = _discover_dirs(root)
    if not dirs:
        print("no plan directories in scope")
        return 0
    # Explicit --plan-dir = the author's own emit gate → full severity ("cli").
    # No-arg discovery = the shared Tier-2 gate path → "gate" (DRAFT downgrade
    # applies). A dir selected ONLY via a sibling's active lock is that sibling's
    # plan — ALL its findings become advisory WARNs (this session cannot fix them).
    run_context = "cli" if args.plan_dir else "gate"
    all_results: list[CheckResult] = []
    for d in dirs:
        found = check_plan_dir(d, context=run_context)
        if d in lock_only:
            found = [
                CheckResult(
                    check_name=r.check_name,
                    severity=Severity.WARN if r.severity.value == "error" else r.severity,
                    message=f"[sibling plan] {r.message}",
                    file_path=r.file_path,
                    line_number=r.line_number,
                    fix_hint=r.fix_hint,
                )
                for r in found
            ]
        all_results.extend(found)
    if args.json:
        print(json.dumps([r.to_dict() for r in all_results], indent=2))
    else:
        for r in all_results:
            icon = {"pass": "✓", "warn": "⚠", "error": "✗"}[r.severity.value]
            print(f"{icon} [{r.check_name}] {r.file_path}: {r.message}")
            if r.fix_hint:
                print(f"  → Fix: {r.fix_hint}")
    return 1 if any(r.severity.value == "error" for r in all_results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
