# Review probe catalogue

The probes earlier review runs found missing, by when they apply. Read the lines that match the change's SHAPE —
never all of them — before the first pin and while writing the brief. Each is a step, not a check box: execute it,
or name in the brief why the shape does not have it.

## Before the first pin (the lead executes)
- Run the changed artifact end to end when it can run (an emitted one-liner run as emitted, under its real shell), and
  check the END STATE a recipe exists to produce, not only each step; run a README snippet, usage text or rewritten
  docstring instruction as a caller would, and probe each exception a rewritten docstring says the function still
  raises.
- Trace the entry path: the first caller that reaches the fixed function; enumerate every call shape through a new
  branch and every input path of a shared reader; trace each rationale sentence's mechanism to the code, and execute
  every "X only when Y" claim the fix adds.
- Enumerate the fix's input class whole (boundary, empty, unset, mandated, non-dict/non-string, every Unicode whitespace
  class, the real committed files' shapes counted by an independent parser) and probe it again before each delta; keep
  an adversarial input list for the fix's own new edges; enumerate each guard's ESCAPE VARIANTS in both directions —
  false green and false red — committing the positive/negative probe list beside it.
- Name the defect's class and grep the whole class (every site, sibling guards, every scaffold type, recursively,
  vendored venvs and `.claude/worktrees` excluded) before patching one instance; diff sibling implementations side by
  side, and before adding a sibling of a pinned or guarded line, read the comment on the line it copies; port vendored
  code, or reimplement another tool's semantics (a YAML merge, a compose override), and prove parity by an executable
  diff against that tool's own output over its edge cases (for a merge: nesting, mixed types, cycles) before the fix
  lands, never a model from memory.
- One mutant per clause the edit states, written as a literal before/after (an ordering claim names its mutant);
  re-run every prior mutant and the reproducing probe after each fix; probe each new grader with its mutant.
- Run the repo's structural source graders, every touched test file whole, every gate the changed sentence will meet
  and the completion gate on the pinned files; feed a sample row through every grader that parses the artifact; a
  synced hook change is checked for its fleet copies' md5.
- Execute: every factual row of a relayed report, every citation in a docs change, every cross-repo claim and every
  count in a decision row (with its command and denominator), every remedy proposed for a security primitive, a
  confirmed candidate's premise before writing its fix, and a report-adopted fix traced into its consumers; paste the
  code path's own enumeration beside a doc sentence that lists it.
- Before widening a matcher or heuristic: its fire rate and added-hit precision on the live population, the
  failure-mode asymmetry, and a written residual (a heuristic finding is fixed by narrowing plus a documented limit);
  new classifier rules run against real dependency outputs; before a parity claim, whether the mirror can be exact
  with the dependencies available; before a counted bar or a spend scale changes, drive it over the real series and
  the unit cost.
- Grep the docs and ledgers for a by-design rule on the subject; resolve an integrity-check exemption against its real
  target; render a fragment edit's consumers to a temp dir and read each.

## The brief's hunt lines (name the ones the shape has)
- Callers and consumers: every caller of a changed exit code, output line or gated script; every consumer of a changed
  prompt output, of import-time side effects, of a flipped Status (generated indexes) or of a renamed name (link fields,
  hand-kept indexes); callers that use a normaliser's return value; a pure helper's own return contract, not only what
  its callers observe; the line that copies a template-emitted claim; every gate grading the old name; every outbound
  sink a production-reaching test can touch; every actor touching an RLS table; placeholder resolution per consumer;
  repo-wide service lists and absence statements.
- Parsers: the producer's real output contract first, then the parsing model before tokens; lossy cases (duplicate
  keys, ordering, whitespace), regex/strip edges (a regex redactor is also timed on a 100k-character input and probed
  at its truncation edges), the request-target grammar for URLs, comment and brace shapes for config, the real
  interpreter (dash) and the parent commit as oracles; a generated file is parsed by its generator's format, and a
  skip check reuses the consumer's own parser.
- Guards and rules: the guard's equivalence class (must fold, must not), what a replaced guard covered that its
  replacement does not, every exception subclass a new catch admits, false negatives classed plausible vs contrived,
  whether each matcher shortcut is covered by the general path, every rule an overriding sentence overrides (and every
  command it prescribes, in its default mode), which value wins when a new knob meets an existing per-row setting, and
  the rule's cost on the previous behaviour; the reader reports each escape shape as executed or read.
- State and concurrency: who waits on a new lock and behind what; new module-level state reset on every return; every
  value a changed predicate sees from each writer (0 vs NULL); whether a filtered counter keeps its own records; which
  fixture scopes run before an autouse pin; an env-leak fix where `delenv` on an absent key records nothing.
- Failure paths: what a fix does when its own fallback fails; the configuration-failure path; a fail-soft mail or
  report path fed malformed stored data; a shell chain whose failing step must fail the chain (a gate line gates the
  commit, never only prints); a dry-run and write path diffed field by field; a validator's direct-call path.
- Surfaces: every connection a guarded module opens; every field a new serializer emits; argparse edges of a new flag;
  machine-parsed section markers; a literal pipe inside a table cell; a moved reference and which sentence branch
  reaches it; each mechanism claim at every lane or version it names; `git check-ignore` on the bare directory;
  defects split between a hook and its generator; a changed compose overlay read through its merged render (`docker
  compose -f <base> -f <overlay> config`), where precedence and port exposure show.
- The premise: the authoritative seat attacks the work item's premise and a ported heuristic's premise, not only the
  implementation; ask whether an existing mechanism or fragment already covers the class, and whether the check fits a
  boundary the data already has; edited prose is checked against its rule pack's SCOPE line; an external quote goes to a
  `fabrik-researcher` seat whose brief names the version the repo pins or deploys (its lockfile or spec line) and asks
  for the claim at that version; a seat names the whole input class of a finding it raises; a re-vendor brief hands the
  seats the lead's executed byte-identity result (the diff command and its output) as a claim to attack — they re-run
  that command first, then spend on what byte identity cannot show: the vendored copy's own header and every importer of
  it.

## Graders
- Grade the PROPERTY across every example, never one spelling; a new assertion must fail when its subject is absent
  (an absence assertion over never-written state is vacuous); a grader EXECUTES an executable subject, through the
  real production adapter and the consumer's entry point (the command's output, as the gate passes files by name),
  never reads it; a premise guard asserts at the call site, not on constants; a prose grader asserts the whole
  generated sentence, not a substring; a test-quality seat checks docstring claims against the scan; a fix recipe
  handed to a coder names one input it must leave unchanged and the test that holds it.
- Each parser-output shape owes its own red; a config or regex grader is graded by running the tool on mutated inputs;
  a red branch of a new procedure step is executed as well as the green; a boundary fix tests both sides with the
  exact message; a numeric bound is derived in its comment and graded at both edges, with the determining input varied
  first; pin the exact stdout line a count reads; a lock-order fix ships an executed concurrency probe.
- Mutants: one per new comparison or constant AND one against every existing assertion whose input changed, each
  anchored on a token the formatter cannot rewrap, the mutated line shown changed before a green is trusted, survivors
  reported; a counter or guard is gutted in the same round to show it can fail; a regression test fails when the
  caller is reverted; one reader mutates the guarded behaviour; graders are written, and named, before the next round
  goes out.
- Test hygiene: a test stub records what it RECEIVED; a timing test is repeated 10× under its mutation; isolation is
  proven by a reversed-order run and by removing the fixture; a state-mutating grader leaves nothing on teardown;
  non-ASCII literals are checked by bytes; the whole suite directory of a changed test runs; a golden value is pinned
  after printing its matched span; a byte-identical refactor gets a HEAD-vs-new differential harness; two emitted
  artifacts are diffed whole for an alias change; a red's failure message is diffed against the baseline and printed
  beside its FAILED line; an import-path fix is graded from the root conftest and a child process; a grader exclusion
  says whether it matches an exact name or a pattern.

## Prose and docs fixes
- Read a fragment's scope sentences, and a rule already in a fragment is quoted in its own words and pointed at; a
  ported rule is re-derived against this command's machinery; a parser rule is stated positively, not as a terminator
  list; a scoped exception beats a new section note; tool claims are written from the source (a sentence describing a
  record format or a code string quotes the emit site's keys or the string verbatim), then checked against the live
  corpus and the tool's real output variants.
- After the edit: rewrap the whole paragraph by tool; re-read an inserted sentence with the one after it; a long-line
  replacement keeps its neighbours' opening clauses; re-read a cited range after rewording its citation; moved table
  rows are placed by computed position and checked by an inversion diff against base; sentences a test pins verbatim
  are marked before they are rewritten.
- Sweep: a corrected claim or quote across every file the change touched (test docstrings included), whitespace- and
  wrap-normalised; every statement of a changed number or count in the whole file; same-subject lines in the pack, doc
  summary rows and artifact generators that restate it; residue words of a flipped decision; a cross-pack citation's
  terms against the section it cites.
- Claims: every factual sentence of an edited paragraph re-derived, every newly rendered table cell included, and a
  corrected fact stated at the original claim's scope; every clause on a count-fixed line, and every reworded README
  claim, checked against the code lines it names, and a sentence describing a matcher or regex executed over its input
  space (punctuation, underscore, empty) before the pin; a count cites the command (with its range — the brief hands
  the seat that exact command) and the line that holds it, a measured count names its population, a closing brief
  names each figure's source and the record's own round trend, a live value is a timestamped snapshot; a code snippet
  in prose is a checkable claim; an evidence block in a report or receipt pastes the artifact's section whole and
  names the file it was copied from, by path and md5 (one that elides is a claim, not evidence); an unverified
  hand-derived enumeration is deleted.
- A site a round re-opened, a bullet wrong two rounds running, or a mechanism the fix added and a round broke, is
  rewritten or deleted whole, never patched again.

## Seat isolation
- The brief names the fix as `git show <sha>` — each sha when the fix spans several commits — or a pathspec-scoped
  diff, never a bare range on a branch others commit to (a range carries every sibling commit landed in it). Seats
  copy the pin to scratch and assert its md5s first; tests run against an archive of the pinned SHA by the seat
  prompt's `PIN_IMPORT`/`PYTEST_PINS` recipe — the whole test tree archived so collection succeeds, the live repo's
  `.venv` python (never `uv run`), no `.env` copied (a dummy on `.invalid` only for an import-failing variable). The
  recipe names its roots by what the tests import, so the brief extends it to every top-level path the tests import,
  read or run (a test that renders `templates/`, reads `.windsurf/` or runs `scripts/` by subprocess is a false red
  without it) and names the live repo as the checkout `git rev-parse --show-toplevel` prints, never `/opt/fabrik` from
  a worktree. The pins line follows the real layout and the digest is the pin authority. A SEAT never runs `git
  worktree add` (its metadata lands in the shared `.git`): a seat's red-on-revert overlays the revert on its archive
  copy by `PYTEST_PINS`, and the lead's red-on-revert and mutate-restore cycle run in CLAUDE.md's throwaway worktree,
  never a `PYTHONPATH` copy — set its upstream and link `.env` before its first gate. Ruff and mypy run from the repo
  root with the repo's own config (on a copy: ruff `--config <repo>/pyproject.toml`, mypy `--config-file` with the
  same path); tests run by exact node id. A script a seat runs is run from its archive copy with every path argument
  under scratch (a script may treat any argument as a write path), and the pin carries the changed files' one-hop
  callees that are repo files (`review_loop_ledger.py pin` refuses the whole list when one path is missing, a symlink
  or outside the repo root).
- No `uv`/`pip`, no live API key outside the suite's fixtures, and every writing verb outside scratch named and
  forbidden; one grep form; large output goes to the seat's scratch first; the adjudication authority (CLAUDE.md, the
  packs) is read at the pin; the brief names which shell guard a seat is under (the worktree guard reads the word
  `git` inside a `-c` program or heredoc as a git call, so the seat writes such a probe to a file) and hands readers a
  ready probe harness file, never promising a tool the seat does not have (the Write tool); a claim only the home
  directory can settle is recorded up front for the lead.
- Every file a grader reads is pinned, the uncommitted module under test included; a "nothing changed for readers"
  claim is proven on a pinned input; a concurrent sibling run on a shared DB is a known false red; a seen-red on a
  DB-writing script names its sandbox; a ledger row whose fix landed in a file outside the pin (a CHANGELOG or ledger
  hunk) has that file pinned next pass, or the brief names it, so the seat never reads the base copy.

## Loop bookkeeping
- Run `dispatch_headroom.py` before the pin, then stamp `command_run.py dispatch --seats <SEATS + one refuter per
  unit>` before the dispatching message — the stamp is an upper bound, closed by the round's `--seats`; a SEATS 0 on a
  box cap is an in-turn wait (re-run once a minute), and when the `Workflow` tool is absent or cannot load the script,
  or the operator did not invoke this run (the tool runs only on their explicit opt-in), seats go out through the
  `Agent` tool and the close's `--evidence` names `shape: agent-tool`; while seats are out, build the next fixes in a
  scratch copy, never the pinned files, and keep a timer running; write the Workflow args JSON to scratch, and
  relaunch an interrupted pass as a NEW `Workflow` invocation carrying the ledger in `args` — never `resumeFromRunId`.
- A round is recorded only after every candidate is read, each classed as a defect of THIS change, pre-existing or
  planned before it counts; `confirmed` counts DEFECTS, never checks passed, and a gate-caught defect counts; each brief
  embeds its ledger text; the closing-pass brief has every seat list each slice file it read, by path; a delta brief
  lists the exact mutant ids executed, reads a unified diff, and checks ROUTED claims for routing only; a one-hop edit
  found mid-fix is named in the next brief, and a guard a fix adds goes into every brief from that next one on, by name,
  with its escape variants (quote styles, unreadable values, globbed paths) and its model boundary; stale pre-existing
  text in an edited file is RECORDED with a destination (term-coverage D4), or fixed in the same hunk and named — never
  counted; the slice ledger is round 1's claim count even at zero confirmed.
- Lint or format findings are compared against HEAD — and against the committed diff, under every claimed toolchain
  version — before they are reported or refuted; tests re-run after the last lint fix; a refutation that a later
  commit lands is checked against the completion gate; read the callee before confirming a wrong-method finding; a
  refuter that needs a forbidden surface marks it `unverified` naming the surface, and the lead executes it; run the
  files a reader names, not every grep hit.
- Remainder rounds: a remainder round names the classes its fixed set re-sweeps; it never fixes a RECORDED candidate;
  a finding it raises is fixed when it is a defect of the fixed set and routed when it is not; a premise-refuted
  verdict is re-probed under the later reader's rule; a slice a trim left with one finder gets its second in the next
  wave — or, when the cap is known before round 1, merge two low-risk slices so the riskiest keeps both finders.
- Route-up and close: a fix that adds a file re-applies step 1's count; a critical finding on a published contract
  routes up at once; artifacts the review itself created go to a follow-up loop; a RECORDED residue whose surface is
  another beat's is mailed at the close; shared-ledger hunks land before the closing pass; the completion gate runs
  before the terminal round is recorded, remembering that its unpushed scope includes base commits a fast-forward
  brought in and that staged-diff checks do not see intent-to-add files; under an operator directive forbidding
  subagents, the close's `--evidence` declares the waiver.
