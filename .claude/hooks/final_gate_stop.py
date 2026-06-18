#!/usr/bin/env python3
"""Claude Code **Stop** hook — the "definition of done" for direct agent sessions.

Fires when the agent finishes a turn. If the worktree has uncommitted changes and
``final_gate.py --lean`` is NOT green, it BLOCKS the stop and feeds the failures
back, so the agent cannot claim "done" until the gate passes. The agent never
commits — this is the in-session checkpoint that replaces "the agent says so".

Safety:
- **Fail-open**: any internal error → allow the stop (a hook bug must never trap
  the session).
- **Loop cap**: after CAP consecutive blocked stops it allows the stop with a loud
  warning (Claude Code's docs expose no ``stop_hook_active`` flag, so we cap here).
- **Scoped**: no uncommitted changes → no gate (conversational turns pass instantly).

Contract (verified against https://code.claude.com/docs/en/hooks, 2026-06):
- stdin JSON: ``session_id``, ``cwd``, ``transcript_path``, ``hook_event_name``,
  ``stop_reason``, ``messages``.
- block: print ``{"decision":"block","reason":...}`` on stdout, exit 0.
- allow: exit 0 with no ``decision``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

CAP = 3  # consecutive blocked stops before letting it stop anyway (anti-trap)


def decide(git_dirty: bool, gate_passed: bool, attempts: int, cap: int = CAP) -> tuple[str, int]:
    """Pure decision logic (unit-tested). Returns (action, new_attempts).

    action ∈ {"allow", "block", "allow_warn"}.
    """
    if not git_dirty:
        return "allow", 0  # nothing changed → nothing to gate
    if gate_passed:
        return "allow", 0  # green → "done" is legitimate; reset the counter
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


def _run_gate(root: Path) -> tuple[bool, str]:
    """Run final_gate --lean --check --json; return (passed, failure_summary)."""
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
        return True, ""
    summary = ""
    try:
        data = json.loads(proc.stdout)
        fails = data.get("failures", [])
        summary = "; ".join(f.get("check", "?") for f in fails) or proc.stdout[-400:]
    except Exception:
        summary = (proc.stdout or proc.stderr or "")[-400:]
    return False, summary.strip()


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        root = Path(data.get("cwd") or os.getcwd()).resolve()
        sid = str(data.get("session_id") or "nosession")

        # Only enforce in a fabrik-style project with a gate, and only when there's
        # actual uncommitted work to judge.
        if not (root / "scripts" / "final_gate.py").exists():
            return 0
        if not _git_dirty(root):
            return 0

        counter = Path(tempfile.gettempdir()) / f"fabrik-gate-stop-{sid}.attempts"
        try:
            attempts = int(counter.read_text())
        except Exception:
            attempts = 0

        passed, summary = _run_gate(root)
        action, new_attempts = decide(True, passed, attempts)

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
            f"DEFINITION OF DONE NOT MET (attempt {new_attempts}/{CAP}). "
            'final_gate.py --lean is RED — the task is not complete until it shows '
            '"status":"success". '
            f"Failing checks: {summary or 'see gate output'}. "
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
    sys.exit(main())
