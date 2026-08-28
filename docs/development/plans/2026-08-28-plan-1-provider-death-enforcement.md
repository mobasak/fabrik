# Plan 1 — Provider-death resilience: the ENFORCEMENT half (infra)

Status: PLANNED

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

Prose-rule changes are largely untestable by design — but three rows here are mechanically assertable, and
one of them would have caught C1b before a human ever noticed it.

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

**Evidence owed:** the red-first output before the fix, the green after, and the red-on-revert transcript
with the mutation asserted on disk.

## Phase B — C2: the missing failure class, as a ladder row

**Depends on:** Phase A (same files touched for `58-resilience`; sequential avoids a self-conflict).

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

## Evidence

Each phase above carries an **Evidence owed** line; the executor pastes real command output into this
section as it goes, per phase, with at least one `path:line` and one fenced output block each. This section
is deliberately empty until execution — a pre-filled Evidence block is a fabricated one.

## Open / blocking unknowns

| # | Unknown | Resolution | Blocks? |
|---|---|---|---|
| 1 | Does fleet accept the three §3b findings (`01M14E2VZM`)? | Their ack. Executor does **not** wait — applies the documented default above. | No |
| 2 | `health-probe/`'s signature for the chain-rebuild helper (`01M14E3MWN`, spec U1) | fabrik-lib replies. Until then the rule names the OUTCOME and `health-probe/` as the module, not a function signature. | No |

## Next

`/fabrik-plan-review` to converge this plan, then `/fabrik-execute-plan`.
