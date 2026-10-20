// fabrik-review-loop — the D-335 review loop as a Claude Code workflow script (chunk 5; D-346, D-347, D-348).
//
// WHAT IT MOVES OUT OF THE LEAD'S TRANSCRIPT: the seat dispatch, the seats' reports, and the execution of
// every candidate's check. The lead launches ONE call per pass, gets ONE ledger back, executes only the
// CONFIRMED candidates' commands itself (Phase 2 of /fabrik-review), fixes, and launches the next pass as a
// NEW invocation carrying this pass's ledger in `args` — never `resumeFromRunId` (a resumed run re-runs every
// agent after the first fan-out: anthropics/claude-code #63102 #67488 #74599 #95076).
//
// THE SHAPE IS D-335 / D-344, UNCHANGED: the surface cut into disjoint slices; by default TWO cheap finders per
// slice (one Sonnet, one Haiku `fabrik-reviewer`), each over the whole slice, candidates UNIONED never voted;
// no Opus finder. A SECTION-partitioned loop (/fabrik-spec-review, /fabrik-plan-review — D-212/D-218, kept by
// D-344 until its measure is in) names its own seats per slice: `models: ['opus']` on the rule/grammar sections,
// `['sonnet']` on the rest, `agent: 'fabrik-researcher'` for a cited-fact slice, `scope` naming the sections; ONE fresh Sonnet refuter per slice EXECUTES every candidate's check and returns the command
// and its output (§ 4.9 findings 27, 36, 41 — row 5b: a seat per candidate mostly ran one grep) — save a check the
// never-execute rule in SEAT_ISOLATION forbids, which comes back unverified with its cited lines (kaizen 01M4W2D1N8); the lead
// re-runs the confirmed ones. Every seat names its model AND effort — an unnamed one inherits the session's
// (finding 43): finders at `medium` with the recall-first brief kept (finding 38), the refuter at `high`. Every pass after the first is the same slice ownership re-verifying the
// slice's claim ledger; refuted and recorded candidates never re-open (D-206, D-230, D-339).
//
// COBRA NOTES (D-253) — the cheapest way to satisfy each measure this script produces WITHOUT the outcome:
//   * lead turns ≤ 15 → push everything into seats: countered by the minutes and tokens rows read WITH turns.
//   * "every file read" → a finder lists files it never opened: `files_read` is the finder's own claim, so the
//     verify stage and the lead's Phase-2 execution are what catch a phantom read; a gap is LOGGED here and the
//     slice is unverified — the script never silently narrows a slice. A seat whose files_read names NO slice file
//     is a failed seat (01M4C00TSS); the cheapest way past that is to list one slice file never opened, which only
//     the same verify stage and execution catch — the zero case is closed, the phantom read is not.
//   * the capture-recapture estimate → two finders that share notes or a model inflate the overlap and read
//     "nothing left": the finders are two models in two contexts, the number is printed as ADVICE and nothing
//     keys on it.
//   * "verified" → the refuter returns a plausible command it never ran: the lead re-executes every
//     CONFIRMED command before a fix (Phase 2), so a fabricated confirmation costs one lead command, and a
//     fabricated refutation is caught by the same slice's next pass or the escaped-defect row (§ 6).
//   * `scope` → a section slice's coverage is NOT diffed: a seat can open the file and read only another slice's
//     sections, and `files_read` still lists it. A section-read field would be the same self-claim as `files_read`,
//     so nothing here counts sections; the refuter's execution and the lead's Phase-2 re-run are what catch it.
//   * `closable` → the cheapest way to a closable slice is a refuter that answers `refuted` to everything:
//     a refutation with an empty command or output is rewritten to `unverified` (finding 36 — refutation
//     needs counter-evidence), an unanswered candidate is `unverified`, and `unverified` never closes. What
//     the script cannot see is a refutation whose command was never run; the lead executes the refutations
//     it relies on (Phase 2). `closable` is a floor for "may close", never a reason to stop early: ≤ 3
//     passes is a target, not a cap (operator ruling 2026-09-23).
//
// ARGS (all strings unless noted; the command source builds them — see /opt/fabrik/docs/reference/review-loop-workflow.md — hub-only, so cited hub-absolute):
//   pass: 1, 2, 3, … (unbounded) · surface · base_sha · digest · pins_dir · scratch_dir (this run's RUN-SCRATCH folder —
//   each seat writes in its own `seat-p<pass>-<digest8>-…/` child of it) · brief (the dispatcher's shared text:
//   hunt classes, lessons, house rules) · slices: [{ name, files: [..], priority, scope?, models?, agent?,
//   ledger?: [ { id, file, line, claim } | "<the claim as one string>" ] }] (ledger present on pass ≥ 2; any other
//   row shape is REFUSED before a seat is dispatched; `models` is one to three distinct of opus|sonnet|haiku,
//   default ['sonnet', 'haiku'] (a third, Opus, is /fabrik-execute-plan's per-round Opus floor on its riskiest slice); `agent` is fabrik-reviewer (default) or fabrik-researcher, and seats BOTH the
//   finders and the refuter; `scope` is the sections of `files` the slice owns) · box_minutes (default 15) ·
//   pin_manifest ({ path: md5 }, from `review_loop_ledger.py pin` — REQUIRED: absent, null, or lacking a slice file
//   REFUSES the launch) · base_pin_dir? (the read-only base
//   tree `pin --base` wrote; seats copy it instead of running git archive)
// RETURNS one ledger: { pass, closable, pinned, slices: [{ name, files, seats: [{ model, files_read, raised, failed (null, or no
//   slice file in files_read) }],
//   gaps, raised, distinct, overlap, estimate_unseen, candidates: [..], recorded: [..] (candidates on a
//   `recorded: true` ledger claim, never refuted), verdicts: [..], refuter: { retried, failed,
//   unanswered, reason }, closable, open: [..] }], dropped_seats (failed finders), failed_refuters }

export const meta = {
  name: 'fabrik-review-loop',
  description: 'D-335 review loop: two cheap finders per slice, one refuter per slice, one ledger back',
  phases: [
    { title: 'Find', detail: 'each slice finders — by default one Sonnet and one Haiku fabrik-reviewer — candidates unioned' },
    { title: 'Verify', detail: 'one fresh Sonnet refuter per slice executes every candidate and returns command + output' },
  ],
}

const CANDIDATE = {
  type: 'object',
  required: ['id', 'file', 'line', 'failure_class', 'claim', 'scenario', 'check', 'confidence'],
  properties: {
    id: { type: 'string' },
    file: { type: 'string', description: 'repo-relative path' },
    line: { type: 'integer' },
    failure_class: { type: 'string' },
    claim: { type: 'string', description: 'one line: what is wrong' },
    scenario: { type: 'string', description: 'inputs/state → wrong output or crash' },
    check: { type: 'string', description: 'the executable command or pinned read that proves or refutes it' },
    confidence: { enum: ['CONFIRMED', 'PLAUSIBLE'] },
  },
}

const FINDINGS = {
  type: 'object',
  required: ['files_read', 'candidates', 'notes'],
  properties: {
    files_read: { type: 'array', items: { type: 'string' }, description: 'EVERY file you opened, repo-relative' },
    candidates: { type: 'array', items: CANDIDATE },
    ledger_status: {
      type: 'array',
      description: 'pass ≥ 2 only: one row per ledger claim; each claim states a DEFECT — DEFECT_PRESENT it persists, DEFECT_ABSENT it is absent, NEW the fix introduced one',
      items: {
        type: 'object',
        required: ['id', 'status', 'command', 'output'],
        properties: {
          id: { type: 'string' },
          status: { enum: ['DEFECT_PRESENT', 'DEFECT_ABSENT', 'NEW'] },
          command: { type: 'string' },
          output: { type: 'string' },
        },
      },
    },
    notes: { type: 'string', description: 'coverage statement and MACHINERY, last' },
  },
}

const VERDICT = {
  type: 'object',
  required: ['id', 'verdict', 'command', 'output', 'mechanism'],
  properties: {
    id: { type: 'string' },
    verdict: { enum: ['confirmed', 'refuted', 'recorded', 'unverified'] },
    command: { type: 'string', description: 'the exact command you ran on the pinned copy' },
    output: { type: 'string', description: 'its output, at most 1500 characters' },
    mechanism: { type: 'string', description: 'one sentence: WHY it fails or does not' },
    destination: { type: 'string', description: 'recorded only: backlog row, mail, sibling ticket' },
  },
}

const REFUTATION = {
  type: 'object',
  required: ['verdicts'],
  properties: { verdicts: { type: 'array', items: VERDICT, description: 'one verdict per candidate id you were handed' } },
}

const DEFAULT_MODELS = ['sonnet', 'haiku']
const KNOWN_MODELS = ['opus', 'sonnet', 'haiku']
const AGENTS = ['fabrik-reviewer', 'fabrik-researcher']
const box = args.box_minutes || 15

// A slice's seats are refused HERE, before any seat runs: an unknown model or agent, an empty or repeated model
// list, or more than three finders (the capture-recapture estimate is defined over exactly two and is null otherwise).
function normalizeSeats(slice) {
  const models = slice.models === undefined ? DEFAULT_MODELS : slice.models
  if (!Array.isArray(models) || models.length < 1 || models.length > 3 || new Set(models).size !== models.length || !models.every((m) => KNOWN_MODELS.includes(m))) {
    throw new Error(`slice ${slice.name}: models must be one to three distinct of ${KNOWN_MODELS.join('|')} — got ${JSON.stringify(slice.models)}`)
  }
  const agentType = slice.agent === undefined ? 'fabrik-reviewer' : slice.agent
  if (!AGENTS.includes(agentType)) throw new Error(`slice ${slice.name}: agent must be one of ${AGENTS.join('|')} — got ${JSON.stringify(slice.agent)}`)
  return { models, agentType }
}

// A ledger row is `{ id, file, line, claim }` or the claim as one string; anything else is refused HERE, before a
// seat runs — a string row once rendered as `undefined · undefined:undefined · undefined` and nothing failed.
function normalizeLedger(slice) {
  return (slice.ledger || []).map((row, i) => {
    if (typeof row === 'string' && row.trim()) return { id: `${slice.name}-L${i + 1}`, claim: row.trim() }
    if (row && typeof row === 'object' && typeof row.claim === 'string' && row.claim.trim()) {
      return { ...row, id: row.id || `${slice.name}-L${i + 1}` }
    }
    throw new Error(`slice ${slice.name}: ledger row ${i + 1} is neither { id, file, line, claim } nor a claim string — got ${JSON.stringify(row)}`)
  })
}
// kaizen 01M4CJKZRH (row 1791120510): `closable` is `every` over the slices, so an empty list read as a CLOSING round
// having read nothing — refused HERE, before anything runs, like a bad model or ledger row
if (!Array.isArray(args.slices) || args.slices.length === 0) {
  throw new Error(`slices must be a non-empty list — got ${JSON.stringify(args.slices)}: a launch over zero slices reads nothing and would return closable`)
}
// review A-S1: a null entry crashed below with a raw TypeError, and a number was dropped later as a thrown stage
args.slices.forEach((s, i) => {
  if (!s || typeof s !== 'object' || Array.isArray(s)) throw new Error(`slices[${i}] must be an object { name, files, … } — got ${JSON.stringify(s)}`)
  // Opus critique 6: the pin check below reads every slice's files on every launch, so a missing list is refused here
  if (!Array.isArray(s.files) || s.files.length === 0 || !s.files.every((f) => typeof f === 'string' && f)) {
    throw new Error(`slices[${i}].files must be a non-empty list of repo-relative paths — got ${JSON.stringify(s.files)}`)
  }
})
for (const s of args.slices) Object.assign(s, { ledger: normalizeLedger(s) }, normalizeSeats(s))
// kaizen 01M4PNBVJ1 row 1791149709: every seat's paths are built from these, and the shell returns to the LIVE
// checkout before every call, so a relative one lands a seat's probes in the live tree. The script has no
// filesystem, so creating the dirs stays the lead's; `review_loop_ledger.py pin` writes the pins absolute.
// mail 01M4Z8X09Y: every seat folder is a `seat-` child of scratch_dir (the run's RUN-SCRATCH folder), which is
// what `command_run.py round`'s size line globs; the pass and the pin digest are in the name because one
// scratch_dir serves every pass of a run, and a reused folder makes the seat's `cp -r <pin> SCRATCH/arch` nest
// the copy under the stale one (Opus design critique 1). Both are stripped to [A-Za-z0-9] — they become a path.
const SEAT_TAG = `seat-p${String(args.pass ?? '').replace(/[^A-Za-z0-9]/g, '')}-${String(args.digest ?? '').replace(/[^A-Za-z0-9]/g, '').slice(0, 8)}`
for (const key of ['pins_dir', 'scratch_dir', 'base_pin_dir']) {
  const v = args[key]
  if (key === 'base_pin_dir' && (v === undefined || v === null || v === '')) continue
  if (typeof v !== 'string' || !v.startsWith('/')) throw new Error(`${key} must be an absolute path — got ${JSON.stringify(v)}: every seat builds its paths from it and runs from the live checkout`)
}

// kaizen 01M4CGJZAX: a workflow script has no filesystem, so the lead's `review_loop_ledger.py pin` writes the
// pins (read-only) and hands back `pin_manifest`; a launch without it, or with a slice file it does not hold, is
// refused HERE, before any seat runs. Optional under D-663 until every launcher passed it (kaizen e29ffb101).
// COBRA (D-253): a typed map of the right shape passes this check — the script cannot hash — so the pass reader's
// `read --pins` (UNPINNED / NOT CHECKED) stays the check that catches a fake.
const PIN_HOW = 'run `python3 scripts/review_loop_ledger.py pin --pins-dir <a new dir> <every slice file>` from the repo root (a project copy without the verb: the hub\'s /opt/fabrik/scripts/review_loop_ledger.py, same arguments) and pass the pin_manifest it prints, naming each slice file exactly as pin printed it; a file pin refuses is not a slice file (the refusal names why): review it through its callers in the slice, or run the agent-tool fallback'
const m = args.pin_manifest
if (m === undefined || m === null) throw new Error(`pin_manifest is required — ${PIN_HOW}`)
if (typeof m !== 'object' || Array.isArray(m) || !Object.values(m).every((v) => typeof v === 'string' && /^[0-9a-f]{32}$/.test(v))) {
  throw new Error(`pin_manifest must map each pinned path to its md5 — got ${JSON.stringify(m)}; ${PIN_HOW}`)
}
// review A-S1: `pin` keys each path by os.path.normpath, so a slice file is normalised the same way —
// `a/./b.py`, `a//b.py`, `./a/b.py` and `x/../a/b.py` all name the pin `a/b.py`
const norm = (p) => String(p).split('/').reduce((out, seg) => {
  if (seg === '' || seg === '.') return out
  if (seg === '..' && out.length && out[out.length - 1] !== '..') return out.slice(0, -1)
  return [...out, seg]
}, []).join('/')
const held = new Set(Object.keys(m).map(norm))
const unpinned = args.slices.flatMap((s) => s.files.filter((f) => !held.has(norm(f))).map((f) => `${s.name}:${f}`))
if (unpinned.length) throw new Error(`pin_manifest holds no pin for ${unpinned.join(', ')} — ${PIN_HOW}`)
// review A-S4: every slice file now matches a pin, so it is handed on in the manifest's form — the path the seat
// reads is the pin's (`<pins_dir>/x/../a/b.py` would need `x` to exist)
for (const s of args.slices) s.files = s.files.map(norm)
const pinned = true
// mail 01M4PHYNXJ row 1791418327: the stamp the lead owes — finders plus one refuter per slice — named before any
// seat runs, as a cross-check of the `dispatch --seats` taken before launch (`review_loop_ledger.py next --args`
// prints the same count before the launch)
{
  const finders = args.slices.reduce((n, s) => n + s.models.length, 0)
  const n = args.slices.length
  log(`DISPATCH: ${finders} finder seat(s) over ${n} slice(s) + up to ${n} refuter(s) = stamp ${finders + n}; a finder or refuter retry runs after the seat it replaces ends and stays inside this stamp`)
}

function ledgerLine(c) {
  return c.file ? `  - ${c.id} · ${c.file}:${c.line} · ${c.claim}` : `  - ${c.id} · ${c.claim}`
}

// 01M469D3 (brand-identiy-creator): the probe recipe above does not hold for a PYTEST run from the live
// repo — pytest resolves its rootdir and ini from where it runs and prepends the live tree, so a seat's
// mutant run reported a false "35 passed". Shared by the finder and the refuter so the two never drift.
// row 1791115993: with the lead's read-only base tree the seat copies it instead of archiving the live repository
// (a seat once wrote an 87 MB whole-repo archive into /opt/fabrik building its own).
const BASE_PIN = args.base_pin_dir
  ? `A read-only copy of the WHOLE base commit is at ${args.base_pin_dir}, written by the lead: in place of the archive and tar steps below — skip their mkdir, ls-tree, git archive, tar and ROOTS steps entirely: the copy is already the whole commit — run \`cp -r ${args.base_pin_dir} SCRATCH/arch\` with SCRATCH/arch not yet created, then, as its own command, \`chmod -R u+w SCRATCH/arch\` — the copy keeps the read-only bits, so without the chmod overlaying a pin fails and you would run the BASE bytes, not the pin. Copy the WHOLE directory with plain \`cp -r\`, never a part of it and never with \`-L\`: a tracked relative link (the hub's \`scripts/verify_prod_parity.py\` points into \`templates/\`) dangles in a partial copy, and a followed link is a frozen base copy the pin overlay no longer reaches, so you would run the base bytes through it. A link that dangles in the base copy is the base's, and a tracked path missing from it is a member the lead's \`pin --base\` SKIPPED (an absolute or escaping link — \`git ls-tree ${args.base_sha} -- <that path>\`, its own command, shows it as mode 120000): neither is a red of the change. `
  : ''
const PIN_IMPORT = `${BASE_PIN}To IMPORT a pinned module, never put the pins dir on sys.path alone: it holds only the pinned files, so an installed package from the live checkout wins and you execute the wrong code. Instead, from your working directory (the live repo, read only), build an archive copy with ONE git command per Bash call — never a git command inside \`$( )\`, a loop, a pipe or an \`&&\` chain, and literal paths in every command — git, tar or python alike — never a \`$VAR\` (the worktree-isolation guard of a linked worktree refuses those shapes): run \`mkdir -p SCRATCH/arch\`, then \`git archive -o SCRATCH/arch.tar ${args.base_sha} ROOTS\`, then \`tar -xf SCRATCH/arch.tar -C SCRATCH/arch\`, with ROOTS every top-level path the code or its tests import, read or run (e.g. \`src edit_products.py templates\` — a test that reads \`templates/\` or \`.windsurf/\`, or runs \`scripts/\` by subprocess, needs that root too), listed from \`git ls-tree --name-only ${args.base_sha}\` run ALONE first — never one package such as src/media_edit (a package that imports a sibling package or a root module fails with ModuleNotFoundError in a one-package archive) — and when unsure, the whole commit (\`git archive -o SCRATCH/arch.tar ${args.base_sha}\` with no paths): over-inclusion is safe and SCRATCH your own scratch dir — git archive only reads the repo and tar -C writes only inside SCRATCH — then overlay EVERY pinned file of the run onto SCRATCH/arch — each path in the pins dir's MANIFEST.md5, not only your slice's (a slice's tests may import another slice's module) — with ONE program: \`python -P -B -c 'import hashlib,os,pathlib,shutil; A="SCRATCH/arch"; L=[l.split("  ",1) for l in pathlib.Path("${args.pins_dir}/MANIFEST.md5").read_text().splitlines()]; [(os.makedirs(os.path.dirname(A+"/"+f),exist_ok=True), os.path.islink(A+"/"+f) and os.unlink(A+"/"+f), shutil.copyfile("${args.pins_dir}/"+f, A+"/"+f)) for m,f in L]; print("overlaid", len(L), "md5 mismatch", [f for m,f in L if hashlib.md5(pathlib.Path(A+"/"+f).read_bytes()).hexdigest()!=m])'\` (MANIFEST.md5 lists no manifest file and no change.diff, so neither lands in the archive), put the directory that HOLDS the top-level import name on sys.path (SCRATCH/arch/src for \`import fabrik\`; SCRATCH/arch when src/ is itself a package, as in \`import src.copy\`) at the index of the first entry ending in site-packages or dist-packages, or at the end when there is none — never at index 0, where a package named like a standard-library module (a src/copy/) shadows the stdlib; run every probe as \`python -P -B\` (without -P the working directory, the live repo, sits ahead of your entry and its code wins; -B writes no bytecode) — -P drops ONLY the working directory: a PYTHONPATH in your environment still sits ahead of your entry, so drop its entries from sys.path in the program; an editable install's .pth path lands after site-packages, so your entry already beats it, and an editable finder on sys.meta_path answers only for a name the archive lacks, so archive the whole package — the repo's .venv python when it has one — and, when ROOTS holds src/fabrik, \`os.environ["FABRIK_ROOT"]="SCRATCH/arch"\` in the program's leading line below (a hub module resolves its write root at import, so a probe run from the live repo writes that checkout's data/). Set the scratch home INSIDE the program, never in front of the command, where the guard refuses it in every spelling: begin the \`-c\` program with \`import os,site; os.environ["PYTHONUSERBASE"]=site.getuserbase(); os.environ["HOME"]="SCRATCH/home"; os.environ["TMPDIR"]="SCRATCH/tmp"\` (mkdir both) — the user base first, so a child process the probe starts keeps your --user packages — and run a script file the read-before-execute rule allows as \`python -P -B -c '<that line>; import runpy,sys; sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0], run_name="__main__")' <script> <args>\`; a home set this way also reaches any git a probe starts, which the guard cannot see, so never write a .gitconfig into SCRATCH/home; check each overlaid file with \`cmp\` against its pin (a batched copy can silently not land); and print the module's \`__file__\` beside every result: a path outside SCRATCH means you ran the live tree, not the pin. Without the lead's base copy (a seat with one skipped these archive steps), a tracked symlink needs the same care in a partial archive: run \`git ls-tree -r ${args.base_sha}\` as its own second command, redirected into a file under SCRATCH (a mode 120000 row is a link, and \`git show ${args.base_sha}:<link>\` prints its target), add to ROOTS the top-level path each link under a listed root points into, repeating for every root that adds (a link archived without its target dangles: the hub's \`scripts/verify_prod_parity.py\` points into \`templates/\`), and after the tar step delete from SCRATCH/arch every link whose target is absolute or climbs out of the repo — tar extracts it as it stands, so it resolves beside SCRATCH/arch, maybe into a live tree — and name it UNPINNED; the overlay program replaces a link the change turned into a file, never writing through it. The archive is ${args.base_sha} plus the run's pins, so a file outside the run's pins is at its ${args.base_sha} bytes: a later fix to it is invisible to you, and a result that rests on such a file says so. In a project repo the fleet-synced scripts and rule packs (\`scripts/enforcement/\`, \`.windsurf/rules/\`) are gitignored, so neither \`git archive\` nor \`git show <sha>:\` reaches them: a slice file is still read from its pin, but a synced dependency outside the slice is copied from the live disk into SCRATCH/arch, named UNPINNED in your notes, and a result resting on it reported unverifiable against the pins. A subject that reads the SIBLING repo fabrik-lib through the hub root — the scaffold's \`FABRIK_LIB_DIR\`, \`FABRIK_ROOT.parent / "fabrik-lib"\` — finds nothing beside SCRATCH/arch: a missing audit-log or auth module raises FileNotFoundError, but a missing docs-site only warns and its test SKIPS, so archive \`scripts/\` with it (the scaffold imports a manifest from FABRIK_ROOT/scripts as it loads) and, before any probe, run ONE command, \`ln -sfn /opt/fabrik-lib SCRATCH/fabrik-lib\` — \`-n\` is load-bearing: a plain \`ln -s\` run a second time follows the existing link and writes a new one INSIDE /opt/fabrik-lib — (the layout the hub's own worktrees and merge_request's throwaway worktree use), never a copy of the live tree; run pytest with \`-rs\` and read a \`fabrik-lib/docs-site not present\` skip as the missing link, never as a result. The link is READ-ONLY: never write, chmod or delete through it, and pass \`-B\` to every python the probe starts — it is per interpreter, and it is what keeps bytecode out of the link. fabrik-lib is another repo, never in the run's pins: a result resting on it — through the link, through any code that names \`/opt/fabrik-lib\`, or through the tests' \`FABRIK_LIB_DIR\` env default, which the scaffold does not read — is UNPINNED. A scaffold probe stays offline and in SCRATCH: call \`create_project\` with its default \`provision=False\` and a \`base=\` under SCRATCH (its default base is /opt), never the \`fabrik scaffold\` CLI (it opts in, then saves the registry, runs a catalog subprocess and the deploy wiring outside the offline gate) and never \`provisioning()\`, and add \`os.environ["FABRIK_SCAFFOLD_OFFLINE"]="1"\` to the program's leading line — the test conftest pins it for a pytest session only.`
const SEAT_ISOLATION = ` ISOLATION (seats have damaged live trees, and once deleted every session's skills by rmtree under the home directory): create, modify or delete NOTHING outside SCRATCH — not $HOME (\`Path.home()\`, \`~\`, \`expanduser\`), not the live checkout, not /tmp outside SCRATCH; a probe that needs a home-relative or installed-corpus path must set HOME, TMPDIR and the module's path constants to SCRATCH first (the tests' monkeypatch pattern; \`tempfile\` writes under TMPDIR, /tmp by default), never act on the real one — the recipe's PYTHONUSERBASE line only READS the real user base, so your --user packages still import. On a refused command: a refusal that names a shape or a path (a \`seat guard (…)\` line, the worktree guard's shapes) is a rule: fix the named shape, every path still under your scratch dir, never re-send it unchanged; a refusal that names neither is the permission classifier, which can refuse a compliant command and accept it moments later: run the SAME command once more unchanged; refused again, reach the same bytes by another command into the same destination under your scratch dir (the pinned or base copy, by \`cp -r\` then \`chmod -R u+w\`, when the brief names one), else mark that check unverified — never a different destination — and say in MACHINERY which command was refused how many times of how many tries. A command reshaped after any refusal, a guard's or the classifier's, never disguises the refused act: fixing the named shape, or changing the command or the tool, is allowed, but a refused name or path assembled, split or encoded (such as \`'gi'+'t'\`) is the same call, so an act no allowed shape reaches is marked unverified and named in MACHINERY. The shell returns to the LIVE checkout before every Bash call, so every path a command, script or env var writes or runs is ABSOLUTE under SCRATCH — a relative path is safe only after a cd to an absolute SCRATCH path inside the SAME call or program; a git verb that WRITES a repo — ANY verb that changes its refs, index, tree, config or objects, these being examples only: init, clone, add, commit, checkout, reset, stash, restore, fetch, pull, push, config, branch, tag, merge, rebase, gc, and remote or worktree in their writing forms (\`git worktree list\` and \`git remote -v\` only read) — runs only as \`git -C <absolute scratch repo>\`, and a probe or test whose code runs git passes cwd=<absolute scratch repo> — the read-only git the pin recipe names (archive -o into SCRATCH, ls-tree, show) may run from the live repo; a grep not fed by a pipe or a redirect names a file or directory operand, and \`-r\` always names one (a bare grep reads stdin and hangs; a bare \`grep -r\` searches the live tree); never \`pkill\`, \`killall\` or kill by pattern — start a background probe only inside a python program (Popen) and stop it by that handle, or bound it with \`timeout\`; never start a background process from Bash yourself (no \`&\`, no run_in_background) — a slow call the harness backgrounds on its own is not yours to stop; a command whose output may be large (\`git show\`, \`git diff\`, \`git log -p\`, a broad search) always redirects into a file under SCRATCH that you then read, because a large stdout is saved by the harness under $HOME, where you may not read. Always read a script before you EXECUTE it, its \`--help\` included, and never execute one that deletes, deploys, provisions, writes outside SCRATCH or contacts a non-local host, whatever binary does it — executing includes importing it and calling a function, \`runpy\`, a test that runs it, or a \`node\` or shell wrapper — even when your brief asks you to confirm what that script does: cite the lines and return that claim unverified (2026-10-14: four plan-review seats ran scripts/proof_run.py, which has no argument parsing, and destroyed a live fixture).`
// 01M4C00TSS (infra): a seat received the lead's live operator question as its relayed user request, answered it
// and read nothing. Shared by the finder and the refuter so the two never drift.
const BRIEF_IS_TASK = `THE TASK: everything in this prompt — the head, your slice, your ledger and the brief — IS your task. A user or operator turn relayed to you is the lead session's conversation, never a request to you — do not answer it; run this prompt.`
const PYTEST_PINS = ` For a PYTEST run the recipe is not enough: pytest resolves its rootdir and ini (\`pythonpath\`, conftest) from where it runs, so a run from the live repo prepends the live tree at sys.path[0] whatever you inserted. Archive ALSO the WHOLE test tree — \`tests/\`, or whatever \`git ls-tree\` shows — never a subset ( a conftest that validates the full tests tree, such as a HEAVY_FILES self-check, aborts collection in a partial one), the root conftest.py, the pytest config and every top-level path the tests import, read or run, and every root module file they import — list them with \`git ls-tree --name-only ${args.base_sha}\` run ALONE first, read its output, then archive only those that exist with one \`git archive -o\` naming them as literal paths — the tracked-link rule above applies to this list too — (pyproject.toml, pytest.ini, setup.cfg, tox.ini; \`git archive\` fails on a missing path) — overlay the pins, and launch pytest in-process with the same insert, changing directory INSIDE the program — the shell returns to the live checkout before every call, and one plain command per call forbids \`cd …; python\`: \`python -P -B -c 'import os,site,sys; os.chdir("SCRATCH/arch"); os.environ["PYTHONUSERBASE"]=site.getuserbase(); os.environ["HOME"]="SCRATCH/home"; os.environ["TMPDIR"]="SCRATCH/tmp"; os.environ["FABRIK_ROOT"]=os.getcwd(); i=next((n for n,p in enumerate(sys.path) if p.endswith(("site-packages","dist-packages"))),len(sys.path)); sys.path[i:i]=[os.path.abspath("src"),os.path.abspath(".")]; import pytest; raise SystemExit(pytest.main(sys.argv[1:]))' <pytest args>\` — the FABRIK_ROOT line keeps fabrik.config's write root (and every reader of it) on the archive: an archive is not a linked worktree, so without it fabrik.config falls back to the live /opt/fabrik and a test reads the moving tree with no error; a module that hard-codes /opt/fabrik (scripts/fabrik_synced_manifest.py, scripts/enforcement/check_synced_unmodified.py) still reads the live hub, so a result resting on one is UNPINNED. Before trusting a result, \`timeout 120 /usr/bin/grep\` the archived tests and conftests for the live repo's absolute path: a test that inserts or runs it (sys.path, a subprocess argv, cwd=) executes live code, so report that test unverifiable against the pins, never passed. Grep the selected tests the same way for \`subprocess\`, \`runpy\` and \`scripts/\`, and read each script a test runs before the run: a test that runs one the never-execute rule forbids is not run, and its claim is unverified. Grep them, and the helpers they import, for \`scratch_pg\` and \`_real_pg\` too, and read each hit on \`docker run\` or \`docker compose\` the test itself executes: such a test starts a database container (and may pull an image), so it is not run either, and its claim is unverified — a test that only reads or emits compose text is not one. Never copy a .env into SCRATCH (git archive leaves it out, and that omission is the isolation); import the package first, and export a dummy only for a var whose absence fails that import, never for a TEST_* or other skip-gate var, with an unroutable value on the reserved never-resolving \`.invalid\` domain (\`postgresql+asyncpg://dummy:dummy@dummy.invalid:1/dummy\`, \`redis://dummy.invalid:1/0\`) — a natural dummy names the real local host. Print \`__file__\` from INSIDE the run (in the test or a conftest) — a separate \`python -c\` builds a different sys.path, and that print does not cover a child process the test starts. A test that reads git HISTORY (log, blame, rev-parse of an older commit) has none in an archive: run it in a shared clone — \`git -C SCRATCH clone --shared --no-checkout <the live checkout, as git rev-parse --show-toplevel prints it> clone\`, then \`git -C SCRATCH/clone config remote.origin.pushurl /nonexistent.invalid\` (its origin IS the live repo: a push would land there; the URL is a tripwire, not a guard: an explicit path or URL bypasses it, so NEVER run \`git push\` in the clone, to origin or to any path or URL), \`git -C SCRATCH/clone checkout ${args.base_sha}\`, the run's pins laid over it (the overlay program above with SCRATCH/clone for SCRATCH/arch), and, when the test reads HEAD, a diff or the tree's status, \`git -C SCRATCH/clone add -A\` then \`git -C SCRATCH/clone -c user.name=seat -c user.email=seat@seat.invalid commit -q --allow-empty -m pins\` (empty when no pin differs from the base); the clone reads the shared objects and writes nothing to the shared \`.git\`, and a branch, worktree or stash a test creates lands in the clone's own \`.git\`, so such a test runs there — only a test that reads the LIVE checkout's own branches, worktrees or stash is reported unverifiable against the pins.`
// W-4ad7ff2d (kaizen row 1792192144): a seat asked to run the completion gate had no layout. The gate grades its
// WORKING DIRECTORY (final_gate.py: PROJECT_ROOT = Path.cwd()) and scopes itself two ways — most enforcement checks
// read ONLY the index, the rest the range against @{upstream} or origin/master — so the layout is the shared clone
// on a `pins` branch whose upstream is the base, the pins STAGED and never committed (a commit empties the index;
// a clone's origin/master is the live master, so without the upstream a pre-merge review grades the whole branch).
const GATE_PINS = ` For a COMPLETION-GATE run (\`scripts/final_gate.py\`) neither recipe above is enough: the gate grades its WORKING DIRECTORY and scopes itself through git — most of its enforcement checks read only the INDEX, the rest the range against @{upstream} or origin/master — so run it never from the live repo and never from an archive, only in the history recipe's shared clone set up this way, before any commit: after its clone and pushurl steps, \`git -C SCRATCH/clone checkout -q ${args.base_sha}\`, \`git -C SCRATCH/clone branch -q base ${args.base_sha}\`, \`git -C SCRATCH/clone checkout -q -b pins\`, \`git -C SCRATCH/clone branch -q --set-upstream-to=base pins\` (the clone's origin/master is the LIVE master: without that upstream, a review whose base is ahead of master grades every commit of the branch); in the hub also run \`ln -sfn /opt/fabrik-lib SCRATCH/fabrik-lib\` once (a doc link to ../fabrik-lib resolves there). Run the gate TWICE in that clone — first with nothing overlaid (the bare base: a clone lacks every gitignored file the live disk holds, so the base itself can read red), then after overlaying the pins and \`git -C SCRATCH/clone add -A\` — and NEVER commit the pins before or between those runs (a commit empties the index, and every index-reading check then passes a pinned defect in silence; the history recipe's commit comes after, if a test needs it). Always \`--check\` (a bare run auto-fixes and re-stages), launched with the repo's own .venv python from the live checkout, the directory changed INSIDE the program: \`python -P -B -c 'import os,runpy,site,sys; os.chdir("SCRATCH/clone"); os.environ["PYTHONUSERBASE"]=site.getuserbase(); os.environ["HOME"]="SCRATCH/home"; os.environ["TMPDIR"]="SCRATCH/tmp"; os.environ["KAIZEN_EVENTS_DIR"]="SCRATCH/events"; os.environ["FABRIK_ROOT"]=os.getcwd(); os.environ["PATH"]=os.path.dirname(sys.executable)+os.pathsep+os.environ["PATH"]; sys.argv=["scripts/final_gate.py","--check","--json"]; runpy.run_path("scripts/final_gate.py", run_name="__main__")' > SCRATCH/gate-base.json\` (and \`> SCRATCH/gate-pins.json\` for the second run: the verdict is some 25 KB and an unredirected one is truncated mid-output, so read it from the file; mkdir home, tmp and events first: they keep the gate's telemetry and semgrep settings off the real home; the venv bin first on PATH makes its ruff the repo's own, which a clone has no .venv to supply) — and print the cwd beside each result. Read \`status\` (success, failure, or setup-error: a tool the gate needs is missing, so nothing was graded), then \`failures\`, \`warnings\`, \`skipped_checks\` and \`advisory\`, never status alone: a check whose script is missing is a green row reported only in \`warnings\`, and a skip says why in its row — a diff-sensed skip (nothing in its scope changed) is scope, a NOT INSTALLED one is a missing tool and not a pass. A red row is the pin's only when it is new or changed against the base run AND names a path in the pins' MANIFEST.md5; a row the base run shares is base debt, a row that asks for a file outside the pins (a CHANGELOG entry, a doc the change would update) is a pin-set row — the commit may carry that file, the pin set does not — and the rest are clone rows. Copy every gitignored path a gate row reads from the live disk into the clone (in a project repo \`scripts/enforcement/\`, \`.windsurf/rules/\`, \`.fabrik/\`) and name each row resting on one UNPINNED; a check that reads the hub by absolute path (\`check_synced_unmodified.py\`, the synced manifest) and the gate's own runner (\`/opt/fabrik/scripts/capped_run.sh\`) are UNPINNED too. In the hub a clone is never the hub (the gate's hub test reads the git common dir), so it runs under project rules: a row that exists only in project mode is a clone row, never a finding. The hub's pytest row is NOT RUN by design. In a project the gate's pytest leg runs when \`.fabrik/run-pytest\` arms it, or \`tests/\` plus a CI file naming pytest does (the gate runs it then on an empty diff — the bare-base run — or one touching src/, tests/ or scripts/, so treat that pair as armed whatever the diff) — without the repo's .env and WITHOUT any of the pytest recipe's guards (the live-path, container and script checks), so an armed leg is never run: after copying the gitignored inputs, look for that arming in the clone, and when it is there launch both runs with \`--lean\` (the tier with no pytest leg) and name every row only the full tier carries NOT RUN — tests go through the pytest recipe above, never the gate. A gate leg the time box kills (an armed pytest leg runs up to 900 s; \`--lean\` is the quicker tier) is NOT RUN, never a result.`

function finderPrompt(slice, model, retry = false) {
  const ledger = slice.ledger && slice.ledger.length
  const head = ledger
    ? `PASS ${args.pass} — you are the ${model} seat that owned slice ${slice.name} in round 1. Every ledger claim states a DEFECT as it was raised. Re-verify each by EXECUTION and report it in ledger_status (command + output each): DEFECT_PRESENT means the defect is still there, DEFECT_ABSENT means the claimed defect is absent (the fix holds, or an earlier refutation still holds — re-run and never cited), NEW is a defect the fix itself introduced. EVERY claim in YOUR ledger is re-executed, an earlier refutation included (term-coverage.md: a quiet round 1's claims are all open to its closing pass), and a ledger_status row with no command and output re-verifies nothing; a claim whose check the never-execute rule forbids gets NO ledger_status row — write "unverified: never-execute rule" and the cited lines in notes, and the claim stays open for the lead; a claim refuted in an earlier pass and NOT in your ledger is closed (D-206). Candidates are ONLY the DEFECT_PRESENT and NEW rows (a DEFECT_ABSENT row is never a candidate) — never a REPORT ONLY claim; a NEW candidate is a defect of a line INSIDE the previous round's fix hunks, or a live contradiction those hunks created with a sentence of the same section, or the break those hunks created in a reader of what they changed (such as a returned value or type, a key or path form, a field, a signature, a raised exception, an exit code, a printed line, or a heading or term another section cites), shown by that reader passing on the previous round's pin and failing on this one; a defect one hop out that the hunks did not create (a caller, a callee, a neighbouring section, a pre-existing claim) is never raised — name it in notes with a destination (D-230). Open EVERY slice file and list it in files_read on this pass too: a fix hunk can sit in a file no claim names, and a slice file no seat lists keeps the slice open.`
    : `PASS 1 — you are the ${model} finder for slice ${slice.name}: ${slice.models.length > 1 ? `one of ${slice.models.length} finders over this whole slice (the others: ${slice.models.filter((m) => m !== model).join(', ')}; never coordinate, candidates are unioned and every one is executed by the orchestrator)` : 'the ONLY finder over this slice (every candidate is executed by a refuter and the orchestrator)'}. RECALL first: surface every candidate with a concrete failure scenario and an EXECUTABLE check; never drop a half-believed one.`
  const files = slice.files.map((f) => `  - ${f}`).join('\n')
  const ledgerText = ledger
    ? '\nSLICE LEDGER (report every id below in ledger_status, exactly as written):\n' +
      slice.ledger.map((c) => ledgerLine(c) + (c.recorded ? ' [REPORT ONLY — recorded (D-230): re-verify and report it, never raise it as a candidate]' : '')).join('\n')
    : ''
  return `${BRIEF_IS_TASK}
${head}

SURFACE: ${args.surface}
BASE: ${args.base_sha} · DIGEST: ${args.digest}
PINS: each slice file's pinned copy is at ${args.pins_dir}/<its repo-relative path> — e.g. ${args.pins_dir}/${slice.files[0]}; read the pin, never the live tree (the pin wins over the live path).${slice.agentType === 'fabrik-researcher' ? '' : ` ${PIN_IMPORT}${PYTEST_PINS}${GATE_PINS}`}
${slice.agentType === 'fabrik-researcher' ? 'SHELL: none — you have no shell: read the PINNED copies.' : `SCRATCH: ${args.scratch_dir}/${SEAT_TAG}-${slice.name}-${model}${retry ? '-retry' : ''}/ (create it first with \`mkdir -p SCRATCH\` — its parent exists and nothing creates it for you; every probe on a COPY there; never write, copy, mkdir or cd-and-create anything outside SCRATCH — your working directory is the LIVE repo, and a seat's stray file there reaches the next gate;${SEAT_ISOLATION} wrap every command that can block in \`timeout 120\`, a search as \`timeout 120 /usr/bin/grep\` (timeout cannot run a shell builtin) — nothing times a seat out but you)`}
YOUR SLICE (${slice.files.length} files — read EVERY one; hunt priority: ${slice.priority || 'none named'}):
${files}${slice.scope ? `\nSECTIONS YOU OWN (the rest of each file belongs to another slice — read it only to resolve a reference): ${slice.scope}` : ''}${ledgerText}

${args.brief}

RETURN the structured output: files_read MUST list every file you opened (repo-relative) — a slice file you did not open is a coverage gap the script logs and the slice is then unverified; a file you grepped, ran or tested counts as opened; a files_read that names none of your slice files fails your seat and keeps the slice open; candidates each with id "${slice.name}-${model[0].toUpperCase()}<n>", file, line, failure_class, claim, scenario, check, confidence; notes: coverage statement, then MACHINERY last. HARD TIME BOX ${box} minutes. FINISH by calling the StructuredOutput tool — a report in prose is a failed seat.`
}

function refutePrompt(slice, cands, suffix = '') {
  const list = cands
    .map((c) => `CANDIDATE ${c.id} · ${c.file}:${c.line} · class ${c.failure_class}\n  CLAIM: ${c.claim}\n  SCENARIO: ${c.scenario}\n  CHECK TO EXECUTE: ${c.check}`)
    .join('\n\n')
  const refuteBox = Math.max(box, 3 * cands.length)
  return `${BRIEF_IS_TASK} REFUTER SEAT — fresh context: you did not find these, and you owe the finders nothing. Execute EVERY candidate from slice ${slice.name} below and return one verdict per candidate id with the command you ran and its output (a check the never-execute rule forbids is the one exception, below). Never fix, never edit. ${slice.agentType === 'fabrik-researcher' ? 'You have no shell: read the PINNED copies' : `git READ-ONLY, every probe on a COPY under ${args.scratch_dir}/${SEAT_TAG}-refute-${slice.name}${suffix}/ (SCRATCH; create it first with \`mkdir -p SCRATCH\` — its parent exists and nothing creates it for you) — never write, copy, mkdir or cd-and-create anything outside SCRATCH, your working directory is the LIVE repo;${SEAT_ISOLATION} wrap every command that can block in \`timeout 120\`, a search as \`timeout 120 /usr/bin/grep\` (timeout cannot run a shell builtin), nothing times a seat out but you; read the PINNED copies`} under ${args.pins_dir}/<repo-relative path> (base ${args.base_sha}, digest ${args.digest}).${slice.agentType === 'fabrik-researcher' ? '' : ` ${PIN_IMPORT}${PYTEST_PINS}${GATE_PINS}`}

${list}

${slice.agentType === 'fabrik-researcher' ? 'A check is the LIVE fetch of the cited source (the URL, the date read, the verbatim quote); the command field is the URL you fetched. ' : ''}For each id, exactly as written: run its check (or the smallest command that proves or refutes the claim on the pinned copy). verdict: confirmed = the check reproduces the failure; refuted = ONLY with counter-evidence — the command and its output that show it cannot happen, and the mechanism; recorded = outside the slice or more than one hop away, with a destination — except the break a fix's hunks created in a reader of what they changed, shown by that reader passing on the previous round's pin and failing on this one, which is confirmed or refuted like any other candidate (D-230, W-7b5a6a17); unverified = you could not execute it (say why in mechanism). Uncertainty is unverified, never refuted. output ≤ 1500 characters, verbatim. A re-read is not execution — run it, unless the never-execute rule forbids the check: then the verdict is unverified, the command is your read of the cited lines and the output is those lines. Work in the order given; when the box runs out, return unverified for the rest. HARD TIME BOX ${refuteBox} minutes.

${args.brief} FINISH by calling the StructuredOutput tool — a report in prose is a failed seat.`
}

// Two candidates are ONE defect only when two DIFFERENT seats cite the same file and class within five lines;
// the same seat's neighbours are two defects (a dedupe key that merged them lost the second one — review of
// 2026-09-22, A-S1), and a fixed bucket split one defect cited at lines 5 and 7 (A-S5).
function sameDefect(a, b) {
  return (
    a.file === b.file &&
    String(a.failure_class || '').toLowerCase() === String(b.failure_class || '').toLowerCase() &&
    Math.abs((a.line || 0) - (b.line || 0)) <= 5
  )
}

// Does one `files_read` entry name slice file `f`? Seats report a file they opened as the repo path, as its pin
// (`<pins_dir>/f`), as their SCRATCH/arch copy (`<scratch_dir>/<seat>/arch/f`), cited (`f:120`) or annotated
// (`f (pinned copy at …)`) — a verbatim compare read all but the first as UNREAD (W-b491da86, W-cd7979d3,
// web-ecommerce-factory 01M46BNT62). Only those two roots are stripped and `f` must then LEAD the entry: no suffix
// match, so a sibling pin of the same name (`<pins_dir>/other/f`) or the live checkout the brief forbids stays a gap
// (design critique, Opus + Fable: a suffix rule credited 23 of 4796 tracked paths with a different file).
const escRe = (s) => String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
// a root is built only from a dir that is a non-empty string once its trailing slashes go: an unset dir must not
// become the literal `^undefined/`, an empty one `^/` (which would strip every absolute path), and `<dir>/` must
// not demand a double slash
const rootDir = (d) => (typeof d === 'string' ? d.replace(/\/+$/, '') : '')
// The ROOT rule alone, shared by `readsFile` and a candidate's `file` (W-177082fc): a seat citing a defect by its pin
// or arch copy and a seat citing the repo path name one file. Never `base_pin_dir` (the base's bytes, a different
// version) and never the lead-and-delimiter tolerance below — 78 real route paths carry `(`/`[` (measured).
function slicePath(entry) {
  let n = String(entry ?? '').trim().replace(/`/g, '').replace(/^file:\/\//, '').replace(/^\.\//, '')
  const pins = rootDir(args.pins_dir)
  const scratch = rootDir(args.scratch_dir)
  const roots = [
    ...(pins ? [new RegExp(`^${escRe(pins)}/`)] : []),
    ...(scratch ? [new RegExp(`^${escRe(scratch)}/[^/]+/arch/`)] : []),
  ]
  for (const root of roots) if (root.test(n)) { n = n.replace(root, ''); break }
  return n
}
function readsFile(entry, f) {
  const n = slicePath(entry)
  return n === f || (n.startsWith(f) && /^[\s:#(\[,—]/.test(n.slice(f.length)))
}

function unionSlice(r) {
  const candidates = []
  let overlap = 0
  for (const seat of r.seats) {
    for (let c of seat.candidates || []) {
      // one spelling BEFORE the twin lookup; a value that strips to nothing (the pins dir itself) keeps its own
      if (typeof c?.file === 'string') c = { ...c, file: slicePath(c.file) || c.file }
      // a candidate absorbs one twin per OTHER seat, so a defect three finders raise is one candidate (chunk 6 review)
      const twin = candidates.find((k) => k.seat !== seat.model && !(k.also_seats || []).includes(seat.model) && sameDefect(k, c))
      if (twin) {
        overlap += 1
        if (!twin.also) Object.assign(twin, { also: c.id, also_seat: seat.model })
        twin.also_seats = [...(twin.also_seats || []), seat.model]
      } else {
        // ids key the refuter's verdicts, so they must be unique in the slice: a reused or missing id gets a
        // suffix here, before the refuter sees it (review of 2026-09-23, A-S2)
        let id = String(c.id || '').trim() || `${r.slice.name}-${seat.model[0].toUpperCase()}?`
        for (let n = 2; candidates.some((k) => k.id === id); n += 1) id = `${String(c.id || '').trim() || r.slice.name}#${n}`
        candidates.push({ ...c, id, seat: seat.model })
      }
    }
  }
  const read = r.seats.flatMap((s) => s.files_read || [])
  const gaps = r.slice.files.filter((f) => !read.some((e) => readsFile(e, f)))
  const counts = r.seats.map((s) => (s.candidates || []).length)
  const distinct = candidates.length
  // Chapman's capture-recapture estimator over the two finders' candidate sets — ADVICE, never a gate; any other
  // seat count has no two-sample estimate, so none (null, never 0)
  const estimate = counts.length === 2 ? Math.max(0, Math.round(((counts[0] + 1) * (counts[1] + 1)) / (overlap + 1) - 1) - distinct) : null
  const failed = r.seats.filter((s) => s.failed).length
  log(`find:${r.slice.name} gaps ${gaps.length} of ${r.slice.files.length} files unread · ${r.seats.map((s, i) => `${s.model} ${counts[i]}`).join(' · ')} · shared ${overlap} · distinct ${distinct} · est. unseen ${estimate === null ? 'n/a (not two finders)' : `${estimate} (Chapman — advice only, unreliable below 3 shared)`}${failed ? ` · ${failed} SEAT FAILED` : ''}`)
  if (gaps.length) log(`find:${r.slice.name} coverage gap — unread: ${gaps.join(', ')} (slice UNVERIFIED until read)`)
  return { ...r, candidates, gaps, raised: counts.reduce((a, b) => a + b, 0), distinct, overlap, estimate_unseen: estimate }
}

// The id is the candidate's, never the seat's echo (A-S3). A candidate the refuter never answered — a null seat, a
// missing id, a timed-out box — is `unverified`; a `refuted` with no command or no output is uncertainty dressed as a
// disproof and is rewritten to `unverified` (finding 36: refutation needs counter-evidence).
const PLACEHOLDER = /^(?:n\/?a|none|null|nil|-+|—|\.+|tbd|skipped|not run)$/i
function evidence(x) {
  const s = String(x || '').trim()
  return s !== '' && !PLACEHOLDER.test(s)
}
// One matcher for a refuter's rows, shared by the verdicts and the retry test: an exact id wins; a case- or
// space-slipped id counts only when its fold names exactly ONE candidate id (A-S7's one-to-one rule), so a slip is
// matched, never re-dispatched (fleet 01M4DP81PE design critiques). A non-array `verdicts` matches nothing.
const foldId = (id) => String(id || '').trim().toLowerCase()
function matchRows(out, id, ids) {
  const all = out && Array.isArray(out.verdicts) ? out.verdicts.filter((x) => x && typeof x === 'object') : []
  const exact = all.filter((x) => x.id === id)
  if (exact.length || ids.filter((k) => foldId(k) === foldId(id)).length !== 1) return exact
  return all.filter((x) => foldId(x.id) === foldId(id))
}
function verdictFor(c, out, ids) {
  const rows = matchRows(out, c.id, ids)
  if (!rows.length) {
    // a row that folds onto this id while another candidate shares the fold was returned, but cannot be assigned
    const folded = out && Array.isArray(out.verdicts) && out.verdicts.some((x) => x && x.id !== c.id && foldId(x.id) === foldId(c.id))
    const mechanism = !out
      ? 'refuter seat failed (null result)'
      : folded
        ? 'a verdict matched this id only by case or spacing, and another candidate shares that spelling — ambiguous, not assigned'
        : 'the refuter returned no verdict for this id'
    return { id: c.id, verdict: 'unverified', command: '', output: '', mechanism }
  }
  if (new Set(rows.map((x) => x.verdict)).size > 1) {
    return { id: c.id, verdict: 'unverified', command: '', output: '', mechanism: `conflicting verdicts for one id: ${rows.map((x) => x.verdict).join(', ')}` }
  }
  // among same-verdict rows the one carrying evidence speaks for the id — never the row the seat happened to list
  // first (review pass 1, A-S1)
  const v = rows.find((x) => evidence(x.command) && String(x.output || '').trim()) || rows[0]
  // the COMMAND is the counter-evidence locator: a placeholder there means nothing ran; the output only has to
  // exist — a real command may genuinely print `None` or `-` (review pass 2, A-S8)
  if (v.verdict === 'refuted' && !(evidence(v.command) && String(v.output || '').trim())) {
    return { ...v, id: c.id, verdict: 'unverified', mechanism: `refuted without counter-evidence (no command or output, or a placeholder): ${v.mechanism || ''}` }
  }
  return { ...v, id: c.id }
}

// A slice may close only when nothing in it is still open: every file read, every seat returned, no candidate
// confirmed or unverified, and on a later pass every ledger claim re-verified by a seat. `open` names each reason.
function closeCheck(r) {
  const open = []
  if (r.gaps.length) open.push(`unread: ${r.gaps.join(', ')}`)
  for (const s of r.seats) if (s.failed) open.push(`seat failed: ${s.model}`)
  if (r.refuter.failed) open.push('refuter failed')
  for (const v of r.verdicts) if (v.verdict === 'confirmed' || v.verdict === 'unverified') open.push(`${v.verdict}: ${v.id}`)
  // an exact id wins; a case- or space-slipped id counts only when it folds onto exactly ONE claim, so a slip is
  // forgiven but one report never closes two claims (review pass 2, A-S7)
  const fold = foldId
  const ids = r.slice.ledger.map((c) => c.id)
  // a seat that echoes `S-L1 · S-O27` re-verified S-L1: a report whose id-shaped tokens (cut at every character an
  // id cannot hold, so `S-L10` never reads as `S-L1`) name EXACTLY ONE of this slice's ledger ids counts for that id;
  // `S-L2 · S-L1` names two, so it is ambiguous and closes neither — the fail-closed default (W-7afacefb, 01M3RX9J)
  // `#` is an id character: the union suffix `S-L1#2` names one claim, never `S-L1` too (mail 01M4PHYNXJ)
  const only = (x) => {
    const named = [...new Set(x.split(/[^A-Za-z0-9._#-]+/).filter((t) => ids.includes(t)))]
    return named.length === 1 && named[0] !== x ? named : []
  }
  // 01M4PPW8D8 (both design critiques executed it): an id echoed with no command re-verified nothing. The output
  // may be empty — a grep that finds no match prints nothing (review round 1, A-H2) — but it must be stated
  const said = r.seats
    .filter((s) => !s.failed)
    .flatMap((s) =>
      (s.ledger_status || [])
        .filter((x) => x && evidence(x.command) && typeof x.output === 'string')
        .map((x) => String(x.id || '').trim())
    )
    .flatMap((x) => [x, ...only(x)])
  const hit = (id) => said.includes(id) || (ids.filter((k) => fold(k) === fold(id)).length === 1 && said.some((x) => fold(x) === fold(id)))
  for (const c of r.slice.ledger) if (!hit(c.id)) open.push(`ledger claim ${c.id} not re-verified by any seat`)
  if (open.length) log(`slice ${r.slice.name} NOT closable: ${open.join(' · ')}`)
  return { ...r, closable: open.length === 0, open }
}

// A refuter that leaves candidates unanswered (a null result, foreign ids, a box that ran out before it reported)
// gets ONE retry over just those, under its own label and scratch dir; what the retry still leaves unanswered
// marks the slice's refuter failed — `open`, `failed_refuters` — never a quiet `unverified` (fleet 01M4DP81PE:
// two refuters died over 11 candidates and nothing said so). A deliberate `unverified` row IS an answer. The
// retry starts after its first refuter ends, so it never exceeds the dispatch stamp's one refuter per slice.
function refuteCall(slice, cands, suffix) {
  return agent(refutePrompt(slice, cands, suffix), {
    label: `refute:${slice.name}${suffix ? ':retry' : ''}`,
    phase: 'Verify',
    schema: REFUTATION,
    model: 'sonnet',
    effort: 'high',
    agentType: slice.agentType,
  }).catch(() => null)
}
async function refuteSlice(r0) {
  const quiet = { retried: false, failed: false, unanswered: 0, reason: '' }
  // a candidate on a `recorded: true` ledger claim is reported, never refuted or counted (D-230); it moves to the
  // slice's `recorded` list, so the lead still sees it and `candidates` stays index-aligned with `verdicts`
  // (the per-seat `confirmed` credit zips the two — review round 1, A-S1)
  const recorded = new Set(r0.slice.ledger.filter((c) => c.recorded === true).map((c) => foldId(c.id)))
  const marked = r0.candidates.map((c) => (recorded.has(foldId(c.id)) ? { ...c, recorded: true } : c))
  const r = { ...r0, candidates: marked.filter((c) => !c.recorded) }
  const keep = (out) => ({ ...out, recorded: marked.filter((c) => c.recorded) })
  if (!r.candidates.length) return keep({ ...r, verdicts: [], refuter: quiet })
  const ids = r.candidates.map((c) => c.id)
  const first = await refuteCall(r.slice, r.candidates, '')
  const missing = r.candidates.filter((c) => !matchRows(first, c.id, ids).length)
  if (!missing.length) return keep({ ...r, verdicts: r.candidates.map((c) => verdictFor(c, first, ids)), refuter: quiet })
  const reason = first ? `no verdict for ${missing.length} of ${ids.length} ids` : 'null result'
  const retry = await refuteCall(r.slice, missing, '-retry')
  const still = missing.filter((c) => !matchRows(retry, c.id, ids).length)
  log(`refute:${r.slice.name} ${reason} — retried ${missing.length}: ${still.length ? `${still.length} STILL UNANSWERED (refuter failed)` : 'recovered'}`)
  return keep({
    ...r,
    verdicts: r.candidates.map((c) => verdictFor(c, missing.includes(c) ? retry : first, ids)),
    refuter: { retried: true, failed: still.length > 0, unanswered: still.length, reason },
  })
}

// W-b36e2a4a: a finder that returns null OR throws (a transport or auth error, a stall) is re-seated ONCE on the
// same model and agent, after the first ends — the refuter retry's shape, so it never exceeds the dispatch stamp —
// under its own label and scratch dir, so a dead seat's half-built arch/ never poisons it. A second null is the
// failed seat it always was. One helper holds the call, so every finder names its model and effort.
function findCall(s, m, retry) {
  return agent(finderPrompt(s, m, retry), {
    label: `find:${s.name}:${m}${retry ? ':retry' : ''}`,
    phase: 'Find',
    schema: FINDINGS,
    model: m,
    effort: 'medium',
    agentType: s.agentType,
  }).catch(() => null)
}
async function findWithRetry(s, m) {
  const first = await findCall(s, m, false)
  if (first) return first
  const again = await findCall(s, m, true)
  log(`find:${s.name}:${m} null — retried: ${again ? 'recovered' : 'STILL NULL'}`)
  return again
}
// 01M4Q4D8VP: a seat that returned no coverage statement, no candidate and no ledger row brought nothing back —
// failed, not a clean 0. No coverage statement: the notes, every MACHINERY line removed, are empty, a PLACEHOLDER,
// or the word placeholder/tbd/todo (2 of 6707 real seats fired, both genuine, 2026-10-13). COBRA (D-253): the
// cheapest dodge is one fluff sentence; the refuter's execution and the lead's Phase-2 re-run of every confirmed
// check are what catch a seat that read nothing it lists.
function broughtNothing(r) {
  const has = (x) => Array.isArray(x) && x.length > 0
  if (has(r.candidates) || has(r.ledger_status)) return false
  // MACHINERY is the notes' LAST part (the brief's order), so it ends at the end: everything from its first line
  // on is not coverage (review round 1, A-S2 — its bullet lines read as a coverage statement)
  const lines = String(r.notes || '').split('\n')
  const cut = lines.findIndex((line) => /^\s*MACHINERY\s*:/i.test(line))
  const text = (cut === -1 ? lines : lines.slice(0, cut)).join(' ').trim()
  return !evidence(text) || /^(?:placeholder|tbd|todo)\.?$/i.test(text)
}
const results = await pipeline(
  args.slices,
  (s) =>
    parallel(s.models.map((m) => () => findWithRetry(s, m))).then((rs) => ({
      slice: s,
      // a seat whose files_read credits NO slice file reviewed nothing: it is DROPPED, not quiet, on every pass —
      // its partner's reads would otherwise hide it from the gap check (01M4C00TSS: a seat answered a relayed
      // operator turn instead). Every array is normalised, so a missing or mistyped field never throws below.
      seats: rs.map((r, i) => {
        const arr = (x) => (Array.isArray(x) ? x : [])
        const read = arr(r && r.files_read)
        const credited = s.files.some((f) => read.some((e) => readsFile(e, f)))
        const empty = !!r && broughtNothing(r)
        return {
          model: s.models[i],
          failed: !r || !credited || empty,
          files_read: read,
          candidates: arr(r && r.candidates),
          ledger_status: arr(r && r.ledger_status),
          notes: !r
            ? 'SEAT FAILED (null result, after one retry)'
            : !credited
              ? `SEAT FAILED (read no slice file): ${r.notes || ''}`
              : empty
                ? `SEAT FAILED (no coverage statement, no candidate, no ledger row): ${r.notes || ''}`
                : r.notes,
        }
      }),
    })),
  (r) => unionSlice(r),
  (r) => refuteSlice(r),
  (r) => closeCheck(r)
)

const slices = results.filter(Boolean)
const droppedSlices = args.slices.length - slices.length
if (droppedSlices) log(`DROPPED ${droppedSlices} of ${args.slices.length} slices (a stage threw) — those slices are UNVERIFIED`)
const droppedSeats = slices.reduce((n, r) => n + r.seats.filter((s) => s.failed).length, 0)
const unverified = slices.reduce((n, r) => n + r.verdicts.filter((v) => v.verdict === 'unverified').length, 0)
const failedRefuters = slices.filter((r) => r.refuter.failed).length
const retriedRefuters = slices.filter((r) => r.refuter.retried).length
const closable = droppedSlices === 0 && slices.every((r) => r.closable)
log(`pass ${args.pass}: ${closable ? 'CLOSABLE' : 'NOT closable'} · ${slices.length} slices · ${slices.reduce((n, r) => n + r.distinct, 0)} distinct candidates · confirmed ${slices.reduce((n, r) => n + r.verdicts.filter((v) => v.verdict === 'confirmed').length, 0)} · dropped seats ${droppedSeats} · refuters retried ${retriedRefuters}, failed ${failedRefuters} · unverified ${unverified}`)

return {
  pass: args.pass,
  closable,
  pinned,
  dropped_slices: droppedSlices,
  dropped_seats: droppedSeats,
  failed_refuters: failedRefuters,
  slices: slices.map((r) => ({
    name: r.slice.name,
    files: r.slice.files,
    // a candidate both finders raised credits BOTH seats (B-S2) — `confirmed/raised` per seat is the Pass-row's `seats:` cell
    seats: r.seats.map((s) => ({
      model: s.model,
      files_read: s.files_read.length,
      raised: s.candidates.length,
      confirmed: r.verdicts.filter((v, i) => v.verdict === 'confirmed' && (r.candidates[i].seat === s.model || (r.candidates[i].also_seats || []).includes(s.model))).length,
      failed: s.failed,
      ledger_status: s.ledger_status,
      notes: s.notes,
    })),
    gaps: r.gaps,
    raised: r.raised,
    distinct: r.distinct,
    overlap: r.overlap,
    estimate_unseen: r.estimate_unseen,
    candidates: r.candidates,
    recorded: r.recorded || [],
    verdicts: r.verdicts,
    refuter: r.refuter,
    closable: r.closable,
    open: r.open,
  })),
}
