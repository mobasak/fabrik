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
// and its output (§ 4.9 findings 27, 36, 41 — row 5b: a seat per candidate mostly ran one grep); the lead
// re-runs the confirmed ones. Every seat names its model AND effort — an unnamed one inherits the session's
// (finding 43): finders at `medium` with the recall-first brief kept (finding 38), the refuter at `high`. Every pass after the first is the same slice ownership re-verifying the
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
// ARGS (all strings unless noted; the command source builds them — see docs/reference/review-loop-workflow.md):
//   pass: 1|2|3 · surface · base_sha · digest · pins_dir · scratch_dir · brief (the dispatcher's shared text:
//   hunt classes, lessons, house rules) · slices: [{ name, files: [..], priority, scope?, models?, agent?,
//   ledger?: [ { id, file, line, claim } | "<the claim as one string>" ] }] (ledger present on pass ≥ 2; any other
//   row shape is REFUSED before a seat is dispatched; `models` is one to three distinct of opus|sonnet|haiku,
//   default ['sonnet', 'haiku'] (a third, Opus, is /fabrik-execute-plan's per-round Opus floor on its riskiest slice); `agent` is fabrik-reviewer (default) or fabrik-researcher, and seats BOTH the
//   finders and the refuter; `scope` is the sections of `files` the slice owns) · box_minutes (default 15)
// RETURNS one ledger: { pass, closable, slices: [{ name, files, seats: [{ model, files_read, raised, failed }],
//   gaps, raised, distinct, overlap, estimate_unseen, candidates: [..], verdicts: [..], closable, open: [..] }],
//   dropped_seats }

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
      description: 'pass ≥ 2 only: one row per ledger claim; each claim states a DEFECT — STILL_TRUE it persists, NOW_FALSE it is gone, NEW the fix introduced one',
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
for (const s of args.slices) Object.assign(s, { ledger: normalizeLedger(s) }, normalizeSeats(s))

function ledgerLine(c) {
  return c.file ? `  - ${c.id} · ${c.file}:${c.line} · ${c.claim}` : `  - ${c.id} · ${c.claim}`
}

function finderPrompt(slice, model) {
  const ledger = slice.ledger && slice.ledger.length
  const head = ledger
    ? `PASS ${args.pass} — you are the ${model} seat that owned slice ${slice.name} in round 1. Every ledger claim states a DEFECT as it was raised. Re-verify each by EXECUTION and report it in ledger_status (command + output each): STILL_TRUE means the defect is still there, NOW_FALSE means it is gone (the fix holds), NEW is a defect the fix itself introduced. Candidates are ONLY the STILL_TRUE and NEW rows (a NOW_FALSE row is a fix that holds, never a candidate); a candidate outside the ledger is RECORDED with a destination, never counted (D-230); a claim refuted in an earlier pass is closed (D-206).`
    : `PASS 1 — you are the ${model} finder for slice ${slice.name}: ${slice.models.length > 1 ? `one of ${slice.models.length} finders over this whole slice (the others: ${slice.models.filter((m) => m !== model).join(', ')}; never coordinate, candidates are unioned and every one is executed by the orchestrator)` : 'the ONLY finder over this slice (every candidate is executed by a refuter and the orchestrator)'}. RECALL first: surface every candidate with a concrete failure scenario and an EXECUTABLE check; never drop a half-believed one.`
  const files = slice.files.map((f) => `  - ${f}`).join('\n')
  const ledgerText = ledger
    ? '\nSLICE LEDGER (report every id below in ledger_status, exactly as written):\n' + slice.ledger.map(ledgerLine).join('\n')
    : ''
  return `${head}

SURFACE: ${args.surface}
BASE: ${args.base_sha} · DIGEST: ${args.digest}
PINS: each slice file's pinned copy is at ${args.pins_dir}/<its repo-relative path> — e.g. ${args.pins_dir}/${slice.files[0]}; read the pin, never the live tree (the pin wins over the live path)
SCRATCH: ${args.scratch_dir}/${slice.name}-${model}/ (every probe on a COPY there; never write, copy, mkdir or cd-and-create anything outside SCRATCH — your working directory is the LIVE repo, and a seat's stray file there reaches the next gate; wrap every command that can block in \`timeout 120\` — nothing times a seat out but you)
YOUR SLICE (${slice.files.length} files — read EVERY one; hunt priority: ${slice.priority || 'none named'}):
${files}${slice.scope ? `\nSECTIONS YOU OWN (the rest of each file belongs to another slice — read it only to resolve a reference): ${slice.scope}` : ''}${ledgerText}

${args.brief}

RETURN the structured output: files_read MUST list every file you opened (repo-relative) — a slice file you did not open is a coverage gap the script logs and the slice is then unverified; candidates each with id "${slice.name}-${model[0].toUpperCase()}<n>", file, line, failure_class, claim, scenario, check, confidence; notes: coverage statement, then MACHINERY last. HARD TIME BOX ${box} minutes. FINISH by calling the StructuredOutput tool — a report in prose is a failed seat.`
}

function refutePrompt(slice, cands) {
  const list = cands
    .map((c) => `CANDIDATE ${c.id} · ${c.file}:${c.line} · class ${c.failure_class}\n  CLAIM: ${c.claim}\n  SCENARIO: ${c.scenario}\n  CHECK TO EXECUTE: ${c.check}`)
    .join('\n\n')
  const refuteBox = Math.max(box, 3 * cands.length)
  return `REFUTER SEAT — fresh context: you did not find these, and you owe the finders nothing. Execute EVERY candidate from slice ${slice.name} below and return one verdict per candidate id with the command you ran and its output. Never fix, never edit. ${slice.agentType === 'fabrik-researcher' ? 'You have no shell: read the PINNED copies' : `git READ-ONLY, every probe on a COPY under ${args.scratch_dir}/refute-${slice.name}/ (SCRATCH) — never write, copy, mkdir or cd-and-create anything outside SCRATCH, your working directory is the LIVE repo; wrap every command that can block in \`timeout 120\`, nothing times a seat out but you; read the PINNED copies`} under ${args.pins_dir}/<repo-relative path> (base ${args.base_sha}, digest ${args.digest}).

${list}

${slice.agentType === 'fabrik-researcher' ? 'A check is the LIVE fetch of the cited source (the URL, the date read, the verbatim quote); the command field is the URL you fetched. ' : ''}For each id, exactly as written: run its check (or the smallest command that proves or refutes the claim on the pinned copy). verdict: confirmed = the check reproduces the failure; refuted = ONLY with counter-evidence — the command and its output that show it cannot happen, and the mechanism; recorded = outside the slice or more than one hop away, with a destination; unverified = you could not execute it (say why in mechanism). Uncertainty is unverified, never refuted. output ≤ 1500 characters, verbatim. A re-read is not execution — run it. Work in the order given; when the box runs out, return unverified for the rest. HARD TIME BOX ${refuteBox} minutes.

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

function unionSlice(r) {
  const candidates = []
  let overlap = 0
  for (const seat of r.seats) {
    for (const c of seat.candidates || []) {
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
  const read = new Set(r.seats.flatMap((s) => s.files_read || []))
  const gaps = r.slice.files.filter((f) => !read.has(f))
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
function verdictFor(c, out) {
  const rows = ((out && out.verdicts) || []).filter((x) => x && x.id === c.id)
  if (!rows.length) return { id: c.id, verdict: 'unverified', command: '', output: '', mechanism: out ? 'the refuter returned no verdict for this id' : 'refuter seat failed (null result)' }
  if (new Set(rows.map((x) => x.verdict)).size > 1) {
    return { id: c.id, verdict: 'unverified', command: '', output: '', mechanism: `conflicting verdicts for one id: ${rows.map((x) => x.verdict).join(', ')}` }
  }
  const v = rows[0]
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
  for (const v of r.verdicts) if (v.verdict === 'confirmed' || v.verdict === 'unverified') open.push(`${v.verdict}: ${v.id}`)
  // an exact id wins; a case- or space-slipped id counts only when it folds onto exactly ONE claim, so a slip is
  // forgiven but one report never closes two claims (review pass 2, A-S7)
  const fold = (id) => String(id || '').trim().toLowerCase()
  const ids = r.slice.ledger.map((c) => c.id)
  const said = r.seats.flatMap((s) => (s.ledger_status || []).map((x) => String(x.id || '').trim()))
  const hit = (id) => said.includes(id) || (ids.filter((k) => fold(k) === fold(id)).length === 1 && said.some((x) => fold(x) === fold(id)))
  for (const c of r.slice.ledger) if (!hit(c.id)) open.push(`ledger claim ${c.id} not re-verified by any seat`)
  if (open.length) log(`slice ${r.slice.name} NOT closable: ${open.join(' · ')}`)
  return { ...r, closable: open.length === 0, open }
}

const results = await pipeline(
  args.slices,
  (s) =>
    parallel(
      s.models.map((m) => () =>
        agent(finderPrompt(s, m), {
          label: `find:${s.name}:${m}`,
          phase: 'Find',
          schema: FINDINGS,
          model: m,
          effort: 'medium',
          agentType: s.agentType,
        })
      )
    ).then((rs) => ({
      slice: s,
      seats: rs.map((r, i) => ({
        model: s.models[i],
        failed: !r,
        files_read: r ? r.files_read : [],
        candidates: r ? r.candidates : [],
        ledger_status: r ? r.ledger_status || [] : [],
        notes: r ? r.notes : 'SEAT FAILED (null result)',
      })),
    })),
  (r) => unionSlice(r),
  (r) =>
    (r.candidates.length
      ? agent(refutePrompt(r.slice, r.candidates), {
          label: `refute:${r.slice.name}`,
          phase: 'Verify',
          schema: REFUTATION,
          model: 'sonnet',
          effort: 'high',
          agentType: r.slice.agentType,
        })
      : Promise.resolve({ verdicts: [] })
    ).then((out) => ({ ...r, verdicts: r.candidates.map((c) => verdictFor(c, out)) })),
  (r) => closeCheck(r)
)

const slices = results.filter(Boolean)
const droppedSlices = args.slices.length - slices.length
if (droppedSlices) log(`DROPPED ${droppedSlices} of ${args.slices.length} slices (a stage threw) — those slices are UNVERIFIED`)
const droppedSeats = slices.reduce((n, r) => n + r.seats.filter((s) => s.failed).length, 0)
const unverified = slices.reduce((n, r) => n + r.verdicts.filter((v) => v.verdict === 'unverified').length, 0)
const closable = droppedSlices === 0 && slices.every((r) => r.closable)
log(`pass ${args.pass}: ${closable ? 'CLOSABLE' : 'NOT closable'} · ${slices.length} slices · ${slices.reduce((n, r) => n + r.distinct, 0)} distinct candidates · confirmed ${slices.reduce((n, r) => n + r.verdicts.filter((v) => v.verdict === 'confirmed').length, 0)} · dropped seats ${droppedSeats} · unverified ${unverified}`)

return {
  pass: args.pass,
  closable,
  dropped_slices: droppedSlices,
  dropped_seats: droppedSeats,
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
    verdicts: r.verdicts,
    closable: r.closable,
    open: r.open,
  })),
}
