# T05b — Shared fragments: subagents-core and the grounding, intake and test-loop fragments — ledger and pin migration, part b
Appetite: 60

## Scope
Migration part b of the Shared fragments: subagents-core and the grounding, intake and test-loop fragments unit (spec § The rule test steps 3 and 7). It moves the presence pins that the tests below hold on the shared files `subagents-core.md`, `delegated-reads.md`, `grounding-artifact.md`, `grounding-code.md`, `grounding-rules.md`, `questionbar.md`, `injection.md`, `test-generation-loop.md`, `chat-intake.md`, `repo-identity.md` into the unit's ledger and deletes them from the tests, so the unit's rewrite ticket edits text only. It cuts no text. DO-NOT: edit `commands/_fragments/subagents-core.md`, `commands/_fragments/delegated-reads.md`, `commands/_fragments/grounding-artifact.md`, `commands/_fragments/grounding-code.md`, `commands/_fragments/grounding-rules.md`, `commands/_fragments/questionbar.md`, `commands/_fragments/injection.md`, `commands/_fragments/test-generation-loop.md`, `commands/_fragments/chat-intake.md`, `commands/_fragments/repo-identity.md`, another unit's ledger, or the tooling files `commands/command_rules.py`, `commands/assemble_commands.py`, `scripts/command_run.py`, `scripts/command_feedback_report.py`, `tests/test_command_rules.py`.

Depends: T05a
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_command_rules.py -q — green, one LEDGER line per ledger this ticket wrote
Gate: python3 commands/assemble_commands.py --check — exit 0, or 1 for drift only (the installed corpus stays master's until the coordinator renders at merge); never 4 (LOSS) or 5 (ceiling)
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest -q tests/test_plan_review_queue_pass.py tests/test_review_command_text_defects.py tests/test_run_scratch_brief_wording.py tests/test_spec_plan_lane_text.py tests/test_spec_review_queue_pass.py — green
Docs: none owned (the orchestrator applies `CHANGELOG.md`, the `INDEX.md` rows for new `commands/_rules/` files and every D-row through Deltas)

## Touches
- commands/_rules/_shared/subagents-core.yaml
- commands/_rules/_shared/subagents-core.baseline.txt
- commands/_rules/_shared/delegated-reads.yaml
- commands/_rules/_shared/delegated-reads.baseline.txt
- commands/_rules/_shared/grounding-artifact.yaml
- commands/_rules/_shared/grounding-artifact.baseline.txt
- commands/_rules/_shared/grounding-code.yaml
- commands/_rules/_shared/grounding-code.baseline.txt
- commands/_rules/_shared/grounding-rules.yaml
- commands/_rules/_shared/grounding-rules.baseline.txt
- commands/_rules/_shared/questionbar.yaml
- commands/_rules/_shared/questionbar.baseline.txt
- commands/_rules/_shared/injection.yaml
- commands/_rules/_shared/injection.baseline.txt
- commands/_rules/_shared/test-generation-loop.yaml
- commands/_rules/_shared/test-generation-loop.baseline.txt
- commands/_rules/_shared/chat-intake.yaml
- commands/_rules/_shared/chat-intake.baseline.txt
- commands/_rules/_shared/repo-identity.yaml
- commands/_rules/_shared/repo-identity.baseline.txt
- tests/test_plan_review_queue_pass.py
- tests/test_review_command_text_defects.py
- tests/test_run_scratch_brief_wording.py
- tests/test_spec_plan_lane_text.py
- tests/test_spec_review_queue_pass.py

## Behavior Contract
- **Given** the presence pins on the shared files `subagents-core.md`, `delegated-reads.md`, `grounding-artifact.md`, `grounding-code.md`, `grounding-rules.md`, `questionbar.md`, `injection.md`, `test-generation-loop.md`, `chat-intake.md`, `repo-identity.md` in the tests of migration part b, **When** this ticket commits, **Then** each is deleted and its phrase is a carrier in the ledger, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)

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
- commands/_fragments/subagents-core.md
- commands/_fragments/delegated-reads.md
- commands/_fragments/grounding-artifact.md
- commands/_fragments/grounding-code.md
- commands/_fragments/grounding-rules.md
- commands/_fragments/questionbar.md
- commands/_fragments/injection.md
- commands/_fragments/test-generation-loop.md
- commands/_fragments/chat-intake.md
- commands/_fragments/repo-identity.md

> Tooling API (W-a9b5e763 slice A, on master since merge bc2a9c30b, D-1221; cited by symbol because review fixes move its lines): `commands/command_rules.py::own_text(source)` blanks every `{{include:}}` line · `commands/command_rules.py::write_baseline(text, out)` writes the unit keys and returns the sha256 for `baseline_sha256:` · `commands/command_rules.py::vanished(baseline, current_text)` lists the 1-based baseline lines with no exact match · `commands/command_rules.py::losses(render_dir, root, src_dir)` is what `--check` and `tests/test_command_rules.py` assert. Slice B adds `command_rules.generate_unchanged(baseline_path, new_own_text) -> [entry]`, the measure and `commands/_size_ceiling.json` with `--check` exit 5.

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
