# T06 — Shared fragments: design, deploy and certification fragments plus the design-review seat
Appetite: 150

## Scope
Implements spec § The rule test step 1 (shared-file ledgers first), steps 2-8, § Target and § How a command is cut for `design-critique.md`, `design-gate-panel.md`, `deploy-chain.md`, `cert-board-contract.md`, `cert-execution.md`, `cert-handoff-grammar.md`, `cert-visual-deliverable.md`, `autonomy-run.md`, `design-review.md` (6012 words today, `wc -w`). Each file gets `commands/_rules/_shared/<name>.yaml` with `shared: <repo path>`, and its own text is the whole file, so the ledger is asserted against the file itself and no including command loses a rule.  DO-NOT: edit any shared fragment or seat definition outside this unit, another command's source, or the tooling files `commands/command_rules.py`, `commands/assemble_commands.py`, `scripts/command_run.py`, `scripts/command_feedback_report.py`, `tests/test_command_rules.py`. Kept behavioural tests that pin its text (never edited here; each pinned phrase survives verbatim): `tests/enforcement/test_certification_coverage.py`, `tests/test_check_command_corpus.py`, `tests/test_review_loop_workflow.py`.

Depends: T05c
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_command_rules.py -q — green, one LEDGER line per ledger this ticket wrote
Gate: python3 commands/assemble_commands.py --check — exit 0, or 1 for drift only (the installed corpus stays master's until the coordinator renders at merge); never 4 (LOSS) or 5 (ceiling)
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest -q tests/test_design_critique_fragment.py tests/test_fabrik_task_queue_pass.py tests/test_frontend_design_routing.py tests/test_plan_review_queue_pass.py tests/test_plan_review_recurring_rules.py tests/test_seat_home_read_rule.py tests/test_spec_review_queue_pass.py — green
Docs: none owned (the orchestrator applies `CHANGELOG.md`, the `INDEX.md` rows for new `commands/_rules/` files and every D-row through Deltas)

## Touches
- commands/_fragments/design-critique.md
- commands/_fragments/design-gate-panel.md
- commands/_fragments/deploy-chain.md
- commands/_fragments/cert-board-contract.md
- commands/_fragments/cert-execution.md
- commands/_fragments/cert-handoff-grammar.md
- commands/_fragments/cert-visual-deliverable.md
- commands/_fragments/autonomy-run.md
- commands/_agents/design-review.md
- commands/_rules/_shared/design-critique.yaml
- commands/_rules/_shared/design-critique.baseline.txt
- commands/_rules/_shared/design-gate-panel.yaml
- commands/_rules/_shared/design-gate-panel.baseline.txt
- commands/_rules/_shared/deploy-chain.yaml
- commands/_rules/_shared/deploy-chain.baseline.txt
- commands/_rules/_shared/cert-board-contract.yaml
- commands/_rules/_shared/cert-board-contract.baseline.txt
- commands/_rules/_shared/cert-execution.yaml
- commands/_rules/_shared/cert-execution.baseline.txt
- commands/_rules/_shared/cert-handoff-grammar.yaml
- commands/_rules/_shared/cert-handoff-grammar.baseline.txt
- commands/_rules/_shared/cert-visual-deliverable.yaml
- commands/_rules/_shared/cert-visual-deliverable.baseline.txt
- commands/_rules/_shared/autonomy-run.yaml
- commands/_rules/_shared/autonomy-run.baseline.txt
- commands/_rules/_shared/design-review.yaml
- commands/_rules/_shared/design-review.baseline.txt
- commands/_size_ceiling.json
- tests/test_design_critique_fragment.py
- tests/test_fabrik_task_queue_pass.py
- tests/test_frontend_design_routing.py
- tests/test_plan_review_queue_pass.py
- tests/test_plan_review_recurring_rules.py
- tests/test_seat_home_read_rule.py
- tests/test_spec_review_queue_pass.py

## Behavior Contract
- **Given** the ledger for the shared files `design-critique.md`, `design-gate-panel.md`, `deploy-chain.md`, `cert-board-contract.md`, `cert-execution.md`, `cert-handoff-grammar.md`, `cert-visual-deliverable.md`, `autonomy-run.md`, `design-review.md` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** the shared files `design-critique.md`, `design-gate-panel.md`, `deploy-chain.md`, `cert-board-contract.md`, `cert-execution.md`, `cert-handoff-grammar.md`, `cert-visual-deliverable.md`, `autonomy-run.md`, `design-review.md` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of the shared files `design-critique.md`, `design-gate-panel.md`, `deploy-chain.md`, `cert-board-contract.md`, `cert-execution.md`, `cert-handoff-grammar.md`, `cert-visual-deliverable.md`, `autonomy-run.md`, `design-review.md` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of the shared files `design-critique.md`, `design-gate-panel.md`, `deploy-chain.md`, `cert-board-contract.md`, `cert-execution.md`, `cert-handoff-grammar.md`, `cert-visual-deliverable.md`, `autonomy-run.md`, `design-review.md`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on the shared files `design-critique.md`, `design-gate-panel.md`, `deploy-chain.md`, `cert-board-contract.md`, `cert-execution.md`, `cert-handoff-grammar.md`, `cert-visual-deliverable.md`, `autonomy-run.md`, `design-review.md`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the the shared files `design-critique.md`, `design-gate-panel.md`, `deploy-chain.md`, `cert-board-contract.md`, `cert-execution.md`, `cert-handoff-grammar.md`, `cert-visual-deliverable.md`, `autonomy-run.md`, `design-review.md` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)

## Steps
1. Record the start commit (`git rev-parse HEAD`): the baseline commit, and the frozen copy the after-window sample re-reviews with. Write each baseline from the start commit's own text: `python3 -c "import sys; sys.path.insert(0, 'commands'); import command_rules as c; from pathlib import Path; print(c.write_baseline(c.own_text(Path('<source>').read_text()), Path('<baseline.txt>')))"` for a command source, `c.write_baseline(Path('<shared file>').read_text(), …)` for a shared file; the printed sha256 is the ledger's `baseline_sha256`.
2. List the phrases the kept behavioural tests named in Scope pin in each file being cut, passing those tests as `<the tests>` (read the printed lines, never the whole test):
   `python3 -c "import ast,sys; t=' '.join(open(sys.argv[1]).read().split()); [print(f+': '+v) for f in sys.argv[2:] for n in ast.walk(ast.parse(open(f).read())) if isinstance(n,ast.Constant) and isinstance(n.value,str) for v in [' '.join(n.value.split())] if len(v)>=25 and v in t]" <the file being cut> <the tests>`
   Each printed phrase is a ledger entry with a `text` carrier and must survive verbatim; those tests are never edited here.
3. Build the ledger before cutting: one entry per rule unit (a step, an order, a ban, a threshold, a format, a refusal, a close condition), each with `id`, `file`, `section`, `baseline`, `current` and at least one carrier. `file:` paths are repo-relative (`commands/_fragments/<n>.md`), never a bare `_fragments/…`. Full form: write every entry by hand.
4. Rewrite with levers (a)-(e) of spec § How a command is cut, cutting hardest where the text drives rounds and seat work: the termination contract, the seat briefs and the per-round obligations (spec § Residual unknowns U4).
5. List the vanished units with `command_rules.vanished`. The orchestrator dispatches two author-blind seats in ONE message, one `model: "sonnet"` and one `model: "haiku"`, each briefed with only the vanished lines and the pinned rewrite. Each labels every line `rule: [ids]`, `duplicate-of: id` or `narrative`, and the orchestrator adjudicates their union into the ledger's `vanished:` map.
   Then delete each presence pin the corpus-text tests in Touches hold on this text, its phrase now a ledger carrier, in this same commit (spec § The rule test step 7); an absence pin becomes a `forbidden:` carrier or stays.
6. Count own text before and after (`command_rules.own_text` for a source, the word count for a shared file). If it is still over 50% and no further cut is possible without a LOSS, hand the orchestrator a floor D-row (live rule count × the U1 words-per-rule figure) through Deltas.
7. Lower this ticket's ceiling rows in `commands/_size_ceiling.json` only through the ratchet slice B ships (spine § Residual unknowns, R2), never by hand.
8. Run the Gate lines. A red test outside Touches is a Touches miss: hand it to the orchestrator (spine § Global Constraints), and never skip or xfail it.

## Context Files
- .windsurf/rules/core/40-documentation.md

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
