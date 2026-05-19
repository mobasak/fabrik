# i18n Kit — Multilingual GUI Template

Drop-in internationalization for any project with a user-facing GUI. One JSON format, one validation script, multiple loaders per platform.

## Platform Support

| Scaffold type | Loader | JSON path | Integration |
|---------------|--------|-----------|-------------|
| **static-site** | `static/js/i18n.js` (vanilla DOM) | `static/i18n/` | Works as-is |
| **desktop-app** (Electron) | `static/js/i18n.js` (vanilla DOM) | `static/i18n/` | Works as-is (Chromium renderer) |
| **saas-skeleton** (Next.js) | `react/I18nProvider.tsx` + `react/server.ts` | `public/i18n/` | React context + SSR |
| **chrome-extension** | Chrome `_locales/` API | `extension/_locales/` | Adapter: `adapters/chrome_messages.py` generates from `en.json` |
| **mobile-app** (React Native) | `i18next` + `react-i18next` | `src/locales/` | Adapter: `adapters/sync_rn_locales.py` copies + validates |
| **docusaurus** | Docusaurus built-in + `code.json` | `i18n/<lang>/code.json` | Adapter: `adapters/sync_docusaurus.py` syncs custom UI strings (nav, footer, homepage). Docs/blog use Docusaurus native markdown i18n. |
| **wordpress** | Polylang + gettext `.po/.mo` | N/A | **Not supported** — PHP-native pipeline |
| **python-api / node-api / file-api / file-worker** | N/A | N/A | No GUI — not applicable |

**Shared across all platforms:** `en.json` format, key naming convention, `validate_i18n.py`, translation workflow (AI first pass → validate → ship).

## Quick Start — Vanilla (static-site, desktop-app)

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

## Quick Start — Next.js (saas-skeleton)

### 1. Copy files to your project

```bash
cp react/I18nProvider.tsx   YOUR_PROJECT/lib/i18n/I18nProvider.tsx
cp react/server.ts          YOUR_PROJECT/lib/i18n/server.ts
cp react/LanguageSwitcher.tsx YOUR_PROJECT/lib/i18n/LanguageSwitcher.tsx
cp static/i18n/en.json      YOUR_PROJECT/public/i18n/en.json
cp scripts/validate_i18n.py  YOUR_PROJECT/scripts/validate_i18n.py
```

### 2. Wrap your root layout

```tsx
// app/layout.tsx
import { I18nProvider } from '@/lib/i18n/I18nProvider';
import { detectLanguage, loadTranslations, SUPPORTED } from '@/lib/i18n/server';

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const lang = await detectLanguage();
  const { strings, fallback } = loadTranslations(lang);
  return (
    <html lang={lang}>
      <body>
        <I18nProvider lang={lang} strings={strings} fallback={fallback} supported={SUPPORTED}>
          {children}
        </I18nProvider>
      </body>
    </html>
  );
}
```

### 3. Use in components

```tsx
'use client';
import { useI18n } from '@/lib/i18n/I18nProvider';
import { LanguageSwitcher } from '@/lib/i18n/LanguageSwitcher';

export function Dashboard() {
  const { t, formatDate } = useI18n();
  return (
    <div>
      <h1>{t('nav.dashboard')}</h1>
      <p>{t('dashboard.welcome', { name: 'Ozgur' })}</p>
      <p>{formatDate(new Date())}</p>
      <LanguageSwitcher />
    </div>
  );
}
```

### 4. Use in Server Components (no hook needed)

```tsx
// app/page.tsx (Server Component)
import { serverT } from '@/lib/i18n/server';

export default async function Home() {
  const t = await serverT();
  return <h1>{t('nav.home')}</h1>;
}
```

No flash-of-English because translations load server-side and render in the initial HTML.

## Quick Start — Chrome Extension

The Chrome extension i18n API requires `_locales/<lang>/messages.json` in a flat format. The adapter converts from the shared `en.json`:

```bash
# One-time: generate _locales/ from your i18n-kit JSON files
python adapters/chrome_messages.py

# In your extension code, use Chrome's native API:
# chrome.i18n.getMessage('nav_home')  ← dots become underscores
```

Add `"default_locale": "en"` to your `manifest.json`. The adapter maps `en.json` keys like `nav.home` → `nav_home` in Chrome format.

Run after every translation update. Can be wired into a pre-commit hook or CI.

## Quick Start — React Native (mobile-app)

React Native uses `i18next` + `react-i18next` per rule 80-mobile. The JSON format is identical to i18n-kit, so the adapter is a sync + validate:

```bash
# Sync all languages from static/i18n/ → src/locales/
python adapters/sync_rn_locales.py

# First time: also generate the i18next config
python adapters/sync_rn_locales.py --init

# In your app entry:
import './src/locales/i18n';  # generated config

# In components:
import { useTranslation } from 'react-i18next';
const { t } = useTranslation();
return <Text>{t('nav.dashboard')}</Text>;
```

The `--init` flag generates `src/locales/i18n.ts` with `expo-localization` device detection and all language resources imported. Run `sync_rn_locales.py` after every translation update.

## Quick Start — Docusaurus

Docusaurus has built-in i18n for docs and blog content (per rule 42-docusaurus). The adapter handles **custom UI strings only** — navbar labels, footer text, homepage content, error pages — via Docusaurus `code.json`:

```bash
# Sync custom UI strings from en.json → i18n/<lang>/code.json
python adapters/sync_docusaurus.py

# Only specific sections
python adapters/sync_docusaurus.py --sections nav,footer,homepage

# Preview
python adapters/sync_docusaurus.py --dry-run
```

The adapter merges into existing `code.json` (preserves Docusaurus-extracted keys from `npm run write-translations`). Default sections synced: `nav`, `common`, `footer`, `homepage`, `theme`, `error`.

For docs and blog content, use Docusaurus' native markdown i18n folder structure (`i18n/tr/docusaurus-plugin-content-docs/current/`). This adapter does not touch those.

## Files

| File | Purpose |
|------|---------|
| **Vanilla loader** | |
| `static/js/i18n.js` | Client-side DOM loader (166 lines). Detects language, loads JSON, replaces `data-i18n` elements. Includes `formatDate/Number/Currency/Relative()`. For static-site, desktop-app. |
| `static/i18n/en.json` | English source of truth. Replace keys with your project's strings. |
| `snippets/` | 5 copy-paste patterns: navbar switcher, footer switcher, head tag, HTML wiring, JS wiring. |
| **React/Next.js loader** | |
| `react/I18nProvider.tsx` | React context provider + `useI18n()` hook. `t()`, `setLanguage()`, `formatDate/Number/Currency/Relative()`. |
| `react/server.ts` | Server-side helpers for Next.js App Router: `detectLanguage()` (cookie → Accept-Language → en), `loadTranslations()` (reads JSON from disk), `serverT()` (translate in Server Components). |
| `react/LanguageSwitcher.tsx` | Drop-in `<select>` language switcher component. |
| **Platform adapters** | |
| `adapters/chrome_messages.py` | Converts `en.json` → Chrome `_locales/<lang>/messages.json` (flat format, dots→underscores). |
| `adapters/sync_rn_locales.py` | Copies `en.json` → `src/locales/<lang>.json` for React Native i18next. `--init` generates the i18next config. |
| `adapters/sync_docusaurus.py` | Syncs custom UI strings (nav, footer, homepage) → Docusaurus `i18n/<lang>/code.json`. Merges with Docusaurus-extracted keys. |
| **Shared** | |
| `scripts/validate_i18n.py` | 3-level validator (595 lines): structural (free) + Kilo back-translation + LLM critique with auto-fix. Works for all platforms. |
| `docs/multilingual-plan.md` | Architecture bible (1170 lines): JSON spec, key naming, ICU plurals, anti-patterns, email localization, SEO strategy, testing, production gotchas. |

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
