---
activation: glob
globs: ["**/docusaurus.config.*", "**/sidebars.*"]
description: Docusaurus discipline — MDX, sidebar org, versioning, search, deployment, content quality
trigger: glob
---
<!-- CONSUMER: Coding agents building Docusaurus sites
     GOAL: Docusaurus-specific rules — static generation, Pagefind search, Scalar API docs, deployment
     TRAYCER USAGE: Injects as Context File for docusaurus scaffold tickets.
     AGENT USAGE: Follow verbatim when working on Docusaurus projects. -->

# Docusaurus Rules

Apply when working on Docusaurus documentation sites — config, content, deployment, or plugins. Skip for Next.js apps, APIs, or non-documentation frontends.

## When Docusaurus Does NOT Make Sense

Do not use Docusaurus when:
- **Non-technical editors** need a visual CMS — use WordPress instead.
- **Dynamic user-generated content**, real-time DB mutations, or server-side state is required — use Next.js.
- **Trivial single-page tools** or internal micro-utilities — a plain `README.md` or single HTML file is sufficient.

## Static Generation Only

- Docusaurus must compile to **pure static HTML/CSS/JS**. Running `docusaurus serve` or any Node.js runtime in a production container is banned — it wastes RAM serving what should be static files.

## Docker Deployment

Deploy via `fabrik apply` using a **two-stage Dockerfile**:

1. **Build stage**: `node:<!--v:node_lts-->24<!--/v-->-<!--v:debian_codename-->trixie<!--/v-->-slim` — `npm ci` then `npm run build`, then `npx -y pagefind --site build` for search indexing.
2. **Serve stage**: `nginx:mainline-<!--v:debian_codename-->trixie<!--/v-->` — copy `build/` to `/usr/share/nginx/html`.

```dockerfile
FROM node:<!--v:node_lts-->24<!--/v-->-<!--v:debian_codename-->trixie<!--/v-->-slim AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build && npx -y pagefind --site build

FROM nginx:mainline-<!--v:debian_codename-->trixie<!--/v-->
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:80/ || exit 1
EXPOSE 80
```

The Nginx config must include `try_files $uri $uri/ /index.html;` to support Docusaurus client-side (React Router) deep links and hard refreshes. Cache static assets aggressively: `Cache-Control: public, max-age=31536000, immutable` for JS/CSS/fonts/images/WASM.

**compose.yaml:**

```yaml
services:
  docs:
    build: .
    platform: linux/amd64
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:80/"]
      interval: 30s
      timeout: 5s
      retries: 3
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: '0.5'
    labels:
      - traefik.enable=true
      - traefik.http.routers.docs.rule=Host(`docs.${DOMAIN}`)
      - traefik.http.routers.docs.entrypoints=websecure
      - traefik.http.routers.docs.tls.certresolver=letsencrypt
      - traefik.http.services.docs.loadbalancer.server.port=80
      - traefik.http.routers.docs.middlewares=gzip@docker
    networks:
      - fabrik

networks:
  fabrik:
    external: true
```

**Rules:** no `ports:` section (Traefik routes traffic), `deploy.resources.limits.memory` mandatory, `platform: linux/amd64` mandatory. See `30-ops.md` for full compose rules.

## Search

- Use **Pagefind**: it generates compressed WASM index chunks post-build — zero bundle bloat, zero SaaS
  dependency, no server, and it is the right shape for a docs site at our scale — Pagefind's own
  stated envelope is "tens of thousands of pages", with a ~300kB total network payload on a
  10,000-page site. (Past that the index fetch is what tells; a hosted engine becomes the better
  tool long before any of our sites get there.)
  ⚠️ **Pagefind is the mandate; a specific PLUGIN is not.** `@getcanary/docusaurus-theme-search-pagefind`
  is the long-standing integration (and is in production use), but CHECK IT BEFORE ADOPTING: at last
  look it had gone well over a year without a release, and its peer range does not declare the
  current Docusaurus/React majors (exact ranges + dates: `CLAIMS.yaml::pagefind-plugin-maintenance-risk`
  — kept there so they are dated and re-verified rather than rotting in prose). If it does not resolve
  against the site's majors, switch integration rather than abandoning Pagefind —
  `docusaurus-plugin-pagefind` is maintained and declares current majors. The floor fallback always
  works: run the `pagefind` CLI at build (the Dockerfile
  already does) and swizzle `SearchBar` — **the one sanctioned swizzle**, notwithstanding
  § Styling & Swizzling's keep-it-minimal rule.
- **Banned here**: Algolia DocSearch and `@easyops-cn/docusaurus-search-local`. ⚠️ Not because they are
  bad — Algolia is Docusaurus's own first-class option and is the better tool at large scale or when
  search is a product feature. They are banned by OUR constraints: Algolia is an external SaaS whose
  free DocSearch tier requires a public site (both disqualifying for private/self-hosted docs), and the
  easyops local plugin ships the whole index in the JS payload, which degrades TTI as the corpus grows.

## API Reference (Docusaurus sites only)

**Scope:** This section applies ONLY when embedding API docs in a Docusaurus site (developer portal for external consumers). If you're working on a `python-api` or `node-api` without a Docusaurus site, use FastAPI's built-in `/docs` + `/redoc` instead — see `15-api-contracts.md` § API Documentation.

- Use **Scalar** (`@scalar/docusaurus`) for interactive OpenAPI documentation. Scalar renders the spec dynamically on the client side — zero build-time file generation, zero Git pollution.
- Point Scalar at the API's `/openapi.json` endpoint — never copy the spec into the docs repo.
- **Banned**: `docusaurus-plugin-openapi-docs`, Redocusaurus — they generate hundreds of physical `.mdx` files at build time, inflating commits and build duration.

## Versioning

- Docusaurus native versioning (`versioned_docs/`, `npm run docusaurus docs:version`) is **banned**. It duplicates all content, creates build times that multiply per retained version, and bloats Git history.
- Archive legacy versions by cutting a Git branch (`release/v1.x`) and deploying it via `fabrik apply` as an immutable static snapshot to a subpath (e.g., `/v1/`). Link from the main site's version dropdown via absolute URLs.

## Internationalization

- Use the native Docusaurus **Git-based i18n** folder structure (`i18n/tr/docusaurus-plugin-content-docs/current/`). Extract UI strings with `npm run write-translations`.
- **Banned**: Crowdin or any third-party SaaS translation platform — unnecessary dependency and workflow complexity for a solo developer.

## Content Quality

- `docusaurus.config.js` must set `onBrokenLinks: 'throw'` and `onBrokenAnchors: 'throw'`. The build fails on any broken internal link or anchor — broken docs never reach production.
- Every `.md` and `.mdx` file must have `title` and `description` in YAML frontmatter. Enforce via a pre-build validation script (Python `python-frontmatter` or equivalent).

## MDX & Authoring

- Write standard documentation prose in **CommonMark**. Reserve JSX/MDX exclusively for interactive elements that cannot be represented natively (live code editors, terminal simulators, API testers).
- Register shared interactive components globally in `src/theme/MDXComponents.js`. Never use fragile relative imports (`import X from '../../components/X'`) in individual `.mdx` files.

## Sidebar Organisation

- Define sidebars manually in `sidebars.js` using nested category-based architecture. Use the `generated-index` link type for category landing pages.
- Avoid relying purely on filesystem-based auto-generation for large sites — it produces poorly categorised navigation.

## Styling & Swizzling

- Override **Infima CSS variables** in `custom.css` with Ocoron Design System tokens:
  - `--ifm-color-primary` → `#5B5BF7` (accent)
  - `--ifm-color-primary-dark` → `#4D4DE0`
  - `--ifm-color-primary-light` → `#7676FF`
  - `--ifm-background-color` → `#0A0A0A` (surface-0)
  - `--ifm-background-surface-color` → `#141414` (surface-1)
  - Map all surface, text, and border tokens from the design system.
- Load **Space Grotesk** (headings), **Inter** (body), **JetBrains Mono** (code) **self-hosted** in `static/fonts/` and declared in `custom.css` (no Google Fonts — external dependency + GDPR concern). Override Infima's default font stack:
  - `--ifm-font-family-base` → `'Inter', sans-serif`
  - `--ifm-heading-font-family` → `'Space Grotesk', sans-serif`
  - `--ifm-font-family-monospace` → `'JetBrains Mono', monospace`
- Set `colorMode.defaultMode: 'dark'` in `docusaurus.config.js`. Dark mode is the Ocoron default.
- Sidebar navigation uses the Ocoron surface hierarchy (`--surface-0` background, `--surface-1` for active items).
- Keep swizzling (`npm run swizzle`) to an absolute minimum — ejected internal components break on major Docusaurus upgrades.

## Repository Scale

- Separate Fabrik products with distinct audiences must use **separate Docusaurus instances** within a monorepo workspace (Turborepo / npm workspaces). Do not use the multi-instance docs plugin within a single site — it couples unrelated build lifecycles.

---

## Doc Sync — a docs site is still a deployed service (D-065)

A Docusaurus site ships as a container behind Traefik via `fabrik apply`, so the hub's deploy AI
needs it in the two files it reads to learn what runs on the VPS. A static site is the easiest one
to forget precisely because it feels like "just docs".

- `docs/DEPLOYMENT.md` — the two-stage build, the serve image, the domain, and `target_vps` if it
  is not the hub.
- `docs/OPERATIONS.md` — how the site is rebuilt/redeployed and where its build breaks surface.
- Any scheduled content job (link-check, rebuild-on-source-change) belongs in the jobs/intervals
  inventory in `docs/RESILIENCE.md`, not only in CI config.

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| `docusaurus serve` or Node.js runtime in production | Multi-stage Docker: build → nginx static serve |
| Algolia DocSearch | Pagefind (WASM, post-build, self-hosted) |
| `@easyops-cn/docusaurus-search-local` | Pagefind |
| `docusaurus-plugin-openapi-docs` / Redocusaurus | Scalar (`@scalar/docusaurus`, client-side) |
| Native `versioned_docs/` versioning | Git branch archive → static subpath deploy |
| Crowdin or SaaS translation platforms | Native Git-based `i18n/` folder structure |
| Relative JSX imports in `.mdx` files | Global registration in `src/theme/MDXComponents.js` |
| Heavy component swizzling | Infima CSS variable overrides in `custom.css` |
| Google Fonts CDN | Self-hosted fonts in `static/fonts/` |
| Missing `deploy.resources.limits.memory` in compose | Always declare — `fabrik apply` rejects services without it |
| `ports:` in compose.yaml | Traefik routes all traffic — no host port bindings |

---

## Related Rule Packs

- `30-ops.md` — compose.yaml, Traefik labels, resource limits, `fabrik apply` deploy
- `40-documentation.md` — AI-friendly markdown, writing style
- `ocoron-design-system.md` — Infima token overrides, fonts, dark mode default

---

## Done When

- [ ] Dockerfile uses two-stage build: `node:<!--v:node_lts-->24<!--/v-->-<!--v:debian_codename-->trixie<!--/v-->-slim` → `nginx:mainline-<!--v:debian_codename-->trixie<!--/v-->` — a STATIC serve stage, never a Node runtime.
- [ ] Nginx serve stage has `curl` installed (stock image doesn't include it — HEALTHCHECK fails without it).
- [ ] Dockerfile has HEALTHCHECK instruction.
- [ ] `docs/DEPLOYMENT.md` + `docs/OPERATIONS.md` name this site as a deployed service (D-065) — the
      hub's deploy AI reads them to learn what runs on the VPS.
- [ ] Pagefind runs post-build (`npx -y pagefind --site build`) — no Algolia or JS-bundled search.
- [ ] Nginx config includes `try_files $uri $uri/ /index.html;` for SPA routing.
- [ ] compose.yaml has `platform: linux/amd64`, `deploy.resources.limits.memory`, Traefik labels, `fabrik` network, no `ports:`.
- [ ] `docusaurus.config.js` sets `onBrokenLinks: 'throw'` and `onBrokenAnchors: 'throw'`.
- [ ] All `.md`/`.mdx` files have `title` and `description` frontmatter.
- [ ] No `versioned_docs/` or `versioned_sidebars/` directories exist.
- [ ] API docs use Scalar (`@scalar/docusaurus`) — no static OpenAPI generators.
- [ ] Interactive MDX components registered globally in `src/theme/MDXComponents.js`.
- [ ] Static assets served with immutable cache headers.
- [ ] Fonts self-hosted in `static/fonts/` — no Google Fonts CDN.
