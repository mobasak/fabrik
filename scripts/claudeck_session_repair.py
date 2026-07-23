#!/usr/bin/env python3
"""Repair an adopted Claude Code session for headless resume (idempotent, backed up).

VS-Code-extension sessions may contain tool_use blocks for extension-only tools
(e.g. Monitor); the API validates ALL replayed history tool refs against current
tools and 400s. This neutralizes every tool_use whose name is neither a known
CLI-native tool nor an mcp__/plugin-prefixed one, plus its tool_results, and
strips stored 'API Error' assistant messages so dead errors stop re-rendering.

Usage: claudeck_session_repair.py <session.jsonl> [--dry-run]
"""
import json, shutil, sys, time
from pathlib import Path

NATIVE = {"Task","Bash","Glob","Grep","Read","Edit","Write","MultiEdit","NotebookEdit",
          "WebFetch","WebSearch","TodoWrite","BashOutput","KillShell","SlashCommand",
          "Skill","ExitPlanMode","EnterPlanMode","AskUserQuestion","TodoRead","LS"}

def known(name: str) -> bool:
    return name in NATIVE or name.startswith(("mcp__", "plugin__"))

def repair(path: Path, dry: bool) -> None:
    ids, u, r, e = set(), 0, 0, 0
    names = set()
    out = []
    for line in open(path, errors="replace"):
        try: o = json.loads(line)
        except Exception: out.append(line); continue
        m = o.get("message"); changed = False
        c = m.get("content") if isinstance(m, dict) else None
        if (o.get("type") == "assistant" and isinstance(c, list) and len(c) == 1
                and isinstance(c[0], dict) and c[0].get("type") == "text"
                and str(c[0].get("text","")).startswith("API Error:")):
            e += 1
            if not dry: continue
        if isinstance(c, list):
            for b in c:
                if not isinstance(b, dict): continue
                if b.get("type") == "tool_use":
                    names.add(b.get("name",""))
                    if not known(b.get("name","")):
                        ids.add(b.get("id")); u += 1; changed = True
                        if not dry:
                            n = b.get("name"); b.clear()
                            b.update({"type":"text","text":f"[legacy tool call: {n} - neutralized for headless resume]"})
                elif b.get("type") == "tool_result" and b.get("tool_use_id") in ids:
                    r += 1; changed = True
                    if not dry:
                        b.clear(); b.update({"type":"text","text":"[legacy tool result - neutralized]"})
        out.append(json.dumps(o, ensure_ascii=False) + "\n" if (changed and not dry) else line)
    unknown = sorted(n for n in names if n and not known(n))
    print(f"{path.name[:12]}: unknown tools={unknown} | neutralized {u} calls + {r} results | stripped {e} stored errors" + (" [DRY]" if dry else ""))
    if not dry and (u or r or e):
        shutil.copy2(path, path.with_suffix(f".jsonl.bak-{time.strftime('%H%M%S')}"))
        path.write_text("".join(out))

if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    for a in sys.argv[1:]:
        if a != "--dry-run": repair(Path(a), dry)
