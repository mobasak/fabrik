<!-- ⛔ RETIRED 2026-09-05 — ettw 01R-decisions-review is no longer a command.
     Replaced by `/fabrik-spec` + `/fabrik-spec-review` (spec § Chain consolidation (a)). Kept for history only. Do NOT wire it back as a command. -->
<!-- ⚠️ FABRIK FACTORY WORKFLOW — DECISIONS REVIEW (the convergence twin of 01-decisions-lock)
     Run DIRECTLY by our orchestrator agent (Claude Code CLI — bare terminal, or inside a Traycer session
     with Claude Code as the backend) — never pasted into a planner GUI.
     TOOL-CAPABLE: it READS the DRAFT decisions artifact from disk, re-verifies every claim adversarially
     (live web for external facts, the epic file / chat INFRA-CHECK for consistency), loops to an
     md5-verified no-op — then STOPS for the operator, whose explicit confirm flips DRAFT → LOCKED.
     ⚠️ THIS COMMAND ENDS AT GATE 1. It is to `01-decisions-lock` what `/fabrik-spec-review` is to
     `/fabrik-spec` — same termination contract, same anti-cheat, same human gate at the end.

     Reads:
       · the DRAFT artifact — `docs/superpowers/specs/YYYY-MM-DD-<slug>-decisions.md` (the review target)
       · Path B: the dispatched epic file — `docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md`
       · the research file `00` consumed — `docs/preplans/*.md` / `docs/development/plans/00-research.md`
       · `fabrik-lib/README.md` (module table — to audit backing-service/vendor decisions)
     -->

<!-- ⚠️ QUALITY GATE: any modification MUST pass EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md
     (every applicable item — N/A is valid; forgetting to check is not). -->

# Decisions Review (converge the DRAFT to a no-op → the operator's confirm LOCKS it — Gate 1)

## ⚠️ Termination contract — READ FIRST (the rule agents skip)

This is a LOOP, not a one-shot. It ends — and the artifact may be presented for locking — **only when a
full, demonstrably-thorough grounding round makes ZERO edits to the artifact** (a genuine no-op pass).
The failure this exists to stop: ground once → fix what you found → declare "converged." That is NOT
converged — fixes open new gaps, so **the pass in which you edited is NEVER the last pass**. **Minimum two passes, ALWAYS** —
even an edit-free pass 1 must be confirmed by an independent pass 2; accuracy outranks pass-count.
The final pass must also have **raised zero candidates** (refuted counts as raised — log them; a pass that
raised anything owes the next pass). **There is NO pass ceiling** — an axis stuck after 3 consecutive
reconcile attempts is BLOCKED-escalated to the operator (named, with the 3 attempts) while the rest converges;
never a self-declared "accepted risk".

**Anti-cheat (mechanical, not vibes):** record the artifact's `md5sum` at the start and end of the final
pass. Identical hash = a real no-op. A no-op asserted without matching hashes does not count. Maintain a
numbered **Pass Ledger** (pass · axes · edits · md5 start→end) and reproduce it verbatim in your report;
you are done only when the last row reads `edits: 0` with `md5(start) == md5(end)`.

**The WHOLE loop runs inside THIS ONE invocation** — never stop after an intermediate pass to be
re-invoked. You return control EXACTLY ONCE: at the operator gate below.

## Phase 1 — Adversarial grounding passes (fan-out per axis)

Treat every claim in the DRAFT as unproven. Each pass covers ALL five axes; fix what survives refutation,
then run the next full pass:

- **A) External facts** — re-fetch every cited source LIVE this session (exa → WebSearch/WebFetch → brave
  → firecrawl → context7/github). Dead URL, citation that doesn't support the claim, stale figure, or an
  external claim with NO cited source (memory) = defect. Freshness binds: a citation not re-opened this
  run is unverified.
- **B) INFRA-CHECK + Metadata consistency** — every field matches what `00` emitted (Path A) or the epic
  file declares (Path B); none silently dropped (Path A 10+3 · Path B 16); the `Decisions` table
  contradicts none of them; backing services exist in `fabrik-lib`/VPS inventory (open the module table —
  don't trust the DRAFT's claim).
- **C) Success-criteria quality** — flavour-correct count (Delta 5–8 · Retrofit 3–5); each a number or
  binary state; ≥1 deploy/gate-level criterion present; parallel-decomposable; zero aspirations, zero
  implementation detail.
- **D) Completeness + consistency** — every skeleton section present and non-silent; `Status: DRAFT`
  intact (a pre-locked artifact is a defect — locking is the operator's, below); no placeholders
  (`TBD`/"handle appropriately"); no internal contradictions (Goal vs Out-of-Scope vs Decisions);
  Open/BLOCKED items each carry a named resolution step.
- **E) Hard constraints** — no decision violates a Fabrik hard constraint (Stripe / managed vector DB /
  direct vendor LLM SDK / Supabase-as-new-default / Alpine / host `ports:` / `localhost` DB host), and the
  design-shaping 12-Factor rows hold. A well-cited choice that trips a constraint is CUT, not footnoted.

**Dispatch policy (per `core/62-using-subagents.md` — BOTH layers, never either/or):** the gradeable
grounding fan-out runs as pool `fanout("review"/"research", …, mode="read_only")` units (auto-recorded;
back-fill each verdict with `set_quality`) **plus ≥1 native `fabrik-researcher` on Opus** as the
authoritative citation-verify pass. You (Opus) own merge / refute / decide-clean and the md5 verdict.
Refute with quotes — a candidate you can disprove from the artifact's own text or a live source dies
there; report only survivors, fix only what survives.

## Phase 2 — The lock (Path A: the operator gate · Path B: auto-lock)

**Path B (epic-fed, BIG flow): auto-lock on the no-op.** The project's intent was already
operator-locked at the mega `00` Vision confirm; per-epic runs are hands-off by design. On the
md5-verified no-op round, flip `Status: LOCKED <date>` yourself, re-mirror with `--status 2`, and continue
the route — the operator may pause/rework any time, but is never *required* here.

**Path A (project entry, SMALL flow): this IS Gate 1** — the only human step between here and
`11-deploy`. Once the md5-verified no-op round is reached:

1. **Present** — the artifact path, a one-screen digest (Goal · the Decisions table · Success Criteria ·
   Out of Scope · anything Open/BLOCKED), the full Pass Ledger, and what hardened across passes.
2. **STOP and ask the operator to confirm the lock.** Silence ≠ confirmation. Do NOT auto-chain.
3. **On explicit confirm:** flip the header line to **`Status: LOCKED <YYYY-MM-DD>`** — this line is the
   machine-readable Gate-1 marker downstream automation (the driver's stage predicate) greps — and
   re-mirror the Traycer artifact as done:

   ```bash
   python /opt/fabrik/scripts/traycer_mirror.py \
          --src docs/superpowers/specs/YYYY-MM-DD-<slug>-decisions.md \
          --name decisions --kind spec --title "Decisions Lock — <slug>" --status 2 --embed
   ```

4. **On requested changes:** apply them to the DRAFT and **re-open the loop** (back to Phase 1 — a full
   grounding pass, not a spot-fix). Never lock an unconverged artifact; never converge past an unresolved
   operator objection.

After `LOCKED`, name the next command from the artifact's `## Route` (GUI scaffolds →
`02-core-flows-fabrik`; headless → `03-tech-plan-fabrik`) — the chain from here to `11-deploy`'s
deploy-prep runs without the operator.

## Does NOT

- Create the artifact — that is `01-decisions-lock-fabrik` (a missing artifact routes back there).
- Re-run `00`'s checks — consistency is audited against `00`'s output, not re-derived.
- Lock without the operator's explicit confirm, or edit the artifact after `LOCKED` (post-lock changes are
  `09-revise-requirements-fabrik`'s job).
- Design flows / tech / tickets — downstream commands.

## Acceptance Criteria

- Pass Ledger reproduced verbatim; last row `edits: 0` with matching md5 hashes.
- Every cited external source re-opened THIS run; every refutation quotes its disproof.
- Pool fan-out recorded + `set_quality`-scored AND ≥1 native Opus pass ran (never pool-only, never
  Opus-only).
- The operator explicitly confirmed (or explicitly sent changes → loop re-opened). Silence ≠ confirmation.
- On confirm: `Status: LOCKED <date>` written; Traycer mirror re-run with `--status 2`; next command named
  from `## Route`.

---

**Next (after LOCK):** the route recorded in the artifact — `02-core-flows-fabrik` (GUI) or
`03-tech-plan-fabrik` (headless). From this point the operator is not needed until `11-deploy` parks
`ready-for-operator`.
