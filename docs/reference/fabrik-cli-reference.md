# Fabrik CLI Reference

**Last Updated:** 2026-01-07

The `fabrik` CLI is the main tool for managing specs, deployments, and project structures in the Fabrik ecosystem.

---

## Core Commands

### `fabrik new`
Create a new deployment spec from a template.

**Usage:**
```bash
fabrik new <name> --template <template> [--domain <domain>] [--output <directory>]
```

**Example:**
```bash
fabrik new my-api --template python-api --domain api.example.com
```

### `fabrik plan`
Preview the deployment plan for a specific spec.

**Usage:**
```bash
fabrik plan <spec_path> [-s KEY=VALUE]
```

### `fabrik apply`
Execute the deployment for a spec.

**Usage:**
```bash
fabrik apply <spec_path> [-s KEY=VALUE] [--yes] [--skip-dns] [--skip-deploy]
```

### `fabrik status`
Check the status of a deployed service.

**Usage:**
```bash
fabrik status <spec_path>
```

### `fabrik logs`
Fetch logs for a deployed application.

**Usage:**
```bash
fabrik logs <spec_path> [--lines <n>] [--follow]
```

### `fabrik destroy`
Remove a deployed application and its associated resources.

**Usage:**
```bash
fabrik destroy <spec_path> [--yes] [--keep-dns] [--keep-files]
```

---

## Project Management

### `fabrik projects`
List all tracked projects in the Fabrik registry.

**Usage:**
```bash
fabrik projects [--status <status>] [--sync]
```

### `fabrik scan`
Scan a directory (default `/opt`) for projects and update the registry.

**Usage:**
```bash
fabrik scan [--base <path>]
```

### `fabrik scaffold`
Create a new project structure following Fabrik standards.

**Usage:**
```bash
fabrik scaffold <name> [--description <text>]
```

### `fabrik validate`
Validate a project's structure against Fabrik standards.

**Usage:**
```bash
fabrik validate <project_path>
```

### `fabrik fix`
Automatically add missing required files to a project to meet standards.

**Usage:**
```bash
fabrik fix <project_path> [--dry-run]
```

---

## Verification & Maintenance

### `fabrik verify`
Run postcondition checks against a deployed service to ensure it meets specifications.

**Usage:**
```bash
fabrik verify <domain> [--spec <type>] [--app-name <name>] [--no-rollback]
```

### `fabrik sync-models`
Sync droid model names across all Fabrik configuration and documentation files.

**Usage:**
```bash
fabrik sync-models
```

### `fabrik templates`
List all available deployment templates.

**Usage:**
```bash
fabrik templates
```

---

## See Also
- [QUICKSTART.md](../QUICKSTART.md) - Get started with Fabrik
- [ENVIRONMENT_VARIABLES.md](../ENVIRONMENT_VARIABLES.md) - Configuration reference
- [docs-updater.md](docs-updater.md) - Automatic documentation updater
