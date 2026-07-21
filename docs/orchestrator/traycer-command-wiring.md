# Traycer Command Wiring — how the factory's artifacts + autonomous execution run inside Traycer

**What this is:** the setup/wiring contract for running the mega-epic-breakdown and epic-to-ticket-workflow
chains *inside Traycer*, so that every command produces a **Traycer card** (artifact) the cockpit renders, and
the whole idea → epics → tickets → execution flow is driven from the Traycer desktop app.

**Where this doc lives:** `docs/orchestrator/traycer-command-wiring.md` — moved here from `docs/infrastructure/`
(commit `32b1b57c`), so it sits beside the command set it describes. `docs/infrastructure/` holds VPS/observability
runbooks and contains **no command files**.

**The one fact everything derives from:** Traycer is a **layer**, not an AI. **Claude Max (Claude Code) is the
engine connected to it** — so the Traycer path is fully tool-capable (shell, MCP, subagents). There is **ONE
tool-capable command set** (the `-fabrik` files under `docs/orchestrator/**`); the old tool-less `-command`
twins were archived (north-star D2, 2026-07-18).

---

## The three moving parts

| Part | Where it lives | Role |
|---|---|---|
| **Command files** (`-fabrik`) | `docs/orchestrator/mega-epic-breakdown/**` · `docs/orchestrator/epic-to-ticket-workflow/**` | The runnable workflow definitions Claude executes. Git-tracked = source of truth. |
| **Skill wrappers** (`SKILL.md`) | `docs/orchestrator/_traycer-skills/**` → installed into **two** skill dirs (see § The doorbell model) | Register the commands under a slash name so they appear in a menu. 13 lines each, **no logic** — a pointer at the canonical `-fabrik` file. |
| **Projection + schema** | `scripts/traycer_mirror.py` · `scripts/epic_order.py` · `docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md` | Turn a disk artifact into a Traycer **card**; order/validate the epic set. |

**Golden rule (D8):** **DISK is the source of truth; the Traycer store is a projection.** A command writes its
artifact to a git-tracked disk path, then *mirrors* it into the Traycer store. Never make the Traycer store the
only copy — a card with no disk file dies with the session.

---

## The doorbell model — why a command is never copied

The single most confusing thing here is that a command *looks* like it exists in three places. It does not. It
exists in **one** place; the other two hold a **doorbell button**.

```
~/.claude/skills/fab-mega-02-decompose/SKILL.md          13 lines  ← the button (a pointer)
~/.traycer/.claude/skills/fab-mega-02-decompose/SKILL.md 13 lines  ← the button (a pointer)
docs/orchestrator/mega-epic-breakdown/
        02-epic-decomposition-fabrik.md                 548 lines  ← THE COMMAND
```

The whole wrapper is frontmatter (`name`, `description`) plus: *"Read the command specification at `<abs path>`.
Follow it exactly as written."* It carries **zero instructions**. Pressing the doorbell doesn't hand anyone a
copy of the house — it sends them to the address.

Three consequences, and they are the point:

- **Editing a `-fabrik.md` file is live immediately.** No re-copy, no re-register, no sync step. There is no
  second copy of the command that can go stale, because there is no second copy at all.
- **The only thing that can break is the address.** Rename or move a `-fabrik.md` and the doorbell rings at a
  house that isn't there — and it fails *silently*: the command runs and reads nothing. Renames must be paired
  with a wrapper update. This is the one integrity check that matters (see § Verify the wire works).
- **Never inline a command body into a wrapper.** That forks it, and the fork is the copy that rots.

### The two skill dirs, and why they differ

| Dir | Surfaces in | Install form | Why |
|---|---|---|---|
| `~/.claude/skills/` | the **engine's** menu (`/fab-…` invocable by Claude) | **symlinks** → `_traycer-skills/<name>/SKILL.md` | Outside Traycer's control, so a link is safe → drift is structurally impossible. |
| `~/.traycer/.claude/skills/` | the **`/traycer` menu** (owner entry point) | **real copies** | Traycer-managed (`SkillSyncService`); symlink tolerance unverified, so don't risk its own dir. |

Symlink at the **file** level (real dir, linked `SKILL.md`) — a loader that walks with `follow_symlinks=False`
would skip a symlinked *directory*, but reads a linked file transparently.

⚠️ **The Traycer dir is the one that can be pruned.** Traycer ships `resources/skills/manifest.json` (its own 14
skills, by `name` + `sha256`) and reconciles that dir on start/upgrade. A manifest keyed by name *suggests*
repair-my-own-entries — which would leave `fab-*` alone — but this is **unverified** (`traycer-host` is an
obfuscated binary). Assume a host **upgrade** may wipe them; recovery is one `cp -r` from `_traycer-skills/`.

### The 17 registered commands (slash name → the file it points at)

**mega-epic-breakdown/** — above-epic portfolio decomposition (4)

| Slash command | Canonical file |
|---|---|
| `/fab-mega-00-trigger` | `00-trigger-mega-epic-fabrik.md` ⟵ *renamed from `00-trigger-fabrik.md`* |
| `/fab-mega-02-decompose` | `02-epic-decomposition-fabrik.md` |
| `/fab-mega-03-expand` | `03-expand-epic-files-fabrik.md` |
| `/fab-mega-04-validate` | `04-cross-epic-validation-fabrik.md` |

**epic-to-ticket-workflow/** — per-epic design → build → deploy (13)

| Slash command | Canonical file |
|---|---|
| `/fab-ettw-00-trigger` | `00-trigger-fabrik.md` |
| `/fab-ettw-01-decisions-lock` | `01-decisions-lock-fabrik.md` |
| `/fab-ettw-01r-decisions-review` | `01R-decisions-review-fabrik.md` |
| `/fab-ettw-02-core-flows` | `02-core-flows-fabrik.md` |
| `/fab-ettw-03-tech-plan` | `03-tech-plan-fabrik.md` |
| `/fab-ettw-04-deploy-plan` | `04-deploy-plan-fabrik.md` |
| `/fab-ettw-05-ticket-outline` | `05-ticket-outline-fabrik.md` |
| `/fab-ettw-06-ticket-breakdown` | `06-ticket-breakdown-fabrik.md` |
| `/fab-ettw-07-execute` | `07-execute-fabrik.md` |
| `/fab-ettw-08-implementation-validation` | `08-implementation-validation-fabrik.md` |
| `/fab-ettw-09-revise-requirements` | `09-revise-requirements-fabrik.md` |
| `/fab-ettw-10-cross-artifact-validation` | `10-cross-artifact-validation-fabrik.md` |
| `/fab-ettw-11-deploy` | `11-deploy-fabrik.md` |

⚠️ Note `01R` — the file is upper-case `R`, the slash name lower-case `01r`. The **frontmatter `name:` is what
resolves the command**, not the directory or the filename; a mismatch makes a command silently un-invokable.

*(Mega numbering skips `01` — no such command ever existed. Mega `05` is **retired**, not merely unused: its
tombstone is `_retired/05-dispatch-epic-tickets-fabrik.RETIRED.md`, its ticket-set integrity gate was absorbed
into `04` via `epic_order.py --check`, and dispatch is now the cockpit epic-card click / the driver's phase
queue. No command may reference a live `05` (checklist 84f).)*

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
2. **Install the 17 wrappers into both skill dirs** (per § The doorbell model — link one, copy the other):

   ```bash
   SRC=/opt/fabrik/docs/orchestrator/_traycer-skills

   # engine menu — symlinks, cannot drift
   for d in "$SRC"/*/; do n=$(basename "$d")
     mkdir -p ~/.claude/skills/"$n"
     ln -sfn "$SRC/$n/SKILL.md" ~/.claude/skills/"$n"/SKILL.md
   done

   # /traycer menu — real copies (Traycer-managed dir; re-run after a host upgrade)
   cp -r "$SRC"/fab-* ~/.traycer/.claude/skills/
   ```

   `~/.traycer/.claude/skills/` is the Traycer-managed dir for the Claude harness — where its own
   `traycer-epic-brief`, `traycer-execute`, … live; one such dir per harness (`.claude` / `.opencode` /
   `.codex` / `.agents`). Installing to only `~/.claude/skills/` makes the commands invocable but leaves them
   **absent from the `/traycer` menu**. Wrapper *sources* stay in the repo — both dirs are installs, never
   the master.
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
 └─ per epic: epic-to-ticket-workflow  00-trigger(consume) → 01-decisions-lock → 01R-decisions-review
              ⟨GATE 1: operator confirm flips DRAFT → LOCKED⟩ → 02-core-flows → 03-tech-plan → 04-deploy-plan
              → 05-ticket-outline → 06-ticket-breakdown → tickets → 07-execute
              → 08 / 10 armed review (review_rubric.py), 09 revises on drift → 11-deploy
              ⟨GATE 2: manual `fabrik apply`⟩
```

- Card **status** moves `0 → 1 → 2` as an epic/ticket progresses; the cockpit shows the live board.
- **Single epic?** Skip mega; enter via `/fabrik-spec` (feature) or the ettw `00-trigger` directly.
- **Two human gates only** (decomposition-in, deploy-out); everything between is agent-run — but the semantic
  reviews are *maximally-enforced, not guaranteed* (see the north-star § Enforcement Model / spec § L1).

---

## Verify the wire works

```bash
# ── shim integrity: the 5 checks. Run after ANY rename/move under docs/orchestrator/ ──
SRC=/opt/fabrik/docs/orchestrator/_traycer-skills
for d in "$SRC"/*/; do n=$(basename "$d")
  # 3. THE CRITICAL ONE — does the address still exist? (a rename fails silently otherwise)
  t=$(grep -o '/opt/fabrik/docs/[^ `]*\.md' "$d/SKILL.md" | head -1)
  [ -f "$t" ] || echo "BROKEN ADDRESS  $n -> ${t:-<none>}"
  # 5. frontmatter name must equal dir name, else un-invokable under the expected name
  [ "$(grep -m1 '^name:' "$d/SKILL.md" | sed 's/^name:[[:space:]]*//')" = "$n" ] || echo "NAME MISMATCH  $n"
  # 1. traycer-dir copy in sync (the ~/.claude one is a symlink — cannot drift)
  cmp -s "$d/SKILL.md" ~/.traycer/.claude/skills/"$n"/SKILL.md || echo "STALE COPY     $n"
done
# 2. orphans: installed fab-* with no repo source · 4. stray files besides SKILL.md
ls -d ~/.traycer/.claude/skills/fab-*/ | while read b; do [ -d "$SRC/$(basename $b)" ] || echo "ORPHAN $b"; done
find "$SRC" -type f ! -name SKILL.md
# silence from all of the above = wired correctly

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
