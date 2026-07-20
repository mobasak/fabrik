# Health Summary Workflow

**Last Updated:** 2026-07-20
**Status:** PRODUCTION
**Script:** `scripts/health_summary.py`
**Source Code:** `src/fabrik/cli.py` -> `fabrik scan --health`
**Outputs:**
- stdout table: `Project | Status | Missing Files`
- stdout JSON array: `--json`

> **Coders:** When modifying `scripts/health_summary.py`, update this workflow doc to match.

---

## Overview

Scans `/opt/*` project folders and checks scaffold health using six essential files. Each project is categorized as `healthy`, `warnings`, or `missing` based on how many essentials are missing.

### Data Flow

```
CLI (`python scripts/health_summary.py`) -> scan_health(root) -> filesystem checks -> table/JSON output
```

---

## Essential Files

The script verifies these files in every project folder:

1. `AGENTS.md`
2. `.env.example`
3. `project.yaml`
4. `compose.yaml`
5. `Dockerfile`
6. `.windsurfrules`

---

## Status Thresholds

| Status | Condition |
|--------|-----------|
| `healthy` | 0 missing files |
| `warnings` | 1-2 missing files |
| `missing` | 3+ missing files |

---

## Exclusion Rules

Project directories are filtered using `sync_projects._is_excluded(name)`, which uses shared `fnmatch` patterns against `DEFAULT_EXCLUDES` (`scripts/sync_projects.py:35-46`, 11 patterns): `_*`, `.*`, `fabrik`, `fabrik-lib`, `fabrik-libs`, `mt-router`, `__pycache__`, `venv`, `google`, `archived`, `containerd`.

---

## CLI Usage

```bash
# Table output (default)
python scripts/health_summary.py

# JSON output for automation
python scripts/health_summary.py --json

# Scan a different root directory
python scripts/health_summary.py --base /some/path
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All scanned projects are `healthy` |
| 1 | At least one project is `warnings` or `missing` |

---

## Trigger Conditions

| Trigger | How |
|---------|-----|
| Manual health check | `python scripts/health_summary.py` |
| Fabrik CLI health scan | `fabrik scan --health` |
