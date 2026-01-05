# WordPress v2 Critical Fixes (ChatGPT Review)

**Date:** 2025-12-25
**Status:** ✅ Fixed and tested
**Review Source:** ChatGPT architectural review

---

## Critical Issues Found

ChatGPT identified 2 critical blockers that would break idempotency and hierarchy:

### 1. Entity Page Slugs Contained Slashes ❌

**Problem:**
- `PageGenerator` created slugs like `"services/ai-consultancy"`
- WordPress REST API **rejects slugs with `/`**
- Created slug would be different (e.g., `"services-ai-consultancy"`)
- `find_page()` lookup would fail → **idempotency broken**
- No `parent_id` set → **hierarchy lost**

**Root Cause:**
```python
# page_generator.py (OLD)
full_slug = f"{parent_slug}/{slug}"  # "services/ai-consultancy"
page = {
    'slug': full_slug,  # ❌ Contains slash
    # No parent_id reference
}
```

**Fix:**
```python
# page_generator.py (NEW)
page = {
    'slug': slug,  # ✅ Child slug only: "ai-consultancy"
    'parent_slug': parent_slug,  # ✅ Explicit parent reference: "services"
}
```

**Deployer Update:**
```python
# deployer.py (NEW)
# Use parent_slug field instead of parsing slashes
for page_spec in page_specs:
    parent_slug = page_spec.get('parent_slug')
    if parent_slug:
        # Group as child of parent
        pages_by_parent[parent_slug].append(page_spec)
```

---

### 2. Preset Entity Config Was Dropped ❌

**Problem:**
- Preset defined `entities.services` as dict with `parent_page`, `page_template`, `generate_pages`
- `spec_loader._normalize()` **overwrote** entire dict with site's services list
- Config lost
- `PageGenerator` hardcoded `parent_slug='services'` and `template_name='service-detail'`
- **Can't customize parent or template per preset**

**Root Cause:**
```python
# spec_loader.py (OLD)
if isinstance(spec[key], list):
    spec["entities"][key] = spec[key]  # ❌ Overwrites preset config
```

**Fix:**
```python
# spec_loader.py (NEW)
if isinstance(spec[key], list):
    preset_config = spec["entities"][key].copy()
    preset_config["items"] = spec[key]  # ✅ Keep config, add data as 'items'
    spec["entities"][key] = preset_config
```

**New Structure:**
```yaml
# After merge and normalization
entities:
  services:
    parent_page: "services"          # From preset
    page_template: "service-detail"  # From preset
    generate_pages: true             # From preset
    items:                           # From site
      - slug: consulting
        name: {en_US: "Consulting"}
```

**PageGenerator Update:**
```python
# page_generator.py (NEW)
entity_config = entities.get('services', {})
if isinstance(entity_config, dict):
    items = entity_config.get('items', [])
    parent_slug = entity_config.get('parent_page', 'services')  # ✅ From preset
    template_name = entity_config.get('page_template', 'service-detail')  # ✅ From preset
```

**SectionRenderer Update:**
```python
# section_renderer.py (NEW)
services_data = self._resolve_ref('entities.services')
if isinstance(services_data, dict):
    services = services_data.get('items', [])  # ✅ Extract items
```

---

## Test Results

### Before Fixes
```
❌ Entity pages had slugs like "services/consulting" (invalid for WP)
❌ Preset config dropped (parent_page, page_template lost)
❌ Idempotency would fail (slug mismatch)
❌ Hierarchy lost (no parent_id)
```

### After Fixes
```
✅ Entity pages have child slug only: "consulting"
✅ Entity pages have parent_slug field: "services"
✅ Preset config preserved: {items: [...], parent_page: "...", page_template: "..."}
✅ 15 pages generated (7 templates + 8 entities)
✅ Deployer dry-run passes all steps
✅ Section renderer handles new format
```

### Verification
```python
# Test 1: Preset config preserved
services_config = spec['entities']['services']
assert isinstance(services_config, dict)
assert 'items' in services_config
assert services_config['parent_page'] == 'services'
assert services_config['page_template'] == 'service-detail'
# ✅ PASS

# Test 2: Entity page slugs
entity_pages = [p for p in pages if p.get('source') == 'entity']
first_page = entity_pages[0]
assert '/' not in first_page['slug']  # No slashes
assert first_page['parent_slug'] == 'services'  # Has parent reference
# ✅ PASS
```

---

## Impact

### Idempotency Now Works
**Before:** `find_page("services/consulting", None)` → Not found (slug mismatch)
**After:** `find_page("consulting", parent_id=3)` → Found (correct slug + parent)

### Hierarchy Preserved
**Before:** All entity pages created as top-level (no parent)
**After:** Entity pages created as children of parent page

### Preset Customization Works
**Before:** All services under `/services` with `service-detail` template (hardcoded)
**After:** Preset can specify custom parent and template per entity type

---

## Files Changed

| File | Changes | Lines |
|------|---------|-------|
| `spec_loader.py` | Preserve preset config, add items as subkey | ~30 |
| `page_generator.py` | Return child slug only, read config from preset | ~40 |
| `section_renderer.py` | Handle new entity config format | ~8 |
| `deployer.py` | Use parent_slug field instead of parsing slashes | ~15 |

---

## Additional Recommendations (Not Implemented)

ChatGPT also suggested (non-blocking):

1. **Merge semantics:** Document array replace behavior, handle type mismatches
2. **Validation:** Check duplicate paths, unresolved placeholders
3. **Path normalization:** Handle case, trailing slashes, WP auto-suffix (`-2`)
4. **Concurrent deploys:** Add per-site locks
5. **Renderer:** Validate section catalog matches presets

These can be addressed in future iterations.

---

## Summary

Both critical blockers fixed:
- ✅ Entity page slugs are WordPress-compatible (no slashes)
- ✅ Preset entity config is preserved (parent_page, page_template)

The v2 architecture is now **functionally correct** and ready for production testing.
