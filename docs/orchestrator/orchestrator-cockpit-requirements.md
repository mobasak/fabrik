# Orchestrator Cockpit — Requirements

**Status:** LOCKED (v1) — under active evaluation. Both **Traycer Desktop** and the **agetor fork** are
live candidates against this requirement set; we're currently spiking agetor (Phase 0 passed 2026-07-18)
to see if it earns the pick. **No final choice yet — Traycer is NOT ruled out** (see
`orchestrator-cockpit-decisions.md`). · **Date:** 2026-07-16 (amended 2026-07-18) · **Owner:** ob@ocoron.com
**What this is:** the requirement set for the **Fabrik-managed orchestration front-end** — the
interactive cockpit the operator drives the `/fabrik-*` pipeline from. This is the north-star's
**Phase-D** deliverable (`[canonical: docs/orchestrator/00-autonomous-factory-north-star.md § D-Zed]`),
re-scoped from "a Zed extension" to **a standalone lightweight desktop app, built by forking an
open-source agent orchestrator** (current pick: **agetor**, `alamops/agetor`, MIT/Electrobun).

**Relationship to the rest of the factory:**
- **This cockpit** = the **interactive** operator surface (drive spec→plan→execute, approve the two gates). Runs `claude` **interactive** per task.
- **`fabrik-lib/subagents` pool** = OpenRouter breadth, **dispatched by Claude inside those tasks** — never a cockpit feature.
- **D3 driver** (`docs/superpowers/specs/2026-07-15-autonomous-factory-driver-design.md`) = the **headless** twin of this cockpit (`claude -p` + the same pool) for unattended runs.
- All three share the command layer + the pool; OpenRouter lives in exactly one place (the pool), reached **through Claude, not around it**.

---

## Purpose
1. A **cockpit/orchestrator** for the autonomous dev factory — the operator orchestrates AI agents, does **not** hand-code.
2. Built by **forking an open-source orchestrator** (agetor current pick), **fork-and-own** — not a from-scratch IDE, not a browser tab.

## Runtime & footprint
3. **Lightweight** — native-webview class (Electrobun/Tauri), ~50–100 MB idle. **Not Electron.**
4. **Native desktop app**, not a browser-served UI (a window to alt-tab to — not a localhost tab lost among many browser tabs).
5. Sustains **~20 concurrent agent sessions** on the **24-core / 48 GB WSL** host. Cap concurrent *build/test* work (autoscale), not agent count; the agent processes themselves are cheap (~106 MB idle each, measured).

## Auth (hard)
6. Drive **Claude Code via OAuth / subscription, per-user local login** — **no `ANTHROPIC_API_KEY`, not the metered Agent-SDK credit path.** (Claude Code prioritizes an API-key env var over subscription auth — it must stay unset.)
7. **No direct OpenRouter in the cockpit.** OpenRouter is reached **only through `fabrik-lib/subagents`**, dispatched by the Claude orchestrator (pool = programmatic breadth, never an interactive tab). Dropped as a first-class feature 2026-07-16.

## Orchestration
8. **Per-task git worktree isolation** — parallel agents on disjoint files (the `owned_paths` contract, north-star R16).
9. **Approvals / human gates surfaced in the GUI** — tool-permission + clarifying-question prompts as structured cards; the **two human gates** (plan-in, deploy-out) as board states.
10. **Local-first** — all state on the machine, no cloud relay.

## GUI (cockpit capable; chat can be simple)
11. **Orchestrator window = a proper GUI:** repo **file tree**, **open/view markdown**, **git status + diff**, and a **hierarchical view of artifacts** (epics → tickets → executions → specs → plans).
12. **Run the entire workflow GUI-based** — drive the pipeline from the board, not the terminal.
13. **Chat/message rendering may be minimal** — polish there is not required; only #11 must be capable.

## Pipeline integration
14. **Extensible to embed the `/fabrik-*` pipeline** — the command chain + the full Tier-2 `final_gate.py` + the rule packs run **inside** the agents (agents-inside-the-quality-system, not a generic runner — the Vibe-Kanban failure mode to avoid).
15. Board maps to the flow: columns/stages = pipeline stages; **plan-in & deploy-out** = the two human gates (north-star R14).

## Platform & foundation
16. Runs on **Windows + WSL Ubuntu** — realistic shape: the **Linux build in WSLg** (tmux + `claude` native in WSL). ⚠️ **The one unproven item — the WSLg runtime spike** (decides *fork agetor* vs *build fresh on Tauri*).
17. **Open source, permissive license** (MIT/Apache) — forkable, modifiable, ownable.

---

## Decision state (2026-07-16)
- **Direction locked:** fork a lightweight open-source orchestrator into a native cockpit.
- **Current pick: agetor** (`alamops/agetor`, v0.0.17, MIT, Electrobun). Deep source read verdict: **genuinely high-quality, deeply tested** (`claude-tmux.ts` ~5,045 LOC + 80 KB test; full GitHub/GitLab/Bitbucket integrations). Subscription/interactive Claude + per-task worktrees + JSONL-based approval cards **already built** (`agents.ts:286`).
- **Fork scope (post-OpenRouter-drop):** (a) add **file-tree + markdown viewer** panel; (b) **map `/fabrik-*`** onto the board; (c) **harden Windows/WSL** (Linux build in WSLg + port peripheral macOS-isms: AppleScript-terminal login flow, macOS notifier).
- **Fallback:** if the WSLg spike fails → **build fresh on Tauri** (first-class Windows via WebView2), using agetor's driver as the reference implementation.
- **Open risk (#16):** Electrobun Linux/WebKitGTK under WSLg — the make-or-break go/no-go spike, not yet run.

## Research trail
- Comparative evaluation of the orchestrator field: `docs/reference/research/ai-coding-orchestrator-comparison.md`.
- Candidates disqualified on the lightweight constraint: Daintree (Electron, 1 GB+), Emdash / Agent-Orchestrator (Electron, 500 MB+), Vibe Kanban (browser JS-heap leak → OOM). Conductor OSS (Rust + web UI, <50 MB) rejected for being **browser-served**, not a native app (requirement #4).
