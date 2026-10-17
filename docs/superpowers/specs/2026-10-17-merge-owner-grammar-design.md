# Merge-owner row grammar — the exact label, bold allowed (design)

Status: CONVERGED
Size: small (≈30 code lines across `scripts/decisions.py`, `scripts/docs_updater.py` and `.claude/hooks/session_orient.py`, 3 code files)
Profile: delta
Work item: W-5d3ed438 · found by the wave-1 review of plan `2026-09-30-plan-1-merge-request-loop`, pass 3 · `/fabrik-task` refused it on `consumers=external` (refusal LR-9f99841a: the fleet-synced hook reads every repo's own ledger)

## Personas

- **PRIMARY — the coordinator (merge owner), whose name the readers must return.** The coordinator's own words when it
  assigned this item: *"decisions.py is on the hub's records path, so check `--merge-owner` still reads coordinator after
  your change"*. Its loop, steps counted (step budget **3**): (1) a session or script asks who the merge owner is
  (`decisions.py --merge-owner .`, the SessionStart hook's ORIENT line, `docs_updater.py`'s PLANS marker); (2) the reader
  scans the ledger's what-cells for declaration rows; (3) the highest-D-id declaration answers. This change touches
  step 2 only and adds no step.
- **The author of a ledger row** — any agent or the operator writing a D-row by hand. They write prose that may open
  with the words "Merge owner:" without meaning to declare one, or bold the label as `**MERGE OWNER:** x` the way
  the ledger bolds other labels.
- **Automated consumers** (each named as the holder of its duty):
  - `scripts/decisions.py::_merge_owner` — the CLI reader every other caller resolves through (`merge_request.py`, the
    Stop hook's merge cause);
  - `scripts/docs_updater.py` — the PLANS `<!-- Merge owner: … -->` marker writer and `--adopt`'s row writer (it writes
    `MERGE OWNER: <name> — …` in upper case, `scripts/docs_updater.py:2540`);
  - `.claude/hooks/session_orient.py` — the fleet-synced SessionStart hook, which cannot import either script and keeps
    its own copy; it reads each of the ~46 repos' own ledger;
  - `tests/test_session_orient_hook.py` — the parity grader holding the three copies identical.

Every item below traces to one of these: the bold label to the row author, the case rule to the coordinator and the
row author, the parity pins to the three readers.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "a bold-wrapped label `**MERGE OWNER:** coordinator` never matches" (W-5d3ed438) | IN | § The delta D1 |
| I2 | "a bare what-cell opening with prose `Merge owner: rotated weekly` reads `rotated` as the owner" (W-5d3ed438) | IN | § The delta D2 |
| I3 | "in all three copies, with a shared-fixture parity test" (W-5d3ed438) | IN | § The delta D3 — the shared fixture list `_OWNER_CASES` already exists; it gains rows |
| I4 | "check `--merge-owner` still reads coordinator after your change" (coordinator) | IN | § Validation V4 |

## Goal

A what-cell declares a merge owner only when it opens — optionally after a `supersedes D-NNN` clause — with the exact
upper-case label `MERGE OWNER:`, whether or not that label is bold (`**MERGE OWNER:**` or `**MERGE OWNER**:`); every
other spelling of the label is prose. A declaring row's first token after the label is its owner, whatever follows it
— the rule decides WHICH rows declare, never how much of the cell is a name. All three readers apply the same rule, and
every ledger on the box resolves to the owner it resolves to today.

## What exists today (grounded, read at 83bc96588)

- `scripts/decisions.py:60-69` — `_SUPERSEDES_PREFIX`, `MERGE_OWNER_RE` and `_UNDECLARED_RE`, all compiled `re.I`. The
  prefix's lookahead already requires the exact upper-case phrase after a supersedes clause (`(?=(?-i:MERGE OWNER:))`);
  the phrase itself is matched case-insensitively, so a bare row has no such requirement.
- `scripts/docs_updater.py:1231-1240` — the same three, byte for byte.
- `.claude/hooks/session_orient.py:227-244` — the same, plus a `(?!UNDECLARED…)` lookahead inside the owner regex (the
  one deliberate divergence, pinned by the parity test).
- `tests/test_session_orient_hook.py:879-920` — the literal-pattern parity pins; `:1271-1306` — `_OWNER_CASES`, the
  shared fixture list run through all three readers by `test_the_three_owner_readers_pick_the_highest_id_row`. One
  case pins today's gap on purpose: `("bare-row-lowercase-phrase", _row2("merge owner: beta") + _A1, "beta")`, commented
  "a bare row keeps its case-insensitivity: nothing that parsed before stops parsing" (added by W-076ff4a9,
  `5412871e0`; no D-row rules it).

Executed this session (`owner_probe.py` in the run folder, the live `decisions.py` grammar):

```
'**MERGE OWNER:** coordinator — bold-wrapped label'      owner=None
'**MERGE OWNER: coordinator** — bold-wrapped whole'      owner='coordinator'
'Merge owner: rotated weekly between agents'             owner='rotated'
'merge owner: agent-1'                                   owner='agent-1'
'**Supersedes D-001.** Merge owner: rotated weekly'      owner=None
```

Census (`owner_census.py`, every `/opt/*/docs/DECISIONS.md`): `ledgers: 52 · rows mentioning a merge owner: 50` —
9 open with the upper-case label, 4 open with a supersedes prefix, 37 mention it mid-prose, **0 open with any other
case, 0 bold-wrap the label**. `python3 scripts/decisions.py --merge-owner .` prints `coordinator`, rc 0.

## External dependencies

This change adds no external facts: it is a regex over the repo's own markdown ledger, and Python's scoped inline
flag `(?-i:…)` is standard library already in use in the same pattern. The approach research is below.

## Chosen approach — A: the exact label on every row, bold allowed (judge panel 3/3)

Field practice, fetched 2026-10-17. Three research seats used WebFetch; the research MCPs failed together (Brave 422,
Exa 403, Firecrawl timeout — the egress pattern, not keys), so the lead re-fetched every quoted source with `curl`
(HTTP 200) and matched the quote in the raw body (`rawcheck.py`, `rawcheck2.py` in the run folder); a source not
re-fetched is marked *summariser-read*.

- **Key case.** git trailers: "The <key-alias> must be a prefix of the full <key> string, although case sensitivity
  does not matter." (https://git-scm.com/docs/git-interpret-trailers, found by WebSearch); `%(trailers:key=…)`:
  "Matching is done case-insensitively and trailing colon is optional." (https://git-scm.com/docs/pretty-formats).
  HTTP: "Field names are case-insensitive and ought to be registered within the …"
  (https://www.rfc-editor.org/rfc/rfc9110.txt §5.1); ABNF: "ABNF strings are case insensitive and the character set
  for these strings is US-ASCII." (https://www.rfc-editor.org/rfc/rfc5234.txt §2.3).
- **The deliberate-uppercase precedent.** ruff TD006: "Checks that a "TODO" tag is properly capitalized"
  (https://raw.githubusercontent.com/astral-sh/ruff/main/crates/ruff_linter/src/rules/flake8_todos/rules/todos.rs) —
  it detects the tag in any case and flags the lowercase one.
- **Decision-log tools.** adr-tools finds the status by the exact, case-sensitive heading `/^## Status/,/^#/ && !/^## Status/ {`
  (https://raw.githubusercontent.com/npryce/adr-tools/master/src/_adr_status); log4brains matches its key
  case-insensitively, ``new RegExp(`^(\\s*${key}\\s*:\\s*)(.*)$`, "i")``, over the RENDERED text, so a bold label
  passes only through rendering
  (https://raw.githubusercontent.com/thomvaill/log4brains/master/packages/core/src/adr/domain/MarkdownBody.ts); MADR
  moved the status to YAML front matter because "tools can handle it more easily"
  (https://adr.github.io/madr/decisions/0013-use-yaml-front-matter-for-meta-data.html, summariser-read).
- **Bold.** CommonMark 0.31.2 (https://spec.commonmark.org/0.31.2/, summariser-read, rules 5, 7, 10 and the flanking
  definitions): both `**MERGE OWNER:** x` and `**MERGE OWNER: x**` are valid strong emphasis; `**MERGE OWNER:**x`
  (no space after the closer) is not. GFM table cells parse inlines the same way (https://github.github.com/gfm/).

**Why A against that practice.** The field matches a `key:` case-insensitively because there the key is the only
signal and every line in that position IS a field. Here it is not: a what-cell is free prose that sometimes opens with
a declaration, and the census shows the label is always written upper case when it declares (10 of 10) while the
lower-case words "Merge owner:" are exactly what prose would open with. adr-tools takes the same exact-match stance;
the ledger's own supersedes clause already requires it (`(?=(?-i:MERGE OWNER:))`, `scripts/decisions.py:60`). A makes
that one rule apply to every row. The bold allowance is exactly one optional `**` on each side of the colon
(`(?-i:MERGE OWNER)(?:\*\*)?:(?:\*\*)?\s*`), so both ways this ledger bolds a label read — the colon inside the bold (7 of the hub
ledger's bold labels) and outside it (1, `**Repos**:` in D-738; no merge-owner row is bold today) — and no run of asterisks does: `\**` would also newly accept `MERGE OWNER:*a*` and `MERGE OWNER:***a` (found by the plan's reader census,
executed in `bold_probe.py`). It accepts `**MERGE OWNER:**x` too, which CommonMark does not render as bold — harmless:
the reader reads text, not rendering, and the name is still the next token.

The panel (three Sonnet judges, approaches in alphabetical order with no recommendation; brief `panel-brief.md` in the
run folder) ranked A first 3 of 3: A > C > B > D, A > D > B > C, and A first with B, C, D unordered. Judge 3's named
cost of A — a hand-typed mixed-case declaration is ignored without a word — is carried to § Lifecycle as the
trigger for D.

## Constraints Digest

- The hook is fleet-synced and standalone: it cannot import the grammar, so the copy stays and the parity test pins it.
- Ledger rows are immutable (`docs/DECISIONS.md` law): no existing row may be rewritten to fit a new grammar, so the
  grammar must read every existing declaration exactly as today (census above).
- No new dependency; no change to `_ADOPT_NAME_RE` or the capture group.

## The delta

- **D1 — bold label.** Allow the closing `**` of a bold label once, before or after the colon:
  `(?-i:MERGE OWNER)(?:\*\*)?:(?:\*\*)?\s*` in `MERGE_OWNER_RE`, `_UNDECLARED_RE` and the hook's `_MERGE_OWNER_RE` — in the hook the
  `(?!UNDECLARED…)` guard stays AFTER the new token, or the owner regex alone would match `MERGE OWNER:** UNDECLARED`
  as a name. The reader hides that order: `_owner_in` tests `_UNDECLARED_RE` first (`.claude/hooks/session_orient.py:327`),
  so only the literal parity pin can see a misplaced guard. Touchpoints `scripts/decisions.py:62`, `:67`,
  `scripts/docs_updater.py:1233`, `:1238`, `.claude/hooks/session_orient.py:231`, `:242`.
- **D2 — exact label on every row.** Wrap the words in each of those six patterns as `(?-i:MERGE OWNER)`, the
  optional `**` and the colon outside the group (D1's token), so the
  phrase is upper-case-exact whether or not a supersedes clause precedes it; the clause itself and the `UNDECLARED`
  token keep `re.I`. `_SUPERSEDES_PREFIX`'s lookahead drops its colon — `(?=(?-i:MERGE OWNER))` — so a supersedes
  clause can precede the colon-outside bold label; the phrase that follows still demands the colon. The un-adoption row
  obeys the same rule: `Merge owner: UNDECLARED` un-adopts today and becomes prose (0 such rows in 52 ledgers).
- **D3 — graders.** In `_OWNER_CASES` (`tests/test_session_orient_hook.py:1271-1306`) the `bare-row-lowercase-phrase`
  case flips to the earlier owner (`alpha`), and new rows cover a bare `Merge owner: rotated weekly` (→ `alpha`),
  `**MERGE OWNER:** beta` and `**MERGE OWNER**: beta` (→ `beta`), `**MERGE OWNER:** UNDECLARED` (→ undeclared),
  `Merge owner: UNDECLARED` (→ `alpha`, its comment naming the cost § Lifecycle Failure states) and
  `**MERGE OWNER:** rotated weekly` (→ `rotated`, pinning the first-token limit § Goal states); `_SUPERSEDES_SPELLINGS`
  (`:1256-1266`) gains `supersedes D-001: **MERGE OWNER:** beta`, `**Supersedes D-001.** **MERGE OWNER:** beta` and
  `supersedes D-001: **MERGE OWNER**: beta`. In the literal parity test (`:879-920`) the `prefix` (`:896`), `phrase`
  (`:897`), `uses` (`:903`) and `undeclared` (`:912`) literals change to the new text. The three comment blocks above the patterns, and the
  hook's `:211` ("Case-insensitive because the phrase match is"), say the rule once each.
- **D4 — docs.** `docs/reference/multi-agent-operating-model.md:122-126` and `docs/workstation/hooks-index.md:16` (the
  two prose statements of the rule, census of 63 lines in the plan's Evidence) state it: the label is always the exact
  `MERGE OWNER:`, bold allowed (read by the hub's own readers at once, by a project's synced copies after its next sync).

## Contract deltas

None. No data contract or UI design; the ledger format is unchanged and every existing declaration still reads.

## Lifecycle

- **Adoption:** `decisions.py` is hub-side, and three fleet-synced readers call it by its hub-absolute path
  (`scripts/work.py`, `scripts/merge_request.py`, `.claude/hooks/final_gate_stop.py`), so they switch at merge;
  `docs_updater.py` and `session_orient.py` are fleet-synced and switch at the next governance sync. Between the two,
  a project's PLANS header and session-start line could name a different owner than `merge_request.py` — only for a
  bold or mixed-case declaring row. The census holds none (0 of 52), but D4's sentence invites the bold form, so the
  window is real until the next governance sync reaches a project: the D4 text says the bold label is read hub-side
  at once and in a project after its next sync. (`scripts/check_commit_trailers.py` also runs `decisions.py`, its own
  repo's, which only the hub has, so it switches at merge too.) No repo has to act.
- **Growth:** the grammar reads one cell per row; a ledger of any size costs the same per row. The trigger to revisit
  is a row opening with the label in another case appearing in the census (re-run
  `/opt/fabrik/.tmp/runs/4e90716e-696b-4ddf-90ab-70e30f51f294/fabrik-spec-2026-10-17T16-09-32-0330/owner_census.py`;
  today 0 of 52 ledgers): one such row revives approach D, the warning, because that row is an author who meant to declare and was
  ignored.
- **Failure:** a row in another case now reads as prose, so the reader falls back to the next-highest declaration —
  the same fallback a mid-prose mention already gets, which the parity test pins. For an un-adoption row that means
  the opposite of what its author meant: `Merge owner: UNDECLARED` above `MERGE OWNER: alpha` names `alpha` again
  instead of leaving the repo undeclared; the census holds no such row, and the § Growth trigger covers it.
- **Retirement:** when the owner moves out of the ledger prose into a structured field, all three copies go together.

## Cost

About 30 changed lines in three code files plus test rows; one `/fabrik-plan-review` small loop.

## Validation

- V1 — `**MERGE OWNER:** beta` and `**MERGE OWNER**: beta`, bare or after a supersedes clause, above
  `MERGE OWNER: alpha` resolve to `beta` in all three readers (red today).
- V2 — a higher-id bare `Merge owner: rotated weekly` row leaves `alpha` standing in all three readers (red today).
- V3 — `**MERGE OWNER:** UNDECLARED` is an un-adoption in all three readers (red today).
- V4 — `python3 scripts/decisions.py --merge-owner .` prints `coordinator`, and the base and edited readers, run back
  to back over every `/opt/*/docs/DECISIONS.md`, give the same owner and exit code for each ledger (52 ledgers: 9
  owners, 43 undeclared at authoring), while a two-row control ledger separates them (base `alpha`, edited `beta`).
- V5 — every existing `_OWNER_CASES` row except the flipped one keeps its answer; the literal parity pins pass.

## Decisions taken

- The label is case-exact everywhere (D2), not only after a supersedes clause: the clause's rule and the bare row's rule
  become one rule (judge panel 3/3; D-row minted with this spec).
- A bold label is accepted (D1) with its colon inside or outside the bold, including the unrendered
  `**MERGE OWNER:**x` (design panel, fable concern 1).
- The first token after an upper-case label is the owner, whatever follows: `**MERGE OWNER:** rotated weekly` reads
  `rotated`, as `MERGE OWNER: rotated weekly` already does today. Closing that class would need approach B's
  terminator, rejected below; the case is pinned so the limit is visible (design panel, opus concern 2).
- No warning for a mixed-case opener until the census finds one (D rejected, § Lifecycle trigger).
- Other bold spellings stay prose, today and after: `***MERGE OWNER:*** x`, `__MERGE OWNER:__ x`,
  `MERGE OWNER:\t** x` (whitespace before the `**`) and a bold name `**MERGE OWNER:** **x**`; none is used (census).
- Cobra (D-253): the cheapest way to satisfy "the label is case-exact" without the outcome is to write prose in upper
  case; that is what a declaration is, so the measure and the outcome coincide.

## Rejected alternatives

- **B — keep the case-insensitive phrase, require a terminator after the name** (end of cell, ` — `, `,`, `;`,
  `.`+space). Rejected: a heuristic (`rotated.` and `rotated, weekly` still read as owners) and a fourth shared
  grammar element to keep byte-identical in the fleet-synced copy; it keeps `merge owner: beta` working, which no
  ledger uses (0 of 52).
- **C — bold label only, document the case rule.** Rejected: leaves the `rotated` misread, which the same lines fix.
- **D — A plus a stderr warning for a mixed-case opener** (the ruff TD006 shape). Rejected for now: its measured fire
  rate is 0 in 52 ledgers, the hook and the writer cannot carry it (the readers would diverge), and `--merge-owner` is
  a query no gate calls at authoring time (`decisions.py:693`, `:731`), so the author who needs it rarely sees it.
  Revived by the § Lifecycle trigger.
- **A structured owner field** (front matter or a dedicated column, MADR's shape). Rejected: the ledger is immutable,
  so every existing declaration would need a new row, across ~46 repos, for two gaps a regex closes.
- **Keep the grammar case-insensitive and fix only the hub's test pin.** Not an option: the pin documents the gap,
  it does not cause it.

## fabrik-lib verdict

| Capability | Verdict | Why |
|---|---|---|
| merge-owner row grammar | BUILD (edit in place) | No fabrik-lib module parses the hub ledger; the grammar lives in three hub files already. Not a candidate: hub-specific. |

## Shape / infra implications

None — no service, no `shape:` flag, no scaffold type.

## Documentation landing sites

- `docs/reference/multi-agent-operating-model.md` § who is agent-1 (D4) — the rule's reader-facing statement.
- The comment block above each copy of the pattern — the rule beside the code.
- `CHANGELOG.md` `[Unreleased]` and a D-row for the case decision.

## Open / blocking unknowns

None open.
