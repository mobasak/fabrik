#!/usr/bin/env python3
"""Align claudeck's model menu + spawn with the operator's real model set (idempotent).

Patches EVERY claudeck install in the npx cache (launches may resolve any of them):
1. MODEL_MAP -> family aliases (opus/sonnet/haiku) that the modern CLI resolves to
   LATEST server-side, + Fable 5 [1m] as an explicit menu entry.
2. Menu labels: Fable 5 / Opus 4.8 / Sonnet 5 / Haiku (latest).
3. SDK wired to the SYSTEM Claude CLI via cli-wrapper.cjs (bundled CLI is ~1.0.x:
   no plugins, no skills, stale tools -> API 400s on adopted sessions).
Run daily via wsl_startup_hook; safe to re-run; survives claudeck/claude updates.
"""
import re, shutil, subprocess, sys
from pathlib import Path

FABLE = "claude-fable-5[1m]"
pkgs = sorted(Path.home().glob(".npm/_npx/*/node_modules/claudeck"))
if not pkgs:
    print("claudeck not found in npx cache"); sys.exit(0)

claude_bin = shutil.which("claude")
wrapper = ""
if claude_bin:
    real = Path(subprocess.check_output(["readlink", "-f", claude_bin], text=True).strip())
    w = real.parent.parent / "cli-wrapper.cjs"
    if w.exists(): wrapper = str(w)

for P in pkgs:
    tag = P.parts[-3]
    # 1+3) server: MODEL_MAP aliases + system CLI
    al = P / "server/agent-loop.js"
    if al.exists():
        t = al.read_text()
        t = re.sub(r'haiku: "[^"]*"', 'haiku: "haiku"', t)
        t = re.sub(r'sonnet: "[^"]*"', 'sonnet: "sonnet"', t)
        t = re.sub(r'opus: "[^"]*"', 'opus: "opus"', t)
        if wrapper:
            if "pathToClaudeCodeExecutable" not in t:
                t = t.replace("  const opts = {", f'  const opts = {{\n    pathToClaudeCodeExecutable: "{wrapper}",', 1)
            else:
                t = re.sub(r'pathToClaudeCodeExecutable: "[^"]*"', f'pathToClaudeCodeExecutable: "{wrapper}"', t)
        al.write_text(t)
    # 2) menu: button labels + select options
    html = P / "public/index.html"
    if html.exists():
        t = html.read_text()
        if FABLE not in t:
            t = t.replace('<option value="haiku">haiku</option>',
                          f'<option value="haiku">haiku</option>\n          <option value="{FABLE}" selected>fable 5</option>', 1)
            t = t.replace('data-target="model-select" data-value="haiku">Haiku</button>',
                          f'data-target="model-select" data-value="haiku">Haiku</button>\n              <button class="header-submenu-item" data-target="model-select" data-value="{FABLE}">Fable 5</button>', 1)
        t = t.replace('data-value="opus">Opus<', 'data-value="opus">Opus 4.8<')
        t = t.replace('data-value="sonnet">Sonnet<', 'data-value="sonnet">Sonnet 5<')
        t = t.replace('data-value="haiku">Haiku<', 'data-value="haiku">Haiku (latest)<')
        html.write_text(t)
    # labels below the input
    meta = P / "public/js/ui/input-meta.js"
    if meta.exists():
        t = meta.read_text()
        if "Fable 5" not in t:
            t = t.replace('haiku: "Haiku",', f'haiku: "Haiku",\n  "{FABLE}": "Fable 5",', 1)
        t = t.replace('opus: "Opus"', 'opus: "Opus 4.8"').replace('sonnet: "Sonnet"', 'sonnet: "Sonnet 5"')
        meta.write_text(t)
    print(f"patched {tag}")
print(f"CLI: {wrapper or 'system claude not found'}")
