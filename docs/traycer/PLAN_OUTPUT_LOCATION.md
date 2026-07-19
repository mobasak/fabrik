# Traycer Plan Output Configuration

**Last Updated:** 2026-03-22

## Rule: Plans Must Go to Project Folder

When Traycer creates plan files (Epic Briefs, PLAN_TEMPLATE, EXECUTION_PLAN_TEMPLATE), they MUST be saved to the **current project's folder**, not `/opt/fabrik/`.

---

## Correct Locations

| Project | Plan Location | ❌ Wrong |
|---------|---------------|---------|
| `/opt/translator` | `/opt/translator/docs/development/plans/` | `/opt/fabrik/docs/development/plans/` |
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

After `fabrik scaffold`, each project has:
- `templates/docs/PLAN_TEMPLATE.md`
- `templates/docs/EXECUTION_PLAN_TEMPLATE.md`
- `templates/docs/FEATURES_TEMPLATE.md`
- `templates/docs/MODULE_REFERENCE_TEMPLATE.md`

Use these project-local templates, not Fabrik's.
