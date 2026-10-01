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
# Create docs site for a SaaS product
fabrik new my-product-docs --template=docusaurus

# Edit spec
vim sites/my-product-docs.yaml

# Deploy
fabrik apply sites/my-product-docs.yaml
```

## Spec Options

```yaml
name: my-product-docs
template: docusaurus
domain: docs.myproduct.com

openapi:
  spec_url: https://api.myproduct.com/openapi.json
  # Or local file
  spec_file: ./openapi.yaml

features:
  blog: false  # Optional changelog
  search: true
  versioning: false  # Enable for multi-version docs

theme:
  primary_color: "#2563eb"
  logo: ./static/logo.svg
```

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
