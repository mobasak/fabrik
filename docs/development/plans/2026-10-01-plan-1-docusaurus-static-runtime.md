# Plan — docusaurus scaffold: static nginx runtime, Pagefind search, registry versions

Status: CONVERGED (/fabrik-plan-review, 2026-10-01, 4 passes; D-476)
Profile: small
**Owner:** —

Spec: `docs/superpowers/specs/2026-10-01-docusaurus-static-runtime-design.md` (CONVERGED, D-472; operator
approval "ok approved" 2026-10-01, D-475). Work item: W-3f2d8e21. Beat: fleet (scaffolding).
Research ledger: `docs/reference/research/2026-10-01-docusaurus-static-runtime-ledger.md` (55 rows; the 17
plan-time rows are `dsb-*`, `pfc-*`, `dsr-*`).

## What this plan is

Three phases that build spec § The delta parts 1–8 exactly as the spec settles them. Phase A makes the
version registry readable by code and teaches `template_renderer.py` to render nested files with `versions` and
`name` in its context. Phase B rewrites the docusaurus templates and the scaffold emitter onto them, and aligns
the spec generator's health path. Phase C proves the result with one opt-in real `docker build` and closes the
plan (whole-plan review, docs review, gate).

**Profile: small — the count, stated so a reviewer can rule on it.** Code diff estimated at ~210 lines across
5 Python files (`src/fabrik/version_registry.py` new, `template_renderer.py`, `scaffold.py`,
`spec_generator.py`, `orchestrator/deployer_ssh.py`) plus 7 template files (`Dockerfile.j2`, `compose.yaml.j2`,
`defaults.yaml`, `package.json.j2`, and the new `nginx.conf.j2`, `src/pages/index.js.j2`,
`src/theme/SearchBar/index.js.j2`). The ≤5-file bound is read here as the Python code surface; the templates are
emitted artifacts of 5–35 lines each; `templates/docusaurus/README.md` (File Scope) is a hand-edited doc the
scaffold never copies, so it is counted with neither. If the review reads the templates as code files
(12 > 5), the profile is
wrong and the plan becomes a 3-ticket set with the same phases — the content does not change, only the
execution profile.

## Intake Inventory

The operator's words this run: "ok approved" (the design gate, 2026-10-01). Every other item comes from the
approved spec's own Intake Inventory (`spec § Intake Inventory`, I1–I9) and the two items the spec routed to
the plan (`spec § Open / blocking unknowns`).

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "`templates/docusaurus/Dockerfile.j2` ends in `node:22-bookworm-slim` running `npm run serve`" | IN | Phase B steps 3–4, 7 |
| I2 | "NO Pagefind anywhere … the pack's § Search is unreachable in every scaffolded site" | IN | Phase B step 6; Phase C |
| I3 | "hardcoded `node:22` + `bookworm` against `versions.yaml`'s node_lts 24 / trixie" | IN | Phase A steps 2–3; Phase B step 7 |
| I4 | "every existing docusaurus project's next redeploy inherits it" | IN | § Residual unknowns R1 (no live project; the inventory check) |
| I5 | "Sized as a scaffold change with a rendered-output grader" | IN | Phase B step 10; Phase C step 2 |
| I6 | The same version literals in six other templates | OUT-OF-SCOPE | W-d6da74e5 (exists; reuses Phase A's loader) |
| I7 | Docusaurus 3.7.0 → 3.10.2 | OUT-OF-SCOPE | W-cdf69863 (exists) |
| I8 | The remaining 42-docusaurus divergences | OUT-OF-SCOPE | W-9aca7862 (exists) |
| I9 | The pack's `try_files` rule loops without a root page and masks 404s | IN (root page) + mailed | Phase B step 5; mails 01M3V92T8N, 01M3VAZQPV (infra) |
| I10 | "template_renderer.py has no `name` in its render context" (`spec § Open / blocking unknowns`) | IN | Phase A step 3 |
| I11 | "`spec_generator.py:112` keeps `health_path: "/docs/intro"`" (`spec § Review record`, recorded) | IN | Phase B step 9 |
| I12 | "Is the `fabrik-test-docusaurus` E2E container … still running on vps1?" (`spec § Open / blocking unknowns`) | IN (resolved from the inventory) | § Residual unknowns R1 |

Intake: 12 items — 9 IN, 3 OUT-OF-SCOPE (each named above), 0 ASK.

## What we already agreed (citations, not restatement)

- The goal and the shape of every emitted artifact: `spec § Goal`, `spec § Contract deltas`.
- One validated version source for both emitters: `spec § The delta` part 1.
- The two-stage Dockerfile and its four recorded deviations from the pack block: `spec § The delta` part 2.
- nginx.conf (`absolute_redirect off`, the pack's `try_files`, gzip, `/assets/` immutable only): part 3.
- The root redirect page: part 4. Search = Pagefind CLI + one swizzled `SearchBar` with the Component UI: part 5.
- Recursive `*.j2` rendering, both emitters writing every file: part 6. Port 80, no middleware: part 7.
- package.json: `pagefind ^1.5.2` devDependency, no `serve`, `engines.node` from the registry: part 8.
- Rejected: `docusaurus-plugin-pagefind`, `@getcanary/docusaurus-theme-search-pagefind`, the legacy Default UI,
  keeping Node, deploy-time version rendering, `nginx-unprivileged`: `spec § Rejected alternatives`.
- The pack conflicts are infra's and are NOT built here: `spec § Pack conflicts` (mails 01M3V92T8N, 01M3VAZQPV).
- The validation set this plan must make executable: `spec § Validation` 1–4.
- Operator approval of the design: "ok approved" (2026-10-01) → D-475.

**Plan-level decisions (the spec left them to the plan; recorded in D-475):**

1. **The loader's home is a new module, `src/fabrik/version_registry.py`.** `grep -rn "versions.yaml"
   src/fabrik/` finds no helper; the only reader is `scripts/sysadmin/rules_render_versions.py:54`
   (`load_versions`), which `src/fabrik` cannot import. A function inside `scaffold.py` (7,600 lines) would make
   `template_renderer.py` import the whole scaffolder; W-d6da74e5 will reuse the module for six more templates.
2. **The registry path resolves from the code's own tree, `fabrik.config.PROJECT_ROOT`** (file-anchored,
   `src/fabrik/config.py:25`), the same anchor `TemplateRenderer` uses for its templates
   (`src/fabrik/template_renderer.py:33-35`). `FABRIK_ROOT` was rejected: it follows the CWD's git toplevel
   (`config.py:34-68`), so from `/tmp` it names the hub while the imported code and the renderer's templates come
   from a worktree — executed in review pass 1 (§ Evidence E9). The scaffold's `DOCUSAURUS_TEMPLATE_DIR` already
   uses `FABRIK_ROOT` (`scaffold.py:238`); that pre-existing split is left alone, and every test this plan adds
   runs with the worktree root as its CWD (pytest from the repo root), where both anchors agree.
3. **The SearchBar emits Pagefind's stylesheet and module script through `@docusaurus/Head`**, so both land in
   the statically rendered `<head>` of every page. Pagefind documents no dynamic injection after load (ledger
   pfc-7, NOT FOUND), so the plan does not rely on it; the two custom elements are rendered in JSX
   (pfc-2..pfc-5).
4. **The scaffold's Jinja environment matches the renderer's whitespace settings** (`trim_blocks`,
   `lstrip_blocks`) and differs only where the spec says it must (autoescape off, `StrictUndefined`,
   `keep_trailing_newline`). Executed: the renderer drops a template's final newline and the scaffold keeps it,
   so the parity test compares with trailing newlines stripped (§ Evidence E3). Each `{% raw %}` opens on the
   same line as the first character of the body, because the newline after `{% raw %}` survives under both
   settings (E3).
5. **The real build test is opt-in by `FABRIK_REAL_DOCKER_BUILD=1`** and skipped with its reason otherwise. It
   differs from the real-PG pattern (`tests/test_app_role_real_pg.py:100-125`, which runs whenever docker is up)
   because it pulls two images and the npm registry and takes minutes. With the flag set, a missing docker is a
   failure, not a skip (the real-PG `REQUIRE` semantics).
6. **`template_renderer.py` adds `name` = `spec.id` to its context** (closes I10). Only docusaurus templates read
   `name` through the renderer (`grep` over `templates/*/*.j2`: `AGENTS.md.j2`, `docusaurus.config.js.j2`,
   `package.json.j2`; the `modal` templates also use `name` but have no `compose.yaml.j2`, so the renderer never
   renders them), so no other template's output changes.

## Global Constraints (every phase inherits these)

- Infra invariants for the emitted compose: external `fabrik` network, no host `ports:`, `container_name`
  mandatory, `deploy.resources.limits.memory` mandatory, `platform: linux/amd64` mandatory, Traefik routes. Public
  services carry no Traefik middleware ("public: none", `core/30-ops.md:195`).
- Base images come only from `.windsurf/rules/versions.yaml` `versions` (`node_lts`, `debian_codename`,
  `node_engines_floor`) through `fabrik.version_registry.load_versions()`; no Node or Debian version literal in
  any base image or in `engines.node`. npm package pins stay literal in `package.json.j2` (`pagefind ^1.5.2`, the
  Docusaurus `3.7.0` pins — W-cdf69863 — and the existing `engines.npm`). Debian `-slim` for the Node builder; the
  pack-mandated `nginx:mainline-<codename>` for the server.
- No new dependency: `jinja2` and `PyYAML` are already imported by `src/fabrik/template_renderer.py:13-14`;
  `pyproject.toml`/`uv.lock` are not touched (`core/10-python.md:30`).
- 12-Factor, as it binds this surface: **II** — every binary the image runs is installed in the Dockerfile
  (curl, nginx in the base image, `pagefind` as a devDependency); **V** — releases are immutable: a scaffolded
  project's versions are frozen into its own repository at scaffold time (`spec § Rejected alternatives`); a
  `source: type: template` spec has no repository of its own — `fabrik apply` re-renders it from the hub's
  templates on every deploy (`src/fabrik/orchestrator/deployer_ssh.py:452`), so its release is the hub commit
  holding the templates and the registry, and a registry bump (itself a hub commit) moves its base image on the
  next apply exactly as any template edit does today; **VII** — the
  container binds port 80 inside, Traefik routes, no host `ports:`; **XI** — nginx logs to stdout/stderr as the
  stock image does, no logfile is configured; **III/IV/VI/VIII/IX/X/XII** — not engaged (no config, backing
  service, session, process manager, worker, database or migration is added).
- Tests: watched-fail-first for every behaviour this plan adds (`core/45-testing-strategy.md:22`); no cosmetic
  assertions (`:21`); a guard is proven on the class, not on one spelling (`:199`).
- Seats never mutate git state (read-only git only: `show`, `diff`, `log`, `status`, `ls-files`); never read
  `~/.claude*`; never run `fabrik apply` or touch a VPS. The shared `.venv` imports `fabrik` from `/opt/fabrik/src`
  — every test run from the worktree exports `PYTHONPATH=/opt/fabrik/.claude/worktrees/fleet/src` inside a
  runner script.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `core/42-docusaurus.md` (MUST-READ, the spec's pack) | no Node runtime; two-stage build; nginx serve; `try_files`; Pagefind; the one swizzle | `.windsurf/rules/core/42-docusaurus.md:26`, `:32-33`, `:53`, `:92`, `:105` |
| `core/10-python.md` (ACTIVE: `scaffold.py`, `template_renderer.py`, `spec_generator.py`) | no deps-file edits; pinned Debian `-slim` | `.windsurf/rules/core/10-python.md:30`, `:254` |
| `core/45-testing-strategy.md` (ACTIVE: the test file) | one test per behaviour; watched-fail-first; no cosmetic assertions; class-proof guards | `.windsurf/rules/core/45-testing-strategy.md:20-22`, `:199` |
| `core/40-documentation.md` (MATCHED: the plan, the receipt, the template README) | no skipped heading levels; fenced code only | `.windsurf/rules/core/40-documentation.md:241`, `:243` |
| `ai/50-agentic.md` (MATCHED by its `**/orchestrator/**` glob on `deployer_ssh.py`) | not engaged: the plan adds no model or agent call | `.windsurf/rules/ai/50-agentic.md:3`, `:16` |
| `core/30-ops.md` (FLOOR) | no `ports:`; `container_name`; immutable releases; public = no middleware | `.windsurf/rules/core/30-ops.md:148`, `:150`, `:195`, `:266` |
| `core/35-security-auth.md`, `core/25-data-postgres.md` (FLOOR) | not engaged: no auth, secret, database or session surface is touched | read; no row applies |
| `fabrik-lib` | no module covers a static-site stack or search UI — build in the hub's templates; not a candidate | `spec § fabrik-lib verdict` |
| `agents-fabrik.md` § Scaffold Types | the docusaurus row (`static`, `is_public`) is unchanged | `agents-fabrik.md:428` |
| `specs/services/<id>.yaml` `shape:` | no flag changes; `shape.kind: static` stays | `templates/docusaurus/defaults.yaml:6-13` |
| data/UI contracts | none exist for scaffold templates | `spec § Contract deltas` |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Verbatim | file:line | Rule |
|---|---|---|
| "Running `docusaurus serve` or any Node.js runtime in a production container is banned — it wastes RAM serving what should be static files." | `.windsurf/rules/core/42-docusaurus.md:26` | No Node runtime |
| "`npm ci` then `npm run build`, then `npx -y pagefind --site build` for search indexing." | `.windsurf/rules/core/42-docusaurus.md:32` | Build stage (the install line deviates: lockfile-conditional, `spec § The delta` part 2) |
| "copy `build/` to `/usr/share/nginx/html`." | `.windsurf/rules/core/42-docusaurus.md:33` | Serve stage |
| "The Nginx config must include `try_files $uri $uri/ /index.html;`" | `.windsurf/rules/core/42-docusaurus.md:53` | SPA fallback |
| "Cache static assets aggressively: `Cache-Control: public, max-age=31536000, immutable` for JS/CSS/fonts/images/WASM." | `.windsurf/rules/core/42-docusaurus.md:53` | Asset caching (narrowed to `/assets/`, spec § Pack conflicts 5) |
| "no `ports:` section (Traefik routes traffic), `deploy.resources.limits.memory` mandatory, `platform: linux/amd64` mandatory." | `.windsurf/rules/core/42-docusaurus.md:88` | Compose |
| "Use **Pagefind**" | `.windsurf/rules/core/42-docusaurus.md:92` | Search engine |
| "**the one sanctioned swizzle**" | `.windsurf/rules/core/42-docusaurus.md:105` | The SearchBar swizzle |
| "**No `ports:` section.** All external traffic routes through Traefik. Never bind host ports." | `.windsurf/rules/core/30-ops.md:148` | No ports |
| "**`container_name: <name>` is mandatory.**" | `.windsurf/rules/core/30-ops.md:150` | Container name |
| "Traefik middleware set per service category — admin UI: `authelia-forward@docker,gzip@docker`; API: `gzip@docker`; public: none" | `.windsurf/rules/core/30-ops.md:195` | Middleware |
| "Releases are IMMUTABLE; the git SHA is the release ID." | `.windsurf/rules/core/30-ops.md:266` | Immutable releases |
| "Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it." | `.windsurf/rules/core/10-python.md:30` | Deps files |
| "Base image is always the pinned Debian `-slim` variant on `linux/amd64`" | `.windsurf/rules/core/10-python.md:254` | Base image |
| "**No skipped heading levels** — `##` to `###`, never `##` to `####`" | `.windsurf/rules/core/40-documentation.md:241` | Headings |
| "**Fenced code blocks only** — never indented code (AI treats it inconsistently)" | `.windsurf/rules/core/40-documentation.md:243` | Code blocks |
| "**Purpose:** Multi-step reasoning or tool use." | `.windsurf/rules/ai/50-agentic.md:16` | Agentic AI — MATCHED only through the pack's `**/orchestrator/**` glob on `deployer_ssh.py`; the plan adds no model call, so no row of it is engaged |
| "every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one**" | `.windsurf/rules/core/45-testing-strategy.md:20` | Behaviour tests |
| "never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes." | `.windsurf/rules/core/45-testing-strategy.md:21` | No cosmetic asserts |
| "a non-trivial behavior's test proves something only if it has been SEEN RED" | `.windsurf/rules/core/45-testing-strategy.md:22` | Seen red |
| "Write the guard's subject five LEGITIMATE ways" | `.windsurf/rules/core/45-testing-strategy.md:199` | Class proof |

Every selection below cites a digest row or the spec section that settled it. The nginx `-slim`/non-slim split
follows the pack's serve stage (`:33`), not `10-python.md:254`, which governs Python service images.

## Phase A — The version source and the template emitter

**Interfaces — Produces:**
- `src/fabrik/version_registry.py`:
  - `VERSIONS_FILE: Path = PROJECT_ROOT / ".windsurf" / "rules" / "versions.yaml"` (`PROJECT_ROOT` from
    `fabrik.config`, file-anchored — plan-level decision 2; a module attribute read at call time, so a test can
    `monkeypatch.setattr(version_registry, "VERSIONS_FILE", tmp)` and the patch reaches `scaffold.py`'s
    `from fabrik.version_registry import load_versions` too).
  - `REQUIRED_KEYS: tuple[str, ...] = ("node_lts", "debian_codename", "node_engines_floor")`.
  - `class VersionRegistryError(ValueError)`.
  - `def load_versions(path: Path | None = None) -> dict[str, str]` — reads `path or VERSIONS_FILE`, returns the
    `versions` map with every value as `str`; raises `VersionRegistryError` naming the file when it is missing,
    unparseable, or its `versions` is not a mapping, and naming the KEY when a required key is absent, `None`, or
    an empty/whitespace string.
- `TemplateRenderer.render(...)`: context gains `"versions": load_versions()` and `"name": spec.id`; every
  `*.j2` under the template dir renders recursively; the output key is the POSIX path relative to the template
  dir minus `.j2` (`src/pages/index.js.j2` → `"src/pages/index.js"`); writes create parent directories.
- `src/fabrik/orchestrator/deployer_ssh.py::_write_file_to_vps_path(path, filename, content)` (`:849-879`) — the
  deploy-time consumer of those keys (`_deploy_template` writes every rendered key with it, `:471-475`): when
  `filename` contains `/`, the remote command first runs `sudo mkdir -p {path}/{dirname(filename)}`, so a nested
  key lands on the VPS instead of failing the `sudo mv` into a missing directory. A flat filename's command is
  unchanged.
- **Mirror (named, accepted):** every template render now reads `versions.yaml`, and `fabrik apply` of every
  `source: type: template` spec renders (`deployer_ssh.py:452`; `src/fabrik/deploy_validator.py:100-101` only calls
  `template_exists` and never reads the registry), so a registry
  missing one of the three keys fails every template render AND every template-source deploy (python-api
  included), not only docusaurus — a hub without its registry is broken, and failing loud with the key's name
  beats rendering `FROM node:--slim` (`spec § The delta` part 1). Output keys of the other eight templates do not
  change: 0 of their `.j2` files are nested (E4). The Coolify deployer's render (`deployer_coolify.py:526`) reads
  only `compose.yaml` from the result.

**Consumes:** nothing from later phases.

1. **Write the failing tests first** in `tests/test_docusaurus_static_runtime.py` (Phase A's rows of the Behavior
   Contract below): a registry fixture in `tmp_path` (the three keys plus one unrelated key), the
   `VERSIONS_FILE` monkeypatch, a throwaway templates dir in `tmp_path` holding `t/compose.yaml.j2`,
   `t/a/b/x.txt.j2` (`{{ versions.node_lts }}-{{ name }}`), and a spec YAML in `tmp_path` with
   `template: t`, `source: type: template` (shape of `specs/services/test-docs.yaml`), loaded with
   `fabrik.spec_loader.load_spec`. Run them and **confirm they fail** for the right reason
   (`ModuleNotFoundError: fabrik.version_registry`, then the missing nested key).
2. Create `src/fabrik/version_registry.py` per the Interfaces. Header comment `# AFTER-EDIT: none` within the
   first 25 lines (doc↔script coupling convention; `src/` is not under `scripts/`, so it is optional — write it
   anyway for the W-d6da74e5 reader). Use `yaml.safe_load`; never `yaml.load`.
3. Edit `src/fabrik/template_renderer.py`:
   - import `load_versions` from `fabrik.version_registry`;
   - add `"versions": load_versions()` and `"name": spec.id` to the context dict (`:129-140`);
   - replace the top-level loop (`:160-165`) with a recursive one: `for j2_file in
     sorted(template_path.rglob("*.j2")):`, `rel = j2_file.relative_to(template_path)`, skipping only
     `rel.as_posix() in ("compose.yaml.j2", "Dockerfile.j2")` (the two top-level files already rendered — compared
     by relative path, so a nested file of the same name still renders), render
     `f"{spec.template}/{rel.as_posix()}"`, key `rel.with_suffix("").as_posix()`;
   - in the write loop (`:211-219`) call `file_path.parent.mkdir(parents=True, exist_ok=True)` before `open`.
3b. Edit `src/fabrik/orchestrator/deployer_ssh.py::_write_file_to_vps_path` per the Interfaces: prefix the
   remote command with `sudo mkdir -p {path}/{posixpath.dirname(filename)} && ` when `"/" in filename`. Its
   test is a NEW direct test of `_write_file_to_vps_path` in `tests/orchestrator/test_deployer_ssh.py` (every
   existing reference there patches the writer away), with `fabrik.drivers.ssh.ssh` and `scp_to_vps` patched
   (no VPS is reached).
   Leave the Jinja environment (`:43-48`) unchanged: autoescape stays on for `.j2` (it escapes only variable
   output — E3). The variables the docusaurus templates render cannot carry an HTML-special character: the
   registry values are digits and codenames, and `name` is the spec id, which `Spec.id` constrains to
   `^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$` (`src/fabrik/spec_loader.py:791-792`).
4. Run the Phase A tests green, then the renderer's existing consumers:
   `PYTHONPATH=<worktree>/src .venv/bin/python -m pytest tests/test_docusaurus_static_runtime.py
   tests/test_companion_services.py tests/test_scaffold_audit_log.py -q -k "render or template or companion"`
   — expect all pass (the audit-log module also needs `FABRIK_ROOT`-reachable templates; it is the existing
   real consumer of `TemplateRenderer.render`, `tests/test_scaffold_audit_log.py:226-238`).
5. **Red-on-revert** in a throwaway worktree (`git worktree add <scratch>/probe HEAD`, apply the phase diff,
   neuter one thing at a time, never in the shared checkout): (a) drop the missing-key check → the three
   missing-key cases go red; (b) revert `rglob` to `glob` → the nested-file case goes red; (c) drop the
   `parent.mkdir` → the write case goes red; (d) drop `name` from the context → the name case goes red; (e) drop
   the remote `mkdir -p` → the deployer case goes red. Record each red line in the phase commit body.
6. Gate: `.venv/bin/ruff check src/fabrik/version_registry.py src/fabrik/template_renderer.py
   src/fabrik/orchestrator/deployer_ssh.py tests/test_docusaurus_static_runtime.py
   tests/orchestrator/test_deployer_ssh.py` clean; `PYTHONPATH=<worktree>/src .venv/bin/python -m pytest
   tests/orchestrator/test_deployer_ssh.py -q` green; `.venv/bin/mypy src/fabrik/version_registry.py src/fabrik/template_renderer.py
   src/fabrik/orchestrator/deployer_ssh.py` clean;
   `python scripts/final_gate.py --lean --json` → `"status":"success"`.
7. Docs: `CHANGELOG.md` `### Changed — docusaurus static runtime, phase A: version registry loader + nested
   template rendering (2026-10-XX)`; `INDEX.md` rows for `src/fabrik/version_registry.py` and
   `tests/test_docusaurus_static_runtime.py`. Then `python scripts/enforcement/check_doc_sync.py` after staging.
8. **`/fabrik-review-scoped` on this phase's changed surface** (`version_registry.py`, `template_renderer.py`,
   `deployer_ssh.py`'s writer, the two test files) plus its one hop (`spec_loader.load_spec`, the two existing renderer test consumers), run to its
   coverage-adjudicated exit — every class CLEAN/FIXED/REFUTED, every confirmed finding fixed in-run with a
   grader. Phase B does not start until it closes.
9. Commit the phase with explicit pathspecs and provenance trailers (`Agent-Phase: A`); push.

**Behavior Contract — Phase A**

- **Given** a registry holding `node_lts`, `debian_codename` and `node_engines_floor`, **When**
  `load_versions()` runs, **Then** it returns the `versions` map with every value a non-empty string
  (`src/fabrik/version_registry.py`; `.windsurf/rules/versions.yaml:12-16`).
- **Given** a registry where one required key is absent, `null` or an empty string (each of the three keys, each
  of the three shapes — nine cases), **When** `load_versions()` runs, **Then** it raises `VersionRegistryError`
  whose message names that key (`spec § The delta` part 1).
- **Given** a missing registry file, or one whose `versions` is a list, **When** `load_versions()` runs, **Then**
  it raises `VersionRegistryError` naming the file — never a `KeyError` or `TypeError` from deeper code.
- **Given** a registry missing `node_lts`, **When** `TemplateRenderer.render` renders any template, **Then** it
  raises `VersionRegistryError` naming `node_lts`, and no `<output>/<id>/` directory exists afterwards (the
  renderer's constructor already creates `output_dir` itself, `src/fabrik/template_renderer.py:39-40`, so the
  assertion is on the per-spec directory) (`spec § Validation` 3, renderer half).
- **Given** a template dir with a nested `a/b/x.txt.j2`, **When** `render(dry_run=True)` runs, **Then** the
  result holds key `a/b/x.txt` with the registry's `node_lts` and the spec id rendered into it
  (`src/fabrik/template_renderer.py:160-165` today renders top-level only).
- **Given** the same template dir, **When** `render(dry_run=False)` runs, **Then** `<output>/<id>/a/b/x.txt` exists
  on disk with that content (`src/fabrik/template_renderer.py:211-219` today has no parent mkdir).
- **Given** a rendered key `src/theme/SearchBar/index.js`, **When** `_write_file_to_vps_path("/opt/docs", key, …)`
  runs with the ssh calls patched, **Then** the remote command creates `/opt/docs/src/theme/SearchBar` before the
  `sudo mv`; and for a flat key (`Dockerfile`) the command is unchanged
  (`src/fabrik/orchestrator/deployer_ssh.py:849-879`; the consumer loop `:471-475`).

## Phase B — The docusaurus templates and the scaffold emitter

**Interfaces — Consumes:** `fabrik.version_registry.load_versions`, `VersionRegistryError` (Phase A); the
renderer's recursive output keys and its `name`/`versions` context (Phase A).
**Produces:** the emitted docusaurus project shape of `spec § Contract deltas`, identical through both emitters
for `Dockerfile`, `nginx.conf`, `src/pages/index.js`, `src/theme/SearchBar/index.js` (byte-equal after stripping
trailing newlines); `_scaffold_docusaurus(project_dir, name, description, **kwargs)` keeps its signature
(`scaffold.py:6141`) and its registry entry (`scaffold.py:6832`).

1. **Write the failing tests first** in `tests/test_docusaurus_static_runtime.py` (Phase B's rows below): one
   module-scoped scaffold of `create_project(name="docs-probe", project_type="docusaurus", ...)` into
   `tmp_path_factory` with `FABRIK_SCAFFOLD_OFFLINE=1`; one `TemplateRenderer(output_dir=tmp).render(load_spec(
   <tmp spec yaml, template: docusaurus>), dry_run=True)`. Every version value is read from
   `load_versions()` in the test, never a literal. Run them and **confirm they fail** against today's emitters
   (e.g. `FROM node:22-bookworm-slim` ≠ `node:24-trixie-slim`, no `nginx.conf`, port 3000).
2. `templates/docusaurus/Dockerfile.j2` — replace whole (`spec § The delta` part 2):
   ```dockerfile
   FROM node:{{ versions.node_lts }}-{{ versions.debian_codename }}-slim AS builder
   WORKDIR /app
   COPY package*.json ./
   RUN if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi
   COPY . .
   RUN npm run build && npx -y pagefind --site build

   FROM nginx:mainline-{{ versions.debian_codename }}
   RUN apt-get update && apt-get install -y --no-install-recommends curl \
       && rm -rf /var/lib/apt/lists/*
   COPY --from=builder /app/build /usr/share/nginx/html
   COPY nginx.conf /etc/nginx/conf.d/default.conf
   HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
       CMD curl -f http://localhost:80/docs/intro/ || exit 1
   EXPOSE 80
   ```
   The curl install stays although the image ships curl (`spec § Pack conflicts` 2 — infra's call).
3. `templates/docusaurus/compose.yaml.j2` — delete the `environment:` block (`:7-9`); Traefik
   `loadbalancer.server.port=80`; healthcheck `["CMD", "curl", "-f", "http://localhost:80/docs/intro/"]`; add no
   middleware label. `templates/docusaurus/defaults.yaml` — drop `NODE_ENV` and `PORT` from `env:` (keep `TZ`).
4. New `templates/docusaurus/nginx.conf.j2` (`spec § The delta` part 3; holds no `{{` and no `{%`):
   ```nginx
   server {
       listen 80;
       server_name _;
       root /usr/share/nginx/html;
       absolute_redirect off;

       gzip on;
       gzip_types text/css application/javascript application/json image/svg+xml application/wasm;

       location /assets/ {
           add_header Cache-Control "public, max-age=31536000, immutable";
           try_files $uri =404;
       }

       location / {
           try_files $uri $uri/ /index.html;
       }
   }
   ```
   The `/assets/` rule rests on Docusaurus 3.7.0's webpack output names (`assets/js/[name].[contenthash:8].js`,
   `assets/css/[name].[contenthash:8].css` — ledger dsr-3), which closes the spec's recorded caveat that this rested
   on a cisagov comment.
5. New `templates/docusaurus/src/pages/index.js.j2` (`spec § The delta` part 4; ledger dsr-1, dsr-2) — the
   `{% raw %}` opens on line 1 before `import`, `{% endraw %}` closes after the last line:
   `import React from 'react'; import {Redirect} from '@docusaurus/router'; export default function Home() {
   return <Redirect to="/docs/intro" />; }` (formatted one statement per line in the file).
6. New `templates/docusaurus/src/theme/SearchBar/index.js.j2` (`spec § The delta` part 5; ledger dsb-1..dsb-5,
   pfc-2..pfc-7) — body inside `{% raw %}…{% endraw %}`, opened on line 1:
   - `import React from 'react'; import Head from '@docusaurus/Head';`
   - default export `SearchBar()` returning a fragment: `<Head>` holding `<link rel="stylesheet"
     href="/pagefind/pagefind-component-ui.css" />` and `<script type="module"
     src="/pagefind/pagefind-component-ui.js"></script>`, then `<pagefind-modal-trigger></pagefind-modal-trigger>`
     and `<pagefind-modal></pagefind-modal>`.
   - No `window`/`document` access anywhere (SSR, dsb-5). No `bundle-path` (the scaffold's `baseUrl` is `/`,
     pfc-6). Under `npm start` the `/pagefind/` files do not exist (the index is built by the Dockerfile only), so
     the dev server shows a trigger with no index — stated in the template's leading comment, inside the raw block.
7. `templates/docusaurus/package.json.j2` — delete the `serve` script; `engines.node` →
   `">={{ versions.node_engines_floor }}"`; add `"pagefind": "^1.5.2"` to `devDependencies` (ledger pf-1). The
   Docusaurus pins stay 3.7.0 (W-cdf69863).
8. `src/fabrik/scaffold.py` `_scaffold_docusaurus`:
   - add one module-level helper `_render_docusaurus_template(rel: str, name: str, versions: dict[str, str]) ->
     str` over `jinja2.Environment(loader=FileSystemLoader(str(DOCUSAURUS_TEMPLATE_DIR)), autoescape=False,
     undefined=StrictUndefined, keep_trailing_newline=True, trim_blocks=True, lstrip_blocks=True)` rendering
     with `{name, versions}`;
   - at the top of `_scaffold_docusaurus`, `versions = load_versions()` (raises before any file is written);
   - package.json (`:6152-6155`): render `package.json.j2` through the helper instead of the literal
     `.replace("{{ name }}", name)`; keep the `json.loads` → `pkg["description"]` → `json.dumps` sequence;
   - Dockerfile (`:6417-6420`): render `Dockerfile.j2` through the helper and write it; delete the
     `.replace("RUN npm ci", "RUN npm install")` swap and its B36 comment's swap sentence (the Dockerfile decides);
   - write `nginx.conf`, `src/pages/index.js`, `src/theme/SearchBar/index.js` through the helper (mkdir parents);
   - `.env.example` (`:6389`): drop the `NODE_ENV=development` line — the image runs no Node and `npm start`
     sets its own mode — keeping the `# {name} Configuration` header;
   - `_write_canonical_compose(project_dir, name, port=80, healthcheck_path="/docs/intro/")` (`:6433-6438`), and
     rewrite the B20+B45 comment to say why `/docs/intro/` (the slash-less path is a 301 under nginx).
9. `src/fabrik/spec_generator.py:112` — docusaurus `health_path` → `"/docs/intro/"`; update the two pinning tests
   `tests/test_spec_generator.py:90` and `:470` (with their B45 comment) in the same change.
10. `tests/test_scaffold.py:932` — replace `assert scripts["serve"] == "docusaurus serve"` with `assert "serve"
    not in scripts` (the behaviour the spec changes; `spec § The delta` part 8).
11. `templates/docusaurus/README.md` § Stack and § Deployment — the nginx static runtime on port 80, Pagefind
    search through the swizzled `SearchBar`, base images from `.windsurf/rules/versions.yaml`; delete the
    "Cloudflare Pages (faster, recommended)" line only if it contradicts the pack's `fabrik apply` mandate (it
    does — `core/42-docusaurus.md:30`).
12. Run the Phase B tests green, then `PYTHONPATH=<worktree>/src .venv/bin/python -m pytest
    tests/test_docusaurus_static_runtime.py tests/test_scaffold.py tests/test_spec_generator.py
    tests/test_scaffold_compose_traefik.py tests/test_scaffold_doc_seeding.py tests/test_scaffold_audit_log.py
    tests/test_scaffold_logging.py tests/test_scaffold_deploy_contract.py -q` — expect all pass (the last three
    also scaffold docusaurus through the real templates: `tests/test_scaffold_audit_log.py:56`,
    `tests/test_scaffold_logging.py:521-523`, `tests/test_scaffold_deploy_contract.py:155-158`).
13. **Red-on-revert** in a throwaway worktree, one neuter at a time: (a) restore the `node:22-bookworm` literal in
    `Dockerfile.j2` → the FROM rows go red; (b) replace the lockfile-conditional line in `Dockerfile.j2` with a
    bare `RUN npm ci --no-audit --no-fund` → the install-line row goes red; (c) drop `absolute_redirect off` → the
    nginx row goes red; (d) `port=3000` → the compose row goes red; (e) delete
    `src/theme/SearchBar/index.js.j2` → the nested-file rows go red through BOTH emitters; (f) a one-character
    post-render edit to the `nginx.conf` the scaffold writes (e.g. re-adding a `.replace(...)` on its text) → the
    parity row goes red. Record each.
14. Gate: `ruff` + `mypy` on the touched Python files clean; `python scripts/final_gate.py --lean --json` →
    success. Docs: `CHANGELOG.md` phase B entry; `INDEX.md` rows for `templates/docusaurus/nginx.conf.j2`,
    `templates/docusaurus/src/pages/index.js.j2`, `templates/docusaurus/src/theme/SearchBar/index.js.j2`;
    `python scripts/enforcement/check_doc_sync.py` after staging.
15. **`/fabrik-review-scoped` on this phase's changed surface** (the seven templates, `scaffold.py`'s docusaurus
    hunk, `spec_generator.py:112`, the three test files) plus one hop (`_write_canonical_compose`,
    `create_project`'s dispatch), run to its coverage-adjudicated exit. Phase C does not start until it closes.
16. Commit the phase with explicit pathspecs and provenance trailers (`Agent-Phase: B`); push.

**Behavior Contract — Phase B**

- **Given** a scaffolded docusaurus project, **When** its `Dockerfile` is read, **Then** the builder is
  `node:<node_lts>-<debian_codename>-slim` and the server `nginx:mainline-<debian_codename>` with the registry's
  values, the builder runs `npm run build && npx -y pagefind --site build`, it copies `package*.json` and carries
  the exact lockfile-conditional install line (`RUN if [ -f package-lock.json ]; then npm ci …; else npm install
  …; fi`) and no other `RUN npm ci`/`RUN npm install` line, and no stage runs `npm run serve` or starts Node
  (`spec § Validation` 1).
- **Given** a scaffolded project, **When** `nginx.conf` is read, **Then** it holds `try_files $uri $uri/
  /index.html;`, `absolute_redirect off;`, `gzip on;` with the five `gzip_types`, and the immutable
  `Cache-Control` header inside `location /assets/` only (`spec § The delta` part 3).
- **Given** a scaffolded project, **When** `compose.yaml` is parsed, **Then** the Traefik loadbalancer port and
  the healthcheck both use 80, the healthcheck path is `/docs/intro/`, and no `middlewares` label exists
  (`spec § The delta` part 7; `core/30-ops.md:195`). Its `environment` is the compose writer's own
  `PORT=80` and `LOG_LEVEL=INFO` (`src/fabrik/scaffold.py:1034-1037`, emitted for every scaffold type; nginx
  ignores both) — the row asserts those two and no `NODE_ENV`, and that the scaffold's `.env.example` names no
  `NODE_ENV` (`src/fabrik/scaffold.py:6389` today). The two emitters' compose files come from two
  different writers by design (`_write_canonical_compose` vs `compose.yaml.j2`), so compose is not a parity
  pair.
- **Given** a scaffolded project, **When** `src/pages/index.js` and `src/theme/SearchBar/index.js` are read,
  **Then** both exist, neither contains `{%`, `{{` or `endraw`, the page redirects to `/docs/intro`, and the
  SearchBar carries `pagefind-modal-trigger`, `pagefind-modal`, and a `type="module"` script for
  `/pagefind/pagefind-component-ui.js` inside `Head` (`spec § The delta` parts 4–5).
- **Given** a scaffolded project, **When** `package.json` is parsed, **Then** `devDependencies.pagefind` is
  `^1.5.2`, `scripts` has no `serve`, `engines.node` is `>=<node_engines_floor>` from the registry, and `name` is
  `<name>-docs` (`spec § The delta` part 8).
- **Given** a `source: type: template` spec with `template: docusaurus`, **When** `TemplateRenderer.render` runs,
  **Then** the same Dockerfile, nginx.conf, nested-file and package.json assertions hold, the compose carries
  port 80 in both places and no `NODE_ENV`/`PORT` environment, and package.json's `name` is `<spec id>-docs`
  (`spec § Validation` 2; closes I10).
- **Given** both emitters run with the same registry, **When** their `Dockerfile`, `nginx.conf`,
  `src/pages/index.js` and `src/theme/SearchBar/index.js` are compared, **Then** each pair is byte-equal after
  stripping trailing newlines (`spec § Goal` — "a scaffolded project and a template-rendered one are the same").
- **Given** a registry missing `debian_codename`, **When** `create_project(... project_type="docusaurus")` runs,
  **Then** it raises `VersionRegistryError` naming `debian_codename` (`spec § Validation` 3, scaffold half).
- **Given** `generate_spec("my-docs", "docusaurus", …)`, **When** its health path is read, **Then** it is
  `/docs/intro/` (`src/fabrik/spec_generator.py:112`; I11).

## Phase C — Real build proof and Finish

**Interfaces — Consumes:** the scaffolded project of Phase B. **Produces:** the review receipt
`docs/development/reviews/2026-10-01-plan-1-docusaurus-static-runtime-review.md`; Status → EXECUTED.

1. **Toolchain preflight** (the first executed step, its output pasted into the commit body):
   `docker info --format '{{.ServerVersion}}'` (expect a version), `timeout 20 curl -sS -o /dev/null -w
   '%{http_code}' https://registry.npmjs.org/pagefind` (expect `200`; measured 200 at plan time, E5). A failure is
   `BLOCKED: missing infra` (docker or registry), never a skipped proof.
2. **Write the opt-in test** `test_real_build_serves_the_static_site` in `tests/test_docusaurus_static_runtime.py`
   (Phase C's rows below): skip with reason unless `FABRIK_REAL_DOCKER_BUILD=1`; with the flag, fail (not skip)
   when `docker` is absent. It scaffolds into `tmp_path` (no lockfile), `docker build -t
   fabrik-docusaurus-probe:<uuid> .` with a 900 s timeout, `docker run -d --rm -p 127.0.0.1::80` (an ephemeral
   loopback port for the TEST container only — never in an emitted compose), polls `/docs/intro/` up to 60 s, runs
   the assertions with `urllib.request` (a handler that does NOT follow redirects for the 301 row), and removes
   the container and the image in a `finally` (the image tag is unique per run, so a leftover is identifiable).
   Run it once with the flag in the background (`run_in_background`): it must pass. Then neuter
   `absolute_redirect off` in the probe worktree and re-run: the relative-301 row must go red; restore.
3. **Read the real build output once** (the spec's recorded caveat): list `build/assets/js/` and
   `build/pagefind/` from the builder stage (`docker build --target builder` + `docker run --rm … ls`), and paste
   the two listings into the receipt — the `/assets/` hash names and `pagefind-component-ui.js/.css` present.
4. Docs: `CHANGELOG.md` phase C entry; `INDEX.md` row for the receipt. `docs/FEATURES.md` holds the docusaurus
   type only in the project-types list (`docs/FEATURES.md:496`), so no feature row is owed — `/fabrik-docs-review`
   below confirms or corrects that.
5. **Whole-plan `/fabrik-review`** (the Profile: small heavy round) over `git diff <plan baseline>..HEAD` — the
   `/fabrik-execute-plan` D7 floor: ≥1 Opus authoritative seat plus one Sonnet and one Haiku mechanical seat per
   independent failure-class group, sized by `python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --units
   <groups>` and stamped with `python3 scripts/command_run.py dispatch --seats <n>` before dispatch; to its
   coverage-adjudicated exit, one receipt.
6. **`/fabrik-docs-review`** over the docs this plan touched or made stale: `templates/docusaurus/README.md`,
   `CHANGELOG.md`, `INDEX.md`, `docs/DECISIONS.md` D-475, `docs/FEATURES.md:496`, `docs/TROUBLESHOOTING.md:184`
   (the multi-stage Node build note — still true of the builder stage?), `docs/reference/architecture.md:54`.
7. Final step: `python scripts/final_gate.py --check --json` → `"status":"success"` **and**
   `python scripts/enforcement/check_convergence.py` → exit 0. A green gate is necessary, not sufficient: it proves
   format and citations, not the design — the proof is § Evidence plus the real build of step 2.
8. **The pack conflicts are not built.** Confirm mails 01M3V92T8N and 01M3VAZQPV are still open with infra; if
   either was answered with a pack change before execution, reconcile the template to the changed pack in this
   phase and say so in the receipt.
9. Flip Status → EXECUTED with the phase commits; commit the receipt with explicit pathspecs and trailers
   (`Agent-Phase: C`); push; `python3 scripts/merge_request.py request --review
   docs/development/reviews/2026-10-01-plan-1-docusaurus-static-runtime-review.md --item W-3f2d8e21`.

**Behavior Contract — Phase C**

- **Given** `FABRIK_REAL_DOCKER_BUILD=1` and a freshly scaffolded site with no lockfile, **When** it is built and
  run, **Then** `docker build` succeeds, `GET /docs/intro/` answers 200, `GET /docs/intro` answers 301 with the
  RELATIVE `Location: /docs/intro/`, `GET /pagefind/pagefind-component-ui.js` answers 200, a missing path answers
  200 (the pack's fallback, never a 500), and the HTML of `/docs/intro/` contains `pagefind-modal-trigger` and the
  module script tag (`spec § Validation` 4).
- **Given** the running container, **When** a `/assets/js/*.js` file named in the page is fetched with
  `Accept-Encoding: gzip`, **Then** it carries `Cache-Control: public, max-age=31536000, immutable` and
  `Content-Encoding: gzip`, and `/docs/intro/` carries no immutable header (`spec § The delta` part 3).
- **Given** `FABRIK_REAL_DOCKER_BUILD` unset, **When** the suite runs, **Then** the real-build test is skipped with
  a reason naming the flag; **Given** the flag set and `docker` absent from `PATH`, **Then** it fails.

## File Scope (owned paths)

- src/fabrik/version_registry.py
- src/fabrik/template_renderer.py
- src/fabrik/scaffold.py
- src/fabrik/spec_generator.py
- src/fabrik/orchestrator/deployer_ssh.py
- templates/docusaurus/Dockerfile.j2
- templates/docusaurus/compose.yaml.j2
- templates/docusaurus/defaults.yaml
- templates/docusaurus/package.json.j2
- templates/docusaurus/nginx.conf.j2
- templates/docusaurus/src/pages/index.js.j2
- templates/docusaurus/src/theme/SearchBar/index.js.j2
- templates/docusaurus/README.md
- tests/test_docusaurus_static_runtime.py
- tests/test_scaffold.py
- tests/test_spec_generator.py
- tests/orchestrator/test_deployer_ssh.py
- docs/development/plans/2026-10-01-plan-1-docusaurus-static-runtime.md
- docs/development/reviews/2026-10-01-plan-1-docusaurus-static-runtime-review.md

The governance files (`CHANGELOG.md`, `INDEX.md`, `docs/README.md`, `docs/FEATURES.md`, `docs/LESSONS_LEARNT.md`,
`docs/DECISIONS.md`, `docs/STRATEGIC_BACKLOG.md`) are outside the lock by design. No active plan lock overlaps
this scope: every lock in `/opt/fabrik/.fabrik/plan-locks/` reads `released`, `executed`, `success`,
`complete` or `failure` (E6). `scaffold.py` is a shared hot file: the executor fetches and rebases onto master
immediately before each phase commit.

## Evidence

**E1 — the emitters as they are (Phase A, B).** `src/fabrik/template_renderer.py:43-48` (autoescape on for
`.j2`, default `Undefined`), `:129-140` (context without `name` or `versions`), `:160-165` (`glob("*.j2")`,
top-level only), `:211-219` (write loop, no parent mkdir); `src/fabrik/scaffold.py:238`
(`DOCUSAURUS_TEMPLATE_DIR = FABRIK_ROOT / "templates" / "docusaurus"`), `:6152-6155` (literal `{{ name }}`
replace), `:6417-6420` (literal Dockerfile read + `npm ci` swap), `:6433-6438` (`port=3000`,
`healthcheck_path="/docs/intro"`); `src/fabrik/spec_generator.py:112`; `tests/test_scaffold.py:932`;
`tests/test_spec_generator.py:90`, `:470`; `src/fabrik/config.py:34-68` (`FABRIK_ROOT` resolution).

**E2 — the registry has the three keys; no loader exists in `src/fabrik` (Phase A).**

```text
$ sed -n 12,16p .windsurf/rules/versions.yaml
versions:
  python_stable: "3.14"
  node_lts: "24"
  node_engines_floor: "22"
  debian_codename: "trixie"
$ grep -rn "versions.yaml\|versions_yaml" src/fabrik/   → 0 hits (the readers live under scripts/sysadmin/:
  rules_render_versions.py:54 load_versions, rules_currency_watch.py)
$ ls src/fabrik/versions.py → No such file or directory
```

**E3 — Jinja whitespace and autoescape under both settings, executed (Phase A, B).**

```text
renderer '\nexport default function X() {\n  return <div className={a}>{b}</div>;\n}\n'
renderer 'FROM node:24-trixie-slim AS builder\nRUN a && b'
scaffold-proposed '\nexport default function X() {\n  return <div className={a}>{b}</div>;\n}\n'
scaffold-proposed 'FROM node:24-trixie-slim AS builder\nRUN a && b\n'
```

The newline after `{% raw %}` survives in both (so the raw block opens inline); `&&` is literal template text and
is not escaped by the renderer's autoescape; the renderer drops the final newline and the scaffold keeps it.

**E4 — no other template has a nested `.j2`; only docusaurus reads `name` through the renderer (Phase A).**

```text
$ find templates -mindepth 2 -name "*.j2" | wc -l   → 26
$ find templates -mindepth 3 -name "*.j2" | wc -l   → 0
$ grep -rn "{{ *name" templates/*/*.j2  → docusaurus/AGENTS.md.j2:1, docusaurus/docusaurus.config.js.j2:14,:68,
  docusaurus/package.json.j2:2, modal/echo-handler.py.j2 (×3), modal/vllm-openai.py.j2 (×3)
$ ls templates/*/compose.yaml.j2 → 9 templates; modal has none (never rendered by TemplateRenderer)
```

**E5 — the build toolchain is present on this box (Phase C).**

```text
$ timeout 20 curl -sS -o /dev/null -w '%{http_code}\n' https://registry.npmjs.org/pagefind
200
$ docker run --rm node:24-slim sh -c 'npm view pagefind version'
1.5.2
$ docker image ls → nginx:mainline-trixie, node:24-slim present; node:24-trixie-slim not yet pulled
```

**E6 — no plan lock overlaps (File Scope).** Top-level `status` of every lock file (a regex over the files counts
nested task statuses too, which review pass 1 caught):

```text
$ python3 <scratch>/probes/locks.py   # json.load each /opt/fabrik/.fabrik/plan-locks/*.json, Counter(status)
lock files: 78 {'released': 73, 'complete': 1, 'executed': 4}
```

**E7 — the SearchBar slot renders with no navbar search item (Phase B step 6).**

```text
$ curl -sS https://raw.githubusercontent.com/facebook/docusaurus/v3.7.0/packages/docusaurus-theme-classic/src/theme/Navbar/Content/index.tsx | grep -n "searchBarItem\|SearchBar\|NavbarSearch"
16:import SearchBar from '@theme/SearchBar';
19:import NavbarSearch from '@theme/Navbar/Search';
70:  const searchBarItem = items.find((item) => item.type === 'search');
88:          {!searchBarItem && (
89:            <NavbarSearch>
90:              <SearchBar />
91:            </NavbarSearch>
```

**E8 — the fixture specs and the live container (I12).** `docs/infrastructure/vps-complete-inventory.md` (Last
Updated 2026-09-04) names no docusaurus container: `grep -n -i "docusaurus\|docs-site\|test-docs"` returns only
line 793, the watchdog applicability note. `specs/services/fabrik-test-docusaurus.yaml` builds from its own repo.

**E9 — where each root resolves, by CWD (plan-level decision 2).** With `PYTHONPATH=<worktree>/src`:

```text
cwd=/tmp FABRIK_ROOT /opt/fabrik | PROJECT_ROOT /opt/fabrik/.claude/worktrees/fleet | scaffold tpl /opt/fabrik/templates/docusaurus | renderer tpl /opt/fabrik/.claude/worktrees/fleet/templates
cwd=/opt/fabrik/.claude/worktrees/fleet FABRIK_ROOT /opt/fabrik/.claude/worktrees/fleet | PROJECT_ROOT /opt/fabrik/.claude/worktrees/fleet | scaffold tpl /opt/fabrik/.claude/worktrees/fleet/templates/docusaurus | renderer tpl /opt/fabrik/.claude/worktrees/fleet/templates
```

**External facts** — every one is a ledger row with its URL: Pagefind CLI 1.5.2 and the Component UI (pf-1..pf-4,
pf-12, pfc-1..pfc-7, https://pagefind.app/docs/, https://pagefind.app/llms-component-ui.txt); Docusaurus 3.7.0
SearchBar slot, JSX compile, SSR (dsb-1..dsb-5, raw.githubusercontent.com/facebook/docusaurus/v3.7.0/…); the root
redirect, build output names and trailingSlash (dsr-1..dsr-4, srv-3); the images (img-1..img-5).

## Self-audit

Grounding passes run: (1) every `path:line` above opened this run; (2) three native researcher seats (Opus on
the SearchBar slot, Sonnet on Pagefind's Component UI, Sonnet on the redirect and build output) — 17 facts, filed
whole into the ledger before synthesis; the one load-bearing JSX line the Opus seat could only paraphrase was
re-fetched raw by the orchestrator (E7); one finding changed the plan — Pagefind does not document dynamic script
injection, so the SearchBar uses `@docusaurus/Head` (decision 3); (3) the Jinja probe (E3) changed the plan twice
— the inline `{% raw %}` and the rstrip-normalised parity comparison; (4) the toolchain probe (E5) moved the real
build from "may be unrunnable here" to an executed Phase C step.

**(a) Coverage** — spec § The delta part 1 → Phase A steps 2–3 + Phase B step 8; part 2 → Phase B step 2; part 3
→ step 4; part 4 → step 5; part 5 → step 6; part 6 → Phase A step 3 + Phase B step 8; part 7 → step 3 and step 8;
part 8 → step 7 and step 10; § Validation 1 → Phase B rows 1–5; 2 → row 6; 3 → Phase A row 4 + Phase B row 8;
4 → Phase C rows 1–2. The spec's two routed open items → Phase A step 3 (I10) and Phase B step 9 (I11); the third
→ § Residual unknowns R1. No gap.

**(b) Cross-phase signatures** — `load_versions(path: Path | None = None) -> dict[str, str]` and
`VersionRegistryError` are produced in Phase A and consumed by Phase B step 8 under the same names; the
renderer's output key `src/theme/SearchBar/index.js` (Phase A step 3's `rel.with_suffix("").as_posix()`) is the
key Phase B's renderer rows read; `FABRIK_REAL_DOCKER_BUILD` appears only in Phase C. Consistent.

`/fabrik-plan-review` pass 1 (author-blind, an Opus seat on the rule/grammar sections and a Sonnet seat on the
rest, every candidate executed by the orchestrator) confirmed 15 defects, all fixed — see § Pass Ledger. The
largest: rendered nested files would have failed `fabrik apply`'s remote `mv` (Phase A step 3b), the registry
anchor followed the CWD (decision 2), and one red-on-revert neuter could not go red (Phase B step 13 (b)).

## Residual unknowns

**Resolved:**
- I10 `name` missing from the renderer context → Phase A step 3 adds `spec.id`.
- Whether a swizzled `src/theme/SearchBar/index.js` renders without a navbar search item → yes (E7, dsb-1, dsb-2).
- Whether the script can be injected after load → not documented, so not relied on (decision 3, pfc-7).
- Whether `/assets/` holds content-hashed files → yes, from source (dsr-3); Phase C step 3 also reads a real build.
- Whether this box can run the real build → yes (E5).

**Still open (each with its resolution step):**
- **R1 — a live `fabrik-test-docusaurus` container on vps1.** The 2026-09-04 inventory names none (E8), and the
  container builds from its own repository, so this plan cannot change what it serves either way. Resolution: a
  read-only `docker ps --filter name=docusaurus` on vps1, run by the operator or by fleet with the operator's
  go — VPS actions ask first (standing operator rule). It does not block execution.
- **R2 — the Profile: small reading** (Python files vs templates). Resolution: `/fabrik-plan-review` rules on it;
  a 3-ticket set is the fallback with the same phases.
- **R3 — an infra answer to the pack-conflict mails before execution.** Resolution: Phase C step 8 reconciles.

## Pass Ledger

`/fabrik-plan-review`, 2026-10-01. Native seats only (D-181), partitioned by section (D-212, D-218): `rules` (Opus —
Global Constraints, Context Ledger, Constraints Digest, every Interfaces block, every Behavior Contract, Evidence,
File Scope, Coverage Checklist) and `prose` (Sonnet — header, What this plan is, Intake Inventory, What we already
agreed, every numbered phase step, Self-audit, Residual unknowns). `shape: agent-tool` — the box allowed 3 seats
(`dispatch_headroom.py --slices opus=1,sonnet=3` → `SEATS: 3`, box-bound) and the workflow shape needs a refuter
per slice (4), so the two finders went out through the `Agent` tool and the orchestrator executed every
candidate. Before pass 1 the orchestrator armed the plan (the verbatim rubric, the derived checklist) and
rewrote the Constraints Digest so `check_rule_grounding` can read it (19 findings → 0).

| Pass | seats · axes re-checked (claims · gates · interfaces · completeness) | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (`rules`) + sonnet×1 (`prose`) · all axes | found: 17, new: 16, confirmed: 15, fixed: 15, unexecuted: 0, edits: 24 | method: citation — full partitioned pass; every candidate executed by the orchestrator: O1 (the remote `mv` of a nested key has no `mkdir`, `deployer_ssh.py:849-870`), O3 (FABRIK_ROOT follows the CWD, E9), O4 (`"RUN npm ci" in` the new line → False), O5, O6, O10, O11 (78 lock files re-counted) re-run; O2, O7, O8, O9, O12 and S2–S4 read; S1 = O6 (duplicate); S5 RECORDED — measured (the scaffold `.gitignore` excludes `node_modules/`, so a VPS build context from a git checkout never holds one; a local `docker build` in a dev checkout is the only exposure, pre-existing and outside the spec) | ff6ade45… → 90c3c103… |
| Pass 2 | opus×1 (round-1 owner of `rules`) + sonnet×1 (round-1 owner of `prose`) · delta over pass 1's fix (306 added / 79 removed) + one hop | found: 6, new: 6, confirmed: 5, fixed: 5, unexecuted: 0, edits: 7 | method: re-derivation — O1–O12 and S1–S4 all NOW_FALSE (S5 stands RECORDED); every new anchor re-read and E6, E9 and the rubric block re-run (E9 identical, 78 lock files, rubric MATCHED 56/56 lines equal). Confirmed, all own-fix (round 1): the step-6 `mypy` line missed two of the phase's three Python files; `deploy_validator.py:100` named as a render site (it only calls `template_exists`); `template_renderer.py:38-39` → `:39-40`; the core/30-ops verdict cited `scaffold.py:1053-1085`, which holds no labels (→ `:931-1082`, labels `:1008-1024`); step 3b said "beside the existing cases" while no direct writer test exists (0 `scp_to_vps` hits). RECORDED — measured (wording; fixed in passing): the writer's extent `:849-870` → `:849-879` | 585f382f… → 92e74b6d… |
| Pass 3 | opus×1 (round-1 owner of `rules`) + sonnet×1 (round-1 owner of `prose`) · delta over pass 2's fix (77-line diff) | found: 2, new: 2, confirmed: 1, fixed: 1, unexecuted: 0, edits: 1 | method: re-derivation — all five pass-2 fixes NOW_FALSE (anchors re-read: `deploy_validator.py:100-101`, `template_renderer.py:39-40`, `scaffold.py:931`/`:1008-1024`/`:1082` with 0 `middlewares`, `deployer_ssh.py:849-879`; `mypy` of the two existing files green; 0 direct writer tests). Confirmed, own-fix (round 2): the core/30-ops checklist row was split across two lines and rendered as two rows (executed with `markdown_it`); the class swept by `table_rows.py` over the whole plan — 2 flagged lines, both that row → 0 of 857 after the join. REFUTED: the prose seat's aside that `output_dir.mkdir` sits at `:38-39` (`sed -n 38,40p`: 38 comment, 39 `templates_dir`, 40 `output_dir`). Scope-growth stop (two of the last three rounds ≥ two-thirds own-fix): the closing pass re-verifies the one fixed row only | 92e74b6d… → 49c1c7cd… |
| Pass 4 | opus×1 (round-1 owner of `rules`) · the pass-3 fix only (scope-growth stop) | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — the joined core/30-ops row re-rendered with `markdown_it` (every Coverage Checklist data row 2 cells, the verdict complete); standing clean since pass 3: every other class of the ledger (citations, counts, interfaces, mirror, behaviour contract, templates, nginx, SSR, File Scope, digest, deploy writer, root anchor, gates) | 1d46a928… → 1d46a928… ✓ → **CONVERGED** |

## Coverage Checklist

Derived from the rubric below (FLOOR + MATCHED) plus the four standing recurrence classes. Every row starts
UNCHECKED and is adjudicated by `/fabrik-plan-review`.

| Class | Verdict |
|---|---|
| FLOOR core/35-security-auth — secrets, auth, config via env | CLEAN — hunted File Scope for auth, secret and config surfaces: none (no env var, no credential, no settings object is added) |
| FLOOR core/25-data-postgres — database, sessions, backing services | CLEAN — no database, session or backing service in File Scope |
| FLOOR core/30-ops — compose invariants (no `ports:`, `container_name`, memory limit, Traefik, public = no middleware), immutable releases | FIXED r1 — the scaffolded compose's writer-owned `PORT=80`/`LOG_LEVEL=INFO` stated in Phase B row 3 (O6); `container_name`, platform, memory limit, `fabrik` network, no `ports:`, no middleware verified in `_write_canonical_compose` (`src/fabrik/scaffold.py:931-1082`; the Traefik labels are built at `:1008-1024` and carry no `middlewares` label) |
| FLOOR 12-Factor — all twelve axes against what the plan steps | FIXED r1 — factor V restated for template-source specs, which re-render at every apply (O2); II/VII/XI verified against the Dockerfile and the stock nginx image |
| MATCHED core/10-python — no deps-file edits, pinned base image, no file logging | CLEAN — no deps-file edit; `jinja2` is already imported by `template_renderer.py:13-14` (resolved via `uv.lock`, not a direct `pyproject.toml` entry — unchanged by this plan); no logging added |
| MATCHED core/40-documentation — heading levels, fenced code, the docs the change makes stale | CLEAN — the plan's headings step `##`→`###` and its code is fenced; the README step is a doc edit |
| MATCHED ai/50-agentic — matched by the `**/orchestrator/**` glob only; any model/agent call the plan adds | CLEAN — matched by the `**/orchestrator/**` glob only; the plan adds no model or agent call |
| MATCHED core/45-testing-strategy — one test per behaviour, watched-fail-first, no cosmetic assertions, class-proof guards | FIXED r1 — the install-line neuter now edits the template (O4); the renderer-failure row asserts the per-spec directory (O9); every row names its red-on-revert step |
| Version pinning: no Node/Debian literal in a base image or `engines.node`, in either emitter | FIXED r1 — scoped to base images and `engines.node`; npm package pins stay literal by design (O8) |
| Governing pack core/42-docusaurus (MUST-READ by the spec; its globs match no File Scope path, so the rubric never injects it) | FIXED r1 — the digest ties the install-line deviation to `spec § The delta` part 2 (O7); this row added (O12) |
| Emitter parity (scaffold vs template renderer) | FIXED r1 — the registry anchors to the code's tree, not the CWD (O3, E9); compose is excluded from parity as two writers by design (O6) |
| nginx behaviour (redirect form, fallback, caching scope, gzip) | CLEAN — executed in pass 1 on `nginx:mainline-trixie` with step 4's config: `/docs/intro` 301 relative `/docs/intro/`, `/docs/intro/` 200 without the immutable header, `/assets/js/*.js` immutable + gzip, `/assets/missing.js` 404, `/nope` 200 |
| SSR safety of the swizzled component | CLEAN — the component uses `@docusaurus/Head` and touches no `window`/`document` (dsb-5); the raw block renders starting `import` under both settings (executed pass 1) |
| Mirror of a context or loop change on the other eight templates | FIXED r1 — the deploy-time writer creates nested remote directories (O1, Phase A step 3b); every template-source deploy reads the registry (O2); the three other docusaurus-scaffolding test files join Phase B step 12 (O5) |
| fail-open vs fail-closed on every gate/guard (here: a broken or absent registry) | FIXED r1 — a broken registry fails every render and template-source deploy loudly and by name, stated in the Mirror (O2) |
| cost/quota/limit accounting edges (seats sized and stamped; the real build's timeouts) | CLEAN — pass-1 seats sized by `dispatch_headroom.py` (box cap 3) and stamped; the real build carries a 900 s timeout and a 60 s readiness poll |
| boundary/sentinel/prefix collisions (empty string, `null`, missing file, non-mapping; nested output paths) | FIXED r1 — the top-level skip compares relative paths, so a nested `compose.yaml.j2` still renders (S3); empty/`null`/missing/non-mapping registry cases are rows |
| behavior-without-a-test | FIXED r1 — rows added for the deployer's nested write (O1) and the scaffold's `.env.example` (S1/O6) |

The rubric this plan's reviews inject into every seat brief, run on the plan's own `## File Scope (owned paths)`:

```bash
python3 scripts/review_rubric.py --changed src/fabrik/version_registry.py src/fabrik/template_renderer.py src/fabrik/scaffold.py src/fabrik/spec_generator.py src/fabrik/orchestrator/deployer_ssh.py templates/docusaurus/Dockerfile.j2 templates/docusaurus/compose.yaml.j2 templates/docusaurus/defaults.yaml templates/docusaurus/package.json.j2 templates/docusaurus/nginx.conf.j2 templates/docusaurus/src/pages/index.js.j2 templates/docusaurus/src/theme/SearchBar/index.js.j2 templates/docusaurus/README.md tests/test_docusaurus_static_runtime.py tests/test_scaffold.py tests/test_spec_generator.py tests/orchestrator/test_deployer_ssh.py docs/development/plans/2026-10-01-plan-1-docusaurus-static-runtime.md docs/development/reviews/2026-10-01-plan-1-docusaurus-static-runtime-review.md
```

```text
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: a default turns one bad/empty JWT into a cross-tenant read, and a raise turns a deny into a 500. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: `postgres:16-alpine`, `plpgsql` only); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
**"Own database" means a DATABASE on `postgres-main`, never a database SERVER.** Per-project isolation is a separate database (its own name, its own role) on the shared container — isolation, quota and backup are all satisfied at that grain. A dedicated Postgres instance is a decision, not a default: it needs its own `docs/DECISIONS.md` row naming what the shared server cannot serve (web-ecommerce-factory 01M1Q8X9, 2026-09-05: "one DB per store" read naively as one server per customer).
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an APPLICATION's settings surface**:
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.** The rubric FLOOR-injects this mandate *and* `35-security-auth`'s "config via env vars only (`os.getenv("KEY", "default")`)" into every finder prompt on every review, so a finder reading both literally has two rules it cannot both satisfy, and files a false positive on whichever it applies. The carve-out: `BaseSettings` governs a SERVICE's config surface (a `Settings` object, DB/Redis DSNs, secrets). A **vendored fabrik-lib module** has no settings object by design — it reads its own knobs with bare `os.getenv("KEY", "default")`, which is `35-security-auth`'s mandate being satisfied, not this … (wrapped further — read the pack)
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }` opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default to flip.
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a bare `curl` of a path you assumed.
- VOLUME gets a plan pointed at a directory that never exists — a paper backup that reads green and archives nothing.  If the data is a volume, say so in the spec comment and rely on the global `docker-volumes` plan; never let a service-named plan be mistaken for the protection.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout.  An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency.
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (2026-09-01: `postgres:16-alpine` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- > **`fabrik run` and `.fabrik/hooks/post-deploy/` do NOT exist** — the real CLI answers `Error: No such command 'run'`, the hook path appears nowhere in the platform, and `_post_deploy_sync()` (`cli.py:64`) only refreshes `data/projects.yaml`; an agent following either ships a deploy where migrations never run. Do not re-add either without a `path:line` in `src/fabrik/` that executes it.
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### ai/50-agentic.md  (hit: src/fabrik/orchestrator/deployer_ssh.py, tests/orchestrator/test_deployer_ssh.py)
- **Claude** for reasoning + tool use. **Operational** agents (sysadmin, watchdog, bootstrap) run via **Claude Code CLI w/ subscription OAuth** — never `ANTHROPIC_API_KEY`.

### core/10-python.md  (hit: src/fabrik/orchestrator/deployer_ssh.py, src/fabrik/scaffold.py, src/fabrik/spec_generator.py)
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### core/40-documentation.md  (hit: docs/development/plans/2026-10-01-plan-1-docusaurus-static-runtime.md, docs/development/reviews/2026-10-01-plan-1-docusaurus-static-runtime-review.md, templates/docusaurus/README.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/orchestrator/test_deployer_ssh.py, tests/test_docusaurus_static_runtime.py, tests/test_scaffold.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting — never point them at a dev/shared DB.

# promote-to-check_* tail elided (83 greppable-literal lines; the full mandates are above)
```
