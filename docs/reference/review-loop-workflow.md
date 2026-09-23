# The review loop as a workflow — `fabrik-review-loop`

**What:** the D-335 review loop (`/fabrik-review`, `/fabrik-repo-review` by file; `/fabrik-spec-review`, `/fabrik-plan-review` by section, chunk 6; `/fabrik-review-scoped` and every review-shaped units fan-out, one slice per unit, chunk 6b) run as a Claude Code workflow script,
`.claude/workflows/fabrik-review-loop.js`, so the seat dispatch, the seats' reports and the execution of every
candidate's check happen outside the lead session's transcript — one fresh refuter per slice executes them. One `Workflow` call per pass, one ledger back.
Built as chunk 5 of `docs/reference/command-loop-performance.md` § 5.2 (D-346, D-347, D-348). The shape is
D-335 / D-344 unchanged; only where it runs moved. Row 5b (D-355) replaced one verify seat per candidate with one
refuter per slice: every candidate is still executed (D-330's "every claim executed" holds), the seat per candidate
mostly ran one grep (§ 4.9 findings 27, 41), and the refuter's box grows with its candidates (3 minutes each, never
below `box_minutes`). The reviewer agent carries `experimental.cacheTtl: 1h`, which Claude Code ignores while a
subscription is spending usage credits (finding 41).

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
| `slices` | `[{ name, files: [repo-relative…], priority, scope?, models?, agent?, ledger?: [{ id, file, line, claim } \| "<claim>"] }]` — `models` is one to three distinct of `opus`/`sonnet`/`haiku` (default `["sonnet", "haiku"]`, D-344's file-slice pair; a section slice names one seat — `["opus"]` on the rule/grammar sections, `["sonnet"]` on the rest, D-212/D-218; `/fabrik-execute-plan` adds its per-round Opus finder as the riskiest slice's third); `agent` is `fabrik-reviewer` (default) or `fabrik-researcher` for a cited-fact slice, and seats that slice's refuter too; `scope` names the sections of `files` the slice owns; an unknown model or agent, or a repeated or fourth finder, stops the script before a seat runs. `ledger` on pass ≥ 2 (a string row gets the id `<slice>-L<n>`; any other row shape stops the script before a seat runs); each `claim` states the DEFECT as raised — `STILL_TRUE` the defect persists · `NOW_FALSE` it is gone (the fix holds) · `NEW` a defect the fix introduced |
| `box_minutes` | the seats' hard time box (default 15) |

The tool returns `async_launched`; the ledger arrives as one result — the lead waits for it with ONE bounded in-turn poll per pass, and when the result is truncated reads the run's `journal.jsonl` (one `result` row per completed agent), never the escaped task-output copy. **Each pass is its own invocation** — never
`resumeFromRunId`: a resumed run re-runs every agent after the first fan-out (anthropics/claude-code #63102,
#67488, #74599, #95076 at 2.1.27x).

## What comes back

```text
{ pass, closable, dropped_slices, dropped_seats,
  slices: [{ name, files, seats: [{ model, files_read, raised, confirmed, failed, ledger_status, notes }],
             gaps, raised, distinct, overlap, estimate_unseen, candidates: [..], verdicts: [..], closable, open: [..] }] }
```

- `candidates` — the two finders' union: two DIFFERENT seats citing the same file and class within five lines are one candidate (`also` carries the twin's id, `also_seat` its seat); the same seat's neighbours are never merged. A candidate both raised credits both seats' `confirmed`.
- `verdicts` — one per candidate from the slice's Sonnet refuter (`effort: high`; the finders run at `medium`): `confirmed | refuted | recorded | unverified`; the script writes `unverified` for a candidate the refuter never answered and for a `refuted` with no command or output (refutation needs counter-evidence); a `refuted` whose command is a placeholder (`n/a`, `none`, `-`) or whose output is empty counts as none, and two rows for one id that disagree are `unverified`; the `id` is always the candidate's — the union suffixes a reused id (`#2`) before the refuter sees it — never the seat's echo; with
  the command it ran, the output (≤ 1500 chars), the mechanism, a destination when recorded.
- `gaps` — slice files no finder listed in `files_read`; logged, and the slice is UNVERIFIED until read.
- `closable` / `open` — a slice may close only with no gap, no failed seat, no `confirmed` or `unverified` verdict and, on a later pass, every ledger claim reported by a seat; `open` names each reason. It is a floor for "may close", never a stop signal: ≤ 3 passes is a target, not a cap (D-355).
- `estimate_unseen` — Chapman's capture-recapture estimate over the two finders' candidate sets (`null` unless the slice has exactly two); advice for the
  re-dispatch brief, never a gate (`command-loop-performance.md` § 4.9 finding 18).

## What the lead still does (Phase 2 of `/fabrik-review`)

Read the pass into a file — `python3 scripts/review_loop_ledger.py read <run transcript dir> --out
<scratch>/pass-<n>.json --box <box_minutes>` — which prints every seat's minutes and tokens — from the seat's own transcript, counted once per message id — (`OVER BOX`: nothing in the Workflow
API times a seat out; one refuter ran 59 minutes against a 12-minute box) and `NO RESULT` for a seat that returned
nothing. Re-run the command of every `confirmed` verdict on the pinned copy before writing a fix; treat `unverified`
and every `gaps` entry as open; fix; record the round (`command_run.py round --slices …`) and name its stop and fix
size in the receipt's Pass row; launch the next pass with `review_loop_ledger.py next <pass file> --ids <confirmed
ids>` as its slices' ledgers. The review closes on the pass that confirms zero, whatever its number — ≤ 3 passes is
a target, never a cap (D-355; D-339: `done` refuses a failing or vanished slice). `dispatch_headroom.py` refuses
while `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` is set, because that variable puts every seat on one model (D-357).

## Fallback

When the `Workflow` tool is absent from the session, the seats go out through the `Agent` tool in one message
with the same briefs and schemas, and the receipt's Pass row (or, with no receipt, the close's `--evidence`) names `shape: agent-tool`. Both shapes are the
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

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/review_loop_ledger.py`
<!-- END related-scripts -->
