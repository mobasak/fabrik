# Fabrik CLI Reference

**Last Updated:** 2026-02-28

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
fabrik apply <spec_path> [-s KEY=VALUE] [--yes] [--skip-dns] [--skip-deploy] [--dry-run] [--use-orchestrator]
```

**Secrets Loading:**
Fabrik automatically loads secrets from the project's `.env` file at `/opt/{project_id}/.env`. Secret loading precedence:
1. Command-line `-s` flags (highest)
2. Project `.env` file
3. Environment variables (lowest)

**Example:**
```bash
# Set secrets in project .env file
# /opt/my-api/.env
API_KEY=your_key
DATABASE_PASSWORD=your_password

# Deploy - secrets auto-loaded from .env file
fabrik apply /opt/fabrik/specs/services/my-api.yaml
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

## AI Commands

### `fabrik ai generate`
Generate content from a prompt using the configured LLM provider.

**Usage:**
```bash
fabrik ai generate "<prompt>" [--provider claude|openai] [--model <model>] [-s <system>]
```

### `fabrik ai revise`
Revise a file based on AI-generated feedback.

**Usage:**
```bash
fabrik ai revise <file> "<instructions>" [--provider claude|openai] [-o <output>]
```

### `fabrik ai usage`
Show usage totals and per-model cost breakdown.

**Usage:**
```bash
fabrik ai usage [--month YYYY-MM] [--project <name>]
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
fabrik scaffold <name> [--description <text>] [--type <type>] [--preset <preset>]
```

### `fabrik validate`
Validate a project's structure against Fabrik standards.

**Usage:**
```bash
fabrik validate <project_path> [--type <type>]
```

### `fabrik fix`
Automatically add missing required files to a project to meet standards.

**Usage:**
```bash
fabrik fix <project_path> [--dry-run] [--type <type>]
```

---

## Verification & Maintenance

### `fabrik verify`
Run postcondition checks against a deployed service to ensure it meets specifications.

**Usage:**
```bash
fabrik verify <domain> [--spec <type>] [--app-name <name>] [--no-rollback]
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
- .env.example - Configuration reference
- [FINAL_GATE_WORKFLOW.md](../workflows/FINAL_GATE_WORKFLOW.md) - Quality gate workflow
