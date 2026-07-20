# Traycer Plan Output Configuration

**Last Updated:** 2026-03-22

## Rule: Plans Must Go to Project Folder

When Traycer creates plan files (Epic Briefs, PLAN_TEMPLATE, EXECUTION_PLAN_TEMPLATE), they MUST be saved to the **current project's folder**, not `/opt/fabrik/`.

---

## Correct Locations

| Project | Plan Location | ❌ Wrong |
|---------|---------------|---------|
| `/opt/captcha` | `/opt/captcha/docs/development/plans/` | `/opt/fabrik/docs/development/plans/` |
| `/opt/site-provisioner` | `/opt/site-provisioner/docs/development/plans/` | `/opt/fabrik/docs/development/plans/` |
| `/opt/fabrik` | `/opt/fabrik/docs/development/plans/` | ✅ (This is Fabrik itself) |

---

## User Instruction for Traycer

**When saving plans from Traycer IDE:**

1. Open project folder in Traycer/Windsurf
2. Generate plan (Epic Brief, etc.)
3. Save to `docs/development/plans/YYYY-MM-DD-plan-name.md`
4. **Verify path** - ensure it's `/opt/<current-project>/docs/development/plans/`, NOT `/opt/fabrik/`

**Each project is self-contained** - no cross-project plan references.

---

## Templates Available in Every Project

The `templates/docs/` path was removed (`src/fabrik/scaffold.py:1173`: "templates/docs/ removed - templates/scaffold/docs/ is the canonical source"). Of the 4 templates this section used to list, only 1 still lands in scaffolded projects:

- `FEATURES_TEMPLATE.md` — still live, now sourced from `templates/scaffold/docs/FEATURES_TEMPLATE.md`, landing at `docs/reference/scaffold-templates/FEATURES_TEMPLATE.md` in each scaffolded project (confirmed present in `/opt/site-provisioner`).
- `PLAN_TEMPLATE.md`, `EXECUTION_PLAN_TEMPLATE.md`, `MODULE_REFERENCE_TEMPLATE.md` — retired; they survive only as historical copies under `templates/.archive/legacy-docs-2026-03-24/` and are not injected into any live scaffolded project.

Use the project-local `docs/reference/scaffold-templates/FEATURES_TEMPLATE.md`, not Fabrik's.
