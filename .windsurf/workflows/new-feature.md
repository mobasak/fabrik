---
auto_execution_mode: 0
description: Start a new feature following Fabrik conventions
---

# New Feature Workflow

Start a new feature following Fabrik conventions and planning requirements.

## Prerequisites

- [ ] Traycer plan exists in `docs/development/plans/` (or manual plan created)
- [ ] Plan indexed in `docs/development/PLANS.md`
- [ ] Plan has `**Status:** NOT_STARTED` or `IN_PROGRESS`

## Steps

1. **Create feature branch**:
```bash
git checkout -b feature/<name>
```

2. **Create/update plan document** in `docs/development/plans/` following naming convention:
   - Filename: `YYYY-MM-DD-plan-<name>.md`
   - See `AGENTS.md` for required sections: Goal, DONE WHEN, Out of Scope, Steps

3. **Implement feature** one step at a time per plan:
   - Complete each step before moving to next
   - Update plan checkboxes as you go
   - Run review after each significant change

4. **Run pre-commit**:
```bash
pre-commit run --all-files
```

// turbo
5. **Run tests**:
```bash
pytest tests/ -x --tb=short
```

6. **Create PR**:
   - Reference the plan document in PR description
   - Ensure all plan checkboxes are checked

## Verification

- [ ] Plan document exists in `docs/development/plans/`
- [ ] Plan indexed in `docs/development/PLANS.md`
- [ ] All tests pass
- [ ] Pre-commit hooks pass
- [ ] `CHANGELOG.md` updated with feature description
