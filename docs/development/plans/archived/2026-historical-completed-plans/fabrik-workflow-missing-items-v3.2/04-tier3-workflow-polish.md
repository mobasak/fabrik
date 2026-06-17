# 04 — Tier 3: Workflow Polish (v3.2)

**Total effort:** ~10 hours; in scope for the single Fabrik Workflow Convergence epic; can land in parallel with Tier 2 work
**Risk:** low — mostly docs and rule files, plus a couple of small CLI commands
**Goal:** make the front-of-funnel (preplan→Traycer) and the executor rule files first-class so the entire flow is unambiguous

## v2 changes

- §21 G-A5 now explicitly absorbs former G-C3 (preplan→epic-brief handoff) — addresses C2
- §24 G-D1 corrected: 5 executor rule files (AGENTS-compact.md, CLAUDE.md, .windsurfrules, AFCL.md, opencode.json) — was 3 in v1
- §24 + §25 add explicit bulk propagation step `python3 scripts/sync_enforcement_to_projects.py --force` — addresses C5
- §25 G-D2 corrected: 22 rule files, not 20 — addresses B8
- All "41 projects" → "42 projects" — addresses C15

## Why Tier 3 after Tier 2

Tier 1 + Tier 2 close the deploy/reconcile loop. Tier 3 closes the **planning + coding** loop.

After Tier 3, an "idea → deploy" pass goes through fully-specified handoffs at every seam.

## Order of operations

19-21 are the preplan handoff (Phase A gaps + absorbed G-C3). 22-23 extend Traycer (Phase C). 24-26 add executor awareness (Phase D). 27 is local-dev convenience (Phase I).

---

## 19. G-A1 + G-A2 — Preplan template + location convention

**Effort:** 1 hour (unchanged from v1)
**Files:** `templates/preplan/preplan.md.j2` + `docs/preplans/.gitkeep` + `docs/preplans/README.md`

### Convention

```
docs/preplans/<YYYY-MM-DD>-<slug>.md
```

### Template content (excerpt)

`templates/preplan/preplan.md.j2`:

```markdown
# Preplan: {{ slug }}

**Date:** {{ date }}
**Status:** draft
**Outputs to:** `fabrik scaffold {{ slug }} --from-preplan docs/preplans/{{ date }}-{{ slug }}.md`

## 1. Idea (one paragraph)
## 2. Project type (pick one of the 12 templates)
## 3. Shape preview (overrides template defaults)
## 4. External dependencies
## 5. Domain (if public)
## 6. Success criteria (3-5 bullets, measurable)
## 7. Out of scope
## 8. Open questions for Traycer epic-brief
## 9. Research notes (Opus output, links, snippets)
```

### Acceptance

- `docs/preplans/` exists with README and `.gitkeep`.
- `templates/preplan/preplan.md.j2` exists.

---

## 20. G-A3 — `fabrik preplan new <slug>` CLI command

**Effort:** 30 minutes (unchanged from v1)
**File:** `src/fabrik/cli.py` — new subcommand

### Behavior

```
$ fabrik preplan new tender-platform-mvp
✅ Created: docs/preplans/2026-05-12-tender-platform-mvp.md
   Edit it, then run:
     fabrik scaffold tender-platform-mvp --type python-api --from-preplan docs/preplans/2026-05-12-tender-platform-mvp.md
```

### Acceptance

- `fabrik preplan new test-slug` creates the file with today's date.
- Re-running fails with a clean error.

---

## 21. G-A4 + G-A5 — `fabrik scaffold --from-preplan` + workflow integration (G-A5 absorbs former G-C3)

**Effort:** 2 hours (unchanged from v1)
**Files:** `src/fabrik/cli.py` (extend `scaffold`), `src/fabrik/scaffold.py` (preplan ingestion), `docs/traycer/fabrik-workflow.md` (Step 2.5)

### G-A5 scope (clarified v2 — absorbs former G-C3)

G-A5 is the **whole preplan→epic-brief handoff workflow**, not just a doc edit. It includes:
1. The `--from-preplan` flag implementation
2. Copying the preplan into `<project>/docs/preplan.md`
3. Adding an AGENTS.md reference line in the project: `Preplan: docs/preplan.md`
4. Adding Step 2.5 to `docs/traycer/fabrik-workflow.md` so Traycer reads `docs/preplan.md` BEFORE the epic-brief stage

This consolidates v1's G-C3 (which was orphaned).

### `--from-preplan` behavior

Reads the preplan file and:
1. Extracts `## 2. Project type` to default the `--type` flag (with confirmation prompt if not specified).
2. Extracts `## 3. Shape preview` and merges into the generated spec's `shape:` block.
3. Extracts `## 5. Domain` and uses for the `domain` field.
4. Copies the entire preplan into the new project as `docs/preplan.md`.
5. Adds a reference line to the project's AGENTS.md: `Preplan: docs/preplan.md`.

### Traycer workflow doc Step 2.5 addition

```markdown
### **Step 2.5: Preplan Ingestion**

If the project has `docs/preplan.md`, read it FIRST before any other research.
The preplan answers:
- What this project IS (Section 1)
- Project type (Section 2) — already enforced by scaffold
- Shape contract (Section 3) — already in the spec
- External deps (Section 4) — informs Step 4 reference reads
- Success criteria (Section 6) — drives epic-brief acceptance criteria
- Out of scope (Section 7) — hard limit on epic scope

Skip the redundant questions Step 3 would otherwise ask.
```

### Acceptance

- `fabrik scaffold tender --type python-api --from-preplan docs/preplans/2026-05-12-tender-platform-mvp.md` succeeds.
- Generated `specs/services/tender.yaml` includes the shape from the preplan.
- New `/opt/tender/docs/preplan.md` matches the source preplan.
- New `/opt/tender/AGENTS.md` references `docs/preplan.md`.
- `docs/traycer/fabrik-workflow.md` has the new Step 2.5.

---

## 22. G-C1 — Extend Traycer workflow doc to cover deploy phase

**Effort:** 1 hour (unchanged from v1)
**File:** `docs/traycer/fabrik-workflow.md`

After `## implementation-validation` and before `## revise-requirements`, add:

```markdown
## deploy

### Role
After implementation-validation passes, a separate Traycer planner role drives the deploy phase. This is NOT the same role as the coder.

### Core Philosophy
- The spec is the deploy contract. Code that contradicts the spec is a code bug, not a deploy bug.
- `fabrik apply` is zero-touch by default. Manual VPS edits are anti-patterns.
- `fabrik audit-registrars` is the source of truth for live state matching the spec.
- `fabrik destroy` is reversible only via redeploy from spec.

### Processing User Request
1. Confirm spec exists at `specs/services/<id>.yaml`.
2. Run `fabrik plan specs/services/<id>.yaml` — review the resolved registrar list.
3. If shape contradictions surface, revise the spec, NOT the deploy.
4. Run `fabrik apply specs/services/<id>.yaml`.
5. After successful apply, run `fabrik verify <domain> --spec registrars`.
6. If any registrar is missing post-apply, treat as a deploy bug. Do NOT manually patch the VPS.
7. Update the project's `docs/preplan.md` front-matter status: `delivered`.

### Acceptance Criteria
- All applicable registrars present per `fabrik audit-registrars`.
- `fabrik verify <domain> --spec registrars` exits 0.
- Project status in `data/projects.yaml` is `delivered`.
- No manual VPS edits made during the deploy.
```

### Acceptance

- `grep -c "fabrik apply" docs/traycer/fabrik-workflow.md` returns ≥1.
- `grep -c "registrar" docs/traycer/fabrik-workflow.md` returns ≥3.

---

## 23. G-C2 — `.windsurf/workflows/registrar-audit.md`

**Effort:** 30 minutes (unchanged from v1)
**File:** `.windsurf/workflows/registrar-audit.md` (new)

```markdown
# /registrar-audit

Run a registrar drift audit on the current spec or all specs.

## Usage
`/registrar-audit` — audit current project's spec
`/registrar-audit --all` — audit every spec under `specs/services/`

## Steps
1. Run `fabrik audit-registrars [--spec specs/services/<current>.yaml]`.
2. Review the output table with the user.
3. For each MISSING (✗) registrar:
   - Confirm the registrar SHOULD run (shape contract correct?).
   - Run `fabrik redeploy --refresh-infra --spec specs/services/<id>.yaml`.
4. For each DRIFT (⚠️) registrar:
   - Surface to user with both sides.
   - User decides; either edit spec OR remove live state via `fabrik destroy --partial <reg>` (G-F5).
5. Re-run audit; expect zero MISSING and zero DRIFT.

## Notes
- Do NOT manually edit VPS configs.
- If a registrar repeatedly fails, file an issue.
```

### Acceptance

- File exists at `.windsurf/workflows/registrar-audit.md`.

---

## 24. G-D1 — Add shape/registrar awareness to executor rule files (CORRECTED v2)

**Effort:** 1.5 hours (was 1; +0.5 for 5 files instead of 3)
**Files (5 total — corrected from v1's 3):** `AGENTS-compact.md`, `CLAUDE.md`, `.windsurfrules`, `AFCL.md`, `opencode.json`

### Current state (v2 corrected)

```bash
$ for f in AGENTS-compact.md CLAUDE.md .windsurfrules AFCL.md opencode.json; do
    echo "$f: $(grep -cE 'shape|registrar|fabrik apply|InfrastructureProvisioner' "$f" 2>/dev/null || echo 0)"
done
# Expected: 0 for all 5; only AGENTS.md has 6-7
```

All 5 are in `GOVERNANCE_FILES` (`scripts/sync_enforcement_to_projects.py`) and propagate to all 42 projects.

### Required snippet (insert into all 5 files)

```markdown
## Spec contract awareness

Every Fabrik project has `specs/services/<id>.yaml` with a `shape:` block that drives:
- Which Postgres DB / Redis index / Backrest plan / Gatus endpoint / Prometheus job / GlitchTip project / Authelia rule / Meilisearch index get auto-created on `fabrik apply`
- The shape contract is canonical: code MUST match it, not the other way around

If your code:
- Adds a database call → `shape.needs_database` MUST be `true` in the spec
- Adds a Redis cache → `shape.needs_cache` MUST be `true`
- Exposes `/metrics` → `shape.exposes_metrics` MUST be `true`
- Adds Meilisearch indexes → `shape.has_search_feature` MUST be `true`
- Adds an admin UI behind auth → `shape.is_admin_dashboard` MUST be `true`

If you change code in a way that affects any of the above, ALSO update `specs/services/<id>.yaml`.
Don't ship code that contradicts the spec — `fabrik apply` will skip the registrar and you'll have a silently broken deploy.

To preview what the spec will trigger: `fabrik plan specs/services/<id>.yaml`
```

For `opencode.json` (which is JSON, not markdown): do **NOT** embed the rule as a stringified JSON value — Kilo CLI won't surface it usefully and it'd be unreadable. Instead, take Option (a):

**Option (a) — Reference an external rules file (recommended):**
1. Create a new `KILO_CLI_RULES.md` at the repo root (and add it to `GOVERNANCE_FILES` in `scripts/sync_enforcement_to_projects.py` so it propagates to all 42 projects).
2. Copy the same shape/registrar markdown snippet into `KILO_CLI_RULES.md`.
3. In `opencode.json`, add (or extend) a `"rules_files": ["KILO_CLI_RULES.md", "AGENTS-compact.md"]` field so Kilo CLI loads them on context init.
4. Keep `opencode.json` as pure config — no embedded prose.

This gives the same propagation guarantee (file is in `GOVERNANCE_FILES`, hits all 42 projects) without polluting structured config with a markdown blob, and stays readable in editor + git diffs.

### Required propagation step (NEW v2 — addresses C5)

After editing the 5 files, the existing `governance-sync` pre-commit hook only fires on staged commits. Initial bulk propagation:

```bash
cd /opt/fabrik
python3 scripts/sync_enforcement_to_projects.py --force
# Watch for "synced X files to Y projects" — should report 5+ files × 42 projects
```

### Acceptance

- All 5 files have the snippet.
- `grep -c "shape" AGENTS-compact.md` ≥ 5.
- `grep -c "shape" CLAUDE.md` ≥ 5.
- `grep -c "shape" .windsurfrules` ≥ 5.
- All 42 `/opt/<project>/` clones have the updated files post-propagation.

---

## 25. G-D2 — Add registrar awareness to `.windsurf/rules/` cross-cutting files (5 OF 22 — CORRECTED)

**Effort:** 1 hour (unchanged from v1)
**Files:** `25-data-postgres.md`, `30-ops.md`, `55-observability.md`, `35-security-auth.md`, `65-rag-search.md` (out of 22 total `.windsurf/rules/` files)

### What goes where

| File | Add |
|---|---|
| `25-data-postgres.md` | "When adding a database call, ensure `shape.needs_database: true`. Postgres registrar auto-creates `<id_with_underscores>` DB; if you need a different name, use `infra.postgres: false` AND `shape.needs_database: true` (proxy.yaml pattern) and document the override." |
| `30-ops.md` | "All operational concerns flow through the spec's `shape:` block. Manual VPS edits are anti-patterns. Use `fabrik apply` / `fabrik audit-registrars` / `fabrik reconcile-all` / `fabrik destroy --partial`." |
| `55-observability.md` | "Service should expose `/metrics` only when `shape.exposes_metrics: true`. Service should expose `/health` always (Gatus depends on it when `shape.is_public: true`). GlitchTip DSN comes from `SENTRY_DSN` env injected by the orchestrator — do NOT hardcode." |
| `35-security-auth.md` | "Public services with admin UI behind 2FA: `shape.is_admin_dashboard: true` (registrar adds Authelia rule). API services with bearer auth on `/api/*`: `shape.has_bearer_api: true`. Don't add Traefik middlewares manually." |
| `65-rag-search.md` | "Meilisearch indexes are auto-created when `shape.has_search_feature: true`. Index name = `<id_with_underscores>`. Do NOT manually create indexes via the Meilisearch API." |

### Required propagation step

Same as G-D1: `python3 scripts/sync_enforcement_to_projects.py --force` after editing.

### Acceptance

- 5 of the 22 `.windsurf/rules/*.md` files mention shape/registrar.
- All 42 projects have the updated rules post-propagation.

---

## 26. G-D3 — `fabrik review` bundle-and-dispatch

**Effort:** 1 hour (unchanged from v1)
**File:** `src/fabrik/cli.py` — new subcommand

### Behavior

```
$ fabrik review
📦 Bundling review pack...
   - git diff (last commit) ............. 234 lines
   - specs/services/<id>.yaml ........... 56 lines
   - docs/preplan.md (if exists) ........ 89 lines
   - resolved registrars ................ 4 RUNS, 5 skipped
✅ Bundle saved to .fabrik/review/2026-05-12-103045.md
   Dispatch with:
     kilo run --agent reviewer --input .fabrik/review/2026-05-12-103045.md
```

### Acceptance

- `fabrik review` produces a single .md file in `.fabrik/review/`.
- Bundle includes diff, spec, preplan (if exists), resolved registrars.
- `.fabrik/review/` is gitignored.

---

## 27. G-I1 + G-I2 — `fabrik dev` + `fabrik logs --local`

**Effort:** 1 hour (unchanged from v1)
**File:** `src/fabrik/cli.py` — two new subcommands

### `fabrik dev`

```python
@cli.command()
@click.option("--project", default=".", help="Project directory")
@click.option("--detach", "-d", is_flag=True)
def dev(project: str, detach: bool):
    project_dir = Path(project).resolve()
    compose_file = project_dir / "compose.dev.yaml"
    if not compose_file.exists():
        click.echo(f"✗ No compose.dev.yaml in {project_dir}", err=True)
        raise SystemExit(1)
    args = ["docker", "compose", "-f", str(compose_file), "up"]
    if detach:
        args.append("-d")
    subprocess.run(args, cwd=project_dir, check=False)
```

### `fabrik logs --local`

```python
@logs.command()
@click.option("--local", is_flag=True)
@click.option("--service", help="Specific service from compose.dev.yaml")
@click.option("--follow", "-f", is_flag=True, default=True)
def local(local: bool, service: str, follow: bool):
    args = ["docker", "compose", "-f", "compose.dev.yaml", "logs"]
    if follow:
        args.append("-f")
    if service:
        args.append(service)
    subprocess.run(args)
```

### Acceptance

- `fabrik dev` in a scaffolded project starts the dev stack.
- `fabrik logs --local -f` tails docker logs.

---

## Tier 3 done — convergence test

After all 9 items:

```bash
# 1. Preplan flow end-to-end
fabrik preplan new test-tier3-demo
ls docs/preplans/2026-05-*-test-tier3-demo.md
fabrik scaffold test-tier3-demo --from-preplan docs/preplans/$(date +%Y-%m-%d)-test-tier3-demo.md
ls /opt/test-tier3-demo/docs/preplan.md
grep "preplan" /opt/test-tier3-demo/AGENTS.md

# 2. Traycer workflow doc updated
grep -c "fabrik apply" docs/traycer/fabrik-workflow.md   # ≥ 1
grep -c "registrar" docs/traycer/fabrik-workflow.md      # ≥ 3

# 3. All 5 executor rule files updated (NOT just 3)
for f in AGENTS-compact.md CLAUDE.md .windsurfrules AFCL.md opencode.json; do
  echo "$f: $(grep -c shape $f 2>/dev/null || echo 0)"
done
# Expect: each ≥ 5 (opencode.json may use a different key but should reference shape)

# 4. Cascade workflow accessible
ls .windsurf/workflows/registrar-audit.md

# 5. Bulk propagation worked: 42 projects synced
ls /opt | wc -l         # ~42
for d in /opt/{captcha,site-provisioner,emailgateway}; do
    grep -c shape "$d/AGENTS-compact.md" 2>/dev/null
done
# Expect: ≥ 5 in each

# 6. Review bundle works
cd /opt/some-deployed-project
fabrik review
ls .fabrik/review/*.md

# 7. Local dev works
fabrik dev -d
fabrik logs --local -f
```

If all 7 pass, the planning + coding loop is fully specified.
