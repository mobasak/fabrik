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


def _run_gate(root: Path) -> tuple[bool, set[str], str]:
    """Run final_gate --lean --check --json. Returns (passed, failing_check_names, failure_text).

    failure_text is the concatenated output of the failing checks — used by the Stop
    path to attribute a NEW failure to this session's files vs a sibling's shared-tree
    dirt (a failing check that cites none of the session's files is not this session's
    breakage to fix; blocking on it would force a shared-tree contract violation).

    Fail-open: a gate that can't run or whose output can't be parsed as a definitive
    failure returns (True, empty, "") — we never block on an indeterminate result.
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
        return True, set(), ""
    try:
        data = json.loads(proc.stdout)
        if data.get("status") == "failure":
            fails = data.get("failures", [])
            names = {f.get("check", "?") for f in fails}
            text = "\n".join(str(f.get("output", "")) for f in fails)
            return False, names, text
    except Exception:
        pass
    # Non-zero but not a definitive parsed failure (crash, missing deps, etc.) →
    # fail-open: don't block on a gate we couldn't actually evaluate.
    return True, set(), ""


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


def _read_counters(counter: Path) -> tuple[int, int]:
    """(gate_attempts, commit_attempts) — tolerates the old single-int format."""
    try:
        raw = counter.read_text().strip()
        if "," in raw:
            a, b = raw.split(",", 1)
            return int(a), int(b)
        return int(raw), 0
    except Exception:
        return 0, 0


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

        # Stop: only enforce when there's actual uncommitted work.
        if not _git_dirty(root):
            return 0

        baseline_file = _baseline_path(sid)
        if not baseline_file.exists():
            # No baseline (SessionStart didn't run / older session) → we can't tell
            # inherited debt from new breakage, so fail-open rather than false-block.
            return 0
        try:
            baseline = set(json.loads(baseline_file.read_text()))
        except Exception:
            return 0

        _passed, failing, failure_text = _run_gate(root)
        new_failures = failing - baseline

        # Session-authored files still uncommitted? (CLAUDE.md § EXIT: an
        # uncommitted task is an unfinished task.) Fail-open on any gap.
        own_uncommitted: set[str] = set()
        authored: dict[str, float] = {}
        transcript = str(data.get("transcript_path") or "")
        if transcript:
            authored = _session_files(transcript, root)
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

        # Attribute NEW gate failures by FILE, not just check name: on shared master a
        # sibling's staged/dirty files flip a check red mid-session, and check-name
        # comparison alone pins it on this session — which then CANNOT fix it without
        # violating the shared-tree contract (never commit/document/revert a sibling's
        # WIP). If the failing checks' outputs cite NONE of this session's authored
        # files, the breakage is not ours: report to stderr, don't block. Attribution
        # runs only when we actually know the session's files (transcript present).
        if new_failures and authored and failure_text:
            if not any(rel in failure_text for rel in authored):
                sys.stderr.write(
                    "final_gate has NEW failing check(s) "
                    f"({', '.join(sorted(new_failures))}) but none cite a file this "
                    "session authored — shared-tree cause (a sibling's uncommitted "
                    "work); not blocking this session on it.\n"
                )
                new_failures = set()

        counter = _counter_path(sid)
        gate_attempts, commit_attempts = _read_counters(counter)

        action, gate_attempts, commit_attempts = decide(
            True,
            bool(new_failures),
            gate_attempts,
            own_uncommitted=bool(own_uncommitted),
            commit_attempts=commit_attempts,
        )

        if action in ("allow", "allow_warn_gate", "allow_warn_commit"):
            try:
                counter.unlink()
            except FileNotFoundError:
                pass
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
            return 0

        counter.write_text(f"{gate_attempts},{commit_attempts}")
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
