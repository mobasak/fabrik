# Plan 1 — Provider-death resilience: the ENFORCEMENT half (infra)

Status: CONVERGED

**Spec:** `docs/superpowers/specs/2026-08-28-provider-death-resilience-design.md` (CONVERGED 2b5b45db,
operator-approved 2026-08-28). **Origin:** operator directive via youtube `01M13YXMCCNS` (acked), plus
fleet's explicit hand-off `01M149Z5MA` (acked — I own this half).

**Shape:** monolith. 3 phases; computed READ set across every file this plan touches plus its Context
Files = **153,977 bytes**, under the 262,144 `READ_BUDGET_BYTES` shape trigger.

## Goal

The corpus does not merely lack a provider-death standard — `76-gpu-workers.md` **teaches the pattern that
failed youtube**. This plan corrects that, adds the missing failure class to the self-healing ladder, and
adds the two planning-phase rubric rows. It does NOT add a mechanical gate: measured 60% fleet incidence
(spec § Measurements) makes one advisory wallpaper, and the spec's § Enforcement says so in writing.

## What we already agreed (from the spec + this conversation)

- The standard is stated as three **OUTCOMES** with the mechanism chosen by route — NOT as three mandated
  mechanisms. Measured: 19 of 26 qualifying repos route only through OpenRouter, where the bespoke probe
  re-implements the gateway.
- **No mechanical gate in scope.** The one honest promotion target (a `RESILIENCE.md` §2b declaration
  check) needs C3 to have landed first so there is something to measure against — recorded, not shipped.
- C3 (scaffold template) is **already shipped by fleet** (`2ec405d4`); C4 is **filed to fabrik-lib**
  (`01M14E3MWN`, ack-required). Neither is in this plan.
- Operator: no subagent or pool dispatch for hub work. Every phase runs natively.

## The unresolved divergence — handled here, not deferred

Fleet asked that the rule and their template "say the same three things". I filed three findings against
§3b today (`01M14E2VZM`, ack-required, **currently unanswered**):

1. §3b mandates mechanism 1 unconditionally — wrong for the 19 gateway-only repos.
2. §3b omits the `sort`/`order` opt-out trap (raw docs `:72862`).
3. §3b points at `resilience/health_promote.py`, which does not exist, instead of the Active
   `health-probe/` + `alerting/`.

**The executor does NOT wait for fleet's ack.** That would be an `[OPEN → resolve at Phase N]` landmine of
exactly the kind `/fabrik-plan-after-chat` forbids. The default the executor applies without stopping:

> Write the rule per the CONVERGED spec (outcomes + the `sort`/`order` caveat + `health-probe/`), and add
> one sentence in the rule naming §3b as the project-facing template plus the fact that the two differ on
> the gateway path pending `01M14E2VZM`. A divergence that is WRITTEN DOWN is a known state; a silently
> picked winner is the defect.

If fleet acks and agrees, a follow-up edit drops that sentence. If fleet disagrees, the disagreement is
already visible in both artifacts. **Phase A is unaffected either way** — it touches no statement of the
standard.

**The cost of that default, stated rather than glossed.** Until `01M14E2VZM` is answered, a project on the
gateway path can read fleet's §3b and this rule and get two different instructions: §3b says build the
probe, the rule says declare which gateway mechanism you rely on. That is a real, temporary inconsistency
in fleet-wide governance and it is the price of not blocking. It is the right price — §3b as written sends
19 of 26 measured repos to re-implement their gateway, and waiting silently would leave that live and
undocumented — but it is a cost, not a free choice, and the executor should not pretend otherwise. Verified
this is genuinely a no-stop default: every sentence Phase B writes is determined by the CONVERGED spec, so
nothing in it needs fleet's answer to be written; only the divergence sentence's eventual removal does.

## Context Ledger

| Source | Grounded fact | Where |
|---|---|---|
| `core/76-gpu-workers.md` (ACTIVE) | `INFERENCE_CHAIN` static 2-rung, one model per provider | `:117-120` |
| `core/76-gpu-workers.md` | `except (httpx.TimeoutException, httpx.ConnectError)` — transport only | `:126` |
| `core/76-gpu-workers.md` | "Circuit-breaker per provider (not per model)" | `:133` |
| `core/58-resilience.md` (ACTIVE) | Per-Scaffold matrix, **11 rows**; `grep -c python-api-gpu` → **0** | `:23-35` |
| `core/58-resilience.md` | § Banned Patterns table — where the untested-last-rung row goes | `:339-361` |
| `core/self-healing.md` (ACTIVE) | 9-row escalation ladder; no zero-progress row | `:29-39` |
| `core/self-healing.md` | **Row-first mandate** — new failure class ⇒ add the row here first | `:54` |
| `core/self-healing.md` | ACK-timeout deadman (`deadman_timeout_seconds`, default 300) — arms only AFTER a Tier C alert; must not be duplicated or contradicted | `:51` |
| `scaffold.py::SCAFFOLD_TYPES` | **12** types (live registry read, not memory); `wordpress` raises `NotImplementedError` | `scaffold.py:146`, `:5835` |
| `templates/scaffold/docs/RESILIENCE_TEMPLATE.md` | fleet's §3b — the project-facing content spec | `:178-215` |
| `commands/_sources/fabrik-spec-review.md` | §E "Other mandates" list — insertion point for the audit row | `:113-117` |
| `commands/_sources/fabrik-plan-review.md` | "structural pillars" list — insertion point for the defect flag | `:104+` |
| fabrik-lib `health-probe/` | Active; pluggable probes, uniform `{system,status,detail}`, feeds `alerting/` | `/opt/fabrik-lib/README.md` |
| fabrik-lib `alerting/` | Active; Apprise→Telegram, **title-based dedup** = the "exactly one alert" property | `/opt/fabrik-lib/README.md` |
| OpenRouter (raw `llms-full.txt`) | outage step `:72848` · `allow_fallbacks` default true `:72814` · `models` any-error fallback `:72375-72380` · **`sort`/`order` disables load balancing `:72862`** | spec § External dependencies |

**fabrik-lib verdict:** no new module. `health-probe/` + `alerting/` are vendored-by-reference in the rule
text only — this plan writes no code that imports them.

## File Scope (owned paths)

- `.windsurf/rules/core/76-gpu-workers.md`
- `.windsurf/rules/core/58-resilience.md`
- `.windsurf/rules/core/self-healing.md`
- `commands/_sources/fabrik-spec-review.md`
- `commands/_sources/fabrik-plan-review.md`
- `tests/test_rule_pack_scaffold_coverage.py` (new)
- `CHANGELOG.md`

**DO NOT touch:** `templates/scaffold/**` (fleet's), `/opt/fabrik-lib/**` and `/opt/youtube/**` (cross-repo
HARD STOP — read only), any `specs/services/*.yaml`.

## Global Constraints

- `.windsurf/rules/**` and `commands/_sources/**` are **governance-sync trigger** surfaces: a commit here
  distributes to ~46 repos. Every sentence must be correct for all **12** `SCAFFOLD_TYPES`, grounded from
  the live registry, never memory.
- **Render from `/opt/fabrik` MAIN checkout only, never a worktree** — `assemble_commands.py` PRUNES
  installed commands absent from the current tree's `_sources/`. `--check` (temp-dir) is always safe.
- Shared tree: explicit pathspecs, `git diff --cached --numstat` before commit, `git reset -q HEAD -- <paths>`
  after. Never `--amend`.
- Commit per phase with Agent Provenance Trailers (`Agent-Role: primary`, `Agent-Name: infra`,
  `Agent-Phase`), then push.
- **No pool/subagent dispatch** (operator standing directive). Declare `NO-POOL:` in each commit body.

## Behavior Contract

Prose-rule changes are largely untestable by design — but all four rows here are mechanically assertable,
and the first would have caught C1b before a human ever noticed it.

- **Given** the live `scaffold.py::SCAFFOLD_TYPES` registry (12 entries) and `58-resilience.md`'s
  Per-Scaffold Applicability matrix, **When** `tests/test_rule_pack_scaffold_coverage.py` compares the
  matrix's row set to the registry, **Then** they are equal — and it fails RED today, because the matrix
  has 11 rows and omits `python-api-gpu`. (Phase A)
- **Given** `76-gpu-workers.md`'s § Provider Failover worked example, **When** the same test module reads
  its fenced `except` clause, **Then** that clause names `httpx.HTTPStatusError` — today it names only
  `TimeoutException`/`ConnectError`, which is why an `http_402` does not advance the chain. (Phase A)
- **Given** the edited `commands/_sources/` after the rubric rows land, **When**
  `python commands/assemble_commands.py --check` runs from the MAIN checkout, **Then** it prints
  `check OK` and exits 0 — the rendered corpus matches its sources. (Phase C)
- **Given** the same edited sources, **When** `python scripts/enforcement/check_command_corpus.py` runs,
  **Then** it exits 0 with every predicate green (advertised closes, chain targets, script paths).
  (Phase C)
- **Mocked:** nothing. Every assertion reads the real rule-pack file, the real registry via import, and
  runs the real renderer/checker. There is no fixture and no stub — a test that parsed a copy of the
  matrix would assert nothing about the file that actually ships to ~46 repos.

The first two rows are the anti-regression value of this plan: C1b existed because nothing compared the
matrix to the registry, and that is a two-line assertion.

**⚠️ What this test does NOT do.** `test_rule_pack_scaffold_coverage.py` mechanically enforces the
**corpus's internal consistency** — that the rule packs cover every scaffold type and that the worked
example is not self-defeating. It enforces **nothing about whether any project complies with the
standard**. Those are different claims and conflating them is exactly the "rule naming enforcement that
does not exist" defect. Project compliance is prose-enforced at the planning phase (spec § Enforcement),
and the one honest mechanical promotion target is deferred until fleet's §3b has landed long enough to be
measured against.

## Phase A — C1 + C1b: stop the corpus teaching the failure

Independent of the divergence and of every other phase. Highest value: it removes active harm.

**Steps**

1. Write `tests/test_rule_pack_scaffold_coverage.py` FIRST. Assert (a) the `58-resilience` matrix row set
   equals `SCAFFOLD_TYPES`, (b) the `76-gpu-workers` failover example's `except` mentions `HTTPStatusError`.
   **Run it and watch BOTH fail red** — the matrix is 11/12 and the example is transport-only today.
2. `76-gpu-workers.md:113-133` — rewrite § Provider Failover: candidate list with **intra-provider
   diversity** (2+ models of one provider) AND cross-provider; `except` that also catches
   `httpx.HTTPStatusError` so 402/403/429 advance the chain; correct `:133` to **per-(provider, model)**
   breaker granularity with the one-line why (a model died while its siblings stayed up).
3. `58-resilience.md:23-35` — add the `python-api-gpu` row. Ground its cell values against what the type
   actually is (an inference orchestrator: external calls yes, `/health` yes, `RESILIENCE.md` yes, and the
   worker columns per whether it queues).
4. Re-run the test → GREEN. Then **neuter each change in turn and confirm the matching assertion goes red**,
   restoring after each; the neutered state is never staged.

**Gate:** `python -m pytest tests/test_rule_pack_scaffold_coverage.py -q` green + `python scripts/final_gate.py --json` → `success`.

**✅ EXECUTED** — see § Evidence · Phase A.

**Evidence owed:** the red-first output before the fix, the green after, and the red-on-revert transcript
with the mutation asserted on disk.

## Phase B — C2: the missing failure class, as a ladder row

**Depends on:** Phase A — but **not for the reason a file-overlap suggests**. Both phases touch
`58-resilience.md`, yet in different sections (A: the matrix at `:23-35`; B: Banned Patterns at `:339` plus
a new section), and this plan runs single-agent with no pool dispatch, so there is no concurrent-edit
conflict to avoid. The real dependency is **content**: Phase A's corrected `76-gpu-workers` example and
Phase B's rule text both state the standard, and B must be written against A's corrected wording or the two
packs will disagree. Stating a file-conflict reason would have been a fake dependency.

**Steps**

1. `self-healing.md:29-39` — add row 10: **Unattended loop makes zero forward progress.** *Symptom* = an
   exported progress counter flat past its threshold while the loop is running. *First response* = rebuild
   the chain from live survivors (direct path) or rely on the declared gateway mechanism (gateway path).
   *Fallback* = the last-resort rung, which must have been exercised. *Escalate* = one operator alert via
   `alerting/`'s title-based dedup, cleared on recovery.
2. **Distinguish it from the existing deadman in the row's own prose** — `:51`'s
   `deadman_timeout_seconds` is an ACK-timeout that arms only after a Tier C alert exists and whose action
   is a container restart. This row fires when **no alert was ever raised** and a restart would not help.
   Without this sentence a reader concludes the row is redundant and deletes it.
3. `58-resilience.md` § Banned Patterns (`:339-361`) — add: *a fallback chain whose bottom rung has never
   been executed* → *exercise the last resort on a schedule; an untested fallback is a silently-dead one*.
4. Add the outcome-shaped standard to `58-resilience`, carrying the `sort`/`order` caveat verbatim in
   substance, plus the one divergence sentence from § The unresolved divergence above.

**Gate:** `python scripts/final_gate.py --json` → `success`; `python scripts/select_rules.py` still lists
both packs ACTIVE (a malformed frontmatter/table silently drops a pack).

**Evidence owed:** the new row rendered, and `select_rules.py` output showing both packs still ACTIVE.

## Phase C — C2b: the two rubric rows + render

**Depends on:** Phase B (the rows point at what B wrote).

**Steps**

1. `commands/_sources/fabrik-spec-review.md:113-117` — extend §E "Other mandates" with the provider-death /
   silent-stall row: for any unattended loop over an external dependency, a design carrying retry/backoff
   but **no provider-death handling and no zero-progress alarm** is a DEFECT.
2. `commands/_sources/fabrik-plan-review.md` — add the matching structural-pillar bullet.
3. **State plainly in both** that these are PROSE rubric rows an LLM reads, not mechanical checks. The spec's
   § Enforcement is explicit; claiming a gate that does not exist is the `oasdiff` defect.
4. `python commands/assemble_commands.py --check` first (safe), then render **from `/opt/fabrik`**, then
   `--check` again and `check_command_corpus.py`.

**Gate:** `assemble_commands.py --check` → `check OK`; `check_command_corpus.py` → `rc=0`;
`final_gate.py --json` → `success`.

**Evidence owed:** verbatim `--check` output before and after the render, and the corpus check.

## Coverage Checklist

Derived from `python scripts/review_rubric.py --changed <the 6 File-Scope paths>`, run this session. Every
class swept to a verdict; convergence means this table is complete, not that nothing further occurred to
the reviewer.

| # | Class | Verdict | Evidence |
|---|---|---|---|
| 1 | Context Ledger `path:line` grounding | CLEAN | Every citation re-opened this session: `76-gpu-workers:117-120` (static 2-rung), `:126` (transport-only `except`), `:133` (per-provider sentence); `58-resilience:23-35` + `:339`; `self-healing:29-39` (9 rows counted), `:51`, `:54`. See § Evidence. |
| 2 | READ-budget → plan SHAPE | CLEAN | Re-run with **stderr captured and empty** → 153,977 B < 262,144. Monolith is correct; a silent `find` miscount would have wrongly justified it. |
| 3 | Watched-fail-first not vacuous | CLEAN | Both Phase-A assertions proven genuinely RED today: matrix 11 rows vs registry 12, missing exactly `python-api-gpu`; `grep -c HTTPStatusError` → **0**. |
| 4 | Fake dependency / needless serialisation | **FIXED** | Phase B's stated reason was a file-overlap self-conflict — false for a single-agent run. Corrected to the real **content** dependency. |
| 5 | Deferred-question landmine (`[OPEN → resolve at Phase N]`) | **FIXED** | Verified Phase B is executable end-to-end without fleet's ack; the cost of the divergence is now stated rather than glossed. |
| 6 | Enforcement overclaim | **FIXED** | Added the explicit note that the new test enforces **corpus consistency**, not project compliance — conflating them is the `oasdiff` defect. |
| 7 | Internal consistency | **FIXED** | "three rows" vs four Given/When/Then rows. |
| 8 | Required monolith sections | CLEAN | Context Ledger · File Scope · Evidence · Behavior Contract · Global Constraints — all present, one each. |
| 9 | Placeholders / "100%" / unknowns overclaim | CLEAN | `grep` for `TBD\|TODO\|FIXME\|100%\|zero unknowns` → no hits. |
| 10 | Governance-sync blast radius | CLEAN | Both surfaces named in § Global Constraints with the 12-type correctness bar and the render-from-MAIN rule. |
| 11 | Cross-repo HARD STOP | CLEAN | `templates/scaffold/**`, `/opt/fabrik-lib/**`, `/opt/youtube/**` all in § File Scope DO-NOT. |
| 12 | Prose-only = under-delivery? | REFUTED | Not under-delivery: the planning phase has no artifact a mechanical check can read but the plan prose itself, and `.windsurf/rules` + the review rubrics ARE that surface. The one honest mechanical target is named and deferred with its measurement precondition. |
| 13 | Rubric FLOOR (35-security-auth, 25-data-postgres, 30-ops, 12-Factor) | REFUTED | No auth, DB, container, port, secret or service surface — this plan edits three markdown rule packs, two command sources, and one test. |

## Self-audit

- **Passes:** 3 (1 wide → 1 scoped fix → 1 wide closing). Terminal pass `edits: 0`, `new: 0`,
  md5 `a0bbe60d229ecd376d2614ad3c87c477` stable start→end.
- **What I could NOT verify and am not claiming:** that fleet will accept the three §3b findings; that
  `health-probe/`'s interface admits the C4 helper (spec U1, cross-repo, filed as `01M14E3MWN`). Both are
  recorded as non-blocking in § Open / blocking unknowns, and neither gates any phase in this plan.
- **Weakest part of this plan, named:** Phase B and C are prose edits whose *quality* no gate can measure.
  Rows 3–4 of the Behavior Contract prove the corpus still RENDERS and its predicates pass; nothing proves
  the sentences are good. That is inherent to a prose standard and is why the spec's § Enforcement is
  explicit about what is and is not mechanically enforced.
- **Not claimed:** "100%", "zero unknowns", or that this plan makes any project compliant with the standard.

## Evidence

Convergence evidence for the PLAN (produced this session by `/fabrik-plan-review`). Execution evidence is
appended per phase by `/fabrik-execute-plan` against each phase's **Evidence owed** line — a pre-filled
execution block would be a fabricated one.

Registry vs matrix, and the failover `except` — the two watched-fail-first claims, proven RED:

```
$ python -c "…compare 58-resilience matrix rows to scaffold.py::SCAFFOLD_TYPES…"
registry types: 12
matrix rows   : 11
MISSING       : ['python-api-gpu']
EXTRA         : []

$ sed -n '126p' .windsurf/rules/core/76-gpu-workers.md
        except (httpx.TimeoutException, httpx.ConnectError):
$ grep -c "HTTPStatusError" .windsurf/rules/core/76-gpu-workers.md
0
```

READ budget with stderr captured (an unchecked `find` stderr is how a bad path silently under-counts and
wrongly justifies a monolith):

```
$ find <the 6 File-Scope + Context paths> -type f -exec cat {} + 2>find.err | wc -c
153977
$ cat find.err
[empty]
```

Self-healing `:51` — proof the existing deadman is an ACK-timeout and therefore does NOT cover this failure
class, which Phase B step 2 depends on being true:

```
$ sed -n '51p' .windsurf/rules/core/self-healing.md
- **Tier C (escalate-only):** … Deadman timer rearms; if operator doesn't ack within
  `WatchdogConfig.deadman_timeout_seconds` (default 300), the watchdog runs `docker restart
  <main_container>` as bleed-stop and re-alerts with `[DEADMAN-TIMEOUT]`.
```

## Open / blocking unknowns

| # | Unknown | Resolution | Blocks? |
|---|---|---|---|
| 1 | Does fleet accept the three §3b findings (`01M14E2VZM`)? | Their ack. Executor does **not** wait — applies the documented default above. | No |
| 2 | `health-probe/`'s signature for the chain-rebuild helper (`01M14E3MWN`, spec U1) | fabrik-lib replies. Until then the rule names the OUTCOME and `health-probe/` as the module, not a function signature. | No |

## Next

`/fabrik-plan-review` to converge this plan, then `/fabrik-execute-plan`.


### Evidence · Phase A (executed 2026-08-28)

Test written FIRST; all three assertions watched RED before either rule pack was touched:

```
$ python -m pytest tests/test_rule_pack_scaffold_coverage.py -q
FAILED …::test_every_scaffold_type_has_a_resilience_row
FAILED …::test_provider_failover_example_handles_http_status_errors
FAILED …::test_provider_failover_breaker_granularity_is_per_model
3 failed in 0.19s
```

Fixes at `path:line` — `.windsurf/rules/core/76-gpu-workers.md` § Provider Failover (candidate list gains
an intra-provider live sibling; the failover now catches `httpx.HTTPStatusError` and SWAPs on 402/403/429
while re-raising a genuine client error; breaker granularity corrected to per-`(provider, model)`), and
`.windsurf/rules/core/58-resilience.md` Per-Scaffold matrix gains the `python-api-gpu` row.

```
$ python -m pytest tests/test_rule_pack_scaffold_coverage.py -q
3 passed in 0.30s
```

**A defect in my own test, caught by the fix.** The first green run still failed the `except` assertion:
the regex matched only PARENTHESIZED except clauses, and the new `except httpx.HTTPStatusError as e:` is
unparenthesized — a false negative on correct code. The regex now grades every clause in the section, and
the widened form was re-proven red against the original file.

Red-on-revert, each mutation asserted on disk and restored (single-file stash of my OWN owned path only —
never a sibling's):

```
$ git stash push -q .windsurf/rules/core/76-gpu-workers.md && pytest -q
2 failed, 1 passed          # except-clause + breaker-granularity assertions
$ git stash pop -q; grep -c HTTPStatusError .windsurf/rules/core/76-gpu-workers.md
2

$ git stash push -q .windsurf/rules/core/58-resilience.md
matrix row present while stashed: 0
1 failed, 2 passed          # the registry-coverage assertion
$ git stash pop -q; grep -c python-api-gpu .windsurf/rules/core/58-resilience.md
1
```

```
$ python scripts/final_gate.py --json
gate: success | blocking: 38 | failures: 0
```
