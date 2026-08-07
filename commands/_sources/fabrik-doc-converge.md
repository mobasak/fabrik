---
description: Converge ONE project doc to the verifiable truth of the codebase — the /fabrik-features loop generalized to every agent-filled scaffold doc (SERVICES, RESILIENCE, CONFIGURATION, OPERATIONS, QUICKSTART, DEPLOYMENT, TROUBLESHOOTING, indexes, README, BUSINESS_MODEL, STRATEGIC_BACKLOG) — pick its convergence contract, discover ground truth, reconcile bidirectionally, iterate to an edit-free no-op. TRIGGER — EN: "converge this doc", "update SERVICES.md to match the code"; TR: "bu dokümanı koda göre güncelle", "SERVICES.md'yi senkronize et" — fires for ONE named doc. SKIP: the whole-tree sweep (→ /fabrik-docs-review) or FEATURES/data-contract/ui-design (their own commands). Stage: utility.
argument-hint: "<doc path or name, e.g. docs/SERVICES.md or SERVICES — one doc per run>"
---

Converge the named project doc into a **claim-free, code-grounded contract**: everything the doc
asserts is verifiable in the tree/infra, and everything the code obligates the doc to say is present.
One doc per run — depth over breadth (the whole-tree sweep is `/fabrik-docs-review`; this is the
single-doc deep converge).

{{include:term-edit}}
{{include:grounding-artifact}}
## Phase 0 — Establish scope + pick the contract

Operate on the current project (cwd). Resolve `$ARGUMENTS` to ONE doc and its row in the
**Convergence Contract table** below. No row → STOP and say so (FEATURES → `/fabrik-features` ·
data-contract → `/fabrik-data-contract` · ui-design/design-system → `/fabrik-ui-design`;
CHANGELOG/LESSONS_LEARNT/AFCL are append-only ledgers — history is never "converged against code" —
and PORTS.md is a per-allocation registry whose reconcile home is `/fabrik-docs-review`; none of these
has a row, by design). Read the doc, its seeding template under
`templates/scaffold/docs/` (the canonical SHAPE — restructure drift back toward it), and the
project's `project.yaml::type` + spec `shape:` (they decide which sections apply).

## The Convergence Contract table (per-doc ground truth + completeness rule)

| Doc | Ground truth to sweep | Complete when (the bidirectional contract) |
|---|---|---|
| `docs/SERVICES.md` | `compose.yaml` services · every external call-site in code (HTTP clients, SDKs, `claude -p`, OpenRouter) · `.env.example` keys | every compose service has a row (`check_compose_services.py` only WARNs on newly-staged services — YOUR sweep is the completeness authority) AND every external call-site has a dependency block (env, cost, rate limits, failure signature, fallback) AND no block cites a dead call-site |
| `docs/RESILIENCE.md` | scheduler code (Beat/cron/queue registrations) · pause-key usage · spec `shape:` flags + top-level `target_vps:` | §7 lists every scheduled job in code with its real interval — and ONLY jobs that exist; every `shape:` flag true in the spec has its §5 addendum honored in code; the §1 Shape Card (incl. `target_vps`) matches the spec; every external API in §2 with a billable balance has a §7 depletion row |
| `docs/CONFIGURATION.md` | every `os.getenv`/`process.env` read in code · `.env.example` | every var read in code is documented AND in `.env.example`; every documented var is actually read (dead vars deleted, stated); defaults in the doc match the code's defaults |
| `docs/OPERATIONS.md` | compose services · RESILIENCE §7 (link, never copy) · real runbook commands | every service has an operate-it section; every §7 job has a manual-fallback playbook or an explicit "no manual path"; every command in the doc RUNS (execute the read-only ones; reason the destructive ones against current flags/paths) |
| `docs/QUICKSTART.md` | live routes/CLI entrypoints · `compose.dev.yaml` · `.env.example` · the spec's top-level `target_vps:` | the 5-minute path works from a clean clone (execute what is executable); every endpoint/SDK example matches a live route signature; the production-URL subdomain matches the spec's `target_vps:`; no step references retired infra |
| `docs/DEPLOYMENT.md` | `specs/services/<id>.yaml` · compose memory limits/labels · the registrar reality READ from the spec `shape:` block (inspection only — `fabrik` is a hub-side CLI, never a project shell-out) | every environment row matches the spec incl. `target_vps:` (spoke projects document the mesh-IP DSN `10.99.0.1:<port>`, never hub Docker-DNS names); the registrar list matches what `shape:` actually triggers; no banned option appears as a choice |
| `docs/TROUBLESHOOTING.md` | git log/LESSONS/incident entries since last converge · current code paths | every entry's symptom+fix still applies to TODAY's code (paths/commands open); recurring symptoms since the last pass have entries; fixed-forever entries are moved to archive with the fixing commit cited |
| `INDEX.md` | the real tree (`git ls-files`) | every tracked file/dir of significance has its row; no row cites a deleted path; purposes match reality (spot-open) |
| `docs/README.md` | `docs/` dir listing · the doc registry buckets | every doc present is indexed with an honest purpose; no row for an absent doc; subdir list matches what exists |
| `README.md` | the codebase + FEATURES.md | the 150–300-word identity is true (type, port, stack from real config); every capability claim maps to a FEATURES row; setup points at QUICKSTART, not inlined |
| `docs/BUSINESS_MODEL.md` | pricing/entitlement code · payment-route config | tiers/prices match the enforcing code; payment routing matches the org's real routes (iyzico/Paddle/RevenueCat — never Stripe); internal-tool block used when nothing is billed |
| `docs/STRATEGIC_BACKLOG.md` | plans/ (active+archived) · review residuals · TROUBLESHOOTING recurrences | no item that a landed plan already shipped (delete, cite the plan); every item has a real trigger; accepted-not-fixed review residuals appear here or are consciously dropped |

## Phase 1 — Discover ground truth (the doc is the CLAIM, never the source)

Sweep the contract row's ground-truth column from the CODE/infra outward. Enumerate what you READ
(files × surfaces), not what you remember — a capability/var/job/service found in the tree but
absent from your sweep notes is the miss this phase exists to prevent. For rows with executable
truth (QUICKSTART steps, OPERATIONS read-only commands, route signatures), RUN it — output beats
inspection.

## Phase 2 — Reconcile bidirectionally

- **Code → doc:** everything the sweep found that the contract obligates gets its row/block/section.
- **Doc → code:** every existing claim opens to something real TODAY (a path that looks right is not
  grounding — open it). Dead claims are deleted with the removal stated; half-true claims are
  corrected to what is true.
- **Shape discipline:** keep the seeding template's structure (it is consumer-contract-hardened);
  respect canonical-inventory boundaries (§7 lives in RESILIENCE — SERVICES/OPERATIONS link, never
  copy; the Doc Sync Matrix rows bind).
- **Ripples:** a fix here may obligate a sibling doc (Doc Sync Matrix) — apply the ripple in the
  same run or state it as a named follow-up, never silently.

## Phase 3 — Converge (LOOP to a no-op)

Repeated passes until one demonstrably-thorough pass makes **zero edits** (the Termination
contract): each pass re-runs a fresh Phase-1 sweep against the CURRENT tree, re-opens every NEW
claim plus a sample of old ones, re-checks the contract row's "complete when" clause end to end,
and bumps `Last Updated:` only at the final flip. List what you re-read each pass.

## Guardrails — never

- Trust the doc as its own inventory — the contract row's ground-truth column is the denominator.
- Write a claim you didn't open a file (or run a command) to ground — memory is not discovery.
- Converge two docs in one run — ripples go through the Matrix or become named follow-ups.
- "Fix" the seeded template's structure locally — shape defects go upstream to
  `templates/scaffold/docs/` (they're Fabrik-maintained), content lives here.
- Declare converged on the pass that edited — the loop ends only on an edit-free, md5-verified
  no-op round.

{{include:subagents-core}}
