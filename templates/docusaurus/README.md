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

Deployed as static site via:
- Coolify (Docker nginx)
- Or Cloudflare Pages (faster, recommended)

## Related

- **WordPress saas preset** — Marketing site at `product.com`
- **Application** — Deployed separately at `app.product.com`
