# Token waste — DEFINE (D-1118)

The fleet's token burn is run as a Lean Six Sigma process (D-1118): this page DEFINEs the waste
categories; `scripts/sysadmin/kaizen_waste.py` MEASUREs them daily; `scripts/sysadmin/kaizen_digest.py`
puts them on control charts; kaizen ANALYSEs, IMPROVEs and CONTROLs (one item per out-of-control
series, measured before and after; D-1119 puts the loop in kaizen's charter).

## The six series

All are per LOCAL day. Ledger rows are the day's TOP-LEVEL closes in `~/.claude/state/command-feedback.jsonl`; a row
carrying `parent` is a nested run whose window overlaps its parent's, so it is excluded and counted. A day before a
source first recorded its field publishes nothing, never a 0, and so does a day whose source cannot vouch for it
(a rotation transcript not found, a ref not fetched past the day); the daily run retries the two days before it.

| Series | Formula | Unit | Source, first day | Counter pair | Cheapest way to game it | Cannot see |
|---|---|---|---|---|---|---|
| `waste_context_per_call` | Σ tok_cache_read / Σ tok_msgs over closes with tok_msgs > 0 | tokens per API call | feedback ledger, 2026-09-07 | rotation_rebuild | rotate sessions constantly | which part of the context (CLAUDE.md, hooks, memory, the conversation) |
| `waste_rotation_rebuild` | Σ (input + cache_creation + cache_read) of each rotated session's first assistant message (a rotation is a new session id bound to a name already bound before; a name's first binding is a birth); any rotation transcript unfound → the day is unmeasured | tokens per day | agent-identity.jsonl + transcripts, 2026-09-24 | context_per_call | never rotate | compactions (same session id) and sessions bound to no name |
| `waste_seat_share` | 100 × Σ four tok_seat_* / Σ lead + seat tokens | % | feedback ledger, 2026-09-08 | red_master_rework | skip review seats | whether a seat found anything |
| `waste_red_master_rework` | non-merge commits whose first-parent commit on `origin/master` is dated that day by committer time (a merge brings in what it introduced, on the merge's date; the window is half-open at local midnight), with a fix-shaped subject (`fix`, `test`, `revert`) and a word-bounded red-master phrase; unmeasured unless the ref was refreshed after the day ended (its tip, its newest reflog entry, or a FETCH_HEAD that names its branch) | commits per day | `git log`, all history | seat_share | stop writing "red master" in fix messages | a red master fixed silently; a fast-forwarded branch keeps its own commit dates; the by-agent cut is who PAID, not who broke it |
| `waste_wall_rate` | 100 × closes blocked at a quota wall (`wall == quota`) / top-level closes; detail: hours waited, from resumed closes whose `resumed_from.reason` names a quota wall | % | feedback ledger, 2026-10-13 | output_per_call | split work into more, smaller closes | an operator pause near a wall (its own reason is not in the ledger) |
| `waste_output_per_call` | Σ tok_out / Σ tok_msgs over closes with tok_msgs > 0 | tokens per API call | feedback ledger, 2026-09-07 | wall_rate | terse answers that force extra turns | whether the output was needed |

Each series also writes a per-agent and per-command breakdown (`~/.claude/state/kaizen/waste-breakdown@v1.jsonl`;
rotation and red-master by agent only). The four ratio series' breakdown carries the day's top-level close count
(`by: total, key: closes`), which the judging floor reads; rotation and red-master carry their rotation and
arrival counts instead.

## Control rules

- **Chart:** XmR (individuals and moving range): centre = mean, σ = MR̄ / 1.128, UCL = centre + 3σ, LCL = max(0, centre − 3σ). `waste_red_master_rework` is a rare event count, so it uses a c-chart, σ = √c̄. A baseline with no width (σ = 0: every point equal, or a zero count) treats any departure as a shift.
- **Frozen Phase-I limits:** the baseline is the first 14 judged points of the series, never a rolling window. A rolling window absorbs a sustained regression within 14 days, which is exactly what CONTROL must keep visible.
- **Judged:** a ratio series' day is judged only with at least 20 top-level closes; below that it is plotted, never judged.
- **Out of control:** a point beyond a limit, or 8 consecutive judged points on one side of the centre (the c-chart above it only: a rare count's quiet days sit below its centre by nature). The digest line names the rule, the limits, the baseline days and the top three breakdown keys.
- **Direction:** every series is lower-is-better. An upward signal prints `OUT OF CONTROL ↑` and is what kaizen opens an item on; a downward one prints `IMPROVED ↓ … — re-baseline once it holds`.
- **Re-baseline:** after kaizen closes an improvement, it re-baselines from the first day of the new process:
  `kaizen_waste.py --rebaseline <series> --from <day> --reason "<the item it follows>"`. This appends to
  `~/.claude/state/kaizen/waste-baselines.jsonl`. It is never done to silence an alarm (that is the cobra path).

## Running it

- Daily: `kaizen_collect_v2.py --daily` publishes the tier after the outcome tier, lazily and fail-open, for the day and the two before it.
- History: `kaizen_waste.py --backfill`, from each source's first day, idempotent.
- One day, read-only: `kaizen_waste.py --day <D> [--json]`.

A publish never goes past min(yesterday, the newest non-waste series day), so a waste file can never block the
collector's catch-up.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/sysadmin/kaizen_digest.py`
- `scripts/sysadmin/kaizen_waste.py`
<!-- END related-scripts -->
