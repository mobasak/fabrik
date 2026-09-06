#!/usr/bin/env python3
# AFTER-EDIT: tests/test_install_user_hooks.py | docs/workstation/hooks-index.md | scripts/sysadmin/user_hook_gate.py | scripts/sysadmin/selfwatch_check.py
"""Install / verify the USER-LEVEL hook registrations in every account dir (review 2026-09-06, B10).

The three entries — the self-watch arm check, and the gate that runs the hub's mcp_watch.py and
quota_stop.py where a project does not wire them — were first written by hand into the canonical
`~/.claude/settings.json` and pushed with `claude_rotate.py --sync-shared`. That left no creator,
no verifier and no restorer: a sixth account dir, a DR restore, or a `--sync-shared` from a stale
canonical strips every window of them silently, and `check_hooks_index.py` derives its required
set FROM the file, so it can only see an UNDOCUMENTED entry, never a MISSING one.

    install_user_hooks.py            # idempotent: add what is missing to the canonical + every fleet dir
    install_user_hooks.py --check    # exit 1 naming any file that lacks an entry (a gate row)

Registration timeout is 10 s — above user_hook_gate's inner 8 s, so the harness never kills the
gate before the gate can kill its child (B8). Other keys in each settings.json are untouched.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HUB = "/opt/fabrik"
ENTRIES = {
    "UserPromptSubmit": [
        f"python3 {HUB}/scripts/sysadmin/selfwatch_check.py",
        f"python3 {HUB}/scripts/sysadmin/user_hook_gate.py {HUB}/.claude/hooks/mcp_watch.py",
    ],
    "PreToolUse": [
        f"python3 {HUB}/scripts/sysadmin/user_hook_gate.py {HUB}/.claude/hooks/quota_stop.py",
    ],
}
TIMEOUT_S = 10


def _targets() -> list[Path]:
    home = Path(os.environ.get("HOME") or Path.home())
    out = [home / ".claude" / "settings.json"]
    fleet = home / ".claude-fleet"
    if fleet.is_dir():
        for d in sorted(fleet.iterdir()):
            # every ACCOUNT dir, present settings.json or not — a restorer that skips the
            # missing file cannot restore (review P2-9); `active` is a symlink, never a target
            if (
                d.is_dir()
                and not d.is_symlink()
                and (d / ".claude.json").exists()
                or d.is_dir()
                and not d.is_symlink()
                and (d / "settings.json").exists()
            ):
                out.append(d / "settings.json")
    return out


def _stale(d: dict) -> list[tuple[str, str, str]]:
    """Every (event, canonical command, reason) whose registration is not EXACTLY the canonical
    one: absent, a different path for the same script (a moved checkout kept firing — P2-8), a
    timeout below the gate's inner timeout (the B8 invariant `--check` could not see — P2-7), or
    a PreToolUse entry without a matcher."""
    out = []
    hooks = d.get("hooks")
    hooks = hooks if isinstance(hooks, dict) else {}
    for ev, cmds in ENTRIES.items():
        entries = hooks.get(ev) if isinstance(hooks.get(ev), list) else []
        for cmd in cmds:
            base = cmd.rsplit("/", 1)[-1].split()[0]
            found = None
            for e in entries:
                if not isinstance(e, dict):
                    continue
                for h in e.get("hooks") or []:
                    if isinstance(h, dict) and base in str(h.get("command", "")):
                        found = (e, h)
            if found is None:
                out.append((ev, cmd, "missing"))
                continue
            e, h = found
            if str(h.get("command", "")) != cmd:
                out.append((ev, cmd, f"stale command `{h.get('command', '')}`"))
            elif not isinstance(h.get("timeout"), (int, float)) or h["timeout"] < TIMEOUT_S:
                out.append((ev, cmd, f"timeout {h.get('timeout')!r} < {TIMEOUT_S}"))
            elif ev == "PreToolUse" and not e.get("matcher"):
                out.append((ev, cmd, "no matcher"))
    return out


def _missing(d: dict) -> list[tuple[str, str]]:
    return [(ev, cmd) for ev, cmd, _ in _stale(d)]


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="verify only; exit 1 on any missing entry")
    args = ap.parse_args(argv)
    bad = 0
    for path in _targets():
        try:
            d = json.loads(path.read_text(encoding="utf-8") or "{}") if path.exists() else {}
            if not isinstance(d, dict):
                d = {}
        except (OSError, ValueError):
            print(f"install_user_hooks: cannot read {path}", file=sys.stderr)
            bad += 1
            continue
        stale = _stale(d)
        if not stale:
            continue
        if args.check:
            for ev, cmd, why in stale:
                print(
                    f"{why.upper() if why == 'missing' else 'STALE'} {path}: {ev} → {cmd} ({why})"
                )
            bad += 1
            continue
        hooks = d.get("hooks")
        if not isinstance(hooks, dict):
            hooks = {}  # a list-shaped `hooks` is not a registration (P2-3)
        d["hooks"] = hooks
        for ev, cmd, _why in stale:
            base = cmd.rsplit("/", 1)[-1].split()[0]
            kept = []
            for e in hooks.get(ev) or []:
                # drop every entry carrying this script under any path — a stale registration
                # kept executing (or failing) on every prompt beside the new one (P2-8)
                if isinstance(e, dict) and any(
                    isinstance(h, dict) and base in str(h.get("command", ""))
                    for h in e.get("hooks") or []
                ):
                    continue
                kept.append(e)
            entry = {"hooks": [{"type": "command", "command": cmd, "timeout": TIMEOUT_S}]}
            if ev == "PreToolUse":
                entry["matcher"] = ".*"
            hooks[ev] = [*kept, entry]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
        print(f"installed {len(stale)} entr{'y' if len(stale) == 1 else 'ies'} into {path}")
    if args.check:
        print(
            "user-level hooks: "
            + ("present in every account dir" if not bad else f"{bad} file(s) missing entries")
        )
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(run())
