# i18n Kit — Multilingual GUI Template

Drop-in internationalization for any web SaaS project. Zero dependencies. Works with Flask, FastAPI, Next.js, static HTML — anything that serves HTML + JS.

## Quick Start (5 minutes)

### 1. Copy files to your project

```
cp static/js/i18n.js      YOUR_PROJECT/static/js/
cp static/i18n/en.json    YOUR_PROJECT/static/i18n/
cp scripts/validate_i18n.py YOUR_PROJECT/scripts/
```

### 2. Add to your base template `<head>`

```html
<script src="/static/js/i18n.js?v=1"></script>
```

Must be in `<head>`, not end of `<body>`. Loads synchronously (~5ms) to prevent flash-of-English.

### 3. Wire your HTML strings

```html
<!-- Before -->
<h1>Dashboard</h1>
<button>Save</button>

<!-- After -->
<h1 data-i18n="nav.dashboard">Dashboard</h1>
<button data-i18n="common.save">Save</button>
```

English text stays as fallback. `data-i18n` tells the loader which key to replace it with.

### 4. Wire your JS strings

```javascript
// Before
if (!confirm('Delete this?')) return;

// After
if (!confirm(I18N.t('common.confirm_delete'))) return;
```

### 5. Add language switcher

Copy `snippets/navbar-switcher.html` into your navbar. Or `snippets/footer-switcher.html` for minimal pages.

### 6. Add a new language

```bash
# 1. Copy en.json → tr.json
cp static/i18n/en.json static/i18n/tr.json

# 2. Translate all values (AI first pass)
# Use Claude/GPT: "Translate the values in this JSON to Turkish.
#   Keep keys unchanged. Keep {variables} unchanged.
#   Tone: direct, technical, concise. Informal register."

# 3. Validate with Kilo
python scripts/validate_i18n.py --validate tr

# 4. Auto-fixes applied. Review and ship.
```

## Files

| File | Size | Purpose |
|------|------|---------|
| `static/js/i18n.js` | 166 lines | Client-side loader. Detects language, loads JSON, replaces DOM text. Includes `formatDate()`, `formatNumber()`, `formatCurrency()`, `formatRelative()`. |
| `static/i18n/en.json` | Starter | English source of truth. Replace keys with your project's strings. |
| `scripts/validate_i18n.py` | 595 lines | 3-level validator: structural (free) + Kilo back-translation + LLM critique with auto-fix. |
| `docs/multilingual-plan.md` | 1170 lines | The bible. Architecture decisions, JSON spec, key naming, ICU plurals, anti-patterns, email localization, SEO strategy, testing, production gotchas. |
| `snippets/` | 5 files | Copy-paste patterns for HTML wiring, JS wiring, language switchers. |

## How It Works

```
Browser loads page
  → <head> runs i18n.js (synchronous, ~5ms)
    → Detects language: cookie → URL ?lang= → navigator.language → 'en'
    → Loads en.json (fallback, always)
    → Loads {lang}.json if not English
    → I18N._ready = true (strings available for JS)
  → DOMContentLoaded fires
    → _applyToDOM() replaces all data-i18n elements
    → Language switcher label updated
```

## Translation Workflow

```
1. Developer writes English UI
2. Add data-i18n="key" to every visible string
3. Create/update en.json with all keys
4. AI translates en.json → {lang}.json (Claude/GPT)
5. validate_i18n.py --validate {lang}
   ├── Level 1: Structural (keys match, placeholders preserved)
   ├── Level 2: Back-translation via Kilo CLI (semantic drift detection)
   └── Level 3: LLM Critique via Kilo CLI (tone/register/grammar)
   └── Auto-applies fixes to the JSON file
6. Ship.
```

## Supported Attributes

| Attribute | Replaces | Example |
|-----------|----------|---------|
| `data-i18n="key"` | `textContent` | `<span data-i18n="nav.home">Home</span>` |
| `data-i18n-placeholder="key"` | `placeholder` | `<input data-i18n-placeholder="auth.email_placeholder">` |
| `data-i18n-title="key"` | `title` (tooltip) | `<button data-i18n-title="common.delete">` |
| `data-i18n-html="key"` | `innerHTML` | `<span data-i18n-html="auth.terms_link">` |

## JS API

```javascript
I18N.t('key')                          // Get translated string
I18N.t('key', { name: 'John' })       // With variable interpolation
I18N.lang                              // Current language code
I18N.setLanguage('tr')                 // Switch language (reloads page)
I18N.formatDate(date)                  // Locale-aware date
I18N.formatDateTime(date)              // Locale-aware date+time
I18N.formatNumber(1234)                // Locale-aware number (1,234 or 1.234)
I18N.formatCurrency(29.99, 'USD')     // Locale-aware currency
I18N.formatRelative(date)              // "3 minutes ago" in current locale
I18N._applyToDOM()                     // Re-apply after dynamic innerHTML
```

## Validation

```bash
# Structural only (free, instant, CI/CD)
python scripts/validate_i18n.py

# Full validation with Kilo CLI (back-translate + critique + auto-fix)
python scripts/validate_i18n.py --validate tr

# Generate review CSV for human review
python scripts/validate_i18n.py --review-csv tr

# Set model per language
KILO_I18N_MODEL="kilo/x-ai/grok-4.3" python scripts/validate_i18n.py --validate tr
```

## Key Naming Convention

```
{page}.{element}           → nav.home, auth.email
{page}.{element}_{action}  → queue.confirm_delete
{page}.{element}_{state}   → dashboard.no_items
common.{noun}              → common.save, common.cancel
error.{type}               → error.not_found
```

## Anti-Patterns (don't do these)

```javascript
// BAD: concatenation — translator can't reorder
label = "You have " + count + " items";

// GOOD: variable interpolation
label = I18N.t('dashboard.items_count', { count: count });
// en.json: "items_count": "{count} items"
// ja.json: "items_count": "{count}件のアイテム"
```

```html
<!-- BAD: split sentence across elements -->
<span>Click </span><a href="/here">here</a><span> to continue</span>

<!-- GOOD: single translatable unit -->
<a href="/here" data-i18n="common.continue">Continue</a>
```

## Adding to a New Project — Checklist

- [ ] Copy `i18n.js` to `static/js/`
- [ ] Copy `validate_i18n.py` to `scripts/`
- [ ] Create `static/i18n/en.json` with your project's strings
- [ ] Add `<script src="/static/js/i18n.js">` to base template `<head>`
- [ ] Add `data-i18n` to every visible HTML string
- [ ] Replace JS hardcoded strings with `I18N.t()`
- [ ] Add `I18N._applyToDOM()` after every dynamic innerHTML
- [ ] Add language switcher (navbar or footer)
- [ ] Update `_supported` array in `i18n.js` if adding languages beyond the default 6
- [ ] Run `validate_i18n.py` in CI/CD pipeline

## Read the Full Bible

See `docs/multilingual-plan.md` for:
- Architecture decision (why client-side JSON, not gettext)
- ICU MessageFormat for plurals/gender
- Text expansion per language
- Character encoding (Turkish dotless-i, Japanese Kanji)
- RTL support path
- Email localization
- SEO/URL strategy (subfolder vs subdomain)
- Testing (pseudo-localization, visual regression)
- Production gotchas (flash-of-English, cache poisoning, stale translations)
