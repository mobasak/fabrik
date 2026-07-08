# PROPOSED RULE — routing tasks to the `subagents` pool

> **Status: proposal.** This is a design-discipline note that ships WITH the
> `subagents` module; it is not an installed `.windsurf/rules` pack. A consuming
> project that adopts `subagents` should fold these guardrails into its own rules.

The `subagents` runtime makes it cheap to fan work out to N models over
OpenRouter. That leverage cuts both ways — the guardrails below keep it safe.

## Never route these to the pool

The pool runs a **general (possibly-adversarial) model** with tools in a worktree.
`run_command` is confined by an **OS sandbox** (bubblewrap, on by default — see
"Keep the sandbox on" below), but that stops *writes outside the worktree*, not bad
judgement. Do NOT hand it tasks where a wrong action is unrecoverable or exfiltrates trust:

- **Auth / identity / session / crypto** code — a subtle bug is a vulnerability.
- **Schema / migrations** — a bad migration corrupts data; humans review these.
- **Secrets / `.env` / credentials / key material** — never in a task, never in
  `owned_paths`. The sandbox is read-only-root, so a command can still *read* any host
  file the user can — and while `--unshare-net` blocks phoning out, **the model's output
  itself exfiltrates** (it flows back to the orchestrator). No-network does NOT make reads
  safe: keep real secrets out of the task, `owned_paths`, the worktree, AND any path the
  command could read.
- **Security controls** (rate limits, RLS, permission checks, `final_gate`).
- **Deploy / infra / anything that mutates production.**

These stay with the primary (human-supervised) agent.

## Keep the sandbox on (non-negotiable for tool-enabled pools)

`AgentSpec.sandbox` defaults to `True` and the runtime is **fail-closed**: a tool-enabled
agent whose host lacks `bwrap` is **refused up front** (no worktree, no paid call) with an
actionable error — it never runs unsandboxed. So the safe path is the default; you only
have to NOT break it:

- **Install bubblewrap** on every host that runs tool-enabled agents:
  `apt install bubblewrap` (Debian/Ubuntu/WSL2) · `dnf install bubblewrap` (Fedora). Needs
  unprivileged user namespaces (default-on modern kernels; WSL2 yes, WSL1 no). Put it in
  the host's provisioning so agents don't hit the fail-closed refusal.
- **Never set `sandbox=False`** except for a genuinely trusted agent on a host without
  `bwrap`, and say why in the call site. Treat `sandbox=False` in a review like a disabled
  security check. (A cheap project lint: flag any `sandbox=False` / `sandbox = False`.)
- **Absolute paths in a task are a smell, not a shield.** The sandbox makes them harmless
  (writes outside the worktree → `EROFS`), but prefer worktree-relative briefs — an
  absolute shared-repo path is exactly what turned an unsandboxed pool into a data-loss
  incident (see `UPSTREAM_FEEDBACK.md`, 2026-07-06).
- Single-shot pools (`tools_enabled=False`) run no commands, so they need neither `bwrap`
  nor the sandbox — the model only emits text/files the caller writes.

## Select the model with `pick_models` — the allowed pool (don't hardcode)

**Call `pick_models(task_type, n=…, …)` — do not hand-pick a model.** It returns, best-first, from
the **allowed cost-vetted pool** (fleet policy, 2026-07-08: `deepseek-v4-flash`, `deepseek-v3.2`,
`deepseek-v4-pro`, `minimax-m2.5`, `minimax-m3` — output **$0.18–$1.20/Mtok**), ranked **per task
type by the flywheel** (real recorded runs, not a static guess). It honors `max_cost_per_mtok` (a
*tighter* ceiling), `exclude=` (drop a model that failed this session), and `prefer="value"` for
cost-sensitive fan-out. The pricier/weaker models (glm-5/5.x, kimi, grok, qwen) are deliberately
**not** in the default pool — reach one only for an explicit, opt-in benchmark, never as a default.

**`pick_models` is the SOLE gatekeeper of the ≤$1.5/Mtok fleet cap — enforced in code, always.** The
cap (`_MAX_POOL_PRICE_PER_MTOK = 1.5`) lives in `pick_models` itself, not in any caller or aggregation
step: even if the synced `CODING_SUBAGENT_SELECTION.md` is refreshed with a pricier model, or a caller
passes a looser `max_cost_per_mtok=`, a >$1.5 model can **never** reach the default (Auto) pool —
`max_cost_per_mtok` can only make the ceiling *tighter*. This is why **rule/command packs name no model
rosters**: they state only the invariant (≤$1.5, turn-count-beats-token-price) and the mechanism (call
`pick_models`); the single named default is **`minimax-m3`** (best overall worker). The rosters live in
one place — this module's `_TABLE` + the synced doc — so there is no 3-way list to drift.

**On-request tier — `allow_above_cap=True`.** A pricier benchmarked model stays in the data (priced,
rankable) but is never returned by default. To deliberately reach one — an explicit opt-in benchmark —
pass `pick_models(..., allow_above_cap=True)` (then only your own `max_cost_per_mtok`, if any, applies).
Treat `allow_above_cap=True` in a review like `sandbox=False`: justified at the call site or it's a bug.

`pick_models` just encodes the rule below (turn count beats token price — the cheapest model takes
2–3× the turns on multi-step work and costs more overall), so you rarely need it by hand:

| Task | Model tier |
|---|---|
| mechanical edit / transcription / single-file with a complete spec | cheapest that can do it |
| multi-file pattern-matching, debugging judgment | mid (e.g. Sonnet) |
| design judgment, broad-codebase reasoning | most capable (e.g. Opus) |
| research / docs / prose (no tools) | `tools_enabled=False`, cheap tier |

## Bound every agent

- Set `owned_paths` to the **narrowest** globs the task needs — this drives both
  the parallel/serial partition and the out-of-scope check. Keep them **disjoint**
  across agents you want to run in parallel. Globs are gitignore-style: `*` stays
  within one path segment, `**` crosses directories.
- **Do NOT add `git` or network tools to `allowed_commands`.** The runtime
  serializes its own worktree admin, but a subagent running `git commit`/`git push`
  in its worktree would mutate the shared `.git` (objects/refs) concurrently with
  other agents (a race). The OS sandbox now RO-binds the shared `.git`, so a subagent
  `git` write would fail with `EROFS` anyway — but the race + needless complexity mean:
  the default allow-list (`python`/`python3`/`pytest`/`ruff`/`mypy`/`bandit`/`semgrep`) omits
  `git`; keep it that way.
- **Web tools (`web_tools`) are PAID + hit the internet — enable per task type,
  not by default.** Turn on only what the task needs (research → `web_search`+
  `docs_lookup`; scraping → `web_scrape`/`web_crawl`) and set the matching
  `*_API_KEY`. `max_cost_usd` does NOT bound web-API spend — cap `max_turns`
  conservatively for web-enabled agents and audit `AgentResult.tool_calls` /the
  ledger after a run. Never route a task to a web-enabled pool if the model could
  exfiltrate sensitive context to a scraped URL.
- **MCP tools (`mcp_servers`) run OUTSIDE the sandbox — keep them to research.** They
  give the pool Claude Code's MCP research servers, but MCP calls execute in the loop
  process, not the bwrap sandbox, so a filesystem/shell/exec server would be a full
  sandbox bypass. Only the `SAFE_RESEARCH_SERVERS` allowlist (`exa`/`brave-search`/
  `firecrawl`/`context7`) is enabled by default; anything else needs an explicit
  `mcp_allow_unlisted=True`. Keep browser/FS/exec MCPs OFF the untrusted pool; point
  `mcp_config` at the fleet source-of-truth `/opt/fabrik/mcp.json` (non-dot). Like
  `web_tools`, MCP spend is bounded by `max_turns`, not `max_cost_usd`.
- Always set `max_turns`, `max_cost_usd`, and `wall_clock_s`. Unbounded is a bug.
- Prefer `tools_enabled=False` when the task is pure text — no worktree writes.

## Verify before you accept (the diff is a proposal, not a result)

`run_agents` **never applies** an agent's changes. For every result:

1. `status == "out_of_scope"` → reject; the agent left its lane.
2. `status == "error"` → its `diff` is partial and NOT scope-guarded; review or discard.
3. `status in ("done", "capped")` → **read the diff, run the tests/gate yourself**,
   and only then apply. A model's "done" is a claim; your green run is the proof.

## Give the agent a DISTILLED system prompt — not the whole rulebook

`AgentSpec.system` is the **durable contract**; `task` is the **per-request** work. The
split that keeps an agent from drifting: *would you write this rule every turn? → `system`;
does it change per request? → `task`.* Best practice (2025–2026, incl. Anthropic's own agent
guidance + the Claude Code 2.0 brevity shift) is a **short** system prompt — aim
**~200–800 tokens** — with load-bearing rules first and the one non-negotiable repeated last.

- **`system` = `methodology(kind)` + your project's COMPACT rule digest.** `methodology("code")`
  already carries the generic discipline (test-first, stay in scope, no hardcoded secrets,
  name real edge cases, re-read your diff). Append only the project rules a task can't restate
  every time — for a fabrik-lib module build that's the **recipe digest** (kebab-dir/snake-pkg,
  `.tmp` not `/tmp`, env-driven, vendored-not-imported, ships README+requirements+≥1 test, the
  gate is `final_gate_fabrik_lib.py`) + the **sandbox/tool rules** (relative paths only, no
  `git`/shell-chaining, allowed commands, tests offline). End with the non-negotiable:
  *"done only when the gate is green."*
- **`task` = the grounded, self-contained work.** A `/fabrik-spec`/`/fabrik-plan` output is
  already project-compliant (gate command, conventions, `path:line`) — it carries the *what* +
  the project rules, so it belongs in `task`, not duplicated into `system`.
- **Do NOT dump `CLAUDE.md` / the full style guide.** It's mostly per-request or deploy/ops
  context; wholesale it violates brevity + on-demand-loading and buys nothing. Distill.
- The **caller composes** this — `subagents` is generic and ships no project-specific rules.

## Record every run to the flywheel (mechanical is automatic; quality is YOUR verdict)

Two tiers, by design (`pg_ledger.record_agent_run` builds the merged record + `INSERT`s the
mechanical row; the table is not writable beyond that):

- **Mechanical (cost/turns/latency/status/model/provider/tool_calls) — the module captures it
  factually.** `cost_usd` is the OpenRouter-billed `usage.cost`, not an estimate.
- **`quality_score` — the ORCHESTRATOR (you) records it AFTER judging.** The module can't run
  your gate/tests, so quality is your verdict. After you evaluate each result (materialize the
  diff → run the gate/tests, or your review), call
  `record_agent_run(spec, result, quality_score=<0–5>, project=<project>)` — one authoritative row
  per run. This is the fleet-wide `subagent_runs` flywheel `pick_models` learns from; **skipping it
  means the ranking never improves.** On the VPS `SUBAGENT_RUNS_DSN` connects directly; on WSL dev
  pass a peer-auth `connect=` factory (postgres there is peer-auth-only, so the TCP DSN fails).
- **⚠️ Call `record_agent_run(spec, result, …)`, NOT `record_run(result, …)`.** The row's
  `model` + `task_type` come from the **spec**, not the `AgentResult`; passing a raw `AgentResult`
  to the low-level `record_run` matches `isinstance(record, dict) → False` and **silently no-ops**
  (fail-open — no row, no error). `record_agent_run` merges the pair via `ledger.agent_record` and
  is the only correct one-call flywheel write.
- **You are IN the loop — recording is mandatory, not a nicety.** The per-task ranking
  `pick_models` uses for the **allowed pool** is refined by exactly these rows: every agent that
  dispatches the pool and records its verdict makes the *next* project's selection sharper (and
  keeps the current five honestly ranked as models change). So it is a closed loop — dispatch →
  judge → `record_agent_run` → better `pick_models` for everyone. One authoritative row per run,
  always; an unrecorded run is a data point the fleet permanently loses.
- Orchestrator commands that dispatch pools (e.g. `/fabrik-execute-plan`, `/fabrik-review`)
  **must** bake this record step into their flow — it is how the allowed-pool rankings stay current.

## Report every pool run — the results table AND the flywheel (both, always)

After a pool run the orchestrator MUST produce **two** things — no exceptions:

1. **A results table** (one row per unit) so a human can compare the models at a glance:

   | Unit | Model | Provider | Cost | Latency | Out | My quality score | Confirmed fixes |
   |---|---|---|---:|---:|---:|:--:|---|
   | web-quota | minimax-m3 | Minimax | $0.0209 | 160s | 14.0k | 5/5 | rate-limit bypass + billing fail-open |

   Use the helper — `results_table([{"unit":…, "model":…, "result":<AgentResult>, "quality":0-5,
   "fixes":…}, …])` renders exactly this. Provider/Cost/Latency/Out come straight from the
   `AgentResult` (`out_tokens` is the summed completion tokens); **quality + confirmed-fixes are
   YOUR verdict** after materializing the diff and running the gate/tests/review.

2. **A flywheel row per unit** — `record_agent_run(spec, result, quality_score=<the same 0-5>,
   project=<name>)` (pairs the spec's model/task_type with the result; NOT `record_run(result, …)`,
   which silently no-ops on a raw `AgentResult`).

The table is the **human report**; the flywheel is the **machine record** that refines `pick_models`
fleet-wide. **Do BOTH** — judge once, put the same score in both. A run that emitted a table but no
`record_agent_run` (or recorded but showed no table) is half-done. Bake both into the command flow.

## Provenance is not optional

Keep the ledger (`ledger_path`) — it is the audit trail of what each model was
asked, what it produced, and what it cost. Review it after a pool run.
