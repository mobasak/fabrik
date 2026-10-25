# T07a — Lean rewrite of /fabrik-review (full form) — ledger and pin migration, part a
Appetite: 60

## Scope
Migration part a of the Lean rewrite of /fabrik-review (full form) unit (spec § The rule test steps 3 and 7). It moves the presence pins that the tests below hold on `/fabrik-review` into the unit's ledger and deletes them from the tests, so the unit's rewrite ticket edits text only. It cuts no text. DO-NOT: edit `commands/_sources/fabrik-review.md`, another unit's ledger, or the tooling files `commands/command_rules.py`, `commands/assemble_commands.py`, `scripts/command_run.py`, `scripts/command_feedback_report.py`, `tests/test_command_rules.py`.

Depends: T06
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_command_rules.py -q — green, one LEDGER line per ledger this ticket wrote
Gate: python3 commands/assemble_commands.py --check — exit 0, or 1 for drift only (the installed corpus stays master's until the coordinator renders at merge); never 4 (LOSS) or 5 (ceiling)
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest -q tests/test_review_queue_pass.py tests/test_review_scoped_queue_pass.py — green
Docs: none owned (the orchestrator applies `CHANGELOG.md`, the `INDEX.md` rows for new `commands/_rules/` files and every D-row through Deltas)

## Touches
- commands/_rules/fabrik-review.yaml
- commands/_rules/fabrik-review.baseline.txt
- tests/test_review_queue_pass.py
- tests/test_review_scoped_queue_pass.py

## Behavior Contract
- **Given** `/fabrik-review` at the unit's start commit, **When** its baseline and ledger are written before any cut, **Then** `tests/test_command_rules.py` prints its LEDGER line with zero LOSS lines and the files are byte-identical to the start commit (spec § The rule test)
- **Given** the presence pins on `/fabrik-review` in the tests of migration part a, **When** this ticket commits, **Then** each is deleted and its phrase is a carrier in the ledger, and an absence pin is a `forbidden:` carrier or stays (spec § The rule test)

## Steps
1. Record the start commit (`git rev-parse HEAD`), the unit's baseline commit. Write each baseline from it: `python3 -c "import sys; sys.path.insert(0, 'commands'); import command_rules as c; from pathlib import Path; print(c.write_baseline(c.own_text(Path('<source>').read_text()), Path('<baseline.txt>')))"` for a command source, `c.write_baseline(Path('<shared file>').read_text(), …)` for a shared file; the printed sha256 is the ledger's `baseline_sha256`. Then write the ledger's entries for every rule unit (a step, an order, a ban, a threshold, a format, a refusal, a close condition), each with `id`, `file`, `section`, `baseline`, `current` and at least one carrier; `file:` paths are repo-relative (`commands/_fragments/<n>.md`), never a bare `_fragments/…`.
2. List each Touches test's literals that occur in the files this unit cuts, passing the Touches tests as `<the tests>`:
   `python3 -c "import ast,sys; t=' '.join(open(sys.argv[1]).read().split()); [print(f+': '+v) for f in sys.argv[2:] for n in ast.walk(ast.parse(open(f).read())) if isinstance(n,ast.Constant) and isinstance(n.value,str) for v in [' '.join(n.value.split())] if len(v)>=25 and v in t]" <the file being cut> <the tests>`
   Each printed phrase that a presence assert pins becomes a ledger entry (`text` carrier, `current` = the sentence holding it); each phrase an absence assert pins becomes a `forbidden:` carrier.
3. Delete each migrated presence assert from its test in this same commit (spec § The rule test step 7). Absence asserts may stay. A test function left with no assert is deleted.
4. Cut nothing here: the source and shared files are byte-identical at this ticket's close.
5. Run the Gate lines.

## Context Files
- .windsurf/rules/core/40-documentation.md
- commands/_sources/fabrik-review.md

> Tooling API (W-a9b5e763 slice A, on master since merge bc2a9c30b, D-1221; cited by symbol because review fixes move its lines): `commands/command_rules.py::own_text(source)` blanks every `{{include:}}` line · `commands/command_rules.py::write_baseline(text, out)` writes the unit keys and returns the sha256 for `baseline_sha256:` · `commands/command_rules.py::vanished(baseline, current_text)` lists the 1-based baseline lines with no exact match · `commands/command_rules.py::losses(render_dir, root, src_dir)` is what `--check` and `tests/test_command_rules.py` assert. Slice B adds `command_rules.generate_unchanged(baseline_path, new_own_text) -> [entry]`, the measure and `commands/_size_ceiling.json` with `--check` exit 5.

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

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:282` — - **T2, the closing pass, stated once:** D-335 as written. A slice with no open claim is restated, not

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:283` — re-dispatched. Any added condition is a rule change.

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:284` — - **T5, the per-round obligations, scripted and stated once:** the lead's hygiene, pin, md5 and ledger-row steps,

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:285` — scripted where a script exists.

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:286` — - **T6, overlap:** the lead executes each returned seat's candidates while slower seats still run. The full union

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:287` — is kept, and no seat is cut short.

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:291` — - **T1, one finder per slice instead of the D-344 pair.**

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:292` — - It applies only where that pair exists: the partitioned loops, `/fabrik-review` and `/fabrik-repo-review`.

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:293` — - It never touches `/fabrik-review-scoped`, whose units-sized three-seat floor (D-186, D-208) stays.

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:294` — - It cuts seat-minutes and tokens, not wall-clock, because paired seats run in parallel.

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:295` — - It is proposed only on D-344's own measure, confirmed candidates per seat, which intel produces before any T1

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:296` — decision.

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:297` — - It is the one lever that can lose recall, so it is trialled in `/fabrik-review`'s phase (§ Order step 4), and

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:298` — its D-row is provisional. T1 spreads to the other partitioned loop only when `/fabrik-review`'s after-window

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:299` — report shows two things: confirmed defects per run at or above the before window's, and no rise on the frozen

> `docs/superpowers/specs/2026-10-25-lean-command-corpus-design.md:300` — sample below. Otherwise the panel reverts T1 by a new D-row.
