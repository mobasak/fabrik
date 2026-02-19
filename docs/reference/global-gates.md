# Global Gates Reference

**Last Updated:** 2026-02-19

Deterministic global gate runner for Fabrik projects with PROJECT/MONOREPO_ROOT classification.

---

## Classification Rules

| Condition | Mode |
|-----------|------|
| `pyproject.toml` + `/opt/<x>` (not `/opt/fabrik*`) + `.windsurf/` | `PROJECT` |
| Everything else | `MONOREPO_ROOT` |

---

## Gate Commands

| Gate | Command | cwd | Fail Condition |
|------|---------|-----|----------------|
| Tests | `pytest tests/` | `/opt/fabrik` | any failure |
| Lint | `ruff check <PATH>` | `PATH` | any violation |
| Types | `mypy <PATH>` | `PATH` | any error |
| Pre-commit | `pre-commit run --all-files` | `PATH` | any failure |
| Docs | `make docs-check` | `/opt/fabrik` | PATH ≠ `/opt/fabrik` or failure |
| Symlinks | see below | `PATH` | mismatch or missing |

---

## Symlink Integrity

Required symlinks for all projects:

| Symlink | Target |
|---------|--------|
| `.windsurfrules` | `/opt/fabrik/windsurfrules` |
| `.windsurf/rules` | `/opt/fabrik/.windsurf/rules` |

**Failure behavior:**

| Condition | PROJECT | MONOREPO_ROOT |
|-----------|---------|---------------|
| Missing symlink | FAIL (exit 2) | WARN (exit 1) |
| Wrong target | FAIL (exit 2) | WARN (exit 1) |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All gates passed |
| `1` | Warn (MONOREPO_ROOT symlink mismatch only) |
| `2` | Fail (any gate failure or PROJECT symlink issue) |

---

## Frozen — Do Not Modify

These files define the authoritative rule architecture and must not be restructured:

- `/opt/fabrik/windsurfrules`
- `/opt/fabrik/.windsurf/rules/`
- `src/fabrik/scaffold.py` (create_project / fix_project logic)

---

## Usage

```bash
# Run at repo root (default)
make global-gates

# Run with explicit path
python -m scripts.enforcement.check_global_gates --path /opt/fabrik

# Run for a specific project
python -m scripts.enforcement.check_global_gates --path /opt/myproject
```
