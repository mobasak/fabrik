# Template Renderer

**Last Updated:** 2026-02-22

The `TemplateRenderer` class (`src/fabrik/template_renderer.py`) renders deployment templates from specs.

---

## Overview

```python
from fabrik.template_renderer import TemplateRenderer

renderer = TemplateRenderer()
files = renderer.render(spec, secrets={"DB_PASSWORD": "secret"}, dry_run=True)
```

---

## Methods

| Method | Description |
|--------|-------------|
| `list_templates()` | Returns list of available template names |
| `template_exists(name)` | Check if a template exists |
| `render(spec, secrets, dry_run)` | Render template files for a spec |

---

## Security

- **Path traversal prevention**: Both `render()` and `template_exists()` validate that template paths stay within the templates directory using `.resolve().relative_to()`.
  - `render()` raises `ValueError` if template path escapes the directory
  - `template_exists()` returns `False` for escaped paths (safe default)
  - Example blocked input: `../../etc/passwd`

---

## Related

- [Templates Reference](templates.md)
- [Orchestrator Reference](orchestrator.md)
