# MUST check templates before creating any document

**Tags:** #enforcement #documentation #templates #cascade_behavior

Before creating ANY .md file (plan, spec, guide, etc.), Cascade MUST:

1. Check if a template exists:
   - find_by_name in templates/docs/ for document templates
   - find_by_name in templates/scaffold/docs/ for project docs

2. If template exists → USE IT exactly
3. If no template → Ask user before freestyle

Templates location: /opt/fabrik/templates/docs/
- PLAN_TEMPLATE.md (exploration/research)
- EXECUTION_PLAN_TEMPLATE.md (locked implementation)

Violation: Creating docs without checking templates first.
