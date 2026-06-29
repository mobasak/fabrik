# Plan — Fabrik Empire Operating Model (one-operator, AI-managed) — v2

**Status:** DRAFT v2.1 — iterated against `openrouter/fusion` panels; target clarified to the **project-factory / portfolio thesis** (§0). **Survive-first, build-less, per-project-attention→0.** Operator-absent policy resolved (§5). Phase 0 (delete sprawl) gates everything.
**Date:** 2026-06-29
**Owner:** Operator + Fabrik AI (hub control plane)
**Provenance:** Two frontier panel consults (`openrouter/fusion` → Claude-Opus/GPT/Gemini panel, Opus-4.8 judge; $0.86 + $0.76; raw in scratchpad `fusion_out2.txt` / `fusion_out3.txt`). v1 led with a capability index → corrected to control-first. v2 corrects three structural gaps the panel found in v1 (§1).

---

## 0. Mission

Run and grow Fabrik as a **mostly-to-fully AI-managed software company operated by ONE human**. The scarce resource is **operator attention at the moment something is silently wrong**. Spend compute, agents (Claude Code, Kilo, fusion, Traycer), and rentable servers/GPUs freely to protect it. **Build less; tier everything; the system shrinks its own complexity over time.** A surviving floor beats a clever ceiling.

**The "$1B solo" target is an explicit 2–5 year DREAM, not a today-state.** The thesis: the infra is a **project factory** — one operator + AI ships *many* projects at **near-zero marginal operator-cost per project**, a few hit, and the *portfolio* reaches a $1B valuation. That reframes the whole OS: the metric it must drive toward zero is **per-project marginal operator-attention** — project #50 must cost no more human time than project #5. Self-management/self-healing isn't a nicety; it's the precondition for project *velocity*. Every capability is judged by: *does this let the operator ship the next project without adding load?*

## 1. What v2 fixes (the three structural gaps in v1)

The panel judged v1 would produce *a better-governed ops platform, not a solo-survivable lean company*. Three gaps, now addressed:

- **Gap A — it governs the infrastructure, not the company.** A $1B solo shop dies from maintaining 38 projects with no revenue, not from registrar drift. v1 had no **portfolio governor / project tiering / attention-accounting**. → Phase 0 + §6 note. *(The full business layer — customer-acquisition / support / revenue-churn / "stop doing this product" loops — is the real $1B driver and is OUT OF SCOPE for this infra-OS plan; it gets its own plan. Naming it so we don't mistake a self-healing machine running dead products for an empire.)*
- **Gap B — leanness was asserted, not mechanized.** v1 added 6 phases of machinery atop existing sprawl (507 docs, 79 scripts, 47 modules) with no net-deletion gate → safety becomes the new monolith, *and* a bigger surface the AI itself must navigate (context-overflow/hallucination risk). → **net-deletion doctrine (§3.5) + hard control-plane budgets (§9) + Phase 0 deletes first.**
- **Gap C — not solo-survivable.** Everything assumed the operator answers Telegram. No dead-man's-switch, no bus-factor escape, no out-of-band recovery if the hub/ledger dies. → §5 operator-absent policy + §7 killer-risk mitigations. And "self-improving" is honestly **operator-assisted backlog** — named as such, sequenced last.

## 2. Keystone

Not discovery (capability index), not even "control" alone — **survivability + bounded authority**. The three things that protect against *unbounded loss*: spend can't run away, nothing acts unrecorded, you can come back from disaster. Everything else is optimization to earn later.

## 3. Operating Doctrine (binding)

1. **Reuse before build** — enforced by an **advisory** capability grep (NOT blocking; with 38 projects a blocking dup-check false-positives and *costs* attention).
2. **Unrecorded prod-impacting step = defect.** Read-only diagnostics, tests, docs, planning are exempt. Deliberate human risk-gates (§8) are not defects.
3. **Self-heal is anesthetic, not cure.** Every heal is a defect signal; track mean-time-between-heals per project; alert on any *decrease*; after N heals/window, freeze auto-heal + escalate.
4. **Bounded authority.** Agents talk to the control plane; the control plane talks to prod. No agent holds the master cred set, a default root shell, or the break-glass envelope. Autonomy is **earned per-component** by demonstrated heal/converge history.
5. **Net-deletion gate (NEW).** Every new phase/feature must delete or merge **≥1 existing module/script/doc**, or it is rejected. Complexity-shrinkage is a hard constraint, not an aspiration.
6. **Spend compute to save attention** — under a hard **spend-velocity** ceiling (Phase 1) that halts-and-pings.
7. **Durable or it didn't happen** — decisions land in CLAUDE.md / AGENTS.md / rule-packs / memory / this plan.
8. **Self-correct to a measured fixed point** — `drift==0 AND heal-rate flat-or-decreasing`; verify against live state.
9. **Improve out of production** — clone→prove→PR→**human merge**. Never mutate live to "improve." This is *operator-assisted*, not autonomous.

> Killed from v1: the `EMPIRE:` self-report ritual (attestation ≠ enforcement) and the *blocking* reuse-grep.

## 4. Control loops (4, by cadence) — build the floor before the upper loops

| Loop | Cadence | Autonomy | Today |
|---|---|---|---|
| **1 — Heal** | sec–min | bounded autonomous (restart/rollback/failover to known-good; never changes intent) | ✅ watchdog Tier A–C |
| **2 — Converge** | hourly–daily | auto-fix *reversible* drift; *propose* spec changes | ⚠️ partial (`audit-registrars`/`reconcile-all`) |
| **3 — Improve** | weekly | AI proposes a backlog *ranked by operator-minutes-saved*; **operator approves the batch** | ❌ later |
| **4 — Prune** | monthly | AI proposes deletion *candidates* (report only); **never autonomous deletion** | ❌ later |

## 5. Operator-absent policy — RESOLVED (adopt as default)

One `operator_presence` state machine keyed off `last_telegram_ack`. Escalating, ~0.5 day.

- **0–4h:** nothing changes; queued actions wait.
- **4–24h "degraded" — autonomous allow-list ONLY:** restart crashed services (Tier A–C, max 3×/30min then backoff); roll back a deploy that failed its own verify *iff* deploy <24h, rollback pre-tested, no DB migration; renew certs/DNS; scale within a pre-set ceiling; WAF/iptables block on DoS-signature spikes; if rollback fails 2×, reroute DNS to a static maintenance page; apply already-approved+ledgered changes; halt on spend breach.
- **24–72h "absent":** shrink to stability-only. Freeze Improve/Prune + all new deploys except emergency rollback; only Tier-0/1 self-heal; stop non-revenue projects to save spend; daily digest to Telegram **+ email**.
- **>30d "incapacitated":** dead-man's-switch fires (§7a).
- **FREEZE-LIST (never, any N, even present):** data/backup deletion · destructive migrations · secret/IAM/root rotation *initiation* · public exposure · recurring-spend increase · cross-project blast-radius · doctrine/rule-pack edits · merging generated code to core · **any action that widens an agent's autonomy.**

## 6. Build sequence v2 (~16 working days nominal — see §10 effort caveat)

Each phase **extends a named existing asset** (reuse-first) and **net-deletes ≥1** (Doctrine 5). The 20/80: if you build only three, build **0/1/(prove)** — they're the survival floor.

| # | Phase | Extends | Effort* |
|---|---|---|---|
| **0** | **Triage + tiering + delete sprawl.** `projects.yaml` Tier 0–4 (Tier-0 = control-plane/backups/DNS/monitoring/billing/ledger; Tier-1 = revenue/customer-facing; freeze/archive Tier-3/4). Control-plane budgets (§9). Delete: rule-packs 49→~15, ops scripts 79→~25, docs 507→index+per-project READMEs. Add `last_used`/`owner`/`delete_after` metadata. | `data/projects.yaml`, `sync_projects.py` | 2d |
| **1** | **Spend-velocity kill-switch + presence SM + dead-man's-switch + Shamir break-glass.** ~1-min billing/velocity poll; on breach cut network to agent containers + Telegram. | fabrik-lib `cost-budget/cost_budget.py` | 2d |
| **2** | **Ledger — git-as-state + minimal hash-chained runtime log.** Git is the universal ledger for code/config (commit=change, signed tag=approval, `git diff` vs live=drift). A *small* append-only hash-chained log ONLY for non-code runtime actions git can't express (spend, infra mutations, agent intent, blast-radius, rollback-refs). **Prod-impacting actions only.** Mirror to spoke + daily object-lock export; boot refuses authority on broken chain; emergency retroactive-entry path (≤24h, agent-inaccessible). | watchdog `deploys`/`approvals` (`60-watchdog.md:83,105`) | 2–3d |
| **3** | **Thin `fabrik prove` recovery gauntlet — Tier-0/1 ONLY.** Rent VPS → bootstrap from declared state → restore real backups → smoke + DB-integrity tests → test rollback → destroy → record RTO/RPO. Pass/fail gates autonomy. *(Moved up: validates recovery before more machinery.)* | `vultr_drill.py:410`, `export`/`import` | 3d |
| **4** | **Drift index — `declared / observed / unknown` daily report** (not a full ranked index yet). `unknown` is the state that kills you. | `audit-registrars` (`cli.py:1371`, `audit.py`) | 1.5d |
| **5** | **Agent regression harness + model-pinning** (§7b). 10 golden incidents incl. *refuse-destructive* / *refuse-secret-exposure*; nightly + pre-change; <100% on safety tasks → diagnose-only + Telegram. | 39 `scripts/enforcement/` checks | 2–3d |
| **6** | **Postmortem-draft + assisted Improve/Prune.** Incident → AI *drafts* a regression test + PR (never auto-appends an enforcement check). Improve = weekly ≤10-item backlog ranked by operator-minutes-saved; Prune = monthly deletion-*candidates* report. Human approves; no autonomous deletion. | `scripts/enforcement/` | 2d |

\* Effort is nominal-with-Claude-Code-doing-the-hands. **The panel flags these are likely 2–5× underestimates** once integration/debugging/operator-review is counted. Treat "16 days" as "several weeks, part-time." Everything past Phase 3 is iteration, not survival.

## 7. The 2 risks that actually kill a solo empire (folded into phases)

**(a) Bus-factor / dead-man's-switch (highest kill probability) — Phase 1.** You're the SPOF; lose the laptop / get sick → company evaporates. Shamir 2-of-3 master-cred split (you + lawyer + cold storage); an `operator_heartbeat`; no heartbeat 30d → email a designated successor a continuity packet (where backups/bills/break-glass live) + run `fabrik prove` to confirm restorability. Agents can NEVER touch the break-glass envelope. ~1d.

**(b) Agent behavioral drift under silent model updates — Phase 5.** OpenRouter swaps a backend or Anthropic re-aligns a model and your autonomous sidecars silently change behavior — your checks validate the *system*, not the *agents that run it*. Record per-agent `provider/model/version/prompt-hash/tool-schema-hash/autonomy-level`; nightly golden-incident regression; drift → freeze autonomy. ~2–3d.

(Ledger-SPOF → mitigated by Phase 2's mirror + hash-chain. Data-integrity-beyond-restorability and fixed-point oscillation are real but won't kill you in year one — deferred, not denied.)

## 8. Human-gated forever (non-negotiable)

Data/backup deletion · destructive/irreversible migrations · secret/IAM/root changes · public-network exposure · large recurring spend · cross-project / multi-tenant actions · **changing the doctrine or rule-packs** · merging generated code into the core control plane. **Meta-rule:** no agent may ever widen its own autonomy or disable a gate. **Approvals are rate-limited + risk-tiered** (impact/proposal/rollback/default-if-no-response); if you approve >~5/day the gate is decorative — ban vague "what should I do?" escalations.

## 9. Control-plane budget (hard caps — Phase 0, enforced thereafter)

≤12 top-level CLI cmds · ≤25 ops scripts · ≤50 docs counted as current · ≤15 rule-packs (each with expiry/review date + firing-frequency report) · ≤20 active service specs. **Every new control feature deletes/merges ≥2 artifacts or is rejected.** Never auto-delete without usage attribution (`last_used`).

## 10. Self-audit / unsolved (carry forward; do not pretend solved)

- v1 was wrong on its keystone (discovery→control) and v1's scope was wrong on its *layer* (infra, not business). Recorded, not hidden.
- **Premise (clarified by operator):** "$1B solo" is a **2–5 year portfolio dream** — many AI-built projects on this infra, a few hit, the portfolio reaches the valuation. So this OS's job is to drive **per-project marginal operator-attention → ~0** (project #50 costs no more human time than #5), which makes project *velocity* the real KPI. The binding constraints then shift to **revenue / distribution / legal / tax** — out of scope here but the actual gating layer. This is the factory floor: necessary, not sufficient. **Corollary:** every phase should also be judged "does it reduce per-project operator-load?", not only "does it reduce risk?"
- **Vendor-concentration SPOF:** the whole stack rests on Anthropic + OpenRouter + Vultr + **Telegram (sole approval channel)** — single-vendor outage/suspension is as severe as the ledger SPOF. Add a second approval channel (email/signal) before Telegram becomes load-bearing.
- **Legal/regulatory continuity:** a one-person company holding customer data carries GDPR/SLA/entity obligations that persist when you're absent — the continuity packet must include these, not just creds.
- **Safety-machinery operating tax:** weekly gauntlets + nightly regression + 1-min billing polls consume real spend + review time; budget it against the "lean" goal or it becomes the sprawl it was meant to prevent.
- **Approval fatigue** is a failure mode, not a UX nit — batching/risk-tiering (§8) is load-bearing.
- **Not claimed:** nothing here is built. Effort estimates are optimistic (2–5×). Phase 0 is the only no-regret start.
