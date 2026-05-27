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

Deploy via Coolify using a **two-stage Dockerfile**:

1. **Build stage**: `node:24-bookworm-slim` — `npm ci` then `npm run build`, then `npx -y pagefind --site build` for search indexing.
2. **Serve stage**: `nginx:mainline-bookworm` — copy `build/` to `/usr/share/nginx/html`.

```dockerfile
FROM node:24-bookworm-slim AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build && npx -y pagefind --site build

FROM nginx:mainline-bookworm
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
      - coolify

networks:
  coolify:
    external: true
```

**Rules:** no `ports:` section (Traefik routes traffic), `deploy.resources.limits.memory` mandatory, `platform: linux/amd64` mandatory. See `30-ops.md` for full compose rules.

## Search

- Use **Pagefind** (`@getcanary/docusaurus-theme-search-pagefind`) exclusively. Pagefind generates compressed WASM index chunks post-build — zero bundle bloat, zero SaaS dependency, sub-millisecond client-side search.
- **Banned**: Algolia DocSearch (external SaaS dependency, requires public site), `@easyops-cn/docusaurus-search-local` (bundles entire index into JS payload, degrades TTI at scale).

## API Reference (Docusaurus sites only)

**Scope:** This section applies ONLY when embedding API docs in a Docusaurus site (developer portal for external consumers). If you're working on a `python-api` or `node-api` without a Docusaurus site, use FastAPI's built-in `/docs` + `/redoc` instead — see `15-api-contracts.md` § API Documentation.

- Use **Scalar** (`@scalar/docusaurus`) for interactive OpenAPI documentation. Scalar renders the spec dynamically on the client side — zero build-time file generation, zero Git pollution.
- Point Scalar at the API's `/openapi.json` endpoint — never copy the spec into the docs repo.
- **Banned**: `docusaurus-plugin-openapi-docs`, Redocusaurus — they generate hundreds of physical `.mdx` files at build time, inflating commits and build duration.

## Versioning

- Docusaurus native versioning (`versioned_docs/`, `npm run docusaurus docs:version`) is **banned**. It duplicates all content, creates exponential build times, and bloats Git history.
- Archive legacy versions by cutting a Git branch (`release/v1.x`) and deploying it via Coolify as an immutable static snapshot to a subpath (e.g., `/v1/`). Link from the main site's version dropdown via absolute URLs.

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
| Missing `deploy.resources.limits.memory` in compose | Always declare — Coolify v4 ignores its UI field |
| `ports:` in compose.yaml | Traefik routes all traffic — no host port bindings |

---

## Related Rule Packs

- `30-ops.md` — compose.yaml, Traefik labels, resource limits, Coolify deploy
- `40-documentation.md` — AI-friendly markdown, writing style
- `ocoron-design-system.md` — Infima token overrides, fonts, dark mode default

---

## Done When

- [ ] Dockerfile uses two-stage build: `node:24-bookworm-slim` → `nginx:mainline-bookworm`.
- [ ] Nginx serve stage has `curl` installed (stock image doesn't include it — HEALTHCHECK fails without it).
- [ ] Dockerfile has HEALTHCHECK instruction.
- [ ] Pagefind runs post-build (`npx -y pagefind --site build`) — no Algolia or JS-bundled search.
- [ ] Nginx config includes `try_files $uri $uri/ /index.html;` for SPA routing.
- [ ] compose.yaml has `platform: linux/amd64`, `deploy.resources.limits.memory`, Traefik labels, `coolify` network, no `ports:`.
- [ ] `docusaurus.config.js` sets `onBrokenLinks: 'throw'` and `onBrokenAnchors: 'throw'`.
- [ ] All `.md`/`.mdx` files have `title` and `description` frontmatter.
- [ ] No `versioned_docs/` or `versioned_sidebars/` directories exist.
- [ ] API docs use Scalar (`@scalar/docusaurus`) — no static OpenAPI generators.
- [ ] Interactive MDX components registered globally in `src/theme/MDXComponents.js`.
- [ ] Static assets served with immutable cache headers.
- [ ] Fonts self-hosted in `static/fonts/` — no Google Fonts CDN.
