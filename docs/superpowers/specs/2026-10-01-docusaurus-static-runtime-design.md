# Docusaurus scaffold: a static nginx runtime with Pagefind search

Status: CONVERGED (/fabrik-spec-review, 2026-10-01, 4 passes; D-472)
Profile: delta — every intake item maps to code that exists today: the docusaurus emitters in
`src/fabrik/scaffold.py::_scaffold_docusaurus` (:6141-6438) and `src/fabrik/template_renderer.py`
(:114-165), and the templates under `templates/docusaurus/`. Personas, Rejected alternatives, Lifecycle,
the constraints digest and the fabrik-lib verdict are kept short; the delta adds no new consumer.

Work item: W-3f2d8e21 (mail 01M1G4PYGTQQGMXKK91VDKZGQJ). Beat: fleet (scaffolding).
Research ledger: `docs/reference/research/2026-10-01-docusaurus-static-runtime-ledger.md` (38 rows,
every fact fetched 2026-10-01).

## Personas

- **PRIMARY — the operator scaffolding a docs site.** No operator quote names this persona for this item;
  the brief is the work item's text: *"`templates/docusaurus/Dockerfile.j2` ends in
  `node:22-bookworm-slim` running `npm run serve`; `core/42-docusaurus.md` bans a Node runtime in
  production"*. Their loop, counted: (1) `fabrik scaffold --type docusaurus <name>`, (2) write docs and
  push, (3) `fabrik apply specs/services/<id>.yaml` — the site is live at its domain with search in the
  navbar. **Step budget: 3**, unchanged by this spec; search now works at step 3 with no extra step.
- **The site's readers** — open a page, deep-link, refresh, search. They hold no duty.
- **The hub deploy path (automated)** — `fabrik apply` builds the image and routes Traefik to the
  container port; `template_renderer.py` renders a `source: type: template` spec. Duty: none new — it
  consumes the emitted Dockerfile, compose and nginx.conf.
- **The version registry watcher (automated)** — `scripts/sysadmin/rules_currency_watch.py` refreshes
  `.windsurf/rules/versions.yaml` weekly. Duty: none new — the scaffold now reads what it writes.
- **The scaffold tests (automated)** — the rendered-output test this spec adds. Duty: fail when an emitter
  drifts from the pack.

## Goal

Every new docusaurus project serves its built site from nginx (no Node runtime), has working Pagefind
search in the navbar, and takes its Node and Debian versions from the hub's version registry — through both
emitters, so a scaffolded project and a template-rendered one are the same.

## Why this exists

The pack bans what the scaffold emits: *"Running `docusaurus serve` or any Node.js runtime in a production
container is banned — it wastes RAM serving what should be static files"*
(`.windsurf/rules/core/42-docusaurus.md:26`). Today:

- `templates/docusaurus/Dockerfile.j2:10-39` runs `npm install --omit=dev` and `npm run serve` on
  `node:22-bookworm-slim` at port 3000, so a static site carries a Node process and its node_modules.
- Pagefind is wired nowhere: the only mention in `src/fabrik/scaffold.py` is a docstring (:4161), and
  `templates/docusaurus/` has none, so the pack's § Search (:90-111) is unreachable in every scaffolded site.
- `node:22` and `bookworm` are literals (Dockerfile.j2:2,10), while the registry pins `node_lts: "24"` and
  `debian_codename: "trixie"` (`.windsurf/rules/versions.yaml:14,16`); bookworm's regular security support
  ended 2026-07-12 (versions.yaml:16).

The delta removes the Node runtime, adds search, and makes the versions follow the registry.

## What exists today (grounded)

| Surface | path:line | Today |
|---|---|---|
| Dockerfile template | `templates/docusaurus/Dockerfile.j2:1-41` | two stages, both `node:22-bookworm-slim`; runtime `npm run serve -- --port 3000`; curl healthcheck on `/` |
| Scaffold emitter, Dockerfile | `src/fabrik/scaffold.py:6417-6420` | reads Dockerfile.j2 as LITERAL text (no Jinja) and swaps `RUN npm ci` for `RUN npm install` (no lockfile at scaffold time) |
| Scaffold emitter, compose | `src/fabrik/scaffold.py:6433-6438` | `_write_canonical_compose(port=3000, healthcheck_path="/docs/intro")`; the port lands in BOTH the healthcheck and the Traefik loadbalancer label (`scaffold.py:991-1019`) |
| Template emitter | `src/fabrik/template_renderer.py:129-165` | Jinja-renders `compose.yaml.j2`, `Dockerfile.j2` and every other `*.j2` in the template dir with context `spec, env, resources, health, …` — no versions |
| Compose template | `templates/docusaurus/compose.yaml.j2:7-28` | `NODE_ENV`/`PORT=3000` env, Traefik port 3000, healthcheck `localhost:3000/` |
| Template defaults | `templates/docusaurus/defaults.yaml` (env) | `NODE_ENV: production`, `PORT: "3000"` |
| package.json | `templates/docusaurus/package.json.j2` | `@docusaurus/core 3.7.0`, `react ^18.3.1`, `engines.node >=22`, a `serve` script, no pagefind |
| Root page | `src/fabrik/scaffold.py:6425-6432` (B45 note) | preset-classic emits no root page; under `docusaurus serve` `/` was a 404, the healthcheck uses `/docs/intro` |
| package.json render | `src/fabrik/scaffold.py:6152-6153` | literal `.replace("{{ name }}", name)`, not Jinja |
| Template renderer scope | `src/fabrik/template_renderer.py:160-165` | top-level `*.j2` only, output named by stem; Jinja env with `autoescape` on for `.j2` and the default `Undefined` (:43-48) |
| Existing test | `tests/test_scaffold.py:932` | asserts `scripts["serve"] == "docusaurus serve"` |
| Version registry | `.windsurf/rules/versions.yaml:12-16` | `versions: node_lts "24", debian_codename "trixie"`; read by `rules_render_versions.py`, never by the scaffold |
| Live projects | `specs/services/` (72 `*.yaml`) | 4 docusaurus specs (`fabrik-test-docusaurus`, `my-docs-site`, `test-docs`, `test-guide-disabled`), test fixtures by their own history, each with `env: PORT: '3000'`, read by no test; 0 in `docs/PROJECT_CATALOG.md`; 0 `project.yaml` with `type: docusaurus` across the 39 under `/opt` |

## The delta — chosen approach: CLI + one swizzle (judge panel 3 of 3)

**1. One version source, validated, for both emitters.** A small loader returns the registry's `versions`
map (`FABRIK_ROOT/.windsurf/rules/versions.yaml`) and raises if `node_lts`, `debian_codename` or
`node_engines_floor` is missing or empty. Both emitters call it, so a missing key fails the scaffold or the
render with the key's name — never a silent fallback to an old literal, and never an empty string:
`template_renderer.py`'s Jinja environment uses the default `Undefined`, which renders a missing variable as
`""` (round 1 executed it: `versions={}` rendered `FROM node:--slim`), so the explicit check, not Jinja, is
the guard. `template_renderer.py` adds the map to its render context as `versions`. `scaffold.py` stops
reading templates as literal text: it renders the docusaurus `.j2` files through one Jinja environment of
its own (autoescape OFF — a Dockerfile, a JSON file and an nginx config are not HTML; `StrictUndefined`;
`keep_trailing_newline`) with the context `{name, versions}`. The scaffold's post-render `RUN npm ci` →
`RUN npm install` swap (`scaffold.py:6419`) is removed: the Dockerfile decides for itself (part 2), so both
emitters emit the same install step.

**2. The pack's two-stage Dockerfile, with four recorded deviations.** Base images render as
`node:{{ versions.node_lts }}-{{ versions.debian_codename }}-slim` (builder) and
`nginx:mainline-{{ versions.debian_codename }}` (server); the builder runs `npm run build && npx -y
pagefind --site build`; the server copies `build/` to `/usr/share/nginx/html` and `nginx.conf` to
`/etc/nginx/conf.d/default.conf`, keeps the pack's curl install, and `EXPOSE 80`. Grounded: `node:24-trixie-slim`
is Node 24.21.0 (ledger img-1), Active LTS to 2026-10-20 and supported to 2028-04-30 (img-2);
`nginx:mainline-trixie` is nginx 1.31.x on `debian:trixie-slim` with curl installed (img-3..img-5; the
round-1 probe pulled 1.31.6). The deviations from the pack's block (`core/42-docusaurus.md:35-51`):
- `COPY package*.json ./`, not `COPY package.json package-lock.json ./` (:38): the scaffold writes no
  lockfile, and Docker fails a COPY of a missing file (round 1 executed it: `stat package-lock.json: file
  does not exist`). A project that commits a lockfile still has it copied.
- `HEALTHCHECK … curl -f http://localhost:80/docs/intro/`, not `/` (:48-49): `/` is now a client-side
  redirect page, and `/docs/intro` without the slash is a 301 (executed below).
- `RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi`, not a bare `npm ci` (:39): a
  scaffolded or template-rendered project has no lockfile, and `npm ci` refuses to run without one ("The
  `npm ci` command can only install with an existing package-lock.json or npm-shrinkwrap.json", the build
  error recorded at `scaffold.py:4106-4115`); a project that commits a lockfile still gets `npm ci`.
- `pagefind` joins package.json `devDependencies` (`^1.5.2`, ledger pf-1) so `npx` runs the installed
  binary instead of fetching one at build time.

**3. nginx.conf (new `templates/docusaurus/nginx.conf.j2`).** `listen 80`; `root /usr/share/nginx/html`;
`absolute_redirect off;` — without it nginx answers a slash-less deep link with an absolute `http://`
Location behind Traefik's TLS edge (executed: `301 http://docs.example.com/docs/intro/`; with it: `301
/docs/intro/`); `location / { try_files $uri $uri/ /index.html; }` as the pack mandates (:53); `gzip on;`
with `gzip_types` covering text/css, application/javascript, application/json, image/svg+xml and
application/wasm (nginx ships `gzip off` and `text/html` only, ledger srv-13); `Cache-Control: public,
max-age=31536000, immutable` on `/assets/`, where Docusaurus writes content-hashed JS and CSS (ledger
srv-11, srv-12). Everything else — HTML, `/img/`, fonts, `/pagefind/` — keeps nginx's default
revalidation, because those names are not known to be content-hashed and an immutable header on a stable
name pins a stale file in browsers for a year. That is narrower than the pack's "JS/CSS/fonts/images/WASM"
(:53) and is routed as a pack conflict. Jinja leaves `$uri` alone; the file holds no `{{`.

**4. A root page, so `/index.html` exists.** `templates/docusaurus/src/pages/index.js.j2` redirects to
`/docs/intro` with Docusaurus's `Redirect`. Without it the pack's fallback points at a file that does not
exist and nginx loops: the round-1 probe answered `/nope` with 500 and logged `rewrite or internal
redirection cycle while internally redirecting to "/index.html"`, and `/` with 403. With it, `/nope` answers
200 (the masking routed in § Pack conflicts).

**5. Search: the Pagefind CLI plus one swizzled `SearchBar`.** The builder produces `build/pagefind/`, which
carries Pagefind's Component UI: `pagefind-component-ui.js` and `pagefind-component-ui.css`, mounted as the
`pagefind-modal-trigger` and `pagefind-modal` elements (ledger pf-12, pf-17 — raw-fetched in review round 1; pf-13).
`templates/docusaurus/src/theme/SearchBar/index.js.j2` — the pack's "one sanctioned swizzle" (:103-106) —
loads those two files from `/pagefind/` and renders the two elements in the navbar. No search package is
added; Pagefind has no server component (pf-4), so nginx alone serves it. The two `.js.j2` files contain
JSX braces, so each body is wrapped in `{% raw %}…{% endraw %}` and renders verbatim through either emitter.

**6. Both emitters write every file.** `template_renderer.py` renders `*.j2` files recursively, keeping each
file's path relative to the template dir, so `src/pages/index.js.j2` lands at `src/pages/index.js`. No
template has a nested `.j2` today (0 of 26), so no other template's output changes. `scaffold.py` renders
the same template files by name: `Dockerfile.j2`, `nginx.conf.j2`, `package.json.j2`,
`src/pages/index.js.j2`, `src/theme/SearchBar/index.js.j2`.

**7. Port 80, no middleware.** `_write_canonical_compose(port=80, healthcheck_path="/docs/intro/")`;
`compose.yaml.j2` moves the Traefik port and healthcheck to 80 and drops `NODE_ENV`/`PORT`; `defaults.yaml`
drops both env keys. No Traefik middleware is added: the hub's rule is "public = none"
(`core/30-ops.md:153`, `CLAUDE.md` § HARD STOPS), and nginx compresses instead (part 3). The docusaurus
pack's own compose adds `gzip@docker` (:79); that pack-vs-pack conflict is routed.

**8. package.json** drops the `serve` script and sets `engines.node` to `>={{ versions.node_engines_floor
}}` (versions.yaml:15, "22"), rendered by Jinja in both emitters. The template emitter's context has no
`name`, so its package.json already renders the name as `-docs` today; that pre-existing gap is the plan's to
close (§ Open unknowns). `tests/test_scaffold.py:932`, which
asserts `scripts["serve"] == "docusaurus serve"`, changes in the same build. The Docusaurus pin stays 3.7.0
(W-cdf69863).

## Contract deltas

No data contract or UI design contract applies; the hub has neither for scaffold templates. The emitted
artifacts change as follows (the shape every new docusaurus project inherits, through either emitter):

| Artifact | Before | After |
|---|---|---|
| `Dockerfile` | Node runtime, port 3000, `npm run serve` | nginx runtime, port 80, static `build/` + `build/pagefind/` |
| `nginx.conf` | absent | pack `try_files`, `absolute_redirect off`, gzip, `/assets/` immutable |
| `compose.yaml` | port 3000, `NODE_ENV`/`PORT` env | port 80, no env, no middleware |
| `src/pages/index.js` | absent | redirect to `/docs/intro` |
| `src/theme/SearchBar/index.js` | absent | Pagefind Component UI |
| `package.json` | `serve` script, no pagefind, `engines.node >=22` literal | `pagefind` devDependency, no `serve`, engines from the registry |

## Rejected alternatives

- **`docusaurus-plugin-pagefind`** (pf-5..pf-9): peers fit (`@docusaurus/core >=3`, `react >=18`), but the
  package is 0.2.2, created 2026-07-14, single author, 0 stars, and it runs Pagefind again in its own
  postBuild — duplicating the builder step the pack fixes — and adds `@docsearch/react`. All three judges
  failed it on duplicate functionality and maintenance risk.
- **`@getcanary/docusaurus-theme-search-pagefind`** (pf-10, pf-11): no release since 2024-10-12, peers
  stop at React 18 while Docusaurus 3.10 accepts 19 and v4 drops 18 (pf-16), and it wraps a UI Pagefind now
  ships itself. The pack already warns against adopting it unchecked (:97-101).
- **The Pagefind legacy Default UI** (`PagefindUI`, pf-14): still supported but replaced by the Component UI
  in 1.5.0 (pf-12); building on the superseded API would set up a migration.
- **Keeping Node and only adding search**: the pack bans the Node runtime (:26), so this is not an option.
- **Rendering versions at deploy time instead of scaffold time**: a deployed project would change base images
  on a redeploy without a commit, against 12-Factor V (an immutable release per commit).
- **`nginx-unprivileged` on port 8080** (img-6, img-7): would diverge from the pack's mandated serve image and
  port; routed to the pack owner (§ Pack conflicts) rather than decided here.

## Lifecycle

Adoption: every scaffold and every template render after the build lands. Growth: Pagefind's own envelope is
tens of thousands of pages (pack :92-96), far past any of our docs sites; a site that outgrows it is a
search-engine decision recorded in the pack. Degradation: a failed Pagefind run fails `docker build` (the
`&&` chain), so a site never deploys without its index. Retirement: when the registry's codename or Node
LTS moves, new scaffolds follow automatically; existing projects move only when someone re-renders their
Dockerfile. A Docusaurus major that drops the `SearchBar` theme slot breaks the swizzle once, in one hub
template.

## External dependencies

| Dependency | Grounded fact (ledger row, fetched 2026-10-01) | URL |
|---|---|---|
| Pagefind CLI 1.5.2 | current stable, released 2026-04-12 (pf-1); `npx -y pagefind --site <dir>` after the build (pf-2); output `<dir>/pagefind/` (pf-3); no server (pf-4) | https://pagefind.app/docs/ |
| Pagefind Component UI | replaces the Default UI in 1.5.0; shipped in `/pagefind/` (pf-12, pf-13) | https://github.com/CloudCannon/pagefind/releases |
| node:24-trixie-slim | Node 24.21.0 (img-1); Active LTS to 2026-10-20, EOL 2028-04-30 (img-2) | https://raw.githubusercontent.com/docker-library/official-images/master/library/node |
| nginx:mainline-trixie | nginx 1.31.x on debian:trixie-slim, curl installed (img-3..img-5; the review probe pulled 1.31.6) | https://raw.githubusercontent.com/docker-library/official-images/master/library/nginx |
| Docusaurus static output | `build/` is static; trailingSlash default emits `/docs/x/index.html` (srv-1, srv-3); `404.html` is emitted (srv-7) | https://docusaurus.io/docs/deployment |
| HTTP caching | fingerprinted URLs get `max-age=31536000`; unversioned get `no-cache` (srv-11) | https://web.dev/articles/http-cache |

## fabrik-lib verdict

No fabrik-lib module covers a static-site serving stack or search UI: build, in the hub's own templates.
Not a fabrik-lib candidate — it is scaffold output, not a reusable runtime module.

## Constraints digest

| Rule | Verbatim | file:line |
|---|---|---|
| No Node runtime | "Running `docusaurus serve` or any Node.js runtime in a production container is banned" | `core/42-docusaurus.md:26` |
| Two-stage build | "Build stage: `node:…-slim` — `npm ci` then `npm run build`, then `npx -y pagefind --site build` for search indexing." | `core/42-docusaurus.md:32` |
| Serve stage | "Serve stage: `nginx:mainline-…` — copy `build/` to `/usr/share/nginx/html`." | `core/42-docusaurus.md:33` |
| SPA fallback | "The Nginx config must include `try_files $uri $uri/ /index.html;`" | `core/42-docusaurus.md:53` |
| Asset caching | "`Cache-Control: public, max-age=31536000, immutable` for JS/CSS/fonts/images/WASM" | `core/42-docusaurus.md:53` |
| Search | "Use **Pagefind**" · "the one sanctioned swizzle" | `core/42-docusaurus.md:92`, `:105` |
| Compose | "no `ports:` section (Traefik routes traffic), `deploy.resources.limits.memory` mandatory, `platform: linux/amd64` mandatory" | `core/42-docusaurus.md:88` |
| Banned search | "**Banned here**: Algolia DocSearch and `@easyops-cn/docusaurus-search-local`" | `core/42-docusaurus.md:107` |
| Versions | "versions change HERE (or, normally, nowhere — the machinery does)" | `.windsurf/rules/versions.yaml:7` |
| No Alpine | "**No Alpine** (`-slim-bookworm` only)" — the codename half is stale against the registry (§ Pack conflicts 6) | `commands/_sources/fabrik-spec.md` § 1b-bis; versions.yaml:16 |

## Shape / infra implications

Scaffold type `docusaurus`; `shape.kind: static`, unchanged. The container port moves 3000 → 80, carried
in the Traefik label and the healthcheck by the compose writer. No registrar changes. Memory needs fall
(nginx instead of Node); the compose's limit is left to `resources.memory` as today.

## Documentation landing sites

- `docs/reference/scaffold-types.md` or the docusaurus row in `agents-fabrik.md` § Scaffold Types: the
  runtime, port and search (the plan names the exact file after grepping both).
- `CHANGELOG.md`, `INDEX.md` (the new template file and test), `docs/DECISIONS.md` (the approach row).
- The pack is infra's: the conflicts below are mailed (01M3V92T8N), never edited from this beat.

## Pack conflicts (routed to infra, not decided here)

Mail 01M3V92T8N carries 1-3; 4-6 were found in review round 1 and are mailed as 01M3VAZQPV, with the stale `check_docker.py` `APPROVED_BASES` list.

1. **`try_files $uri $uri/ /index.html`** (`core/42-docusaurus.md:53`). Docusaurus pre-renders every route to
   its own file (srv-3) and emits a real `404.html` (srv-7). Executed in round 1: with the rule and no root
   page, a missing path answers 500 (redirection cycle) and `/` 403; with a root page, a missing path answers
   200, so the 404 page never shows. Two sources converge on `try_files $uri $uri/ $uri.html =404;` with
   `error_page 404 /404.html;` (srv-9, srv-10). This spec follows the pack and adds the root page.
2. **The curl install** (:44-45) is redundant on `nginx:mainline-trixie`, which ships curl (img-5; the probe
   found `/usr/bin/curl`).
3. **Root vs unprivileged nginx**: the stock master runs as root (img-6); `nginx-unprivileged` listens on
   8080 (img-7).
4. **Middleware**: 42-docusaurus's compose adds `gzip@docker` (:79), while `core/30-ops.md:153` and the hub
   contract say "public = none". This spec follows the contract and compresses in nginx.
5. **Caching scope**: the pack's immutable header covers "JS/CSS/fonts/images/WASM" (:53); only `/assets/` is
   known to be content-hashed, so this spec caches `/assets/` only.
6. **The `/fabrik-spec` § 1b-bis constraint text** reads "-slim-bookworm only"
   (`commands/_sources/fabrik-spec.md`, § 1b-bis), while the registry moved to trixie on 2026-09-01
   (versions.yaml:16) and the pack mandates the non-slim `nginx:mainline-<codename>` serve image. The
   command text is stale against both; the design follows the registry and the pack.

## Out of scope (each with a named destination)

- The other six templates hardcode `node:22-bookworm-slim` or `python:3.12-slim-bookworm` (desktop-app,
  file-api, node-api, saas-skeleton, file-worker, and the inline python Dockerfile at `scaffold.py:5690`).
  Each is also a runtime bump with its own compatibility risk → W-d6da74e5, using this spec's loader.
- Docusaurus 3.7.0 → 3.10.2 (pf-15) → W-cdf69863 (a dependency bump with its own build test).
- Other pack divergences in the docusaurus scaffold: `onBrokenLinks: 'warn'` against the pack's `'throw'`
  (kept deliberately by the B43 note, `scaffold.py:6181-6188`), non-Ocoron colour tokens and no dark
  default (`scaffold.py:6367-6381` vs pack :148-159), no frontmatter validation script (pack :134), and the
  OpenAPI placeholder artifacts for a plugin the pack bans (`scaffold.py:6299-6346` vs pack :119) → W-9aca7862.

## Cost

No runtime cost; a smaller container (nginx instead of Node plus node_modules). Build time grows by one
Pagefind run (seconds for a small site).

## Validation

Every assertion below is proven red against today's emitter before the fix.

1. **Scaffold emitter, rendered output.** Scaffold a docusaurus project into a temp dir and assert: both
   `FROM` lines equal the values `versions.yaml` holds (read in the test, never a literal); no Node runtime
   stage and no `npm run serve`; `npx -y pagefind --site build` in the builder; `COPY package*.json` and the
   lockfile-conditional install line, with no post-render `npm install` swap;
   `nginx.conf` holds the pack's `try_files` line, `absolute_redirect off`, `gzip on` and the `/assets/`
   immutable header; compose port 80 in BOTH the Traefik label and the healthcheck, healthcheck path
   `/docs/intro/`, no middleware label; `src/pages/index.js` and `src/theme/SearchBar/index.js` exist with
   no `{%` or `{{ versions` left in them; package.json has `pagefind`, no `serve`, and `engines.node` from
   the registry.
2. **Template emitter, the same assertions** through `template_renderer.py` for a `source: type: template`
   spec, including the two nested files, so the emitters cannot drift.
3. **A missing registry key fails both emitters** with the key's name (one test per emitter).
4. **One real build** (opt-in, like the real-PG tests): `docker build` of a scaffolded site succeeds with no
   lockfile; in the running container `curl /docs/intro/` answers 200, `curl /docs/intro` answers a
   RELATIVE 301, `/pagefind/pagefind-component-ui.js` answers 200, a
   missing path answers 200 (the pack's fallback, not a 500), and the built `index.html` of a doc page
   contains the `pagefind-modal-trigger` element.

## Decisions taken

- The search integration: Pagefind CLI + one swizzled SearchBar (3 of 3 judges; the pack's floor).
- The pack's `try_files` rule is followed as written, with a root page added; the conflicts are mailed.
- Versions are rendered at scaffold or render time from the registry, through both emitters, with an
  explicit missing-key check.
- `template_renderer.py` renders `*.j2` recursively (0 of 26 templates have nested files today).
- No Traefik middleware on the docs site; nginx compresses.
- Existing docusaurus projects: none catalogued. The four fixture specs are read by no test, so nothing
  re-renders them; their `PORT: '3000'` env is inert under nginx and is left alone. `fabrik-test-docusaurus`
  builds from its own GitHub repo, so this change never reaches it unless that repo is re-scaffolded.
Recorded as D-472.

## Open / blocking unknowns

- **Is the `fabrik-test-docusaurus` E2E container from 2026-04 still running on vps1?** It builds from its
  own GitHub repo, so this change does not reach it; if it is still up it keeps serving with Node until that
  repo is re-scaffolded or the container is retired. Resolution: a read-only `docker ps` on vps1 at plan
  time, by fleet; not run from a spec.
- `template_renderer.py` has no `name` in its render context (:129-140), so package.json.j2 renders
  `"-docs"` through the template emitter today. Resolution: the plan adds `name` (the spec id) to that
  context or records why the template path never needs a package name.

## Review record

`/fabrik-spec-review`, 2026-10-01. Native seats only (D-181), partitioned by section (D-212, D-218): `rules`
(Opus — § The delta, Contract deltas, Constraints digest, Validation, Pack conflicts, Decisions taken), `rest`
(Sonnet — every other section), `facts` (Sonnet `fabrik-researcher` — § External dependencies and the ledger
rows the spec relies on). Each slice had one refuter that executed every candidate. Round-zero probes, run by
the orchestrator on `nginx:mainline-trixie` in throwaway containers: the pack's `try_files` with no root page
answers a missing path 500 (`rewrite or internal redirection cycle`) and `/` 403; with a root page, 200;
`/docs/intro` 301 with an absolute `http://` Location by default and a relative one with
`absolute_redirect off`.

| Pass | seats · axes re-checked | counters | method | spec md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 + sonnet×1 + sonnet×1 researcher (+ refuter×3) · all axes | found: 19, new: 19, confirmed: 17, fixed: 17, unexecuted: 0, edits: 17 | method: citation — full partitioned pass; 19 raised = 17 distinct (rest-S1 = rules-O9, rest-S3 = rules-O15); class rewrite of § The delta, Contract deltas, Validation, Pack conflicts, Decisions taken from the executed probes | 73ec9394… → ab5b8fa5… |
| Pass 2 | opus×1 + sonnet×1 + sonnet×1 researcher (the round-1 slice owners) · delta over the rewrite + one hop | found: 2, new: 2, confirmed: 2, fixed: 2, unexecuted: 0, edits: 6 | method: re-derivation — 19 of 19 ledger claims NOW_FALSE; 2 NEW inside the round-1 hunks (rules-O17 install step per emitter, rules-O18 an ungrounded entry-file name), own-fix: round 1 | ab5b8fa5… → 988dc8a3… |
| Pass 3 | opus×1 (round-1 owner of `rules`) · the round-2 hunks + one hop | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — rules-O17 and rules-O18 NOW_FALSE; the conditional install line executed both ways (no lockfile → `npm install`, lockfile → `npm ci`) | 988dc8a3… → 988dc8a3… ✓ |
| Pass 4 | sonnet×1 (round-1 owner of `rest`) · the round-2 hunks in its sections | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — rest-S2 and rest-S3 NOW_FALSE; the header's 38 rows re-counted by check_research_ledger.py; the template_renderer `name` gap confirmed at :129-140; `facts` standing clean since pass 2 (1 of 1 NOW_FALSE, no hunk since) | 988dc8a3… → 988dc8a3… ✓ → **CONVERGED** |

Recorded, not counted (one hop out of a fix, D-230): `spec_generator.py:112` keeps `health_path: "/docs/intro"`
while the healthcheck moves to `/docs/intro/` (curl `-f` accepts the 301; the plan aligns them);
`check_docker.py:20-26` `APPROVED_BASES` lists only bookworm bases and nothing reads it (mailed to infra,
01M3VAZQPV); the round-1 claim that Docusaurus writes content-hashed assets under `/assets/` rests on the
cisagov config's comment rather than a Docusaurus source (the plan confirms it on a real build — § Validation 4).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "`templates/docusaurus/Dockerfile.j2` ends in `node:22-bookworm-slim` running `npm run serve`" (W-3f2d8e21) | IN | § The delta 2, 6 |
| I2 | "NO Pagefind anywhere … so the pack's § Search is unreachable in every scaffolded site" | IN | § The delta 5 |
| I3 | "hardcoded `node:22` + `bookworm` against `versions.yaml`'s node_lts 24 / trixie (D-064)" | IN | § The delta 1 |
| I4 | "every existing docusaurus project's next redeploy inherits it" | IN | § What exists today (live projects); § Open unknowns |
| I5 | "Sized as a scaffold change with a rendered-output grader" | IN | § Validation 1-3 |
| I6 | The same version literals in six other templates (found this run) | OUT-OF-SCOPE | W-d6da74e5, § Out of scope |
| I7 | Docusaurus 3.7.0 is three minors behind 3.10.2 (found this run) | OUT-OF-SCOPE | W-cdf69863, § Out of scope |
| I8 | The remaining 42-docusaurus divergences: onBrokenLinks, colour tokens, dark default, frontmatter check, OpenAPI placeholders (found this run) | OUT-OF-SCOPE | W-9aca7862, § Out of scope |
| I9 | The pack's `try_files` rule loops without a root page and masks 404s (found this run) | IN (root page) + mailed | § The delta 4; § Pack conflicts 1 |
