---
description: Read-only .windsurf/rules compliance POSTURE audit — the whole-surface complement to /fabrik-review's per-diff rubric floor: one native finder per applicable pack, refute false gaps, iterate to a stable gap list, prioritized GAP table with path:line proof. Runs in a PROJECT (audit it against its synced packs) or the HUB (audit the packs themselves). TRIGGER — EN: "check rules-pack compliance", "audit against the windsurf rule packs"; TR: "kural paketlerine uyumu denetle", "windsurf kurallarını kontrol et" — a PACK-compliance gap audit, not a defect review. SKIP: code-defect finding (→ /fabrik-review, /fabrik-repo-review); one diff's rules floor (→ /fabrik-review's injected rubric). Stage: gate.
argument-hint: "[a specific pack or rules subdir to scope — omit to audit all applicable packs]"
---

> **⚠️ POOL OFF — D-181.** Every `fanout` / `pick_models` / `set_quality` / `record_agent_run` / `results_table` instruction is SUSPENDED: run every fan-out NATIVELY with Claude Task subagents (`fabrik-reviewer` · `fabrik-researcher`), skip flywheel back-fills, and never write `NO-POOL:` for it (`62-using-subagents.md` § Dispatch policy).

Run a `.windsurf/rules` COMPLIANCE GAP AUDIT. **READ-ONLY — do NOT modify code, config, docs, or the
rules; produce an audit only.** The Termination contract's closing round (Phase 4) is the only proof it is complete. Propose nothing as fixed/done until I say so.
**Context is never a reason to stop:** the harness auto-compacts and the run continues — keep going.

`/fabrik-review` covers the CHANGED DIFF; this is the **whole-surface posture audit** of every applicable pack, invoked deliberately (pre-release, after adopting a pack, on suspected drift).

### Two modes — detect which repo you are in (`git rev-parse --show-toplevel`)

- **PROJECT mode** (any `/opt/<project>` with a `project.yaml`): audit THIS project against its synced packs, a **read-only synced copy** (gate: `check_synced_unmodified.py`) — never edit them locally; a defect IN a pack is a finding filed upstream via `/fabrik-upstream`.
- **HUB mode** (`/opt/fabrik`): the packs THEMSELVES are the audited surface; run this blast-radius checklist across the corpus (scoped by `$ARGUMENTS`), **harder than product code**, since every pack reaches every project on the next sync:
  - Does a rule **contradict another pack**?
  - Would it **break a project that lacks feature X**? Is it backward-compatible?
  - Does it **false-positive on a legitimate, mandated pattern** (banning "daemonize" must not condemn `tini` as PID 1, nor SQLite `desktop-app`'s mandated SQLCipher store)?
  - **Does the rule's `globs:` actually fire where the violation is written?** A glob that never matches the offending file is **theatre**.

{{include:run-record}}
{{include:orient}}
{{include:term-edit}}
{{include:grounding-artifact}}
- Verify globs via `python scripts/select_rules.py` — a plausible-looking glob is not proof it matches.

## Phase 0 — Ground truth (never trust labels; PROJECT mode — in HUB mode steps 1–2 are N/A, steps 3–4 apply)

1. **Establish the real stack:** read `project.yaml::type`, CONFIRM by grep (`package.json` vs `requirements.txt`/`pyproject.toml`, lockfiles) + the real entrypoint; the code is truth.
2. **Read the spec shape flags** in `specs/services/<id>.yaml` (registry: `spec_loader.py::Shape`): a feature off because its flag is false is spec-consistent, not a gap.
3. **Read the project's ADR doc FIRST** (e.g. `docs/reference/architecture-decisions.md`) **AND grep `docs/DECISIONS.md`**: a deviation accepted by a ledger row is as deliberate as an ADR-accepted one, stack-shaped or not (a decided no-audit-log, no-`/metrics`, single-tenant). Capture the accepted-deviation list before auditing anything.
4. If an argument was given, scope the audit to it: `$ARGUMENTS` (a pack or rules subdir); otherwise audit all applicable packs.

## Phase 1 — Which packs apply

Read each `.windsurf/rules/**/*.md` pack's frontmatter `globs:` and any "Per-Scaffold Applicability" matrix to decide if it applies to THIS scaffold + stack. SKIP non-applicable packs unless the code uses them, and STATE which you skipped and why. (HUB mode: every pack is in scope unless `$ARGUMENTS` narrows it.)

## Phase 2 — Audit each applicable pack (parallel native fan-out)

The packs are independent, so this step MUST fan out — sized and stamped at THIS point (`python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --units <packs>` prints the seats, `python3 scripts/command_run.py dispatch --seats <n>` BEFORE they go out, Phase 4's `round --seats <n>` closes) — one native `fabrik-reviewer` seat (Sonnet) per applicable pack, in parallel; Opus for any pack whose subject is authoritative/high-risk (auth, schema, migrations, secrets, concurrency).

**Give each finder ONLY its pack + the Phase-0 ground truth + the RELEVANT CODE EXCERPTS you select for that pack's subject (grep-driven).** Secrets carve-out: never inline secret-material content (`.env` / `.env.*` values — `.env.example` is exempt —, `secrets/`, key files) into any seat's excerpts; redact an unavoidable config excerpt first. Each finder:

- Extracts the pack's "Done When" / requirements / Banned Patterns and judges EACH against the excerpts, citing `path:line`; it **flags any requirement it cannot decide** (`UNVERIFIABLE-FROM-EXCERPTS`) instead of guessing.
- Classifies each item:
  - ✅ COMPLIANT — with `path:line` proof.
  - 🟡 DEVIATION — deliberate + ADR-accepted (cite the ADR line); NOT a gap.
  - ❌ GAP — applicable + not met, with spec-consistency, severity, and where it is already tracked (`RESILIENCE.md`, `STRATEGIC_BACKLOG.md`, `docs/development/plans/*`).

**HUB mode:** the per-pack requirement list IS the blast-radius checklist, judged against the pack's text + the sibling packs you inline + `python scripts/select_rules.py` output.

## Phase 3 — Merge + refute (kill false gaps)

Merge and dedupe all per-pack findings. YOU resolve every `UNVERIFIABLE-FROM-EXCERPTS` flag and verify every cited `path:line` with real tools, exhaustively, not a sample — flags are finder QUESTIONS, never findings. Then try to REFUTE every ❌ GAP: ADR-accepted (cite the ADR line) or spec-consistent-off (cite the shape flag) reclassifies it as 🟡 DEVIATION; only survivors are real. No ✅ COMPLIANT stands without a `path:line` you spot-checked.

## Phase 4 — Iterate to the closing round, then output

**Do not stop after one pass.** Re-run Phases 2–3 until a pass is the Termination contract's closing round: the round-1 seats, over their own slices, CONFIRMING no NEW gap and reclassifying none — `confirmed: 0`, the gap list's md5 unchanged. A pass that changed the list is never the last; only the identical-to-prior pass is convergence. This converges the AUDIT; it fixes no gap (fixing is a separate, user-authorized step).

**Record each pass:** `python3 scripts/command_run.py round --seats <seats dispatched this pass> --findings <raw gaps raised>
--confirmed <n> --classes-swept <the packs swept> --classes-new <…>` — `--findings` is raw recall; `--confirmed <n>` counts gaps that HELD (NEW or RECLASSIFIED this pass, executed against `path:line`), never the standing gap-table size: a re-listed standing gap is CITED, not counted (D-206), so the closing pass records `--confirmed 0`. The round ledger is the only trace, since the audit is chat-only.

**Run the next pass UNPROMPTED the moment a pass adds, removes or reclassifies anything** — never wait to be asked whether the audit stabilized. *"I already audited that pack,"* *"only one item moved,"* *"it's obviously stable"* each mean run it now.

Then output:

1. A prioritized **GAP table**: `pack | requirement | status | evidence (path:line) | already-tracked?`
2. A **"Deliberate deviations (not gaps)"** list with ADR/spec citations.
3. A one-line **"Compliant"** summary per pack.
4. **Pack-defect findings** (PROJECT mode): a `/fabrik-upstream` proposal, never a local edit.
5. **Honesty rules:** no full-compliance claim without embedded proof; don't invent gaps; mark uncertain items; new/unverifiable behavior gets a residual-risk note.
6. End with which gaps are real TODOs vs deliberate and which to fold into the active plan (`docs/development/plans/*`) — but do NOT edit anything unless I say so.

{{include:subagents-core}}

{{include:close-chain}}
