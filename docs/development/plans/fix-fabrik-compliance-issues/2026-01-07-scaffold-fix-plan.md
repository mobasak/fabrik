# Scaffold.py Compliance Fix

**What is this?** Make `create_project()` generate Fabrik-compliant projects with all enforcement hooks active from day one.

**AI Council Review:** Gemini 3 Pro ✅, Claude Sonnet 4.5 ✅, GPT-5.2 ✅
**Status:** ⚠️ PARTIAL (AGENTS.md symlink done, test_scaffold.py missing)

---

```text
MODE: EXECUTION (PLAN LOCKED)

RULES:
- Follow steps exactly in order
- Do NOT redesign or change scope
- One step at a time
- After each step: show Evidence + Gate result
- If a Gate fails or is unclear → STOP and report
```

---

## TASK METADATA

```text
TASK:
scaffold-compliance-fix

GOAL:
New projects created via `create_project()` pass all Fabrik enforcement checks on first commit.

DONE WHEN (all true):
- AGENTS.md is symlinked to /opt/fabrik/AGENTS.md (with copy fallback)
- .pre-commit-config.yaml exists and hooks install gracefully
- Dockerfile CMD uses `src.main:app` (not `app.main:app`)
- pyproject.toml exists with ruff/mypy config
- Gate command passes: pytest tests/test_scaffold.py -v

OUT OF SCOPE:
- Profile system (--minimal flag) - future enhancement
- Progress indicators (rich library) - future enhancement
- Auto-registration in SERVICES.md - rejected by council
```

---

## GLOBAL CONSTRAINTS

```text
CONSTRAINTS:
- Language: Python 3.12
- No new deps (use stdlib only in scaffold.py)
- Follow patterns in: src/fabrik/scaffold.py
- Backward compatibility: YES (fix_project must still work)
```

---

## CANONICAL GATE

```text
CANONICAL GATE:
python -c "from fabrik.scaffold import create_project; import shutil; p = create_project('test-gate', 'Test', base=__import__('pathlib').Path('/tmp')); print('PASS' if (p/'AGENTS.md').is_symlink() and (p/'.pre-commit-config.yaml').exists() else 'FAIL'); shutil.rmtree(p)"
```

---

## EXECUTION STEPS

### Step 1 — Fix Dockerfile template

```text
DO:
- Edit templates/scaffold/docker/Dockerfile.python
- Change CMD from `app.main:app` to `src.main:app`

GATE:
- grep "src.main:app" templates/scaffold/docker/Dockerfile.python

EVIDENCE REQUIRED:
- File diff
- Gate output showing src.main:app
```

---

### Step 2 — AGENTS.md symlink with fallback

```text
DO:
- Remove "AGENTS.md": "AGENTS.md" from TEMPLATE_MAP
- Add _link_agents_md() helper function
- Call it in create_project() after other symlinks
- Symlink to /opt/fabrik/AGENTS.md, fallback to copy if not found

GATE:
- python -c "from fabrik.scaffold import create_project; import shutil; p = create_project('test-agents', 'Test', base=__import__('pathlib').Path('/tmp')); print('SYMLINK' if (p/'AGENTS.md').is_symlink() else 'COPY'); shutil.rmtree(p)"

EVIDENCE REQUIRED:
- Code diff
- Gate output showing "SYMLINK"
```

---

### Step 3 — Add pre-commit config and install

```text
DO:
- Copy templates/scaffold/pre-commit-config.yaml to .pre-commit-config.yaml
- Add _install_pre_commit() helper with shutil.which() check
- Call it after git init
- Warn (don't fail) if pre-commit not available

GATE:
- python -c "from fabrik.scaffold import create_project; import shutil; p = create_project('test-precommit', 'Test', base=__import__('pathlib').Path('/tmp')); print('PASS' if (p/'.pre-commit-config.yaml').exists() else 'FAIL'); shutil.rmtree(p)"

EVIDENCE REQUIRED:
- Code diff
- Gate output showing "PASS"
```

---

### Step 4 — Add pyproject.toml from template

```text
DO:
- Add "python/pyproject.toml.template": "pyproject.toml" to TEMPLATE_MAP
- Or create inline if template needs project name substitution

GATE:
- python -c "from fabrik.scaffold import create_project; import shutil; p = create_project('test-pyproject', 'Test', base=__import__('pathlib').Path('/tmp')); print('PASS' if (p/'pyproject.toml').exists() else 'FAIL'); shutil.rmtree(p)"

EVIDENCE REQUIRED:
- Code diff
- Gate output showing "PASS"
```

---

### Step 5 — Add input validation

```text
DO:
- Add _validate_project_name() function
- Check: lowercase, alphanumeric + hyphens, no reserved names
- Call at start of create_project()

GATE:
- python -c "from fabrik.scaffold import create_project; import pathlib; create_project('Invalid Name', 'Test', base=pathlib.Path('/tmp'))" 2>&1 | grep -q "ValueError" && echo "PASS" || echo "FAIL"

EVIDENCE REQUIRED:
- Code diff
- Gate output showing "PASS" (ValueError raised)
```

---

### Step 6 — Final verification

```text
DO:
- Run full create_project() flow
- Verify all artifacts exist
- Run pre-commit hooks on new project

GATE:
- CANONICAL GATE passes

EVIDENCE REQUIRED:
- Full gate output
- List of files in created project
```

---

## STOP CONDITIONS

```text
STOP IF:
- A gate cannot be satisfied
- Template file missing from templates/scaffold/
- pre-commit binary not found AND copy fails

ON STOP:
- Report exact blocker
- Propose at most 2 resolution options
```
