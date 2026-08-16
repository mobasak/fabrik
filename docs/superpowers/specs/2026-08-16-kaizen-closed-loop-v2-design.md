# Kaizen closed-loop v2 — daily self-improving coding infrastructure

Status: CONVERGED
Date: 2026-08-16
Author: infra (Claude, /fabrik-spec) — operator: Özgür

## Goal

The operator's vision, verbatim (repeated ≥5 times, 2026-08-16): *"you are the authority of all
command files and coding infrastructure, your goal is to continuously monitor these, update commands
where needed, and present us the fastest, most accurate and correct, rules-obeyed coding
infrastructure."* Cadence requirement: **daily, not weekly.**

One operator runs ~46 projects through 10–12 concurrent AI agents (8 VS Code windows on a normal
day). They cannot review each agent's output; the only thing that scales is the machinery that makes
agents correct by default — the 203 governance artifacts this repo owns (27 command sources + 13
fragments, 56 rule packs, 57 gate checks, 5 hooks, 12 scaffold types, 12 fleet-synced core scripts,
21 crons). This spec designs the **closed loop** over that machinery: observe how agents actually
behave fleet-wide → find where they are slow, wrong, or rule-breaking → change the infrastructure →
prove the change helped — with autonomy **earned in stages**, never assumed.

**DONE WHEN** (for the system this spec designs; each milestone has its own gate in § Sequencing):
a daily cycle runs unattended that (a) measures agent behaviour from a typed event stream with
versioned, recomputable definitions — **including outcome metrics governance ceremony cannot move**,
(b) validates candidate infrastructure changes by replay or cohort exposure, (c) files or promotes
changes under the safety regime of § Layer 3, and (d) reports one terse daily verdict the operator
can read in under a minute. A cycle that reports "measured, tested, nothing safe and valuable to
change, guardrails green" is the loop **working**, not idling.

## Why v1 failed (the grounding for everything below)

- `kaizen_metrics.py` (shipped days before) read **one directory** — this repo's own review ledgers
  (grep `/opt/` in it: zero hits). It produced one row with 5 of 8 columns `—`, while 5,317 session
  transcripts (8.2 GB, 98 project dirs, ~91 sessions/day), a 3,292-row subagent ledger, and 237
  fleet review ledgers sat unread.
- `kaizen_collect.py` (shipped 2026-08-16, commits 29dc51b7 + e4ed9959) now reads the real record —
  and its first run produced **two instrument bugs** (100% failure rate from a wrong status
  vocabulary; a 1440-round ledger from a naive table regex) plus one confounded metric (the
  compliance denominator counts ~36 final blocks/session against a once-per-run contract).
- The v1 **actor** design ("fix daily, judge by next-day fleet mean, verify with the gate") was
  reviewed by 12 independent frontier models on one identical brief
  (`docs/archive/2026-08-16-kaizen-consultation-raw.md`, $2.40, 2026-08-16; 3 of the 12 are
  Claude-family, so "independent" is a family-diversity claim for 9). The panel's verdict, stated
  precisely: **every reviewer endorsed the epistemics** (dossier → worktree → independent verify →
  hypothesis → escalation) **and none accepted the control design as specified** — the wave-1 fusion
  ruled *"keep the instincts; do not ship the loop"*, the wave-2 fusion *"ship its instruments
  first, its proving ground second, and the actor last, in human-approve-everything mode"*; the
  friendliest individual reviews (o3-pro "directionally correct", kimi-k3 "shape fundamentally
  sound") conditioned it on the same instruments-first prerequisites. The named defects: it would
  revert good fixes on noise, and validate itself with a gate it is allowed to weaken.

## Chosen approach — three layers, autonomy earned per milestone

### Layer 1 — Measure truthfully

**Typed append-only event stream at the source.** The hooks and the run-record machinery — code that
already runs at every session boundary — emit one-line JSON events (`session_start`, `run_open`,
`phase`, `round`, `run_close`, `gate_run` **with per-check outcomes** (opus-5: the gate becomes a
diagnostic sensor array, "currently unexploited and nearly free"), `rule_activation` (which packs
fired for which globs — minimax: activation is unobservable today and is "the very first thing I
would verify"; without it the deletion evidence in Layer 3 does not exist), `stop_block` by cause,
`final_block_emitted`, `death`, `revival`, `operator_override` (fable-5: a marker the hooks
recognize, turning sanctioned skips from noise into labeled data)) to
`~/.claude/state/events/YYYY-MM-DD.jsonl`. Transcripts become *forensics*; the meter reads events.
Rationale: every metric defect found on 2026-08-16 is a parsing artifact of treating prose as data
(gpt-5.6-luna-pro; wave-1 fusion calls it the highest-leverage single item, and both wave-2 qwens
independently converged on an "event spine"). Emission is **fail-open and zero-dependency** (append
to a local file; never a DB, never blocking — a broken emitter must never break a session).

**The platform, not the agent, owns the run-record lifecycle** (minimax; qwen3.8-2.4t; elevated by
the wave-2 fusion: "if the agent opens/closes the run record, conformance is forgeable and the whole
compliance rebuild rests on sand"). Today the agent calls `command_run.py start/done` itself — a
live, checkable defect. M1 audits the path from slash-command to ledger row; closure becomes a
gate-verdict-controlled event, not an agent assertion.

**Versioned definitions + backward recompute, append-only** (the operator's own design, reconciled
with the panel's strongest objection): every metric definition carries a version; every published
number carries its definition hash. A definition change computes a **new versioned series** over
history and shows the divergence — **published series are never overwritten** (minimax: retroactive
recomputation "shifts every baseline and no one can tell which fixes caused what"; the wave-2 fusion
elevates the append-only ledger as a single-source insight). Baselines for any active experiment
stay pinned to the definition version that was pre-registered. History is recomputed from an
**append-only derived-facts store** — each session parsed once into a compact row (opus-5: at
8.2 GB growing ~91 sessions/day, a full re-parse eventually stops finishing). Tampering becomes
*undeniable* rather than *prevented*, and fixing real collector bugs stays legal. Where the panel
adjudicated collector governance (wave-2 fusion): measurement changes ride a separate metrology
path — golden datasets, dual-run old/new for 7–14 days, definitions **frozen for the duration of
any active experiment**, human sign-off on definition changes. Only o3-pro proposed literally
freezing the collector; that is the rejected variant, not the panel position.

**Every event carries exposure + stratification metadata** (the near-unanimous attribution
prerequisite): hub commit, rendered-command + rulepack hash, model, account, plan era, project,
scaffold type, **human-vs-headless flag** (opus-5: two different distributions — pooled, the loop
can "improve" any metric by shifting the mix), and a **concurrency flag** (overlapping session
windows on the same cwd — opus-5: on a 3-agent shared tree, some fraction of gate-failure signal is
peer crosstalk; minimax: file-centric view first). Three accounts rotating every ~2 days means the
model mix changes intrinsically through the week; unstamped, that drift gets attributed to whatever
merged that day.

**The collector proves itself before its numbers are believed** (near-unanimous): every parsing
predicate ships a checked-in fixture that must evaluate BOTH ways (grok: "you already paid for this
lesson at 100% and at 1440"), plus a golden corpus of hand-labelled transcripts whose expected
counts are asserted daily before any number is consumed. Instrument health is metric zero — red
instrument ⇒ no actor dispatch (qwen3.8-max's preflight), and per-metric completeness gates action
(gpt-5.6: "this metric is not actionable because 18% of the relevant events are unclassified").

**The stream gets a coroner** (author-adversarial finding #3 — hooks go silent exactly when
things get interesting: a mid-stream death fires no Stop hook and writes no closing event, so a
hook-only meter has survivorship bias built in; this session died mid-stream twice on the day the
spec was written). Two REQUIRED second sources close the hole: (a) the resume mesh's death/park
markers (`/tmp/claude-sound-locks-*/`.errparked` + the notify log) — already written by machinery
outside the session's process; (b) transcript tails (`isApiErrorMessage` rows — the mesh's own
detection keys). The collector reconstructs `death` events post-hoc from these, and completeness
accounting counts "transcript exists but no `session_end` event" as a first-class hole metric — a
rising hole count is an instrument alarm, not background noise.

**Backfill the noise floor** (opus-5, stated as a prerequisite): recompute the versioned metrics
over the full historical corpus to establish per-metric variance BEFORE any adjudication — "you
cannot detect a change you cannot distinguish from Tuesday."

**The metric set covers all four clauses of the vision, not just rules-obeyed** (C-fix: a loop
allowed to write the rules cannot be scored on rules-obeyed — both fusions, consensus):

- *Outcome tier (the numbers ceremony cannot move):* **rework rate** (commits reverted or re-touched
  within N days, minable from provenance trailers across all 46 repos today — opus-5's nomination
  for headline "correct"); **nightly fleet-health sweep** (does each project build, do its tests
  pass, does its gate go green — deterministic, no AI, opus-5: "the one number governance ceremony
  cannot move"); **escape rate** (defects found by a later stage than the one that owned them);
  **premature-stop rate** (Stop-hook fires per session — "an oracle you already built and are not
  reading").
- *Process tier:* **first-attempt gate pass rate**; gate-failure taxonomy per check;
  **search-to-edit ratio** (opus-5: rising = agents are lost — almost always a docs/scaffold/naming
  defect); quota per accepted task.
- *Compliance tier (control metrics, never objectives):* the confounded scalar splits into
  `rules_compliance` (task-completing responses opening with RULES ACTIVE, denominator = run-record
  closures) and `terminator_spam` (final blocks per run over the once-per-run contract) — the second
  is its own defect signal, currently hidden inside the first.
- **Every driving metric registers a paired counter-metric at definition time, as a schema
  constraint of the registry, not a convention** (opus-5; fable-5: "never let the loop optimize an
  unpaired metric"): rounds↓ pairs with rework↛↑; compliance↑ pairs with governance-mass↛↑;
  gate-pass↑ pairs with vacuity↛↑. A metric with no registered pair cannot drive a fix.
- **Sentinel metrics the actor cannot READ** (opus-5; kimi's weekly holdout audit; grok's held-out
  formula): at least one outcome formula lives outside every path the dossier renderer can load —
  the only proposed detector for fleet-wide Goodharting. On the sentinel registry the actor is
  denied BOTH read and write (a fixer that can read the formula can optimize against it); on the
  rest of the measurement surface it is denied write only.

### Layer 2 — Decide correctly

**The decidable rule: if the outcome is computable without calling a model, replay it; otherwise
cohort it.**

- **Replay (authoritative for deterministic surfaces; run-cost $0):** gate predicates, parsers,
  globs, renderers, denominators — run against the stored corpus, **against rendered artifacts, not
  sources** (grok: agents see the rendered composition; measuring sources is "the same failure in a
  new hat"). Identical inputs ⇒ a delta is caused by the change. Proven in-session: the corpus
  check was validated red-on-revert against the real historical defect this way. Replay includes
  **stateful sequences** where the finding implicates cross-session state (qwen3-max-thinking).
- **Split-fleet cohorts (run-cost $0; the mechanism is a real build item, not free):** behavioural
  changes — command wording, rule text — cannot replay (recorded responses can't react to changed
  prompts). ~46 projects give natural exposure, **but per-repo sync targeting does not exist today**
  (fable-5: "currently a commit propagates everywhere — a real engineering task"). The build:
  a `channel: stable|canary` field honoured by the governance sync (qwen3.8-2.4t's rings;
  qwen3-max-thinking's one-line `rollout_id` as the minimal form; scaffold registers new projects
  into a cohort — o3-pro). **The free v0 exists now: the hub is already a one-repo canary** (kimi)
  — ship hub-first, adjudicate hub-vs-fleet, then sync.
- **Adjudicate on exposure count, not the calendar** (gemini's event-volume rule, sonnet-5's
  exposure-count window, qwen3.8-2.4t's minimum-exposure metadata — independently derived):
  re-measure once N sessions have *touched the changed surface*. **And scope the metric to the
  exposure set** (sonnet-5; minimax: *spatial* attribution beats temporal — "if the metric moves
  only on sessions that don't touch rule-pack X, you deployed a placebo"), with a **placebo metric**
  no fix should ever move flagging noisy days, and per-project stratification as the default
  aggregation (opus-5: each project is its own control; break out by scaffold type — fleet means
  hide heterogeneous effects permanently).
- **Adjudication statistics, pre-registered** (kimi's Level 1; opus-5): 28-day rolling median + MAD
  per metric; the dossier's expected movement is a binding pre-registration (metric version,
  direction, threshold ≥1.5×MAD, window, guardrails); "confirmed" = crossed **and persisted**
  against the rolling baseline, never against yesterday. Verdicts are **three-valued** — confirmed /
  refuted / **inconclusive with effect size + interval** (qwen3.8-max: "if you force binary
  moved/not-moved, you will teach the loop to hallucinate certainty"). Below-minimum-n numbers
  render with their n in every downstream consumer **including dossiers** (kimi; this spec's own
  3.2 (n=12) is exploratory, not a baseline). Selection is gated on **minimum detectable effect
  given current traffic** (o3-pro) — a finding whose effect cannot be detected is parked, not
  dispatched. **Never promote on single-model-family evidence** (qwen3-max-thinking).
- **fable-5's two-tier verification, adopted** (independently opus-5's defect/policy split):
  *deterministic, replay-provable fixes* are verified by construction — failing fixture before,
  passing after — and are **never re-attempted because a noisy metric sat still** (his named
  failure: "the retry-with-diff-attached mechanism converts measurement noise into governance
  escalation"); *behavioural hypotheses* go through cohorts and windows. **Long-arc
  re-adjudication** (minimax): confirmed fixes re-measured at day 14 and day 30; an effect that
  evaporated is reverted — day-2 wins are provisional. In-house proof that blended means hide
  effects: mixed-era review rounds = 4.8; ticket-era = 3.2.
- **Generation is decoupled from promotion** (fusion resolution): candidates and falsification are
  cheap — run many. The real concurrency constraint is **one open hypothesis per metric family,
  3–4 open total** (kimi; "dispatch frequency is an output, not a setting" — wave-2 fusion); the
  off-peak window bounds blast radius and quota, not the calendar-as-experiment. One hypothesis ≠
  one file hunk — a coherent fix ships whole. Findings touching one file set may group into one
  hypothesis (o3-pro); a **weekly deep cycle** may propose architectural fixes too large for the
  daily loop (o3-pro — the answer to "60 micro-patches with no architecture pass").
- **A persistent finding registry + a tested selection policy** — fable-5: *"the selection policy is
  the actual product, and it's unspecified"*; o3-pro's backlog-explosion warning (>1,000 rotting
  findings at 60 days); gpt-5.6's registry schema. Findings are durable, deduplicated objects
  (first-seen, severity, confidence, blast radius, attempt history, expiry) ranked by expected value
  — frequency × harm × confidence ÷ (cost × blast radius) — **with an explicit allocation across
  finding categories** (gpt-5.6: reserve capacity for high-risk audits even when their metric is
  not the largest — the counter to pure-EV ranking), per-surface caps and cooldowns (a file touched
  >2× in 14 days is a thrashing flag — sonnet-5), an **influence map** (grok: don't edit a command
  that hasn't appeared in run records for 14 days unless it's an immune-system finding), and aging.
  The policy is CODE WITH TESTS. Four verdicts are first-class, non-failure outcomes:
  **"no safe valuable action today"** (qwen3.8-max's phrase; kimi's gloss — a loop that cannot say
  no will eventually eat the platform), **"not fixable by infrastructure"** (sonnet-5: some low
  compliance is task difficulty; forcing a daily commit is how rules accrete cruft), **"wrong
  control surface — project-local, not hub"** (gpt-5.6's phrase; grok's argument — the 7–73% spread
  is likelier scaffold/override misfit than a missing hub sentence), and **"insufficient evidence —
  closed"** (gpt-5.6).
- **A fix ledger with refutation memory** (kimi: "the crown jewel … currently planned as a side
  effect"; opus-5: "no memory of refutation"): every hypothesis, pre-registration, verdict, failed
  diff and revert in one append-only, off-box-backed ledger; the selection policy consults the
  refuted-hypothesis index so the loop cannot re-propose next month what failed last month with a
  cosmetically different diff. Failure classification (noise vs. bad patch vs. wrong hypothesis) is
  required before any retry; two "not moved" on the same finding *category* means the diagnosis is
  wrong, not the patch (sonnet-5); three failures trigger **strategy escalation** — change the
  surface, the hook, the routing, or close as not-actionable — never a third try at the same
  sentence (gpt-5.6). A monthly **backtest of past promotions** ("of the last 30, how many still
  look right?") re-litigates history (wave-1 fusion — nobody else proposed it).
- **A deterministic fix tier below the LLM** (minimax, adopted by the wave-2 fusion): regex
  corrections, renames, log-point additions are applied by deterministic tooling with a unit test
  as the verifier — `sed` plus pytest, zero model calls. The headless coding dispatch is reserved
  for changes whose source of truth is an instruction requiring interpretation.

### Layer 3 — Change safely

- **Per-change risk tiers, not one pipeline** (independently constructed by grok, opus-5 and both
  wave-2 qwens; grok's indictment of the alternative: "your §5 treats every change as class B and
  then merges to 46 repos — that is how you get a polite, weaker platform"):
  **T0 — never touched by the actor:** credentials, crontab, the sound system, sync mechanism, Stop
  hook, collector + metric registry, fixture/corpus labels, the actor's own halt conditions (kimi:
  "a loop that can edit the conditions under which it stops will eventually not stop").
  **T1 — actor prepares + verifies, human approves the merge:** anything enforcement-path (gate
  checks, rule packs, hooks config) or synced fleet-wide; **scaffolds** (grok: "a bad scaffold
  births the next 10 projects already wrong — class A, always"; opus-5 dissents T2 — the panel's
  5-to-1 majority rules, and sonnet-5 adds a separate weekly scaffold-vs-current-best-practice
  check since behavioural data structurally lags scaffold defects); anything **weakening** by the
  classifier below, even when the loop is right that the rule is bad (fable-5: "loosening is
  exactly the move a Goodharting fixer would make, so it always goes through the human").
  **T2 — autonomous on green:** docs, command prose clarifications that change no MUST, additive
  non-blocking checks, fixtures (authored under the separation rule below), evidence-backed
  deletions of provably-dead artifacts.
  **T1→T2 graduation, or the autonomous lane is economically pointless** (author-adversarial
  finding #5 — everything high-value on this platform is enforcement-surface; without an earn-down
  path the loop autonomously tidies the lobby while every fix that matters queues for a human who
  asked to be out of the loop, and M4 converges to a frozen platform): a surface CLASS graduates
  T1→T2 after **10 consecutive human-approved proposals in that class with zero reverts through
  their long-arc windows**; graduation is per-class, logged in the fix ledger, and **auto-revoked**
  by any auto-revert in the class (back to T1); two rejections in a class pause its proposals for
  14 days. **Never graduates, ever:** scaffolds, Stop-hook semantics, gate semantics, the sync
  mechanism, T0. The human's approval workload is designed to trend to zero on the classes the loop
  proves itself on — that is the earn-down the vision requires.
- **Staged promotion, never instant 46-repo sync**: shadow (non-enforcing `would_have_blocked`
  logging inside gate runs that happen anyway — grok's near-free variant; qwen3-max-thinking's
  dual-execution shadow at 2–3× compute is **rejected**, and the wave-1 fusion adjudicated
  identically) → hub-only canary → cohort → fleet. **The landing protocol is designed before the
  actor** (grok's build-order item #1): promotions land off-peak; project-side sync applies
  **on-idle / at next SessionStart, never mid-turn**; a project's pin holds until its open run
  records close (sonnet-5: check no project has an open run on a surface the sync touches, or defer
  that project one cycle).
- **Rollback is a first-class, exercised path** (the audit's top missed item — opus-5, kimi,
  qwen3.8-2.4t, o3-pro, sonnet-5; wave-2 fusion: reversibility and exercised reverts are *primary*
  protections on a single-user box, not supplementary): every promotion records its revert SHA and
  a scheduled re-evaluation; a paired counter-metric degrading within its window **auto-reverts
  without asking** (opus-5: "bounding the damage of every wrong decision to one week is worth more
  than getting the merge decision right"); canary tripwires (gate red-rate, stop-block rate,
  session aborts, first-turn latency) revert same-hour (kimi); a one-liner reverts the fleet in
  ~30s (o3-pro); a quarterly **revert drill** proves the path still works (kimi: "revert paths rot
  like everything else"); two consecutive auto-reverts pause the loop (opus-5).
- **Session-pinned law** (grok; independently fable-5): the rendered command + rulepack hash is
  pinned at SessionStart; gate and Stop evaluate against the pin until the run record closes — a
  mid-day promotion never rewrites the rules under a live run.
- **Net-zero governance budget with a deletion engine, not just a brake** (kimi's budget; opus-5's
  quota; fable-5's finding type): total injected governance tokens per median session — **measured
  from transcripts, not from disk** (opus-5) — is a guardrail that must trend flat-to-down; a
  change that grows it names what it retires; resolution preference is ranked *delete dead text →
  edit → consolidate → add-with-justification* (kimi); **hygiene findings are a first-class class**
  (packs that never activate, commands never invoked, checks that never fire — emitted mechanically
  from the `rule_activation`/run-record events); and governance churn's **prompt-cache tax** is
  measured (kimi: every synced-surface edit invalidates the fleet's prompt-cache prefix — a real
  quota cost this spec's costing must carry, so cosmetic edits batch). Deletion stays
  evidence-backed only, and any diff shrinking a gate check or rule pack escalates to the operator
  even when green (sonnet-5: "deletion is the cheapest way to make an inconvenient check vanish").
  **The budget binds the kaizen system itself** (author-adversarial finding #4 — this spec grew 70%
  during its own review while preaching net-zero): the loop's artifacts (its docs, scripts, registry
  schemas, and this spec) carry their own governance-mass line from M1, and loop-authored changes to
  the loop obey the same delete→edit→consolidate→add ranking. A self-improvement system exempt from
  its own law ratchets by construction.
- **Verification the actor cannot weaken** (C-fix — the candidate gate alone is disqualified by
  this spec's own diagnosis; the panel's mechanisms, adopted): the orchestrator verifies every
  candidate with (a) the **frozen-reference gate** — the gate from the last human-blessed ref, run
  from an immutable worktree; diverging verdicts between frozen and candidate gates fail the merge
  and escalate (minimax: "I'd take the frozen-reference check immediately"; sonnet-5's prior-day
  snapshot; gpt-5.6's bootstrap verifier "must not import the candidate's verifier code");
  (b) **machine invariants outside the synced surfaces** (grok's `invariants.py`; gpt-5.6's list:
  a blocking check cannot silently become advisory, error states cannot map to pass, no test
  deleted without explicit replacement, deny-paths unchanged, assertion surface may not drop);
  (c) a **deterministic weakening classifier over the diff — including rule TEXT** (opus-5's
  AST+regex pass: deleted asserts, added skip/xfail, broadened excepts, `|| true`, early returns,
  loosened comparisons, narrowed globs; qwen3.8-2.4t's `weakening_signals`; minimax for prose:
  MUST→should, tunneled carve-outs, plain-language render diff — "character overlap catches
  'should not edit' → 'should not normally edit' reliably"); (d) a **mandatory pre-merge
  adversarial critic for enforcement-surface diffs, different model family, goal withheld**
  (opus-5: "no dossier, no target metric, no framing — framing is what makes reviewers agreeable";
  kimi's strictness-hawk + Goodhart-hunter briefs, metered, "the single best use of the metered
  pool in the whole design"; grok's ordering holds — mechanical critics are load-bearing, the LLM
  critic is extra); (e) **behavioural canaries** — scripted known-delinquent sessions (ends turn
  with uncommitted work, omits RULES ACTIVE, emits the terminator three times, leaves a run record
  open, touches a denied path) that must still get caught after ANY enforcement-surface merge
  (fable-5's rated-strongest layer: "indifferent to *how* the fixer weakened something"; grok's
  four synthetic git repos for the Stop hook).
- **`vacuous_check_rate` as a permanent guardrail** (minimax's construction — in this author's
  judgement the single most valuable idea in the set; sonnet-5 and fable-5 proposed the same metric
  independently): per gate check, the fraction of recent runs where any branch *could have failed*;
  zero ⇒ the check asserts nothing. Computed by a mutation harness run **weekly** (minimax: heavy
  check), paired with the per-check known-bad fixtures above — proposed in some form by **all 12**;
  the 6 vacuous checks found manually this week are the seed set.
- **Fixture and corpus authorship is separated from fixing** (grok: fixture in commit N, check
  change in commit N+1, or critic-authored only; sonnet-5: "the fixer should never be the sole
  author of its own negative test"; opus-5: seed files are protected — any diff touching them goes
  to a human, always). Fixture rot has an owner: a monthly human fixture review (wave-1 fusion:
  "the six hollow PASSes will recur as hollow mutation fixtures" without one), and a fixture that
  ERRORS rather than fails is a quarantine event, not a pass (kimi).
- **The actor never switches the number it is judged on**: collector/definition changes ride the
  human-signed metrology path (Layer 1), frozen during active experiments. The write-allow-list is
  enforced in the promotion path; the diff is capped (~150 net lines — opus-5: larger is a design
  decision and belongs to a human); an out-of-scope touch **destroys the worktree** (grok: "do not
  ask it to revert; it will get creative"); the dispatch env is stripped, no credentials mounted,
  and the diff is secret-scanned including new log lines (o3-pro: exfiltration-via-logging).
- **The dossier is a privilege-escalation channel and is treated as one** (kimi; independently
  qwen3.8-max, opus-5, fable-5 — the wave-2 fusion's roster): transcript excerpts quoted as
  evidence contain arbitrary third-party text which must never reach the fixer in instruction
  position. Evidence is fenced as untrusted data with hard delimiters; the fixer prompt is
  assembled from templates; imperative-looking content in evidence is a flag, not a command.
  Relatedly (gpt-5.6's actual §7G point): the transcript corpus is secret-bearing — the event
  store and replay corpus get secret-scanning at ingestion and a retention policy.
- **Kill switch + external deadman** (qwen3.8-max's `KAIZEN_FREEZE`; opus-5's silent-death proof —
  the hourly CI fixer dispatched zero times today and nobody noticed): the loop checks a freeze
  file before every action, and a watchdog OUTSIDE the loop's process tree alerts when no completed
  cycle has been recorded in 48h. Silence must be an alarm, not an absence of one. A periodic
  **red-team pass** tries to get a bad change through in a sandbox; a success is a severe finding
  and a new fixture (both wave-2 qwens; wave-2 fusion adopt-anyway).
- **Escalation is budgeted and defaults safe** (C-fix — the operator asked to be out of the loop;
  an unbounded approval queue rebuilds the dashboard he refused, as both fusions warn): ≤2
  escalations/week; exceeding the budget makes **the loop slow itself** (kimi), never the operator;
  an unanswered ask **defaults to park, never proceed** (wave-1 fusion; qwen3.8-2.4t's
  deny-after-48h). What must interrupt: invariant breach, fixture inversion, auto-revert, deny/T0
  touch, quota-reserve breach, deadman.
- **Sync-skew / propagation fidelity as a metric** (grok; minimax): of the last 30 days' governance
  changes, how many arrived at all ~46 repos within the expected window — a `git` query per repo
  per day. A "fleet improvement" measured while only some projects received the change is the
  attribution killer nobody watches for.
- Tier-D precedent inherited (`60-watchdog.md`): isolated worktree (never the shared tree —
  `ci_fix_dispatcher`'s dirty-tree skip produced **0 dispatches** on 2026-08-16 with 10 failures
  pending; worktrees are why this actor will actually run), tests-pass hard gate, transactional
  merge (lease → rebase → re-run the full battery → else abort), every verdict emits a counter +
  structured line (`self-healing.md`), full audit trail in the event stream.

## The builder is a guarded actor too (author-adversarial finding #2)

Every guard above points at the future fixer; the system's biggest unverified actor during M0–M3 is
the interactive session that BUILDS it — which, on the day this spec was written, produced three
instrument bugs, two bad dispatch scripts and four false hook claims in one session. Binding rules
for the build itself:

- **Every kaizen component ships its own anti-vacuity canary in the same commit** (the discipline
  proven live on `check_command_corpus.py --selftest`): known-bad input must fail, known-good must
  pass, and the canary is proven discriminating red-on-revert against a real historical defect.
- **The fixture harness is itself fixtured** (meta-fixture): a deliberately-broken fixture (one that
  ERRORS, one that silently passes) must be detected by the harness's quarantine path — otherwise
  the harness is the next vacuous check.
- **Every milestone exits through a non-author review** (`/fabrik-review` with non-author finders —
  the standing corpus law), and every M-gate proof is a runnable command with its output embedded,
  never a claim.
- **From M2 onward, the builder's own diffs to kaizen surfaces run through the weakening classifier
  and invariants it just built** — the tools apply to their maker the day they exist.

## Quota posture (a consciously-held deviation, recorded)

Ten of twelve consultants said the loop should run **metered-first** (gemini: "you are proposing
using your precious subscription quota to fix the platform — do not do this"; kimi, opus-5 as a
hard rule). This spec adopts that for everything except the coding dispatch itself: collection,
ranking, dossiers, critics, audits and adjudication are deterministic Python or metered-pool calls;
**the headless coding session stays on the subscription lane** (`claude --model claude-fable-5
--fallback-model claude-opus-5`, full IDs — aliases resolve stale) per the operator's standing
stack ruling (Claude Code OAuth for operational coding; metered API only for what OR can serve).
The panel's mitigations are adopted with it: a **quota-reserve preflight** (below threshold: the
loop measures and queues but does not dispatch — opus-5), a **hard cap of 10% of the weekly quota
share** (qwen3.8-2.4t's band; a cap breach parks the loop, it never borrows), the fixer reported
as a line item in **quota per accepted improvement**, off-peak scheduling, and the **critic always
on a different, metered family** (kimi/gemini: same-family review shares the blind spots — the
verification argument, not just the cost one). **The cost figure is measured, not estimated**
(author-adversarial finding #6 — the earlier "≈1–2% of daily burn" was pre-verification optimism;
the calibration anchor from the spec's own review day: ONE Opus verification agent consumed ~234k
subagent tokens and died twice, each retry re-burning): M3's ten propose-only dossiers measure the
loop's real burn end-to-end, and the M4 budget is set from that measurement. Scope note recorded
honestly: the operator's standing subscription-lane ruling was made for operational sysadmin loops;
its extension to this new daily consumer is pinned by the operator's explicit amendment instruction
(2026-08-17), and the M4 gate re-confirms it against the measured cost.

## Sequencing — autonomy is earned (M-gates)

| M | Delivers | Autonomy | Gate to next |
|---|---|---|---|
| **M0** | **The shrink audit, FIRST** (author-adversarial finding #1 — building a full observatory to measure a city you suspect should be a village is backwards). No event stream needed: artifact usage is measurable from data that already exists — command invocations grep-able from the 5,317 transcripts, rule-pack applicability replayed by glob-matching git history, checks-that-never-failed from gate JSON history. Deliverable: a usage-evidence deletion report over all 203 artifacts + the operator's shrink ruling. Every later milestone is sized to the SURVIVING surface | none (read-only audit) | operator has ruled on the report; the artifact census the meter must cover is final |
| **M1** | Event emitters in hooks + run-record machinery (full exposure metadata; `rule_activation`; platform-owned lifecycle audit); split compliance metrics + outcome tier (rework, fleet-health sweep, premature-stop, first-pass gate); versioned definitions + append-only derived-facts store + recompute; collector predicate fixtures + golden corpus; noise-floor backfill; paired-counter-metric registry; daily collector cron replaces weekly | none (measurement only) | 7 days of events; recompute reproduces history without overwriting it; denominators verified against hand-counted samples; per-metric variance established; activation logging verified to exist |
| **M2** | Replay harness (rendered artifacts, stateful option); weekly vacuity/mutation harness + per-check known-bad fixtures + assertion-surface floor; behavioural canary suite (Stop hook + hooks + packs); finding registry + tested selection policy + fix ledger; deletion-candidate report (the shrink-first question, answered with evidence); hub-as-canary v0 | none (analysis only) | replay red-on-revert proven on ≥3 historical defects; every blocking check owns a fixture that FAILS; canaries catch all scripted delinquents; selection policy passes its fixture tests |
| **M3** | Propose-only shadow actor: deterministic tier + headless dispatch in a fresh worktree filing dossiers + candidate diffs it **cannot promote**; frozen-reference verification + weakening classifier + invariants; mandatory different-family critic on enforcement diffs; quota-reserve preflight; kill switch + deadman live | proposes only | ≥10 dossiers; operator spot-audit finds no fabricated evidence; false-positive rate visible; zero T0 touches; worktree run-record keying verified; **measured end-to-end quota burn published** (sets the M4 cap) |
| **M4** | Promotion rights under Layer 3 in full: risk-tiered (T2 auto / T1 human-approved), one open hypothesis per metric family (3–4 total), off-peak promotion windows, cohort mechanism (channel field) built, exposure-count + long-arc adjudication, rollback drills scheduled | **operator gate — explicit approval required to enter** | ongoing: any guardrail regression auto-parks the loop; monthly promotion backtest |

## Rejected alternatives

1. **Actor v1** (fix daily → judge by next-day fleet mean → verify with `final_gate.py`) — rejected
   by the full panel (both fusion syntheses; even the friendliest reviews — o3-pro's "directionally
   correct", kimi-k3's "shape fundamentally sound" — condition it on the same instruments-first
   prerequisites): next-day fleet-mean adjudication is causally empty (in-house proof: 4.8 vs
   3.2); "the number moved" both false-negatives good rare-path fixes and false-positives noise; the
   gate cannot verify changes to the gate (6 checks passed while asserting nothing, found
   2026-08-16); instant sync is a ~46-repo blast radius.
2. **Full statistical platform** (o3-pro: 2³ strata × 20% holdout × paired t-tests;
   qwen3-max-thinking wave-1: dual-execution shadow at 2–3× compute) — rejected: not credible at n=46
   non-exchangeable projects (compliance spread 7–73%); dual execution violates the hard
   $0-new-spend ceiling. Cohorts serve as bias control with effect sizes, not significance theatre.
3. **Freeze/chmod the collector** (o3-pro alone) — rejected in favour of the operator's
   recompute-over-immutable-history design plus the panel's adjudicated metrology path (dual-run,
   frozen-during-experiment, human sign-off): the collector has known bugs and must remain fixable;
   filesystem permissions don't bind a promoted diff; the control belongs in the promotion path.
4. **Metered-only actor** (10/12) — deviation recorded and mitigated in § Quota posture; the
   operator's stack ruling governs the coding lane.

## Recorded, deliberately deferred (so nothing is silently dropped)

Panel mechanisms acknowledged but NOT in scope for M1–M4, each with its disposition:
**switchback / step-wedge / within-project crossover** (qwen3-max-thinking, o3-pro, opus-5) — only
if cohort difference-in-differences proves insufficient; **artifact-level ELO** (gemini) — the
exposure-set scoping covers the need at lower complexity; **offline rule-prose eval over frozen
task setups** (opus-5's ~20-task text eval) — revisit at M4 if cohort evidence on wording changes
proves too slow; **per-project governance forks** (kimi argues against; agreed — heterogeneity is a
finding, not a configuration); **separate OS user / container isolation** (both wave-2 qwens) —
on a single-user box every control is advisory (wave-2 fusion); reversibility and blast-radius
limits are the primary protections here; **meta-stability output cap** (qwen3-max-thinking) — the
quota governor in § Quota posture is the adopted variant; **account-rotation ToS/ban risk of
automated dispatch** (wave-1 fusion blind spot) — flagged to the operator as a standing risk, not
designable-away here; **structural anti-vacuity lint** (assert-presence schema) — subsumed by
fixtures + assertion-surface floor; **fix-pattern blacklisting via 5% stricter-oracle audits**
(qwen3-max-thinking) — the refutation-memory + category rule covers the near term.

## External dependencies (all grounded THIS session, 2026-08-16 — live probes, not memory)

| Dependency | Grounded fact | Source + date |
|---|---|---|
| `claude` CLI model pinning | `--model claude-fable-5` and explicit `--model claude-opus-5` verified live (headless probe returned exact IDs); `--fallback-model` accepts a comma-separated list. ⚠️ Aliases (`opus`) resolve to the *latest stable* line (4.8), NOT Opus 5 — **full IDs only** | live CLI probes, this box, 2026-08-16 |
| Headless context inheritance | a `claude -p` session on this box inherits CLAUDE.md, MEMORY.md index, fabrik-mail digest, and a **working session-recall MCP** (probe returned `{"claude_md":true,"memory_index":true,"session_recall":true,"mail":true,"recap":true}`) | live headless probe, 2026-08-16 |
| OpenRouter model IDs (consult panel) | frontier set live-verified: `qwen/qwen3.8-max`, `moonshotai/kimi-k3`, `minimax/minimax-m3`, `openai/gpt-5.6-luna-pro`, `x-ai/grok-4.6`, `google/gemini-3.1-pro-preview`. ⚠️ naive prefix match fails (`gemini-3-pro` hits image-only variants); stale point-releases flatter (qwen3-max-thinking vs 3.8-max, measured) | live `/api/v1/models` probes, 2026-08-16; request for a live-resolved FRONTIER preset filed to fabrik-lib (mail `01M05V82ZQ540R8RK52F5H3QNG`) |
| ai-consult module | `panel(question, models=[...])` returns per-model answers + fusion synthesis; SSE liveness, restart-on-stuck, no blind timeout — wave 2 ran 1,122s without a cutoff (this session's run log, not the archive); 12 consults = $2.40 | module source + live runs, 2026-08-16 |
| Session transcripts | `~/.claude/projects/<dir>/*.jsonl`, rows carry `cwd`/`gitBranch`/`timestamp`/typed `type`; 5,317 files / 8.2 GB / 98 dirs; ~91 touched per active day | live filesystem census, 2026-08-16 |
| Resume mesh | mid-stream deaths (5 named classes) detected + death-recorded + Telegrammed in 2s; revival requires an armed waker — self-watch arming now in ORIENT (commit 20a28cbc) | live incident + `docs/workstation/hooks-index.md`, 2026-08-16 |
| 12-consultant design review | the approach-space grounding for this spec. All 12 answers + both fusion syntheses were read IN FULL during `/fabrik-spec-review` convergence — by this author and independently by a native-Opus auditor whose report found six attribution defects in the pass-1 draft (all corrected in this revision) and 53 unadopted mechanisms (adopted, rejected, or ledgered above) | `docs/archive/2026-08-16-kaizen-consultation-raw.md`, 2026-08-16 |

## fabrik-lib verdict table

| Capability | Verdict | Module / why |
|---|---|---|
| Frontier design-critique panel (M3 critic; future spec reviews) | **VENDOR** | `ai-consult` — proven live today; vendor into `libs/` at M3 (currently imported from `/opt/fabrik-lib` path, acceptable for consults run hub-side) |
| Pool fan-out + flywheel | VENDOR (already vendored) | `libs/subagents` |
| Alerting (daily verdict → Telegram leg) | VENDOR (already vendored) | `libs/alerting` |
| Metered-spend caps (OR consult budget) | VENDOR (already vendored) | `libs/cost_budget.py` — caps the *metered* lane only; per operator ruling 2026-06 the subscription-billed Claude lane is never per-call capped |
| Event emitter (hooks + run records) | **BUILD** | must be fail-open, zero-dependency, append-only local file — `app-audit-log` is DB-coupled at the wrong seam (a hook must never block on postgres). Not yet a fabrik-lib candidate: coupled to this box's hook surface; revisit once stable |
| Replay harness / metric registry / recompute / finding registry | **BUILD** | nothing in the module table covers replay-over-transcripts, versioned-metric recompute, or the finding registry; project-local by design (they ARE the hub's meter) |

## Shape / infra implications

- **No scaffold type, no service, no deploy** — box-local scripts + crons in the hub repo (same
  class as `kaizen_metrics.py` / `liveness_audit.py`). No `specs/services/*.yaml`, no `shape:` flags.
- New crons (M1: daily collector; M3: daily actor dispatch, off-peak) → `docs/RESILIENCE.md` §7 is
  the canonical jobs inventory (Doc Sync Matrix) + `docs/workstation/wsl-startup-inventory.md` §C.
- New subsystem docs at each milestone (`docs/workstation/kaizen.md` evolves; event stream + replay
  get reference docs); INDEX rows per the allowlist.
- Logs: cron-redirected stdout (`55-observability.md` — the tool writes stdout; the environment
  routes). Event files are **data**, not logs.
- Tests: `uv run pytest`, watched-fail-first per `45-testing-strategy.md`; the replay harness's own
  correctness is proven red-on-revert against the three historical instrument bugs it must catch.

## Constraints (binding)

- **$0 new spend.** Ceiling is the existing 8× Claude Max ($800/mo) + $50–100 OR. Shadow =
  non-enforcing logging only; replay and cohort *runs* are free (the cohort *mechanism* is a build
  item, priced in engineering time at M4, not dollars); consult panels are occasional and metered
  (~$2.40/12 opinions), inside the existing OR budget. The prompt-cache tax of governance churn is
  measured and counted against the loop, not ignored.
- **Quota is the binding resource**: § Quota posture governs — metered/deterministic everywhere
  except the coding dispatch; reserve preflight; the loop reports quota per accepted improvement.
- **Shared tree** (3 concurrent hub sessions): actor works in fresh worktrees; explicit pathspecs;
  never touches sibling WIP; transactional merge (lease → rebase → full battery re-run → else abort).
- **Write-allow-list enforced in the promotion path** (T0 list in Layer 3); hard denies:
  credentials, `~/.claude-fleet`, crontab (M1–M3; M4 cron changes are operator-applied),
  `~/.claude/bin/claude-sound.sh` (untouchable, standing order), any repo other than `/opt/fabrik`
  (cross-repo = mail, never edits).
- No login automation; no direct HTTP token refresh.
- LLM gateway for metered calls = OpenRouter only; the coding lane is Claude Code subscription
  OAuth (operator's standing stack ruling — see § Quota posture).
- Governance edits remain subject to every existing gate (42 blocking checks incl.
  `check_command_corpus.py`) *plus* this spec's Layer-3 additions.

## Open / blocking unknowns

| # | Unknown | Status | Resolution step |
|---|---|---|---|
| 1 | Do hooks fire reliably enough in ALL session types (headless `-p`, compact-resume, subagents) to make the event stream complete? | open, non-blocking for M1 | M1 measures its own coverage: events-per-session vs transcript census daily; gaps become M1 findings before any M2+ decision trusts the stream |
| 2 | Exposure-count threshold N per surface class | open by design | derived from M1–M2 measured traffic (per-surface activation rates), not guessed now |
| 3 | Off-peak window for the actor (operator's working hours vary) | open, operator input at M3 | one-line question at M3 kickoff; default 05:00–06:00 (before the 06:xx cron train) |
| 4 | Stop-hook mid-stream blind spot: a turn that dies mid-stream closes no run record and the Stop hook never fires (observed live 2026-08-16; mesh caught it, revival required the now-mandated armed self-watch) | mitigated, watch | M1's `death`/`revival` events make the residual rate measurable; revisit if >0 unrevived deaths/week |
| 5 | Run records + Stop hook in a WORKTREE may key to the wrong tree (kimi's implementation check) — a fixer that cannot close its own record spins until quota dies | open, blocks M3 dispatch | verify the exact keying path before the first real dispatch; fail closed |
| 6 | ~~Should the first act be SHRINKING the surface?~~ **RESOLVED** (operator, 2026-08-17: "fix them properly") — promoted to **M0**, before the meter is built; the fusion w2 question ("203 and 57 → 60 and 20?") is answered with usage evidence from the EXISTING corpus, not deferred until after the observatory is sized for the unshrunk city | resolved | M0 delivers the report; the operator rules; M1+ size to the survivors |
| 7 | The loop's own stopping/EV condition (fusion w2 blind spot: nobody defines when the loop is good enough to slow down, or proves it pays for its quota) | open by design | pre-register the loop's own success test at M3: quota spent vs. accepted improvements, reviewed monthly; a loop that cannot pay for itself gets demoted to weekly |
| 8 | Rule-pack activation logging may not exist at all today (minimax: "the very first thing I would verify") — Layer 3's deletion evidence and the activation metrics depend on it | open, M1 first task | verify; if absent, adding it is M1's first mechanical deliverable |
| 9 | The safe degraded configuration if the build stalls half-built (wave-2 fusion: "the most likely outcome and strictly worse than either endpoint if autonomous merge is on") | designed-for | each M-gate leaves a self-sufficient system; autonomy defaults OFF at every stage until its gate passes, so a stall anywhere leaves measurement-only or propose-only — never orphaned merge rights |

*(Deliberately NOT written: "zero unknowns". The list above is the honest state.)*

## Out of scope

- VPS/fleet state, deploy docs, container health (fleet's beat).
- Editing peer repos (mail only; the fabrik-lib FRONTIER-preset request is already filed).
- Replacing `kaizen_metrics.py`'s honesty rules — inherited verbatim (a metric that can't be
  measured prints `—` + reason; never 0-for-no-data; never a number it didn't compute).
- The epic/ticket orchestrator route — this is feature-scale: each milestone is one operator-carried
  plan (`/fabrik-plan-after-chat` per milestone, **M0 — the shrink audit — first**).
