# Evaluation checklist — the `/fabrik-*` command corpus

Every command/skill in `commands/_sources/` must be evaluated against this list before it is
considered sound. **Not every item applies to every command — but every item must be CHECKED.**
"N/A for this command, because X" is a valid verdict; forgetting to check is not.

**Sibling checklists, deliberately separate:**
`docs/orchestrator/epic-to-ticket-workflow/EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md` and
`docs/orchestrator/mega-epic-breakdown/EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md` audit the **Traycer
workflow artifacts** (epics, tickets, tech plans). This one audits the **command corpus itself** —
the instruction set every agent on this box runs on. Different surface, different failure modes.

## ⚠️ Do not re-litigate what a gate already proves

`scripts/enforcement/check_command_corpus.py` is BLOCKING at Tier 2 and mechanically decides five
facts (detail: `docs/reference/command-corpus-check.md`): `web_tools=[…]` names only real tool
names · every `/fabrik-x` chain reference resolves · every `scripts/**.py` a command names exists ·
`Co-Authored-By:` matches the canonical trailer · every command opens a run record. **Run the check;
do not spend audit attention re-deriving its verdict.** Items below marked **[GATED]** are in that
set — confirm the gate is green and move on. Everything else is judgement, which is why this
document exists.

## ⚠️ Evaluate the RENDERED command, not the source alone

`commands/_sources/<cmd>.md` is a TEMPLATE. `{{include:…}}` fragments expand at render time, so
obligations the agent actually reads — closing the run record by name, the three sanctioned BLOCKED
cases, the phase count — appear in `~/.claude/commands/<cmd>.md` and in **none** of the sources that
include them. Auditing the source alone reported three false findings against `/fabrik-rivals` on the
first calibration run. Read the source for AUTHORED content and the rendered file for CONTRACT
coverage; `assemble_commands.py --check` proves the two are in sync.

Some obligations live in neither: the 6-line FINAL OUTPUT block and the STATE footer are owed by
**CLAUDE.md globally**, to every response from every command. Only 2 of 31 sources mention them, and
that is correct — do not raise 29 findings for a contract no command is supposed to restate.

## The 22 surfaces an audit of one command touches

An audit that reads only `commands/_sources/<cmd>.md` will pass a command whose companions have all
rotted — or whose paired twin never asserts what it states. The surfaces, grouped by the question they answer:

| Group | Surfaces | Question |
|---|---|---|
| Contract | `commands/_sources/<cmd>.md` · `commands/_fragments/` | Is the contract complete and terminable? |
| Wiring | `assemble_commands.py` (NEXT map + PARAMS) · `~/.claude/commands` · `~/.claude/skills` · `.claude/hooks/skill_router.py` | Successor named, rendered==installed, can it fire? |
| Grader | `scripts/enforcement/**` · `scripts/final_gate.py` | Is any of the contract executable? |
| Fleet | `scripts/fabrik_synced_manifest.py` · `src/fabrik/scaffold.py` · `.pre-commit-config.yaml` | Works in a project? In a NEW project? Blast radius known? |
| Governance | hub `CLAUDE.md` · `templates/governance/CLAUDE.md` · `agents-fabrik.md` | In the pipeline chain AND the Orient table — in BOTH? |
| Rules | `.windsurf/rules/**` | Does it contradict a pack, or need one it never names? |
| Docs | `docs/reference/<subsystem>.md` · `INDEX.md` · `docs/README.md` · `docs/FEATURES.md` · `CHANGELOG.md` | Do the companions still describe what shipped? |
| Neighbours | `docs/orchestrator/**` | Do the Traycer chains still invoke it by a name that exists? |
| **Twin** | the command's PAIRED command — `/fabrik-x` ↔ `/fabrik-x-review`, author ↔ reviewer | **Is every rule this one STATES asserted by SOMETHING — the twin OR a gate?** A rule set in the author and asserted nowhere is a gate nobody runs. ⚠️ **Absence from the twin is NOT the finding** — check for a mechanical assertor first. On this surface's first real use (cmd 12/31) it flagged two rules missing from `/fabrik-plan-review`, and BOTH were refuted: `READ_BUDGET_BYTES` is asserted by `check_plan_tickets.py` (6 refs, blocking) and `## Evidence` by `check_convergence.py:149`. A gate is a STRICTER assertor than a prose twin, so gate-covered is the good outcome, not a gap. Grep the author for numbers, thresholds and MUSTs; for each, grep the twin AND `scripts/enforcement/`. Watch for the reviewer paraphrasing a number away — `/fabrik-flows` set *"target ≤30 lines, hard split at 50"* while `/fabrik-flows-review` said only *"length within targets"*, so the closing round had no number to assert and flows at 83 and 53 lines passed unremarked (transdoc `01M14Y90D0`). Grep the author for numbers, thresholds and MUSTs, then grep the twin for each one. |

---

## Identity & Routing

1. Does the frontmatter carry a `description:` that states what the command DOES, not what it is about?
2. Does the description carry a bilingual `TRIGGER — EN: … ; TR: …` clause with realistic operator phrasing?
3. Does the description tell a near-miss where to go instead? Check for skip **SEMANTICS**, not the literal `SKIP:` token: 11 of 31 sources carry no `SKIP:` label, but **7 of those 11** redirect inline (`… never a fresh idea (→ /fabrik-spec) or a plan review (→ /fabrik-plan-review)`) and are CLEAN. Only **4 of 31** — `fabrik-catchup`, `fabrik-decommission`, `fabrik-deploy-verify`, `fabrik-upstream` — give no sibling guidance at all. Grepping the token alone produces 7 false findings (measured on command 3).
4. Does it carry `Stage: <1-design|2-contract|3-plan|4-build|5-certify|6-release|gate|utility>`, and is that stage the one CLAUDE.md § Orient would route the task to?
5. Does it carry an `argument-hint:` when it takes arguments? (`design-review` and `fabrik-workflow-review` carry none; `design-review` is deliberately router-excluded, `fabrik-workflow-review` takes an artifact path + type and should have one.)
6. Is it reachable by the operator the way the TRIGGER clause implies — i.e. is its stem in `skill_router.py::STEM_SKILLS`? ⚠️ **Run the router on the command's OWN advertised trigger phrases** (`first_regex_match(phrase)`); do not just check for a stem. A MIS-route is worse than no route: `/fabrik-spec-review` advertised "review this spec" and the router sent it to `fabrik-review`, the code-diff reviewer, whose own SKIP clause excludes specs (found + fixed 2026-08-27). First match wins in `KEYWORD_STEMS`, so a specific stem must precede its generic sibling. **13 stems serve 31 commands**, so most TRIGGER clauses serve model-native matching only. That is defensible; a description that implies auto-routing it does not have is not.
7. **[GATED]** Does every `/fabrik-x` it names resolve to a real command source?
7b. **[GATED]** Does every `scripts/**.py` it tells an agent to run actually exist?
8. Is it in the NEXT map (`assemble_commands.py`), with a successor AND a one-line why? (Currently 31/31 — a new command missing here is the regression to catch.)
9. Does the named successor match CLAUDE.md § Pipeline, and does § Pipeline match back?
10. If it is a **gate** (no linear successor), does it say so explicitly — "resume what called it" — rather than naming a stage?

## Contract & Termination

⚠️ **First decide which SHAPE the command is, or items 11-15 will generate false findings.**

- **Self-converging** (`/fabrik-review`, `/fabrik-repo-review`, `/fabrik-rivals`, the certification
  gauntlets): owns its loop. Items 11-15 apply in full.
- **Producer with a review TWIN** (`/fabrik-spec`→`/fabrik-spec-review`,
  `/fabrik-plan-after-chat`→`/fabrik-plan-review`, `/fabrik-ui-design`→`/fabrik-ui-design-review`,
  `/fabrik-deploy-plan`→`/fabrik-deploy-plan-review`, `/fabrik-flows`→`/fabrik-flows-review`):
  convergence is DELEGATED. The correct contract is a light self-review, a **MANDATORY invocation of
  the twin in the same turn**, a stated "do not end on an unconverged DRAFT", and a named short list
  of the only legitimate early stops. Demanding an in-command md5/Pass-Ledger loop here is a
  DEFECT — it duplicates the twin, which the sibling epic checklist names as an anti-pattern at its
  item 135. Evaluate 11-15 against the DELEGATION, not against an absent loop.
- **One-shot utility** (`/fabrik-doc-converge`, `/fabrik-upstream`): a stated done-condition is still
  owed; a loop is not.

Calibration note: on the first pass over `/fabrik-spec` this distinction was missing, and a grep for
"termination contract" returned zero — nearly producing a false finding against a command whose
Phase 6 delegates correctly and names its two legitimate early stops.

11. Does it have an explicit **termination contract** — a stated condition that ends the run (for a
    producer: the delegation above)?
12. Is that condition **mechanically decidable**, or does it rest on the agent's own judgement of its own output?
13. Is the terminal condition reachable? Walk the mechanism that feeds it and prove a round can genuinely re-ask the question (**anti-pattern 90**).
14. If it is a LOOP, does it forbid a fixed round count and require a no-op round?
15. Does it distinguish "found nothing" from "could not look"? Those produce byte-identical evidence and only one is convergence.
16. Does it open a run record as its first act (`{{include:run-record}}` **or** a bespoke `command_run.py start` block)? **[GATED]** — `fabrik-docs-review`, `fabrik-execute-plan` and `fabrik-review` carry bespoke blocks, not the fragment; that is legitimate, absence of both is not.
17. Does it name the phase count honestly? The fragment's phase count is computed at render time by `_phase_count`; a hand-written count drifts the moment a phase is added.
18. Does it close its run record **by name** (`done --command <name>`), never by closing "whatever is live"?
19. Does it state which of the three sanctioned BLOCKED cases may stop it, and forbid stopping for anything else?
20. Does it avoid CONTRADICTING the global output contract (6-line FINAL OUTPUT on a task-completing run, 2-line STATE footer otherwise)? The obligation is CLAUDE.md-global, not per-command — 2 of 31 sources restate it and that is fine. A finding here means the command tells the agent to end DIFFERENTLY, not that it stayed silent.

## Fragments & Composition

21. Does it include the fragments its shape requires, and NONE it does not? (`run-record` · `term-edit` / `term-coverage` · `grounding-*` · `injection` · `questionbar` · `repo-identity` · `subagents-core` · `autonomy-run`)
22. Is every included fragment still load-bearing, or is one residue from a superseded design that now contradicts the body? (Live: `/fabrik-rivals` includes `repo-identity` beside "there is no mode to pick".)
23. Does it inline content that a fragment already owns — a divergent copy that will drift?
24. If it hand-inlines a fragment's text (the orchestrator docs do), does it carry the version marker so drift is detectable?
25. Does the `term-*` fragment it chose match its surface? A DIFF surface takes `term-coverage`'s wide/scoped/wide round shape; a journey/inventory surface keeps its discovery-until-dry loop.

## Evidence & Grounding

26. Does it forbid reporting success from a PROXY when an executable check of the real thing exists?
27. Does it require every cited fact to be grounded at a real `path:line`, read this run, not remembered?
28. Does it require external/vendor claims to be re-verified LIVE with a cited URL + fetch date?
29. Does it treat a subagent's "success" as a claim to verify, never as proof?
30. Does it require the proving command to be run in the SAME message as the claim (freshness)?
31. Does it forbid a stale gate result — a green from before the last file change?
32. Does it verify every path it cites still exists (`ls`/`Read`) rather than trusting the citation (**anti-pattern 93**)?
33. Does it carry the injection fragment wherever it ingests untrusted content (web text, LLM output, mail, another repo's files)?
34. Does it state what it CANNOT prove, rather than leaving the blind spot implicit?

## Enforcement Backing (the grader question)

35. **Is any part of this command's contract graded by something executable?** A contract with no grader is graded by the agent it constrains.
36. If a grader exists, name it: `check_review_coverage` (reviews) · `check_convergence` (convergence claims) · `check_plan_tickets` / `check_ticket_breadth` / `check_phase_tests` (plans) · `check_certification_coverage` (cert boards) · `check_rivals_dossier` (dossiers) · `check_command_corpus` (the corpus itself) · the `check_doc_*` family (docs).
37. If none exists, is that a deliberate ruling or an oversight? Say which.
38. Does the grader read the artifact the command actually produces, or a proxy for it?
39. Does the grader state its **denominator** — how many things it examined?
40. Does the grader state what it could NOT check?
41. Is the grader registered in `final_gate.py` at the right tier, and outside any `if tier` guard if it should always run?
42. If registered `warn_only=True`, does it **always exit 0** — including its own error path, argparse failure, and a hostile `--root`? A non-zero exit from a `warn_only` check is a BLOCKING red across ~46 repos (**anti-pattern 91**).
43. Does the grader stay SILENT in repos where its subject does not exist? Permanent advisory noise trains readers to skip advisory output.
44. Does its output fit `final_gate`'s 500-char truncation **with margin**, remedy line intact (**anti-pattern 95**)?

## Fleet Safety & Blast Radius

45. Does the command work from a PROJECT repo, not only the hub?
46. If it needs a driver script, is that script in `CORE_SCRIPTS` (`fabrik_synced_manifest.py`) so every repo has it?
47. Does `src/fabrik/scaffold.py` emit it, so a NEW project gets it? (It reads `CORE_SCRIPTS` from the manifest — a hardcoded list there once left new projects missing 7 scripts.)
48. Does it correctly distinguish cross-repo **reads** (allowed) from cross-repo **writes** (HARD STOP)? Misreading this once split a one-repo command into a two-repo mail errand (**anti-pattern 92**).
49. Does every artifact it writes land in the CALLING repo?
50. Does it degrade with a NAMED fix when a dependency is absent, rather than silently doing less?
51. Is the blast radius of editing it known — is any surface it touches in the `governance-sync` files-filter in `.pre-commit-config.yaml`? Read the filter; do not recall it.
52. If it edits a synced surface, is the change correct for **all** ~46 projects, not just the repo in front of you?
53. Does it forbid hand-editing a single project's synced copy as a hotfix?
54. Are enumerations of canonical values (scaffold types, shapes, stages) copied from the live registry (`scaffold.py::SCAFFOLD_TYPES`, `spec_loader.py::Shape`), never from memory?
55. Does it handle the UI-bearing vs headless split correctly — GUI commands skipped for `{python-api, python-api-gpu, node-api, file-api, file-worker}`, and `5-certify` routed to `/fabrik-service-test` not `/fabrik-user-test`?

## Governance Chain

56. Is it in hub `CLAUDE.md` § Pipeline **and** the § Orient stage table?
57. Is it in `templates/governance/CLAUDE.md` — the project-facing contract — in both places too? **Three CLAUDE.md files exist** (hub, governance template, fabrik-lib); a command that reaches only one is half-shipped.
58. Does it contradict any `.windsurf/rules/` pack? A command that fights a pack is worse than either alone.
59. Should a pack activate for the work it drives, and does the command name it?
60. Does it respect the conflict order — rule pack > ticket for *how*; `spec.shape` canonical for *what*?
61. Does it honour the HARD STOPS (no `git add -A`, no force-push, provenance trailers, explicit pathspecs, memory limits, no host ports, no `localhost` DB)?
62. Does it require the Agent Provenance Trailer block as its own paragraph with no blank line inside?
62b. **[GATED]** Does `Co-Authored-By:` in any commit template it carries match CLAUDE.md's canonical trailer? Six templates once named a retired model.
63. Do the Traycer chains under `docs/orchestrator/**` still invoke it by a name that exists?

## Docs & Companions

64. Does a new subsystem it introduces have its OWN `docs/reference/<name>.md`? (grep/`ls` first — extend, never write a second.)
65. Does that reference doc describe the CURRENT architecture, not a superseded one? **This is the highest-yield check in the list** (**anti-pattern 94**).
66. Do the `INDEX.md` rows describe what shipped?
67. Is `docs/README.md` updated when a doc is added or removed?
68. Is the Doc Sync Matrix honoured — and treated as a FLOOR, not a whitelist? Any doc the change made stale is owed, listed or not.
69. Is there a `CHANGELOG.md` entry under `## [Unreleased]`, appended without resetting the section?
70. Is `docs/LESSONS_LEARNT.md` updated when a reusable lesson exists, or explicitly `none`?
71. Are new `.md` files inside the gate-enforced allowlist (`docs/reference/**` is; `commands/*.md` is not)?
72. Does it avoid citing `CHANGELOG.md:<line>`? The file is prepend-ordered; cite the dated entry title.
73. Does it prefer a section anchor to a line range when citing another command?

## Subagents, Cost & the Flywheel

74. If it dispatches gradeable fan-out, does it use the pool (`fanout` → `set_quality`), never hand-rolled `run_agents`/`record_run`?
75. Does it add a native Opus pass ON TOP for the authoritative/high-risk slice, never instead?
76. Does it require the flywheel back-fill after merge+refute?
77. Does it satisfy the parallelism shape — read-only fan-out `tools_enabled=False`, or tools-enabled with **disjoint** `owned_paths`? Empty/overlapping `owned_paths` + `tools_enabled=True` silently serializes.
78. **[GATED]** Does it name only real tool names in `web_tools=[…]`? Provider names yield an agent with zero tools and confident ungrounded prose — the founding corpus defect.
79. Does it declare `NO-POOL: <reason>` when the operator has forbidden dispatch, rather than silently landing zero flywheel rows?
80. Does it respect the cost posture — `claude -p` subscription for synthesis, no metered API on operational paths, no per-call budget cap on sysadmin loops?
81. Does it forbid prompting the operator for an API key? A missing key is a provisioning escalation.

## Authoring Quality

82. Is every instruction **actionable**? "Consider X" is banned; "Check X and state the finding" is correct.
83. Is every statement **factual** — reflecting what exists, not what is planned? Planned things say "planned".
84. Does it avoid restating what an upstream command already produced — reference, never duplicate?
85. Are its citations classified — PROVENANCE (decision inline, tagged) / HOLLOW (inline the minimal decision) / DEPTH-POINTER (marked optional)? A citation the reader must open to act on is a defect.
86. Does it carry a **question bar** — ask only when the answer materially changes the artifact AND cannot be resolved from repo/convention/rules?
87. Does it carry a `Guardrails — never` section for hard prohibitions, distinct from the scope boundary? Only 5 of 31 sources do, so bare absence is NOT a finding — it is a finding when the command has hard prohibitions scattered inline that a reader must assemble themselves (`/fabrik-rivals` had eight).
88. Is it LEAN — would deleting any sentence change no agent behaviour? Delete it.
89. Does it follow `docs/reference/MD/ai-prompt-templates.md` (Part A template · Part B agentic patterns · Part C markdown rules)?

---

## Anti-patterns — defect CLASSES found live, with evidence

Each was reproduced in this corpus. Hunt them by name.

90. **Vacuous convergence loop** — the command instructs "re-run and diff until dry", but the mechanism it calls cannot re-ask. `/fabrik-rivals` Phase 2 told the agent to re-run discovery each round; the engine guards discovery with `if not discovery_done:` (`libs/competitor_intel/orchestrator.py:566`) and persists the flag per `job_id`, which the driver derives deterministically from the market. Round 2 onward could not surface a new rival BY CONSTRUCTION, so "two consecutive dry rounds" auto-satisfied at round 2 and the command reported CONVERGED. → OPEN the code the re-run calls; prove it is not a replay. Every cache, checkpoint, memo or idempotency layer between the loop and the question is a candidate.

91. **`warn_only` check with a non-zero exit path** — `argparse` calls `sys.exit(2)` on a bad flag, and `SystemExit` derives from `BaseException`, so `except Exception` does not catch it. `check_rivals_dossier.py` exited 2 on `--bogus-flag` while its own docstring claimed "always exits 0" — a BLOCKING red across ~46 repos. `check_plan_lock_release.py:454-456` had already solved it with `parse_known_args` and written down why; the new check copied its guard shape but not its parser. → PROBE every argv and root shape; never reason about it.

92. **Cross-repo hard stop misread as banning READS** — the rule governs "create/edit/**commit** files in a repo OTHER than the one you were launched in". `/fabrik-rivals` shipped a two-repo design where a project filed a brief by mail and the operator opened a hub session to run it, turning a one-rival scan into a cross-repo errand. Importing a hub module while writing only into your own tree breaks nothing. → RE-READ the rule's verbs before designing around it.

93. **Stale companion** — the command source gets fixed and its reference doc, `INDEX.md` rows, router entry and grader do not move with it. Four of five defects on `/fabrik-rivals` were this class; the reference doc still routed project agents into the two-repo workflow that had already been deleted, which is exactly how an agent got stuck. → After any contract change, walk all 22 surfaces, not just the source.

94. **Reference doc describing a superseded architecture** — the sub-case of 93 that does the most damage, because `INDEX.md` points agents *at* the doc. → Grep the doc for the vocabulary of the removed design ("two modes", "hand-off", the old flag names) after every change.

95. **Advisory output that blows the truncation budget** — ⚠️ **The historical numbers in this row are STALE and were nearly acted on again 2026-08-28.** `final_gate` no longer does a bare `[:500]`: `clip_output` (`scripts/final_gate.py:174`) keeps `head=1400` + `tail=600` = **2000 chars**, with an in-band `… [truncated: ~N line(s) omitted — tail follows] …` marker plus `truncated`/`omitted_lines` JSON fields — so the tail SURVIVES and an omission is visible. The original defect stands as history: `check_rivals_dossier`'s first draft emitted 544 into a 500-char no-ellipsis cut and lost its REMEDY line mid-word, because the budget was charged without charging the marker. **What still binds:** charge the marker up front, sweep REAL counts, and leave headroom — but MEASURE against `clip_output`'s live constants, never against the 500 quoted here. A corpus audit re-derived a truncation risk from this row and was about to cap a check's output at a budget four times smaller than the real one; the fix was to read `clip_output`, not to add the cap. → Read the constant before you engineer against it.

96. **A constant that does not mean what it says** — `line[:MAX_LINE - 1] + "..."` yields `MAX_LINE + 2` (measured 222 against a declared 220). Was present in BOTH `check_rivals_dossier.py` and `check_plan_lock_release.py` — the second inherited it by copying the first's shape; both carry `- 3` as of 2026-08-27, so this is a class to hunt, not an open defect. → Assert the invariant the constant NAMES, not the arithmetic you wrote.

97. **Fail-silent-green rebuilt inside its own fix** — `_rediscover_reset` returned `[]` for both "no checkpoint yet" and "the re-arm write FAILED"; in the second case discovery is skipped, so a VOIDED round reads as a dry one and counts toward convergence, while the driver prints "discovery re-armed". → Every error path of a truth-telling mechanism must be distinguishable from its success path.

98. **Vacuous test** — a test asserting on a field the producer never emits, a constant the module never uses, a tautology over the collection it claims to pin, or (live, twice) the wrong subject entirely: an assertion anchored on `_rediscover_reset(checkpoint_dir` matched the function DEFINITION 500 lines above its call site. Formatters make it worse — the gate's auto-formatter silently DELETED literal U+2028/U+2029 characters from a test, leaving two empty strings. → Assert the subject you mean; encode subjects as escapes, not as bytes a formatter may rewrite; and before reading a red-on-revert verdict, assert the mutation APPLIED.

99. **Data loss across a call you do not own** — the accumulated competitor union lived only in a local variable across `await run(…)`, while the engine overwrites the list mid-call and its `_persist()` is a literal dict that drops any key you add. A raise, or an operator Ctrl-C on a long scan, destroyed rivals already PAID for. → State that must survive a call you do not control goes somewhere durable BEFORE the call.

100. **Contract with no grader** — the whole class 35–44 exists because `/fabrik-user-test`, `/fabrik-service-test` and `/fabrik-rivals` each shipped a multi-condition termination contract that nothing executable ever read. → For each terminal condition, name the check that decides it, or say plainly that none does.

## Related

- `docs/reference/command-corpus-check.md` — the mechanical half (5 BLOCKING predicates + its anti-vacuity selftest)
- `docs/reference/convergence-prompts.md` — the embedded-proof templates the convergence gate expects
- `docs/reference/MD/ai-prompt-templates.md` — how to author a command body
- `.windsurf/rules/core/62-using-subagents.md` — the canonical dispatch + `web_tools` recipe
