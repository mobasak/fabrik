# T01d — Pilot shared files: the fragments and seat definitions /fabrik-review-scoped shares — the rewrite
Appetite: 210

## Scope
Implements spec § The rule test step 1 (shared-file ledgers first), steps 2-8, § Target and § How a command is cut for `no-workflow-hub.md`, `run-record.md`, `orient.md`, `close-chain.md`, `close-feedback.md`, `review-probe-catalogue.md`, `fabrik-reviewer.md`, `fabrik-researcher.md`, `fabrik-gui.md` (16463 words today, `wc -w`). Each file gets `commands/_rules/_shared/<name>.yaml` with `shared: <repo path>`, and its own text is the whole file, so the ledger is asserted against the file itself and no including command loses a rule. It folds three filed findings into the files it cuts: W-6effedda (the `review-probe-catalogue.md` § Seat isolation recipe says a gitignored GENERATED file the code imports is copied into the archive tree), the catalogue half of W-9ad5860f (the seat-isolation test recipe runs Python with `-P` and `env -C`, so the live tree is never imported; the `.claude/workflows/fabrik-review-loop.js` half stays intel's item), and W-f723cb66 (`commands/_agents/fabrik-reviewer.md` forbids a seat executing the surface it reviews). It takes lever T4 to the Opus + Fable panel: briefs carry the question and the pin, and the house rules stay in `fabrik-reviewer.md`, the seat's rule source under `omitClaudeMd: true` (`commands/_agents/fabrik-reviewer.md:6`). `close-feedback.md` is ledgered as it stands at T01a's start commit; L2's `remove:` sentence lands before that or after this unit merges (spine § Global Constraints). DO-NOT: edit any shared fragment or seat definition outside this unit, another command's source, or the tooling files `commands/command_rules.py`, `commands/assemble_commands.py`, `scripts/command_run.py`, `scripts/command_feedback_report.py`, `tests/test_command_rules.py`. Its pins were migrated by the unit's preceding migration ticket(s), so this ticket edits no test. Kept behavioural tests that pin its text (never edited here; each pinned phrase survives verbatim): `tests/test_command_feedback_report.py`, `tests/test_command_run.py`, `tests/test_review_loop_workflow.py`.

Depends: T01c
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_command_rules.py -q -rP — green; its PASSES section shows one LEDGER line per ledger this ticket wrote
Gate: python3 commands/assemble_commands.py --check — exit 0, or exit 1 only when every DRIFT line reads `DIFFERS from what this tree renders` or `MISSING` (the installed corpus stays master's until the coordinator renders at merge); any other DRIFT line (a missing D-191 dispatch step, an ORPHAN), a render `SystemExit` message, or exit 2, 4 (LOSS) or 5 (ceiling) fails
Gate: the reader-test run of spine § Global Constraints over every file this ticket cuts — green; a red test is a Touches miss, never skipped
Docs: none owned (the orchestrator applies `CHANGELOG.md`, the `INDEX.md` rows for new `commands/_rules/` files and every D-row through Deltas)

## Touches
- commands/_fragments/no-workflow-hub.md
- commands/_fragments/run-record.md
- commands/_fragments/orient.md
- commands/_fragments/close-chain.md
- commands/_fragments/close-feedback.md
- commands/_fragments/review-probe-catalogue.md
- commands/_agents/fabrik-reviewer.md
- commands/_agents/fabrik-researcher.md
- commands/_agents/fabrik-gui.md
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
- commands/_size_ceiling.json

## Behavior Contract
- **Given** the ledger for the shared files `no-workflow-hub.md`, `run-record.md`, `orient.md`, `close-chain.md`, `close-feedback.md`, `review-probe-catalogue.md`, `fabrik-reviewer.md`, `fabrik-researcher.md`, `fabrik-gui.md` written from its baseline own text at the unit's start commit, **When** `tests/test_command_rules.py` renders the corpus, **Then** it prints a LEDGER line for it with zero LOSS lines (spec § The rule test)
- **Given** the shared files `no-workflow-hub.md`, `run-record.md`, `orient.md`, `close-chain.md`, `close-feedback.md`, `review-probe-catalogue.md`, `fabrik-reviewer.md`, `fabrik-researcher.md`, `fabrik-gui.md` rewritten, **When** its own text is counted with `command_rules.own_text`, **Then** it is at most 50% of the baseline count or unit 01's merge names it as an open floor that T02 settles (spec § Target)
- **Given** every baseline unit of the shared files `no-workflow-hub.md`, `run-record.md`, `orient.md`, `close-chain.md`, `close-feedback.md`, `review-probe-catalogue.md`, `fabrik-reviewer.md`, `fabrik-researcher.md`, `fabrik-gui.md` with no surviving match, **When** the ledger is loaded, **Then** each has a `vanished:` label adjudicated from a Sonnet and a Haiku seat's union (spec § The rule test)
- **Given** a NEVER or refusal clause, or a phrase a kept behavioural test pins, in the baseline of the shared files `no-workflow-hub.md`, `run-record.md`, `orient.md`, `close-chain.md`, `close-feedback.md`, `review-probe-catalogue.md`, `fabrik-reviewer.md`, `fabrik-researcher.md`, `fabrik-gui.md`, **When** it is rewritten, **Then** the phrase survives verbatim as a `text` carrier (spec § How a command is cut)
- **Given** the corpus after the shared files `no-workflow-hub.md`, `run-record.md`, `orient.md`, `close-chain.md`, `close-feedback.md`, `review-probe-catalogue.md`, `fabrik-reviewer.md`, `fabrik-researcher.md`, `fabrik-gui.md` rewrite, **When** `assemble_commands.py --check` runs, **Then** it exits 0 or 1 and never 4 or 5 (spec § The rule test)
- **Given** the `review-probe-catalogue.md` seat-isolation recipe, **When** the code under test imports a gitignored generated file or runs from a git archive, **Then** the recipe says to copy that file into the archive tree and to run Python with `-P` and `env -C` (W-6effedda, W-9ad5860f)
- **Given** `commands/_agents/fabrik-reviewer.md` rewritten, **When** a seat reads its house rules, **Then** they forbid executing the surface under review, and the T4 panel verdict on brief contents is a D-row (W-f723cb66, spec § Time budget)

## Steps
1. Record the start commit (`git rev-parse HEAD`): the baseline commit, and the frozen copy the after-window sample re-reviews with. The baseline and the pin entries were written by part a; never rewrite the baseline.
2. List the phrases the reader tests outside this ticket's Touches (spine § Global Constraints) pin in each file being cut, passing them as `<the tests>` (read the printed lines, never the whole test):
   `python3 -c "import ast,sys; t=' '.join(open(sys.argv[1]).read().split()); [print(f+': '+v) for f in sys.argv[2:] for n in ast.walk(ast.parse(open(f).read())) if isinstance(n,ast.Constant) and isinstance(n.value,str) for v in [' '.join(n.value.split())] if len(v)>=25 and v in t]" <the file being cut> <the tests>`
   Each printed phrase is a ledger entry with a `text` carrier and must survive verbatim; those tests are never edited here.
3. Build the ledger before cutting: one entry per rule unit (a step, an order, a ban, a threshold, a format, a refusal, a close condition), each with `id`, `file`, `section`, `baseline`, `current` and at least one carrier. `file:` paths are repo-relative (`commands/_fragments/<n>.md`), never a bare `_fragments/…`; a rule in a command source omits `file:`, which defaults to the render. Full form: write every remaining entry by hand, beside the pin entries a migration part already wrote, never a second entry for one rule.
4. Rewrite with levers (a)-(e) of spec § How a command is cut, cutting hardest where the text drives rounds and seat work: the termination contract, the seat briefs and the per-round obligations (spec § Residual unknowns U4).
5. List the vanished units: `c.vanished(c._read_baseline(Path('<baseline.txt>').read_bytes()), <new own text>)`, the new own text being `c.own_text(…)` of the source, or a shared file's whole text. The orchestrator dispatches two author-blind seats in ONE message, one `model: "sonnet"` and one `model: "haiku"`, each briefed with only the vanished lines and the pinned rewrite. Each labels every line `rule: [ids]`, `duplicate-of: id` or `narrative`, and the orchestrator adjudicates their union into the ledger's `vanished:` map.
6. Count own text before and after (`command_rules.own_text` for a source, the word count for a shared file). If a file is still over 50% and no further cut is possible without a LOSS, name it to the orchestrator as an open floor for unit 01's merge; T02 mints its floor D-row (spine § Interfaces).
7. Lower this ticket's ceiling rows in `commands/_size_ceiling.json` only through the text-measure merge's ratchet (`docs/reference/command-corpus-check.md` § Rule ledger; spine § Residual unknowns R2), never by hand.
8. Run the Gate lines. A red test outside Touches is a Touches miss: hand it to the orchestrator (spine § Global Constraints), and never skip or xfail it.

## Context Files
- .windsurf/rules/core/40-documentation.md

> Tooling API (W-a9b5e763 slice A, on master since merge bc2a9c30b, D-1221; cited by symbol because review fixes move its lines): `commands/command_rules.py::own_text(source)` returns a source's own text, no included fragment text in it · `commands/command_rules.py::write_baseline(text, out)` writes the unit keys and returns the sha256 for `baseline_sha256:` · `commands/command_rules.py::vanished(baseline, current_text)` lists the 1-based baseline lines with no exact match · `commands/command_rules.py::losses(render_dir, root, src_dir)` is what `--check` and `tests/test_command_rules.py` assert. infra-2's text-measure merge adds `command_rules.generate_unchanged(baseline_path, new_own_text) -> [entry]`, the measure and `commands/_size_ceiling.json` with `--check` exit 5 (spine § Interfaces).

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
