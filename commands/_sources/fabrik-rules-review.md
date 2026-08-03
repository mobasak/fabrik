---
description: Read-only .windsurf/rules compliance gap audit — establish real stack + spec flags + ADR, fan out one subagent per applicable pack (parallel), refute false gaps, iterate until a full pass surfaces nothing new (stable gap list), prioritized GAP table with path:line proof
argument-hint: "[a specific pack or rules subdir to scope — omit to audit all applicable packs]"
---

Run a `.windsurf/rules` COMPLIANCE GAP AUDIT for this project. **READ-ONLY — do NOT modify code,
config, docs, or the rules; produce an audit only.** And do NOT stop after one pass: **iterate the
audit until it converges** (Phase 4) — a pass whose gap list is identical to the prior pass (a no-op
on the finding set) is the only proof the audit is complete. Propose nothing as fixed/done until I
say so.

### ⚠️ Scope note — this command is the HUB exception

The rule packs ARE this command's target, so the "synced files are read-only" rule that binds
`/fabrik-review` and `/fabrik-docs-review` **does not apply here** — but it does mean **this command only
runs in the HUB** (`/opt/fabrik`). Confirm with `git rev-parse --show-toplevel`.

**If you are in a PROJECT: STOP.** `.windsurf/rules/**` is a read-only synced copy there (gate:
`check_synced_unmodified.py`); editing it is a Tier-1 violation and the next sync overwrites it anyway. Take
the finding upstream to `/opt/fabrik` instead.

**In the hub, review these HARDER than product code** — they are the widest blast radius in the system
(every rule pack + every enforcement check (count them live) → every project on the next sync):

- Does a rule **contradict another pack**? (a pack that fights another is worse than no pack)
- Would it **break a project that lacks feature X**? Is it backward-compatible?
- Does it **false-positive on a legitimate, mandated pattern**? (e.g. banning "daemonize" must not condemn
  `tini` as PID 1 or the Adaptive Worker Pool's forked children; banning SQLite must not condemn
  `desktop-app`'s mandated SQLCipher store). A rule that cries wolf gets ignored — that is how a rule dies.
- **Does the rule's `globs:` actually fire where the violation is written?** A perfectly-worded rule in a pack
  whose glob never matches the offending file is **theatre**. Verify against `scripts/select_rules.py`.

{{include:grounding-artifact}}
- Verify globs via `scripts/select_rules.py` — a plausible-looking glob is not proof it matches.

## Phase 0 — Ground truth (never trust labels)

1. **Establish the real stack.** Read `project.yaml::type`, then CONFIRM by grep (`package.json` vs
   `requirements.txt`/`pyproject.toml`, lockfiles) + the real entrypoint. Labels lie; the code is truth.
2. **Read the spec shape flags** in `specs/services/<id>.yaml` (e.g. `is_public` / `is_admin_dashboard` /
   `has_bearer_api` / `needs_database` / `needs_cache` / `has_persistent_data` / `has_search_feature` /
   `exposes_metrics`). These decide which features are INTENTIONALLY on/off — a feature that's off because
   its flag is false is spec-consistent, not a gap.
3. **Read the project's ADR / architecture-decisions doc FIRST** (e.g.
   `docs/reference/architecture-decisions.md`). The packs assume a particular stack (language, framework,
   DB, migration tool, id scheme); wherever the ADR records this project deliberately differs, that
   mismatch is an ADR-accepted deliberate decision, NOT a gap — and the same holds for ANY deviation the ADR
   accepts (stack-shaped or not: a decided no-audit-log, no-/metrics, single-tenant). Capture the accepted-deviation list before
   auditing anything.
4. If an argument was given, scope the audit to it: `$ARGUMENTS` (a specific pack or rules subdir).
   Otherwise audit all applicable packs.

## Phase 1 — Which packs apply

List `.windsurf/rules/**/*.md` (core + any subdir packs matching this scaffold). For each, read its
frontmatter `globs:` and any "Per-Scaffold Applicability / Observability Matrix" to decide if it applies to
THIS scaffold + stack. SKIP non-applicable packs (e.g. mobile / chrome / docusaurus / file-api /
gpu-workers / rag / payments / email) unless the code actually uses them. STATE which you skipped and why.

## Phase 2 — Audit each applicable pack (parallel fan-out, enforced)

The packs are independent, so this step MUST fan out: spawn one INDEPENDENT subagent per applicable pack,
run them in parallel (batch them; don't serialize), and have each return its findings for merge. (Only loop
solo if ≤2 packs apply.) Each per-pack subagent:

- Extracts that pack's "Done When" / requirements / Banned Patterns.
- For EACH requirement, VERIFIES against real code with a `path:line` citation — never assert from memory;
  a file/column NAME ≠ its behavior (read it). Run greps/queries where needed.
- Classifies each item:
  - ✅ COMPLIANT — with `path:line` proof.
  - 🟡 DEVIATION — deliberate + ADR-accepted (cite the ADR line); NOT a gap.
  - ❌ GAP — applicable + not met. Note (a) spec-consistency (e.g. no `/metrics` because
    `exposes_metrics:false` → not a gap), (b) severity, (c) where it's already tracked (the project's
    resilience/backlog/plan docs, e.g. `RESILIENCE.md`, `STRATEGIC_BACKLOG.md`, `docs/development/plans/*`).

Give each subagent ONLY its pack + the Phase-0 ground truth (stack, spec flags, accepted deviations) so its
verdicts are grounded, not guessed.

## Phase 3 — Merge + refute (kill false gaps)

Merge and dedupe all per-pack findings. Then adversarially try to REFUTE every ❌ GAP before it reaches the
table: is it actually ADR-accepted (cite the ADR line) or spec-consistent-off (cite the shape flag)? If so,
reclassify it as 🟡 DEVIATION. Only gaps that survive this refutation are real. Equally, do not let a
subagent's ✅ COMPLIANT stand without its `path:line` proof.

## Phase 4 — Iterate to a stable audit (no-op pass), then output

**Do not stop after one pass.** Re-run the fan-out + merge/refute (Phases 2–3) until a full,
demonstrably-thorough pass is a **no-op on the finding set**: it surfaces no NEW gap and
refutes/reclassifies none further — the gap list is unchanged from the prior pass. The pass in which the
list *changed* is never the last; run one more, and if anything is added, removed, or reclassified, keep
going. A single pass, or "I think I caught them all," is not convergence — the stable (identical-to-prior)
pass is. This converges the AUDIT to completeness; it does **not** fix the gaps (fixing is a separate,
user-authorized step).

**Run that next pass UNPROMPTED — the moment a pass adds/removes/reclassifies anything you owe it,
automatically.** Never wait to be asked *"did the audit stabilize?"*; the obligation is yours and predates any
challenge — reframing your own skipped rule as a *"fair challenge"* you then conceded to is itself the dodge.
Three thoughts that each mean **run the next pass now**: *"I already audited that pack,"* *"only one item
moved,"* *"it's obviously stable."* Only the identical-to-prior pass is convergence.

Then output:

1. A prioritized **GAP table**: `pack | requirement | status | evidence (path:line) | already-tracked?`
2. A short **"Deliberate deviations (not gaps)"** list (each with its ADR/spec citation).
3. A **"Compliant"** one-line summary per pack.
4. **Honesty rules:** don't claim full compliance without embedded proof; don't invent gaps; mark
   volatile/uncertain items as such; new/unverifiable behavior gets a residual-risk note.
5. End with: which gaps are real TODOs vs deliberate, and which to fold into the active plan
   (`docs/development/plans/*`) — but do NOT edit anything unless I say so.

{{include:subagents-core}}
