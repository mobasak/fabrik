# Docusaurus scaffold: a static nginx runtime with Pagefind search

Status: DRAFT
Profile: delta — every intake item maps to code that exists today: the docusaurus emitters in
`src/fabrik/scaffold.py::_scaffold_docusaurus` (:6141-6438) and `src/fabrik/template_renderer.py`
(:114-165), and the templates under `templates/docusaurus/`. Personas, Rejected alternatives, Lifecycle,
the constraints digest and the fabrik-lib verdict are kept short; the delta adds no new consumer.

Work item: W-3f2d8e21 (mail 01M1G4PYGTQQGMXKK91VDKZGQJ). Beat: fleet (scaffolding).
Research ledger: `docs/reference/research/2026-10-01-docusaurus-static-runtime-ledger.md` (37 rows,
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
| Root page | `src/fabrik/scaffold.py:6425-6432` (B45 note) | preset-classic emits no root page, so `/` is a 404; the healthcheck uses `/docs/intro` |
| Version registry | `.windsurf/rules/versions.yaml:12-16` | `versions: node_lts "24", debian_codename "trixie"`; read by `rules_render_versions.py`, never by the scaffold |
| Live projects | `specs/services/` (72 files) | 4 docusaurus specs (`fabrik-test-docusaurus`, `my-docs-site`, `test-docs`, `test-guide-disabled`), all test fixtures by their own history; 0 in `docs/PROJECT_CATALOG.md`; 0 `project.yaml` with `type: docusaurus` across 39 under `/opt` |

## The delta — chosen approach: CLI + one swizzle (judge panel 3 of 3)

**1. One version source for both emitters.** A small loader returns the registry's `versions` map
(`FABRIK_ROOT/.windsurf/rules/versions.yaml`). `template_renderer.py` adds it to the render context as
`versions`; `scaffold.py` renders `Dockerfile.j2` through Jinja with the same map instead of reading it as
literal text (the existing `npm ci` → `npm install` swap stays, applied after rendering). The Dockerfile
template then reads `node:{{ versions.node_lts }}-{{ versions.debian_codename }}-slim` and
`nginx:mainline-{{ versions.debian_codename }}`. A missing registry or key fails the scaffold loudly —
never a silent fallback to an old literal.

**2. The pack's two-stage Dockerfile** (`core/42-docusaurus.md:35-51`, verbatim except the version
tokens): builder `npm ci` (scaffold: `npm install`) → `npm run build && npx -y pagefind --site build`;
server `nginx:mainline-<codename>`, `COPY --from=builder /app/build /usr/share/nginx/html`,
`COPY nginx.conf /etc/nginx/conf.d/default.conf`, `HEALTHCHECK … curl -f http://localhost:80/docs/intro`,
`EXPOSE 80`. Grounded: `node:24-trixie-slim` resolves to Node 24.21.0 (ledger img-1), Node 24 is Active
LTS until 2026-10-20 and supported to 2028-04-30 (img-2); `nginx:mainline-trixie` is nginx 1.31.4 on
`debian:trixie-slim` (img-3, img-4) and already installs curl (img-5), so the pack's curl step is redundant
but harmless and is kept to match the pack. `pagefind` joins package.json `devDependencies` (pinned
`^1.5.2`, ledger pf-1) so `npx` resolves the locally installed binary rather than fetching at build time.

**3. nginx.conf (new `templates/docusaurus/nginx.conf.j2`)** — `listen 80`; `root /usr/share/nginx/html`;
`location / { try_files $uri $uri/ /index.html; }` as the pack mandates (:53); hashed assets under
`/assets/` get `Cache-Control: public, max-age=31536000, immutable` (pack :53, ledger srv-11, srv-12); HTML
and `/pagefind/` keep nginx's default revalidation (the Pagefind entry file is not content-hashed, pf-3).
gzip stays at the edge: the compose adds Traefik's `gzip@docker` middleware, as the pack's compose does
(:79), so nginx needs no gzip block.

**4. A root page, so `/index.html` exists.** The scaffold writes `src/pages/index.js` that redirects to
`/docs/intro` (Docusaurus `Redirect`). Without it the pack's `try_files … /index.html` fallback points at a
file that does not exist (the B45 note measured `/` as a 404), and nginx re-enters the same location for
the fallback — an internal redirection cycle that answers 500 instead of 404 (see § Pack conflicts).

**5. Search: the Pagefind CLI plus one swizzled `SearchBar`.** The builder already produces
`build/pagefind/`, which carries Pagefind's own Component UI (`pagefind-component-ui.js/.css`, new in
1.5.0, ledger pf-12, pf-13). The scaffold writes `src/theme/SearchBar/index.js` — the pack's "one
sanctioned swizzle" (:103-106) — a small component that loads those two files from `/pagefind/` and
renders the `pagefind-modal-trigger` and `pagefind-modal` elements in the navbar. No search package is
added. Pagefind has no server component (pf-4), so nginx alone serves it.

**6. Port 80 end to end.** `_write_canonical_compose(port=80, healthcheck_path="/docs/intro",
extra_labels=("traefik.http.routers.<name>.middlewares=gzip@docker",))`; `compose.yaml.j2` moves the
Traefik port and healthcheck to 80, adds the same middleware label and drops `NODE_ENV`/`PORT`;
`defaults.yaml` drops `NODE_ENV` and `PORT`. The healthcheck stays on `/docs/intro`, a pre-rendered file,
rather than `/`, which is now a client-side redirect.

**7. package.json** drops the `serve` script (nothing serves with Node any more) and raises
`engines.node` to the registry's `node_engines_floor` (versions.yaml:15, "22"). The Docusaurus version pin
stays 3.7.0 (see § Out of scope).

## Contract deltas

No data contract or UI design contract applies: the hub has neither for scaffold templates. The emitted
artifacts change as follows (the shape every docusaurus project inherits):

| Artifact | Before | After |
|---|---|---|
| `Dockerfile` | Node runtime, port 3000, `npm run serve` | nginx runtime, port 80, static `build/` + `build/pagefind/` |
| `nginx.conf` | absent | pack config + asset caching |
| `compose.yaml` | port 3000, no middleware | port 80, `gzip@docker` |
| `src/pages/index.js` | absent | redirect to `/docs/intro` |
| `src/theme/SearchBar/index.js` | absent | Pagefind Component UI |
| `package.json` | `serve` script, no pagefind | `pagefind` devDependency, no `serve` |

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
| nginx:mainline-trixie | nginx 1.31.4 on debian:trixie-slim, curl installed (img-3..img-5) | https://raw.githubusercontent.com/docker-library/official-images/master/library/nginx |
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
| No Alpine | "**No Alpine** (`-slim-bookworm` only)" — trixie is the registry's current codename | `/fabrik-spec` § 1b-bis; versions.yaml:16 |

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

1. **`try_files $uri $uri/ /index.html`** (`core/42-docusaurus.md:53`). Docusaurus pre-renders every route
   to its own file (srv-3) and emits a real `404.html` (srv-7), so a blanket fallback to `/index.html`
   answers 200 for every typo, and when `/index.html` is missing it loops. Two sources converge on
   `try_files $uri $uri/ $uri.html =404;` with `error_page 404 /404.html;` (srv-9, srv-10). This spec
   follows the pack (pack outranks external practice) and adds the root page so the loop cannot happen.
2. **The curl install step** (:44-45) is redundant on `nginx:mainline-trixie`, which installs curl (img-5).
3. **Root vs unprivileged nginx**: the stock image's master runs as root (img-6); `nginx-unprivileged`
   listens on 8080 (img-7). A pack decision, not a scaffold one.

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

1. A rendered-output test scaffolds a docusaurus project into a temp dir and asserts: both `FROM` lines
   match `versions.yaml` (read in the test, never a literal); no `npm run serve` or Node runtime stage;
   `npx -y pagefind --site build` in the builder; `nginx.conf` holds the pack's `try_files` line and the
   asset cache header; compose port 80 in both the Traefik label and the healthcheck, plus `gzip@docker`;
   `src/pages/index.js` and `src/theme/SearchBar/index.js` exist; package.json has `pagefind` and no
   `serve`.
2. The same assertions through `template_renderer.py` for a `source: type: template` spec, so the two
   emitters cannot drift.
3. A test that a missing registry key fails the scaffold (no silent literal fallback).
4. One real `docker build` of a scaffolded site at plan execution (opt-in, like the real-PG tests): the image
   builds, `build/pagefind/pagefind-entry.json` exists, and `curl /docs/intro` answers 200 from nginx.
   Every assertion is proven red against today's emitter before the fix.

## Decisions taken

- The search integration: Pagefind CLI + one swizzled SearchBar (3 of 3 judges; the pack's floor).
- The pack's `try_files` rule is followed as written, with a root page added; the better rule is mailed to
  infra.
- Versions are rendered at scaffold time from the registry, through both emitters, failing loudly.
- Existing docusaurus projects: none catalogued; the four fixtures re-render on their next test run.
These become one `docs/DECISIONS.md` row at convergence.

## Open / blocking unknowns

- **Is the `fabrik-test-docusaurus` E2E container from 2026-04 still running on vps1?** If it is, its next
  `fabrik apply` moves it from port 3000 to 80 (Traefik follows the label, so no manual step). Resolution:
  a read-only `docker ps` on vps1 at plan time, by fleet; not run from a spec.
- The exact Component UI markup is quoted from the Pagefind docs through a crawl (pf-12); the plan
  re-fetches the raw page before writing the component.

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
