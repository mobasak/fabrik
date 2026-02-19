# Fabrik Development Mindset: Think Beyond Fabrik

**Tags:** #mindset #architecture #scaffold #deployment

When developing Fabrik, I MUST think about:

1. **Fabrik itself** - the CLI, drivers, templates
2. **ALL future projects** - that will be developed AND deployed via Fabrik

Every decision should consider:
- Will this pattern work for projects scaffolded by `fabrik new`?
- Will this convention apply to deployed WordPress sites, APIs, workers?
- Is this enforcement portable to child projects?

**Examples:**
- Type annotations → Should scaffold templates include them?
- Pre-commit hooks → Should new projects get these automatically?
- droid-review.sh → Should this be part of scaffolded projects?

**Test:** Before implementing anything in Fabrik, ask:
> "How will this affect a project created via `create_project()` and deployed via `fabrik apply`?"
