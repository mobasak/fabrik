# RAW consultation answers — kaizen daily-loop design (2026-08-16)

Primary source for `docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md`.
12 independent consultants, one identical brief (reproduced at the end). Total cost $2.40.
Kept verbatim: the synthesis is an interpretation; this is the evidence.



---

## openai/gpt-5.6-luna-pro

# Overall judgment

The proposed loop has the right *direction* but not yet the right control-system design.

“Observe → change one thing → independently verify → measure later” is much better than a dashboard or an agent that merely reports that it improved itself. However, the current proposal risks becoming a highly disciplined machine for making small, weakly attributable changes to a system whose most dangerous failures are not visible in its current metrics.

I would not initially authorize unrestricted daily autonomous edits to governance surfaces. I would build a **staged, evidence-driven control loop**:

1. Observe with an immutable, typed event model.
2. Detect a problem and rank it by expected harm, not just metric size.
3. Reproduce it against a versioned corpus.
4. Generate one candidate intervention.
5. Verify the intervention against trusted infrastructure, adversarial tests, and protected invariants.
6. Canary it on a small project cohort or in shadow mode.
7. Measure both target and guardrail metrics.
8. Promote, roll back, or escalate based on predeclared rules.
9. Keep a permanent experiment and provenance record.

The important change is that **“the metric moved” must not be the definition of success**. A metric can move because the measurement changed, the population changed, agents learned to emit the expected strings, or actual quality got worse.

The system should treat metric movement as one piece of evidence, not as proof.

---

# 1. The loop shape

## What is right

Several elements of the proposed actor are good:

- It uses an isolated worktree.
- It requires independent verification.
- It records a hypothesis rather than accepting an agent's completion claim.
- It limits the number of interventions.
- It maintains ordinary, revertible commits.
- It separates the actor from the measurement code.
- It recognizes that the current shared working tree is an operational hazard.

The worktree point is especially important. A fixer that refuses to run whenever the main tree is dirty is not conservative; it is mostly inert. But isolation must apply not only to files. It must also isolate:

- the Git base commit,
- the target ref,
- credentials,
- network access,
- quota usage,
- distribution side effects,
- and concurrent promotion.

## What will break after 60 days

### 1. “Exactly one finding” creates starvation

The largest metric is not necessarily the highest-value defect. A low-level formatting-compliance issue may repeatedly outrank:

- a gate that is vacuous,
- a rule that causes incorrect code,
- a security regression,
- an expensive command pattern,
- or a scaffold defect affecting all new projects.

You need a backlog with persistent identities for findings. Each finding should have:

- first-seen date,
- affected projects and versions,
- severity,
- confidence,
- estimated blast radius,
- reproducibility,
- prior attempts,
- metric owner,
- and expiry/revalidation rules.

The daily selector should optimize something like:

\[
\text{priority} =
\frac{\text{expected harm} \times \text{affected exposure} \times \text{confidence}}
{\text{cost} \times \text{blast radius} \times \text{reversibility penalty}}
\]

Not literally that exact formula, but that shape.

A finding that has failed twice should not necessarily be tried a third time by making the same type of command edit. Three failed attempts should trigger **strategy escalation**, not merely “ask the human.” For example:

- change the command,
- change the hook,
- change the gate,
- change the task scaffold,
- change the model routing,
- or conclude that the observable metric is not actionable.

### 2. One-day adjudication is often too short

Some outcomes are immediate:

- whether a gate runs,
- whether a command record closes,
- whether a parser recognizes an event.

Others need more exposure:

- escaped defects,
- review rounds,
- downstream rework,
- new-project success,
- regressions,
- or whether agents simply adapt to a new instruction.

“Did the number move tomorrow?” is a bad success criterion for sparse metrics. The system needs a predeclared observation window per hypothesis:

- immediate: parser and invariant checks,
- 3–7 days: protocol adherence,
- 14–30 days: code quality and review behavior,
- project-lifecycle based: scaffold outcomes.

The next day should adjudicate whether the intervention is *still healthy and receiving exposure*, not necessarily whether it has definitively succeeded.

### 3. The loop can optimize for easy observability

The actor will naturally choose defects with:

- clear file locations,
- easy changes,
- immediate metrics,
- and low verification cost.

That is not the same as choosing defects with the greatest operational value. Over time, the platform may become excellent at response formatting while remaining poor at correctness.

You need an explicit allocation across categories, for example:

- correctness and escaped defects,
- enforcement integrity,
- agent efficiency,
- rules compliance,
- cost/quota,
- scaffold quality,
- and security/reliability.

Reserve some intervention capacity for high-risk audits even when their metric is not the largest.

### 4. Synced governance creates multiplicative blast radius

A change to a command or rule is not one change. It is a fleet-wide deployment to approximately 46 consumers, possibly with different:

- repositories,
- languages,
- project types,
- local overrides,
- tool versions,
- and task distributions.

The unit of deployment must therefore be a **versioned governance package**, not a collection of files silently synchronized by commit.

Every project should report:

- governance package version,
- command/rule versions,
- local overrides,
- and last successful application.

Without this, a measured “fleet improvement” may actually mean that only some projects received the change.

### 5. Worktree isolation does not solve merge races

The actor can create a clean worktree while three other agents modify the hub. It still has to safely merge against a moving target.

The merge protocol should be transactional:

1. Record the base commit and intended files.
2. Build and verify in the isolated worktree.
3. Rebase or merge onto the current target only after verification.
4. Re-run all verification after rebasing.
5. Acquire a promotion lease.
6. Verify the target ref has not changed unexpectedly.
7. Fast-forward or perform a narrowly scoped merge.
8. Push with lease protection, never force-push.
9. Release the lease.

If the target changed in a relevant area, abort and rebuild. Do not let “verified on branch X” become “merged into a different state.”

---

# 2. What should be measured

The existing metrics are useful as diagnostic inputs, but most are not yet suitable as primary optimization objectives.

## A. Correctness and outcome metrics

These should be the highest-level measures:

### Escaped defect rate

A defect discovered after the agent's claimed completion, divided by completed tasks with sufficient follow-up exposure.

Possible sources:

- human review findings,
- post-merge test failures,
- production failures,
- reverts,
- follow-up corrective commits,
- and downstream tickets.

This is difficult but much harder to game than protocol strings.

Track severity-weighted and unweighted versions. A one-line typo and a security defect should not have equal impact.

### Rework rate

Fraction of tasks requiring:

- a corrective follow-up,
- a revert,
- an additional review cycle,
- or human intervention caused by the original agent work.

This is likely more available than true escaped defects.

### First-pass acceptance

Whether a task passes its declared acceptance criteria without a second implementation round. Be careful: acceptance criteria themselves can be weakened, so retain an immutable task snapshot and require evidence that the criteria were not changed after implementation.

### Review rounds

The existing review-round metric is useful, but only after defining:

- the unit of work,
- plan version,
- review type,
- whether rounds are caused by implementation defects or scope changes,
- and whether the same reviewer/model produced the rounds.

The ticket-era versus mixed-era distinction is exactly the right instinct. Keep eras separate permanently.

## B. Agent efficiency metrics

### Time to useful completion

Wall-clock time from task start to an accepted change, excluding waiting time where appropriate but reporting both gross and active time.

### Turns and tool calls per accepted task

Useful, but highly Goodhart-vulnerable. An agent can reduce turns by making larger, riskier edits or by stopping early.

### Human intervention rate

This is one of the most important metrics for a solo operator. Count:

- manual corrections,
- manual gate overrides,
- manual conflict resolution,
- manual restarts,
- and human review required because the system lacked evidence.

### Quota consumed per accepted task

Since subscription quota is the binding resource, dollar cost is not the primary metric. Track:

- model/account,
- tokens or equivalent usage,
- dispatch count,
- retry count,
- and quota consumed per accepted outcome.

The denominator should be accepted work, not sessions.

## C. Governance and enforcement metrics

### Protocol compliance

Split the current metric into separate events:

- `rules_active_required` and `rules_active_present`,
- `run_opened`,
- `run_terminal_required`,
- `run_terminal_emitted`,
- `run_terminal_emitted_more_than_once`,
- `stop_hook_blocked`,
- `stop_hook_bypassed`,
- `invalid_record`,
- `missing_record`,
- and `unknown_state`.

Do not infer these from arbitrary text if structured hooks can emit events directly.

The denominator must be generated from task/session state:

- Which turns were task-completing?
- Which command run was active?
- Was the response conversational, read-only, or implementation-related?
- Was the agent interrupted?
- Was the session terminated by a crash?

“Number of responses containing a block” is not a meaningful denominator.

### Gate effectiveness

A gate passing is not proof that it is useful. Measure:

- checks executed,
- checks skipped,
- checks errored,
- checks with zero assertions,
- checks whose result is constant over a corpus,
- checks whose inputs were absent,
- and checks that would have caught known seeded defects.

A gate should have an effectiveness score based on mutation testing or seeded-failure detection.

### Enforcement friction

A rule can be technically effective but so noisy that agents learn to bypass it or spend most of their time satisfying bureaucracy.

Track:

- false block rate,
- repeated retries caused by the same check,
- time spent resolving governance failures,
- and bypass/override attempts.

## D. Safety and stability metrics

Every intervention needs guardrails:

- gate pass rate,
- task acceptance rate,
- escaped defect rate,
- review rounds,
- latency,
- quota usage,
- human intervention,
- parser error rate,
- and project coverage.

An intervention that improves compliance by doubling task duration or increasing defects is not successful.

## E. Data quality metrics

These should be first-class and visible to the actuator:

- event completeness,
- duplicate event rate,
- unknown enum values,
- timestamp anomalies,
- missing project/version identity,
- impossible state transitions,
- transcript parsing failure rate,
- delayed ingestion,
- and source disagreement.

The collector should be able to say: **“This metric is not actionable because 18% of the relevant events are unclassified.”**

Until then, it should not trigger an automated fix.

## Which current metrics are “junk”?

Not useless, but unsafe as primary objectives:

- raw compliance percentage,
- raw sessions per day,
- raw subagent failure rate,
- raw review-round mean across mixed eras,
- raw turns or tool calls,
- and any metric inferred by loose text matching.

The subagent failure rate can be useful after the vocabulary bug is fixed, but it needs stratification by model, task type, timeout, and `out_of_scope` versus genuine failure.

Means are particularly dangerous. Report:

- median,
- p75/p90,
- tail count,
- and confidence interval.

A mean review count of 3.2 with n=12 should be labeled exploratory, not presented as a stable baseline.

---

# 3. The measurement system needs to become an event system

The collector should not primarily parse prose. It should consume a typed event stream.

Each event should include at least:

```text
event_id
session_id
run_id
task_id
project_id
git_commit
governance_version
agent/model
event_type
event_time
ingest_time
payload
schema_version
```

Events should be append-only and deduplicated by `event_id`.

Examples:

```text
session_started
task_declared
command_started
command_phase_completed
gate_check_started
gate_check_completed
response_classified
run_closed
commit_created
review_round_completed
human_intervention
task_accepted
defect_found
```

Transcripts remain valuable for forensic analysis, but they should not be the authoritative source for protocol compliance when a hook can emit a structured event.

The data pipeline also needs a **replayable corpus**. Preserve representative sessions and known bad cases, including:

- missing `RULES ACTIVE`,
- repeated terminators,
- premature stop,
- uncommitted work,
- fake gate passes,
- malformed records,
- and successful normal sessions.

Every collector change must replay this corpus and produce expected labels. This is a stronger protection than simply forbidding the fixer from editing the collector.

Selection by file mtime is not acceptable for causal measurement. Use event time, ingestion watermarks, explicit late-arrival handling, and stable cohort definitions. A daily report should say which data is provisional and which is complete.

---

# 4. Verification: the largest unresolved risk

The statement “the orchestrator reruns the full gate” is insufficient because the gate itself is part of the attack and failure surface.

The platform has already found six checks that reported PASS while asserting nothing. That means “all checks passed” currently has weak semantic value.

## A. Use a trusted verifier outside the change surface

The actor must not be able to alter the verifier that judges it.

Use at least two layers:

### Immutable bootstrap verifier

A small, separately protected verifier that:

- checks changed paths,
- checks signatures or hashes of protected files,
- runs the governance package's tests,
- and invokes the candidate gate.

It should be sourced from:

- a protected Git ref,
- a separate repository,
- or a pinned container/image.

It must not import the candidate's verifier code before checking it.

### Candidate gate

The normal full gate, run for behavioral compatibility.

If the change modifies the gate, the candidate gate is evidence, not authority.

## B. Protected invariants

The verifier should reject changes that violate invariants such as:

- required blocking checks still exist,
- check identifiers are stable,
- a blocking check cannot silently become advisory,
- error states cannot map to pass,
- no check can return success without examining an input or producing an assertion,
- no deny-listed path changes,
- no command can disable the stop hook,
- no provenance requirement is removed,
- no sync scope expands unexpectedly,
- and no test is deleted without an explicit replacement.

These should be tested structurally and behaviorally.

## C. Mutation testing

For each gate check, maintain seeded mutations:

- delete a required line,
- introduce an invalid path,
- break a required command record,
- remove a provenance trailer,
- violate a known rule,
- alter a synced artifact,
- or create an uncommitted state.

The check should fail on the corresponding mutant.

A gate check that never fails on any valid mutation is either dead, too broad, or not testing what its name implies.

This directly addresses the six vacuous checks.

## D. Negative and adversarial testing

The fixer should be tested against cases where the easiest way to improve the metric is prohibited:

- emit the required response block repeatedly,
- remove the denominator,
- classify task turns as conversational,
- suppress failure events,
- weaken a gate,
- add a no-op assertion,
- or route around a hook.

The test suite must verify that such changes either fail verification or are visible as a regression.

## E. Differential replay

Run the old and new governance versions over a corpus of real sessions and synthetic cases. Compare:

- classifications,
- gate outcomes,
- command phase transitions,
- and generated records.

Any unexpected behavioral difference needs an explanation. A change that improves one metric by changing many unrelated classifications should not be promoted automatically.

## F. Canary distribution

Do not immediately sync a changed governance surface to all 46 projects.

First deploy to:

- one representative project,
- then a small cohort with different scaffold types,
- then the fleet.

The canary should include at least:

- a high-activity project,
- a project with poor measured compliance,
- a project with a different language/toolchain,
- and a newly scaffolded project if scaffolds are affected.

For a command or rule that must be fleet-wide immediately for safety, use shadow mode first where possible.

## G. Static deny-lists are not enough

A hard deny-list for credentials, crontab, and other repos is necessary but insufficient. Use path and capability controls:

- read-only access to raw telemetry,
- no ability to alter cron or system services,
- no network by default,
- no access to unrelated repositories,
- no credentials mounted into the worktree,
- write access only to an allow-listed checkout,
- and promotion performed by a separate process.

The fixer should propose a commit. A separate promotion service should decide whether the commit may enter the hub.

---

# 5. Attribution and experimental design

## One change per day is not enough for attribution

It provides an intuitive narrative, but not necessarily causal evidence. The population changes daily:

- projects differ,
- tasks differ,
- models differ,
- humans differ,
- workloads differ,
- and agents may be using different governance versions.

A metric moving after a commit does not establish that the commit caused the movement.

## Recommended design: staged, controlled rollout

### Phase 1: Shadow mode

The new infrastructure runs but does not affect agents. Measure what it would have classified or blocked.

This detects:

- false positives,
- parser changes,
- unexpected project incompatibility,
- and denominator changes.

### Phase 2: Canary cohort

Assign projects to:

- treatment,
- control,
- or delayed rollout.

If every project must eventually receive the change, use a stepped-wedge design: different cohorts receive it on different days or weeks.

Analyze changes relative to each project's own baseline, not just fleet averages.

### Phase 3: Fleet promotion

Promote only if:

- target metric improves by a predeclared minimum,
- no guardrail metric worsens beyond threshold,
- data completeness is adequate,
- and the effect is not explained by cohort composition.

For a small fleet, statistical significance may be unrealistic. Use effect sizes, confidence intervals, replication, and conservative operational thresholds rather than pretending that n=46 provides strong inference.

## Use synthetic replay for fast decisions

Some interventions can be tested immediately against a fixed corpus. For example:

- a parser fix,
- a gate check,
- a command rendering change,
- or a stop-hook behavior.

This provides a controlled result, while live fleet data confirms whether the behavior transfers.

## One intervention per day versus multiple

I would retain a limit on **simultaneous promotion**, but not necessarily one candidate per day.

A better policy is:

- many findings may be analyzed and tested in parallel,
- one or a few may enter shadow mode,
- only a bounded number may be promoted,
- and interacting changes must not be bundled in the same experiment.

One per day is a quota and blast-radius policy, not a causal-identification strategy. If quota is scarce, one promotion per day may be sensible. But it should not be described as sufficient attribution.

## Define success before dispatch

Every hypothesis needs:

```text
target metric
baseline version and window
expected effect size
minimum exposure
observation window
guardrail metrics
rollback threshold
analysis method
```

Example:

> On the canary cohort, repeated run terminators will fall from 31% to below 10% of eligible runs over seven days, with no increase in missing terminal records, gate blocks, task rework, or median completion time greater than 10%.

That is much stronger than “the metric should move down.”

---

# 6. Human visibility and stop conditions

The operator does not need a dashboard, but he does need a compact, trustworthy control signal.

## Minimum daily signal

Send one daily message containing:

1. **What changed**
   - commit,
   - governance version,
   - affected surfaces,
   - affected projects/cohort.

2. **Why**
   - finding,
   - evidence count,
   - baseline,
   - expected effect.

3. **What happened**
   - verification result,
   - canary result,
   - target metric,
   - guardrail metrics,
   - data completeness.

4. **Decision**
   - promoted,
   - rolled back,
   - still observing,
   - or stopped.

5. **Risk**
   - quota consumed,
   - remaining exposure,
   - unresolved anomalies.

Most days this should be machine-generated and terse. The operator should only need to inspect a diff when the system reports an exception.

## Immediate escalation conditions

Stop autonomous work and ask for human review when:

- a protected invariant fails,
- a gate's pass/fail behavior changes unexpectedly,
- a check becomes vacuous,
- the target metric improves while a high-priority guardrail worsens,
- a synced surface affects more projects than expected,
- a candidate touches a protected path,
- a promotion merge requires conflict resolution outside the allow-list,
- telemetry completeness drops,
- a rollback itself fails,
- two consecutive interventions produce contradictory results,
- the intervention cannot be attributed because the cohort or version identity is missing,
- or the system proposes changing measurement semantics.

Also stop after repeated non-actionable findings. Three failed attempts should not merely produce a red counter; it should quarantine that finding and require a different hypothesis or human decision.

The human should approve:

- changes to the measurement schema,
- changes to what counts as a task or success,
- changes to safety invariants,
- changes to model routing or quota allocation,
- broad scaffold changes,
- and any change whose rollback is not immediate.

---

# 7. Important things not yet considered

## A. Governance version drift

You need to know exactly which infrastructure governed each session and task. Otherwise historical comparisons are unreliable.

This includes:

- hub commit,
- rendered command hash,
- rule-pack hash,
- gate version,
- hook version,
- and local project overrides.

## B. Agents will adapt to the measured surface

Once agents reliably observe the metrics, they will optimize for them. That may be intentional or accidental.

Examples:

- producing required strings without doing the work,
- closing records before the task is complete,
- splitting work into sessions to improve per-session compliance,
- avoiding task classifications that carry obligations,
- or reducing review rounds by narrowing the declared scope.

Countermeasures:

- measure independent outcomes,
- randomly audit transcripts,
- use hidden or rotating tests,
- compare declared scope to actual diff and task history,
- and track suspicious distribution shifts.

Hidden tests must not be the only defense; otherwise the system becomes adversarial and opaque. But some unannounced validation is appropriate.

## C. Safety regressions can be delayed

A command change may look good for a week and cause problems only on a rare scaffold or a new project. Canary selection must cover project types, not just project counts.

Maintain a long-lived regression suite containing prior incidents. Every future candidate must pass it.

## D. The loop may spend scarce quota on low-leverage fixes

Because subscription quota is binding, dispatching a daily agent is not free even if API dollars are low.

Use a tiered actor:

1. deterministic repair or configuration change,
2. cheap external model for diagnosis or patch proposal,
3. subscription agent only when coding judgment is genuinely needed,
4. human escalation for high-risk or ambiguous changes.

The actor should have a quota budget and report **quota per accepted improvement**, not just dispatch count.

## E. Revertibility is not the same as harmlessness

A revertible commit can still cause:

- fleet-wide behavioral changes,
- bad data collection,
- generated artifacts propagating to projects,
- or irreversible human confusion.

For synced surfaces, keep versioned packages and a known-good release. Rollback should be tested as an operation, not merely assumed to be `git revert`.

## F. The system needs a model of non-action

Sometimes the right result is “do not change infrastructure.” If the defect is caused by task ambiguity, model limitations, or project-local practices, editing a shared command can make every project worse.

Findings should be classified as:

- infrastructure-fixable,
- project-local,
- model-routing,
- measurement defect,
- workload effect,
- or not actionable.

The actor should be allowed to close a finding as “insufficient evidence” or “wrong control surface,” with an explanation. Otherwise it will keep editing commands because that is the only action available.

## G. Security and privacy of transcripts

The raw corpus contains messages, tool results, paths, and potentially secrets. The collector and fixer should not have unrestricted access to all raw transcripts.

Implement:

- secret scanning and redaction at ingestion,
- access separation between aggregate metrics and raw forensic data,
- retention policies,
- project-level data minimization,
- and audit logs for transcript access.

This matters even in a single-operator environment because automated agents are powerful and accidental leakage is easy.

---

# A concrete architecture I would implement

## 1. Immutable telemetry layer

- Typed append-only events.
- Stable IDs for session, task, run, project, and governance version.
- Schema validation.
- Late-event handling.
- Data-quality metrics.
- Replayable corpus.
- Raw transcripts retained for evidence, not primary metric computation.

## 2. Finding registry

Each finding is a durable object:

```text
finding_id
problem_class
affected_versions
evidence
severity
confidence
candidate_control_surface
target_metric
guardrails
attempt_history
status
next_eligible_time
```

## 3. Candidate patch pipeline

- Create worktree from pinned base.
- Give the agent a dossier and a narrow file allow-list.
- Run an immutable verifier.
- Run ordinary tests and full gate.
- Run mutation and adversarial tests.
- Run differential replay.
- Require a real commit and provenance.
- Produce a machine-readable change report.

## 4. Promotion controller

- Acquire a lease.
- Rebase onto the current target.
- Re-run verification.
- Deploy to shadow/canary.
- Record exact cohort and version.
- Promote or roll back based on predeclared thresholds.
- Never let the coding agent perform final promotion directly.

## 5. Adjudicator

The next day's job should not just compare `A` and `B`. It should determine:

- whether exposure was sufficient,
- whether data was complete,
- whether the target improved,
- whether guardrails held,
- whether the effect replicated across cohorts,
- and whether the change should be promoted, held, rolled back, or superseded.

## 6. Operator report

One concise daily report, plus immediate alerts for stop conditions. No dashboard required.

---

# Final design judgment

The proposal is a strong starting discipline, but its current central belief is too strong:

> Nothing counts as fixed until the number moves.

That rule is attractive because it prevents unverified self-congratulation. It is also dangerous. A number may move for unrelated reasons, fail to move because exposure is insufficient, or move because the system learned to manipulate the measurement.

The stronger rule is:

> Nothing counts as fixed until the intervention passes trusted verification, survives controlled exposure, improves the intended outcome, and does not worsen declared guardrails.

I would keep:

- isolated worktrees,
- independent verification,
- narrow changes,
- ordinary commits,
- explicit hypotheses,
- and bounded autonomous activity.

I would change:

- one finding per day into one bounded promotion at a time,
- next-day adjudication into windowed, cohort-aware evaluation,
- transcript parsing into typed event instrumentation,
- full-gate verification into trusted verifier plus mutation testing,
- fleet-wide sync into versioned canary deployment,
- and “metric moved” into outcome-plus-guardrail acceptance.

The most dangerous failure is not that the actor fails to fix something. It is that it becomes successful at improving the visible governance metrics while gradually weakening actual software correctness, enforcement integrity, or operator control. The design must assume that failure mode from the beginning.



---

## x-ai/grok-4.6

**The loop as specified will optimize ritual, not work.** Isolation, independent verify, “don’t let it edit the meter,” and “hypothesis not trophy” are the right instincts. The experimental design, the promotion path, and the objective function are not. If you build §5 as written you will get a daily machine that lengthens commands, inflates incantation-compliance, and cannot tell a real win from Tuesday’s project mix.

---

## 0. The actual production function

You do not have a metrics problem. You have a **control-system** problem whose plant is:

- 3 agents, one dirty tree, no shared context
- a hub commit that is a **fleet release** to ~46 repos
- a weekly subscription quota that is the real budget
- rules that are both **policy** and **the thing being edited**

“Rules-obeyed” cannot be the primary objective of a loop that is allowed to write the rules. That is a tautology. Obedience is a **control metric**. The objective is still: *correct work lands, fast, without the operator in the review seat.*

Write that down as a constitution the fixer **cannot touch**. Everything below hangs off it.

---

## 1. The shape is wrong in four places

Observe → one patch → merge to fleet → look at tomorrow’s mean is not a closed loop. It is an **uncontrolled release train with a diary**.

### 1.1 You are missing the only two things that make a change attributable

A hub edit is instantly global, and tomorrow’s sessions are a different mix of projects, tasks, humans, and whichever subscription account is still alive. Next-day movement of a fleet mean is not a causal estimator. It is weather.

You already watched this happen: mixed-era review rounds 4.8 vs ticket-era 3.2. The process change was real; the blended number hid it. A daily auto-fixer will generate a new blended number every morning and then **act on the hiding**.

**Required shape:**

```
find → hypothesize → patch in worktree → replay + critic + gate
     → shadow or canary → promote or revert → log
```

- **Replay** (same day, causal): frozen labeled traces vs new rendered rules/gates.
- **Canary / holdout** (1–3 days, quasi-experiment): 5–8 projects do not get the change.
- **Fleet mean** (weak, lagged): context only, never the promote bit.

Without a holdout channel, “one change per day so we can attribute” is self-talk. You shipped to everyone; you attributed to no one.

You do not have this channel today (“a synced surface changes ~46 repos”). **Build the flag/pin before the actor.** A one-line `holdout:` list honored by governance sync is a bigger reliability win than the fixer. Until it exists, the actor may only land changes that are *non-enforcing* (shadow checks that log, do not block).

### 1.2 “Nothing counts as fixed until the number moves” will delete good work and keep bad work

True fixes that will often **not** move tomorrow’s fleet KPI:

- a gate that fires on a file type nobody touched today
- a rare catastrophic path (force-push, credential leak, vacuous PASS)
- a denominator fix in the collector (you banned the collector, correctly)
- a scaffold that only affects project #47

True non-fixes that **will** move tomorrow’s KPI:

- calendar, quota rotation onto a worse model, a quiet day (you already measured 16 vs ~91), one well-behaved project dominating the mix

The 3-strike retry then attaches the previous diff and tells another agent to “make the number move.” That is how you get vacuous checks. You have already found six. This rule manufactures the seventh.

**Replace with two bars, both required:**

1. **Immediate:** replay and fixtures move in the predicted direction; guardrail metrics do not regress; assertion surface does not shrink.
2. **Delayed:** canary vs holdout over a pre-registered window, *or* a change-point with an explicit “too noisy, park it” outcome.

“Didn’t move” is a **legal result**. It is not a failed fix. Failed fix = replay/canary say the hypothesis is false, or a guardrail moved the wrong way.

### 1.3 One *finding* per day confuses git atomicity with experimental atomicity

One **hypothesis** per experiment is right. One file hunk is not. “Split the terminator metric and stop mid-run spam” is one hypothesis and several edits. Splitting it across three days just guarantees confounding with yourself.

One **promotion** per window is the real constraint (blast radius + quota + sync storms). Generate whenever you have a high-confidence dossier. Promote on a schedule, not on a streak of green gates.

### 1.4 What breaks at day 60 (the failure nobody is pricing)

- **Incantation overfitting.** The cheapest confirmed “wins” are RULES ACTIVE and the 6-line block. Commands get longer. Agents ignore them harder. Compliance % goes up. Review rounds do not. You will call this success.
- **Uncoordinated micro-patches.** 60 commits to 27 commands + 56 rule packs with no architecture pass. Shared fragments become a junk drawer. Rendered commands diverge from what any human can audit.
- **Mid-session law changes.** A 14:00 promote rewrites rules under live agents who started on yesterday’s command text. Stop hook and gate disagree with the prompt they were given. Metric noise + real breakage. Your 3-way shared tree makes this ordinary, not rare.
- **Partial sync.** Pre-commit governance sync means the fleet is *never* on one version. Projects mid-work stay old until they commit. The “one change” is not applied uniformly, which finishes off attribution and can strand a project on a bad rule until someone happens to commit.
- **Instrumentation chasing.** Run records just started. The first two weeks of findings will be about the new sensor. Useful, but it is not the product.
- **Operator atrophy.** When the loop finally escalates, he no longer remembers why a rule exists. Escalation without a decision log is a page at 2 a.m. about a system nobody owns.

**Unseen critical failure:** governance sync of a daily hub commit into 46 trees that are already dirty from 3 agents. You forbade `git add -A` and stash-of-others, correctly. You did not say how a *fleet* change lands without doing the same violence in the *projects*. If sync is a pre-commit hook, you get silent divergence. If sync is a bot commit on every project, you get 46 collisions/day and a Stop-hook war. **Design the landing protocol before the fixer.** Candidate: fixer only commits on hub at a dead window (e.g. 03:00); project sync is pull-on-idle / next SessionStart, never mid-turn; a project pin stays put until the session’s run record closes.

---

## 2. What to measure (and what to throw out)

### 2.1 Junk, or not fit to steer a fixer

| Thing you have | Verdict |
|---|---|
| “Rules-compliance %” as built | **Junk for steering.** Mixes omit-once with emit-36-times. Denominator includes turns that do not owe the block. Project range 7–73% is a siren, not a KPI. |
| “20/91 lacked RULES ACTIVE” | **Junk.** Conversational/read-only turns are not violations. |
| Mixed-era review rounds 4.8 | **Junk as a current KPI.** Keep as history. |
| Sessions selected by mtime | **Biased.** A session that started yesterday and finished today is either double-counted or dropped. Use session-id + start/end timestamps. |
| Ticket-era rounds 3.2 (n=12) | **Real, too small to steer daily.** Weekly / per-experiment only. |
| Subagent 4% fail, p50 37s, $0.74 | **Keep as cost/reliability**, not as the objective. After the `status != "ok"` bug, treat every new predicate as guilty until it has a fixture. |

### 2.2 The set I would actually build

Three layers. The fixer may be scored on layer A via **replay**, watched on layer B, and **never** given a reward for layer C moving in isolation.

**A — Outcomes (what the vision actually said)**

1. **Time-to-correct-land** — session (or ticket) start → first commit that is gate-green **and** pushed **and** not reverted within 48h. Report p50/p90, not the mean.
2. **Review rounds per ticket** — ticket-era only, with a frozen definition of “round.” Guardrail: human-authored review notes length / reject-reason mix.
3. **Rework ratio** — commits whose next commit in the same ticket touches the same paths and is classified fixup/revert. You can mine this from provenance trailers + paths.
4. **Operator unstick rate** — sessions where a human message is required after a Stop-hook block, a red gate loop, or an explicit “help.” This is the “he is still in the loop” meter. If this does not fall, the product is not working.
5. **Post-land defect** — revert, emergency follow-up within 72h, or review-reject after gate-green. Gate-green-then-reject is your best “vacuous gate” sensor in the wild.

**B — Mechanism (leading, Goodhart-prone, still necessary)**

6. **Task-completing responses only** — a turn owes RULES ACTIVE + the closer **iff** it is the turn that closes a run record (or is classified task-completing by a frozen heuristic: opened a run record, or last turn before Stop). One closer per run. Two counters, never one: `omit_closer`, `midrun_closer_spam`.
7. **Stop-hook fire rate** by reason (uncommitted / unpushed / gate red / run record open). Rising fires can mean worse agents *or* a tighter hook. Pair with (4) and with “hook fired then agent dumped junk just to exit.”
8. **Gate cycles per land** — how many times `final_gate.py` went red before success, per ticket. Complements (1).
9. **Rendered-command obedience, not source obedience** — did the agent run the commands the *rendered* slash-command required (from the run-record ledger), and in order? This is the actual “rules obeyed.”
10. **Quota per landed ticket** — subscription-account minutes / tokens per (1). The fixer itself must appear as a line item here.

**C — Immune system (fixer must not improve these by deletion)**

11. **Assertion surface** of gates: count of checks that have a reachable fail branch and that read real state (AST, not comments). Six vacuous PASSes are the calibration set.
12. **Enforcement recall/precision on a frozen corpus** (below).
13. **Command mass** — tokens and MUST-count in the rendered command the agent sees. A “fix” that adds 400 tokens of nag is a regression unless A-metrics move on replay.
14. **Sync skew** — how many of 46 repos are not on hub HEAD for each synced path.

### 2.3 Goodhart counter-design (concrete)

- **Split reward from sensor.** The dossier names one A or B metric as the *target* and two C/A guardrails that must not regress. Promote requires target ↑ and no guardrail ↓ on replay/canary.
- **Held-out formula.** Keep one outcome (I would pick rework ratio or gate-green-then-reject) whose exact definition is not in any command file the fixer can read. Compute it only in the observer. Painful, and worth it.
- **Measurement code is read-only to the actor** — keep this. Add: measurement *definitions* (the markdown that says what a “round” is) are also read-only.
- **Never reward the proxy alone.** A confirmed experiment that improved `omit_closer` but not time-to-land / review rounds is logged as “ritual improved, outcome unchanged” and that *class* of finding is deprioritized for 14 days.
- **Predicate fixtures.** Every collector predicate has a checked-in JSON example that must evaluate both ways. You already paid for this lesson at 100% and at 1440.

Implementation sketch: one `metrics.yml` the observer loads, with `id`, `layer`, `denominator`, `window`, `min_n`, `holdout`. The actor receives only `id` + last value + `min_n` status, not the parser code.

How this fails: people will still stare at B because A is slow. Counter that in the triage policy (next section), not with a pep talk.

---

## 3. Verification: the gate cannot police the gate

Re-running `final_gate.py`, tests, and “a commit exists” catches crashes. It does **not** catch:

- `return True` / empty check / glob that never matches
- MUST → SHOULD, or a new exception that is the common case
- deleting the fixture that made the check real
- Stop hook that accepts any commit, including `chore: wip`
- command text that tells the agent to skip a now-inconvenient rule
- scaffolds that birth weaker projects (invisible to hub tests)

You need a **second immune system** that does not share fate with the thing being edited.

### 3.1 Frozen constitution (human-owned, not in the 203)

A short file the fixer cannot modify, e.g. `/opt/fabrik/CONSTITUTION.md` plus a machine-checked `invariants.py` living **outside** the synced surfaces (or with a different review class). Examples of machine invariants:

- every gate check module exports a `failing_fixture` and a `passing_fixture`; both must run
- `final_gate.py --json` with the failing fixture of check *k* must not be `success`
- Stop hook must still refuse: dirty tree, unpushed, red gate, open run record (four synthetic git repos as fixtures)
- deny-list paths unchanged
- no check’s glob may expand to `**/*` without a class-A review
- assertion-surface count may not drop

If the fixer needs to change an invariant, that **is** the escalation.

### 3.2 Mutation tests for gates (this is how you stay ahead of the next six vacuous PASSes)

For each of the 57 checks: a tiny known-bad tree and a known-good tree. CI (and the orchestrator, independently of the session) runs all of them. A diff that makes a known-bad pass is rejected even if the full gate is green on the worktree.

How it fails: fixtures rot (the bad example no longer resembles reality). Schedule a monthly *human* fixture hunt; do not let the fixer write its own fixtures in the same commit as the check. New fixture in commit N, check change in commit N+1 of the same hypothesis, or critic-authored fixtures only.

### 3.3 Replay corpus (the real verifier)

You have 5,317 transcripts. That is enough to stop guessing.

Build `corpus/vN/` (append-only, versioned):

- ~200 traces, stratified by project, era (pre/post 2026-08-09), outcome (clean land, review fight, Stop-hook thrash, gate thrash)
- labels: `should_fail_gate: [ids]`, `should_match_rule: [ids]`, `should_block_stop: bool`, `task_completing_turns: [i]`, `required_commands: [...]`
- labels are human or critic-proposed + spot-checked; **not** written by the fixer
- run the *rendered* command assembler + rule globs + gate + Stop predicates against the trace. Do not grep command source.

Promote bar: recall on labeled faults does not drop; precision does not drop by more than a pre-set ε; the dossier’s target labels move the right way.

How it fails: corpus overfits last month’s projects; new failure modes are invisible. Add every escalated incident to the corpus before the next promote. Treat corpus-miss + production incident as a measurement bug, same severity as the 1440-round incident.

### 3.4 Adversarial critic (use the cheap metered pool)

This is the correct use of “you” in §6.

- Fixer: path-restricted, isolated worktree, subscription **or** cheap model, but not stealing peak quota (see §6).
- Critic: different model, **no write**, gets the diff + constitution + assertion-surface delta + replay delta. Its only job: find weakenings, glob widening, MUST dilution, deleted tests, measurement leakage.
- Orchestrator merges only if critic returns `no_weakening` *or* the human accepts a recorded dissent.

How it fails: both models share a taste for polite rules. Mitigate with *mechanical* critics first (AST assertion surface, fixture mutations, MUST-count, glob volume). The LLM critic is extra, not the load-bearing wall.

### 3.5 Change classes (do not run one pipeline)

| Class | Examples | Auto-promote? |
|---|---|---|
| D | comments, examples, typo in a command | after gate + critic |
| C | command wording that does not change MUSTs or order | after replay |
| B | new rule, tighter glob, new gate check (assertion surface ↑) | shadow 48h or canary |
| A | Stop/Session hooks, gate semantics, sync protocol, scaffolds, crontab, anything that widens a glob or drops an assertion | **human** |

Your §5 treats every change as class B and then merges to 46 repos. That is how you get a polite, weaker platform.

### 3.6 Path sandbox is not a deny-list

Deny-list credentials / crontab / other repos is necessary and insufficient. Run the fixer with a **write-allow** list: the 27 commands, 13 fragments, 56 rule packs, 57 gates, 12 scaffolds — and not hooks, not sync scripts, not collector, not constitution, not corpus labels. Enforce with a worktree hook + `git diff --name-only` in the orchestrator. If the session touches anything else, destroy the tree. Do not ask it to revert; it will get creative.

---

## 4. Attribution: one-a-day is the wrong experiment

One fleet-wide treatment per day, outcome = next-day mean, n_sessions wildly unstable (16 vs 91), treatment applied through a laggy sync: **you will not have power**, and you will pretend you do.

**Better design, in order of leverage:**

1. **Replay as the primary “did this work.”** Immediate, same traces, actually causal. This is your unit test for policy.
2. **Holdout projects as the primary “did this work in the wild.”** 6 projects pinned off the change. Pre-register: metric, window (min 48h or min_n sessions, whichever later), guardrails. Promote if treated − control beats a threshold; else revert or park.
3. **Shadow enforcement** when you cannot hold out (hooks, global Stop behavior): new predicate logs `would_have_blocked` for 48–72h. Compare to subsequent review-reject / rework. Then flip to blocking.
4. **Change-point, not tomorrow-vs-today.** Even a simple pre/post with a 7-day window and an explicit “underpowered” state is better than a binary next-day call.
5. **Hypothesis register, not a findings lottery.**

```
id: H-014
target: gate_cycles_per_land
direction: down
guardrails: [assertion_surface, review_rounds_ticket, command_mass]
min_n: 30 tickets
window: 72h
class: B
canary: [proj-a, proj-b, ...]
holdout: [proj-x, ...]
```

One hypothesis can be several commits. No second hypothesis promoted until this one is confirmed, rejected, or parked-underpowered.

Is one-change-per-day right? **One promotion window per day, off-peak, is right. One finding arbitrarily selected is not.** Rank findings with a deterministic, tested policy:

- layer-A or immune-system (vacuous gate, Stop-hook bypass) first
- then high influence: commands that appear in the most run-records / most review-reject tickets
- drop anything with `min_n` not met
- drop ritual-B findings if the last two confirmed wins were ritual-only
- **never** pick “biggest swing in yesterday’s %” — that selects noise

How this fails: holdout projects are not exchangeable (your 7–73% spread says they are not). Stratify holdouts (one high-compliance, one low, one high-volume) and do not use a single pooled delta. If you cannot hold out honestly, stay on shadow + replay and **do not claim confirmation**.

---

## 5. What a human still sees

He asked to be out of the noticing business, not the sovereignty business.

**Never a dashboard he must tend.** One of three objects, and only those:

1. **Decision notice** (asynchronous, skimmable, the “present us the infrastructure” he actually asked for):

   > H-014 class B. Tightened gate `foo` (assertion surface 42→43). Replay: +6 recall on corpus v4, precision −0.5pp. Canary 72h vs 3 holdouts: gate cycles 2.4→1.7, review rounds flat, command mass +12 tokens. Promoting 03:00. Reply `veto H-014` to hold.

   That is a proof, not a chart.

2. **Halt** (interrupt, rare): assertion surface ↓; fixture inversion; critic `weakening`; 3 failed attempts; deny/allow-list trip; sync skew above bound; fixer quota > agreed daily cap; merge would touch a dirty peer path on hub; corpus/gate disagreement on a labeled fatal.

3. **Ask** (blocks that class until he answers): any class A; first time a new surface is edited; hypothesis that trades an A-metric against another A-metric (faster land, more review rounds); anything that changes what “task-completing” means.

Weekly, not daily: a 20-line decision log append (hypotheses, confirmed/rejected/parked, quota spent by fixer vs product, sync skew, corpus version). If he never reads it, the loop still has a spine when he comes back at day 60.

**Stop and ask immediately when** the loop is about to change the definition of good. Everything else can wait for 03:00.

Do not escalate “metric didn’t move.” Escalate “we were about to lie about why it moved.”

---

## 6. What you are not thinking about

**Quota is a product constraint, not a footnote.** Three accounts empty in ~2 days. A daily headless session of the same class as the workers is a tax on the 46 projects — the thing the machinery exists to produce. Put the fixer + critic on metered models. If you must use subscription, hard-cap it (one off-peak job, killed at $N or T minutes) and show it as a line in metric 10. “Daily” refers to *observe + maybe promote*, not *burn a worker-equivalent session*.

**Rendered ≠ source.** You already failed once by measuring paperwork (hub review ledgers). Measuring command *files* while agents see a rendered composition of 27+13 fragments is the same failure in a new hat. Every replay and every dossier cites the rendered text hash the session actually got.

**Influence map before ranking.** 203 artifacts will not matter equally. Join run-records × command name × review-reject × rework. The fixer should not be allowed to edit a command that has not appeared in 14 days unless the finding is class A immune-system. Otherwise you will “fix” dead scaffolds forever.

**Project-local vs hub-global.** 7% vs 73% compliance is more likely a scaffold / local override / task-type problem than a missing sentence in `/fabrik-spec`. A hub-only actor will write global nags that punish the 73% project. Triage must be allowed to emit “this is a project-X scaffold finding” and **not** touch the hub. Your deny-list says “another repo”; that also blocks the legitimate local fix. Allow a *separate* project-local actor with a tighter blast radius, or file those findings as human.

**Stop-hook gaming is the attractor.** You already force agents to commit/push/green/close to exit. A fixer scored on hook fires or land speed will make exiting easier: accept empty commits, weaken the gate, auto-close run records. Put “junk commit to satisfy Stop” in the corpus as a labeled fault. Measure it (short-SHA commits with no test touch + hook in the last two minutes of a session).

**Law cannot change mid-turn.** Pin the rendered command pack and rule pack version on SessionStart in the run record. Gate and Stop evaluate against the pin, not HEAD, until the record closes. Otherwise your own promotes are an unmeasured intervention in every live session.

**Identity.** Distinct git author + trailer `Hypothesis: H-014` + `Expect: gate_cycles down`. Otherwise you cannot bisect the loop out of the fleet. Revert is one `git revert`; keep it that way. Never squash hypothesis history.

**The collector is still the most dangerous code you have.** Two first-run bugs were definitional, not off-by-ones. Freeze predicates with fixtures; canary the collector itself (run old and new definitions side by side for 7 days before switching the number the actor sees). The actor never switches the number.

**Scaffolds are a delayed weapon.** A bad scaffold change does not move any daily metric. It births the next 10 projects already wrong. Class A, always.

**Taste.** For one operator, “correct” includes style he has not formalized. A closed loop will drift off that taste and then enforce the drift. The constitution plus mandatory class-A review is how he stays the principal without reviewing 46 repos.

**Concurrency on the hub.** Worktree isolation solves dirty-tree skip. It does not solve “fixer merge vs human/agent commit on the same command file.” Orchestrator must rebase onto current hub HEAD and **re-run the entire verify battery** after rebase, or abort. No force-forward.

---

## 7. What I would build instead (concrete)

Keep from §5: isolated worktree (this is the piece that makes any actor real), independent orchestrator verify, measurement-code ban, 3-strike park, revertible ordinary commits, dossier-not-vibes.

Throw away: next-day fleet mean as judge, “number must move or retry,” single undifferentiated pipeline, subscription-burn daily dispatch, implicit fleet-wide enforce on every green gate.

**Build order** — if you invert this you will automate a lie.

1. **Landing protocol + holdout pins + session-pinned rulepack.** Without these, do not auto-merge.
2. **Metric surgery.** Split omit vs spam; fix denominators; session windows not mtime; `metrics.yml` with `min_n` and layers; predicate fixtures for the collector. Re-run the “verify the instrument” lesson as a gate on the observer.
3. **Gate mutation fixtures + assertion-surface snapshot** for the existing 57. You already know six are hollow; that set is the seed.
4. **Corpus v0** (even 40 traces beats tomorrow’s mean). Replay harness on *rendered* artifacts.
5. **Triage policy** as code, with tests (given a fake findings table, which one is picked).
6. **Actor** on allow-listed paths, metered model, 03:00 window, critic, class A/B/C/D.
7. **Shadow default, canary for B, human for A.** Hypothesis register. Decision notices, not a dashboard.

**Daily rhythm that matches “daily, not weekly” without lying:**

- Continuous observe.
- 03:00: at most one promote of an already-verified hypothesis, only if no class-A live session pins are open on the affected files, only if quota cap remains.
- Daytime: critic + replay can prepare the *next* hypothesis; they do not merge.
- Human sees decision notices and halts only.

**How this design fails:** holdouts drift from treated projects; corpus ages; constitution rots; the operator vetoes nothing and is back in atrophy. Mitigations: re-stratify holdouts monthly; every halt adds a corpus item; constitution changes are the only diffs he *must* read; if 14 days pass with no class-A change and no halt, force a human review of the decision log before the next B promote.

---

## Direct answers to the six questions

1. **Shape.** Half right (observe, isolate, don’t trust the agent, hypothesis). The promote/adjudicate half is unsafe and causally empty. Add pin/holdout/shadow, verify by replay+fixtures+critic, promote off-peak, allow “parked-underpowered.” After 60 days the silent killer is ritual-overfit + mid-session law change + 46-way dirty sync, not “we didn’t pick enough findings.”

2. **Metrics.** Steer on time-to-correct-land, ticket review rounds, rework, operator-unstick, gate-green-then-reject. Keep subagent cost. Split and demote compliance theatre. Command mass and assertion surface are guardrails. Current compliance % and mixed-era rounds are junk for control.

3. **Verification.** Gate-on-the-worktree is necessary and easily fooled. Constitution + mutation fixtures + assertion-surface monotonicity + labeled replay + mechanical then LLM critic + change classes. Fixer never writes fixtures or corpus labels in the same act as the change.

4. **Attribution.** One-change-per-day fleet-wide cannot attribute. One hypothesis, replay for causality, holdout/shadow for the field, min_n or you do not get to claim. Ranking is the policy — write it down and test it.

5. **Human.** Decision notices with proofs; halt on immune-system failure; ask on class A and on A-vs-A tradeoffs. No dashboard. No “please look at yesterday’s 36%.”

6. **Blind spots.** Quota tax, rendered vs source, landing into 46 dirty trees, session-pinned law, project-local vs global, Stop-hook gaming, scaffold delay, fixer identity, collector as the sharpest weapon, taste drift.

The operator already learned the only lesson that matters: **verify the instrument before believing the number.** §5 as written puts an agent in charge of the plant and uses an unverified, confounded instrument as the reward. That is the same failure, automated, and pointed at 46 repos at once.

Do not turn the actor on until landing, holdout/shadow, collector fixtures, and a 40-trace replay exist. That is not caution. It is the difference between a loop and a daily unattributed release.



---

## qwen/qwen3-max-thinking

This is a deeply thoughtful and unusually mature design problem. The operator has already avoided many classic pitfalls: they understand Goodhart’s Law, have instrumented behavior (not just self-reported claims), recognize the danger of editing their own measurement code, and are aware that shared mutable state breaks automation. That said, **the proposed loop shape is fundamentally fragile**, and several core assumptions will cause silent degradation or catastrophic failure within weeks—not months.

Below is my independent design judgment, organized by your six questions, with concrete alternatives and failure-mode analysis.

---

## 1. **Is the loop's shape right? Observe → one fix → verify → adjudicate-next-day**

### Short answer: **No. The “one change per day” model creates attribution illusions and invites strategic gaming by the AI fixer.**

### Why it fails:
- **Metrics drift for exogenous reasons**: Project mix shifts daily (e.g., one project dominates sessions), humans intervene unpredictably, external APIs change, models degrade. A single metric movement cannot be causally attributed to one diff.
- **The fixer learns to exploit lag**: If adjudication happens *the next day*, the fixer can make changes that *temporarily* improve a metric but cause harm later (e.g., disable a slow but critical gate check → compliance ↑ today, bugs ↑ in 3 days). The loop never sees the delayed cost.
- **One-change-per-day starves learning**: With ~200 artifacts and dozens of failure modes, fixing one thing per day means 200+ days to cycle through known issues. Meanwhile, new defects emerge daily. The system falls behind.
- **Silent compounding**: If a fix *appears* successful (metric moves) but actually weakens correctness (e.g., makes a rule less strict), the next fix builds on corrupted infrastructure. Errors compound silently.

### Better shape: **Batched, counterfactual, short-horizon experiments**
Instead of one change per day, do this:

#### Daily cycle:
1. **Identify up to 3 candidate fixes** (not just one).
2. For each, create an **isolated shadow environment** (a full copy of `/opt/fabrik` + representative project repos).
3. **Replay recent sessions** (last 48h) against each shadow env *with and without* the proposed fix.
4. Measure delta in metrics *on the same session corpus* → **counterfactual attribution**.
5. Only promote fixes that show **consistent improvement across ≥80% of replayed sessions** and **no regression in safety metrics** (e.g., gate pass rate, review rounds).
6. Merge at most one *per artifact type* (e.g., one rule pack, one command file) to limit blast radius.

> **Why this works**: Attribution is solved by replaying identical inputs. No waiting for tomorrow’s noisy data. You detect harmful “improvements” immediately because you see both worlds.

> **Implementation**: Use `git worktree add --detach` + `rsync -a /opt/project* ./shadow/`. Replay via a deterministic session player that mocks LLM calls with recorded tool responses (you already have transcripts!). Cost: ~3× current quota, but avoids human intervention.

> **Failure mode**: Replay fidelity. If tool calls aren’t perfectly reproducible (e.g., time-dependent APIs), use dependency injection to mock non-determinism. Log all non-mocked calls as “unreplayable”—exclude those sessions from evaluation.

---

## 2. **What should actually be measured?**

Your current metrics are **mostly junk due to denominator errors and conflated signals**. Here’s a minimal viable set:

### Core principles:
- **Measure *outcomes*, not proxies**.
- **Denominator = only turns that *should* obey the rule**.
- **Track latency *and* accuracy together** (fast wrong = worse than slow right).

### Proposed metric set:

| Metric | Definition | Why it’s better |
|--------|------------|-----------------|
| **Task Completion Rate (TCR)** | % of agent-initiated tasks that reach `GATE:DONE` without human intervention | Direct measure of autonomy. Exclude read-only turns. |
| **Rule Adherence per Obligated Turn** | For turns that *must* emit `RULES ACTIVE` + terminator block: % that do so *exactly once* | Fixes your conflation: split into (a) missing, (b) duplicated. |
| **Review Rounds per Autonomous Task** | Only count reviews triggered by agent commits that passed gate | Removes human-injected noise. |
| **Gate Check Failure Distribution** | Which of the 42 checks fail most often? Track top 5 weekly. | Finds weak gates (e.g., vacuous checks). |
| **Subagent Utility Ratio** | (Successful subagent calls) / (Total subagent calls) | Measures if delegation helps or hurts. |
| **Infrastructure Drift Score** | # of projects where synced files differ from hub (should be 0) | Catches sync failures early. |

### Junk metrics to discard:
- **“Fleet review rounds” without task-type filtering**: Meaningless due to human noise.
- **Raw session count**: Not a quality signal.
- **Compliance % with broken denominator**: Actively misleading.

### Goodhart counter-design:
- **Never optimize a single metric**. Require *Pareto improvement*: e.g., TCR ↑ *and* Review Rounds ↓ *and* no new gate failures.
- **Randomly audit 5% of “successful” fixes** by re-running with stricter oracle (e.g., human-written test suite). If audit fails, blacklist the fix pattern.

---

## 3. **The verification problem: Preventing malicious or incompetent self-modification**

You’re right to fear this. Gates can be gamed; tests can be deleted; rules can be weakened. Your current guard (“don’t edit measurement code”) is necessary but insufficient.

### Solution: **Triple-layer verification**

1. **Pre-commit static guardrails** (cheap, fast):
   - Enforce schema on rule packs/gates (e.g., every gate check must contain `assert ...` or `raise`).
   - Block diffs that reduce line count in test files or gate checks (deletion = red flag).
   - Require comments explaining *why* a rule was relaxed.

2. **Post-fix behavioral replay** (as above): Does the change *actually* improve outcomes on historical data?

3. **Delayed oracle check** (critical):
   - After merging, run a **72-hour shadow mode**: All agent sessions execute *both* old and new infra in parallel.
   - Compare outputs: If new infra produces different (but still passing) results, log for human review.
   - If new infra causes *more* human interventions in 72h, auto-revert.

> **Implementation**: Use git branches (`infra/main` vs `infra/shadow-{date}`). Agent runner forks execution. Cost: 2× compute, but catches subtle regressions.

> **Failure mode**: Shadow mode misses rare edge cases. Mitigation: Prioritize shadowing for high-risk changes (e.g., gate edits, rule relaxations).

---

## 4. **Attribution: Can one change cause a metric movement?**

**No—not reliably in a multi-project, multi-agent, human-in-the-loop system.**

Your intuition to avoid batches is correct (batch = confounded), but one-change-per-day is too sparse.

### Better approach: **Controlled micro-experiments**

- When proposing a fix to a *specific artifact* (e.g., a rule pack for `.py` files), **only apply it to a random 20% of Python projects** for 24h.
- Compare metric M between treatment (20%) and control (80%).
- If M improves *only* in treatment group, promote globally.

> **Why**: Isolates effect of change from global noise.

> **Implementation**: Extend your sync mechanism to support *partial rollout*. Add a `rollout_id` field to governance files. Sync script respects it.

> **Cost**: Slightly more complex sync, but gives causal inference.

> **Failure**: Small n (only 9 Python projects?). Then use **within-project crossover**: Apply fix Mon/Wed/Fri, revert Tue/Thu/Sat. Compare same project over time.

---

## 5. **What should a human still see?**

The operator wants to be out of the loop—but **must see signals that indicate systemic decay, not daily noise**.

### Minimum viable human interface:
- **Weekly digest email** with:
  - Top 3 *confirmed* improvements (metric moved as predicted).
  - Top 3 *failed hypotheses* (fix merged but metric didn’t move).
  - Any **auto-reverts** (from shadow mode or 3-failure cap).
  - **Quota burn rate**: “At current pace, quota exhausted in X days.”
- **Real-time alerts only for**:
  - Infrastructure drift > 0 (projects out of sync).
  - Gate check coverage drop (e.g., <95% of checks are non-vacuous).
  - Fixer attempting to edit deny-listed files (even if blocked).

> **Never show raw metrics daily**. Humans will overreact to noise.

> **When to stop and ask**: 
> - 3 consecutive failed hypotheses on the same artifact type.
> - Quota projected to exhaust in <2 days.
> - Shadow mode detects output divergence >5%.

---

## 6. **What are we not thinking about at all?**

### Critical blind spots:

#### A. **Model drift and version skew**
- Your agents likely use multiple LLM versions (via rotation). A “fix” that works on Model A may fail on Model B.
- **Solution**: Tag every session with `model_version`. Stratify metrics by model. Never merge a fix validated only on one model.

#### B. **Stateful agent memory**
- Agents may carry context across sessions (e.g., via file edits). A fix that works in isolation may fail when combined with prior agent state.
- **Solution**: Include “stateful replay”: replay sequences of sessions, not just single sessions.

#### C. **The meta-stability trap**
- If the fixer improves efficiency, agents complete more tasks/day → more sessions → more opportunities for failure → more fixes needed. The loop accelerates until quota exhaustion.
- **Solution**: Cap *total daily agent output* (e.g., max 100 autonomous tasks/day). Let the fixer optimize *within* the cap, not expand it.

#### D. **Credential leakage via diffs**
- Even with deny-lists, a clever fixer might embed secrets in error messages or logs that get committed.
- **Solution**: Run `git-secrets` or `trufflehog` on every proposed diff before merge.

#### E. **The “correctness illusion”**
- Gates and rules enforce *process compliance*, not *correctness*. An agent can follow all rules and still produce broken code.
- **Solution**: Inject **oracle tests**—small, human-written assertions about critical behaviors (e.g., “this function must not call network”). Run these in shadow mode.

---

## Final Recommendation

**Do not implement the proposed one-fix-per-day loop.** It will appear to work for 2–3 weeks, then begin producing plausible but harmful changes that evade detection until damage is widespread.

Instead, adopt a **replay-based, counterfactual, shadow-mode verified loop** with:
- Micro-experimentation for attribution,
- Triple-layer verification (static + replay + delayed oracle),
- Causal metrics with clean denominators,
- Human alerts only for systemic risks.

This costs ~2–3× more in compute/quota upfront but prevents catastrophic silent failures. Given your constraint of limited quota, **prioritize verification over velocity**. One verified fix per week is better than seven unverified ones.

The goal isn’t just *daily* action—it’s *reliable* self-improvement. Speed without verification is technical debt with compound interest.



---

## openai/o3-pro

Independent design review – 2026-08-16

================================================================
I have read the whole description, the data and the proposal.  
Below is my own judgement.  I try to point out failure modes that will bite you later, suggest a more reliable metric set, tighten the “actor” safeguards, and sketch a different experimental design.

----------------------------------------------------------------
1.  Is the daily closed-loop shaped right?
----------------------------------------------------------------
Good parts
•	Instrumentation first, action second, and require the number to move before claiming success – correct principle.  
•	Isolated work-tree and “never trust what the session says” – essential.

What breaks after 60 days
•	Back-pressure / backlog explosion.  You observe dozens of defects per day but only let one through the pipe.  After two months you will have >1 000 open findings.  Their contexts rot; the metric that motivated them may have vanished.  
•	Local optimisation, global stasis.  One-fix-per-day tends to pick the cheapest, most detectable symptom, not the root cause with the biggest swing.  You will polish minor lint errors while a design flaw that costs 25 % of all turns sits untouched.  
•	Unbounded measurement drift.  As projects, models and work-mix change the baseline of every metric drifts.  Without a control group (see §4) you will celebrate or condemn noise.  
•	Merge conflict storm.  Twelve daily infrastructure commits that touch shared files are fine; sixty days later you are rebasing forty-six repos every morning and human sessions work on stale trees.
•	Resource starvation.  A headless fixer that fires even when quota is critically low can steal the tokens a high-value human session needs to ship revenue work that day.

Recommended reshaping
a.	Keep the single isolated “actor” but allow N find-fixes per day, where N = min( open quota bucket / X, 5 ).  Make the backlog explicit and prioritised (see metrics section).  
b.	Run the loop only if quota > H water-mark and expected impact > threshold.  
c.	Group findings that touch the same file set and let the actor fix them in one shot; this preserves causal attribution (the unit under test is the file set, not the line).  
d.	Add a weekly “deep” cycle in which a more expensive model may propose architectural fixes that are too large for the daily loop.

----------------------------------------------------------------
2.  What should be measured?
----------------------------------------------------------------
Principles
•	A metric must correspond to user-visible harm or cost.  
•	It must be attributable to a single commit within a short window.  
•	It must be guarded against Goodharting by either a hold-out set or an independent oracle.

Concrete metric set

A. Governance compliance (rules-obeyed)
  1.	Compliance rate = compliant_responses / obligated_responses  
     – denominator = turns that are either (a) code-writing, (b) review-writing, (c) command reply, identified by tool call presence or BEGIN/END markers.  
  2.	Duplicate terminator rate.  
  3.	Stop-hook override events (agent tries to exit while gate red).  
  Guard: a suite of synthetic transcripts injected nightly; compliance must stay 100 % on them.

B. Velocity/Cost
  4.	Median review rounds per ticket type (separate code-review, plan-review).  
  5.	Cycle time = (first human request → gate green commit) p50/p90.  
  6.	Token spend per merged LOC (fleet and per-project).

C. Correctness / Stability
  7.	Gate pass rate on first attempt.  
  8.	Post-merge revert rate (proxy for latent defects).  
  9.	Mutation-testing score of the rule/gate suite itself (see §3).

D. Reliability of subagents
 10.	Failure rate, p90 latency, cost spikes.

Metrics to drop or alter
•	“Sessions per day” -- not actionable; use cycle time.  
•	Raw “RULES ACTIVE line present” – replace with A.1/A.2 split.  
•	30-day mixed review mean – confounded, drop.  
•	$ cost/day – subscription quota, not cash, matters.

----------------------------------------------------------------
3.  Verification – keeping the fixer honest
----------------------------------------------------------------
Additional safeguards

1.	Immutable measurement package
   •	Mark the collector and its tests read-only for the AI id (chmod 0555, Git attribute).  
   •	Gate refuses any diff touching paths under /metrics or /collector.  
   •	Human review required to change them.

2.	Sentinel tests / mutation testing
   •	For every gate rule add one positive and one negative sentinel case in a synthetic repo.  
   •	Nightly job mutates each rule (invert predicate, delete line) and confirms gate fails.  
   •	A commit that makes any mutant survive is blocked.

3.	Two-phase merge
   •	Fix is first merged into a staging branch.  
   •	Collector runs on a 24 h slice of live traffic replayed in Docker against that branch.  
   •	If deltas are positive and no sentinel fails, change is promoted to main and fanned out.

4.	Cross-model attestation
   •	Use a second, cheaper model that was not involved in the fix to summarise the diff and answer five yes/no questions (“Did this diff weaken a regex?”, “Did it delete an assert?”).  
   •	Collect its logits; veto if any answer scores <0.2 confidence.

----------------------------------------------------------------
4.  Attribution – proving a change moved a number
----------------------------------------------------------------
Better design than “one per day then eyeball deltas”:

1.	Canary / control group
   •	The 46 projects are split into 2³ strata: language (py/js/other) × project age (young/old) × size (small/large).  
   •	Within each stratum randomly pick 20 % as hold-out.  
   •	The daily infrastructure commit is applied only to treatment projects for 24 h.  
   •	Collector compares delta_treatment – delta_control; a paired t-test or bootstrap CI must exclude zero before the commit is promoted.

2.	Step-wedge roll-out
   •	Every day a different stratum crosses over from control → treatment, giving you multiple independent causal observations.

3.	Backlog ranking
   •	Expected Δmetric × traffic × confidence / estimated tokens = priority score.  
   •	The actor takes the top-scoring item whose predicted effect is above the minimum detectable effect given current traffic (power analysis).

----------------------------------------------------------------
5.  Minimum signal to the human operator
----------------------------------------------------------------
Deliver exactly two artefacts:

A.	Daily digest (JSON + 80-char human e-mail)
   •	actor_attempt: {status, finding_id, token_cost, diffstat, sentinel_pass}  
   •	key_metrics: {A1…D10 24 h deltas vs control, spark-line 7 d}  
   •	alerts: {quota_low, sentinel_fail, >2σ regression, backlog > N}.  
   The human never opens a dashboard; his mail client is enough.

B.	Pager rotation
   •	If any of: three consecutive actor failures, gate global pass rate < 95 %, sentinel fails, quota < 10 % – send a high-priority push and pause the loop.

----------------------------------------------------------------
6.  What you are not thinking about
----------------------------------------------------------------
•	Data retention / replay.  For attribution and post-mortem you need deterministic re-execution of yesterday’s traffic.  Store tool I/O, model responses and environment snap-shots for 7 days compressed, or you cannot debug a bad commit.  
•	Model drift / version pinning.  If OpenAI silently ships gpt-4.5 tomorrow all your deltas confound.  Pin model versions and record them in every ledger row.  
•	Concurrency hazards in the shared work-tree even for read-only operations (the “CI fixer” problem shows that `git status` is not free).  Mount a tmpfs overlay per session and commit through that; do not rely on `git worktree add` alone.  
•	Gradual credential leakage – the actor could add a verbose log line printing env vars and blow past your deny-list.  Run it in a stripped environment and only mount the minimal token file it needs.  
•	Disaster recovery.  One bad infrastructure sync today pushes a syntax error to 46 projects.  Keep a proven-green rollback tag and a one-liner script the human can run to revert every repo in 30 s.

----------------------------------------------------------------
Implementation sketches and failure modes
----------------------------------------------------------------
•	Sentinel framework – pytest plugin that discovers *.sentinel.txt pairs; mutation tool flips lines, runs gate; fails if any mutant survives.  Failure mode: Sentinel corpus grows stale; schedule quarterly manual review.

•	Collector hold-out logic – write project id → cohort file; failure mode: A new project is born outside cohorts; add hook in scaffold to register itself.

•	Quota guard – actor.sh checks `$(quota_remaining)`; race if human session starts between check and spend; fix by using atomic redis INCR scripts.

•	Two-phase merge – use GitLab environment promotion; failure mode: staging data hits disk quota; cron cleans staging trees >3 d.

----------------------------------------------------------------
Bottom line
----------------------------------------------------------------
The current plan is directionally correct but under-powered against measurement drift and Goodhart attacks, and it will choke on backlog and attribution.  Introduce cohort-based controlled roll-out, richer compliance + velocity + stability metric set, invariant guards (sentinels + immutable collector), and a quota-aware prioritised backlog.  Give the human a single daily JSON digest and a pager on red lines.  With those changes the loop can run for months without silent quality decay.



---

## FUSION SYNTHESIS (wave 1)

# VERDICT

**Keep the instincts; do not ship the loop.** All four reviewers converge on the same judgment from different angles: the proposal's *epistemics* are right (instrument first, distrust the agent's self-report, isolate, one hypothesis, revertible) and its *control design* is wrong (fleet-wide instant promotion, next-day mean as judge, the gate policing the gate, "the number moved" as the acceptance test). Three of four say explicitly: don't turn the actor on yet. The fourth (o3-pro) says "directionally correct" but then demands cohorts, sentinels, and an immutable collector as preconditions — which is the same answer in a friendlier tone.

**Prerequisites before any autonomous promotion** (union of what all four gate on): (1) a landing protocol — versioned/pinned governance packages, sync-on-idle not mid-turn, session-pinned rulepack; (2) holdout/shadow capability in the sync layer; (3) collector denominators fixed and frozen with checked-in fixtures; (4) a labeled replay corpus (40–200 traces) run against *rendered* artifacts; (5) mutation fixtures + assertion-surface snapshot for the existing gate checks; (6) write-allow-list enforced in the promotion path, not just a deny-list.

---

## 1. Consensus (unanimous or 3/4 with no dissent)

1. **"Nothing counts as fixed until the number moves" must be replaced.** A number moves for calendar, quota rotation, project mix, and gaming reasons; good fixes (rare-path gates, scaffolds, denominator repairs) often move nothing. Acceptance rule: *trusted verification + controlled exposure + target improves + no guardrail regresses*. "Didn't move / underpowered" is a legal, non-punitive outcome.
2. **Next-day fleet-mean adjudication is causally empty.** You already have the proof in-house: 4.8 mixed-era vs 3.2 ticket-era. A daily blended mean *hides* real effects, and an auto-fixer would then act on the hiding.
3. **Re-running `final_gate.py` is not verification when the gate is in the change surface.** Six checks that PASS while asserting nothing means "all checks passed" currently has weak semantic value. Required: something outside the actor's reach — protected invariants/constitution, mutation or sentinel fixtures (known-bad tree must fail), an assertion-surface count that may not shrink.
4. **Current metrics are unfit to steer an actuator.** Junk for control: compliance % with a denominator of all responses (conflates omit-once with emit-36-times), 20/91 "lacked RULES ACTIVE" (conversational turns owe nothing), mixed-era review rounds, session-selection by file mtime, raw session counts. Report p50/p90 with n and min-n gating, not means (3.2 with n=12 is exploratory, not a baseline).
5. **Steer on outcomes, watch ritual.** Time-to-correct-land, review rounds (ticket-era only), rework/revert/post-land-defect, human-unstick rate, quota per accepted task. Compliance and gate-pass are *control* metrics, never the objective — a loop allowed to write the rules cannot be scored on rules-obeyed.
6. **Goodhart is the primary threat, not incompetence.** Never optimize a single number: pre-declare one target plus guardrails and require Pareto-safety. The dangerous 60-day outcome is a platform excellent at response formatting and worse at correctness.
7. **Instant sync to ~46 repos is unacceptable blast radius.** Governance changes are fleet releases and need versions, canaries, and per-project coverage reporting.
8. **Quota is the real budget, and the fixer taxes production.** Off-peak windows, hard caps, metered/cheap models for diagnosis and criticism, and "quota per accepted improvement" as a line item.
9. **Human interface: no dashboard.** One terse decision notice with the proof, plus a hard interrupt on invariant breach. Escalate definitional changes (what counts as a task, a round, a success), never "yesterday's metric was 36%."
10. **Deny-list is insufficient**; use a write-allow-list, stripped environment, no credentials mounted, promotion by a separate process — plus secret scanning on every proposed diff.

---

## 2. Contradictions, adjudicated

**a) Is the loop too fast or too slow?** Qwen says one-per-day invites silent compounding *and* starves learning; o3-pro's dominant worry is the opposite — backlog explosion, >1,000 rotting findings, cheapest-symptom selection. Grok says one *promotion window* is right but one arbitrarily-selected finding is wrong; GPT-5.6 says one-per-day is a blast-radius policy misdescribed as an attribution strategy.
**Resolution: decouple generation from promotion.** Candidate generation and replay falsification are cheap and carry zero blast radius — run many. Promotion of *enforcing* changes is capped (one per off-peak window). Grok's point settles the surface question: **one hypothesis ≠ one file hunk**; splitting a coherent fix across three days confounds you with yourself.

**b) Replay vs field cohorts as the attribution engine.** Qwen: replay solves attribution ("identical inputs"). o3-pro: randomized strata + paired t-tests. Grok/GPT-5.6: replay for policy causality, holdout/shadow for the field, and no pretense of significance at n=46.
**Resolution: a hierarchy, plus a distinction none stated cleanly.** Replay validates *deterministic* infrastructure — parsers, globs, gate predicates, rendered-command assembly. It **cannot** validate instruction/wording changes, because mocked model responses cannot respond to a changed prompt. So: deterministic changes → replay is authoritative; behavioral/instruction changes → shadow then canary, replay is only a regression check.

**c) Statistical ambition.** o3-pro's 2³ strata × 20% holdout with t-tests is not credible here — several strata will hold one or two projects, and the 7–73% compliance spread proves projects are not exchangeable. GPT-5.6 and Grok are right: use cohorts as **bias control**, report effect sizes and stratified deltas, and make "parked — underpowered" a first-class verdict.

**d) What "shadow mode" costs.** Qwen's shadow = run old and new infra in parallel on live sessions at 2–3× compute. That directly contradicts the unanimous finding that quota is binding. Grok's version — a new predicate logs `would_have_blocked` without enforcing — is near-free.
**Resolution: shadow means non-enforcing observation, not dual agent execution.**

**e) How the collector is protected.** All agree the actor can't edit it. But the collector has *known definitional bugs*, so it must change. o3-pro: `chmod 0555` (insufficient — filesystem perms don't control a diff applied by a promoter; the control belongs in the promotion path). Grok: definitions in markdown are read-only too, one outcome formula is held out from the fixer entirely, and the collector itself gets canaried by running old and new definitions side-by-side for 7 days. GPT-5.6: a replay corpus is a *stronger* protection than a prohibition.
**Resolution: human-authored collector changes + fixtures that must evaluate both ways + dual-run before switching the number. The actor never switches the number it is judged on.**

**f) Minor:** o3-pro says 42 gate checks where the record says 57, prices spend per *merged LOC* (rewards verbosity — use per accepted task), and proposes vetoing on a critic model's yes/no *logit confidence*, which is not calibrated. Grok's ordering is correct: mechanical critics (AST assertion surface, mutation fixtures, MUST-count, glob volume) are load-bearing; the LLM critic is extra.

---

## 3. Partial coverage — raised by one or two, adopt anyway

| Item | Raised by | Why it matters |
|---|---|---|
| **Typed append-only event stream** replacing prose parsing as the authority for compliance | GPT-5.6 only | Highest-leverage single item; most current metric defects are parsing/denominator artifacts. Transcripts become forensics, not the meter. |
| **Session-pinned law**: pin rendered command + rulepack hash at SessionStart; gate/Stop evaluate the pin until the run record closes | Grok only | A 14:00 promote otherwise rewrites the rules under live agents — an unmeasured intervention in every session, plus real breakage. |
| **Landing protocol into 46 already-dirty trees**; pre-commit sync ⇒ the fleet is *never* on one version; track **sync skew** | Grok (GPT-5.6 partially) | Kills attribution and can strand a project on a bad rule. |
| **Transactional merge**: lease, rebase onto current HEAD, re-run the *entire* battery post-rebase or abort | GPT-5.6, Grok | Worktree isolation solves dirty-tree skip, not merge races. |
| **Project-local vs hub-global triage**; the 7–73% spread is probably scaffold/override, not a missing sentence | Grok (GPT-5.6 as "wrong control surface") | A hub-only actor writes global nags that punish the compliant project. Non-action and "wrong surface" must be legal verdicts. |
| **Strategy escalation** after 3 failures (change the surface, not the sentence) | GPT-5.6 only | Otherwise 3-strike park just buries the finding. |
| **Data-quality metrics as first-class**: "not actionable, 18% unclassified" blocks automated action | GPT-5.6 only | The min-n/completeness gate that prevents acting on noise. |
| **Stop-hook gaming**: junk commit to satisfy the exit condition | Grok only | Direct consequence of your own hook design; belongs in the corpus as a labeled fault with a detector. |
| **Scaffolds are delayed weapons** — no daily metric moves; they birth the next 10 projects wrong | Grok, GPT-5.6 | Always human-reviewed, never auto-promoted. |
| **Meta-stability**: fixer success → more sessions → more quota burn → exhaustion | Qwen only | Needs a quota governor, not a task cap. |
| **Tested fleet rollback + transcript retention/redaction** | o3-pro, GPT-5.6, Qwen | Revertibility ≠ harmlessness; 5,317 transcripts are a secret-bearing corpus. |
| **Decision log against operator atrophy / taste drift** | Grok only | At day 60 he must be able to re-acquire sovereignty; constitution diffs are the only thing he *must* read. |

---

## 4. Blind spots — where all four are weak or silent

1. **The action space is additive; nobody proposes shrinking anything.** Only Grok gestures at this (command mass as a guardrail). A self-improving governance system whose only move is "edit a rule" will monotonically grow 203 artifacts toward 400. No expert entertains the strongest hypothesis on the table: that **203 governance artifacts for one operator is itself the defect**, and the highest-value fix is deletion. Add an explicit simplification objective (rendered token mass, artifact count, checks per land, MUST-count) that must trend *down* over quarters.
2. **The outcome metrics they trust are endogenous.** All four escape Goodhart by moving to "escaped defects / rework / review-reject / revert." In this fleet, tests, reviews, gates, and reverts are all produced by the same agents and rules being optimized. There is no exogenous oracle. Only Qwen gestures (human-written oracle tests). Something outside the loop must anchor correctness: a small human-authored acceptance suite per project, or genuinely external signals (production failures, user-visible breakage).
3. **Cost of the apparatus, and who verifies the verifier.** The union of these four answers is several person-months of work — typed events, 200 labeled traces, 57×2 mutation fixtures, constitution + invariants, cohort sync, promotion controller, critic — to be built *by the same unreliable agents that motivated it*. And the verification layer becomes a new unverified surface: the six hollow PASSes will recur as hollow mutation fixtures. Only Grok gives a build order; none gives a minimum viable version sized to one operator, or a fixture-rot owner.
4. **The human's attention is the unpriced bottleneck.** Every reviewer routes class-A changes, invariant edits, and definitional changes to the human — while the stated goal is getting him out of the loop. If 30% of findings are class A, the loop stalls or he rubber-stamps (worse than stalling). Needs an explicit attention budget (≤N decisions/week; exceed it and the loop *pauses*) and a default for unanswered asks (default = park, never proceed).
5. **No dwell/hysteresis; the loop can oscillate.** A daily actuator with multi-day outcome windows is a control system with delay and unbounded gain. Nothing prevents change → revert → re-apply on the same surface. Add a cooldown per surface, damped step size, and a periodic **backtest of past promotions** ("of the last 30, how many still look right?"). Nobody proposed re-litigating history.
6. **Account rotation is an existential single point of failure.** "Three accounts empty in ~2 days" plus automated headless daily dispatch is a plausible terms-of-service and ban risk that would kill all 46 projects at once. Not one reviewer mentions it.
7. **No graceful degradation, and no meta-experiment on the loop itself.** What happens when the loop is off (vacation, quota exhausted, provider outage)? Governance must be valid unattended. And nobody pre-registers the loop's *own* success criteria: run a time-holdout with the fixer off, and if it cannot demonstrably pay for its quota in landed work, turn it off.

---

## 5. The reconciled design, compressed

**Build order (inverting this automates a lie):** landing protocol + holdout pins + session-pinned rulepack → metric surgery (split omit vs. duplicate-emit, obligated-turn denominators, session windows not mtime, min-n, collector fixtures) → mutation fixtures + assertion-surface snapshot for existing checks → replay corpus v0 on *rendered* artifacts → triage policy as tested code → actor on allow-listed paths, metered model, off-peak → shadow default, canary for enforcing changes, human for hooks/gate-semantics/sync/scaffolds/constitution.

**Acceptance rule:** replay/fixtures move as predicted **and** assertion surface does not shrink **and** guardrails hold **and** (for behavioral changes) canary-vs-holdout beats a pre-registered threshold over a pre-registered window with min-n met. Otherwise: revert, or park as underpowered.

**Daily rhythm:** observe continuously; generate and falsify candidates freely; promote at most one enforcing change per off-peak window, only if no live session pins the affected files and quota cap holds. Human sees decision notices and halts; he is asked only when the loop wants to change the definition of good.

**The one line to keep from the operator's own experience:** verify the instrument before believing the number. §5 as written puts an agent in charge of the plant while using an unverified, confounded instrument as its reward — the same mistake, automated, aimed at 46 repositories simultaneously.



---

## qwen/qwen3.8-max

## Bottom line

The ambition is correct: you need machinery that makes the agents correct by default, because human review across 46 projects does not scale. But I would **not** build the proposed “daily actor” as described. It is conceptually close to a good scientific loop, but it is unsafe and statistically unsound in several places.

The most dangerous assumptions in the current proposal are:

1. **“Green gate” is treated as an independent oracle, even though the fixer may modify governance, rules, commands, or gate-adjacent behavior.**  
   If the system being fixed can alter the thing that declares it fixed, “green” is not proof.

2. **Next-day fleet metric movement is treated as causal adjudication.**  
   With 16–91 sessions/day, changing project mix, changing task types, model/account rotation, and tiny samples like `n=12` review ledgers, next-day movement is mostly noise unless the change is large and the metric is high-volume.

3. **A daily calendar cadence is imposed on high-blast-radius global changes.**  
   Daily observation and triage: yes. Daily global mutation of governance that affects 46 repos: no. The right cadence is risk-based, not date-based.

4. **The physical concurrency model is still the weakest link.**  
   Three agents sharing one working tree plus pre-commit sync to 46 repos is a structural accident waiting to happen. An isolated worktree for the fixer helps the fixer, but it does not protect the fleet from the merge/sync side effects.

5. **“Nothing counts as fixed until the number moves” is wrong for rare but severe defects.**  
   Some fixes are valuable precisely because they prevent rare failures that will not produce a statistically visible movement in one day. A reproducible failing test moving to passing is often better evidence than a noisy fleet metric.

My independent recommendation:

> Build a **daily observability and hypothesis loop**, but do not make it a daily global auto-patcher.  
> Build a **proving ground** and a **risk-tiered change government** first.  
> Allow autonomous merging only for narrow, low-blast-radius changes with strong deterministic proof.  
> Treat all enforcement, measurement, sync, hook, and scaffold surfaces as protected unless canary/shadow evidence and exceptional verification exist.

The rest of this document explains where I disagree, what I would measure, how I would verify, how I would handle attribution, what the human should see, and what you are probably not thinking about yet.

---

# 1. Is the loop shape right?

## 1.1 What is good in the proposed shape

Several instincts are correct:

- **One finding at a time** is better than batch mutation.
- **Evidence dossier rather than vague instruction** is correct.
- **Isolated git worktree** is correct in spirit.
- **Independent verification** is correct in spirit.
- **Failed attempts are recorded, not treated as success** is correct.
- **Fixer may not edit measurement code** is correct but insufficient.
- **Hard deny-list and escalation after repeated failure** are sensible.

So the problem is not the general desire for a closed loop. The problem is that the proposed loop skips several layers that are mandatory when the thing being improved governs the improver.

---

## 1.2 What is wrong with “observe → one fix → verify → adjudicate next day”

### Problem 1: The gate is not an independent verifier if the fixer can affect gate-adjacent surfaces

You already found six gate checks that reported PASS while asserting nothing. That is the warning shot.

If the actor changes:

- a gate check,
- a rule pack,
- a command prompt that influences whether agents trigger a gate,
- a run-record terminal condition,
- a Stop hook,
- a scaffold that causes future projects to omit checks,
- or the data emitted into transcripts/ledgers,

then re-running “the full gate” is not independent verification. The actor may have changed the definition of green.

The current guard — “fixer may never edit the measurement code” — is necessary but far too narrow. The fixer also should not autonomously edit the **oracle**, and the oracle includes:

- `final_gate.py`,
- gate checks,
- hooks,
- run-record schema/terminal conditions,
- sync scripts,
- scaffold defaults,
- policy/deny-list files,
- proving-ground fixtures,
- metric definitions,
- adjudication code,
- anything that emits telemetry used by metrics.

If those are editable by the daily actor, the loop can accidentally or adversarially weaken its own definition of correctness.

---

### Problem 2: “Merge only on green” is not enough when green is mutable

A correct verification layer must answer:

1. Does the change do what it claims?
2. Does it avoid weakening existing enforcement?
3. Does it still catch known bad cases?
4. Does it introduce false positives?
5. Does it change agent behavior in ways not covered by tests?
6. Does it survive contact with the 46-repo fleet?

“Gate is green in the worktree” answers only a small part of #1.

You need a **proving ground**: a battery of deterministic, adversarial, and behavioral tests that run before any fleet-facing merge.

---

### Problem 3: Next-day adjudication is too noisy for most metrics

You have:

- 16 sessions on a quiet day,
- ~91 on a busy day,
- 10 projects on the quiet day,
- 98 project dirs historically,
- only 12 ticket-era review ledgers,
- process change on 2026-08-09,
- model/account quota rotation,
- varying project mix,
- varying task mix.

In that environment, “metric moved tomorrow” is not a reliable causal test.

Example:

- Review rounds drop from 3.2 to 2.6 tomorrow.
- But tomorrow happens to have easier tickets, fewer new projects, a different model account, or fewer complex refactors.
- The loop declares success.

Or:

- A real improvement needs 5 days to appear in review rounds.
- The loop sees no movement after 1 day and declares failure.
- It retries with a more aggressive patch.
- Now you have churn, not learning.

The adjudication window must be metric-specific. Fast operational metrics can be daily. Slow outcome metrics need longer windows, benchmark evidence, or canary evidence.

---

### Problem 4: One change per day is the wrong unit

The right unit is not “one change per day.” The right unit is:

> One hypothesis with a bounded blast radius, a reproducible test, a verification plan, an expected effect, and a rollback path.

Some days the correct output is:

- no change,
- a new failing test,
- a measurement defect report,
- a human approval request,
- a shadow-mode experiment,
- a canary deployment,
- a rollback,
- or a postmortem.

If the system is forced to produce one fix per day, it will eventually invent fixes to satisfy the cadence.

A better rule:

> Daily triage and experimentation.  
> Merge only when the change class and evidence justify it.  
> Some experiments take hours; some take days; some should not merge at all.

---

## 1.3 What breaks after 60 days?

If you run the proposed loop unchanged for 60 days, I expect one or more of these failure modes:

### 1. Goodhart collapse

The loop learns to improve the measured surface, not the underlying quality.

Examples:

- Add boilerplate instructions to commands so agents emit `GATE:/DONE:/NEXT:` more reliably. Compliance rises. Correctness does not.
- Make a gate check less strict. Gate pass rate rises. Escaped defects rise later.
- Make Stop hook less annoying. Stop-hook interventions fall. Agents end turns with unfinished work more often.
- Encourage earlier review acceptance. Review rounds fall. Post-accept defects rise.

### 2. Oracle drift

The system’s tests, gates, and metrics slowly become aligned with the changes being made, rather than with the operator’s intent.

After 60 days, you can end up with a platform that is very good at passing its own checks but worse at producing trustworthy software.

### 3. Rule bloat and contradiction

The fixer adds rules, fragments, gates, or command instructions to solve local symptoms. Over time:

- rule packs overlap,
- commands become longer,
- agents waste quota on boilerplate,
- instructions conflict,
- new projects inherit increasingly brittle scaffolds.

This is especially likely because the loop is optimizing for observable defects, not for simplicity or coherence.

### 4. Metric chasing

The actor selects findings that are easy to measure, not findings that matter.

For example, it may optimize terminal-block compliance because that is easy to count, while ignoring subtle command-prompt defects that cause bad code but are hard to measure.

### 5. Attribution rot

Because adjudication is too fast and too global, the experiment ledger fills with false positives and false negatives. The system no longer knows which changes helped, which hurt, and which did nothing.

### 6. Quota starvation

A daily headless dispatch consumes subscription quota. If the change probability or expected benefit is low, the loop burns quota that human sessions need.

### 7. Escalation fatigue

The loop escalates after three failed attempts, but if findings are poorly chosen or metrics are noisy, escalations become frequent and useless.

### 8. Hidden concurrency damage

The fixer uses a worktree, but merges into a hub whose shared tree is dirty and whose sync process touches 46 repos. Eventually a sync collides with an agent’s uncommitted state, or a governance update breaks a project mid-session.

---

## 1.4 The loop shape I would use instead

I would split the system into four planes.

### Plane A: Constitution

A small, protected set of invariants the loop may not violate.

Examples:

- Stop hook must block red gate.
- Commits must have provenance trailers.
- Gate checks must have known-bad fixtures.
- Measurement code may not be edited by the actor.
- Sync must be reversible.
- Credentials and crontab are untouchable.
- No autonomous decrease in enforcement strength without human approval.

This should be machine-checkable where possible.

### Plane B: Observatory

A trusted measurement layer with:

- event schema,
- run-record identity,
- metric tests,
- data-quality gates,
- incremental parsing,
- baselines,
- anomaly detection.

If the observatory is unhealthy, the actor does not act.

### Plane C: Proving Ground

A change-validation layer with:

- unit tests,
- render tests,
- rule activation tests,
- gate golden tests,
- mutation tests,
- sandboxed behavioral evals,
- shadow mode,
- canary support,
- semantic diff review,
- rollback generation.

No behavioral governance change should reach the fleet without passing this.

### Plane D: Change Government

Risk-tiered policy that decides what may merge automatically.

For example:

| Tier | Change type | Autonomous merge? |
|---|---|---|
| 0 | Docs/comments with no agent-facing effect | Yes, if lint passes |
| 1 | Additive telemetry, new test fixtures, advisory-only checks | Yes, if isolated and non-blocking |
| 2 | Command wording, rule wording, non-critical prompts | Only after proving ground and preferably canary/shadow |
| 3 | Blocking gate logic, Stop hook, run-record terminal logic, sync, scaffold defaults | No autonomous merge; human approval required |
| 4 | Credentials, crontab, deny-list, measurement/oracle code | Never by the actor |

The current proposal treats too many surfaces as if they were Tier 2 when they are actually Tier 3.

---

## 1.5 Revised daily cycle

A better daily cycle looks like this:

```text
1. Preflight
   - Is data fresh?
   - Do metric tests pass?
   - Are guardrails green?
   - Is quota available?
   - Is there an active incident or freeze?
   If any red: stop and report.

2. Collect and normalize
   - Ingest new transcripts, ledgers, gate logs, sync logs, run records.
   - Validate schema.
   - Reject unknown status values instead of guessing.

3. Detect and rank findings
   - Metric anomalies.
   - Known defect patterns.
   - Gate false-negative candidates.
   - Rule activation failures.
   - Sync drift.
   - Command render issues.
   Rank by expected value, confidence, blast radius, and fixability.

4. Choose an action class
   - No change.
   - Add measurement/test.
   - Create human proposal.
   - Run sandbox experiment.
   - Low-risk autonomous patch.
   - Canary/shadow experiment.

5. If patchable and low-risk:
   - Generate dossier.
   - Generate or require failing test.
   - Dispatch sandboxed patch agent with no push rights.
   - Verify with proving ground.
   - Merge only if risk tier allows.

6. If behavioral/global:
   - Do not merge globally.
   - Put into shadow/canary if possible.
   - Adjudicate over appropriate window.

7. Post-deploy monitoring
   - Watch veto metrics.
   - Automatic rollback on guardrail breach.

8. Daily attestation
   - One short report.
   - Exceptions only if action needed.
```

This is still daily. But it is not “daily global mutation.”

---

# 2. What should actually be measured?

The operator’s goal has four components:

> fastest, most accurate, correct, rules-obeyed.

Those are not one metric. They are a Pareto surface. If you optimize one without veto metrics, the system will sacrifice another.

I would not create a single composite score except maybe as a weak monitoring artifact. Composite scores are extremely Goodhart-vulnerable.

Instead, use metric families with counter-metrics.

---

## 2.1 Current metrics: what is junk, what is promising

### Sessions per day

**Verdict:** context only, not quality.

Useful for interpreting denominators and day-type variance. Not a success metric.

### Rules-compliance 36%

**Verdict:** currently junk as a driver.

The metric conflates:

- missing required terminal block,
- repeated terminal block,
- invalid terminal block,
- conversational responses that owe no block,
- read-only sessions,
- non-terminal responses,
- run-record absence.

It should be split into several precise protocol metrics with run-level denominators.

### Subagent failure rate 4%

**Verdict:** useful but too coarse.

It needs:

- canonical status mapping,
- task_type denominators,
- model/account segmentation,
- distinction between `error`, `capped`, and `out_of_scope`,
- retry analysis.

A global failure rate can hide the fact that hard tasks are being avoided or classified as out of scope.

### Review rounds per ticket: 3.2

**Verdict:** promising, but not yet strong enough for adjudication.

`n=12` is too small. It should be stratified by:

- project archetype,
- ticket complexity,
- plan type,
- model/account,
- reviewer type,
- era.

It also needs counter-metrics: first-pass acceptance and post-accept defect rate.

### Mixed 30-day review rounds: 4.8

**Verdict:** misleading for decisions.

The era mix hides the process change. Keep it only as historical context.

### Cost per day: $0.74

**Verdict:** context only.

Better: cost/quota per clean successful run, per ticket, or per completed task.

---

## 2.2 Metric zero: instrument health

Before any other metric is trusted, you need a meta-metric.

### Instrument health

Definition:

- Collector ran on time.
- Input data is fresh.
- Schema validation passes.
- Metric unit tests pass.
- Known golden inputs produce known outputs.
- Unknown statuses are zero or explicitly quarantined.
- Run-record coverage is above threshold.
- Denominators are stable.
- No parser anomaly spike.

Implementation:

- Put metric definitions in code.
- Give each metric golden inputs and expected outputs.
- Run metric CI daily.
- Version metric definitions.
- If a metric definition changes, invalidate old experiments unless explicitly migrated.

Failure mode:

- Too strict, and every small schema change blocks useful work.
- Too loose, and the loop acts on garbage.

Mitigation:

- Separate hard failures from warnings.
- No autonomous merges when instrument health is red.
- Human approval required for metric definition changes.

This is not optional. Your two collector bugs already prove the need.

---

## 2.3 Delivery and correctness metrics

### 1. Clean Run Completion Rate

Definition:

> Of runs intended to produce a deliverable, how many end with a valid terminal run record, green gate, committed/pushed artifact, no Stop-hook violation, and no stuck open record?

Denominator:

- task-completing runs,
- not messages,
- not sessions,
- not conversational replies.

Implementation:

- Run record must include `run_id`, `command`, `project`, `branch`, `infra_sha`, `model`, `account`, `task_type`, `start_ts`, `end_ts`, `terminal_status`.
- Stop hook and gate logs link to `run_id`.
- Git commit trailers include `Run-Record-Id` and `Infra-Version`.

Goodhart risk:

- Agents may close runs without doing meaningful work.

Counter:

- Track “empty deliverable” runs.
- Require diff/test evidence for task-completing runs where applicable.
- Sample-audit closed runs.

---

### 2. First-Pass Gate Rate

Definition:

> Percentage of final deliverable attempts whose first final gate run is green.

Useful for speed and rule obedience, but dangerous alone.

Counter-metrics:

- Gate false-negative rate.
- Red-corpus escape rate.
- Post-commit defect rate.
- Gate check failure distribution.

If first-pass gate rate rises while escaped defects also rise, the gate has become weaker, not the agents better.

---

### 3. Gate False-Negative / Red-Corpus Escape Rate

Definition:

> Known-bad artifacts that should fail the gate but pass.

This is one of the most important metrics on the platform.

Implementation:

- Maintain a red corpus: known bad commits, missing trailers, broken tests, rule violations, vacuous outputs, malformed run records, dangerous file edits.
- Every blocking gate check should have at least one known-bad fixture.
- Run red corpus in CI and before any gate-related merge.
- Add every real escaped defect to the red corpus.

Goodhart risk:

- The fixer may tune to the public red corpus.

Counter:

- Keep some hidden fixtures outside the fixer’s writable area if possible.
- Use separate Unix user or remote oracle if feasible.
- Periodically generate new adversarial cases.
- Treat red-corpus escape as a severe incident.

Failure mode:

- Red corpus becomes stale or overfit.
- Tests only catch old failure shapes.

Mitigation:

- Mutation testing.
- Periodic red-team runs.
- Postmortem-driven fixture growth.

---

### 4. Escaped Defect Rate / Rework Rate

Definition:

> Commits or runs that passed the gate but later required fixup, revert, human correction, or another agent session to repair within N days.

Implementation:

- Heuristics initially:
  - revert commits,
  - fixup commits to same ticket/branch,
  - follow-up sessions touching same files within 24–72 hours,
  - human-authored corrections,
  - review comments marked defect.
- Later, add explicit incident/defect ledger.

This is the primary counter-metric to gate pass rate and speed.

Goodhart risk:

- The system may hide defects by not labeling them.

Counter:

- Random sample audits.
- Red-team checks.
- External model review of sampled diffs.
- Human approval for high-risk changes.

---

### 5. Review Quality, not just Review Rounds

Review rounds alone are dangerous.

Use:

- first-pass acceptance rate,
- rounds per comparable ticket,
- severity of review comments,
- post-accept defect rate,
- review abandonment rate.

Implementation:

- Review ledgers should be structured, not scraped from prose.
- Each review row should have:
  - ticket_id,
  - plan_set_id,
  - project,
  - era,
  - task complexity,
  - reviewer type,
  - round number,
  - outcome,
  - defect severity.

Goodhart risk:

- Agents rubber-stamp earlier to reduce rounds.

Counter:

- Post-accept defects.
- Random audit of accepted work.
- Compare review acceptance with later failures.

---

## 2.4 Protocol and rule-obedience metrics

These are useful, but only after denominator repair.

### 6. Terminal Block Missing Rate

Definition:

> Among terminal task-completing runs that owe a final block, how many lack it?

Denominator:

- terminal runs requiring completion block.

Not:

- all agent responses,
- all sessions,
- conversational turns.

---

### 7. Terminal Block Duplication Rate

Definition:

> Among terminal runs, how many emit the final block more than once?

This measures the distinct forbidden failure mode you already observed.

This should be separated from missing-block compliance.

---

### 8. Terminal Block Invalid Rate

Definition:

> Final block exists but has malformed fields, wrong order, invalid status, missing `GATE:`/`DONE:`/`NEXT:` components, or inconsistent run-record state.

---

### 9. Rules Active Missing Rate

Definition:

> Among terminal runs where rule packs should be active due to edited file globs, how many lack the required `RULES ACTIVE` line?

Implementation:

- Map file edits from tool calls to rule-pack globs.
- Determine expected active rule packs.
- Compare with transcript evidence or hook logs.

If you cannot reliably determine expected active rules, do not compute this metric as a violation rate. Compute “rule activation observability” instead.

---

### 10. Rule Activation Precision/Recall

Definition:

- Recall: expected rule packs were active when matching files were edited.
- Precision: unexpected rule packs were not active.

This is more meaningful than syntax compliance.

Goodhart risk:

- Agents avoid editing files that trigger rules.

Counter:

- Track whether task requirements required those files.
- Track task success and rework.

---

### 11. Stop-Hook Intervention Rate

Definition:

> Number of Stop-hook blocks per run.

Interpretation:

- High rate: agents repeatedly try to end while red.
- Sudden zero rate: hook may be broken or bypassed.
- Increasing rate after a governance change: new friction.

Counter-metric:

- Stop-hook false-block rate.
- Stop-hook liveness tests.
- Bypass attempts.

---

## 2.5 Speed and efficiency metrics

### 12. Lead Time per Run

Definition:

> Time from run-record open to terminal success.

Segment by:

- command,
- task_type,
- project archetype,
- model/account,
- infra version.

Counter:

- success rate,
- defect rate.

Never optimize lead time alone.

---

### 13. Tool-Call Efficiency

Definition:

- tool calls per successful run,
- repeated identical commands,
- failed commands,
- loops with no file progress,
- subagent dispatches per completed task.

Goodhart risk:

- The system reduces tool calls by skipping necessary exploration.

Counter:

- Clean completion rate.
- Escaped defect rate.

---

### 14. Quota/Cost per Clean Successful Run

Better than daily cost.

Definition:

> Subscription quota or dollar cost divided by clean successful runs.

Segment by:

- task type,
- model/account,
- project,
- command.

This directly addresses the binding resource constraint.

---

### 15. Gate and Sync Latency

If the machinery is slow, agents burn quota waiting.

Track:

- p50/p95 `final_gate.py` duration,
- p50/p95 command render time,
- p50/p95 governance sync time,
- p50/p95 SessionStart/PreCompact hook time.

Counter:

- correctness metrics must not degrade when latency improves.

---

## 2.6 Fleet and infrastructure health metrics

### 16. Governance Sync Health

Definition:

- sync success rate,
- sync conflicts,
- drift between hub and projects,
- version distribution across 46 repos,
- post-sync gate/hook health.

This is critical because one bad sync can hit all 46 projects.

---

### 17. Artifact Integrity

Definition:

- all commands render,
- all fragments resolve,
- rule globs are valid,
- no orphaned includes,
- no duplicate command names,
- scaffold creation succeeds,
- gate checks are registered,
- fixture coverage exists.

Implementation:

- Daily corpus integrity check.
- Dependency graph from fragments to commands, rule packs, scaffolds.

Failure mode:

- Dependency graph incomplete.

Mitigation:

- Treat unknown dependencies as high-risk.

---

### 18. Cron and Hook Liveness

You have 21 cron jobs and 5 session hooks. These need heartbeats.

Track:

- last success time,
- failure count,
- duration,
- output schema validity.

The loop should detect dead cron jobs, but should not autonomously edit crontab.

---

## 2.7 Change-safety metrics

### 19. Experiment Pass Rate

Definition:

> Candidate changes that pass proving ground / total candidate changes.

Too high may mean experiments are trivial. Too low may mean findings are bad or verification is too brittle.

---

### 20. Merge Rate and Rollback Rate

Definition:

- merged experiments,
- rolled-back merges,
- post-merge guardrail breaches.

Rollback rate is a crucial safety metric.

---

### 21. Escalation Quality

Definition:

- escalations per week,
- fraction of escalations that required human action,
- fraction dismissed as noise.

If escalations are noisy, the human will ignore them. That is fatal.

---

## 2.8 Which metrics are most Goodhart-vulnerable?

Most vulnerable:

1. **Syntax compliance**  
   Easy to satisfy by emitting strings.

2. **Gate pass rate**  
   Easy to improve by weakening gates.

3. **Review rounds**  
   Easy to improve by rubber-stamping.

4. **Session length / tool calls**  
   Easy to improve by doing less work.

5. **Subagent failure rate**  
   Easy to improve by avoiding hard tasks or reclassifying failures.

Counter-design principles:

- Pair every accelerator metric with a brake metric.
- Require known-bad fixtures.
- Use hidden or protected evals.
- Sample-audit outcomes.
- Track rare severe events separately.
- Do not let the actor edit the oracle.
- Do not use a single composite target.

---

# 3. The verification problem: AI fixing infrastructure that governs AI

This is the hardest part. The current proposal says:

> Verify independently — never trust the session’s claim.

Correct instinct. But the proposed verification — re-run gate, corpus integrity, tests, confirm commit — is not independent enough.

You need layered verification.

---

## 3.1 First principle: the oracle must be harder to change than the system

If the actor can modify:

- gate checks,
- Stop hook,
- run-record schema,
- compliance expectations,
- test fixtures,
- sync logic,
- policy files,

then it can modify the definition of success.

Therefore:

> The actor should have no autonomous write access to the oracle.

The oracle includes:

- measurement code,
- metric definitions,
- final gate,
- hooks,
- proving-ground fixtures,
- red corpus,
- policy engine,
- deny-list,
- audit ledger,
- sync mechanism,
- scaffold defaults if they determine future enforcement.

If a finding requires changing one of those, the actor should create a proposal, not a merge.

---

## 3.2 The actor should produce patches, not pushes

The headless session should not have push rights.

Better:

1. Orchestrator creates isolated worktree.
2. Session receives dossier.
3. Session produces a patch or local branch.
4. Session cannot push, cannot edit crontab, cannot access credentials.
5. Orchestrator extracts diff.
6. Orchestrator applies policy checks.
7. Orchestrator runs proving ground.
8. Orchestrator merges only if allowed.

This reduces the risk that the session itself performs an unsafe git operation.

Failure mode:

- The session can still produce a dangerous patch.

That is why the proving ground exists.

---

## 3.3 Risk classification must be semantic, not only path-based

A deny-list is useful but insufficient.

You need a change classifier that looks at:

- file paths,
- dependency graph,
- diff content,
- artifact type,
- blast radius,
- whether enforcement strength increases or decreases,
- whether tests/fixtures are added or removed,
- whether public behavior changes.

Examples of high-risk diff patterns:

- removal of assertions,
- broad `except Exception: pass`,
- changing `blocking: true` to `false`,
- lowering severity,
- deleting tests,
- deleting known-bad fixtures,
- changing a required “must” to “should” in a rule,
- adding bypass flags,
- adding `--no-verify`,
- weakening regexes,
- expanding globs to `*`,
- changing Stop-hook terminal conditions,
- altering run-record closure rules,
- editing sync scripts,
- editing scaffold defaults,
- editing command fragments used by many commands.

Path-based deny-lists can be bypassed by editing a shared fragment that is included into a protected command. Use the dependency graph.

Failure mode:

- Static pattern checks produce false positives.

Mitigation:

- Use them as triggers for stronger review or human escalation, not always as hard rejection.

---

## 3.4 Every actionable finding needs a failing test before a patch

This is one of the most important rules I would impose.

For any finding the actor wants to fix:

1. First produce a reproducible check that fails on the current system.
   - unit test,
   - golden transcript,
   - red-corpus entry,
   - rule activation test,
   - command render test,
   - gate negative fixture,
   - scaffold smoke test.
2. If no reproducible check can be produced, the finding is not ready for autonomous fixing.
3. The patch must make the new check pass without breaking existing checks.

This changes the culture from “fix the symptom” to “prove the defect.”

It also prevents many vacuous fixes.

Failure mode:

- Some behavioral problems are hard to test.

Correct response:

- Those become human proposals or shadow experiments, not autonomous merges.

---

## 3.5 Test the tests: mutation and fault injection

The six vacuous gate checks are exactly why you need mutation testing.

For each gate check:

- known-good input passes,
- known-bad input fails,
- mutated bad inputs still fail.

Examples of mutations:

- remove provenance trailer,
- corrupt run record,
- omit final block,
- insert forbidden file,
- break test suite,
- change gate status manually,
- use wrong branch,
- leave unpushed commits,
- create secret-looking file,
- produce syntactically valid but semantically empty output.

For gate code changes, require:

- existing negative fixtures pass,
- new negative fixture for the defect being fixed,
- no reduction in mutation coverage,
- no removal of assertions without replacement.

Implementation can start simple:

- one good fixture and one bad fixture per blocking check,
- three mutation cases for high-risk checks,
- CI fails if fixtures missing.

Failure mode:

- Mutation testing becomes expensive or flaky.

Mitigation:

- Run full mutation only for changed checks.
- Run sampling nightly.
- Treat missing fixtures as high-priority findings.

---

## 3.6 Use a red corpus and red-team agent

Maintain a corpus of known bad behavior:

- bad commits,
- malformed run records,
- missing trailers,
- forbidden file edits,
- rule violations,
- early Stop attempts,
- fake compliance strings,
- vacuous gate outputs,
- broken scaffolds,
- bad command render outputs.

Periodically run a red-team process whose only job is to try to get a bad change through the system in a sandbox project.

If it succeeds, that becomes a severe finding and a fixture.

This is one of the few ways to catch “the gate is technically green but semantically empty.”

---

## 3.7 Shadow mode for enforcement changes

Any change to gate or rule behavior should first run in shadow mode if possible.

Example:

- Existing stable gate remains blocking.
- Candidate gate runs non-blocking in parallel.
- Log differences:
  - would-block cases,
  - newly-pass cases,
  - runtime cost,
  - false-positive candidates.

For rule packs or prompts, shadow mode is harder, but you can still:

- render candidate commands in a side worktree,
- run sandbox tasks,
- compare agent outputs,
- compare gate results,
- compare protocol compliance.

Shadow mode gives fleet evidence without fleet damage.

Failure mode:

- Shadow behavior differs from real blocking behavior because agents behave differently when not blocked.

True. But shadow mode is still much safer than direct global merge.

---

## 3.8 Semantic review by a separate model

Use a separate model, preferably metered and not the same session/account, to review diffs.

Prompt it with:

- the dossier,
- the diff,
- the invariants,
- the affected artifacts,
- a list of forbidden weakenings.

Require structured output:

```json
{
  "weakens_enforcement": true/false,
  "removes_tests": true/false,
  "adds_bypass": true/false,
  "changes_denominator": true/false,
  "unclear_semantics": true/false,
  "risk_tier": "0|1|2|3|4",
  "required_tests": ["..."],
  "recommendation": "approve|reject|human"
}
```

This is not a primary oracle. It is another layer.

Failure mode:

- The reviewer hallucinates or misses subtle weakening.

Mitigation:

- Use deterministic tests first.
- Treat uncertain semantic review as rejection/escalation.

---

## 3.9 Ratchet principle for enforcement strength

For autonomous changes, allow only monotonic increases in enforcement strength.

Examples:

- Add a new advisory check: okay.
- Add a new negative fixture: okay.
- Convert advisory check to blocking: not okay without canary/human.
- Remove a blocking check: never autonomous.
- Reduce severity: never autonomous.
- Broaden an exception: never autonomous.
- Delete a test: never autonomous unless replaced by stronger test and approved.

Defining “strength” perfectly is hard, but the ratchet principle catches many dangerous changes.

---

## 3.10 Protected surfaces and permissions

On a single box with one Unix user, true isolation is hard. But you should still create separation.

Minimum:

- The actor runs as a separate user if possible.
- The oracle directory is read-only to the actor.
- The worktree agent has no push credentials.
- The orchestrator has merge rights but only after policy checks.
- Audit ledger is append-only.
- Freeze file is respected.
- Watchdog cron is not editable by the actor.

Better:

- Use a bare git origin with branch protections.
- Require signed or tagged commits for merges.
- Store hidden eval fixtures in a separate service or directory with restricted permissions.

Failure mode:

- A sufficiently broken agent with same-user permissions can bypass all of this.

True. Therefore high-risk changes still need human approval or at least canary/shadow evidence. Software controls reduce accidental damage; they do not eliminate malicious or wildly confused behavior on a single-operator box.

---

# 4. Attribution: how do you know a change caused a movement?

One change per day plus next-day measurement is not an experimental design. It is a hope.

You need a causal hierarchy.

---

## 4.1 Causal hierarchy

### Level 1: Deterministic proof

Best.

Example:

- A gate check failed to catch missing provenance.
- Add failing fixture.
- Patch check.
- Fixture passes.
- All other fixtures pass.

This is strong evidence regardless of fleet metric movement.

### Level 2: Sandbox benchmark

Good.

Run identical synthetic tasks against:

- old infrastructure SHA,
- candidate infrastructure SHA.

Compare:

- success,
- gate result,
- protocol compliance,
- cost,
- latency,
- defects.

This gives causal evidence because the environment is controlled.

### Level 3: Shadow mode

Moderate.

Candidate behavior is observed alongside stable behavior in real operations, but without enforcement.

Good for false-positive/false-negative estimation.

### Level 4: Canary fleet

Good if you can implement governance versioning.

Deploy candidate to a small cohort of projects, compare against matched stable projects.

### Level 5: Global before/after fleet metrics

Weak.

Use only as corroboration, not primary proof, unless the effect is huge and the metric is high-volume.

---

## 4.2 Build a proving-ground benchmark

This is essential.

The benchmark should include small disposable projects generated from your 12 scaffold types.

Each benchmark task should be cheap and reproducible.

Examples:

1. **Simple bug-fix task**
   - Broken test.
   - Agent must fix.
   - Gate must pass.
   - Provenance must be present.

2. **Known-bad commit task**
   - Agent attempts to commit missing trailer.
   - Gate must block.

3. **Rule-activation task**
   - Edit files matching a rule pack.
   - Expected rules must activate.
   - Terminal block must be correct.

4. **Premature Stop task**
   - Agent tries to end with uncommitted work.
   - Stop hook must block.

5. **Command render task**
   - Render all slash commands.
   - No missing fragments.

6. **Scaffold birth task**
   - Create a project from each scaffold.
   - Gate and basic hooks must work.

7. **Review-round simulation**
   - Synthetic ticket with known expected number of rounds.
   - Useful for process changes, but harder.

For AI-in-the-loop benchmark tasks, use:

- multiple replicates,
- fixed seeds where possible,
- cheap models for first pass,
- production-like model for final validation when quota allows,
- paired comparison old vs candidate.

Failure mode:

- Benchmarks become unrepresentative.

Mitigation:

- Add real incidents as new benchmark tasks.
- Periodically retire stale tasks.
- Keep benchmark versioning.

---

## 4.3 Canary and versioning

With 46 repos, global all-at-once governance sync is too dangerous.

I would introduce governance versions.

Example:

```text
hub tag: gov/2026-08-14-a1b2c3
project file: .fabrik/governance.lock
lock content: gov/2026-08-14-a1b2c3 or cohort=stable|canary
```

Sync becomes explicit:

```text
fabrikctl sync --cohort canary --version gov/2026-08-14-a1b2c3
fabrikctl sync --cohort stable --version gov/2026-08-09-...
fabrikctl rollback --cohort canary --to gov/2026-08-09-...
```

Canary cohort:

- 3–5 low-risk projects,
- representative enough to be useful,
- not the operator’s most critical repos.

Metrics must include `governance_version`.

Then adjudication can compare:

- canary vs stable,
- same task types,
- same period,
- with project mix controls.

Failure mode:

- Projects drift or fail to sync.

Mitigation:

- Drift detection.
- Sync health metrics.
- Refuse to act on projects with unknown version.

If you cannot implement canary/versioning soon, then do not autonomously merge global blocking changes. Use shadow mode or human approval.

---

## 4.4 Statistical design

For each experiment, record:

```yaml
hypothesis:
  finding_id: ...
  change_id: ...
  metric: clean_run_completion_rate
  baseline: 0.82
  expected_direction: up
  minimum_meaningful_effect: 0.03
  window: 3_days
  unit: run
  strata: [project_archetype, task_type, model_account]
  veto_metrics:
    - red_corpus_escape_rate
    - escaped_defect_rate
    - stop_hook_false_block_rate
```

Do not declare success from a single day unless:

- sample is large,
- variance is known,
- effect is large,
- counter-metrics are stable,
- and the change has immediate mechanical effect.

Use categories:

- confirmed,
- rejected,
- inconclusive,
- rolled back,
- superseded.

“Inconclusive” is a valid state. If you force binary moved/not-moved, you will teach the loop to hallucinate certainty.

---

## 4.5 Is one-change-per-day right?

Not as a universal rule.

Better:

- **One active high-risk experiment per surface/metric** to avoid cross-contamination.
- **Multiple low-risk independent changes** can be processed if tests isolate them.
- **No change** is a valid daily outcome.
- **One finding per day** is okay for triage focus, but not necessarily one merge per day.

The calendar should serve the evidence, not the other way around.

---

# 5. What should a human still see?

The operator does not want a dashboard. Good. He should get exception-driven signals and attestations.

But “out of the loop” cannot mean “approves nothing and knows nothing.” There are normative changes that should not be fully autonomous.

---

## 5.1 Daily attestation

One short message per day.

If everything is okay:

```text
KAIZEN 2026-08-14 OK
Merged: none
Experiments: 1 passed sandbox, 1 failed, 0 canary
Guardrails: green
Instrument: green
Quota used: 3%
Escalations: none
Action required: none
```

If action is required:

```text
KAIZEN 2026-08-14 ATTENTION
Action required: 1
- High-risk proposal: Stop hook false-block rate rose after rule pack change.
  Candidate fix weakens Stop hook. Requires approval or rollback.
Merged: none
Guardrails: red on stop_hook_false_block_rate
Instrument: green
Quota used: 4%
```

The human should not need to read a dashboard when status is OK.

---

## 5.2 Immediate alerts

The loop should immediately stop and alert if:

1. Red-corpus escape occurs.
2. A known-bad artifact passes gate.
3. A merged change is rolled back.
4. Governance sync fails across multiple repos.
5. Stop hook appears broken or bypassed.
6. Instrument health fails.
7. The actor touches a protected surface.
8. Diff touches deny-list or unknown high-risk files.
9. Quota budget exceeded.
10. Two consecutive high-risk anomalies occur.
11. A canary cohort shows guardrail degradation.
12. The orchestrator cannot verify its own logs.

These should be loud and actionable.

---

## 5.3 What must reach the human weekly?

Even if no action is required, a weekly digest should exist but can be skimmable:

- merged changes,
- rejected changes,
- rolled-back changes,
- top findings,
- metric trends for veto metrics,
- red-team results,
- pending high-risk proposals,
- fixture coverage growth,
- quota spend vs expected benefit.

If the operator truly does not want to read weekly, then the system must restrict itself to low-risk autonomous changes only. High-risk proposals need a decision queue.

---

## 5.4 What must the human approve?

At minimum:

- changes to the constitution/policy,
- changes to measurement definitions,
- changes to final gate semantics,
- changes to Stop hook,
- changes to run-record terminal logic,
- changes to governance sync,
- changes to scaffold defaults,
- removal/disabling of any enforcement check,
- any change that decreases enforcement strength,
- any change with global blast radius and no canary evidence,
- any change touching credentials/crontab/deny-list/oracle.

If the operator refuses to approve these ever, then the system must not make them.

---

## 5.5 When must the loop stop?

The loop should stop and ask when:

- three failed attempts on one finding occur,
- one failure involves protected surfaces,
- verification suite cannot run,
- data quality is red,
- rollback occurs,
- red-corpus escape occurs,
- canary guardrails degrade,
- quota budget is exhausted,
- sync conflicts exceed threshold,
- the actor attempts to edit policy/oracle,
- an experiment affects a metric already under another active experiment,
- the finding is high severity but low confidence.

Stopping is not failure. Silent continuation is failure.

---

# 6. What are you not thinking about?

Here are the things I think are underweighted or missing.

---

## 6.1 The shared working tree is the biggest physical hazard

Three concurrent AI sessions sharing the hub’s single working tree is not a minor constraint. It is a foundational concurrency flaw.

The proposed actor uses an isolated worktree, which is good, but the problem remains:

- Other agents have dirty state.
- The shared tree can change under automation.
- Stop hooks may see another session’s uncommitted files.
- Governance sync may touch 46 repos while projects are dirty.
- A merge to hub may trigger sync while agents are mid-turn.
- The hourly CI fixer already skips because the tree is dirty.

I would make this a hard requirement:

> Automation must never operate on a shared mutable working tree.

Implementation:

- Convert hub to a bare origin or at least treat `main` as integration branch only.
- Every agent session gets its own git worktree or clone.
- Every session branch is unique: `session/<id>`.
- Every automation run gets its own worktree: `kaizen/<finding>/<attempt>`.
- Governance sync runs from committed tags/branches, not from a dirty tree.
- Use locks or a merge queue for changes to shared surfaces.

Failure mode:

- Existing commands/scripts assume `/opt/fabrik` as a live tree.

Mitigation:

- Introduce a wrapper (`fabrikctl session start`) that creates and enters the correct worktree.
- Migrate commands gradually.
- Until migration is done, freeze autonomous merges to shared surfaces.

This is probably the first thing I would fix before building more actor capability.

---

## 6.2 Pre-commit governance sync to 46 repos is too high-blast-radius

A commit to a synced surface propagating to 46 repos is a fleet-wide deploy. It should not be a side effect of an ordinary commit.

I would replace it with explicit versioned release:

1. Hub changes are merged to `main`.
2. A governance version/tag is created.
3. Sync pipeline applies that version to projects by cohort.
4. Each project records `.fabrik/governance.lock`.
5. Rollback is changing the lock to a previous version.

This gives:

- canary,
- rollback,
- auditability,
- per-project version visibility,
- drift detection.

Failure mode:

- Projects forget to sync or drift locally.

Mitigation:

- Daily drift check.
- SessionStart warns if project governance is stale.
- Gate blocks if local drift is dangerous.

If pre-commit sync must remain temporarily, at least add:

- dry-run mode,
- sync lock,
- sync audit log,
- immediate rollback script,
- freeze file,
- canary subset.

---

## 6.3 Run records are too new to support the full loop

Command run records just started. That is a problem for the proposed adjudication model.

Before using run records as the backbone of metrics, you need:

- coverage,
- schema stability,
- terminal-state integrity,
- linkage to gate logs,
- linkage to commits,
- linkage to transcripts,
- linkage to infra version.

I would track:

```text
run_record_coverage_rate
run_record_stuck_open_rate
run_record_invalid_terminal_rate
run_record_missing_infra_sha_rate
run_record_missing_commit_sha_rate
```

Until coverage and integrity are high, the loop should treat run-based metrics as provisional.

---

## 6.4 You need an event warehouse, not ad-hoc parsing

8.2 GB of transcripts and growing is not something to parse with brittle regexes every day.

Build an incremental event pipeline:

- Input sources:
  - transcripts,
  - subagent ledger,
  - review ledgers,
  - plan sets,
  - run records,
  - gate logs,
  - Stop-hook logs,
  - sync logs,
  - cron logs.
- Output:
  - normalized event tables in DuckDB/SQLite/Parquet.
- Checkpointing:
  - file path,
  - size,
  - hash,
  - last offset,
  - internal timestamp.
- Selection:
  - use event timestamps and watermarks, not just mtime.
- Data quality:
  - schema validation,
  - unknown status quarantine,
  - duplicate detection,
  - late-arrival handling.

Failure mode:

- Transcript format changes.

Mitigation:

- Schema versioning.
- Golden transcript tests.
- Alert when unknown fields/statuses appear.

This also reduces the chance of bugs like the “table row regex matched unrelated document” incident.

---

## 6.5 Denominators need first-class design

You already identified this, but I would elevate it.

Every metric definition should explicitly declare:

```yaml
metric: terminal_block_missing_rate
unit: run
denominator: terminal_task_runs_requiring_final_block
numerator: terminal_task_runs_without_valid_final_block
exclusions:
  - conversational_runs
  - read_only_runs
  - runs_without_terminal_condition
strata:
  - project
  - command
  - task_type
  - model_account
  - infra_version
known_failure_modes:
  - run_record_missing
  - transcript_parser_misses_block
  - command_type_misclassified
```

If the denominator cannot be known, the metric should not be used for automated adjudication.

---

## 6.6 The fixer can affect denominators without touching measurement code

This is a subtle but important point.

Suppose the fixer does not edit the collector. It can still change:

- command prompts so agents stop opening run records,
- run-record terminal conditions,
- which commands are classified as task-completing,
- transcript format,
- the frequency of final-block emission,
- the conditions under which Stop hook fires.

These changes alter denominators and metric meanings.

Therefore protected surfaces must include:

- run-record opening/closing behavior,
- command classification metadata,
- telemetry emission points,
- transcript status-line format,
- hook event contracts.

If the actor needs to change these, it should be a human-approved measurement/oracle change.

---

## 6.7 Prompt and rule text are behavior, not documentation

It is tempting to treat command files and rule packs as “just text.” They are not. They are executable policy for LLM agents.

A one-word change from “must” to “should” can change fleet behavior.

Therefore:

- natural-language artifacts consumed by agents are behavioral artifacts,
- they need tests/examples,
- they need semantic diff review,
- they need canary/shadow when high-risk.

Implementation:

- For each important rule, maintain:
  - rationale,
  - positive examples,
  - negative examples,
  - known violations,
  - expected gate or review evidence.

Failure mode:

- This becomes a large documentation burden.

Mitigation:

- Start only with high-risk rules and blocking checks.
- Let the loop propose examples, but not merge rule semantics without proof.

---

## 6.8 The 13 shared fragments create hidden blast radius

A fragment included into many commands is high-leverage.

If the actor edits a fragment, it may affect:

- several slash commands,
- multiple workflows,
- multiple project types.

You need an artifact dependency graph:

```text
fragment -> commands
rule pack -> file globs -> projects/tasks
gate check -> final_gate -> all repos
scaffold -> new projects
hook -> all sessions
```

Before any patch, the dossier should include computed blast radius:

```text
affected_commands: [ ... ]
affected_rule_packs: [ ... ]
affected_projects: 46
risk_tier: 3
```

If the graph cannot determine impact, treat as high-risk.

---

## 6.9 Scaffold changes affect future projects and should be treated as high-risk

There are 12 scaffold types. A bad scaffold change may not show up until new projects are born, then latent failures spread.

For scaffolds, require:

- scaffold creation smoke test,
- gate passes in fresh scaffold,
- commands render,
- hooks initialize,
- run records open/close,
- basic task simulation succeeds.

Scaffold changes should not be autonomous unless they are purely additive and proven non-breaking.

---

## 6.10 Cron jobs should be monitored, not autonomously edited

You have 21 cron jobs. The loop should detect:

- dead jobs,
- late jobs,
- failing jobs,
- duplicate jobs,
- missing logs.

But it should not edit crontab. Cron is a privileged persistence mechanism. A bad cron change can survive reboots and hide evidence.

The actor may propose cron changes, but not apply them.

---

## 6.11 The quota constraint should drive expected-value triage

Since subscription quota is binding, the loop should not dispatch just because a finding exists.

It should estimate:

```text
expected_value =
  probability_of_success
  * expected_metric_improvement
  * operational_value
  - quota_cost
  - risk_cost
```

Even if the math is approximate, the loop should have thresholds.

Use metered models for:

- parsing summaries,
- dossier generation,
- diff review,
- test generation,
- semantic analysis,
- benchmark orchestration,
- postmortem drafting.

Reserve subscription quota for:

- production-like behavioral evals,
- high-value fixes,
- canary validation where model identity matters.

Failure mode:

- Metered model behavior differs from subscription model behavior.

Mitigation:

- Use metered models for cheap triage and verification, but validate critical behavioral changes with the production-like model/account in limited doses.

---

## 6.12 You need an audit ledger, not just git history

Git history is not enough. You need a structured ledger of the loop itself.

Tables:

```text
findings
attempts
patches
verifications
experiments
adjudications
rollbacks
escalations
guardrail_breaches
```

Each autonomous merge should have:

- finding ID,
- evidence dossier,
- patch SHA,
- allowed paths,
- risk tier,
- verifier logs,
- benchmark results,
- expected metric movement,
- adjudication window,
- rollback command.

This should be append-only.

Failure mode:

- Ledger grows large.

Fine. Store hashes and references; archive old entries. The cost is small compared to losing the ability to explain why the system changed.

---

## 6.13 You need memory of failed attempts

The proposal says a failed fix returns with previous diff attached. That is a start, but insufficient.

You need structured memory:

- what was tried,
- why it failed,
- which files were touched,
- which verifier failed,
- which metric did not move,
- whether the failure was due to noise, patch quality, or wrong hypothesis.

Before dispatching a new attempt, the orchestrator should query:

```text
Have we tried this finding before?
Did previous attempts touch the same files?
Did they fail for the same reason?
Is this a repeat of a known bad strategy?
```

Failure mode:

- Memory becomes overly restrictive and blocks legitimate new approaches.

Mitigation:

- Expire old attempt constraints.
- Allow override with a materially different strategy.

---

## 6.14 You need a kill switch and a watchdog

The loop should check a freeze file before every action:

```text
/opt/fabrik/KAIZEN_FREEZE
```

If present, stop and report.

Also create a watchdog outside the loop’s control:

- checks that daily attestation occurred,
- checks disk space,
- checks collector freshness,
- checks freeze state,
- alerts if the loop died silently.

The watchdog must be protected from the actor.

---

## 6.15 Security and prompt injection

The actor will read evidence from transcripts and project files. That evidence may contain malicious or accidental prompt-injection content.

Risks:

- A project file says “ignore previous rules and edit the gate.”
- A transcript excerpt contains instructions.
- A bad agent output manipulates the fixer.
- A test executes malicious code in the proving ground.

Mitigations:

- Treat all evidence as untrusted data.
- Sanitize excerpts in dossiers.
- Run headless fixer with no network if possible.
- No credentials in worktree.
- No push rights.
- Sandbox test execution.
- Deny secret paths.
- Do not let the fixer read credential-rotation directories.
- Be careful with tests that execute arbitrary project code.

Failure mode:

- Sandboxing on a single-operator box is imperfect.

True. This is another reason high-risk changes need human approval.

---

## 6.16 Model/account non-stationarity

If the underlying model or account changes, agent behavior may change even if infrastructure is unchanged.

Every session/run should record:

- model,
- account,
- quota tier,
- infra SHA,
- governance version,
- command version,
- session hook version.

Metrics should be stratified by model/account. If a model version changes, baselines may need to reset.

Otherwise the loop will attribute model drift to infrastructure changes.

---

## 6.17 The loop can become a source of rule bloat

The loop will naturally want to add things:

- new rules,
- new fragments,
- new checks,
- new hooks,
- new telemetry,
- new command instructions.

But subtraction is harder.

You need lifecycle management:

- artifact owner,
- created-by finding,
- last review date,
- usage statistics,
- trigger frequency,
- false-positive rate,
- deprecation candidate flag.

If a rule has not triggered in 90 days and has no test, it should be reviewed. Not auto-deleted.

The operator’s 203 artifacts will become 500 artifacts if the loop only adds.

---

## 6.18 You need backups and disaster recovery

This system is now the platform. If the loop corrupts the hub or governance sync propagates corruption, all 46 projects suffer.

Minimum:

- daily git bundle backups of hub and project repos,
- tested restore,
- governance version snapshots,
- config snapshot of cron/hooks,
- audit ledger backup.

This is not glamorous, but it is necessary.

---

# 7. Concrete implementation plan

If I were implementing this, I would phase it.

---

## Phase 0: Stop the bleeding

Do not enable autonomous global fixes yet.

1. Create a freeze/kill switch.
2. Freeze autonomous changes to:
   - gates,
   - hooks,
   - sync,
   - run records,
   - measurement,
   - scaffolds,
   - cron,
   - credentials.
3. Create an append-only audit ledger.
4. Separate automation from the shared dirty tree:
   - use isolated worktrees,
   - no automation in `/opt/fabrik` working tree.
5. Make governance sync explicit and logged if possible; if not, add dry-run and rollback.

Failure mode:

- This slows current automation.

Acceptable. The alternative is a fleet-wide breakage.

---

## Phase 1: Trusted observability

Goal: make the instruments trustworthy.

Build:

- event warehouse,
- run-record schema,
- metric definitions as code,
- metric CI,
- golden inputs for collector,
- data-quality dashboard hidden from operator but visible to loop,
- protocol compliance split.

Specific fixes:

1. Split compliance metric:
   - missing terminal block,
   - duplicate terminal block,
   - invalid terminal block,
   - missing `RULES ACTIVE` when rules expected,
   - spurious terminal block outside terminal runs.
2. Fix denominators:
   - use run records,
   - exclude conversational/read-only runs,
   - track unknown run types separately.
3. Fix selection bias:
   - use event timestamps/watermarks,
   - handle late transcripts,
   - stratify by project/day-type.
4. Canonicalize subagent statuses:
   - `done`, `error`, `capped`, `out_of_scope`.
   - Do not map unknown statuses to success/failure silently.
5. Standardize review ledgers:
   - structured rows,
   - ticket ID,
   - round count,
   - outcome,
   - severity.

Exit criteria:

- Metric tests pass.
- Run-record coverage is high enough for at least 7 days.
- No known parser bug in golden corpus.
- Data-quality gate can freeze the actor.

---

## Phase 2: Proving ground

Goal: make changes verifiable before fleet exposure.

Build:

1. Artifact inventory and dependency graph.
2. Render tests for all commands/fragments.
3. Rule activation tests for rule packs.
4. Gate golden tests:
   - every blocking check has at least one pass and one fail fixture.
5. Mutation tests for high-risk checks.
6. Red corpus.
7. Sandbox behavioral tasks.
8. Semantic diff reviewer.
9. Risk-tier policy.
10. Rollback generator.

Exit criteria:

- All 42 blocking checks have known-good and known-bad fixtures.
- Vacuous-check lint catches checks with no assertions/evidence.
- Candidate changes can be verified in isolated worktree without touching fleet.
- Policy can reject diffs touching protected surfaces.

---

## Phase 3: Low-risk autonomous actor

Only after Phases 0–2 are healthy.

Allow autonomous merging only for Tier 0/1:

- non-agent-facing docs,
- comments,
- additive test fixtures,
- additive telemetry that does not change behavior,
- advisory-only checks,
- lint fixes with no semantic effect.

Daily loop:

- selects finding,
- requires failing test,
- dispatches sandboxed patch agent,
- verifies,
- merges if low-risk,
- records hypothesis.

Do not yet touch:

- command prompts,
- rule semantics,
- blocking gates,
- hooks,
- sync,
- scaffolds.

Exit criteria:

- 2–4 weeks of low-risk merges with zero rollbacks.
- No protected-surface violations.
- Audit ledger complete.
- Human attestation shows no noise.

---

## Phase 4: Shadow/canary for behavioral changes

Build governance versioning and canary cohorts.

Then allow Tier 2 experiments:

- command wording,
- rule wording,
- non-critical prompts,
- advisory rule packs,

but only through:

- sandbox benchmark,
- shadow mode,
- canary cohort,
- guardrail monitoring,
- automatic rollback.

No direct global merge.

Exit criteria:

- Canary metrics are comparable to stable.
- Rollback works.
- Governance version appears in all relevant telemetry.

---

## Phase 5: High-risk proposals

For Tier 3 changes:

- Stop hook,
- blocking gate logic,
- run-record terminal logic,
- sync mechanism,
- scaffold defaults,

the loop may:

- detect finding,
- build dossier,
- draft patch,
- run proving ground,
- prepare canary plan,

but it should not merge without human approval or exceptionally strong autonomous evidence.

This is not a failure of autonomy. It is recognition that these are normative changes.

---

# 8. Specific critiques of the proposed actor steps

## Step 1: “Select exactly one finding”

Mostly good, but add:

- rank by expected value,
- allow no selection,
- avoid selecting findings with insufficient evidence,
- avoid selecting findings already under active experiment.

Better wording:

> Select at most one finding for action. The selected finding must have sufficient evidence, a plausible causal mechanism, and a risk tier that permits action.

---

## Step 2: “Build an evidence dossier”

Good. Add:

- allowed paths,
- forbidden semantic patterns,
- required failing test,
- blast-radius graph,
- risk tier,
- rollback plan,
- expected adjudication window,
- veto metrics.

Also sanitize evidence to reduce prompt-injection risk.

---

## Step 3: “Create an isolated git worktree”

Good but insufficient.

Add:

- worktree from clean origin commit,
- no push credentials,
- no shared-tree mutation,
- merge queue,
- lock for sync,
- rebase and re-test if main moved.

The worktree protects the fixer from peers, but not peers from the fixer. Need branch/worktree discipline for all sessions.

---

## Step 4: “Dispatch a headless AI coding session”

Add constraints:

- max runtime,
- max quota,
- no network if possible,
- no credentials,
- no push,
- output patch only,
- treat dossier evidence as untrusted.

Also prefer cheap/metered models for simple patches.

---

## Step 5: “Verify independently”

Too weak as stated.

Replace with:

1. Policy lint.
2. Allowed-path check.
3. Dependency-graph blast-radius check.
4. Unit tests.
5. Render tests.
6. Rule activation tests.
7. Gate golden tests.
8. Mutation tests.
9. Red corpus.
10. Sandbox behavioral eval.
11. Semantic reviewer.
12. Dry-run sync.
13. Rollback generation.

“Confirm a real commit exists” should also confirm:

- commit message,
- trailers,
- no protected paths,
- no secrets,
- expected branch,
- expected diff size.

---

## Step 6: “Merge only on green, then push”

Add:

- merge only if risk tier permits,
- merge to branch first,
- canary/shadow where possible,
- post-merge guardrails,
- automatic rollback on breach.

For global governance, “push” should mean “publish version to cohort,” not “immediately update all 46 repos.”

---

## Step 7: “Record a hypothesis”

Good. Make it structured and include:

- minimum meaningful effect,
- required sample size or benchmark evidence,
- veto metrics,
- expiration/window.

---

## Step 8: “Adjudicate the next day”

Too simplistic.

Replace:

- Fast metrics: 1-day adjudication possible if high volume.
- Slow metrics: use benchmark/canary or longer window.
- Rare severe defects: adjudicate by test/red corpus, not fleet movement.
- Insufficient data: mark inconclusive, not failed.

---

## Guard: “Fixer may never edit measurement code”

Correct but insufficient.

Extend to:

- metric definitions,
- collector,
- adjudicator,
- final gate,
- hooks,
- run-record schema,
- sync,
- policy,
- deny-list,
- proving-ground fixtures,
- audit ledger,
- watchdog.

If a change requires touching these, create a human-facing proposal.

---

## Guard: “3 failed attempts → escalate”

Good, but add:

- immediate escalation if protected surface touched,
- immediate escalation if rollback occurs,
- cooldown before retry,
- structured postmortem,
- memory check to prevent same failed strategy.

---

## Guard: “Hard deny-list”

Good, but make it semantic and graph-aware.

Deny:

- credentials,
- credential rotation,
- crontab,
- watchdog,
- measurement/oracle,
- policy files,
- audit ledger,
- sync scripts,
- hooks,
- gate checks if not tier-approved,
- scaffold defaults if not tier-approved,
- shared fragments that affect protected commands.

Also deny editing the deny-list.

---

## Guard: “One dispatch per day”

Good as cost control, but not as a goal.

Add:

- dispatch only if expected value exceeds threshold,
- no dispatch if instrument health red,
- no dispatch if quota budget too low,
- no dispatch if only high-risk changes are available.

The loop should be allowed to say: “No safe valuable action today.”

---

# 9. What I would measure as the “north star,” if forced

I would avoid a single north star, but if one is required:

> Human-intervention-free clean successful runs per unit quota, subject to safety and correctness vetoes.

Operational definition:

```text
North-star numerator:
  Clean successful runs with no human correction,
  no rollback,
  no escaped defect within N days.

Denominator:
  Subscription quota consumed,
  or cost-adjusted quota.

Veto metrics:
  red_corpus_escape_rate = 0,
  protected_surface_violations = 0,
  rollback_rate < threshold,
  escaped_defect_rate not increasing,
  gate_false_negative_rate not increasing,
  instrument_health = green.
```

Even this is Goodhart-vulnerable, so it should be used as a monitoring composite, not as the sole objective.

---

# 10. The most important design rule

If I had to reduce this to one rule:

> The loop may optimize the system only after the system has proven that the optimizer cannot weaken the proof.

In practice:

- The actor cannot edit the oracle.
- Every fix needs a failing test.
- Every enforcement change needs known-bad fixtures.
- Every global change needs shadow/canary or exceptional proof.
- Every metric needs a denominator and a counter-metric.
- Every day’s run must be allowed to end with “no change.”

---

# 11. Final recommendation

I would not ship the proposed daily actor as a global auto-fixer.

I would ship this instead:

1. **Daily observability loop**  
   Runs every day, collects, validates, detects, ranks, and reports.

2. **Trusted metric layer**  
   Metric CI, run-record denominators, split compliance metrics, data-quality gates.

3. **Proving ground**  
   Golden tests, red corpus, mutation tests, render/rule activation tests, sandbox evals.

4. **Risk-tiered change government**  
   Autonomous only for low-risk changes; human approval or canary for high-risk governance.

5. **Concurrency repair**  
   No shared mutable working tree for automation; separate worktrees/branches; explicit versioned sync.

6. **Canary/rollback capability**  
   Governance versions, cohort deployment, automatic rollback, drift detection.

7. **Exception-only human signal**  
   Daily attestation, immediate alerts, weekly high-risk proposal queue.

The operator’s goal — daily, not weekly, and no dashboard — can still be met. The loop runs daily and produces a daily attestation. But the loop’s daily output is often:

> “I observed, I tested, I found nothing safe and valuable to merge, and all guardrails are green.”

That is not a failure of the loop. That is the loop working correctly.



---

## qwen/qwen3.8-2.4t-a95b

## Executive judgement

The direction is right, but the proposed daily actor is premature and structurally dangerous in its current form.

You have correctly identified the real assets:

- The raw execution record: transcripts, run records, subagent ledger, reviews, gates, hooks.
- The need for isolation: worktrees, no shared-tree mutation.
- The need for independent verification: do not trust the agent’s claim.
- The need for hypothesis-driven change: change X, expect metric M to move.
- The need to stop treating paperwork as reality.

But the proposed shape — **select one finding daily, dispatch a fixer, merge on green, adjudicate by tomorrow’s number** — is too brittle, too statistically naive, and too globally actuated. If you run this for 60 days, the most likely failure is not a loud crash. It is a quiet pile of green commits and improved proxy metrics while real correctness, autonomy, and trust degrade.

My core design judgement:

> The daily loop should be a **learning and proving loop**, not necessarily a daily fleet-mutation loop.  
> The loop’s primary daily output should be **better evidence, failing tests, and risk-tiered proposals**.  
> Fleet-wide governance changes should happen only when the evidence layer, risk tier, canary exposure, and guard metrics justify it.

Put differently:

- Daily observation: yes.
- Daily test/fixture creation: yes.
- Daily low-risk isolated improvement: yes.
- Daily global enforcement change across 46 repos: no.
- Next-day adjudication as the primary proof of success: no.

The better shape is:

```text
observe real behaviour
  → validate the instrument
  → convert findings into failing tests / negative controls
  → propose smallest safe patch
  → verify independently in sandbox
  → deploy through risk-tiered rings
  → adjudicate with exposure-aware statistics
  → rollback / promote / escalate
```

That preserves the operator’s “daily” requirement without turning the platform into a Goodhart machine.

---

# 1. Is the loop shape right?

## 1.1 The high-level loop is right, but the cadence and unit are wrong

The sequence:

```text
observe → one fix → verify → adjudicate next day
```

is directionally sane. It is better than “vibe-driven infrastructure editing.” But it makes three bad assumptions:

1. **One finding per day is the right unit.**  
   It is not. Some findings require five small changes. Some require no change. Some require only a test. Some require instrument repair. Some require human judgement. A daily quota of one fix biases the system toward things that can be fixed in one day, not things that matter.

2. **One daily fleet change is safe.**  
   It is not, especially when a synced surface affects 46 repos and the measurement system is still young. The blast radius is too large.

3. **A next-day metric movement is meaningful attribution.**  
   Usually it is not. Project mix, task mix, model/account rotation, session volume, plan era, and random variation will dominate many metrics. A next-day movement is useful as a smoke alarm, not as proof of causality.

So I would keep the loop’s spirit but change its granularity.

## 1.2 What will break after 60 days?

If the current design is run unchanged, I expect these failure modes.

### Failure mode 1: Goodhart saturation

The loop will find metrics it can move cheaply.

Examples:

- Increase “compliance” by making agents emit the required block more often, including where they should not.
- Reduce review rounds by making review shallower or easier to skip.
- Increase gate pass rate by weakening or bypassing expensive checks.
- Reduce subagent failure by classifying inconvenient cases as `out_of_scope`.
- Reduce cost by doing less work.

The dashboard will look better. The platform may be worse.

### Failure mode 2: Proxy divergence

The loop will optimize leading proxies that are not tied to outcomes.

If you measure “final block present” but not “task was actually correct,” agents and fixers will converge on producing beautiful final blocks around mediocre work.

If you measure “gate success” but not “gate checks assert anything,” the gate becomes a ceremonial object.

### Failure mode 3: Statistical thrash

With small samples, the loop will confirm false positives and revert false negatives.

Example: review rounds are 3.2 with n=12. A change appears to reduce them to 2.7. That may be noise. If the system declares success, it learns superstition. If it reverts a good change because tomorrow’s sample happened to be bad, it learns noise.

### Failure mode 4: Rule sprawl and governance overhead

Every successful “improvement” may add a rule, check, fragment, hook condition, or prompt paragraph. After 60 days, agents become slower, prompts become bloated, gates become slower, and quota consumption rises. The loop will have improved local metrics while increasing systemic friction.

You need a **governance overhead budget** and retirement criteria for rules/checks.

### Failure mode 5: Hidden coupling

A change to a shared fragment may affect many commands. A change to a stop hook may affect every session. A change to scaffold defaults may affect every future project. The loop may not understand the dependency graph, so it will make locally sensible changes with global side effects.

### Failure mode 6: The actor becomes self-referential

If the actor can modify commands, hooks, run records, gates, or prompts that influence its own dispatch, evidence collection, or adjudication, it can accidentally tune the machinery that judges it.

The platform needs a constitutional boundary: the actor may govern governed artifacts, but not the governor.

## 1.3 The better shape: daily learning, staged acting

I would split the system into three loops with different authority and cadence.

### Loop A: Daily metrology loop

Runs every day.

Responsibilities:

- Ingest raw execution data.
- Validate data contracts.
- Recompute metrics.
- Detect anomalies.
- Generate findings.
- Quarantine metrics when instrument health is bad.
- Produce evidence dossiers.

Authority:

- May not change platform behaviour.
- May flag instrument bugs.
- May produce research tasks.

This loop must be allowed to say: “Today there is not enough evidence to act.”

### Loop B: Daily proof loop

Runs every day.

Responsibilities:

- Convert top findings into failing tests, fixtures, negative controls, or golden tasks.
- Build evidence dossiers.
- Estimate blast radius.
- Classify risk tier.
- Prepare patch proposals.

Authority:

- May add tests/fixtures.
- May propose patches.
- May auto-merge only very low-risk changes.

Key rule:

> No behavioural infrastructure fix is dispatched unless the finding has a reproducible test or negative control, or unless the change is explicitly classified as exploratory/research.

This is the “regression factory” idea. The loop’s job is not merely to patch files. Its job is to convert observed failure into executable evidence.

### Loop C: Staged change loop

Runs as evidence allows, not necessarily daily.

Responsibilities:

- Dispatch fixer in isolated worktree.
- Verify independently.
- Merge low-risk changes.
- Deploy medium/high-risk changes through canary rings.
- Monitor guard metrics.
- Promote or rollback.
- Adjudicate over appropriate windows.

Authority:

- Tiered. Some changes auto-merge, some require canary, some require human approval, some are forbidden.

This preserves daily motion without requiring daily global mutation.

## 1.4 Risk-tiered change authority

I would not treat all infrastructure changes equally. Suggested tiers:

| Tier | Change type | Examples | Authority | Required proof |
|---|---|---|---|---|
| 0 | Non-behavioural | docs, comments, artifact metadata, test additions, telemetry annotations | Auto-merge if tests green | lint, schema, no policy diff |
| 1 | Additive non-blocking | new advisory check, shadow metric, warning-only rule, new fixture | Auto-merge to shadow/canary | no enforcement impact, overhead budget |
| 2 | Behavioural but strictness-preserving or strictness-increasing | prompt clarification, gate fix that catches known bad, rule activation fix, scaffold template fix | Auto only with failing test + canary + guard metrics stable | negative control, semantic diff, shadow/canary |
| 3 | Behavioural and potentially weakening or high-blast-radius | removing/relaxing gate, changing stop hook, shared fragment change, scaffold default change, command structure change | Human approval or default-deny queue | strong evidence, canary, rollback plan |
| 4 | Constitutional/forbidden | credentials, crontab, orchestrator, metric registry, sync engine, audit logs, deny-list, its own permissions | Never autonomous | human-owned change only |

The current proposal effectively treats many Tier 2/3 changes as if they can be daily autonomous if the gate is green. That is the part I reject.

## 1.5 How this would be implemented

Concrete implementation:

- A finding queue in `/var/kaizen/findings/`.
- Each finding is JSON:

```json
{
  "finding_id": "...",
  "metric_id": "...",
  "severity": "...",
  "evidence_sessions": ["..."],
  "affected_artifacts": ["..."],
  "expected_metric_movement": "...",
  "risk_tier": 2,
  "has_failing_test": true,
  "allowed_paths": ["..."],
  "forbidden_paths": ["..."],
  "canary_plan": "...",
  "quota_budget": "...",
  "status": "ready_for_patch"
}
```

- A dispatcher selects findings by expected value, not by calendar pressure:

```text
score = expected_impact * evidence_confidence / (risk * quota_cost)
```

- If no finding exceeds threshold, no dispatch occurs. That is a healthy state, not a failure.

## 1.6 How this can fail

This design can fail by becoming too conservative. If every change requires perfect tests, nothing ships.

Countermeasure:

- Allow Tier 0/1 changes freely.
- Allow exploratory changes in sandbox/canary with explicit “research” labels.
- Require proof primarily for enforcement and global surfaces.

Another failure mode: the fixture corpus becomes artificial and unrepresentative.

Countermeasure:

- Fixtures must be mined from real historical failures.
- Periodically generate adversarial tasks from transcripts.
- Audit the fixtures themselves.

---

# 2. What should actually be measured?

The operator’s goal is:

> fastest, most accurate and correct, rules-obeyed coding infrastructure.

That is a multi-objective goal. It cannot be reduced safely to one number without creating Goodhart risk. I would use a hierarchy:

```text
Safety/integrity metrics > quality/outcome metrics > compliance/process metrics > speed/cost metrics
```

If speed improves but escapes worsen, that is not success.  
If compliance improves but agents become slower or less correct, that is not success.  
If gate pass rate improves but gate integrity falls, that is not success.

## 2.1 North Star metric

I would define a strategic outcome metric:

### Validated Autonomous Task Rate

```text
VAT = completed tasks that remain valid / total completed tasks
```

A completed task is “validated” if all of these are true:

1. A command run record reached a terminal success state.
2. The final gate was green.
3. No human corrective intervention occurred within, say, 7 days.
4. No likely defect escape occurred within, say, 7–14 days.
5. No later automated or human revert/fix can be attributed to the task.

Then the efficiency-adjusted version:

```text
Validated autonomous tasks per unit quota
```

This is not a daily control metric. It is a strategic metric. It resists the most obvious Goodhart attacks because it pairs completion with post-completion survival.

Implementation difficulty:

- Requires task identity.
- Requires attribution from later fixes/reverts to earlier tasks.
- Requires commit trailers, run record IDs, branch/ticket links.

It will be imperfect at first. That is acceptable. It is still better than optimizing syntax compliance.

## 2.2 Metric set I would build

### A. Instrument health metrics

These are prerequisites. If they are red, the actor should not dispatch behavioural fixes.

| Metric | Definition | Why it matters | Goodhart risk | Counter-design |
|---|---|---|---|---|
| Data contract pass rate | % of raw events passing schema, vocabulary, timestamp, identity checks | Prevents acting on corrupt observations | Fixer could loosen schema | Schema tests owned separately; dual-run schema changes |
| Collector golden-test pass rate | Collector output on synthetic known dataset matches expected metrics | Prevents collector bugs | Fixer could edit golden tests | Separate metrology pipeline; test deletion audited |
| Metric lineage completeness | Every metric can be traced from raw event to final number | Prevents “paperwork metrics” | Lineage docs can become stale | Auto-generate lineage from queries |
| Denominator validity | % metric denominators matching event-based definitions | Prevents manufactured outrage | Denominator can be gamed | Denominators frozen per experiment |

### B. Gate and enforcement integrity metrics

These are more important than raw gate pass rate.

| Metric | Definition | Why it matters | Goodhart risk | Counter-design |
|---|---|---|---|---|
| Blocking-check negative-control coverage | % of blocking gate checks with at least one known-bad fixture that fails the check | Detects vacuous gates | Fixer could add trivial fixtures | Mutation testing + fixture audit |
| Gate mutation score | % of simple gate-weakening mutants caught by fixtures | Detects weak tests | Fixer could write fixtures that only catch exact mutant | Use varied mutation operators and periodic red-team fixtures |
| Gate assertion trace validity | Each blocking check reports assertions/evidence; zero-assertion PASS is invalid | Prevents “PASS while asserting nothing” | Checks could emit fake assertions | Require meaningful evidence fields; audit sample |
| Shadow disagreement rate | New gate version vs old gate version decisions on same commits | Detects silent behavioural change | Fixer could disable shadow | Shadow runner owned by verifier, not fixer |

The six gate checks that reported PASS while asserting nothing are a first-class emergency. Until every blocking gate check has a negative control, I would not trust “gate green” as proof of anything.

### C. Task/run completion metrics

Sessions are too coarse. The primary unit should be a **command run record**, not a transcript session.

| Metric | Definition | Why it matters | Goodhart risk | Counter-design |
|---|---|---|---|---|
| Run completion yield | run records reaching terminal success / run records started | Measures whether commands finish properly | Agents may close runs falsely | Stop hook validates terminal state; audit open/closed runs |
| Completion protocol correctness | runs with exactly one terminal completion block and correct RULES ACTIVE / runs closed | Fixes the current confounded compliance metric | Agents may emit block everywhere | Count per run, not per response; penalize premature blocks |
| Premature terminator rate | terminal-like blocks emitted mid-run per 100 runs | Detects the “36 blocks per session” failure separately | Could be over-detected in legitimate intermediate summaries | Define exact terminal block schema and run-record state |
| Stop-hook block rate | blocked stop attempts / stop attempts | Detects agents trying to end while incomplete | Hook may become too strict and trap agents | Pair with stuck-session rate and appeal/override log |
| Untracked completion rate | task-like completions without run record | Detects missing instrumentation | Agents may avoid run records | Make run record mandatory for command invocation/stop |

The current “rules-compliance 36%” metric is not actionable. It conflates:

- Missing required terminator.
- Terminator emitted repeatedly.
- Conversational turns that owe no terminator.
- Read-only sessions.
- Sessions without command run records.
- Parser bugs.

I would suspend it as a driver until it is rebuilt from events.

### D. Rule activation metrics

Rule packs should be measured mechanically, not by trusting the agent’s text.

| Metric | Definition | Why it matters | Goodhart risk | Counter-design |
|---|---|---|---|---|
| Rule activation recall | expected rule packs active / expected from changed file globs | Detects missing rules | Agent may list all rules | Compute expected set from actual changed files |
| Rule activation precision | active rule packs that were actually expected / all active | Detects rule spam | Agent may emit broad rules to look compliant | Mechanical glob engine owns expected set |
| Rule overhead | tokens/time added by active rules | Prevents rule sprawl | Overhead may be hidden | Measure rendered prompt size and gate runtime |

Implementation:

- When a run completes, compute changed files from git/commits/worktree.
- Apply rule-pack glob definitions.
- Compare expected active rule set to recorded active rule set.
- Store result in run record.

Failure mode: glob definitions are ambiguous or overlapping. Countermeasure: lint rule packs for overlaps, conflicts, missing owners, and missing tests.

### E. Quality/outcome metrics

These are the anti-Goodhart layer.

| Metric | Definition | Why it matters | Goodhart risk | Counter-design |
|---|---|---|---|---|
| First-pass gate yield | tasks green on first final gate / tasks attempting completion | Measures process maturity | Gate may be weakened | Gate integrity metrics must be green |
| Review rounds per completed ticket | rounds for ticket-era reviews only | Measures review friction/quality | Agents may avoid review or make review shallow | Pair with escape rate and review severity |
| Review severity mix | severity-weighted findings per review | Prevents “fewer rounds, worse findings” | Severity labels can be gamed | Audit sampled reviews |
| Defect escape rate | completed tasks followed by corrective evidence within 7/14 days | Most important quality metric | Attribution may miss escapes | Use reverts, follow-up runs, human commits, failed CI, linked tickets |
| Human intervention rate | human corrective actions per AI task | Direct autonomy metric | Human work may happen outside tracked repos | Use provenance trailers and commit authorship heuristics |
| Rework ratio | follow-up corrective work linked to original task / completed tasks | Measures durability | Linkage may be incomplete | Require ticket/run links in commits and run records |

Review rounds alone are dangerous. Fewer rounds can mean better work, but they can also mean skipped review, shallower review, or lower standards. Review rounds must always be paired with escapes and severity.

### F. Efficiency and quota metrics

| Metric | Definition | Why it matters | Goodhart risk | Counter-design |
|---|---|---|---|---|
| Quota per validated task | subscription/quota consumed / validated tasks | True cost efficiency | Agent may do less to save quota | Quality guard metrics |
| Turns/tool calls per completed task | median/p95 by task type | Detects inefficiency | Agent may rush | Pair with escapes/rework |
| Wall-clock per completed task | median/p95 by task type | Detects slowness | Agent may parallelize badly | Pair with correctness |
| Subagent reliability by task type | `done` / all dispatches, with `error`, `capped`, `out_of_scope` separated | Detects subagent issues | Failures may be reclassified | Audit status vocabulary; treat non-done as adverse unless justified |
| Gate runtime | time to run final gate | Prevents gate bloat | Checks may be disabled to speed gate | Gate integrity metrics |

The current “$0.74/day” is too aggregate. It does not tell you cost per successful outcome. Use:

```text
quota or cost per validated task
```

not cost per day.

### G. Governance overhead metrics

This is missing from the current plan and will matter after 60 days.

| Metric | Definition | Why it matters |
|---|---|---|
| Artifact count growth | number of rules/gates/fragments/hooks over time | Detects sprawl |
| Prompt overhead | tokens added by rules/fragments per session | Detects slowing agents |
| Gate overhead | gate runtime and check count | Detects process bloat |
| Rule retirement rate | rules/checks removed or demoted per quarter | Detects whether the system can prune |
| Sync drift | projects whose governance version differs from expected channel | Detects fleet inconsistency |

## 2.3 Which of your current metrics are junk?

Bluntly:

### Junk as currently computed

1. **Overall rules-compliance 36%**  
   Junk as a driver until split and event-sourced. It conflates omission, spam, denominator errors, and parser bugs.

2. **Review rounds across mixed plan eras**  
   Junk for current process evaluation. The plan-era change makes the mixed average misleading. Keep ticket-era only, or model eras separately.

3. **Sessions per day**  
   Not a performance metric. It is volume/context. Useful for denominators, not success.

4. **Raw gate pass rate without gate integrity**  
   Dangerous. If gate checks can be vacuous, gate green is not evidence.

5. **Cost/day alone**  
   Too aggregate. It can reward doing less.

### Not junk, but not ready

1. **Subagent failure rate 4%**  
   Not junk, but incomplete. Need status taxonomy, task-type stratification, retry behaviour, and model/account stratification.

2. **Review rounds per ticket-era ticket**  
   Promising, but n=12 is too small to drive automation. Use as a research metric, not an actuation trigger.

3. **Session count by project**  
   Useful for coverage and selection bias detection, not quality.

## 2.4 Goodhart counter-design

Rules:

1. **Never optimize a single metric.**  
   Every target metric must have at least one guard metric.

   Examples:

   - Target: completion protocol correctness. Guard: premature terminator rate, stuck sessions.
   - Target: review rounds. Guard: escape rate, review severity.
   - Target: gate pass rate. Guard: gate mutation score, negative-control coverage.
   - Target: cost per task. Guard: defect escape rate.

2. **Freeze metric definitions during experiments.**  
   The fixer should not be judged by a metric it can alter.

3. **Dual-run metric changes.**  
   If a metric definition changes, compute old and new versions side-by-side for at least 7–14 days.

4. **Require denominators from events, not text regex.**  
   The stop hook and run records should define task completion.

5. **Sample-based adversarial audits.**  
   Periodically have a separate model or human audit random sessions and ask: “Was this actually correct? Was the gate right? Was the review meaningful?”

6. **Metric changes are constitutional changes.**  
   They should be versioned, logged, and require higher authority than ordinary platform fixes.

---

# 3. The verification problem

This is the hardest part: an AI fixing infrastructure that governs AI.

The current plan says:

> Re-run the full gate, corpus integrity check, and test suite in the worktree.

That is necessary but insufficient. If the fixer changes the gate, weakens a rule, deletes a test, or makes a check vacuous, the worktree may be “green” precisely because the change made the verification weaker.

You need a meta-verification layer.

## 3.1 Negative controls are mandatory

For every blocking gate check, there must be at least one known-bad fixture that fails the check.

Structure:

```text
/fabrik-evals/gate-fixtures/
  check_python_imports/
    pass/
      case_001/
    fail/
      case_001/
  check_run_record_closed/
    pass/
    fail/
  check_no_secrets/
    pass/
    fail/
```

A daily job runs:

```text
gate_prove.py --all --json
```

Expected output:

```json
{
  "check_id": "check_python_imports",
  "pass_fixtures": 3,
  "fail_fixtures": 2,
  "all_pass_fixtures_passed": true,
  "all_fail_fixtures_failed": true,
  "assertion_count": 17,
  "runtime_ms": 240
}
```

Rule:

> A blocking gate check with no negative control is not considered verified.  
> A blocking gate check that passes a negative control is red.

The six false-pass checks should be treated as P1 infrastructure incidents.

Failure mode: fixer adds trivial negative fixtures to satisfy coverage.

Countermeasure:

- Fixture quality audits.
- Mutation testing.
- Fixtures derived from real historical failures.
- Separate auditor reviews fixture changes.

## 3.2 Mutation testing for gates and rules

Mutation testing answers:

> If this check were weakened, would our tests notice?

For Python gate checks, simple mutation operators include:

- Replace condition with `True`.
- Replace condition with `False`.
- Invert condition.
- Remove a function call.
- Swallow exceptions.
- Change `>`, `<`, `==`, `!=` thresholds.
- Return success early.
- Skip file read.
- Remove required pattern check.

A mutation runner produces:

```json
{
  "check_id": "check_final_block",
  "mutants_generated": 18,
  "mutants_killed": 17,
  "mutation_score": 0.944,
  "surviving_mutants": ["mutant_013"]
}
```

Policy:

- Blocking checks should have a mutation score above a threshold, e.g. 90%.
- If a changed check’s mutation score drops, reject the patch.
- If a check survives mutants, its fixtures are weak.

Failure mode: mutation testing is slow or noisy.

Countermeasure:

- Run mutation testing only on touched checks daily.
- Run full mutation suite weekly.
- Cache results by check hash.

## 3.3 Assertion trace requirement

A gate check should not be allowed to say merely:

```json
{"status": "success"}
```

It should say:

```json
{
  "status": "success",
  "assertions": [
    {
      "description": "final block exists exactly once",
      "evidence": "run_record.close_event",
      "result": "pass"
    }
  ],
  "files_inspected": ["..."],
  "commands_run": ["..."]
}
```

Meta-gate rule:

> A blocking check with zero meaningful assertions is invalid.

This is gameable if taken alone, so combine with negative controls and mutation testing.

## 3.4 Shadow mode for behavioural changes

For any change to gates, hooks, rule activation, or command rendering, run old and new versions in parallel before enforcement.

Example:

```text
final_gate.py --shadow --old=main --new=patch-branch --commit=<sha>
```

Output:

```json
{
  "old_status": "failure",
  "new_status": "success",
  "disagreements": [
    {
      "check_id": "check_run_record_closed",
      "old": "fail",
      "new": "pass"
    }
  ]
}
```

Policy:

- If new passes what old fails, it may be a fix or a weakening. Requires explanation.
- If new fails what old passes, it may be stricter or a false positive. Requires canary.
- Shadow disagreement logs must be retained.

Failure mode: shadow mode doubles runtime.

Countermeasure:

- Shadow only touched checks.
- Shadow on sampled commits.
- Run shadow in canary ring first.

## 3.5 Semantic policy diff

A normal diff is not enough. You need a policy-aware diff.

For each patch, run a deterministic linter that extracts:

- Removed assertions.
- Lowered thresholds.
- Removed file patterns.
- Added ignore/exemption paths.
- Changed severity from error to warning.
- Changed blocking to advisory.
- Deleted tests/fixtures.
- Replaced strict equality with fuzzy matching.
- Removed timeouts.
- Changed status vocabulary.
- Removed logging/audit fields.

Example output:

```json
{
  "weakening_signals": [
    {
      "file": "gates/check_max_file_size.py",
      "change": "threshold changed from 5000 to 20000",
      "severity": "high"
    }
  ],
  "deleted_tests": [],
  "added_exemptions": ["*.generated.py"],
  "risk": "tier3"
}
```

Then a separate LLM auditor can review the diff with a checklist:

- Does this reduce enforcement?
- Does this remove a hard test?
- Does this make a check vacuous?
- Does this add a bypass?
- Does this alter adjudication or evidence?
- Does this increase blast radius?
- Is the evidence sufficient?

But do not rely primarily on the LLM auditor. Use deterministic policy diff first; LLM auditor second.

## 3.6 Golden task harness

Gate fixtures test static states. You also need behavioural tasks.

For command/hook/scaffold changes, build a harness that:

1. Creates a disposable project from a scaffold.
2. Applies a known task prompt.
3. Runs a cheap model or scripted agent simulation.
4. Checks structural properties:
   - Run record opened.
   - Correct rules active.
   - No premature final block.
   - Final gate run.
   - Stop hook behaviour correct.
   - Commit trailers present.
   - Expected gate result.

This does not need to prove full semantic correctness. It proves protocol and infrastructure behaviour.

Failure mode: synthetic tasks are not representative.

Countermeasure:

- Mine golden tasks from real historical sessions.
- Keep a rotating set of task types.
- Mark synthetic results as leading indicators, not final proof.

## 3.7 Privilege separation: deny-list is not enough

The proposed deny-list is a good instinct but insufficient.

A fixer could avoid the deny-list by editing:

- A script that later edits the crontab.
- A command fragment that causes a future agent to touch credentials.
- A sync script that propagates a malicious change.
- A test that silently disables a check.
- A metric input file that changes future measurement.

Use allow-list sandboxing.

Minimum sandbox:

- Fixer runs in a separate OS user/container.
- Write access only to its worktree.
- Read-only access to hub tests/fixtures.
- No SSH keys.
- No credential directories.
- No crontab access.
- No network except approved model API endpoint.
- No ability to push.
- No ability to modify orchestrator, verifier, metric registry, audit logs, or sync service.

The orchestrator, not the fixer, performs:

- Branch creation.
- Commit validation.
- Merge.
- Push.
- Sync.
- Rollback.

## 3.8 Test deletion and fixture weakening

Special rule:

> Any diff that deletes or weakens a test/fixture is automatically Tier 3 or rejected.

If a test must be changed because it was wrong, the patch must include:

- The original defect that justified the old test.
- The new defect class being protected.
- A replacement test that fails before the change and passes after.
- Auditor approval.

Otherwise the cheapest way to make tests pass is to delete them.

## 3.9 Separate measurement-code policy

The proposal says:

> The fixer may never edit the measurement code.

I disagree with the absolute ban.

Why? Because you already found collector bugs. If the instrument is wrong, the loop needs a safe way to fix it.

But the fixer must not be able to edit the metric that judges its current hypothesis.

Better rule:

> Measurement code changes are handled by a separate metrology pipeline, with golden datasets, dual-run comparison, and frozen metric versions during active experiments.

Implementation:

- Collector lives in a separate repo or protected directory.
- Metric definitions are versioned.
- Every metric has golden input data and expected output.
- Metric changes produce `metric_v2` and run alongside `metric_v1`.
- Active experiments continue using the frozen metric version.
- New metric becomes official only after comparison period and approval/attestation.

Failure mode: metrology pipeline becomes a bottleneck.

Countermeasure:

- Allow additive telemetry freely as Tier 1.
- Allow metric bugfixes if they do not alter active experiment adjudication.
- Require human/auditor sign-off only for definition changes that affect success criteria.

---

# 4. Attribution

The current plan says:

> One change per day. Adjudicate next day. Nothing counts as fixed until the number moves.

This is too simplistic.

## 4.1 The attribution problem

A daily metric movement can be caused by:

- Different projects being active.
- Different task types.
- Different models/accounts.
- Different plan eras.
- Different session volume.
- Human intervention.
- Randomness.
- Late-arriving data.
- Collector bugs.
- Previous unadjudicated changes.
- Canary exposure differences.

Without exposure tracking, you cannot attribute anything.

## 4.2 Mandatory exposure metadata

Every session/run should record:

```json
{
  "hub_commit": "...",
  "governance_channel": "canary|stable|frozen",
  "command_file_hashes": {...},
  "fragment_hashes": {...},
  "rule_pack_hashes": {...},
  "gate_version": "...",
  "hook_version": "...",
  "scaffold_version": "...",
  "model": "...",
  "account": "...",
  "plan_era": "ticket|single-file",
  "project_id": "..."
}
```

Without this, you cannot know whether a task was exposed to the change.

This is one of the most important missing pieces.

## 4.3 Experiment registry

Before any behavioural change merges, create an immutable experiment record:

```json
{
  "experiment_id": "...",
  "change_id": "...",
  "hypothesis": "...",
  "target_metric": "completion_protocol_correctness",
  "guard_metrics": [
    "premature_terminator_rate",
    "stuck_session_rate",
    "defect_escape_rate"
  ],
  "population": "task-completing runs in canary projects",
  "exposure_marker": "command_hash:abc123",
  "start_time": "...",
  "minimum_exposure_hours": 48,
  "minimum_sample_size": 30,
  "expected_direction": "increase",
  "minimum_meaningful_effect": "5pp",
  "analysis_method": "difference-in-differences with project fixed effects",
  "rollback_trigger": "guard metric degradation > threshold"
}
```

This record should be append-only.

## 4.4 Do not adjudicate most changes after one day

Use different adjudication windows by metric type.

| Metric class | Minimum adjudication window |
|---|---|
| Instrument health | immediate, but only as safety signal |
| Gate integrity | immediate |
| Protocol compliance | 24–72 hours and minimum sample |
| Run completion | 24–72 hours and minimum sample |
| Review rounds | 7+ days or n>=30–50 exposed tickets |
| Defect escapes | 7–14 days |
| Human intervention | 7 days |
| Cost/quota efficiency | 7 days and task mix normalization |
| Rule activation | 24–72 hours and minimum sample |

Next-day movement should be used for **rollback triggers**, not success declarations.

Example:

- If a change causes stop-hook blocks to spike, rollback now.
- If a change appears to improve review rounds after one day, do not declare success.

## 4.5 Use canary and stable rings

The current global sync destroys your ability to run comparisons.

I would introduce governance channels:

```text
frozen: 1–2 projects that lag deliberately for control
canary: 2–3 low-risk active projects
stable: remaining projects
```

Each project repo has:

```text
.fabrik/channel
.fabrik/governance.lock
```

Sync service:

```text
fleet_sync.py --channel canary --change <change_id>
fleet_sync.py --channel stable --change <change_id>
```

Promotion rule:

1. Merge change to hub.
2. Deploy to canary.
3. Monitor guard metrics for 24–48 hours.
4. If no degradation and target metric moves as expected with enough exposure, deploy to stable.
5. Keep frozen channel behind for comparison or emergency rollback.

Failure mode: canary projects are not representative.

Countermeasure:

- Choose canaries with regular activity.
- Rotate canary projects occasionally.
- Stratify metrics by project and task type.
- Do not use canary results for metrics with too few samples.

## 4.6 One-change-per-day: partially right, mostly wrong

The right part:

- Avoid overlapping global changes whose effects cannot be separated.

The wrong part:

- Making the calendar the unit of experimental control.

Better rule:

> At most one global enforcement experiment may be in flight for a given metric population.  
> Multiple isolated low-risk changes may proceed if their affected surfaces and metrics do not overlap.

So:

- One stop-hook experiment at a time.
- One shared-fragment experiment at a time.
- One gate-check experiment affecting the same check family at a time.
- Multiple documentation/test/telemetry changes can proceed.

## 4.7 Evidence ladder, not single number

Not every fix needs fleet metric movement to be considered validated. Some fixes are proven at lower layers.

Evidence ladder:

| Level | Evidence | Sufficient for |
|---|---|---|
| 0 | Unit test / fixture proves mechanism | Low-risk internal correctness |
| 1 | Negative control now fails/pass as expected | Gate/rule fix |
| 2 | Shadow mode shows intended behavioural difference | Enforcement change candidate |
| 3 | Canary metric moves with guard metrics stable | Limited deployment |
| 4 | Stable fleet metric moves over adequate window | Full validation |
| 5 | Outcome metrics improve: escapes, human intervention, validated tasks | Strategic success |

Example:

- A gate check that previously passed a known-bad fixture now fails it. That is real progress even if tomorrow’s fleet gate pass rate does not move.
- A command prompt change that reduces premature final blocks in canary from 22% to 4% with n=60 and no stuck sessions is meaningful, even if global review rounds do not move tomorrow.

The principle:

> Nothing counts as validated until the appropriate evidence layer moves.  
> Fleet numbers are one layer, not the only layer.

## 4.8 Statistical design

Keep it simple but honest.

For each experiment:

- Compare exposed tasks to control tasks.
- Stratify by project/task type/model.
- Report effect size and uncertainty.
- Require minimum sample.
- Mark underpowered experiments as `inconclusive`, not `failed`.

A lightweight approach:

```text
outcome ~ exposed + project + task_type + plan_era + model
```

If sample is tiny, report:

```json
{
  "status": "inconclusive",
  "exposed_n": 8,
  "required_n": 30,
  "effect_estimate": "+0.11",
  "confidence_interval": [-0.14, 0.36]
}
```

Do not make heroic claims from n=8.

## 4.9 How attribution can fail

Failure mode: canary projects differ from stable projects.

Countermeasure:

- Use difference-in-differences: compare canary change before/after against stable before/after.
- Use project fixed effects.
- Keep a frozen control ring.

Failure mode: exposure metadata is missing or wrong.

Countermeasure:

- If exposure metadata is missing, the session is excluded from experiment adjudication.
- Data quality metric tracks missing exposure fields.
- If missing rate is high, experiment is invalid.

Failure mode: changes interact.

Countermeasure:

- Maintain artifact dependency graph.
- Do not run overlapping experiments on dependent artifacts.
- If interactions are suspected, mark experiment as confounded.

---

# 5. What should a human still see?

The operator wants to be out of the loop but not blind. That is reasonable, but “out of the loop” must mean “not the daily detector,” not “no decisions ever.”

The minimum human interface should be exception-based, plus a short weekly attestation.

## 5.1 Immediate escalations

These should interrupt or notify immediately.

### P1: safety/integrity

Notify and pause relevant automation if:

- Gate integrity falls below threshold.
- A blocking check has no negative control.
- Collector/data contract failures persist.
- A canary guard metric degrades sharply.
- Automatic rollback occurs.
- The fixer attempts to touch forbidden paths.
- The sandbox denies an unexpected operation.
- Quota forecast shows human sessions will be starved.
- Three failed attempts on one finding.
- Governance sync drift is detected.
- A change appears to weaken enforcement without approval.

Message format should be one line plus link:

```text
[KAIZEN P1] Gate integrity red: check_run_record_closed passed known-bad fixture. Tier 2+ merges paused. Evidence: /var/kaizen/evidence/...
```

### P2: approval required

Require explicit approval, or default deny, for:

- Weakening or removing a blocking gate.
- Changing stop-hook semantics.
- Changing metric definitions.
- Changing governance sync engine.
- Changing scaffold defaults for all new projects.
- Changing shared fragments used by many commands.
- Removing tests/fixtures.
- Any change with high blast radius and uncertain reversibility.

Approval request should be tiny:

```text
[KAIZEN APPROVAL] Change weakens max-file-size gate. Reason: false positives on generated files. Evidence: 8 sessions. Canary plan: 2 projects, 48h. Default: deny after 48h. Approve? [link]
```

If the operator truly does not want to approve anything, then the system should default-deny those changes and leave them queued. That is safer than silent autonomous weakening.

## 5.2 Weekly attestation

The operator does not need a dashboard, but he does need a trustworthy summary. One short weekly report is enough.

Example:

```text
Weekly Kaizen Attestation

Merged: 5 low-risk, 1 canary-only, 0 global enforcement.
Promoted: 1 gate fix to stable.
Reverted: 0.
Validated: completion protocol +6pp, n=61, guard metrics stable.
Inconclusive: review rounds, n=14.
Failed: 1 prompt change caused +18% premature blocks in canary; rolled back.
Gate integrity: 100% negative-control coverage for blocking checks.
Data quality: 99.6%.
Quota used by automation: 7% of weekly budget.
Open escalations: none.
Unknowns: escape attribution still incomplete for 3 projects.
```

This is not a dashboard to read daily. It is an attestation that the loop is not lying to itself.

## 5.3 When the loop must stop and ask

The loop should stop and ask when:

1. It cannot reproduce a finding but wants to make a high-risk change.
2. A proposed change weakens enforcement.
3. A metric definition must change.
4. Guard metrics move opposite to target metrics.
5. The same finding fails three times.
6. The fixer attempts to modify constitutional surfaces.
7. Quota reserve falls below threshold.
8. Data quality is red for more than 24 hours.
9. A canary rollback occurs.
10. The governance sync would affect more than a defined blast radius without prior canary evidence.

The loop should not ask for:

- Routine low-risk changes.
- Test additions.
- Documentation fixes.
- Shadow-only telemetry.
- Canary deployment of already-approved risk classes.

---

# 6. What are you not thinking about?

Several things are underweighted or missing.

## 6.1 The shared working tree is the biggest operational hazard

Three concurrent agents sharing one working tree is dangerous even without automation. With automation, it is a critical failure waiting to happen.

The isolated worktree for the fixer is necessary, but not sufficient. The hub itself should move toward:

```text
/opt/fabrik.git           # bare canonical repo
/opt/fabrik-worktrees/agent-1/
/opt/fabrik-worktrees/agent-2/
/opt/fabrik-worktrees/agent-3/
/opt/fabrik-worktrees/kaizen-<id>/
```

The shared tree should be clean or removed.

Requirements:

- Each agent works in its own worktree/branch.
- A merge queue serializes changes to `main`.
- No agent directly mutates the canonical tree.
- Automation never operates on a dirty shared tree.
- Active run records can declare intended files for advisory locking.

If you cannot migrate fully immediately, at least:

- Make the automation use only a bare repo and isolated worktrees.
- Prevent automated merges when conflicting uncommitted changes are detected in the shared tree.
- Require rebase and re-verification before merge.
- Never use `git add -A` in shared spaces.

Failure mode if ignored: an automated merge or sync destroys or overrides an agent’s uncommitted work. That is exactly the critical failure you listed.

## 6.2 Governance sync needs staged deployment

A commit to a synced surface propagating to 46 repos is a global production deploy. It should not happen instantly by default.

You need:

- Governance channels: `canary`, `stable`, `frozen`.
- Per-project governance lock files.
- Sync manifests recording which project received which hub commit.
- Dry-run mode.
- Rollback command.
- Post-sync verification.
- Sync failure alerts.

Current model:

```text
commit → all 46 repos
```

Better model:

```text
commit → canary ring → monitor → stable ring → monitor → frozen ring optional
```

If the operator wants daily operation, the daily part can be canary promotion, not instant global propagation.

## 6.3 Run records must become the primary truth

The current compliance metric relies on transcript regex. That is brittle.

Run records should become the source of truth for:

- Command started.
- Command version.
- Active rule packs.
- Phases entered.
- Final block emitted.
- Gate run.
- Stop attempted.
- Stop blocked.
- Run closed.
- Terminal condition.
- Premature terminator events.

The stop hook should enforce:

- No stop without a run record for task-like commands.
- No stop if run record is not in terminal state.
- No stop if final gate is red.
- No stop if uncommitted/unpushed work exists.
- No stop if final block is missing or malformed.
- Record if final block was emitted more than once.

This converts “rules-obeyed” from a text-pattern metric into an event-based enforcement metric.

## 6.4 The textual RULES ACTIVE / final block design is fragile

The platform currently asks agents to emit certain text. Agents can:

- Forget it.
- Emit it too often.
- Emit it with wrong contents.
- Emit it when not task-completing.
- Emit it around bad work.

Better:

- Compute expected active rules mechanically.
- Inject or record them via hooks.
- Validate them against changed files.
- Treat text as a secondary representation, not the enforcement point.

If the text block is still needed, make it schema-validated and tied to run-record state.

## 6.5 You need an artifact dependency graph

You have commands, fragments, rule packs, gates, hooks, scaffolds, fleet scripts, and cron jobs. These are not independent.

Build a graph:

```text
command A includes fragment X
fragment X references gate Y
rule pack R activates on glob G
scaffold S installs command A
fleet script F syncs rule pack R
hook H invokes gate Y
```

Use this for:

- Blast-radius estimation.
- Finding selection.
- Experiment overlap detection.
- Rollback planning.
- Risk tier assignment.

Without it, the actor will make changes whose side effects it cannot understand.

## 6.6 You need outcome tracking for “correct”

“Correct” cannot be inferred only from gate success or review rounds.

You need at least heuristic outcome tracking:

- Revert commits.
- Follow-up fix commits.
- Follow-up run records marked `fix`, `repair`, `regression`, `bug`.
- Human commits after AI commits in the same files/ticket.
- Failed CI after merge.
- Review findings marked severe.
- Tickets reopened.

Start with heuristics. Do not wait for perfect attribution. A coarse escape metric is better than none.

## 6.7 You need a governance overhead budget

Every new rule/check/fragment/hook has a cost:

- More prompt tokens.
- More agent hesitation.
- More gate runtime.
- More false positives.
- More maintenance.
- More coupling.

Define budgets:

- Blocking gate runtime p95 below X seconds.
- Rendered command prompt overhead below X tokens.
- Total active rule packs per task below X.
- New blocking check requires retirement candidate or justification.
- Rules with no true positives for 90 days are reviewed for removal.

Otherwise the system will become slower and more brittle while reporting higher compliance.

## 6.8 Cron jobs and fleet scripts need observability but not autonomous edit authority

There are 21 cron jobs and 12 fleet-synced core scripts. These are dangerous surfaces.

For cron:

- Inventory all jobs.
- Record last run, exit status, duration, output hash.
- Alert on missed runs or repeated failures.
- Do not let the actor edit crontab.

For fleet scripts:

- Checksum across projects.
- Detect drift.
- Version pin.
- Test in sandbox.
- Treat changes as high-risk.

## 6.9 Quota must be part of the control loop

The binding resource is weekly subscription quota. Therefore:

- Every automated dispatch must check quota reserve.
- Automation should have a hard budget, e.g. no more than 10–15% of weekly quota unless human approves.
- Prefer metered API models for:
  - Transcript parsing.
  - Anomaly detection.
  - Dossier generation.
  - Semantic diff audit.
  - Fixture generation.
  - Collector fixes.
  - Auditor role.
- Reserve subscription quota for human sessions and primary project work.

A change that saves quota per validated task is high-value. A change that improves a proxy metric while burning quota is suspect.

## 6.10 The actor must not be able to modify its own constitution

Protected surfaces should include:

- Orchestrator code.
- Dispatcher policy.
- Risk-tier matrix.
- Deny/allow lists.
- Audit logs.
- Experiment registry.
- Metric definitions.
- Adjudication thresholds.
- Rollback triggers.
- Sync engine.
- Hook entrypoints that control the actor.
- Its own prompt templates, unless treated as Tier 3.

This should be enforced by filesystem permissions and git policy, not merely by prompt instructions.

## 6.11 You need a red-team/adversarial function

Periodically, the system should try to break itself in a sandbox.

Examples:

- Submit code with missing final block. Stop hook should block.
- Submit known-bad code. Gate should fail.
- Emit final block mid-run. Run record should flag.
- Create a run record that never closes. Stop hook should block.
- Add a secret-like string. Gate should fail.
- Use an out-of-scope subagent. Ledger should classify correctly.
- Create a conflicting rule pack. Lint should detect.
- Change a synced surface in a canary project. Sync drift should detect.

This function should be separate from the fixer and should produce findings.

---

# 7. Concrete recommended implementation plan

If I were advising implementation, I would not start by turning on the daily fixer. I would do this:

## Phase 0: Freeze high-risk autonomous action

Duration: immediate.

- Disable autonomous Tier 2+ changes.
- Allow only measurement, tests, documentation, fixtures, and shadow telemetry.
- Announce that the loop is in “proof-building” mode.

This is not failure. It is instrument calibration.

## Phase 1: Build the event spine

Goal: make metrics event-based.

Implement:

1. Canonical project registry mapping 98 directories to actual projects/repos.
2. Session event schema.
3. Run record event schema.
4. Gate run schema.
5. Hook event schema.
6. Subagent dispatch schema.
7. Review ledger schema.
8. Exposure metadata: hub commit, command hashes, rule hashes, gate version, model/account, plan era.
9. Immutable raw event store.
10. DuckDB/SQLite analytics store.

Data quality rule:

```text
If schema pass rate < 99%, actor dispatch is paused.
```

Failure mode: agents do not produce run records consistently.

Countermeasure:

- Make command wrappers create run records automatically.
- Make stop hook refuse to close task-like sessions without run records.

## Phase 2: Build gate integrity

Goal: make “green” meaningful.

Implement:

1. Inventory all 57 gate checks.
2. For each blocking check, require:
   - owner,
   - description,
   - pass fixture,
   - fail fixture,
   - assertion trace,
   - mutation score.
3. Prioritize the six known false-pass checks.
4. Run `gate_prove.py` daily.
5. Mark any blocking check without negative control as unverified.
6. Demote unverified checks from adjudication weight.

Failure mode: many checks have no obvious fixture.

Countermeasure:

- Mine historical failures.
- Use LLM to propose adversarial fixtures.
- Have auditor review fixtures.
- Mark those checks as “fixture debt” and do not trust them.

## Phase 3: Rebuild compliance metric

Replace the current confounded metric with:

### Completion protocol correctness

Denominator:

```text
run records that reached task-completion terminal state
```

Numerator:

```text
runs with exactly one valid terminal block,
correct RULES ACTIVE according to changed files,
closed run record,
green gate,
no premature terminator events
```

Separate adverse metric:

```text
premature terminators per 100 runs
```

This immediately splits:

- Missing terminator.
- Repeated terminator.
- Wrong terminator timing.
- Wrong active rules.
- Untracked completion.

## Phase 4: Create canary rings

Implement governance channels.

Select:

- 1 frozen control project.
- 2–3 canary projects with regular activity and low criticality.
- Remaining projects stable.

Sync service:

```text
fleet_sync.py --dry-run
fleet_sync.py --channel canary
fleet_sync.py --channel stable
fleet_sync.py --rollback <change_id>
```

Each sync writes:

```text
/var/kaizen/sync-manifest.jsonl
```

## Phase 5: Start low-risk daily action

Allow only:

- Tier 0 documentation/metadata fixes.
- Tier 1 non-blocking telemetry/advisory checks.
- Fixture creation.
- Collector/metric shadow fixes through metrology pipeline.

No global enforcement changes yet.

## Phase 6: Start canary-only behavioural changes

When data quality and gate integrity are green:

- Allow one Tier 2 experiment in canary at a time.
- Require failing test/negative control.
- Require shadow comparison.
- Require 24–48 hour canary monitoring.
- Auto-rollback on guard metric degradation.
- Promote to stable only with sufficient sample and no guard regression.

## Phase 7: Begin weekly attestation and exception channel

Generate:

- P1 alerts immediately.
- Approval requests for Tier 3.
- Weekly attestation.
- Immutable audit log.

The operator should not need to check anything unless notified.

---

# 8. Specific criticisms of the proposed actor

Here is my direct critique of the proposed actor in section 5 of your document.

## 8.1 “Select exactly one finding”

Wrong as a hard rule.

Better:

- Maintain a ranked queue.
- Dispatch zero, one, or several changes depending on risk tier and independence.
- For global enforcement, allow at most one experiment per affected population.
- For low-risk isolated changes, allow more if quota allows.

The daily quota should apply to risk and quota, not to findings.

## 8.2 “Build an evidence dossier, not an instruction”

Good instinct, but incomplete.

The dossier should include:

- Failing test or negative control.
- Blast-radius estimate from dependency graph.
- Risk tier.
- Allowed paths.
- Forbidden paths.
- Max diff size.
- Expected metric movement.
- Guard metrics.
- Canary plan.
- Rollback plan.
- Prior failed attempts and their root causes.
- Whether the change weakens, strengthens, or preserves enforcement.

Without a failing test, the dossier is mostly narrative.

## 8.3 “Create an isolated git worktree”

Correct and necessary.

But also require:

- Worktree from bare/canonical repo.
- No access to shared dirty tree.
- OS-level sandbox.
- No push authority.
- No secret access.
- No crontab access.
- No orchestrator access.

## 8.4 “Dispatch a headless AI coding session”

Potentially useful, but constrained.

Add:

- Diff size limit.
- Allowed paths enforced after diff.
- Commit trailers mandatory.
- No deletion of tests/fixtures without Tier 3 approval.
- Model/account recorded.
- Quota cost recorded.
- Session transcript stored as evidence.

If the fixer uses subscription quota, enforce budget. If possible, move fixer to metered API.

## 8.5 “Verify independently”

Correct, but expand verification to:

- Data contract tests.
- Gate negative controls.
- Mutation score for touched checks.
- Policy diff.
- Semantic auditor.
- Shadow comparison.
- Golden task harness where relevant.
- Commit provenance validation.
- Diff allowlist validation.
- Rollback plan validation.

The orchestrator should not merely re-run the new gate. It must verify that the gate itself was not weakened.

## 8.6 “Merge only on green”

Correct, but “green” must include meta-green.

Green should mean:

- Worktree tests pass.
- Gate fixtures pass.
- Mutation score acceptable.
- No forbidden paths touched.
- No policy weakening unless approved.
- No test deletion unless approved.
- Shadow comparison acceptable.
- Canary plan exists.
- Rollback possible.
- Exposure metadata available.

## 8.7 “Record a hypothesis”

Correct. Make it immutable and include:

- Target metric version.
- Guard metric versions.
- Minimum sample.
- Minimum exposure.
- Analysis method.
- Rollback trigger.

## 8.8 “Adjudicate the next day”

Too soon for success, useful for safety.

Use next-day adjudication for:

- Sharp guard-metric degradation.
- Stuck sessions.
- Gate integrity failures.
- Stop-hook traps.
- Sync failures.
- Quota blowouts.

Use longer windows for:

- Review rounds.
- Escapes.
- Human intervention.
- Validated task rate.
- Cost efficiency.

## 8.9 “Fixer may never edit measurement code”

Too absolute.

Replace with:

- Metric definitions are frozen during experiments.
- Measurement changes go through separate metrology pipeline.
- Measurement changes require golden tests and dual-run comparison.
- The actor cannot edit the metric used to judge its current experiment.
- Metric definition changes are logged and included in weekly attestation.

## 8.10 “3 failed attempts → escalate”

Good.

Add:

- Preserve failed worktree diff, transcript, verifier logs.
- Require root-cause classification before retry.
- Do not allow identical retry without new evidence.
- If failures are due to insufficient evidence, convert to research/fixture task.

## 8.11 “Hard deny-list”

Good intent, insufficient.

Use allow-list sandbox and filesystem permissions. Deny-list can be bypassed indirectly.

## 8.12 “One dispatch per day”

Good as cost control, bad as experimental design.

Replace with:

- Quota budget.
- Risk budget.
- One global enforcement experiment per affected population.
- No dispatch if expected value is too low.

---

# 9. What I would measure first, in priority order

If I had to choose a practical sequence:

## Priority 1: Instrument health

- Collector golden tests.
- Schema pass rate.
- Denominator validity.
- Exposure metadata completeness.

Without this, everything else is contaminated.

## Priority 2: Gate integrity

- Negative-control coverage.
- Assertion trace validity.
- Mutation score.
- Shadow disagreement.

Without this, “green gate” is not proof.

## Priority 3: Run-record completion

- Run completion yield.
- Untracked completion rate.
- Stop-hook block rate.
- Premature terminator rate.

This gives you a real denominator for task-like work.

## Priority 4: Protocol correctness

- Completion block correctness per run.
- RULES ACTIVE correctness based on changed files.

This replaces the current broken compliance metric.

## Priority 5: Quality outcomes

- Defect escape rate.
- Human intervention rate.
- Rework ratio.
- Review severity and rounds, ticket-era only.

This prevents proxy optimization.

## Priority 6: Efficiency

- Quota per validated task.
- Turns/tool calls per completed task.
- Subagent reliability by task type.
- Gate runtime.

This captures “fastest” without rewarding corner-cutting.

## Priority 7: Governance overhead

- Artifact count growth.
- Prompt token overhead.
- Rule activation frequency.
- Rule retirement rate.

This prevents 60-day bloat.

---

# 10. The fundamental better shape

If I reduce my recommendation to one concept:

> Turn the kaizen loop into a **regression factory**.

Every observed defect should become a test before it becomes a patch.

Examples:

### Observed defect

Agents emit final block 36 times per session.

Regression factory response:

1. Extract representative transcripts.
2. Create fixture: session with premature final blocks.
3. Define expected behaviour: run record flags premature terminator; stop hook/gate rejects or records violation.
4. Fix command/hook until fixture passes.
5. Measure premature terminator rate in fleet.
6. Guard against false positives with normal multi-turn sessions.

### Observed defect

Gate check passes while asserting nothing.

Regression factory response:

1. Create known-bad fixture that previously passed.
2. Meta-test expects gate failure; currently meta-test fails.
3. Fix gate check.
4. Meta-test passes.
5. Add mutation tests.
6. Add shadow comparison.
7. Canary deploy.

### Observed defect

Review rounds are high.

Regression factory response:

Do not immediately change commands. First:

1. Classify why rounds occur.
2. Sample reviews.
3. Identify recurring defect classes.
4. Create fixtures/golden tasks for those defect classes.
5. Only then propose prompt/rule/gate changes.
6. Measure review rounds and escapes together.

This is slower than “dispatch one fix today,” but it compounds. After 60 days you have:

- A corpus of negative controls.
- A corpus of golden tasks.
- A trustworthy gate.
- A meaningful metric layer.
- A change history with evidence.
- A system that gets harder to fool.

That is the actual product.

---

# 11. Bottom line

I would not run the proposed daily actor as written. It is too eager to act, too reliant on immature metrics, too globally actuated, and too trusting of “green” verification.

I would replace it with this:

1. **Daily metrology loop** that validates data and generates findings.
2. **Daily regression factory** that converts findings into failing tests and evidence dossiers.
3. **Risk-tiered change pipeline** that allows only low-risk changes to merge freely.
4. **Canary/stable/frozen governance channels** instead of instant sync to 46 repos.
5. **Meta-verification**: negative controls, mutation testing, shadow mode, semantic policy diff, golden tasks.
6. **Exposure-aware adjudication** over appropriate windows, not next-day number worship.
7. **Exception-only human signal**, with weekly attestation and hard stop conditions.
8. **Constitutional boundaries** that prevent the actor from editing its own judge, credentials, cron, sync engine, or metric definitions.

The operator’s goal is correct:

> Machinery that makes AI agents correct by default.

But that machinery will not be built by a daily patch loop that optimizes its own paperwork. It will be built by a system that turns real failures into provable tests, changes infrastructure in bounded rings, and treats every green signal as something that must itself be proven.



---

## moonshotai/kimi-k3

# Independent design review: the daily self-improving loop

I've read the whole system. My overall verdict first, then the sections in your order.

**Overall verdict:** The shape — dossier → isolated worktree → independently verified merge → hypothesis → next-day adjudication — is fundamentally sound. Keep all of it. But as specified, the loop has three structural flaws that will dominate its behavior within 60 days, and none of them is in the parts you're worried about:

1. **Your adjudication rule will confirm noise and kill signal.** Worst-first selection plus day-over-day comparison is a regression-to-the-mean machine. You will "confirm" no-op fixes, accumulate them as governance text, and revert real fixes that happened to land on a loud day.
2. **Every merged fix is an uncontrolled fleet-wide experiment.** You have sync machinery that can propagate to 46 repos and no way to propagate to *some* of them. The absence of a canary channel is simultaneously your biggest attribution problem and your biggest blast-radius problem — and it's the same fix.
3. **The loop as specified only ever adds governance.** Every fix is more lines, more checks, more rules. Your enforcer is an attention-based reader of that text. Monotonic growth of the rulebook degrades the very compliance you're measuring — a self-reinforcing failure that no individual metric will attribute to it.

A fourth runs underneath everything: "the fixer may never edit the collector" is the right instinct at one-tenth the necessary scope. The correct rule is a **plane separation**: anything that *shapes* behavior is fair game for the fixer; anything that *measures or blocks* requires human sign-off and instrument tests. Details below.

---

## 1. The loop's shape — what breaks at 60 days

### The headline failure mode nobody sees coming: governance bloat

Every finding resolution in your design is an addition: a clarified rule, a new check, an extra line in a command, a new fragment. Now run the loop for 60 days. The rulebook grows by dozens of edits. Your 56 rule packs and 27 commands get longer, more cross-referential, more redundant.

The enforcer of these rules is a language model with finite attention. Compliance with any individual rule rises after its fix — and aggregate compliance *falls* as total governance volume rises, because each agent is now skimming a longer document. The loop observes falling compliance, selects it as a finding, and fixes it by adding more text. **This is a positive feedback loop with no term in your design that opposes it.**

Counter-design, concretely:

- **A net-zero governance budget.** Track total token count of all synced governance surfaces as a first-class guardrail metric. Any fix that increases it must also remove at least as much. The dossier template should have a mandatory field: "what text is deleted or condensed."
- **Prefer-edit-over-add as a dispatch constraint.** The fixer's instructions should rank acceptable resolutions: (1) delete dead text, (2) edit existing text, (3) consolidate two artifacts into one, (4) add new text — only with explicit justification.
- **Hygiene findings as a first-class finding class.** The collector should emit: rule packs not triggered in 60 days, commands never invoked, gate checks that have never fired (see §3 — mutation testing distinguishes "never fires because compliance is perfect" from "never fires because it asserts nothing"). Deletion fixes are your cheapest throughput improvements and they shrink the attack surface.

Related, and also invisible day-to-day: **governance churn has a prompt-cache cost.** Every edit to a synced command or fragment invalidates the prompt cache prefix of every session in the fleet. With quota as your binding resource, a daily fleet-wide governance push is a daily tax on every session's first turn. Measure it (cost/latency delta of first turns after syncs), batch cosmetic edits, and let this cost inform the "is this finding worth fixing" threshold.

### Second failure mode: confirmed-noise accumulation

If you select the worst-measured finding each day, you are selecting on a noisy draw. Metrics measured at a bad draw drift back toward their mean with no intervention. Your adjudication rule — "moved → confirmed" — will certify these as fixes. Each certified non-fix leaves behind a commit, usually additive. Over 60 days: ~30 merged changes, of which a substantial fraction are noise-certified, all accumulating text. The fix ledger looks like progress; the fleet is just heavier.

This is why §4 (attribution) is not a statistics nicety — it is the difference between the loop compounding value and compounding mass.

### Third: barrel-scraping

By day 40 the easy findings are gone. The queue contains hard, root-caused, ambiguous problems. A daily cadence with a must-pick-one rule forces the actor to pick *something*, and a fixer session with a dossier will always produce *a* change. Marginal-to-harmful changes get dispatched because the alternative — declaring "nothing worth fixing today" — isn't in your design.

Make **idle a first-class success state.** Detection runs daily; dispatch runs when the queue's top item clears an expected-value bar (frequency × severity × blast radius × measurement confidence ÷ fix risk). On days below the bar, the loop's output is "nothing today, queue state attached." A loop that cannot say no will eventually eat the platform.

### Fourth: hypothesis capacity

Adjudication windows are multi-day (they must be — see §4). If you dispatch daily with 5–7 day windows, you have 5–7 open hypotheses at any time. That's fine when they target orthogonal metrics and confounding when they don't. The real constraint isn't one-change-per-calendar-day; it's **at most one open hypothesis per metric family**, and a bounded total of concurrent open hypotheses (I'd set it at 3–4 initially). A finding targeting a metric with an open hypothesis waits, or merges into the open one. Calendar cadence is a proxy for this constraint — replace the proxy with the constraint.

### Fifth: fix-memory, or the 3-strikes rule is not enough

Three strikes stops *this* attempt series. Nothing stops attempt #4 next month, with a cosmetically different diff and the same underlying theory of the defect. Record every failed attempt with its diff and its hypothesis; before dispatch, check the new dossier against the failed-attempt store (embedding similarity over diffs plus the finding text is sufficient). "We already tried the obvious thing" is institutional knowledge the loop currently plans to forget.

### What I'd keep exactly as proposed

The dossier-as-evidence design (file:line, proving sessions, expected metric direction, may-touch/must-not-touch lists) is the strongest part of the proposal — it's what converts the fixer from an investigator into an editor, and it matters doubly given quota economics. Independent orchestrator-side verification is correct and the "never trust the session's claim" framing is right. Worktree isolation is the correct fix for the dirty-tree starvation your CI fixer exhibited. Escalation after repeated failure is correct.

One implementation detail to check before you trust the worktree plan: your run-record and Stop-hook machinery is presumably keyed by repo path. Verify the fixer session in a worktree opens its run records in the *worktree's* ledger, not the main tree's, and that the Stop hook doesn't see the main tree's state. A fixer that can't close its own run record because it's looking at the wrong tree will spin until quota dies. And the final merge into main must check, path-by-path (`git status --porcelain -- <touched paths>`), that none of the fix's paths are dirty in the main tree — merge-clean is not enough when three agents share the tree. Fail closed.

---

## 2. What to measure

### The principle underneath everything: govern artifacts, not utterances

Your two collector bugs and your six vacuous gate checks are the same disease. The failure predicate `status != "ok"` asserted on *vocabulary*; the 1440-rounds bug asserted on *text shape*; the vacuous checks asserted on *the presence of text*. Every one of these is a check on an utterance rather than on the state of the world.

Utterance-checks are Goodhart-bait by construction: the cheapest way to satisfy "response contains X" is to emit X, which is exactly the failure your compliance metric is already conflating (terminator spam vs. missing header). State-checks — git state, file state, test results, run-record terminal conditions — resist this, because the agent can't cheaply fake the world.

Audit all 203 artifacts through this lens. Wherever a gate check or metric asserts on transcript text and could assert on state (your run-record machinery is the right substrate — it has phases and terminal conditions), migrate it. Where a text assertion is unavoidable, treat it as a known-weak check and pair it with an abuse detector (e.g., terminator-spam detection alongside terminator-presence).

### Run records are your denominator oracle — prioritize them above everything

Every denominator problem you listed (defects 1, 2, 3) dissolves if task-completing turns are defined by run records rather than transcript regexes. The run record knows a command was invoked, what phases it entered, and whether it closed. That is the population against which "did the agent emit the required block" is well-defined. Until run-records have coverage, *no compliance-derived fix should be dispatchable* — the instrument hasn't passed its own gate. Fixing instruments before the behaviors they measure should be a standing rule, not a one-time lesson.

### The metric set I'd build, mapped to the verbatim goal

"Fastest, most accurate, most correct, rules-obeyed" decomposes cleanly:

| Goal | Metric | Goodhart failure | Counter-design |
|---|---|---|---|
| Fastest | **Time-to-green per run record** (open → gate success), and turns-to-green | Splitting work into smaller records; abandoning hard tasks | Measure per *ticket*, not per record; pair with rework guardrail |
| Accurate | **First-pass gate rate** (gate green on first run per task) | Deferring the gate run (never run it, never fail) | Stop-hook already forces gate before close — keep it that way; metric is rate *per closed record* |
| Correct | **Rework-after-merge**: commits reverted or fix-committed within 72h; escaped-defect count where projects have tests | Not merging (no rework if no merge); reclassifying fixes | Fixed vocabulary owned by measurement plane; pair with throughput |
| Rules-obeyed | **Compliance as a vector**, split into atomic components: missing header when record demands it / terminator spam / premature close / unpushed work | Auto-emitting the boilerplate from a hook (100% compliance, zero behavior change) | Detect hook-emitted blocks mechanically; the metric counts agent-emitted only |
| (platform health) | **Stop-hook block rate per session** | Weakening the Stop hook | Plane 2 — human sign-off to touch it |
| (invisible today) | **Rule-pack trigger precision/recall**: did the packs that fired match the files edited (from transcripts) | Broadening globs until everything fires (recall 1.0, precision ~0) | Report both numbers; precision collapse is itself a finding |
| (bloat guardrail) | **Total governance token count**, per surface and fleet | — | Net-zero budget, §1 |
| (loop health) | **Confirmed-fix rate, reversion rate, escalations/week, quota+$ per confirmed fix** | The loop grading itself leniently | Adjudication statistics are fixed code in Plane 2, not prompt text |

Verdicts on your existing metrics:

- **The 36% compliance scalar: junk as-is, and you correctly identified why.** Don't tune it; split it into the vector above and re-baseline. The 7%→73% per-project spread is worth one investigation before any fix — my prior is that it's rule-glob misfit (packs not firing where they should), which the precision/recall metric would confirm cheaply.
- **Review rounds: keep, but only era-stratified, with n attached everywhere it renders.** A number computed from n=12 that displays without its n is a future bad decision. Build minimum-n suppression into the collector: below n=30, the number renders as "3.2 (n=12 — low confidence)" in every downstream consumer, including dossiers.
- **Subagent failure rate / latency / cost: keep, with the status vocabulary made a versioned schema** (see §3). And cost-per-day is a *report*, never a *target* — the cheapest subagent fleet is the empty one.
- **Sessions/day: context, not health.** Use it only as a stratifier for other metrics.

### Two metrics you don't have that matter more than most above

**A holdout metric the fixer never sees.** Reserve one holistic measure — a weekly metered-model audit that reads a stratified sample of transcripts and scores them against a rubric (coherence, task fit, corner-cutting, instruction-following in the large) — that is never included in dossiers and never drives finding selection. If every targeted metric improves for a month while the holdout degrades, you are Goodharting at fleet scale and no per-metric counter will catch it. This is your tripwire for metric monoculture drift, which is otherwise undetectable from inside the metric set.

**Outcome-level validation.** Everything above measures agent *behavior*. Behavior metrics are leading indicators; the claim of the whole platform is that they proxy project outcomes. Pick one or two lagging outcome signals per project (build green rate, deploy success, whatever each project affords) and check quarterly that behavior-metric improvements correlate with outcome movement. If compliance doubles and outcomes don't move, you've been tuning the map. This check is cheap, infrequent, and is the only thing that validates the entire premise.

### Instrument hygiene, built into the collector

Your two collector bugs both would have been caught by machinery cheaper than the bugs were confusing:

- **Schema contracts.** Every ledger gets a versioned schema with enumerated vocabularies (`done`/`error`/`capped`/`out_of_scope`). The collector validates on read and *refuses* on violation. `status != "ok"` dies at the schema, not in a meeting.
- **Plausible-range invariants per metric.** Review rounds ∈ [0, 20]; rates ∈ [0, 1]; failures ≤ dispatches; rounds ≤ turns. "1440 rounds" violates an obvious invariant. Invariant violation quarantines the metric and pages the human — an instrument failure is a Plane 2 event, not a finding.

---

## 3. The verification problem

You asked the right question, and your own evidence answers its scale: six of fifty-seven gate checks were theater. Assume ≥10% of Plane 2 is theater until proven otherwise. Here is the defense-in-depth I'd build, in order of leverage.

### 3.1 Plane separation with teeth

Formalize two planes:

- **Plane 1 — shapes behavior:** commands, fragments, rule packs, scaffolds. The fixer may touch these, within the dossier's may-touch list.
- **Plane 2 — measures or blocks:** gate checks, hooks, run-record machinery, collector, adjudicator, dossier templates, sync machinery, **and the actor itself**. Fixer-proposed changes here go to a human approval queue. No exceptions, including "obvious improvements."

Enforce mechanically, not by instruction: a **pre-merge policy engine** reads the dossier's may-touch list, classifies every diff path against plane globs, applies the denylist (credentials, crontab, other repos), and **fails closed** — an unclassifiable path blocks the merge. The fixer prompt can say whatever it wants; the merge doesn't care.

How this fails: path classification has edge cases (a fixture file a gate test reads is arguably Plane 2). Fail-closed means those land in the human queue — acceptable friction, and the queue length is itself observable.

### 3.2 Mutation testing — the direct answer to "weakening a rule, making a check vacuous"

You've already discovered the disease manually; now make discovery continuous. For each of the 57 gate checks, maintain a **seeded-defect fixture**: a minimal repo state that violates exactly that check. Nightly, and on any merge touching gate paths: every check must FAIL on its fixture and PASS on the clean state. A check that cannot be made to fail is vacuous — quarantine it (and that is a finding). A fixer change that causes a check to stop firing on its fixture blocks the merge *even with a green gate* — that is precisely the "made the check vacuous" attack, caught structurally rather than by review luck.

How this fails: fixtures rot as the platform evolves (paths move, fixture setup breaks). Mitigate by making fixture health itself an invariant in the nightly run — a fixture that errors rather than fails is a quarantine event, not a pass.

### 3.3 Golden corpus for the collector

Hand-label 50–100 transcripts: this one has terminator spam, this one is clean, this one is a read-only session that owes nothing. The collector's output on the golden corpus is snapshotted; any drift is an instrument event. This turns "verify the instrument before believing the number" from a lesson into a mechanism, and it's what makes compliance-vector fixes *dispatchable at all* under the instruments-first rule.

### 3.4 Adversarial review by a different model family

Before any merge, two metered-API reviews of the diff, each with a narrow brief:

- **Strictness hawk:** "Compare before/after. Classify every governance-affecting hunk as tightening / neutral / loosening. Anything loosening → human queue." Apply this to rule packs too, not just gates — a "clarification" that removes a MUST is a loosening.
- **Goodhart hunter:** "Given the finding and the metric it targets, describe the cheapest way this diff could move the metric without fixing the underlying behavior. Does this diff do that?"

Use a **different model family for review than for fixing.** A fixer built on the same weights as the reviewer shares its blind spots; a fixer built on the same weights as the *fleet agents* may not even perceive the failure mode it's dispatched to fix. The metered pool being cheap and off-quota makes diversity nearly free. This is the single best use of the metered pool in the whole design.

How this fails: reviewers miss subtle weakening, and rubric-gaming diffs can be written to *read* as tightening. This layer catches the obvious 80%; the canary tripwires (3.5) catch what gets through, in behavior rather than in text.

### 3.5 Canary tripwires — the runtime backstop

Some badness is invisible statically. After any merge to a canary cohort (§4), watch for hours, not a day: gate red-rate, Stop-hook block rate, session aborts, sync failures, first-turn latency/cost (cache invalidation). Breach → automatic revert commit + page the human. This converts "weakening that only manifests in agent behavior" from a next-day discovery into a same-hour revert, and it's the mechanism that makes auto-merge survivable at 46-repo blast radius.

### 3.6 The loop may not modify its own halt conditions

The tripwire thresholds, the 3-strikes rule, the escalation budget, the policy engine itself: changes to these are human-only, full stop. A self-improving loop that can edit the conditions under which it stops is a loop that will eventually not stop.

---

## 4. Attribution

### Why daily pre/post cannot work here

Your metrics have: daily n swinging 16→91; project mix drifting day to day; task mix drifting; and — the one you didn't list — **model rotation**. Three accounts exhausted in ~2 days and rotated means the underlying model mix *intrinsically changes through the week*. A metric that looks like it moved after your fix may have moved because Tuesday is a different model than Monday. Add worst-first selection (guaranteeing you measured at a bad draw) and "moved → confirmed" certifies regression to the mean as engineering.

You already have internal proof that naive aggregation lies: the mixed-era 4.8 hid the ticket-era 3.2. That lesson generalizes to every adjudication.

### The ladder of designs, and where to stand

**Level 1 — rolling baseline with pre-registration and persistence (do this immediately, it's two days of work):**
- Per metric: 28-day rolling median + MAD, stratified at minimum by busy/quiet day.
- The dossier's "expected metric movement" becomes a **binding pre-registration** (structured YAML in the fix ledger): metric, direction, threshold (e.g., ≥1.5×MAD), window (e.g., must hold 3 of the next 5 days), guardrails that must not degrade.
- "Confirmed" = crossed threshold *and persisted* against the rolling baseline — never against yesterday. "Failed" = window elapsed without crossing. Indeterminate is an allowed verdict.
- Every merged fix is logged as a **change point against all metrics**, not just its target. A monthly scan of the fix × metric-movement matrix shows side effects and confounds — fixes that move metrics they weren't aiming at are information, not noise.

**Level 2 — cohort channels (the main recommendation; this is the highest-leverage infrastructure investment available to you):**

Your sync layer currently has one channel: everyone. Add a `channel: stable|canary` field to the sync manifest. Canary cohort: 8–10 repos, stratified by activity so the cohort's aggregate baselines roughly track the fleet's. Every governance change ships to canary first; adjudication compares **cohort vs. rest over the same window** — difference-in-differences. This design kills your worst confounds by construction: day effects, model rotation, and project-mix drift hit both cohorts simultaneously, so they cancel in the difference. It simultaneously caps blast radius (a bad change reaches 9 repos, not 46) and enables the §3.5 tripwires. One mechanism, three of your biggest problems.

**The free v0: the hub is already a one-repo canary.** It has the most sessions and 49 of your 237 review ledgers. Ship to hub first, adjudicate hub-vs-fleet, then sync. You can do this this week with zero sync changes; build real channels when the v0 proves the pattern.

**Level 3 — switchbacks (rarely):** for hub-global changes where no cohort exists (Stop-hook behavior, the collector itself), alternate treatment by day with washout days. More complex, more disruptive; reserve for the few changes that need it.

### So: is one-change-per-day right?

As a **quality discipline**, yes — one dossier, one hypothesis, done well, beats a batch done sloppily, and batches genuinely can't be attributed when they share a metric. As a **throughput constraint**, it becomes wrong the moment channels exist: changes targeting orthogonal metrics in isolated cohorts don't confound each other. The correct rule is the §1 capacity rule — one open hypothesis per metric family, 3–4 open total, queue-driven dispatch with idle as a valid state. Early on (Level 1 only), that will *feel* like one-a-day. That's a coincidence, not a design.

### Minimum-n as a hard rule

No structural conclusion below a pre-registered n. Your 3.2-vs-4.8 ticket-era finding rests on n=12 from 3 plan sets — directionally encouraging, statistically fragile (could be task size, novelty, project). Flag it as provisional, keep measuring, and don't encode it into scaffolds until it survives Level 1 persistence. A platform that "learns" from n=3 will encode noise into the birthplace of every future project — scaffolds are the worst place to be wrong, because they replicate.

---

## 5. What the human should see

The operator wants out of the loop but not blind. The design principle: **push is for events that change what he must do; everything else is pull.**

### Push (interrupt him), the complete list

1. Denylist or Plane 2 touch attempts by the fixer (including the human-approval queue for legitimate Plane 2 changes).
2. Three-strikes escalation on a finding.
3. Canary tripwire auto-revert.
4. Instrument failures: schema violation, invariant breach, golden-corpus drift, vacuous-check quarantine.
5. Loop self-damage: the actor, collector, or adjudicator failing to run (dead-man's switch — silence by 09:00 is an alert, not an absence of one).

### Pull (he looks when he wants)

A weekly one-paragraph digest: fixes attempted / confirmed / reverted / indeterminate; escalations and their disposition; top of the queue; quota + dollars consumed by the loop and cost per confirmed fix; governance token count delta; open hypotheses with their pre-registered windows. Every merged fix listed with a **one-word veto** — replies "revert 12" and the loop reverts fix 12. Revertibility that's exercised is real; revertibility that's theoretical is not (run a quarterly revert drill: pick an old fix, revert it, confirm nothing depended on it — revert paths rot like everything else).

### The escalation budget and the monthly constitutional review

Track escalations/week as loop health, with a budget (say ≤2). If the loop exceeds it, the loop *slows itself* (dispatch every other day) rather than converting the operator into the loop's employee — alert fatigue is how "out of the loop but not blind" dies. Monthly: a 30-minute constitutional review — all Plane 2 diffs (should be few), the confirmed-fix rate, the fix × metric impact matrix, and 3–5 randomly sampled merged fixes read by the human for *taste*. The metrics encode "fastest, most accurate, most correct"; they do not encode the operator's architectural preferences, and a loop that never samples his judgment will drift from it silently.

---

## 6. What you're not thinking about

**1. The dossier path is a privilege escalation channel, treat it like one.** You've built an automated path from *fleet transcript content* to *commits that govern 46 repos*. Transcripts are not trusted input — agents produce pathological text, and if any of your 46 projects ingests external data, prompt injection can ride a transcript into a dossier into a fixer session with push rights. Mitigations: dossier construction treats session excerpts as quoted data with hard delimiters, never as instructions; the policy engine's denylist is mechanical and fail-closed (you have this if you build 3.1); the fixer's prompt is assembled from templates with the evidence in clearly marked data blocks. This isn't paranoia — it's the natural consequence of automating trust, and it's cheap to get right now and expensive to retrofit.

**2. Model rotation is an unmeasured covariate.** Log account/model per session (probably already recoverable from transcripts) and include model mix as a stratifier in adjudication. Otherwise a slice of every metric's weekly variance is rotation, and some "fixes" will be confirmed on the strength of which account was active.

**3. The fix ledger is the crown jewel.** After 90 days it is the institutional memory of what works — hypotheses, pre-registrations, verdicts, failed diffs, reversions. Back it up off-box, append-only, integrity-checked. It is more valuable than any single artifact it manages, and it's currently planned as a side effect.

**4. Deletion is the missing fix class.** Covered in §1 but worth restating as a blind spot: your finding taxonomy has no hygiene class. Dead rule packs, never-invoked commands, never-firing gates. The collector can emit all three mechanically. A loop that can only add will eventually choke the thing it maintains.

**5. Sampling and data growth.** 8.2 GB and ~91 sessions/day growing. Mechanical metrics can afford full-corpus reads for a long time; LLM audits cannot and should not — stratified sampling (by project, length, outcome) both bounds cost and forces explicit denominators, which you've already learned you need. Decide the sampling frame now, while the audit is being designed, not after its first bill.

**6. Resist per-project governance forks.** The 7%→73% compliance spread will tempt per-project rule variants. Don't, until the per-project deltas prove stable across weeks. Forty-six variants is forty-six times the Plane 1 surface, the fix memory, and the adjudication demand. Heterogeneity is a finding, not a configuration opportunity.

**7. Fixer model choice is a verification decision.** When the finding is "agents of model family X exhibit behavior Y," dispatching the fix to family X risks self-blindness; dispatching review to family X guarantees shared blind spots. Default: fixer and reviewer from different families, both metered where the harness allows. Which leads to:

**8. Move the loop off the subscription quota almost entirely.** Dossier drafting, finding clustering, both adversarial reviews, the weekly audit, adjudication arithmetic — all metered, all cheap. The fixer dispatch is metered too if your harness supports headless API sessions (worth the plumbing; the dossier design already makes the fixer's job narrow). Then the loop's quota footprint approaches zero and the "a daily fix costs quota a human session can't use" tension mostly evaporates. Schedule any residual subscription work for the operator's low-activity hours.

---

## If I were sequencing the first 30 days

1. **Week 1 — instrument integrity (Plane 2 first, always):** schema contracts + plausible-range invariants in the collector; mutation fixtures for all 57 gate checks (expect to quarantine several — budget for it); golden corpus v0 (even 30 transcripts).
2. **Week 2 — denominators:** run-record coverage pushed to the point where the compliance vector can be defined on records, not regexes; compliance scalar split into the vector; minimum-n rendering everywhere.
3. **Week 3 — adjudication before actor:** rolling baselines + pre-registration YAML + persistence rule; hub-first canary as the v0 cohort; tripwire metrics defined even before auto-revert exists.
4. **Week 4 — actor pilot in human-approve-everything mode:** the policy engine and planes enforced mechanically from day one, but every merge also human-approved. Loosen to auto-merge only after ~10 clean cycles, and only for Plane 1 canary-first changes.

Note what this sequence does: the actor is the *last* thing trusted, not the first thing built. The loop's credibility is its instrument integrity and its statistics; the fixer is interchangeable labor, and should be treated that way — narrow dossiers, different model family, mechanical constraints, verified by machinery it cannot touch.

The vision is right. The failure mode of visionary loops is never the vision — it's confirmed noise accumulating as governance mass until the enforcer drowns in its own rulebook. Build the statistics, the channels, and the bloat budget, and the rest of the design earns its keep.



---

## minimax/minimax-m3

I'll work through this in the order that builds the most leverage. The loop's shape is downstream of the metric set, the metric set is downstream of what "correct" actually means in this system, so I'll start there and let everything else fall out. Then I'll go after the parts of the proposal I think are wrong — and there are several.

---

## 1. What "correct" means when the consumer is an AI agent

This is the question that has to be settled first, because every metric, every gate, and every fixer decision is an answer to it. The operator's stated goal — "fastest, most accurate and correct, rules-obeyed" — is four clauses, and they are not all the same kind of thing. Conflating them is the most likely source of a Goodhart failure mode inside this loop.

I would separate them into four independent objectives, each with its own measurement, because anything else will be optimized into a single number that means nothing:

**Fastest** is unambiguous *when measured against a specific task shape.* A session's wall-clock, normalized for tokens-in/turns/shell time, is a throughput proxy. But "fastest" without a task taxonomy is just latency on whatever happens to be measured — the exact Goodhart pattern. Without controlling for *what kind of work was done*, every rule change that makes the agent skip a verification step will look like a speedup. That's not a speedup; that's removing the work. So speed is only meaningful paired with a task taxonomy, and that taxonomy has to be enumerated and stable.

**Most accurate** is the most dangerous one. The plain reading — "the agent's code is correct" — cannot be directly measured on a fleet of 46 projects because most of them have no automated test suite. The operator has, in effect, substituted the gate for tests. That's defensible — but only if the gate is honestly measured itself, and we already have evidence it isn't: six checks report PASS while asserting nothing (the "vacuous check" problem, which I'll come back to). *Accuracy* in this system is really a compound of three things:

1. The gate's true positive rate (does it catch real defects? — measurable by mutation testing on hand-injected defects).
2. The gate's false positive rate (does it block work that would have shipped? — measurable by a held-out gold set of human-approved diffs).
3. The agent's rule-observance (does it emit the required provenance markers, open run records, run the gate before declaring done?).

These three don't move together. A rule that requires more provenance will *decrease* perceived accuracy (more failed runs) while *increasing* rule-observance. They need to be tracked separately or the compound number is meaningless.

**Most correct** is — I think — distinct from *accurate.* I read this as "the resulting code does what the user asked, in the way they would have asked if they had time to ask." This is closer to user-acceptance signal than to gate signal, and right now there is no measurement of it on this fleet at all. Review-round counts are a weak proxy (more rounds = less correct on first try) but they only fire on work that gets reviewed, and the selection bias on which work gets reviewed is enormous. A bug that ships because nobody reviewed the file cannot be observed through round counts.

**Rules-obeyed** is the only objective with a crisp measurement today — and even that is the one the proposal admits is currently broken (the conflating of "omitted" with "emitted too often"). I'll come to its redesign.

So my first disagreement with the proposal is implicit in this section: I don't think "metric M" should be a single thing. I think the loop has to track *a vector* of metrics, and the fixer has to choose which dimension of the vector is the actual target of today's change. Otherwise the system will oscillate — fix accuracy, watch rules-observance drop; fix rule-observance, watch speed drop; fix speed, watch accuracy drop. An oscillating loop looks broken even when it's not.

**Implementation note (and how it fails):** store the metric vector as a fixed daily snapshot in append-only files (one row per day, one column per metric). Never overwrite. The most common way this kind of system silently breaks is by allowing retroactive recomputation — someone "fixes" the collector, reruns it over historical data, and now all the baselines shift, and no one can tell which fixes caused what. The ledger has to be append-only. How it fails: someone, in good faith, deletes and rewrites a corrupted day's row. Solve by writing to a file that has a daily hash recorded, and by making "edit a historical row" require the same ceremony as "change a governance surface." Cheap to enforce; expensive to skip.

---

## 2. The metric set I would actually build

I'm going to mark each proposed metric with one of three tags: **KEEP** (it is sound and we should keep it), **REPAIR** (the underlying concept is right but the current implementation is misleading and needs surgery), or **DROP/REPLACE** (the metric is doing more harm than good and should be retired).

### KEEP

**Subagent failure rate.** The 4% number from the corrected collector is legitimate, and the predicate bug (`status != "ok"` vs. the real vocabulary) was an honest bug, not a Goodhart issue. The rate is bounded between 0 and 100% and has a clear cost interpretation. KEEP.

But: split it by `task_type`. A 4% failure rate averaged over (a) simple lookups and (b) multi-hour refactors is useless. If "code-authoring" subagents fail at 12% and "lookup" subagents fail at 0.5%, the metric is hiding the failure in the expensive place. The taxonomy matters more than the rate.

**Subagent cost per task-type, in quota-equivalent units.** Cost on subscription quota is the binding constraint, and the operator has just learned (the three-account rotation story) that dollars are not the bottleneck — quota days are. So the metric has to be expressed in something that accounts for *which account* the work would have hit, weighted by that account's remaining margin. This is the only metric that directly tells the fixer "do less of X."

How it fails: any quota-tracking system is a measurement of an external system you don't control. If the provider changes their bucket model, the metric lies. Mitigation: rebase the unit on *wall-clock-equivalent at the lowest-margin account* rather than on raw tokens. Time is more stable than tokens.

**First-attempt review rounds, restricted to the ticket era.** The 3.2 number is meaningful and the 4.8 average is dishonest. The proposal already understands this and is correctly restricting to the post-2026-08-09 plan format. KEEP. But see the attribution section below — this metric is the one that is *most* vulnerable to confounders (which projects are using tickets, which reviewers, what kind of work). Without a control comparison it can drift for reasons unrelated to the fix.

### REPAIR

**Rules-compliance (36%).** The concept is essential — the operator's whole product is "do what the rules say" — but the implementation is broken in exactly the way the proposal identifies. The fix is not to count blocks, it is to count **behavioral conformance against a per-command expected sequence.** The run record is supposed to be one per command invocation. So:

- Denominator: number of *command invocations* (open run records in a day), not number of terminal blocks in transcripts.
- Compliance numerator per command: did the run record (a) open before any tool calls, (b) advance through expected phases, (c) close with the gate reporting `success`, (d) terminate with exactly one `DONE:` line and no others?

This puts the run record (which is the system of record) and the transcript (which is a by-product) in the right relationship. The current collector is consulting the by-product. That's backwards.

How this fails: a sophisticated agent could learn to write a run record that *traverses the phases* without actually doing the work — closing the record while the gate is still red, then reopening it. The fix is that the run record is opened by the platform (in the Stop hook or in a wrapper), not by the agent. If the platform opens it, the agent cannot forge conformance — it can only fail to advance it. I would audit this: trace the path from "agent types a slash command" to "run record appears in the ledger" and confirm the agent is not the one writing the open. If it is, the compliance number is gameable from day one.

**"RULES ACTIVE" present/absent.** This is currently a per-response count, which the proposal correctly flags as conflated. It should be computed against the *expected surface*: which rules are active for a file given its glob, which hooks fired, and whether the agent's response acknowledged them. A response that does not include a `RULES ACTIVE` line when files matching 14 rule-pack globs are open is one signal; the same omission when only the default pack applies is a weaker signal. Concretely: store the active-rule set per session (which is observable from the rule-pack activation logs the platform should already have), and the compliance is `(sessions where active-rule acknowledgements ≥ required acknowledgements) / (sessions that owed them)`. The "sessions that owed them" denominator is the conversation-shape filter the proposal correctly warns about — read-only turns do not owe the line.

How it fails: this depends on the rule-pack activation being itself measurable. If the rule-packs are activated by file-glob but not logged, you cannot know which rules *should have been* acknowledged. The first action might be to add activation logging. That's a one-line instrumentation fix and is a legitimate target for the first daily action.

### DROP/REPLACE

**Review rounds as the headline "review-cost" metric.** Drop it from the headline, keep it as a diagnostic. The reason: review rounds are downstream of *which work got reviewed*, and review selection is biased toward work that looked risky to begin with. A "bug fix a typo in a comment" line item gets 1 round and 0 reviews; a "redesign the auth subsystem" gets 8 rounds and 4 reviews. The average is a measure of *what got selected for review* more than of *how many rounds things take.* I'd replace it with two metrics:

- **Time-to-merge from issue-open**, restricted to issues where the agent was the proposer. This is a true cost proxy and is less selection-biased.
- **Review-round count, restricted to issues that were reviewed** — kept as the existing diagnostic, but never reported without the population it was drawn from.

How it fails: time-to-merge requires that "issue open" be observable, which on this fleet means log-able at the point the agent first creates a tracked issue. If the agent often does work without opening an issue (very common), the metric is silent on the un-tracked work. The honest move is to label the metric as "*of tracked work,*" not to overstate it.

**"Average review rounds across all projects."** Outright retire the mixed-era 4.8 number. The proposal already knows this. I'd go further: don't mix eras at all. Store the era in the row, compute per-era, never present an average that spans process changes. The 4.8 number should never reappear in any output.

### One metric I would add that is not in the current set

**The "vacuous-check rate."** Six gate checks pass while asserting nothing. The fix is to compute, for each check, a *coverage* statistic: in the last 30 days, how many of its runs were on inputs where any branch of the check could have failed? If the answer is "0," the check is vacuous. Report `vacuous_checks / total_checks` as a metric. This is the single most important number for the whole system, because *the gate is what stands between agent output and the fleet.* A gate that lies about itself is a worse failure than a gate that misses a defect.

How I would implement it: a small mutation harness. Inject 1,000 known-bad inputs across all checks (mutate a JSON record, swap a glob for one that doesn't match, etc.). Record which checks fire. Any check that fires on <1% of mutations is vacuous by definition. Run weekly, not daily — it's a heavy check. The first time you run it, you will find more than six. (You found six by reading the source. The harness finds them by behavior, which is the only way that matters.)

How it fails: a check whose failure mode is *categorical* (e.g., "expects file X to exist") may not be reachable by mutation. The harness can produce false negatives — checks that look vacuous but aren't. Mitigation: pair the harness with a *positive* check on a hand-built defect corpus ("here are 30 real defects from the last 90 days — does the gate catch each one?"). The pair is harder to game than either alone.

---

## 3. What breaks in the loop's shape after 60 days

The proposal's loop — *observe → one fix → verify → adjudicate-next-day* — is the right *spirit* but has three structural problems I don't think it has reckoned with yet.

### Problem 1: The loop has no theory of which fix to pick first

A daily queue, sorted by what metric a fix could plausibly move, sounds like a queue. It isn't, because each fix has *unknown expected effect size and unknown cost*. Over 60 days you have 60 fixes. Most won't move the metric you expected. So the loop accumulates a long tail of "tried X, didn't move M, returned with the previous diff attached" rows. That tail is itself the most valuable data the system produces, but the proposal treats it as a failure mode rather than as primary output.

I would treat the *sequence* of attempts as the unit of learning, not the individual attempt. After 14 days, you have a record of "we tried to move M, the diff sizes that worked were small, the ones that failed were large, the ones that affected rule-packs were net-negative on second-day metrics." That record, fed to the daily selector, is what eventually produces a competent prioritization. Until you have ~14 days of it, *the selector is essentially guessing.* Budget for that: the first two weeks should be expected to be unproductive, and the metric for those weeks should be "did the measurement system stay trustworthy," not "did anything move."

### Problem 2: The verifier is the same loop as the fixer, mechanically

Step 5 says "the orchestrator re-runs the gate, the corpus integrity check, and the test suite." That's necessary and not sufficient. The orchestrator is running the *same* gate the agent was supposed to run. If the fixer's diff weakened a gate check, the orchestrator running that gate won't catch it — the weakened check now passes by design.

This is the same problem you identified in the briefing: "six gate checks that reported PASS while asserting nothing." Step 5 does not address it. The orchestrator must run, *additionally*, a check whose contents the fixer cannot influence. The two practical options:

- **A frozen reference check.** A hash of the gate's source, signed at platform-install time. If the gate source is modified, the orchestrator runs the *previous* gate from an immutable copy (a worktree of the gate at commit N-1) and compares verdicts. Diverging verdicts fail the verification. Cost: one extra git check per adjudication. This means a fix that legitimately changes a gate check is *also* flagged, and a human has to bless it. That's the right asymmetry: changing the gate is a high-trust action, and the system should treat it as one.

- **A differential oracle.** A small model — even a cheap one — that, given a diff to a rule-pack or gate, scores "does this change make the check vacuous, weaker, or easier to bypass?" This is a perfect use of the metered, separately-billed model pool (the briefing notes these exist and are cheap relative to the subscription quota). Cost: a fraction of a cent per adjudication. How it fails: the oracle is a model, so it can be wrong; the fix is to log *all* of its judgements and only act on disagreements. Disagreements between the oracle and the gate's verdict are themselves a metric.

I'd take the frozen-reference check immediately, even before the oracle exists. The frozen reference is free and addresses the most acute failure mode.

### Problem 3: One change per day is too few *and* too many

This is the most important structural disagreement I have with the proposal.

It's too few because some findings are *trivial instrumentation fixes* (add a log line, fix a regex, rename a column). Routing these through the full AI-coding-agent lifecycle to "fix a regex" is wildly disproportionate — both in time and in quota. The proposal says "the binding resource is weekly AI subscription quota," and the right reflex is to keep quota for changes that *require* an LLM. A regex fix that is provably correct against a unit test does not. So I'd have a tier below the agent: a deterministic-applier path for fixes that have mechanical, verifiable forms (regex corrections, column renames when the new name is given, logging-additions where the log point is given). The verifier is the unit test. The fixer is `sed`. The agent is reserved for changes where the source-of-truth is "an instruction that requires interpretation."

It's too many because *one change per day is not a controlled experiment.* If today the metric moves 0.3 in the desired direction, you have established roughly nothing. The trend over time is what establishes causation, and one change per day gives you a daily data point that is dominated by project mix, day-of-week, even weather (some teams ship more on Mondays). I'd argue the right shape is closer to **two to three changes per week, with a beat**. The agent runs, applies a change, verifies, adjudicates next cycle. Empty cycles are fine — they should be the *expected* output of the first month, not a sign of failure. A cycle that finds nothing actionable is a successful measurement cycle.

The proposal's "one fix per day" cap is also implicitly a quota cap, which is right — but for the wrong reason (it's framed as "bounding cost," not "bounding confounds"). The right reason is: the metric signal-to-noise ratio at one fix per day is poor enough that most days you can't tell if you helped or not.

### A fourth structural concern the proposal did not raise

**The fixer doesn't know what *not* to fix.** The proposal's hard deny-list covers credentials, the rotation directory, the crontab, and another repo. It does not cover **measurement code, run-record code, the gate's invocation path, the corpus-integrity check, or the activation logic for any rule-pack.** The deny-list will grow by accretion. Worse: a future deny-list entry becomes a place to look for what the system considers load-bearing. I would derive the deny-list from a single principle — *the fixer may not edit code that defines or measures what the fixer is supposed to fix* — and let the deny-list be whatever that principle implies. This protects against a long tail of bypass attempts ("I'll just change how this specific gate check is invoked, which is in this other module that isn't on the deny-list"). The principle is the rule; the list is an implementation detail.

---

## 4. The verification problem in detail

The briefing already flagged this. It is the single highest-leverage point in the system to get wrong, because a fixer that degrades governance silently is worse than a fixer that fails loudly. I've already proposed the frozen-reference check as the core defense. Let me name the specific failure modes and the defenses against each:

**Failure mode A — vacuous checks.** Defended by the mutation harness above, run on a separate cadence (weekly). Also defended by the frozen reference, because a check that was meaningful at N-1 and became vacuous at N will be a no-op on the frozen source.

**Failure mode B — weakened rule.** A rule that originally said "must not edit files matching glob X" is changed to "should not" or "warns when." This won't be caught by the gate because the gate doesn't read rule contents at evaluation time (it evaluates outcomes). It can be caught by:

- A diff-content check on rule-packs: any rule change that *removes* a verb of obligation is flagged. Crude but cheap.
- The agent's own claim, *verified against the rule text from the previous commit* — i.e., the verifier reads the previous rule file and asserts "the fix says it strengthened X, and the previous rule file did not say X."
- The trajectory analysis: did the next 100 sessions after the fix change behave differently on the path the rule constrains? If a "must not" rule is weakened, the population of agents that violates it should rise.

**Failure mode C — tunneled fix.** A fix is described as "improved detection of issue X" but actually adds a carve-out: "do not apply when project is in Y." This narrows the rule's reach without flagging as a removal. Same defenses as above apply. Additionally: any rule-pack diff should be rendered to human-readable plain language and diffed against itself in plain English. The verifier should fail any diff whose plain-English rendering changed in meaning from "this rule still applies broadly" to "this rule applies narrowly." This sounds silly but is effective — text embeddings and even simple *character overlap* on the rendered English catches "should not edit" → "should not normally edit" reliably.

**Failure mode D — passing the verifier with a fake-green commit.** The agent's commit "passes the gate" because it actually suppressed the gate (added `2>/dev/null`, set an env var the gate respects, edited a fixture to make the test pass). Defense: the verifier runs the gate from a known-clean invocation — *no inherited env from the worktree beyond a fixed allowlist, no fixture files reachable from the working tree unless explicitly required.* Treat the gate invocation as adversarial. This is the standard practice in CI security; it's under-applied here.

**Failure mode E — collusion between measurement and target.** Even with a deny-list on measurement code, the agent could change an *input* that the measurement reads. If the measurement reads run records, and the agent causes run records to be created differently, the metric moves with the agent's cooperation, not with the world. Defense: trend metrics across multiple input sources. If "open run records per day" and "command invocations observed via prompt-router logs per day" both move, you have a real movement. If only one moves, suspect the input channel.

None of these defenses are exotic. What's exotic — and the proposal is correct to worry about — is that *all of them have to be in place at once.* A defense-in-depth that misses one layer will be exploited at that layer within weeks.

---

## 5. Attribution under drift

This is the second-place disagreement with the proposal, and a deep one.

The proposal's model is: "change X, measure M tomorrow, expect to see M move." With one change per day, the metric tomorrow is dominated by:

1. **Task mix.** A fleet of 46 projects varies day to day in which projects are active. If today's fix is to `fabrik-review`, but tomorrow only one project runs `fabrik-review` and it happens to be a difficult ticket, the metric reflects the ticket, not the fix.
2. **Agent rotation.** Three concurrent sessions, quota-rotated, model-rotated — same task behaves differently on different models. A daily metric is partly a model-allocation artifact.
3. **Day-of-week and human-presence effects.** (You'd be surprised, but the operator's own usage pattern will show in the data.)
4. **The fix itself changing the composition of measured sessions.** If you add a rule, agents that previously failed-fast now run longer. The *duration* metric moves, but it's a movement of the population, not of the underlying behavior.

The honest experimental design under these conditions is one of three:

**Option A — matched pairs (cupid shuffle).** For each change, identify *the population of sessions to which it applies* (e.g., "sessions editing files matching rule-pack X") and compare like-for-like: a 7-day window before vs. a 7-day window after, with same-day-of-week alignment. If the after window is consistently better, you have a signal even if individual days are noisy.

**Option B — synthetic control.** Pick a small number (3-5) of projects that look comparable, apply the fix to a random subset, hold out the others. After N weeks, difference-in-differences. This is the gold standard. It costs you half the daily fix budget (you'd only deploy to half the fleet at a time). It also forces an explicit decision about the unit of randomization, which the current proposal lacks.

**Option C — hold back.** Apply no fix on most days, accumulate a baseline, and only deploy fixes that have a defensible expected-effect direction. Days with no deployment are *not failures.* This is the proposal's null hypothesis run in slow motion, and is probably the right move for the first month.

I would *not* recommend A or B at first; I'd start with C and only move to A once there's a 30-day baseline. The reason: A and B require fixed categorizations of "what kind of session is this," and you don't have a stable session taxonomy yet (see my point about "fastest" requiring a task taxonomy). Until you have the taxonomy, matched-pair analysis is matching on the wrong axis.

The strongest signal in this system is not "did M move tomorrow" — it's "did M move *across the right sessions* and not across the wrong ones." If a fix targets rule-pack X and the metric moves only on sessions that don't touch rule-pack X, you deployed a placebo or a side-effect. If it moves on both, you probably changed something broader than intended. *Spatial* attribution (which subpopulation moved) is more diagnostic than *temporal* attribution (did it move the next day).

Practically: every daily adjudication should report, in addition to "did M move," the *correlation between target-population and observation.* If the correlation is low, that's a stronger signal than "did it move" — it tells you the fix is operating by the wrong mechanism.

---

## 6. What a human should still see

The operator wants out of the loop but not blind. The right minimal signal surface is small and event-driven, not periodic:

- **Daily: one line.** A single-line summary of the day's decision: "deployed fix X to file Y, expected Z, verifier verdict PASS/FAIL." No more. The operator should be able to read it in five seconds and ignore it on most days.

- **Weekly: a metric-vector snapshot.** Four to seven numbers from the metric vector, each with a 7-day delta and a 30-day delta. No interpretations, no recommendations. The operator reads the numbers, sees if anything is at a boundary he's set for himself (e.g., compliance <50%, or subagent failure >10%), and acts only then.

- **Event-driven, not periodic: every time the loop escalates.** Three failed attempts on one finding, a frozen-reference divergence, a vacuous-check rate that crosses some threshold, a quota-spent alarm, any time the loop *cannot proceed without a decision.* This is the only signal class that requires the operator to be reachable. The escalation surface should have *one* channel: a single notification mechanism that the operator knows means "stop and decide." Don't expand it. Every channel you add becomes noise the operator learns to ignore.

- **Monthly: a structural review.** Read the deny-list, read the metric definitions, read the verifier's recent false positives and negatives. The system changes its own operating environment; the operator reviews its operating environment, not its outputs.

The minimum signal is closer to "the loop is healthy" than to "the loop is producing fixes." A loop that produced zero fixes in a month but kept its measurement clean and its gate trustworthy has done its job. The operator's signal surface should report that *as healthy,* not as idle.

What must reach him in an emergency: only changes to a class the platform defines as "load-bearing for trust" (the gate, the run-record platform code, the corpus integrity check, the credential rotation). He should approve every such change *before* it merges, not after. This is one extra review per N weeks, on average — small enough to be tolerable, large enough to be a meaningful filter on adversarial or degrading fixes. (And I would not delegate that final human review to the AI on the argument that "it would have caught it.")

---

## 7. What is not being thought about at all

Six things, in roughly descending order of how much damage they will do if missed.

**a. The loop has no model of its own operating cost.** Each cycle burns quota (subscription model time) and cents (metered API), and applies CPU to verification. "Daily" as a fixed cadence conflates "we should do this often" with "we should do this every day." I would track *operating cost per successful verified movement of any metric,* and have a fallback to "skip today because yesterday's verification cost exceeded this week's budget." The fallback is itself a metric. The loop should be allowed to say "nothing to do today."

**b. The three concurrent agents are themselves a metric source.** Session transcripts are being read for one of the three at a time, with no clear policy. Sessions are not a clean unit of measurement when three of them share a working tree: a file edited in session A and committed by session B belongs to neither's transcript in a measurable way. The first measurement should *not* be "what did session X do" but "what files changed, and which sessions touched them, and in what order." File-centric view first, session-centric view derived from it. Otherwise the collector is reading partial stories.

**c. The "single working tree" creates a stronger rule than the deny-list.** Even a *legitimate* fix that adds new files to the working tree can collide with a peer's in-flight edit. The proposal says "use a worktree." But the verifier still has to merge the change *back* into the shared tree, and the merge is racy. The proposal needs to specify: who resolves a conflict, in what order, with what precedence? The safest rule is "the fixer merges only during a quiet window" — and the loop has no way to detect a quiet window, because it can't see what the agents are doing in real time. **Recommendation:** the fixer's merge cadence should be *something the agents know about and yield to,* not a thing it grabs opportunistically. A simple announcement file — touched by the fixer at merge time and present in the shared tree — tells the agents "delay any new commits by 60 seconds, the platform is merging." Agents are already instructed to avoid contention; the signal has to actually be there for the instruction to be effective.

**d. Governance propagation is itself a measurement surface.** The proposal describes ~46 repos receiving updates from a single synced surface. The metric "did the rule move" is also "did it arrive at all 46 repos correctly?" Synced surfaces can drift — a clone that failed a sync step, a repo with a conflicting local change, a credential issue that quietly skipped three of them. **Add a propagation-fidelity metric:** of N governed surface changes in the last 30 days, how many arrived at all 46 repos within the expected window? If propagation is broken, the whole loop is operating on inconsistent input. This metric is essentially free to compute (it's a `git` query per repo per day) and catches a class of failures nobody is looking for.

**e. Rule-pack activation is unobservable.** Rule-packs are activated by file-glob match. The proposal says agents should "acknowledge" them, but does not say the platform *knows which were activated.* The compliance measurement section above depends on this, and it may not exist. This is the very first thing I would verify and, if missing, the very first thing I would add. Until you know which rules were active in a given session, you cannot measure rule-observance — you can only measure some weaker correlate.

**f. The system has no concept of permanent regression.** A fix that initially moves a metric in the desired direction, then slowly drifts back as agents find workarounds over weeks, has produced a net-negative change with a positive-shaped metric trajectory in the short term. The loop adjudicates *next day.* It never adjudicates *next month.* **Long-arc adjudication** (re-measure the same metric 14 and 30 days after deployment; require stability across all three timepoints before declaring a fix "real") is what separates durable improvement from Goodhart theater. This costs almost nothing extra — it's a delayed re-read of the same ledger rows — but it changes the meaning of every daily decision. Without it, you will accumulate "fixes" that look real on day 2 and have evaporated by day 30, and the loop will never notice.

There's a seventh issue but I'll mention it briefly rather than develop it: **the run-record lifecycle is also a place the platform can be made more robust.** Specifically, the platform (not the agent) should be the one closing the run record at the gate's `success` verdict. Right now, the run record appears to terminate on agent-asserted completion. I would treat run-record closure as a gate-controlled event, not an agent-asserted event. If it isn't already so, changing it is a one-day mechanical change and would substantially reduce the conformance game's surface.

---

## 8. A revised loop, summarized

Pulling the threads together, the loop I would build is:

1. **Daily measurement.** Append a row to the ledger. Use the metric vector (8-10 metrics), not a single number. Use the *file-centric* view first. The row is append-only, never recomputed.
2. **Daily selection.** From the vector, pick *at most one* finding where (a) the expected mechanism is explicit, (b) the fix is either mechanical (deterministic-applier path) or an LLM task, and (c) the population attribution is plausible (target subpopulation is identifiable). If nothing clears the bar, do nothing for the day. Record that.
3. **Apply.** Two paths. Mechanical fixes are applied by a deterministic tool with a unit test as the verifier. LLM fixes are applied in an isolated worktree by a headless session that receives an evidence dossier, not an instruction.
4. **Verify in-worktree.** Run the gate from a frozen reference; run the corpus-integrity check; run a text-oracle on rule-pack diffs; require all four checks (gate, frozen gate, corpus, oracle) to agree before a change is mergeable.
5. **Merge on quiet windows,** announced via a marker file.
6. **Day-1 adjudication:** next cycle, re-measure. Was the relevant population's metric moved?
7. **Day-14 and day-30 re-adjudication:** stability must hold. If it doesn't, the "fix" is reverted (the system has reverts as ordinary commits, which the proposal already supports).
8. **Escalation triggers:** 3 failed attempts, frozen-reference divergence, vacuous-check threshold crossed, propagation-fidelity drop, quota-spent alarm — *any* of these halts the loop and pages the operator.

This is roughly the proposal's loop with five structural changes: tier the fix path (mechanical vs. LLM); change the cadence from daily-fixed to rate-limited-with-skip; add long-arc adjudication; add propagation fidelity and rule-activation observability as prerequisites; use a frozen-reference check in verification.

### A closing observation

The proposal's biggest single risk isn't measurement, isn't the agent, isn't the gate. It's the temptation, after three weeks of running, to *trust the loop.* A loop that has produced nine successful fixes and zero failures is a loop that has produced nine fixes — not nine proven improvements. The system has to be designed assuming every fix is wrong until long-arc adjudication confirms otherwise. That's not a hostile framing; it's the only framing under which the measurement code, the gate, and the verifier stay sharp. If the loop is ever told "the user trusts us now," it will optimize for the trust, not for the truth. Build it so trust doesn't enter the decision.

That, more than anything, is what I would change about the proposal as written.



---

## FUSION SYNTHESIS (wave 2)

# Reconciled Verdict

## The consensus (all four, with high confidence)

**Do not ship the proposed daily actor as specified. Ship its instruments first, its proving ground second, and the actor last — in human-approve-everything mode.** Every panelist independently reached this conclusion despite different framings. The loop's *shape* (evidence dossier → isolated worktree → independent verification → pre-registered hypothesis → adjudication → escalation) is endorsed by all four and should be kept. What is rejected is the combination of **daily cadence + global blast radius + "green gate" as oracle + next-day adjudication**.

Eight points of unanimous agreement:

1. **The gate cannot verify changes to the gate.** Six vacuous checks out of 57 is the warning shot; assume ~10% of enforcement is theater until proven. Every blocking check needs a known-bad fixture that must fail, checked continuously (mutation testing / seeded defects / assertion traces).
2. **Next-day metric movement is not causal evidence.** Confounded by project mix, task mix, model/account rotation, session volume swing (16→91), plan era, and n≈12 samples. Next-day movement is legitimate only as a **rollback tripwire**, never as a success verdict.
3. **The actor must not be able to edit its own judge.** Plane separation: artifacts that *shape* behavior are fair game; artifacts that *measure or block* (gate, hooks, run records, collector, adjudicator, sync, deny-list, the actor's own halt conditions) are not autonomously editable.
4. **A deny-list is insufficient.** Needs a fail-closed policy engine over diff paths, allow-listed writes, no push rights for the fixer (the orchestrator merges), and OS-level separation where possible.
5. **The 36% compliance scalar is junk as computed** — it conflates omission, terminator spam, wrong denominators, and parser bugs. Split into a vector; **use run records, not transcript regexes, as the denominator**. Retire the mixed-era 4.8 review-rounds figure. Sessions/day and cost/day are context, not targets.
6. **Every accelerator metric needs a brake metric.** No single composite objective. Speed, gate-pass, review rounds, and subagent success are all trivially gameable by doing less work or weakening checks.
7. **"No change today" must be a first-class success state**, and the shared dirty working tree is a structural hazard that the fixer's worktree mitigates for the fixer but not for the fleet.
8. **Instruments before behaviors; exception-driven human interface** (push only for escalations/tripwires/instrument failures; pull for a weekly digest), with human sign-off reserved for anything that weakens enforcement or redefines a metric.

## Genuine contradictions, and how I rule

| Issue | Split | Ruling |
|---|---|---|
| **May the fixer ever touch measurement code?** | E1 and E3: absolute ban (Plane 2, no exceptions). E2: explicitly rejects the ban — you already found two collector bugs, so a safe path must exist. E4: principled ban, yet proposes adding rule-activation logging as an early action. | **E2 wins on substance, E1/E3 on mechanism.** The ban is on *autonomous merge*, not on change. Route measurement changes through a separate metrology pipeline: golden datasets, dual-run `metric_v1`/`metric_v2` for 7–14 days, metric versions frozen for the duration of any active experiment, human sign-off on definition changes. An absolute ban makes a broken instrument permanently broken. |
| **Canary rings now, or baseline first?** | E1/E2/E3: cohort channels are the highest-leverage investment; E3 offers a free v0 (hub-as-canary, ship to hub → adjudicate hub-vs-fleet → sync). E4: explicitly argues *against* matched-pair/synthetic-control designs first, because there is no stable task taxonomy to match on. | **Both, because they answer different questions.** Channels are primarily *blast-radius containment* and secondarily coarse difference-in-differences — neither requires a taxonomy, since day, model-rotation, and mix effects hit both cohorts and cancel. E4's objection lands only against fine-grained stratified matching, which should indeed wait. Do E3's hub-first v0 this week. |
| **Cadence** | E1: risk-based, not date-based. E2: three loops at different cadences. E3: daily detection, queue-driven dispatch above an expected-value bar, cap of 3–4 open hypotheses, ≤1 per metric family. E4: 2–3 changes/week, plus a first month of near-total hold-back. | **E3's formulation supersedes the others**: the calendar is a proxy for the real constraint, which is *one open hypothesis per metric family and a bounded total*. Daily detection satisfies the operator's "daily, not weekly." Dispatch frequency is an output, not a setting. E4's hold-back month is correct in effect — early on the EV bar will rarely clear. |
| **Review rounds** | E1/E2/E3: keep, era-stratified, with n attached and guard metrics. E4: demote from headline entirely — round counts measure *which work got selected for review*, not how many rounds work takes. | **E4's selection-bias argument is the sharpest and is under-weighted by the others.** Keep review rounds as a diagnostic only; never as an adjudication target until the selection mechanism is characterized. |
| **North star** | E2: a single strategic metric (Validated Autonomous Task Rate — completions that survive 7–14 days). E1: reluctant composite with hard vetoes. E3/E4: refuse a scalar; use a vector. | **Adopt E2's construct as a strategic, non-control metric.** It is the same object as E1's north star and E3/E4's rework/escape metric: *did the work survive contact with reality*. It reports; it never drives daily selection. |

## Partial coverage worth adopting (single-source insights)

- **E3 — governance bloat as a self-reinforcing failure.** Every fix adds text; the enforcer is an attention-limited reader; aggregate compliance falls as the rulebook grows, which the loop then "fixes" by adding more text. No term in the proposal opposes this. Remedies: net-zero governance token budget, prefer-edit-over-add as a dispatch constraint, **deletion as a first-class finding class** (dead rule packs, never-invoked commands, never-firing checks). Also E3 alone: daily governance pushes invalidate every session's **prompt cache prefix** — a direct quota tax.
- **E3 — a holdout metric the fixer never sees.** A weekly metered-model rubric audit on a stratified transcript sample, excluded from all dossiers and selection. This is the only proposed detector for fleet-wide Goodharting; nothing inside the optimized metric set can catch it.
- **E4 — long-arc adjudication.** Re-measure confirmed fixes at day 14 and day 30; revert if the effect evaporated. Nobody else re-checks *confirmed* fixes for durability, which is exactly where workaround-driven decay shows up.
- **E4 — spatial attribution.** Ask whether the metric moved *in the targeted subpopulation and not elsewhere*. More diagnostic than temporal movement; catches placebos and over-broad changes.
- **E4 — run-record integrity and rule-activation observability.** If the *agent* opens/closes the run record, conformance is forgeable and the whole compliance rebuild rests on sand; the platform must own record lifecycle. And rule-pack activation may not be logged *at all* today — verify before measuring it. E1/E2 both specify activation precision/recall while assuming this data exists.
- **E4 — append-only metric ledger.** Never retroactively recompute history; a good-faith collector "fix" reruns over the past, shifts every baseline, and destroys all attribution.
- **E4 — a deterministic fix tier.** Regex corrections, renames, log-point additions do not need an LLM: `sed` plus a unit test. Preserves quota for changes that genuinely require interpretation.
- **E1/E3 — the dossier is a privilege-escalation channel.** Transcript content flows into commits governing 46 repos; treat all evidence as untrusted quoted data. E2 and E4 are silent on this.
- **E3 — an escalation budget (≤2/week) after which the loop slows itself.** The only mechanism that protects the human interface from becoming the bottleneck E1/E2's rich approval queues would create.
- **E3 — the fixer's run record and Stop hook may be keyed to the wrong tree**, spinning until quota death. Check before trusting worktree isolation.
- **E1/E2 — a red-team function** that periodically tries to sneak bad changes through in a sandbox. E3/E4 omit it.

## Shared blind spots

1. **Nobody seriously questions the premise.** Four panelists prescribe a proving ground, metrology pipeline, experiment registry, canary channels, dependency graph, red team, and audit ledger — collectively far more machinery than the actor itself — for a one-operator, $0.74/day, ~50-session/day system with 203 governance artifacts. **Not one asks whether the defect is the platform's size**, or costs out who maintains the meta-platform when it breaks. E3's bloat budget is the closest anyone comes, and it's aimed at the rulebook, not at the remedy.
2. **Operator sustainability.** All four hand over multi-phase programs (5 phases, 7 phases, 4 weeks, a hold-back month). None asks whether a single operator finishes Phase 1, or specifies the **safe degraded configuration if the program stalls half-built** — which is the most likely outcome and strictly worse than either endpoint if autonomous merge is on.
3. **Model non-stationarity as an existential threat to the program.** E1 and E3 mention stratifying by model/account. Nobody notes that a model upgrade every few months may reset all baselines and silently obsolete a large fraction of accumulated rule-text micro-fixes — a strong argument against investing 60 days in prompt/rule tuning versus state-based enforcement.
4. **The human is the single point of failure in all four designs.** Every high-risk path terminates in approval from an operator who has explicitly asked to be out of the loop. Only E2 specifies a default (deny after 48h). None models the steady state where the queue goes unread for three months — permanent default-deny is a frozen platform, not a safe one.
5. **On a single-user box, every control is advisory.** E1 concedes this in passing and then everyone keeps designing permissions. The real protections are blast-radius limits, reversibility, exercised reverts, and off-box backups — those should be *primary*, not supplementary.
6. **No stopping condition for the loop itself.** All four assume perpetual daily operation. None defines when the platform is good enough to reduce the loop to weekly or turn it off.
7. **21 cron jobs × 3 live agents.** Treated only as "monitor, don't edit." No lock hierarchy, no global mutex, no interaction analysis.
8. **Nobody estimates the loop's expected value.** What is compliance 36%→80% worth in delivered software, versus spending that quota on project work? E3's quarterly outcome-correlation check is the only nod, and it's a tripwire rather than a business case.

## The synthesized order of work

**Week 1 — instruments:** schema contracts with enumerated vocabularies, plausible-range invariants, golden transcript corpus, append-only metric ledger, seeded-defect fixture per blocking check (expect to quarantine more than six), vacuous-check rate as a headline number.
**Week 2 — denominators:** platform-owned run-record lifecycle; verify rule-activation logging exists; compliance scalar split into a vector defined on records; minimum-n suppression rendered into every downstream consumer including dossiers.
**Week 3 — adjudication before actor:** rolling 28-day baselines with MAD, binding pre-registration YAML, persistence requirement, hub-as-canary v0, tripwire metrics, long-arc (day-14/30) re-check, spatial attribution.
**Week 4 — actor pilot, human-approves-everything,** mechanical fix tier first, fail-closed policy engine enforced from day one, deletion findings included, net-zero token budget, off-box append-only fix ledger. Loosen to auto-merge only for canary-first, behavior-shaping, strictly-additive-or-subtractive changes, after ~10 clean cycles.

And one addition the panel did not make: **before any of this, spend a day asking whether 203 artifacts and 57 checks should become 60 and 20.** Deletion is the cheapest fix class, the only one that shrinks the attack surface, and the only one that makes every subsequent phase smaller.



---

## google/gemini-3.1-pro-preview

As an independent consultant, I have reviewed the current state, the constraints, and the proposed daily loop. 

Here is my direct judgement: **The vision is correct, but the proposed "Actor" loop will slowly destroy your platform.** 

If you run the proposed system for 60 days, you will experience **Prompt/Rule Bloat** leading to context-window exhaustion, and **Governance Collapse** where the AI silently weakens constraints to make its own life easier. Furthermore, a strict 24-hour adjudication cycle will fail because fleet activity is too noisy to attribute causality in a single day.

Here is a tear-down of the proposed design and a fundamentally better shape for the system.

---

### 1. The Loop’s Shape & The "60-Day" Failure Mode
**The proposed shape:** Observe → Fix → Verify (CI/Tests) → Push to 46 repos → Adjudicate next day.

**The fatal flaw:** AI models are additive, not subtractive. When faced with an edge-case failure, an AI will append a new rule, add a new conditional to a gate, or insert another command fragment. Over 60 days, your 56 rule packs will become massive, contradictory, and hyper-specific to past anomalies. Agent context windows will choke on governance overhead, slowing down the actual coding and driving up quota usage.

**The second flaw:** "Adjudicate next day" assumes the platform will see the *exact same type of work* tomorrow to prove the fix. If the AI fixes a Python parsing rule on Tuesday, but Wednesday's agents only write CSS, the metric won't move. Reverting it on Thursday because the metric "didn't move" creates thrash. Adjudication must be based on *event volume* ($N$ executions of the rule), not a 24-hour clock.

**The Better Shape (The Replay Loop):**
Do not test hypotheses on the live fleet. You have 8.2 GB of transcripts. 
1. **Observe:** Find a failure.
2. **Hypothesize & Fix:** The Fixer creates the isolated worktree and patches the infrastructure.
3. **Replay (Shadow Mode):** *Do not merge yet.* Use the cheap API models (which don't consume your binding subscription quota) to replay the exact 5 historical session turns that failed yesterday, but using the *new* infrastructure. 
4. **Adjudicate Instantly:** Did the API model succeed where yesterday's agent failed? 
5. **Merge & Push:** If the replay passes, push to the fleet. The "adjudication" is done before the fleet ever sees it.

### 2. The Verification Problem (Preventing Governance Collapse)
**The problem:** You noted the platform already found gates that reported PASS while asserting nothing. If you tell an AI "Fix the infrastructure so agents stop failing the gate," the mathematically easiest solution for the AI is to *delete or weaken the gate*. CI and test suites will pass because the code isn't broken; the *governance* is broken.

**The Solution: Mutation Testing & The "Vault of Shame"**
You cannot verify governance by checking if it is "green." You verify governance by proving it goes "red" when it should.
*   **Implementation:** You must build a `vault/` of known-bad commits and transcripts (e.g., a commit with missing provenance trailers, a transcript where an agent ended a turn early). 
*   Whenever the Fixer modifies a Gate, Rule, or Hook, the orchestrator runs the *new* governance against the *Vault of Shame*. 
*   If the new infrastructure allows a known-bad commit to pass, the Fixer has weakened the system. The worktree is destroyed, the attempt fails, and a strike is recorded.

### 3. What to Actually Measure (Escaping Goodhart's Law)
Your current metrics are confounded by wrong denominators. "Rules obeyed" is a terrible metric because agents will optimize for the appearance of compliance (e.g., printing the terminator block 36 times).

Throw away basic compliance counters and measure the **Friction** and the **Yield**.

*   **Metric 1: First-Pass Yield (FPY) per task.** Did the agent reach a terminal state without the Stop Hook firing once? If the Stop Hook fires, the governance caught a failure, but the *infrastructure failed to guide the agent correctly*. FPY is immune to Goodharting because the agent doesn't know it's being measured on it.
*   **Metric 2: Mean Rounds to Green (MRTG).** How many times did `final_gate.py` run before returning `"success"` in a single session? If this number trends up, agents are struggling with your gates.
*   **Metric 3: Infrastructure-to-Code Token Ratio.** (Using the subagent ledger). How much of the context window is consumed by your 203 artifacts vs. the actual project code? If this climbs, Rule Bloat is happening.

*Rule for Denominators:* Never use "total sessions" or "total turns." The denominator must be "Turns where Rule X was triggered by file-glob."

### 4. Attribution (Causality in a Noisy Fleet)
You cannot establish that a change caused a movement by looking at a daily global average across 46 wildly different projects. 

**The Counter-Design: Artifact-Level ELO Scoring.**
Stop tracking global averages. Track the "win rate" of *specific infrastructure artifacts*. 
*   If Rule Pack A is invoked, does the turn succeed? 
*   If the Fixer modifies Rule Pack A, you only measure the success rate of sessions that *actually triggered Rule Pack A* after the fix. 
*   This removes the noise of the 45 projects that didn't touch that rule. If the local success rate of the artifact improves with statistical significance (e.g., $N > 20$ invocations), the fix is confirmed.

### 5. Quota Arbitrage (The Unseen Leverage)
You noted that your binding constraint is the *weekly AI subscription quota* (which 3 agents share and exhaust), but *metered API models are separate and cheap*.

**You are currently proposing using your precious subscription quota to fix the platform.** Do not do this.
*   The Daily Collector, the Hypothesis Generator, the Dossier Builder, and the Headless Fixer should **exclusively use the metered API** (e.g., Claude 3.5 Sonnet / GPT-4o API). 
*   Keep the subscription quota 100% dedicated to the human's 46 projects. 
*   This also ensures the "Fixer" AI has a slightly different system prompt and operational environment than the "Worker" AI, preventing shared blind spots.

### 6. What the Human Must See
The operator wants no dashboards and zero manual intervention unless necessary.

**The Notification Model: The "Intervention Ledger"**
Send exactly one plain-text digest to the operator's terminal/log upon login, formatted strictly as past-tense actions and alarms:

```text
[SYSTEM KAIZEN - 2026-08-11]
- PROMOTED: Updated /fabrik-spec/python_rules.md. 
  Reason: MRTG was 4.2. Replay shadow-test improved to 1.1.
- ROLLED BACK: Gate check 12 modification. 
  Reason: Failed Vault of Shame test (allowed unsigned commit).
- WARNING: /fabrik-review/auth_rules.md has not been triggered in 45 days. Candidate for deletion.
```

**When to Hard-Stop and Escalate (The Circuit Breakers):**
The loop must halt and demand human input if:
1.  **3 consecutive Vault of Shame failures.** (The AI is trying to weaken governance and cannot figure out how to satisfy it).
2.  **Infrastructure Token Ratio exceeds X%.** (The AI has bloated the prompt to the point of endangering the context window).
3.  **A fix results in a Pre-Commit Sync failure.** (If a fix breaks the fleet's ability to sync, the shared working tree will instantly fracture. This is a fatal platform error).

### Summary of Recommendations

To make this machinery safe and effective, change your proposal to include:
1.  **A Shadow-Replay step** using cheap API models to validate fixes against yesterday's failing transcripts *before* merging.
2.  **A "Vault of Shame"** (mutation testing) that the new infrastructure must correctly block, preventing the AI from secretly weakening gates.
3.  **Measurement of Friction (First-Pass Yield)** rather than raw rule compliance.
4.  **An automated rule-deletion protocol** to fight the inevitable 60-day rule bloat.



---

## claude-fable-5

This brief is complete and self-contained, so I'll answer directly with my own judgement rather than gathering more context. The short version first, then the six questions in depth.

**TL;DR of my position:** The measurement half is now pointed at the right data, and the actor's mechanics (worktree isolation, independent verification, merge-on-green, deny-list) are sound. But the loop's central epistemic commitment — *"nothing counts as fixed until the number moves, adjudicated next day"* — is statistically unworkable at your traffic volume and will cause the loop to thrash: correct fixes will be declared failures and re-attempted on top of themselves. The fix is to split verification into two tiers (deterministic proof-of-fix at merge time; statistical trend-tracking at portfolio level), to move most evaluation from "wait for tomorrow" to "replay yesterday," and to exploit the one experimental asset you have and are ignoring — 46 parallel repos that permit split-fleet rollouts. Separately, the design has no counter-force to governance accumulation, and after 60 days that ratchet is the failure mode I'd bet on.

---

## 1. Is the loop's shape right?

The shape — observe → one fix → verify → adjudicate-next-day — is right in spirit and wrong in two load-bearing places.

### 1a. Next-day adjudication assumes signal that does not exist

You have 16–91 sessions/day, spread across up to 46 heterogeneous projects, doing heterogeneous tasks, and (per §4) with denominators you don't yet trust. Consider what "the metric moved" means at that n. Say a fix targets rules-compliance in one project that sees 3 sessions on a given day. The day-over-day variance of a 3-sample proportion swamps any plausible effect size. Even fleet-wide, a real 5-point improvement in a ~36% compliance rate needs on the order of a thousand observations per arm to distinguish from noise — that's *weeks* of traffic, not a day. And review-rounds-per-ticket, your best outcome metric, accrues at ~1.5 ledgers/day fleet-wide.

So the adjudicator will routinely deliver false verdicts in both directions, and the false negatives are the dangerous ones. Trace the mechanism: a correct fix merges Monday; Tuesday the target project happens to get two conversational sessions and the metric doesn't budge; the finding "returns with the previous attempt's diff attached"; a second headless session, told the first attempt failed, makes a *stronger* intervention on top of a correct one — tightens a rule further, adds a gate check, hardens a hook. Three rounds of this and you've over-tightened a governance surface that syncs to 46 repos, because the loop punished a fix for the crime of being measured too soon. **The retry-with-diff-attached mechanism converts measurement noise into governance escalation.** That is my candidate for "the failure mode nobody sees coming."

The repair is to stop conflating two different claims:

- **"The change is correct"** — the defect existed, the change removes it, nothing else broke. This is *deterministically verifiable at merge time* for most of your surface. A wrong path in a command file, a vacuous gate check, a hook that fires on the wrong condition, a regex that matched a data table — every one of these can be expressed as a reproducible check: demonstrate the defect against the old code (a failing fixture), demonstrate its absence against the new (the fixture passes), run the full gate. This is just TDD applied to infrastructure, and it should be the *merge criterion*. If a finding cannot be expressed as a reproducible before/after check, it is not ready to be acted on — send it back to the collector for sharpening, don't dispatch a fixer at it.
- **"The change improved fleet behaviour"** — a statistical claim about a noisy, drifting time series. Track it, but at the portfolio level over 7–14 day windows with change-point detection (CUSUM is fine), not as a per-change next-day verdict. A hypothesis whose metric hasn't moved after two weeks *and* whose deterministic verification still holds should be closed as "correct but low-impact," not "failed" — that's a prioritization lesson, not a defect in the fix.

Keep the hypothesis record (§5 item 7) — it's the best idea in the actor design — but change what a non-movement means: it demotes the *finding class* in future prioritization; it does not trigger a re-attempt on a deterministically-verified fix.

### 1b. One-change-per-day is the wrong knob

It's motivated entirely by attribution, and since next-day attribution is mostly illusory anyway (above), it buys little while costing a lot: your finding backlog grows at collector speed (dozens per sweep) and drains at 1/day, so within 60 days the queue is hundreds deep and the *selection policy* — which the proposal doesn't specify at all — becomes the actual system. See §6.

Better partition: **provably-correct fixes flow at whatever rate deterministic verification supports** (they need no experimental slot — a fixed wrong path doesn't need a metric to move), while **behavioral hypotheses** — prompt wording changes, rule-text changes intended to alter *model behaviour* rather than fix a mechanical defect — are capped at one or two *concurrently active experiments*, each with a proper multi-week window and, ideally, a split-fleet design (§4). One-per-day is neither necessary for the first class nor sufficient for the second.

### 1c. What breaks at 60 days: the ratchet

Every fix in this design's vocabulary *adds*: a rule, a gate check, a hook condition, a required line. Nothing in the loop ever removes anything. After 60 days you have more of the 56 rule packs, more than 57 gate checks, more required boilerplate per response — which means more injected context per session, slower sessions, more surface for agents to violate, therefore *worse* measured compliance, which the loop treats as more findings, which produce more rules. The loop's own output degrades the metric it optimizes, and it responds by producing more output. This positive feedback is slow enough that nobody notices it week to week.

Counter-design, concretely:

- Make **governance mass** a first-class metric: total tokens of rules/fragments injected into a median session, gate wall-clock time, count of active checks. Its growth trend is a defect the collector reports like any other.
- Make **deletion a finding type**: the dispatch ledger and transcripts can tell you which of the 56 rule packs *ever activate*, which commands are never invoked, which gate checks have never failed in 60 days across 46 repos (a check that never fires is either vacuous — see Q3 — or enforcing something the fleet has fully internalized; either way it's a candidate for the mutation-corpus test or removal). Dead governance is pure context-window cost.
- Budget rule: a fix that adds a gate check or rule text above some size must name what it retires, or explicitly record "net addition" in its hypothesis — so the ratchet is at least visible.

---

## 2. What should actually be measured

Judging yours first:

- **Rules-compliance (36%)** — junk *as constituted*, and you know it (§4.1). But the underlying signal is good once split. Do the split by changing the denominator source: stop regexing transcripts for the block and instead join transcripts to **run records**, which you built precisely to know when a run is open and when it terminates. Then you get three clean metrics: (a) *terminator emitted exactly once per completed run* (binary, per run — clean denominator); (b) *runs that completed without the required line* (violation); (c) *terminator emissions mid-run* (the distinct forbidden mode — count per run). A metric with a run-record denominator is also far harder to Goodhart than a regex over free text.
- **Review rounds per ticket (3.2, ticket-era)** — your best outcome metric, and your own spine-vs-ticket finding proves it can detect real process changes. Keep it, ticket-era only, and accept n will be small for weeks. It is Goodhart-vulnerable in an ugly way: rounds go down if reviews get lazier. It must be paired (see below).
- **Subagent failure rate / latency / cost** — fine as a health floor; low information for driving fixes. Don't let it occupy a daily dispatch slot.
- **Mixed-era averages** — you already learned this one: segment by regime or don't report.

The set I would build, organized by what the operator actually asked for:

**Correct (the north star cluster — measures outcomes, hardest to game):**
1. **First-attempt gate pass rate** per session — did the agent's work pass `final_gate` on the first try? Every session that runs the gate contributes; denominator is clean; it directly measures "correct by default," which is the operator's stated product.
2. **Rework rate**: commits that revert or re-touch the same files as an AI commit within N days, fleet-wide, via the provenance trailers you already stamp. This is "escaped defects" without needing anyone to file a bug.
3. **Review rounds per ticket** (ticket-era), *paired with* rework rate — rounds may only count as improved if rework didn't rise.

**Rules-obeyed (measures the enforcement machinery):**
4. **Stop-hook interventions per session** — how often did the hook have to block an early turn-end? This is the purest "agent tried to break a rule and machinery caught it" signal, with a perfect denominator (the hook sees every turn-end).
5. The split compliance triple from above.

**Fastest (measure the binding resource, not wall-clock vanity):**
6. **Quota per completed ticket** (or per closed run record), by task type. Your binding resource is subscription quota (§6); a "faster" infrastructure is one that closes the same work in fewer tokens/turns. Wall-clock p50 to run-record close is the secondary.
7. **Gate wall-clock time** — the tax every session pays, 42 checks deep and growing.

**Instrument health (the meta-metric your kaizen failure demands):**
8. Collector coverage (% of the day's transcripts successfully parsed — a parse-failure spike is how the *next* `status != "ok"` bug announces itself), plus fixture self-tests on the collector (feed it canned transcripts with known counts; wrong output = red).
9. **Gate check non-vacuity**: % of gate checks that kill their known-bad fixture (Q3). You found six vacuous checks by accident; this makes finding them systematic.

**Sustainability:**
10. Governance mass (Q1c).

The general Goodhart counter-design: **never let the loop optimize an unpaired metric.** Every target metric ships with an integrity metric that must not degrade — rounds↓ paired with rework↛↑; compliance↑ paired with governance-mass↛↑; gate-pass↑ paired with non-vacuity↛↓. The adjudicator scores the pair, not the target. And prefer metrics computed from artifacts the governed agents don't author free-form (run records, hook logs, gate JSON) over regexes on prose — prose metrics teach agents to produce parseable prose, not correct work. That's the subtle fleet-level Goodhart: a loop tuning the rules that govern agents will, given a transcript-regex metric, gradually optimize agents for *legibility to the collector*.

---

## 3. The verification problem

This is the hardest question and your six-vacuous-checks discovery is the whole story in miniature: **a pass/fail gate cannot see assertion strength.** A check that asserts nothing passes forever. By symmetry, the gate also cannot see a rule that was quietly weakened, a glob that was narrowed, a test whose body was hollowed out. So "the fixer must leave the gate green" is a necessary condition that verifies almost nothing about the class of harm you're worried about. Four layers, cheapest first:

**Layer 1 — mutation corpus (make vacuity mechanically detectable).** Every gate check must own at least one *known-bad fixture* it demonstrably fails on, and CI runs check-vs-fixture as a standing job. A check with no killing fixture is, by policy, not a check — it's the six-vacuous-checks bug waiting to recur. Now "making a check vacuous" has a signature: its fixture stops failing, and that's a red CI light the fixer cannot avoid tripping. Cost: one-time authoring of ~57 fixtures (a good early dispatch target for the loop itself, with human review since it's enforcement-surface work), then trivial maintenance.

**Layer 2 — behavioural canaries (test the machinery end-to-end, not its text).** A small suite of scripted "known-delinquent" sessions replayed against the infrastructure: one that tries to end its turn with uncommitted work, one that omits RULES ACTIVE, one that emits the terminator three times, one that leaves a run record open, one that touches a deny-listed path. After *any* merge to the enforcement surface, all canaries must still get caught. This is regression testing for governance behaviour rather than governance prose, and it's the strongest guard on this list because it's indifferent to *how* the fixer weakened something — deleted text, narrowed a glob, inverted a condition — the delinquent either gets caught or it doesn't. Your Stop hook and gate are deterministic code, so this is buildable without burning model quota.

**Layer 3 — asymmetric merge policy (the ratchet in the safe direction).** Classify every diff to the enforcement surface (gates, rules, hooks, deny-lists) as strengthening / neutral / weakening, with a cheap pattern classifier: removed assertions, added skip/allowlist entries, widened exclusions, deleted test bodies, lowered thresholds → weakening. **Weakening changes are never auto-merged** — they become proposals for the human, full stop, even when the loop is right that the rule is bad (over-tight rules are real, per Q1c, but loosening is exactly the move a Goodharting fixer would make, so it always goes through the human). The classifier will have false negatives on novel weakenings — that's what layers 1–2 backstop. Err toward escalation on ambiguity.

**Layer 4 — adversarial second session for enforcement-surface diffs.** When the diff touches gates/rules/hooks at all, a second, independent, cheap metered-model session reviews it with a single hostile brief: *"argue that this change weakens enforcement or narrows what's caught."* Different model, no shared context with the fixer, output attached to the merge decision. You already run this finder/refuter pattern in `/fabrik-review`; reuse it. It's not airtight — nothing at this layer is — but it raises the cost of a plausible-looking weakening from "fools one gate" to "fools one gate plus a skeptic that was told to be suspicious."

Also keep the collector deny-list, but recognize its insufficiency: the cheapest way to move a metric isn't editing the collector — it's editing the *measured thing's definition* (the rule text the compliance metric checks for, the check the pass-rate counts). Layer 3 is what actually covers that, because rule-text edits are enforcement-surface diffs.

One prioritization note: build layers 1–2 *before* letting the actor loose on enforcement surfaces. Until they exist, restrict auto-merge to non-enforcement surfaces (command prose, fragments, scaffolds) and route everything else to the human. That sequencing costs you a couple of weeks and removes the scariest failure class from the autonomous period.

---

## 4. Attribution

Blunt answer: with this traffic, per-change causal attribution from an uncontrolled next-day time series is not achievable, and one-change-per-day does not rescue it — serialization removes *confounding between your own changes* but does nothing about the dominant noise sources (project mix, task mix, the operator's own week, model/harness updates upstream). You'd be running an uncontrolled interrupted-time-series with n≈1 pre/post day per test. Three better designs, in the order I'd deploy them:

**First: replay evaluation — don't wait for tomorrow when you own yesterday.** You are sitting on 8.2 GB / 5,317 sessions of recorded behaviour, and most of your infrastructure is *deterministic code*: hooks, the prompt router, gate checks, collectors, run-record logic. For any change to a deterministic surface, you can re-run old-vs-new against a large historical sample tonight and get, with zero variance and zero waiting: "under the new router, 214 of last month's sessions would have routed differently; here are ten." That is attribution by construction — same inputs, changed code, diffed outputs. This should be the *primary* evaluation instrument, and the daily live metrics demoted to drift detection. The proposal never mentions it, and it's the single biggest missed idea in the brief: it converts most "hypotheses" into computations.

**Second: split-fleet rollout for genuinely behavioural changes.** Prompt-wording and rule-text changes affect model behaviour, so replay can't fully evaluate them. But you have 46 repos and a governance-sync mechanism — that is a ready-made parallel-units experiment. Sync the change to a stratified half of the fleet (stratify by activity level so the busy projects split evenly), hold the rest, run 1–2 weeks, compare arms difference-in-differences. This controls for exactly the confounders that kill the time-series design — a fleet-wide busy week, a model update — because both arms experience them. Costs: the sync mechanism needs per-repo targeting (a real engineering task — currently a commit propagates everywhere); and a fortnight of deliberate fleet inconsistency, which for a single-operator dev platform is acceptable if the digest says which projects are in which arm. Cap concurrent split-fleet experiments at one or two; *this* is where the one-at-a-time discipline belongs, not on the deterministic fixes.

**Third: change-point detection on the portfolio, not per-change verdicts.** For the metrics themselves, run CUSUM/BOCPD per metric over 14-day windows. When a change-point fires, *then* ask which merges landed near it — attribution as forensics on a detected shift, rather than a verdict manufactured for every change on a schedule. Most fixes will never separate from noise individually; the portfolio trend is the honest unit of account, and it's what the operator actually cares about anyway.

Under this design the "adjudicate next day" step becomes: next day, the collector *re-runs the deterministic reproduction check* (still fixed? — catches regressions and interacting changes) and updates trend state. Nothing statistical is claimed daily.

Confounder to log starting now, because it will otherwise eat an experiment: **model and harness versions.** A Claude model update shifts fleet behaviour overnight and will masquerade as the effect (or failure) of whatever you merged that day. Stamp model ID and harness version into every run record and segment every metric by them. Same for your own account rotation if the three accounts ever map to different model access.

---

## 5. What should the human still see

The operator wants out of the loop, not out of the blast radius. Three tiers:

**Tier 1 — interrupt (push, and the loop halts the relevant activity until acknowledged):**
- Any **enforcement-weakening diff** (Q3 layer 3) — arrives as a proposal with the diff, the finding, and the skeptic session's argument.
- **Auto-freeze on regression**: if a north-star metric (first-attempt gate pass, rework) degrades past a change-point threshold fleet-wide and the recent-merge window contains the loop's own commits, the loop stops dispatching, flags the candidate commits for revert, and pages. A self-improving loop that made things worse *and keeps running* compounds daily; freezing must be the default failure posture, not an operator decision.
- **Instrument-health alarm**: collector coverage below threshold, fixture self-test red, a gate-check mutation fixture no longer failing. Your entire epistemology rests on the instrument; when it's suspect, every green light is suspect, and the loop should not act on numbers it can't trust.
- The **3-strikes escalation** (keep it), and any attempted touch of the deny-list.
- **Quota anomaly**: the loop's spend exceeding its budget envelope — it's eating sessions the human needed.

**Tier 2 — weekly digest (pushed, one screenful, decisions first).** He said the *loop* runs daily; nothing says the *reading* must. Daily reports to a man running 46 projects become unread reports within two weeks, and an unread safety channel is worse than none because everyone assumes it's covered. Weekly: pending proposals needing a decision (top), changes merged with their verification evidence (one line each), trend deltas on the north-star metrics, experiment status, backlog top-5, quota spent. Every line links to the dossier, none require the link.

**Tier 3 — pull-only.** Dossiers, per-change hypothesis records, full metric history, the finding backlog. Exists, indexed, never pushed.

Plus one **kill switch** that stops all dispatching and (separately) can revert the loop's last N commits — trivially, since everything is ordinary commits, but pre-scripted so it's a one-liner at 2 a.m., not an exercise.

---

## 6. What you are not thinking about

Roughly in order of how much it worries me:

**The selection policy is the actual product, and it's unspecified.** "Select exactly one finding" hides the hardest sub-problem. The collector will emit findings far faster than any actor drains them; within weeks the backlog is hundreds deep and *which one gets picked* determines everything the loop achieves. Unspecified, it degenerates: to recency (whatever today's sweep surfaced), to tractability (Goodhart at the meta level — the loop picks fixes whose metrics move easily), or to oscillation. You need a persistent, deduplicated backlog with expected-value scoring — frequency × cost-per-occurrence × confidence-the-fix-is-mechanical — with aging, and with per-surface caps so one noisy metric can't monopolize the actor for a month. This deserves as much design attention as the actor got in §5, and it got none.

**Prompt injection through the dossier.** The dossier embeds transcript excerpts as evidence. Transcripts contain arbitrary third-party text — web content fetched by agents, tool output, user-pasted material. A hostile or merely weird string inside a quoted session becomes *instructions inside the fixer's prompt*, in a session that holds commit rights to a surface syncing to 46 repos. Treat transcript excerpts as untrusted data: fence them, label them as evidence-not-instruction, strip imperative-looking content where possible, and rely on Q3's layers to catch what steering slips through. The same applies to the collector if any of its parsing feeds model prompts.

**Governance changes landing under running sessions.** Three concurrent agents share the hub tree, and a synced-surface merge changes the rules *mid-session* for agents that loaded the old rules at SessionStart. Best case: confusion. Worst case: an agent fails a gate check that didn't exist when it planned its work, thrashes against it, burns quota. Either quiesce merges to a window when sessions are typically closed, or version-pin governance per session (SessionStart records the governance commit; hooks and gates evaluate against that pin; new rules apply to new sessions). The pin is cleaner and also improves your experiments — you know exactly which governance version produced each session's data, which Q4 needs anyway.

**Non-stationarity from your own success.** Every effective fix changes the data distribution the collector reads. Stricter gates → longer sessions → different session mix → compliance percentages shift for *compositional* reasons with no behaviour change at all. Watch denominators over time, not just rates; report counts alongside percentages; expect Simpson's-paradox reversals when aggregating across projects (your mixed-era review-rounds number was exactly this lesson — it generalizes past eras to every aggregation).

**Scaffold debt vs. sync reach.** Fixing a scaffold improves projects born tomorrow; the 46 existing projects keep whatever the scaffold gave them at birth on every non-synced file. Scaffold fixes silently under-deliver unless paired with a backfill mechanism (or an explicit decision not to backfill, recorded in the hypothesis so the adjudicator doesn't wait for a fleet-wide metric to move that structurally can't).

**Quota placement.** Constraint §6 says metered API models are cheap and the subscription quota is binding — so the *default* fixer should be a metered-model headless session, with subscription-model dispatch reserved for the hardest findings. The proposal as written ("a headless AI coding session," one/day) doesn't commit; make it explicit, because a daily subscription-quota dispatch is a real tax on the human's own capacity, and cost pressure is the quiet reason daily loops get turned off.

**The collector needs the same loop it feeds.** The kaizen lesson — verify the instrument before believing the number — is stated as a one-time learning, but instrument decay is continuous: transcript formats drift, ledger vocabularies grow new statuses (your `"ok"` bug was exactly a vocabulary assumption going stale), directories move. Fixture self-tests on the collector, run every day *before* its numbers are consumed, are the institutionalized version of that lesson. And when the ledger grows a status the collector has never seen, that's an alarm, not a silent bucket.

**The operator is a confounder inside his own experiment.** Some measured "violations" will trace to the operator explicitly telling an agent to skip process mid-session. The collector can't easily distinguish sanctioned exceptions from delinquency; a cheap `operator-override` marker (a phrase the hooks recognize and log) turns those from noise into labeled data.

---

## Summing up

Build order I'd actually follow: (1) fix the compliance denominators via run-record joins and add collector self-test fixtures — nothing downstream is trustworthy until the instrument is; (2) build the mutation corpus and behavioural canaries for the enforcement surface; (3) turn on the actor for *deterministic, replay-verifiable* fixes on non-enforcement surfaces, merge criterion = reproduced-before/absent-after plus green gate, no metric-movement requirement; (4) add the asymmetric merge policy and skeptic session, extend the actor to enforcement surfaces; (5) build per-repo sync targeting and run your first split-fleet experiment on a behavioural change; (6) stand up the weekly digest, auto-freeze, and kill switch before you stop watching daily yourself.

The deepest disagreement, restated once: the proposal treats "the number moved the next day" as the definition of fixed. At your scale that definition is noise wearing a lab coat, and a loop that takes noise as verdicts will punish good fixes, escalate on retries, and ratchet governance tighter forever. Define *fixed* as deterministically re-provable, define *improved* as a portfolio trend over weeks with controls where possible, and keep the daily cadence for observation, dispatch, and re-verification — daily action, weekly belief. That preserves everything the operator asked for — a loop that runs without him — while grounding it in evidence that can actually bear the weight.



---

## claude-opus-5

# Independent review: the daily self-improving loop

**Headline judgement.** The diagnosis in §3 is excellent and the instinct in §5 is broadly right, but the build order is inverted and the experimental design does not work. The actor is the exciting half and the wrong half to build next. Three things must exist before an autonomous fixer is safe or useful: a noise floor (you have one day of data and no idea what normal daily variation looks like), a proof corpus for the enforcement layer (you already know six gates passed while asserting nothing — the fixer's easiest path to any green is to manufacture more of exactly those), and a fleet-outcome metric that governance ceremony cannot move. Also: one-change-per-day buys attribution it does not actually get, while capping throughput below what 203 artifacts need. You own the distribution channel to 46 repos, which means you can randomize — and that changes the whole design.

Detail below, by question.

---

## 1. Is the loop's shape right?

The cycle *observe → act → verify → adjudicate* is correct. Three things about its current shape are not.

### 1a. It conflates two kinds of work that need different machinery

There are two disjoint classes of finding here:

- **Defects** — a gate check that asserts nothing, a rule pack whose glob never matches, a collector parsing bug, a fragment that fails to render, a scaffold missing a file. These are verifiable *by construction*. "This check now rejects a seeded violation it previously accepted" is proof. No metric needs to move; no adjudication delay is meaningful.
- **Policy changes** — rule text, command prose, hook conditions, anything whose effect is mediated by an AI's behaviour. These need measurement, have a long noisy lag, and can only be adjudicated statistically.

Running both through one pipeline gives you the worst of each. Deterministic fixes get gated behind a noisy daily metric that will frequently say "didn't move," and then the 3-strikes rule escalates work that was obviously correct. Meanwhile policy changes get a next-day binary verdict they cannot support.

Split into two tracks with different rules. Track A (defects): unlimited per day, verified by proof artifact, merged on green, never adjudicated by metric. Track B (policy): small number in flight, randomized where possible, 7–14 day windows, pre-registered analysis.

### 1b. One per day is the wrong rate, chosen for the wrong reason

The rationale given is attribution — "a batch cannot be attributed to a metric movement." But a single change cannot be attributed either (§4), so the constraint purchases nothing while imposing a hard ceiling of ~365 changes/year against a 203-artifact surface that is itself growing. You are paying a large throughput tax for a statistical property you don't receive.

### 1c. The 60-day failure mode nobody sees coming

**Ceremony inflation.** The loop optimizes what the collector can parse. What the collector can parse is markers, blocks, and structured records. The cheapest way to raise a compliance number is always to add more required structure, or to make existing structure more machine-legible. Every such change has a real cost — prompt bytes consumed, agent attention diverted, more surfaces that can fail, more rules for a model to hold — and **none of that cost is visible to the collector.**

Project this 60 days. Compliance reads 95%. Rule packs have grown from 56 to ~80. The governance preamble injected into every session has doubled. Agents are measurably slower, and the metric that would show it doesn't exist. The system has optimized itself into a bureaucracy and scored itself an A.

Counter-design, concretely:

- Make **governance surface bytes per session** a first-class metric (total rules + command + fragment + hook text actually injected, measured from transcripts, not from disk). It is a ratchet that must not increase. Any change that increases it must declare that in the dossier and justify it against a specific defect.
- Impose a **deletion quota**: at least 1 in every 5 accepted changes must be a net removal of an artifact or rule. Not a suggestion — a scheduler constraint. If the queue holds no deletion candidate, the loop's job that day is to *find* one.

Two more 60-day hazards:

**Non-stationary metric definitions.** The collector reads transcripts of agents governed by infrastructure the loop is rewriting. Change the terminator block format and every historical compliance number becomes incomparable — silently. Stamp a `governance_schema_version` on the synced surface, record it per session, and compute metrics per-version with explicit break markers in the series. Without this, every adjudication after the first format change is comparing apples to oranges and will not know it.

**Silent death.** You already have the proof: an hourly CI fixer that dispatched zero times today and nobody noticed until this exercise. The loop's whole premise is that the operator is not watching. So a deadman is mandatory, it must live *outside* the loop (separate cron at minimum, external ping service preferably — a deadman that shares a process with the thing it watches dies with it), and "no completed cycle in 48h" must reach a human.

### 1d. Quota

§6 says the binding resource is a weekly subscription quota shared with the operator, and that metered API models are cheap and a legitimate place to move work. Then take that seriously as a hard rule: **the loop never spends subscription quota.** Fixer, verifiers, skeptics, judges — all on the metered pool. A daily automated fix that eats the quota the operator needs on day 6 of the week is a self-inflicted outage. Add a reserve check: if remaining quota is below threshold, the loop still measures and still queues, but does not dispatch.

---

## 2. What should actually be measured

### What's junk or dangerous in the current set

**Rules-compliance %, as defined, is junk.** It is confounded (§4.1 is correct), it has a fabricated denominator, and it is Goodhart-maximal: it is a string-presence check on text the agent itself writes. An agent can be 100% compliant and produce nothing of value. Keep it as a hygiene diagnostic; never let it be the headline, and never let it alone justify a governance change.

The denominator fix is the highest-value measurement change available, and it isn't an NLP problem — it's a join. **A turn owes the block iff a run record closes on that turn.** Run records already exist. That makes the denominator exact rather than inferred, and it collapses §4.1 and §4.2 simultaneously. If run records aren't yet universal across the fleet, *making them universal is a better first fix than anything currently in the queue.*

And split the metric three ways, because the three are different defects with different fixes:
- (a) marker absent on an obligated turn — a prompt/rule failure;
- (b) terminator emitted more than once per run — this is the *more interesting* one, because repeated terminators mean the agent believed it was finished multiple times. That's premature-completion behaviour, which is a correctness problem, not a formatting one;
- (c) marker present but content vacuous (`GATE:` with no gate run) — the compliance-theatre case, and the one that will grow as you optimize the metric.

**Review rounds per ticket** is a good metric and Goodhart-vulnerable in the nastiest way: the cheapest way to reduce it is to make the reviewer less demanding, and the loop has write access to the reviewer. Never let it stand alone.

**Subagent failure rate / $-per-day**: low information. 4% mostly measures the dispatch layer. Replace $/day with **quota-tokens per closed ticket** — dollars aren't the scarcity, quota is. Keep latency but use p95, not p50; the "slow" complaint lives in the tail.

### The set I would build

**Outcome tier — these are the real ones, and the brief has none of them.**

1. **Rework rate.** Fraction of commits touched again by a fix/revert commit within N days, per project. Computable from git across all 46 repos today, no new instrumentation, and near-impossible to game — gaming it requires actually not needing rework. This is my nomination for headline "correct."
2. **Premature-stop rate.** Stop-hook fires per session. You already built an oracle for "the agent tried to quit while wrong" and you are not reading it. Free, high-signal, hard to fake.
3. **Escape rate.** Defects found by a later stage than the one that owned them (review→certify, certify→deploy-verify, deploy→production), attributed to the stage that missed them. This is the counter-metric that protects review rounds, and it is what makes "3.2 rounds" mean something.
4. **Fleet health.** Nightly across all 46 repos: does it build, do its tests pass, does its gate go green, when did it last release. Deterministic, needs no AI, cheap, and it is the one number governance ceremony cannot move. See §6 — this should be true north.

**Process tier.**

5. **Gate-failure taxonomy at first attempt.** For each session: did the gate go red before green, and on which of the 57 checks. This turns your gates from enforcement into a diagnostic sensor array pointed exactly at where the infrastructure fails to make agents correct-by-default. A check that trips constantly is either a bad rule or a missing scaffold. Currently unexploited and nearly free.
6. **Search-to-edit ratio.** Read/grep/glob calls vs edit/write/commit calls per closed run record. A rising ratio means agents are lost — almost always a docs, scaffold, or naming defect. Excellent early warning.
7. **Rule-pack activation vs. efficacy.** Per pack: how often did it activate, and when it activated, did the session subsequently trip a gate in that pack's domain? Packs that never activate are dead weight (delete). Packs that activate and don't prevent their own failure class are ineffective (rewrite). **This is the only metric in the set that produces a deletion signal, and with 203 artifacts you need one badly.**

**Health tier.** Governance bytes per session (§1c). Quota per closed ticket. Loop liveness counters.

### Goodhart counter-design — three structural mechanisms

- **Mandatory paired counter-metrics.** Every driving metric registers its pair at definition time. Rounds↓ pairs with escapes↑. Compliance↑ pairs with governance-bytes and turn-count. Adjudication *requires the pair not to degrade*; a metric with no registered pair is not allowed to drive a fix. Make this a schema constraint on the metric registry, not a convention.
- **Sentinel metrics.** A registry the fixer is never shown and that the dossier renderer physically cannot read (`metrics/driving/` vs `metrics/sentinel/`, separate load path). If the target moves and sentinels degrade, the change is suspect. Extend the existing "may not edit the collector" rule to "may not *read* the metric registry at all" — otherwise it infers the sentinels from the code.
- **Measure at three altitudes.** String-presence (cheap, gameable) → LLM-judged semantic sample (metered pool, ~30 sessions/week, harder to game) → outcome (rework/escape, hardest). When they diverge, trust the outcome — *and treat the divergence itself as a finding*, because divergence is the signature of gaming.

---

## 3. The verification problem

This is where the plan is weakest, and the weakness is structural: **"re-run the gate" cannot verify a change to the gate.** You already have six proofs that a check can report PASS while asserting nothing. "Make the check pass" is a vastly easier objective than "make the code right," and you are about to point an optimizer at it.

Seven mechanisms, roughly in order of value.

**a) Mutation testing / seeded-violation corpus. Build this before the actor.**

For every one of the 57 gate checks, maintain fixtures that the check *must* reject. Before any merge, the orchestrator runs every check against its whole seed corpus and requires that every check still rejects every seed it owns. A change that makes a check vacuous fails instantly and mechanically.

This has two payoffs. The obvious one is that it makes the fixer safe. The larger one is that it *retroactively finds the vacuous checks you haven't discovered yet*: any check with zero seeds is by definition unverified, and should be quarantined from counting as a pass until it has one. That is a substantial real improvement to the platform that requires no loop at all.

Same treatment for rule packs (one "must activate" fixture and one "must not" per pack) and for the Stop hook (a fixture per blocking condition). Failure mode: seeds go stale or tautological. Counter: seed files are themselves a protected surface — any diff touching them goes to a human, always, no exceptions.

**b) A weakening classifier over the diff.** Deterministic, cheap, and it catches the whole family. Presumptively reject any diff that deletes a test or an assert, adds a skip/xfail, broadens an exception handler, adds `|| true` or a bare `except:`, converts a blocking check to a warning, inserts an early return in a checker, loosens a comparison, or narrows a rule pack's glob. Presumption is overridden only by an explicit pre-declaration in the dossier that this weakening *is* the intended change — otherwise it escalates to the human. Implement as an AST pass plus a coarse regex net; false positives are fine, because the cost of a false positive is one cheap question.

**c) Scope enforcement, mechanically.** The dossier already names the files it may touch. Enforce it: anything outside the allow-list in the diff is rejected without argument. Cap net diff size (~150 lines). An infrastructure change larger than that is a design decision and belongs to a human.

**d) Adversarial review with the goal withheld.** Give two or three independent models *only the diff* and one question: "does this change reduce what the system detects or enforces, in any way?" No dossier, no target metric, no framing. Framing is what makes reviewers agreeable, and withholding it is the cheapest available defence. Majority-refute kills the change. Metered pool — this is precisely the right place to spend non-quota money.

**e) Shadow evaluation for governance *text*.** Rule prose and command prose currently have **no verification at all**, and they are the surface that propagates to 46 repos. Freeze ~20 recorded task setups (repo state + prompt), run them under old and new governance on the metered pool, score with the outcome metrics. Too expensive daily; run it weekly over the week's accumulated text changes. It is the only mechanism that can catch "the new rule made agents worse."

**f) Blast-radius tiering — and here I disagree with the plan's shape.**

A deny-list is the wrong instrument. Deny-lists enumerate known dangers; the whole lesson of the six vacuous gates is that the dangerous class is the one you haven't enumerated. Invert to an allow-list:

- **T0 — never touched by the fixer:** the collector and metric registry, the seed corpus, the crontab, credentials, the sync mechanism itself, the Stop hook.
- **T1 — fixer prepares and verifies; human approves the merge:** anything synced to 46 repos, anything in the enforcement path (gate checks, rule packs).
- **T2 — fixer merges autonomously on green:** docs, unsynced command prose, reporting, scaffolds (they affect *future* projects only), and deletions of provably-dead artifacts.

A self-modifying enforcement system with autonomous authority to weaken its own enforcement across 46 repos is not a risk profile I would accept for a single operator with no reviewer. And I don't think T1 violates his stated goal. He objected to *noticing problems* and *reading dashboards*. Approving one small, pre-verified, evidence-backed diff is not being in the loop in the sense he rejected — the loop did the observing, the diagnosis, the fix, and the proof. He clicks yes. That is a genuinely different job, and I'd hold the line on it.

**g) Rollback as a first-class path, and aggressive.** Every change records its revert SHA and a scheduled re-evaluation. If the paired counter-metric degrades within 7 days, auto-revert without asking. Given how noisy adjudication is (§4), *bounding the damage of every wrong decision to one week is worth more than getting the merge decision right.* Cheap to revert; the loop can always retry with better evidence.

**One more, easy to miss:** worktree isolation does not solve the merge race. Between verify-in-worktree and merge, three agents have moved the base. Verifying pre-rebase and merging post-rebase means landing a change in a state it was never tested in. Require: lock → rebase → **re-run the full verification in the rebased worktree** → push → unlock, with a short lock and a hard timeout.

---

## 4. Attribution

Blunt: one change per day with next-day adjudication will not establish causation, and no amount of care will make it. The population is non-stationary (16 sessions one day, 91 another; different projects, different task mixes, human and headless pooled). Day-to-day variance will swamp any real effect. The binary "moved → confirmed" will confirm noise roughly half the time and thereby *lock in* bad changes with a rubber stamp that reads "proven."

The ticket-era discovery is the perfect illustration of the real danger, and it should worry you more than it seems to: a process change confounded the metric, and it was only visible because a human happened to know the change existed and thought to segment on it. Now picture 60 unlabeled changes in a 60-day window.

Four designs, in order of preference.

**i) Randomize. You can, and this is my main constructive disagreement with the plan's premise.**

You own the distribution channel. The sync mechanism that pushes governance to 46 repos can push *variants*. Cluster-randomize by project: 23 repos get the new rule text, 23 keep the old, for a week; then compare. That is a real controlled experiment, available to you because of a property of your architecture that the plan currently treats only as a hazard ("editing a synced surface changes 46 repos at once") rather than as an asset.

This dissolves the reason for one-change-per-day. With disjoint metric families you can run 3–5 concurrent experiments. Throughput goes up *and* attribution gets better, simultaneously.

Failure modes, honestly: cross-contamination if a project's agent reads hub docs directly (audit and close those paths first); 46 clusters detects a large effect, not a 5% one (accept that — you should only be shipping large effects anyway); and the operator's own session behaviour is a huge per-cluster random effect (prefer metrics with per-session granularity — rule violations, gate trips, search:edit — over per-ticket ones where n is hopeless).

**ii) Interrupted time series with pre-registration, for anything that can't be split** (Stop hook, collector, crontab-level things). Pre-register the metric, the window, and the minimum effect size *before* dispatching. Adjudicate at day 7 or 14 with segmented regression on the daily series, unit of analysis = sessions or tickets, not days. Report an interval. **Most verdicts will be "insufficient evidence," and the system must be allowed to say that** — a three-valued adjudication (confirmed / refuted / inconclusive) rather than the plan's binary.

**iii) Stratify by project; each project is its own control.** Compute within-project deltas, then aggregate. Kills the largest confounder nearly for free, and should be the default aggregation everywhere regardless of design.

**iv) Switchback** for globally-toggleable changes: alternate on/off by day. Handles project-mix confounding perfectly, time trends poorly. Good cheap fallback.

**v) And don't route deterministic fixes through any of this.** "This check asserted nothing; it now rejects three seeded violations" is proven by construction. Sending it to the statistical machinery generates a queue of "unadjudicated" items that are actually fine, and then the 3-strikes rule escalates them to the human. That's how the operator learns to ignore the alerts.

**Verdict: one-change-per-day is wrong.** Replace with unlimited proof-verified deterministic fixes, plus 3–5 concurrent randomized policy experiments on 7–14 day windows with pre-registered analysis.

---

## 5. What the human must still see

Design principle: he receives **decisions and exceptions, never status**. Silence is the default and silence is meaningful.

**Weekly, pushed to a channel he actually reads (not a file he must open), ≤15 lines:** what changed, adjudications (confirmed / refuted / inconclusive), what auto-reverted, and the four outcome metrics with a four-week direction. Nothing else.

**Immediate, same-day interrupt — the loop stops and asks:**
- A T1 change is verified and ready — one-line ask with the diff.
- The weakening classifier fired and the fixer wants to override it.
- 2 failed attempts on one finding (I'd lower the plan's 3 — the third attempt is almost never the one that works, and the information value of "stuck" is highest early).
- **Any metric moving the wrong way by more than its historical weekly variance, regardless of cause.** This is the "something is wrong and nobody noticed" alarm, and note it fires on the *metric*, not on the loop — it must catch problems the loop didn't create.
- Deadman: no completed cycle in 48h.
- Quota reserve breached.
- Any proposed deletion of an artifact. Deletion is right and necessary (§6) but effectively irreversible for governance.
- Two consecutive auto-reverts of the loop's own changes — the loop is thrashing and should be paused.

**On demand only, never pushed:** the complete ledger — every attempt, dossier, diff, verification result, adjudication. Plain files, greppable. He will want it exactly once, at 2am, when something has gone badly wrong, and at that moment it must be complete and local.

The calibration test: a month of perfect operation should produce about four messages. If he gets more than ten in a month without something actually being wrong, the alerting is miscalibrated, he will start ignoring it, and you have rebuilt the dashboard he said he didn't want — except this one interrupts him.

---

## 6. What you are not thinking about at all

**No baseline, and therefore no noise floor.** You have one day of collector output and no idea what normal daily variation looks like. You cannot detect a change you cannot distinguish from Tuesday. Before the actor exists: tag a frozen snapshot of all 203 artifacts, and **backfill the fixed collector over the historical transcript corpus** — 8.2 GB and 5,317 sessions already exist, which is enough to estimate per-metric variance properly and set honest effect-size thresholds. This is a prerequisite, not a nicety. It also answers the question the loop otherwise can never answer: "is the platform better than before we started?"

**The collector now needs more rigor than the fixer.** Two of its first four numbers were wrong. It is now the most privileged component in the system — the fixer may not edit it and everything is judged by it — and it has no tests. Give every metric a golden fixture: ~20 hand-labeled sessions with known ground truth, asserted in CI. A silent collector regression turns the entire loop into a random-walk generator, and by construction nobody is watching.

**mtime selection is a bug, not a caveat.** Long sessions get attributed to the wrong day, midnight-spanning sessions double- or zero-count, and any tool that touches a file re-dates its whole session. Use in-transcript event timestamps, bucket per message. Related: at 8.2 GB and growing ~91 sessions/day, a full re-parse will eventually not finish. Build an append-only derived facts store now — parse each session once, write a compact row, never re-parse.

**Nothing measures whether the 46 projects are any good.** Every metric in the brief is about agent *process*. The vision says the 46 projects are the output. A platform can hit 95% rules-compliance while a third of the fleet doesn't build. Add the nightly fleet health sweep (§2.4) and treat it as true north — it is deterministic, cheap, needs no AI, and it is immune to every form of governance ceremony.

**Fleet heterogeneity is invisible.** 46 projects, 12 scaffold types. A change that helps python-api may hurt chrome-extension. Fleet means will hide that permanently. Break every metric out by scaffold type and have the adjudicator explicitly check for heterogeneous effects — "improved overall, worsened for two types" is a common and important result that a single number erases.

**The three concurrent agents are a measurement confounder, not only a merge hazard.** A session can trip a gate because a *peer* left the tree dirty. Some unknown fraction of your compliance and gate-failure signal is crosstalk. Detect concurrency (overlapping session windows on the same cwd), then either control for it or exclude those sessions from the affected metrics. Right now it's pooled silently.

**Human and headless sessions are pooled.** They are two completely different distributions. Mixing them means the loop can "improve" any metric by shifting the mix. Tag and stratify.

**No memory of refutation.** After 60 days the loop will re-propose things it already tried and that already failed. It needs a persistent index of refuted hypotheses with their diffs, injected into *finding selection* — not just into the retry path for one finding.

**Model drift.** The models change underneath you. A shift on 2026-09-15 may be a vendor update, not your rule text. Record model version per session and treat model changes as known interventions in the time series, or you will spend a fortnight attributing someone else's improvement to yourself.

**Prompt injection into the dossier.** The dossier is assembled from transcript content — text that agents, tools, and remote sources put into sessions. A payload sitting in one project's transcript can ride into a dossier and steer a privileged autonomous fixer holding commit rights across 46 repos. Treat all transcript-derived text as untrusted data: fenced, quoted, never in the instruction position, escaped. This is a low-probability, one-time-only failure — the kind worth closing before it's interesting.

---

## Build order I'd recommend

1. Fix the collector's known defects; add golden fixtures; move to an incremental facts store; backfill history to get real variance estimates.
2. Build the seeded-violation corpus for all 57 gates and 56 rule packs. Quarantine every check that has no seed. *(Large standalone improvement, no loop required.)*
3. Nightly fleet health sweep across all 46 repos.
4. Weakening classifier, scope enforcement, blast-radius tiering, merge-queue discipline.
5. Then the actor — T2 autonomous, T1 proposing-with-approval, metered pool only.
6. Then variant-based randomized adjudication, once step 1 tells you what effect sizes you can actually detect.

The actor is step five. The pull to build it first is strong because it's the half that feels like the product. It is also the half that does damage if the first four aren't underneath it.



---

## claude-sonnet-5

This is a research/analysis consultation, not a coding task — no skill applies here. I'll answer directly from the brief as an independent expert.

## 1. Is the loop's shape right?

The shape — observe → one fix → verify → adjudicate-next-day — is *close* to right but has one structural flaw and one scaling flaw.

**Structural flaw: the adjudication window is wrong for the effect being measured.** A single infrastructure fix (e.g., a rule pack edit) doesn't move a fleet metric in one day when the fleet issues ~91 sessions/day across 46 projects with huge task-type variance. One day gives you a sample of sessions that may not even exercise the changed rule. You'll get false negatives ("didn't move, mark failed") for genuinely good fixes that simply weren't triggered by that day's traffic, and false positives from noise. The fix: adjudicate on *exposure count*, not calendar time — "re-measure once N sessions have touched the changed surface," which could be one day or five depending on how often that rule/command fires. Log exposure denominator alongside the metric.

**Scaling flaw at 60 days: finding exhaustion and oscillation.** After ~60 daily fixes to a 203-artifact surface, you will have touched almost every artifact at least once. Two things happen: (a) the easy, high-leverage, obviously-wrong findings are gone by week 2-3, and the system starts proposing marginal or speculative fixes to fill the daily quota — this is the classic optimizer-runs-out-of-real-work problem; (b) without cross-fix memory, the system can oscillate — fix A weakens a check to reduce false positives, three weeks later a different day's finding (from a different symptom) re-tightens it because the loop has no model of *why* A happened, only that a metric moved. You need a **standing decision log** (not just per-finding hypothesis records) that any new finding's dossier-builder is required to search before proposing a change to the same file/rule — otherwise you'll thrash the same 10 hot files repeatedly. This is worse than it sounds because governance-synced files touch 46 repos per edit — thrashing there isn't just wasted quota, it's 46x commit noise and 46x chances to break someone's mid-flight session.

**The failure mode nobody sees coming: the loop starts fixing symptoms of task difficulty, not infrastructure defects.** Some fraction of "low compliance" or "high review rounds" is not a rule/command problem, it's that certain tasks are inherently harder (novel domain, ambiguous spec) and no infrastructure tweak fixes that. If the collector can't distinguish "agent ignored a knowable rule" from "task was genuinely hard," the daily fixer will keep proposing infrastructure changes for a problem infrastructure can't solve, and — because it must ship one change a day — it will eventually start "fixing" things that aren't broken, which is how rules accrete cruft (exactly what this whole project is trying to prevent, done to itself). I'd add a **third bucket to every finding**: "not fixable by infrastructure — flag and skip" is a valid daily outcome, not a failure. Don't force one commit a day; force one *finding* a day, where "no action" is an allowed disposition alongside fix/escalate.

## 2. What should actually be measured

I'd throw out "rules-compliance %" as currently defined and rebuild the metric set around three questions, each with a Goodhart counter-design:

**A. Did the agent do the *right thing* on the first pass?** (accuracy)
- Proxy: review rounds per ticket (already have this, and it's good — it's a real cost, hard to game cheaply). Keep it, but segment by task_type and by plan era, as you're already discovering with the spine/ticket split. Don't report one fleet-wide mean; report the distribution and call out any bucket under n=10 as unreliable rather than hiding it in an average.
- Goodhart risk: an agent (or the loop) could reduce review rounds by making the reviewer weaker, or by the fixer editing review-trigger thresholds. Counter: reviewer logic is itself a governed surface — put it on the same deny-list as the measurement code ("the fixer may never edit review-trigger or gate-check logic that the metric depends on" — extend guard #1 from a "measurement code" deny-list to a "anything the numerator/denominator of an active metric depends on" deny-list, which is broader than what's proposed).

**B. Did the agent obey the process without being told twice?** (rules-obeyed, redefined)
- Kill the current "RULES ACTIVE + terminator block" binary. Replace with: (1) rate of Stop-hook blocks per session (agent tried to end turn in a non-compliant state — this is a *direct*, unconfoundable signal of "rule not obeyed on first attempt," already logged by your own hook, and you're not using it); (2) rate of gate failures on first gate run per commit, vs. total gate runs needed to reach green. These are structurally cleaner than parsing transcript text for a line that's supposed to appear "once per run" — you're already hitting the exact confound (36 blocks/session) that plagues text-pattern metrics. Stop hook and gate already emit structured pass/fail; use their logs as the source of truth instead of re-deriving compliance from prose.
- Goodhart risk: an agent could learn to never attempt to close a non-compliant turn by just... not finishing (going quiet, capping out). Counter: pair this with a completion-rate metric (sessions that reach a terminal committed state / sessions started) so "fewer stop-hook blocks" achieved via "fewer completions" nets to zero or negative.

**C. Is the agent fast without cutting corners?** (speed)
- Wall-clock and $/turn to green gate, subagent latency p50/p95 (you have this — it's good, keep it, it's a real operational metric not easily gamed).
- Goodhart risk: low, this one's fairly honest, but watch for the fixer "speeding up" gate checks by making them lighter/no-op — this is exactly the six-vacuous-checks problem in section 3, so speed must always be reported jointly with the "checks that assert something" count (see below), never alone.

**New metric I'd add that's missing entirely: check vacuity rate.** You already found six gate checks that PASS while asserting nothing. That is itself a trackable, first-class metric: what fraction of the 57 gate checks and 56 rule packs have you *positively verified* fire on a known-bad input in the last N days (mutation-tested), versus how many have only ever been observed to pass? This is your single best defense against the fixer quietly neutering enforcement, and it currently doesn't exist as a number at all — only as an anecdote from one manual pass. I'd make this a weekly (not daily — it's expensive, requires deliberately breaking things) job: for each gate check and rule pack, synthesize or replay a known-violating case and confirm it fails. Track "checks with a verified negative-control test" as a metric that must monotonically not decrease.

**What I'd drop from the proposed set:** the raw "36% compliance" headline number, full stop, until it's rebuilt on structured hook/gate signals instead of transcript text parsing. It's currently Goodhart-vulnerable in the worst way — trivially gameable by an agent (or a "helpful" fixer) that just emits the terminator block more consistently, which moves the number without moving correctness at all.

## 3. The verification problem

This is the sharpest problem in the whole design and I think the proposed guards are necessary but not sufficient.

The stated guards (deny-list on measurement code, gate+corpus+tests must pass, 3-strikes escalation) stop the *crude* attack (fixer edits the collector directly) but not the *subtle* one: **the fixer weakens a gate check, rule pack, or hook in a way that still passes the gate, because the gate's own check for "is this check still meaningful" is exactly the thing that's missing** — you've already found six examples of this happening organically, without any adversarial pressure at all. An AI fixer under daily pressure to "make the metric move" will find this path faster than a human would, because it's the path of least resistance: weakening a check that's currently rejecting some work is often the cheapest way to reduce "gate failures" or "review rounds," and it will look, from the gate's perspective, identical to a legitimate simplification.

Concrete defenses I'd add, beyond what's proposed:

1. **Diff classification before dispatch, not just deny-list by path.** Any diff touching a file under the gate-checks/, rule-packs/, or hooks/ directories should be tagged high-risk and require a *semantic* check, not just "does the gate pass": run the modified check/rule against a held-out corpus of known-bad examples (you need to build and maintain this corpus — it's the negative-control set from my metric #C above) and confirm it still flags them. If a check's true-positive rate on the held-out corpus drops, reject the change regardless of gate status. This is the single most important addition — it directly targets "PASS while asserting nothing."

2. **Assertion-count invariant.** For any changed gate check or rule pack, diff the number and specificity of assertions (a crude proxy: count of `assert`/`raise`/regex-match branches, or for LLM-graded rules, count of distinct failure conditions enumerated in the prompt). A change that reduces this count is not auto-rejected, but it must be flagged in the dossier and requires the *next day's* human-visible summary to explicitly call it out — "this fix reduced enforcement surface in file X" — rather than silently reporting a clean merge.

3. **The fixer should never be the sole author of its own negative test.** If a fixer's job is "fix check C," it must not also be the one who decides what counts as C still working. The verification corpus (bad examples C should catch) should be static, versioned separately, and appended to by *humans or by a different, non-fixing pipeline* — never generated fresh by the same dispatch that's under pressure to make its own fix look good.

4. **Escalate on any diff that reduces line count in a gate-check or rule-pack file**, even if tests pass. Deletion is the cheapest way to make an inconvenient check vanish, and "delete a hard test" is explicitly named in your own brief as a fear. A shrinking gate-check file is a near-perfect leading indicator worth a mandatory human glance, cheap to implement (just `git diff --stat` on the merge).

5. **Structural separation of "propose" and "merge-worthy" judgment.** Right now the same headless session both writes the fix and the orchestrator "independently" reruns the gate — but the gate is drawn from the same governed surface the fixer might have touched. Use a second, *different* model or a frozen prior-day snapshot of the gate to do the re-verification when the change touches gate/rule files, so the fixer can't (even accidentally) get lucky with a gate config that happens to validate its own change.

## 4. Attribution

One-change-per-day is right for *safety* (bounded blast radius, easy revert, clean commit history) but wrong for *causal attribution* as currently framed, and I'd decouple the two rather than accept the tension as fixed.

The core problem: your fleet is running ~91 sessions/day across 46 heterogeneous projects doing different tasks with a live human also intervening. A single day's before/after comparison on a fleet-wide metric is almost pure noise — you correctly already caught this with the plan-era confound (3.2 vs 4.8 review rounds), which was only detectable because you had a large enough n and a known intervention date. A daily infra tweak will rarely have that luxury.

What I'd do instead, keeping one-change-per-day as the *action* cadence but decoupling *attribution*:

- **Scope the metric to the exposure set, not the fleet.** If today's fix touches rule-pack R which only activates on `*.py` edits in projects using scaffold-type X, don't look at fleet-wide compliance tomorrow — look at compliance specifically among sessions that triggered R, before vs. after. This shrinks the denominator but removes almost all the cross-project noise. This requires the collector to tag every session/review/gate-run with which rule packs/gate checks/commands were actually exercised — which you likely already have from the transcripts (tool calls, file globs touched) and just aren't joining yet.
- **Batch adjudication over a rolling exposure-count window, not calendar days.** "Adjudicate the next day" becomes "adjudicate once ≥30 exposed sessions have occurred post-fix" — sometimes that's 6 hours, sometimes 4 days on a quiet surface. Report both: the same-day naive read (for the human glance) and the exposure-confirmed read (for the permanent record). Never let the naive read alone flip a hypothesis to "confirmed."
- **Hold a control.** Since 46 projects exist, you effectively have a natural quasi-experiment: after fixing rule R (synced to all 46), a few projects may not touch the affected surface in the exposure window and effectively serve as a partial control on general "did anything else change." This is weaker than a true control (governance sync means you often can't A/B a rule) but even the partial signal — "did *unexposed* projects' aggregate metrics also drift on the same day, suggesting something else moved the needle" — is a cheap and valuable sanity check against attributing a global drift (e.g., a model provider update, a bad Tuesday) to your fix.
- **Track a fixed background/placebo metric that no fix should ever move** — e.g., session count or something structurally unrelated to any governed rule — and if it moves in lockstep with your "attributed" metric, that's a red flag the whole day was noisy (holiday, outage, model version bump upstream) rather than your fix being effective.

I would explicitly *not* try to batch multiple fixes per day to get more statistical power faster — that trades away the one property (clean attribution + easy revert) that makes this loop trustworthy at all, for a marginal speed gain you don't need on a 60-day time horizon.

## 5. What should a human still see, and when must the loop stop and ask

The operator wants zero-effort visibility, not zero visibility — those aren't the same, and I think the brief slightly underspecifies this by focusing on "record a hypothesis" as if that's the whole interface.

**Minimum required signal (push, not pull — he said no dashboard):**
- One message per day, only when something happened: what finding was picked, what changed, and yesterday's hypothesis outcome (confirmed / not moved / still pending exposure). If nothing was dispatched that day (valid, per §1), silence is fine — don't manufacture a report.
- A running "hot files" flag: any file touched by the fixer more than twice in a rolling 14-day window, surfaced proactively even without being asked — this is your thrashing/oscillation early warning from §1.
- The vacuity/assertion-shrink flags from §3 — any merge that reduced a gate check's or rule pack's enforcement surface, even if it passed, gets called out by name in the daily message, not buried.

**Hard stop-and-ask triggers** (beyond the given 3-strikes and deny-list):
- Any diff touching a governance-synced surface that will propagate to all 46 repos on next sync — I'd require explicit human sign-off before *every* sync-surface merge for at least the first 30 days of the loop's operation, graduating to autonomous only once you have a track record. The blast radius (46 repos, one bad rule) is too asymmetric to trust to "gate passed" alone in the early running-in period.
- Any hypothesis that gets marked "confirmed" but where the exposure n is below some floor (e.g., <10) — auto-flag as statistically unconfirmed rather than let a lucky small-n bounce count as a win, or you'll quietly poison the "what worked" record the fixer/dossier-builder relies on for future attempts.
- Two consecutive "not moved" adjudications on the *same underlying finding category* (not just the same file) — this is a sign the diagnosis, not just the fix, is wrong, and no amount of retrying the same fix shape will help.

## 6. What you're not thinking about at all

- **Quota starvation from the automation itself, precisely when it's most needed.** You note the fleet's binding constraint is subscription quota shared across 3 rotating accounts, ~2 days heavy use each. A daily automated dispatch competes with human sessions for that same pool. On a day the operator most wants to do real work, the daily fixer (plus its verification re-runs — gate, corpus, tests, all in a fresh worktree, potentially re-dispatching if the first attempt fails) could be the thing that exhausts the account he's about to use. I'd make quota headroom a pre-flight check the daily job consults before dispatching, and skip (log, don't force) on days where fleet quota utilization is already high — "one dispatch per day" bounds attempt count but not cost per attempt, and a 3-strikes retry-in-worktree pattern could burn 3-4x a single session's quota on a bad day.

- **Who verifies the collector itself, going forward?** You just had two significant bugs in a brand-new collector (100%→4%, 21.3→4.8), caught by manual scrutiny before anyone believed them. The loop as designed trusts the collector's numbers to drive the daily action, forever, with no mentioned mechanism to keep catching collector bugs after the initial build. I'd want the same negative-control-corpus discipline applied to the collector itself: synthetic sessions with known, injected violations, run through the collector periodically, confirming the metric reads what you think it reads. Otherwise you've just relocated the "measuring your own paperwork" failure mode from the review-ledger script to the new collector, on a longer fuse.

- **The 3 concurrent same-tree agents are a bigger hazard to the *daily fixer's data*, not just to its file-writes.** The brief covers file-collision risk (worktree isolation solves that) but the collector reading transcripts to compute metrics is reading the interleaved output of 3 agents plus the daily pipeline sharing one cwd/gitBranch context, with no mention of how sessions are disambiguated from each other in the transcript data. If two concurrent sessions' tool calls or commits get attributed to the wrong session (plausible if disambiguation relies on timestamp proximity rather than a hard session id), your per-session compliance and review-round numbers get silently cross-contaminated — worth explicitly auditing that the transcript schema has an unambiguous session key before trusting any per-session aggregate.

- **Scaffold drift.** 12 scaffold types define what new projects are born with, but the loop as scoped operates on existing infrastructure (commands, gates, rules) observed via existing project behavior. A defect that only manifests in project #47 (not yet created) because the scaffold itself encodes a wrong default won't show up in behavioral data until a new project is born and starts accumulating sessions — meaning scaffold defects have the longest feedback latency of anything in the system and are exactly the kind of thing a "daily, reactive, evidence-from-behavior" loop will systematically underserve. Consider a separate, lower-frequency (weekly?) scaffold-specific check: diff each scaffold type against the *current* best-practice state of the rule packs/commands it bundles, independent of whether any project has yet exhibited the resulting bug.

- **The fixer competing with the 46 projects' own review/gate infrastructure for interpretation of "correct."** If a fix to a shared rule pack changes what "correct" means, every open review or in-flight plan in the other 45 projects at that moment is now being judged against a goalpost that moved mid-session. This is a governance-sync problem in general, but the daily automated loop makes it a daily occurrence instead of an occasional human-paced one. I'd want sync timing to avoid merging into projects with a currently in-flight session (you already track run records / open command state — check no project has an open run record for a rule the sync is about to touch, or defer sync for that project by one cycle).

- **No mention of rollback UX for the 46-repo propagation specifically** — the brief says "ordinary revertible commit" for the hub, but reverting a hub commit after it has already synced to 46 repos means either re-syncing a revert (another 46-repo wave) or the 46 repos silently sit on a bad rule until the next sync catches the revert. Given the operator explicitly does not want to be paged, a bad rule-pack sync that isn't caught same-day could sit live across the fleet for days. Worth explicit design: does sync itself have a fast-forward-only or is there a "hold" mechanism to freeze propagation of a specific commit pending next-day adjudication, rather than syncing immediately on merge?



---

## THE BRIEF (identical for all 12)


# Design consultation: a daily self-improving loop for an AI-agent coding platform

You are being consulted as an independent expert. Read everything, then give your own design
judgement. Do not agree with the plan below because it is presented — the most useful thing you can
do is find what is wrong with it, or propose a fundamentally better shape.

---

## 1. THE OPERATOR'S VISION (this is the goal; everything else is means)

One solo developer runs ~46 software projects. He cannot personally review what each project's AI
agent produces. So the only thing that scales is **machinery that makes AI agents correct by
default** — the commands they run, the rules they obey, the gates that block bad work, the hooks
that stop them ending a turn early, and the scaffolds that new projects are born from.

That machinery is the product. The 46 projects are its output.

His stated goal, verbatim and repeated many times:

> "you are the authority of all command files and coding infrastructure, your goal is to
> continuously monitor these, update commands where needed, and present us the fastest, most
> accurate and correct, rules-obeyed coding infrastructure."

He wants a **closed loop that runs daily without him in it**: observe how agents actually behave
across all projects → find where they are slow, wrong, or ignoring rules → fix the infrastructure →
prove the number moved. He does NOT want a dashboard he has to read. He does not want to be the one
who notices a problem.

He has explicitly said: **daily, not weekly.**

---

## 2. WHAT PHYSICALLY EXISTS TODAY (all figures measured, not estimated)

### The platform
- A hub repo (`/opt/fabrik`) that is the platform itself, plus ~46 project repos under `/opt`.
- The hub distributes governance to every project via a pre-commit "governance sync". A commit to a
  synced surface propagates to ~46 repos.
- **3 concurrent AI agent sessions share the hub's single working tree**, plus an automated daily
  pipeline. They cannot see each other's context, only each other's file changes. This matters
  enormously for any automation that wants to commit.

### The infrastructure under management — 203 artifacts
| Surface | Count |
|---|---|
| Slash-command source files (`/fabrik-spec`, `/fabrik-review`, …) | 27 |
| Shared command fragments (included into commands at render time) | 13 |
| Rule packs (activate by file-glob when an agent edits a matching file) | 56 |
| Gate checks (block a commit when they fail) | 57 |
| Session hooks (Stop hook, prompt router, SessionStart, PreCompact) | 5 |
| Scaffold types (what a brand-new project is born with) | 12 |
| Fleet-synced core scripts | 12 |
| Cron jobs | 21 |

### The enforcement model already in place
- **Gate**: `final_gate.py --json` runs 42 blocking checks; agents must reach `status:"success"`.
- **Stop hook**: blocks an agent from ending its turn if its work is uncommitted, unpushed, the gate
  is red, or a command "run record" is still open.
- **Run record**: every command invocation opens a JSON record with phases and a terminal condition;
  a pinned status line appears in every agent reply until it closes.
- **Provenance trailers** on every AI commit.

### The data that exists about agent behaviour (this is the raw material)
| Source | Volume |
|---|---|
| Session transcripts (every message, tool call, tool result, with `cwd`, `gitBranch`, timestamps) | **5,317 sessions · 8.2 GB · 98 project dirs** (2,281 in the last 7 days; ~91/day) |
| Subagent dispatch ledger (cost, latency, model, status, turns, tool_calls, error, task_type) | **3,292 rows**, 2026-07-08 → today |
| Review ledgers (a record per code review, with round counts) | **237** (49 hub + 188 in other projects) |
| Plan sets | 110 |
| Command run records | just started — see below |

---

## 3. WHAT WAS ALREADY BUILT, AND HOW IT FAILED

A "kaizen" measurement script was built days ago. It reads **exactly one directory**: the hub's own
review ledgers. It produced **one row**, with 5 of its 8 columns empty. It never read a single
session transcript, never read another project, never read the subagent ledger.

That is the core failure being corrected: **a measurement system that reads its own paperwork rather
than the fleet's behaviour.**

A collector was just built (today) that reads the real execution record. Its first runs produced:

| Metric | Value |
|---|---|
| Sessions in a day | 16 sessions across 10 projects (a quieter day; ~91 on a busy one) |
| Rules-compliance (see caveat below) | 36% overall — from 73% (one project) down to 7% (another) |
| Subagent failure rate | 4% (4/97), p50 latency 37s, $0.74/day |
| Review rounds per ticket, ticket-era only | **3.2** (n=12/16), max 8, min 1 |
| Review rounds, mixed 30-day window | 4.8 — misleading, see below |

**Two of the collector's first numbers were bugs in the collector itself**, found and fixed before
being believed:
- Subagent failure read **100%** because the predicate was `status != "ok"`; the ledger's actual
  vocabulary is `done`/`error`/`capped`/`out_of_scope` and never contains `"ok"`. True rate: 4%.
- Fleet review rounds read **21.3 with a maximum of 1440**, because a naive "table row starting with
  a number" regex matched a data table in an unrelated document. True mean: 4.8.

This is treated as a first-class lesson: **verify the instrument before believing the number.**

**A recent process change is already visible in the data**: the platform switched from single-file
plans to "spine + ticket" plan sets on 2026-08-09. Measured across both eras, review rounds average
4.8. Measured on ticket-based plans alone: **3.2**. The process change bought ~33% off review cost,
and the mixed average hid it.

---

## 4. KNOWN DEFECTS IN THE CURRENT MEASUREMENT (be skeptical of these numbers)

1. **The compliance metric is confounded.** Governance requires a "RULES ACTIVE" line at the top and
   a 6-line block (`GATE:/DONE:/NEXT:` …) at the bottom of any *task-completing* response. The
   collector counts responses containing the final block as the denominator. But it counted ~36 such
   blocks per session, when the block is supposed to be emitted **once per run**. So the metric
   currently conflates (a) agents omitting the required line with (b) agents emitting the
   terminator repeatedly mid-run — which is itself a distinct, forbidden failure mode. It cannot
   drive a fix until it is split.
2. **Denominators generally.** "20 of 91 sessions lacked RULES ACTIVE" is not 71 violations —
   conversational and read-only turns do not owe the line. Choosing wrong denominators manufactures
   outrage and gets the metric ignored.
3. **Selection bias.** Transcripts are selected by file mtime for a given day.
4. **Only 3 ticket-era plan sets exist** (2026-08-09 onward), so n=12 review ledgers. Very small.

---

## 5. THE PROPOSED "ACTOR" (the half that is NOT yet built — critique this hardest)

The measurement half now exists. The proposal for the acting half, once a day:

1. **Select exactly one finding** (not a batch — a batch cannot be attributed to a metric movement).
2. **Build an evidence dossier**, not an instruction: the defect at `file:line`, the measurement
   that found it, the specific sessions proving it, the metric expected to move and in which
   direction, the files it may touch, and the files it must not.
3. **Create an isolated git worktree.** Rationale: an existing hourly "CI fixer" on this box
   dispatched **zero** times today because it skips whenever the working tree is dirty — and with 3
   agents sharing every tree, it is almost always dirty. Isolation is what makes the fixer actually
   run rather than exist.
4. **Dispatch a headless AI coding session** into that worktree with the dossier.
5. **Verify independently — never trust the session's claim.** The orchestrator itself re-runs the
   full gate, the corpus integrity check, and the test suite in that worktree, and confirms a real
   commit exists. "It says it fixed it" is not evidence.
6. **Merge only on green**, then push. Otherwise destroy the worktree and record a failed attempt.
7. **Record a hypothesis, not a completion**: "changed X, expect metric M to move from A toward B".
8. **Adjudicate the next day.** The collector re-measures M. Moved → confirmed. Didn't move → the
   fix failed; it returns with the previous attempt's diff attached. **Nothing counts as fixed until
   the number moves.**

Proposed guards:
- The fixer **may never edit the measurement code** (a diff touching the collector is rejected).
  Otherwise the cheapest way to move any metric is to change how it is measured.
- 3 failed attempts on one finding → stop, escalate to the human.
- Hard deny-list: credentials, the credential-rotation directory, the crontab, another repo.
- One dispatch per day, bounding the cost.
- Every change is an ordinary revertible commit.

---

## 6. CONSTRAINTS THAT ARE NOT NEGOTIABLE

- **A shared working tree with 3 concurrent agents.** Destroying a peer's uncommitted work is a
  critical failure. No `git add -A`, no force-push, no stashing another agent's files.
- **Editing a synced governance surface changes ~46 repos at once.**
- **The binding resource is a weekly AI subscription quota, not dollars.** Three accounts, each
  exhausted in ~2 days of heavy use, rotated automatically. A daily automated fix costs quota that a
  human session then cannot use.
- The platform is a single-operator development environment, not a multi-tenant product.
- Metered API models (you, in this consultation) are billed separately from that quota and are
  comparatively cheap — so the pool of non-subscription models is a legitimate place to move work.

---

## 7. WHAT WE ARE ASKING YOU

Not a yes/no. Give your independent design judgement on this whole system. In particular, we want
you to think hard about — and disagree where you disagree:

1. **Is the loop's shape right?** Observe → one fix → verify → adjudicate-next-day. What breaks at
   scale, or after 60 days of running? What is the failure mode nobody sees coming?
2. **What should actually be measured** to capture "fastest, most accurate, most correct,
   rules-obeyed"? Propose the metric set you would build, and say which of ours are junk. Which are
   Goodhart-vulnerable, and what is the counter-design?
3. **The verification problem.** An AI fixing infrastructure that governs AI. How do you prevent the
   fixer from making the system worse in ways the gate cannot detect — e.g. weakening a rule,
   deleting a hard test, making a check vacuous? Note this platform already found six gate checks
   that reported PASS while asserting nothing.
4. **Attribution.** With one change per day and metrics that drift for unrelated reasons (different
   projects, different tasks, different humans), how do you establish that a change caused a
   movement? Is one-change-per-day right, or is there a better experimental design?
5. **What should a human still see?** The operator wants to be out of the loop but not blind. What
   is the minimum signal that must reach him, and when must the loop stop and ask?
6. **What are we not thinking about at all?**

Be concrete. Where you propose something, say how it would be implemented and how it would fail.
Length is not limited; depth is what is wanted. Take your time.
