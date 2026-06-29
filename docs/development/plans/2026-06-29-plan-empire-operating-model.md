# Plan — Fabrik Empire Operating Model (one-operator, AI-managed) — v3 (velocity-first)

**Status:** DRAFT v3.1 — three `openrouter/fusion` panels (all **unanimous**) → **velocity-first**; keystone `fabrik launch`. **Now explicitly two-pillar (§0):** (A) the Factory + (B) Agent Enablement (a cold agent self-orients + self-acts with zero human onboarding — the substrate that makes A's near-zero-attention real). Survival kept as a cheap floor, gated behind traction.
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

**Why this is co-equal, not a nice-to-have:** every project the factory ships is built/operated by agents. If onboarding an agent costs operator time, that cost rides on *every* project and the per-project-attention KPI never reaches zero. Agent-enablement is the multiplier on the whole factory. It is also self-reinforcing: `fabrik launch` becomes a skill; the watchdog/sysadmin read the same index; a new project auto-registers into the index — the factory documents itself as it grows.

**Cross-agent reality:** Fabrik runs 3+ agent runtimes (Claude Code, Kilo, Cascade/Windsurf, Traycer). The KNOW source must be runtime-neutral (the index + AGENTS.md, which all read); the ACT entry points are per-runtime (`.claude/skills` for Claude Code; `.windsurf/workflows` for Cascade; `AGENTS-compact.md` for Kilo) but generated from the same index so they don't drift.

## 4. Doctrine (binding — velocity lens)

1. **Every line judged by the KPI:** *"Does this make launching/testing/killing/growing a project cost less operator-attention?"* If it only reduces variance, it's survival — and survival is **capped at what protects graduated projects**, not experiments.
2. **Monetizable by default** — no project launches without auth + a payment-or-waitlist path + an analytics funnel. A project that can't be paid or measured is noise.
3. **Cattle, not pets** — auto-kill zero-traction; auto-graduate winners. Attention routed strictly by traction.
4. **Reuse before build** (advisory grep, not blocking) · **net-deletion gate** (every phase deletes/merges ≥1 module) · **durable or it didn't happen.**
5. **Bounded authority** — agents talk to the control plane; the control plane talks to prod; no agent holds master creds, a default root shell, or break-glass; autonomy earned per-component.
6. **Self-heal is a defect signal** — alert on *rising* heal frequency; improve **out of production** (clone→prove→PR→human merge).

## 5. The factory lifecycle (the real loop)

**Launch → Measure → Kill-or-Graduate → (winners only) Harden.** This replaces v2's infra-only heal/converge loops as the primary loop:
- **Launch** (`fabrik launch`) — zero-attention idea→monetizable-prod.
- **Measure** — every project emits {visitors, signups, MRR, errors, last-deploy} to one control-plane `projects` table (the traction beacon).
- **Kill** — ~$0 revenue AND below signup/visitor threshold by day ~21–30 → `kill_candidate`; no veto in 72h → scale down, pause paid APIs, dump DB to object storage, detach watchdog, park DNS. *(Caveat §9: with zero distribution this kills almost everything — thresholds are provisional until there's an acquisition motion.)*
- **Graduate** — ≥~$100 MRR or ≥5 paid conversions → Tier-1: *now* it earns recovery gauntlet, model-pinning, drift monitoring, dedicated resources, human review.

## 6. Operator-absent policy (resolved — keep from v2)

One `operator_presence` state machine keyed off `last_telegram_ack`: **0–4h** nothing changes · **4–24h "degraded"** autonomous allow-list only (restart Tier A–C w/ backoff; roll back a deploy that failed its own verify if <24h + no migration; renew certs/DNS; scale within ceiling; WAF-block DoS spikes; reroute to maintenance page after 2 failed rollbacks; halt on spend breach) · **24–72h "absent"** stability-only, freeze new deploys + Improve/Prune, stop non-revenue projects · **>30d** dead-man's-switch. **Freeze-list (never, any N):** data/backup deletion · destructive migrations · secret/IAM/root · public exposure · recurring-spend increase · cross-project blast-radius · doctrine/rule-pack edits · merging generated code · any autonomy-widening. **Telegram is a vendor SPOF — add email as a second channel before it's load-bearing.**

## 7. Build sequence v3 (velocity-first; effort is optimistic — treat as 2–5×)

| # | Phase | Builds on | Effort* |
|---|---|---|---|
| **0** | **Do-not-die floor + Auto-Kill (cap it at ~1–2 days, not a sprawl-archaeology project).** Spend-velocity kill-switch (cut agent-container network on breach) + dead-man's-switch + break-glass (Bitwarden/encrypted, **not** Shamir yet) + backup-exists + ONE restore smoke test. Plus the **auto-kill cron** scaffold (needs the beacon, §1-after). Delete only sprawl that blocks launch (cap 8 operator-hrs). | `cost-budget`, `vultr_drill` | 2d |
| **1** | **`fabrik launch` — the velocity engine (§3). THE keystone.** Canonical monetizable scaffold + commercial-kit + auto-enroll (control-plane + watchdog) + traction beacon. | 18 scaffolds, 47 lib modules, `fabrik apply` | 5–7d |
| **2** | **Traction beacon + `projects` table + Grim-Reaper auto-kill** (the Measure+Kill half of §5). | `data/projects.yaml`, `sync_projects.py` | 2d |
| **3** | **Graduation gate** — thin metrics view; ≥$100 MRR / ≥5 conv → Tier-1 unlocks the heavy infra. | beacon | 1d |
| **4** | **Golden-path acceptance tests** — `fabrik launch` 3 example specs → assert 200 + signup + payment/waitlist + analytics event + watchdog enrolled + kill/promote attached. (This is the only agent-regression that matters now.) | `scripts/enforcement/` | 1–2d |
| **5+** | **Survival infra — GATED to Tier-1 graduates only:** full `fabrik prove` gauntlet, model-pinning + golden-incident regression, drift index, git-as-state + minimal hash-chained runtime log. Built *when the first project graduates*, not before. | `audit-registrars`, watchdog tables | deferred |

\* Optimistic-with-Claude-Code; the panel flags 2–5× once integration/debug/operator-review is counted. **Phase 1 is the only no-regret big build.**

**Track B (Pillar B — Agent Enablement; runs in PARALLEL, cheap, de-risks every other phase):**
- **B1 — Generate the capability index** (`docs/CAPABILITIES.md` + JSON; introspects CLI/drivers/scripts/specs/lib/live-`docker ps`; wired into the daily pipeline). ~1.5d. *Do this near-first: it's what lets the agent building `fabrik launch` reuse the 47 modules / 27 drivers instead of re-inventing — it pays for itself inside Phase 1.*
- **B2 — Skills + slash-commands** (`.claude/skills/`) ported from `.windsurf/workflows`, incl. a `launch` skill once Phase 1 lands. ~2d, incremental.
- **B3 — Domain subagents** (`.claude/agents/`: `fleet-auditor`, `deploy-readiness`, `launch`) — only the heavy isolated ones. ~1–2d.
- **B4 — One-hop orientation:** CLAUDE.md/AGENTS.md point at the index as step 1 of orientation; index regenerates per project so the factory self-documents. ~0.5d.

Sequencing: **B1 first (alongside Phase 0)**, then B2/B4 alongside Phase 1, B3 as heavy sweeps appear. Net-deletion still applies — porting a `.windsurf/workflow` to a skill should retire the duplicate, not double it.

## 8. Human-gated forever (unchanged)

Data/backup deletion · destructive migrations · secret/IAM/root · public exposure · large recurring spend · cross-project actions · doctrine/rule-pack edits · merging generated code to core. **Meta-rule:** no agent widens its own autonomy or disables a gate. Approvals rate-limited + risk-tiered (impact/proposal/rollback/default-if-no-response).

## 9. The unsolved layer — DISTRIBUTION (honesty banner)

**`fabrik launch` makes you *able* to test 50 ideas cheaply; it does not make anyone show up.** Shipping 500 monetizable apps with zero marketing yields ~zero traction — and auto-kill at day-30 would then scythe everything, measuring *distribution absence*, not product quality. **Velocity is necessary, not sufficient. Distribution is the genuinely unsolved layer and gets its own plan** (channels, content, the Fabrik-exhaust audience flywheel §2, SEO, build-in-public) — it is NOT another deferral; it is the next plan after `fabrik launch` exists. Two cheap guardrails before scaling launch count: **(a) platform-ban contagion** — 50 monetized apps under one Stripe/domain/cloud account = one suspension kills the whole portfolio → use Stripe Connect + isolated domains/accounts early; **(b) legal/refund liability** — you cannot ethically/legally `fabrik destroy` a project that took real money; auto-kill must handle refunds/data-deletion/notice for any project with paying users.

## 10. Self-audit / carried-forward risks

- v1 wrong on keystone (discovery→control); v2 wrong on layer (infra→business-substrate); **v3 corrects to velocity-first.** Recorded, not hidden.
- **Premise honesty:** "$1B solo in 2–5y" is a portfolio bet whose binding constraint is **distribution + a non-zero hit-rate**, not infra. This plan builds the factory; the portfolio still needs winners, and winners need distribution (§9).
- **AI-code security debt at high N:** auto-shipped monetizable apps hold payment data — the watchdog/self-heal is assumed to cover this but the stakes rise with project count; revisit when launch volume grows.
- **Cross-project shared-infra attention** (router/fusion upkeep, 47-module dependency drift) grows non-linearly and is undercounted; the net-deletion gate + auto-kill are the only brakes.
- **Not built yet.** The no-regret first move is **Phase 0 floor + Phase 1 `fabrik launch`**; everything else is gated on a graduate or on the distribution plan.
