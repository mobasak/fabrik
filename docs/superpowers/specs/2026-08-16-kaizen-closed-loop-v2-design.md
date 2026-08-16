# Kaizen closed-loop v2 — daily self-improving coding infrastructure

Status: DRAFT
Date: 2026-08-16
Author: infra (Claude, /fabrik-spec) — operator: Özgür

## Goal

The operator's vision, verbatim (repeated ≥5 times, 2026-08-16): *"you are the authority of all
command files and coding infrastructure, your goal is to continuously monitor these, update commands
where needed, and present us the fastest, most accurate and correct, rules-obeyed coding
infrastructure."* Cadence requirement: **daily, not weekly.**

One operator runs ~46 projects through 10–12 concurrent AI agents (8 VS Code windows on a normal
day). They cannot review each agent's output; the only thing that scales is the machinery that makes
agents correct by default — the 203 governance artifacts this repo owns (27 command sources + 13
fragments, 56 rule packs, 57 gate checks, 5 hooks, 12 scaffold types, 12 fleet-synced core scripts,
21 crons). This spec designs the **closed loop** over that machinery: observe how agents actually
behave fleet-wide → find where they are slow, wrong, or rule-breaking → change the infrastructure →
prove the change helped — with autonomy **earned in stages**, never assumed.

**DONE WHEN** (for the system this spec designs; each milestone has its own gate in § Sequencing):
a daily cycle runs unattended that (a) measures agent behaviour from a typed event stream with
versioned, recomputable definitions, (b) validates candidate infrastructure changes by replay or
cohort exposure, (c) files or promotes changes under the safety regime of § Layer 3, and (d) reports
one terse daily verdict the operator can read in under a minute.

## Why v1 failed (the grounding for everything below)

- `kaizen_metrics.py` (shipped days before) read **one directory** — this repo's own review ledgers
  (grep `/opt/` in it: zero hits). It produced one row with 5 of 8 columns `—`, while 5,317 session
  transcripts (8.2 GB, 98 project dirs, ~91 sessions/day), a 3,292-row subagent ledger, and 237
  fleet review ledgers sat unread.
- `kaizen_collect.py` (shipped 2026-08-16, commits 29dc51b7 + e4ed9959) now reads the real record —
  and its first run produced **two instrument bugs** (100% failure rate from a wrong status
  vocabulary; a 1440-round ledger from a naive table regex) plus one confounded metric (the
  compliance denominator counts ~36 final blocks/session against a once-per-run contract).
- The v1 **actor** design ("fix daily, judge by next-day fleet mean, verify with the gate") was
  reviewed by 12 independent frontier models on one identical brief
  (`docs/archive/2026-08-16-kaizen-consultation-raw.md`, $2.40, 2026-08-16). Unanimous verdict:
  **keep the epistemics, do not ship the actor** — it would revert good fixes on noise and validate
  itself with a gate it is allowed to weaken.

## Chosen approach — three layers, autonomy earned per milestone

### Layer 1 — Measure truthfully

**Typed append-only event stream at the source.** The hooks and `command_run.py` — code that already
runs at every session boundary — emit one-line JSON events (`session_start`, `run_open`, `phase`,
`round`, `run_close`, `gate_run`, `stop_block`, `final_block_emitted`, `death`, `revival`) to
`~/.claude/state/events/YYYY-MM-DD.jsonl`. Transcripts become *forensics*; the meter reads events.
Rationale: every metric defect found on 2026-08-16 (denominator conflation, mtime selection,
prose-parsing artifacts) is a parsing artifact of treating prose as data (gpt-5.6-luna-pro's
highest-leverage item, endorsed by the fusion synthesis). Emission is **fail-open and
zero-dependency** (append to a local file; never a DB, never blocking — a broken emitter must never
break a session).

**Versioned definitions + backward recompute** (operator's own design, 2026-08-16, replacing the
panel's "freeze the collector"): every metric definition carries a version; every published number
carries its definition hash; a definition change triggers recompute of the **entire history** under
old + new with the divergence shown. Tampering becomes *undeniable* rather than *prevented*, and
fixing real collector bugs stays legal. The immutable substrate already exists: transcripts + event
files are append-only.

**Every event carries exposure metadata** (the near-unanimous attribution prerequisite —
qwen3.8-2.4t's mandatory-exposure list, grok's session pin, kimi's model-rotation covariate,
opus-5's governance_schema_version): hub commit, rendered-command + rulepack hash, model, account,
plan era, project. Three accounts rotating every ~2 days means the model mix changes intrinsically
through the week; unstamped, that drift gets attributed to whatever merged that day.

**The collector proves itself before its numbers are believed** (all 12, distilled): every parsing
predicate ships a checked-in fixture that must evaluate BOTH ways (grok: "you already paid for this
lesson at 100% and at 1440"), plus a golden corpus of hand-labelled transcripts whose expected
counts are asserted daily before any number is consumed. Instrument health is metric zero — red
instrument ⇒ no actor dispatch (qwen3.8-max's preflight).

**Backfill the noise floor** (opus-5, stated as a prerequisite): recompute the versioned metrics
over the full 8.2 GB historical corpus to establish per-metric variance BEFORE any adjudication —
"you cannot detect a change you cannot distinguish from Tuesday." The recompute machinery (above)
is exactly what makes this possible.

**The confounded compliance metric splits into two**: `rules_compliance` (task-completing responses
opening with RULES ACTIVE) and `terminator_spam` (final blocks emitted per run over the once-per-run
contract) — the second is itself a defect signal, currently hidden inside the first.

### Layer 2 — Decide correctly

**The decidable rule: if the outcome is computable without calling a model, replay it; otherwise
cohort it.**

- **Replay (authoritative, $0):** deterministic changes — gate predicates, parsers, globs, renderers,
  denominators — run against stored transcripts/events. Identical inputs ⇒ a delta is caused by the
  change. Proven in-session: the corpus check was validated red-on-revert against the real historical
  defect this way.
- **Split-fleet cohorts ($0):** behavioural changes — command wording, rule text — cannot replay
  (recorded responses can't react to changed prompts). ~46 projects and ~91 sessions/day give free
  exposure; changes land in a cohort first, compared against the rest.
- **Adjudicate on exposure count, not the calendar** (gemini's event-volume rule, sonnet-5's
  exposure-count window, qwen3.8-2.4t's minimum-exposure metadata — independently derived):
  re-measure once N sessions have *touched the changed surface*; a Tuesday Python-rule fix is not
  falsified by a Wednesday of CSS work. **"Underpowered — parked" is a legal, non-punitive verdict.**
  fable-5's variant is adopted alongside, not merged in: *deterministic proof at merge time*
  ("demonstrate the defect against the old code, its absence against the new") for mechanical fixes,
  with fleet numbers demoted to portfolio-level trend over 7–14-day windows — a proven-by-construction
  fix is never re-attempted just because a noisy metric sat still (his named failure: "the
  retry-with-diff-attached mechanism converts measurement noise into governance escalation").
  **Long-arc re-adjudication** (minimax-m3): confirmed fixes are re-measured at day 14 and day 30;
  an effect that evaporated (agents found workarounds) is reverted — day-2 wins are provisional.
  In-house proof that blended means hide effects: mixed-era review rounds = 4.8; ticket-era = 3.2.
- **Generation is decoupled from promotion** (fusion synthesis resolution): generating and
  falsifying candidates is cheap and zero-blast-radius — do many; *enforcing* changes promote at
  most one per off-peak window. One hypothesis ≠ one file hunk — a coherent fix ships whole.
- **A persistent finding registry + a tested selection policy** — fable-5: *"the selection policy is
  the actual product, and it's unspecified"*; o3-pro's backlog-explosion warning (>1,000 rotting
  findings at 60 days); gpt-5.6's registry schema. Findings are durable, deduplicated objects
  (first-seen, severity, confidence, blast radius, attempt history, expiry) ranked by expected value
  — frequency × harm × confidence ÷ (cost × blast radius) — with per-surface caps so one noisy
  metric cannot monopolize the actor, and aging so stale findings re-validate before dispatch. The
  policy is CODE WITH TESTS (given a fixture findings-table, which is picked?). Three verdicts every
  consultant demanded are first-class, non-failure outcomes: **"no safe valuable action today"**
  (kimi: a loop that cannot say no will eventually eat the platform), **"not fixable by
  infrastructure"** (sonnet-5: some low-compliance is task difficulty, and forcing a daily commit
  is how rules accrete cruft), and **"wrong control surface — project-local, not hub"** (grok: the
  7–73% compliance spread is likelier scaffold/override misfit than a missing hub sentence).
- **A fix ledger with refutation memory** (kimi: "the crown jewel … currently planned as a side
  effect"; opus-5: "no memory of refutation"): every hypothesis, pre-registration, verdict, failed
  diff and revert in one append-only, off-box-backed ledger; the selection policy consults the
  refuted-hypothesis index so the loop cannot re-propose next month what failed last month with a
  cosmetically different diff. Failure classification (noise vs. bad patch vs. wrong hypothesis) is
  required before any retry.
- **A deterministic fix tier below the LLM** (minimax-m3, adopted by fusion w2): regex corrections,
  renames, log-point additions are applied by deterministic tooling with a unit test as the
  verifier — `sed` plus pytest, zero model calls. The fable-5 dispatch is reserved for changes whose
  source of truth is an instruction requiring interpretation. Quota goes only where judgement is
  genuinely needed.

### Layer 3 — Change safely

- **Staged promotion, never instant 46-repo sync**: shadow (non-enforcing `would_have_blocked`
  logging inside gate runs that happen anyway — Grok's near-free variant; qwen's dual-execution
  shadow is **rejected**, it violates the cost ceiling) → hub-only canary → fleet, with the
  governance-sync as the final leg, not the first.
- **Session-pinned law** (grok-4.6): the rendered command + rulepack hash is pinned at SessionStart;
  a mid-day promotion never rewrites the rules under a live run.
- **Net-zero governance budget** (kimi-k3): total token count of the synced governance surfaces is a
  guardrail metric; a change that grows it must name what it retires. Deletion is legal **only
  evidence-backed** ("pack never activated in 60d across N sessions" — measurable from the event
  stream), never convenience-driven — sonnet-5's counter ("deletion is the cheapest way to make an
  inconvenient check vanish") means any diff shrinking a gate check or rule pack escalates to the
  operator even when green.
- **`vacuous_check_rate` as a permanent guardrail** (minimax-m3, best single idea of the 12): per
  gate check, the fraction of recent runs where any branch *could have failed*; zero ⇒ the check
  asserts nothing. Computed by a replay/mutation harness run **weekly** (minimax's own cost guidance
  — it is a heavy check), paired with per-check known-bad fixtures that must FAIL continuously
  (the near-unanimous "seeded-defect / Vault-of-Shame" mechanism: gpt-5.6, grok, gemini, opus-5,
  fable-5, both qwens); the 6 vacuous checks found manually this week become the seed set, and the
  assertion-surface count may never shrink.
- **The actor never switches the number it is judged on**: collector/definition changes are
  human-authored, with dual-run old/new before any switch. The actor's write-allow-list excludes
  `kaizen_*`, the event emitters, and the enforcement of this spec — checked in the promotion path,
  not by file permissions.
- **The dossier is a privilege-escalation channel and is treated as one** (kimi-k3; independently
  gpt-5.6, opus-5, fable-5, qwen3.8-max): transcript excerpts quoted as evidence contain arbitrary
  third-party text — web content, tool output — which must never reach the fixer in instruction
  position. Evidence is fenced as untrusted data with hard delimiters; the fixer prompt is assembled
  from templates; imperative-looking content in evidence is a flag, not a command.
- **Kill switch + external deadman** (qwen3.8-max's `KAIZEN_FREEZE`; opus-5's silent-death proof —
  the hourly CI fixer dispatched zero times today and nobody noticed): the loop checks a freeze file
  before every action, and a watchdog OUTSIDE the loop's process tree alerts when no completed cycle
  has been recorded in 48h. Silence must be an alarm, not an absence of one.
- **Sync-skew / propagation fidelity as a metric** (grok; minimax-m3): of the last 30 days'
  governance changes, how many arrived at all ~46 repos within the expected window — a `git` query
  per repo per day. A "fleet improvement" measured while only some projects received the change is
  the attribution killer nobody watches for.
- Tier-D precedent inherited (`60-watchdog.md`): isolated worktree (never the shared tree —
  `ci_fix_dispatcher`'s dirty-tree skip produced **0 dispatches** on 2026-08-16 with 10 failures
  pending; worktrees are why this actor will actually run), tests-pass hard gate, secret-scan on
  every proposed diff, every verdict emits a counter + structured line (`self-healing.md`), full
  audit trail in the event stream.

## Sequencing — autonomy is earned (M-gates)

| M | Delivers | Autonomy | Gate to next |
|---|---|---|---|
| **M1** | Event emitters in hooks + `command_run.py` (with exposure metadata); split compliance metrics; versioned definitions + recompute harness; collector predicate fixtures + golden corpus; noise-floor backfill over the historical corpus; daily collector cron replaces weekly | none (measurement only) | 7 days of events; recompute reproduces history; denominators verified against hand-counted samples; per-metric variance established |
| **M2** | Replay harness over stored transcripts/events; `vacuous_check_rate` (weekly harness) + per-check known-bad fixtures + assertion-surface floor; finding registry + tested selection policy | none (analysis only) | replay red-on-revert proven on ≥3 historical defects; every blocking check owns a fixture that FAILS; selection policy passes its fixture tests |
| **M3** | Propose-only shadow actor: daily headless dispatch (`claude --model claude-fable-5 --fallback-model claude-opus-5 --dangerously-skip-permissions -p <dossier>` in a fresh worktree) that files evidence dossiers + candidate diffs it **cannot promote**; independent verification (the orchestrator re-runs gate + corpus check + tests itself — a session's "fixed" claim is never trusted); ai-consult panel critique on request | proposes only | ≥10 dossiers; operator spot-audit finds no fabricated evidence; false-positive rate visible |
| **M4** | Promotion rights under Layer 3 in full: one enforcing change per off-peak window, exposure-count adjudication, staged rollout, net-zero budget | **operator gate — explicit approval required to enter** | ongoing: any guardrail regression auto-parks the loop |

## Rejected alternatives

1. **Actor v1** (fix daily → judge by next-day fleet mean → verify with `final_gate.py`) — rejected
   by the full panel (both fusion syntheses; even the friendliest reviews — o3-pro's "directionally
   correct", kimi-k3's "shape fundamentally sound" — condition it on the same instruments-first
   prerequisites): next-day fleet-mean adjudication is causally empty (in-house proof: 4.8 vs
   3.2); "the number moved" both false-negatives good rare-path fixes and false-positives noise; the
   gate cannot verify changes to the gate (6 checks passed while asserting nothing, found
   2026-08-16); instant sync is a ~46-repo blast radius.
2. **Full statistical platform** (o3-pro: 2³ strata × 20% holdout × paired t-tests; qwen wave-1:
   dual-execution shadow at 2–3× compute) — rejected: not credible at n=46 non-exchangeable projects
   (compliance spread 7–73%); dual execution violates the hard $0-new-spend ceiling. Cohorts serve
   as bias control with effect sizes, not significance theatre.
3. **Freeze/chmod the collector** (o3-pro) — rejected in favour of the operator's
   recompute-over-immutable-history design: the collector has known bugs and must remain fixable;
   filesystem permissions don't bind a promoted diff anyway; the control belongs in the promotion
   path + dual-run.

## External dependencies (all grounded THIS session, 2026-08-16 — live probes, not memory)

| Dependency | Grounded fact | Source + date |
|---|---|---|
| `claude` CLI model pinning | `--model claude-fable-5` and explicit `--model claude-opus-5` verified live (headless probe returned exact IDs); `--fallback-model` accepts a comma-separated list. ⚠️ Aliases (`opus`) resolve to the *latest stable* line (4.8), NOT Opus 5 — **full IDs only** | live CLI probes, this box, 2026-08-16 |
| Headless context inheritance | a `claude -p` session on this box inherits CLAUDE.md, MEMORY.md index, fabrik-mail digest, and a **working session-recall MCP** (probe returned `{"claude_md":true,"memory_index":true,"session_recall":true,"mail":true,"recap":true}`) | live headless probe, 2026-08-16 |
| OpenRouter model IDs (consult panel) | frontier set live-verified: `qwen/qwen3.8-max`, `moonshotai/kimi-k3`, `minimax/minimax-m3`, `openai/gpt-5.6-luna-pro`, `x-ai/grok-4.6`, `google/gemini-3.1-pro-preview`. ⚠️ naive prefix match fails (`gemini-3-pro` hits image-only variants); stale point-releases flatter (qwen3-max-thinking vs 3.8-max, measured) | live `/api/v1/models` probes, 2026-08-16; request for a live-resolved FRONTIER preset filed to fabrik-lib (mail `01M05V82ZQ540R8RK52F5H3QNG`) |
| ai-consult module | `panel(question, models=[...])` returns per-model answers + fusion synthesis; SSE liveness, restart-on-stuck, no blind timeout — proven on a 1,122s wave with zero cutoffs; 12 consults = $2.40 | module source + live runs, 2026-08-16 |
| Session transcripts | `~/.claude/projects/<dir>/*.jsonl`, rows carry `cwd`/`gitBranch`/`timestamp`/typed `type`; 5,317 files / 8.2 GB / 98 dirs; ~91 touched per active day | live filesystem census, 2026-08-16 |
| Resume mesh | mid-stream deaths (5 named classes) detected + death-recorded + Telegrammed in 2s; revival requires an armed waker — self-watch arming now in ORIENT (commit 20a28cbc) | live incident + `docs/workstation/hooks-index.md`, 2026-08-16 |
| 12-consultant design review | the approach-space grounding for this spec (per the invocation's research-gate ruling: consultation = the external base; only CLI flags + model IDs needed live re-verification, done above). **All 12 answers + both fusion syntheses read IN FULL during /fabrik-spec-review convergence** — every attribution in this spec verified against the raw text; missed mechanisms folded in (finding registry, fix-ledger memory, long-arc adjudication, deadman, injection fencing, deterministic tier, noise-floor backfill) | `docs/archive/2026-08-16-kaizen-consultation-raw.md`, 2026-08-16 |

## fabrik-lib verdict table

| Capability | Verdict | Module / why |
|---|---|---|
| Frontier design-critique panel (M3 actor's critic; future spec reviews) | **VENDOR** | `ai-consult` — proven live today; vendor into `libs/` at M3 (currently imported from `/opt/fabrik-lib` path, acceptable for consults run hub-side) |
| Pool fan-out + flywheel | VENDOR (already vendored) | `libs/subagents` |
| Alerting (daily verdict → Telegram leg) | VENDOR (already vendored) | `libs/alerting` |
| Metered-spend caps (OR consult budget) | VENDOR (already vendored) | `libs/cost_budget.py` — caps the *metered* lane only; per operator ruling 2026-06 the subscription-billed Claude lane is never per-call capped |
| Event emitter (hooks + command_run) | **BUILD** | must be fail-open, zero-dependency, append-only local file — `app-audit-log` is DB-coupled at the wrong seam (a hook must never block on postgres). Not yet a fabrik-lib candidate: coupled to this box's hook surface; revisit once stable |
| Replay harness / metric registry / recompute | **BUILD** | nothing in the module table covers replay-over-transcripts or versioned-metric recompute; project-local by design (they ARE the hub's meter) |

## Shape / infra implications

- **No scaffold type, no service, no deploy** — box-local scripts + crons in the hub repo (same
  class as `kaizen_metrics.py` / `liveness_audit.py`). No `specs/services/*.yaml`, no `shape:` flags.
- New crons (M1: daily collector; M3: daily actor dispatch, off-peak) → `docs/RESILIENCE.md` §7 is
  the canonical jobs inventory (Doc Sync Matrix) + `docs/workstation/wsl-startup-inventory.md` §C.
- New subsystem docs at each milestone (`docs/workstation/kaizen.md` evolves; event stream + replay
  get reference docs); INDEX rows per the allowlist.
- Logs: cron-redirected stdout (`55-observability.md` — the tool writes stdout; the environment
  routes). Event files are **data**, not logs.
- Tests: `uv run pytest`, watched-fail-first per `45-testing-strategy.md`; the replay harness's own
  correctness is proven red-on-revert against the three historical instrument bugs it must catch.

## Constraints (binding)

- **$0 new spend.** Ceiling is the existing 8× Claude Max ($800/mo) + $50–100 OR. Shadow =
  non-enforcing logging only; replay + cohorts are free by construction; consult panels are
  occasional and metered (~$2.40/12 opinions), inside the existing OR budget.
- **Quota is the binding resource**: one fable-5 dispatch/day ≈ 1–2% of normal daily burn; actor
  runs off-peak; diagnosis/ranking/dossier-building is deterministic Python at $0.
- **Shared tree** (3 concurrent hub sessions): actor works in fresh worktrees; explicit pathspecs;
  never touches sibling WIP; transactional merge (lease → rebase → full battery re-run → else abort).
- **Write-allow-list enforced in the promotion path**; hard denies: credentials, `~/.claude-fleet`,
  crontab (M1–M3; M4 cron changes are operator-applied), `~/.claude/bin/claude-sound.sh` (untouchable,
  standing order), any repo other than `/opt/fabrik` (cross-repo = mail, never edits).
- No login automation; no direct HTTP token refresh.
- LLM gateway for metered calls = OpenRouter only (`1b-bis`); the actor's coding lane is Claude Code
  subscription OAuth (operator's standing stack ruling).
- Governance edits remain subject to every existing gate (42 blocking checks incl.
  `check_command_corpus.py`) *plus* this spec's Layer-3 additions.

## Open / blocking unknowns

| # | Unknown | Status | Resolution step |
|---|---|---|---|
| 1 | Do hooks fire reliably enough in ALL session types (headless `-p`, compact-resume, subagents) to make the event stream complete? | open, non-blocking for M1 | M1 measures its own coverage: events-per-session vs transcript census daily; gaps become M1 findings before any M2+ decision trusts the stream |
| 2 | Exposure-count threshold N per surface class | open by design | derived from M1–M2 measured traffic (per-surface activation rates), not guessed now |
| 3 | Off-peak window for the actor (operator's working hours vary) | open, operator input at M3 | one-line question at M3 kickoff; default 05:00–06:00 (before the 06:xx cron train) |
| 4 | Stop-hook mid-stream blind spot: a turn that dies mid-stream closes no run record and the Stop hook never fires (observed live 2026-08-16; mesh caught it, revival required the now-mandated armed self-watch) | mitigated, watch | M1's `death`/`revival` events make the residual rate measurable; revisit if >0 unrevived deaths/week |

| 5 | Run records + Stop hook in a WORKTREE may key to the wrong tree (kimi's implementation check) — a fixer that cannot close its own record spins until quota dies | open, blocks M3 dispatch | verify the exact keying path before the first real dispatch; fail closed |
| 6 | Should the first act be SHRINKING the surface? (fusion w2's closing addition: "spend a day asking whether 203 artifacts and 57 checks should become 60 and 20") — deletion findings are the cheapest fix class and shrink every later phase | open, operator conversation | M1's activation/usage data makes it answerable with evidence instead of taste; deletion-candidate report is an M2 deliverable |
| 7 | The loop's own stopping/EV condition (fusion w2 blind spot: nobody defines when the loop is good enough to slow down, or proves it pays for its quota) | open by design | pre-register the loop's own success test at M3: quota spent vs. accepted improvements, reviewed monthly; a loop that cannot pay for itself gets demoted to weekly |

*(Deliberately NOT written: "zero unknowns". The list above is the honest state.)*

## Out of scope

- VPS/fleet state, deploy docs, container health (fleet's beat).
- Editing peer repos (mail only; the fabrik-lib FRONTIER-preset request is already filed).
- Replacing `kaizen_metrics.py`'s honesty rules — inherited verbatim (a metric that can't be
  measured prints `—` + reason; never 0-for-no-data; never a number it didn't compute).
- The epic/ticket orchestrator route — this is feature-scale: each milestone is one operator-carried
  plan (`/fabrik-plan-after-chat` per milestone, M1 first).
