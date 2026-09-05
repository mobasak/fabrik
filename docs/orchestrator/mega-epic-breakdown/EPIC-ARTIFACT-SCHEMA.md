<!-- ⚠️ FABRIK ORCHESTRATOR — the ONE data model for epic artifacts (D10).
     Cited by 02/03/04 and by scripts/epic_order.py. A single typed header
     serves TWO consumers: (a) ordering + assignment-in-code, (b) cross-epic
     validation. Keep them in lockstep. -->

# Epic Artifact Schema

Every epic file `03-expand-epic-files-fabrik` writes to
`docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md` MUST open with this
frontmatter block, then the existing prose body (`## Epic N — [Name]` …) unchanged:

```yaml
---
kind: story                     # plain metadata — no current reader; retained for
                                 # compatibility (would have driven a renderer that
                                 # was never built)
title: "Epic 1 — hello-api"     # exact "Epic N — [Name]" (em-dash) — read by
                                 # epic_order.py's title-shape check
status: 0                       # 0 TODO · 1 in-progress · 2 done — the epic's own
                                 # status, flipped by its owning agent (1 on start,
                                 # 2 on merge); loaded by epic_order.py, not
                                 # asserted by it today
epic_n: 1                       # integer — the graph-node id
slug: hello-api
depends_on: []                  # hard deps, epic numbers → phased ordering
parallel_with: []               # co-phase peers → ordering + disjointness proof
owned_paths: ["src/hello_api/**"]  # the concurrency contract (carried from 02)
owner: ""                       # named agent — "" means unassigned; set by --assign
scaffold: python-api            # informational (mirrors the ticket Metadata)
port: 8099
target_vps: vps1
---
```

## Why one header, two consumers (D10)

| Consumer | Reads | Purpose |
|---|---|---|
| `scripts/epic_order.py` | `epic_n`, `depends_on`, `parallel_with`, `owned_paths`, `title`, `owner` | integrity (was 05 Step 1) + phased order (was 05 Step 2) + assignment — **code, not prose (R8)** |
| `04-cross-epic-validation-fabrik` | all of the above | cross-epic consistency, run over the typed fields |

## Rules

- **`kind`** is plain metadata — no current consumer reads or enforces it (retained for compatibility; it would have distinguished artifact types for a renderer that was never built). Convention only: `story` for epics, `spec` for the infra-decisions doc, `review` for a `04` report.
- **`owned_paths`** is the load-bearing concurrency contract — parallel epics MUST have disjoint globs, and at most one may own migrations (`alembic/versions/**`, `db/schema.sql`). `epic_order.py --check` proves this.
- **`owner`** is a plain string — the named agent working the epic; `""` means unassigned. `epic_order.py --assign <a,b,c>` sets it deterministically (round-robin per phase, `epic_n` order); `--check --owners <a,b,c>` flags any epic whose owner is missing or outside that set.
- The frontmatter is **flat**: scalars, or an inline `[a, b]` list (preferred). A multi-line block list (`key:` alone, then `  - item` lines) is also accepted, but ONLY for the three declared list fields — `depends_on`, `parallel_with`, `owned_paths`; the same shape under any other field is a malformed-value finding, never silently promoted to a list. An unquoted trailing ` # comment` is stripped from every value (a `#` inside quotes is part of the value). All of it parses without a PyYAML dependency and stays diffable.
- **Disk is source of truth (D8).** `docs/development/epics/*.md` is the only copy — never hand-authored elsewhere, never mirrored.

## The hub script (project-agnostic)

```bash
# ordering + integrity over the current project's epics (an orchestrating agent
# calls this before dispatch — no cockpit or driver was ever built)
python /opt/fabrik/scripts/epic_order.py --check --expected-count <N>   # integrity gate
python /opt/fabrik/scripts/epic_order.py --check --owners <a,b,c>       # owner-set gate
python /opt/fabrik/scripts/epic_order.py --assign <a,b,c>               # round-robin owner: per phase
python /opt/fabrik/scripts/epic_order.py --json                         # phased order → the orchestrating agent's dispatch
```
