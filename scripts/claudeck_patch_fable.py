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
