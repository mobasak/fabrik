---
activation: glob
globs: ["**/subagents/**", "**/libs/subagents/**", "**/*subagent*", "**/mcp.json", "**/.mcp.json", "**/agents/*.md"]
description: How to dispatch subagents — native Claude Task subagents for every fan-out while the OpenRouter pool is OFF by ruling (D-181/D-182), per-task tool access, the never-route safety list, the mcp.json source-of-truth; the pool runtime and its flywheel are kept in comments for re-enable
trigger: glob
---
<!-- CONSUMER: Coding agents (all) + Traycer (planning)
     GOAL: One place that says which subagent runtime to use, what tools it gets, what NEVER goes to a subagent, and how tool access is a single-source change.
     AGENT USAGE: When a command dispatches subagents, pick the runtime + the tool scope from here. Design authority: docs/superpowers/specs/archived/2026-07-07-subagent-tool-parity-design.md (Claude Code side) + fabrik-lib subagents/PROPOSED_RULE-using-subagents.md + its 2026-07-07-subagents-mcp-client-design.md (pool side). -->

# Using Subagents

> **⚠️ STATUS — POOL OFF (D-181, operator, 2026-09-07).** Runtime B (the OpenRouter pool) is OFF by ruling; its credentials stay provisioned (D-182), so this pack and the gate are the control. Every fan-out runs Runtime A (native Claude Task subagents); the pool sections below are kept in `<!-- POOL OFF -->` comments for re-enable. Binding detail: § Dispatch policy.

Two runtimes dispatch subagents; each scopes tools differently. **Never restate tool lists in a command brief — the access lives in the agent-type file (Runtime A) or the `AgentSpec` (Runtime B).**

**Composing the subagent's brief/system prompt:** follow `docs/reference/MD/ai-prompt-templates.md` — a distilled system prompt (Part A) that enforces the agentic patterns (Part B: termination contract, evidence-before-assertion, path:line grounding, untrusted-input). Distil, don't dump the whole rulebook into the brief.

## The two runtimes

- **A — Claude Code subagents** (`Agent` tool / `subagent_type`). *Are* Claude; tool access = the agent-type frontmatter (`tools` / `mcpServers` / `disallowedTools`). Used today. Can drive browsers.
- **B — fabrik-lib `subagents` pool** — **OFF by ruling since D-181 (2026-09-07; mechanism revised by D-182 — the credentials stay provisioned, so a dispatch would still spend: do not call it).** (OpenRouter-API models, sandboxed worktree). Not Claude; tools = the module's `web_tools` (Exa/Firecrawl/Context7/Brave HTTP) + `mcp_servers` (MCP client) + `allowed_commands`. **No browser** — GUI work never routes here.

## Which subagent_type per command (Runtime A)

These are the **native** types — and, while the pool is OFF (D-181, 2026-09-07), the ONLY runtime: every gradeable fan-out (review finders, research grounders, doc reconcilers, rules auditors, implementers) runs here too. <!-- POOL OFF (D-181): These are the **native** types — used for GUI, the authoritative/high-risk pass, and the decide/refute/merge. Under § Dispatch policy the **gradeable fan-out** of these same commands (review finders, research grounders, doc reconcilers, rules auditors, implementers) **defaults to the POOL** (Runtime B); native here is the authoritative complement, not the default worker. -->

| Work | subagent_type | Access |
|---|---|---|
| web-research grounders (`/fabrik-spec`, `/fabrik-spec-review`, `/fabrik-plan-after-chat`, `/fabrik-plan-review`, `/fabrik-data-contract`) | **`fabrik-researcher`** | search + docs MCPs; read-only |
| code/doc/contract review (`/fabrik-review`, `/fabrik-docs-review`, `/fabrik-repo-review`, `/fabrik-rules-review`, `/fabrik-ui-design-review`) | **`fabrik-reviewer`** (or equivalent) | repo-only, no MCP |
| GUI screen build + verify (`/fabrik-execute-plan` GUI phases, Build Verification Loop) | **`fabrik-gui`** / `design-review` | browser MCPs + shell |
| code implementers (`/fabrik-execute-plan`) | general builder | file/edit/Bash + optional `context7`; no search/GUI MCP |

## Pool tool access · Pool model selection — SUSPENDED (D-181/D-182): the pool is OFF by ruling; `pick_models` still returns a dispatchable roster, so do not call it; kept for re-enable

<!-- POOL OFF (D-181, 2026-09-07) — kept verbatim for re-enable:
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
-->

## Dispatch policy — NATIVE for every fan-out while the pool is OFF (D-181, 2026-09-07); BINDING

**⚠️ THE OPENROUTER POOL IS OFF — operator ruling D-181 (2026-09-07), OFF BY POLICY (D-182 revised the mechanism: the credentials stay provisioned, so a `fanout` would still dispatch and spend — this pack is the control; intel monitors `fabrik_analytics.subagent_runs` for any dispatch).** Until the operator re-enables it: **every fan-out a command names runs NATIVE (Runtime A)** — `fabrik-reviewer` / `fabrik-researcher` / `fabrik-gui` / general-purpose — with the SAME unit split, the SAME author-blind rule (§ Role separation) and the SAME decide/refute/merge you own. Nothing records to the flywheel (a native seat has no `AgentResult`) and nothing is scored; `scripts/enforcement/check_subagent_flywheel.py`'s pool-or-declare layer stands down by the same ruling (`_POOL_POLICY_ON = False`, D-182), so **no `NO-POOL:` declaration is owed**. Native sizing has TWO shapes and the command picks by kind. **PARTITIONED — the partitioned review loops (`/fabrik-review` and `/fabrik-repo-review` by FILE; the `term-edit` family's `/fabrik-spec-review` and `/fabrik-plan-review` by SECTION — D-207, D-212, D-218, on the operator's ruling D-203):** the surface is cut into DISJOINT slices by file, the union of the slices IS the full pass and no file's logic is read by two seats — **Opus on the RISKY units only** (concurrency and locks, record and file formats, fleet-synced paths — `scripts/enforcement/`, `scripts/command_run.py`, the hooks, `templates/governance/` — auth, schema, migrations, secrets; a surface with no risky unit still gets ONE Opus seat over its most consequential slice, carved OUT of Sonnet's allocation, never added to it), **Sonnet on every other code and doc unit**, **at most ONE Haiku seat** across the whole surface — for a judgement-shaped inventory class the close-out hygiene script cannot express, and only when the brief NAMES it (the scriptable classes — stale phrases, table and fence shape, dead symbols, `{{` residue — are the script's from round 1's start, never a seat) — and **Fable** (Opus BY NAME when Fable refuses) orchestrating: it partitions, dispatches, adjudicates and EXECUTES every refutation and every confirmed reproduction, never a finder. Size it with `python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --slices opus=N,sonnet=N,haiku=N` (a section partition passes `opus=N,sonnet=N` only — no Haiku seat, D-218; SEATS = Σ slices against the same CLI/box/quota caps, NO floor padding; the kinds are exactly `opus`/`sonnet`/`haiku` — a `fable=` kind, a negative count or a repeated kind is REFUSED, exit 2) and stamp it BEFORE dispatch with `python3 scripts/command_run.py dispatch --seats <n>`. **Round 1 is the ONLY full pass; every round ≥ 2 is a DELTA round**, and its surface is COMPUTED, not judged: `git diff <last round's commit>..HEAD -- <the review's surface>`, plus one hop of callers and callees (grep the changed symbols, or `find_referencing_symbols` where the language server is up) (the hop bounds the EXTENT; what a delta round may COUNT is the fragments' bounded-hop rule — `term-edit`/`term-coverage`), sized by the fix under the fragments' delta budget (`dispatch_headroom.py --delta <n>` beside the round-1 `--slices`/`--units` — one fresh seat PLUS the hygiene script at or under 20 changed lines; D-229 narrows D-208's floor to round 1), plus the tests that import a changed module, plus any sibling commit that landed on the surface since the last round. The class ledger PERSISTS across rounds: a delta round sweeps the classes its diff touches and CITES the rest as standing-clean from the last full pass, and the receipt says which — a round is never a re-scope. **A delta round that dispatches NO finder seat may not close the loop:** the fix diff is the orchestrator's own work and § Role separation binds, so the closing delta round always carries a fresh, non-authoring seat over that diff (Opus if any hunk is risky, else Sonnet); the hygiene script and the orchestrator's own execution never close a review alone. **Quiet is zero CONFIRMED code or doc defects (D-206), never zero raised:** a candidate becomes CONFIRMED only when the orchestrator REPRODUCES it (probe, failing test, or a mutation on a pinned copy), and REFUTED only when it EXECUTES the refutation and the receipt row cites that command and its output; a candidate neither reproduced nor refuted is `RECORDED — unexecuted (<why>)`, one reproduced and kept on purpose is `RECORDED — by design (<owning row>, round N)`, and RECORDED and REFUTED rows never reopen the loop. The Pass Ledger row states the counters in that order — `found: F, new: N, confirmed: C, fixed: X, unexecuted: U` — and the loop closes on `confirmed: 0, fixed: 0` with `unexecuted: 0` or none — a round that FIXED something is never the closing row. **UNITS-SIZED — every OTHER command:** per INDEPENDENT unit of the surface — failure class · file · screen · doc · pack · journey · fact · behaviour — a Sonnet breadth seat plus a Haiku mechanical seat, all dispatched in a SINGLE message so they run in parallel, plus the Opus authoritative seat(s): a 3-unit surface with a mechanical angle is 7 seats (4 with `--mechanical 0`), never a token 1–2 (the executable number is (1) below). The CAP is independence OF THE SURFACE, not of the reader — partition so no unit's ground truth is another's; a unit you cannot brief distinctly is not a seat. ⚠️ **NEVER solo, never two — the FLOOR is three seats for every command that is NOT a partitioned review loop (D-208; under a partition the floor stands down, satisfied by construction — D-218) — the floor binds ROUND 1 only: a delta round at or under the fragments' budget is ONE fresh seat plus the hygiene script (D-229):** `/fabrik-review-scoped`, the grounding and adjudication commands (the researcher floors) and the sweep and audit reviews. Under a partition the floor stands DOWN — it is satisfied by construction, since every non-empty slice kind already keeps its own seat, and the third angle there is the orchestrator's EXECUTION of every candidate rather than a third reader. Where it applies, a surface with fewer than three units still dispatches THREE seats on DIFFERENT angles over it: measured, not assumed (1 seat found 0; 3 over the same surface found 0/5/0, and the 5 held a real fail-open two self-sweeps had read past). (Deliberate DUPLICATE briefs over one small surface are a different, measured technique — `/fabrik-review-scoped` § floor: 1 seat found 0, 3 seats sharing one brief found 0/5/0 and the 5 held a real fail-open. They buy sampling variance, not coverage, and are budgeted as ONE unit.) ⚠️ **Dispatch economics — five constraints, ONE executable number (D-189, operator 2026-09-08: *"maximum count of viable and useful subagents … utilize the box capacity properly, do not cause OOMs, finish fastest with affordable token usage, and utilize proper claude models such as fable, opus, sonnet, haiku"*).** EVERY partitioned review loop runs `python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --slices opus=N,sonnet=N,haiku=N` (a section partition passes `opus=N,sonnet=N` only — no Haiku seat, D-218) before it dispatches, however small the partition — sized at Σ slices with NO floor padding. A units-sized surface runs `--units <N> [--heavy] [--risky <R>] [--mechanical <M>]` before any fan-out wider than the floor and dispatches the `SEATS:` it prints — `min(units × angles + the Opus seat(s), CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS=20, box_cap, quota_cap)`, never below 3 unless a hard cap binds, the fleet is on HOLD, or the round is delta-sized (D-229 — at or under the fragments' budget, then one fresh seat plus the hygiene script); a floor-sized units fan-out at ROUND 1 (1 unit = 3 seats = the floor) needs no script — stamp its three seats with `dispatch --seats 3`. (1) **Maximum (D-191 — the operator's third statement of it)**: the BOX is the ceiling and the units are the PARTITION. Every unit gets one seat per ANGLE — a Sonnet breadth seat and a Haiku mechanical seat — plus the Opus authoritative seat(s), one per risky unit and at least one (a risky unit therefore carries THREE angles: authoritative, breadth, mechanical — cost 8); `dispatch_headroom.py` computes that as the WANTED count and trims it to what the box, the CLI cap and the quota allow for maximum unit COVERAGE — Haiku first, then the extra Opus seats, then Sonnet, never the last Opus seat. **The mechanical angle is grep-shaped and therefore GLOBAL:** `--mechanical <M>` is the number of grep-able classes the surface HAS (inventory · naming · format · links/anchors · counts); when the budget trims below one Haiku seat per unit, each remaining Haiku seat sweeps ONE class across every unit; and a grounding or adjudication surface has no mechanical angle at all (`--mechanical 0`) — a Haiku seat briefed on a judgement returns a claim you must refute, which is spend without recall. A 3-unit surface on an idle box is 7 seats, not 3; before D-191 the rule capped at the unit count while the box allowed 23. Dispatch ALL of what it prints, in ONE message, each seat a distinct unit × angle brief — and when the COST line says TRIMMED, dispatch the trimmed mix, never the per-unit sentence. (2) **Box, no OOMs**: a native seat runs inside its parent `claude` process, so its memory is its TOOL subprocesses — and a "read-only" finder still runs pytest through Bash (measured 2026-09-08: 1.19 GB max RSS), so the box bound applies to EVERY seat: 2 GB planned per `--heavy` seat (pytest/build/render), 1 GB per read-only seat, against `min(MemAvailable, CommitLimit − Committed_AS)` and one core per seat, MINUS the seats sibling sessions DISPATCHED in the last 25 minutes (`command_run.py dispatch --seats <n>`, stamped BEFORE the seats go out and accumulated within the round — a `round --seats` written at the round's close reserved nothing while the seats ran; measured 2026-09-08 on 245 seat transcripts: median 550 s, p95 1354 s; the caller's OWN record is never subtracted) — three sessions cannot each take the whole box in the same minute, but siblings RESERVE, they never starve: a session always gets the floor the box physically has room for. The floor never overrides a hard cap: a box with room for two seats gets two, with the reason. Measured on this box: 24 cores, 47 GB, ~25 GB available with 9 sessions up ⇒ 12 heavy seats. (3) **Fastest**: every seat in ONE message (parallel), never one message apart; keep working while they run. ⚠️ Measured cost of D-191 on this axis (2026-09-08, n=95 completed seats of THIS session's reviews since 09-07 timed on their own transcripts — first to last line; median 446 s, p90 832 s — the typical round; the reservation window in (2) uses the wider n=245 across every account's seats, median 550 s, p95 1354 s, because a reservation must cover the tail, a barrier estimate the typical seat; bootstrap of the round barrier = max of its seats): 3 → 7 seats is **+28 % wall-clock per round** (763 s → 976 s), 6 → 13 is +23 % (an earlier +31 % came from the old synchronous shape's last-turn durations, the same instrument D-193 retired for tokens); and the ledger says round-1 findings predict MORE rounds (r = 0.672, n=36). ⚠️ And the seats are NOT cheap: measured on their OWN transcripts (`<sid>/subagents/agent-*.jsonl` — the parent's result line carries one turn, 10× under), one review's 21 seats billed 69.5M input against the orchestrator's 35.7M — seats ≈ 195 % of the orchestrator's spend AT THE ROUND BOUNDARY (before the orchestrator read their reports; ~150 % once it had — the ratio is a curve, the stable figure is ~3.3M billed input per seat); a 13-seat round is ~43M ≈ 1.4 quota points at ~30M per point. D-191 roughly TRIPLES a run's tokens: "maximum" is paid in tokens AND per-round wall-clock, the quota band in (4) is the guard that bounds it, and the tripwire below (rounds) plus the ledger's `tok_seat_*` columns (cost) are what say whether it was worth it — the operator holds that judgement with the number in front of them. (4) **Affordable**: native seats are subscription quota shared by five accounts, three hub sessions and ~46 repos — at ≥85% on the active account's hottest window (the picture's own `in_drain_band`) the round runs at the FLOOR and sweeps the remaining units NEXT round; with no COOL standby the round still runs but the script names the risk ("0 of N standby(s) are COOL" — every fallback is itself in the band — or "NO standby account at all"), so keep the seats proportionate to the active window; on the fleet HOLD it dispatches nothing. (5) **The right model per ROLE** — and the MECHANISM is the one-token per-dispatch override, `Agent(subagent_type=…, model="opus"|"sonnet"|"haiku"|"fable")`: `fabrik-reviewer` defaults to Sonnet and `fabrik-researcher`/`fabrik-gui` inherit, so a role stated without the token IS Sonnet, authoritative pass included. The four names, one job each: **Fable** = orchestrator/adjudicator and the final validation's authoritative seat (substitutes for, never adds to, the Opus seat there; never a routine finder, never a coder) — ⚠️ **Fable is METERED usage credits, not a subscription window** (the CLI bundle: "Fable 5 requires usage credits"; the quota probe cannot see it): check availability before a run that needs it, and a Fable seat that refuses falls back to Opus BY NAME with the fallback recorded, never silently · **Opus** = the authoritative pass — its RISKY slices under a partition, ≥1 seat on every review — and design-heavy never-route coding · **Sonnet** = breadth, one seat per independent unit, and the default never-route coder · **Haiku** = every unit's mechanical seat (grep-able classes, format, inventory), never codes. GUI stays `fabrik-gui`. Model is chosen by the seat's JOB, never by what is idle. **Price multipliers (operator ruling D-190, 2026-09-08): haiku 1× · sonnet 2× · opus 5× · fable 10×** — "affordable" is a NUMBER, `cost = Σ seats × multiplier` in haiku-units, and `dispatch_headroom.py` prints it (`--mix opus=1,sonnet=5` → 15). Breadth on Sonnet costs 2 per seat; the same seat on Opus costs 5, so an Opus breadth seat costs 2.5× a Sonnet one — whether it buys more recall is UNMEASURED (the D-186 tripwire ledger, with `--seats` recorded, is where that answer will come from), and until it is measured the default is the cheaper seat; a Fable adjudicator costs 10 and is one seat per run, never per unit. The default mix is the script's `full_mix` (D-191): one Opus authoritative seat plus one Sonnet AND one Haiku seat per unit; risk-bearing units (auth/schema/migrations/secrets) each get their own Opus seat (`--risky N`), and when a cap binds the cheapest angle is trimmed first — Haiku, then Sonnet, never the last Opus seat; the `/fabrik-review-scoped` floor is one unit, i.e. the script's 3-seat answer at round 1 (its delta rounds floor at the D-229 one seat). The number is RELATIVE and dimensionless — it assumes equal tokens per seat, and the orchestrator's own reading (at its own multiplier, growing with every seat's report; the ledger's median run reads 37.4M tokens on the orchestrator's transcript (n=31 rows), ~80M/hour just existing) is NOT counted — and the seats' own reading is larger still (~3.3M billed input per seat on its own transcript; ~30M tokens per quota point measured 2026-09-08, so a 13-seat round is ≈ 1.4 points): the quota band guards the seats, and nothing yet guards the orchestrator's own reading; the Fable adjudicator is one seat per run at 10, printed beside the seat total, never inside it. ⚠️ The quota band of (4) is a SEAT band by design and cost stays advisory until `round --seats` rows let the band be re-cut in cost — three Opus seats (15) cost more than six Sonnet (12), and the band cannot see that yet. **And record what you dispatched** — `python3 scripts/command_run.py round --seats <n> …` — because the D-186 tripwire is evaluated with seats unknown on every row that omits it (0 of 97 rounds carried one when this was written). The ledger's token columns now include the SEATS' own usage (`tok_seat_*`, summed from each seat's OWN transcript under `<sid>/subagents/` — synchronous and background seats alike; the parent's result line carries one turn, 10× under, and a background launch none, so the two earlier instruments saw 0 % and then one turn of seat spend), so the tripwire has a cost leg: findings per 100K seat-tokens per run, falling while seats rise, is the manufactured-seat signal. **Dispatch them together and keep working while they run** — measured across the 37 agent-closed runs in the feedback ledger, wall-clock tracks ROUNDS (r = 0.937 over the 32 rows that carry a round count; median **6.7 min/round**, and bimodal — 3.2 scoped vs 10.5 heavy, with only 6 of 32 within ±20% of any single figure). ⚠️ Two honesty bounds on that: 5 further rows record 0 rounds and carry 31% of all measured wall-clock, so the model does not cover them (r falls to 0.638 over all 37); and the ledger has **no seat-count field**, so "seats do not drive wall-clock" is an INFERENCE, not a measurement — `command_run.py round --seats <n>` now records it so the next audit is not blind; blocking on a single seat is how one round becomes twelve minutes of nothing. ⚠️ **The payoff claim is a HYPOTHESIS under test, not a measured result:** in the same ledger, more findings in round 1 predicts MORE rounds (r = 0.672, n=36 — the same figure as (3)) and more wall-clock (r = 0.648, n=37), and `check_ticket_breadth.py` carries a measured `rounds ≈ 1.0 × risk-class count` model — so a wider round may converge slower, not faster. TRIPWIRE (re-based at D-191 — the 20 rows count from 2026-09-08, and the variable that changed last is per-unit-per-ANGLE sizing, not per-unit): if `/fabrik-review`'s median rounds rises above 4 (the median before D-186/D-191, n=9) over the next 20 ledger rows, seat inflation is inflating convergence and the rule reverts to a per-round class budget. ⚠️ **The unit count is what the SURFACE HAS — the rule scales itself and is not a quota to spend:** a one-file diff in a small synced project yields one or two units, not eight, and only the AUTHORITATIVE seat is Opus (breadth is Sonnet, the mechanical seat Haiku) — so the spend is bounded by the UNIT count (one unit = 3 seats = 8 haiku-units), never by how idle that project's box looks. That is what reconciles this with the standing quota line — native seats bill one shared subscription across ~46 repos, so more units means more seats, and a padded unit list means a wasted account. ⚠️ Do NOT "turn the pool off" by emptying `TASK_SUBAGENT_SELECTION.md` — `pick_models` falls through an EMPTY section to the unrestricted vendored `_TABLE` (40 models incl. ones the operator removed under D-159/D-168); under D-182 the only lever that refuses is this text (the credential is provisioned). The pool-default contract is kept below, commented, so re-enabling is an uncomment, not a rewrite.

<!-- POOL OFF (D-181) — the original heading, kept for re-enable:
## Dispatch policy — pool-default for gradeable fan-out, native for GUI/authoritative/decide (BINDING)
-->

**Everything decomposable → a subagent; the only question is the runtime.** Every command task that decomposes is fanned out in parallel wherever suitable (independent work, disjoint `owned_paths` — finder / grounder / reconciler / auditor / implementer classes). Do decomposable work via subagents, not inline; serialize only on a true data dependency or a shared file.

<!-- POOL OFF (D-181, 2026-09-07) — kept verbatim for re-enable:
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
-->

**Native Claude Task subagents (`fabrik-*`, subscription-billed) are for GUI + the authoritative/high-risk pass + the decide/refute/merge.** GUI (`fabrik-gui`, browser MCPs — no pool equivalent); the authoritative line-precise verification (`fabrik-reviewer`/Opus on auth / schema / migrations / secrets / concurrency); and the decide/refute/merge you always own. A native fan-out produces no `AgentResult`, so it **records nothing** to the flywheel (nothing to rank — that is by nature, not a gap).

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
(`data.total_credits - data.total_usage`; live-verified 2026-08-29, the balance was $3.65 — one
7-seat panel is a real slice of that) — and if the balance cannot cover the consult, **ask the
operator for a credit top-up naming the estimated cost; never spend the tail silently and never
substitute a degraded panel**. Single-model `consult()` before any panel; the panel only when the
single opinion conflicts with ours or the fork genuinely needs diversity. Every use reports
`cost_usd` in the run's evidence (the `Result` carries it). Never for gradeable fan-out — that is
the pool's job (`/fabrik-review` already names bypassing `fanout` for ai-consult as throwing away
recording, containment and caps). Live-verify the roster's model IDs before a paid session —
`curl -s https://openrouter.ai/api/v1/models | python3 -c "import sys,json; print('\n'.join(m['id'] for m in json.load(sys.stdin)['data']))" | grep -x "<id>"`
(the public models list, no key needed) — the seats were frozen from a past measured run and IDs rot.

<!-- POOL OFF (D-181, 2026-09-07) — kept verbatim for re-enable:
**⚠️ BOTH layers, never either/or — native is ADDED ON TOP of the pool breadth, not instead of it.** A *substantial* review / repo-review / rules-audit runs the **pool** breadth layer (`run_agents` finders — recall + they record) **AND** native `fabrik-reviewer` (Opus) for the auth/schema/migrations/secrets/concurrency slices + the decide/merge. "Native for the high-risk pass" does NOT mean native-**only**: a high-risk surface needs the pool breadth *plus* the native authoritative pass. Going all-native and skipping the pool layer lands **zero** flywheel rows (the flywheel learns nothing) — the exact miss `check_subagent_flywheel.py` advisory-WARNs (a big changed surface with no pool run). Trivial one-file reviews may run a single layer; anything substantial runs both.

**Trust = the METHODOLOGY, not a model pin.** A review's trust does NOT come from which pool model ran; it comes from **≥1 native Opus finder as the authoritative decider + every pool finding independently refuted before it is acted on** — both hold regardless of which models the flywheel currently ranks top. So never gate trust on a model name; gate it on the native-Opus-authority + refutation invariant.

**Always cost-conservative + you adjudicate:** select via § Pool model selection (`pick_models`); pass an explicit `max_cost_per_mtok` only when a run needs a hard budget. Cheap pool workers *surface* candidates; you refute / merge / decide and own the verdict.
-->

## Pool vs native · Parallelism — SUSPENDED (D-181): the runtime for every fan-out is native (Runtime A); the pool comparison and the two parallel shapes are kept for re-enable

<!-- POOL OFF (D-181, 2026-09-07) — kept verbatim for re-enable:
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
-->

## Parallelism (Runtime A — native) — what is known, and what is NOT

Seats dispatched as multiple Task calls **in one assistant message** are started together; seats dispatched one message apart are serial by construction, which is the failure this pack exists to prevent. The ceiling is **`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`, default 20** — unset on this box, so 20 here (read out of the CLI bundle 2026-09-08, v2.1.263: `pt=20; … CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS??pt`; re-check it with `grep -aoE 'MAX_CONCURRENT_SUBAGENTS.{0,80}' "$(readlink -f "$(which claude)")"` rather than trusting this line). It is per-SESSION, not box-wide, so three hub sessions each get their own budget. ⚠️ **Past the ceiling a seat is REFUSED, not queued** (`Concurrent subagent limit reached … Do not retry`) — a refused seat is a FAILED seat and its absence is never a clean round. Under D-191 a wide surface DOES reach the ceiling (16 units want 33 seats) and `dispatch_headroom.py` trims to it — the cap is a HARD cap the script never exceeds; below it **the binding constraint on fan-out width is the box and subscription QUOTA, not concurrency** — check headroom, not the cap. (§ Parallelism — the two shapes, below, is Runtime B's and lives inside a `<!-- POOL OFF -->` comment with the rest of the pool contract; its `max_concurrency` default of 4 is the POOL's, not this one's.)

## Role separation (review loops) — who hunts LAST is never the author

The loop-closing round's **FINDER pass** runs in a context that did **not author the artifact** — a
dispatched fresh subagent (pool or native), or a post-compaction session re-grounding from disk. An
author's own quiet round never closes a review loop: the context that shaped the artifact is the one
least able to see its gaps (an author re-reads intentions, not text). The closing round of a `term-edit`
loop is a delta round with a fresh seat (D-212). **One sanctioned exception — the solo
self-convergence loop:** a command whose loop dispatches NO seat that reads the artifact for
defects — no finder, grounder, auditor or reconciler — anywhere; a seat that DRAFTS a section of
it is none of those (an author self-convergence pass, e.g. `/fabrik-ui-design`'s own convergence,
whose per-screen seats draft the contract) closes with its own full fresh read — independence
there is deferred to the PAIRED review command that follows it (`/fabrik-ui-design-review`), never
silently skipped. **Adjudication —
decide/refute/merge — stays with the orchestrator** (CLAUDE.md § Subagent fan-out: "the
decide/refute/merge you own"); this rule governs who HUNTS last, never who adjudicates. The loop
fragments' fresh/independent-round language defers to THIS definition of independent.

**Per-command dispatch mode — SUSPENDED (D-181): every command's fan-out is native seats; the pool shapes below are kept for re-enable.**

<!-- POOL OFF (D-181, 2026-09-07) — kept verbatim for re-enable:
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
-->

## NEVER route to the pool (fabrik-lib PROPOSED_RULE)

Auth/identity/session/crypto · schema/migrations · secrets/`.env`/keys · security controls (RLS, rate-limits, `final_gate`) · deploy/infra. These stay with the primary (human-supervised) agent. **Never web/MCP-enable a task carrying sensitive context** — the model's output exfiltrates via a scraped URL. Keep the bwrap sandbox on (`sandbox=True`, fail-closed).

## The mcp.json source-of-truth

The canonical MCP server list is a hub-owned standard-format file — `/opt/fabrik/mcp.json` (`{"mcpServers": {name: {type, command, args, env}}}`, keys via `${ENV}` expansion, never inline). The pool's MCP client reads it via `AgentSpec.mcp_config` (path → unwrap the `mcpServers` key; dict → the bare server map).

**Since the 2026-08-30 MCP split, MAIN-AGENT servers are per-repo:** each repo's `.mcp.json`
(project scope — gitignored, because postgres-pro's env carries the repo's resolved `DATABASE_URL`)
is EMITTED by the hub's `scripts/sysadmin/emit_mcp_project_config.py` from the roster-ruled sets in
`docs/workstation/mcp-roster.md`; the user-level rosters carry only the universal 6. Never hand-edit
an emitted `.mcp.json` — change the roster/ledger ruling, then re-run the emitter.

Adding a tool touches exactly: the roster ruling + emitter table (main agents, per repo) →
`mcpServers` in the relevant Runtime-A agent type → `/opt/fabrik/mcp.json` (pool) — never a command
brief.

## Report every pool run — SUSPENDED (D-181): a native seat has no `AgentResult`, records nothing, owes no score

<!-- POOL OFF (D-181, 2026-09-07) — kept verbatim for re-enable:
## Report every pool run — the results table AND the flywheel (both, always)

After any **pool** (`run_agents`, Runtime B) dispatch you EVALUATE, emit **BOTH** — sharing **one** quality verdict (judge once, put the same 0–5 in both). A run that showed a table but no flywheel row (or vice-versa) is **half-done**:

1. **A results table** (one row per unit) so a human can compare models at a glance — use the helper `results_table([{ "unit":…, "model":…, "result":<AgentResult>, "quality":0-5, "fixes":… }, …])`. Provider / Cost / Latency / **Out** (`out_tokens`) come straight from the `AgentResult`; **quality + confirmed-fixes are YOUR verdict** after materializing the diff and running the gate/tests/review.
2. **A flywheel row per unit** — **`record_agent_run(spec, result, quality_score=<the same 0-5>, project=<name>)`**. ⚠️ the older `record_run(result, …)` **silently no-ops** on a raw `AgentResult` (it wants a dict; `model`/`task_type` live on the *spec*) — always `record_agent_run(spec, result, …)`. On the VPS `SUBAGENT_RUNS_DSN` connects directly; on WSL dev pass a peer-auth `connect=` factory. It is fail-open (returns `False` silently on a DB problem) — to prove the plumbing, SELECT the row back, don't trust the return.

**A native Claude-Code-subagent (Runtime A) dispatch produces NO `AgentResult` — it CANNOT record; the flywheel is pool-only (Runtime B).** So a native-fan-out command carries no flywheel footer (see § Pool vs native). Inline / no-dispatch → nothing to record. Telemetry design: `docs/superpowers/specs/archived/2026-07-06-subagent-runs-telemetry-design.md`.
-->

## Vendored-module bug → UPSTREAM_FEEDBACK (binding)

When a project fixes a real bug in a **vendored `fabrik-lib` module** (e.g. `libs/subagents/`), it MUST append the fix — symptom + fix + date — to `/opt/fabrik-lib/<module>/UPSTREAM_FEEDBACK.md`. That file is the **one write allowed back into `/opt/fabrik-lib`** (cross-repo HARD STOP otherwise); the module author reads + resolves it, so the fix isn't silently lost on the next re-vendor. Fixing a vendored module without the entry breaks the loop.

## Banned

- A command brief that restates tool lists instead of naming a `subagent_type` / pointing here.
- A GUI/browser task routed to the pool (no equivalent — Runtime A/primary only).
<!-- POOL OFF (D-181, 2026-09-07) — kept verbatim for re-enable:
- A pool task with `sandbox=False`, an inline API key, or web/MCP enabled while it carries sensitive context.
-->
- Hard-coding the `mcp` SDK v2 API or the Tool schema attribute name.
<!-- POOL OFF (D-181, 2026-09-07) — kept verbatim for re-enable:
- Naming a model roster, a per-stage ranking, or a `$X` price cap in this pack — the roster lives in the module `_TABLE` + `TASK_SUBAGENT_SELECTION.md`, and there is no always-on cap; NO model may appear by name here.
-->
- Gating a review's trust on a specific pool model name instead of the methodology (native-Opus authority + refutation).
<!-- POOL OFF (D-181, 2026-09-07) — kept verbatim for re-enable:
- A pool run that emitted a `record_agent_run` but no `results_table` (or vice-versa) — both, one verdict. (And never `record_run(result, …)` — it no-ops; use `record_agent_run(spec, result, …)`.)
-->
- Telling a **native** (Runtime A) fan-out to record a flywheel row — it has no `AgentResult`; recording is pool-only.
- Fixing a bug in a vendored `fabrik-lib` module without an `UPSTREAM_FEEDBACK.md` entry.
