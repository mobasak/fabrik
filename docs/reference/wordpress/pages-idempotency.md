# WordPress Pages: Path-Based Keys & Idempotency

**Date:** 2025-12-25
**Status:** ✅ Implemented and tested
**Module:** `src/fabrik/wordpress/pages.py`

---

## Problem Statement

The original `PageCreator.create_all()` had two critical issues:

### 1. Slug Collision Risk

**Old behavior:**
```python
created[slug] = page  # Stores by slug only
```

**Problem:**
```yaml
pages:
  - slug: consulting
    title: "Consulting"
  - slug: services
    children:
      - slug: consulting  # COLLISION! Overwrites first consulting
        title: "Consulting Service"
```

Result: Data loss in the returned dict. Only one "consulting" page accessible.

### 2. Non-Idempotent Creation

**Old behavior:**
- Always creates new pages
- Re-running deployer duplicates all pages
- No way to detect "already exists"

**Problem:**
- CI/CD pipelines can't safely re-run
- Manual fixes require deleting all pages first
- State tracking impossible

---

## Solution: Path-Based Keys + Idempotent Creation

### Implementation

**Three new methods in `PageCreator`:**

1. **`find_page(slug, parent_id)`** - Query existing pages
2. **`create_or_get_page(...)`** - Idempotent creation
3. **`create_all(..., parent_path)`** - Path-based keys

### Path-Based Keys

**New behavior:**
```python
path = f"{parent_path}/{slug}".strip("/")
created[path] = page
```

**Result:**
```python
{
    "": CreatedPage(...),                      # Homepage
    "about": CreatedPage(...),                 # /about
    "services": CreatedPage(...),              # /services
    "services/consulting": CreatedPage(...),   # /services/consulting (child)
    "consulting": CreatedPage(...),            # /consulting (top-level)
}
```

**No collisions possible** - full path uniquely identifies each page.

### Idempotent Creation

**New behavior:**
```python
def create_or_get_page(title, slug, parent_id, ...):
    # Try to find existing
    existing = self.find_page(slug, parent_id)
    if existing:
        return existing  # Reuse

    # Create new
    return self.create_page(...)
```

**Result:**
- First run: Creates all pages
- Second run: Finds existing pages, returns same IDs
- No duplicates

---

## API Changes

### Before (v1)

```python
creator = PageCreator(...)
pages = creator.create_all([
    {"slug": "about", "title": "About"},
    {"slug": "services", "children": [
        {"slug": "consulting", "title": "Consulting"}
    ]}
])

# Returns:
# {
#     "about": CreatedPage(id=1),
#     "services": CreatedPage(id=2),
#     "consulting": CreatedPage(id=3)  # COLLISION RISK
# }
```

### After (v2)

```python
creator = PageCreator(...)
pages = creator.create_all([
    {"slug": "about", "title": "About"},
    {"slug": "services", "children": [
        {"slug": "consulting", "title": "Consulting"}
    ]}
])

# Returns:
# {
#     "about": CreatedPage(id=1),
#     "services": CreatedPage(id=2),
#     "services/consulting": CreatedPage(id=3)  # COLLISION-SAFE
# }

# Access by path:
services_page = pages["services"]
consulting_page = pages["services/consulting"]
```

---

## Deployer Integration

### Challenge

PageGenerator returns flat list with paths like `"services/consulting"`, but PageCreator expects hierarchical structure with `children` arrays.

### Solution

**Two-pass hierarchy building in deployer:**

```python
# First pass: Group children by parent
pages_by_parent = {}
top_level_specs = []

for page_spec in page_specs:
    slug = page_spec.get('slug', '')

    if '/' in slug:
        # Child page
        parent_slug, child_slug = slug.split('/', 1)
        pages_by_parent[parent_slug].append({
            'slug': child_slug,
            ...
        })
    else:
        # Top-level page
        top_level_specs.append(page_spec)

# Second pass: Attach children
for page_spec in top_level_specs:
    slug = page_spec.get('slug', '')
    if slug in pages_by_parent:
        page_spec['children'] = pages_by_parent[slug]
```

**Result:** Hierarchical structure for PageCreator, path-based keys in return value.

---

## Test Results

### Collision Prevention

```
Input: 15 pages (7 top-level + 8 service children)
Output: 15 unique paths

Paths:
  '' (homepage)
  'about'
  'services'
  'services/investment-incentives'
  'services/foreign-trade'
  'services/ai-consultancy'
  'services/manufacturing'
  'services/logistics'
  'services/b2b-marketing'
  'services/medical-procurement'
  'services/quality-management'
  'contact'
  'insights'
  'privacy-policy'
  'terms'

✅ No collisions: 15 paths, 15 unique
```

### Idempotency

```
Test: Create same page twice

First call:  create_or_get_page('about', None) → Page(id=2)
Second call: create_or_get_page('about', None) → Page(id=2)

✅ Same page returned (idempotent)
```

### Hierarchy Preservation

```
CMS Structure:
  /services (id=3, parent=None)
    ├─ /services/consulting (id=4, parent=3)
    ├─ /services/implementation (id=5, parent=3)
    └─ /services/support (id=6, parent=3)

Return Value:
  {
    "services": Page(id=3),
    "services/consulting": Page(id=4),
    "services/implementation": Page(id=5),
    "services/support": Page(id=6)
  }

✅ Hierarchy in CMS, flat dict for O(1) access
```

---

## Benefits

### 1. Collision-Safe

**Before:** Slug-only keys could collide
**After:** Full path keys are unique

### 2. Idempotent

**Before:** Re-run creates duplicates
**After:** Re-run reuses existing pages

### 3. CI/CD Ready

**Before:** Manual cleanup required between runs
**After:** Safe to run repeatedly

### 4. State Tracking Ready

**Before:** No way to detect "already deployed"
**After:** `find_page()` enables state comparison

### 5. Fast Lookup

**Before:** O(n) tree traversal
**After:** O(1) dict lookup by path

### 6. URL-Aligned

**Before:** Keys don't match URLs
**After:** Path keys match URL structure

---

## Future Enhancements

### 1. Content Hashing (Detect Updates)

```python
def needs_update(existing_page, new_content):
    existing_hash = hashlib.sha256(existing_page.content.encode()).hexdigest()
    new_hash = hashlib.sha256(new_content.encode()).hexdigest()
    return existing_hash != new_hash

def create_or_update_page(...):
    existing = find_page(slug, parent_id)
    if existing:
        if needs_update(existing, content):
            update_page(existing.id, content)
        return existing
    return create_page(...)
```

### 2. Dry-Run Mode

```python
def create_all(pages, dry_run=False):
    if dry_run:
        # Return what WOULD be created
        return simulate_creation(pages)
    return actual_creation(pages)
```

### 3. Parallel Creation

```python
# Create independent pages in parallel
async def create_all_parallel(pages):
    tasks = []
    for page in pages:
        if not page.get('children'):
            tasks.append(create_page_async(page))

    await asyncio.gather(*tasks)
```

### 4. Dependency Ordering

```python
# Ensure parents created before children
def topological_sort(pages):
    # Sort by depth (parents first)
    return sorted(pages, key=lambda p: p['slug'].count('/'))
```

---

## Migration Guide

### For Existing Code

**Old code:**
```python
pages = creator.create_all(page_specs)
about_page = pages["about"]
```

**New code (same):**
```python
pages = creator.create_all(page_specs)
about_page = pages["about"]  # Still works for top-level
```

**New code (child pages):**
```python
pages = creator.create_all(page_specs)
consulting_page = pages["services/consulting"]  # Use full path
```

### For Deployer Code

**No changes required** - deployer automatically builds hierarchical structure and uses path-based keys.

---

## Summary

Path-based keys + idempotent creation provide a **production-ready foundation** for WordPress page management:

- ✅ Collision-safe (15/15 unique paths)
- ✅ Idempotent (safe re-runs)
- ✅ Fast lookup (O(1) by path)
- ✅ Hierarchy preserved (in CMS)
- ✅ CI/CD ready (no manual cleanup)
- ✅ State tracking ready (find_page)

**Critical for v2 architecture** where entity pages (`services/consulting`) must coexist with potential top-level pages of the same slug.
