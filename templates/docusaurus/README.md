# Docusaurus Template

Documentation site for SaaS products with OpenAPI integration.

## Architecture

```
docs.product.com/
├── docs/                    # Guides & tutorials (native MDX)
│   ├── getting-started.md
│   ├── guides/
│   └── tutorials/
├── api/                     # API reference (generated from OpenAPI)
│   └── [endpoints].mdx
├── blog/                    # Optional changelog/updates
├── static/                  # Assets
├── docusaurus.config.js
└── package.json
```

## Stack

- **Docusaurus 3.x** — Static site generator
- **Pagefind** — search: the Docker build runs `npx -y pagefind --site build`, and the swizzled
  `src/theme/SearchBar/index.js` mounts Pagefind's Component UI in the navbar (no search server)
- **docusaurus-plugin-openapi-docs** — Generates MDX from OpenAPI spec
- **docusaurus-theme-openapi-docs** — Interactive API explorer

## Usage

```bash
# Create a docs site for a SaaS product (writes /opt/my-product-docs and its spec)
fabrik scaffold my-product-docs --type docusaurus

# Review the spec
vim specs/services/my-product-docs.yaml

# Deploy (from the hub)
fabrik apply specs/services/my-product-docs.yaml
```

## Site options

The deploy spec carries no docusaurus-specific keys: blog, OpenAPI docs, theme and navbar are set in `docusaurus.config.js` (and the OpenAPI spec file it points at, `./openapi.yaml` by default). Search is Pagefind, built into every image.

## Deployment

Deployed with `fabrik apply` (SSH + Docker Compose, routed by Traefik) as a two-stage image: a Node
builder (`npm run build` + Pagefind) and an nginx server that serves the static `build/` on port 80 —
no Node runtime in production. `nginx.conf` sets `absolute_redirect off` (relative redirects behind
Traefik's TLS edge), gzip, and an immutable cache header on the content-hashed `/assets/`. The
healthcheck hits `/docs/intro/`; `/` is a client-side redirect page. Base images (`node:<lts>-<codename>-slim`,
`nginx:mainline-<codename>`) and `engines.node` come from `.windsurf/rules/versions.yaml` at scaffold or
render time.

## Related

- **WordPress saas preset** — Marketing site at `product.com`
- **Application** — Deployed separately at `app.product.com`
