# Plan — Fabrik Empire Operating Model (one-operator, AI-managed)

**Status:** DRAFT — roadmap; needs the §7 operator-absent decision before Phase 2+ executes.
**Date:** 2026-06-29
**Owner:** Operator + Fabrik AI (hub control plane)
**Provenance:** Corrected by a frontier panel consult (`openrouter/fusion` → Claude-Opus/GPT/Gemini panel, Opus-4.8 judge; $0.86; raw in scratchpad `fusion_out2.txt`). The consult overturned the original "capability-index-first" plan — see §1.

---

## 0. Mission

Run and grow Fabrik as a **mostly-to-fully AI-managed software company operated by ONE human**. The only scarce resource is **operator attention at the moment something is silently wrong**. Spend compute, agents (Claude Code, Kilo, OpenRouter/fusion, Traycer), and rentable servers/GPUs (Vultr/RunPod/Modal/Vast) freely to protect it. Every task either ships value or removes a human from a loop. **The system must also shrink itself** — sprawl is the enemy, not the asset.

## 1. The keystone correction (what changed and why)

The original plan made a **capability index + an `EMPIRE:` per-task self-report** the keystone. The panel unanimously rejected this:

- A capability index solves **discovery** ("what can I do?"), not **control** ("should this happen, did it work, what's silently rotting?"). It makes sprawl *navigable, not smaller* — it paves the cow path.
- **Self-reported attestation ≠ enforcement.** Agents will emit `reuse=true` and write the bespoke script anyway (reward-hacking, guaranteed). **Enforce mechanically at the runtime perimeter, not in the prompt.**
- The real keystone is **a measured Reality-vs-Intent control layer** + bounded authority. The capability index is one *output* of that, built later.

## 2. Operating Doctrine (revised — binding)

1. **Reuse before build** — enforced *mechanically*: the build/scaffold path greps the (generated) capability index and **blocks on a near-duplicate**; it does not ask an agent to attest it checked.
2. **Unrecorded manual step = defect** (softened from "manual = defect"). Some manual gates are deliberate **risk boundaries** (see §6) and must stay. What's banned is the *undocumented, unledgered* manual step.
3. **Self-heal is anesthetic, not cure.** Every heal is a **defect signal**. Track mean-time-between-heals per project; **alert on any decrease**; after N heals/window, freeze auto-heal and escalate.
4. **Bounded authority.** Agents talk to the control plane; the control plane talks to production. No agent holds the master credential set or a default root shell. Autonomy is **earned per-component** by demonstrated heal/converge history, never granted globally.
5. **Lean + self-pruning.** Single-operator threat model. The system runs a monthly "what can we delete?" loop (§3, Loop 4). Surface-area targets are real deliverables, not aspirations.
6. **Spend compute to save attention** — under a hard **spend-velocity** ceiling (§4 Phase 1) that halts-and-pings, not logs.
7. **Durable or it didn't happen.** Decisions/capabilities/fixes land in CLAUDE.md / AGENTS.md / rule-packs / skills / memory / this plan — never only in chat.
8. **Self-correct to a measured fixed point.** The fixed point is literal: `drift == 0 AND heal-rate flat-or-decreasing`. Verify against **live** state, not docs. Prove, don't claim.
9. **Improve out of production.** Self-improvement = clone→prove→PR→**human merge**. Never mutate live to "improve."

> Dropped from the original plan: the `EMPIRE: reuse=.. | automate=.. | heal=..` first-line ritual. Replaced by mechanical perimeter checks (Doctrine 1/4) + the ledger (Phase 2).

## 3. Control-loop architecture (4 nested loops, different cadences)

| Loop | Cadence | Autonomy | Exists today? |
|---|---|---|---|
| **1 — Heal** | seconds–min | autonomous, bounded (restart/rollback/failover to known-good; never changes intent) | ✅ watchdog Tier A–C |
| **2 — Converge** | hourly–daily | auto-fix *reversible* drift to spec; *propose* spec changes | ⚠️ partial — `audit-registrars`/`reconcile-all` exist; not per-project converged/drifted/**unknown** |
| **3 — Improve** | weekly | AI *proposes* a ranked backlog from telemetry (heal-rates, drift recurrence, cost/task, rule-firing); **operator approves the batch** | ❌ missing |
| **4 — Prune** | monthly | AI proposes deletions/merges (unused drivers/scripts/docs/projects); operator approves | ❌ missing |

Each loop's output is the next loop's input: heals feed Converge; convergence failures feed Improve; Improve's changes get measured by Heal. *That* cycle — a system that metabolizes its own failures — is what "100-person company" means operationally (institutional memory + safety + throughput, **not** headcount).

## 4. Build order (fusion-corrected; each phase EXTENDS an existing asset)

**Phase 1 — Spend-velocity kill-switch (hours; do FIRST).** A hard per-loop and per-day ceiling that **halts and Telegrams**, not logs — before any autonomy increase. *Extend* `/opt/fabrik-lib/cost-budget/cost_budget.py` (today: absolute daily/per-incident caps) with a **velocity** breaker + a global fleet ceiling. Guards the catastrophic-cheap failure (a heal→break→heal loop burning $400 overnight).

**Phase 2 — Append-only cross-agent change ledger.** One query for "what changed in the last 6h and by which agent." *Extend* the watchdog `deploys`/`approvals` tables (`60-watchdog.md:83,105`) into a unified ledger every actor (Claude Code sysadmins, sidecars, the pipeline, `fabrik apply`) writes: actor, scope, intent, commands, diffs, blast-radius, approval, result, rollback. No ledger entry → no action (Doctrine 4).

**Phase 3 — Drift / Reality-vs-Intent index (the true keystone).** Per-project status: `converged / drifted / **unknown**` (unknown is the state that kills you), ranked by blast radius. *Extend* `fabrik audit-registrars` (`cli.py:1371`, `audit.py`, `scripts/audit_all_registrars.py`) from registrar-drift to whole-project drift (compose/DNS/Traefik/DB/Redis/secrets). Makes Doctrine 8's fixed point measurable. **This — not the capability index — is the keystone.**

**Phase 4 — `fabrik prove` recovery gauntlet + restore drill.** Rent a fresh VPS → bootstrap from declared state → restore real backups → run critical-flow + DB-integrity tests → test rollback → destroy → record RTO/RPO. *Extend* `vultr_drill.py:410` (`fabrik vultr drill`) + `export`/`import` + bootstrap. Untested backups are the most likely company-ender; an index *claims* deploy works, `prove` shows it *did*.

**Phase 5 — Postmortem-to-Patch (the only compounding capability).** Every incident auto-extracts the violated invariant → generates a regression **check + reproducing test** → files it for one-click approval → it joins the 39 `scripts/enforcement/` checks forever. System competence rises monotonically with each failure = the operator's institutional memory.

**Phase 6 — Capability index + heal-rate-as-alarm + the Improve/Prune loops.** *Now* build the generated index (it was the original "keystone") as an output of the ledger+drift layer, with reuse enforced mechanically (Doctrine 1). Add heal-rate alerting and Loops 3–4.

## 5. Adjacent guardrails (fold into the phases above)

- **Approval firewall** (with Phase 2): rate-limited, risk-tiered Telegram; every approval carries impact / proposal / rollback / **default-if-no-response**. Ban vague "what should I do?" escalations. If you approve >~5/day, the gate is decorative.
- **Host sysadmins read-only for diagnostics** (with Phase 3): out-of-band host fixes drift, then `fabrik apply` overwrites them and crashes the node. Fixes route through a central spec commit, never in-place.
- **Route by blast-radius, not just cheapest-model** (with Phase 2): cheap model summarizes logs; prod-mutation *proposals* need a strong model; prod-mutation *execution* is a deterministic tool behind the policy gate. Ops is tail-risk dominated.
- **Scoped, short-TTL creds via a broker** (with Phase 4): agents + tool access + private data + external comms = the lethal trifecta (prompt-injection exfil). Never the master set.
- **Independent verifier** (with Phase 5): the agent that writes the fix is not the sole verifier of the fix.

## 6. Human-gated forever (non-negotiable)

Data/backup deletion · destructive/irreversible DB migrations · secret/IAM/root changes · public-network exposure · large recurring spend (e.g. a week-long GPU box, not a spot hour) · cross-project / multi-tenant blast-radius actions · **changing the doctrine or rule-packs themselves** · merging generated code into the core control plane. **Meta-rule:** no agent may ever widen its own autonomy or disable a gate.

## 7. OPEN DECISION (gates Phase 2+) — operator-absent mode

> **When you don't answer Telegram for N hours, what is the system allowed to do?**

This single policy determines how much autonomy is safe everywhere else. Define: the N-hour threshold; the allow-list of autonomous actions while absent (heal-to-known-good? converge reversible drift?); and the freeze-list (no spec changes, no spend > $X, no destructive anything). **Resolve this before Phase 2 ships.** The operator is a SPOF; this is the degraded mode.

## 8. Surface-area budget (Loop 4 targets — directional, usage-gated)

27 drivers → ~3 blessed · 18 scaffolds → ~4 · 79 ops scripts → wrapped by `fabrik` cmds or deleted · 507 docs → generated + a small human core · 49 rule-packs → consolidated, each with an expiry/review date + a firing-frequency report (a rule that never fires is perfect or dead — you can't tell without data). **Never auto-delete without usage attribution** (a low-traffic driver may serve a revenue-critical project).

## 9. Self-audit / honesty

- This plan was **wrong on its keystone** until the fusion consult; it now leads with control, not discovery. Recorded, not hidden.
- Every phase **extends a named existing asset** (paths in §4) — reuse-before-build applied to the roadmap itself.
- **Not claimed:** nothing here is built. Phases 2+ are gated on §7. The biggest unaddressed risks the panel itself flagged: the control-plane/ledger is itself a SPOF (no quorum/out-of-band recovery yet); agent behavioral drift under silent model updates (no version-pinning/regression of the agents themselves); data-integrity beyond restorability; bus-factor / dead-man's-switch for a one-person company; and the meta-risk that this safety machinery becomes the new sprawl. Carry these into the relevant phases; do not pretend they're solved.
