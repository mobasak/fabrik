#!/usr/bin/env python3
"""Add 'Fable 5' to claudeck's hardcoded model menu (idempotent; re-run after updates).

claudeck v1.4.x hardcodes haiku/sonnet/opus in its UI, but server resolveModel()
passes unknown values through verbatim — so a full model id in the menu just works.
Patches (in the live npx cache, located dynamically): index.html submenu button +
hidden <select> option, and input-meta.js label. Safe to run daily via startup hook.
"""

import sys
from pathlib import Path

MODEL_ID = "claude-fable-5[1m]"
pkgs = sorted(
    Path.home().glob(".npm/_npx/*/node_modules/claudeck"), key=lambda p: p.stat().st_mtime
)
if not pkgs:
    print("claudeck package not found in npx cache")
    sys.exit(0)
P = pkgs[-1]

html = P / "public/index.html"
t = html.read_text()
if MODEL_ID not in t:
    t = t.replace(
        '<option value="haiku">haiku</option>',
        f'<option value="haiku">haiku</option>\n          <option value="{MODEL_ID}">fable 5</option>',
        1,
    )
    t = t.replace(
        'data-target="model-select" data-value="haiku">Haiku</button>',
        f'data-target="model-select" data-value="haiku">Haiku</button>\n              <button class="header-submenu-item" data-target="model-select" data-value="{MODEL_ID}">Fable 5</button>',
        1,
    )
    html.write_text(t)
    print("index.html patched")
else:
    print("index.html already patched")

al = P / "server/agent-loop.js"; t2 = al.read_text()
if "claude-opus-4-6" in t2:
    al.write_text(t2.replace("claude-opus-4-6", "claude-opus-4-8"))
    print("agent-loop: stale opus id fixed")

meta = P / "public/js/ui/input-meta.js"
t = meta.read_text()
if "Fable 5" not in t:
    t = t.replace('haiku: "Haiku",', f'haiku: "Haiku",\n  "{MODEL_ID}": "Fable 5",', 1)
    meta.write_text(t)
    print("input-meta.js patched")
else:
    print("input-meta.js already patched")

# Wire claudeck's SDK to the SYSTEM Claude Code CLI (bundled one is ~1.0.x:
# no plugins, no skills, missing native tools like Monitor -> API 400 on resume).
import shutil, subprocess
al = P / "server/agent-loop.js"; t3 = al.read_text()
claude_bin = shutil.which("claude")
if claude_bin:
    real = Path(subprocess.check_output(["readlink", "-f", claude_bin], text=True).strip())
    wrapper = real.parent.parent / "cli-wrapper.cjs"
    if wrapper.exists():
        w = str(wrapper)
        if "pathToClaudeCodeExecutable" not in t3:
            t3 = t3.replace("  const opts = {", f'  const opts = {{\n    pathToClaudeCodeExecutable: "{w}",', 1)
            al.write_text(t3); print(f"agent-loop: system CLI wired ({w})")
        elif w not in t3:
            import re
            t3 = re.sub(r'pathToClaudeCodeExecutable: "[^"]*"', f'pathToClaudeCodeExecutable: "{w}"', t3)
            al.write_text(t3); print(f"agent-loop: system CLI path refreshed ({w})")
