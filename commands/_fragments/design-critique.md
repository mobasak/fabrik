**Two independent design critiques before the operator decides (operator ruling 2026-10-03).** Before the
design-approval DECISION block — and in `/fabrik-task`, after writing `design.md` and BEFORE `step --design`
records it, so before phase 3 builds anything — dispatch two author-blind critique seats in ONE message: `fabrik-reviewer` with `model: "opus"`
(the latest Opus) and `fabrik-reviewer` with `model: "fable"` (the latest Fable) — the operator's exception to
the tier map's "Fable is never a routine finder" (D-517). **Dispatch step (D-191):** the pair is fixed at two
seats, under the floor `dispatch_headroom.py` always grants, so no sizing run is owed — stamp them BEFORE they
go out with `python3 scripts/command_run.py dispatch --seats 2`. Both get the SAME brief, and neither sees the
other's answer. The brief holds:
- the design artifact pinned by md5 (the spec, plan, flows or UI contract, or the phase-2 `design.md`) and the
  commit it was read at — a cited fleet-synced file (`scripts/enforcement/`, `.windsurf/rules/`) is gitignored in a
  project, so no commit of the project holds it: copy the project's own file to the scratchpad and name it by that
  path and its md5 (its origin is the hub's `/opt/fabrik/<path>`), the md5 standing in for a commit wherever line
  numbers are cited;
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

**Once both critiques are in hand (the stand-in Opus seat's when Fable failed, the re-dispatched seat's when
one came back empty), you adjudicate every concern by executing its claim**, then give it one disposition:
- `ACCEPTED` — the change is applied, and reviewed before anyone approves it: in spec-review and plan-review
  it re-opens the loop for ONE delta round by the round-1 seats over the fix, and `Status: CONVERGED` stands only
  if that round confirms 0 (else the loop continues — that round is a delta round of the same loop, so its
  own-fix defects count in the same scope-growth window and, once that stop has fired, route to its backlog row); in `/fabrik-task` you edit `design.md` before `step
  --design` records it, which works on both lane versions;
- `REJECTED` — with the counter-evidence;
- `OPEN` — the operator rules on it (at a design-approval gate, an OPEN concern makes the panel split).

Run the step once per artifact version: an md5 already critiqued in this run is not re-dispatched. In
`/fabrik-task`, present both critiques with the design: each seat's verdict, then each concern with its
disposition. At a design-approval gate, the panel step that follows decides what reaches the operator.

**Cobra (D-253):** the cheapest way past this step is two rubber-stamp `sound` verdicts. The counter: a
critique that names no concern AND no attack it tried is re-dispatched once, then shown to the operator as
empty.
