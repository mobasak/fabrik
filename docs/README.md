# docs/ — the Fabrik hub documentation tree

**Charter (2026-07-20, docs-truth convergence):** every folder has ONE role; a doc that doesn't fit its
folder's role is misplaced. `INDEX.md` (repo root) is the machine-checked index; this file is the map of
what belongs where.

| Folder | Role — what belongs here | What does NOT |
|---|---|---|
| `docs/` root | The gate-required canonical set (BUSINESS_MODEL, CONFIGURATION, DEPLOYMENT_ARCHITECTURE, FEATURES, QUICKSTART, SERVICES, TROUBLESHOOTING, LESSONS_LEARNT, STRATEGIC_BACKLOG, CAPABILITIES, PROJECT_CATALOG, owner profile) | anything else — new root docs are gate-blocked |
| `reference/` | Look-up truth, no procedures: `apis/` (external API contracts incl. EXTERNAL_SYSTEMS.md), `modules/` (src/fabrik module references), root (CLI reference, architecture map, decision guides, sync-pinned agent contracts), `research/` (operator deep-research), `service-contracts/` (live microservice contracts), `fixtures/` (ground-truth captures), `kilo/` (auto-generated subagent-pool selection tables — the dir name is legacy; the content is the LIVE flywheel), `MD/` (prompt-authoring standards), `windsurf/` (Windsurf IDE/extension docs — the Cascade LLM route is retired) | runbooks (→ operations/), fleet state (→ infrastructure/), workflow how-tos (→ workflows/) |
| `operations/` | Operate-the-fleet runbooks: deployment, disaster-recovery, credential-recovery, gpu-rent, restore inventories, WSL cron | dev-box setup (→ workstation/) |
| `infrastructure/` | VPS-fleet setup references, rebuild runbooks, status snapshots, probe-reports, audit-prompts | workstation docs, orchestrator wiring |
| `workstation/` | Local dev-box setup: WSL fixes, MCP transports, editor tooling, the full Claude config inventory, the fabrik-mail AI message channel | anything that runs on the fleet |
| `workflows/` | Per-script reference docs for live hub automation (final_gate, sync, scaffold, health) | docs for retired scripts (→ archive/) |
| `orchestrator/` | The autonomous-factory command chains (epic-to-ticket, mega-epic), cockpit docs, north star, Traycer wiring | — |
| `development/` | Plan/epic/review artifacts: `plans/` (+`archived/`), `epics/`, `reviews/` (evidence ledgers) | — |
| `superpowers/` | `/fabrik-spec` designs (`specs/` + `specs/archived/`) and skill-authored plans | — |
| `traycer/` | Traycer-GUI usage docs (the tool is live; its Kilo-era docs are archived) | — |
| `preplans/` | Stage-1 operator research intents (`fabrik preplan`) | — |
| `zed/` | Operator's Zed-migration notes (personal, in-flight) | — |
| `archive/` | History. Content is frozen as written; internal links inside archived docs are exempt from link gates | anything still load-bearing |

**Lifecycle rules:** finished plans → `development/plans/archived/`; shipped/superseded specs →
`superpowers/specs/archived/`; retired-tool docs → `archive/`. Enforced by `scripts/final_gate.py`
(doc-links, doc-index, retired-terms, sprawl checks — see `scripts/enforcement/`).
