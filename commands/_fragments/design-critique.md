**Two independent design critiques before the operator decides (operator ruling 2026-10-03).** Before the
design-approval DECISION block — and in `/fabrik-task`, after writing `design.md` and BEFORE `step --design`
records it — dispatch two author-blind critique seats in ONE message: `fabrik-reviewer` with `model: "opus"`
(the latest Opus) and `fabrik-reviewer` with `model: "fable"` (the latest Fable) — the operator's exception to
the tier map's "Fable is never a routine finder" (D-517). **Dispatch step (D-191):** the pair is fixed at two
seats, under the floor `dispatch_headroom.py` always grants, so no sizing run is owed — stamp them BEFORE they
go out with `python3 scripts/command_run.py dispatch --seats 2`. Both get the SAME brief, and neither sees the
other's answer. The brief holds:
- the design artifact pinned by md5 (the spec, plan, flows or UI contract, or the phase-2 `design.md`) and the
  commit it was read at;
- the operator's ask in their own words;
- the house rules every seat brief carries: read-only, no `$HOME/.claude*` reads, scratch only under the
  absolute scratchpad, `timeout 120 /usr/bin/grep`.

The brief never carries the author's review history or recommendation. Ask each seat to read the design
COLD and return:
- a verdict: `sound` · `sound-with-changes` · `unsound`;
- its concerns, ranked — each with an anchor (section or line), the claim, its evidence (`path:line` or the
  command run and its output), and the change it proposes;
- or, when it has no concern, the attacks it tried and why each held.

Fable runs on metered usage credits. When Fable is unavailable, refused or out of credit, run a second
Opus seat in its place, and say so in the presentation with the reason. Never present a single critique.

**You adjudicate every concern by executing its claim**, then give it one disposition:
- `ACCEPTED` — the change is applied, and reviewed before anyone approves it: in spec-review and plan-review
  it re-opens the loop for ONE delta round by the round-1 seats over the fix, and `Status: CONVERGED` stands only
  if that round confirms 0 (else the loop continues); in `/fabrik-task` you edit `design.md` before `step
  --design` records it, which works on both lane versions;
- `REJECTED` — with the counter-evidence;
- `OPEN` — the operator rules on it (at a design-approval gate, an OPEN concern makes the panel split).

Run the step once per artifact version: an md5 already critiqued in this run is not re-dispatched. In
`/fabrik-task`, present both critiques with the design: each seat's verdict, then each concern with its
disposition. At a design-approval gate, the panel step that follows decides what reaches the operator.

**Cobra (D-253):** the cheapest way past this step is two rubber-stamp `sound` verdicts. The counter: a
critique that names no concern AND no attack it tried is re-dispatched once, then shown to the operator as
empty.
