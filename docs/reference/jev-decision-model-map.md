# Jev (TypeSafe's decision model) — use cases mapped onto Fabrik's infra

Researched 2026-10-03 with fabrik-lib's `deep-research` engine (the hub copy in `libs/deep_research`). The pack was a
one-off use-case pack. There were three briefs: deployments, independent evaluations, and agent harnesses. Each brief
ran twice, once with Firecrawl search off by a wiring error (`lg-15`) and once with it on; the legs were Exa, Firecrawl and
Brave, with `claude -p` sonnet as the LLM. That gave 103 evidence cards from 62 distinct source URLs for $0.21 of search
spend. Ten pivotal or doubtful sources were then read directly (`v-01..v-08`, `v-10`, `v-11`). Every fact, with its disposition, is in the research ledger
[2026-10-03-jev-use-cases-ledger.md](research/2026-10-03-jev-use-cases-ledger.md); the ids below (`hr2-12`, `lg-03`, …)
are its rows. The OpenRouter price/latency test of the same day (90 items, four models) is row `t-01`.

**Verdict:** Jev fits Fabrik where today a regex stands in for a semantic judgement on a hot path, or where a human
labels by hand at volume, provided the answer is reversible and a threshold sends the uncertain band elsewhere. It does
not fit anything that is a security boundary, anything that needs reasoning or a written rationale, or many-class
routing. Two hub pilots stand out: the Stop hook's stall detector and the skill router's Tier 2. Both are blocked on
two operator rulings (§ 5): whether hub text may be sent to an external decision API, and through which channel.

## 1. What it is good at (the evidence)

| Class | What the deployments do | Evidence (ledger ids) |
|---|---|---|
| **U1 — Tool-call / permission gating** | Static rules first; Jev scores the commands they don't cover; auto-approve above a threshold, ask the human below it | measured: `hr2-02` (91.7% on 60 risk cases), `hr2-03` (79% of real tool calls are harmless, so a constant "benign" is the baseline to beat) with `v-01` (Jev 93% zero-shot, 95% nine-shot against it; 7 of 9 dangerous calls refused), `hr-03` (Pi: requested 0.77–0.98 vs unrequested 0.06–0.15), `hr-01` (Claude Code hook); integration guides that show the pattern but measure nothing (`hr-02` OpenRouter cookbook, auto-approve above a configured 90%; `hr-17` Vercel eve); `hr2-04` (Brier 0.026 vs GPT-4.1 mini 0.056), `hr2-05` (243 ms vs 1,512 ms median), `ev-09`/`v-03` (Claude Code permission hook, needed threshold tuning; 95% vs Haiku 4.5's 94% and Opus 5.5's 98% on 100 banking queries, 0.38 s median), `hr-05`/`v-06` (30 of 30 pooled across a risk gate, a drift alert and a skill picker in one run by an unaffiliated site — no per-decision breakdown) |
| **U2 — Pre-filter in front of an expensive agent** | Close or route the obvious cases before the LLM agent runs; the agent keeps the rest | `dr-01` (closed 15–33% of alerts at ~98%, "cannot decide outright"), `dr-02..04` (on-call severity, dedup, proactive post; 39% cheaper) |
| **U3 — Routing / intent / skill picking** | Pick a lane, team, skill or model from a fixed list | `hr-07` (skill picker; inside the pooled 30 of 30 of `v-06`), `dr-05` (procurement lanes), `dr-17` (lead/ticket triage), `ev-12` (13 multilingual tasks), `hr-11` (support ticket bundle), `dr-09`/`dr-11` (content triage, catalog selection), `t-01` (our 30/30 on hub mail beats) |
| **U4 — Moderation / abuse / injection / fraud** | One fixed question per risk, at a fixed point | `dr-07` (signup misuse, "five cents a day"), `hr-16` (prompt injection, 791 decisions), `hr-04` (a vendor-tagged research note: 12 guardrails replacing word counting, results not quoted), `ev2-13` (fraud recall 93% vs rules 90% vs LLM 62%), `dr-10` (three guardrails in a video agent) |
| **U5 — Retrieval gating / memory** | Decide whether retrieval should run, which notes to inject, whether two mentions are one entity | `dr2-02` (replaced a cross-encoder: better precision, recall and silence at equal cost; 12,927 labels), `v-04` (direct read: "cost and latency were a wash"), `dr-19` (greeting gate), `dr-06` (entity resolution) |
| **U6 — Judging / eval scoring** | Typed grade instead of LLM-as-judge prose | `hr-13` (variance 92–913× lower than LLM judges), `hr2-13` (consistent across runs, no rationale), `dr2-09` (32× cheaper than sonnet), `ev-17`, `dr-08` (pentest report quality gate), `hr-09` (verifier); **mixed**: `hr-14` (Claude beats it on raw accuracy, Jev wins only with abstention) |
| **U7 — Classification / tagging at scale** | Label a backlog | `dr-12`, `dr-13` (54 accounts right, one 10-item cohort confidently wrong), `dr-14` (16,000 calls vs small LLMs), `ev-08` (91.7% on hard claims), `ev2-08` (lead over Haiku shrank from ~30 to 1.5 points once the evaluation was fixed), `v-10` (beat a small zero-shot encoder on 4- and 72-label sets: 0.91 and 0.87 accuracy), `dr2-13` (arXiv: high zero-shot accuracy on sentiment, topic and intent) |

The pattern that holds across every class: **code builds the candidates and Jev picks** (`dr2-11`, all reports
n≈1). Inside whole agents it rarely raised success. The two most-cited wins are a gate in front of an agent (`dr-01`)
and a reranker swap (`dr2-02`); one team rebuilt an agent's whole decision core around it but published no figures
(`hr2-09`). Community catalogs of shipped uses: `dr2-17`, `dr2-10`. TypeSafe's own headline multiples come from in-house
evals graded against the average of two frontier models (`ev-18`, `dr2-01`, `hr2-01`, `hr-10`), and its 70–500 ms
latency is vendor-reported (`ev-11`); they are named here and not used as evidence. Rows the engine tagged `vendor`
are cited for the pattern only: the integration guides' numbers (OpenRouter, Vercel) are configuration, such as a
chosen threshold, not measurements, and agent.nexus's research note's per-check results are not quoted here.

## 2. What it is bad at — the constraints every use must respect

| # | Constraint | Evidence | Consequence for a design |
|---|---|---|---|
| C1 | **It cannot abstain** — it always picks an option | `hr2-12` (0 of 24 no-answer cases declined), `v-02` (direct read of the same test), `ev-07`/`v-05` (without an abstain option, accuracy 0.95 → 0.00 and ECE 0.79), `dr2-14` (it cannot answer outside the predefined options) | Always offer an explicit `insufficient`/`other` option, and treat the low-confidence band as "fall back" |
| C2 | **Calibration varies by task and by wording** | `ev2-05` (rewording one question moved ECE by 0.071; the middle of a scale was overconfident), `ev-06` (one write-up of a study: ECE 0.18 on its synthetic set against 0.035 on OpenBookQA) and `v-08` (another write-up of the same study: 0.325 on unseen synthetic tickets against 0.024 on OpenBookQA) — the two disagree, and both put the unseen-task figure far above the benchmark one, `v-10` (on 6-way emotion it was worse calibrated than a small encoder, Brier 0.846 vs 0.668), `v-05` (a yes/no question and a two-option choice on the same question differ by 0.125), `ev-08`, `ev-09`/`v-03` (below 0.9 the probabilities were too optimistic), `dr-13`, `dr-16` (the cost claim holds, the speed and calibration claims only partly), `dr-20` ("The hard part was never the model. It was choosing a threshold per decision"), on the other side `ev2-06` (still the best-calibrated of 16 models under one second) | Calibrate the threshold per decision point on our own labelled data. Sweeping the threshold beats tuning the prompt (`v-04`) |
| C3 | **Not a security boundary** | `v-05` (with the question removed it still scores 0.38–0.46), `v-01` (Sonnet's 8 errors were all leaks; Jev's were spread more evenly between false allows and false blocks), `dr2-08`/`v-07` (a production user kept auth, payments, deletions and approvals out of its reach) | Where a wrong allow is irreversible, deterministic rules stay in front and Jev may only tighten. Never let it be the only thing between an agent and an irreversible act; where a wrong allow is reversible, it may loosen only after the § 4 leak measurement |
| C4 | **Accuracy misleads under class skew** | `hr2-03`/`v-01` (79% of real tool calls are harmless; "Overall score does not show whether it fails safely"), `ev2-08` (a keyword search first beat it) | Measure the leak rate (wrong allows) and coverage at the threshold, not accuracy |
| C5 | **It gives no rationale**, so a wrong answer is silent | `hr-19`/`dr-18`, `hr2-13`, `ev-17` | Log the full probability vector, and sample failures to an LLM when you need to know why |
| C6 | **Literal reading**: weak on negation, counting, field names and non-English text | `ev-09`/`v-03`, `hr-19`, `dr2-10` | Do counting and arithmetic in code; test negation explicitly |
| C7 | **Many-class routing**: it drops behind frontier models, and the speed edge reverses at about 77 options | `hr-15` (5 points behind GPT-5.6 Terra on 77-way), `ev2-11` | Keep option lists short (≲25), or split the question into stages |
| C8 | **Hosted only** — every call sends the text to TypeSafe (directly, or via OpenRouter/Vercel) | `t-01` (single provider), `v-11` (the open-weights alternative Laya scored 0.69 against Jev's 0.91 on 1,240 decisions), `ev-14` (re-implementing the mechanism on an open 0.5B model gave only 1.83× over generation) | Data egress is a ruling, not a default (§ 5) |

## 3. The map — our decision points × the evidence

The infra inventory is a read-only sweep of 371 hub files and 72 fabrik-lib files that found 44 closed-answer decision
points (`lg-00`); the 14 rows below (`lg-01..lg-14`) are the ones the evidence bears on. Fit:
**PILOT** = best first candidate · **FIT** = matches a proven class, worth doing after a pilot · **CONDITIONAL** =
only with the named precondition · **NO** = a constraint rules it out.

| Infra decision point | Today | Class | Fit | Why / precondition |
|---|---|---|---|---|
| Stop-hook stall and deferral detection — `.claude/hooks/final_gate_stop.py:1451-1696` (`lg-01`) | regex closed lists; by the hook's own measure, 85% of the deferrals it saw were unjustified (`:1543-1551`) | U1/U4 (`hr2-02`, `v-01`; the pattern in `hr-06`) | **PILOT 1** | Runs once per turn end (Jev p50 0.2–0.5 s fits); a wrong verdict is reversible — a wrong block ends at the cap, a wrong exemption only lets a turn end; and a **labelled set already exists**: `docs/reference/research/2026-09-23-stop-compaction/verdict-*.json`, replayed by `scripts/sysadmin/stop_mine.py`. Regex stays as the first pass; Jev scores its fires in shadow mode, and may clear one only once § 4's leak rate (wrong exemptions) is no worse than the regex's (C3) |
| Skill-router Tier 2 — `.claude/hooks/skill_router.py:20-36, :846, :909` (`lg-02`) | Haiku fallback, **OFF** because cold start was 8.6–10.7 s on every unmatched prompt | U3 (`hr-07`) | **PILOT 2** | A suggestion only, so fully reversible; Jev's latency removes the reason Tier 2 was switched off. `check_trigger_routing.py` measured 45 of 71 advertised phrases routing nowhere, which is a ready eval set. The curated roster is 33 options (31 `STEM_SKILLS` targets plus 2 dynamic), past C7's ≲25: cut it or split the question into two stages before the pilot |
| Command FEEDBACK queues — `scripts/command_run.py:1401-1600`, `scripts/sysadmin/feedback_relay.py` (`lg-03`) | axis fit not judged at all; filing detection by regex; 302 + 285 + 72 unanswered verdicts | U7 | **FIT** (offline batch) | Label each verdict (actionable? which command section? does the axis fit?) and cluster them for `/fabrik-command-improve`. Cents for the whole backlog, no hot path, nothing irreversible |
| Mail beat routing — `scripts/mail.py:975-1010, :1252` (`lg-04`) | the sender picks by hand; 24 of 28 live hub messages were unaddressed before the guard | U3 (`t-01`) | **FIT** | Suggest `--to-agent` when it is omitted; the addressee is a filter, never a lock, so it is reversible. Mail bodies leave the box (C8) |
| Production watchdog / incident triage — `src/fabrik/drivers/watchdog.py:577-590`, `scripts/sysadmin/incident_context.py` (`lg-05`) | LLM sidecar for everything | U2 (`dr-01..04`) | **FIT** — fleet beat | Pre-filter: is this a known incident, how severe, should we page — before the expensive diagnosis runs. The fix decision stays with the LLM (`ev-02`) |
| fabrik-lib `rag/classifier.py` ontology tags; retrieval gating (`lg-06`) | qwen3-8b via OpenRouter, batches of 25 | U5/U7 (`dr2-02`, `dr-19`) | **FIT** — fabrik-lib | A relevance or "should we retrieve at all" gate is the strongest measured win (`dr2-02`, `v-04`) |
| fabrik-lib `competitor-intel` sentiment and source trust — `adapters/hn_algolia.py:83`, `trust.py:70-90` (`lg-07`) | sentiment hard-coded `"neutral"`, which once emptied `beat_list` | U7 | **FIT** — fabrik-lib | A score question per signal fixes a known defect for fractions of a cent per run |
| Product moderation / spam / support intent for the ~46 projects (`lg-08`) | no fabrik-lib module exists | U3/U4 | **FIT** — fabrik-lib | A vendorable "typed decision gate" (threshold + fallback + probability log) would serve every project that routes or moderates user text |
| Review-loop candidate dedup — `.claude/workflows/fabrik-review-loop.js:192-198` (`lg-09`) | same file, same class, ±5 lines | U5 (entity resolution, `dr-06`) | **CONDITIONAL** | Advisory merge only; refutation stays with the orchestrator (C5). A community staged code-review pipeline exists (`dr-21`), unmeasured |
| Plan-quality negated mandates — `scripts/enforcement/check_plan_quality.py:240-295` (`lg-10`) | keyword presence, so "Do NOT run /fabrik-review" passes | U7 | **CONDITIONAL** | Negation is a documented weakness (C6); measure it before trusting it |
| Quota-hold allow-list — `.claude/hooks/quota_stop.py:88-150` (`lg-11`) | regex, with recorded bypasses | U1 | **NO** | A wrong allow is irreversible; C1 and C3 forbid a probabilistic gate here. Fix the regex |
| Mail secret guard — `scripts/mail.py:102-223` (`lg-12`) | regex, fail-closed | U4 | **NO** | A leaked secret syncs fleet-wide; five "is this a placeholder?" classifiers have already leaked |
| Review refutation, research-ledger dispositions, incident fix choice (`lg-13`) | orchestrator / LLM | U6 | **NO** | These need reading and reasoning with a rationale (C5, `ev-02`, `dr2-11`) |
| Model / seat routing — `scripts/kilo-benchmarks/rank_task_subagents.py` (`lg-14`) | declared task_type + formula; the pool is OFF | U3 (`hr-08`) | **NO** (now) | Nothing routes while D-181/D-182 hold |

## 4. How a pilot is run (the same steps for each)

1. **Labelled set from our own data.** Stop: the committed verdict files. Router: the 71 trigger phrases plus real
   prompts. Mail: archived messages with their `to-agent`. Feedback: hand-label 100 rows.
2. **Shadow mode.** Jev runs beside the current mechanism and logs its full probability vector; nothing changes behaviour.
   Harness patterns to copy rather than invent: `ev-13`, `hr-12` (LangGraph node), `hr-18`/`hr2-14` (MCP servers).
3. **Sweep the threshold** per decision point (C2). Report coverage at the threshold and the **leak rate** — wrong allows
   or wrong exemptions — beside the current mechanism's (C4); accuracy alone is not the measure.
4. **Arm only if** the leak rate is no worse than today's, and keep the deterministic first pass (C3). Every question
   carries an explicit `insufficient` option (C1).
5. **Cobra check (D-253):** the cheapest way to "pass" a pilot is to tune the threshold on the same labelled set it is
   scored on, which reports calibration it doesn't have. Hold out a third of each set, and re-score on fresh traffic
   after a week.

Cost is not a constraint. At $0.042 per million input tokens, a 2,000-token Stop-hook call costs $0.00008; ten
thousand turn ends a day would be $0.84. Measured, 90 calls cost $0.00153 in total, $0.000017 each, at a mean of about 400 input tokens per call (`t-01`); a
whole independent calibration study of 4,621 items cost about $0.06 (`ev2-07`), and the list price is the same on every
channel (`dr-15`).

## 5. The two rulings needed before any pilot sends hub text

- **Data egress.** Every pilot sends hub text out of the box to TypeSafe: operator prompts (router), agents' final
  messages (Stop hook), or mail bodies. There is no self-hosted Jev (C8).
- **Channel.** OpenRouter's Decisions API is the provider behind the paused subagent pool (D-181/D-182). A single typed
  call is not a subagent fan-out, but it is metered OpenRouter spend. The alternative is TypeSafe's own API, which is
  early access only.

The fabrik-lib and fleet rows (§ 3) sit on other beats: fabrik-lib owns `rag`, `competitor-intel` and any new module;
fleet owns the watchdog.
