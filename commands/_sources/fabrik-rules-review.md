---
description: Read-only .windsurf/rules compliance POSTURE audit — the full-coverage complement to /fabrik-review's per-diff rubric floor: establish real stack + spec shape flags + ADR, fan out one pool finder per applicable pack (parallel, flywheel-recorded), refute false gaps, iterate to a stable gap list, prioritized GAP table with path:line proof. Runs in a PROJECT (audit the project against its synced packs) or in the HUB (audit the packs themselves — blast-radius mode). TRIGGER — EN: "check rules-pack compliance", "audit against the windsurf rule packs"; TR: "kural paketlerine uyumu denetle", "windsurf kurallarını kontrol et" — fires for a PACK-compliance gap audit, not a defect review. SKIP: code-defect finding (→ /fabrik-review, /fabrik-repo-review); a single diff's rules floor (→ /fabrik-review's injected rubric). Stage: gate.
argument-hint: "[a specific pack or rules subdir to scope — omit to audit all applicable packs]"
---

Run a `.windsurf/rules` COMPLIANCE GAP AUDIT. **READ-ONLY — do NOT modify code, config, docs, or the
rules; produce an audit only.** And do NOT stop after one pass: **iterate the audit until it
converges** (Phase 4) — a pass whose gap list is identical to the prior pass (a no-op on the finding
set) is the only proof the audit is complete. Propose nothing as fixed/done until I say so.
**Context is never a reason to stop:** the harness auto-compacts and the run continues — keep going.

**Where this sits vs `/fabrik-review`:** every `/fabrik-review` already injects the rules floor into
its finders (`scripts/review_rubric.py --changed <paths>`) — that covers the CHANGED DIFF. This
command is the **whole-surface posture audit**: every requirement of every applicable pack against
the whole project, invoked deliberately (pre-release, post-adoption of a new pack, or when
compliance drift is suspected) — not per-commit.

### Two modes — detect which repo you are in (`git rev-parse --show-toplevel`)

- **PROJECT mode** (any `/opt/<project>` with a `project.yaml`): audit THIS project's code against
  its synced packs. The packs are a **read-only synced copy** here (gate:
  `check_synced_unmodified.py`) — never edit them locally; a defect IN a pack (contradiction,
  false-positive, dead glob) discovered mid-audit is recorded as a finding and filed upstream via
  `/fabrik-upstream`, never fixed in place.
- **HUB mode** (`/opt/fabrik`): the packs THEMSELVES are the audited surface — there is no
  `project.yaml` here (the hub is the platform, not a scaffold type), so Phase 0's stack/spec steps
  are N/A and the audit runs the blast-radius checklist below across the pack corpus (optionally
  scoped by `$ARGUMENTS`). Review packs **harder than product code** — widest blast radius in the
  system (every pack + every enforcement check → every project on the next sync):
  - Does a rule **contradict another pack**? (a pack that fights another is worse than no pack)
  - Would it **break a project that lacks feature X**? Is it backward-compatible?
  - Does it **false-positive on a legitimate, mandated pattern**? (e.g. banning "daemonize" must not
    condemn `tini` as PID 1; banning SQLite must not condemn `desktop-app`'s mandated SQLCipher
    store). A rule that cries wolf gets ignored — that is how a rule dies.
  - **Does the rule's `globs:` actually fire where the violation is written?** A perfectly-worded
    rule in a pack whose glob never matches the offending file is **theatre**. Verify against
    `python scripts/select_rules.py`.

{{include:run-record}}
{{include:grounding-artifact}}
- Verify globs via `python scripts/select_rules.py` — a plausible-looking glob is not proof it matches.

## Phase 0 — Ground truth (never trust labels; PROJECT mode — in HUB mode only step 4 applies)

1. **Establish the real stack.** Read `project.yaml::type`, then CONFIRM by grep (`package.json` vs
   `requirements.txt`/`pyproject.toml`, lockfiles) + the real entrypoint. Labels lie; the code is truth.
2. **Read the spec shape flags** in `specs/services/<id>.yaml` (the live registry is
   `spec_loader.py::Shape` — e.g. `is_public` / `is_admin_dashboard` / `has_bearer_api` /
   `needs_database` / `needs_cache` / `has_persistent_data` / `has_search_feature` /
   `exposes_metrics`). These decide which features are INTENTIONALLY on/off — a feature that's off
   because its flag is false is spec-consistent, not a gap.
3. **Read the project's ADR / architecture-decisions doc FIRST** (e.g.
   `docs/reference/architecture-decisions.md`). The packs assume a particular stack (language,
   framework, DB, migration tool, id scheme); wherever the ADR records this project deliberately
   differs, that mismatch is an ADR-accepted deliberate decision, NOT a gap — and the same holds for
   ANY deviation the ADR accepts (stack-shaped or not: a decided no-audit-log, no-`/metrics`,
   single-tenant). Capture the accepted-deviation list before auditing anything.
4. If an argument was given, scope the audit to it: `$ARGUMENTS` (a specific pack or rules subdir).
   Otherwise audit all applicable packs.

## Phase 1 — Which packs apply

List `.windsurf/rules/**/*.md` (core + any subdir packs matching this scaffold). For each, read its
frontmatter `globs:` and any "Per-Scaffold Applicability / Observability Matrix" to decide if it
applies to THIS scaffold + stack. SKIP non-applicable packs (e.g. mobile / chrome / docusaurus /
file-api / gpu-workers / rag / payments / email) unless the code actually uses them. STATE which you
skipped and why. (HUB mode: every pack is in scope unless `$ARGUMENTS` narrows it.)

## Phase 2 — Audit each applicable pack (parallel pool fan-out, flywheel-recorded)

The packs are independent, so this step MUST fan out — **pool-default per the dispatch policy**: one
unit per applicable pack via `fanout("review", units, repo=REPO, project=<project>,
mode="read_only")`, with `set_quality` back-fill after Phase 3 adjudication. Add a **native**
finder on top for any pack whose subject is authoritative/high-risk (auth, schema, migrations,
secrets, concurrency — the same reservation every review command uses); a 1–2-pack audit still
dispatches through `fanout` (it records to the flywheel either way).

**Division of labor — read_only units cannot touch the filesystem, so build their prompts
accordingly:** each unit's prompt inlines its pack's text + the Phase-0 ground truth + the
RELEVANT CODE EXCERPTS you (the orchestrator) select for that pack's subject (grep-driven —
config files, the entrypoint, the modules the pack governs). The unit then:

- Extracts that pack's "Done When" / requirements / Banned Patterns.
- For EACH requirement, judges it against the inlined excerpts and cites `path:line` from them —
  and **explicitly flags any requirement its excerpts cannot decide** (`UNVERIFIABLE-FROM-EXCERPTS`)
  instead of guessing. YOU verify every flagged item AND every cited `path:line` yourself with
  real tools in Phase 3 — exhaustively, not a sample; a finder verdict on code it never saw is
  not evidence, and a fabricated citation survives exactly as long as nobody opens it.
- Classifies each item:
  - ✅ COMPLIANT — with `path:line` proof.
  - 🟡 DEVIATION — deliberate + ADR-accepted (cite the ADR line); NOT a gap.
  - ❌ GAP — applicable + not met. Note (a) spec-consistency (e.g. no `/metrics` because
    `exposes_metrics:false` → not a gap), (b) severity, (c) where it's already tracked (the
    project's resilience/backlog/plan docs, e.g. `RESILIENCE.md`, `STRATEGIC_BACKLOG.md`,
    `docs/development/plans/*`).

Give each finder ONLY its pack + the Phase-0 ground truth (stack, spec flags, accepted
deviations) + its selected excerpts — nothing else, so its verdicts are grounded, not guessed.

**HUB mode:** the per-pack unit's requirement list IS the blast-radius checklist from the mode
section (contradiction with sibling packs, backward-compatibility, false-positive risk on
mandated patterns, glob reach) — judged against the pack's own text + the sibling packs you
inline + `python scripts/select_rules.py` output, since there is no project code to audit.

## Phase 3 — Merge + refute (kill false gaps)

Merge and dedupe all per-pack findings. Resolve every `UNVERIFIABLE-FROM-EXCERPTS` flag yourself
with real tools (grep/Read) — those items are finder QUESTIONS, never findings. Then adversarially
try to REFUTE every ❌ GAP before it reaches the table: is it actually ADR-accepted (cite the ADR
line) or spec-consistent-off (cite the shape flag)? If so, reclassify it as 🟡 DEVIATION. Only gaps
that survive this refutation are real. Equally, do not let a finder's ✅ COMPLIANT stand without a
`path:line` you spot-checked. Back-fill `set_quality` scores for the pool finders here
(confirmed-gap yield + proof quality).

## Phase 4 — Iterate to a stable audit (no-op pass), then output

**Do not stop after one pass.** Re-run the fan-out + merge/refute (Phases 2–3) until a full,
demonstrably-thorough pass is a **no-op on the finding set**: it surfaces no NEW gap and
refutes/reclassifies none further — the gap list is unchanged from the prior pass. The pass in which
the list *changed* is never the last; run one more, and if anything is added, removed, or
reclassified, keep going. A single pass, or "I think I caught them all," is not convergence — the
stable (identical-to-prior) pass is. This converges the AUDIT to completeness; it does **not** fix
the gaps (fixing is a separate, user-authorized step).

**Run that next pass UNPROMPTED — the moment a pass adds/removes/reclassifies anything you owe it,
automatically.** Never wait to be asked *"did the audit stabilize?"*; the obligation is yours and
predates any challenge — reframing your own skipped rule as a *"fair challenge"* you then conceded
to is itself the dodge. Three thoughts that each mean **run the next pass now**: *"I already audited
that pack,"* *"only one item moved,"* *"it's obviously stable."* Only the identical-to-prior pass is
convergence.

Then output:

1. A prioritized **GAP table**: `pack | requirement | status | evidence (path:line) | already-tracked?`
2. A short **"Deliberate deviations (not gaps)"** list (each with its ADR/spec citation).
3. A **"Compliant"** one-line summary per pack.
4. **Pack-defect findings** (PROJECT mode): anything wrong with a PACK itself → a `/fabrik-upstream`
   proposal, never a local edit.
5. **Honesty rules:** don't claim full compliance without embedded proof; don't invent gaps; mark
   volatile/uncertain items as such; new/unverifiable behavior gets a residual-risk note.
6. End with: which gaps are real TODOs vs deliberate, and which to fold into the active plan
   (`docs/development/plans/*`) — but do NOT edit anything unless I say so.

{{include:subagents-core}}
