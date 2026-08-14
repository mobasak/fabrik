# Sync-excluded repo audit — 2026-08-15

**Why:** fabrik-lib reported an orphaned-governance shape (a `refresh-governance.sh` branch that
could never fire, because the hub had moved `CLAUDE.md` out of `GOVERNANCE_FILES`) and asked
whether other sync-excluded repos carry the same defect. Operator-approved audit.

## Scope — grounded, not assumed

The exclusion set is `exclude_folders` in `scripts/sync_enforcement_to_projects.py:765-777`
(discovery is `is_dir()` over `/opt`, minus that set, minus `_*`/`.*`/`fabrik` itself):

| Excluded name | Status on the box | Audit verdict |
|---|---|---|
| `fabrik-lib` | live git repo | **AUDITED — clean** (below) |
| `fabrik-libs` | ABSENT (legacy name, kept for safety) | nothing to audit |
| `mt-router` | ABSENT | nothing to audit |
| `archived` | not a repo; holds ~30 archived projects | out of scope by definition (archived) |
| `fabrik-mail` | data store, not a project | out of scope (mailbox root) |
| `containerd`, `google`, `logs` | system dirs | out of scope |

**There is exactly ONE live sync-excluded repo: `fabrik-lib`.** The reported class therefore
cannot be widespread — it had a population of one.

## fabrik-lib — clean

- The dead `CLAUDE.md` branch in `/opt/fabrik-lib/scripts/refresh-governance.sh` is **documented in place**
  (`⚠ DEAD CODE as of 2026-08-12 — the hub REMOVED "CLAUDE.md" from GOVERNANCE_FILES`), not
  silently left to rot. Their agent handled it as reported.
- All five UNIVERSAL governance anchors are present in its `CLAUDE.md`: commit-at-task-end ·
  push-at-task-end · explicit-pathspecs · provenance-trailers · no-force-push.
- Its own `/opt/fabrik-lib/scripts/enforcement/check_governance_drift.py` exists and is wired into
  its `final_gate_fabrik_lib.py` — so future hub drift surfaces there automatically.

## The reverse question (the valuable half)

"Is governance actually ARRIVING everywhere it should?" — swept all 43 `/opt` git repos:

- **repos with no `.fabrik/synced.lock`: 0**
- **repos missing files their own lock lists: 0**
- **8282 delivered synced files compared byte-for-byte against the hub.**

### Three apparent "forks" — all FALSE POSITIVES of the comparison, not real drift

Recorded because the next person to run this sweep will hit the same traps:

1. **`CLAUDE.md` differs in 41 repos** — by design. Projects receive
   `templates/governance/CLAUDE.md` (GOVERNANCE_TEMPLATES), never the hub's own contract.
   Compared against the template: **identical**.
2. **`libs/subagents/{agent,ledger,pg_ledger}.py` differ in 41 repos** — the HUB worktree was
   dirty with a sibling session's in-flight edits. Compared against hub `HEAD`: **identical**.
   *A sweep that compares against a live worktree measures uncommitted work, not drift.*
3. **`scripts/sync_extensions.sh` differs in 41 repos** — sourced from
   `templates/scaffold/scripts/` (RUN_SCRIPTS), not from `scripts/` at the hub root. Compared
   against its real source: **identical**.

**Net: zero forks fleet-wide.** Every project copy matches its true source.

## Recommendation

No action. The class fabrik-lib found is closed (population 1, remediated), and the delivery
mechanism is verifiably intact. If a future audit re-runs this, resolve each file to its SOURCE
via the manifest (`GOVERNANCE_FILES` / `GOVERNANCE_TEMPLATES` / `REFERENCE_DOCS` / `RUN_SCRIPTS`)
and compare against hub `HEAD`, never the worktree.
