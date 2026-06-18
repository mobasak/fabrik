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


def decide(git_dirty: bool, has_new_failures: bool, attempts: int, cap: int = CAP) -> tuple[str, int]:
    """Pure decision logic (unit-tested). Returns (action, new_attempts).

    action ∈ {"allow", "block", "allow_warn"}. Blocks only when the worktree is
    dirty AND the session introduced new gate failures (not inherited debt).
    """
    if not git_dirty:
        return "allow", 0  # nothing changed → nothing to gate
    if not has_new_failures:
        return "allow", 0  # green, or only pre-existing/baseline failures remain
    attempts += 1
    if attempts > cap:
        return "allow_warn", 0  # don't trap the session; stop with a loud warning
    return "block", attempts


def _git_dirty(root: Path) -> bool:
    out = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout
    return bool(out.strip())


def _run_gate(root: Path) -> tuple[bool, set[str]]:
    """Run final_gate --lean --check --json. Returns (passed, failing_check_names).

    Fail-open: a gate that can't run or whose output can't be parsed as a definitive
    failure returns (True, empty) — we never block on an indeterminate result.
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
        return True, set()
    try:
        data = json.loads(proc.stdout)
        if data.get("status") == "failure":
            return False, {f.get("check", "?") for f in data.get("failures", [])}
    except Exception:
        pass
    # Non-zero but not a definitive parsed failure (crash, missing deps, etc.) →
    # fail-open: don't block on a gate we couldn't actually evaluate.
    return True, set()


def _baseline_path(sid: str) -> Path:
    return Path(tempfile.gettempdir()) / f"fabrik-gate-baseline-{sid}.json"


def _counter_path(sid: str) -> Path:
    return Path(tempfile.gettempdir()) / f"fabrik-gate-stop-{sid}.attempts"


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
            _passed, failing = _run_gate(root)
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

        _passed, failing = _run_gate(root)
        new_failures = failing - baseline

        counter = _counter_path(sid)
        try:
            attempts = int(counter.read_text())
        except Exception:
            attempts = 0

        action, new_attempts = decide(True, bool(new_failures), attempts)

        if action in ("allow", "allow_warn"):
            try:
                counter.unlink()
            except FileNotFoundError:
                pass
            if action == "allow_warn":
                sys.stderr.write(
                    f"final_gate still RED after {CAP} attempts — stopping anyway. "
                    "Run: python scripts/final_gate.py --lean --json\n"
                )
            return 0

        counter.write_text(str(new_attempts))
        reason = (
            f"DEFINITION OF DONE NOT MET (attempt {new_attempts}/{CAP}). This session "
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
