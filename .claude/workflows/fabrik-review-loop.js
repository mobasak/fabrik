// fabrik-review-loop — the D-335 review loop as a Claude Code workflow script (chunk 5; D-346, D-347, D-348).
//
// WHAT IT MOVES OUT OF THE LEAD'S TRANSCRIPT: the seat dispatch, the seats' reports, and the execution of
// every candidate's check. The lead launches ONE call per pass, gets ONE ledger back, executes only the
// CONFIRMED candidates' commands itself (Phase 2 of /fabrik-review), fixes, and launches the next pass as a
// NEW invocation carrying this pass's ledger in `args` — never `resumeFromRunId` (a resumed run re-runs every
// agent after the first fan-out: anthropics/claude-code #63102 #67488 #74599 #95076).
//
// THE SHAPE IS D-335 / D-344, UNCHANGED: the surface cut into disjoint slices by file; TWO cheap finders per
// slice (one Sonnet, one Haiku `fabrik-reviewer`), each over the whole slice, candidates UNIONED never voted;
// no Opus finder; a Sonnet verify seat EXECUTES each candidate's check and returns the command and its output;
// the lead re-runs the confirmed ones. Every pass after the first is the same slice ownership re-verifying the
// slice's claim ledger; refuted and recorded candidates never re-open (D-206, D-230, D-339).
//
// COBRA NOTES (D-253) — the cheapest way to satisfy each measure this script produces WITHOUT the outcome:
//   * lead turns ≤ 15 → push everything into seats: countered by the minutes and tokens rows read WITH turns.
//   * "every file read" → a finder lists files it never opened: `files_read` is the finder's own claim, so the
//     verify stage and the lead's Phase-2 execution are what catch a phantom read; a gap is LOGGED here and the
//     slice is unverified — the script never silently narrows a slice.
//   * the capture-recapture estimate → two finders that share notes or a model inflate the overlap and read
//     "nothing left": the finders are two models in two contexts, the number is printed as ADVICE and nothing
//     keys on it.
//   * "verified" → the verify seat returns a plausible command it never ran: the lead re-executes every
//     CONFIRMED command before a fix (Phase 2), so a fabricated confirmation costs one lead command, and a
//     fabricated refutation is caught by the same slice's next pass or the escaped-defect row (§ 6).
//
// ARGS (all strings unless noted; the command source builds them — see docs/reference/review-loop-workflow.md):
//   pass: 1|2|3 · surface · base_sha · digest · pins_dir · scratch_dir · brief (the dispatcher's shared text:
//   hunt classes, lessons, house rules) · slices: [{ name, files: [..], priority, ledger?: [{ id, file, line,
//   claim }] }] (ledger present on pass ≥ 2) · box_minutes (default 15)
// RETURNS one ledger: { pass, slices: [{ name, files, seats: [{ model, files_read, raised, failed }],
//   gaps, raised, distinct, overlap, estimate_unseen, candidates: [..], verdicts: [..] }], dropped_seats }

export const meta = {
  name: 'fabrik-review-loop',
  description: 'D-335 review loop: two cheap finders per slice, one verify seat per candidate, one ledger back',
  phases: [
    { title: 'Find', detail: 'one Sonnet and one Haiku fabrik-reviewer per slice, candidates unioned' },
    { title: 'Verify', detail: 'one Sonnet fabrik-reviewer executes each candidate and returns command + output' },
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
      description: 'pass ≥ 2 only: one row per ledger claim',
      items: {
        type: 'object',
        required: ['id', 'status', 'command', 'output'],
        properties: {
          id: { type: 'string' },
          status: { enum: ['STILL_TRUE', 'NOW_FALSE', 'NEW'] },
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
    verdict: { enum: ['confirmed', 'refuted', 'recorded'] },
    command: { type: 'string', description: 'the exact command you ran on the pinned copy' },
    output: { type: 'string', description: 'its output, at most 1500 characters' },
    mechanism: { type: 'string', description: 'one sentence: WHY it fails or does not' },
    destination: { type: 'string', description: 'recorded only: backlog row, mail, sibling ticket' },
  },
}

const MODELS = ['sonnet', 'haiku']
const box = args.box_minutes || 15

function finderPrompt(slice, model) {
  const ledger = slice.ledger && slice.ledger.length
  const head = ledger
    ? `PASS ${args.pass} — you are the ${model} seat that owned slice ${slice.name} in round 1. Re-verify EVERY claim in your slice ledger by EXECUTION and report each as STILL_TRUE, NOW_FALSE or NEW in ledger_status (command + output each). Candidates are ONLY the NOW_FALSE and NEW rows; a candidate outside the ledger is RECORDED with a destination, never counted (D-230); a claim refuted in an earlier pass is closed (D-206).`
    : `PASS 1 — you are the ${model} finder for slice ${slice.name}: one of TWO cheap finders over this whole slice (the other is a ${model === 'sonnet' ? 'haiku' : 'sonnet'} seat; never coordinate, candidates are unioned and every one is executed by the orchestrator). RECALL first: surface every candidate with a concrete failure scenario and an EXECUTABLE check; never drop a half-believed one.`
  const files = slice.files.map((f) => `  - ${f}`).join('\n')
  const ledgerText = ledger
    ? '\nSLICE LEDGER:\n' + slice.ledger.map((c) => `  - ${c.id} · ${c.file}:${c.line} · ${c.claim}`).join('\n')
    : ''
  return `${head}

SURFACE: ${args.surface}
BASE: ${args.base_sha} · DIGEST: ${args.digest}
PINS: ${args.pins_dir} (read the pinned copies, never the live tree — the pin wins over the live path)
SCRATCH: ${args.scratch_dir}/${slice.name}-${model}/ (every probe on a COPY there)
YOUR SLICE (${slice.files.length} files — read EVERY one; hunt priority: ${slice.priority || 'none named'}):
${files}${ledgerText}

${args.brief}

RETURN the structured output: files_read MUST list every file you opened (repo-relative) — a slice file you did not open is a coverage gap the script logs and the slice is then unverified; candidates each with id "${slice.name}-${model[0].toUpperCase()}<n>", file, line, failure_class, claim, scenario, check, confidence; notes: coverage statement, then MACHINERY last. HARD TIME BOX ${box} minutes.`
}

function verifyPrompt(slice, c) {
  return `VERIFY SEAT — execute ONE candidate from slice ${slice.name} and return the verdict with the command you ran and its output. Never fix, never edit, git READ-ONLY, every probe on a COPY under ${args.scratch_dir}/verify-${c.id}/; read the PINNED copy under ${args.pins_dir} (base ${args.base_sha}, digest ${args.digest}).

CANDIDATE ${c.id} · ${c.file}:${c.line} · class ${c.failure_class}
CLAIM: ${c.claim}
SCENARIO: ${c.scenario}
CHECK TO EXECUTE: ${c.check}

Run the check (or the smallest command that proves or refutes the claim on the pinned copy). verdict: confirmed = the check reproduces the failure; refuted = the check proves it cannot happen (say the mechanism); recorded = outside the slice or more than one hop away, with a destination. output ≤ 1500 characters, verbatim. mechanism: one sentence, the WHY. A re-read is not execution — run it. HARD TIME BOX ${box} minutes.

${args.brief}`
}

function keyOf(c) {
  return `${c.file}:${Math.floor((c.line || 0) / 6)}:${String(c.failure_class || '').toLowerCase()}`
}

function unionSlice(r) {
  const seen = new Map()
  let overlap = 0
  for (const seat of r.seats) {
    for (const c of seat.candidates || []) {
      const k = keyOf(c)
      if (seen.has(k)) {
        overlap += 1
        seen.get(k).also = c.id
      } else {
        seen.set(k, { ...c, seat: seat.model })
      }
    }
  }
  const candidates = [...seen.values()]
  const read = new Set(r.seats.flatMap((s) => s.files_read || []))
  const gaps = r.slice.files.filter((f) => !read.has(f))
  const [n1, n2] = r.seats.map((s) => (s.candidates || []).length)
  const distinct = candidates.length
  // Chapman's capture-recapture estimator over the two finders' candidate sets — ADVICE, never a gate.
  const estimate = Math.max(0, Math.round(((n1 + 1) * (n2 + 1)) / (overlap + 1) - 1) - distinct)
  const failed = r.seats.filter((s) => s.failed).length
  log(`find:${r.slice.name} gaps ${gaps.length} of ${r.slice.files.length} files unread · sonnet ${n1} · haiku ${n2} · shared ${overlap} · distinct ${distinct} · est. unseen ${estimate}${failed ? ` · ${failed} SEAT FAILED` : ''}`)
  if (gaps.length) log(`find:${r.slice.name} coverage gap — unread: ${gaps.join(', ')} (slice UNVERIFIED until read)`)
  return { ...r, candidates, gaps, raised: n1 + n2, distinct, overlap, estimate_unseen: estimate }
}

const results = await pipeline(
  args.slices,
  (s) =>
    parallel(
      MODELS.map((m) => () =>
        agent(finderPrompt(s, m), {
          label: `find:${s.name}:${m}`,
          phase: 'Find',
          schema: FINDINGS,
          model: m,
          agentType: 'fabrik-reviewer',
        })
      )
    ).then((rs) => ({
      slice: s,
      seats: rs.map((r, i) => ({
        model: MODELS[i],
        failed: !r,
        files_read: r ? r.files_read : [],
        candidates: r ? r.candidates : [],
        ledger_status: r ? r.ledger_status || [] : [],
        notes: r ? r.notes : 'SEAT FAILED (null result)',
      })),
    })),
  (r) => unionSlice(r),
  (r) =>
    parallel(
      r.candidates.map((c) => () =>
        agent(verifyPrompt(r.slice, c), {
          label: `verify:${r.slice.name}:${c.id}`,
          phase: 'Verify',
          schema: VERDICT,
          model: 'sonnet',
          agentType: 'fabrik-reviewer',
        })
      )
    ).then((vs) => ({
      ...r,
      verdicts: vs.map(
        (v, i) =>
          v || { id: r.candidates[i].id, verdict: 'unverified', command: '', output: '', mechanism: 'verify seat failed (null result)' }
      ),
    }))
)

const slices = results.filter(Boolean)
const droppedSlices = args.slices.length - slices.length
if (droppedSlices) log(`DROPPED ${droppedSlices} of ${args.slices.length} slices (a stage threw) — those slices are UNVERIFIED`)
const droppedSeats = slices.reduce((n, r) => n + r.seats.filter((s) => s.failed).length, 0)
const unverified = slices.reduce((n, r) => n + r.verdicts.filter((v) => v.verdict === 'unverified').length, 0)
log(`pass ${args.pass}: ${slices.length} slices · ${slices.reduce((n, r) => n + r.distinct, 0)} distinct candidates · confirmed ${slices.reduce((n, r) => n + r.verdicts.filter((v) => v.verdict === 'confirmed').length, 0)} · dropped seats ${droppedSeats} · unverified ${unverified}`)

return {
  pass: args.pass,
  dropped_slices: droppedSlices,
  dropped_seats: droppedSeats,
  slices: slices.map((r) => ({
    name: r.slice.name,
    files: r.slice.files,
    seats: r.seats.map((s) => ({ model: s.model, files_read: s.files_read.length, raised: s.candidates.length, failed: s.failed, ledger_status: s.ledger_status, notes: s.notes })),
    gaps: r.gaps,
    raised: r.raised,
    distinct: r.distinct,
    overlap: r.overlap,
    estimate_unseen: r.estimate_unseen,
    candidates: r.candidates,
    verdicts: r.verdicts,
  })),
}
