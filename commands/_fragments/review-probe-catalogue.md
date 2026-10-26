# Review probe catalogue

Read the lines that match the change's SHAPE — never all of them, § Seat isolation excepted: it applies whole in every
brief that runs tests or imports pinned code — before every pin, the first and each delta, and while writing every
brief. Each is step: execute it, or name in brief why shape lacks it.

## Before the first pin, and again before each delta pin (the lead executes)

- Run the changed artifact end to end when it can run (an emitted one-liner run as emitted, under its real shell), and
  check END STATE recipe exists to produce, not only each step, against the artifact the next step compares it with (a
  lock file, a manifest), not only the source it reads; run README snippet, usage text or rewritten docstring
  instruction as caller would; one that writes live store, sends, commits, deploys or reaches host stays lead's; only a
  read that changes nothing (no write, lock, quota spend or triggered job) runs against its real host; probe each
  exception rewritten docstring says function raises.
- A line another tool injects or renders, with rendering change alters, is read back whole through that tool's output: a
  pack line in `review_rubric.py --changed <a path its globs hit>`, fragment edit's consumers, never in its source
  alone; line change leaves emitted by no invocation (a pack line with no mandate keyword) is named in brief as dropped.
- Trace entry path: the first caller reaching fixed function; enumerate every call shape through new branch and every
  input path; trace each rationale sentence's mechanism through every branch it summarises (refusals, fallbacks, not
  only the happy path), and execute every "X only when Y" claim the fix adds.
- Enumerate fix's input class whole (boundary, empty, unset, mandated, non-dict/non-string); keep adversarial input list
  for fix's new edges; enumerate each guard's ESCAPE VARIANTS in both directions — false green and false red —
  committing the positive/negative probe list beside it.
- Name defect's class and grep whole class (every site, sibling guards; `.claude/worktrees` excluded); diff sibling
  implementations side by side; before adding sibling of pinned or guarded line, read comment; port vendored code, or
  reimplement another tool's semantics (a YAML merge), prove parity by executable diff against that tool's output before
  fix lands, never a model from memory.
- One mutant per clause the edit states and one per guard it adds or alters (that guard removed — term-coverage rule
  (4): "each grader is proven it CAN fail by REMOVING THE GUARD, never by breaking an expression inside it"), written as
  a literal before/after (an ordering claim names its mutant); re-run every prior mutant and reproducing probe after
  each fix against every test file change touched, collected again with no selection that leaves test out (`-k`, node
  ids, `--lf`, `--deselect`, `-m`, `--ignore`) beyond term-coverage rule (4)'s environment-bound deselection; probe each
  new grader with its mutant.
- Run repo's structural source graders, every touched test file; feed sample row through every grader that parses;
  synced hook change: fleet copies' md5 checked.
- Execute: every factual row of relayed report, every citation in docs change; paste code path's enumeration beside doc
  sentence that lists it.
- Before widening matcher or heuristic: its fire rate and added-hit precision; classifier rules run against real
  dependency outputs; before parity claim, whether mirror can be exact with dependencies; before counted bar or spend
  scale changes, drive it over real series.
- Grep docs and ledgers for by-design rule; resolve integrity-check exemption against its real target.

## The brief's hunt lines (name the ones the shape has)

- Callers and consumers: every caller of changed exit code, output line; every consumer of changed prompt output, of
  import-time side effects; callers of normaliser's return value; every line that joins, compares or keys changed
  output; a pure helper's own return contract, not only what its callers observe; line that copies template-emitted
  claim; every gate grading old name; every reader of changed or vendored file's text that never imports it (a scaffold
  fold such as `src/fabrik/scaffold.py::_audit_log_schema_block`, a drift or sync checker), found by the lead grepping
  the hub and the fleet repos for the file's path, basename and directory and reading
  `scripts/fabrik_synced_manifest.py` for a glob that covers it (a covered file is also read through each project's
  `.fabrik/synced.lock` by `scripts/enforcement/check_synced_unmodified.py`), each hit that reads the file named in the
  brief; every outbound sink production-reaching test touches; every actor touching RLS table; placeholder resolution
  per consumer; repo-wide service lists and absence statements; every reader of changed predicate's verdict (a notice,
  message or wall line).
- Parsers: the producer's real output contract first, then parsing model; lossy cases (duplicate keys, ordering,
  whitespace), regex/strip edges, request-target grammar for URLs with its parser-differential classes named in round-1
  brief (UTS-46 mapping, `@` in userinfo, `#` or `?` before `@`, unclosed `[`); generated file is parsed by its
  generator's format; skip check reuses consumer's parser; hand-written reader whose input is source in language other
  than its own with no real parser at hand, starts from strict grammar that REFUSES any line matching none of its named
  forms, none a catch-all, its refusal executed before every pin on a line of that language's own syntax that no named
  form admits, and run by the lead over the live files the reader will read, each refusal there classed a grammar gap or
  a true out-of-grammar line; seats attack what grammar wrongly accepts; tokenizer is built only where the brief names
  the construct no line form can hold.
- Guards and rules: the guard's equivalence class (must fold, must not), what a replaced guard covered that its
  replacement does not, every exception subclass a new catch admits, false negatives classed plausible vs contrived,
  whether each matcher shortcut is covered by the general path, every rule an overriding sentence overrides (and every
  command it prescribes, in its default mode), which value wins when a new knob meets an existing per-row setting, and
  the rule's cost on the previous behaviour; the reader reports each escape shape as executed or read
- State and concurrency: who waits on new lock and behind what; new module-level state reset on every return; every
  value changed predicate sees from each writer (0 vs NULL); whether filtered counter keeps records; which fixture
  scopes run before autouse pin; env-leak fix where `delenv` on absent key records nothing; change that writes outside
  its state dir: every isolation seam (`COMMAND_RUN_DIR`, `HOME` or `TMPDIR` override).
- Failure paths: what fix does when its fallback fails; configuration-failure path; fail-soft mail or report path fed
  malformed data; shell chain whose failing step must fail the chain (a gate line gates the commit, never only prints);
  dry-run and write path diffed by field; validator's direct-call path.
- Surfaces: every connection guarded module opens; every field new serializer emits; argparse edges of flag;
  machine-parsed section markers; literal pipe inside table cell; moved reference and which sentence branch reaches it;
  each mechanism claim at every lane or version; `git check-ignore` on bare directory; defects split between hook and
  its generator; changed compose overlay read through its merged render (`docker compose -f <base> -f <overlay>
  config`); page-type or reader move: base and head are built and each page's visible text is diffed, since dist diff
  cannot see dev- or preview-only settings.
- Deletions (a change that deletes file, directory or input): a deleting probe also removes every directory it empties
  as `git rm` does (`find <root> -name .git -prune -o -type d -empty -print` prints no new line; leftover hides
  `readdirSync`); seed restoring deleted inputs first lists, by grepping code under test, each input it reads; Callers
  grep above runs for each deleted path, basename and directory, never the package; seats name, for each guard on a
  deleted input, whether it re-runs at removal or only at classification.
- The premise: the authoritative seat attacks work item's premise, not only the implementation; ask whether existing
  mechanism or fragment already covers class; edited prose checked against its rule pack's SCOPE line; an external quote
  goes to a `fabrik-researcher` seat whose brief names the version the repo pins or deploys (its lockfile or spec line)
  and asks for the claim at that version; claim about what dependency accepts or does (a guard over its keys) is checked
  against every case dependency defines; each branch and alias in its source at that version, else its versioned
  reference docs; never only the cases the author listed; seat names whole input class of finding it raises; re-vendor
  brief hands seats lead's executed byte-identity result; diff reads source's COMMITTED blob at SHA copy records (a
  `VENDORED-FROM` header, else `Vendored-From:` trailer; HEAD when neither does: `git -C <source> show <sha>:<source
  path>`) against copy minus that header, never the source's working file, where a sibling's uncommitted edit reads as
  drift; brief names source's regression test for file at that SHA, run with its import path pointed at copy; they
  re-run that command and that test first, then spend on what byte identity cannot show (every importer; its `from …
  import` names and each `module.attr` use).

## Graders

- Grade the PROPERTY across every example, never one spelling; a new assertion must fail when its subject is absent (an
  absence assertion over never-written state is vacuous); grader EXECUTES executable subject, through real production
  adapter and consumer's entry point, never reads it; premise guard asserts at call site, not constants; grader of fixed
  prose or of deterministic message asserts whole sentence it pins by equality (`==` against all of it, every line of
  message, never `in`, a prefix, a suffix or a regex over part of it), so an added clause or a leaked value fails it,
  and a grader of that text's position, of its absence or of a property across its examples sits beside that equality
  grader, never in place of it; grader of MOVED text (a sentence or row), added in edit that moves it, also fails when
  text sits at its old position; test-quality seat checks docstring claims; a fix recipe handed to a coder names one
  input it must leave unchanged and the test that holds it; grader of `path:N-M` cite asserts its first line AND its
  last line still hold text.
- Each parser-output shape owes its own red; config or regex grader is graded by running tool on mutated inputs; red
  branch of procedure step is executed as well as green; boundary fix tests both sides with exact message; numeric bound
  is derived in its comment and graded at both edges; pin exact stdout line count reads; lock-order fix ships executed
  concurrency probe.
- Mutants: one per new comparison or constant AND one against every existing assertion whose input changed, survivors
  reported only once shown to change observable behaviour (an output, return value, exit code, raised exception or
  written state diffed against the unmutated copy), and an equivalent mutant is struck with that diff quoted, never a
  test gap; counter or guard is gutted in same round to show it can fail; regression test fails when caller is reverted;
  each slice's seats write and run one mutant of their own per guard change adds, under `timeout` its brief names
  (`/fabrik-review`); one reader mutates guarded behaviour; tests slice's seats also write and run mutants of their own
  against each behaviour its tests claim; graders are written and named before next round.
- Test hygiene: a test stub records what it RECEIVED; timing test is repeated 10× under its mutation; isolation is
  proven by reversed-order run and by removing fixture; state-mutating grader leaves nothing on teardown; non-ASCII
  literals are checked by bytes; whole suite directory of changed test runs; golden value is pinned after printing its
  matched span; byte-identical refactor gets HEAD-vs-new differential harness, and fix that swaps one call, guard or
  protocol for another (`in` plus `[]` for `.get`) gets one; two emitted artifacts are diffed whole for alias change;
  red's failure message is diffed against baseline, printed beside its FAILED line; import-path fix is graded from root
  conftest and child process; grader exclusion says whether it matches exact name or pattern.

## Prose and docs fixes

- Read fragment's scope sentences; rule already in fragment is quoted in its words and pointed at; ported rule is
  re-derived against this command's machinery; parser rule is stated positively, not as terminator list; scoped
  exception beats new section note; tool claims are written from source (a sentence describing record format quotes emit
  site's keys verbatim), then checked against live corpus.
- After edit: rewrap whole paragraph by tool once each test that caps file's line length or pins its raw lines is found
  (grep `tests/` for file's basename) and run; re-read inserted sentence with one after it; long-line replacement keeps
  its neighbours' opening clauses; re-read cited range after rewording its citation; moved table rows are placed by
  computed position and checked by inversion diff; sentences test pins verbatim are marked before rewriting.
- Sweep: a corrected claim or quote across every file change touched; each sentence fix writes that restates rule
  already stated elsewhere, held to `/fabrik-review-scoped` step 3's rule; fix that narrows, widens or splits rule's
  subject is held to `/fabrik-review`'s "does the new form still hold EVERY shape the form it replaces held", with "the
  shapes enumerated from OLD form before fix is drafted, never from the new one": here each case no new clause covers,
  two now cover or only the new wording reaches, listed with where it now lands or, with its reason, that it is dropped
  on purpose, where your command records the fix (`/fabrik-review`'s Pass Ledger `method:` cell,
  `/fabrik-review-scoped`'s report); every doc line, docstring, comment and `Raises` section stating outcome fix changes
  (when function raises or deletes), found by grepping its verb and each removed name across WHOLE file, not only its
  hunks, in the round the fix lands (a `Raises` section phrased by its rule, never an enumeration that the next fix
  outdates), and every comment and docstring of a function whose behaviour a fix changes re-read whole, since a
  paraphrase names neither the verb nor a removed name; every statement of changed number or count in whole file;
  same-subject lines in pack, doc summary rows and artifact generators; residue words of flipped decision; cross-pack
  citation's terms against section it cites; `path:line` cite merge or edit shifted, remapped by CONTENT in one script
  over every doc that cites file, never renumbered by hand, and the remap runs after each round's fix, before the next
  pin, over every anchor a brief or mutant list carries.
- Claims: every factual sentence of edited paragraph re-derived, every newly rendered table cell included; every clause
  on count-fixed line, and every reworded README claim, checked against code lines it names, and sentence describing
  matcher, regex or guard written from its input space executed on both sides before pin, never from its subject's own
  docstring; count cites command (with its range — brief hands seat that exact command); code snippet in prose is
  checkable claim; evidence block in report or receipt pastes artifact's section whole; unverified hand-derived
  enumeration is deleted.
- A site round re-opened, bullet wrong two rounds running, or a mechanism the fix added and a round broke, is rewritten
  whole, never patched again.

## Seat isolation

- The brief names the fix as `git show <sha>`, each sha when it spans several commits, or pathspec-scoped diff, never a
  bare range on a branch others commit to (a range carries every sibling commit landed in it). The brief names the fix
  that way, and the diff a seat reads is still the pin's own `change.diff`, never one the lead pastes in its place; fix
  already committed is pinned with `--from <its last commit>`, plus `--base <the commit before the fix>` when it spans
  several, since working-tree pin prints each file `UNCHANGED` with only a header line in its `change.diff`, and
  `--base` without `--from` pins the working tree, a sibling's later commit or uncommitted edit included. Seats copy pin
  to their seat folder `<run scratch>/seat-<n>/` under run's `RUN-SCRATCH:` path
  (`/opt/fabrik/commands/_fragments/subagents-core.md`, the D8 paragraph; `<scratch>` below is that folder) and assert
  its md5s first; tree is staged there only by the archive or the clone this section gives, never by copying the live
  checkout; tests run against an archive of the pinned SHA by the seat prompt's `PIN_IMPORT`/`PYTEST_PINS` recipe; whole
  test tree archived so collection succeeds, live repo's `.venv` python (never `uv run`), no `.env` copied (a dummy on
  `.invalid` only for an import-failing variable). A brief lead writes tells each seat to read `PIN_IMPORT` and
  `PYTEST_PINS` when it runs pytest, in `.claude/workflows/fabrik-review-loop.js`, and gives values that recipe's
  `${args.base_sha}` and `${args.pins_dir}` stand for (and `${args.base_pin_dir}`) and seat's folder as `SCRATCH`; seat
  derives `ROOTS` as recipe says, plus roots this section's next sentence has brief add (a pins dir on `sys.path` alone,
  or pytest's `--rootdir` at copy, imports live package). The recipe names its roots by what the tests import, so the
  brief extends it to every top-level path the tests import, read or run (a test that renders `templates/`, reads
  `.windsurf/` or runs `scripts/`) and names live repo as checkout `git rev-parse --show-toplevel` prints, never
  `/opt/fabrik` from a worktree. An editable install's `.pth` entry never outranks a copy placed as `PIN_IMPORT` says;
  live code still runs instead of pin through `PYTHONPATH` entry (`PIN_IMPORT`), pytest run from live repo
  (`PYTEST_PINS`) and child process with `env=`, which resolves `.pth` again. Run Python (pytest included) as `env -C
  <scratch>/arch python -P -B …`, so the live tree is never imported. The pins line follows real layout, digest pin
  authority. A SEAT never runs `git worktree add` on the live repo (its metadata lands in the shared `.git`): a seat's
  red-on-revert overlays the revert on its archive copy by `PYTEST_PINS`, and the lead's red-on-revert and
  mutate-restore cycle run in CLAUDE.md's throwaway worktree, never a `PYTHONPATH` copy — set its upstream and link
  `.env` before its first gate. A seat test that reads git history or tracked set (`git ls-files`: neither archive nor
  pin copy has `.git`) runs in clone seat makes with `git -C <scratch> clone --shared --no-checkout <live checkout>
  clone`, checks out at `git -C <scratch>/clone checkout -q <the pass's base SHA>`, with its push to `origin` disabled
  at once (`git -C <scratch>/clone config remote.origin.pushurl /nonexistent.invalid`); that test's red-on-revert
  overlays revert on clone. Branch, worktree and stash state test creates lands in clone's `.git`; only a test that
  reads the live checkout's own branches, worktrees or stash runs in the lead's throwaway worktree. Ruff and mypy run
  from repo root with repo's own config (on copy: ruff `--no-cache --config <repo>/pyproject.toml`, mypy
  `--config-file`; ruff writes `.ruff_cache` and fails inside read-only pin without `--no-cache`); tests run by exact
  node id, except mutant run or re-run of one, which takes selection rule of `One mutant per clause` bullet; brief over
  changed code names tests that load each changed module (found by grepping `tests/` for each changed file's stem, its
  name without `.py`, or `__init__.py`'s package dotted name) for every seat to run by `PIN_IMPORT`/`PYTEST_PINS`
  recipe. A script seat runs is run from its archive copy with every path argument under scratch, and pin carries
  changed files' one-hop callees that are repo files (`review_loop_ledger.py pin` refuses the whole list when one path
  is missing, a symlink or outside the repo root). The pin also carries each file a fix's text points at by path, and
  the brief says the pin holds only the files it lists, so a seat reads any other file, the rest of a changed module's
  directory included, from the base tree with the pins laid over it (`<pins_dir>.base` when the pin was taken `--base`,
  else the archive of its `base_sha`), never from the live tree beyond what the seat prompt's recipes (`PIN_IMPORT`,
  `PYTEST_PINS`, `GATE_PINS`) take from the live disk and name UNPINNED.
- A pins-only copy is not a test tree: it holds the pins and nothing else; no package, no pytest config, no conftest,
  none of files conftest loads by path (the hub's `tests/conftest.py` loads `tests/memguard.py`; its root `conftest.py`
  imports this tree's `src`). A seat runs a Python test only through pytest, and only on a tree this section stages,
  with the pins laid over it — the archive the recipe builds (the whole test tree, the root conftest, the pytest config
  and every root the tests import, read or run, never a subset that leaves one out), the lead's base copy, or, for a
  test that reads git history or the tracked set, the clone above — never on the pins dir, a copy of it or any
  hand-assembled tree, and never with a conftest or the pytest config dropped, skipped or pointed elsewhere by any flag,
  option or environment variable (`--noconftest`, `--confcutdir`, `--ignore` of a conftest, `-p no:` on a conftest's
  plugin, `PYTEST_ADDOPTS`, `-c` or `--rootdir` naming any other file or tree, or `-o` on `addopts`, `testpaths`,
  `python_files` or another key that changes what is collected; `-o timeout=…` and the like stay legal); a test it
  cannot run that way is unverified, never run another way. A seat that runs pytest or imports pinned code needs
  unmodified tree, so its brief's pin takes `--base` (`/opt/fabrik/commands/_fragments/subagents-core.md`'s PIN
  paragraph), by shape that pass's surface has (a committed surface is pinned `--from`): `HEAD` for working-tree pin
  (its `base_sha` HEAD's commit; repo with no commit has no base copy, and `--base` is refused there), `<c>^` for a fix
  pinned `--from <c>` (never `<c>`, which calls every file `UNCHANGED`), and the commit before the fix when it spans
  several. The brief's `base_sha` is then one pin records, and gives `<pins_dir>.base` as recipe's
  `${args.base_pin_dir}`; each seat copies that tree in place of archive steps of `PIN_IMPORT` and `PYTEST_PINS`. Where
  the including command puts pins there, a base copy is whole commit (some 120 MB in hub) beside pins dir in durable
  `SCRATCH:` folder, which `start` keeps 14 days: once pass is adjudicated, lead removes it (`chmod -R u+w
  <pins_dir>.base`, then `rm -rf <pins_dir>.base`, each its own command), since every pass pins afresh and delta brief
  reads previous `pins_dir`, never its base copy.
- A delta brief also names the previous pass's `base_sha` (for the working-tree pin `/fabrik-review-scoped` step 5
  takes, the HEAD its `MANIFEST.json` records as `base_sha`, read back, never verified, since no md5 manifest covers it,
  and null in a repo with no commit; for any other pin the brief names the commit itself, since one taken `--base`
  records that commit (else its `--from` ref) and one written before `base_sha` was recorded has none) and pins_dir, for
  the bounded hop's reader run (a reader passing on the previous round's pin and failing on it with only the fix hunks
  applied). The lead first diffs two pins' files (`diff -r -x change.diff -x 'MANIFEST*' <previous pins_dir> <this
  pins_dir>`) and two `base_sha`s (`git diff --name-only <previous base_sha> <this base_sha>`), and states in brief that
  difference is round's fix alone, naming any other hunk or path, which leaves every reader it touches `unverified`
  (each `Only in` line is named and classed from `git diff --name-status <previous base_sha> <this base_sha>` for what
  fix committed and `git status --short --untracked-files=all --ignored -- <path>` for what it did not, `change.diff`
  carries no entry for removed path; a path the fix added, modified, removed or renamed is the fix's own, and its
  readers run on both pins, a removal or rename whose old path this pass's `base_sha` still holds leaving those readers
  `unverified`; a seat greps a heading or term another section cites over each pin's tree, where its citers live; any
  path pinned in only one pass is another path; a directory line covers every listed path under it; a fix's own path's
  readers are the tests the `tests/` grep above finds and, for a document, the citers the heading-or-term grep below
  finds, and an importer outside `tests/` is named and left `unverified`); seat then runs each reader once on each pin
  by `PIN_IMPORT`/`PYTEST_PINS` recipe with that pin's `base_sha`; reader pre-pin section keeps lead's ("one that writes
  a live store") takes § Loop bookkeeping's `unverified` route; reader that fails on previous pin is no evidence of
  break, `RECORDED` with its destination.
- No `uv`/`pip`, no live API key outside suite's fixtures, every writing verb outside scratch named and forbidden; one
  grep form; large output goes to seat's scratch first; adjudication authority (CLAUDE.md, packs) is read at pin; brief
  names which shell guard seat is under (the worktree guard reads word `git` inside `-c` program or heredoc as git call)
  and hands readers ready probe harness file, never promising a tool the seat does not have (the Write tool); a claim
  only the home directory can settle is recorded up front for the lead. A scratch repo seat makes (the `git init` in
  pin, clone above) is checked before its first git write: `git -C <it> rev-parse --show-toplevel` prints its own path
  (an init that failed under hub's `.tmp/` leaves later git calls on live repo). A test or probe that runs git runs with
  `GIT_CONFIG_GLOBAL` at empty file, `GIT_CONFIG_NOSYSTEM=1`, and `HOME` and `XDG_CONFIG_HOME` at empty folders under
  its scratch, with `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME` and `GIT_COMMITTER_EMAIL` set when it
  commits (an older git ignores `GIT_CONFIG_GLOBAL` and reads `$HOME/.gitconfig`).
- Every file grader reads is pinned, uncommitted module under test included; "nothing changed for readers" claim is
  proven on pinned input; test that needs database (the suite skips or fails it without database variable; no `.env`
  copied, `.invalid` dummy serves imports only) runs with the variable the suite reads (`TEST_DATABASE_URL`, an isolated
  `DATABASE_URL`) in place of that dummy, and a seat probe that must connect uses the same variable; both connect over
  form lead proved by one connect before pin (a unix-socket DSN where TCP `localhost` fails password auth), and where
  only a password form connects the lead runs that test or probe itself and quotes its result, never writing the
  password into a brief, so no seat skips the test, re-implements it or probes auth; concurrent sibling run on shared DB
  is known false red; seen-red on DB-writing script names its sandbox; ledger row whose fix landed in file outside pin
  (a CHANGELOG hunk) has that file pinned next pass, so seat never reads the base copy.
- Overlay and pin currency: the brief lists every pinned path, dot-dirs (`.fabrik/`) included; a seat copies each file
  to its own path or runs `cp -r <pin>/. <dest>/` then `chmod -R u+w <dest>`, never `cp -r <pin> <dest>` onto a
  directory that exists; `pin` writes pin and its `<pins_dir>.base` tree read-only, files and directories, so a seat
  that copies the base tree runs `chmod -R u+w <dest>` right after that copy and before laying the pins over it, and
  again after it, since a pin file the base lacks lands read-only; it checks each overlaid file's md5 against manifest
  before its first run. `git archive` omits untracked files, so pin also carries gitignored inputs tests read (the
  repo's `.worktreeinclude` list, `.env` excepted). Copy a gitignored GENERATED file the code imports from the live disk
  into the archive tree, named UNPINNED. Each later pass's brief names its own pin dir and digest, cut after the last
  fix, never the round-1 pin, and seat scratch dirs from earlier rounds are kept until the close, so a seat re-runs its
  saved probes.

## Loop bookkeeping

- Run `dispatch_headroom.py` before pin, then stamp `command_run.py dispatch --seats <SEATS + one refuter per unit>`
  before dispatch; stamp is upper bound, closed by round's `--seats`; SEATS 0 on box cap is in-turn wait (re-run once
  minute), and when the `Workflow` tool is absent or cannot load the script, or the session is in the hub (D-961: the
  hub never calls the `Workflow` tool), or the operator did not invoke this run (the tool runs only on their explicit
  opt-in), seats go out through the `Agent` tool and the close's `--evidence` names `shape: agent-tool`; while seats are
  out, build the next fixes in a scratch copy, never the pinned files, and keep a timer running; outside the hub
  (D-961), write the Workflow args JSON to scratch and relaunch interrupted pass as NEW `Workflow` invocation carrying
  ledger in `args`; never `resumeFromRunId`; in the hub, re-dispatch its `Agent` seats over the same ledger.
- A round is recorded only after every candidate is read, each classed as a defect of THIS change, pre-existing or
  planned before it counts; `confirmed` counts DEFECTS, never checks passed, and a gate-caught defect counts; each brief
  embeds its ledger text and states what seat must report (a count, a verdict, an output), never the value the lead
  expects; closing-pass brief has every seat list each slice file it read; delta brief lists exact mutant ids executed,
  reads unified diff, and checks ROUTED claims for routing only; one-hop edit found mid-fix is named in next brief;
  guard fix adds goes into every brief from then on; stale pre-existing text in edited file is RECORDED with a
  destination (term-coverage D4), or fixed in the same hunk and named; never counted; slice ledger is round 1's claim
  count at zero confirmed. A measurement or proof brief hands seat names, up front, bound that limits it (a peak capped
  by very limit being sized), so seat attacks it as bounded, never as unbounded.
- Lint or format findings are compared against HEAD, against committed diff, under every claimed toolchain version,
  before reported or refuted; tests re-run after last lint fix; refutation that later commit lands is checked against
  completion gate; read callee before confirming wrong-method finding; refuter that needs forbidden surface marks it
  `unverified` naming surface; run files reader names, not every grep hit.
- Remainder rounds: a remainder round names classes its fixed set re-sweeps; it never fixes a RECORDED candidate;
  finding it raises is fixed when it is defect of fixed set and routed when not; premise-refuted verdict is re-probed
  under later reader's rule; slice trim left with one finder gets its second next wave, or, when cap is known before
  round 1, merge two low-risk slices.
- Route-up and close: a fix that adds file re-applies step 1's count; critical finding on published contract routes up
  at once; artifacts review itself created go to follow-up loop; RECORDED residue whose surface is another beat's is
  mailed at close; shared-ledger hunks land before closing pass; completion gate runs before terminal round is recorded;
  under operator directive forbidding subagents, close's `--evidence` declares waiver.
