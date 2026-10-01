# Plan — docusaurus scaffold: static nginx runtime, Pagefind search, registry versions

Status: DRAFT
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

**Profile: small — the count, stated so a reviewer can rule on it.** Code diff estimated at ~200 lines across
4 Python files (`src/fabrik/version_registry.py` new, `template_renderer.py`, `scaffold.py`,
`spec_generator.py`) plus 7 template files (`Dockerfile.j2`, `compose.yaml.j2`, `defaults.yaml`,
`package.json.j2`, and the new `nginx.conf.j2`, `src/pages/index.js.j2`, `src/theme/SearchBar/index.js.j2`).
The ≤5-file bound is read here as the Python code surface; the templates are emitted artifacts of 5–35 lines
each. If the review reads the templates as code files (11 > 5), the profile is wrong and the plan becomes a
3-ticket set with the same phases — the content does not change, only the execution profile.

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
2. **The registry path resolves from `FABRIK_ROOT`**, the same root `DOCUSAURUS_TEMPLATE_DIR` uses
   (`scaffold.py:238`), so a worktree's templates and its registry always come from the same tree.
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
  `node_engines_floor`) through `fabrik.version_registry.load_versions()`; no version literal in any emitter or
  template. Debian `-slim` for the Node builder; the pack-mandated `nginx:mainline-<codename>` for the server.
- No new dependency: `jinja2` and `PyYAML` are already imported by `src/fabrik/template_renderer.py:13-14`;
  `pyproject.toml`/`uv.lock` are not touched (`core/10-python.md:30`).
- 12-Factor, as it binds this surface: **II** — every binary the image runs is installed in the Dockerfile
  (curl, nginx in the base image, `pagefind` as a devDependency); **V** — releases are immutable, versions are
  rendered at scaffold/render time, never at deploy time (`spec § Rejected alternatives`); **VII** — the
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
| `core/30-ops.md` (FLOOR) | no `ports:`; `container_name`; immutable releases; public = no middleware | `.windsurf/rules/core/30-ops.md:148`, `:150`, `:195`, `:266` |
| `core/35-security-auth.md`, `core/25-data-postgres.md` (FLOOR) | not engaged: no auth, secret, database or session surface is touched | read; no row applies |
| `fabrik-lib` | no module covers a static-site stack or search UI — build in the hub's templates; not a candidate | `spec § fabrik-lib verdict` |
| `agents-fabrik.md` § Scaffold Types | the docusaurus row (`static`, `is_public`) is unchanged | `agents-fabrik.md:428` |
| `specs/services/<id>.yaml` `shape:` | no flag changes; `shape.kind: static` stays | `templates/docusaurus/defaults.yaml:6-13` |
| data/UI contracts | none exist for scaffold templates | `spec § Contract deltas` |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Rule | Verbatim | file:line |
|---|---|---|
| No Node runtime | "Running `docusaurus serve` or any Node.js runtime in a production container is banned — it wastes RAM serving what should be static files." | `.windsurf/rules/core/42-docusaurus.md:26` |
| Build stage | "`npm ci` then `npm run build`, then `npx -y pagefind --site build` for search indexing." | `.windsurf/rules/core/42-docusaurus.md:32` |
| Serve stage | "copy `build/` to `/usr/share/nginx/html`." | `.windsurf/rules/core/42-docusaurus.md:33` |
| SPA fallback | "The Nginx config must include `try_files $uri $uri/ /index.html;`" | `.windsurf/rules/core/42-docusaurus.md:53` |
| Asset caching | "Cache static assets aggressively: `Cache-Control: public, max-age=31536000, immutable` for JS/CSS/fonts/images/WASM." | `.windsurf/rules/core/42-docusaurus.md:53` (narrowed to `/assets/`, spec § Pack conflicts 5) |
| Compose | "no `ports:` section (Traefik routes traffic), `deploy.resources.limits.memory` mandatory, `platform: linux/amd64` mandatory." | `.windsurf/rules/core/42-docusaurus.md:88` |
| Search | "Use **Pagefind**" · "swizzle `SearchBar` — **the one sanctioned swizzle**" | `.windsurf/rules/core/42-docusaurus.md:92`, `:105` |
| No ports | "**No `ports:` section.** All external traffic routes through Traefik. Never bind host ports." | `.windsurf/rules/core/30-ops.md:148` |
| Container name | "**`container_name: <name>` is mandatory.**" | `.windsurf/rules/core/30-ops.md:150` |
| Middleware | "Traefik middleware set per service category — admin UI: `authelia-forward@docker,gzip@docker`; API: `gzip@docker`; public: none" | `.windsurf/rules/core/30-ops.md:195` |
| Immutable releases | "Releases are IMMUTABLE; the git SHA is the release ID." | `.windsurf/rules/core/30-ops.md:266` |
| Deps files | "Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it." | `.windsurf/rules/core/10-python.md:30` |
| Base image | "Base image is always the pinned Debian `-slim` variant on `linux/amd64`" | `.windsurf/rules/core/10-python.md:254` |
| Behaviour tests | "every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one**" | `.windsurf/rules/core/45-testing-strategy.md:20` |
| No cosmetic asserts | "never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes." | `.windsurf/rules/core/45-testing-strategy.md:21` |
| Seen red | "a non-trivial behavior's test proves something only if it has been SEEN RED" | `.windsurf/rules/core/45-testing-strategy.md:22` |
| Class proof | "Write the guard's subject five LEGITIMATE ways … and count how many it still catches" | `.windsurf/rules/core/45-testing-strategy.md:199` |

Every selection below cites a digest row or the spec section that settled it. The nginx `-slim`/non-slim split
follows the pack's serve stage (`:33`), not `10-python.md:254`, which governs Python service images.

## Phase A — The version source and the template emitter

**Interfaces — Produces:**
- `src/fabrik/version_registry.py`:
  - `VERSIONS_FILE: Path = FABRIK_ROOT / ".windsurf" / "rules" / "versions.yaml"` (module attribute, read at call
    time so a test can `monkeypatch.setattr(version_registry, "VERSIONS_FILE", tmp)`).
  - `REQUIRED_KEYS: tuple[str, ...] = ("node_lts", "debian_codename", "node_engines_floor")`.
  - `class VersionRegistryError(ValueError)`.
  - `def load_versions(path: Path | None = None) -> dict[str, str]` — reads `path or VERSIONS_FILE`, returns the
    `versions` map with every value as `str`; raises `VersionRegistryError` naming the file when it is missing,
    unparseable, or its `versions` is not a mapping, and naming the KEY when a required key is absent, `None`, or
    an empty/whitespace string.
- `TemplateRenderer.render(...)`: context gains `"versions": load_versions()` and `"name": spec.id`; every
  `*.j2` under the template dir renders recursively; the output key is the POSIX path relative to the template
  dir minus `.j2` (`src/pages/index.js.j2` → `"src/pages/index.js"`); writes create parent directories.
- **Mirror (named, accepted):** every template render now reads `versions.yaml`, so a registry missing one of
  the three keys fails EVERY template render (python-api included), not only docusaurus — a hub without its
  registry is broken, and failing loud with the key's name beats rendering `FROM node:--slim` (`spec § The
  delta` part 1). Output keys of the other eight templates do not change: 0 of their `.j2` files are nested (E4).

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
     sorted(template_path.rglob("*.j2")):` skipping the two top-level files already rendered, `rel =
     j2_file.relative_to(template_path)`, render `f"{spec.template}/{rel.as_posix()}"`, key
     `rel.with_suffix("").as_posix()`;
   - in the write loop (`:211-219`) call `file_path.parent.mkdir(parents=True, exist_ok=True)` before `open`.
   Leave the Jinja environment (`:43-48`) unchanged: autoescape stays on for `.j2` (it escapes only variable
   output, and the docusaurus variables are digits and codenames — E3).
4. Run the Phase A tests green, then the renderer's existing consumers:
   `PYTHONPATH=<worktree>/src .venv/bin/python -m pytest tests/test_docusaurus_static_runtime.py
   tests/test_companion_services.py tests/test_scaffold_audit_log.py -q -k "render or template or companion"`
   — expect all pass (the audit-log module also needs `FABRIK_ROOT`-reachable templates; it is the existing
   real consumer of `TemplateRenderer.render`, `tests/test_scaffold_audit_log.py:226-238`).
5. **Red-on-revert** in a throwaway worktree (`git worktree add <scratch>/probe HEAD`, apply the phase diff,
   neuter one thing at a time, never in the shared checkout): (a) drop the missing-key check → the three
   missing-key cases go red; (b) revert `rglob` to `glob` → the nested-file case goes red; (c) drop the
   `parent.mkdir` → the write case goes red; (d) drop `name` from the context → the name case goes red. Record
   each red line in the phase commit body.
6. Gate: `.venv/bin/ruff check src/fabrik/version_registry.py src/fabrik/template_renderer.py
   tests/test_docusaurus_static_runtime.py` clean; `.venv/bin/mypy src/fabrik/version_registry.py` clean;
   `python scripts/final_gate.py --lean --json` → `"status":"success"`.
7. Docs: `CHANGELOG.md` `### Changed — docusaurus static runtime, phase A: version registry loader + nested
   template rendering (2026-10-XX)`; `INDEX.md` rows for `src/fabrik/version_registry.py` and
   `tests/test_docusaurus_static_runtime.py`. Then `python scripts/enforcement/check_doc_sync.py` after staging.
8. **`/fabrik-review-scoped` on this phase's changed surface** (`version_registry.py`, `template_renderer.py`,
   the test file) plus its one hop (`spec_loader.load_spec`, the two existing renderer test consumers), run to its
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
  raises `VersionRegistryError` naming `node_lts` and writes nothing (`spec § Validation` 3, renderer half).
- **Given** a template dir with a nested `a/b/x.txt.j2`, **When** `render(dry_run=True)` runs, **Then** the
  result holds key `a/b/x.txt` with the registry's `node_lts` and the spec id rendered into it
  (`src/fabrik/template_renderer.py:160-165` today renders top-level only).
- **Given** the same template dir, **When** `render(dry_run=False)` runs, **Then** `<output>/<id>/a/b/x.txt` exists
  on disk with that content (`src/fabrik/template_renderer.py:211-219` today has no parent mkdir).

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
    tests/test_scaffold_compose_traefik.py tests/test_scaffold_doc_seeding.py -q` — expect all pass.
13. **Red-on-revert** in a throwaway worktree, one neuter at a time: (a) restore the `node:22-bookworm` literal in
    `Dockerfile.j2` → the FROM rows go red; (b) restore the `npm ci` swap in `scaffold.py` → the install-line row
    goes red; (c) drop `absolute_redirect off` → the nginx row goes red; (d) `port=3000` → the compose row goes
    red; (e) delete `src/theme/SearchBar/index.js.j2` → the nested-file rows go red through BOTH emitters; (f) the
    parity row must go red under (b) too (the scaffold's Dockerfile then differs from the renderer's), and under a
    one-character edit to the scaffold's written `nginx.conf` after rendering. Record each.
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
  the lockfile-conditional install line, and no stage runs `npm run serve` or starts Node (`spec § Validation` 1).
- **Given** a scaffolded project, **When** `nginx.conf` is read, **Then** it holds `try_files $uri $uri/
  /index.html;`, `absolute_redirect off;`, `gzip on;` with the five `gzip_types`, and the immutable
  `Cache-Control` header inside `location /assets/` only (`spec § The delta` part 3).
- **Given** a scaffolded project, **When** `compose.yaml` is parsed, **Then** the Traefik loadbalancer port and
  the healthcheck both use 80, the healthcheck path is `/docs/intro/`, and no `middlewares` label exists
  (`spec § The delta` part 7; `core/30-ops.md:195`).
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
$ grep -rn "versions.yaml\|versions_yaml" src/fabrik/*.py   → only FABRIK_ROOT path joins in cli.py; no reader
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

**E6 — no plan lock overlaps (File Scope).**

```text
$ grep -ho '"status": *"[A-Za-z-]*"' /opt/fabrik/.fabrik/plan-locks/*.json | sort | uniq -c
      1 "status": "complete"
     16 "status": "executed"
      3 "status": "failure"
     72 "status": "released"
     30 "status": "success"
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

Not yet a fixed point: `/fabrik-plan-review` follows in this same turn.

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

## Coverage Checklist

| Class | Verdict |
|---|---|
| Version pinning: no literal survives in either emitter | OPEN — Phase B rows 1, 5, 6 and the parity row |
| Emitter parity (scaffold vs template renderer) | OPEN — Phase B parity row |
| Fail-closed on a broken registry (key named, nothing half-written) | OPEN — Phase A rows 2–4, Phase B row 8 |
| Mirror of a context or loop change on the other eight templates | OPEN — E4 counts; Phase A step 4 runs the existing consumers |
| nginx behaviour (redirect form, fallback, caching scope, gzip) | OPEN — Phase C rows 1–2 |
| Compose invariants (port in both places, no middleware, no ports:) | OPEN — Phase B row 3 |
| SSR safety of the swizzled component | OPEN — Phase B row 4, Phase C row 1 |
| fail-open on a malformed row (here: a malformed registry) | OPEN — Phase A row 3 |
| cost/quota accounting (seats sized by `dispatch_headroom.py`, stamped) | OPEN — Phase C step 5 |
| boundary/sentinel (empty string, `null`, missing file, non-mapping) | OPEN — Phase A rows 2–3 |
| behavior-without-a-test | OPEN — every Behavior Contract row names its test |

The rubric this plan's reviews inject into every seat brief, run on the plan's own changed paths:

```bash
python3 scripts/review_rubric.py --changed src/fabrik/version_registry.py src/fabrik/scaffold.py src/fabrik/template_renderer.py src/fabrik/spec_generator.py templates/docusaurus/Dockerfile.j2 templates/docusaurus/nginx.conf.j2 templates/docusaurus/compose.yaml.j2 tests/test_docusaurus_static_runtime.py
```

```text
## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)
### core/35-security-auth.md
### core/25-data-postgres.md
### core/30-ops.md
### 12-FACTOR (all twelve axes)
## MATCHED — packs whose globs hit the changed paths
### core/10-python.md  (hit: src/fabrik/scaffold.py, src/fabrik/spec_generator.py, src/fabrik/template_renderer.py)
### core/45-testing-strategy.md  (hit: tests/test_docusaurus_static_runtime.py)
```
