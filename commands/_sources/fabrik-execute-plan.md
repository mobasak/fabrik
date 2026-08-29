---
description: Execute a pre-approved implementation plan autonomously — phase-sequenced with code reviews between phases; a dated plan-SET directory (spine + T## tickets) instead runs DISPATCHER mode over the whole Board. Supersedes superpowers:executing-plans + superpowers:subagent-driven-development. TRIGGER — EN: "execute this plan", "run the approved plan phase by phase"; TR: "bu planı uygula", "onaylı planı adım adım çalıştır" — fires once a plan is APPROVED and ready to build. SKIP: authoring/converging the plan (→ /fabrik-plan-after-chat, /fabrik-plan-review) or standalone test authoring (→ /fabrik-generate-tests). Stage: 4-build.
argument-hint: "<path to plan file>"
---

# Autonomous Plan Executor

You are executing the plan at `$ARGUMENTS`. The user has pre-approved this plan — it IS the approval. The plan and its design spec together govern this execution — `superpowers:subagent-driven-development` and `superpowers:executing-plans` are superseded by this command when invoked via `/fabrik-execute-plan`.

## Run record — open it FIRST (this is the command that gets abandoned mid-flight)

Before step 0, read the plan's phase count and open the record — `--phases` is **the plan's own phase
count** (dispatcher mode: the Board's ticket count), not a fixed number:

```bash
python3 scripts/command_run.py start --command fabrik-execute-plan --phases <plan's phases> \
  --terminal "every phase EXECUTED + its /fabrik-review round clean"
```

`step --phase <N> --title "<the plan's phase title>"` on entering each phase. **The `/fabrik-review` at a
phase boundary opens its OWN nested record and restores this one when it closes** — so a green phase gate
never reads as "the plan is done" — and every close NAMES its own run, so a retried `done` from the
nested review can never end the plan by accident (it is refused). Close this run with
`done --command fabrik-execute-plan --evidence "<the phases + their review verdicts>" --feedback "<what you filed, to whom | none — surfaces exercised>"` only when the
LAST phase is EXECUTED; a real halt is
`blocked --command fabrik-execute-plan --reason "…" --feedback "<what you filed, to whom | none — surfaces exercised>"` naming one of the
three sanctioned BLOCKED cases (3 consecutive same-test failures · missing infra · unresolvable spec
contradiction). **Open the `RUN:` line on every reply until the run closes** — the FINAL OUTPUT block is a
TASK terminator, and the record is what proves the task is actually over.

## Before You Start

0. **Shape detection — which mode runs.** If `$ARGUMENTS` is a dated plan DIRECTORY
   (`docs/development/plans/YYYY-MM-DD-plan-<slug>/`), or a spine (`## Ticket Board` present), or any
   file inside a plan-set directory (resolve to the parent), this run executes in **DISPATCHER MODE**
   (§ Dispatcher Mode below): the plan unit is the WHOLE SET — read the spine + every
   `T##[a-z]?-<slug>.md` ticket, and the dispatcher contract overrides the sections it names.
   **Corroborate before committing to the mode:** a real set has the dated directory + a same-stem
   spine + ≥1 `T##` ticket file — a lone `## Ticket Board` string in a monolith's prose with no
   ticket files is NOT a set (run phase mode and report the anomaly). A
   monolith plan file runs the phase mode below verbatim.
1. Read the plan file fully.
2. Read `agents-fabrik.md` — the canonical infra + codebase map (`AGENTS.md` is a stub).
3. Run `python scripts/select_rules.py` and read **every ACTIVE pack**.
4. Read the design spec the plan references (usually linked at the top or in `docs/superpowers/specs/`).
5. Read `AFCL.md` if it exists — known friction points.
6. Identify all phases, their dependency order, and the Subagent Mandates table (in the design spec).
7. **Acquire the scope lock (this is what lets several scoped runs share one project, AND what makes a run
   resumable after a crash / disconnect / quota-hit).** Read the plan's `## File Scope (owned paths)`. Scan
   `.fabrik/plan-locks/*.json` for any lock with `status:"active"` whose paths overlap yours, and resolve:
   - **Your OWN plan's lock (same plan-id) left `active` by an interrupted / crashed / quota-killed prior
     run → RESUME is permitted** (check `.fabrik/plan-locks/<plan-id>.json` directly by id, not only via the
     overlap scan). The operator's re-invocation IS the authorization that the prior session is dead — running
     two sessions of one plan at once is the operator's to avoid, exactly like freeing a sibling's lock.
     Keep the lock. Then split by what the tree actually shows:
     - **CLEAN-BOUNDARY resume (the normal case — per-phase commits make it so):** owned paths clean AND the
       first unmarked phase has no landed commits → continue from the last `✅ EXECUTED` phase per §Plan
       Status Tracking. Fully autonomous.
     - **MESSY resume (died mid-phase):** owned paths dirty, or the first unmarked phase already has commits
       the plan file doesn't account for →
       `BLOCKED: resume needs operator ruling — found: <the files/commits> — missing: which are the crashed
       run's to continue vs. a sibling's to leave`. **Never guess:** on this shared tree, uncommitted residue
       on "your" paths can be an unlocked sibling's or the daily pipeline's, and
       no prose heuristic can tell — resetting destroys a sibling's work, adopting publishes it. The operator
       rules once; the run then continues autonomously. A resume never `reset`s, `clean`s, stashes, or
       reverts anything. (The five governance surfaces — CHANGELOG/INDEX/docs README/FEATURES/
       LESSONS_LEARNT — are OUTSIDE every plan's lock by grammar; residue there is never resolved by this
       rule alone — see the dispatcher MESSY-resume sweep for the one case where it can be yours.)
   - **Same-plan lock `status:"released"`, or the plan already `EXECUTED`/archived → do NOT re-create the
     lock or re-run** — report it as already finished (the lock's `completed_at`/`final_commit` is the
     completion record; overwriting it destroys provenance).
   - **A DIFFERENT plan's overlapping `active` lock → `BLOCKED: scope overlap with <plan-id> on <path>` and
     STOP — always, even if it looks dead.** There is NO auto-reclaim of another plan's lock: with no atomic
     lock primitive and no liveness signal a blocked-on-a-long-call agent can emit, any staleness heuristic
     WILL eventually stomp a live sibling mid-slice (two runs committing the same paths to shared `master` =
     data loss — the critical failure). Instead REPORT it: name the lock file, its `started_at`, and the
     one-line operator remedy — *"if that run is confirmed dead, delete `.fabrik/plan-locks/<plan-id>.json`
     and re-invoke"*. Freeing a dead sibling's lock is an OPERATOR action, never an agent judgment call.
   - **No overlapping lock** → create `.fabrik/plan-locks/<plan-id>.json` =
     `{plan, owned_paths, branch, started_at, status:"active"}`. After step 8's baseline capture, append
     `baseline_commit` (HEAD then) + `baseline_gate` (the red-check set + owners) to the lock — a resume and
     the Finish whole-plan review / doc-receipt ranges reuse THOSE recorded values, never a re-captured
     mid-plan baseline (else pre-crash phases drop out of the cumulative diff and the run's own pre-crash
     reds get mis-attributed to siblings; a legacy lock without these fields → the messy-resume BLOCKED path).
     (A lock left `active` by an orderly `BLOCKED` halt is INTENTIONAL — the plan still owns its scope until
     resolved; the BLOCKED report should say so.)
8. **Isolate + verify clean + capture the baseline.**
   - **Don't nest a worktree:** if you're already in a linked worktree (`GIT_DIR != GIT_COMMON` and
     `git rev-parse --show-superproject-working-tree` is empty, so it's not a submodule), work in place —
     don't create another.
   - **Isolate concurrent runs:** if any *other* plan-lock is `active`, run this plan in its **own git
     worktree** (`isolation:"worktree"`) so two runs never share a working tree (ensure its `.venv`/deps
     exist before any gate runs there); if yours is the only active run, the main worktree is fine.
   - **Verify your owned paths are clean:** `git status --short -- <owned paths>` must be empty. If not →
     STOP — for a step-7 same-plan RESUME this is the MESSY case: `BLOCKED: resume needs operator ruling`
     per step 7 (never adopt, reset, or revert residue on shared paths — the operator rules first).
   - **Capture the baseline (shared-master attribution — do this BEFORE Phase A).** Record the starting gate
     state: `python scripts/final_gate.py --lean --json` → note its `status` and **every already-red check +
     which file owns it** (yours vs. a sibling's / an untracked file). This is your attribution reference: a
     red at finish that was **already red at start is NOT yours to fix** (a sibling owns it — shared-master);
     only a **newly**-red check is. It's what lets you answer "did I introduce this?" instead of chasing a
     sibling's file or an untracked plan (the exact trap that stalls a run at the end).
9. **Critical pre-flight review (ONCE, before Phase A — the plan may be stale even if it converged).** A plan
   is grounded when written, not necessarily now — the repo moves under it (siblings commit, deps drift,
   an approach gets invalidated). Read the plan **adversarially against the code AS IT IS NOW**: does any
   phase contradict the current code/schema, assume a `path:line` / dependency / invariant that has since
   changed, or rest on an approach the codebase has moved past? Spot-check the plan's key `Interfaces` and
   Evidence `path:line`s still resolve. If a gap would prevent *starting correctly* →
   `BLOCKED: <concern> — searched: <what you checked> — missing: <need>` and surface it to the user before
   executing. This is a **one-time upfront sanity gate**; it does NOT weaken the autonomous contract — once
   past it you execute start→finish per §Execution Contract, **fixing (not asking)** at every step. (This is
   `executing-plans`' "review critically, raise concerns before starting," adapted: a pre-flight, not a
   licence to stop mid-run.)
10. **Track in-session with TodoWrite** — create one todo per phase (and per parallel task) so progress is
    visible; the plan file's `Status:` field + phase-done markers remain the **durable** record a resumed
    run reads (§Plan Status Tracking). The todo list is the ephemeral view, the plan file is the source of truth.

> **Branch model — deliberate divergence, not an omission.** Fabrik runs on **shared `master`** with
> plan-locks + Agent Provenance Trailers + explicit-path commits (§Commit Provenance Trailers), so
> `executing-plans`' "never start on main without consent" and the `finishing-a-development-branch`
> merge/PR handoff are intentionally **superseded** — there is no feature branch to finish; the plan-lock IS
> the isolation and the per-phase commits ARE the integration. Worktrees are used only to isolate
> *concurrent* runs (step 8), not as a merge-to-main gate.

## Self-Service Knowledge Hierarchy

When you encounter uncertainty, resolve it yourself in this order — do NOT ask the user unless you exhaust all levels:

| Level | Source | What it answers |
|---|---|---|
| 1 | The plan file itself | What to build, exact code, exact commands |
| 2 | The design spec | Why decisions were made, grounded references |
| 3 | `.windsurf/rules/` packs (match by glob) | How to write code for this domain (workers, security, ops, etc.) |
| 4 | `agents-fabrik.md` (the canonical map; `AGENTS.md` is a stub) | Infra map, service topology, DB schemas |
| 5 | `docs/` + `AFCL.md` | Configuration, troubleshooting, known friction |
| 6 | `grep` / `Read` the codebase | Existing patterns, function signatures, imports |
| 7 | `mcp__context7` (library docs) → `mcp__exa__web_search_exa` / `WebSearch` / `WebFetch` / `mcp__brave-search__brave_web_search` | 3rd-party API + library docs (cite URL) — the plan already grounded these; this is only for a detail it missed |
| 8 | **STOP and ask the user** | Only after 3 failed resolution attempts across levels 1-7 |

Format when blocked: `BLOCKED: <what> — searched: <sources checked> — missing: <what you need>`

## Execution Contract

> ⛔ **TWO NON-NEGOTIABLES — the failures this contract exists to stop. READ FIRST.**
>
> 1. **No self-authorized deferral.** You do **NOT** get to decide to skip, descope, defer, simplify away, or
>    "leave for later" any step, task, or phase in the plan. There is **no** *optional / nice-to-have /
>    out-of-scope-for-now / TODO-revisit / follow-up-PR / good-enough* bucket for plan work — **every step
>    ships in THIS run**, or you halt with `BLOCKED: <what> — searched: <…> — missing: <…>` (only the defined
>    HARD STOPS: 3 same-test failures, missing infra, unresolvable spec/scope contradiction). *"I judged X
>    unnecessary"*, *"running low on context so I'll finish the rest later"*, *"the core is done, the edges can
>    wait"*, *"I'd rather do this carefully than fast"*, *"substantial enough to deserve a fresh context"*, *"I won't open work I can't
>    finish — stopping at a clean state preserves the value"* (deferral dressed as judgment/prudence — the pattern live-observed repeatedly, incl. the quoted context and clean-state forms; a clean
>    boundary makes the RESUME cheap, it does not make the STOP legitimate — the next stage was still yours to run) are
>    **contract violations, not decisions.** **Context is NOT a reason to stop — the harness AUTO-COMPACTS:**
>    when the conversation grows long it is summarized and the run CONTINUES in the same invocation; your
>    per-phase commits + plan markers are exactly what make the post-compact continuation seamless, so keep
>    them current and KEEP GOING. Filing the context excuse as `BLOCKED: context budget` does not legitimize
>    it (live observed) — a resource limit is not missing infra, and the harness removes the limit. If a
>    remaining phase genuinely deserves fresher eyes than you have, the contract-legal move is to DISPATCH
>    that phase's work to fresh subagents per §Subagent Strategy — decompose, don't abort. Post-compact, the SessionStart hook auto-injects a recent-context recap, and the `session-recall` MCP (`search_chats` / `get_chat`) recovers any detail the summary dropped — use it instead of re-deriving or guessing. A step you believe is genuinely wrong is a `BLOCKED`
>    for the **user** to rule on — never a silent skip or a quiet descope.
> 2. **The plan file is updated every phase, INSIDE that phase's commit — not optional, not "at the end".** A
>    phase is **not complete** until the plan file records it: mark the phase `✅ EXECUTED <YYYY-MM-DD>
>    (<short-commit>)` at its boundary and **stage the plan file in the same phase commit** (flip `Status:`
>    `CONVERGED → IN-PROGRESS` on start; `→ EXECUTED <date>` at the end). **A phase commit that did not also
>    stage the plan-file update is an INCOMPLETE phase — go back and record it before moving on.** The plan
>    file is the durable state; leaving it stale is how a resumed run redoes or drops work. (§Plan Status Tracking)

1. **The plan is the approval — run start→finish, autonomously.** Execute every phase without per-step
   confirmation and **without stopping mid-run to ask or to narrate progress.** Never end a turn with
   "shall I continue / proceeding now unless you redirect" — keep going until the plan is `EXECUTED`,
   `BLOCKED`, or a HARD STOP fires. The only permitted mid-run halts are a real `BLOCKED` (3 consecutive
   same-test failures, missing infra, unresolvable spec/scope contradiction) or a HARD STOP. Permitted
   output between start and finish is **exactly**: a one-line phase-boundary marker per phase, and the
   final completion block. Commit per phase as specified.
2. **Fix, don't ask.** Test failures mean your code is wrong. Read the error, fix, re-run. After 3 consecutive failures on the same test with different fix approaches → STOP and report.
3. **Phase reviews run as parallel subagents.** At each phase boundary, run the full `/fabrik-review`
   methodology on the changed surface *plus everything it calls / is called by* — dispatch its independent
   **finder passes pool-default** (per `/fabrik-review` § Dispatch policy — `fanout("review", …, mode="read_only")`, which auto-records each finder UNSCORED then wants a `set_quality` back-fill), reserving
   **native `fabrik-reviewer` (Opus)** for a phase diff touching auth / schema / migrations / secrets /
   concurrency, then merge + **refute** false positives (you, the orchestrator on Opus), and
   **prove-before-fix** each surviving finding — **CONFIRMED and PLAUSIBLE alike** — with a kept regression
   test. Every finding terminates **FIXED or REFUTED** (proof required to refute); a PLAUSIBLE finding you
   "couldn't reproduce" is NOT resolved — fix it defensively or prove it impossible. There is no
   noted/deferred/residual bucket for an in-scope finding (see `/fabrik-review` Phase 3 + the disposition
   ledger). After fixing, **re-run a fresh `/fabrik-review` finder round on the updated surface** (not just
   the gate — the gate finds no logic bugs), and **iterate find → fix → re-review until one full round
   returns zero CONFIRMED OR PLAUSIBLE findings and every finding sits at FIXED/REFUTED.** Re-run the phase
   gate after each fix too. The next phase begins **only** after that clean round — a single pass is never enough.
   Fixes are the least-reviewed code in any loop, so `/fabrik-review`'s proof standard binds here too:
   **a test that passes because the environment cannot express the failure has proven nothing** — "it
   passed locally" is not evidence when local is the one place the bug is unreachable (a superuser role
   for an RLS bug, one tenant for an isolation bug). Reach for the missing constraint in a
   throwaway instance you own; **never** degrade shared or paid infrastructure to manufacture a red.
   This changes what counts as proof — it adds no disposition and no halt.
3b. **GUI phases also run the Build Verification Loop (per `/fabrik-ui-design`) — a BLOCKING per-screen gate,
   looped to a no-op, alongside `/fabrik-review`.** **A GUI-phase build+verify subagent runs as
   `subagent_type: fabrik-gui`** (web/extension surfaces — browser MCPs Playwright/shadcn/chrome-devtools to
   build the screen and drive/screenshot its own render); the rendered critique stays the `design-review`
   agent. For each screen the phase built: **drive the running screen
   via the surface's MCP** — **web:** Playwright MCP (screenshot 375/768/1440); **mobile (RN):** Maestro MCP +
   Mobile Next MCP, **deferring to `.windsurf/rules/mobile-app/80-mobile.md`**; **extension (MV3):** the web loop
   via a Playwright load-extension fixture, **deferring to `.windsurf/rules/chrome-ext/70-chrome-ext.md`** — match
   it to `docs/ui-design.md` +
   `docs/data-contract.md` (flows within click budget, all enriched states, no invented field/component,
   design-system tokens only), run the surface's a11y/visual/token **+ performance** gate (**web:**
   `@axe-core/playwright` `violations == []` + `toHaveScreenshot` + a Core-Web-Vitals budget via the
   `chrome-devtools` MCP `lighthouse_audit` (LCP/CLS/INP — a slow screen fails "easy to use"); **mobile:**
   `eslint-plugin-react-native-a11y` +
   `@testing-library/react-native` + Maestro `assertScreenshot`; **extension:** `@axe-core/playwright`
   `bypassCSP:true` + `toHaveScreenshot` (400px popup) + `size-limit`), then dispatch **`/design-review`** (or the
   `design-review` subagent) for the rendered critique. Every finding terminates FIXED or REFUTED; iterate until
   `/fabrik-review` reaches its coverage-adjudicated exit (every checklist class CLEAN/FIXED/REFUTED). The next phase begins only after that exit. Non-GUI phases skip this. ⚠️ **That exit must EMIT AN ARTIFACT** — a file under `docs/development/reviews/` whose name contains `phase-<N>`. `check_review_coverage.py`'s subject is that DIRECTORY, so a phase review that writes nothing there leaves the gate with NO SUBJECT and it passes on an empty set: transdoc shipped 17 phases that way and the first real adversarial gate found 71 defects, including a dead job queue. `command_run.py step --phase N+1` now REFUSES until phase N's artifact exists; an unavoidable skip goes through `--review-waived "<reason>"`, which is recorded in the run record rather than silent.
4. **All HARD STOPS still apply** — except the commit restriction is suspended for plan-scoped commits. Never `git add -A`. Never push unless the plan says to.
5. **Documentation is blocking, per phase — not advisory.** Before each phase commit, run
   `python scripts/enforcement/check_doc_sync.py`; **any WARNING whose trigger file is in *this phase's*
   changed set MUST be resolved** (update the doc) before you commit — treat it as an error, not a hint.
   The plan's declared doc steps are checked artifacts of their phase gate. As the **final phase of any run
   that shipped a feature / route / service / schema / config change**, run `/fabrik-docs-review` to
   converge the docs to a truthful fixed point — touch-on-change proves presence; this proves correctness.
6. **LESSONS_LEARNT** — at the end, either add an entry to `docs/LESSONS_LEARNT.md` or confirm `none` in the completion block. This is a Completion Contract requirement.

## Commit Provenance Trailers

Every commit made during plan execution MUST include git trailers that identify which agent, phase, and task produced it. Git can't distinguish AI agents by author — all commits show the same user. Trailers solve this.

### Trailer schema

| Trailer | Values | Required |
|---|---|---|
| `Agent-Role` | `orchestrator`, `subagent`, `review-fix` | Always |
| `Agent-Phase` | `A`, `B`, `C`, ... | Always in phase mode; OMITTED in dispatcher mode (`Agent-Task: T##` identifies the unit — tickets have no phase letter) |
| `Agent-Task` | Task number (`4`, `5`, ...) in phase mode; the FULL ticket ID (`T04`, `T07a`) in dispatcher mode | Subagent commits + dispatcher acceptance commits |
| `Agent-Context` | Short description of what this agent did | Always |
| `Merged-From` | Comma-separated branch list | Orchestrator squash commits only |
| `Conflicts-Resolved` | Count of merge conflicts resolved | Orchestrator squash commits only |

### Commit message format

**Subagent commit** (in worktree, before merge):
```bash
git commit -m "$(cat <<'EOF'
feat(scope): Phase B Task 5 — GDPR schema + routes

Agent-Role: subagent
Agent-Phase: B
Agent-Task: 5
Agent-Context: GDPR schema migration + Flask consent routes
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

**Orchestrator phase commit** (after squash-merging subagent branches):
```bash
git commit -m "$(cat <<'EOF'
feat(scope): Phase B — Compliance

Merged-From: phase-B-task-4 (audit-log vendor), phase-B-task-5 (GDPR schema), phase-B-task-6 (audit wiring)
Agent-Role: orchestrator
Agent-Phase: B
Agent-Context: merged 3 subagent branches, ran phase gate + review
Conflicts-Resolved: 0
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

**Inline phase commit** (no subagents, orchestrator did the work directly):
```bash
git commit -m "$(cat <<'EOF'
feat(scope): Phase D — File Cache

Agent-Role: orchestrator
Agent-Phase: D
Agent-Context: inline execution, no subagents (low complexity)
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

**Review-fix commit** (from `/fabrik-review` findings):
```bash
git commit -m "$(cat <<'EOF'
fix(scope): Phase B review — null guard in audit_log.record_event

Agent-Role: review-fix
Agent-Phase: B
Agent-Context: fixed CONFIRMED finding from /fabrik-review — missing None check on target_id
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

### Querying provenance after the fact

```bash
# All subagent commits
git log --format='%h %s %(trailers:key=Agent-Role)' | grep subagent

# What happened in Phase B?
git log --format='%h %s%(trailers:key=Agent-Role,key=Agent-Task,separator=, )' --grep='Phase B'

# Which phases had merge conflicts?
git log --format='%h %s %(trailers:key=Conflicts-Resolved)' | grep -v ': 0' | grep -v '^$'

# All review fixes
git log --format='%h %s' --grep='Agent-Role: review-fix'
```

## Execution Loop

**PHASE MODE ONLY** — in dispatcher mode this entire loop is REPLACED by the Board loop in
§ Dispatcher Mode (its D-loop pseudocode); do not follow the block below there.

```
read plan → read spec → read active rule packs → read agents-fabrik.md
acquire scope lock (.fabrik/plan-locks/<id>.json) — RESUME your own plan's stale lock (reconcile real state from git); a DIFFERENT plan's overlap = BLOCK always (freeing a dead sibling's lock is an OPERATOR action); isolate in a worktree if another run is active
verify OWNED paths clean (same-plan RESUME: dirty = the step-7 MESSY case -> BLOCKED for operator ruling; never adopt/reset)

for each PHASE in dependency order:

    if Subagent Mandates table says "parallel":
        dispatch subagents per §Subagent Strategy below
        merge results per §Merge Protocol below
    else (inline):
        for each TASK in this phase:
            for each STEP:
                execute step
                if test fails: read error → fix → re-run (max 3 attempts)

    run phase validation gate (bash checks from the plan)
    fix any gate failures → re-run
    run: python scripts/enforcement/check_doc_sync.py
    → any WARNING whose trigger file is in THIS phase's diff is BLOCKING: update the doc before commit
    STAGE the phase's code changes, THEN run the Tier-1 doc-reconcile loop on the STAGED diff: `python scripts/doc_reconcile.py` — **no `--range`**: it reads `git diff --cached`, so it sees the just-staged phase changes. (Do NOT use `--range <phase-base>..HEAD` HERE — the phase isn't committed yet, so a committed-history range is an empty no-op; `--range` is only for the Finish receipt, when all phases ARE committed.) It dispatches a cheap pool author (`pick_models("docs")`) → verify-before-apply → converge, and APPLIES the verified doc patches to the working tree. Then YOU review the applied patches for truth (inject a native-Claude verify_fn for a high-risk doc) and `git add` them so they ride THIS phase's commit. Replaces hand-authoring the declared doc-update steps; hand-write only judgment-heavy prose the loop can't.
    commit the phase CODE (authors run on committed HEAD via git worktree add --detach) → /fabrik-generate-tests on THIS phase's ## Behavior Contract: the pool authors one test per behavior the implementer did NOT already TDD (fanout("code", mode="write"), disjoint owned_paths, sandbox self-verify), you review test-quality + git apply the survivors → re-run the phase gate (now incl. the authored tests). Skip only if the phase added no user-observable behavior.
    /fabrik-review on phase's changed surface (code + the authored tests) — PARALLEL pool finders (fanout("review", mode="read_only") auto-records → set_quality back-fill; native fabrik-reviewer/Opus for auth/schema/risky diffs) → refute → prove-before-fix
    iterate: fix → re-run finders → repeat until one review round is clean, THEN next phase
    fix CONFIRMED findings → commit review fixes with Agent-Role: review-fix trailer
    re-run gate until clean
    UPDATE THE PLAN FILE: mark this phase ✅ EXECUTED <date> (<commit>) [+ flip Status on the first/last phase]
    commit phase with provenance trailers per §Commit Provenance Trailers — STAGE THE PLAN FILE in THIS commit
    (a phase commit without the staged plan-file update is INCOMPLETE — §Execution Contract non-negotiable #2)
    (report ONE line: ✓ Phase X — … ; do NOT stop to ask — continue to next phase; NEVER defer/skip a step — non-negotiable #1)

whole-plan doc-coverage RECEIPT (the free "definitely-done" check): run
    python scripts/enforcement/check_doc_sync.py --range <the step-8 baseline>..HEAD
    python scripts/enforcement/check_doc_stubs.py --range <the step-8 baseline>..HEAD
    → asserts EVERY fired-trigger doc was touched across the WHOLE plan (not just the last commit); an ERROR-tier miss (CHANGELOG/CONFIGURATION/schema) is BLOCKING — reconcile it (doc_reconcile.py or by hand) before Finish.

if this run shipped a feature/route/service/schema/config change:
    run /fabrik-docs-review → converge docs to a truthful fixed point

run FULL final gate: python scripts/final_gate.py --json     # Tier 2 (mypy+bandit+semgrep), never --lean
fix until {"status": "success"} (baseline check: a red that was red at step-8 start is a sibling's, not yours)
run §Finish: /fabrik-review over the WHOLE-plan cumulative diff (→ coverage-adjudicated exit) → gate green (fresh) → requirements coverage → clean up OWN worktree → release scope lock + plan Status: EXECUTED → archive plan to plans/archived/ (only if 100% verified) → PUSH (task-end law; ladder on rejection) → name the deploy decision
```

## Dispatcher Mode — spine+ticket plan sets

Detected per Before-You-Start step 0. The spine's `## Ticket Board` is the work queue; tickets are the
dispatch units. Everything below OVERRIDES the phase-mode sections it names — including the whole
`## Execution Loop` (replaced by the D-loop here) — and everything it doesn't name (HARD STOPS,
provenance trailers, doc discipline, the Execution Contract's non-negotiables) binds unchanged.

```
read spine + EVERY ticket → rules/spec/AFCL per Before You Start
acquire lock (owned_paths = spine File Scope MINUS stem-scoped metadata) → baseline capture
FIRST dispatch commit flips spine Status: CONVERGED → IN-PROGRESS

while the Board has non-terminal tickets:
    eligible = ⬜ tickets with every Depends: row ✅ and no pending Serialized: barrier
    dispatch up to 3 coders, Merge-Order position order, runtime per Complexity (D2)
    on each coder return: per-ticket review loop to coverage-adjudicated exit (D4)
    merge in Merge Order: squash-apply code + Board flip + applied Deltas in ONE commit (D5)
    timeout / dead coder → salvage procedure (D6); 3 same-test strikes → 🔴, CONTINUE the Board

all non-🔴 terminal → D7 final validation (found: 0, fixed: 0) → Finish (whole-directory archive)
any 🔴 remaining and nothing in flight → blocked-end (D7): spine BLOCKED, lock retained/paths cleared
```

(Board glyph vocabulary — per the plan grammar: ⬜ queued · 🔵 dispatched/in-work · 🟡 in review ·
✅ merged · 🔴 blocked. The gate keys on ⬜ mechanically — a merge commit whose Board row is still ⬜
is an ERROR — and treats the sanctioned back-flips ✅→🔵/🔴 as compliant states.)

### D1 — Entry + the IN-PROGRESS flip

Lock acquisition is per Before You Start, with the set adaptations: the lock's `owned_paths` = the spine's
`## File Scope` **minus the stem-scoped metadata** (the plan set's own directory, its lock file, its
review files — orchestrator territory, never lockable work surface). **The FIRST dispatch commit flips the
spine `Status: CONVERGED → IN-PROGRESS`** — the budget WARN keying and resume logic depend on that flip
landing before any ticket work is visible. **The lock and the spine Board are ORCHESTRATOR territory:
tickets never write either** — a coder that edits the spine, the lock, or another ticket's files has left
its Touches (contract violation → its diff is rejected at acceptance).

### D2 — Dispatcher contract (who codes, who is dispatched, when)

- **PRECONDITION — a dispatched coder must be able to RUN its proof floor.** A native
  `claude -p` coder under `--permission-mode acceptEdits` can write files but cannot execute
  ANY Bash without a pre-approved allowlist — five coders on one transdoc ticket each wrote
  code none could verify (proposal 2026-08-23, upstream'd). The fleet baseline that grants the
  verification surface (pytest/ruff/mypy/gate/git-reads) ships in the SYNCED
  `.claude/settings.json` `permissions.allow`; **before the first dispatch, confirm it is
  present in THIS repo's copy** (`python3 -c "import json;print('allow' in
  json.load(open('.claude/settings.json')).get('permissions',{}))"` → `True`). Absent →
  re-sync from the hub (`pull, don't expect push` for excluded repos) or halt with a
  pre-start finding — do NOT fall back to `bypassPermissions` (unbounded grant) and do NOT
  run the coders' tests yourself (that collapses coder and reviewer — the separation is what
  catches the findings). The failure PRESENTS as "BLOCKED: missing infra"; it is a missing
  capability grant — check the settings first.
- **The orchestrator writes NO ticket code**, with exactly ONE exception — trivial ≤1-file/≤50-LOC
  **strictly-mechanical** inline edits (**no-new-logic** defined: no conditional/loop/function-body
  change). Any orchestrator-authored fixup is bound by the same numeric limits, lands **inside the
  ticket's acceptance commit under its `Agent-Task:` trailer**, and gets a pool finder pass before final
  validation trusts it.
- **Fixup ROUTING (a rule, not an exception):** fixups go to the ticket's coder — SAME coder if its
  session is alive; a FRESH coder/unit otherwise, whose task payload = the standard cold-coder
  briefing frame (the § Briefing template's "Before you start" reads — rules/infra/spec) + the ticket
  file + the branch history (`git log <base_commit>..HEAD`) + the specific findings — and NO session
  history, prior-phase summaries, or other tickets (the exclusion targets context bloat, never the
  standard briefing).
- **Dispatch eligibility:** every `Depends:` row ✅ AND no `Serialized:` barrier pending (a Serialized row
  is a dispatch barrier: later waits for earlier ✅ — **direction per `## Merge Order` position, the
  canonical order signal**; the row's own ID listing order is not load-bearing, and a row listed against
  Merge Order is an authoring defect `/fabrik-plan-review` should have caught).
- **Dispatch timeout:** a coder with no result within 2× the ticket's plan-time estimate (no estimate
  stated → use 30 min as the estimate, i.e. a 60-minute timeout) → the D6 salvage procedure; 2
  consecutive timeouts on one ticket → 🔴.
- **Coder runtime per `Complexity:` (all FOUR values):** **`simple`** →
  `pick_models("code", prefer="value")` pool unit · **`complex`** → mid pool coder — both via
  `fanout("code", units=[{task, owned_paths: <ticket Touches>}…], mode="write")` · **`never-route`** →
  native worktree coder (**gate cross-check:** the gate independently ERRORs a pool-tier ticket
  touching never-route paths — trust it, don't re-derive) · **`native`** → native worktree coder by
  AUTHOR'S CHOICE for non-never-route work the pool must not code (the Integration ticket always
  carries `Complexity: native` — a pool-tier Integration ticket is a gate ERROR). An all-native cycle
  → a **`NO-POOL:`** declaration naming the reason per ticket (the never-route class, or
  author-chosen `native`). Native coder tier: Sonnet default; Opus for design-heavy (auth
  flow/schema/migration design, concurrency); Haiku never codes. Concurrency: **3 coders**; when more
  tickets are eligible than free slots, dispatch in `## Merge Order` position order (deterministic
  across runs, and it frees downstream `Depends:` earliest); **acceptance reviews serialize** (one at
  a time — the orchestrator's adjudication is serial anyway, and it meters the Opus stream).
- **Dispatch economics (budgeted rules, not vibes):**
  - **Two currencies:** native Claude = subscription **quota** (binding; accounts exhaust in ~2–3 days);
    pool = metered dollars at cents-scale. Never burn an Opus call to avoid a cents-scale pool unit;
    never dispatch pool units the floor doesn't need.
  - **Native tier map (four rungs):** **Fable** = orchestrator/adjudication + the final validation's
    authoritative native seat (it SUBSTITUTES for, never adds to, the Opus seat there); never a routine
    finder, never a coder. **Opus** = the per-round per-ticket authoritative finder + design-heavy
    never-route coding. **Sonnet** = default never-route coder; as a native finder ONLY via a named
    trigger (breadth is trigger-funded, not routine). **Haiku** = trivial-mechanical checks; never codes.
  - **Count discipline — the floor IS the default, per review ROUND:** each per-ticket review round =
    **2–3 diverse pool finders + exactly 1 native Opus finder**; every material re-review round re-runs
    the floor; scale up by at most +2 finders (pool-tier unless never-route) ONLY on a named trigger
    (diff >~400 net LOC · never-route surface · a repeat-failed round). Grounding fan-outs: one unit per
    independent dependency, never per file.
  - **Quota-pause terminal:** a native call failing on quota exhaustion (not a transient error) → the
    plan PAUSES: lock `status: "paused"`, Board preserved, spine stays IN-PROGRESS; resume on quota
    reset/rotation. **The Opus floor is never substitutable downward** — quota pressure pauses the plan,
    it never thins the review.

### D3 — Shared governance files: orchestrator-applied Deltas

The five governance surfaces (CHANGELOG.md · INDEX.md · docs/README.md · docs/FEATURES.md ·
docs/LESSONS_LEARNT.md) are never in Touches (gate-enforced). Every coder report ends with a
**`## Deltas` block** in fixed format: `### CHANGELOG` (entry text verbatim) · `### INDEX` (rows) ·
`### LESSONS` (entry-or-none) · matching headings for any other fired governance surface. The
orchestrator applies deltas at merge in Merge-Order order, **dedupes on normalized full entry text —
same-title-different-body pairs are surfaced to the acceptance review, never silently dropped** — and the
applied diff is part of the acceptance-review surface, landing in the acceptance commit (where
`check_changelog.py` demands the entry). Integration-ticket command outputs flow through the same
mechanism.

### D4 — Per-ticket receive + review: the ettw-07 floor, per round

("ettw-07" is provenance — the epic-to-ticket workflow step this floor was adapted from; the CONTRACT
is the text below, self-contained.) Each returned ticket converges to `/fabrik-review`'s coverage-adjudicated exit BEFORE merge — pool
breadth (counts per D2) **AND exactly 1 native Opus finder per round, UNCONDITIONAL**. **Secrets
carve-out:** a diff touching secret-material paths (`.env`-prefix, `secrets/`, key files) is reviewed
**native-only** — secret contents never go to pool APIs; all other never-route classes get both layers.
The orchestrator refutes/merges/adjudicates; fixups route per D2. Each ticket's review is persisted as
`docs/development/reviews/<plan>-T<id>-review.md` (full ID; **one file per ticket, round sections
APPENDED**, each round carrying a machine-readable roster line — `Finders: pool <model×n> + native
<model×n> — round N` — so the floor is attestable, not asserted). `/fabrik-generate-tests` runs at
acceptance for non-TDD'd behaviors. Consumer seam tests are blocking at the CONSUMER's review. **Fixups
reuse the ticket row/file — Board back to 🔵; new rows post-CONVERGED forbidden.** 3 consecutive
same-test failures → 🔴 + `BLOCKED` for that ticket, **continue the Board** (3-strikes-continue: one
red ticket never halts the others).

**Docs converge with the ticket, not at the end of the plan.** Before a ticket merges, run
`python scripts/enforcement/check_doc_sync.py` — **any WARNING whose trigger file is in THIS ticket's
diff is BLOCKING** — then the Tier-1 reconcile on the STAGED diff (`python scripts/doc_reconcile.py`,
no `--range`: it reads `git diff --cached`), review the applied patches for truth, and stage them so
they ride the TICKET's own commit. This mirrors the phase-mode loop, which has always done it per
phase. Without it the dispatcher's only doc gate is D7's whole-plan receipt — so a stale doc surfaces
at the END of the plan, detached from the ticket that caused it and from the agent that still had the
context to write it. The receipt then stays what it is meant to be, a *receipt*, rather than the first
time anyone looks.

### D5 — Merge protocol (overrides § Merge Protocol for ticket merges)

Merge in `## Merge Order`. Merges are **squash-applied**: code + spine Board flip + applied Deltas staged
in ONE ordinary commit with the full-ID `Agent-Task:` trailer — same-commit atomicity is what makes the
Board trustworthy. Touches are exclusively owned → a same-file collision between coders is a **contract
violation → ERROR + re-dispatch**, never a merge-rule pick. Cross-ticket semantic incompatibility is
caught by tests, not diffs: at each merge, re-run the producer tickets' Behavior-Contract tests + the
consumer's seam tests on the integrated tree — red → fixup routed to the **CONSUMER's coder** with both
contracts in scope. **Salvaged/stale branches are rebased onto current master before acceptance review**
(conflicts → a fixup, never a silent resolution).

### D6 — Lock registry: per-ticket resume

The lock gains `tickets: {<full ID>: {state, worktree_path, branch, base_commit, started_at}}` per
dispatch — pool tickets record `worktree_path/branch: null` (fanout captures diffs, never auto-applies: a
crashed pool unit leaves no partial writes; recovery = re-dispatch the unit). **Dead-coder procedure
(native):** recorded path missing/erroring, or dirty with state ≠ merged → **salvage check first**
(`git -C <wt> log <base_commit>..HEAD --oneline` non-empty → returned work → rebase → acceptance review;
fixups → fresh coder per D2); otherwise log the dirty file list to spine Evidence, then
`git worktree remove --force` + re-dispatch fresh — fully autonomous; coder worktrees are disposable,
never resumed. Orchestrator partial-diff assessment is capped (`git diff --stat` + ≤3 files/500 lines;
larger → straight to a fresh coder's salvage review — the orchestrator does not read big diffs at its
tail). **MESSY-resume sweep:** on ANY resume, run this procedure over every 🔵 lock entry BEFORE new
dispatches, and ALSO probe the five governance surfaces for uncommitted residue — a crashed run's
half-applied Deltas are the ONE case where governance residue can be yours (the lock's `tickets` map
says which merge was in flight); operator ruling remains only for the orchestrator's OWN tree. **SIZING
DEFECT signals (orchestrator-logged to spine Evidence):** a re-dispatch, a partial diff vs Touches, a
dispatch timeout, or a coder-report context marker.

### D7 — Final validation + terminal states

**The Integration ticket runs BEFORE validation — it is a Board unit (the LAST one), not part of
validation.** The set's
exactly-one `Integration: true` ticket (`Complexity: native`, last in Merge Order — both
gate-enforced) owns the monolith's mandatory closing work: the whole-plan doc receipts
(`check_doc_sync.py --range <baseline>..HEAD` + `check_doc_stubs.py --range`), `/fabrik-docs-review`,
`/fabrik-features` when features shipped, the cross-ticket seam-test run, and the whole-plan
`final_gate.py --check --json` + `check_convergence.py` run; its command outputs and doc-drift fixes
flow through `## Deltas` (D3), and it merges like any ticket. D7's validation is the adversarial
layer ON TOP of those receipts — never a substitute for them.

Validation runs only when every non-🔴 ticket is terminal (✅ — no ⬜ dispatchable, no 🔵/🟡 in
flight, all salvage procedures complete). ONE whole-plan validation — internally consistent · factual · correct:
spine↔tickets↔frozen-contract seams + the integrated cumulative diff + a full run of **every ticket's
Behavior-Contract tests and every seam test**. **Finder counts SCALE with the surface:** minimum 3 pool
finders + the native authoritative seat (**Fable substitutes for Opus here**), adding ~1 pool finder per
2 tickets; NO round cap; closes only on `found: 0, fixed: 0`. A flaky test is itself a finding (fix or
quarantine-with-recorded-ruling — never an excuse to loop). Validation findings are FIXED by fresh
coders/units bound to the owning ticket's Touches through the per-ticket review loop (cross-cutting
findings split along Touches); a producer-originated defect surfacing here (or at the Integration seam
run) flips the producer's row ✅→🔵 and re-dispatches — the **sanctioned back-flip**. The validation MAY
run in a fresh orchestrator context (spine + lock are the durable handoff).

**⚠️ A plan that shipped HTTP surface does not reach a terminal state on green suites alone — it owes
at least one LIVE REQUEST.** When any merged ticket added or changed a route, endpoint, or client
call, validation requires ≥1 real request issued against the running service, with its actual
response pasted verbatim into the spine's `## Evidence`. A passing suite proves the code the tests
call; only a live request proves the route EXISTS at the path the caller uses. Measured (transdoc,
2026-08-25): six verification layers were simultaneously green — the governing rule pack unreachable,
45 `page.route` mocks covering exactly the missing endpoints, `final_gate` green, 296 tests passing —
while 19 frontend calls pointed at routes that did not exist and 14 built endpoints had no caller. No
suite could see it; one request would have. Mocked, stubbed, or recorded responses do NOT satisfy
this; a plan with no HTTP surface states that in `## Evidence` and moves on.

Then Finish: receipt, gate,
spine `Status: EXECUTED` citing the WHOLE-PLAN validation review
(`docs/development/reviews/<plan>-review.md` — `check_convergence` enforces the citation exists with a
quiet `found: 0` pass, and for a plan set it rejects a per-ticket `-T##-review.md` as that proof), lock
release, **archive = whole-directory move** (§ Finish step 6).

**Blocked-end rule:** when no dispatchable tickets remain, no 🔵/🟡 in flight, and any row is 🔴 — no
final validation; flip spine `Status: BLOCKED` + commit; clean 🔴 tickets' worktrees/branches; the lock
is RETAINED with `status: "blocked"` + the full `tickets` map for operator inspection but its
`owned_paths` is CLEARED (so it never blocks future overlapping plans); stop for operator ruling.
**Blocked-resume:** the ruling, recorded in spine Evidence, authorizes 🔴→🔵 re-dispatch of named
tickets (never new rows); flip the spine `BLOCKED → IN-PROGRESS` (committed with the ruling), restore
the lock (`status: "active"`, re-derive `owned_paths` per the D1 rule — File Scope MINUS the
stem-scoped metadata), and execution re-enters at D2.

## Subagent Strategy

### When to dispatch

Check the plan's design spec for a **Subagent Mandates** table. It specifies per-phase:
- How many parallel subagents
- What each subagent does
- Where results merge

Phases marked "inline" or with 1 subagent → execute directly, no dispatch.

### ⚠️ Dispatched subagents run their work SYNCHRONOUSLY — never background, never wait on a Monitor

**The #1 way a phase silently burns its whole budget without writing a line.** A dispatched implementer /
reviewer subagent that starts a long job (a build, a test suite, a provisioning routine, `pytest`, a
migration) **in the background — or arms a Monitor and ends its turn to "wait for the result" — STALLS
FOREVER: background and Monitor notifications do NOT deliver to a subagent.** From the orchestrator's side it
looks alive, then reports `completed` with nothing done. Every dispatched subagent MUST run each command as a
plain **synchronous** shell call (a generous `timeout`) and read its exit output in the SAME turn. **If a
step is too slow for one synchronous call, SPLIT its scope** (e.g. a big provisioning phase → seed-countries,
then chart-of-accounts, then fiscal-year, each run and verified synchronously) — never defer a slice to a
signal that will not arrive. ⚠️ **"A generous `timeout`" is not advice, it is the load-bearing part:
the Bash tool's DEFAULT is 120s, and a call that exceeds it does not error — it AUTO-BACKGROUNDS.**
So a subagent obeying this instruction to the letter lands in exactly the state the instruction
exists to prevent, with no signal that it happened (transdoc, 2026-08-28: a first synchronous
`npx playwright test` silently backgrounded on a cold dev-server boot). Pass an EXPLICIT
multi-minute `timeout` on anything that boots a server, runs a browser suite, or provisions —
"split scope" cannot help when the call is a single unsplittable server boot. Dispatch every
subagent with an explicit *"run synchronously with an explicit multi-minute `timeout` on any
server-boot / browser-suite / provisioning call; never background a run or wait on a
Monitor/notification; split scope only when the work genuinely divides"* instruction in its brief.

### Isolation model: worktrees

Every parallel subagent MUST use `isolation: "worktree"` in the Agent tool call. This gives each subagent its own git worktree — a separate working directory with its own branch. They cannot clobber each other.

```
Phase with 3 parallel subagents:

  main worktree (orchestrator)
    ├── worktree-1/ (subagent 1, branch: phase-B-task-4)
    ├── worktree-2/ (subagent 2, branch: phase-B-task-5)
    └── worktree-3/ (subagent 3, branch: phase-B-task-6)

Each subagent commits to its own branch.
Orchestrator merges branches back sequentially.
```

### Briefing template

Each subagent starts **cold** — it has zero context from this conversation. The prompt you give it must be self-contained. Use this template:

⚠️ **State the precedence in the brief, or every finder re-derives it.** A dispatched subagent inherits
`CLAUDE.md`'s response contract (the FIRST-OUTPUT `RULES ACTIVE` line, the 6-line FINAL OUTPUT block,
the STATE footer) — written for an OPERATOR-facing turn — while its brief asks for a return VALUE the
orchestrator will parse. Those collide, and nothing says which wins, so each finder decides for itself
(reported by brand-identiy-creator `01M150NTHP`). **The brief outranks the response-format contract for
a dispatched subagent:** return exactly what the brief asks for and nothing else. The response contract
binds the ORCHESTRATOR's turn, not the subagent's return value — a subagent that wraps its findings in a
6-line block is handing the parser prose it did not ask for. Put this line IN the brief; do not assume
it.

```
You are executing Task {N} of the fabrik-lib integration plan as an isolated subagent.

## Your assignment

{Copy the FULL task text from the plan — every step, every code block, every
command. Do NOT say "read the plan at <path>" — the subagent should have
everything it needs right here. Only reference the plan/spec for WHY context.}

## Interfaces

Consumes: {copy the task's Consumes block}
Produces: {copy the task's Produces block}

## Files you will touch

Create: {list}
Modify: {list with line ranges}
Test: {list}

## Before you start

1. Read `agents-fabrik.md` — infra map.
2. Run `python scripts/select_rules.py` and read every ACTIVE pack.
3. Read the design spec at {path} — sections {X, Y} for context on why.
4. Read `AFCL.md` if it exists.

## Global Constraints

{Copy the plan's Global Constraints section verbatim.}

## Vendoring protocol (if this task vendors a module)

{Copy steps 1–6 of this command's § When Vendoring (Copying fabrik-lib Modules) verbatim.}

## Self-Service Knowledge Hierarchy

{Copy the full hierarchy table from this command.}

## When done

Commit your work to the worktree branch with provenance trailers:
  git add {explicit file list}
  git commit -m "$(cat <<'EOF'
feat(scope): Phase {X} Task {N} — {title}

Agent-Role: subagent
Agent-Phase: {X}
Agent-Task: {N}
Agent-Context: {one-line summary of what you did}
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
  )"

Do NOT push. Do NOT merge. The orchestrator handles that.

Report: list of files changed, tests passing (count), any issues encountered.
```

### Dispatch pattern

Send ALL parallel subagents for a phase in a **single message** with multiple Agent tool calls. This runs them truly in parallel:

```python
# Example: Phase B with 3 parallel subagents
Agent(
    description="Phase B Task 4 — audit-log vendor",
    isolation="worktree",
    prompt="You are executing Task 4 of the fabrik-lib integration plan..."
)
Agent(
    description="Phase B Task 5 — GDPR schema + routes",
    isolation="worktree",
    prompt="You are executing Task 5 of the fabrik-lib integration plan..."
)
Agent(
    description="Phase B Task 6 — audit wiring",
    isolation="worktree",
    prompt="You are executing Task 6 of the fabrik-lib integration plan..."
)
# All three dispatch in ONE message → true parallel execution
```

### Model selection (specify it explicitly — an omitted model burns the session default)

**Always pass `model=` on every Agent dispatch.** An omitted model inherits *this* session's model —
usually the most capable and most expensive — which silently defeats cost control. Pick the **least
powerful model that can do the role**, because **turn count beats token price**: the cheapest models take
2–3× the turns on multi-step work, costing more overall.

| Role | Model |
|---|---|
| Implementer — the phase brief contains the exact code/commands (transcription + test) | cheapest tier |
| Implementer — 1–2 files, complete spec, mechanical | cheap |
| Implementer — multi-file integration, pattern-matching, debugging judgment | standard (Sonnet) |
| Implementer — design judgment / broad-codebase reasoning | most capable (Opus) |
| Finder / reviewer | **pool-default** (`fanout("review", …)` — flywheel-ranked, no default price cap; auto-records to the flywheel, `set_quality` back-fill); native `fabrik-reviewer` on **Opus** when the diff touches auth / schema / migrations / secrets / concurrency — scale to the diff's risk, not a flat default |

### File handoffs — move artifacts as FILES, not pasted text

Everything you paste into a dispatch prompt **and** everything a subagent prints back stays resident in
your context and is **re-read on every later turn** — a real session hit 42k chars of pasted prior-task
history. Conserve the orchestrator's context:

- **Brief as a file:** write the phase's brief (its steps + `Interfaces` + `Global Constraints`) to a scratch
  file (e.g. `<scratchpad>/phase-<X>-brief.md`) and give the subagent the **path**, introduced as "read this
  first — your requirements, use its exact values verbatim." Exact values (signatures, magic strings, test
  cases) live only in the brief.
- **Report as a file:** tell the subagent to write its full report to `<scratchpad>/phase-<X>-task-<N>-report.md`
  and **return only** status + commit range + a one-line test summary + concerns. The reviewer reads the
  brief + report + the diff (`git diff <base>..<head>`) as files.
- **Never paste session history / prior-phase summaries into a dispatch.** A cold subagent needs only its
  brief, the `Interfaces` it touches, the Global Constraints, and your resolution of any ambiguity you
  spotted. Nothing else — not "state after Phases A–C."

### Implementer status protocol

Each implementer subagent reports exactly one status; handle each — **never force the same model to retry
unchanged**:

- **DONE** → a `DONE` is a **claim, not proof — verify it yourself before accepting the phase.** Read the
  actual `git diff <base>..<head>` (using the base you recorded *before* dispatching — never `HEAD~1`, which
  truncates a multi-commit task): do the changes match the assignment, and did it change only its owned
  paths? **Re-run the covering tests yourself** (the subagent's "N/N passing" line is its report, not your
  evidence — a fresh run in your turn is). Only a diff that matches + your own green run → phase-boundary
  `/fabrik-review`.
- **DONE_WITH_CONCERNS** → read the concerns first; if correctness/scope, resolve before review; if
  observations, note in the ledger and proceed.
- **NEEDS_CONTEXT** → supply the missing context, re-dispatch (same model).
- **BLOCKED** → diagnose: context gap → re-dispatch with more context; needs more reasoning → re-dispatch
  on a more capable model; task too large → split it; **plan itself wrong → escalate to the user** (`BLOCKED:`).

### Reviewer & fix-dispatch discipline

- **Do NOT pre-judge findings in a review dispatch.** Never tell a finder what *not* to flag or pre-rate a
  severity ("treat as Minor at most", "the plan chose this"). If your dispatch text contains "don't flag" /
  "the plan mandates it" — stop, you're suppressing a finding to save a loop. Let it surface and adjudicate
  it in the refute/merge step. A plan-mandated finding that conflicts with the plan is the **user's** call.
- **One fix subagent for the whole findings list, not one per finding.** Per-finding fixers each rebuild
  context and re-run suites — a real session's per-finding fix wave cost more than all its tasks combined.
  Batch CONFIRMED findings into a single fix dispatch; it re-runs the covering tests and reports results.

### Flywheel — `fanout` auto-records; YOU back-fill the score (feeds `pick_models`)

This command dispatches its pool workers via **`fanout(task_type, units, …)`** — the designed **first mover**
is the per-phase **implementer** fan-out (§Subagent Strategy: `fanout("code", units, mode="write", …)` with
disjoint `owned_paths`). `fanout` **auto-records one row per unit UNSCORED** at dispatch and returns
`(results, results_table)` — the human table is already built for you. After you **EVALUATE** each worker's
output (its diff verified + tests re-run by YOU), **back-fill your 0–5 verdict**:

```python
results, table = fanout("code", units, mode="write", repo=REPO, project=<project>)  # auto-records UNSCORED
# … you verify each diff + re-run its covering tests yourself …
for r in results:
    set_quality(r.agent_id, score(r), project=<project>, task_type="code", model=r.model)
```

⚠️ A **native** Claude Task implementer / `fabrik-reviewer` finder (Runtime A) produces **no `AgentResult`** →
it **cannot** record; only pool dispatches feed the flywheel. A phase that ran inline / solo or native →
**nothing to record**. ⚠️ never hand-roll `run_agents`+`record_run` — `record_run` silently no-ops on a raw
`AgentResult`; `fanout` (auto-record) + `set_quality` (back-fill) IS the whole recording path, one shared 0–5
verdict in both the returned `results_table` and the DB row.

**Pool-default (per `62` § Dispatch policy):** implementers `fanout` to the pool **by default** — the plumbing
is proven (`from libs.subagents import fanout, set_quality` resolve + rows land in `subagent_runs`;
the flywheel check's Layer 2 warns on UNRECORDED runs, not unscored ones — `fanout` already records at dispatch, so nothing catches a missing score but you). Reserve **native** implementers for high-risk
units (auth/schema/migrations/concurrency) + the decide/merge.

The module captures cost / turns / latency automatically; **YOU supply the `set_quality` score** (0 = wrong/
unusable, 5 = fully correct, high-signal). `fanout`'s auto-record and `set_quality` connect via the module's
configured DSN; exact connection handling (WSL dev vs VPS `SUBAGENT_RUNS_DSN`), the import path, and the
`result` object are per `fabrik-lib/README.md` + the vendored module's own `README.md`.

> Rollout safety: on a genuine pool dispatch, wrap the import — `try: from libs.subagents import fanout,
> set_quality / except ImportError: fanout = None` — and guard with `if fanout:` so a not-yet-vendored project
> no-ops instead of erroring.

## Merge Protocol

After all subagents for a phase complete, merge their branches back to the working branch. This is the critical step — do it carefully.

### Sequential merge, lowest task number first

```bash
# 1. Verify you're on the working branch, tree is clean
git status --short  # must be empty

# 2. Merge each subagent branch in task-number order (lowest first)
git merge --no-ff phase-B-task-4 -m "merge: Phase B Task 4 — audit-log vendor"
git merge --no-ff phase-B-task-5 -m "merge: Phase B Task 5 — GDPR schema"
git merge --no-ff phase-B-task-6 -m "merge: Phase B Task 6 — audit wiring"

# 3. If a merge conflicts:
#    - Read BOTH sides of the conflict
#    - The HIGHER task number wins on semantic conflicts (it has more context)
#    - For additive conflicts (both added to same file, different locations):
#      keep both additions
#    - For import conflicts: combine both import sets
#    - Resolve, then: git add <resolved files> && git merge --continue

# 4. After all merges: verify the combined result compiles
python -c "import src.module_that_changed"  # or whatever the plan's verify command is

# 5. Clean up worktree branches
git branch -d phase-B-task-4 phase-B-task-5 phase-B-task-6
```

### Conflict resolution rules

| Conflict type | Resolution |
|---|---|
| Both edited same function | Higher task number wins (more context) |
| Both added imports to same file | Combine — keep all imports from both |
| Both added code to same file at different locations | Keep both additions |
| Both modified the same test | Higher task number wins; re-run to verify |
| One added a file the other also added | Higher task number wins; diff to check for lost work |
| Schema/migration ordering | Merge both migrations; adjust sequence numbers if needed |

### Post-merge verification

After merging all subagent branches for a phase:

1. Run ALL tests that any subagent in this phase touched
2. Run the phase validation gate
3. Run `python scripts/enforcement/check_doc_sync.py`
4. Fix any issues (you're the orchestrator — you fix merge-induced bugs)
5. Squash the merge commits into one phase commit with provenance trailers:
   ```bash
   git reset --soft <pre-merge-commit>
   git add <all phase files — explicit list>
   git commit -m "$(cat <<'EOF'
feat(scope): Phase {X} — {title}

Merged-From: phase-{X}-task-{A} ({desc}), phase-{X}-task-{B} ({desc})
Agent-Role: orchestrator
Agent-Phase: {X}
Agent-Context: merged {N} subagent branches, ran phase gate
Conflicts-Resolved: {count}
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
   )"
   ```
6. THEN proceed to `/fabrik-review`

## Inter-Phase Parallelism

The design spec may indicate that some phases are independent (e.g., "Phases A, C, D are independent — MAY run in parallel"). If so:

1. Only parallelize phases that the spec explicitly marks as independent.
2. Each parallel phase gets its own worktree (same `isolation: "worktree"` model as subagents within a phase).
3. After all parallel phases complete, merge them sequentially (alphabetical phase order).
4. Run the validation gate for EACH phase after merge to confirm nothing broke.
5. Run `/fabrik-review` on the combined changed surface.

**Caution:** Inter-phase parallelism multiplies merge complexity. Only do it when the spec says the phases are truly independent (no shared files, no interface dependencies). When in doubt, run phases sequentially.

## When Vendoring (Copying fabrik-lib Modules)

1. Copy the files as the plan specifies
2. Fix internal imports: `from module_name import X` → `from libs.module_name import X`
3. Add `__init__.py` if the source module doesn't have one
4. Verify: `python -c "from libs.X import Y"` — must exit 0
5. Then proceed to wiring steps
6. **If you FIX a bug in the vendored copy** (not just adapt imports/wiring): append a dated note to
   `/opt/fabrik-lib/<module>/UPSTREAM_FEEDBACK.md` — the symptom + how you fixed it — so the fabrik-lib AI
   upstreams it for every future project. This single append is the **only** write permitted outside the
   project tree.

## Plan Status Tracking

Keep the plan file's own `**Status:**` field current as you execute — it is the **durable record** of
where execution stands, and a resumed session reads it to know what is already done. All of these edits
are part of the phase commits (explicit path: the plan file) and carry the same provenance trailers; do
**not** delete the `## Evidence` / `## Self-audit` sections (they remain the execution's design record).

- **On start** (before the first phase commit): flip `**Status:** CONVERGED` → `**Status:** IN-PROGRESS`.
  This also moves the plan out of `check_convergence.py`'s scope — it only gates plans whose Status is
  `CONVERGED`/`zero unknowns` — so the Evidence stays as the design record with no re-validation.
- **At each phase boundary** (after the phase commit AND a clean `/fabrik-review`): mark that phase done
  in the plan — append `— ✅ EXECUTED <YYYY-MM-DD> (<short-commit>)` to the phase's heading (or tick its
  DoD checklist). A resumed run skips phases already marked done; a first UNMARKED phase with landed-but-unaccounted commits or dirty owned paths is step 7's MESSY case -> BLOCKED for the operator (never blind-redo, never mark on partial evidence, never guess residue ownership).
- **On completion** (all phases done, final gate green): flip `**Status:** IN-PROGRESS` →
  `**Status:** EXECUTED <YYYY-MM-DD>`, add a one-line completion stamp (final commit + gate result), **and
  cite the whole-plan review artifact** — `Whole-plan review: docs/development/reviews/<plan>-review.md`.
  Gate-enforced: `check_convergence.py` fails an `EXECUTED` plan that cites no existing, coverage-adjudicated
  review (the backstop for a run that skipped the step-1 whole-plan `/fabrik-review`).
- **On a HARD STOP / BLOCKED**: set `**Status:** BLOCKED — <what> (Phase N)` so the halt reason lives in
  the plan, not just the chat.
- **Dispatcher mode:** the "at each phase boundary" bullet does NOT apply — the Board row flip inside
  each acceptance commit (D5) IS the durable per-unit record. **Never write a completion marker or
  `Status:` line into a ticket file** (the gate rejects any ticket Status — state lives ONLY in the
  spine Board). The spine's own `Status:` moves only on D1/D7 events: `CONVERGED → IN-PROGRESS` at
  the first dispatch commit (D1); `→ EXECUTED` only at D7's close; `→ BLOCKED` at blocked-end, and
  on blocked-resume `BLOCKED → IN-PROGRESS` (committed with the ruling) before any 🔴→🔵 re-dispatch —
  never any other value, never mid-run.

## Progress Reporting

After each phase: `✓ Phase {X} — {title} — {n} tests passing, gate green, review clean`

If subagents were used: `  ↳ merged {n} subagent branches, {n} conflicts resolved`

After all phases, output the CLAUDE.md completion block:
```
GATE: python scripts/final_gate.py --json → success   # FULL (Tier 2)
DOCS UPDATED: <files>
CHANGELOG: <entry>
LESSONS LEARNT: <none | docs/LESSONS_LEARNT.md entry title>
```

## Finish (shared-master — there is no branch to merge)

Fabrik commits per-phase directly to `master` and the plan-lock was your isolation, so
`finishing-a-development-branch`'s merge / PR / keep / discard menu **does not apply** — there is nothing
to merge back. "Finishing" is:

1. **Final whole-plan review — the cross-phase net the per-phase reviews CAN'T see.** Run **`/fabrik-review`
   over the CUMULATIVE diff across ALL phases** (`git diff <the step-8 baseline commit>..HEAD` — the whole
   plan's surface, NOT a single phase's slice), run to its coverage-adjudicated exit (every checklist class CLEAN/FIXED/REFUTED, every
   finding FIXED/REFUTED). The per-phase boundary reviews caught phase-local defects; this catches what only
   appears once the phases combine — a Phase-A interface a later phase quietly violated, a global invariant
   that only breaks in aggregate, a regression a later phase introduced into earlier phases' code, a
   requirement that fell between phases. This is **not a new methodology** — it's `/fabrik-review` over the
   whole plan. Fix + re-review to a clean pass before you proceed to archive.
2. **Gate green (fresh, this turn)** — `python scripts/final_gate.py --json` (Tier 2) shows
   `"status":"success"`; fix to green first. Run it **now**, in the finishing turn — never cite an earlier
   run (freshness, CLAUDE.md FINAL OUTPUT). **Cross-check the step-8 baseline:** any check that was *already
   red at start* is a sibling's / an untracked file's — say so and do **not** fix it (shared-master
   discipline); only a **newly**-red check is yours.
3. **Requirements coverage — gate-green is NOT requirements-met.** Re-read the plan and checklist each
   item you agreed to deliver (every `Interfaces.Produces` and each "What we already agreed" line) against
   what actually shipped: point to the commit/file that delivers it. Report any gap explicitly — a passing
   gate does not prove the plan's intent was built (it proves format + the tests you wrote pass). Don't flip
   `Status: EXECUTED` with an un-delivered requirement unaccounted for.
4. **Clean up your OWN worktree only** — if THIS run used its own worktree (step 8, concurrent run): resolve
   the MAIN checkout first (`MAIN=$(git worktree list --porcelain | sed -n '1s/^worktree //p')` — never
   dirname-of-`--git-common-dir`, which is a `.git` DIRECTORY, not a checkout), **step your shell OUT of
   the worktree being removed** (`cd "$MAIN"` — a shell sitting inside it makes the remove fail), then
   `git -C "$MAIN" worktree remove <path>` + `git -C "$MAIN" worktree prune`. **Provenance guard:** remove only a worktree THIS run
   created — never a harness-owned or a sibling's tree. (The Merge Protocol already deletes the *subagent*
   branches; this is the *orchestrator's own* worktree.)
5. **Release + record** — set `.fabrik/plan-locks/<id>.json` `status:"released"` (+ `completed_at`,
   `final_commit`), flip the plan `Status: EXECUTED <date>`, **and cite the step-1 whole-plan review artifact
   in the completion stamp** — a `Whole-plan review: docs/development/reviews/<the step-1 review>.md` line.
   This is not bookkeeping: **`check_convergence.py` FAILS the gate on any plan that claims `EXECUTED` (in
   `plans/` OR `plans/archived/`) unless it cites a review artifact that EXISTS on disk and shows a
   coverage-adjudicated exit** (a `Coverage Checklist` + a final `found: 0` pass). The citation is the proof
   the step-1 loop actually ran to a no-op; without it the status flip is unproven and the archive in step 6
   is blocked. Then output the completion block above.
6. **Archive the plan — ONLY when 100% verified done.** The plan is finished only when ALL of: the
   whole-plan review (step 1) came back clean, the final gate (step 2) is green THIS turn, and requirements
   coverage (step 3) accounts for every agreed item. Then archive: a monolith plan moves as
   `git mv docs/development/plans/<plan>.md docs/development/plans/archived/<plan>.md`; a spine+ticket
   plan SET moves as a **whole-directory** `git mv docs/development/plans/<dir>
   docs/development/plans/archived/<dir>` (spine, tickets, and Board travel together — never the
   single-file move, which strands the tickets as gate-flagged orphans). Explicit paths either way;
   repoint the lock's `plan` field to the
   archived path. ⚠️ **`git mv` moves the INDEXED content, not your working tree — re-stage the plan
   AFTER the move:** `git add docs/development/plans/archived/<plan>.md`. ⚠️ **And the scoped commit
   must name BOTH paths** — `git commit -- <old-path> <new-path>` — or the deletion half of the
   rename stays staged-uncommitted and the plan lives at TWO paths in HEAD (youtube `01M1584B0`;
   the constitutions carry the same clause at the realign rule). Step 5's `Status: EXECUTED`
   flip is an unstaged working-tree edit, so the rename carries the OLD bytes and the archived plan
   commits as `IN-PROGRESS` while your tree shows EXECUTED. The commit says `rename … (100%)`, which
   is the tell. No gate caught it: an IN-PROGRESS plan is simply out of scope for the EXECUTED
   contract, so a plan can be archived — a claim that nothing is left — while its own status says
   work continues, and every check stays green (tryton-crm, 2026-08-28; `check_convergence` now flags
   archived-but-not-EXECUTED as the backstop). **Never archive a plan with an open requirement gap, an un-green gate, or an unresolved
   review finding** — archiving IS the "I am 100% sure this is done" act, and a plan in `archived/` is a
   claim that nothing is left. Commit the move with the plan-status commit (explicit paths).
7. **Push, then name the one decision left.** The commits are on `master` — **PUSH them now** (`git push`;
   the task-end law: rejected → dirty tree: defer + report, wip-net protects · clean tree:
   `git pull --rebase=merges` then push (preserves the Merge Protocol's `--no-ff` merge commits —
   plain `--rebase` linearizes them away) · conflict: abort + report · NEVER `--force`). The only remaining
   operator call is **deploy**: `fabrik redeploy` / `fabrik apply` is **hub-side + user-run**
   (trigger-not-execute) — name it as the next step, don't run it. Don't trail off with "what next?" —
   push, name the deploy decision, stop.
