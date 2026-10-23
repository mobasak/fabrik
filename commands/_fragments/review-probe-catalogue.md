# Review probe catalogue

The probes earlier review runs found missing, by when they apply. Read the lines that match the change's SHAPE — never
all of them, § Seat isolation excepted: it applies whole in every brief that runs tests or imports pinned code —
before every pin, the first and each delta, and while writing every brief. Each is a step, not a check box: execute
it, or name in the brief why the shape does not have it.

## Before the first pin, and again before each delta pin (the lead executes)
- Run the changed artifact end to end when it can run (an emitted one-liner run as emitted, under its real shell), and
  check the END STATE a recipe exists to produce, not only each step, against the artifact the next step compares it
  with (a lock file, a manifest), not only the source it reads; run a README snippet, usage text or rewritten docstring
  instruction as a caller would, and hand each seat of the brief that same command to run under § Seat isolation — one
  that writes a live store, sends, commits, deploys or reaches a host stays the lead's — and probe each exception a
  rewritten docstring says the function still raises.
- A line another tool injects or renders, changed or with a rendering the change alters, is read back whole through
  that tool's output after the edit and before each delta pin, under an invocation that emits it — a pack line in
  `review_rubric.py --changed <a path its globs hit>`, a fragment edit's consumers rendered to a temp dir, a
  template's emitted file — never in its source alone; a line the change leaves emitted by no invocation (a pack
  line with no mandate keyword, a section under a conditional heading) is named in the brief as dropped.
- Trace the entry path: the first caller that reaches the fixed function; enumerate every call shape through a new
  branch and every input path of a shared reader; trace each rationale sentence's mechanism to the code through
  every branch it summarises (refusals and fallbacks, not only the happy path), and execute
  every "X only when Y" claim the fix adds.
- Enumerate the fix's input class whole (boundary, empty, unset, mandated, non-dict/non-string, a fix's identity or
  dedup key (byte vs text read, line endings, recycled ids such as inode reuse), every Unicode whitespace class, every
  reader of a shell recipe or printed command (its own shell, a paste, another shell or locale; IFS, noglob, PATH), the
  real committed files' shapes counted by an independent parser, and every order its duplicate records can arrive in
  when the fix keeps one of them) and probe it again before each delta; keep an
  adversarial input list for the fix's own new edges; enumerate each guard's ESCAPE VARIANTS in both directions — false
  green and false red — committing the positive/negative probe list beside it.
- Name the defect's class and grep the whole class (every site, sibling guards, every scaffold type, recursively,
  vendored venvs and `.claude/worktrees` excluded) before patching one instance; diff sibling implementations side by
  side, and before adding a sibling of a pinned or guarded line, read the comment on the line it copies; port vendored
  code, or reimplement another tool's semantics (a YAML merge, a compose override), and prove parity by an executable
  diff against that tool's own output over its edge cases (for a merge: nesting, mixed types, cycles) before the fix
  lands, never a model from memory.
- One mutant per clause the edit states and one per guard it adds or alters (that guard removed — term-coverage rule
  (4): "each grader is proven it CAN fail by REMOVING THE GUARD, never by breaking an expression inside it"), written
  as a literal before/after (an ordering claim names its mutant); re-run every prior mutant and the reproducing probe
  after each fix (a seat re-running a delta brief's mutant ids too) against every test file the change touched or
  added, collected again after the fix with no selection that leaves a test out (`-k`, node ids, `--lf`, `--deselect`,
  `-m`, `--ignore`) beyond term-coverage rule (4)'s environment-bound deselection (§ Seat isolation's exact node ids
  are for a seat's other test runs); probe each new grader with its mutant.
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
  target.

## The brief's hunt lines (name the ones the shape has)
- Callers and consumers: every caller of a changed exit code, output line or gated script; every consumer of a changed
  prompt output, of import-time side effects, of a flipped Status (generated indexes) or of a renamed name (link
  fields, hand-kept indexes); callers that use a normaliser's return value; every line that joins, compares or keys a
  changed output against another producer's, named with the form each side's values take (a path relative to a
  subdirectory or to the top level, say); a pure helper's own return contract, not only what its callers observe; the
  line that copies a template-emitted claim; every gate grading the old name; every reader of a changed or vendored
  file's text that never imports it (a scaffold fold such as `src/fabrik/scaffold.py::_audit_log_schema_block`, a
  drift or sync checker), found by the lead grepping the hub and the fleet repos for the file's path, basename and
  directory and reading `scripts/fabrik_synced_manifest.py` for a glob that covers it (a covered file is also read
  through each project's `.fabrik/synced.lock` by `scripts/enforcement/check_synced_unmodified.py`), each hit that
  reads the file named in the brief; every outbound sink a production-reaching test can touch; every actor touching an
  RLS table; placeholder resolution per consumer; repo-wide service lists and absence statements; every reader of a
  changed predicate's verdict (a notice, message or wall line that reads the same hold), and of each field a fix
  writes, named before the closing round.
- Parsers: the producer's real output contract first, then the parsing model before tokens; lossy cases (duplicate keys,
  ordering, whitespace), regex/strip edges (a regex redactor is also timed on a 100k-character input and probed at its
  truncation edges, and run beside the parent commit's redactor over one generated input corpus, its generator and size
  named in the brief, each output that differs classed intended or a defect in the seat's report), the request-target
  grammar for URLs with its parser-differential classes named in the round-1 brief (a backslash, a percent-encoded host,
  an IDNA host under its UTS-46 mapping, a numeric or shortened IPv4 host, whitespace and control characters, `@` in
  userinfo, a `#` or `?` before the `@`, a malformed port, an unclosed `[`, no scheme), comment and brace shapes for
  config, the real interpreter (dash) and the parent commit as oracles; a generated file is parsed by its generator's
  format, and a skip check reuses the consumer's own parser; a hand-written reader whose input is source in a language
  other than its own (TypeScript read by Python, SQL, a Dockerfile), with no real parser of that language at hand,
  starts from a strict grammar that REFUSES any line matching none of its named forms, none a catch-all, its refusal
  executed before every pin on a line of that language's own syntax that no named form admits, and run by the lead over
  the live files the reader will read, each refusal there classed a grammar gap or a true out-of-grammar line; the seats
  attack what the grammar wrongly accepts — a tokenizer is built only where the brief names the construct no line form
  can hold.
- Guards and rules: the guard's equivalence class (must fold, must not), what a replaced guard covered that its
  replacement does not, every exception subclass a new catch admits, false negatives classed plausible vs contrived,
  whether each matcher shortcut is covered by the general path, every rule an overriding sentence overrides (and every
  command it prescribes, in its default mode), which value wins when a new knob meets an existing per-row setting, and
  the rule's cost on the previous behaviour; the reader reports each escape shape as executed or read.
- State and concurrency: who waits on a new lock and behind what; new module-level state reset on every return; every
  value a changed predicate sees from each writer (0 vs NULL); whether a filtered counter keeps its own records; which
  fixture scopes run before an autouse pin; an env-leak fix where `delenv` on an absent key records nothing; a change
  that writes outside its state dir: every isolation seam its callers' tests use (`COMMAND_RUN_DIR`, a `HOME` or
  `TMPDIR` override), each shown to land under its own root by listing the live checkout after the suite.
- Failure paths: what a fix does when its own fallback fails; the configuration-failure path; a fail-soft mail or
  report path fed malformed stored data; a shell chain whose failing step must fail the chain (a gate line gates the
  commit, never only prints); a dry-run and write path diffed field by field; a validator's direct-call path.
- Surfaces: every connection a guarded module opens; every field a new serializer emits; argparse edges of a new flag;
  machine-parsed section markers; a literal pipe inside a table cell; a moved reference and which sentence branch
  reaches it; each mechanism claim at every lane or version it names; `git check-ignore` on the bare directory;
  defects split between a hook and its generator; a changed compose overlay read through its merged render (`docker
  compose -f <base> -f <overlay> config`), where precedence and port exposure show; a page-type or reader move: base
  and head are built and each page's visible text and heading outline (h1-h3 counts) are diffed independently of any
  identity diff the change ships, and the preview server runs on each language root, since a dist diff cannot see dev-
  or preview-only settings.
- Deletions (a change that deletes a file, directory or input): a deleting probe also removes every directory it
  empties, up to the root, as `git rm` does (`find <root> -name .git -prune -o -type d -empty -print`, run before
  and after the deletion, prints no new line; a leftover hides a `readdirSync`); a seed restoring deleted inputs
  first lists, by grepping the code under test, each input it reads by name or by listing a directory, and restores
  no other; the Callers grep above runs for each deleted path, basename and directory from the hub and the fleet
  repos, never the package; seats name, for each guard on a deleted input, whether it re-runs at removal or only at
  classification.
- The premise: the authoritative seat attacks the work item's premise and a ported heuristic's premise, not only the
  implementation; ask whether an existing mechanism or fragment already covers the class, and whether the check fits a
  boundary the data already has; edited prose is checked against its rule pack's SCOPE line; an external quote goes to
  a `fabrik-researcher` seat whose brief names the version the repo pins or deploys (its lockfile or spec line) and
  asks for the claim at that version; a claim about what a dependency accepts or does (a guard over its keys, a docs
  sentence about its behaviour) is checked against every case the dependency defines for the keys or behaviour the
  claim covers — each branch and alias in its source at that version, else its versioned reference docs plus an
  executed probe — never only the cases the author listed; a seat names the whole input class of a finding it raises;
  a re-vendor brief hands the seats the lead's executed byte-identity result (the diff command and its output) as a
  claim to attack — the diff reads the source's COMMITTED blob at the SHA the copy records (a `VENDORED-FROM` header,
  else the `Vendored-From:` trailer of the commit that vendored it; HEAD when neither does: `git -C <source> show
  <sha>:<source path>`) against the copy minus that header, never the source's working file, where a sibling's
  uncommitted edit reads as drift — and the brief names the source's own regression test for the file at that SHA, run
  with its import path pointed at the copy (or says the source has none) and whether that test assumes a co-located
  hub tree, so a standalone run of it is a known false red; they re-run that command and that test first, then spend
  on what byte identity cannot show: the vendored copy's own header, every importer of it, and every name it reads
  from each module vendored beside it (its `from … import` names and each `module.attr` use), each shown present in
  that module's copy.

## Graders
- Grade the PROPERTY across every example, never one spelling; a new assertion must fail when its subject is absent
  (an absence assertion over never-written state is vacuous); a grader EXECUTES an executable subject, through the
  real production adapter and the consumer's entry point (the command's output, as the gate passes files by name),
  never reads it; a premise guard asserts at the call site, not on constants; a grader of fixed prose or of a
  deterministic message asserts the whole sentence, bullet or message it pins by equality (`==` against all of it,
  every line of a message, never `in`, a prefix, a suffix or a regex over part of it), so an added clause or a leaked
  value fails it, and a grader of that text's position, of its absence or of a property across its examples sits
  beside that equality grader, never in place of it; a grader of MOVED text (a sentence, clause, bullet or row), added
  in the edit that moves it, also fails when the text sits at its old position; a test-quality seat checks docstring
  claims against the scan; a fix recipe handed to a coder names one input it must leave unchanged and the test that
  holds it; a grader of a `path:N-M` cite asserts its first line AND its last line still hold the text the cite backs.
- Each parser-output shape owes its own red; a config or regex grader is graded by running the tool on mutated inputs;
  a red branch of a new procedure step is executed as well as the green; a boundary fix tests both sides with the
  exact message; a numeric bound is derived in its comment and graded at both edges, with the determining input varied
  first; pin the exact stdout line a count reads; a lock-order fix ships an executed concurrency probe.
- Mutants: one per new comparison or constant AND one against every existing assertion whose input changed, each
  anchored on a token the formatter cannot rewrap, the mutated line shown changed before a green is trusted, survivors
  reported only once shown to change observable behaviour (an output, return value, exit code, raised exception or
  written state diffed against the unmutated copy), and an equivalent mutant is struck with that diff quoted, never
  a test gap; a counter or guard is gutted in the same round
  to show it can fail; a regression test fails when the caller is reverted; each slice's seats write and run one mutant
  of their own per guard the change adds in their slice, written
  afresh rather than re-run from the lead's pre-pin list, on a copy made from the pin, under the explicit `timeout` its
  brief names (`/fabrik-review`'s D8 mutation-seat lesson); one reader
  mutates the guarded
  behaviour; a tests slice's seats also write and run mutants of their own against each behaviour its tests
  claim, beside the lead's, and report each survivor that changes observable behaviour, as above; graders
  are written, and named, before the next round goes out.
- Test hygiene: a test stub records what it RECEIVED; a timing test is repeated 10× under its mutation; isolation is
  proven by a reversed-order run and by removing the fixture; a state-mutating grader leaves nothing on teardown;
  non-ASCII literals are checked by bytes; the whole suite directory of a changed test runs; a golden value is pinned
  after printing its matched span; a byte-identical refactor gets a HEAD-vs-new differential harness, and a fix that
  swaps one call, guard or protocol for another (`in` plus `[]` for `.get`) gets one over the input types its callers
  pass, subclasses and registered virtual types included, before each pin; two emitted artifacts are diffed whole for an
  alias change; a red's failure message is diffed against the baseline and printed beside its FAILED line; an
  import-path fix is graded from the root conftest and a child process; a grader exclusion says whether it matches an
  exact name or a pattern.

## Prose and docs fixes
- Read a fragment's scope sentences, and a rule already in a fragment is quoted in its own words and pointed at; a
  ported rule is re-derived against this command's machinery; a parser rule is stated positively, not as a terminator
  list; a scoped exception beats a new section note; tool claims are written from the source (a sentence describing a
  record format or a code string quotes the emit site's keys or the string verbatim), then checked against the live
  corpus and the tool's real output variants, and each stream and input channel the sentence names (stdout or stderr;
  argv, stdin or a flag) is executed before the pin.
- After the edit: rewrap the whole paragraph by tool once each test that caps the file's line length or pins its raw
  lines is found (grep `tests/` for the file's basename, since a test may build the path in parts) and run, a raw-line
  pin bounding the rewrap to the lines the edit lengthened, and run those tests again after it; re-read an inserted
  sentence with the one after it; a long-line replacement keeps its neighbours' opening clauses; re-read a cited range
  after rewording its citation; moved table rows are placed by computed position and checked by an inversion diff
  against base; sentences a test pins verbatim are marked before they are rewritten.
- Sweep: a corrected claim or quote across every file the change touched (test docstrings included), whitespace- and
  wrap-normalised, each quote a fix writes re-read against its source verbatim before the pin; each sentence a fix
  writes that restates a rule already stated elsewhere, found at its source by that restated rule's terms and two
  rewordings of them and then held to `/fabrik-review-scoped` step 3's rule for what is already stated; every doc line,
  docstring, comment and `Raises` section stating an outcome a fix changes (when a function raises or deletes, a module
  that no longer exists), found by grepping its verb and each removed name across the WHOLE file, not only its hunks, in
  the round the fix lands (a `Raises` section phrased by its rule, never an enumeration that the next fix outdates), and
  every comment and docstring of a function whose behaviour a fix changes re-read whole, since a paraphrase names
  neither the verb nor a removed name; every statement of a changed number or count in the whole file; same-subject
  lines in the pack, doc summary rows and artifact generators that restate it; residue words of a flipped decision; a
  cross-pack citation's terms against the section it cites; a `path:line` cite a merge or an edit shifted, remapped by
  CONTENT in one script over every doc that cites the file (find the symbol the prose names, compare it with the target
  line), never renumbered by hand, and the remap runs after each round's fix, before the next pin, over every anchor a
  brief or mutant list carries.
- Claims: every factual sentence of an edited paragraph re-derived, every newly rendered table cell included, and a
  corrected fact stated at the original claim's scope; every clause on a count-fixed line, and every reworded README
  claim, checked against the code lines it names, and a sentence (a comment, a docstring, a doc line) describing a
  matcher, regex or guard written from its input space executed on both sides (punctuation, underscore, empty, the
  lead's escape variants and every one the seats returned) before the pin, never from its subject's own docstring; a
  count cites the command (with its range — the brief hands the seat that exact command) and the line that holds it, a
  measured count names its population and each file or site it leaves out (a guard file, a file holding several sites),
  a closing brief names each figure's source and the record's own round trend, a
  live value is a timestamped snapshot; a code snippet in prose is a checkable claim; an evidence block in a report or
  receipt pastes the artifact's section whole and names the file it was copied from, by path and md5 (one that elides is
  a claim, not evidence); an unverified hand-derived enumeration is deleted.
- A site a round re-opened, a bullet wrong two rounds running, or a mechanism the fix added and a round broke, is
  rewritten or deleted whole, never patched again.

## Seat isolation
- The brief names the fix as `git show <sha>` — each sha when the fix spans several commits — or a pathspec-scoped diff,
  never a bare range on a branch others commit to (a range carries every sibling commit landed in it). The brief names
  the fix that way, and the diff a seat reads is still the pin's own `change.diff`, never one the lead pastes in its
  place; a fix already committed is pinned with `--from <its last commit>`, plus `--base <the commit before the fix>`
  when it spans several, since a working-tree pin of a committed surface prints each file `UNCHANGED` with only a header
  line in its `change.diff`, and `--base` without `--from` pins the working tree, a sibling's later commit or
  uncommitted edit included. Seats copy the pin to their seat folder — `<run scratch>/seat-<n>/` under the run's
  `RUN-SCRATCH:` path (`/opt/fabrik/commands/_fragments/subagents-core.md`, the D8 paragraph; `<scratch>` below is that
  folder) — and assert its md5s first; a tree is staged there only by the archive or the clone this section gives, never
  by copying the live checkout; tests run against an archive of the pinned SHA by the seat prompt's
  `PIN_IMPORT`/`PYTEST_PINS` recipe — the whole test tree archived so collection succeeds, the live repo's `.venv`
  python (never `uv run`), no `.env` copied (a dummy on `.invalid` only for an import-failing variable). A brief the
  lead writes itself tells each seat to read and follow `PIN_IMPORT` — and `PYTEST_PINS` when it runs pytest — in
  `.claude/workflows/fabrik-review-loop.js`, and gives the values that recipe's `${args.base_sha}` and
  `${args.pins_dir}` stand for (and `${args.base_pin_dir}` when the lead wrote a base copy) and the seat's own folder as
  `SCRATCH`; the seat derives `ROOTS` as the recipe says, plus the roots this section's next sentence has the brief add,
  and the brief carries no import or pytest recipe of the lead's own (a pins dir on `sys.path` alone, or pytest's
  `--rootdir` at a copy, imports the live checkout's installed package). The recipe names its roots by what the tests
  import, so the brief extends it to every top-level path the tests import, read or run (a test that renders
  `templates/`, reads `.windsurf/` or runs `scripts/` by subprocess is a false red without it) and names the live repo
  as the checkout `git rev-parse --show-toplevel` prints, never `/opt/fabrik` from a worktree. An editable install's
  `.pth` entry never outranks a copy placed as `PIN_IMPORT` says; live code still runs instead of the pin through a
  `PYTHONPATH` entry (`PIN_IMPORT`), a pytest run from the live repo (`PYTEST_PINS`) and a child process started with
  its own `env=`, which resolves the `.pth` again. The pins line follows the real layout and the digest is the pin
  authority. A SEAT never runs `git worktree add` on the live repo (its metadata lands in the shared `.git`): a seat's
  red-on-revert overlays the revert on its archive copy by `PYTEST_PINS`, and the lead's red-on-revert and
  mutate-restore cycle run in CLAUDE.md's throwaway worktree, never a `PYTHONPATH` copy — set its upstream and link
  `.env` before its first gate. A seat test that reads git history or the tracked set (`git ls-files`: neither the
  archive nor a pin copy has a `.git`) runs in a clone the seat makes with `git -C <scratch> clone --shared
  --no-checkout <live checkout> clone`, checks out at `git -C <scratch>/clone checkout -q <the pass's base SHA>` (until
  then its status reads every file deleted), with its push to `origin` disabled at once (`git -C <scratch>/clone config
  remote.origin.pushurl /nonexistent.invalid`: `origin` is the live repo, so a push writes its `.git`; no other remote
  is ever pushed to) and the pins laid over it, committed in the clone when the test reads HEAD, a diff, the status or
  the tracked set; that test's red-on-revert overlays the revert on the clone. Branch, worktree and stash state the test
  creates lands in the clone's own `.git`; only a test that reads the live checkout's own branches, worktrees or stash
  runs in the lead's throwaway worktree. Ruff and mypy run from the repo root with the repo's own config (on a copy:
  ruff `--no-cache --config <repo>/pyproject.toml`, mypy `--config-file` with the same path; ruff writes `.ruff_cache`
  in its working directory and fails inside a read-only pin without `--no-cache`); tests run by exact node id, except
  a mutant or a re-run of one, which runs every test file the change touched or added whole (the `One mutant per
  clause` bullet above), never a node id or `-k` carried from an earlier brief, and a
  brief over changed code names the tests that load each changed module (by import, or by path through a loader or a
  stub — found by grepping `tests/` for each changed file's stem, its name without `.py`, or an `__init__.py`'s package
  dotted name, and keeping the hits that import or load it) for every seat to run by the `PIN_IMPORT`/`PYTEST_PINS`
  recipe (a test it leaves unrun stays unverified), so a new import that breaks a stubbed loader reds in the pass. A
  script a seat runs is run from its archive copy with every path argument under scratch (a script may treat any
  argument as a write path), and the pin carries the changed files' one-hop callees that are repo files
  (`review_loop_ledger.py pin` refuses the whole list when one path is missing, a symlink or outside the repo root). The
  pin also carries each file a fix's text points at by path, and the brief says the pin holds only the files it lists,
  so a seat reads any other file, the rest of a changed module's directory included, from the base tree with the pins
  laid over it (`<pins_dir>.base` when the pin was taken `--base`, else the archive of its `base_sha`), never from the
  live tree beyond what the seat prompt's recipes (`PIN_IMPORT`, `PYTEST_PINS`, `GATE_PINS`) take from the live disk and
  name UNPINNED.
- A delta brief also names the previous pass's `base_sha` (for the working-tree pin `/fabrik-review-scoped` step 5
  takes, the HEAD its `MANIFEST.json` records as `base_sha`, read back, never verified, since no md5 manifest covers it,
  and null in a repo with no commit; for any other pin the brief names the commit itself, since one taken `--base`
  records that commit (else its `--from` ref) and one written before `base_sha` was recorded has none) and pins_dir, for
  the bounded hop's reader run (a reader passing on the previous round's pin and failing on it with only the fix hunks
  applied). The lead first diffs the two pins' files (`diff -r -x change.diff -x 'MANIFEST*' <previous pins_dir> <this
  pins_dir>`) and the two `base_sha`s (`git diff --name-only <previous base_sha> <this base_sha>`), and states in the
  brief that the difference is the round's fix alone, committed or not, naming any other hunk or path, which leaves
  every reader it touches `unverified` (each `Only in` line, a path one pin holds and the other does not, is named too,
  and classed from `git diff --name-status <previous base_sha> <this base_sha>` for what the fix committed and `git
  status --short --untracked-files=all --ignored -- <path>` for what it did not (a fix can be both), since a removed
  path cannot be pinned and `change.diff` carries no entry for it: a path the fix added, modified, removed or renamed is
  the fix's own, and its readers run on both pins, a removal or rename whose old path this pass's `base_sha` still holds
  leaving those readers `unverified`; any other path pinned in only one pass is another path; a directory line covers
  every listed path under it; a fix's own path's readers are the tests the `tests/` grep above finds and, for a
  document, the citers the heading-or-term grep below finds, and an importer outside `tests/` is named and left
  `unverified`); the seat then runs each reader once on each pin by the `PIN_IMPORT`/`PYTEST_PINS` recipe with that
  pin's own `base_sha`, and greps a heading or term another section cites over each pin's tree, where its citers live; a
  reader the pre-pin section keeps the lead's ("one that writes a live store, sends, commits, deploys or reaches a
  host") takes § Loop bookkeeping's `unverified` route; and a reader that fails on the previous pin is no evidence of a
  break, and is `RECORDED` with its destination.
- No `uv`/`pip`, no live API key outside the suite's fixtures, and every writing verb outside scratch named and
  forbidden; one grep form; large output goes to the seat's scratch first; the adjudication authority (CLAUDE.md, the
  packs) is read at the pin; the brief names which shell guard a seat is under (the worktree guard reads the word
  `git` inside a `-c` program or heredoc as a git call, so the seat writes such a probe to a file) and hands readers a
  ready probe harness file, never promising a tool the seat does not have (the Write tool); a claim only the home
  directory can settle is recorded up front for the lead. A scratch repo a seat makes (the `git init` in a pin, the
  clone above) is checked before its first git write: `git -C <it> rev-parse --show-toplevel` prints its own path, since
  an init that failed under the hub's `.tmp/` leaves every later git call on the live repo. A test or probe that runs
  git runs with `GIT_CONFIG_GLOBAL` at an empty file, `GIT_CONFIG_NOSYSTEM=1`, and `HOME` and `XDG_CONFIG_HOME` at empty
  folders under its scratch, with `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`,
  `GIT_COMMITTER_NAME` and `GIT_COMMITTER_EMAIL` set when it commits, since the empty config holds no identity (an older
  git ignores `GIT_CONFIG_GLOBAL` and reads `$HOME/.gitconfig`), and a test that a
  hook stays silent first shows that hook fire on a positive control.
- Every file a grader reads is pinned, the uncommitted module under test included; a "nothing changed for readers" claim
  is proven on a pinned input; a test that needs a database (the suite skips or fails it without a database variable: no
  `.env` is copied, and the `.invalid` dummy serves imports only) runs with the variable the suite reads
  (`TEST_DATABASE_URL`, an isolated `DATABASE_URL`) in place of that dummy, and a seat probe that must connect uses the
  same variable; both connect over the form the lead proved by one connect before the pin (a unix-socket DSN where TCP
  `localhost` fails password auth), the variable and the form named in the brief, and where only a password form
  connects the lead runs that test or probe itself and quotes its result, never writing the password into a brief, so no
  seat skips the test, re-implements it or probes auth; a concurrent sibling run on a shared DB is a known false red; a
  seen-red on a DB-writing script names its sandbox; a ledger row whose fix landed in a file outside the pin (a
  CHANGELOG or ledger hunk) has that file pinned next pass, so the seat never reads the base copy.
- Overlay and pin currency: the brief lists every pinned path, dot-dirs (`.fabrik/`) included; a seat copies each file
  to its own path or runs `cp -r <pin>/. <dest>/` then `chmod -R u+w <dest>`, never `cp -r <pin> <dest>` onto a
  directory that exists; `pin` writes the pin and its `<pins_dir>.base` tree read-only, files and directories, so a
  seat that copies the base tree runs `chmod -R u+w <dest>` right after that copy and before laying the pins over
  it, and again after it, since a pin file the base lacks lands read-only; and it checks each overlaid file's md5
  against the manifest before its first run. `git archive`
  omits untracked files, so the pin also carries the gitignored inputs the tests read (the repo's `.worktreeinclude`
  list, `.env` excepted) and any sibling-repo symlink they follow. Each later pass's brief names its own pin dir and
  digest, cut after the last fix, never the round-1 pin, and seat scratch dirs from earlier rounds are kept until the
  close, so a seat re-runs its saved probes.

## Loop bookkeeping
- Run `dispatch_headroom.py` before the pin, then stamp `command_run.py dispatch --seats <SEATS + one refuter per
  unit>` before the dispatching message — the stamp is an upper bound, closed by the round's `--seats`; a SEATS 0 on a
  box cap is an in-turn wait (re-run once a minute), and when the `Workflow` tool is absent or cannot load the script,
  or the session is in the hub (D-961: the hub never calls the `Workflow` tool), or the operator did not invoke this
  run (the tool runs only on their explicit opt-in), seats go out through the `Agent` tool and the close's
  `--evidence` names `shape: agent-tool`; while seats are out, build the next fixes in a scratch copy, never the
  pinned files, and keep a timer running; outside the hub (D-961), write the Workflow args JSON to scratch and
  relaunch an interrupted pass as a NEW `Workflow` invocation carrying the ledger in `args` — never
  `resumeFromRunId`; in the hub, re-dispatch its `Agent` seats over the same ledger.
- A round is recorded only after every candidate is read, each classed as a defect of THIS change, pre-existing or
  planned before it counts; `confirmed` counts DEFECTS, never checks passed, and a gate-caught defect counts; each brief
  embeds its ledger text and states what the seat must report (a count, a verdict, an output), never the value the
  lead expects; the closing-pass brief has every seat list each slice file it read, by path, and re-check every fix
  that replaced a form against the shapes the OLD form held, as the fix's ledger row lists them; a delta brief
  lists the exact mutant ids executed, reads a unified diff, and checks ROUTED claims for routing only; a one-hop edit
  found mid-fix is named in the next brief, and a guard a fix adds goes into every brief from that next one on, by name,
  with its escape variants (quote styles, unreadable values, globbed paths) and its model boundary; stale pre-existing
  text in an edited file is RECORDED with a destination (term-coverage D4), or fixed in the same hunk and named — never
  counted; the slice ledger is round 1's claim count even at zero confirmed. A measurement or proof a brief hands a
  seat names, up front, the bound that limits it (a peak capped by the very limit being sized, a re-vendor's byte
  identity read at HEAD because neither the copy's header nor its vendoring commit's trailer records a SHA), so the seat
  attacks it as bounded, never as unbounded.
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
