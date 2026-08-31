---
description: Adversarial code review of the CHANGED SURFACE (diff/PR/branch) — independent finders → refute false positives → prove & fix with regression guards → LOOP until every Coverage-Checklist class is CLEAN/FIXED/REFUTED and a full fresh round returns found:0·new:0 with every candidate adjudicated (re-raises of adjudicated standing rows cited, not counted; no round cap). TRIGGER — EN: "review this diff", "is this PR safe to merge"; TR: "bu diff'i incele", "bu değişiklikleri gözden geçir" — fires on a changed-surface review, not a whole-repo one. SKIP: whole-repo audits (→ /fabrik-repo-review), rules-pack compliance (→ /fabrik-rules-review), Traycer artifact convergence (→ /fabrik-workflow-review), rendered-UI review (→ /design-review). Stage: gate.
argument-hint: "[path, PR number, or git range — omit to review the working-tree/branch diff]"
---

Review this implementation as an adversary trying to break it, optimizing for RECALL
first and then DEPTH.

{{include:term-coverage}}
{{include:grounding-code}}
## Run record — open it FIRST, keep it current, close it only at the no-op round

This command has **5 phases (0–4)** and exactly one terminal condition, and it has TWO parts that are BOTH required (neither alone is enough — see § Termination): **a full fresh round that
returns **`found: 0 · new: 0`** with every candidate ever raised adjudicated** (a re-raise of an
already-adjudicated STANDING row is cited in its row, never counted — see § Reporting). Open the record before Phase 0 does anything else:

```bash
python3 scripts/command_run.py start --command fabrik-review --phases 5 \
  --terminal "found:0 no-op round"
```

Then, for the whole run: `step --phase <N> --title "<the phase title>"` on entering each phase, and
**one `round` call per Phase-4 pass** —
`python3 scripts/command_run.py round --findings <this pass's found count> --classes-swept <the
Coverage-Checklist classes this pass swept CLEAN> --classes-new <classes this pass opened>`.
The class ledger persists across rounds: **re-sweep it, never re-scope it** — a pass that invents a
fresh brief is why a review runs 30 rounds instead of 4. When a round sweeps every known class with
`--findings 0`, `command_run.py` prints the TERMINAL verdict; **only then**
`done --command fabrik-review --evidence "<the round number + its found:0 · new:0>" --feedback "<what you filed, to whom | none — surfaces exercised>"`. A genuinely stuck
review exits via `blocked --command fabrik-review --reason "…" --feedback "<what you filed, to whom | none — surfaces exercised>"` on one of the three sanctioned cases —
never by simply stopping. **Always name the run you close**: a bare close would end whatever is live,
which after this review pops back to its CALLER (`/fabrik-execute-plan`) means silently ending the
plan. A mismatched name is refused; closing an already-closed run is a warned no-op.

**Open the `RUN:` line (`python3 scripts/command_run.py line`) on every reply until this run closes.**

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
**Third exit — REPRO-DEFECTIVE:** a committed red repro is a claim, not proof; it can itself be
rig-defective (asserting the wrong key casing, a field the contract never promised, a stale selector).
If this review proves the repro's assertion contradicts the contract — cite the schema/contract line
PLUS the actual wire/state evidence — the valid exit is to **fix the REPRO** (green against the
service's real, contract-conforming behavior; paste that green run) and return the row to the caller
as **REFUTED-RIG**. What is NEVER valid: "fixing" correct code into agreeing with a broken assertion
to satisfy the green-repro contract.

If an argument was given, treat it as the review target: `$ARGUMENTS`
(a path, a PR number, or a git range). Otherwise get the diff under review with
`git diff @{upstream}...HEAD` (fall back to `git diff main...HEAD`, then
`git diff HEAD~1`); if there are uncommitted changes or the range is empty, also
run `git diff HEAD` and include the working tree.

⚠️ **A FINDER GIVEN A SHA MUST NOT READ THE LIVE TREE — it is probably dirty, and not with your
changes.** This hub runs three concurrent sessions plus a daily pipeline, so at any moment the working
tree carries siblings' uncommitted work. A finder handed `HEAD <sha>` and pointed at the live tree
silently reviews THEIR half-finished code as if it were the surface under review, and reports findings
against lines that are in no commit. Live case (fabrik-lib `01M15081Q5`): an Opus finder ran three probes
against the tree, got results contradicting the source it had read, and caught it only because a token it
observed did not exist at the sha it was given — it could as easily not have noticed.

**So when you hand a finder a sha, materialise that sha:**

```
$ git archive <sha> | tar -x -C <scratchpad>/review-<sha>
```

and brief the finder against that path. If a finder must read the live tree instead (a working-tree
review, `git diff HEAD`), say so IN the brief so the finder knows what it is looking at. This is the
same class as the `Surface:` anchor rule — both are about the finder actually looking at the thing it
was told to look at.

The scope is the full changed
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
`check_subagent_flywheel.py` BLOCKS it (exit 1) on a substantial code change, unless the run declares `NO-POOL: <reason>` in an in-cycle commit message or sets `FABRIK_NO_POOL`. (Evidence it earns its cost: cheap pool finders have caught
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
prove-and-fix authority — the finders only report. When adjudicating a caller/impact claim
("nothing else calls this", "every consumer handles None"), derive the call-site list with the
`serena` MCP (`find_referencing_symbols` — real references, not name collisions) before ruling;
`Grep` remains the tool for strings, config and prose the language server doesn't index. (If neither mechanism is available, run genuinely
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
a `WebFetch` of the library's official docs rather than asserting it from memory — the only place this code-vs-code review
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
  warning) counts as FIXED **only if you actually made the change and recorded why** — and that disposition
  is decision-shaped: **mint its `docs/DECISIONS.md` row staged in the fix commit** (CLAUDE.md § the
  decision ledger; a mechanical bug-fix stays row-less — the carve-out class).
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
- **Every pool row this review dispatched is `set_quality`-scored — a round with unscored pool rows is
  NOT closed.** The back-fill has the same rank as the refute step, per round, not "at the end":
  dispatch guarantees the row, so a skipped back-fill leaks 100% of the time (measured 2026-08-12:
  `done`-status rows sat at 40.9% scored — the single largest flywheel leak, and the scoring moment is
  exactly when attention leaves the finders for the diff). Adjudicate → `set_quality` → only then the
  round is closed. Zero pool dispatches this round (native-only for a secrets surface) → nothing owed.

**The round in which you made a fix is NEVER the last look at the classes it touched.** "I fixed what the
first pass found" is not an exit — those classes return to UNCHECKED until a fresh round re-adjudicates them.

**Record the pass before you decide:** `python3 scripts/command_run.py round --findings <found> \
--classes-swept <classes swept CLEAN this pass> --classes-new <classes this pass opened>`. Its TERMINAL
verdict — every known class clean, `--findings 0` — is the machine-readable form of the EXIT above, and
its NON-CONVERGENCE warning names the failure mode this loop actually has: re-scoping instead of
re-sweeping. Close the run at that verdict with
`done --command fabrik-review --evidence "round <n> quiet: found:0 · new:0, all adjudicated" --feedback "<what you filed, to whom | none — surfaces exercised>"`.

## Behavior Contract test generation — the pool authors, you curate (the fix for an untested behavior)

⚠️ **`/fabrik-generate-tests` is CANONICAL for this pipeline — invoke it** (`/fabrik-generate-tests <the
phase's Behavior Contract | the module>`) rather than hand-running it. The steps below are the SAME BYTES
it runs — both files render them from one shared fragment (`commands/_fragments/test-generation-loop.md`),
so they cannot drift out of step with the command that owns them. They are shown here because a reviewer
mid-loop needs the shape without leaving the page, NOT as a second implementation; the per-step DETAIL
lives only in `/fabrik-generate-tests`. **Edit the fragment, never either copy.**

When Phase-3's test-quality check finds a **behavior with no test** (or the plan's Behavior Contract has
uncovered behaviors), generate the missing tests via the pool:

{{include:test-generation-loop}}

{{include:subagents-core}}
## Reporting

After each pass, show exactly what you inspected (files/paths + which failure classes) and what you found;
a pass that finds nothing must still enumerate that coverage — an empty pass with no evidence doesn't count.

**Both exit proofs live in `docs/development/reviews/YYYY-MM-DD-<scope>-review.md` (created before Pass 1 per the Termination contract) — the adjudicated Coverage Checklist (every row: verdict + evidence naming the files/paths hunted) AND the numbered Pass Ledger. Chat output is a courtesy copy; the FILE is the review:**

```
Pass 1 — finders: <classes covered> | found: 3 | new: 3 | fixed: 3 | → not done (changed code)
Pass 2 — finders: <classes covered> | found: 2 | new: 1 | fixed: 1 | → not done (changed code)
Pass 3 — finders: <classes covered> | found: 0 | new: 0 | fixed: 0 | → EXIT (the standing DESIGN-GAP
                                                   re-raise is CITED in its row, not counted)
```

Note pass 3: the finder DID re-raise the standing DESIGN-GAP row (an unbuilt endpoint, a missing
feature the run may not decide) — that re-raise is RECORDED in the disposition ledger row, citing its
standing adjudication, but **`found:` counts only candidates NEEDING adjudication**, so an
already-adjudicated re-raise never increments it. This is the ruling that reconciles the loop with its
graders (2026-08-31): `check_convergence.py`'s QUIET_PASS demands a `found: 0 · fixed: 0` pair and
`check_review_coverage.py` demands a quiet FINAL row — counting the re-raise made honest termination
impossible (transdoc, 2026-08-27), while suppressing it would hide a real observation; citing-not-counting
does neither. `new:` stays the stopped-learning signal.

You may claim completion **only** when the last row is `found: 0 · new: 0` from a demonstrably-thorough
pass, with every candidate ever raised adjudicated. A ledger ending on a row with fresh candidates is an
unfinished review — run the next pass. A ledger with a single row is only valid if that row is
`found: 0 · new: 0` from a demonstrably-thorough pass.

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
