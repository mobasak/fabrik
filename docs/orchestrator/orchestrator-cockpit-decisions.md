# Orchestrator Cockpit — Locked Decisions & Workflow Model

**Status:** ACTIVE EVALUATION — currently **spiking the agetor fork** (Phase 0 WSLg render + Claude-Code wiring passed 2026-07-18) to see if it earns the pick. **Traycer Desktop remains a live candidate / fallback — NOT ruled out;** the choice between the two is still open. · **Date:** 2026-07-16 (amended 2026-07-18) · **Owner:** ob@ocoron.com
**Companion to:** `orchestrator-cockpit-requirements.md` (the 17 requirements). This file records the
**decisions** made while brainstorming the cockpit — persisted so they survive context compaction.

---

## Locked decisions

- **D1 — Fork target = agetor** (`alamops/agetor`, MIT, Electrobun, v0.0.17). Strongest lightweight *native* fork base; deep source read = genuinely high-quality (5k-LOC tmux driver, deep tests, full git-host integrations). **REINSTATED 2026-07-17** after the Traycer Desktop detour (see amendment below) — **pending the WSLg runtime spike**, now with the HiDPI display blocker already cleared (`.wslgconfig` fix confirmed working).
- **D2 — Native desktop app, not browser-served.** Lightweight (Electrobun/Tauri class). **Not Electron.** (Rejected Conductor for being browser-served; rejected Daintree/Emdash/AO for Electron weight.)
- **D3 — Auth:** Claude Code via **OAuth / subscription, per-user local login**. **No `ANTHROPIC_API_KEY`, no Agent-SDK metered credit.** (agetor already drives `claude` interactive = subscription.)
- **D4 — No direct OpenRouter in the cockpit.** OpenRouter is reached **only through `fabrik-lib/subagents`**, dispatched by the Claude orchestrator (pool = programmatic breadth, never an interactive tab). Cockpit only runs Claude Code.
- **D5 — Two-level nested workflow.** The core model:
  - **Project level = `mega-epic-breakdown`** → produces **Vision · Decisions · Infra-Decisions · External-Tools (fabrik-lib verdict) · Specs · Epics**. **NO tickets.**
  - **Epic level = `epic-to-ticket-workflow`** (run when you drill INTO an epic) → produces **Decisions-Lock · Core-Flows · Tech-Plan · Deploy-Plan · Tickets · Executions · Reviews**.
  - **Tickets are epic-scoped executable leaves** — the units AI agents run. **Executions** = agent runs per ticket.
  - **Hierarchy: Project ▸ Epic ▸ Ticket ▸ Execution.**
- **D6 — `00` & `02` are interactive chat artifacts** (Vision Summary; compact epic proposal). Approved **in spirit** (interactive, lean, confirm-before-expand). **Improvement locked: persist on confirm** — do NOT leave load-bearing artifacts chat-only; the headless driver, cold re-runs, and the GUI cards all need them read back.
- **D7 — `02` emits a structured epic list** (`name · summary · depends_on · owned_paths · parallel_with`) → indexed into SQLite → shown as **epic cards in the GUI immediately** (the Traycer-like view), *before* `03` expands them into files.
- **D8 — Store split: disk = source of truth, SQLite = derived index.** NOT SQLite-only (would trap artifacts in the cockpit + break the headless driver + agent-readability — the Traycer-proprietary-store mistake the pipeline explicitly rejects). Files are agent-readable, git-tracked, portable; SQLite caches names/summaries/status/executions for fast GUI rendering.
- **D9 — On-disk layout mirrors the tree** *(proposed; needs a one-line allowlist update)*:
  ```
  docs/development/
  ├── 00-vision.md
  ├── infra-decisions.md
  ├── external-tools.md            (fabrik-lib verdict)
  └── epics/
      └── epic-<n>-<slug>/
          ├── epic.md              (brief/summary — the container)
          ├── core-flows.md
          ├── tech-plan.md
          └── tickets/ticket-<n>.md
  ```
  So the file-tree panel, the GUI drill-down, and the agent-read contract are one shape.
- **D10 — Per-command I/O contracts.** Each command declares structured `consumes` / `produces` / `gate` / `next` (frontmatter). The union of all `produces` = the GUI's artifact/ticket/execution nodes = the pipeline DAG. **One data model** drives GUI + routing + validation.
- **D11 — The steps are not the bible.** The command chain is modifiable (add/remove/reorder), made safe by the typed I/O contracts (D10).
- **D12 — Two GUIs** (see below): a **Mega-Epic** view (project) and an **Epic** view (inside one epic). Each = **Chat · List · Reader** (3 regions); left List = 3–4 category cells; right Reader shows the selected item.

---

## The two GUIs

### GUI 1 — Mega-Epic Breakdown (project level · NO tickets)
```
┌───────────────┬────────────────────┬────────────────────────┐
│    CHAT        │  LIST               │  READER                │
│  runs 00, 02   │   Artifacts         │   selected item        │
│  (Vision,      │   Decisions         │   rendered here        │
│  decomposition)│   Specs / Infra     │   (read-only md)       │
│                │   Epics  ───────────┼─► click → opens GUI 2  │
└───────────────┴────────────────────┴────────────────────────┘
```

### GUI 2 — Epic (inside one epic · epic-to-ticket workflow)
```
   Project ▸ Epic-<n>
┌───────────────┬────────────────────┬────────────────────────┐
│    CHAT        │  LIST               │  READER                │
│  runs 01..11   │   Artifacts         │   selected item:       │
│  for THIS epic │   (brief, flows,    │   md · diff ·          │
│                │    tech-plan)       │   run transcript       │
│                │   Tickets  ─────────┼─► click → Executions   │
│                │   Executions        │                        │
└───────────────┴────────────────────┴────────────────────────┘
```

---

## ⚠️ Amendment 2026-07-17 — Traycer Desktop trial DONE; decision REVERTS to the agetor fork

**Reached Traycer Desktop inside WSL** (installed via `.deb`, `traycer-host` connected) — but getting there
surfaced a hard, general fact that decides this independent of Traycer's own merits:

- **WSLg on this machine has a HiDPI display bug**: at 200% Windows scaling, WSLg's Weston compositor
  registers windows (RAIL app-list, taskbar icon) but **never paints their content** — for *every* GUI app,
  not just Traycer (`xeyes`/`xclock`, plain X11 with zero Chromium, showed the identical symptom). Root
  cause + fix: `C:\Users\user\.wslgconfig` → `[system-distro-env]` → `WESTON_RDP_DISABLE_HI_DPI_SCALING=true`
  + `wsl --shutdown`. Confirmed working (`xeyes` visible, then Traycer visible) — but only after ~2 hours of
  layered misdiagnosis (chased Chromium GPU/GL flags — `--disable-gpu`, ANGLE/SwiftShader, X11-vs-Wayland
  ozone — before finding the actual HiDPI root cause).
- **Separately, Traycer Desktop is confirmed Electron** (`clients/desktop/package.json`) — the #3 lightweight
  requirement still fails on its own terms, independent of the WSLg saga.

**Operator decision (2026-07-17): return to developing our OWN orchestrator.** "Our approach is better."
This **reverts** the 2026-07-16 amendment below — **Traycer Desktop is no longer the primary candidate**;
the **agetor fork (D1/D2) is reinstated as the plan.**

**Why this episode strengthens the fork case (not just preference):**
1. **WSLg is fragile on this box** — a display bug silently blocks *every* GUI app until a non-obvious
   host-side config fix. This risk is now KNOWN and MITIGATED (the `.wslgconfig` fix is in place,
   `guiApplications=true` is set) — so it de-risks the agetor WSLg spike too: whichever app we run next
   (agetor/Electrobun/WebKitGTK) inherits this same fixed HiDPI baseline, not a fresh unknown.
2. **Debugging someone else's Electron app blind (no source access to its renderer) was slow.** Owning the
   cockpit (forking agetor) means the operator/agent fleet can read the actual render/window code when
   something breaks — not guess flags against opaque logs.
3. **Traycer Desktop's own merits are unchanged** (still ~15/17 requirements, still Electron) — the
   reversal is about **control and fit**, not a finding that Traycer is broken. Keep it installed as a
   reference/fallback; it is not being torn down.

**State now:** WSLg confirmed capable of displaying GUI apps (with the fix applied). **D1 (fork agetor)
reinstated as the active plan.** Next concrete step: the agetor WSLg spike (clone at `/tmp/agetor-eval`,
build, run one real Claude task end-to-end) — now with the HiDPI blocker already cleared.

---

## Epic Mode probe 2026-07-17 — Traycer runs its OWN pipeline (evaluation input, NOT a closure)

**Test run (operator, live):** connected Claude Opus 4.8 inside Traycer Desktop (WSL) and asked, on
entering an epic, which workflow files it follows. Full reply on record in the conversation transcript
this doc is derived from. Key finding, verbatim from the agent's own account:

> *"there isn't a single on-disk 'workflow file' I load when I enter an epic... My epic behavior comes
> from instructions injected into my context by Traycer, plus a set of skill definitions I invoke on
> demand"* — the injected set: `traycer-epic-brief`, `traycer-core-flows`, `traycer-tech-plan`,
> `traycer-revise-requirements` (planning); `traycer-ticket-breakdown`, `traycer-execute`,
> `traycer-implement`, `traycer-artifact-critique`, `traycer-review`, `traycer-changeset-walkthrough`
> (execution); `traycer-debate`, `traycer-autobuild`, `traycer-housekeeping` (other).

**What this proves:**
1. **Tool-capability is real** — Claude Code inside Traycer genuinely invokes the `Skill` tool, reads the
   real filesystem, reports precisely. The original concern with Traycer (tool-less chat) is confirmed
   solved at the engine level. Req #6 (subscription auth, tool-capable agent) → ✅.
2. **But "entering an epic" runs TRAYCER'S OWN pipeline, not ours.** `traycer-epic-brief` →
   `traycer-tech-plan` → `traycer-ticket-breakdown` → `traycer-execute` structurally mirrors our
   `01-decisions-lock-fabrik → 03-tech-plan-fabrik → 06-ticket-breakdown-fabrik → 07-execute-fabrik` almost
   1:1 — validating our design's shape — but it is a **separate, non-Fabrik-aware implementation**: no
   BLOCKING live-research gate, no `fabrik-lib` verdict, no Tier-2 `final_gate.py` enforcement, no rule-pack
   awareness, no `docs/development/epics/` file convention. Req #14 (embed OUR `/fabrik-*` pipeline) →
   **fails via the native Epic Mode entry point.** A "Custom Workflows" override exists in principle (per
   the docs research) but is untested and would mean fighting the tool's own default injection rather than
   using it cleanly.
3. Combined with the standing, unconditional fact that **Traycer Desktop is Electron** (req #3 fails
   regardless of any workflow finding) — the evidence now **converges**, not just leans.

**Correction to the operator's framing:** "wait for Traycer to develop WSL support" is moot — WSL support
is **already confirmed working** (installed, connected, running, tonight). The open question was never
WSL support; it was whether Traycer's workflow model fits **our** pipeline. This probe answered that: no,
not without adversarial reconfiguration.

**Working direction (NOT final):** the Epic Mode probe leans us toward the **agetor fork** — Traycer's
native pipeline isn't Fabrik-aware and it's Electron. But **Traycer Desktop stays a live candidate /
break-glass fallback; nothing is ruled out.** We're currently **spiking agetor** to see whether it earns
the pick before committing either way. Next concrete step: the agetor WSLg spike (`/tmp/agetor-eval`,
HiDPI blocker already cleared) → wire Claude Code → live-task trial, then compare against Traycer.

---

## Amendment 2026-07-16 — Traycer Desktop (open-source) is a live contender

Traycer shipped a **free, open-source (MIT) desktop app** (`github.com/traycerai/traycer`) **purpose-built for exactly this cockpit's pattern** — command-file workflows + a Next-Steps DAG + custom CLI agents + epics/tickets/artifacts + worktrees + subscription auth. It likely **obsoletes the agetor fork** *if* one crux holds (tool-capable command execution, below).

**This supersedes D1/D2:** **Traycer Desktop = primary candidate (pending the trial); the agetor fork = fallback.** And the original reason we left Traycer (tool-less chat) appears **solved** — a custom CLI agent runs **real Claude Code** as a subprocess (`$TRAYCER_PROMPT`), which is tool-capable (shell · MCP · gate · subagents · subscription).

### 17-requirement conformance (grounded from the repo + docs)
| # | Requirement | Traycer Desktop |
|---|---|---|
| 1 | Cockpit / orchestrator | ✅ it is one |
| 2 | Fork-and-own | 🟡 MIT (forkable) — but likely **use as-is**, no fork |
| 3 | Lightweight, **NOT Electron** | ❌ **Electron** (`clients/desktop/package.json`: *"Traycer standalone desktop shell (Electron)"*) |
| 4 | Native desktop app | ✅ Windows `nsis`/`msi` + Linux AppImage/deb/rpm + macOS |
| 5 | ~20 concurrent agents | 🟡 built for parallel fleets; 20-scale unverified |
| 6 | Claude OAuth/subscription, no API key | ✅ "bring your Claude/Codex/Opencode subscription" |
| 7 | No direct OpenRouter (pool via Claude) | ✅ Claude = a custom CLI agent → your pool runs inside it |
| 8 | Per-task git worktrees | ✅ native (`concepts/worktrees`) |
| 9 | GUI approvals / human gates | 🟡 drives agents; structured-approval-card depth unverified |
| 10 | Local-first (no cloud relay) | 🟡 has team boards / real-time editing → **verify cloud dependency** |
| 11 | GUI: file tree · md · git · hierarchy | ✅ Epic mode (artifacts/tickets, git-diff panels, tabs/sub-tabs) — *the 4-window artifact view* |
| 12 | Run workflow GUI-based | ✅ |
| 13 | Chat can be minimal | ✅ (full chat present) |
| 14 | **Embed `/fabrik-*` pipeline** | ✅ **custom workflows = command files + Next-Steps DAG** (docs: *"chain commands like mega-epic-breakdown → epic-to-ticket"*) — *pending the tool-capability crux* |
| 15 | Board maps to flow (2 gates) | 🟡 Next-Steps DAG; gate-as-board-state mappable |
| 16 | Windows + WSL | ✅ Windows build; drives Claude in WSL (workable, unverified) |
| 17 | Open source, permissive | ✅ **MIT** |

**Score: ~15/17.** Only hard miss = **#3 (Electron)**. Weight nuance: **one** cockpit instance ≈ 300–500 MB baseline (one-time, **not ×20**) — noise vs the 20-agent fleet (already 49 claude procs in ~5 GB). So holding #3 strictly = rebuild+maintain a cockpit to save ~350 MB.

### The crux — a 30-minute hands-on trial (go/no-go)
Does a Traycer **workflow command** execute through the **tool-capable Claude Code agent**, or through Traycer's own (possibly tool-less) planner?
1. Install Traycer Desktop.
2. Register **Claude Code** as a custom CLI agent (subscription; confirm `ANTHROPIC_API_KEY` unset — Claude Code prioritizes an API key over the subscription).
3. Create a workflow with **one `-fabrik` command file** (e.g. a trimmed `00-trigger-fabrik`).
4. Run it → confirm it actually **reads real files · runs `python scripts/final_gate.py` · does live web research (exa/brave) · dispatches subagents** → **tool-capable ✅**. If it only produces a plan → **tool-less ❌** (old blocker persists → fall back to agetor).
5. While there, clear the 🟡 items: 20-agent scale · structured approval cards · **local-vs-cloud** (does it need a Traycer account/relay?) · Windows→WSL Claude execution.

**Decision rule:** trial passes tool-capability **and** you accept Electron → **adopt Traycer Desktop, drop the fork.** Trial fails, **or** Electron is unacceptable → **fork agetor.**

---

## Phase 0 — WSLg render spike: RESOLVED ✅ GO (2026-07-18)

The make-or-break question is answered: **agetor's Electrobun (WebKitGTK) Linux build renders
under WSLg**, and its real orchestrator cockpit UI (task composer + BACKLOG→DONE kanban) painted
crisply and interactively (an earlier Chromium-under-WSLg attempt could not render at all). Backend
wired too: 27 SQLite migrations applied, API on `127.0.0.1:4318`, and PATH-rehydrate found the
subscription `claude=/home/ozgur/.local/bin/claude` + `tmux=/usr/bin/tmux` (no `ANTHROPIC_API_KEY`).
**Direction (not final): agetor is the leading fork candidate; the from-scratch Tauri option is set
aside. Traycer Desktop stays a live fallback.** Full live-task drive (worktree + tmux + approval card)
not yet exercised.

### WSLg baseline — fold ALL of this into the fork's Linux launcher (so nothing is hand-edited)
- **System libs (apt):** `libwebkit2gtk-4.1-0`, `libayatana-appindicator3-1`. Electrobun's
  `libNativeWrapper.so` dlopen-fails without them.
- **`LD_LIBRARY_PATH` → the app's `bin/`:** Electrobun ships `libasar.so` beside the wrapper but
  omits an `$ORIGIN` rpath, so the loader can't find it. The fork launcher MUST export this (or we
  patch the rpath at build).
- **Software compositing:** the `X11 Error: GLXBadWindow` + `libEGL … DRI3` warnings are **benign** —
  WebKitGTK falls back to software compositing and paints correctly. No `/dev/dri` needed (that was
  the Chromium/ANGLE wall). Do NOT chase GPU flags.
- **HiDPI (the fiddly part):** Windows monitor scaling (200%) → WSLg presents a **1920×1200 logical**
  X-screen, not native 4K. `.wslgconfig` `WESTON_RDP_DISABLE_HI_DPI_SCALING=true` is **kept** — it's
  required by sibling **Chromium WSLg apps** (calendar-engine admin-ui, Brand Identity Creator);
  removing it to get native-4K crispness risks regressing them (that flag was the Traycer HiDPI fix).
  Consequence: on 1920×1200 logical you can't have both razor-crisp (`GDK_SCALE=2` halves usable
  logical px) AND the full 6-column board (needs ~2060 logical). Dialed-in compromise that fits:
  - `GDK_SCALE=1`, window frame **1912×1117 @ (0,0)** (`DEFAULT_FRAME`), renderer **`html{zoom:0.9}`**
    to shrink the board ~10% so every column fits. Fork ships this as a real **Ctrl± zoom / window
    setting**, not a source constant.
- **Prereqs:** Bun 1.3.14 (`~/.bun/bin/bun`), tmux 3.4, WSL claude v2.1.214.

### Claude Code wiring — subscription-only, VERIFIED (2026-07-18)
- **Harness:** built-in `claude-code` (also `codex`), enabled by default, `is_builtin=1`. No custom
  `home` → agetor does NOT override `HOME`/`CLAUDE_CONFIG_DIR`, so claude reads the real `~/.claude` +
  `~/.claude.json` = your OAuth subscription (`mob@ocoron.com`, `~/.claude/.credentials.json`).
- **Binary:** `resolveBin()` (`agents.ts`) → `harness.bin` → `AGETOR_CLAUDE_BIN` → `Bun.which("claude")`.
  Resolves to `/home/ozgur/.local/bin/claude` v2.1.214.
- **Drive:** `spawnClaudeViaTmux` (`claude-tmux.ts:3576`) builds env via `buildClaudeSessionEnv`, then
  `tmux new-session -e K=V …` on agetor's **private tmux socket** (`tmuxSocketArgs()` → `-L <name>`).
- **⚠️ CRITICAL metered-key leak (found + fixed):** `/opt/fabrik/.env:29` exports `ANTHROPIC_API_KEY`
  (for `fabrik ai generate`). It was inherited into agetor's process → its private tmux server's global
  env → every claude session (a session inherits the server env, not just `-e` vars). Claude Code
  prioritizes the API key over OAuth, so it would have **silently billed the metered API**. Two-layer fix:
  1. **Code (fork-grade):** `buildClaudeSessionEnv` now `delete`s `ANTHROPIC_API_KEY` + `ANTHROPIC_AUTH_TOKEN`.
  2. **Launch:** start agetor with those unset so the tmux *server* env is clean.
  Verified: agetor `/proc/<pid>/environ` = **0** ANTHROPIC keys (login shell = 1). Fork must bake BOTH in.

### Spike-only edits (throwaway `/tmp/agetor-eval` clone — NOTHING in `/opt/fabrik` touched)
- `src/bun/index.ts` + `vite.config.ts`: HMR port `5173→5199` (5173 was owned by calendar-engine's
  vite — a **port collision**, not a bug; the fork picks a private port or a free-port probe).
- `src/bun/window-lifecycle.ts` `DEFAULT_FRAME` and `src/mainview/index.css` `zoom` — the window-fit
  values above.

## Open items (NOT yet locked)
- Exact left-column **cell grouping** per GUI (Mega: Artifacts/Decisions/Specs-Infra/Epics; Epic: Artifacts/Tickets/Executions — subject to refinement).
- **Per-epic directory (D9) vs flat epic file** — D9 proposed, not ratified.
- Whether **executions** persist to disk (logs) or SQLite-only.

## Provenance
- Requirements: `docs/orchestrator/orchestrator-cockpit-requirements.md`
- Research: `docs/reference/research/ai-coding-orchestrator-comparison.md`
- North-star (this is its Phase-D cockpit): `docs/orchestrator/00-autonomous-factory-north-star.md`
- Fork-target deep read: `alamops/agetor` @ v0.0.17 (`agents.ts:286` subscription-drive; `03-expand-epic-files-fabrik.md:24` disk-is-the-store).
