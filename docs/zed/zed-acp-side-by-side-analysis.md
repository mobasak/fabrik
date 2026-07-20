# Zed — Multiple ACP threads visible side-by-side (research + patch plan)

_Saved 2026-07-16. Personal research note. Not a fabrik artifact._

---

# Zed Migration Status — 2026-07-16

**Goal:** move primary development to Zed (Claude via ACP) on WSL; keep VS Code only for Traycer.
**Overall: ~90% — functionally ready for an agent-orchestration workflow now.** The only
things left are a few one-click UI steps and Traycer (which stays in VS Code).

Zed is on **Windows**, connected to **WSL Ubuntu** via Zed remoting. Projects: `/opt/fabrik`,
`/opt/tojlo-mail`. Config file: `AppData/Roaming/Zed/settings.json` (timestamped backups beside it).

### ✅ Done — configured & verified
| Area | State |
|---|---|
| Claude Code agent | `claude-acp` (ACP registry, `opus[1m]`) |
| Kilo agent | `kilo` (custom ACP: `bash -c` sources nvm + injects `OPENROUTER_API_KEY` from `/opt/fabrik/.env`; the registry "Add Agent" button is a no-op, so wired by hand) |
| OpenRouter models | `openrouter-curated` (`openai_compatible`) — **28 curated models**, real context sizes from OR's live API; a true whitelist (native provider can't filter — merges the full catalog) |
| Workspace parity | VSCode keymap, VSCode Modern Dark theme, minimap off, terminal copy-on-select + 20k scrollback + `.venv` auto-detect, WSL projects |
| Python (optional) | `ruff` + `basedpyright` referenced; `format_on_save` OFF (no surprise shared-repo reformat) |
| Extension gate | `scripts/check_zed_extensions.py (moved from docs/zed/ 2026-07-20)` — derives required extensions from `settings.json`, checks Zed's `index.json`; `--json`, exit 0/1 |

### ⏳ Pending — your UI actions (config is ready, inert until done)
1. **OpenRouter key** → `agent: open settings` → LLM Providers → **openrouter-curated** → paste `sk-or-v1-…`.
2. **Clear the native OpenRouter key** → else its 340-model catalog shows alongside your 28.
3. **Kilo first launch** → npx downloads the CLI; may prompt for auth.
4. **Ruff + Basedpyright extensions** (`Ctrl+Shift+X`) — **OPTIONAL** for you (agents write the code); the extension gate FAILS until installed or the config is switched to built-in `pyright`. Zed has **no CLI install** ([#58417](https://github.com/zed-industries/zed/discussions/58417)).

### ❌ Not ported (no Zed equivalent)
- **Traycer** — planning tool, VS Code/Windsurf only → **the one real gap**; plan there, execute in Zed.
- **Inline AI autocomplete** (Codeium, Kilo `mercury-edit-2`) — not needed since agents write code; Zed's native Edit Prediction (Zeta)/Copilot available if ever wanted.
- Minor: office-doc viewer, markdownlint, GitHub-PR panel (use `gh`/GitHub MCP), claude-manager.

### Workflow-fit note
Because **AI agents write all code**, IDE authoring tooling (autocomplete, linters, formatters)
is optional. The real loop — **drive agents → review git diffs → run in terminal** — is fully
working in Zed today (native git panel, terminal + `.venv`, search, highlighting).

### Known Zed limitation (see research below)
Multiple ACP threads run **concurrently**, but only **one is visible at a time** (switch via
sidebar / `Ctrl+Tab`). Simultaneous side-by-side view is open request
[#54911](https://github.com/zed-industries/zed/discussions/54911) — details + a patch plan below.

---

## The goal (verbatim)

> Multiple ACP (Claude-connected) agent thread views open simultaneously, side by side,
> visible at the same time, inside a single Zed window, on the same project folder —
> not switching between them, not separate windows, not terminal panes.

Setup context: Zed installed on **Windows**, connected to **WSL Ubuntu** via Zed remoting.
Working dir of the fabrik agent that produced this: `/opt/fabrik`.

---

## 1. Current state of Zed (as of mid-July 2026) — grounded

- **Parallel Agents shipped** (v0.233.5, Apr 2026). You can run many ACP threads (Claude,
  Codex, Gemini, any ACP agent) concurrently, each with its own agent/context/history.
- **BUT the Agent Panel is a single dock panel that renders exactly ONE thread at a time.**
  You switch via the Threads Sidebar (`ctrl-alt-j` on Linux/WSL) or cycle with `Ctrl+Tab`.
- Zed deliberately chose the **sidebar model over tabs**. Maintainer: _"we landed on a new
  sidebar design instead and we don't plan to pursue a tab-based implementation."_
- Simultaneous side-by-side visibility = **open, unimplemented** feature request:
  - #54911 "Open parallel agent threads in split panes" — maintainer (macraig) engaged,
    asked for design input, blocked on _"how tabs would interact with the thread sidebar."_
  - #50397 "Allow Agent panel to be docked in the center editor area" — no maintainer reply.

### Confirmed: backgrounded ACP threads KEEP RUNNING when you switch
- Zed docs, verbatim: _"Each thread runs independently, so you can send a prompt, open a
  second thread, and give it a different task while the first continues working."_
- You get a top-right **visual notification** when a background thread finishes, and the same
  "needs your attention" notification when a hidden thread is waiting on a prompt/permission.
- The old bug where a new thread killed the previous one (#35108, Jul 2025) is **CLOSED/fixed**.
- **So concurrent EXECUTION already works today. Only simultaneous VISIBILITY is missing.**

---

## 2. Is Zed open source / modifiable? — yes

- License: **GPL-3.0-or-later**, with **Apache-2.0** for marked components (GPUI framework).
- ~97% **Rust**, on their own **GPUI** GPU-accelerated UI framework.
- Buildable from source (macOS/Linux/Windows), official build docs. Fork/modify freely.
- GPL: modify freely for own use; only if you _distribute_ a modified build must you publish
  the source changes. Solo/personal use = no friction.

---

## 3. The trilemma (the core tension in the ask)

"Patch it" + "keep receiving Zed updates" + "zero maintenance" → **pick two.**
Zed ships weekly and `crates/agent_ui` is one of the highest-churn areas, so any on-top patch
WILL hit rebase conflicts.

| Strategy | Fast? | Maintenance | Gets Zed updates? | Verdict |
|---|---|---|---|---|
| **A. Freeze-fork** — patch once, pin version, disable auto-update, wait for upstream | Fastest (one build) | **Zero** | No (frozen until #54911 ships) | **RECOMMENDED** |
| B. Fork + CI auto-rebase/rebuild each release | Slower setup | "Zero until conflict" — agent_ui churn = periodic manual rebases | Yes | Only if freezing unacceptable |
| C. Upstream the PR to #54911 | Weeks (review) | Zero forever after merge | Yes | Run in PARALLEL with A; it kills the fork |
| D. Zed extension | — | — | — | **IMPOSSIBLE** — WASM extension API = languages/themes/slash-cmds/MCP/debug-adapters only; cannot create panes/UI |

**Key insight:** the feature is an accepted-direction upstream request, not shipped. So the
patch is inherently **temporary** → don't chase upstream. Patch once, freeze, let the fork die
when upstream ships it. Perpetual patching (B) is the trap: maintaining a hot-path fork forever
for a feature Zed will give you free.

---

## 4. What the patch actually is (small; there's a template)

- Runtime already supports N concurrent ACP threads (they keep running in background). This is
  **pure UI plumbing**: wrap the existing thread view in a `workspace::Item` so it opens as a
  **center tab**, which then inherits Zed's native splits (left/right/2×2 grid) for FREE.
- **Template to copy:** `crates/agent_ui/src/agent_diff.rs` — same crate, already
  `impl Item for AgentDiff`, already registered as a center-pane tab. The patch is a sibling
  file: an item wrapper holding the ACP thread view + one action ("open thread in center pane"
  from the Threads Sidebar) + registration.
- Estimate: **~300–500 lines, 1–3 focused days** for someone competent in Rust (GPUI learning
  curve is the bulk), plus build-env setup.
- NOTE: exact current thread-view struct name still needs confirming in-source (GitHub code
  search was flaky on struct names). Look in `crates/agent_ui/src/` for the ACP thread view
  component; `agent_diff.rs` shows the Item pattern to mirror.

---

## 5. WSL/Windows build wrinkle — and a shortcut

The patch is **client-side UI**; your client is Zed-on-Windows. Two routes:

1. **Build the Windows client on Windows** — supported/documented, needs MSVC toolchain;
   first build ~30–60 min. Patched client still works with WSL remoting (remote-server
   protocol untouched).
2. **Shortcut: build the Linux client inside WSL, run via WSLg** — much easier build loop
   (drivable from a Claude session in WSL), and projects are local to it so remoting disappears.
   Trade-off: GPUI under WSLg can be less smooth than native Windows. Test 10 min before
   committing to route 1.

Then set `"auto_update": false` in Zed settings so an update never overwrites the patched build.

---

## 6. Recommended plan (fastest to working, then zero-touch)

1. **Build vanilla first** (retires the toolchain risk) — try WSL/WSLg route first (Claude can
   execute it); fall back to Windows build.
2. **Write the patch** modeled on `agent_diff.rs`: `AcpThreadItem` wrapper + "Open thread in
   center pane" action.
3. **Pin & freeze:** `auto_update: false`; keep the patch as a single `.patch` file in a tiny
   repo for reproducibility.
4. **In parallel, post the patch to #54911 / open a PR** — maintainer asked for design input;
   a working diff is the strongest input. When upstream ships, delete the fork.

**Caveat while frozen:** no Zed security/feature updates until you unfreeze — acceptable for
weeks-to-a-few-months, which is the realistic window given upstream momentum.

---

## Zero-code fallback (if you never want to build)

Run Claude Code CLI as **center-pane terminals** and split them (Cmd-K + arrow, or
`pane: split right/down`) into a 2×2 grid → true simultaneous side-by-side NOW. Trade-off:
it's the terminal TUI, not the ACP conversation UI (lose inline-diff review, native model
picker). This is the only zero-build way to get simultaneous visibility today.

---

## Sources

- https://zed.dev/docs/ai/parallel-agents
- https://zed.dev/docs/ai/agent-panel
- https://zed.dev/docs/ai/external-agents
- https://zed.dev/blog/parallel-agents
- https://zed.dev/blog/terminal-threads
- https://github.com/zed-industries/zed/discussions/54911  (split-pane threads — OPEN)
- https://github.com/zed-industries/zed/discussions/50397  (center-dock agent panel — OPEN)
- https://github.com/zed-industries/zed/discussions/42381  (tabbed threads — shipped as sidebar)
- https://github.com/zed-industries/zed/issues/35108  (parallel-kills-previous bug — CLOSED/fixed)
- https://github.com/zed-industries/zed  (GPL-3.0-or-later, Rust/GPUI)
- Patch template in-source: crates/agent_ui/src/agent_diff.rs  (impl Item for AgentDiff)
