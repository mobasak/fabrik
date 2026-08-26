# Design: plan-lock release check — a finished plan must not hold its scope lock

Status: CONVERGED (review 2, 2026-08-26 — 8 passes, md5-verified no-op `6b853a48`; the first
review's CONVERGED verdict did not hold, see § Review history)

**Owner:** `[infra]` · **Scope:** one enforcement check + its test · **Stage:** 1-design

## Goal

Detect, the day it happens, a plan lock left in a **non-terminal** state (`active`, `paused` or
`blocked` — see § status vocabulary) after its plan finished — so the omission surfaces at its
cause instead of a week later as a hard `BLOCKED` halt at another agent's
`/fabrik-execute-plan` step 7.

Explicitly NOT the goal: making lock creation/release mechanical (a writer API, a hook, a
`command_run`-style helper). That is a larger change to how `/fabrik-execute-plan` works. This
check is the cheap detector that makes the omission *visible*; whether to then make the write
mechanical is a separate decision the detector's own data should inform.

⚠️ **The honest risk in that sequencing, stated rather than buried: shipping a detector can
relieve the pressure to do the real fix.** The mechanical writer is strictly better — it makes
the omission impossible instead of merely visible — and an advisory line that becomes wallpaper
would leave the protocol exactly as unbound as it is today, while *feeling* addressed. This is
not a hypothetical in this repo: `final_gate.py:1382-1386` records that `check_doc_sprawl.py`
"was inert since ≤2026-08-04, then WARN-only while the fleet was cleaned" before anyone promoted
it, and `:1392-1400` records `check_watchdog.py` being left **UNWIRED** after measuring 62
fleet-wide WARNs — the check that produces noise nobody acts on gets removed, not obeyed.

So the detector is justified only on the cost asymmetry — ~100 lines against a failure that costs
an unrelated agent a hard `BLOCKED` halt plus an operator ruling — and it carries an explicit
exit condition rather than an open-ended life: **if it catches more than two NEW instances after
landing, that is the signal to build the mechanical writer and DELETE this check**, not to keep
tuning it. That trigger is recorded in the check's own docstring (Open unknown 2), where the next
agent reads it, not only here.

⚠️ **"NEW instances" is load-bearing and this sentence had to be corrected mid-review.** It first
read *"if it fires more than twice"* — written before the fleet was measured, and the fleet
measurement then found **exactly two findings on day one** (§ Constraints). The trigger would
have been satisfied by the pre-existing backlog on the morning it shipped, which measures the
wrong thing entirely: a detector's day-one yield is the debt it inherited, not evidence about
whether detection changes behaviour. The counter starts at zero **after** the day-one findings
are dispositioned.

## Why — the protocol has readers and no writer

**Nothing writes a plan lock but the agent.** Verified this session, not recalled:

```
$ grep -rl "plan-locks" scripts/ .claude/hooks/ --include=*.py
scripts/kilo-benchmarks/tests/test_golden_parity.py   # :1347 — a string-literal guard
                                                      #   asserting plan-locks is NOT staged;
                                                      #   never opens a lock. Not a consumer.
scripts/enforcement/check_phase_tests.py      # READS  (:36, :44-46)
scripts/enforcement/check_plan_tickets.py     # READS  (:561, :1470) — plus :949, which
                                              #   string-matches a ticket's Touches path
                                              #   and never opens a lock (see below)
.claude/hooks/final_gate_stop.py              # READS  (:785)
$ grep -rn "plan-locks" scripts/ .claude/hooks/ --include=*.py | grep -E "write_text|json.dump|open\(.*['\"]w"
(no output)
```

FOUR files match; THREE parse lock files, the fourth only asserts the string is absent from a
stage list. So: three consumers, zero writers. (The grep is shown returning four because that
is what it returns — an earlier draft of this spec said "three", which would have sent anyone
re-running it looking for the discrepancy.) The lock is created by prose (`/fabrik-execute-plan`
Before-You-Start step 7: *"create `.fabrik/plan-locks/<plan-id>.json`"*) and released by prose
(Finish step 5: *"set `status:"released"` (+ `completed_at`, `final_commit`)"*). So the whole
mutual-exclusion protocol is honour-system, with the honour supplied by an LLM following a
paragraph it read hours earlier at the tail of a long run — exactly the condition CLAUDE.md
already names for the Stop hook: *"prose alone cannot bind an agent that read this contract
hours ago."*

### Two live instances, both measured and both freed today

| lock | status | completed_at | final_commit | plan's real state | cost |
|---|---|---|---|---|---|
| `2026-08-19-plan-1-kaizen-m1-event-stream` | `active` | `2026-08-21` | `null` | `EXECUTED`, archived, 9/9 tickets merged | BLOCKED the inert-rule-packs plan at step 7 on `final_gate.py`, `select_rules.py`, `review_rubric.py` until the operator ruled |
| `2026-07-26-plan-1-ai-model-catalog-extraction` | `active` | `null` | `null` | `EXECUTED 2026-08-15`, archived, residue 0 | held 10 paths (`scripts/kilo-benchmarks/`, `tests/kilo_benchmarks/`, …) for 13 days |

Instance 1 is the diagnostic one: `completed_at` set and `final_commit` null is **one field of a
three-field write landing** — a half-applied Finish step 5, which is a different failure from
"the agent forgot entirely" (instance 2, both fields null).

The blast radius is not incidental. Both locks held high-traffic hub paths that most plans
touch, so one unreleased lock silently blocks the *next several* plans, and it surfaces far from
its cause.

## Chosen approach — a standalone advisory check, modelled on `check_vendored_drift.py`

`scripts/enforcement/check_plan_lock_release.py`, wired into `final_gate.py` via
`run_optional_check(..., warn_only=True)`.

⚠️ **The status vocabulary — the axiom two reviews got wrong, in opposite directions.**

Draft 1 called it binary. Review 1 measured the hub corpus, found four values, and adopted the
rule *"key on `status == "active"`, treat EVERY other value as terminal"* — congratulating itself
that "a fifth value invented tomorrow then needs no code change." **That rule is unsafe, and
review 2 found out why by asking the writer instead of the corpus.**

`/fabrik-execute-plan` prescribes **two further status literals, both NON-terminal**:

- `:459` — *"the plan PAUSES: lock `status: "paused"`, Board preserved, spine stays IN-PROGRESS;
  resume on quota reset/rotation."*
- `:563` — *"the lock is RETAINED with `status: "blocked"` + the full `tickets` map for operator
  inspection but its `owned_paths` is CLEARED"*

A `paused` or `blocked` lock is **mid-flight**. Under review 1's rule both are silently counted
`terminal` — so the check reports every run finished while a plan is still holding scope. And
`paused` is not exotic here: quota exhaustion is the *routine* interruption on this box.

**It is not hypothetical — the fleet has one right now.** Measured across all 16 `/opt` repos
that carry locks (the hub is 49 of 213; every number in this spec before review 2 was hub-only):

```
$ status distribution across 213 fleet locks           # 2026-08-26 ~13:30 UTC
{'released': 197, 'active': 6, 'executed': 6, 'complete': 2, 'completed': 1, 'paused': 1}
```

**Seven values, not four** — the fleet adds `completed` (a seventh, distinct from `complete`)
and a live `paused` lock in `whatsapp-agent`. Reading only the hub would have shipped a check
blind to both.

⚠️ **Every fleet figure in this spec is timestamped, because the corpus MOVED during the review
that measured it.** The first fleet run (~12:50) found 212 locks and 5 active; the confirming run
40 minutes later found **213 and 6** — a sibling session in `fabrik-lib` had taken a lock at
10:17 that had not existed at the start. That is not a defect in the measurement; it is the
operating condition. **The check runs against a corpus other agents are mutating concurrently**,
so any "the corpus is clean" claim is true only of an instant, and the spec states its instants
rather than implying permanence.

**So the partition follows the WRITER's contract, not the corpus, and unknowns are named:**

| class | values | treatment |
|---|---|---|
| **non-terminal** | `active` · `paused` · `blocked` | all rules apply |
| **terminal** | `released` · `executed` · `complete` · `completed` | skip |
| **unrecognised** | anything else | its own `UNKNOWN STATUS:` line — never silently terminal |

The `UNKNOWN STATUS` third class is the actual future-proofing review 1 reached for and missed:
an eighth value (or a typo) must surface as an unasked question, not be absorbed into a green
count. `check_pack_reachability.py:243-247` added exactly this category for exactly this reason.

⚠️ **A non-terminal lock is NOT automatically a defect — two sanctioned steady states exist.**
A `paused` lock (quota) and a `blocked` lock (halt) are *correct*, however long held: the plan
still owns its scope until resolved. So "non-terminal" gates the rules; it never IS the finding.
Rule 1 still needs the plan to be finished, rule 2 still needs the half-applied field shape. This
is also why the rejected age-based alternative is not merely unreliable but **wrong in
principle** — the lock guaranteed to look oldest is the one legitimately waiting on an operator.

⚠️ **The command contradicts itself here, and the check must tolerate both readings.** Step 7
says *"(A lock left `active` by an orderly `BLOCKED` halt is INTENTIONAL …)"* while `:563` says
the halted lock is *"RETAINED with `status: "blocked"`"*. So a blocked run's lock is `active` in
one paragraph and `blocked` in another, and **both shapes exist in the wild**. Treating either as
terminal would hide a live run; treating either as a finding would flag a correct one. Both are
non-terminal, neither is a finding on its own. *(The command-corpus inconsistency is a separate
defect, filed against `commands/_sources/fabrik-execute-plan.md` — not fixed here, because
changing the lock protocol's prose is a different change with its own fleet blast radius.)*

**Three rules and one catch-all. Two are mechanically decidable; 1B is explicitly inductive and
labelled as such** — review 1 claimed "two mechanically-decidable rules, no judgement" and that
framing is what made the inductive limb feel unwelcome enough to be got wrong twice (first
over-reaching, then cut entirely). Naming the confidence per rule is what lets the inductive one
exist safely:

1. A lock is stale if its plan is finished. **"Finished" has two limbs, reported at different
   confidence:**

   - **1A — the plan lives under `docs/development/plans/archived/`** ⇒ `STALE LOCK`.
     Definitive: archiving is a deliberate, observable, mechanical act.
   - **1B — the plan is still under `plans/` but its `Status:` value BEGINS with a finished
     token** ⇒ `LIKELY STALE LOCK`, quoting the matched token and the verbatim status line.

   ⚠️ **The draft's `Status: EXECUTED` test was wrong, and it survived the first review
   unchallenged** — repeating, on the plan-status axis, the exact enumerate-from-partial-data
   trap this spec congratulates itself for avoiding on the *lock*-status axis one paragraph
   above. A naive `^Status: EXECUTED` matches **28** archived spines and misses **39** finished
   ones:

   ```
   $ naive '^Status: EXECUTED' MATCHES: 28   ·   FINISHED-but-MISSED: 39
      2026-04-13-ocoron-com-full-deployment.md    **Status:** COMPLETE — All stages successful
      2026-05-30-coolify-residue-cleanup.md       **Status:** ✅ **CLOSED 2026-06-02 …
      …-watchdog-error-webhook.md                 **Status:** DONE (2026-07-01) …
      …-ci-scaffold.md                            **Status:** SHIPPED (core) 2026-07-01 …
   ```

   Finished plans say `EXECUTED`, `COMPLETE`, `CLOSED`, `DONE`, `SHIPPED`, `FIXED`,
   `SUPERSEDED`, `IMPLEMENTATION-CONVERGED`; most older spines prefix it **bold**
   (`**Status:**`) and many lead with `✅`, which a bare `^Status:` regex never reaches.

   ⚠️ **But cutting the status test entirely — this review's first instinct — is ALSO wrong,
   and measuring caught it.** Seven finished plans currently sit under `plans/` un-archived
   (`2026-08-10-plan-1-quota-health` = `EXECUTED`, `2026-08-14-plan-1-doc-sprawl-non-vacuous` =
   `EXECUTED 2026-08-14`, …). Location-only would miss every one — a real coverage regression
   introduced while fixing a real over-reach.

   **ANCHORING is what makes a token list safe, and that is the whole finding.** The defect was
   never "using tokens"; it was matching one token, un-anchored, behind an un-stripped prefix.
   Strip leading decoration (`**`, `✅`, `🚧`, whitespace), then require the token at the
   **START** of the value — never a substring search. Measured across the entire corpus:

   ```
   $ anchored, decoration-stripped, START-of-value
   LIVE plans/:  anchored-finished = 5    substring-only (correctly NOT flagged) = 1
   ARCHIVED:     anchored-finished = 61   substring-only (correctly NOT flagged) = 5
   $ the 6 a substring search would have WRONGLY flagged — every one genuinely unfinished:
      2026-06-29-plan-watchdog-deploy-side   "Issue 1 RESOLVED (§2.8) … Tier-D is not yet ENABLED"
      2026-04-18-zero-touch-deployment       "IN PROGRESS — Phase 4a ✅ · … 4l pending"
      2026-04-13-fabrik-control-plane        "APPROVED — Phase 0 COMPLETE · … Phase 1 + 2 pending"
      2026-05-30-ai-watchdog-platform-P2     "✅ Architecture approved 2026-05-30 …"
   ```

   66 anchored hits, 6 substring-only cases excluded, **0 errors in either direction** on the
   live corpus. `RESOLVED` is deliberately absent from the token set — it is how this repo
   labels a resolved *issue inside* an unfinished plan, and it was the first false positive.
   `CONVERGED` is likewise absent: a converged plan is ready to execute, not executed.

   1B is reported as `LIKELY` rather than `STALE` because a token set is inductive where a
   directory is not — and the confidence asymmetry is deliberate: a false `LIKELY` costs the
   operator one glance, a miss costs an unrelated agent a `BLOCKED` halt.

   🔁 **DO NOT WRITE A NEW STATUS REGEX — one already exists, hardened, and this spec nearly had
   a fourth parser built.** `scripts/enforcement/check_convergence.py:122-126` is exactly this
   matcher, in production, behind a *blocking* gate:

   ```python
   EXECUTED = re.compile(
       r"^\s*(?:[-*>]\s+)?\*{0,2}Status\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*(?:✅[^\S\n]*)?"
       r"\*{0,2}[^\S\n]*EXECUTED\b", re.I | re.M)
   ```

   It already tolerates the leading list/quote marker, bold-or-plain `Status`, the colon inside
   or outside the bold, and the `✅` prefix — and its own comment at `:116-118` gives the
   anchoring rationale in the same words this review reached by measurement: *"EXECUTED must be
   the status VALUE … else a `Status: CLOSED … never executed directly` line false-positives."*
   That the two converged independently is confirmation of the rule; that this spec got to a
   token-matcher design without grepping for one is the process defect, and it is **the same
   duplicate-parser class the predecessor plan's T04 existed to close** (`select_rules` and
   `review_rubric` each carried a private glob matcher until one was extracted). A fourth status
   parser here would be that defect committed by its own successor.

   **Prescription, and its one sharp edge:** import and reuse `check_convergence.EXECUTED` for
   the canonical form — which is also the *contractually prescribed* one, since `/fabrik-execute-
   plan` Finish step 5 says to flip the plan to `Status: EXECUTED <date>`; every other token in
   the list is historical drift, not an alternative contract. The legacy alternation
   (`COMPLETE`/`CLOSED`/`DONE`/`SHIPPED`/`FIXED`/`SUPERSEDED`/`IMPLEMENTATION-CONVERGED`) is
   built in the NEW module **by extending the same anchor pattern**, and
   `check_convergence.EXECUTED` is **NOT edited** — it backs a blocking, fleet-synced gate, and
   widening it to catch legacy wording would risk reddening ~46 repos for an advisory check's
   convenience. A test pins that the two agree on the canonical form so they cannot silently
   drift apart.

2. **A NON-TERMINAL lock** with a completion timestamp set but `final_commit` missing ⇒
   `HALF-APPLIED FINISH`. (Instance 1's signature: a half-applied Finish step 5.)

   ⚠️ **The non-terminal scoping is load-bearing and was MISSING from this spec's first draft.**
   Executed against the real corpus, the unscoped rule flags **14 locks — 13 `released` and 1
   `complete`** — because a completion timestamp without `final_commit` is the ordinary historical
   shape of a *finished* lock, not a defect signature. Landing that would have fired on 14 locks
   on day one: exactly the "a check firing fleet-wide on day one is how a gate gets ignored"
   failure this spec warns about, committed by the spec itself. Scoped, it flags **0** at the hub.
   Measured, not reasoned:

   ```
   $ # rule 2, unscoped, over all hub locks
   locks matching (completed_at set, final_commit null): 14
   their status distribution: {'released': 13, 'complete': 1}
   $ # rule 2, scoped to non-terminal status
   would flag: 0
   ```

   ⚠️ **Review 1 wrote this scope as `status == "active"`; that is now `non-terminal`.** A
   `paused` lock carrying a completion timestamp and no `final_commit` is the *same* half-applied
   Finish — the quota-pause path writes the lock too. Keying on `active` alone would have made
   rule 2 blind to exactly the interruption this box hits most often.

**Why standalone rather than folded into `check_plan_tickets.py`:** that check is a
spine↔ticket *contract* gate, and it already carries **two** lock-related rules — at `:1470` it
collects active locks whose `owned_paths` intersect the changed set, to decide which plan dirs to
check; and at `:949` it refuses a ticket that names the plan's own lock in `Touches`, on the
ground that *"the lock is orchestrator-owned, never a ticket's write set"*. Both were read, not
assumed. Neither is lifecycle validation: `:1470` asks *which plans are in play*, `:949` asks
*who may write the lock* — **nobody asks whether a lock that is still `active` has any business
being so.** That is the gap, and it is genuinely new work rather than a duplicate.

The `:949` rule is worth naming for a second reason: it shows the repo already treats the lock as
having a designated writer (the orchestrator) — the protocol has an *owner*, just no *code*. That
strengthens rather than weakens the case here; the missing piece is verification, not ownership.

Folding the new rules in anyway would mix two questions in one exit code and make the
advisory/blocking split impossible: `check_plan_tickets.py` is blocking, and this must be
advisory.

### Three grounded design inputs, each found by doing rather than assuming

1. **The `plan` field cannot be followed literally — measured, 3 of 49 locks break it.** A naive
   `Path(lock["plan"]).exists()` reports *"plan missing"* for all three and would mis-classify
   the very instance that motivated the check. Two independent causes, both live and both
   re-runnable today:

   ```
   $ plan-field shapes across 49 locks
   PATH (has /): 48   ·   BARE NAME: 1
      BARE NAME: 2026-08-10-plan-1-quota-health.json -> '2026-08-10-plan-1-quota-health'
   $ stored path resolves as-is?
   RESOLVES: 46   ·   STALE (file not at that path): 2
      2026-07-20-plan-2-claude-p-first-class-scoring.json -> docs/development/plans/…-scoring.md
      2026-08-19-plan-1-kaizen-m1-event-stream.json      -> docs/development/plans/…-stream.md
   $ resolution by filename STEM
   archived: 46 · live: 3 · UNRESOLVABLE: 0
   ```

   The **stale-path** cause is the stronger one and was missing from this spec's first draft: a
   lock stores the plan's path at *creation*, under `plans/` — and archiving the plan on Finish
   moves the file, silently invalidating the stored path. Instance 1's lock is exactly this. So
   the field goes stale through the ordinary, correct lifecycle, not only through sloppy writing.

   ⚠️ **A correction to this spec's own earlier evidence.** The first draft cited instance 2's
   field as the bare name `"2026-07-26-plan-1-ai-model-catalog-extraction"`. That was true when
   observed, but **is no longer reproducible**: freeing that lock (commit `17f00754`) rewrote the
   field to a full path. A reader re-running the claim finds a path and concludes the spec is
   wrong. The bare-name shape is therefore re-grounded on `2026-08-10-plan-1-quota-health`, which
   is still bare in the live corpus. A spec whose value is "these claims were executed" owes
   claims that still execute.

   **Resolve the plan by filename STEM against both `plans/` and `plans/archived/`, treating the
   `plan` field as a hint.** Stem resolution succeeds for **49 of 49** locks.

   ⚠️ **But stem resolution alone would make the check robust and blind at the same time — so it
   also REPORTS the mismatch.** Finish step 6 (`fabrik-execute-plan.md:970`) mandates a *fourth*
   terminal write this spec had not accounted for: *"repoint the lock's `plan` field to the
   archived path."* The field is therefore contract-bearing, not decorative — and the 2 stale
   paths above are 2 live instances of a **missed step-6 repoint**. Silently rescuing them by
   stem lets the field rot corpus-wide with no gate anywhere noticing, and drags
   `check_phase_tests.py` down with it (design input 3). So a third line is emitted:

   ```
   PLAN FIELD STALE: <lock>.plan does not resolve ('<value>') — Finish step 6 repoint missing
   ```

   **It has two live positive cases at the hub today** — the only rule that does, since rule 1's
   live instance is in another repo and rule 2 has none anywhere (§ VERIFICATION GAP). It costs
   nothing extra: the resolution already computes both answers.

2. **The filename stem is the reliable key**, and the repo already relies on it:
   `check_plan_tickets.py:1481` does `cand = root / "docs" / "development" / "plans" / lf.stem`.
   That is the established convention; reuse it rather than inventing a second resolution path.
3. **The two existing consumers each mis-resolve an archived plan, but by DIFFERENT mechanisms —
   and this spec's first two drafts asserted one mechanism of both.**
   - `check_plan_tickets.py:1481-1482` builds `plans/<stem>` and never looks in `archived/`, so
     an archived plan's lock fails `cand.is_dir()` and is silently skipped.
   - `check_phase_tests.py:61-66` does something else entirely: it joins the **raw `plan` field**
     to `PROJECT_ROOT` (`p = (PROJECT_ROOT / plan_path).resolve()`) and bails on `not p.is_file()`.
     It never consults `plans/` at all. So the bare-name lock documented in input 1 resolves to
     `/opt/fabrik/<bare-name>`, misses, and that check silently returns `[]`. It also gates on
     `d.get("status") == "active"` at `:53`, so a `paused` run's phase tests go unchecked too —
     the same non-terminal blind spot as § status vocabulary, in a second consumer.

   Two distinct live silent-skips, not one. The generalisation *"existing consumers only look in
   `plans/`"* was true of one file and asserted of both — the same over-reach class as the
   `:949` mis-annotation above.

### Output contract

A success line **states its denominator** — the class this session closed repeatedly, applied to
this check from the start rather than retrofitted. It must also state what it could NOT evaluate,
because a denominator that silently absorbs its own blind spots is the fail-silent-green defect
wearing a denominator.

⚠️ **`OK` is the WRONG word when nothing was evaluable — and on today's hub corpus, nothing is.**
Every rule gates on a non-terminal lock. The hub has **0**. So the check enumerates 49 locks,
evaluates **0** claims, and review 1's proposed line said `OK — 0 stale of 49 examined`: a
headline claiming 49 and a parenthetical admitting 0. The disclosure was there; the verdict word
contradicted it. That is precisely the defect `check_pack_reachability.py:302-310` closed one day
earlier, in a comment that names the trap and its own relapse:

> *"0 verified is NOT 'OK'. Saying 'every pack reaches' after evaluating nothing is exactly the
> fail-silent-green this plan closes — and the fix for finding 13 briefly reintroduced it."*

**A working check and a dead one must not print the same line.** So:

```
# ≥1 lock was evaluable
OK — 0 stale of 213 plan lock(s) examined (6 non-terminal evaluated · 206 terminal · 1 unevaluable)

# nothing was evaluable — the hub today
NOTHING VERIFIED — 0 of 49 lock(s) were in an evaluable (non-terminal) state; this is an
  unasked question, not a pass
```

**Findings lead with a count line, because the gate truncates.** `final_gate.py:2092` (and `:1638`,
`:2104`, `:2113`) emits advisory output as `output[:500]`, and `:387` prints only
`output.split("\n")[:10]` with **no ellipsis and no "N more" marker**. `--json` is the mandated
completion gate, so 500 characters is the real budget — and review 1's own two-instance worked
example already consumed roughly 490 of them. A third finding would be cut mid-sentence with
nothing indicating anything was dropped. So the **first** line is always the census:

```
1 stale · 1 likely-stale · 0 half-applied · 1 orphan · 7 foreign · 2 plan-field-stale · 0 unknown-status · 0 unevaluable
```

Eight counters, one per label, always all eight — **including the zeros.** A census that prints
only non-zero categories cannot be distinguished from a census whose category was never computed,
which is the same fail-silent-green defect one level up.

Truncation may then cost detail; it can never cost the *existence* of a finding.

Then, one line each:

```
STALE LOCK: 2026-08-10-plan-1-deep-research.json is status:"active" but its plan is ARCHIVED —
  the plan's OWNER releases it (Finish step 5); if that run is confirmed dead the OPERATOR
  deletes the lock (fabrik-execute-plan.md:77). Never edit another session's lock.
LIKELY STALE LOCK: 2026-08-10-plan-1-quota-health.json is status:"active" but its plan reads
  Status: "EXECUTED" (docs/development/plans/…-quota-health.md) — same remedy, same owner
HALF-APPLIED FINISH: …-kaizen-m1… has completed_at:"2026-08-21" with final_commit absent —
  Finish step 5 landed one field of three
```

⚠️ **The remediation wording is a safety surface, and review 1's version was actively
dangerous.** It read *"release it (status:"released", completed_at, final_commit)"* — an
instruction addressed to whoever reads the gate output, who is usually **not** the lock's owner.
The locks are git-**tracked** (`git ls-files .fabrik/plan-locks/` → 49, not gitignored), so
following it means editing and committing a file authored by a concurrent session: the
`explicit-pathspecs` / never-commit-a-file-you-did-not-author HARD STOP, triggered *by the
enforcement check's own output*. It also contradicts the command twice —
`fabrik-execute-plan.md:77` gives the operator remedy as **delete** the lock file, and `:69-71`
forbids overwriting a completed lock at all (*"the lock's `completed_at`/`final_commit` is the
completion record; overwriting it destroys provenance"*). The spec's `NEVER auto-reclaims` rule
stopped the check from writing; nothing stopped it from *telling a reader to write*. Now the text
names the owner and the sanctioned action.

**Eight labels, and the operator can tell them apart at a glance.** Four are findings, four are
states the check must report *about itself*:

| label | kind | basis |
|---|---|---|
| `STALE LOCK` | finding | plan is archived — definitive |
| `LIKELY STALE LOCK` | finding | anchored status token — inductive |
| `HALF-APPLIED FINISH` | finding | field shape (timestamp without `final_commit`) |
| `PLAN FIELD STALE` | finding | missed Finish step-6 repoint |
| `ORPHAN LOCK` | self-report | plan-shaped lock, but no plan resolves for its stem |
| `FOREIGN LOCK` | self-report | not a plan lock at all (`holder` + `owned_paths:["**"]`) — out of jurisdiction, not judged |
| `UNKNOWN STATUS` | self-report | status value outside the writer's contract |
| `UNEVALUABLE` | self-report | plan resolved but its state could not be read |

A single undifferentiated `WARN` would collapse exactly the distinction that makes the inductive
limb safe to ship — and would collapse the finding/self-report split, which is the more important
of the two: **the last three are not defects in the repo, they are gaps in the check's own
knowledge**, and conflating "I found a problem" with "I could not look" is the fail-silent-green
class in miniature.

⚠️ **The finding line says ARCHIVED, not EXECUTED, and that wording is load-bearing.** Archived
does not imply finished: the live archive holds **8 plans reading `NOT_STARTED`, 2 `IN_PROGRESS`
and 1 `PLANNING`**. A lock on an abandoned plan should still be released — but a message
asserting "its plan is EXECUTED" would be *false* for eleven of them, and a check that states a
falsehood while reporting a true defect teaches the operator to distrust its other lines. If the
plan's status line is readable, quote it verbatim (`its plan is ARCHIVED (Status: NOT_STARTED)`);
if it is not, say so rather than inferring.

**`UNEVALUABLE` in particular is not hypothetical.** A lock can resolve to a plan whose state
cannot be read — measured on the live corpus, **7 archived plan-set directories contain no
`<dirname>.md` spine at all** and 4 more spines carry no `Status:` line. Those are not passes and
must never be counted as `terminal`:

```
UNEVALUABLE: <lock>.json → plan '<stem>' resolved to a directory with no spine file — lock
  lifecycle NOT verified for this entry
```

This is the predecessor check's hardest-won lesson carried forward rather than re-learned:
`check_pack_reachability.py` reports `examined_count`, `claim_pairs` **and** `unevaluable_types`
separately, and prints `NOTHING VERIFIED — 0 claim(s) could be evaluated` instead of `OK` when
nothing could be checked (`:253-255`, `:307-308`). **This check inherits both behaviours:** the
three counts are reported separately, and if every lock lands in `unevaluable` the line reads
`NOTHING VERIFIED`, never `OK`.

**The check NEVER auto-reclaims.** It reports; freeing another plan's lock is an operator
action. That rule is not decoration — it is what stopped this session from stomping a sibling,
and a detector that "helpfully" released locks would be strictly more dangerous than the defect
it detects.

## Rejected alternatives

| Alternative | Why rejected |
|---|---|
| **Auto-release a lock whose plan is EXECUTED** | Violates the D1/step-7 rule that freeing another plan's lock is an operator action. No agent-side signal distinguishes a dead run from one blocked on a long call; any staleness heuristic will eventually stomp a live sibling mid-slice, and two runs committing the same paths to shared `master` is the critical-failure case. The detector must stay a detector. |
| **Age-based staleness (non-terminal for > N days ⇒ stale)** | Time is not evidence, and here it is actively misleading: a `paused` lock waiting on a quota reset and a `blocked` lock waiting on an operator are *designed* to look old (§ status vocabulary). This repo already learned the equivalent lesson in `mail.py sweep` — archiving by AGE buries unread mail rather than handling it. Every rule above is decidable from the lock plus the plan's location or status, with no clock. |
| **Fold into `check_plan_tickets.py`** | Mixes a blocking contract gate with an advisory lifecycle report in one exit code; see above. `:949` also shows *why* the contract gate structurally cannot cover this: the lock is excluded from every ticket's declared write set by design, so it is never in scope for a spine↔ticket check. |
| **Leave `fabrik-catchup` probe 1 as prose** | This was the live alternative neither review considered until review 2 found the probe (§ Open / blocking unknowns). Rejected because prose an agent may or may not run is the exact failure mode this spec diagnoses in the lock protocol itself — the probe has been in that state since it was written. Making it executable IS this check. |
| **Make the write mechanical instead (a `plan_lock.py` acquire/release CLI)** | Genuinely better long-term and explicitly out of scope here — it changes `/fabrik-execute-plan`'s contract and needs its own spec. The detector is cheap, ships now, and its findings are the evidence for whether the bigger change is worth it. |
| **A pre-commit hook refusing a commit while a stale lock exists** | Wrong blast radius: the stale lock is usually another plan's, so it would block an innocent agent's commit for a defect they did not cause and cannot fix. |

## External dependencies

**None.** This is a stdlib-only repo-local check — `json`, `pathlib`, `re`, `argparse`. No
vendor, no API, no pricing, no rate limit, no third-party library. The BLOCKING live-research
gate (1a) is therefore vacuously satisfied, and that is stated plainly rather than dressed up
with irrelevant citations: there is no external fact in this design to get stale.

The approach space is likewise internal — "how should a fabrik enforcement check be shaped?" is
answered by the repo's own corpus, which is stronger evidence than any external article:
`check_vendored_drift.py` is the closest sibling (advisory, hub-aware, docstring naming the
measured class it closes) and is the template.

## fabrik-lib verdict

| Capability | Ladder verdict | Why |
|---|---|---|
| Validate a governance JSON state file's lifecycle | **BUILD** (project-local) | Read `/opt/fabrik-lib/README.md`: every module is a runtime APP capability (alerting, auth, credits, storage, pagination…). None covers repo-governance state validation, and none could be enhanced into it without changing what fabrik-lib is for. |
| 🆕 fabrik-lib candidate? | **No** | Fails the generic bar: this encodes fabrik's own plan-lock protocol. Governance machinery lives in `scripts/enforcement/` and is distributed by the governance-sync, not vendored from fabrik-lib — a different distribution channel for a different kind of artifact. |

## Shape / infra implications

No scaffold type, no `shape:` flag, no DB, no cache, no port, no container. But **"one script,
one test file, one line" understated the deliverable** — three hub-side registrations the gate
enforces were missing from it:

1. **The `# AFTER-EDIT:` header.** `check_script_headers.py:11` WARNs on any staged
   `scripts/**/*.py` without one; the predecessor carries it at `check_pack_reachability.py:2`.
   → `# AFTER-EDIT: tests/enforcement/test_plan_lock_release.py`
2. **The registration TIER, which decides whether the check runs at all.** `final_gate.py` gates
   by tier (`:884 if tier in (1, 2)`, `:1093 if tier == 2`, `:1306 if tier == 3`, and `:1089
   if tier == 1`). The stated template `check_vendored_drift.py` registers at `:876` — above
   every tier gate, so it runs in all modes. The actual predecessor
   `check_pack_reachability.py` registers at `:1151`, inside `if tier == 2`, so it is absent from
   `--lean`. **`--lean` is the mode agents run DURING execution — exactly when a lock is live —
   so this check registers at every-tier, alongside `check_vendored_drift.py`.** Note
   `WARN_ONLY_CHECKS` is populated as a side effect of the call (`:246-248`), so a tier-gated
   check is not even *listed* as advisory in the modes where it does not run.
3. **`liveness_audit.py:734`** picks the check up the moment it is registered
   (`_REGISTERED = re.compile(r'run_optional_check\(\s*"(scripts/enforcement/[a-z_0-9]+\.py)"')`),
   so a check that prints `OK` over a zero-evaluable corpus gets flagged there as vacuous — a
   second, independent reason the `NOTHING VERIFIED` branch is not optional.

## Constraints

- **Fleet-synced, and NO manifest edit is required — verified, not assumed.**
  `scripts/enforcement/` is a *recursive directory* in the manifest
  (`fabrik_synced_manifest.py:100-101`, expanded by `rglob("*")` at `:259-272`);
  `sync_enforcement_to_projects.py:453-476` walks it directly; `.pre-commit-config.yaml:69`
  carries a bare `^scripts/enforcement/` alternative in the governance-sync filter; and
  `final_gate.py` is `CORE_SCRIPTS[0]` under the same filter, so the script and its registration
  ship in one commit. ⚠️ **One caveat that bites here specifically:** the hook body guards on
  `if [ "$(pwd)" = "/opt/fabrik" ]` (`.pre-commit-config.yaml:67`), so committing this from a
  **worktree** fires no sync at all and the check reaches zero projects until
  `sync_enforcement_to_projects.py --force` is run from `/opt/fabrik`.
- It must be correct for a project with no `.fabrik/plan-locks/` at all — absent directory ⇒
  `0 examined`, exit 0, never a crash and never a false pass. **That is 30 of ~46 repos, not an
  overwhelming majority:** 16 repos carry locks.
- **ADVISORY (WARN) on landing** via `warn_only=True`. A check firing fleet-wide on day one is
  how a gate gets ignored.

  ⚠️ **"The corpus starts clean" was a HUB-ONLY claim and it is false fleet-wide.** Every number
  in this spec before review 2 came from `/opt/fabrik` alone — 49 of the 213 locks this check
  will actually judge. Measured across all 16 repos that carry locks (2026-08-26 ~13:30 UTC):

  ```
  $ fleet lock corpus
  fabrik 49 · fabrik-lib 45 · trade-intelligence 27 · tryton-crm 23
  brand-identiy-creator 16 · iterative_image_editor 12 · web-ecommerce-factory 9
  seo 8 · tojlo-mail 7 · youtube 6 · calendar-orchestration-engine 3 · transdoc 3
  meb / session-recall / site-provisioner / whatsapp-agent 1 each   → 213 total

  $ day-one output, all rules, read-only
  brand-identiy-creator  2026-08-10-plan-1-deep-research.json     active  STALE (plan archived)
  whatsapp-agent         plan-6-multitenant-whatsapp.json         paused  ORPHAN (no plan found)
  fabrik-lib             repo-lock-OBASAK-EB840-344494.json       active  FOREIGN (not a plan lock)
  ```

  **Two genuine findings across two repos, plus one jurisdiction miss** — and the third is the
  instructive one. `repo-lock-…` is `fabrik-lib`'s own repo-wide mutex, one of **7** such files
  there; without the `FOREIGN LOCK` classification (§ Open / blocking unknowns, item 1) all seven would have
  become permanent ORPHAN noise in a single repo on landing day, which is exactly the "fires
  fleet-wide and gets ignored" failure. **This is what the fleet measurement was for:** the
  hub corpus contains zero foreign locks, so nothing at `/opt/fabrik` could have revealed the
  class.

  Two real findings clears the noise bar comfortably. It also retires the VERIFICATION GAP below
  in the only way that counts: **rule 1 has a live positive case after all**, just not at the hub.
- Promotion to blocking is a separate operator decision once the fleet corpus is clean — it is
  not clean today (2 findings), so promotion is not on the table yet.
- **`warn_only=True` fails the gate on ANY non-zero exit** (`final_gate.py:221-248`). Every
  failure path — unreadable JSON, a malformed lock, a missing plans dir — must return 0 with an
  honest line, never a traceback. This plan's predecessor hit that class five separate times;
  the check must catch the CLASS (any exception ⇒ "could not evaluate this lock", named), not
  enumerate exception types.
- **Never auto-reclaim.**
- **State the denominator** on success, and distinguish "0 stale of 49 examined" from "0 locks
  found" — a silent pass is only honest when it says what it examined.
- **A lock the check could not evaluate is never counted as clean.** `unevaluable` is its own
  reported bucket (missing spine, unreadable status, unparseable JSON), and an all-unevaluable
  run prints `NOTHING VERIFIED`, not `OK` — carried from `check_pack_reachability.py:253-255`
  and `:307-308` rather than re-learned. This is the same repo-wide class as `warn_only` above,
  seen from the other side: the exception guard keeps the check from going *red* dishonestly,
  this keeps it from going *green* dishonestly.
- **Assume no field exists, and do not enumerate KEY names either.** The 49 hub locks carry
  **35 distinct keys** between them; `completed_at` appears in 40 and `final_commit` in only 28.
  Every field read is a `.get()` with an explicit absent-case, and "absent" is never conflated
  with "null". ⚠️ **The don't-enumerate doctrine applies to the key axis too, and rule 2 broke
  it:** three locks record completion under `finished_at` and one under `released_at`, not
  `completed_at` — the same half-applied Finish, invisible to a rule that names one key. Treat
  `completed_at | finished_at | released_at` as the completion-timestamp **family**. This is the
  spec's own warning at § status vocabulary, committed one axis over — for the third time in this
  document's history.

## Open / blocking unknowns

**RESOLVED**

- *Does an existing check already do this?* **The honest answer is no longer a clean "no", and
  both reviews got here by searching too narrowly.** Review 1 read the two *lock* consumers.
  Review 2 added the *plan-status* consumer (`check_convergence.py` — see rule 1B). Neither
  searched the **command corpus**, and that is where the real answer was:

  **`commands/_sources/fabrik-catchup.md:47-60` probe 1 already specifies rule 1 verbatim** —
  *"a lock whose `plan` path resolves INTO `docs/development/plans/archived/` while its `status`
  is still `"active"` (an abandoned run archived by hand without releasing the lock)"* — plus the
  false-positive suppression this spec re-derived from scratch (*"**Not a finding:** a lock
  pointing INTO archived/ with a terminal `status` is the normal end state"*), plus an answer to
  the question this spec still carries as STILL-OPEN #1 (*"a lock whose `plan` path does not
  resolve on disk"*), plus two contradiction classes this spec does not have at all (spine
  `IN-PROGRESS` with a non-active lock; spine `DRAFT`/`CONVERGED` with an active lock).

  **So this check is not new work — it is the executable backing for a probe that already exists
  as prose.** That reframing is strictly better than the "novel check" framing: prose that an
  agent may or may not run is precisely the failure mode this spec diagnoses in the lock protocol
  itself (§ Why), and probe 1 has been sitting in exactly that state. **The check therefore
  adopts `fabrik-catchup` probe 1's taxonomy verbatim rather than inventing a parallel one**, and
  cites it as the contract. Two governance surfaces disagreeing about what "stale lock" means —
  each synced to ~46 repos — is a worse outcome than either one alone.

  Note probe 1 also fixes the terminal set the same way review 2 did independently: it says
  terminal = `released`/`complete`, never "anything but active".
- *Have we tried and rejected this before?* Searched `session-recall` for the lock/scope/BLOCKED
  vocabulary; the only hits are other sessions reading the command text itself. No prior
  decision, no rejected approach, no wall already hit.
- *How should the plan be resolved from a lock?* By filename stem against both `plans/` and
  `plans/archived/`, per `check_plan_tickets.py:1481`'s existing convention — the `plan` field
  is a hint, not a path.

**⚠️ VERIFICATION GAP — RETIRED by review 2, and the way it was retired is the lesson.** Review 1
recorded that rule 1 had *"no positive case left on live data"*, because both motivating
instances were freed hours earlier and the hub corpus holds **zero** active locks. That was true
of the hub and false of the world: the fleet carries non-terminal locks continuously, and
`brand-identiy-creator/2026-08-10-plan-1-deep-research.json` is a **live, unfixed instance of
rule 1** — `status:"active"` with its plan archived. (Stated without an aggregate count on
purpose: the fleet-wide `active` total changed twice during this review as sibling sessions
took and released locks, so a count here would be stale before the spec was committed. The
named instance is the durable evidence; the aggregate lives in the timestamped snapshots.) The gap was never a property of
the defect; it was a property of where review 1 stopped looking. *(The lock belongs to another
repo and is left untouched — reporting it is the whole point; freeing it is the operator's.)*

Synthetic fixtures are still mandatory, because most of the twelve shapes below have no live
instance anywhere and a rule verified only by silence has never been seen to work. But the suite
now also gets a **live end-to-end assertion**: run the check against a copy of
`brand-identiy-creator`'s lock corpus read-only and assert it finds exactly that lock.

**Twelve fixtures, not one**, because the corpus proves twelve distinct shapes exist and the hub
can exercise none of them (no non-terminal locks left). Four are **negative** — the check must
be proven NOT to fire, or not to claim jurisdiction:

| # | fixture | expected |
|---|---|---|
| a | `active` + stem resolves under `plans/archived/` | `STALE LOCK` |
| b | `active` + `completed_at` set + `final_commit` **absent** (not null) | `HALF-APPLIED FINISH` |
| c | `active` + plan under `plans/` with `**Status:** ✅ EXECUTED 2026-08-14` | `LIKELY STALE LOCK` |
| d | `active` + archived plan reading `Status: NOT_STARTED` | flagged, message quotes `NOT_STARTED` — never asserts `EXECUTED` |
| e | `active` + archived plan-set dir with **no spine file** | `UNEVALUABLE` — never counted `terminal` |
| f | `active` + plan whose status is `Issue 1 RESOLVED (§2.8) … not yet ENABLED` | **NOT flagged** — the substring false positive |
| g | `paused` (quota) or `blocked` lock on an un-archived, unfinished plan | **NOT flagged** — the sanctioned carve-out, both status spellings |
| h | `paused` lock whose plan IS archived | **flagged** — non-terminal gates the rule; it is not itself the finding |
| i | lock with `status:"finshed"` (a typo) | `UNKNOWN STATUS` — never silently counted terminal |
| j | `active` + `finished_at` set + `final_commit` absent | `HALF-APPLIED FINISH` — the key-name family, not just `completed_at` |
| k | lock whose `plan` field does not resolve, stem does | `PLAN FIELD STALE` — and the lock still evaluated normally |
| l | `repo-lock-<host>-<pid>.json` with `holder` + `owned_paths:["**"]` and a prose `plan` | `FOREIGN LOCK` — counted, **not** judged, never ORPHAN |

(f), (g), (i) and (l) matter most: they are the only fixtures that can catch the check becoming *too
eager* or silently *too green*, and a suite of positive-only fixtures would pass a check that
flags everything. (e) and (h) are the ones a first implementation silently gets wrong — (h)
especially, because "non-terminal ⇒ suspicious" and "non-terminal ⇒ eligible for the rules" are
easy to conflate.

**STILL OPEN — each with its resolution step**

1. ~~**Should a lock whose plan file cannot be found at all be reported?**~~ **CLOSED by review 2
   — it was never open.** `fabrik-catchup.md:55-56` already answers it: *"a lock whose `plan` path
   does not resolve on disk"* is a probe-1 finding. This spec carried it as an open question for
   two reviews only because neither searched the command corpus. **Resolution (adopted, not
   invented): report it as `ORPHAN LOCK: no plan found for <stem>`**, matching probe 1's taxonomy.

   ⚠️ **The "noise risk is zero" reassurance was hub-only, and the fleet answer is worse than
   "one" — there is an entire lock CLASS this spec does not own.** 25 of 213 fleet locks (12%)
   are not named `YYYY-MM-DD-plan-N-<slug>`, and they split into two very different groups:

   - **Undated plan locks** (`tojlo-mail/plan-3-membrane.json`, `youtube/api-smoke-test.json`,
     `meb/flashcard-apk-phase1.json`, …, 18 of them). Real plan locks; stem resolution works
     normally. Not a problem — but proof the `YYYY-MM-DD-plan-N` stem is a hub convention, not a
     fleet invariant, so **nothing may parse the filename for a date or a plan number.**
   - **`repo-lock-<HOST>-<PID>.json` — 7 in `fabrik-lib`, a DIFFERENT protocol entirely.** They
     are repo-wide advisory mutexes, not plan locks:

     ```json
     { "plan": "(repo-wide action) port the hub Stop hook + add 2 enforcement checks",
       "owned_paths": ["**"], "status": "active",
       "holder": "OBASAK-EB840:344494", "reason": "…" }
     ```

     The `plan` field holds **prose**, not a path or a stem. No plan exists or ever will. Under
     the specced rules all 7 become **permanent ORPHAN findings, forever, in one repo** — the
     "fires fleet-wide and gets ignored" failure, concentrated.

   **So the check must first decide whether a lock is even in its jurisdiction.** A lock carrying
   `holder` and `owned_paths: ["**"]` with a non-resolving, separator-free `plan` value is a
   foreign lock, not a stale plan lock. It gets a fifth self-report label — `FOREIGN LOCK:
   <name> is not a plan lock (no resolvable plan, holder=<h>) — not judged` — counted in the
   denominator, explicitly **not** judged. Claiming jurisdiction over another protocol's state
   file and calling it stale would be this check's own version of the over-reach it was written
   to catch.
2. **Promotion from WARN to blocking — or deletion.** Deliberately out of scope to decide here,
   but NOT left open-ended, because "advisory forever" is how a check becomes wallpaper (§ Goal).
   **Resolution: the check's own docstring records both exits as named triggers, so the next
   agent reads them without re-deriving this discussion —** (a) **promote to blocking** once it
   has run with zero findings across the fleet for two consecutive weekly syncs, an operator
   decision; (b) **build the mechanical writer and delete this check** if it catches **more than
   two NEW instances after landing** — a third means detection is not changing behaviour and only
   removing the prose write will. Two counters, two named outcomes, no indefinite middle.

   ⚠️ **"NEW" is doing real work in (b), and (a) and (b) are not symmetric.** The day-one findings
   (2, § Constraints) are inherited debt, not evidence — counting them would satisfy the deletion
   trigger on the morning the check ships. The counter starts after they are dispositioned. And
   note (a) cannot fire before those two are fixed, since it requires a clean fleet: the check's
   first job is to get its own corpus to zero, and only then does the clock on either exit start.

---

## Review history — TWO reviews, and the second one mattered

### Review 2 — `/fabrik-spec-review`, 2026-08-26

Re-invoked by the operator on an **unchanged** spec that review 1 had marked `CONVERGED`. It was
not a rubber stamp: **four passes, ~44 corrections, seven of them design-changing.** Review 1's
verdict did not hold, and *why* it did not hold is the finding worth keeping — **every single
miss came from measuring the wrong population.** Review 1 measured the hub corpus and called it
the vocabulary; it read the `.py` consumers and called that the prior art; it checked the hub
locks and called the corpus clean. Each conclusion was correct about what it sampled and wrong
about the world.

**The seventh design change came from the pass that was supposed to be a no-op.** Re-running the
fleet probe at the close found the corpus had moved (212 → 213 locks, a sibling took one at
10:17) and surfaced a class no earlier pass had seen: **25 of 213 fleet locks are not
`YYYY-MM-DD-plan-N` shaped, and 7 of those are `fabrik-lib` `repo-lock-<host>-<pid>.json` files
— a different locking protocol entirely**, with `holder`, `owned_paths:["**"]` and a prose
`plan` value. Under the rules as written at that moment, all 7 would have become permanent
`ORPHAN` findings in one repo on landing day. They now get a `FOREIGN LOCK` label: counted, out
of jurisdiction, not judged. **The confirming pass earned its place** — the spec's own doctrine
is that the pass which makes edits is never the last, and this is the run where that paid.

⚠️ **Pass 3 was not cleanup — a third of the corrections were self-inflicted by passes 1 and 2.**
Cutting rule 1's status test created a coverage regression; retiring the VERIFICATION GAP left a
paragraph still citing it; adding the fleet measurement falsified two "currently zero" claims
elsewhere; adding `PLAN FIELD STALE`, `UNKNOWN STATUS` and `UNEVALUABLE` left a label census
listing five of seven and a heading calling `unevaluable` "the third bucket"; and the deletion
trigger "if it fires more than twice" was written *before* the fleet measurement found exactly
two findings on day one — it would have been satisfied on the morning it shipped. **A large-edit
pass reliably breaks its own document's internal consistency**, which is precisely why the
termination contract forbids exiting on the pass that made edits.

**Layer honesty:** the pool breadth layer was dispatched twice and returned nothing usable — the
first run died on a result-shape bug in the dispatch harness, the second hung past 45 minutes and
was killed. This review therefore ran on one native Opus grounder plus the reviewing session's
own measurements, **not** the pool+native floor the command specifies. Recorded rather than
papered over: the breadth layer is missing, and a third review would not be redundant.

**The five that changed the design:**

1. **`paused` and `blocked` are prescribed, NON-terminal lock states** (`fabrik-execute-plan.md`
   `:459`, `:563`), so review 1's centrepiece axiom — *"key on `active`, treat EVERY other value
   as terminal"* — silently counts mid-flight runs as finished. It reached that axiom from the
   corpus; the answer was in the writer. The fleet has a live `paused` lock today. The partition
   is now writer-derived, with an `UNKNOWN STATUS` third class for anything unrecognised.
2. **`fabrik-catchup.md:47-60` probe 1 already specifies rule 1 verbatim**, plus the
   false-positive suppression this spec re-derived from scratch and an answer to its STILL-OPEN
   #1. Neither review searched the **command corpus**. The check is not new work — it is the
   executable backing for a probe that has been sitting in prose exactly as unenforced as the
   lock protocol it audits.
3. **Rule 1's `Status: EXECUTED` test repeated the enumerate-from-partial-data trap** review 1
   congratulated itself for fixing on the lock-status axis, one screen higher (28 matched, 39
   finished plans missed) — **and cutting it outright, this review's first instinct, was also
   wrong** (7 finished plans sit un-archived). Measuring caught the regression the fix
   introduced. The answer was **anchoring**: 66 hits, 6 substring-only cases correctly excluded,
   0 errors either way. A hardened version of that matcher already existed at
   `check_convergence.py:122-126` — the spec was one step from shipping a FOURTH status parser,
   the exact duplicate-parser class its own predecessor plan existed to close.
4. **The corpus was never clean — that was a hub-only claim.** 213 locks across 16 repos, not 49;
   running both rules fleet-wide read-only finds **2 real day-one findings**, including a live
   `active` lock on an archived plan in `brand-identiy-creator`. This retires review 1's
   "VERIFICATION GAP" (rule 1 has a live positive case after all) and gives the
   "would it fire everywhere on day one?" constraint an actual number.
5. **`OK` was the wrong word.** Every rule gates on a non-terminal lock; the hub has zero, so the
   check evaluates **0** claims and review 1's line still said `OK — 0 stale of 49 examined`.
   A working check and a dead one printed the same string — the fail-silent-green class
   `check_pack_reachability.py:302-310` had closed the day before.

**And one that was a safety defect, not a design one:** the finding text said *"release it
(status:"released", completed_at, final_commit)"* — addressed to whoever reads the gate, who is
usually not the lock's owner. Locks are git-tracked, so following it means committing a
concurrent session's file: the never-commit-what-you-did-not-author HARD STOP, triggered by the
check's own output. It also contradicted `fabrik-execute-plan.md:77` (the operator remedy is to
**delete**) and `:69-71` (overwriting a completed lock destroys provenance).

**Twelve more, each grounded:** the 500-char/10-line advisory truncation that would silently drop
a third finding (`final_gate.py:2092`, `:387`) → a census line first · `PLAN FIELD STALE` as a
third rule, since Finish step 6 mandates repointing `plan` and 2 locks show it missed ·
`check_phase_tests.py:61` mis-resolves by raw-join, a *different* bug from the one design input 3
generalised to both consumers · design input 1's bare-name evidence no longer reproduced
(commit `17f00754` overwrote it) · the completion-timestamp **key** family
(`finished_at` ×3, `released_at`) — the don't-enumerate doctrine broken on the key axis · the
registration tier, which decides whether the check runs in `--lean` at all · the missing
`# AFTER-EDIT:` header · `liveness_audit.py:734` auto-registering it as a vacuity candidate ·
the `:949` line annotated `READS` though it never opens a lock · the message asserting `EXECUTED`
where the evidence was only `ARCHIVED` (false for 11 archived plans) · the missing `unevaluable`
bucket · and the command's own self-contradiction about whether a blocked run's lock is `active`
or `blocked` (filed, not fixed here).

### Review 1 — `/fabrik-spec-review`, 2026-08-25

Edit-free md5-verified no-op round (`aea589ae4c38e0f456c04441d0842128` before == after). Four
corrections, each caught by executing a claim rather than reading it:

1. **Rule 2 would have fired on 14 healthy locks.** Unscoped, `completed_at` without
   `final_commit` is the ordinary shape of a FINISHED lock (13 `released` + 1 `complete`), not a
   half-applied Finish. The rule needed `status == "active"` scoping the first draft omitted —
   and landing it unscoped would have committed the exact "fires fleet-wide on day one, gets
   ignored" failure the spec itself warns against.
2. **The status vocabulary was stated twice from partial data** — first as binary, then as three
   values — before being measured at FOUR (`active`/`released`/`executed`/`complete`). Both
   rules now key on `active` and treat everything else as terminal, so a fifth value needs no
   code change. Enumerating the values would have been the same instance-by-instance trap the
   predecessor plan hit four times.
3. **The corpus is 49 locks, not 21** — the number the spec's own example denominator used.
4. **The reader grep returns four files, not three**; the fourth is a string-literal guard that
   never opens a lock. A spec whose value is "these claims were executed" must show what the
   command actually prints.

Plus one gap named rather than papered over: **rule 1 has no positive case left on live data**,
because both motivating instances were freed hours before this review. Its test must therefore
build a synthetic fixture — a rule verified only by silence on a clean corpus has never been
seen to work.

---

**CONVERGED** — review 2, 8 passes, edit-free md5-verified no-op (`6b853a48…` before == after).

| pass | what it re-checked | raised | new | edits |
|---:|---|---:|---:|---:|
| 1 | full read + all 4 embedded probes | 9 | 9 | 9 |
| 2 | native-Opus grounder merge + first fleet-wide execution | 12 | 12 | 11 |
| 3 | full internal-consistency read | 13 | 13 | 13 |
| 4 | probes re-run → corpus drift + the `FOREIGN LOCK` class | 10 | 10 | 10 |
| 5 | probes + every numeric claim swept | 2 | 2 | 2 |
| 6 | `§` cross-reference resolution | 1 | 1 | 1 |
| 7 | probes + drift re-check | 1 | 1 | 1 |
| 8 | all probes + `check_convergence` green | 0 | 0 | **0** ✓ |

`new:` falls 9 → 12 → 13 → 10 → 2 → 1 → 1 → 0; no stall, and the terminal row is a genuine
quiet pass, not merely an edit-free one. Durable probes re-run at the close and reproducing
verbatim: 4 reader files · 0 writers · 49 hub locks · rule 2 unscoped 14 `{released 13,
complete 1}` · naive `^Status: EXECUTED` 28 · anchored 61 archived / 5 substring-only ·
188 plan-shaped vs 25 other fleet locks · `brand-identiy-creator`'s stale lock still `active`.

⚠️ **Coverage this review did NOT have:** the pool breadth layer returned nothing usable (two
dispatches, one harness bug, one hang). One native Opus grounder plus the session's own
measurements carried it. A third review would not be redundant.
