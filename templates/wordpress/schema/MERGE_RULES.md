# Fabrik Spec Merge Rules

## Merge Order

```
defaults.yaml → presets/<preset>.yaml → sites/<domain>.yaml → .env secrets → runtime flags
```

Precedence: **Right wins** (site overrides preset overrides defaults)

---

## Merge Semantics by Type

### 1. Maps (Dictionaries)

**Rule:** Deep merge with right-side precedence

```yaml
# defaults.yaml
brand:
  colors:
    primary: "#1e3a5f"
    secondary: "#0891b2"

# site.yaml
brand:
  colors:
    primary: "#FF0000"  # Override

# Result:
brand:
  colors:
    primary: "#FF0000"   # From site
    secondary: "#0891b2" # From defaults
```

### 2. Arrays

**Rule:** Replace by default (no append/merge)

```yaml
# defaults.yaml
plugins:
  base: [wp-mail-smtp, generatepress]

# preset.yaml
plugins:
  base: [rank-math, fluent-forms]

# Result:
plugins:
  base: [rank-math, fluent-forms]  # Preset replaces defaults
```

**Exception:** Arrays marked with `_merge: append` or `_merge: unique`

```yaml
# preset.yaml
plugins:
  add: [wpml, thrive-architect]
  _merge: append

# site.yaml
plugins:
  add: [complianz-pro]
  _merge: append

# Result:
plugins:
  add: [wpml, thrive-architect, complianz-pro]  # Appended
```

### 3. Primitives (strings, numbers, booleans)

**Rule:** Replace (right wins)

```yaml
# defaults.yaml
timezone: UTC

# site.yaml
timezone: Europe/Istanbul

# Result:
timezone: Europe/Istanbul
```

---

## Special Cases

### Plugin Layering

```yaml
# defaults.yaml
plugins:
  base: [wp-mail-smtp, generatepress, rank-math]

# preset.yaml
plugins:
  add: [wpml, thrive-architect]
  skip: [rank-math]  # Remove from base

# site.yaml
plugins:
  add: [complianz-pro]

# Result:
plugins:
  final: [wp-mail-smtp, generatepress, wpml, thrive-architect, complianz-pro]
  # rank-math removed by skip
```

**Rules:**
- `base` from defaults
- `add` from preset + site (appended)
- `skip` removes from final list
- Duplicates removed (last occurrence wins)

### Page Templates vs Entity-Generated Pages

```yaml
# preset.yaml
page_templates:
  services:
    slug: services
    title: {en_US: "Services"}

entities:
  services:
    generate_pages: true
    parent_page: services

# site.yaml
services:
  - slug: consulting
    name: {en_US: "Consulting"}

# Result:
pages:
  - slug: services (from page_templates)
    children:
      - slug: services/consulting (generated from entity)
```

**Conflict Resolution:**
- Explicit pages in `pages:` override generated pages (by slug)
- Generated entity pages become children of parent_page
- If slug collision: explicit page wins, log warning

### Deployment Targets

```yaml
# defaults.yaml
deployment:
  targets:
    production:
      server_profile: vps1
      ssl: letsencrypt
      backup:
        frequency: daily
        retention_days: 30

# site.yaml
deployment:
  target: production
  targets:
    production:
      backup:
        retention_days: 90  # Override one field

# Result (deep merge):
deployment:
  target: production
  targets:
    production:
      server_profile: vps1      # From defaults
      ssl: letsencrypt          # From defaults
      backup:
        frequency: daily        # From defaults
        retention_days: 90      # From site (overridden)
```

---

## Reference Resolution

### items_ref vs inline items

```yaml
# Priority: inline items > items_ref

sections:
  - type: testimonials
    items_ref: content.testimonials  # Pull from content pool
    items: []  # If provided, overrides items_ref

# If items_ref points to missing path:
# - Fail validation with error: "Reference 'content.testimonials' not found"
```

### content_ref

```yaml
sections:
  - type: rich_text
    content_ref: content.about  # Must exist in content: namespace

# Validation:
# - Resolve all *_ref at load time
# - Fail fast with source path if missing
```

### entity.* references

```yaml
# In generated entity pages:
sections:
  - type: rich_text
    content_ref: entity.description  # Refers to current entity

# Resolved at page generation time
# entity.* only valid in entity page templates
```

---

## Localization Rules

### Required vs Optional Locales

```yaml
languages:
  primary: en_US    # Required
  additional: [tr_TR]  # Optional

brand:
  tagline:
    en_US: "English"  # Required (primary)
    tr_TR: "Türkçe"   # Optional (additional)
```

**Rules:**
1. Primary locale MUST be present in all localized strings
2. Additional locales MAY be missing
3. Fallback: Use primary locale if additional missing
4. Validation: Fail if primary locale missing

### Partial Localization in Arrays

```yaml
# INVALID (partial localization):
content:
  value_props:
    - title: {en_US: "Value 1", tr_TR: "Değer 1"}
    - title: {en_US: "Value 2"}  # Missing tr_TR

# Validation: Warn or fail based on policy
# Default: Warn + use primary as fallback
```

### Locale Key Validation

```yaml
languages:
  primary: en_US
  additional: [tr_TR]

brand:
  tagline:
    en_US: "English"
    fr_FR: "Français"  # ERROR: fr_FR not in languages list

# Validation: Fail if locale key not in languages
```

---

## Schema Normalization

### Top-level vs entities namespace

Both accepted, normalized to `entities.*`:

```yaml
# Input (site.yaml):
services:
  - slug: consulting

# Normalized internally:
entities:
  services:
    - slug: consulting
```

**Accepted top-level keys:**
- `services` → `entities.services`
- `features` → `entities.features`
- `products` → `entities.products`
- `locations` → `entities.locations`

---

## Validation Order

1. **Load** each layer (defaults, preset, site)
2. **Normalize** (top-level entities, locale keys)
3. **Merge** (apply rules above)
4. **Validate schema** (required fields, types)
5. **Resolve references** (items_ref, content_ref)
6. **Check localization** (primary present, keys valid)
7. **Generate pages** (from entities + templates)
8. **Detect conflicts** (duplicate slugs)

**Fail fast:** Stop at first validation error with clear message
