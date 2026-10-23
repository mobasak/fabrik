**The panel answers the design-approval gate in the operator's place (operator ruling 2026-10-06, D-613 —
for design approval only, it supersedes D-558's "a panel never approves a gate class" and D-153's printed
presentation).** The two critique seats above are the operator's stand-ins, not advisers. Their brief adds what
the operator would weigh: the artifacts this one builds on or feeds (spec, plan, flows, data contract, UI
contract), the rule packs `python3 scripts/select_rules.py` marks ACTIVE for the surface, the
`agents-fabrik.md` sections it touches, and the `docs/DECISIONS.md` rows it cites. Each seat answers as the
operator would — approve it, or name the changes it wants first — and opens its answer with the line
`VERDICT: <sound|sound-with-changes|unsound> — <artifact path>`.

1. **Read the verdicts.** A seat approves when it returns `sound`, or `sound-with-changes` with every concern
   ACCEPTED. A concern you REJECT or leave OPEN, or an `unsound`, makes the panel SPLIT — the author never
   overrules the operator's stand-in. When Fable is unavailable, the second Opus seat stands in and the Panel
   line adds `fable unavailable: <reason>`.
2. **Revise.** Apply every ACCEPTED change to the artifact — written as this command's own fix-shape rule says,
   where it states one — and to any linked artifact it makes stale. Before the round that reviews the revision
   is pinned, each sentence it adds or changes is written whole from the source it cites (the code line it
   describes, or the decision row or artifact section it builds on — never a seat's report), not spliced into
   the old sentence; each name it introduces is traced through every reader it must reach, process boundaries
   included (an `env -i` keep-list, a systemd unit, a hook environment); and each ACCEPTED concern's
   counter-case, the legitimate input the change must still pass, is written beside it for step 3's row. Then
   run the ONE delta round the critique step names. spec-review and plan-review flip `Status: CONVERGED` only on its
   `confirmed 0`, in the step-3 commit; flows-review and ui-design-review bump `Version:`, re-run the closing round and rewrite
   `Independently reviewed: v<N+1>`.
3. **Record.** Mint the approval row (`python3 scripts/decisions.py --reserve-id .`), staged with the revisions
   and that flip: the artifact path and its final md5, each change the panel caused with its counter-case, and
   the line `Panel: opus="<its VERDICT line>" fable="<its VERDICT line>" → both-approve`, each quoted whole. The
   ask↔spec comparison table is still built — in the artifact or its review receipt, not in chat. Commit and
   push.
4. **Brief the operator** in at most ten lines under the heading `PANEL APPROVED (<artifact path>)`: what the
   file is, what it will make happen once built, each verdict in one line, the changes it caused, the approval
   row's id, and the same `Panel:` line. In autonomy mode the Stop hook checks that line against the seats'
   own returned text: two approving VERDICT lines naming this artifact.
5. **Continue.** After the brief, run the next command named below. `/fabrik-execute-plan` is never started
   from a gate: after an approved plan, the brief's `NEXT:` names it as ready work.

**A split still goes to the operator.** Write the same brief, add one line per disputed concern with each
seat's position, then end the turn with the command's DECISION block, its Why line naming the artifact path and its
`Panel:` line ending `→ split`. Other gate classes (deploy, destructive, spend, credentials, publish) stay the
operator's.

**Cobra (D-253):** the cheapest way through is a change ACCEPTED on paper and never made. The counter: the
approval row lists each change as written — a translated mechanism is listed as the behaviour it secures — and the
delta round's seats check each one in the revised artifact.
