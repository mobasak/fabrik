Output: the **CERT BOARD + LEDGER**, generated — never hand-written.

⚠️ **The denominator comes from a live REGISTRY, not from this list and not from a doc.** The four
discovery modes above are **demoted to cross-checks** (their bidirectional-reconciliation value is real and is kept). The denominator resolves to a machine-readable registry of the RUNNING system,
declared in `project.yaml::certification_registry`; undeclared falls back to the per-type default AND
records the fallback. A registry that cannot be reached **fails LOUD naming what could not be
enumerated**.

On a surface the project authored, the agent's enumeration and reality converge and this never bites; on an INHERITED surface it under-counts silently and the run terminates HONESTLY AND WRONG. `/fabrik-features` is NOT the fix: it documents what the project
BUILT; certification must cover what the product SHIPS.

**Two generated artifacts and one hand-written recipe, all inside the run's own board directory so they archive as a unit:**

```
docs/development/certifications/YYYY-MM-DD-cert-<surface>/
  YYYY-MM-DD-cert-<surface>.md   ← the spine, carrying `## Test Board`
  ledger.md                      ← source: · registry_total: · ids_enumerated:
  runtime.md                     ← hand-written: how the target was started, recorded before any round
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
REJECTED**, with its synonyms. `inherited` / `vendored` / `generated` / `legacy` / `low priority` are **rejected REASONS**:
they describe how OUR surface came to exist, not whether a customer can reach it; T3 generated-smoke covers inherited surfaces.

**Board grammar, exact (learned by failing the grader — brand-identiy `01M168QED`):** the
disposition column is headed **`Disposition`** (or `State`) — a `Status` column reads as UNVISITED;
ONE evidence path per cell (a comma-separated cell fails the existence check whole); ticket files
are `TC##[a-z]?-<slug>.md` ONLY — beside the spine, `ledger.md` and the `runtime.md` recipe are the
two non-ticket files, and any other `.md` flags BAD TICKET. **Evidence discipline:** the board's `evidence/`
dir is NEVER a runner's `--output` dir (runners WIPE their output root at start — passing the sweep dir as `--output` deletes cross-run evidence); take explicit `page.screenshot` paths and `cp` to
`evidence/` IMMEDIATELY (attachments persist only for failing tests).

**Bulk marking is where a deny-list leaks — and the grader never records.** A sweep flag
(`--tier`/`--kind`/any multi-id form) must pass the SAME per-id refusals as a single mark: the
reference implementation's first live sweep marked 39 navigation containers `EXERCISED` via a
screen suite that never touched them because the sweep path skipped the modelless-entry refusal
(tryton-crm, fixed and re-proven 424→385). And recording stays OUT of the grader by design; retiring an id goes
through the PROJECT'S recorder script — project-local by design, not hub-synced; the reference
implementation is `/opt/tryton-crm/scripts/certification_record.py` (cross-repo READ to vendor
from; a project without one vendors it before the first sweep), evidence mandatory, the grader
only reads.

**The fifth oracle — reference-data reconciliation (trade-intelligence `01M1580AH`, 2026-08-29).**
The UI-truth-vs-SYSTEM-truth comparison is blind to a defect ABSENT FROM BOTH SIDES: a levy the API
never computed and the card therefore never rendered agreed perfectly across four certification
runs (30 quiet rounds) while silently omitting a ~2.46M TRY line whose ZERO happened to be correct. So for every journey whose output is ADJUDICATED CONTENT (levies, prices, entitlements, computed rows), at least one scenario per content class reconciles the
response against an INDEPENDENT reference source — the governing table/ruleset/fixture the domain
itself names — asserting not just that rendered rows are right but that every row the reference
implies is PRESENT or its absence individually justified. No independent reference reachable → say
so in the ledger (`reference-reconciliation: unavailable — <why>`).

**The demoted doc inventory keeps its teeth.** Demoting `docs/FEATURES.md` to a cross-check does NOT mean discarding it: **every FEATURES row must map to the ticket/scenario IDs that exercise it, and a
feature with zero mapped IDs cannot be reported as working**. A large divergence between the doc inventory and the registry is
REPORTED, not silently preferred either way.

**Tiers set DEPTH, never whether something is tested.** T1 money/tenancy/PII/auth → full
UI-truth-vs-system-truth · T2 authored or modified → deep · T3 inherited → **generated** smoke. 100%
is achievable only because the tail is generated; hand-authoring it guarantees the tier is skipped.

**Every ticket declares `Runner:`** — `gui` · `service` · `generated-smoke` · `fix`. The dispatcher's
default unit is a CODER, so an unrouted test ticket puts a coding agent on a browser job. **An issue
found becomes ANOTHER TICKET on the same board** (`Runner: fix`), and **a fix ticket does not close
its test ticket** — the test must be re-run green.
