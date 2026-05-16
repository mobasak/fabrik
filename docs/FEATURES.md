# Fabrik — Features

**Last Updated:** 2026-03-08
**Version:** 0.1.0

> This document serves as both **product documentation** and **marketing source material**.

---

## Quick Reference

| Feature | Status | Audience | Headline |
|---------|--------|----------|----------|
| [Preplan Handoff](#preplan-handoff) | ✅ Shipped | Developer | Capture intent before scaffold; every agent reads the same intent |
| [Project Scaffolding](#project-scaffolding) | ✅ Shipped | Developer | Create production-ready projects in seconds |
| [Documentation Enforcement](#documentation-enforcement) | ✅ Shipped | Developer | Never ship undocumented code again |
| [9-Step Workflow](#9-step-workflow) | ✅ Shipped | Developer | Systematic code quality from plan to commit |
| [Kilo AI Review](#kilo-ai-review) | ✅ Shipped | Developer | AI-powered code review with fix suggestions |
| [Registrar Audit & Reconcile](#registrar-audit--reconcile) | ✅ Shipped | Operator | Spec ↔ live drift detection across the fleet |
| [Local Dev Loop](#local-dev-loop) | ✅ Shipped | Developer | `fabrik dev` / `fabrik logs --local` / `fabrik review` — code, watch, bundle for review without leaving WSL |
| [State-Driven Destroy](#state-driven-destroy) | ✅ Shipped | Operator | `fabrik destroy --use-state` reverses what was actually deployed, not what the spec says now |
| [Cross-VPS Portability](#cross-vps-portability) | ✅ Shipped (import untested) | Operator | `fabrik export` / `fabrik import` — bundle VPS state for rebuild on a fresh target |
| [WordPress Provisioning](#wordpress-provisioning) | 🚧 Beta | Admin | Declarative WordPress site deployment |

**Status Legend:**
- ✅ **Shipped** — Production-ready
- 🚧 **Beta** — Available but may change
- 📋 **Planned** — On roadmap

---

## Preplan Handoff

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.2 (T3-01)

> **Headline:** Capture project intent BEFORE scaffold — every agent reads the same intent without re-deriving it.

### What It Does

The Fabrik lifecycle begins with **intent capture**. Before `fabrik scaffold` creates any files, run `fabrik preplan new <slug>` to author `docs/preplans/<YYYY-MM-DD>-<slug>.md` from a 9-section template (Idea / Project type / Shape preview / External deps / Domain / Success criteria / Out of scope / Open questions / Notes-VPS1-inventory-reminders). Refine the markdown with Opus / Claude / ChatGPT until the intent is hardened. Then `fabrik scaffold <name> --from-preplan <path>` ingests it:

1. Pre-fills `--type` from the preplan's "Project type" section
2. Pre-fills the spec's `shape:` block from the preplan's "Shape preview" yaml
3. Adopts the preplan's "Idea" first line as the project description
4. Copies the preplan to `<project>/docs/preplan.md`
5. **Appends a `Preplan:` reference line to all 4 AI guardrail files** — `AGENTS.md` (Traycer), `CLAUDE.md` (Claude Code), `AGENTS-compact.md` (Kilo), `.windsurfrules` (Windsurf) — so every downstream agent that opens the project reads the same intent

### How To Use

```bash
fabrik preplan new citation-verifier
# Edit docs/preplans/<today>-citation-verifier.md — fill in the 9 sections
fabrik scaffold citation-verifier --from-preplan docs/preplans/<today>-citation-verifier.md
```

Traycer's `docs/traycer/fabrik-workflow.md` Step 2.5 is the planning-side companion: when Traycer detects a fresh project (no scaffold yet), it looks for a matching preplan in `docs/preplans/` BEFORE asking the operator to declare anything from scratch.

### Why This Matters

Without intent capture, every downstream agent (Claude Code writing code, Kilo reviewing, Windsurf editing, Traycer planning) has to **re-derive** what the project does from incomplete context. That re-derivation is where "wait, what was this project supposed to do?" drift comes from. The preplan is the single source of truth; the 4-guardrail injection makes sure every agent reads it.

The template's `## 9. Notes` section also embeds the VPS1-inventory reminders (postgres-main:5432, redis-main:6379, X-Internal-Token pattern, `*.vps1/health` Authelia bypass, /metrics scrape target, GlitchTip DSN convention) — so agents reading the preplan stay grounded in the same VPS1 reality the scaffold-emitted guardrails enforce.

---

## Project Scaffolding

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.1

> **Headline:** Create production-ready projects in seconds with built-in best practices

### What It Does

Fabrik scaffold generates a complete project structure with pre-configured tooling, documentation templates, and inherited quality rules. Every scaffolded project starts with the same conventions, reducing onboarding time and ensuring consistency.

### How To Use

```bash
fabrik scaffold my-project --type python-api
```

### Marketing Copy

| Channel | Copy |
|---------|------|
| **Landing Page** | "Stop configuring, start building. Fabrik scaffolds production-ready projects with documentation, testing, and deployment ready to go." |
| **Email Subject** | "New project? Fabrik gets you to 'Hello World' in 30 seconds" |
| **Social Media** | "🏗️ fabrik scaffold my-app → Full project with docs, tests, CI/CD in seconds #DevTools" |
| **Sales One-liner** | "Fabrik scaffold eliminates boilerplate so teams ship features, not config." |

### Technical Details

<details>
<summary>Click to expand</summary>

**CLI Command:** `fabrik scaffold <name> [--type TYPE] [--github-create]`

**Generated Structure:**
- `src/` — Source code with `__init__.py`
- `tests/` — Test directory with sample test
- `docs/` — Documentation with FEATURES.md, INDEX.md
- `.env.example` — Environment template
- `AGENTS.md` — file copy of `/opt/fabrik/AGENTS.md` (Traycer)
- `AGENTS-compact.md` — file copy of `/opt/fabrik/AGENTS-compact.md` (Kilo CLI)
- `CLAUDE.md` — file copy of `/opt/fabrik/CLAUDE.md` (Claude Code) — *added T1-02 G-B5*
- `.windsurfrules` — file copy of `/opt/fabrik/.windsurfrules` (Windsurf Cascade)
- `.windsurf/rules/` — file copy of `/opt/fabrik/.windsurf/rules/`

**Optional flags:**

- `--github-create` (T1-02 G-B2): also creates a private GitHub repo at `mobasak/<name>` via `gh repo create … --yes`. Best-effort — missing `gh` binary or unauthenticated state log a warning and continue.

**Output trailer:** Every successful scaffold ends with a `# Next: cd /opt/<name>; open Traycer …` hint pointing at the Traycer-managed workflow (T1-02 G-B4).

**Project Types:** `python-api`, `saas-skeleton`, `node-api`, `file-api`, `file-worker`, `wordpress`, `docusaurus`, `chrome-extension`, `mobile-app`, `desktop-app`, `static-site`

</details>

---

## Documentation Enforcement

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.1

> **Headline:** Never ship undocumented code again

### What It Does

Automated checks ensure documentation stays in sync with code. When you add a feature, change a schema, or create an API endpoint, Fabrik reminds you to update the relevant docs.

### Enforcement Scripts

| Script | Trigger | Severity |
|--------|---------|----------|
| `check_changelog.py` | Code changes ≥10 lines | ERROR |
| `check_schema_sync.py` | DB model changes | ERROR |
| `check_readme_md.py` | Missing required sections | ERROR |
| `check_openapi_sync.py` | New API routes | WARNING |
| `check_test_coverage.py` | New public functions | WARNING |
| `check_env_example.py` | New env vars in code | WARNING |
| `check_compose_services.py` | New Docker services | WARNING |

### Marketing Copy

| Channel | Copy |
|---------|------|
| **Landing Page** | "Documentation that updates itself. Fabrik catches missing docs before they reach production." |
| **Email Subject** | "Your code review just got smarter: auto-doc enforcement" |
| **Social Media** | "📝 Fabrik now enforces schema.sql sync, API docs, and test coverage automatically #DevOps" |
| **Sales One-liner** | "Fabrik's enforcement scripts catch documentation drift at commit time." |

---

## 9-Step Workflow

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.1

> **Headline:** Systematic code quality from plan to commit

### What It Does

A structured workflow that ensures every code change goes through planning, implementation, review, and verification before commit. Token-optimized to run deterministic checks before expensive AI review.

### The Flow

```
PLAN → IMPLEMENT → SELF_REVIEW → FINAL_GATE → KILO → FINAL_GATE → VERIFY → SYNC → COMMIT
```

| Step | Action |
|------|--------|
| 1 | Traycer Plan (spec, edge cases, env vars) |
| 2 | Coder Implements |
| 2.5 | Self-Review (MANDATORY) |
| 3 | Final Gate (pre-Kilo) |
| 4 | Kilo Review Loop |
| 5 | Final Gate (post-Kilo) |
| 6 | Traycer Verification |
| 7 | Sync Only |
| 8 | Commit |

### Marketing Copy

| Channel | Copy |
|---------|------|
| **Landing Page** | "From idea to commit in 9 verified steps. No shortcuts, no surprises." |
| **Email Subject** | "The workflow that catches bugs before your users do" |
| **Social Media** | "🔄 9-step workflow: Plan → Code → Review → Gate → Ship. Every time. #QualityFirst" |
| **Sales One-liner** | "Fabrik's 9-step workflow embeds quality gates into every commit." |

---

## Kilo AI Review

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.1

> **Headline:** AI-powered code review with actionable fix suggestions

### What It Does

Kilo is a diff-aware AI code reviewer that analyzes changes against your task spec. It identifies issues, suggests fixes, and validates plan coverage—all with structured JSON output for automation.

### How To Use

```bash
python scripts/kilo_code_review.py review <files> --plan "Task description" --output json
```

### Marketing Copy

| Channel | Copy |
|---------|------|
| **Landing Page** | "AI code review that understands your intent. Kilo checks your changes against your plan." |
| **Email Subject** | "Meet Kilo: Your AI code reviewer that actually reads the spec" |
| **Social Media** | "🤖 Kilo AI review: $0.03-0.40 per review, catches issues humans miss #AICodeReview" |
| **Sales One-liner** | "Kilo reviews code against your spec, not just syntax—finding logic errors, not just lint." |

---

## Registrar Audit & Reconcile

**Status:** ✅ Shipped | **Audience:** Operator | **Since:** v0.2 (T2-02)

> **Headline:** Spec ↔ live drift detection across the fleet, surgical destroy, fleet-wide reconcile

### What It Does

Every `fabrik apply` writes a per-spec state file (T2-01) capturing which registrars fired. T2-02 layers four operator commands on top of that foundation:

- **`fabrik audit-registrars`** — Compares each spec's shape-resolved registrars (what SHOULD be live) to the VPS's actual state (postgres `\l`, gatus `apps/<id>.yaml`, authelia config rules, backrest `config.json` plans, glitchtip project API, meilisearch index, prometheus scrape jobs, redis `assignments.json`). Outputs a pivot table or JSON. Exit 2 if any `missing`.
- **`fabrik reconcile-all`** — Walks every deployed spec, holds a per-spec file lock (T2-01 `locks_local.file_lock`), re-runs `DeploymentOrchestrator.refresh_infrastructure` per spec. Dry-run by default; `--yes` to apply. `--filter <substr>` to scope.
- **`fabrik verify <domain> --spec registrars`** — Single-domain postcondition check using the YAML-driven `PostconditionChecker`. Fails on any `missing` registrar.
- **`fabrik destroy --partial <reg>`** — Surgical un-registration without touching DNS, Coolify app, or local files. Repeatable: `--partial gatus --partial backrest`. Backed by module-level `HANDLER_ARGS` / `HANDLER_FUNCS` exports in `orchestrator/destroyer.py` (also consumed by T4-02).

### How To Use

```bash
# Audit the whole fleet
fabrik audit-registrars

# JSON for automation (alerts, dashboards)
fabrik audit-registrars --spec specs/services/translator.yaml --json | jq .

# Re-run registrars across the fleet (dry-run)
fabrik reconcile-all --filter translator

# Single-domain registrar coverage check
fabrik verify translator.vps1.ocoron.com --spec registrars

# Surgical removal of one or more registrars
fabrik destroy specs/services/translator.yaml --partial gatus --dry-run
fabrik destroy specs/services/translator.yaml --partial gatus --partial backrest -y
```

### Status Glyphs

| Glyph | Status  | Meaning                                                          |
|-------|---------|------------------------------------------------------------------|
| `✓`   | present | Shape says yes, live state agrees                                |
| `✗`   | missing | Shape says yes, live state says no                               |
| `·`   | n/a     | Shape says skip (includes `infra:` override case, reason in detail) |
| `?`   | unknown | Probe failed (e.g. SSH error, missing token, container not found)   |

A `drift` status (live exists but in a different shape than expected) is
not yet produced by any auditor — they currently check presence only.
Follow-up auditors will compare config bags.

### Excluded by design

`grafana` is intentionally excluded from destroy handlers and reports `n/a` for audit. Grafana annotations are point-in-time decorative markers, not driftable lifecycle state.

---

## Local Dev Loop

**Status:** ✅ Shipped | **Audience:** Developer | **Since:** v0.3 (T3-03)

> **Headline:** Code, watch, and bundle for review without leaving WSL. Three CLI commands close the inner-loop gap between scaffold and `fabrik apply`.

### What It Does

Stage 2 of the Fabrik lifecycle (Agentic Implementation) is where the developer iterates on code against the spec contract. T3-03 ships three commands that keep that loop tight without round-tripping to the VPS:

- **`fabrik dev`** — runs the project's `compose.dev.yaml` stack locally via `docker compose up`. Hot-reload + bind mounts, no Coolify involvement.
- **`fabrik logs --local`** — tails `docker compose -f compose.dev.yaml logs` (sibling of the Loki-backed `fabrik logs <service>` for remote queries).
- **`fabrik review`** — bundles `git diff` + `specs/services/<id>.yaml` + `docs/preplan.md` + the resolved-registrar table into `.fabrik/review/<ts>.md`. Hand the bundle to a human reviewer or dispatch to Kilo CLI's reviewer agent.

### How To Use

```bash
cd /opt/<project>

# 1. Spin up the local dev stack (compose.dev.yaml from the scaffold)
fabrik dev -d

# 2. Tail logs in another terminal
fabrik logs --local -f
fabrik logs --local --service api -f   # one service only

# 3. When the diff looks good, bundle for review
fabrik review                          # uses HEAD by default
fabrik review --since HEAD~3           # last 3 commits
fabrik review --out /tmp/review.md     # custom output path

# 4. Dispatch (out-of-band)
kilo run --agent reviewer --input .fabrik/review/<ts>.md
```

### Why This Matters

Pre-T3-03 the only feedback channel was `fabrik apply` → VPS deploy → Loki tail. That's a multi-minute loop for every iteration. `fabrik dev` keeps the loop in-WSL (sub-second), and `fabrik review` puts the spec contract + resolved-registrar surface in front of every reviewer so they catch shape contradictions before the deploy phase (consistent with the agent-rule snippet T3-02 propagated everywhere: "don't ship code that contradicts the spec").

### Technical Details

- **Scope of `--local`**: only `fabrik logs --local` branches to docker. The remote `fabrik logs <service>` path (Loki) is unchanged — `--local` is opt-in.
- **`.fabrik/review/` is gitignored**: bundles are local artefacts. The PR diff already captures the change set; the bundle is a reviewer prompt, not a tracked file.
- **Spec auto-detection**: `fabrik review` finds the first `specs/services/*.yaml` under cwd. Override with `--spec <path>`.
- **No spec required**: works on projects without a spec (the resolved-registrar section is omitted).
- **Helpers extracted** to [`src/fabrik/dev_tools.py`](../src/fabrik/dev_tools.py) so tests can exercise `build_review_bundle` / `run_dev_compose` / `run_local_logs` without invoking docker.

---

## State-Driven Destroy

**Status:** ✅ Shipped | **Audience:** Operator | **Since:** v0.3 (T4-02)

> **Headline:** `fabrik destroy --use-state` reverses what was actually applied, not what the spec says now. The spec is allowed to drift; the teardown isn't.

### What It Does

The default `fabrik destroy <spec>` walks the spec's current `shape:` block and runs only the destroyers the current shape declares applicable. That breaks when the spec drifted between apply and destroy:

```bash
# Day 1 — apply with search
echo "shape: { has_search_feature: true }" >> spec.yaml
fabrik apply spec.yaml         # meilisearch index created

# Day 7 — search no longer needed
sed -i 's/has_search_feature: true/has_search_feature: false/' spec.yaml

# Day 30 — destroy
fabrik destroy spec.yaml       # ❌ shape says no search → meilisearch destroyer SKIPPED → orphan index
fabrik destroy spec.yaml --use-state --drop-data -y   # ✅ replays Day-1 state, reaps the index
```

### How To Use

```bash
# Dry-run to see what state-driven destroy would tear down
fabrik destroy /opt/fabrik/specs/services/hello-api.yaml --use-state --dry-run

# Safe path (no data-bearing registrars in state, or operator OK with refusal)
fabrik destroy /opt/fabrik/specs/services/hello-api.yaml --use-state -y

# State has postgres / redis / meilisearch → must explicitly drop data
fabrik destroy /opt/fabrik/specs/services/hello-api.yaml --use-state --drop-data -y
```

### Why This Matters

Two invariants the vision insists on (Stage 3 — Proper Registration) are now load-bearing on teardown too:

1. **Zero leaks.** Every registrar that `fabrik apply` ran ends up in the state file; `--use-state` guarantees every one of them runs its destroyer. No orphan auth rules, no orphan meilisearch indexes, no ghost gatus monitors.
2. **No silent data destruction.** State files mark `postgres / redis / meilisearch` entries with `data_bearing: true` (per [`state.DATA_BEARING_REGISTRARS`](../src/fabrik/state.py#L69)). `--use-state` refuses with an explicit error if any are present and `--drop-data` isn't set:

   ```text
   ❌ data-bearing-guard refused — state has data-bearing registrars (meilisearch, postgres);
      re-run with --drop-data to confirm destruction
   ```

   Operators have to type the data-destruction intent every single time.

### Technical Details

- **Phase 0** — data-bearing guard. Scans state's `registrars_applied` for `data_bearing: true` entries; refuses pre-flight if `--drop-data` not set.
- **Phase 1** — canonical reverse-order registrar teardown using `reversed(_REGISTRAR_ORDER)`: `prometheus → meilisearch → authelia → grafana → glitchtip → backrest → gatus → redis → postgres`. Order is enforced because postgres-last avoids FK violations against authelia session rows. Grafana is intentionally skipped (annotations are decorative). Dispatch uses T2-02's module-level `HANDLER_FUNCS` + `HANDLER_ARGS` maps.
- **Phase 2** — Coolify app (always), DNS (gated by `--keep-dns` + spec domain), local files (gated by `--keep-files`).
- **On success** — `state.archive_destroyed(spec.id)` moves `<id>.json` → `_destroyed/<id>.json.<UTC-ts>`. State file is the deploy-state record; the archive preserves the audit trail without leaving the file in place to confuse future audits.
- **Mutually exclusive with `--partial`** — both flags exist for distinct surgical purposes (per-registrar vs. per-state-file). The combination errors out (exit 2).
- **Handler exception → bounded error.** A single failing destroyer doesn't abort the rest of the teardown; the failure goes into the report as an `error` ActionResult and `--use-state` exits 2 so CI can catch it.

### Acceptance Reference

Epic Brief Success Criterion 3. Live verification: `pytest tests/test_destroy_use_state.py -v` (16/16 pass), including the primary-path `TestPrimaryPathSpecDrift::test_a_resources_destroyed_even_after_shape_b`.

---

## Cross-VPS Portability

**Status:** ✅ Shipped (export verified; import path untested in this epic) | **Audience:** Operator | **Since:** v0.3 (T4-03)

> **Headline:** `fabrik export` produces a portable tarball that captures every resource `fabrik apply` registers on this VPS. `fabrik import` provides the rebuild scaffold on a fresh target. Zero secrets, zero UUIDs.

### What It Does

If vps1 dies — or you want to spin up vps2 as a base for a second customer / staging environment — the portability bundle lets you carry the registration story across machines without re-running every `fabrik apply` ticket by hand:

```bash
# On vps1 — produce the bundle
fabrik export --out /tmp/vps1-base.tar.gz

# Transfer to the new VPS (operator's choice: scp, rsync, etc.)
scp /tmp/vps1-base.tar.gz vps2:/tmp/

# On vps2 — see what would be restored (dry-run, default)
fabrik import /tmp/vps1-base.tar.gz

# Re-populate .env secrets per the bundle's secrets-redacted.json checklist
# (the ~0.5-day manual cost pack §28 'Secrets ergonomics' calls out)
nano /opt/fabrik/.env

# Execute the restore (stubbed in this epic; live roundtrip lands in vps2 stand-up)
fabrik import /tmp/vps1-base.tar.gz --apply
```

### What's Inside the Bundle

```text
fabrik-export-vps1-YYYY-MM-DD.tar.gz
├── manifest.json                  # version + section counts + untested_paths
├── README.md                      # restore steps + prerequisites
├── secrets-redacted.json          # .env KEY NAMES (never values)
├── specs/services/*.yaml          # every service spec
├── state/*.json                   # T2-01 state files, coolify_uuid stripped
├── coolify/{applications,services,projects}.json    # UUIDs recursively stripped
├── monitoring/{prometheus,alertmanager,redis-assignments,postgres-allocations}*
├── monitoring/grafana-dashboards/  # repo-local mirrors
├── authelia/configuration.yml      # SSH-pulled (best-effort)
└── backrest/config.json            # SSH-pulled (best-effort)
```

### Security Invariants (test-enforced)

1. **No plaintext secret values.** `_redact_env_keys` reads only up to the first `=` of each `.env` line. The test byte-scans the entire gzip stream for known values and asserts zero hits.
2. **No Coolify UUIDs.** `_strip_uuids` recurses both keys (14 known UUID-named fields including `private_key_uuid`, `server_uuid`, `deployment_uuid`) and bare 24-alphanum string values. The test scans 5 distinct UUID markers across all bundle entries.
3. **No Coolify private-key UUIDs** (a special case of the above) — guarantees the target can't accidentally inherit the source's git deploy-key references.

### Why Import Is Shipped Untested

The real roundtrip needs a fresh Ubuntu VM with bootstrapped Coolify + postgres-main + redis-main. Pack §28 explicitly defers this to the vps2 stand-up. Until then:

- The `import` pipeline parses the bundle, validates the manifest, and emits a restore plan.
- The `--apply` flag runs but ends at a documented stub (`phase: real_run / status: stub`).
- The bundle README enumerates manual follow-ups not automated by import: LetsEncrypt cert transfer, DNS provider re-binding, OAuth provider re-creation, postgres/meilisearch data restore (only if `--include-data` was used at export).

### Acceptance Reference

Pack v3.2 §EPIC SCOPE Tier 4 G-J2 (effort revised v2: +0.5 day for secrets ergonomics). Live verification: `pytest tests/test_portability.py -v` (23/23 pass). Sample run on `/opt/fabrik` produced a 44 KB tarball with 26 Coolify applications, 348 redacted secret keys, and zero UUID leaks.

---

## WordPress Provisioning

**Status:** 🚧 Beta | **Audience:** Admin | **Since:** v0.1

> **Headline:** Declarative WordPress site deployment

### What It Does

Define your WordPress site in YAML—pages, menus, plugins, users—and Fabrik provisions it. Reproducible, version-controlled WordPress infrastructure.

### Marketing Copy

| Channel | Copy |
|---------|------|
| **Landing Page** | "WordPress as code. Define your site in YAML, deploy with one command." |
| **Email Subject** | "Finally: Version-controlled WordPress deployments" |
| **Social Media** | "📄 WordPress spec → 🚀 Live site. Fabrik provisions WP declaratively #WordPress #IaC" |
| **Sales One-liner** | "Fabrik treats WordPress like infrastructure: defined, versioned, reproducible." |

---

## Appendix: Marketing Asset Extraction

### All Headlines

1. **Scaffolding:** "Create production-ready projects in seconds"
2. **Doc Enforcement:** "Never ship undocumented code again"
3. **9-Step Workflow:** "Systematic code quality from plan to commit"
4. **Kilo AI:** "AI-powered code review with actionable fix suggestions"
5. **WordPress:** "Declarative WordPress site deployment"

### Feature Matrix

| Feature | OSS | Pro |
|---------|-----|-----|
| Project Scaffolding | ✅ | ✅ |
| Documentation Enforcement | ✅ | ✅ |
| 9-Step Workflow | ✅ | ✅ |
| Kilo AI Review | ✅ | ✅ |
| WordPress Provisioning | 🚧 | ✅ |

---

## See Also

- [README.md](../README.md) — Project overview
- [CHANGELOG.md](../CHANGELOG.md) — Version history
- [AGENTS.md](../AGENTS.md) — AI agent briefing
