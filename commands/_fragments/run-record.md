## Run record — open it as this command's FIRST act

A step this command's text names as running BEFORE the record (`/fabrik-review-scoped`'s surface classification) runs first; then the record opens, unless that step routed to another command, whose record replaces this one.

`CLAUDE.md` makes a run record the first act of any `/fabrik-*` invocation, and the Stop hook's fifth cause reads it: while a record says `running`, ending the turn is BLOCKED. That is the machinery that stops a command being abandoned half-executed — it only protects you if you open it.

```bash
python3 scripts/command_run.py start --command {{COMMAND}} --phases {{PHASES}} \
  --surface "<what this run is OVER — the spec | plan dir | ticket | diff range>" \
  --terminal "<this command's own terminal condition, in your words>"
```

Then `step --phase <N> --title "<the phase title>"` on entering each phase, so the pinned `RUN:` line shows the operator where the run actually is rather than where it started. `--surface` is what makes the run's ledger row ANALYSABLE; name it at `start` (the close accepts `--surface` too if you learn it late).

Where the outcome rests on an act this run does not perform (a deploy, a service restart, a port another process binds, a merge by its owner), the `--terminal` names the hand-off and who performs the act, and `--evidence` says whether they had acted at the close.

Close it EXACTLY ONE of these ways — never by simply stopping (a third, ``handoff --resume <a file with a `## RESUME` block>``, only where this command's own text names that close):

- `python3 scripts/command_run.py done --command {{COMMAND}} --evidence "<what proves the terminal condition was met>" --feedback "<what you filed, to whom | none — the surfaces this run exercised>"` — "finished" is not evidence. ⚠️ **`--feedback` is REQUIRED: the close REFUSES without it** (§ Close-out feedback, at the end of this command), and a refused close leaves the record `running`, which the Stop hook blocks the turn on. `none` is a valid verdict; silence is not.
- `python3 scripts/command_run.py blocked --command {{COMMAND}} --reason "<what · searched · missing>" --feedback "<what you filed, to whom | none — the surfaces this run exercised>"` on one of the three sanctioned BLOCKED cases (3 consecutive same-test failures · missing infra · an unresolvable spec contradiction). Two more stops close `blocked` too: the quota wall (`blocked --wall`, at the RED or WALL band of `CLAUDE.md`'s quota bands: commit, push, then close) and a pause the operator ordered (`blocked --paused`, its `--reason` the operator's words, D-993). Both hold in every command, even where its text calls other stops the only ones, and every stop that text names holds too; the verdict is required here too.

**Always name the run you close.** A bare close ends whatever is live — which, when this command was invoked BY another, silently ends the *caller* instead. A mismatched name is refused; closing an already-closed run is a warned no-op.

**Open the `RUN:` line (`python3 scripts/command_run.py line`) on every reply until this run closes.**

**Sync-excluded repo (fabrik-lib and its worktrees)?** A check this command names by script is NOT necessarily present locally; absence is never compliance: run the HUB copy read-only against your tree — `python3 /opt/fabrik/scripts/enforcement/<check>.py --root <repo>` (plan checks: `--plan-dir <dir> --project-root <repo>`), and report ITS verdict.
