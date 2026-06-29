# Plan — Fabrik Empire Operating Model (one-operator, AI-managed) — v3 (velocity-first)

**Status:** v4 — **FINAL consult absorbed** (3 fusion tiers, unanimous **REVISE→GO-after-fixes**). v4 inserts the missing **brake** (§3c): the supply side (`fabrik launch`) + safety doctrine are good, but the plan created faster than it could **select / contain / maintain**. Three cheap pre-Phase-2 fixes added: **selection-validity** (`untested` state + min-exposure gate + verified-paid-conversion as the sole graduate metric), an **attention control plane** (launch backpressure), and **radical simplification** (18 scaffolds → 1 on Day 1). Effort re-baselined 2.5×. Track B right-sized to **B1-first** (index), the rest deferred. Two-pillar (§0); survival a cheap floor gated behind traction.
**Date:** 2026-06-29
**Owner:** Operator + Fabrik AI (hub control plane)
**Provenance:** `openrouter/fusion` (Opus/GPT/Gemini-Pro panel + budget/fast Gemini-Flash/DeepSeek/Kimi panels, Opus-4.8 judge; ~$2.4 total; raw in scratchpad `fusion_out2/3.txt`, `out_high/budget/fast.txt`).

---

## 0. What we're trying to achieve (TWO objectives)

**Objective 1 — The Factory.** One operator + AI ships many *monetizable* projects at near-zero marginal operator-attention; a few hit; the *portfolio* compounds toward a $1B valuation over 2–5 years. Fabrik (the infra) is the factory, not the product. **KPI: per-project marginal operator-attention → 0** — launching project #50 must cost no more human time than #5.

**Objective 2 — Agent Enablement (the enabler of Objective 1).** Any AI agent entering Fabrik — Claude Code, Kilo, Cascade, Traycer, or a fresh session — must, with **zero human onboarding**: **KNOW** its capabilities, infra, and rules, and **ACT** on them through ready entry points. **KPI: time-to-productive for a cold agent → minutes, from a single self-describing source.** *(Today this fails — a new agent knows almost nothing without the operator re-explaining, and even this assistant kept missing developed items. That gap directly caps Objective 1: a factory "run by AI" only reaches near-zero* operator-*attention if the agents can self-orient and self-actuate without the human re-teaching them each time.)*

The two are one system: **Objective 2 is the substrate; Objective 1 is what it produces.** Everything is judged by *"does this let an agent ship/test/kill/grow a project without adding human load — including the load of orienting the agent itself?"*

Two honest boundaries up front (§9): **velocity is necessary, not sufficient — distribution is the real unsolved bottleneck**; and **we do not monetize the factory itself** (§2).

## 1. The v2→v3 pivot (why velocity-first)

Three independent fusion panels, unanimous: **v2 was "a survival plan in a velocity costume — armor-plating an empty truck."** ~85–95% of effort hardened existing zero-revenue experiments; ~0 reduced the cost of *creating/monetizing* a project — the actual KPI. The fix:

- **Build the conveyor before the armor.** `fabrik launch` (the velocity engine) is Phase 1.
- **Billing/auth/landing/analytics is NOT "the business layer" — it is the velocity substrate.** Scoping it out was the fatal error; a project that can't take a dollar or emit a metric on day one can't prove or disprove itself. Re-inserted as core factory infra.
- **Survival is gated behind traction.** Expensive survival infra (recovery gauntlet, model-pinning, drift index, hash-chain ledger) applies ONLY to graduated/Tier-1 projects. Experiments get a cheap floor (spend kill-switch + backups + restore smoke test) and nothing more. Applying survival infra to all 38→500 projects makes marginal attention scale *up*, not toward zero.
- **Cattle, not pets:** zero-traction projects are auto-killed; winners auto-graduate into the heavy infra.

## 2. Is Fabrik itself monetizable? (asked 2026-06-29)

**Don't sell the factory — it's a trap and anti-thesis. But its byproducts are the distribution flywheel we're missing.**

- **Fabrik as a PaaS / AI-managed IDP:** credible ("Heroku for solo founders, with AI self-heal") but the market is crowded (Coolify/Railway/Render/Fly/Vercel/Dokku), margins thin, and a *multi-tenant* AI agent holding `docker.sock` on **customers'** infra is a support + lethal-trifecta-security + SLA burden — it consumes the exact operator-attention this whole plan protects. It competes with the portfolio for your time. **Reject as a primary play.**
- **The aligned play — Fabrik's exhaust as a distribution engine (not a product):** the panel's sharpest point is that **distribution, not shipping, is the bottleneck.** Fabrik's byproducts are unusually good *audience* assets: the **AI Models Browser** (live cross-provider pricing/quality — useful, low-maintenance, SEO/dev-audience magnet), **fabrik-lib (47 modules) + the scaffolds** (open-source → credibility + inbound), and the **build-in-public "one-person AI-managed empire" narrative** itself. Open them → build the developer/founder audience every portfolio project then launches *into*. This monetizes Fabrik *indirectly and on-thesis*: it attacks distribution instead of competing with the portfolio.
- **Defer-but-watch:** if any byproduct shows real pull, it *graduates into a portfolio project* under the same `fabrik launch` + graduation gate as everything else — dogfooding the factory on itself. Don't pre-build; let traction pull.

## 3. Keystone — `fabrik launch <idea-spec>`

One command: **idea → repo (from the canonical monetizable scaffold) + deploy + DNS + DB/Redis + commercial-kit (auth · Stripe-or-waitlist · landing · `/pricing` · `/checkout` · legal stubs) + analytics funnel (page_view→signup→payment→retention_d7) + watchdog sidecar + control-plane registration + a traction beacon.** Target: **≤30 min operator time, ≤5 manual steps, ≤2h idea→live monetizable URL, 100% monetization+analytics coverage.** This is the only thing that literally makes #50 = #5 in operator-cost. It's *integration* of what already exists (18 scaffolds, 47 lib modules, 27 drivers, 11 registrars), not invention.

## 3b. Pillar B — Agent Enablement (the agents that run the factory)

Two layers, both required (the operator asked to address agents AND skills/orchestrator/workflows — these are the ACT and KNOW halves):

**KNOW — one self-describing source a cold agent reads first.** Today the knowledge is real but scattered (CLAUDE.md auto-loads; AGENTS.md is the map; 49 rule-packs glob-activate; `select_rules.py`; MEMORY) and incomplete (no single index → agents miss capabilities). Deliverables:
- **Generated capability index** (`docs/CAPABILITIES.md` + a JSON the router reads) — introspects `fabrik --help` (29 cmds + subcmds), `drivers/`, `scripts/`, `templates/`, `specs/`, the fabrik-lib README, and live `docker ps`; emits one **INTENT → capability + source-path** map. **Generated, never hand-curated** (hand-curation is exactly how the operator + this assistant kept missing items); regenerated by the daily pipeline so it can't rot. *(This is Doctrine 0 made real — and the lean version fusion endorsed: an index that is an OUTPUT of the live system, not a maintained artifact.)*
- **One-hop orientation path:** CLAUDE.md/AGENTS.md → the index → the right skill. A cold agent's first action resolves "what can I do here?" in one read.

**ACT — ready entry points, not raw capability.** Today `.claude/` has **zero** skills, agents, or slash-commands; the 11 `.windsurf/workflows/` are Cascade-only. So a Claude Code agent has no task-oriented entry points into Fabrik at all. Deliverables (lean — net-deletion-gated like everything else):
- **Skills** (`.claude/skills/`) for the repeatable workflows — port the high-value `.windsurf/workflows` (deploy, registrar-audit, scaffold, launch, enable-watchdog). Discoverable + invokable; Claude auto-suggests them by intent.
- **A small set of domain subagents** (`.claude/agents/`) for heavy isolated sweeps — `fleet-auditor`, `deploy-readiness`, `launch` — NOT one-per-command (that just moves the recall problem).
- **The orchestrator/router** = intent → (index lookup) → skill/command/subagent. This is the "route by intent" mechanism; built on the index, not a new framework.
- **`ai-consult` (fabrik-lib module) — the decide-hard-things / self-correct capability.** A robust frontier-AI consult client (OpenRouter `openrouter/fusion` panel + adversarial `verify`; streamed, durable, cost-bounded — SPEC ready in scratchpad `ai-consult-SPEC.md`). Agents *and* the operator call it for high-blast-radius design/architecture decisions and self-verification (*this plan itself was built by 3 fusion consults through it; it caught two keystone errors no single pass would have*). Vendored, env-driven, no fabrik coupling. This is what makes Doctrine 9 (self-correct) and "spend-compute-to-save-attention" real for *judgment*, not just code.

**Why this is co-equal, not a nice-to-have:** every project the factory ships is built/operated by agents. If onboarding an agent costs operator time, that cost rides on *every* project and the per-project-attention KPI never reaches zero. Agent-enablement is the multiplier on the whole factory. It is also self-reinforcing: `fabrik launch` becomes a skill; the watchdog/sysadmin read the same index; a new project auto-registers into the index — the factory documents itself as it grows.

**Cross-agent reality:** Fabrik runs 3+ agent runtimes (Claude Code, Kilo, Cascade/Windsurf, Traycer). The KNOW source must be runtime-neutral (the index + AGENTS.md, which all read); the ACT entry points are per-runtime (`.claude/skills` for Claude Code; `.windsurf/workflows` for Cascade; `AGENTS-compact.md` for Kilo) but generated from the same index so they don't drift.

## 3c. THE BRAKE — selection validity + attention budget (v4: the fatal omission all 3 final panels found)

The factory creates faster than it can **select**, **contain**, or **maintain**. Three cheap primitives, all **before Phase 2 ships** — without them `fabrik launch` is a sprawl multiplier, not a factory:

1. **Selection validity (~1d) — so kill/graduate data means something.** With distribution unsolved, ~100% of launches hit the kill gate for the *same* reason (no traffic), so a kill teaches nothing and the factory becomes "a random number generator that deletes its own outputs." Fix: add a 4th lifecycle state **`untested`**; **minimum-exposure gate** — no verdict until ≥N *qualified* (bot- and self-excluded) sessions, below which status = `untested` (a *distribution* failure, logged separately, NOT a product signal); **verified paid conversion (cleared Stripe webhook) is the SOLE graduate metric** — visitors/signups demoted to diagnostic (they trip on your own QA, watchdog curls, and crawlers); bot/self exclusion at the beacon (~10 lines).
2. **Attention control plane (~1d) — the brake the accelerator lacked.** Auto-kill exists for *revenue* failure but not *attention* failure; exception load (100 projects × 5%/day × 15 min = 75 min/day; 500 = 375 min/day) silently inverts the KPI. Fix: every operator touch → `attention_events`; `fabrik launch` calls **`launch-gate check` FIRST** → BLOCK if trailing-7d operator-minutes > 5h OR unresolved P1/P2 > 0 OR kill-candidates await veto. Hard caps: ≤15 min/Tier-0/month, ≤20 active Tier-0, ≤2 launches/week until measured exception rate proves lower. Also: a Tier-0 project consuming >120 human-min/30d with <$300 MRR auto-kills.
3. **Radical simplification (Day 1) — kill maintenance-debt at the root.** 18 scaffolds + 27 drivers + 47 modules is unmaintainable solo; by Month 3 `fabrik launch` rots into dependency errors and you become a janitor. Collapse to **ONE canonical monetizable scaffold** + one default driver/registrar/DB path; AI watchdog self-heal is **deferred** behind deterministic healthchecks (restart/rollback/mark-degraded) — AI-self-heal-in-prod invents its own incidents.

## 4. Doctrine (binding — the full operating doctrine, velocity-lensed)

1. **Every line judged by the KPI** — *"does this let an agent ship/test/kill/grow a project (or orient itself) with less operator-attention?"* If it only reduces variance it's survival, and survival is **capped at what protects graduated projects**, not experiments.
2. **Monetizable by default** — no project launches without auth + a payment-or-waitlist path + an analytics funnel. Unmeasurable/unpayable = noise.
3. **Cattle, not pets** — auto-kill zero-traction; auto-graduate winners; attention routed strictly by traction.
4. **Self-describing system (Doctrine 0)** — capabilities/infra/rules are GENERATED from the live system into one index, **never memorized or hand-curated** (that's exactly how items get missed); reuse + routing resolve against the index, not recall; stale → regenerate.
5. **Reuse before build → route by intent** — first action on any task: search the index / fabrik-lib / drivers; name what you reused or prove it's absent. If the right entry point is missing, **create the entry point** (skill/command/index-row), not a one-off. Advisory grep, not blocking. **Net-deletion gate:** every phase deletes/merges ≥1 module.
6. **Unrecorded manual step = defect** — a hand-done prod-impacting step (deploy/secret/restart/fix) is a bug: wire it so an agent does it next time, or file the gap. (Deliberate human risk-gates §8 are *not* defects.)
7. **Self-heal is a defect signal** — failures route to watchdog/sysadmin (detect→diagnose→fix→test→verify→rollback), not the operator; alert on *rising* heal frequency; improve **out of production** (clone→prove→PR→human merge).
8. **Spend compute to save attention** — rent servers (Vultr) + GPUs (RunPod/Modal/Vast); fan out agents (Kilo, subagents); pick the cheapest-model-that-clears-the-bar via the Models Browser / kilo-route — under the spend-velocity ceiling (Phase 0).
9. **Self-correct, prove don't claim** — gate-green + adversarial self-review to a fixed point; **consult `ai-consult`/fusion for high-blast-radius decisions** (panel + `verify`); verify against LIVE state, not docs; report failures with evidence.
10. **Bounded authority** — agents talk to the control plane; the control plane talks to prod; no agent holds master creds, a default root shell, or break-glass; autonomy earned per-component.
11. **Durable or it didn't happen** — decisions/capabilities/fixes land in CLAUDE.md / AGENTS.md / rule-packs / skills / memory / this plan, never only in chat.

> *Dropped after the fusion consult:* the `EMPIRE: reuse=..|automate=..` per-task self-report. Attestation ≠ enforcement (agents reward-hack a self-report); enforce mechanically — Doctrines 4/5 are satisfied by the **generated index + advisory grep**, not by an agent attesting it checked. Do not re-add the ritual.

## 5. The factory lifecycle (the real loop)

**Launch → Measure → Kill-or-Graduate → (winners only) Harden.** This replaces v2's infra-only heal/converge loops as the primary loop:
- **Launch** (`fabrik launch`) — zero-attention idea→monetizable-prod.
- **Measure** — every project emits {visitors, signups, MRR, errors, last-deploy} to one control-plane `projects` table (the traction beacon).
- **Kill** — ~$0 revenue AND below signup/visitor threshold by day ~21–30 → `kill_candidate`; no veto in 72h → scale down, pause paid APIs, dump DB to object storage, detach watchdog, park DNS. *(Caveat §9: with zero distribution this kills almost everything — thresholds are provisional until there's an acquisition motion.)*
- **Graduate** — ≥~$100 MRR or ≥5 paid conversions → Tier-1: *now* it earns recovery gauntlet, model-pinning, drift monitoring, dedicated resources, human review.

## 6. Operator-absent policy (resolved — keep from v2)

One `operator_presence` state machine keyed off `last_telegram_ack`: **0–4h** nothing changes · **4–24h "degraded"** autonomous allow-list only (restart Tier A–C w/ backoff; roll back a deploy that failed its own verify if <24h + no migration; renew certs/DNS; scale within ceiling; WAF-block DoS spikes; reroute to maintenance page after 2 failed rollbacks; halt on spend breach) · **24–72h "absent"** stability-only, freeze new deploys + Improve/Prune, stop non-revenue projects · **>30d** dead-man's-switch. **Freeze-list (never, any N):** data/backup deletion · destructive migrations · secret/IAM/root · public exposure · recurring-spend increase · cross-project blast-radius · doctrine/rule-pack edits · merging generated code · any autonomy-widening. **Telegram is a vendor SPOF — add email as a second channel before it's load-bearing.**

## 7. Build sequence v4 — the first 14 working days (effort re-baselined 2.5×; "14 days" ≈ several weeks part-time)

**SINGLE DAY-1 TASK: *fire* — don't just write — the spend kill-switch + dead-man's-switch.** Trip them on purpose; confirm the hard cutoff and scale-to-zero. An uncapped agent fleet with partial authority running unattended can bankrupt you before anything else matters.

1. **Day 1 — Do-not-die floor, tested.** Spend-velocity kill-switch (cut agent-container network on breach) + dead-man's-switch (keyed off `last_telegram_ack`), both *fired*. Confirm no agent holds master/root.
2. **Day 2 — Break-glass + restore.** Bitwarden break-glass verified offline-from-phone; backup-exists + **one real restore** to a throwaway host. Auto-kill cron skeleton (logs, does nothing).
3. **Day 3 — PURGE (the net-deletion gate, made real).** 18 scaffolds → **1 canonical monetizable stack**; trim drivers/registrars to one default path each; archive the rest. Deterministic healthchecks chosen over AI self-heal.
4. **Days 4–5 — THE BRAKE (§3c), before the keystone.** `projects` + `attention_events` schema with honest metrics (`verified_paid_conversions`, `qualified_sessions`, diagnostic visitors/signups) + the **`untested`** state; bot/self-exclusion filter + minimum-exposure gate + **`launch-gate check`**. Test: a 5-bot project lands `untested`; an over-budget portfolio returns BLOCK.
5. **Days 6–11 — `fabrik launch` v0 (keystone; your 5–7d → expect 10–14 real).** spec → repo (the ONE scaffold) → deploy → DNS → DB → commercial-kit (**Stripe webhook = the conversion metric**) → analytics *through the exclusion filter* → traction beacon → control-plane register. **Day 11: launch ONE real project, time it.** If it's 6h not 2h, re-baseline everything.
6. **Day 12 — Auto-kill live** against the real table; confirm it *refuses* to kill an `untested` project.
7. **Days 13–14 — B1 + golden-path.** **B1: generate the capability+live-state index** (`docs/CAPABILITIES.md` + JSON from `fabrik --help` + drivers + `docker ps`; **subsumes the stale `vps-complete-inventory.md`** — the original freshness gap) on a git hook + daily pipeline; ONE `.claude/skill` for `launch`; golden-path acceptance test; set the launch throttle.

**Explicitly NOT in the first 14 days (deferred until a project HONESTLY graduates):** graduation-gate heavy infra, golden-path beyond the one test, **B3 subagents, B5 `ai-consult`, the intent router** (you have OpenRouter already — fewer branches, not more opinions in the loop), all Phase-5 survival infra (full `fabrik prove`, model-pinning, drift index, hash-chain ledger).

**Track B right-sizing (the final panels' call on Pillar B):** Pillar B is **not cut** — it is **B1-first**. B1 (the generated index) is the highest-leverage item and the actual cure for "agents don't know what exists" → ship it Day 13–14. B2 (one `launch` skill) follows. **B3/B4/B5 defer** past the first honest graduate. Net-deletion still applies: a ported `.windsurf/workflow` retires its duplicate.

## 8. Human-gated forever (unchanged)

Data/backup deletion · destructive migrations · secret/IAM/root · public exposure · large recurring spend · cross-project actions · doctrine/rule-pack edits · merging generated code to core. **Meta-rule:** no agent widens its own autonomy or disables a gate. Approvals rate-limited + risk-tiered (impact/proposal/rollback/default-if-no-response).

## 9. The unsolved layer — DISTRIBUTION (honesty banner)

**`fabrik launch` makes you *able* to test 50 ideas cheaply; it does not make anyone show up.** Shipping 500 monetizable apps with zero marketing yields ~zero traction — and auto-kill at day-30 would then scythe everything, measuring *distribution absence*, not product quality. **Velocity is necessary, not sufficient. Distribution is the genuinely unsolved layer and gets its own plan** (channels, content, the Fabrik-exhaust audience flywheel §2, SEO, build-in-public) — it is NOT another deferral; it is the next plan after `fabrik launch` exists. Two cheap guardrails before scaling launch count: **(a) platform-ban contagion** — 50 monetized apps under one Stripe/domain/cloud account = one suspension kills the whole portfolio → use Stripe Connect + isolated domains/accounts early; **(b) legal/refund liability** — you cannot ethically/legally `fabrik destroy` a project that took real money; auto-kill must handle refunds/data-deletion/notice for any project with paying users.

## 10. Self-audit / carried-forward risks

- v1 wrong on keystone (discovery→control); v2 wrong on layer (infra→business-substrate); **v3 corrects to velocity-first.** Recorded, not hidden.
- **Premise honesty (recalibrated by the final panels):** the **empirical solo-portfolio ceiling is ~$3–5M ARR** (Pieter Levels ~$3.1M, Marc Lou ~$1M) — "$1B solo" is, bluntly, a valuation-outlier, not a base-rate. Keep $1B as the *lottery upside* of the dream; **plan and measure against $3–10M ARR**. The binding constraint remains **distribution + a non-zero hit-rate**, not infra (§9). A factory that can't *select* winners from noise (§3c) or *contain* attention (§3c) never compounds regardless of launch volume.
- **The three final-consult killers are now §3c**, not buried: selection blindness, attention bankruptcy, and factory maintenance-debt. They were the unanimous "REVISE" cause; the plan is a GO once §3c ships *before* Phase 2.
- **AI-code security debt at high N:** auto-shipped monetizable apps hold payment data — the watchdog/self-heal is assumed to cover this but the stakes rise with project count; revisit when launch volume grows.
- **Cross-project shared-infra attention** (router/fusion upkeep, 47-module dependency drift) grows non-linearly and is undercounted; the net-deletion gate + auto-kill are the only brakes.
- **Not built yet.** The no-regret first move is **Phase 0 floor + Phase 1 `fabrik launch`**; everything else is gated on a graduate or on the distribution plan.
