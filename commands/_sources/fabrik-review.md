---
description: Adversarial code review of the CHANGED SURFACE (diff/PR/branch) — independent finders → refute false positives → prove & fix with regression guards → LOOP until every Coverage-Checklist class is CLEAN/FIXED/REFUTED and a full fresh round returns found: 0 (no round cap). TRIGGER — EN: "review this diff", "is this PR safe to merge"; TR: "bu diff'i incele", "bu değişiklikleri gözden geçir" — fires on a changed-surface review, not a whole-repo one. SKIP: whole-repo audits (→ /fabrik-repo-review), rules-pack compliance (→ /fabrik-rules-review), Traycer artifact convergence (→ /fabrik-workflow-review), rendered-UI review (→ /design-review). Stage: gate.
argument-hint: "[path, PR number, or git range — omit to review the working-tree/branch diff]"
---

Review this implementation as an adversary trying to break it, optimizing for RECALL
first and then DEPTH.

{{include:term-coverage}}
{{include:grounding-code}}
## Phase 0 — Establish scope

### ⚠️ Synced files — CONTEXT, never a TARGET (settle this BEFORE dispatching finders)

**Am I in the HUB or a PROJECT?** → `git rev-parse --show-toplevel`.

**PROJECT** (repo root ≠ `/opt/fabrik`) — the centrally-distributed set is **read-only** here (gate:
`scripts/enforcement/check_synced_unmodified.py`). Get the list **mechanically; never hand-copy it**
(⚠️ `fabrik_synced_manifest.py` is NOT synced into projects — use the project's own lock):

```bash
# The lock records exactly what was distributed to THIS project (~190 paths). PORTS.md is
# SEEDED_NOT_ENFORCED — projects may edit it, so it stays a normal review target.
python3 -c "import json;print('\n'.join(sorted(json.load(open('.fabrik/synced.lock')))))" | grep -vx 'PORTS.md'
# Covers: AGENTS.md · CLAUDE.md · .windsurfrules · AGENTS-compact.md · .windsurf/rules/** (all packs)
#         scripts/enforcement/** (all checks — counts drift, list is computed) · final_gate.py · select_rules.py · review_rubric.py · hooks · reference docs
```

- **ARM the finders — run `python scripts/review_rubric.py --changed <the diff's paths>` and INJECT its
  output into EVERY finder's prompt as the rubric they hunt against (G5/G6: an un-armed reviewer measured
  ~0–22% defect recall; the injected rubric is the root-cause fix).** The rubric carries two layers:
  **(1) the mandatory-core floor** — `core/35-security-auth` + `core/25-data-postgres` + `core/30-ops` +
  all twelve 12-Factor axes — ALWAYS injected regardless of glob and never skippable, so a review is never
  un-armed on the high-blast-radius rules; **(2)** every pack whose glob matches a changed path (mandate
  lines only). The whole rubric is computed fresh by the script; nothing is inherited from the doer.
  Honesty (L1): the injection STEP is maximally enforced (the rubric is always injected); this raises
  compliance probability — it does **not** make compliance guaranteed. The packs remain BINDING CONTEXT you
  may read in full for depth — **Context ≠ target.**
- **NEVER** review their *contents* as a target, raise findings against them, or "fix" one. An agent that
  helpfully edits a synced file **creates the exact drift the gate exists to catch** — and the next sync
  overwrites it anyway. Wasted review budget at best, a Tier-1 violation at worst.
- **A synced file appearing IN THE DIFF is ITSELF a CONFIRMED finding:** *"synced file modified —
  `git checkout -- <path>`, then propose the change upstream in `/opt/fabrik` (it is correct for ALL projects
  or it is not correct)."* Do **NOT** silently exclude it — excluding **hides** the violation.
- **`PORTS.md` is the exception** (`SEEDED_NOT_ENFORCED`): projects MAY edit it → review it normally. This is
  exactly why the list is **computed, not written by hand**.

**HUB (`/opt/fabrik`)** — these files **ARE the product**, and they carry the **widest blast radius in the
system**: every rule pack + enforcement check propagates to every project on the next sync. **Review them
HARDER, not less**, through a fleet lens:

- Does this break a project that does **not** have feature X? Is it backward-compatible?
- Does this rule **contradict another pack**? (a pack that fights another is worse than no pack)
- Does an enforcement change **false-positive on a legitimate pattern**? (a gate that cries wolf gets
  `# noqa`'d into uselessness — that is how a check dies)
- Proven live: review is what caught a **hallucinated Kubernetes section** and a **fleet-breaking SQLite ban**
  before they reached 39 projects. Excluding these files from review would have shipped both.

**Seeded-repro contract:** if invoked with a committed red repro (a `repro: <path>` seed from a
certification gauntlet or any caller), that failing test is the review's PRIMARY target: it anchors the
diff scope (the committed repro is IN the diff, pulling the buggy module into scope via callers/callees),
and **this review MAY NOT exit until that repro is GREEN** — paste its green run output verbatim in the
review file. Adjudicating every checklist class while the seeded repro stays red is NOT a valid exit.

If an argument was given, treat it as the review target: `$ARGUMENTS`
(a path, a PR number, or a git range). Otherwise get the diff under review with
`git diff @{upstream}...HEAD` (fall back to `git diff main...HEAD`, then
`git diff HEAD~1`); if there are uncommitted changes or the range is empty, also
run `git diff HEAD` and include the working tree. The scope is the full changed
surface (the diff) PLUS everything it calls or is called by — trace callers and
callees, and read the whole enclosing function of each hunk (bugs in unchanged lines
that a change re-exposes are in scope).

## Phase 1 — Independent finders (recall)

Dispatch several independent finder subagents in parallel, **each committing to a DIFFERENT subset of
failure classes** before seeing the others' results. **Worker: run BOTH layers for any substantial review —
never either/or (per `62-using-subagents.md` § Dispatch policy).** The **pool breadth layer is MANDATORY**:
dispatch cheap pool finders via **`fanout("review", …, mode="read_only")`** in parallel — it picks the
**flywheel-ranked** reviewers for the `review` task from the per-task selection table (below); **do not name a
model** — for differently-biased recall breadth that **auto-records to the flywheel** — **AND, added ON TOP (never instead)**,
**native `fabrik-reviewer`** (Opus) for the authoritative/high-risk pass (auth / `internal_auth` / migrations /
schema / secrets / concurrency) + the decide/refute/merge you own. A high-risk surface needs the pool breadth
*plus* the native pass; going all-native (skipping the pool layer) lands **zero** flywheel rows and
`check_subagent_flywheel.py` advisory-WARNs it. (Evidence it earns its cost: cheap pool finders have caught
real bugs that an Opus-only self-review missed — complementary recall, not redundant.) The two mechanisms:

- **Claude finders (native · subscription · the authoritative pass):** the **`fabrik-reviewer`** Claude Code agent
  (`subagent_type: "fabrik-reviewer"`). **Floor — at least one Opus, ALWAYS:** every review dispatches **≥1 native
  `fabrik-reviewer` on Opus** (`model: "opus"`) as the authoritative pass, **regardless of diff risk** — the pool
  never runs Opus (no `anthropic/*`), so this native Opus finder is the review's only Opus eyes and pool-only is
  **not a valid review**. **Add** cheaper native finders for extra recall breadth — **Sonnet** routine, **Haiku**
  trivial — but the Opus finder is mandatory, not conditional. Recall matters most where a missed bug is expensive.
- **OpenRouter finders (the pool — Claude *and* OpenRouter models via one API):** when `libs/subagents/` is
  vendored, dispatch through the pool via **`fanout`** — it replaces the hand-rolled `run_agents`+`AgentSpec`
  boilerplate (family-diverse model pick, parallel-safe, auto-recorded):
  `fanout("review", units=[<unit code + "find bugs, cite path:line"> …], repo=…, project="review", mode="read_only", system=methodology("review"), max_turns=2, max_cost_usd=0.25, wall_clock_s=600)`. `mode="read_only"` IS the single-shot review finder — it sets `tools_enabled=False`+`allow_ungrounded=True` for you (you attest each unit inlined its code into the task text); use `mode="write"` only if a finder needs real file reads.
  `fanout`/`pick_models` return the **flywheel-ranked** models for the `review` task (from the per-task
  selection table below) and **never `anthropic/*`** — Claude via OpenRouter bills per-token and
  is expensive; for a Claude reviewer use the **native** finder above (subscription). **There is no always-on
  price cap** — pass `max_cost_per_mtok=` only if you want an explicit budget ceiling for a run. **After you adjudicate each run, back-fill the flywheel:**
  `set_quality(r.agent_id, <0–5>, project="review", task_type="review", model=r.model)` (⚠️ never `record_run`
  — it silently no-ops; `fanout` already recorded the row UNSCORED, `set_quality` scores it) so the flywheel
  learns which model reviews well.
  **Trust policy — the METHODOLOGY, not a model pin (README):** a review's trust does NOT come from which pool
  model ran; it comes from **≥1 native Opus finder as the authoritative decider + every pool finding
  independently refuted before it is acted on** (both hold regardless of roster). `fanout("review", …)` returns
  the flywheel-ranked, empirically-proven reviewers from the per-task table below — trust *those numbers*, not a
  frozen name. A never-run `[benchmark]` candidate in the table's tail may appear in a large fan-out: harmless —
  it adds recall breadth, is scored into the flywheel, and its findings are refuted like any pool finding (no
  pool finding is authoritative on its own).
- **NEVER hand-roll a raw `ai-consult` / OpenRouter call for a finder.** The pool *is* ai-consult **plus**
  worktree containment, caps, and the `fanout`→`set_quality` flywheel — bypassing to ai-consult throws all of that away
  and `pick_models` learns nothing. Use `fanout`. (And verify any model you name exists — don't invent version
  strings; the authoritative roster is the per-task selection table, not memory.)

**📋 Per-task model selection — READ THE TABLE, don't hardcode.** The roster is NOT pinned in this command. The
canonical, auto-refreshed, flywheel-ranked table lives at **`/opt/fabrik/docs/reference/kilo/TASK_SUBAGENT_SELECTION.md`**
(one ranked section per task type: `code · docs · plan · research · review · spec`, each row = `shrunk_q ·
success · avg_cost · n`; `[benchmark]` = never-run candidate). `pick_models`/`fanout` **read this table
automatically** to select — so "the agent looks in the table" is already true in code. When you need to *see*
today's ranked reviewers (e.g. to justify a pick or spot a benchmark), read that file or call
`pick_models("review")`. Any model name or `$X` cap written into prose has FROZEN a snapshot the table has
since moved past — that drift is exactly the bug this points-at-the-table rule prevents.

YOU (the dispatching session) remain the refute/merge/decide-clean and
prove-and-fix authority — the finders only report. (If neither mechanism is available, run genuinely
independent passes and do not let a later pass narrow an earlier one.) Cover, across the finders: logic errors, off-by-one,
null/empty/None handling, idempotency, effective-dating/ordering, fail-open vs
fail-closed, error/edge paths, concurrency & transaction atomicity, resource cleanup,
auth/tenant-isolation, precision/timezone/encoding, removed-guard / removed-behavior
regressions, cross-file contract breaks (changed signature / return-shape /
precondition / new exception), **test quality** (does each test actually prove its claim,
or pass trivially?), **12-Factor violations** (its own checklist below — one finder MUST own
this class), and plan↔code deviations (verify against the spec's INTENT, since
the written spec can itself be wrong). Each finder surfaces every candidate with a
concrete, nameable failure scenario — do NOT drop half-believed candidates; that is
the dominant cause of misses.

**Test-quality checklist (the finder covering tests applies all of these — a test that ships green while
the behavior is broken is a defect):** would the test still PASS if the feature/fix were reverted? (if yes,
it proves nothing — it was written after the code and never watched fail); asserting on **mock behavior** /
`*-mock` test IDs instead of real behavior; **test-only methods on production classes** (a method only ever
called from tests); **over-mocking** that removes a side-effect the test depends on (mock at the wrong
level → passes for the wrong reason); **incomplete mocks** (fewer fields than the real API returns → passes
in test, fails in integration); mock setup that is >50% of the test. Flag any of these as a test-quality
finding. **When a finding hinges on what a 3rd-party library / SDK / API *actually* returns** (an incomplete
mock, or a cross-file contract break against an external signature), confirm the real shape with
`mcp__context7` (library docs) rather than asserting it from memory — the only place this code-vs-code review
reaches for an external tool.

**12-Factor checklist (one finder OWNS this class — these are GREPPABLE, so there is no excuse for missing them).**
Every item below is a **CONFIRMED defect** if present, not a style nit. The rule packs
(`.windsurf/rules/core/{10-python,12-node,25-data-postgres,30-ops,45-testing-strategy,55-observability,75-workers-jobs,76-gpu-workers}.md`)
carry the full mandates; this is the hunt list:

| # | Grep for | Why it's a defect |
|---|---|---|
| XI | `FileHandler`, `RotatingFileHandler`, `TimedRotatingFileHandler`, loguru file sink, `pino.destination('*.log')`, `winston.transports.File`, `fs.createWriteStream` for logs, any `*.log` write, in-app log rotation | The app must **never write or manage a logfile**. Unbuffered JSON → `stdout`; Docker → Promtail → Loki owns routing/retention. |
| XI | a service `compose.yaml` with **no `PYTHONUNBUFFERED`** | Python block-buffers stdout to Docker's log driver ⇒ an OOM-killed process **loses its own crash logs**. |
| VIII | `daemon=True`, double-fork, `.pid` file writes, `supervisord`/`pm2` inside the container | Never daemonize / write PID files. **Carve-out:** `tini` as PID 1 and the Adaptive Worker Pool's forked children are *mandatory* Fabrik patterns — **not** violations. Don't false-positive them. |
| IX | a worker SIGTERM handler that **drops or leaves locked** its in-flight job; a non-idempotent job handler | On SIGTERM a worker must **return the in-flight job to the queue** (reset the row to `pending`); jobs must be reentrant. Dropping it = data loss (or a ~10-min orphan-sweep stall). |
| VI | Traefik `loadbalancer.sticky.*` label; in-process/file-based sessions | **Sticky sessions are a 12F violation.** Session state → `redis-main` (+ the spec must set `shape.needs_cache: true`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken). |
| X | `sqlite:///`, `:memory:`, `fakeredis` used as a **server-side** backing service (incl. in tests) | Dev/test/prod run the same backing services. **Scope carefully:** `desktop-app`/`mobile-app` **client-local** SQLite (SQLCipher / expo-sqlite) is *mandated* there — **not** a violation. |
| XII | `alembic upgrade head` in FastAPI `lifespan` / `@app.on_event("startup")` / an import side-effect | Concurrent replicas **race the Alembic version table** → wedged deploy. Migrations are a one-off process against the deployed release. |
| III | secrets/config constants in code; a `config/production.yml` or `settings.production` **grouped env set** | Config is env vars, granular + orthogonal. Litmus: *could this repo be open-sourced right now without leaking credentials?* |
| VII | host `ports:` in `compose.yaml` | Bind the port in-container; **Traefik routes.** |
| V | `docker exec` to edit code/config in a running container; any runtime code mutation | Releases are **immutable**; the git SHA is the release ID. |
| II | `subprocess`/`spawn` of a binary (`ffmpeg`, `yt-dlp`, `poppler`, `tesseract`) that is **not installed + pinned in the Dockerfile** | Works in WSL (dev's PATH), `FileNotFoundError` in the container. Vendor the tool + `shutil.which()` probe at startup. |

## Phase 2 — Verify / refute (kill false positives)

Dedup near-duplicates. For each remaining candidate, try to REFUTE it from the code:
mark REFUTED only when it is provably impossible (quote the type/constant/invariant/
guard that prevents it), factually wrong (quote the actual line), or already handled in
this change (cite the guard). Otherwise keep it as CONFIRMED or PLAUSIBLE — do not
refute something merely for needing a "rare but reachable" state (error handler, cold
cache, missing optional field, race, falsy-zero, boundary, retry / partial failure,
lost regex anchor). A defect the code's own author cannot see is exactly what this step
exists to catch, so do not defer to the implementation's apparent intent.

## Phase 3 — Prove & fix (depth) — every survivor terminates FIXED or REFUTED

Every finding that survived Phase 2 — **CONFIRMED and PLAUSIBLE alike** — must reach one of exactly TWO
terminal states. **There is no third "noted / probably fine / to-watch / deferred" state, and the user does
NOT accept an unfixed CONFIRMED or PLAUSIBLE finding.**

- **FIXED** — reproduce it with a runnable test/execution FIRST, fix it, keep the test as a regression guard
  (verify red→green). A deliberate design decision that resolves it (e.g. choosing fail-open with a logged
  warning) counts as FIXED **only if you actually made the change and recorded why**.
  - **A test that passes because the environment cannot express the failure has proven nothing** —
    "it passed locally" is not evidence when local is the one place the bug is unreachable (a superuser
    role for an RLS bug, no concurrency for a race, one tenant for an isolation bug). Reach for the
    missing constraint **in a throwaway/ephemeral instance you own** — a scratch DB, a local container,
    a disposable account. **NEVER** degrade shared or paid infrastructure to manufacture a red
    (`postgres-main`/`redis-main` and the VPS fleet are shared; real vendor quota is the operator's
    money) — if the only way to see the failure is to break something shared, say so in the finding
    instead. This changes what counts as proof; dispositions below are unchanged.

- **REFUTED** — you did the work to PROVE it cannot happen: quote the guard / type / invariant that makes it
  impossible, or the exact line that makes it factually wrong. Promoting a finding to REFUTED requires
  proof, not a shrug.

**PLAUSIBLE is not a licence to skip — it is the opposite.** PLAUSIBLE means "reachable but not yet proven,"
so the burden is on YOU to discharge it. **"I couldn't reproduce it" is NOT a terminal state:** either
fix it defensively (the failure is real-if-rare and the guard is cheap — a `None`-check, a `try/except`, a
bound) or do the work to REFUTE it. Leaving it un-fixed and un-refuted means the review is **not done**.
(This is the exact failure this command exists to stop: finders raise PLAUSIBLE findings and the controller
quietly drops them.)

**A real finding does not make the obvious fix correct — verify the FIX, not just the finding
(`receiving-code-review`).** Before applying any fix — yours, or one a finder *proposed* — check it against
THIS codebase: does it break an existing caller or a documented invariant? is there a reason the current
code is the way it is (legacy/compat/perf)? is the "do it properly" version **YAGNI** (grep for real usage —
if nothing calls it, the correct fix may be "delete it," not "build it out")? A **wrong fix to a real
finding is itself a defect**, and cheaper finders/implementers propose more of them — treat a finder's
suggested fix as an *external reviewer's suggestion to verify*, never an order to transcribe. If the finding
is real but its proposed fix is wrong, implement the correct fix (or, when the current behavior is actually
right, REFUTE the fix with the reason). **Never apply a fix you can't stand behind just to clear the
ledger** — no performative "fixed."

Classify each as correctness/security vs. style — correctness/security outranks style — but a style finding
is still FIXED or REFUTED, never ignored. Re-run the project gate/test suite after EACH fix (fixes regress);
green is necessary, NOT sufficient — it does not test logic, so never cite it as proof of correctness.

## Phase 4 — Converge (the loop — you are here after EVERY pass, not once)

Log the pass you just finished in the **Pass Ledger** (Reporting: its `found`/`fixed` counts), then decide:

- **This pass found or fixed anything** → you are **structurally not done**. Go back to Phase 1 and run a
  fresh, fully-independent finder round on the updated code (the fixes themselves can introduce defects).
  Do not skip this because the change was small or "obviously safe" — that judgment is exactly what the
  next round exists to check.
- **Every Coverage Checklist row is adjudicated** (CLEAN / FIXED / REFUTED), the last code-changing pass has
  had its touched classes re-checked, and the mechanical gates are green → **EXIT** (the Termination
  contract's conditions). This — not an empty pass — is the ONLY thing that ends the review and lets the
  caller (e.g. `/fabrik-execute-plan` at a phase boundary) proceed. A finding stuck after 3 fix attempts:
  BLOCKED-escalate it per the contract and keep looping on the rest.

**The round in which you made a fix is NEVER the last look at the classes it touched.** "I fixed what the
first pass found" is not an exit — those classes return to UNCHECKED until a fresh round re-adjudicates them.

## Behavior Contract test generation — the pool authors, you curate (the fix for an untested behavior)

When Phase-3's test-quality check finds a **behavior with no test** (or the plan's Behavior Contract has uncovered behaviors), generate the missing tests via the pool — cheap where cheap works, you where judgment matters (per `62-using-subagents.md` § Dispatch policy + `.windsurf/rules/core/45-testing-strategy.md`):

1. **Suggest (pool, multi-model)** — `fanout("review", units=[<the same suggest task, code inlined> ×3], mode="read_only")` (3 UNITS → 3 agents on 3 diverse families — one unit = ONE agent; `k` only sizes the model draw, never the fan-out) to each propose the distinct user-observable behaviors; **union** them. A single suggester is the blind spot — diverse families catch what one misses, for cents.
2. **Curate (you)** — evaluate the union: add missing behaviors, cut trivia/dupes, risk-order. You own *what* gets tested (the anti-bloat + anti-gap gate) before any authoring spend.
3. **Author (pool, parallel)** — `fanout("code", units=[{"task":…, "owned_paths":[<test file>]}, …], mode="write")` — one cheap **pool** author per curated behavior, **disjoint `owned_paths`** so each writes its own test file in parallel. ⚠️ Tool-enabled authors see committed **HEAD** (`workspace.py` `worktree add --detach HEAD`) — **commit the code-under-test first** (or inline it), and each author **self-verifies collection** (`pytest` on its new test) before returning.
4. **Report + score** — `fanout` returns `(results, results_table)` and auto-records each author UNSCORED; **back-fill** `set_quality(r.agent_id, <0–5>, project=…, task_type="code", model=r.model)` per author (⚠️ never `record_run`, which no-ops; `check_subagent_flywheel.py` WARNs on a pool run left unscored).
5. **Fix (you)** — review test-quality (would it fail if the behavior broke? real assertions, no mock-theater?), fix issues, then `FABRIK_MUTMUT=1 python scripts/enforcement/check_mutation.py` on the **applied** code to confirm the tests kill mutants (advisory). You own final quality.

So "test every behavior" (the Behavior Contract) costs **cents + minutes**, not hours of hand-writing — the maintenance-burden objection dissolves. (Proven 2026-07-08: a `pick_models("review")` suggest run proposed the 3 behaviors of a `clamp(x,lo,hi)` for $0.0019 and recorded a flywheel row.)

{{include:subagents-core}}
## Reporting

After each pass, show exactly what you inspected (files/paths + which failure classes) and what you found;
a pass that finds nothing must still enumerate that coverage — an empty pass with no evidence doesn't count.

**Both exit proofs live in `docs/development/reviews/YYYY-MM-DD-<scope>-review.md` (created before Pass 1 per the Termination contract) — the adjudicated Coverage Checklist (every row: verdict + evidence naming the files/paths hunted) AND the numbered Pass Ledger. Chat output is a courtesy copy; the FILE is the review:**

```
Pass 1 — finders: <classes covered> | found: 3 (2 CONFIRMED, 1 PLAUSIBLE) | fixed: 3 | → not done (changed code)
Pass 2 — finders: <classes covered> | found: 1 (1 PLAUSIBLE)            | fixed: 1 | → not done (changed code)
Pass 3 — finders: <classes covered> | found: 0                          | fixed: 0 | → EXIT (checklist fully adjudicated)
```

You may claim completion **only** when the last row is `found: 0 | fixed: 0`. A ledger that ends on a row
with a non-zero found/fixed count is an unfinished review — run the next pass. A ledger with a single row
is only valid if that row is `found: 0 | fixed: 0` from a demonstrably-thorough pass.

**Emit a per-finding disposition ledger — this is what makes a skipped finding impossible to hide.** Every
candidate raised by any finder across all rounds appears as one row ending in exactly ONE terminal state:
`FIXED` (cite the commit + the regression test) or `REFUTED` (quote the proof). A finding that appears in no
row — or sits in a "noted / to-watch / residual / accepted" bucket — **is a skipped finding**, the exact
failure this command exists to prevent. Count them: `N findings → N FIXED + N REFUTED`, and the two must sum.

**"Residual risks" is NOT a parking lot for PLAUSIBLE findings.** It may hold ONLY: (a) pre-existing issues
this change did not introduce (inherited, genuinely out of scope — say so); (b) findings in code this change
does not OWN that you EXPLICITLY escalated / upstreamed (name where — e.g. an `UPSTREAM_FEEDBACK.md` entry);
(c) deliberate, documented design tradeoffs that a FIX decision already resolved. An in-scope CONFIRMED or
PLAUSIBLE finding **never** belongs here — it goes to FIXED or REFUTED.

Do NOT claim convergence on your own say-so: convergence = a full independent finder round that **found
nothing new AND changed nothing** (zero new CONFIRMED **or PLAUSIBLE** findings, zero fixes) **AND** every
finding ever raised sits at FIXED or REFUTED in the ledger. "I fixed what I found" is not convergence. When
unsure whether something is a bug, surface it and discharge it — never assume it's fine.
