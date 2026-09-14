# Kaizen feedback loop — pieces 1 + 2: axis-keyed OBSERVE, and a command that ACTS on the queue

Status: EXECUTED (2026-09-15 — Phase A `48742920`, Phase B `980f2ca2`, Phase C this commit; whole-plan review closed on the D-252 scope-growth stop at `docs/development/reviews/2026-09-14-plan-1-kaizen-observe-and-act-review.md`)
Profile: small
**Owner:** —
Date: 2026-09-14
Spec: `docs/superpowers/specs/2026-09-10-kaizen-feedback-loop-design.md` § D4 rows 1 and 2 (`:327`, `:328`), the axis table (`:345-354`, the seven per-run axes at `:347-354`, axis 5 at `:351`), § Q3 (`:555`)
Ruling: **D-224** (the loop is approved) · **D-234** (four pieces; 3 + 4 shipped first) · **D-254** (pieces 3 + 4 EXECUTED, `bd99030b`)

## What this plan is

Pieces 3 and 4 made the loop MEASURE. This plan makes it ACT. Today every close writes a `change:`
row — 157 of 162 rows carry a non-`none` value — the relay mails infra a digest daily, and nobody
reads the queue and edits a command. Two edits close that:

- **Piece 1 — OBSERVE.** The `change:` field becomes AXIS-KEYED on the seven per-run axes, so the
  queue is routable instead of 157 rows of prose; and on the commands where a close is expensive
  enough to pay for it, a SUBAGENT writes the line rather than the agent grading its own run.
- **Piece 2 — ACT.** A new `/fabrik-command-improve <command>` reads that command's queue, proposes
  ONE edit to its source, renders, reviews and commits — the commit trailer naming the ledger rows
  it answers and declaring the series the edit expects to move.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"what will i decide? proceed and finish your work properly"* | **IN** — this plan is the proceeding; the operator-decision exit was withdrawn as a stall | the whole plan |
| I2 | *"what have you implemented? how will kaizen work now?"* | **IN** — the loop only closes when something ACTS; that is piece 2 | Phase B |
| I3 | *"during spec creation, spec review, plan creation, plan review, have you provided full feedback to infra about the commands/skills and rules?"* | **IN** — this is the duty piece 2 mechanises; the `change:` field is where that feedback already lands | Phase A + B |
| I4 | *"this should not take that much of time, what is going on"* / *"why did you drift that much?"* | **IN** as a CONSTRAINT — `/fabrik-command-improve` is bounded by construction: ONE command, ONE edit, `/fabrik-review-scoped`, never the heavy loop | Phase B, Global Constraints |
| I5 | the spec's own piece-1 clause *"have a subagent write it"* on the expensive commands | **IN** — but the command list is DERIVED at close time, never pasted | Phase A, A4 |
| I6 | the spec's `rid` prerequisite for piece 2 (`spec:328`) | **OUT-OF-SCOPE — measured away.** `ts` is unique on 162 of 162 live rows, so the conditional never fires and the lock-owned writer needs no edit | § Evidence M1 |
| I7 | the CLAUDE.md contract line that makes running the command a DUTY (`spec:328`) | **OUT-OF-SCOPE — lock-owned.** `CLAUDE.md` belongs to the active `2026-09-09-plan-1-review-convergence-redesign` lock; routed to infra as mail with the exact sentence | Phase C step 4 |
| I8 | the `NEXT` map entry for the new command (`assemble_commands.py`) | **OUT-OF-SCOPE — lock-owned**, and non-blocking: a missing entry renders a default sentence (`assemble_commands.py:102`) | Phase C step 4 |
| I9 | Q3's grading-and-revert clause (`spec:555`) | **OUT-OF-SCOPE — waits on the noise floor** (M2/D3 sign-off); the DECLARATION ships now, the grading does not | Phase B, B6 |
| I10 | per-command variance of the fragment via a renderer PARAMS slot | **OUT-OF-SCOPE — lock-owned and unnecessary**: the condition lives in the fragment's TEXT and is evaluated by the closing agent against live data | Phase A, A4 |

Intake: 10 items — 5 IN, 5 OUT-OF-SCOPE (each named above), 0 ASK.

## What we already agreed (citations, not restatement)

- The axes are properties of the COMMAND TEXT, and the loop's gap is that nobody acts on the
  `change:` queue — `spec § D4` preamble (`:196`), D-234. The spec names EIGHT axes and this plan
  keys SEVEN: axis 5, continuous improvement, is read across runs and has no per-run key
  (`spec:351`, the axis table's own row 5) — so seven keys for eight axes is the spec's arithmetic,
  not a miscount here.
- Piece 1 is two edits: axis-keying, and a subagent writer on the expensive commands, chosen as a
  RANK CUT re-derived at sign-off — `spec:327`.
- Piece 2 is a new command whose applied edit is a COMMIT carrying the rows it answers and Q3's
  declaration — `spec:328`.
- Q3's contribution is the declaration; the grading and the revert wait on the noise floor —
  `spec:555-566`.
- Never auto-edit a fleet-synced governance file; the optimiser PROPOSES and a session applies
  through the normal review path — `spec § Constraints 2`.

## Global Constraints (every phase inherits these)

- **The close parser is NOT ours to change.** `scripts/command_run.py` is owned by the active
  `2026-09-09-plan-1-review-convergence-redesign` lock. Every piece-1 edit must be ADDITIVE to a
  parser that stays exactly as it is.
- **No field-boundary character may appear anywhere inside the `change:` value, and the reason has
  TWO arms — one loud, one silent.** `_USAGE_LABEL_RE` (`scripts/command_run.py:1125-1127`) matches
  `confusion|waste|change|filed|cost` after a boundary — the start of a line, or `·`, `|`, `;`, a
  newline. **Loud arm:** `waste` is both a field label and one of the seven axes, so `change: lean: X
  · waste: Y` is parsed as a SECOND `waste` field and the close is REFUSED as a duplicate. **Silent
  arm, and it is the dangerous one:** `cost:` is OPTIONAL on a FEEDBACK line, so an injected one is
  usually the FIRST occurrence and the duplicate check never fires — `change: lean: X · cost: 3`
  parses to `change='lean: X'` at rc 0, the rest of the sentence is gone, and a phantom `cost: 3`
  lands in the ledger row. (The duplicate check at `:1223-1225` is label-agnostic and DOES cover
  `cost`: a line that already carries a real `cost:` gets the loud arm instead. So the silence is a
  property of the line, not of the label — executed both ways, § Evidence M3 shapes F and F2.) A
  ` · ` with no label after it survives intact (shape I), which is why the rule below is about
  boundary characters and not about axes. **So: the axis key sits at the HEAD of the value, a second
  axis is separated by a COMMA, and no `·`, `|`, `;` or newline appears in the value at all.**
- **⚠️ The axis prefix DISABLES the placeholder guard for `change:`, and the fix is not ours to
  make.** `_is_placeholder` (`scripts/command_run.py:1168`) is anchored —
  `re.fullmatch(r"<(?P<c>.*)>\s*\[?", value.strip())` — so any non-`<` prefix makes it return
  `False` before any of its logic runs. Today `change: <the ONE concrete edit…>` is REFUSED as a
  pasted placeholder; after piece 1, `change: lean: <…>` closes cleanly (executed, § Evidence M3
  shapes G1–G3). The counter-measure must therefore catch the TEXT, not the brackets — de-bracketing
  the fragment's example would defeat both the parser AND a bracket-shaped detector at once
  (`_is_placeholder("the ONE concrete edit to the command/rule…")` is `False`, executed). So:
  Phase A5's `placeholder` bucket matches the GRAMMAR PHRASES the fragment itself prints. Two rules
  keep that from rotting, because `command_run.py:1142-1150`'s `_GRAMMAR_NOUNS` is a hand-kept
  mirror of the OLD sentence in a file this plan may not edit, and step 3 says the sentence will
  diverge: **(a) the report carries its OWN noun list, seeded from the fragment's text, never a
  cross-file import of another script's private constant** (`command_feedback_report.py` imports
  nothing from `command_run.py` today and must not start), and **(b) a grader pins that list against
  the fragment's LIVE text** — so any reword that empties the bucket fails a test instead of
  silently passing. The measured starting point: the fragment's blockquoted grammar at `:18-22`
  prints FIVE of the seven phrases `_GRAMMAR_NOUNS` holds (`steps, turns` at `:19`,
  `the ONE concrete edit` at `:20`, `mail id` at `:21`, `what your run touched` at `:22`, and
  `what in the command` across the `:18`–`:19` line break — the count was four until the whole-plan
  review re-derived it with the blockquote markers stripped, which is how a reader sees it), so the
  bucket has five independent handles today and the grader is what keeps that true — not a promise
  to preserve any one of them — with or without brackets
  and with or without an axis key; the fragment's worked example is a REAL past edit rather than a
  template, so there is nothing template-shaped to paste; and Phase C step 4's mail carries the one-line parser
  fix — strip a leading `<axis>:` before the placeholder test — because `command_run.py` is
  lock-owned and this hole stays open until they apply it.
- **A close with nothing to change writes `change: none`, with NO axis key.** The axis names the
  edit, so a verdict of "no edit" has no axis. This is load-bearing for the reader:
  `_is_none` (`scripts/command_feedback_report.py:66-69`) tests the value's HEAD token, so
  `lean: none` would count as a real change and over-report the queue (executed, § Evidence M8).
  **And the axis tally NEVER sees a `none` row:** a no-change close is counted by `change_none`,
  which already exists, and is excluded from the four axis buckets — otherwise the mandated honest
  shape would land in `unkeyed` and the bucket that means "the instrument is broken" would be mostly
  people following the rule (5 of 162 rows today).
- **`_cap_field` truncates at 2000 characters** (`scripts/command_run.py:1235`). The live median
  `change:` value is 249 chars, so the convention has room; a grader pins that the axis key survives
  a value at the cap.
- **The fragment is box-wide, not fleet-wide.** `commands/_fragments/close-feedback.md` is appended
  to 36 of 36 rendered commands (`assemble_commands.py:1193-1194`) written under `~/.claude/commands/`
  — outside this repo. It is NOT in the governance-sync trigger regex and NOT in the synced manifest,
  so it reaches every session on this box and no project repo.
- **Render order is render → `--check` → commit, from the main master checkout only.** A render from
  a worktree PRUNES master-only commands box-wide (`assemble_commands.py:1235-1243`).
- **A command whose text fans out MUST carry the literal `THE DISPATCH STEP (D-191`** or
  `assemble_commands.py --check` reports DRIFT and the `command-corpus-check` pre-commit hook
  refuses the commit (`check_command_corpus.py:330`, `:1277-1281`).
- **The cobra-effect statement this plan owes for its own metric.** The per-axis tally is a
  measure, so here is the cheapest way to satisfy it without producing the outcome: **paste `lean:`
  in front of whatever you were going to write.** It costs nothing, it is the fragment's own first
  example, and it moves the tally while teaching the corpus nothing. Three counter-measures ship with
  it, in the same change: the report distinguishes `unkeyed` from `bad-axis` from `placeholder`, so
  a lazy key is visible as a key rather than as an axis; the tally is never used to rank or gate
  anything — `/fabrik-command-improve` reads the VALUES, and the axis is only a sort order; and the
  writer-seat rule is derived from the cost of the run, not from the tally, so no one can move a
  command into or out of the seat list by how they key their line.
- **Bounded by construction (I4).** `/fabrik-command-improve` improves ONE command per run with ONE
  proposed edit and closes on `/fabrik-review-scoped`. It never opens the heavy review loop.
- **No auto-apply.** The command proposes and commits through the normal review path; it never
  writes a `.windsurf/rules` pack or a `templates/governance/` file, and it never edits a command
  source owned by another plan's active lock — it reads the lock first and says so.
- 12-Factor: this plan adds no service, no env var, no logfile, no migration, no backing service.
  The two scripts it touches are stdlib-only local readers; the `.md` surfaces are prompt text.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/40-documentation.md` (MATCHED by `review_rubric.py --changed`) | doc-sync triggers; a new file owes an `INDEX.md` row; fenced code only; no skipped heading levels | the MATCHED block quoted in § Constraints Digest |
| `.windsurf/rules/core/10-python.md` (FLOOR) | `uv` is the package manager; `datetime.now(UTC)`; no file logging; ruff rule-sets | rubric FLOOR, quoted below |
| `.windsurf/rules/core/62-using-subagents.md` (ACTIVE) | the pool is OFF (D-181/D-182) — every fan-out this plan's command names runs NATIVE, sized by `dispatch_headroom.py` | `62-using-subagents.md` § Dispatch policy |
| `scripts/command_run.py` (LOCK-OWNED, read-only here) | the close's four-field grammar, the boundary regex, the 2000-char cap, the ledger path | `:1120`, `:1125-1127`, `:1235`, `:1254-1255` |
| `scripts/command_feedback_report.py` (ours) | the only reader of the ledger's `change:` rows; `_rows` `:44`, `build` `:330`, `_items` `:426`, `change_none` `:376`, `render` `:513` | read this run |
| `commands/assemble_commands.py` (LOCK-OWNED, read-only here) | the render path: the source glob IS the registry `:1130`; `NEXT` falls back `:102`; close-feedback auto-append `:1193`; prune `:1235` | read by the authoritative seat |
| fabrik-lib | **checked, nothing to vendor** — this is prompt text plus a stdlib reader over a local JSONL; no module in `fabrik-lib/README.md` covers corpus-feedback routing | no 🆕 candidate: the surface is hub-specific by construction |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Rule | Verbatim | Source |
|---|---|---|
| MUST | *"**No skipped heading levels** — `##` to `###`, never `##` to `####`"* | `.windsurf/rules/core/40-documentation.md:240` |
| MUST | *"**Fenced code blocks only** — never indented code (AI treats it inconsistently)"* | `.windsurf/rules/core/40-documentation.md:242` |
| MUST | *"⚠️ **Link it or it is decoration.** … a file only gets read when something points at it"* | `.windsurf/rules/core/40-documentation.md:224` |
| MUST | *"Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it"* | `.windsurf/rules/core/40-documentation.md:111` |
| BAN | *"`uv` is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`"* | `.windsurf/rules/core/10-python.md:21` (FLOOR) |
| BAN | *"**`datetime.now(UTC)`, never `datetime.utcnow()`**"* | `.windsurf/rules/core/10-python.md:219` (FLOOR) |

```bash
python3 scripts/review_rubric.py --changed commands/_fragments/close-feedback.md commands/_sources/fabrik-command-improve.md scripts/command_feedback_report.py
# FLOOR: core/10-python.md + the 12-factor axes
# MATCHED — packs whose globs hit the changed paths
#   core/40-documentation.md  (hit: commands/_fragments/close-feedback.md, commands/_sources/fabrik-command-improve.md)
```

## Phase A — OBSERVE: the axis key, and a derived writer rule

**Interfaces — Produces:** the axis vocabulary (seven tokens), the head-position rule, and two new
report flags: `--observer-rank` (prints the commands whose closes are expensive enough to pay for a
writer seat, derived live) and axis-grouped output inside the existing report. **Consumes:** nothing
from later phases.

1. **Read `commands/_fragments/close-feedback.md` whole before editing** (138 lines) and find the ONE
   place that defines the `change:` field's shape — the blockquoted FEEDBACK grammar at `:18-22`,
   whose `change:` clause is the same sentence `scripts/command_run.py:1131-1132` holds as
   `_USAGE_GRAMMAR`. The axis rule is written INSIDE that definition, not appended as a new section.
2. Rewrite the `change:` placeholder to carry the axis key and the separator rule, in the fragment's
   own voice — **and write the worked example as a REAL past edit from the ledger, never as a
   template**, so there is no template-shaped string in the fragment for anyone to paste. **Keep the
   `change:` clause's own noun phrase (`the ONE concrete edit`) intact while rewording around it**,
   and if a reword genuinely needs to drop it, update the report's noun list in the same change —
   step 6's grader will fail otherwise, which is the point: the seven axes (`lean` · `fast` · `accurate` · `waste` · `infra` · `rules` ·
   `manifesto`), the key at the HEAD of the value, a second axis after a COMMA, and the one-line
   reason the boundary characters are forbidden (a ` · ` before `waste:` is parsed as the FEEDBACK
   field and refuses the close).
3. **Disclose the drift the fragment cannot fix.** `_USAGE_GRAMMAR` in the lock-owned
   `command_run.py` is a hand-kept twin of this sentence and will now differ. Write one line in the
   fragment saying which is canonical (the fragment) and that the code constant is mailed to infra
   in Phase C — so the next reader is not left to guess which of two truths is current.
4. **The writer rule is DERIVED, never pasted — and it FAILS OPEN off the hub.** Add
   `--observer-rank` to `scripts/command_feedback_report.py`: it prints, one command per line, the
   top four by the mean of `tok_in + tok_out` per close — **`tok_in + tok_out` only; cache tokens are
   excluded. **Reuse `_io_total` (`scripts/command_feedback_report.py:224-247`), which is already
   exactly Σ `tok_in` + `tok_out` and whose docstring says why it is DELIBERATELY not `_tok_total`;
   do not write a second inline sum, and never reuse the cache-INCLUSIVE `_tok_total`/`median tokens`
   path** (at 116 rows that cache-inclusive median ran 200–320× R3's mean, `spec:135`) —
   with each command's n. The fragment then says: *a close for a command named by
   `python3 /opt/fabrik/scripts/command_feedback_report.py --observer-rank` dispatches ONE Sonnet
   seat to author the `change:` line from the run's own record, rather than the agent grading
   itself.* Two things make that safe in the ~46 project repos, where this rendered text is loaded
   by every session and the script does not exist on a relative path: the path is **ABSOLUTE**, and
   the instruction carries its own escape in one clause — *if the hub script or the ledger is not
   readable from here, write the line yourself; the seat is an optimisation, never a gate.* The
   absolute-path half is the pattern `commands/_fragments/run-record.md:40` already uses for a
   hub-only script; the escape half deliberately DIVERGES from it, and the difference is the point:
   that fragment refuses to let a missing GATE read as compliance, and this is not a gate — a close
   that writes its own `change:` line has lost an optimisation, not skipped a check. The rank moves with the data and no list rots in a
   box-wide file.
5. Add axis parsing to the report: a helper that reads the leading `<axis>:` token off a `change:`
   value (case-insensitive, only the seven, only at the head, only before the first comma), and a
   per-axis tally per command in `build()` — **an instrument defect is counted, never bucketed** (the
   pattern `kaizen_collect_v2.py:384` already uses, extended here, not reinvented). **FOUR buckets,
   in this fixed precedence, tested in this order:** `placeholder` (a value carrying the grammar's
   own noun phrases, bracketed or not — § Global Constraints) → `bad-axis` (a leading `word:` outside
   the seven — an attempt that missed) → the named axis (one of the seven) → `unkeyed` (no `word:`
   head at all). A value that satisfies two rules lands in exactly one bucket, and the four counts
   sum to the number of rows carrying a NON-`none` `change:` value — the tally's population, since
   `none` rows are excluded before it runs and counted by `change_none` instead (157 of 162 today).
   **The mirror this breaks, named rather than discovered:** `_is_none` is SHARED — `_items()`
   (`:426-450`) gates `change`, `confusion` and `waste` on it, and `change_none` (`:376`) reads it
   too. So the axis strip is **NOT** added inside `_is_none`; it goes in a separate
   `_change_is_none(value)` applied only to the `change` field, and a grader pins that a `confusion:`
   or `waste:` value beginning `lean:` is unaffected.
6. Graders in `tests/test_command_feedback_report.py`, each proven red-on-revert:
   - the axis helper accepts the seven at the head and rejects a key after a comma, after a ` · `,
     mid-sentence, and an eighth word;
   - a value at the 2000-char cap keeps its axis key;
   - the four buckets in their fixed precedence — `placeholder` (a grammar noun phrase, bracketed or
     not, with or without an axis key) beats `bad-axis` beats the named axis beats `unkeyed` — and
     the four counts sum to the number of rows carrying a non-`none` `change:` value, never to the
     row total (the `none` rows are `change_none`'s, and a fixture carrying both proves it);
   - a `none` row is counted by `change_none` and appears in NO axis bucket;
   - `_change_is_none` strips a leading axis key before the `none` test, and a `confusion:` or
     `waste:` value beginning `lean:` is UNCHANGED by it (the shared-helper mirror);
   - `--observer-rank` on a six-command fixture names the top four by `_io_total` per close with
     their n, ignores cache tokens, degrades to "fewer than four qualified" and to "nothing
     measurable", and never crashes;
   - the report's placeholder noun list is pinned against the LIVE text of
     `commands/_fragments/close-feedback.md`: every phrase in the list still appears in the fragment,
     and the fragment's `change:` clause still matches at least one — a reword that empties the
     bucket fails here;
   - `--queue` escapes a TAB or a newline inside a value;
   - the whole-report property graders still hold (no cell prints `None`, every figure finite).
7. **Canary (spec § Constraints — every metric ships one):** a grader that fires when the axis tally
   is computed over ZERO rows carrying a `change:` value — the report must say so, never print a
   confident `0` per axis. This is the same phantom-zero class the pieces-3+4 review closed.
8. Gate: `uv run pytest tests/test_command_feedback_report.py -q` green ·
   `uv run ruff check scripts/command_feedback_report.py tests/test_command_feedback_report.py` clean ·
   `python3 scripts/command_feedback_report.py --since 30` renders unchanged for every pre-existing
   column (diff against a pre-change capture — byte-identical or the difference is named).
9. `python3 scripts/enforcement/check_doc_sync.py` after staging for real (an `add -N` file asserts
   nothing) + the INDEX row if a file was added.
10. **`/fabrik-review-scoped` on this phase's changed surface, run to its coverage-adjudicated exit**
    — every class CLEAN/FIXED/REFUTED/RECORDED, every confirmed finding fixed in-run with a grader.
11. Commit the phase with explicit pathspecs and provenance trailers.

**Behavior Contract — Phase A**

- **Given** a `change:` value whose head is one of the seven axis tokens, **When** the report parses
  it, **Then** the row is tallied under that axis (`scripts/command_feedback_report.py`, the new
  helper; the axis vocabulary is `spec:347-354`).
- **Given** a `change:` value with an axis token after a comma, **When** it is parsed, **Then** the
  row is tallied under the HEAD axis only — a comma-separated second axis never re-keys the row.
- **Given** a `change:` value with no axis token, **When** it is parsed, **Then** it counts as
  `unkeyed` and the count is published, never dropped.
- **Given** a `change:` value at the 2000-character cap, **When** it is parsed, **Then** the axis key
  still reads (`scripts/command_run.py:1235` is the cap this pins against).
- **Given** a ledger with no `change:`-carrying row, **When** the axis tally renders, **Then** it
  says nothing was measured rather than printing `0` for every axis.
- **Given** a FIXTURE ledger holding six commands with token pairs, **When** `--observer-rank` runs,
  **Then** it prints the four highest by the mean of `tok_in + tok_out` per close, each with its n,
  and the ranking ignores cache tokens entirely (a row with a huge `tok_cache_read` does not move).
- **Given** a fixture with fewer than four commands carrying a token pair, **When** `--observer-rank`
  runs, **Then** it prints the ones that qualify and says how many of how many commands qualified —
  never a padded list and never a crash.
- **Given** a fixture where no row carries a token pair, **When** `--observer-rank` runs, **Then** it
  says nothing is measurable and exits 0, so a closing agent reading it falls through to writing the
  line itself.
- **Given** a `change:` value that is the grammar's own `<…>` text behind an axis key, **When** the
  report parses it, **Then** it is counted as `placeholder`, not as a change.
- **Given** a `change:` value whose head is a `word:` outside the seven, **When** it is parsed,
  **Then** it is counted as `bad-axis`, distinct from `unkeyed`.
- **Given** a close with nothing to change, **When** it writes `change: none` with no axis key,
  **Then** the row is counted by `change_none` and appears in no axis bucket.
- **Given** `change: lean: none`, **When** `_change_is_none` is applied, **Then** the value reads as
  `none` after the axis key is stripped, so `change_none` does not over-report — and the same input
  in a `confusion:` or `waste:` field is left alone.
- **Given** a `change:` value carrying the grammar's own noun phrase with no brackets and an axis
  key, **When** the report parses it, **Then** it is counted as `placeholder` — the shape the close
  parser can no longer refuse.
- **Given** the live 162-row ledger, **When** the phase's change lands, **Then** every pre-existing
  rendered column is byte-identical to a capture taken before the change — and the same comparison
  is re-run against a fixture that DOES carry axis keys, so the assertion is not vacuous.

## Phase B — ACT: `/fabrik-command-improve`

**Interfaces — Consumes:** Phase A's axis vocabulary and the report's reader. **Produces:** the
command source, and `--queue <command>` on the report (every non-`none` `change:` row for one
command, newest first, each line carrying its `ts` so the commit can name the rows it answers).

1. Add `--queue <command>` to `scripts/command_feedback_report.py`: one row per line, TAB-separated
   — `<ts>\t<axis|unkeyed|bad-axis|placeholder>\t<the change value>` — filtered to that command,
   newest first, with a header stating how many of how many ledger rows matched. The delimiter is a
   TAB and not ` · ` on purpose: a stored `change:` value may legally contain ` · ` whenever no
   label follows it (§ Evidence M3 shape I — `change: lean: X · and more prose` stores the middle dot
   intact; shape F is the opposite case, where a following label CUTS the value), so a middle-dot
   delimiter would share an alphabet with its own payload and a three-field line would read as
   five. Any TAB or newline inside
   a value is escaped on the way out. This is the command's whole input, and making it a flag rather
   than prose in the command text means the queue is testable.
2. Write `commands/_sources/fabrik-command-improve.md`, modelled on
   `commands/_sources/fabrik-review-scoped.md` (the closest existing shape: short, a run record, a
   bounded ledger, fix-in-run semantics). It carries:
   - frontmatter `description:` ending `Stage: utility.` and `argument-hint: "<command>"`;
   - `{{include:run-record}}` — `{{COMMAND}}`/`{{PHASES}}` are renderer-filled, never hand-authored;
   - the queue read (`--queue`), grouped by axis;
   - **ONE proposed edit per run**, chosen as the edit that answers the most rows, with the rows it
     answers listed by `ts`;
   - the lock check: read `.fabrik/plan-locks/*.json` for an ACTIVE lock owning the target source and
     STOP with the owner named if one holds it;
   - render → `assemble_commands.py --check` → `/fabrik-review-scoped` → commit, in that order, from
     the main master checkout only;
   - the commit trailer, spelled literally:
     `Agent-Context: command-improve <command> · rows <ts,…> · expects <series> <direction>`
     in its own paragraph with no blank line inside the block, verified with
     `git log -1 --format='%(trailers:key=Agent-Role,valueonly)'`;
   - the literal `THE DISPATCH STEP (D-191` line, because the command dispatches a review seat and
     the corpus grader refuses a fan-out command without it;
   - the terminal condition: one edit committed and rendered, or an explicit `no edit this run —
     the queue holds nothing that survives review`, which is a legitimate outcome and not a failure.
3. Render from the main master checkout, then `python3 commands/assemble_commands.py --check` clean
   — and then `python3 scripts/final_gate.py --json --check` BEFORE this phase's commit, because
   `check_command_corpus.py` (whose per-source predicates the new command must satisfy) is invoked
   from `final_gate.py` and by nothing the pre-commit hook runs. Running it here rather than in
   Phase C is what keeps a failing predicate from being discovered after the source is committed.
4. `INDEX.md` gains the row for the new source (Doc Sync: file added).
5. Graders in `tests/test_command_feedback_report.py` for `--queue`: the filter, the ordering, the
   `ts` on every line, the denominator in the header, and an empty queue that says so.
6. **Q3's declaration, not its grading.** The command's trailer names the series it expects to move
   and the direction; nothing grades it until the noise floor exists (`spec:555-566`). The command
   text says so in one line, so a future reader does not think the grading was forgotten.
7. Gate: the suite green · ruff clean · `assemble_commands.py --check` clean ·
   `python3 scripts/command_feedback_report.py --queue fabrik-review` prints a non-empty queue
   (46 rows waiting when this plan was written).
8. **`/fabrik-review-scoped`** to its exit, then commit with explicit pathspecs and trailers.

**Behavior Contract — Phase B**

- **Given** a command name with rows in the ledger, **When** `--queue <command>` runs, **Then** every
  non-`none` `change:` row for it prints with its `ts`, newest first, under a header naming how many
  of how many rows matched.
- **Given** a command with no rows, **When** `--queue` runs, **Then** it says so and exits 0.
- **Given** the new source, **When** `assemble_commands.py --check` runs, **Then** it reports no
  drift (the `THE DISPATCH STEP (D-191` literal is present).
- **Given** a target command source owned by an ACTIVE plan lock, **When** the command runs, **Then**
  it stops and names the lock's owner rather than editing.
- **Given** an applied edit, **When** it is committed, **Then** the trailer block parses and carries
  the rows by `ts` and the expected series with its direction.

## Phase C — Finish — ✅ EXECUTED 2026-09-15

**Phase C as executed (2026-09-15).** Steps 1–2: 137 passed across the three suites, `ruff` clean,
`final_gate.py --json --check` `"status": "success"` 65/0. Step 3: the ONE heavy `/fabrik-review` ran
four rounds (confirmed 14 → 4 → 1 → 3) with six author-blind seats and closed on the D-252
scope-growth stop, which `check_review_coverage.py` recognises as an exit since `130c6ef0`. Step 4:
ONE mail to infra carrying all SIX lock-owned edits — `01M2H05R2SSTJK166WAVBR3MKG`. Step 5:
governance rows by private index; `INDEX.md`'s row for the new command source rode Phase B's own
commit, as Phase B step 4 said. Step 6: this flip, the citations repaired before the archive move,
the lock released.

**Three things this execution learned that the plan did not say.** (1) A new command source's phase
count comes from `## PHASE N` headings, and a numbered `## 1 — …` heading silently falls through to a
section count — a five-step command declared six phases until the headings were renamed. (2) The
render refuses a composed skill description over 1024 characters, which is a real gate nobody names
until it fires. (3) The `--ledger` flag's `or` default treated `Path("")` as truthy and read the CWD,
which is the same falsy-value class as the `--queue ""` defect a seat found one flag over.


1. Full suites + `ruff` clean over both changed scripts and their tests.
2. `python3 scripts/final_gate.py --json --check` → `"status": "success"`; read `skipped_checks`.
3. The ONE heavy **`/fabrik-review`** over the whole-plan diff, receipt at
   `docs/development/reviews/2026-09-14-plan-1-kaizen-observe-and-act-review.md` with the verbatim
   gate embed and a per-phase verdict. Sized with `dispatch_headroom.py --units 2 --risky 1`,
   stamped with `command_run.py dispatch --seats <n>` before the seats go out.
4. **ONE mail to infra, carrying SIX exact edits to lock-owned files — this is the only place the
   plan promises a mail, and every other section points here.** Each item is written out verbatim so
   the lock holder applies rather than re-derives: (a) the `CLAUDE.md` contract line making
   `/fabrik-command-improve` a duty when a command's queue is non-empty; (b) the `NEXT` map entry for
   the new command in `commands/assemble_commands.py`; (c) the `_USAGE_GRAMMAR` twin at
   `scripts/command_run.py:1131-1132`, which this plan's fragment edit puts out of step; (d) the
   one-line placeholder fix — strip a leading `<axis>:` before `_is_placeholder`'s `re.fullmatch`
   (`command_run.py:1168`) — which is the only real close of the hole § Global Constraints names;
   (e) the two sentences `docs/reference/command-run-protocol.md` and
   `docs/workstation/kaizen-event-stream.md` each need, since both are lock-owned and this plan makes
   them stale; and **(f)** the `change:` clause of the FINAL OUTPUT block in `CLAUDE.md` AND
   `templates/governance/CLAUDE.md` — the fragment tells every session on the box that both twins are
   "in the edit mailed to infra", so leaving this out would make the shipped fragment's own sentence
   false. Precedent for the route: `01M2AJKKVGH8Q2PK51CM2GJ5FC`.
5. Governance rows by private-index plumbing (HEAD + mine, `$base` CAS): `CHANGELOG.md` one entry ·
   `docs/DECISIONS.md` one row minted with `decisions.py --next-id` · `docs/STRATEGIC_BACKLOG.md` for
   any residue · `docs/development/PLANS.md` regenerated by `docs_updater.py --sync`.
6. Status → EXECUTED citing the receipt; **repair every doc that cites this plan's pre-archive path
   before the archive move** (`git grep -n '<plan path>' -- docs/`), then archive, release the lock,
   commit + push, scratch sweep.

## File Scope (owned paths)

- commands/_fragments/close-feedback.md
- commands/_sources/fabrik-command-improve.md
- scripts/command_feedback_report.py
- tests/test_command_feedback_report.py
- docs/development/PLANS.md
- docs/development/reviews/2026-09-14-plan-1-kaizen-observe-and-act-review.md
- .fabrik/plan-locks/2026-09-14-plan-1-kaizen-observe-and-act.json

`INDEX.md` is NOT here and must not be: it is one of the seven governance files
(`check_plan_tickets.py::GOVERNANCE_FILES`), which are orchestrator-applied shared-append surfaces
deliberately outside the plan lock — listing one is a dedicated gate ERROR. Its row for the new
command source rides PHASE B's own commit — by the same private-index
plumbing, because a governance file is orchestrator-applied wherever it is written and the Doc Sync
trigger ("file added") fires in the phase that adds the file. (Phase B step 4 always said so; this
sentence said Phase C until the whole-plan review caught the two halves disagreeing.) `docs/development/PLANS.md` IS here: it is written by
`docs_updater.py --sync` in Phase C and is not a governance file, so nothing else covers it.

**OUT of scope because the ACTIVE `2026-09-09-plan-1-review-convergence-redesign` lock owns them —
7 of that lock's 34 owned paths, named because this plan would otherwise touch them:** `CLAUDE.md`,
`templates/governance/CLAUDE.md`, `scripts/command_run.py`, `tests/test_command_run.py`,
`docs/reference/command-run-protocol.md`, `commands/assemble_commands.py`, `scripts/final_gate.py`
(runnable read-only, never edited). **Nine more of its 34 are operationally live for this plan and are
read, never written — this list is the ones this plan TOUCHES, not the lock's remainder (34 owned =
7 out-of-scope + 9 read-only + 18 neither):** `scripts/enforcement/check_review_coverage.py` and
`scripts/enforcement/check_review_hygiene.py` (they grade the Phase C receipt),
`scripts/sysadmin/dispatch_headroom.py` (Phase C3 sizing), `scripts/review_receipt.py`,
`commands/_sources/fabrik-review-scoped.md` (the model for B2 and the closer of A10/B8),
`commands/_fragments/subagents-core.md` (where the `THE DISPATCH STEP (D-191` literal comes from),
`.windsurf/rules/core/62-using-subagents.md` (a Context Ledger row),
`scripts/enforcement/check_convergence.py` (the gate that grades this plan's own Evidence and
Self-audit at every flip), and `docs/workstation/kaizen-event-stream.md` — which this plan may make stale under the Doc Sync floor
and can neither edit nor silently ignore, so Phase C step 4 mails it to the lock holder with the
sentence it needs. All five edits ride ONE mail in Phase C step 4.

**One coupling this plan cannot satisfy, stated here rather than discovered at the gate.**
`scripts/command_feedback_report.py:2` declares `# AFTER-EDIT: tests/test_command_feedback_report.py,
docs/reference/command-run-protocol.md`, and that doc is lock-owned. Every phase commit that touches
the report therefore draws the `check_script_headers.py` WARN for a coupled file it did not stage —
expected, advisory, and never a reason to edit a locked path. Phase C step 4's mail carries the
sentences that doc needs (item (e)), and each phase commit names the WARN so a reader does not read
it as an oversight.

## Evidence

**M1 — `ts` is a unique per-row handle, so piece 2 needs no lock-owned writer change.**

```
rows: 162
ts present: 162 | distinct: 162 | dupes: []
id-ish fields present: ['sid']   # a SESSION id, non-unique across a session's closes — not a row handle
```

**M2 — the rank cut still names the spec's four (R3 = mean of `tok_in + tok_out`, cache excluded).**

```
command                         n n_tok      mean io
fabrik-execute-plan            17    16      539,433
fabrik-review                  46    42      301,428
fabrik-plan-review             13    12      255,714
fabrik-plan-after-chat          8     8      217,986
--- the cut ---
fabrik-spec-review             14    14      191,703
```

**M3 — the axis key is additive to the lock-owned parser, with exactly one trap.** Executed against
`scripts/command_run.py::_parse_usage_feedback`, imported rather than re-implemented:

```
A  change: lean: <text>           -> change='lean: <text>'           missing=[]                    PASS
B  change: waste: <text>          -> change='waste: <text>'          missing=[]                    PASS
C  change: lean: X, accurate: Y   -> change='lean: X, accurate: Y'   missing=[]                    PASS
D  change: lean: X · waste: Y     -> change='lean: X'                missing=['waste (duplicate)'] REFUSED (loud)
E  change: [waste] <text>         -> change='[waste] <text>'         missing=[]                    PASS
F  change: lean: X · cost: 3      -> change='lean: X'  cost='3'      missing=[]                    PASS  ← SILENT
F2 …· cost: 3 · cost: 9 (cost present) -> change='lean: X' cost='9'   missing=['cost (duplicate)']  REFUSED (loud)
I  change: lean: X · and more prose -> change='lean: X · and more prose'                missing=[]  PASS  ← the dot SURVIVES
G1 change: <the ONE concrete…>    -> (unprefixed)                    missing=['change (placeholder)'] REFUSED
G2 change: lean: <the ONE conc…>  -> change='lean: <the ONE conc…'   missing=[]                    PASS  ← the guard is off
G3 change: lean: <…>              -> change='lean: <…>'              missing=[]                    PASS  ← the guard is off
```

F is the silent arm: the sentence after ` · ` is gone at rc 0 and a phantom `cost` field lands in
the ledger row. G1 vs G2 is the placeholder hole: the same pasted grammar is refused bare and
accepted with an axis key, because `_is_placeholder` (`scripts/command_run.py:1168`) is a
`re.fullmatch` on `<…>` and any prefix defeats it.

**M8 — `_is_none` tests the HEAD token, so a no-change close must not carry an axis key.**

```
_is_none('none')                 = True
_is_none('lean: none')           = False      <- would count as a real change
_is_none('lean: cut the digest') = False
_is_none('  none  ')             = True
```

**M4 — the queue is real on day one.**

```
change: non-none 157 of 162
names a command or a file: 63 of 162
queue depth: 46 fabrik-review · 42 fabrik-review-scoped · 16 fabrik-execute-plan ·
             14 fabrik-spec-review · 13 fabrik-plan-review · 8 fabrik-plan-after-chat · 8 fabrik-spec · …
median change: value length: 249 chars
```

**M5 — a new command source needs no lock-owned file.** `commands/assemble_commands.py:102` —
`nxt = NEXT.get(name, "(no defined successor — this command is terminal or standalone).")`; the
source glob at `:1130` IS the registry.

**M6 — the blast radius.** The fragment reaches 36 of 36 rendered commands
(`assemble_commands.py:1193-1194`, population = `commands/_sources/*.md`), written under
`~/.claude/commands/`, and `commands/_fragments/` appears in neither the governance-sync trigger
regex (`.pre-commit-config.yaml:155`) nor `scripts/fabrik_synced_manifest.py` — box-wide, not
fleet-wide.

**M7 — the lock census.** 69 lock files, 2 `active`. The second (`2026-09-05-plan-1-windowed-cost-sidecar`)
owns none of this plan's paths; the first owns `CLAUDE.md` (`:19`), `commands/assemble_commands.py`
(`:28`) and `scripts/command_run.py` (`:34`), and is a live unfinished plan, not an abandoned file.

## Self-audit

- **Grounding passes:** three native seats in parallel (one Opus authoritative over blast radius, the
  lock and the render path; two Sonnet breadth over the close-out path and the command shape), sized
  by `dispatch_headroom.py --units 2 --mechanical 0` → `SEATS: 3`, stamped before dispatch. Each
  finding below is theirs, re-checked by me against the cited line.
- **(a) Coverage.** All five "What we already agreed" lines map: the axes-and-the-gap framing → the
  whole plan's shape, and specifically A5's three buckets (the axis is a property of the command
  text, so the tally is per command) and B1's queue (the gap is that nobody reads it); axis-keying →
  A2; the subagent writer → A4; the new command → B2; Q3's declaration → B6; the no-auto-edit
  constraint → Global Constraints and B2's lock check.
- **(b) Cross-phase signatures.** Phase A produces the axis vocabulary and `--observer-rank`; Phase B
  consumes the same vocabulary in `--queue`'s second column and nothing else. One reader
  (`scripts/command_feedback_report.py`), one vocabulary, one helper — the two phases cannot drift
  apart because B's flag reads A's parser.
- **Refuted during grounding:** the authoritative seat's risk 2 ("piece 1 cannot be just a fragment
  edit — the validator may reject the grammar") is REFUTED by M3, which executed all five shapes: the
  parser accepts the axis key at the head; only the ` · ` form is refused, and the fragment forbids
  it. The seat's risk 3 (per-command variance needs a renderer PARAMS slot) is REFUTED by design:
  A4 puts the condition in the text and derives the list at close time, so the fragment stays
  identical in all 36 commands.
- **Profile, estimated rather than assumed.** Code diff, tests excluded: the fragment edit ~25
  lines, `scripts/command_feedback_report.py` ~150–250 across four additions (the axis helper and
  its four buckets, `_change_is_none`, `--observer-rank`, `--queue`), and the new command
  source ~100–160 lines of prompt text. Three files, ~275–435 lines, of which only the report is
  executable code. That sits at the edge of the ≤400/≤5 bar rather than comfortably inside it, so
  `Profile: small` is a judgement with a stated margin: if the report's diff runs past ~250 lines in
  execution, Phase B splits rather than the profile being quietly re-read.
- **How this plan converged, stated plainly because it did not end on a quiet round.** Four review
  rounds, confirmed 13 → 10 → 7 → 3, six author-blind seats (Opus on the rule/grammar sections,
  Sonnet on the prose, a single Opus exit seat for each delta). **Round 1 is the only round that
  found a defect in the plan as originally written, and all 13 were fixed.** Rounds 2, 3 and 4 each
  confirmed ONLY defects inside the previous round's fix — `command_run.py` fired the D-252
  scope-growth stop after round 3 (`confirmed/own-fix: 10/10 → 7/7`) and round 4 held the same shape
  (3/3). The flip is taken under that stop, on the original delta's state, with the residue named
  below — not on a quiet exit round. Every factual claim in this plan was re-derived by a seat that
  did not write it: the parser shapes, the rank cut, the lock arithmetic (34 = 7 + 9 + 18), the
  fragment's blast radius, and every `path:line` in the Context Ledger and Constraints Digest.

## Residual unknowns

**Resolved this run:** `ts` uniqueness (M1) · the rank cut (M2) · the parser's tolerance and its one
trap (M3) · the blast radius (M6) · the lock boundary (M7) · whether a new source needs a locked file
(M5).

**Residue of the review itself, routed rather than cut (D-252's stop):** the plan's prose has been
rewritten four times and the last three rounds found only defects in those rewrites, each of falling
severity. Two extension findings a seat raised and I did NOT count, recorded here so the next reader
does not re-derive them: no mail item asks the lock holder to update `tests/test_command_run.py`
alongside the two `command_run.py` edits (their hygiene, not this plan's promise), and step 6 has no
grader proving the four-bucket precedence is TOTAL — that every value falls into exactly one bucket
rather than through all four. Both belong to Phase A's own `/fabrik-review-scoped` pass, where the
code they describe will actually exist.

**Still open, each with its resolution step:**

- **R1 — RESOLVED this run, not deferred.** `scripts/enforcement/check_feedback_duty.py::_audit`
  (`:100-132`) reads each record's `feedback_text` as an OPAQUE string for a human digest and never
  parses the four fields, so an axis-keyed `change:` value passes through it unchanged. Executed,
  read-only. No grader owed. (Noted in passing, fire rate 0, not this plan's to fix: the same
  function's `except OSError` arm at `:106` returns a 2-tuple where every caller unpacks 3 — a latent
  arity bug on a path `Path.glob` does not currently reach.)
- **R2 — RESOLVED by moving the gate, not by deferring the question.** `check_command_corpus.py` is
  invoked only from `scripts/final_gate.py`, never by `assemble_commands.py --check` or the
  `command-corpus-check` hook, so the earlier wording would have exercised it for the first time in
  Phase C — after Phase B had already committed the new source. Phase B step 3 now runs
  `python3 scripts/final_gate.py --json --check` BEFORE the phase commit, which is the executable
  answer whatever `audit()` contains.
- **R3 — the `_USAGE_GRAMMAR` twin drifts the moment Phase A lands** and the fix is lock-owned.
  **Resolution:** Phase A step 3 discloses it in the fragment; Phase C step 4 mails infra the exact
  replacement text.

## Pass Ledger

| Pass | seats · angle | counters | method | pin md5 |
|---|---|---|---|---|
| Pass 1 | opus×1 (rule/grammar sections) + sonnet×1 (header · Intake · phase prose · Self-audit · Residuals), both fresh and non-authoring, `--slices opus=1,sonnet=1` | found: 19, new: 19, confirmed: 13, fixed: 13, unexecuted: 0 | method: re-derivation — the seats executed rather than argued: the five close-parser shapes re-run against the imported `_parse_usage_feedback`, the R3 means and the rank cut recomputed at 162 rows, the 36-of-36 fragment population counted, the 69-file lock census taken, and every `path:line` in the Context Ledger and Constraints Digest opened. The thirteen: the placeholder guard the axis prefix disables, `_is_none`'s head-token read, `INDEX.md` in File Scope, the project-repo fail-open, the 7-of-34 lock denominator, two live-ledger Behavior-Contract Givens, the silent `cost:` truncation, the missing cobra counter-measure, two residuals whose resolution steps did not exist, the cache-exclusion rule absent at its point of use, the `--queue` delimiter, and `sid` mis-enumerated | `ed6b66e0` |
| Pass 2 | opus×1 + sonnet×1 (fresh) · delta over pass 1's fix (173 added / 55 removed) | found: 12, new: 10, confirmed: 10, fixed: 10, unexecuted: 0 | method: re-derivation — every count in the delta re-derived; the cancelling counter-measures found by executing `_is_placeholder` against the de-bracketed text, the `cost:` mechanism falsified by running both arms, the delimiter justification falsified by re-running the shape it cited | `acc1ad0d` |
| Pass 3 | opus×1 (fresh, sole seat) · delta over pass 2's fix (75 added / 31 removed) | found: 9, new: 7, confirmed: 7, fixed: 7, unexecuted: 0 | method: re-derivation — the seat re-derived the lock arithmetic (34 = 7 + 9 + 18), `_GRAMMAR_NOUNS`, `_io_total`'s span and `spec:351`, and found that round 2 had corrected the assertions while leaving the INSTRUCTION (step 5) and the precondition (step 3) saying the opposite | `fc693fd2` |
| Pass 4 | opus×1 (fresh, sole seat), closing · delta over pass 3's fix (44 added / 23 removed) | found: 3, new: 3, confirmed: 3, fixed: 3, unexecuted: 0 | method: re-derivation — the closing pass re-derived every citation round 3 had touched from its primary source rather than re-reading the plan: the `_GRAMMAR_NOUNS` span (1142–1150), `_io_total` (224–247), the spec's axis table row by row (`:345` header, axes at `:347-354`, axis 5 at `:351`), and the four phrases the fragment actually prints — which falsified a claim round 3 had ADDED. It also walked every mail promise to its item and every `_is_none`/`_change_is_none` mention to its section, and reported the step-5-vs-graders class CLOSED | `369c1231` |

The loop closed on the D-252 scope-growth stop, not on a quiet round: `command_run.py` fired it after
Pass 3 (`confirmed/own-fix: 10/10 → 7/7`) and Pass 4 held the same shape (3/3). Pass 1 is the only
pass that found a defect in the plan as originally written.

## Coverage Checklist

| Class | Verdict |
|---|---|
| Parser compatibility (the axis key against the lock-owned close) | FIXED r1+r2 — the head-position rule, the comma separator, and the five executed shapes; r2 corrected the stated mechanism |
| The placeholder guard the axis prefix disables | FIXED r1+r2+r3 — disclosed in Global Constraints, countered by the `placeholder` bucket, and mailed to the lock holder as item (d); r2 caught the first counter-measure cancelling itself, r4 the missing grader |
| Fail-open off the hub (a project repo has no report script) | FIXED r1 — an absolute hub path plus an escape clause, with the divergence from the run-record precedent stated rather than claimed away |
| Field-boundary characters inside a value — BOTH arms: the loud duplicate and the SILENT `cost:` truncation | FIXED r1+r2 — both arms executed and stated; r2 replaced a wrong mechanism with the measured one |
| Cap and truncation behaviour (2000 chars) | CLEAN — `_cap_field("lean: " + "x"*3000)` keeps the key; the live median value is 249 chars |
| Derived-not-pasted command list (the rank cut cannot rot) | CLEAN — `--observer-rank` recomputes from the ledger; the four names were re-derived at 162 rows and still hold |
| Render path + corpus drift for a NEW source | FIXED r2 — the real corpus gate (`final_gate.py --json --check`) moved into Phase B BEFORE its commit, since `assemble_commands.py --check` never reaches `check_command_corpus.py` |
| Lock boundary: nothing written to an owned path | FIXED r1+r2 — `INDEX.md` removed from File Scope, `PLANS.md` added, and the lock enumerated as 34 = 7 out-of-scope + 9 read-only + 18 neither |
| Trailer parses and names its rows | CLEAN — the shape is spelled literally in Phase B with its verification command |
| Doc truth across fragment, command text, INDEX and CHANGELOG | FIXED r3 — four scattered mail promises collapsed into one enumerated item list |
| fail-open on a malformed row | FIXED r1+r2 — four buckets in a fixed precedence, `none` rows excluded, and the shared-helper mirror named rather than discovered |
| cost/quota accounting | CLEAN — the writer seat is priced (15,680 tok, 3.0–8.5% of a close) and the rank that admits a command to it is derived from cost, not from the tally |
| boundary/sentinel | FIXED r1+r2 — head position, the comma, the cap, and the four-bucket precedence |
| behavior-without-a-test | FIXED r2+r3+r4 — graders added for the buckets, `_change_is_none`, the degenerate `--observer-rank` cases, the `--queue` escaping, and the noun list pinned against the fragment's live text |

The rubric this review injected into every seat brief, run on the plan's own changed paths:

```bash
python3 scripts/review_rubric.py --changed commands/_fragments/close-feedback.md commands/_sources/fabrik-command-improve.md scripts/command_feedback_report.py tests/test_command_feedback_report.py
```

```

# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; TOOLING surface)

### core/10-python.md
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

…
```
