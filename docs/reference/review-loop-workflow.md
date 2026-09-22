# The review loop as a workflow — `fabrik-review-loop`

**What:** the D-335 review loop (`/fabrik-review`, `/fabrik-repo-review`) run as a Claude Code workflow script,
`.claude/workflows/fabrik-review-loop.js`, so the seat dispatch, the seats' reports and the execution of every
candidate's check happen outside the lead session's transcript. One `Workflow` call per pass, one ledger back.
Built as chunk 5 of `docs/reference/command-loop-performance.md` § 5.2 (D-346, D-347, D-348). The shape is
D-335 / D-344 unchanged; only where it runs moved.

## Launch (the command source does this; the lead never dispatches seats one by one)

```text
Workflow({ scriptPath: "/opt/fabrik/.claude/workflows/fabrik-review-loop.js", args: { … } })
```

| `args` key | Value |
|---|---|
| `pass` | 1 on the partitioned round; 2, 3 on the passes over the slice ledgers |
| `surface`, `base_sha`, `digest` | the Phase-0 surface, the pinned commit, `git diff HEAD \| md5sum` |
| `pins_dir`, `scratch_dir` | the pinned copies every seat reads; the per-seat scratch root |
| `brief` | the dispatcher's shared text: the 16 failure classes, the D8 lessons, the house rules, the referents |
| `slices` | `[{ name, files: [repo-relative…], priority, ledger?: [{ id, file, line, claim }] }]` — `ledger` on pass ≥ 2 |
| `box_minutes` | the seats' hard time box (default 15) |

The tool returns `async_launched`; the ledger arrives as one result. **Each pass is its own invocation** — never
`resumeFromRunId`: a resumed run re-runs every agent after the first fan-out (anthropics/claude-code #63102,
#67488, #74599, #95076 at 2.1.27x).

## What comes back

```text
{ pass, dropped_slices, dropped_seats,
  slices: [{ name, files, seats: [{ model, files_read, raised, failed, ledger_status, notes }],
             gaps, raised, distinct, overlap, estimate_unseen, candidates: [..], verdicts: [..] }] }
```

- `candidates` — the two finders' union: two DIFFERENT seats citing the same file and class within five lines are one candidate (`also` carries the twin's id, `also_seat` its seat); the same seat's neighbours are never merged. A candidate both raised credits both seats' `confirmed`.
- `verdicts` — one per candidate from the Sonnet verify seat: `confirmed | refuted | recorded` (the seat's schema), or `unverified` written by the script for a seat that returned nothing; the `id` is always the candidate's, never the seat's echo; with
  the command it ran, the output (≤ 1500 chars), the mechanism, a destination when recorded.
- `gaps` — slice files no finder listed in `files_read`; logged, and the slice is UNVERIFIED until read.
- `estimate_unseen` — Chapman's capture-recapture estimate over the two finders' candidate sets; advice for the
  re-dispatch brief, never a gate (`command-loop-performance.md` § 4.9 finding 18).

## What the lead still does (Phase 2 of `/fabrik-review`)

Re-run the command of every `confirmed` verdict on the pinned copy before writing a fix; treat `unverified` and
every `gaps` entry as open; fix; record the round (`command_run.py round --slices …`); launch pass 2 with each
slice's ledger. The closing pass is pass 3 confirming zero (D-339: `done` refuses a failing or vanished slice).

## Fallback

When the `Workflow` tool is absent from the session, the seats go out through the `Agent` tool in one message
with the same briefs and schemas, and the run record's round notes `shape: agent-tool`. Both shapes are the
same loop; the workflow is the one that keeps the lead's turns flat.

## Cobra notes (D-253)

Written beside the script's header; the two that matter most: `files_read` is the finder's own claim, so the
verify stage and the lead's Phase-2 execution are what catch a phantom read; the capture-recapture number is
advice and nothing in the record keys on it.

## Measurement

`tok_msgs` (lead turns), `wall_s`, tokens and the confirmed counts per run in `~/.claude/state/command-feedback.jsonl`;
the KILL for chunk 5 (D-347): two `/fabrik-review` runs at ≤ 15 lead turns with confirmed counts not below the
D-335 runs (14, 21, 15) and the escaped-defect rate not up, else the script is reverted.

## Related surfaces

`.claude/workflows/fabrik-review-loop.js` · `scripts/command_run.py` (`round --slices`, `done`) ·
`scripts/sysadmin/dispatch_headroom.py --slices` · `scripts/review_receipt.py` · `commands/_sources/fabrik-review.md`
