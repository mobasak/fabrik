# T02 — Lean rewrite of /fabrik-review-scoped (full form)
Appetite: 210

## Scope
Implements spec § Target, § The rule test steps 2-8 and § How a command is cut for `/fabrik-review-scoped`, whose source's own text is 5103 words today (`command_rules.own_text`; the baseline is re-measured at this unit's start, spec § Target). Full form: every rule gets a hand-written entry. Its single-command fragment `scope-growth-exit.md` is own text too, ledgered as `commands/_rules/_shared/<name>.yaml` (the grammar's `shared:` form, because a command ledger's baseline covers the source alone). The shared fragments and seat definitions it includes already carry their own ledgers and are not re-cut here. This unit closes the pilot (spec § Order step 2). The program KILL test runs here over the pilot's whole own text: the source plus the shared files the pilot shared-file unit cut. The pilot's words per rule (live own-text words ÷ live ledger entries) goes to the orchestrator for the U1 D-row. Lever T1 never applies here (spec § Time budget). As the first unit to set a `render` ceiling row, it shakes out the ceiling ratchet. DO-NOT: edit any shared fragment or seat definition outside this unit, another command's source, or the tooling files `commands/command_rules.py`, `commands/assemble_commands.py`, `scripts/command_run.py`, `scripts/command_feedback_report.py`, `tests/test_command_rules.py`. Kept behavioural tests that pin its text (never edited here; each pinned phrase survives verbatim): `tests/test_assemble_dispatch_step.py`, `tests/test_governance_template_split.py`, `tests/test_review_loop_workflow.py`.

Depends: T01d
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_command_rules.py -q — green, one LEDGER line per ledger this ticket wrote
Gate: python3 commands/assemble_commands.py --check — exit 0, or 1 for drift only (the installed corpus stays master's until the coordinator renders at merge); never 4 (LOSS) or 5 (ceiling)
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest -q tests/test_command_improve_queue_pass.py tests/test_review_command_text_defects.py tests/test_review_scoped_queue_pass.py tests/test_spec_review_queue_pass.py — green
Docs: none owned (the orchestrator applies `CHANGELOG.md`, the `INDEX.md` rows for new `commands/_rules/` files and every D-row through Deltas)

## Touches
- commands/_sources/fabrik-review-scoped.md
- commands/_fragments/scope-growth-exit.md
- commands/_rules/fabrik-review-scoped.yaml
- commands/_rules/fabrik-review-scoped.baseline.txt
- commands/_rules/_shared/scope-growth-exit.yaml
- commands/_rules/_shared/scope-growth-exit.baseline.txt
- commands/_size_ceiling.json
- tests/test_command_improve_queue_pass.py
- tests/test_review_command_text_defects.py
- tests/test_review_scoped_queue_pass.py
- tests/test_spec_review_queue_pass.py

## Behavior Contract
- **Given** the ledger for `/fabrik-review-scoped` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-review-scoped` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-review-scoped` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-review-scoped`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-review-scoped`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-review-scoped` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the pilot's whole own text (`/fabrik-review-scoped`'s source plus the pilot shared files), **When** it is measured against its baseline with a green rule test, **Then** it is at or under 60%, or the orchestrator stops the program by the KILL clause; and words per rule (live words ÷ live entries) goes to the U1 D-row (spec § Binding)

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

> Tooling API (W-a9b5e763 slice A, branch `w-a9b5e763-lean-tooling`, D-1221, merged before the first ticket starts; cited by symbol because review fixes move its lines): `commands/command_rules.py::own_text(source)` blanks every `{{include:}}` line · `commands/command_rules.py::write_baseline(text, out)` writes the unit keys and returns the sha256 for `baseline_sha256:` · `commands/command_rules.py::vanished(baseline, current_text)` lists the 1-based baseline lines with no exact match · `commands/command_rules.py::losses(render_dir, root, src_dir)` is what `--check` and `tests/test_command_rules.py` assert. Slice B adds `command_rules.generate_unchanged(baseline_path, new_own_text) -> [entry]`, the measure and `commands/_size_ceiling.json` with `--check` exit 5.

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:125` — this program creates or grows for a command. Each command reaches at most 50% of its own-text baseline, or the

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:126` — floor its ledger sets (§ Binding, KILL). A file outside `commands/` that another beat owns stays in the full

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:129` — The baseline is measured at the start of the command's own phase, never at spec approval. kaizen keeps editing

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:130` — commands until then, and a ledger cut early would miss rules added later. The coordinator freezes non-program

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:131` — edits to a command while its phase runs. A command meets the target only when its rule test is green at the

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

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:393` — 2. **Pilot: `/fabrik-review-scoped`** (1,120 runs, 9,551 words, about a third of `/fabrik-review`'s size). The

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:394` — fragments it includes are `no-workflow-hub`, `run-record`, `orient`, `scope-growth-exit` and `close-chain`,

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:395` — plus the auto-appended `close-feedback`. It also reads `review-probe-catalogue` and dispatches the

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:396` — `fabrik-reviewer`, `fabrik-researcher` and `fabrik-gui` definitions. Every one of those that

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:397` — another command's own text also contains gets its ledger in this phase, before the pilot cuts it: all but

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:398` — `scope-growth-exit`. The pilot shakes out the YAML grammar, the audit pair and

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:399` — the ceilings.

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:495` — KILL: there is no per-command KILL. A command that cannot reach 50% without a LOSS stops at a **recorded floor**,

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:496` — written as a D-row: its live rule count × the words-per-rule figure U1 defines.

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:497` — The program as a whole is killed if the pilot cannot reach 60% of its own-text baseline with a green rule test.

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:467` — - **U1 — the words-per-rule figure behind the floor** is unknown until the pilot lands. The resolution: the

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:468` — pilot's own words per rule, recorded by kaizen in the pilot phase's D-row, is used until any command reaches

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:469` — 50%; from then on it is the median over the commands that reached 50% (§ Binding, KILL).
