# Fabrik Factory — Information & Enforcement Architecture (Design Spec)

**Status:** CONVERGED
**Date:** 2026-07-18
**Kind:** meta-design (the factory that builds all projects — not a product itself)
**Owner:** operator (solo dev)

> This is the governing design for how the Fabrik autonomous coding factory delivers rules to acting agents
> and enforces them. It is a **design-time source**: the command chains, skills, gates, and governance docs are
> authored/compiled to satisfy it. It supersedes the stale "two-workflow / tool-less-Traycer / always-read-AGENTS.md"
> model (north-star D1/D2/D6, corrected 2026-07-18).

---

## Goal

For a **solo owner** running **Traycer desktop ⇐ Claude Max engine ⇐ OpenRouter/`fabrik-lib` pool** (chat-only, two
human gates), design the factory so that:

1. **Owner needs are fulfilled** — chat-only interaction (never hand-edit), persist-on-confirm, Traycer cards, two
   gates (decomposition-in, `fabrik apply`-out), procurement discipline (free→cheapest→build), and "use what I already have."
2. **Rules are enforced as reliably as the mechanism allows** — not by hoping a doer reads a governance document
   (empirically unreliable), but via a **reliability ladder**: mechanical *certainty* where a gate can check, and
   *maximally-enforced* (injected-rubric, separate-reviewer, converge-to-no-op) — **not merely hoped** — semantic
   compliance where only a reviewer can judge. The honest bound on the semantic tier is stated in § Known limitations
   (it raises compliance probability; it does not prove it).
3. **Leanest-but-complete, ZERO repetition** — one canonical home per kind of information; governance docs are
   **compiled FROM at authoring time**, never **referenced AT runtime**; commands are self-sufficient.

---

## The governing law (the one principle everything derives from)

> **Nothing is ambient. Every load-bearing constraint reaches the acting agent through one of three delivery tiers
> — mechanical gate, compiled context, or armed review — never by an agent voluntarily reading a governance doc.**

This replaces the assumption that `AGENTS.md`/rules are "always in context." They are not, and even when they are,
compliance is not guaranteed (grounding §G1). Governance docs become **build inputs**, not runtime references.

---

## Chosen approach — the Reliability Ladder

Three delivery tiers, most-reliable first. Each catches a different violation class; together they are complete.

| Tier | Mechanism | Catches | Primary grounding |
|---|---|---|---|
| **1 — Mechanical gate** | `final_gate.py` (Tier-2: ruff/mypy/bandit/semgrep/…), `epic_order.py`, `scaffold.py`, `check_*` suite, Claude Code **hooks** | Mechanical/structural violations (types, secrets, schema-sync, counts, ports, sprawl). Deterministic — **can't be skimmed.** | G1 (Anthropic: for must-run, use enforcement/hooks, not prose) |
| **2 — Compiled context** | Self-sufficient **command/skill files** (decisions inlined at authoring time; progressive disclosure) + the **one auto-loaded file `CLAUDE.md`** | The agent skipping context — it's *in* the execution window. | G2/G3 (Anthropic context-engineering: high-signal governance "dropped into context up front"; Skills compile rules at build time) |
| **3 — Armed adversarial review** | `/fabrik-review`, mega-`04`, ettw-`08`/`10`: a **separate** reviewer **injected** with `select_rules.py`'s matched packs **+ the `EVALUATION_CHECKLIST` items as a discrete rubric**, looped to a **no-op** with a **refute step + oscillation guard** | **Semantic** violations a script cannot ("this design ignores the auth rule"). **This is the compliance engine.** | G4/G5/G6 |

**The load-bearing consequence:** semantic "rules obeyed" is driven primarily at **Tier 3** — a fresh reviewer armed
with the exact rule excerpts hunts the doer's output; the doer need not have read the rule. Tier 1 covers mechanics;
Tier 2 keeps the doer on-track. Nothing relies on "read doc X and obey." ⚠️ But Tier 3 **raises the probability** of
compliance — it does not prove it (see § Known limitations & honest bounds); the design's honest claim is
*"maximally-enforced,"* not *"guaranteed-compliant."*

---

## Known limitations & honest bounds (what this design does NOT guarantee)

Surfaced by an independent adversarial review 2026-07-18. These are inherent bounds, not fixable defects — the design
mitigates them; it does not eliminate them. Stating them is what keeps the design honest.

- **L1 — No-op ≠ compliance. Tier 3's fixed point is a fixed point of the reviewer's RECALL, not of zero violations.**
  "Converge-to-no-op" means the reviewer *stopped finding*, not that nothing is there (G5: judge recall can be low).
  The loop **raises compliance probability** — via rubric injection (G5's root-cause fix), family-diverse finders
  (`fanout`), and multiple rounds — but does not make it certain. "Rules obeyed" (Goal §2) is **probabilistic, not
  sound.** *Mitigation, not cure:* inject the rubric that covers the violation classes; diversify finders; keep the
  mechanical gates (Tier 1) as the sound floor for everything they *can* check.
- **L2 — Residual "obey in-context" dependency (not eliminated, reduced).** Tier 3 replaces *"hope the doer reads the
  doc"* with *"the reviewer obeys the injected rubric"* — a **weaker** version of the same dependency the governing law
  distrusts (G1: even loaded context is "no guarantee"). The design's real claim is a **reduction ladder**: injection >
  voluntary reading; separate reviewer > self-review; multi-round + diverse > single. It moves the reliance to its most
  favorable form; it does not remove it.
- **L3 — Pack-selection blind spot.** Tier 3 is armed by `select_rules.py`, which activates packs by **glob match on
  existing files**. For a greenfield/design-time artifact (few files), the ACTIVE set is near-empty and packs are
  chosen *proactively* — if the doer chose the wrong packs, an armed reviewer that inherits the same selection is
  **blind to the same rule** (the shared-blind-spot failure the design claims to fix). *Mitigation:* the reviewer must
  select packs **independently of the doer** (description-based, err toward a superset), and the `EVALUATION_CHECKLIST`
  rubric is **always injected** regardless of glob — so at least the chain's own discipline is never un-armed.
- **L4 — This is 3–4 independently-shippable workstreams, not one build.** (a) collapse+`@import` the agents doc,
  (b) wire `select_rules`+rubric injection into the review commands, (c) bake the governing law into the north-star,
  (d) the `service_catalog.json` mechanical step. Shared philosophy, **disjoint blast radii** — (a) and (b) can ship
  independently. `/fabrik-plan-after-chat` phases them; the success criterion for "rules obeyed" is a **process metric**
  (every review boundary injects the matched rubric + checklist) plus the L1 probability improvement — never an absolute.

## Information architecture (one canonical home per kind — DRY)

```
DESIGN-TIME SOURCES  — we (owner + Claude) read these to AUTHOR the factory; runtime agents do NOT
  · north-star + § Owner Working Model    = intent, decisions, this governing law
  · .windsurf/rules/** (54 packs)          = THE discipline base (planning + code + domain) — canonical
  · ONE agents doc (agents-fabrik.md)      = live platform facts ONLY (hosts/ports/services/projects) — rule-restatements stripped
  · service_catalog.json (+ gather_envs.py)= machine inventory of owned external services
        │  compiled at authoring time ↓            fetched fresh at review time ↓
COMPILED PROGRAMS (self-sufficient)          ARMED REVIEW (Tier 3)
  · mega-epic-breakdown 00→02→03→04           · select_rules.py → matched packs' mandates
  · epic-to-ticket-workflow 00→…→11           · EVALUATION_CHECKLIST items = discrete rubric
  · ~/.claude/commands /fabrik-*              · injected into finder prompts; loop to no-op
        │                                     ↑ enforces the rules the doer may not have read
MECHANICAL GATES (Tier 1, deterministic)     BOOTSTRAP (the only auto-loaded file)
  · scaffold.py · epic_order.py               · CLAUDE.md = hard-stops + gate contract + pointers
  · final_gate.py (Tier-2) · check_* · hooks    + @import of the one agents doc (compiles it in)
```

**No runtime reference chains.** A command does not say "read the rules and obey"; it carries the specific inlined
decision (tagged `[canonical: pack §X]` for provenance), and the review re-fetches the pack to verify. Rules stay DRY
and canonical; commands stay self-sufficient; drift is caught by the review re-fetch, not hoped away.

---

## AGENTS.md resolution — **approved: option (b) collapse + `@import`**

Grounding G2: **Claude Code reads `CLAUDE.md`, not `AGENTS.md`** (verbatim). `AGENTS.md` reaches Claude only via an
`@AGENTS.md` import or symlink. Current state: `AGENTS.md` ≈ `agents-fabrik.md` are 72 KB near-duplicates (42 differing
lines), and both restate rule-pack facts (`postgres-main` 9×, etc.).

**Decision:** collapse to **one** agents doc (`agents-fabrik.md`, which the commands already cite), **strip every
rule-restatement to a tagged one-liner** (keep only live platform facts the rules don't carry), then **`@import` it
into `CLAUDE.md`** so it is compiled into the one auto-loaded file. Result: DRY *and* guaranteed-in-context — the
Claude-Code-native mechanism the vendor docs endorse. `AGENTS.md`'s "always-read planner context" role is retired.

⚠️ **Load-cost is real (G2):** the cited memory doc states `@path` imports *"load in full into context"* and
*"don't reduce context"* — so `@import` grows the always-loaded window by the agents doc's **full size**. The
"`CLAUDE.md` stays small" constraint is therefore met by **content-stripping the agents doc to genuinely small**
(live platform facts only, rule-restatements removed), **not** by the import mechanism. If the stripped doc is still
large, it does NOT belong in the auto-load — split the rarely-needed part into a `Reads:`-fetched reference and keep
only the high-frequency facts imported. The import is depth-capped (per the same doc), so recursion is bounded (U1).

---

## External grounding (best-practice — cited, fetched 2026-07-18)

| # | Grounded claim | Source (URL · fetched 2026-07-18) |
|---|---|---|
| G1 | Referenced/on-demand docs aren't reliably read+obeyed; even loaded context is "no guarantee of strict compliance"; must-run → hooks/enforcement, not prose | Claude Code memory — https://code.claude.com/docs/en/memory |
| G2 | "Claude Code reads `CLAUDE.md`, not `AGENTS.md`"; bridge via `@AGENTS.md`/symlink. AGENTS.md not universally auto-loaded | https://code.claude.com/docs/en/memory · https://agents.md/ |
| G3 | Context engineering = compile high-signal governance up-front; CLAUDE.md "naively dropped into context up front" vs just-in-time retrieval for bulk; Skills compile rules at build time (progressive disclosure) | Anthropic — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents · https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills |
| G4 | Separate evaluator (not self-attestation) is the canonical pattern — "effective when we have clear evaluation criteria"; "circular when the evaluator cannot reliably tell good output from bad" | Anthropic — https://www.anthropic.com/research/building-effective-agents |
| G5 | A production multi-turn agent study measured LLM-judge defect recall at "**one in five**" (≈20%; per-batch **0–22%**), root-caused to a **rubric missing whole categories** → fix = inject state/diffs + an expanded rubric wired to the gate. ⚠️ **Domain caveat:** the study is a *transaction agent* (food-ordering), not code/design review — we borrow the **root-cause + fix**, not a code-review recall number. | arXiv 2606.10315 — https://arxiv.org/abs/2606.10315 |
| G6 | Locking a **discrete, evidence-grounded rubric** improves judge reliability (ablation-confirmed) over raw-rubric/general-knowledge scoring — "fixed criteria, traceable evidence." ⚠️ **Domain caveat:** essay-scoring/summarization; directional for code review, not proven there. | arXiv 2601.08654 — https://arxiv.org/html/2601.08654 |
| G7 | Iterate to a fixed-point/no-op with a **refute step + oscillation guard**; a single pass is insufficient, and refinement can *introduce* new defects a correctness test won't catch | Anthropic evaluator-optimizer (G4) · SlopCodeBench arXiv:2603.24755 (refinement-degradation) |

**Grounding caveats (honest — these bound how far the design's claims can lean):**
- G5/G6 are **out-of-domain** (transaction-agent / essay-scoring) — we adopt their *mechanism* (inject a rubric that covers the violation classes), **not** a code-review recall figure. No cited study measures LLM-judge recall on *code-review rule violations* specifically.
- G7 carries **no citable round-count** — the earlier "3–8 rounds" was research-theater and is removed. What is grounded: iterate-don't-single-pass, and refinement can regress (SlopCodeBench).
- The exact A/B "inline-obeyed vs told-to-read-and-ignored" is *inferred* from G1/G3 primary docs, not a single controlled study.

---

## Internal-capability verdict (vendor→enhance→build)

| Capability the design needs | Verdict | Detail |
|---|---|---|
| Pick applicable rule packs for injection | **VENDOR** | `scripts/select_rules.py` exists — parses each pack's `globs`+`description` frontmatter, prints ACTIVE/AVAILABLE. Ready. |
| Mechanical gate (Tier 1) | **VENDOR** | `scripts/final_gate.py` (Tier-1/2/3), `epic_order.py`, `check_*` suite, `scaffold.py`. Ready. |
| Diverse-model finder breadth + cost control (Tier 3) | **VENDOR** | `/opt/fabrik-lib/subagents/` (cross-repo) — `fanout` + `set_quality` defined in `subagents/agent.py`. Verified present 2026-07-18. Vendored into projects as `libs/subagents`. |
| Converge-to-no-op review loops | **VENDOR** | `/fabrik-review` + `/fabrik-workflow-review` already implement the termination contract. |
| **Rule-excerpt + checklist-rubric INJECTION into the review finders** | **ENHANCE** | `/fabrik-review` already inlines *static* hunt-lists (12-Factor table, test-quality checklist) and *tells the reviewer to read* `.windsurf/rules` as binding context — so this is a **behavioral migration**, not from-scratch. The missing wire: a step that runs `select_rules.py` → **reads the matched packs' bodies** to extract their mandates + the relevant `EVALUATION_CHECKLIST` items → injects them as the *dynamic* finder rubric (G5/G6). ⚠️ Corrected 2026-07-18: `select_rules` *is referenced* (e.g. `/fabrik-review`'s synced-file list) but **no review command injects its output into the finders**, and `select_rules` only emits *which packs to read* — the injection step must additionally parse pack bodies. Command-authoring change (+ a small body-extractor); no new module. |
| Compile the agents doc into the one auto-loaded file | **CONFIGURE** | `@import` in `CLAUDE.md` (G2). |

No `🆕 fabrik-lib candidate`: the injection wiring is command-local, not a generic reusable module.

---

## Shape / infra implications

**N/A** — this design produces/changes **documentation, command/skill files, and small edits to existing scripts**.
No new deployed service, no scaffold, no `shape:` flags, no `fabrik apply`. It has no runtime footprint of its own; it
governs how *other* projects are built.

---

## Constraints (binding on any implementation of this design)

- **No 5th source of truth.** Every fact has exactly one canonical home; commands inline *decisions* (tagged), reviews
  *fetch* rules — neither copies a whole document.
- **No runtime dependency on reading a governance doc** — if a constraint is load-bearing, it must be Tier-1 (gate),
  Tier-2 (inlined/compiled), or Tier-3 (review-injected).
- **The two human gates are preserved** (decomposition-in, `fabrik apply`-out).
- **`CLAUDE.md` stays small** — it is the one auto-loaded file; it holds hard-stops + the gate contract + `@import` +
  pointers, not the full discipline (that's the packs, fetched at review time). ⚠️ Because `@import` loads the target
  **in full** (G2), "small" is achieved by **content-stripping the imported agents doc** (§ AGENTS.md resolution), not
  by the import mechanism — an import of a large doc is not small.
- **Secrets never inlined** into any command/plan/prompt; live data reaches a command via a mechanical step, not a
  "read the secrets file" instruction.

---

## Rejected alternatives (+ why)

1. **Rely on `AGENTS.md` as ambient always-read context** — REJECTED: Claude Code doesn't auto-read it (G2), and even
   auto-loaded context isn't reliably obeyed (G1).
2. **Inline every rule into every command** — REJECTED: bloat + drift (a fact copied into 12 commands rots in 11); the
   opposite failure of #1.
3. **`Reads:`-header referencing as the reliability mechanism** — REJECTED: referenced docs are "on demand," not
   guaranteed read+obeyed (G1). Demoted to a design-time authoring aid.
4. **Generator self-attests rule compliance** — REJECTED: measured judge recall "one in five" (≈20%, G5); self-review shares the doer's
   blind spots.
5. **Single review pass** — REJECTED: insufficient recall; needs converge-to-no-op + refute + oscillation guard (G7).
6. **Unarmed reviewer (general knowledge, no injected rubric)** — REJECTED: ~0–22% recall; the rubric must be injected
   and must cover the violation classes (G5/G6).

---

## Open / blocking unknowns (each with a resolution step)

- **U1 — `@import` behaviour (mostly resolved from grounding).** G2 confirms `@import` loads the target **in full** and
  is **depth-capped** (recursion is bounded) — so the only genuinely open item is confirming it loads as expected in
  *this* Claude Code version, and that the stripped agents doc is small enough to belong in the auto-load (per §
  Constraints). → **Resolve:** one scratch-`CLAUDE.md` smoke test before the real edit. *(Not blocking the spec.)*
- **U2 — injection format.** The exact shape of "select_rules output + checklist items → finder prompt rubric" is a
  design detail. → **Resolve:** prototype in ONE review command (`/fabrik-review`), review quality, then replicate.
- **U3 — `service_catalog.json` status.** Created by the fabrik-AI; owner hasn't fully endorsed it as canonical. →
  **Resolve:** owner decision (keep as the mechanical inventory source, or replace).

Not "zero unknowns."

---

## Implementation surface (for `/fabrik-plan-after-chat`, NOT this spec)

The design, once approved+converged, is realized by: (1) bake the governing law into the north-star; (2) collapse the
two agents docs → one, strip rule-restatements, `@import` into a slimmed `CLAUDE.md` bootstrap; (3) wire
`select_rules` + checklist-rubric injection into `/fabrik-review` + mega-`04` + ettw-`08`/`10`; (4) the pending ettw
producer pass (00–06) and the `service_catalog.json` mechanical step in `00-trigger` inherit this model. Sequencing and
grounding are the plan's job.
