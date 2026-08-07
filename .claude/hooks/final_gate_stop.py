#!/usr/bin/env python3
"""Claude Code SessionStart + Stop hooks — enforce final_gate as the definition of done.

ONE script, two modes:
  --baseline  (SessionStart): snapshot the set of FAILING gate checks the session
              INHERITED. Never blocks. This is what stops the hook from trapping the
              agent on a project's pre-existing debt.
  (default)   (Stop): re-run the gate and BLOCK end-of-turn only when the session has
              introduced NEW failing checks (current failures − baseline) AND the
              worktree is dirty. So the agent is blocked only for problems IT caused.

Safety:
- **Fail-open**: any internal error, an un-runnable/unparseable gate, or a missing
  baseline → allow the stop (a hook must never trap the session, and inherited debt
  must never be attributed to the agent).
- **Loop cap**: after CAP consecutive blocked stops it allows the stop with a loud
  warning (Claude Code exposes no stop_hook_active flag, verified against the docs).
- **Scoped**: clean worktree / non-fabrik project → instant pass.

Contract (verified against https://code.claude.com/docs/en/hooks, 2026-06):
- stdin JSON: session_id, cwd, hook_event_name, ...
- block: print {"decision":"block","reason":...} on stdout, exit 0.
- allow: exit 0 with no decision.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

CAP = 3  # consecutive blocked stops before letting it stop anyway (anti-trap)


def decide(
    git_dirty: bool,
    has_new_failures: bool,
    gate_attempts: int,
    cap: int = CAP,
    own_uncommitted: bool = False,
    commit_attempts: int = 0,
) -> tuple[str, int, int]:
    """Pure decision logic (unit-tested). Returns (action, gate_attempts', commit_attempts').

    action ∈ {"allow", "block", "block_commit", "allow_warn_gate",
    "allow_warn_commit"} — the warn actions name their CAUSE so the caller's
    warning can be truthful (an unconditional "gate still RED" message was
    factually false on commit-cap exhaustion; review finding). Priority:
    1. new gate failures (dirty tree)  → "block"        (fix before anything)
    2. session-authored files uncommitted → "block_commit" (an uncommitted task
       is an UNFINISHED task — CLAUDE.md § EXIT)
    Each reason has its OWN anti-trap counter: exhausting the gate CAP must not
    starve the commit check (or vice versa) — with a shared counter, alternating
    causes walked straight past enforcement (review finding, 2026-08-07).
    """
    if not git_dirty:
        return "allow", 0, 0  # nothing changed → nothing to gate
    # A cause's counter RESETS the moment that cause stops being true — a stale
    # count must never carry into an unrelated future streak of the same cause
    # (review finding: a resolved gate streak's persisted 3 waved a brand-new
    # regression through on its FIRST stop). A still-true cause keeps its count
    # across interleaves (the streak genuinely continues).
    if not has_new_failures:
        gate_attempts = 0
    if not own_uncommitted:
        commit_attempts = 0
    if has_new_failures:
        gate_attempts += 1
        if gate_attempts > cap:
            return "allow_warn_gate", 0, commit_attempts
        return "block", gate_attempts, commit_attempts
    if own_uncommitted:
        commit_attempts += 1
        if commit_attempts > cap:
            return "allow_warn_commit", gate_attempts, 0
        return "block_commit", gate_attempts, commit_attempts
    return "allow", 0, 0  # green + own work committed (or none authored)


def _git_dirty(root: Path) -> bool:
    out = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout
    return bool(out.strip())


def _run_gate(root: Path) -> tuple[bool, set[str], dict[str, str]]:
    """Run final_gate --lean --check --json. Returns (passed, failing_check_names, outputs).

    outputs maps each failing check name to its output text — used by the Stop path to
    attribute a NEW failure to this session's files vs a sibling's shared-tree dirt.
    Per-check (not concatenated) so attribution can scope to the NEW failures only:
    an inherited baseline failure that happens to cite a session file must not
    contaminate the verdict on an unrelated new one.

    Fail-open: a gate that can't run or whose output can't be parsed as a definitive
    failure returns (True, empty, {}) — we never block on an indeterminate result.
    """
    venv_py = root / ".venv" / "bin" / "python"
    py = str(venv_py) if venv_py.exists() else sys.executable
    proc = subprocess.run(
        [py, "scripts/final_gate.py", "--lean", "--check", "--json"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=110,
    )
    if proc.returncode == 0:
        return True, set(), {}
    try:
        data = json.loads(proc.stdout)
        if data.get("status") == "failure":
            fails = data.get("failures", [])
            names = {f.get("check", "?") for f in fails}
            outputs = {f.get("check", "?"): str(f.get("output") or "") for f in fails}
            return False, names, outputs
    except Exception:
        pass
    # Non-zero but not a definitive parsed failure (crash, missing deps, etc.) →
    # fail-open: don't block on a gate we couldn't actually evaluate.
    return True, set(), {}


# Path-shaped tokens in a failure output: something with a slash, or a dotted
# filename. Attribution compares these as normalized relative paths — substring
# matching is banned ('app.py' must never match inside 'data_app.py').
_PATH_TOKEN = re.compile(r"[A-Za-z0-9_\-./]*/[A-Za-z0-9_\-./]+|[A-Za-z0-9_\-]+\.[A-Za-z0-9_]{1,8}")

# Governance files EVERY session routinely writes (Completion Contract / Doc Sync
# Matrix obligations). A failing check that cites ONLY these plus sibling files is
# sibling-caused: the sibling's code change created the CHANGELOG/INDEX obligation,
# and the session's own routine edits to these files must not claim the failure.
_ROUTINE_GOVERNANCE = frozenset(
    {"CHANGELOG.md", "INDEX.md", "PORTS.md", "docs/README.md", "docs/LESSONS_LEARNT.md"}
)


def _failure_cites_session(new_outputs: list[str], authored: dict[str, int], session_floor: float) -> bool | None:
    """Attribute NEW gate failures to this session by cited path, or None if indeterminate.

    Returns True (session-caused → block), False (sibling-caused → downgrade), or
    None (no path-shaped evidence in any new failure's output → cannot attribute →
    caller keeps the pre-attribution behavior, i.e. block up to the cap; the known
    shared-tree false-positive checks all cite paths, so indeterminate is rare).

    - Tokens are compared as normalized relative paths, never substrings: exact
      match, cited-path suffix (`/opt/x/src/a.py` vs authored `src/a.py`), or
      basename cite (`a.py` vs authored `src/a.py`).
    - authored entries older than session_floor (the SessionStart baseline mtime)
      are a resumed transcript's ancient edits, not this session's work (same
      false-positive class the own_uncommitted timestamp guard kills).
    - _ROUTINE_GOVERNANCE names never attribute on their own — every session
      writes them, and Doc Sync failures cite the obligation doc by name even
      when a SIBLING's code change created the obligation.
    """
    text = "\n".join(new_outputs)
    tokens = {t.strip("./,:;)(\"'") for t in _PATH_TOKEN.findall(text)}
    tokens = {t for t in tokens if t and ("." in t or "/" in t)}
    if not tokens:
        return None
    candidates = {
        rel
        for rel, ts in authored.items()
        if rel not in _ROUTINE_GOVERNANCE and (not ts or not session_floor or ts >= session_floor)
    }
    for t in tokens:
        for rel in candidates:
            if t == rel or t.endswith("/" + rel) or rel.endswith("/" + t):
                return True
    # No non-governance match. If the output cites ONLY routine-governance names and
    # the session authored one of them, the session may have broken that file ITSELF
    # (malformed CHANGELOG edit) — that is not attributable either way: indeterminate,
    # keep blocking up to the cap. The sibling-obligation incident is different: its
    # output also cites the sibling's trigger file, a non-governance token.
    non_gov = {t for t in tokens if t not in _ROUTINE_GOVERNANCE}
    if not non_gov and any(g in authored for g in tokens):
        return None
    return False


# Tools whose input.file_path marks a file THIS session authored/edited. Bash
# heredoc writes are invisible here — under-detection is the fail-open direction.
_EDIT_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})


def _session_files(transcript_path: str, root: Path) -> dict[str, int]:
    """Root-relative path → unix ts of this session's LAST Edit/Write to it.

    Parsed from the session transcript (JSONL). Fail-open: any parse problem →
    empty dict (the commit check then never blocks). Only paths INSIDE root count
    (memory/config edits outside the repo are not repo work). Timestamps matter:
    a long-lived resumed session's transcript spans weeks — an edit that was
    COMMITTED long ago must not re-attach to today's unrelated dirt (live
    false-positive on first ship: a July edit + the daily pipeline's timestamp
    bump today flagged the file as this session's unfinished work)."""
    import datetime as _dt

    files: dict[str, int] = {}
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"tool_use"' not in line:
                    continue  # cheap pre-filter before json cost
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                content = (entry.get("message") or {}).get("content")
                if not isinstance(content, list):
                    continue
                ts = 0
                raw_ts = entry.get("timestamp")
                if isinstance(raw_ts, str):
                    try:
                        ts = int(
                            _dt.datetime.fromisoformat(raw_ts.replace("Z", "+00:00")).timestamp()
                        )
                    except ValueError:
                        ts = 0
                for item in content:
                    if (
                        isinstance(item, dict)
                        and item.get("type") == "tool_use"
                        and item.get("name") in _EDIT_TOOLS
                    ):
                        fp = (item.get("input") or {}).get("file_path")
                        if not fp:
                            continue
                        try:
                            rel = Path(fp).resolve().relative_to(root)
                        except (ValueError, OSError):
                            continue  # outside the repo → not repo work
                        key = str(rel)
                        files[key] = max(files.get(key, 0), ts)
    except Exception:
        return {}
    return files


def _last_commit_ts(root: Path, rel: str) -> int:
    """Unix ts of the last commit touching ``rel`` (0 = never committed)."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", rel],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()
        return int(out) if out.isdigit() else 0
    except Exception:
        return 0


def _dirty_paths(root: Path) -> set[str]:
    """Root-relative paths with uncommitted changes (staged or not), rename-aware."""
    out = subprocess.run(
        ["git", "-c", "core.quotePath=false", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout
    paths: set[str] = set()
    for line in out.splitlines():
        body = line[3:]
        if " -> " in body:
            body = body.split(" -> ", 1)[1]
        paths.add(body.strip().strip('"'))
    return paths


def _baseline_path(sid: str) -> Path:
    return Path(tempfile.gettempdir()) / f"fabrik-gate-baseline-{sid}.json"


def _counter_path(sid: str) -> Path:
    return Path(tempfile.gettempdir()) / f"fabrik-gate-stop-{sid}.attempts"


def _read_counters(counter: Path) -> tuple[int, int, int]:
    """(gate_attempts, commit_attempts, stall_attempts) — tolerates older formats."""
    try:
        raw = counter.read_text().strip()
        parts = raw.split(",")
        vals = [int(p) for p in parts[:3]]
        while len(vals) < 3:
            vals.append(0)
        return vals[0], vals[1], vals[2]
    except Exception:
        return 0, 0, 0


def decide_stall(stalled: bool, attempts: int, cap: int = CAP) -> tuple[str, int]:
    """Pure promise-guard decision. Returns (action, attempts').

    action ∈ {"allow", "block_stall", "allow_warn_stall"} — same anti-trap shape
    as the other causes: counter resets when the cause resolves, warn-through at
    the cap so a misfire can never trap the session.
    """
    if not stalled:
        return "allow", 0
    attempts += 1
    if attempts > cap:
        return "allow_warn_stall", 0
    return "block_stall", attempts


# Narrate-instead-of-act stall (live class, 2 incidents 2026-08-07): the final
# message PROMISES an action it never dispatched, or ASKS permission an active
# plan/review contract already grants. Precision over recall throughout —
# indeterminate parses fail open, human-gate wording is exempt, a kept promise
# (a dispatch in the same final turn) is exempt.
# Two-stage promise match (precision-first; review finding: bare verbs blocked
# read-only turns like "Let me run through the options"): a first-person future
# verb must be followed, within 60 chars, by an ACTION OBJECT — a slash command,
# a work artifact, or a direct object pronoun. "run through" (reviewing idiom)
# and "start by" (conversational) are excluded at the verb.
_PROMISE_VERB_RE = re.compile(
    r"\b(?:I(?:'|’)?ll|I will|let me)\s+(?:now\s+)?"
    r"(?:run(?!\s+through)|start(?!\s+by)|dispatch|launch|kick\s+off"
    r"|keep\s+(?:working|going|chaining)|work\s+through)\b"
    r"|\b(?:starting|running|dispatching)\s+(?:it|that|this|the\s+[\w\- ]{1,40}?)\s+now\b",
    re.I,
)
_ACTION_OBJECT_RE = re.compile(
    r"/[a-z][\w-]+|\bit\b|\bthem\b|\bpass(?:es)?\b|\bround\b|\bsuite\b|\bgate\b"
    r"|\breviews?\b|\btests?\b|\bpytest\b|\bplans?\b|\btickets?\b|\bphases?\b"
    r"|\bfinders?\b|\bsweep\b|\bfix(?:es|ups?)?\b|\bbatch\b|\bcommand\b|\bscript\b"
    r"|\bsubagents?\b|\bcoders?\b|\bworkflow\b|\bnow\b",
    re.I,
)
_PERMISSION_RE = re.compile(
    r"\b(?:want me to|shall I|should I(?!\s+have)|would you like me to|do you want me to)\b"
    r"[^?\n]{0,120}\?",
    re.I,
)
# Legitimate stops: named human gates, BLOCKED escalations, operator-owned steps.
_GATE_EXEMPT_RE = re.compile(
    r"\bBLOCKED:|\bgate\s*2\b|\boperator decision\b|\bapproval\b|\bhuman gate\b"
    r"|\byours to run\b|\bawait\w*\s+(?:your|the operator)\b|\boperator[- ]gated\b",
    re.I,
)
# Tool names whose use in the final turn means a promise was KEPT (work dispatched).
_DISPATCH_TOOLS = frozenset({"Task", "Agent", "Skill", "Workflow", "SlashCommand"})


def _is_dispatch(tool: dict) -> bool:
    if tool["name"] in _DISPATCH_TOOLS:
        return True
    if tool["name"] == "Bash":
        if tool["input"].get("run_in_background"):
            return True
        # `rund -- <cmd>` is CLAUDE.md's sanctioned foreground-wrapper that
        # backgrounds internally — a kept promise (review finding).
        cmd = str(tool["input"].get("command") or "")
        if re.match(r"\s*rund\b", cmd):
            return True
    return False


# Bounded transcript read: the final TURN lives in the last slice of the file; a
# full read_text() on a multi-hundred-MB transcript cost 2.5+ GB RSS per Stop
# (measured live, review finding). 2 MB >> any single turn's tail.
_TAIL_READ_BYTES = 2 * 1024 * 1024


def _final_turn(transcript_path: str) -> tuple[str, list[dict]] | None:
    """(final assistant text, tool_use list of the final turn) or None on any gap.

    Text comes ONLY from the LAST assistant entry (an empty final message stays
    empty — never inherit an older message's promise; review finding). Tools are
    collected across the whole final turn, back to the last REAL user message.
    """
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - _TAIL_READ_BYTES))
            raw = f.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    lines = raw.splitlines()
    if size > _TAIL_READ_BYTES and lines:
        lines = lines[1:]  # first line of a mid-file slice is almost surely partial
    text = ""
    seen_assistant_entry = False
    tools: list[dict] = []
    for line in reversed(lines):
        if '"type"' not in line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        etype = entry.get("type")
        content = (entry.get("message") or {}).get("content")
        if etype == "user":
            # tool_result blocks also arrive as type=user — only a REAL user
            # message (text content) ends the turn walk.
            if isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "text" for b in content
            ):
                break
            continue
        if etype != "assistant" or not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                tools.append({"name": block.get("name", ""), "input": block.get("input") or {}})
            elif block.get("type") == "text" and not seen_assistant_entry and not text:
                text = str(block.get("text") or "")
        seen_assistant_entry = True  # only the LAST assistant entry may supply text
    return text, tools


def _midrun_marker(root: Path, authored: set[str]) -> bool:
    """A SESSION-OWNED mid-run signal: an active plan lock this session edited, or a
    session-authored review doc with UNCHECKED rows. Session-scoped deliberately —
    an unrelated sibling session's active lock must not turn another session's
    legitimate follow-up offer into a stall."""
    for rel in authored:
        p = root / rel
        try:
            if ".fabrik/plan-locks/" in rel and p.is_file():
                # Parse, don't substring-match: compact JSON must still arm it, and
                # a history entry recording a PAST active status must not (review
                # finding). Unparseable lock → not armed (fail toward allowing).
                try:
                    if json.loads(p.read_text(encoding="utf-8", errors="replace")).get("status") == "active":
                        return True
                except Exception:
                    pass
            elif "docs/development/reviews/" in rel and p.is_file():
                # Live checklist ROW form only — a closed review's prose mention of
                # the word ("rows return to UNCHECKED") must not keep the marker on.
                if "| UNCHECKED" in p.read_text(encoding="utf-8", errors="replace"):
                    return True
        except OSError:
            pass
    return False


def _detect_stall(transcript_path: str, root: Path, authored: set[str]) -> tuple[str, str] | None:
    """Return ("promise"|"permission", snippet) when the final message is a stall, else None."""
    try:
        turn = _final_turn(transcript_path)
        if not turn:
            return None
        text, tools = turn
        if not text:
            return None
        tail = text[-600:]
        # Exemptions scan the FULL message: a long BLOCKED escalation's header must
        # not be split away from its own detail by the tail cut (review finding).
        if _GATE_EXEMPT_RE.search(text):
            return None

        def _quoted(match: re.Match[str]) -> bool:
            """A match directly preceded by a quote char is a QUOTATION (discussing
            the phrase, not making it) — live FP: the guard's author quoting
            'I'll run it' as an example. Conservative: only the immediately
            preceding non-space character is inspected."""
            before = tail[: match.start()].rstrip()
            return bool(before) and before[-1] in "\"'`“‘«"

        # First UNQUOTED verb match with an action object in reach — a quoted
        # example must not MASK a later genuine promise (review finding).
        for m in _PROMISE_VERB_RE.finditer(tail):
            if _quoted(m):
                continue
            if not _ACTION_OBJECT_RE.search(tail[m.end() : m.end() + 60]):
                continue  # conversational verb with no work object — not a promise
            if not any(_is_dispatch(t) for t in tools):
                return "promise", m.group(0)
            break  # promise exists but was KEPT (work dispatched this turn)
        for m in _PERMISSION_RE.finditer(tail):
            if _quoted(m):
                continue
            if _midrun_marker(root, authored):
                return "permission", m.group(0)
            break
        return None
    except Exception as e:
        # Fail open — but never SILENTLY (review finding: a MemoryError-disabled
        # guard was indistinguishable from "no stall").
        sys.stderr.write(f"[promise-guard] detection error, failing open: {e}\n")
        return None


def main(argv: list[str]) -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        root = Path(data.get("cwd") or os.getcwd()).resolve()
        sid = str(data.get("session_id") or "nosession")

        if not (root / "scripts" / "final_gate.py").exists():
            return 0  # not a fabrik-style project → nothing to enforce

        # SessionStart: record the inherited failing set, then always allow.
        if "--baseline" in argv:
            _passed, failing, _ftext = _run_gate(root)
            try:
                _baseline_path(sid).write_text(json.dumps(sorted(failing)))
            except Exception:
                pass
            return 0

        # Promise-guard input (independent of tree state): the narrate-instead-of-act
        # stall fires with a CLEAN tree just as often (a stalling agent has usually
        # committed everything and then narrates instead of dispatching).
        transcript_p = str(data.get("transcript_path") or "")
        authored_map: dict[str, int] = {}
        if transcript_p:
            try:
                authored_map = _session_files(transcript_p, root)
            except Exception:
                authored_map = {}
        stall = _detect_stall(transcript_p, root, set(authored_map)) if transcript_p else None

        def _stall_gate() -> int:
            """Run the promise-guard counter flow. Returns the exit code."""
            counter = _counter_path(sid)
            g, c, s_att = _read_counters(counter)
            s_action, s_att = decide_stall(bool(stall), s_att)
            if s_action == "allow":
                if g == 0 and c == 0:
                    counter.unlink(missing_ok=True)
                else:
                    counter.write_text(f"{g},{c},0")
                return 0
            if s_action == "allow_warn_stall":
                counter.write_text(f"{g},{c},0")
                sys.stderr.write(
                    f"Final message still ends in a stall after {CAP} blocked stops — "
                    "stopping anyway.\n"
                )
                return 0
            counter.write_text(f"{g},{c},{s_att}")
            kind, snippet = stall  # type: ignore[misc]
            what = (
                f'promises an action ("{snippet}") that was never dispatched'
                if kind == "promise"
                else f'asks permission ("{snippet}") that the active plan/review contract already grants'
            )
            reason = (
                f"STALL DETECTED (attempt {s_att}/{CAP}). Your final message {what}. "
                "Do the work NOW — dispatch it or run it in this same turn — instead of "
                "narrating or asking (CLAUDE.md: run every owed pass unprompted; the "
                "checkpoint-stall is a named live defect). Legitimate stops must name "
                "their human gate explicitly (design approval, Gate 2, operator "
                "decision, or a formatted BLOCKED: escalation)."
            )
            sys.stdout.write(json.dumps({"decision": "block", "reason": reason}) + "\n")
            return 0

        # Stop: gate/commit causes only apply when there's actual uncommitted work;
        # the promise-guard applies regardless.
        if not _git_dirty(root):
            return _stall_gate()

        baseline_file = _baseline_path(sid)
        if not baseline_file.exists():
            # No baseline (SessionStart didn't run / older session) → we can't tell
            # inherited debt from new breakage, so fail-open rather than false-block —
            # but the promise-guard needs no baseline.
            return _stall_gate()
        try:
            baseline = set(json.loads(baseline_file.read_text()))
        except Exception:
            # Corrupt baseline → gate/commit causes can't run, but the promise-guard
            # must not be disabled for the rest of the session (review finding).
            return _stall_gate()

        _passed, failing, gate_outputs = _run_gate(root)
        new_failures = failing - baseline

        # Session-authored files still uncommitted? (CLAUDE.md § EXIT: an
        # uncommitted task is an unfinished task.) Fail-open on any gap.
        own_uncommitted: set[str] = set()
        # Reuse the stall path's parse — _session_files costs ~1s on a large
        # transcript; three passes per Stop was a measured review finding.
        authored: dict[str, int] = authored_map
        transcript = str(data.get("transcript_path") or "")
        if transcript:
            dirty = _dirty_paths(root)
            for rel, edit_ts in authored.items():
                if rel not in dirty:
                    continue
                # The session's last edit already COMMITTED → today's dirt on the
                # same file belongs to someone else (pipeline/sibling), not this
                # session. Only an edit NEWER than the file's last commit counts.
                if edit_ts and _last_commit_ts(root, rel) >= edit_ts:
                    continue
                own_uncommitted.add(rel)

        # Attribute NEW gate failures by CITED PATH, not just check name: on shared
        # master a sibling's staged/dirty files flip a check red mid-session, and
        # check-name comparison alone pins it on this session — which then CANNOT fix
        # it without violating the shared-tree contract (never commit/document/revert
        # a sibling's WIP). Attribution scopes to the NEW failures' own outputs only,
        # compares normalized path tokens (never substrings), ignores the routine
        # governance files every session writes, and treats a path-less output as
        # INDETERMINATE (keep blocking up to the cap) rather than waving it through.
        # Runs only when we actually know the session's files (transcript present).
        if new_failures and authored:
            session_floor = 0.0
            try:
                session_floor = baseline_file.stat().st_mtime
            except OSError:
                pass
            new_outputs = [gate_outputs.get(n, "") for n in new_failures]
            verdict = _failure_cites_session(new_outputs, authored, session_floor)
            if verdict is False:
                sys.stderr.write(
                    "final_gate has NEW failing check(s) "
                    f"({', '.join(sorted(new_failures))}) whose cited paths include no "
                    "file this session authored — shared-tree cause (a sibling's "
                    "uncommitted work); not blocking this session on it.\n"
                )
                new_failures = set()

        counter = _counter_path(sid)
        gate_attempts, commit_attempts, stall_attempts = _read_counters(counter)

        action, gate_attempts, commit_attempts = decide(
            True,
            bool(new_failures),
            gate_attempts,
            own_uncommitted=bool(own_uncommitted),
            commit_attempts=commit_attempts,
        )

        if action in ("allow", "allow_warn_gate", "allow_warn_commit"):
            if action == "allow_warn_gate":
                sys.stderr.write(
                    f"final_gate still RED after {CAP} attempts — stopping anyway. "
                    "Run: python scripts/final_gate.py --lean --json\n"
                )
            elif action == "allow_warn_commit":
                sys.stderr.write(
                    f"Session-authored files STILL UNCOMMITTED after {CAP} blocked stops — "
                    "stopping anyway. Commit your own work: git commit -- <your files> "
                    "(pathspecs + Agent Provenance Trailers).\n"
                )
            # gate/commit causes resolved (or capped) → reset their counters, then
            # the promise-guard still has the last word on THIS stop.
            counter.write_text(f"0,0,{stall_attempts}")
            return _stall_gate()

        # Reset-when-cause-false applies to the stall slot here too: a gate/commit
        # block must not STRAND a stale stall count that later waves a brand-new
        # stall streak through on its first stop (review finding — the same
        # regression class decide()'s own docstring documents, reintroduced).
        counter.write_text(f"{gate_attempts},{commit_attempts},{stall_attempts if stall else 0}")
        if action == "block_commit":
            listed = ", ".join(sorted(own_uncommitted)[:8])
            more = len(own_uncommitted) - 8
            gate_state = (
                "The gate is green"
                if _passed
                else "No NEW gate failures (inherited debt remains)"
            )
            reason = (
                f"DEFINITION OF DONE NOT MET (attempt {commit_attempts}/{CAP}). {gate_state} "
                "but files THIS session authored are still uncommitted — an "
                "uncommitted task is an UNFINISHED task (CLAUDE.md § EXIT): "
                f"{listed}{f' (+{more} more)' if more > 0 else ''}. Commit YOUR OWN work "
                "now with explicit pathspecs + Agent Provenance Trailers "
                "(git commit -- <your files>); never bundle files you didn't author. "
                "Push stays operator-authorized."
            )
            sys.stdout.write(json.dumps({"decision": "block", "reason": reason}) + "\n")
            return 0
        reason = (
            f"DEFINITION OF DONE NOT MET (attempt {gate_attempts}/{CAP}). This session "
            "introduced gate failures that were not present at session start — the task "
            'is not complete until `final_gate.py --lean` shows "status":"success". '
            f"New failing checks: {', '.join(sorted(new_failures))}. "
            "Fix them, then finish. Run: python scripts/final_gate.py --lean --json"
        )
        # stdout is the hook's channel to Claude Code (not logging) — write directly
        # so the print/console.log ban doesn't false-positive on a required emit.
        sys.stdout.write(json.dumps({"decision": "block", "reason": reason}) + "\n")
        return 0
    except Exception as e:  # fail-open — never trap the session on a hook bug
        sys.stderr.write(f"[final_gate_stop hook] error, allowing stop: {e}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
