## ⚠️ Autonomous run contract — finish the gauntlet, don't pause (READ FIRST — the rule agents skip)

This certification runs **start→finish in ONE invocation, fully autonomously.** You do NOT pause to ask, to
narrate progress, or to hand control back so the operator can say "continue." The operator invoked this
because they want a *finished* certification, not a conversation — **stopping to ask is the failure this
contract exists to prevent.** Permitted output between start and finish is a one-line-per-round ledger and
the final report; never "shall I continue / proceeding unless you redirect."

**Self-service EVERY uncertainty — in this order — before it can even become a question:**
1. {{SELF_SERVICE}}
2. the `.windsurf/rules/` packs (the surface pack + core) — binding on how the product must behave
3. `docs/` (QUICKSTART / OPERATIONS / CONFIGURATION / TROUBLESHOOTING) + `AFCL.md`
4. `grep` / `Read` the codebase — the router / handler / schema / the actual symbol
5. research online — `mcp__context7` for a library/API detail → `WebSearch` / `WebFetch`; cite the URL

Only a question that **materially changes what "correct" means** AND that all five sources fail to settle may
even be considered — and if it truly stops you establishing the oracle to run at all, that is the pre-start
refusal below, never a mid-run chat. Everything else: **decide with the house rules, note it in one line the
operator can override, and keep going.**

**Fix or hand off — BOTH are autonomous and NON-BLOCKING; neither is ever a reason to stop:**
- a defect you own ({{OWN_FIX}}) → prove-before-fix (red→green), keep going.
- a defect you do not own ({{HANDOFF}}) → write the failing repro test, **commit it red**, route it to the
  owning `/fabrik-review` / plan, and **keep going.** A handoff is a logged routing action, never a halt —
  the run does not wait for the other owner mid-sweep, and the gauntlet continues on everything else.
  **Where a Phase 6 exists (the certification gauntlets), the routes are EXECUTED there in this same run,
  in fresh dispatched contexts** — deferred sequencing, never exported work.

Classify by ownership **honestly** — a defect you own (the {{OWN_FIX}} list) terminates FIXED; never re-label
it a handoff to dodge the fix loop.

There is **no** "noted / I'll ask about this / defer to the operator / good enough for now" bucket — that is
the exact stall this kills. "I judged this worth asking," "running low on context, I'll finish later," "the
core is covered, the rest can wait" are contract violations, not decisions. (Context is not a reason: the
harness AUTO-COMPACTS long conversations and the run continues — your durable-as-you-go artifacts are what
make that seamless. Dressing the context excuse as a BLOCKED report does not legitimize it.)

**A HARD STOP always overrides — this contract AND the Termination contract below; it is never a "routable
finding," and it is the one thing that outranks "never pause."** If you discover mid-run that a seam actually
touches **production / shared-VPS data**, or that a scenario would fire a **destructive action against real
data**: **abort that action and HALT the run immediately** in the `BLOCKED:` format — you have lost the
test-isolation precondition, so you can no longer safely certify. This is the one legitimate early exit that
may leave checklist rows `UNCHECKED` (safety outranks coverage); resume only once a safe, isolated
environment is restored. "Never pause" never authorizes writing to real data — safety outranks autonomy, always.

**Otherwise** (absent the safety HARD STOP above, which is the only thing that halts the whole run mid-loop),
**stop ONLY on an absolute-must**, in the format `BLOCKED: <what> — searched: <sources checked> — missing:
<need>`. There are exactly two, and **neither halts the whole run on a single finding** — one pauses a lone
finding, the other refuses before the loop begins:

*In-loop, mid-run* (governed by the Termination contract **below**): the loop's only non-quiet stop is a
specific finding that survived **3 consecutive fix attempts** (the same test failing three times) — and even
that only **pauses THAT finding while you keep looping on everything else**, never the whole run. Any other
finding — a contract↔code contradiction on one field/flow, a degradable gap — is **routed, not halted:**
refute it, or terminate it FIXED / HANDED-OFF per Phase 4, and keep going. (A FROZEN-contract conflict is a
re-freeze handoff to the owning contract command, not a run-stop.)

*Pre-start refusal* (Phase 0 "Ground truth, or refuse" — you cannot establish the oracle to run the gauntlet
**at all**, so there is no loop to enter): the app/service will not start, OR there is no isolated test
dataset/seam and you cannot seed one, OR a required backing service is truly absent. This is the one refusal
that predates the loop — never a stop within it.

**Degradable gaps are NEITHER stop:** the pool 402/quota, or a test-only dependency you can't seed (a
mail-catcher, a sandbox key), is a BLOCKED-**env FINDING** you record and route around INLINE so coverage
doesn't suffer; a paid external with no sandbox is a recorded BLOCKED-**env FINDING you SKIP** — **never spend
real operator money to manufacture a red.**

**Interruption is recoverable — the gauntlet RESUMES, it never restarts from scratch.** Every unit of
progress is durable the moment it lands: the persisted review file (the adjudicated checklist + ledgers),
the committed specs under `tests/` (the rerunnable suite), each fix's commit, and per-agent output dirs.
On re-invocation after a crash / quota-hit / disconnect / kill, the Termination contract's Anchor step reads
the newest review file for this scope and **re-adjudicates from where it stands**: rows already CLEAN /
FIXED / REFUTED with evidence are banked (spot-verify, don't redo); `UNCHECKED` rows and un-run matrix cells
are the remaining work; committed specs re-run cheaply as regression proof. Update artifacts **as you go**
(after each round, not only at the end) — an artifact written only at the end is the resume state a crash
destroys. Dead subagents' partial output dirs are evidence to harvest, not to re-earn.

**Dispatched subagents run their suites SYNCHRONOUSLY.** A subagent that backgrounds a test/suite run or arms
a Monitor and then waits for a notification **stalls until its budget is exhausted** — background/Monitor
signals do NOT deliver to a subagent. Every gauntlet subagent runs its
suite as a plain synchronous shell call with a generous timeout and reads the exit output; if a suite is too
slow for one call, it **splits its scope** and runs each slice synchronously. Dispatch each agent with an
explicit "run synchronously; never background a run or wait on a Monitor/notification" instruction.
