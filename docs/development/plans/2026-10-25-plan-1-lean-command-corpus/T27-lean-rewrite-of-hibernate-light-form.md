# T27 — Lean rewrite of /hibernate (light form)
Appetite: 60

## Scope
Implements spec § Target, § The rule test steps 2-8 and 9 and § How a command is cut for `/hibernate`, whose source's own text is 877 words today (`command_rules.own_text`; the baseline is re-measured at this unit's start, spec § Target). Light form (spec § The rule test step 9): after the rewrite, `command_rules.generate_unchanged` writes the entries for the units that survived unchanged, and the seats classify only the vanished units and write carriers only for reworded rules. The shared fragments and seat definitions it includes already carry their own ledgers and are not re-cut here.  DO-NOT: edit any shared fragment or seat definition outside this unit, another command's source, or the tooling files `commands/command_rules.py`, `commands/assemble_commands.py`, `scripts/command_run.py`, `scripts/command_feedback_report.py`, `tests/test_command_rules.py`.

Depends: T26
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_command_rules.py -q -rP — green; its PASSES section shows one LEDGER line per ledger this ticket wrote
Gate: python3 commands/assemble_commands.py --check — exit 0, or exit 1 only when every DRIFT line reads `DIFFERS from what this tree renders` or `: MISSING in` (the installed corpus stays master's until the coordinator renders at merge); any other DRIFT line (a missing D-191 dispatch step, an ORPHAN), a render `SystemExit` message, or exit 2, 4 (LOSS) or 5 (ceiling) fails
Gate: the reader-test run of spine § Global Constraints over every file this ticket cuts — green; a red test is a Touches miss, never skipped
Docs: none owned (the orchestrator applies `CHANGELOG.md`, the `INDEX.md` rows for new `commands/_rules/` files and every D-row through Deltas)

## Touches
- commands/_sources/hibernate.md
- commands/_rules/hibernate.yaml
- commands/_rules/hibernate.baseline.txt
- commands/_size_ceiling.json

## Behavior Contract
- **Given** the ledger for `/hibernate` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** `/hibernate` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or a floor D-row names the shortfall (spec § Target)
- **Given** every baseline unit of `/hibernate` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of `/hibernate`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** the corpus after the `/hibernate` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)

## Steps
1. Record the start commit (`git rev-parse HEAD`): the baseline commit, and the frozen copy the after-window sample re-reviews with. Write each baseline from the start commit's own text: `python3 -c "import sys; sys.path.insert(0, 'commands'); import command_rules as c; from pathlib import Path; print(c.write_baseline(c.own_text(Path('<source>').read_text()), Path('<baseline.txt>')))"` for a command source, `c.write_baseline(Path('<shared file>').read_text(), …)` for a shared file; the printed sha256 is the ledger's `baseline_sha256`.
2. List the phrases the reader tests (spine § Global Constraints) pin in each file being cut, passing them as `<the tests>` (read the printed lines, never the whole test):
   `python3 -c "import ast,sys; t=' '.join(open(sys.argv[1]).read().split()); [print(f+': '+v) for f in sys.argv[2:] for n in ast.walk(ast.parse(open(f).read())) if isinstance(n,ast.Constant) and isinstance(n.value,str) for v in [' '.join(n.value.split())] if len(v)>=25 and v in t]" <the file being cut> <the tests>`
   Each printed phrase is a ledger entry with a `text` carrier and must survive verbatim; those tests are never edited here.
3. Build the ledger before cutting: one entry per rule unit (a step, an order, a ban, a threshold, a format, a refusal, a close condition), each with `id`, `file`, `section`, `baseline`, `current` and at least one carrier. `file:` paths are repo-relative (`commands/_fragments/<n>.md`), never a bare `_fragments/…`; a rule in a command source omits `file:`, which defaults to the render. Light form: after step 4, `command_rules.generate_unchanged(baseline_path, new_own_text)` returns the entries for the unchanged units, which go into the ledger's `entries:`; hand-write carriers only for reworded rules.
4. Rewrite with levers (a)-(e) of spec § How a command is cut, cutting hardest where the text drives rounds and seat work: the termination contract, the seat briefs and the per-round obligations (spec § Residual unknowns U4).
5. List the vanished units: `c.vanished(c._read_baseline(Path('<baseline.txt>').read_bytes()), <new own text>)`, the new own text being `c.own_text(…)` of the source, or a shared file's whole text. The orchestrator dispatches two author-blind seats in ONE message, one `model: "sonnet"` and one `model: "haiku"`, each briefed with only the vanished lines and the pinned rewrite. Each labels every line `rule: [ids]`, `duplicate-of: id` or `narrative`, and the orchestrator adjudicates their union into the ledger's `vanished:` map.
6. Count own text before and after (`command_rules.own_text` for a source, the word count for a shared file). If it is still over 50% and no further cut is possible without a LOSS, hand the orchestrator a floor D-row (live rule count × the U1 words-per-rule figure) through Deltas.
7. Lower this ticket's ceiling rows in `commands/_size_ceiling.json` only through the text-measure merge's ratchet (`docs/reference/command-corpus-check.md` § Rule ledger; spine § Residual unknowns R2), never by hand.
8. Run the Gate lines. A red test outside Touches is a Touches miss: hand it to the orchestrator (spine § Global Constraints), and never skip or xfail it.

## Context Files
- .windsurf/rules/core/40-documentation.md

> Tooling API (W-a9b5e763 slice A, on master since merge bc2a9c30b, D-1221; cited by symbol because review fixes move its lines): `commands/command_rules.py::own_text(source)` blanks every `{{include:}}` line · `commands/command_rules.py::write_baseline(text, out)` writes the unit keys and returns the sha256 for `baseline_sha256:` · `commands/command_rules.py::vanished(baseline, current_text)` lists the 1-based baseline lines with no exact match · `commands/command_rules.py::losses(render_dir, root, src_dir)` is what `--check` and `tests/test_command_rules.py` assert. infra-2's text-measure merge adds `command_rules.generate_unchanged(baseline_path, new_own_text) -> [entry]`, the measure and `commands/_size_ceiling.json` with `--check` exit 5 (spine § Interfaces).

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

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:239` — 9. **The tail.** A command outside the top four (741 of the 3,072 hours since 09-21, combined) may use the light

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:240` — form. Every rule still gets a ledger entry and the standing gate. In the light form:

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:241` — - a rule whose baseline sentence survives unchanged gets its entry generated by script, as a `text` carrier

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:242` — copied from that sentence;

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:243` — - the seats classify only the vanished sentences and write carriers only for reworded rules.
