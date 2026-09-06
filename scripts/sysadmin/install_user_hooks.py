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
            if d.is_dir() and not d.is_symlink() and (d / "settings.json").exists():
                out.append(d / "settings.json")
    return out


def _missing(d: dict) -> list[tuple[str, str]]:
    miss = []
    for ev, cmds in ENTRIES.items():
        have = [
            h.get("command", "")
            for e in (d.get("hooks") or {}).get(ev) or []
            for h in (e.get("hooks") or [])
        ]
        for cmd in cmds:
            if not any(cmd in h for h in have):
                miss.append((ev, cmd))
    return miss


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="verify only; exit 1 on any missing entry")
    args = ap.parse_args(argv)
    bad = 0
    for path in _targets():
        try:
            d = json.loads(path.read_text(encoding="utf-8") or "{}")
            if not isinstance(d, dict):
                d = {}
        except (OSError, ValueError):
            print(f"install_user_hooks: cannot read {path}", file=sys.stderr)
            bad += 1
            continue
        miss = _missing(d)
        if not miss:
            continue
        if args.check:
            for ev, cmd in miss:
                print(f"MISSING {path}: {ev} → {cmd}")
            bad += 1
            continue
        hooks = d.setdefault("hooks", {})
        for ev, cmd in miss:
            entry = {"hooks": [{"type": "command", "command": cmd, "timeout": TIMEOUT_S}]}
            if ev == "PreToolUse":
                entry["matcher"] = ".*"
            hooks.setdefault(ev, []).append(entry)
        path.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
        print(f"installed {len(miss)} entr{'y' if len(miss) == 1 else 'ies'} into {path}")
    if args.check:
        print(
            "user-level hooks: "
            + ("present in every account dir" if not bad else f"{bad} file(s) missing entries")
        )
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(run())
