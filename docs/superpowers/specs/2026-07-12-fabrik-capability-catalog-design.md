# Design Spec — Fabrik Capability Catalog + Tool-Doc Audit

**Status:** CONVERGED (2026-07-12) — `/fabrik-spec-review` fixed point. Pass 1 (all axes) corrected the
AGENTS.md characterization (its audience is planner/orchestrator AI agents — Traycer / Kilo / Claude-Code-as-
orchestrator — not humans; still prose, not a machine-invokable manifest) + the success-criteria arithmetic
(267 raw, not 207); Pass 2 fixed a heading; Pass 3 re-grounded all axes with **zero edits** (md5 `100da1b5`
start = end). Re-verified this session: llms.txt + agents.md standards (fetched 2026-07-12, citations support
the claims); the in-repo precedent scripts (`generate_model_capabilities.py` + `verify_openrouter_catalog.py`)
and doc-audit reuse targets exist; `docs/CAPABILITIES.md` + `generate_capability_index.py` still absent; no
fabrik-lib repo-introspection module (BUILD confirmed). No BLOCKING unknowns.

**Provenance.** The real goal behind the (now-archived) empire operating-model plan: a builder who wants **any
AI agent entering the fabrik repo to discover and correctly use every tool with zero human onboarding.** This
spec grounds *that* — a verified capability catalog + a documentation audit — inheriting only the reusable idea
from the archived plan's §Agent-enablement (a **generated, self-verifying** capability index, never
hand-curated). Grounded 2026-07-12.

---

## Goal

Produce and keep-current a **single, machine- and human-readable catalog of every invokable capability in the
fabrik repo**, each entry verified to actually work, so a cold AI agent reads one file first and knows *what it
can do and how to invoke it* — plus bring every tool's **documentation into line with reality** (fix stale,
delete dead) as a side effect of the verification pass.

**Success in one line:** a fresh agent, given only `docs/CAPABILITIES.md` + `capabilities.json`, can list and
correctly invoke any fabrik tool; every listed entry's `--help`/import/`--check` actually returns 0; broken
ones are flagged, not offered.

**Explicitly out of scope:** the operating-model / monetization / project-selection machinery (removed — the
builds serve known customers); teaching agents *how to write code here* (that stays `AGENTS.md` + `.windsurf/rules`).

---

## The surface to catalog (grounded 2026-07-12)

| Surface | Count | Source of truth |
|---|---|---|
| `fabrik` CLI verbs | **23** | `@cli.command(` in `src/fabrik/cli.py` |
| Drivers | **27** | `src/fabrik/drivers/*.py` |
| Registrars | **10** | `src/fabrik/orchestrator/infrastructure.py:90` `_REGISTRAR_ORDER` |
| Scripts | **82** | `scripts/*.py` + `scripts/*.sh` |
| fabrik-lib modules | **~55** (110 raw README rows incl. the capability matrix — de-dup to dir-backed) | `/opt/fabrik-lib/README.md` table + real dirs |
| Scaffolds | **20** | `templates/*/` |
| `.windsurf/rules` packs | **50** | `.windsurf/rules/**/*.md` |

Existing agent-facing docs that this **complements** (does not duplicate): `AGENTS.md` (625 lines) +
`AGENTS-compact.md` — natural-language *how-to-work-here instructions* read by **planner/orchestrator AI
agents** (Traycer, Kilo Code orchestrator, Claude Code used as orchestrator/planner), not by humans; and
`INDEX.md` (762 lines — *file*-purpose index). **None is an invokable-capability catalog** an agent can
enumerate + call from — and **`docs/CAPABILITIES.md` is absent** (verified). The catalog serves those same
orchestrator agents: `AGENTS.md` says *how to work here*, `capabilities.json` says *what tools exist to invoke*.

---

## Chosen approach

**A generated, self-verifying two-layer catalog + a doc-audit that rides the verification pass.**

1. **`capabilities.json` (machine-readable, the invokable layer).** One record per capability:
   `{ name, kind (cli|driver|registrar|script|lib-module|scaffold|rules-pack), summary, invoke (the exact
   command / import), status (ok|broken|manual), doc_link, verified_at }`. This is the layer AGENTS.md/INDEX.md
   don't provide — a structured manifest an agent parses to *discover and call* tools.
2. **`docs/CAPABILITIES.md` (human/LLM-readable) — follows the llms.txt convention** (see External deps): H1 +
   a blockquote summary + one H2 section per `kind`, each a markdown link-list `[name](doc_link): summary`.
   Generated from the same records so the two never drift.
3. **Self-verifying generation (never hand-curated).** For each entry the generator runs a cheap liveness
   probe — CLI verb → `fabrik <verb> --help` exit 0; lib module → `import`; script → `--help`/`--check` or a
   header parse; scaffold → dir + required files present; rules pack → file parses. A probe that errors ⇒
   `status:"broken"`, listed as a defect, **excluded from the "usable" set** an agent is offered.
4. **Doc-audit as a by-product (goal #2).** The same pass reconciles each entry's existing doc to reality —
   **extending the existing** `scripts/doc_reconcile.py` / `docs_updater.py` / `check_docs.py` (not a new
   engine): a capability whose doc is missing/stale is flagged; the reconcile loop fixes or the entry links to
   the authoritative doc. Dead docs (a documented tool that no longer exists) are deleted.
5. **Regenerated by the existing daily pipeline** (`scripts/wsl_startup_hook.sh` +
   `scripts/kilo-benchmarks/daily_refresh.sh`) so the catalog never rots — it's a build artifact, re-derived,
   not a document someone maintains by hand.

**Pattern to follow (in-repo precedent):** `scripts/kilo-benchmarks/generate_model_capabilities.py` +
`verify_openrouter_catalog.py` already do exactly "generate a catalog + verify each entry" for *models* — the
tool catalog is the same shape applied to the repo's own tools. Reuse the structure, not a copy.

### Rejected alternatives

- **Hand-curated `CAPABILITIES.md`** — rejected: it rots the day it's written (the empire plan's own lesson —
  counts drift under parallel agents). Must be generated + verified.
- **A new fabrik-lib "repo-introspection" module** — rejected: no such module exists and this is
  fabrik-hub-specific (introspects *this* repo's CLI/drivers/registrars); it fails the generic-reusable bar
  (§verdict). `doc-crawl/` is external-site crawling, not repo introspection.
- **AGENTS.md-only (extend the existing file)** — rejected: AGENTS.md is prose *instructions* for
  planner/orchestrator agents, not a machine-parseable invokable manifest (per the agents.md standard); an
  orchestrator can't reliably *enumerate + call* tools from prose. Keep AGENTS.md as orchestrator instructions;
  add the JSON manifest for discovery.

---

## External dependencies (grounded live 2026-07-12)

- **llms.txt standard** — `https://llmstxt.org/` (fetched 2026-07-12). A `/llms.txt` markdown file for
  LLM-friendly content discovery: **required H1** (project name) + **blockquote** summary + optional body +
  **H2 sections that are markdown link-lists** (`[name](url): notes`), designed for both human and programmatic
  parsing. → **`docs/CAPABILITIES.md` adopts this structure**, and the design adds an optional root `/llms.txt`
  that points at it (the standard's canonical location). No SDK, no runtime dep — it's a file format.
- **AGENTS.md convention** — `https://agents.md/` (fetched 2026-07-12). A "README **for agents**" — standard
  Markdown, no schema, 60k+ projects — whose audience is **AI planner/orchestrator agents** (Traycer, Kilo
  orchestrator, Claude Code-as-orchestrator), i.e. natural-language *instructions* those agents parse, **not**
  a human doc and **explicitly not a machine-readable capability manifest** (the standard "deliberately avoided
  proprietary machine formats"). → confirms the split: `AGENTS.md` = how-to-work instructions for orchestrators
  (already present, keep), the new `capabilities.json` = the machine-invokable tool-discovery layer for those
  same orchestrators. No dep.

*No 3rd-party API/SDK/pricing is involved — the catalog is generated from the local repo. Both external items
are format conventions, not services.*

---

## fabrik-lib vendor → enhance → build verdict

| Capability | Verdict | Where | Note |
|---|---|---|---|
| Repo introspection (enumerate CLI verbs / drivers / registrars / scripts / modules / scaffolds / rules) | **BUILD** | new `scripts/generate_capability_index.py` | No module introspects *this* repo; fabrik-hub-specific. Follow the `generate_model_capabilities.py` + `verify_*` pattern. |
| Per-entry liveness verify (`--help` exit 0 / import / dir-check) | **BUILD** | in the generator | Same pattern as `verify_openrouter_catalog.py` (catalog + verify). |
| Doc audit / reconcile each tool's doc to reality | **VENDOR + ENHANCE (in-repo scripts)** | extend `scripts/doc_reconcile.py` + `docs_updater.py` + `enforcement/check_docs.py` | The reconcile loop exists; feed it the catalog's stale/broken set. Enhancement stays in these hub scripts (not a fabrik-lib fork). |
| Machine-readable manifest format | **BUILD (trivial)** | `capabilities.json` schema | A small JSON schema; no module needed. |
| Human/LLM-readable catalog format | **VENDOR the standard** | llms.txt structure | Adopt the format, emit `docs/CAPABILITIES.md` + optional `/llms.txt`. |
| Daily regeneration | **VENDOR (existing)** | `wsl_startup_hook.sh` + `daily_refresh.sh` | Wire the generator in; it already runs the model-catalog refresh. |

**🆕 fabrik-lib candidate:** *none clears the bar* — repo-introspection is fabrik-hub-specific (fails the
generic + ≥2-project-type test). If a *generic* "verify-a-CLI's-subcommands → manifest" primitive later proves
reusable across hubs, revisit; for now it's hub-local.

---

## Shape / infra implications

- **Not a new scaffold / not a deployed service.** This is **hub-side tooling** in `/opt/fabrik`: a new
  `scripts/generate_capability_index.py`, enhancements to existing `scripts/`, and two generated artifacts
  (`docs/CAPABILITIES.md`, `capabilities.json`, optional `/llms.txt`). No DB, cache, metrics, search, auth, or
  admin — no `shape:` flags. It reads the live system (files + `fabrik --help` + `docker ps` for a live-state
  block) and writes docs.
- **Doc allowlist:** `docs/CAPABILITIES.md` is a root/`docs/` doc (allowlisted); `capabilities.json` is a
  generated artifact. `INDEX.md` gets one row for each new file (Doc Sync Matrix).

---

## Decomposition (2 components — buildable together or phased)

Tightly coupled (the generator's verify pass *is* the doc-audit's discovery), so one spec, but two clean phases:

- **C1 — Catalog generator + manifest.** `generate_capability_index.py` enumerates all 7 surfaces, runs the
  liveness probe per entry, emits `capabilities.json` + `docs/CAPABILITIES.md` (llms.txt-style) + optional
  `/llms.txt`; wire into the daily pipeline. *(Ships standalone value: the catalog exists + self-verifies.)*
- **C2 — Doc audit/reconcile.** Feed C1's `status:"broken"` + stale-doc set into the extended
  `doc_reconcile.py`/`docs_updater.py` loop; fix or delete; re-run until the catalog is all-`ok`/documented.
  *(Depends on C1's output.)*

Recommended: build **C1 first** (the catalog is the higher-value, standalone deliverable), then C2.

---

## Success criteria (testable)

- **C1:** `python scripts/generate_capability_index.py` writes `capabilities.json` + `docs/CAPABILITIES.md`;
  `jq '.capabilities | length' capabilities.json` ≥ the grounded surface count (23+27+10+82+~55+20+50 = **267**
  raw, so **≥ ~250** after de-duping the fabrik-lib capability-matrix rows); every `status:"ok"` entry's `invoke` returns 0 on `--help`/import; a deliberately-broken entry
  re-scans to `status:"broken"` and is excluded from the usable set; `docs/CAPABILITIES.md` parses as valid
  llms.txt (H1 + blockquote + H2 link-lists).
- **C2:** every catalog entry has a live `doc_link` OR is flagged; `python scripts/enforcement/check_docs.py`
  green; no documented-but-absent tool remains (dead-doc count 0).
- **Freshness:** the daily pipeline regenerates the catalog; the live-state block carries a `docker ps`
  timestamp ≤24h old.

---

## Residuals / open items

- **Verify depth (self-service default):** liveness = `--help` exit 0 / import / dir-check (cheap, no side
  effects) — NOT executing the tool for real (some tools mutate prod). Default applied; the plan can deepen it
  per-kind if a `--help` pass proves too shallow.
- **`capabilities.json` location (self-service default):** repo root `capabilities.json` (next to a root
  `/llms.txt`), mirrored/linked from `docs/`. Decide finally in the plan.
- **De-dup of the 110 raw fabrik-lib README rows → ~55 modules (self-service):** the generator counts
  dir-backed module rows only (the capability-matrix table repeats names); handled in C1.
- No BLOCKING unknowns — everything is local repo introspection + two file-format conventions grounded this
  session.

---

## Handoff

On approval: data/field-shaped? Minimal (`capabilities.json` is a generated artifact, not a persisted user
schema) — so the applicable next is **`/fabrik-plan-after-chat`** (no data-contract/UI-design needed; it's
headless hub tooling). The plan inherits this spec's grounding (the surface counts, the llms.txt/AGENTS.md
format decision, the vendor verdict: BUILD the generator following the `generate_model_capabilities.py` pattern,
EXTEND the existing doc-reconcile scripts) + does the full build grounding.

💡 **fabrik-lib candidates:** none (repo-introspection is hub-specific).
