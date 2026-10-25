# T01b — Pilot shared files: the fragments and seat definitions /fabrik-review-scoped shares — ledger and pin migration, part b
Appetite: 60

## Scope
Migration part b of the Pilot shared files: the fragments and seat definitions /fabrik-review-scoped shares unit (spec § The rule test steps 3 and 7). It moves the presence pins that the tests below hold on the shared files `no-workflow-hub.md`, `run-record.md`, `orient.md`, `close-chain.md`, `close-feedback.md`, `review-probe-catalogue.md`, `fabrik-reviewer.md`, `fabrik-researcher.md`, `fabrik-gui.md` into the unit's ledger and deletes them from the tests, so the unit's rewrite ticket edits text only. It cuts no text. DO-NOT: edit `commands/_fragments/no-workflow-hub.md`, `commands/_fragments/run-record.md`, `commands/_fragments/orient.md`, `commands/_fragments/close-chain.md`, `commands/_fragments/close-feedback.md`, `commands/_fragments/review-probe-catalogue.md`, `commands/_agents/fabrik-reviewer.md`, `commands/_agents/fabrik-researcher.md`, `commands/_agents/fabrik-gui.md`, another unit's ledger, or the tooling files `commands/command_rules.py`, `commands/assemble_commands.py`, `scripts/command_run.py`, `scripts/command_feedback_report.py`, `tests/test_command_rules.py`.

Depends: T01a
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_command_rules.py -q -rP — green; its PASSES section shows one LEDGER line per ledger this ticket wrote
Gate: python3 commands/assemble_commands.py --check — exit 0, or exit 1 only when every DRIFT line reads `DIFFERS from what this tree renders` or `: MISSING in` (the installed corpus stays master's until the coordinator renders at merge); any other DRIFT line (a missing D-191 dispatch step, an ORPHAN), a render `SystemExit` message, or exit 2, 4 (LOSS) or 5 (ceiling) fails
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest -q tests/test_command_improve_queue_pass.py tests/test_fabrik_task_queue_pass.py tests/test_plan_review_queue_pass.py tests/test_spec_plan_lane_text.py — green
Docs: none owned (the orchestrator applies `CHANGELOG.md`, the `INDEX.md` rows for new `commands/_rules/` files and every D-row through Deltas)

## Touches
- commands/_rules/_shared/no-workflow-hub.yaml
- commands/_rules/_shared/no-workflow-hub.baseline.txt
- commands/_rules/_shared/run-record.yaml
- commands/_rules/_shared/run-record.baseline.txt
- commands/_rules/_shared/orient.yaml
- commands/_rules/_shared/orient.baseline.txt
- commands/_rules/_shared/close-chain.yaml
- commands/_rules/_shared/close-chain.baseline.txt
- commands/_rules/_shared/close-feedback.yaml
- commands/_rules/_shared/close-feedback.baseline.txt
- commands/_rules/_shared/review-probe-catalogue.yaml
- commands/_rules/_shared/review-probe-catalogue.baseline.txt
- commands/_rules/_shared/fabrik-reviewer.yaml
- commands/_rules/_shared/fabrik-reviewer.baseline.txt
- commands/_rules/_shared/fabrik-researcher.yaml
- commands/_rules/_shared/fabrik-researcher.baseline.txt
- commands/_rules/_shared/fabrik-gui.yaml
- commands/_rules/_shared/fabrik-gui.baseline.txt
- tests/test_command_improve_queue_pass.py
- tests/test_fabrik_task_queue_pass.py
- tests/test_plan_review_queue_pass.py
- tests/test_spec_plan_lane_text.py

## Behavior Contract
- **Given** the presence pins on the shared files `no-workflow-hub.md`, `run-record.md`, `orient.md`, `close-chain.md`, `close-feedback.md`, `review-probe-catalogue.md`, `fabrik-reviewer.md`, `fabrik-researcher.md`, `fabrik-gui.md` in the tests of migration part b, **When** this ticket commits, **Then** each is deleted and its phrase is a carrier in the ledger, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)

## Steps
1. The baseline and ledger already exist from part a; extend the ledger, never rewrite its baseline.
2. List each Touches test's literals that occur in the files this unit cuts, passing the Touches tests as `<the tests>`:
   `python3 -c "import ast,sys; t=' '.join(open(sys.argv[1]).read().split()); [print(f+': '+v) for f in sys.argv[2:] for n in ast.walk(ast.parse(open(f).read())) if isinstance(n,ast.Constant) and isinstance(n.value,str) for v in [' '.join(n.value.split())] if len(v)>=25 and v in t]" <the file being cut> <the tests>`
   Each printed phrase that a presence assert pins becomes a ledger entry (`text` carrier, `current` = the sentence holding it); each phrase an absence assert pins becomes a `forbidden:` carrier.
3. Delete each migrated presence assert from its test in this same commit (spec § The rule test step 7). Absence asserts may stay. A test function left with no assert is deleted.
4. Cut nothing here: the source and shared files are byte-identical at this ticket's close.
5. Run the Gate lines.

## Context Files
- .windsurf/rules/core/40-documentation.md
- commands/_fragments/no-workflow-hub.md
- commands/_fragments/run-record.md
- commands/_fragments/orient.md
- commands/_fragments/close-chain.md
- commands/_fragments/close-feedback.md
- commands/_fragments/review-probe-catalogue.md
- commands/_agents/fabrik-reviewer.md
- commands/_agents/fabrik-researcher.md
- commands/_agents/fabrik-gui.md

> Tooling API (W-a9b5e763 slice A, on master since merge bc2a9c30b, D-1221; cited by symbol because review fixes move its lines): `commands/command_rules.py::own_text(source)` blanks every `{{include:}}` line · `commands/command_rules.py::write_baseline(text, out)` writes the unit keys and returns the sha256 for `baseline_sha256:` · `commands/command_rules.py::vanished(baseline, current_text)` lists the 1-based baseline lines with no exact match · `commands/command_rules.py::losses(render_dir, root, src_dir)` is what `--check` and `tests/test_command_rules.py` assert. infra-2's text-measure merge adds `command_rules.generate_unchanged(baseline_path, new_own_text) -> [entry]`, the measure and `commands/_size_ceiling.json` with `--check` exit 5 (spine § Interfaces).

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:166` — 1. **Shared-file ledgers first.** Every file under `commands/` that more than one command's own text contains

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:167` — gets its own ledger, `commands/_rules/_shared/<file>.yaml`, before it is cut. That covers four routes:

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:168` — - a fragment pulled in by `{{include:`: 24 fragments today, counted over `commands/_sources/*.md`;

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:125` — this program creates or grows for a command. Each command reaches at most 50% of its own-text baseline, or the

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:126` — floor its ledger sets (§ Binding, KILL). A file outside `commands/` that another beat owns stays in the full

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:177` — 2. **Completeness by construction.** At the phase start a script splits the baseline own text into sentences and

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:178` — diffs them against the rewrite. **Every baseline sentence with no surviving match must be classified** as one

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:179` — of:

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:184` — Two author-blind seats (one Sonnet, one Haiku) classify the vanished sentences, and the lead adjudicates their

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:185` — union. Recall therefore does not depend on a seat noticing every rule in 27k words. A deleted sentence with no

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:186` — classification fails the test. How much rewording still counts as a surviving match is U2.

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:232` — 7. **Retiring pins.** A presence pin whose rule is now a ledger entry is deleted in the same commit. Absence pins

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:233` — become `forbidden:` carriers or stay.

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:234` — 8. **A rule removed on purpose** needs a D-row that names its ledger id, and the entry moves to a `retired:`

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:235` — list. It is never deleted silently. **A rule CHANGED on purpose** (a § Time budget rule change) keeps its

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:336` — - **(a) Remove narrative.** Incident stories, dates, mail ids, "measured: …" anecdotes and decision ids cited as

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:337` — history all go (D-331). Keep a narrative clause only when it is the rule's one-clause reason, the sentence that

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:338` — defines the class the rule covers. For example, keep "a grader constructs the rows it needs, so it only tests

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:345` — - **(d) Write positive imperatives with a one-clause reason**, per the Anthropic guidance above. A NEVER or

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:346` — refusal clause keeps its ban verbatim.

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:307` — - **T4, briefs carry the question and the pin, not the command's rules.** The house rules stay in

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:308` — `commands/_agents/fabrik-reviewer.md`, which is the seat's only rule source under D-344(1)'s `omitClaudeMd`. The

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:309` — pilot phase (§ Order step 2) ledgers and cuts that definition, so T4 is decided there.

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:393` — 2. **Pilot: `/fabrik-review-scoped`** (1,120 runs, 9,551 words, about a third of `/fabrik-review`'s size). The

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:394` — fragments it includes are `no-workflow-hub`, `run-record`, `orient`, `scope-growth-exit` and `close-chain`,

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:395` — plus the auto-appended `close-feedback`. It also reads `review-probe-catalogue` and dispatches the

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:396` — `fabrik-reviewer`, `fabrik-researcher` and `fabrik-gui` definitions. Every one of those that

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:397` — another command's own text also contains gets its ledger in this phase, before the pilot cuts it: all but

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:398` — `scope-growth-exit`. The pilot shakes out the YAML grammar, the audit pair and

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:399` — the ceilings.
