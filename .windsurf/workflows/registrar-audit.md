---
auto_execution_mode: 0
description: Run a registrar drift audit on current or all specs (read-only — surfaces MISSING/DRIFT, no mutations)
---

# /registrar-audit

Run a registrar drift audit on the current spec or all specs.

## Usage

- `/registrar-audit` — audit current project's spec
- `/registrar-audit --all` — audit every spec under `specs/services/`

## Steps

1. Run `fabrik audit-registrars [--spec specs/services/<current>.yaml]`.
2. Review the output table with the user.
3. For each MISSING (✗) registrar:
   - Confirm the registrar SHOULD run (shape contract correct?).
   - Run `fabrik redeploy --refresh-infra --spec specs/services/<id>.yaml`.
4. For each DRIFT (⚠️) registrar:
   - Surface to user with both sides.
   - User decides; either edit spec OR remove live state via `fabrik destroy --partial <reg>` (G-F5).
5. Re-run audit; expect zero MISSING and zero DRIFT.

## Notes

- Do NOT manually edit VPS configs.
- If a registrar repeatedly fails, file an issue.
