---
description: Converge ONE project doc to the verifiable truth of the codebase — the /fabrik-features loop generalized to every agent-filled scaffold doc (SERVICES, RESILIENCE, CONFIGURATION, OPERATIONS, QUICKSTART, DEPLOYMENT, TROUBLESHOOTING, indexes, README, BUSINESS_MODEL, STRATEGIC_BACKLOG) — pick its convergence contract, discover ground truth, reconcile bidirectionally, iterate to an edit-free no-op. TRIGGER — EN: "converge this doc", "update SERVICES.md to match the code"; TR: "bu dokümanı koda göre güncelle", "SERVICES.md'yi senkronize et" — fires for ONE named doc. SKIP: the whole-tree sweep (→ /fabrik-docs-review) or FEATURES/data-contract/ui-design (their own commands). Stage: utility.
argument-hint: "<doc path or name, e.g. docs/SERVICES.md or SERVICES — one doc per run>"
---

Converge ONE named project doc into a **claim-free, code-grounded contract**: everything it asserts is verifiable in the tree/infra, and everything the code obligates it to say is present. The whole-tree sweep is `/fabrik-docs-review`.

{{include:run-record}}
{{include:orient}}

{{include:delegated-reads}}
{{include:term-edit}}
{{include:grounding-artifact}}
## Phase 0 — Establish scope + pick the contract

Resolve `$ARGUMENTS` in the current project to ONE doc and its row in the **Convergence Contract table**. No row → STOP and say so: FEATURES → `/fabrik-features`, data-contract → `/fabrik-data-contract`, ui-design/design-system → `/fabrik-ui-design`; CHANGELOG/LESSONS_LEARNT/AFCL are append-only ledgers and PORTS.md is a registry whose reconcile home is `/fabrik-docs-review`. Read the doc, its seeding template under `templates/scaffold/docs/` (the canonical SHAPE — restructure drift back toward it), and `project.yaml::type` plus the spec `shape:` (they decide which sections apply).

## The Convergence Contract table (per-doc ground truth + completeness rule)

| Doc | Ground truth to sweep | Complete when |
|---|---|---|
| `docs/SERVICES.md` | `compose.yaml` services · every external call-site in code (HTTP clients, SDKs, `claude -p`, OpenRouter) · `.env.example` keys | every compose service has a row (YOUR sweep is the completeness authority, not `check_compose_services.py`) AND every call-site has a dependency block (env, cost, rate limits, failure signature, fallback) AND no block cites a dead call-site |
| `docs/RESILIENCE.md` | scheduler code · pause-key usage · spec `shape:` flags + `target_vps:` · every external call-site's per-call price, balance endpoint or quota constant | §7 lists every scheduled job in code with its real interval, and ONLY jobs that exist; each `shape:` flag true in the spec has its §5 addendum honored in code; the §1 Shape Card (incl. `target_vps`) matches the spec; every external API the CODE calls with a billable balance has a §7 depletion row (never §2's own cost column) |
| `docs/CONFIGURATION.md` | every `os.getenv`/`process.env` read in code · `.env.example` | every var read in code is documented AND in `.env.example`; every documented var is read (delete dead vars, stated); documented defaults match the code |
| `docs/OPERATIONS.md` | compose services · RESILIENCE §7 (link, never copy) · runbook commands | every service has an operate-it section; every §7 job has a manual-fallback playbook or an explicit "no manual path"; every command RUNS (execute read-only ones; reason destructive ones against current flags/paths) |
| `docs/QUICKSTART.md` | live routes/CLI entrypoints · `compose.dev.yaml` · `.env.example` · the spec's `target_vps:` | the 5-minute path works from a clean clone (execute what is executable); every endpoint/SDK example matches a live route signature; the production-URL subdomain matches `target_vps:`; no step references retired infra |
| `docs/DEPLOYMENT.md` | `specs/services/<id>.yaml` · compose memory limits/labels · the registrar reality READ from the spec `shape:` block (inspection only; `fabrik` is hub-side, never a project shell-out) | every environment row matches the spec incl. `target_vps:` (spoke projects document the mesh-IP DSN `10.99.0.1:<port>`, never hub Docker-DNS names); the registrar list matches what `shape:` triggers; no banned option appears as a choice |
| `docs/TROUBLESHOOTING.md` | git log/LESSONS/incidents since last converge · current code paths | every entry's symptom+fix still applies to TODAY's code (open the paths/commands); recurring symptoms have entries; fixed-forever entries move to archive citing the fixing commit |
| `INDEX.md` | the real tree (`git ls-files`; a file on disk but untracked is present, not deleted; a bare filename in a directory's row resolves under that directory) | every tracked file/dir of significance has a row; no row cites a deleted path; purposes match reality (spot-open) |
| `docs/README.md` · `docs/INDEX.md` | `docs/` listing · the doc registry buckets | every doc present is indexed with an honest purpose; no row for an absent doc; the subdir list matches; each docs-level index obeys this rule and the two agree — a disagreement in the one not under converge is a keyed ripple (Phase 2) |
| `README.md` | the codebase + FEATURES.md | the 150–300-word identity is true (type, port, stack from real config); every capability claim is verified against the code, with FEATURES as a cross-check; setup points at QUICKSTART, not inlined |
| any project-local `docs/reference/<name>.md` (a subsystem's dedicated doc) | the subsystem's code paths, config keys, live probe | every claim maps to a current code path or an executed probe; every `## Related scripts` block is rendered from the scripts' `# AFTER-EDIT:` headers, never hand-kept; a doc whose subsystem is gone is retired, not polished |
| `docs/BUSINESS_MODEL.md` | pricing/entitlement code · payment-route config | tiers/prices match the enforcing code; payment routing matches the org's real routes (PayTR/iyzico/Paddle/RevenueCat — never Stripe; `core/85-payments-billing.md` § Payment Providers is canonical); internal-tool block used when nothing is billed |
| `docs/STRATEGIC_BACKLOG.md` | plans/ (active+archived) · review residuals · TROUBLESHOOTING recurrences | no item a landed plan already shipped (delete, cite the plan); every item has a real trigger; accepted-not-fixed residuals appear here or are dropped WITH the drop cited in the commit body (an uncited drop is a miss) |

## Phase 1 — Discover ground truth (the doc is the CLAIM, never the source)

Sweep the row's ground-truth column from the CODE/infra outward, enumerating what you READ (files × surfaces), not what you remember. RUN the executable truth (QUICKSTART steps, OPERATIONS read-only commands, route signatures) — output beats inspection.

## Phase 2 — Reconcile bidirectionally

- **Code → doc:** everything the sweep found that the contract obligates gets its row/block/section.
- **Doc → code:** every existing claim opens to something real TODAY (a path that looks right is not grounding — open it). Delete dead claims, stating the removal; correct half-true ones.
- **Shape discipline:** keep the seeding template's structure; respect canonical-inventory boundaries (§7 lives in RESILIENCE — SERVICES/OPERATIONS link, never copy; the Doc Sync Matrix rows bind). A path in another `/opt` repo is written as a backticked plain path, never a markdown link — GitHub resolves a link's leading `/` against this repo's root. A `\|` inside a table cell is cell content (GFM), so a table-shape check splits on unescaped pipes only — and a bare pipe inside a backtick span still splits the row, so it is escaped too. Seat briefs carry these two rules and the by-design check below.
- **Code defects:** before raising a schema, missing-table or missing-feature finding, grep `docs/DECISIONS.md` and `docs/archive/` for a by-design ruling, quoting the row; a ruling that does not cover the finding leaves it standing. A CODE defect the converge uncovers is filed to its owner (a mail to the owning session, or a backlog row), never patched inside a doc converge; the doc states what the code does today and names the filed id.
- **Ripples:** a KEYED ripple (Doc Sync Matrix) lands as the MINIMAL MECHANICAL EDIT in this run's commit, outside the convergence counters (`edits:` and the md5 track the ARTIFACT only), so it never re-opens the loop. A ripple needing a full converge becomes the named follow-up (`/fabrik-doc-converge <sibling>`), with the staleness stated in the commit body — never silently.

## Phase 3 — Converge (LOOP to a no-op)

Repeat passes until the Termination contract's closing round — `confirmed: 0`, md5 unchanged. Each pass re-runs a fresh Phase-1 sweep against the CURRENT tree, re-opens every NEW claim plus a STATED sample of old ones (the pass ledger carries re-opened k of N), re-checks the row's "complete when" clause end to end, and lists what it re-read. The CLOSING pass re-opens every claim any edit touched plus the full contract clause. Bump `Last Updated:` only at the final flip.

## Guardrails — never

- Trust the doc as its own inventory — the row's ground-truth column is the denominator.
- Write a claim you didn't open a file (or run a command) to ground — memory is not discovery.
- Converge two docs in one run — ripples go through the Matrix or become named follow-ups.
- "Fix" the seeded template's structure locally — shape defects go upstream to `templates/scaffold/docs/`, content lives here.
- Declare converged on the pass that edited — the loop ends only at the Termination contract's closing round (`confirmed: 0`, md5-verified).

{{include:subagents-core}}

{{include:close-chain}}
