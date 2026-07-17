<!-- ⚠️ FABRIK ORCHESTRATOR — the ONE data model for epic artifacts (D10).
     Cited by 02/03/04 and by scripts/epic_order.py + scripts/traycer_mirror.py.
     A single typed header serves THREE consumers: (a) ordering-in-code, (b) the
     Traycer/cockpit renderer, (c) cross-epic validation. Keep them in lockstep. -->

# Epic Artifact Schema (Traycer-ready)

Every epic file `03-expand-epic-files-fabrik` writes to
`docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md` MUST open with this
frontmatter block, then the existing prose body (`## Epic N — [Name]` …) unchanged:

```yaml
---
kind: story                     # Traycer artifact kind → renders as an epic CARD
title: "Epic 1 — hello-api"     # exact "Epic N — [Name]" (em-dash) — the card label
status: 0                       # 0 TODO · 1 in-progress · 2 done → Traycer pills
epic_n: 1                       # integer — the graph-node id
slug: hello-api
depends_on: []                  # hard deps, epic numbers → phased ordering
parallel_with: []               # co-phase peers → ordering + disjointness proof
owned_paths: ["src/hello_api/**"]  # the concurrency contract (carried from 02)
scaffold: python-api            # informational (mirrors the ticket Metadata)
port: 8099
target_vps: vps1
---
```

## Why one header, three consumers (D10)

| Consumer | Reads | Purpose |
|---|---|---|
| `scripts/epic_order.py` | `epic_n`, `depends_on`, `parallel_with`, `owned_paths`, `title` | integrity (was 05 Step 1) + phased order (was 05 Step 2) — **code, not prose (R8)** |
| `scripts/traycer_mirror.py` → Traycer/cockpit GUI | `kind`, `title`, `status` | renders the epic as a card; `status` drives the pill |
| `04-cross-epic-validation-fabrik` | all of the above | cross-epic consistency, run over the typed fields |

## Rules

- **`kind: story`** for epics (renders in Traycer today). Infra-decisions spec = `kind: spec`; a `04` report = `kind: review`.
- **`owned_paths`** is the load-bearing concurrency contract — parallel epics MUST have disjoint globs, and at most one may own migrations (`alembic/versions/**`, `db/schema.sql`). `epic_order.py --check` proves this.
- The frontmatter is **flat** (scalars + inline `[a, b]` lists) so it parses without a PyYAML dependency and stays diffable.
- **Disk is source of truth (D8).** The Traycer-store copy is a *projection* written by `traycer_mirror.py`, only when `$TRAYCER_EPIC_ID` is set — never hand-authored, never the master.

## The two scripts (hub, project-agnostic)

```bash
# ordering + integrity over the current project's epics (cockpit/driver call this)
python /opt/fabrik/scripts/epic_order.py --check --expected-count <N>   # integrity gate
python /opt/fabrik/scripts/epic_order.py --json                         # phased order → cockpit/driver

# mirror a disk artifact into the Traycer store (no-op when TRAYCER_EPIC_ID unset)
python /opt/fabrik/scripts/traycer_mirror.py --src <file> --name epic-<n> --kind story \
       --title "Epic <n> — <Name>" --status 0 --embed
```
