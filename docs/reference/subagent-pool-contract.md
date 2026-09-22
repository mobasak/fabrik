# Subagent pool contract — FROZEN (OpenRouter pool · ai-consult · flywheel)

**Status:** PAUSED. The OpenRouter subagent pool (fabrik-lib `subagents`, "Runtime B"), the metered `ai-consult` panel and the flywheel that ranked pool models are OFF by operator ruling (D-181, 2026-09-07; mechanism D-182: the credentials stay provisioned, so a `fanout()` would still dispatch and SPEND) and the operator re-confirmed on 2026-09-22 that OpenRouter and Kilo subagents are paused in the regular coding workflow. Every fan-out runs NATIVE Claude Task subagents — the live rule is `.windsurf/rules/core/62-using-subagents.md`. While the pause holds, intel monitors `fabrik_analytics.subagent_runs` for any dispatch (D-182's tripwire).

**What this file is:** the pool-era contract, moved out of the fleet-synced pack on 2026-09-22 (D-343 — the pack shipped ~18 KB of HTML-commented pool instructions to ~46 repos and into every activation's context for a runtime nobody may call). Nothing here is binding while the pause holds. **Re-enabling is an operator ruling first**, then restoring the sections below into the pack — verbatim, in the pack's original order, with their original headings. Line cites into `libs/subagents/agent.py` / `workspace.py` and `select.py` are as of the vendored copy on the freeze date; re-verify them against the module before trusting one.

**Contents:** the 10 multi-line `<!-- POOL OFF -->` blocks, the one inline comment (§ Which subagent_type), the `ai-consult` section (live text under an "OFF WITH THE POOL" banner at HEAD), and § Pool-era rules that were live one-liners — all from `core/62-using-subagents.md` at `0bb10dbe7` (`git log -1 --format=%h -- .windsurf/rules/core/62-using-subagents.md` on the freeze date). Frozen 2026-09-22.

**Already refuted at freeze time (fix these before any restore):** (1) the `mcp` Python SDK rule ("pin v1 — the v2 `mcp.client.Client` line is a pre-release") is backwards — v2 is the current stable line and v1.x is maintenance-only (github.com/modelcontextprotocol/python-sdk README, 2026-09-22); the pool's MCP client imports v1's `ClientSession`/`stdio_client` and would need porting. The rule's other half — never hard-code the Tool schema attribute name (`inputSchema` vs `input_schema`), resolve it at build time against the pinned version — still stands. (2) The `ai-consult` pre-flight `GET https://openrouter.ai/api/v1/credits` now requires a MANAGEMENT key — a normal inference key gets 403 "Only management keys can perform this operation"; the regular-key check is `GET /api/v1/key` (`limit_remaining`). `GET /api/v1/models` is still public (openrouter.ai/docs/api-reference, 2026-09-22). (3) Known text defect carried verbatim: the `ai-consult` section's lead-in was lost before the freeze — it reads "…for the day it returns.** different eyes at a DECISION FORK, never breadth.**"; the intended sentence is "`ai-consult` buys different eyes at a DECISION FORK, never breadth."

---

## Pool-era rules that were live one-liners in the pack

- **The runtime:** fabrik-lib `subagents` pool — OpenRouter-API models in a sandboxed worktree. Not Claude; tools = the module's `web_tools` (Exa/Firecrawl/Context7/Brave HTTP) + `mcp_servers` (MCP client) + `allowed_commands`. **No browser** — GUI work never routes here. Design authorities (pool side): fabrik-lib `subagents/PROPOSED_RULE-using-subagents.md` + fabrik-lib's spec `2026-07-07-subagents-mcp-client-design.md` (under `/opt/fabrik-lib/docs/superpowers/specs/`, not this repo).
- **Never route to the pool** (fabrik-lib PROPOSED_RULE): auth/identity/session/crypto · schema/migrations · secrets/`.env`/keys · security controls (RLS, rate-limits, `final_gate`) · deploy/infra. Never web/MCP-enable a task carrying sensitive context — the model's output exfiltrates via a scraped URL. **Keep the bwrap sandbox on (`sandbox=True`, fail-closed).**
- **mcp.json reader:** the pool's MCP client reads the hub-owned `/opt/fabrik/mcp.json` via `AgentSpec.mcp_config` (a path → unwrap the `mcpServers` key; a dict → the bare server map); adding a tool for the pool touches that file, never a brief.
- **Banned (pool):** hard-coding the `mcp` SDK API line or the Tool schema attribute name (see refutation 1 above for the SDK half).

## Inline comment — § Which subagent_type per command (pool-era framing)

These are the **native** types — used for GUI, the authoritative/high-risk pass, and the decide/refute/merge. Under § Dispatch policy the **gradeable fan-out** of these same commands (review finders, research grounders, doc reconcilers, rules auditors, implementers) **defaults to the POOL** (Runtime B); native here is the authoritative complement, not the default worker.

## The `<!-- POOL OFF -->` blocks, in the pack's original order


### Block 1

<!-- opener at HEAD: <!-- POOL OFF (D-181, 2026-09-07) — kept verbatim for re-enable: -->

## Pool tool access (Runtime B)

- Enable **`web_tools`** and **`mcp_servers`** *per `task_type`*, off by default (they cost money + reach the internet): `research`/`plan` → `web_search`+`docs_lookup` (+ `web_scrape` to read a page); `code`/`review`/`docs` → none.
- **Safe-server allowlist (fail-safe):** research servers `exa`/`brave-search`/`firecrawl`/`context7` are default-on; **FS/shell/exec MCPs are refused** unless `allow_unlisted=True`; **browser MCPs are opt-in** on a capable host only — never default-on the pool.
- **Keys via the process env** (`EXA/FIRECRAWL/CONTEXT7/BRAVE_API_KEY`) — same model as `web_tools`; the hub provisions them into the pool env (`/opt/fabrik/.env` on WSL, deploy env on VPS). Never inline a key.
- **Pin the `mcp` Python SDK v1** (`ClientSession`/`stdio_client`) — the v2 `mcp.client.Client` line is a pre-release the repo marks "do not use in production." Don't hard-code the Tool schema attribute (`inputSchema` vs `input_schema`) — resolve it at build time against the pinned version.
- `max_turns` (not `max_cost_usd`) bounds MCP/web spend — cap it for tool-enabled pool agents and audit the ledger.

## Pool model selection — flywheel-ranked, per-task, NO price cap (BINDING)

The pool is a **rule, not a roster: `pick_models(task_type)` returns the flywheel-ranked models for the task, best-first — take the top that clears your bar.** **Name no model rosters or per-stage rankings in this pack** — they are the flywheel's *output* and live in ONE place: the module's vendored `_TABLE` (fallback seed) + the synced per-task table **`/opt/fabrik/docs/reference/kilo/TASK_SUBAGENT_SELECTION.md`** — one `### <task_type>` section each (`code · docs · plan · research · review · spec`), rows ranked by real recorded runs (`shrunk_q · success · avg_cost · n`; `[benchmark]` = a never-run candidate). `pick_models` **auto-reads that hub doc** (`_HUB_SELECTION_DOC` in `select.py`, overridable via `SUBAGENT_SELECTION_DOC`) and prefers its empirical order over `_TABLE`. Copying any model name into this pack is the drift this pack exists to avoid.

**Dispatch-size ceiling is real:** a `read_only` unit's task text rides one API request — a full
multi-file diff inlined into one unit can 413/400 at the provider and the unit DIES having swept
nothing (measured live). Split oversized surfaces across units, and state any excerpt's BOUND inside
the task text (a finder given a truncated excerpt reads absence-in-window as absence).

**No default price cap.** Per-run task cost is pennies regardless of $/Mtok (a review/spec/research fan-out especially), and a blanket cap would exclude the flywheel's top-ranked models. Price is **opt-in**: pass `max_cost_per_mtok=` to `pick_models`/`fanout` *only* when you want a hard budget ceiling for a run; `allow_above_cap=` is a **no-op**.

**Select with `pick_models(task_type, …)` — never hand-pick, never name a model in prose.** It returns the flywheel-ranked pool best-first (`prefer="value"` biases toward cheapest-that-clears-the-bar; `exclude=` drops a model). **No `anthropic/*` via the pool** — Claude is subscription-native; use the `fabrik-reviewer` Claude Code subagent, not the pool. Don't invent OpenRouter IDs — verify any ID against the table, not memory.

- **Close the flywheel loop (every *pool* dispatch):** `pick_models(task_type)` → judge the run → **`record_agent_run(spec, result, quality_score, project=<name>)`**. Via `fanout` the dispatch half is automatic (recorded UNSCORED) — your judgment lands with `set_quality`. ⚠️ `record_run(result, …)` on a raw `AgentResult` **silently no-ops** (it wants a dict; `model`/`task_type` live on the *spec*) — always `record_agent_run(spec, result, …)`. Fleet runs → `subagent_runs` → per-task aggregation → **`TASK_SUBAGENT_SELECTION.md`** → sharper `pick_models` next time.
- **⚠️ Keep the sources aligned:** the module's vendored `_TABLE` (fallback seed) and the flywheel-refreshed `TASK_SUBAGENT_SELECTION.md` (which overrides it via `_HUB_SELECTION_DOC`/`SUBAGENT_SELECTION_DOC`). **This pack lists NO models and NO price literal — only the mechanism — so it can never be the source that drifts.**


### Block 2

<!-- opener at HEAD: <!-- POOL OFF (D-181) — the original heading, kept for re-enable: -->

## Dispatch policy — pool-default for gradeable fan-out, native for GUI/authoritative/decide (BINDING)


### Block 3

<!-- opener at HEAD: <!-- POOL OFF (D-181, 2026-09-07) — kept verbatim for re-enable: -->

**The OpenRouter pool is the DEFAULT worker for gradeable text/code fan-out** — review finders, repo-review unit reviewers, doc reconcilers, rules-pack auditors, spec/plan research grounders, code implementers. **Route it through `fanout(task_type, units, *, repo, project, mode="read_only"|"write")`** — where **`repo=` is the project ROOT as an absolute path** (e.g. `repo="/opt/job-agent"`, NEVER a bare name: `repo="job-agent"` called from inside the repo silently nested every ledger/env path under `<root>/<name>/` until the module learned to refuse it — the flywheel rows recorded there were invisible to the gate) — the one-call helper that selects via `pick_models` (flywheel-ranked, NO default price cap; **family diversity is BEST-EFFORT, not a guarantee** — `agent.py` reorders the draw distinct-family-first, but it can only diversify across what `pick_models` RETURNS, and the operator's routing allowlist (D-159) currently pins every task kind to two models of one vendor family, so a fan-out repeats them rather than spanning families. Where family diversity is the POINT — a substantial review's recall breadth — add the native layer on top, which is what § Dispatch policy already requires), runs parallel-safe, **auto-records each unit to the flywheel UNSCORED**, and recovers a zero-output straggler once; then **back-fill your 0–5 verdict with `set_quality(agent_id, score, project=, task_type=, model=)`** after you judge — a `fanout` row left unscored teaches the flywheel nothing. `run_agents([AgentSpec, …])` is the lower-level primitive for a hand-tuned mix — then YOU owe `record_agent_run(spec, result)` + `results_table` per unit (§ Report every pool run). A single-shot (`tools_enabled=False`) **repo-grounded** worker (`task_type` `review`/`docs`/`plan` — they assert about code they can't see) must set `allow_ungrounded=True` to attest it inlined the content into `task`, or use `tools_enabled=True` for real file reads — the module **refuses** ungrounded single-shot verification (it hallucinates). **The attestation is only as good as the inline: VERIFY the inlined content actually resolved before dispatch** — a `[MISSING: <path>]` marker passed as "source" produced a full, confident, line-numbered fabrication of a file the model never saw (measured 2026-08-28: one model refused honestly in its first sentence, another invented status values, methods and a five-step trace — wrong in exactly the direction that plans the wrong fix). Enforced (not prose) by `scripts/enforcement/check_subagent_flywheel.py`.

⚠️ **NEITHER MODE FITS A READ-ONLY REVIEWER OVER A LARGE FILE — know this before you dispatch.**
Verified in `libs/subagents/agent.py` at HEAD: `read_only` sets `tools_enabled=False` (`:938`), so the
unit CANNOT read files and you must INLINE the content — for a 1,950-line contract plus its siblings
that is most of a context window before the reviewer has read anything. `write` gives real file reads
but **requires a non-empty, disjoint `owned_paths` per unit** (`:1066`, an explicit raise) because it is
built to return a DIFF. So a reviewer that CORRECTLY writes nothing returns an empty diff — and
`AgentStatus` (`:48`) is `done | capped | error | out_of_scope`, with **no value distinguishing
done-with-findings from done-with-nothing**. The run costs real money and reports success.

Measured (transdoc, 2026-08-28): three dispatches, **~$0.18 for zero usable output**, nothing errored,
ledger rows read `done`. Note the contrast that makes the gap obvious — the `capped` status DOES say
*"the output/diff is PARTIAL … do NOT trust a capped diff"*, and that message was the only reason the
third unit was distrusted. The empty-`done` case has no such signal.

**Until the pool grows a read-only-with-file-reads mode, do NOT fan out a large-file review to the pool.**
Either inline a BOUNDED extract (the section under review, not the whole contract) and accept
`read_only`, or run that reviewer NATIVELY (`fabrik-reviewer`, which has real file reads) and keep the
pool for units whose content genuinely fits inline. **And whichever you pick, treat an empty return as a
FAILED unit, never a clean one** — check the output length before you score it, because the status will
not tell you.


### Block 4

<!-- opener at HEAD: <!-- POOL OFF (D-181, 2026-09-07) — kept verbatim for re-enable: -->

**⚠️ BOTH layers, never either/or — native is ADDED ON TOP of the pool breadth, not instead of it.** A *substantial* review / repo-review / rules-audit runs the **pool** breadth layer (`run_agents` finders — recall + they record) **AND** native `fabrik-reviewer` (Opus) for the auth/schema/migrations/secrets/concurrency slices + the decide/merge. "Native for the high-risk pass" does NOT mean native-**only**: a high-risk surface needs the pool breadth *plus* the native authoritative pass. Going all-native and skipping the pool layer lands **zero** flywheel rows (the flywheel learns nothing) — the exact miss `check_subagent_flywheel.py` advisory-WARNs (a big changed surface with no pool run). Trivial one-file reviews may run a single layer; anything substantial runs both.

**Trust = the METHODOLOGY, not a model pin.** A review's trust does NOT come from which pool model ran; it comes from **≥1 native Opus finder as the authoritative decider + every pool finding independently refuted before it is acted on** — both hold regardless of which models the flywheel currently ranks top. So never gate trust on a model name; gate it on the native-Opus-authority + refutation invariant.

**Always cost-conservative + you adjudicate:** select via § Pool model selection (`pick_models`); pass an explicit `max_cost_per_mtok` only when a run needs a hard budget. Cheap pool workers *surface* candidates; you refute / merge / decide and own the verdict.


### Block 5

<!-- opener at HEAD: <!-- POOL OFF (D-181, 2026-09-07) — kept verbatim for re-enable: -->

## Pool vs native — which runtime for a fan-out

| | Native Claude Task subagent (`fabrik-reviewer`/`-researcher`/`-gui`) | OpenRouter pool (`run_agents`) |
|---|---|---|
| **Model** | Claude (subscription) | cheap non-Claude — flywheel-ranked per task (`TASK_SUBAGENT_SELECTION.md`), typically pennies/run |
| **Tools** | Read/Grep/Glob/Bash on the real tree; browser/UI | sandboxed worktree + `run_command`; real file R/W (`tools_enabled=True`) — **not** text-only |
| **Best for** | line-precise grounding, review recall, GUI, the decide/refute/merge | parallel code implementation, cheap review-recall breadth, research/prose |
| **Flywheel** | **no `AgentResult` → CANNOT record** (don't tell it to) | **must `record_agent_run(spec, result)` + `results_table`** per unit |

**Pool-default (above):** gradeable fan-out (finders / grounders / reconcilers / auditors / implementers) goes to the pool by default and records; GUI / authoritative / decide-merge stay native. Per-command map: `/fabrik-execute-plan` implementers · `/fabrik-review` + `/fabrik-repo-review` finders · `/fabrik-rules-review` per-pack auditors · `/fabrik-spec-review` + `/fabrik-plan-review` grounders · `/fabrik-docs-review` reconcilers · `/fabrik-plan-after-chat` + `/fabrik-data-contract` `path:line` grounders (+ a native ~20% citation verify-sample) · `/fabrik-flows` per-persona journey walkers + `/fabrik-flows-review` axis reviewers (tracing · persona completeness · discipline · cross-artifact) → pool; the second-actor hunt and async-boundary sweep → **native** · `/fabrik-spec` fact + best-practice grounders (research phases 1a/1c) → **all pool**; `/fabrik-ui-design` (screen build) → **native** (`fabrik-gui`); decide/refute/merge → **always you/native**. Keep the `try: from libs.subagents import record_agent_run / except ImportError: record_agent_run = None` guard **only** on genuine pool-dispatch commands — not as a device to pre-write native footers.

## Parallelism — the two shapes (a fan-out that is neither SILENTLY SERIALIZES)

`run_agents` parallelizes a fan-out in **exactly two shapes**; anything else collapses to one serial group — an
**empty `owned_paths` overlaps everything** (`workspace.py:441` `unrestricted = not owned[i] or not owned[j]`, inside `disjoint()` at `workspace.py:419`) and
every `tools_enabled=True` worker is routed through `disjoint()` (`agent.py:632-636`):

1. **Read-only fan-out (finders / grounders / auditors / reconcilers) → `tools_enabled=False`.** **The
   parallelism trigger is `tools_enabled=False` ALONE** — every such worker becomes its own group (`agent.py:636`
   — `groups += [{i} … if not s.tools_enabled]`) → **all parallel, regardless of `owned_paths`**. This is the
   DEFAULT for every gradeable read-only fan-out. **Separately (orthogonal to parallelism — a *don't-get-refused*
   requirement, NOT a shape condition):** a single-shot read-only worker on a **grounded** `task_type`
   (`review`/`docs`/`plan`) must ALSO set `allow_ungrounded=True` and INLINE the unit's content into `task`, or the
   module refuses it up-front (`agent.py:351`, the fail-closed pre-flight — it would hallucinate). Non-grounded read-only workers
   (`research`/`spec`/`code`) parallelize on `tools_enabled=False` with no such attestation.
2. **Tools-enabled fan-out (implementers, or graders that must read/write the tree themselves) →
   `tools_enabled=True` + DISJOINT `owned_paths` (one unit's files each).** Disjoint globs → parallel worktrees.
   ⚠️ **`tools_enabled=True` + empty/overlapping `owned_paths` → one group → SERIAL — the #1 dispatch trap** (looks
   parallel, runs serial). If a read-only fan-out needs file reads, prefer shape 1 (inline) over shape 2.

**Corollaries (verified against the module):** `pick_models(task_type, n=<K>)` for a K-model fan-out — the default
is **`n=1`**, so you MUST pass `n` to get more than one model. Parallel groups run **`max_concurrency` (default 4)**
at a time — raise it to widen a big fan-out. Worker tools (**tools-enabled workers only** — a read-only single-shot
worker has none of these, it just returns text): `read_file · write_file · apply_patch · list_dir · grep ·
run_command` (bwrap-sandboxed). (Prices + the per-kind best model are the flywheel's *output* — they live in
`select.py`'s `_TABLE` + the synced `CODING_SUBAGENT_SELECTION.md`, never restated here; `pick_models(task_type)`
returns them cheapest-that-clears-the-bar first — see § Pool model selection for why no roster lives in this pack.)


### Block 6

<!-- opener at HEAD: <!-- POOL OFF (D-181, 2026-09-07) — kept verbatim for re-enable: -->

**Per-command dispatch mode** (which shape each command's fan-out uses — pairs with the routing map above):

| Command | Fan-out | Shape |
|---|---|---|
| `/fabrik-review`, `/fabrik-repo-review` | finders (`n=3` differently-biased) | **RO** (inline) |
| `/fabrik-rules-review` | one auditor per rules pack | **RO** (inline) |
| `/fabrik-spec`, `-spec-review`, `-plan-review`, `-plan-after-chat`, `-data-contract`, `-docs-review`, `-ui-design-review` | grounders / reconcilers | **RO** (inline) — OR TE-disjoint (`owned_paths` per unit) if the worker reads the tree itself; **never** `tools_enabled=True` + empty `owned_paths` + "parallel" |
| `/fabrik-execute-plan` | implementers | **TE-disjoint** (worktrees, one unit's `owned_paths` each) |
| `/fabrik-ui-design` | screen build/drive | **native `fabrik-gui`** (no pool equivalent) |

> The two shapes govern **pool** fan-out (`run_agents`). `/fabrik-ui-design` runs a **native** `fabrik-gui`
> subagent (browser) — not a pool fan-out at all, so the shapes don't apply; it's in the table only to mark it
> non-pooled (native runtimes never hit the `disjoint()` grouping). Same for any native pass.


### Block 7

<!-- opener at HEAD: <!-- POOL OFF (D-181, 2026-09-07) — kept verbatim for re-enable: -->

## Report every pool run — the results table AND the flywheel (both, always)

After any **pool** (`run_agents`, Runtime B) dispatch you EVALUATE, emit **BOTH** — sharing **one** quality verdict (judge once, put the same 0–5 in both). A run that showed a table but no flywheel row (or vice-versa) is **half-done**:

1. **A results table** (one row per unit) so a human can compare models at a glance — use the helper `results_table([{ "unit":…, "model":…, "result":<AgentResult>, "quality":0-5, "fixes":… }, …])`. Provider / Cost / Latency / **Out** (`out_tokens`) come straight from the `AgentResult`; **quality + confirmed-fixes are YOUR verdict** after materializing the diff and running the gate/tests/review.
2. **A flywheel row per unit** — **`record_agent_run(spec, result, quality_score=<the same 0-5>, project=<name>)`**. ⚠️ the older `record_run(result, …)` **silently no-ops** on a raw `AgentResult` (it wants a dict; `model`/`task_type` live on the *spec*) — always `record_agent_run(spec, result, …)`. On the VPS `SUBAGENT_RUNS_DSN` connects directly; on WSL dev pass a peer-auth `connect=` factory. It is fail-open (returns `False` silently on a DB problem) — to prove the plumbing, SELECT the row back, don't trust the return.

**A native Claude-Code-subagent (Runtime A) dispatch produces NO `AgentResult` — it CANNOT record; the flywheel is pool-only (Runtime B).** So a native-fan-out command carries no flywheel footer (see § Pool vs native). Inline / no-dispatch → nothing to record. Telemetry design: `docs/superpowers/specs/archived/2026-07-06-subagent-runs-telemetry-design.md`.


### Block 8

<!-- opener at HEAD: <!-- POOL OFF (D-181, 2026-09-07) — kept verbatim for re-enable: -->

- A pool task with `sandbox=False`, an inline API key, or web/MCP enabled while it carries sensitive context.


### Block 9

<!-- opener at HEAD: <!-- POOL OFF (D-181, 2026-09-07) — kept verbatim for re-enable: -->

- Naming a model roster, a per-stage ranking, or a `$X` price cap in this pack — the roster lives in the module `_TABLE` + `TASK_SUBAGENT_SELECTION.md`, and there is no always-on cap; NO model may appear by name here.


### Block 10

<!-- opener at HEAD: <!-- POOL OFF (D-181, 2026-09-07) — kept verbatim for re-enable: -->

- A pool run that emitted a `record_agent_run` but no `results_table` (or vice-versa) — both, one verdict. (And never `record_run(result, …)` — it no-ops; use `record_agent_run(spec, result, …)`.)


## The `ai-consult` lane (was live text under the OFF banner)

**The THIRD lane — `ai-consult` (fabrik-lib, metered frontier panel) — OFF WITH THE POOL (D-181/D-182: the same no-metered-fan-out ruling; its key stays provisioned, so do not call it); the four entry points below stay the contract for the day it returns.** different eyes at a DECISION
FORK, never breadth.** The pool buys gradeable recall and the flywheel learns from it; native buys
authority on subscription; `ai-consult` buys the one thing neither can — genuinely foreign frontier
judgment (the `frontier` roster: 7 seats, 6 vendor families, zero Anthropic — Claude eyes come via
`claude -p`, never metered). It records nothing to the flywheel and burns real credits, so it fires
ONLY at these four entry points, and never as a reflex:

1. **Operator-named** — the operator asks for a consult.
2. **A genuine design fork** in `/fabrik-spec` / `/fabrik-spec-review`: approaches truly balanced,
   repo/rules/docs cannot settle it, and the question bar is about to ask the operator — a panel run
   FIRST upgrades that question from "A or B?" to "A or B, and here is what seven foreign models
   argued." The operator still decides.
3. **A `BLOCKED: NON-CONVERGENCE` verdict** — the stall breaker names a suspected foundation error;
   that is precisely when same-family eyes stop helping.
4. **Pre-freeze on an irreversible heavy surface** (schema, auth model, migration strategy), as an
   optional named step.

Stinginess rules, all binding: **check the OpenRouter remaining credits FIRST** —
`curl -s https://openrouter.ai/api/v1/credits -H "Authorization: Bearer $OPENROUTER_API_KEY"`
(`data.total_credits - data.total_usage`) — and if the balance cannot cover the consult, **ask the
operator for a credit top-up naming the estimated cost; never spend the tail silently and never
substitute a degraded panel**. Single-model `consult()` before any panel; the panel only when the
single opinion conflicts with ours or the fork genuinely needs diversity. Every use reports
`cost_usd` in the run's evidence (the `Result` carries it). Never for gradeable fan-out — that is
the pool's job (`/fabrik-review` already names bypassing `fanout` for ai-consult as throwing away
recording, containment and caps). Live-verify the roster's model IDs before a paid session —
`curl -s https://openrouter.ai/api/v1/models | python3 -c "import sys,json; print('\n'.join(m['id'] for m in json.load(sys.stdin)['data']))" | grep -x "<id>"`
(the public models list, no key needed) — the seats were frozen from a past measured run and IDs rot.
