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
Workflow({ scriptPath: "<repo root>/.claude/workflows/fabrik-review-loop.js", args: { … } })
```

`<repo root>` is the session's own checkout — `git rev-parse --show-toplevel` from its working directory, so in a worktree the worktree, never the main checkout. The script and its pass reader `scripts/review_loop_ledger.py` are synced to every project (`scripts/fabrik_synced_manifest.py`), so the path exists in any checkout the sync has reached; elsewhere the § Fallback below applies.

| `args` key | Value |
|---|---|
| `pass` | 1 on the partitioned round; 2, 3 on the passes over the slice ledgers |
| `surface`, `base_sha`, `digest` | the Phase-0 surface, the pinned commit, the pin's identity printed to every seat — the md5 of the pass's `md5sum` manifest of its files, taken as they are pinned: `review_loop_ledger.py pin` writes that manifest as `<pins_dir>/MANIFEST.md5` and prints its md5 as `digest`; where the verb is not on disk the lead builds it by hand (`/fabrik-review-scoped` step 5; `commands/_fragments/subagents-core.md`'s PIN paragraph for `/fabrik-review`) |
| `pins_dir`, `scratch_dir` | the pinned copies every seat reads, each at `<pins_dir>/<repo-relative path>`; the per-seat scratch root. Build the pins with `python3 scripts/review_loop_ledger.py pin --pins-dir <a NEW dir per pass> [--from <tip sha>] [--base <base_sha>] <every slice file>` from the repo root (kaizen 01M4CGJZAX): it writes each file from the working tree, or from the commit with `--from` (a committed range — the working tree may carry WIP; working-tree mode prints `DIRTY <file>` for a pin that is not HEAD's bytes); makes every pin and directory read-only (a writable directory lets `sed -i` rename over a read-only pin); writes `MANIFEST.md5` and `MANIFEST.json`; refuses an absent file, a directory, a symlink, a path outside the repo and a used dir (`--replace` re-pins one on purpose); and prints the `pins_dir` / `pin_manifest` / `digest` / `base_pin_dir` args fragment — pass its `digest` as the launch's `digest`. ONE mechanism: `pin`'s `MANIFEST.md5` IS the per-pass `md5sum` manifest the PIN rule names, and `read --pins` is its `md5sum -c` — `pin` is authoritative; the hand recipe (`cp --parents <file> <pins_dir>/` from the repo root, then `md5sum`, then `md5sum -c` before adjudicating) is the fallback where `pin` is not on disk |
| `pin_manifest` | optional — the `{ path: md5 }` map `pin` printed. A slice file it lacks stops the script before a seat runs; without it the launch logs `UNPINNED LAUNCH` and the ledger reads `pinned: false` |
| `base_pin_dir` | optional — the read-only base tree `pin --base` wrote; the seats' recipe copies it (`cp -r`, then `chmod -R u+w` as its own command — the copy keeps the read-only bits, and an overlay that fails leaves the seat on the base bytes) in place of `git archive`, so a seat runs no git against the live repo |
| `brief` | the dispatcher's shared text: the 16 failure classes, the D8 lessons, the house rules, the referents |
| `slices` | `[{ name, files: [repo-relative…], priority, scope?, models?, agent?, ledger?: [{ id, file, line, claim } \| "<claim>"] }]` — `models` is one to three distinct of `opus`/`sonnet`/`haiku` (default `["sonnet", "haiku"]`, D-344's file-slice pair; a section slice names one seat — `["opus"]` on the rule/grammar sections, `["sonnet"]` on the rest, D-212/D-218; `/fabrik-execute-plan` adds its per-round Opus finder as the riskiest slice's third); `agent` is `fabrik-reviewer` (default) or `fabrik-researcher` for a cited-fact slice, and seats that slice's refuter too; `scope` names the sections of `files` the slice owns; an unknown model or agent, or a repeated or fourth finder, stops the script before a seat runs. `ledger` on pass ≥ 2 (a string row gets the id `<slice>-L<n>`; any other row shape stops the script before a seat runs); each `claim` states the DEFECT as raised — `STILL_TRUE` the defect persists · `NOW_FALSE` it is gone (the fix holds) · `NEW` a defect the fix introduced |
| `box_minutes` | the seats' hard time box (default 15) |

The tool returns `async_launched`; the ledger arrives as one result — the lead waits for it with ONE bounded in-turn poll per pass, and when the result is truncated reads the run's `journal.jsonl` (one `result` row per completed agent), never the escaped task-output copy. **Each pass is its own invocation** — never
`resumeFromRunId`: a resumed run re-runs every agent after the first fan-out (anthropics/claude-code #63102,
#67488, #74599, #95076 at 2.1.27x).

## What comes back

```text
{ pass, closable, pinned, dropped_slices, dropped_seats,
  slices: [{ name, files, seats: [{ model, files_read, raised, confirmed, failed, ledger_status, notes }],
             gaps, raised, distinct, overlap, estimate_unseen, candidates: [..], verdicts: [..], closable, open: [..] }] }
```

- `seats[].files_read` — a COUNT here (the number of files the seat listed), not the list it returned; the list is in the seat's own result row (`journal.jsonl`), which `review_loop_ledger.py read` keeps.
- `candidates` — the two finders' union: two DIFFERENT seats citing the same file and class within five lines are one candidate (`also` carries the twin's id, `also_seat` its seat, and `also_seats` every seat that raised it — the list the per-seat `confirmed` credit is computed from); the same seat's neighbours are never merged. A candidate both raised credits both seats' `confirmed`.
- `verdicts` — one per candidate from the slice's Sonnet refuter (`effort: high`; the finders run at `medium`): `confirmed | refuted | recorded | unverified`; the script writes `unverified` for a candidate the refuter never answered and for a `refuted` with no command or output (refutation needs counter-evidence); a `refuted` whose command is a placeholder (`n/a`, `none`, `-`) or whose output is empty counts as none, and two rows for one id that disagree are `unverified`; the `id` is always the candidate's — the union suffixes a reused id (`#2`) before the refuter sees it — never the seat's echo; with
  the command it ran, the output (≤ 1500 chars), the mechanism, a destination when recorded.
- `gaps` — slice files no finder listed in `files_read`; logged, and the slice is UNVERIFIED until read. An entry
  counts for a slice file `f` when, after stripping one `<pins_dir>/` or `<scratch_dir>/<seat>/arch/` prefix (and
  backticks, `file://`, `./`), it is `f` or begins with `f` followed by whitespace, `:`, `#`, `(`, `[`, `,` or `—` —
  so `f:120`, `f#L120` and `f (pinned copy at …)` count. A trailing slash on either dir is ignored, and an unset or
  empty dir strips nothing. A path under any other root (the live checkout) or a sibling of the same
  name never does (`readsFile` in the script).
- `failed` / `dropped_seats` — a finder seat is failed when it returns nothing or its `files_read` names none of the slice's files: it reviewed nothing, and its partner's reads would otherwise hide it from the gap check (01M4C00TSS — a seat answered a relayed operator turn instead). A failed seat's `ledger_status` re-verifies no claim; `dropped_seats` counts them; `review_loop_ledger.py read` flags only the narrower case, a returned finder whose `files_read` names no file at all (`READ 0 FILES`): it has no slice list, so a seat that listed only an off-slice file is failed here and not flagged there — the workflow ledger's `seats[].failed` and `open` are the authority.
- `closable` / `open` — a slice may close only with no gap, no failed seat, no `confirmed` or `unverified` verdict and, on a later pass, every ledger claim reported by a seat; `open` names each reason. It is a floor for "may close", never a stop signal: ≤ 3 passes is a target, not a cap (D-355).
- `estimate_unseen` — Chapman's capture-recapture estimate over the two finders' candidate sets (`null` unless the slice has exactly two); advice for the
  re-dispatch brief, never a gate (`command-loop-performance.md` § 4.9 finding 18).

## What the lead still does (Phase 2 of `/fabrik-review`)

Read the pass into a file — `python3 scripts/review_loop_ledger.py read <run transcript dir> --out
<scratch>/pass-<n>.json --box <box_minutes> --pins <pins_dir>` — BEFORE any fix (`--pins` re-hashes the manifest into the pass file's `pins`: a changed pin is `PIN MOVED` — the pass is void for the slices that read it, the read exits 3 and names every seat whose transcript span, widened by two minutes, covers the pin's mtime; re-pin into a NEW dir and re-launch those slices; a working-tree pin whose live file no longer matches is `LIVE MOVED`, informational — re-verify its candidates against the current tree, as `/fabrik-review-scoped` step 5 does; a dir with no manifest reads `UNPINNED`, and a read without `--pins` prints `pins: NOT CHECKED`) — which prints every seat's minutes and tokens — from the seat's own transcript, counted once per message id — (`OVER BOX`: nothing in the Workflow
API times a seat out; one refuter ran 59 minutes against a 12-minute box) and `NO RESULT` for a seat that returned
nothing. Re-run the command of every `confirmed` verdict on the pinned copy before writing a fix; treat `unverified`
and every `gaps` entry as open; fix; record the round (`command_run.py round --slices …`) and name its stop and fix
size in the receipt's Pass row; launch the next pass with `review_loop_ledger.py next <pass file> --ids <confirmed
ids>` as its slices' ledgers, and restate every round-1 slice in that pass's `round --slices`, a verified one at its last `<verified>/<claims>`. The review closes on the pass that confirms zero, whatever its number — ≤ 3 passes is
a target, never a cap (D-355; D-339: `done` refuses a failing or vanished slice). `dispatch_headroom.py` refuses
while `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` is set, because that variable puts every seat on one model (D-357).

## Fallback

When the `Workflow` tool is absent from the session, or cannot load the script (a repo or checkout the sync has not reached, such as fabrik-lib), the seats go out through the `Agent` tool in one message
with the same briefs and schemas, and the receipt's Pass row (or, with no receipt, the close's `--evidence`) names `shape: agent-tool`. Both shapes are the
same loop; the workflow is the one that keeps the lead's turns flat.

## Cobra notes (D-253)

Written beside the script's header; the two that matter most: `files_read` is the finder's own claim, so the
verify stage and the lead's Phase-2 execution are what catch a phantom read; the capture-recapture number is
advice and nothing in the record keys on it. The pin manifest is optional while the launchers build their pins by hand, so the cheapest launch skips `pin`: the workflow logs `UNPINNED LAUNCH` and returns `pinned: false`, and the pass reader — the path the lead actually reads — prints `pins: NOT CHECKED` or `UNPINNED`; a strict-xfail grader (`test_every_launcher_passes_a_pin_manifest`) turns red the day every launcher passes the manifest, which forces making it mandatory. The pins are checked at the two points the lead's tools can see, before dispatch and after the pass; a per-seat hash would need an agent after every seat and is not built — PIN MOVED attributes by mtime and seat span instead. The `/fabrik-review` Leak check (git status and the stash list before and after each pass) stays the authority for the live tree outside the slice files.

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
