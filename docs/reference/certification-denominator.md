# Certification denominator — what a gauntlet must cover, and who says so

**What this covers:** how `/fabrik-user-test` and `/fabrik-service-test` decide WHAT must be tested,
the generated cert board that records it, and `scripts/enforcement/check_certification_coverage.py`,
the grader that reads it. **Fleet-synced** — the check ships to every governance-synced project.

---

## The defect this exists to close

Both commands enumerated an inventory and terminated when a round added nothing new. The inventory
was **prose with counts**, authored by the agent that was later graded against it — and **nothing
read it**. `scripts/enforcement/` graded reviews and unit tests and had no certification grader at
all. The agent chose its own denominator and marked its own homework.

On a surface the project authored, the agent's enumeration and reality converge and this never bites.
On an **inherited** surface it under-counts silently and the run terminates **honestly and wrong** —
a true statement about the wrong denominator, which neither command can self-detect.

Measured on a `saas-skeleton` wrapping a vendored ERP, taken immediately after a genuine
md5-verified `/fabrik-features` no-op, so the denominator was as healthy as the old contract allowed:

```
FEATURES.md:    30 shipped rows, ~12 browser-reachable
live registry:  271 menus · 316 window actions · 80 wizards · 19 reports
                142 model buttons · 867 views
authored split: 19 ours / 252 vendored — 93% of the navigation a customer clicks is inherited
```

~12 of ~1,700 would be exercised and the gauntlet would report converged. **`/fabrik-features` is not
the fix** — it documents what the project BUILT; certification must cover what the product SHIPS.

## The denominator comes from a registry

Declared in `project.yaml::certification_registry`, copying the shipped precedent `has_user_guide`,
which arms `check_user_guide.py` (`:7-8` — pass when absent, fail when declared-but-missing). NOT
`spec_loader.py::Shape`, which declares which *infrastructure registrars* apply (`:205-215`); a
certification denominator is not an infrastructure registrar.

Undeclared falls back to the per-type default **and records the fallback** — a declared-and-justified
fallback is auditable, an inferred one is not. Defaults live in `REGISTRY_BY_TYPE`: live route table
or OpenAPI for the API types, the task/beat registry for workers, `sitemap.xml` for sites, the MV3
manifest for extensions, the navigator tree for mobile, the window/menu registry for desktop, and for
anything wrapping a vendored platform, **that platform's own registry**.

⚠️ `wordpress` is deliberately absent. It is a dead legacy string in `SCAFFOLD_TYPES`
(`scaffold.py:146`, with `:5783` raising `NotImplementedError`); zero projects declare it. It lives
in `RETIRED_TYPES` as a **crash guard** — a sibling check that iterated the frozenset and let that
exception escape turned a `warn_only` row into a blocking red across ~46 repos.

## Two artifacts, one directory

```
docs/development/certifications/YYYY-MM-DD-cert-<surface>/
  YYYY-MM-DD-cert-<surface>.md   ← spine, carrying `## Test Board`
  ledger.md                      ← source: · registry_total: · ids_enumerated:
  TC01-<slug>.md …               ← one ticket per touchpoint GROUP
```

Co-sited on purpose: the dispatcher archives the whole directory at Finish, and a board that archives
without its ledger leaves a later auditor holding the verdict without the question it answered.

## ⚠️ The namespace is SEPARATE, and that is load-bearing

| | Implementation | Certification |
|---|---|---|
| directory | `plans/YYYY-MM-DD-plan-<slug>/` | `certifications/YYYY-MM-DD-cert-<surface>/` |
| ticket | `T##[a-z]?-<slug>.md` | `TC##[a-z]?-<slug>.md` |
| board | `## Ticket Board` | `## Test Board` |
| lock | `.fabrik/plan-locks/` | `.fabrik/cert-locks/` |

`/fabrik-execute-plan`'s dispatcher detection triggers on the **bare heading string** (`:34-38`), so a
cert board wearing `## Ticket Board` would be dispatched to **coding agents** holding a lock
`final_gate_stop.py:785` believes in. `check_phase_tests.py:36` reads the same lock dir.

**These four are BLOCKING findings from day one** while everything else is advisory. The advisory
rollout was ruled for *coverage completeness* — nobody's release should freeze because their real
fraction became visible. It was never ruled for a wrong-agent dispatch, and a warn-only safety guard
is one nobody reads until after the damage.

## Dispositions — there are two, and `DEFERRED` is not one

| Disposition | Meaning |
|---|---|
| `EXERCISED` | visited and asserted on; the **evidence path must exist on disk** |
| `OUT-OF-SCOPE(reason)` | not our product's functionality; the reason must NAME AN EXTERNAL OWNER |
| `UNVISITED` | not terminal — **blocks the close** |

`DEFERRED` is rejected, with its synonyms (`SKIPPED`/`TODO`/`PENDING`/`WONTFIX`) — rejecting the word
and leaving the synonyms is how a banned state returns.

⚠️ **Deleting `DEFERRED` moved the hole; it did not close it.** `OUT-OF-SCOPE` was graded on a
non-empty reason alone, so 1,688 `OUT-OF-SCOPE(inherited vendor surface)` + 12 `EXERCISED` would
report CONVERGED — the same scenario, different word. Three closures: a **rejected-reason list**
(`inherited`, `vendored`, `generated`, `legacy`, `low priority` describe how OUR surface came to
exist, not whether a customer can click it), an **always-printed disposition census**, and
`out-of-scope > exercised` as a **distinct non-silent verdict** needing operator acknowledgement.

## Tiers set DEPTH, never whether something is tested

**T1** money / tenancy / PII / auth → full UI-truth-vs-system-truth · **T2** authored or modified →
deep · **T3** inherited → **generated** smoke. 100% is reachable only because the tail is generated;
mandating hand-written specs for T3 guarantees the tier is quietly skipped.

## Runners — a cert ticket is not a coding ticket

Every `TC##` declares `Runner:` — `gui` · `service` · `generated-smoke` · `fix`. The dispatcher's
default unit is a coder, so an unrouted test ticket puts a coding agent on a browser job.

**An issue found becomes another ticket on the same board** (`Runner: fix`), and **a fix ticket does
not close its test ticket** — the test must be re-run green. That is the retest loop, structurally,
rather than a prose "HANDED-OFF list" a defect can rot in.

## The anti-cheat, and its limit

At close: re-enumerate and diff — any new ID means NOT converged. But that alone **cannot see a
consistently short generator**, because both enumerations come from the same generator and a short
list agrees with itself. So the ledger records a raw `registry_total` counted straight from the
registry against `ids_enumerated`, and a mismatch is a loud refusal. The doc-derived inventory
survives as a **graded cross-check** — an independent second opinion is what catches a generator that
agrees with itself.

**Honest limit:** the grader can verify an evidence path EXISTS; it cannot verify the assertion behind
it was meaningful. A generated T3 smoke that asserts nothing would pass. Path-existence is the
strongest mechanical proxy available and it defeats the cheapest cheat — a ledger of plausible paths
nobody produced.

## Contract

- **Advisory** (`warn_only`) on landing, except the four namespace findings above. Promotion of the
  rest to blocking is a separate operator decision, taken once the fleet has run it.
- **Always exits 0.** `final_gate.py:198-208` converts a non-zero `warn_only` exit into a fleet-wide
  blocking red; the BLOCKING verdict rides the finding's flag, never the exit code.
- **stdlib only**; ASCII output by construction; census first, within the 500-char / 10-line budget.

## See also

- `docs/development/plans/2026-08-27-plan-1-certification-denominator.md` — the plan (14 rounds)
- `scripts/enforcement/check_certification_coverage.py` · `tests/enforcement/test_certification_coverage.py`
- `commands/_sources/fabrik-user-test.md` · `commands/_sources/fabrik-service-test.md`

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/enforcement/check_certification_coverage.py`
<!-- END related-scripts -->
