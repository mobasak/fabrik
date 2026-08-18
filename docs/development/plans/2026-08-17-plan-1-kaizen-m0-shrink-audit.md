# Kaizen M0 — the shrink audit (usage-evidence census over all 203 governance artifacts)

Status: IN-PROGRESS
Spec: docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md (§ Sequencing M0 — operator-approved 2026-08-17, commit 3cd798ae)

## What we already agreed

- **Goal (operator, verbatim vision):** size every later kaizen milestone to the *surviving* surface —
  "spend a day asking whether 203 artifacts and 57 checks should become 60 and 20" runs FIRST, with
  evidence, before the meter is built.
- **Scope: M0 ONLY.** A READ-ONLY audit producing a deletion-candidate report + the operator's ruling.
  No artifact is edited, moved, or deleted by this plan; deletions (later, post-ruling) are
  archive-moves, revivable.
- **Evidence-honesty rules (spec, final-panel amendments — BINDING):** rule-pack rows labelled
  *"applicability-only — activation unknown until M1"*; immune-system artifacts EXCLUDED from deletion
  candidacy; the audit's own parsers carry both-ways duplex fixtures (Lesson 126 / the 1440-rounds
  incident); census final for METER SIZING only, re-opens on M1 activation data.
- **Builder-is-guarded (spec § builder):** every component ships its anti-vacuity canary in the same
  commit, proven red-on-revert; the milestone exits via non-author `/fabrik-review`; proofs are
  runnable commands with embedded output, never claims.
- **Spec correction found at grounding (carried honestly, not silently):** the spec's M0 evidence list
  names "checks-that-never-failed from gate JSON history" — **no gate JSON history exists**
  (`final_gate.py` prints JSON, stores nothing; verified by inspection + `find .fabrik`). Substitutes
  that DO exist: per-check activity grepped from gate outputs embedded in transcripts (2,450 check-name
  hits in one session file, measured), and the liveness audit's verdicts. The report states this
  substitution; the spec gets a one-line erratum in this plan's docs step.

## Global Constraints

- Box-local Python 3.12 stdlib script; `uv run pytest` for tests (`45-testing-strategy.md:47` — never
  bare pytest); no new deps (deps files untouchable without authorization).
- Shared tree, 3 concurrent sessions: explicit pathspecs only; never touch sibling WIP; commit each
  phase with Agent Provenance Trailers.
- READ-ONLY over the 203 census artifacts and all evidence sources; writes limited to File Scope
  (the spec's one-line erratum is a declared File-Scope write — the spec is not one of the 203).
- Instrument hazards (each hit live this week — design in, don't rediscover): `grep -a` / open with
  `errors="replace"` (UTF-8 dirt makes grep call transcripts binary); resolve `~/.claude-fleet`
  symlinks with `Path.resolve()` (bare `find` returned 0 across a symlink); run records nearly all
  collided into `nosession.json` (supplementary signal only, never a denominator); transcripts are
  per-session files with long-session mtime skew (census by file, dates as ranges, not day-buckets).
- 12-Factor non-negotiables (inherited; mostly structurally N/A for a box-local read-only script):
  logs = stdout only, never a logfile (XI — cron `>>` routing is the environment's concern); config
  via env vars with defaults (III); no daemonizing/PID files (VIII); no backing-service substitution
  (X — N/A: no DB/Redis); releases immutable, migrations N/A (V/XII); no sticky sessions/ports (VI/VII
  — N/A: no service).
- The audit script itself obeys the kaizen honesty rule: an unmeasurable signal prints `—` + reason,
  never 0-for-no-data.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `core/45-testing-strategy.md` (ACTIVE) | watched-fail-first for every new test; `uv run pytest`; zero-mock-DB N/A (no DB) | `.windsurf/rules/core/45-testing-strategy.md:21,47` |
| `core/10-python.md` (ACTIVE) | env config via `os.getenv` w/ defaults; no grouped config sets | `.windsurf/rules/core/10-python.md:249` |
| `core/55-observability.md` (ACTIVE) | stdout only; the script never writes/rotates a logfile | `.windsurf/rules/core/55-observability.md:62` |
| `core/40-documentation.md` (ACTIVE) | Doc Sync Matrix rows below; md shape rules (no skipped heading levels, fenced code only) | `.windsurf/rules/core/40-documentation.md:59,197` |
| `core/62-using-subagents.md` (ACTIVE) | pool-default for gradeable fan-out + `set_quality` back-fill; native for the decide/merge | `.windsurf/rules/core/62-using-subagents.md:35` |
| Script coupling header law | new script carries `# AFTER-EDIT:` in first ~25 lines | CLAUDE.md § Pointers (gate-WARN'd by `check_script_headers.py`) |
| fabrik-lib consult | **BUILD** — README module table has no artifact-census/usage-audit module (checked 2026-08-16 for the spec's verdict table; re-confirmed: closest are `claude-evaluator`/`app-audit-log`, both wrong seam). Not a 🆕 candidate: single-box, hub-specific inputs | `/opt/fabrik-lib/README.md` module table |
| Artifact registries (the census's denominators — enumerate from these, never memory) | 27+13 from `commands/_sources/`+`_fragments/` ls; 56 packs from `.windsurf/rules/**/*.md`; 57 checks from `scripts/enforcement/check_*.py`; 5 hooks from `.claude/hooks/*.py`; 12 scaffold types from `scaffold.py::SCAFFOLD_TYPES`; 12 synced scripts from `fabrik_synced_manifest.py::CORE_SCRIPTS`; 21 crons from `crontab -l` | `src/fabrik/scaffold.py` · `scripts/fabrik_synced_manifest.py` |
| Evidence source: transcripts | invocation signal spans BOTH channels — `<command-name>/x` rows (typed) + Skill tool_use rows (agent-initiated; 145 vs 4 in one file, measured); gate check names appear in embedded tool outputs (2,450 hits/one file) | `~/.claude/projects/*/*.jsonl` (fixture: this session's own file) |
| Evidence source: rule-pack globs | frontmatter `globs: [...]` → glob-replay vs `git log --name-only` = APPLICABILITY only | `.windsurf/rules/core/10-python.md:1-5` |
| Evidence source: liveness verdicts | per-surface LIVE/DEAD/UNKNOWN from the weekly liveness audit — the gate-history substitute | `scripts/sysadmin/liveness_audit.py` + `.fabrik/liveness-registry.json` |
| Evidence source: review ledgers + run records | mentions of commands/scripts fleet-wide (237 ledgers); run records supplementary-only (nosession collision) | `/opt/*/docs/development/reviews/` · `~/.claude/state/command-runs/` |
| `.md` allowlist | report lives at `docs/workstation/kaizen-shrink-audit.md` (box-local system doc — Doc Sync Matrix "new subsystem → dedicated doc" row; kaizen.md precedent) | CLAUDE.md § HARD STOPS (allowlist) + § Doc Sync Matrix |
| No `shape:` flags / no deploy | box-local script + report; no service, no spec, no cron in M0 | spec § Shape/infra |

## Phase A — the evidence engine (`kaizen_shrink_audit.py`) with duplex fixtures — ✅ EXECUTED 2026-08-19 (f9e253b1)

**Files:** `scripts/sysadmin/kaizen_shrink_audit.py` (new; `# AFTER-EDIT:` header),
`tests/test_kaizen_shrink_audit.py` (new).

**Interfaces — Produces:** `audit(sources: Sources) -> list[ArtifactRow]` — the composition of the
collectors (Phase A step 3c assembles it) — where `ArtifactRow` =
`{artifact, cls, invocations (per-channel), last_seen, applicability_structural,
applicability_recent, liveness, mentions, evidence_note, immune=None, verdict=None}` — **the
`immune`/`verdict` fields are None at Phase A** and are filled ONLY by Phase B (review finding: the
v1 schema implied A needed B's registry — a circular dependency; A gathers evidence, B judges);
CLI `--json` / `--selftest` / `--report`; `Sources` dataclass with overridable roots (fixtures
inject temp dirs). **Consumes:** nothing from other phases.

Steps:
1. Toolchain preflight: `uv run pytest --version` and `git -C /opt/fabrik log --oneline -1` both
   succeed (expected: version line; one commit line).
2. **TDD the riskiest parser first (watched-fail-first):** write
   `test_transcript_invocations_counts_both_channels` against a fixture transcript containing two
   `<command-name>/fabrik-review</command-name>` rows, one Skill tool_use row
   (`{"type":"tool_use","name":"Skill","input":{"skill":"fabrik-spec"}}` inside an assistant message),
   and one line of invalid UTF-8 → expect `{"fabrik-review": 2, "fabrik-spec": 1}` per-channel-tagged,
   and no crash. RUN IT, confirm RED (no engine yet), then implement `collect_invocations()` to green.
   **The signal spans BOTH invocation channels** (review grounding, this session's own transcript:
   145 Skill tool_use rows vs 4 `<command-name>` rows for the same commands — counting only the
   typed channel under-counts exactly the agent-initiated invocations): (a) `<command-name>/x`
   rows (operator-typed), (b) Skill tool_use rows keyed on JSON structure, not raw grep (a quoted
   `"skill":"x"` in conversation text must not count). Open `errors="replace"`, per-session files,
   `Path.resolve()` on roots; report the two channels as separate columns summed into `invocations`.
3. Implement the remaining collectors, each with its own both-ways fixture pair (good input counts,
   bad/empty input yields `—`-with-reason, never 0):
   - `collect_applicability()` — parse every pack's frontmatter `globs:`; emit TWO columns (review
     finding: a time-bounded replay conflates structural reach with recent activity):
     `applicability_structural` = globs matched against the CURRENT tree (`git ls-files`) — timeless,
     "could this pack ever fire here"; `applicability_recent` = matched against
     `git log --since=<--since-days, default 60> --name-only` file lists — the activity proxy. Both
     labelled `applicability-only`; neither is ever usage.
   - `collect_check_activity()` — grep check display-names + script names (from
     `scripts/enforcement/check_*.py` registry) across transcripts (`-a` semantics) + join the latest
     liveness verdicts.
   - `collect_mentions()` — command/script/fragment/hook/scaffold-type/cron-target name greps across
     the 237 review ledgers + run records (records flagged `supplementary` in the row).
   Then **3c: compose `audit()`** over the collectors into `ArtifactRow`s (immune/verdict left
   `None` — Phase B's), with a composition test: a fixture Sources tree yields exactly the expected
   rows.
4. `--selftest` canary (same commit, the `check_command_corpus` discipline): every collector must FAIL
   its bad fixture and PASS its good one; prove the suite discriminating **red-on-revert** — neuter
   one collector in a throwaway copy, watch its fixture fail, restore.
   Gate: `uv run pytest tests/test_kaizen_shrink_audit.py -q` → all pass;
   `python3 scripts/sysadmin/kaizen_shrink_audit.py --selftest` → `all collectors fire on bad input`.
5. Closing sequence: (1) phase gate green; (2) `python scripts/enforcement/check_doc_sync.py` + this
   phase's doc rows (none yet — script lands with Phase B's docs); (3) **`/fabrik-review` on the
   changed surface, run to its coverage-adjudicated exit — BLOCKING**; (4) commit
   (`git commit -- scripts/sysadmin/kaizen_shrink_audit.py tests/test_kaizen_shrink_audit.py`,
   provenance trailers).

**Behavior Contract (Phase A):**
- **Given** a transcript with `<command-name>` rows, Skill tool_use rows, a QUOTED
  `"skill":"x"` inside prose, and invalid UTF-8, **When** invocations are collected, **Then** both
  real channels count, the quoted mention does NOT, and the file is never skipped as binary
  (`scripts/sysadmin/kaizen_shrink_audit.py:collect_invocations`).
- **Given** an empty/absent evidence root, **When** any collector runs, **Then** its signal is `—` with
  a reason, never 0 (the kaizen honesty rule).
- **Given** a pack whose globs matched no changed file in 60d, **When** applicability is computed,
  **Then** the row is labelled `applicability-only — activation unknown until M1`, never "unused".

## Phase B — census, immune registry, report, operator-ruling section — ✅ EXECUTED 2026-08-19

**Files:** `scripts/sysadmin/kaizen_immune_list.py` (new — the DATA lives as a reviewed Python list
with per-entry one-line justifications, so the human can audit it),
`docs/workstation/kaizen-shrink-audit.md` (new — the report), edits to
`scripts/sysadmin/kaizen_shrink_audit.py` + tests.

**Interfaces — Consumes:** Phase A's `audit()` rows. **Produces:** the report file; verdict vocabulary
`candidate | keep | unknown` (exact tokens); `IMMUNE: frozenset[str]` in `kaizen_immune_list.py`.

Steps:
1. **Immune registry first** (test-first): seed from the enumerable safety surfaces — the built-in
   never-route set (`scripts/enforcement/check_plan_tickets.py` never-route paths), Stop-hook +
   mesh scripts (`docs/workstation/hooks-index.md` inventory), DR/backup commands, the freeze/guard
   machinery, `/fabrik-decommission` + `/fabrik-upstream` (rare-by-design commands). Test: every
   immune entry carries a justification string; an immune artifact NEVER receives verdict `candidate`
   even at zero usage (watched-fail-first: assert on a zero-usage immune fixture).
2. Verdict assignment: the verdict is EXACTLY one enum token `candidate|keep|unknown`; human-facing
   annotations (`keep — immune: <justification>`, the applicability label) live in `evidence_note`,
   never in the token (review finding: v1 examples read as extra verdict forms).
   **`applicability-only-class` is DEFINED as: rule packs** — the only glob-activated class with no
   invocation channel; their zero-usage never yields `candidate`, only `unknown` with the label. For
   every OTHER class the report legend states its measurability (commands: both invocation channels;
   checks: transcript gate-output + liveness; hooks/crons/scripts: liveness + mentions; scaffold
   types: scaffold-invocation greps) — a class whose named signals are ALL unmeasurable routes to
   `unknown`, never `candidate` (the honesty rule generalized, per review). `candidate` then requires:
   zero on every measurable signal for its class AND not immune. Duplex-test each branch.
3. Emit the report (`--report`): per-class tables (all 203 rows — invocations · last-seen ·
   applicability · liveness · mentions · immune · verdict · evidence note), the evidence-substitution
   erratum (gate-history → transcripts+liveness), the census-scope statement ("final for METER SIZING;
   re-opens on M1 activation data"), and a `## Operator ruling` section listing every `candidate` with
   an empty `[ ]` decision box — the ruling is the OPERATOR's act, recorded in this file.
   Gate: `python3 scripts/sysadmin/kaizen_shrink_audit.py --report` writes the file; row count == the
   enumerated census total (assert in-script; print the count).
4. Closing sequence: (1) gate green; (2) doc rows: `INDEX.md` (script + report + immune list),
   `CHANGELOG.md` entry, `docs/workstation/kaizen.md` M0 section, spec erratum line (one line in the
   spec's M0 row pointing at the substitution — a docs-only edit to a CONVERGED spec, flagged in the
   commit), `docs/README.md` untouched (dir-level index only); (3) **`/fabrik-review` on the changed
   surface to its adjudicated exit — BLOCKING**; (4) commit with pathspecs + trailers.

**Behavior Contract (Phase B):**
- **Given** an immune artifact with zero usage everywhere, **When** verdicts assign, **Then** it is
  `keep — immune: <justification>`, never `candidate` (`scripts/sysadmin/kaizen_immune_list.py:IMMUNE`).
- **Given** the finished report, **When** rows are counted, **Then** they equal the live enumeration of
  all artifact classes (no artifact silently dropped).
- **Given** a rule-pack row, **When** rendered, **Then** it carries the literal label
  `applicability-only — activation unknown until M1`.

## Phase C — receipt: full gate, docs convergence, non-author review

**Files:** `docs/development/reviews/2026-08-17-plan-1-kaizen-m0-shrink-audit-review.md` (receipt),
`docs/LESSONS_LEARNT.md` (entry or `none` — decided at run time).

Steps:
1. Whole-plan verification: `python scripts/final_gate.py --check --json` → expect
   `"status":"success"` **and** `python scripts/enforcement/check_convergence.py` → green. State
   plainly: a green gate is necessary, not sufficient — the Evidence section is the proof.
2. `/fabrik-docs-review` over this plan's touched docs (report, kaizen.md, INDEX rows) → truthful
   no-op.
3. **Non-author `/fabrik-review` closing sweep (spec § builder-is-guarded): finders in a non-author
   context over the full plan surface, to a coverage-adjudicated `found: 0`** — BLOCKING; the receipt
   file embeds the verbatim gate JSON + per-phase verdicts.
4. Present the report's `## Operator ruling` section to the operator. **The M0 gate ("operator has
   ruled; census final for meter sizing") is the operator's act — the plan ENDS by presenting, never
   by self-ruling.**
5. Commit receipt + docs (pathspecs + trailers); push.

**Behavior Contract (Phase C):**
- **Given** the finished plan surface, **When** the closing non-author review runs, **Then** it reaches
  `found: 0` on a full fresh round and the receipt embeds the gate's `"status":"success"` verbatim.

## Behavior Contract

The roll-up of every per-phase contract row (the per-phase blocks above are the same rows in place):

- **Given** a transcript with `<command-name>` rows, Skill tool_use rows, a QUOTED
  `"skill":"x"` inside prose, and invalid UTF-8, **When** invocations are collected, **Then** both
  real channels count, the quoted mention does NOT, and the file is never skipped as binary
  (`scripts/sysadmin/kaizen_shrink_audit.py:collect_invocations`).
- **Given** an empty/absent evidence root, **When** any collector runs, **Then** its signal is `—` with
  a reason, never 0 (the kaizen honesty rule).
- **Given** a pack whose globs matched no changed file in 60d, **When** applicability is computed,
  **Then** the row is labelled `applicability-only — activation unknown until M1`, never "unused".
- **Given** an immune artifact with zero usage everywhere, **When** verdicts assign, **Then** it is
  `keep — immune: <justification>`, never `candidate` (`scripts/sysadmin/kaizen_immune_list.py:IMMUNE`).
- **Given** the finished report, **When** rows are counted, **Then** they equal the live enumeration of
  all artifact classes (no artifact silently dropped).
- **Given** a rule-pack row, **When** rendered, **Then** it carries the literal label
  `applicability-only — activation unknown until M1`.
- **Given** the finished plan surface, **When** the closing non-author review runs, **Then** it reaches
  `found: 0` on a full fresh round and the receipt embeds the gate's `"status":"success"` verbatim.

## Execution discipline (binding on /fabrik-execute-plan)

- **Review floor:** every phase ends with `/fabrik-review` on its changed surface to a
  coverage-adjudicated exit BEFORE its commit is considered done; Phase C's closing sweep runs with
  non-author finders.
- **Dispatch policy:** pool-default for the gradeable fan-out — Phase A/B test authoring may use
  `/fabrik-generate-tests` (pool authors, you curate); the evidence-collector *verification* sweep in
  Phase C review runs pool finders (`fanout("review", …)` + `set_quality` back-fill) with native on
  top for the decide/merge. All parser/verdict DESIGN stays native (this is the meter's meter).
- **Parallelism:** Phase A's collectors are independent units — their fixture-authoring fans out;
  results merge in the census assembly (Phase B step 2). Phases are sequential (true data dependency
  A→B→C).

## File Scope (owned paths)

- scripts/sysadmin/kaizen_shrink_audit.py
- scripts/sysadmin/kaizen_immune_list.py
- tests/test_kaizen_shrink_audit.py
- docs/workstation/kaizen-shrink-audit.md
- docs/workstation/kaizen.md
- docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md
- docs/development/reviews/2026-08-17-plan-1-kaizen-m0-shrink-audit-review.md

## Evidence

- **Phase A:** transcript invocation signal proven live: `grep -a -o '<command-name>[^<]*'` over this
  session's transcript returned `/fabrik-review ×22`, `/model ×29`, `/compact ×12` (command run
  2026-08-17, embedded below). Gate-history absence proven: `find /opt/fabrik/.fabrik -name "*.json"`
  → only `lint-baseline`, `liveness-registry`, `state/*` (no gate history); `final_gate.py` grep shows
  no persistence path. Rule-pack glob frontmatter format: `.windsurf/rules/core/10-python.md:1-5`
  (`globs: ["**/*.py"]`).
  ```
  29 <command-name>/model</command-name>
  22 <command-name>/fabrik-review</command-name>
  12 <command-name>/compact</command-name>   (this session's transcript, grep -a, 2026-08-17)
  145 Skill tool_use rows same transcript — the SECOND channel (review finding: plan v1 counted
      only <command-name>; "skill":"fabrik-plan-review"×32, "fabrik-spec"×12 …)
  ```
- **Phase B:** artifact registries enumerated live 2026-08-16: 27 sources + 13 fragments (`ls`),
  56 packs, 57 checks, 5 hooks, 12 scaffold types (`scaffold.py::SCAFFOLD_TYPES`), 12 core scripts
  (`fabrik_synced_manifest.py`), 21 crons (`crontab -l | grep -c opt/fabrik`). Never-route built-ins:
  `scripts/enforcement/check_plan_tickets.py` (never-route set). Hooks inventory:
  `docs/workstation/hooks-index.md`.
- **Phase C:** convergence contract: `scripts/enforcement/check_convergence.py` (docstring:9-20 —
  Evidence + self-audit floor at the flip); receipt naming = plan-stem (`<stem>-review.md`).

## Self-audit

- Grounding passes run: evidence-source probes (invocation signal, gate-history absence, glob format,
  liveness registry shape, run-record collision state) — all embedded above; fabrik-lib consult
  re-confirmed BUILD; allowlist checked for the report path (docs/workstation precedent: kaizen.md).
- **(a) coverage:** every "What we already agreed" item maps — evidence-honesty rules → Phase A step 3
  + Phase B steps 1–3; builder-guarded → Phase A step 4 + Phase C step 3; read-only → Global
  Constraints + File Scope (no artifact paths); spec correction → Phase B step 4 erratum + report
  section; operator ruling → Phase C step 4. No gaps found.
- **(b) cross-phase signatures:** `audit() -> list[ArtifactRow]` (A.Produces) consumed by B verdicts;
  verdict vocabulary `candidate|keep|unknown` (B.Produces) consumed by the report + ruling section;
  `IMMUNE` frozenset consumed by B step 2. Names reconciled — one vocabulary, stated once.
- Fixed point not yet claimed — that is `/fabrik-plan-review`'s flip.

## Residual unknowns

- **Resolved:** gate-history absence (substituted, erratum planned); report location (allowlist
  precedent); extend-vs-build (BUILD, ledger row).
- **Still-open:** (1) exact immune-list membership — resolution: Phase B step 1 seeds from the four
  enumerable registries and the OPERATOR's ruling pass is the final say (self-service; never blocks
  execution). (2) 60-day git window for applicability may under-represent dormant-but-alive packs —
  resolution: the window is a report parameter (`--since-days`, default 60), and the
  `applicability-only` label already prevents over-reading; noted in the report legend.
