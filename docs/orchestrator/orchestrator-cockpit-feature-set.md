# Orchestrator Cockpit — Feature Set (derived from a deep Traycer Desktop analysis)

**Status:** DERIVED v1 — input to the cockpit spec/plan · **Date:** 2026-07-17 · **Owner:** ob@ocoron.com
**Companion to:** `orchestrator-cockpit-requirements.md` (the 17 requirements) + `orchestrator-cockpit-decisions.md` (D1–D12 + closure).
**Method:** hands-on analysis of the live Traycer Desktop 1.1.6 install in WSL — all 13 injected skills read in full
(`~/.traycer/.claude/skills/*/SKILL.md`), the shared philosophy + 2 lenses, the CLI surface exercised live
(`traycer agent|comments|worktree|workspace|monitor`), harness/model discovery run live, the renderer bundle mined for the
UI model (`epic-session-provider-*.js`), and the operator's own customization layer (`agent-selection-guide.md`,
`routing-policy.yaml`). The operator has used Traycer for months (extension era) and judged its stock commands
"too shallow" — this doc extracts what is worth taking, adapting, or skipping for OUR cockpit (the agetor fork).

---

## Traycer Desktop's anatomy (as measured, not as marketed)

| Layer | What it actually is |
|---|---|
| **Desktop** | Electron shell hosting a React renderer; lifecycle delegated to the CLI |
| **Host** (`traycer-host`) | The process owning workspaces, terminals, files, git, agents (the "Host" concept; cross-device "coming soon") |
| **CLI** (`traycer`) | auth · host supervisor · `workspace`/`worktree` (create/list/delete + teardown scripts) · `agent` (create/send/transcript/inbox/list-harness-models/selection-guide) · `comments` (artifact threads) · `monitor` (inbox stream) |
| **Skills** | 13 `SKILL.md` files injected per session (`.traycer-managed.json`: "Do not edit") + shared `philosophy.md` + 2 lenses |
| **Artifacts** | On-disk markdown under `~/.traycer/epics/<id>/artifacts/**` — frontmatter `kind` (`story`/`spec`/`review`) + `title` + `status`; dir-per-unit (`tickets/<name>/index.md`, `debates/<slug>/round-01/…`, `autobuild/<slug>/sprint-01/…`) |
| **Harnesses** | 14 pluggable agent CLIs (claude, codex, opencode, openrouter, cursor, grok, qwen, kiro, droid, kimi, copilot, kilocode, amp, traycer) with **live model discovery** (`list-harness-models` → model ids incl. `opus[1m]`, reasoning efforts, fast-mode) |
| **User layer** | `agent-selection-guide.md` (prose routing policy the skills consult — the operator's is 5 lines: everything → Opus) + `mcp.json` (operator wired his own kilo MCP server in) |

---

## The derived feature set

Tiering: **ADOPT** = build into the cockpit as-is (concept-level) · **ADAPT** = take the pattern, fabrik-ize it · **SKIP** = deliberately not ours.

### A. Artifact & review layer (the heart of the cockpit GUI)

| # | Feature | Tier | Notes for our build |
|---|---|---|---|
| F1 | **Artifact lifecycle state machine** — `drafting → ready → awaiting_approval → approved / rejected / superseded` (frontmatter `status`, rendered as pills) | **ADOPT** | This is the missing formalization of our two human gates (R14): plan-in = an artifact reaching `approved`. Superseded-tracking kills stale-artifact drift. Add to D9's frontmatter. |
| F2 | **Artifact comment threads** with `open/resolved` status, CLI-inspectable (`traycer comments list/set-status`) | **ADOPT** | The human-review primitive we didn't have: inline comments ON artifacts, agents can read + resolve them. Maps directly onto GUI-1/GUI-2's Reader pane. |
| F3 | **Artifact kinds** (`story` / `spec` / `review` / ticket) driving distinct rendering + grouping | **ADAPT** | Extend with our kinds: `vision`, `epic`, `ticket`, `decision`, `infra`, `walkthrough`. Kind = the left-column cell it lands in (D12). |
| F4 | **Dir-per-unit artifact layout** (`tickets/<name>/index.md`, `debates/<slug>/round-N/<perspective>/index.md`) | **ADOPT** | Independently validates our proposed D9 (dir-per-epic). Ratify D9. |
| F5 | **```wireframe blocks** — self-contained HTML in an artifact, rendered as a live preview | **ADOPT** | Perfect for `02-core-flows` / `/fabrik-ui-design` artifacts. Cheap in a webview cockpit. |
| F6 | **Changeset walkthrough** — a review-guide artifact for the human: change areas, risk-first review order, non-obvious decisions, gotchas, verification state | **ADOPT** | This IS the missing Gate-2 (deploy-approval) artifact. Make it a required output of our `07-execute` before the deploy gate. |

### B. Multi-agent runtime

| # | Feature | Tier | Notes |
|---|---|---|---|
| F7 | **Peer-to-peer inter-agent messaging** (`agent send`, inbox, `monitor` stream) — agents message each other directly, mediator not the middleman | **ADAPT** | Enables debate cross-examination + generator↔evaluator contract negotiation. Our pool (`subagents`) is dispatch-only today; the cockpit needs a message bus (SQLite table + polling is enough at our scale). |
| F8 | **Child-agent transcript inspection** (`agent transcript`, `traycer_get_transcript`) — "read the trace, don't just relaunch" as the primary debugging loop | **ADOPT** | agetor already tails Claude JSONL; expose it as a first-class cockpit view (Executions cell → transcript in Reader). |
| F9 | **Multi-harness registry + live model discovery** (models, reasoning efforts, fast-mode per harness, resolved at runtime — never hard-coded) | **ADAPT** | agetor's `AGENT_OPTIONS` is curated-static; adopt Traycer's live-probe pattern. Matches our "roster stays LIVE via pick_models" rule. |
| F10 | **User-editable agent-selection-guide** consulted by every skill before spawning | **ADAPT** | Ours must route: Opus = orchestrator/authority, pool via `libs/subagents` = breadth (D4) — i.e. the guide encodes `62-using-subagents.md`, not a free-text whim. |
| F11 | **Worktree provenance** — every worktree carries `owners[]` (epicId, ownerKind, ownerId), PR state, branch status | **ADOPT** | agetor has worktrees; add the ownership/provenance layer so the GUI can answer "what created this and is it safe to delete". |
| F12 | **Worktree lifecycle classifier** — 6 shared tiers (`in-use / orphaned / review / merged / at-base-commit / unreferenced`), same classifier in UI + CLI + skill; housekeeping = report → approve → delete via CLI only | **ADOPT** | Solves worktree sprawl (the #1 ops pain of this tool class) with real judgment (submodule cohort, null-signal ≠ green). Steal the tier model wholesale. |

### C. Orchestration patterns (from the skills — the best content in the product)

| # | Feature | Tier | Notes |
|---|---|---|---|
| F13 | **Autobuild** — Planner/Generator/Evaluator adversarial loop: deliberately high-level spec; Generator↔Evaluator **negotiate a per-sprint contract** ("what does done mean"); **dual verdicts** (contract + user-approved rubric — a pair can't negotiate itself an easy pass); Evaluator **exercises** the output (browser MCP), never reads Generator's reasoning; **checkpoint-restart over endless patching**; state-ownership table; JSON breadcrumbs ("models overwrite markdown far more readily") | **ADAPT** | The strongest single idea in Traycer. Map onto our stack: Generator = `07-execute` coder, Evaluator = `/fabrik-review` finders + Build-Verification-Loop, rubric = our checklists + gate. **The contract-negotiation step and dual-verdict are NEW to us — adopt both.** Contract ≈ our ticket Done-When, but *negotiated with the verifier before building*. |
| F14 | **Debate** — roster proposal → user approves perspectives → **execution profiles** (model/effort per perspective, live-resolved) → user approves → rounds with **peer cross-examination** → synthesis per round → stop criteria → closing digest for a reader who didn't follow the process | **ADAPT** | A formalized, GUI-native version of our judge-panel pattern. Keep for consequential design decisions (spec-review escalation). Pool = perspectives, Opus = mediator (D4-compliant). |
| F15 | **Readiness Check** — before drafting any plan artifact, a *visible* message to the user: what's still vague · which answers left implementation space open · silent inferences — then the USER decides drafting | **ADOPT** | Directly upgrades our `ask-before-not-during` lesson into a structured pre-draft gate. Add to `00`/`02`/`03` twins. Honest-empty allowed ("if it's short, that's legitimate"). |
| F16 | **Execution drift taxonomy** — Well-Implemented / Minor Issues / Technical Drift / Product Misalignment / Major Drift; fixup-tickets under the same ticket; **the same child agent that built it fixes it**; deviations recorded in a run-spec for observability | **ADOPT** | Our `07-execute` twin has review loops; this taxonomy + same-agent-fixes + deviation-spec is cleaner triage vocabulary. Product-lens = non-negotiable, tech-lens = flexible mirrors our spec.shape-canonical rule. |
| F17 | **Fresh-agent review rule** — "if you produced or shaped the code this session, you're too close to judge it; delegate to a fresh agent" (in BOTH review + critique skills) | **ADOPT** (already ours) | Independently confirms our CC1 (separate fresh-context review beats embedded self-review). No change — evidence our discipline is right. |
| F18 | **Child-implementer contract** (`traycer-implement`, 21 lines) — ask-on-correctness-uncertainty, don't block on minor choices, keep a running note of interpretations/deviations/tradeoffs, structured report-back | **ADOPT** | The leanest good handoff contract we've seen. Make it the template for our `07` coder handoffs (compose with `owned_paths` File Scope). |
| F19 | **Review lenses** — baseline pass / correctness-in-context (blast radius) / reuse / simplification / efficiency / altitude / alignment; findings validated against real code before reporting; leave out findings that wouldn't change what anyone does | **ADAPT** | Merge into our `/fabrik-review` finder partitions; "altitude" (special-case patch over shared machinery = fix belongs deeper) is a lens our finders lack. Validate-before-report = our refute step (confirms CC1 refute). |

### D. GUI / chat UX (why Traycer's chat feels good — directly reusable in our webview cockpit)

| # | Feature | Tier | Notes |
|---|---|---|---|
| F20 | **`<TRAYCER_NEXT_STEPS>` protocol** — the agent ends turns with prose + checkbox options; the renderer parses it into **clickable next-step chips** | **ADOPT** | Our § Pipeline "name the NEXT command" rule, turned into a GUI affordance. Trivial to parse; agents already produce it if told. This is how the cockpit drives the command chain click-by-click. |
| F21 | **Activity compression** — tool calls classified (read/explore/search/edit/run/hook/subagent/approval) and folded into one-line group summaries ("explored 3 files, read 5, edited 2, spawned 2 subagents"), expanded on demand | **ADOPT** | THE answer to "raw agent streams are unreadable" (the operator's original complaint about Zed's panel). agetor already has structured JSONL events — add this folding layer over them. |
| F22 | **Interview tiles** — structured Q&A segments rendered as forms; collapsed to "Answered 3/4 questions" | **ADOPT** | agetor already intercepts AskUserQuestion → cards; add the collapsed-summary state. |
| F23 | **A2A message tiles** — inter-agent sends/receives as first-class transcript items | **ADOPT** | Pairs with F7. Makes multi-agent runs legible. |
| F24 | **Todo-progress tiles** with status styling | **ADOPT** | agetor has `TodoProgressCard` already — keep. |

### E. Deliberately SKIP

| Feature | Why not |
|---|---|
| Electron shell | Fails req #3 — the whole reason for the agetor (Electrobun) fork. |
| Traycer cloud auth + team boards / real-time collab | Solo operator; local-first (req #10). Per-user local login only. |
| Traycer's own cloud "traycer" harness | Subscription-Claude + pool only (D3/D4). |
| 14-harness breadth | We need exactly one interactive harness (Claude Code); the pool covers breadth through it. Keep the *registry pattern* (F9), not the inventory. |
| Voice dictation / STT models (parakeet) | Not our use case. |
| `.traycer-managed.json` overwrite model | **Anti-feature for us**: user edits to managed skills are silently at risk on update (the operator HAS edited his layer — his guide survives only because it's a user-layer file). Our fabrik-sync manifest + `check_synced_unmodified.py` is the stronger, gate-enforced version. Cockpit command files stay in OUR repo, synced OUR way. |

---

## Gap analysis — what WE have that Traycer lacks (the moat; do not trade away)

| Ours | Traycer's state |
|---|---|
| **BLOCKING live-research gates** (N3k: every external fact grounded via exa/brave/firecrawl, cited) | Absent — planning trusts the model + user paste |
| **Tier-2 `final_gate.py`** (mypy/bandit/semgrep + doc-sync + convergence checks) as the acceptance bar | Absent — "verification expectations" are prose in tickets |
| **Rule packs + scaffold/shape awareness** (11 types, registrars, PORTS, deploy invariants) | Absent — generic codebase exploration |
| **fabrik-lib vendor→enhance→build verdict** | Absent |
| **Convergence-to-no-op loops** (md5-stable, Pass Ledger) | One-pass review/critique; no fixed-point discipline |
| **Two-level mega→epic decomposition** (vision → independent epics with `owned_paths` disjointness proofs) | Flat epics; no decomposition tier, no file-scope contracts between parallel units |
| **The flywheel** (`results_table` + `record_agent_run` → `pick_models` learns) | `agent-selection-guide.md` is static prose; nothing learns |
| **Deploy pipeline** (fabrik apply, 10 registrars, Gatus/Prometheus/Backrest) | Explicitly out of scope ("no deployment tickets unless asked") |

**The verdict this table encodes:** Traycer built a better *cockpit shell* (artifact lifecycle, chat UX, agent runtime, worktree ops); we built a better *engineering discipline* (grounding, gates, convergence, decomposition, deploy). The cockpit project = put OUR discipline inside THEIR class of shell — on a lightweight base (agetor).

---

## Implications for the agetor fork (delta to the locked fork scope)

The fork scope in `orchestrator-cockpit-decisions.md` grows by these concrete, now-referenced items — each with a proven design to copy rather than invent:

1. **Artifact layer** (F1–F4, F6): frontmatter `kind/title/status` + lifecycle pills + comment threads + dir-per-unit store → feeds GUI-1/GUI-2's List/Reader panes. (Ratifies D9.)
2. **Chat rendering layer** (F20–F24): NEXT_STEPS chips + activity folding + interview/A2A/todo tiles over agetor's existing JSONL events.
3. **Agent runtime additions** (F7–F12): message bus, transcript view, live model discovery, worktree provenance + 6-tier classifier + housekeeping flow.
4. **Command-content upgrades** (F13, F15, F16, F18, F19) — these land in the `-fabrik` command files, not the cockpit code: Readiness Check into `00`/`02`/`03`; contract-negotiation + dual-verdict into `07`+review; drift taxonomy + implementer contract into `07` handoffs; altitude lens into `/fabrik-review`.
5. **Debate/autobuild as later skills** (F13, F14) — after the core chain runs end-to-end.

Priority order for v1 (matches D12's two GUIs): **1 → 2** (artifacts + readable chat = the operator-facing core), then **3**, then **4** (pipeline content, independent of cockpit code), then **5**.

## Appendix — Windows Desktop app: file & GUI anatomy (measured live, 2026-07-17)

Analyzed the running Windows install (`C:\Program Files\Traycer`, v1.1.6) from WSL: full file tree, asar index
parsed, live process table, window enumeration + screen capture, and the desktop state file
(`C:\Users\user\.traycer\desktop-windows.json`).

**Install & runtime weight (measured, not estimated):**
- Install ≈ **470 MB**: `Traycer.exe` 232 MB (Electron), `resources/` 170 MB (app.asar 55 MB main-process deps ·
  renderer 26 MB · **CLI 91 MB self-contained binary**), locales 48 MB, GPU stack DLLs (dxcompiler/dxil/vulkan/swiftshader).
- Live footprint right now: `Traycer.exe` ×3 ≈ **445 MB** + `traycer-host.exe` **204 MB** + CLI ≈ **~650 MB running**.
  (agetor's Electrobun class: ~50–100 MB. The req-#3 argument, now in numbers.)
- The **host is not shipped in Program Files** (placeholder README only) — the CLI stages `traycer-host.exe` per-user at
  runtime and reconciles versions (`cli/manifest.json`, `desktop-reconcile.json`). Clean separation: shell ⁄ CLI ⁄ host
  each update independently — an architecture worth copying in the fork.

**GUI model (from the live window + `desktop-windows.json` + renderer bundle):**
- **Browser-style epic tabs**: one tab per epic (+ new-tab, back/forward nav); multi-window with an explicit
  `ownership` map (tab ↔ epic ↔ window). Tray icon + global shortcut (`Ctrl+Shift+Space`).
- **Per-tab canvas = a tiling pane tree**: `root pane → tabInstanceIds → tiles`, resizable groups, preview tabs,
  activation history — a mini window-manager per epic. (Our D12 fixed 3-region layout is the deliberately simpler v1;
  the freeform canvas is a vNext option, not a v1 need.)
- **Detached agent windows**: an agent terminal (the floating `claude` window, Claude icon) pops out as its own OS
  window. Nice affordance; not v1.
- Electron renders via DirectComposition — screen captures of content come back black (`PrintWindow`/`CopyFromScreen`
  can't grab the HW surface); only window chrome + tab bar captured. GUI structure was therefore derived from the
  state file + renderer code, which is the stronger source anyway.

**Two clarifying facts for the record:**
1. The **"WSL Integration Setup" tab is an operator-created epic** (epicId `77915f39…` in the Windows-side
   `~/.traycer/epics/`), not a Traycer product feature — the Windows app still cannot reach WSL (its `claude` window
   runs `claude.exe` against Windows paths). The docs' "no Windows→WSL connection; cross-device Hosts coming soon"
   remains true.
2. The **extension-era epic store** (`Temp/traycer-epics/<id>-<name>/`) used exactly
   **`specs/` · `tickets/` · `executions/`** as its taxonomy — the operator's three-cell List model (D12) is the
   structure he already lived with for months. Independent validation of GUI-2's left column.

## ⚠️ OPERATOR NOTE — your Traycer skill edits are at overwrite risk

> Every `SKILL.md` under `~/.traycer/.claude/skills/` (and `~/.traycer/.agents/skills/`) carries a
> `.traycer-managed.json` "Generated by Traycer. **Do not edit**" marker — **Traycer updates will silently
> overwrite in-place edits.** Your `agent-selection-guide.md` is safe (user-layer file, consulted by the skills
> but not managed), but if you changed any `SKILL.md` directly, **copy those modified files into
> `docs/traycer/` (version-controlled) BEFORE the next Traycer update** — otherwise the customizations die
> with the update, silently. This is the exact failure mode fabrik's own synced-files gate
> (`check_synced_unmodified.py`) exists to prevent; Traycer has no equivalent guard.

## Residuals / risks

- The Epic Mode *injected system prompt* itself was not extractable from the renderer bundle (host-side or cloud-delivered); its content is known only via the operator's in-session probe (artifact model, planning/execution command split, agent tools, NEXT_STEPS). Good enough for feature derivation; re-probe if we need exact wording.
- Skill-edit overwrite risk — see the ⚠️ OPERATOR NOTE above.
- Traycer versions its skills with the app; our adopted patterns are frozen HERE as of Desktop 1.1.6 — re-derive deliberately, not by accident, if Traycer ships major new skills.
