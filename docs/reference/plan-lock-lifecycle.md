# Plan-lock lifecycle

**What this covers:** `.fabrik/plan-locks/<plan-id>.json` — what writes it, what reads it, the
states it moves through, and the advisory gate (`scripts/enforcement/check_plan_lock_release.py`)
that reports a lock a finished plan is still holding.

**Fleet-synced.** The check ships to every governance-synced project. This doc is the reference for
all of them.

---

## Why the lock exists, and why it needs a detector

The lock is what lets several scoped plan runs share one project without colliding, and what makes
a run resumable after a crash. `/fabrik-execute-plan` step 7 scans for an overlapping `active` lock
before starting; an overlap is a hard `BLOCKED`.

**The protocol has three readers and zero writers.** Nothing in `scripts/` or `.claude/hooks/`
creates or releases a lock — it is written by an agent following a paragraph, and released by an
agent following another paragraph at the tail of a long run:

| Consumer | What it reads the lock for |
|---|---|
| `scripts/enforcement/check_plan_tickets.py:561`, `:1470` | `baseline_commit`; which plan dirs are in play |
| `scripts/enforcement/check_phase_tests.py:36`, `:44-46` | active locks with a baseline, to scope phase tests |
| `.claude/hooks/final_gate_stop.py:785` | whether an authored lock is `active` (Stop-hook arming) |

Every one of them reads. So a missed release is **silent** — until days later, when an unrelated
agent hits `BLOCKED: scope overlap` at step 7 on paths it does not own and cannot free. Two measured
instances (2026-08-25): one lock held ten high-traffic hub paths for **thirteen days**; another
blocked a plan until the operator ruled.

`commands/_sources/fabrik-catchup.md:47-60` probe 1 already specified the rule — in prose, which is
exactly as unenforced as the protocol it audits. This check is that probe made executable.

## The status vocabulary

**Derived from the WRITER's contract, not from whatever the corpus happens to contain.**
Reading the corpus alone yields only the values that already exist and silently counts a paused run
as finished.

| Class | Values | Treatment |
|---|---|---|
| **non-terminal** | `active` · `paused` · `blocked` | mid-flight — all rules apply |
| **terminal** | `released` · `executed` · `complete` · `completed` | finished — skipped |
| **unrecognised** | anything else | `UNKNOWN STATUS` — never silently terminal |

- `paused` — `/fabrik-execute-plan:459`: a quota-exhaustion pause. The Board is preserved and the
  spine stays IN-PROGRESS. On a box where accounts hit weekly quota every few days, this is the
  *routine* interruption, not an exotic one.
- `blocked` — `:563`: an orderly halt; the lock is retained with the ticket map for inspection.
  ⚠️ The command contradicts itself here — step 7 says a lock left **`active`** by an orderly
  BLOCKED halt is intentional, while `:563` says the halted lock is retained as **`blocked`**. Both
  shapes exist in the wild; both are non-terminal, and neither is a finding on its own.
- The comparison is **case-folded**. A live upper-case `"RELEASED"` lock exists in `tryton-crm` on a
  correctly archived plan; un-folded it would report as `UNKNOWN STATUS` on every gate run there.

**A non-terminal lock is not itself a defect.** `paused` and `blocked` are sanctioned steady states
and may be held indefinitely. Non-terminal only makes a lock *eligible* for the rules below.

## What the check reports

Eight labels — four findings, four self-reports about the check's own knowledge.

| Label | Kind | Basis |
|---|---|---|
| `STALE LOCK` | finding | the plan lives under `plans/archived/` — definitive |
| `LIKELY STALE LOCK` | finding | un-archived plan whose `Status:` value *begins with* a finished token — inductive |
| `HALF-APPLIED FINISH` | finding | a completion timestamp set with `final_commit` absent |
| `PLAN FIELD STALE` | finding | the stored `plan` value no longer resolves (a missed Finish step-6 repoint) |
| `ORPHAN LOCK` | self-report | plan-shaped lock, but no plan resolves for its stem |
| `FOREIGN LOCK` | self-report | not a plan lock at all — out of jurisdiction, counted, never judged |
| `UNKNOWN STATUS` | self-report | a status value outside the writer's contract |
| `UNEVALUABLE` | self-report | the plan resolved but its state could not be read |

The census line prints **first, always all eight, including the zeros** — `final_gate.py:2092` ships
advisory output as `output[:500]` and `:387` prints ten lines with no ellipsis, so a finding without
a leading census can be truncated into invisibility. A counter that prints only when non-zero is
indistinguishable from a counter that was never computed.

### Three verdicts, and why the ordering matters

- `FINDINGS` — at least one of the four findings. **This outranks everything.**
- `NOTHING VERIFIED` — no lock was in an evaluable state. *An unasked question, not a pass.*
- `OK` — at least one lock was evaluated and nothing was found.

⚠️ **`FINDINGS` must outrank `NOTHING VERIFIED`.** `STALE LOCK`, `HALF-APPLIED FINISH` and
`ORPHAN LOCK` are all emitted on paths where the lock is *not* evaluable, so an ordering that let
"nothing was evaluable" win produced a run that printed `1 stale` in the census and *"nothing was
verified — this is an unasked question, not a pass"* on the very next line, with the finding, its
detail and the remedy never printing at all. That shipped in development and was caught by the
Phase-A review; `test_findings_print_even_when_nothing_was_evaluable` pins it.

**A repo with no `.fabrik/plan-locks/` prints nothing at all** — 30 of ~46 synced repos have none,
and `warn_only` implies `advisory`, so stdout is shown on every pass. A `NOTHING VERIFIED` block
there would be permanent noise.

## Anchoring, and why the token list is safe

`LIKELY STALE LOCK` needs to know whether a plan's prose status means "finished". The vocabulary is
not standardised — plans say `EXECUTED`, `COMPLETE`, `COMPLETED`, `CLOSED`, `DONE`, `SHIPPED`,
`FIXED`, `SUPERSEDED`, `IMPLEMENTATION-CONVERGED`, most behind a bold `**Status:**` and many behind
a `✅`.

The rule that makes a token list safe is **anchoring**:

1. take the **first** `Status:`-shaped line, after **stripping fenced blocks**;
2. strip leading decoration (`**`, `✅`, `🚧`, whitespace);
3. require the token at the **START** — never a substring search.

Each clause is load-bearing and each was measured:

- *Anchored, not substring* — `Issue 1 RESOLVED (§2.8). **Phase B complete + live-validated.**` is a
  real, **unfinished** fleet plan. A substring search returns `COMPLETE`.
- *First, not last* — five live fleet plans carry more than one `Status:`-shaped line, and two flip
  verdict between the first and the last.
- *Fence-stripped* — `site-provisioner`'s plan contains `status: Mapped[str] = mapped_column(`
  inside a code fence. Unstripped, that parses as the plan's status.

`RESOLVED` and `CONVERGED` are deliberately **absent** from the token set: the first is how this
repo labels a resolved issue inside an unfinished plan, and a converged plan is ready to execute,
not executed.

## Jurisdiction: `FOREIGN LOCK`

`fabrik-lib` keeps seven `repo-lock-<host>-<pid>.json` files in the same directory. They are
repo-wide advisory mutexes from a **different protocol** — `holder`, `owned_paths: ["**"]`, and a
`plan` field holding a prose description rather than a path.

The discriminator is **`holder` present AND `owned_paths == ["**"]`** — never the plan value's
shape. Across the whole fleet those two signals agree perfectly (7 both, 207 neither, zero mixed),
and one of the seven carries a `/` inside its prose, so a shape-based test sends it to
`ORPHAN LOCK` — exactly the noise this class exists to prevent.

Foreign locks are **counted in the census and never printed as lines**: seven per run, forever, in
the one repo that owns them, would be noise rather than signal.

## Resolution: by stem, four ways

The `plan` field cannot be followed literally. Measured across the fleet: most locks store a path,
some store a bare stem, and some store a path that went stale when the plan was archived. So the
plan is resolved by filename **stem**, four ways in order:

```
plans/<stem>.md · plans/<stem>/<stem>.md · plans/archived/<stem>.md · plans/archived/<stem>/<stem>.md
```

This is **this check's own design decision, not an inherited convention** —
`check_plan_tickets.py:1481` resolves one location gated on `is_dir()`, which misses every
single-file `.md` plan.

The stored field is then checked separately, and a mismatch is `PLAN FIELD STALE` — **scoped to
non-terminal locks**. Unscoped it fires on 37 of 203 path-storing fleet locks, 35 of them terminal:
dead history on finished work, and re-pointing a released lock's field would destroy the provenance
`fabrik-execute-plan.md:69-71` protects. An absolute or `..`-bearing value is rejected rather than
probed — `Path("/a") / "/b"` is `/b`, so an unguarded probe declares a lock healthy on the strength
of a file in a **different repo**.

## Remediation — who acts

The check **never auto-reclaims**. Freeing another plan's lock is an operator action
(`fabrik-execute-plan.md:73-78`), and the finding text names the owner and the sanctioned action:

> the plan's OWNER releases it (Finish step 5); if that run is confirmed dead the OPERATOR deletes
> the lock (`fabrik-execute-plan.md:77`). Never edit another session's lock.

The wording is a safety surface, not a courtesy. Locks are **git-tracked**, so a bare "release it"
addressed to whoever reads the gate output instructs a never-commit-what-you-did-not-author
violation — from the check's own output.

## Contract

- **Advisory** (`warn_only=True`), registered **every-tier** in `final_gate.py`, above the
  `# ── Tier 1` marker. `--lean` is the mode agents run *during* execution, which is exactly when a
  lock is live, so a tier-gated registration would be absent precisely when the check matters.
  `tests/enforcement/test_final_gate_registration.py` pins the placement and rejects **any**
  `if tier …` ancestor — an `Eq`-only pin waves through `in (1, 2)` and `>= 2`.
- **Always exits 0**, findings included. `final_gate.py:262-270` converts a non-zero exit from a
  `warn_only` check into a **blocking red**, which on a governance-synced check means ~46 repos.
  Unknown flags are tolerated (`parse_known_args`) for the same reason.
- **stdlib only** — `json`, `pathlib`, `re`, `argparse`.
- CLI: `--project-root PATH` (default cwd) · `--json`.

## Two named exits — this check is not meant to live forever

- **PROMOTE to blocking** once it has run with zero findings across the fleet for two consecutive
  weekly syncs. Operator decision.
- **DELETE it and build the mechanical acquire/release writer** if it catches more than two NEW
  instances after landing (day-one inherited debt does not count). A third instance means detection
  is not changing behaviour, and only removing the prose write will.

The second is the honest one. A detector makes an omission *visible*; a writer API would make it
*impossible*. This check is the cheap instrument that tells us which is worth building — not a
substitute for the answer.

## Where the measurements come from

Every fleet figure in this doc (the 7/207 jurisdiction split, `37 of 203` stale plan fields, the
five multi-`Status:` plans, `started_at` on 212 of ~213 locks) was measured by executing a sweep
over `/opt/*/.fabrik/plan-locks/` and `/opt/*/docs/development/plans/` during the design and review
of this check. The runs and their verbatim output live in the spec's `## Evidence` and the plan's
Pass Ledger, cited below — they are snapshots of a corpus other sessions mutate continuously, so
**re-measure rather than quote them**. The invariants they support (anchoring, the jurisdiction
discriminator, the non-terminal scoping) are stable; the counts are not.

## See also

- the plan `2026-08-26-plan-1-plan-lock-release-check` — under `docs/development/plans/` while
  it runs, `docs/development/plans/archived/` once executed (named, not linked, because the
  path moves at Finish and a link would be broken in one state or the other)
- `docs/superpowers/specs/2026-08-25-plan-lock-release-check-design.md` — the design spec
- `commands/_sources/fabrik-catchup.md:47-60` — probe 1, the prose contract this check enforces
- `docs/reference/rule-pack-reachability.md` — the sibling advisory gate this one is modelled on
