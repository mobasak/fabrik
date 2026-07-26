#!/usr/bin/env bash
# Double-click diagnostic export of the Claude Code quota/account state (run via the desktop .bat
# through WSL). Dumps EVERYTHING reachable non-interactively so the operator's fabrik session can
# evaluate what quota data actually exists (and confirm the live weekly % is not script-readable).
# Writes a timestamped JSON to $1 (the Windows desktop) and echoes the path. Read-only; no secrets.
set -u
OUT_DIR="${1:-$HOME}"
TS="$(date -u +%Y%m%d-%H%M%S)"
OUT="$OUT_DIR/claude-quota-snapshot-$TS.json"
CM="$HOME/.claude/.claude-manager"

# jq-free: build the JSON in python from the raw files (fail-soft per field — a missing file → null).
python3 - "$OUT" <<'PY'
import json, sys, os, datetime, subprocess
from pathlib import Path
home = Path.home(); cm = home / ".claude" / ".claude-manager"

def _load(p):
    try: return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception as e: return {"_unreadable": str(e)}

def _active_org():
    try: return (json.loads((home/".claude.json").read_text(encoding="utf-8")) or {}).get("organizationUuid")
    except Exception: return None

def _accounts():
    try: return sorted(p.name for p in (home/".claude"/"manager-accounts").iterdir() if p.is_dir())
    except Exception: return []

def _usage_week():
    """Last-7-calendar-day token totals per model + grand total (global — NOT per-account)."""
    try:
        d = json.loads((cm/"usage-history.json").read_text(encoding="utf-8")); days = d.get("days") or {}
        cut = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        today = datetime.date.today().isoformat(); per = {}; grand = 0
        for k, day in days.items():
            if not (cut <= k <= today): continue
            for m, v in (day.get("byModel") or {}).items():
                t = sum(int(v.get(x,0) or 0) for x in ("input","output","cacheRead","cacheCreation"))
                per[m] = per.get(m,0)+t; grand += t
        return {"window_start": cut, "per_model_tokens": per, "total_tokens": grand}
    except Exception as e:
        return {"_error": str(e)}

def _claude_version():
    try: return subprocess.run([os.path.expanduser("~/.local/bin/claude"),"--version"],
                               capture_output=True,text=True,timeout=15).stdout.strip()
    except Exception as e: return f"<error: {e}>"

snap = {
    "captured_at_utc": datetime.datetime.utcnow().isoformat(timespec="seconds")+"Z",
    "claude_version": _claude_version(),
    "active_org_uuid": _active_org(),
    "manager_accounts": _accounts(),
    "statusline": _load(cm/"statusline.json"),
    "statusline_inner": _load(cm/"statusline-inner.json"),
    "active_sessions": _load(cm/"active-sessions.json"),
    "usage_last_7d": _usage_week(),
    "NOTE": ("Live weekly quota % is NOT here by design: claude has no non-interactive status cmd, "
             "statusline.rateLimits is null unless Claude Code emits it during an interactive turn, "
             "and /status is interactive-only. The reliable machine source is the quota-hit ERROR "
             "(weekly/opus/N-hour + reset) — captured via the rotation-event log, not this export."),
}
Path(sys.argv[1]).write_text(json.dumps(snap, indent=2, default=str)+"\n", encoding="utf-8")
print(sys.argv[1])
PY
echo "Saved: $OUT"
