# Plan 1 — Routine task-end push (2026-08-09)

Status: EXECUTED 2026-08-09 (f5c71bde → cef3be75 → adjudication fixes)
Whole-plan review: docs/development/reviews/2026-08-09-plan-1-routine-push-review.md

## Goal

Operator directive: agents commit AND PUSH their own work at task end, everywhere (hub + all projects),
without being told. Push is a BACKUP step — a push deploys nothing (`fabrik apply`/`redeploy` are the
only deploy actions). `--force` to shared branches stays banned forever. The Stop hook enforces the new
law (4th cause: committed-but-unpushed), fail-open in every indeterminate case so no session is ever
trapped by a missing remote or an offline box.

**Rejection ladder (PROBE-VERIFIED in a two-clone sandbox, review pass 1):** `git push` → rejected →
tree DIRTY (sibling WIP present — the hub's normal state)? **defer + report** ("push deferred:
divergent + dirty shared tree; wip-net protects; retries next task end") — `pull --rebase` on a dirty
tree is stranding-capable (probe left a mid-rebase state) and autostash on a shared tree is the
pre-commit-stash incident class, both banned. Tree CLEAN → `git pull --rebase` (rewrites only OWN
unpushed commits — probe-proven: push OK, linear history) → push; rebase conflict →
`git rebase --abort` → report. `merge --ff-only` is NOT the remedy (probe-proven: "Diverging branches
can't be fast-forwarded" whenever both agents are ahead).

## Context Ledger

- **ACTIVE packs consulted:** `core/10-python.md` (hook edit), `core/45-testing-strategy.md`
  (red-first). Others touch no surface here (prose governance + one hook cause).
- **agents-fabrik.md / agents-fabrik-core.md:** "commit → push → redeploy" already push-consistent;
  deploy remains hub-triggered — no edits needed there.
- **Grounded sweep (all opened this turn):**
  - Hub `CLAUDE.md:71` § EXIT ("Push stays operator-authorized (unless said this turn)" + the ad-hoc
    branch menu "push (operator-gated, as ever)") and `:84` HARD-STOP row ("`git push` (unless user
    said so this turn)").
  - `templates/governance/CLAUDE.md:51` + `:64` — same two surfaces, project side.
  - `AGENTS-compact.md:37` + `:131` — mirrors.
  - `.windsurfrules:35` + `:40` — BONUS pre-existing contradiction: still bans COMMIT without say-so
    (predates the commit-required law); bring to commit-AND-push-required.
  - `.claude/hooks/final_gate_stop.py:743` — block-message text "Push stays operator-authorized.";
    plus the new 4th cause + counter slot.
  - `commands/_sources/fabrik-execute-plan.md:935` — §Finish menu: push "only if the user said so this
    turn" → push becomes the DEFAULT disposition for merged work.
  - Redeploy rows (`CLAUDE.md:91`, template `:71`, `AGENTS-compact:124`, `.windsurfrules:42`) stay —
    commit→push→redeploy is still true.
  - Counter file format: 3-slot "g,c,s" (`_read_counters`) — extend to 4-slot "g,c,s,p",
    backward-compatible reads.
- **Risk constraints (encode in the hook):** the push cause fires ONLY when the current branch HAS an
  upstream AND `rev-list @{upstream}..HEAD` > 0 AND the remote is reachable-irrelevant (the hook only
  counts — it never networks; ahead-count needs no network). No upstream / detached HEAD / any git
  error → indeterminate → allow. Dispatcher worktree branches have no upstream → never blocked
  mid-plan; merged master (with upstream) is what the law binds.
- **shape.\*/spec:** n/a. **fabrik-lib:** n/a.

## File Scope (owned paths)

- `CLAUDE.md`
- `templates/governance/CLAUDE.md`
- `AGENTS-compact.md`
- `.windsurfrules`
- `.claude/hooks/final_gate_stop.py`
- `tests/test_final_gate_stop_hook.py`
- `commands/_sources/fabrik-execute-plan.md`

Disjoint from active plans (none running).

## Phase A — Stop-hook 4th cause (tests red-first)

1. Red-first tests (`tests/test_final_gate_stop_hook.py`, watch fail before the hook change):
   see `## Behavior Contract` rows 1–4.
2. Hook: `_ahead_of_upstream(root) -> int | None` (None = indeterminate: no upstream/detached/any
   error; count via `git rev-list --count @{upstream}..HEAD` — no network). New cause in `main()`
   after the commit cause: ahead > 0 → block "committed work is UNPUSHED — push YOUR work now.
   Rejected? dirty tree → defer (wip-net protects) · clean → `git pull --rebase` then push ·
   conflict → `git rebase --abort` + report · NEVER --force" (same ladder as § EXIT — one law, two
   surfaces). 4th counter slot "g,c,s,p"
   (`_read_counters` backward-compatible with 3-slot files), warn-through cap 3, reset-when-cause-false
   (the stranded-counter regression class from the guard's own history).
3. Update the `:743` block-message text (commit cause) to the new law's wording.
4. **Gate:** full stop-hook suite green; `ruff` clean.

## Phase B — Governance prose sweep + corpus

1. Hub `CLAUDE.md` § EXIT: "Gate green → COMMIT your own work NOW … then **PUSH it** (`git push`; on
   rejection apply the ladder: dirty tree → defer + report (wip-net protects) · clean tree →
   `git pull --rebase` then push · conflict → `git rebase --abort` + report · never `--force`). An
   unpushed task is an OFF-BOX-UNPROTECTED task." Ad-hoc menu: push becomes part of the default merge
   disposition ("merge to base locally **then push base**"), menu keeps keep/discard as the
   operator-choice residue.
2. HARD-STOP row swap (hub + template + AGENTS-compact): ban narrows to
   `git push --force`/`-f` to any shared branch · pushing a branch you don't own · publishing
   secrets — plain `git push` of OWN committed work is REQUIRED at task end (the wip_backup
   `refs/wip/*` force-push is the sanctioned backup-ref exception).
3. `templates/governance/CLAUDE.md` + `AGENTS-compact.md`: mirror both edits.
4. `.windsurfrules`: replace the stale "No commit/push unless user said so" with the
   commit-AND-push-required law (6-line block untouched — already updated).
5. `commands/_sources/fabrik-execute-plan.md:935`: §Finish — merged work pushes by DEFAULT; re-render
   corpus + `--check`.
6. **Gate:** `final_gate.py --check --json` → no NEW failures; corpus check OK.
   §Finish extras: update memory `feedback_commit_push_backup_discipline` (proposal → EXECUTED;
   user-level file, outside File Scope by design), CHANGELOG entry, whole-diff `/fabrik-review`
   (native, NO-POOL surface), archive plan + EXECUTED flip with receipt — **and this plan's own final
   commit PUSHES (the law binds its author; the hub's unpushed backlog goes off-box here, per the
   operator's standing directive)**.

## Behavior Contract

- **Given** a tmp repo with a bare origin and one commit ahead of upstream, **When** the Stop hook runs with a clean tree, **Then** it BLOCKS naming the unpushed work. [Phase A]
- **Given** the same repo after `git push`, **When** the Stop hook runs, **Then** it allows and the p-slot resets. [Phase A]
- **Given** a repo with NO upstream (or detached HEAD), **When** the Stop hook runs, **Then** it allows — indeterminate never blocks. [Phase A]
- **Given** a legacy 3-slot counter file "1,2,0", **When** `_read_counters` reads it, **Then** it returns (1,2,0,0) and writes round-trip 4-slot. [Phase A]
- **Given** the rendered corpus after Phase B, **When** `assemble_commands.py --check` runs, **Then** it reports OK and the §Finish menu names push as the default disposition. [Phase B]
- **Mocked:** tmp repos + bare remotes only; the hook's git calls run real.

## Pass Ledger (plan-review convergence)

| Pass | axes re-grounded | edits | plan md5 (start → end) |
|-----:|---|---:|---|
| 1 | citations (all opened this turn) · rejection-remedy EXECUTED in a two-clone sandbox (ff-only disproven, rebase proven clean-tree, dirty-tree stranding observed) · self-binding §Finish push | 3 | 1428e8e7… → (superseded) |
| 2 | full re-read · internal A↔B remedy consistency (Self-audit (b) violation caught) | 1 | (superseded) |
| 3 | all axes fresh — **0 content edits**; this ledger row-write + Status flip are the only changes after verification | 0 | recorded at flip |

## Subagents & parallelism

A → B sequential (B's prose cites A's shipped wording). Native-only review (NO-POOL: hooks +
governance), declared in the commit.

## Evidence

**Planning-time grounding:** every sweep citation opened this turn (`CLAUDE.md:71,84`, template
`:51,64`, `AGENTS-compact.md:37,131`, `.windsurfrules:35,40`, `final_gate_stop.py:743`,
`fabrik-execute-plan.md:935`). The rejection remedy was EXECUTED, not assumed (two-clone sandbox,
review pass 1):

```
$ git push -q               # clone b, diverged from a
 ! [rejected]  master -> master
$ git merge --ff-only origin/master
hint: Diverging branches can't be fast-forwarded, you need to either:   # ff-only DISPROVEN
$ git pull -q --rebase && git push -q && echo "PUSH OK after rebase"
PUSH OK after rebase                                                    # clean-tree remedy PROVEN
# dirty-tree probe: pull --rebase left a mid-rebase detached state → dirty-tree leg = defer
```

**Execution evidence:**

```
Phase A red-first: 2 failed (unpushed-blocks, legacy-counter) -> hook change -> 65 passed
Phase B: corpus check OK -- installed commands + skills match rendered sources
Adjudication: 7 findings (5 fixed incl. --rebase=merges ladder + p-slot strand w/ multi-stop
red-first test; 2 accepted residuals) + 1 live FP fixed (1df51065); final suite 67 passed
Live self-demonstration: the 4th cause's first firing was on its own author; git push cleared it
(cef3be75..003091e9), and the block message already spoke the new law.
$ python scripts/final_gate.py --check --json
{"status": "success", "tier": 2, "passed": 45, "failed": 0}
```

## Self-audit

- (a) Every directive maps: push-required → A2/B1-4; don't-chase-source-control → the law + the hook
  cause; fleet-wide → template/compact/windsurfrules mirrors (sync distributes).
- (b) Cross-phase: A's block-message wording == B1's § EXIT wording (one law, two surfaces).

## Residual unknowns

- The ~16 currently-uncommitted fabrik files are SIBLING-owned live WIP — snapshot-protected
  (refs/wip), drain via their owners' task-ends under the new law; never bundled by this plan.
- Older memories stating "push operator-gated" (e.g. quota/backup notes) are superseded by the
  memory update in §Finish; a full memory sweep is follow-up if a stale one resurfaces.
