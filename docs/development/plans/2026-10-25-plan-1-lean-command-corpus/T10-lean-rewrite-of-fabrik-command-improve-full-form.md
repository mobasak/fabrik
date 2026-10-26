# T10 — Lean rewrite of /fabrik-command-improve (full form)
Appetite: 180

## Scope
Implements spec § Target, § The rule test steps 2-8 and § How a command is cut for `/fabrik-command-improve`, whose source's own text is 6378 words today (`command_rules.own_text`; the baseline is re-measured at this unit's start, spec § Target). Full form: every rule gets a hand-written entry. Its fragment `agent-feedback.md` is own text too, ledgered as `commands/_rules/_shared/<name>.yaml` (the grammar's `shared:` form, because a command ledger's baseline covers the source alone). No source includes it: the assembler appends it to every agent definition's render, keyed on its first line (`commands/assemble_commands.py:1048-1050`), so that first line, `## ⚠️ Machinery findings — SURFACE them, you cannot file them`, stays verbatim, and `tests/test_agent_definitions.py` pins its heading. The shared fragments and seat definitions it includes already carry their own ledgers and are not re-cut here. It lands L1's wording. The source says an edit must fit its command's ceiling and pass the ledger, and it treats a grouped `remove:` candidate as a ledger check, never as permission to delete (spec § Loop changes). The existing size paragraph (`commands/_sources/fabrik-command-improve.md:288-300`, `check_corpus_weight.py --check`) is reconciled with that wording, never duplicated. The unit starts only after the L2 merge (spine § Global Constraints). The `/fabrik-command-improve` hold has already lifted at the L2 merge this ticket waits on (spec § Program holds; spine § Global Constraints). DO-NOT: edit any shared fragment or seat definition outside this unit, another command's source, or the tooling files `commands/command_rules.py`, `commands/assemble_commands.py`, `scripts/command_run.py`, `scripts/command_feedback_report.py`, `tests/test_command_rules.py`. Kept behavioural tests that pin its text (never edited here; each pinned phrase survives verbatim): `tests/test_command_feedback_report.py`, `tests/test_command_improve_drive.py`.

Depends: T09
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_command_rules.py -q -rP — green; its PASSES section shows one LEDGER line per ledger this ticket wrote
Gate: python3 commands/assemble_commands.py --check — exit 0, or exit 1 only when every DRIFT line reads `DIFFERS from what this tree renders` or `MISSING` (the installed corpus stays master's until the coordinator renders at merge); any other DRIFT line (a missing D-191 dispatch step, an ORPHAN), a render `SystemExit` message, or exit 2, 4 (LOSS) or 5 (ceiling) fails
Gate: the reader-test run of spine § Global Constraints over every file this ticket cuts, with `tests/test_command_improve_queue_pass.py` added to its list — green; a red test is a Touches miss, never skipped
Docs: none owned (the orchestrator applies `CHANGELOG.md`, the `INDEX.md` rows for new `commands/_rules/` files and every D-row through Deltas)

## Touches
- commands/_sources/fabrik-command-improve.md
- commands/_fragments/agent-feedback.md
- commands/_rules/fabrik-command-improve.yaml
- commands/_rules/fabrik-command-improve.baseline.txt
- commands/_rules/_shared/agent-feedback.yaml
- commands/_rules/_shared/agent-feedback.baseline.txt
- commands/_size_ceiling.json
- tests/test_command_improve_queue_pass.py

## Behavior Contract
- **Given** the ledger for `/fabrik-command-improve` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/fabrik-command-improve` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/fabrik-command-improve` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/fabrik-command-improve`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** a presence pin in a corpus-text test on `/fabrik-command-improve`, **When** this ticket commits, **Then** the pin is deleted and its phrase is a ledger carrier, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)
- **Given** the corpus after the `/fabrik-command-improve` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** `/fabrik-command-improve`'s rewritten source, **When** an agent reads its edit contract, **Then** it states that an edit must fit its ceiling and pass the ledger, and that a `remove:` candidate is a ledger check, never permission to delete (spec § Loop changes)

## Steps
1. Record the start commit (`git rev-parse HEAD`): the baseline commit, and the frozen copy the after-window sample re-reviews with. Write each baseline from the start commit's own text: `python3 -c "import sys; sys.path.insert(0, 'commands'); import command_rules as c; from pathlib import Path; print(c.write_baseline(c.own_text(Path('<source>').read_text()), Path('<baseline.txt>')))"` for a command source, `c.write_baseline(Path('<shared file>').read_text(), …)` for a shared file; the printed sha256 is the ledger's `baseline_sha256`.
2. List the phrases the reader tests outside this ticket's Touches (spine § Global Constraints) pin in each file being cut, passing them as `<the tests>` (read the printed lines, never the whole test):
   `python3 -c "import ast,sys; t=' '.join(open(sys.argv[1]).read().split()); [print(f+': '+v) for f in sys.argv[2:] for n in ast.walk(ast.parse(open(f).read())) if isinstance(n,ast.Constant) and isinstance(n.value,str) for v in [' '.join(n.value.split())] if len(v)>=25 and v in t]" <the file being cut> <the tests>`
   Each printed phrase is a ledger entry with a `text` carrier and must survive verbatim; those tests are never edited here.
3. Build the ledger before cutting: one entry per rule unit (a step, an order, a ban, a threshold, a format, a refusal, a close condition), each with `id`, `file`, `section`, `baseline`, `current` and at least one carrier. `file:` paths are repo-relative (`commands/_fragments/<n>.md`), never a bare `_fragments/…`; a rule in a command source omits `file:`, which defaults to the render. Full form: write every remaining entry by hand, beside the pin entries a migration part already wrote, never a second entry for one rule.
4. Rewrite with levers (a)-(e) of spec § How a command is cut, cutting hardest where the text drives rounds and seat work: the termination contract, the seat briefs and the per-round obligations (spec § Residual unknowns U4).
5. List the vanished units: `c.vanished(c._read_baseline(Path('<baseline.txt>').read_bytes()), <new own text>)`, the new own text being `c.own_text(…)` of the source, or a shared file's whole text. The orchestrator dispatches two author-blind seats in ONE message, one `model: "sonnet"` and one `model: "haiku"`, each briefed with only the vanished lines and the pinned rewrite. Each labels every line `rule: [ids]`, `duplicate-of: id` or `narrative`, and the orchestrator adjudicates their union into the ledger's `vanished:` map.
   Then delete each presence pin the corpus-text tests in Touches hold on this text, its phrase now a ledger carrier, in this same commit (spec § The rule test step 7); an absence pin becomes a `forbidden:` carrier or stays.
6. Count own text before and after (`command_rules.own_text` for a source, the word count for a shared file). If it is still over 50% and no further cut is possible without a LOSS, hand the orchestrator a floor D-row (live rule count × the U1 words-per-rule figure) through Deltas.
7. Lower this ticket's ceiling rows in `commands/_size_ceiling.json` only through the text-measure merge's ratchet (`docs/reference/command-corpus-check.md` § Rule ledger; spine § Residual unknowns R2), never by hand.
8. Run the Gate lines. A red test outside Touches is a Touches miss: hand it to the orchestrator (spine § Global Constraints), and never skip or xfail it.

## Context Files
- .windsurf/rules/core/40-documentation.md

> Tooling API (W-a9b5e763 slice A, on master since merge bc2a9c30b, D-1221; cited by symbol because review fixes move its lines): `commands/command_rules.py::own_text(source)` returns a source's own text, no included fragment text in it · `commands/command_rules.py::write_baseline(text, out)` writes the unit keys and returns the sha256 for `baseline_sha256:` · `commands/command_rules.py::vanished(baseline, current_text)` lists the 1-based baseline lines with no exact match · `commands/command_rules.py::losses(render_dir, root, src_dir)` is what `--check` and `tests/test_command_rules.py` assert. infra-2's text-measure merge adds `command_rules.generate_unchanged(baseline_path, new_own_text) -> [entry]`, the measure and `commands/_size_ceiling.json` with `--check` exit 5 (spine § Interfaces).

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

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:362` — Before a command's own phase, `/fabrik-command-improve` may not grow it. An edit that would grow it is queued to

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:363` — that phase, not paid for with deletions. The `/fabrik-command-improve` text says that an edit must fit its

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:364` — ceiling and pass the ledger. Three kinds of addition are exempt from that queueing:

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:365` — - the program's own landed text: the `remove:` wording and the ceiling sentence;

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:366` — - a clause landed under a D-row, such as infra-2's lane clause (W-a0a32de2);

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:367` — - a P0 fix.

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:368` — 

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:369` — The exempt text is then part of the baseline its command's phase measures.

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:373` — - **L2: the remove field.** The FEEDBACK verdict gains a fifth required field: `remove: "<a sentence quoted

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:374` — verbatim from the rendered command>" | none`. `command_run.py` refuses a quote that is absent from the render.

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:375` — The digest groups `remove:` rows by phrase, so N runs naming one sentence become a deletion candidate with

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:376` — evidence. `/fabrik-command-improve` treats a candidate as a ledger check, never as permission to delete. This is

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:377` — the only new close grammar the program adds.
