# Traycer Command Wiring — how the factory's artifacts + autonomous execution run inside Traycer

**What this is:** the setup/wiring contract for running the mega-epic-breakdown and epic-to-ticket-workflow
chains *inside Traycer*, so that every command produces a **Traycer card** (artifact) the cockpit renders, and
the whole idea → epics → tickets → execution flow is driven from the Traycer desktop app.

**The one fact everything derives from:** Traycer is a **layer**, not an AI. **Claude Max (Claude Code) is the
engine connected to it** — so the Traycer path is fully tool-capable (shell, MCP, subagents). There is **ONE
tool-capable command set** (the `-fabrik` files under `docs/orchestrator/**`); the old tool-less `-command`
twins were archived (north-star D2, 2026-07-18).

---

## The three moving parts

| Part | Where it lives | Role |
|---|---|---|
| **Command files** (`-fabrik`) | `docs/orchestrator/mega-epic-breakdown/**` · `docs/orchestrator/epic-to-ticket-workflow/**` | The runnable workflow definitions Claude executes. Git-tracked = source of truth. |
| **Skill wrappers** (`SKILL.md`) | `docs/orchestrator/_traycer-skills/**` → copied to **`~/.traycer/.claude/skills/**`** | Make the commands appear in the **`/traycer` menu** (owner entry point) and be followed by the Traycer-spawned Claude harness. |
| **Projection + schema** | `scripts/traycer_mirror.py` · `scripts/epic_order.py` · `docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md` | Turn a disk artifact into a Traycer **card**; order/validate the epic set. |

**Golden rule (D8):** **DISK is the source of truth; the Traycer store is a projection.** A command writes its
artifact to a git-tracked disk path, then *mirrors* it into the Traycer store. Never make the Traycer store the
only copy — a card with no disk file dies with the session.

---

## The Traycer artifact store (what a "card" is)

Traycer renders artifacts from:

```
$TRAYCER_HOME/epics/$TRAYCER_EPIC_ID/artifacts/<name>/index.md      # $TRAYCER_HOME defaults to ~/.traycer
```

Each `index.md` is markdown with a YAML frontmatter head:

```yaml
---
kind:  spec | ticket | review | story    # spec=vision/plan · story=grouping · ticket=work item
title: "Epic 1 — Billing"
status: 0                                 # 0=TODO · 1=in-progress · 2=done  (ticket/story only)
---
```

For **epic tickets**, the frontmatter is the fuller typed block from `EPIC-ARTIFACT-SCHEMA.md` — one data model
(D10) serving three consumers: `epic_order.py` reads `epic_n`/`depends_on`/`parallel_with`/`owned_paths`;
`traycer_mirror.py` reads `kind`/`title`/`status`; validation (`04`) reads all of it.

---

## `traycer_mirror.py` — the disk → card bridge (the load-bearing wire)

Every command that produces an artifact calls this **after** persisting to disk:

```bash
python /opt/fabrik/scripts/traycer_mirror.py \
       --src   docs/superpowers/specs/2026-07-19-<project>-vision.md \   # the disk artifact (source of truth)
       --name  vision \                                                  # → artifacts/vision/index.md
       --kind  spec  --title "Vision Summary — <project>"  --status 1 \
       --embed                                                           # copy body inline (else a pointer)
```

- **Writes** `$TRAYCER_HOME/epics/$TRAYCER_EPIC_ID/artifacts/<name>/index.md` → the cockpit renders it as a card.
- **NO-OP when `$TRAYCER_EPIC_ID` is unset** → the *identical* command is safe headless (a driver run, any `/opt`
  project). This is why the same command works in Traycer and out of it.
- Same `--name` on a later call **overwrites** the same card (idempotent) — e.g. `02` mirrors a preliminary
  `epic-<n>` card, `03` later overwrites it with the fully-expanded epic.

---

## Setup — where to copy, what to change

1. **Commands** already live at `docs/orchestrator/{mega-epic-breakdown,epic-to-ticket-workflow}/`. Nothing to
   move — they are the canonical set.
2. **Skill wrappers → the `/traycer` menu.** `/traycer` surfaces the skills in **`~/.traycer/.claude/skills/`**
   (the Traycer-managed dir for the Claude harness — that's where Traycer's own `traycer-epic-brief`,
   `traycer-execute`, … live; one such dir per harness: `.claude` / `.opencode` / `.codex` / `.agents`). To
   register a fabrik command there, copy its thin wrapper `docs/orchestrator/_traycer-skills/<name>/SKILL.md`
   into `~/.traycer/.claude/skills/<name>/SKILL.md`. The wrapper only surfaces the command + points at the
   canonical `-fabrik` file — **never copy the command body** (that forks it; one source of truth in
   `docs/orchestrator/`). ⚠️ Traycer may re-sync that dir, so keep the wrapper *sources* in the repo
   (`_traycer-skills/`) and re-copy after a Traycer update (a tiny install step). *(The global
   `~/.claude/skills/` copies only make the commands available to Claude directly — they do NOT put them in the
   `/traycer` menu.)*
3. **Scripts are hub-absolute.** Commands call `python /opt/fabrik/scripts/traycer_mirror.py` and
   `…/epic_order.py` by absolute path — they need no per-project install.
4. **The one env var:** Traycer sets **`$TRAYCER_EPIC_ID`** per epic; that is what makes mirroring fire. (Set
   `$TRAYCER_HOME` only to relocate the store from `~/.traycer`.) Nothing else to configure.
5. **Persist-on-confirm is already wired** into `00`/`02`/`03`: on the owner's confirmation they write the disk
   artifact **and** call `traycer_mirror.py`. When authoring a new command, add both steps.

---

## The end-to-end autonomous flow (what creates which card, in order)

```
idea (in Traycer chat, Claude Max = engine)
 │
 ├─ /fab-mega-00-trigger  → Vision Summary  → specs/…-vision.md          → card: vision (kind spec)   ⟨GATE: owner confirms⟩
 ├─ /fab-mega-02-decompose→ epic proposal + graph → specs/…-epic-proposal.md → preliminary cards: epic-1..N (story)
 ├─ /fab-mega-03-expand   → one ticket FILE per epic → docs/development/epics/…-epic-<n>-<slug>.md
 │                          + infra spec → specs/…-infrastructure-decisions.md
 │                          → mirror each → cards: epic-<n> (kind story/ticket, status 0) + infra-decisions (spec)
 ├─ /fab-mega-04-validate → epic_order.py --check (integrity) + --json (phased order); no new content, arms review
 │
 ▼  each epic card → dispatched (cockpit card-click, or the driver's phase queue)
 └─ per epic: epic-to-ticket-workflow  00-trigger(consume) → 01-brief → … → 06-ticket-breakdown → tickets
              → 07-execute → 08/10 armed review (review_rubric.py) → 11-deploy  ⟨GATE: manual `fabrik apply`⟩
```

- Card **status** moves `0 → 1 → 2` as an epic/ticket progresses; the cockpit shows the live board.
- **Single epic?** Skip mega; enter via `/fabrik-spec` (feature) or the ettw `00-trigger` directly.
- **Two human gates only** (decomposition-in, deploy-out); everything between is agent-run — but the semantic
  reviews are *maximally-enforced, not guaranteed* (see the north-star § Enforcement Model / spec § L1).

---

## Verify the wire works

```bash
# card renders when inside Traycer:
TRAYCER_EPIC_ID=<epic-id> python /opt/fabrik/scripts/traycer_mirror.py --src <disk file> --name smoke --kind spec --title smoke
ls ~/.traycer/epics/<epic-id>/artifacts/smoke/index.md          # → exists

# headless is a clean no-op:
unset TRAYCER_EPIC_ID; python /opt/fabrik/scripts/traycer_mirror.py --src <disk file> --name smoke  # → "mirror skipped", exit 0

# the epic set is well-formed + orderable:
python /opt/fabrik/scripts/epic_order.py --check --expected-count <N> --epics-dir docs/development/epics
python /opt/fabrik/scripts/epic_order.py --json  --epics-dir docs/development/epics
```

**Contract for any new command:** produce a disk artifact under an allowlisted tree (`docs/superpowers/specs/**`
for specs, `docs/development/epics/**` for tickets) → typed frontmatter per `EPIC-ARTIFACT-SCHEMA.md` →
`traycer_mirror.py` to project it → the card appears. Disk stays truth; Traycer shows it.
