# Fabrik Spec Validation Rules

## Validation Order

1. **Schema validation** (required fields, types)
2. **Reference resolution** (items_ref, content_ref, entity.*)
3. **Localization completeness** (primary locale present)
4. **Conflict detection** (duplicate slugs, menu items)
5. **Plugin deduplication** (handle duplicates/versions)

---

## 1. Schema Validation

### Required Fields

**Site level:**
- `schema_version` (integer)
- `site.domain` (string)
- `brand.name` (string)
- `contact.email` (email)
- `languages.primary` (locale)
- `deployment.target` (string)

**Validation:**
```python
def validate_required(spec: dict) -> list[str]:
    errors = []
    required = [
        'schema_version',
        'site.domain',
        'brand.name',
        'contact.email',
        'languages.primary',
        'deployment.target'
    ]
    for path in required:
        if not get_nested(spec, path):
            errors.append(f"Missing required field: {path}")
    return errors
```

### Type Validation

```python
TYPES = {
    'schema_version': int,
    'site.domain': str,
    'brand.colors.primary': str,  # hex color
    'languages.primary': str,     # locale format
    'contact.email': str,         # email format
}

def validate_types(spec: dict) -> list[str]:
    errors = []
    for path, expected_type in TYPES.items():
        value = get_nested(spec, path)
        if value and not isinstance(value, expected_type):
            errors.append(f"{path}: expected {expected_type}, got {type(value)}")
    return errors
```

---

## 2. Reference Resolution

### items_ref Validation

```python
def validate_items_ref(section: dict, spec: dict) -> Optional[str]:
    """Validate items_ref points to existing content."""
    if 'items_ref' not in section:
        return None
    
    ref = section['items_ref']  # e.g., "content.testimonials"
    
    # Check if items provided (overrides ref)
    if section.get('items'):
        return None  # items override, ref not used
    
    # Resolve reference
    value = get_nested(spec, ref)
    if value is None:
        return f"Reference '{ref}' not found in spec"
    
    if not isinstance(value, list):
        return f"Reference '{ref}' must be an array, got {type(value)}"
    
    return None
```

### content_ref Validation

```python
def validate_content_ref(section: dict, spec: dict) -> Optional[str]:
    """Validate content_ref points to existing content."""
    if 'content_ref' not in section:
        return None
    
    ref = section['content_ref']
    
    # Check if inline content provided (overrides ref)
    if section.get('content'):
        return None
    
    # Resolve reference
    value = get_nested(spec, ref)
    if value is None:
        return f"Reference '{ref}' not found in spec"
    
    return None
```

### entity.* References

```python
def validate_entity_ref(section: dict, context: str) -> Optional[str]:
    """Validate entity.* references only in entity page templates."""
    ref = section.get('content_ref', '')
    
    if ref.startswith('entity.'):
        if context != 'entity_page_template':
            return f"Reference '{ref}' only valid in entity page templates"
    
    return None
```

---

## 3. Localization Completeness

### Primary Locale Required

```python
def validate_localized_string(value: dict, primary: str, field_path: str) -> list[str]:
    """Validate localized string has primary locale."""
    errors = []
    
    if not isinstance(value, dict):
        errors.append(f"{field_path}: localized string must be a dict, got {type(value)}")
        return errors
    
    if primary not in value:
        errors.append(f"{field_path}: missing primary locale '{primary}'")
    
    return errors
```

### Locale Key Validation

```python
def validate_locale_keys(value: dict, allowed_locales: list[str], field_path: str) -> list[str]:
    """Validate all locale keys are in languages list."""
    errors = []
    
    for locale in value.keys():
        if locale not in allowed_locales:
            errors.append(f"{field_path}: locale '{locale}' not in languages list")
    
    return errors
```

### Array Localization Consistency

```python
def validate_localized_array(items: list, primary: str, field_path: str) -> list[str]:
    """Validate all items in array have consistent localization."""
    errors = []
    
    for i, item in enumerate(items):
        # Find localized fields
        for key, value in item.items():
            if isinstance(value, dict) and primary in value:
                # This is a localized field
                if primary not in value:
                    errors.append(f"{field_path}[{i}].{key}: missing primary locale")
    
    return errors
```

### Fallback Policy

**Default:** Warn on missing additional locales, use primary as fallback

```python
def apply_locale_fallback(value: dict, primary: str, additional: list[str]) -> dict:
    """Apply fallback for missing additional locales."""
    result = value.copy()
    
    for locale in additional:
        if locale not in result:
            logger.warning(f"Missing locale '{locale}', using primary '{primary}' as fallback")
            result[locale] = result[primary]
    
    return result
```

---

## 4. Conflict Detection

### Duplicate Slugs

```python
def detect_slug_conflicts(pages: list) -> list[str]:
    """Detect duplicate page slugs."""
    errors = []
    seen = {}
    
    for page in pages:
        slug = page.get('slug', '')
        if slug in seen:
            errors.append(f"Duplicate slug '{slug}' in pages (sources: {seen[slug]}, {page.get('source', 'explicit')})")
        else:
            seen[slug] = page.get('source', 'explicit')
    
    return errors
```

**Resolution:** Explicit pages win over generated pages

```python
def resolve_slug_conflicts(explicit_pages: list, generated_pages: list) -> list:
    """Merge pages, explicit wins on conflict."""
    explicit_slugs = {p['slug'] for p in explicit_pages}
    
    # Filter out generated pages with conflicting slugs
    filtered_generated = [
        p for p in generated_pages 
        if p['slug'] not in explicit_slugs
    ]
    
    for conflict in explicit_slugs & {p['slug'] for p in generated_pages}:
        logger.warning(f"Slug conflict '{conflict}': using explicit page, ignoring generated")
    
    return explicit_pages + filtered_generated
```

---

## 5. Plugin Deduplication

### Handle Duplicates

```python
def deduplicate_plugins(plugins: list) -> list:
    """Remove duplicate plugins, keep last occurrence."""
    seen = {}
    
    for plugin in plugins:
        # Normalize plugin name (remove version, extension)
        name = normalize_plugin_name(plugin)
        seen[name] = plugin  # Last wins
    
    return list(seen.values())

def normalize_plugin_name(plugin: str) -> str:
    """Normalize plugin name for deduplication."""
    # Remove .zip extension
    name = plugin.replace('.zip', '')
    
    # Remove version numbers (e.g., -1.2.3, -v1.2.3)
    import re
    name = re.sub(r'-v?\d+\.\d+(\.\d+)?', '', name)
    
    # Remove hash prefixes (e.g., 7aaUOmxu84su-)
    name = re.sub(r'^[a-zA-Z0-9]+-', '', name)
    
    return name
```

### Apply Skip List

```python
def apply_plugin_skip(base: list, skip: list) -> list:
    """Remove plugins in skip list from base."""
    skip_normalized = {normalize_plugin_name(p) for p in skip}
    
    return [
        p for p in base
        if normalize_plugin_name(p) not in skip_normalized
    ]
```

---

## Validation Pipeline

```python
class SpecValidator:
    def __init__(self, spec: dict):
        self.spec = spec
        self.errors = []
        self.warnings = []
    
    def validate(self) -> tuple[list[str], list[str]]:
        """Run all validations, return (errors, warnings)."""
        
        # 1. Schema validation
        self.errors.extend(validate_required(self.spec))
        self.errors.extend(validate_types(self.spec))
        
        # 2. Reference resolution
        for page in self.spec.get('pages', []):
            for section in page.get('sections', []):
                if err := validate_items_ref(section, self.spec):
                    self.errors.append(err)
                if err := validate_content_ref(section, self.spec):
                    self.errors.append(err)
        
        # 3. Localization
        primary = self.spec.get('languages', {}).get('primary')
        allowed = [primary] + self.spec.get('languages', {}).get('additional', [])
        
        for path, value in find_localized_strings(self.spec):
            self.errors.extend(validate_localized_string(value, primary, path))
            self.errors.extend(validate_locale_keys(value, allowed, path))
        
        # 4. Conflicts
        all_pages = self.spec.get('pages', []) + generate_entity_pages(self.spec)
        self.errors.extend(detect_slug_conflicts(all_pages))
        
        # 5. Plugin deduplication (warnings only)
        plugins = collect_all_plugins(self.spec)
        if len(plugins) != len(set(normalize_plugin_name(p) for p in plugins)):
            self.warnings.append("Duplicate plugins detected, will deduplicate")
        
        return self.errors, self.warnings
    
    def fail_fast(self):
        """Raise exception on first error."""
        errors, warnings = self.validate()
        
        if errors:
            raise ValidationError(f"Spec validation failed:\n" + "\n".join(errors))
        
        if warnings:
            for warning in warnings:
                logger.warning(warning)
```

---

## Error Messages

**Format:** `{field_path}: {error_description}`

**Examples:**
```
Missing required field: site.domain
brand.colors.primary: expected str, got int
Reference 'content.testimonials' not found in spec
pages[2].sections[0]: Reference 'entity.description' only valid in entity page templates
brand.tagline: missing primary locale 'en_US'
brand.tagline: locale 'fr_FR' not in languages list
Duplicate slug 'about' in pages (sources: explicit, generated)
```
