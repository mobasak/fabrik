# Plan: Three superpowers-skill adoptions (watched-fail-first · repo-identity preamble · end-of-branch menu)

Status: CONVERGED
Date: 2026-08-07
Source: operator-approved comparison of the superpowers plugin skills vs the fabrik command corpus
(this conversation; skills read from `~/.claude/plugins/cache/claude-plugins-official/superpowers/6.1.1/skills/`).

## Context Ledger

- **Decision (settled):** adopt exactly three nuggets; explicitly REJECT superpowers'
  Critical/Important/Minor triage (our FIXED-or-REFUTED ban on a third state is stronger).
- **A1 — watched-fail-first:** superpowers:test-driven-development's edge ("If you didn't watch the
  test fail, you don't know if it tests the right thing") is sharper than our Behavior Contract
  sentence at `CLAUDE.md:46`, which mandates coverage + "TDD for the risky ones" but not
  fail-first sequencing for ordinary behaviors. Live motivation: T08 shipped two guards whose tests
  never failed on revert (caught only by the Opus mutation protocol, 2026-08-07).
- **A2 — repo-identity preamble:** superpowers:using-git-worktrees Step 0 (`git-dir` vs
  `git-common-dir` + the submodule guard). Live motivation: three wrong-cwd git mutations this
  session + T04's worktree mode mis-dispatch (fixed per-command there; this generalizes it as a
  fragment). Include mechanics exist: `commands/assemble_commands.py:306` substitutes
  `{{include:NAME}}` from `commands/_fragments/NAME.md`; catchup already includes a fragment at
  `commands/_sources/fabrik-catchup.md:29`, upstream at `commands/_sources/fabrik-upstream.md:58`.
- **A3 — end-of-branch menu:** superpowers:finishing-a-development-branch's 4-option integration
  menu (merge locally / push+PR / keep / discard) + merge-verify-THEN-cleanup ordering. Our
  `CLAUDE.md:51` § EXIT covers commit + operator-gated push but has no structured hand-off for
  ad-hoc NON-plan branch/worktree work (plan work has §Finish).
- **Synced-file legality:** `CLAUDE.md` and `.windsurf/rules/**` are HUB-canonical — this repo IS
  the distribution source; edits here are the sanctioned route (HARD STOPS synced-file row).
- **Never-route class:** CLAUDE.md + rule packs + `commands/` are NO-POOL surfaces; all work in
  this plan is orchestrator/native-authored.

## Phase A — Governance prose (A1 + A3)

1. `CLAUDE.md:46` (Completion Contract §1, Behavior Contract sentence): append the
   watched-fail-first clause — every non-trivial behavior's test is **seen red first** (fail-first),
   and a test written after the code counts only once **proven red-on-revert**; "it passes" is not
   evidence the test tests anything.
2. `.windsurf/rules/core/45-testing-strategy.md` § Core Philosophy (:16-20): add the matching
   mandate bullet; § Banned Patterns table (:167+): add row "A test never seen red (written
   after the code, no red-on-revert proof) | Watch it fail first, or neuter the fix/feature and
   prove the test goes red".
3. `CLAUDE.md:51` § EXIT: append the ad-hoc end-of-branch clause — when NON-plan work finishes on
   a branch/worktree, present exactly: merge to base locally / push + PR / keep as-is / discard;
   ordering is merge → verify (tests on the merged result) → only then cleanup worktree → delete
   branch; plan-set work keeps its own §Finish (archive/lock) unchanged.

Gate A: `python scripts/final_gate.py --lean --check --json` (expect only pre-existing
sibling-owned failures) + `grep -c "red-on-revert" CLAUDE.md .windsurf/rules/core/45-testing-strategy.md`
each ≥1 + `grep -c "merge-verify" CLAUDE.md` OR the menu options greppable.
Boundary: `/fabrik-review` over the Phase A diff (native-only — synced governance surface).

## Phase B — Repo-identity fragment (A2)

1. Write `commands/_fragments/repo-identity.md` (~10 lines): resolve `git rev-parse --show-toplevel`
   + `--git-common-dir`; `GIT_DIR != GIT_COMMON` = linked worktree (identity = the COMMON checkout's
   repo — for mode selection, a `/opt/fabrik` worktree IS hub); submodule guard
   (`git rev-parse --show-superproject-working-tree` non-empty → treat as normal repo of the
   superproject, never a worktree); never mutate git state without pinning cwd (`git -C <toplevel>`).
2. Insert `{{include:repo-identity}}` into `commands/_sources/fabrik-catchup.md` (Phase 0 head,
   near :29) and `commands/_sources/fabrik-upstream.md` (mode-selection region, near :58's existing
   include) — placement must complement, not contradict, upstream's existing repo-identity text
   (T04 round-2 F4): the fragment CENTRALIZES the mechanics; the command keeps its mode semantics.
3. Render from master (`python commands/assemble_commands.py`) + `--check` clean; verify both
   rendered commands and skills carry the preamble.

Gate B: `python commands/assemble_commands.py --check` → check OK; `grep -l "show-superproject-working-tree" ~/.claude/commands/fabrik-catchup.md ~/.claude/commands/fabrik-upstream.md` → both.
Boundary: `/fabrik-review` over the Phase B diff.

## Behavior Contract

- **Given** `CLAUDE.md` §1, **When** an agent reads the Behavior Contract, **Then** it mandates
  fail-first for non-trivial behaviors and red-on-revert proof for after-the-fact tests (CLAUDE.md:46).
- **Given** `45-testing-strategy.md`, **When** consulted, **Then** Core Philosophy carries the same
  mandate and Banned Patterns bans never-seen-red tests (.windsurf/rules/core/45-testing-strategy.md:16,167).
- **Given** the rendered `fabrik-catchup` and `fabrik-upstream` commands, **When** installed, **Then**
  both carry the repo-identity preamble incl. the submodule guard (commands/assemble_commands.py:306).
- **Given** `CLAUDE.md` § EXIT, **When** ad-hoc non-plan branch work finishes, **Then** the four
  integration options and merge-verify-then-cleanup ordering are stated (CLAUDE.md:51).

## Subagents & parallelism

None dispatched — never-route surfaces end-to-end; phases are sequential (A then B); the
phase-boundary `/fabrik-review`s run native-only (synced governance + command sources), consistent
with `62-using-subagents.md` (a pool layer on a ~40-line governance diff has no gradeable unit).

## Evidence

### Phase A (planning-time grounding)

- `CLAUDE.md:46` — current sentence ends "…lean-but-complete, NOT 100%-coverage dogma (skip docs-only)." (the append point).
- `CLAUDE.md:51` — § EXIT ends "**Push stays operator-authorized** (unless said this turn)." (the append point).
- `.windsurf/rules/core/45-testing-strategy.md:19` — Behavior Contract bullet present ("…ensure every behavior has a test that would fail if that behavior regressed" — the regression-direction idea exists; the FAIL-FIRST sequencing does not); `:167` Banned Patterns table.

```
$ grep -n "red-on-revert\|revert" .windsurf/rules/core/45-testing-strategy.md
(no output — the mandate does not exist yet in the pack; T08's ticket cited the pack for the
discipline, but the words are absent — A1 closes exactly this gap)
```

### Phase B (planning-time grounding)

- `commands/assemble_commands.py:306` — `out.append("{{include:%s}}" % frag)` (the include mechanism).
- `commands/_sources/fabrik-catchup.md:29` + `commands/_sources/fabrik-upstream.md:58` — existing
  `{{include:grounding-artifact}}` markers prove both sources already consume fragments.

```
$ ls commands/_fragments/
autonomy-run.md  grounding-artifact.md  grounding-code.md  grounding-research.md
grounding-rules-cite.md  grounding-rules.md  injection.md  questionbar.md
subagents-core.md  term-coverage.md  term-edit.md
```

## Self-audit

- Every step grounded in a real `path:line` read THIS session (no memory citations).
- Scope honest: ~40 lines, 6 files, zero code — the only executable surface is the assembler render.
- The rejected adoption (severity triage) is recorded so a future session doesn't re-import it.
- Risk: A3's menu must not contradict the plan-set §Finish — scoped to NON-plan work explicitly.
- Risk: B's fragment vs upstream's existing repo-identity prose — placement rule stated in B.2.

## Pass Ledger (plan-review)

| Pass | axes | edits | md5 (start → end) |
|---:|---|---:|---|
| 1 | all citations re-executed + contradiction probes + both plan gates | 1 (pack line :18→:19 + regression-vs-fail-first distinction) | 1a2d8db0… → c45fb777… |
| 2 | full re-verify (path existence, scope clauses, rejected-adoption record) + gates rc=0 (`check_convergence`, `check_plan_quality` via -m) | **0** | c45fb777… → c45fb777… ✓ CONVERGED |

Gate at flip: `final_gate.py --check --json` → 43 passed / 1 failed — the single failure is the
concurrent sibling session's seo spec↔project DB-name drift (their staged files, disclosed in
`docs/development/reviews/2026-08-07-orchestrator-work-review.md`); every check touching this
plan's surfaces is green.

## Residuals / rollback

- Residual: superpowers' TDD "delete code written before the test" extreme is NOT adopted
  (deliberate — our red-on-revert proof achieves the spirit without the churn).
- Rollback: all six files are git-versioned; revert = `git revert` of the two phase commits;
  fragment removal requires a re-render (from master only).
