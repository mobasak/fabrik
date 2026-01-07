# WordPress

**Last Updated:** 2026-01-07

## Purpose

Automates WordPress site deployment, configuration, and content management via the Fabrik CLI and SiteDeployer.

## Usage

```python
from fabrik.wordpress import SiteDeployer, load_spec

deployer = SiteDeployer()
spec = load_spec("specs/my-site.yaml")
result = deployer.deploy(spec)
```

## Configuration

| Env Var | Description | Default |
|---------|-------------|---------|
| `WP_ADMIN_USER` | Admin username for new sites | `admin` |
| `WP_ADMIN_PASSWORD` | Admin password | - |
| `WP_ADMIN_EMAIL` | Admin email | - |

## Ownership

- **Owner:** Platform Team
- **SLA:** Best effort (Internal tool)

## See Also

- [WordPress Architecture](wordpress/architecture.md)
- [Site Specification](../reference/wordpress/site-specification.md)
