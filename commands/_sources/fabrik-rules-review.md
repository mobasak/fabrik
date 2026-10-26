---
description: Read-only .windsurf/rules compliance POSTURE audit — the whole-surface full-coverage complement to /fabrik-review's per-diff rubric floor: establish real stack + spec shape flags + ADR, fan out one native finder per applicable pack (parallel), refute false gaps, iterate to a stable gap list, prioritized GAP table with path:line proof. Runs in a PROJECT (audit it against its synced packs) or the HUB (audit the packs themselves — blast-radius mode). TRIGGER — EN: "check rules-pack compliance", "audit against the windsurf rule packs"; TR: "kural paketlerine uyumu denetle", "windsurf kurallarını kontrol et" — fires for a PACK-compliance gap audit, not a defect review. SKIP: code-defect finding (→ /fabrik-review, /fabrik-repo-review); one diff's rules floor (→ /fabrik-review's injected rubric). Stage: gate.
argument-hint: "[a specific pack or rules subdir to scope — omit to audit all applicable packs]"
---

> **⚠️ POOL OFF — D-181 (operator, 2026-09-07; mechanism revised by D-182).** Every `fanout` / `pick_models` / `set_quality` / `record_agent_run` / `results_table` instruction is SUSPENDED (left in place, or in `<!-- POOL OFF -->` comments, for re-enable): run every fan-out NATIVELY with Claude Task subagents (`fabrik-reviewer` · `fabrik-researcher` · `fabrik-gui` · general-purpose) — same unit split, same author-blind rule, same decide/refute/merge by you — and skip every flywheel back-fill (a native seat records nothing). Never write `NO-POOL:` for it: `check_subagent_flywheel.py`'s pool-or-declare layer stands down by the same ruling (`_POOL_POLICY_ON = False`, D-182). Canonical: `62-using-subagents.md` § Dispatch policy.

Run a `.windsurf/rules` COMPLIANCE GAP AUDIT. **READ-ONLY — do NOT modify code, config, docs, or the
rules; produce an audit only.** The Termination contract's closing round (Phase 4) is the only proof the audit is complete. Propose nothing as fixed/done until I say so.
**Context is never a reason to stop:** the harness auto-compacts and the run continues — keep going.

Every `/fabrik-review` already injects the rules floor into its finders (`scripts/review_rubric.py --changed <paths>`) — that covers the CHANGED DIFF; this is the **whole-surface posture audit**: every requirement of every applicable pack against the whole project, invoked deliberately (pre-release, after adopting a pack, on suspected drift) — not per-commit.

### Two modes — detect which repo you are in (`git rev-parse --show-toplevel`)

- **PROJECT mode** (any `/opt/<project>` with a `project.yaml`): audit THIS project against its synced packs, a **read-only synced copy** (gate: `check_synced_unmodified.py`) — never edit them locally; a defect IN a pack (contradiction, false-positive, dead glob) discovered mid-audit is recorded as a finding and filed upstream via `/fabrik-upstream`, never fixed in place.
- **HUB mode** (`/opt/fabrik`): the packs THEMSELVES are the audited surface — there is no `project.yaml` here; run this blast-radius checklist across the corpus (optionally scoped by `$ARGUMENTS`), **harder than product code** — widest blast radius in the system (every pack + every enforcement check → every project on the next sync):
  - Does a rule **contradict another pack**?
  - Would it **break a project that lacks feature X**? Is it backward-compatible?
  - Does it **false-positive on a legitimate, mandated pattern** (banning "daemonize" must not condemn `tini` as PID 1, nor SQLite `desktop-app`'s mandated SQLCipher store)?
  - **Does the rule's `globs:` actually fire where the violation is written?** A glob that never matches the offending file is **theatre**.

{{include:run-record}}
{{include:orient}}
{{include:term-edit}}
{{include:grounding-artifact}}
- Verify globs via `python scripts/select_rules.py` — a plausible-looking glob is not proof it matches.

## Phase 0 — Ground truth (never trust labels; PROJECT mode — in HUB mode steps 1–2 are N/A, steps 3–4 apply: the hub's own ledger + ADR record accepted deviations too)

1. **Establish the real stack:** read `project.yaml::type`, CONFIRM by grep (`package.json` vs `requirements.txt`/`pyproject.toml`, lockfiles) + the real entrypoint; Labels lie; the code is truth.
2. **Read the spec shape flags** in `specs/services/<id>.yaml` (registry: `spec_loader.py::Shape` — e.g. `is_public` / `is_admin_dashboard` / `has_bearer_api` / `needs_database` / `needs_cache` / `has_persistent_data` / `has_search_feature` / `exposes_metrics`); these decide which features are INTENTIONALLY on/off — a feature off because its flag is false is spec-consistent, not a gap.
3. **Read the project's ADR doc FIRST** (e.g. `docs/reference/architecture-decisions.md`) **AND grep `docs/DECISIONS.md`** — the fleet-wide decision ledger (D-000) is the canonical decisions store, and a deviation accepted by a ledger row is exactly as deliberate as an ADR-accepted one. The packs assume a particular stack (language, framework, DB, migration tool, id scheme); wherever the ADR or a ledger row records this project deliberately differs, that mismatch is an accepted deliberate decision, NOT a gap — and the same holds for ANY deviation either accepts (stack-shaped or not: a decided no-audit-log, no-`/metrics`, single-tenant). Capture the accepted-deviation list before auditing anything.
4. If an argument was given, scope the audit to it: `$ARGUMENTS` (a pack or rules subdir); otherwise audit all applicable packs.

## Phase 1 — Which packs apply

Read each `.windsurf/rules/**/*.md` pack's frontmatter `globs:` and any "Per-Scaffold Applicability / Observability Matrix" to decide if it applies to THIS scaffold + stack. SKIP non-applicable packs unless the code uses them, and STATE which you skipped and why. (HUB mode: every pack is in scope unless `$ARGUMENTS` narrows it.)

## Phase 2 — Audit each applicable pack (parallel native fan-out)

The packs are independent, so this step MUST fan out — sized, stamped and closed at THIS point (`python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --units <packs>` prints the seats, `python3 scripts/command_run.py dispatch --seats <n>` BEFORE they go out, Phase 4's `round --seats <n>` closes; the recipe in § Subagents below is the same one) — one native `fabrik-reviewer` seat (Sonnet) per applicable pack, in parallel; Opus for any pack whose subject is authoritative/high-risk (auth, schema, migrations, secrets, concurrency). The pool form is kept below for re-enable (D-181):
<!-- POOL OFF (D-181, 2026-09-07) — kept verbatim for re-enable:
The packs are independent, so this step MUST fan out — **pool-default per the dispatch policy**: one
unit per applicable pack via `fanout("review", units, repo=REPO, project=<project>,
mode="read_only")`, with `set_quality` back-fill after Phase 3 adjudication. Add a **native**
finder on top for any pack whose subject is authoritative/high-risk (auth, schema, migrations,
secrets, concurrency — the same reservation every review command uses); a 1–2-pack audit still
dispatches through `fanout` (it records to the flywheel either way).
-->

**Give each finder ONLY its pack + the Phase-0 ground truth (stack, spec flags, accepted deviations) + the RELEVANT CODE EXCERPTS you select for that pack's subject (grep-driven — config files, the entrypoint, the modules the pack governs) — nothing else, so its verdicts are grounded, not guessed.** Secrets carve-out (mirrors `/fabrik-repo-review`): never inline secret-material content (`.env` / `.env.*` values — `.env.example` is exempt, it carries names only — `secrets/`, key files) into a POOL unit's excerpts — a pack whose audit needs those files gets the NATIVE finder, and an unavoidable config excerpt is redacted first; secret contents never go to pool APIs. Each finder:

- Extracts the pack's "Done When" / requirements / Banned Patterns and judges EACH against the excerpts, citing `path:line`; it **flags any requirement it cannot decide** (`UNVERIFIABLE-FROM-EXCERPTS`) instead of guessing.
- Classifies each item:
  - ✅ COMPLIANT — with `path:line` proof.
  - 🟡 DEVIATION — deliberate + ADR-accepted (cite the ADR line); NOT a gap.
  - ❌ GAP — applicable + not met, with spec-consistency (e.g. no `/metrics` because `exposes_metrics:false` → not a gap), severity, and where it is already tracked (`RESILIENCE.md`, `STRATEGIC_BACKLOG.md`, `docs/development/plans/*`).

**HUB mode:** the per-pack requirement list IS the blast-radius checklist (contradiction with sibling packs, backward-compatibility, false-positive risk on mandated patterns, glob reach), judged against the pack's text + the sibling packs you inline + `python scripts/select_rules.py` output.

## Phase 3 — Merge + refute (kill false gaps)

Merge and dedupe all per-pack findings. YOU resolve every `UNVERIFIABLE-FROM-EXCERPTS` flag and verify every cited `path:line` with real tools, exhaustively, not a sample — flags are finder QUESTIONS, never findings. Then adversarially try to REFUTE every ❌ GAP before it reaches the table: ADR-accepted (cite the ADR line) or spec-consistent-off (cite the shape flag) reclassifies it as 🟡 DEVIATION; only gaps that survive this refutation are real. Equally, do not let a finder's ✅ COMPLIANT stand without a `path:line` you spot-checked.

## Phase 4 — Iterate to the closing round, then output

**Do not stop after one pass.** Re-run the fan-out + merge/refute (Phases 2–3) until a full pass is the Termination contract's closing round: the round-1 seats, over their own slices, CONFIRMING no NEW gap and reclassifying none — `confirmed: 0`, the gap list's md5 unchanged. A pass that changed the list is never the last; A single pass, or "I think I caught them all," is not convergence — only the identical-to-prior pass is. This converges the AUDIT; it fixes no gap (fixing is a separate, user-authorized step).

**Record each pass:** `python3 scripts/command_run.py round --seats <seats dispatched this pass> --findings <raw gaps raised>
--confirmed <n> --classes-swept <the packs swept> --classes-new <…>` — `--findings` is raw recall; `--confirmed <n>` counts gaps that HELD (NEW or RECLASSIFIED this pass, executed against `path:line`), never the standing gap-table size: a re-listed standing gap is CITED, not counted (D-206), so the closing pass honestly records `--confirmed 0` and the TERMINAL verdict is reachable while real gaps stand. The round ledger is this command's persisted trace: the audit itself is deliberately chat-only (the GAP table lands in the final response; a READ-ONLY command writes no artifact), so a run whose rounds are unrecorded has no evidence it converged.

**Run the next pass UNPROMPTED the moment a pass adds, removes or reclassifies anything** — never wait to be asked *"did the audit stabilize?"*; the obligation is yours and predates any challenge — reframing your own skipped rule as a *"fair challenge"* you then conceded to is itself the dodge. *"I already audited that pack,"* *"only one item moved,"* *"it's obviously stable"* each mean run it now.

Then output:

1. A prioritized **GAP table**: `pack | requirement | status | evidence (path:line) | already-tracked?`
2. A **"Deliberate deviations (not gaps)"** list (each with its ADR/spec citation).
3. A one-line **"Compliant"** summary per pack.
4. **Pack-defect findings** (PROJECT mode): anything wrong with a PACK itself → a `/fabrik-upstream` proposal, never a local edit.
5. **Honesty rules:** no full-compliance claim without embedded proof; don't invent gaps; mark volatile/uncertain items as such; new/unverifiable behavior gets a residual-risk note.
6. End with which gaps are real TODOs vs deliberate and which to fold into the active plan (`docs/development/plans/*`) — but do NOT edit anything unless I say so.

{{include:subagents-core}}

{{include:close-chain}}
