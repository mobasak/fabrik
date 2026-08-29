Output: the **CERT BOARD + LEDGER**, generated — never hand-written.

⚠️ **The denominator comes from a live REGISTRY, not from this list and not from a doc.** The four
discovery modes above are demoted to **cross-checks** (their bidirectional-reconciliation value is
real and is kept). The denominator resolves to a machine-readable registry of the RUNNING system,
declared in `project.yaml::certification_registry`; undeclared falls back to the per-type default AND
records the fallback. A registry that cannot be reached **fails LOUD naming what could not be
enumerated** — a silently short list rebuilds the defect one layer down.

Why: the inventory used to be PROSE WITH COUNTS, authored by the agent later graded against it, and
**nothing read it**. On a surface the project authored, the agent's enumeration and reality converge
and this never bites; on an INHERITED surface it under-counts silently and the run terminates
HONESTLY AND WRONG. Measured on a `saas-skeleton` wrapping a vendored ERP, immediately after a
genuine md5-verified `/fabrik-features` no-op: **30 shipped FEATURES rows (~12 browser-reachable)
against 271 menus / 316 window actions / 80 wizards / 19 reports / 142 model buttons / 867 views —
93% inherited.** ~12 of ~1,700 would be exercised and the gauntlet would report converged.
`/fabrik-features` is NOT the fix: it documents what the project BUILT; certification must cover what
the product SHIPS.

**Two generated artifacts, both inside the run's own board directory so they archive as a unit:**

```
docs/development/certifications/YYYY-MM-DD-cert-<surface>/
  YYYY-MM-DD-cert-<surface>.md   ← the spine, carrying `## Test Board`
  ledger.md                      ← source: · registry_total: · ids_enumerated:
  TC01-<slug>.md …               ← one ticket per touchpoint GROUP
```

⚠️ **NAMESPACE — never reuse the implementation plan's.** `## Test Board` (not `## Ticket Board`),
`TC##[a-z]?-<slug>.md` (not `T##`), `docs/development/certifications/` (not `plans/`), and
`.fabrik/cert-locks/` (not `.fabrik/plan-locks/`). The heading is load-bearing:
`/fabrik-execute-plan`'s dispatcher triggers on that **bare string**, so a mis-headed board is
dispatched to CODING agents holding a lock the Stop hook believes in. `check_certification_coverage.py`
flags all four as **BLOCKING**, not advisory.

**Every ID reaches a terminal disposition — `EXERCISED` (evidence path must EXIST on disk) or
`OUT-OF-SCOPE(reason naming an external owner)`. `UNVISITED` is a FINDING, not a hard block: `check_certification_coverage.py` reports it **advisory by deliberate design** (registration `advisory=True`; since 2026-08-29 a MIX-UP finding exits 1 and BLOCKS — coverage quality alone never does; see its docstring) — so a board full of `UNVISITED` will NOT redden the gate. **You must therefore paste the grader's verbatim counters into the report** (`ids`/`exercised`/`unvisited`/`blocking`) and read them: measured at transdoc 2026-08-27, a board reporting `{ids: 7, exercised: 0, unvisited: 7}` passed a green 49/0 gate because the board had gone STALE, and neither the grader nor an operator reading a green gate could tell that from a genuinely untested surface. A run that closes with `unvisited > 0` closes NOT-QUIET, never `done`. `DEFERRED` is
REJECTED**, with its synonyms — a "later" state is the loophole that lets the whole contract be
ignored. `inherited` / `vendored` / `generated` / `legacy` / `low priority` are **rejected REASONS**:
they describe how OUR surface came to exist, not whether a customer can reach it, and inherited
surfaces are exactly what the T3 generated-smoke tier is FOR.

**Bulk marking is where a deny-list leaks — and the grader never records.** A sweep flag
(`--tier`/`--kind`/any multi-id form) must pass the SAME per-id refusals as a single mark: the
reference implementation's first live sweep marked 39 navigation containers `EXERCISED` via a
screen suite that never touched them because the sweep path skipped the modelless-entry refusal
(tryton-crm, fixed and re-proven 424→385). And recording stays OUT of the grader by design — a
checker that can also mark things done will eventually mark things done; retiring an id goes
through the PROJECT'S recorder script — project-local by design, not hub-synced; the reference
implementation is `/opt/tryton-crm/scripts/certification_record.py` (cross-repo READ to vendor
from; a project without one vendors it before the first sweep), evidence mandatory, the grader
only reads.

**The fifth oracle — reference-data reconciliation (trade-intelligence `01M1580AH`, 2026-08-29).**
The UI-truth-vs-SYSTEM-truth comparison is blind to a defect ABSENT FROM BOTH SIDES: a levy the API
never computed and the card therefore never rendered agreed perfectly across four certification
runs (30 quiet rounds) while silently omitting a ~2.46M TRY line whose ZERO happened to be correct
— agreement is what the comparison checks, and no number of rounds, personas or viewports can see a
row missing from both sides. So for every journey whose output is ADJUDICATED CONTENT (levies,
prices, entitlements, computed rows), at least one scenario per content class reconciles the
response against an INDEPENDENT reference source — the governing table/ruleset/fixture the domain
itself names — asserting not just that rendered rows are right but that every row the reference
implies is PRESENT or its absence individually justified. No independent reference reachable → say
so in the ledger (`reference-reconciliation: unavailable — <why>`); an unstated missing oracle is
how this class survives.

**The demoted doc inventory keeps its teeth.** Demoting `docs/FEATURES.md` to a cross-check does NOT
mean discarding it: **every FEATURES row must map to the ticket/scenario IDs that exercise it, and a
feature with zero mapped IDs cannot be reported as working.** That clause survived the denominator
change and is the cross-check's whole value — an independent second opinion is exactly what catches a
generator that agrees with itself. A large divergence between the doc inventory and the registry is
REPORTED, not silently preferred either way.

**Tiers set DEPTH, never whether something is tested.** T1 money/tenancy/PII/auth → full
UI-truth-vs-system-truth · T2 authored or modified → deep · T3 inherited → **generated** smoke. 100%
is achievable only because the tail is generated; hand-authoring it guarantees the tier is skipped.

**Every ticket declares `Runner:`** — `gui` · `service` · `generated-smoke` · `fix`. The dispatcher's
default unit is a CODER, so an unrouted test ticket puts a coding agent on a browser job. **An issue
found becomes ANOTHER TICKET on the same board** (`Runner: fix`), and **a fix ticket does not close
its test ticket** — the test must be re-run green. That is the retest loop, structurally.
