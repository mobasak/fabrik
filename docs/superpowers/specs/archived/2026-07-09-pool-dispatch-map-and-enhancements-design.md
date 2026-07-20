# Design Spec — Pool fan-out dispatch map (final, verified) + `subagents`-module enhancements

Status: CONVERGED
Date: 2026-07-09
Converged: 2026-07-09 (/fabrik-spec-review — 3 passes to an edit-free md5-verified no-op; every cited path:line re-opened + verified this session; caught 2 stale facts — pg_ledger `:96→:97` and github plan-2 now EXECUTED/archived — and 2 missing template sections)
Module touched: `subagents` (VENDOR+ENHANCE — canonical in `/opt/fabrik-lib`; proposed, not built here)
Governance touched: `.windsurf/rules/core/62-using-subagents.md`, `CLAUDE.md`, the 12 `~/.claude/commands/fabrik-*.md`

## Goal

Two coupled deliverables, so the fleet dispatches the pool **correctly** and **generously**:

1. **The definitive, verified per-command pool fan-out map** — the dispatch contract (worker mode ·
   `task_type` · `tools_enabled` · `owned_paths` strategy · `n` · records) grounded in each command's own
   § Subagents **and the module's REAL runtime behavior verified this session** — so `62 § Dispatch policy`
   + `CLAUDE.md` + the command files can be reconciled to **one** source of truth.
2. **The enumerated `subagents`-module enhancements** fabrik-lib should make to eliminate the dispatch traps
   this session exposed (the answer to *"what enhancement do you need in the subagents module?"*).

This spec is a **codification of verified facts + a change list**, not a new feature build. Its value is that
the dispatch rules were demonstrably wrong in practice — including in the commands' own guidance and in my own
dogfood — and this pins them.

## Why this spec exists (the motivating evidence)

An adversarial verification pass this session found the raw `run_agents` API has **five silent-failure modes**,
all hit or nearly hit in real dispatches:

| Trap | Wrong result | Proof (`path:line`) |
|---|---|---|
| `tools_enabled=True` + empty/overlapping `owned_paths` | **serial, not parallel** (collapses to one overlap group) | `workspace.py:321` (`unrestricted = not owned[i] or not owned[j]`), `agent.py:430`; my 1st dogfood ran serial |
| `pick_models` default `n=1` | 1 model, not the intended fan-out | `select.py:333`; dogfood printed 1 model |
| `record_run(raw AgentResult)` | **silent no-op** → 0 flywheel rows | `pg_ledger.py:97` (isinstance-dict guard) |
| quality judged post-hoc + INSERT-only writer role | rows land `quality_score=NULL` | earlier dogfood; `pg_ledger.record_agent_run` |
| forgot `results_table` / `record_agent_run` / DSN | half-recorded or unrecorded | recurring |

**The serialization trap is in the commands' own guidance:** `fabrik-data-contract.md:108` says "one grounder
per surface, `tools_enabled=True`, run them **in parallel**" — but those grounders have no `owned_paths`, so
they **serialize**. The guidance is wrong wherever it pairs `tools_enabled=True` + "parallel" without disjoint
`owned_paths`.

## Success criteria (testable)

1. `62 § Dispatch policy` states the **two-shape parallelism rule** verbatim + the `n`-default + `max_concurrency=4`
   + the per-command map — verifiable by grep of `62-using-subagents.md`.
2. Every command that pairs `tools_enabled=True` + "parallel" is corrected to **RO-inline** or **disjoint
   `owned_paths`** (starting with `fabrik-data-contract.md:108`) — verifiable by re-reading each command's § Subagents.
3. The `subagents` enhancement list is delivered to the fabrik-lib AI, and `fanout()` (or equivalent) lands in
   canonical such that: a read-only fan-out is **parallel by default**, each unit **auto-records**, and a
   serialize-prone dispatch **warns** — verifiable by a module test.
4. No row in the dispatch map is ungrounded — each fact traces to a `path:line` in the grounding table below.

## Grounding (this session — freshness satisfied; internal module, path:line verified)

| Fact | Verified at |
|---|---|
| Read-only (`tools_enabled=False`) workers → each its own group → **all parallel** | `agent.py:435` |
| Writer (`tools_enabled=True`) workers → routed through `disjoint()`; **empty `owned_paths` overlaps everything → serial** | `agent.py:430-434`, `workspace.py:299-323` |
| `pick_models(kind, n)` returns `n` best-first under ≤$1.5 cap; **default `n=1`** | `select.py:333`; empirically `pick_models("review", n=3)` → 3 distinct |
| Prices (vendored fallback; synced doc canonical): m3 $1.20 · v4-flash $0.18 · m2.5 $0.48 · v3.2 $0.343 · v4-pro $0.87 | `select.py:44-61` |
| Best per kind: review/plan/docs/research→`minimax-m3`; code→`deepseek-v4-flash`; spec→`minimax-m2.5` | `select.py:120-163`; empirically via `pick_models` |
| Worker tools: `read_file · write_file · apply_patch · list_dir · grep · run_command` (surgical `apply_patch` exists) | `tools.py` dispatch |
| `web_tools`: web_search · web_search_brave · web_scrape · web_crawl · docs_lookup | `web_tools.py:36` |
| MCP research servers (hub): exa · brave-search · firecrawl · context7 | `mcp_tools.py:62` |
| `load_env` auto-loads `OPENROUTER_API_KEY`+`SUBAGENT_RUNS_DSN` from repo `.env` then shared file (manual `source` redundant) | `_dotenv.py:141`; `/opt/fabrik/.env` has both |
| `max_concurrency` default = **4** (parallel groups run 4-at-a-time) | `agent.py:394,462` |
| `record_agent_run(spec,result,…)` writes; `record_run(raw AgentResult)` no-ops (now warns loudly) | `pg_ledger.py:97` |
| github read-only: `_force_github_readonly` + write-verb verify (legacy prefixes **and** `*_write` toolsets) present in canonical | `/opt/fabrik-lib/…/mcp_tools.py:98,78` |
| **github plan-2 DONE** — plan **archived**, lock `released`, `final_commit: b3dc97d`; **hub copy still lacks `github`** → the hub re-vendor is the ONLY remaining gate | plan-lock + archived plan, 2026-07-09 |

## The verified parallelism rule (the linchpin — must land in `62`)

**A pool fan-out runs in parallel ONLY under one of these two shapes; anything else silently serializes:**

- **Read-only fan-out (finders / grounders / auditors / reconcilers):** `tools_enabled=False` +
  `allow_ungrounded=True`, with the unit's content **inlined into `task`**. Each worker is its own group →
  **all parallel** (bounded by `max_concurrency`, default 4 — raise for wide fan-outs). *This is the default
  for every gradeable read-only fan-out.*
- **Tools-enabled fan-out (workers that must read/write files themselves — implementers, or graders that
  read the tree):** `tools_enabled=True` + **disjoint `owned_paths`** (one unit's files each). Disjoint globs →
  parallel worktrees. **Empty or overlapping `owned_paths` → one group → SERIAL.**

`pick_models(task_type, n=<K>)` for a K-model fan-out (**pass `n`**; default is 1). Every pool unit owes
`record_agent_run(spec, result, quality_score, project)` **and** `results_table` — never `record_run`.

## The verified dispatch map (per command)

Worker mode legend: **RO** = read-only parallel (`tools_enabled=False`+`allow_ungrounded=True`, content
inlined); **TE-disjoint** = `tools_enabled=True` + disjoint `owned_paths`; **writer** = TE-disjoint in a
worktree. All pool units record. `[+github]` = pending the **hub re-vendor** only (plan-2 EXECUTED 2026-07-09).

| Command | Pool fan-out (mode · task_type · n) | Native (Opus) | Notes |
|---|---|---|---|
| /fabrik-review, /fabrik-repo-review | finders **RO** · `review` · `n=3` differently-biased; repo-review = 20+ units in waves | `fabrik-reviewer` on auth/schema/migrations/secrets/concurrency; decide/merge | `[+github]` review a live PR (files/CI/comments) |
| /fabrik-rules-review | one auditor **RO** · `review` per pack | ~20% spot-audit + cross-pack contradiction; merge | pack text inlined |
| /fabrik-spec (1a/1c) | research **RO or TE** · `research` · one per dep/approach · `web_tools`+MCP | vendor-ladder verdict; approach choice | `[+github]` ground API at source |
| /fabrik-spec-review, /fabrik-plan-review | grounders **RO or TE-disjoint** · `research`/`plan` · one per phase/dep | gating-claim verify; verdict | `[+github]` cross-repo re-ground |
| /fabrik-plan-after-chat, /fabrik-data-contract | grounders — **RO (inline)** OR **TE-disjoint (one surface/entity each)** · `plan`/`research` | ~20% verify-sample; the write | **fixes the data-contract:108 serialization trap** |
| /fabrik-docs-review | one reconciler **RO or TE-disjoint** · `docs` per doc/subsystem | ~20% re-check; route fixes | `[+github]` cross-repo doc claims |
| /fabrik-execute-plan | implementers **writer** (TE-disjoint `owned_paths`, worktrees) · `code` · TDD via `run_command` ‖ finders **RO** | orchestration; merge; **writes/PR-merge**; authoritative review | `[+github]` CI + cross-repo context |
| /fabrik-ui-design-review | axis-reviewers **RO** · `review` (design-system·data-wiring·coverage·consistency) | design-coherence judgment; merge | pool-default (text-vs-text) |
| /fabrik-ui-design | non-visual logic/tests only | **`fabrik-gui`** builds/drives screens | no pool browser equivalent |

## Command + rule-file update list (the point of the map)

1. **`62 § Dispatch policy` — add the parallelism rule verbatim** (the two shapes above) + the `n`-default +
   `max_concurrency=4` facts + this per-command map as the canonical reference. This is the highest-value edit:
   the rule that would have stopped the trap does not currently exist anywhere.
2. **`fabrik-data-contract.md:108`** — the "`tools_enabled=True` … in parallel" grounders **serialize**. Fix
   to either RO (inline each surface's content) OR TE-disjoint (assign `owned_paths` per surface/entity).
3. **Audit every command that pairs `tools_enabled=True` + "parallel"** (grep hit: data-contract, spec,
   spec-review, plan-review, plan-after-chat, docs-review, rules-review, ui-design-review) — each must specify
   **either** RO-inline **or** disjoint `owned_paths`, never `tools_enabled=True` + empty `owned_paths` +
   "parallel". (Note: /fabrik-review + /fabrik-repo-review already say `tools_enabled=False`+`allow_ungrounded`
   — **correct/parallel**; they are the reference pattern.)
4. **`CLAUDE.md § Subagent fan-out`** — one-line pointer to `62`'s parallelism rule (no duplication).
5. **`[+github]` rows stay documented-but-PENDING** until the hub re-vendors `libs/subagents` (plan-2 is
   `EXECUTED`/archived as of 2026-07-09; the re-vendor is the only remaining step — actionable now).

These edits are a **follow-up gated on this spec's approval** — not done here (this is the design).

## `subagents`-module enhancements needed (fabrik-lib — the answer to the question)

**VENDOR + ENHANCE `subagents`** (canonical, fabrik-lib-owned → they build; I propose). Ranked by value:

1. **A footgun-free dispatch helper — `fanout()` (subsumes 4 of the 5 traps).** One call:
   `fanout(task_type, units, *, n=3, mode="read_only"|"tools", project, quality_fn=None) -> (results, table)`.
   Internally: `pick_models(task_type, n)`; builds **parallel-safe** specs (mode `read_only` → each unit's
   content inlined, `tools_enabled=False`, `allow_ungrounded=True`; mode `tools` → assigns **disjoint
   `owned_paths`** per unit); runs `run_agents`; **auto-records** each via `record_agent_run` (never
   `record_run`); returns results + the rendered `results_table`. Makes correct-parallel-recording dispatch the
   path of least resistance — the whole "friction is why the pool isn't used" thread, fixed in code not prose.
2. **Serialization guard (cheap safety net, independent of #1).** In `arun_agents`, when ≥2 `tools_enabled=True`
   workers land in one overlap group (would serialize), emit a **loud warning**: *"N tools-enabled workers with
   overlapping/empty owned_paths will run SERIALLY — pass disjoint owned_paths, or tools_enabled=False for a
   read-only fan-out."* Non-breaking; pure visibility. Directly prevents the trap I hit even without #1.
3. **Quality-score back-fill (fixes the NULL-quality flywheel gap).** A `set_quality(agent_id, score)` writer
   (needs an UPDATE/upsert grant on `subagent_runs`) OR a serialize→reconstruct path, so **judge-once-then-record
   survives the process boundary** — today rows land `quality_score=NULL` because the orchestrator can only score
   after reading output, and the writer role is INSERT-only. Without this the flywheel learns cost/latency but
   not quality (its whole purpose). (Flagged earlier this session; restated as a formal ask.)
4. **(DONE — fabrik-lib landed it)** `record_run(raw AgentResult)` now warns loudly on stderr instead of silent
   no-op. Kept here for completeness.

## Rejected alternatives

- **Document-only — fix `62` + the commands, no module helper.** Rejected as the *sole* fix: prose is exactly
  what failed all session (I read the module cold and still dispatched serially). The `62` rule is necessary
  but insufficient; the helper is what makes correct dispatch the path of least resistance. Kept **both** (the
  `62` rule AND the helper), not either.
- **A blocking gate that fails the build on a serialize-prone dispatch.** Rejected: dispatch happens at runtime
  inside an agent turn, outside the static gate's reach; a **runtime warning** (enhancement #2) is the correct
  seam, not a `final_gate` check.
- **Project-local-only helper (no fabrik-lib enhance).** Rejected (operator's call this session): it forks the
  pattern across ~35 consumers; the `subagents` module is the durable home.
- **Hold the whole spec until the github re-vendor lands.** Rejected: the non-github map is complete now, and
  `[+github]` is cleanly marked "pending the one hub re-vendor" — no reason to block the map on it.

## fabrik-lib verdict table

| Capability | Verdict | Why |
|---|---|---|
| Parallel subagent runtime, worktrees, scope-check, ledger, `pick_models`, `record_agent_run`, `results_table` | **VENDOR (as-is)** | Exists + verified this session; the map just uses it correctly. |
| `fanout()` helper + serialization guard + quality back-fill | **VENDOR + ENHANCE `subagents`** | Correctness/ergonomics layer at the module's public seam; canonical-owned → fabrik-lib builds, no `UPSTREAM_FEEDBACK` round-trip (propose from here — cross-repo). |
| A new module | **NO** | It's an enhance of an existing module; no `🆕 candidate`. |

## External dependencies

- **`subagents` module** — internal; grounded at `path:line` this session (table above). No external API.
- **OpenRouter** — wrapped by the module (`pick_models`/`run_agents`); prices are the module's **vendored
  fallback** (`select.py:44-61`), not re-verified live here (the synced `CODING_SUBAGENT_SELECTION.md` is
  canonical) — this spec is about dispatch *params*, not price accuracy.
- **GitHub read-only MCP (plan-2)** — canonical code present + **plan-2 `EXECUTED`/archived** (`final_commit:
  b3dc97d`, 2026-07-09). The remaining gate for the `[+github]` rows is the **hub re-vendor** of
  `libs/subagents` (hub copy still lacks `github`) — actionable now, not a blocking unknown. Not blocking the
  non-github map either way.

## Shape / infra implications

None. `subagents` is a vendorable library module, not a deployed service — no scaffold type, no `shape:` flags,
no compose/Traefik/ports. The command/rule files are governance docs.

## Constraints

- **The parallelism rule is the invariant the fleet is missing** — it exists in neither `62` nor any command;
  landing it (update #1) is the core fix, with or without the module helper.
- **Commands are edited in their real home** — command files are user-level (`~/.claude/commands`), `62` +
  `CLAUDE.md` are fabrik-synced (edit in `/opt/fabrik`, re-sync). No fork.
- **The module enhancements are fabrik-lib's to build** (cross-repo) — this spec proposes; it does not write
  `/opt/fabrik-lib`.
- **`[+github]` is documented but inert** until the hub re-vendors `libs/subagents` (plan-2 already EXECUTED).

## Open / blocking unknowns

- **[UNBLOCKED — action pending, github rows only]** plan-2 (`github` read-only) is **`EXECUTED`/archived**
  (`final_commit: b3dc97d`, 2026-07-09); canonical carries the read-only injection + write-verb verify. The
  ONLY remaining step to activate the `[+github]` rows is the **hub re-vendor** of `libs/subagents` (hub copy
  still lacks `github`) — actionable now. Does **not** block the rest of the map.
- **[SELF-SERVICE]** The exact `fanout()` signature/mode names are fabrik-lib's design call — this spec fixes
  the *behavior contract* (parallel-safe defaults, auto-record, results_table), not the bikeshed.
- **[RESOLVED]** Where the helper lives → fabrik-lib enhance (operator's call this session); command/rule
  updates are a fabrik-side follow-up gated on this spec.
