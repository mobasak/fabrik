---
auto_execution_mode: 0
description: Run dual-model code review using droid-review.sh
---

# Code Review Workflow

Run dual-model code review for non-Traycer tasks.

> **Note:** For Traycer-managed tasks, use Traycer verification as primary. This workflow is for non-Traycer tasks only. See `.windsurf/rules/50-code-review.md` for the full protocol.

## Steps

// turbo
1. **Run pre-flight gates**:
```bash
ruff check .
mypy .
pytest tests/ -x --tb=short
```

2. **Run dual-model review** — Uses models from `config/models.yaml`:
```bash
./scripts/droid-review.sh <changed_files>
```

3. **Address findings**:
   - Fix all `error`-severity issues before proceeding
   - Fix `warning`-severity issues if reasonable
   - Document any intentional skips

4. **Re-run review** until clean:
   - Target: `"issues": []` or only minor warnings remain
   - Re-run `./scripts/droid-review.sh <changed_files>` after fixes

5. **Run convention validator**:
```bash
python3 -m scripts.enforcement.validate_conventions --strict <changed_files>
```

## Verification

- [ ] Pre-flight gates pass (lint, types, tests)
- [ ] No `error`-severity findings from review
- [ ] Convention validator passes
- [ ] Documentation updated if code changed
